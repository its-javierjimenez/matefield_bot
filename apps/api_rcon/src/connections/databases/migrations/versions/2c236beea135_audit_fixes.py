"""audit_fixes

Revision ID: 2c236beea135
Revises: a82b4eba14e5
Create Date: 2026-10-04 00:47:49.897573

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2c236beea135'
down_revision: Union[str, Sequence[str], None] = 'a82b4eba14e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. LIMPIEZA DE STEAM IDs CORRUPTOS
    op.execute("DELETE FROM player_roles WHERE steam_id != UPPER(TRIM(steam_id))")
    op.execute("DELETE FROM player_sessions WHERE steam_id != UPPER(TRIM(steam_id))")
    op.execute("DELETE FROM memberships WHERE steam_id != UPPER(TRIM(steam_id))")
    op.execute("DELETE FROM reward_claims WHERE steam_id != UPPER(TRIM(steam_id))")
    op.execute("DELETE FROM players WHERE steam_id != UPPER(TRIM(steam_id))")

    # 2. LIMPIEZA DE FECHAS CORRUPTAS
    op.execute("DELETE FROM memberships WHERE end_date IS NOT NULL AND start_date > end_date")

    # 3. CONVERSIÓN FINANCIERA (Flotante -> Entero Centavos)
    op.execute("ALTER TABLE membership_types ADD COLUMN price_cents INTEGER DEFAULT 0")
    op.execute("UPDATE membership_types SET price_cents = CAST(price_usd * 100 AS INTEGER)")
    op.execute("ALTER TABLE membership_types DROP COLUMN price_usd")
    op.execute("ALTER TABLE membership_types RENAME COLUMN price_cents TO price_usd")

    # 4. EXPANSIÓN DE LÍMITES DE TEXTO (bot_config)
    op.execute("ALTER TABLE bot_config ALTER COLUMN config_value TYPE TEXT")

    # 5. RESTRICCIONES DE INTEGRIDAD ESTRICTAS (Check Constraints)
    op.execute("ALTER TABLE players ADD CONSTRAINT check_player_points_positive CHECK (reward_points >= 0)")
    op.execute("ALTER TABLE reward_claims ADD CONSTRAINT check_claim_points_positive CHECK (points_spent >= 0)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("ALTER TABLE reward_claims DROP CONSTRAINT check_claim_points_positive")
    op.execute("ALTER TABLE players DROP CONSTRAINT check_player_points_positive")
    op.execute("ALTER TABLE bot_config ALTER COLUMN config_value TYPE VARCHAR(255)")
    
    op.execute("ALTER TABLE membership_types ADD COLUMN price_float DOUBLE PRECISION DEFAULT 0.0")
    op.execute("UPDATE membership_types SET price_float = CAST(price_usd AS DOUBLE PRECISION) / 100.0")
    op.execute("ALTER TABLE membership_types DROP COLUMN price_usd")
    op.execute("ALTER TABLE membership_types RENAME COLUMN price_float TO price_usd")
