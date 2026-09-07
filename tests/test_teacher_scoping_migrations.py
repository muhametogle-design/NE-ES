"""Migration data preservation on SQLite and offline PostgreSQL DDL checks."""
import io
import uuid
from datetime import date
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext

from app.models import Base

ROOT = Path(__file__).resolve().parents[1]
PREVIOUS_REVISION = "f9da2d24c61a"
PHOTO_REVISION = "83dda6195453"
REFERENCES = (
    ("teaching_assignments", "teacher_id"),
    ("timetable_slots", "teacher_id"),
    ("teacher_absences", "teacher_id"),
    ("substitution_assignments", "substitute_teacher_id"),
)


def _config(output_buffer=None):
    config = Config(str(ROOT / "alembic.ini"), output_buffer=output_buffer)
    config.set_main_option("script_location", str(ROOT / "alembic"))
    return config


@pytest.fixture
def legacy_database(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'teacher-migration.db'}"
    monkeypatch.setenv("NE_EMIS_DATABASE_URL", url)
    config = _config()
    command.upgrade(config, PREVIOUS_REVISION)
    engine = sa.create_engine(url)

    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    metadata = sa.MetaData()
    metadata.reflect(engine)
    tables = metadata.tables
    with engine.begin() as conn:
        conn.execute(tables["private_schools"].insert().values(id=7, school_code="MP", school_name="Migration School"))
        for user_id, role in ((11, "teacher"), (12, "teacher"), (20, "school_manager")):
            conn.execute(tables["users"].insert().values(
                id=user_id, school_id=7, email=f"legacy{user_id}@example.org", password_hash=f"original-hash-{user_id}",
                role=role, first_name=f"Legacy {user_id}", last_name="Staff", staff_identifier=f"STAFF-{user_id}",
                phone="123", bio="Preserve me", is_department_head=None, is_active=True,
            ))
        conn.execute(tables["school_classes"].insert().values(id=201, school_id=7, class_level=4, stream="A"))
        conn.execute(tables["subjects"].insert().values(id=301, school_id=7, code="MAT-04", name="Math", level=4))
        conn.execute(tables["students"].insert().values(
            id=401, school_id=7, class_id=201, national_student_id="SID-401", roll_number="MP-401",
            first_name="Existing", last_name="Student", gender="Female", is_active=True,
        ))
        conn.execute(tables["teaching_assignments"].insert().values(
            id=501, school_id=7, teacher_id=11, class_id=201, subject_id=301,
        ))
        conn.execute(tables["timetable_slots"].insert().values(
            id=601, school_id=7, teacher_id=11, class_id=201, subject_id=301, day_of_week=0, period=1,
        ))
        conn.execute(tables["teacher_absences"].insert().values(
            id=701, school_id=7, teacher_id=11, date=date(2026, 9, 7), reason="Preserve absence",
        ))
        conn.execute(tables["substitution_assignments"].insert().values(
            id=801, school_id=7, absence_id=701, substitute_teacher_id=12, timetable_slot_id=601, confirmed=True,
        ))
        conn.execute(tables["student_grades"].insert().values(
            id=901, school_id=7, student_id=401, subject_id=301, term="Legacy", score=75,
        ))
        conn.execute(tables["subject_attendance"].insert().values(
            id=902, school_id=7, student_id=401, subject_id=301, class_id=201,
            date=date(2026, 9, 7), status="present", marked_by=12,
        ))
        conn.execute(tables["live_attendance"].insert().values(
            id=903, school_id=7, student_id=401, timetable_slot_id=601,
            date=date(2026, 9, 7), status="present", marked_by=12,
        ))
        conn.execute(tables["student_biometrics"].insert().values(
            id=uuid.uuid4().hex, student_id=401, template_data="ZXhpc3Rpbmc=",
        ))
    try:
        yield config, engine
    finally:
        engine.dispose()


def _assert_history_survived(engine):
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT roll_number FROM students WHERE id=401")) == "MP-401"
        assert conn.scalar(sa.text("SELECT score FROM student_grades WHERE id=901")) == 75
        assert conn.scalar(sa.text("SELECT marked_by FROM subject_attendance WHERE id=902")) == 12
        assert conn.scalar(sa.text("SELECT status FROM live_attendance WHERE id=903")) == "present"
        assert conn.scalar(sa.text("SELECT template_data FROM student_biometrics WHERE student_id=401")) == "ZXhpc3Rpbmc="
        assert conn.scalar(sa.text("SELECT password_hash FROM users WHERE id=11")) == "original-hash-11"
        assert conn.execute(sa.text("PRAGMA foreign_key_check")).all() == []


