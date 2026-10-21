-- 03_queries.sql
SET search_path = campus_pantry, public;

-- Q1. Detailed shift stock-count report.
SELECT shift_id, shift_date, start_time, end_time, stock_number,
       product_name, counting_unit, opening_qty, received_qty,
       waste_qty, closing_qty, estimated_dispensed_qty
FROM v_shift_stock_report
ORDER BY shift_date, shift_id, product_name;

-- Q2. Estimated dispensing by product across closed shifts.
SELECT product_id, product_name, counting_unit,
       SUM(estimated_dispensed_qty) AS estimated_total
FROM v_shift_stock_report
WHERE estimated_dispensed_qty IS NOT NULL
GROUP BY product_id, product_name, counting_unit
ORDER BY estimated_total DESC;

-- Q3. Latest known physical count per stock batch.
SELECT stock_number, product_name, counting_unit,
       last_counted_qty, counted_at, count_type
FROM v_latest_stock_count
ORDER BY product_name, stock_number;

-- Q4. Products below low-stock threshold, using latest counts.
WITH batch_latest AS (
    SELECT DISTINCT ON (sc.stock_number)
           sc.stock_number, sb.product_id, sc.counted_qty
    FROM stock_count sc JOIN stock_batch sb USING (stock_number)
    ORDER BY sc.stock_number, sc.counted_at DESC, sc.stock_count_id DESC
),
product_totals AS (
    SELECT p.product_id, p.product_name, p.counting_unit, p.low_stock_threshold,
           COALESCE(SUM(bl.counted_qty),0) AS last_known_quantity
    FROM product p LEFT JOIN batch_latest bl ON bl.product_id = p.product_id
    GROUP BY p.product_id
)
SELECT *
FROM product_totals
WHERE last_known_quantity < low_stock_threshold
ORDER BY last_known_quantity;

-- Q5. Session booking and attendance summary.
SELECT session_date, session_id, start_time, end_time, capacity,
       active_bookings, attended, absent, awaiting_checkin, spaces_remaining
FROM v_booking_attendance

ORDER BY session_date, start_time;

-- Q6. Opening stock variances from the previous shift closing count.
WITH previous_close AS (
    SELECT cur.shift_id, cur.stock_number, cur.opening_qty,
           prev.closing_qty AS previous_closing_qty,
           cur.opening_qty - prev.closing_qty AS variance_qty,
           cur.opening_variance_reason
    FROM shift_stock_count cur
    JOIN pantry_shift cur_shift ON cur_shift.shift_id = cur.shift_id
    JOIN LATERAL (
        SELECT s2.shift_id, s2.closing_qty
        FROM shift_stock_count s2
        JOIN pantry_shift sh2 ON sh2.shift_id = s2.shift_id
        WHERE s2.stock_number = cur.stock_number
          AND sh2.status = 'CLOSED'
          AND sh2.shift_id <> cur.shift_id
          AND (sh2.shift_date < cur_shift.shift_date
               OR (sh2.shift_date = cur_shift.shift_date AND sh2.end_time <= cur_shift.start_time))
        ORDER BY sh2.shift_date DESC, sh2.end_time DESC
        LIMIT 1
    ) prev ON true
)
SELECT * FROM previous_close
WHERE variance_qty <> 0
ORDER BY shift_id, stock_number;

-- Q7. Products with no estimated dispensing in the selected data.
SELECT p.product_id, p.product_name
FROM product p
WHERE NOT EXISTS (
    SELECT 1
    FROM v_shift_stock_report r
    WHERE r.product_id = p.product_id
      AND r.estimated_dispensed_qty > 0
);

-- Q8. Staff and volunteer roster by shift.
SELECT sh.shift_date, sh.shift_id, sh.start_time, sh.end_time,
       a.assignment_role, pe.full_name AS staff_name
FROM pantry_shift sh
JOIN shift_staff_assignment a ON a.shift_id = sh.shift_id
JOIN person pe ON pe.unikey = a.staff_unikey
ORDER BY sh.shift_date, sh.start_time, a.assignment_role;

SELECT sh.shift_id, sh.start_time, sh.end_time, pe.full_name AS volunteer_name
FROM pantry_shift sh
JOIN volunteer_shift vs ON vs.shift_id = sh.shift_id
JOIN person pe ON pe.unikey = vs.volunteer_unikey
ORDER BY sh.shift_id, pe.full_name;

-- Q9. Purchase totals by product.
SELECT pr.purchase_date, p.product_code, p.product_name,
       SUM(prl.quantity) AS quantity_purchased,
       SUM(prl.quantity * COALESCE(prl.unit_cost,0)) AS known_line_cost
FROM purchase_record pr
JOIN purchase_record_line prl ON prl.purchase_id = pr.purchase_id
JOIN product p ON p.product_id = prl.product_id
GROUP BY pr.purchase_date, p.product_code, p.product_name
ORDER BY pr.purchase_date, p.product_name;

-- Q10. Confirmed bookings, attendance and absences by session.
SELECT s.session_date, s.session_id, s.start_time,
       COUNT(b.booking_id) FILTER (WHERE b.status <> 'CANCELLED') AS active_bookings,
       COUNT(b.booking_id) FILTER (WHERE b.status = 'ATTENDED') AS attended,
       COUNT(b.booking_id) FILTER (WHERE b.status = 'ABSENT') AS absent,
       ROUND(100.0 * COUNT(b.booking_id) FILTER (WHERE b.status = 'ATTENDED')
             / NULLIF(COUNT(b.booking_id) FILTER (WHERE b.status <> 'CANCELLED'),0), 1)
             AS attendance_percent
FROM session s LEFT JOIN booking b ON b.session_id = s.session_id
GROUP BY s.session_id
ORDER BY s.session_date, s.start_time;

-- Q11. Batches approaching expiry within the next 30 days.
SELECT sb.stock_number, p.product_name, sb.batch_code, sb.expires_on,
       sb.received_qty, (sb.expires_on - CURRENT_DATE) AS days_to_expiry
FROM stock_batch sb JOIN product p ON p.product_id = sb.product_id
WHERE sb.expires_on BETWEEN CURRENT_DATE AND CURRENT_DATE + 30
ORDER BY sb.expires_on;

-- Q12. Sessions at or near capacity (80% or more).
SELECT session_date, session_id, start_time, capacity, active_bookings,
       ROUND(100.0 * active_bookings / NULLIF(capacity,0),1) AS capacity_percent,
       spaces_remaining
FROM v_booking_attendance
WHERE active_bookings >= CEIL(capacity * 0.8)
ORDER BY session_date, start_time;
