"""Admin-rights CLI implementation.

Don't invoke this module directly — use the location-independent launcher:
    python scripts/make_admin.py <player-name> [--revoke] [--list]
It works from any directory, locally and inside the Docker container.
"""
import argparse
import sys

from sqlalchemy import select

from .database import SessionLocal, init_db
from .models import Player


def set_admin(name: str, admin: bool) -> str:
    """Flip the flag; returns a human-readable result. Raises LookupError."""
    with SessionLocal() as db:
        player = db.scalar(select(Player).where(Player.name == name))
        if player is None:
            raise LookupError(f"No player named {name!r}")
        player.is_admin = admin
        db.commit()
        verb = "granted to" if admin else "revoked from"
        return f"Admin rights {verb} {player.name!r} (id {player.id})"


def list_players() -> list[str]:
    with SessionLocal() as db:
        players = db.scalars(select(Player).order_by(Player.name)).all()
        return [
            f"{'[admin] ' if p.is_admin else '        '}{p.name} (id {p.id})"
            for p in players
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Grant/revoke QuickHammer admin rights.")
    parser.add_argument("name", nargs="?", help="player name")
    parser.add_argument("--revoke", action="store_true", help="revoke instead of grant")
    parser.add_argument("--list", action="store_true", help="list players")
    args = parser.parse_args()

    init_db()

    if args.list:
        rows = list_players()
        print("\n".join(rows) if rows else "No players yet.")
        return 0

    if not args.name:
        parser.error("player name required (or use --list)")

    try:
        print(set_admin(args.name, admin=not args.revoke))
        return 0
    except LookupError as exc:
        print(exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
