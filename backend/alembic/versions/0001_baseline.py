"""Baseline: the schema as it was before Alembic existed.

This revision is deliberately IDEMPOTENT. QuickHammer was deployed before
Alembic was introduced, so a real database may already have all of these
tables, some of them, or none. Rather than stamping (which cannot know which
tables are missing), this revision creates only what is absent and adds the
columns that were once applied by hand. Running `upgrade head` therefore
converges any database, new or old, onto the same schema.

Everything here describes the schema AT THIS POINT IN HISTORY. Never update it
to match newer models; later revisions do that.

Revision ID: 0001_baseline
Revises: None
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Columns that were added by hand to already-deployed tables, before Alembic.
_LEGACY_COLUMNS = [
    ("players", "is_admin", sa.Boolean(), "0"),
    ("units", "faction", sa.String(length=100), "''"),
    ("units", "points", sa.Integer(), "0"),
    ("game_players", "faction", sa.String(length=100), "''"),
]


def _existing_tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _existing_columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    present = _existing_tables()

    if "players" not in present:
        op.create_table(
            "players",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=50), nullable=False),
            sa.Column("password_hash", sa.String(length=200), nullable=False),
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="0"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_players_name"), "players", ["name"], unique=True)

    if "units" not in present:
        op.create_table(
            "units",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("image_path", sa.String(length=300), nullable=True),
            sa.Column("faction", sa.String(length=100), nullable=False, server_default="''"),
            sa.Column("points", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("movement", sa.Integer(), nullable=False),
            sa.Column("toughness", sa.Integer(), nullable=False),
            sa.Column("save", sa.Integer(), nullable=False),
            sa.Column("invuln_save", sa.Integer(), nullable=True),
            sa.Column("wounds", sa.Integer(), nullable=False),
            sa.Column("leadership", sa.Integer(), nullable=False),
            sa.Column("oc", sa.Integer(), nullable=False),
            sa.Column("model_count", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["owner_id"], ["players.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_units_owner_id"), "units", ["owner_id"], unique=False)

    if "weapons" not in present:
        op.create_table(
            "weapons",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("unit_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("kind", sa.Enum("ranged", "melee", name="weaponkind"), nullable=False),
            sa.Column("range", sa.Integer(), nullable=False),
            sa.Column("attacks", sa.String(length=20), nullable=False),
            sa.Column("skill", sa.Integer(), nullable=False),
            sa.Column("strength", sa.Integer(), nullable=False),
            sa.Column("ap", sa.Integer(), nullable=False),
            sa.Column("damage", sa.String(length=20), nullable=False),
            sa.Column("keywords", sa.String(length=300), nullable=False),
            sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_weapons_unit_id"), "weapons", ["unit_id"], unique=False)

    if "games" not in present:
        op.create_table(
            "games",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=8), nullable=False),
            sa.Column(
                "status",
                sa.Enum("lobby", "active", "finished", name="gamestatus"),
                nullable=False,
            ),
            sa.Column("current_phase", sa.Integer(), nullable=False),
            sa.Column("current_round", sa.Integer(), nullable=False),
            sa.Column("active_player_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["active_player_id"], ["players.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_games_code"), "games", ["code"], unique=True)

    if "game_players" not in present:
        op.create_table(
            "game_players",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=False),
            sa.Column("player_id", sa.Integer(), nullable=False),
            sa.Column("is_ready", sa.Boolean(), nullable=False),
            sa.Column("turn_order", sa.Integer(), nullable=False),
            sa.Column("faction", sa.String(length=100), nullable=False, server_default="''"),
            sa.ForeignKeyConstraint(["game_id"], ["games.id"]),
            sa.ForeignKeyConstraint(["player_id"], ["players.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("game_id", "player_id"),
        )
        op.create_index(
            op.f("ix_game_players_game_id"), "game_players", ["game_id"], unique=False
        )

    if "game_units" not in present:
        op.create_table(
            "game_units",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("game_player_id", sa.Integer(), nullable=False),
            sa.Column("unit_id", sa.Integer(), nullable=False),
            sa.ForeignKeyConstraint(["game_player_id"], ["game_players.id"]),
            sa.ForeignKeyConstraint(["unit_id"], ["units.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("game_player_id", "unit_id"),
        )
        op.create_index(
            op.f("ix_game_units_game_player_id"), "game_units", ["game_player_id"], unique=False
        )
        op.create_index(op.f("ix_game_units_unit_id"), "game_units", ["unit_id"], unique=False)

    # Tables that already existed may pre-date these columns.
    for table, column, coltype, default in _LEGACY_COLUMNS:
        if table in present and column not in _existing_columns(table):
            op.add_column(
                table,
                sa.Column(column, coltype, nullable=False, server_default=default),
            )


def downgrade() -> None:
    op.drop_table("game_units")
    op.drop_table("game_players")
    op.drop_table("games")
    op.drop_table("weapons")
    op.drop_table("units")
    op.drop_table("players")
