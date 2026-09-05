import os
import json
import hashlib
import shutil
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.backups import BackupRecord, BackupAuditEvent
from app.models.tenancy import PrivateSchool, User
from app.models.academic import Student

class BackupService:
    @staticmethod
    def _get_encryption_key() -> bytes:
        raw_key = settings.BACKUP_ENCRYPTION_KEY or settings.JWT_SECRET_KEY
        return hashlib.sha256(raw_key.encode("utf-8")).digest()

    @staticmethod
    def create_encrypted_backup(
        db: Session,
        backup_type: str = "full",
        user_id: Optional[int] = None
    ) -> BackupRecord:
        os.makedirs(settings.BACKUP_DIR, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        
        # Prepare payload: snapshot of core tables as structured JSON export
        payload = {
            "version": "1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "backup_type": backup_type,
            "schools": [
                {
                    "id": s.id,
                    "code": s.school_code,
                    "name": s.school_name,
                    "license": s.state_license_number,
                    "proprietor": s.proprietor_name
                } for s in db.query(PrivateSchool).all()
            ],
            "students": [
                {
                    "id": str(st.id),
                    "school_id": st.school_id,
                    "roll_number": st.roll_number,
                    "first_name": st.first_name,
                    "last_name": st.last_name,
                    "gender": st.gender,
                    "class_id": st.class_id
                } for st in db.query(Student).all()
            ],
            "users": [
                {
                    "id": u.id,
                    "email": u.email,
                    "role": u.role,
                    "school_id": u.school_id,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "staff_identifier": u.staff_identifier
                } for u in db.query(User).all()
            ]
        }
        
        data_bytes = json.dumps(payload, default=str).encode("utf-8")
        
        # Encrypt with AES-256-GCM
        key = BackupService._get_encryption_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        encrypted_data = nonce + aesgcm.encrypt(nonce, data_bytes, None)

        filename = f"backup_{backup_type}_{timestamp}.enc"
        file_path = os.path.join(settings.BACKUP_DIR, filename)

        with open(file_path, "wb") as f:
            f.write(encrypted_data)

        sha256_hash = hashlib.sha256(encrypted_data).hexdigest()
        md5_hash = hashlib.md5(encrypted_data).hexdigest()
        file_size = len(encrypted_data)

        record = BackupRecord(
            backup_type=backup_type,
            file_path=file_path,
            checksum_sha256=sha256_hash,
            checksum_md5=md5_hash,
            file_size_bytes=file_size,
            encryption_algorithm="AES-256-GCM"
        )
        db.add(record)
        db.flush()

        audit = BackupAuditEvent(
            backup_id=record.id,
            action="created",
            user_id=user_id,
            details=f"Backup {filename} generated successfully ({file_size} bytes, sha256={sha256_hash[:8]}...)"
        )
        db.add(audit)
        db.commit()
        db.refresh(record)

        # Retention cleanup
        BackupService.prune_old_backups(db)

        return record

    @staticmethod
    def verify_backup(db: Session, backup_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        record = db.query(BackupRecord).filter_by(id=backup_id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Backup record not found")

        if not os.path.exists(record.file_path):
            audit = BackupAuditEvent(
                backup_id=backup_id,
                action="failed",
                user_id=user_id,
                details=f"Backup file missing at {record.file_path}"
            )
            db.add(audit)
            db.commit()
            return {"valid": False, "reason": "Backup file missing on disk"}

        try:
            with open(record.file_path, "rb") as f:
                content = f.read()

            # Verify checksums
            curr_sha = hashlib.sha256(content).hexdigest()
            if record.checksum_sha256 and curr_sha != record.checksum_sha256:
                raise ValueError("SHA-256 checksum mismatch")

            # Verify AES-256-GCM decryption
            nonce = content[:12]
            ciphertext = content[12:]
            key = BackupService._get_encryption_key()
            aesgcm = AESGCM(key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            parsed = json.loads(decrypted.decode("utf-8"))

            audit = BackupAuditEvent(
                backup_id=backup_id,
                action="verified",
                user_id=user_id,
                details=f"Decryption and integrity check passed. Extracted {len(parsed.get('students', []))} students."
            )
            db.add(audit)
            db.commit()

            return {
                "valid": True,
                "record_id": backup_id,
                "checksum_sha256": curr_sha,
                "item_counts": {
                    "schools": len(parsed.get("schools", [])),
                    "students": len(parsed.get("students", [])),
                    "users": len(parsed.get("users", []))
                }
            }
        except Exception as e:
            audit = BackupAuditEvent(
                backup_id=backup_id,
                action="failed",
                user_id=user_id,
                details=f"Verification error: {str(e)}"
            )
            db.add(audit)
            db.commit()
            return {"valid": False, "reason": str(e)}

    @staticmethod
    def prune_old_backups(db: Session):
        cutoff = datetime.utcnow() - timedelta(days=settings.BACKUP_RETENTION_DAYS)
        old_records = db.query(BackupRecord).filter(BackupRecord.created_at < cutoff).all()
        for rec in old_records:
            try:
                if os.path.exists(rec.file_path):
                    os.remove(rec.file_path)
            except Exception:
                pass
            audit = BackupAuditEvent(
                backup_id=rec.id,
                action="pruned",
                details=f"Pruned backup older than {settings.BACKUP_RETENTION_DAYS} days"
            )
            db.add(audit)
            db.delete(rec)
        db.commit()
