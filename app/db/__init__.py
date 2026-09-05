"""Database package for NE-ES.

``app.db.session`` owns the SQLAlchemy engine, the session factory and the
FastAPI ``get_db`` dependency.  ``app.core.db`` and ``app.core.database``
remain as thin compatibility shims so existing imports keep working.
"""
