"""Backwards-compatible alias for :mod:`app.db.session`.

Historical entry point — the engine, session factory and helpers now live in
``app/db/session.py``.  Every name is re-exported verbatim so the existing
import sites (``app.api.*``, ``app.main``, ``app.services.*``, ``scripts.*``,
``tests.conftest``) keep working unchanged.

New code should import from ``app.db.session`` directly.
"""
from __future__ import annotations

from app.db.session import (  # noqa: F401
    Base,
    SessionLocal,
    build_connect_args,
    build_engine_kwargs,
    check_database_connection,
    create_database_engine,
    dispose_engine,
    engine,
    get_db,
    init_db,
    migrate_sqlite_columns,
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
    "migrate_sqlite_columns",
    "set_rls_context",
    "create_database_engine",
    "build_connect_args",
    "build_engine_kwargs",
    "check_database_connection",
    "dispose_engine",
]
