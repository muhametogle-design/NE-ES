"""Exercise the actual fingerprint revision, not just Base.metadata.create_all."""
import base64
import io
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

PREVIOUS_REVISION = "1c64b29eebdf"
BIOMETRIC_REVISION = "f9da2d24c61a"
REPO_ROOT = Path(__file__).resolve().parents[1]


def _config(**kwargs):
    config = Config(str(REPO_ROOT / "alembic.ini"), **kwargs)
    config.set_main_option("script_location", str(REPO_ROOT / "alembic"))
    return config


def test_fingerprint_migration_sqlite_round_trip_preserves_students(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'fingerprint_migrations.db'}"
    # Alembic-only override: never migrate the app's configured or shared test DB.
    monkeypatch.setenv("NE_EMIS_DATABASE_URL", url)
    config = _config()
    command.upgrade(config, PREVIOUS_REVISION)
    engine = sa.create_engine(url)

    @sa.event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    try:
        metadata = sa.MetaData()
        schools = sa.Table("private_schools", metadata, autoload_with=engine)
        students = sa.Table("students", metadata, autoload_with=engine)
        with engine.begin() as connection:
            connection.execute(schools.insert().values(id=1, school_code="BM", school_name="Migration School"))
            for student_id in (41, 42):
                connection.execute(students.insert().values(
                    id=student_id, school_id=1,
                    national_student_id=f"BIO-{student_id}", roll_number=f"BM-{student_id}",
                    first_name="Existing", last_name="Student", gender="F", is_active=True,
                ))

        command.upgrade(config, BIOMETRIC_REVISION)
        inspector = sa.inspect(engine)
        assert inspector.get_pk_constraint("student_biometrics")["name"] == "pk_student_biometrics"
        fk, = inspector.get_foreign_keys("student_biometrics")
        assert fk["name"] == "fk_student_biometrics_student_id_students"
        assert fk["constrained_columns"] == ["student_id"]
        assert fk["referred_table"] == "students"
        assert fk["referred_columns"] == ["id"]
        assert fk["options"]["ondelete"] == "CASCADE"
        assert any(
            index["name"] == "ix_student_biometrics_student_id" and index["column_names"] == ["student_id"]
            for index in inspector.get_indexes("student_biometrics")
        )
        assert any(
            constraint["name"] == "ck_student_biometrics_finger_position"
            for constraint in inspector.get_check_constraints("student_biometrics")
        )

        biometrics = sa.Table("student_biometrics", metadata, autoload_with=engine)
        assert isinstance(biometrics.c.student_id.type, sa.Integer)
        template = base64.b64encode(b"migration-test-template").decode("ascii")
        with engine.begin() as connection:
            assert connection.scalar(sa.select(students.c.roll_number).where(students.c.id == 41)) == "BM-41"
            for student_id in (41, 42):
                # Use reflected columns so defaults come from the migration/DB,
                # not from the ORM's Python-side defaults or enum validation.
                connection.execute(biometrics.insert().values(
                    id=uuid.uuid4().hex, student_id=student_id, template_data=template,
                ))
            row = connection.execute(sa.select(biometrics).where(biometrics.c.student_id == 41)).one()
            uuid.UUID(row.id)
            assert row.finger_position == "RIGHT_INDEX"
            assert row.template_format == "ISO_19794_2"
            assert row.quality_score is None and row.device_model is None
            assert row.created_at is not None and row.updated_at is not None

        for overrides in (
            {"student_id": 999999999},
            {"finger_position": "RIGHT_MIDDLE"},
            {"template_data": None},
        ):
            with pytest.raises(sa.exc.IntegrityError):
                with engine.begin() as connection:
                    connection.execute(biometrics.insert().values({
                        "id": uuid.uuid4().hex, "student_id": 41, "template_data": template, **overrides,
                    }))

        with engine.begin() as connection:
            assert connection.scalar(sa.text("PRAGMA foreign_keys")) == 1
            connection.execute(students.delete().where(students.c.id == 42))
            assert connection.scalar(sa.select(sa.func.count()).select_from(biometrics)) == 1
            assert connection.scalar(sa.select(biometrics.c.student_id)) == 41
            assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []

        command.downgrade(config, PREVIOUS_REVISION)
        assert "student_biometrics" not in sa.inspect(engine).get_table_names()
        assert "biometric_credentials" in sa.inspect(engine).get_table_names()
        with engine.connect() as connection:
            assert connection.scalar(sa.select(students.c.roll_number).where(students.c.id == 41)) == "BM-41"

        # Re-applying the same revision is supported after downgrade.
        command.upgrade(config, BIOMETRIC_REVISION)
        with engine.connect() as connection:
            assert connection.scalar(sa.select(sa.func.count()).select_from(biometrics)) == 0
            assert connection.execute(sa.text("PRAGMA foreign_key_check")).all() == []
    finally:
        engine.dispose()


def test_fingerprint_migration_compiles_for_postgresql(monkeypatch):
    # Offline SQL generation needs no running PostgreSQL server or credentials.
    monkeypatch.setenv("NE_EMIS_DATABASE_URL", "postgresql+psycopg2://localhost/biometrics_migration_check")
    output = io.StringIO()
    config = _config(output_buffer=output)
    command.upgrade(config, f"{PREVIOUS_REVISION}:{BIOMETRIC_REVISION}", sql=True)
    sql = output.getvalue()
    assert "CREATE TABLE student_biometrics" in sql
    assert "id UUID NOT NULL" in sql
    assert "student_id INTEGER NOT NULL" in sql
    assert "TIMESTAMP WITH TIME ZONE" in sql
    assert "CONSTRAINT pk_student_biometrics PRIMARY KEY (id)" in sql
    assert (
        "CONSTRAINT fk_student_biometrics_student_id_students FOREIGN KEY(student_id) "
        "REFERENCES students (id) ON DELETE CASCADE"
    ) in sql
    assert "CONSTRAINT ck_student_biometrics_finger_position CHECK" in sql
    assert "CREATE INDEX ix_student_biometrics_student_id" in sql
    assert "CREATE TYPE" not in sql  # no native enum to leak across downgrades

    output.seek(0)
    output.truncate(0)
    command.downgrade(config, f"{BIOMETRIC_REVISION}:{PREVIOUS_REVISION}", sql=True)
    sql = output.getvalue()
    assert "DROP INDEX ix_student_biometrics_student_id" in sql
    assert "DROP TABLE student_biometrics" in sql
