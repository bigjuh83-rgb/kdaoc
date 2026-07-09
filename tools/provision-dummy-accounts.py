#!/usr/bin/env python3
"""Provision dummy accounts/characters for headless OpenDAoC load tests."""

from __future__ import annotations

import argparse
import csv
import hashlib
import os
import random
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from tools.dummy_mysql_compat import windows_argument_path_for_wsl, writable_windows_client_defaults_dir
except ModuleNotFoundError:
    from dummy_mysql_compat import windows_argument_path_for_wsl, writable_windows_client_defaults_dir


DEFAULT_MYSQL_CANDIDATES = [
    str(Path(__file__).resolve().parents[2] / "_tools" / "mariadb-10.11.11-winx64" / "bin" / "mariadb.exe"),
    r"C:\Program Files\MariaDB 12.3\bin\mariadb.exe",
    r"C:\Program Files\MariaDB 12.3\bin\mysql.exe",
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
RANDOM_STAT_COLUMNS = {
    "Strength",
    "Constitution",
    "Dexterity",
    "Quickness",
    "Intelligence",
    "Piety",
    "Empathy",
    "Charisma",
}


def read_serverconfig_password() -> str:
    config_path = Path(__file__).resolve().parents[1] / "CoreServer" / "config" / "serverconfig.xml"

    if not config_path.exists():
        return "opendaoc-local"

    match = re.search(r"Password=([^;]+)", config_path.read_text(encoding="utf-8", errors="ignore"))
    return match.group(1) if match else "opendaoc-local"

def client_character_index(realm: int, slot_index: int) -> int:
    """Return the WorldInit client index for a realm-local character slot."""

    return (realm - 1) * 10 + slot_index


def deterministic_random(args: argparse.Namespace, field: str, position_offset: int) -> random.Random:
    seed = str(getattr(args, "random_seed", "") or getattr(args, "seed", "") or "opendaoc-dummy")
    return random.Random(f"{seed}:{field}:{position_offset}")


def random_cycle_int(args: argparse.Namespace, values: list[str], field: str, position_offset: int) -> int | None:
    parsed = [int(value) for value in values if str(value).strip().lstrip("-").isdigit()]
    if not parsed:
        return None
    return deterministic_random(args, field, position_offset).choice(parsed)


def random_stat_value(args: argparse.Namespace, stat_name: str, position_offset: int) -> int:
    minimum = int(getattr(args, "random_stat_min", 45) or 45)
    maximum = int(getattr(args, "random_stat_max", 75) or 75)
    if maximum < minimum:
        minimum, maximum = maximum, minimum
    minimum = max(1, minimum)
    maximum = min(255, maximum)
    return deterministic_random(args, f"stat:{stat_name}", position_offset).randint(minimum, maximum)


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
WEAPON_ITEM_TYPES = {RIGHT_HAND_SLOT, LEFT_HAND_SLOT, TWO_HAND_SLOT}
SPEC_WEAPON_OBJECT_TYPES = {
    "slash": 3,
    "thrust": 4,
    "crush": 2,
    "staff": 8,
    "sword": 11,
    "hammer": 12,
    "axe": 13,
    "left axe": 17,
    "blades": 19,
    "blunt": 20,
    "large weapons": 22,
    "celtic spear": 23,
}


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

    command = [
        *command_prefix,
        *([f"--defaults-extra-file={defaults_file_arg}"] if defaults_file_arg else []),
        "--batch",
        "--raw",
        "--protocol=tcp",
        "-h",
        args.db_host,
        "-P",
        str(args.db_port),
        "-u",
        args.db_user,
        "--default-character-set=utf8mb4",
        args.db_name,
        "-e",
        sql,
    ]
    try:
        process = subprocess.run(command, check=True, capture_output=True, text=True, env=env)
        return process.stdout
    finally:
        if defaults_file:
            Path(defaults_file).unlink(missing_ok=True)


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


def mysql_bin_available(value: str) -> bool:
    if Path(value).exists():
        return True
    if os.name == "nt" and str(value).startswith("/"):
        try:
            process = subprocess.run(
                [os.environ.get("WSL_EXE", r"C:\Windows\System32\wsl.exe"), "--exec", "test", "-x", value],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError:
            return False
        return process.returncode == 0
    return False


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


def parse_cycle(value: str, delimiter: str = "|") -> list[str]:
    return [part.strip() for part in value.split(delimiter) if part.strip()]


def cycle_value(values: list[str], offset: int) -> str | None:
    if not values:
        return None

    return values[offset % len(values)]


def cycle_int(values: list[str], offset: int) -> int | None:
    value = cycle_value(values, offset)
    return int(value) if value is not None else None


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


def preferred_weapon_object_type_from_specs(specs: str | None) -> int | None:
    best_name = ""
    best_value = -1
    for part in (specs or "").split(";"):
        if "|" not in part:
            continue
        name, value = part.split("|", 1)
        normalized = name.strip().lower()
        try:
            score = int(value.strip())
        except ValueError:
            continue
        if normalized in SPEC_WEAPON_OBJECT_TYPES and score > best_value:
            best_name = normalized
            best_value = score

    return SPEC_WEAPON_OBJECT_TYPES.get(best_name)


def sort_starter_templates_for_specs(
    class_id: int,
    specs: str | None,
    templates: list[dict[str, str]],
) -> list[dict[str, str]]:
    preferred_object_type = preferred_weapon_object_type_from_specs(specs)
    if preferred_object_type is None:
        return list(templates)

    def sort_key(row: dict[str, str]) -> tuple[int, int]:
        try:
            item_type = int(row.get("Item_Type", "0") or 0)
            object_type = int(row.get("Object_Type", "0") or 0)
        except ValueError:
            return (2, 0)
        if item_type in {RIGHT_HAND_SLOT, LEFT_HAND_SLOT, TWO_HAND_SLOT} and object_type == preferred_object_type:
            return (0, item_type)
        return (1, item_type)

    return sorted(templates, key=sort_key)


def is_weapon_starter_template(row: dict[str, str]) -> bool:
    try:
        item_type = int(row.get("Item_Type", "0") or 0)
        object_type = int(row.get("Object_Type", "0") or 0)
    except ValueError:
        return False

    return item_type in WEAPON_ITEM_TYPES and object_type != SHIELD_OBJECT_TYPE


def starter_template_matches_weapon(row: dict[str, str], object_type: int) -> bool:
    try:
        return is_weapon_starter_template(row) and int(row.get("Object_Type", "0") or 0) == object_type
    except ValueError:
        return False


def filter_starter_templates_for_preferred_weapon(
    templates: list[dict[str, str]],
    preferred_object_type: int | None,
) -> list[dict[str, str]]:
    if preferred_object_type is None:
        return list(templates)

    if not any(starter_template_matches_weapon(row, preferred_object_type) for row in templates):
        return list(templates)

    return [
        row
        for row in templates
        if not is_weapon_starter_template(row) or starter_template_matches_weapon(row, preferred_object_type)
    ]


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
    class_id = cycle_int(getattr(args, "class_cycle_values", []), position_offset)
    race_values = getattr(args, "race_cycle_values", [])
    race_id = (
        random_cycle_int(args, race_values, "race", position_offset)
        if getattr(args, "randomize_race", False)
        else cycle_int(race_values, position_offset)
    )
    creation_model = cycle_int(getattr(args, "creation_model_cycle_values", []), position_offset)
    current_model = cycle_int(getattr(args, "current_model_cycle_values", []), position_offset)
    specs = cycle_value(getattr(args, "spec_cycle_values", []), position_offset)
    abilities = cycle_value(getattr(args, "ability_cycle_values", []), position_offset)

    for column in columns:
        if column == "AccountName":
            select_parts.append(f"{sql_quote(account_name)} AS `{column}`")
        elif column == "AccountSlot":
            select_parts.append(f"{account_slot} AS `{column}`")
        elif column == "Name":
            select_parts.append(f"{sql_quote(character_name)} AS `{column}`")
        elif column == "DOLCharacters_ID":
            select_parts.append(f"UUID() AS `{column}`")
        elif column == "Realm":
            select_parts.append(f"{args.realm} AS `{column}`")
        elif column == "Class" and class_id is not None:
            select_parts.append(f"{class_id} AS `{column}`")
        elif column == "Race" and race_id is not None:
            select_parts.append(f"{race_id} AS `{column}`")
        elif column in RANDOM_STAT_COLUMNS and getattr(args, "randomize_stats", False):
            select_parts.append(f"{random_stat_value(args, column, position_offset)} AS `{column}`")
        elif column == "CreationModel" and creation_model is not None:
            select_parts.append(f"{creation_model} AS `{column}`")
        elif column == "CurrentModel" and current_model is not None:
            select_parts.append(f"{current_model} AS `{column}`")
        elif column == "SerializedSpecs" and specs is not None:
            select_parts.append(f"{sql_quote(specs)} AS `{column}`")
        elif column == "SerializedAbilities" and abilities is not None:
            select_parts.append(f"{sql_quote(abilities)} AS `{column}`")
        elif column == "GuildID":
            select_parts.append(f"NULL AS `{column}`")
        elif column in {"CreationDate", "LastLevelUp", "LastTimeRowUpdated"}:
            select_parts.append(f"NOW() AS `{column}`")
        elif column == "LastPlayed":
            select_parts.append(f"NULL AS `{column}`")
        elif column == "Level":
            level_override = cycle_int(getattr(args, "level_values", []), position_offset)
            if level_override is not None and level_override > 0:
                select_parts.append(f"{level_override} AS `{column}`")
            else:
                select_parts.append(f"`{column}`")
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
        elif column == "BindXpos" and args.start_x is not None:
            select_parts.append(f"{args.start_x + args.position_step * position_offset} AS `{column}`")
        elif column == "BindYpos" and args.start_y is not None:
            select_parts.append(f"{args.start_y + args.position_step * position_offset} AS `{column}`")
        elif column == "BindZpos" and args.start_z is not None:
            select_parts.append(f"{args.start_z} AS `{column}`")
        elif column == "BindRegion" and args.start_region is not None:
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


def load_preferred_weapon_template(args: argparse.Namespace, preferred_object_type: int) -> dict[str, str] | None:
    rows = parse_mysql_rows(
        run_mysql(
            args,
            f"""
            SELECT
                '' AS Class,
                it.Id_nb AS TemplateID,
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
            FROM itemtemplate it
            WHERE it.Item_Type IN ({RIGHT_HAND_SLOT}, {LEFT_HAND_SLOT}, {TWO_HAND_SLOT})
              AND it.Object_Type = {preferred_object_type}
              AND it.Level <= 1
              AND it.Realm IN (0, {int(args.realm)})
            ORDER BY
                CASE WHEN it.Level = 0 THEN 0 ELSE 1 END,
                CASE WHEN it.Realm = 0 THEN 0 ELSE 1 END,
                it.Level,
                it.DPS_AF,
                it.Id_nb
            LIMIT 1;
            """,
        )
    )
    return rows[0] if rows else None


def starter_templates_for_specs(args: argparse.Namespace, class_id: int, specs: str | None) -> list[dict[str, str]]:
    preferred_object_type = preferred_weapon_object_type_from_specs(specs)
    templates = sort_starter_templates_for_specs(class_id, specs, load_starter_templates(args, class_id))

    if preferred_object_type is not None and not any(
        starter_template_matches_weapon(row, preferred_object_type) for row in templates
    ):
        preferred_template = load_preferred_weapon_template(args, preferred_object_type)
        if preferred_template is not None:
            templates = [preferred_template, *templates]

    return filter_starter_templates_for_preferred_weapon(templates, preferred_object_type)


def inventory_count(args: argparse.Namespace, owner_id: str) -> int:
    row = get_single_row(
        args,
        f"SELECT COUNT(*) AS Count FROM `inventory` WHERE `OwnerID`={sql_quote(owner_id)};",
    )
    return int(row["Count"]) if row else 0


def inventory_slot_positions(args: argparse.Namespace, owner_id: str) -> set[int]:
    rows = parse_mysql_rows(
        run_mysql(
            args,
            f"SELECT `SlotPosition` FROM `inventory` WHERE `OwnerID`={sql_quote(owner_id)};",
        )
    )
    return {int(row["SlotPosition"]) for row in rows if str(row.get("SlotPosition", "")).strip().isdigit()}


def preferred_starter_slot(item_type: int, object_type: int, used_slots: set[int]) -> int | None:
    if item_type not in EQUIP_SLOTS:
        return None
    if item_type == LEFT_HAND_SLOT and object_type != SHIELD_OBJECT_TYPE and RIGHT_HAND_SLOT not in used_slots:
        return RIGHT_HAND_SLOT
    return item_type


def add_starter_equipment(args: argparse.Namespace, account_name: str, character_name: str) -> int:
    character = get_single_row(
        args,
        "SELECT DOLCharacters_ID, Class, SerializedSpecs FROM `dolcharacters` "
        f"WHERE `AccountName`={sql_quote(account_name)} AND `Name`={sql_quote(character_name)} LIMIT 1;",
    )

    if character is None:
        return 0

    owner_id = character["DOLCharacters_ID"]

    class_id = int(character["Class"])
    starter_templates = starter_templates_for_specs(args, class_id, character.get("SerializedSpecs", ""))
    existing_slots = inventory_slot_positions(args, owner_id)
    used_slots: set[int] = set(existing_slots)
    inserted = 0
    active_weapon_slot: int | None = None

    for template in starter_templates:
        item_type = int(template["Item_Type"])
        object_type = int(template["Object_Type"])
        preferred_slot = preferred_starter_slot(item_type, object_type, used_slots)
        if preferred_slot is not None and preferred_slot in existing_slots:
            continue
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


def sanitize_invalid_item_procs(args: argparse.Namespace, account_name: str, character_name: str) -> None:
    character = get_single_row(
        args,
        "SELECT DOLCharacters_ID FROM `dolcharacters` "
        f"WHERE `AccountName`={sql_quote(account_name)} AND `Name`={sql_quote(character_name)} LIMIT 1;",
    )

    if character is None:
        return

    owner_id = character["DOLCharacters_ID"]

    run_mysql(
        args,
        "UPDATE `itemtemplate` it "
        "JOIN `inventory` inv ON inv.`ITemplate_Id`=it.`Id_nb` "
        "LEFT JOIN `spell` sp ON sp.`SpellID`=it.`ProcSpellID` "
        "SET it.`ProcSpellID`=0 "
        f"WHERE inv.`OwnerID`={sql_quote(owner_id)} AND it.`ProcSpellID`<>0 AND sp.`SpellID` IS NULL;",
    )
    run_mysql(
        args,
        "UPDATE `itemtemplate` it "
        "JOIN `inventory` inv ON inv.`ITemplate_Id`=it.`Id_nb` "
        "LEFT JOIN `spell` sp ON sp.`SpellID`=it.`ProcSpellID1` "
        "SET it.`ProcSpellID1`=0 "
        f"WHERE inv.`OwnerID`={sql_quote(owner_id)} AND it.`ProcSpellID1`<>0 AND sp.`SpellID` IS NULL;",
    )
    run_mysql(
        args,
        "UPDATE `itemtemplate` it "
        "JOIN `inventory` inv ON inv.`ITemplate_Id`=it.`Id_nb` "
        "SET it.`ProcChance`=0 "
        f"WHERE inv.`OwnerID`={sql_quote(owner_id)} "
        "AND it.`ProcSpellID`=0 AND it.`ProcSpellID1`=0;",
    )


CLASS_NAMES = {
    1: "Paladin",
    2: "Armsman",
    3: "Scout",
    4: "Minstrel",
    5: "Theurgist",
    6: "Cleric",
    7: "Wizard",
    8: "Sorcerer",
    10: "Friar",
    11: "Mercenary",
    13: "Cabalist",
    14: "Fighter",
    15: "Elementalist",
    16: "Acolyte",
    17: "Rogue",
    18: "Mage",
    20: "Disciple",
    22: "Warrior",
    24: "Skald",
    26: "Healer",
    28: "Shaman",
    29: "Runemaster",
    31: "Berserker",
    35: "Viking",
    36: "Mystic",
    37: "Seer",
    38: "Rogue",
    40: "Eldritch",
    41: "Enchanter",
    43: "Blademaster",
    44: "Hero",
    45: "Champion",
    47: "Druid",
    48: "Bard",
    51: "Magician",
    52: "Guardian",
    53: "Naturalist",
    54: "Stalker",
    57: "Forester",
}


def write_accounts_csv(path: Path, rows: list[dict[str, str | int | None]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [
            "username",
            "password",
            "realm",
            "char_index",
            "class_id",
            "class_name",
            "specs",
            "start_x",
            "start_y",
            "start_z",
            "zone_id",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mysql-bin", default=os.environ.get("MYSQL_BIN"))
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT", "3306")))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME", "opendaoc"))
    parser.add_argument("--db-user", default=os.environ.get("DB_USER", "root"))
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD", read_serverconfig_password()))
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
    parser.add_argument("--class-cycle", default="", help="pipe-separated class IDs to assign by offset")
    parser.add_argument("--csv-class-cycle", default="", help="pipe-separated target class IDs to write to csv by offset")
    parser.add_argument("--race-cycle", default="", help="pipe-separated race IDs to assign by offset")
    parser.add_argument("--randomize-race", action="store_true", help="choose a deterministic random race from --race-cycle for each generated character")
    parser.add_argument("--randomize-stats", action="store_true", help="assign deterministic random base stats instead of copying template stats")
    parser.add_argument("--random-stat-min", type=int, default=45, help="minimum random base stat when --randomize-stats is enabled")
    parser.add_argument("--random-stat-max", type=int, default=75, help="maximum random base stat when --randomize-stats is enabled")
    parser.add_argument("--random-seed", default="opendaoc-dummy", help="seed for deterministic random race/stat generation")
    parser.add_argument("--creation-model-cycle", default="", help="pipe-separated CreationModel values to assign by offset")
    parser.add_argument("--current-model-cycle", default="", help="pipe-separated CurrentModel values to assign by offset")
    parser.add_argument("--spec-cycle", default="", help="pipe-separated SerializedSpecs values to assign by offset")
    parser.add_argument("--ability-cycle", default="", help="pipe-separated SerializedAbilities values to assign by offset")
    parser.add_argument("--language", default="KR")
    parser.add_argument("--priv-level", type=int, default=1)
    parser.add_argument("--position-step", type=int, default=20)
    parser.add_argument("--start-x", type=int, help="override dummy character start X coordinate")
    parser.add_argument("--start-y", type=int, help="override dummy character start Y coordinate")
    parser.add_argument("--start-z", type=int, help="override dummy character start Z coordinate")
    parser.add_argument("--start-region", type=int, help="override dummy character start region")
    parser.add_argument("--level", default="", help="pipe-separated level values to assign by offset; overrides template level")
    parser.add_argument("--slot-index", type=int, default=0, help="client-visible character index inside the selected realm")
    parser.add_argument("--csv", default="tools/dummy-accounts.csv")
    parser.add_argument("--replace", action="store_true", help="delete existing dummy accounts/chars in the requested range first")
    parser.add_argument("--no-starter-equipment", action="store_true", help="do not add class starter equipment to empty dummy inventories")
    args = parser.parse_args()
    args.mysql_bin = resolve_mysql_bin(args.mysql_bin)
    args.class_cycle_values = parse_cycle(args.class_cycle)
    args.csv_class_cycle_values = parse_cycle(args.csv_class_cycle)
    args.race_cycle_values = parse_cycle(args.race_cycle)
    args.creation_model_cycle_values = parse_cycle(args.creation_model_cycle)
    args.current_model_cycle_values = parse_cycle(args.current_model_cycle)
    args.spec_cycle_values = parse_cycle(args.spec_cycle, "||")
    args.ability_cycle_values = parse_cycle(args.ability_cycle, "||")
    args.level_values = parse_cycle(args.level)

    if not mysql_bin_available(args.mysql_bin):
        raise SystemExit(f"mysql client not found: {args.mysql_bin}")

    if not exists(args, "account", "Name", args.template_account):
        raise SystemExit(f"template account not found: {args.template_account}")

    if not exists(args, "dolcharacters", "Name", args.template_character):
        raise SystemExit(f"template character not found: {args.template_character}")

    password_hash = crypt_password(args.password)
    natural_names = load_character_names(args)

    if args.character_name_mode == "natural" and not natural_names:
        raise SystemExit("natural character name mode needs at least one name")

    csv_rows: list[dict[str, str | int | None]] = []
    created = 0
    skipped = 0
    equipped = 0

    for offset in range(args.count):
        number = args.start + offset
        account_name = f"{args.prefix}{number:03d}"
        character_name = build_character_name(args, number, offset, natural_names)
        char_index = client_character_index(args.realm, args.slot_index)
        account_slot = args.realm * 100 + args.slot_index
        class_id = cycle_int(args.class_cycle_values, offset)
        csv_class_id = cycle_int(args.csv_class_cycle_values, offset) or class_id
        specs = cycle_value(args.spec_cycle_values, offset)

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
            sanitize_invalid_item_procs(args, account_name, character_name)

        csv_rows.append(
            {
                "username": account_name,
                "password": args.password,
                "realm": args.realm,
                "char_index": char_index,
                "class_id": csv_class_id or "",
                "class_name": CLASS_NAMES.get(csv_class_id or 0, ""),
                "specs": specs or "",
                "start_x": args.start_x + args.position_step * offset if args.start_x is not None else "",
                "start_y": args.start_y + args.position_step * offset if args.start_y is not None else "",
                "start_z": args.start_z if args.start_z is not None else "",
                "zone_id": args.start_region if args.start_region is not None else "",
            }
        )

    write_accounts_csv(Path(args.csv), csv_rows)
    print(f"dummy provisioning completed: created={created} skipped={skipped} equipped_items={equipped} csv={args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
