# Campus Pantry — University Food Pantry Database System

**COMP9120 Database Management Systems — Final Project Deliverables**  
**University of Sydney**

Campus Pantry is a comprehensive, PostgreSQL-backed scheduling, attendance, and inventory tracking system built for the University FoodHub charity. The system manages student session reservations, generates secure QR check-in tokens, tracks attendance and late arrivals, handles administrative overrides, enforces strict shift staffing requirements (1 supervisor + 1 assistant), and maintains end-to-end traceability of food purchases, batches, physical stock counts, and intra-shift waste/receipt adjustments.

---

## 1. Quick Start Guide

### Step 1: PostgreSQL Setup
Ensure PostgreSQL 15+ is running locally. Connection variables can be passed via environment variables (defaults shown):
```powershell
$env:PGHOST="127.0.0.1"
$env:PGPORT="5433"          # or 5432
$env:PGUSER="postgres"
$env:PGDATABASE="campus_pantry"
```

### Step 2: Database Initialization (Controlled SQL Order)
Execute the SQL scripts in order using `psql` or pgAdmin Query Tool:

```powershell
# 1. Schema Definition (Tables, NOT NULL constraints, Triggers, Views, Indexes)
psql -h 127.0.0.1 -p 5433 -U postgres -d campus_pantry -f campus_pantry_sql/01_schema.sql

# 2. Seed Data (Realistic Synthetic Population & Sequence Synchronization)
psql -h 127.0.0.1 -p 5433 -U postgres -d campus_pantry -f campus_pantry_sql/02_seed_data.sql

# 3. Analytical & Operational Reporting Queries (Q1–Q12)
psql -h 127.0.0.1 -p 5433 -U postgres -d campus_pantry -f campus_pantry_sql/03_queries.sql

# 4. Transaction Demonstrations (Booking, Check-in, Cancel, No-Show, Stock Count, Rollback)
psql -h 127.0.0.1 -p 5433 -U postgres -d campus_pantry -f campus_pantry_sql/04_transactions.sql

# 5. Database Integrity & Validation Invariant Checks (Checks 1–12)
psql -h 127.0.0.1 -p 5433 -U postgres -d campus_pantry -f campus_pantry_sql/05_validation.sql

# 6. Negative & Boundary Failure Testing Suite (10 Automated Tests)
psql -h 127.0.0.1 -p 5433 -U postgres -d campus_pantry -f campus_pantry_sql/06_failure_tests.sql
```

*(Convenience one-shot rebuild script: `psql -h 127.0.0.1 -p 5433 -U postgres -d campus_pantry -f campus_pantry_app/sql/rebuild_campus_pantry.sql`)*

---

## 2. Python Functional Prototype

The functional CLI prototype provides interactive menus for Students and Staff, as well as an automated 17-rule test suite and concurrency demo.

### Installation
```powershell
cd campus_pantry_app
py -m pip install -r requirements.txt
```

### Running the Interactive CLI
```powershell
py cli.py
```
- **Student Persona:** Log in with `alex1001` or `chen7061`. View sessions, book spots, retrieve QR tokens, and cancel bookings.
- **Staff Persona:** Log in with `must2203` or `haim2897`. Scan QR codes, view session attendee lists, view assigned shifts & rosters, record stock counts & adjustments, mark 16:00 no-shows, and inspect low-stock reports.
- **Overlapping Roles:** Log in with `kevi5326` (Student + Volunteer).

### Running Automated Business Rules Test Suite
```powershell
py test_all_rules.py
```
Verifies all 17 core database rules and prints a structured markdown summary table. **Result: 17/17 Passed (100%).**

### Running Concurrency Race Condition Demo
```powershell
py concurrency_demo.py 5 6
```
Demonstrates multi-threaded race conditions when booking the last space or double-booking, and proves how row-level locking (`SELECT ... FOR UPDATE`) guarantees serializability.

---

## 3. Project Directory Map

```text
Project/
├── README.md                           # Master project guide & deliverables index
├── campus_pantry_report.md             # Complete formal project report (Parts A, B, C, D)
├── campus_pantry_poster.md             # One-page conference/presentation poster
├── campus_pantry_video_script.md       # Maximum 3-minute video presentation plan & script
├── campus_pantry_participation.md      # Group participation statement (summing to 100%)
├── campus_pantry_ai_declaration.md     # University AI-use declaration
│
├── campus_pantry_sql/                  # Production PostgreSQL implementation
│   ├── 01_schema.sql                   # Relational schema, check constraints, triggers, views
│   ├── 02_seed_data.sql                # Synthetic seed fixtures + sequence resets
│   ├── 03_queries.sql                  # 12 analytical management queries (Q1–Q12)
│   ├── 04_transactions.sql             # 6 production transaction workflows (A–F)
│   ├── 05_validation.sql               # 12 integrity checks & invariant validations
│   ├── 06_failure_tests.sql            # Negative & boundary testing PL/pgSQL suite
│   └── setup_all_01_02.sql             # Consolidated schema + seed runner
│
└── campus_pantry_app/                  # Python functional prototype
    ├── cli.py                          # Terminal user interface
    ├── services.py                     # Business transaction service layer
    ├── db.py                           # PostgreSQL connection manager & error translator
    ├── concurrency_demo.py             # Multi-threaded concurrency safety demo
    ├── test_all_rules.py               # Automated 17-test verification suite
    ├── requirements.txt                # Python dependencies (psycopg2-binary)
    ├── README.md                       # Prototype technical notes
    └── sql/
        ├── rebuild_campus_pantry.sql   # Complete drop-and-rebuild script
        ├── 01b_fix_booking_trigger.sql # Trigger update logic
        ├── 01c_unikey_format.sql       # UniKey regex constraint
        └── 02b_sync_sequences.sql      # Sequence resynchronization
```

---

## 4. Key Engineering Fixes & Resolved Audits

1. **NOT NULL Session Shift Relationship:** `session.shift_id` is defined as `NOT NULL REFERENCES pantry_shift(shift_id)`, enforcing the ERD 1..1 cardinality.
2. **Shift Staffing Completeness Trigger:** Added `validate_shift_status()` trigger on `pantry_shift` preventing shifts from moving to `OPEN` or `CLOSED` unless exactly 1 `MAIN_SUPERVISOR` and 1 `ASSISTANT` are assigned.
3. **Database-Level Concurrency Protection:** Added `SELECT ... FOR UPDATE` row locks inside `validate_booking()` on both `session` (capacity serialization) and `student` (single daily booking serialization).
4. **Consecutive Shift Q6 Fix:** Corrected lateral join inequality in `03_queries.sql` to link back-to-back shifts whose end time equals the subsequent start time (`sh2.end_time <= cur_shift.start_time`).
5. **16:00 No-Show Timing:** Fixed transaction demonstration D and services to enforce no-show marking strictly after the daily 16:00 closing time.
6. **Stock Count Atomicity:** Transaction E records an atomic closing count event in `stock_count` and updates `shift_stock_count.closing_qty`.
7. **Identity Sequence Synchronization:** All 8 identity sequences automatically sync past manually seeded IDs.
8. **Negative Testing Suite:** Created `06_failure_tests.sql` covering 10 critical boundary and failure modes with transactional rollbacks.
