"""Photo storage, teacher↔user binding and subject-level scoping.

Covers the ``add_photos_and_teacher_user_scoping`` feature set:

* ``photo_url`` on students and teachers (staff profile **and** login account,
  kept in sync), including validation of accepted URL shapes;
* provisioning a ``role="teacher"`` user account together with a staff profile,
  auto-linking (``POST /api/v1/teachers/me``) and manual linking
  (``link_user_id`` / ``POST /api/v1/teachers/{id}/link-user``);
* scoping: a teacher only sees — and may only modify — the subjects and
  classrooms assigned through ``Teacher.user_id == current_user.id``. Another
  teacher's subject in the same tenant is a **403**, another tenant's is a 404;
* ``POST /api/v1/media/upload`` and the ``/media/...`` serving route.
"""
import base64
import io
from types import SimpleNamespace

import pytest

from app.core.security import verify_password
from app.models.academic import Student, Subject, SchoolClass, TeachingAssignment
from app.models.auth import Teacher
from app.models.tenancy import PrivateSchool, User
from app.services.teacher_scope import TeacherScope

# A real 1x1 PNG: MediaService validates magic bytes, not the whole codec.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8AAAwAB/AF+p7RLAAAAAElFTkSuQmCC"
)
EXTERNAL_PHOTO = "https://cdn.ne-emis.so/portraits/ayaan.png"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def ilays(db_session):
    """The IL tenant with its manager and two teachers that teach disjoint subjects."""
    school = db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "IL").first()
    manager = (
        db_session.query(User)
        .filter(User.school_id == school.id, User.role == "school_manager")
        .first()
    )
    teachers = (
        db_session.query(User)
        .filter(User.school_id == school.id, User.role == "teacher")
        .order_by(User.id)
        .all()
    )
    return SimpleNamespace(school=school, manager=manager, teacher_a=teachers[0], teacher_b=teachers[1])


@pytest.fixture
def other_school(db_session):
    return db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "NG").first()


@pytest.fixture
def profile_of(db_session):
    def _get(user: User) -> Teacher:
        profile = db_session.query(Teacher).filter(Teacher.user_id == user.id).first()
        assert profile is not None, "demo seeding should bind every teacher account to a profile"
        return profile

    return _get


@pytest.fixture
def subjects_of(db_session):
    """Subject ids a teacher account is scoped to (assignments ∪ profile mappings)."""
    def _get(user: User):
        return TeacherScope.assigned_subject_ids(db_session, user)

    return _get


@pytest.fixture
def foreign_subject(db_session, ilays, subjects_of):
    """A subject taught by teacher B but not by teacher A."""
    exclusive = sorted(subjects_of(ilays.teacher_b) - subjects_of(ilays.teacher_a))
    assert exclusive, "expected the two demo teachers to own different subjects"
    return db_session.query(Subject).filter(Subject.id == exclusive[0]).first()


@pytest.fixture
def foreign_classroom(db_session, ilays):
    """A classroom taught **only** by teacher B (with two students on roll).

    The demo seed gives every teacher the full set of classrooms (each subject
    is taught at every level), so an exclusive classroom has to be created to
    exercise the scoping rules. Reused across tests in this module.
    """
    existing = (
        db_session.query(SchoolClass)
        .filter(
            SchoolClass.school_id == ilays.school.id,
            SchoolClass.class_level == 9,
            SchoolClass.stream == "F",
        )
        .first()
    )
    if existing is not None:
        return existing

    school_class = SchoolClass(school_id=ilays.school.id, class_level=9, stream="F")
    db_session.add(school_class)
    db_session.flush()

    subject = (
        db_session.query(Subject)
        .filter(Subject.school_id == ilays.school.id, Subject.level == 9)
        .order_by(Subject.id)
        .first()
    )
    db_session.add(
        TeachingAssignment(
            school_id=ilays.school.id,
            teacher_id=ilays.teacher_b.id,
            class_id=school_class.id,
            subject_id=subject.id,
        )
    )
    for index, (first_name, gender) in enumerate((("Ubax", "Female"), ("Khadar", "Male")), start=1):
        roll = f"{ilays.school.school_code}-90{index}01"
        db_session.add(
            Student(
                school_id=ilays.school.id,
                national_student_id=roll,
                roll_number=roll,
                first_name=first_name,
                last_name="Scoped",
                gender=gender,
                class_id=school_class.id,
                is_active=True,
            )
        )
    db_session.commit()
    db_session.refresh(school_class)
    return school_class


# ---------------------------------------------------------------------------
# 1. Photo storage — students
# ---------------------------------------------------------------------------
def test_student_photo_url_accepted_on_create(client, school_manager_headers, db_session):
    response = client.post(
        "/api/v1/school/students",
        headers=school_manager_headers,
        json={
            "first_name": "Sagal",
            "last_name": "Photo",
            "gender": "Female",
            "class_id": 1,
            "photo_url": EXTERNAL_PHOTO,
        },
    )
    assert response.status_code == 201
    assert response.json()["photo_url"] == EXTERNAL_PHOTO

    stored = (
        db_session.query(Student)
        .filter(Student.roll_number == response.json()["roll_number"])
        .first()
    )
    assert stored.photo_url == EXTERNAL_PHOTO


