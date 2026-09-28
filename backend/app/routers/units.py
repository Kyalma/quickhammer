"""Unit / loadout CRUD and picture upload."""
import secrets
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_player
from ..config import get_settings
from ..database import get_db
from ..models import Player, Unit, Weapon
from ..schemas import UnitIn, UnitOut

router = APIRouter(prefix="/api/units", tags=["units"])

ALLOWED_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8 MB


def _get_owned_unit(unit_id: int, player: Player, db: Session) -> Unit:
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found")
    if unit.owner_id != player.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your unit")
    return unit


def _apply_unit_payload(unit: Unit, body: UnitIn) -> None:
    for attr in ("name", "faction", "points", "movement", "toughness", "save",
                 "invuln_save", "wounds", "leadership", "oc", "model_count"):
        setattr(unit, attr, getattr(body, attr))
    unit.keywords = ",".join(body.keywords)
    unit.weapons.clear()
    for w in body.weapons:
        unit.weapons.append(Weapon(
            name=w.name, kind=w.kind, range=w.range, attacks=w.attacks,
            skill=w.skill, strength=w.strength, ap=w.ap, damage=w.damage,
            keywords=",".join(w.keywords), carrier_count=w.carrier_count,
        ))


@router.get("", response_model=list[UnitOut])
def list_my_units(
    player: Player = Depends(get_current_player), db: Session = Depends(get_db)
) -> list[UnitOut]:
    units = db.scalars(select(Unit).where(Unit.owner_id == player.id)).all()
    return [UnitOut.model_validate(u) for u in units]


@router.get("/player/{player_id}", response_model=list[UnitOut])
def list_player_units(
    player_id: int,
    _: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> list[UnitOut]:
    """Any logged-in player can view another player's roster (needed for A vs B)."""
    units = db.scalars(select(Unit).where(Unit.owner_id == player_id)).all()
    return [UnitOut.model_validate(u) for u in units]


@router.post("", response_model=UnitOut, status_code=status.HTTP_201_CREATED)
def create_unit(
    body: UnitIn,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> UnitOut:
    unit = Unit(owner_id=player.id)
    _apply_unit_payload(unit, body)
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return UnitOut.model_validate(unit)


@router.get("/{unit_id}", response_model=UnitOut)
def get_unit(
    unit_id: int,
    _: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> UnitOut:
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit not found")
    return UnitOut.model_validate(unit)


@router.put("/{unit_id}", response_model=UnitOut)
def update_unit(
    unit_id: int,
    body: UnitIn,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> UnitOut:
    unit = _get_owned_unit(unit_id, player, db)
    _apply_unit_payload(unit, body)
    db.commit()
    db.refresh(unit)
    return UnitOut.model_validate(unit)


@router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_unit(
    unit_id: int,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> None:
    unit = _get_owned_unit(unit_id, player, db)
    db.delete(unit)
    db.commit()


@router.post("/{unit_id}/image", response_model=UnitOut)
async def upload_image(
    unit_id: int,
    file: UploadFile,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> UnitOut:
    unit = _get_owned_unit(unit_id, player, db)
    extension = ALLOWED_IMAGE_TYPES.get(file.content_type or "")
    if extension is None:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only JPEG, PNG, WebP, or GIF images are allowed",
        )
    data = await file.read()
    if len(data) > MAX_IMAGE_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "Image too large (max 8 MB)")

    upload_dir = get_settings().upload_path
    filename = f"unit-{unit.id}-{secrets.token_hex(4)}{extension}"
    (upload_dir / filename).write_bytes(data)

    # Delete the previous image if it exists.
    if unit.image_path:
        old = upload_dir / Path(unit.image_path).name
        old.unlink(missing_ok=True)

    unit.image_path = f"/uploads/{filename}"
    db.commit()
    db.refresh(unit)
    return UnitOut.model_validate(unit)

