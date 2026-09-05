"""Classroom schemas."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _sanitize(value: str, field: str) -> str:
    cleaned = " ".join(str(value).strip().split())
    if not cleaned:
        raise ValueError(f"{field} must not be empty")
    return cleaned


class ClassroomBase(BaseModel):
    name: str = Field(..., max_length=100, examples=["Grade 10-A"])
    grade_level: str = Field(..., max_length=50, examples=["Grade 10"])
    academic_year: str = Field(..., max_length=20, examples=["2025-2026"])
    capacity: int = Field(default=40)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: str) -> str:
        return _sanitize(v, "name")

    @field_validator("grade_level")
    @classmethod
    def _v_grade(cls, v: str) -> str:
        return _sanitize(v, "grade_level")

    @field_validator("academic_year")
    @classmethod
    def _v_year(cls, v: str) -> str:
        return _sanitize(v, "academic_year")

    @field_validator("capacity")
    @classmethod
    def _v_capacity(cls, v: int) -> int:
        if v is None or v <= 0:
            raise ValueError("capacity must be greater than 0")
        return v


class ClassroomCreate(ClassroomBase):
    school_id: int = Field(..., description="Owning private school id")


class ClassroomUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    grade_level: Optional[str] = Field(default=None, max_length=50)
    academic_year: Optional[str] = Field(default=None, max_length=20)
    capacity: Optional[int] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def _v_name(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _sanitize(v, "name")

    @field_validator("grade_level")
    @classmethod
    def _v_grade(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _sanitize(v, "grade_level")

    @field_validator("academic_year")
    @classmethod
    def _v_year(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _sanitize(v, "academic_year")

    @field_validator("capacity")
    @classmethod
    def _v_capacity(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("capacity must be greater than 0")
        return v


class ClassroomResponse(ClassroomBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    school_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
