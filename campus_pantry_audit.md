# Campus Pantry — Complete Codebase Audit & Takeover Plan

> **Audited:** 21 October 2026  
> **Auditor:** Antigravity (automated code review — no SQL was executed against a database)  
> **Source documents:** [ERD.pdf](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/ERD.pdf), [Work Completed and Remaining Tasks.pdf](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Work Completed and Remaining Tasks.pdf), [Campus_Pantry_Complete_Revised_Project.pdf](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Campus_Pantry_Complete_Revised_Project.pdf)

> [!IMPORTANT]
> **I have not connected to PostgreSQL or executed any SQL.** All assessments below are based on reading the code. Claims about "runs correctly" or "returns expected results" cannot be made without live execution. This is explicitly flagged throughout.

---

## 1. Project Structure (File-by-File Inventory)

```text
Project/
├── campus_pantry_sql/                      ← Team SQL scripts (standalone)
│   ├── 01_schema.sql
│   ├── 02_seed_data.sql
│   ├── 03_queries.sql
│   ├── 04_transactions.sql
│   ├── 05_validation.sql
│   └── setup_all_01_02.sql                ← Convenience: schema + seed combined
│
├── campus_pantry_app/                      ← Python prototype + fix scripts
│   ├── README.md
│   ├── requirements.txt
│   ├── db.py
│   ├── services.py
│   ├── cli.py
│   ├── concurrency_demo.py
│   ├── .venv/                              ← Local virtualenv (psycopg2-binary installed)
│   ├── __pycache__/
│   └── sql/
│       ├── 01b_fix_booking_trigger.sql
│       ├── 01c_unikey_format.sql
│       ├── 02b_sync_sequences.sql
│       └── rebuild_campus_pantry.sql       ← All-in-one: drops schema, runs 01+01b+01c+02+02b
│
├── __MACOSX/                               ← macOS ZIP metadata (irrelevant, safe to delete)
├── _pdf_complete_project.txt               ← Temp extract (created during this audit)
└── _pdf_theory_workflow.txt                ← Temp extract (created during this audit)
```

> [!NOTE]
> **Missing expected files:** `06_failure_tests.sql` does not exist anywhere. No report, poster, video, participation statement, or AI-use declaration files were found in the repository.

### Detailed File Inventory

