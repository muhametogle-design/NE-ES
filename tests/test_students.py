"""Tests for the V1 Student API: CRUD, tenancy, capacity and emis_id uniqueness."""
import uuid

import pytest

from app.models.tenancy import PrivateSchool

BASE = "/api/v1/students"
CLASSROOMS = "/api/v1/classrooms"


@pytest.fixture
def il_school(db_session):
    return db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "IL").first()


@pytest.fixture
def ng_school(db_session):
    return db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "NG").first()


def _emis():
    return f"NE-2026-{uuid.uuid4().hex[:8].upper()}"


def _payload(school_id, **overrides):
    data = {
        "school_id": school_id,
        "emis_id": _emis(),
        "first_name": "Amina",
        "last_name": "Hassan",
        "gender": "female",
    }
    data.update(overrides)
    return data


def _create(client, headers, school_id, **overrides):
    resp = client.post(BASE, json=_payload(school_id, **overrides), headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _make_classroom(client, headers, school_id, capacity=40, name=None):
    resp = client.post(
        CLASSROOMS,
        json={
            "school_id": school_id,
            "name": name or f"Room {uuid.uuid4().hex[:6]}",
            "grade_level": "Grade 10",
            "academic_year": "2025-2026",
            "capacity": capacity,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --------------------------------------------------------------- CRUD


def test_create_student(client, school_manager_headers, il_school):
    body = _create(client, school_manager_headers, il_school.id, first_name="  Amina  ")
    assert body["first_name"] == "Amina"  # sanitized
    assert body["school_id"] == il_school.id
    assert body["is_active"] is True
    assert uuid.UUID(body["id"])


def test_create_with_classroom(client, school_manager_headers, il_school):
    room = _make_classroom(client, school_manager_headers, il_school.id)
    body = _create(client, school_manager_headers, il_school.id, classroom_id=room["id"])
    assert body["classroom_id"] == room["id"]


def test_create_unknown_school_404(client, state_admin_headers):
    resp = client.post(BASE, json=_payload(999999), headers=state_admin_headers)
    assert resp.status_code == 404


def test_create_unknown_classroom_404(client, school_manager_headers, il_school):
    resp = client.post(
        BASE,
        json=_payload(
            il_school.id, classroom_id="00000000-0000-0000-0000-000000000000"
        ),
        headers=school_manager_headers,
    )
    assert resp.status_code == 404


def test_create_classroom_from_other_school_rejected(
    client, state_admin_headers, il_school, ng_school
):
    room = _make_classroom(client, state_admin_headers, ng_school.id)
    resp = client.post(
        BASE,
        json=_payload(il_school.id, classroom_id=room["id"]),
        headers=state_admin_headers,
    )
    assert resp.status_code == 400


def test_get_student_and_404(client, school_manager_headers, il_school):
    created = _create(client, school_manager_headers, il_school.id)
    resp = client.get(f"{BASE}/{created['id']}", headers=school_manager_headers)
    assert resp.status_code == 200
    assert resp.json()["emis_id"] == created["emis_id"]

    missing = client.get(
        f"{BASE}/00000000-0000-0000-0000-000000000000", headers=school_manager_headers
    )
    assert missing.status_code == 404


def test_patch_student_details(client, school_manager_headers, il_school):
    created = _create(client, school_manager_headers, il_school.id)
    resp = client.patch(
        f"{BASE}/{created['id']}",
        json={"last_name": "Yusuf", "gender": "male", "is_active": False},
        headers=school_manager_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["last_name"] == "Yusuf"
    assert body["gender"] == "male"
    assert body["is_active"] is False


def test_patch_transfers_classroom(client, school_manager_headers, il_school):
    room_a = _make_classroom(client, school_manager_headers, il_school.id)
    room_b = _make_classroom(client, school_manager_headers, il_school.id)
    created = _create(client, school_manager_headers, il_school.id, classroom_id=room_a["id"])

    resp = client.patch(
        f"{BASE}/{created['id']}",
        json={"classroom_id": room_b["id"]},
        headers=school_manager_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["classroom_id"] == room_b["id"]


# --------------------------------------------------------- validation


@pytest.mark.parametrize("gender", ["unknown", "", "m"])
def test_gender_must_be_valid(client, school_manager_headers, il_school, gender):
    resp = client.post(
        BASE, json=_payload(il_school.id, gender=gender), headers=school_manager_headers
    )
    assert resp.status_code == 422


def test_gender_is_normalized(client, school_manager_headers, il_school):
    body = _create(client, school_manager_headers, il_school.id, gender="MALE")
    assert body["gender"] == "male"


def test_blank_name_rejected(client, school_manager_headers, il_school):
    resp = client.post(
        BASE, json=_payload(il_school.id, first_name="   "), headers=school_manager_headers
    )
    assert resp.status_code == 422


def test_duplicate_emis_id_rejected(client, school_manager_headers, il_school):
    created = _create(client, school_manager_headers, il_school.id)
    resp = client.post(
        BASE,
        json=_payload(il_school.id, emis_id=created["emis_id"]),
        headers=school_manager_headers,
    )
    assert resp.status_code == 409


def test_emis_id_unique_across_schools(
    client, state_admin_headers, il_school, ng_school
):
    created = _create(client, state_admin_headers, il_school.id)
    resp = client.post(
        BASE,
        json=_payload(ng_school.id, emis_id=created["emis_id"]),
        headers=state_admin_headers,
    )
    assert resp.status_code == 409


# ----------------------------------------------------- capacity bounds


def test_classroom_capacity_enforced_on_create(client, school_manager_headers, il_school):
    room = _make_classroom(client, school_manager_headers, il_school.id, capacity=1)
    _create(client, school_manager_headers, il_school.id, classroom_id=room["id"])

    resp = client.post(
        BASE,
        json=_payload(il_school.id, classroom_id=room["id"]),
        headers=school_manager_headers,
    )
    assert resp.status_code == 409
    assert "capacity" in resp.json()["detail"].lower()


def test_classroom_capacity_enforced_on_transfer(client, school_manager_headers, il_school):
    full = _make_classroom(client, school_manager_headers, il_school.id, capacity=1)
    _create(client, school_manager_headers, il_school.id, classroom_id=full["id"])
    other = _create(client, school_manager_headers, il_school.id)

    resp = client.patch(
        f"{BASE}/{other['id']}",
        json={"classroom_id": full["id"]},
        headers=school_manager_headers,
    )
    assert resp.status_code == 409


def test_inactive_students_do_not_consume_capacity(
    client, school_manager_headers, il_school
):
    room = _make_classroom(client, school_manager_headers, il_school.id, capacity=1)
    sitting = _create(client, school_manager_headers, il_school.id, classroom_id=room["id"])
    client.patch(
        f"{BASE}/{sitting['id']}", json={"is_active": False}, headers=school_manager_headers
    )

    resp = client.post(
        BASE,
        json=_payload(il_school.id, classroom_id=room["id"]),
        headers=school_manager_headers,
    )
    assert resp.status_code == 201


def test_patch_keeping_same_classroom_at_capacity_allowed(
    client, school_manager_headers, il_school
):
    room = _make_classroom(client, school_manager_headers, il_school.id, capacity=1)
    student = _create(client, school_manager_headers, il_school.id, classroom_id=room["id"])

    resp = client.patch(
        f"{BASE}/{student['id']}",
        json={"classroom_id": room["id"], "first_name": "Renamed"},
        headers=school_manager_headers,
    )
    assert resp.status_code == 200


# ------------------------------------------------------------ tenancy


def test_school_manager_cannot_create_for_other_school(
    client, school_manager_headers, ng_school
):
    resp = client.post(BASE, json=_payload(ng_school.id), headers=school_manager_headers)
    assert resp.status_code == 403


def test_cross_tenant_read_and_write_forbidden(
    client, state_admin_headers, other_school_manager_headers, il_school
):
    created = _create(client, state_admin_headers, il_school.id)
    assert (
        client.get(f"{BASE}/{created['id']}", headers=other_school_manager_headers).status_code
        == 403
    )
    assert (
        client.patch(
            f"{BASE}/{created['id']}",
            json={"first_name": "Hacked"},
            headers=other_school_manager_headers,
        ).status_code
        == 403
    )


def test_list_scoped_to_own_school(client, school_manager_headers, il_school):
    _create(client, school_manager_headers, il_school.id)
    body = client.get(BASE, headers=school_manager_headers).json()
    assert body["items"]
    assert {r["school_id"] for r in body["items"]} == {il_school.id}


def test_list_cross_school_query_forbidden(client, school_manager_headers, ng_school):
    resp = client.get(f"{BASE}?school_id={ng_school.id}", headers=school_manager_headers)
    assert resp.status_code == 403


def test_state_role_queries_across_schools(
    client, state_admin_headers, inspector_headers, il_school, ng_school
):
    _create(client, state_admin_headers, il_school.id)
    _create(client, state_admin_headers, ng_school.id)

    all_rows = client.get(f"{BASE}?per_page=100", headers=state_admin_headers).json()
    assert all_rows["total"] >= 2

    scoped = client.get(
        f"{BASE}?school_id={ng_school.id}&per_page=100", headers=inspector_headers
    ).json()
    assert {r["school_id"] for r in scoped["items"]} == {ng_school.id}


def test_teacher_cannot_write(client, teacher_headers, il_school):
    resp = client.post(BASE, json=_payload(il_school.id), headers=teacher_headers)
    assert resp.status_code == 403


def test_requires_authentication(client, il_school):
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=_payload(il_school.id)).status_code == 401


# ------------------------------------------------- filters & pagination


def test_search_by_name_and_emis_id(client, school_manager_headers, il_school):
    created = _create(
        client, school_manager_headers, il_school.id, first_name="Zdenka", last_name="Marvel"
    )

    by_name = client.get(f"{BASE}?q=Zdenka", headers=school_manager_headers).json()
    assert [r["id"] for r in by_name["items"]] == [created["id"]]

    by_emis = client.get(
        f"{BASE}?q={created['emis_id']}", headers=school_manager_headers
    ).json()
    assert [r["id"] for r in by_emis["items"]] == [created["id"]]


def test_filter_by_classroom_and_is_active(client, school_manager_headers, il_school):
    room = _make_classroom(client, school_manager_headers, il_school.id, capacity=5)
    active = _create(client, school_manager_headers, il_school.id, classroom_id=room["id"])
    inactive = _create(
        client, school_manager_headers, il_school.id, classroom_id=room["id"], is_active=False
    )

    in_room = client.get(
        f"{BASE}?classroom_id={room['id']}", headers=school_manager_headers
    ).json()
    assert {r["id"] for r in in_room["items"]} == {active["id"], inactive["id"]}

    only_active = client.get(
        f"{BASE}?classroom_id={room['id']}&is_active=true", headers=school_manager_headers
    ).json()
    assert [r["id"] for r in only_active["items"]] == [active["id"]]


def test_pagination(client, school_manager_headers, il_school):
    for _ in range(3):
        _create(client, school_manager_headers, il_school.id)

    page1 = client.get(f"{BASE}?page=1&per_page=2", headers=school_manager_headers).json()
    assert len(page1["items"]) == 2
    assert page1["per_page"] == 2
    assert page1["pages"] == max(1, -(-page1["total"] // 2))

    page2 = client.get(f"{BASE}?page=2&per_page=2", headers=school_manager_headers).json()
    assert {r["id"] for r in page1["items"]}.isdisjoint({r["id"] for r in page2["items"]})
