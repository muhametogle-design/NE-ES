"""Tests for the District domain: model relationship, /api/v1/districts CRUD,
duplicate-code validation, filtering/pagination and role-based access."""
import uuid

import pytest

from app.models.academic import District
from app.models.tenancy import PrivateSchool

BASE = "/api/v1/districts"


def _unique_code(prefix: str = "T") -> str:
    return f"{prefix}{uuid.uuid4().hex[:6].upper()}"


def _payload(**overrides):
    data = {
        "code": _unique_code(),
        "name": "Test Regional Education Office",
        "region": "Sool",
        "reo_contact_email": "reo.test@education.gov",
    }
    data.update(overrides)
    return data


@pytest.fixture
def district(client, state_admin_headers):
    """A freshly created district (via the API) for read/update tests."""
    res = client.post(BASE, json=_payload(), headers=state_admin_headers)
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def test_create_district_returns_201_with_full_representation(client, state_admin_headers):
    payload = _payload(code="sool-01", name="  Sool REO  ")
    res = client.post(BASE, json=payload, headers=state_admin_headers)
    assert res.status_code == 201, res.text
    body = res.json()

    uuid.UUID(body["id"])  # valid UUID primary key
    assert body["code"] == "SOOL-01"  # normalised to upper-case
    assert body["name"] == "Sool REO"  # whitespace stripped
    assert body["region"] == "Sool"
    assert body["reo_contact_email"] == "reo.test@education.gov"
    assert body["is_active"] is True
    assert body["school_count"] == 0
    assert body["created_at"] and body["updated_at"]


def test_create_district_persists_to_database(client, state_admin_headers, db_session):
    payload = _payload()
    res = client.post(BASE, json=payload, headers=state_admin_headers)
    assert res.status_code == 201

    row = db_session.query(District).filter(District.code == payload["code"]).one()
    assert str(row.id) == res.json()["id"]
    assert row.name == payload["name"]
    assert row.is_active is True


def test_create_district_duplicate_code_rejected_with_409(client, state_admin_headers):
    payload = _payload(code="DUPE01")
    first = client.post(BASE, json=payload, headers=state_admin_headers)
    assert first.status_code == 201

    second = client.post(BASE, json={**payload, "name": "Another Name"}, headers=state_admin_headers)
    assert second.status_code == 409
    assert "already exists" in second.json()["detail"]
    assert "DUPE01" in second.json()["detail"]


def test_create_district_duplicate_code_is_case_insensitive(client, state_admin_headers):
    assert client.post(BASE, json=_payload(code="CASE01"), headers=state_admin_headers).status_code == 201
    dup = client.post(BASE, json=_payload(code="case01"), headers=state_admin_headers)
    assert dup.status_code == 409


@pytest.mark.parametrize(
    "bad_field, bad_value",
    [
        ("code", "X"),  # too short
        ("code", "bad code!"),  # disallowed characters
        ("code", "A" * 17),  # too long
        ("name", ""),
        ("region", ""),
        ("reo_contact_email", "not-an-email"),
    ],
)
def test_create_district_validation_errors(client, state_admin_headers, bad_field, bad_value):
    res = client.post(BASE, json=_payload(**{bad_field: bad_value}), headers=state_admin_headers)
    assert res.status_code == 422
    assert any(bad_field in (err.get("loc") or []) for err in res.json()["detail"])


def test_create_district_missing_required_fields(client, state_admin_headers):
    res = client.post(BASE, json={"name": "Only a name"}, headers=state_admin_headers)
    assert res.status_code == 422


def test_reo_contact_email_is_optional(client, state_admin_headers):
    payload = _payload()
    payload.pop("reo_contact_email")
    res = client.post(BASE, json=payload, headers=state_admin_headers)
    assert res.status_code == 201
    assert res.json()["reo_contact_email"] is None


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def test_get_district_by_id(client, state_admin_headers, district):
    res = client.get(f"{BASE}/{district['id']}", headers=state_admin_headers)
    assert res.status_code == 200
    assert res.json() == district