| File | Purpose | Status | Dependencies | Tested? |
|------|---------|--------|-------------|---------|
| [01_schema.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/01_schema.sql) | Tables, constraints, triggers, views, indexes (279 lines) | **Substantially complete** — has known issues (#1 shift_id nullable, #2 shift staffing) | Standalone; must run first | **Not tested against PostgreSQL** |
| [02_seed_data.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/02_seed_data.sql) | 27 people, 4 staff, 9 volunteers, 15 students, 3 shifts, 12 sessions, 15 bookings, 8 products, 1 purchase, 8 stock batches, shift stock counts, adjustments, count history (166 lines) | **Substantially complete** — needs sequence reset afterwards | Requires 01_schema.sql | **Not tested** |
| [03_queries.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/03_queries.sql) | 12 reporting queries Q1–Q12 (133 lines) | **Complete** — Q6 has the known `<` vs `<=` inequality bug | Requires schema + seed | **Not tested** |
| [04_transactions.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/04_transactions.sql) | 6 transaction demos A–F (62 lines) | **Has bugs** — Txn A will fail (issue #6), Txn D wrong timing (issue #3), Txn E mislabelled (issue #10) | Requires schema + seed | **Not tested** |
| [05_validation.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/05_validation.sql) | 12 validation/integrity checks (74 lines) | **Complete** — good coverage | Requires schema + seed | **Not tested** |
| [setup_all_01_02.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/setup_all_01_02.sql) | Concatenation of 01_schema + 02_seed_data (444 lines) | **Duplicate** — identical to running 01 then 02; doesn't include fixes | — | **Not tested** |
| [README.md](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/README.md) | Setup instructions, feature table, file map (80 lines) | **Complete and well-written** | — | N/A |
| [db.py](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/db.py) | PostgreSQL connection via env vars; friendly constraint error messages (54 lines) | **Complete** — credentials from env vars ✓ | psycopg2-binary | **Not tested** |
| [services.py](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/services.py) | Business logic: book, check-in, cancel, no-shows, set_up_day, stock counts, reports (247 lines) | **Complete** — implements concurrency fix via FOR UPDATE | db.py | **Not tested** |
| [cli.py](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/cli.py) | CLI menus for student and staff roles (173 lines) | **Complete** — all service functions wired to menus | services.py, db.py | **Not tested** |
| [concurrency_demo.py](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/concurrency_demo.py) | Demonstrates double-booking race + locking fix (77 lines) | **Complete** — uses threading, cleans up after itself | db.py | **Not tested** |
| [requirements.txt](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/requirements.txt) | `psycopg2-binary>=2.9` | **Complete** | — | N/A |
| [01b_fix_booking_trigger.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/sql/01b_fix_booking_trigger.sql) | Fixes trigger to skip validation on status-only updates (58 lines) | **Complete** — critical fix for check-in/no-show after admin override | Requires 01_schema.sql | **Not tested** |
| [01c_unikey_format.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/sql/01c_unikey_format.sql) | CHECK constraint: unikey must match `^[a-z]{4}[0-9]{4}$` (8 lines) | **Complete** | Requires 01_schema.sql | **Not tested** |
| [02b_sync_sequences.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/sql/02b_sync_sequences.sql) | Resets 8 identity sequences past seed data IDs (23 lines) | **Complete** — addresses issue #7 | Requires 02_seed_data.sql | **Not tested** |
| [rebuild_campus_pantry.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/sql/rebuild_campus_pantry.sql) | `DROP SCHEMA CASCADE` + all of 01 + 01b + 01c + 02 + 02b (534 lines) | **Complete** — one-shot rebuild | Standalone | **Not tested** |
| `06_failure_tests.sql` | Negative-path tests | **MISSING — does not exist** | — | — |

---

## 2. Database Audit Against the Revised ERD

### ERD Entity-by-Entity Comparison

| ERD Entity | Schema Table | Match? | Issues |
|-----------|-------------|--------|--------|
| Person (UniKey PK, full_name, email, contact) | `person` | ✅ Match | UniKey format CHECK in 01c only |
| Student (degree_level, student_category) | `student` | ✅ Match | Seed data inserts NULLs for both — allowed by schema but odd |
| Volunteer (is_active) | `volunteer` | ✅ Match | — |
| Staff (staff_code, is_active) | `staff` | ✅ Match | — |
| ISA overlapping, total | person → student/volunteer/staff FKs | ⚠️ Partial | Overlapping ✓. **Total participation not enforced** — a person can exist without any role subtype. No trigger/constraint prevents this. |
| Session (session_id, date, start, end, capacity) | `session` | ✅ Match | capacity CHECK 1–50 ✓ |
| Session BelongsTo Shift (1..1 cardinality) | `session.shift_id` FK | ❌ **Mismatch** | ERD says 1..1 (exactly one shift). Schema adds `shift_id` as **nullable** via ALTER TABLE. **Issue #1.** |
| Shift (shift_id, date, start, end, status) | `pantry_shift` | ✅ Match | — |
| Staff AssignedTo Shift (2..2 per shift) | `shift_staff_assignment` | ⚠️ Partial | ERD says exactly 2 staff per shift (1 MAIN_SUPERVISOR + 1 ASSISTANT). UNIQUE(shift_id, assignment_role) prevents >1 of each role, but **nothing enforces ≥1**. A shift with 0 or 1 staff passes. **Issue #2.** |
| Volunteer RegistersFor Shift (0..*, 0..*) | `volunteer_shift` | ✅ Match | — |
| Student Makes Booking (0..*, 1..1) | `booking.student_unikey` NOT NULL FK | ✅ Match | — |
| Booking For Session (1..1, 0..*) | `booking.session_id` NOT NULL FK | ✅ Match | — |
| Booking attributes | booking_id, status, qr_token, created_at, attendance_at, admin_override | ✅ Match | `override_by_staff` and `override_reason` are extras not on ERD but consistent with business rules |
| Staff Records PurchaseRecord | `purchase_record.recorded_by_staff` FK | ✅ Match | — |
| PurchaseRecord Contains PurchaseLine (1..*, 1..1) | `purchase_record_line.purchase_id` FK | ⚠️ Partial | ERD says 1..* (each purchase must have ≥1 line). **Not enforced** — a purchase_record with zero lines is allowed. |
| PurchaseLine Of Product (1..1, 0..*) | `purchase_record_line.product_id` FK | ✅ Match | — |
| Product → StockBatch (0..*, 1..1) | `stock_batch.product_id` FK | ✅ Match | **Denormalization noted** — product_id is also derivable via purchase_line → product. **Issue #4** — intentional trade-off, should be documented. |
| StockBatch Supplies PurchaseLine (1..1) | `stock_batch.purchase_line_id` FK | ✅ Match | — |
| StockCount CountOf StockBatch (1..1, 0..*) | `stock_count.stock_number` FK | ✅ Match | — |
| StockCount DuringShift (0..1) | `stock_count.shift_id` FK nullable | ✅ Match | — |
| StockCount CountedBy Staff (1..1) | `stock_count.counted_by_staff` FK | ✅ Match | — |

### ERD Entities NOT on the ERD Diagram but in Schema

| Extra Table | Justification |
|------------|---------------|
| `shift_stock_count` | Summarizes opening/closing per shift+batch. Not on the ERD diagram but described in the Complete Project document as "retained from original design." |
| `stock_adjustment` | RECEIPT/WASTE adjustments within shift. Not on ERD diagram. References shift_stock_count. |

> [!WARNING]
> `shift_stock_count` and `stock_adjustment` **do not appear on the ERD diagram** but are in the schema and the Complete Revised Project document. The report must reconcile these — either add them to the ERD or explain they are implementation-level summary tables.

### Business Rule Enforcement Summary

| Rule | Mechanism | Adequate? |
|------|----------|-----------|
| Max 50 active bookings/session | Trigger `validate_booking()` counts non-cancelled bookings | ✅ Yes — uses `FOR UPDATE` on session row |
| One booking/student/day (default) | Trigger `validate_booking()` checks by date | ✅ Yes — bypassed with `admin_override` |
| Admin override must identify staff | CHECK constraint + trigger check | ✅ Yes |
| QR check-in → ATTENDED + attendance_at | CHECK `(status='ATTENDED' ⇒ attendance_at IS NOT NULL)` | ✅ Yes |
| Idempotent QR scan | Python prototype handles; SQL `WHERE status='CONFIRMED'` | ✅ Yes |
| No-show = ABSENT after 16:00 | Python: `CLOSING_TIME = "16:00"` ✅. SQL 04_transactions Txn D: uses session end_time ❌ | ⚠️ **Issue #3** |
| Session within shift time | Trigger `validate_session_shift()` | ⚠️ Allows NULL shift_id — **Issue #1** |
| Exactly 2 staff per shift | UNIQUE prevents >1 per role; **nothing prevents <1** | ❌ **Issue #2** |
| Concurrent booking safety | Python: `SELECT … FOR UPDATE` on student row ✅. SQL scripts: no protection ❌ | ⚠️ **Issue #8** |

---

## 3. SQL Script Audit

### 3.1  `01_schema.sql` — [View](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/01_schema.sql)

**Tables created (15):** person, student, volunteer, staff, pantry_shift, session, shift_staff_assignment, volunteer_shift, booking, purchase_record, product, purchase_record_line, stock_batch, stock_count, shift_stock_count, stock_adjustment

**Triggers (2):**
- `validate_booking()` — capacity + daily uniqueness (lines 166–211)
- `validate_session_shift()` — session must fall within shift time (lines 217–236)

**Views (3):**
- `v_booking_attendance` — session-level booking summary
- `v_latest_stock_count` — last count per batch (DISTINCT ON)
- `v_shift_stock_report` — shift-level stock movement report

**Indexes (6):** booking_by_session, booking_by_student, stock_batch_by_product, stock_batch_by_expiry, stock_count_by_batch_time, shift_count_by_batch

**Key structural issue:** `session.shift_id` is added via `ALTER TABLE` at line 215 as a **nullable** column rather than being part of the initial CREATE TABLE. This is the root of Issue #1.

**Dependency order:** Correct — tables are created in FK-dependency order. The ALTER TABLE for shift_id comes after both `session` and `pantry_shift` exist.

### 3.2  `02_seed_data.sql` — [View](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/02_seed_data.sql)

| Entity | Count | Notes |
|--------|-------|-------|
| person | 27 | All with email, empty contact string |
| staff | 4 | must2203, part2550, haim2897, jaim3244 |
| volunteer | 9 | incl. kevi5326 (also a student) |
| student | 15 | All with NULL degree_level and student_category |
| pantry_shift | 3 | All 2026-10-09, all CLOSED |
| shift_staff_assignment | 6 | 2 per shift ✓ |
| volunteer_shift | 10 | Distributed across shifts |
| session | 12 | All with shift_id set ✓ |
| booking | 15 | 7 in session 1, 8 in session 2 |
| product | 8 | With explicit product_id 1–8 |
| purchase_record | 1 | Explicit purchase_id = 1 |
| purchase_record_line | 8 | Explicit IDs 1–8 |
| stock_batch | 8 | Explicit STK-000001 to STK-000008 |
| shift_stock_count | 24 | 8 batches × 3 shifts |
| stock_adjustment | 5 | 3 RECEIPT, 2 WASTE |
| stock_count | 48 | Generated from shift_stock_count (24 opening + 24 closing) |

**Issues found:**
1. All students have `NULL` degree_level and student_category — technically allowed by schema but doesn't demonstrate the constraint.
2. **Explicit identity IDs are inserted** — sequences WILL be out of sync without `02b_sync_sequences.sql`. This is Issue #7, which is addressed by the fix script.
3. The `contact` column for all persons is empty string `''`, not NULL.

### 3.3  `03_queries.sql` — [View](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/03_queries.sql)

| Query | Purpose | Logic | Issues |
|-------|---------|-------|--------|
| **Q1** | Detailed shift stock-count report | Uses `v_shift_stock_report` view | ✅ Looks correct |
| **Q2** | Estimated dispensing by product | SUM of estimated_dispensed_qty grouped by product | ✅ Looks correct |
| **Q3** | Latest count per stock batch | Uses `v_latest_stock_count` view | ✅ Looks correct |
| **Q4** | Products below low-stock threshold | CTE with DISTINCT ON for latest count per batch, then aggregate by product | ✅ Looks correct |
| **Q5** | Session booking/attendance summary | Uses `v_booking_attendance` view | ✅ Looks correct |
| **Q6** | Opening variance from previous closing | Uses `LATERAL` join to find previous shift's closing | ❌ **Bug (Issue #5)**: Line 64 uses strict `<` — `(sh2.shift_date, sh2.end_time) < (cur_shift.shift_date, cur_shift.start_time)`. When shift 1 ends at 12:00 and shift 2 starts at 12:00, the `<` misses it. Should use `<=` on end_time or tuple comparison with `<=`. |
| **Q7** | Products with no dispensing | NOT EXISTS on v_shift_stock_report | ✅ Looks correct |
| **Q8** | Staff + volunteer roster by shift | Two separate SELECT statements | ✅ Correct but note: produces two result sets |
| **Q9** | Purchase totals by product | JOIN purchase_record → lines → product | ✅ Looks correct |
| **Q10** | Bookings/attendance/absences by session | FILTER aggregation with attendance % | ✅ Looks correct |
| **Q11** | Batches approaching expiry (30 days) | WHERE expires_on BETWEEN CURRENT_DATE AND +30 | ✅ Looks correct |
| **Q12** | Sessions at/near capacity (≥80%) | Uses `v_booking_attendance` with CEIL(capacity*0.8) | ✅ Looks correct |

### 3.4  `04_transactions.sql` — [View](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/04_transactions.sql)

| Txn | Description | Steps | Issues |
|-----|-------------|-------|--------|
| **A** | Booking creation | INSERT booking for zhex6714 in session 3 | ❌ **Will fail (Issue #6)**: zhex6714 already has a CONFIRMED booking in session 1 on the same day (2026-10-09). Trigger will reject: "Student already has an active booking on this date." Need a different student or add admin_override. |
| **B** | QR check-in | UPDATE booking WHERE qr_token = 'DEMO-QR-001' AND status = 'CONFIRMED' → ATTENDED | ⚠️ After 01b_fix, this works. Without 01b_fix, may fail if zhex6714 has an admin-override second booking (though that's not in seed data). |
| **C** | Cancellation | UPDATE booking WHERE qr_token = 'DEMO-QR-NEW-001' → CANCELLED | ⚠️ Depends on Txn A succeeding first (which it won't). |
| **D** | Mark no-shows | UPDATE confirmed → ABSENT WHERE `(session_date + end_time) < localtimestamp` | ❌ **Wrong timing (Issue #3)**: Uses individual session end_time instead of the 16:00 operating-day close. Should compare against 16:00. |
| **E** | Atomic stock count | INSERT SPOT_CHECK + UPDATE closing_qty | ⚠️ **Mislabelled (Issue #10)**: Comment says "Atomic stock-count update" but inserts a SPOT_CHECK and overwrites a closing_qty. The stated intent was opening+closing workflow. Functionally it runs, but the demo narrative doesn't match. |
| **F** | Rollback demo | UPDATE → ROLLBACK | ✅ Works as intended — demonstrates explicit rollback. |

### 3.5  `05_validation.sql` — [View](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/05_validation.sql)

| Check | Purpose | Expected Result | Assessment |
|-------|---------|-----------------|------------|
| 1 | Core row counts | Table counts | ✅ Informational |
| 2 | Shifts with ≠1 supervisor or ≠1 assistant | Should return 0 rows | ✅ Good — catches Issue #2 |
| 3 | Sessions exceeding capacity | Should return 0 rows | ✅ Good |
| 4 | Students with >1 active booking/day | Surfaces overrides | ✅ Good |
| 5 | Invalid status/attendance_at combinations | Should return 0 rows | ✅ Good |
| 6 | Batches with no count history | Should return 0 rows | ✅ Good |
| 7 | Negative last-count quantities | Should return 0 rows | ✅ Good |
| 8 | Negative estimated dispensing | Identifies arithmetic issues | ✅ Good |
| 9 | StockNumber format validation | Should return 0 rows | ✅ Good |
| 10 | Sessions outside their shift times | Should return 0 rows | ✅ Good |
| 11 | Booking attendance summary | Full view dump | ✅ Informational |
| 12 | Latest stock count summary | Full view dump | ✅ Informational |

### 3.6  `06_failure_tests.sql` — **MISSING**

This file does not exist. The task list requires these negative tests:

| Required Test | Status |
|--------------|--------|
| Duplicate daily booking (should be rejected) | **Not written** |
| 51st active booking in a session (should be rejected) | **Not written** |
| Negative stock / invalid stock quantity | **Not written** |
| Missing foreign-key reference | **Not written** |
| Repeated check-in (should be idempotent) | **Not written** |
| Two-connection concurrency test | **Not written** (Python concurrency_demo.py exists but not pure SQL) |

---

## 4. Known Issues Audit Table

| # | Issue | Required Behaviour | Current Implementation | Status | File/Location | Recommended Fix |
|---|-------|-------------------|----------------------|--------|---------------|----------------|
| 1 | `Session.shift_id` must be NOT NULL | Every session belongs to exactly one shift (ERD 1..1) | `shift_id` added as **nullable** via ALTER TABLE at [01_schema.sql:215](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/01_schema.sql#L215) | **Incorrect** | 01_schema.sql L215, rebuild L219 | Move shift_id into the CREATE TABLE statement with NOT NULL, or add `ALTER TABLE session ALTER COLUMN shift_id SET NOT NULL` after the ALTER TABLE ADD COLUMN. |
| 2 | Shift staffing: exactly 1 MAIN_SUPERVISOR + 1 ASSISTANT | ERD says 2..2 staff per shift | UNIQUE(shift_id, assignment_role) prevents >1 per role but **does not enforce ≥1**. A shift with 0 staff is valid. | **Partially implemented** | [01_schema.sql:54-61](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/01_schema.sql#L54-L61) | Add a trigger that fires on INSERT/UPDATE of `pantry_shift` to status='OPEN' or 'CLOSED', rejecting if the shift lacks exactly one of each role. Or add an application-level check (the validation query in 05_validation.sql#L12-L20 already detects violations). |
| 3 | No-shows marked after 16:00 operating-day close | Use 16:00 close, not individual session end time | SQL Txn D: `(s.session_date + s.end_time) < localtimestamp` — marks absences per session end. Python: correctly uses `CLOSING_TIME = "16:00"`. | **Incorrect in SQL, correct in Python** | [04_transactions.sql:31-39](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/04_transactions.sql#L31-L39) vs [services.py:184-190](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/services.py#L184-L190) | Change SQL Txn D to: `AND (s.session_date + TIME '16:00') < localtimestamp` to match the Python implementation and business rule. |
| 4 | Redundant `product_id` in `stock_batch` | Document the denormalization trade-off | `stock_batch` has both `product_id FK` and `purchase_line_id FK` (where purchase_line already has product_id). | **Implemented, needs documentation** | [01_schema.sql:112-122](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/01_schema.sql#L112-L122) | Add a note in the report explaining: "product_id is denormalized into stock_batch for faster lookups and index-only queries on product→batch relationships, avoiding a join through purchase_record_line." |
| 5 | Q6 back-to-back shift inequality | Consecutive shifts meeting at the same time (e.g., 12:00) should be linked | Uses strict `<` at [03_queries.sql:64](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/03_queries.sql#L64): `(sh2.shift_date, sh2.end_time) < (cur_shift.shift_date, cur_shift.start_time)` | **Incorrect** | [03_queries.sql:64](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/03_queries.sql#L64) | Change to `(sh2.shift_date < cur_shift.shift_date OR (sh2.shift_date = cur_shift.shift_date AND sh2.end_time <= cur_shift.start_time))` to capture shifts whose end_time equals the next shift's start_time. |
| 6 | Booking demo same-day conflict | Txn A must not violate one-booking-per-day | Txn A books zhex6714 into session 3, but seed data already has zhex6714 CONFIRMED in session 1 (same date). Trigger will reject. | **Incorrect** | [04_transactions.sql:7-8](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/04_transactions.sql#L7-L8) | Change to a student without an existing booking on that date (e.g., one of the students in sessions 3–12 who have no bookings), OR add admin_override=true with override_by_staff and reason. |
| 7 | Identity sequence reset | Sequences must advance past manually-inserted IDs | [02b_sync_sequences.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/sql/02b_sync_sequences.sql) correctly resets 8 sequences. | **Implemented, untested** | campus_pantry_app/sql/02b_sync_sequences.sql | Run as part of the setup procedure and verify new inserts get IDs higher than seed data IDs. |
| 8 | Concurrent daily booking check | Two simultaneous bookings for the same student must not both succeed | SQL scripts: **no protection**. Python: `SELECT … FOR UPDATE` on student row at [services.py:121](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/services.py#L121). `concurrency_demo.py` demonstrates the race. | **Partially implemented** | services.py L121; concurrency_demo.py; 04_transactions.sql (no note) | Add a comment to 04_transactions.sql explaining the concurrency gap, or demonstrate using SERIALIZABLE isolation. The Python fix is correct. |
| 9 | ERD–schema consistency | All entities, keys, cardinalities match | Mostly consistent. **Discrepancies:** (a) shift_stock_count and stock_adjustment not on ERD diagram; (b) Session.shift_id nullable vs ERD 1..1; (c) total participation in ISA not enforced. | **Partially implemented** | Multiple files | Add shift_stock_count and stock_adjustment to the ERD or explain their absence. Fix shift_id NOT NULL. Document ISA total participation as application-level enforcement. |
| 10 | Stock-count demo clarity | Should demo opening+closing workflow, not spot_check + closing override | Txn E inserts SPOT_CHECK and updates closing_qty. Comment says "Atomic stock-count update" which is vague. | **Incorrect** | [04_transactions.sql:42-52](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/04_transactions.sql#L42-L52) | Either relabel to explain it's demonstrating a spot-check correction, or change to demonstrate a proper CLOSING count entry with the matching shift_stock_count update. |
| 11 | End-to-end testing + prototype running | SQL executed in PostgreSQL; prototype connected to live DB | **Nothing has been tested.** The task list confirms "The SQL has not been run in PostgreSQL yet. The Python prototype has not been connected to a live database." | **Missing** | All files | Execute `rebuild_campus_pantry.sql`, then run 03, 04, 05, capture screenshots. Start the Python CLI and test each workflow. |

---

## 5. Python Prototype Audit

### Application Architecture

| Component | File | Lines | Framework |
|-----------|------|-------|-----------|
| Entry point | [cli.py](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/cli.py) | 173 | Plain Python CLI (no web framework) |
| Business logic | [services.py](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/services.py) | 247 | Pure functions, each one transaction |
| DB connection | [db.py](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/db.py) | 54 | psycopg2-binary via env vars |
| Concurrency demo | [concurrency_demo.py](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/concurrency_demo.py) | 77 | threading + psycopg2 |
| Dependencies | [requirements.txt](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/requirements.txt) | 1 | psycopg2-binary>=2.9 |

### Connection & Credentials

- **Host:** `PGHOST` env var (default: localhost)
- **Port:** `PGPORT` env var (default: 5432)
- **Database:** `PGDATABASE` env var (default: campus_pantry)
- **User:** `PGUSER` env var (default: OS login name)
- **Password:** `PGPASSWORD` env var (prompted if needed and not set)
- **Schema:** `campus_pantry` set via connection `options`

> [!TIP]
> Credentials are handled safely via environment variables. No hardcoded passwords found. ✅

### Feature Inventory

| Feature | Service Function | CLI Menu | Status |
|---------|-----------------|----------|--------|
| View sessions with capacity | `list_sessions()` | Student > "View sessions and spaces" | ✅ Implemented |
| Book a session | `book_session()` | Student > "Book a session" | ✅ Implemented (with FOR UPDATE lock) |
| My bookings | `my_bookings()` | Student > "My bookings" | ✅ Implemented |
| Cancel booking | `cancel_booking()` | Student > "Cancel a booking" | ✅ Implemented |
| QR check-in | `check_in()` | Staff > "Front desk: check in a QR code" | ✅ Implemented (idempotent) |
| Special booking (admin override) | `book_session()` with override | Staff > "Special booking" | ✅ Implemented |
| Mark no-shows | `mark_no_shows()` | Staff > "Mark no-shows after closing" | ✅ Implemented (uses 16:00) |
| Set up day | `set_up_day()` | Staff > "Set up a day" | ✅ Implemented (creates 3 shifts + 12 sessions) |
| Day attendance report | `report_day_summary()` | Staff > "Report: day attendance summary" | ✅ Implemented |
| Near-capacity report | `report_near_capacity()` | Staff > "Report: sessions near capacity" | ✅ Implemented |
| Latest stock counts | `latest_stock()` | Staff > "Stock: latest counts" | ✅ Implemented |
| Record stock count | `record_stock_count()` | Staff > "Stock: record a count" | ✅ Implemented |
| Low stock report | `report_low_stock()` | Staff > "Report: low stock" | ✅ Implemented |
| Concurrency demo | `concurrency_demo.py` | Standalone script | ✅ Implemented |

### Missing Features

| Feature | Status |
|---------|--------|
| Volunteer menu | Not implemented (CLI says "This prototype has menus for students and staff only") |
| Person/role creation | Not implemented — read-only from seed data |
| Purchase record creation | Not implemented |
| Email QR code | Not implemented — token printed to console |
| Stock batch creation | Not implemented |

> [!NOTE]
> The prototype covers the core booking+check-in+stock-count workflow. Missing features (volunteer menu, purchasing, email) are reasonable scope cuts for a university project prototype.

---

## 6. Report & Submission Requirements

| Deliverable | Status | Evidence |
|-------------|--------|----------|
| **Report Part 1** — Problem & requirements (≤500 words) | **NOT STARTED** | Not found in repo. The Complete Revised Project PDF has draft content that could be adapted. |
| **Report Part 2** — Conceptual design (ERD + rationale) | **PARTIALLY DONE** | ERD.pdf exists. Complete Revised Project PDF has entity descriptions and cardinalities. Need final consistency pass. |
| **Report Part 3** — Logical design (FDs, BCNF, mapping) | **PARTIALLY DONE** | Complete Revised Project PDF §6 has FDs and normalisation reasoning. Needs review and adaptation. |
| **Report Part 4** — SQL & transactions (queries, screenshots, explanations) | **NOT STARTED** | Queries exist but no execution results or screenshots. |
| **README** | **DONE** ✅ | [README.md](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/README.md) — well-written setup instructions |
| **06_failure_tests.sql** | **NOT STARTED** | File does not exist |
| **Prototype demo video** | **NOT STARTED** | No video file found |
| **One-page poster** | **NOT STARTED** | No poster file found |
| **Participation statement** | **NOT STARTED** | No statement file found |
| **AI-use declaration** | **NOT STARTED** | No declaration file found |
| **ERD consistent with final schema** | **NEEDS VERIFICATION** | Known gaps: shift_stock_count, stock_adjustment missing from ERD; shift_id nullability |
| **All SQL tested + screenshots** | **NOT STARTED** | No evidence of execution |

---

## 7. Takeover Plan

### A. Executive Summary

1. **Your teammate wrote ~95% of the code:** 5 SQL scripts, 4 Python files, a concurrency demo, 4 fix scripts, a rebuild script, and a README — approximately 1,600 lines of SQL and 550 lines of Python.
2. **Nothing has been tested against PostgreSQL.** The task list explicitly confirms this. All code is "written but unverified."
3. **The Python prototype is architecturally sound** — clean separation (db.py / services.py / cli.py), transactions with rollback, concurrency locking, and environment-variable credentials.
4. **The SQL schema is ~90% correct** — the core structure matches the ERD with 2 structural issues (shift_id nullable, shift staffing completeness) and several bugs in 04_transactions.sql.
5. **The 12 reporting queries are well-written** — only Q6 has a confirmed bug (strict `<` instead of `<=`).
6. **06_failure_tests.sql does not exist** — this is a required deliverable.
7. **No report, poster, video, or administrative documents exist** — these represent the largest remaining effort.
8. **The biggest risk is time:** testing, fixing 4–5 SQL bugs, writing failure tests, producing the report with screenshots, and recording a prototype video all need to happen before submission.
9. **No data loss risk:** existing code is solid and changes needed are small, localized fixes.
10. **Estimated completion:** Code fixes = ~2–3 hours. Testing + screenshots = ~2–3 hours. Report writing = ~4–6 hours. Video + poster + admin = ~2–3 hours. **Total: ~10–15 hours of focused work.**

### B. Completion Matrix

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Schema (01_schema.sql) | ⚠️ Implemented, 2 bugs | shift_id nullable; shift staffing incomplete |
| Seed data (02_seed_data.sql) | ⚠️ Implemented, needs seq reset | 02b_sync_sequences.sql addresses this |
| Reporting queries (03_queries.sql) | ⚠️ Implemented, Q6 bug | Strict `<` → `<=` fix needed |
| Transactions (04_transactions.sql) | ❌ 3 bugs | Txn A (same-day conflict), D (timing), E (mislabel) |
| Validation (05_validation.sql) | ✅ Implemented | 12 good checks |
| Failure tests (06_failure_tests.sql) | ❌ Missing | Not written |
| Booking trigger fix (01b) | ✅ Implemented, untested | Fix is correct by code reading |
| UniKey format (01c) | ✅ Implemented, untested | Correct regex |
| Sequence sync (02b) | ✅ Implemented, untested | Covers all identity columns |
| Python prototype | ✅ Implemented, untested | All core workflows |
| Concurrency demo | ✅ Implemented, untested | Threading-based |
| README | ✅ Complete | Good quality |
| Report Parts 1–4 | ❌ Not started | — |
| 06_failure_tests.sql | ❌ Not started | — |
| Prototype video | ❌ Not started | — |
| Poster | ❌ Not started | — |
| Participation statement | ❌ Not started | — |
| AI-use declaration | ❌ Not started | — |

### C. Critical Bugs (Priority Ranking)

#### P0 — Prevents execution or invalidates core correctness

| Bug | Impact | Fix Effort |
|-----|--------|-----------|
| **Txn A: zhex6714 same-day conflict** | 04_transactions.sql will error on Txn A, which cascades to Txn C (depends on A's booking). Cannot demonstrate booking+cancel without fixing. | 2 min: change student or add admin override |
| **Session.shift_id nullable** | Violates ERD's 1..1 relationship. Any session inserted without shift_id silently succeeds, breaking a core design constraint. | 5 min: add NOT NULL to the ALTER TABLE or restructure |
| **No end-to-end testing** | Cannot submit without evidence that SQL runs. Unknown execution errors may exist. | 2–3 hours to run + capture screenshots |

#### P1 — Core functionality or assessment requirement missing

| Bug | Impact | Fix Effort |
|-----|--------|-----------|
| **06_failure_tests.sql missing** | Required deliverable not written | 30–60 min to write 5–6 negative tests |
| **Q6 inequality bug** | Reporting query produces wrong results for back-to-back shifts | 2 min: change `<` to `<=` |
| **Txn D: no-show timing** | SQL demo contradicts business rule (per-session vs. 16:00) | 2 min: change to `TIME '16:00'` |
| **Report Parts 1–4** | Required deliverable not started | 4–6 hours |
| **Shift staffing completeness** | Nothing prevents a shift with 0 staff | 15–30 min: add trigger or document as application-level |

#### P2 — Report, usability, documentation, or presentation

| Bug | Impact | Fix Effort |
|-----|--------|-----------|
| **Txn E mislabelled** | Demo narrative doesn't match what the SQL does | 5 min: fix comments or change to CLOSING count |
| **Prototype video** | Required deliverable | 30–60 min |
| **Poster** | Required deliverable | 1–2 hours |
| **Participation statement** | Required deliverable | 10 min |
| **AI-use declaration** | Required deliverable | 10 min |
| **stock_batch product_id denormalization** | Needs documentation in report | 5 min paragraph |
| **shift_stock_count / stock_adjustment not on ERD** | ERD inconsistency | 15 min: add to ERD or document |
| **Concurrent booking note in SQL** | Issue #8 not addressed in pure SQL | 5 min: add comment |

### D. Ordered Implementation Plan

| # | Task | File(s) | Prerequisites | Test | Success Criteria | Unblocks |
|---|------|---------|--------------|------|-----------------|----------|
| 1 | **Install PostgreSQL locally and create the `campus_pantry` database** | — | PostgreSQL 15+ installed | `psql -c "SELECT version()"` | Version 15+ returned | Everything |
| 2 | **Run `rebuild_campus_pantry.sql`** | [rebuild_campus_pantry.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_app/sql/rebuild_campus_pantry.sql) | Step 1 | Check tables in pgAdmin | 15+ tables created in `campus_pantry` schema | Steps 3–11 |
| 3 | **Fix Session.shift_id to NOT NULL** | 01_schema.sql L215 + rebuild | Step 2 | Try `INSERT INTO session … WHERE shift_id IS NULL` → should fail | NULL shift_id rejected | Step 5 |
| 4 | **Fix Q6 inequality** | [03_queries.sql:64](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/03_queries.sql#L64) | Step 2 | Run Q6 → shift 2 should show variance from shift 1's closing | Shift 2 rows appear | Step 7 |
| 5 | **Fix Txn A (change student)** | [04_transactions.sql:7-8](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/04_transactions.sql#L7-L8) | Step 2 | Run Txn A → booking created | No trigger error | Steps 6, 7 |
| 6 | **Fix Txn D (16:00 timing)** | [04_transactions.sql:38](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/04_transactions.sql#L38) | Step 2 | Run Txn D after 16:00 demo date → marks absences | Correct rows updated | Step 7 |
| 7 | **Fix Txn E (relabel or rework)** | [04_transactions.sql:42-52](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/04_transactions.sql#L42-L52) | Step 2 | Run Txn E → clear narrative match | Comment matches behaviour | Step 9 |
| 8 | **Write `06_failure_tests.sql`** | New file in campus_pantry_sql/ | Step 2 | Run all tests → each should fail as expected | 5–6 expected-error scenarios | Step 9 |
| 9 | **Run complete SQL workflow and capture screenshots** | 01 → 02 → 02b → 03 → 04 → 05 → 06 | Steps 3–8 | All scripts execute; screenshot each result | Evidence for report Part 4 | Step 11 |
| 10 | **Test Python prototype** | cli.py | Step 2, psycopg2 installed | `python cli.py` → log in as student/staff → test each menu option | All workflows complete without errors | Step 11 |
| 11 | **Run concurrency demo** | concurrency_demo.py | Steps 9, 10 | `python concurrency_demo.py 14 15` (future sessions) | Round 1: both succeed; Round 2: second rejected | Step 12 |
| 12 | **Write the report** | New PDF document | Steps 9–11 | Review against §4 requirements | Parts 1–4 complete with screenshots | Step 13 |
| 13 | **Record prototype video** | Screen recording | Step 10 | Demonstrate all CLI workflows | Video shows booking, check-in, cancel, no-show, stock, reports | Step 14 |
| 14 | **Create poster, participation statement, AI-use declaration** | New documents | Step 12 | Review against checklist | All administrative deliverables complete | Submission |

### E. First Work Session — Five Concrete Actions

1. **Verify PostgreSQL is installed and accessible:**
   ```powershell
   psql -U postgres -c "SELECT version();"
   ```
   If PostgreSQL is not installed, install it first (download from postgresql.org).

2. **Create the database and run the rebuild script:**
   ```powershell
   psql -U postgres -c "CREATE DATABASE campus_pantry;"
   psql -U postgres -d campus_pantry -f "c:\Users\loq\Desktop\USYD\Sem 1\DBMS\Project\campus_pantry_app\sql\rebuild_campus_pantry.sql"
   ```
   Check for errors. The rebuild script drops any existing schema and creates everything fresh.

3. **Run the validation script to check initial state:**
   ```powershell
   psql -U postgres -d campus_pantry -f "c:\Users\loq\Desktop\USYD\Sem 1\DBMS\Project\campus_pantry_sql\05_validation.sql"
   ```
   All checks should return 0 rows (except checks 1, 11, 12 which are informational).

4. **Start the Python prototype:**
   ```powershell
   cd "c:\Users\loq\Desktop\USYD\Sem 1\DBMS\Project\campus_pantry_app"
   .venv\Scripts\activate
   $env:PGUSER="postgres"; $env:PGPASSWORD="<your-password>"; python cli.py
   ```
   Log in as `zhex6714` (student) → view sessions → book a session. Then log in as `must2203` (staff) → check in a QR token → view reports.

5. **Read through `04_transactions.sql` while the database is live:**
   Open [04_transactions.sql](file:///c:/Users/loq/Desktop/USYD/Sem 1/DBMS/Project/campus_pantry_sql/04_transactions.sql) in pgAdmin's Query Tool and try running each transaction (A through F) one at a time. **Txn A will fail** — this confirms Issue #6 in a live environment. Note the error for your report.

### F. Questions for Your Teammate

1. **Has any of this SQL been run in PostgreSQL at all, even partially?** The task list says no, but confirm — any partial test results or pgAdmin history would save time.
2. **Which students should be in Txn A?** The current demo uses zhex6714 who already has a booking. Was this intentional to show the trigger rejection, or should it use a different student?
3. **Are shift_stock_count and stock_adjustment supposed to be on the ERD?** They're in the schema and the Complete Revised Project document but missing from ERD.pdf. Did she plan to add them?
4. **What was the agreed interpretation of "exactly two staff per shift"?** Is it a hard database constraint (trigger) or an application-level check? The validation query in 05_validation.sql detects violations but doesn't prevent them.
5. **Did she already start a report draft anywhere (Google Docs, Overleaf, etc.)?** The Complete Revised Project PDF has substantial content that could be adapted for Parts 1–3.
6. **What percentage split should the participation statement use?** This needs agreement from all team members.
7. **Is the `setup_all_01_02.sql` file still needed?** It's a duplicate of running 01 + 02 and doesn't include the fixes. The `rebuild_campus_pantry.sql` script supersedes it.

---

> [!TIP]
> The codebase is in much better shape than a typical handoff. The core architecture is sound, the SQL is well-structured, and the Python prototype covers all essential workflows. The remaining work is primarily: **fix 5 small SQL bugs → write failure tests → execute everything → capture screenshots → write the report → record the video.** The heaviest lift is the report, not the code.