def test_student_photo_url_update_and_clear(client, school_manager_headers, db_session):
    student = db_session.query(Student).filter(Student.school_id == 1).first()
    roll = student.roll_number

    updated = client.patch(
        f"/api/v1/school/students/{roll}",
        headers=school_manager_headers,
        json={"photo_url": "/media/uploads/portrait.jpg"},
    )
    assert updated.status_code == 200
    assert updated.json()["photo_url"] == "/media/uploads/portrait.jpg"

    cleared = client.patch(
        f"/api/v1/school/students/{roll}", headers=school_manager_headers, json={"photo_url": None}
    )
    assert cleared.status_code == 200
    assert cleared.json()["photo_url"] is None
    db_session.refresh(student)
    assert student.photo_url is None


def test_student_photo_url_rejects_unsupported_shapes(client, school_manager_headers, db_session):
    student = db_session.query(Student).filter(Student.school_id == 1).first()

    for bad_value in (
        "ftp://cdn.example.com/a.jpg",          # scheme not allowed
        "//cdn.example.com/a.jpg",              # protocol-relative
        "data:image/png;base64,iVBORw0KGgo=",   # inline bytes
        "/media/../../etc/passwd",              # traversal
        "https://cdn.example.com/" + "a" * 600, # longer than the 500-char column
    ):
        response = client.patch(
            f"/api/v1/school/students/{student.roll_number}",
            headers=school_manager_headers,
            json={"photo_url": bad_value},
        )
        assert response.status_code == 422, bad_value


def test_classroom_roster_exposes_student_photo_url(client, school_manager_headers, db_session):
    student = db_session.query(Student).filter(Student.school_id == 1, Student.class_id.isnot(None)).first()
    student.photo_url = EXTERNAL_PHOTO
    db_session.commit()

    response = client.get(f"/api/v1/classrooms/{student.class_id}/students", headers=school_manager_headers)
    assert response.status_code == 200
    roster = {row["id"]: row for row in response.json()}
    assert roster[student.id]["photo_url"] == EXTERNAL_PHOTO


