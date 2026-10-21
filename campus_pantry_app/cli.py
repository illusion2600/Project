"""Command-line prototype for Campus Pantry.

Run:  python cli.py
"""
import datetime

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


# ---------------------------------------------------------------- staff

def staff_menu(conn, unikey):
    def scan():
        booking_id, student = svc.check_in(conn, ask("Scan / enter QR token"))
        print(f"  ✓ Checked in booking {booking_id} for {student}.")

    def special_booking():
        student = ask("Student UniKey").lower()
        session_id = int(ask("Session number"))
        reason = ask("Reason for the exception")
        booking_id, token = svc.book_session(conn, student, session_id,
                                             override_by_staff=unikey, reason=reason)
        print(f"  ✓ Special booking {booking_id} created. QR token: {token}")

    def no_shows():
        print(f"  ✓ {svc.mark_no_shows(conn)} booking(s) marked ABSENT.")

    def setup_day():
        on = ask_date("Date to set up (YYYY-MM-DD)")
        print(f"  ✓ Created 3 shifts and {svc.set_up_day(conn, on)} sessions for {on}.")

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

    menu(f"Staff {unikey}", [
        ("Front desk: check in a QR code", scan),
        ("Special booking (admin override)", special_booking),
        ("Mark no-shows after closing", no_shows),
        ("Set up a day's shifts and sessions", setup_day),
        ("Report: day attendance summary", day_summary),
        ("Report: sessions near capacity", near_capacity),
        ("Stock: latest counts", stock),
        ("Stock: record a count", count),
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
            name, is_student, _is_volunteer, is_staff = person
            print(f"  Hello, {name}.")
            if is_staff:
                staff_menu(conn, unikey)
            elif is_student:
                student_menu(conn, unikey)
            else:
                print("  This prototype has menus for students and staff only.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
