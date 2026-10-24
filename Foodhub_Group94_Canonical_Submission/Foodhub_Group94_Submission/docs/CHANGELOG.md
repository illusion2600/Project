# Completed changes and rationale

Release date: 24 October 2026. Scope: university submission/showcase. Baseline: supplied Foodhub_project.zip. Names: Ziyue Wu, Nikhil Khatri, Samowel Aboud (Group 94).

## C01 - Genuine stock observations

Before: recording a closing count first invented an equal opening; an adjustment could invent a zero opening. Completed: require a real opening before either action; reject duplicate openings/closings; commit the observed count and summary together. Why: inferred dispensing must not be based on fabricated observations. Files: services.py, tests/test_release.py.

## C02 - Reconciliation and closed inventory

Completed: positive whole-number adjustments require a reason, cannot exceed available stock as waste, and cannot follow a closing count. Closing cannot exceed opening plus receipts minus waste. A shift cannot close with an unfinished count or negative estimated dispensing. Database triggers protect closed stock records against INSERT/UPDATE/DELETE. Why: prevent impossible balances and preserve completed shift stock reports. Files: services.py, 01_schema.sql.

## C03 - Complete shift workflow

Before: the menu created PLANNED shifts but offered no supported way to open/close them. Completed: staff actions for PLANNED -> OPEN -> CLOSED, active staffing checks, upcoming-shift listing and per-shift reconciliation reporting. Reopening is rejected. Why: the full operating workflow is now possible without manual SQL. Files: cli.py, services.py, 01_schema.sql.

## C04 - Scheduling and staffing integrity

Completed: shift/session schedules and session parent linkage are immutable; capacity cannot be lowered below current noncancelled bookings. Staff changes are allowed only while PLANNED, preserving required staffing after opening. Repeated same-key assignment and valid role correction while PLANNED work without false overlap errors. Why: parent edits and assignment deletion must not invalidate previously valid child data. Files: 01_schema.sql, services.py.

## C05 - Booking-date attendance and late arrivals

Before: an old confirmed token could check in on a later date. Completed: check booking date and the 10:00 inclusive-16:00 exclusive Sydney window before idempotence; reject unopened shifts. Accept a same-day late arrival even after its original shift has CLOSED, preserving the supplied operating policy. Only mark no-shows at/after day end. Why: prevent stale attendance without penalising permitted late arrivals. Files: services.py, tests/test_release.py.

## C06 - Audited overrides and attendance metadata

Before: an early trigger return could bypass override validation on UPDATE. Completed: always validate override actor/reason consistency; ordinary bookings cannot retain override audit fields. Overrides do not bypass capacity. Attendance timestamp exists if and only if status is ATTENDED. Why: updates must satisfy the same rules as inserts and leave consistent evidence. Files: 01_schema.sql, services.py.

## C07 - Concurrency and transaction order

Completed: consistent student-then-session locks for booking; shared staff/volunteer row locks before overlap decisions; ordered affected-record locks; shift locks coordinate closing and inventory. Queries and writes use transaction boundaries with rollback and limited retries for PostgreSQL serialization/deadlock errors. Why: simultaneous requests must not both claim the last place or overlapping duty. Files: 01_schema.sql, services.py. Bounded race tests demonstrate targeted cases, not arbitrary load capacity.

## C08 - Purchase/batch relationship

Before: changing a purchase line's product could leave a batch pointing to the wrong product. Completed: composite foreign key (purchase_line_id, product_id) references a matching unique purchase-line key. Why: declarative referential integrity covers both parent and child updates. File: 01_schema.sql.

## C09 - Active roles and volunteer decisions

Completed: hide inactive roles and require an active acting staff member for privileged mutations/reports; validate volunteers at service entry. Review only a PENDING request, rejecting stale decisions, ended shifts and closed shifts. Why: inactive identities cannot continue through an old portal, and one reviewer cannot overwrite another's decision. Files: services.py, cli.py. UniKey selection remains simulated authentication.

## C10 - Recoverable input and menu errors

Before: a malformed volunteer-filter date could escape the menu's error handler; an invalid staffing choice defaulted to assistant. Completed: strict calendar-date parsing, consistent database error translation and rollback, explicit menu-choice validation, friendly missing-schema/connection errors, and upcoming filters that omit ended shifts. Why: ordinary input errors must leave the menu and transaction usable. Files: cli.py, services.py, db.py.

## C11 - Predictable connections and targeted indexes

Completed: one configured endpoint, no silent port fallback, five-second default connection timeout and bounded database waits. Pinned psycopg2-binary 2.9.10. Added/revised indexes for latest-count ordering and staff/volunteer overlap lookups. Why: configuration failures are explainable and repeated lookup predicates have suitable indexes. Files: db.py, requirements.txt, 01_schema.sql. No measured throughput or latency improvement is claimed; no connection pool was added.

## C12 - Canonical, nondestructive setup

Before: legacy patches could overwrite the corrected booking trigger and rebuild scripts could destroy data. Completed: canonical schema/seed with ON_ERROR_STOP wrappers; existing schema makes initialization fail without dropping data. Legacy patches emit no-op notices. Seed loading follows the revised lifecycle. Why: a fresh installation always receives the same rules and accidental reruns preserve existing rows. Files: campus_pantry_sql and campus_pantry_app/sql. This is not a migration for an existing deployment.

## C13 - Isolated verification and safe cleanup

Before: tests used broad identifiers/prefixes for cleanup and could mutate seed/application records. Completed: explicit test target settings, random database names, ownership markers checked before teardown, per-test fixture reset only inside the owned database, and nonzero status if cleanup fails. Why: verification must not damage someone else's data. Files: tests/support.py, tests/run_tests.py; legacy test entrypoints now delegate safely.

## C14 - Assertions that prove their outcome

Before: some tests printed PASS in both branches, accepted any exception, used fixed dates or only executed analytics. Completed: named unittest assertions with expected errors and values, barrier-coordinated races with separate connections/timeouts, current-day fixtures and explicit clock-boundary tests. Validate all twelve query groups/thirteen result sets. Replace SQL failure tests with 23 specific assertions and compare all table rows before/after rollback scripts. Why: a green result now checks the intended rule, not merely absence of a crash. Files: tests, 04_transactions.sql, 05_validation.sql, 06_failure_tests.sql.

## C15 - Repeatable after-hours demonstration

Completed: showcase.py runs the real services in a disposable database at a clearly labelled simulated business time. It verifies booking, duplicate rejection, volunteer approval, attendance, shift closure and a 20-unit reconciliation, then proves cleanup. Why: the presentation works outside operating hours without weakening the normal CLI clock rules. Files: showcase.py, tests/support.py.

## C16 - Accurate handover and evidence

Completed: rewritten setup/use instructions, change report, captured test results and demo transcript, clear local-showcase scope, synthetic identities and AI acknowledgement. Removed old misleading documentation from the release package; did not reissue signatures or participation claims. Why: reviewers can reproduce results and distinguish implemented functionality from simulated integrations. No Canvas submission, email delivery or public deployment has occurred.

## Deliberate scope boundaries

Preserved: Python CLI/PostgreSQL stack, 16 tables, three views, twelve query groups, original synthetic seed identities and group context. Direct SQL owners can bypass service-only date/role policies; this package is not a least-privilege hosted service. Stock adjustments aggregate by shift/batch/kind and retain the latest reason, not a full event ledger. A shift with no stock rows can close. External authentication, mail/QR integration, backups, monitoring, security review, migration and load testing require separate work for real users. These are disclosed boundaries for the user-selected submission/showcase scope.
