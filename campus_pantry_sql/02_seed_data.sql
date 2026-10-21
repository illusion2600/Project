SET search_path = campus_pantry, public;
BEGIN;

-- People and role memberships. UniKeys are synthetic placeholders for this example.
INSERT INTO person (unikey, full_name, email, contact) VALUES
('must2203','Mustafa','mustafa@example.test',''),
('part2550','Parth','parth@example.test',''),
('haim2897','Haimish','haimish@example.test',''),
('jaim3244','Jaimi','jaimi@example.test',''),
('nikh3591','Nikhil','nikhil@example.test',''),
('phoe3938','Phoebe','phoebe@example.test',''),
('sams4285','Sam','sam@example.test',''),
('saum4632','Saumya','saumya@example.test',''),
('nico4979','Nicole','nicole@example.test',''),
('kevi5326','Kevin','kevin@example.test',''),
('donn5673','Donna','donna@example.test',''),
('joan6020','Joanne','joanne@example.test',''),
('aary6367','Aarya','aarya@example.test',''),
('zhex6714','Zhexi','zhexi@example.test',''),
('chen7061','Chen','chen@example.test',''),
('kara7408','Karan','karan@example.test',''),
('prad7755','Pradeep','pradeep@example.test',''),
('diks8102','Dikshant','dikshant@example.test',''),
('alle8449','Allen','allen@example.test',''),
('susa8796','Susan','susan@example.test',''),
('clai9143','Claire','claire@example.test',''),
('sara9490','Sarah','sarah@example.test',''),
('jaco9837','Jacob','jacob@example.test',''),
('jone1184','Jones','jones@example.test',''),
('chlo1531','Chloe','chloe@example.test',''),
('sneh1878','Sneha','sneha@example.test',''),
('shre2225','Shreya','shreya@example.test','');

INSERT INTO staff (unikey, staff_code) VALUES
('must2203','STAFF-MUSTAFA'),('part2550','STAFF-PARTH'),
('haim2897','STAFF-HAIMISH'),('jaim3244','STAFF-JAIMI');

INSERT INTO volunteer (unikey) VALUES
('nikh3591'),('phoe3938'),('sams4285'),('saum4632'),('nico4979'),
('kevi5326'),('donn5673'),('joan6020'),('aary6367');

-- Kevin is also a student for Session 1; one Person row is shared across roles.
INSERT INTO student (unikey, degree_level, student_category) VALUES

('kevi5326',NULL,NULL),
('zhex6714',NULL,NULL),('chen7061',NULL,NULL),('kara7408',NULL,NULL),
('prad7755',NULL,NULL),('diks8102',NULL,NULL),('alle8449',NULL,NULL),
('susa8796',NULL,NULL),('clai9143',NULL,NULL),('sara9490',NULL,NULL),
('jaco9837',NULL,NULL),('jone1184',NULL,NULL),('chlo1531',NULL,NULL),
('sneh1878',NULL,NULL),('shre2225',NULL,NULL);

INSERT INTO pantry_shift (shift_id, shift_date, start_time, end_time, status) VALUES
(1, DATE '2026-10-09', TIME '10:00', TIME '12:00', 'CLOSED'),
(2, DATE '2026-10-09', TIME '12:00', TIME '14:00', 'CLOSED'),
(3, DATE '2026-10-09', TIME '14:00', TIME '16:00', 'CLOSED');

INSERT INTO shift_staff_assignment (shift_id, staff_unikey, assignment_role) VALUES
(1,'must2203','MAIN_SUPERVISOR'),(1,'part2550','ASSISTANT'),
(2,'haim2897','MAIN_SUPERVISOR'),(2,'part2550','ASSISTANT'),
(3,'jaim3244','MAIN_SUPERVISOR'),(3,'part2550','ASSISTANT');

INSERT INTO volunteer_shift (shift_id, volunteer_unikey) VALUES
(1,'nikh3591'),(1,'phoe3938'),(1,'sams4285'),
(2,'nikh3591'),(2,'saum4632'),(2,'nico4979'),(2,'kevi5326'),
(3,'donn5673'),(3,'joan6020'),(3,'aary6367');

