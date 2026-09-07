"""Teacher profiles and optional, teacher-only login provisioning."""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator, model_validator


class TeacherUserCreate(BaseModel):
    """Credentials for a new login in the creating manager's school.

    Tenant and privileges cannot be supplied by the caller. Passwords are
    write-only; TeacherResponse never includes this object or password hashes.
    """
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)
    role: Literal["teacher"] = "teacher"


class TeacherBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: str
    last_name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    qualifications: Optional[str] = None
    designation: Optional[str] = None
    bio: Optional[str] = None
    is_department_head: bool = False
    is_active: bool = True
    photo_url: Optional[str] = Field(default=None, max_length=500)
    # Must match the existing INTEGER users.id, including on PostgreSQL.
    user_id: Optional[int] = Field(default=None, ge=1)


class TeacherCreate(TeacherBase):
    create_user: Optional[TeacherUserCreate] = None
    # Retain the existing flat email/password creation payload.
    password: Optional[SecretStr] = Field(default=None, min_length=8, max_length=128)

    @model_validator(mode="after")
    def validate_account_mode(self):
        modes = sum((self.user_id is not None, self.create_user is not None, self.password is not None))
        if modes > 1:
            raise ValueError("Choose user_id, create_user, or email/password, not multiple account modes")
        if self.password is not None and self.email is None:
            raise ValueError("email is required when provisioning with password")
        return self


class TeacherUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    qualifications: Optional[str] = None
    designation: Optional[str] = None
    bio: Optional[str] = None
    is_department_head: Optional[bool] = None
    is_active: Optional[bool] = None
    photo_url: Optional[str] = Field(default=None, max_length=500)
    user_id: Optional[int] = Field(default=None, ge=1)

    @field_validator("first_name", "last_name", "is_department_head", "is_active")
    @classmethod
    def reject_null_required_fields(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class TeacherResponse(TeacherBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    staff_identifier: Optional[str] = None
    created_at: datetime
