"""Behavioural regression tests against real PostgreSQL, never the working DB.

Dates derive from Sydney's current date. Only the internal business clock is
patched for attendance boundaries; SQL constraints and locking stay enabled.
Each test reloads the canonical schema and seed in the runner's owned database.
"""
from contextlib import redirect_stdout
from datetime import datetime, time, timedelta
from decimal import Decimal
import io
import re
import sys
import threading
import unittest
from unittest.mock import patch

import psycopg2
import support

sys.path.insert(0, str(support.ROOT / "campus_pantry_app"))
import services as svc
import cli

STAFF = "must2203"
VOLUNTEER = "nikh3591"
STUDENT = "alex1001"
STOCK = "STK-000001"


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.conn = support.connect()
        support.reset(self.conn)
        self.today = self.sql("SELECT (CURRENT_TIMESTAMP AT TIME ZONE 'Australia/Sydney')::date")[0][0]
        # Keep fresh-day fixtures separate from the historical 9 October seed.
        self.future = max(self.today + timedelta(days=7), datetime(2026, 11, 1).date())

    def tearDown(self):
        self.conn.close()

    def sql(self, statement, params=(), conn=None):
        with conn or self.conn as active:
            with active.cursor() as cur:
                cur.execute(statement, params)
                return cur.fetchall() if cur.description else []

    def rejected_sql(self, statement, params=(), pattern=None):
        context = self.assertRaisesRegex(psycopg2.Error, pattern) if pattern else self.assertRaises(psycopg2.Error)
        with context:
            self.sql(statement, params)
        self.assertEqual(self.sql("SELECT 1"), [(1,)], "A rejected transaction must remain usable")

    def clock(self, hour=12, minute=0, day=None):
        return patch.object(svc, "_business_now", return_value=datetime.combine(day or self.today, time(hour, minute)))

    def shift(self, on=None, start="10:00", end="12:00"):
        return self.sql("INSERT INTO pantry_shift(shift_date,start_time,end_time) VALUES (%s,%s,%s) RETURNING shift_id",
                        (on or self.future, start, end))[0][0]

    def session(self, shift=None, on=None, start="10:00", end="10:30", capacity=50):
        shift = shift or self.shift(on=on)
        return self.sql("INSERT INTO session(shift_id,session_date,start_time,end_time,capacity) "
                        "VALUES (%s,%s,%s,%s,%s) RETURNING session_id",
                        (shift, on or self.future, start, end, capacity))[0][0]

    def staffed(self, shift=None):
        shift = shift or self.shift()
        svc.assign_staff_shift(self.conn, STAFF, shift, STAFF, "MAIN_SUPERVISOR")
        svc.assign_staff_shift(self.conn, STAFF, shift, "part2550", "ASSISTANT")
        return shift

    def opened(self, shift=None):
        shift = self.staffed(shift)
        svc.set_shift_status(self.conn, STAFF, shift, "OPEN")
        return shift

    def student(self, index):
        key = f"test{index:04d}"
        self.sql("INSERT INTO person(unikey,full_name,email) VALUES (%s,%s,%s)",
                 (key, f"Test Student {index}", f"student{index}@example.test"))
        self.sql("INSERT INTO student(unikey) VALUES (%s)", (key,))
        return key

    def today_booking(self, key=STUDENT):
        shift = self.shift(on=self.today)
        session = self.session(shift, on=self.today)
        self.opened(shift)
        with self.clock(9):
            booking, token = svc.book_session(self.conn, key, session)
        return shift, session, booking, token

    def race(self, first, second, expected_error):
        """Start independent connections at one barrier; bound every wait.

        The result assertion rejects unexpected deadlocks/timeouts, rather than
        counting every exception as a successful business-rule rejection.
        """
        barrier = threading.Barrier(2)
        results = [None, None]
        connections = []

        def worker(index, operation):
            conn = None
            try:
                conn = support.connect()
                connections.append(conn)
                barrier.wait(timeout=5)
                results[index] = ("success", operation(conn))
            except svc.PantryError as exc:
                results[index] = ("rejected", str(exc))
            except Exception as exc:
                results[index] = ("unexpected", f"{type(exc).__name__}: {exc}")
            finally:
                if conn:
                    conn.close()

        workers = [threading.Thread(target=worker, args=(i, op), daemon=True)
                   for i, op in enumerate((first, second))]
        for thread in workers:
            thread.start()
        for thread in workers:
            thread.join(timeout=15)
        if any(thread.is_alive() for thread in workers):
            for conn in connections:
                if not conn.closed:
                    conn.cancel()
            for thread in workers:
                thread.join(timeout=2)
            self.fail("Concurrent operations exceeded their timeout")
        self.assertEqual([r[0] for r in results].count("success"), 1, results)
        rejected = [r[1] for r in results if r[0] == "rejected"]
        self.assertEqual(len(rejected), 1, results)
        self.assertRegex(rejected[0].lower(), expected_error)
        self.assertNotRegex(rejected[0].lower(), "deadlock|timeout|connection")
        return results

    def test_schema_seed_and_shared_roles(self):
        self.assertEqual(self.sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='campus_pantry' AND table_type='BASE TABLE'"), [(16,)])
        self.assertEqual(self.sql("SELECT count(*) FROM information_schema.views WHERE table_schema='campus_pantry'"), [(3,)])
        self.assertEqual(self.sql("SELECT count(*) FROM booking"), [(15,)])
        self.assertEqual(self.sql("SELECT count(*) FROM session"), [(12,)])
        self.assertEqual(svc.find_person(self.conn, "kevi5326")[1:], (True, True, False))
        self.assertIsNone(svc.find_person(self.conn, "none0000"))

    def test_booking_daily_limit_and_token(self):
        shift = self.shift()
        first = self.session(shift)
        second = self.session(shift, start="10:30", end="11:00")
        booking, token = svc.book_session(self.conn, STUDENT, first)
        self.assertGreater(len(token), 12)
        self.assertEqual(svc.my_bookings(self.conn, STUDENT)[0][0], booking)
        with self.assertRaisesRegex(svc.PantryError, "active booking"):
            svc.book_session(self.conn, STUDENT, second)
        self.assertEqual(self.sql("SELECT count(*) FROM booking WHERE student_unikey=%s", (STUDENT,)), [(1,)])

    def test_non_student_and_missing_session_rejected(self):
        session = self.session()
        with self.assertRaisesRegex(svc.PantryError, "student"):
            svc.book_session(self.conn, STAFF, session)
        with self.assertRaisesRegex(svc.PantryError, "does not exist"):
            svc.book_session(self.conn, STUDENT, 999999)

    def test_cancellation_releases_capacity_and_requires_owner(self):
        session = self.session(capacity=1)
        booking, _ = svc.book_session(self.conn, STUDENT, session)
        with self.assertRaises(svc.PantryError):
            svc.cancel_booking(self.conn, "emma2002", booking)
        with self.assertRaisesRegex(svc.PantryError, "capacity"):
            svc.book_session(self.conn, "emma2002", session)
        svc.cancel_booking(self.conn, STUDENT, booking)
        svc.book_session(self.conn, "emma2002", session)
        self.assertEqual(self.sql("SELECT active_bookings,spaces_remaining FROM v_booking_attendance WHERE session_id=%s", (session,)), [(1, 0)])
        with self.assertRaises(svc.PantryError):
            svc.cancel_booking(self.conn, STUDENT, booking)

    def test_exact_fifty_seat_boundary(self):
        session = self.session()
        for index in range(1, 51):
            svc.book_session(self.conn, self.student(index), session)
        extra = self.student(51)
        with self.assertRaisesRegex(svc.PantryError, "capacity of 50"):
            svc.book_session(self.conn, extra, session)
        self.assertEqual(self.sql("SELECT active_bookings,spaces_remaining FROM v_booking_attendance WHERE session_id=%s", (session,)), [(50, 0)])

    def test_concurrency_last_seat(self):
        session = self.session(capacity=1)
        self.race(lambda c: svc.book_session(c, STUDENT, session),
                  lambda c: svc.book_session(c, "emma2002", session), "capacity")
        self.assertEqual(self.sql("SELECT count(*) FROM booking WHERE session_id=%s", (session,)), [(1,)])

    def test_concurrency_direct_sql_last_seat(self):
        session = self.session(capacity=1)
        def raw_booking(conn, student, token):
            return svc._run(conn, lambda cur: cur.execute(
                "INSERT INTO booking(student_unikey,session_id,qr_token) VALUES (%s,%s,%s)",
                (student, session, token)))
        self.race(lambda c: raw_booking(c, STUDENT, "RAW-CAPACITY-A"),
                  lambda c: raw_booking(c, "emma2002", "RAW-CAPACITY-B"), "capacity")
        self.assertEqual(self.sql("SELECT count(*) FROM booking WHERE session_id=%s", (session,)), [(1,)])

    def test_concurrency_same_student_two_sessions(self):
        shift = self.shift()
        first = self.session(shift)
        second = self.session(shift, start="10:30", end="11:00")
        self.race(lambda c: svc.book_session(c, STUDENT, first),
                  lambda c: svc.book_session(c, STUDENT, second), "active booking")
        self.assertEqual(self.sql("SELECT count(*) FROM booking WHERE student_unikey=%s", (STUDENT,)), [(1,)])

    def test_override_validates_actor_reason_and_updates(self):
        shift = self.shift()
        first = self.session(shift)
        second = self.session(shift, start="10:30", end="11:00")
        svc.book_session(self.conn, STUDENT, first)
        with self.assertRaisesRegex(svc.PantryError, "reason"):
            svc.book_session(self.conn, STUDENT, second, STAFF, " ")
        with self.assertRaisesRegex(svc.PantryError, "staff|Staff"):
            svc.book_session(self.conn, STUDENT, second, VOLUNTEER, "Exception")
        booking, _ = svc.book_session(self.conn, STUDENT, second, STAFF, "Accessible collection")
        self.assertEqual(self.sql("SELECT admin_override,override_by_staff,override_reason FROM booking WHERE booking_id=%s", (booking,)), [(True, STAFF, "Accessible collection")])
        self.rejected_sql("UPDATE booking SET override_reason=NULL WHERE booking_id=%s", (booking,), "reason")
        self.rejected_sql("UPDATE booking SET admin_override=false,override_by_staff=NULL,override_reason=NULL WHERE booking_id=%s", (booking,), "active booking")

    def test_override_cannot_skip_capacity(self):
        session = self.session(capacity=1)
        svc.book_session(self.conn, STUDENT, session)
        with self.assertRaisesRegex(svc.PantryError, "capacity"):
            svc.book_session(self.conn, "emma2002", session, STAFF, "Extra collection")

    def test_attendance_metadata_and_qr_constraints(self):
        self.rejected_sql("UPDATE booking SET status='ATTENDED' WHERE booking_id=1", pattern="booking_attendance_consistency")
        self.rejected_sql("UPDATE booking SET attendance_at=now() WHERE booking_id=1", pattern="booking_attendance_consistency")
        self.rejected_sql("UPDATE booking SET qr_token='DEMO-QR-001' WHERE booking_id=2", pattern="unique")

    def test_capacity_parent_schedule_and_batch_integrity(self):
        self.rejected_sql("UPDATE session SET capacity=1 WHERE session_id=1", pattern="Capacity")
        self.rejected_sql("UPDATE session SET session_date=session_date+1 WHERE session_id=1", pattern="immutable")
        self.rejected_sql("UPDATE pantry_shift SET start_time='09:00' WHERE shift_id=1", pattern="immutable")
        self.rejected_sql("DELETE FROM shift_staff_assignment WHERE shift_id=1 AND assignment_role='ASSISTANT'", pattern="PLANNED")
        self.rejected_sql("UPDATE purchase_record_line SET product_id=2 WHERE purchase_line_id=1", pattern="foreign key")
        self.rejected_sql("UPDATE stock_batch SET product_id=2 WHERE stock_number=%s", (STOCK,), "foreign key")

    def test_session_must_fit_shift_without_overlap(self):
        shift = self.shift()
        self.session(shift)
        self.rejected_sql("INSERT INTO session(shift_id,session_date,start_time,end_time) VALUES (%s,%s,'09:30','10:00')", (shift, self.future), "within")
        self.rejected_sql("INSERT INTO session(shift_id,session_date,start_time,end_time) VALUES (%s,%s,'10:15','10:45')", (shift, self.future), "overlap")
        self.rejected_sql("INSERT INTO session(shift_id,session_date,start_time,end_time,capacity) VALUES (%s,%s,'10:30','11:00',51)", (shift, self.future), "check constraint")

    def test_setup_day_and_lifecycle(self):
        self.assertEqual(svc.set_up_day(self.conn, self.future, STAFF), 12)
        rows = svc.list_sessions(self.conn, self.future)
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row[3:] == (0, 50, 50) for row in rows))
        shifts = self.sql("SELECT shift_id FROM pantry_shift WHERE shift_date=%s ORDER BY start_time", (self.future,))
        self.assertEqual(len(shifts), 3)
        shift = shifts[0][0]
        with self.assertRaises(svc.PantryError):
            svc.set_shift_status(self.conn, STAFF, shift, "CLOSED")
        with self.assertRaisesRegex(svc.PantryError, "MAIN_SUPERVISOR"):
            svc.set_shift_status(self.conn, STAFF, shift, "OPEN")
        self.opened(shift)
        svc.set_shift_status(self.conn, STAFF, shift, "CLOSED")
        with self.assertRaises(svc.PantryError):
            svc.set_shift_status(self.conn, STAFF, shift, "OPEN")
        with self.assertRaises(svc.PantryError):
            svc.set_up_day(self.conn, self.future, STAFF)
        self.assertEqual(self.sql("SELECT count(*) FROM session WHERE session_date=%s", (self.future,)), [(12,)])

    def test_staff_assignment_upsert_and_planned_role_correction(self):
        shift = self.shift()
        svc.assign_staff_shift(self.conn, STAFF, shift, STAFF, "MAIN_SUPERVISOR")
        svc.assign_staff_shift(self.conn, STAFF, shift, STAFF, "MAIN_SUPERVISOR")
        self.assertEqual(self.sql("SELECT staff_unikey,assignment_role FROM shift_staff_assignment WHERE shift_id=%s", (shift,)), [(STAFF, "MAIN_SUPERVISOR")])
        svc.assign_staff_shift(self.conn, STAFF, shift, STAFF, "ASSISTANT")
        self.assertEqual(self.sql("SELECT staff_unikey,assignment_role FROM shift_staff_assignment WHERE shift_id=%s", (shift,)), [(STAFF, "ASSISTANT")])
        svc.assign_staff_shift(self.conn, STAFF, shift, "part2550", "MAIN_SUPERVISOR")
        with self.assertRaises(svc.PantryError):
            svc.assign_staff_shift(self.conn, STAFF, shift, STAFF, "MAIN_SUPERVISOR")
        self.assertEqual(self.sql("SELECT count(*) FROM shift_staff_assignment WHERE shift_id=%s", (shift,)), [(2,)])

    def test_checkin_same_day_late_repeat_and_unknown(self):
        _, _, booking, token = self.today_booking()
        with self.clock(15, 59):
            self.assertEqual(svc.check_in(self.conn, token, STAFF), (booking, STUDENT))
            before = self.sql("SELECT attendance_at FROM booking WHERE booking_id=%s", (booking,))
            self.assertEqual(svc.check_in(self.conn, token, STAFF), (booking, STUDENT))
            self.assertEqual(self.sql("SELECT attendance_at FROM booking WHERE booking_id=%s", (booking,)), before)
            with self.assertRaisesRegex(svc.PantryError, "Unknown"):
                svc.check_in(self.conn, "nonexistent-token", STAFF)
        self.assertEqual(self.sql("SELECT status,attendance_at IS NOT NULL FROM booking WHERE booking_id=%s", (booking,)), [("ATTENDED", True)])

    def test_checkin_operating_hours_boundaries(self):
        _, _, booking, token = self.today_booking()
        for hour, minute in ((9, 59), (16, 0), (23, 0)):
            with self.clock(hour, minute), self.assertRaises(svc.PantryError):
                svc.check_in(self.conn, token, STAFF)
        self.assertEqual(self.sql("SELECT status FROM booking WHERE booking_id=%s", (booking,)), [("CONFIRMED",)])
        with self.clock(10):
            svc.check_in(self.conn, token, STAFF)

    def test_checkin_late_arrival_after_original_shift_closed(self):
        shift, _, booking, token = self.today_booking()
        svc.set_shift_status(self.conn, STAFF, shift, "CLOSED")
        with self.clock(13):
            self.assertEqual(svc.check_in(self.conn, token, STAFF), (booking, STUDENT))
        self.assertEqual(self.sql("SELECT status FROM pantry_shift WHERE shift_id=%s", (shift,)), [("CLOSED",)])
        self.assertEqual(self.sql("SELECT status FROM booking WHERE booking_id=%s", (booking,)), [("ATTENDED",)])

    def test_checkin_past_future_and_unopened_rejected(self):
        _, _, _, token = self.today_booking()
        for day in (self.today - timedelta(days=1), self.today + timedelta(days=1)):
            with self.clock(day=day), self.assertRaises(svc.PantryError):
                svc.check_in(self.conn, token, STAFF)
        shift = self.shift(on=self.today, start="12:00", end="14:00")
        session = self.session(shift, on=self.today, start="12:00", end="12:30")
        with self.clock(9):
            _, planned_token = svc.book_session(self.conn, "emma2002", session)
        with self.clock(12), self.assertRaisesRegex(svc.PantryError, "OPEN|open"):
            svc.check_in(self.conn, planned_token, STAFF)

    def test_no_show_boundary_and_idempotence(self):
        _, _, booking, _ = self.today_booking()
        with self.clock(15, 59):
            svc.mark_no_shows(self.conn, STAFF)
        self.assertEqual(self.sql("SELECT status FROM booking WHERE booking_id=%s", (booking,)), [("CONFIRMED",)])
        with self.clock(16):
            self.assertEqual(svc.mark_no_shows(self.conn, STAFF), 1)
            self.assertEqual(svc.mark_no_shows(self.conn, STAFF), 0)
        self.assertEqual(self.sql("SELECT status,attendance_at FROM booking WHERE booking_id=%s", (booking,)), [("ABSENT", None)])

    def test_inactive_roles_are_hidden_and_denied(self):
        self.sql("UPDATE staff SET is_active=false WHERE unikey=%s", (STAFF,))
        self.sql("UPDATE volunteer SET is_active=false WHERE unikey=%s", (VOLUNTEER,))
        self.assertFalse(svc.find_person(self.conn, STAFF)[3])
        self.assertFalse(svc.find_person(self.conn, VOLUNTEER)[2])
        with self.assertRaisesRegex(svc.PantryError, "active staff"):
            svc.mark_no_shows(self.conn, STAFF)
        with self.assertRaisesRegex(svc.PantryError, "active volunteer"):
            svc.request_volunteer_shift(self.conn, VOLUNTEER, self.shift())

    def test_staff_reports_and_mutations_require_actor(self):
        operations = [lambda: svc.check_in(self.conn, "DEMO-QR-001"),
                      lambda: svc.mark_no_shows(self.conn),
                      lambda: svc.set_up_day(self.conn, self.future),
                      lambda: svc.report_day_summary(self.conn, self.future),
                      lambda: svc.report_near_capacity(self.conn),
                      lambda: svc.report_low_stock(self.conn),
                      lambda: svc.latest_stock(self.conn),
                      lambda: svc.session_bookings(self.conn, 1),
                      lambda: svc.shift_roster(self.conn, self.future),
                      lambda: svc.list_volunteer_requests(self.conn),
                      lambda: svc.report_shift_stock(self.conn, self.future)]
        for operation in operations:
            with self.assertRaisesRegex(svc.PantryError, "staff"):
                operation()

    def test_volunteer_request_approval_and_stale_review(self):
        shift = self.shift()
        svc.request_volunteer_shift(self.conn, VOLUNTEER, shift)
        with self.assertRaises(svc.PantryError):
            svc.request_volunteer_shift(self.conn, VOLUNTEER, shift)
        self.assertEqual(svc.review_volunteer_request(self.conn, STAFF, shift, VOLUNTEER, "APPROVED"), "APPROVED")
        self.assertEqual(self.sql("SELECT status,reviewed_by_staff,reviewed_at IS NOT NULL FROM volunteer_shift WHERE shift_id=%s", (shift,)), [("APPROVED", STAFF, True)])
        with self.assertRaises(svc.PantryError):
            svc.review_volunteer_request(self.conn, STAFF, shift, VOLUNTEER, "REJECTED")
        with self.assertRaises(svc.PantryError):
            svc.withdraw_volunteer_request(self.conn, VOLUNTEER, shift)

    def test_volunteer_reapply_and_withdraw(self):
        shift = self.shift()
        svc.request_volunteer_shift(self.conn, VOLUNTEER, shift)
        svc.review_volunteer_request(self.conn, STAFF, shift, VOLUNTEER, "REJECTED")
        svc.request_volunteer_shift(self.conn, VOLUNTEER, shift)
        self.assertEqual(self.sql("SELECT status,reviewed_by_staff,reviewed_at FROM volunteer_shift WHERE shift_id=%s", (shift,)), [("PENDING", None, None)])
        svc.withdraw_volunteer_request(self.conn, VOLUNTEER, shift)
        self.assertEqual(self.sql("SELECT count(*) FROM volunteer_shift WHERE shift_id=%s", (shift,)), [(0,)])

    def test_past_and_closed_volunteer_requests_rejected(self):
        past = self.shift(on=self.today - timedelta(days=1))
        closed = self.opened()
        svc.set_shift_status(self.conn, STAFF, closed, "CLOSED")
        for shift in (past, closed):
            with self.assertRaises(svc.PantryError):
                svc.request_volunteer_shift(self.conn, VOLUNTEER, shift)
        listed = {row[0] for row in svc.list_upcoming_shifts(self.conn)}
        self.assertNotIn(past, listed)
        self.assertNotIn(closed, listed)
        self.assertTrue(listed.isdisjoint({1, 2, 3}))

    def test_concurrency_volunteer_overlap(self):
        first = self.shift()
        second = self.shift(start="11:00", end="13:00")
        self.race(lambda c: svc.request_volunteer_shift(c, VOLUNTEER, first),
                  lambda c: svc.request_volunteer_shift(c, VOLUNTEER, second), "overlap")
        self.assertEqual(self.sql("SELECT count(*) FROM volunteer_shift WHERE shift_id IN (%s,%s)", (first, second)), [(1,)])

    def test_concurrency_staff_overlap(self):
        first = self.shift()
        second = self.shift(start="11:00", end="13:00")
        self.race(lambda c: svc.assign_staff_shift(c, STAFF, first, "haim2897", "MAIN_SUPERVISOR"),
                  lambda c: svc.assign_staff_shift(c, STAFF, second, "haim2897", "MAIN_SUPERVISOR"), "overlap")
        self.assertEqual(self.sql("SELECT count(*) FROM shift_staff_assignment WHERE shift_id IN (%s,%s)", (first, second)), [(1,)])

    def test_concurrency_direct_sql_staff_overlap(self):
        first = self.shift()
        second = self.shift(start="11:00", end="13:00")
        def assign(conn, shift):
            return svc._run(conn, lambda cur: cur.execute(
                "INSERT INTO shift_staff_assignment VALUES (%s,'haim2897','MAIN_SUPERVISOR')", (shift,)))
        self.race(lambda c: assign(c, first), lambda c: assign(c, second), "overlap")
        self.assertEqual(self.sql("SELECT count(*) FROM shift_staff_assignment WHERE shift_id IN (%s,%s)", (first, second)), [(1,)])

    def test_concurrency_direct_sql_volunteer_overlap(self):
        first = self.shift()
        second = self.shift(start="11:00", end="13:00")
        def request(conn, shift):
            return svc._run(conn, lambda cur: cur.execute(
                "INSERT INTO volunteer_shift(shift_id,volunteer_unikey) VALUES (%s,%s)", (shift, VOLUNTEER)))
        self.race(lambda c: request(c, first), lambda c: request(c, second), "overlap")
        self.assertEqual(self.sql("SELECT count(*) FROM volunteer_shift WHERE shift_id IN (%s,%s)", (first, second)), [(1,)])

    def test_concurrency_mixed_sql_service_booking(self):
        shift = self.shift()
        first = self.session(shift)
        second = self.session(shift, start="10:30", end="11:00")
        def raw_booking(conn):
            return svc._run(conn, lambda cur: cur.execute(
                "INSERT INTO booking(student_unikey,session_id,qr_token) VALUES (%s,%s,'RAW-RACE-TOKEN')",
                (STUDENT, first)))
        self.race(raw_booking, lambda c: svc.book_session(c, STUDENT, second), "active booking")
        self.assertEqual(self.sql("SELECT count(*) FROM booking WHERE student_unikey=%s", (STUDENT,)), [(1,)])

    def test_concurrency_duplicate_opening_is_atomic(self):
        shift = self.opened()
        self.race(lambda c: svc.record_stock_count(c, STAFF, STOCK, "OPENING", 20, shift),
                  lambda c: svc.record_stock_count(c, "part2550", STOCK, "OPENING", 21, shift), "opening count already")
        self.assertEqual(self.sql("SELECT count(*) FROM stock_count WHERE shift_id=%s", (shift,)), [(1,)])
        rows = self.sql("SELECT a.opening_qty,b.counted_qty FROM shift_stock_count a JOIN stock_count b USING(shift_id,stock_number) WHERE a.shift_id=%s", (shift,))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], rows[0][1])

    def test_concurrency_review_decision_once(self):
        shift = self.shift()
        svc.request_volunteer_shift(self.conn, VOLUNTEER, shift)
        self.race(lambda c: svc.review_volunteer_request(c, STAFF, shift, VOLUNTEER, "APPROVED"),
                  lambda c: svc.review_volunteer_request(c, "part2550", shift, VOLUNTEER, "REJECTED"), "pending|review|already")
        self.assertEqual(self.sql("SELECT count(*) FROM volunteer_shift WHERE shift_id=%s AND status IN ('APPROVED','REJECTED') AND reviewed_at IS NOT NULL", (shift,)), [(1,)])

    def test_inventory_closing_first_and_adjustment_first_rollback(self):
        shift = self.opened()
        initial = self.sql("SELECT count(*) FROM stock_count")[0][0]
        with self.assertRaisesRegex(svc.PantryError, "[Oo]pening"):
            svc.record_stock_count(self.conn, STAFF, STOCK, "CLOSING", 15, shift)
        with self.assertRaisesRegex(svc.PantryError, "[Oo]pening"):
            svc.record_stock_adjustment(self.conn, STAFF, shift, STOCK, "RECEIPT", 5, "Delivery")
        self.assertEqual(self.sql("SELECT count(*) FROM stock_count"), [(initial,)])
        self.assertEqual(self.sql("SELECT count(*) FROM shift_stock_count WHERE shift_id=%s", (shift,)), [(0,)])
        self.assertEqual(self.sql("SELECT count(*) FROM stock_adjustment WHERE shift_id=%s", (shift,)), [(0,)])

    def test_inventory_full_reconciliation_and_closed_history(self):
        shift = self.opened()
        svc.record_stock_count(self.conn, STAFF, STOCK, "OPENING", 20, shift, "Actual opening")
        svc.record_stock_adjustment(self.conn, STAFF, shift, STOCK, "RECEIPT", 10, "Delivery")
        svc.record_stock_adjustment(self.conn, STAFF, shift, STOCK, "WASTE", 2, "Damage")
        svc.record_stock_count(self.conn, STAFF, STOCK, "CLOSING", 18, shift)
        self.assertEqual(self.sql("SELECT estimated_dispensed_qty FROM v_shift_stock_report WHERE shift_id=%s", (shift,)), [(None,)])
        self.assertIsNone(svc.report_shift_stock(self.conn, self.future, STAFF)[0][-1])
        svc.set_shift_status(self.conn, STAFF, shift, "CLOSED")
        self.assertEqual(self.sql("SELECT opening_qty,received_qty,waste_qty,closing_qty,estimated_dispensed_qty FROM v_shift_stock_report WHERE shift_id=%s", (shift,)), [(20, 10, 2, 18, 10)])
        self.assertEqual(len(svc.report_shift_stock(self.conn, self.future, STAFF)), 1)
        with self.assertRaisesRegex(svc.PantryError, "CLOSED"):
            svc.record_stock_count(self.conn, STAFF, STOCK, "SPOT_CHECK", 17, shift)
        self.rejected_sql("UPDATE shift_stock_count SET closing_qty=17 WHERE shift_id=%s", (shift,), "CLOSED")

    def test_inventory_duplicate_observations_and_missing_close(self):
        shift = self.opened()
        svc.record_stock_count(self.conn, STAFF, STOCK, "OPENING", 20, shift)
        with self.assertRaises(svc.PantryError):
            svc.record_stock_count(self.conn, STAFF, STOCK, "OPENING", 21, shift)
        with self.assertRaisesRegex(svc.PantryError, "closing"):
            svc.set_shift_status(self.conn, STAFF, shift, "CLOSED")
        svc.record_stock_count(self.conn, STAFF, STOCK, "CLOSING", 15, shift)
        with self.assertRaises(svc.PantryError):
            svc.record_stock_count(self.conn, STAFF, STOCK, "CLOSING", 16, shift)
        self.assertEqual(self.sql("SELECT count(*) FROM stock_count WHERE shift_id=%s", (shift,)), [(2,)])

    def test_inventory_negative_dispensing_cannot_close(self):
        shift = self.opened()
        svc.record_stock_count(self.conn, STAFF, STOCK, "OPENING", 10, shift)
        with self.assertRaisesRegex(svc.PantryError, "exceeds"):
            svc.record_stock_count(self.conn, STAFF, STOCK, "CLOSING", 12, shift)
        self.assertEqual(self.sql("SELECT count(*) FROM stock_count WHERE shift_id=%s", (shift,)), [(1,)])
        # Even an administrative direct write cannot close an invalid balance.
        self.sql("UPDATE shift_stock_count SET closing_qty=12 WHERE shift_id=%s", (shift,))
        with self.assertRaisesRegex(svc.PantryError, "negative"):
            svc.set_shift_status(self.conn, STAFF, shift, "CLOSED")
        self.assertEqual(self.sql("SELECT status FROM pantry_shift WHERE shift_id=%s", (shift,)), [("OPEN",)])
        self.assertEqual(self.sql("SELECT estimated_dispensed_qty FROM v_shift_stock_report WHERE shift_id=%s", (shift,)), [(None,)])

    def test_inventory_invalid_inputs_and_low_stock(self):
        shift = self.opened()
        for kind in ("OPENING", "CLOSING"):
            with self.assertRaises(svc.PantryError):
                svc.record_stock_count(self.conn, STAFF, STOCK, kind, 1)
        with self.assertRaises(svc.PantryError):
            svc.record_stock_count(self.conn, STAFF, STOCK, "SPOT_CHECK", -1)
        svc.record_stock_count(self.conn, STAFF, STOCK, "OPENING", 20, shift)
        with self.assertRaises(svc.PantryError):
            svc.record_stock_adjustment(self.conn, STAFF, shift, STOCK, "WASTE", 0, "Reason")
        with self.assertRaises(svc.PantryError):
            svc.record_stock_adjustment(self.conn, STAFF, shift, STOCK, "WASTE", 1, " ")
        svc.record_stock_count(self.conn, STAFF, STOCK, "SPOT_CHECK", 5)
        rows = svc.report_low_stock(self.conn, STAFF)
        self.assertIn(("Rice 1 kg", 5, 30, "pack"), rows)

    def test_query_error_rolls_back_and_menu_recovers(self):
        with self.assertRaises(svc.PantryError):
            svc._query(self.conn, "SELECT 1/0")
        self.assertEqual(svc._query(self.conn, "SELECT 123"), [(123,)])
        output = io.StringIO()
        with patch.object(cli, "ask", side_effect=["1", "2", "0"]), redirect_stdout(output):
            cli.menu("Recovery", [("Bad date", lambda: svc.list_volunteer_requests(self.conn, "banana", staff_unikey=STAFF)),
                                  ("Good query", lambda: print(svc._query(self.conn, "SELECT 123")[0][0]))])
        self.assertIn("123", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())
        for invalid in ("banana", "2026-02-30", "2026-13-01"):
            with self.assertRaises((svc.PantryError, ValueError)):
                svc.list_volunteer_requests(self.conn, invalid, staff_unikey=STAFF)
        self.assertEqual(svc.list_volunteer_requests(self.conn, self.future, staff_unikey=STAFF), [])

    def test_cli_invalid_staff_role_does_not_write(self):
        captured = []
        with patch.object(cli, "menu", side_effect=lambda title, options: captured.extend(options)):
            cli.staff_menu(self.conn, STAFF)
        action = next(action for label, action in captured if "Assign staff member" in label)
        with patch.object(cli, "ask", side_effect=[str(self.shift()), "haim2897", "9"]):
            with self.assertRaises((svc.PantryError, ValueError)):
                action()
        self.assertEqual(self.sql("SELECT count(*) FROM shift_staff_assignment"), [(6,)])

    def test_cli_volunteer_filter_typo_recovers_in_staff_portal(self):
        output = io.StringIO()
        # 7 = volunteer filter. Invalid date must return before the status prompt.
        # 12 = latest stock, demonstrating a successful subsequent DB action.
        with patch.object(cli, "ask", side_effect=["7", "banana", "12", "0"]), redirect_stdout(output):
            cli.staff_menu(self.conn, STAFF)
        self.assertIn("Invalid input", output.getvalue())
        self.assertIn("Rice 1 kg", output.getvalue())
        self.assertNotIn("Traceback", output.getvalue())

    def test_sql_transaction_demo_and_failure_suite_preserve_all_rows(self):
        tables = [row[0] for row in self.sql("SELECT tablename FROM pg_tables WHERE schemaname='campus_pantry' ORDER BY tablename")]
        def snapshot():
            # These identifiers come exclusively from PostgreSQL's own catalogue.
            from psycopg2 import sql
            return {name: self.sql(sql.SQL("SELECT row_to_json(t)::text FROM {} t ORDER BY row_to_json(t)::text").format(sql.Identifier(name)))
                    for name in tables}
        before = snapshot()
        for filename in ("04_transactions.sql", "06_failure_tests.sql"):
            self.conn.notices.clear()
            source = (support.ROOT / "campus_pantry_sql" / filename).read_text(encoding="utf-8-sig")
            with self.conn.cursor() as cur:
                cur.execute(source)
            self.assertEqual(snapshot(), before, filename + " must roll back all fixture rows")
            if filename == "06_failure_tests.sql":
                self.assertIn("all SQL assertions completed", "".join(self.conn.notices))
                self.assertGreaterEqual(sum("PASS:" in n for n in self.conn.notices), 23)
        # Sequence advancement is intentional PostgreSQL behaviour, not row loss.

    def test_sql_validation_reports_expected_clean_seed(self):
        source = (support.ROOT / "campus_pantry_sql" / "05_validation.sql").read_text(encoding="utf-8-sig")
        source = re.sub(r"--[^\n]*", "", source)
        statements = [s.strip() for s in source.split(";") if s.strip() and not s.strip().upper().startswith("SET ")]
        results = [self.sql(statement) for statement in statements]
        self.assertEqual(len(results), 15)
        self.assertEqual(dict(results[0]), {"person": 29, "student": 17, "booking": 15, "session": 12, "stock_batch": 8, "stock_count": 48})
        for index in (*range(1, 10), 12, 13):
            self.assertEqual(results[index], [], f"Validation check {index + 1}")
        self.assertEqual(len(results[10]), 12)
        self.assertEqual(len(results[11]), 8)
        self.assertEqual(len(results[14]), 10)

    def test_sandbox_ignores_normal_database_configuration(self):
        with patch.dict("os.environ", {"PGDATABASE": "working_database", "PGUSER": "normal_role"}, clear=True):
            with self.assertRaisesRegex(ValueError, "TEST_PGUSER"):
                support.admin_settings()
        with patch.dict("os.environ", {"PGDATABASE": "working_database", "TEST_PGUSER": "explicit_test_role"}, clear=True):
            config = support.admin_settings()
            self.assertEqual(config["dbname"], "postgres")
            self.assertEqual(config["user"], "explicit_test_role")
        with self.assertRaises(ValueError):
            support.Sandbox({}, "working_database")

    def test_twelve_query_groups_thirteen_known_result_sets(self):
        source = (support.ROOT / "campus_pantry_sql" / "03_queries.sql").read_text(encoding="utf-8-sig")
        self.assertEqual(len(re.findall(r"^-- Q\d+\.", source, re.M)), 12)
        source = re.sub(r"--[^\n]*", "", source)
        statements = [s.strip() for s in source.split(";") if s.strip() and not s.strip().upper().startswith("SET ")]
        results = [self.sql(statement) for statement in statements]
        self.assertEqual(len(results), 13)
        self.assertEqual(len(results[0]), 24)
        self.assertEqual(next(row[-1] for row in results[0] if row[0] == 1 and row[4] == STOCK), 20)
        totals = {row[0]: row[3] for row in results[1]}
        self.assertEqual(totals, {1: 57, 2: 24, 3: 35, 4: 28, 5: 25, 6: 25, 7: 25, 8: 18})
        self.assertEqual(len(results[2]), 8)
        self.assertEqual(next(row[3] for row in results[2] if row[0] == STOCK), 60)
        self.assertEqual(results[3], [])
        self.assertEqual([r[5] for r in results[4]], [7, 8] + [0] * 10)
        self.assertEqual(len(results[5]), 1)
        self.assertEqual(results[5][0][:5], (2, STOCK, 92, 90, 2))
        self.assertEqual(results[6], [])
        self.assertEqual(len(results[7]), 6)
        self.assertEqual(len(results[8]), 10)
        self.assertEqual(next(row[3:] for row in results[9] if row[1] == "RICE1"), (100, Decimal("250.00")))
        self.assertEqual(results[10][0][3:], (7, 0, 0, Decimal("0.0")))
        # Add a date-relative expiry fixture; Q11 must include it with exactly 5 days.
        self.sql("INSERT INTO stock_batch(stock_number,product_id,purchase_line_id,received_on,expires_on,received_qty) "
                 "VALUES ('STK-900001',1,1,CURRENT_DATE,CURRENT_DATE+5,10)")
        expiry_rows = self.sql(statements[11])
        self.assertEqual(next(row[-1] for row in expiry_rows if row[0] == "STK-900001"), 5)
        self.assertEqual(results[12], [])
        session = self.session(capacity=2)
        svc.book_session(self.conn, STUDENT, session)
        svc.book_session(self.conn, "emma2002", session)
        near = self.sql(statements[12])
        self.assertEqual(next(row[3:] for row in near if row[1] == session), (2, 2, Decimal("100.0"), 0))


if __name__ == "__main__":
    raise SystemExit("Use tests/run_tests.py so an owned disposable database is created first.")
