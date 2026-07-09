#!/usr/bin/env python3
"""Unit checks for dummy boss gear provisioning helpers."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("equip-dummy-boss-gear.py")
    spec = importlib.util.spec_from_file_location("equip_dummy_boss_gear_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


gear = load_module()


class EquipDummyBossGearTests(unittest.TestCase):
    def test_weapon_template_query_rejects_object_type_zero_and_low_dps(self) -> None:
        sql = gear.choose_template_sql(object_type=3, item_type=10, class_id=1, realm=1)

        self.assertIn("`Object_Type`<>0", sql)
        self.assertIn("`DPS_AF` BETWEEN 160 AND 200", sql)

    def test_template_level_cap_uses_level_bound_instead_of_boss_dps_filter(self) -> None:
        sql = gear.choose_template_sql(object_type=3, item_type=10, class_id=1, realm=1, template_level_cap=12)

        self.assertIn("`Level` <= 12", sql)
        self.assertIn("`Quality` >= 85", sql)
        self.assertNotIn("`DPS_AF` BETWEEN 160 AND 200", sql)

    def test_cloth_armor_query_accepts_level_50_af_scale(self) -> None:
        sql = gear.choose_template_sql(object_type=32, item_type=21, class_id=7, realm=1)

        self.assertIn("`DPS_AF` >= 50", sql)
        self.assertNotIn("`DPS_AF` >= 100", sql)

    def test_instrument_query_accepts_instrument_type_dps_scale(self) -> None:
        sql = gear.choose_template_sql(object_type=45, item_type=12, class_id=4, realm=1)

        self.assertIn("`Quality`>=95", sql)
        self.assertNotIn("`DPS_AF` BETWEEN 160 AND 200", sql)

    def test_build_equipment_plan_requires_expected_boss_slots(self) -> None:
        row = {"owner_id": "char-id", "account": "albtest001", "class": "1", "realm": "1"}
        profile = gear.CLASS_PROFILES[1]
        choices = {
            (profile.weapon_object_type, profile.weapon_slot, 1, 1): "slash_weapon",
            (42, 11, 1, 1): "shield",
        }
        for slot in gear.ARMOR_SLOTS:
            choices[(profile.armor_object_type, slot, 1, 1)] = f"armor_{slot}"

        sql, equipped, missing = gear.build_equipment_plan([row], choices)

        self.assertEqual(equipped, 8)
        self.assertEqual(missing, 0)
        joined = "\n".join(sql)
        self.assertIn("DELETE FROM `inventory`", joined)
        self.assertIn("`ActiveWeaponSlot`=0", joined)

    def test_albion_extended_boss_pool_classes_have_gear_profiles(self) -> None:
        for class_id in (4, 5, 8, 10):
            self.assertIn(class_id, gear.CLASS_PROFILES)

        self.assertEqual(gear.CLASS_PROFILES[4], gear.GearProfile(34, 3, instrument=True))
        self.assertEqual(gear.CLASS_PROFILES[5], gear.GearProfile(32, 8, weapon_slot=12))
        self.assertEqual(gear.CLASS_PROFILES[8], gear.GearProfile(32, 8, weapon_slot=12))
        self.assertEqual(gear.CLASS_PROFILES[10], gear.GearProfile(33, 8, weapon_slot=12))

    def test_mercenary_uses_slashing_dual_wield_profile(self) -> None:
        self.assertEqual(gear.CLASS_PROFILES[11], gear.GearProfile(34, 3, offhand_object_type=3))

    def test_speed_song_classes_equip_active_instrument(self) -> None:
        row = {"owner_id": "minstrel-id", "account": "albtest012", "class": "4", "realm": "1"}
        profile = gear.CLASS_PROFILES[4]
        choices = {
            (profile.weapon_object_type, profile.weapon_slot, 4, 1): "slash_weapon",
            (45, gear.INSTRUMENT_TEMPLATE_ITEM_TYPE, 4, 1): "instrument",
        }
        for slot in gear.ARMOR_SLOTS:
            choices[(profile.armor_object_type, slot, 4, 1)] = f"armor_{slot}"

        sql, equipped, missing = gear.build_equipment_plan([row], choices)

        self.assertEqual(equipped, 8)
        self.assertEqual(missing, 0)
        joined = "\n".join(sql)
        self.assertIn("`SlotPosition`, `Count`", joined)
        self.assertIn("'instrument'", joined)
        self.assertIn("`ActiveWeaponSlot`=2", joined)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
