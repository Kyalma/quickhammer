"""Starting a game is an explicit press, not a side effect of readying up.

Any player in the lobby may press Start once everyone has an army and is ready;
there is no privileged host.
"""
from .test_api import client, register, select_army  # noqa: F401 (fixture)
from .test_armies import make_unit, new_game


def two_player_lobby(client) -> tuple[str, dict, dict]:
    """A lobby with two players who each have an army but are not ready yet."""
    alice = register(client, "Alice")
    bob = register(client, "Bob")
    a_unit = make_unit(client, alice, "Intercessors", "Space Marines", 80)
    b_unit = make_unit(client, bob, "Boyz", "Orks", 90)
    code = new_game(client, alice)
    client.post(f"/api/games/{code}/join", headers=bob)
    select_army(client, code, alice, [a_unit["id"]])
    select_army(client, code, bob, [b_unit["id"]])
    return code, alice, bob


def ready_both(client, code: str, alice: dict, bob: dict) -> dict:
    client.post(f"/api/games/{code}/ready", headers=alice)
    return client.post(f"/api/games/{code}/ready", headers=bob).json()


def test_readying_up_does_not_start_the_game(client):
    code, alice, bob = two_player_lobby(client)

    state = ready_both(client, code, alice, bob)

    assert state["status"] == "lobby"
    assert state["active_player_id"] is None
    assert state["ready_to_start"] is True


def test_any_player_can_start_not_just_the_creator(client):
    code, alice, bob = two_player_lobby(client)
    ready_both(client, code, alice, bob)

    # Bob joined second and did not open the game, but may still start it.
    started = client.post(f"/api/games/{code}/start", headers=bob)

    assert started.status_code == 200, started.text
    body = started.json()
    assert body["status"] == "active"
    assert body["phase_name"] == "Command"
    assert body["current_round"] == 1
    assert body["active_player_id"] is not None
    # Once running, the lobby button must not offer to start it again.
    assert body["ready_to_start"] is False


def test_cannot_start_until_everyone_is_ready(client):
    code, alice, bob = two_player_lobby(client)
    client.post(f"/api/games/{code}/ready", headers=alice)  # Bob is not ready

    response = client.post(f"/api/games/{code}/start", headers=alice)

    assert response.status_code == 409
    assert "ready up" in response.json()["detail"]
    assert client.get(f"/api/games/{code}", headers=alice).json()["ready_to_start"] is False


def test_cannot_start_without_an_army(client):
    """Ready plus an empty army is not startable, even though both are ready."""
    alice = register(client, "Alice")
    bob = register(client, "Bob")
    a_unit = make_unit(client, alice, "Intercessors", "Space Marines", 80)
    code = new_game(client, alice)
    client.post(f"/api/games/{code}/join", headers=bob)
    select_army(client, code, alice, [a_unit["id"]])
    client.post(f"/api/games/{code}/ready", headers=alice)
    # Bob cannot even ready up without an army, so he stays not-ready.
    assert client.post(f"/api/games/{code}/ready", headers=bob).status_code == 409

    response = client.post(f"/api/games/{code}/start", headers=alice)

    assert response.status_code == 409
    assert client.get(f"/api/games/{code}", headers=alice).json()["ready_to_start"] is False


def test_cannot_start_a_solo_lobby(client):
    alice = register(client, "Alice")
    unit = make_unit(client, alice, "Intercessors", "Space Marines", 80)
    code = new_game(client, alice)
    select_army(client, code, alice, [unit["id"]])
    client.post(f"/api/games/{code}/ready", headers=alice)

    response = client.post(f"/api/games/{code}/start", headers=alice)

    assert response.status_code == 409
    assert "two players" in response.json()["detail"]


def test_non_member_cannot_start(client):
    code, alice, bob = two_player_lobby(client)
    ready_both(client, code, alice, bob)
    stranger = register(client, "Mallory")

    response = client.post(f"/api/games/{code}/start", headers=stranger)

    assert response.status_code == 403
    assert client.get(f"/api/games/{code}", headers=alice).json()["status"] == "lobby"


def test_cannot_start_twice(client):
    code, alice, bob = two_player_lobby(client)
    ready_both(client, code, alice, bob)
    assert client.post(f"/api/games/{code}/start", headers=alice).status_code == 200

    again = client.post(f"/api/games/{code}/start", headers=bob)

    assert again.status_code == 409
    assert "already started" in again.json()["detail"]


def test_unreadying_withdraws_the_start_offer(client):
    code, alice, bob = two_player_lobby(client)
    ready_both(client, code, alice, bob)
    assert client.get(f"/api/games/{code}", headers=alice).json()["ready_to_start"] is True

    # Alice changes her mind before anyone pressed Start.
    state = client.post(f"/api/games/{code}/ready", headers=alice).json()

    assert state["ready_to_start"] is False
    assert client.post(f"/api/games/{code}/start", headers=bob).status_code == 409


def test_changing_army_withdraws_the_start_offer(client):
    """Replacing an army clears that player's readiness, so Start must go away."""
    code, alice, bob = two_player_lobby(client)
    ready_both(client, code, alice, bob)
    extra = make_unit(client, alice, "Terminators", "Space Marines", 180)

    state = select_army(client, code, alice, [extra["id"]])

    assert state["ready_to_start"] is False
    assert client.post(f"/api/games/{code}/start", headers=bob).status_code == 409
