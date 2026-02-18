"""add_rich_metadata_to_restaurant

Revision ID: a1b2c3d4e5f6
Revises: 078519919b65
Create Date: 2026-02-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = '078519919b65'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('restaurant', schema=None) as batch_op:
        batch_op.add_column(sa.Column('price_level', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('rating', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('user_rating_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('editorial_summary', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('primary_type', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('serves_dine_in', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('serves_takeout', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('serves_delivery', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('reservable', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('last_enriched_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('city_hint', sa.String(100), nullable=True))


def downgrade():
    with op.batch_alter_table('restaurant', schema=None) as batch_op:
        batch_op.drop_column('city_hint')
        batch_op.drop_column('last_enriched_at')
        batch_op.drop_column('reservable')
        batch_op.drop_column('serves_delivery')
        batch_op.drop_column('serves_takeout')
        batch_op.drop_column('serves_dine_in')
        batch_op.drop_column('primary_type')
        batch_op.drop_column('editorial_summary')
        batch_op.drop_column('user_rating_count')
        batch_op.drop_column('rating')
        batch_op.drop_column('price_level')
