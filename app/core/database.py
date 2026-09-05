"""Deprecated alias for :mod:`app.db.session`.

This module used to declare a **second** ``DeclarativeBase``.  That produced two
independent metadata registries (``app.models.base.Base`` and
``app.core.database.Base``) and is the classic source of

    sqlalchemy.exc.InvalidRequestError: Table 'users' is already defined for
    this MetaData instance.

when both model sets end up on the same metadata.  It now re-exports the one
and only declarative base from ``app.models.base`` — please import from
``app.db.session`` or ``app.models.base`` instead.
"""
from __future__ import annotations

from app.db.session import (  # noqa: F401
    Base,
    SessionLocal,
    check_database_connection,
    dispose_engine,
    engine,
    get_db,
    init_db,
    session_scope,
    set_rls_context,
)

__all__ = [
    "Base",
    "SessionLocal",
    "engine",
    "get_db",
    "session_scope",
    "init_db",
    "set_rls_context",
    "check_database_connection",
    "dispose_engine",
]
