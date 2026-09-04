from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, UniqueConstraint, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base

class TuitionRate(Base):
    __tablename__ = "tuition_rates"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    class_level = Column(Integer, nullable=False)
    term = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('school_id', 'class_level', 'term', name='uq_school_tuition_term'),
    )

class StudentInvoice(Base):
    __tablename__ = "student_invoices"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    invoice_number = Column(String, unique=True, nullable=False, index=True)
    term = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String, default="pending")  # pending, paid, overdue, partially_paid
    due_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    student = relationship("Student", back_populates="invoices")
    payments = relationship("PaymentTransaction", back_populates="invoice", cascade="all, delete-orphan")

class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(Integer, primary_key=True)
    school_id = Column(Integer, ForeignKey("private_schools.id", ondelete="CASCADE"), nullable=False)
    invoice_id = Column(Integer, ForeignKey("student_invoices.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String)  # Cash, Zaad, Sahal, Bank Transfer, EvcPlus
    transaction_reference = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    invoice = relationship("StudentInvoice", back_populates="payments")
