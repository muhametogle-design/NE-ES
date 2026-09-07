"""add_photos_and_teacher_user_scoping

Revision ID: 83dda6195453
Revises: f9da2d24c61a
Create Date: 2026-09-07 16:30:58.481046
"""
from typing import Sequence, Union

from alembic import context, op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '83dda6195453'
down_revision: Union[str, None] = 'f9da2d24c61a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Existing staff IDs are User IDs. Backfill Teacher.id with those IDs before
# repointing operational FKs; actor/audit FKs (marked_by, syllabus progress,
# etc.) deliberately continue to reference users.
TEACHER_REFERENCES = (
    ("teaching_assignments", "teacher_id"),
    ("timetable_slots", "teacher_id"),
    ("teacher_absences", "teacher_id"),
    ("substitution_assignments", "substitute_teacher_id"),
)
NAMING_CONVENTION = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}


def _legacy_fk_name(table: str, column: str) -> str:
    if context.is_offline_mode():
        # PostgreSQL's names for the unnamed FKs in the baseline migration.
        return f"{table}_{column}_fkey"
    for fk in sa.inspect(op.get_bind()).get_foreign_keys(table):
        if fk["constrained_columns"] == [column] and fk["referred_table"] == "users":
            # SQLite reflects the original FK with no name; batch mode's
            # naming convention gives that constraint an explicit drop target.
            return fk["name"] or f"fk_{table}_{column}_users"
    raise RuntimeError(f"Cannot find the legacy foreign key on {table}.{column}")


def _check_sqlite_batch_connection() -> None:
    # Alembic's own SQLite connection defaults to FK enforcement off while
    # batch tables are rebuilt. Never rebuild with it ON: dropping a parent
    # table would otherwise cascade-delete its existing children.
    if not context.is_offline_mode() and op.get_bind().dialect.name == "sqlite":
        if op.get_bind().exec_driver_sql("PRAGMA foreign_keys").scalar():
            raise RuntimeError("Run this SQLite batch migration with foreign_keys=OFF on the migration connection")


def upgrade() -> None:
    _check_sqlite_batch_connection()
    if not context.is_offline_mode():
        for table, column in TEACHER_REFERENCES:
            invalid = op.get_bind().execute(sa.text(f"""
                SELECT COUNT(*) FROM {table} r LEFT JOIN users u ON r.{column} = u.id
                WHERE u.id IS NULL OR u.school_id IS NULL
            """)).scalar()
            if invalid:
                # Check before CREATE/ALTER on SQLite's nontransactional DDL.
                raise RuntimeError("Assign legacy teaching staff to a school before migrating teacher scoping")
    # Generated with --autogenerate, then reviewed for data preservation and
    # explicit constraint names. INTEGER user_id matches the existing users.id;
    # changing just this FK to UUID is not valid on PostgreSQL.
    op.create_table('teachers',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('school_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('photo_url', sa.String(length=500), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('first_name', sa.String(), nullable=False),
        sa.Column('last_name', sa.String(), nullable=False),
        sa.Column('staff_identifier', sa.String(), nullable=True),
        sa.Column('phone', sa.String(), nullable=True),
        sa.Column('qualifications', sa.String(), nullable=True),
        sa.Column('designation', sa.String(), nullable=True),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('is_department_head', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['school_id'], ['private_schools.id'], name='fk_teachers_school_id_private_schools', ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name='fk_teachers_user_id_users', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id', name='pk_teachers'),
        sa.UniqueConstraint('staff_identifier', name='uq_teachers_staff_identifier'),
        sa.UniqueConstraint('user_id', name='uq_teachers_user_id')
    )
    with op.batch_alter_table('teachers', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_teachers_school_id'), ['school_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_teachers_user_id'), ['user_id'], unique=False)

    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('photo_url', sa.String(length=500), nullable=True))

    # Include referenced legacy staff as well as teacher-role logins. This
    # preserves historical assignments without changing any User privileges.
    references = " UNION ".join(f"SELECT {column} FROM {table}" for table, column in TEACHER_REFERENCES)
    op.execute(sa.text(f"""
        INSERT INTO teachers (
            id, school_id, user_id, email, first_name, last_name,
            staff_identifier, phone, qualifications, designation, bio,
            is_department_head, is_active, created_at
        )
        SELECT id, school_id, id, email, COALESCE(first_name, ''), COALESCE(last_name, ''),
            staff_identifier, phone, qualifications, designation, bio,
            COALESCE(is_department_head, false), COALESCE(is_active, true),
            COALESCE(created_at, CURRENT_TIMESTAMP)
        FROM users
        WHERE school_id IS NOT NULL AND (role = 'teacher' OR id IN ({references}))
    """))
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("""
            SELECT setval(pg_get_serial_sequence('teachers', 'id'),
                COALESCE((SELECT MAX(id) FROM teachers), 1),
                EXISTS (SELECT 1 FROM teachers))
        """))

    for table, column in TEACHER_REFERENCES:
        old_name = _legacy_fk_name(table, column)
        with op.batch_alter_table(table, naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.drop_constraint(old_name, type_='foreignkey')
            batch_op.create_foreign_key(
                f"fk_{table}_{column}_teachers", 'teachers', [column], ['id'], ondelete='CASCADE',
            )


def downgrade() -> None:
    _check_sqlite_batch_connection()
    if not context.is_offline_mode():
        # The old schema cannot represent an assigned teacher without a User.
        # Fail before any DDL rather than deleting academic history implicitly.
        for table, column in TEACHER_REFERENCES:
            unlinked = op.get_bind().execute(sa.text(f"""
                SELECT COUNT(*) FROM {table} r JOIN teachers t ON r.{column} = t.id
                WHERE t.user_id IS NULL
            """)).scalar()
            if unlinked:
                raise RuntimeError("Link assigned teachers to users before downgrading teacher scoping")

    for table, column in reversed(TEACHER_REFERENCES):
        with op.batch_alter_table(table, naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_{column}_teachers", type_='foreignkey')
        # New or rebound profiles need not have the same ID as their login.
        op.execute(sa.text(f"""
            UPDATE {table} SET {column} = (
                SELECT user_id FROM teachers WHERE teachers.id = {table}.{column}
            )
        """))
        with op.batch_alter_table(table, naming_convention=NAMING_CONVENTION) as batch_op:
            batch_op.create_foreign_key(
                f"{table}_{column}_fkey", 'users', [column], ['id'], ondelete='CASCADE',
            )

    with op.batch_alter_table('students') as batch_op:
        batch_op.drop_column('photo_url')
    with op.batch_alter_table('teachers') as batch_op:
        batch_op.drop_index('ix_teachers_user_id')
        batch_op.drop_index('ix_teachers_school_id')
    op.drop_table('teachers')
