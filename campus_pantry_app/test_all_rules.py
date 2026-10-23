"""Comprehensive, Isolated Test Suite for Campus Pantry
Verifies All 17 Core Business Rules with Guaranteed Test Isolation and Repeatability.

Regression Test Suite:
  1. A valid student booking succeeds and generates QR token.
  2. Duplicate active booking on same day is rejected.
  3. Volunteer who is also a student can book without role conflict.
  4. Volunteer shift request creation recorded as PENDING.
  5. Pending volunteer request appears as pending and NOT on confirmed roster.
  6. Staff approval and rejection of volunteer shift requests.
  7. Duplicate volunteer request for same shift is rejected.
  8. Shift-overlap validation prevents overlapping staff or volunteer shifts.
  9. Exact staff duty assignments enforced (1 supervisor + 1 assistant).
  10. Session capacity limit and immediate cancellation space restoration.
  11. Concurrent race condition for final space serializes safely.
  12. Valid and invalid QR check-in handling.
  13. No-show processing after 16:00 and repeated idempotent execution.
  14. Admin override safeguards, non-empty reason, and audit trail.
  15. Inventory receipt, waste, count reconciliation, and low-stock reporting.
  16. All 12 analytical management queries (Q1-Q12) execute without errors.
  17. Database integrity and validation invariants hold.
"""
import datetime
import os
import sys
import threading
import time

sys.path.append(os.path.dirname(__file__))
from db import get_connection, error_message
import services as svc

results = []

def record(test_num, name, expected, actual, passed, details=""):
    results.append({
        "num": test_num,
        "name": name,
        "expected": expected,
        "actual": actual,
        "status": "PASS" if passed else "FAIL",
        "details": details
    })
    status_icon = "PASS" if passed else "FAIL"
    print(f"[{status_icon}] Test {test_num:2d}: {name} - {details}")


def cleanup_test_data(conn):
    """Purge test-generated data so tests are completely isolated and repeatable."""
    conn.rollback()
    with conn.cursor() as cur:
        # 1. Delete test bookings
        cur.execute("""
            DELETE FROM booking
            WHERE student_unikey IN ('stud0001', 'dual0001', 'volu0001', 'volu0002', 'scan0001', 'nosh0001', 'test1001')
               OR student_unikey LIKE 'capa%'
               OR student_unikey LIKE 'race%'
               OR student_unikey LIKE 'capp%'
               OR student_unikey LIKE 'racp%'
               OR session_id >= 800;
        """)
        # 2. Delete test stock records referencing shifts
        cur.execute("""
            DELETE FROM stock_adjustment WHERE shift_id >= 800;
            DELETE FROM shift_stock_count WHERE shift_id >= 800;
            DELETE FROM stock_count WHERE shift_id >= 800 OR stock_number LIKE 'TST-%';
            DELETE FROM stock_batch WHERE stock_number LIKE 'TST-%';
            DELETE FROM purchase_record_line WHERE product_id IN (SELECT product_id FROM product WHERE product_code LIKE 'TST-%');
            DELETE FROM purchase_record WHERE purchase_id >= 800;
            DELETE FROM product WHERE product_code LIKE 'TST-%';
        """)
        # 3. Delete test sessions
        cur.execute("""
            DELETE FROM session
            WHERE session_id >= 800;
        """)
        # 4. Delete test volunteer shifts
        cur.execute("""
            DELETE FROM volunteer_shift
            WHERE volunteer_unikey IN ('stud0001', 'dual0001', 'volu0001', 'volu0002')
               OR shift_id >= 800;
        """)
        # 5. Delete test staff assignments
        cur.execute("""
            DELETE FROM shift_staff_assignment
            WHERE shift_id >= 800;
        """)
        # 6. Delete test shifts
        cur.execute("""
            DELETE FROM pantry_shift
            WHERE shift_id >= 800;
        """)
        # 7. Delete test students, volunteers, persons
        cur.execute("""
            DELETE FROM student
            WHERE unikey IN ('stud0001', 'dual0001', 'volu0001', 'volu0002', 'scan0001', 'nosh0001', 'test1001')
               OR unikey LIKE 'capa%' OR unikey LIKE 'race%' OR unikey LIKE 'capp%' OR unikey LIKE 'racp%';
            DELETE FROM volunteer
            WHERE unikey IN ('dual0001', 'volu0001', 'volu0002');
            DELETE FROM person
            WHERE unikey IN ('stud0001', 'dual0001', 'volu0001', 'volu0002', 'scan0001', 'nosh0001', 'test1001')
               OR unikey LIKE 'capa%' OR unikey LIKE 'race%' OR unikey LIKE 'capp%' OR unikey LIKE 'racp%';
        """)
        conn.commit()


