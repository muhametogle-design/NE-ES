"""Photo persistence, account lifecycle, and fail-closed subject/class RBAC.

This module uses a fresh FK-enforcing database per test. Deliberately different
User/Teacher IDs catch regressions that accidentally authorize by numeric ID.
"""
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.db import get_db
from app.core.ratelimit import rate_limit
from app.core.security import create_access_token, hash_password, verify_password
from app.main import app
from app.models import Base
from app.models.academic import (
    LiveAttendance, SchoolClass, Student, StudentGrade, Subject, SubjectAttendance,
    Teacher, TeachingAssignment, TimetableSlot,
)
from app.models.absence import TeacherAbsence
from app.models.syllabus import SyllabusPlan, SyllabusProgressEntry, SyllabusTopic
from app.models.tenancy import PrivateSchool, SchoolRollSequence, User
from app.services.tenant_service import TenantService

PASSWORD = "TeacherScope@2026"
PHOTO = "https://media.example.org/photos/original.jpg"
NEW_PHOTO = "/media/photos/updated.png"
TODAY = "2026-09-07"


def _headers(user):
    token = create_access_token({"sub": str(user.id), "role": user.role, "school_id": user.school_id})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def password_hash():
    return hash_password(PASSWORD)


@pytest.fixture
def scoped_school(password_hash):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)

    @event.listens_for(engine, "connect")
    def enforce_fks(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine, autoflush=False) as db:
        school = PrivateSchool(id=1, school_code="TS", school_name="Scoped School")
        foreign_school = PrivateSchool(id=2, school_code="TX", school_name="Other School")
        db.add_all([school, foreign_school])
        db.flush()

        def account(id, role="teacher", school_id=1, active=True):
            return User(
                id=id, school_id=school_id, role=role,
                email=f"account{id}@example.org", password_hash=password_hash,
                first_name=f"User{id}", last_name="Account", staff_identifier=f"AUTH-{id}", is_active=active,
            )

        manager = account(100, "school_manager")
        user = account(101)
        other_user = account(102)
        unbound_user = account(103)
        foreign_user = account(201, school_id=2)
        disabled_user = account(104, active=False)
        state_user = account(300, "state_admin", school_id=None)
        db.add_all([manager, user, other_user, unbound_user, foreign_user, disabled_user, state_user])
        db.add(SchoolRollSequence(school_id=1, next_value=10000))
        db.flush()

        teacher = Teacher(
            id=11, school_id=1, user=user, first_name="Assigned", last_name="Teacher",
            email=user.email, photo_url=PHOTO, staff_identifier="PROFILE-11",
        )
        other_teacher = Teacher(
            id=12, school_id=1, user=other_user, first_name="Other", last_name="Teacher",
            email=other_user.email, staff_identifier="PROFILE-12",
        )
        foreign_teacher = Teacher(
            id=13, school_id=2, user=foreign_user, first_name="Foreign", last_name="Teacher",
            email=foreign_user.email, staff_identifier="PROFILE-13",
        )
        classes = [SchoolClass(id=i, school_id=2 if i == 4 else 1, class_level=4, stream=f"C{i}") for i in range(1, 5)]
        subjects = [Subject(
            id=i, school_id=2 if i == 4 else 1, level=4, code=f"SUB-{i}", name=f"Subject {i}",
        ) for i in range(1, 5)]
        db.add_all([teacher, other_teacher, foreign_teacher, *classes, *subjects])
        db.flush()
        # Subject 2 belongs to this teacher in C2, but to another teacher in C1.
        # Subject 1 is assigned twice: listing must still return it only once.
        assignments = [(11, 1, 1), (11, 2, 1), (11, 2, 2), (12, 1, 2), (12, 3, 3), (13, 4, 4)]
        for tid, cid, sid in assignments:
            db.add(TeachingAssignment(school_id=2 if cid == 4 else 1, teacher_id=tid, class_id=cid, subject_id=sid))
        students = [Student(
            id=i, school_id=2 if i == 4 else 1, class_id=i,
            roll_number=f"{'TX' if i == 4 else 'TS'}-{i}", national_student_id=f"SID-{i}",
            first_name=f"Student{i}", last_name="Learner", gender="Female", photo_url=PHOTO,
        ) for i in range(1, 5)]
        slots = [
            TimetableSlot(id=1, school_id=1, class_id=1, subject_id=1, teacher_id=11, day_of_week=0, period=1),
            TimetableSlot(id=2, school_id=1, class_id=1, subject_id=2, teacher_id=12, day_of_week=0, period=2),
            TimetableSlot(id=3, school_id=1, class_id=3, subject_id=3, teacher_id=12, day_of_week=0, period=1),
        ]
        plans = [
            SyllabusPlan(id=1, school_id=1, class_id=1, subject_id=1),
            SyllabusPlan(id=2, school_id=1, class_id=1, subject_id=2),
            SyllabusPlan(id=3, school_id=2, class_id=4, subject_id=4),
        ]
        db.add_all([*students, *slots, *plans])
        db.flush()
        db.add_all([SyllabusTopic(id=i, plan_id=i, unit_number=1, title=f"Topic {i}") for i in range(1, 4)])
        db.commit()

        ctx = SimpleNamespace(
            db=db, manager=manager, user=user, other_user=other_user, unbound_user=unbound_user,
            foreign_user=foreign_user, disabled_user=disabled_user,
            teacher=teacher, other_teacher=other_teacher, foreign_teacher=foreign_teacher,
            classes=classes, subjects=subjects, students=students, slots=slots,
            manager_headers=_headers(manager), headers=_headers(user), other_headers=_headers(other_user),
            unbound_headers=_headers(unbound_user), state_headers=_headers(state_user),
        )
        original_overrides = app.dependency_overrides.copy()
        app.dependency_overrides[get_db] = lambda: db
        rate_limit.reset()
        try:
            with TestClient(app) as client:
                ctx.client = client
                yield ctx
        finally:
            app.dependency_overrides.clear()
            app.dependency_overrides.update(original_overrides)
    engine.dispose()


