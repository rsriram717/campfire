"""increase cuisine_type length to 200

Revision ID: 2024_03_14_01
Revises: c9e344f09bd8
Create Date: 2024-03-14 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2024_03_14_01'
down_revision = 'c9e344f09bd8'
branch_labels = None
depends_on = None

def upgrade():
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('restaurant') as batch_op:
        batch_op.alter_column('cuisine_type',
                            existing_type=sa.String(50),
                            type_=sa.String(200),
                            existing_nullable=True)

def downgrade():
    # Use batch mode for SQLite compatibility
    with op.batch_alter_table('restaurant') as batch_op:
        batch_op.alter_column('cuisine_type',
                            existing_type=sa.String(200),
                            type_=sa.String(50),
                            existing_nullable=True) 