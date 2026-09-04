import pytest
from app.models.tenancy import User
from app.core.security import verify_password, hash_pin, create_access_token
from datetime import timedelta

def test_login_with_valid_email_and_password(client):
    response = client.post("/api/auth/login", json={
        "email": "stateadmin@education.gov",
        "password": "StateAdmin@2026"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["user"]["role"] == "state_admin"
    assert "access_token" in response.cookies

def test_login_with_invalid_password(client):
    response = client.post("/api/auth/login", json={
        "email": "stateadmin@education.gov",
        "password": "WrongPassword@123"
    })
    assert response.status_code == 401
    assert "Invalid credentials" in response.json()["detail"]

def test_login_with_nonexistent_email(client):
    response = client.post("/api/auth/login", json={
        "email": "unknown.user@education.gov",
        "password": "SomePassword@2026"
    })
    assert response.status_code == 401

def test_login_with_staff_id_and_pin(client, db_session):
    teacher = db_session.query(User).filter(User.role == "teacher").first()
    teacher.staff_pin_hash = hash_pin("1234")
    db_session.commit()

    response = client.post("/api/auth/login", json={
        "staff_identifier": teacher.staff_identifier,
        "pin": "1234"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["user"]["id"] == teacher.id

def test_login_with_invalid_pin(client, db_session):
    teacher = db_session.query(User).filter(User.role == "teacher").first()
    teacher.staff_pin_hash = hash_pin("1234")
    db_session.commit()

    response = client.post("/api/auth/login", json={
        "staff_identifier": teacher.staff_identifier,
        "pin": "9999"
    })
    assert response.status_code == 401

def test_login_inactive_user_rejected(client, db_session):
    user = db_session.query(User).filter(User.role == "teacher").all()[-1]
    user.is_active = False
    db_session.commit()

    response = client.post("/api/auth/login", json={
        "email": user.email,
        "password": "Teach@2026"
    })
    assert response.status_code == 403
    assert "account is deactivated" in response.json()["detail"]
    user.is_active = True
    db_session.commit()

def test_get_current_user_me(client, state_admin_headers):
    response = client.get("/api/auth/me", headers=state_admin_headers)
    assert response.status_code == 200
    assert response.json()["email"] == "stateadmin@education.gov"

def test_logout_clears_cookie(client, state_admin_headers):
    response = client.post("/api/auth/logout", headers=state_admin_headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Successfully logged out"

def test_change_password_valid(client, school_manager_headers, db_session):
    response = client.post("/api/auth/change-password", headers=school_manager_headers, json={
        "current_password": "School@2026",
        "new_password": "UpdatedSchool@2026"
    })
    assert response.status_code == 200
    assert response.json()["message"] == "Password changed successfully"

    mgr = db_session.query(User).filter(User.email == "manager@ilays.edu.so").first()
    assert verify_password("UpdatedSchool@2026", mgr.password_hash)

def test_change_password_wrong_current(client, school_manager_headers):
    response = client.post("/api/auth/change-password", headers=school_manager_headers, json={
        "current_password": "IncorrectPassword",
        "new_password": "NewSecret@2026"
    })
    assert response.status_code == 400
    assert "Incorrect current password" in response.json()["detail"]

def test_set_pin_endpoint(client, teacher_headers):
    response = client.post("/api/auth/set-pin", headers=teacher_headers, json={"pin": "5678"})
    assert response.status_code == 200
    assert response.json()["message"] == "Staff PIN updated successfully"

def test_set_pin_too_short_rejected(client, teacher_headers):
    response = client.post("/api/auth/set-pin", headers=teacher_headers, json={"pin": "12"})
    assert response.status_code == 400
    assert "at least 4 digits" in response.json()["detail"]

def test_token_auth_via_cookie_fallback(client, db_session):
    user = db_session.query(User).filter(User.role == "state_admin").first()
    token = create_access_token({"sub": str(user.id), "role": user.role, "school_id": None})
    
    # Request without Authorization header but with access_token cookie
    client.cookies.set("access_token", token)
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["id"] == user.id
    client.cookies.clear()

def test_expired_token_rejected(client):
    expired_token = create_access_token({"sub": "1", "role": "state_admin"}, expires_delta=timedelta(seconds=-10))
    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
    assert response.status_code == 401
    assert "Invalid or expired access token" in response.json()["detail"]

def test_unauthenticated_request_to_me_returns_401(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    assert "Authentication credentials required" in response.json()["detail"]

def test_dual_login_with_different_roles(client):
    res_admin = client.post("/api/auth/login", json={
        "email": "stateadmin@education.gov",
        "password": "StateAdmin@2026"
    })
    assert res_admin.status_code == 200
    assert res_admin.json()["user"]["role"] == "state_admin"

    res_insp = client.post("/api/auth/login", json={
        "email": "inspector@education.gov",
        "password": "State@2026"
    })
    assert res_insp.status_code == 200
    assert res_insp.json()["user"]["role"] == "inspector"


