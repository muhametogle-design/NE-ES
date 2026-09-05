"""V1 Student endpoints with pagination, search and tenant isolation."""
from __future__ import annotations

import math
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models.academic import Classroom, Student
from app.models.tenancy import PrivateSchool, User
from app.schemas.student import (
    StudentCreate,
    StudentListResponse,
    StudentResponse,
    StudentUpdate,
)

router = APIRouter(prefix="/students", tags=["students"])

STATE_ROLES = {"state_admin", "inspector"}
SCHOOL_WRITE_ROLES = {"school_admin", "school_manager"}
WRITE_ROLES = {"state_admin"} | SCHOOL_WRITE_ROLES


def _is_state(user: User) -> bool:
    return user.role in STATE_ROLES


def _assert_can_write(user: User, school_id: int) -> None:
    if user.role not in WRITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.role}' cannot modify students",
        )
    if user.role in SCHOOL_WRITE_ROLES and user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant student access denied",
        )


def _assert_can_read(user: User, school_id: int) -> None:
    if _is_state(user):
        return
    if user.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cross-tenant student access denied",
        )


def _get_or_404(db: Session, student_id: uuid.UUID) -> Student:
    student = db.query(Student).filter(Student.id == student_id).first()
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {student_id} not found",
        )
    return student


def _validate_classroom(
    db: Session, classroom_id: uuid.UUID, school_id: int, exclude_student_id=None
) -> Classroom:
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if classroom is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classroom {classroom_id} not found",
        )
    if classroom.school_id != school_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Classroom belongs to a different school",
        )

    occupancy_q = db.query(Student).filter(
        Student.classroom_id == classroom.id, Student.is_active == True  # noqa: E712
    )
    if exclude_student_id is not None:
        occupancy_q = occupancy_q.filter(Student.id != exclude_student_id)
    if occupancy_q.count() >= classroom.capacity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Classroom '{classroom.name}' is at full capacity ({classroom.capacity})",
        )
    return classroom


@router.get("", response_model=StudentListResponse, summary="List students")
def list_students(
    school_id: Optional[int] = Query(None),
    classroom_id: Optional[uuid.UUID] = Query(None),
    is_active: Optional[bool] = Query(None),
    q: Optional[str] = Query(None, description="Search name or EMIS id"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Student)

    if _is_state(user):
        if school_id is not None:
            query = query.filter(Student.school_id == school_id)
    else:
        if not user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not assigned to any school tenant",
            )
        if school_id is not None and school_id != user.school_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cross-tenant student access denied",
            )
        query = query.filter(Student.school_id == user.school_id)

    if classroom_id is not None:
        query = query.filter(Student.classroom_id == classroom_id)
    if is_active is not None:
        query = query.filter(Student.is_active == is_active)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Student.first_name.ilike(like),
                Student.last_name.ilike(like),
                Student.emis_id.ilike(like),
            )
        )

    total = query.count()
    pages = max(1, math.ceil(total / per_page))
    items = (
        query.order_by(Student.emis_id)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
    }


@router.post(
    "",
    response_model=StudentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create student",
)
def create_student(
    payload: StudentCreate,
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

    if payload.classroom_id is not None:
        _validate_classroom(db, payload.classroom_id, payload.school_id)

    if db.query(Student).filter(Student.emis_id == payload.emis_id).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"emis_id '{payload.emis_id}' already exists",
        )

    student = Student(id=uuid.uuid4(), **payload.model_dump())
    db.add(student)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"emis_id '{payload.emis_id}' already exists",
        )
    db.refresh(student)
    return student


@router.get("/{student_id}", response_model=StudentResponse, summary="Get student")
def get_student(
    student_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    student = _get_or_404(db, student_id)
    _assert_can_read(user, student.school_id)
    return student


@router.patch("/{student_id}", response_model=StudentResponse, summary="Update student")
def update_student(
    student_id: uuid.UUID,
    payload: StudentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    student = _get_or_404(db, student_id)
    _assert_can_write(user, student.school_id)

    data = payload.model_dump(exclude_unset=True)
    if data.get("classroom_id") is not None:
        _validate_classroom(
            db, data["classroom_id"], student.school_id, exclude_student_id=student.id
        )

    for field, value in data.items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return student
