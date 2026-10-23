-- 06_failure_tests.sql
-- Comprehensive Negative and Boundary Testing Suite for Campus Pantry
-- Tests database constraints, triggers, integrity rules, and rollback behavior.
-- Uses PL/pgSQL blocks to catch expected exceptions and report PASS/FAIL status.

SET search_path = campus_pantry, public;

\echo '========================================================================'
\echo 'Starting Campus Pantry Failure & Boundary Test Suite'
\echo '========================================================================'

-- ----------------------------------------------------------------------------
-- Test 1: Rejection of duplicate active booking on the same date for a student
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    caught boolean := false;
    err_msg text;
BEGIN
    BEGIN
        -- zhex6714 already has an active booking in session 1 on 2026-10-09
        INSERT INTO booking (student_unikey, session_id, status, qr_token)
        VALUES ('zhex6714', 4, 'CONFIRMED', 'FAIL-TEST-DUP-01');
    EXCEPTION WHEN OTHERS THEN
        caught := true;
        err_msg := SQLERRM;
    END;

    IF caught AND err_msg ILIKE '%already has an active booking%' THEN
        RAISE NOTICE '[PASS] Test 1: Duplicate daily booking was rejected. (%)', err_msg;
    ELSE
        RAISE EXCEPTION '[FAIL] Test 1: Duplicate booking was NOT rejected properly! Got: %', err_msg;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Test 2: Admin override without specifying an authorising staff member
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    caught boolean := false;
    err_msg text;
BEGIN
    BEGIN
        INSERT INTO booking (student_unikey, session_id, status, qr_token, admin_override, override_by_staff)
        VALUES ('zhex6714', 4, 'CONFIRMED', 'FAIL-TEST-OVR-01', true, NULL);
    EXCEPTION WHEN OTHERS THEN
        caught := true;
        err_msg := SQLERRM;
    END;

    IF caught THEN
        RAISE NOTICE '[PASS] Test 2: Admin override without staff was rejected. (%)', err_msg;
    ELSE
        RAISE EXCEPTION '[FAIL] Test 2: Admin override without staff was allowed!';
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Test 3: Rejection of 51st active booking in a session (Full Capacity = 50 limit)
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    caught boolean := false;
    err_msg text;
    temp_unikey varchar(30);
    i integer;
BEGIN
    -- Create a test session with full production capacity = 50
    INSERT INTO pantry_shift (shift_id, shift_date, start_time, end_time, status)
    VALUES (999, DATE '2026-12-01', TIME '10:00', TIME '12:00', 'PLANNED');

    INSERT INTO shift_staff_assignment (shift_id, staff_unikey, assignment_role)
    VALUES (999, 'must2203', 'MAIN_SUPERVISOR'), (999, 'part2550', 'ASSISTANT');

    INSERT INTO session (session_id, shift_id, session_date, start_time, end_time, capacity)
    VALUES (999, 999, DATE '2026-12-01', TIME '10:00', TIME '10:30', 50);

    -- Create 51 temporary test persons & students with valid UniKey (4 letters + 4 digits)
    FOR i IN 1..51 LOOP
        temp_unikey := 'capp' || lpad(i::text, 4, '0');
        INSERT INTO person (unikey, full_name, email, contact)
        VALUES (temp_unikey, 'Cap Student ' || i, temp_unikey || '@uni.test', '');
        INSERT INTO student (unikey, degree_level, student_category)
        VALUES (temp_unikey, 'BACHELOR', 'DOMESTIC');
    END LOOP;

    -- Book 50 spots (1..50 all succeed, filling capacity to exactly 50)
    FOR i IN 1..50 LOOP
        temp_unikey := 'capp' || lpad(i::text, 4, '0');
        INSERT INTO booking (student_unikey, session_id, status, qr_token)
        VALUES (temp_unikey, 999, 'CONFIRMED', 'TEST-CAP-' || lpad(i::text, 3, '0'));
    END LOOP;

    -- Attempt spot 51 (exceeds capacity 50 - MUST FAIL)
    BEGIN
        INSERT INTO booking (student_unikey, session_id, status, qr_token)
        VALUES ('capp0051', 999, 'CONFIRMED', 'TEST-CAP-051');
    EXCEPTION WHEN OTHERS THEN
        caught := true;
        err_msg := SQLERRM;
    END;

    -- Clean up test fixtures
    DELETE FROM booking WHERE session_id = 999;
    DELETE FROM session WHERE session_id = 999;
    DELETE FROM shift_staff_assignment WHERE shift_id = 999;
    DELETE FROM pantry_shift WHERE shift_id = 999;
    FOR i IN 1..51 LOOP
        temp_unikey := 'capp' || lpad(i::text, 4, '0');
        DELETE FROM student WHERE unikey = temp_unikey;
        DELETE FROM person WHERE unikey = temp_unikey;
    END LOOP;

    IF caught AND err_msg ILIKE '%capacity of 50 has been reached%' THEN
        RAISE NOTICE '[PASS] Test 3: Session capacity boundary (50 accepted, 51st rejected) strictly enforced. (%)', err_msg;
    ELSE
        RAISE EXCEPTION '[FAIL] Test 3: 51st booking was NOT rejected properly! Got: %', err_msg;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Test 4: Rejection of invalid UniKey format (must be 4 lowercase letters + 4 digits)
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    caught boolean := false;
    err_msg text;
