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
    carrier_count: int = Field(
        default=0, ge=0, le=30, description="Models carrying this weapon; 0 means all"
    )

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
    # Datasheet keywords; MONSTER and VEHICLE ignore the Pistol firing restriction.
    keywords: list[str] = []
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

    @field_validator("keywords", mode="before")
    @classmethod
    def split_keywords(cls, value: object) -> object:
        """The ORM stores keywords as a comma-separated string."""
        if isinstance(value, str):
            return [k.strip() for k in value.split(",") if k.strip()]
        return value


# --- Games -----------------------------------------------------------------

class ArmyUnitSummary(BaseModel):
    """Lightweight entry for the polled game state, including live condition.

    `id` is the GameUnit id (this unit in this game), not the roster Unit id.
    """

    id: int
    unit_id: int
    name: str
    points: int
    # Profile, so the UI can render "4 / 10 models" without another request.
    model_count: int
    wounds: int
    leadership: int
    # Live state.
    models_remaining: int
    wounds_lost: int
    is_destroyed: bool
    below_half_strength: bool
    is_battle_shocked: bool
    needs_shock_test: bool
    # Shooting phase: a unit shoots once per phase.
    has_shot: bool = False


class GamePlayerOut(BaseModel):
    player: PlayerOut
    is_ready: bool
    turn_order: int
    faction: str = ""
    army: list[ArmyUnitSummary] = []
    army_points: int = 0
    command_points: int = 0


class ApplyWoundsIn(BaseModel):
    """Positive damages the unit, negative heals and doubles as undo."""

    wounds: int = Field(ge=-100, le=100)


class BattleShockIn(BaseModel):
    """The 2D6 total the player physically rolled."""

    roll: int = Field(ge=2, le=12)


class BattleShockResult(BaseModel):
    unit_name: str
    roll: int
    leadership: int
    passed: bool
    game: "GameOut"


# --- Shooting --------------------------------------------------------------

class ShootIn(BaseModel):
    """A shooting attack: one attacker, a SET of weapons, one target.

    Several weapons at once because a model fires all its non-pistol ranged
    weapons simultaneously.
    """

    attacker_game_unit_id: int
    weapon_ids: list[int] = Field(min_length=1, max_length=20)
    target_game_unit_id: int


class AttackRollOut(BaseModel):
    """A rolled attack awaiting confirmation. `rolls` is the dice structure
    produced by services/attack_roll.resolve_shooting."""

    id: int
    applied: bool
    resolved: bool
    attacker_name: str
    target_name: str
    rolls: dict


class SetArmyIn(BaseModel):
    """The units a player brings to a game. All must share one faction."""

    unit_ids: list[int] = Field(min_length=1, max_length=50)


class GameArmyOut(BaseModel):
    """Full unit data for one player's army (used by the combat resolver)."""

    player: PlayerOut
    faction: str
    units: list[UnitOut]


class GameOut(BaseModel):
    id: int
    code: str
    status: GameStatus
    current_phase: int
    phase_name: str
    current_round: int
    active_player_id: int | None
    players: list[GamePlayerOut]
    # An attack that has been rolled but not yet confirmed or discarded. The
    # dice themselves are fetched separately to keep the polled payload small.
    pending_attack_id: int | None = None


class JoinGameIn(BaseModel):
    code: str = Field(min_length=4, max_length=8)


class GameSummaryOut(BaseModel):
    """One row in the games list. Deliberately light: no armies or dice."""

    id: int
    code: str
    status: GameStatus
    current_round: int
    phase_name: str
    player_count: int
    player_names: list[str]
    creator_name: str | None
    is_member: bool
    can_join: bool
    can_delete: bool


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
