"""Unit tests for the pure combat math."""
import pytest

from app.services.combat import (
    AttackerProfile,
    DefenderProfile,
    parse_dice,
    probability,
    resolve_attack,
    roll_needed_to_wound,
)


class TestParseDice:
    def test_flat_number(self):
        assert parse_dice("3") == 3

    def test_d6(self):
        assert parse_dice("D6") == 3.5

    def test_d3(self):
        assert parse_dice("D3") == 2.0

    def test_multiple_dice(self):
        assert parse_dice("2D6") == 7.0

    def test_dice_with_bonus(self):
        assert parse_dice("D6+2") == 5.5

    def test_lowercase_and_spaces(self):
        assert parse_dice(" 2d6+1 ") == 8.0

    @pytest.mark.parametrize("bad", ["", "abc", "D", "+3", "D6+"])
    def test_invalid(self, bad):
        with pytest.raises(ValueError):
            parse_dice(bad)


class TestWoundChart:
    def test_double_strength_wounds_on_2(self):
        assert roll_needed_to_wound(8, 4) == 2

    def test_higher_strength_wounds_on_3(self):
        assert roll_needed_to_wound(5, 4) == 3

    def test_equal_wounds_on_4(self):
        assert roll_needed_to_wound(4, 4) == 4

    def test_lower_strength_wounds_on_5(self):
        assert roll_needed_to_wound(3, 4) == 5

    def test_half_strength_wounds_on_6(self):
        assert roll_needed_to_wound(2, 4) == 6
        assert roll_needed_to_wound(3, 8) == 6


class TestProbability:
    def test_three_plus(self):
        assert probability(3) == pytest.approx(4 / 6)

    def test_never_auto_succeeds(self):
        # A 1 always fails: 2+ is the best possible roll.
        assert probability(1) == pytest.approx(5 / 6)
        assert probability(2) == pytest.approx(5 / 6)

    def test_impossible_roll(self):
        assert probability(7) == 0


def make_attacker(**overrides) -> AttackerProfile:
    defaults = dict(
        weapon_name="Boltgun", attacks="2", skill=3, strength=4,
        ap=0, damage="1", keywords=[], model_count=5,
    )
    defaults.update(overrides)
    return AttackerProfile(**defaults)


def make_defender(**overrides) -> DefenderProfile:
    defaults = dict(
        unit_name="Ork Boyz", toughness=5, save=5, invuln_save=None,
        wounds=1, model_count=10,
    )
    defaults.update(overrides)
    return DefenderProfile(**defaults)


class TestResolveAttack:
    def test_boltguns_into_boyz(self):
        """5 marines, 2 shots each, BS3+, S4 vs T5 (5+), Sv5+ unmodified."""
        result = resolve_attack(make_attacker(), make_defender())
        steps = {s["label"]: s["value"] for s in result["steps"]}
        assert steps["Attacks"] == 10
        assert steps["Hits"] == pytest.approx(10 * 4 / 6, abs=0.01)
        assert steps["Wounds"] == pytest.approx(10 * 4 / 6 * 2 / 6, abs=0.01)
        # Save 5+ succeeds 2/6 -> fails 4/6
        assert steps["Failed saves"] == pytest.approx(10 * 4 / 6 * 2 / 6 * 4 / 6, abs=0.01)
        assert result["expected_damage"] == steps["Damage"]

    def test_ap_worsens_save(self):
        no_ap = resolve_attack(make_attacker(ap=0), make_defender(save=3))
        with_ap = resolve_attack(make_attacker(ap=2), make_defender(save=3))
        assert with_ap["expected_damage"] > no_ap["expected_damage"]

    def test_invuln_caps_ap(self):
        """A 4++ ignores AP-3 on a 3+ armour save (3+3=6+ is worse than 4++)."""
        result = resolve_attack(
            make_attacker(ap=3), make_defender(save=3, invuln_save=4)
        )
        save_step = next(s for s in result["steps"] if s["label"] == "Failed saves")
        assert "invulnerable" in save_step["detail"]

    def test_no_save_possible(self):
        result = resolve_attack(make_attacker(ap=3), make_defender(save=5))
        wounds = next(s for s in result["steps"] if s["label"] == "Wounds")["value"]
        failed = next(s for s in result["steps"] if s["label"] == "Failed saves")["value"]
        assert failed == wounds  # 5+3 = 8+ -> every wound goes through

    def test_lethal_hits_increases_wounds_vs_tough_target(self):
        base = resolve_attack(make_attacker(), make_defender(toughness=10))
        lethal = resolve_attack(
            make_attacker(keywords=["LETHAL HITS"]), make_defender(toughness=10)
        )
        assert lethal["expected_damage"] > base["expected_damage"]

    def test_sustained_hits_adds_hits(self):
        base = resolve_attack(make_attacker(), make_defender())
        sustained = resolve_attack(
            make_attacker(keywords=["SUSTAINED HITS 1"]), make_defender()
        )
        base_hits = next(s for s in base["steps"] if s["label"] == "Hits")["value"]
        sus_hits = next(s for s in sustained["steps"] if s["label"] == "Hits")["value"]
        # 10 attacks -> 10/6 crits -> +1.67 expected extra hits
        assert sus_hits == pytest.approx(base_hits + 10 / 6, abs=0.01)

    def test_torrent_auto_hits(self):
        result = resolve_attack(
            make_attacker(skill=6, keywords=["TORRENT"]), make_defender()
        )
        hits = next(s for s in result["steps"] if s["label"] == "Hits")
        assert hits["value"] == 10  # every attack hits regardless of skill
        assert "TORRENT" in hits["detail"]

    def test_torrent_disables_crit_keywords(self):
        torrent_only = resolve_attack(make_attacker(keywords=["TORRENT"]), make_defender())
        with_lethal = resolve_attack(
            make_attacker(keywords=["TORRENT", "LETHAL HITS"]), make_defender()
        )
        assert with_lethal["expected_damage"] == torrent_only["expected_damage"]

    def test_unsupported_keyword_noted(self):
        result = resolve_attack(
            make_attacker(keywords=["DEVASTATING WOUNDS"]), make_defender()
        )
        assert any("DEVASTATING WOUNDS" in n for n in result["notes"])

    def test_models_slain_capped_at_unit_size(self):
        result = resolve_attack(
            make_attacker(attacks="20", strength=20, ap=6, damage="10"),
            make_defender(toughness=3, save=6, wounds=1, model_count=5),
        )
        assert result["expected_models_slain"] <= 5

    def test_damage_does_not_spill_over(self):
        """D6 damage vs 1-wound models: one failed save kills exactly one model."""
        result = resolve_attack(
            make_attacker(damage="D6"),
            make_defender(wounds=1, model_count=10),
        )
        failed = next(s for s in result["steps"] if s["label"] == "Failed saves")["value"]
        assert result["expected_models_slain"] == pytest.approx(failed, abs=0.01)
