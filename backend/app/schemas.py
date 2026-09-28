"""Pydantic request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .models import GameStatus, WeaponKind
from .services.combat import parse_dice


# --- Players ---------------------------------------------------------------

class PlayerCredentials(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    password: str = Field(min_length=4, max_length=100)


class PlayerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    is_admin: bool = False


class TokenOut(BaseModel):
    token: str
    player: PlayerOut


# --- Units & weapons -------------------------------------------------------

class WeaponIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: WeaponKind = WeaponKind.ranged
    range: int = Field(default=24, ge=0, le=120)
    attacks: str = "1"
    skill: int = Field(default=3, ge=2, le=6)
    strength: int = Field(default=4, ge=1, le=24)
    ap: int = Field(default=0, ge=0, le=6, description="Positive number: 2 means AP-2")
    damage: str = "1"
    keywords: list[str] = []

    @field_validator("attacks", "damage")
    @classmethod
    def valid_dice_notation(cls, value: str) -> str:
        """Accept flat numbers or dice notation: '2', 'D6', 'D6+1', '2D6+1'."""
        parse_dice(value)  # raises ValueError -> 422 with the message
        return value.strip().upper()


class WeaponOut(WeaponIn):
    model_config = ConfigDict(from_attributes=True)

    id: int

    @field_validator("keywords", mode="before")
    @classmethod
    def split_keywords(cls, value: object) -> object:
        """The ORM stores keywords as a comma-separated string."""
        if isinstance(value, str):
            return [k.strip() for k in value.split(",") if k.strip()]
        return value


class UnitIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    faction: str = Field(default="", max_length=100)
    points: int = Field(default=0, ge=0, le=10000)
    movement: int = Field(default=6, ge=0, le=30)
    toughness: int = Field(default=4, ge=1, le=16)
    save: int = Field(default=3, ge=2, le=7)
    invuln_save: int | None = Field(default=None, ge=2, le=6)
    wounds: int = Field(default=2, ge=1, le=40)
    leadership: int = Field(default=6, ge=4, le=10)
    oc: int = Field(default=1, ge=0, le=10)
    model_count: int = Field(default=1, ge=1, le=30)
    weapons: list[WeaponIn] = []


class UnitOut(UnitIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    image_path: str | None = None
    weapons: list[WeaponOut] = []


# --- Games -----------------------------------------------------------------

class GamePlayerOut(BaseModel):
    player: PlayerOut
    is_ready: bool
    turn_order: int


class GameOut(BaseModel):
    id: int
    code: str
    status: GameStatus
    current_phase: int
    phase_name: str
    current_round: int
    active_player_id: int | None
    players: list[GamePlayerOut]


class JoinGameIn(BaseModel):
    code: str = Field(min_length=4, max_length=8)


# --- Combat ----------------------------------------------------------------

class CombatRequest(BaseModel):
    attacker_unit_id: int
    weapon_id: int
    defender_unit_id: int


class CombatStep(BaseModel):
    label: str
    value: float
    detail: str


class CombatResult(BaseModel):
    attacker: str
    weapon: str
    defender: str
    steps: list[CombatStep]
    expected_damage: float
    expected_models_slain: float
    notes: list[str] = []
