"""Phase order and turn progression for a game session."""
from __future__ import annotations

from ..models import PHASES, Game, GamePlayer, GameStatus


def phase_name(index: int) -> str:
    return PHASES[index % len(PHASES)]


def all_ready(game: Game) -> bool:
    return len(game.players) >= 2 and all(gp.is_ready for gp in game.players)


def start_game(game: Game) -> None:
    """Move a lobby to active: first player (by join order) takes the first turn."""
    game.status = GameStatus.active
    game.current_phase = 0
    game.current_round = 1
    game.active_player_id = game.players[0].player_id


def advance(game: Game) -> None:
    """Advance one phase. After the Fight phase, play passes to the next
    player; once every player has had a turn, the round increases."""
    if game.status != GameStatus.active:
        raise ValueError("Game is not active")

    if game.current_phase < len(PHASES) - 1:
        game.current_phase += 1
        return

    # End of turn: next player, possibly next round.
    game.current_phase = 0
    order: list[GamePlayer] = list(game.players)  # already ordered by turn_order
    ids = [gp.player_id for gp in order]
    current_index = ids.index(game.active_player_id)
    next_index = (current_index + 1) % len(ids)
    game.active_player_id = ids[next_index]
    if next_index == 0:
        game.current_round += 1