@pytest.mark.parametrize("prefix", ["/api/v1", "/api/v1/school"])
@pytest.mark.parametrize("resource", ["students", "teachers"])
def test_photo_create_read_update_omit_and_clear(scoped_school, prefix, resource):
    s = scoped_school
    payload = {"first_name": "Photo", "last_name": "Record", "photo_url": PHOTO}
    if resource == "students":
        payload.update(gender="Female", class_id=1)
    created = s.client.post(f"{prefix}/{resource}", headers=s.manager_headers, json=payload)
    assert created.status_code == 201, created.text
    record = created.json()
    assert record["photo_url"] == PHOTO
    path = f"{prefix}/{resource}/{record['id']}"
    assert s.client.get(path, headers=s.manager_headers).json()["photo_url"] == PHOTO
    listed = s.client.get(f"{prefix}/{resource}", headers=s.manager_headers).json()
    items = listed["items"] if resource == "students" else listed
    assert next(item for item in items if item["id"] == record["id"])["photo_url"] == PHOTO

    updated = s.client.patch(path, headers=s.manager_headers, json={"photo_url": NEW_PHOTO})
    assert updated.status_code == 200, updated.text
    assert updated.json()["photo_url"] == NEW_PHOTO
    omitted = s.client.put(path, headers=s.manager_headers, json={"first_name": "Changed"})
    assert omitted.status_code == 200
    assert omitted.json()["photo_url"] == NEW_PHOTO
    cleared = s.client.patch(path, headers=s.manager_headers, json={"photo_url": None})
    assert cleared.status_code == 200
    assert cleared.json()["photo_url"] is None
    s.db.expire_all()
    model = Student if resource == "students" else Teacher
    assert s.db.get(model, record["id"]).photo_url is None


@pytest.mark.parametrize("resource", ["students", "teachers"])
def test_photo_length_and_type_validation(scoped_school, resource):
    s = scoped_school
    path = f"/api/v1/{resource}/{1 if resource == 'students' else 11}"
    response = s.client.patch(path, headers=s.manager_headers, json={"photo_url": "x" * 500})
    assert response.status_code == 200
    for value in ("x" * 501, {"url": PHOTO}, 123):
        response = s.client.patch(path, headers=s.manager_headers, json={"photo_url": value})
        assert response.status_code == 422
    assert s.client.get(path, headers=s.manager_headers).json()["photo_url"] == "x" * 500
    payload = {"first_name": "Invalid", "last_name": "Photo", "photo_url": "x" * 501, "gender": "Female"}
    if resource == "teachers":
        payload.pop("gender")
    assert s.client.post(f"/api/v1/{resource}", headers=s.manager_headers, json=payload).status_code == 422


