"""cuisine_type_to_text

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('restaurant') as batch_op:
        batch_op.alter_column('cuisine_type',
                              existing_type=sa.String(200),
                              type_=sa.Text(),
                              existing_nullable=True)


def downgrade():
    with op.batch_alter_table('restaurant') as batch_op:
        batch_op.alter_column('cuisine_type',
                              existing_type=sa.Text(),
                              type_=sa.String(200),
                              existing_nullable=True)
