import pytest
from app.models.tenancy import User
from app.models.academic import TeachingAssignment, Student, StudentGrade
from app.models.compliance import ExamSubmissionEvent

def test_grade_entry_and_publishing_creates_exam_event(client, school_manager_headers, state_admin_headers, db_session):
    school_id = 1
    assignment = db_session.query(TeachingAssignment).filter(TeachingAssignment.school_id == school_id).first()
    student = db_session.query(Student).filter(Student.class_id == assignment.class_id).first()

    # 1. Enter Grades
    grade_res = client.post("/api/v1/school/grades", headers=school_manager_headers, json={
        "subject_id": assignment.subject_id,
        "class_id": assignment.class_id,
        "term": "Term 1",
        "grades": [
            {"student_id": student.id, "score": 88.5}
        ]
    })
    assert grade_res.status_code == 200

    # 2. Check draft state
    draft = db_session.query(StudentGrade).filter_by(student_id=student.id, subject_id=assignment.subject_id, term="Term 1").first()
    assert draft.score == 88.5
    assert draft.is_published is False

    # 3. Publish Grades (Release Valve)
    pub_res = client.post("/api/v1/school/grades/publish", headers=school_manager_headers, json={
        "subject_id": assignment.subject_id,
        "class_id": assignment.class_id,
        "term": "Term 1"
    })
    assert pub_res.status_code == 200
    assert "Published and certified" in pub_res.json()["message"]

    # 4. Check published state
    published = db_session.query(StudentGrade).filter_by(student_id=student.id, subject_id=assignment.subject_id, term="Term 1").first()
    assert published.is_published is True
    assert published.published_at is not None

    # 5. Check ExamSubmissionEvent in state audit
    events_res = client.get("/api/v1/state/exam-events", headers=state_admin_headers)
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) > 0
    assert any(e["action"] == "published" and e["exam_id"] == assignment.subject_id for e in events)

def test_letter_grade_bands():
    from app.services.academic_service import AcademicService
    assert AcademicService.calculate_letter_grade(95) == "A+"
    assert AcademicService.calculate_letter_grade(85) == "A"
    assert AcademicService.calculate_letter_grade(75) == "B"
    assert AcademicService.calculate_letter_grade(65) == "C"
    assert AcademicService.calculate_letter_grade(55) == "D"
    assert AcademicService.calculate_letter_grade(45) == "F"

def test_grades_listing_filtered_by_term(client, school_manager_headers):
    response = client.get("/api/v1/school/grades?subject_id=1&class_id=1&term=Term 1", headers=school_manager_headers)
    assert response.status_code == 200
    grades = response.json()
    assert isinstance(grades, list)

