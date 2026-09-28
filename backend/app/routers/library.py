"""Browse the OpenHammer datasheet library and import units into a roster.

QuickHammer proxies the public OpenHammer API server-side: the browser never
talks to it directly (no CORS issues, works from LAN devices), and all schema
mapping stays in app/services/library.py.
"""
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_player
from ..config import get_settings
from ..database import get_db
from ..models import Player, Unit, Weapon
from ..schemas import UnitOut
from ..services.library import map_unit

router = APIRouter(prefix="/api/library", tags=["library"])


class LibraryFaction(BaseModel):
    name: str
    faction_type: str
    unit_count: int


class LibraryUnitSummary(BaseModel):
    id: str
    name: str
    faction: str
    points: int | None = None
    min_models: int | None = None
    max_models: int | None = None


def _fetch(path: str, params: dict[str, Any] | None = None) -> Any:
    settings = get_settings()
    url = f"{settings.openhammer_base_url}/v1/{settings.openhammer_edition}{path}"
    try:
        response = httpx.get(url, params=params, timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found in the unit library")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The unit library returned an error"
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, "The unit library is unreachable"
        ) from exc
    return response.json()


@router.get("/factions", response_model=list[LibraryFaction])
def list_factions(_: Player = Depends(get_current_player)) -> list[LibraryFaction]:
    data = _fetch("/factions")
    return sorted(
        (LibraryFaction.model_validate(f) for f in data),
        key=lambda f: f.name,
    )


@router.get("/units", response_model=list[LibraryUnitSummary])
def search_units(
    search: str = Query(default="", max_length=100),
    faction: str = Query(default="", max_length=100),
    limit: int = Query(default=30, ge=1, le=100),
    _: Player = Depends(get_current_player),
) -> list[LibraryUnitSummary]:
    params: dict[str, Any] = {"limit": limit, "sort_by": "name"}
    if search.strip():
        params["name"] = search.strip()
    if faction.strip():
        params["faction"] = faction.strip()
    data = _fetch("/units", params)
    return [
        LibraryUnitSummary(
            id=u["id"],
            name=u["name"],
            faction=u.get("faction", ""),
            points=(u.get("points") or {}).get("base"),
            min_models=(u.get("composition") or {}).get("min_models"),
            max_models=(u.get("composition") or {}).get("max_models"),
        )
        for u in data
    ]


@router.post("/units/{unit_id}/import", response_model=UnitOut, status_code=status.HTTP_201_CREATED)
def import_unit(
    unit_id: str,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> UnitOut:
    """Fetch a datasheet from OpenHammer and add it to the player's roster."""
    data = _fetch(f"/units/{unit_id}")
    mapped = map_unit(data)

    unit = Unit(
        owner_id=player.id,
        name=mapped.name,
        faction=mapped.faction,
        points=mapped.points,
        movement=mapped.movement,
        toughness=mapped.toughness,
        save=mapped.save,
        invuln_save=mapped.invuln_save,
        wounds=mapped.wounds,
        leadership=mapped.leadership,
        oc=mapped.oc,
        model_count=mapped.model_count,
    )
    for w in mapped.weapons:
        unit.weapons.append(Weapon(
            name=w.name, kind=w.kind, range=w.range, attacks=w.attacks,
            skill=w.skill, strength=w.strength, ap=w.ap, damage=w.damage,
            keywords=",".join(w.keywords),
        ))
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return UnitOut.model_validate(unit)
