"""Pure combat math for Warhammer 40k 10th edition, expected-value based.

No database or framework imports here: everything takes plain values and
returns plain dicts, so it is trivially unit-testable.

Attack sequence:
  attacks -> hit roll -> wound roll -> saving throw -> damage -> models slain

Supported weapon keywords: SUSTAINED HITS X, LETHAL HITS.
Unsupported keywords are ignored and reported in the result notes.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SUPPORTED_KEYWORDS = ("SUSTAINED HITS", "LETHAL HITS", "TORRENT")


def parse_dice_notation(notation: str) -> tuple[int, int, int, int]:
    """Break dice notation into (dice_count, sides, bonus, flat).

    '3' -> (0, 0, 0, 3); 'D6' -> (1, 6, 0, 0); '2D6+1' -> (2, 6, 1, 0).
    A dice_count of 0 means there is nothing to roll, just the flat value.
    Shared by the expected-value path and the rolled path so there is exactly
    one parser for the format.
    """
    text = notation.strip().upper().replace(" ", "")
    if not text:
        raise ValueError("Empty dice notation")

    match = re.fullmatch(r"(?:(\d*)D(\d+))?(?:\+(\d+))?(\d+)?", text)
    if not match or (match.group(2) is None and match.group(4) is None):
        raise ValueError(f"Bad dice notation: {notation!r}")
    count_s, sides_s, bonus_s, flat_s = match.groups()

    if sides_s is not None:
        count = int(count_s) if count_s else 1
        sides = int(sides_s)
        if count < 1 or sides < 2:
            raise ValueError(f"Bad dice notation: {notation!r}")
        if flat_s:  # e.g. 'D63' would parse as sides=63; trailing digits are invalid
            raise ValueError(f"Bad dice notation: {notation!r}")
        return count, sides, int(bonus_s) if bonus_s else 0, 0

    if bonus_s:
        raise ValueError(f"Bad dice notation: {notation!r}")
    return 0, 0, 0, int(flat_s)


def parse_dice(notation: str) -> float:
    """Average value of dice notation: '3', 'D6', '2D6', 'D3+1', '2D6+2'."""
    count, sides, bonus, flat = parse_dice_notation(notation)
    if count == 0:
        return float(flat)
    return count * (sides + 1) / 2 + bonus


def roll_needed_to_wound(strength: int, toughness: int) -> int:
    """10th-edition wound chart. Returns the D6 result needed (2..6)."""
    if strength >= 2 * toughness:
        return 2
    if strength > toughness:
        return 3
    if strength == toughness:
        return 4
    if strength * 2 <= toughness:
        return 6
    return 5


def probability(needed: int) -> float:
    """P(D6 >= needed). A 1 always fails, a 6 always succeeds."""
    needed = max(2, min(needed, 7))
    return (7 - needed) / 6


@dataclass
class AttackerProfile:
    weapon_name: str
    attacks: str          # dice notation
    skill: int            # BS/WS: 3 means 3+
    strength: int
    ap: int               # positive: 2 means AP-2
    damage: str           # dice notation
    keywords: list[str] = field(default_factory=list)
    model_count: int = 1  # each model fires/swings the weapon


@dataclass
class DefenderProfile:
    unit_name: str
    toughness: int
    save: int
    invuln_save: int | None
    wounds: int           # per model
    model_count: int


def parse_keywords(keywords: list[str]) -> tuple[int, bool, bool, list[str]]:
    """Return (sustained_hits_x, lethal_hits, torrent, unsupported)."""
    sustained = 0
    lethal = False
    torrent = False
    unsupported: list[str] = []
    for raw in keywords:
        kw = raw.strip().upper()
        if not kw:
            continue
        if kw.startswith("SUSTAINED HITS"):
            tail = kw.removeprefix("SUSTAINED HITS").strip()
            try:
                sustained = int(parse_dice(tail)) if tail else 1
            except ValueError:
                sustained = 1
        elif kw == "LETHAL HITS":
            lethal = True
        elif kw == "TORRENT":
            torrent = True
        else:
            unsupported.append(raw.strip())
    return sustained, lethal, torrent, unsupported


# --- Which weapons may fire together (Shooting phase) ----------------------

# A model shoots EITHER its pistols OR all its other ranged weapons, never both.
# Monsters and Vehicles ignore that restriction and fire everything.
PISTOL_KEYWORD = "PISTOL"
IGNORES_PISTOL_RESTRICTION = ("MONSTER", "VEHICLE")


def _upper(keywords: list[str]) -> set[str]:
    return {k.strip().upper() for k in keywords if k.strip()}


def is_pistol(weapon_keywords: list[str]) -> bool:
    return PISTOL_KEYWORD in _upper(weapon_keywords)


def ignores_pistol_restriction(unit_keywords: list[str]) -> bool:
    """MONSTER and VEHICLE models may fire pistols alongside everything else."""
    return bool(_upper(unit_keywords) & set(IGNORES_PISTOL_RESTRICTION))


def weapon_selection_error(
    unit_keywords: list[str], selected: list[tuple[str, str, list[str]]]
) -> str | None:
    """Validate a set of weapons chosen to shoot with.

    `selected` is (name, kind, keywords) per weapon. Returns an error message,
    or None when the selection is legal.
    """
    if not selected:
        return "Select at least one weapon to shoot with"

    melee = [name for name, kind, _ in selected if kind != "ranged"]
    if melee:
        return f"{melee[0]} is a melee weapon and cannot be fired in the Shooting phase"

    if ignores_pistol_restriction(unit_keywords):
        return None

    pistols = [name for name, _, kws in selected if is_pistol(kws)]
    others = [name for name, _, kws in selected if not is_pistol(kws)]
    if pistols and others:
        return (
            f"A model must shoot either its pistols or its other weapons, not both: "
            f"{pistols[0]} is a Pistol but {others[0]} is not. "
            "Only Monsters and Vehicles may combine them."
        )
    return None


def resolve_attack(attacker: AttackerProfile, defender: DefenderProfile) -> dict:
    """Full expected-value resolution. Returns a step-by-step breakdown."""
    notes: list[str] = []
    sustained, lethal, torrent, unsupported = parse_keywords(attacker.keywords)
    for kw in unsupported:
        notes.append(f"Keyword '{kw}' is not supported yet and was ignored.")

    # 1. Attacks
    attacks = parse_dice(attacker.attacks) * max(1, attacker.model_count)

    # 2. Hit roll (crit = unmodified 6, always 1/6 of attacks).
    # TORRENT weapons hit automatically: no hit roll, so no crits and no
    # crit-triggered keywords.
    if torrent:
        p_hit = 1.0
        crit_hits = 0.0
        normal_hits = attacks
        notes.append("TORRENT: attacks hit automatically; the hit skill is ignored.")
        if sustained or lethal:
            notes.append("SUSTAINED/LETHAL HITS need a hit roll, so TORRENT disables them.")
            sustained, lethal = 0, False
    else:
        p_hit = probability(attacker.skill)
        crit_hits = attacks * (1 / 6)
        normal_hits = attacks * max(0.0, p_hit - 1 / 6)
    extra_hits = crit_hits * sustained  # SUSTAINED HITS: extra normal hits on crits
    total_hits = normal_hits + crit_hits + extra_hits
    if sustained:
        notes.append(f"SUSTAINED HITS {sustained}: +{extra_hits:.2f} expected hits from 6s.")

    # 3. Wound roll (LETHAL HITS: crit hits wound automatically)
    needed_wound = roll_needed_to_wound(attacker.strength, defender.toughness)
    p_wound = probability(needed_wound)
    if lethal:
        auto_wounds = crit_hits
        rolled_wounds = (normal_hits + extra_hits) * p_wound
        notes.append(f"LETHAL HITS: {auto_wounds:.2f} expected auto-wounds from 6s to hit.")
    else:
        auto_wounds = 0.0
        rolled_wounds = total_hits * p_wound
    total_wounds = rolled_wounds + auto_wounds

    # 4. Saving throw (AP worsens armour save; invuln is never modified)
    modified_save = defender.save + attacker.ap
    best_save = modified_save
    used_invuln = False
    if defender.invuln_save is not None and defender.invuln_save < modified_save:
        best_save = defender.invuln_save
        used_invuln = True
    p_save = probability(best_save) if best_save <= 6 else 0.0
    failed_saves = total_wounds * (1 - p_save)
    save_detail = f"invulnerable {best_save}+" if used_invuln else (
        f"no save possible" if best_save > 6 else f"save {best_save}+ after AP"
    )

    # 5. Damage & models slain (damage does not spill over between models)
    avg_damage = parse_dice(attacker.damage)
    effective_damage = min(avg_damage, defender.wounds)
    if effective_damage < avg_damage:
        notes.append(
            f"Damage capped at {defender.wounds} per failed save "
            "(excess damage does not spill over)."
        )
    total_damage = failed_saves * avg_damage
    models_slain = min(
        defender.model_count, failed_saves * effective_damage / defender.wounds
    )

    steps = [
        {"label": "Attacks", "value": round(attacks, 2),
         "detail": f"{attacker.attacks} per model x {max(1, attacker.model_count)} model(s)"},
        {"label": "Hits", "value": round(total_hits, 2),
         "detail": "auto-hit (TORRENT)" if torrent
         else f"hitting on {attacker.skill}+ ({p_hit * 6:.0f}/6 per die)"},
        {"label": "Wounds", "value": round(total_wounds, 2),
         "detail": f"S{attacker.strength} vs T{defender.toughness}: wounding on {needed_wound}+"},
        {"label": "Failed saves", "value": round(failed_saves, 2),
         "detail": save_detail},
        {"label": "Damage", "value": round(total_damage, 2),
         "detail": f"{attacker.damage} damage per failed save"},
        {"label": "Models slain", "value": round(models_slain, 2),
         "detail": f"defender has {defender.wounds} wound(s) per model"},
    ]

    return {
        "weapon": attacker.weapon_name,
        "defender": defender.unit_name,
        "steps": steps,
        "expected_damage": round(total_damage, 2),
        "expected_models_slain": round(models_slain, 2),
        "notes": notes,
    }
