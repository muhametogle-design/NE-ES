"""Request/response schemas for fingerprint template enrollment and identification."""
import base64
import binascii
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.biometric import FingerPosition

# Fingerprint templates are small binary records, not fingerprint images.
MAX_TEMPLATE_LENGTH = 64 * 1024


class _TemplateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_data: str = Field(
        ...,
        min_length=1,
        max_length=MAX_TEMPLATE_LENGTH,
        repr=False,
        description="Standard Base64-encoded ISO/ANSI template (not an image).",
    )
    template_format: str = Field("ISO_19794_2", min_length=1, max_length=50)

    @field_validator("template_data")
    @classmethod
    def validate_template(cls, value: str) -> str:
        try:
            decoded = base64.b64decode(value, validate=True)
        except (binascii.Error, ValueError):
            raise ValueError("template_data must be valid standard Base64") from None
        if not decoded:
            raise ValueError("template_data must contain a non-empty template")
        # Canonicalize padding bits so exact matching compares template bytes,
        # rather than different Base64 representations of the same bytes.
        return base64.b64encode(decoded).decode("ascii")

    @field_validator("template_format", mode="before")
    @classmethod
    def normalize_format(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class BiometricEnrollRequest(_TemplateRequest):
    student_id: int = Field(..., gt=0, strict=True)
    finger_position: FingerPosition = FingerPosition.RIGHT_INDEX
    quality_score: Optional[int] = Field(None, ge=0, le=100, strict=True)
    device_model: Optional[str] = Field(None, max_length=100)


class BiometricVerifyRequest(_TemplateRequest):
    """1:N lookup: no claimed student ID is needed."""

    school_id: int = Field(..., gt=0, strict=True)
    finger_position: Optional[FingerPosition] = None


class BiometricResponse(BaseModel):
    """Enrollment metadata only; raw templates are sensitive and are not returned."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    student_id: int
    finger_position: FingerPosition
    template_format: str
    quality_score: Optional[int] = None
    device_model: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class BiometricVerifyResponse(BaseModel):
    """Exact-template identification result, not a biometric similarity score."""

    verified: bool
    student_id: Optional[int] = None
    student_name: Optional[str] = None
    roll_number: Optional[str] = None
    message: str
