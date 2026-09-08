"""Subject- and classroom-level scoping for ``role="teacher"`` accounts.

School managers keep tenant-wide access. Teachers are narrowed to what they are
actually assigned to, resolved from two sources:

``teaching_assignments``
    class-level rows (teacher + class + subject) created by managers — the
    same rows :meth:`AcademicService.check_teacher_authority` already uses for
    attendance and grade entry;
``teacher_subjects``
    subject-level ownership on the staff profile bound through
    ``teachers.user_id`` (:class:`app.models.auth.TeacherSubject`).

Confirmed substitutions additionally grant temporary access to the covered
timetable slot's classroom, which keeps the substitution engine usable.

Reads outside the scope answer **403** (not 404) so a teacher probing another
teacher's subject gets an unambiguous authorization error, while cross-tenant
access stays a 404 because the tenant filter never matches.
"""
from __future__ import annotations

from typing import Optional, Set

from fastapi import HTTPException, status
from sqlalchemy.orm import Query, Session

from app.models.absence import SubstitutionAssignment
from app.models.academic import (
    SchoolClass, Subject, TeachingAssignment, TimetableSlot,
)
from app.models.auth import Teacher, TeacherSubject
from app.models.tenancy import User

MANAGER_ROLES = ("school_manager",)
TEACHER_ROLE = "teacher"


