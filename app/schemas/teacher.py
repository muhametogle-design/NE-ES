"""Teacher / staff schemas.

Two related resources share these definitions:

``Teacher*`` (this module's primary types)
    The **staff profile** (:class:`app.models.auth.Teacher`) served by
    ``/api/v1/teachers``.  A profile carries ``photo_url`` and the optional
    ``user_id`` binding to the login account, plus subject-level assignments.

``TeacherAccount*``
    The **login account** (``User`` with ``role="teacher"``) served by the
    legacy ``/api/v1/school/teachers`` endpoints.  ``app.schemas.school``
    re-exports these as ``TeacherCreate`` / ``TeacherUpdate`` /
    ``TeacherResponse`` so the existing router keeps its import names while
    gaining ``photo_url`` and ``user_id``.

``TeacherUserProvision`` describes the account that is auto-provisioned when a
staff profile is created without an existing login (``role`` is pinned to
``"teacher"`` — staff profiles never mint manager or state accounts).
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.schemas.media import PhotoUrl
from app.schemas.subject import SubjectBrief

#: Password floor for auto-provisioned staff accounts.
MIN_TEACHER_PASSWORD_LENGTH = 8


class TeacherBase(BaseModel):
    """Fields shared by staff-profile create/update/response payloads."""

    model_config = ConfigDict(extra="ignore")

    first_name: str = Field(..., min_length=1, max_length=120)
    last_name: str = Field(..., min_length=1, max_length=120)
    phone: Optional[str] = Field(None, max_length=64)
    qualifications: Optional[str] = Field(None, max_length=255)
    designation: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None
    is_department_head: bool = False
    #: Portrait URL — absolute http(s) or a local ``/media/...`` path.
    photo_url: PhotoUrl = None


class TeacherUserProvision(BaseModel):
    """Credentials for the ``role="teacher"`` account created with a profile."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(..., min_length=MIN_TEACHER_PASSWORD_LENGTH, max_length=128)
    #: Pinned: a staff profile can only ever provision a teacher login.
    role: Literal["teacher"] = "teacher"
    first_name: Optional[str] = Field(None, max_length=120)
    last_name: Optional[str] = Field(None, max_length=120)
    #: Optional 4-8 digit staff PIN (hashed server-side like every other PIN).
    staff_pin: Optional[str] = Field(None, min_length=4, max_length=8, pattern=r"^\d{4,8}$")


class TeacherCreate(TeacherBase):
    """Create a staff profile, optionally provisioning/binding its login.

    Exactly one of these three shapes is expected:

    1. ``link_user_id`` — bind an existing teacher account in the same school.
    2. ``user`` (or top-level ``email`` + ``password``) with
       ``auto_provision_user=True`` (default) — create the ``role="teacher"``
       account and bind it.
    3. ``auto_provision_user=False`` — record the staff member before any
       account exists (``user_id`` stays NULL and can be linked later).
    """

    model_config = ConfigDict(extra="ignore")

    school_id: Optional[int] = Field(None, gt=0)
    staff_identifier: Optional[str] = Field(None, max_length=64)
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(None, min_length=MIN_TEACHER_PASSWORD_LENGTH, max_length=128)
    user: Optional[TeacherUserProvision] = None
    link_user_id: Optional[int] = Field(None, gt=0)
    auto_provision_user: bool = True
    #: Subject-level assignments (must belong to the same school).
    subject_ids: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_account_intent(self) -> "TeacherCreate":
        if self.link_user_id is not None:
            if self.auto_provision_user and (self.user is not None or self.password is not None):
                raise ValueError(
                    "Provide either link_user_id or provisioning credentials, not both"
                )
            return self
        if not self.auto_provision_user:
            return self
        if self.user is None and not (self.email and self.password):
            raise ValueError(
                "Auto-provisioning requires `user` credentials, or top-level `email` and `password`; "
                "set auto_provision_user=false to create an unlinked staff record"
            )
        return self


