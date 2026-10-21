-- 04_transactions.sql
-- Transaction Demonstrations for Campus Pantry
-- Run in PostgreSQL against campus_pantry database after seeding.
SET search_path = campus_pantry, public;

-- ============================================================================
-- A. Booking Creation (Standard Booking & Admin Override)
-- ============================================================================
-- A1. Standard Booking: student 'alex1001' books into session 3 (no previous booking today).
-- Row-level locking on session and student prevents concurrent overbooking and double-booking.
BEGIN;
INSERT INTO booking (student_unikey, session_id, status, qr_token)
VALUES ('alex1001', 3, 'CONFIRMED', 'DEMO-QR-NEW-001');
COMMIT;

-- A2. Admin Override Booking: student 'zhex6714' already has a booking in session 1 on this date.
-- A normal booking would be rejected by validate_booking().
-- With explicit admin_override and override_by_staff, the database permits the exception.
BEGIN;
INSERT INTO booking (student_unikey, session_id, status, qr_token, admin_override, override_by_staff, override_reason)
VALUES ('zhex6714', 3, 'CONFIRMED', 'DEMO-QR-OVERRIDE-001', true, 'must2203', 'Emergency welfare food-parcel exception');
COMMIT;

-- ============================================================================
-- B. Front-Desk QR Check-in
-- ============================================================================
-- Resolves the booking token, updates status from CONFIRMED to ATTENDED,
-- and records the timestamp. Safe and idempotent.
BEGIN;
UPDATE booking
SET status = 'ATTENDED', attendance_at = now()
WHERE qr_token = 'DEMO-QR-001'
  AND status = 'CONFIRMED';
-- Application verifies that exactly 1 row was updated.
COMMIT;

-- ============================================================================
-- C. Booking Cancellation
-- ============================================================================
-- Student cancels an active booking. Status moves to CANCELLED and attendance_at is cleared.
-- The space is instantly returned to available session capacity.
BEGIN;
UPDATE booking
SET status = 'CANCELLED', attendance_at = NULL
WHERE qr_token = 'DEMO-QR-NEW-001'
  AND status = 'CONFIRMED';
COMMIT;

-- ============================================================================
-- D. Mark No-Shows After Operating Day Close (16:00)
-- ============================================================================
-- In accordance with business rules, students may arrive any time during operating hours.
-- No-shows are marked ABSENT only after the pantry's closing time (16:00), not at session end.
BEGIN;
UPDATE booking b
SET status = 'ABSENT'
FROM session s
WHERE s.session_id = b.session_id
  AND s.session_date <= CURRENT_DATE
  AND b.status = 'CONFIRMED'
  AND (s.session_date + TIME '16:00') <= localtimestamp;
COMMIT;

-- ============================================================================
-- E. Atomic Shift Stock Count (Closing Count Handover)
-- ============================================================================
-- Atomically writes the physical closing count event into the audit history (stock_count)
-- and updates the shift summary record (shift_stock_count.closing_qty).
BEGIN;
INSERT INTO stock_count
    (stock_number, shift_id, counted_by_staff, count_type, counted_qty, notes)
VALUES
    ('STK-000001', 1, 'must2203', 'CLOSING', 88, 'Shift 1 closing count audit');

UPDATE shift_stock_count
SET closing_qty = 88
WHERE shift_id = 1 AND stock_number = 'STK-000001';
COMMIT;

-- ============================================================================
-- F. Transaction Rollback Demonstration
-- ============================================================================
-- Demonstrates atomicity: if an error or invalid state is detected before commit,
-- issuing ROLLBACK restores the database to its exact prior state.
BEGIN;
UPDATE booking
SET status = 'ATTENDED', attendance_at = now()
WHERE qr_token = 'DEMO-QR-002'
  AND status = 'CONFIRMED';
-- Simulated detection of condition requiring abort:
ROLLBACK;
