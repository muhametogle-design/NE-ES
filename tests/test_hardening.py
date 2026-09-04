import pytest

def test_security_headers_present(client):
    response = client.get("/api/v1/state/schools")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert response.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "geolocation=()" in response.headers.get("Permissions-Policy", "")

def test_unauthenticated_request_rejected(client):
    response = client.get("/api/v1/school/students")
    assert response.status_code == 401
    assert "Authentication credentials required" in response.json()["detail"]

def test_invalid_jwt_token_rejected(client):
    response = client.get("/api/v1/school/students", headers={"Authorization": "Bearer invalid.token.payload"})
    assert response.status_code == 401
    assert "Invalid or expired access token" in response.json()["detail"]

def test_sql_injection_safe_search(client, state_admin_headers):
    response = client.get("/api/v1/state/students/search?q=' OR 1=1 --", headers=state_admin_headers)
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_cors_preflight_request(client):
    response = client.options("/api/auth/login", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST"
    })
    assert response.status_code == 200
    assert "access-control-allow-origin" in response.headers

def test_malformed_json_returns_422(client, school_manager_headers):
    response = client.post(
        "/api/v1/school/students",
        headers={**school_manager_headers, "Content-Type": "application/json"},
        content="{\"first_name\": 12345, \"gender\": [invalid]}"
    )
    assert response.status_code in [400, 422]
