import uuid

import sqlalchemy as sa
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Float, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class SchoolClass(Base):
    __tablename__ = "school_classes"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_level = Column(Integer, nullable=False)  # 1-12
    stream = Column(String, nullable=False)  # A, B
    academic_year_id = Column(Integer, ForeignKey("academic_years.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('school_id', 'class_level', 'stream', name='uq_class_stream'),
    )

    school = relationship("PrivateSchool", back_populates="classes")
    students = relationship("Student", back_populates="class_ref", cascade="all, delete-orphan")
    assignments = relationship("TeachingAssignment", back_populates="class_ref", cascade="all, delete-orphan")
    timetable_slots = relationship("TimetableSlot", back_populates="class_ref", cascade="all, delete-orphan")

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    code = Column(String, nullable=False)  # e.g., ENG-02
    name = Column(String, nullable=False)
    level = Column(Integer, nullable=False)  # 1-12
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('school_id', 'code', name='uq_subject_code'),
    )

    assignments = relationship("TeachingAssignment", back_populates="subject", cascade="all, delete-orphan")
    timetable_slots = relationship("TimetableSlot", back_populates="subject", cascade="all, delete-orphan")
    grades = relationship("StudentGrade", back_populates="subject", cascade="all, delete-orphan")
    attendance = relationship("SubjectAttendance", back_populates="subject", cascade="all, delete-orphan")

class TeachingAssignment(Base):
    __tablename__ = "teaching_assignments"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('school_id', 'teacher_id', 'class_id', 'subject_id', name='uq_assignment'),
    )

    teacher = relationship("User", back_populates="teaching_assignments")
    class_ref = relationship("SchoolClass", back_populates="assignments")
    subject = relationship("Subject", back_populates="assignments")

class TimetableSlot(Base):
    __tablename__ = "timetable_slots"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday .. 6=Sunday
    period = Column(Integer, nullable=False)  # 1-8
    room = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('school_id', 'class_id', 'day_of_week', 'period', name='uq_slot_class_time'),
    )

    class_ref = relationship("SchoolClass", back_populates="timetable_slots")
    subject = relationship("Subject", back_populates="timetable_slots")
    teacher = relationship("User")
    live_attendance = relationship("LiveAttendance", back_populates="slot", cascade="all, delete-orphan")
    substitutions = relationship("SubstitutionAssignment", back_populates="slot", cascade="all, delete-orphan")

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    national_student_id = Column(String, unique=True, nullable=False, index=True)
    roll_number = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    gender = Column(String, nullable=False)
    date_of_birth = Column(Date, nullable=True)
    class_id = Column(Integer, ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("PrivateSchool", back_populates="students")
    class_ref = relationship("SchoolClass", back_populates="students")
    grades = relationship("StudentGrade", back_populates="student", cascade="all, delete-orphan")
    attendance = relationship("SubjectAttendance", back_populates="student", cascade="all, delete-orphan")
    live_attendance = relationship("LiveAttendance", back_populates="student", cascade="all, delete-orphan")
    biometric_credentials = relationship("BiometricCredential", back_populates="student", cascade="all, delete-orphan")
    invoices = relationship("StudentInvoice", back_populates="student", cascade="all, delete-orphan")

class StudentGrade(Base):
    __tablename__ = "student_grades"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    term = Column(String, nullable=False)
    score = Column(Float, nullable=False)
    grade = Column(String, nullable=True)
    is_published = Column(Boolean, default=False)
    published_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('school_id', 'student_id', 'subject_id', 'term', name='uq_student_grade_term'),
    )

    student = relationship("Student", back_populates="grades")
    subject = relationship("Subject", back_populates="grades")

class SubjectAttendance(Base):
    __tablename__ = "subject_attendance"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String, nullable=False)  # present, absent, late, excused
    marked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('student_id', 'subject_id', 'date', name='uq_subject_attendance_record'),
    )

    student = relationship("Student", back_populates="attendance")
    subject = relationship("Subject", back_populates="attendance")
    class_ref = relationship("SchoolClass")
    marker = relationship("User")

class LiveAttendance(Base):
    __tablename__ = "live_attendance"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    timetable_slot_id = Column(Integer, ForeignKey("timetable_slots.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    status = Column(String, nullable=False)  # present, absent, late, excused
    marked_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('student_id', 'timetable_slot_id', 'date', name='uq_live_attendance_slot'),
    )

    student = relationship("Student", back_populates="live_attendance")
    slot = relationship("TimetableSlot", back_populates="live_attendance")
    marker = relationship("User")

class Classroom(Base):
    """Physical/administrative classroom grouping (e.g. "Grade 10-A")."""

    __tablename__ = "classrooms"

    id = Column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    # NOTE: private_schools.id is an Integer PK in this codebase, so the FK
    # column must be Integer to remain a valid foreign key reference.
    school_id = Column(
        Integer,
        ForeignKey("private_schools.id", ondelete="CASCADE", name="fk_classrooms_school_id"),
        index=True,
        nullable=False,
    )
    name = Column(String(100), nullable=False)
    grade_level = Column(String(50), nullable=False, index=True)
    academic_year = Column(String(20), nullable=False, index=True)
    capacity = Column(Integer, default=40, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    school = relationship("PrivateSchool", back_populates="classrooms")
