"""Legacy WebAuthn coverage and tenant-scoped fingerprint template API tests."""
import base64
import uuid
from datetime import datetime, timezone

import pytest

from app.models import Base, StudentBiometric, all_models
from app.models.academic import Student
from app.models.biometric import FingerPosition
from app.models.tenancy import PrivateSchool
from app.schemas.biometric import MAX_TEMPLATE_LENGTH

def test_biometric_registration_and_verification_flow(client, school_manager_headers, db_session):
    student = db_session.query(Student).filter(Student.school_id == 1).first()

    # 1. Options generator
    opt_res = client.post("/api/v1/school/biometrics/register/options", headers=school_manager_headers, json={
        "student_id": student.id
    })
    assert opt_res.status_code == 200
    assert "challenge" in opt_res.json()
    assert opt_res.json()["user"]["id"] == str(student.id)

    # 2. Register Credential
    cred_id = f"FIDO2-TEST-{student.roll_number}-123"
    reg_res = client.post("/api/v1/school/biometrics/register/verify", headers=school_manager_headers, json={
        "student_id": student.id,
        "credential_id": cred_id,
        "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA..."
    })
    assert reg_res.status_code == 200
    assert "registered successfully" in reg_res.json()["message"]

    # 3. Verify Biometric for Exam Hall Entry (Success)
    ver_res = client.post("/api/v1/school/biometrics/verify", headers=school_manager_headers, json={
        "credential_id": cred_id,
        "verification_type": "exam_hall_entry"
    })
    assert ver_res.status_code == 200
    data = ver_res.json()
    assert data["success"] is True
    assert data["status"] == "success"
    assert data["student_id"] == student.id
    assert data["roll_number"] == student.roll_number

    # 4. Verify Unknown Credential (Rejected)
    rej_res = client.post("/api/v1/school/biometrics/verify", headers=school_manager_headers, json={
        "credential_id": "UNKNOWN-CREDENTIAL-999",
        "verification_type": "exam_hall_entry"
    })
    assert rej_res.status_code == 200
    rej_data = rej_res.json()
    assert rej_data["success"] is False
    assert rej_data["status"] == "failed"
    assert "Unrecognized" in rej_data["reason"]

    # 5. Check Logs
    logs_res = client.get("/api/v1/school/biometrics/logs", headers=school_manager_headers)
    assert logs_res.status_code == 200
    logs = logs_res.json()
    assert len(logs) >= 2

def test_biometric_options_nonexistent_student_returns_404(client, school_manager_headers):
    response = client.post("/api/v1/school/biometrics/register/options", headers=school_manager_headers, json={
        "student_id": 99999
    })
    assert response.status_code == 404

def test_staff_checkin_biometrics(client, teacher_headers):
    response = client.post("/api/v1/school/biometrics/staff-checkin", headers=teacher_headers, json={
        "credential_id": "STAFF-KEY-9988",
        "verification_type": "staff_attendance"
    })
    assert response.status_code == 200
    assert response.json()["status"] == "success"


# ---------------------------------------------------------------------------
# Fingerprint templates (/api/v1/biometrics), not WebAuthn credentials.
# Synthetic binary records are sufficient for testing the exact-match contract;
# they are deliberately not represented as real ISO/ANSI fingerprint scans.
# ---------------------------------------------------------------------------
FINGERPRINT_BASE = "/api/v1/biometrics"


def _template():
    return base64.b64encode(uuid.uuid4().bytes).decode("ascii")


@pytest.fixture
def fingerprint_student_factory(db_session):
    """Create and clean up test students without mutating the shared demo data."""
    created_ids = []

    def create(school_code="IL", is_active=True):
        school = db_session.query(PrivateSchool).filter_by(school_code=school_code).one()
        tag = uuid.uuid4().hex
        student = Student(
            school_id=school.id,
            national_student_id=f"BIO-{tag}",
            roll_number=f"{school_code}-BIO-{tag}",
            first_name=f"Fingerprint-{tag[:8]}",
            last_name="Test",
            gender="F",
            is_active=is_active,
        )
        db_session.add(student)
        db_session.commit()
        db_session.refresh(student)
        created_ids.append(student.id)
        return student

    yield create

    db_session.rollback()
    for student in db_session.query(Student).filter(Student.id.in_(created_ids)).all():
        db_session.delete(student)
    db_session.commit()


