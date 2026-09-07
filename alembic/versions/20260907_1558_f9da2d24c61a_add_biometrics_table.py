"""add_biometrics_table

Adds fingerprint templates without changing the existing integer student IDs
or the separate WebAuthn tables. Constraints are explicitly named and the
finger-position enum uses a portable CHECK, not a PostgreSQL-only enum type.

Revision ID: f9da2d24c61a
Revises: 1c64b29eebdf
Create Date: 2026-09-07 15:58:16.253724
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9da2d24c61a"
down_revision: Union[str, None] = "1c64b29eebdf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_biometrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column(
            "finger_position",
            sa.Enum(
                "RIGHT_THUMB", "RIGHT_INDEX", "LEFT_THUMB", "LEFT_INDEX",
                name="ck_student_biometrics_finger_position",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="RIGHT_INDEX",
            nullable=False,
        ),
        sa.Column("template_data", sa.Text(), nullable=False),
        sa.Column("template_format", sa.String(length=50), server_default="ISO_19794_2", nullable=False),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("device_model", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["student_id"], ["students.id"],
            name="fk_student_biometrics_student_id_students", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_student_biometrics"),
    )
    # Keep table alterations in batch mode for SQLite/PostgreSQL compatibility.
    with op.batch_alter_table("student_biometrics", schema=None) as batch_op:
        batch_op.create_index("ix_student_biometrics_student_id", ["student_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("student_biometrics", schema=None) as batch_op:
        batch_op.drop_index("ix_student_biometrics_student_id")
    op.drop_table("student_biometrics")
