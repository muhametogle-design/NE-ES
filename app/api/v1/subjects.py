"""Subject routes, shared by /v1/subjects and /v1/school/subjects."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_school_manager, require_school_tenant
from app.core.db import get_db
from app.models.academic import Subject
from app.models.tenancy import User
from app.schemas.common import MessageResponse
from app.schemas.subject import SubjectCreate, SubjectResponse, SubjectUpdate
from app.services.teacher_scoping import assigned_to, require_subject_access

router = APIRouter(tags=["subjects"])


def _save(db: Session, subject: Subject):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Subject code already exists in this school") from None
    db.refresh(subject)
    return subject


@router.get("", response_model=List[SubjectResponse])
def list_subjects(
    level: Optional[int] = None,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    query = db.query(Subject).filter(Subject.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(assigned_to(user, subject_id=Subject.id))
    if level is not None:
        query = query.filter(Subject.level == level)
    return query.order_by(Subject.level, Subject.code).all()


@router.post("", response_model=SubjectResponse, status_code=201)
def create_subject(
    data: SubjectCreate,
    user: User = Depends(require_school_manager),
    db: Session = Depends(get_db),
):
    subject = Subject(school_id=user.school_id, **data.model_dump())
    db.add(subject)
    return _save(db, subject)


@router.get("/{id}", response_model=SubjectResponse)
def get_subject(id: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    return require_subject_access(db, user, id)


@router.put("/{id}", response_model=SubjectResponse)
@router.patch("/{id}", response_model=SubjectResponse)
def update_subject(
    id: int, data: SubjectUpdate,
    user: User = Depends(require_school_tenant), db: Session = Depends(get_db),
):
    subject = require_subject_access(db, user, id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(subject, field, value)
    return _save(db, subject)


@router.delete("/{id}", response_model=MessageResponse)
def delete_subject(id: int, user: User = Depends(require_school_manager), db: Session = Depends(get_db)):
    subject = require_subject_access(db, user, id)
    db.delete(subject)
    db.commit()
    return {"message": "Subject removed"}
