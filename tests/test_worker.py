import pytest
from app.services.compliance_service import run_attendance_audit
from app.models.compliance import DailySubmissionLog, CommunicationLog
from app.models.tenancy import PrivateSchool

def test_attendance_audit_execution(db_session):
    # Execute audit
    result = run_attendance_audit(db_session)
    assert "alarms_raised" in result
    assert "date" in result

def test_attendance_audit_idempotency(db_session):
    # Initial audit
    run_attendance_audit(db_session)
    initial_comms = db_session.query(CommunicationLog).filter(CommunicationLog.type == "Red_Alarm").count()

    # Second audit run on same day
    run_attendance_audit(db_session)
    second_comms = db_session.query(CommunicationLog).filter(CommunicationLog.type == "Red_Alarm").count()

    # Count of alarms must remain idempotent (no duplicates created)
    assert second_comms == initial_comms

def test_state_manual_audit_endpoint(client, state_admin_headers):
    response = client.post("/api/v1/state/audit/run", headers=state_admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "Manual compliance attendance audit executed" in data["message"]

def test_daily_submission_log_status_and_timestamps(client, school_manager_headers, db_session):
    # Submit daily attendance
    sub_res = client.post("/api/v1/school/attendance/submit", headers=school_manager_headers)
    assert sub_res.status_code == 200
    data = sub_res.json()
    assert data["success"] is True
    assert "officially transmitted" in data["message"]

    log = db_session.query(DailySubmissionLog).filter(DailySubmissionLog.school_id == 1).order_by(DailySubmissionLog.log_date.desc()).first()
    assert log.attendance_submitted is True
    assert log.submitted_at is not None
    assert log.alarm_triggered is False

def test_dismiss_alarm_endpoint(client, state_admin_headers, db_session):
    alarm = db_session.query(CommunicationLog).first()
    if alarm:
        response = client.post(f"/api/v1/state/alarms/dismiss?alarm_id={alarm.id}", headers=state_admin_headers)
        assert response.status_code == 200
        assert "dismissed" in response.json()["message"] or "resolved" in response.json()["message"]