def test_get_district_unknown_id_returns_404(client, state_admin_headers):
    res = client.get(f"{BASE}/{uuid.uuid4()}", headers=state_admin_headers)
    assert res.status_code == 404
    assert res.json()["detail"] == "District not found"


def test_get_district_malformed_id_returns_422(client, state_admin_headers):
    res = client.get(f"{BASE}/not-a-uuid", headers=state_admin_headers)
    assert res.status_code == 422


def test_list_districts_is_paginated(client, state_admin_headers):
    for _ in range(3):
        assert client.post(BASE, json=_payload(region="Pagination"), headers=state_admin_headers).status_code == 201

    res = client.get(BASE, params={"region": "Pagination", "per_page": 2, "page": 1}, headers=state_admin_headers)
    assert res.status_code == 200
    body = res.json()
    assert set(body) == {"items", "total", "page", "pages"}
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["pages"] == 2
    assert len(body["items"]) == 2

    page2 = client.get(BASE, params={"region": "Pagination", "per_page": 2, "page": 2}, headers=state_admin_headers).json()
    assert len(page2["items"]) == 1
    ids_page1 = {d["id"] for d in body["items"]}
    ids_page2 = {d["id"] for d in page2["items"]}
    assert ids_page1.isdisjoint(ids_page2)


def test_list_districts_filter_by_region_is_case_insensitive(client, state_admin_headers):
    client.post(BASE, json=_payload(region="Togdheer"), headers=state_admin_headers)
    client.post(BASE, json=_payload(region="Sanaag"), headers=state_admin_headers)

    res = client.get(BASE, params={"region": "togdheer"}, headers=state_admin_headers)
    assert res.status_code == 200
    items = res.json()["items"]
    assert items and all(d["region"] == "Togdheer" for d in items)


def test_list_districts_filter_by_is_active_and_search(client, state_admin_headers):
    active = client.post(BASE, json=_payload(code="SRCH01", name="Searchable Alpha", region="Filter"), headers=state_admin_headers).json()
    inactive = client.post(BASE, json=_payload(code="SRCH02", name="Searchable Beta", region="Filter", is_active=False), headers=state_admin_headers).json()

    res = client.get(BASE, params={"region": "Filter", "is_active": "false"}, headers=state_admin_headers)
    assert [d["id"] for d in res.json()["items"]] == [inactive["id"]]

    res = client.get(BASE, params={"q": "alpha"}, headers=state_admin_headers)
    ids = {d["id"] for d in res.json()["items"]}
    assert active["id"] in ids and inactive["id"] not in ids


