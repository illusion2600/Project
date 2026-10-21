# Campus Pantry prototype

A command-line Python app for the FoodHub booking and inventory database (COMP9120 group project).
Students book half-hour sessions and receive a QR token. Staff check students in at the front desk,
mark no-shows, set up a day's shifts and sessions, record stock counts, and view reports.
Every operation reads and writes the PostgreSQL database directly; nothing is hard-coded.

## 1. Create the database

Create an empty database called `campus_pantry`, then run these scripts in order in pgAdmin's
Query Tool, or with `psql -d campus_pantry -f <file>`:

| Order | File | What it does |
| --- | --- | --- |
| 1 | `01_schema.sql` | Tables, constraints, triggers, views (schema `campus_pantry`) |
| 2 | `sql/01b_fix_booking_trigger.sql` | Proposed fix: booking trigger no longer blocks check-in / no-show updates |
| 3 | `sql/01c_unikey_format.sql` | CHECK constraint: UniKey must look like `abcd0123` |
| 4 | `02_seed_data.sql` | Synthetic sample data |
| 5 | `sql/02b_sync_sequences.sql` | Moves ID sequences past the sample IDs so new rows get free IDs |

Shortcut: `sql/rebuild_campus_pantry.sql` runs all five in order and first drops any existing
`campus_pantry` schema, so it also resets the sample data.

## 2. Install and run

```bash
cd campus_pantry_app
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python cli.py
```

Connection settings are read from environment variables (defaults in brackets):
`PGHOST` (localhost), `PGPORT` (5432), `PGDATABASE` (campus_pantry), `PGUSER` (your login name)
and `PGPASSWORD` (asked for if the server needs one). Example: `PGUSER=postgres python cli.py`.

UniKeys use the university format: 4 lowercase letters + 4 digits (e.g. `abcd0123`).
Sample logins (synthetic): students `zhex6714`, `chen7061`, `kara7408`, … `shre2225`;
staff `must2203`, `part2550`, `haim2897`, `jaim3244`. `kevi5326` is both a volunteer and a student.

## 3. What it does

| Role | Operation | Database feature shown |
| --- | --- | --- |
| Student | View sessions with live spaces left | View `v_booking_attendance` (JOIN + aggregation) |
| Student | Book a session | Multi-step transaction, row lock, trigger checks capacity and one booking per day |
| Student | My bookings / cancel | UPDATE with ownership and status checks |
| Staff | Front-desk QR check-in | Conditional UPDATE … RETURNING; a second scan is rejected |
| Staff | Special booking (admin override) | Override recorded with the staff member and reason |
| Staff | Mark no-shows | Bulk UPDATE, only after the 16:00 close of the operating day |
| Staff | Set up a day | One transaction creates 3 shifts and 12 sessions; all or nothing |
| Staff | Stock counts and reports | Inserts into `stock_count`; latest-count, low-stock and near-capacity reports |

## 4. Transactions and concurrency

`services.book_session` runs as one transaction: lock the student's row (`SELECT … FOR UPDATE`),
check the session, insert the booking. The booking trigger then locks the session row and enforces
capacity and the one-booking-per-day rule. If any step fails the whole transaction rolls back.

Without the student lock, two simultaneous requests from the same student for different sessions
can both pass the daily check before either commits, and both succeed. To show this:

```bash
python concurrency_demo.py 14 15     # two future sessions on the same day
```

Round 1 (no lock) books both sessions. Round 2 (with the lock) rejects the second request. The
script cancels its own test bookings afterwards.

## 5. Files

| File | Purpose |
| --- | --- |
| `cli.py` | Menus and input/output |
| `services.py` | Business operations, one function per user operation |
| `db.py` | Connection settings and readable error messages |
| `concurrency_demo.py` | Shows the double-booking race and the locking fix |
| `sql/` | Proposed fix scripts to run alongside the team's SQL |
