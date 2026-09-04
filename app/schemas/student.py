"""Student schemas."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.student import Gender, StudentStatus


class StudentBase(BaseModel):
    admission_no: str = Field(..., max_length=32, examples=["NE-2026-001"])
    first_name: str = Field(..., max_length=120)
    last_name: str = Field(..., max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=32)
    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None
    grade: str = Field(..., max_length=32)
    guardian_name: Optional[str] = Field(default=None, max_length=255)
    guardian_phone: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = Field(default=None, max_length=500)
    status: StudentStatus = StudentStatus.active
    enrolled_on: date = Field(default_factory=date.today)


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    first_name: Optional[str] = Field(default=None, max_length=120)
    last_name: Optional[str] = Field(default=None, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=32)
    gender: Optional[Gender] = None
    date_of_birth: Optional[date] = None
    grade: Optional[str] = Field(default=None, max_length=32)
    guardian_name: Optional[str] = Field(default=None, max_length=255)
    guardian_phone: Optional[str] = Field(default=None, max_length=32)
    address: Optional[str] = Field(default=None, max_length=500)
    status: Optional[StudentStatus] = None


class StudentRead(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class StudentList(BaseModel):
    """Paginated student directory response."""

    items: list[StudentRead]
    total: int
    page: int
    page_size: int
    pages: int