INSERT INTO session (session_date, start_time, end_time, capacity, shift_id) VALUES
(DATE '2026-10-09',TIME '10:00',TIME '10:30',50,1),
(DATE '2026-10-09',TIME '10:30',TIME '11:00',50,1),
(DATE '2026-10-09',TIME '11:00',TIME '11:30',50,1),
(DATE '2026-10-09',TIME '11:30',TIME '12:00',50,1),
(DATE '2026-10-09',TIME '12:00',TIME '12:30',50,2),
(DATE '2026-10-09',TIME '12:30',TIME '13:00',50,2),
(DATE '2026-10-09',TIME '13:00',TIME '13:30',50,2),
(DATE '2026-10-09',TIME '13:30',TIME '14:00',50,2),
(DATE '2026-10-09',TIME '14:00',TIME '14:30',50,3),
(DATE '2026-10-09',TIME '14:30',TIME '15:00',50,3),
(DATE '2026-10-09',TIME '15:00',TIME '15:30',50,3),
(DATE '2026-10-09',TIME '15:30',TIME '16:00',50,3);

-- Supplied first two attendee lists. Tokens are synthetic demonstration tokens only.
INSERT INTO booking (student_unikey, session_id, status, qr_token) VALUES
('zhex6714',1,'CONFIRMED','DEMO-QR-001'),
('chen7061',1,'CONFIRMED','DEMO-QR-002'),
('kevi5326',1,'CONFIRMED','DEMO-QR-003'),
('kara7408',1,'CONFIRMED','DEMO-QR-004'),
('prad7755',1,'CONFIRMED','DEMO-QR-005'),

('diks8102',1,'CONFIRMED','DEMO-QR-006'),
('alle8449',1,'CONFIRMED','DEMO-QR-007'),
('susa8796',2,'CONFIRMED','DEMO-QR-008'),
('clai9143',2,'CONFIRMED','DEMO-QR-009'),
('sara9490',2,'CONFIRMED','DEMO-QR-010'),
('jaco9837',2,'CONFIRMED','DEMO-QR-011'),
('jone1184',2,'CONFIRMED','DEMO-QR-012'),
('chlo1531',2,'CONFIRMED','DEMO-QR-013'),
('sneh1878',2,'CONFIRMED','DEMO-QR-014'),
('shre2225',2,'CONFIRMED','DEMO-QR-015');

-- Sample catalogue, purchase records, purchase lines and stock batches.
INSERT INTO product (product_id, product_code, product_name, category, counting_unit, low_stock_threshold) VALUES
(1,'RICE1','Rice 1 kg','Grains','pack',30),
(2,'PASTA5','Pasta 500 g','Grains','pack',35),
(3,'MILK1','UHT oat milk 1 L','Dairy alternatives','carton',20),
(4,'BREAD1','Sliced bread','Bakery','loaf',20),
(5,'BEANS4','Beans 400 g','Canned food','can',20),
(6,'TUNA2','Tuna 185 g','Canned food','can',40),
(7,'OATS5','Oats 500 g','Breakfast','pack',15),
(8,'APPLE1','Apple bag','Produce','bag',10);

INSERT INTO purchase_record (purchase_id, recorded_by_staff, purchase_date, reference, notes) VALUES
(1,'must2203',DATE '2026-10-09','DEMO-PO-001','Synthetic purchase data for the project example');

INSERT INTO purchase_record_line (purchase_line_id, purchase_id, product_id, quantity, unit_cost) VALUES
(1,1,1,100,2.50),(2,1,2,80,1.80),(3,1,3,60,2.20),(4,1,4,50,2.00),
(5,1,5,100,1.10),(6,1,6,70,1.40),(7,1,7,60,1.60),(8,1,8,40,3.00);

