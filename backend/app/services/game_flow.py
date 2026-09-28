"""Phase order and turn progression for a game session."""
from __future__ import annotations

from ..models import PHASES, Game, GamePlayer, GameStatus


def phase_name(index: int) -> str:
    return PHASES[index % len(PHASES)]


def all_ready(game: Game) -> bool:
    """Two or more players, each ready and each with an army selected."""
    return len(game.players) >= 2 and all(
        gp.is_ready and gp.army for gp in game.players
    )


def membership(game: Game, player_id: int | None) -> GamePlayer | None:
    for gp in game.players:
        if gp.player_id == player_id:
            return gp
    return None


def begin_command_phase(game_player: GamePlayer) -> None:
    """Command step effects for the player whose turn is beginning: gain 1 CP,
    and Battle-shock inflicted on their units last turn wears off."""
    game_player.command_points += 1
    for entry in game_player.army:
        entry.is_battle_shocked = False


def start_game(game: Game) -> None:
    """Move a lobby to active: first player (by join order) takes the first turn."""
    game.status = GameStatus.active
    game.current_phase = 0
    game.current_round = 1
    first = game.players[0]
    game.active_player_id = first.player_id
    begin_command_phase(first)


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
    # The new active player's Command phase starts immediately.
    begin_command_phase(order[next_index])
