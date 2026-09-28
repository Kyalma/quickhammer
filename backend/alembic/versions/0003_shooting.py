"""Shooting phase: unit keywords, weapon carriers, shot tracking, attack rolls.

Written by hand rather than taken raw from autogenerate: every non-nullable
column needs a server_default or the ALTER fails on a table that already has
rows, which is exactly the live database this protects.

Revision ID: 0003_shooting
Revises: 0002_command_phase
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_shooting"
down_revision: Union[str, None] = "0002_command_phase"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("units", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("keywords", sa.String(length=500), nullable=False, server_default="")
        )

    with op.batch_alter_table("weapons", schema=None) as batch_op:
        # 0 means "every model in the unit carries this".
        batch_op.add_column(
            sa.Column("carrier_count", sa.Integer(), nullable=False, server_default="0")
        )

    with op.batch_alter_table("game_units", schema=None) as batch_op:
        # Null means "has not shot"; no default needed.
        batch_op.add_column(sa.Column("shot_in_round", sa.Integer(), nullable=True))

    op.create_table(
        "attack_rolls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("game_id", sa.Integer(), nullable=False),
        sa.Column("attacker_game_unit_id", sa.Integer(), nullable=False),
        sa.Column("target_game_unit_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("resolved_round", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
        sa.ForeignKeyConstraint(["attacker_game_unit_id"], ["game_units.id"]),
        sa.ForeignKeyConstraint(["target_game_unit_id"], ["game_units.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_attack_rolls_game_id"), "attack_rolls", ["game_id"], unique=False)


def downgrade() -> None:
    op.drop_table("attack_rolls")

    with op.batch_alter_table("game_units", schema=None) as batch_op:
        batch_op.drop_column("shot_in_round")

    with op.batch_alter_table("weapons", schema=None) as batch_op:
        batch_op.drop_column("carrier_count")

    with op.batch_alter_table("units", schema=None) as batch_op:
        batch_op.drop_column("keywords")
