"""A repeatable, after-hours showcase in an owned disposable database.

Uses the same service methods as the CLI. The business clock alone is simulated.
The normal CLI never reads this simulated clock or the TEST_PG settings.
"""
from datetime import date, datetime, time
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "campus_pantry_app"))
sys.path.insert(0, str(ROOT / "tests"))

import services
from support import disposable_database


def main():
    print("CAMPUS PANTRY | Group 94 | Final showcase")
    print("Synthetic data; simulated 10 October 2026, 10:15 Sydney time.")
    print("Creates and removes its own test database. Existing app data is untouched.\n")
    sandbox = None
    try:
        with disposable_database("SHOWCASE") as sandbox:
            conn = sandbox.connect()
            sandbox.reset(conn)
            demo_day = date(2026, 10, 10)
            staff = "must2203"
            with patch.object(services, "_business_now", return_value=datetime.combine(demo_day, time(10, 15))):
                count = services.set_up_day(conn, demo_day, staff)
                assert count == 12
                print("1. Set up a new day: 3 shifts and 12 half-hour sessions.")
                with conn, conn.cursor() as cur:
                    cur.execute("SELECT shift_id FROM pantry_shift WHERE shift_date=%s ORDER BY start_time", (demo_day,))
                    shift_id = cur.fetchone()[0]
                    cur.execute("SELECT session_id FROM session WHERE shift_id=%s ORDER BY start_time", (shift_id,))
                    session_id = cur.fetchone()[0]
                services.assign_staff_shift(conn, staff, shift_id, staff, "MAIN_SUPERVISOR")
                services.assign_staff_shift(conn, staff, shift_id, "part2550", "ASSISTANT")
                services.set_shift_status(conn, staff, shift_id, "OPEN")
                print("2. Assign a supervisor and assistant; open the shift.")
                booking_id, token = services.book_session(conn, "alex1001", session_id)
                print(f"3. Student alex1001 books a place (booking {booking_id}); a token is generated.")
                try:
                    services.book_session(conn, "alex1001", session_id)
                except services.PantryError as exc:
                    if "one" not in str(exc).lower() and "already" not in str(exc).lower():
                        raise
                    print(f"   Duplicate attempt correctly rejected: {exc}")
                else:
                    raise AssertionError("The duplicate booking was incorrectly accepted")
                services.request_volunteer_shift(conn, "nikh3591", shift_id)
                services.review_volunteer_request(conn, staff, shift_id, "nikh3591", "APPROVED")
                print("4. Volunteer nikh3591 requests the shift; staff approves the pending request.")
                attended = services.check_in(conn, token, staff)
                assert attended == (booking_id, "alex1001")
                assert services.check_in(conn, token, staff) == attended
                print("5. Staff checks in the student; scanning again leaves one attendance record.")
                services.record_stock_count(conn, staff, "STK-000001", "OPENING", 100, shift_id)
                services.record_stock_adjustment(conn, staff, shift_id, "STK-000001", "RECEIPT", 10, "Demo receipt")
                services.record_stock_adjustment(conn, staff, shift_id, "STK-000001", "WASTE", 2, "Demo damaged packs")
                services.record_stock_count(conn, staff, "STK-000001", "CLOSING", 88, shift_id)
                services.set_shift_status(conn, staff, shift_id, "CLOSED")
                rows = services.report_shift_stock(conn, demo_day, staff)
                assert len(rows) == 1 and rows[0][1] == "CLOSED" and rows[0][-1] == 20
                print("6. Reconcile stock and close the shift:")
                print("   100 opening + 10 received - 2 waste - 88 closing = 20 estimated dispensed.")
                print("   Closed-shift stock and staffing are protected from later edits.")
                with conn, conn.cursor() as cur:
                    cur.execute("SELECT count(*), min(status) FROM booking WHERE booking_id=%s", (booking_id,))
                    assert cur.fetchone() == (1, "ATTENDED")
        assert sandbox.removed
        print("\nSHOWCASE PASSED. Disposable database removed successfully.")
        return 0
    except Exception as exc:
        print(f"SHOWCASE FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        if sandbox is not None:
            print(f"Disposable database removed: {sandbox.removed}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
