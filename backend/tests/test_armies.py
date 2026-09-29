"""Per-game army selection: one faction, at least one unit, own units only."""
from .test_api import UNIT_PAYLOAD, client, register, select_army  # noqa: F401 (fixture)


def make_unit(client, headers, name: str, faction: str, points: int = 10) -> dict:
    payload = {**UNIT_PAYLOAD, "name": name, "faction": faction, "points": points}
    response = client.post("/api/units", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def new_game(client, headers) -> str:
    return client.post("/api/games", headers=headers).json()["code"]


def test_select_army_sets_faction_and_points(client):
    alice = register(client, "Alice")
    marine = make_unit(client, alice, "Intercessors", "Space Marines", 80)
    other = make_unit(client, alice, "Terminators", "Space Marines", 180)
    code = new_game(client, alice)

    state = select_army(client, code, alice, [marine["id"], other["id"]])
    me = state["players"][0]
    assert me["faction"] == "Space Marines"
    assert {u["name"] for u in me["army"]} == {"Intercessors", "Terminators"}
    assert me["army_points"] == 260


def test_cannot_mix_factions(client):
    alice = register(client, "Alice")
    marine = make_unit(client, alice, "Intercessors", "Space Marines")
    ork = make_unit(client, alice, "Boyz", "Orks")
    code = new_game(client, alice)

    response = client.post(
        f"/api/games/{code}/army",
        json={"unit_ids": [marine["id"], ork["id"]]},
        headers=alice,
    )
    assert response.status_code == 422
    assert "same faction" in response.json()["detail"]


def test_empty_selection_rejected(client):
    alice = register(client, "Alice")
    code = new_game(client, alice)
    response = client.post(f"/api/games/{code}/army", json={"unit_ids": []}, headers=alice)
    assert response.status_code == 422  # min_length=1


def test_cannot_select_another_players_unit(client):
    alice = register(client, "Alice")
    bob = register(client, "Bob")
    bob_unit = make_unit(client, bob, "Boyz", "Orks")
    code = new_game(client, alice)

    response = client.post(
        f"/api/games/{code}/army", json={"unit_ids": [bob_unit["id"]]}, headers=alice
    )
    assert response.status_code == 403


def test_unknown_unit_rejected(client):
    alice = register(client, "Alice")
    code = new_game(client, alice)
    response = client.post(
        f"/api/games/{code}/army", json={"unit_ids": [9999]}, headers=alice
    )
    assert response.status_code == 404


def test_ready_requires_an_army(client):
    alice = register(client, "Alice")
    unit = make_unit(client, alice, "Intercessors", "Space Marines")
    code = new_game(client, alice)

    blocked = client.post(f"/api/games/{code}/ready", headers=alice)
    assert blocked.status_code == 409
    assert "at least one unit" in blocked.json()["detail"]

    select_army(client, code, alice, [unit["id"]])
    assert client.post(f"/api/games/{code}/ready", headers=alice).status_code == 200


def test_changing_army_clears_ready(client):
    alice = register(client, "Alice")
    a = make_unit(client, alice, "Intercessors", "Space Marines")
    b = make_unit(client, alice, "Terminators", "Space Marines")
    code = new_game(client, alice)

    select_army(client, code, alice, [a["id"]])
    readied = client.post(f"/api/games/{code}/ready", headers=alice).json()
    assert readied["players"][0]["is_ready"] is True

    changed = select_army(client, code, alice, [a["id"], b["id"]])
    assert changed["players"][0]["is_ready"] is False


def test_army_replaces_previous_selection(client):
    alice = register(client, "Alice")
    a = make_unit(client, alice, "Intercessors", "Space Marines")
    b = make_unit(client, alice, "Terminators", "Space Marines")
    code = new_game(client, alice)

    select_army(client, code, alice, [a["id"], b["id"]])
    state = select_army(client, code, alice, [b["id"]])
    assert [u["name"] for u in state["players"][0]["army"]] == ["Terminators"]


def test_unaligned_units_can_be_selected(client):
    alice = register(client, "Alice")
    unit = make_unit(client, alice, "Homebrew Squad", "")
    code = new_game(client, alice)
    state = select_army(client, code, alice, [unit["id"]])
    assert state["players"][0]["faction"] == ""
    assert len(state["players"][0]["army"]) == 1


def test_armies_endpoint_returns_full_units(client):
    alice = register(client, "Alice")
    bob = register(client, "Bob")
    alice_unit = make_unit(client, alice, "Intercessors", "Space Marines")
    bob_unit = make_unit(client, bob, "Boyz", "Orks")
    code = new_game(client, alice)
    client.post(f"/api/games/{code}/join", headers=bob)
    select_army(client, code, alice, [alice_unit["id"]])
    select_army(client, code, bob, [bob_unit["id"]])

    armies = client.get(f"/api/games/{code}/armies", headers=alice).json()
    by_name = {a["player"]["name"]: a for a in armies}
    assert by_name["Alice"]["faction"] == "Space Marines"
    assert by_name["Bob"]["faction"] == "Orks"
    # Full statline + weapons, so the combat resolver can use them directly.
    unit = by_name["Bob"]["units"][0]
    assert unit["toughness"] == 4
    assert unit["weapons"][0]["name"] == "Bolt rifle"


def test_army_locked_after_game_starts(client):
    alice = register(client, "Alice")
    bob = register(client, "Bob")
    a_unit = make_unit(client, alice, "Intercessors", "Space Marines")
    b_unit = make_unit(client, bob, "Boyz", "Orks")
    code = new_game(client, alice)
    client.post(f"/api/games/{code}/join", headers=bob)
    select_army(client, code, alice, [a_unit["id"]])
    select_army(client, code, bob, [b_unit["id"]])
    client.post(f"/api/games/{code}/ready", headers=alice)
    client.post(f"/api/games/{code}/ready", headers=bob)
    started = client.post(f"/api/games/{code}/start", headers=alice).json()
    assert started["status"] == "active"

    response = client.post(
        f"/api/games/{code}/army", json={"unit_ids": [a_unit["id"]]}, headers=alice
    )
    assert response.status_code == 409


def test_deleting_a_unit_removes_it_from_armies(client):
    alice = register(client, "Alice")
    a = make_unit(client, alice, "Intercessors", "Space Marines")
    b = make_unit(client, alice, "Terminators", "Space Marines")
    code = new_game(client, alice)
    select_army(client, code, alice, [a["id"], b["id"]])

    assert client.delete(f"/api/units/{a['id']}", headers=alice).status_code == 204
    state = client.get(f"/api/games/{code}", headers=alice).json()
    assert [u["name"] for u in state["players"][0]["army"]] == ["Terminators"]
