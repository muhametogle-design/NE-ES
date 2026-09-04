import pytest
from app.models.compliance import SecurityAuditLog

def test_state_admin_cannot_access_finance_summary(client, state_admin_headers):
    response = client.get("/api/v1/school/finance/summary", headers=state_admin_headers)
    assert response.status_code == 403
    assert "Financial records restricted to school tenants" in response.json()["detail"]

def test_inspector_cannot_access_finance_summary(client, inspector_headers):
    response = client.get("/api/v1/school/finance/summary", headers=inspector_headers)
    assert response.status_code == 403
    assert "Financial records restricted to school tenants" in response.json()["detail"]

def test_inspector_cannot_access_finance_invoices(client, inspector_headers):
    response = client.get("/api/v1/school/finance/invoices", headers=inspector_headers)
    assert response.status_code == 403
    assert "Financial records restricted to school tenants" in response.json()["detail"]

def test_state_admin_cannot_access_finance_invoices(client, state_admin_headers):
    response = client.get("/api/v1/school/finance/invoices", headers=state_admin_headers)
    assert response.status_code == 403

def test_state_admin_cannot_access_tuition_rates(client, state_admin_headers):
    response = client.get("/api/v1/school/finance/rates", headers=state_admin_headers)
    assert response.status_code == 403

def test_inspector_cannot_access_tuition_rates(client, inspector_headers):
    response = client.get("/api/v1/school/finance/rates", headers=inspector_headers)
    assert response.status_code == 403

def test_state_admin_cannot_create_tuition_rate(client, state_admin_headers):
    response = client.post("/api/v1/school/finance/rates", headers=state_admin_headers, json={
        "class_level": 1,
        "term": "Term 1",
        "amount": 100.0
    })
    assert response.status_code == 403

def test_state_admin_cannot_create_invoice(client, state_admin_headers):
    response = client.post("/api/v1/school/finance/invoices", headers=state_admin_headers, json={
        "student_id": 1,
        "term": "Term 1",
        "amount": 100.0
    })
    assert response.status_code == 403

def test_state_admin_cannot_record_payment(client, state_admin_headers):
    response = client.post("/api/v1/school/finance/invoices/1/payments", headers=state_admin_headers, json={
        "amount": 50.0,
        "payment_method": "Cash"
    })
    assert response.status_code == 403

def test_firewall_blocks_and_records_security_audit_log(client, state_admin_headers, db_session):
    initial_count = db_session.query(SecurityAuditLog).filter(SecurityAuditLog.status == "BLOCKED").count()
    
    response = client.get("/api/v1/school/finance/rates", headers=state_admin_headers)
    assert response.status_code == 403

    new_count = db_session.query(SecurityAuditLog).filter(SecurityAuditLog.status == "BLOCKED").count()
    assert new_count > initial_count

    latest = db_session.query(SecurityAuditLog).filter(SecurityAuditLog.status == "BLOCKED").order_by(SecurityAuditLog.created_at.desc()).first()
    assert latest.action == "BLOCKED_FINANCE_ACCESS"
    assert "State role" in latest.details

def test_school_manager_can_access_finance_summary(client, school_manager_headers):
    response = client.get("/api/v1/school/finance/summary", headers=school_manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert "collected_revenue" in data
    assert "total_invoices" in data

def test_state_schools_view_excludes_billing_block(client, state_admin_headers):
    response = client.get("/api/v1/state/schools", headers=state_admin_headers)
    assert response.status_code == 200
    schools = response.json()
    assert len(schools) > 0
    for s in schools:
        assert "billing_contact_name" not in s
        assert "billing_phone" not in s
        assert "billing_email" not in s
        assert "billing_address" not in s
        assert "billing_notes" not in s

def test_state_student_search_has_no_tuition_data(client, state_admin_headers):
    response = client.get("/api/v1/state/students/search?q=Ahmed", headers=state_admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    for st in data:
        assert "invoices" not in st
        assert "tuition" not in st
        assert "balance" not in st
