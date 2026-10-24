# Campus Pantry — FoodHub Booking, Attendance & Inventory Database

**COMP9120 Database Management Systems · Group 94 · University of Sydney**

Campus Pantry is a PostgreSQL database and Python command-line prototype for a campus food pantry such as the University of Sydney FoodHub. Students book 30-minute collection sessions and receive a check-in token; staff check students in, roster supervisors and volunteers, and record purchases, stock batches and physical stock counts. Business rules (50 places per session, one booking per student per day, exactly one supervisor and one assistant per open shift, no overlapping shifts, batch–purchase consistency) are enforced inside the database by constraints and triggers, so they also hold for SQL run outside the prototype.

This README explains how to build the database, run every submitted script and test, and walk through the prototype. Design rationale, ER/relational diagrams and normalisation analysis are in the project report.

---

## Contents

```text
.
├── README.md                          This guide
├── campus_pantry_sql/                 PostgreSQL implementation (run in numeric order)
│   ├── 01_schema.sql                  Schema campus_pantry: 16 tables, keys, CHECKs, triggers, indexes, 3 views
│   ├── 02_seed_data.sql               Synthetic data for one operating day (9 Oct 2026)
│   ├── 03_queries.sql                 12 management queries (Q1–Q12)
│   ├── 04_transactions.sql            Transaction scenarios A–F (booking, check-in, cancel, no-shows, stock count, rollback)
│   ├── 05_validation.sql              12 integrity checks
│   ├── 06_failure_tests.sql           10 negative / boundary tests (each prints [PASS] or stops with [FAIL])
│   ├── setup_all_01_02.sql            01 + 02 in one file
│   └── 07_migration_volunteer_workflow.sql   Only for databases built before the volunteer workflow; not needed on a fresh build
├── campus_pantry_app/                 Python prototype
│   ├── cli.py                         Menu-driven interface for students, volunteers and staff
│   ├── services.py                    One function per operation; each write is one transaction
│   ├── db.py                          Connection settings (PG* environment variables) and error messages
│   ├── test_all_rules.py              17 automated end-to-end tests, including a concurrency race
│   ├── concurrency_demo.py            Two simultaneous bookings by the same student
│   ├── requirements.txt               psycopg2-binary
│   └── sql/rebuild_campus_pantry.sql  Drops and rebuilds the schema with seed data (01 + 02); use it to reset
└── campus_pantry_*.md                 Poster, video script, participation and AI-use declarations
```

The files `campus_pantry_app/sql/01b_…`, `01c_…` and `02b_…` are earlier patches whose changes are already included in `01_schema.sql` and `02_seed_data.sql`; you do not need to run them.

---

## 1. Requirements

| Software | Version | Check with |
|---|---|---|
| PostgreSQL server and `psql` client | 15 or later (tested on 16) | `psql --version` |
| Python | 3.10 or later (tested on 3.13) | `python3 --version` (Windows: `py --version`) |

---

## 2. Connection settings

Set these once in each new terminal window. Every command below, and the Python prototype, reads them, so no `-h/-p/-U/-d` flags are needed.

**macOS / Linux**

```bash
export PGHOST=localhost
export PGPORT=5432               # change if your server uses another port
export PGUSER=postgres           # Homebrew/Postgres.app on macOS: usually your macOS login name
export PGDATABASE=campus_pantry
# export PGPASSWORD=...          # only if your server asks for a password
```

**Windows (PowerShell)**

```powershell
$env:PGHOST="localhost"
$env:PGPORT="5432"
$env:PGUSER="postgres"
$env:PGDATABASE="campus_pantry"
$env:PGPASSWORD="your-password"   # the password chosen when PostgreSQL was installed
```

Check the connection (this uses the default `postgres` database, which always exists):

```bash
psql -d postgres -c "select version();"
```

---

## 3. Build the database

Run from the repository root:

