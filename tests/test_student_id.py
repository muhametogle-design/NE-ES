import pytest
from app.models.academic import Student
from app.models.tenancy import PrivateSchool, SchoolRollSequence

def test_student_roll_number_format_and_sequence(client, school_manager_headers, db_session):
    school = db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "IL").first()
    seq_before = db_session.query(SchoolRollSequence).filter(SchoolRollSequence.school_id == school.id).first().next_value

    response = client.post("/api/v1/school/students", headers=school_manager_headers, json={
        "first_name": "Khadar",
        "last_name": "Guleed",
        "gender": "Male",
        "class_id": 1
    })
    assert response.status_code == 201
    student = response.json()
    assert student["roll_number"] == f"IL-{seq_before}"
    assert student["national_student_id"] == f"IL-{seq_before}"

    seq_after = db_session.query(SchoolRollSequence).filter(SchoolRollSequence.school_id == school.id).first().next_value
    assert seq_after == seq_before + 1

def test_roll_number_immutability(client, school_manager_headers, db_session):
    student = db_session.query(Student).filter(Student.school_id == 1).first()
    original_roll = student.roll_number

    response = client.put(f"/api/v1/school/students/{original_roll}", headers=school_manager_headers, json={
        "first_name": "UpdatedName",
        "roll_number": "FORGED-99999",
        "national_student_id": "FORGED-99999"
    })
    assert response.status_code == 200
    updated = response.json()
    assert updated["first_name"] == "UpdatedName"
    assert updated["roll_number"] == original_roll

def test_cross_tenant_student_isolation_returns_404(client, other_school_manager_headers, db_session):
    student_sch1 = db_session.query(Student).filter(Student.school_id == 1).first()

    response = client.get(f"/api/v1/school/students/{student_sch1.roll_number}", headers=other_school_manager_headers)
    assert response.status_code == 404
    assert "Student not found" in response.json()["detail"]

def test_cross_tenant_student_update_returns_404(client, other_school_manager_headers, db_session):
    student_sch1 = db_session.query(Student).filter(Student.school_id == 1).first()

    response = client.put(f"/api/v1/school/students/{student_sch1.roll_number}", headers=other_school_manager_headers, json={
        "first_name": "HackedName"
    })
    assert response.status_code == 404

def test_cross_tenant_student_delete_returns_404(client, other_school_manager_headers, db_session):
    student_sch1 = db_session.query(Student).filter(Student.school_id == 1).first()

    response = client.delete(f"/api/v1/school/students/{student_sch1.roll_number}", headers=other_school_manager_headers)
    assert response.status_code == 404

def test_state_roll_sequence_update_forward(client, state_admin_headers):
    response = client.patch("/api/v1/state/schools/1/roll-sequence", headers=state_admin_headers, json={
        "next_value": 30000
    })
    assert response.status_code == 200
    assert response.json()["next_value"] == 30000

def test_state_roll_sequence_update_cannot_decrement(client, state_admin_headers):
    response = client.patch("/api/v1/state/schools/1/roll-sequence", headers=state_admin_headers, json={
        "next_value": 5000
    })
    assert response.status_code == 400
    assert "Cannot decrement roll number sequence" in response.json()["detail"]

def test_state_lookup_student_by_roll_number(client, state_admin_headers, db_session):
    student = db_session.query(Student).first()
    response = client.get(f"/api/v1/state/students/lookup?ne_sid={student.roll_number}", headers=state_admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["roll_number"] == student.roll_number
    assert data["first_name"] == student.first_name
    assert "school_code" in data

def test_state_lookup_nonexistent_student_returns_404(client, state_admin_headers):
    response = client.get("/api/v1/state/students/lookup?ne_sid=XX-99999", headers=state_admin_headers)
    assert response.status_code == 404
    assert "No student record found" in response.json()["detail"]

def test_student_pagination_pages_calculation(client, school_manager_headers):
    response = client.get("/api/v1/school/students?page=1&per_page=5", headers=school_manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 5
    assert data["page"] == 1
    assert data["pages"] >= 1

def test_create_student_without_class_id(client, school_manager_headers):
    response = client.post("/api/v1/school/students", headers=school_manager_headers, json={
        "first_name": "Unassigned",
        "last_name": "Student",
        "gender": "Female"
    })
    assert response.status_code == 201
    assert response.json()["class_id"] is None
    assert response.json()["roll_number"].startswith("IL-")

