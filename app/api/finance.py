"""Finance endpoints: billing ledger — invoices, payments, and summaries."""
from __future__ import annotations

import math
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser, DbSession
from app.models.finance import (
    FeeType,
    Invoice,
    InvoiceStatus,
    Payment,
    PaymentMethod,
)
from app.models.student import Student
from app.schemas.finance import (
    FinanceSummary,
    InvoiceCreate,
    InvoiceList,
    InvoiceRead,
    InvoiceUpdate,
    MonthlyRevenue,
    PaymentCreate,
    PaymentRead,
)

router = APIRouter(prefix="/finance", tags=["finance"])

MONEY = Decimal("0.01")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _generate_invoice_no(db: Session) -> str:
    year = date.today().year
    prefix = f"INV-{year}-"
    last = db.scalar(
        select(Invoice.invoice_no)
        .where(Invoice.invoice_no.like(f"{prefix}%"))
        .order_by(Invoice.invoice_no.desc())
    )
    seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def _generate_receipt_no(db: Session) -> str:
    year = date.today().year
    prefix = f"RCP-{year}-"
    last = db.scalar(
        select(Payment.receipt_no)
        .where(Payment.receipt_no.like(f"{prefix}%"))
        .order_by(Payment.receipt_no.desc())
    )
    seq = int(last.split("-")[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def _get_invoice_or_404(db: Session, invoice_id: int) -> Invoice:
    invoice = db.get(Invoice, invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice {invoice_id} not found.",
        )
    return invoice


def _serialize_invoice(invoice: Invoice) -> InvoiceRead:
    data = InvoiceRead.model_validate(invoice)
    data.student_name = invoice.student.full_name if invoice.student else None
    data.student_admission_no = (
        invoice.student.admission_no if invoice.student else None
    )
    data.grade = invoice.student.grade if invoice.student else None
    return data


def _refresh_invoice_status(invoice: Invoice) -> None:
    """Derive paid/partial status from amount_paid vs amount."""
    if invoice.status == InvoiceStatus.void:
        return
    paid = Decimal(invoice.amount_paid or 0)
    total = Decimal(invoice.amount or 0)
    if paid >= total and total > 0:
        invoice.status = InvoiceStatus.paid
    elif paid > 0:
        invoice.status = InvoiceStatus.partial
    else:
        # Unpaid: flag overdue when past due date, otherwise keep issued.
        if (
            invoice.due_date is not None
            and invoice.due_date < date.today()
        ):
            invoice.status = InvoiceStatus.overdue
        elif invoice.status not in (InvoiceStatus.draft,):
            invoice.status = InvoiceStatus.issued


# ---------------------------------------------------------------------------
# Dashboard summary
# ---------------------------------------------------------------------------
@router.get("/summary", response_model=FinanceSummary, summary="Billing KPIs")
def finance_summary(db: DbSession, current_user: CurrentUser) -> FinanceSummary:
    total_billed = db.scalar(
        select(func.coalesce(func.sum(Invoice.amount), 0)).where(
            Invoice.status != InvoiceStatus.void
        )
    ) or Decimal("0")
    total_collected = db.scalar(
        select(func.coalesce(func.sum(Payment.amount), 0))
    ) or Decimal("0")

    outstanding_stmt = select(
        func.coalesce(
            func.sum(Invoice.amount - Invoice.amount_paid),
            0,
        )
    ).where(Invoice.status.in_([InvoiceStatus.issued, InvoiceStatus.partial, InvoiceStatus.overdue]))
    total_outstanding = db.scalar(outstanding_stmt) or Decimal("0")

    overdue_stmt = select(
        func.coalesce(func.sum(Invoice.amount - Invoice.amount_paid), 0)
    ).where(Invoice.status == InvoiceStatus.overdue)
    total_overdue = db.scalar(overdue_stmt) or Decimal("0")

    invoices_total = db.scalar(
        select(func.count()).select_from(Invoice)
    ) or 0
    payments_total = db.scalar(
        select(func.count()).select_from(Payment)
    ) or 0

    collection_rate = (
        float((total_collected / total_billed) * 100)
        if total_billed > 0
        else 0.0
    )

    return FinanceSummary(
        total_billed=Decimal(total_billed).quantize(MONEY),
        total_collected=Decimal(total_collected).quantize(MONEY),
        total_outstanding=Decimal(total_outstanding).quantize(MONEY),
        total_overdue=Decimal(total_overdue).quantize(MONEY),
        invoices_total=invoices_total,
        payments_total=payments_total,
        collection_rate=round(collection_rate, 2),
    )


@router.get(
    "/revenue/monthly",
    response_model=list[MonthlyRevenue],
    summary="Monthly billed vs collected (last 6 months)",
)
def monthly_revenue(db: DbSession, current_user: CurrentUser) -> list[MonthlyRevenue]:
    """Aggregate invoices/payments by calendar month for charting."""
    months: list[MonthlyRevenue] = []
    today = date.today()
    for i in range(5, -1, -1):
        first = (today.replace(day=1) - _month_delta(i))
        last = _month_end(first)
        label = first.strftime("%Y-%m")

        billed = db.scalar(
            select(func.coalesce(func.sum(Invoice.amount), 0)).where(
                Invoice.issue_date >= first,
                Invoice.issue_date <= last,
                Invoice.status != InvoiceStatus.void,
            )
        ) or Decimal("0")
        collected = db.scalar(
            select(func.coalesce(func.sum(Payment.amount), 0)).where(
                Payment.paid_at >= datetime(first.year, first.month, 1, tzinfo=timezone.utc),
                Payment.paid_at <= datetime(last.year, last.month, last.day, 23, 59, 59, tzinfo=timezone.utc),
            )
        ) or Decimal("0")

        months.append(
            MonthlyRevenue(
                month=label,
                billed=Decimal(billed).quantize(MONEY),
                collected=Decimal(collected).quantize(MONEY),
            )
        )
    return months


def _month_delta(months: int) -> "timedelta":  # type: ignore[name-defined]
    from datetime import timedelta

    # Approximate 30.44 days/month; used only for the rolling window boundary.
    return timedelta(days=int(months * 30.44))


def _month_end(first: date) -> date:
    if first.month == 12:
        return date(first.year, 12, 31)
    nxt = date(first.year, first.month + 1, 1)
    return nxt.fromordinal(nxt.toordinal() - 1)


# ---------------------------------------------------------------------------
# Invoices
# ---------------------------------------------------------------------------
@router.get("/invoices", response_model=InvoiceList, summary="List invoices")
def list_invoices(
    db: DbSession,
    current_user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status_filter: Optional[InvoiceStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None, description="Invoice no. or student name"),
) -> InvoiceList:
    stmt = select(Invoice)
    count_stmt = select(func.count()).select_from(Invoice)

    if status_filter:
        stmt = stmt.where(Invoice.status == status_filter)
        count_stmt = count_stmt.where(Invoice.status == status_filter)

    if search:
        like = f"%{search.strip()}%"
        student_ids = select(Student.id).where(
            (Student.first_name.ilike(like))
            | (Student.last_name.ilike(like))
            | (Student.admission_no.ilike(like))
        )
        condition = (
            Invoice.invoice_no.ilike(like)
            | Invoice.student_id.in_(student_ids)
        )
        stmt = stmt.where(condition)
        count_stmt = count_stmt.where(condition)

    total = db.scalar(count_stmt) or 0
    invoices = db.scalars(
        stmt.order_by(Invoice.created_at.desc(), Invoice.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return InvoiceList(
        items=[_serialize_invoice(i) for i in invoices],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.post(
    "/invoices",
    response_model=InvoiceRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create an invoice",
)
def create_invoice(
    payload: InvoiceCreate, db: DbSession, current_user: CurrentUser
) -> InvoiceRead:
    student = db.get(Student, payload.student_id)
    if student is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {payload.student_id} not found.",
        )

    invoice = Invoice(
        invoice_no=_generate_invoice_no(db),
        **payload.model_dump(),
    )
    _refresh_invoice_status(invoice)
    db.add(invoice)
    db.commit()
    db.refresh(invoice)
    return _serialize_invoice(invoice)


@router.get(
    "/invoices/{invoice_id}",
    response_model=InvoiceRead,
    summary="Fetch a single invoice with payments",
)
def get_invoice(
    invoice_id: int, db: DbSession, current_user: CurrentUser
) -> InvoiceRead:
    return _serialize_invoice(_get_invoice_or_404(db, invoice_id))


@router.patch(
    "/invoices/{invoice_id}",
    response_model=InvoiceRead,
    summary="Update an invoice",
)
def update_invoice(
    invoice_id: int,
    payload: InvoiceUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> InvoiceRead:
    invoice = _get_invoice_or_404(db, invoice_id)
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(invoice, field, value)
    _refresh_invoice_status(invoice)
    db.commit()
    db.refresh(invoice)
    return _serialize_invoice(invoice)


@router.delete(
    "/invoices/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Void/delete an invoice",
)
def delete_invoice(
    invoice_id: int, db: DbSession, current_user: CurrentUser
) -> Response:
    invoice = _get_invoice_or_404(db, invoice_id)
    db.delete(invoice)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Payments
# ---------------------------------------------------------------------------
@router.post(
    "/payments",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record a payment against an invoice",
)
def record_payment(
    payload: PaymentCreate, db: DbSession, current_user: CurrentUser
) -> PaymentRead:
    invoice = _get_invoice_or_404(db, payload.invoice_id)

    if invoice.status == InvoiceStatus.void:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot record a payment against a void invoice.",
        )

    new_balance = invoice.balance - payload.amount
    if new_balance < -Decimal("0.01"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Overpayment: invoice balance is "
                f"{invoice.balance.quantize(MONEY)}, payment of "
                f"{payload.amount.quantize(MONEY)} exceeds it."
            ),
        )

    payment = Payment(
        receipt_no=_generate_receipt_no(db),
        invoice_id=invoice.id,
        amount=payload.amount,
        method=payload.method,
        reference=payload.reference,
        note=payload.note,
        recorded_by=current_user.id,
    )
    invoice.amount_paid = Decimal(invoice.amount_paid or 0) + payload.amount
    _refresh_invoice_status(invoice)

    db.add(payment)
    db.commit()
    db.refresh(payment)
    return PaymentRead.model_validate(payment)


@router.get(
    "/payments",
    response_model=list[PaymentRead],
    summary="Recent payments (ledger activity)",
)
def list_payments(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(20, ge=1, le=200),
) -> list[PaymentRead]:
    payments = db.scalars(
        select(Payment).order_by(Payment.paid_at.desc(), Payment.id.desc()).limit(limit)
    ).all()
    return [PaymentRead.model_validate(p) for p in payments]


# Enums exposed for the frontend dropdowns
@router.get("/meta/enums", summary="Enum lookup for finance forms")
def finance_enums(current_user: CurrentUser) -> dict:
    return {
        "fee_types": [e.value for e in FeeType],
        "invoice_statuses": [s.value for s in InvoiceStatus],
        "payment_methods": [m.value for m in PaymentMethod],
    }
