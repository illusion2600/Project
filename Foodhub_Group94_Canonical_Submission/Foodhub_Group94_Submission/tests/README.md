# Integration tests

Run from the project root after installing `campus_pantry_app/requirements.txt`:

```powershell
$env:TEST_PGHOST = '127.0.0.1'
$env:TEST_PGPORT = '5432'
$env:TEST_PGUSER = 'your_test_role'
# Set TEST_PGPASSWORD privately if the PostgreSQL server requires a password.
python tests/run_tests.py
```

The role needs permission to create a database. `TEST_PGMAINTENANCE_DB` defaults
to `postgres`; `TEST_PGSSLMODE` defaults to `prefer`. Normal application `.env`
and `PGDATABASE` settings are ignored. The runner generates a unique database,
sets an ownership marker, and verifies that marker before removing only that
database. Each test reloads the canonical schema and seed within that sandbox.
Do not run the test module directly against a working database.

The suite covers service and database rules, INSERT/UPDATE/DELETE integrity,
capacity and daily booking limits, audited overrides, cancelled bookings,
Sydney attendance boundaries and same-day late arrivals after shift closure,
stock observation and reconciliation, staff and volunteer authorization,
lifecycle transitions, CLI recovery, 12 reporting groups (13 result sets),
the SQL regression scripts, and coordinated races using separate connections.
Concurrency assertions require the expected business error and fail on a
deadlock, timeout or unrelated exception. Database locks remain enabled.
These bounded scenarios verify targeted regressions; they are not a load test.

Dates derive from the current Sydney date. The internal service clock is mocked
only for time-boundary scenarios. The normal CLI has no simulated-time option.
All table rows are compared before/after the SQL rollback examples. PostgreSQL
identity sequences may advance across rollback, which is intentional behaviour.

`test-results.json` records each test's outcome and elapsed time, server version,
the generated database name, and whether cleanup succeeded. Failure produces a
nonzero exit code. To run only concurrency cases:

```powershell
python campus_pantry_app/concurrency_demo.py --report concurrency-results.json
```

The historical `campus_pantry_app/test_all_rules.py` entry point delegates to the
same safe runner. No original broad cleanup predicates or lock-disabling demo
remain. The shared `support.disposable_database(label='DEMO')` context manager
also isolates the scripted showcase.
