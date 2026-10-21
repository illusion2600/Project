-- 02b_sync_sequences.sql
-- Run once after 02_seed_data.sql.
-- The seed data inserts explicit IDs, so each identity sequence must be moved past
-- the highest ID already used; otherwise the next default ID collides (issue 7).
SET search_path = campus_pantry, public;

SELECT setval(pg_get_serial_sequence('campus_pantry.pantry_shift', 'shift_id'),
              COALESCE((SELECT max(shift_id) FROM pantry_shift), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('campus_pantry.session', 'session_id'),
              COALESCE((SELECT max(session_id) FROM session), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('campus_pantry.booking', 'booking_id'),
              COALESCE((SELECT max(booking_id) FROM booking), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('campus_pantry.product', 'product_id'),
              COALESCE((SELECT max(product_id) FROM product), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('campus_pantry.purchase_record', 'purchase_id'),
              COALESCE((SELECT max(purchase_id) FROM purchase_record), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('campus_pantry.purchase_record_line', 'purchase_line_id'),
              COALESCE((SELECT max(purchase_line_id) FROM purchase_record_line), 0) + 1, false);
SELECT setval(pg_get_serial_sequence('campus_pantry.stock_count', 'stock_count_id'),
              COALESCE((SELECT max(stock_count_id) FROM stock_count), 0) + 1, false);
SELECT setval('campus_pantry.stock_number_seq',
              COALESCE((SELECT max(substring(stock_number FROM 5)::int) FROM stock_batch), 0) + 1, false);
