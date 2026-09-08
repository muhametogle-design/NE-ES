"""Teacher staff-profile endpoints — ``/api/v1/teachers``.

These endpoints manage the *staff profile* (``teachers``) and its binding to a
login account (``users`` with ``role="teacher"``):

* ``POST /api/v1/teachers`` provisions the profile **and** the user account in
  one call (``auto_provision_user`` defaults to true), or binds an existing
  account through ``link_user_id``;
* ``POST /api/v1/teachers/me`` auto-links a profile to the caller's own
  account (useful for staff seeded before profiles existed);
* ``PATCH`` accepts ``photo_url`` — managers may change anything, a teacher may
  only change their own portrait, phone and bio;
* ``PUT /{id}/subjects`` maintains the subject-level mapping that
  ``/api/v1/subjects`` and ``/api/v1/classrooms`` scope against.

Access policy: school managers manage their own tenant's staff; teachers see and
edit only their own profile; state roles are rejected by
:func:`app.api.deps.require_school_tenant`; other tenants are a 404.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_school_manager, require_school_tenant
from app.core.db import get_db
from app.models.auth import Teacher
from app.models.tenancy import User
from app.schemas.common import MessageResponse
from app.schemas.teacher import (
    TeacherCreate, TeacherLinkUserRequest, TeacherResponse,
    TeacherSubjectSetRequest, TeacherUpdate,
)
from app.services.teacher_scope import TeacherScope
from app.services.teacher_service import TeacherService

router = APIRouter(prefix="/v1/teachers", tags=["teachers"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_profile(db: Session, user: User, teacher_id: int) -> Teacher:
    """Tenant-scoped fetch; teachers may only reach their own profile."""
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
    if not TeacherScope.is_manager(user) and profile.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Teachers may only access their own staff profile",
        )
    return profile


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------
@router.get("", response_model=List[TeacherResponse], summary="List staff profiles (teacher-scoped)")
async def list_teachers(
    q: Optional[str] = Query(None, min_length=1, description="Search in names or email"),
    include_inactive: bool = Query(False, description="Also return deactivated profiles"),
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    query = db.query(Teacher).filter(Teacher.school_id == user.school_id)

    if TeacherScope.is_restricted(user):
        # A teacher only ever sees their own record.
        query = query.filter(Teacher.user_id == user.id)
    if not include_inactive:
        query = query.filter(Teacher.is_active.is_(True))
    if q:
        pattern = f"%{q.strip()}%"
        query = query.filter(
            Teacher.first_name.ilike(pattern)
            | Teacher.last_name.ilike(pattern)
            | Teacher.email.ilike(pattern)
        )

    profiles = query.order_by(Teacher.last_name, Teacher.first_name).all()
    return TeacherService.serialize_many(db, profiles)


@router.post(
    "",
    response_model=TeacherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create staff profile (school managers)",
)
async def create_teacher(
    data: TeacherCreate,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    """Create a profile and, by default, provision its ``role="teacher"`` login."""
    profile = TeacherService.create_profile(db, caller=user, payload=data)
    return TeacherService.serialize(db, profile)


# ---------------------------------------------------------------------------
# Self-service
# ---------------------------------------------------------------------------
@router.get("/me", response_model=TeacherResponse, summary="Current caller's staff profile")
async def get_my_profile(
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    profile = TeacherScope.profile_for_user(db, user)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No staff profile is bound to this account yet; "
                "call POST /api/v1/teachers/me or ask a school manager to create one"
            ),
        )
    return TeacherService.serialize(db, profile)


@router.post(
    "/me",
    response_model=TeacherResponse,
    status_code=status.HTTP_200_OK,
    summary="Auto-link a staff profile to the caller's account",
)
async def sync_my_profile(
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    """Idempotent: returns the existing profile or creates and binds one."""
    profile = TeacherService.ensure_profile_for_user(db, user)
    return TeacherService.serialize(db, profile)


# ---------------------------------------------------------------------------
# Item
# ---------------------------------------------------------------------------
@router.get("/{teacher_id}", response_model=TeacherResponse, summary="Get staff profile")
async def get_teacher(
    teacher_id: int,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    return TeacherService.serialize(db, _get_profile(db, user, teacher_id))


@router.patch("/{teacher_id}", response_model=TeacherResponse, summary="Update staff profile")
async def update_teacher(
    teacher_id: int,
    data: TeacherUpdate,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    profile = _get_profile(db, user, teacher_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided for update",
        )

    self_service = not TeacherScope.is_manager(user)
    profile = TeacherService.update_profile(db, profile, data, self_service=self_service)
    return TeacherService.serialize(db, profile)


@router.delete("/{teacher_id}", response_model=MessageResponse, summary="Deactivate staff profile (school managers)")
async def deactivate_teacher(
    teacher_id: int,
    deactivate_account: bool = Query(
        False, description="Also disable the bound login account"
    ),
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
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

    # Soft delete: staff history (grades, attendance, photos) must survive.
    profile.is_active = False
    account = (
        db.query(User).filter(User.id == profile.user_id).first()
        if profile.user_id is not None
        else None
    )
    if account is not None and deactivate_account:
        account.is_active = False
    db.commit()

    message = f"Staff profile '{profile.full_name}' deactivated"
    if account is not None and deactivate_account:
        message += " and its login account disabled"
    return {"message": message}


# ---------------------------------------------------------------------------
# Bindings
# ---------------------------------------------------------------------------
@router.post(
    "/{teacher_id}/link-user",
    response_model=TeacherResponse,
    summary="Bind a profile to an existing teacher account (school managers)",
)
async def link_teacher_user(
    teacher_id: int,
    data: TeacherLinkUserRequest,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
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
    if profile.user_id is not None and profile.user_id != data.user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Staff profile {profile.id} is already bound to user account "
                f"{profile.user_id}; unlink it before rebinding"
            ),
        )

    profile = TeacherService.link_user(db, profile, data.user_id)
    return TeacherService.serialize(db, profile)


@router.put(
    "/{teacher_id}/subjects",
    response_model=TeacherResponse,
    summary="Replace a teacher's subject assignments (school managers)",
)
async def set_teacher_subjects(
    teacher_id: int,
    data: TeacherSubjectSetRequest,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
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

    TeacherService.set_subjects(db, profile, data.subject_ids, data.primary_subject_id)
    db.refresh(profile)
    return TeacherService.serialize(db, profile)
