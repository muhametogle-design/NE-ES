from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class BiometricCredential(Base):
    __tablename__ = "biometric_credentials"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    credential_id = Column(String, unique=True, nullable=False, index=True)
    public_key = Column(Text, nullable=False)
    sign_count = Column(Integer, default=0, nullable=False)
    transports = Column(String, default="internal")
    created_at = Column(DateTime, server_default=func.now())

    student = relationship("Student", back_populates="biometric_credentials")

class BiometricVerificationLog(Base):
    __tablename__ = "biometric_verification_logs"

    id = Column(Integer, primary_key=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    credential_id = Column(String, nullable=True)
    verification_type = Column(String, nullable=False)  # exam_hall_entry, staff_attendance, daily_gate
    status = Column(String, nullable=False)  # success, failed, rejected
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    student = relationship("Student")
