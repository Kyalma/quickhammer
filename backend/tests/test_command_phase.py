"""Command phase API: command points, casualties, and Battle-shock tests."""
from .test_api import UNIT_PAYLOAD, client, register, select_army  # noqa: F401 (fixture)

# A 10-model, 1-wound, Ld 6+ unit: easy to push below half strength.
HORDE = {
    **UNIT_PAYLOAD,
    "name": "Boyz",
    "faction": "Orks",
    "points": 90,
    "model_count": 10,
    "wounds": 1,
    "leadership": 6,
}


def start_two_player_game(client) -> tuple[dict, dict, str, dict, dict]:
    """Returns (alice_headers, bob_headers, code, alice_army_unit, bob_army_unit)
    with the game active and Alice to move."""
    alice = register(client, "Alice")
    bob = register(client, "Bob")
    a_unit = client.post("/api/units", json=HORDE, headers=alice).json()
    b_unit = client.post("/api/units", json=HORDE, headers=bob).json()
    code = client.post("/api/games", headers=alice).json()["code"]
    client.post(f"/api/games/{code}/join", headers=bob)
    state = select_army(client, code, alice, [a_unit["id"]])
    state = select_army(client, code, bob, [b_unit["id"]])
    client.post(f"/api/games/{code}/ready", headers=alice)
    state = client.post(f"/api/games/{code}/ready", headers=bob).json()
    assert state["status"] == "active"
    a_entry = next(p for p in state["players"] if p["player"]["name"] == "Alice")["army"][0]
    b_entry = next(p for p in state["players"] if p["player"]["name"] == "Bob")["army"][0]
    return alice, bob, code, a_entry, b_entry


def army_of(state: dict, name: str) -> dict:
    return next(p for p in state["players"] if p["player"]["name"] == name)


def damage(client, code, entry_id, headers, wounds: int) -> dict:
    response = client.post(
        f"/api/games/{code}/units/{entry_id}/damage", json={"wounds": wounds}, headers=headers
    )
    assert response.status_code == 200, response.text
    return response.json()


def advance_full_turn(client, code, headers) -> dict:
    """Walk the active player through all five phases, passing the turn on."""
    state = {}
    for _ in range(5):
        state = client.post(f"/api/games/{code}/advance", headers=headers).json()
    return state


class TestCommandPoints:
    def test_first_player_gains_cp_when_the_game_starts(self, client):
        alice, bob, code, _, _ = start_two_player_game(client)
        state = client.get(f"/api/games/{code}", headers=alice).json()
        assert army_of(state, "Alice")["command_points"] == 1
        assert army_of(state, "Bob")["command_points"] == 0

    def test_each_player_gains_cp_at_the_start_of_their_own_turn(self, client):
        alice, bob, code, _, _ = start_two_player_game(client)
        state = advance_full_turn(client, code, alice)  # Alice's turn ends, Bob's begins
        assert army_of(state, "Alice")["command_points"] == 1
        assert army_of(state, "Bob")["command_points"] == 1

        state = advance_full_turn(client, code, bob)  # round 2, Alice again
        assert state["current_round"] == 2
        assert army_of(state, "Alice")["command_points"] == 2
        assert army_of(state, "Bob")["command_points"] == 1


class TestCasualties:
    def test_damage_reduces_models_remaining(self, client):
        alice, _, code, a_entry, _ = start_two_player_game(client)
        state = damage(client, code, a_entry["id"], alice, 4)
        unit = army_of(state, "Alice")["army"][0]
        assert unit["models_remaining"] == 6
        assert unit["below_half_strength"] is False

    def test_exactly_half_is_not_below_half_strength(self, client):
        alice, _, code, a_entry, _ = start_two_player_game(client)
        state = damage(client, code, a_entry["id"], alice, 5)
        unit = army_of(state, "Alice")["army"][0]
        assert unit["models_remaining"] == 5
        assert unit["below_half_strength"] is False
        assert unit["needs_shock_test"] is False

    def test_below_half_strength_flags_a_pending_test(self, client):
        alice, _, code, a_entry, _ = start_two_player_game(client)
        state = damage(client, code, a_entry["id"], alice, 6)
        unit = army_of(state, "Alice")["army"][0]
        assert unit["models_remaining"] == 4
        assert unit["below_half_strength"] is True
        assert unit["needs_shock_test"] is True

    def test_wiping_a_unit_marks_it_destroyed(self, client):
        alice, _, code, a_entry, _ = start_two_player_game(client)
        state = damage(client, code, a_entry["id"], alice, 10)
        unit = army_of(state, "Alice")["army"][0]
        assert unit["is_destroyed"] is True
        assert unit["needs_shock_test"] is False  # destroyed units do not test

    def test_healing_undoes_damage(self, client):
        alice, _, code, a_entry, _ = start_two_player_game(client)
        damage(client, code, a_entry["id"], alice, 6)
        state = damage(client, code, a_entry["id"], alice, -6)
        unit = army_of(state, "Alice")["army"][0]
        assert unit["models_remaining"] == 10
        assert unit["below_half_strength"] is False

    def test_cannot_damage_another_players_unit(self, client):
        alice, bob, code, a_entry, _ = start_two_player_game(client)
        response = client.post(
            f"/api/games/{code}/units/{a_entry['id']}/damage",
            json={"wounds": 5},
            headers=bob,
        )
        assert response.status_code == 403

    def test_unknown_unit_is_404(self, client):
        alice, _, code, _, _ = start_two_player_game(client)
        response = client.post(
            f"/api/games/{code}/units/9999/damage", json={"wounds": 1}, headers=alice
        )
        assert response.status_code == 404


