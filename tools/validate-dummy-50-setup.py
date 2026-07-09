#!/usr/bin/env python3
"""Validate dummy boss-test accounts after provisioning and gearing."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path


def load_equip_module():
    module_path = Path(__file__).with_name("equip-dummy-boss-gear.py")
    spec = importlib.util.spec_from_file_location("equip_dummy_boss_gear_runtime", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


equip = load_equip_module()


def load_accounts(paths: list[str]) -> list[str]:
    accounts: list[str] = []
    for path_s in paths:
        with Path(path_s).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                username = (row.get("username") or "").strip()
                if username:
                    accounts.append(username)
    return accounts


def parse_character_rows(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        rows.append(
            {
                "owner_id": parts[0],
                "account": parts[1],
                "name": parts[2],
                "realm": parts[3],
                "class": parts[4],
                "level": parts[5],
                "specs": parts[6],
                "abilities": parts[7] if len(parts) > 7 else "",
            }
        )
    return rows


def parse_equipment_rows(output: str) -> dict[str, dict[int, dict[str, str]]]:
    equipment: dict[str, dict[int, dict[str, str]]] = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 7:
            continue
        owner_id, slot, template_id, object_type, item_type, dps_af, quality = parts[:7]
        equipment.setdefault(owner_id, {})[int(slot)] = {
            "template_id": template_id,
            "object_type": object_type,
            "item_type": item_type,
            "dps_af": dps_af,
            "quality": quality,
        }
    return equipment


def expected_slots(profile) -> dict[int, tuple[int, str]]:
    slots: dict[int, tuple[int, str]] = {
        profile.weapon_slot: (profile.weapon_object_type, "weapon"),
    }
    if profile.shield:
        slots[11] = (42, "shield")
    if profile.offhand_object_type:
        slots[11] = (profile.offhand_object_type, "weapon")
    if getattr(profile, "instrument", False):
        slots[13] = (45, "instrument")
    for slot in equip.ARMOR_SLOTS:
        slots[slot] = (profile.armor_object_type, "armor")
    return slots


def validate_db_setup(characters: list[dict[str, str]], equipment: dict[str, dict[int, dict[str, str]]]) -> list[str]:
    failures: list[str] = []
    for character in characters:
        account = character["account"]
        owner_id = character["owner_id"]
        class_id = int(character["class"] or 0)
        level = int(character["level"] or 0)
        profile = equip.CLASS_PROFILES.get(class_id)

        if level < 50:
            failures.append(f"{account}: level {level} is below 50")
        if not character["specs"] or "|" not in character["specs"]:
            failures.append(f"{account}: SerializedSpecs is missing or malformed")
        if not character["abilities"] or "|" not in character["abilities"]:
            failures.append(f"{account}: SerializedAbilities is missing or malformed")
        if profile is None:
            failures.append(f"{account}: no boss gear profile for class {class_id}")
            continue

        by_slot = equipment.get(owner_id, {})
        for slot, (expected_object_type, slot_kind) in expected_slots(profile).items():
            item = by_slot.get(slot)
            if item is None:
                failures.append(f"{account}: missing {slot_kind} slot {slot}")
                continue

            object_type = int(item["object_type"] or 0)
            dps_af = int(item["dps_af"] or 0)
            quality = int(item["quality"] or 0)
            if object_type == 0:
                failures.append(f"{account}: slot {slot} has invalid Object_Type=0")
            if object_type != expected_object_type:
                failures.append(
                    f"{account}: slot {slot} Object_Type {object_type} != expected {expected_object_type}"
                )
            if slot_kind == "weapon" and dps_af < 160:
                failures.append(f"{account}: weapon slot {slot} DPS_AF {dps_af} below 160")
            if slot_kind == "shield" and dps_af < 100:
                failures.append(f"{account}: shield slot {slot} DPS_AF {dps_af} below 100")
            if slot_kind == "armor" and dps_af < 50:
                failures.append(f"{account}: armor slot {slot} DPS_AF {dps_af} below 50")
            if quality < 95:
                failures.append(f"{account}: slot {slot} quality {quality} below 95")

    return failures


def fetch_usable_snapshot(api_url: str, account: str, timeout: float) -> dict[str, object] | None:
    separator = "&" if "?" in api_url else "?"
    url = api_url + separator + urllib.parse.urlencode({"account": account})
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def validate_usable_api(args: argparse.Namespace, accounts: list[str]) -> list[str]:
    if not args.usable_api_url:
        return []

    failures: list[str] = []
    checked = 0
    for account in accounts:
        try:
            snapshot = fetch_usable_snapshot(args.usable_api_url, account, args.usable_api_timeout)
        except Exception as exc:
            if args.require_online_usable:
                failures.append(f"{account}: usable API unavailable: {exc}")
            continue

        if not isinstance(snapshot, dict):
            failures.append(f"{account}: usable API returned non-object payload")
            continue

        checked += 1
        skills = snapshot.get("skills", [])
        spell_lines = snapshot.get("spellLines", [])
        if not isinstance(skills, list) or not skills:
            failures.append(f"{account}: usable API has no skills")
        if not isinstance(spell_lines, list):
            failures.append(f"{account}: usable API spellLines malformed")

    if args.require_online_usable and checked == 0:
        failures.append("usable API did not validate any online dummy character")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("accounts", nargs="*", default=[
        "tools/dummy-accounts-albion-40.csv",
        "tools/dummy-accounts-midgard-40.csv",
        "tools/dummy-accounts-hibernia-40.csv",
    ])
    parser.add_argument("--mysql-bin", default=os.environ.get("MYSQL_BIN"))
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT", "3306")))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME", "opendaoc"))
    parser.add_argument("--db-user", default=os.environ.get("DB_USER", "root"))
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD", equip.default_db_password()))
    parser.add_argument("--usable-api-url", default="", help="optional /api/dummy/combat/usable endpoint")
    parser.add_argument("--usable-api-timeout", type=float, default=1.5)
    parser.add_argument("--require-online-usable", action="store_true")
    args = parser.parse_args()
    args.mysql_bin = equip.resolve_mysql_bin(args.mysql_bin)

    accounts = load_accounts(args.accounts)
    if not accounts:
        raise SystemExit("no accounts found")

    account_list = ",".join(equip.sql_quote(account) for account in accounts)
    characters = parse_character_rows(
        equip.run_mysql(
            args,
            "SELECT `DOLCharacters_ID`, `AccountName`, `Name`, `Realm`, `Class`, `Level`, "
            "COALESCE(`SerializedSpecs`, ''), COALESCE(`SerializedAbilities`, '') "
            "FROM `dolcharacters` "
            f"WHERE `AccountName` IN ({account_list}) "
            "ORDER BY `AccountName`;",
        )
    )
    owner_list = ",".join(equip.sql_quote(row["owner_id"]) for row in characters)
    equipment = parse_equipment_rows(
        equip.run_mysql(
            args,
            "SELECT inv.`OwnerID`, inv.`SlotPosition`, inv.`ITemplate_Id`, it.`Object_Type`, "
            "it.`Item_Type`, it.`DPS_AF`, it.`Quality` "
            "FROM `inventory` inv "
            "JOIN `itemtemplate` it ON it.`Id_nb`=inv.`ITemplate_Id` "
            f"WHERE inv.`OwnerID` IN ({owner_list}) "
            f"AND inv.`SlotPosition` IN ({','.join(str(slot) for slot in equip.EQUIP_SLOTS)}) "
            "ORDER BY inv.`OwnerID`, inv.`SlotPosition`;",
        )
        if owner_list
        else ""
    )

    failures = validate_db_setup(characters, equipment)
    failures.extend(validate_usable_api(args, accounts))

    if failures:
        for failure in failures:
            print(f"FAIL {failure}")
        print(f"dummy 50 setup validation failed: accounts={len(accounts)} failures={len(failures)}")
        return 1

    print(f"dummy 50 setup validation ok: accounts={len(accounts)} characters={len(characters)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
