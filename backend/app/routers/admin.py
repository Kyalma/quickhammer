"""Admin-only views: all players and all games.

Admin rights are granted from the server console (see app/make_admin.py),
never through the API.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Game, GameStatus, Player, Unit
from ..schemas import PlayerOut
from ..services import game_flow

router = APIRouter(prefix="/api/admin", tags=["admin"])


class AdminPlayer(BaseModel):
    id: int
    name: str
    is_admin: bool
    unit_count: int


class AdminGame(BaseModel):
    id: int
    code: str
    status: GameStatus
    current_round: int
    phase_name: str
    player_names: list[str]
    active_player: str | None


@router.get("/players", response_model=list[AdminPlayer])
def all_players(
    _: Player = Depends(require_admin), db: Session = Depends(get_db)
) -> list[AdminPlayer]:
    rows = db.execute(
        select(Player, func.count(Unit.id))
        .outerjoin(Unit, Unit.owner_id == Player.id)
        .group_by(Player.id)
        .order_by(Player.name)
    ).all()
    return [
        AdminPlayer(
            id=player.id, name=player.name,
            is_admin=player.is_admin, unit_count=unit_count,
        )
        for player, unit_count in rows
    ]


@router.get("/games", response_model=list[AdminGame])
def all_games(
    _: Player = Depends(require_admin), db: Session = Depends(get_db)
) -> list[AdminGame]:
    games = db.scalars(select(Game).order_by(Game.id.desc())).all()
    result = []
    for game in games:
        by_id = {gp.player_id: gp.player.name for gp in game.players}
        result.append(AdminGame(
            id=game.id,
            code=game.code,
            status=game.status,
            current_round=game.current_round,
            phase_name=game_flow.phase_name(game.current_phase),
            player_names=list(by_id.values()),
            active_player=by_id.get(game.active_player_id),
        ))
    return result
