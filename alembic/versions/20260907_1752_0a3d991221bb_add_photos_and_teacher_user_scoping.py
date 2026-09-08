"""add_photos_and_teacher_user_scoping

Adds portrait storage and the teacher staff-profile layer used for
subject-level access scoping:

* ``students.photo_url`` and ``users.photo_url`` — nullable ``VARCHAR(500)``
  columns holding an absolute ``https://`` URL or a local ``/media/...`` path
  (never image bytes).
* ``teachers`` — staff profiles. ``teachers.user_id`` binds a profile to its
  login account with ``ON DELETE SET NULL``, so the staff record and its photo
  survive the removal of the account; the binding is unique
  (``ix_teachers_user_id``) because one account maps to at most one profile.
* ``teacher_subjects`` — subject-level assignment (many-to-many
  ``teachers`` ↔ ``subjects``) that ``/api/v1/subjects`` and
  ``/api/v1/classrooms`` scope teacher access against.

Data backfill: every existing ``role='teacher'`` account receives a profile
bound through ``user_id``, and each subject that account already teaches through
``teaching_assignments`` is mirrored into ``teacher_subjects``. Deployed
teachers therefore keep (and gain) correctly scoped access immediately after
``alembic upgrade head``. The backfill is idempotent — rows that already exist
are skipped — so re-running or branching migrations is safe.

Dialect notes: table alterations run through ``batch_alter_table`` (a no-op on
PostgreSQL, a table rebuild on SQLite, which cannot ``ALTER TABLE ... ADD
CONSTRAINT``) and every constraint/index is explicitly named so both databases
end up with identical DDL. Boolean backfill values are compiled per dialect
(``sa.false()`` / ``sa.true()``) because SQLite stores ``0/1`` while PostgreSQL
requires ``true/false``, and compiling keeps offline ``--sql`` output valid.

Revision ID: 0a3d991221bb
Revises: f9da2d24c61a
Create Date: 2026-09-07 17:52:54.022360
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0a3d991221bb'
down_revision: Union[str, None] = 'f9da2d24c61a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Explicit constraint / index names (shared with app.models.auth).
PK_TEACHERS = "pk_teachers"
FK_TEACHERS_SCHOOL = "fk_teachers_school_id_private_schools"
FK_TEACHERS_USER = "fk_teachers_user_id_users"
UQ_TEACHERS_STAFF_IDENTIFIER = "uq_teachers_staff_identifier"
UQ_TEACHERS_SCHOOL_EMAIL = "uq_teachers_school_email"
IX_TEACHERS_SCHOOL_ID = "ix_teachers_school_id"
IX_TEACHERS_USER_ID = "ix_teachers_user_id"

PK_TEACHER_SUBJECTS = "pk_teacher_subjects"
FK_TS_TEACHER = "fk_teacher_subjects_teacher_id_teachers"
FK_TS_SUBJECT = "fk_teacher_subjects_subject_id_subjects"
FK_TS_SCHOOL = "fk_teacher_subjects_school_id_private_schools"
UQ_TEACHER_SUBJECT = "uq_teacher_subject"
IX_TS_TEACHER_ID = "ix_teacher_subjects_teacher_id"
IX_TS_SUBJECT_ID = "ix_teacher_subjects_subject_id"
IX_TS_SCHOOL_ID = "ix_teacher_subjects_school_id"


def _backfill_teacher_profiles() -> None:
    """Bind existing teacher accounts to profiles + subject mappings.

    Portable SQL through ``op.get_bind()``. Two details matter for
    cross-dialect behaviour:

    * booleans are rendered with ``sa.false()`` / ``sa.true()`` compiled for the
      target dialect (SQLite stores ``0/1``, PostgreSQL requires
      ``true/false``) instead of bound parameters, so the statement also comes
      out correct in offline ``alembic upgrade --sql`` mode where binds cannot
      be rendered;
    * ``created_at`` / ``updated_at`` are omitted and filled by their
      ``CURRENT_TIMESTAMP`` server defaults.
    """
    bind = op.get_bind()
    dialect = bind.dialect
    false_literal = sa.false().compile(dialect=dialect)
    true_literal = sa.true().compile(dialect=dialect)

    bind.execute(
        sa.text(
            f"""
            INSERT INTO teachers (
                school_id, user_id, staff_identifier, first_name, last_name, email,
                phone, designation, qualifications, bio, photo_url,
                is_department_head, is_active
            )
            SELECT
                u.school_id, u.id, u.staff_identifier,
                COALESCE(u.first_name, 'Unknown'), COALESCE(u.last_name, ''),
                u.email, u.phone, u.designation, u.qualifications, u.bio, u.photo_url,
                COALESCE(u.is_department_head, {false_literal}),
                COALESCE(u.is_active, {true_literal})
            FROM users u
            WHERE u.role = 'teacher'
              AND u.school_id IS NOT NULL
              AND NOT EXISTS (SELECT 1 FROM teachers t WHERE t.user_id = u.id)
            """
        )
    )

    bind.execute(
        sa.text(
            f"""
            INSERT INTO teacher_subjects (teacher_id, subject_id, school_id, is_primary)
            SELECT DISTINCT t.id, ta.subject_id, ta.school_id, {false_literal}
            FROM teachers t
            JOIN teaching_assignments ta ON ta.teacher_id = t.user_id
            WHERE t.user_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM teacher_subjects ts
                  WHERE ts.teacher_id = t.id AND ts.subject_id = ta.subject_id
              )
            """
        )
    )


def upgrade() -> None:
    # --- staff profiles -------------------------------------------------
    op.create_table(
        'teachers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('staff_identifier', sa.String(length=64), nullable=True),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('designation', sa.String(), nullable=True),
        sa.Column('qualifications', sa.String(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('photo_url', sa.String(length=500), nullable=True),
        sa.Column('is_department_head', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(
            ['school_id'], ['private_schools.id'], name=FK_TEACHERS_SCHOOL, ondelete='CASCADE'
        ),
        # SET NULL: deleting a login must not destroy the staff record.
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'], name=FK_TEACHERS_USER, ondelete='SET NULL'
        ),
        sa.PrimaryKeyConstraint('id', name=PK_TEACHERS),
        sa.UniqueConstraint('school_id', 'email', name=UQ_TEACHERS_SCHOOL_EMAIL),
        sa.UniqueConstraint('staff_identifier', name=UQ_TEACHERS_STAFF_IDENTIFIER),
    )
    # Batch mode: identical behaviour on PostgreSQL, table rebuild on SQLite.
    with op.batch_alter_table('teachers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f(IX_TEACHERS_SCHOOL_ID), ['school_id'], unique=False)
        # One profile per account.
        batch_op.create_index(batch_op.f(IX_TEACHERS_USER_ID), ['user_id'], unique=True)

    # --- subject-level teacher mapping ----------------------------------
    op.create_table(
        'teacher_subjects',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('teacher_id', sa.Integer(), nullable=False),
        sa.Column('subject_id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.Integer(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(
            ['school_id'], ['private_schools.id'], name=FK_TS_SCHOOL, ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['subject_id'], ['subjects.id'], name=FK_TS_SUBJECT, ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['teacher_id'], ['teachers.id'], name=FK_TS_TEACHER, ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('id', name=PK_TEACHER_SUBJECTS),
        sa.UniqueConstraint('teacher_id', 'subject_id', name=UQ_TEACHER_SUBJECT),
    )
    with op.batch_alter_table('teacher_subjects', schema=None) as batch_op:
        batch_op.create_index(batch_op.f(IX_TS_SCHOOL_ID), ['school_id'], unique=False)
        batch_op.create_index(batch_op.f(IX_TS_SUBJECT_ID), ['subject_id'], unique=False)
        batch_op.create_index(batch_op.f(IX_TS_TEACHER_ID), ['teacher_id'], unique=False)

    # --- portrait columns on the existing tables -------------------------
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_url', sa.String(length=500), nullable=True))

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_url', sa.String(length=500), nullable=True))

    # --- data backfill (idempotent) --------------------------------------
    _backfill_teacher_profiles()


def downgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('photo_url')

    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('photo_url')

    with op.batch_alter_table('teacher_subjects', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f(IX_TS_TEACHER_ID))
        batch_op.drop_index(batch_op.f(IX_TS_SUBJECT_ID))
        batch_op.drop_index(batch_op.f(IX_TS_SCHOOL_ID))

    op.drop_table('teacher_subjects')

    with op.batch_alter_table('teachers', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f(IX_TEACHERS_USER_ID))
        batch_op.drop_index(batch_op.f(IX_TEACHERS_SCHOOL_ID))

    op.drop_table('teachers')