```bash
createdb campus_pantry
psql -v ON_ERROR_STOP=1 -f campus_pantry_sql/01_schema.sql
psql -v ON_ERROR_STOP=1 -f campus_pantry_sql/02_seed_data.sql
psql -c "select count(*) as bookings from campus_pantry.booking;"
```

Expected: no `ERROR` lines, and the last command prints **15**.

`-v ON_ERROR_STOP=1` makes `psql` stop at the first error, so only the real cause is shown.

**Rebuilding or resetting.** `01_schema.sql` expects an empty database. If the schema already exists (or after running the tests, which change data), reset everything with:

```bash
psql -v ON_ERROR_STOP=1 -f campus_pantry_app/sql/rebuild_campus_pantry.sql
```

This drops the `campus_pantry` schema and rebuilds it with the seed data.

---

## 4. Run the SQL deliverables

Run in this order, on a freshly built database:

| Command | What it shows | Expected result |
|---|---|---|
| `psql -f campus_pantry_sql/03_queries.sql` | Q1–Q12 management queries | Q1: 24 rows. Q2: Rice 1 kg first (57). Q6: one row, rice +2 at shift 2 with a reason. Q9: purchases totalling $1,050. Q4, Q7, Q11 and Q12 return 0 rows on the seed data (no product is below its threshold, every product was dispensed, no batch expires within 30 days of the run date, no session is ≥ 80% full). |
| `psql -f campus_pantry_sql/04_transactions.sql` | Transactions A–F, each in its own `BEGIN … COMMIT/ROLLBACK` | `INSERT`/`UPDATE` counts for A–E, then `UPDATE 0` and `ROLLBACK` for F. **This script changes the seed data.** |
| `psql -f campus_pantry_sql/05_validation.sql` | Integrity checks | Violation checks return 0 rows. Check 4 lists one student (`zhex6714`) with two bookings on one day: the second was created by transaction A2 with an authorised admin override, so it is listed for review, not as a violation. |
| `psql -f campus_pantry_sql/06_failure_tests.sql` | 10 invalid operations that must be rejected | Ten `[PASS]` notices, then "All failure & boundary tests completed successfully!" Each test removes its own test data. |

Tip: add `| less` to page through long output (`q` to quit).

---

## 5. Python prototype and automated tests