def _enroll_fingerprint(client, headers, student, **overrides):
    payload = {"student_id": student.id, "template_data": _template(), **overrides}
    response = client.post(f"{FINGERPRINT_BASE}/enroll", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return payload, response.json()


def _verify_fingerprint(client, headers, school_id, template_data, **overrides):
    return client.post(
        f"{FINGERPRINT_BASE}/verify",
        headers=headers,
        json={"school_id": school_id, "template_data": template_data, **overrides},
    )


def _assert_not_verified(response):
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verified"] is False
    assert body["student_id"] is None
    assert body["student_name"] is None
    assert body["roll_number"] is None
    assert body["message"]
    assert "template_data" not in body


def test_fingerprint_enrollment_defaults_and_persistence(
    client, school_manager_headers, db_session, fingerprint_student_factory,
):
    student = fingerprint_student_factory()
    payload, body = _enroll_fingerprint(client, school_manager_headers, student)

    record_id = uuid.UUID(body["id"])
    assert record_id.version == 4
    assert body["student_id"] == student.id
    assert isinstance(body["student_id"], int)
    assert body["finger_position"] == "RIGHT_INDEX"
    assert body["template_format"] == "ISO_19794_2"
    assert body["quality_score"] is None
    assert body["device_model"] is None
    assert datetime.fromisoformat(body["created_at"])
    assert datetime.fromisoformat(body["updated_at"])
    assert "template_data" not in body

    row = db_session.get(StudentBiometric, record_id)
    assert row.template_data == payload["template_data"]
    assert row.student is student
    assert row in student.biometrics
    assert row.finger_position is FingerPosition.RIGHT_INDEX


@pytest.mark.parametrize("position", list(FingerPosition))
def test_fingerprint_enrollment_all_fingers_and_metadata(
    client, school_manager_headers, db_session, fingerprint_student_factory, position,
):
    student = fingerprint_student_factory()
    _, body = _enroll_fingerprint(
        client, school_manager_headers, student,
        finger_position=position.value,
        template_format="  ansi_378  ",
        quality_score=92,
        device_model="Test Fingerprint Reader",
    )
    assert body["finger_position"] == position.value
    assert body["template_format"] == "ANSI_378"
    assert body["quality_score"] == 92
    assert body["device_model"] == "Test Fingerprint Reader"
    row = db_session.get(StudentBiometric, uuid.UUID(body["id"]))
    assert row.finger_position is position
    assert row.template_format == body["template_format"]
    assert row.quality_score == body["quality_score"]
    assert row.device_model == body["device_model"]


@pytest.mark.parametrize("quality", [0, 100])
def test_fingerprint_quality_score_boundaries(
    client, school_manager_headers, fingerprint_student_factory, quality,
):
    _, body = _enroll_fingerprint(
        client, school_manager_headers, fingerprint_student_factory(), quality_score=quality,
    )
    assert body["quality_score"] == quality


def test_fingerprint_enrollment_unknown_student_is_404(client, school_manager_headers, db_session):
    count = db_session.query(StudentBiometric).count()
    response = client.post(
        f"{FINGERPRINT_BASE}/enroll", headers=school_manager_headers,
        json={"student_id": 999999999, "template_data": _template()},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"
    assert db_session.query(StudentBiometric).count() == count


def test_fingerprint_enrollment_cannot_target_other_tenant(
    client, school_manager_headers, other_school_manager_headers, db_session, fingerprint_student_factory,
):
    student = fingerprint_student_factory("NG")
    payload = {"student_id": student.id, "template_data": _template()}
    response = client.post(f"{FINGERPRINT_BASE}/enroll", headers=school_manager_headers, json=payload)
    assert response.status_code == 404
    assert response.json()["detail"] == "Student not found"
    assert db_session.query(StudentBiometric).filter_by(student_id=student.id).count() == 0

    # The same student is visible to the correct tenant only.
    _, enrolled = _enroll_fingerprint(client, other_school_manager_headers, student, **payload)
    assert enrolled["student_id"] == student.id
    again = client.post(f"{FINGERPRINT_BASE}/enroll", headers=school_manager_headers, json=payload)
    assert again.status_code == 404
    assert db_session.query(StudentBiometric).filter_by(student_id=student.id).count() == 1


def test_fingerprint_verification_matches_one_of_many_active_students(
    client, school_manager_headers, fingerprint_student_factory,
):
    students = [fingerprint_student_factory() for _ in range(3)]
    enrollments = [_enroll_fingerprint(client, school_manager_headers, student) for student in students]
    target = students[-1]
    response = _verify_fingerprint(
        client, school_manager_headers, target.school_id, enrollments[-1][0]["template_data"],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["verified"] is True
    assert body["student_id"] == target.id
    assert body["student_name"] == f"{target.first_name} {target.last_name}"
    assert body["roll_number"] == target.roll_number
    assert body["message"] == "Exact template match found"
    assert "template_data" not in body


def test_fingerprint_verification_unknown_template_has_no_identity(
    client, school_manager_headers, fingerprint_student_factory,
):
    student = fingerprint_student_factory()
    # Empty candidate set, then an unrelated enrollment: both are safe no-matches.
    _assert_not_verified(_verify_fingerprint(client, school_manager_headers, student.school_id, _template()))
    _enroll_fingerprint(client, school_manager_headers, student)
    _assert_not_verified(_verify_fingerprint(client, school_manager_headers, student.school_id, _template()))


def test_fingerprint_verification_excludes_inactive_students(
    client, school_manager_headers, db_session, fingerprint_student_factory,
):
    student = fingerprint_student_factory()
    payload, _ = _enroll_fingerprint(client, school_manager_headers, student)
    student.is_active = False
    db_session.commit()
    _assert_not_verified(
        _verify_fingerprint(client, school_manager_headers, student.school_id, payload["template_data"])
    )

    # An inactive duplicate must not make a genuine active match ambiguous.
    active = fingerprint_student_factory()
    _enroll_fingerprint(client, school_manager_headers, active, template_data=payload["template_data"])
    response = _verify_fingerprint(client, school_manager_headers, active.school_id, payload["template_data"])
    assert response.status_code == 200
    assert response.json()["verified"] is True
    assert response.json()["student_id"] == active.id


def test_fingerprint_verification_requires_same_format_and_optional_finger(
    client, school_manager_headers, fingerprint_student_factory,
):
    student = fingerprint_student_factory()
    payload, _ = _enroll_fingerprint(
        client, school_manager_headers, student, finger_position="LEFT_THUMB",
    )
    for filters in ({"template_format": "ANSI_378"}, {"finger_position": "RIGHT_THUMB"}):
        _assert_not_verified(_verify_fingerprint(
            client, school_manager_headers, student.school_id, payload["template_data"], **filters,
        ))
    for filters in ({}, {"finger_position": "LEFT_THUMB", "template_format": "iso_19794_2"}):
        response = _verify_fingerprint(
            client, school_manager_headers, student.school_id, payload["template_data"], **filters,
        )
        assert response.status_code == 200
        assert response.json()["verified"] is True
        assert response.json()["student_id"] == student.id


def test_fingerprint_verification_normalizes_equivalent_base64(
    client, school_manager_headers, db_session, fingerprint_student_factory,
):
    student = fingerprint_student_factory()
    # Unused padding bits differ; both representations decode to the byte 'a'.
    _, body = _enroll_fingerprint(client, school_manager_headers, student, template_data="YR==")
    assert db_session.get(StudentBiometric, uuid.UUID(body["id"])).template_data == "YQ=="
    for probe in ("YQ==", "YR=="):
        response = _verify_fingerprint(client, school_manager_headers, student.school_id, probe)
        assert response.status_code == 200
        assert response.json()["verified"] is True
        assert response.json()["student_id"] == student.id


def test_fingerprint_verification_cannot_search_another_tenant(
    client, school_manager_headers, other_school_manager_headers, fingerprint_student_factory,
):
    own = fingerprint_student_factory()
    foreign = fingerprint_student_factory("NG")
    payload, _ = _enroll_fingerprint(client, other_school_manager_headers, foreign)

    # Knowing another school's template does not make it visible in one's own school.
    _assert_not_verified(_verify_fingerprint(
        client, school_manager_headers, own.school_id, payload["template_data"],
    ))
    for school_id in (foreign.school_id, 999999999):
        response = _verify_fingerprint(client, school_manager_headers, school_id, payload["template_data"])
        assert response.status_code == 403
        assert response.json() == {"detail": "Cannot verify biometrics for another school"}

    allowed = _verify_fingerprint(client, other_school_manager_headers, foreign.school_id, payload["template_data"])
    assert allowed.status_code == 200
    assert allowed.json()["verified"] is True
    assert allowed.json()["student_id"] == foreign.id


def test_fingerprint_identical_templates_in_different_tenants_are_isolated(
    client, school_manager_headers, other_school_manager_headers, fingerprint_student_factory,
):
    template = _template()
    students = [fingerprint_student_factory(), fingerprint_student_factory("NG")]
    headers = [school_manager_headers, other_school_manager_headers]
    for student, auth in zip(students, headers):
        _enroll_fingerprint(client, auth, student, template_data=template)
    for student, auth in zip(students, headers):
        response = _verify_fingerprint(client, auth, student.school_id, template)
        assert response.status_code == 200
        assert response.json()["verified"] is True
        assert response.json()["student_id"] == student.id


def test_fingerprint_ambiguous_matches_fail_closed(
    client, school_manager_headers, fingerprint_student_factory,
):
    students = [fingerprint_student_factory() for _ in range(2)]
    template = _template()
    for student in students:
        _enroll_fingerprint(client, school_manager_headers, student, template_data=template)
    response = _verify_fingerprint(client, school_manager_headers, students[0].school_id, template)
    _assert_not_verified(response)
    assert "uniquely" in response.json()["message"]


def test_fingerprint_multiple_enrollments_of_same_student_are_not_ambiguous(
    client, school_manager_headers, fingerprint_student_factory,
):
    student = fingerprint_student_factory()
    template = _template()
    records = [
        _enroll_fingerprint(client, school_manager_headers, student, template_data=template)[1]
        for _ in range(2)
    ]
    assert records[0]["id"] != records[1]["id"]
    response = _verify_fingerprint(client, school_manager_headers, student.school_id, template)
    assert response.status_code == 200
    assert response.json()["verified"] is True
    assert response.json()["student_id"] == student.id


@pytest.mark.parametrize("endpoint", ["enroll", "verify"])
def test_fingerprint_endpoints_require_authentication(client, endpoint):
    payload = {"template_data": _template(), "student_id" if endpoint == "enroll" else "school_id": 1}
    assert client.post(f"{FINGERPRINT_BASE}/{endpoint}", json=payload).status_code == 401


@pytest.mark.parametrize("role_headers", ["state_admin_headers", "inspector_headers"])
def test_state_roles_cannot_access_fingerprint_templates(client, request, role_headers):
    headers = request.getfixturevalue(role_headers)
    assert client.post(
        f"{FINGERPRINT_BASE}/enroll", headers=headers,
        json={"student_id": 1, "template_data": _template()},
    ).status_code == 403
    assert _verify_fingerprint(client, headers, 1, _template()).status_code == 403


def test_teacher_can_enroll_and_verify_within_own_school(client, teacher_headers, fingerprint_student_factory):
    student = fingerprint_student_factory()
    payload, _ = _enroll_fingerprint(client, teacher_headers, student)
    response = _verify_fingerprint(client, teacher_headers, student.school_id, payload["template_data"])
    assert response.status_code == 200
    assert response.json()["verified"] is True
    assert response.json()["student_id"] == student.id


@pytest.mark.parametrize("endpoint", ["enroll", "verify"])
@pytest.mark.parametrize("field, value", [
    ("template_data", ""),
    ("template_data", "not-base64!"),
    ("template_data", "YQ"),
    ("template_data", "éé=="),
    ("template_data", None),
    pytest.param("template_data", "A" * (MAX_TEMPLATE_LENGTH + 4), id="oversized-template"),
    ("template_format", "   "),
    ("template_format", "F" * 51),
    ("template_format", None),
    ("finger_position", "RIGHT_MIDDLE"),
])
def test_fingerprint_template_validation(client, school_manager_headers, endpoint, field, value):
    payload = {"template_data": _template(), "student_id" if endpoint == "enroll" else "school_id": 1}
    payload[field] = value
    response = client.post(f"{FINGERPRINT_BASE}/{endpoint}", headers=school_manager_headers, json=payload)
    assert response.status_code == 422
    assert any(field in error["loc"] for error in response.json()["detail"])


@pytest.mark.parametrize("field, value", [
    ("student_id", 0),
    ("student_id", 1.5),
    ("student_id", True),
    ("finger_position", None),
    ("quality_score", -1),
    ("quality_score", 101),
    ("quality_score", 2.5),
    ("quality_score", True),
    ("device_model", "D" * 101),
    ("school_id", 999999999),  # tenant cannot be supplied/overridden on enrollment
])
def test_fingerprint_enrollment_metadata_validation(client, school_manager_headers, field, value):
    payload = {"student_id": 1, "template_data": _template(), field: value}
    response = client.post(f"{FINGERPRINT_BASE}/enroll", headers=school_manager_headers, json=payload)
    assert response.status_code == 422
    assert any(field in error["loc"] for error in response.json()["detail"])


@pytest.mark.parametrize("school_id", [0, -1, True, 1.5])
def test_fingerprint_verification_requires_integer_school_id(client, school_manager_headers, school_id):
    response = _verify_fingerprint(client, school_manager_headers, school_id, _template())
    assert response.status_code == 422


@pytest.mark.parametrize("endpoint, required", [
    ("enroll", "student_id"), ("enroll", "template_data"),
    ("verify", "school_id"), ("verify", "template_data"),
])
def test_fingerprint_missing_required_fields(client, school_manager_headers, endpoint, required):
    payload = {"template_data": _template(), "student_id" if endpoint == "enroll" else "school_id": 1}
    del payload[required]
    response = client.post(f"{FINGERPRINT_BASE}/{endpoint}", headers=school_manager_headers, json=payload)
    assert response.status_code == 422
    assert any(required in error["loc"] for error in response.json()["detail"])


def test_fingerprint_model_registration_defaults_relationship_and_timestamps(db_session, fingerprint_student_factory):
    assert StudentBiometric in all_models
    assert Base.metadata.tables["student_biometrics"] is StudentBiometric.__table__
    assert StudentBiometric.__table__.c.created_at.type.timezone is True
    assert StudentBiometric.__table__.c.updated_at.type.timezone is True
    student = fingerprint_student_factory()
    row = StudentBiometric(
        template_data=_template(), updated_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
    )
    student.biometrics.append(row)
    db_session.commit()
    db_session.refresh(row)
    assert isinstance(row.id, uuid.UUID)
    assert row.student_id == student.id
    assert row.student is student
    assert row.finger_position is FingerPosition.RIGHT_INDEX
    assert row.template_format == "ISO_19794_2"
    created, updated = row.created_at, row.updated_at

    row.device_model = "Updated reader"
    db_session.commit()
    db_session.refresh(row)
    assert row.created_at == created
    assert row.updated_at > updated

    record_id = row.id
    student.biometrics.remove(row)
    db_session.commit()
    assert db_session.get(StudentBiometric, record_id) is None  # delete-orphan


def test_fingerprint_templates_cascade_on_orm_student_deletion(db_session, fingerprint_student_factory):
    student = fingerprint_student_factory()
    db_session.add_all([StudentBiometric(student=student, template_data=_template()) for _ in range(2)])
    db_session.commit()
    assert db_session.query(StudentBiometric).filter_by(student_id=student.id).count() == 2
    student_id = student.id
    db_session.delete(student)
    db_session.commit()
    assert db_session.query(StudentBiometric).filter_by(student_id=student_id).count() == 0
