"""Stored fingerprint templates, separate from the WebAuthn credential models."""
import enum
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class FingerPosition(str, enum.Enum):
    RIGHT_THUMB = "RIGHT_THUMB"
    RIGHT_INDEX = "RIGHT_INDEX"
    LEFT_THUMB = "LEFT_THUMB"
    LEFT_INDEX = "LEFT_INDEX"


class StudentBiometric(Base):
    __tablename__ = "student_biometrics"
    __table_args__ = (sa.PrimaryKeyConstraint("id", name="pk_student_biometrics"),)

    id = sa.Column(sa.Uuid, primary_key=True, default=uuid.uuid4)
    # Match the existing integer students.id on both SQLite and PostgreSQL.
    student_id = sa.Column(
        sa.Integer,
        sa.ForeignKey(
            "students.id", name="fk_student_biometrics_student_id_students", ondelete="CASCADE"
        ),
        index=True,
        nullable=False,
    )
    finger_position = sa.Column(
        sa.Enum(
            FingerPosition,
            name="ck_student_biometrics_finger_position",
            native_enum=False,
            create_constraint=True,
            validate_strings=True,
        ),
        nullable=False,
        default=FingerPosition.RIGHT_INDEX,
        server_default=FingerPosition.RIGHT_INDEX.value,
    )
    # Canonical Base64 ISO/ANSI template; never included in API responses.
    template_data = sa.Column(sa.Text, nullable=False)
    template_format = sa.Column(
        sa.String(50), nullable=False, default="ISO_19794_2", server_default="ISO_19794_2"
    )
    quality_score = sa.Column(sa.Integer, nullable=True)
    device_model = sa.Column(sa.String(100), nullable=True)
    created_at = sa.Column(sa.DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = sa.Column(
        sa.DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    student = relationship("Student", back_populates="biometrics")
