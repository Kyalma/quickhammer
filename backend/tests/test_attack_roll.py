"""Rolled shooting resolution. The RNG is seeded, so every die is assertable."""
import random

import pytest

from app.services.attack_roll import (
    AUTO_HIT,
    AUTO_WOUND,
    CRITICAL_HIT,
    HIT,
    MISS,
    NO_SAVE,
    SAVE_FAILED,
    SAVED,
    SUSTAINED_HIT,
    TargetProfile,
    WeaponProfile,
    allocate_damage,
    best_save,
    resolve_shooting,
    roll_dice,
)


class FixedRng(random.Random):
    """Returns a scripted sequence of die results, for exact assertions."""

    def __init__(self, values):
        super().__init__()
        self.values = list(values)
        self.used = 0

    def randint(self, a, b):  # noqa: ARG002 - range is fixed by the caller
        if self.used >= len(self.values):
            raise AssertionError("The roller asked for more dice than the test scripted")
        value = self.values[self.used]
        self.used += 1
        return value


def weapon(**overrides) -> WeaponProfile:
    defaults = dict(
        name="Bolt rifle", attacks="1", skill=3, strength=4, ap=0,
        damage="1", keywords=[], carriers=1,
    )
    defaults.update(overrides)
    return WeaponProfile(**defaults)


def target(**overrides) -> TargetProfile:
    defaults = dict(
        name="Boyz", toughness=4, save=6, invuln_save=None, wounds=1,
        model_count=10, models_lost=0, wounds_lost=0,
    )
    defaults.update(overrides)
    return TargetProfile(**defaults)


def fire(weapons, target_profile, rng, attacker_models: int = 5):
    """Roll an attack.

    `attacker_models` is the size of the ATTACKING unit and must never come from
    the target. A default is supplied so each test states only what it cares
    about; the tests below that care pass it explicitly.
    """
    return resolve_shooting(weapons, attacker_models, target_profile, rng)


def stage(result: dict, name: str, weapon_index: int = 0) -> dict:
    return next(s for s in result["weapons"][weapon_index]["stages"] if s["name"] == name)


def outcomes(result: dict, name: str, weapon_index: int = 0) -> list[str]:
    return [d["outcome"] for d in stage(result, name, weapon_index)["dice"]]


class TestRollDice:
    def test_flat_value_rolls_nothing(self):
        assert roll_dice("3", FixedRng([])) == (3, [])

    def test_single_die(self):
        assert roll_dice("D6", FixedRng([4])) == (4, [4])

    def test_multiple_dice_sum(self):
        assert roll_dice("2D6", FixedRng([3, 5])) == (8, [3, 5])

    def test_bonus_is_added_once(self):
        assert roll_dice("D6+2", FixedRng([4])) == (6, [4])

    def test_invalid_notation_raises(self):
        with pytest.raises(ValueError):
            roll_dice("banana", FixedRng([]))


class TestBestSave:
    def test_ap_worsens_the_armour_save(self):
        assert best_save(3, None, 2) == (5, False)

    def test_invulnerable_used_when_better(self):
        assert best_save(3, 4, 3) == (4, True)

    def test_armour_kept_when_better_than_invulnerable(self):
        assert best_save(2, 5, 0) == (2, False)

    def test_no_save_possible_when_worse_than_six(self):
        number, _ = best_save(6, None, 2)
        assert number > 6


class TestAllocateDamage:
    def test_one_damage_kills_a_one_wound_model(self):
        models_lost, wounds_lost, _ = allocate_damage(target(wounds=1), [1])
        assert (models_lost, wounds_lost) == (1, 0)

    def test_excess_damage_does_not_spill_to_the_next_model(self):
        # 6 damage against 2-wound models kills ONE model, not three.
        models_lost, wounds_lost, notes = allocate_damage(
            target(wounds=2, model_count=5), [6]
        )
        assert (models_lost, wounds_lost) == (1, 0)
        assert "excess lost" in notes[0]

    def test_partial_damage_wounds_the_lead_model(self):
        models_lost, wounds_lost, _ = allocate_damage(
            target(wounds=3, model_count=5), [2]
        )
        assert (models_lost, wounds_lost) == (0, 2)

    def test_damage_finishes_an_already_wounded_lead_model(self):
        # Lead model already has 2 of 3 wounds lost, so 1 more kills it.
        models_lost, wounds_lost, _ = allocate_damage(
            target(wounds=3, model_count=5, wounds_lost=2), [1]
        )
        assert (models_lost, wounds_lost) == (1, 0)

    def test_separate_instances_kill_separate_models(self):
        models_lost, wounds_lost, _ = allocate_damage(
            target(wounds=2, model_count=5), [2, 2, 2]
        )
        assert (models_lost, wounds_lost) == (3, 0)

    def test_allocation_stops_once_the_unit_is_wiped(self):
        models_lost, wounds_lost, notes = allocate_damage(
            target(wounds=1, model_count=2), [1, 1, 1, 1]
        )
        assert (models_lost, wounds_lost) == (2, 0)
        assert sum("wasted" in n for n in notes) == 2