@pytest.mark.parametrize("mode", ["nested", "legacy"])
def test_teacher_provisions_login_atomically_without_returning_secrets(scoped_school, mode):
    s = scoped_school
    credentials = {"email": "new.teacher@example.org", "password": PASSWORD}
    payload = {"first_name": "New", "last_name": "Teacher", "photo_url": PHOTO}
    if mode == "nested":
        payload["create_user"] = {**credentials, "role": "teacher"}
    else:
        payload.update(credentials)
    response = s.client.post("/api/v1/teachers", headers=s.manager_headers, json=payload)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["id"] != result["user_id"]
    assert not {"password", "password_hash", "create_user"}.intersection(result)
    account = s.db.get(User, result["user_id"])
    profile = s.db.get(Teacher, result["id"])
    assert account.role == "teacher" and account.school_id == s.manager.school_id
    assert account.teacher is profile and profile.user is account
    assert account.password_hash != PASSWORD and verify_password(PASSWORD, account.password_hash)

    login = s.client.post("/api/auth/login", json=credentials)
    assert login.status_code == 200, login.text
    assert login.json()["user"]["teacher_id"] == profile.id
    assert login.json()["user"]["photo_url"] == PHOTO
    assert "password_hash" not in login.text


def test_teacher_can_be_created_without_login_then_manually_linked(scoped_school):
    s = scoped_school
    user_count = s.db.query(User).count()
    response = s.client.post("/api/v1/teachers", headers=s.manager_headers, json={
        "first_name": "Unlinked", "last_name": "Staff", "photo_url": PHOTO,
    })
    assert response.status_code == 201
    profile = response.json()
    assert profile["user_id"] is None
    assert s.db.query(User).count() == user_count
    assigned = s.client.post("/api/v1/school/assignments", headers=s.manager_headers, json={
        "teacher_id": profile["id"], "class_id": 3, "subject_id": 3,
    })
    assert assigned.status_code == 201, assigned.text
    assert s.client.get("/api/v1/subjects", headers=s.unbound_headers).json() == []
    linked = s.client.patch(f"/api/v1/teachers/{profile['id']}", headers=s.manager_headers, json={
        "user_id": s.unbound_user.id,
    })
    assert linked.status_code == 200, linked.text
    assert linked.json()["user_id"] == s.unbound_user.id
    assert linked.json()["photo_url"] == PHOTO
    assert s.db.query(User).count() == user_count
    assert {r["id"] for r in s.client.get("/api/v1/subjects", headers=s.unbound_headers).json()} == {3}


def test_teacher_can_manually_link_existing_user_during_creation(scoped_school):
    s = scoped_school
    user_count = s.db.query(User).count()
    response = s.client.post("/api/v1/teachers", headers=s.manager_headers, json={
        "first_name": "Linked", "last_name": "Staff", "user_id": s.unbound_user.id,
    })
    assert response.status_code == 201, response.text
    assert response.json()["user_id"] == s.unbound_user.id
    assert response.json()["email"] == s.unbound_user.email
    assert s.db.query(User).count() == user_count
    assert verify_password(PASSWORD, s.unbound_user.password_hash)


@pytest.mark.parametrize("user_field,status", [
    ("foreign_user", 404), ("manager", 400), ("disabled_user", 400), ("other_user", 409),
])
@pytest.mark.parametrize("operation", ["create", "update"])
def test_binding_rejects_foreign_wrong_role_disabled_or_already_linked_accounts(scoped_school, user_field, status, operation):
    s = scoped_school
    payload = {"user_id": getattr(s, user_field).id}
    if operation == "create":
        payload.update(first_name="Bad", last_name="Link")
        response = s.client.post("/api/v1/teachers", headers=s.manager_headers, json=payload)
    else:
        response = s.client.patch("/api/v1/teachers/11", headers=s.manager_headers, json=payload)
    assert response.status_code == status, response.text
    s.db.refresh(s.teacher)
    assert s.teacher.user_id == s.user.id
    assert s.db.query(Teacher).count() == 3


def test_missing_user_binding_returns_404(scoped_school):
    s = scoped_school
    assert s.client.patch("/api/v1/teachers/11", headers=s.manager_headers, json={"user_id": 9999}).status_code == 404


@pytest.mark.parametrize("extra", [
    {"role": "school_manager"},
    {"school_id": 2},
    {"create_user": {"email": "test@example.org", "password": PASSWORD, "role": "state_admin"}},
    {"create_user": {"email": "test@example.org", "password": PASSWORD, "school_id": 2}},
    {"user_id": 103, "create_user": {"email": "test@example.org", "password": PASSWORD}},
    {"user_id": 103, "email": "test@example.org", "password": PASSWORD},
    {"password": PASSWORD},
])
def test_provisioning_rejects_escalation_and_ambiguous_modes(scoped_school, extra):
    s = scoped_school
    response = s.client.post("/api/v1/teachers", headers=s.manager_headers, json={
        "first_name": "Bad", "last_name": "Provision", **extra,
    })
    assert response.status_code == 422
    assert s.db.query(User).count() == 7 and s.db.query(Teacher).count() == 3


