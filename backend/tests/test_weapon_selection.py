"""Which weapons may fire together in the Shooting phase.

Rule: a model fires all its non-pistol ranged weapons simultaneously, but must
choose EITHER its pistols OR its other weapons. Monsters and Vehicles ignore
that restriction.
"""
from app.services.combat import (
    ignores_pistol_restriction,
    is_pistol,
    weapon_selection_error,
)

RIFLE = ("Bolt rifle", "ranged", ["Assault", "Heavy"])
PLASMA = ("Plasma gun", "ranged", ["Hazardous"])
PISTOL = ("Bolt pistol", "ranged", ["Pistol"])
HAND_FLAMER = ("Hand flamer", "ranged", ["Ignores Cover", "Pistol", "Torrent"])
CHAINSWORD = ("Astartes chainsword", "melee", [])

INFANTRY = ["Infantry", "Battleline", "Imperium"]
VEHICLE = ["Vehicle", "Imperium", "Transport"]
MONSTER = ["Monster", "Tyranids"]


class TestKeywordHelpers:
    def test_detects_pistol_case_insensitively(self):
        assert is_pistol(["Pistol"]) is True
        assert is_pistol(["PISTOL"]) is True
        assert is_pistol(["Ignores Cover", "Pistol", "Torrent"]) is True
        assert is_pistol(["Assault", "Heavy"]) is False
        assert is_pistol([]) is False

    def test_monsters_and_vehicles_ignore_the_restriction(self):
        assert ignores_pistol_restriction(VEHICLE) is True
        assert ignores_pistol_restriction(MONSTER) is True
        assert ignores_pistol_restriction(INFANTRY) is False
        assert ignores_pistol_restriction([]) is False


class TestSelection:
    def test_several_non_pistol_weapons_fire_together(self):
        assert weapon_selection_error(INFANTRY, [RIFLE, PLASMA]) is None

    def test_several_pistols_fire_together(self):
        assert weapon_selection_error(INFANTRY, [PISTOL, HAND_FLAMER]) is None

    def test_mixing_pistols_with_other_weapons_is_rejected(self):
        error = weapon_selection_error(INFANTRY, [RIFLE, PISTOL])
        assert error is not None
        assert "either its pistols" in error

    def test_vehicles_may_mix_pistols_with_everything(self):
        assert weapon_selection_error(VEHICLE, [RIFLE, PISTOL]) is None

    def test_monsters_may_mix_pistols_with_everything(self):
        assert weapon_selection_error(MONSTER, [RIFLE, PISTOL]) is None

    def test_melee_weapons_cannot_be_fired(self):
        error = weapon_selection_error(INFANTRY, [RIFLE, CHAINSWORD])
        assert error is not None
        assert "melee" in error

    def test_melee_is_rejected_even_for_a_vehicle(self):
        assert weapon_selection_error(VEHICLE, [CHAINSWORD]) is not None

    def test_empty_selection_is_rejected(self):
        assert weapon_selection_error(INFANTRY, []) is not None
