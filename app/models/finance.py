"""Finance: invoices and payments (billing ledger)."""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"
    partial = "partial"
    paid = "paid"
    overdue = "overdue"
    void = "void"


class FeeType(str, enum.Enum):
    tuition = "tuition"
    registration = "registration"
    examination = "examination"
    transport = "transport"
    meals = "meals"
    library = "library"
    other = "other"


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    invoice_no: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fee_type: Mapped[FeeType] = mapped_column(
        Enum(FeeType, values_callable=lambda e: [m.value for m in e]),
        default=FeeType.tuition,
        nullable=False,
    )
    description: Mapped[Optional[str]] = mapped_column(Text)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    issue_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    due_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, values_callable=lambda e: [m.value for m in e]),
        default=InvoiceStatus.issued,
        nullable=False,
        index=True,
    )
    term: Mapped[Optional[str]] = mapped_column(String(32))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    student: Mapped["Student"] = relationship(  # type: ignore[name-defined] # noqa: F821
        "Student", lazy="joined"
    )
    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Payment.paid_at.desc()",
    )

    @property
    def balance(self) -> Decimal:
        return Decimal(self.amount or 0) - Decimal(self.amount_paid or 0)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Invoice id={self.id} invoice_no={self.invoice_no!r}>"


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    bank_transfer = "bank_transfer"
    card = "card"
    mobile_money = "mobile_money"
    cheque = "cheque"


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    receipt_no: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    invoice_id: Mapped[int] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, values_callable=lambda e: [m.value for m in e]),
        default=PaymentMethod.cash,
        nullable=False,
    )
    reference: Mapped[Optional[str]] = mapped_column(String(128))
    note: Mapped[Optional[str]] = mapped_column(Text)
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    recorded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payments")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Payment id={self.id} receipt_no={self.receipt_no!r}>"