def test_duplicate_email_and_constraint_race_leave_no_orphan_login(scoped_school, monkeypatch):
    s = scoped_school
    original_count = s.db.query(User).count()
    payload = {
        "first_name": "Atomic", "last_name": "Staff",
        "create_user": {"email": s.other_user.email.upper(), "password": PASSWORD},
    }
    assert s.client.post("/api/v1/teachers", headers=s.manager_headers, json=payload).status_code == 409
    payload["create_user"]["email"] = "atomic@example.org"
    # This identifier is unique among Users, so the login INSERT succeeds;
    # the subsequent Teacher INSERT conflicts and must roll it back as well.
    with monkeypatch.context() as patch:
        patch.setattr(TenantService, "generate_staff_id", lambda _: s.other_teacher.staff_identifier)
        response = s.client.post("/api/v1/teachers", headers=s.manager_headers, json=payload)
        assert response.status_code == 409, response.text
    assert s.db.query(User).count() == original_count
    assert s.db.query(User).filter_by(email="atomic@example.org").first() is None
    assert s.db.query(Teacher).count() == 3
    assert s.client.post("/api/v1/teachers", headers=s.manager_headers, json=payload).status_code == 201


def test_rebinding_and_unlinking_immediately_transfer_and_revoke_scope(scoped_school):
    s = scoped_school
    linked = s.client.patch("/api/v1/teachers/11", headers=s.manager_headers, json={"user_id": 103})
    assert linked.status_code == 200
    assert s.client.get("/api/v1/subjects", headers=s.headers).json() == []
    assert s.client.get("/api/v1/subjects/1", headers=s.headers).status_code == 403
    assert {r["id"] for r in s.client.get("/api/v1/subjects", headers=s.unbound_headers).json()} == {1, 2}
    assert s.client.patch("/api/v1/subjects/1", headers=s.unbound_headers, json={"name": "New owner"}).status_code == 200
    assert s.client.patch("/api/v1/teachers/11", headers=s.manager_headers, json={"user_id": None}).status_code == 200
    assert s.client.get("/api/v1/classrooms", headers=s.unbound_headers).json() == []
    assert s.client.get("/api/v1/subjects/1", headers=s.unbound_headers).status_code == 403
    assert s.db.query(TeachingAssignment).filter_by(teacher_id=11).count() == 3
    assert s.db.get(Teacher, 11).photo_url == PHOTO


def test_deleting_login_sets_binding_null_without_deleting_teacher_or_assignments(scoped_school):
    s = scoped_school
    # Raw SQL tests ON DELETE SET NULL rather than ORM relationship bookkeeping.
    s.db.execute(delete(User).where(User.id == s.user.id))
    s.db.commit()
    s.db.expire_all()
    teacher = s.db.get(Teacher, 11)
    assert teacher.user_id is None and teacher.user is None
    assert teacher.photo_url == PHOTO
    assert len(teacher.assignments) == 3
    assert s.db.get(TimetableSlot, 1).teacher_id == 11


def test_relationships_share_one_authoritative_assignment_mapping(scoped_school):
    s = scoped_school
    assert s.user.teacher.id == 11
    assert {a.id for a in s.user.teaching_assignments} == {a.id for a in s.teacher.assignments}
    assert {sub.id for sub in s.teacher.subjects} == {1, 2}
    assert {t.id for t in s.subjects[0].teachers} == {11}
    assert {c.id for c in s.teacher.classrooms} == {1, 2}
    assert {t.id for t in s.classes[0].teachers} == {11, 12}
    assert {st.id for st in s.teacher.students} == {1, 2}
    assert {t.id for t in s.students[0].teachers} == {11, 12}


@pytest.mark.parametrize("prefix,classes", [("/api/v1", "classrooms"), ("/api/v1/school", "classes")])
def test_subject_and_class_lists_are_explicitly_scoped_and_deduplicated(scoped_school, prefix, classes):
    s = scoped_school
    for resource in ("subjects", classes):
        response = s.client.get(f"{prefix}/{resource}", headers=s.headers)
        assert response.status_code == 200
        ids = [row["id"] for row in response.json()]
        assert set(ids) == {1, 2} and len(ids) == 2
        assert {row["id"] for row in s.client.get(f"{prefix}/{resource}", headers=s.manager_headers).json()} == {1, 2, 3}
    assert s.client.get(f"{prefix}/subjects?level=5", headers=s.headers).json() == []


