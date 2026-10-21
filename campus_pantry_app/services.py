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
      2. check the session exists and has not already finished;
      3. insert the booking with a fresh random token; the booking trigger then locks
         the session row and enforces capacity and the daily limit.
    """
    def work(cur):
        cur.execute("SELECT unikey FROM student WHERE unikey = %s FOR UPDATE", (unikey,))
        if cur.fetchone() is None:
            raise PantryError(f"{unikey} is not a registered student.")
        cur.execute("""
            SELECT (session_date + end_time) < localtimestamp
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
             override_by_staff, reason))
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
    """Front-desk scan: CONFIRMED -> ATTENDED. A second scan changes nothing."""
    def work(cur):
        cur.execute("""
            UPDATE booking SET status = 'ATTENDED', attendance_at = now()
            WHERE qr_token = %s AND status = 'CONFIRMED'
            RETURNING booking_id, student_unikey""", (qr_token,))
        row = cur.fetchone()
        if row:
            return row
        cur.execute("SELECT status FROM booking WHERE qr_token = %s", (qr_token,))
        found = cur.fetchone()
        if found is None:
            raise PantryError("Unknown QR code.")
        raise PantryError(f"Cannot check in: this booking is {found[0]}.")
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


# ---------------------------------------------------------------- stock

def record_stock_count(conn, staff_unikey, stock_number, count_type, qty, shift_id=None, notes=None):
    def work(cur):
        cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active", (staff_unikey,))
        if cur.fetchone() is None:
            raise PantryError("Only active staff can record stock counts.")
        cur.execute("""
            INSERT INTO stock_count (stock_number, shift_id, counted_by_staff,
                                     count_type, counted_qty, notes)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING stock_count_id""",
            (stock_number, shift_id, staff_unikey, count_type, qty, notes))
        return cur.fetchone()[0]
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
        GROUP BY p.product_id
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
    """View full staffing and volunteer roster for shifts on a given date."""
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
               'VOLUNTEER' AS duty, pe.full_name, pe.unikey
        FROM pantry_shift sh
        JOIN volunteer_shift vs ON vs.shift_id = sh.shift_id
        JOIN person pe ON pe.unikey = vs.volunteer_unikey
        WHERE sh.shift_date = %s::date
        ORDER BY sh.start_time, pe.full_name""", (on_date,))
    return staff_rows + vol_rows


def record_stock_adjustment(conn, staff_unikey, shift_id, stock_number, adjustment_kind, qty, reason):
    """Record an intra-shift stock adjustment (RECEIPT or WASTE)."""
    def work(cur):
        cur.execute("SELECT 1 FROM staff WHERE unikey = %s AND is_active", (staff_unikey,))
        if cur.fetchone() is None:
            raise PantryError("Only active staff can record stock adjustments.")
        cur.execute("""
            INSERT INTO stock_adjustment (shift_id, stock_number, adjustment_kind, quantity, reason)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (shift_id, stock_number, adjustment_kind)
            DO UPDATE SET quantity = stock_adjustment.quantity + EXCLUDED.quantity,
                          reason = EXCLUDED.reason""",
            (shift_id, stock_number, adjustment_kind, qty, reason))
    return _run(conn, work)

