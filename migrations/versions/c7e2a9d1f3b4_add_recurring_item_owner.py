"""Add recurring item owner

Revision ID: c7e2a9d1f3b4
Revises: b41f0c2d9e7a
Create Date: 2026-10-26 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c7e2a9d1f3b4'
down_revision = 'b41f0c2d9e7a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('recurring_items', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_recurring_items_user_id_users', 'users', ['user_id'], ['id'])


def downgrade():
    with op.batch_alter_table('recurring_items', schema=None) as batch_op:
        batch_op.drop_constraint('fk_recurring_items_user_id_users', type_='foreignkey')
        batch_op.drop_column('user_id')
