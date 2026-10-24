-- Database regression checks: run after 01 + 02 in a disposable showcase database.
-- Assertions verify the specific SQLSTATE and message, not merely any failure.
-- All fixture rows and the temporary helper are rolled back. Identity sequences advance.
-- Concurrency and service tests are in ../tests (separate connections).
BEGIN;
SET LOCAL search_path = campus_pantry, public;

CREATE FUNCTION pg_temp.expect_error(label text, statement text, expected_state text, fragment text)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE actual_state text; actual_message text;
BEGIN
    BEGIN
        EXECUTE statement;
    EXCEPTION WHEN OTHERS THEN
        GET STACKED DIAGNOSTICS actual_state=RETURNED_SQLSTATE, actual_message=MESSAGE_TEXT;
    END;
    IF actual_state IS DISTINCT FROM expected_state
       OR position(fragment IN coalesce(actual_message,''))=0 THEN
        RAISE EXCEPTION 'FAIL %: expected % containing %, got %: %',
            label,expected_state,fragment,actual_state,actual_message;
    END IF;
    RAISE NOTICE 'PASS: %',label;
END $$;

DO $$
DECLARE
    sh integer; overlap_sh integer; s1 integer; s2 integer; b1 bigint;
    test_date date := CURRENT_DATE+45;
    i integer; key varchar; affected integer;
