-- 01b_fix_booking_trigger.sql  (proposed fix — run after 01_schema.sql)
-- Problem: validate_booking() re-ran the capacity and one-per-day checks on EVERY status
-- update. A student with an admin-override second booking on the same day could then not
-- be checked in or marked ABSENT ("Student already has an active booking on this date").
-- Fix: only validate when a booking becomes active — on INSERT, when it moves to another
-- session or student, or when a CANCELLED booking is re-activated. Moving between active
-- states (CONFIRMED -> ATTENDED / ABSENT) or to CANCELLED never adds load, so it is skipped.
SET search_path = campus_pantry, public;

CREATE OR REPLACE FUNCTION validate_booking() RETURNS trigger
LANGUAGE plpgsql SET search_path = campus_pantry, public AS $$
DECLARE
    target_date date;
    target_capacity integer;
    active_count integer;
    duplicate_count integer;
BEGIN
    IF TG_OP = 'UPDATE'
       AND NEW.session_id = OLD.session_id
       AND NEW.student_unikey = OLD.student_unikey
       AND (OLD.status <> 'CANCELLED' OR NEW.status = 'CANCELLED') THEN
        RETURN NEW;
    END IF;

    SELECT session_date, capacity INTO target_date, target_capacity
    FROM session WHERE session_id = NEW.session_id FOR UPDATE;

    IF NEW.status <> 'CANCELLED' THEN
        SELECT count(*) INTO active_count
        FROM booking b
        WHERE b.session_id = NEW.session_id
          AND b.status <> 'CANCELLED'
          AND b.booking_id IS DISTINCT FROM NEW.booking_id;

        IF active_count >= target_capacity THEN
            RAISE EXCEPTION 'Session capacity of % has been reached', target_capacity;
        END IF;

        IF NOT NEW.admin_override THEN
            SELECT count(*) INTO duplicate_count
            FROM booking b JOIN session s ON s.session_id = b.session_id
            WHERE b.student_unikey = NEW.student_unikey
              AND s.session_date = target_date
              AND b.status <> 'CANCELLED'
              AND b.booking_id IS DISTINCT FROM NEW.booking_id;
            IF duplicate_count > 0 THEN
                RAISE EXCEPTION 'Student already has an active booking on this date';
            END IF;
        END IF;
    END IF;

    IF NEW.admin_override AND NEW.override_by_staff IS NULL THEN
        RAISE EXCEPTION 'Admin override must identify the staff member';
    END IF;
    RETURN NEW;
END;
$$;
