"""Tests for the OpenHammer -> QuickHammer mapping (pure functions)."""
from app.services.library import map_unit, map_weapon

# Trimmed real payload from GET /v1/10e/units?name=intercessor
INTERCESSOR = {
    "name": "Intercessor Squad",
    "id": "8da0-4570-c3c-819f",
    "faction": "Space Marines",
    "points": {"base": 80, "variants": []},
    "composition": {"min_models": 5, "max_models": 10},
    "stats": {"M": '6"', "T": "4", "SV": "3+", "W": "2", "LD": "6+", "OC": "2"},
    "invuln_save": None,
    "weapons": {
        "ranged": [
            {"name": "Bolt Rifle", "Range": '24"', "A": "2", "BS": "3+", "WS": None,
             "S": "4", "AP": "-1", "D": "1", "Keywords": "Assault, Heavy"},
            {"name": "Hand flamer", "Range": '12"', "A": "D6", "BS": "N/A", "WS": None,
             "S": "3", "AP": "0", "D": "1", "Keywords": "Ignores Cover, Pistol, Torrent"},
            {"name": "➤ Plasma pistol - supercharge", "Range": '12"', "A": "1",
             "BS": "3+", "WS": None, "S": "8", "AP": "-3", "D": "2", "Keywords": "Hazardous, Pistol"},
        ],
        "melee": [
            {"name": "Power fist", "Range": "Melee", "A": "3", "BS": None, "WS": "3+",
             "S": "8", "AP": "-2", "D": "2", "Keywords": "-"},
        ],
    },
}

FLAMERS = {
    "name": "Flamers",
    "stats": {"M": '9"', "T": "4", "SV": "7+", "W": "3", "LD": "7+", "OC": "1"},
    "invuln_save": "4+",
    "composition": {"min_models": 1, "max_models": 1},
    "weapons": {"ranged": [], "melee": []},
}


class TestMapUnit:
    def test_faction_and_points(self):
        unit = map_unit(INTERCESSOR)
        assert unit.faction == "Space Marines"
        assert unit.points == 80

    def test_datasheet_keywords_are_imported(self):
        """Needed for the Pistol rule: MONSTER and VEHICLE ignore it."""
        unit = map_unit({**INTERCESSOR, "keywords": ["Infantry", "Battleline", "Imperium"]})
        assert unit.keywords == ["Infantry", "Battleline", "Imperium"]

    def test_vehicle_keyword_survives_import(self):
        unit = map_unit({**INTERCESSOR, "keywords": ["Vehicle", "Transport"]})
        assert "Vehicle" in unit.keywords

    def test_missing_keywords_default_to_empty(self):
        assert map_unit(INTERCESSOR).keywords == []

    def test_missing_faction_and_points_default(self):
        unit = map_unit({"name": "Mystery"})
        assert unit.faction == ""
        assert unit.points == 0

    def test_statline(self):
        unit = map_unit(INTERCESSOR)
        assert unit.name == "Intercessor Squad"
        assert unit.movement == 6
        assert unit.toughness == 4
        assert unit.save == 3
        assert unit.invuln_save is None
        assert unit.wounds == 2
        assert unit.leadership == 6
        assert unit.oc == 2
        assert unit.model_count == 5  # min_models

    def test_invuln_and_no_save(self):
        unit = map_unit(FLAMERS)
        assert unit.invuln_save == 4
        assert unit.save == 7

    def test_all_weapons_included(self):
        unit = map_unit(INTERCESSOR)
        assert len(unit.weapons) == 4
        kinds = {w.name: w.kind for w in unit.weapons}
        assert kinds["Power fist"] == "melee"
        assert kinds["Bolt Rifle"] == "ranged"

    def test_titan_stats_are_clamped(self):
        unit = map_unit({
            "name": "Warlord Titan",
            "stats": {"M": '10"', "T": "18", "SV": "2+", "W": "70", "LD": "6+", "OC": "12"},
            "composition": {"min_models": 1, "max_models": 1},
            "weapons": {},
        })
        assert unit.toughness == 16
        assert unit.wounds == 40
        assert unit.oc == 10

    def test_missing_fields_get_defaults(self):
        unit = map_unit({"name": "Mystery"})
        assert unit.model_count == 1
        assert unit.weapons == []


class TestMapWeapon:
    def test_negative_ap_string_to_positive_int(self):
        weapon = map_weapon(INTERCESSOR["weapons"]["ranged"][2])
        assert weapon.ap == 3

    def test_torrent_weapon_keeps_keyword_and_gets_placeholder_skill(self):
        weapon = map_weapon(INTERCESSOR["weapons"]["ranged"][1])
        assert "Torrent" in weapon.keywords
        assert 2 <= weapon.skill <= 6  # placeholder; the math ignores it

    def test_melee_weapon(self):
        weapon = map_weapon(INTERCESSOR["weapons"]["melee"][0])
        assert weapon.kind == "melee"
        assert weapon.range == 0
        assert weapon.skill == 3

    def test_decorative_prefix_stripped(self):
        weapon = map_weapon(INTERCESSOR["weapons"]["ranged"][2])
        assert weapon.name == "Plasma pistol - supercharge"

    def test_dash_keywords_mean_none(self):
        weapon = map_weapon(INTERCESSOR["weapons"]["melee"][0])
        assert weapon.keywords == []

    def test_bad_dice_notation_falls_back(self):
        weapon = map_weapon({"name": "Weird gun", "Range": '12"', "A": "D6+D3",
                             "BS": "4+", "S": "5", "AP": "-1", "D": "1"})
        assert weapon.attacks == "1"