```bash
cd campus_pantry_app
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

| Command | Expected result |
|---|---|
| `python3 test_all_rules.py` | 17 lines `[PASS]` and `Total Tests: 17 | Passed: 17 | Failed: 0`. The suite creates and deletes its own test data and can be run repeatedly. It does mark the past seed bookings of 9 Oct as ABSENT (that is test 13). |
| `python3 concurrency_demo.py 5 6` | Two simultaneous bookings by one student for sessions 5 and 6. In both rounds request 1 is booked and request 2 is rejected with "Student already has an active booking on this date": the booking trigger locks the student row itself, so the rule holds even when the application does not lock. The script cancels its own bookings at the end. |

On Windows use `py` instead of `python3`.

---

## 6. Prototype walkthrough

Reset the data first so the seed bookings are back in their original state, then start the CLI:

```bash
psql -v ON_ERROR_STOP=1 -f sql/rebuild_campus_pantry.sql     # from inside campus_pantry_app
python3 cli.py
```

At the `UniKey` prompt type an account below; inside a menu, `0` goes back, and an empty UniKey quits.

| UniKey | Roles | Try |
|---|---|---|
| `must2203`, `haim2897`, `jaim3244`, `part2550` | Staff | Front desk, rosters, volunteer approval, stock, reports |
| `alex1001`, `chen7061` | Student | View sessions, book, my bookings, cancel |
| `kevi5326` | Student + Volunteer | Shows the role chooser; request a volunteer shift |
| `nikh3591`, `aary6367` | Volunteer | Request / withdraw shift requests |

**Important:** the seed data only covers **9 October 2026**, and a session can only be booked before it ends. Create sessions for the day you are testing first.

1. **Open a day (staff).** `must2203` → option **9** → press Enter for today, or type tomorrow's date (`YYYY-MM-DD`) if you are testing after 16:00, when all of today's sessions have ended. Expected: "Created 3 shifts and 12 sessions". The new sessions are numbered from 13.
2. **Book (student).** `alex1001` → **1** → the date you opened (Enter = today) to list sessions and places left → **2** → a session that has not finished yet. Expected: "Booking … confirmed. Your QR code token: …". Booking a second session the same day is rejected ("Student already has an active booking on this date").
3. **Check in (staff).** `must2203` → **1** → paste the token → "Checked in booking …". Scanning the same token again is rejected ("this booking is ATTENDED"). Check-in is only allowed for today's or past sessions, so if you are testing after 16:00, use a seed token instead: `DEMO-QR-001` … `DEMO-QR-015` (9 Oct bookings, valid after a reset).
4. **Admin override (staff).** Option **3** → `alex1001` → another session → a reason. Accepted despite the one-per-day rule, and the approving staff member and reason are stored. An empty reason is rejected.
5. **Volunteer workflow.** `kevi5326` → Volunteer portal → **1** lists shifts (after a reset, the day opened in step 1 has shifts 4–6) → **2** request one → status PENDING. Then `must2203` → **7** → Enter, Enter (lists pending requests) → **1** approve → the volunteer's UniKey and the shift ID. Option **6** shows the roster with the volunteer added.
6. **Stock.** `must2203` → **12** latest count per batch → **13** record a count (e.g. `STK-000008`, `SPOT_CHECK`, `2`, blank shift) → **15** low-stock report now lists *Apple bag*. For receipt/waste adjustments (**14**), record the shift's opening count first.
7. **No-shows.** Option **4** marks every still-confirmed booking whose day has closed (after 16:00) as ABSENT; running it again reports 0.

Staff menu reference: 1 check-in · 2 bookings for a session · 3 admin-override booking · 4 mark no-shows · 5 my shifts · 6 roster · 7 volunteer requests · 8 assign staff to a shift · 9 open a day · 10 day attendance summary · 11 sessions near capacity · 12 latest stock · 13 record a count · 14 receipt/waste adjustment · 15 low stock.

---

## 7. Troubleshooting

| Message | Cause and fix |
|---|---|
| `database "campus_pantry" does not exist` | Run `createdb campus_pantry` (Section 3). |
| `connection refused` / `role "postgres" does not exist` | Wrong `PGPORT` or `PGUSER`; see Section 2. On macOS with Homebrew, `PGUSER` is usually your login name. |
| `password authentication failed` or a password prompt | Set `PGPASSWORD`, or type the password when `cli.py` asks for it. |
| `relation "person" already exists`, `duplicate key value … person_pkey` | The schema was already built. Reset with `rebuild_campus_pantry.sql` (Section 3). |
| `dropdb: database "campus_pantry" is being accessed by other users` | pgAdmin or another `cli.py` is connected. Close it, or reset with the rebuild script instead, which drops only the schema. |
| `Session … has already finished` / empty session list | No sessions for that day yet, or the session has ended. Open a day with staff option 9 (Section 6, step 1). |
| `Cannot check in: this booking is ABSENT` for a `DEMO-QR-…` token | `04_transactions.sql`, `test_all_rules.py` or option 4 already marked it ABSENT. Reset the data. |
| `ModuleNotFoundError: No module named 'psycopg2'` | Activate the virtual environment and run `pip install -r requirements.txt` (Section 5). |

---

## 8. Known limitations

These are discussed in the report (Sections 3.5 and 4.5):

- Changing a shift's date after its sessions were created does not move the sessions; shift times are treated as fixed once sessions exist.
- Q11 lists batches expiring in the next 30 days; batches that have already expired are not included.
- Receipt/waste adjustments keep one row per shift, batch and type: quantities are added together and the latest reason is kept.
- Login is by UniKey only, the check-in "QR code" is a text token typed at the front desk, and no emails are sent.
