"""Password hashing (stdlib PBKDF2) and signed session tokens (stdlib HMAC).

Kept dependency-free on purpose: good enough for a friendly companion app,
easy to swap for OAuth/JWT later.
"""
import hashlib
import hmac
import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Player

_PBKDF2_ITERATIONS = 200_000

bearer_scheme = HTTPBearer(auto_error=False)


# --- Passwords -------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS
    ).hex()
    return f"{salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS
    ).hex()
    return hmac.compare_digest(candidate, digest)


# --- Tokens ----------------------------------------------------------------

def _sign(payload: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()


def create_token(player_id: int) -> str:
    payload = str(player_id)
    return f"{payload}.{_sign(payload)}"


def decode_token(token: str) -> int | None:
    """Return the player id if the token signature is valid, else None."""
    try:
        payload, signature = token.rsplit(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        return int(payload)
    except ValueError:
        return None


# --- FastAPI dependency ----------------------------------------------------

def get_current_player(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Player:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    player_id = decode_token(credentials.credentials)
    if player_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    player = db.get(Player, player_id)
    if player is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Unknown player")
    return player


def require_admin(player: Player = Depends(get_current_player)) -> Player:
    if not player.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin rights required")
    return player
