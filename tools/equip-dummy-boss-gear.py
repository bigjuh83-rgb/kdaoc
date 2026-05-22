#!/usr/bin/env python3
"""Equip dummy boss-test characters with safe level-50 combat gear."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MYSQL_CANDIDATES = [
    "/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb",
    "/usr/bin/mariadb",
    "/usr/local/bin/mariadb",
    "/usr/bin/mysql",
    "/usr/local/bin/mysql",
]
EQUIP_SLOTS = (10, 11, 12, 13, 21, 22, 23, 25, 27, 28)
ARMOR_SLOTS = (21, 22, 23, 25, 27, 28)


@dataclass(frozen=True)
class GearProfile:
    armor_object_type: int
    weapon_object_type: int
    weapon_slot: int = 10
    shield: bool = False
    offhand_object_type: int = 0


CLASS_PROFILES: dict[int, GearProfile] = {
    # Albion
    1: GearProfile(36, 3, shield=True),   # Paladin: plate, slash + shield
    2: GearProfile(36, 2, shield=True),   # Armsman: plate, crush + shield
    4: GearProfile(34, 3),                # Minstrel: studded, slash
    5: GearProfile(32, 8, weapon_slot=12), # Theurgist: cloth, staff
    6: GearProfile(35, 2, shield=True),   # Cleric: chain, crush + shield
    7: GearProfile(32, 8, weapon_slot=12), # Wizard: cloth, staff
    8: GearProfile(32, 8, weapon_slot=12), # Sorcerer: cloth, staff
    10: GearProfile(33, 8, weapon_slot=12), # Friar: leather, staff
    11: GearProfile(34, 3, offhand_object_type=3), # Mercenary: studded, slash dual
    13: GearProfile(32, 8, weapon_slot=12), # Cabalist: cloth, staff
    # Midgard
    22: GearProfile(35, 12, shield=True), # Warrior: chain, hammer + shield
    24: GearProfile(35, 11),              # Skald: chain, sword
    26: GearProfile(35, 12, shield=True), # Healer: chain, hammer + shield
    28: GearProfile(35, 12, shield=True), # Shaman: chain, hammer + shield
    29: GearProfile(32, 8, weapon_slot=12), # Runemaster: cloth, staff
    31: GearProfile(34, 13, offhand_object_type=17), # Berserker: studded, axe + left axe
    # Hibernia
    40: GearProfile(32, 8, weapon_slot=12), # Eldritch: cloth, staff
    41: GearProfile(32, 8, weapon_slot=12), # Enchanter: cloth, staff
    43: GearProfile(37, 19, offhand_object_type=19), # Blademaster: reinforced, blades dual
    44: GearProfile(38, 19, shield=True), # Hero: scale, blades + shield
    45: GearProfile(38, 22, weapon_slot=12), # Champion: scale, large weapon
    47: GearProfile(38, 20, shield=True), # Druid: scale, blunt + shield
    48: GearProfile(37, 19),              # Bard: reinforced, blades
}


def sql_quote(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def resolve_mysql_bin(value: str | None) -> str:
    if value:
        return value

    for candidate in DEFAULT_MYSQL_CANDIDATES:
        if Path(candidate).exists():
            return candidate

    found = shutil.which("mariadb") or shutil.which("mysql")
    if found:
        return found

    raise SystemExit("mysql client not found")


def default_db_password() -> str:
    config_path = Path("CoreServer/config/serverconfig.xml")
    if not config_path.exists():
        return os.environ.get("DB_PASSWORD", "opendaoc-local")

    config = config_path.read_text(encoding="utf-8")
    match = re.search(r"Password=([^;]+)", config)
    return match.group(1) if match else os.environ.get("DB_PASSWORD", "opendaoc-local")


def run_mysql(args: argparse.Namespace, sql: str) -> str:
    env = os.environ.copy()
    env["MYSQL_PWD"] = args.db_password
    cmd = [
        args.mysql_bin,
        f"-h{args.db_host}",
        f"-P{args.db_port}",
        f"-u{args.db_user}",
        args.db_name,
        "-N",
        "-B",
    ]
    return subprocess.check_output(cmd, input=sql, text=True, env=env)


def load_accounts(paths: list[str]) -> list[str]:
    accounts: list[str] = []
    for path_s in paths:
        with Path(path_s).open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                username = (row.get("username") or "").strip()
                if username:
                    accounts.append(username)
    return accounts


def parse_rows(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) < 4:
            continue
        rows.append({"owner_id": parts[0], "account": parts[1], "class": parts[2], "realm": parts[3]})
    return rows


def class_allowed_expression(class_id: int) -> str:
    class_text = str(class_id)
    return (
        "`AllowedClasses`='0' OR `AllowedClasses`='' OR `AllowedClasses` IS NULL "
        f"OR FIND_IN_SET({sql_quote(class_text)}, REPLACE(`AllowedClasses`, ';', ',')) > 0"
    )


def choose_template_sql(object_type: int, item_type: int, class_id: int, realm: int) -> str:
    if object_type == 42:
        stat_filter = "`DPS_AF` BETWEEN 100 AND 200"
    elif 31 <= object_type <= 38:
        stat_filter = "`DPS_AF` >= 50"
    else:
        stat_filter = "`DPS_AF` BETWEEN 160 AND 200"

    return (
        "SELECT `Id_nb` FROM `itemtemplate` "
        f"WHERE `Object_Type`={object_type} AND `Item_Type`={item_type} "
        "AND `Object_Type`<>0 AND `Quality`>=95 "
        f"AND {stat_filter} "
        f"AND (`Realm` IN (0,{realm}) OR {class_allowed_expression(class_id)}) "
        "ORDER BY "
        f"({class_allowed_expression(class_id)}) DESC, "
        "`Quality` DESC, `DPS_AF` DESC, `Level` DESC, `SPD_ABS` DESC, `Id_nb` "
        "LIMIT 1"
    )


def load_template_choices(args: argparse.Namespace, rows: list[dict[str, str]]) -> dict[tuple[int, int, int, int], str]:
    wanted: set[tuple[int, int, int, int]] = set()
    for row in rows:
        class_id = int(row["class"])
        realm = int(row["realm"])
        profile = CLASS_PROFILES.get(class_id)
        if profile is None:
            continue
        wanted.add((profile.weapon_object_type, profile.weapon_slot, class_id, realm))
        if profile.shield:
            wanted.add((42, 11, class_id, realm))
        if profile.offhand_object_type:
            wanted.add((profile.offhand_object_type, 11, class_id, realm))
        for slot in ARMOR_SLOTS:
            wanted.add((profile.armor_object_type, slot, class_id, realm))

    choices: dict[tuple[int, int, int, int], str] = {}
    for key in sorted(wanted):
        object_type, item_type, class_id, realm = key
        output = run_mysql(args, choose_template_sql(object_type, item_type, class_id, realm)).strip()
        if output:
            choices[key] = output.splitlines()[0].split("\t")[0]
    return choices


def inventory_insert_sql(owner_id: str, template_id: str, slot: int) -> str:
    return (
        "INSERT INTO `inventory` ("
        "`OwnerID`, `OwnerLot`, `ITemplate_Id`, `UTemplate_Id`, `IsCrafted`, `Creator`, "
        "`SlotPosition`, `Count`, `SellPrice`, `Experience`, `Color`, `Emblem`, `Extension`, "
        "`Condition`, `Durability`, `PoisonSpellID`, `PoisonMaxCharges`, `PoisonCharges`, "
        "`Charges`, `Charges1`, `Cooldown`, `LastTimeRowUpdated`, `Inventory_ID`, `IsROG`, `SalvageExtension`"
        ") "
        "SELECT "
        f"{sql_quote(owner_id)}, 0, it.`Id_nb`, NULL, 0, 'equip-dummy-boss-gear.py', "
        f"{slot}, GREATEST(it.`PackSize`, 1), 0, 0, it.`Color`, it.`Emblem`, it.`Extension`, "
        "it.`MaxCondition`, it.`MaxDurability`, it.`PoisonSpellID`, it.`PoisonMaxCharges`, it.`PoisonCharges`, "
        "IF(it.`Charges` > 0, it.`Charges`, it.`MaxCharges`), IF(it.`Charges1` > 0, it.`Charges1`, it.`MaxCharges1`), "
        "0, NOW(), UUID(), 0, it.`SalvageExtension` "
        "FROM `itemtemplate` it "
        f"WHERE it.`Id_nb`={sql_quote(template_id)} LIMIT 1;"
    )


def build_equipment_plan(
    rows: list[dict[str, str]],
    choices: dict[tuple[int, int, int, int], str],
) -> tuple[list[str], int, int]:
    sql: list[str] = ["USE opendaoc;"]
    equipped = 0
    missing = 0

    for row in rows:
        owner_id = row["owner_id"]
        class_id = int(row["class"])
        realm = int(row["realm"])
        profile = CLASS_PROFILES.get(class_id)
        if profile is None:
            missing += 1
            continue

        sql.append(
            "DELETE FROM `inventory` "
            f"WHERE `OwnerID`={sql_quote(owner_id)} "
            f"AND `SlotPosition` IN ({','.join(str(slot) for slot in EQUIP_SLOTS)});"
        )

        inserts: list[tuple[int, int, int]] = [(profile.weapon_object_type, profile.weapon_slot, profile.weapon_slot)]
        if profile.shield:
            inserts.append((42, 11, 11))
        if profile.offhand_object_type:
            inserts.append((profile.offhand_object_type, 11, 11))
        for slot in ARMOR_SLOTS:
            inserts.append((profile.armor_object_type, slot, slot))

        for object_type, item_type, slot in inserts:
            template_id = choices.get((object_type, item_type, class_id, realm))
            if not template_id:
                missing += 1
                continue
            sql.append(inventory_insert_sql(owner_id, template_id, slot))
            equipped += 1

        active_weapon_slot = 1 if profile.weapon_slot == 12 else 0
        sql.append(
            "UPDATE `dolcharacters` "
            f"SET `ActiveWeaponSlot`={active_weapon_slot}, `Health`=9999, `Endurance`=10000, `Mana`=9999, "
            "`DeathTime`=0, `DeathCount`=0 "
            f"WHERE `DOLCharacters_ID`={sql_quote(owner_id)};"
        )

    return sql, equipped, missing


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
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD", default_db_password()))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.mysql_bin = resolve_mysql_bin(args.mysql_bin)

    accounts = load_accounts(args.accounts)
    if not accounts:
        raise SystemExit("no accounts found")

    account_list = ",".join(sql_quote(account) for account in accounts)
    rows = parse_rows(
        run_mysql(
            args,
            "SELECT `DOLCharacters_ID`, `AccountName`, `Class`, `Realm` "
            "FROM `dolcharacters` "
            f"WHERE `AccountName` IN ({account_list}) "
            "ORDER BY `AccountName`;",
        )
    )
    choices = load_template_choices(args, rows)
    sql, equipped, missing = build_equipment_plan(rows, choices)

    if args.dry_run:
        print("\n".join(sql))
    else:
        run_mysql(args, "\n".join(sql))
    print(f"dummy boss gear equipped: characters={len(rows)} items={equipped} missing_slots={missing} dry_run={args.dry_run}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
