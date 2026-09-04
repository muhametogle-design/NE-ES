import pytest
from app.models.academic import SchoolClass, Subject

def test_syllabus_plan_lifecycle_and_pacing(client, school_manager_headers, teacher_headers, db_session):
    school_class = db_session.query(SchoolClass).filter(SchoolClass.school_id == 1).first()
    subject = db_session.query(Subject).filter(Subject.school_id == 1).first()

    # 1. Create Plan with 4 units, 50% midterm target
    plan_res = client.post("/api/v1/school/syllabus/plans", headers=school_manager_headers, json={
        "class_id": school_class.id,
        "subject_id": subject.id,
        "total_units": 4,
        "midterm_target": 50.0,
        "final_target": 100.0
    })
    assert plan_res.status_code == 201
    plan = plan_res.json()
    assert plan["total_units"] == 4
    assert plan["completed_units"] == 0
    assert plan["status"] == "behind"  # 0% < 50%

    # 2. Add Topics
    t1_res = client.post("/api/v1/school/syllabus/topics", headers=school_manager_headers, json={
        "plan_id": plan["id"],
        "unit_number": 1,
        "title": "Unit 1: Fundamentals",
        "description": "Core principles"
    })
    assert t1_res.status_code == 201
    t1_id = t1_res.json()["id"]

    t2_res = client.post("/api/v1/school/syllabus/topics", headers=school_manager_headers, json={
        "plan_id": plan["id"],
        "unit_number": 2,
        "title": "Unit 2: Applied Analysis",
        "description": "Methods and experiments"
    })
    assert t2_res.status_code == 201
    t2_id = t2_res.json()["id"]

    # 3. Record Progress on Topic 1 (25% completion -> still behind 50%)
    p1_res = client.post("/api/v1/school/syllabus/progress", headers=teacher_headers, json={
        "topic_id": t1_id,
        "date_covered": "2026-09-02",
        "notes": "Unit 1 covered in full"
    })
    assert p1_res.status_code == 201

    plan_check1 = client.get(f"/api/v1/school/syllabus/plans/{plan['id']}", headers=school_manager_headers).json()
    assert plan_check1["completed_units"] == 1
    assert plan_check1["progress_percentage"] == 25.0
    assert plan_check1["status"] == "behind"

    # 4. Record Progress on Topic 2 (50% completion -> on_track!)
    p2_res = client.post("/api/v1/school/syllabus/progress", headers=teacher_headers, json={
        "topic_id": t2_id,
        "date_covered": "2026-09-04",
        "notes": "Unit 2 completed"
    })
    assert p2_res.status_code == 201

    plan_check2 = client.get(f"/api/v1/school/syllabus/plans/{plan['id']}", headers=school_manager_headers).json()
    assert plan_check2["completed_units"] == 2
    assert plan_check2["progress_percentage"] == 50.0
    assert plan_check2["status"] == "on_track"

def test_syllabus_status_overview(client, school_manager_headers):
    response = client.get("/api/v1/school/syllabus/status", headers=school_manager_headers)
    assert response.status_code == 200
    data = response.json()
    assert "total_plans" in data
    assert "on_track_count" in data
    assert "behind_count" in data
    assert "plans" in data

def test_list_syllabus_topics(client, school_manager_headers):
    plans = client.get("/api/v1/school/syllabus/plans", headers=school_manager_headers).json()
    if len(plans) > 0:
        plan_id = plans[0]["id"]
        response = client.get(f"/api/v1/school/syllabus/topics?plan_id={plan_id}", headers=school_manager_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

