"""User accounts — compatibility alias.

The canonical ORM model lives in :mod:`app.models.tenancy` (table ``users``,
multi-tenant, ``school_id`` scoped).  This module used to declare a *second*
``User`` mapped to the same ``users`` table on a different declarative base,
which is what makes SQLAlchemy raise::

    InvalidRequestError: Table 'users' is already defined for this MetaData

It now only re-exports the canonical model so legacy imports keep resolving
without registering a duplicate table.

Prefer::

    from app.models.tenancy import User
"""
from __future__ import annotations

import enum

from app.models.tenancy import User  # noqa: F401  (canonical definition)

__all__ = ["User", "UserRole"]


class UserRole(str, enum.Enum):
    """Legacy role vocabulary kept for older call sites.

    :class:`app.models.tenancy.User.role` stores the authoritative role string
    (``state_admin``, ``inspector``, ``school_manager``, ``teacher``); this enum
    is a plain Python enum and is **not** attached to any table.
    """

    admin = "admin"
    staff = "staff"
    finance = "finance"
