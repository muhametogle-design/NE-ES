import pytest

def test_state_compliance_map_view(client, state_admin_headers):
    response = client.get("/api/v1/state/compliance-map", headers=state_admin_headers)
    assert response.status_code == 200
    cmap = response.json()
    assert len(cmap) >= 5
    codes = {c["school_code"] for c in cmap}
    assert "IL" in codes
    assert "MY" in codes
    # Muse Yusuf (MY) should have alarm = True from seed
    my = next(c for c in cmap if c["school_code"] == "MY")
    assert my["alarm"] is True

def test_state_analytics_summary_view(client, state_admin_headers):
    response = client.get("/api/v1/state/analytics/summary", headers=state_admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_schools"] >= 5
    assert data["total_students"] > 0
    assert data["total_teachers"] > 0
    assert "compliance_rate" in data

def test_state_institution_classes_and_breakdown(client, state_admin_headers):
    # Classes
    cls_res = client.get("/api/v1/state/institutions/1/classes", headers=state_admin_headers)
    assert cls_res.status_code == 200
    classes = cls_res.json()
    assert len(classes) > 0
    class_id = classes[0]["id"]

    # Breakdown
    bk_res = client.get(f"/api/v1/state/institutions/1/classes/{class_id}/breakdown", headers=state_admin_headers)
    assert bk_res.status_code == 200
    breakdown = bk_res.json()
    assert "total_students" in breakdown
    assert "subjects" in breakdown
    assert "invoices" not in breakdown  # Strictly firewalled

def test_state_school_rankings_view(client, state_admin_headers):
    response = client.get("/api/v1/state/analytics/school-rankings", headers=state_admin_headers)
    assert response.status_code == 200
    rankings = response.json()
    assert len(rankings) >= 5
    assert rankings[0]["total_enrolled"] >= rankings[-1]["total_enrolled"]

def test_state_gender_distribution_view(client, state_admin_headers):
    response = client.get("/api/v1/state/analytics/gender-distribution", headers=state_admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert "male" in data
    assert "female" in data
    assert "total" in data
    assert data["total"] == data["male"] + data["female"]

def test_state_enrollment_by_class_view(client, state_admin_headers):
    response = client.get("/api/v1/state/analytics/enrollment-by-class", headers=state_admin_headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_state_class_levels_helper(client, state_admin_headers):
    response = client.get("/api/v1/state/class-levels", headers=state_admin_headers)
    assert response.status_code == 200
    levels = response.json()
    assert len(levels) == 12
    assert levels[0]["level"] == 1
    assert levels[-1]["level"] == 12

def test_state_school_code_suggestion(client, state_admin_headers):
    response = client.get("/api/v1/state/school-code-suggestion", headers=state_admin_headers)
    assert response.status_code == 200
    assert "suggested_code" in response.json()
    assert len(response.json()["suggested_code"]) == 2

