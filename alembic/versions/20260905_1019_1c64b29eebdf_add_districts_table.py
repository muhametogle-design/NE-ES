"""add_districts_table

Adds the ``districts`` reference table (Regional Education Offices) and an
optional ``private_schools.district_id`` foreign key (ON DELETE SET NULL).

Revision ID: 1c64b29eebdf
Revises: 6017c4a7f9d5
Create Date: 2026-09-05 10:19:39.093473
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1c64b29eebdf'
down_revision: Union[str, None] = '6017c4a7f9d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_SCHOOL_DISTRICT = "fk_private_schools_district_id_districts"


def upgrade() -> None:
    op.create_table(
        'districts',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.String(length=16), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('region', sa.String(length=128), nullable=False),
        sa.Column('reo_contact_email', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_districts_code'), 'districts', ['code'], unique=True)
    op.create_index(op.f('ix_districts_region'), 'districts', ['region'], unique=False)

    # batch mode is a no-op on PostgreSQL and lets the same migration run on
    # SQLite (which cannot ALTER TABLE ... ADD CONSTRAINT) — same convention as
    # the baseline revision.
    with op.batch_alter_table('private_schools', schema=None) as batch_op:
        batch_op.add_column(sa.Column('district_id', sa.Uuid(), nullable=True))
        batch_op.create_index(batch_op.f('ix_private_schools_district_id'), ['district_id'], unique=False)
        batch_op.create_foreign_key(
            FK_SCHOOL_DISTRICT, 'districts', ['district_id'], ['id'], ondelete='SET NULL'
        )


def downgrade() -> None:
    with op.batch_alter_table('private_schools', schema=None) as batch_op:
        batch_op.drop_constraint(FK_SCHOOL_DISTRICT, type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_private_schools_district_id'))
        batch_op.drop_column('district_id')

    op.drop_index(op.f('ix_districts_region'), table_name='districts')
    op.drop_index(op.f('ix_districts_code'), table_name='districts')
    op.drop_table('districts')