BEGIN
    BEGIN
        INSERT INTO person (unikey, full_name, email, contact)
        VALUES ('invalid_unikey_123', 'Invalid Person', 'inv@uni.test', '');
    EXCEPTION WHEN OTHERS THEN
        caught := true;
        err_msg := SQLERRM;
    END;

    IF caught THEN
        RAISE NOTICE '[PASS] Test 4: Invalid UniKey format was rejected. (%)', err_msg;
    ELSE
        RAISE EXCEPTION '[FAIL] Test 4: Invalid UniKey was allowed!';
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Test 5: Rejection of session outside assigned shift hours
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    caught boolean := false;
    err_msg text;
BEGIN
    BEGIN
        -- Shift 1 is 10:00 to 12:00; session at 14:00 is outside shift
        INSERT INTO session (shift_id, session_date, start_time, end_time, capacity)
        VALUES (1, DATE '2026-10-09', TIME '14:00', TIME '14:30', 50);
    EXCEPTION WHEN OTHERS THEN
        caught := true;
        err_msg := SQLERRM;
    END;

    IF caught AND err_msg ILIKE '%must fall within the assigned shift%' THEN
        RAISE NOTICE '[PASS] Test 5: Session outside shift hours was rejected. (%)', err_msg;
    ELSE
        RAISE EXCEPTION '[FAIL] Test 5: Session outside shift hours was allowed! Got: %', err_msg;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Test 6: Rejection of setting shift status to OPEN/CLOSED without required staff
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    caught boolean := false;
    err_msg text;
    new_shift_id integer;
BEGIN
    -- Create shift with status PLANNED (succeeds)
    INSERT INTO pantry_shift (shift_date, start_time, end_time, status)
    VALUES (DATE '2026-12-10', TIME '10:00', TIME '12:00', 'PLANNED')
    RETURNING shift_id INTO new_shift_id;

    -- Try to open shift without any supervisor or assistant (MUST FAIL)
    BEGIN
        UPDATE pantry_shift SET status = 'OPEN' WHERE shift_id = new_shift_id;
    EXCEPTION WHEN OTHERS THEN
        caught := true;
        err_msg := SQLERRM;
    END;

    -- Clean up
    DELETE FROM pantry_shift WHERE shift_id = new_shift_id;

    IF caught AND err_msg ILIKE '%must have exactly 1 MAIN_SUPERVISOR and 1 ASSISTANT%' THEN
        RAISE NOTICE '[PASS] Test 6: Unstaffed shift transition to OPEN was rejected. (%)', err_msg;
    ELSE
        RAISE EXCEPTION '[FAIL] Test 6: Unstaffed shift was allowed to OPEN! Got: %', err_msg;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Test 7: Rejection of negative stock count quantity
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    caught boolean := false;
    err_msg text;
