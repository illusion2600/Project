-- 04_transactions.sql
SET search_path = campus_pantry, public;

-- A. Booking creation: generate a non-identifying booking token in the application.
-- The database trigger validates daily uniqueness and capacity.
BEGIN;
INSERT INTO booking (student_unikey, session_id, status, qr_token)
VALUES ('zhex6714', 3, 'CONFIRMED', 'DEMO-QR-NEW-001');
-- In the application, commit first, then send the QR email; if email fails,
-- keep the booking and provide a resend action rather than creating a duplicate.
COMMIT;

-- B. QR check-in: scan resolves the token to one booking.
BEGIN;
UPDATE booking
SET status = 'ATTENDED', attendance_at = now()
WHERE qr_token = 'DEMO-QR-001'
  AND status = 'CONFIRMED';
-- Application should check exactly one row was updated.
COMMIT;

-- C. Cancellation: removes the booking from the active roster/capacity count.
BEGIN;
UPDATE booking
SET status = 'CANCELLED', attendance_at = NULL
WHERE qr_token = 'DEMO-QR-NEW-001'
  AND status = 'CONFIRMED';
COMMIT;

-- D. Mark no-shows at the end of the operating day.
BEGIN;
UPDATE booking b
SET status = 'ABSENT'
FROM session s
WHERE s.session_id = b.session_id
  AND s.session_date = CURRENT_DATE
  AND b.status = 'CONFIRMED'
  AND (s.session_date + s.end_time) < localtimestamp;
COMMIT;

-- E. Atomic stock-count update: record the physical event and shift count pair.
BEGIN;
INSERT INTO stock_count

    (stock_number, shift_id, counted_by_staff, count_type, counted_qty, notes)
VALUES
    ('STK-000001', 1, 'must2203', 'SPOT_CHECK', 88, 'Demonstration spot count');

UPDATE shift_stock_count
SET closing_qty = 88
WHERE shift_id = 1 AND stock_number = 'STK-000001';
COMMIT;

-- F. Demonstrate rollback after a failed business-rule check.
BEGIN;
UPDATE booking
SET status = 'ATTENDED', attendance_at = now()
WHERE qr_token = 'DEMO-QR-002'
  AND status = 'CONFIRMED';
-- If the application detects an invalid token or inconsistent state, use:
ROLLBACK;
