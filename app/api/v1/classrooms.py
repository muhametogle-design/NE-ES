"""Explicitly assigned classrooms, also mounted at the legacy /school/classes."""
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_school_manager, require_school_tenant
from app.core.db import get_db
from app.models.academic import SchoolClass, Student, Subject, TeachingAssignment
from app.models.tenancy import AcademicYear, User
from app.schemas.classroom import ClassCreate, ClassResponse, ClassUpdate
from app.schemas.subject import SubjectResponse
from app.services.teacher_scoping import (
    assigned_to, require_class_access, require_course_access, scoped_assignments,
)

router = APIRouter(tags=["classrooms"])


def _validate_year(db: Session, user: User, academic_year_id):
    if academic_year_id is not None and not db.query(AcademicYear).filter_by(
        id=academic_year_id, school_id=user.school_id,
    ).first():
        raise HTTPException(404, "Academic year not found in this school")


def _save(db: Session, classroom: SchoolClass):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(400, "Class with this level and stream already exists") from None
    db.refresh(classroom)
    return classroom


@router.get("", response_model=List[ClassResponse])
def list_classes(user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    query = db.query(SchoolClass).filter(SchoolClass.school_id == user.school_id)
    if user.role == "teacher":
        query = query.filter(assigned_to(user, class_id=SchoolClass.id))
    return query.order_by(SchoolClass.class_level, SchoolClass.stream).all()


@router.post("", response_model=ClassResponse, status_code=201)
def create_class(
    data: ClassCreate, user: User = Depends(require_school_manager), db: Session = Depends(get_db),
):
    _validate_year(db, user, data.academic_year_id)
    classroom = SchoolClass(school_id=user.school_id, **data.model_dump())
    db.add(classroom)
    return _save(db, classroom)


@router.get("/{id}", response_model=ClassResponse)
def get_class(id: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    return require_class_access(db, user, id)


@router.put("/{id}", response_model=ClassResponse)
@router.patch("/{id}", response_model=ClassResponse)
def update_class(
    id: int, data: ClassUpdate,
    user: User = Depends(require_school_tenant), db: Session = Depends(get_db),
):
    classroom = require_class_access(db, user, id)
    _validate_year(db, user, data.academic_year_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(classroom, field, value)
    return _save(db, classroom)


@router.get("/{id}/breakdown")
def class_breakdown(id: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    classroom = require_class_access(db, user, id)
    students = db.query(Student).filter_by(class_id=id, school_id=user.school_id, is_active=True).all()
    assignments = scoped_assignments(db, user).filter(TeachingAssignment.class_id == id).all()
    return {
        "class_id": classroom.id,
        "class_level": classroom.class_level,
        "stream": classroom.stream,
        "total_students": len(students),
        "male_students": sum(s.gender.lower() == "male" for s in students),
        "female_students": sum(s.gender.lower() == "female" for s in students),
        "subjects": [{
            "subject_id": a.subject_id,
            "subject_name": a.subject.name,
            "subject_code": a.subject.code,
            "teacher_id": a.teacher_id,
            "teacher_name": f"{a.teacher.first_name} {a.teacher.last_name}",
        } for a in assignments],
    }


@router.get("/{id}/subjects", response_model=List[SubjectResponse])
def list_class_subjects(id: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db)):
    classroom = require_class_access(db, user, id)
    query = db.query(Subject).filter(Subject.school_id == user.school_id)
    if user.role == "teacher":
        # Not all level-matched subjects, nor the union of a teacher's subjects
        # across other classrooms: only the explicitly assigned pair.
        query = query.filter(assigned_to(user, class_id=id, subject_id=Subject.id))
    else:
        query = query.filter(Subject.level == classroom.class_level)
    return query.order_by(Subject.code).all()


@router.get("/{cid}/subjects/{sid}/assignment")
def get_class_subject_assignment(
    cid: int, sid: int, user: User = Depends(require_school_tenant), db: Session = Depends(get_db),
):
    require_course_access(db, user, cid, sid)
    assignment = scoped_assignments(db, user).filter(
        TeachingAssignment.class_id == cid, TeachingAssignment.subject_id == sid,
    ).first()
    if assignment is None:
        return {"assigned": False, "teacher": None}
    return {
        "assigned": True,
        "teacher_id": assignment.teacher_id,
        "teacher_name": f"{assignment.teacher.first_name} {assignment.teacher.last_name}",
        "email": assignment.teacher.email,
    }
