"""Command-line prototype for Campus Pantry.

Run:  python cli.py
"""
import datetime
import sys

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import services as svc
from db import get_connection
from services import PantryError


def ask(prompt):
    return input(f"{prompt}: ").strip()


def ask_date(prompt="Date (YYYY-MM-DD, blank = today)"):
    text = ask(prompt)
    if not text:
        return datetime.date.today().isoformat()
    datetime.date.fromisoformat(text)          # raises ValueError on a bad date
    return text


def table(headers, rows):
    if not rows:
        print("  (nothing to show)")
        return
    cells = [[("" if v is None else str(v)) for v in row] for row in rows]
    widths = [max(len(h), *(len(r[i]) for r in cells)) for i, h in enumerate(headers)]
    print("  " + "  ".join(h.ljust(w) for h, w in zip(headers, widths)))
    print("  " + "  ".join("-" * w for w in widths))
    for r in cells:
        print("  " + "  ".join(v.ljust(w) for v, w in zip(r, widths)))


def menu(title, options):
    """options: list of (label, function). Returns when the user picks 0."""
    while True:
        print(f"\n== {title} ==")
        for i, (label, _) in enumerate(options, 1):
            print(f"  {i}. {label}")
        print("  0. Back")
        choice = ask("Choose")
        if choice == "0":
            return
        if not choice.isdigit() or not 1 <= int(choice) <= len(options):
            print("  Please enter one of the numbers above.")
            continue
        try:
            options[int(choice) - 1][1]()
        except PantryError as exc:
            print(f"  ✗ {exc}")
        except ValueError as exc:
            print(f"  ✗ Invalid input: {exc}")


# ---------------------------------------------------------------- student

def student_menu(conn, unikey):
    def show_sessions():
        on = ask_date()
        table(["Session", "Start", "End", "Booked", "Capacity", "Spaces left"],
              svc.list_sessions(conn, on))

    def book():
        session_id = int(ask("Session number"))
        booking_id, token = svc.book_session(conn, unikey, session_id)
        print(f"  ✓ Booking {booking_id} confirmed. Your QR code token: {token}")

    def mine():
        table(["Booking", "Date", "Start", "Status", "QR token"], svc.my_bookings(conn, unikey))

    def cancel():
        svc.cancel_booking(conn, unikey, int(ask("Booking number to cancel")))
        print("  ✓ Booking cancelled; the place is free again.")

    menu(f"Student {unikey}", [
        ("View sessions and spaces", show_sessions),
        ("Book a session", book),
        ("My bookings", mine),
        ("Cancel a booking", cancel),
    ])


# ---------------------------------------------------------------- volunteer

def volunteer_menu(conn, unikey, is_student=False):
    def show_shifts():
        table(["Shift ID", "Date", "Start", "End", "Status", "Approved Volunteers"],
              svc.list_upcoming_shifts(conn))

    def request_shift():
        shift_id = int(ask("Shift ID to request"))
        svc.request_volunteer_shift(conn, unikey, shift_id)
        print(f"  ✓ Request submitted for shift {shift_id}. Status: PENDING staff approval.")

    def my_shifts():
        table(["Shift ID", "Date", "Start", "End", "Status", "Requested At", "Reviewed At"],
              svc.my_volunteer_shifts(conn, unikey))

    def withdraw():
        shift_id = int(ask("Shift ID of pending request to withdraw"))
        svc.withdraw_volunteer_request(conn, unikey, shift_id)
        print(f"  ✓ Pending request for shift {shift_id} has been withdrawn.")

    options = [
        ("View scheduled shifts", show_shifts),
        ("Request to join a shift", request_shift),
        ("View my shift requests & status", my_shifts),
        ("Withdraw a pending shift request", withdraw),
    ]
    if is_student:
        options.append(("Go to Student Bookings Portal", lambda: student_menu(conn, unikey)))

    menu(f"Volunteer {unikey}", options)


# ---------------------------------------------------------------- staff

