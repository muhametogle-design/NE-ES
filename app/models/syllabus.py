from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Date, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class SyllabusPlan(Base):
    __tablename__ = "syllabus_plans"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("school_classes.id", ondelete="CASCADE"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    total_units = Column(Integer, default=10, nullable=False)
    midterm_target = Column(Float, default=50.0, nullable=False)
    final_target = Column(Float, default=100.0, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('school_id', 'class_id', 'subject_id', name='uq_syllabus_plan_class_subject'),
    )

    topics = relationship("SyllabusTopic", back_populates="plan", cascade="all, delete-orphan")
    class_ref = relationship("SchoolClass")
    subject = relationship("Subject")

class SyllabusTopic(Base):
    __tablename__ = "syllabus_topics"

    id = Column(Integer, primary_key=True)
    plan_id = Column(Integer, ForeignKey("syllabus_plans.id", ondelete="CASCADE"), nullable=False)
    unit_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    planned_completion_date = Column(Date, nullable=True)

    plan = relationship("SyllabusPlan", back_populates="topics")
    progress_entries = relationship("SyllabusProgressEntry", back_populates="topic", cascade="all, delete-orphan")

class SyllabusProgressEntry(Base):
    __tablename__ = "syllabus_progress_entries"

    id = Column(Integer, primary_key=True)
    topic_id = Column(Integer, ForeignKey("syllabus_topics.id", ondelete="CASCADE"), nullable=False)
    teacher_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    date_covered = Column(Date, nullable=False)
    notes = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    topic = relationship("SyllabusTopic", back_populates="progress_entries")
    teacher = relationship("User")
