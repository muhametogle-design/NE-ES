"""Tenant-scoped fingerprint endpoints — ``/api/v1/biometrics``.

Managers and teachers have the same school-tenant access as the existing
WebAuthn endpoints. Templates are canonicalized by the request schemas and
matched exactly, within the same format. This is not a fingerprint similarity
matcher: identifying fresh scans requires a compatible ISO/ANSI matcher SDK.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_school_tenant
from app.core.db import get_db
from app.models.academic import Student
from app.models.biometric import StudentBiometric
from app.models.tenancy import User
from app.schemas.biometric import (
    BiometricEnrollRequest,
    BiometricResponse,
    BiometricVerifyRequest,
    BiometricVerifyResponse,
)

router = APIRouter(prefix="/v1/biometrics", tags=["biometrics"])


@router.post(
    "/enroll",
    response_model=BiometricResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Enroll a student fingerprint template",
)
def enroll_biometric(
    data: BiometricEnrollRequest,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter_by(id=data.student_id, school_id=user.school_id).first()
    if student is None:
        # Foreign-tenant IDs and nonexistent IDs are deliberately indistinguishable.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found")

    biometric = StudentBiometric(**data.model_dump())
    db.add(biometric)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        # A concurrent student deletion can invalidate the FK after the lookup.
        # Do not expose SQL parameters (which contain the raw template).
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to enroll template; the student record may have changed",
        ) from None
    db.refresh(biometric)
    return biometric


@router.post(
    "/verify",
    response_model=BiometricVerifyResponse,
    summary="Identify an active student by exact template match (1:N)",
)
def verify_biometric(
    data: BiometricVerifyRequest,
    user: User = Depends(require_school_tenant),
    db: Session = Depends(get_db),
):
    if data.school_id != user.school_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot verify biometrics for another school",
        )

    query = (
        db.query(Student)
        .join(StudentBiometric, StudentBiometric.student_id == Student.id)
        .filter(
            Student.school_id == user.school_id,
            Student.is_active.is_(True),
            StudentBiometric.template_format == data.template_format,
            StudentBiometric.template_data == data.template_data,
        )
    )
    if data.finger_position is not None:
        query = query.filter(StudentBiometric.finger_position == data.finger_position)

    # A student can have several matching enrollments. Never choose an arbitrary
    # identity if the same template has been enrolled for two different students.
    matches = query.distinct().limit(2).all()
    if not matches:
        return BiometricVerifyResponse(verified=False, message="No matching active student found")
    if len(matches) > 1:
        return BiometricVerifyResponse(
            verified=False, message="Template does not uniquely identify an active student"
        )

    student = matches[0]
    return BiometricVerifyResponse(
        verified=True,
        student_id=student.id,
        student_name=f"{student.first_name} {student.last_name}",
        roll_number=student.roll_number,
        message="Exact template match found",
    )
