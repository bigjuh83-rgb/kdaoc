#!/usr/bin/env python3
"""Unit checks for dummy account provisioning helpers."""

from __future__ import annotations

import importlib.util
import csv
import re
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def load_module():
    module_path = Path(__file__).with_name("provision-dummy-accounts.py")
    spec = importlib.util.spec_from_file_location("provision_dummy_accounts_for_tests", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


provision = load_module()


class ProvisionDummyAccountsTests(unittest.TestCase):
    def test_parse_starter_classes_accepts_semicolon_and_comma(self):
        self.assertEqual(provision.parse_class_list("14;2;1;11;19;"), {1, 2, 11, 14, 19})
        self.assertEqual(provision.parse_class_list("14, 2, bad, 19"), {2, 14, 19})

    def test_left_hand_weapon_can_seed_right_hand_when_empty(self):
        used_slots: set[int] = set()

        slot = provision.choose_starter_slot(
            provision.LEFT_HAND_SLOT,
            object_type=3,
            used_slots=used_slots,
        )

        self.assertEqual(slot, provision.RIGHT_HAND_SLOT)
        self.assertIn(provision.RIGHT_HAND_SLOT, used_slots)

    def test_shield_stays_left_hand(self):
        used_slots: set[int] = set()

        slot = provision.choose_starter_slot(
            provision.LEFT_HAND_SLOT,
            object_type=provision.SHIELD_OBJECT_TYPE,
            used_slots=used_slots,
        )

        self.assertEqual(slot, provision.LEFT_HAND_SLOT)

    def test_duplicate_equipment_slot_falls_back_to_backpack(self):
        used_slots = {provision.RIGHT_HAND_SLOT}

        slot = provision.choose_starter_slot(
            provision.RIGHT_HAND_SLOT,
            object_type=3,
            used_slots=used_slots,
        )

        self.assertEqual(slot, provision.FIRST_BACKPACK_SLOT)

    def test_existing_partial_inventory_gets_missing_starter_slots_only(self):
        def template(template_id, item_type, object_type):
            return {
                "TemplateID": template_id,
                "Item_Type": str(item_type),
                "Object_Type": str(object_type),
                "PackSize": "1",
                "Color": "0",
                "Emblem": "0",
                "Extension": "0",
                "SalvageExtension": "",
                "MaxCondition": "100",
                "MaxDurability": "100",
                "Charges": "0",
                "MaxCharges": "0",
                "Charges1": "0",
                "MaxCharges1": "0",
                "PoisonSpellID": "0",
                "PoisonMaxCharges": "0",
                "PoisonCharges": "0",
            }

        args = SimpleNamespace()
        character = {
            "DOLCharacters_ID": "char-hib",
            "Class": "44",
            "SerializedSpecs": "Blades|50;Shields|42",
        }
        templates = [
            template("training_sword_hib", provision.LEFT_HAND_SLOT, 19),
            template("training_shield", provision.LEFT_HAND_SLOT, provision.SHIELD_OBJECT_TYPE),
            template("leaf_tacuil_helm3", 21, 37),
            template("leaf_tacuil_vest3", 25, 37),
        ]

        with (
            patch.object(provision, "get_single_row", return_value=character),
            patch.object(provision, "starter_templates_for_specs", return_value=templates),
            patch.object(
                provision,
                "inventory_slot_positions",
                return_value={provision.RIGHT_HAND_SLOT, provision.LEFT_HAND_SLOT},
            ),
            patch.object(provision, "run_mysql") as run_mysql,
        ):
            inserted = provision.add_starter_equipment(args, "growthhib741", "GrowthHib741")

        self.assertEqual(inserted, 2)
        combined_sql = "\n".join(call.args[1] for call in run_mysql.call_args_list)
        self.assertIn("leaf_tacuil_helm3", combined_sql)
        self.assertIn("leaf_tacuil_vest3", combined_sql)
        self.assertNotIn("training_sword_hib", combined_sql)
        self.assertNotIn("training_shield", combined_sql)

    def test_character_insert_can_override_start_location(self):
        args = SimpleNamespace(
            start_x=523520,
            start_y=490520,
            start_z=2543,
            start_region=1,
            position_step=20,
            template_account="bigjuh",
            template_character="천재다",
            class_cycle_values=[],
            race_cycle_values=[],
            creation_model_cycle_values=[],
            current_model_cycle_values=[],
            spec_cycle_values=[],
            ability_cycle_values=[],
            level_values=[],
            randomize_race=False,
            randomize_stats=False,
            random_seed="",
        )

        with patch.object(
            provision,
            "get_columns",
            return_value=[
                "AccountName",
                "Name",
                "DOLCharacters_ID",
                "Xpos",
                "Ypos",
                "Zpos",
                "Region",
                "BindXpos",
                "BindYpos",
                "BindZpos",
                "BindRegion",
            ],
        ):
            sql = provision.build_character_insert(args, "dummy001", "Dummy001", 100, 2)

        self.assertIn("523560 AS `Xpos`", sql)
        self.assertIn("490560 AS `Ypos`", sql)
        self.assertIn("2543 AS `Zpos`", sql)
        self.assertIn("1 AS `Region`", sql)
        self.assertIn("523560 AS `BindXpos`", sql)
        self.assertIn("490560 AS `BindYpos`", sql)
        self.assertIn("2543 AS `BindZpos`", sql)
        self.assertIn("1 AS `BindRegion`", sql)

    def test_accounts_csv_includes_start_location_for_client_fallback(self):
        rows = [
            {
                "username": "growthalb741",
                "password": "dummy-pass",
                "realm": 1,
                "char_index": 0,
                "class_id": 1,
                "class_name": "Paladin",
                "specs": "Slash|39",
                "start_x": 534900,
                "start_y": 477500,
                "start_z": 2200,
                "zone_id": 1,
            },
            {
                "username": "growthalb742",
                "password": "dummy-pass",
                "realm": 1,
                "char_index": 0,
                "class_id": 6,
                "class_name": "Cleric",
                "specs": "Rejuvenation|40",
                "start_x": 534980,
                "start_y": 477580,
                "start_z": 2200,
                "zone_id": 1,
            },
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "accounts.csv"
            provision.write_accounts_csv(path, rows)
            with path.open(encoding="utf-8", newline="") as handle:
                written = list(csv.DictReader(handle))

        self.assertEqual(written[0]["start_x"], "534900")
        self.assertEqual(written[1]["start_y"], "477580")
        self.assertEqual(written[1]["start_z"], "2200")
        self.assertEqual(written[1]["zone_id"], "1")

    def test_character_insert_can_randomize_race_from_cycle_deterministically(self):
        args = SimpleNamespace(
            start_x=None,
            start_y=None,
            start_z=None,
            start_region=None,
            position_step=20,
            template_account="bigjuh",
            template_character="천재다",
            class_cycle_values=[],
            race_cycle_values=["1", "3", "4"],
            creation_model_cycle_values=[],
            current_model_cycle_values=[],
            spec_cycle_values=[],
            ability_cycle_values=[],
            level_values=[],
            randomize_race=True,
            randomize_stats=False,
            random_seed="mercenary",
        )

        with patch.object(provision, "get_columns", return_value=["AccountName", "Name", "DOLCharacters_ID", "Race"]):
            first = provision.build_character_insert(args, "merc001", "Merc001", 100, 7)
            second = provision.build_character_insert(args, "merc002", "Merc002", 100, 7)

        first_race = re.search(r"([134]) AS `Race`", first)
        second_race = re.search(r"([134]) AS `Race`", second)
        self.assertIsNotNone(first_race)
        self.assertIsNotNone(second_race)
        self.assertEqual(first_race.group(1), second_race.group(1))

    def test_character_insert_can_randomize_base_stats_deterministically(self):
        args = SimpleNamespace(
            start_x=None,
            start_y=None,
            start_z=None,
            start_region=None,
            position_step=20,
            template_account="bigjuh",
            template_character="천재다",
            class_cycle_values=[],
            race_cycle_values=[],
            creation_model_cycle_values=[],
            current_model_cycle_values=[],
            spec_cycle_values=[],
            ability_cycle_values=[],
            level_values=[],
            randomize_race=False,
            randomize_stats=True,
            random_stat_min=45,
            random_stat_max=75,
            random_seed="mercenary",
        )

        columns = [
            "AccountName",
            "Name",
            "DOLCharacters_ID",
            "Strength",
            "Constitution",
            "Dexterity",
            "Quickness",
            "Intelligence",
            "Piety",
            "Empathy",
            "Charisma",
        ]
        with patch.object(provision, "get_columns", return_value=columns):
            sql = provision.build_character_insert(args, "merc001", "Merc001", 100, 3)

        for column in columns[3:]:
            self.assertRegex(sql, rf"(4[5-9]|[56][0-9]|7[0-5]) AS `{column}`")
        self.assertNotIn("SELECT `Strength`", sql)

    def test_resolve_mysql_bin_uses_system_mariadb_when_legacy_path_missing(self):
        def fake_exists(path):
            return str(path) == "/usr/bin/mariadb"

        with (
            patch.object(provision, "DEFAULT_MYSQL_CANDIDATES", ["/usr/bin/mariadb"]),
            patch.object(provision.Path, "exists", fake_exists),
        ):
            self.assertEqual(provision.resolve_mysql_bin(None), "/usr/bin/mariadb")

    def test_resolve_mysql_bin_keeps_explicit_value(self):
        self.assertEqual(provision.resolve_mysql_bin("/custom/mysql"), "/custom/mysql")

    def test_read_serverconfig_password_falls_back_when_config_missing(self):
        class MissingPath:
            def __init__(self, *_parts):
                pass

            def resolve(self):
                return self

            @property
            def parents(self):
                return {1: self}

            def __truediv__(self, _other):
                return self

            def exists(self):
                return False

        with patch.object(provision, "Path", MissingPath):
            self.assertEqual(provision.read_serverconfig_password(), "opendaoc-local")


if __name__ == "__main__":
    raise SystemExit(unittest.main())