@pytest.mark.parametrize("state", ["unbound", "inactive_profile"])
def test_unbound_or_inactive_teacher_fails_closed(scoped_school, state):
    s = scoped_school
    headers = s.unbound_headers
    if state == "inactive_profile":
        assert s.client.delete("/api/v1/teachers/11", headers=s.manager_headers).status_code == 200
        headers = s.headers
    for path in ("/api/v1/subjects", "/api/v1/classrooms", "/api/v1/school/timetable"):
        response = s.client.get(path, headers=headers)
        assert response.status_code == 200 and response.json() == []
    assert s.client.get("/api/v1/subjects/1", headers=headers).status_code == 403
    assert s.client.get("/api/v1/classrooms/1", headers=headers).status_code == 403
    assert s.client.post("/api/v1/school/attendance", headers=headers, json={
        "class_id": 1, "subject_id": 1, "date": TODAY, "records": [],
    }).status_code == 403


@pytest.mark.parametrize("base", ["/api/v1/subjects", "/api/v1/school/subjects", "/api/v1/classrooms", "/api/v1/school/classes"])
@pytest.mark.parametrize("method", ["get", "patch", "put"])
def test_teacher_gets_403_for_another_teachers_resource(scoped_school, base, method):
    s = scoped_school
    kwargs = {} if method == "get" else {"json": {"name": "Forbidden"} if "subjects" in base else {"stream": "Forbidden"}}
    response = getattr(s.client, method)(f"{base}/3", headers=s.headers, **kwargs)
    assert response.status_code == 403, response.text
    assert s.db.get(Subject, 3).name == "Subject 3"
    assert s.db.get(SchoolClass, 3).stream == "C3"


@pytest.mark.parametrize("base", ["/api/v1/subjects", "/api/v1/school/subjects", "/api/v1/classrooms", "/api/v1/school/classes"])
def test_teacher_can_read_and_update_assigned_resource(scoped_school, base):
    s = scoped_school
    assert s.client.get(f"{base}/1", headers=s.headers).status_code == 200
    payload = {"name": "Allowed"} if "subjects" in base else {"stream": "Allowed"}
    response = s.client.patch(f"{base}/1", headers=s.headers, json=payload)
    assert response.status_code == 200, response.text
    assert all(response.json()[key] == value for key, value in payload.items())


@pytest.mark.parametrize("base", ["/api/v1/subjects", "/api/v1/classrooms"])
def test_foreign_or_missing_resource_is_404_even_for_managers(scoped_school, base):
    s = scoped_school
    for headers in (s.headers, s.manager_headers):
        for id in (4, 9999):
            assert s.client.get(f"{base}/{id}", headers=headers).status_code == 404


@pytest.mark.parametrize("base", ["/api/v1/classrooms", "/api/v1/school/classes"])
def test_nested_class_views_do_not_leak_other_subject_assignments(scoped_school, base):
    s = scoped_school
    assert {row["id"] for row in s.client.get(f"{base}/1/subjects", headers=s.headers).json()} == {1}
    breakdown = s.client.get(f"{base}/1/breakdown", headers=s.headers).json()
    assert {row["subject_id"] for row in breakdown["subjects"]} == {1}
    assignment = s.client.get(f"{base}/1/subjects/1/assignment", headers=s.headers)
    assert assignment.status_code == 200 and assignment.json()["teacher_id"] == 11
    # Teacher owns C1 and subject 2 separately, but not their pairing.
    assert s.client.get(f"{base}/1/subjects/2/assignment", headers=s.headers).status_code == 403
    for suffix in ("subjects", "breakdown", "subjects/3/assignment"):
        assert s.client.get(f"{base}/3/{suffix}", headers=s.headers).status_code == 403


def test_student_roster_and_photo_writes_are_class_scoped(scoped_school):
    s = scoped_school
    response = s.client.get("/api/v1/students?per_page=1", headers=s.headers)
    assert response.status_code == 200
    assert response.json()["total"] == 2 and response.json()["pages"] == 2
    assert s.client.get("/api/v1/students?class_id=3", headers=s.headers).status_code == 403
    assert s.client.get("/api/v1/students/3", headers=s.headers).status_code == 403
    assert s.client.patch("/api/v1/students/1", headers=s.headers, json={"photo_url": NEW_PHOTO}).status_code == 200
    assert s.client.patch("/api/v1/students/3", headers=s.headers, json={"photo_url": NEW_PHOTO}).status_code == 403
    for target_class in (None, 3):
        assert s.client.patch("/api/v1/students/1", headers=s.headers, json={"class_id": target_class}).status_code == 403
    assert s.db.get(Student, 1).class_id == 1
    assert s.db.get(Student, 3).photo_url == PHOTO
    assert s.client.patch("/api/v1/students/4", headers=s.manager_headers, json={"photo_url": NEW_PHOTO}).status_code == 404
    assert s.client.patch("/api/v1/teachers/13", headers=s.manager_headers, json={"photo_url": NEW_PHOTO}).status_code == 404


