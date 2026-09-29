"""Shooting phase API: roll, then confirm or discard."""
from .test_api import client, register, select_army  # noqa: F401 (fixture)

RIFLE = {
    "name": "Bolt rifle", "kind": "ranged", "range": 24, "attacks": "2",
    "skill": 3, "strength": 4, "ap": 1, "damage": "1", "keywords": [],
}
PISTOL = {
    "name": "Bolt pistol", "kind": "ranged", "range": 12, "attacks": "1",
    "skill": 3, "strength": 4, "ap": 0, "damage": "1", "keywords": ["Pistol"],
    "carrier_count": 1,
}
CHAINSWORD = {
    "name": "Chainsword", "kind": "melee", "range": 0, "attacks": "3",
    "skill": 3, "strength": 4, "ap": 0, "damage": "1", "keywords": [],
}


def squad(
    name: str, faction: str, keywords: list[str], weapons: list[dict],
    model_count: int = 5,
) -> dict:
    return {
        "name": name, "faction": faction, "points": 100, "keywords": keywords,
        "model_count": model_count, "wounds": 1, "toughness": 4, "save": 4,
        "leadership": 6, "weapons": weapons,
    }


def setup_shooting_game(
    client, attacker_weapons=None, attacker_keywords=None,
    attacker_models: int = 5, target_models: int = 9,
):
    """Two players in an active game, advanced to the attacker's Shooting phase.

    The attacker and target have DIFFERENT model counts by default, so a mix-up
    between the two shows up immediately.
    """
    alice = register(client, "Alice")
    bob = register(client, "Bob")
    a_unit = client.post("/api/units", json=squad(
        "Intercessors", "Space Marines",
        attacker_keywords if attacker_keywords is not None else ["Infantry"],
        attacker_weapons if attacker_weapons is not None else [RIFLE, CHAINSWORD],
        model_count=attacker_models,
    ), headers=alice).json()
    b_unit = client.post("/api/units", json=squad(
        "Boyz", "Orks", ["Infantry"], [RIFLE], model_count=target_models,
    ), headers=bob).json()

    code = client.post("/api/games", headers=alice).json()["code"]
    client.post(f"/api/games/{code}/join", headers=bob)
    select_army(client, code, alice, [a_unit["id"]])
    select_army(client, code, bob, [b_unit["id"]])
    client.post(f"/api/games/{code}/ready", headers=alice)
    client.post(f"/api/games/{code}/ready", headers=bob)
    state = client.post(f"/api/games/{code}/start", headers=alice).json()

    # Command -> Movement -> Shooting
    client.post(f"/api/games/{code}/advance", headers=alice)
    state = client.post(f"/api/games/{code}/advance", headers=alice).json()
    assert state["phase_name"] == "Shooting"

    a_entry = army_of(state, "Alice")["army"][0]
    b_entry = army_of(state, "Bob")["army"][0]
    a_full = client.get(f"/api/units/{a_unit['id']}", headers=alice).json()
    return alice, bob, code, a_entry, b_entry, a_full


def army_of(state: dict, name: str) -> dict:
    return next(p for p in state["players"] if p["player"]["name"] == name)


def weapon_id(unit: dict, name: str) -> int:
    return next(w["id"] for w in unit["weapons"] if w["name"] == name)


def shoot(client, code, headers, attacker, target, weapon_ids):
    return client.post(
        f"/api/games/{code}/shooting/resolve",
        json={
            "attacker_game_unit_id": attacker,
            "weapon_ids": weapon_ids,
            "target_game_unit_id": target,
        },
        headers=headers,
    )


