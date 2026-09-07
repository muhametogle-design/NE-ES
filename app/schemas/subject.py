"""Subject metadata; teaching assignments are managed separately by managers."""
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubjectBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    level: int = Field(ge=1, le=12)


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Optional[str] = Field(default=None, min_length=1)
    name: Optional[str] = Field(default=None, min_length=1)
    level: Optional[int] = Field(default=None, ge=1, le=12)

    @field_validator("code", "name", "level")
    @classmethod
    def reject_null_required_fields(cls, value):
        if value is None:
            raise ValueError("This field cannot be null")
        return value


class SubjectResponse(SubjectBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    school_id: int