BEGIN
    INSERT INTO person(unikey,full_name,email) VALUES
        ('tsta9001','Test supervisor','supervisor@example.test'),
        ('tstb9001','Test assistant','assistant@example.test'),
        ('tstv9001','Test volunteer','volunteer@example.test');
    INSERT INTO staff(unikey,staff_code) VALUES
        ('tsta9001','SQL-TEST-SUPERVISOR'),('tstb9001','SQL-TEST-ASSISTANT');
    INSERT INTO volunteer(unikey) VALUES('tstv9001');
    FOR i IN 1..51 LOOP
        key:='tstq'||lpad(i::text,4,'0');
        INSERT INTO person(unikey,full_name,email) VALUES(key,'Capacity test student',key||'@example.test');
        INSERT INTO student(unikey) VALUES(key);
    END LOOP;
    INSERT INTO pantry_shift(shift_date,start_time,end_time)
        VALUES(test_date,'10:00','12:00') RETURNING shift_id INTO sh;
    INSERT INTO pantry_shift(shift_date,start_time,end_time)
        VALUES(test_date,'10:30','12:30') RETURNING shift_id INTO overlap_sh;
    INSERT INTO session(shift_id,session_date,start_time,end_time,capacity)
        VALUES(sh,test_date,'10:00','10:30',50) RETURNING session_id INTO s1;
    INSERT INTO session(shift_id,session_date,start_time,end_time,capacity)
        VALUES(sh,test_date,'10:30','11:00',50) RETURNING session_id INTO s2;

    PERFORM pg_temp.expect_error('opening requires staffing',
        format('UPDATE pantry_shift SET status=''OPEN'' WHERE shift_id=%s',sh),
        'P0001','must have exactly 1 MAIN_SUPERVISOR and 1 ASSISTANT');
    INSERT INTO shift_staff_assignment VALUES
        (sh,'tsta9001','MAIN_SUPERVISOR'),(sh,'tstb9001','ASSISTANT');
    PERFORM pg_temp.expect_error('staff overlap',
        format('INSERT INTO shift_staff_assignment VALUES(%s,''tsta9001'',''MAIN_SUPERVISOR'')',overlap_sh),
        'P0001','already assigned to an overlapping shift');
    INSERT INTO volunteer_shift(shift_id,volunteer_unikey) VALUES(sh,'tstv9001');
    PERFORM pg_temp.expect_error('volunteer overlap',
        format('INSERT INTO volunteer_shift(shift_id,volunteer_unikey) VALUES(%s,''tstv9001'')',overlap_sh),
        'P0001','overlapping shift request or assignment');
    PERFORM pg_temp.expect_error('session containment',
        format('INSERT INTO session(shift_id,session_date,start_time,end_time) VALUES(%s,%L,''13:00'',''13:30'')',sh,test_date),
        'P0001','must fall within the assigned shift');
    PERFORM pg_temp.expect_error('session overlap',
        format('INSERT INTO session(shift_id,session_date,start_time,end_time) VALUES(%s,%L,''10:15'',''10:45'')',sh,test_date),
        'P0001','Session times cannot overlap');

    FOR i IN 1..50 LOOP
        key:='tstq'||lpad(i::text,4,'0');
        INSERT INTO booking(student_unikey,session_id,qr_token)
            VALUES(key,s1,'SQL-TEST-CAPACITY-'||i);
    END LOOP;
    IF (SELECT count(*) FROM booking WHERE session_id=s1)<>50 THEN
        RAISE EXCEPTION 'FAIL: expected exactly 50 accepted bookings';
    END IF;
    PERFORM pg_temp.expect_error('capacity boundary: 50 accepted, 51st rejected',
        format('INSERT INTO booking(student_unikey,session_id,qr_token) VALUES(''tstq0051'',%s,''SQL-TEST-51'')',s1),
        'P0001','Session capacity of 50 has been reached');
    PERFORM pg_temp.expect_error('same student/day duplicate',
        format('INSERT INTO booking(student_unikey,session_id,qr_token) VALUES(''tstq0001'',%s,''SQL-TEST-DUPLICATE'')',s2),
        'P0001','already has an active booking on this date');
    INSERT INTO booking(student_unikey,session_id,qr_token,admin_override,override_by_staff,override_reason)
        VALUES('tstq0001',s2,'SQL-TEST-OVERRIDE',true,'tsta9001','Test welfare exception')
        RETURNING booking_id INTO b1;
    PERFORM pg_temp.expect_error('override audit reason cannot be cleared on update',
        format('UPDATE booking SET override_reason='' '' WHERE booking_id=%s',b1),
        'P0001','must include a valid reason');
    PERFORM pg_temp.expect_error('override removal revalidates daily rule',
        format('UPDATE booking SET admin_override=false,override_by_staff=NULL,override_reason=NULL WHERE booking_id=%s',b1),
        'P0001','already has an active booking on this date');
    PERFORM pg_temp.expect_error('attendance requires its timestamp',
        format('UPDATE booking SET status=''ATTENDED'' WHERE booking_id=%s',b1),
        '23514','booking_attendance_consistency');
    UPDATE booking SET status='ATTENDED',attendance_at=transaction_timestamp()
        WHERE booking_id=b1 AND status='CONFIRMED';
    UPDATE booking SET status='ATTENDED',attendance_at=transaction_timestamp()
        WHERE booking_id=b1 AND status='CONFIRMED';
    GET DIAGNOSTICS affected=ROW_COUNT;
    IF affected<>0 THEN RAISE EXCEPTION 'FAIL: second check-in changed a row'; END IF;
    RAISE NOTICE 'PASS: repeat check-in is idempotent';
    PERFORM pg_temp.expect_error('capacity cannot undercut existing bookings',
        format('UPDATE session SET capacity=49 WHERE session_id=%s',s1),
        'P0001','Capacity cannot be reduced below 50');
    PERFORM pg_temp.expect_error('shift schedule is immutable',
        format('UPDATE pantry_shift SET end_time=''13:00'' WHERE shift_id=%s',sh),
        'P0001','Shift date and times are immutable');
    PERFORM pg_temp.expect_error('session schedule is immutable',
        format('UPDATE session SET end_time=''10:45'' WHERE session_id=%s',s1),
        'P0001','Session schedule is immutable');

    PERFORM pg_temp.expect_error('invalid UniKey',
        'INSERT INTO person(unikey,full_name,email) VALUES(''wrong'',''Bad key'',''bad@example.test'')',
        '23514','person_unikey_check');
    PERFORM pg_temp.expect_error('negative physical stock count',
        format('INSERT INTO stock_count(stock_number,shift_id,counted_by_staff,count_type,counted_qty) VALUES(''STK-000001'',%s,''tsta9001'',''SPOT_CHECK'',-1)',sh),
        '23514','stock_count_counted_qty_check');
    PERFORM pg_temp.expect_error('batch product must match source purchase line',
        'INSERT INTO stock_batch(stock_number,product_id,purchase_line_id,received_on,received_qty) VALUES(''STK-999999'',2,1,CURRENT_DATE,1)',
        '23503','stock_batch_purchase_product_fkey');
    PERFORM pg_temp.expect_error('purchase line parent edit cannot break batch product',
        'UPDATE purchase_record_line SET product_id=2 WHERE purchase_line_id=1',
        '23503','stock_batch_purchase_product_fkey');

    UPDATE pantry_shift SET status='OPEN' WHERE shift_id=sh;
    PERFORM pg_temp.expect_error('open shift retains required staff',
        format('DELETE FROM shift_staff_assignment WHERE shift_id=%s AND assignment_role=''ASSISTANT''',sh),
        'P0001','Staff assignments can only change while a shift is PLANNED');
    INSERT INTO shift_stock_count(shift_id,stock_number,opening_qty)
        VALUES(sh,'STK-000001',10);
    PERFORM pg_temp.expect_error('closing requires physical closing count',
        format('UPDATE pantry_shift SET status=''CLOSED'' WHERE shift_id=%s',sh),
        'P0001','needs a closing count before closing');
    UPDATE shift_stock_count SET closing_qty=11 WHERE shift_id=sh AND stock_number='STK-000001';
    PERFORM pg_temp.expect_error('closing rejects negative reconciliation',
        format('UPDATE pantry_shift SET status=''CLOSED'' WHERE shift_id=%s',sh),
        'P0001','cannot have negative estimated dispensing');
    UPDATE shift_stock_count SET closing_qty=5 WHERE shift_id=sh AND stock_number='STK-000001';
    UPDATE pantry_shift SET status='CLOSED' WHERE shift_id=sh;
    PERFORM pg_temp.expect_error('closed shift inventory is immutable',
        format('UPDATE shift_stock_count SET closing_qty=4 WHERE shift_id=%s',sh),
        'P0001','Inventory records cannot change on a CLOSED shift');
    PERFORM pg_temp.expect_error('closed shifts cannot reopen',
        format('UPDATE pantry_shift SET status=''OPEN'' WHERE shift_id=%s',sh),
        'P0001','Shift transitions must follow PLANNED to OPEN to CLOSED');
    RAISE NOTICE 'PASS: all SQL assertions completed; fixture data will be rolled back';
END $$;
ROLLBACK;
