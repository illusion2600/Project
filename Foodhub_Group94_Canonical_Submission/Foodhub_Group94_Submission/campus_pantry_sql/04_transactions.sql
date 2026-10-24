-- Transaction demonstrations for the university showcase.
-- Run against a fresh seeded disposable database. All changes are rolled back.
-- Sequence values may advance: PostgreSQL sequences intentionally do not roll back.
-- Real operations should use the CLI, which also checks actor identity and local time.
BEGIN;
SET LOCAL search_path = campus_pantry, public;

DO $$
DECLARE
    demo_shift integer;
    first_session integer;
    second_session integer;
    demo_booking bigint;
    changed integer;
    demo_date date := CURRENT_DATE + 30;
BEGIN
    -- A. Create a planned shift and its non-overlapping sessions, then staff it.
    INSERT INTO pantry_shift(shift_date,start_time,end_time)
    VALUES(demo_date,'10:00','12:00') RETURNING shift_id INTO demo_shift;
    INSERT INTO session(shift_id,session_date,start_time,end_time)
    VALUES(demo_shift,demo_date,'10:00','10:30') RETURNING session_id INTO first_session;
    INSERT INTO session(shift_id,session_date,start_time,end_time)
    VALUES(demo_shift,demo_date,'10:30','11:00') RETURNING session_id INTO second_session;
    INSERT INTO shift_staff_assignment(shift_id,staff_unikey,assignment_role) VALUES
    (demo_shift,'must2203','MAIN_SUPERVISOR'),(demo_shift,'part2550','ASSISTANT');

    -- B. Booking and a recorded welfare override are in this same transaction.
    -- validate_booking locks student then session for concurrent capacity safety.
    INSERT INTO booking(student_unikey,session_id,qr_token)
    VALUES('alex1001',first_session,'TRANSACTION-DEMO-PRIMARY') RETURNING booking_id INTO demo_booking;
    INSERT INTO booking(student_unikey,session_id,qr_token,admin_override,override_by_staff,override_reason)
    VALUES('alex1001',second_session,'TRANSACTION-DEMO-OVERRIDE',true,'must2203','Demonstration welfare exception');

    -- C. A physical opening count initializes the summary. Closing never invents zero.
    INSERT INTO stock_count(stock_number,shift_id,counted_by_staff,count_type,counted_qty)
    VALUES('STK-000001',demo_shift,'must2203','OPENING',20);
    INSERT INTO shift_stock_count(shift_id,stock_number,opening_qty)
    VALUES(demo_shift,'STK-000001',20);
    UPDATE pantry_shift SET status='OPEN' WHERE shift_id=demo_shift;

    -- D. Predicate-based check-in is idempotent. The CLI additionally enforces date/time.
    UPDATE booking SET status='ATTENDED',attendance_at=transaction_timestamp()
    WHERE booking_id=demo_booking AND status='CONFIRMED';
    GET DIAGNOSTICS changed=ROW_COUNT;
    IF changed<>1 THEN RAISE EXCEPTION 'Expected one first check-in'; END IF;
    UPDATE booking SET status='ATTENDED',attendance_at=transaction_timestamp()
    WHERE booking_id=demo_booking AND status='CONFIRMED';
    GET DIAGNOSTICS changed=ROW_COUNT;
    IF changed<>0 THEN RAISE EXCEPTION 'Repeated check-in must change zero rows'; END IF;

    -- E. One physical closing event and summary change are committed or rolled back together.
    INSERT INTO stock_count(stock_number,shift_id,counted_by_staff,count_type,counted_qty)
    VALUES('STK-000001',demo_shift,'must2203','CLOSING',15);
    UPDATE shift_stock_count SET closing_qty=15 WHERE shift_id=demo_shift AND stock_number='STK-000001';
    UPDATE pantry_shift SET status='CLOSED' WHERE shift_id=demo_shift;
    IF (SELECT estimated_dispensed_qty FROM v_shift_stock_report
        WHERE shift_id=demo_shift AND stock_number='STK-000001')<>5 THEN
        RAISE EXCEPTION 'Expected estimated dispensing of five units';
    END IF;
    RAISE NOTICE 'PASS: atomic booking, override, idempotent check-in, stock reconciliation and lifecycle';
END $$;
ROLLBACK;
