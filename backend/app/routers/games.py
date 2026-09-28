"""Game sessions: create / join / ready / start / poll / advance."""
import secrets
import string

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import get_current_player
from ..database import get_db
from ..models import PHASES, Game, GamePlayer, GameStatus, GameUnit, Player, Unit
from ..schemas import (
    ApplyWoundsIn,
    ArmyUnitSummary,
    BattleShockIn,
    BattleShockResult,
    GameArmyOut,
    GameOut,
    GamePlayerOut,
    GameSummaryOut,
    PlayerOut,
    SetArmyIn,
    UnitOut,
)
from ..services import deletion, game_flow, unit_state

router = APIRouter(prefix="/api/games", tags=["games"])

MAX_PLAYERS = 4
COMMAND_PHASE = PHASES.index("Command")


def _summarize_unit(entry: GameUnit, game: Game) -> ArmyUnitSummary:
    unit = entry.unit
    destroyed = unit_state.is_destroyed(entry.models_lost, unit.model_count)
    below_half = unit_state.is_below_half_strength(
        entry.models_lost, entry.wounds_lost, unit.model_count, unit.wounds
    )
    return ArmyUnitSummary(
        id=entry.id,
        unit_id=unit.id,
        name=unit.name,
        points=unit.points,
        model_count=unit.model_count,
        wounds=unit.wounds,
        leadership=unit.leadership,
        models_remaining=unit_state.models_remaining(entry.models_lost, unit.model_count),
        wounds_lost=entry.wounds_lost,
        is_destroyed=destroyed,
        below_half_strength=below_half,
        is_battle_shocked=entry.is_battle_shocked,
        needs_shock_test=(
            below_half
            and not destroyed
            and entry.shock_tested_round != game.current_round
        ),
        has_shot=entry.shot_in_round == game.current_round,
    )


def serialize_game(game: Game) -> GameOut:
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
                army=[_summarize_unit(e, game) for e in gp.army],
                army_points=sum(e.unit.points for e in gp.army),
                command_points=gp.command_points,
            )
            for gp in game.players
        ],
        pending_attack_id=next(
            (roll.id for roll in game.attack_rolls if not roll.resolved), None
        ),
    )


def get_game(code: str, db: Session) -> Game:
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
    game = Game(code=_new_code(db), creator_player_id=player.id)
    game.players.append(GamePlayer(player_id=player.id, turn_order=0))
    db.add(game)
    db.commit()
    db.refresh(game)
    return serialize_game(game)


@router.get("", response_model=list[GameSummaryOut])
def list_games(
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
    limit: int = 50,
) -> list[GameSummaryOut]:
    """Joinable and in-progress games, newest first.

    Finished games are left out: players only care about what they can join or
    return to. The admin view lists everything, including finished games.
    """
    games = db.scalars(
        select(Game)
        .where(Game.status != GameStatus.finished)
        .order_by(Game.id.desc())
        .limit(limit)
    ).all()
    summaries = []
    for game in games:
        member_ids = {gp.player_id for gp in game.players}
        is_member = player.id in member_ids
        creator = next(
            (gp.player.name for gp in game.players
             if gp.player_id == game.creator_player_id),
            None,
        )
        summaries.append(GameSummaryOut(
            id=game.id,
            code=game.code,
            status=game.status,
            current_round=game.current_round,
            phase_name=game_flow.phase_name(game.current_phase),
            player_count=len(game.players),
            player_names=[gp.player.name for gp in game.players],
            creator_name=creator,
            is_member=is_member,
            can_join=(
                game.status == GameStatus.lobby
                and not is_member
                and len(game.players) < MAX_PLAYERS
            ),
            # Only the creator, and only before the game starts.
            can_delete=(
                game.status == GameStatus.lobby
                and game.creator_player_id == player.id
            ),
        ))
    return summaries


@router.delete("/{code}", status_code=status.HTTP_204_NO_CONTENT)
def delete_game(
    code: str,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> None:
    """Cancel a game you created, while it is still in the lobby."""
    game = get_game(code, db)
    if game.creator_player_id != player.id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the player who created a game can delete it"
        )
    if game.status != GameStatus.lobby:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "A game that has started cannot be deleted; end it instead",
        )
    deletion.delete_game(db, game)
    db.commit()


