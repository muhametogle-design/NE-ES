-- ==========================================================
-- 002_security_firewall.sql: Financial Firewall & Row-Level Security
-- ==========================================================

-- Enable Row Level Security on core tenant tables
ALTER TABLE private_schools ENABLE ROW LEVEL SECURITY;
ALTER TABLE tuition_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE students ENABLE ROW LEVEL SECURITY;
ALTER TABLE school_classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE subjects ENABLE ROW LEVEL SECURITY;
ALTER TABLE teaching_assignments ENABLE ROW LEVEL SECURITY;
ALTER TABLE timetable_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE student_grades ENABLE ROW LEVEL SECURITY;
ALTER TABLE subject_attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE live_attendance ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners where applicable
ALTER TABLE tuition_rates FORCE ROW LEVEL SECURITY;
ALTER TABLE student_invoices FORCE ROW LEVEL SECURITY;
ALTER TABLE payment_transactions FORCE ROW LEVEL SECURITY;

-- Create Roles
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'state_readonly') THEN
        CREATE ROLE state_readonly;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'school_tenant') THEN
        CREATE ROLE school_tenant;
    END IF;
END
$$;

-- State Permissions: Grant read access on public academic and compliance data
GRANT USAGE ON SCHEMA public TO state_readonly;
GRANT SELECT ON private_schools, school_classes, subjects, students, daily_submission_logs, communication_logs, exam_submission_events TO state_readonly;

-- STRICT FINANCIAL FIREWALL: Revoke any select, insert, update, delete on finance tables from state_readonly
REVOKE ALL ON tuition_rates, student_invoices, payment_transactions FROM state_readonly;

-- RLS Isolation Policy: Schools
CREATE POLICY tenant_isolation_schools ON private_schools
    FOR ALL
    USING (
        id = NULLIF(current_setting('app.school_id', true), '')::integer
        OR current_setting('app.role', true) IN ('state_admin', 'inspector')
    );

-- RLS Isolation Policy: Academic & Students
CREATE POLICY tenant_isolation_students ON students
    FOR ALL
    USING (
        school_id = NULLIF(current_setting('app.school_id', true), '')::integer
        OR current_setting('app.role', true) IN ('state_admin', 'inspector')
    );

-- RLS Firewall Policies for Finance (Zero State Access)
CREATE POLICY finance_firewall_tuition ON tuition_rates
    FOR ALL
    USING (
        school_id = NULLIF(current_setting('app.school_id', true), '')::integer
        AND current_setting('app.role', true) IN ('school_manager', 'teacher')
    );

CREATE POLICY finance_firewall_invoices ON student_invoices
    FOR ALL
    USING (
        school_id = NULLIF(current_setting('app.school_id', true), '')::integer
        AND current_setting('app.role', true) IN ('school_manager', 'teacher')
    );

CREATE POLICY finance_firewall_payments ON payment_transactions
    FOR ALL
    USING (
        school_id = NULLIF(current_setting('app.school_id', true), '')::integer
        AND current_setting('app.role', true) IN ('school_manager', 'teacher')
    );
