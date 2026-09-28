"""Unit tests for live unit state and Battle-shock rules."""
import pytest

from app.services.unit_state import (
    apply_wounds,
    is_below_half_strength,
    is_destroyed,
    models_remaining,
    passes_battle_shock,
)


class TestApplyWounds:
    def test_partial_damage_on_lead_model(self):
        # 5 models, 2 wounds each; 1 damage wounds the lead model only.
        assert apply_wounds(0, 0, 5, 2, 1) == (0, 1)

    def test_damage_carries_into_the_next_model(self):
        # 3 damage against 2-wound models kills one and wounds the next.
        assert apply_wounds(0, 0, 5, 2, 3) == (1, 1)

    def test_exact_model_kill_leaves_no_partial_wounds(self):
        assert apply_wounds(0, 0, 5, 2, 4) == (2, 0)

    def test_single_wound_models(self):
        assert apply_wounds(0, 0, 10, 1, 4) == (4, 0)

    def test_accumulates_from_existing_damage(self):
        assert apply_wounds(1, 1, 5, 2, 1) == (2, 0)

    def test_clamped_at_wiped_out(self):
        assert apply_wounds(0, 0, 3, 2, 99) == (3, 0)

    def test_healing_reverses_damage(self):
        assert apply_wounds(2, 1, 5, 2, -3) == (1, 0)

    def test_healing_clamped_at_undamaged(self):
        assert apply_wounds(1, 0, 5, 2, -99) == (0, 0)

    def test_rejects_impossible_profile(self):
        with pytest.raises(ValueError):
            apply_wounds(0, 0, 0, 2, 1)


class TestStrength:
    def test_models_remaining(self):
        assert models_remaining(3, 10) == 7
        assert models_remaining(12, 10) == 0  # never negative

    def test_destroyed(self):
        assert is_destroyed(10, 10) is True
        assert is_destroyed(9, 10) is False


class TestBelowHalfStrength:
    def test_multi_model_exactly_half_is_not_below(self):
        # 5 of 10 models remaining: half, not FEWER than half.
        assert is_below_half_strength(5, 0, 10, 2) is False

    def test_multi_model_one_fewer_is_below(self):
        assert is_below_half_strength(6, 0, 10, 2) is True

    def test_multi_model_odd_size(self):
        assert is_below_half_strength(2, 0, 5, 1) is False  # 3 of 5 remain
        assert is_below_half_strength(3, 0, 5, 1) is True   # 2 of 5 remain

    def test_undamaged_unit_is_not_below(self):
        assert is_below_half_strength(0, 0, 10, 2) is False

    def test_single_model_half_wounds_lost_is_below(self):
        # A 6-wound character that has lost 3 IS below half strength.
        assert is_below_half_strength(0, 3, 1, 6) is True

    def test_single_model_fewer_than_half_wounds_lost_is_not(self):
        assert is_below_half_strength(0, 2, 1, 6) is False

    def test_single_model_odd_wounds(self):
        assert is_below_half_strength(0, 2, 1, 5) is False  # lost 2 of 5
        assert is_below_half_strength(0, 3, 1, 5) is True   # lost 3 of 5

    def test_destroyed_unit_counts_as_below(self):
        assert is_below_half_strength(1, 0, 1, 6) is True
        assert is_below_half_strength(10, 0, 10, 1) is True


class TestBattleShock:
    def test_equal_to_leadership_passes(self):
        # Leadership 6+ passes on exactly 6.
        assert passes_battle_shock(6, 6) is True

    def test_below_leadership_fails(self):
        assert passes_battle_shock(5, 6) is False

    def test_above_leadership_passes(self):
        assert passes_battle_shock(12, 7) is True

    def test_worst_roll_fails_typical_leadership(self):
        assert passes_battle_shock(2, 6) is False
