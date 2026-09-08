"""Subject schemas (canonical location), including teacher ownership.

A subject belongs to a school tenant and is taught by one or more members of
staff.  Two mappings exist and both are surfaced here:

``teacher_ids`` / ``assigned_teachers``
    Subject-level ownership from ``teacher_subjects``
    (:class:`app.models.auth.TeacherSubject`).
``assignment_count``
    Class-level rows in ``teaching_assignments`` (teacher + class + subject).

Teacher-scoped reads (``/api/v1/subjects``) use these mappings to decide what a
``role="teacher"`` account may see and edit.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class SubjectTeacherSummary(BaseModel):
    """Compact teacher reference embedded in subject payloads."""

    model_config = ConfigDict(from_attributes=True)

    teacher_id: int
    user_id: Optional[int] = None
    full_name: Optional[str] = None
    photo_url: Optional[str] = None
    is_primary: bool = False


class SubjectBrief(BaseModel):
    """Minimal subject reference embedded in teacher payloads."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    level: int
    #: Whether this teacher is the department lead for the subject.
    is_primary: bool = False


class SubjectBase(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str = Field(..., min_length=1, max_length=32)
    name: str = Field(..., min_length=1, max_length=160)
    level: int = Field(..., ge=1, le=12)


class SubjectCreate(SubjectBase):
    """Payload for ``POST /api/v1/subjects`` (school managers only)."""

    #: Optionally bind the subject to existing staff profiles on creation.
    teacher_ids: List[int] = Field(default_factory=list)


class SubjectUpdate(BaseModel):
    """Partial update; only sent fields change."""

    model_config = ConfigDict(extra="ignore")

    code: Optional[str] = Field(None, min_length=1, max_length=32)
    name: Optional[str] = Field(None, min_length=1, max_length=160)
    level: Optional[int] = Field(None, ge=1, le=12)
    #: When provided, replaces the subject-level teacher mappings.
    teacher_ids: Optional[List[int]] = None


class SubjectResponse(SubjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    created_at: Optional[datetime] = None
    teacher_ids: List[int] = Field(default_factory=list)
    assigned_teachers: List[SubjectTeacherSummary] = Field(default_factory=list)


class SubjectTeacherRosterRequest(BaseModel):
    """Body for ``PUT /api/v1/subjects/{id}/teachers`` (full replacement)."""

    model_config = ConfigDict(extra="forbid")

    teacher_ids: List[int] = Field(default_factory=list)
    #: Teacher that owns the subject as department lead.
    primary_teacher_id: Optional[int] = None


class SubjectTeacherAssignRequest(BaseModel):
    """Body for ``POST /api/v1/subjects/{id}/teachers``."""

    model_config = ConfigDict(extra="forbid")

    teacher_id: int = Field(..., gt=0)
    is_primary: bool = False
