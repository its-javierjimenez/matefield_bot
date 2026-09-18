"""Change role_type to VARCHAR(50) to support dynamic role types

Revision ID: e1a2b3c4d5e6
Revises: 0e7d9f2ccf83
Create Date: 2026-09-18 05:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'e1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = '0e7d9f2ccf83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("ALTER TABLE roles ALTER COLUMN role_type TYPE VARCHAR(50) USING role_type::text")

def downgrade() -> None:
    pass
