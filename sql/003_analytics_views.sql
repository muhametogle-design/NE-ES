-- ==========================================================
-- 003_analytics_views.sql: Analytics and Aggregation Views
-- ==========================================================

-- View 1: Student Enrollment Breakdown by School, Class Level, and Stream
CREATE OR REPLACE VIEW student_enrollment_by_class AS
SELECT
    ps.id AS school_id,
    ps.school_code,
    ps.school_name,
    sc.class_level,
    sc.stream,
    COUNT(s.id) AS total_students,
    SUM(CASE WHEN LOWER(s.gender) = 'male' THEN 1 ELSE 0 END) AS male_students,
    SUM(CASE WHEN LOWER(s.gender) = 'female' THEN 1 ELSE 0 END) AS female_students
FROM private_schools ps
JOIN school_classes sc ON sc.school_id = ps.id
LEFT JOIN students s ON s.class_id = sc.id AND s.is_active = TRUE
GROUP BY ps.id, ps.school_code, ps.school_name, sc.class_level, sc.stream;

-- View 2: Daily Attendance Compliance Summary
CREATE OR REPLACE VIEW daily_attendance_compliance_summary AS
SELECT
    ps.id AS school_id,
    ps.school_code,
    ps.school_name,
    dsl.log_date,
    COALESCE(dsl.attendance_submitted, FALSE) AS attendance_submitted,
    dsl.submitted_at,
    COALESCE(dsl.alarm_triggered, FALSE) AS alarm_triggered,
    dsl.alarm_raised_at
FROM private_schools ps
LEFT JOIN daily_submission_logs dsl ON dsl.school_id = ps.id;

-- View 3: Teacher Workload and Department Assignments
CREATE OR REPLACE VIEW teacher_workload_summary AS
SELECT
    u.id AS teacher_id,
    u.school_id,
    ps.school_code,
    u.first_name,
    u.last_name,
    u.email,
    u.staff_identifier,
    u.is_department_head,
    COUNT(DISTINCT ta.id) AS assigned_courses,
    COUNT(DISTINCT ts.id) AS weekly_periods
FROM users u
JOIN private_schools ps ON ps.id = u.school_id
LEFT JOIN teaching_assignments ta ON ta.teacher_id = u.id
LEFT JOIN timetable_slots ts ON ts.teacher_id = u.id
WHERE u.role = 'teacher' AND u.is_active = TRUE
GROUP BY u.id, u.school_id, ps.school_code, u.first_name, u.last_name, u.email, u.staff_identifier, u.is_department_head;

-- View 4: Syllabus Completion Rate Summary
CREATE OR REPLACE VIEW syllabus_completion_summary AS
SELECT
    sp.id AS plan_id,
    sp.school_id,
    sp.class_id,
    sp.subject_id,
    sub.code AS subject_code,
    sub.name AS subject_name,
    sp.total_units,
    sp.midterm_target,
    sp.final_target,
    COUNT(DISTINCT spe.topic_id) AS units_completed,
    ROUND((COUNT(DISTINCT spe.topic_id)::NUMERIC / NULLIF(sp.total_units, 0)::NUMERIC) * 100, 2) AS completion_percentage
FROM syllabus_plans sp
JOIN subjects sub ON sub.id = sp.subject_id
LEFT JOIN syllabus_topics st ON st.plan_id = sp.id
LEFT JOIN syllabus_progress_entries spe ON spe.topic_id = st.id
GROUP BY sp.id, sp.school_id, sp.class_id, sp.subject_id, sub.code, sub.name, sp.total_units, sp.midterm_target, sp.final_target;
