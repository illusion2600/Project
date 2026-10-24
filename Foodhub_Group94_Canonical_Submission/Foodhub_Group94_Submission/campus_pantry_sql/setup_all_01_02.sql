-- Canonical fresh-database setup for psql. Stops at the first error.
-- This never drops an existing schema. Use a new disposable database for a new demo.
-- Run: psql -X -v ON_ERROR_STOP=1 -d YOUR_NEW_DATABASE -f setup_all_01_02.sql
\set ON_ERROR_STOP on
\ir 01_schema.sql
\ir 02_seed_data.sql
