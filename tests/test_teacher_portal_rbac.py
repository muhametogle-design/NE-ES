import pytest
from app.models.tenancy import User
from app.models.academic import TeachingAssignment, SchoolClass, Subject, Student

def test_teacher_can_mark_attendance_for_assigned_class(client, teacher_headers, db_session):
    teacher = db_session.query(User).filter(User.role == "teacher", User.school_id == 1).first()
    assignment = db_session.query(TeachingAssignment).filter(TeachingAssignment.teacher_id == teacher.id).first()
    student = db_session.query(Student).filter(Student.class_id == assignment.class_id).first()

    response = client.post("/api/v1/school/attendance", headers=teacher_headers, json={
        "class_id": assignment.class_id,
        "subject_id": assignment.subject_id,
        "date": "2026-09-04",
        "records": [
            {"student_id": str(student.id), "status": "present"}
        ]
    })
    assert response.status_code == 200
    assert "Successfully marked attendance" in response.json()["message"]

def test_teacher_forbidden_from_marking_unassigned_class(client, teacher_headers, db_session):
    teacher = db_session.query(User).filter(User.role == "teacher", User.school_id == 1).first()
    
    # Create an unassigned class for testing RBAC restriction
    unassigned_class = SchoolClass(
        school_id=1,
        class_level=12,
        stream="Z"
    )
    db_session.add(unassigned_class)
    db_session.flush()

    student = Student(
        school_id=1,
        emis_id="IL-99999",
        national_student_id="IL-99999",
        roll_number="IL-99999",
        first_name="Test",
        last_name="Student",
        gender="Male",
        class_id=unassigned_class.id
    )
    db_session.add(student)
    db_session.commit()

    subject = db_session.query(Subject).filter(Subject.school_id == 1).first()

    response = client.post("/api/v1/school/attendance", headers=teacher_headers, json={
        "class_id": unassigned_class.id,
        "subject_id": subject.id,
        "date": "2026-09-04",
        "records": [
            {"student_id": str(student.id), "status": "present"}
        ]
    })
    assert response.status_code == 403
    assert "Not authorized to mark attendance" in response.json()["detail"]

def test_school_manager_can_mark_attendance_for_any_class(client, school_manager_headers, db_session):
    school_class = db_session.query(SchoolClass).filter(SchoolClass.school_id == 1).first()
    subject = db_session.query(Subject).filter(Subject.school_id == 1).first()
    student = db_session.query(Student).filter(Student.class_id == school_class.id).first()

    response = client.post("/api/v1/school/attendance", headers=school_manager_headers, json={
        "class_id": school_class.id,
        "subject_id": subject.id,
        "date": "2026-09-04",
        "records": [
            {"student_id": str(student.id), "status": "present"}
        ]
    })
    assert response.status_code == 200

def test_teacher_can_query_own_timetable(client, teacher_headers):
    response = client.get("/api/v1/school/timetable", headers=teacher_headers)
    assert response.status_code == 200
    timetable = response.json()
    assert isinstance(timetable, list)

def test_teacher_can_view_subject_attendance(client, teacher_headers):
    response = client.get("/api/v1/school/attendance?class_id=1&subject_id=1&att_date=2026-09-04", headers=teacher_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_teacher_list_classes(client, teacher_headers):
    response = client.get("/api/v1/school/classes", headers=teacher_headers)
    assert response.status_code == 200
    assert len(response.json()) > 0