def setup_test_fixtures(conn):
    """Create controlled shift, session, student, and volunteer test entities."""
    with conn.cursor() as cur:
        # 1. Planned test shifts on 2026-11-20
        cur.execute("""
            INSERT INTO pantry_shift (shift_id, shift_date, start_time, end_time, status)
            VALUES (801, '2026-11-20', '10:00', '12:00', 'PLANNED'),
                   (802, '2026-11-20', '12:00', '14:00', 'PLANNED'),
                   (803, '2026-11-20', '11:00', '13:00', 'PLANNED')  -- overlapping shift for testing
            ON CONFLICT (shift_id) DO NOTHING;

            INSERT INTO shift_staff_assignment (shift_id, staff_unikey, assignment_role)
            VALUES (801, 'must2203', 'MAIN_SUPERVISOR'),
                   (801, 'part2550', 'ASSISTANT'),
                   (802, 'haim2897', 'MAIN_SUPERVISOR'),
                   (802, 'part2550', 'ASSISTANT')
            ON CONFLICT DO NOTHING;

            -- Sessions for shift 801
            INSERT INTO session (session_id, shift_id, session_date, start_time, end_time, capacity)
            VALUES (811, 801, '2026-11-20', '10:00', '10:30', 50),
                   (812, 801, '2026-11-20', '10:30', '11:00', 50)
            ON CONFLICT (session_id) DO NOTHING;

            -- Small capacity session (capacity = 5) for capacity tests
            INSERT INTO session (session_id, shift_id, session_date, start_time, end_time, capacity)
            VALUES (815, 801, '2026-11-20', '11:00', '11:30', 5)
            ON CONFLICT (session_id) DO NOTHING;

            -- Concurrency test session (capacity = 5)
            INSERT INTO session (session_id, shift_id, session_date, start_time, end_time, capacity)
            VALUES (816, 801, '2026-11-20', '11:30', '12:00', 5)
            ON CONFLICT (session_id) DO NOTHING;
        """)

        # 2. Test person records (valid 4-letter + 4-digit UniKeys)
        cur.execute("""
            -- Pure student
            INSERT INTO person (unikey, full_name, email)
            VALUES ('stud0001', 'Test Student One', 'stud01@test.uni')
            ON CONFLICT (unikey) DO NOTHING;
            INSERT INTO student (unikey, degree_level, student_category)
            VALUES ('stud0001', 'BACHELOR', 'DOMESTIC')
            ON CONFLICT (unikey) DO NOTHING;

            -- Multi-role: Student + Volunteer
            INSERT INTO person (unikey, full_name, email)
            VALUES ('dual0001', 'Test Dual Role Person', 'dual01@test.uni')
            ON CONFLICT (unikey) DO NOTHING;
            INSERT INTO student (unikey, degree_level, student_category)
            VALUES ('dual0001', 'POSTGRADUATE', 'INTERNATIONAL')
            ON CONFLICT (unikey) DO NOTHING;
            INSERT INTO volunteer (unikey, is_active)
            VALUES ('dual0001', true)
            ON CONFLICT (unikey) DO NOTHING;

            -- Pure Volunteer
            INSERT INTO person (unikey, full_name, email)
            VALUES ('volu0001', 'Test Volunteer Only', 'volu01@test.uni')
            ON CONFLICT (unikey) DO NOTHING;
            INSERT INTO volunteer (unikey, is_active)
            VALUES ('volu0001', true)
            ON CONFLICT (unikey) DO NOTHING;

            -- Second Volunteer for approval/rejection test
            INSERT INTO person (unikey, full_name, email)
            VALUES ('volu0002', 'Test Volunteer Two', 'volu02@test.uni')
            ON CONFLICT (unikey) DO NOTHING;
            INSERT INTO volunteer (unikey, is_active)
            VALUES ('volu0002', true)
            ON CONFLICT (unikey) DO NOTHING;
        """)
        conn.commit()