# ---------------------------------------------------------------------------
# 2. Photo storage — teachers (account + profile stay in sync)
# ---------------------------------------------------------------------------
def test_teacher_account_photo_update_mirrors_staff_profile(
    client, school_manager_headers, db_session, ilays, profile_of
):
    teacher = ilays.teacher_a
    response = client.put(
        f"/api/v1/school/teachers/{teacher.id}",
        headers=school_manager_headers,
        json={"photo_url": EXTERNAL_PHOTO},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["photo_url"] == EXTERNAL_PHOTO
    assert payload["user_id"] == teacher.id
    assert payload["teacher_profile_id"] == profile_of(teacher).id

    db_session.refresh(teacher)
    db_session.refresh(profile_of(teacher))
    assert teacher.photo_url == EXTERNAL_PHOTO
    assert profile_of(teacher).photo_url == EXTERNAL_PHOTO


def test_teacher_profile_photo_update_mirrors_account(
    client, school_manager_headers, db_session, ilays, profile_of
):
    profile = profile_of(ilays.teacher_b)
    response = client.patch(
        f"/api/v1/teachers/{profile.id}",
        headers=school_manager_headers,
        json={"photo_url": "/media/uploads/mohamed.png"},
    )
    assert response.status_code == 200
    assert response.json()["photo_url"] == "/media/uploads/mohamed.png"
    assert response.json()["user_id"] == ilays.teacher_b.id

    db_session.refresh(profile)
    db_session.refresh(ilays.teacher_b)
    assert profile.photo_url == "/media/uploads/mohamed.png"
    assert ilays.teacher_b.photo_url == "/media/uploads/mohamed.png"


def test_teacher_can_update_own_photo_but_not_own_identity(
    client, db_session, ilays, auth_headers, profile_of
):
    headers = auth_headers(ilays.teacher_a)
    profile = profile_of(ilays.teacher_a)

    allowed = client.patch(
        f"/api/v1/teachers/{profile.id}", headers=headers, json={"photo_url": EXTERNAL_PHOTO}
    )
    assert allowed.status_code == 200
    assert allowed.json()["photo_url"] == EXTERNAL_PHOTO

    forbidden = client.patch(
        f"/api/v1/teachers/{profile.id}", headers=headers, json={"first_name": "Impostor"}
    )
    assert forbidden.status_code == 403
    assert "school manager" in forbidden.json()["detail"]


def test_teacher_cannot_touch_another_teachers_profile(client, db_session, ilays, auth_headers, profile_of):
    headers = auth_headers(ilays.teacher_a)
    other_profile = profile_of(ilays.teacher_b)

    assert client.get(f"/api/v1/teachers/{other_profile.id}", headers=headers).status_code == 403
    patched = client.patch(
        f"/api/v1/teachers/{other_profile.id}", headers=headers, json={"photo_url": EXTERNAL_PHOTO}
    )
    assert patched.status_code == 403


def test_teacher_account_update_rejects_manager_only_fields(client, db_session, ilays, auth_headers):
    headers = auth_headers(ilays.teacher_a)
    response = client.put(
        f"/api/v1/school/teachers/{ilays.teacher_a.id}", headers=headers, json={"is_active": False}
    )
    assert response.status_code == 403
    assert "school manager" in response.json()["detail"]


def test_teacher_profile_list_is_self_only(client, db_session, ilays, auth_headers, profile_of):
    response = client.get("/api/v1/teachers", headers=auth_headers(ilays.teacher_a))
    assert response.status_code == 200
    profiles = response.json()
    assert [row["id"] for row in profiles] == [profile_of(ilays.teacher_a).id]

    manager_view = client.get("/api/v1/teachers", headers=auth_headers(ilays.manager))
    assert manager_view.status_code == 200
    assert len(manager_view.json()) >= 2


# ---------------------------------------------------------------------------
# 3. Teacher ↔ user binding
# ---------------------------------------------------------------------------
def test_demo_seeding_binds_teacher_accounts_to_profiles(client, db_session, ilays, subjects_of):
    for teacher in (ilays.teacher_a, ilays.teacher_b):
        profile = db_session.query(Teacher).filter(Teacher.user_id == teacher.id).first()
        assert profile is not None
        assert profile.school_id == ilays.school.id
        assert profile.email == teacher.email
        assert subjects_of(teacher), "seeded teachers should own at least one subject"


def test_create_teacher_auto_provisions_user_account(client, db_session, ilays, auth_headers):
    response = client.post(
        "/api/v1/teachers",
        headers=auth_headers(ilays.manager),
        json={
            "first_name": "Naima",
            "last_name": "Warsame",
            "email": "naima.warsame@ilays.edu.so",
            "password": "Teach@2026x",
            "designation": "Senior Teacher (GEO)",
            "qualifications": "B.Ed Geography, University of Hargeisa",
            "photo_url": EXTERNAL_PHOTO,
        },
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["user_id"] is not None
    assert profile["email"] == "naima.warsame@ilays.edu.so"
    assert profile["photo_url"] == EXTERNAL_PHOTO
    assert profile["staff_identifier"].startswith("NE-TID-")

    account = db_session.query(User).filter(User.id == profile["user_id"]).first()
    assert account is not None
    assert account.role == "teacher"
    assert account.school_id == ilays.school.id
    assert account.photo_url == EXTERNAL_PHOTO
    assert verify_password("Teach@2026x", account.password_hash)

    # The provisioned account can log in immediately.
    login = client.post(
        "/api/auth/login", json={"email": "naima.warsame@ilays.edu.so", "password": "Teach@2026x"}
    )
    assert login.status_code == 200
    assert login.json()["user"]["role"] == "teacher"


def test_create_teacher_with_explicit_user_block(client, db_session, ilays, auth_headers):
    response = client.post(
        "/api/v1/teachers",
        headers=auth_headers(ilays.manager),
        json={
            "first_name": "Guled",
            "last_name": "Egal",
            "user": {
                "email": "guled.egal@ilays.edu.so",
                "password": "Teach@2026x",
                "role": "teacher",
                "first_name": "Guled",
                "last_name": "Egal",
            },
        },
    )
    assert response.status_code == 201
    assert response.json()["user_id"] is not None
    assert response.json()["first_name"] == "Guled"


def test_auto_provisioning_requires_credentials(client, db_session, ilays, auth_headers):
    response = client.post(
        "/api/v1/teachers",
        headers=auth_headers(ilays.manager),
        json={"first_name": "NoAccount", "last_name": "NoPassword"},
    )
    assert response.status_code == 422


def test_auto_provisioning_rejects_non_teacher_role(client, db_session, ilays, auth_headers):
    response = client.post(
        "/api/v1/teachers",
        headers=auth_headers(ilays.manager),
        json={
            "first_name": "Escalate",
            "last_name": "Privileges",
            "user": {
                "email": "escalated@ilays.edu.so",
                "password": "Teach@2026x",
                "role": "school_manager",
            },
        },
    )
    assert response.status_code == 422


def test_profile_can_exist_without_an_account(client, db_session, ilays, auth_headers):
    response = client.post(
        "/api/v1/teachers",
        headers=auth_headers(ilays.manager),
        json={
            "first_name": "Prehire",
            "last_name": "Pending",
            "email": "pending@ilays.edu.so",
            "auto_provision_user": False,
        },
    )
    assert response.status_code == 201
    assert response.json()["user_id"] is None
    assert response.json()["account"] is None


def test_link_existing_account_at_creation(client, db_session, ilays, auth_headers):
    account = db_session.query(User).filter(User.email == "naima.warsame@ilays.edu.so").first()
    assert account is not None, "expected the auto-provisioned account from the previous test"

    # The account is already bound, so binding it again must be refused.
    conflict = client.post(
        "/api/v1/teachers",
        headers=auth_headers(ilays.manager),
        json={
            "first_name": "Naima",
            "last_name": "Warsame",
            "link_user_id": account.id,
            "auto_provision_user": False,
        },
    )
    assert conflict.status_code == 409


def test_link_user_endpoint_binds_unlinked_profile(client, db_session, ilays, auth_headers):
    # A fresh account with no profile yet.
    from app.services.teacher_service import TeacherService

    account = TeacherService.provision_account(
        db_session,
        school_id=ilays.school.id,
        email="hodan.link@ilays.edu.so",
        password="Teach@2026x",
        first_name="Hodan",
        last_name="Link",
    )
    profile = db_session.query(Teacher).filter(Teacher.email == "pending@ilays.edu.so").first()
    assert profile is not None and profile.user_id is None

    db_session.commit()
    response = client.post(
        f"/api/v1/teachers/{profile.id}/link-user",
        headers=auth_headers(ilays.manager),
        json={"user_id": account.id},
    )
    assert response.status_code == 200
    assert response.json()["user_id"] == account.id
    assert response.json()["account"]["email"] == account.email

    db_session.refresh(profile)
    assert profile.user_id == account.id


def test_link_user_rejects_manager_accounts_and_double_binding(
    client, db_session, ilays, other_school, auth_headers
):
    created = client.post(
        "/api/v1/teachers",
        headers=auth_headers(ilays.manager),
        json={
            "first_name": "Unbound",
            "last_name": "Profile",
            "email": "unbound@ilays.edu.so",
            "auto_provision_user": False,
        },
    )
    assert created.status_code == 201
    profile_id = created.json()["id"]

    # A school_manager account cannot be bound to a teaching profile.
    refused = client.post(
        f"/api/v1/teachers/{profile_id}/link-user",
        headers=auth_headers(ilays.manager),
        json={"user_id": ilays.manager.id},
    )
    assert refused.status_code == 409
    assert "only teacher accounts" in refused.json()["detail"]

    # An account already bound to another profile cannot be reused.
    taken = client.post(
        f"/api/v1/teachers/{profile_id}/link-user",
        headers=auth_headers(ilays.manager),
        json={"user_id": ilays.teacher_b.id},
    )
    assert taken.status_code == 409
    assert "already bound" in taken.json()["detail"]

    # Accounts of another tenant are not linkable (404, not 403).
    foreign_teacher = (
        db_session.query(User)
        .filter(User.school_id == other_school.id, User.role == "teacher")
        .first()
    )
    foreign = client.post(
        f"/api/v1/teachers/{profile_id}/link-user",
        headers=auth_headers(ilays.manager),
        json={"user_id": foreign_teacher.id},
    )
    assert foreign.status_code == 404


def test_me_endpoint_auto_links_profile_for_teacher_account(client, db_session, ilays, auth_headers):
    from app.services.teacher_service import TeacherService

    account = TeacherService.provision_account(
        db_session,
        school_id=ilays.school.id,
        email="auto.link@ilays.edu.so",
        password="Teach@2026x",
        first_name="Auto",
        last_name="Link",
    )
    db_session.commit()
    headers = auth_headers(account)

    missing = client.get("/api/v1/teachers/me", headers=headers)
    assert missing.status_code == 404

    created = client.post("/api/v1/teachers/me", headers=headers)
    assert created.status_code == 200
    assert created.json()["user_id"] == account.id
    assert created.json()["email"] == account.email

    # Idempotent: a second call returns the same profile.
    again = client.post("/api/v1/teachers/me", headers=headers)
    assert again.json()["id"] == created.json()["id"]
    assert client.get("/api/v1/teachers/me", headers=headers).status_code == 200


def test_profile_binding_survives_account_deletion(db_session, ilays):
    """``teachers.user_id`` is ON DELETE SET NULL, not CASCADE."""
    from app.services.teacher_service import TeacherService

    account = TeacherService.provision_account(
        db_session,
        school_id=ilays.school.id,
        email="leaver@ilays.edu.so",
        password="Teach@2026x",
        first_name="Leaving",
        last_name="Teacher",
        photo_url=EXTERNAL_PHOTO,
    )
    profile = TeacherService.ensure_profile_for_user(db_session, account)
    db_session.commit()
    profile_id = profile.id

    db_session.delete(account)
    db_session.commit()

    surviving = db_session.query(Teacher).filter(Teacher.id == profile_id).first()
    assert surviving is not None
    assert surviving.user_id is None
    assert surviving.photo_url == EXTERNAL_PHOTO


def test_manager_updates_profile_subject_assignments(client, db_session, ilays, auth_headers, subjects_of):
    # A brand-new subject nobody teaches yet.
    created = client.post(
        "/api/v1/subjects",
        headers=auth_headers(ilays.manager),
        json={"code": "AST-07", "name": "Astronomy", "level": 7},
    )
    assert created.status_code == 201
    subject_id = created.json()["id"]

    profile = db_session.query(Teacher).filter(Teacher.user_id == ilays.teacher_a.id).first()
    before = subjects_of(ilays.teacher_a)
    assert subject_id not in before
    teacher_headers = auth_headers(ilays.teacher_a)
    assert subject_id not in {row["id"] for row in client.get("/api/v1/subjects", headers=teacher_headers).json()}

    response = client.put(
        f"/api/v1/teachers/{profile.id}/subjects",
        headers=auth_headers(ilays.manager),
        json={"subject_ids": sorted(before | {subject_id}), "primary_subject_id": subject_id},
    )
    assert response.status_code == 200
    assert subject_id in response.json()["subject_ids"]
    primary = [row for row in response.json()["assigned_subjects"] if row["id"] == subject_id]
    assert primary and primary[0]["is_primary"] is True

    # The teacher is scoped to the new subject immediately.
    listing = client.get("/api/v1/subjects", headers=teacher_headers)
    assert subject_id in {row["id"] for row in listing.json()}
    assert {row["id"] for row in listing.json()} == subjects_of(ilays.teacher_a)

    # Reject subjects from another tenant.
    foreign = db_session.query(Subject).filter(Subject.school_id != ilays.school.id).first()
    rejected = client.put(
        f"/api/v1/teachers/{profile.id}/subjects",
        headers=auth_headers(ilays.manager),
        json={"subject_ids": [foreign.id]},
    )
    assert rejected.status_code == 400

    # Restore the demo mapping so the remaining tests see the seeded scope.
    restore = client.put(
        f"/api/v1/teachers/{profile.id}/subjects",
        headers=auth_headers(ilays.manager),
        json={"subject_ids": sorted(before)},
    )
    assert restore.status_code == 200
    assert set(subjects_of(ilays.teacher_a)) == before


def test_teacher_cannot_edit_own_subject_roster(client, db_session, ilays, auth_headers, profile_of):
    profile = profile_of(ilays.teacher_a)
    response = client.put(
        f"/api/v1/teachers/{profile.id}/subjects",
        headers=auth_headers(ilays.teacher_a),
        json={"subject_ids": []},
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4. Subject scoping
# ---------------------------------------------------------------------------
def test_teacher_subject_list_is_scoped_to_assignments(
    client, db_session, ilays, auth_headers, subjects_of
):
    response = client.get("/api/v1/subjects", headers=auth_headers(ilays.teacher_a))
    assert response.status_code == 200
    visible = {row["id"] for row in response.json()}
    assert visible == subjects_of(ilays.teacher_a)
    assert visible, "a seeded teacher should own subjects"
    assert all(row["school_id"] == ilays.school.id for row in response.json())


def test_manager_subject_list_is_tenant_wide(client, db_session, ilays, auth_headers, subjects_of):
    manager_view = client.get("/api/v1/subjects", headers=auth_headers(ilays.manager))
    teacher_view = client.get("/api/v1/subjects", headers=auth_headers(ilays.teacher_a))
    assert manager_view.status_code == 200
    manager_ids = {row["id"] for row in manager_view.json()}
    teacher_ids = {row["id"] for row in teacher_view.json()}
    assert teacher_ids < manager_ids


def test_teacher_cannot_read_subject_assigned_to_another_teacher(
    client, db_session, ilays, auth_headers, foreign_subject
):
    response = client.get(f"/api/v1/subjects/{foreign_subject.id}", headers=auth_headers(ilays.teacher_a))
    assert response.status_code == 403
    assert "assigned to them" in response.json()["detail"]


def test_teacher_cannot_modify_subject_assigned_to_another_teacher(
    client, db_session, ilays, auth_headers, foreign_subject
):
    response = client.patch(
        f"/api/v1/subjects/{foreign_subject.id}",
        headers=auth_headers(ilays.teacher_a),
        json={"name": "Hijacked Mathematics"},
    )
    assert response.status_code == 403

    db_session.refresh(foreign_subject)
    assert foreign_subject.name != "Hijacked Mathematics"


def test_teacher_can_modify_own_subject(client, db_session, ilays, auth_headers, subjects_of):
    own_subject_id = sorted(subjects_of(ilays.teacher_a))[0]
    response = client.patch(
        f"/api/v1/subjects/{own_subject_id}",
        headers=auth_headers(ilays.teacher_a),
        json={"name": "Somali (Af-Somali) — updated"},
    )
    assert response.status_code == 200
    assert response.json()["name"].endswith("updated")

    # Roster changes stay manager-only even for an owned subject.
    roster = client.patch(
        f"/api/v1/subjects/{own_subject_id}",
        headers=auth_headers(ilays.teacher_a),
        json={"teacher_ids": []},
    )
    assert roster.status_code == 403


def test_teacher_cannot_create_or_delete_subjects(client, db_session, ilays, auth_headers, subjects_of):
    created = client.post(
        "/api/v1/subjects",
        headers=auth_headers(ilays.teacher_a),
        json={"code": "SMUGGLE-01", "name": "Smuggled", "level": 1},
    )
    assert created.status_code == 403

    own_subject_id = sorted(subjects_of(ilays.teacher_a))[0]
    deleted = client.delete(f"/api/v1/subjects/{own_subject_id}", headers=auth_headers(ilays.teacher_a))
    assert deleted.status_code == 403
    assert db_session.query(Subject).filter(Subject.id == own_subject_id).first() is not None


def test_manager_creates_subject_and_assigns_teachers(client, db_session, ilays, auth_headers, profile_of):
    created = client.post(
        "/api/v1/subjects",
        headers=auth_headers(ilays.manager),
        json={"code": "COD-05", "name": "Coding", "level": 5},
    )
    assert created.status_code == 201
    subject_id = created.json()["id"]
    assert created.json()["teacher_ids"] == []

    profile_a = profile_of(ilays.teacher_a)
    assigned = client.post(
        f"/api/v1/subjects/{subject_id}/teachers",
        headers=auth_headers(ilays.manager),
        json={"teacher_id": profile_a.id, "is_primary": True},
    )
    assert assigned.status_code == 201
    assert assigned.json()["teacher_ids"] == [profile_a.id]
    assert assigned.json()["assigned_teachers"][0]["full_name"] == profile_a.full_name
    assert assigned.json()["assigned_teachers"][0]["is_primary"] is True

    # The subject is now inside teacher A's scope — and still outside B's.
    assert subject_id in {row["id"] for row in client.get("/api/v1/subjects", headers=auth_headers(ilays.teacher_a)).json()}
    assert subject_id not in {row["id"] for row in client.get("/api/v1/subjects", headers=auth_headers(ilays.teacher_b)).json()}
    assert client.get(f"/api/v1/subjects/{subject_id}", headers=auth_headers(ilays.teacher_b)).status_code == 403

    # Teachers may not manage the roster themselves.
    forbidden = client.post(
        f"/api/v1/subjects/{subject_id}/teachers",
        headers=auth_headers(ilays.teacher_a),
        json={"teacher_id": profile_of(ilays.teacher_b).id},
    )
    assert forbidden.status_code == 403

    removed = client.delete(
        f"/api/v1/subjects/{subject_id}/teachers/{profile_a.id}", headers=auth_headers(ilays.manager)
    )
    assert removed.status_code == 200
    assert removed.json()["teacher_ids"] == []


def test_subject_not_found_across_tenants(client, db_session, ilays, other_school, auth_headers):
    foreign = db_session.query(Subject).filter(Subject.school_id == other_school.id).first()
    response = client.get(f"/api/v1/subjects/{foreign.id}", headers=auth_headers(ilays.teacher_a))
    assert response.status_code == 404


def test_state_roles_are_rejected_by_subject_and_classroom_routers(client, state_admin_headers, inspector_headers):
    for headers in (state_admin_headers, inspector_headers):
        assert client.get("/api/v1/subjects", headers=headers).status_code == 403
        assert client.get("/api/v1/classrooms", headers=headers).status_code == 403
        assert client.get("/api/v1/teachers", headers=headers).status_code == 403


def test_legacy_subject_listing_is_scoped_for_teachers(client, db_session, ilays, auth_headers, subjects_of):
    response = client.get("/api/v1/school/subjects", headers=auth_headers(ilays.teacher_a))
    assert response.status_code == 200
    assert {row["id"] for row in response.json()} == subjects_of(ilays.teacher_a)

    manager_ids = {
        row["id"]
        for row in client.get("/api/v1/school/subjects", headers=auth_headers(ilays.manager)).json()
    }
    assert subjects_of(ilays.teacher_a) < manager_ids


# ---------------------------------------------------------------------------
# 5. Classroom scoping
# ---------------------------------------------------------------------------
def test_teacher_classroom_list_is_scoped_to_assignments(client, db_session, ilays, auth_headers):
    response = client.get("/api/v1/classrooms", headers=auth_headers(ilays.teacher_a))
    assert response.status_code == 200
    visible = {row["id"] for row in response.json()}
    assert visible == TeacherScope.assigned_class_ids(db_session, ilays.teacher_a)
    assert all(row["school_id"] == ilays.school.id for row in response.json())
    assert all("student_count" in row and row["label"].startswith("Class ") for row in response.json())


def test_manager_classroom_list_is_tenant_wide(client, db_session, ilays, auth_headers, foreign_classroom):
    manager_ids = {row["id"] for row in client.get("/api/v1/classrooms", headers=auth_headers(ilays.manager)).json()}
    teacher_a_ids = {row["id"] for row in client.get("/api/v1/classrooms", headers=auth_headers(ilays.teacher_a)).json()}
    teacher_b_ids = {row["id"] for row in client.get("/api/v1/classrooms", headers=auth_headers(ilays.teacher_b)).json()}

    # The demo seed assigns every classroom to every subject teacher, so the
    # distinguishing case is the classroom that only teacher B teaches.
    assert teacher_a_ids <= manager_ids and teacher_b_ids <= manager_ids
    assert foreign_classroom.id in manager_ids
    assert foreign_classroom.id in teacher_b_ids
    assert foreign_classroom.id not in teacher_a_ids


def test_teacher_cannot_read_classroom_taught_by_another_teacher(
    client, db_session, ilays, auth_headers, foreign_classroom
):
    detail = client.get(f"/api/v1/classrooms/{foreign_classroom.id}", headers=auth_headers(ilays.teacher_a))
    assert detail.status_code == 403
    roster = client.get(
        f"/api/v1/classrooms/{foreign_classroom.id}/students", headers=auth_headers(ilays.teacher_a)
    )
    assert roster.status_code == 403
    subjects = client.get(
        f"/api/v1/classrooms/{foreign_classroom.id}/subjects", headers=auth_headers(ilays.teacher_a)
    )
    assert subjects.status_code == 403


def test_teacher_classroom_subjects_are_scoped(client, db_session, ilays, auth_headers, subjects_of):
    own_class_id = sorted(TeacherScope.assigned_class_ids(db_session, ilays.teacher_a))[0]
    response = client.get(f"/api/v1/classrooms/{own_class_id}/subjects", headers=auth_headers(ilays.teacher_a))
    assert response.status_code == 200
    assert {row["id"] for row in response.json()} <= subjects_of(ilays.teacher_a)

    manager_response = client.get(
        f"/api/v1/classrooms/{own_class_id}/subjects", headers=auth_headers(ilays.manager)
    )
    assert len(manager_response.json()) >= len(response.json())


def test_teacher_cannot_write_classrooms(client, db_session, ilays, auth_headers, foreign_classroom):
    created = client.post(
        "/api/v1/classrooms",
        headers=auth_headers(ilays.teacher_a),
        json={"class_level": 9, "stream": "Z"},
    )
    assert created.status_code == 403

    own_class_id = sorted(TeacherScope.assigned_class_ids(db_session, ilays.teacher_a))[0]
    patched = client.patch(
        f"/api/v1/classrooms/{own_class_id}", headers=auth_headers(ilays.teacher_a), json={"stream": "Q"}
    )
    assert patched.status_code == 403

    deleted = client.delete(f"/api/v1/classrooms/{foreign_classroom.id}", headers=auth_headers(ilays.teacher_a))
    assert deleted.status_code == 403


def test_manager_classroom_crud_round_trip(client, db_session, ilays, auth_headers):
    created = client.post(
        "/api/v1/classrooms",
        headers=auth_headers(ilays.manager),
        json={"class_level": 11, "stream": "Q"},
    )
    assert created.status_code == 201
    class_id = created.json()["id"]
    assert created.json()["label"] == "Class 11Q"
    assert created.json()["student_count"] == 0

    duplicate = client.post(
        "/api/v1/classrooms", headers=auth_headers(ilays.manager), json={"class_level": 11, "stream": "Q"}
    )
    assert duplicate.status_code == 409

    patched = client.patch(
        f"/api/v1/classrooms/{class_id}", headers=auth_headers(ilays.manager), json={"stream": "R"}
    )
    assert patched.status_code == 200
    assert patched.json()["label"] == "Class 11R"

    deleted = client.delete(f"/api/v1/classrooms/{class_id}", headers=auth_headers(ilays.manager))
    assert deleted.status_code == 200
    assert db_session.query(SchoolClass).filter(SchoolClass.id == class_id).first() is None


def test_classroom_with_students_cannot_be_deleted(client, db_session, ilays, auth_headers):
    occupied = (
        db_session.query(SchoolClass)
        .join(Student, Student.class_id == SchoolClass.id)
        .filter(SchoolClass.school_id == ilays.school.id, Student.is_active.is_(True))
        .first()
    )
    response = client.delete(f"/api/v1/classrooms/{occupied.id}", headers=auth_headers(ilays.manager))
    assert response.status_code == 409


def test_legacy_class_listing_is_scoped_for_teachers(client, db_session, ilays, auth_headers):
    response = client.get("/api/v1/school/classes", headers=auth_headers(ilays.teacher_a))
    assert response.status_code == 200
    assert {row["id"] for row in response.json()} == TeacherScope.assigned_class_ids(
        db_session, ilays.teacher_a
    )


def test_classroom_not_found_across_tenants(client, db_session, ilays, other_school, auth_headers):
    foreign = db_session.query(SchoolClass).filter(SchoolClass.school_id == other_school.id).first()
    assert client.get(f"/api/v1/classrooms/{foreign.id}", headers=auth_headers(ilays.teacher_a)).status_code == 404


# ---------------------------------------------------------------------------
# 6. Scoping still governs grade entry (existing RBAC stays intact)
# ---------------------------------------------------------------------------
def test_teacher_cannot_enter_grades_for_another_teachers_subject(
    client, db_session, ilays, auth_headers, foreign_classroom
):
    assignment = (
        db_session.query(TeachingAssignment)
        .filter(
            TeachingAssignment.class_id == foreign_classroom.id,
            TeachingAssignment.teacher_id == ilays.teacher_b.id,
        )
        .first()
    )
    assert assignment is not None
    student = (
        db_session.query(Student)
        .filter(Student.class_id == foreign_classroom.id, Student.school_id == ilays.school.id)
        .first()
    )
    assert student is not None

    response = client.post(
        "/api/v1/school/grades",
        headers=auth_headers(ilays.teacher_a),
        json={
            "subject_id": assignment.subject_id,
            "class_id": foreign_classroom.id,
            "term": "Term 1",
            "grades": [{"student_id": student.id, "score": 91.0}],
        },
    )
    assert response.status_code == 403
    assert "Not authorized to enter grades" in response.json()["detail"]


def test_teacher_can_enter_grades_for_own_subject(client, db_session, ilays, auth_headers):
    assignment = (
        db_session.query(TeachingAssignment)
        .filter(
            TeachingAssignment.teacher_id == ilays.teacher_a.id,
            TeachingAssignment.school_id == ilays.school.id,
        )
        .first()
    )
    student = (
        db_session.query(Student)
        .filter(Student.class_id == assignment.class_id, Student.school_id == ilays.school.id)
        .first()
    )

    response = client.post(
        "/api/v1/school/grades",
        headers=auth_headers(ilays.teacher_a),
        json={
            "subject_id": assignment.subject_id,
            "class_id": assignment.class_id,
            "term": "Term 1",
            "grades": [{"student_id": student.id, "score": 78.0}],
        },
    )
    assert response.status_code == 200


# ---------------------------------------------------------------------------
# 7. Media upload helper
# ---------------------------------------------------------------------------
def test_media_upload_returns_usable_photo_url(client, db_session, ilays, auth_headers):
    response = client.post(
        "/api/v1/media/upload",
        headers=auth_headers(ilays.manager),
        files={"file": ("ayaan.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["content_type"] == "image/png"
    assert payload["size_bytes"] == len(TINY_PNG)
    assert payload["url"] == payload["photo_url"]
    assert payload["url"].startswith("/media/uploads/")
    assert payload["filename"].endswith(".png")

    served = client.get(payload["url"])
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == TINY_PNG

    # The returned URL is accepted by the student/teacher photo fields.
    attached = client.patch(
        f"/api/v1/teachers/{db_session.query(Teacher).filter(Teacher.user_id == ilays.teacher_a.id).first().id}",
        headers=auth_headers(ilays.manager),
        json={"photo_url": payload["photo_url"]},
    )
    assert attached.status_code == 200
    assert attached.json()["photo_url"] == payload["photo_url"]


def test_media_upload_by_teacher_is_allowed(client, db_session, ilays, auth_headers):
    response = client.post(
        "/api/v1/media/upload",
        headers=auth_headers(ilays.teacher_a),
        files={"file": ("selfie.jpg", io.BytesIO(b"\xff\xd8\xff\xe0" + b"\x00" * 32), "image/jpeg")},
    )
    assert response.status_code == 201
    assert response.json()["content_type"] == "image/jpeg"
    assert response.json()["filename"].endswith(".jpg")


def test_media_upload_rejects_non_images_and_empty_files(client, db_session, ilays, auth_headers):
    not_an_image = client.post(
        "/api/v1/media/upload",
        headers=auth_headers(ilays.manager),
        files={"file": ("notes.txt", io.BytesIO(b"plain text, not a portrait"), "text/plain")},
    )
    assert not_an_image.status_code == 415
    assert "Unsupported image type" in not_an_image.json()["detail"]

    empty = client.post(
        "/api/v1/media/upload",
        headers=auth_headers(ilays.manager),
        files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
    )
    assert empty.status_code == 400


def test_media_upload_enforces_size_limit(client, db_session, ilays, auth_headers, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_MB", 1)
    oversized = b"\x89PNG\r\n\x1a\n" + b"\x00" * (2 * 1024 * 1024)
    response = client.post(
        "/api/v1/media/upload",
        headers=auth_headers(ilays.manager),
        files={"file": ("huge.png", io.BytesIO(oversized), "image/png")},
    )
    assert response.status_code == 413
    assert "1 MB limit" in response.json()["detail"]


def test_media_upload_requires_school_tenant(client, state_admin_headers):
    anonymous = client.post(
        "/api/v1/media/upload", files={"file": ("x.png", io.BytesIO(TINY_PNG), "image/png")}
    )
    assert anonymous.status_code == 401

    state_role = client.post(
        "/api/v1/media/upload",
        headers=state_admin_headers,
        files={"file": ("x.png", io.BytesIO(TINY_PNG), "image/png")},
    )
    assert state_role.status_code == 403


def test_media_serving_rejects_traversal_and_missing_files(client, db_session, ilays, auth_headers):
    for path in (
        "/media/uploads/..%2f..%2fapp%2fcore%2fconfig.py",
        "/media/..%2f..%2falembic.ini",
        "/media/uploads/does-not-exist.png",
    ):
        assert client.get(path).status_code == 404, path


def test_accepted_upload_types_are_discoverable(client, db_session, ilays, auth_headers):
    response = client.get("/api/v1/media/accepted-types", headers=auth_headers(ilays.manager))
    assert response.status_code == 200
    assert "image/png" in response.json()["accepted_content_types"]
    assert response.json()["url_prefix"] == "/media"
