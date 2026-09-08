"""Subject catalog endpoints — ``/api/v1/subjects``.

Access policy
    * ``GET`` — any school-tenant role. A ``role="teacher"`` caller only ever
      receives the subjects assigned to them, resolved through
      ``teachers.user_id == current_user.id`` (subject-level rows in
      ``teacher_subjects`` plus their class-level ``teaching_assignments``).
    * ``PATCH`` — school managers for any subject of their tenant; teachers only
      for subjects they own at subject level.
    * ``POST`` / ``DELETE`` / teacher-roster writes — school managers only:
      creating or removing a subject, and deciding who teaches it, is a tenant
      administration action.

Cross-tenant access is a 404 (the tenant filter never matches); another
teacher's subject inside the same tenant is a 403.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_school_manager, require_school_tenant
from app.core.db import get_db
from app.models.academic import Subject
from app.models.auth import Teacher, TeacherSubject
from app.models.tenancy import User
from app.schemas.common import MessageResponse
from app.schemas.subject import (
    SubjectCreate, SubjectResponse, SubjectTeacherAssignRequest,
    SubjectTeacherRosterRequest, SubjectTeacherSummary, SubjectUpdate,
)
from app.services.subject_service import SubjectService
from app.services.teacher_scope import TeacherScope

router = APIRouter(prefix="/v1/subjects", tags=["subjects"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_subject(db: Session, user: User, subject_id: int) -> Subject:
    """Tenant-scoped fetch; teachers are additionally checked for ownership."""
    subject = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.school_id == user.school_id)
        .first()
    )
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject {subject_id} not found in this school",
        )
    return TeacherScope.ensure_subject_access(db, user, subject)


def _get_teacher_profile(db: Session, user: User, teacher_id: int) -> Teacher:
    profile = (
        db.query(Teacher)
        .filter(Teacher.id == teacher_id, Teacher.school_id == user.school_id)
        .first()
    )
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Teacher profile {teacher_id} not found in this school",
        )
    return profile


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("", response_model=List[SubjectResponse], summary="List subjects (teacher-scoped)")
async def list_subjects(
    level: Optional[int] = Query(None, ge=1, le=12, description="Filter by class level"),
    q: Optional[str] = Query(None, min_length=1, description="Search in code or name"),
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    query = db.query(Subject).filter(Subject.school_id == user.school_id)
    # Teachers only see the subjects assigned to them.
    query = TeacherScope.scope_subject_query(db, user, query)
    if level is not None:
        query = query.filter(Subject.level == level)
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(or_(Subject.code.ilike(pattern), Subject.name.ilike(pattern)))

    subjects = query.order_by(Subject.level, Subject.code).all()
    return SubjectService.serialize_many(db, subjects)


@router.get("/mine", response_model=List[SubjectResponse], summary="List the caller's assigned subjects")
async def list_my_subjects(
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    """Explicit "what do I teach?" view.

    For teachers this is identical to the scoped ``GET /api/v1/subjects``;
    managers get the subjects mapped to their own staff profile (usually none),
    which keeps the endpoint safe to call from a teacher-only UI.
    """
    profile = TeacherScope.profile_for_user(db, user)
    if profile is None:
        return []

    subject_ids = [
        row[0]
        for row in db.query(TeacherSubject.subject_id)
        .filter(
            TeacherSubject.teacher_id == profile.id,
            TeacherSubject.school_id == user.school_id,
        )
        .all()
    ]
    if not subject_ids:
        return []

    subjects = (
        db.query(Subject)
        .filter(Subject.school_id == user.school_id, Subject.id.in_(subject_ids))
        .order_by(Subject.level, Subject.code)
        .all()
    )
    return SubjectService.serialize_many(db, subjects)


@router.post(
    "",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create subject (school managers)",
)
async def create_subject(
    data: SubjectCreate,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Subject)
        .filter(Subject.school_id == user.school_id, Subject.code == data.code)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subject code '{data.code}' already exists in this school",
        )

    payload = data.model_dump(exclude={"teacher_ids"})
    subject = Subject(school_id=user.school_id, **payload)
    db.add(subject)
    try:
        db.flush()
    except IntegrityError:  # pragma: no cover - race with the pre-check above
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subject code '{data.code}' already exists in this school",
        ) from None

    if data.teacher_ids:
        SubjectService.set_teachers(db, subject, data.teacher_ids, commit=False)
    db.commit()
    db.refresh(subject)
    return SubjectService.serialize(db, subject)


@router.get("/{subject_id}", response_model=SubjectResponse, summary="Get subject")
async def get_subject(
    subject_id: int,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    subject = _get_subject(db, user, subject_id)
    return SubjectService.serialize(db, subject)


@router.patch("/{subject_id}", response_model=SubjectResponse, summary="Update subject")
async def update_subject(
    subject_id: int,
    data: SubjectUpdate,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    subject = _get_subject(db, user, subject_id)
    # Teachers may only edit subjects they own; managers may edit any.
    TeacherScope.ensure_subject_write(db, user, subject)

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided for update",
        )

    teacher_ids = changes.pop("teacher_ids", None)
    if teacher_ids is not None and not TeacherScope.is_manager(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only school managers may change a subject's teacher roster",
        )

    new_code = changes.get("code")
    if new_code and new_code != subject.code:
        clash = (
            db.query(Subject)
            .filter(Subject.school_id == user.school_id, Subject.code == new_code)
            .first()
        )
        if clash is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Subject code '{new_code}' already exists in this school",
            )

    for field, value in changes.items():
        setattr(subject, field, value)

    if teacher_ids is not None:
        SubjectService.set_teachers(db, subject, teacher_ids, commit=False)

    try:
        db.commit()
    except IntegrityError:  # pragma: no cover - race with the pre-check above
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Subject code '{new_code}' already exists in this school",
        ) from None
    db.refresh(subject)
    return SubjectService.serialize(db, subject)


@router.delete("/{subject_id}", response_model=MessageResponse, summary="Delete subject (school managers)")
async def delete_subject(
    subject_id: int,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    subject = (
        db.query(Subject)
        .filter(Subject.id == subject_id, Subject.school_id == user.school_id)
        .first()
    )
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Subject {subject_id} not found in this school",
        )
    db.delete(subject)
    db.commit()
    return {"message": f"Subject '{subject.code}' deleted"}


# ---------------------------------------------------------------------------
# Subject ↔ teacher roster
# ---------------------------------------------------------------------------
@router.get(
    "/{subject_id}/teachers",
    response_model=List[SubjectTeacherSummary],
    summary="List teachers assigned to a subject",
)
async def list_subject_teachers(
    subject_id: int,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    subject = _get_subject(db, user, subject_id)
    return SubjectService.teacher_map(db, [subject.id]).get(subject.id, [])


@router.post(
    "/{subject_id}/teachers",
    response_model=SubjectResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Assign a teacher to a subject (school managers)",
)
async def assign_subject_teacher(
    subject_id: int,
    data: SubjectTeacherAssignRequest,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    subject = _get_subject(db, user, subject_id)
    _get_teacher_profile(db, user, data.teacher_id)
    SubjectService.add_teacher(db, subject, data.teacher_id, is_primary=data.is_primary)
    db.refresh(subject)
    return SubjectService.serialize(db, subject)


@router.put(
    "/{subject_id}/teachers",
    response_model=SubjectResponse,
    summary="Replace a subject's teacher roster (school managers)",
)
async def set_subject_teachers(
    subject_id: int,
    data: SubjectTeacherRosterRequest,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    subject = _get_subject(db, user, subject_id)
    for teacher_id in data.teacher_ids:
        _get_teacher_profile(db, user, teacher_id)
    SubjectService.set_teachers(db, subject, data.teacher_ids, data.primary_teacher_id)
    db.refresh(subject)
    return SubjectService.serialize(db, subject)


@router.delete(
    "/{subject_id}/teachers/{teacher_id}",
    response_model=SubjectResponse,
    summary="Remove a teacher from a subject (school managers)",
)
async def unassign_subject_teacher(
    subject_id: int,
    teacher_id: int,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    subject = _get_subject(db, user, subject_id)
    SubjectService.remove_teacher(db, subject, teacher_id)
    db.refresh(subject)
    return SubjectService.serialize(db, subject)