def test_sqlite_upgrade_backfills_teachers_and_preserves_all_history(legacy_database):
    config, engine = legacy_database
    command.upgrade(config, PHOTO_REVISION)
    inspector = sa.inspect(engine)
    teachers_columns = {column["name"]: column for column in inspector.get_columns("teachers")}
    student_columns = {column["name"]: column for column in inspector.get_columns("students")}
    assert teachers_columns["photo_url"]["type"].length == student_columns["photo_url"]["type"].length == 500
    assert teachers_columns["photo_url"]["nullable"] and student_columns["photo_url"]["nullable"]
    assert teachers_columns["user_id"]["nullable"] and isinstance(teachers_columns["user_id"]["type"], sa.Integer)
    assert inspector.get_pk_constraint("teachers")["name"] == "pk_teachers"
    binding_fk = next(fk for fk in inspector.get_foreign_keys("teachers") if fk["constrained_columns"] == ["user_id"])
    assert binding_fk["name"] == "fk_teachers_user_id_users"
    assert binding_fk["referred_table"] == "users" and binding_fk["referred_columns"] == ["id"]
    assert binding_fk["options"]["ondelete"] == "SET NULL"
    assert any(index["name"] == "ix_teachers_user_id" for index in inspector.get_indexes("teachers"))
    assert any(constraint["name"] == "uq_teachers_user_id" for constraint in inspector.get_unique_constraints("teachers"))
    for table, column in REFERENCES:
        fk = next(fk for fk in inspector.get_foreign_keys(table) if fk["constrained_columns"] == [column])
        assert fk["name"] == f"fk_{table}_{column}_teachers"
        assert fk["referred_table"] == "teachers" and fk["options"]["ondelete"] == "CASCADE"
    with engine.begin() as conn:
        profiles = conn.execute(sa.text("SELECT id, user_id, first_name, bio FROM teachers ORDER BY id")).all()
        assert profiles == [(11, 11, "Legacy 11", "Preserve me"), (12, 12, "Legacy 12", "Preserve me")]
        assert conn.scalar(sa.text("SELECT COUNT(*) FROM teachers WHERE photo_url IS NOT NULL")) == 0
        conn.execute(sa.text("UPDATE teachers SET photo_url='/media/teacher.jpg' WHERE id=11"))
        conn.execute(sa.text("UPDATE students SET photo_url='/media/student.jpg' WHERE id=401"))
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT photo_url FROM teachers WHERE id=11")) == "/media/teacher.jpg"
        assert conn.scalar(sa.text("SELECT photo_url FROM students WHERE id=401")) == "/media/student.jpg"
        assert compare_metadata(MigrationContext.configure(conn), Base.metadata) == []
    _assert_history_survived(engine)


def test_sqlite_downgrade_maps_rebound_profile_ids_back_to_user_ids(legacy_database):
    config, engine = legacy_database
    command.upgrade(config, PHOTO_REVISION)
    with engine.begin() as conn:
        conn.execute(sa.text("""
            INSERT INTO users (id, school_id, email, password_hash, role, first_name, last_name)
            VALUES (31, 7, 'rebound@example.org', 'new-hash', 'teacher', 'New', 'Login')
        """))
        conn.execute(sa.text("UPDATE teachers SET user_id=31 WHERE id=11"))
    command.downgrade(config, PREVIOUS_REVISION)
    assert "teachers" not in sa.inspect(engine).get_table_names()
    assert "photo_url" not in {column["name"] for column in sa.inspect(engine).get_columns("students")}
    with engine.connect() as conn:
        for table, column in REFERENCES:
            assert conn.scalar(sa.text(f"SELECT {column} FROM {table}")) == (12 if column == "substitute_teacher_id" else 31)
    _assert_history_survived(engine)
    # Re-applying after downgrade also handles the now explicitly named FKs.
    command.upgrade(config, PHOTO_REVISION)
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT user_id FROM teachers WHERE id=31")) == 31
        assert conn.scalar(sa.text("SELECT teacher_id FROM teaching_assignments WHERE id=501")) == 31
    _assert_history_survived(engine)


