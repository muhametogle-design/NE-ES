"""V1 Classroom endpoints with multi-tenant isolation."""
from __future__ import annotations

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.academic import Classroom
from app.models.tenancy import PrivateSchool, User
from app.schemas.classroom import ClassroomCreate, ClassroomResponse, ClassroomUpdate

router = APIRouter(prefix="/classrooms", tags=["classrooms"])

STATE_ROLES = {"state_admin", "inspector"}
# "school_admin" is the canonical name in the spec; this deployment also uses
# "school_manager" for the same privilege level.
SCHOOL_WRITE_ROLES = {"school_admin", "school_manager"}
WRITE_ROLES = {"state_admin"} | SCHOOL_WRITE_ROLES


def _is_state(user: User) -> bool:
    return user.role in STATE_ROLES


def _assert_can_write(user: User, school_id: int) -> None:
    if user.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role}' cannot modify classrooms",
        )
    if user.role in SCHOOL_WRITE_ROLES and user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant classroom access denied",
        )


def _assert_can_read(user: User, school_id: int) -> None:
    if _is_state(user):
        return
    if user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant classroom access denied",
        )


def _get_or_404(db: Session, classroom_id: uuid.UUID) -> Classroom:
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classroom {classroom_id} not found",
        )
    return classroom


@router.get("", response_model=List[ClassroomResponse], summary="List classrooms")
def list_classrooms(
    school_id: Optional[int] = Query(None),
    grade_level: Optional[str] = Query(None),
    academic_year: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Classroom)

    if _is_state(user):
        if school_id is not None:
            query = query.filter(Classroom.school_id == school_id)
    else:
        if not user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not assigned to any school tenant",
            )
        if school_id is not None and school_id != user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant classroom access denied",
            )
        query = query.filter(Classroom.school_id == user.school_id)

    if grade_level:
        query = query.filter(Classroom.grade_level == grade_level)
    if academic_year:
        query = query.filter(Classroom.academic_year == academic_year)
    if is_active is not None:
        query = query.filter(Classroom.is_active == is_active)

    return query.order_by(Classroom.grade_level, Classroom.name).all()


@router.post(
    "",
    response_model=ClassroomResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create classroom",
)
def create_classroom(
    payload: ClassroomCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _assert_can_write(user, payload.school_id)

    school = db.query(PrivateSchool).filter(PrivateSchool.id == payload.school_id).first()
    if school is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"School {payload.school_id} not found",
        )

    classroom = Classroom(id=uuid.uuid4(), **payload.model_dump())
    db.add(classroom)
    db.commit()
    db.refresh(classroom)
    return classroom


@router.get("/{classroom_id}", response_model=ClassroomResponse, summary="Get classroom")
def get_classroom(
    classroom_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    classroom = _get_or_404(db, classroom_id)
    _assert_can_read(user, classroom.school_id)
    return classroom


@router.patch("/{classroom_id}", response_model=ClassroomResponse, summary="Update classroom")
def update_classroom(
    classroom_id: uuid.UUID,
    payload: ClassroomUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    classroom = _get_or_404(db, classroom_id)
    _assert_can_write(user, classroom.school_id)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(classroom, field, value)

    db.commit()
    db.refresh(classroom)
    return classroom


@router.delete("/{classroom_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete classroom")
def delete_classroom(
    classroom_id: uuid.UUID,
    soft: bool = Query(False, description="Deactivate instead of hard delete"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    classroom = _get_or_404(db, classroom_id)
    _assert_can_write(user, classroom.school_id)

    if soft:
        classroom.is_active = False
    else:
        db.delete(classroom)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
