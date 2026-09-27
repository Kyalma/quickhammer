"""Player registration, login, and identity."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import auth
from ..database import get_db
from ..models import Player
from ..schemas import PlayerCredentials, PlayerOut, TokenOut

router = APIRouter(prefix="/api/players", tags=["players"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(body: PlayerCredentials, db: Session = Depends(get_db)) -> TokenOut:
    existing = db.scalar(select(Player).where(Player.name == body.name))
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That name is already taken")
    player = Player(name=body.name, password_hash=auth.hash_password(body.password))
    db.add(player)
    db.commit()
    db.refresh(player)
    return TokenOut(token=auth.create_token(player.id), player=PlayerOut.model_validate(player))


@router.post("/login", response_model=TokenOut)
def login(body: PlayerCredentials, db: Session = Depends(get_db)) -> TokenOut:
    player = db.scalar(select(Player).where(Player.name == body.name))
    if player is None or not auth.verify_password(body.password, player.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong name or password")
    return TokenOut(token=auth.create_token(player.id), player=PlayerOut.model_validate(player))


@router.get("/me", response_model=PlayerOut)
def me(player: Player = Depends(auth.get_current_player)) -> Player:
    return player