@router.get("/{code}", response_model=GameOut)
def get_game_state(
    code: str,
    _: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    """Polling endpoint: full game state."""
    return serialize_game(get_game(code, db))


@router.post("/{code}/join", response_model=GameOut)
def join_game(
    code: str,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    game = get_game(code, db)
    if any(gp.player_id == player.id for gp in game.players):
        return serialize_game(game)  # already in: idempotent
    if game.status != GameStatus.lobby:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game has already started")
    if len(game.players) >= MAX_PLAYERS:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game is full")
    game.players.append(GamePlayer(player_id=player.id, turn_order=len(game.players)))
    db.commit()
    db.refresh(game)
    return serialize_game(game)


@router.post("/{code}/army", response_model=GameOut)
def set_army(
    code: str,
    body: SetArmyIn,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    """Pick the units to bring to this game. All must share one faction."""
    game = get_game(code, db)
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
    return serialize_game(game)


@router.get("/{code}/armies", response_model=list[GameArmyOut])
def get_armies(
    code: str,
    _: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> list[GameArmyOut]:
    """Full unit data for every player's army â€” used by the combat resolver."""
    game = get_game(code, db)
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
    game = get_game(code, db)
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
    return serialize_game(game)


@router.post("/{code}/advance", response_model=GameOut)
def advance_phase(
    code: str,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    game = get_game(code, db)
    _membership(game, player)
    if game.status != GameStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game is not active")
    if game.active_player_id != player.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "It is not your turn")
    game_flow.advance(game)
    db.commit()
    db.refresh(game)
    return serialize_game(game)


def _owned_entry(game: Game, game_unit_id: int, player: Player) -> GameUnit:
    """The caller's own unit in this game. Players manage their own units, the
    same way you remove your own models at the table."""
    for gp in game.players:
        for entry in gp.army:
            if entry.id == game_unit_id:
                if gp.player_id != player.id:
                    raise HTTPException(
                        status.HTTP_403_FORBIDDEN, "You can only update your own units"
                    )
                return entry
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Unit is not in this game")


@router.post("/{code}/units/{game_unit_id}/damage", response_model=GameOut)
def apply_damage(
    code: str,
    game_unit_id: int,
    body: ApplyWoundsIn,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    """Record wounds on one of your units. Negative heals, so it also undoes."""
    game = get_game(code, db)
    if game.status != GameStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game is not active")
    entry = _owned_entry(game, game_unit_id, player)

    entry.models_lost, entry.wounds_lost = unit_state.apply_wounds(
        entry.models_lost,
        entry.wounds_lost,
        entry.unit.model_count,
        entry.unit.wounds,
        body.wounds,
    )
    db.commit()
    db.refresh(game)
    return serialize_game(game)


@router.post("/{code}/units/{game_unit_id}/battle-shock", response_model=BattleShockResult)
def battle_shock_test(
    code: str,
    game_unit_id: int,
    body: BattleShockIn,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> BattleShockResult:
    """Resolve a Battle-shock test from the 2D6 total the player rolled."""
    game = get_game(code, db)
    if game.status != GameStatus.active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Game is not active")
    if game.current_phase != COMMAND_PHASE:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Battle-shock tests are taken in the Command phase",
        )
    if game.active_player_id != player.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "It is not your turn")

    entry = _owned_entry(game, game_unit_id, player)
    unit = entry.unit
    if unit_state.is_destroyed(entry.models_lost, unit.model_count):
        raise HTTPException(status.HTTP_409_CONFLICT, "That unit has been destroyed")
    if not unit_state.is_below_half_strength(
        entry.models_lost, entry.wounds_lost, unit.model_count, unit.wounds
    ):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Only units below half strength take Battle-shock tests",
        )
    if entry.shock_tested_round == game.current_round:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "That unit has already tested this round"
        )

    passed = unit_state.passes_battle_shock(body.roll, unit.leadership)
    entry.is_battle_shocked = not passed
    entry.shock_tested_round = game.current_round
    db.commit()
    db.refresh(game)
    return BattleShockResult(
        unit_name=unit.name,
        roll=body.roll,
        leadership=unit.leadership,
        passed=passed,
        game=serialize_game(game),
    )


@router.post("/{code}/finish", response_model=GameOut)
def finish_game(
    code: str,
    player: Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> GameOut:
    game = get_game(code, db)
    _membership(game, player)
    game.status = GameStatus.finished
    db.commit()
    db.refresh(game)
    return serialize_game(game)