def _academic_payload(endpoint, *, class_id=1, subject_id=1, student_ids=(1,)):
    if endpoint == "attendance/live":
        return {"timetable_slot_id": 1, "date": TODAY, "records": [{"student_id": i, "status": "present"} for i in student_ids]}
    payload = {"class_id": class_id, "subject_id": subject_id}
    if endpoint == "attendance":
        payload.update(date=TODAY, records=[{"student_id": i, "status": "present"} for i in student_ids])
    else:
        payload["term"] = "Scoped term"
        if endpoint == "grades":
            payload["grades"] = [{"student_id": i, "score": 88} for i in student_ids]
    return payload


@pytest.mark.parametrize("endpoint", ["attendance", "grades", "grades/publish"])
@pytest.mark.parametrize("class_id,subject_id", [(1, 2), (3, 3)])
def test_writes_require_the_exact_assigned_class_subject_pair(scoped_school, endpoint, class_id, subject_id):
    s = scoped_school
    payload = _academic_payload(endpoint, class_id=class_id, subject_id=subject_id)
    response = s.client.post(f"/api/v1/school/{endpoint}", headers=s.headers, json=payload)
    assert response.status_code == 403, response.text
    assert s.db.query(StudentGrade).count() == 0 and s.db.query(SubjectAttendance).count() == 0


@pytest.mark.parametrize("endpoint", ["attendance", "grades", "attendance/live"])
@pytest.mark.parametrize("student_id,status", [(2, 403), (3, 403), (4, 404), (9999, 404)])
def test_mixed_batches_cannot_smuggle_students_from_other_classes_or_tenants(scoped_school, endpoint, student_id, status):
    s = scoped_school
    payload = _academic_payload(endpoint, student_ids=(1, student_id))
    response = s.client.post(f"/api/v1/school/{endpoint}", headers=s.headers, json=payload)
    assert response.status_code == status, response.text
    assert s.db.query(StudentGrade).count() == 0
    assert s.db.query(SubjectAttendance).count() == 0
    assert s.db.query(LiveAttendance).count() == 0


@pytest.mark.parametrize("endpoint", ["attendance", "grades", "attendance/live", "grades/publish"])
def test_teacher_can_write_assigned_course(scoped_school, endpoint):
    s = scoped_school
    response = s.client.post(f"/api/v1/school/{endpoint}", headers=s.headers, json=_academic_payload(endpoint))
    assert response.status_code == 200, response.text


def test_grade_and_attendance_reads_and_live_session_writes_are_scoped(scoped_school):
    s = scoped_school
    for endpoint in ("grades", "attendance"):
        assert s.client.get(f"/api/v1/school/{endpoint}?class_id=1&subject_id=2", headers=s.headers).status_code == 403
        assert s.client.get(f"/api/v1/school/{endpoint}?class_id=1&subject_id=1", headers=s.headers).status_code == 200
    assert s.client.get("/api/v1/school/attendance/live?slot_id=2", headers=s.headers).status_code == 403
    payload = _academic_payload("attendance/live")
    payload["timetable_slot_id"] = 2
    assert s.client.post("/api/v1/school/attendance/live", headers=s.headers, json=payload).status_code == 403
    timetable = s.client.get("/api/v1/school/timetable", headers=s.headers)
    assert timetable.status_code == 200 and [row["id"] for row in timetable.json()] == [1]
    assert s.client.get("/api/v1/school/timetable?teacher_id=12", headers=s.headers).status_code == 403


@pytest.mark.parametrize("endpoint,payload", [
    ("/api/v1/teachers", {"first_name": "Escalate", "last_name": "Staff", "user_id": 103}),
    ("/api/v1/subjects", {"code": "NEW", "name": "Unassigned", "level": 4}),
    ("/api/v1/classrooms", {"class_level": 4, "stream": "NEW"}),
    ("/api/v1/school/assignments", {"teacher_id": 11, "class_id": 3, "subject_id": 3}),
    ("/api/v1/school/timetable", {"teacher_id": 11, "class_id": 3, "subject_id": 3, "day_of_week": 0, "period": 5}),
])
def test_teacher_cannot_self_provision_or_grant_scope(scoped_school, endpoint, payload):
    s = scoped_school
    assert s.client.post(endpoint, headers=s.headers, json=payload).status_code == 403
    assert s.db.query(TeachingAssignment).filter_by(teacher_id=11, class_id=3).count() == 0