def test_sqlite_set_null_uniqueness_and_safe_downgrade_preflight(legacy_database):
    config, engine = legacy_database
    command.upgrade(config, PHOTO_REVISION)
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE teachers SET user_id=11 WHERE id=12"))
    with pytest.raises(sa.exc.IntegrityError):
        with engine.begin() as conn:
            conn.execute(sa.text("UPDATE teachers SET user_id=99999 WHERE id=12"))
    with engine.begin() as conn:
        # Teacher 11 has course, timetable, and absence records. None may be
        # cascade-deleted when only the authentication account is deleted.
        conn.execute(sa.text("DELETE FROM users WHERE id=11"))
        assert conn.scalar(sa.text("SELECT user_id FROM teachers WHERE id=11")) is None
        assert conn.scalar(sa.text("SELECT COUNT(*) FROM teaching_assignments")) == 1
        assert conn.scalar(sa.text("SELECT COUNT(*) FROM teacher_absences")) == 1
        assert conn.scalar(sa.text("SELECT COUNT(*) FROM substitution_assignments")) == 1
        assert conn.execute(sa.text("PRAGMA foreign_key_check")).all() == []
        # Multiple unlinked profiles are legal despite the one-to-one binding.
        conn.execute(sa.text("""
            INSERT INTO teachers (school_id, first_name, last_name, is_active, is_department_head)
            VALUES (7, 'Unlinked', 'Second', true, false)
        """))
    with pytest.raises(RuntimeError, match="Link assigned teachers"):
        command.downgrade(config, PREVIOUS_REVISION)
    with engine.connect() as conn:
        assert conn.scalar(sa.text("SELECT version_num FROM alembic_version")) == PHOTO_REVISION
        assert conn.scalar(sa.text("SELECT teacher_id FROM teaching_assignments")) == 11
        assert conn.execute(sa.text("PRAGMA foreign_key_check")).all() == []


def test_migration_compiles_for_postgresql(monkeypatch):
    monkeypatch.setenv("NE_EMIS_DATABASE_URL", "postgresql+psycopg2://localhost/teacher_migration_check")
    output = io.StringIO()
    config = _config(output)
    command.upgrade(config, f"{PREVIOUS_REVISION}:{PHOTO_REVISION}", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE teachers" in sql
    assert "user_id INTEGER" in sql
    assert "photo_url VARCHAR(500)" in sql
    assert "CONSTRAINT pk_teachers PRIMARY KEY (id)" in sql
    assert "CONSTRAINT uq_teachers_user_id UNIQUE (user_id)" in sql
    assert "CONSTRAINT fk_teachers_user_id_users FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL" in sql
    assert "CREATE INDEX ix_teachers_user_id" in sql
    assert "ALTER TABLE students ADD COLUMN photo_url VARCHAR(500)" in sql
    assert "INSERT INTO teachers" in sql and "pg_get_serial_sequence('teachers', 'id')" in sql
    for table, column in REFERENCES:
        assert f"DROP CONSTRAINT {table}_{column}_fkey" in sql
        assert f"CONSTRAINT fk_{table}_{column}_teachers FOREIGN KEY({column}) REFERENCES teachers (id) ON DELETE CASCADE" in sql
    output.seek(0)
    output.truncate(0)
    command.downgrade(config, f"{PHOTO_REVISION}:{PREVIOUS_REVISION}", sql=True)
    sql = output.getvalue()
    assert "DROP TABLE teachers" in sql and "ALTER TABLE students DROP COLUMN photo_url" in sql
    for table, column in REFERENCES:
        assert f"UPDATE {table} SET {column}" in sql
        assert f"CONSTRAINT {table}_{column}_fkey FOREIGN KEY({column}) REFERENCES users (id) ON DELETE CASCADE" in sql


def test_invalid_legacy_staff_binding_fails_before_any_schema_changes(legacy_database):
    config, engine = legacy_database
    with engine.begin() as conn:
        conn.execute(sa.text("UPDATE users SET school_id=NULL WHERE id=11"))
    with pytest.raises(RuntimeError, match="Assign legacy teaching staff"):
        command.upgrade(config, PHOTO_REVISION)
    inspector = sa.inspect(engine)
    assert "teachers" not in inspector.get_table_names()
    assert "photo_url" not in {column["name"] for column in inspector.get_columns("students")}
    with engine.begin() as conn:
        assert conn.scalar(sa.text("SELECT version_num FROM alembic_version")) == PREVIOUS_REVISION
        conn.execute(sa.text("UPDATE users SET school_id=7 WHERE id=11"))
    command.upgrade(config, PHOTO_REVISION)
    _assert_history_survived(engine)
