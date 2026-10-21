-- 01c_unikey_format.sql  (run after 01_schema.sql, before the seed data)
-- A University of Sydney UniKey is four lowercase letters followed by four digits,
-- e.g. abcd0123. Enforce that shape for every person (students, volunteers and staff).
SET search_path = campus_pantry, public;

ALTER TABLE person
    ADD CONSTRAINT person_unikey_format CHECK (unikey ~ '^[a-z]{4}[0-9]{4}$');