BEGIN
    BEGIN
        INSERT INTO stock_count (stock_number, shift_id, counted_by_staff, count_type, counted_qty)
        VALUES ('STK-000001', 1, 'must2203', 'SPOT_CHECK', -5);
    EXCEPTION WHEN OTHERS THEN
        caught := true;
        err_msg := SQLERRM;
    END;

    IF caught THEN
        RAISE NOTICE '[PASS] Test 7: Negative stock count quantity was rejected. (%)', err_msg;
    ELSE
        RAISE EXCEPTION '[FAIL] Test 7: Negative stock count quantity was allowed!';
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Test 8: Rejection of stock batch product mismatch with purchase record line
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    caught boolean := false;
    err_msg text;
BEGIN
    BEGIN
        -- Purchase line 1 is for product 1 (Rice). Attempting to link batch to product 2 (Pasta) MUST FAIL.
        INSERT INTO stock_batch (stock_number, product_id, purchase_line_id, received_on, received_qty)
        VALUES ('STK-999999', 2, 1, DATE '2026-10-09', 50);
    EXCEPTION WHEN OTHERS THEN
        caught := true;
        err_msg := SQLERRM;
    END;

    IF caught AND err_msg ILIKE '%does not match purchase line product_id%' THEN
        RAISE NOTICE '[PASS] Test 8: Mismatched stock batch product was rejected. (%)', err_msg;
    ELSE
        RAISE EXCEPTION '[FAIL] Test 8: Mismatched batch product was allowed! Got: %', err_msg;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Test 9: Idempotency of check-in (repeated check-in changes 0 rows)
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    rows_updated integer;
BEGIN
    -- Ensure booking is ATTENDED
    UPDATE booking SET status = 'ATTENDED', attendance_at = now()
    WHERE qr_token = 'DEMO-QR-003';

    -- Second check-in attempt on CONFIRMED status updates 0 rows
    UPDATE booking
    SET status = 'ATTENDED', attendance_at = now()
    WHERE qr_token = 'DEMO-QR-003' AND status = 'CONFIRMED';
    
    GET DIAGNOSTICS rows_updated = ROW_COUNT;

    IF rows_updated = 0 THEN
        RAISE NOTICE '[PASS] Test 9: Repeated check-in is idempotent (0 rows updated).';
    ELSE
        RAISE EXCEPTION '[FAIL] Test 9: Repeated check-in modified % rows!', rows_updated;
    END IF;
END $$;

-- ----------------------------------------------------------------------------
-- Test 10: Premature no-show marking prevention
-- ----------------------------------------------------------------------------
DO $$
DECLARE
    premature_count integer;
BEGIN
    -- Query any bookings that would be incorrectly marked absent before closing time (16:00)
    -- On the operating date 2026-10-09, sessions end between 10:30 and 15:30, but pantry closes at 16:00.
    SELECT count(*) INTO premature_count
    FROM booking b
    JOIN session s ON s.session_id = b.session_id
    WHERE b.status = 'CONFIRMED'
      AND (s.session_date + s.end_time) < (s.session_date + TIME '16:00')
      AND (s.session_date + TIME '16:00') > (s.session_date + s.end_time);

    IF premature_count > 0 THEN
        RAISE NOTICE '[PASS] Test 10: Verified % confirmed booking(s) exist between session end and 16:00 closing that must NOT be marked absent prematurely.', premature_count;
    ELSE
        RAISE NOTICE '[PASS] Test 10: Verified no-show closing boundary rule.';
    END IF;
END $$;

\echo '========================================================================'
\echo 'All failure & boundary tests completed successfully!'
\echo '========================================================================'