class TestHitRolls:
    def test_outcomes_follow_the_skill(self):
        result = fire(
            [weapon(attacks="4", skill=3, carriers=1)],
            target(),
            FixedRng([1, 3, 6, 2] + [6, 6, 6, 6] + [1, 1, 1, 1] + []),
        )
        assert outcomes(result, "Hit rolls") == [MISS, HIT, CRITICAL_HIT, MISS]

    def test_a_one_always_misses_even_at_skill_one(self):
        result = fire(
            [weapon(attacks="1", skill=2)], target(), FixedRng([1])
        )
        assert outcomes(result, "Hit rolls") == [MISS]

    def test_torrent_rolls_no_hit_dice(self):
        result = fire(
            [weapon(attacks="3", keywords=["Torrent"])],
            target(),
            # No hit dice: straight to 3 wound rolls, then saves.
            FixedRng([2, 2, 2] + [1, 1, 1]),
        )
        assert outcomes(result, "Hit rolls") == [AUTO_HIT, AUTO_HIT, AUTO_HIT]
        assert any("TORRENT" in n for n in result["notes"])

    def test_torrent_disables_crit_keywords(self):
        result = fire(
            [weapon(attacks="2", keywords=["Torrent", "Sustained Hits 1"])],
            target(),
            FixedRng([2, 2] + [1, 1]),
        )
        assert SUSTAINED_HIT not in outcomes(result, "Hit rolls")
        assert any("disables" in n for n in result["notes"])

    def test_sustained_hits_adds_extra_hits_per_critical(self):
        result = fire(
            [weapon(attacks="2", keywords=["Sustained Hits 2"])],
            target(),
            # Two hit dice: one crit, one miss -> 1 hit + 2 sustained = 3 wound rolls.
            FixedRng([6, 1] + [1, 1, 1]),
        )
        hit_outcomes = outcomes(result, "Hit rolls")
        assert hit_outcomes.count(SUSTAINED_HIT) == 2
        assert len(stage(result, "Wound rolls")["dice"]) == 3


class TestWoundRolls:
    def test_lethal_hits_converts_crits_to_automatic_wounds(self):
        result = fire(
            [weapon(attacks="2", strength=4, keywords=["Lethal Hits"])],
            target(toughness=10),  # would need 6+ to wound normally
            # crit + normal hit; the normal hit rolls one wound die and fails.
            FixedRng([6, 3] + [1] + [1]),
        )
        wound_outcomes = outcomes(result, "Wound rolls")
        assert AUTO_WOUND in wound_outcomes
        # One automatic wound plus one rolled die, not two rolled dice.
        assert len(wound_outcomes) == 2

    def test_wound_threshold_comes_from_the_strength_chart(self):
        result = fire(
            [weapon(attacks="1", strength=8)],
            target(toughness=4),  # S8 vs T4 wounds on 2+
            FixedRng([3] + [2] + [1] + []),
        )
        assert "needs 2+" in stage(result, "Wound rolls")["summary"]


