# Campus Pantry Prototype

A command-line Python prototype for the University of Sydney FoodHub booking and inventory management database (COMP9120 Database Management Systems group project).

Students book half-hour sessions and receive a QR check-in token. Staff check students in at the front desk, mark no-shows after the 16:00 close of the operating day, view assigned shifts and rosters, set up daily shifts and sessions, record physical stock counts and adjustments, and inspect analytical reports. Every operation directly executes parameterized SQL against the live PostgreSQL database.

---

## 1. Prerequisites and Installation

- **Python 3.10+** (tested on Python 3.13)
- **PostgreSQL 15+** (tested on PostgreSQL 16)
- **psycopg2-binary**

```bash
# Navigate to the app directory
cd campus_pantry_app

# Create and activate virtual environment (optional but recommended)
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 2. Database Configuration

Connection parameters are read dynamically from standard environment variables (no hardcoded passwords in code):

| Variable | Default Value | Description |
|---|---|---|
| `PGHOST` | `localhost` / `127.0.0.1` | PostgreSQL database host |
| `PGPORT` | `5432` (or `5433` for custom instance) | PostgreSQL port |
| `PGDATABASE` | `campus_pantry` | Target database name |
| `PGUSER` | Current OS login (or `postgres`) | Database username |
| `PGPASSWORD` | (prompted if needed) | Database password |

**Example Windows PowerShell:**
```powershell
$env:PGHOST="127.0.0.1"
$env:PGPORT="5433"
$env:PGUSER="postgres"
$env:PGDATABASE="campus_pantry"
python cli.py
```

**Example macOS/Linux Bash:**
```bash
PGHOST=127.0.0.1 PGPORT=5433 PGUSER=postgres PGDATABASE=campus_pantry python3 cli.py
```

---

## 3. Database Initialisation & Rebuild

To initialize or completely rebuild the disposable project database from scratch:

```powershell
psql -h 127.0.0.1 -p 5433 -U postgres -d campus_pantry -f sql/rebuild_campus_pantry.sql
```

This single command:
1. Drops existing `campus_pantry` schema with CASCADE.
2. Recreates schema, sequences, tables, constraints, triggers, and views (`01_schema.sql`).
3. Seeds synthetic students, staff, volunteers, shifts, sessions, bookings, batches, and counts (`02_seed_data.sql`).
4. Automatically synchronizes all 8 identity/serial sequences past seeded IDs.

---

## 4. Running the Application and Tests

### A. Interactive CLI
```bash
python cli.py
```
- **Login as Student:** enter `alex1001`, `chen7061`, `kara7408`, etc.
- **Login as Staff:** enter `must2203`, `part2550`, `haim2897`, or `jaim3244`.
- **Login with Overlapping Roles:** enter `kevi5326` (Student + Volunteer).

### B. Automated 17-Rule Business Test Suite
```bash
python test_all_rules.py
```
Executes all 17 required business rules (boundary capacity, concurrency, admin override, QR scan idempotency, 16:00 no-shows, staffing triggers, and analytical queries) and outputs a markdown summary table.

### C. Concurrency Race Condition Demo
```bash
python concurrency_demo.py 5 6
```
Demonstrates that two concurrent requests for the same student or for the final session space are safely serialized using row-level locking (`SELECT ... FOR UPDATE`), preventing double-booking and overselling.

---

## 5. Architectural Structure

```text
campus_pantry_app/
├── cli.py                  # User interface menus, input validation, and tables
├── services.py             # Business transaction layer with row locking & atomic rollbacks
├── db.py                   # Database connection pooling & friendly constraint error mapping
├── concurrency_demo.py     # Live multi-threaded race condition demonstration
├── test_all_rules.py       # Automated 17-test verification suite
├── requirements.txt        # psycopg2-binary dependency
├── README.md               # App documentation
└── sql/
    ├── rebuild_campus_pantry.sql   # One-shot database schema and seed builder
    ├── 01b_fix_booking_trigger.sql # Standalone trigger patch (included in schema)
    ├── 01c_unikey_format.sql       # Standalone UniKey regex check (included in schema)
    └── 02b_sync_sequences.sql      # Standalone sequence sync script (included in seed)
```
