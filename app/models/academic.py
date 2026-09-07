import uuid

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, UniqueConstraint, Float, Date, Uuid, Text, PrimaryKeyConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class District(Base):
    """Regional Education Office (REO) district.

    Groups private schools by administrative district for state oversight.
    ``Uuid`` is dialect-portable: native ``UUID`` on PostgreSQL, ``CHAR(32)``
    on SQLite (used by the test suite and the zero-config default).
    """
    __tablename__ = "districts"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    code = Column(String(16), unique=True, index=True, nullable=False)  # e.g. SOOL, TOG-01
    name = Column(String(255), nullable=False)
    region = Column(String(128), nullable=False, index=True)
    reo_contact_email = Column(String(255), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    # Schools are never deleted with their district: the FK is ON DELETE SET NULL.
    schools = relationship("PrivateSchool", back_populates="district", order_by="PrivateSchool.school_code")

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<District {self.code} ({self.region})>"

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
    teachers = relationship("Teacher", secondary="teaching_assignments", back_populates="classrooms", viewonly=True)
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
    teachers = relationship("Teacher", secondary="teaching_assignments", back_populates="subjects", viewonly=True)
    timetable_slots = relationship("TimetableSlot", back_populates="subject", cascade="all, delete-orphan")
    grades = relationship("StudentGrade", back_populates="subject", cascade="all, delete-orphan")
    attendance = relationship("SubjectAttendance", back_populates="subject", cascade="all, delete-orphan")

class Teacher(Base):
    """School staff profile; assignments belong to this record, not its login.

    ``users.id`` is INTEGER in the existing schema, so ``user_id`` must use the
    same type on both SQLite and PostgreSQL. Unlinking/deleting a login does not
    delete the teacher or their academic assignments.
    """
    __tablename__ = "teachers"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey(
        "private_schools.id", name="fk_teachers_school_id_private_schools", ondelete="CASCADE"
    ), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey(
        "users.id", name="fk_teachers_user_id_users", ondelete="SET NULL"
    ), nullable=True, index=True)
    photo_url = Column(String(500), nullable=True)
    email = Column(String, nullable=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    staff_identifier = Column(String, nullable=True)
    phone = Column(String, nullable=True)
    qualifications = Column(String, nullable=True)
    designation = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    is_department_head = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())

    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_teachers"),
        UniqueConstraint("user_id", name="uq_teachers_user_id"),
        UniqueConstraint("staff_identifier", name="uq_teachers_staff_identifier"),
    )

    user = relationship("User", back_populates="teacher")
    school = relationship("PrivateSchool", back_populates="teachers")
    assignments = relationship("TeachingAssignment", back_populates="teacher", cascade="all, delete-orphan")
    timetable_slots = relationship("TimetableSlot", back_populates="teacher", cascade="all, delete-orphan")
    absences = relationship("TeacherAbsence", back_populates="teacher", cascade="all, delete-orphan")
    substitutions = relationship("SubstitutionAssignment", back_populates="substitute_teacher", cascade="all, delete-orphan")
    # TeachingAssignment is the single writable source of subject/class scope.
    subjects = relationship("Subject", secondary="teaching_assignments", back_populates="teachers", viewonly=True)
    classrooms = relationship("SchoolClass", secondary="teaching_assignments", back_populates="teachers", viewonly=True)
    students = relationship(
        "Student", secondary="teaching_assignments",
        primaryjoin="Teacher.id == TeachingAssignment.teacher_id",
        secondaryjoin="and_(Student.class_id == TeachingAssignment.class_id, Student.school_id == TeachingAssignment.school_id)",
        back_populates="teachers", viewonly=True,
    )

class TeachingAssignment(Base):
    __tablename__ = "teaching_assignments"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id", name="fk_teaching_assignments_teacher_id_teachers", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('school_id', 'teacher_id', 'class_id', 'subject_id', name='uq_assignment'),
    )

    teacher = relationship("Teacher", back_populates="assignments")
    class_ref = relationship("SchoolClass", back_populates="assignments")
    subject = relationship("Subject", back_populates="assignments")

class TimetableSlot(Base):
    __tablename__ = "timetable_slots"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("teachers.id", name="fk_timetable_slots_teacher_id_teachers", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(Integer, nullable=False)  # 0=Monday .. 6=Sunday
    period = Column(Integer, nullable=False)  # 1-8
    room = Column(String)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('school_id', 'class_id', 'day_of_week', 'period', name='uq_slot_class_time'),
    )

    class_ref = relationship("SchoolClass", back_populates="timetable_slots")
    subject = relationship("Subject", back_populates="timetable_slots")
    teacher = relationship("Teacher", back_populates="timetable_slots")
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
    photo_url = Column(String(500), nullable=True)
    class_id = Column(Integer, ForeignKey("school_classes.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("PrivateSchool", back_populates="students")
    class_ref = relationship("SchoolClass", back_populates="students")
    teachers = relationship(
        "Teacher", secondary="teaching_assignments",
        primaryjoin="and_(Student.class_id == TeachingAssignment.class_id, Student.school_id == TeachingAssignment.school_id)",
        secondaryjoin="Teacher.id == TeachingAssignment.teacher_id",
        back_populates="students", viewonly=True,
    )
    grades = relationship("StudentGrade", back_populates="student", cascade="all, delete-orphan")
    attendance = relationship("SubjectAttendance", back_populates="student", cascade="all, delete-orphan")
    live_attendance = relationship("LiveAttendance", back_populates="student", cascade="all, delete-orphan")
    biometric_credentials = relationship("BiometricCredential", back_populates="student", cascade="all, delete-orphan")
    biometrics = relationship("StudentBiometric", back_populates="student", cascade="all, delete-orphan")
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
