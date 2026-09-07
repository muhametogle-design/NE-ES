"""Student CRUD schemas. Photos are nullable stored URLs, not inline files."""
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudentBase(BaseModel):
    first_name: str
    last_name: str
    gender: str
    date_of_birth: Optional[date] = None
    class_id: Optional[int] = None
    photo_url: Optional[str] = Field(default=None, max_length=500)


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    class_id: Optional[int] = None
    is_active: Optional[bool] = None
    photo_url: Optional[str] = Field(default=None, max_length=500)

    @field_validator("first_name", "last_name", "gender", "is_active")
    @classmethod
    def reject_null_required_fields(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class StudentResponse(StudentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
    national_student_id: str
    roll_number: str
    is_active: bool
    created_at: datetime
