# Campus Pantry CLI

Use the top-level README.md for installation, safe database setup, demonstration accounts and testing. From the package root run:

    python campus_pantry_app/cli.py

The CLI uses standard PGHOST, PGPORT, PGDATABASE, PGUSER and PGPASSWORD configuration. UniKey selection is simulated login. Active-role checks guard staff actions; this is not real authentication.

Use `python showcase.py` for the isolated after-hours demonstration and `python tests/run_tests.py` for regression tests. These require explicit TEST_PG configuration and create owned disposable databases; they do not reset the interactive application's database.
