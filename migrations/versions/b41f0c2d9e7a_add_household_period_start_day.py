"""Add household budget period start day

Revision ID: b41f0c2d9e7a
Revises: 6dc5cdabe637
Create Date: 2026-10-26 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b41f0c2d9e7a'
down_revision = '6dc5cdabe637'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('households', schema=None) as batch_op:
        batch_op.add_column(sa.Column('period_start_day', sa.Integer(), server_default='1', nullable=False))


def downgrade():
    with op.batch_alter_table('households', schema=None) as batch_op:
        batch_op.drop_column('period_start_day')
