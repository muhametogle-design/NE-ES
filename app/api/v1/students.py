"""Student CRUD and URL-based photos; shared by canonical and school routes."""
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.api.deps import require_school_tenant
from app.core.db import get_db
from app.models.academic import Student
from app.models.tenancy import PrivateSchool, User
from app.schemas.common import MessageResponse, PaginatedResponse
from app.schemas.student import StudentCreate, StudentResponse, StudentUpdate
from app.services.teacher_scoping import assigned_to, require_class_access
from app.services.tenant_service import TenantService

router = APIRouter(tags=["students"])


def _check_class(db: Session, user: User, class_id):
    if class_id is not None:
        require_class_access(db, user, class_id)
    elif user.role == "teacher":
        raise HTTPException(403, "Not authorized to access students without an assigned class")


def _get_student(db: Session, user: User, ne_sid: str):
    query = db.query(Student).filter(Student.school_id == user.school_id)
    identifiers = [Student.roll_number == ne_sid, Student.national_student_id == ne_sid]
    if ne_sid.isdigit():
        identifiers.append(Student.id == int(ne_sid))
    student = query.filter(or_(*identifiers)).first()
    if student is None:
        raise HTTPException(404, f"Student not found with identifier '{ne_sid}' in this school")
    _check_class(db, user, student.class_id)
    return student


@router.get("", response_model=PaginatedResponse[StudentResponse])
def list_students(
    q: Optional[str] = None,
    class_id: Optional[int] = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    query = db.query(Student).filter(Student.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(assigned_to(user, class_id=Student.class_id))
    if class_id is not None:
        _check_class(db, user, class_id)
        query = query.filter(Student.class_id == class_id)
    if q:
        search = f"%{q}%"
        query = query.filter(or_(
            Student.first_name.ilike(search), Student.last_name.ilike(search),
            Student.roll_number.ilike(search), Student.national_student_id.ilike(search),
        ))
    total = query.count()
    items = query.order_by(Student.roll_number).offset((page - 1) * per_page).limit(per_page).all()
    return {"items": items, "total": total, "page": page, "pages": max(1, math.ceil(total / per_page))}


@router.post("", response_model=StudentResponse, status_code=201)
def create_student(
    student: StudentCreate, user: User = Depends(require_school_tenant), db: Session = Depends(get_db),
):
    _check_class(db, user, student.class_id)
    school = db.query(PrivateSchool).filter(PrivateSchool.id == user.school_id).first()
    if school is None:
        raise HTTPException(404, "School not found")
    next_num = TenantService.get_next_roll_number(db, user.school_id)
    roll_number = f"{school.school_code}-{next_num}"
    db_student = Student(
        school_id=user.school_id, national_student_id=roll_number, roll_number=roll_number,
        is_active=True, **student.model_dump(),
    )
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


@router.get("/{ne_sid}", response_model=StudentResponse)
def get_student(ne_sid: str, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    return _get_student(db, user, ne_sid)


@router.put("/{ne_sid}", response_model=StudentResponse)
@router.patch("/{ne_sid}", response_model=StudentResponse)
def update_student(
    ne_sid: str, update_data: StudentUpdate,
    user: User = Depends(require_school_tenant), db: Session = Depends(get_db),
):
    student = _get_student(db, user, ne_sid)
    # The schema excludes immutable IDs. Omitted photo_url is preserved, while
    # explicit null clears it, for both PATCH and the legacy partial PUT.
    data = update_data.model_dump(exclude_unset=True)
    if "class_id" in data:
        _check_class(db, user, data["class_id"])
    for field, value in data.items():
        setattr(student, field, value)
    db.commit()
    db.refresh(student)
    return student


@router.delete("/{ne_sid}", response_model=MessageResponse)
def delete_student(ne_sid: str, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    student = _get_student(db, user, ne_sid)
    student.is_active = False
    db.commit()
    return {"message": "Student deactivated successfully"}
