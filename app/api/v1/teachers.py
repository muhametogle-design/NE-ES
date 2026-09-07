"""Staff profiles and manager-controlled, optional system account binding."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_school_manager, require_school_tenant
from app.core.db import get_db
from app.models.academic import Teacher
from app.models.tenancy import User
from app.schemas.common import MessageResponse
from app.schemas.teacher import TeacherCreate, TeacherResponse, TeacherUpdate
from app.services import teacher_service

router = APIRouter(tags=["teachers"])


def _get_teacher(db: Session, user: User, teacher_id: int):
    teacher = db.query(Teacher).filter_by(id=teacher_id, school_id=user.school_id).first()
    if teacher is None:
        raise HTTPException(404, "Teacher not found in this school")
    if user.role == "teacher" and (teacher.user_id != user.id or not teacher.is_active):
        raise HTTPException(403, "Not authorized to access this teacher")
    return teacher


@router.get("", response_model=List[TeacherResponse])
def list_teachers(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    query = db.query(Teacher).filter(Teacher.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(Teacher.user_id == user.id, Teacher.is_active.is_(True))
    return query.order_by(Teacher.id).all()


@router.post("", response_model=TeacherResponse, status_code=201)
def create_teacher(
    data: TeacherCreate, user: User = Depends(require_school_manager), db: Session = Depends(get_db),
):
    return teacher_service.create_teacher(db, user.school_id, data)


@router.get("/{id}", response_model=TeacherResponse)
def get_teacher(id: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    return _get_teacher(db, user, id)


@router.put("/{id}", response_model=TeacherResponse)
@router.patch("/{id}", response_model=TeacherResponse)
def update_teacher(
    id: int, data: TeacherUpdate,
    user: User = Depends(require_school_manager), db: Session = Depends(get_db),
):
    return teacher_service.update_teacher(db, _get_teacher(db, user, id), data)


@router.delete("/{id}", response_model=MessageResponse)
def delete_teacher(id: int, user: User = Depends(require_school_manager), db: Session = Depends(get_db)):
    teacher = _get_teacher(db, user, id)
    teacher_service.update_teacher(db, teacher, TeacherUpdate(is_active=False))
    return {"message": "Teacher deactivated successfully"}
