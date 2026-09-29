"""Admin endpoints, the grant script logic, and the additive column migration."""
from sqlalchemy import select

from app.models import Player

from .test_api import (  # noqa: F401 (fixture)
    TestSession,
    UNIT_PAYLOAD,
    client,
    register,
    select_army,
)


def make_admin_directly(name: str) -> None:
    """Set the flag straight in the test DB (the script path is tested separately)."""
    with TestSession() as db:
        player = db.scalar(select(Player).where(Player.name == name))
        player.is_admin = True
        db.commit()


def test_admin_endpoints_forbidden_for_normal_players(client):
    headers = register(client, "Alice")
    assert client.get("/api/admin/players", headers=headers).status_code == 403
    assert client.get("/api/admin/games", headers=headers).status_code == 403


def test_admin_sees_all_players_with_unit_counts(client):
    alice = register(client, "Alice")
    register(client, "Bob")
    client.post("/api/units", json=UNIT_PAYLOAD, headers=alice)
    make_admin_directly("Alice")

    response = client.get("/api/admin/players", headers=alice)
    assert response.status_code == 200
    players = {p["name"]: p for p in response.json()}
    assert players["Alice"]["unit_count"] == 1
    assert players["Alice"]["is_admin"] is True
    assert players["Bob"]["unit_count"] == 0
    assert players["Bob"]["is_admin"] is False


def test_admin_sees_all_games_with_status(client):
    alice = register(client, "Alice")
    bob = register(client, "Bob")
    make_admin_directly("Alice")

    alice_unit = client.post("/api/units", json=UNIT_PAYLOAD, headers=alice).json()
    bob_unit = client.post("/api/units", json=UNIT_PAYLOAD, headers=bob).json()

    lobby = client.post("/api/games", headers=alice).json()
    running = client.post("/api/games", headers=alice).json()
    client.post(f"/api/games/{running['code']}/join", headers=bob)
    select_army(client, running["code"], alice, [alice_unit["id"]])
    select_army(client, running["code"], bob, [bob_unit["id"]])
    client.post(f"/api/games/{running['code']}/ready", headers=alice)
    client.post(f"/api/games/{running['code']}/ready", headers=bob)
    client.post(f"/api/games/{running['code']}/start", headers=alice)

    response = client.get("/api/admin/games", headers=alice)
    assert response.status_code == 200
    games = {g["code"]: g for g in response.json()}
    assert games[lobby["code"]]["status"] == "lobby"
    assert games[running["code"]]["status"] == "active"
    assert set(games[running["code"]]["player_names"]) == {"Alice", "Bob"}
    assert games[running["code"]]["active_player"] == "Alice"


def test_me_reports_admin_flag(client):
    headers = register(client, "Alice")
    assert client.get("/api/players/me", headers=headers).json()["is_admin"] is False
    make_admin_directly("Alice")
    assert client.get("/api/players/me", headers=headers).json()["is_admin"] is True


# Migrations of pre-Alembic databases are covered in tests/test_migrations.py.