def test_list_districts_rejects_invalid_pagination(client, state_admin_headers):
    assert client.get(BASE, params={"page": 0}, headers=state_admin_headers).status_code == 422
    assert client.get(BASE, params={"per_page": 101}, headers=state_admin_headers).status_code == 422


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------
def test_patch_district_partial_update(client, state_admin_headers, district):
    res = client.patch(
        f"{BASE}/{district['id']}",
        json={"name": "Renamed Office", "is_active": False},
        headers=state_admin_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Renamed Office"
    assert body["is_active"] is False
    # untouched fields preserved
    assert body["code"] == district["code"]
    assert body["region"] == district["region"]
    assert body["reo_contact_email"] == district["reo_contact_email"]
    assert body["created_at"] == district["created_at"]


def test_patch_district_can_change_code_when_free(client, state_admin_headers, district):
    res = client.patch(f"{BASE}/{district['id']}", json={"code": "newcode1"}, headers=state_admin_headers)
    assert res.status_code == 200
    assert res.json()["code"] == "NEWCODE1"

    # setting the same code again on the same record is a no-op, not a conflict
    again = client.patch(f"{BASE}/{district['id']}", json={"code": "NEWCODE1"}, headers=state_admin_headers)
    assert again.status_code == 200


def test_patch_district_duplicate_code_rejected_with_409(client, state_admin_headers, district):
    other = client.post(BASE, json=_payload(code="TAKEN01"), headers=state_admin_headers).json()

    res = client.patch(f"{BASE}/{district['id']}", json={"code": "taken01"}, headers=state_admin_headers)
    assert res.status_code == 409
    assert "already exists" in res.json()["detail"]

    # original record unchanged
    current = client.get(f"{BASE}/{district['id']}", headers=state_admin_headers).json()
    assert current["code"] == district["code"]
    assert client.get(f"{BASE}/{other['id']}", headers=state_admin_headers).json()["code"] == "TAKEN01"


def test_patch_district_empty_body_rejected(client, state_admin_headers, district):
    res = client.patch(f"{BASE}/{district['id']}", json={}, headers=state_admin_headers)
    assert res.status_code == 422
    assert res.json()["detail"] == "No fields provided for update"


def test_patch_district_validation_error(client, state_admin_headers, district):
    res = client.patch(f"{BASE}/{district['id']}", json={"reo_contact_email": "nope"}, headers=state_admin_headers)
    assert res.status_code == 422


def test_patch_unknown_district_returns_404(client, state_admin_headers):
    res = client.patch(f"{BASE}/{uuid.uuid4()}", json={"name": "Ghost"}, headers=state_admin_headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Authorization
# ---------------------------------------------------------------------------
def test_district_endpoints_require_authentication(client):
    assert client.get(BASE).status_code == 401
    assert client.post(BASE, json=_payload()).status_code == 401
    assert client.get(f"{BASE}/{uuid.uuid4()}").status_code == 401
    assert client.patch(f"{BASE}/{uuid.uuid4()}", json={"name": "x"}).status_code == 401


def test_inspector_can_read_but_not_write_districts(client, inspector_headers, district):
    assert client.get(BASE, headers=inspector_headers).status_code == 200
    assert client.get(f"{BASE}/{district['id']}", headers=inspector_headers).status_code == 200

    assert client.post(BASE, json=_payload(), headers=inspector_headers).status_code == 403
    assert client.patch(f"{BASE}/{district['id']}", json={"name": "x"}, headers=inspector_headers).status_code == 403


def test_school_tenants_cannot_access_districts(client, school_manager_headers, teacher_headers, district):
    for headers in (school_manager_headers, teacher_headers):
        assert client.get(BASE, headers=headers).status_code == 403
        assert client.get(f"{BASE}/{district['id']}", headers=headers).status_code == 403
        assert client.post(BASE, json=_payload(), headers=headers).status_code == 403
        assert client.patch(f"{BASE}/{district['id']}", json={"name": "x"}, headers=headers).status_code == 403


# ---------------------------------------------------------------------------
# Model relationship: District <-> PrivateSchool
# ---------------------------------------------------------------------------
def test_school_district_relationship_and_school_count(client, state_admin_headers, db_session, district):
    school = db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "IL").one()
    try:
        school.district_id = uuid.UUID(district["id"])
        db_session.commit()

        db_session.refresh(school)
        assert school.district is not None
        assert school.district.code == district["code"]
        assert [s.school_code for s in school.district.schools] == ["IL"]

        res = client.get(f"{BASE}/{district['id']}", headers=state_admin_headers)
        assert res.json()["school_count"] == 1

        listed = client.get(BASE, params={"q": district["code"]}, headers=state_admin_headers).json()["items"]
        assert listed[0]["school_count"] == 1
    finally:
        school.district_id = None
        db_session.commit()


def test_district_updated_at_changes_on_update(db_session):
    d = District(code=_unique_code("U"), name="Timestamp Probe", region="Probe")
    db_session.add(d)
    db_session.commit()
    created, updated = d.created_at, d.updated_at
    assert created is not None and updated is not None

    d.name = "Timestamp Probe (renamed)"
    db_session.commit()
    db_session.refresh(d)
    assert d.created_at == created
    assert d.updated_at >= updated
