import pytest
from app.models.academic import Student

def test_biometric_registration_and_verification_flow(client, school_manager_headers, db_session):
    student = db_session.query(Student).filter(Student.school_id == 1).first()

    # 1. Options generator
    opt_res = client.post("/api/v1/school/biometrics/register/options", headers=school_manager_headers, json={
        "student_id": str(student.id)
    })
    assert opt_res.status_code == 200
    assert "challenge" in opt_res.json()
    assert opt_res.json()["user"]["id"] == str(student.id)

    # 2. Register Credential
    cred_id = f"FIDO2-TEST-{student.roll_number}-123"
    reg_res = client.post("/api/v1/school/biometrics/register/verify", headers=school_manager_headers, json={
        "student_id": str(student.id),
        "credential_id": cred_id,
        "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA..."
    })
    assert reg_res.status_code == 200
    assert "registered successfully" in reg_res.json()["message"]

    # 3. Verify Biometric for Exam Hall Entry (Success)
    ver_res = client.post("/api/v1/school/biometrics/verify", headers=school_manager_headers, json={
        "credential_id": cred_id,
        "verification_type": "exam_hall_entry"
    })
    assert ver_res.status_code == 200
    data = ver_res.json()
    assert data["success"] is True
    assert data["status"] == "success"
    assert data["student_id"] == str(student.id)
    assert data["roll_number"] == student.roll_number

    # 4. Verify Unknown Credential (Rejected)
    rej_res = client.post("/api/v1/school/biometrics/verify", headers=school_manager_headers, json={
        "credential_id": "UNKNOWN-CREDENTIAL-999",
        "verification_type": "exam_hall_entry"
    })
    assert rej_res.status_code == 200
    rej_data = rej_res.json()
    assert rej_data["success"] is False
    assert rej_data["status"] == "failed"
    assert "Unrecognized" in rej_data["reason"]

    # 5. Check Logs
    logs_res = client.get("/api/v1/school/biometrics/logs", headers=school_manager_headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) >= 2

def test_biometric_options_nonexistent_student_returns_404(client, school_manager_headers):
    response = client.post("/api/v1/school/biometrics/register/options", headers=school_manager_headers, json={
        "student_id": "00000000-0000-0000-0000-000000000000"
    })
    assert response.status_code == 404

def test_staff_checkin_biometrics(client, teacher_headers):
    response = client.post("/api/v1/school/biometrics/staff-checkin", headers=teacher_headers, json={
        "credential_id": "STAFF-KEY-9988",
        "verification_type": "staff_attendance"
    })
    assert response.status_code == 200
    assert response.json()["status"] == "success"

