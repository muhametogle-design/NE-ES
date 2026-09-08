"""Classroom endpoints — ``/api/v1/classrooms``.

Access policy mirrors :mod:`app.api.v1.subjects`:

* ``GET`` — school managers see every classroom of their tenant; a
  ``role="teacher"`` caller only sees the classrooms they are assigned to
  (``teaching_assignments`` rows for ``Teacher.user_id == current_user.id``,
  plus classrooms covered by a confirmed substitution).
* ``POST`` / ``PATCH`` / ``DELETE`` — school managers only. A teacher's write
  authority is limited to the academic records of their own classes
  (attendance, grades — enforced by ``AcademicService.check_teacher_authority``),
  never to the classroom record itself.

Another teacher's classroom answers **403**; another tenant's classroom
answers **404**.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_school_manager, require_school_tenant
from app.core.db import get_db
from app.models.academic import SchoolClass, Student, Subject
from app.models.tenancy import User
from app.schemas.classroom import (
    ClassroomCreate, ClassroomDetailResponse, ClassroomUpdate,
)
from app.schemas.common import MessageResponse
from app.schemas.student import StudentResponse
from app.schemas.subject import SubjectResponse
from app.services.classroom_service import ClassroomService
from app.services.subject_service import SubjectService
from app.services.teacher_scope import TeacherScope

router = APIRouter(prefix="/v1/classrooms", tags=["classrooms"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_classroom(db: Session, user: User, class_id: int) -> SchoolClass:
    """Tenant-scoped fetch plus the teacher ownership check."""
    school_class = (
        db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.school_id == user.school_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classroom {class_id} not found in this school",
        )
    return TeacherScope.ensure_class_access(db, user, school_class)


def _ensure_unique_classroom(
    db: Session, school_id: int, class_level: int, stream: str, exclude_id: Optional[int] = None
) -> None:
    query = db.query(SchoolClass.id).filter(
        SchoolClass.school_id == school_id,
        SchoolClass.class_level == class_level,
        SchoolClass.stream == stream,
    )
    if exclude_id is not None:
        query = query.filter(SchoolClass.id != exclude_id)
    if query.first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Classroom '{class_level}{stream}' already exists in this school",
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "",
    response_model=List[ClassroomDetailResponse],
    summary="List classrooms (teacher-scoped)",
)
async def list_classrooms(
    level: Optional[int] = Query(None, ge=1, le=12, description="Filter by class level"),
    stream: Optional[str] = Query(None, min_length=1, max_length=8, description="Filter by stream"),
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    query = db.query(SchoolClass).filter(SchoolClass.school_id == user.school_id)
    # Teachers only receive the classrooms they are assigned to.
    query = TeacherScope.scope_class_query(db, user, query)
    if level is not None:
        query = query.filter(SchoolClass.class_level == level)
    if stream:
        query = query.filter(SchoolClass.stream == stream.strip().upper())

    classes = query.order_by(SchoolClass.class_level, SchoolClass.stream).all()
    return ClassroomService.serialize_many(db, user.school_id, classes)


@router.post(
    "",
    response_model=ClassroomDetailResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create classroom (school managers)",
)
async def create_classroom(
    data: ClassroomCreate,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    stream = data.stream.strip().upper()
    _ensure_unique_classroom(db, user.school_id, data.class_level, stream)

    school_class = SchoolClass(
        school_id=user.school_id,
        class_level=data.class_level,
        stream=stream,
        academic_year_id=data.academic_year_id,
    )
    db.add(school_class)
    try:
        db.commit()
    except IntegrityError:  # pragma: no cover - race with the pre-check above
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Classroom '{data.class_level}{stream}' already exists in this school",
        ) from None
    db.refresh(school_class)
    return ClassroomService.serialize(db, user.school_id, school_class)


@router.get("/{class_id}", response_model=ClassroomDetailResponse, summary="Get classroom")
async def get_classroom(
    class_id: int,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    school_class = _get_classroom(db, user, class_id)
    return ClassroomService.serialize(db, user.school_id, school_class)


@router.patch("/{class_id}", response_model=ClassroomDetailResponse, summary="Update classroom (school managers)")
async def update_classroom(
    class_id: int,
    data: ClassroomUpdate,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    school_class = (
        db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.school_id == user.school_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classroom {class_id} not found in this school",
        )

    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No fields provided for update",
        )
    if "stream" in changes and changes["stream"]:
        changes["stream"] = changes["stream"].strip().upper()

    _ensure_unique_classroom(
        db,
        user.school_id,
        changes.get("class_level", school_class.class_level),
        changes.get("stream", school_class.stream),
        exclude_id=school_class.id,
    )

    for field, value in changes.items():
        setattr(school_class, field, value)
    try:
        db.commit()
    except IntegrityError:  # pragma: no cover - race with the pre-check above
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Classroom level/stream combination already exists in this school",
        ) from None
    db.refresh(school_class)
    return ClassroomService.serialize(db, user.school_id, school_class)


@router.delete("/{class_id}", response_model=MessageResponse, summary="Delete classroom (school managers)")
async def delete_classroom(
    class_id: int,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    school_class = (
        db.query(SchoolClass)
        .filter(SchoolClass.id == class_id, SchoolClass.school_id == user.school_id)
        .first()
    )
    if school_class is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Classroom {class_id} not found in this school",
        )

    enrolled = (
        db.query(Student.id)
        .filter(Student.class_id == school_class.id, Student.is_active.is_(True))
        .count()
    )
    if enrolled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Classroom '{school_class.label}' still has {enrolled} active student(s); "
                "reassign them before deleting"
            ),
        )

    label = school_class.label
    db.delete(school_class)
    db.commit()
    return {"message": f"Classroom '{label}' deleted"}


@router.get(
    "/{class_id}/subjects",
    response_model=List[SubjectResponse],
    summary="Subjects taught in a classroom (teacher-scoped)",
)
async def list_classroom_subjects(
    class_id: int,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    school_class = _get_classroom(db, user, class_id)

    query = db.query(Subject).filter(
        Subject.school_id == user.school_id, Subject.level == school_class.class_level
    )
    query = TeacherScope.scope_subject_query(db, user, query)
    subjects = query.order_by(Subject.code).all()
    return SubjectService.serialize_many(db, subjects)


@router.get(
    "/{class_id}/students",
    response_model=List[StudentResponse],
    summary="Classroom roster (teacher-scoped)",
)
async def list_classroom_students(
    class_id: int,
    include_inactive: bool = Query(False, description="Also return deactivated students"),
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    school_class = _get_classroom(db, user, class_id)

    query = db.query(Student).filter(
        Student.school_id == user.school_id, Student.class_id == school_class.id
    )
    if not include_inactive:
        query = query.filter(Student.is_active.is_(True))
    return query.order_by(Student.roll_number).all()
