-- ==========================================================
-- 005_module_refinements.sql: Schema Refinements & Index Optimization
-- ==========================================================

-- Ensure Staff-ID & PIN indexes for rapid auth lookup
CREATE INDEX IF NOT EXISTS idx_users_staff_identifier ON users(staff_identifier);
CREATE INDEX IF NOT EXISTS idx_users_role_school ON users(role, school_id);

-- Ensure Student lookup indexes
CREATE INDEX IF NOT EXISTS idx_students_roll_number ON students(roll_number);
CREATE INDEX IF NOT EXISTS idx_students_national_id ON students(national_student_id);
CREATE INDEX IF NOT EXISTS idx_students_school_class ON students(school_id, class_id);

-- Timetable and attendance performance indexes
CREATE INDEX IF NOT EXISTS idx_timetable_lookup ON timetable_slots(school_id, day_of_week, period);
CREATE INDEX IF NOT EXISTS idx_subject_attendance_date ON subject_attendance(school_id, date);
CREATE INDEX IF NOT EXISTS idx_daily_submission_date ON daily_submission_logs(school_id, log_date);

-- Biometric indexes
CREATE INDEX IF NOT EXISTS idx_biometric_cred_id ON biometric_credentials(credential_id);
CREATE INDEX IF NOT EXISTS idx_biometric_logs_student ON biometric_verification_logs(student_id);

-- Syllabus plan & progress indexes
CREATE INDEX IF NOT EXISTS idx_syllabus_topics_plan ON syllabus_topics(plan_id);
CREATE INDEX IF NOT EXISTS idx_syllabus_progress_topic ON syllabus_progress_entries(topic_id);
