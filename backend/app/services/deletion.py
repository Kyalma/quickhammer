"""Deleting games and players without leaving dangling rows.

SQLite does not enforce foreign keys by default, so an incomplete delete would
not raise — it would quietly leave rows pointing at things that no longer
exist, and the next serialize of that game would blow up. These helpers do the
teardown in dependency order so that cannot happen.

Shared by the lobby's creator-delete and the admin panel.
"""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from ..models import AttackRoll, Game, GamePlayer, GameUnit, Player


def delete_game(db: Session, game: Game) -> None:
    """Remove a game and everything that belongs only to it.

    Attack rolls reference game_units through two separate foreign keys, so they
    are cleared explicitly rather than relying on an ambiguous relationship.
    """
    db.execute(delete(AttackRoll).where(AttackRoll.game_id == game.id))
    db.flush()
    # GamePlayer -> GameUnit cascades are configured on the relationships.
    db.delete(game)
    db.flush()


def delete_player(db: Session, player: Player) -> None:
    """Remove a player, their roster, and their place in every game.

    Games the player was in survive with the remaining players, except that a
    game left with nobody in it is removed too. A game they created but are no
    longer in keeps running; its creator id simply goes stale, which only
    affects who may delete it from the lobby.
    """
    memberships = db.scalars(
        select(GamePlayer).where(GamePlayer.player_id == player.id)
    ).all()
    affected_game_ids = {gp.game_id for gp in memberships}

    # Any game this player touched may hold attack rolls pointing at game_units
    # that are about to disappear.
    if affected_game_ids:
        db.execute(delete(AttackRoll).where(AttackRoll.game_id.in_(affected_game_ids)))

    # Their roster units may also be fielded in games they are not a member of
    # (they cannot be, today, but be defensive rather than leave orphans).
    unit_ids = [u.id for u in player.units]
    if unit_ids:
        entry_game_ids = set(
            db.scalars(
                select(GamePlayer.game_id)
                .join(GameUnit, GameUnit.game_player_id == GamePlayer.id)
                .where(GameUnit.unit_id.in_(unit_ids))
            ).all()
        )
        extra = entry_game_ids - affected_game_ids
        if extra:
            db.execute(delete(AttackRoll).where(AttackRoll.game_id.in_(extra)))
        db.execute(delete(GameUnit).where(GameUnit.unit_id.in_(unit_ids)))
    db.flush()

    # Stop games pointing at them as the active player.
    db.execute(
        update(Game)
        .where(Game.active_player_id == player.id)
        .values(active_player_id=None)
    )

    for membership in memberships:
        db.delete(membership)
    db.flush()

    # Player -> units -> weapons cascade via the relationships.
    db.delete(player)
    db.flush()

    # A game nobody is left in is just litter.
    for game_id in affected_game_ids:
        game = db.get(Game, game_id)
        if game is not None and not game.players:
            delete_game(db, game)