class TestBattleShockTest:
    def shocked_setup(self, client):
        alice, bob, code, a_entry, b_entry = start_two_player_game(client)
        damage(client, code, a_entry["id"], alice, 6)  # 4 of 10 remain
        return alice, bob, code, a_entry, b_entry

    def test_failing_the_test_battle_shocks_the_unit(self, client):
        alice, _, code, a_entry, _ = self.shocked_setup(client)
        response = client.post(
            f"/api/games/{code}/units/{a_entry['id']}/battle-shock",
            json={"roll": 4},  # Ld 6+, so 4 fails
            headers=alice,
        )
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["passed"] is False
        assert body["leadership"] == 6
        unit = army_of(body["game"], "Alice")["army"][0]
        assert unit["is_battle_shocked"] is True
        assert unit["needs_shock_test"] is False  # already tested this round

    def test_passing_the_test_leaves_the_unit_alone(self, client):
        alice, _, code, a_entry, _ = self.shocked_setup(client)
        body = client.post(
            f"/api/games/{code}/units/{a_entry['id']}/battle-shock",
            json={"roll": 9},
            headers=alice,
        ).json()
        assert body["passed"] is True
        assert army_of(body["game"], "Alice")["army"][0]["is_battle_shocked"] is False

    def test_cannot_test_twice_in_the_same_round(self, client):
        alice, _, code, a_entry, _ = self.shocked_setup(client)
        client.post(
            f"/api/games/{code}/units/{a_entry['id']}/battle-shock",
            json={"roll": 4},
            headers=alice,
        )
        again = client.post(
            f"/api/games/{code}/units/{a_entry['id']}/battle-shock",
            json={"roll": 12},
            headers=alice,
        )
        assert again.status_code == 409
        assert "already tested" in again.json()["detail"]

    def test_healthy_units_cannot_be_tested(self, client):
        alice, bob, code, a_entry, b_entry = start_two_player_game(client)
        response = client.post(
            f"/api/games/{code}/units/{a_entry['id']}/battle-shock",
            json={"roll": 4},
            headers=alice,
        )
        assert response.status_code == 409
        assert "below half strength" in response.json()["detail"]

    def test_destroyed_units_cannot_be_tested(self, client):
        alice, _, code, a_entry, _ = start_two_player_game(client)
        damage(client, code, a_entry["id"], alice, 10)
        response = client.post(
            f"/api/games/{code}/units/{a_entry['id']}/battle-shock",
            json={"roll": 4},
            headers=alice,
        )
        assert response.status_code == 409
        assert "destroyed" in response.json()["detail"]

    def test_only_the_active_player_can_test(self, client):
        alice, bob, code, a_entry, b_entry = self.shocked_setup(client)
        damage(client, code, b_entry["id"], bob, 6)
        response = client.post(
            f"/api/games/{code}/units/{b_entry['id']}/battle-shock",
            json={"roll": 4},
            headers=bob,  # Alice is the active player
        )
        assert response.status_code == 403

    def test_cannot_test_outside_the_command_phase(self, client):
        alice, _, code, a_entry, _ = self.shocked_setup(client)
        client.post(f"/api/games/{code}/advance", headers=alice)  # into Movement
        response = client.post(
            f"/api/games/{code}/units/{a_entry['id']}/battle-shock",
            json={"roll": 4},
            headers=alice,
        )
        assert response.status_code == 409
        assert "Command phase" in response.json()["detail"]

    def test_roll_must_be_a_possible_2d6_total(self, client):
        alice, _, code, a_entry, _ = self.shocked_setup(client)
        for bad in (1, 13):
            response = client.post(
                f"/api/games/{code}/units/{a_entry['id']}/battle-shock",
                json={"roll": bad},
                headers=alice,
            )
            assert response.status_code == 422

    def test_battle_shock_clears_at_the_start_of_the_owners_next_turn(self, client):
        alice, bob, code, a_entry, _ = self.shocked_setup(client)
        body = client.post(
            f"/api/games/{code}/units/{a_entry['id']}/battle-shock",
            json={"roll": 3},
            headers=alice,
        ).json()
        assert army_of(body["game"], "Alice")["army"][0]["is_battle_shocked"] is True

        # Alice's turn ends, Bob plays a full turn: still shocked through Bob's turn.
        state = advance_full_turn(client, code, alice)
        assert army_of(state, "Alice")["army"][0]["is_battle_shocked"] is True

        # Alice's next Command phase begins: shock wears off and she can test again.
        state = advance_full_turn(client, code, bob)
        unit = army_of(state, "Alice")["army"][0]
        assert unit["is_battle_shocked"] is False
        assert unit["needs_shock_test"] is True  # still below half, new round