class TestResolve:
    def test_rolling_returns_every_stage_with_dice(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        response = shoot(client, code, alice, a["id"], b["id"],
                         [weapon_id(unit, "Bolt rifle")])
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["attacker_name"] == "Intercessors"
        assert body["target_name"] == "Boyz"
        stages = body["rolls"]["weapons"][0]["stages"]
        assert [s["name"] for s in stages] == [
            "Attacks", "Hit rolls", "Wound rolls", "Saving throws", "Damage",
        ]
        # The ATTACKER has 5 models and 2 attacks each, so 10 hit dice. The
        # target's 9 models must not come into it.
        assert body["rolls"]["weapons"][0]["models_firing"] == 5
        hits = next(s for s in stages if s["name"] == "Hit rolls")
        assert len(hits["dice"]) == 10
        assert all("outcome" in d for d in hits["dice"])
        assert body["applied"] is False

    def test_a_lone_character_fires_once_at_a_big_squad(self, client):
        """Regression: model count used to be read from the target."""
        alice, _, code, a, b, unit = setup_shooting_game(
            client, attacker_models=1, target_models=9
        )
        body = shoot(client, code, alice, a["id"], b["id"],
                     [weapon_id(unit, "Bolt rifle")]).json()
        assert body["rolls"]["weapons"][0]["models_firing"] == 1
        stages = {s["name"]: s for s in body["rolls"]["weapons"][0]["stages"]}
        assert len(stages["Hit rolls"]["dice"]) == 2  # 1 model x 2 attacks

    def test_casualties_reduce_how_many_models_fire(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(
            client, attacker_models=5, target_models=9
        )
        client.post(f"/api/games/{code}/units/{a['id']}/damage",
                    json={"wounds": 3}, headers=alice)
        body = shoot(client, code, alice, a["id"], b["id"],
                     [weapon_id(unit, "Bolt rifle")]).json()
        assert body["rolls"]["weapons"][0]["models_firing"] == 2

    def test_rolling_spends_the_units_shot(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        shoot(client, code, alice, a["id"], b["id"], [weapon_id(unit, "Bolt rifle")])
        state = client.get(f"/api/games/{code}", headers=alice).json()
        assert army_of(state, "Alice")["army"][0]["has_shot"] is True

    def test_a_unit_cannot_shoot_twice_in_a_phase(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        shoot(client, code, alice, a["id"], b["id"], [weapon_id(unit, "Bolt rifle")])
        again = shoot(client, code, alice, a["id"], b["id"],
                      [weapon_id(unit, "Bolt rifle")])
        assert again.status_code == 409
        assert "already shot" in again.json()["detail"]

    def test_pending_roll_is_announced_in_the_game_state(self, client):
        alice, bob, code, a, b, unit = setup_shooting_game(client)
        rolled = shoot(client, code, alice, a["id"], b["id"],
                       [weapon_id(unit, "Bolt rifle")]).json()
        # The defender can see that an attack is being resolved, and read it.
        state = client.get(f"/api/games/{code}", headers=bob).json()
        assert state["pending_attack_id"] == rolled["id"]
        seen = client.get(f"/api/games/{code}/shooting/{rolled['id']}", headers=bob)
        assert seen.status_code == 200
        assert seen.json()["target_name"] == "Boyz"

    def test_melee_weapons_cannot_be_fired(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        response = shoot(client, code, alice, a["id"], b["id"],
                         [weapon_id(unit, "Chainsword")])
        assert response.status_code == 422
        assert "melee" in response.json()["detail"]

    def test_infantry_cannot_mix_pistols_with_other_weapons(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(
            client, attacker_weapons=[RIFLE, PISTOL], attacker_keywords=["Infantry"]
        )
        response = shoot(client, code, alice, a["id"], b["id"], [
            weapon_id(unit, "Bolt rifle"), weapon_id(unit, "Bolt pistol"),
        ])
        assert response.status_code == 422
        assert "pistols" in response.json()["detail"]

    def test_a_vehicle_may_mix_pistols_with_other_weapons(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(
            client, attacker_weapons=[RIFLE, PISTOL], attacker_keywords=["Vehicle"]
        )
        response = shoot(client, code, alice, a["id"], b["id"], [
            weapon_id(unit, "Bolt rifle"), weapon_id(unit, "Bolt pistol"),
        ])
        assert response.status_code == 201, response.text
        assert len(response.json()["rolls"]["weapons"]) == 2

    def test_carrier_count_limits_how_many_models_fire_a_weapon(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(
            client, attacker_weapons=[PISTOL], attacker_keywords=["Infantry"]
        )
        body = shoot(client, code, alice, a["id"], b["id"],
                     [weapon_id(unit, "Bolt pistol")]).json()
        # carrier_count 1 in a 5-model squad: only the one model fires.
        assert body["rolls"]["weapons"][0]["models_firing"] == 1

    def test_cannot_shoot_outside_the_shooting_phase(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        client.post(f"/api/games/{code}/advance", headers=alice)  # into Charge
        response = shoot(client, code, alice, a["id"], b["id"],
                         [weapon_id(unit, "Bolt rifle")])
        assert response.status_code == 409
        assert "Shooting phase" in response.json()["detail"]

    def test_only_the_active_player_can_shoot(self, client):
        alice, bob, code, a, b, unit = setup_shooting_game(client)
        b_full = client.get("/api/units", headers=bob).json()[0]
        response = shoot(client, code, bob, b["id"], a["id"],
                         [weapon_id(b_full, "Bolt rifle")])
        assert response.status_code == 403

    def test_cannot_shoot_your_own_unit(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        response = shoot(client, code, alice, a["id"], a["id"],
                         [weapon_id(unit, "Bolt rifle")])
        assert response.status_code == 400

    def test_cannot_shoot_a_destroyed_target(self, client):
        alice, bob, code, a, b, unit = setup_shooting_game(client)
        client.post(f"/api/games/{code}/units/{b['id']}/damage",
                    json={"wounds": 99}, headers=bob)
        response = shoot(client, code, alice, a["id"], b["id"],
                         [weapon_id(unit, "Bolt rifle")])
        assert response.status_code == 409
        assert "destroyed" in response.json()["detail"]

    def test_weapon_must_belong_to_the_attacking_unit(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        response = shoot(client, code, alice, a["id"], b["id"], [9999])
        assert response.status_code == 404


class TestConfirmAndDiscard:
    def test_confirming_applies_damage_to_the_enemy_unit(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        rolled = shoot(client, code, alice, a["id"], b["id"],
                       [weapon_id(unit, "Bolt rifle")]).json()
        expected = rolled["rolls"]["result_models_lost"]

        state = client.post(
            f"/api/games/{code}/shooting/{rolled['id']}/confirm", headers=alice
        ).json()
        target = army_of(state, "Bob")["army"][0]
        assert target["models_remaining"] == target["model_count"] - expected
        assert state["pending_attack_id"] is None

    def test_confirming_twice_is_rejected(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        rolled = shoot(client, code, alice, a["id"], b["id"],
                       [weapon_id(unit, "Bolt rifle")]).json()
        client.post(f"/api/games/{code}/shooting/{rolled['id']}/confirm", headers=alice)
        again = client.post(
            f"/api/games/{code}/shooting/{rolled['id']}/confirm", headers=alice
        )
        assert again.status_code == 409

    def test_discarding_applies_nothing_and_gives_the_shot_back(self, client):
        """Discard is a full undo, so a mis-picked target can be corrected."""
        alice, _, code, a, b, unit = setup_shooting_game(client)
        rolled = shoot(client, code, alice, a["id"], b["id"],
                       [weapon_id(unit, "Bolt rifle")]).json()
        state = client.post(
            f"/api/games/{code}/shooting/{rolled['id']}/discard", headers=alice
        ).json()
        target = army_of(state, "Bob")["army"][0]
        assert target["models_remaining"] == target["model_count"]
        assert army_of(state, "Alice")["army"][0]["has_shot"] is False

    def test_the_unit_can_shoot_again_after_a_discard(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        first = shoot(client, code, alice, a["id"], b["id"],
                      [weapon_id(unit, "Bolt rifle")]).json()
        client.post(f"/api/games/{code}/shooting/{first['id']}/discard", headers=alice)
        second = shoot(client, code, alice, a["id"], b["id"],
                       [weapon_id(unit, "Bolt rifle")])
        assert second.status_code == 201, second.text

    def test_a_confirmed_shot_stays_spent(self, client):
        alice, _, code, a, b, unit = setup_shooting_game(client)
        rolled = shoot(client, code, alice, a["id"], b["id"],
                       [weapon_id(unit, "Bolt rifle")]).json()
        client.post(f"/api/games/{code}/shooting/{rolled['id']}/confirm", headers=alice)
        again = shoot(client, code, alice, a["id"], b["id"],
                      [weapon_id(unit, "Bolt rifle")])
        assert again.status_code == 409
        assert "already shot" in again.json()["detail"]

    def test_the_opponent_cannot_confirm_your_attack(self, client):
        alice, bob, code, a, b, unit = setup_shooting_game(client)
        rolled = shoot(client, code, alice, a["id"], b["id"],
                       [weapon_id(unit, "Bolt rifle")]).json()
        response = client.post(
            f"/api/games/{code}/shooting/{rolled['id']}/confirm", headers=bob
        )
        assert response.status_code == 403


def test_shot_clears_for_the_next_round(client):
    alice, bob, code, a, b, unit = setup_shooting_game(client)
    shoot(client, code, alice, a["id"], b["id"], [weapon_id(unit, "Bolt rifle")])

    # Finish Alice's turn, play Bob's, and come back round to Alice's Shooting.
    for _ in range(3):
        client.post(f"/api/games/{code}/advance", headers=alice)
    for _ in range(5):
        client.post(f"/api/games/{code}/advance", headers=bob)
    client.post(f"/api/games/{code}/advance", headers=alice)
    state = client.post(f"/api/games/{code}/advance", headers=alice).json()
    assert state["phase_name"] == "Shooting"
    assert state["current_round"] == 2
    assert army_of(state, "Alice")["army"][0]["has_shot"] is False
