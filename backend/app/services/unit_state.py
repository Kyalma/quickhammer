"""Live unit state and Battle-shock rules (Warhammer 40k 10th edition).

Pure functions with no framework or DB imports, like services/combat.py.

A unit's condition is stored as LOSSES rather than remainders (`models_lost`,
`wounds_lost`), so zero always means undamaged. `wounds_lost` is damage on the
current lead model only and is always less than the unit's wounds characteristic.
"""
from __future__ import annotations


def total_wounds_lost(models_lost: int, wounds_lost: int, wounds: int) -> int:
    return models_lost * wounds + wounds_lost


def apply_wounds(
    models_lost: int,
    wounds_lost: int,
    model_count: int,
    wounds: int,
    delta: int,
) -> tuple[int, int]:
    """Apply `delta` wounds to a unit and return the new (models_lost, wounds_lost).

    Damage accumulates through the unit one model at a time, so 3 damage against
    2-wound models kills one model and leaves the next on 1 wound lost. A
    negative delta heals, which doubles as an undo for a mis-tap. The result is
    clamped between undamaged and wiped out.
    """
    if model_count < 1 or wounds < 1:
        raise ValueError("A unit needs at least one model and one wound")

    capacity = model_count * wounds
    total = total_wounds_lost(models_lost, wounds_lost, wounds) + delta
    total = max(0, min(capacity, total))
    return total // wounds, total % wounds


def models_remaining(models_lost: int, model_count: int) -> int:
    return max(0, model_count - models_lost)


def is_destroyed(models_lost: int, model_count: int) -> bool:
    return models_remaining(models_lost, model_count) <= 0


def is_below_half_strength(
    models_lost: int, wounds_lost: int, model_count: int, wounds: int
) -> bool:
    """Below Half-strength, which is what triggers a Battle-shock test.

    The two branches are deliberately asymmetric, per the core rules:

    * A single-model unit qualifies once it has lost HALF OR MORE of its wounds.
      A 6-wound character that has lost 3 is below half strength.
    * A multi-model unit qualifies once FEWER THAN HALF its models remain.
      5 of 10 models is NOT below half strength; 4 of 10 is.
    """
    if is_destroyed(models_lost, model_count):
        return True
    if model_count == 1:
        return wounds_lost * 2 >= wounds
    return models_remaining(models_lost, model_count) * 2 < model_count


def passes_battle_shock(roll: int, leadership: int) -> bool:
    """A Battle-shock test is a Leadership test: 2D6 equal to or over Ld passes.

    Leadership is stored as the number needed, so 6 means "6+".
    """
    return roll >= leadership
