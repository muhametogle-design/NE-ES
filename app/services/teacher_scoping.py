"""Shared, fail-closed academic scope checks for canonical and legacy routes.

A User ID is never a Teacher ID. Every teacher permission traverses the active
Teacher.user_id binding, then an explicit class/subject TeachingAssignment.
"""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.academic import SchoolClass, Student, Subject, Teacher, TeachingAssignment
from app.models.tenancy import User


def assigned_to(user: User, *, class_id=None, subject_id=None):
    """Correlated EXISTS, avoiding duplicate list rows and pagination leaks."""
    query = (
        select(TeachingAssignment.id)
        .join(Teacher, Teacher.id == TeachingAssignment.teacher_id)
        .where(
            TeachingAssignment.school_id == user.school_id,
            Teacher.school_id == user.school_id,
            Teacher.user_id == user.id,
            Teacher.is_active.is_(True),
        )
        .correlate_except(TeachingAssignment, Teacher)
    )
    if class_id is not None:
        query = query.where(TeachingAssignment.class_id == class_id)
    if subject_id is not None:
        query = query.where(TeachingAssignment.subject_id == subject_id)
    return query.exists()


def scoped_assignments(db: Session, user: User):
    query = db.query(TeachingAssignment).filter(TeachingAssignment.school_id == user.school_id)
    if user.role == "teacher":
        query = query.join(Teacher).filter(
            Teacher.user_id == user.id,
            Teacher.school_id == user.school_id,
            Teacher.is_active.is_(True),
        )
    return query


def require_class_access(db: Session, user: User, class_id: int) -> SchoolClass:
    classroom = db.query(SchoolClass).filter_by(id=class_id, school_id=user.school_id).first()
    if classroom is None:
        # Foreign tenants remain indistinguishable from missing records.
        raise HTTPException(404, "Class not found")
    if user.role == "teacher" and not db.query(assigned_to(user, class_id=class_id)).scalar():
        raise HTTPException(403, "Not authorized to access this class")
    return classroom


def require_subject_access(db: Session, user: User, subject_id: int) -> Subject:
    subject = db.query(Subject).filter_by(id=subject_id, school_id=user.school_id).first()
    if subject is None:
        raise HTTPException(404, "Subject not found")
    if user.role == "teacher" and not db.query(assigned_to(user, subject_id=subject_id)).scalar():
        raise HTTPException(403, "Not authorized to access this subject")
    return subject


def require_course_access(db: Session, user: User, class_id: int, subject_id: int):
    """Independent class and subject grants must never authorize their cross product."""
    classroom = require_class_access(db, user, class_id)
    subject = require_subject_access(db, user, subject_id)
    if user.role == "teacher" and not db.query(
        assigned_to(user, class_id=class_id, subject_id=subject_id)
    ).scalar():
        raise HTTPException(403, "Not authorized to access this class and subject")
    return classroom, subject


def validate_roster(db: Session, user: User, class_id: int, student_ids):
    """Validate the entire batch before changing anything (including updates).

    The class/subject grant alone is insufficient: a malicious client could put
    students from a different class or school into an otherwise authorized batch.
    """
    ids = set(student_ids)
    if not ids:
        return
    students = db.query(Student).filter(Student.id.in_(ids), Student.school_id == user.school_id).all()
    if len(students) != len(ids):
        raise HTTPException(404, "Student not found in this school")
    if any(student.class_id != class_id for student in students):
        raise HTTPException(
            403 if user.role == "teacher" else 400,
            "All students must belong to the requested class",
        )