def test_teacher_cannot_rebind_profiles_delete_subjects_or_remove_slots(scoped_school):
    s = scoped_school
    assert s.client.patch("/api/v1/teachers/12", headers=s.headers, json={"user_id": 101}).status_code == 403
    assert s.client.patch("/api/v1/teachers/11", headers=s.headers, json={"user_id": 103}).status_code == 403
    assert s.client.delete("/api/v1/subjects/3", headers=s.headers).status_code == 403
    assert s.client.delete("/api/v1/school/timetable/2", headers=s.headers).status_code == 403
    assert s.db.get(Teacher, 12).user_id == 102


@pytest.mark.parametrize("field,value", [("teacher_id", 13), ("class_id", 4), ("subject_id", 4)])
def test_manager_assignments_cannot_cross_tenants(scoped_school, field, value):
    s = scoped_school
    payload = {"teacher_id": 11, "class_id": 1, "subject_id": 1, field: value}
    assert s.client.post("/api/v1/school/assignments", headers=s.manager_headers, json=payload).status_code == 404


def test_manager_can_write_any_course_in_own_school(scoped_school):
    s = scoped_school
    for endpoint in ("attendance", "grades", "grades/publish"):
        response = s.client.post(f"/api/v1/school/{endpoint}", headers=s.manager_headers, json=_academic_payload(
            endpoint, class_id=3, subject_id=3, student_ids=(3,),
        ))
        assert response.status_code == 200, response.text


def test_syllabus_reads_and_writes_require_exact_course_scope(scoped_school):
    s = scoped_school
    assert [p["id"] for p in s.client.get("/api/v1/school/syllabus/plans", headers=s.headers).json()] == [1]
    status = s.client.get("/api/v1/school/syllabus/status", headers=s.headers).json()
    assert status["total_plans"] == 1
    for path in ("plans/2", "topics?plan_id=2"):
        assert s.client.get(f"/api/v1/school/syllabus/{path}", headers=s.headers).status_code == 403
    for topic_id, status_code in ((1, 201), (2, 403), (3, 404)):
        response = s.client.post("/api/v1/school/syllabus/progress", headers=s.headers, json={
            "topic_id": topic_id, "date_covered": TODAY,
        })
        assert response.status_code == status_code, response.text
    assert s.db.query(SyllabusProgressEntry).count() == 1
    assert s.client.post("/api/v1/school/syllabus/topics", headers=s.headers, json={
        "plan_id": 2, "unit_number": 2, "title": "Forbidden",
    }).status_code == 403


def test_substitution_is_manager_controlled_confirmed_and_date_slot_limited(scoped_school):
    s = scoped_school
    absence = TeacherAbsence(id=1, school_id=1, teacher_id=12, date=date.fromisoformat(TODAY))
    s.db.add(absence)
    s.db.commit()
    payload = {"absence_id": 1, "substitute_teacher_id": 11, "timetable_slot_id": 2}
    assert s.client.post("/api/v1/school/substitutions", headers=s.headers, json=payload).status_code == 403
    created = s.client.post("/api/v1/school/substitutions", headers=s.manager_headers, json=payload)
    assert created.status_code == 201, created.text
    sub_id = created.json()["id"]
    attendance = _academic_payload("attendance/live")
    attendance["timetable_slot_id"] = 2
    assert s.client.post("/api/v1/school/attendance/live", headers=s.headers, json=attendance).status_code == 403
    assert s.client.post(f"/api/v1/school/substitutions/{sub_id}/confirm", headers=s.headers).status_code == 403
    assert s.client.post(f"/api/v1/school/substitutions/{sub_id}/confirm", headers=s.manager_headers).status_code == 200
    assert s.client.post("/api/v1/school/attendance/live", headers=s.headers, json=attendance).status_code == 200
    attendance["date"] = "2026-09-08"
    assert s.client.post("/api/v1/school/attendance/live", headers=s.headers, json=attendance).status_code == 403
    attendance.update(date=TODAY, timetable_slot_id=3)
    assert s.client.post("/api/v1/school/attendance/live", headers=s.headers, json=attendance).status_code == 403
    # Coverage does not grant permanent course metadata/grade authority.
    assert s.client.get("/api/v1/classrooms/1/subjects/2/assignment", headers=s.headers).status_code == 403


