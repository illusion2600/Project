-- 04_transactions.sql
-- Comprehensive Transaction Demonstrations for Campus Pantry
-- Demonstrates ACID properties, concurrency safeguards, idempotency, and rollback.
-- All demonstration transactions run atomically within a test transaction block
-- and are safely rolled back at the end, leaving the database completely clean.

BEGIN;
SET LOCAL search_path = campus_pantry, public;

DO $$
DECLARE
    demo_shift integer;
    first_session integer;
    second_session integer;
    demo_booking bigint;
    override_booking bigint;
    cancel_booking bigint;
    changed integer;
    initial_avail integer;
    after_cancel_avail integer;
    demo_date date := CURRENT_DATE + 30;
BEGIN
    -- ------------------------------------------------------------------------
    -- Setup: Isolated shift and sessions for the transaction demonstrations
    -- ------------------------------------------------------------------------
    INSERT INTO pantry_shift (shift_date, start_time, end_time, status)
    VALUES (demo_date, TIME '10:00', TIME '12:00', 'PLANNED')
    RETURNING shift_id INTO demo_shift;

    INSERT INTO shift_staff_assignment (shift_id, staff_unikey, assignment_role)
    VALUES (demo_shift, 'must2203', 'MAIN_SUPERVISOR'), (demo_shift, 'part2550', 'ASSISTANT');

    INSERT INTO session (shift_id, session_date, start_time, end_time, capacity)
    VALUES (demo_shift, demo_date, TIME '10:00', TIME '10:30', 50)
    RETURNING session_id INTO first_session;

    INSERT INTO session (shift_id, session_date, start_time, end_time, capacity)
    VALUES (demo_shift, demo_date, TIME '10:30', TIME '11:00', 50)
    RETURNING session_id INTO second_session;

    -- ========================================================================
    -- Transaction A: Booking Creation (Standard Booking & Admin Override)
    -- ========================================================================
    -- A1. Standard Booking: student 'alex1001' books into first_session.
    -- Row-level locking on student and session prevents concurrent race conditions.
    INSERT INTO booking (student_unikey, session_id, status, qr_token)
    VALUES ('alex1001', first_session, 'CONFIRMED', 'DEMO-TXN-QR-001')
    RETURNING booking_id INTO demo_booking;

    -- A2. Admin Override Booking: student 'alex1001' already has an active booking today.
    -- Normal booking would be rejected. Explicit admin_override with staff attribution allows it.
    INSERT INTO booking (student_unikey, session_id, status, qr_token, admin_override, override_by_staff, override_reason)
    VALUES ('alex1001', second_session, 'CONFIRMED', 'DEMO-TXN-QR-OVR', true, 'must2203', 'Emergency welfare food-parcel exception')
    RETURNING booking_id INTO override_booking;

    RAISE NOTICE '[PASS] Transaction A: Standard and admin-override bookings created atomically.';

    -- ========================================================================
    -- Transaction B: Front-Desk QR Check-in (Predicate-based & Idempotent)
    -- ========================================================================
    -- First scan: transitions CONFIRMED -> ATTENDED and records timestamp.
    UPDATE booking
    SET status = 'ATTENDED', attendance_at = clock_timestamp()
    WHERE qr_token = 'DEMO-TXN-QR-001' AND status = 'CONFIRMED';
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> 1 THEN
        RAISE EXCEPTION 'Transaction B failed: Expected 1 row updated on first check-in, got %', changed;
    END IF;

    -- Repeated scan: condition status = 'CONFIRMED' ensures exactly 0 rows modified.
    UPDATE booking
    SET status = 'ATTENDED', attendance_at = clock_timestamp()
    WHERE qr_token = 'DEMO-TXN-QR-001' AND status = 'CONFIRMED';
    GET DIAGNOSTICS changed = ROW_COUNT;
    IF changed <> 0 THEN
        RAISE EXCEPTION 'Transaction B failed: Repeated check-in must be idempotent (0 rows), got %', changed;
    END IF;

    RAISE NOTICE '[PASS] Transaction B: Front-desk QR check-in verified atomic and idempotent.';

    -- ========================================================================
    -- Transaction C: Booking Cancellation (Instant Capacity Restoration)
    -- ========================================================================
    INSERT INTO booking (student_unikey, session_id, status, qr_token)
    VALUES ('susa8796', first_session, 'CONFIRMED', 'DEMO-TXN-QR-CANCEL')
    RETURNING booking_id INTO cancel_booking;

    SELECT spaces_remaining INTO initial_avail
    FROM v_booking_attendance WHERE session_id = first_session;

    UPDATE booking
    SET status = 'CANCELLED', attendance_at = NULL
    WHERE booking_id = cancel_booking AND status = 'CONFIRMED';

    SELECT spaces_remaining INTO after_cancel_avail
    FROM v_booking_attendance WHERE session_id = first_session;

    IF after_cancel_avail <> initial_avail + 1 THEN
        RAISE EXCEPTION 'Transaction C failed: Cancellation did not restore capacity. Before: %, After: %',
            initial_avail, after_cancel_avail;
    END IF;

    RAISE NOTICE '[PASS] Transaction C: Cancellation successfully freed capacity.';

    -- ========================================================================
    -- Transaction D: Mark No-Shows After Operating Day Close (16:00)
    -- ========================================================================
    -- Past confirmed bookings whose operating day has closed (after 16:00) are marked ABSENT.
    -- Demonstrates safe boundary condition without prematurely cancelling bookings.
    UPDATE booking b
    SET status = 'ABSENT'
    FROM session s
    WHERE s.session_id = b.session_id
      AND b.status = 'CONFIRMED'
      AND s.session_date <= CURRENT_DATE
      AND (s.session_date + TIME '16:00') <= localtimestamp;

    -- ========================================================================
    -- Transaction E: Atomic Shift Stock Count Handover & Reconciliation
    -- ========================================================================
    -- Physical count event and summary are committed together.
    INSERT INTO stock_count (stock_number, shift_id, counted_by_staff, count_type, counted_qty, notes)
    VALUES ('STK-000001', demo_shift, 'must2203', 'OPENING', 50, 'Shift opening count');

    INSERT INTO shift_stock_count (shift_id, stock_number, opening_qty)
    VALUES (demo_shift, 'STK-000001', 50);

    UPDATE pantry_shift SET status = 'OPEN' WHERE shift_id = demo_shift;

    INSERT INTO stock_count (stock_number, shift_id, counted_by_staff, count_type, counted_qty, notes)
    VALUES ('STK-000001', demo_shift, 'must2203', 'CLOSING', 38, 'Shift closing count');

    UPDATE shift_stock_count
    SET closing_qty = 38
    WHERE shift_id = demo_shift AND stock_number = 'STK-000001';

    UPDATE pantry_shift SET status = 'CLOSED' WHERE shift_id = demo_shift;

    IF (SELECT estimated_dispensed_qty FROM v_shift_stock_report
        WHERE shift_id = demo_shift AND stock_number = 'STK-000001') <> 12 THEN
        RAISE EXCEPTION 'Transaction E failed: Expected estimated dispensing of 12';
    END IF;

    RAISE NOTICE '[PASS] Transaction E: Stock count event and shift summary reconciled atomically.';

    -- ========================================================================
    -- Transaction F: Transaction Rollback Demonstration
    -- ========================================================================
    -- Demonstrates atomicity: issuing ROLLBACK restores the database to prior state.
    RAISE NOTICE '[PASS] Transaction F: All transaction steps succeeded; issuing complete ROLLBACK.';
END $$;

ROLLBACK;
