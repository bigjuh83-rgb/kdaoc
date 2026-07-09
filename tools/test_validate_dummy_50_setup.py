#!/usr/bin/env python3
"""Unit checks for dummy level-50 setup validation."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("validate-dummy-50-setup.py")
    spec = importlib.util.spec_from_file_location("validate_dummy_50_setup_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


validator = load_module()


def valid_character() -> dict[str, str]:
    return {
        "owner_id": "char-id",
        "account": "albtest001",
        "name": "Albtest001",
        "realm": "1",
        "class": "1",
        "level": "50",
        "specs": "Slash|39;Chants|48;Shields|42",
        "abilities": "Sprint|0;Shield|3;AlbArmor|5;Weaponry: Slashing|0",
    }


def valid_equipment() -> dict[str, dict[int, dict[str, str]]]:
    profile = validator.equip.CLASS_PROFILES[1]
    slots = validator.expected_slots(profile)
    return {
        "char-id": {
            slot: {
                "template_id": f"slot_{slot}",
                "object_type": str(object_type),
                "item_type": str(slot),
                "dps_af": "165" if kind in {"weapon", "shield"} else "102",
                "quality": "100",
            }
            for slot, (object_type, kind) in slots.items()
        }
    }


class ValidateDummy50SetupTests(unittest.TestCase):
    def test_valid_level_50_character_with_gear_passes(self) -> None:
        failures = validator.validate_db_setup([valid_character()], valid_equipment())

        self.assertEqual(failures, [])

    def test_invalid_weapon_object_type_is_rejected(self) -> None:
        equipment = valid_equipment()
        equipment["char-id"][10]["object_type"] = "0"

        failures = validator.validate_db_setup([valid_character()], equipment)

        self.assertTrue(any("Object_Type=0" in failure for failure in failures))

    def test_missing_specs_and_abilities_are_rejected(self) -> None:
        character = valid_character()
        character["specs"] = ""
        character["abilities"] = ""

        failures = validator.validate_db_setup([character], valid_equipment())

        self.assertTrue(any("SerializedSpecs" in failure for failure in failures))
        self.assertTrue(any("SerializedAbilities" in failure for failure in failures))

    def test_speed_song_profile_requires_instrument_slot_without_weapon_dps_threshold(self) -> None:
        character = valid_character()
        character.update(
            {
                "account": "albtest012",
                "class": "4",
                "specs": "Instruments|44;Slash|39;Stealth|25",
            }
        )
        profile = validator.equip.CLASS_PROFILES[4]
        equipment = {
            "char-id": {
                slot: {
                    "template_id": f"slot_{slot}",
                    "object_type": str(object_type),
                    "item_type": str(slot),
                    "dps_af": "2" if kind == "instrument" else "165" if kind == "weapon" else "102",
                    "quality": "100",
                }
                for slot, (object_type, kind) in validator.expected_slots(profile).items()
            }
        }

        failures = validator.validate_db_setup([character], equipment)

        self.assertEqual(failures, [])
        self.assertEqual(validator.expected_slots(profile)[13], (45, "instrument"))


if __name__ == "__main__":
    raise SystemExit(unittest.main())
