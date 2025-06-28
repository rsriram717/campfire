"""add provider columns to restaurant

Revision ID: 2024_03_14_02
Revises: 2024_03_14_01
Create Date: 2024-11-30 23:45:48.620832

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '2024_03_14_02'
down_revision = '2024_03_14_01'
branch_labels = None
depends_on = None

def upgrade():
    # Add new columns
    op.add_column('restaurant', sa.Column('provider', sa.String(length=20), nullable=False, server_default='google'))
    op.add_column('restaurant', sa.Column('place_id', sa.String(length=128), nullable=False, server_default='manual'))
    op.add_column('restaurant', sa.Column('slug', sa.String(length=200), nullable=False, server_default='default'))
    
    # Drop old unique constraint on name
    op.drop_constraint('restaurant_name_key', 'restaurant')
    
    # Add new unique constraints
    op.create_unique_constraint('uq_restaurant_provider_place', 'restaurant', ['provider', 'place_id'])
    op.create_unique_constraint('uq_restaurant_slug', 'restaurant', ['slug'])

def downgrade():
    # Drop new unique constraints
    op.drop_constraint('uq_restaurant_provider_place', 'restaurant')
    op.drop_constraint('uq_restaurant_slug', 'restaurant')
    
    # Restore old unique constraint on name
    op.create_unique_constraint('restaurant_name_key', 'restaurant', ['name'])
    
    # Drop new columns
    op.drop_column('restaurant', 'slug')
    op.drop_column('restaurant', 'place_id')
    op.drop_column('restaurant', 'provider') 