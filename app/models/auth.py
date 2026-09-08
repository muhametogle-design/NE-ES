"""Teacher / staff identity models.

NE-EMIS authenticates everybody through the single ``users`` table
(:class:`app.models.tenancy.User`), where a teacher is a ``User`` row with
``role="teacher"``.  This module adds the *staff profile* layer on top of that
login account:

``teachers``
    One row per member of teaching staff.  ``teachers.user_id`` binds the
    profile to its system user account.  The foreign key is
    ``ON DELETE SET NULL`` so a staff record — with its photo and subject
    mappings — survives the removal of the login it was issued from, and a
    profile may exist *before* an account is provisioned (``user_id`` NULL) and
    be linked later.

``teacher_subjects``
    Subject-level assignment (many-to-many ``teachers`` ↔ ``subjects``).  It
    answers "which subjects is this teacher responsible for?" and is the
    coarser companion of ``teaching_assignments`` (teacher + class + subject),
    which keeps driving per-class attendance/grade authority.

Constraint and index names are explicit (``pk_``/``fk_``/``uq_``/``ix_``) so
Alembic emits identical DDL on SQLite and PostgreSQL — the convention already
used by :mod:`app.models.biometric`.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Teacher(Base):
    """Staff profile for a member of teaching staff.

    ``user_id`` is the (optional) binding to the login account; ``photo_url``
    stores the location of the portrait — either an absolute ``https://`` URL
    or a local ``/media/...`` path produced by ``POST /api/v1/media/upload``.
    """

    __tablename__ = "teachers"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_teachers"),
        sa.UniqueConstraint("staff_identifier", name="uq_teachers_staff_identifier"),
        sa.UniqueConstraint("school_id", "email", name="uq_teachers_school_email"),
    )

    id = sa.Column(sa.Integer, primary_key=True)
    school_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            "private_schools.id", name="fk_teachers_school_id_private_schools", ondelete="CASCADE"
        ),
        nullable=False,
        index=True,
    )
    # Direct binding to the system user account. SET NULL keeps the staff
    # record (and its photo / subject mappings) when the login is deleted.
    user_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("users.id", name="fk_teachers_user_id_users", ondelete="SET NULL"),
        nullable=True,
        index=True,
        unique=True,
    )
    staff_identifier = sa.Column(sa.String(64), nullable=True)
    first_name = sa.Column(sa.String, nullable=False)
    last_name = sa.Column(sa.String, nullable=False)
    email = sa.Column(sa.String, nullable=True)
    phone = sa.Column(sa.String, nullable=True)
    designation = sa.Column(sa.String, nullable=True)
    qualifications = sa.Column(sa.String, nullable=True)
    bio = sa.Column(sa.Text, nullable=True)
    # Portrait location: an absolute https:// URL or a local /media/... path
    # returned by POST /api/v1/media/upload. The 500-character bound is
    # enforced by the API schemas (SQLite ignores VARCHAR lengths).
    photo_url = sa.Column(sa.String(500), nullable=True)
    is_department_head = sa.Column(sa.Boolean, nullable=False, default=False)
    is_active = sa.Column(sa.Boolean, nullable=False, default=True)
    created_at = sa.Column(sa.DateTime, nullable=False, server_default=func.now())
    updated_at = sa.Column(
        sa.DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # --- relationships -------------------------------------------------
    school = relationship("PrivateSchool", back_populates="teachers")
    # One profile per account (uselist=False); no cascade — deleting the user
    # must NULL the binding, not destroy the staff record.
    user = relationship("User", back_populates="teacher_profile")

    #: Subject-level assignments (managed explicitly through ``TeacherSubject``
    #: rows so ``school_id``/``is_primary`` metadata is never lost).
    subject_links = relationship(
        "TeacherSubject", back_populates="teacher", cascade="all, delete-orphan"
    )
    #: Read-only convenience view over ``subject_links``.
    subjects = relationship("Subject", secondary="teacher_subjects", viewonly=True)

    #: Class-level assignments already recorded against the bound account.
    #: ``teaching_assignments.teacher_id`` points at ``users.id``, hence the
    #: join through ``user_id`` (viewonly: never written through this alias).
    teaching_assignments = relationship(
        "TeachingAssignment",
        primaryjoin="foreign(TeachingAssignment.teacher_id) == Teacher.user_id",
        viewonly=True,
    )
    classes = relationship(
        "SchoolClass",
        secondary="teaching_assignments",
        primaryjoin="Teacher.user_id == foreign(TeachingAssignment.teacher_id)",
        secondaryjoin="SchoolClass.id == foreign(TeachingAssignment.class_id)",
        viewonly=True,
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Teacher {self.id} {self.full_name} user_id={self.user_id}>"


class TeacherSubject(Base):
    """Association row binding a staff profile to a subject they may teach."""

    __tablename__ = "teacher_subjects"
    __table_args__ = (
        sa.PrimaryKeyConstraint("id", name="pk_teacher_subjects"),
        sa.UniqueConstraint("teacher_id", "subject_id", name="uq_teacher_subject"),
    )

    id = sa.Column(sa.Integer, primary_key=True)
    teacher_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("teachers.id", name="fk_teacher_subjects_teacher_id_teachers", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject_id = sa.Column(
        sa.Integer,
        sa.ForeignKey("subjects.id", name="fk_teacher_subjects_subject_id_subjects", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Denormalised for tenant scoping, mirroring every other academic table.
    school_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            "private_schools.id",
            name="fk_teacher_subjects_school_id_private_schools",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    #: Lead teacher for the subject (department ownership).
    is_primary = sa.Column(sa.Boolean, nullable=False, default=False)
    created_at = sa.Column(sa.DateTime, nullable=False, server_default=func.now())

    teacher = relationship("Teacher", back_populates="subject_links")
    subject = relationship("Subject", back_populates="teacher_links")
    school = relationship("PrivateSchool")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<TeacherSubject teacher_id={self.teacher_id} subject_id={self.subject_id}>"
