# Campus Pantry — Python prototype

A command-line prototype that connects to the Campus Pantry PostgreSQL database and lets students, volunteers and staff carry out the system's main operations.

**Setup, run commands and a step-by-step walkthrough are in the [main README](../README.md)** (build the database first, Sections 2–3). In short, from this folder:

```bash
python3 -m venv .venv && source .venv/bin/activate      # Windows: py -m venv .venv; .venv\Scripts\activate
pip install -r requirements.txt
python3 cli.py
```

---

## How the code is organised

| File | Responsibility |
|---|---|
| `cli.py` | Menus, input prompts and table output. Holds no SQL and no business rules. |
| `services.py` | One function per operation (book, cancel, check in, approve a volunteer, record a count, …). Every function that writes runs as **one transaction**: `with conn:` commits when the function finishes and rolls back if any step raises. |
| `db.py` | Opens the connection from the standard `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE` and `PGPASSWORD` environment variables (tries ports 5432 and 5433 if `PGPORT` is unset; asks for a password if needed) and turns database errors into readable messages. |
| `test_all_rules.py` | 17 end-to-end tests through `services.py`, including a two-thread race for the last place in a session. Creates and removes its own test data. |
| `concurrency_demo.py` | Two simultaneous bookings by the same student (`python3 concurrency_demo.py 5 6`). |
| `sql/rebuild_campus_pantry.sql` | Drops and rebuilds the schema with seed data; use it to reset before a demo. |
| `sql/01b_…`, `01c_…`, `02b_…`, `07_…` | Earlier patches and a migration for old databases. Their changes are already in `../campus_pantry_sql/01_schema.sql` and `02_seed_data.sql`; not needed on a fresh build. |

### Where the rules are enforced

The rules live in the database, not in Python, so they also hold for SQL run directly in `psql` or pgAdmin:

- **Capacity (50 per session) and one active booking per student per day:** trigger `validate_booking()`, which locks the session and student rows (`SELECT … FOR UPDATE`) before counting, so concurrent bookings are serialised.
- **Staffing (one supervisor and one assistant before a shift opens), no overlapping shifts, sessions inside their shift, batch/purchase-line product match:** triggers in `01_schema.sql`.
- **Keys, value ranges, status values, UniKey format:** PRIMARY KEY, UNIQUE, FOREIGN KEY and CHECK constraints.

`services.py` additionally locks the student row before booking and checks inputs (e.g. a session that has already finished), so the user gets a clear message before the database is asked to reject anything.

---

## What each role can do

After `python3 cli.py`, log in with a UniKey (4 lowercase letters + 4 digits). A person with several roles first chooses a portal.

| Role | Menu options |
|---|---|
| **Student** (`alex1001`, `chen7061`) | View sessions and places left for a date · Book a session (returns a check-in token) · My bookings · Cancel a booking |
| **Volunteer** (`nikh3591`, `aary6367`; `kevi5326` is also a student) | View scheduled shifts · Request to join a shift (PENDING) · View my requests and their status · Withdraw a pending request |
| **Staff** (`must2203`, `haim2897`, `jaim3244`, `part2550`) | 1 Check in a token · 2 Bookings for a session · 3 Special booking with admin override · 4 Mark no-shows after the 16:00 close · 5 My shifts · 6 Shift roster · 7 Approve/reject volunteer requests · 8 Assign staff to a shift · 9 Set up a day's 3 shifts and 12 sessions · 10 Day attendance summary · 11 Sessions near capacity · 12 Latest stock counts · 13 Record a stock count · 14 Record a receipt/waste adjustment · 15 Low-stock report |

The seed data covers 9 October 2026 only. Before booking, open a day with staff option 9 (see the main README, Section 6).
