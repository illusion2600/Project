"""Business operations for the Campus Pantry university showcase release.

Each function that changes data runs as ONE transaction: `with conn:` commits when the
block finishes and rolls back if any step raises, so the database never keeps half of
an operation. Database rules (capacity, one booking per day, valid statuses) are still
enforced by the constraints and triggers in 01_schema.sql; this layer adds the locking
and the user-facing checks around them.
"""
import datetime
import re
import secrets
import time

import psycopg2

from db import error_message

OPENING_TIME = "10:00"
CLOSING_TIME = "16:00"          # no-shows are only marked after the operating day ends
SESSION_MINUTES = 30
SHIFT_HOURS = 2
NEAR_CAPACITY = 0.8             # 80% full counts as "near capacity"


class PantryError(Exception):
    """A business-rule failure to show to the user."""


def _run(conn, work):
    """Commit once, roll back on failure, and retry transient transaction conflicts."""
    for attempt in range(3):
        try:
            with conn:
                with conn.cursor() as cur:
                    return work(cur)
        except psycopg2.Error as exc:
            if exc.pgcode in ("40001", "40P01") and attempt < 2:
                time.sleep(0.03 * (attempt + 1))
                continue
            raise PantryError(error_message(exc)) from exc


def _query(conn, sql, params=()):
    def work(cur):
        cur.execute(sql, params)
        return cur.fetchall()
    return _run(conn, work)


def _require_staff(cur, unikey):
    cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active", (unikey,))
    if cur.fetchone() is None:
        raise PantryError("Only active staff can perform this action.")


def _require_volunteer(cur, unikey, lock=False):
    cur.execute("SELECT 1 FROM volunteer WHERE unikey = %s AND is_active" +
                (" FOR UPDATE" if lock else ""), (unikey,))
    if cur.fetchone() is None:
        raise PantryError("Only active volunteers can perform this action.")


def _staff_query(conn, staff_unikey, sql, params=()):
    def work(cur):
        _require_staff(cur, staff_unikey)
        cur.execute(sql, params)
        return cur.fetchall()
    return _run(conn, work)


def _business_now(cur):
    """Authoritative Sydney clock; tests may patch this private seam."""
    cur.execute("SELECT CURRENT_TIMESTAMP AT TIME ZONE 'Australia/Sydney'")
    return cur.fetchone()[0]


def current_business_date(conn):
    return _run(conn, lambda cur: _business_now(cur).date())


def _date(value):
    if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
        return value
    try:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise PantryError("Enter a valid date in YYYY-MM-DD format.") from exc


def _shift(cur, shift_id, lock=False):
    cur.execute("SELECT shift_date, start_time, end_time, status FROM pantry_shift "
                "WHERE shift_id = %s" + (" FOR UPDATE" if lock else ""), (shift_id,))
    row = cur.fetchone()
    if row is None:
        raise PantryError(f"Shift {shift_id} does not exist.")
    return row


def _editable_shift(cur, shift_id):
    row = _shift(cur, shift_id, lock=True)
    if row[3] == "CLOSED":
        raise PantryError("A CLOSED shift cannot be changed.")
    return row


# ---------------------------------------------------------------- people

UNIKEY_PATTERN = re.compile(r"[a-z]{4}[0-9]{4}")     # e.g. abcd0123


def valid_unikey(unikey):
    return isinstance(unikey, str) and bool(UNIKEY_PATTERN.fullmatch(unikey))


def find_person(conn, unikey):
    """Return (full_name, is_student, is_volunteer, is_staff) or None."""
    rows = _query(conn, """
        SELECT p.full_name,
               EXISTS (SELECT 1 FROM student s WHERE s.unikey = p.unikey),
               EXISTS (SELECT 1 FROM volunteer v WHERE v.unikey = p.unikey AND v.is_active),
               EXISTS (SELECT 1 FROM staff st WHERE st.unikey = p.unikey AND st.is_active)
        FROM person p WHERE p.unikey = %s""", (unikey,))
    return rows[0] if rows else None


# ---------------------------------------------------------------- sessions

