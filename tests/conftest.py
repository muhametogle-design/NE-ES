import os

# ---------------------------------------------------------------------------
# Test isolation: mark this process as a test environment BEFORE anything from
# ``app`` is imported. ``app.core.config.settings`` is built at import time and
# environment variables take precedence over ``.env``; ``app.main``'s lifespan
# checks ``APP_ENV`` to skip ``init_db()`` and demo seeding, so a ``TestClient``
# never touches the live ``DATABASE_URL`` (e.g. the ne_es_dev PostgreSQL DB).
# ``setdefault`` keeps an explicit ``APP_ENV=testing`` from the shell intact.
# ---------------------------------------------------------------------------
os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.core.config import settings
from app.core.db import Base, get_db, set_rls_context
from app.core.security import create_access_token
from app.services.seed import seed_demo_data
from app.core.ratelimit import rate_limit
from app.models.tenancy import User, PrivateSchool

# In-memory SQLite for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def isolated_backup_dir(tmp_path_factory):
    """Write backup snapshots produced by the tests to a throwaway directory.

    ``BackupService`` reads ``settings.BACKUP_DIR`` at call time, so pointing it
    at pytest's temp dir keeps ``data/backups/`` (the real, .gitignored backup
    location) free of test artefacts.
    """
    original = settings.BACKUP_DIR
    settings.BACKUP_DIR = str(tmp_path_factory.mktemp("backups"))
    yield settings.BACKUP_DIR
    settings.BACKUP_DIR = original


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    set_rls_context(db, None, "state_admin")
    seed_demo_data(db)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def db_session():
    rate_limit.reset()
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture
def state_admin_headers(db_session):
    user = db_session.query(User).filter(User.role == "state_admin").first()
    token = create_access_token({"sub": str(user.id), "role": user.role, "school_id": None})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def inspector_headers(db_session):
    user = db_session.query(User).filter(User.role == "inspector").first()
    token = create_access_token({"sub": str(user.id), "role": user.role, "school_id": None})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def school_manager_headers(db_session):
    school = db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "IL").first()
    user = db_session.query(User).filter(User.school_id == school.id, User.role == "school_manager").first()
    token = create_access_token({"sub": str(user.id), "role": user.role, "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def other_school_manager_headers(db_session):
    school = db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "NG").first()
    user = db_session.query(User).filter(User.school_id == school.id, User.role == "school_manager").first()
    token = create_access_token({"sub": str(user.id), "role": user.role, "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def teacher_headers(db_session):
    school = db_session.query(PrivateSchool).filter(PrivateSchool.school_code == "IL").first()
    user = db_session.query(User).filter(User.school_id == school.id, User.role == "teacher").first()
    token = create_access_token({"sub": str(user.id), "role": user.role, "school_id": school.id})
    return {"Authorization": f"Bearer {token}"}