class TeacherUpdate(BaseModel):
    """Partial staff-profile update; ``photo_url=None`` clears the portrait.

    ``subject_ids`` replaces the subject-level mappings when present.
    ``user_id`` re-binds the profile to another teacher account (managers only).
    """

    model_config = ConfigDict(extra="ignore")

    first_name: Optional[str] = Field(None, min_length=1, max_length=120)
    last_name: Optional[str] = Field(None, min_length=1, max_length=120)
    phone: Optional[str] = Field(None, max_length=64)
    qualifications: Optional[str] = Field(None, max_length=255)
    designation: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None
    is_department_head: Optional[bool] = None
    is_active: Optional[bool] = None
    photo_url: PhotoUrl = None
    staff_identifier: Optional[str] = Field(None, max_length=64)
    email: Optional[EmailStr] = None
    user_id: Optional[int] = Field(None, gt=0)
    subject_ids: Optional[List[int]] = None


class TeacherSubjectSetRequest(BaseModel):
    """Body for ``PUT /api/v1/teachers/{id}/subjects`` (full replacement)."""

    model_config = ConfigDict(extra="forbid")

    subject_ids: List[int] = Field(default_factory=list)
    #: Subject the teacher owns as department lead.
    primary_subject_id: Optional[int] = None


class TeacherLinkUserRequest(BaseModel):
    """Body for ``POST /api/v1/teachers/{id}/link-user``."""

    model_config = ConfigDict(extra="forbid")

    user_id: int = Field(..., gt=0)


class TeacherAccountBrief(BaseModel):
    """The login account bound to a staff profile (never exposes secrets)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    role: str
    staff_identifier: Optional[str] = None
    is_active: bool = True
    photo_url: Optional[str] = None


class TeacherResponse(TeacherBase):
    """Staff profile as served by ``/api/v1/teachers``."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    #: Binding to ``users.id`` — NULL until an account is provisioned/linked.
    user_id: Optional[int] = None
    staff_identifier: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    is_active: bool = True
    subject_ids: List[int] = Field(default_factory=list)
    assigned_subjects: List[SubjectBrief] = Field(default_factory=list)
    #: Class-level teaching assignments resolved through the bound account.
    class_ids: List[int] = Field(default_factory=list)
    account: Optional[TeacherAccountBrief] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Login-account views (legacy /api/v1/school/teachers endpoints)
# ---------------------------------------------------------------------------
class TeacherAccountCreate(BaseModel):
    """Create a ``role="teacher"`` login account for the caller's school."""

    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: str = Field(..., min_length=MIN_TEACHER_PASSWORD_LENGTH, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=120)
    last_name: str = Field(..., min_length=1, max_length=120)
    phone: Optional[str] = Field(None, max_length=64)
    qualifications: Optional[str] = Field(None, max_length=255)
    designation: Optional[str] = None
    bio: Optional[str] = None
    is_department_head: bool = False
    photo_url: PhotoUrl = None
    #: Also create the matching staff profile (subject-level scoping needs one).
    create_profile: bool = True


class TeacherAccountUpdate(BaseModel):
    """Partial account update; only these fields may be written by the router."""

    model_config = ConfigDict(extra="ignore")

    first_name: Optional[str] = Field(None, min_length=1, max_length=120)
    last_name: Optional[str] = Field(None, min_length=1, max_length=120)
    phone: Optional[str] = Field(None, max_length=64)
    qualifications: Optional[str] = Field(None, max_length=255)
    designation: Optional[str] = Field(None, max_length=255)
    bio: Optional[str] = None
    is_department_head: Optional[bool] = None
    is_active: Optional[bool] = None
    photo_url: PhotoUrl = None


class TeacherAccountResponse(BaseModel):
    """Account-shaped teacher payload (``id`` is the ``users.id`` value)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: Optional[int] = None
    #: The account a teacher record is bound to (itself, for account views).
    user_id: Optional[int] = None
    teacher_profile_id: Optional[int] = None
    email: str
    role: str = "teacher"
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    staff_identifier: Optional[str] = None
    phone: Optional[str] = None
    qualifications: Optional[str] = None
    designation: Optional[str] = None
    bio: Optional[str] = None
    is_department_head: bool = False
    is_active: bool = True
    photo_url: Optional[str] = None
    created_at: Optional[datetime] = None
