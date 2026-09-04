import secrets
import base64
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.academic import Student
from app.models.biometrics import BiometricCredential, BiometricVerificationLog
from app.models.tenancy import User

class BiometricService:
    @staticmethod
    def generate_registration_options(student_id: int) -> Dict[str, Any]:
        challenge = secrets.token_urlsafe(32)
        return {
            "challenge": challenge,
            "rp": {"name": "NE-EMIS Identity & Biometrics", "id": "ne-emis.edu.so"},
            "user": {
                "id": str(student_id),
                "name": f"student-{student_id}",
                "displayName": f"Student #{student_id}",
            },
            "pubKeyCredParams": [{"alg": -7, "type": "public-key"}, {"alg": -257, "type": "public-key"}],
            "authenticatorSelection": {
                "authenticatorAttachment": "platform",
                "userVerification": "required",
            },
            "timeout": 60000,
            "attestation": "none",
        }

    @staticmethod
    def register_credential(
        db: Session,
        school_id: int,
        student_id: int,
        credential_id: str,
        public_key: str,
        transports: Optional[str] = "internal"
    ) -> BiometricCredential:
        student = db.query(Student).filter_by(id=student_id, school_id=school_id).first()
        if not student:
            raise HTTPException(status_code=404, detail="Student not found in this school")

        existing = db.query(BiometricCredential).filter_by(credential_id=credential_id).first()
        if existing:
            existing.public_key = public_key
            existing.sign_count = 0
            cred = existing
        else:
            cred = BiometricCredential(
                student_id=student_id,
                credential_id=credential_id,
                public_key=public_key,
                sign_count=0,
                transports=transports or "internal"
            )
            db.add(cred)

        db.commit()
        db.refresh(cred)
        return cred

    @staticmethod
    def verify_biometric(
        db: Session,
        school_id: int,
        credential_id: str,
        verification_type: str = "exam_hall_entry",
        student_id: Optional[int] = None
    ) -> Dict[str, Any]:
        cred = db.query(BiometricCredential).filter_by(credential_id=credential_id).first()
        
        status = "failed"
        reason = None
        matched_student = None

        if not cred:
            reason = "Unrecognized biometric credential"
        else:
            student = db.query(Student).filter_by(id=cred.student_id, school_id=school_id).first()
            if not student:
                reason = "Credential belongs to student from different school / invalid school tenant"
            elif not student.is_active:
                reason = "Student enrollment status is inactive"
            elif student_id and student.id != student_id:
                reason = f"Credential does not match expected student ID {student_id}"
            else:
                status = "success"
                cred.sign_count += 1
                matched_student = student

        log = BiometricVerificationLog(
            student_id=matched_student.id if matched_student else student_id,
            credential_id=credential_id,
            verification_type=verification_type,
            status=status,
            reason=reason
        )
        db.add(log)
        db.commit()

        return {
            "status": status,
            "success": status == "success",
            "reason": reason,
            "student_id": matched_student.id if matched_student else None,
            "student_name": f"{matched_student.first_name} {matched_student.last_name}" if matched_student else None,
            "roll_number": matched_student.roll_number if matched_student else None,
            "verification_type": verification_type
        }
