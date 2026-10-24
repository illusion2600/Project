-- 05_validation.sql
SET search_path = campus_pantry, public;

-- 1. Inspect core counts.
SELECT 'person' AS table_name, count(*) FROM person
UNION ALL SELECT 'student', count(*) FROM student
UNION ALL SELECT 'booking', count(*) FROM booking
UNION ALL SELECT 'session', count(*) FROM session
UNION ALL SELECT 'stock_batch', count(*) FROM stock_batch
UNION ALL SELECT 'stock_count', count(*) FROM stock_count;

-- 2. Open/completed shifts must have exactly one supervisor and one assistant.
-- Planned shifts may be awaiting staffing.
SELECT sh.shift_id,
       count(*) FILTER (WHERE a.assignment_role='MAIN_SUPERVISOR') AS supervisors,
       count(*) FILTER (WHERE a.assignment_role='ASSISTANT') AS assistants
FROM pantry_shift sh
LEFT JOIN shift_staff_assignment a ON a.shift_id = sh.shift_id
WHERE sh.status IN ('OPEN','CLOSED')
GROUP BY sh.shift_id
HAVING count(*) FILTER (WHERE a.assignment_role='MAIN_SUPERVISOR') <> 1
    OR count(*) FILTER (WHERE a.assignment_role='ASSISTANT') <> 1;

-- 3. Find sessions whose active bookings exceed capacity (should return no rows).
SELECT s.session_id, s.capacity, count(b.booking_id) AS active_bookings
FROM session s LEFT JOIN booking b ON b.session_id=s.session_id AND b.status <> 'CANCELLED'
GROUP BY s.session_id, s.capacity
HAVING count(b.booking_id) > s.capacity;

-- 4. Find students with more than one active booking on the same date.
-- Admin-authorised overrides are surfaced for review rather than silently ignored.
SELECT b.student_unikey, s.session_date, count(*) AS booking_count,
       bool_or(b.admin_override) AS any_admin_override
FROM booking b JOIN session s ON s.session_id=b.session_id
WHERE b.status <> 'CANCELLED'
GROUP BY b.student_unikey, s.session_date
HAVING count(*) > 1;

-- 5. Find invalid attendance status/timestamp combinations (should return no rows).
SELECT booking_id, status, attendance_at
FROM booking
WHERE (status='ATTENDED' AND attendance_at IS NULL)
   OR (status<>'ATTENDED' AND attendance_at IS NOT NULL);

-- 6. Find batches with no count history.

SELECT sb.stock_number
FROM stock_batch sb
WHERE NOT EXISTS (SELECT 1 FROM stock_count sc WHERE sc.stock_number=sb.stock_number);

-- 7. Find batches whose last known count is negative (should return no rows).
SELECT * FROM v_latest_stock_count WHERE last_counted_qty < 0;

-- 8. Check stock arithmetic for completed shifts.
SELECT *
FROM v_shift_stock_report
WHERE estimated_dispensed_qty < 0;

-- 9. Verify StockNumber format.
SELECT stock_number
FROM stock_batch
WHERE stock_number !~ '^STK-[0-9]{6}$';

-- 10. Confirm all session times fit their assigned shifts.
SELECT s.session_id, s.session_date, s.start_time, s.end_time, sh.shift_id
FROM session s JOIN pantry_shift sh ON sh.shift_id=s.shift_id
WHERE s.session_date <> sh.shift_date
   OR s.start_time < sh.start_time
   OR s.end_time > sh.end_time;

-- 11. Inspect booking attendance summary.
SELECT * FROM v_booking_attendance ORDER BY session_date, start_time;

-- 12. Inspect latest stock count summary.
SELECT * FROM v_latest_stock_count ORDER BY product_name, stock_number;

-- 13. Closed shifts with missing closing counts (should return no rows).
SELECT s.shift_id, s.stock_number
FROM shift_stock_count s JOIN pantry_shift sh USING(shift_id)
WHERE sh.status='CLOSED' AND s.closing_qty IS NULL;

-- 14. A batch must match its source purchase line even after parent edits.
SELECT b.stock_number FROM stock_batch b JOIN purchase_record_line l USING(purchase_line_id)
WHERE b.product_id<>l.product_id;

-- 15. Inspect active volunteer requests and decisions, including their reviewer.
SELECT shift_id,volunteer_unikey,status,reviewed_by_staff,reviewed_at
FROM volunteer_shift ORDER BY shift_id,volunteer_unikey;
