"""Shooting phase: roll an attack, look at the dice, then confirm or discard.

Dice are rolled on the server and stored, so refreshing the page cannot re-roll
a bad result. Rolling spends the unit's shot for the phase; discarding is a full
undo and gives it back, so a mis-picked target or weapon can be corrected.
"""
import json
import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_player
from ..database import get_db
from ..models import PHASES, AttackRoll, Game, GameStatus, GameUnit, Player
from ..schemas import AttackRollOut, GameOut, ShootIn
from ..services import attack_roll as roller
from ..services import combat, unit_state
from .games import get_game, serialize_game

router = APIRouter(prefix="/api/games", tags=["shooting"])

SHOOTING_PHASE = PHASES.index("Shooting")


def _entry(game: Game, game_unit_id: int) -> tuple[GameUnit, int]:
    """Find a unit in this game. Returns (entry, owning player id)."""
    for gp in game.players:
        for entry in gp.army:
            if entry.id == game_unit_id:
                return entry, gp.player_id
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit is not in this game")


def _require_shooting_turn(game: Game, player: Player) -> None:
    if game.status != GameStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game is not active")
    if game.current_phase != SHOOTING_PHASE:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Shooting attacks happen in the Shooting phase"
        )
    if game.active_player_id != player.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "It is not your turn")


def _serialize_roll(roll: AttackRoll, game: Game) -> AttackRollOut:
    attacker, _ = _entry(game, roll.attacker_game_unit_id)
    target, _ = _entry(game, roll.target_game_unit_id)
    return AttackRollOut(
        id=roll.id,
        applied=roll.applied,
        resolved=roll.resolved,
        attacker_name=attacker.unit.name,
        target_name=target.unit.name,
        rolls=json.loads(roll.payload),
    )


def _get_roll(game: Game, roll_id: int) -> AttackRoll:
    for roll in game.attack_rolls:
        if roll.id == roll_id:
            return roll
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Attack roll not found")


@router.post("/{code}/shooting/resolve", response_model=AttackRollOut,
             status_code=status.HTTP_201_CREATED)
def resolve_shooting(
    code: str,
    body: ShootIn,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> AttackRollOut:
    """Roll a shooting attack. Spends the attacker's shot until it is discarded."""
    game = get_game(code, db)
    _require_shooting_turn(game, player)

    attacker, attacker_owner = _entry(game, body.attacker_game_unit_id)
    if attacker_owner != player.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only shoot with your own units")
    if unit_state.is_destroyed(attacker.models_lost, attacker.unit.model_count):
        raise HTTPException(status.HTTP_409_CONFLICT, "That unit has been destroyed")
    if attacker.shot_in_round == game.current_round:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That unit has already shot this phase"
        )

    target, target_owner = _entry(game, body.target_game_unit_id)
    if target_owner == player.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot shoot your own unit")
    if unit_state.is_destroyed(target.models_lost, target.unit.model_count):
        raise HTTPException(status.HTTP_409_CONFLICT, "That target has been destroyed")

    # Resolve the chosen weapons against the attacker's datasheet.
    by_id = {w.id: w for w in attacker.unit.weapons}
    missing = [wid for wid in body.weapon_ids if wid not in by_id]
    if missing:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "One or more weapons are not on that unit"
        )
    chosen = [by_id[wid] for wid in dict.fromkeys(body.weapon_ids)]

    unit_keywords = [k.strip() for k in attacker.unit.keywords.split(",") if k.strip()]
    selection = [
        (w.name, w.kind.value, [k.strip() for k in w.keywords.split(",") if k.strip()])
        for w in chosen
    ]
    error = combat.weapon_selection_error(unit_keywords, selection)
    if error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, error)

    profiles = [
        roller.WeaponProfile(
            name=w.name,
            attacks=w.attacks,
            skill=w.skill,
            strength=w.strength,
            ap=w.ap,
            damage=w.damage,
            keywords=[k.strip() for k in w.keywords.split(",") if k.strip()],
            carriers=w.carrier_count,
        )
        for w in chosen
    ]
    target_profile = roller.TargetProfile(
        name=target.unit.name,
        toughness=target.unit.toughness,
        save=target.unit.save,
        invuln_save=target.unit.invuln_save,
        wounds=target.unit.wounds,
        model_count=target.unit.model_count,
        models_lost=target.models_lost,
        wounds_lost=target.wounds_lost,
    )

    attacker_models = unit_state.models_remaining(
        attacker.models_lost, attacker.unit.model_count
    )
    try:
        rolled = roller.resolve_shooting(
            profiles, attacker_models, target_profile, random.Random()
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    roll = AttackRoll(
        game_id=game.id,
        attacker_game_unit_id=attacker.id,
        target_game_unit_id=target.id,
        payload=json.dumps(rolled),
        resolved_round=game.current_round,
    )
    db.add(roll)
    # Spend the shot; discarding hands it back.
    attacker.shot_in_round = game.current_round
    db.commit()
    db.refresh(game)
    db.refresh(roll)
    return _serialize_roll(roll, game)


@router.get("/{code}/shooting/{roll_id}", response_model=AttackRollOut)
def get_attack_roll(
    code: str,
    roll_id: int,
    _: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> AttackRollOut:
    """Read a roll, so the defending player can see the same dice."""
    game = get_game(code, db)
    return _serialize_roll(_get_roll(game, roll_id), game)


@router.post("/{code}/shooting/{roll_id}/confirm", response_model=GameOut)
def confirm_attack(
    code: str,
    roll_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    """Apply a rolled attack's damage to the target.

    This is the one path where a player writes to someone else's unit. The
    manual /damage endpoint stays owner-only; here the stored dice are the
    record of why the damage happened.
    """
    game = get_game(code, db)
    _require_shooting_turn(game, player)
    roll = _get_roll(game, roll_id)
    if roll.resolved:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That attack has already been confirmed or discarded"
        )

    attacker, attacker_owner = _entry(game, roll.attacker_game_unit_id)
    if attacker_owner != player.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That is not your attack")

    target, _owner = _entry(game, roll.target_game_unit_id)
    rolled = json.loads(roll.payload)
    target.models_lost = rolled["result_models_lost"]
    target.wounds_lost = rolled["result_wounds_lost"]
    roll.applied = True
    roll.resolved = True
    db.commit()
    db.refresh(game)
    return serialize_game(game)


@router.post("/{code}/shooting/{roll_id}/discard", response_model=GameOut)
def discard_attack(
    code: str,
    roll_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    """Throw a rolled attack away without applying it.

    Discarding is a full undo: the attacker gets its shot back, so a mis-picked
    target or weapon can be corrected. That does mean a player can roll again,
    which is a trust question rather than something the app enforces.
    """
    game = get_game(code, db)
    _require_shooting_turn(game, player)
    roll = _get_roll(game, roll_id)
    if roll.resolved:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That attack has already been confirmed or discarded"
        )
    attacker, attacker_owner = _entry(game, roll.attacker_game_unit_id)
    if attacker_owner != player.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "That is not your attack")

    roll.resolved = True
    roll.applied = False
    attacker.shot_in_round = None  # give the shot back
    db.commit()
    db.refresh(game)
    return serialize_game(game)
