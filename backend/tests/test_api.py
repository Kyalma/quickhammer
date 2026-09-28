"""End-to-end API smoke tests using an in-memory SQLite database."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client():
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


def register(client: TestClient, name: str) -> dict:
    response = client.post(
        "/api/players/register", json={"name": name, "password": "secret1"}
    )
    assert response.status_code == 201, response.text
    body = response.json()
    return {"Authorization": f"Bearer {body['token']}"}


UNIT_PAYLOAD = {
    "name": "Intercessors",
    "faction": "Space Marines", "points": 80,
    "toughness": 4, "save": 3, "wounds": 2, "model_count": 5,
    "weapons": [{
        "name": "Bolt rifle", "kind": "ranged", "range": 24,
        "attacks": "2", "skill": 3, "strength": 4, "ap": 1, "damage": "1",
        "keywords": [],
    }],
}


def select_army(client: TestClient, code: str, headers: dict, unit_ids: list[int]) -> dict:
    response = client.post(
        f"/api/games/{code}/army", json={"unit_ids": unit_ids}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


def test_register_login_me(client):
    headers = register(client, "Alice")
    me = client.get("/api/players/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["name"] == "Alice"

    login = client.post(
        "/api/players/login", json={"name": "Alice", "password": "secret1"}
    )
    assert login.status_code == 200

    bad = client.post(
        "/api/players/login", json={"name": "Alice", "password": "wrong!"}
    )
    assert bad.status_code == 401


def test_duplicate_name_rejected(client):
    register(client, "Alice")
    response = client.post(
        "/api/players/register", json={"name": "Alice", "password": "secret1"}
    )
    assert response.status_code == 409


def test_unit_crud(client):
    headers = register(client, "Alice")

    created = client.post("/api/units", json=UNIT_PAYLOAD, headers=headers)
    assert created.status_code == 201, created.text
    unit = created.json()
    assert unit["weapons"][0]["name"] == "Bolt rifle"

    listed = client.get("/api/units", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["faction"] == "Space Marines"
    assert listed[0]["points"] == 80

    unit["name"] = "Assault Intercessors"
    updated = client.put(f"/api/units/{unit['id']}", json=unit, headers=headers)
    assert updated.json()["name"] == "Assault Intercessors"

    deleted = client.delete(f"/api/units/{unit['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get("/api/units", headers=headers).json() == []


def test_weapon_accepts_dice_notation_attacks(client):
    headers = register(client, "Alice")
    payload = {**UNIT_PAYLOAD, "weapons": [
        {**UNIT_PAYLOAD["weapons"][0], "attacks": "D6+1", "damage": "2D3"},
    ]}
    response = client.post("/api/units", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    weapon = response.json()["weapons"][0]
    assert weapon["attacks"] == "D6+1"
    assert weapon["damage"] == "2D3"


def test_weapon_rejects_bad_dice_notation(client):
    headers = register(client, "Alice")
    payload = {**UNIT_PAYLOAD, "weapons": [
        {**UNIT_PAYLOAD["weapons"][0], "attacks": "banana"},
    ]}
    response = client.post("/api/units", json=payload, headers=headers)
    assert response.status_code == 422


def test_other_player_cannot_edit_my_unit(client):
    alice = register(client, "Alice")
    bob = register(client, "Bob")
    unit = client.post("/api/units", json=UNIT_PAYLOAD, headers=alice).json()
    response = client.put(f"/api/units/{unit['id']}", json=UNIT_PAYLOAD, headers=bob)
    assert response.status_code == 403


def test_game_lifecycle_and_combat(client):
    alice = register(client, "Alice")
    bob = register(client, "Bob")

    # Rosters
    alice_unit = client.post("/api/units", json=UNIT_PAYLOAD, headers=alice).json()
    bob_unit = client.post("/api/units", json=UNIT_PAYLOAD, headers=bob).json()

    # Lobby
    game = client.post("/api/games", headers=alice).json()
    code = game["code"]
    assert game["status"] == "lobby"

    joined = client.post(f"/api/games/{code}/join", headers=bob).json()
    assert len(joined["players"]) == 2

    # Each player fields an army before readying up.
    select_army(client, code, alice, [alice_unit["id"]])
    select_army(client, code, bob, [bob_unit["id"]])

    client.post(f"/api/games/{code}/ready", headers=alice)
    started = client.post(f"/api/games/{code}/ready", headers=bob).json()
    assert started["status"] == "active"
    assert started["phase_name"] == "Command"
    assert started["active_player_id"] is not None

    # Only the active player can advance.
    active_headers = alice  # Alice created the game, so she goes first
    blocked = client.post(f"/api/games/{code}/advance", headers=bob)
    assert blocked.status_code == 403

    # Walk all five phases: turn passes to Bob.
    for expected in ["Movement", "Shooting", "Charge", "Fight", "Command"]:
        state = client.post(f"/api/games/{code}/advance", headers=active_headers).json()
        assert state["phase_name"] == expected
    assert state["active_player_id"] != started["active_player_id"]
    assert state["current_round"] == 1

    # Combat: Alice's unit shoots Bob's.
    result = client.post(
        "/api/combat/resolve",
        json={
            "attacker_unit_id": alice_unit["id"],
            "weapon_id": alice_unit["weapons"][0]["id"],
            "defender_unit_id": bob_unit["id"],
        },
        headers=alice,
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["expected_damage"] > 0
    assert [s["label"] for s in body["steps"]] == [
        "Attacks", "Hits", "Wounds", "Failed saves", "Damage", "Models slain",
    ]