INSERT INTO stock_batch (stock_number, product_id, purchase_line_id, batch_code, received_on, expires_on, received_qty) VALUES
('STK-000001',1,1,'RICE-A',DATE '2026-10-09',DATE '2027-03-31',100),
('STK-000002',2,2,'PASTA-A',DATE '2026-10-09',DATE '2027-02-28',80),
('STK-000003',3,3,'MILK-A',DATE '2026-10-09',DATE '2026-12-15',60),
('STK-000004',4,4,'BREAD-A',DATE '2026-10-09',DATE '2026-10-15',50),
('STK-000005',5,5,'BEANS-A',DATE '2026-10-09',DATE '2027-06-30',100),
('STK-000006',6,6,'TUNA-A',DATE '2026-10-09',DATE '2027-07-31',70),
('STK-000007',7,7,'OATS-A',DATE '2026-10-09',DATE '2027-01-31',60),
('STK-000008',8,8,'APPLE-A',DATE '2026-10-09',DATE '2026-10-20',40);

-- Illustrative shift stock counts and aggregate adjustments.
INSERT INTO shift_stock_count (shift_id, stock_number, opening_qty, closing_qty, opening_variance_reason) VALUES
(1,'STK-000001',100,90,NULL),(1,'STK-000002',80,72,NULL),(1,'STK-000003',60,55,NULL),
(1,'STK-000004',50,40,NULL),(1,'STK-000005',100,95,NULL),(1,'STK-000006',70,65,NULL),

(1,'STK-000007',60,55,NULL),(1,'STK-000008',40,35,NULL),
(2,'STK-000001',90,75,NULL),(2,'STK-000002',72,64,NULL),(2,'STK-000003',55,45,NULL),
(2,'STK-000004',40,30,NULL),(2,'STK-000005',95,85,NULL),(2,'STK-000006',65,55,NULL),
(2,'STK-000007',55,45,NULL),(2,'STK-000008',35,28,NULL),
(3,'STK-000001',75,60,NULL),(3,'STK-000002',64,56,NULL),(3,'STK-000003',45,35,NULL),
(3,'STK-000004',30,20,NULL),(3,'STK-000005',85,75,NULL),(3,'STK-000006',55,45,NULL),
(3,'STK-000007',45,35,NULL),(3,'STK-000008',28,20,NULL);

INSERT INTO stock_adjustment (shift_id, stock_number, adjustment_kind, quantity, reason) VALUES
(1,'STK-000001','RECEIPT',10,'Additional rice batch units received during shift'),
(1,'STK-000004','WASTE',2,'Damaged bread packaging'),
(2,'STK-000003','RECEIPT',10,'Additional milk stock received'),
(2,'STK-000008','WASTE',2,'Bruised produce removed'),
(3,'STK-000001','RECEIPT',5,'Additional rice stock received');

-- Store physical opening and closing count events as history too.
INSERT INTO stock_count (stock_number, shift_id, counted_by_staff, counted_at, count_type, counted_qty, notes)
SELECT ssc.stock_number, ssc.shift_id,
       CASE ssc.shift_id WHEN 1 THEN 'must2203' WHEN 2 THEN 'haim2897' ELSE 'jaim3244' END,
       (DATE '2026-10-09' + CASE ssc.shift_id WHEN 1 THEN TIME '10:00'
          WHEN 2 THEN TIME '12:00' ELSE TIME '14:00' END)::timestamp AT TIME ZONE 'Australia/Sydney',
       'OPENING', ssc.opening_qty, 'Synthetic opening count'
FROM shift_stock_count ssc;

INSERT INTO stock_count (stock_number, shift_id, counted_by_staff, counted_at, count_type, counted_qty, notes)
SELECT ssc.stock_number, ssc.shift_id,
       CASE ssc.shift_id WHEN 1 THEN 'must2203' WHEN 2 THEN 'haim2897' ELSE 'jaim3244' END,
       (DATE '2026-10-09' + CASE ssc.shift_id WHEN 1 THEN TIME '12:00'
          WHEN 2 THEN TIME '14:00' ELSE TIME '16:00' END)::timestamp AT TIME ZONE 'Australia/Sydney',
       'CLOSING', ssc.closing_qty, 'Synthetic closing count'
FROM shift_stock_count ssc;

COMMIT;