class TestSaves:
    def test_failed_and_passed_saves_are_labelled(self):
        result = fire(
            [weapon(attacks="2", skill=2, ap=0)],
            target(save=4, wounds=1),
            FixedRng([5, 5] + [5, 5] + [6, 2]),
        )
        assert outcomes(result, "Saving throws") == [SAVED, SAVE_FAILED]

    def test_no_save_possible_rolls_no_dice(self):
        result = fire(
            [weapon(attacks="1", skill=2, ap=3)],
            target(save=5, invuln_save=None),
            FixedRng([5] + [5] + []),  # hit, wound, then no save dice
        )
        assert outcomes(result, "Saving throws") == [NO_SAVE]

    def test_invulnerable_save_is_used_when_better(self):
        result = fire(
            [weapon(attacks="1", skill=2, ap=4)],
            target(save=3, invuln_save=4),
            FixedRng([5] + [5] + [4]),
        )
        assert "invulnerable save 4+" in stage(result, "Saving throws")["summary"]


class TestCarriers:
    """How many models fire must depend ONLY on the attacking unit.

    Regression guard: this used to be taken from the target, so a lone character
    shooting a ten-model squad fired ten times.
    """

    def test_a_lone_model_fires_once_at_a_big_squad(self):
        result = fire(
            [weapon(attacks="3", carriers=0)],
            target(model_count=9, models_lost=0),  # a nine-model squad
            FixedRng([1, 1, 1]),
            attacker_models=1,                     # a single character
        )
        assert result["weapons"][0]["models_firing"] == 1
        assert len(stage(result, "Hit rolls")["dice"]) == 3  # 1 model x 3 attacks

    def test_target_size_never_changes_the_attack(self):
        small = fire([weapon(attacks="2", carriers=0)], target(model_count=1),
                     FixedRng([1, 1, 1, 1]), attacker_models=2)
        big = fire([weapon(attacks="2", carriers=0)], target(model_count=20),
                   FixedRng([1, 1, 1, 1]), attacker_models=2)
        assert small["weapons"][0]["models_firing"] == 2
        assert big["weapons"][0]["models_firing"] == 2

    def test_each_carrier_rolls_its_own_variable_attacks(self):
        result = fire(
            [weapon(attacks="D6", carriers=3)],
            target(),
            # Three attack dice, then 2+3+1=6 hit dice, all missing.
            FixedRng([2, 3, 1] + [1] * 6),
            attacker_models=5,
        )
        assert len(stage(result, "Attacks")["dice"]) == 3
        assert len(stage(result, "Hit rolls")["dice"]) == 6

    def test_zero_carriers_means_every_surviving_attacking_model(self):
        result = fire(
            [weapon(attacks="1", carriers=0)],
            target(model_count=10, models_lost=6),
            FixedRng([1, 1, 1, 1]),
            attacker_models=4,  # the ATTACKER has four models left
        )
        assert result["weapons"][0]["models_firing"] == 4

    def test_carriers_capped_by_the_attackers_surviving_models(self):
        result = fire(
            [weapon(attacks="1", carriers=10)],
            target(model_count=10),
            FixedRng([1, 1]),
            attacker_models=2,  # only two left to carry it
        )
        assert result["weapons"][0]["models_firing"] == 2


class TestMultipleWeapons:
    def test_weapons_resolve_separately_and_damage_accumulates(self):
        result = fire(
            [
                weapon(name="Bolt rifle", attacks="1", skill=2, ap=6),
                weapon(name="Plasma gun", attacks="1", skill=2, ap=6),
            ],
            target(wounds=1, model_count=5, save=3),
            # Rifle: hit 4, wound 4, no save (AP-6), damage flat.
            # Plasma: hit 4, wound 4, no save.
            FixedRng([4] + [4] + [] + [4] + [4] + []),
        )
        assert [w["weapon"] for w in result["weapons"]] == ["Bolt rifle", "Plasma gun"]
        assert result["models_slain"] == 2
        assert result["total_damage"] == 2

    def test_outcome_reports_destruction(self):
        result = fire(
            [weapon(attacks="2", skill=2, ap=6)],
            target(wounds=1, model_count=2, save=3),
            FixedRng([4, 4] + [4, 4] + []),
        )
        assert result["destroyed"] is True
        assert "destroyed" in result["outcome"]
        assert result["result_models_lost"] == 2

    def test_unharmed_outcome_when_everything_misses(self):
        result = fire(
            [weapon(attacks="2", skill=4)], target(), FixedRng([1, 2])
        )
        assert result["models_slain"] == 0
        assert result["destroyed"] is False
        assert "unharmed" in result["outcome"]

