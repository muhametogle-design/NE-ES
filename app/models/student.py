"""Student directory records."""
from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Gender(str, enum.Enum):
    male = "male"
    female = "female"
    other = "other"


class StudentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    graduated = "graduated"
    suspended = "suspended"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admission_no: Mapped[str] = mapped_column(
        String(32), unique=True, index=True, nullable=False
    )
    first_name: Mapped[str] = mapped_column(String(120), nullable=False)
    last_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    gender: Mapped[Optional[Gender]] = mapped_column(
        Enum(Gender, values_callable=lambda e: [m.value for m in e])
    )
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date)
    grade: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    guardian_name: Mapped[Optional[str]] = mapped_column(String(255))
    guardian_phone: Mapped[Optional[str]] = mapped_column(String(32))
    address: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[StudentStatus] = mapped_column(
        Enum(StudentStatus, values_callable=lambda e: [m.value for m in e]),
        default=StudentStatus.active,
        nullable=False,
        index=True,
    )
    enrolled_on: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Student id={self.id} admission_no={self.admission_no!r}>"