def staff_menu(conn, unikey):
    def scan():
        token = ask("Scan / enter QR token")
        if not token:
            print("  ✗ QR token cannot be blank.")
            return
        booking_id, student = svc.check_in(conn, token)
        print(f"  ✓ Checked in booking {booking_id} for {student}.")

    def special_booking():
        student = ask("Student UniKey").lower()
        if not svc.valid_unikey(student):
            print("  ✗ Invalid UniKey format. Expected 4 letters followed by 4 digits.")
            return
        session_id = int(ask("Session number"))
        reason = ask("Reason for the exception")
        if not reason.strip():
            print("  ✗ A reason must be provided for an administrative override.")
            return
        booking_id, token = svc.book_session(conn, student, session_id,
                                             override_by_staff=unikey, reason=reason)
        print(f"  ✓ Special booking {booking_id} created. QR token: {token}")

    def no_shows():
        count = svc.mark_no_shows(conn)
        print(f"  ✓ {count} past uninspected confirmed booking(s) marked ABSENT.")

    def setup_day():
        on = ask_date("Date to set up (YYYY-MM-DD)")
        count = svc.set_up_day(conn, on)
        print(f"  ✓ Created 3 shifts and {count} sessions for {on}.")

    def day_summary():
        table(["Session", "Start", "Active", "Attended", "Absent", "Waiting", "Spaces"],
              svc.report_day_summary(conn, ask_date()))

    def near_capacity():
        table(["Date", "Start", "Booked", "Capacity"], svc.report_near_capacity(conn))

    def stock():
        table(["Stock no.", "Product", "Last count", "Unit", "Type"], svc.latest_stock(conn))

    def count():
        stock_number = ask("Stock number (e.g. STK-000001)")
        count_type = ask("Count type (OPENING / CLOSING / SPOT_CHECK)").upper()
        qty = int(ask("Counted quantity"))
        shift = ask("Shift number (blank if none)")
        count_id = svc.record_stock_count(conn, unikey, stock_number, count_type, qty,
                                          int(shift) if shift else None, ask("Notes") or None)
        print(f"  ✓ Stock count {count_id} recorded.")

    def low_stock():
        table(["Product", "On hand", "Threshold", "Unit"], svc.report_low_stock(conn))

    def view_my_shifts():
        table(["Shift ID", "Date", "Start", "End", "Role", "Status"],
              svc.my_shifts(conn, unikey))

    def view_session_bookings():
        session_id = int(ask("Session ID"))
        table(["Booking ID", "UniKey", "Name", "Status", "QR Token", "Attendance At", "Override"],
              svc.session_bookings(conn, session_id))

    def view_roster():
        on = ask_date("Date for roster (YYYY-MM-DD)")
        table(["Shift ID", "Start", "End", "Role Type", "Duty", "Name", "UniKey"],
              svc.shift_roster(conn, on))

    def manage_volunteer_requests():
        on = ask("Filter date (YYYY-MM-DD, blank = all)")
        st_filter = ask("Status filter (PENDING / APPROVED / REJECTED, blank = PENDING)").upper() or "PENDING"
        rows = svc.list_volunteer_requests(conn, on_date=on if on else None, status_filter=st_filter)
        table(["Shift ID", "Date", "Start", "End", "UniKey", "Name", "Status", "Requested At"], rows)
        if not rows:
            return
        action = ask("Review a request? (1: Approve, 2: Reject, 0: Skip)")
        if action in ("1", "2"):
            vol_unikey = ask("Volunteer UniKey").lower()
            shift_id = int(ask("Shift ID"))
            decision = "APPROVED" if action == "1" else "REJECTED"
            svc.review_volunteer_request(conn, unikey, shift_id, vol_unikey, decision)
            print(f"  ✓ Volunteer request for {vol_unikey} on shift {shift_id} marked {decision}.")

    def assign_staff():
        shift_id = int(ask("Shift ID"))
        target_staff = ask("Staff UniKey to assign").lower()
        role = ask("Role (1: MAIN_SUPERVISOR, 2: ASSISTANT)")
        assignment_role = "MAIN_SUPERVISOR" if role == "1" else "ASSISTANT"
        svc.assign_staff_shift(conn, unikey, shift_id, target_staff, assignment_role)
        print(f"  ✓ Assigned {target_staff} as {assignment_role} to shift {shift_id}.")

    def adjust_stock():
        shift_id = int(ask("Shift ID"))
        stock_number = ask("Stock number (e.g. STK-000001)")
        kind = ask("Adjustment kind (RECEIPT / WASTE)").upper()
        qty = int(ask("Quantity"))
        reason = ask("Reason for adjustment")
        svc.record_stock_adjustment(conn, unikey, shift_id, stock_number, kind, qty, reason)
        print(f"  ✓ Recorded {kind} adjustment of {qty} for {stock_number} in shift {shift_id}.")

    menu(f"Staff {unikey}", [
        ("Front desk: check in a QR code", scan),
        ("Front desk: view bookings for a session", view_session_bookings),
        ("Special booking (admin override)", special_booking),
        ("Mark no-shows after closing", no_shows),
        ("View my assigned shifts", view_my_shifts),
        ("View shift staffing & confirmed volunteer roster", view_roster),
        ("Manage volunteer shift requests (Approve / Reject)", manage_volunteer_requests),
        ("Assign staff member to a shift", assign_staff),
        ("Set up a day's shifts and sessions", setup_day),
        ("Report: day attendance summary", day_summary),
        ("Report: sessions near capacity", near_capacity),
        ("Stock: latest counts", stock),
        ("Stock: record a count", count),
        ("Stock: record receipt/waste adjustment", adjust_stock),
        ("Report: low stock", low_stock),
    ])


# ---------------------------------------------------------------- start

def main():
    conn = get_connection()
    print("Campus Pantry — FoodHub booking and inventory prototype")
    try:
        while True:
            unikey = ask("\nUniKey (blank to quit)").lower()
            if not unikey:
                break
            if not svc.valid_unikey(unikey):
                print("  ✗ A UniKey is 4 letters followed by 4 digits, e.g. abcd0123.")
                continue
            person = svc.find_person(conn, unikey)
            if person is None:
                print("  ✗ Unknown UniKey.")
                continue
            name, is_student, is_volunteer, is_staff = person
            roles = []
            if is_student:
                roles.append("Student")
            if is_volunteer:
                roles.append("Volunteer")
            if is_staff:
                roles.append("Staff")

            print(f"  Hello, {name} (Roles: {', '.join(roles)}).")

            # Multi-role navigation portal
            while True:
                portal_options = []
                if is_student:
                    portal_options.append(("Student Portal", lambda: student_menu(conn, unikey)))
                if is_volunteer:
                    portal_options.append(("Volunteer Portal", lambda: volunteer_menu(conn, unikey, is_student=is_student)))
                if is_staff:
                    portal_options.append(("Staff Portal", lambda: staff_menu(conn, unikey)))

                if not portal_options:
                    print("  This UniKey has no active system roles assigned.")
                    break
                elif len(portal_options) == 1:
                    portal_options[0][1]()
                    break
                else:
                    print(f"\n== Role Portals for {name} ==")
                    for idx, (label, _) in enumerate(portal_options, 1):
                        print(f"  {idx}. {label}")
                    print("  0. Log out")
                    choice = ask("Select portal")
                    if choice == "0" or not choice:
                        break
                    if choice.isdigit() and 1 <= int(choice) <= len(portal_options):
                        portal_options[int(choice) - 1][1]()
                    else:
                        print("  Please enter one of the numbers above.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()

