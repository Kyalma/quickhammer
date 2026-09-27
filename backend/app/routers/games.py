"""Game sessions: create / join / ready / start / poll / advance."""
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_player
from ..database import get_db
from ..models import Game, GamePlayer, GameStatus, Player
from ..schemas import GameOut, GamePlayerOut, PlayerOut
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