def list_sessions(conn, on_date):
    """Sessions on a date with live capacity figures (view v_booking_attendance)."""
    return _query(conn, """
        SELECT session_id, start_time, end_time, active_bookings, capacity, spaces_remaining
        FROM v_booking_attendance
        WHERE session_date = %s::date
        ORDER BY start_time""", (_date(on_date),))


def set_up_day(conn, on_date, staff_unikey=None):
    """Create the day's 3 two-hour shifts and 12 half-hour sessions in one transaction."""
    on_date = _date(on_date)
    def work(cur):
        _require_staff(cur, staff_unikey)
        if on_date < _business_now(cur).date():
            raise PantryError("Cannot set up an operating day in the past.")
        cur.execute("SELECT count(*) FROM pantry_shift WHERE shift_date = %s::date", (on_date,))
        if int(cur.fetchone()[0]) > 0:
            raise PantryError(f"Shifts already exist for {on_date}.")
        created = 0
        for shift_no in range(3):
            cur.execute("""
                INSERT INTO pantry_shift (shift_date, start_time, end_time)
                VALUES (%s::date,
                        %s::time + make_interval(hours => %s),
                        %s::time + make_interval(hours => %s))
                RETURNING shift_id""",
                (on_date, OPENING_TIME, shift_no * SHIFT_HOURS,
                 OPENING_TIME, (shift_no + 1) * SHIFT_HOURS))
            shift_id = cur.fetchone()[0]
            for slot in range(SHIFT_HOURS * 60 // SESSION_MINUTES):
                start = shift_no * SHIFT_HOURS * 60 + slot * SESSION_MINUTES
                cur.execute("""
                    INSERT INTO session (session_date, start_time, end_time, shift_id)
                    VALUES (%s::date,
                            %s::time + make_interval(mins => %s),
                            %s::time + make_interval(mins => %s),
                            %s)
                    RETURNING session_id""",
                    (on_date, OPENING_TIME, start, OPENING_TIME, start + SESSION_MINUTES, shift_id))
                created += 1
        return created
    return _run(conn, work)


def set_shift_status(conn, staff_unikey, shift_id, status):
    """Advance PLANNED -> OPEN -> CLOSED; database validates staffing and stock."""
    status = status.upper()
    if status not in ("OPEN", "CLOSED"):
        raise PantryError("Choose OPEN or CLOSED for the next shift status.")
    def work(cur):
        _require_staff(cur, staff_unikey)
        shift = _shift(cur, shift_id, lock=True)
        expected = "PLANNED" if status == "OPEN" else "OPEN"
        if shift[3] != expected:
            raise PantryError(f"Only a {expected} shift can become {status}.")
        cur.execute("UPDATE pantry_shift SET status = %s WHERE shift_id = %s", (status, shift_id))
        return status
    return _run(conn, work)


# ---------------------------------------------------------------- bookings

def book_session(conn, unikey, session_id, override_by_staff=None, reason=None):
    """Book a session and return the QR token.

    Steps in one transaction:
      1. lock the student's row, so two simultaneous requests from the same student
         are handled one after the other (otherwise both could pass the
         one-booking-per-day check and both succeed);
      2. validate student eligibility;
      3. if admin override, validate staff identity and non-empty reason;
      4. check session exists and has not already finished (unless override);
      5. insert booking with fresh random token; booking trigger locks session row
         and enforces capacity and daily limit.
    """
    def work(cur):
        cur.execute("SELECT unikey FROM student WHERE unikey = %s FOR UPDATE", (unikey,))
        if cur.fetchone() is None:
            raise PantryError(f"{unikey} is not a registered student.")

        if override_by_staff is not None:
            _require_staff(cur, override_by_staff)
            if not reason or not reason.strip():
                raise PantryError("A reason must be provided for an administrative override.")
        elif reason:
            raise PantryError("An override reason must have an acting staff member.")

        cur.execute("""
            SELECT s.session_date, s.end_time, sh.status
            FROM session s JOIN pantry_shift sh ON sh.shift_id = s.shift_id
            WHERE s.session_id = %s FOR UPDATE OF s""", (session_id,))
        row = cur.fetchone()
        if row is None:
            raise PantryError(f"Session {session_id} does not exist.")
        now = _business_now(cur)
        if row[2] == "CLOSED":
            raise PantryError("Cannot book a session in a CLOSED shift.")
        if row[0] < now.date() or (row[0] == now.date() and now.time() >= datetime.time(16)):
            raise PantryError("Cannot book a session after its operating day has ended.")
        if datetime.datetime.combine(row[0], row[1]) <= now and override_by_staff is None:
            raise PantryError(f"Session {session_id} has already finished.")

        token = secrets.token_urlsafe(24)
        cur.execute("""
            INSERT INTO booking (student_unikey, session_id, qr_token,
                                 admin_override, override_by_staff, override_reason)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING booking_id""",
            (unikey, session_id, token, override_by_staff is not None,
             override_by_staff, reason.strip() if reason else None))
        return cur.fetchone()[0], token
    return _run(conn, work)


def my_bookings(conn, unikey):
    return _query(conn, """
        SELECT b.booking_id, s.session_date, s.start_time, b.status, b.qr_token
        FROM booking b JOIN session s ON s.session_id = b.session_id
        WHERE b.student_unikey = %s
        ORDER BY s.session_date DESC, s.start_time""", (unikey,))


def cancel_booking(conn, unikey, booking_id):
    def work(cur):
        cur.execute("SELECT 1 FROM student WHERE unikey = %s FOR UPDATE", (unikey,))
        if cur.fetchone() is None:
            raise PantryError("Only a registered student can cancel their booking.")
        cur.execute("""
            SELECT b.status, s.session_date + s.end_time
            FROM booking b JOIN session s ON s.session_id = b.session_id
            WHERE b.booking_id = %s AND b.student_unikey = %s FOR UPDATE OF b""", (booking_id, unikey))
        row = cur.fetchone()
        if row is None or row[0] != "CONFIRMED":
            raise PantryError("No confirmed booking with that number belongs to you.")
        if row[1] <= _business_now(cur):
            raise PantryError("A booking cannot be cancelled after the session has finished.")
        cur.execute("UPDATE booking SET status = 'CANCELLED', attendance_at = NULL WHERE booking_id = %s", (booking_id,))
    _run(conn, work)


def check_in(conn, qr_token, staff_unikey=None):
    """Check in on the booked day during operating hours, including late arrivals.

    A previously opened shift may already be CLOSED: closure freezes its stock
    and staffing, while BR09 allows its students to arrive until 16:00.
    """
    def work(cur):
        _require_staff(cur, staff_unikey)
        cur.execute("""
            SELECT b.booking_id, b.student_unikey, b.status, s.session_date, sh.status
            FROM booking b
            JOIN session s ON s.session_id = b.session_id
            JOIN pantry_shift sh ON sh.shift_id = s.shift_id
            WHERE b.qr_token = %s
            FOR UPDATE OF b""", (qr_token,))
        row = cur.fetchone()
        if row is None:
            raise PantryError("Unknown check-in token.")
        b_id, student, status, s_date, shift_status = row
        now = _business_now(cur)
        if s_date != now.date():
            raise PantryError(f"This token is valid only on its booking date, {s_date}.")
        if not datetime.time(10) <= now.time() < datetime.time(16):
            raise PantryError("Check-in is available only during 10:00-16:00 Sydney time.")
        if status == "ATTENDED":
            return b_id, student
        if status != "CONFIRMED":
            raise PantryError(f"Cannot check in: this booking is {status}.")
        if shift_status == "PLANNED":
            raise PantryError("Check-in requires a shift that has been opened.")

        cur.execute("""
            UPDATE booking SET status = 'ATTENDED', attendance_at = %s AT TIME ZONE 'Australia/Sydney'
            WHERE booking_id = %s
            RETURNING booking_id, student_unikey""", (now, b_id))
        return cur.fetchone()
    return _run(conn, work)


def mark_no_shows(conn, staff_unikey=None):
    """Mark ABSENT every confirmed booking whose operating day has ended (after 16:00)."""
    def work(cur):
        _require_staff(cur, staff_unikey)
        now = _business_now(cur)
        cur.execute("""
            UPDATE booking b SET status = 'ABSENT', attendance_at = NULL
            FROM session s
            WHERE s.session_id = b.session_id
              AND b.status = 'CONFIRMED'
              AND (s.session_date + %s::time) <= %s::timestamp
            RETURNING b.booking_id""", (CLOSING_TIME, now))
        return len(cur.fetchall())
    return _run(conn, work)


# ---------------------------------------------------------------- volunteers

def list_upcoming_shifts(conn):
    """List scheduled shifts with count of confirmed volunteers."""
    def work(cur):
        now = _business_now(cur)
        cur.execute("""
            SELECT sh.shift_id, sh.shift_date, sh.start_time, sh.end_time, sh.status,
                   COUNT(vs.volunteer_unikey) FILTER (WHERE vs.status = 'APPROVED') AS approved_volunteers
            FROM pantry_shift sh
            LEFT JOIN volunteer_shift vs ON vs.shift_id = sh.shift_id
            WHERE sh.status <> 'CLOSED' AND sh.shift_date + sh.end_time > %s::timestamp
            GROUP BY sh.shift_id
            ORDER BY sh.shift_date, sh.start_time""", (now,))
        return cur.fetchall()
    return _run(conn, work)


def request_volunteer_shift(conn, volunteer_unikey, shift_id):
    """Volunteer registers for a shift; records a PENDING request."""
    def work(cur):
        _require_volunteer(cur, volunteer_unikey, lock=True)
        shift = _editable_shift(cur, shift_id)
        if datetime.datetime.combine(shift[0], shift[2]) <= _business_now(cur):
            raise PantryError("Cannot request to join a shift that has ended.")

        cur.execute("SELECT status FROM volunteer_shift WHERE shift_id = %s AND volunteer_unikey = %s FOR UPDATE",
                    (shift_id, volunteer_unikey))
        existing = cur.fetchone()
        if existing:
            st = existing[0]
            if st == "PENDING":
                raise PantryError("You already have a pending request for this shift.")
            elif st == "APPROVED":
                raise PantryError("You are already approved and assigned to this shift.")
            else:  # REJECTED - allow re-applying as PENDING
                cur.execute("""
                    UPDATE volunteer_shift
                    SET status = 'PENDING', request_date = now(), reviewed_by_staff = NULL, reviewed_at = NULL
                    WHERE shift_id = %s AND volunteer_unikey = %s""", (shift_id, volunteer_unikey))
                return shift_id

        cur.execute("""
            INSERT INTO volunteer_shift (shift_id, volunteer_unikey, status)
            VALUES (%s, %s, 'PENDING')""", (shift_id, volunteer_unikey))
        return shift_id
    return _run(conn, work)


def my_volunteer_shifts(conn, volunteer_unikey):
    """View volunteer's pending, approved, and rejected shift requests."""
    def work(cur):
        _require_volunteer(cur, volunteer_unikey)
        cur.execute("""
            SELECT vs.shift_id, sh.shift_date, sh.start_time, sh.end_time,
                   vs.status, vs.request_date, vs.reviewed_at
            FROM volunteer_shift vs
            JOIN pantry_shift sh ON sh.shift_id = vs.shift_id
            WHERE vs.volunteer_unikey = %s
            ORDER BY sh.shift_date DESC, sh.start_time""", (volunteer_unikey,))
        return cur.fetchall()
    return _run(conn, work)


def withdraw_volunteer_request(conn, volunteer_unikey, shift_id):
    """Withdraw a pending volunteer request."""
    def work(cur):
        _require_volunteer(cur, volunteer_unikey, lock=True)
        _editable_shift(cur, shift_id)
        cur.execute("""
            DELETE FROM volunteer_shift
            WHERE shift_id = %s AND volunteer_unikey = %s AND status = 'PENDING'
            RETURNING shift_id""", (shift_id, volunteer_unikey))
        if cur.fetchone() is None:
            cur.execute("SELECT status FROM volunteer_shift WHERE shift_id = %s AND volunteer_unikey = %s",
                        (shift_id, volunteer_unikey))
            row = cur.fetchone()
            if row is None:
                raise PantryError("No shift request found for that shift.")
            raise PantryError(f"Cannot withdraw request because it is already {row[0]}.")
    _run(conn, work)


def list_volunteer_requests(conn, on_date=None, status_filter=None, staff_unikey=None):
    """Staff view of volunteer shift requests."""
    sql = """
        SELECT vs.shift_id, sh.shift_date, sh.start_time, sh.end_time,
               vs.volunteer_unikey, pe.full_name, vs.status, vs.request_date
        FROM volunteer_shift vs
        JOIN pantry_shift sh ON sh.shift_id = vs.shift_id
        JOIN person pe ON pe.unikey = vs.volunteer_unikey
        WHERE 1=1
    """
    params = []
    if on_date:
        sql += " AND sh.shift_date = %s::date"
        params.append(_date(on_date))
    if status_filter:
        status_filter = status_filter.upper()
        if status_filter not in ("PENDING", "APPROVED", "REJECTED"):
            raise PantryError("Status must be PENDING, APPROVED, or REJECTED.")
        sql += " AND vs.status = %s"
        params.append(status_filter)
    sql += " ORDER BY sh.shift_date, sh.start_time, vs.request_date"
    return _staff_query(conn, staff_unikey, sql, tuple(params))


def review_volunteer_request(conn, staff_unikey, shift_id, volunteer_unikey, decision):
    """Staff approves or rejects a volunteer shift request."""
    decision = decision.upper()
    if decision not in ("APPROVED", "REJECTED"):
        raise PantryError("Decision must be APPROVED or REJECTED.")
    def work(cur):
        _require_staff(cur, staff_unikey)
        _require_volunteer(cur, volunteer_unikey, lock=True)
        shift = _editable_shift(cur, shift_id)
        if datetime.datetime.combine(shift[0], shift[2]) <= _business_now(cur):
            raise PantryError("Cannot review a request after its shift has ended.")
        cur.execute("""
            UPDATE volunteer_shift
            SET status = %s, reviewed_by_staff = %s, reviewed_at = now()
            WHERE shift_id = %s AND volunteer_unikey = %s AND status = 'PENDING'
            RETURNING shift_id""", (decision, staff_unikey, shift_id, volunteer_unikey))
        if cur.fetchone() is None:
            raise PantryError("No pending request remains; it may already have been reviewed.")
        return decision
    return _run(conn, work)


# ---------------------------------------------------------------- staff assignments

def assign_staff_shift(conn, assigner_staff_unikey, shift_id, target_staff_unikey, role):
    """Assign a staff member to a shift as MAIN_SUPERVISOR or ASSISTANT."""
    role = role.upper()
    if role not in ("MAIN_SUPERVISOR", "ASSISTANT"):
        raise PantryError("Duty role must be MAIN_SUPERVISOR or ASSISTANT.")
    def work(cur):
        _require_staff(cur, assigner_staff_unikey)
        cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active FOR UPDATE", (target_staff_unikey,))
        if cur.fetchone() is None:
            raise PantryError(f"{target_staff_unikey} is not an active staff member.")
        shift = _shift(cur, shift_id, lock=True)
        if shift[3] != "PLANNED":
            raise PantryError("Staff assignments can be changed only while the shift is PLANNED.")
        cur.execute("""
            INSERT INTO shift_staff_assignment (shift_id, staff_unikey, assignment_role)
            VALUES (%s, %s, %s)
            ON CONFLICT (shift_id, staff_unikey)
            DO UPDATE SET assignment_role = EXCLUDED.assignment_role""",
            (shift_id, target_staff_unikey, role))
    return _run(conn, work)


# ---------------------------------------------------------------- stock

def record_stock_count(conn, staff_unikey, stock_number, count_type, qty, shift_id=None, notes=None):
    if isinstance(qty, bool) or not isinstance(qty, int) or qty < 0:
        raise PantryError("A counted quantity must be a nonnegative whole number.")
    count_type = count_type.upper()
    if count_type not in ('OPENING', 'CLOSING', 'SPOT_CHECK'):
        raise PantryError("Count type must be OPENING, CLOSING or SPOT_CHECK.")
    if count_type in ('OPENING', 'CLOSING') and shift_id is None:
        raise PantryError("Opening and closing counts must identify a shift.")
    def work(cur):
        _require_staff(cur, staff_unikey)
        if shift_id is not None:
            _editable_shift(cur, shift_id)
        cur.execute("SELECT 1 FROM stock_batch WHERE stock_number = %s", (stock_number,))
        if cur.fetchone() is None:
            raise PantryError(f"Stock number {stock_number} does not exist.")
        if count_type in ('OPENING', 'CLOSING'):
            cur.execute("""
                SELECT opening_qty, closing_qty FROM shift_stock_count
                WHERE shift_id = %s AND stock_number = %s FOR UPDATE""", (shift_id, stock_number))
            summary = cur.fetchone()
            if count_type == 'OPENING':
                if summary is not None:
                    raise PantryError("An opening count already exists for this batch and shift.")
                cur.execute("""
                    INSERT INTO shift_stock_count (shift_id, stock_number, opening_qty)
                    VALUES (%s, %s, %s)""", (shift_id, stock_number, qty))
            else:
                if summary is None:
                    raise PantryError("Record a real opening count before the closing count.")
                if summary[1] is not None:
                    raise PantryError("A closing count already exists for this batch and shift.")
                cur.execute("""
                    SELECT COALESCE(SUM(CASE WHEN adjustment_kind = 'RECEIPT'
                        THEN quantity ELSE -quantity END), 0)
                    FROM stock_adjustment WHERE shift_id = %s AND stock_number = %s""", (shift_id, stock_number))
                available = summary[0] + cur.fetchone()[0]
                if qty > available:
                    raise PantryError("Closing quantity exceeds opening plus receipts minus waste; reconcile receipts first.")
                cur.execute("""
                    UPDATE shift_stock_count SET closing_qty = %s
                    WHERE shift_id = %s AND stock_number = %s""", (qty, shift_id, stock_number))
        cur.execute("""
            INSERT INTO stock_count (stock_number, shift_id, counted_by_staff,
                                     count_type, counted_qty, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING stock_count_id""",
            (stock_number, shift_id, staff_unikey, count_type, qty, notes))
        return cur.fetchone()[0]
    return _run(conn, work)


def record_stock_adjustment(conn, staff_unikey, shift_id, stock_number, adjustment_kind, qty, reason):
    """Record an intra-shift stock adjustment (RECEIPT or WASTE)."""
    if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
        raise PantryError("Adjustment quantity must be a positive whole number.")
    adjustment_kind = adjustment_kind.upper()
    if adjustment_kind not in ('RECEIPT', 'WASTE'):
        raise PantryError("Adjustment kind must be RECEIPT or WASTE.")
    if not reason or not reason.strip():
        raise PantryError("Adjustment reason cannot be blank.")
    def work(cur):
        _require_staff(cur, staff_unikey)
        _editable_shift(cur, shift_id)
        cur.execute("SELECT opening_qty, closing_qty FROM shift_stock_count WHERE shift_id = %s AND stock_number = %s FOR UPDATE",
                    (shift_id, stock_number))
        summary = cur.fetchone()
        if summary is None:
            raise PantryError("Record a real opening count before recording adjustments.")
        if summary[1] is not None:
            raise PantryError("Adjustments cannot be added after the closing count.")
        cur.execute("""
            SELECT COALESCE(SUM(CASE WHEN adjustment_kind = 'RECEIPT'
                THEN quantity ELSE -quantity END), 0)
            FROM stock_adjustment WHERE shift_id = %s AND stock_number = %s""", (shift_id, stock_number))
        net_adjustment = cur.fetchone()[0]
        if adjustment_kind == 'WASTE' and qty > summary[0] + net_adjustment:
            raise PantryError("Waste exceeds the available recorded stock.")
        cur.execute("""
            INSERT INTO stock_adjustment (shift_id, stock_number, adjustment_kind, quantity, reason)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (shift_id, stock_number, adjustment_kind)
            DO UPDATE SET quantity = stock_adjustment.quantity + EXCLUDED.quantity,
                          reason = EXCLUDED.reason""",
            (shift_id, stock_number, adjustment_kind, qty, reason.strip()))
    return _run(conn, work)


# ---------------------------------------------------------------- reports

def report_day_summary(conn, on_date, staff_unikey=None):
    return _staff_query(conn, staff_unikey, """
        SELECT session_id, start_time, active_bookings, attended, absent,
               awaiting_checkin, spaces_remaining
        FROM v_booking_attendance
        WHERE session_date = %s::date
        ORDER BY start_time""", (_date(on_date),))


def report_near_capacity(conn, staff_unikey=None):
    return _staff_query(conn, staff_unikey, """
        SELECT session_date, start_time, active_bookings, capacity
        FROM v_booking_attendance
        WHERE active_bookings >= CEIL(capacity * %s)
        ORDER BY session_date, start_time""", (NEAR_CAPACITY,))


def report_low_stock(conn, staff_unikey=None):
    return _staff_query(conn, staff_unikey, """
        SELECT p.product_name, COALESCE(SUM(l.last_counted_qty), 0) AS on_hand,
               p.low_stock_threshold, p.counting_unit
        FROM product p
        LEFT JOIN v_latest_stock_count l ON l.product_id = p.product_id
        GROUP BY p.product_id, p.product_name, p.low_stock_threshold, p.counting_unit
        HAVING COALESCE(SUM(l.last_counted_qty), 0) < p.low_stock_threshold
        ORDER BY on_hand""")


def latest_stock(conn, staff_unikey=None):
    return _staff_query(conn, staff_unikey, """
        SELECT stock_number, product_name, last_counted_qty, counting_unit, count_type
        FROM v_latest_stock_count
        ORDER BY product_name, stock_number""")


def my_shifts(conn, staff_unikey):
    """List shifts assigned to a specific staff member."""
    return _staff_query(conn, staff_unikey, """
        SELECT sh.shift_id, sh.shift_date, sh.start_time, sh.end_time, a.assignment_role, sh.status
        FROM pantry_shift sh
        JOIN shift_staff_assignment a ON a.shift_id = sh.shift_id
        WHERE a.staff_unikey = %s
        ORDER BY sh.shift_date DESC, sh.start_time""", (staff_unikey,))


def session_bookings(conn, session_id, staff_unikey=None):
    """List bookings and attendance for a specific session."""
    return _staff_query(conn, staff_unikey, """
        SELECT b.booking_id, b.student_unikey, p.full_name, b.status, b.qr_token, b.attendance_at, b.admin_override
        FROM booking b
        JOIN person p ON p.unikey = b.student_unikey
        WHERE b.session_id = %s
        ORDER BY b.booking_id""", (session_id,))


def shift_roster(conn, on_date, staff_unikey=None):
    """View full staffing and approved volunteer roster for shifts on a given date."""
    on_date = _date(on_date)
    return _staff_query(conn, staff_unikey, """
        SELECT sh.shift_id, sh.start_time, sh.end_time, 'Staff' AS person_role,
               a.assignment_role AS duty, pe.full_name, pe.unikey
        FROM pantry_shift sh
        JOIN shift_staff_assignment a ON a.shift_id = sh.shift_id
        JOIN person pe ON pe.unikey = a.staff_unikey
        WHERE sh.shift_date = %s::date
        UNION ALL
        SELECT sh.shift_id, sh.start_time, sh.end_time, 'Volunteer' AS person_role,
               'VOLUNTEER (APPROVED)' AS duty, pe.full_name, pe.unikey
        FROM pantry_shift sh
        JOIN volunteer_shift vs ON vs.shift_id = sh.shift_id
        JOIN person pe ON pe.unikey = vs.volunteer_unikey
        WHERE sh.shift_date = %s::date AND vs.status = 'APPROVED'
        ORDER BY 2, 4, 6""", (on_date, on_date))


def report_shift_stock(conn, on_date, staff_unikey=None):
    """Reconciliation is an estimate: opening + receipts - waste - closing."""
    return _staff_query(conn, staff_unikey, """
        SELECT r.shift_id, sh.status, r.stock_number, r.product_name, r.opening_qty,
               r.received_qty, r.waste_qty, r.closing_qty, r.estimated_dispensed_qty
        FROM v_shift_stock_report r JOIN pantry_shift sh ON sh.shift_id = r.shift_id
        WHERE r.shift_date = %s::date
        ORDER BY r.start_time, r.stock_number""", (_date(on_date),))


