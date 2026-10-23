"""Business operations for the Campus Pantry prototype.

Each function that changes data runs as ONE transaction: `with conn:` commits when the
block finishes and rolls back if any step raises, so the database never keeps half of
an operation. Database rules (capacity, one booking per day, valid statuses) are still
enforced by the constraints and triggers in 01_schema.sql; this layer adds the locking
and the user-facing checks around them.
"""
import re
import secrets

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
    """Run work(cur) as one transaction and turn database errors into PantryError."""
    try:
        with conn:
            with conn.cursor() as cur:
                return work(cur)
    except psycopg2.Error as exc:
        raise PantryError(error_message(exc)) from exc


def _query(conn, sql, params=()):
    with conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


# ---------------------------------------------------------------- people

UNIKEY_PATTERN = re.compile(r"[a-z]{4}[0-9]{4}")     # e.g. abcd0123


def valid_unikey(unikey):
    return bool(UNIKEY_PATTERN.fullmatch(unikey))


def find_person(conn, unikey):
    """Return (full_name, is_student, is_volunteer, is_staff) or None."""
    rows = _query(conn, """
        SELECT p.full_name,
               EXISTS (SELECT 1 FROM student s WHERE s.unikey = p.unikey),
               EXISTS (SELECT 1 FROM volunteer v WHERE v.unikey = p.unikey),
               EXISTS (SELECT 1 FROM staff st WHERE st.unikey = p.unikey)
        FROM person p WHERE p.unikey = %s""", (unikey,))
    return rows[0] if rows else None


# ---------------------------------------------------------------- sessions

def list_sessions(conn, on_date):
    """Sessions on a date with live capacity figures (view v_booking_attendance)."""
    return _query(conn, """
        SELECT session_id, start_time, end_time, active_bookings, capacity, spaces_remaining
        FROM v_booking_attendance
        WHERE session_date = %s::date
        ORDER BY start_time""", (on_date,))


def set_up_day(conn, on_date):
    """Create the day's 3 two-hour shifts and 12 half-hour sessions in one transaction."""
    def work(cur):
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
            cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active", (override_by_staff,))
            if cur.fetchone() is None:
                raise PantryError(f"Staff member {override_by_staff} does not exist or is inactive.")
            if not reason or not reason.strip():
                raise PantryError("A reason must be provided for an administrative override.")

        cur.execute("""
            SELECT (session_date + end_time) < localtimestamp, session_date
            FROM session WHERE session_id = %s""", (session_id,))
        row = cur.fetchone()
        if row is None:
            raise PantryError(f"Session {session_id} does not exist.")
        if row[0] and override_by_staff is None:
            raise PantryError(f"Session {session_id} has already finished.")

        token = secrets.token_urlsafe(12)
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
        cur.execute("""
            UPDATE booking SET status = 'CANCELLED'
            WHERE booking_id = %s AND student_unikey = %s AND status = 'CONFIRMED'
            RETURNING booking_id""", (booking_id, unikey))
        if cur.fetchone() is None:
            raise PantryError("No confirmed booking with that number belongs to you.")
    _run(conn, work)


def check_in(conn, qr_token):
    """Front-desk scan: CONFIRMED -> ATTENDED atomically."""
    def work(cur):
        cur.execute("""
            SELECT b.booking_id, b.student_unikey, b.status, s.session_date
            FROM booking b
            JOIN session s ON s.session_id = b.session_id
            WHERE b.qr_token = %s
            FOR UPDATE OF b""", (qr_token,))
        row = cur.fetchone()
        if row is None:
            raise PantryError("Unknown QR code.")
        b_id, student, status, s_date = row
        if status != "CONFIRMED":
            raise PantryError(f"Cannot check in: this booking is {status}.")

        cur.execute("SELECT CURRENT_DATE")
        today = cur.fetchone()[0]
        if s_date > today:
            raise PantryError(f"Cannot check in: this booking is for a future session on {s_date}.")

        cur.execute("""
            UPDATE booking SET status = 'ATTENDED', attendance_at = now()
            WHERE booking_id = %s
            RETURNING booking_id, student_unikey""", (b_id,))
        return cur.fetchone()
    return _run(conn, work)


