-- ==========================================================
-- 001_schema.sql: NE-EMIS Core Relational Schema (PostgreSQL)
-- ==========================================================

-- 1. Private Schools Table
CREATE TABLE IF NOT EXISTS private_schools (
    id SERIAL PRIMARY KEY,
    state_license_number VARCHAR(64) UNIQUE,
    school_code VARCHAR(2) UNIQUE NOT NULL,
    school_name VARCHAR(255) NOT NULL,
    proprietor_name VARCHAR(255),
    contact_phone VARCHAR(64),
    contact_email VARCHAR(255),
    physical_address VARCHAR(255),
    accreditation_status VARCHAR(64) DEFAULT 'Active',
    billing_contact_name VARCHAR(255),
    billing_phone VARCHAR(64),
    billing_email VARCHAR(255),
    billing_address VARCHAR(255),
    billing_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 2. School Roll Sequences Table
CREATE TABLE IF NOT EXISTS school_roll_sequences (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL UNIQUE REFERENCES private_schools(id) ON DELETE CASCADE,
    next_value INTEGER NOT NULL DEFAULT 10000
);

-- 3. Users Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    school_id INTEGER REFERENCES private_schools(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(64) NOT NULL,
    first_name VARCHAR(128),
    last_name VARCHAR(128),
    staff_identifier VARCHAR(64) UNIQUE,
    staff_pin_hash VARCHAR(255),
    is_department_head BOOLEAN DEFAULT FALSE,
    phone VARCHAR(64),
    qualifications VARCHAR(255),
    designation VARCHAR(128),
    bio TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 4. Academic Years Table
CREATE TABLE IF NOT EXISTS academic_years (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    year_name VARCHAR(64) NOT NULL,
    start_date TIMESTAMP WITH TIME ZONE,
    end_date TIMESTAMP WITH TIME ZONE,
    is_current BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 5. School Classes Table
CREATE TABLE IF NOT EXISTS school_classes (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_level INTEGER NOT NULL,
    stream VARCHAR(32) NOT NULL,
    academic_year_id INTEGER REFERENCES academic_years(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_class_stream UNIQUE (school_id, class_level, stream)
);

-- 6. Subjects Table
CREATE TABLE IF NOT EXISTS subjects (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    code VARCHAR(32) NOT NULL,
    name VARCHAR(128) NOT NULL,
    level INTEGER NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subject_code UNIQUE (school_id, code)
);

-- 7. Teaching Assignments Table
CREATE TABLE IF NOT EXISTS teaching_assignments (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_assignment UNIQUE (school_id, teacher_id, class_id, subject_id)
);

-- 8. Timetable Slots Table
CREATE TABLE IF NOT EXISTS timetable_slots (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    day_of_week INTEGER NOT NULL,
    period INTEGER NOT NULL,
    room VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_slot_class_time UNIQUE (school_id, class_id, day_of_week, period)
);

-- 9. Students Table
CREATE TABLE IF NOT EXISTS students (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    national_student_id VARCHAR(64) UNIQUE NOT NULL,
    roll_number VARCHAR(64) UNIQUE NOT NULL,
    first_name VARCHAR(128) NOT NULL,
    last_name VARCHAR(128) NOT NULL,
    gender VARCHAR(32) NOT NULL,
    date_of_birth DATE,
    class_id INTEGER REFERENCES school_classes(id) ON DELETE SET NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 10. Student Grades Table
CREATE TABLE IF NOT EXISTS student_grades (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    term VARCHAR(32) NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    grade VARCHAR(8),
    is_published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_student_grade_term UNIQUE (school_id, student_id, subject_id, term)
);

-- 11. Subject Attendance Table
CREATE TABLE IF NOT EXISTS subject_attendance (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status VARCHAR(32) NOT NULL,
    marked_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_subject_attendance_record UNIQUE (student_id, subject_id, date)
);

-- 12. Live Attendance Table
CREATE TABLE IF NOT EXISTS live_attendance (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    timetable_slot_id INTEGER NOT NULL REFERENCES timetable_slots(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    status VARCHAR(32) NOT NULL,
    marked_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_live_attendance_slot UNIQUE (student_id, timetable_slot_id, date)
);

-- 13. Tuition Rates Table
CREATE TABLE IF NOT EXISTS tuition_rates (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_level INTEGER NOT NULL,
    term VARCHAR(32) NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_school_tuition_term UNIQUE (school_id, class_level, term)
);

-- 14. Student Invoices Table
CREATE TABLE IF NOT EXISTS student_invoices (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    invoice_number VARCHAR(64) UNIQUE NOT NULL,
    term VARCHAR(32) NOT NULL,
    amount DOUBLE PRECISION NOT NULL,
    status VARCHAR(32) DEFAULT 'pending',
    due_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 15. Payment Transactions Table
CREATE TABLE IF NOT EXISTS payment_transactions (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    invoice_id INTEGER NOT NULL REFERENCES student_invoices(id) ON DELETE CASCADE,
    amount DOUBLE PRECISION NOT NULL,
    payment_method VARCHAR(64) NOT NULL,
    transaction_reference VARCHAR(128),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 16. Daily Submission Logs Table
CREATE TABLE IF NOT EXISTS daily_submission_logs (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    log_date DATE NOT NULL,
    attendance_submitted BOOLEAN DEFAULT FALSE,
    submitted_at TIMESTAMP WITH TIME ZONE,
    alarm_triggered BOOLEAN DEFAULT FALSE,
    alarm_raised_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_daily_submission UNIQUE (school_id, log_date)
);

-- 17. Exam Submission Events Table
CREATE TABLE IF NOT EXISTS exam_submission_events (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    exam_id INTEGER NOT NULL,
    action VARCHAR(64) NOT NULL,
    performed_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 18. Communication Logs Table
CREATE TABLE IF NOT EXISTS communication_logs (
    id SERIAL PRIMARY KEY,
    school_id INTEGER REFERENCES private_schools(id) ON DELETE CASCADE,
    type VARCHAR(64) NOT NULL,
    status VARCHAR(32) DEFAULT 'Pending',
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 19. Security Audit Log Table
CREATE TABLE IF NOT EXISTS security_audit_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(64) NOT NULL,
    resource VARCHAR(255),
    status VARCHAR(32) NOT NULL,
    details TEXT,
    ip_address VARCHAR(64),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 20. Data Change Log Table
CREATE TABLE IF NOT EXISTS data_change_log (
    id SERIAL PRIMARY KEY,
    table_name VARCHAR(64) NOT NULL,
    record_id INTEGER NOT NULL,
    action VARCHAR(32) NOT NULL,
    changed_data TEXT,
    user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 21. Backup Records Table
CREATE TABLE IF NOT EXISTS backup_records (
    id SERIAL PRIMARY KEY,
    backup_type VARCHAR(32) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    checksum_sha256 VARCHAR(64),
    checksum_md5 VARCHAR(32),
    file_size_bytes BIGINT DEFAULT 0,
    encryption_algorithm VARCHAR(32) DEFAULT 'AES-256-GCM',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 22. Backup Audit Events Table
CREATE TABLE IF NOT EXISTS backup_audit_events (
    id SERIAL PRIMARY KEY,
    backup_id INTEGER,
    action VARCHAR(64) NOT NULL,
    user_id INTEGER,
    details TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 23. Biometric Credentials Table
CREATE TABLE IF NOT EXISTS biometric_credentials (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
    credential_id VARCHAR(255) UNIQUE NOT NULL,
    public_key TEXT NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    transports VARCHAR(64) DEFAULT 'internal',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 24. Biometric Verification Logs Table
CREATE TABLE IF NOT EXISTS biometric_verification_logs (
    id SERIAL PRIMARY KEY,
    student_id INTEGER REFERENCES students(id) ON DELETE SET NULL,
    credential_id VARCHAR(255),
    verification_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL,
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 25. Teacher Absences Table
CREATE TABLE IF NOT EXISTS teacher_absences (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    reason VARCHAR(255),
    status VARCHAR(32) DEFAULT 'reported',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 26. Substitution Assignments Table
CREATE TABLE IF NOT EXISTS substitution_assignments (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    absence_id INTEGER NOT NULL REFERENCES teacher_absences(id) ON DELETE CASCADE,
    substitute_teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    timetable_slot_id INTEGER NOT NULL REFERENCES timetable_slots(id) ON DELETE CASCADE,
    confirmed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 27. Syllabus Plans Table
CREATE TABLE IF NOT EXISTS syllabus_plans (
    id SERIAL PRIMARY KEY,
    school_id INTEGER NOT NULL REFERENCES private_schools(id) ON DELETE CASCADE,
    class_id INTEGER NOT NULL REFERENCES school_classes(id) ON DELETE CASCADE,
    subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    total_units INTEGER NOT NULL DEFAULT 10,
    midterm_target DOUBLE PRECISION NOT NULL DEFAULT 50.0,
    final_target DOUBLE PRECISION NOT NULL DEFAULT 100.0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_syllabus_plan_class_subject UNIQUE (school_id, class_id, subject_id)
);

-- 28. Syllabus Topics Table
CREATE TABLE IF NOT EXISTS syllabus_topics (
    id SERIAL PRIMARY KEY,
    plan_id INTEGER NOT NULL REFERENCES syllabus_plans(id) ON DELETE CASCADE,
    unit_number INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    planned_completion_date DATE
);

-- 29. Syllabus Progress Entries Table
CREATE TABLE IF NOT EXISTS syllabus_progress_entries (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES syllabus_topics(id) ON DELETE CASCADE,
    teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    date_covered DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
