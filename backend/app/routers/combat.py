"""A-vs-B combat resolution endpoint."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import get_current_player
from ..database import get_db
from ..models import Player, Unit, Weapon
from ..schemas import CombatRequest, CombatResult
from ..services.combat import AttackerProfile, DefenderProfile, resolve_attack

router = APIRouter(prefix="/api/combat", tags=["combat"])


@router.post("/resolve", response_model=CombatResult)
def resolve(
    body: CombatRequest,
    _: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> CombatResult:
    attacker_unit = db.get(Unit, body.attacker_unit_id)
    defender_unit = db.get(Unit, body.defender_unit_id)
    weapon = db.get(Weapon, body.weapon_id)

    if attacker_unit is None or defender_unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found")
    if weapon is None or weapon.unit_id != attacker_unit.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Weapon not found on the attacking unit")

    attacker = AttackerProfile(
        weapon_name=weapon.name,
        attacks=weapon.attacks,
        skill=weapon.skill,
        strength=weapon.strength,
        ap=weapon.ap,
        damage=weapon.damage,
        keywords=[k.strip() for k in weapon.keywords.split(",") if k.strip()],
        model_count=attacker_unit.model_count,
    )
    defender = DefenderProfile(
        unit_name=defender_unit.name,
        toughness=defender_unit.toughness,
        save=defender_unit.save,
        invuln_save=defender_unit.invuln_save,
        wounds=defender_unit.wounds,
        model_count=defender_unit.model_count,
    )

    try:
        result = resolve_attack(attacker, defender)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc

    return CombatResult(attacker=attacker_unit.name, **result)
