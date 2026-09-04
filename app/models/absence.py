from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class TeacherAbsence(Base):
    __tablename__ = "teacher_absences"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False)
    reason = Column(String, nullable=True)
    status = Column(String, default="reported")  # reported, covered, unassigned
    created_at = Column(DateTime, server_default=func.now())

    teacher = relationship("User", back_populates="absences")
    substitutions = relationship("SubstitutionAssignment", back_populates="absence", cascade="all, delete-orphan")

class SubstitutionAssignment(Base):
    __tablename__ = "substitution_assignments"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    absence_id = Column(Integer, ForeignKey("teacher_absences.id", ondelete="CASCADE"), nullable=False)
    substitute_teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    timetable_slot_id = Column(Integer, ForeignKey("timetable_slots.id", ondelete="CASCADE"), nullable=False)
    confirmed = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())

    absence = relationship("TeacherAbsence", back_populates="substitutions")
    substitute_teacher = relationship("User")
    slot = relationship("TimetableSlot", back_populates="substitutions")
