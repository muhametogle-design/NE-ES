from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from datetime import date, datetime
from app.models.finance import TuitionRate, StudentInvoice, PaymentTransaction
from app.models.academic import Student, SchoolClass

class FinanceService:
    @staticmethod
    def list_tuition_rates(db: Session, school_id: int) -> List[TuitionRate]:
        return db.query(TuitionRate).filter(TuitionRate.school_id == school_id).order_by(TuitionRate.class_level).all()

    @staticmethod
    def create_or_update_tuition_rate(db: Session, school_id: int, class_level: int, term: str, amount: float) -> TuitionRate:
        rate = db.query(TuitionRate).filter_by(
            school_id=school_id,
            class_level=class_level,
            term=term
        ).first()
        if rate:
            rate.amount = amount
        else:
            rate = TuitionRate(
                school_id=school_id,
                class_level=class_level,
                term=term,
                amount=amount
            )
            db.add(rate)
        db.commit()
        db.refresh(rate)
        return rate

    @staticmethod
    def list_invoices(db: Session, school_id: int, student_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        query = db.query(StudentInvoice).filter(StudentInvoice.school_id == school_id)
        if student_id:
            query = query.filter(StudentInvoice.student_id == student_id)
        if status:
            query = query.filter(StudentInvoice.status == status)
        
        invoices = query.order_by(StudentInvoice.created_at.desc()).all()
        result = []
        for inv in invoices:
            paid_sum = db.query(func.coalesce(func.sum(PaymentTransaction.amount), 0.0)).filter(
                PaymentTransaction.invoice_id == inv.id
            ).scalar()
            result.append({
                "id": inv.id,
                "school_id": inv.school_id,
                "student_id": inv.student_id,
                "student_name": f"{inv.student.first_name} {inv.student.last_name}" if inv.student else "Unknown",
                "roll_number": inv.student.roll_number if inv.student else "N/A",
                "invoice_number": inv.invoice_number,
                "term": inv.term,
                "amount": inv.amount,
                "status": inv.status,
                "due_date": inv.due_date,
                "created_at": inv.created_at,
                "paid_amount": float(paid_sum),
            })
        return result

    @staticmethod
    def create_invoice(db: Session, school_id: int, student_id: int, term: str, amount: float, due_date: Optional[date] = None) -> StudentInvoice:
        student = db.query(Student).filter_by(id=student_id, school_id=school_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found in this school")

        timestamp = int(datetime.utcnow().timestamp())
        invoice_number = f"INV-{student.roll_number}-{term.replace(' ', '')}-{timestamp % 100000}"
        
        invoice = StudentInvoice(
            school_id=school_id,
            student_id=student_id,
            invoice_number=invoice_number,
            term=term,
            amount=amount,
            status="pending",
            due_date=due_date
        )
        db.add(invoice)
        db.commit()
        db.refresh(invoice)
        return invoice

    @staticmethod
    def generate_class_invoices(db: Session, school_id: int, class_id: int, term: str, due_date: Optional[date] = None) -> List[StudentInvoice]:
        school_class = db.query(SchoolClass).filter_by(id=class_id, school_id=school_id).first()
        if not school_class:
            raise HTTPException(status_code=404, detail="Class not found")

        rate = db.query(TuitionRate).filter_by(
            school_id=school_id,
            class_level=school_class.class_level,
            term=term
        ).first()
        amount = rate.amount if rate else 100.0

        students = db.query(Student).filter_by(class_id=class_id, school_id=school_id, is_active=True).all()
        created_invoices = []
        for s in students:
            # Check existing invoice for this term
            existing = db.query(StudentInvoice).filter_by(
                school_id=school_id,
                student_id=s.id,
                term=term
            ).first()
            if not existing:
                inv = FinanceService.create_invoice(db, school_id, s.id, term, amount, due_date)
                created_invoices.append(inv)
        return created_invoices

    @staticmethod
    def record_payment(db: Session, school_id: int, invoice_id: int, amount: float, payment_method: str, transaction_reference: Optional[str] = None) -> PaymentTransaction:
        invoice = db.query(StudentInvoice).filter_by(id=invoice_id, school_id=school_id).first()
        if not invoice:
            raise HTTPException(status_code=404, detail="Invoice not found in this school")

        payment = PaymentTransaction(
            school_id=school_id,
            invoice_id=invoice_id,
            amount=amount,
            payment_method=payment_method,
            transaction_reference=transaction_reference
        )
        db.add(payment)
        db.flush()

        # Update invoice status
        total_paid = db.query(func.coalesce(func.sum(PaymentTransaction.amount), 0.0)).filter(
            PaymentTransaction.invoice_id == invoice_id
        ).scalar()
        
        if total_paid >= invoice.amount:
            invoice.status = "paid"
        elif total_paid > 0:
            invoice.status = "partially_paid"
        else:
            invoice.status = "pending"

        db.commit()
        db.refresh(payment)
        return payment

    @staticmethod
    def get_finance_summary(db: Session, school_id: int) -> Dict[str, Any]:
        total_invoiced = db.query(func.coalesce(func.sum(StudentInvoice.amount), 0.0)).filter(
            StudentInvoice.school_id == school_id
        ).scalar()

        total_collected = db.query(func.coalesce(func.sum(PaymentTransaction.amount), 0.0)).filter(
            PaymentTransaction.school_id == school_id
        ).scalar()

        invoice_count = db.query(StudentInvoice).filter(StudentInvoice.school_id == school_id).count()
        paid_count = db.query(StudentInvoice).filter(
            StudentInvoice.school_id == school_id,
            StudentInvoice.status == "paid"
        ).count()

        pending_amount = max(0.0, float(total_invoiced) - float(total_collected))

        return {
            "total_invoices": float(total_invoiced),
            "collected_revenue": float(total_collected),
            "pending_amount": float(pending_amount),
            "invoice_count": invoice_count,
            "paid_invoices_count": paid_count
        }
