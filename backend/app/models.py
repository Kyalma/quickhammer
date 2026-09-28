"""ORM models: Player, Unit, Weapon, Game, GamePlayer."""
from __future__ import annotations

import enum

from sqlalchemy import Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# The five phases of a Warhammer 40k player turn, in order.
PHASES = ["Command", "Movement", "Shooting", "Charge", "Fight"]


class WeaponKind(str, enum.Enum):
    ranged = "ranged"
    melee = "melee"


class GameStatus(str, enum.Enum):
    lobby = "lobby"
    active = "active"
    finished = "finished"


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    is_admin: Mapped[bool] = mapped_column(default=False)

    units: Mapped[list[Unit]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    image_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    faction: Mapped[str] = mapped_column(String(100), default="")
    points: Mapped[int] = mapped_column(Integer, default=0)

    # 10th-edition statline
    movement: Mapped[int] = mapped_column(Integer, default=6)      # inches
    toughness: Mapped[int] = mapped_column(Integer, default=4)
    save: Mapped[int] = mapped_column(Integer, default=3)          # e.g. 3 means 3+
    invuln_save: Mapped[int | None] = mapped_column(Integer, nullable=True)
    wounds: Mapped[int] = mapped_column(Integer, default=2)        # per model
    leadership: Mapped[int] = mapped_column(Integer, default=6)
    oc: Mapped[int] = mapped_column(Integer, default=1)            # objective control
    model_count: Mapped[int] = mapped_column(Integer, default=1)

    owner: Mapped[Player] = relationship(back_populates="units")
    weapons: Mapped[list[Weapon]] = relationship(
        back_populates="unit", cascade="all, delete-orphan"
    )
    # Deleting a unit also removes it from any game army it was picked for.
    game_entries: Mapped[list[GameUnit]] = relationship(
        back_populates="unit", cascade="all, delete-orphan"
    )


class Weapon(Base):
    __tablename__ = "weapons"

    id: Mapped[int] = mapped_column(primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[WeaponKind] = mapped_column(Enum(WeaponKind), default=WeaponKind.ranged)

    range: Mapped[int] = mapped_column(Integer, default=24)        # inches; 0 for melee
    attacks: Mapped[str] = mapped_column(String(20), default="1")  # dice notation: "2", "D6", "2D6+1"
    skill: Mapped[int] = mapped_column(Integer, default=3)         # BS/WS, e.g. 3 means 3+
    strength: Mapped[int] = mapped_column(Integer, default=4)
    ap: Mapped[int] = mapped_column(Integer, default=0)            # stored positive: 2 means AP-2
    damage: Mapped[str] = mapped_column(String(20), default="1")   # dice notation
    keywords: Mapped[str] = mapped_column(String(300), default="") # comma-separated

    unit: Mapped[Unit] = relationship(back_populates="weapons")


class Game(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    status: Mapped[GameStatus] = mapped_column(Enum(GameStatus), default=GameStatus.lobby)
    current_phase: Mapped[int] = mapped_column(Integer, default=0)   # index into PHASES
    current_round: Mapped[int] = mapped_column(Integer, default=1)
    active_player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"), nullable=True)

    players: Mapped[list[GamePlayer]] = relationship(
        back_populates="game", cascade="all, delete-orphan", order_by="GamePlayer.turn_order"
    )


class GamePlayer(Base):
    __tablename__ = "game_players"
    __table_args__ = (UniqueConstraint("game_id", "player_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("games.id"), index=True)
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    is_ready: Mapped[bool] = mapped_column(default=False)
    turn_order: Mapped[int] = mapped_column(Integer, default=0)
    # The single faction this player brings to the game ("" = Unaligned).
    faction: Mapped[str] = mapped_column(String(100), default="")
    # Gained at the start of each of this player's Command phases.
    command_points: Mapped[int] = mapped_column(Integer, default=0)

    game: Mapped[Game] = relationship(back_populates="players")
    player: Mapped[Player] = relationship()
    army: Mapped[list[GameUnit]] = relationship(
        back_populates="game_player", cascade="all, delete-orphan"
    )


class GameUnit(Base):
    """One unit a player selected for one game (their army for that match)."""

    __tablename__ = "game_units"
    __table_args__ = (UniqueConstraint("game_player_id", "unit_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_player_id: Mapped[int] = mapped_column(ForeignKey("game_players.id"), index=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), index=True)

    # Live battlefield state. Losses are stored rather than remainders so that
    # zero always means "undamaged", which keeps migrations trivial.
    models_lost: Mapped[int] = mapped_column(Integer, default=0)
    # Damage on the current lead model only, never a whole model's worth.
    wounds_lost: Mapped[int] = mapped_column(Integer, default=0)
    is_battle_shocked: Mapped[bool] = mapped_column(default=False)
    # Round in which a Battle-shock test was taken, to block re-tests.
    shock_tested_round: Mapped[int | None] = mapped_column(Integer, nullable=True)

    game_player: Mapped[GamePlayer] = relationship(back_populates="army")
    unit: Mapped[Unit] = relationship(back_populates="game_entries")