class TeacherScope:
    """Helpers that turn "current user" into "rows this user may touch"."""

    # ------------------------------------------------------------------
    # Role predicates
    # ------------------------------------------------------------------
    @staticmethod
    def is_teacher(user: User) -> bool:
        return user.role == TEACHER_ROLE

    @staticmethod
    def is_manager(user: User) -> bool:
        return user.role in MANAGER_ROLES

    @staticmethod
    def is_restricted(user: User) -> bool:
        """True when the caller's queries must be narrowed to their assignments."""
        return TeacherScope.is_teacher(user)

    # ------------------------------------------------------------------
    # Profile / assignment resolution
    # ------------------------------------------------------------------
    @staticmethod
    def profile_for_user(db: Session, user: User) -> Optional[Teacher]:
        """The staff profile bound to ``user`` (``teachers.user_id``)."""
        if user is None or user.id is None:
            return None
        query = db.query(Teacher).filter(Teacher.user_id == user.id)
        if user.school_id is not None:
            query = query.filter(Teacher.school_id == user.school_id)
        return query.order_by(Teacher.id).first()

    @staticmethod
    def assigned_subject_ids(db: Session, user: User) -> Set[int]:
        """Every subject the user teaches (assignment rows ∪ profile mappings)."""
        if not TeacherScope.is_restricted(user):
            return set()

        rows = (
            db.query(TeachingAssignment.subject_id)
            .filter(
                TeachingAssignment.school_id == user.school_id,
                TeachingAssignment.teacher_id == user.id,
            )
            .distinct()
            .all()
        )
        subject_ids = {row[0] for row in rows if row[0] is not None}

        profile = TeacherScope.profile_for_user(db, user)
        if profile is not None:
            links = (
                db.query(TeacherSubject.subject_id)
                .filter(
                    TeacherSubject.teacher_id == profile.id,
                    TeacherSubject.school_id == user.school_id,
                )
                .distinct()
                .all()
            )
            subject_ids |= {row[0] for row in links if row[0] is not None}
        return subject_ids

    @staticmethod
    def assigned_class_ids(db: Session, user: User) -> Set[int]:
        """Classrooms the user teaches, including confirmed substitutions."""
        if not TeacherScope.is_restricted(user):
            return set()

        rows = (
            db.query(TeachingAssignment.class_id)
            .filter(
                TeachingAssignment.school_id == user.school_id,
                TeachingAssignment.teacher_id == user.id,
            )
            .distinct()
            .all()
        )
        class_ids = {row[0] for row in rows if row[0] is not None}

        covered = (
            db.query(TimetableSlot.class_id)
            .join(
                SubstitutionAssignment,
                SubstitutionAssignment.timetable_slot_id == TimetableSlot.id,
            )
            .filter(
                SubstitutionAssignment.school_id == user.school_id,
                SubstitutionAssignment.substitute_teacher_id == user.id,
                SubstitutionAssignment.confirmed.is_(True),
            )
            .distinct()
            .all()
        )
        class_ids |= {row[0] for row in covered if row[0] is not None}
        return class_ids

    # ------------------------------------------------------------------
    # Query scoping
    # ------------------------------------------------------------------
    @staticmethod
    def scope_subject_query(db: Session, user: User, query: Query) -> Query:
        """Narrow a ``Subject`` query to the caller's assigned subjects."""
        if not TeacherScope.is_restricted(user):
            return query
        subject_ids = sorted(TeacherScope.assigned_subject_ids(db, user))
        if not subject_ids:
            return query.filter(Subject.id.is_(None))
        return query.filter(Subject.id.in_(subject_ids))

    @staticmethod
    def scope_class_query(db: Session, user: User, query: Query) -> Query:
        """Narrow a ``SchoolClass`` query to the caller's assigned classrooms."""
        if not TeacherScope.is_restricted(user):
            return query
        class_ids = sorted(TeacherScope.assigned_class_ids(db, user))
        if not class_ids:
            return query.filter(SchoolClass.id.is_(None))
        return query.filter(SchoolClass.id.in_(class_ids))

    # ------------------------------------------------------------------
    # Single-record guards
    # ------------------------------------------------------------------
    @staticmethod
    def can_access_subject(db: Session, user: User, subject_id: Optional[int]) -> bool:
        if not TeacherScope.is_restricted(user):
            return True
        return subject_id in TeacherScope.assigned_subject_ids(db, user)

    @staticmethod
    def can_access_class(db: Session, user: User, class_id: Optional[int]) -> bool:
        if not TeacherScope.is_restricted(user):
            return True
        return class_id in TeacherScope.assigned_class_ids(db, user)

    @staticmethod
    def ensure_subject_access(db: Session, user: User, subject: Subject) -> Subject:
        """403 when a teacher touches a subject assigned to somebody else."""
        if subject is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found"
            )
        if not TeacherScope.can_access_subject(db, user, subject.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Teachers may only access subjects assigned to them "
                    f"(subject '{subject.code}' belongs to another teacher)"
                ),
            )
        return subject

    @staticmethod
    def ensure_class_access(db: Session, user: User, school_class: SchoolClass) -> SchoolClass:
        """403 when a teacher touches a classroom they do not teach."""
        if school_class is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Classroom not found"
            )
        if not TeacherScope.can_access_class(db, user, school_class.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Teachers may only access classrooms assigned to them "
                    f"({school_class.label} is taught by another teacher)"
                ),
            )
        return school_class

    @staticmethod
    def ensure_subject_write(db: Session, user: User, subject: Subject) -> Subject:
        """Write guard for grades/attendance-adjacent subject mutations."""
        TeacherScope.ensure_subject_access(db, user, subject)
        if not TeacherScope.can_write_subject(db, user, subject):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Teachers may only modify subjects assigned to them "
                    f"(subject '{subject.code}' is read-only for this account)"
                ),
            )
        return subject

    @staticmethod
    def can_write_subject(db: Session, user: User, subject: Optional[Subject]) -> bool:
        """A teacher may edit a subject only if it is mapped to their profile.

        Class-level ``teaching_assignments`` grant read access (they need to see
        the syllabus they teach); mutating the subject record itself — code,
        name, level or its teacher roster — requires subject-level ownership.
        """
        if TeacherScope.is_manager(user):
            return True
        if not TeacherScope.is_teacher(user) or subject is None:
            return False
        profile = TeacherScope.profile_for_user(db, user)
        if profile is None:
            return False
        return (
            db.query(TeacherSubject.id)
            .filter(
                TeacherSubject.teacher_id == profile.id,
                TeacherSubject.subject_id == subject.id,
                TeacherSubject.school_id == user.school_id,
            )
            .first()
            is not None
        )