@pytest.mark.parametrize("resource", ["subjects", "classrooms", "teachers", "students"])
def test_canonical_resources_require_school_authentication(scoped_school, resource):
    s = scoped_school
    assert s.client.get(f"/api/v1/{resource}").status_code == 401
    assert s.client.get(f"/api/v1/{resource}", headers=s.state_headers).status_code == 403


@pytest.mark.parametrize("endpoint", ["attendance", "grades", "attendance/live"])
def test_invalid_batch_does_not_partially_update_existing_records(scoped_school, endpoint):
    s = scoped_school
    if endpoint == "grades":
        existing = StudentGrade(school_id=1, student_id=1, subject_id=1, term="Scoped term", score=42)
    elif endpoint == "attendance":
        existing = SubjectAttendance(
            school_id=1, student_id=1, class_id=1, subject_id=1, date=date.fromisoformat(TODAY), status="absent",
        )
    else:
        existing = LiveAttendance(
            school_id=1, student_id=1, timetable_slot_id=1, date=date.fromisoformat(TODAY), status="absent",
        )
    s.db.add(existing)
    s.db.commit()
    response = s.client.post(f"/api/v1/school/{endpoint}", headers=s.headers, json=_academic_payload(
        endpoint, student_ids=(1, 3),
    ))
    assert response.status_code == 403
    s.db.refresh(existing)
    if endpoint == "grades":
        assert existing.score == 42
    else:
        assert existing.status == "absent"


def test_grade_updates_and_publication_cannot_modify_another_teachers_subject(scoped_school):
    s = scoped_school
    grade = StudentGrade(school_id=1, student_id=3, subject_id=3, term="Scoped term", score=42, is_published=False)
    s.db.add(grade)
    s.db.commit()
    for endpoint in ("grades", "grades/publish"):
        response = s.client.post(f"/api/v1/school/{endpoint}", headers=s.headers, json=_academic_payload(
            endpoint, class_id=3, subject_id=3, student_ids=(3,),
        ))
        assert response.status_code == 403
    s.db.refresh(grade)
    assert grade.score == 42 and grade.is_published is False


def test_academic_summaries_use_the_same_scope_as_detail_routes(scoped_school):
    s = scoped_school
    for class_id, subject_id, score in ((1, 1, 88), (1, 2, 20), (3, 3, 30)):
        s.db.add(StudentGrade(school_id=1, student_id=class_id, subject_id=subject_id, term="Summary", score=score))
        s.db.add(SubjectAttendance(
            school_id=1, student_id=class_id, class_id=class_id, subject_id=subject_id,
            date=date.today(), status="present" if subject_id == 1 else "absent",
        ))
    s.db.commit()
    enrollment = s.client.get("/api/v1/school/analytics/enrollment", headers=s.headers).json()
    assert enrollment["total_students"] == 2
    performance = s.client.get("/api/v1/school/analytics/academic-performance", headers=s.headers).json()
    assert performance["total_grades_recorded"] == 1 and performance["average_score"] == 88
    attendance = s.client.get("/api/v1/school/analytics/attendance", headers=s.headers).json()
    assert attendance["total_marked"] == 1 and attendance["present_count"] == 1


def test_teacher_absence_ids_are_profile_ids_and_cannot_be_spoofed(scoped_school):
    s = scoped_school
    for teacher_id, expected in ((11, 201), (12, 403), (101, 403)):
        response = s.client.post("/api/v1/school/absences", headers=s.headers, json={
            "teacher_id": teacher_id, "date": TODAY,
        })
        assert response.status_code == expected, response.text
    assert len(s.client.get("/api/v1/school/absences", headers=s.headers).json()) == 1
    assert s.client.get("/api/v1/school/absences", headers=s.other_headers).json() == []
    assert s.client.get("/api/v1/school/substitutions/candidates?slot_id=2", headers=s.headers).status_code == 403
    assert s.client.post("/api/v1/school/attendance/submit", headers=s.headers).status_code == 403


def test_state_staff_views_use_profile_ids_and_photo_fields(scoped_school):
    s = scoped_school
    response = s.client.get("/api/v1/state/institutions/1/teachers", headers=s.state_headers)
    assert response.status_code == 200
    assert {t["id"] for t in response.json()} == {11, 12}
    teacher = s.client.get("/api/v1/state/teachers/11", headers=s.state_headers)
    assert teacher.status_code == 200
    assert teacher.json()["user_id"] == 101 and teacher.json()["photo_url"] == PHOTO