def mark_no_shows(conn):
    """Mark ABSENT every confirmed booking whose operating day has ended (after 16:00)."""
    def work(cur):
        cur.execute("""
            UPDATE booking b SET status = 'ABSENT'
            FROM session s
            WHERE s.session_id = b.session_id
              AND b.status = 'CONFIRMED'
              AND (s.session_date + %s::time) <= localtimestamp
            RETURNING b.booking_id""", (CLOSING_TIME,))
        return len(cur.fetchall())
    return _run(conn, work)


# ---------------------------------------------------------------- volunteers

def list_upcoming_shifts(conn):
    """List scheduled shifts with count of confirmed volunteers."""
    return _query(conn, """
        SELECT sh.shift_id, sh.shift_date, sh.start_time, sh.end_time, sh.status,
               COUNT(vs.volunteer_unikey) FILTER (WHERE vs.status = 'APPROVED') AS approved_volunteers
        FROM pantry_shift sh
        LEFT JOIN volunteer_shift vs ON vs.shift_id = sh.shift_id
        GROUP BY sh.shift_id
        ORDER BY sh.shift_date, sh.start_time""")


def request_volunteer_shift(conn, volunteer_unikey, shift_id):
    """Volunteer registers for a shift; records a PENDING request."""
    def work(cur):
        cur.execute("SELECT 1 FROM volunteer WHERE unikey = %s AND is_active", (volunteer_unikey,))
        if cur.fetchone() is None:
            raise PantryError(f"{volunteer_unikey} is not an active volunteer.")

        cur.execute("SELECT shift_date, start_time, end_time, status FROM pantry_shift WHERE shift_id = %s", (shift_id,))
        shift = cur.fetchone()
        if shift is None:
            raise PantryError(f"Shift {shift_id} does not exist.")
        if shift[3] == "CLOSED":
            raise PantryError("Cannot request to join a CLOSED shift.")

        cur.execute("SELECT status FROM volunteer_shift WHERE shift_id = %s AND volunteer_unikey = %s",
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
    return _query(conn, """
        SELECT vs.shift_id, sh.shift_date, sh.start_time, sh.end_time,
               vs.status, vs.request_date, vs.reviewed_at
        FROM volunteer_shift vs
        JOIN pantry_shift sh ON sh.shift_id = vs.shift_id
        WHERE vs.volunteer_unikey = %s
        ORDER BY sh.shift_date DESC, sh.start_time""", (volunteer_unikey,))


def withdraw_volunteer_request(conn, volunteer_unikey, shift_id):
    """Withdraw a pending volunteer request."""
    def work(cur):
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


def list_volunteer_requests(conn, on_date=None, status_filter=None):
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
        params.append(on_date)
    if status_filter:
        sql += " AND vs.status = %s"
        params.append(status_filter)
    sql += " ORDER BY sh.shift_date, sh.start_time, vs.request_date"
    return _query(conn, sql, tuple(params))


def review_volunteer_request(conn, staff_unikey, shift_id, volunteer_unikey, decision):
    """Staff approves or rejects a volunteer shift request."""
    decision = decision.upper()
    if decision not in ("APPROVED", "REJECTED"):
        raise PantryError("Decision must be APPROVED or REJECTED.")
    def work(cur):
        cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active", (staff_unikey,))
        if cur.fetchone() is None:
            raise PantryError("Only active staff can review volunteer requests.")
        cur.execute("""
            UPDATE volunteer_shift
            SET status = %s, reviewed_by_staff = %s, reviewed_at = now()
            WHERE shift_id = %s AND volunteer_unikey = %s
            RETURNING shift_id""", (decision, staff_unikey, shift_id, volunteer_unikey))
        if cur.fetchone() is None:
            raise PantryError(f"No volunteer request found for {volunteer_unikey} on shift {shift_id}.")
        return decision
    return _run(conn, work)


# ---------------------------------------------------------------- staff assignments

def assign_staff_shift(conn, assigner_staff_unikey, shift_id, target_staff_unikey, role):
    """Assign a staff member to a shift as MAIN_SUPERVISOR or ASSISTANT."""
    role = role.upper()
    if role not in ("MAIN_SUPERVISOR", "ASSISTANT"):
        raise PantryError("Duty role must be MAIN_SUPERVISOR or ASSISTANT.")
    def work(cur):
        cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active", (assigner_staff_unikey,))
        if cur.fetchone() is None:
            raise PantryError("Only active staff can assign staff to shifts.")
        cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active", (target_staff_unikey,))
        if cur.fetchone() is None:
            raise PantryError(f"{target_staff_unikey} is not an active staff member.")
        cur.execute("SELECT shift_date, start_time, end_time FROM pantry_shift WHERE shift_id = %s", (shift_id,))
        if cur.fetchone() is None:
            raise PantryError(f"Shift {shift_id} does not exist.")
        cur.execute("""
            INSERT INTO shift_staff_assignment (shift_id, staff_unikey, assignment_role)
            VALUES (%s, %s, %s)
            ON CONFLICT (shift_id, staff_unikey)
            DO UPDATE SET assignment_role = EXCLUDED.assignment_role""",
            (shift_id, target_staff_unikey, role))
    return _run(conn, work)


# ---------------------------------------------------------------- stock

def record_stock_count(conn, staff_unikey, stock_number, count_type, qty, shift_id=None, notes=None):
    if qty < 0:
        raise PantryError("A counted quantity cannot be negative.")
    count_type = count_type.upper()
    if count_type not in ('OPENING', 'CLOSING', 'SPOT_CHECK'):
        raise PantryError("Count type must be OPENING, CLOSING or SPOT_CHECK.")
    def work(cur):
        cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active", (staff_unikey,))
        if cur.fetchone() is None:
            raise PantryError("Only active staff can record stock counts.")
        cur.execute("SELECT 1 FROM stock_batch WHERE stock_number = %s", (stock_number,))
        if cur.fetchone() is None:
            raise PantryError(f"Stock number {stock_number} does not exist.")
        if shift_id is not None:
            cur.execute("SELECT 1 FROM pantry_shift WHERE shift_id = %s", (shift_id,))
            if cur.fetchone() is None:
                raise PantryError(f"Shift {shift_id} does not exist.")
        cur.execute("""
            INSERT INTO stock_count (stock_number, shift_id, counted_by_staff,
                                     count_type, counted_qty, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING stock_count_id""",
            (stock_number, shift_id, staff_unikey, count_type, qty, notes))
        cid = cur.fetchone()[0]

        # Reconcile with shift_stock_count if shift_id provided
        if shift_id is not None:
            if count_type == 'OPENING':
                cur.execute("""
                    INSERT INTO shift_stock_count (shift_id, stock_number, opening_qty)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (shift_id, stock_number)
                    DO UPDATE SET opening_qty = EXCLUDED.opening_qty""",
                    (shift_id, stock_number, qty))
            elif count_type == 'CLOSING':
                cur.execute("""
                    INSERT INTO shift_stock_count (shift_id, stock_number, opening_qty, closing_qty)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (shift_id, stock_number)
                    DO UPDATE SET closing_qty = EXCLUDED.closing_qty""",
                    (shift_id, stock_number, qty, qty))
        return cid
    return _run(conn, work)


def record_stock_adjustment(conn, staff_unikey, shift_id, stock_number, adjustment_kind, qty, reason):
    """Record an intra-shift stock adjustment (RECEIPT or WASTE)."""
    if qty <= 0:
        raise PantryError("Adjustment quantity must be positive.")
    adjustment_kind = adjustment_kind.upper()
    if adjustment_kind not in ('RECEIPT', 'WASTE'):
        raise PantryError("Adjustment kind must be RECEIPT or WASTE.")
    if not reason or not reason.strip():
        raise PantryError("Adjustment reason cannot be blank.")
    def work(cur):
        cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active", (staff_unikey,))
        if cur.fetchone() is None:
            raise PantryError("Only active staff can record stock adjustments.")
        cur.execute("SELECT 1 FROM pantry_shift WHERE shift_id = %s", (shift_id,))
        if cur.fetchone() is None:
            raise PantryError(f"Shift {shift_id} does not exist.")
        cur.execute("SELECT 1 FROM stock_batch WHERE stock_number = %s", (stock_number,))
        if cur.fetchone() is None:
            raise PantryError(f"Stock number {stock_number} does not exist.")

        # Ensure shift_stock_count entry exists to satisfy FK constraint
        cur.execute("SELECT opening_qty FROM shift_stock_count WHERE shift_id = %s AND stock_number = %s",
                    (shift_id, stock_number))
        if cur.fetchone() is None:
            cur.execute("""
                INSERT INTO shift_stock_count (shift_id, stock_number, opening_qty)
                VALUES (%s, %s, 0)
                ON CONFLICT (shift_id, stock_number) DO NOTHING""",
                (shift_id, stock_number))

        cur.execute("""
            INSERT INTO stock_adjustment (shift_id, stock_number, adjustment_kind, quantity, reason)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (shift_id, stock_number, adjustment_kind)
            DO UPDATE SET quantity = stock_adjustment.quantity + EXCLUDED.quantity,
                          reason = EXCLUDED.reason""",
            (shift_id, stock_number, adjustment_kind, qty, reason))
    return _run(conn, work)


# ---------------------------------------------------------------- reports

def report_day_summary(conn, on_date):
    return _query(conn, """
        SELECT session_id, start_time, active_bookings, attended, absent,
               awaiting_checkin, spaces_remaining
        FROM v_booking_attendance
        WHERE session_date = %s::date
        ORDER BY start_time""", (on_date,))


def report_near_capacity(conn):
    return _query(conn, """
        SELECT session_date, start_time, active_bookings, capacity
        FROM v_booking_attendance
        WHERE active_bookings >= CEIL(capacity * %s)
        ORDER BY session_date, start_time""", (NEAR_CAPACITY,))


def report_low_stock(conn):
    return _query(conn, """
        SELECT p.product_name, COALESCE(SUM(l.last_counted_qty), 0) AS on_hand,
               p.low_stock_threshold, p.counting_unit
        FROM product p
        LEFT JOIN v_latest_stock_count l ON l.product_id = p.product_id
        GROUP BY p.product_id, p.product_name, p.low_stock_threshold, p.counting_unit
        HAVING COALESCE(SUM(l.last_counted_qty), 0) < p.low_stock_threshold
        ORDER BY on_hand""")


def latest_stock(conn):
    return _query(conn, """
        SELECT stock_number, product_name, last_counted_qty, counting_unit, count_type
        FROM v_latest_stock_count
        ORDER BY product_name, stock_number""")


def my_shifts(conn, staff_unikey):
    """List shifts assigned to a specific staff member."""
    return _query(conn, """
        SELECT sh.shift_id, sh.shift_date, sh.start_time, sh.end_time, a.assignment_role, sh.status
        FROM pantry_shift sh
        JOIN shift_staff_assignment a ON a.shift_id = sh.shift_id
        WHERE a.staff_unikey = %s
        ORDER BY sh.shift_date DESC, sh.start_time""", (staff_unikey,))


def session_bookings(conn, session_id):
    """List bookings and attendance for a specific session."""
    return _query(conn, """
        SELECT b.booking_id, b.student_unikey, p.full_name, b.status, b.qr_token, b.attendance_at, b.admin_override
        FROM booking b
        JOIN person p ON p.unikey = b.student_unikey
        WHERE b.session_id = %s
        ORDER BY b.booking_id""", (session_id,))


def shift_roster(conn, on_date):
    """View full staffing and approved volunteer roster for shifts on a given date."""
    staff_rows = _query(conn, """
        SELECT sh.shift_id, sh.start_time, sh.end_time, 'Staff' AS person_role,
               a.assignment_role AS duty, pe.full_name, pe.unikey
        FROM pantry_shift sh
        JOIN shift_staff_assignment a ON a.shift_id = sh.shift_id
        JOIN person pe ON pe.unikey = a.staff_unikey
        WHERE sh.shift_date = %s::date
        ORDER BY sh.start_time, a.assignment_role""", (on_date,))
    vol_rows = _query(conn, """
        SELECT sh.shift_id, sh.start_time, sh.end_time, 'Volunteer' AS person_role,
               'VOLUNTEER (APPROVED)' AS duty, pe.full_name, pe.unikey
        FROM pantry_shift sh
        JOIN volunteer_shift vs ON vs.shift_id = sh.shift_id
        JOIN person pe ON pe.unikey = vs.volunteer_unikey
        WHERE sh.shift_date = %s::date AND vs.status = 'APPROVED'
        ORDER BY sh.start_time, pe.full_name""", (on_date,))
    return staff_rows + vol_rows


