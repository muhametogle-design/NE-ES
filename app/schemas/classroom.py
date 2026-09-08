"""Classroom (``school_classes``) schemas served by ``/api/v1/classrooms``.

``app.schemas.school`` re-exports ``ClassroomCreate`` / ``ClassroomResponse``
under their historical ``ClassCreate`` / ``ClassResponse`` names so the legacy
``/api/v1/school/classes`` endpoints keep working unchanged.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClassroomBase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    class_level: int = Field(..., ge=1, le=12)
    stream: str = Field(..., min_length=1, max_length=8)
    academic_year_id: Optional[int] = None


class ClassroomCreate(ClassroomBase):
    """Payload for ``POST /api/v1/classrooms`` (school managers only)."""


class ClassroomUpdate(BaseModel):
    """Partial update; ``(school, level, stream)`` must stay unique."""

    model_config = ConfigDict(extra="ignore")

    class_level: Optional[int] = Field(None, ge=1, le=12)
    stream: Optional[str] = Field(None, min_length=1, max_length=8)
    academic_year_id: Optional[int] = None


class ClassroomResponse(ClassroomBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    #: Human label (``Class 5A``) — provided by ``SchoolClass.label``.
    label: Optional[str] = None
    created_at: Optional[datetime] = None


class ClassroomDetailResponse(ClassroomResponse):
    """Classroom with its roster size and teaching staff.

    Populated by ``/api/v1/classrooms``; teacher callers only ever receive the
    classrooms they are assigned to.
    """

    student_count: int = 0
    male_students: int = 0
    female_students: int = 0
    teacher_ids: List[int] = Field(default_factory=list)
    subject_ids: List[int] = Field(default_factory=list)
