"""Student directory endpoints: CRUD with search, filters and pagination."""
from __future__ import annotations

import math
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.models.student import Student, StudentStatus
from app.schemas.student_legacy import (
    StudentCreate,
    StudentList,
    StudentRead,
    StudentUpdate,
)

router = APIRouter(prefix="/students", tags=["students"])


def _get_student_or_404(db: Session, student_id: int) -> Student:
    student = db.get(Student, student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {student_id} not found.",
        )
    return student


@router.get("", response_model=StudentList, summary="List students")
def list_students(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None, description="Name, email or admission no."),
    grade: Optional[str] = None,
    status_filter: Optional[StudentStatus] = Query(None, alias="status"),
) -> StudentList:
    filters = []
    if search:
        like = f"%{search.strip()}%"
        filters.append(
            or_(
                func.lower(Student.first_name).like(func.lower(like)),
                func.lower(Student.last_name).like(func.lower(like)),
                func.lower(Student.email).like(func.lower(like)),
                Student.admission_no.ilike(like),
            )
        )
    if grade:
        filters.append(Student.grade == grade)
    if status_filter:
        filters.append(Student.status == status_filter)

    count_stmt = select(func.count()).select_from(Student)
    list_stmt = (
        select(Student)
        .order_by(Student.created_at.desc(), Student.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    for condition in filters:
        count_stmt = count_stmt.where(condition)
        list_stmt = list_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    students = db.scalars(list_stmt).all()

    return StudentList(
        items=[StudentRead.model_validate(s) for s in students],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/grades", summary="Distinct grade values for filter dropdowns")
def list_grades(db: DbSession, current_user: CurrentUser) -> list[str]:
    rows = db.scalars(select(Student.grade).distinct().order_by(Student.grade)).all()
    return list(rows)


@router.get(
    "/{student_id}",
    response_model=StudentRead,
    summary="Fetch a single student",
)
def get_student(
    student_id: int, db: DbSession, current_user: CurrentUser
) -> Student:
    return _get_student_or_404(db, student_id)


@router.post(
    "",
    response_model=StudentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new student",
)
def create_student(
    payload: StudentCreate, db: DbSession, current_user: CurrentUser
) -> Student:
    existing = db.scalar(
        select(Student).where(Student.admission_no == payload.admission_no)
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Admission number {payload.admission_no!r} already exists.",
        )

    student = Student(**payload.model_dump())
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


@router.patch(
    "/{student_id}",
    response_model=StudentRead,
    summary="Update a student record",
)
def update_student(
    student_id: int,
    payload: StudentUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Student:
    student = _get_student_or_404(db, student_id)

    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return student


@router.delete(
    "/{student_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete a student record",
)
def delete_student(
    student_id: int, db: DbSession, current_user: CurrentUser
) -> Response:
    student = _get_student_or_404(db, student_id)
    db.delete(student)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
