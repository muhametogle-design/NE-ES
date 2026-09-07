"""Seed the configured database with the NE-EMIS default records.

Usage (from the repository root)::

    python -m scripts.seed            # idempotent: creates only what is missing
    python -m scripts.seed --reset    # SQLite only: delete the DB file first

What gets seeded (see ``app.services.seed.seed_demo_data``):

* State ministry accounts — ``state_admin`` and ``inspector`` users.
* The five pre-provisioned private-school tenants (IL, MY, NG, AQ, LB) with
  their roll-number sequences, classes, subjects, demo students and the
  ``school_manager`` / ``teacher`` accounts documented in the README.
* Today's compliance (daily-submission) state for the oversight dashboard.

The target database is ``DATABASE_URL`` (shell environment, then ``.env``,
then the SQLite default) — the same resolution used by the API and by
``alembic/env.py``. Seeding is refused when ``APP_ENV`` is ``test``/``testing``
so a test configuration can never populate a real database by accident.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv  # noqa: E402

# Mirror alembic/env.py: load the repo-root .env before app.* is imported so
# ``settings.DATABASE_URL`` is identical no matter which directory we run from.
load_dotenv(REPO_ROOT / ".env")

from sqlalchemy import inspect  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal, engine, init_db, set_rls_context  # noqa: E402
from app.models.academic import Student  # noqa: E402
from app.models.tenancy import PrivateSchool, User  # noqa: E402
from app.services.seed import seed_demo_data  # noqa: E402

TEST_ENVIRONMENTS = ("test", "testing")


def _masked_url() -> str:
    return make_url(settings.DATABASE_URL).render_as_string(hide_password=True)


def _reset_sqlite_file() -> None:
    if not settings.DATABASE_URL.startswith("sqlite"):
        print("--reset only deletes a local SQLite file; for PostgreSQL drop and "
              "recreate the database, then run `alembic upgrade head`.")
        return
    db_path = settings.DATABASE_URL.replace("sqlite:///", "", 1)
    if db_path and db_path != ":memory:" and os.path.exists(db_path):
        os.remove(db_path)
        print(f"Removed SQLite database file: {db_path}")


def _print_summary(db) -> None:
    schools = db.query(PrivateSchool).order_by(PrivateSchool.id).all()
    state_users = db.query(User).filter(User.school_id.is_(None)).order_by(User.id).all()

    print("\nSeed summary")
    print("  State ministry accounts:")
    for u in state_users:
        print(f"    - {u.role:<13} {u.email}")
    print(f"  Schools ({len(schools)}):")
    for s in schools:
        managers = db.query(User).filter(User.school_id == s.id, User.role == "school_manager").count()
        teachers = db.query(User).filter(User.school_id == s.id, User.role == "teacher").count()
        students = db.query(Student).filter(Student.school_id == s.id).count()
        print(f"    - {s.school_code}  {s.school_name:<45} "
              f"managers={managers} teachers={teachers} students={students}")
    print(f"  Users total: {db.query(User).count()}  |  Students total: {db.query(Student).count()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--reset", action="store_true",
                        help="SQLite only: delete the database file before seeding")
    args = parser.parse_args(argv)

    if settings.APP_ENV.strip().lower() in TEST_ENVIRONMENTS:
        print(f"Refusing to seed: APP_ENV={settings.APP_ENV!r} is a test environment.",
              file=sys.stderr)
        return 2

    print(f"Target database: {_masked_url()}")

    if args.reset:
        _reset_sqlite_file()

    # Schema: prefer Alembic-managed schemas; fall back to create_all() for a
    # brand-new SQLite file (matches the previous scripts/seed_data behaviour).
    inspector = inspect(engine)
    if "alembic_version" in inspector.get_table_names():
        print("Schema managed by Alembic (alembic_version present) - skipping create_all().")
    else:
        print("No alembic_version table found - initializing schema with create_all() ...")
        init_db()

    db = SessionLocal()
    try:
        set_rls_context(db, None, "state_admin")
        print("Seeding NE-EMIS default records (state admins, schools, managers, demo data) ...")
        seed_demo_data(db)
        db.commit()
        _print_summary(db)
        print("\nSeeding completed successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
