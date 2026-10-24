-- Legacy filename retained for compatibility: this now INITIALIZES a new database.
-- It never drops or rebuilds an existing schema. CREATE SCHEMA fails if it exists.
-- Keep campus_pantry_app and campus_pantry_sql as sibling directories.
-- Run: psql -X -v ON_ERROR_STOP=1 -d YOUR_NEW_DATABASE -f sql/rebuild_campus_pantry.sql
\set ON_ERROR_STOP on
\ir ../../campus_pantry_sql/setup_all_01_02.sql
