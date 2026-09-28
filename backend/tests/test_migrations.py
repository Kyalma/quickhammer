"""Migrations must upgrade a live database without losing data.

This is the highest-stakes code in the project: the deployed server holds real
accounts, rosters and uploaded pictures. These tests run the real startup path
in a fresh subprocess, exactly as the container does, against databases in each
state a real deployment could be in.
"""
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parent.parent

EXPECTED_TABLES = {
    "players", "units", "weapons", "games", "game_players", "game_units",
    "alembic_version",
}

# Schema from before the per-game armies feature: no game_units table and no
# game_players.faction column.
PRE_ARMIES_SQL = """
CREATE TABLE players (id INTEGER PRIMARY KEY, name VARCHAR(50), password_hash VARCHAR(200),
  is_admin BOOLEAN NOT NULL DEFAULT 0);
CREATE TABLE units (id INTEGER PRIMARY KEY, owner_id INTEGER, name VARCHAR(100),
  image_path VARCHAR(300), faction VARCHAR(100) NOT NULL DEFAULT '',
  points INTEGER NOT NULL DEFAULT 0, movement INTEGER, toughness INTEGER, save INTEGER,
  invuln_save INTEGER, wounds INTEGER, leadership INTEGER, oc INTEGER, model_count INTEGER);
CREATE TABLE weapons (id INTEGER PRIMARY KEY, unit_id INTEGER, name VARCHAR(100),
  kind VARCHAR(6), range INTEGER, attacks VARCHAR(20), skill INTEGER, strength INTEGER,
  ap INTEGER, damage VARCHAR(20), keywords VARCHAR(300));
CREATE TABLE games (id INTEGER PRIMARY KEY, code VARCHAR(8), status VARCHAR(8),
  current_phase INTEGER, current_round INTEGER, active_player_id INTEGER);
CREATE TABLE game_players (id INTEGER PRIMARY KEY, game_id INTEGER, player_id INTEGER,
  is_ready BOOLEAN, turn_order INTEGER);
INSERT INTO players (name, password_hash, is_admin) VALUES ('Veteran', 'hash-abc', 1);
INSERT INTO units (owner_id, name, faction, points, movement, toughness, save, wounds,
  leadership, oc, model_count)
  VALUES (1, 'Legacy Squad', 'Space Marines', 80, 6, 4, 3, 2, 6, 1, 5);
"""

# Schema as of the armies feature, with a game already in progress.
WITH_ARMIES_SQL = PRE_ARMIES_SQL + """
ALTER TABLE game_players ADD COLUMN faction VARCHAR(100) NOT NULL DEFAULT '';
CREATE TABLE game_units (id INTEGER PRIMARY KEY, game_player_id INTEGER, unit_id INTEGER);
INSERT INTO games (code, status, current_phase, current_round) VALUES ('ABC12', 'lobby', 0, 1);
INSERT INTO game_players (game_id, player_id, is_ready, turn_order, faction)
  VALUES (1, 1, 0, 0, 'Space Marines');
INSERT INTO game_units (game_player_id, unit_id) VALUES (1, 1);
"""


def migrate(db_path: Path) -> None:
    """Run the real startup migration in a fresh process, like the container."""
    result = subprocess.run(
        [sys.executable, "-c", "from app.database import run_migrations; run_migrations()"],
        cwd=BACKEND,
        env={
            "PATH": "",
            "SYSTEMROOT": "C:\\Windows",  # sqlite3/ssl need this on Windows
            "QH_DATABASE_URL": f"sqlite:///{db_path.as_posix()}",
        },
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


@pytest.fixture()
def legacy_db(tmp_path, request):
    db_path = tmp_path / "legacy.db"
    sql = request.param
    if sql:
        con = sqlite3.connect(db_path)
        con.executescript(sql)
        con.commit()
        con.close()
    return db_path


@pytest.mark.parametrize(
    "legacy_db",
    [None, PRE_ARMIES_SQL, WITH_ARMIES_SQL],
    ids=["empty", "pre_armies", "with_armies"],
    indirect=True,
)
def test_migrates_to_head_with_every_table_and_column(legacy_db):
    migrate(legacy_db)
    con = sqlite3.connect(legacy_db)
    try:
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert EXPECTED_TABLES <= tables

        # Columns added across the project's history must all be present.
        assert "is_admin" in columns(con, "players")
        assert {"faction", "points"} <= columns(con, "units")
        assert {"faction", "command_points"} <= columns(con, "game_players")
        assert {
            "models_lost", "wounds_lost", "is_battle_shocked", "shock_tested_round",
        } <= columns(con, "game_units")
    finally:
        con.close()


@pytest.mark.parametrize(
    "legacy_db", [PRE_ARMIES_SQL, WITH_ARMIES_SQL], ids=["pre_armies", "with_armies"],
    indirect=True,
)
def test_existing_rows_survive_and_get_sane_defaults(legacy_db):
    migrate(legacy_db)
    con = sqlite3.connect(legacy_db)
    try:
        assert con.execute("SELECT name, is_admin FROM players").fetchall() == [("Veteran", 1)]
        assert con.execute("SELECT name, faction, points FROM units").fetchall() == [
            ("Legacy Squad", "Space Marines", 80)
        ]
        # New non-nullable columns must be backfilled, not left null.
        assert con.execute("SELECT command_points FROM game_players").fetchall() in (
            [], [(0,)]
        )
    finally:
        con.close()


def test_in_progress_game_keeps_its_army_and_starts_undamaged(tmp_path):
    db_path = tmp_path / "in_progress.db"
    con = sqlite3.connect(db_path)
    con.executescript(WITH_ARMIES_SQL)
    con.commit()
    con.close()

    migrate(db_path)

    con = sqlite3.connect(db_path)
    try:
        assert con.execute("SELECT game_player_id, unit_id FROM game_units").fetchall() == [(1, 1)]
        state = con.execute(
            "SELECT models_lost, wounds_lost, is_battle_shocked, shock_tested_round "
            "FROM game_units"
        ).fetchone()
        assert state == (0, 0, 0, None)
    finally:
        con.close()


def test_migration_is_idempotent(tmp_path):
    db_path = tmp_path / "twice.db"
    migrate(db_path)
    migrate(db_path)  # must not fail or duplicate anything
    con = sqlite3.connect(db_path)
    try:
        version = con.execute("SELECT version_num FROM alembic_version").fetchall()
        assert len(version) == 1
    finally:
        con.close()
