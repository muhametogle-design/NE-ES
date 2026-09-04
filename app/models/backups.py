from sqlalchemy import Column, Integer, String, DateTime, Text, BigInteger
from sqlalchemy.sql import func
from app.models.base import Base

class BackupRecord(Base):
    __tablename__ = "backup_records"

    id = Column(Integer, primary_key=True)
    backup_type = Column(String, nullable=False)  # full, delta, snapshot
    file_path = Column(String, nullable=False)
    checksum_sha256 = Column(String, nullable=True)
    checksum_md5 = Column(String, nullable=True)
    file_size_bytes = Column(BigInteger, default=0)
    encryption_algorithm = Column(String, default="AES-256-GCM")
    created_at = Column(DateTime, server_default=func.now())

class BackupAuditEvent(Base):
    __tablename__ = "backup_audit_events"

    id = Column(Integer, primary_key=True)
    backup_id = Column(Integer, nullable=True)
    action = Column(String, nullable=False)  # created, verified, downloaded, failed, pruned
    user_id = Column(Integer, nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
