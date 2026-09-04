from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, UniqueConstraint, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class DailySubmissionLog(Base):
    __tablename__ = "daily_submission_logs"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    log_date = Column(Date, nullable=False)
    attendance_submitted = Column(Boolean, default=False)
    submitted_at = Column(DateTime, nullable=True)
    alarm_triggered = Column(Boolean, default=False)
    alarm_raised_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint('school_id', 'log_date', name='uq_daily_submission'),
    )

    school = relationship("PrivateSchool")

class ExamSubmissionEvent(Base):
    __tablename__ = "exam_submission_events"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    exam_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False)  # published, withheld, updated
    performed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("PrivateSchool")
    user = relationship("User")

class CommunicationLog(Base):
    __tablename__ = "communication_logs"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=True)
    type = Column(String, nullable=False)  # Red_Alarm, notification, broadcast
    status = Column(String, default="Pending")  # Pending, Delivered, Failed
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    school = relationship("PrivateSchool")

class SecurityAuditLog(Base):
    __tablename__ = "security_audit_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String, nullable=False)
    resource = Column(String)
    status = Column(String, nullable=False)  # BLOCKED, ALLOWED, DENIED
    details = Column(Text)
    ip_address = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User")

class DataChangeLog(Base):
    __tablename__ = "data_change_log"

    id = Column(Integer, primary_key=True)
    table_name = Column(String, nullable=False)
    record_id = Column(Integer, nullable=False)
    action = Column(String, nullable=False)
    changed_data = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
