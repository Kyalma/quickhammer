"""Record who created each game, so lobby deletion can be authorised.

Backfills existing rows from join order: create_game always adds the creator
first, with turn_order 0.

Revision ID: 0004_game_creator
Revises: 0003_shooting
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_game_creator"
down_revision: Union[str, None] = "0003_shooting"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("games", schema=None) as batch_op:
        batch_op.add_column(sa.Column("creator_player_id", sa.Integer(), nullable=True))

    # Existing games: the player who joined first is the creator.
    op.execute(
        """
        UPDATE games SET creator_player_id = (
            SELECT gp.player_id FROM game_players gp
            WHERE gp.game_id = games.id
            ORDER BY gp.turn_order, gp.id
            LIMIT 1
        )
        WHERE creator_player_id IS NULL
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("games", schema=None) as batch_op:
        batch_op.drop_column("creator_player_id")
