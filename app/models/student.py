"""Student records — compatibility alias.

The canonical ORM model lives in :mod:`app.models.academic` (table ``students``,
``school_id``/``class_id`` scoped, ``national_student_id`` + ``roll_number``).
This module used to declare a *second* ``Student`` mapped to the same
``students`` table on a different declarative base — the classic cause of::

    InvalidRequestError: Table 'students' is already defined for this MetaData

It now re-exports the canonical model and keeps the gender/status vocabularies
that :mod:`app.schemas.student` and :mod:`app.api.students` import.  Neither
enum is attached to a table.

Prefer::

    from app.models.academic import Student
"""
from __future__ import annotations

import enum

from app.models.academic import Student  # noqa: F401  (canonical definition)

__all__ = ["Student", "Gender", "StudentStatus"]


class Gender(str, enum.Enum):
    """Gender vocabulary (plain enum, not persisted on its own table)."""

    male = "male"
    female = "female"
    other = "other"


class StudentStatus(str, enum.Enum):
    """Lifecycle states used by student directory listings."""

    active = "active"
    inactive = "inactive"
    graduated = "graduated"
    suspended = "suspended"
