"""Listing games, cancelling a lobby, and admin deletion of players and games.

The integrity cases matter most here: SQLite does not enforce foreign keys, so a
partial delete would leave rows pointing at nothing and only fail later.
"""
from .test_admin import make_admin_directly  # noqa: F401
from .test_api import UNIT_PAYLOAD, client, register, select_army  # noqa: F401 (fixture)
from .test_shooting import setup_shooting_game, shoot, weapon_id


def games_of(client, headers) -> dict:
    response = client.get("/api/games", headers=headers)
    assert response.status_code == 200, response.text
    return {g["code"]: g for g in response.json()}


class TestListGames:
    def test_lists_games_with_join_and_delete_flags(self, client):
        alice = register(client, "Alice")
        bob = register(client, "Bob")
        code = client.post("/api/games", headers=alice).json()["code"]

        mine = games_of(client, alice)[code]
        assert mine["is_member"] is True
        assert mine["can_join"] is False       # already in it
        assert mine["can_delete"] is True      # creator, still pending
        assert mine["creator_name"] == "Alice"
        assert mine["status"] == "lobby"

        theirs = games_of(client, bob)[code]
        assert theirs["is_member"] is False
        assert theirs["can_join"] is True
        assert theirs["can_delete"] is False   # not the creator

    def test_running_games_cannot_be_joined_or_deleted(self, client):
        alice, bob, code, _, _, _ = setup_shooting_game(client)
        listing = games_of(client, alice)[code]
        assert listing["status"] == "active"
        assert listing["can_join"] is False
        assert listing["can_delete"] is False
        assert sorted(listing["player_names"]) == ["Alice", "Bob"]

    def test_finished_games_are_hidden_from_players(self, client):
        alice, bob, code, _, _, _ = setup_shooting_game(client)
        assert code in games_of(client, alice)  # visible while running

        client.post(f"/api/games/{code}/finish", headers=alice)
        assert code not in games_of(client, alice)
        assert code not in games_of(client, bob)

    def test_admins_still_see_finished_games(self, client):
        alice, _, code, _, _, _ = setup_shooting_game(client)
        client.post(f"/api/games/{code}/finish", headers=alice)
        make_admin_directly("Alice")
        admin_view = client.get("/api/admin/games", headers=alice).json()
        assert [g["code"] for g in admin_view] == [code]
        assert admin_view[0]["status"] == "finished"

    def test_full_games_cannot_be_joined(self, client):
        alice = register(client, "Alice")
        code = client.post("/api/games", headers=alice).json()["code"]
        for name in ("Bob", "Carol", "Dave"):
            headers = register(client, name)
            client.post(f"/api/games/{code}/join", headers=headers)
        outsider = register(client, "Eve")
        assert games_of(client, outsider)[code]["can_join"] is False


class TestCreatorDeletesLobby:
    def test_creator_can_delete_a_pending_game(self, client):
        alice = register(client, "Alice")
        code = client.post("/api/games", headers=alice).json()["code"]
        assert client.delete(f"/api/games/{code}", headers=alice).status_code == 204
        assert code not in games_of(client, alice)
        assert client.get(f"/api/games/{code}", headers=alice).status_code == 404

    def test_another_player_cannot_delete_it(self, client):
        alice = register(client, "Alice")
        bob = register(client, "Bob")
        code = client.post("/api/games", headers=alice).json()["code"]
        client.post(f"/api/games/{code}/join", headers=bob)
        assert client.delete(f"/api/games/{code}", headers=bob).status_code == 403

    def test_a_started_game_cannot_be_deleted(self, client):
        alice, bob, code, _, _, _ = setup_shooting_game(client)
        response = client.delete(f"/api/games/{code}", headers=alice)
        assert response.status_code == 409
        assert "has started" in response.json()["detail"]

    def test_deleting_a_lobby_leaves_the_rosters_alone(self, client):
        alice = register(client, "Alice")
        unit = client.post("/api/units", json=UNIT_PAYLOAD, headers=alice).json()
        code = client.post("/api/games", headers=alice).json()["code"]
        select_army(client, code, alice, [unit["id"]])
        client.delete(f"/api/games/{code}", headers=alice)
        assert len(client.get("/api/units", headers=alice).json()) == 1


