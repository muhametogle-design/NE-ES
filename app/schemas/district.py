"""Pydantic schemas for the District (Regional Education Office) resource."""
import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# District codes are short, upper-case administrative identifiers (e.g. "SOOL", "TOG-01").
DISTRICT_CODE_PATTERN = r"^[A-Z0-9][A-Z0-9_-]{1,15}$"


def _normalize_code(value: str) -> str:
    return value.strip().upper()


def _strip(value: Optional[str]) -> Optional[str]:
    return value.strip() if isinstance(value, str) else value


class DistrictBase(BaseModel):
    code: str = Field(
        ...,
        min_length=2,
        max_length=16,
        description="Unique district code, normalised to upper-case (e.g. SOOL, TOG-01).",
        examples=["SOOL"],
    )
    name: str = Field(..., min_length=2, max_length=255, examples=["Sool Regional Education Office"])
    region: str = Field(..., min_length=2, max_length=128, examples=["Sool"])
    reo_contact_email: Optional[EmailStr] = Field(None, examples=["reo.sool@education.gov"])
    is_active: bool = True

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, v):
        if isinstance(v, str):
            v = _normalize_code(v)
        return v

    @field_validator("code")
    @classmethod
    def validate_code_pattern(cls, v: str) -> str:
        if not re.fullmatch(DISTRICT_CODE_PATTERN, v):
            raise ValueError(
                "code must be 2-16 characters of letters, digits, '-' or '_' (e.g. SOOL, TOG-01)"
            )
        return v

    @field_validator("name", "region", mode="before")
    @classmethod
    def strip_text(cls, v):
        return _strip(v)


class DistrictCreate(DistrictBase):
    """Payload for ``POST /api/v1/districts``."""


class DistrictUpdate(BaseModel):
    """Partial update payload for ``PATCH /api/v1/districts/{id}`` — all fields optional."""
    code: Optional[str] = Field(None, min_length=2, max_length=16)
    name: Optional[str] = Field(None, min_length=2, max_length=255)
    region: Optional[str] = Field(None, min_length=2, max_length=128)
    reo_contact_email: Optional[EmailStr] = None
    is_active: Optional[bool] = None

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, v):
        if isinstance(v, str):
            v = _normalize_code(v)
        return v

    @field_validator("code")
    @classmethod
    def validate_code_pattern(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(DISTRICT_CODE_PATTERN, v):
            raise ValueError(
                "code must be 2-16 characters of letters, digits, '-' or '_' (e.g. SOOL, TOG-01)"
            )
        return v

    @field_validator("name", "region", mode="before")
    @classmethod
    def strip_text(cls, v):
        return _strip(v)


class DistrictResponse(DistrictBase):
    """District as returned by the API."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    school_count: int = Field(0, description="Number of schools currently assigned to this district.")
    created_at: datetime
    updated_at: datetime
