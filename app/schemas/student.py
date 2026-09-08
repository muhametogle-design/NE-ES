"""Student schemas (canonical location).

``app.schemas.school`` re-exports these names, so the legacy
``/api/v1/school/students`` endpoints and anything importing
``app.schemas.student`` share one definition — including the new ``photo_url``
portrait field.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.media import PhotoUrl


class StudentBase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    first_name: str = Field(..., min_length=1, max_length=120)
    last_name: str = Field(..., min_length=1, max_length=120)
    gender: str = Field(..., min_length=1, max_length=32)
    date_of_birth: Optional[date] = None
    class_id: Optional[int] = None
    #: Portrait URL — absolute http(s) or a local ``/media/...`` path.
    photo_url: PhotoUrl = None


class StudentCreate(StudentBase):
    """Payload for ``POST /api/v1/school/students``.

    ``roll_number`` / ``national_student_id`` are deliberately absent: they are
    minted server-side from the immutable school roll sequence.
    """


class StudentUpdate(BaseModel):
    """Partial update; unset fields are left untouched.

    ``photo_url`` may be sent as ``null`` (or an empty string) to remove the
    stored portrait. Roll number and national student ID are immutable: they are
    not part of this schema and, if a client sends them anyway, the router drops
    them (``extra="ignore"``) rather than rejecting the whole request.
    """

    model_config = ConfigDict(extra="ignore")

    first_name: Optional[str] = Field(None, min_length=1, max_length=120)
    last_name: Optional[str] = Field(None, min_length=1, max_length=120)
    gender: Optional[str] = Field(None, min_length=1, max_length=32)
    date_of_birth: Optional[date] = None
    class_id: Optional[int] = None
    is_active: Optional[bool] = None
    photo_url: PhotoUrl = None


class StudentResponse(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    national_student_id: str
    roll_number: str
    is_active: bool
    created_at: Optional[datetime] = None
