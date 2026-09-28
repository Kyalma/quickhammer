"""Rolled attack resolution for the Shooting phase (Warhammer 40k 10th edition).

Where services/combat.py computes expected values for a preview, this module
rolls real dice and reports every one, so a player sees Miss / Hit / Wounded /
Saved the way they would at the table.

Pure and framework-free. The RNG is injected, so tests seed it and assert exact
dice. Nothing here touches the database.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

from .combat import parse_dice_notation, parse_keywords, roll_needed_to_wound

# Outcome labels. These are shown verbatim in the UI.
MISS = "Miss"
HIT = "Hit"
CRITICAL_HIT = "Critical hit"
AUTO_HIT = "Auto-hit"
SUSTAINED_HIT = "Sustained hit"
WOUND_FAILED = "No wound"
WOUNDED = "Wounded"
CRITICAL_WOUND = "Critical wound"
AUTO_WOUND = "Auto-wound"
SAVED = "Saved"
SAVE_FAILED = "Save failed"
NO_SAVE = "No save possible"

CRIT_ROLL = 6


@dataclass
class WeaponProfile:
    """One weapon being fired, with how many models are firing it."""

    name: str
    attacks: str          # dice notation
    skill: int            # BS: 3 means 3+
    strength: int
    ap: int               # positive: 2 means AP-2
    damage: str           # dice notation
    keywords: list[str] = field(default_factory=list)
    carriers: int = 1     # models firing this weapon


@dataclass
class TargetProfile:
    name: str
    toughness: int
    save: int
    invuln_save: int | None
    wounds: int           # per model
    model_count: int
    # Current condition, so damage finishes off an already-wounded lead model.
    models_lost: int = 0
    wounds_lost: int = 0


def roll_dice(notation: str, rng: random.Random) -> tuple[int, list[int]]:
    """Roll dice notation. Returns (total, individual results).

    A flat value like '3' rolls nothing and returns (3, []).
    """
    count, sides, bonus, flat = parse_dice_notation(notation)
    if count == 0:
        return flat, []
    rolls = [rng.randint(1, sides) for _ in range(count)]
    return sum(rolls) + bonus, rolls


def best_save(save: int, invuln_save: int | None, ap: int) -> tuple[int, bool]:
    """The save actually used: armour worsened by AP, or a better invulnerable.

    Returns (target number, used_invuln). A number above 6 means no save.
    """
    modified = save + ap
    if invuln_save is not None and invuln_save < modified:
        return invuln_save, True
    return modified, False


def allocate_damage(
    target: TargetProfile, damage_values: list[int]
) -> tuple[int, int, list[str]]:
    """Apply each failed save's damage to the lead model in turn.

    Deliberately NOT unit_state.apply_wounds: that cascades a net wound total,
    which is right for manual tracking. Here each instance of damage hits one
    model and **excess damage is lost rather than spilling** into the next, which
    is the actual rule. Allocation stops once the unit is wiped out.

    Returns (models_lost, wounds_lost, per-instance descriptions).
    """
    models_lost = target.models_lost
    wounds_lost = target.wounds_lost
    notes: list[str] = []

    for value in damage_values:
        if models_lost >= target.model_count:
            notes.append(f"{value} damage wasted, unit already destroyed")
            continue
        remaining_on_lead = target.wounds - wounds_lost
        if value >= remaining_on_lead:
            models_lost += 1
            wounds_lost = 0
            spilled = value - remaining_on_lead
            if models_lost >= target.model_count:
                notes.append(f"{value} damage: model slain, unit destroyed")
            elif spilled > 0:
                notes.append(f"{value} damage: model slain, {spilled} excess lost")
            else:
                notes.append(f"{value} damage: model slain")
        else:
            wounds_lost += value
            notes.append(
                f"{value} damage: lead model on "
                f"{target.wounds - wounds_lost}/{target.wounds} wounds"
            )

    return models_lost, wounds_lost, notes


def _models_firing(weapon: WeaponProfile, attacker_models: int) -> int:
    """How many models fire this weapon.

    `carriers` of 0 means every model in the ATTACKING unit. Either way it is
    capped by how many of the attacker's models are still alive, never by
    anything about the target.
    """
    carriers = weapon.carriers if weapon.carriers > 0 else attacker_models
    return max(0, min(carriers, attacker_models))


def resolve_shooting(
    weapons: list[WeaponProfile],
    attacker_models: int,
    target: TargetProfile,
    rng: random.Random,
) -> dict:
    """Roll a whole shooting attack: several weapons into one target.

    `attacker_models` is how many models the ATTACKING unit has left. It decides
    how many times each weapon is fired. Nothing about the target may influence
    that: a lone character shooting a ten-model squad still fires once.

    Returns a structure with a stage list per weapon (each stage carrying its
    individual dice and their outcomes) plus the aggregate damage allocation.
    """
    weapon_results = []
    all_damage: list[int] = []
    notes: list[str] = []

    for weapon in weapons:
        sustained, lethal, torrent, unsupported = parse_keywords(weapon.keywords)
        for kw in unsupported:
            notes.append(f"{weapon.name}: keyword '{kw}' is not supported yet and was ignored.")

        firing = _models_firing(weapon, attacker_models)
        stages = []

        # --- Attacks -------------------------------------------------------
        attack_dice: list[dict] = []
        attacks = 0
        for _ in range(firing):
            total, rolls = roll_dice(weapon.attacks, rng)
            attacks += total
            for value in rolls:
                attack_dice.append({"value": value, "outcome": f"{value} attacks"})
        stages.append({
            "name": "Attacks",
            "dice": attack_dice,
            "summary": (
                f"{attacks} attacks from {firing} model{'' if firing == 1 else 's'}"
                f" ({weapon.attacks} each)"
            ),
        })

        # --- Hit rolls -----------------------------------------------------
        hit_dice: list[dict] = []
        normal_hits = 0
        crit_hits = 0
        if torrent:
            normal_hits = attacks
            notes.append(f"{weapon.name}: TORRENT, attacks hit automatically.")
            if sustained or lethal:
                notes.append(
                    f"{weapon.name}: SUSTAINED/LETHAL HITS need a hit roll, "
                    "so TORRENT disables them."
                )
                sustained, lethal = 0, False
            hit_summary = f"{attacks} automatic hits (TORRENT)"
            hit_dice = [{"value": 0, "outcome": AUTO_HIT} for _ in range(attacks)]
        else:
            for _ in range(attacks):
                value = rng.randint(1, 6)
                if value == CRIT_ROLL:
                    crit_hits += 1
                    hit_dice.append({"value": value, "outcome": CRITICAL_HIT})
                elif value >= weapon.skill and value > 1:
                    normal_hits += 1
                    hit_dice.append({"value": value, "outcome": HIT})
                else:
                    hit_dice.append({"value": value, "outcome": MISS})
            hit_summary = f"{normal_hits + crit_hits} hits on {weapon.skill}+"
            if crit_hits:
                hit_summary += f", {crit_hits} critical"

        extra_hits = crit_hits * sustained
        if extra_hits:
            hit_dice.extend(
                {"value": 0, "outcome": SUSTAINED_HIT} for _ in range(extra_hits)
            )
            hit_summary += f", +{extra_hits} from SUSTAINED HITS {sustained}"
        stages.append({"name": "Hit rolls", "dice": hit_dice, "summary": hit_summary})

        # --- Wound rolls ---------------------------------------------------
        # LETHAL HITS: critical hits wound automatically and roll no dice.
        needed = roll_needed_to_wound(weapon.strength, target.toughness)
        wound_dice: list[dict] = []
        wounds = 0
        auto_wounds = crit_hits if lethal else 0
        to_roll = normal_hits + extra_hits + (0 if lethal else crit_hits)

        for _ in range(auto_wounds):
            wound_dice.append({"value": 0, "outcome": AUTO_WOUND})
        wounds += auto_wounds

        for _ in range(to_roll):
            value = rng.randint(1, 6)
            if value == CRIT_ROLL:
                wounds += 1
                wound_dice.append({"value": value, "outcome": CRITICAL_WOUND})
            elif value >= needed and value > 1:
                wounds += 1
                wound_dice.append({"value": value, "outcome": WOUNDED})
            else:
                wound_dice.append({"value": value, "outcome": WOUND_FAILED})

        wound_summary = (
            f"{wounds} wounds, S{weapon.strength} vs T{target.toughness} needs {needed}+"
        )
        if auto_wounds:
            wound_summary += f" ({auto_wounds} automatic from LETHAL HITS)"
        stages.append({"name": "Wound rolls", "dice": wound_dice, "summary": wound_summary})

        # --- Saving throws -------------------------------------------------
        save_target, used_invuln = best_save(target.save, target.invuln_save, weapon.ap)
        save_dice: list[dict] = []
        failed_saves = 0
        if save_target > 6:
            failed_saves = wounds
            save_dice = [{"value": 0, "outcome": NO_SAVE} for _ in range(wounds)]
            save_summary = f"{wounds} unsaved, no save possible against AP-{weapon.ap}"
        else:
            for _ in range(wounds):
                value = rng.randint(1, 6)
                if value >= save_target and value > 1:
                    save_dice.append({"value": value, "outcome": SAVED})
                else:
                    failed_saves += 1
                    save_dice.append({"value": value, "outcome": SAVE_FAILED})
            kind = "invulnerable" if used_invuln else "armour"
            save_summary = (
                f"{failed_saves} failed of {wounds}, {kind} save {save_target}+"
            )
        stages.append({"name": "Saving throws", "dice": save_dice, "summary": save_summary})

        # --- Damage --------------------------------------------------------
        damage_dice: list[dict] = []
        weapon_damage: list[int] = []
        for _ in range(failed_saves):
            total, rolls = roll_dice(weapon.damage, rng)
            weapon_damage.append(total)
            if rolls:
                for value in rolls:
                    damage_dice.append({"value": value, "outcome": f"{total} damage"})
            else:
                damage_dice.append({"value": total, "outcome": f"{total} damage"})
        all_damage.extend(weapon_damage)
        stages.append({
            "name": "Damage",
            "dice": damage_dice,
            "summary": f"{sum(weapon_damage)} damage from {failed_saves} unsaved "
                       f"({weapon.damage} each)",
        })

        weapon_results.append({
            "weapon": weapon.name,
            "models_firing": firing,
            "stages": stages,
        })

    # --- Allocation across every weapon in order ---------------------------
    models_lost, wounds_lost, allocation = allocate_damage(target, all_damage)
    models_slain = models_lost - target.models_lost
    destroyed = models_lost >= target.model_count

    if destroyed:
        outcome = f"{target.name} is destroyed"
    elif models_slain:
        outcome = (
            f"{models_slain} model{'' if models_slain == 1 else 's'} slain, "
            f"{target.model_count - models_lost} left"
        )
    elif wounds_lost != target.wounds_lost:
        outcome = f"{target.name} wounded but no models slain"
    else:
        outcome = f"{target.name} is unharmed"

    return {
        "target": target.name,
        "weapons": weapon_results,
        "total_damage": sum(all_damage),
        "models_slain": models_slain,
        "destroyed": destroyed,
        "allocation": allocation,
        "outcome": outcome,
        "notes": notes,
        # What confirming this roll will write to the target.
        "result_models_lost": models_lost,
        "result_wounds_lost": wounds_lost,
    }
