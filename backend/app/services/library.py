"""Mapping from the OpenHammer API's unit JSON to QuickHammer's schemas.

OpenHammer (https://openhammer-api-production.up.railway.app) serves 40k
datasheets with string-typed stats: M '6"', SV '3+', AP '-1', Range 'Melee',
BS 'N/A' for Torrent weapons, Keywords '-' for none. These pure functions
normalize all of that into our UnitIn/WeaponIn shape, clamping values to our
schema bounds so an exotic datasheet (a Titan, say) still imports.
"""
from __future__ import annotations

import re
from typing import Any

from ..schemas import UnitIn, WeaponIn
from .combat import parse_dice


def _int_from(text: object, default: int) -> int:
    """Extract the leading integer from strings like '6\"', '3+', '-1', 'N/A'."""
    match = re.search(r"-?\d+", str(text or ""))
    return int(match.group()) if match else default


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _clean_name(name: str) -> str:
    """Drop decorative prefixes like '➤ ' that mark wargear options."""
    return re.sub(r"^[^0-9A-Za-z]+", "", name).strip() or name.strip()


def _dice_or(raw: object, default: str) -> str:
    """Pass through valid dice notation; fall back rather than fail an import."""
    text = str(raw or "").strip().upper()
    try:
        parse_dice(text)
        return text
    except ValueError:
        return default


def _split_keywords(raw: object) -> list[str]:
    text = str(raw or "").strip()
    if not text or text == "-":
        return []
    return [k.strip() for k in text.split(",") if k.strip()]


def map_weapon(data: dict[str, Any]) -> WeaponIn:
    is_melee = str(data.get("Range", "")).strip().lower() == "melee"
    skill_raw = data.get("WS") if is_melee else data.get("BS")
    return WeaponIn(
        name=_clean_name(str(data.get("name", "Unknown weapon")))[:100],
        kind="melee" if is_melee else "ranged",
        range=0 if is_melee else _clamp(_int_from(data.get("Range"), 24), 0, 120),
        attacks=_dice_or(data.get("A"), "1"),
        # 'N/A' (Torrent weapons auto-hit): the skill is unused by the math.
        skill=_clamp(_int_from(skill_raw, 4), 2, 6),
        strength=_clamp(_int_from(data.get("S"), 4), 1, 24),
        ap=_clamp(abs(_int_from(data.get("AP"), 0)), 0, 6),
        damage=_dice_or(data.get("D"), "1"),
        keywords=_split_keywords(data.get("Keywords")),
    )


def map_unit(data: dict[str, Any]) -> UnitIn:
    stats = data.get("stats") or {}
    composition = data.get("composition") or {}
    weapons_by_kind = data.get("weapons") or {}
    weapons = [
        map_weapon(w)
        for w in (weapons_by_kind.get("ranged") or []) + (weapons_by_kind.get("melee") or [])
    ]

    invuln_raw = data.get("invuln_save")
    invuln = _clamp(_int_from(invuln_raw, 4), 2, 6) if invuln_raw else None

    points = data.get("points") or {}

    return UnitIn(
        name=str(data.get("name", "Imported unit")).strip()[:100],
        faction=str(data.get("faction") or "").strip()[:100],
        points=_clamp(_int_from(points.get("base"), 0), 0, 10000),
        movement=_clamp(_int_from(stats.get("M"), 6), 0, 30),
        toughness=_clamp(_int_from(stats.get("T"), 4), 1, 16),
        save=_clamp(_int_from(stats.get("SV"), 3), 2, 7),
        invuln_save=invuln,
        wounds=_clamp(_int_from(stats.get("W"), 1), 1, 40),
        leadership=_clamp(_int_from(stats.get("LD"), 6), 4, 10),
        oc=_clamp(_int_from(stats.get("OC"), 1), 0, 10),
        model_count=_clamp(_int_from(composition.get("min_models"), 1), 1, 30),
        weapons=weapons,
    )
