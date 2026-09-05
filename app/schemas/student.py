"""V1 Student schemas."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

GENDER_OPTIONS = ("male", "female")


def _sanitize_name(value: str, field: str) -> str:
    cleaned = " ".join(str(value).strip().split())
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    return cleaned


class StudentBase(BaseModel):
    first_name: str = Field(..., max_length=50)
    last_name: str = Field(..., max_length=50)
    gender: str = Field(..., max_length=10, examples=["male"])
    date_of_birth: Optional[date] = None
    classroom_id: Optional[uuid.UUID] = None
    is_active: bool = True

    @field_validator("first_name")
    @classmethod
    def _v_first(cls, v: str) -> str:
        return _sanitize_name(v, "first_name")

    @field_validator("last_name")
    @classmethod
    def _v_last(cls, v: str) -> str:
        return _sanitize_name(v, "last_name")

    @field_validator("gender")
    @classmethod
    def _v_gender(cls, v: str) -> str:
        normalized = str(v).strip().lower()
        if normalized not in GENDER_OPTIONS:
            raise ValueError(f"gender must be one of {', '.join(GENDER_OPTIONS)}")
        return normalized


class StudentCreate(StudentBase):
    school_id: int
    emis_id: str = Field(..., max_length=30, examples=["NE-2026-0001"])

    @field_validator("emis_id")
    @classmethod
    def _v_emis(cls, v: str) -> str:
        cleaned = str(v).strip()
        if not cleaned:
            raise ValueError("emis_id must not be empty")
        return cleaned


class StudentUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=50)
    last_name: Optional[str] = Field(default=None, max_length=50)
    gender: Optional[str] = Field(default=None, max_length=10)
    date_of_birth: Optional[date] = None
    classroom_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

    @field_validator("first_name")
    @classmethod
    def _v_first(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _sanitize_name(v, "first_name")

    @field_validator("last_name")
    @classmethod
    def _v_last(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _sanitize_name(v, "last_name")

    @field_validator("gender")
    @classmethod
    def _v_gender(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        normalized = str(v).strip().lower()
        if normalized not in GENDER_OPTIONS:
            raise ValueError(f"gender must be one of {', '.join(GENDER_OPTIONS)}")
        return normalized


class StudentResponse(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    emis_id: str
    school_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StudentListResponse(BaseModel):
    items: list[StudentResponse]
    total: int
    page: int
    per_page: int
    pages: int
