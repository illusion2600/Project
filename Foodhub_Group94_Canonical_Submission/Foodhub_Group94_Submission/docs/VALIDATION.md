# Release validation

Executed on 24 October 2026 against PostgreSQL 16.15, Python 3.12.14, psycopg2-binary 2.9.10 and Windows 11. These are observations from this release, not carried-over claims from the original project.

| Run | Started (UTC) | Passed | Suite time | Database removed |
| --- | --- | --- | --- | --- |
| 1 | 2026-10-24T09:37:26.717879+00:00 | 44/44 | 9.8281s | yes |
| 2 | 2026-10-24T09:37:37.607533+00:00 | 44/44 | 9.1163s | yes |

Each run had zero failures, errors and skipped tests. Each created a different randomly named owned database. Full named results and runtime metadata are in `evidence/test-results-run-1.json` and `test-results-run-2.json`; matching `test-run-1.txt` and `test-run-2.txt` contain captured output. Tests include ten coordinated concurrency scenarios; these are bounded regressions, not a performance/load certification.

## Additional handover checks

Both `campus_pantry_sql/setup_all_01_02.sql` and `campus_pantry_app/sql/rebuild_campus_pantry.sql` were executed with real psql in separate disposable databases. First initialization succeeded. Second initialization refused the existing schema, and all 29 seed people remained present. Both databases were removed. An actual CLI subprocess signed in as the synthetic staff identity, displayed latest stock and exited successfully. See `evidence/handover-checks.json` and `evidence/cli-smoke-transcript.txt`.

`showcase.py` then completed its full service workflow with a 20-unit stock reconciliation and verified database removal. The captured output is `docs/showcase-transcript.txt`. Its clock is intentionally simulated and labelled; the ordinary CLI uses the actual Sydney business clock.

## What the tests assert

- Capacity at exactly 50 places, one standard booking per student/day, cancellation, token uniqueness and audited override updates.
- Attendance metadata, same-date validity, 10:00/16:00 boundaries, repeated scan idempotence, same-day late arrival after shift closure and no-show timing.
- Active staff/volunteer checks, request/review lifecycle, invalid staff-role input, and safe repeated assignments/role correction.
- Concurrent last-place claims, same-student requests, staff/volunteer overlaps, mixed SQL/service access, duplicate opening counts and competing decisions. Separate connections synchronize with barriers; unrelated errors, deadlocks and timeouts are not accepted as expected business rejections.
- Genuine opening observations, atomic closing, missing/duplicate counts, exact receipt/waste arithmetic, insufficient stock and closed-history protection.
- Parent schedule/capacity edits and batch-product relationships, all twelve analytic groups/thirteen result sets, and full table-row comparison around rolled-back SQL examples. The SQL failure suite contains 23 explicit assertions. Sequences may advance despite row rollback, by PostgreSQL design.
- Invalid date recovery in the actual staff-menu logic, database query error translation, and test configuration isolation from a normal application database name.

## Reproduce

Follow the root README to install requirements and configure explicit TEST_PG target settings with a CREATEDB-capable role. Run `python tests/run_tests.py --report my-results.json` and `python showcase.py`. Never direct old prototype cleanup scripts at an existing application database. The revised runner generates its own target and verifies an ownership marker before cleanup.

## Limits

Tests validate the specified scenarios, not every possible schedule, OS, PostgreSQL version or deployment. No live authentication, email, QR image/scanner integration, hosted deployment, backup/restore drill, migration or load benchmark was tested or claimed. PostgreSQL owns the authoritative constraints; service-only clock/actor rules are not a security boundary against a direct database owner. The package is a fresh local submission/showcase installation.

For the canonical handover, host-specific output paths in text logs were normalized to relative package paths. Test outcomes and JSON evidence are unchanged.
