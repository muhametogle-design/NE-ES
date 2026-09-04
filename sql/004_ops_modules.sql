-- ==========================================================
-- 004_ops_modules.sql: Row-Level Change Capture & Delta Logging
-- ==========================================================

CREATE OR REPLACE FUNCTION capture_data_change()
RETURNS TRIGGER AS $$
DECLARE
    curr_user_id INTEGER;
BEGIN
    BEGIN
        curr_user_id := NULLIF(current_setting('app.user_id', true), '')::integer;
    EXCEPTION WHEN OTHERS THEN
        curr_user_id := NULL;
    END;

    IF (TG_OP = 'DELETE') THEN
        INSERT INTO data_change_log (table_name, record_id, action, changed_data, user_id, created_at)
        VALUES (TG_TABLE_NAME, OLD.id, 'DELETE', row_to_json(OLD)::text, curr_user_id, CURRENT_TIMESTAMP);
        RETURN OLD;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO data_change_log (table_name, record_id, action, changed_data, user_id, created_at)
        VALUES (TG_TABLE_NAME, NEW.id, 'UPDATE', row_to_json(NEW)::text, curr_user_id, CURRENT_TIMESTAMP);
        RETURN NEW;
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO data_change_log (table_name, record_id, action, changed_data, user_id, created_at)
        VALUES (TG_TABLE_NAME, NEW.id, 'INSERT', row_to_json(NEW)::text, curr_user_id, CURRENT_TIMESTAMP);
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Attach triggers to core operational tables
DROP TRIGGER IF EXISTS trg_student_changes ON students;
CREATE TRIGGER trg_student_changes
    AFTER INSERT OR UPDATE OR DELETE ON students
    FOR EACH ROW EXECUTE FUNCTION capture_data_change();

DROP TRIGGER IF EXISTS trg_grades_changes ON student_grades;
CREATE TRIGGER trg_grades_changes
    AFTER INSERT OR UPDATE OR DELETE ON student_grades
    FOR EACH ROW EXECUTE FUNCTION capture_data_change();

DROP TRIGGER IF EXISTS trg_attendance_changes ON subject_attendance;
CREATE TRIGGER trg_attendance_changes
    AFTER INSERT OR UPDATE OR DELETE ON subject_attendance
    FOR EACH ROW EXECUTE FUNCTION capture_data_change();
