"""Classroom schemas; Class* names preserve the school API's imports."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ClassCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_level: int = Field(ge=1, le=12)
    stream: str = Field(min_length=1)
    academic_year_id: Optional[int] = None


class ClassUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_level: Optional[int] = Field(default=None, ge=1, le=12)
    stream: Optional[str] = Field(default=None, min_length=1)
    academic_year_id: Optional[int] = None

    @field_validator("class_level", "stream")
    @classmethod
    def reject_null_required_fields(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class ClassResponse(ClassCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
