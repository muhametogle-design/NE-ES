"""Tests for the V1 Classroom API: CRUD, tenancy, validation and filters."""
import pytest

from app.models.tenancy import PrivateSchool

BASE = "/api/v1/classrooms"


@pytest.fixture
def il_school(db_session):
    return db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "IL").first()


@pytest.fixture
def ng_school(db_session):
    return db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "NG").first()


def _payload(school_id, **overrides):
    data = {
        "school_id": school_id,
        "name": "Grade 10-A",
        "grade_level": "Grade 10",
        "academic_year": "2025-2026",
        "capacity": 40,
    }
    data.update(overrides)
    return data


def _create(client, headers, school_id, **overrides):
    resp = client.post(BASE, json=_payload(school_id, **overrides), headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------- CRUD


def test_create_classroom_as_school_manager(client, school_manager_headers, il_school):
    body = _create(client, school_manager_headers, il_school.id, name="  Grade 9-B  ")
    assert body["name"] == "Grade 9-B"  # sanitized
    assert body["school_id"] == il_school.id
    assert body["is_active"] is True
    assert body["id"]


def test_create_classroom_as_state_admin(client, state_admin_headers, ng_school):
    body = _create(client, state_admin_headers, ng_school.id, name="Grade 11-C")
    assert body["school_id"] == ng_school.id


def test_create_classroom_unknown_school_404(client, state_admin_headers):
    resp = client.post(BASE, json=_payload(999999), headers=state_admin_headers)
    assert resp.status_code == 404


def test_get_classroom_and_404(client, school_manager_headers, il_school):
    created = _create(client, school_manager_headers, il_school.id)
    resp = client.get(f"{BASE}/{created['id']}", headers=school_manager_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]

    missing = client.get(
        f"{BASE}/00000000-0000-0000-0000-000000000000", headers=school_manager_headers
    )
    assert missing.status_code == 404


def test_patch_classroom(client, school_manager_headers, il_school):
    created = _create(client, school_manager_headers, il_school.id)
    resp = client.patch(
        f"{BASE}/{created['id']}",
        json={"capacity": 55, "name": "Grade 10-Z"},
        headers=school_manager_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["capacity"] == 55
    assert body["name"] == "Grade 10-Z"
    assert body["grade_level"] == created["grade_level"]


def test_delete_classroom_hard(client, school_manager_headers, il_school):
    created = _create(client, school_manager_headers, il_school.id)
    resp = client.delete(f"{BASE}/{created['id']}", headers=school_manager_headers)
    assert resp.status_code == 204
    assert client.get(f"{BASE}/{created['id']}", headers=school_manager_headers).status_code == 404


def test_delete_classroom_soft(client, school_manager_headers, il_school):
    created = _create(client, school_manager_headers, il_school.id)
    resp = client.delete(f"{BASE}/{created['id']}?soft=true", headers=school_manager_headers)
    assert resp.status_code == 204
    body = client.get(f"{BASE}/{created['id']}", headers=school_manager_headers).json()
    assert body["is_active"] is False


# ----------------------------------------------------------- validation


@pytest.mark.parametrize("capacity", [0, -5])
def test_capacity_must_be_positive(client, school_manager_headers, il_school, capacity):
    resp = client.post(
        BASE, json=_payload(il_school.id, capacity=capacity), headers=school_manager_headers
    )
    assert resp.status_code == 422


def test_patch_capacity_validation(client, school_manager_headers, il_school):
    created = _create(client, school_manager_headers, il_school.id)
    resp = client.patch(
        f"{BASE}/{created['id']}", json={"capacity": 0}, headers=school_manager_headers
    )
    assert resp.status_code == 422


def test_blank_name_rejected(client, school_manager_headers, il_school):
    resp = client.post(
        BASE, json=_payload(il_school.id, name="   "), headers=school_manager_headers
    )
    assert resp.status_code == 422


# ------------------------------------------------------------- tenancy


def test_school_manager_cannot_create_for_other_school(
    client, school_manager_headers, ng_school
):
    resp = client.post(BASE, json=_payload(ng_school.id), headers=school_manager_headers)
    assert resp.status_code == 403


def test_school_manager_cannot_read_other_school_classroom(
    client, state_admin_headers, other_school_manager_headers, il_school
):
    created = _create(client, state_admin_headers, il_school.id, name="Grade 12-A")
    resp = client.get(f"{BASE}/{created['id']}", headers=other_school_manager_headers)
    assert resp.status_code == 403


def test_school_manager_cannot_patch_or_delete_other_school_classroom(
    client, state_admin_headers, other_school_manager_headers, il_school
):
    created = _create(client, state_admin_headers, il_school.id, name="Grade 12-B")
    assert (
        client.patch(
            f"{BASE}/{created['id']}", json={"capacity": 10}, headers=other_school_manager_headers
        ).status_code
        == 403
    )
    assert (
        client.delete(f"{BASE}/{created['id']}", headers=other_school_manager_headers).status_code
        == 403
    )


def test_list_scoped_to_own_school(
    client, school_manager_headers, state_admin_headers, il_school, ng_school
):
    _create(client, school_manager_headers, il_school.id, name="Scoped IL")
    _create(client, state_admin_headers, ng_school.id, name="Scoped NG")

    rows = client.get(BASE, headers=school_manager_headers).json()
    assert rows
    assert {r["school_id"] for r in rows} == {il_school.id}


def test_list_cross_school_query_forbidden(client, school_manager_headers, ng_school):
    resp = client.get(f"{BASE}?school_id={ng_school.id}", headers=school_manager_headers)
    assert resp.status_code == 403


def test_state_role_can_query_across_schools(
    client, state_admin_headers, inspector_headers, il_school, ng_school
):
    _create(client, state_admin_headers, il_school.id, name="Cross IL")
    _create(client, state_admin_headers, ng_school.id, name="Cross NG")

    rows = client.get(BASE, headers=state_admin_headers).json()
    assert {il_school.id, ng_school.id} <= {r["school_id"] for r in rows}

    scoped = client.get(f"{BASE}?school_id={ng_school.id}", headers=inspector_headers).json()
    assert {r["school_id"] for r in scoped} == {ng_school.id}


def test_teacher_cannot_write(client, teacher_headers, il_school):
    resp = client.post(BASE, json=_payload(il_school.id), headers=teacher_headers)
    assert resp.status_code == 403


def test_requires_authentication(client, il_school):
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=_payload(il_school.id)).status_code == 401


# -------------------------------------------------------------- filters


def test_filters(client, state_admin_headers, il_school):
    _create(
        client,
        state_admin_headers,
        il_school.id,
        name="Filter A",
        grade_level="Grade 7",
        academic_year="2030-2031",
    )
    _create(
        client,
        state_admin_headers,
        il_school.id,
        name="Filter B",
        grade_level="Grade 8",
        academic_year="2030-2031",
        is_active=False,
    )

    by_grade = client.get(
        f"{BASE}?school_id={il_school.id}&grade_level=Grade 7", headers=state_admin_headers
    ).json()
    assert [r["name"] for r in by_grade] == ["Filter A"]

    by_year = client.get(
        f"{BASE}?academic_year=2030-2031&school_id={il_school.id}", headers=state_admin_headers
    ).json()
    assert {r["name"] for r in by_year} == {"Filter A", "Filter B"}

    inactive = client.get(
        f"{BASE}?academic_year=2030-2031&is_active=false", headers=state_admin_headers
    ).json()
    assert [r["name"] for r in inactive] == ["Filter B"]
