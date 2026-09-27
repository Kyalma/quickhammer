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


def parse_dice(notation: str) -> float:
    """Average value of dice notation: '3', 'D6', '2D6', 'D3+1', '2D6+2'."""
    text = notation.strip().upper().replace(" ", "")
    if not text:
        raise ValueError("Empty dice notation")

    match = re.fullmatch(r"(?:(\d*)D(\d+))?(?:\+(\d+))?(\d+)?", text)
    if not match or (match.group(2) is None and match.group(4) is None):
        raise ValueError(f"Bad dice notation: {notation!r}")
    count_s, sides_s, bonus_s, flat_s = match.groups()

    total = 0.0
    if sides_s is not None:
        count = int(count_s) if count_s else 1
        sides = int(sides_s)
        if count < 1 or sides < 2:
            raise ValueError(f"Bad dice notation: {notation!r}")
        total += count * (sides + 1) / 2
        if bonus_s:
            total += int(bonus_s)
        if flat_s:  # e.g. "D63" would be sides=63; flat trailing digits invalid after dice
            raise ValueError(f"Bad dice notation: {notation!r}")
    else:
        if bonus_s:
            raise ValueError(f"Bad dice notation: {notation!r}")
        total += int(flat_s)
    return total


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
