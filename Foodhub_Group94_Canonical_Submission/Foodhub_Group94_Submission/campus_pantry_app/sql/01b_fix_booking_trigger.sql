-- Retired prototype patch: this file intentionally makes no schema changes.
-- All final rules are defined once in campus_pantry_sql/01_schema.sql.
-- Initialize a NEW database using campus_pantry_sql/setup_all_01_02.sql.
-- This is not an in-place migration for an existing prototype database.
DO $$ BEGIN
    RAISE NOTICE 'Retired prototype patch: no changes applied. Use the canonical setup in a new database.';
END $$;
