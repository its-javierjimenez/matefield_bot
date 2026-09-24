"""Add is_booster to memberships

Revision ID: f2b3c4d5e6a7
Revises: e1a2b3c4d5e6
Create Date: 2026-09-22 05:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f2b3c4d5e6a7'
down_revision: Union[str, Sequence[str], None] = 'e1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('memberships', sa.Column('is_booster', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade() -> None:
    op.drop_column('memberships', 'is_booster')
