#!/usr/bin/env python3
"""Provision dummy accounts/characters for headless OpenDAoC load tests."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path


DEFAULT_MYSQL_CANDIDATES = [
    "/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb",
    "/usr/bin/mariadb",
    "/usr/local/bin/mariadb",
    "/usr/bin/mysql",
    "/usr/local/bin/mysql",
]
DEFAULT_NATURAL_CHARACTER_NAMES = [
    "가온",
    "라온",
    "이든",
    "하람",
    "서윤",
    "도윤",
    "유찬",
    "시온",
    "루아",
    "아린",
    "로한",
    "유리",
    "카엘",
    "리안",
    "엘린",
    "세린",
    "아델",
    "노아",
    "라엘",
    "하온",
    "벨라",
    "루카",
    "아셀",
    "레온",
    "이안",
    "에린",
    "마엘",
    "세아",
    "리아",
    "테오",
]

EQUIP_SLOTS = {
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    15,
    16,
    17,
    21,
    22,
    23,
    24,
    25,
    26,
    27,
    28,
    29,
    32,
    33,
    34,
    35,
    36,
    37,
}
RIGHT_HAND_SLOT = 10
LEFT_HAND_SLOT = 11
TWO_HAND_SLOT = 12
RANGED_SLOT = 13
FIRST_BACKPACK_SLOT = 40
LAST_BACKPACK_SLOT = 79
SHIELD_OBJECT_TYPE = 42


def crypt_password(password: str) -> str:
    digest = hashlib.md5(password.encode("utf-16-be")).digest()
    return "##" + "".join(f"{value:X}" for value in digest)


def sql_quote(value: str | None) -> str:
    if value is None:
        return "NULL"

    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def parse_name_list(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def load_character_names(args: argparse.Namespace) -> list[str]:
    if args.character_names:
        return parse_name_list(args.character_names)

    if args.character_name_file:
        return [
            line.strip()
            for line in Path(args.character_name_file).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

    return list(DEFAULT_NATURAL_CHARACTER_NAMES)


def build_character_name(args: argparse.Namespace, number: int, offset: int, natural_names: list[str]) -> str:
    if args.character_name_mode == "natural":
        base_name = natural_names[offset % len(natural_names)]
        cycle = offset // len(natural_names)
        return base_name if cycle == 0 else f"{base_name}{cycle + 1}"

    return f"{args.character_prefix}{number:03d}"


def run_mysql(args: argparse.Namespace, sql: str) -> str:
    command = [
        args.mysql_bin,
        "--batch",
        "--raw",
        "--protocol=tcp",
        "-h",
        args.db_host,
        "-P",
        str(args.db_port),
        "-u",
        args.db_user,
        f"-p{args.db_password}",
        "--default-character-set=utf8mb4",
        args.db_name,
        "-e",
        sql,
    ]
    process = subprocess.run(command, check=True, capture_output=True, text=True)
    return process.stdout


def resolve_mysql_bin(value: str | None) -> str:
    if value:
        return value

    for candidate in DEFAULT_MYSQL_CANDIDATES:
        if Path(candidate).exists():
            return candidate

    for binary in ("mariadb", "mysql"):
        found = shutil.which(binary)

        if found:
            return found

    return DEFAULT_MYSQL_CANDIDATES[0]


def parse_mysql_rows(output: str) -> list[dict[str, str]]:
    lines = [line for line in output.splitlines() if line.strip()]

    if len(lines) < 2:
        return []

    columns = lines[0].split("\t")
    rows: list[dict[str, str]] = []

    for line in lines[1:]:
        values = line.split("\t")
        rows.append({column: values[index] if index < len(values) else "" for index, column in enumerate(columns)})

    return rows


def get_columns(args: argparse.Namespace, table: str) -> list[str]:
    output = run_mysql(args, f"SHOW COLUMNS FROM `{table}`;")
    columns: list[str] = []

    for index, line in enumerate(output.splitlines()):
        if index == 0 or not line.strip():
            continue
        columns.append(line.split("\t", 1)[0])

    return columns


def exists(args: argparse.Namespace, table: str, column: str, value: str) -> bool:
    output = run_mysql(
        args,
        f"SELECT COUNT(*) FROM `{table}` WHERE `{column}`={sql_quote(value)};",
    )
    lines = [line for line in output.splitlines() if line.strip()]
    return len(lines) >= 2 and int(lines[1]) > 0


def parse_class_list(value: str) -> set[int]:
    classes: set[int] = set()

    for part in re.split(r"[;,]", value):
        part = part.strip()

        if not part:
            continue

        try:
            classes.add(int(part))
        except ValueError:
            continue

    return classes


def choose_starter_slot(item_type: int, object_type: int, used_slots: set[int]) -> int:
    if item_type in EQUIP_SLOTS:
        chosen_slot = item_type

        if item_type == LEFT_HAND_SLOT and object_type != SHIELD_OBJECT_TYPE and RIGHT_HAND_SLOT not in used_slots:
            chosen_slot = RIGHT_HAND_SLOT

        if chosen_slot not in used_slots:
            used_slots.add(chosen_slot)
            return chosen_slot

    for slot in range(FIRST_BACKPACK_SLOT, LAST_BACKPACK_SLOT):
        if slot not in used_slots:
            used_slots.add(slot)
            return slot

    raise RuntimeError("no free starter equipment slot")


def get_single_row(args: argparse.Namespace, sql: str) -> dict[str, str] | None:
    rows = parse_mysql_rows(run_mysql(args, sql))
    return rows[0] if rows else None


def build_account_insert(args: argparse.Namespace, account_name: str, password_hash: str) -> str:
    columns = get_columns(args, "account")
    select_parts: list[str] = []

    for column in columns:
        if column == "Name":
            select_parts.append(f"{sql_quote(account_name)} AS `{column}`")
        elif column == "Password":
            select_parts.append(f"{sql_quote(password_hash)} AS `{column}`")
        elif column == "PrivLevel":
            select_parts.append(f"{args.priv_level} AS `{column}`")
        elif column == "Realm":
            select_parts.append(f"{args.realm} AS `{column}`")
        elif column == "Language":
            select_parts.append(f"{sql_quote(args.language)} AS `{column}`")
        elif column == "Account_ID":
            select_parts.append(f"{sql_quote(account_name)} AS `{column}`")
        elif column in {"CreationDate", "LastTimeRowUpdated"}:
            select_parts.append(f"NOW() AS `{column}`")
        elif column in {"LastLogin", "LastDisconnected", "Realm_Timer_Last_Combat"}:
            select_parts.append(f"NULL AS `{column}`")
        elif column == "LastLoginIP":
            select_parts.append(f"{sql_quote('127.0.0.1')} AS `{column}`")
        elif column == "Notes":
            select_parts.append(f"{sql_quote('Headless dummy account')} AS `{column}`")
        else:
            select_parts.append(f"`{column}`")

    return (
        f"INSERT INTO `account` ({', '.join(f'`{column}`' for column in columns)}) "
        f"SELECT {', '.join(select_parts)} FROM `account` "
        f"WHERE `Name`={sql_quote(args.template_account)} LIMIT 1;"
    )


def build_character_insert(
    args: argparse.Namespace,
    account_name: str,
    character_name: str,
    account_slot: int,
    position_offset: int,
) -> str:
    columns = get_columns(args, "dolcharacters")
    select_parts: list[str] = []

    for column in columns:
        if column == "AccountName":
            select_parts.append(f"{sql_quote(account_name)} AS `{column}`")
        elif column == "AccountSlot":
            select_parts.append(f"{account_slot} AS `{column}`")
        elif column == "Name":
            select_parts.append(f"{sql_quote(character_name)} AS `{column}`")
        elif column == "DOLCharacters_ID":
            select_parts.append(f"UUID() AS `{column}`")
        elif column == "GuildID":
            select_parts.append(f"NULL AS `{column}`")
        elif column in {"CreationDate", "LastLevelUp", "LastTimeRowUpdated"}:
            select_parts.append(f"NOW() AS `{column}`")
        elif column == "LastPlayed":
            select_parts.append(f"NULL AS `{column}`")
        elif column in {"PlayedTime", "PlayedTimeSinceLevel", "RealmPoints", "BountyPoints", "Experience"}:
            select_parts.append(f"0 AS `{column}`")
        elif column == "Xpos" and args.start_x is not None:
            select_parts.append(f"{args.start_x + args.position_step * position_offset} AS `{column}`")
        elif column == "Ypos" and args.start_y is not None:
            select_parts.append(f"{args.start_y + args.position_step * position_offset} AS `{column}`")
        elif column == "Zpos" and args.start_z is not None:
            select_parts.append(f"{args.start_z} AS `{column}`")
        elif column in {"Region", "RegionID"} and args.start_region is not None:
            select_parts.append(f"{args.start_region} AS `{column}`")
        elif column == "Xpos":
            select_parts.append(f"`{column}` + {args.position_step * position_offset} AS `{column}`")
        elif column == "Ypos":
            select_parts.append(f"`{column}` + {args.position_step * position_offset} AS `{column}`")
        else:
            select_parts.append(f"`{column}`")

    return (
        f"INSERT INTO `dolcharacters` ({', '.join(f'`{column}`' for column in columns)}) "
        f"SELECT {', '.join(select_parts)} FROM `dolcharacters` "
        f"WHERE `AccountName`={sql_quote(args.template_account)} "
        f"AND `Name`={sql_quote(args.template_character)} LIMIT 1;"
    )


def load_starter_templates(args: argparse.Namespace, class_id: int) -> list[dict[str, str]]:
    rows = parse_mysql_rows(
        run_mysql(
            args,
            """
            SELECT
                se.Class,
                se.TemplateID,
                it.Item_Type,
                it.Object_Type,
                it.PackSize,
                it.Color,
                it.Emblem,
                it.Extension,
                it.SalvageExtension,
                it.MaxCondition,
                it.MaxDurability,
                it.Charges,
                it.MaxCharges,
                it.Charges1,
                it.MaxCharges1,
                it.PoisonSpellID,
                it.PoisonMaxCharges,
                it.PoisonCharges
            FROM starterequipment se
            JOIN itemtemplate it ON it.Id_nb = se.TemplateID
            ORDER BY it.Item_Type, se.StarterEquipmentID;
            """,
        )
    )
    return [row for row in rows if class_id in parse_class_list(row.get("Class", ""))]


def inventory_count(args: argparse.Namespace, owner_id: str) -> int:
    row = get_single_row(
        args,
        f"SELECT COUNT(*) AS Count FROM `inventory` WHERE `OwnerID`={sql_quote(owner_id)};",
    )
    return int(row["Count"]) if row else 0


def add_starter_equipment(args: argparse.Namespace, account_name: str, character_name: str) -> int:
    character = get_single_row(
        args,
        "SELECT DOLCharacters_ID, Class FROM `dolcharacters` "
        f"WHERE `AccountName`={sql_quote(account_name)} AND `Name`={sql_quote(character_name)} LIMIT 1;",
    )

    if character is None:
        return 0

    owner_id = character["DOLCharacters_ID"]

    if inventory_count(args, owner_id) > 0:
        return 0

    starter_templates = load_starter_templates(args, int(character["Class"]))
    used_slots: set[int] = set()
    inserted = 0
    active_weapon_slot: int | None = None

    for template in starter_templates:
        item_type = int(template["Item_Type"])
        object_type = int(template["Object_Type"])
        slot = choose_starter_slot(item_type, object_type, used_slots)
        count = max(int(template["PackSize"]), 1)
        charges = int(template["Charges"])
        max_charges = int(template["MaxCharges"])
        charges1 = int(template["Charges1"])
        max_charges1 = int(template["MaxCharges1"])
        salvage_extension = template.get("SalvageExtension", "")
        salvage_sql = "NULL" if salvage_extension in {"", "NULL", r"\N"} else str(int(salvage_extension))

        run_mysql(
            args,
            "INSERT INTO `inventory` ("
            "`OwnerID`, `OwnerLot`, `ITemplate_Id`, `UTemplate_Id`, `IsCrafted`, `Creator`, "
            "`SlotPosition`, `Count`, `SellPrice`, `Experience`, `Color`, `Emblem`, `Extension`, "
            "`Condition`, `Durability`, `PoisonSpellID`, `PoisonMaxCharges`, `PoisonCharges`, "
            "`Charges`, `Charges1`, `Cooldown`, `LastTimeRowUpdated`, `Inventory_ID`, `IsROG`, `SalvageExtension`"
            ") VALUES ("
            f"{sql_quote(owner_id)}, 0, {sql_quote(template['TemplateID'])}, NULL, 0, {sql_quote('provision-dummy-accounts.py')}, "
            f"{slot}, {count}, 0, 0, {int(template['Color'])}, {int(template['Emblem'])}, {int(template['Extension'])}, "
            f"{int(template['MaxCondition'])}, {int(template['MaxDurability'])}, {int(template['PoisonSpellID'])}, "
            f"{int(template['PoisonMaxCharges'])}, {int(template['PoisonCharges'])}, "
            f"{charges if charges > 0 else max_charges}, {charges1 if charges1 > 0 else max_charges1}, "
            f"0, NOW(), UUID(), 0, {salvage_sql});",
        )
        inserted += 1

        if active_weapon_slot is None:
            if slot == RIGHT_HAND_SLOT:
                active_weapon_slot = 0
            elif slot == TWO_HAND_SLOT:
                active_weapon_slot = 1
            elif slot == RANGED_SLOT:
                active_weapon_slot = 2

    if active_weapon_slot is not None:
        run_mysql(
            args,
            f"UPDATE `dolcharacters` SET `ActiveWeaponSlot`={active_weapon_slot} WHERE `DOLCharacters_ID`={sql_quote(owner_id)};",
        )

    return inserted


def write_accounts_csv(path: Path, rows: list[tuple[str, str, int, int]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write("username,password,realm,char_index\n")

        for username, password, realm, char_index in rows:
            handle.write(f"{username},{password},{realm},{char_index}\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mysql-bin", default=os.environ.get("MYSQL_BIN"))
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT", "3306")))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME", "opendaoc"))
    parser.add_argument("--db-user", default=os.environ.get("DB_USER", "root"))
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD", "opendaoc-local"))
    parser.add_argument("--template-account", default="bigjuh")
    parser.add_argument("--template-character", default="천재다")
    parser.add_argument("--prefix", default="dummy")
    parser.add_argument("--character-prefix", default="Dummy")
    parser.add_argument("--character-name-mode", choices=["sequential", "natural"], default="sequential")
    parser.add_argument("--character-names", default="", help="pipe-separated character names for --character-name-mode natural")
    parser.add_argument("--character-name-file", default="", help="UTF-8 text file with one character name per line")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--count", type=int, default=5)
    parser.add_argument("--password", default=os.environ.get("OPENDAOC_DUMMY_PASSWORD", "dummy-pass"))
    parser.add_argument("--realm", type=int, default=1)
    parser.add_argument("--language", default="KR")
    parser.add_argument("--priv-level", type=int, default=1)
    parser.add_argument("--position-step", type=int, default=20)
    parser.add_argument("--start-x", type=int, help="override dummy character start X coordinate")
    parser.add_argument("--start-y", type=int, help="override dummy character start Y coordinate")
    parser.add_argument("--start-z", type=int, help="override dummy character start Z coordinate")
    parser.add_argument("--start-region", type=int, help="override dummy character start region")
    parser.add_argument("--slot-index", type=int, default=0, help="client-visible character index inside the selected realm")
    parser.add_argument("--csv", default="tools/dummy-accounts.csv")
    parser.add_argument("--replace", action="store_true", help="delete existing dummy accounts/chars in the requested range first")
    parser.add_argument("--no-starter-equipment", action="store_true", help="do not add class starter equipment to empty dummy inventories")
    args = parser.parse_args()
    args.mysql_bin = resolve_mysql_bin(args.mysql_bin)

    if not Path(args.mysql_bin).exists():
        raise SystemExit(f"mysql client not found: {args.mysql_bin}")

    if not exists(args, "account", "Name", args.template_account):
        raise SystemExit(f"template account not found: {args.template_account}")

    if not exists(args, "dolcharacters", "Name", args.template_character):
        raise SystemExit(f"template character not found: {args.template_character}")

    password_hash = crypt_password(args.password)
    natural_names = load_character_names(args)

    if args.character_name_mode == "natural" and not natural_names:
        raise SystemExit("natural character name mode needs at least one name")

    csv_rows: list[tuple[str, str, int, int]] = []
    created = 0
    skipped = 0
    equipped = 0

    for offset in range(args.count):
        number = args.start + offset
        account_name = f"{args.prefix}{number:03d}"
        character_name = build_character_name(args, number, offset, natural_names)
        char_index = args.slot_index
        account_slot = args.realm * 100 + char_index

        if args.replace:
            run_mysql(
                args,
                f"DELETE FROM `dolcharacters` WHERE `AccountName`={sql_quote(account_name)} OR `Name`={sql_quote(character_name)};"
                f"DELETE FROM `account` WHERE `Name`={sql_quote(account_name)};",
            )

        if exists(args, "account", "Name", account_name) or exists(args, "dolcharacters", "Name", character_name):
            skipped += 1
        else:
            run_mysql(args, build_account_insert(args, account_name, password_hash))
            run_mysql(args, build_character_insert(args, account_name, character_name, account_slot, offset))
            created += 1

        if not args.no_starter_equipment:
            equipped += add_starter_equipment(args, account_name, character_name)

        csv_rows.append((account_name, args.password, args.realm, char_index))

    write_accounts_csv(Path(args.csv), csv_rows)
    print(f"dummy provisioning completed: created={created} skipped={skipped} equipped_items={equipped} csv={args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
