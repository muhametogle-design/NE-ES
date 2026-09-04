from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class PrivateSchool(Base):
    __tablename__ = "private_schools"

    id = Column(Integer, primary_key=True, index=True)
    state_license_number = Column(String, unique=True, index=True)
    school_code = Column(String(2), unique=True, index=True, nullable=False)
    school_name = Column(String, nullable=False)
    proprietor_name = Column(String)
    contact_phone = Column(String)
    contact_email = Column(String)
    physical_address = Column(String)
    accreditation_status = Column(String, default="Active")

    # Tenant-private billing block (Firewalled from State)
    billing_contact_name = Column(String)
    billing_phone = Column(String)
    billing_email = Column(String)
    billing_address = Column(String)
    billing_notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

    # Relationships
    users = relationship("User", back_populates="school", cascade="all, delete-orphan")
    classes = relationship("SchoolClass", back_populates="school", cascade="all, delete-orphan")
    students = relationship("Student", back_populates="school", cascade="all, delete-orphan")
    roll_sequence = relationship("SchoolRollSequence", back_populates="school", uselist=False, cascade="all, delete-orphan")
    academic_years = relationship("AcademicYear", back_populates="school", cascade="all, delete-orphan")

class SchoolRollSequence(Base):
    __tablename__ = "school_roll_sequences"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False, unique=True)
    next_value = Column(Integer, default=10000, nullable=False)

    school = relationship("PrivateSchool", back_populates="roll_sequence")

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(String, nullable=False)  # state_admin, inspector, school_manager, teacher
    first_name = Column(String)
    last_name = Column(String)
    staff_identifier = Column(String, unique=True, nullable=True, index=True)
    staff_pin_hash = Column(String, nullable=True)
    is_department_head = Column(Boolean, default=False)
    phone = Column(String)
    qualifications = Column(String)
    designation = Column(String)
    bio = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("PrivateSchool", back_populates="users")
    teaching_assignments = relationship("TeachingAssignment", back_populates="teacher")
    absences = relationship("TeacherAbsence", back_populates="teacher")

class AcademicYear(Base):
    __tablename__ = "academic_years"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    year_name = Column(String, nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_current = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("PrivateSchool", back_populates="academic_years")
