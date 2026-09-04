import pytest
from datetime import date
from app.models.tenancy import User
from app.models.academic import TimetableSlot, TeachingAssignment
from app.models.absence import TeacherAbsence, SubstitutionAssignment

def test_absence_reporting_and_candidate_ranking(client, school_manager_headers, db_session):
    school_id = 1
    teachers = db_session.query(User).filter(User.school_id == school_id, User.role == "teacher").all()
    absent_teacher = teachers[0]

    # Create Timetable Slot for absent teacher
    slot = TimetableSlot(
        school_id=school_id,
        class_id=1,
        subject_id=1,
        teacher_id=absent_teacher.id,
        day_of_week=0,
        period=1,
        room="Hall A"
    )
    db_session.add(slot)
    db_session.commit()
    db_session.refresh(slot)

    # Report absence
    abs_res = client.post("/api/v1/school/absences", headers=school_manager_headers, json={
        "teacher_id": absent_teacher.id,
        "date": "2026-09-08",
        "reason": "Medical appointment"
    })
    assert abs_res.status_code == 201
    absence_id = abs_res.json()["id"]

    # Candidate ranking
    cand_res = client.get(f"/api/v1/school/substitutions/candidates?slot_id={slot.id}&abs_date=2026-09-08", headers=school_manager_headers)
    assert cand_res.status_code == 200
    candidates = cand_res.json()
    assert len(candidates) > 0
    # Top candidate should have a positive score
    top_candidate = candidates[0]
    assert top_candidate["match_score"] > 0
    assert top_candidate["is_free"] is True

    # Assign substitution
    sub_res = client.post("/api/v1/school/substitutions", headers=school_manager_headers, json={
        "absence_id": absence_id,
        "substitute_teacher_id": top_candidate["teacher_id"],
        "timetable_slot_id": slot.id
    })
    assert sub_res.status_code == 201
    sub_id = sub_res.json()["id"]
    assert sub_res.json()["confirmed"] is False

    # Confirm substitution
    conf_res = client.post(f"/api/v1/school/substitutions/{sub_id}/confirm", headers=school_manager_headers)
    assert conf_res.status_code == 200
    assert conf_res.json()["confirmed"] is True

def test_list_substitutions_endpoint(client, school_manager_headers):
    response = client.get("/api/v1/school/substitutions", headers=school_manager_headers)
    assert response.status_code == 200
    subs = response.json()
    assert isinstance(subs, list)

def test_list_absences_endpoint(client, school_manager_headers):
    response = client.get("/api/v1/school/absences", headers=school_manager_headers)
    assert response.status_code == 200
    abs_list = response.json()
    assert isinstance(abs_list, list)