class TestAdminDeletesGames:
    def test_admin_can_delete_a_running_game(self, client):
        alice, bob, code, a_entry, b_entry, unit = setup_shooting_game(client)
        # Leave an attack roll behind: it references game_units by two FKs.
        shoot(client, code, alice, a_entry["id"], b_entry["id"],
              [weapon_id(unit, "Bolt rifle")])
        make_admin_directly("Alice")

        game_id = next(g["id"] for g in client.get("/api/admin/games", headers=alice).json())
        assert client.delete(f"/api/admin/games/{game_id}", headers=alice).status_code == 204
        assert client.get("/api/admin/games", headers=alice).json() == []
        # Rosters survive; only the game is gone.
        assert len(client.get("/api/units", headers=alice).json()) == 1

    def test_non_admins_cannot_delete_games(self, client):
        alice = register(client, "Alice")
        game = client.post("/api/games", headers=alice).json()
        assert client.delete(f"/api/admin/games/{game['id']}", headers=alice).status_code == 403

    def test_unknown_game_is_404(self, client):
        alice = register(client, "Alice")
        make_admin_directly("Alice")
        assert client.delete("/api/admin/games/9999", headers=alice).status_code == 404


class TestAdminDeletesPlayers:
    def test_deleting_a_player_removes_their_roster(self, client):
        alice = register(client, "Alice")
        bob = register(client, "Bob")
        client.post("/api/units", json=UNIT_PAYLOAD, headers=bob)
        make_admin_directly("Alice")

        bob_id = next(
            p["id"] for p in client.get("/api/admin/players", headers=alice).json()
            if p["name"] == "Bob"
        )
        assert client.delete(f"/api/admin/players/{bob_id}", headers=alice).status_code == 204
        names = [p["name"] for p in client.get("/api/admin/players", headers=alice).json()]
        assert names == ["Alice"]
        # Their token no longer identifies anyone.
        assert client.get("/api/players/me", headers=bob).status_code == 401

    def test_deleting_a_player_mid_game_keeps_the_game_usable(self, client):
        """The remaining player's view of the game must still serialize."""
        alice, bob, code, a_entry, b_entry, unit = setup_shooting_game(client)
        shoot(client, code, alice, a_entry["id"], b_entry["id"],
              [weapon_id(unit, "Bolt rifle")])
        make_admin_directly("Alice")

        bob_id = next(
            p["id"] for p in client.get("/api/admin/players", headers=alice).json()
            if p["name"] == "Bob"
        )
        assert client.delete(f"/api/admin/players/{bob_id}", headers=alice).status_code == 204

        state = client.get(f"/api/games/{code}", headers=alice)
        assert state.status_code == 200, state.text
        body = state.json()
        assert [p["player"]["name"] for p in body["players"]] == ["Alice"]
        assert body["pending_attack_id"] is None  # the roll went with the units

    def test_a_game_left_empty_is_removed(self, client):
        alice = register(client, "Alice")
        bob = register(client, "Bob")
        code = client.post("/api/games", headers=bob).json()["code"]
        make_admin_directly("Alice")

        bob_id = next(
            p["id"] for p in client.get("/api/admin/players", headers=alice).json()
            if p["name"] == "Bob"
        )
        client.delete(f"/api/admin/players/{bob_id}", headers=alice)
        assert client.get(f"/api/games/{code}", headers=alice).status_code == 404

    def test_admins_cannot_delete_themselves(self, client):
        alice = register(client, "Alice")
        make_admin_directly("Alice")
        alice_id = client.get("/api/players/me", headers=alice).json()["id"]
        response = client.delete(f"/api/admin/players/{alice_id}", headers=alice)
        assert response.status_code == 409
        assert "your own account" in response.json()["detail"]

    def test_non_admins_cannot_delete_players(self, client):
        alice = register(client, "Alice")
        bob = register(client, "Bob")
        bob_id = client.get("/api/players/me", headers=bob).json()["id"]
        assert client.delete(f"/api/admin/players/{bob_id}", headers=alice).status_code == 403

    def test_unknown_player_is_404(self, client):
        alice = register(client, "Alice")
        make_admin_directly("Alice")
        assert client.delete("/api/admin/players/9999", headers=alice).status_code == 404