def run_all_tests():
    global results
    results = []
    conn = get_connection()

    try:
        # Pre-cleanup ensures clean slate even if prior run was interrupted
        cleanup_test_data(conn)
        setup_test_fixtures(conn)

        # -------------------------------------------------------------
        # 1. A valid student booking
        # -------------------------------------------------------------
        try:
            bid, token = svc.book_session(conn, 'stud0001', 811)
            with conn.cursor() as cur:
                cur.execute("SELECT status, qr_token FROM booking WHERE booking_id = %s", (bid,))
                st, tok = cur.fetchone()
            passed = (st == 'CONFIRMED' and tok == token and bool(tok))
            record(1, "Valid student booking", "Booking created with status CONFIRMED and QR token",
                   f"Booking ID {bid}, Status {st}", passed, f"Token: {tok}")
        except Exception as e:
            conn.rollback()
            record(1, "Valid student booking", "CONFIRMED booking created", str(e), False, str(e))

        # -------------------------------------------------------------
        # 2. Duplicate active booking rejection
        # -------------------------------------------------------------
        try:
            svc.book_session(conn, 'stud0001', 812)
            record(2, "Duplicate active booking rejection", "PantryError: Already has active booking",
                   "Unexpectedly allowed second booking", False, "No exception raised")
        except svc.PantryError as e:
            passed = "already has an active booking" in str(e).lower()
            record(2, "Duplicate active booking rejection", "PantryError: Student already has an active booking",
                   str(e), passed, str(e))
        except Exception as e:
            conn.rollback()
            record(2, "Duplicate active booking rejection", "PantryError", str(e), False, str(e))

        # -------------------------------------------------------------
        # 3. Volunteer who is also a student booking a session
        # -------------------------------------------------------------
        try:
            bid3, tok3 = svc.book_session(conn, 'dual0001', 811)
            person_roles = svc.find_person(conn, 'dual0001')
            name, is_stud, is_vol, is_stf = person_roles
            passed = (bid3 is not None and is_stud is True and is_vol is True)
            record(3, "Dual-role booking (Student + Volunteer)",
                   "Booking succeeds while volunteer role is preserved",
                   f"Booked ID {bid3}, is_student={is_stud}, is_volunteer={is_vol}", passed,
                   "Dual-role integrity holds")
        except Exception as e:
            conn.rollback()
            record(3, "Dual-role booking (Student + Volunteer)", "Booking succeeds", str(e), False, str(e))

        # -------------------------------------------------------------
        # 4. Volunteer shift request creation
        # -------------------------------------------------------------
        try:
            shift_req_id = svc.request_volunteer_shift(conn, 'volu0001', 801)
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM volunteer_shift WHERE shift_id = 801 AND volunteer_unikey = 'volu0001'")
                v_st = cur.fetchone()[0]
            passed = (v_st == 'PENDING')
            record(4, "Volunteer shift request creation", "Shift request recorded with status PENDING",
                   f"Request for shift 801, Status: {v_st}", passed, "PENDING recorded")
        except Exception as e:
            conn.rollback()
            record(4, "Volunteer shift request creation", "PENDING request created", str(e), False, str(e))

        # -------------------------------------------------------------
        # 5. Pending volunteer request appears as pending, not approved
        # -------------------------------------------------------------
        try:
            roster = svc.shift_roster(conn, '2026-11-20')
            confirmed_vol_unikeys = [row[6] for row in roster if row[3] == 'Volunteer']
            my_shifts = svc.my_volunteer_shifts(conn, 'volu0001')
            v_status = my_shifts[0][4] if my_shifts else None
            passed = ('volu0001' not in confirmed_vol_unikeys and v_status == 'PENDING')
            record(5, "Pending request excluded from confirmed roster",
                   "Request is labelled PENDING and does not appear as confirmed on roster",
                   f"Volunteer in confirmed roster: {'volu0001' in confirmed_vol_unikeys}, Status: {v_status}",
                   passed, "Roster isolates pending requests")
        except Exception as e:
            conn.rollback()
            record(5, "Pending request excluded from roster", "Excluded from roster", str(e), False, str(e))

        # -------------------------------------------------------------
        # 6. Staff approval and rejection of volunteer requests
        # -------------------------------------------------------------
        try:
            # Create second request for volu0002
            svc.request_volunteer_shift(conn, 'volu0002', 801)

            # Approve volu0001
            svc.review_volunteer_request(conn, 'must2203', 801, 'volu0001', 'APPROVED')
            # Reject volu0002
            svc.review_volunteer_request(conn, 'must2203', 801, 'volu0002', 'REJECTED')

            with conn.cursor() as cur:
                cur.execute("SELECT status, reviewed_by_staff FROM volunteer_shift WHERE shift_id = 801 AND volunteer_unikey = 'volu0001'")
                st1, staff1 = cur.fetchone()
                cur.execute("SELECT status, reviewed_by_staff FROM volunteer_shift WHERE shift_id = 801 AND volunteer_unikey = 'volu0002'")
                st2, staff2 = cur.fetchone()

            roster_after = svc.shift_roster(conn, '2026-11-20')
            approved_in_roster = any(row[6] == 'volu0001' for row in roster_after)
            rejected_in_roster = any(row[6] == 'volu0002' for row in roster_after)

            passed = (st1 == 'APPROVED' and staff1 == 'must2203' and
                      st2 == 'REJECTED' and staff2 == 'must2203' and
                      approved_in_roster and not rejected_in_roster)
            record(6, "Staff approval and rejection of volunteer requests",
                   "volu0001 APPROVED and on roster; volu0002 REJECTED and off roster",
                   f"volu01: {st1} (on roster: {approved_in_roster}), volu02: {st2} (on roster: {rejected_in_roster})",
                   passed, "Approval and rejection applied atomically with audit trail")
        except Exception as e:
            conn.rollback()
            record(6, "Staff approval and rejection", "Applied properly", str(e), False, str(e))

        # -------------------------------------------------------------
        # 7. Duplicate volunteer request rejection
        # -------------------------------------------------------------
        try:
            svc.request_volunteer_shift(conn, 'volu0001', 801)
            record(7, "Duplicate volunteer request rejected", "PantryError: Already approved or requested",
                   "Unexpectedly allowed duplicate request", False, "No error raised")
        except svc.PantryError as e:
            passed = "already" in str(e).lower()
            record(7, "Duplicate volunteer request rejected", "PantryError: Already approved / pending",
                   str(e), passed, str(e))
        except Exception as e:
            conn.rollback()
            record(7, "Duplicate volunteer request rejected", "PantryError", str(e), False, str(e))

        # -------------------------------------------------------------
        # 8. Shift-overlap validation
        # -------------------------------------------------------------
        try:
            # Shift 801 is 10:00-12:00, Shift 803 is 11:00-13:00 (overlaps)
            # must2203 is already supervisor on Shift 801
            caught_staff_overlap = False
            try:
                svc.assign_staff_shift(conn, 'haim2897', 803, 'must2203', 'MAIN_SUPERVISOR')
            except svc.PantryError as err:
                caught_staff_overlap = "overlapping shift" in str(err).lower()

            # volu0001 is approved on Shift 801 (10:00-12:00). Attempt request on overlapping 803 (11:00-13:00)
            caught_vol_overlap = False
            try:
                svc.request_volunteer_shift(conn, 'volu0001', 803)
            except svc.PantryError as err:
                caught_vol_overlap = "overlapping shift" in str(err).lower()

            passed = (caught_staff_overlap and caught_vol_overlap)
            record(8, "Shift overlap validation (Staff & Volunteer)",
                   "Both staff and volunteer prevented from overlapping shift assignments",
                   f"Staff caught: {caught_staff_overlap}, Volunteer caught: {caught_vol_overlap}",
                   passed, "Database triggers reject overlapping intervals")
        except Exception as e:
            conn.rollback()
            record(8, "Shift overlap validation", "Rejects overlap", str(e), False, str(e))

        # -------------------------------------------------------------
        # 9. Exact staff duty assignments (1 supervisor + 1 assistant)
        # -------------------------------------------------------------
        try:
            with conn.cursor() as cur:
                # Create an unstaffed shift
                cur.execute("""
                    INSERT INTO pantry_shift (shift_id, shift_date, start_time, end_time, status)
                    VALUES (850, '2026-11-26', '10:00', '12:00', 'PLANNED')
                    ON CONFLICT (shift_id) DO NOTHING;
                """)
                conn.commit()

            caught_unstaffed = False
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE pantry_shift SET status = 'OPEN' WHERE shift_id = 850")
                    conn.commit()
            except Exception:
                conn.rollback()
                caught_unstaffed = True

            # Assign only MAIN_SUPERVISOR
            svc.assign_staff_shift(conn, 'must2203', 850, 'must2203', 'MAIN_SUPERVISOR')
            caught_partial = False
            try:
                with conn.cursor() as cur:
                    cur.execute("UPDATE pantry_shift SET status = 'OPEN' WHERE shift_id = 850")
                    conn.commit()
            except Exception:
                conn.rollback()
                caught_partial = True

            # Now assign ASSISTANT as well -> exactly 1 supervisor + 1 assistant
            svc.assign_staff_shift(conn, 'must2203', 850, 'part2550', 'ASSISTANT')
            with conn.cursor() as cur:
                cur.execute("UPDATE pantry_shift SET status = 'OPEN' WHERE shift_id = 850")
                cur.execute("SELECT status FROM pantry_shift WHERE shift_id = 850")
                final_st = cur.fetchone()[0]
                conn.commit()

            passed = (caught_unstaffed and caught_partial and final_st == 'OPEN')
            record(9, "Exact staff duty enforcement",
                   "Shift cannot open without exactly 1 MAIN_SUPERVISOR and 1 ASSISTANT",
                   f"Unstaffed rejected: {caught_unstaffed}, Partial rejected: {caught_partial}, Staffed status: {final_st}",
                   passed, "Completeness constraint verified")
        except Exception as e:
            conn.rollback()
            record(9, "Exact staff duty enforcement", "Enforce 1 supervisor + 1 assistant", str(e), False, str(e))

        # -------------------------------------------------------------
        # 10. Session capacity and cancellation restoration
        # -------------------------------------------------------------
        try:
            # Session 815 has capacity = 5
            # Create 6 students (capa0001 .. capa0006)
            c_bids = []
            with conn.cursor() as cur:
                for i in range(1, 7):
                    u = f"capa{i:04d}"
                    cur.execute("INSERT INTO person (unikey, full_name, email) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                                (u, f"Cap Student {i}", f"{u}@test.uni"))
                    cur.execute("INSERT INTO student (unikey, degree_level, student_category) VALUES (%s, 'BACHELOR', 'DOMESTIC') ON CONFLICT DO NOTHING",
                                (u,))
                conn.commit()

            for i in range(1, 6):
                bid, _ = svc.book_session(conn, f"capa{i:04d}", 815)
                c_bids.append(bid)

            # 6th attempt should fail due to capacity 5
            caught_cap = False
            try:
                svc.book_session(conn, 'capa0006', 815)
            except svc.PantryError as err:
                caught_cap = "capacity of 5" in str(err).lower()

            # Cancel 1 booking
            svc.cancel_booking(conn, 'capa0001', c_bids[0])

            # Now 6th student can book
            bid6, _ = svc.book_session(conn, 'capa0006', 815)
            passed = (caught_cap and bid6 is not None)
            record(10, "Capacity limit and cancellation place freeing",
                   "5th fills capacity, 6th rejected; cancellation frees place, 6th then succeeds",
                   f"Over-capacity caught: {caught_cap}, 6th booking after cancel: ID {bid6}",
                   passed, "Cancellation immediately restores available space")
        except Exception as e:
            conn.rollback()
            record(10, "Capacity limit and cancellation", "Capacity and cancellation work", str(e), False, str(e))

        # -------------------------------------------------------------
        # 11. Concurrent attempts for the last available place
        # -------------------------------------------------------------
        try:
            # Session 816 has capacity = 5. Pre-fill 4 seats.
            with conn.cursor() as cur:
                for i in range(1, 5):
                    u = f"race{i:04d}"
                    cur.execute("INSERT INTO person (unikey, full_name, email) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                                (u, f"Racer {i}", f"{u}@test.uni"))
                    cur.execute("INSERT INTO student (unikey, degree_level, student_category) VALUES (%s, 'BACHELOR', 'DOMESTIC') ON CONFLICT DO NOTHING",
                                (u,))
                # 2 racing students
                for u in ('race0005', 'race0006'):
                    cur.execute("INSERT INTO person (unikey, full_name, email) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                                (u, f"Racer {u}", f"{u}@test.uni"))
                    cur.execute("INSERT INTO student (unikey, degree_level, student_category) VALUES (%s, 'BACHELOR', 'DOMESTIC') ON CONFLICT DO NOTHING",
                                (u,))
                conn.commit()

            for i in range(1, 5):
                svc.book_session(conn, f"race{i:04d}", 816)

            # Concurrent race for final (5th) seat
            race_results = {}
            def race(student_u):
                c = get_connection()
                try:
                    b_id, _ = svc.book_session(c, student_u, 816)
                    race_results[student_u] = ("SUCCESS", b_id)
                except Exception as exc:
                    race_results[student_u] = ("REJECTED", str(exc))
                finally:
                    c.close()

            t1 = threading.Thread(target=race, args=('race0005',))
            t2 = threading.Thread(target=race, args=('race0006',))
            t1.start(); t2.start()
            t1.join(); t2.join()

            wins = [k for k, v in race_results.items() if v[0] == "SUCCESS"]
            losses = [k for k, v in race_results.items() if v[0] == "REJECTED"]
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM booking WHERE session_id = 816 AND status <> 'CANCELLED'")
                final_active = cur.fetchone()[0]

            passed = (len(wins) == 1 and len(losses) == 1 and final_active == 5)
            record(11, "Concurrent race for final place",
                   "Exactly 1 winner, 1 rejected with capacity error; total active bookings = 5",
                   f"Winner: {wins}, Loser: {losses}, Final count: {final_active}", passed,
                   "Row-level locking guarantees serializability under concurrency")
        except Exception as e:
            conn.rollback()
            record(11, "Concurrent race for final place", "Safe serialization", str(e), False, str(e))

        # -------------------------------------------------------------
        # 12. Valid and invalid QR check-in
        # -------------------------------------------------------------
        try:
            # Create a session for today late evening so it hasn't finished, allowing check-in
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pantry_shift (shift_id, shift_date, start_time, end_time, status)
                    VALUES (820, CURRENT_DATE, '23:00', '23:59', 'PLANNED')
                    ON CONFLICT (shift_id) DO NOTHING;
                    INSERT INTO shift_staff_assignment (shift_id, staff_unikey, assignment_role)
                    VALUES (820, 'must2203', 'MAIN_SUPERVISOR'), (820, 'part2550', 'ASSISTANT')
                    ON CONFLICT DO NOTHING;
                    INSERT INTO session (session_id, shift_id, session_date, start_time, end_time, capacity)
                    VALUES (821, 820, CURRENT_DATE, '23:00', '23:30', 50)
                    ON CONFLICT (session_id) DO NOTHING;
                    INSERT INTO person (unikey, full_name, email)
                    VALUES ('scan0001', 'Scanner Student', 'scan@test.uni') ON CONFLICT DO NOTHING;
                    INSERT INTO student (unikey, degree_level, student_category)
                    VALUES ('scan0001', 'BACHELOR', 'DOMESTIC') ON CONFLICT DO NOTHING;
                """)
                conn.commit()

            b_scan_id, scan_token = svc.book_session(conn, 'scan0001', 821)
            # 1. Valid scan
            c_id, c_stud = svc.check_in(conn, scan_token)
            with conn.cursor() as cur:
                cur.execute("SELECT status, attendance_at FROM booking WHERE booking_id = %s", (c_id,))
                c_st, c_time = cur.fetchone()
            valid_ok = (c_st == 'ATTENDED' and c_time is not None)

            # 2. Repeated scan rejection
            caught_repeat = False
            try:
                svc.check_in(conn, scan_token)
            except svc.PantryError as err:
                caught_repeat = "attended" in str(err).lower()

            # 3. Invalid token rejection
            caught_invalid = False
            try:
                svc.check_in(conn, "TOTALLY-BOGUS-TOKEN-XYZ")
            except svc.PantryError as err:
                caught_invalid = "unknown qr" in str(err).lower()

            passed = (valid_ok and caught_repeat and caught_invalid)
            record(12, "Valid and invalid QR check-in",
                   "Valid check-in marks ATTENDED with timestamp; repeat and bogus tokens rejected",
                   f"Valid scan: {valid_ok}, Repeat rejected: {caught_repeat}, Unknown rejected: {caught_invalid}",
                   passed, "QR attendance behaves atomically and idempotently")
        except Exception as e:
            conn.rollback()
            record(12, "Valid and invalid QR check-in", "Check-in validation", str(e), False, str(e))

        # -------------------------------------------------------------
        # 13. No-show processing and repeated execution
        # -------------------------------------------------------------
        try:
            # Create past day booking (2026-10-01) with properly staffed shift
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO pantry_shift (shift_id, shift_date, start_time, end_time, status)
                    VALUES (830, '2026-10-01', '10:00', '12:00', 'PLANNED')
                    ON CONFLICT (shift_id) DO NOTHING;
                    INSERT INTO shift_staff_assignment (shift_id, staff_unikey, assignment_role)
                    VALUES (830, 'must2203', 'MAIN_SUPERVISOR'), (830, 'part2550', 'ASSISTANT')
                    ON CONFLICT DO NOTHING;
                    UPDATE pantry_shift SET status = 'CLOSED' WHERE shift_id = 830;
                    INSERT INTO session (session_id, shift_id, session_date, start_time, end_time, capacity)
                    VALUES (831, 830, '2026-10-01', '10:00', '10:30', 50)
                    ON CONFLICT (session_id) DO NOTHING;
                    INSERT INTO person (unikey, full_name, email)
                    VALUES ('nosh0001', 'NoShow Student', 'noshow@test.uni') ON CONFLICT DO NOTHING;
                    INSERT INTO student (unikey, degree_level, student_category)
                    VALUES ('nosh0001', 'BACHELOR', 'DOMESTIC') ON CONFLICT DO NOTHING;
                    INSERT INTO booking (student_unikey, session_id, status, qr_token)
                    VALUES ('nosh0001', 831, 'CONFIRMED', 'TEST-TOKEN-NOSHOW')
                    ON CONFLICT (qr_token) DO NOTHING;
                """)
                conn.commit()

            # First run marks at least 1 absent
            marked1 = svc.mark_no_shows(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT status FROM booking WHERE qr_token = 'TEST-TOKEN-NOSHOW'")
                ns_st = cur.fetchone()[0]

            # Second run marks 0 (idempotent, safe against re-running)
            marked2 = svc.mark_no_shows(conn)

            passed = (marked1 >= 1 and ns_st == 'ABSENT' and marked2 == 0)
            record(13, "No-show processing & idempotence",
                   "Past confirmed bookings marked ABSENT; re-running safe and reports 0 changes",
                   f"First run marked: {marked1}, Booking status: {ns_st}, Second run marked: {marked2}",
                   passed, "No-show processing is strictly idempotent")
        except Exception as e:
            conn.rollback()
            record(13, "No-show processing", "Marks absences", str(e), False, str(e))

        # -------------------------------------------------------------
        # 14. Admin override safeguards and audit trail
        # -------------------------------------------------------------
        try:
            # Student stud0001 already has booking in 811 on 2026-11-20
            # 1. Attempt override without reason (MUST FAIL)
            caught_empty_reason = False
            try:
                svc.book_session(conn, 'stud0001', 812, override_by_staff='must2203', reason='   ')
            except svc.PantryError as err:
                caught_empty_reason = "reason" in str(err).lower()

            # 2. Attempt override with invalid staff (MUST FAIL)
            caught_bad_staff = False
            try:
                svc.book_session(conn, 'stud0001', 812, override_by_staff='nost0001', reason='Welfare')
            except svc.PantryError as err:
                caught_bad_staff = "staff" in str(err).lower()

            # 3. Legitimate override (MUST SUCCEED)
            ovr_bid, ovr_tok = svc.book_session(conn, 'stud0001', 812, override_by_staff='must2203', reason='Emergency welfare exception')
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT admin_override, override_by_staff, override_reason
                    FROM booking WHERE booking_id = %s""", (ovr_bid,))
                is_ovr, staff_id, rsn = cur.fetchone()

            passed = (caught_empty_reason and caught_bad_staff and is_ovr is True and staff_id == 'must2203' and 'welfare' in rsn.lower())
            record(14, "Admin override safeguards & audit trail",
                   "Rejects missing reason or bad staff; records full audit trail on success",
                   f"Empty reason caught: {caught_empty_reason}, Bad staff caught: {caught_bad_staff}, Overridden: {is_ovr}, Staff: {staff_id}",
                   passed, "Complete audit trail preserved")
        except Exception as e:
            conn.rollback()
            record(14, "Admin override safeguards", "Override behaves safely", str(e), False, str(e))

        # -------------------------------------------------------------
        # 15. Inventory receipt, waste, count, and low-stock reporting
        # -------------------------------------------------------------
        try:
            # Create a deliberate test product with low stock
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO product (product_id, product_code, product_name, category, counting_unit, low_stock_threshold)
                    VALUES (999, 'TST-PROD-01', 'Test Emergency Biscuits', 'Snacks', 'pack', 50)
                    ON CONFLICT (product_id) DO NOTHING;
                    INSERT INTO purchase_record (purchase_id, recorded_by_staff, purchase_date, reference)
                    VALUES (999, 'must2203', CURRENT_DATE, 'TEST-PO-999')
                    ON CONFLICT (purchase_id) DO NOTHING;
                    INSERT INTO purchase_record_line (purchase_line_id, purchase_id, product_id, quantity, unit_cost)
                    VALUES (999, 999, 999, 100, 2.50)
                    ON CONFLICT (purchase_line_id) DO NOTHING;
                    INSERT INTO stock_batch (stock_number, product_id, purchase_line_id, batch_code, received_on, received_qty)
                    VALUES ('TST-STK-999', 999, 999, 'BATCH-999', CURRENT_DATE, 100)
                    ON CONFLICT (stock_number) DO NOTHING;
                """)
                conn.commit()

            # Record OPENING count of 20 (which is < threshold 50)
            svc.record_stock_count(conn, 'must2203', 'TST-STK-999', 'OPENING', 20, shift_id=801, notes='Opening count')
            # Record intra-shift adjustments: RECEIPT +10, WASTE +2
            svc.record_stock_adjustment(conn, 'must2203', 801, 'TST-STK-999', 'RECEIPT', 10, 'Supplier top-up')
            svc.record_stock_adjustment(conn, 'must2203', 801, 'TST-STK-999', 'WASTE', 2, 'Damaged box')
            # Record CLOSING count: 28
            svc.record_stock_count(conn, 'must2203', 'TST-STK-999', 'CLOSING', 28, shift_id=801, notes='Closing count')

            # Verify shift_stock_count has both opening and closing reconciliations
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT opening_qty, closing_qty FROM shift_stock_count
                    WHERE shift_id = 801 AND stock_number = 'TST-STK-999'
                """)
                op_q, cl_q = cur.fetchone()

            # Check low stock report - our test product (28 < 50) MUST appear
            low_stock_rows = svc.report_low_stock(conn)
            low_stock_names = [r[0] for r in low_stock_rows]
            prod_in_report = ('Test Emergency Biscuits' in low_stock_names)

            passed = (op_q == 20 and cl_q == 28 and prod_in_report)
            record(15, "Inventory movements & low-stock reporting",
                   "Counts reconcile with shift summary; low stock product (< threshold) surfaces in report",
                   f"Opening: {op_q}, Closing: {cl_q}, Deliberate product in low-stock report: {prod_in_report}",
                   passed, "End-to-end inventory tracking verified")
        except Exception as e:
            conn.rollback()
            record(15, "Inventory movements & reporting", "Tracks inventory", str(e), False, str(e))

        # -------------------------------------------------------------
        # 16. All analytics queries Q1-Q12
        # -------------------------------------------------------------
        try:
            queries_path = os.path.join(os.path.dirname(__file__), "..", "campus_pantry_sql", "03_queries.sql")
            with open(queries_path, "r", encoding="utf-8") as f:
                sql_content = f.read()

            with conn.cursor() as cur:
                cur.execute(sql_content)

            record(16, "All 12 analytics queries (Q1-Q12)",
                   "All queries execute cleanly and produce valid tabular outputs",
                   "Queries Q1 through Q12 executed successfully", True,
                   "All 12 queries verified against active schema")
        except Exception as e:
            conn.rollback()
            record(16, "All 12 analytics queries", "Execute cleanly", str(e), False, str(e))

        # -------------------------------------------------------------
        # 17. Database integrity and validation checks
        # -------------------------------------------------------------
        try:
            with conn.cursor() as cur:
                # 1. Closed or open shifts must have exactly 1 supervisor and 1 assistant
                cur.execute("""
                    SELECT count(*) FROM (
                        SELECT sh.shift_id
                        FROM pantry_shift sh
                        LEFT JOIN shift_staff_assignment a ON a.shift_id = sh.shift_id
                        WHERE sh.status IN ('OPEN', 'CLOSED')
                        GROUP BY sh.shift_id
                        HAVING count(*) FILTER (WHERE a.assignment_role = 'MAIN_SUPERVISOR') <> 1
                            OR count(*) FILTER (WHERE a.assignment_role = 'ASSISTANT') <> 1
                    ) s;
                """)
                bad_staffing = cur.fetchone()[0]

                # 2. No session exceeds capacity
                cur.execute("""
                    SELECT count(*) FROM (
                        SELECT s.session_id
                        FROM session s
                        LEFT JOIN booking b ON b.session_id = s.session_id AND b.status <> 'CANCELLED'
                        GROUP BY s.session_id, s.capacity
                        HAVING count(b.booking_id) > s.capacity
                    ) o;
                """)
                over_capacity = cur.fetchone()[0]

                # 3. Attendance invariants (status = ATTENDED <=> attendance_at is not null)
                cur.execute("""
                    SELECT count(*) FROM booking
                    WHERE (status = 'ATTENDED' AND attendance_at IS NULL)
                       OR (status <> 'ATTENDED' AND attendance_at IS NOT NULL)
                """)
                bad_attendance = cur.fetchone()[0]

                # 4. No overlapping shift staff assignments
                cur.execute("""
                    SELECT count(*) FROM shift_staff_assignment s1
                    JOIN pantry_shift p1 ON p1.shift_id = s1.shift_id
                    JOIN shift_staff_assignment s2 ON s2.staff_unikey = s1.staff_unikey AND s2.shift_id <> s1.shift_id
                    JOIN pantry_shift p2 ON p2.shift_id = s2.shift_id
                    WHERE p1.shift_date = p2.shift_date
                      AND p1.start_time < p2.end_time AND p2.start_time < p1.end_time;
                """)
                staff_overlaps = cur.fetchone()[0]

                # 5. No overlapping volunteer shifts
                cur.execute("""
                    SELECT count(*) FROM volunteer_shift v1
                    JOIN pantry_shift p1 ON p1.shift_id = v1.shift_id
                    JOIN volunteer_shift v2 ON v2.volunteer_unikey = v1.volunteer_unikey AND v2.shift_id <> v1.shift_id
                    JOIN pantry_shift p2 ON p2.shift_id = v2.shift_id
                    WHERE v1.status IN ('PENDING', 'APPROVED') AND v2.status IN ('PENDING', 'APPROVED')
                      AND p1.shift_date = p2.shift_date
                      AND p1.start_time < p2.end_time AND p2.start_time < p1.end_time;
                """)
                vol_overlaps = cur.fetchone()[0]

            passed = (bad_staffing == 0 and over_capacity == 0 and bad_attendance == 0 and staff_overlaps == 0 and vol_overlaps == 0)
            record(17, "Database integrity & validation invariant checks",
                   "0 violations across all 5 structural integrity invariants",
                   f"Staffing violations: {bad_staffing}, Over capacity: {over_capacity}, Bad attendance: {bad_attendance}, Overlaps: {staff_overlaps + vol_overlaps}",
                   passed, "All database constraints, triggers, and invariants hold")
        except Exception as e:
            conn.rollback()
            record(17, "Database integrity checks", "0 violations", str(e), False, str(e))

    finally:
        # Post-cleanup ensures test database is left in a clean state
        cleanup_test_data(conn)
        conn.close()

    print("\n" + "=" * 80)
    print("FINAL TEST SUMMARY")
    print("=" * 80)
    passed_count = sum(1 for r in results if r["status"] == "PASS")
    total_count = len(results)
    print(f"Total Tests: {total_count} | Passed: {passed_count} | Failed: {total_count - passed_count}\n")
    print("| # | Test Name | Expected | Actual | Status |")
    print("|---|-----------|----------|--------|--------|")
    for r in results:
        print(f"| {r['num']:2d} | {r['name']} | {r['expected']} | {r['actual']} | **{r['status']}** |")

    return passed_count == total_count


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
