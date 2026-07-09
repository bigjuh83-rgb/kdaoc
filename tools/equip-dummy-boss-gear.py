#!/usr/bin/env python3
"""Equip dummy boss-test characters with safe level-50 combat gear."""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import tempfile
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
INSTRUMENT_TEMPLATE_ITEM_TYPE = 12
INSTRUMENT_EQUIP_SLOT = 13


@dataclass(frozen=True)
class GearProfile:
    armor_object_type: int
    weapon_object_type: int
    weapon_slot: int = 10
    shield: bool = False
    offhand_object_type: int = 0
    instrument: bool = False


CLASS_PROFILES: dict[int, GearProfile] = {
    # Albion
    1: GearProfile(36, 3, shield=True),   # Paladin: plate, slash + shield
    2: GearProfile(36, 2, shield=True),   # Armsman: plate, crush + shield
    3: GearProfile(34, 3, shield=True),   # Scout: studded, slash + shield
    4: GearProfile(34, 3, instrument=True), # Minstrel: studded, slash + instrument
    5: GearProfile(32, 8, weapon_slot=12), # Theurgist: cloth, staff
    6: GearProfile(35, 2, shield=True),   # Cleric: chain, crush + shield
    7: GearProfile(32, 8, weapon_slot=12), # Wizard: cloth, staff
    8: GearProfile(32, 8, weapon_slot=12), # Sorcerer: cloth, staff
    10: GearProfile(33, 8, weapon_slot=12), # Friar: leather, staff
    11: GearProfile(34, 3, offhand_object_type=3), # Mercenary: studded, slash dual
    13: GearProfile(32, 8, weapon_slot=12), # Cabalist: cloth, staff
    # Midgard
    22: GearProfile(35, 12, shield=True), # Warrior: chain, hammer + shield
    24: GearProfile(35, 11, instrument=True), # Skald: chain, sword + instrument
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
    48: GearProfile(37, 19, instrument=True), # Bard: reinforced, blades + instrument
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


def windows_argument_path_for_wsl(path: str) -> str:
    match = re.match(r"^/mnt/([a-zA-Z])/(.*)$", path)
    if not match:
        return path
    drive = match.group(1).upper()
    rest = match.group(2).replace("/", "\\")
    return f"{drive}:\\{rest}"


def writable_windows_client_defaults_dir(mysql_bin: str) -> str | None:
    mysql_dir = os.path.dirname(str(mysql_bin))
    if mysql_dir and os.path.isdir(mysql_dir) and os.access(mysql_dir, os.W_OK):
        return mysql_dir

    cwd = str(Path.cwd())
    if re.match(r"^/mnt/[a-zA-Z]/", cwd) and os.access(cwd, os.W_OK):
        return cwd

    temp_dir = tempfile.gettempdir()
    if re.match(r"^/mnt/[a-zA-Z]/", temp_dir) and os.access(temp_dir, os.W_OK):
        return temp_dir

    return None


def run_mysql(args: argparse.Namespace, sql: str) -> str:
    env = os.environ.copy()
    use_defaults_file = os.name != "nt" and str(args.mysql_bin).lower().endswith(".exe")
    if use_defaults_file:
        env.pop("MYSQL_PWD", None)
    else:
        env["MYSQL_PWD"] = args.db_password
    command_prefix = [args.mysql_bin]
    if os.name == "nt" and str(args.mysql_bin).startswith("/"):
        wslenv = env.get("WSLENV", "")
        parts = [part for part in wslenv.split(":") if part]
        if "MYSQL_PWD/u" not in parts:
            parts.append("MYSQL_PWD/u")
        env["WSLENV"] = ":".join(parts)
        command_prefix = [os.environ.get("WSL_EXE", r"C:\Windows\System32\wsl.exe"), "--exec", args.mysql_bin]

    defaults_file = None
    defaults_file_arg = None
    if use_defaults_file:
        handle = tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            delete=False,
            dir=writable_windows_client_defaults_dir(str(args.mysql_bin)),
            prefix="opendaoc-mysql-",
            suffix=".ini",
        )
        defaults_file = handle.name
        defaults_file_arg = windows_argument_path_for_wsl(defaults_file)
        with handle:
            handle.write("[client]\n")
            handle.write(f"password={args.db_password}\n")

    cmd = [
        *command_prefix,
        *([f"--defaults-extra-file={defaults_file_arg}"] if defaults_file_arg else []),
        f"-h{args.db_host}",
        f"-P{args.db_port}",
        f"-u{args.db_user}",
        args.db_name,
        "-N",
        "-B",
    ]
    try:
        return subprocess.check_output(cmd, input=sql, text=True, env=env)
    finally:
        if defaults_file:
            Path(defaults_file).unlink(missing_ok=True)


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


def choose_template_sql(
    object_type: int,
    item_type: int,
    class_id: int,
    realm: int,
    *,
    template_level_cap: int = 0,
) -> str:
    level_cap = max(0, int(template_level_cap or 0))
    if level_cap:
        stat_filter = f"`Level` <= {level_cap} AND `Quality` >= 85"
    elif object_type == 45:
        stat_filter = "`Quality`>=95"
    elif 31 <= object_type <= 38:
        stat_filter = "`DPS_AF` >= 50 AND `Quality`>=95"
    else:
        stat_filter = "`DPS_AF` BETWEEN 160 AND 200 AND `Quality`>=95"

    order_clause = (
        "`Level` DESC, `Quality` DESC, `DPS_AF` DESC, `SPD_ABS` DESC, `Id_nb` "
        if level_cap
        else "`Quality` DESC, `DPS_AF` DESC, `Level` DESC, `SPD_ABS` DESC, `Id_nb` "
    )
    return (
        "SELECT `Id_nb` FROM `itemtemplate` "
        f"WHERE `Object_Type`={object_type} AND `Item_Type`={item_type} "
        "AND `Object_Type`<>0 "
        f"AND {stat_filter} "
        f"AND (`Realm` IN (0,{realm}) OR {class_allowed_expression(class_id)}) "
        "ORDER BY "
        f"({class_allowed_expression(class_id)}) DESC, "
        + order_clause +
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
        if profile.instrument:
            wanted.add((45, INSTRUMENT_TEMPLATE_ITEM_TYPE, class_id, realm))
        for slot in ARMOR_SLOTS:
            wanted.add((profile.armor_object_type, slot, class_id, realm))

    choices: dict[tuple[int, int, int, int], str] = {}
    for key in sorted(wanted):
        object_type, item_type, class_id, realm = key
        output = run_mysql(
            args,
            choose_template_sql(
                object_type,
                item_type,
                class_id,
                realm,
                template_level_cap=getattr(args, "template_level_cap", 0),
            ),
        ).strip()
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
        if profile.instrument:
            inserts.append((45, INSTRUMENT_TEMPLATE_ITEM_TYPE, INSTRUMENT_EQUIP_SLOT))
        for slot in ARMOR_SLOTS:
            inserts.append((profile.armor_object_type, slot, slot))

        for object_type, item_type, slot in inserts:
            template_id = choices.get((object_type, item_type, class_id, realm))
            if not template_id:
                missing += 1
                continue
            sql.append(inventory_insert_sql(owner_id, template_id, slot))
            equipped += 1

        active_weapon_slot = 2 if profile.instrument else 1 if profile.weapon_slot == 12 else 0
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
    parser.add_argument("--template-level-cap", type=int, default=0, help="when set, choose equipment templates at or below this item level")
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
