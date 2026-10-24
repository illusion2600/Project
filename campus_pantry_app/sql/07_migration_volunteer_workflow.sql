-- ============================================================================
-- 07_migration_volunteer_workflow.sql
-- Repeatable, safe migration for Volunteer Workflow and Overlap Safeguards
-- Safe to re-run; will not corrupt or duplicate existing data.
-- ============================================================================

BEGIN;
SET search_path = campus_pantry, public;

-- 1. Add status, request_date, reviewed_by_staff, reviewed_at to volunteer_shift if not present
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'campus_pantry' 
          AND table_name = 'volunteer_shift' 
          AND column_name = 'status'
    ) THEN
        ALTER TABLE volunteer_shift ADD COLUMN status varchar(12) NOT NULL DEFAULT 'PENDING'
            CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED'));
        ALTER TABLE volunteer_shift ADD COLUMN request_date timestamptz NOT NULL DEFAULT now();
        ALTER TABLE volunteer_shift ADD COLUMN reviewed_by_staff varchar(30) REFERENCES staff(unikey);
        ALTER TABLE volunteer_shift ADD COLUMN reviewed_at timestamptz;

        -- Historical seed records were already confirmed shifts:
        UPDATE volunteer_shift SET status = 'APPROVED';
    END IF;
END $$;

-- 2. Staff Shift Overlap Trigger: prevent assigning a staff member to overlapping shifts
CREATE OR REPLACE FUNCTION validate_staff_shift_overlap() RETURNS trigger
LANGUAGE plpgsql SET search_path = campus_pantry, public AS $$
DECLARE
    cur_date date;
    cur_start time;
    cur_end time;
    overlap_count integer;
BEGIN
    SELECT shift_date, start_time, end_time INTO cur_date, cur_start, cur_end
    FROM pantry_shift WHERE shift_id = NEW.shift_id;

    SELECT count(*) INTO overlap_count
    FROM shift_staff_assignment ssa
    JOIN pantry_shift ps ON ps.shift_id = ssa.shift_id
    WHERE ssa.staff_unikey = NEW.staff_unikey
      AND ssa.shift_id <> NEW.shift_id
      AND ps.shift_date = cur_date
      AND ps.start_time < cur_end
      AND cur_start < ps.end_time;

    IF overlap_count > 0 THEN
        RAISE EXCEPTION 'Staff member % is already assigned to an overlapping shift on %', NEW.staff_unikey, cur_date;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS staff_shift_overlap_validate ON shift_staff_assignment;
CREATE TRIGGER staff_shift_overlap_validate
BEFORE INSERT OR UPDATE OF shift_id, staff_unikey
ON shift_staff_assignment FOR EACH ROW EXECUTE FUNCTION validate_staff_shift_overlap();

-- 3. Volunteer Shift Overlap Trigger: prevent volunteer from having overlapping approved/pending shifts
CREATE OR REPLACE FUNCTION validate_volunteer_shift_overlap() RETURNS trigger
LANGUAGE plpgsql SET search_path = campus_pantry, public AS $$
DECLARE
    cur_date date;
    cur_start time;
    cur_end time;
    overlap_count integer;
BEGIN
    IF NEW.status IN ('PENDING', 'APPROVED') THEN
        SELECT shift_date, start_time, end_time INTO cur_date, cur_start, cur_end
        FROM pantry_shift WHERE shift_id = NEW.shift_id;

        SELECT count(*) INTO overlap_count
        FROM volunteer_shift vs
        JOIN pantry_shift ps ON ps.shift_id = vs.shift_id
        WHERE vs.volunteer_unikey = NEW.volunteer_unikey
          AND vs.shift_id <> NEW.shift_id
          AND vs.status IN ('PENDING', 'APPROVED')
          AND ps.shift_date = cur_date
          AND ps.start_time < cur_end
          AND cur_start < ps.end_time;

        IF overlap_count > 0 THEN
            RAISE EXCEPTION 'Volunteer % has an overlapping shift request or assignment on %', NEW.volunteer_unikey, cur_date;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS volunteer_shift_overlap_validate ON volunteer_shift;
CREATE TRIGGER volunteer_shift_overlap_validate
BEFORE INSERT OR UPDATE OF shift_id, volunteer_unikey, status
ON volunteer_shift FOR EACH ROW EXECUTE FUNCTION validate_volunteer_shift_overlap();

-- 4. Update validate_booking() to enforce non-empty override_reason when admin_override is true
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

    PERFORM 1 FROM student WHERE unikey = NEW.student_unikey FOR UPDATE;

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

    IF NEW.admin_override THEN
        IF NEW.override_by_staff IS NULL THEN
            RAISE EXCEPTION 'Admin override must identify the staff member';
        END IF;
        IF NEW.override_reason IS NULL OR length(btrim(NEW.override_reason)) = 0 THEN
            RAISE EXCEPTION 'Admin override must include a valid reason';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

-- 5. Purchase line and stock batch consistency (composite foreign key)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'campus_pantry'
          AND table_name = 'purchase_record_line'
          AND constraint_name = 'purchase_record_line_purchase_line_id_product_id_key'
    ) THEN
        ALTER TABLE purchase_record_line ADD CONSTRAINT purchase_record_line_purchase_line_id_product_id_key UNIQUE (purchase_line_id, product_id);
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE table_schema = 'campus_pantry'
          AND table_name = 'stock_batch'
          AND constraint_name = 'stock_batch_purchase_product_fkey'
    ) THEN
        ALTER TABLE stock_batch ADD CONSTRAINT stock_batch_purchase_product_fkey
            FOREIGN KEY (purchase_line_id, product_id)
            REFERENCES purchase_record_line(purchase_line_id, product_id);
    END IF;
END $$;

COMMIT;
