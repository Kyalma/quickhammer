"""Game sessions: create / join / ready / start / poll / advance."""
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_player
from ..database import get_db
from ..models import Game, GamePlayer, GameStatus, GameUnit, Player, Unit
from ..schemas import (
    ArmyUnitSummary,
    GameArmyOut,
    GameOut,
    GamePlayerOut,
    PlayerOut,
    SetArmyIn,
    UnitOut,
)
from ..services import game_flow

router = APIRouter(prefix="/api/games", tags=["games"])

MAX_PLAYERS = 4


def _serialize(game: Game) -> GameOut:
    return GameOut(
        id=game.id,
        code=game.code,
        status=game.status,
        current_phase=game.current_phase,
        phase_name=game_flow.phase_name(game.current_phase),
        current_round=game.current_round,
        active_player_id=game.active_player_id,
        players=[
            GamePlayerOut(
                player=PlayerOut.model_validate(gp.player),
                is_ready=gp.is_ready,
                turn_order=gp.turn_order,
                faction=gp.faction,
                army=[
                    ArmyUnitSummary(id=e.unit.id, name=e.unit.name, points=e.unit.points)
                    for e in gp.army
                ],
                army_points=sum(e.unit.points for e in gp.army),
            )
            for gp in game.players
        ],
    )


def _get_game(code: str, db: Session) -> Game:
    game = db.scalar(select(Game).where(Game.code == code.upper()))
    if game is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Game not found")
    return game


def _membership(game: Game, player: Player) -> GamePlayer:
    for gp in game.players:
        if gp.player_id == player.id:
            return gp
    raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not in this game")


def _new_code(db: Session) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(5))
        if db.scalar(select(Game).where(Game.code == code)) is None:
            return code


@router.post("", response_model=GameOut, status_code=status.HTTP_201_CREATED)
def create_game(
    player: Player = Depends(get_current_player), db: Session = Depends(get_db)
) -> GameOut:
    game = Game(code=_new_code(db))
    game.players.append(GamePlayer(player_id=player.id, turn_order=0))
    db.add(game)
    db.commit()
    db.refresh(game)
    return _serialize(game)


@router.get("/{code}", response_model=GameOut)
def get_game_state(
    code: str,
    _: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    """Polling endpoint: full game state."""
    return _serialize(_get_game(code, db))


@router.post("/{code}/join", response_model=GameOut)
def join_game(
    code: str,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    game = _get_game(code, db)
    if any(gp.player_id == player.id for gp in game.players):
        return _serialize(game)  # already in: idempotent
    if game.status != GameStatus.lobby:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game has already started")
    if len(game.players) >= MAX_PLAYERS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game is full")
    game.players.append(GamePlayer(player_id=player.id, turn_order=len(game.players)))
    db.commit()
    db.refresh(game)
    return _serialize(game)


@router.post("/{code}/army", response_model=GameOut)
def set_army(
    code: str,
    body: SetArmyIn,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    """Pick the units to bring to this game. All must share one faction."""
    game = _get_game(code, db)
    if game.status != GameStatus.lobby:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game has already started")
    gp = _membership(game, player)

    unit_ids = list(dict.fromkeys(body.unit_ids))  # de-duplicate, keep order
    units = db.scalars(select(Unit).where(Unit.id.in_(unit_ids))).all()
    by_id = {u.id: u for u in units}
    if len(by_id) != len(unit_ids):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "One or more units were not found")
    if any(u.owner_id != player.id for u in units):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only select your own units")

    factions = {u.faction for u in units}
    if len(factions) > 1:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "All selected units must belong to the same faction",
        )

    gp.faction = factions.pop()
    # Flush the removals before inserting, or re-picking the same unit trips the
    # (game_player_id, unit_id) unique constraint.
    for entry in list(gp.army):
        db.delete(entry)
    db.flush()
    for unit_id in unit_ids:
        gp.army.append(GameUnit(unit_id=unit_id))
    # Changing the army means re-confirming readiness.
    gp.is_ready = False
    db.commit()
    db.refresh(game)
    return _serialize(game)


@router.get("/{code}/armies", response_model=list[GameArmyOut])
def get_armies(
    code: str,
    _: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> list[GameArmyOut]:
    """Full unit data for every player's army — used by the combat resolver."""
    game = _get_game(code, db)
    return [
        GameArmyOut(
            player=PlayerOut.model_validate(gp.player),
            faction=gp.faction,
            units=[UnitOut.model_validate(e.unit) for e in gp.army],
        )
        for gp in game.players
    ]


@router.post("/{code}/ready", response_model=GameOut)
def toggle_ready(
    code: str,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    game = _get_game(code, db)
    if game.status != GameStatus.lobby:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game has already started")
    gp = _membership(game, player)
    if not gp.is_ready and not gp.army:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Select at least one unit for this game before readying up",
        )
    gp.is_ready = not gp.is_ready
    # Auto-start once at least two players are all ready.
    if game_flow.all_ready(game):
        game_flow.start_game(game)
    db.commit()
    db.refresh(game)
    return _serialize(game)


@router.post("/{code}/advance", response_model=GameOut)
def advance_phase(
    code: str,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    game = _get_game(code, db)
    _membership(game, player)
    if game.status != GameStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game is not active")
    if game.active_player_id != player.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "It is not your turn")
    game_flow.advance(game)
    db.commit()
    db.refresh(game)
    return _serialize(game)


@router.post("/{code}/finish", response_model=GameOut)
def finish_game(
    code: str,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    game = _get_game(code, db)
    _membership(game, player)
    game.status = GameStatus.finished
    db.commit()
    db.refresh(game)
    return _serialize(game)
