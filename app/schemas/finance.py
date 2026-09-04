"""Finance schemas: invoices, payments, and ledger summaries."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.finance import FeeType, InvoiceStatus, PaymentMethod

# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
class PaymentCreate(BaseModel):
    invoice_id: int
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    method: PaymentMethod = PaymentMethod.cash
    reference: Optional[str] = Field(default=None, max_length=128)
    note: Optional[str] = None


class PaymentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    receipt_no: str
    invoice_id: int
    amount: Decimal
    method: PaymentMethod
    reference: Optional[str]
    note: Optional[str]
    paid_at: datetime


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------
class InvoiceCreate(BaseModel):
    student_id: int
    fee_type: FeeType = FeeType.tuition
    description: Optional[str] = None
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    issue_date: date = Field(default_factory=date.today)
    due_date: Optional[date] = None
    status: InvoiceStatus = InvoiceStatus.issued
    term: Optional[str] = Field(default=None, max_length=32)


class InvoiceUpdate(BaseModel):
    fee_type: Optional[FeeType] = None
    description: Optional[str] = None
    amount: Optional[Decimal] = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    due_date: Optional[date] = None
    status: Optional[InvoiceStatus] = None
    term: Optional[str] = Field(default=None, max_length=32)


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    invoice_no: str
    student_id: int
    fee_type: FeeType
    description: Optional[str]
    amount: Decimal
    amount_paid: Decimal
    balance: Decimal
    issue_date: date
    due_date: Optional[date]
    status: InvoiceStatus
    term: Optional[str]
    created_at: datetime
    payments: list[PaymentRead] = []

    # Student snapshot fields (populated from the joined relationship)
    student_name: Optional[str] = None
    student_admission_no: Optional[str] = None
    grade: Optional[str] = None


class InvoiceList(BaseModel):
    items: list[InvoiceRead]
    total: int
    page: int
    page_size: int
    pages: int


# ---------------------------------------------------------------------------
# Dashboard / ledger summaries
# ---------------------------------------------------------------------------
class FinanceSummary(BaseModel):
    total_billed: Decimal
    total_collected: Decimal
    total_outstanding: Decimal
    total_overdue: Decimal
    invoices_total: int
    payments_total: int
    collection_rate: float  # 0.0 - 100.0


class MonthlyRevenue(BaseModel):
    month: str  # e.g. "2026-09"
    billed: Decimal
    collected: Decimal
