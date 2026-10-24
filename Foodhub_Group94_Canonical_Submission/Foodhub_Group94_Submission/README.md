> Canonical package index: see START_HERE.md for the report, poster, video and contribution summary.

# Campus Pantry - FoodHub final submission release

Group 94: Ziyue Wu, Nikhil Khatri and Samowel Aboud.

A hardened **university submission and showcase** release of the supplied Python CLI and PostgreSQL project. It retains the 16-table design, three views and twelve analytical query groups. It fixes the reviewed correctness and concurrency defects, completes operational menus, and supplies repeatable tests and an after-hours demonstration.

UniKey selection is simulated authentication: knowing a staff UniKey is sufficient to select that identity. Tokens are displayed in the terminal. There is no email delivery, QR image generation, camera scanner or university SSO. This package is for local educational use with synthetic data, not a public service with real student records.

## Fastest showcase

Install Python 3.12 and a running PostgreSQL server (tested with PostgreSQL 16.15). Ensure `python`, `createdb` and `psql` refer to these installations. Tests and the disposable showcase require a PostgreSQL role with `CREATEDB` permission. Use your local credentials; never commit passwords.

From this extracted folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:TEST_PGHOST = '127.0.0.1'
$env:TEST_PGPORT = '5432'
$env:TEST_PGUSER = 'postgres'
$testCredential = Get-Credential -UserName $env:TEST_PGUSER -Message 'Local PostgreSQL password'
$env:TEST_PGPASSWORD = $testCredential.GetNetworkCredential().Password
.\.venv\Scripts\python.exe showcase.py
.\.venv\Scripts\python.exe tests/run_tests.py
Remove-Item Env:TEST_PGPASSWORD
```

On macOS/Linux, create/activate the environment with `python3 -m venv .venv` and `source .venv/bin/activate`; install `requirements.txt`. Export the same `TEST_PGHOST`, `TEST_PGPORT` and `TEST_PGUSER` values. Supply a local `.pgpass` file with PostgreSQL's required permissions or a process-scoped `TEST_PGPASSWORD`. Run `python showcase.py` and `python tests/run_tests.py`.

The showcase creates a randomly named `campus_pantry_test_<24 hex digits>` database, loads canonical SQL and synthetic fixtures, exercises the actual services, then removes only that owned database after checking an ownership marker. It does not read or reset `PGDATABASE`. A clearly labelled simulated business clock (10 October 2026, 10:15 Sydney) makes the demo work after hours. The normal CLI always uses PostgreSQL's actual Sydney clock.

The demo covers three shifts/twelve sessions, staffing/opening, booking/duplicate rejection, volunteer approval, attendance and stock reconciliation: `100 + 10 - 2 - 88 = 20` estimated units dispensed.

## Interactive application

Create a **new dedicated database**. Setup fails if the schema exists and never drops it. Keep any original project database and choose a different name. This release is a fresh install, not a migration of existing records.

```powershell
$env:PGHOST = '127.0.0.1'
$env:PGPORT = '5432'
$env:PGUSER = 'postgres'
$env:PGDATABASE = 'campus_pantry_showcase'
createdb -h $env:PGHOST -p $env:PGPORT -U $env:PGUSER $env:PGDATABASE
psql -X -v ON_ERROR_STOP=1 -d $env:PGDATABASE -f campus_pantry_sql/setup_all_01_02.sql
.\.venv\Scripts\python.exe campus_pantry_app/cli.py
```

The clients prompt for a password if needed, including the interactive Python CLI. For unattended use, supply standard PostgreSQL credentials or a process-scoped `PGPASSWORD`. There is no `.env` loader. The app connects to exactly `PGHOST:PGPORT`, without guessing another port. Standard libpq settings such as `PGSSLMODE` remain available. `PGCONNECT_TIMEOUT` accepts 1-60 seconds (default 5). `db.py` also limits statement, lock and idle-transaction waits.

Synthetic identities: staff `must2203`, assistant `part2550`, volunteer `nikh3591`, student `alex1001`. Seeds represent 9 October 2026 and are intentionally historical; old tokens cannot bypass today's check-in rules. In the staff menu, create a new day, assign one main supervisor and one assistant to each shift while PLANNED, then open it. Students can book a planned or open future session. Staff can check in a same-day booking after its original shift has opened, including a shift already CLOSED earlier that day.

## Operating rules

- Day: 10:00 inclusive to 16:00 exclusive, Australia/Sydney. Twelve half-hour sessions, maximum capacity 50. One standard active booking per student per day. Overrides require active staff and a nonblank reason; they never bypass capacity.
- Attendance: same booking date and operating window only, including late arrivals. Repeat valid scans are idempotent. No-shows are marked only after the operating day ends. Cancellation is allowed before the booked session ends.
- Lifecycle: PLANNED -> OPEN -> CLOSED, with no reopening. Opening requires exactly one active main supervisor and one active assistant. Staffing is frozen once opened; volunteer requests cannot change on a closed shift. Shift/session date, time and parent linkage are immutable; create a replacement record for scheduling corrections.
- Inventory: record a real OPENING before receipts, waste or CLOSING. Closing cannot exceed recorded available stock; adjustments cannot follow a closing count. Each recorded opening requires a closing count before closure. Closing freezes inventory records. A shift with no stock records may close; record every handled batch for a complete stock report.
- Dispensing is estimated from counts, not recorded per student: `opening + receipts - waste - closing`. Adjustments aggregate quantity by kind and retain the latest reason, so this is not a complete event audit ledger. Database owners can administer the schema; storage is not tamper-proof.

## Tests and SQL tools

`python tests/run_tests.py` creates an isolated database and resets fixtures only there. It writes `test-results.json` with named results, server version and verified cleanup. Failed tests/cleanup return nonzero. `--match substring` selects test IDs; `--report path.json` selects evidence output. Empty selections fail. The old `test_all_rules.py` entrypoint forwards to this safe runner. `concurrency_demo.py` runs synchronized concurrency tests. All require explicit `TEST_PGUSER`, not the application's credentials.

Read `docs/VALIDATION.md`, captured JSON results and `docs/showcase-transcript.txt` for executed evidence. Tests cover business rules, parent edits, rollback, exact analytics, CLI errors and synchronized separate-connection races. Arbitrary exceptions do not count as successful rule rejections.

Run standalone scripts with `psql -X -v ON_ERROR_STOP=1 -d campus_pantry_showcase -f <file>`:

| File in campus_pantry_sql | Purpose |
| --- | --- |
| 01_schema.sql / 02_seed_data.sql | Canonical fresh schema / historical synthetic seed |
| 03_queries.sql | Twelve query groups; thirteen SELECT result sets because Q8 has two |
| 04_transactions.sql | Rolled-back transaction demonstration |
| 05_validation.sql | Read-only validation |
| 06_failure_tests.sql | Expected-failure assertions, rolled back at the end |
| setup_all_01_02.sql | Safe psql initialization wrapper |

Row changes in demonstrations roll back, but PostgreSQL sequence increments do not. Prefer disposable tests. Legacy patch files are explanatory no-ops; do not apply original patches to this release. The old `rebuild_campus_pantry.sql` name now forwards to initialization and does not rebuild existing data.

## Package and acknowledgement

`docs/Foodhub_Changes_and_Validation.pdf` explains changes and their rationale; `docs/CHANGELOG.md` provides a searchable list. The original ZIP is untouched. Database clusters, binaries, credentials, caches and virtual environments are excluded. Original participation statements/signatures are not reissued as claims about this revision.

AI assistance acknowledgement: OpenAI Codex assisted with code review, implementation, tests and documentation for this revision. Group members should review and understand the changes and include this acknowledgement in their submission according to unit requirements. The group remains responsible for submitted work.
