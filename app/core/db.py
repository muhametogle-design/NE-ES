import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator, Optional
from app.core.config import settings
from app.models.base import Base

# Ensure data directory exists if sqlite
if settings.DATABASE_URL.startswith("sqlite"):
    db_file = settings.DATABASE_URL.replace("sqlite:///", "")
    db_dir = os.path.dirname(db_file)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {},
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app.models import all_models
    Base.metadata.create_all(bind=engine)
    if settings.DATABASE_URL.startswith("sqlite"):
        migrate_sqlite_columns()

def migrate_sqlite_columns():
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        with engine.connect() as conn:
            for table_name in existing_tables:
                columns = {col["name"] for col in inspector.get_columns(table_name)}
                model_table = Base.metadata.tables.get(table_name)
                if model_table is not None:
                    for col in model_table.columns:
                        if col.name not in columns:
                            col_type = col.type.compile(engine.dialect)
                            nullable = "NULL" if col.nullable else "NOT NULL DEFAULT ''"
                            conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type} {nullable}"))
            conn.commit()
    except Exception:
        pass

def set_rls_context(db: Session, school_id: Optional[int], role: str):
    if settings.DATABASE_URL.startswith("postgresql"):
        try:
            db.execute(text("SELECT set_config('app.school_id', :school_id, true)"),
                       {"school_id": str(school_id) if school_id else ""})
            db.execute(text("SELECT set_config('app.role', :role, true)"),
                       {"role": role})
        except Exception:
            pass
