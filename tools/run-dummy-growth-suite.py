#!/usr/bin/env python3
"""Run realm/party dummy growth tests and record DB-backed progress timelines."""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import math
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from daoc_zone_heightmap import ClientZoneHeightSampler
DEFAULT_REPORT_ROOT = TOOLS / "reports" / "dummy-growth"
DEFAULT_DUMMY_HOST = os.environ.get("OPENDAOC_DUMMY_HOST", "192.168.0.42")
DEFAULT_MYSQL_CANDIDATES = [
    "/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb",
    "/usr/bin/mariadb",
    "/usr/local/bin/mariadb",
    "/usr/bin/mysql",
    "/usr/local/bin/mysql",
]
DEFAULT_WINDOWS_MYSQL_CANDIDATES = [
    r"C:\Program Files\MariaDB 12.3\bin\mariadb.exe",
    r"C:\Program Files\MariaDB 12.2\bin\mariadb.exe",
    r"C:\Program Files\MariaDB 12.1\bin\mariadb.exe",
    r"C:\Program Files\MariaDB 12.0\bin\mariadb.exe",
    r"C:\Program Files\MariaDB 11.8\bin\mariadb.exe",
    r"C:\Program Files\MariaDB 11.4\bin\mariadb.exe",
    r"D:\다옥프리서버\_tools\mariadb-10.11.11-winx64\bin\mariadb.exe",
]
COPPER_PER_SILVER = 100
COPPER_PER_GOLD = 10_000
COPPER_PER_PLATINUM = 10_000_000
TIMELINE_WRITE_LOCK = threading.Lock()
GROWTH_SAFE_EXIT_MAX_SECONDS = 90.0
GROWTH_SAFE_EXIT_RECENT_DAMAGE_GRACE = 12.0
GROWTH_STARTUP_TELEPORTER_HOME_TIMEOUT = 90.0
GROWTH_STAGE_DEFAULTS = {
    "custom": None,
    "stabilize": {"reset_level": 1, "max_level": 4, "segment_seconds": 90, "max_segments": 1},
    "train": {"reset_level": 5, "max_level": 6, "segment_seconds": 120, "max_segments": 2},
    "gear": {"reset_level": 6, "max_level": 10, "segment_seconds": 300, "max_segments": 10},
    "long": {"reset_level": 10, "max_level": 50, "segment_seconds": 600, "max_segments": 60},
}
GROWTH_SPEED_PROFILES = {"debug", "fast-balance"}
EQUIPMENT_SLOTS = {7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29, 32, 33, 34, 35, 36, 37}
BACKPACK_FIRST_SLOT = 40
BACKPACK_LAST_SLOT = 79
MERCHANT_WINDOW_SLOTS = 30
ARMOR_OBJECT_TYPE_MIN = 31
ARMOR_OBJECT_TYPE_MAX = 38
SHIELD_OBJECT_TYPE = 42
WEAPON_EQUIPMENT_SLOTS = {10, 11, 12, 13}
OFFHAND_WEAPON_SLOT = 11
OFFHAND_WEAPON_CLASS_IDS = {9, 11, 23, 31, 43, 49}
OFFHAND_WEAPON_ABILITY_TOKENS = ("dual wield", "left axe", "left axes", "celtic dual")
RANDOM_LOOT_TIER_FIELDS = {
    "일반": "loot_tier_common",
    "마력": "loot_tier_magic",
    "희귀": "loot_tier_rare",
    "영웅": "loot_tier_heroic",
    "전설": "loot_tier_legendary",
    "신화": "loot_tier_mythic",
}
RANDOM_LOOT_FIELDS = ["random_loot_total", *RANDOM_LOOT_TIER_FIELDS.values()]
ARMOR_ABILITY_BY_REALM = {
    1: "AlbArmor",
    2: "MidArmor",
    3: "HibArmor",
}
ARMOR_REQUIRED_ABILITY_LEVEL_BY_OBJECT_TYPE = {
    31: 0,  # GenericArmor
    32: 1,  # Cloth
    33: 2,  # Leather
    34: 3,  # Studded
    35: 4,  # Chain
    36: 5,  # Plate
    37: 3,  # Reinforced
    38: 4,  # Scale
}
WEAPON_ABILITY_NAMES_BY_OBJECT_TYPE = {
    2: ("Weaponry: Crushing",),
    3: ("Weaponry: Slashing",),
    4: ("Weaponry: Thrusting",),
    5: ("Weaponry: Shortbows",),
    6: ("Weaponry: Two Handed",),
    7: ("Weaponry: Polearms",),
    8: ("Weaponry: Staves",),
    9: ("Weaponry: Longbows", "Weaponry: Archery"),
    10: ("Weaponry: Crossbow",),
    11: ("Weaponry: Swords",),
    12: ("Weaponry: Hammers",),
    13: ("Weaponry: Axes",),
    14: ("Weaponry: Spears",),
    15: ("Weaponry: Composite Bows", "Weaponry: Archery"),
    16: ("Weaponry: Thrown",),
    17: ("Weaponry: Left Axes",),
    18: ("Weaponry: Recurved Bows", "Weaponry: Archery"),
    19: ("Weaponry: Blades",),
    20: ("Weaponry: Blunt",),
    21: ("Weaponry: Piercing",),
    22: ("Weaponry: Large Weapons",),
    23: ("Weaponry: Celtic Spears",),
    24: ("Weaponry: Flexible",),
    25: ("Weaponry: Hand to Hand",),
    26: ("Weaponry: Scythe",),
    27: ("Weaponry: Fist Wraps",),
    28: ("Weaponry: Mauler Staff",),
    42: ("Shield",),
    44: ("Weaponry: Crossbow",),
    45: ("Weaponry: Instruments",),
}
WEAPON_SPEC_NAMES_BY_OBJECT_TYPE = {
    2: ("Crush", "Blunt"),
    3: ("Slash",),
    4: ("Thrust", "Piercing"),
    5: ("Shortbows",),
    6: ("Two Handed",),
    7: ("Polearm",),
    8: ("Staff",),
    9: ("Longbows",),
    10: ("Crossbows",),
    11: ("Sword",),
    12: ("Hammer",),
    13: ("Axe",),
    14: ("Spear",),
    15: ("Composite Bow",),
    16: ("Thrown Weapons",),
    17: ("Left Axe",),
    18: ("Recurve Bow",),
    19: ("Blades",),
    20: ("Blunt",),
    21: ("Piercing",),
    22: ("Large Weapons",),
    23: ("Celtic Spear",),
    24: ("Flexible",),
    25: ("Hand to Hand",),
    26: ("Scythe",),
}
WEAPON_ABILITY_BY_SPEC_NAME = {
    "Crush": "Weaponry: Crushing",
    "Blunt": "Weaponry: Blunt",
    "Slash": "Weaponry: Slashing",
    "Thrust": "Weaponry: Thrusting",
    "Piercing": "Weaponry: Piercing",
    "Two Handed": "Weaponry: Two Handed",
    "Polearm": "Weaponry: Polearms",
    "Staff": "Weaponry: Staves",
    "Hammer": "Weaponry: Hammers",
    "Sword": "Weaponry: Swords",
    "Axe": "Weaponry: Axes",
    "Left Axe": "Weaponry: Left Axes",
    "Blades": "Weaponry: Blades",
    "Large Weapons": "Weaponry: Large Weapons",
    "Celtic Spear": "Weaponry: Celtic Spears",
    "Flexible": "Weaponry: Flexible",
    "Hand to Hand": "Weaponry: Hand to Hand",
    "Scythe": "Weaponry: Scythe",
}
XP_FOR_LEVEL = (
    0,
    50,
    250,
    850,
    2300,
    6350,
    15950,
    37950,
    88950,
    203950,
    459950,
    839950,
    1399950,
    2199950,
    3399950,
    5199950,
    7899950,
    11799950,
    17499950,
    25899950,
    38199950,
    54699950,
    76999950,
    106999950,
    146999950,
    199999950,
    269999950,
    359999950,
    479999950,
    639999950,
    849999950,
    1119999950,
    1469999950,
    1929999950,
    2529999950,
    3319999950,
    4299999950,
    5499999950,
    6899999950,
    8599999950,
    12899999950,
    20699999950,
    29999999950,
    40799999950,
    53999999950,
    69599999950,
    88499999950,
    110999999950,
    137999999950,
    169999999950,
    999999999950,
)
XP_MESSAGE_PATTERNS = [
    re.compile(r"경험치\s*([0-9,]+)\s*점"),
    re.compile(r"寃쏀뿕移\D{0,12}([0-9][0-9,]*)"),
    re.compile(r"\b(?:you\s+)?(?:gain|get|got|receive|received)\s+([0-9,]+)\s+(?:experience|xp)\b", re.IGNORECASE),
    re.compile(r"\b([0-9,]+)\s+(?:experience|xp)\b", re.IGNORECASE),
]


@dataclass(frozen=True)
class RoutePoint:
    level: int
    x: int
    y: int
    z: int
    prefer: str = ""
    avoid: str = ""
    teleport_destination: str = ""
    objective_adds: str = ""
    source: str = ""
    mob_level: int = 0
    mob_count: int = 0
    live_anchor_z: bool = False
    startup_anchor: bool = False


@dataclass(frozen=True)
class RealmProfile:
    key: str
    realm_id: int
    region: int
    prefix: str
    character_prefix: str
    class_cycle: str
    race_cycle: str
    spec_cycle: str
    start: tuple[int, int, int]
    points: tuple[RoutePoint, ...]
    ground_z_map: str = ""
    startup_service_npc_name: str = ""
    growth_class_cycle: str = ""
    growth_race_cycle: str = ""
    growth_spec_cycle: str = ""


TELEPORT_DESTINATIONS: dict[str, tuple[tuple[str, int, int, int], ...]] = {
    "alb": (
        ("Adribard's Retreat", 472348, 629103, 1724),
        ("Avalon Marsh", 462144, 633058, 1739),
        ("Caer Ulfwych", 521393, 616461, 1784),
        ("Campacorentin Station", 493679, 591770, 1819),
        ("Castle Sauvage", 584151, 477177, 2600),
        ("Cotswold Village", 560574, 511800, 2280),
        ("Prydwen Keep", 574199, 528948, 2863),
        ("Snowdonia Fortress", 527543, 358900, 8320),
        ("Yarley's Farm", 369957, 679721, 5540),
    ),
    "mid": (
        ("Audliten", 729152, 760225, 4573),
        ("Fort Atla", 749218, 817547, 4408),
        ("Fort Veldon", 801046, 678588, 5299),
        ("Gotar", 771152, 836380, 4624),
        ("Huginfell", 712192, 783970, 4672),
        ("Mularn", 803612, 726671, 4743),
        ("Svasud Faste", 767242, 669591, 5736),
        ("Vindsaul Faste", 703389, 738621, 5704),
        ("West Skona", 712345, 923847, 5043),
    ),
    "hib": (
        ("Ardagh", 350446, 553634, 5120),
        ("Connla", 295765, 642599, 4849),
        ("Druim Cain", 421264, 486315, 1824),
        ("Druim Ligen", 334342, 419994, 5184),
        ("Howth", 343184, 592636, 5456),
        ("Innis Carthaig", 334622, 720123, 4296),
        ("Mag Mell", 346100, 491380, 5210),
        ("Shannon Estuary", 309968, 645164, 4848),
        ("Tir na mBeo", 345698, 528897, 5448),
    ),
}

DIRECT_STARTUP_TELEPORT_DESTINATIONS = {
    "druim cain",
    "svasud faste",
}


STARTUP_TELEPORTER_HUBS: dict[str, tuple[int, int, int]] = {
    "alb": (531504, 479073, 2200),
    "mid": (774601, 755307, 4600),
    "hib": (345677, 490738, 5200),
}


@dataclass(frozen=True)
class CharacterSnapshot:
    account: str
    name: str
    character_id: str
    level: int
    experience: int
    realm: int
    class_id: int
    specs: str
    region: int
    x: int
    y: int
    z: int
    deaths: int
    money_copper: int
    inventory_rows: int
    inventory_items: int
    serialized_abilities: str = ""


@dataclass(frozen=True)
class InventoryItem:
    account: str
    slot: int
    template_id: str
    name: str
    level: int
    dps_af: int
    spd_abs: int
    object_type: int
    item_type: int
    quality: int
    bonus: int
    allowed_classes: str
    count: int
    sell_price: int
    realm: int = 0
    type_damage: int = 0


@dataclass(frozen=True)
class GrowthPartyShareTransfer:
    source_account: str
    source_slot: int
    target_account: str
    target_slot: int
    target_equip_slot: int
    item_name: str
    candidate_score: int
    equipped_score: int


@dataclass(frozen=True)
class SegmentDbRestoreState:
    character_rows: list[dict[str, str]]
    inventory_columns: list[str]
    inventory_rows: list[dict[str, str]]


@dataclass(frozen=True)
class GrowthItemPlan:
    equip_slots: list[int]
    sell_slots: list[int]
    party_share_slots: list[int] = field(default_factory=list)
    party_share_transfers: list[GrowthPartyShareTransfer] = field(default_factory=list)
    party_share_executed_slots: list[int] = field(default_factory=list)
    party_share_received_slots: list[int] = field(default_factory=list)
    party_share_failed_slots: list[int] = field(default_factory=list)
    equip_reason: str = ""
    sell_reason: str = ""
    party_share_reason: str = ""
    party_share_execution_reason: str = ""
    merchant_npc_name: str = ""
    buy_slots: list[int] = field(default_factory=list)
    buy_inventory_slots: list[int] = field(default_factory=list)
    buy_reason: str = ""
    buy_shortage_copper: int = 0


@dataclass(frozen=True)
class MerchantItemCandidate:
    merchant_name: str
    item_list_id: str
    buy_slot: int
    template_id: str
    name: str
    level: int
    dps_af: int
    spd_abs: int
    object_type: int
    item_type: int
    quality: int
    bonus: int
    allowed_classes: str
    price: int
    distance: int
    realm: int = 0
    type_damage: int = 0


def route_point(
    level: int,
    x: int,
    y: int,
    z: int,
    prefer: str = "",
    avoid: str = "",
    teleport_destination: str = "",
    objective_adds: str = "",
    source: str = "",
    mob_level: int = 0,
    mob_count: int = 0,
    live_anchor_z: bool = False,
    startup_anchor: bool = False,
) -> RoutePoint:
    return RoutePoint(
        level=level,
        x=x,
        y=y,
        z=z,
        prefer=prefer,
        avoid=avoid,
        teleport_destination=teleport_destination,
        objective_adds=objective_adds,
        source=source,
        mob_level=mob_level,
        mob_count=mob_count,
        live_anchor_z=live_anchor_z,
        startup_anchor=startup_anchor,
    )


def mid_level_ten_hobgoblin_party_route() -> RoutePoint:
    return route_point(
        10,
        747600,
        855000,
        4760,
        "hobgoblin prowler",
        "노련한,돌연변이,흉포한,우두머리,정예,챔피언,ghost light,nacken,haunt,wind wisp,seithr orb,svartalf guard,svartalf outcast",
        "Gotar",
        source="hunting-index",
        mob_level=8,
        mob_count=19,
    )


def mid_level_ten_tawny_lynx_party_route() -> RoutePoint:
    return route_point(
        10,
        780000,
        850000,
        4820,
        "tawny lynx",
        "노련한,돌연변이,흉포한,우두머리,정예,챔피언,tawny lynx cub,young lynx,green serpent,nacken,wolf spiderling,wind wisp,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,wood-eater alate,small hill cat",
        "Gotar",
        source="hunting-index",
        mob_level=8,
        mob_count=6,
        live_anchor_z=True,
    )


def nearest_teleport_destination(realm: RealmProfile, route: RoutePoint) -> str:
    if route.teleport_destination:
        return route.teleport_destination
    destinations = TELEPORT_DESTINATIONS.get(realm.key, ())
    if not destinations:
        return route.teleport_destination

    def distance_squared(destination: tuple[str, int, int, int]) -> int:
        _, x, y, z = destination
        return (route.x - x) ** 2 + (route.y - y) ** 2 + (route.z - z) ** 2

    return min(destinations, key=distance_squared)[0]


def teleport_destination_point(realm: RealmProfile, destination_name: str) -> tuple[int, int, int] | None:
    destination_key = normalize_teleport_destination(destination_name)
    if not destination_key:
        return None
    for name, x, y, z in TELEPORT_DESTINATIONS.get(realm.key, ()):
        if normalize_teleport_destination(name) == destination_key:
            return x, y, z
    return None


def startup_teleporter_home(realm: RealmProfile) -> str:
    x, y, z = STARTUP_TELEPORTER_HUBS[realm.key]
    return f"{x},{y},{z}"


def normalize_teleport_destination(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def normalize_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", normalize_teleport_destination(value)).strip("_")


def growth_cycle(value: str, fallback: str) -> str:
    return value or fallback


def split_spec_cycle(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split("||") if part.strip()]


def checkpoint_specs_by_account(
    account_names: list[str],
    realm: RealmProfile | None,
    target_specs_by_account: dict[str, str] | None,
) -> dict[str, str]:
    if realm is None:
        return {}
    cycle_specs = split_spec_cycle(growth_cycle(realm.growth_spec_cycle, realm.spec_cycle))
    specs_by_account: dict[str, str] = {}
    for index, account in enumerate(account_names):
        spec = (target_specs_by_account or {}).get(account, "").strip()
        if not spec and cycle_specs:
            spec = cycle_specs[index % len(cycle_specs)]
        if spec:
            specs_by_account[account] = spec
    return specs_by_account


BASE_CLASS_BY_TARGET_CLASS = {
    1: 14,
    2: 14,
    4: 17,
    5: 15,
    6: 16,
    7: 15,
    8: 18,
    10: 16,
    11: 14,
    13: 18,
    22: 35,
    24: 35,
    26: 37,
    28: 37,
    29: 36,
    31: 35,
    40: 51,
    41: 51,
    43: 52,
    44: 52,
    45: 52,
    47: 53,
    48: 53,
}


PROMOTION_RIGHT_HAND_WEAPON_BY_TARGET_CLASS = {
    1: "slash_sword_item",
    22: "bronze_battle_hammer2",
    44: "bastard_sword",
}


def base_class_cycle_for_growth(class_cycle: str) -> str:
    values: list[str] = []
    for token in class_cycle.split("|"):
        token = token.strip()
        if not token:
            continue
        class_id = to_int(token)
        values.append(str(BASE_CLASS_BY_TARGET_CLASS.get(class_id, class_id)))
    return "|".join(values)


def should_provision_base_classes(args: argparse.Namespace) -> bool:
    if not bool(getattr(args, "growth_start_base_classes", True)):
        return False
    checkpoint_levels = [
        int(level)
        for level in getattr(args, "checkpoint_levels_parsed", []) or []
        if int(level or 0) > 0
    ]
    if checkpoint_levels:
        return min(checkpoint_levels) < 5
    return int(getattr(args, "reset_level", 1) or 1) < 5


def strict_route_target_name(route: RoutePoint, current_level: int, party_size: int = 0, realm_key: str = "") -> str:
    if realm_key == "mid" and party_size <= 1 and current_level == 7:
        for token in (token.strip() for token in route.prefer.split(",") if token.strip()):
            return token
    if realm_key == "alb" and party_size == 2 and current_level == 10 and route.source == "hunting-index":
        preferred = route.prefer.split(",", 1)[0].strip()
        if preferred.lower() in {"river racer", "rotting zombie"}:
            return preferred
    if realm_key == "mid" and party_size == 2 and current_level == 10 and route.source == "hunting-index":
        preferred = route.prefer.split(",", 1)[0].strip()
        if preferred:
            return preferred
    if realm_key == "hib" and party_size == 2 and current_level == 10 and route.source == "hunting-index":
        preferred = route.prefer.split(",", 1)[0].strip()
        if preferred.lower() in {"water beetle"}:
            return preferred
    if realm_key == "mid" and party_size >= 8 and current_level == 3 and route.source == "hunting-index":
        for token in (token.strip() for token in route.prefer.split(",") if token.strip()):
            return token
    if realm_key == "hib" and party_size <= 1 and current_level in {5, 6} and route.source == "hunting-index":
        for token in (token.strip() for token in route.prefer.split(",") if token.strip()):
            return token
    if route.source == "hunting-index":
        if (
            int(current_level or 0) >= 7
            and int(party_size or 0) == 1
            and realm_key in {"alb", "hib"}
            and route.prefer
        ):
            return route.prefer
        if int(party_size or 0) <= 1 and int(current_level or 0) >= 8 and route.prefer:
            return route.prefer
        return ""
    if realm_key == "hib" and party_size == 1 and current_level <= 2:
        return ""
    if realm_key == "hib" and party_size == 1 and current_level == 3:
        preferred = route.prefer.split(",", 1)[0].strip()
        if preferred.lower() in {"water beetle larva", "skeletal pawn", "large frog", "sand crab"}:
            return preferred
        return ""
    if realm_key == "hib" and party_size == 1 and current_level == 4:
        return ""
    if realm_key == "hib" and party_size == 1 and current_level == 6:
        preferred_tokens = {token.strip().lower() for token in route.prefer.split(",") if token.strip()}
        if "mudman" in preferred_tokens:
            return "mudman"
        return ""
    if realm_key == "mid" and party_size == 4 and current_level <= 1:
        preferred_tokens = {token.strip().lower() for token in route.prefer.split(",") if token.strip()}
        if "tawny lynx cub" in preferred_tokens:
            return "tawny lynx cub"
        return ""
    if current_level <= 1 and party_size == 1 and route.prefer:
        return route.prefer.split(",", 1)[0].strip()
    if current_level >= 8 and route.prefer:
        return route.prefer
    return ""


def normalize_growth_target_name(value: str) -> str:
    return " ".join(str(value or "").replace("’", "'").lower().split())


GROWTH_ROUTE_PREFLIGHT_TARGET_ARTICLES = ("a", "an", "the")
GROWTH_ROUTE_PREFLIGHT_TARGET_PREFIXES = (
    "돌연변이",
    "우두머리",
    "흉포한",
    "노련한",
    "정예",
    "챔피언",
    "mutant",
    "mutated",
    "boss",
    "ferocious",
    "veteran",
    "elite",
    "champion",
)


def growth_route_preflight_is_generic_growth_prefix_token(value: str) -> bool:
    return normalize_growth_target_name(value) in GROWTH_ROUTE_PREFLIGHT_TARGET_PREFIXES


def growth_route_preflight_name_has_growth_prefix(value: str) -> bool:
    parts = normalize_growth_target_name(value).split()
    while parts and parts[0] in GROWTH_ROUTE_PREFLIGHT_TARGET_ARTICLES:
        parts = parts[1:]
    observed = False
    while parts and parts[0] in GROWTH_ROUTE_PREFLIGHT_TARGET_PREFIXES:
        observed = True
        parts = parts[1:]
    return observed


def growth_route_preflight_name_without_growth_prefix(value: str) -> str:
    parts = normalize_growth_target_name(value).split()
    while parts and parts[0] in GROWTH_ROUTE_PREFLIGHT_TARGET_ARTICLES:
        parts = parts[1:]
    while parts and parts[0] in GROWTH_ROUTE_PREFLIGHT_TARGET_PREFIXES:
        parts = parts[1:]
    return " ".join(parts)


def growth_route_preflight_same_base_growth_prefix_items(
    target_name: str,
    items: Iterable[dict[str, object]],
) -> tuple[dict[str, object], ...]:
    target_base = growth_route_preflight_name_without_growth_prefix(target_name)
    if not target_base or growth_route_preflight_name_has_growth_prefix(target_name):
        return ()
    prefixed: list[dict[str, object]] = []
    for item in items:
        item_name = str(item.get("name", "") or "")
        if not growth_route_preflight_name_has_growth_prefix(item_name):
            continue
        if growth_route_preflight_name_without_growth_prefix(item_name) == target_base:
            prefixed.append(item)
    return tuple(prefixed)


def growth_route_preflight_item_distance(left: dict[str, object], right: dict[str, object]) -> float | None:
    left_x = to_int(left.get("x"))
    left_y = to_int(left.get("y"))
    right_x = to_int(right.get("x"))
    right_y = to_int(right.get("y"))
    if left_x <= 0 or left_y <= 0 or right_x <= 0 or right_y <= 0:
        return None
    return math.hypot(left_x - right_x, left_y - right_y)


def growth_route_preflight_filter_same_base_growth_prefix_pressure(
    target_name: str,
    available_items: tuple[dict[str, object], ...],
    raw_items: tuple[dict[str, object], ...],
    *,
    radius: float,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, object], ...]]:
    if radius <= 0.0 or not available_items:
        return available_items, ()
    prefix_items = growth_route_preflight_same_base_growth_prefix_items(target_name, raw_items)
    measurable_prefix_items = tuple(
        item for item in prefix_items if to_int(item.get("x")) > 0 and to_int(item.get("y")) > 0
    )
    if not measurable_prefix_items:
        return available_items, ()
    safe_items: list[dict[str, object]] = []
    pressure_items: list[dict[str, object]] = []
    for item in available_items:
        item_x = to_int(item.get("x"))
        item_y = to_int(item.get("y"))
        if item_x <= 0 or item_y <= 0:
            safe_items.append(item)
            continue
        nearest_prefix = min(
            (
                distance
                for prefix_item in measurable_prefix_items
                for distance in [growth_route_preflight_item_distance(item, prefix_item)]
                if distance is not None
            ),
            default=None,
        )
        if nearest_prefix is not None and nearest_prefix <= radius:
            pressure_items.append(item)
        else:
            safe_items.append(item)
    if not pressure_items:
        return available_items, ()
    return tuple(safe_items), tuple(measurable_prefix_items)


def growth_route_preflight_same_base_growth_prefix_scan_names(target_name: str) -> tuple[str, ...]:
    target_base = growth_route_preflight_name_without_growth_prefix(target_name)
    if not target_base or growth_route_preflight_name_has_growth_prefix(target_name):
        return ()
    return tuple(f"{prefix} {target_base}" for prefix in GROWTH_ROUTE_PREFLIGHT_TARGET_PREFIXES)


def growth_route_preflight_item_nearby_avoid_count(item: dict[str, object]) -> int:
    return max(
        0,
        to_int(
            item.get(
                "nearbyAvoidCount",
                item.get("nearby_avoid_count", 0),
            )
        ),
    )


def growth_route_preflight_filter_nearby_avoid_pressure(
    available_items: tuple[dict[str, object], ...],
) -> tuple[tuple[dict[str, object], ...], int]:
    if not available_items:
        return (), 0
    safe_items = tuple(
        item
        for item in available_items
        if growth_route_preflight_item_nearby_avoid_count(item) <= 0
    )
    return safe_items, len(available_items) - len(safe_items)


def strict_route_target_name_requires_exact(
    route: RoutePoint,
    current_level: int,
    party_size: int = 0,
    realm_key: str = "",
) -> bool:
    required = strict_route_target_name(route, current_level, party_size, realm_key)
    if (
        str(realm_key or "").strip().lower() == "alb"
        and int(current_level or 0) == 7
        and int(party_size or 0) <= 1
        and str(route.source or "").startswith("hunting-index")
        and "rot worm" in str(required or "").lower()
    ):
        return False
    if is_alb_solo_level_seven_failed_rot_worm_emerald_route(
        route,
        level=current_level,
        party_size=party_size,
        realm_key=realm_key,
    ) or is_alb_solo_level_seven_dragon_ant_worker_route(
        route,
        level=current_level,
        party_size=party_size,
        realm_key=realm_key,
    ):
        return False
    if (
        required
        and realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and str(route.source or "").startswith("hunting-index")
    ):
        return True
    return bool(
        required
        and int(party_size or 0) <= 1
        and (
            (realm_key == "mid" and int(current_level or 0) == 7)
            or (
                realm_key in {"alb", "hib"}
                and int(current_level or 0) == 7
                and str(route.source or "").startswith("hunting-index")
            )
        )
    )


REALMS: dict[str, RealmProfile] = {
    "alb": RealmProfile(
        key="alb",
        realm_id=1,
        region=1,
        prefix="growthalb",
        character_prefix="GrowthAlb",
        class_cycle="1|2|11|10|6|6|7|5|1|2|11|4|6|10|13|8",
        race_cycle="1|3|1|3|3|3|1|1|1|3|1|1|3|3|2|2",
        spec_cycle=(
            "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13||"
            "Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1||"
            "Slash|50;Thrust|1;Crush|1;Dual Wield|50;Parry|28||"
            "Staff|39;Enhancement|45;Rejuvenation|30;Parry|18||"
            "Smite|1;Rejuvenation|40;Enhancement|36||"
            "Smite|1;Rejuvenation|40;Enhancement|36||"
            "Fire Magic|50;Earth Magic|15;Cold Magic|10||"
            "Wind Magic|45;Earth Magic|25;Cold Magic|8||"
            "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13||"
            "Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1||"
            "Slash|50;Thrust|1;Crush|1;Dual Wield|50;Parry|28||"
            "Instruments|44;Slash|39;Stealth|25||"
            "Smite|1;Rejuvenation|40;Enhancement|36||"
            "Staff|39;Enhancement|45;Rejuvenation|30;Parry|18||"
            "Matter Magic|46;Body Magic|28;Spirit Magic|4||"
            "Body Magic|45;Mind Magic|29;Matter Magic|4"
        ),
        growth_class_cycle="1|6|2|11|10|7|5|6|13|8|4",
        growth_race_cycle="1|3|3|1|3|1|1|3|2|2|1",
        growth_spec_cycle=(
            "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13||"
            "Smite|1;Rejuvenation|40;Enhancement|36||"
            "Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1||"
            "Slash|50;Thrust|1;Crush|1;Dual Wield|50;Parry|28||"
            "Staff|39;Enhancement|45;Rejuvenation|30;Parry|18||"
            "Fire Magic|50;Earth Magic|15;Cold Magic|10||"
            "Wind Magic|45;Earth Magic|25;Cold Magic|8||"
            "Smite|1;Rejuvenation|40;Enhancement|36||"
            "Body Magic|45;Mind Magic|29;Matter Magic|4||"
            "Matter Magic|46;Body Magic|28;Spirit Magic|4||"
            "Instruments|44;Slash|39;Stealth|25"
        ),
        start=(534900, 477500, 2200),
        points=(
            route_point(1, 534650, 477500, 2200, "black wolf pup,boar piglet,weak skeleton", "young cutpurse,green snake"),
            route_point(2, 534900, 478900, 2310, "black wolf pup", "young cutpurse,green snake,small gray wolf"),
            route_point(3, 534900, 478900, 2310, "black wolf pup", "young cutpurse,green snake,small gray wolf"),
            route_point(4, 532950, 473718, 2395, "skeleton,bear cub,wild sow", "young cutpurse,green snake,small gray wolf,black wolf pup,boar piglet,Pebble"),
            route_point(5, 534900, 478900, 2310, "small gray wolf", "skeleton,bear cub,wild sow,young cutpurse,weak skeleton,Pebble,Yaren,shady pilferer,green snake,black wolf pup,boar piglet,spectral hound,river drakeling,river sprite,bear,carrion drake"),
            route_point(6, 591020, 532686, 2342, "small bear", "Pebble,Yaren,goblin fisherman,undead goblin fisherman,shady pilferer,young cutpurse,green snake,spectral hound,highwayman,cutpurse,bullyboy,red dwarf thief,river drakeling,river sprite,carrion drake", teleport_destination="Prydwen Keep"),
            route_point(
                7,
                464792,
                645770,
                1699,
                "rot worm,emerald snake,faerie bell-wether,zombie boar",
                "bogman grappler,bandit,giant spider,tree spirit,shady pilferer,spriggarn stalker,skeleton,young cutpurse",
                teleport_destination="Avalon Marsh",
            ),
            route_point(
                8,
                498052,
                592067,
                1994,
                "giant spider",
                "tree spirit,bogman grappler,bandit,shady pilferer,spriggarn stalker,skeleton,rot worm,emerald snake,faerie bell-wether,young cutpurse",
                teleport_destination="Campacorentin Station",
            ),
            route_point(
                9,
                595800,
                526000,
                2725,
                "adder",
                "moldy skeleton,goblin scout,spectral hound,Slith,giant spider,tree spirit,shady pilferer,spriggarn stalker,skeleton,rot worm,emerald snake,faerie bell-wether,young cutpurse",
                teleport_destination="Prydwen Keep",
            ),
            route_point(
                10,
                594457,
                499932,
                2057,
                "adder",
                "dragon ant soldier,spirit,노련한 spirit,bandit,노련한 도적,moldy skeleton,goblin scout,spectral hound,Slith,giant spider,tree spirit,shady pilferer,spriggarn stalker,skeleton,rot worm,emerald snake,faerie bell-wether,young cutpurse",
                teleport_destination="Castle Sauvage",
                mob_level=8,
            ),
            route_point(15, 542572, 584326, 3263, "ashen fellwood", teleport_destination="Caer Ulfwych"),
            route_point(20, 536446, 475521, 3652, teleport_destination="Caer Ulfwych"),
            route_point(25, 494638, 482463, 4231, teleport_destination="Campacorentin Station"),
            route_point(30, 542878, 608836, 2917, "black lion,black lioness", teleport_destination="Caer Ulfwych"),
            route_point(35, 488921, 459093, 4242, teleport_destination="Cornwall Station"),
            route_point(40, 490379, 482595, 4043, teleport_destination="Swanton Keep"),
            route_point(45, 506796, 463636, 3860, teleport_destination="Lyonesse"),
            route_point(
                50,
                332701,
                669142,
                2712,
                "moorlich",
                "gabriel hound,woodeworm,peallaidh,pygmy goblin,archer,footman",
                teleport_destination="Yarley's Farm",
            ),
        ),
        ground_z_map="tools/pathing/heightmaps/region001_client_zones.json",
        startup_service_npc_name="Brother Penric",
    ),
    "mid": RealmProfile(
        key="mid",
        realm_id=2,
        region=100,
        prefix="growthmid",
        character_prefix="GrowthMid",
        class_cycle="22|22|31|24|26|26|28|29",
        race_cycle="5|7|6|5|7|7|8|5",
        spec_cycle=(
            "Hammer|50;Shields|42;Parry|39;Sword|1;Axe|1;Thrown Weapons|1||"
            "Sword|50;Shields|42;Parry|39;Hammer|1;Axe|1;Thrown Weapons|1||"
            "Axe|50;Left Axe|50;Parry|28;Sword|1;Hammer|1||"
            "Sword|44;Battlesongs|46;Parry|21;Hammer|1;Axe|1||"
            "Mending|40;Augmentation|36;Pacification|1||"
            "Mending|40;Augmentation|36;Pacification|1||"
            "Augmentation|40;Mending|36;Subterranean|1||"
            "Runecarving|50;Darkness|15;Suppression|10"
        ),
        growth_class_cycle="22|26|31|22|22|28|29|26",
        growth_race_cycle="5|7|6|5|7|8|5|7",
        growth_spec_cycle=(
            "Hammer|50;Shields|42;Parry|39;Sword|1;Axe|1;Thrown Weapons|1||"
            "Mending|40;Augmentation|36;Pacification|1||"
            "Axe|50;Left Axe|50;Parry|28;Sword|1;Hammer|1||"
            "Hammer|50;Shields|42;Parry|39;Sword|1;Axe|1;Thrown Weapons|1||"
            "Sword|50;Shields|42;Parry|39;Hammer|1;Axe|1;Thrown Weapons|1||"
            "Augmentation|40;Mending|36;Subterranean|1||"
            "Runecarving|50;Darkness|15;Suppression|10||"
            "Mending|40;Augmentation|36;Pacification|1"
        ),
        start=(773327, 749653, 4552),
        points=(
            route_point(1, 770900, 746700, 4620, "young sveawolf", "soft-shelled crab,vein spiderling,lupine gnawer,lupine snarler"),
            route_point(2, 767400, 745984, 4542, "young lynx,lupine snarler,young sveawolf", "soft-shelled crab,vein spiderling,lupine gnawer"),
            route_point(3, 767400, 745984, 4542, "young lynx,lupine snarler,young sveawolf", "thrall,green serpent,soft-shelled crab,vein spiderling,lupine gnawer,impling"),
            route_point(
                5,
                786637,
                723034,
                4722,
                "wood-eater",
                "wood-eater worker,hill person,young grendelorm,wood-eater hunter,vein spider,huldu hunter,huldu stalker,small hill cat",
                teleport_destination="Mularn",
            ),
            route_point(
                6,
                786637,
                723034,
                4722,
                "wood-eater worker",
                "hill person,young grendelorm,vein spider,huldu hunter,huldu stalker,small hill cat,young lynx,green serpent,lupine snarler,young sveawolf",
                teleport_destination="Mularn",
            ),
            route_point(
                7,
                787192,
                868637,
                6698,
                "carrion crawler",
                "wood-eater worker,wood-eater hunter,vein spider,huldu stalker,army ant worker,young grendelorm,black mauler juvenile,sveawolf mother",
                teleport_destination="Gotar",
            ),
            route_point(
                8,
                719301,
                770132,
                4506,
                "army ant worker",
                "tawny lynx,carrion crawler,vein spider,black mauler juvenile,young grendelorm,sveawolf mother",
                teleport_destination="Audliten",
            ),
            route_point(
                10,
                809316,
                678732,
                5003,
                "young grendelorm",
                "wolf spiderling,hill person,huldu stalker,small hill cat",
                teleport_destination="Fort Veldon",
            ),
            route_point(15, 736792, 836202, 5159, teleport_destination="Fort Veldon"),
            route_point(20, 783734, 797071, 5282, teleport_destination="Audliten"),
            route_point(25, 779270, 829104, 4856, teleport_destination="Huginfell"),
            route_point(30, 733576, 760848, 5342, teleport_destination="Fort Atla"),
            route_point(35, 709212, 769221, 5283, teleport_destination="Gna Faste"),
            route_point(40, 681918, 728644, 5595, teleport_destination="Vindsaul Faste"),
            route_point(45, 674302, 736960, 5227, teleport_destination="Raumarik"),
            route_point(
                50,
                742631,
                668137,
                7887,
                "savage wyvern",
                "winter wolf,fallen troll,fenrir shredder",
                teleport_destination="Svasud Faste",
            ),
        ),
        ground_z_map="tools/pathing/heightmaps/region100_client_zones.json",
        startup_service_npc_name="Aud",
    ),
    "hib": RealmProfile(
        key="hib",
        realm_id=3,
        region=200,
        prefix="growthhib",
        character_prefix="GrowthHib",
        class_cycle="44|43|45|48|47|47|40|41",
        race_cycle="9|9|9|9|9|9|11|11",
        spec_cycle=(
            "Blades|50;Shields|42;Parry|39;Large Weapons|1;Celtic Spear|1||"
            "Blades|50;Celtic Dual|50;Parry|28;Shields|1||"
            "Large Weapons|50;Valor|40;Parry|23;Shields|1;Blades|1||"
            "Music|43;Nurture|37;Regrowth|33;Blades|1||"
            "Regrowth|40;Nurture|36;Nature|1||"
            "Regrowth|40;Nurture|36;Nature|1||"
            "Light|50;Mana|15;Void|10||"
            "Mana|50;Enchantments|20;Light|1"
        ),
        growth_class_cycle="44|47|43|43|48|40|41|47",
        growth_race_cycle="9|9|9|9|9|11|11|9",
        growth_spec_cycle=(
            "Blades|50;Shields|42;Parry|39;Large Weapons|1;Celtic Spear|1||"
            "Regrowth|40;Nurture|36;Nature|1||"
            "Blades|50;Celtic Dual|50;Parry|28;Shields|1||"
            "Blades|50;Celtic Dual|50;Parry|28;Shields|1||"
            "Music|43;Nurture|37;Regrowth|33;Blades|1||"
            "Light|50;Mana|15;Void|10||"
            "Mana|50;Enchantments|20;Light|1||"
            "Regrowth|40;Nurture|36;Nature|1"
        ),
        start=(344500, 474500, 5372),
        points=(
            route_point(1, 344500, 474500, 5372, "badger cub,large frog,annoying lucradan", "water beetle larva,skeletal pawn,feccan,ambient,Lance Settler,lunantishee,blackthorn"),
            route_point(2, 345100, 474178, 5473, "badger cub,large frog,annoying lucradan", "water beetle larva,skeletal pawn,feccan,ambient,Lance Settler,lunantishee,blackthorn"),
            route_point(3, 345100, 474178, 5473, "badger cub,large frog,annoying lucradan", "water beetle larva,skeletal pawn,mudman,villainous youth,feccan,ambient,Lance Settler,lunantishee,blackthorn"),
            route_point(4, 345935, 470831, 6032, "skeletal pawn", "water beetle larva,mudman,feccan,ambient,Lance Settler,lunantishee,blackthorn", teleport_destination="Mag Mell"),
            route_point(5, 348637, 479175, 5742, "mudman", "feccan,lough wolf,wild crouch,water beetle,eirebug,spraggon,villainous youth"),
            route_point(6, 348637, 479175, 5742, "mudman", "skeletal minion,lough wolf,wild crouch,water beetle,water beetle collector,eirebug,spraggon,villainous youth,feccan"),
            route_point(8, 309663, 647096, 5234, "hill toad", teleport_destination="Shannon Estuary"),
            route_point(10, 350899, 531716, 3637, "water beetle", "water beetle collector", teleport_destination="Tir na mBeo"),
            route_point(15, 339898, 516372, 5410, teleport_destination="Tir na mBeo"),
            route_point(20, 344391, 564431, 5739, teleport_destination="Ardagh"),
            route_point(25, 343316, 522184, 5174, teleport_destination="Howth"),
            route_point(30, 344511, 546390, 5249, teleport_destination="Connla"),
            route_point(35, 335203, 518049, 4450, teleport_destination="Innis Carthaig"),
            route_point(40, 370138, 573183, 4407, teleport_destination="Druim Cain"),
            route_point(45, 399161, 507683, 4546, teleport_destination="Cursed Forest"),
            route_point(
                50,
                332526,
                733763,
                4750,
                "far darrig",
                "melancholic fairy,dullahan",
                teleport_destination="Innis Carthaig",
            ),
        ),
        ground_z_map="tools/pathing/heightmaps/region200_client_zones.json",
        startup_service_npc_name="Ionhar",
    ),
}


LEVEL_ONE_PARTY_ROUTE_VARIANTS: dict[str, dict[int, RoutePoint]] = {
    "alb": {
        1: route_point(1, 533085, 478620, 2200, "green snake", "young cutpurse,weak skeleton,small gray wolf,black wolf pup,boar piglet"),
        2: route_point(1, 533085, 478620, 2200, "green snake,boar piglet", "young cutpurse,weak skeleton,small gray wolf,black wolf pup"),
        4: route_point(1, 534520, 477220, 2200, "boar piglet,black wolf pup,green snake", "young cutpurse,weak skeleton,small gray wolf"),
        8: route_point(1, 534650, 477500, 2200, "black wolf pup", "young cutpurse,weak skeleton,green snake,small gray wolf"),
    },
    "mid": {
        1: route_point(1, 770900, 746700, 4620, "lupine gnawer", "young sveawolf,soft-shelled crab,vein spiderling,lupine snarler"),
        2: route_point(1, 773538, 749971, 4552, "vein spiderling,wildling,mud snake,tawny lynx cub", "young sveawolf,soft-shelled crab,sveawolf cub,lupine gnawer,lupine snarler"),
        4: route_point(1, 774968, 748210, 4695, "tawny lynx cub", "young sveawolf,soft-shelled crab,sveawolf cub,lupine gnawer,lupine snarler,vein spiderling,mud snake,wildling"),
        8: route_point(1, 776800, 752135, 4595, "sveawolf cub", "soft-shelled crab,vein spiderling,lupine gnawer,lupine snarler"),
    },
    "hib": {
        1: route_point(1, 344500, 474500, 5372, "badger cub,large frog,annoying lucradan", "water beetle larva,skeletal pawn,feccan,ambient,Lance Settler,lunantishee,blackthorn"),
        2: route_point(1, 344500, 474500, 5372, "annoying lucradan,badger cub,large frog", "water beetle larva,skeletal pawn,feccan,ambient,Lance Settler,lunantishee,blackthorn"),
        4: route_point(1, 344500, 474500, 5372, "annoying lucradan,badger cub,large frog", "water beetle larva,skeletal pawn,feccan,ambient,Lance Settler,lunantishee,blackthorn"),
        8: route_point(1, 344888, 589665, 5101, "water beetle larva", "large frog,skeletal pawn,badger cub,feccan,annoying lucradan,ambient,Lance Settler,lunantishee,blackthorn", "Howth"),
    },
}


LOW_PARTY_CARRY_ROUTE_VARIANTS: dict[str, dict[int, dict[int, RoutePoint]]] = {
    "alb": {
        2: {
            4: route_point(
                2,
                534900,
                478900,
                2310,
                "small gray wolf,black wolf pup,boar piglet",
                "young cutpurse,green snake,weak skeleton,adder",
            ),
        },
    },
}


LEVEL_FOUR_PARTY_ROUTE_VARIANTS: dict[str, dict[int, RoutePoint]] = {
    "mid": {
        2: route_point(
            5,
            788300,
            723100,
            4672,
            "wood-eater",
            "wood-eater worker,hill person,young grendelorm,wood-eater hunter,vein spider,huldu hunter,huldu stalker,small hill cat,young lynx,green serpent,lupine snarler,young sveawolf",
            teleport_destination="Mularn",
        ),
        4: route_point(
            5,
            786637,
            723034,
            4722,
            "wood-eater worker,wood-eater",
            "hill person,young grendelorm,wood-eater hunter,vein spider,huldu hunter,huldu stalker,small hill cat,young lynx,green serpent,lupine snarler,young sveawolf",
            teleport_destination="Mularn",
        ),
        8: route_point(
            5,
            786637,
            723034,
            4722,
            "wood-eater worker,wood-eater",
            "hill person,young grendelorm,wood-eater hunter,vein spider,huldu hunter,huldu stalker,small hill cat,young lynx,green serpent,lupine snarler,young sveawolf",
            teleport_destination="Mularn",
        ),
    },
}


LEVEL_TEN_PARTY_ROUTE_VARIANTS: dict[str, dict[int, RoutePoint]] = {
    "alb": {
        2: route_point(
            10,
            496426,
            593548,
            1904,
            "giant spider",
            "tree spirit,shady pilferer,spriggarn stalker,skeleton,rot worm,emerald snake,faerie bell-wether,young cutpurse",
            teleport_destination="Campacorentin Station",
        ),
        4: route_point(10, 511763, 615379, 1779, "wild boar", "brownie,river sprite,bandit", teleport_destination="Caer Ulfwych"),
        8: route_point(10, 511763, 615379, 1779, "wild boar", "brownie,river sprite,bandit", teleport_destination="Caer Ulfwych"),
    },
    "mid": {
        2: mid_level_ten_tawny_lynx_party_route(),
        4: mid_level_ten_hobgoblin_party_route(),
        8: mid_level_ten_hobgoblin_party_route(),
    },
    "hib": {
        2: route_point(10, 336157, 532604, 5556, "lough wolf", "wild lucradan,red wolfhound,badger,hazard,blackthorn,feccan", teleport_destination="Tir na mBeo"),
        4: route_point(10, 336157, 532604, 5556, "lough wolf", "wild lucradan,red wolfhound,badger,hazard,blackthorn,feccan", teleport_destination="Tir na mBeo"),
        8: route_point(10, 336157, 532604, 5556, "lough wolf", "wild lucradan,red wolfhound,badger,hazard,blackthorn,feccan", teleport_destination="Tir na mBeo"),
    },
}


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_csv_list(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[,;]", value) if part.strip()]


def parse_int_list(value: str) -> list[int]:
    return [int(part) for part in parse_csv_list(value)]


def parse_slot_list(value: str) -> list[int]:
    slots: list[int] = []
    for part in parse_csv_list(value):
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            start = int(start_text)
            end = int(end_text)
            if end < start:
                raise ValueError(f"invalid slot range: {part}")
            slots.extend(range(start, end + 1))
        else:
            slots.append(int(part))
    return slots


def sql_quote(value: str | None) -> str:
    if value is None:
        return "NULL"
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def sql_literal(value: str | None) -> str:
    if value is None:
        return "NULL"
    text = str(value)
    if text.upper() == "NULL":
        return "NULL"
    return sql_quote(text)


def sql_identifier(name: str) -> str:
    return "`" + name.replace("`", "``") + "`"


def resolve_mysql_bin(value: str | None) -> str:
    if value:
        return value
    if os.name == "nt":
        for binary in ("mariadb", "mysql"):
            found = shutil.which(binary)
            if found:
                return found
        for candidate in DEFAULT_WINDOWS_MYSQL_CANDIDATES:
            if Path(candidate).exists():
                return candidate
    for candidate in DEFAULT_MYSQL_CANDIDATES:
        if Path(candidate).exists():
            return candidate
    for binary in ("mariadb", "mysql"):
        found = shutil.which(binary)
        if found:
            return found
    return DEFAULT_MYSQL_CANDIDATES[0]


def read_serverconfig_password() -> str:
    config_path = ROOT / "CoreServer" / "config" / "serverconfig.xml"
    if not config_path.exists():
        return "opendaoc-local"
    text = config_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"Password=([^;]+)", text)
    return match.group(1) if match else "opendaoc-local"


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

    cwd = os.getcwd()
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
        return subprocess.run(command, check=True, capture_output=True, text=True, env=env).stdout
    finally:
        if defaults_file:
            Path(defaults_file).unlink(missing_ok=True)


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


def to_int(value: object) -> int:
    if value is None:
        return 0
    text = str(value).strip()
    if text == "" or text.upper() == "NULL":
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def money_to_copper(row: dict[str, str]) -> int:
    return (
        to_int(row.get("Copper"))
        + to_int(row.get("Silver")) * COPPER_PER_SILVER
        + to_int(row.get("Gold")) * COPPER_PER_GOLD
        + to_int(row.get("Platinum")) * COPPER_PER_PLATINUM
    )


def coin_parts_from_copper(total_copper: int) -> tuple[int, int, int, int]:
    remaining = max(0, int(total_copper or 0))
    platinum, remaining = divmod(remaining, COPPER_PER_PLATINUM)
    gold, remaining = divmod(remaining, COPPER_PER_GOLD)
    silver, copper = divmod(remaining, COPPER_PER_SILVER)
    return copper, silver, gold, platinum


def checkpoint_seed_money_copper(args: argparse.Namespace, level: int, party_size: int, realm_key: str = "") -> int:
    raw_configured = getattr(args, "checkpoint_seed_copper", -1)
    configured = -1 if raw_configured is None else int(raw_configured)
    if configured >= 0:
        return configured
    if int(party_size or 0) <= 1 and int(level or 0) == 10 and realm_key == "alb":
        return 100
    return 0


def read_accounts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_accounts(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    if not fieldnames:
        fieldnames = ["username", "password", "realm", "char_index"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def checkpoint_account_segment_count(checkpoint_levels: list[int], max_segments: int) -> int:
    return 1


def select_segment_account_rows(
    account_rows: list[dict[str, str]],
    *,
    party_size: int,
    watcher_count: int,
    segment_ordinal: int,
    account_segments: int,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    rows_per_segment = party_size + watcher_count
    if rows_per_segment <= 0:
        return [], []
    start = max(0, int(segment_ordinal)) * rows_per_segment if account_segments > 1 else 0
    end = start + rows_per_segment
    if len(account_rows) < end:
        raise ValueError(
            f"not enough account rows for segment {segment_ordinal + 1}: "
            f"need {end}, have {len(account_rows)}"
        )
    rows = account_rows[start:end]
    return rows[:party_size], rows[party_size : party_size + watcher_count]


def character_name_from_account(account: str) -> str:
    normalized = str(account or "").strip()
    lowered = normalized.lower()
    for prefix, character_prefix in (
        ("growthalb", "GrowthAlb"),
        ("growthmid", "GrowthMid"),
        ("growthhib", "GrowthHib"),
        ("dummy", "Dummy"),
    ):
        if lowered.startswith(prefix):
            return character_prefix + normalized[len(prefix) :]
    return normalized[:1].upper() + normalized[1:]


def watcher_character_name(account: str) -> str:
    return "\uac10\uc2dc\uc790" + character_name_from_account(account)


def experience_floor_for_level(level: int) -> int:
    level_index = max(1, min(int(level), len(XP_FOR_LEVEL))) - 1
    return XP_FOR_LEVEL[level_index]


def snapshot_characters(args: argparse.Namespace, accounts: Iterable[str]) -> dict[str, CharacterSnapshot]:
    account_names = [account for account in accounts if account]
    if not account_names:
        return {}
    quoted = ", ".join(sql_quote(account) for account in account_names)
    sql = f"""
        SELECT
            c.AccountName,
            c.Name,
            c.DOLCharacters_ID,
            c.Level,
            c.Experience,
            c.Realm,
            c.Class,
            c.SerializedSpecs,
            c.SerializedAbilities,
            c.Region,
            c.Xpos,
            c.Ypos,
            c.Zpos,
            c.DeathCount,
            c.Copper,
            c.Silver,
            c.Gold,
            c.Platinum,
            COUNT(inv.OwnerID) AS InventoryRows,
            COALESCE(SUM(inv.Count), 0) AS InventoryItems
        FROM DOLCharacters c
        LEFT JOIN inventory inv ON inv.OwnerID = c.DOLCharacters_ID
        WHERE c.AccountName IN ({quoted})
        GROUP BY
            c.AccountName,
            c.Name,
            c.DOLCharacters_ID,
            c.Level,
            c.Experience,
            c.Realm,
            c.Class,
            c.SerializedSpecs,
            c.SerializedAbilities,
            c.Region,
            c.Xpos,
            c.Ypos,
            c.Zpos,
            c.DeathCount,
            c.Copper,
            c.Silver,
            c.Gold,
            c.Platinum
        ORDER BY c.AccountName;
    """
    rows = parse_mysql_rows(run_mysql(args, sql))
    snapshots: dict[str, CharacterSnapshot] = {}
    for row in rows:
        account = row.get("AccountName", "")
        snapshots[account] = CharacterSnapshot(
            account=account,
            name=row.get("Name", ""),
            character_id=row.get("DOLCharacters_ID", ""),
            level=to_int(row.get("Level")),
            experience=to_int(row.get("Experience")),
            realm=to_int(row.get("Realm")),
            class_id=to_int(row.get("Class")),
            specs=row.get("SerializedSpecs", ""),
            serialized_abilities=row.get("SerializedAbilities", ""),
            region=to_int(row.get("Region")),
            x=to_int(row.get("Xpos")),
            y=to_int(row.get("Ypos")),
            z=to_int(row.get("Zpos")),
            deaths=to_int(row.get("DeathCount")),
            money_copper=money_to_copper(row),
            inventory_rows=to_int(row.get("InventoryRows")),
            inventory_items=to_int(row.get("InventoryItems")),
        )
    return snapshots


def class_allows_item(allowed_classes: str | None, class_id: int) -> bool:
    text = (allowed_classes or "").strip()
    if not text or text == "0":
        return True
    return str(class_id) in {part.strip() for part in re.split(r"[,;]", text) if part.strip()}


def parse_serialized_ability_levels(serialized_abilities: str | None) -> dict[str, int]:
    levels: dict[str, int] = {}
    for entry in re.split(r"[;,]", serialized_abilities or ""):
        if "|" not in entry:
            continue
        name, level_text = entry.rsplit("|", 1)
        name = name.strip()
        if not name:
            continue
        try:
            levels[name] = int(level_text.strip() or "0")
        except ValueError:
            levels[name] = 0
    return levels


def item_armor_required_ability_level(object_type: int) -> int | None:
    return ARMOR_REQUIRED_ABILITY_LEVEL_BY_OBJECT_TYPE.get(int(object_type or 0))


def armor_ability_level_for_item(
    *,
    serialized_abilities: str | None,
    item_realm: int,
    character_realm: int,
) -> int | None:
    if not (serialized_abilities or "").strip():
        return None

    levels = parse_serialized_ability_levels(serialized_abilities)
    realm_id = int(item_realm or 0)
    if realm_id <= 0:
        realm_id = int(character_realm or 0)

    ability_name = ARMOR_ABILITY_BY_REALM.get(realm_id)
    if ability_name:
        return int(levels.get(ability_name, 0) or 0)
    return max((int(levels.get(name, 0) or 0) for name in ARMOR_ABILITY_BY_REALM.values()), default=0)


def class_can_wear_armor_item(
    item: InventoryItem | MerchantItemCandidate,
    *,
    realm_id: int,
    serialized_abilities: str | None = "",
) -> bool:
    required_level = item_armor_required_ability_level(item.object_type)
    if required_level is None:
        return True

    ability_level = armor_ability_level_for_item(
        serialized_abilities=serialized_abilities,
        item_realm=getattr(item, "realm", 0),
        character_realm=realm_id,
    )
    if ability_level is None:
        return True
    return ability_level >= required_level


def class_can_use_growth_equipment_item(
    item: InventoryItem | MerchantItemCandidate,
    *,
    realm_id: int,
    serialized_abilities: str | None = "",
) -> bool:
    if not (serialized_abilities or "").strip():
        return True

    object_type = int(getattr(item, "object_type", 0) or 0)
    if object_type == SHIELD_OBJECT_TYPE:
        levels = parse_serialized_ability_levels(serialized_abilities)
        return int(levels.get("Shield", 0) or 0) >= max(0, int(getattr(item, "type_damage", 0) or 0))
    if ARMOR_OBJECT_TYPE_MIN <= object_type <= ARMOR_OBJECT_TYPE_MAX:
        return class_can_wear_armor_item(
            item,
            realm_id=realm_id,
            serialized_abilities=serialized_abilities,
        )
    if object_type in (0, 1, 31, 41):
        return True

    required_abilities = WEAPON_ABILITY_NAMES_BY_OBJECT_TYPE.get(object_type)
    if required_abilities is None:
        return not (2 <= object_type <= 28 or object_type in {43, 44, 45, 46})

    levels = parse_serialized_ability_levels(serialized_abilities)
    return any(name in levels for name in required_abilities)


def item_target_slot(item: InventoryItem) -> int | None:
    if item.item_type not in EQUIPMENT_SLOTS or item.object_type <= 0:
        return None
    return item.item_type


def is_backpack_slot(slot: int) -> bool:
    return BACKPACK_FIRST_SLOT <= slot <= BACKPACK_LAST_SLOT


def is_armor_or_shield(item: InventoryItem) -> bool:
    return ARMOR_OBJECT_TYPE_MIN <= item.object_type <= ARMOR_OBJECT_TYPE_MAX or item.object_type == SHIELD_OBJECT_TYPE


def is_weapon_item(item: InventoryItem) -> bool:
    target_slot = item_target_slot(item)
    return (
        target_slot in WEAPON_EQUIPMENT_SLOTS
        and 1 <= int(item.object_type) < ARMOR_OBJECT_TYPE_MIN
        and int(item.dps_af or 0) > 0
    )


def is_growth_auto_equip_safe(item: InventoryItem) -> bool:
    return is_armor_or_shield(item) or is_weapon_item(item)


def is_offhand_weapon_item(item: InventoryItem) -> bool:
    return item_target_slot(item) == OFFHAND_WEAPON_SLOT and is_weapon_item(item)


def class_can_auto_equip_offhand_weapon(
    item: InventoryItem,
    *,
    class_id: int,
    serialized_abilities: str = "",
) -> bool:
    if not is_offhand_weapon_item(item):
        return True
    if int(class_id or 0) in OFFHAND_WEAPON_CLASS_IDS:
        return True
    ability_names = {name.strip().lower() for name in parse_serialized_ability_levels(serialized_abilities)}
    return any(token in ability_name for ability_name in ability_names for token in OFFHAND_WEAPON_ABILITY_TOKENS)


def weapon_matches_trained_growth_spec(item: InventoryItem, specs: str = "") -> bool:
    if not is_weapon_item(item):
        return True
    parsed_specs = parse_specs(specs)
    if not parsed_specs:
        return True
    expected_specs = WEAPON_SPEC_NAMES_BY_OBJECT_TYPE.get(int(item.object_type or 0))
    if not expected_specs:
        return False
    return any(int(parsed_specs.get(spec_name, 0) or 0) > 1 for spec_name in expected_specs)


def inventory_item_category(item: InventoryItem) -> str:
    if is_armor_or_shield(item):
        return "armor"
    if 1 <= int(item.object_type) < ARMOR_OBJECT_TYPE_MIN:
        return "weapon"
    if item_target_slot(item) is not None:
        return "equipment_other"
    return "junk"


def inventory_category_summary(items: list[InventoryItem]) -> dict[str, int]:
    summary = {
        "weapon_items": 0,
        "armor_items": 0,
        "equipment_other_items": 0,
        "junk_items": 0,
        "zero_value_junk_items": 0,
        "sellable_junk_items": 0,
        "sellable_junk_value_copper": 0,
        "total_sell_value_copper": 0,
    }
    for item in items:
        count = max(1, int(item.count or 0))
        category = inventory_item_category(item)
        if category == "weapon":
            summary["weapon_items"] += count
        elif category == "armor":
            summary["armor_items"] += count
        elif category == "equipment_other":
            summary["equipment_other_items"] += count
        else:
            summary["junk_items"] += count
            if int(item.sell_price or 0) <= 0:
                summary["zero_value_junk_items"] += count
            else:
                summary["sellable_junk_items"] += count
                summary["sellable_junk_value_copper"] += max(0, int(item.sell_price or 0)) * count
        summary["total_sell_value_copper"] += max(0, int(item.sell_price or 0)) * count
    return summary


def inventory_category_delta(before_items: list[InventoryItem], after_items: list[InventoryItem]) -> dict[str, int]:
    before = inventory_category_summary(before_items)
    after = inventory_category_summary(after_items)
    delta: dict[str, int] = {}
    for key in before:
        delta[f"{key}_before"] = before[key]
        delta[f"{key}_after"] = after[key]
        delta[f"{key}_delta"] = after[key] - before[key]
    return delta


def write_segment_inventory_csv(path: Path, items_by_account: dict[str, list[InventoryItem]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "account",
        "slot",
        "container",
        "category",
        "template_id",
        "name",
        "level",
        "count",
        "sell_price_copper",
        "total_sell_value_copper",
        "object_type",
        "type_damage",
        "item_type",
        "quality",
        "bonus",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for account, items in sorted(items_by_account.items()):
            for item in sorted(items, key=lambda candidate: candidate.slot):
                count = max(1, int(item.count or 0))
                writer.writerow(
                    {
                        "account": account,
                        "slot": item.slot,
                        "container": "equipped" if item.slot in EQUIPMENT_SLOTS else "backpack",
                        "category": inventory_item_category(item),
                        "template_id": item.template_id,
                        "name": item.name,
                        "level": item.level,
                        "count": count,
                        "sell_price_copper": item.sell_price,
                        "total_sell_value_copper": max(0, int(item.sell_price or 0)) * count,
                        "object_type": item.object_type,
                        "type_damage": item.type_damage,
                        "item_type": item.item_type,
                        "quality": item.quality,
                        "bonus": item.bonus,
                    }
                )


def item_score(item: InventoryItem) -> int:
    stat = max(0, item.dps_af)
    quality = max(0, item.quality)
    bonus = max(0, item.bonus)
    level = max(0, item.level)
    if is_armor_or_shield(item):
        return stat * 1000 + quality * 10 + bonus * 25 + level
    speed_bonus = max(0, 100 - item.spd_abs)
    return stat * 1000 + quality * 10 + bonus * 30 + level + speed_bonus


def build_growth_item_plan(
    items: list[InventoryItem],
    *,
    class_id: int,
    level: int,
    realm_id: int = 0,
    serialized_abilities: str = "",
    specs: str = "",
) -> GrowthItemPlan:
    equipped_by_slot: dict[int, InventoryItem] = {
        item.slot: item for item in items if item.slot in EQUIPMENT_SLOTS
    }
    equip_slots: list[int] = []
    sell_slots: list[int] = []
    equip_reasons: list[str] = []
    sell_reasons: list[str] = []

    def add_sell_candidate(item: InventoryItem, reason: str) -> None:
        if int(item.sell_price or 0) > 0:
            sell_slots.append(item.slot)
            sell_reasons.append(f"{item.slot}:{item.name}:{reason}")
        else:
            sell_reasons.append(f"{item.slot}:{item.name}:{reason}_zero_value_hold")

    for item in sorted((candidate for candidate in items if is_backpack_slot(candidate.slot)), key=lambda candidate: candidate.slot):
        target_slot = item_target_slot(item)
        if target_slot is None:
            if item.sell_price > 0:
                sell_slots.append(item.slot)
                sell_reasons.append(f"{item.slot}:{item.name}:junk")
            continue
        if int(realm_id or 0) > 0 and int(item.realm or 0) not in (0, int(realm_id or 0)):
            add_sell_candidate(item, "realm")
            continue
        if not class_allows_item(item.allowed_classes, class_id):
            add_sell_candidate(item, "class")
            continue
        if not class_can_wear_armor_item(item, realm_id=realm_id, serialized_abilities=serialized_abilities):
            add_sell_candidate(item, "armor_ability")
            continue
        if not class_can_use_growth_equipment_item(
            item,
            realm_id=realm_id,
            serialized_abilities=serialized_abilities,
        ):
            add_sell_candidate(item, "equipment_ability")
            continue
        if not class_can_auto_equip_offhand_weapon(
            item,
            class_id=class_id,
            serialized_abilities=serialized_abilities,
        ):
            add_sell_candidate(item, "offhand_ability")
            continue
        if not weapon_matches_trained_growth_spec(item, specs):
            add_sell_candidate(item, "weapon_spec")
            continue
        if item.level > max(1, level):
            continue
        if not is_growth_auto_equip_safe(item):
            sell_reasons.append(f"{item.slot}:{item.name}:manual_equipment_check")
            continue
        equipped = equipped_by_slot.get(target_slot)
        equipped_score = item_score(equipped) if equipped else 0
        candidate_score = item_score(item)
        if candidate_score > equipped_score:
            equip_slots.append(item.slot)
            equip_reasons.append(f"{item.slot}->{target_slot}:{candidate_score}>{equipped_score}")
            equipped_by_slot[target_slot] = item
        elif candidate_score <= equipped_score:
            add_sell_candidate(item, "worse")

    return GrowthItemPlan(
        equip_slots=sorted(set(equip_slots)),
        sell_slots=sorted(set(sell_slots) - set(equip_slots)),
        party_share_slots=[],
        equip_reason=";".join(equip_reasons),
        sell_reason=";".join(sell_reasons),
        party_share_reason="",
    )


def copy_growth_item_plan(
    plan: GrowthItemPlan,
    *,
    merchant_npc_name: str | None = None,
    sell_slots: list[int] | None = None,
    buy_slots: list[int] | None = None,
    buy_inventory_slots: list[int] | None = None,
    buy_reason: str | None = None,
    buy_shortage_copper: int | None = None,
    sell_reason: str | None = None,
    party_share_slots: list[int] | None = None,
    party_share_transfers: list[GrowthPartyShareTransfer] | None = None,
    party_share_executed_slots: list[int] | None = None,
    party_share_received_slots: list[int] | None = None,
    party_share_failed_slots: list[int] | None = None,
    party_share_reason: str | None = None,
    party_share_execution_reason: str | None = None,
    equip_slots: list[int] | None = None,
    equip_reason: str | None = None,
) -> GrowthItemPlan:
    return GrowthItemPlan(
        equip_slots=list(plan.equip_slots if equip_slots is None else equip_slots),
        sell_slots=list(plan.sell_slots if sell_slots is None else sell_slots),
        party_share_slots=list(plan.party_share_slots if party_share_slots is None else party_share_slots),
        party_share_transfers=list(
            plan.party_share_transfers if party_share_transfers is None else party_share_transfers
        ),
        party_share_executed_slots=list(
            plan.party_share_executed_slots
            if party_share_executed_slots is None
            else party_share_executed_slots
        ),
        party_share_received_slots=list(
            plan.party_share_received_slots
            if party_share_received_slots is None
            else party_share_received_slots
        ),
        party_share_failed_slots=list(
            plan.party_share_failed_slots if party_share_failed_slots is None else party_share_failed_slots
        ),
        equip_reason=plan.equip_reason if equip_reason is None else equip_reason,
        sell_reason=plan.sell_reason if sell_reason is None else sell_reason,
        party_share_reason=plan.party_share_reason if party_share_reason is None else party_share_reason,
        party_share_execution_reason=(
            plan.party_share_execution_reason
            if party_share_execution_reason is None
            else party_share_execution_reason
        ),
        merchant_npc_name=plan.merchant_npc_name if merchant_npc_name is None else merchant_npc_name,
        buy_slots=list(plan.buy_slots if buy_slots is None else buy_slots),
        buy_inventory_slots=list(plan.buy_inventory_slots if buy_inventory_slots is None else buy_inventory_slots),
        buy_reason=plan.buy_reason if buy_reason is None else buy_reason,
        buy_shortage_copper=plan.buy_shortage_copper if buy_shortage_copper is None else buy_shortage_copper,
    )


def append_reason(existing: str, addition: str) -> str:
    if not addition:
        return existing
    return f"{existing};{addition}" if existing else addition


def growth_item_upgrade_for_snapshot(
    item: InventoryItem,
    equipped_items: list[InventoryItem],
    snapshot: CharacterSnapshot,
    *,
    realm_id: int = 0,
) -> tuple[int, int, int] | None:
    target_slot = item_target_slot(item)
    if target_slot is None:
        return None
    character_realm = int(realm_id or snapshot.realm or 0)
    if character_realm > 0 and int(item.realm or 0) not in (0, character_realm):
        return None
    if not class_allows_item(item.allowed_classes, snapshot.class_id):
        return None
    if not class_can_wear_armor_item(
        item,
        realm_id=character_realm,
        serialized_abilities=snapshot.serialized_abilities,
    ):
        return None
    if not class_can_use_growth_equipment_item(
        item,
        realm_id=character_realm,
        serialized_abilities=snapshot.serialized_abilities,
    ):
        return None
    if not class_can_auto_equip_offhand_weapon(
        item,
        class_id=snapshot.class_id,
        serialized_abilities=snapshot.serialized_abilities,
    ):
        return None
    if not weapon_matches_trained_growth_spec(item, snapshot.specs):
        return None
    if item.level > max(1, snapshot.level):
        return None
    if not is_growth_auto_equip_safe(item):
        return None
    equipped_by_slot = {equipped.slot: equipped for equipped in equipped_items if equipped.slot in EQUIPMENT_SLOTS}
    equipped = equipped_by_slot.get(target_slot)
    equipped_score = item_score(equipped) if equipped else 0
    candidate_score = item_score(item)
    if candidate_score <= equipped_score:
        return None
    return target_slot, candidate_score, equipped_score


def first_free_backpack_slot(items: list[InventoryItem], reserved_slots: set[int] | None = None) -> int | None:
    reserved = {int(slot) for slot in reserved_slots or set()}
    occupied = {
        item.slot
        for item in items
        if BACKPACK_FIRST_SLOT <= int(item.slot or 0) <= BACKPACK_LAST_SLOT
    }
    for slot in range(BACKPACK_FIRST_SLOT, BACKPACK_LAST_SLOT + 1):
        if slot not in occupied and slot not in reserved:
            return slot
    return None


def apply_party_share_growth_item_plans(
    inventory_by_account: dict[str, list[InventoryItem]],
    snapshots: dict[str, CharacterSnapshot],
    plans: dict[str, GrowthItemPlan],
    *,
    realm_id: int = 0,
) -> dict[str, GrowthItemPlan]:
    if len(snapshots) <= 1:
        return plans
    updated: dict[str, GrowthItemPlan] = dict(plans)
    reserved_target_slots: dict[str, set[int]] = {account: set() for account in snapshots}
    for source_account, items in inventory_by_account.items():
        source_plan = updated.get(source_account)
        if source_plan is None:
            continue
        share_slots = list(source_plan.party_share_slots)
        share_transfers = list(source_plan.party_share_transfers)
        share_reasons = [source_plan.party_share_reason] if source_plan.party_share_reason else []
        for item in sorted((candidate for candidate in items if is_backpack_slot(candidate.slot)), key=lambda candidate: candidate.slot):
            if item.slot in source_plan.equip_slots or item.slot in share_slots:
                continue
            best: tuple[int, str, int, int, int] | None = None
            for target_account, snapshot in snapshots.items():
                if target_account == source_account:
                    continue
                upgrade = growth_item_upgrade_for_snapshot(
                    item,
                    inventory_by_account.get(target_account, []),
                    snapshot,
                    realm_id=realm_id or snapshot.realm,
                )
                if upgrade is None:
                    continue
                target_slot, candidate_score, equipped_score = upgrade
                improvement = candidate_score - equipped_score
                if best is None or improvement > best[0]:
                    best = (improvement, target_account, target_slot, candidate_score, equipped_score)
            if best is None:
                continue
            _improvement, target_account, target_slot, candidate_score, equipped_score = best
            destination_slot = first_free_backpack_slot(
                inventory_by_account.get(target_account, []),
                reserved_target_slots.get(target_account, set()),
            )
            if destination_slot is None:
                share_reasons.append(f"{item.slot}:{item.name}->no_free_slot:{target_account}")
                continue
            reserved_target_slots.setdefault(target_account, set()).add(destination_slot)
            share_slots.append(item.slot)
            share_transfers.append(
                GrowthPartyShareTransfer(
                    source_account=source_account,
                    source_slot=item.slot,
                    target_account=target_account,
                    target_slot=destination_slot,
                    target_equip_slot=target_slot,
                    item_name=item.name,
                    candidate_score=candidate_score,
                    equipped_score=equipped_score,
                )
            )
            share_reasons.append(
                f"{item.slot}:{item.name}->{target_account}:{destination_slot}->{target_slot}:score={candidate_score}>{equipped_score}"
            )
        if share_slots:
            new_sell_slots = [slot for slot in source_plan.sell_slots if slot not in set(share_slots)]
            buy_reason = source_plan.buy_reason
            if buy_reason == "party_merchant_routing_pending" and not new_sell_slots:
                buy_reason = "party_share_candidate_held"
            updated[source_account] = copy_growth_item_plan(
                source_plan,
                sell_slots=new_sell_slots,
                sell_reason=append_reason(source_plan.sell_reason, "party_share_candidates_held"),
                buy_reason=buy_reason,
                party_share_slots=sorted(set(share_slots)),
                party_share_transfers=share_transfers,
                party_share_reason=";".join(reason for reason in share_reasons if reason),
            )
    return updated


def estimated_growth_sell_value(items: list[InventoryItem], sell_slots: list[int], sell_ratio_percent: int) -> int:
    sell_slot_set = set(sell_slots)
    ratio = max(0, int(sell_ratio_percent))
    total = 0
    for item in items:
        if item.slot in sell_slot_set and item.sell_price > 0:
            total += item.sell_price * max(1, item.count) * ratio // 100
    return total


def predicted_purchase_inventory_slot(items: list[InventoryItem], sell_slots: list[int]) -> int | None:
    occupied = {item.slot for item in items if BACKPACK_FIRST_SLOT <= item.slot <= BACKPACK_LAST_SLOT}
    reusable = {slot for slot in sell_slots if BACKPACK_FIRST_SLOT <= slot <= BACKPACK_LAST_SLOT}
    for slot in range(BACKPACK_FIRST_SLOT, BACKPACK_LAST_SLOT + 1):
        if slot not in occupied or slot in reusable:
            return slot
    return None


def growth_merchant_search_point(
    args: argparse.Namespace,
    realm: RealmProfile,
    snapshot: CharacterSnapshot,
    *,
    current_level: int,
    party_size: int,
) -> tuple[int, int, int]:
    start_location = str(getattr(args, "checkpoint_start_location", "realm-start") or "realm-start").strip().lower()
    fast_travel = str(getattr(args, "growth_fast_travel", "off") or "off").strip().lower()
    reset_level_ten_checkpoint = (
        int(current_level or 0) == 10
        and int(party_size or 0) == 1
        and int(getattr(args, "reset_level", 0) or 0) == 10
        and not [int(checkpoint) for checkpoint in getattr(args, "checkpoint_levels_parsed", []) or []]
    )
    if reset_level_ten_checkpoint and start_location in {"route-home", "teleport"}:
        return realm.start
    if fast_travel in {"route-home", "teleport"} and start_location in {"route-home", "teleport"}:
        return realm.start
    route = select_route_point(realm, current_level, party_size)
    teleport_destination = nearest_teleport_destination(realm, route) if current_level >= 10 else route.teleport_destination
    if teleport_destination and not skip_startup_teleport_for_checkpoint_start(args):
        destination = teleport_destination_point(realm, teleport_destination)
        if destination is not None:
            return destination
    if start_location in {"route-home", "teleport"}:
        point = checkpoint_start_point(args, realm, current_level, party_size)
        return point.x, point.y, point.z
    return realm.start


def query_growth_merchant_item_candidates(
    args: argparse.Namespace,
    realm: RealmProfile,
    *,
    x: int,
    y: int,
    level: int,
    max_distance: float,
) -> list[MerchantItemCandidate]:
    max_distance_squared = int(max(0.0, max_distance) ** 2)
    sql = f"""
        SELECT
            m.Name AS MerchantName,
            m.ItemsListTemplateID AS ItemListID,
            mi.PageNumber,
            mi.SlotPosition,
            it.Id_nb AS TemplateId,
            COALESCE(it.Name, '') AS ItemName,
            COALESCE(it.Level, 0) AS ItemLevel,
            COALESCE(it.DPS_AF, 0) AS DpsAf,
            COALESCE(it.SPD_ABS, 0) AS SpdAbs,
            COALESCE(it.Type_Damage, 0) AS TypeDamage,
            COALESCE(it.Object_Type, 0) AS ObjectType,
            COALESCE(it.Item_Type, 0) AS ItemType,
            COALESCE(it.Quality, 0) AS Quality,
            COALESCE(it.Bonus, 0) AS Bonus,
            COALESCE(it.Realm, 0) AS Realm,
            COALESCE(it.AllowedClasses, '') AS AllowedClasses,
            COALESCE(it.Price, 0) AS Price,
            ((m.X - {int(x)}) * (m.X - {int(x)}) + (m.Y - {int(y)}) * (m.Y - {int(y)})) AS DistanceSquared
        FROM mob m
        JOIN merchantitem mi ON mi.ItemListID = m.ItemsListTemplateID
        JOIN itemtemplate it ON it.Id_nb = mi.ItemTemplateID
        WHERE m.Region = {int(realm.region)}
          AND COALESCE(m.ItemsListTemplateID, '') <> ''
          AND COALESCE(m.Name, '') <> ''
          AND COALESCE(it.Price, 0) > 0
          AND COALESCE(it.Level, 0) <= {int(level)}
          AND (COALESCE(m.Realm, 0) IN (0, {int(realm.realm_id)}))
          AND (COALESCE(it.Realm, 0) IN (0, {int(realm.realm_id)}))
          AND ((m.X - {int(x)}) * (m.X - {int(x)}) + (m.Y - {int(y)}) * (m.Y - {int(y)})) <= {max_distance_squared}
        ORDER BY DistanceSquared ASC, COALESCE(it.Level, 0) DESC, COALESCE(it.Price, 0) ASC;
    """
    candidates: list[MerchantItemCandidate] = []
    for row in parse_mysql_rows(run_mysql(args, sql)):
        page = to_int(row.get("PageNumber"))
        slot = to_int(row.get("SlotPosition"))
        distance_squared = max(0, to_int(row.get("DistanceSquared")))
        candidates.append(
            MerchantItemCandidate(
                merchant_name=row.get("MerchantName", ""),
                item_list_id=row.get("ItemListID", ""),
                buy_slot=page * MERCHANT_WINDOW_SLOTS + slot,
                template_id=row.get("TemplateId", ""),
                name=row.get("ItemName", ""),
                level=to_int(row.get("ItemLevel")),
                dps_af=to_int(row.get("DpsAf")),
                spd_abs=to_int(row.get("SpdAbs")),
                type_damage=to_int(row.get("TypeDamage")),
                object_type=to_int(row.get("ObjectType")),
                item_type=to_int(row.get("ItemType")),
                quality=to_int(row.get("Quality")),
                bonus=to_int(row.get("Bonus")),
                allowed_classes=row.get("AllowedClasses", ""),
                price=to_int(row.get("Price")),
                distance=int(math.sqrt(distance_squared)),
                realm=to_int(row.get("Realm")),
            )
        )
    return candidates


def nearest_growth_merchant_name(
    args: argparse.Namespace,
    realm: RealmProfile,
    *,
    x: int,
    y: int,
    max_distance: float,
) -> str:
    max_distance_squared = int(max(0.0, max_distance) ** 2)
    sql = f"""
        SELECT
            m.Name AS MerchantName,
            ((m.X - {int(x)}) * (m.X - {int(x)}) + (m.Y - {int(y)}) * (m.Y - {int(y)})) AS DistanceSquared
        FROM mob m
        WHERE m.Region = {int(realm.region)}
          AND COALESCE(m.ItemsListTemplateID, '') <> ''
          AND COALESCE(m.Name, '') <> ''
          AND (COALESCE(m.Realm, 0) IN (0, {int(realm.realm_id)}))
          AND ((m.X - {int(x)}) * (m.X - {int(x)}) + (m.Y - {int(y)}) * (m.Y - {int(y)})) <= {max_distance_squared}
        ORDER BY DistanceSquared ASC
        LIMIT 1;
    """
    rows = parse_mysql_rows(run_mysql(args, sql))
    return rows[0].get("MerchantName", "") if rows else ""


def growth_merchant_npc_point(
    args: argparse.Namespace,
    realm: RealmProfile,
    merchant_name: str,
) -> RoutePoint | None:
    name = str(merchant_name or "").strip()
    if not name:
        return None
    sql = f"""
        SELECT Name, X, Y, Z
        FROM mob
        WHERE Region = {int(realm.region)}
          AND COALESCE(ItemsListTemplateID, '') <> ''
          AND Name = {sql_quote(name)}
        ORDER BY X ASC, Y ASC
        LIMIT 1;
    """
    rows = parse_mysql_rows(run_mysql(args, sql))
    if not rows:
        return None
    row = rows[0]
    return route_point(
        0,
        to_int(row.get("X")),
        to_int(row.get("Y")),
        to_int(row.get("Z")),
        "",
        "",
        "",
    )


def build_growth_merchant_item_plan(
    args: argparse.Namespace,
    realm: RealmProfile,
    snapshot: CharacterSnapshot,
    items: list[InventoryItem],
    plan: GrowthItemPlan,
    *,
    current_level: int,
    party_size: int,
) -> GrowthItemPlan:
    max_distance = float(getattr(args, "growth_merchant_max_distance", 8000.0) or 0.0)
    if int(current_level or 0) == 7 and str(getattr(args, "growth_stage", "") or "").strip().lower() == "gear":
        max_distance = max(max_distance, 20000.0)
    sell_ratio = int(getattr(args, "growth_merchant_sell_ratio_percent", 50) or 50)
    x, y, _z = growth_merchant_search_point(args, realm, snapshot, current_level=current_level, party_size=party_size)
    nearest_merchant = nearest_growth_merchant_name(args, realm, x=x, y=y, max_distance=max_distance)

    equipped_by_slot: dict[int, InventoryItem] = {
        item.slot: item for item in items if item.slot in EQUIPMENT_SLOTS
    }
    upgrade_rows: list[tuple[int, MerchantItemCandidate, int, int, int]] = []
    for candidate in query_growth_merchant_item_candidates(
        args,
        realm,
        x=x,
        y=y,
        level=max(1, current_level),
        max_distance=max_distance,
    ):
        target_slot = item_target_slot(candidate)  # type: ignore[arg-type]
        if target_slot is None:
            continue
        if not class_allows_item(candidate.allowed_classes, snapshot.class_id):
            continue
        if not class_can_wear_armor_item(
            candidate,  # type: ignore[arg-type]
            realm_id=snapshot.realm,
            serialized_abilities=snapshot.serialized_abilities,
        ):
            continue
        if not class_can_use_growth_equipment_item(
            candidate,  # type: ignore[arg-type]
            realm_id=snapshot.realm,
            serialized_abilities=snapshot.serialized_abilities,
        ):
            continue
        if not class_can_auto_equip_offhand_weapon(
            candidate,  # type: ignore[arg-type]
            class_id=snapshot.class_id,
            serialized_abilities=snapshot.serialized_abilities,
        ):
            continue
        if not weapon_matches_trained_growth_spec(candidate, snapshot.specs):  # type: ignore[arg-type]
            continue
        if not is_growth_auto_equip_safe(candidate):  # type: ignore[arg-type]
            continue
        equipped = equipped_by_slot.get(target_slot)
        equipped_score = item_score(equipped) if equipped else 0
        candidate_score = item_score(candidate)  # type: ignore[arg-type]
        improvement = candidate_score - equipped_score
        if improvement <= 0:
            continue
        upgrade_rows.append((improvement, candidate, target_slot, candidate_score, equipped_score))

    if not upgrade_rows:
        if plan.sell_slots and nearest_merchant:
            return copy_growth_item_plan(plan, merchant_npc_name=nearest_merchant, buy_reason="sell_only:no_safe_upgrade")
        if plan.sell_slots:
            return copy_growth_item_plan(
                plan,
                sell_reason=append_reason(plan.sell_reason, "merchant_missing"),
                buy_reason="no_safe_upgrade",
            )
        return copy_growth_item_plan(plan, buy_reason="no_safe_upgrade")

    sell_value = estimated_growth_sell_value(items, plan.sell_slots, sell_ratio)
    estimated_copper = snapshot.money_copper + sell_value
    predicted_slot = predicted_purchase_inventory_slot(items, plan.sell_slots)
    if predicted_slot is None:
        merchant = nearest_merchant or upgrade_rows[0][1].merchant_name
        return copy_growth_item_plan(plan, merchant_npc_name=merchant, buy_reason="no_inventory_space")

    affordable = [row for row in upgrade_rows if row[1].price <= estimated_copper]
    if not affordable:
        shortage_row = min(upgrade_rows, key=lambda row: max(0, row[1].price - estimated_copper))
        _improvement, candidate, target_slot, candidate_score, equipped_score = shortage_row
        missing = max(0, candidate.price - estimated_copper)
        reason = (
            f"shortage:{candidate.name}:merchant={candidate.merchant_name}:target_slot={target_slot}:"
            f"price={candidate.price}:have_after_sell={estimated_copper}:missing={missing}:"
            f"score={candidate_score}>{equipped_score}"
        )
        return copy_growth_item_plan(
            plan,
            merchant_npc_name=nearest_merchant if plan.sell_slots else "",
            buy_reason=reason,
            buy_shortage_copper=missing,
        )

    affordable.sort(key=lambda row: (row[0], row[1].level, row[1].quality, -row[1].price), reverse=True)
    _improvement, candidate, target_slot, candidate_score, equipped_score = affordable[0]
    reason = (
        f"{candidate.buy_slot}:{candidate.name}:merchant={candidate.merchant_name}:target_slot={target_slot}:"
        f"price={candidate.price}:have_after_sell={estimated_copper}:score={candidate_score}>{equipped_score}"
    )
    return copy_growth_item_plan(
        plan,
        merchant_npc_name=candidate.merchant_name,
        buy_slots=[candidate.buy_slot],
        buy_inventory_slots=[predicted_slot],
        buy_reason=reason,
        buy_shortage_copper=0,
    )


def should_equip_growth_checkpoint_gear(
    args: argparse.Namespace,
    realm: RealmProfile,
    *,
    current_level: int,
    party_size: int,
) -> bool:
    if getattr(args, "dry_run", False):
        return False
    checkpoint_levels = [int(level) for level in getattr(args, "checkpoint_levels_parsed", []) or []]
    solo_level_seven_gear_stage = (
        str(getattr(args, "growth_stage", "") or "").strip().lower() == "gear"
        and int(current_level or 0) == 7
    )
    solo_level_ten_reset_checkpoint = (
        int(current_level or 0) == 10
        and int(getattr(args, "reset_level", 0) or 0) == 10
        and not checkpoint_levels
    )
    return (
        realm.key in {"alb", "mid", "hib"}
        and int(party_size or 0) == 1
        and (
            (int(current_level or 0) in {6, 10} and int(current_level or 0) in checkpoint_levels)
            or solo_level_seven_gear_stage
            or solo_level_ten_reset_checkpoint
        )
    )


def growth_checkpoint_gear_search_point(
    args: argparse.Namespace,
    realm: RealmProfile,
    snapshot: CharacterSnapshot,
    *,
    current_level: int,
    party_size: int,
) -> tuple[int, int, int]:
    if int(current_level or 0) == 7 and str(getattr(args, "growth_stage", "") or "").strip().lower() == "gear":
        return realm.start
    return growth_merchant_search_point(args, realm, snapshot, current_level=current_level, party_size=party_size)


def equip_growth_checkpoint_gear(
    args: argparse.Namespace,
    realm: RealmProfile,
    snapshots: dict[str, CharacterSnapshot],
    inventory_items: dict[str, list[InventoryItem]],
    *,
    current_level: int,
    party_size: int,
) -> int:
    if not should_equip_growth_checkpoint_gear(args, realm, current_level=current_level, party_size=party_size):
        return 0

    updates: list[str] = []
    max_distance = float(getattr(args, "growth_merchant_max_distance", 8000.0) or 0.0)
    if int(current_level or 0) == 7 and str(getattr(args, "growth_stage", "") or "").strip().lower() == "gear":
        max_distance = max(max_distance, 30000.0)
    if (
        int(current_level or 0) == 10
        and int(party_size or 0) == 1
        and (
            int(current_level or 0) in [int(checkpoint) for checkpoint in getattr(args, "checkpoint_levels_parsed", []) or []]
            or (
                int(getattr(args, "reset_level", 0) or 0) == 10
                and not [int(checkpoint) for checkpoint in getattr(args, "checkpoint_levels_parsed", []) or []]
            )
        )
    ):
        max_distance = max(max_distance, 30000.0)
    for account, snapshot in snapshots.items():
        items = inventory_items.get(account, [])
        equipment_snapshot = growth_checkpoint_equipment_snapshot(
            snapshot,
            realm,
            current_level=current_level,
        )
        x, y, _z = growth_checkpoint_gear_search_point(
            args,
            realm,
            snapshot,
            current_level=current_level,
            party_size=party_size,
        )
        best_by_slot: dict[int, tuple[int, InventoryItem]] = {}
        for candidate in query_growth_merchant_item_candidates(
            args,
            realm,
            x=x,
            y=y,
            level=max(1, int(current_level or 1)),
            max_distance=max_distance,
        ):
            target_slot = item_target_slot(candidate)  # type: ignore[arg-type]
            if target_slot is None:
                continue
            candidate_item = merchant_candidate_inventory_item(account, candidate, target_slot)
            upgrade = growth_item_upgrade_for_snapshot(
                candidate_item,
                items,
                equipment_snapshot,
                realm_id=realm.realm_id,
            )
            if upgrade is None:
                continue
            slot, candidate_score, equipped_score = upgrade
            improvement = candidate_score - equipped_score
            current = best_by_slot.get(slot)
            if current is None or improvement > current[0]:
                best_by_slot[slot] = (improvement, candidate_item)

        for slot, (_improvement, item) in sorted(best_by_slot.items()):
            updates.append(
                replace_equipped_inventory_template_sql(
                    account,
                    slot,
                    item.template_id,
                    "run-dummy-growth-suite.py:checkpoint-gear",
                )
            )

    if updates:
        run_mysql(args, "\n".join(updates))
    return len(updates)


def snapshot_inventory_items(args: argparse.Namespace, accounts: Iterable[str]) -> dict[str, list[InventoryItem]]:
    account_names = [account for account in accounts if account]
    if not account_names:
        return {}
    quoted = ", ".join(sql_quote(account) for account in account_names)
    sql = f"""
        SELECT
            c.AccountName,
            inv.SlotPosition,
            COALESCE(inv.UTemplate_Id, inv.ITemplate_Id, '') AS TemplateId,
            COALESCE(iu.Name, it.Name, '') AS ItemName,
            COALESCE(iu.Level, it.Level, 0) AS ItemLevel,
            COALESCE(iu.DPS_AF, it.DPS_AF, 0) AS DpsAf,
            COALESCE(iu.SPD_ABS, it.SPD_ABS, 0) AS SpdAbs,
            COALESCE(iu.Type_Damage, it.Type_Damage, 0) AS TypeDamage,
            COALESCE(iu.Object_Type, it.Object_Type, 0) AS ObjectType,
            COALESCE(iu.Item_Type, it.Item_Type, 0) AS ItemType,
            COALESCE(iu.Quality, it.Quality, 0) AS Quality,
            COALESCE(iu.Bonus, it.Bonus, 0) AS Bonus,
            COALESCE(iu.AllowedClasses, it.AllowedClasses, '') AS AllowedClasses,
            COALESCE(iu.Realm, it.Realm, 0) AS Realm,
            COALESCE(inv.Count, 1) AS ItemCount,
            COALESCE(NULLIF(inv.SellPrice, 0), NULLIF(iu.Price, 0), NULLIF(it.Price, 0), 0) AS SellPrice
        FROM DOLCharacters c
        JOIN inventory inv ON inv.OwnerID = c.DOLCharacters_ID
        LEFT JOIN itemtemplate it ON it.Id_nb = inv.ITemplate_Id
        LEFT JOIN itemunique iu ON iu.Id_nb = inv.UTemplate_Id
        WHERE c.AccountName IN ({quoted})
          AND inv.SlotPosition IN ({','.join(str(slot) for slot in sorted(EQUIPMENT_SLOTS | set(range(BACKPACK_FIRST_SLOT, BACKPACK_LAST_SLOT + 1))))})
        ORDER BY c.AccountName, inv.SlotPosition;
    """
    rows = parse_mysql_rows(run_mysql(args, sql))
    by_account: dict[str, list[InventoryItem]] = {account: [] for account in account_names}
    for row in rows:
        account = row.get("AccountName", "")
        by_account.setdefault(account, []).append(
            InventoryItem(
                account=account,
                slot=to_int(row.get("SlotPosition")),
                template_id=row.get("TemplateId", ""),
                name=row.get("ItemName", ""),
                level=to_int(row.get("ItemLevel")),
                dps_af=to_int(row.get("DpsAf")),
                spd_abs=to_int(row.get("SpdAbs")),
                type_damage=to_int(row.get("TypeDamage")),
                object_type=to_int(row.get("ObjectType")),
                item_type=to_int(row.get("ItemType")),
                quality=to_int(row.get("Quality")),
                bonus=to_int(row.get("Bonus")),
                allowed_classes=row.get("AllowedClasses", ""),
                count=to_int(row.get("ItemCount")),
                sell_price=to_int(row.get("SellPrice")),
                realm=to_int(row.get("Realm")),
            )
        )
    return by_account


def table_columns(args: argparse.Namespace, table_name: str) -> list[str]:
    rows = parse_mysql_rows(run_mysql(args, f"SHOW COLUMNS FROM {sql_identifier(table_name)};"))
    return [row.get("Field", "") for row in rows if row.get("Field")]


def snapshot_segment_db_restore_state(args: argparse.Namespace, accounts: Iterable[str]) -> SegmentDbRestoreState:
    account_names = [account for account in accounts if account]
    if not account_names:
        return SegmentDbRestoreState([], [], [])
    quoted_accounts = ", ".join(sql_quote(account) for account in account_names)
    dol_columns = set(table_columns(args, "DOLCharacters"))
    character_columns = [
        column
        for column in (
            "DOLCharacters_ID",
            "AccountName",
            "Name",
            "Level",
            "Experience",
            "Realm",
            "Class",
            "SerializedSpecs",
            "Region",
            "Xpos",
            "Ypos",
            "Zpos",
            "BindRegion",
            "BindXpos",
            "BindYpos",
            "BindZpos",
            "DeathCount",
            "Copper",
            "Silver",
            "Gold",
            "Platinum",
            "Health",
            "Mana",
            "Endurance",
            "MaxEndurance",
            "GainXP",
            "PlayedTimeSinceLevel",
        )
        if column in dol_columns
    ]
    character_rows = parse_mysql_rows(
        run_mysql(
            args,
            f"""
            SELECT {', '.join(sql_identifier(column) for column in character_columns)}
            FROM DOLCharacters
            WHERE AccountName IN ({quoted_accounts})
            ORDER BY AccountName;
            """,
        )
    )
    owner_ids = [row.get("DOLCharacters_ID", "") for row in character_rows if row.get("DOLCharacters_ID")]
    inventory_columns = table_columns(args, "inventory")
    inventory_rows: list[dict[str, str]] = []
    if owner_ids and inventory_columns:
        quoted_owner_ids = ", ".join(sql_quote(owner_id) for owner_id in owner_ids)
        inventory_rows = parse_mysql_rows(
            run_mysql(
                args,
                f"""
                SELECT {', '.join(sql_identifier(column) for column in inventory_columns)}
                FROM inventory
                WHERE OwnerID IN ({quoted_owner_ids})
                ORDER BY OwnerID, SlotPosition;
                """,
            )
        )
    return SegmentDbRestoreState(character_rows, inventory_columns, inventory_rows)


def restore_segment_db_state(args: argparse.Namespace, state: SegmentDbRestoreState) -> None:
    if not state.character_rows:
        return
    owner_ids = [row.get("DOLCharacters_ID", "") for row in state.character_rows if row.get("DOLCharacters_ID")]
    statements: list[str] = []
    for row in state.character_rows:
        character_id = row.get("DOLCharacters_ID", "")
        if not character_id:
            continue
        assignments = [
            f"{sql_identifier(column)} = {sql_literal(row.get(column))}"
            for column in row
            if column not in {"DOLCharacters_ID", "AccountName"}
        ]
        if assignments:
            statements.append(
                "UPDATE DOLCharacters SET "
                + ", ".join(assignments)
                + f" WHERE DOLCharacters_ID = {sql_literal(character_id)};"
            )
    if owner_ids:
        quoted_owner_ids = ", ".join(sql_quote(owner_id) for owner_id in owner_ids)
        statements.append(f"DELETE FROM inventory WHERE OwnerID IN ({quoted_owner_ids});")
    if state.inventory_rows and state.inventory_columns:
        column_list = ", ".join(sql_identifier(column) for column in state.inventory_columns)
        values = []
        for row in state.inventory_rows:
            values.append(
                "(" + ", ".join(sql_literal(row.get(column)) for column in state.inventory_columns) + ")"
            )
        statements.append(f"INSERT INTO inventory ({column_list}) VALUES\n" + ",\n".join(values) + ";")
    if statements:
        run_mysql(args, "\n".join(statements))


def build_growth_item_plans(
    args: argparse.Namespace,
    accounts: Iterable[str],
    snapshots: dict[str, CharacterSnapshot],
    *,
    realm: RealmProfile | None = None,
    current_level: int = 0,
    party_size: int = 0,
) -> dict[str, GrowthItemPlan]:
    if args.dry_run:
        return {}
    inventory_by_account = snapshot_inventory_items(args, accounts)
    plans: dict[str, GrowthItemPlan] = {}
    for account, items in inventory_by_account.items():
        snapshot = snapshots.get(account)
        if snapshot is None:
            continue
        plan = build_growth_item_plan(
            items,
            class_id=snapshot.class_id,
            level=snapshot.level,
            realm_id=realm.realm_id if realm is not None else snapshot.realm,
            serialized_abilities=snapshot.serialized_abilities,
            specs=snapshot.specs,
        )
        if realm is not None and bool(getattr(args, "growth_auto_buy_merchant_gear", True)):
            plan = build_growth_merchant_item_plan(
                args,
                realm,
                snapshot,
                items,
                plan,
                current_level=current_level or snapshot.level,
                party_size=party_size,
            )
        plans[account] = plan
    if party_size > 1:
        plans = apply_party_share_growth_item_plans(
            inventory_by_account,
            snapshots,
            plans,
            realm_id=realm.realm_id if realm is not None else 0,
        )
    return plans


def write_party_share_transfers_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp_utc",
        "source_account",
        "source_character_id",
        "source_slot",
        "target_account",
        "target_character_id",
        "target_slot",
        "target_equip_slot",
        "item_name",
        "candidate_score",
        "equipped_score",
        "status",
        "reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def execute_growth_party_share_transfers(
    args: argparse.Namespace,
    plans: dict[str, GrowthItemPlan],
    snapshots: dict[str, CharacterSnapshot],
    output_path: Path,
) -> dict[str, GrowthItemPlan]:
    transfers = [
        transfer
        for plan in plans.values()
        for transfer in plan.party_share_transfers
    ]
    if args.dry_run or not transfers:
        return plans

    updated: dict[str, GrowthItemPlan] = dict(plans)
    event_rows: list[dict[str, object]] = []
    for transfer in transfers:
        source_plan = updated.get(transfer.source_account)
        if source_plan is None:
            continue
        source_snapshot = snapshots.get(transfer.source_account)
        target_snapshot = snapshots.get(transfer.target_account)
        status = "executed"
        reason = "db_transfer"
        if source_snapshot is None or target_snapshot is None:
            status = "skipped"
            reason = "missing_character_snapshot"
        elif not source_snapshot.character_id or not target_snapshot.character_id:
            status = "skipped"
            reason = "missing_character_id"
        else:
            run_mysql(
                args,
                f"""
                UPDATE inventory
                SET OwnerID = {sql_literal(target_snapshot.character_id)},
                    SlotPosition = {int(transfer.target_slot)}
                WHERE OwnerID = {sql_literal(source_snapshot.character_id)}
                  AND SlotPosition = {int(transfer.source_slot)}
                LIMIT 1;
                """,
            )

        event_rows.append(
            {
                "timestamp_utc": utc_now(),
                "source_account": transfer.source_account,
                "source_character_id": source_snapshot.character_id if source_snapshot else "",
                "source_slot": transfer.source_slot,
                "target_account": transfer.target_account,
                "target_character_id": target_snapshot.character_id if target_snapshot else "",
                "target_slot": transfer.target_slot,
                "target_equip_slot": transfer.target_equip_slot,
                "item_name": transfer.item_name,
                "candidate_score": transfer.candidate_score,
                "equipped_score": transfer.equipped_score,
                "status": status,
                "reason": reason,
            }
        )

        if status != "executed":
            updated[transfer.source_account] = copy_growth_item_plan(
                source_plan,
                party_share_failed_slots=sorted(
                    set(source_plan.party_share_failed_slots + [transfer.source_slot])
                ),
                party_share_execution_reason=append_reason(
                    source_plan.party_share_execution_reason,
                    f"{transfer.source_slot}:{reason}",
                ),
            )
            continue

        remaining_slots = [
            slot for slot in source_plan.party_share_slots if int(slot) != int(transfer.source_slot)
        ]
        remaining_transfers = [
            candidate
            for candidate in source_plan.party_share_transfers
            if int(candidate.source_slot) != int(transfer.source_slot)
        ]
        updated[transfer.source_account] = copy_growth_item_plan(
            source_plan,
            party_share_slots=remaining_slots,
            party_share_transfers=remaining_transfers,
            party_share_executed_slots=sorted(
                set(source_plan.party_share_executed_slots + [transfer.source_slot])
            ),
            party_share_execution_reason=append_reason(
                source_plan.party_share_execution_reason,
                f"{transfer.source_slot}->{transfer.target_account}:{transfer.target_slot}:db_transfer",
            ),
        )

        target_plan = updated.get(transfer.target_account, GrowthItemPlan([], []))
        buy_reason = target_plan.buy_reason
        buy_slots = target_plan.buy_slots
        buy_inventory_slots = target_plan.buy_inventory_slots
        buy_shortage_copper = target_plan.buy_shortage_copper
        if f"target_slot={transfer.target_equip_slot}" in buy_reason:
            buy_slots = []
            buy_inventory_slots = []
            buy_shortage_copper = 0
            buy_reason = append_reason(buy_reason, "satisfied_by_party_share")
        updated[transfer.target_account] = copy_growth_item_plan(
            target_plan,
            equip_slots=sorted(set(target_plan.equip_slots + [transfer.target_slot])),
            equip_reason=append_reason(
                target_plan.equip_reason,
                f"party_share_received:{transfer.target_slot}->{transfer.target_equip_slot}:"
                f"{transfer.source_account}:{transfer.source_slot}:"
                f"{transfer.candidate_score}>{transfer.equipped_score}",
            ),
            party_share_received_slots=sorted(
                set(target_plan.party_share_received_slots + [transfer.target_slot])
            ),
            buy_slots=buy_slots,
            buy_inventory_slots=buy_inventory_slots,
            buy_reason=buy_reason,
            buy_shortage_copper=buy_shortage_copper,
        )

    write_party_share_transfers_csv(output_path, event_rows)
    return updated


def union_plan_slots(plans: dict[str, GrowthItemPlan], attr: str, fallback: list[int] | None = None) -> list[int]:
    slots: set[int] = set()
    for plan in plans.values():
        slots.update(getattr(plan, attr))
    if not slots and fallback:
        slots.update(fallback)
    return sorted(slots)


def party_slot_by_account_from_rows(primary_rows: list[dict[str, str]], party_size: int) -> dict[str, int]:
    width = max(1, int(party_size or 1))
    return {
        row.get("username", ""): index % width
        for index, row in enumerate(primary_rows)
        if row.get("username")
    }


def party_slot_slot_maps(
    plans: dict[str, GrowthItemPlan],
    attr: str,
    party_slot_by_account: dict[str, int],
    *,
    merchant_name: str = "",
) -> list[str]:
    mappings: list[str] = []
    merchant_key = merchant_name.strip().lower()
    for account, plan in sorted(plans.items(), key=lambda item: party_slot_by_account.get(item[0], 9999)):
        if account not in party_slot_by_account:
            continue
        if merchant_key and str(plan.merchant_npc_name or "").strip().lower() != merchant_key:
            continue
        slots = sorted(set(getattr(plan, attr)))
        if not slots:
            continue
        mappings.append(
            f"{party_slot_by_account[account]}:" + ",".join(str(slot) for slot in slots)
        )
    return mappings


def first_growth_merchant_name(plans: dict[str, GrowthItemPlan]) -> str:
    return next((plan.merchant_npc_name for plan in plans.values() if plan.merchant_npc_name), "")


def append_repeated_values(command: list[str], flag: str, values: Iterable[str]) -> None:
    for value in values:
        if value:
            command.extend([flag, value])


def reset_growth_characters(
    args: argparse.Namespace,
    accounts: Iterable[str],
    level: int = 1,
    realm: RealmProfile | None = None,
    party_size: int = 0,
    target_specs_by_account: dict[str, str] | None = None,
    start_point: RoutePoint | None = None,
    reset_money: bool = True,
) -> None:
    account_names = [account for account in accounts if account]
    if not account_names:
        return
    quoted = ", ".join(sql_quote(account) for account in account_names)
    reset_level = max(1, level)
    reset_experience = experience_floor_for_level(reset_level)
    position_assignments = ""
    if realm is not None:
        effective_start_point = start_point or checkpoint_start_point(args, realm, reset_level, party_size)
        base_x, base_y, base_z = effective_start_point.x, effective_start_point.y, effective_start_point.z
        step = int(getattr(args, "position_step", 0) or 0)
        x_cases = " ".join(
            f"WHEN {sql_quote(account)} THEN {base_x + step * index}"
            for index, account in enumerate(account_names)
        )
        y_cases = " ".join(
            f"WHEN {sql_quote(account)} THEN {base_y + step * index}"
            for index, account in enumerate(account_names)
        )
        position_assignments = f"""
            Xpos = CASE AccountName {x_cases} ELSE Xpos END,
            Ypos = CASE AccountName {y_cases} ELSE Ypos END,
            Zpos = {base_z},
            Region = {realm.region},
            BindXpos = CASE AccountName {x_cases} ELSE BindXpos END,
            BindYpos = CASE AccountName {y_cases} ELSE BindYpos END,
            BindZpos = {base_z},
            BindRegion = {realm.region},
        """
    money_assignments = ""
    if reset_money:
        seed_copper = checkpoint_seed_money_copper(args, reset_level, party_size, realm.key if realm is not None else "")
        copper, silver, gold, platinum = coin_parts_from_copper(seed_copper)
        money_assignments = f"""
            Copper = {copper},
            Silver = {silver},
            Gold = {gold},
            Platinum = {platinum},
        """
    sql = f"""
        UPDATE DOLCharacters
        SET
            Level = {reset_level},
            Experience = {reset_experience},
            Health = 1000000,
            Mana = 1000000,
            MaxEndurance = GREATEST(MaxEndurance, 100),
            Endurance = 1000000,
            GainXP = 1,
            PlayedTimeSinceLevel = 0,
            DeathCount = 0,
            {money_assignments}
            {position_assignments}
            LastLevelUp = NOW()
        WHERE AccountName IN ({quoted});
    """
    run_mysql(args, sql)
    rows = parse_mysql_rows(
        run_mysql(
            args,
            f"""
            SELECT AccountName, SerializedSpecs
            FROM DOLCharacters
            WHERE AccountName IN ({quoted});
            """,
        )
    )
    updates: list[str] = []
    checkpoint_specs = (
        checkpoint_specs_by_account(account_names, realm, target_specs_by_account)
        if reset_level >= 50 or target_specs_by_account
        else {}
    )
    for row in rows:
        account = row.get("AccountName", "")
        specs = checkpoint_specs.get(account) or baseline_specs(row.get("SerializedSpecs", ""))
        if not account or not specs:
            continue
        updates.append(
            "UPDATE DOLCharacters "
            f"SET SerializedSpecs = {sql_quote(specs)} "
            f"WHERE AccountName = {sql_quote(account)};"
        )
    if updates:
        run_mysql(args, "\n".join(updates))


def rename_watcher_characters(args: argparse.Namespace, accounts: Iterable[str]) -> None:
    account_names = [account for account in accounts if account]
    if not account_names or getattr(args, "dry_run", False):
        return
    updates = [
        "UPDATE DOLCharacters "
        f"SET Name = {sql_quote(watcher_character_name(account))} "
        f"WHERE AccountName = {sql_quote(account)};"
        for account in account_names
    ]
    run_mysql(args, "\n".join(updates))


def select_route_point(realm: RealmProfile, level: int, party_size: int = 0) -> RoutePoint:
    if level <= 3 and party_size > 1:
        route = LOW_PARTY_CARRY_ROUTE_VARIANTS.get(realm.key, {}).get(level, {}).get(party_size)
        if route is not None:
            return route
    if level <= 1 and party_size > 0:
        route = LEVEL_ONE_PARTY_ROUTE_VARIANTS.get(realm.key, {}).get(party_size)
        if route is not None:
            return route
    if level == 4 and party_size > 1:
        route = LEVEL_FOUR_PARTY_ROUTE_VARIANTS.get(realm.key, {}).get(party_size)
        if route is not None:
            return route
    if level == 10 and party_size > 1:
        route = LEVEL_TEN_PARTY_ROUTE_VARIANTS.get(realm.key, {}).get(party_size)
        if route is not None:
            return route
    selected = realm.points[0]
    for point in realm.points:
        if level >= point.level:
            selected = point
        else:
            break
    return selected


def load_growth_hunting_index(args: argparse.Namespace) -> dict[tuple[str, int, int], list[RoutePoint]]:
    cached = getattr(args, "_growth_hunting_index_cache", None)
    if cached is not None:
        return cached
    index: dict[tuple[str, int, int], list[RoutePoint]] = {}
    path_text = str(getattr(args, "growth_hunting_index", "") or "").strip()
    if not path_text:
        setattr(args, "_growth_hunting_index_cache", index)
        return index
    path = Path(path_text)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        raise FileNotFoundError(f"growth hunting index not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            realm_key = str(row.get("realm", "") or "").strip().lower()
            level = to_int(row.get("player_level"))
            party_size = to_int(row.get("party_size"))
            if not realm_key or level <= 0:
                continue
            destination = str(row.get("nearest_teleporter", "") or "").strip()
            if destination.lower() == "bind start":
                destination = ""
            teleporter_distance = to_int(row.get("teleporter_distance"))
            mob_level = to_int(row.get("mob_level"))
            route_home_fast_travel = str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
            if level <= 4 and teleporter_distance > 8000 and not route_home_fast_travel:
                continue
            mob_count = to_int(row.get("mob_count"))
            preferred_names = preferred_growth_hunting_candidates(realm_key, level, party_size)
            name = str(row.get("name", "") or "").strip()
            target_ideal = to_int(row.get("target_ideal"))
            if (
                uses_growth_party_carry_tuning(level, party_size)
                and target_ideal > 0
                and mob_level > target_ideal
            ):
                continue
            static_avoid_text = growth_hunting_index_avoid_targets(realm_key, level, party_size)
            failed_avoid_text = growth_failed_target_memory_avoid_targets(args, realm_key, level, party_size)
            avoid_text = merge_target_name_csv(
                static_avoid_text,
                failed_avoid_text,
            )
            if target_name_matches_any(name, preferred_target_tokens(failed_avoid_text)):
                continue
            if target_name_matches_any(name, preferred_target_tokens(static_avoid_text)) and not (
                growth_hunting_index_allows_static_avoid_candidate(
                    args,
                    realm_key=realm_key,
                    level=level,
                    party_size=party_size,
                    name=name,
                    mob_level=mob_level,
                    mob_count=mob_count,
                )
            ):
                continue
            if (
                level <= 4
                and party_size >= 4
                and mob_count < max(8, party_size * 3)
                and name.lower() not in {preferred.lower() for preferred in preferred_names}
            ):
                continue
            live_preflight_adjusted = to_bool(row.get("live_preflight_adjusted"))
            point = route_point(
                level,
                to_int(row.get("x")),
                to_int(row.get("y")),
                to_int(row.get("z")),
                name,
                avoid_text,
                destination,
                source="hunting-index",
                mob_level=mob_level,
                mob_count=mob_count,
                live_anchor_z=live_preflight_adjusted,
                startup_anchor=live_preflight_adjusted,
            )
            index.setdefault((realm_key, party_size, level), []).append(point)
    setattr(args, "_growth_hunting_index_cache", index)
    return index


def select_growth_hunting_index_point_for_target(
    args: argparse.Namespace,
    realm_key: str,
    target_level: int,
    party_size: int,
    caller_player_level: int | None = None,
    allow_player_reward_floor_fallback: bool = False,
) -> RoutePoint | None:
    path_text = str(getattr(args, "growth_hunting_index", "") or "").strip()
    if not path_text:
        return None
    cache = getattr(args, "_growth_hunting_target_index_cache", None)
    if cache is None:
        cache = {}
        path = Path(path_text)
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            raise FileNotFoundError(f"growth hunting index not found: {path}")
        with path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                row_realm = str(row.get("realm", "") or "").strip().lower()
                row_party_size = to_int(row.get("party_size"))
                row_player_level = to_int(row.get("player_level"))
                target_min = to_int(row.get("target_min"))
                target_max = to_int(row.get("target_max"))
                mob_level = to_int(row.get("mob_level"))
                if not row_realm or row_party_size <= 0 or row_player_level <= 0 or target_min <= 0 or target_max <= 0:
                    continue
                target_ideal = to_int(row.get("target_ideal"))
                if (
                    uses_growth_party_carry_tuning(row_player_level, row_party_size)
                    and target_ideal > 0
                    and mob_level > target_ideal
                ):
                    continue
                name = str(row.get("name", "") or "").strip()
                x = to_int(row.get("x"))
                y = to_int(row.get("y"))
                z = to_int(row.get("z"))
                mob_count = to_int(row.get("mob_count"))
                if (
                    row_realm == "mid"
                    and row_party_size == 4
                    and name.lower() == "tawny lynx"
                    and 760000 <= x <= 774000
                    and 833000 <= y <= 845000
                    and target_min <= 18 <= target_max
                ):
                    continue
                avoid_text = growth_hunting_index_avoid_targets(row_realm, row_player_level, row_party_size)
                if target_name_matches_any(name, preferred_target_tokens(avoid_text)) and not (
                    growth_hunting_index_allows_static_avoid_candidate(
                        args,
                        realm_key=row_realm,
                        level=row_player_level,
                        party_size=row_party_size,
                        name=name,
                        mob_level=mob_level,
                        mob_count=mob_count,
                    )
                ):
                    continue
                destination = str(row.get("nearest_teleporter", "") or "").strip()
                if destination.lower() == "bind start":
                    destination = ""
                live_preflight_adjusted = to_bool(row.get("live_preflight_adjusted"))
                point = route_point(
                    row_player_level,
                    x,
                    y,
                    z,
                    name,
                    avoid_text,
                    destination,
                    source="hunting-index",
                    mob_level=mob_level,
                    mob_count=mob_count,
                    live_anchor_z=live_preflight_adjusted,
                    startup_anchor=live_preflight_adjusted,
                )
                score = float(row.get("score") or 0.0)
                mob_count = to_int(row.get("mob_count"))
                dense_threshold = max(4, min(12, int(row_party_size or 0) * 3))
                if bool(getattr(args, "growth_route_level_is_carry_target", False)) or growth_party_uses_carry_tuning(
                    args,
                    int(getattr(args, "growth_target_level_override", 0) or row_player_level or 1),
                    row_party_size,
                ):
                    if int(row_party_size or 0) <= 2:
                        dense_threshold = max(dense_threshold, 10)
                    else:
                        dense_threshold = max(dense_threshold, 12)
                    if row_realm == "alb" and int(row_party_size or 0) >= 8 and row_player_level <= 7:
                        dense_threshold = min(dense_threshold, 10)
                sparse_rank = 0 if mob_count >= dense_threshold else 1
                for level in range(target_min, target_max + 1):
                    eligible_band = mob_level >= level and mob_level <= level + 3
                    cache.setdefault((row_realm, row_party_size, level), []).append(
                        (0 if eligible_band else 1, sparse_rank, -score, abs(mob_level - level), mob_level, point)
                    )
        for key, candidates in cache.items():
            candidates.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[5].prefer))
        setattr(args, "_growth_hunting_target_index_cache", cache)
    candidates = cache.get((realm_key, int(party_size or 0), int(target_level or 0)))
    if not candidates and int(party_size or 0) > 0:
        candidates = cache.get((realm_key, 0, int(target_level or 0)))
    carry_route_mode = (
        bool(getattr(args, "growth_route_level_is_carry_target", False))
        or growth_party_uses_carry_tuning(
            args,
            int(getattr(args, "growth_target_level_override", 0) or target_level or 1),
            int(party_size or 0),
        )
    ) and int(party_size or 0) > 1
    if not candidates and not carry_route_mode:
        return None
    caller_level_for_memory = int(caller_player_level if caller_player_level is not None else target_level or 0)
    caller_avoid_tokens = preferred_target_tokens(
        merge_target_name_csv(
            growth_hunting_index_avoid_targets(
                realm_key,
                caller_level_for_memory,
                int(party_size or 0),
            ),
            growth_failed_target_memory_avoid_targets(
                args,
                realm_key,
                caller_level_for_memory,
                int(party_size or 0),
            ),
        )
    )
    preferred_level = int(target_level or 0)
    if caller_player_level is not None and not carry_route_mode:
        preferred_level = int(caller_player_level or target_level or 0)
    allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
        getattr(args, "growth_allow_lower_xp_gear_farm", True)
    )
    target_plan_override = getattr(args, "growth_target_plan_override", None)
    prefer_lower_shortage_recovery = (
        allow_lower_xp_target_plan
        and isinstance(target_plan_override, (list, tuple))
        and len(target_plan_override) >= 2
        and 0 < int(target_plan_override[1] or 0) <= 5
    )
    if (
        allow_lower_xp_target_plan
        and not carry_route_mode
        and realm_key == "mid"
        and int(party_size or 0) <= 1
        and int(caller_level_for_memory or 0) == 7
    ):
        if prefer_lower_shortage_recovery:
            preferred_names = ("black mauler juvenile", "young grendelorm", "vein spider")
        else:
            preferred_names = ("carrion crawler", "young grendelorm", "vein spider")
    else:
        preferred_names = (
            preferred_growth_carry_hunting_candidates(realm_key, int(target_level or 0), int(party_size or 0))
            if carry_route_mode
            else ()
        ) or preferred_growth_hunting_candidates(realm_key, preferred_level, int(party_size or 0))
    preflight_realm = REALMS.get(realm_key)
    preflight_current_level = growth_route_preflight_policy_level(
        args,
        (target_level if carry_route_mode else caller_player_level)
        if (target_level if carry_route_mode else caller_player_level) is not None
        else target_level or 1,
        party_size,
    )
    max_candidate_mob_level: int | None = None
    if carry_route_mode and target_plan_override is not None:
        _, plan_ideal_target, plan_max_delta = target_plan_override
        command_player_level = int(getattr(args, "growth_target_level_override", 0) or target_level or 1)
        max_candidate_mob_level = growth_command_max_target_level(
            command_player_level,
            int(plan_ideal_target),
            int(plan_max_delta),
            int(party_size or 0),
        )
    if carry_route_mode:
        _plan_min, route_ideal_target, _plan_delta = growth_party_carry_target_plan_for_realm(
            int(getattr(args, "growth_route_player_level", 0) or target_level or 1),
            int(party_size or 0),
            realm_key,
        )
        if int(route_ideal_target or 0) > 0:
            if max_candidate_mob_level is None:
                max_candidate_mob_level = int(route_ideal_target)
            else:
                max_candidate_mob_level = min(int(max_candidate_mob_level), int(route_ideal_target))
    elif allow_lower_xp_target_plan and target_plan_override is not None:
        _, plan_ideal_target, plan_max_delta = target_plan_override
        command_player_level = int(
            getattr(args, "growth_target_level_override", 0)
            or caller_player_level
            or target_level
            or 1
        )
        max_candidate_mob_level = growth_command_max_target_level(
            command_player_level,
            int(plan_ideal_target),
            int(plan_max_delta),
            int(party_size or 0),
        )
    min_candidate_mob_level: int | None = None
    if caller_player_level is not None and not carry_route_mode:
        non_grey_floor = minimum_non_grey_target_level(
            int(
                getattr(args, "growth_shortage_recovery_player_level", 0)
                or caller_player_level
                or target_level
                or 1
            )
        )
        target_plan_override = getattr(args, "growth_target_plan_override", None)
        if allow_lower_xp_target_plan and target_plan_override is not None:
            min_candidate_mob_level = max(int(target_plan_override[0]), non_grey_floor)
        else:
            min_candidate_mob_level = minimum_growth_effective_target_level(
                int(caller_player_level or target_level or 1),
                int(party_size or 0),
                realm_key,
            )
            if non_grey_floor > 0:
                min_candidate_mob_level = max(min_candidate_mob_level, non_grey_floor)
    if carry_route_mode:
        carry_floor_player_level = int(getattr(args, "growth_target_level_override", 0) or target_level or 1)
        carry_reward_floor = growth_party_carry_reward_floor(
            args,
            carry_floor_player_level,
            int(party_size or 0),
            realm_key,
        )
        if carry_reward_floor > 0:
            min_candidate_mob_level = max(int(min_candidate_mob_level or 0), int(carry_reward_floor))
            carry_reward_ceiling = int(carry_reward_floor)
            max_candidate_mob_level = max(int(max_candidate_mob_level or 0), carry_reward_ceiling)
        player_reward_floor = 0
        if allow_player_reward_floor_fallback:
            player_floor_level = int(
                getattr(args, "growth_route_player_level", 0)
                or caller_player_level
                or getattr(args, "growth_target_level_override", 0)
                or target_level
                or 1
            )
            player_reward_floor = minimum_growth_effective_target_level(
                player_floor_level,
                int(party_size or 0),
                realm_key,
            )
            if player_reward_floor > 0:
                if min_candidate_mob_level is None:
                    min_candidate_mob_level = player_reward_floor
                elif int(getattr(args, "growth_route_player_level", 0) or 0) > 0:
                    min_candidate_mob_level = max(int(min_candidate_mob_level), int(player_reward_floor))
                else:
                    min_candidate_mob_level = min(int(min_candidate_mob_level), int(player_reward_floor))
    else:
        player_reward_floor = 0

    def select_from_candidates(
        route_candidates: list[tuple[int, int, float, int, int, RoutePoint]] | None,
        *,
        require_dense: bool,
        require_positive_dense: bool = False,
    ) -> RoutePoint | None:
        if not route_candidates:
            return None
        if max_candidate_mob_level is not None:
            route_candidates = [
                candidate for candidate in route_candidates if int(candidate[4] or 0) <= max_candidate_mob_level
            ]
            if not route_candidates:
                return None
        if min_candidate_mob_level is not None:
            route_candidates = [
                candidate for candidate in route_candidates if int(candidate[4] or 0) >= min_candidate_mob_level
            ]
            if not route_candidates:
                return None
        if caller_avoid_tokens:
            preferred_name_tokens = {name.strip().lower() for name in preferred_names if name.strip()}
            route_candidates = [
                candidate
                for candidate in route_candidates
                if not target_name_matches_any(candidate[5].prefer, caller_avoid_tokens)
                or (
                    carry_route_mode
                    and candidate[5].prefer.strip().lower() in preferred_name_tokens
                )
                or growth_hunting_index_allows_static_avoid_candidate(
                    args,
                    realm_key=realm_key,
                    level=caller_level_for_memory,
                    party_size=int(party_size or 0),
                    name=candidate[5].prefer,
                    mob_level=int(candidate[4] or 0),
                    mob_count=int(getattr(candidate[5], "mob_count", 0) or 0),
                )
                or growth_is_mid_solo_l7_shortage_black_mauler_candidate(
                    args,
                    realm_key=realm_key,
                    level=caller_level_for_memory,
                    party_size=int(party_size or 0),
                    name=candidate[5].prefer,
                    mob_level=int(candidate[4] or 0),
                    mob_count=int(getattr(candidate[5], "mob_count", 0) or 0),
                )
            ]
            if not route_candidates:
                return None
        if caller_player_level is not None and not carry_route_mode:
            caller_level = max(1, int(caller_player_level or 1))
            route_candidates = [
                candidate
                for candidate in route_candidates
                if int(candidate[5].level or 0) <= caller_level
            ]
            if not route_candidates:
                return None
        eligible_candidates = [candidate for candidate in route_candidates if candidate[0] == 0]
        dense_candidates = [candidate for candidate in eligible_candidates if candidate[1] == 0]
        if require_dense and not dense_candidates:
            return None
        positive_score_candidates = [candidate for candidate in dense_candidates if candidate[2] < 0]
        if require_positive_dense and not positive_score_candidates:
            return None
        route_pool = positive_score_candidates or dense_candidates or eligible_candidates or route_candidates
        if carry_route_mode:
            route_pool = sorted(
                route_pool,
                key=lambda candidate: (
                    int(candidate[3] or 0),
                    int(candidate[4] or 0),
                    int(candidate[1] or 0),
                    float(candidate[2] or 0.0),
                    str(candidate[5].prefer or ""),
                ),
            )
        def dedupe_candidates(
            candidate_pool: list[tuple[int, int, float, int, int, RoutePoint]],
        ) -> list[tuple[int, int, float, int, int, RoutePoint]]:
            deduped: list[tuple[int, int, float, int, int, RoutePoint]] = []
            seen_routes: set[tuple[int, int, int, str]] = set()
            for candidate in candidate_pool:
                point = candidate[5]
                route_key = (
                    int(point.x),
                    int(point.y),
                    int(point.z),
                    str(point.prefer or "").strip().lower(),
                )
                if route_key in seen_routes:
                    continue
                seen_routes.add(route_key)
                deduped.append(candidate)
            return deduped

        deduped_route_pool = dedupe_candidates(route_pool)
        if deduped_route_pool:
            route_pool = deduped_route_pool
        preferred_route_pool = route_pool
        if prefer_lower_shortage_recovery:
            preferred_route_pool = eligible_candidates or route_pool
        elif preferred_names and caller_player_level is not None and not carry_route_mode:
            preferred_route_pool = dense_candidates or eligible_candidates or route_pool
        if carry_route_mode and require_dense and int(party_size or 0) >= 4:
            preferred_limit = 3
            if realm_key == "hib" and int(party_size or 0) == 4 and int(target_level or 0) in {7, 8}:
                preferred_limit = 2
            if len(preferred_route_pool) > preferred_limit:
                preferred_route_pool = preferred_route_pool[:preferred_limit]
        if preferred_names:
            rotated_preferred_names = preferred_names
            keep_preferred_order = (
                allow_lower_xp_target_plan
                and realm_key == "mid"
                and int(party_size or 0) <= 1
                and int(caller_level_for_memory or 0) == 7
            ) or (
                realm_key == "hib"
                and int(party_size or 0) <= 1
                and int(caller_level_for_memory or target_level or 0) == 7
            )
            if not keep_preferred_order:
                rotated_preferred_names = rotate_growth_preferred_names(
                    args,
                    preferred_names,
                    realm_key=realm_key,
                    level=int(target_level or 0),
                    party_size=int(party_size or 0),
                )
            for preferred_name in rotated_preferred_names:
                preferred_pool = [
                    candidate
                    for candidate in preferred_route_pool
                    if candidate[5].prefer.strip().lower() == preferred_name.strip().lower()
                ]
                if (
                    allow_lower_xp_target_plan
                    and realm_key == "mid"
                    and int(party_size or 0) <= 1
                    and int(caller_level_for_memory or 0) == 7
                ):
                    low_density_pool = [
                        candidate
                        for candidate in preferred_pool
                        if 0 < int(getattr(candidate[5], "mob_count", 0) or 0) <= 12
                    ]
                    if low_density_pool:
                        preferred_pool = low_density_pool
                if preferred_pool and preflight_realm is not None:
                    preferred_pool = growth_route_preflight_filter_candidate_pool(
                        args,
                        preferred_pool,
                        realm=preflight_realm,
                        current_level=preflight_current_level,
                        party_size=int(party_size or 0),
                    )
                if preferred_pool:
                    return preferred_pool[
                        growth_route_selection_index(
                            args,
                            realm_key=realm_key,
                            level=int(target_level or 0),
                            party_size=int(party_size or 0),
                            modulo=len(preferred_pool),
                            salt=f"preferred-pool:{preferred_name.strip().lower()}",
                        )
                    ][5]
        if preflight_realm is not None:
            candidate_pools_to_preflight = [route_pool]
            if allow_player_reward_floor_fallback and carry_route_mode:
                for candidate_pool in (dense_candidates, eligible_candidates, route_candidates):
                    if not candidate_pool:
                        continue
                    deduped_pool = dedupe_candidates(candidate_pool)
                    if not deduped_pool or deduped_pool == route_pool:
                        continue
                    candidate_pools_to_preflight.append(deduped_pool)
            filtered_route_pool: list[tuple[int, int, float, int, int, RoutePoint]] = []
            for candidate_pool in candidate_pools_to_preflight:
                filtered_route_pool = growth_route_preflight_filter_candidate_pool(
                    args,
                    candidate_pool,
                    realm=preflight_realm,
                    current_level=preflight_current_level,
                    party_size=int(party_size or 0),
                )
                if filtered_route_pool:
                    break
            if not filtered_route_pool:
                return None
            route_pool = filtered_route_pool
        route_pool = route_pool[: min(len(route_pool), 3)]
        return route_pool[
            growth_route_selection_index(
                args,
                realm_key=realm_key,
                level=int(target_level or 0),
                party_size=int(party_size or 0),
                modulo=len(route_pool),
                salt="target-pool",
            )
        ][5]

    require_positive_carry_dense = carry_route_mode and int(party_size or 0) <= 2
    live_discovery_source_candidates: list[tuple[int, int, float, int, int, RoutePoint]] = list(candidates or [])
    selected = select_from_candidates(
        candidates,
        require_dense=carry_route_mode,
        require_positive_dense=require_positive_carry_dense,
    )
    if selected is not None:
        return selected
    if carry_route_mode:
        fallback_floor_level = max(1, int(target_level or 0) - 2)
        if allow_player_reward_floor_fallback and player_reward_floor > 0:
            fallback_floor_level = min(fallback_floor_level, int(player_reward_floor))
        for fallback_level in range(int(target_level or 0) - 1, fallback_floor_level - 1, -1):
            fallback_candidates = cache.get((realm_key, int(party_size or 0), fallback_level))
            if not fallback_candidates and int(party_size or 0) > 0:
                fallback_candidates = cache.get((realm_key, 0, fallback_level))
            if fallback_candidates:
                live_discovery_source_candidates.extend(fallback_candidates)
            selected = select_from_candidates(
                fallback_candidates,
                require_dense=True,
                require_positive_dense=require_positive_carry_dense,
            )
            if selected is not None:
                return selected
    selected = select_from_candidates(candidates, require_dense=False)
    if selected is not None:
        return selected
    if carry_route_mode and preflight_realm is not None:
        return select_live_growth_preflight_candidate_route(
            args,
            preflight_realm,
            live_discovery_source_candidates,
            realm_key=realm_key,
            target_level=int(target_level or 0),
            current_level=preflight_current_level,
            caller_level=caller_level_for_memory,
            party_size=int(party_size or 0),
        )
    return None


def growth_live_preflight_discovery_enabled(
    args: argparse.Namespace,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> bool:
    return bool(
        growth_route_preflight_enabled(args)
        and str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and bool(getattr(args, "growth_route_level_is_carry_target", False))
        and int(party_size or 0) > 1
        and int(current_level or 0) >= 5
        and str(realm_key or "").strip().lower() in REALMS
    )


def select_live_growth_preflight_candidate_route(
    args: argparse.Namespace,
    realm: RealmProfile,
    source_candidates: Iterable[tuple[int, int, float, int, int, RoutePoint]],
    *,
    realm_key: str,
    target_level: int,
    current_level: int,
    caller_level: int,
    party_size: int,
) -> RoutePoint | None:
    if not growth_live_preflight_discovery_enabled(
        args,
        realm_key=realm_key,
        current_level=current_level,
        party_size=party_size,
    ):
        return None
    endpoint = growth_route_preflight_endpoint(args)
    timeout = max(0.1, float(getattr(args, "growth_route_preflight_timeout", 1.5) or 1.5))
    _min_target, computed_ideal_target, _max_delta = growth_party_carry_target_plan_for_realm(
        current_level,
        party_size,
        realm_key,
    )
    ideal_target_level = int(computed_ideal_target or target_level or 0)
    target_plan_override = getattr(args, "growth_target_plan_override", None)
    if isinstance(target_plan_override, (list, tuple)) and len(target_plan_override) >= 2:
        ideal_target_level = int(target_plan_override[1] or ideal_target_level or 0)
    max_discovery_mob_level = ideal_target_level if ideal_target_level > 0 else 0
    source_routes: list[RoutePoint] = []
    seen_source_routes: set[tuple[int, int, int, str, int]] = set()
    for candidate in source_candidates:
        route = candidate[5]
        key = (
            int(route.x),
            int(route.y),
            int(route.z),
            str(route.prefer or "").strip().lower(),
            int(getattr(route, "mob_level", 0) or 0),
        )
        if key in seen_source_routes:
            continue
        seen_source_routes.add(key)
        if not growth_route_preflight_strict_required(
            args,
            route,
            current_level=current_level,
            party_size=party_size,
        ):
            continue
        if max_discovery_mob_level > 0 and int(getattr(route, "mob_level", 0) or 0) > max_discovery_mob_level:
            continue
        source_routes.append(route)
    if not source_routes:
        return None

    static_avoid_text = growth_hunting_index_avoid_targets(realm_key, caller_level, party_size)
    failed_avoid_text = growth_failed_target_memory_avoid_targets(args, realm_key, caller_level, party_size)
    avoid_text = merge_target_name_csv(
        "노련한,돌연변이,흉포한,우두머리,정예,챔피언",
        static_avoid_text,
        failed_avoid_text,
    )
    avoid_tokens = preferred_target_tokens(merge_target_name_csv(static_avoid_text, failed_avoid_text))
    discovered: list[tuple[int, int, float, int, int, RoutePoint]] = []
    seen_scan_keys: set[tuple[int, int, int, int, int]] = set()
    seen_live_routes: set[tuple[str, int, int, int]] = set()
    for source_route in source_routes:
        min_level, max_level = growth_route_preflight_level_band(
            args,
            source_route,
            realm_key=realm.key,
            current_level=current_level,
            party_size=party_size,
        )
        if max_level <= 0:
            continue
        scan_max_level = max_level
        if ideal_target_level > 0 and ideal_target_level >= min_level:
            scan_max_level = min(max_level, ideal_target_level)
        radius = max(
            12000,
            growth_route_preflight_radius(
                args,
                source_route,
                realm_key=realm.key,
                current_level=current_level,
                party_size=party_size,
            ),
        )
        query = {
            "region": int(realm.region),
            "x": int(source_route.x),
            "y": int(source_route.y),
            "radius": int(radius),
            "minLevel": int(min_level),
            "maxLevel": int(scan_max_level),
            "limit": 200,
        }
        nearby_avoid_names = growth_runtime_target_nearby_avoid_names_for_route(
            current_level,
            party_size,
            realm.key,
            source_route,
            allow_lower_xp_target_plan=bool(getattr(args, "growth_allow_lower_xp_target_plan", False))
            and bool(getattr(args, "growth_allow_lower_xp_gear_farm", True)),
        )
        nearby_avoid_radius = 1800 if nearby_avoid_names else 0
        if nearby_avoid_radius > 0 and nearby_avoid_names:
            query["nearbyRadius"] = nearby_avoid_radius
            query["nearbyAvoidName"] = nearby_avoid_names
        scan_key = (
            int(source_route.x),
            int(source_route.y),
            int(radius),
            int(min_level),
            int(scan_max_level),
            int(nearby_avoid_radius),
            nearby_avoid_names.lower(),
        )
        if scan_key in seen_scan_keys:
            continue
        seen_scan_keys.add(scan_key)
        url = f"{endpoint}?{urllib.parse.urlencode(query)}"
        payload = fetch_growth_route_preflight_payload(url, timeout)
        if payload is None:
            log_growth_route_preflight(
                args,
                realm_key=realm.key,
                current_level=current_level,
                party_size=party_size,
                route=source_route,
                status="unknown",
                reason=f"live_discovery_api_unavailable_or_error:level={min_level}-{scan_max_level}:radius={radius}",
                url=url,
            )
            continue
        items_by_name: dict[str, list[dict[str, object]]] = {}
        for item in growth_route_preflight_payload_items(payload):
            item_name = str(item.get("name", "") or "").strip()
            if not item_name or growth_route_preflight_name_has_growth_prefix(item_name):
                continue
            item_level = to_int(item.get("level"))
            if item_level < min_level or item_level > scan_max_level:
                continue
            if not growth_route_preflight_item_available(item):
                continue
            if nearby_avoid_radius > 0 and growth_route_preflight_item_nearby_avoid_count(item) > 0:
                continue
            if target_name_matches_any(item_name, avoid_tokens) and not growth_hunting_index_allows_static_avoid_candidate(
                args,
                realm_key=realm.key,
                level=caller_level,
                party_size=party_size,
                name=item_name,
                mob_level=item_level,
                mob_count=1,
            ):
                continue
            key = normalize_growth_target_name(item_name)
            items_by_name.setdefault(key, []).append(item)
        min_available_targets = growth_route_preflight_min_available_targets(
            args,
            source_route,
            realm_key=realm.key,
            current_level=current_level,
            party_size=party_size,
        )
        for name_key, items in items_by_name.items():
            if len(items) < min_available_targets:
                continue
            items.sort(key=lambda item: (float(item.get("distance", 0.0) or 0.0), to_int(item.get("objectId"))))
            logged_runtime_distance_mismatch = False
            for anchor in items:
                name = str(anchor.get("name", "") or name_key).strip()
                item_level = to_int(anchor.get("level"))
                if item_level <= 0:
                    item_level = min_level
                if max_discovery_mob_level > 0 and item_level > max_discovery_mob_level:
                    continue
                live_route = route_point(
                    source_route.level,
                    to_int(anchor.get("x")),
                    to_int(anchor.get("y")),
                    to_int(anchor.get("z")) or source_route.z,
                    name,
                    avoid_text,
                    source_route.teleport_destination,
                    source_route.objective_adds,
                    source="hunting-index",
                    mob_level=item_level,
                    mob_count=len(items),
                    live_anchor_z=True,
                )
                runtime_items = growth_route_preflight_runtime_distance_items(
                    args,
                    live_route,
                    items,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                )
                if len(runtime_items) < min_available_targets:
                    if not logged_runtime_distance_mismatch:
                        log_growth_route_preflight(
                            args,
                            realm_key=realm.key,
                            current_level=current_level,
                            party_size=party_size,
                            route=live_route,
                            status="skip",
                            reason=(
                                f"live_discovery_runtime_distance_mismatch:{name}:"
                                f"available={len(items)}:"
                                f"runtime={len(runtime_items)}:"
                                f"required={min_available_targets}:"
                                f"max={growth_max_target_distance(args, current_level, party_size, realm.key, live_route):.0f}:"
                                f"home={growth_target_home_max_distance(args, current_level, party_size, realm.key, live_route):.0f}:"
                                f"radius={radius}"
                            ),
                            url=url,
                        )
                        logged_runtime_distance_mismatch = True
                    continue
                route_key = (normalize_growth_target_name(name), to_int(anchor.get("x")), to_int(anchor.get("y")), item_level)
                if route_key in seen_live_routes:
                    continue
                seen_live_routes.add(route_key)
                level_distance = abs(item_level - max(min_level, min(scan_max_level, int(ideal_target_level or item_level))))
                live_route = replace(live_route, mob_count=len(runtime_items))
                discovered.append((0, 0, -float(len(runtime_items)), level_distance, item_level, live_route))
                break
    if not discovered:
        return None
    discovered.sort(key=lambda candidate: (candidate[3], candidate[4] > int(ideal_target_level or 0), candidate[2]))
    filtered = growth_route_preflight_filter_candidate_pool(
        args,
        discovered,
        realm=realm,
        current_level=current_level,
        party_size=party_size,
    )
    if not filtered:
        return None
    same_plane_candidates: list[tuple[int, int, float, int, int, RoutePoint]] = []
    z_delta_candidates: list[tuple[int, int, float, int, int, RoutePoint]] = []
    for candidate in filtered:
        route = candidate[5]
        mismatch = growth_live_discovery_startup_plane_mismatch(
            args,
            realm,
            route,
            current_level=current_level,
            party_size=party_size,
        )
        if mismatch is not None:
            log_growth_route_preflight(
                args,
                realm_key=realm.key,
                current_level=current_level,
                party_size=party_size,
                route=route,
                status="warn",
                reason=(
                    "live_discovery_startup_plane_delta:"
                    f"{route.prefer}:"
                    f"landing_z={mismatch.get('landing_z', 0)}:"
                    f"target_z={mismatch.get('target_z', 0)}:"
                    f"delta={mismatch.get('delta', 0)}:"
                    f"max={mismatch.get('max_delta', 0)}"
                ),
            )
            z_delta_candidates.append(candidate)
        else:
            same_plane_candidates.append(candidate)

    def filter_landing_pressure(
        candidates: list[tuple[int, int, float, int, int, RoutePoint]],
    ) -> list[tuple[int, int, float, int, int, RoutePoint]]:
        plane_filtered: list[tuple[int, int, float, int, int, RoutePoint]] = []
        for candidate in candidates:
            route = candidate[5]
            landing_pressure = growth_live_discovery_startup_landing_pressure(
                args,
                realm,
                route,
                endpoint=endpoint,
                timeout=timeout,
                current_level=current_level,
                party_size=party_size,
            )
            if landing_pressure is not None:
                reanchored_route = growth_live_discovery_reanchor_landing_pressure(
                    args,
                    realm,
                    route,
                    endpoint=endpoint,
                    timeout=timeout,
                    current_level=current_level,
                    party_size=party_size,
                )
                if reanchored_route is not None:
                    log_growth_route_preflight(
                        args,
                        realm_key=realm.key,
                        current_level=current_level,
                        party_size=party_size,
                        route=reanchored_route,
                        status="warn",
                        reason=(
                            "live_discovery_startup_landing_anchor_replaced:"
                            f"{route.prefer}:"
                            f"from={route.x},{route.y}:"
                            f"nearest={landing_pressure.get('nearest_name', '')}:"
                            f"distance={landing_pressure.get('nearest_distance', 0)}:"
                            f"radius={landing_pressure.get('radius', 0)}"
                        ),
                    )
                    plane_filtered.append((candidate[0], candidate[1], candidate[2], candidate[3], candidate[4], reanchored_route))
                    continue
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    route=route,
                    status="skip",
                    reason=(
                        "live_discovery_startup_landing_pressure:"
                        f"{route.prefer}:"
                        f"nearest={landing_pressure.get('nearest_name', '')}:"
                        f"distance={landing_pressure.get('nearest_distance', 0)}:"
                        f"count={landing_pressure.get('count', 0)}:"
                        f"radius={landing_pressure.get('radius', 0)}"
                    ),
                )
                continue
            plane_filtered.append(candidate)
        return plane_filtered

    plane_filtered = filter_landing_pressure(same_plane_candidates)
    if not plane_filtered:
        plane_filtered = filter_landing_pressure(z_delta_candidates)
    if not plane_filtered:
        return None
    filtered = plane_filtered
    selected = filtered[
        growth_route_selection_index(
            args,
            realm_key=realm.key,
            level=int(target_level or 0),
            party_size=int(party_size or 0),
            modulo=len(filtered),
            salt="live-discovery",
        )
    ][5]
    log_growth_route_preflight(
        args,
        realm_key=realm.key,
        current_level=current_level,
        party_size=party_size,
        route=selected,
        status="warn",
        reason=(
            f"live_discovery_candidate_selected:{selected.prefer}:"
            f"mob_level={selected.mob_level}:count={selected.mob_count}"
        ),
    )
    return selected


def growth_route_case_index(args: argparse.Namespace) -> int:
    return max(0, int(getattr(args, "growth_route_case_index", 0) or 0))


def stable_growth_case_route_offset(
    args: argparse.Namespace,
    *,
    realm_key: str,
    level: int,
    party_size: int,
    modulo: int,
    salt: str = "",
) -> int:
    if modulo <= 1:
        return 0
    case_name = str(getattr(args, "case_name", "") or "").strip()
    if not case_name:
        return 0
    seed = f"{case_name}|{realm_key}|{int(level or 0)}|{int(party_size or 0)}|{salt}"
    return sum((index + 1) * ord(char) for index, char in enumerate(seed)) % modulo


def growth_route_selection_index(
    args: argparse.Namespace,
    *,
    realm_key: str,
    level: int,
    party_size: int,
    modulo: int,
    salt: str = "",
) -> int:
    if modulo <= 1:
        return 0
    return (
        growth_route_case_index(args)
        + stable_growth_case_route_offset(
            args,
            realm_key=realm_key,
            level=level,
            party_size=party_size,
            modulo=modulo,
            salt=salt,
        )
    ) % modulo


def rotate_growth_preferred_names(
    args: argparse.Namespace,
    preferred_names: tuple[str, ...],
    *,
    realm_key: str,
    level: int,
    party_size: int,
) -> tuple[str, ...]:
    if len(preferred_names) <= 1:
        return preferred_names
    offset = stable_growth_case_route_offset(
        args,
        realm_key=realm_key,
        level=level,
        party_size=party_size,
        modulo=len(preferred_names),
        salt="preferred",
    )
    return preferred_names[offset:] + preferred_names[:offset]


def growth_route_preflight_enabled(args: argparse.Namespace) -> bool:
    if not bool(getattr(args, "growth_route_preflight", False)):
        return False
    if bool(getattr(args, "dry_run", False)):
        return False
    return True


def growth_route_preflight_policy_level(
    args: argparse.Namespace,
    current_level: int,
    party_size: int,
) -> int:
    level = max(1, int(current_level or 1))
    if int(party_size or 0) > 1 and bool(getattr(args, "growth_route_level_is_carry_target", False)):
        player_level = int(getattr(args, "growth_route_player_level", 0) or 0)
        if player_level > 0:
            return player_level
    return level


def growth_route_home_low_solo_anchor_search_enabled(
    args: argparse.Namespace,
    route: RoutePoint | None,
    *,
    current_level: int,
    party_size: int,
) -> bool:
    return bool(
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and getattr(route, "source", "") == "hunting-index"
        and int(party_size or 0) <= 1
        and 5 <= int(current_level or 0) <= 9
    )


def growth_route_home_low_solo_anchor_search_radius(
    args: argparse.Namespace,
    *,
    current_level: int,
) -> float:
    base = float(getattr(args, "max_target_distance", 0.0) or 0.0)
    if 5 <= int(current_level or 0) <= 9:
        return max(base, 6500.0)
    return max(base, 2200.0)


def is_mid_solo_level_seven_lower_xp_route(
    args: argparse.Namespace,
    level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint | None,
) -> bool:
    if (
        str(realm_key or "").strip().lower() != "mid"
        or int(party_size or 0) > 1
        or int(level or 0) != 7
        or getattr(route, "source", "") != "hunting-index"
    ):
        return False
    if not bool(getattr(args, "growth_allow_lower_xp_target_plan", False)):
        return False
    if not bool(getattr(args, "growth_allow_lower_xp_gear_farm", True)):
        return False
    return bool(route and str(getattr(route, "prefer", "") or "").strip())


def growth_runtime_low_solo_target_cap(
    args: argparse.Namespace,
    level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint | None = None,
) -> float:
    if is_mid_solo_level_seven_lower_xp_route(args, level, party_size, realm_key, route):
        base = float(getattr(args, "max_target_distance", 0.0) or 0.0)
        return max(base, 2800.0)
    return 0.0


def is_alb_solo_level_seven_failed_rot_worm_emerald_route(
    route: RoutePoint | None,
    *,
    level: int,
    party_size: int,
    realm_key: str,
) -> bool:
    if route is None:
        return False
    return bool(
        str(realm_key or "").strip().lower() == "alb"
        and int(level or 0) == 7
        and int(party_size or 0) <= 1
        and str(getattr(route, "source", "") or "") == "hunting-index"
        and "emerald snake" in str(getattr(route, "prefer", "") or "").lower()
        and "rot worm" in str(getattr(route, "avoid", "") or "").lower()
        and int(getattr(route, "x", 0) or 0) == 491304
        and int(getattr(route, "y", 0) or 0) == 592010
    )


def is_alb_solo_level_seven_dragon_ant_worker_route(
    route: RoutePoint | None,
    *,
    level: int,
    party_size: int,
    realm_key: str,
) -> bool:
    if route is None:
        return False
    return bool(
        str(realm_key or "").strip().lower() == "alb"
        and int(level or 0) == 7
        and int(party_size or 0) <= 1
        and str(getattr(route, "source", "") or "") == "hunting-index"
        and target_name_matches_any("dragon ant worker", preferred_target_tokens(getattr(route, "prefer", "")))
    )


def growth_route_home_low_solo_target_cap(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    if not growth_route_home_low_solo_anchor_search_enabled(
        args,
        route,
        current_level=level,
        party_size=party_size,
    ):
        return 0.0
    if (
        str(realm_key or "").strip().lower() == "alb"
        and int(level or 0) == 7
        and int(party_size or 0) <= 1
        and "rot worm" in str(getattr(route, "prefer", "") or "").lower()
    ):
        base = float(getattr(args, "max_target_distance", 0.0) or 0.0)
        return max(base, 9000.0)
    if is_alb_solo_level_seven_failed_rot_worm_emerald_route(
        route,
        level=level,
        party_size=party_size,
        realm_key=realm_key,
    ) or is_alb_solo_level_seven_dragon_ant_worker_route(
        route,
        level=level,
        party_size=party_size,
        realm_key=realm_key,
    ):
        base = float(getattr(args, "max_target_distance", 0.0) or 0.0)
        return max(base, 6500.0)
    return growth_route_home_low_solo_anchor_search_radius(args, current_level=level)


def growth_route_preflight_strict_required(
    args: argparse.Namespace,
    route: RoutePoint | None,
    *,
    current_level: int,
    party_size: int,
) -> bool:
    if not growth_route_preflight_enabled(args):
        return False
    if growth_route_home_low_solo_anchor_search_enabled(
        args,
        route,
        current_level=current_level,
        party_size=party_size,
    ):
        return True
    policy_level = growth_route_preflight_policy_level(args, current_level, party_size)
    return bool(
        route is not None
        and str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and str(getattr(route, "source", "") or "") == "hunting-index"
        and int(party_size or 0) > 1
        and bool(getattr(args, "growth_route_level_is_carry_target", False))
        and int(policy_level or 0) >= 5
    )


def growth_route_preflight_names(route: RoutePoint) -> tuple[str, ...]:
    return tuple(token.strip() for token in str(route.prefer or "").split(",") if token.strip())[:3]


def growth_route_preflight_unsuitable_combat_profile_reason(
    route: RoutePoint,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> str:
    if (
        str(realm_key or "").strip().lower() != "mid"
        or int(current_level or 0) != 10
        or int(party_size or 0) != 2
    ):
        return ""
    target_tokens = preferred_target_tokens(getattr(route, "prefer", ""))
    if target_name_matches_any("roaming dirge", target_tokens):
        return "roaming dirge:caster_cc"
    return ""


def growth_hunting_index_allows_static_avoid_candidate(
    args: argparse.Namespace,
    *,
    realm_key: str,
    level: int,
    party_size: int,
    name: str = "",
    mob_level: int,
    mob_count: int = 0,
) -> bool:
    if growth_is_mid_solo_l7_shortage_black_mauler_candidate(
        args,
        realm_key=realm_key,
        level=level,
        party_size=party_size,
        name=name,
        mob_level=mob_level,
        mob_count=mob_count,
    ):
        return True
    if (
        str(realm_key or "").lower() == "hib"
        and int(party_size or 0) in {2, 4}
        and int(level or 0) in {6, 7}
        and normalize_growth_target_name(name) == "water beetle"
        and int(mob_level or 0) >= 6
    ):
        return True
    if (
        str(realm_key or "").lower() == "hib"
        and int(party_size or 0) == 2
        and int(level or 0) == 10
        and normalize_growth_target_name(name) == "water beetle"
        and int(mob_level or 0) >= 7
    ):
        return True
    if (
        str(realm_key or "").lower() == "mid"
        and int(party_size or 0) == 2
        and int(level or 0) == 10
        and int(mob_level or 0) >= minimum_growth_effective_target_level(10, 2, "mid")
        and int(mob_count or 0) >= 10
    ):
        return True
    return bool(
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and realm_key == "mid"
        and int(party_size or 0) <= 1
        and int(level or 0) == 7
        and int(mob_level or 0) == 6
    )


def growth_is_mid_solo_l7_shortage_black_mauler_candidate(
    args: argparse.Namespace,
    *,
    realm_key: str,
    level: int,
    party_size: int,
    name: str,
    mob_level: int,
    mob_count: int,
) -> bool:
    target_plan_override = getattr(args, "growth_target_plan_override", None)
    if not isinstance(target_plan_override, (list, tuple)) or len(target_plan_override) < 2:
        return False
    return bool(
        bool(getattr(args, "growth_allow_lower_xp_target_plan", False))
        and bool(getattr(args, "growth_allow_lower_xp_gear_farm", True))
        and str(realm_key or "").lower() == "mid"
        and int(party_size or 0) <= 1
        and int(level or 0) == 7
        and 0 < int(target_plan_override[1] or 0) <= 5
        and normalize_growth_target_name(name) == "black mauler juvenile"
        and int(mob_level or 0) == 5
        and 0 < int(mob_count or 0) <= 10
    )


def growth_hunting_index_candidate_target_band(
    args: argparse.Namespace,
    *,
    realm_key: str,
    level: int,
    party_size: int,
) -> tuple[int, int]:
    target_level_override = max(0, int(getattr(args, "growth_target_level_override", 0) or 0))
    actual_player_level = max(
        1,
        int(getattr(args, "growth_shortage_recovery_player_level", 0) or level or 1),
    )
    player_level = target_level_override or actual_player_level
    target_plan_override = getattr(args, "growth_target_plan_override", None)
    if target_plan_override is not None:
        min_target, ideal_target, max_delta = target_plan_override
    else:
        min_target, ideal_target, max_delta = target_levels(player_level, party_size, realm_key)
    min_target, ideal_target, max_delta = enforce_no_lower_xp_target_plan(
        args,
        player_level,
        party_size,
        int(min_target),
        int(ideal_target),
        int(max_delta),
        realm_key,
    )
    min_target, ideal_target, max_delta = enforce_reward_non_grey_target_plan(
        actual_player_level,
        int(min_target),
        int(ideal_target),
        int(max_delta),
    )
    carry_reward_floor = growth_party_carry_reward_floor(args, actual_player_level, party_size, realm_key)
    if carry_reward_floor > 0:
        min_target = max(int(min_target), int(carry_reward_floor))
        ideal_target = max(int(ideal_target), int(min_target))
    return int(min_target), int(growth_command_max_target_level(player_level, int(ideal_target), int(max_delta), party_size))


def filter_growth_hunting_index_candidates_for_target_band(
    args: argparse.Namespace,
    candidates: list[RoutePoint],
    *,
    realm_key: str,
    level: int,
    party_size: int,
) -> list[RoutePoint]:
    if not candidates:
        return candidates
    min_level, max_level = growth_hunting_index_candidate_target_band(
        args,
        realm_key=realm_key,
        level=level,
        party_size=party_size,
    )
    filtered = [
        candidate
        for candidate in candidates
        if int(getattr(candidate, "mob_level", 0) or 0) <= 0
        or min_level <= int(getattr(candidate, "mob_level", 0) or 0) <= max_level
    ]
    if filtered:
        return filtered
    if growth_party_carry_reward_floor(args, level, party_size, realm_key) > 0:
        return []
    return candidates


def growth_route_preflight_endpoint(args: argparse.Namespace) -> str:
    base = str(getattr(args, "nav_api_url", "") or "").strip()
    if not base:
        host = str(getattr(args, "host", "127.0.0.1") or "127.0.0.1").strip()
        port = int(getattr(args, "api_port", 5000) or 5000)
        base = f"http://{host}:{port}"
    base = base.rstrip("/")
    if base.endswith("/api/dummy/combat/npcs"):
        return base
    return f"{base}/api/dummy/combat/npcs"


def growth_route_preflight_level_band(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> tuple[int, int]:
    route_player_level = max(
        1,
        int(getattr(args, "growth_shortage_recovery_player_level", 0) or current_level or 1),
    )
    target_level_override = max(0, int(getattr(args, "growth_target_level_override", 0) or 0))
    player_level = target_level_override or route_player_level
    target_plan_override = getattr(args, "growth_target_plan_override", None)
    if target_plan_override is not None:
        min_target, ideal_target, max_delta = target_plan_override
    else:
        min_target, ideal_target, max_delta = target_levels(player_level, party_size, realm_key)
    min_target, ideal_target, max_delta = enforce_no_lower_xp_target_plan(
        args,
        player_level,
        party_size,
        int(min_target),
        int(ideal_target),
        int(max_delta),
        realm_key,
    )
    min_target, ideal_target, max_delta = enforce_reward_non_grey_target_plan(
        route_player_level,
        int(min_target),
        int(ideal_target),
        int(max_delta),
    )
    min_target, ideal_target, max_delta = adjust_growth_target_plan_for_required_route(
        route,
        current_level=player_level,
        party_size=party_size,
        realm_key=realm_key,
        min_target=int(min_target),
        ideal_target=int(ideal_target),
        max_delta=int(max_delta),
    )
    min_target, ideal_target, max_delta = adjust_low_solo_hunting_target_plan(
        args,
        route,
        current_level=player_level,
        party_size=party_size,
        realm_key=realm_key,
        min_target=int(min_target),
        ideal_target=int(ideal_target),
        max_delta=int(max_delta),
    )
    min_target, ideal_target, max_delta = adjust_party_carry_target_plan_for_route_fallback(
        route,
        current_level=player_level,
        party_size=party_size,
        realm_key=realm_key,
        min_target=int(min_target),
        ideal_target=int(ideal_target),
        max_delta=int(max_delta),
    )
    carry_reward_floor = growth_party_carry_verified_route_reward_floor(
        args,
        route_player_level,
        party_size,
        realm_key,
        route,
    )
    if carry_reward_floor > 0:
        min_target = max(int(min_target), int(carry_reward_floor))
        ideal_target = max(int(ideal_target), int(min_target))
    if target_level_override > 0 and bool(getattr(args, "growth_equip_party_carry_gear", False)):
        min_target, ideal_target, max_delta = enforce_party_carry_non_grey_target_plan(
            args,
            player_level,
            party_size,
            int(min_target),
            int(ideal_target),
            int(max_delta),
            realm_key,
        )
    min_level = max(0, int(min_target))
    max_level = max(
        0,
        int(growth_command_max_target_level(player_level, int(ideal_target), int(max_delta), party_size)),
    )
    if growth_route_home_low_solo_anchor_search_enabled(
        args,
        route,
        current_level=player_level,
        party_size=party_size,
    ):
        mob_level = int(getattr(route, "mob_level", 0) or 0)
        if mob_level > 0:
            min_level = min(min_level, mob_level)
            max_level = max(max_level, mob_level)
    min_level, max_level = include_verified_route_mob_level_in_target_band(
        route,
        int(min_level),
        int(max_level),
        realm_key=realm_key,
        current_level=route_player_level,
        party_size=party_size,
        allow_lower_xp_route_mob=growth_allows_verified_route_mob_below_current_level(args),
    )
    if carry_reward_floor > 0:
        min_level = max(int(min_level), int(carry_reward_floor))
        max_level = max(int(max_level), int(min_level))
    return min_level, max_level


def growth_allows_verified_route_mob_below_current_level(args: argparse.Namespace) -> bool:
    if not bool(getattr(args, "growth_allow_lower_xp_gear_farm", True)):
        return False
    return bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) or bool(
        getattr(args, "growth_route_level_is_carry_target", False)
    )


def include_verified_route_mob_level_in_target_band(
    route: RoutePoint,
    min_target: int,
    command_max_target_level: int,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
    allow_lower_xp_route_mob: bool = False,
) -> tuple[int, int]:
    mob_level = int(getattr(route, "mob_level", 0) or 0)
    if mob_level <= 0:
        return int(min_target), int(command_max_target_level)
    if str(getattr(route, "source", "") or "").startswith("hunting-index"):
        if (
            str(realm_key or "").lower() == "mid"
            and int(party_size or 0) <= 1
            and int(current_level or 0) == 10
            and mob_level > int(command_max_target_level or 0)
            and int(command_max_target_level or 0) <= 7
            and "small hill cat" in str(getattr(route, "prefer", "") or "").lower()
        ):
            return int(min_target), int(command_max_target_level)
        if int(party_size or 0) > 1 and uses_growth_party_carry_tuning(current_level, party_size):
            if mob_level <= max(1, int(current_level or 1)) and not bool(allow_lower_xp_route_mob):
                return int(min_target), int(command_max_target_level)
        xp_floor = max(1, minimum_growth_effective_target_level(current_level, party_size, realm_key))
        if mob_level < xp_floor:
            return int(min_target), int(command_max_target_level)
        return min(int(min_target), mob_level), max(int(command_max_target_level), mob_level)
    if (
        str(realm_key or "").lower() == "alb"
        and int(party_size or 0) <= 1
        and int(current_level or 0) == 10
        and mob_level == 8
        and target_name_matches_any("adder", preferred_target_tokens(str(getattr(route, "prefer", "") or "")))
    ):
        return min(int(min_target), mob_level), max(int(command_max_target_level), mob_level)
    return int(min_target), int(command_max_target_level)


def growth_route_preflight_radius(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> int:
    explicit_radius = int(float(getattr(args, "growth_route_preflight_radius", 0) or 0))
    if explicit_radius > 0:
        return explicit_radius
    try:
        radius = int(growth_hunter_target_api_radius(args, current_level, party_size, realm_key, route))
    except Exception:
        radius = 0
    if radius <= 0:
        radius = int(growth_max_target_distance(args, current_level, party_size, realm_key, route) or 0)
    if (
        realm_key == "hib"
        and int(party_size or 0) <= 1
        and int(current_level or 0) == 4
        and getattr(route, "source", "") == "hunting-index"
    ):
        return max(5000, radius)
    if growth_route_home_low_solo_anchor_search_enabled(
        args,
        route,
        current_level=current_level,
        party_size=party_size,
    ):
        return max(2200, int(growth_route_home_low_solo_anchor_search_radius(args, current_level=current_level)))
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and str(getattr(route, "source", "") or "") == "hunting-index"
        and int(party_size or 0) > 1
        and bool(getattr(args, "growth_route_level_is_carry_target", False))
        and 8 <= int(current_level or 0) <= 10
        and growth_route_preflight_strict_required(
            args,
            route,
            current_level=current_level,
            party_size=party_size,
        )
    ):
        if int(current_level or 0) >= 10:
            return max(8000, radius)
        return max(6500, radius)
    if int(party_size or 0) <= 1 and int(current_level or 0) <= 10:
        low_solo_radius = int(float(getattr(args, "growth_route_preflight_low_solo_radius", 2500) or 2500))
        if low_solo_radius > 0:
            radius = min(radius if radius > 0 else low_solo_radius, low_solo_radius)
    return max(2200, radius)


def fetch_growth_route_preflight_payload(url: str, timeout: float) -> object | None:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        return None
    except Exception:
        return None


def growth_route_preflight_payload_has_items(payload: object) -> bool:
    return bool(growth_route_preflight_payload_items(payload))


def growth_route_preflight_payload_items(payload: object) -> tuple[dict[str, object], ...]:
    if payload is None:
        return ()
    if isinstance(payload, dict):
        raw_items = payload.get("items") or payload.get("npcs") or payload.get("results") or []
    else:
        raw_items = payload
    if not isinstance(raw_items, list):
        return ()
    return tuple(item for item in raw_items if isinstance(item, dict))


def growth_route_preflight_item_matches_name(
    route: RoutePoint,
    item: dict[str, object],
    name: str,
    *,
    exact: bool,
) -> bool:
    item_name = str(item.get("name", "") or "")
    if exact:
        return normalize_growth_target_name(item_name) == normalize_growth_target_name(name)
    return target_name_matches_any(item_name, [name.strip().lower()]) or target_name_matches_any(
        name,
        [item_name.strip().lower()],
    )


def growth_route_preflight_anchor_enabled(
    args: argparse.Namespace,
    *,
    route: RoutePoint,
    current_level: int,
    party_size: int,
) -> bool:
    if not bool(getattr(args, "growth_route_preflight_anchor", True)):
        return False
    return bool(
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and route.source == "hunting-index"
        and int(party_size or 0) >= 1
        and 5 <= int(current_level or 0) <= 10
    )


def growth_route_preflight_anchor_key(
    realm_key: str,
    route: RoutePoint,
    *,
    current_level: int,
    party_size: int,
) -> tuple[str, int, int, int, int, int, str, int]:
    return (
        realm_key,
        int(current_level or 0),
        int(party_size or 0),
        int(route.x),
        int(route.y),
        int(route.z),
        str(route.prefer or "").strip().lower(),
        int(getattr(route, "mob_level", 0) or 0),
    )


def growth_route_preflight_item_route(
    route: RoutePoint,
    item: dict[str, object],
) -> RoutePoint | None:
    x = to_int(item.get("x"))
    y = to_int(item.get("y"))
    if x <= 0 or y <= 0:
        return None
    z = to_int(item.get("z")) or int(route.z)
    item_level = to_int(item.get("level"))
    return route_point(
        route.level,
        x,
        y,
        z,
        route.prefer,
        route.avoid,
        route.teleport_destination,
        route.objective_adds,
        source=route.source,
        mob_level=item_level if item_level > 0 else route.mob_level,
        mob_count=route.mob_count,
        live_anchor_z=True,
        startup_anchor=bool(getattr(route, "startup_anchor", False)),
    )


def growth_route_preflight_startup_landing_buffer_radius(
    current_level: int,
    party_size: int,
    safety_radius: float,
) -> float:
    if safety_radius <= 0.0:
        return 0.0
    if int(current_level or 0) >= 10 and int(party_size or 0) > 1:
        return max(float(safety_radius), min(1400.0, max(900.0, float(safety_radius) * 3.0)))
    return float(safety_radius)


def growth_route_preflight_startup_safe_anchor_route(
    args: argparse.Namespace,
    route: RoutePoint,
    items: tuple[dict[str, object], ...],
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
    safety_radius: float,
) -> RoutePoint | None:
    if safety_radius <= 0.0 or not items:
        return None
    valid_items: list[tuple[int, int]] = []
    for item in items:
        item_x = to_int(item.get("x"))
        item_y = to_int(item.get("y"))
        if item_x <= 0 or item_y <= 0:
            continue
        valid_items.append((item_x, item_y))
    if not valid_items:
        return None

    height_samplers = build_realm_height_samplers()
    ground_z_offset = int(getattr(args, "ground_z_offset", 0) or 0)
    target_z = int(route.z)
    attack_delta = int(growth_hunter_target_max_attack_z_delta(current_level, party_size, realm.key))
    max_target_plane_delta = max(440, attack_delta * 2)
    landing_buffer_radius = growth_route_preflight_startup_landing_buffer_radius(
        current_level,
        party_size,
        safety_radius,
    )
    primary_step = max(int(math.ceil(safety_radius * 4.0)), 900)
    secondary_step = max(primary_step * 2, 1400)
    candidate_offsets: list[tuple[int, int]] = []
    for step in (primary_step, secondary_step):
        candidate_offsets.extend(
            (
                (step, 0),
                (step, step),
                (0, step),
                (-step, step),
                (-step, 0),
                (-step, -step),
                (0, -step),
                (step, -step),
            )
        )

    best_xy: tuple[int, int] | None = None
    best_score: tuple[float, float] | None = None
    for dx, dy in candidate_offsets:
        candidate_x = int(route.x) + int(dx)
        candidate_y = int(route.y) + int(dy)
        nearest_distance = min(math.hypot(candidate_x - item_x, candidate_y - item_y) for item_x, item_y in valid_items)
        if nearest_distance <= landing_buffer_radius:
            continue
        candidate_ground_z = sample_route_z(
            realm,
            height_samplers,
            candidate_x,
            candidate_y,
            target_z,
            ground_z_offset=ground_z_offset,
        )
        if target_z > 0 and abs(int(candidate_ground_z) - target_z) > max_target_plane_delta:
            continue
        score = (math.hypot(dx, dy), -nearest_distance)
        if best_score is None or score < best_score:
            best_score = score
            best_xy = (candidate_x, candidate_y)

    if best_xy is None:
        return None

    return route_point(
        route.level,
        best_xy[0],
        best_xy[1],
        int(route.z),
        route.prefer,
        route.avoid,
        route.teleport_destination,
        route.objective_adds,
        source=route.source,
        mob_level=route.mob_level,
        mob_count=route.mob_count,
        live_anchor_z=True,
        startup_anchor=True,
    )


def growth_route_preflight_item_available(item: dict[str, object]) -> bool:
    if to_bool(item.get("inCombat")) or to_bool(item.get("hasAggro")):
        return False
    if str(item.get("target", "") or "").strip():
        return False
    health_percent = to_int(item.get("healthPercent"))
    if 0 < health_percent < 95:
        return False
    return True


def growth_route_preflight_item_xy_distance(route: RoutePoint, item: dict[str, object]) -> float:
    item_x = to_int(item.get("x"))
    item_y = to_int(item.get("y"))
    if item_x <= 0 or item_y <= 0:
        try:
            return float(item.get("distance", 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0
    return math.hypot(item_x - int(route.x), item_y - int(route.y))


def growth_route_preflight_runtime_distance_items(
    args: argparse.Namespace,
    route: RoutePoint,
    items: Iterable[dict[str, object]],
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> tuple[dict[str, object], ...]:
    max_target_distance = float(growth_max_target_distance(args, current_level, party_size, realm_key, route) or 0.0)
    max_home_distance = float(growth_target_home_max_distance(args, current_level, party_size, realm_key, route) or 0.0)
    max_safe_home_distance = growth_route_preflight_safe_home_distance(
        args,
        route,
        realm_key=realm_key,
        current_level=current_level,
        party_size=party_size,
    )
    eligible: list[dict[str, object]] = []
    for item in items:
        home_distance = growth_route_preflight_item_xy_distance(route, item)
        target_distance = home_distance
        if max_target_distance > 0.0 and target_distance > max_target_distance:
            continue
        if max_home_distance > 0.0 and home_distance > max_home_distance:
            continue
        if max_safe_home_distance > 0.0 and home_distance > max_safe_home_distance:
            continue
        eligible.append(item)
    return tuple(eligible)


def growth_route_preflight_safe_home_distance(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> float:
    if not is_mid_duo_level_ten_tawny_lynx_route(current_level, party_size, realm_key, route):
        return 0.0
    leash_distance = float(
        growth_combat_home_leash_distance_for_route(args, current_level, party_size, realm_key, route) or 0.0
    )
    if leash_distance <= 0.0:
        return 0.0
    return max(900.0, leash_distance - 400.0)


def growth_route_preflight_anchor_pool(
    args: argparse.Namespace,
    route: RoutePoint,
    items: tuple[dict[str, object], ...],
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> tuple[dict[str, object], ...]:
    scored_items: list[tuple[float, dict[str, object]]] = []
    for item in items:
        anchored = growth_route_preflight_item_route(route, item)
        if anchored is None:
            continue
        distance = item.get("distance")
        try:
            score = float(distance)
        except (TypeError, ValueError):
            score = math.hypot(int(anchored.x) - int(route.x), int(anchored.y) - int(route.y))
        scored_items.append((score, item))
    if not scored_items:
        return ()
    scored_items.sort(key=lambda entry: entry[0])
    anchor_pool = [entry[1] for entry in scored_items if growth_route_preflight_item_available(entry[1])]
    if not anchor_pool:
        anchor_pool = [entry[1] for entry in scored_items]
    if int(party_size or 0) <= 1 and len(anchor_pool) > 1:
        anchor_index = growth_route_selection_index(
            args,
            realm_key=realm_key,
            level=current_level,
            party_size=party_size,
            modulo=len(anchor_pool),
            salt=f"preflight-anchor:{int(route.x)}:{int(route.y)}:{str(route.prefer or '').lower()}",
        )
        anchor_pool = anchor_pool[anchor_index:] + anchor_pool[:anchor_index]
    return tuple(anchor_pool)


def growth_route_preflight_item_z_mismatch(
    args: argparse.Namespace,
    route: RoutePoint,
    item: dict[str, object],
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
    height_samplers: dict[str, ClientZoneHeightSampler],
) -> dict[str, int] | None:
    if str(getattr(args, "growth_fast_travel", "") or "").strip().lower() != "route-home":
        return None
    item_route = growth_route_preflight_item_route(route, item)
    if item_route is None:
        return None
    target_z = int(item_route.z)
    ground_z = sample_route_z(
        realm,
        height_samplers,
        item_route.x,
        item_route.y,
        target_z,
        ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
    )
    max_delta = int(growth_hunter_target_max_ground_z_delta(current_level, party_size, realm.key))
    delta = abs(int(target_z) - int(ground_z))
    if delta <= max_delta:
        return None
    return {
        "x": int(item_route.x),
        "y": int(item_route.y),
        "target_z": int(target_z),
        "ground_z": int(ground_z),
        "delta": int(delta),
        "max_delta": int(max_delta),
    }


def growth_route_preflight_z_viable_items(
    args: argparse.Namespace,
    route: RoutePoint,
    items: tuple[dict[str, object], ...],
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
) -> tuple[tuple[dict[str, object], ...], tuple[dict[str, int], ...]]:
    if not items:
        return (), ()
    height_samplers = build_realm_height_samplers()
    viable: list[dict[str, object]] = []
    mismatches: list[dict[str, int]] = []
    for item in items:
        mismatch = growth_route_preflight_item_z_mismatch(
            args,
            route,
            item,
            realm=realm,
            current_level=current_level,
            party_size=party_size,
            height_samplers=height_samplers,
        )
        if mismatch is None:
            viable.append(item)
        else:
            mismatches.append(mismatch)
    return tuple(viable), tuple(mismatches)


def growth_live_discovery_startup_plane_mismatch(
    args: argparse.Namespace,
    realm: RealmProfile,
    route: RoutePoint,
    *,
    current_level: int,
    party_size: int,
) -> dict[str, int] | None:
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() != "route-home"
        or not bool(getattr(route, "live_anchor_z", False))
        or int(party_size or 0) <= 1
    ):
        return None
    destination_name = str(getattr(route, "teleport_destination", "") or "").strip()
    if destination_name and teleport_destination_point(realm, destination_name) is not None:
        return None
    landing = live_anchor_party_safe_landing_point(
        realm,
        route,
        current_level=current_level,
        party_size=party_size,
        ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
    )
    if landing is None:
        return {
            "landing_z": 0,
            "target_z": int(route.z),
            "delta": 0,
            "max_delta": 0,
        }
    target_z = int(route.z)
    landing_z = int(landing.z)
    delta = abs(target_z - landing_z)
    attack_delta = int(growth_hunter_target_max_attack_z_delta(current_level, party_size, realm.key))
    max_delta = max(440, attack_delta * 2)
    if delta <= max_delta:
        return None
    return {
        "landing_z": landing_z,
        "target_z": target_z,
        "delta": int(delta),
        "max_delta": int(max_delta),
    }


def growth_live_discovery_startup_landing_pressure(
    args: argparse.Namespace,
    realm: RealmProfile,
    route: RoutePoint,
    *,
    endpoint: str,
    timeout: float,
    current_level: int,
    party_size: int,
) -> dict[str, object] | None:
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() != "route-home"
        or not bool(getattr(route, "live_anchor_z", False))
        or int(party_size or 0) <= 1
    ):
        return None
    landing = live_anchor_party_safe_landing_point(
        realm,
        route,
        current_level=current_level,
        party_size=party_size,
        ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
    )
    if landing is None:
        return None
    min_level = max(
        1,
        min(
            int(getattr(route, "mob_level", 0) or current_level or 1),
            int(current_level or 1) - 3,
        ),
    )
    max_level = max(min_level, int(current_level or 0) + 5, min_level + 3)
    radius = int(max(1800.0, float(growth_party_leech_start_distance(current_level, party_size)) + 1200.0))
    query = {
        "region": int(realm.region),
        "x": int(landing.x),
        "y": int(landing.y),
        "radius": int(radius),
        "minLevel": int(min_level),
        "maxLevel": int(max_level),
        "limit": 20,
    }
    url = f"{endpoint}?{urllib.parse.urlencode(query)}"
    payload = fetch_growth_route_preflight_payload(url, timeout)
    if payload is None:
        return None
    danger_items: list[tuple[float, dict[str, object]]] = []
    for item in growth_route_preflight_payload_items(payload):
        if not growth_route_preflight_item_available(item):
            continue
        item_level = to_int(item.get("level"))
        if item_level < min_level or item_level > max_level:
            continue
        item_x = to_int(item.get("x"))
        item_y = to_int(item.get("y"))
        if item_x <= 0 or item_y <= 0:
            continue
        distance = math.hypot(item_x - int(landing.x), item_y - int(landing.y))
        if distance <= radius:
            danger_items.append((distance, item))
    if not danger_items:
        return None
    danger_items.sort(key=lambda entry: (entry[0], str(entry[1].get("name", "") or "")))
    nearest_distance, nearest_item = danger_items[0]
    return {
        "nearest_name": str(nearest_item.get("name", "") or ""),
        "nearest_distance": int(round(nearest_distance)),
        "count": len(danger_items),
        "radius": int(radius),
    }


def growth_live_discovery_reanchor_landing_pressure(
    args: argparse.Namespace,
    realm: RealmProfile,
    route: RoutePoint,
    *,
    endpoint: str,
    timeout: float,
    current_level: int,
    party_size: int,
) -> RoutePoint | None:
    if not growth_route_preflight_anchor_enabled(
        args,
        route=route,
        current_level=current_level,
        party_size=party_size,
    ):
        return None
    max_home_distance = growth_required_target_home_hunt_distance(
        args,
        current_level,
        party_size,
        realm.key,
        route,
    )
    max_offset = max(1800.0, min(float(max_home_distance or 0.0) * 0.75, 4800.0))
    if max_offset <= 0.0:
        return None

    base_steps = [1800, 2600, 3600, 4600]
    steps = [step for step in base_steps if float(step) <= max_offset]
    if not steps:
        steps = [int(max_offset)]
    directions = (
        (1.0, 0.0),
        (0.707, 0.707),
        (0.0, 1.0),
        (-0.707, 0.707),
        (-1.0, 0.0),
        (-0.707, -0.707),
        (0.0, -1.0),
        (0.707, -0.707),
    )
    destination_name = str(getattr(route, "teleport_destination", "") or "").strip()
    if not destination_name or teleport_destination_point(realm, destination_name) is None:
        destination_name = nearest_teleport_destination(realm, replace(route, teleport_destination=""))
    if destination_name:
        destination = teleport_destination_point(realm, destination_name)
        if destination is not None:
            teleport_x, teleport_y, _teleport_z = destination
            away_x = float(route.x - teleport_x)
            away_y = float(route.y - teleport_y)
            length = math.hypot(away_x, away_y)
            if length > 0.0:
                directions = ((away_x / length, away_y / length),) + directions

    seen: set[tuple[int, int]] = set()
    height_samplers = build_realm_height_samplers()
    ground_z_offset = int(getattr(args, "ground_z_offset", 0) or 0)
    for step in steps:
        for dir_x, dir_y in directions:
            x = int(round(int(route.x) + float(dir_x) * float(step)))
            y = int(round(int(route.y) + float(dir_y) * float(step)))
            key = (x, y)
            if key in seen:
                continue
            seen.add(key)
            if math.hypot(x - int(route.x), y - int(route.y)) > max_offset:
                continue
            z = sample_route_z(
                realm,
                height_samplers,
                x,
                y,
                int(route.z),
                ground_z_offset=ground_z_offset,
            )
            candidate = replace(route, x=x, y=y, z=z, live_anchor_z=True, startup_anchor=True)
            landing = live_anchor_party_safe_landing_point(
                realm,
                candidate,
                current_level=current_level,
                party_size=party_size,
                ground_z_offset=ground_z_offset,
            )
            candidate_landing_z = int(landing.z) if landing is not None else int(candidate.z)
            target_z = int(route.z)
            attack_delta = int(growth_hunter_target_max_attack_z_delta(current_level, party_size, realm.key))
            max_target_plane_delta = max(440, attack_delta * 2)
            target_plane_delta = abs(candidate_landing_z - target_z)
            if target_z > 0 and target_plane_delta > max_target_plane_delta:
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    route=candidate,
                    status="skip",
                    reason=(
                        "live_discovery_reanchor_target_plane_delta:"
                        f"{route.prefer}:"
                        f"from={route.x},{route.y}:"
                        f"candidate={candidate.x},{candidate.y}:"
                        f"landing_z={candidate_landing_z}:"
                        f"target_z={target_z}:"
                        f"delta={target_plane_delta}:"
                        f"max={max_target_plane_delta}"
                    ),
                )
                continue
            status = growth_route_preflight_status(
                args,
                candidate,
                realm=realm,
                current_level=current_level,
                party_size=party_size,
            )
            if status is not True:
                continue
            if growth_live_discovery_startup_landing_pressure(
                args,
                realm,
                candidate,
                endpoint=endpoint,
                timeout=timeout,
                current_level=current_level,
                party_size=party_size,
            ) is not None:
                continue
            return candidate
    return None


def store_growth_route_preflight_anchor(
    args: argparse.Namespace,
    route: RoutePoint,
    items: tuple[dict[str, object], ...],
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> None:
    if not items or not growth_route_preflight_anchor_enabled(
        args,
        route=route,
        current_level=current_level,
        party_size=party_size,
    ):
        return
    anchor_pool = growth_route_preflight_anchor_pool(
        args,
        route,
        items,
        realm_key=realm_key,
        current_level=current_level,
        party_size=party_size,
    )
    if not anchor_pool:
        return
    anchored_route = growth_route_preflight_item_route(route, anchor_pool[0])
    if anchored_route is None:
        return
    store_growth_route_preflight_anchor_route(
        args,
        route,
        anchored_route,
        realm_key=realm_key,
        current_level=current_level,
        party_size=party_size,
    )


def store_growth_route_preflight_anchor_route(
    args: argparse.Namespace,
    route: RoutePoint,
    anchored_route: RoutePoint,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> None:
    cache = getattr(args, "_growth_route_preflight_anchor_cache", None)
    if cache is None:
        cache = {}
        setattr(args, "_growth_route_preflight_anchor_cache", cache)
    cache[
        growth_route_preflight_anchor_key(
            realm_key,
            route,
            current_level=current_level,
            party_size=party_size,
        )
    ] = anchored_route


def growth_route_preflight_adjusted_route(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
) -> RoutePoint:
    cache = getattr(args, "_growth_route_preflight_anchor_cache", None)
    if not isinstance(cache, dict):
        return route
    return cache.get(
        growth_route_preflight_anchor_key(
            realm.key,
            route,
            current_level=current_level,
            party_size=party_size,
        ),
        route,
    )


def growth_route_preflight_checked_route(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
) -> RoutePoint | None:
    unsuitable_reason = ""
    if growth_route_preflight_enabled(args):
        unsuitable_reason = growth_route_preflight_unsuitable_combat_profile_reason(
            route,
            realm_key=realm.key,
            current_level=current_level,
            party_size=party_size,
        )
    if unsuitable_reason:
        log_growth_route_preflight(
            args,
            realm_key=realm.key,
            current_level=current_level,
            party_size=party_size,
            route=route,
            status="skip",
            reason=f"live_target_unsuitable_combat_profile:{unsuitable_reason}",
        )
        return None
    status = growth_route_preflight_status(
        args,
        route,
        realm=realm,
        current_level=current_level,
        party_size=party_size,
    )
    if status is False:
        return None
    if status is None and growth_route_preflight_strict_required(
        args,
        route,
        current_level=current_level,
        party_size=party_size,
    ):
        return None
    return growth_route_preflight_adjusted_route(
        args,
        route,
        realm=realm,
        current_level=current_level,
        party_size=party_size,
    )


def growth_route_preflight_filter_routes(
    args: argparse.Namespace,
    routes: Iterable[RoutePoint],
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
) -> list[RoutePoint]:
    filtered: list[RoutePoint] = []
    for route in routes:
        adjusted = growth_route_preflight_checked_route(
            args,
            route,
            realm=realm,
            current_level=current_level,
            party_size=party_size,
        )
        if adjusted is not None:
            filtered.append(adjusted)
    return filtered


def growth_route_preflight_filter_candidate_pool(
    args: argparse.Namespace,
    candidates: list[tuple[int, int, float, int, int, RoutePoint]],
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
) -> list[tuple[int, int, float, int, int, RoutePoint]]:
    filtered: list[tuple[int, int, float, int, int, RoutePoint]] = []
    for candidate in candidates:
        adjusted = growth_route_preflight_checked_route(
            args,
            candidate[5],
            realm=realm,
            current_level=current_level,
            party_size=party_size,
        )
        if adjusted is not None:
            filtered.append((candidate[0], candidate[1], candidate[2], candidate[3], candidate[4], adjusted))
    return filtered


def growth_route_preflight_hazard_tokens(
    route: RoutePoint,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
    allow_lower_xp_target_plan: bool = False,
) -> tuple[str, ...]:
    if (
        allow_lower_xp_target_plan
        and realm_key == "mid"
        and int(party_size or 0) <= 1
        and int(current_level or 0) == 7
    ):
        return ()
    avoid_text = growth_avoid_targets_for_current_context(
        route,
        realm_key,
        current_level,
        party_size,
        allow_lower_xp_target_plan=allow_lower_xp_target_plan,
    )
    route_targets = {token.lower() for token in growth_route_preflight_names(route)}
    tokens: list[str] = []
    seen: set[str] = set()
    priority_tokens: tuple[str, ...] = ()
    if str(realm_key or "").lower() == "mid" and int(party_size or 0) >= 8 and int(current_level or 0) <= 5:
        priority_tokens = (
            "wood-eater hunter",
            "wood-eater soldier",
            "wood-eater royal guard",
            "young grendelorm",
            "huldu",
            "huldu hunter",
            "huldu stalker",
            "small hill cat",
        )
    for token in (*priority_tokens, *preferred_target_tokens(avoid_text)):
        clean = token.strip()
        key = clean.lower()
        if not clean or key in seen or key in route_targets:
            continue
        if growth_route_preflight_is_generic_growth_prefix_token(clean):
            continue
        seen.add(key)
        tokens.append(clean)
    return tuple(tokens)


def log_growth_route_preflight(
    args: argparse.Namespace,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
    route: RoutePoint,
    status: str,
    reason: str,
    url: str = "",
) -> None:
    run_dir = str(getattr(args, "run_dir", "") or "").strip()
    if not run_dir:
        return
    try:
        path = Path(run_dir) / "route-preflight.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": status,
            "reason": reason,
            "realm": realm_key,
            "level": int(current_level or 0),
            "party_size": int(party_size or 0),
            "route": {
                "prefer": route.prefer,
                "level": route.level,
                "mob_level": route.mob_level,
                "x": route.x,
                "y": route.y,
                "z": route.z,
                "source": route.source,
            },
            "url": url,
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        return


def growth_route_preflight_limit_for_route(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> int:
    base = max(1, int(getattr(args, "growth_route_preflight_limit", 3) or 3))
    if strict_route_target_name_requires_exact(route, current_level, party_size, realm_key):
        min_targets = growth_route_preflight_min_available_targets(
            args,
            route,
            realm_key=realm_key,
            current_level=current_level,
            party_size=party_size,
        )
        return max(base, 10, int(min_targets or 0) + 8)
    if growth_route_preflight_strict_required(
        args,
        route,
        current_level=current_level,
        party_size=party_size,
    ):
        min_targets = growth_route_preflight_min_available_targets(
            args,
            route,
            realm_key=realm_key,
            current_level=current_level,
            party_size=party_size,
        )
        return max(base, 10, int(min_targets or 0) + 8)
    if is_mid_solo_level_seven_lower_xp_route(args, current_level, party_size, realm_key, route):
        return max(base, 10)
    return base


def growth_route_preflight_min_available_targets(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> int:
    configured = int(getattr(args, "growth_route_preflight_min_available_targets", 0) or 0)
    if configured > 0:
        return configured
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and int(party_size or 0) > 1
        and int(current_level or 0) <= 10
        and growth_party_uses_carry_tuning(args, current_level, party_size)
    ):
        return min(3, max(2, int(party_size or 0)))
    return 1


def growth_route_preflight_startup_safety_radius(
    args: argparse.Namespace,
    *,
    current_level: int,
    party_size: int,
) -> float:
    configured = float(getattr(args, "growth_route_preflight_startup_safety_radius", 0.0) or 0.0)
    if configured > 0.0:
        return configured
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and int(party_size or 0) > 1
        and 1 <= int(current_level or 0) <= 10
    ):
        return 350.0
    return 0.0


def growth_route_preflight_hazard_radius(
    args: argparse.Namespace,
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> int:
    base = int(float(getattr(args, "growth_route_preflight_hazard_radius", 2500) or 0))
    if str(realm_key or "").lower() == "hib" and int(party_size or 0) >= 8 and int(current_level or 0) <= 1:
        return min(base, 800)
    if str(realm_key or "").lower() == "mid" and int(party_size or 0) >= 8 and int(current_level or 0) <= 5:
        return max(base, 5200)
    return base


def growth_route_preflight_status(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
) -> bool | None:
    if not growth_route_preflight_enabled(args):
        return None
    names = growth_route_preflight_names(route)
    if not names:
        return None
    min_level, max_level = growth_route_preflight_level_band(
        args,
        route,
        realm_key=realm.key,
        current_level=current_level,
        party_size=party_size,
    )
    radius = growth_route_preflight_radius(
        args,
        route,
        realm_key=realm.key,
        current_level=current_level,
        party_size=party_size,
    )
    limit = growth_route_preflight_limit_for_route(
        args,
        route,
        realm_key=realm.key,
        current_level=current_level,
        party_size=party_size,
    )
    min_available_targets = growth_route_preflight_min_available_targets(
        args,
        route,
        realm_key=realm.key,
        current_level=current_level,
        party_size=party_size,
    )
    timeout = max(0.1, float(getattr(args, "growth_route_preflight_timeout", 1.5) or 1.5))
    hazard_radius = growth_route_preflight_hazard_radius(
        args,
        realm_key=realm.key,
        current_level=current_level,
        party_size=party_size,
    )
    hazard_limit = max(1, int(getattr(args, "growth_route_preflight_hazard_limit", 3) or 3))
    hazard_token_limit = max(0, int(getattr(args, "growth_route_preflight_hazard_token_limit", 12) or 0))
    cache = getattr(args, "_growth_route_preflight_cache", None)
    if cache is None:
        cache = {}
        setattr(args, "_growth_route_preflight_cache", cache)
    items_cache = getattr(args, "_growth_route_preflight_items_cache", None)
    if items_cache is None:
        items_cache = {}
        setattr(args, "_growth_route_preflight_items_cache", items_cache)
    raw_items_cache = getattr(args, "_growth_route_preflight_raw_items_cache", None)
    if raw_items_cache is None:
        raw_items_cache = {}
        setattr(args, "_growth_route_preflight_raw_items_cache", raw_items_cache)
    endpoint = growth_route_preflight_endpoint(args)
    saw_positive_not_found = False
    target_name = ""
    target_url = ""
    target_items: tuple[dict[str, object], ...] = ()
    target_anchor_items: tuple[dict[str, object], ...] = ()
    preselected_anchor_route: RoutePoint | None = None
    startup_safety_radius = growth_route_preflight_startup_safety_radius(
        args,
        current_level=current_level,
        party_size=party_size,
    )
    nearby_avoid_names = growth_runtime_target_nearby_avoid_names_for_route(
        current_level,
        party_size,
        realm.key,
        route,
        allow_lower_xp_target_plan=bool(getattr(args, "growth_allow_lower_xp_target_plan", False))
        and bool(getattr(args, "growth_allow_lower_xp_gear_farm", True)),
    )
    nearby_avoid_radius = 1800 if nearby_avoid_names else 0
    hazard_scan_radius = hazard_radius
    if hazard_scan_radius > 0 and nearby_avoid_radius > 0:
        hazard_scan_radius = min(hazard_scan_radius, nearby_avoid_radius)
    for name in names:
        query = {
            "region": int(realm.region),
            "x": int(route.x),
            "y": int(route.y),
            "radius": radius,
            "minLevel": min_level,
            "maxLevel": max_level,
            "limit": limit,
            "name": name,
        }
        if nearby_avoid_radius > 0 and nearby_avoid_names:
            query["nearbyRadius"] = nearby_avoid_radius
            query["nearbyAvoidName"] = nearby_avoid_names
        url = f"{endpoint}?{urllib.parse.urlencode(query)}"
        cache_key = (
            endpoint,
            int(realm.region),
            int(route.x),
            int(route.y),
            int(radius),
            int(min_level),
            int(max_level),
            int(limit),
            name.lower(),
            int(nearby_avoid_radius),
            nearby_avoid_names.lower(),
            bool(strict_route_target_name_requires_exact(route, current_level, party_size, realm.key)),
        )
        if cache_key in cache:
            status = cache[cache_key]
            cached_items = items_cache.get(cache_key, ())
            target_items = cached_items if isinstance(cached_items, tuple) else ()
            cached_raw_items = raw_items_cache.get(cache_key, ())
            raw_target_items = cached_raw_items if isinstance(cached_raw_items, tuple) else target_items
        else:
            payload = fetch_growth_route_preflight_payload(url, timeout)
            if payload is None:
                status = None
                target_items = ()
                raw_target_items = ()
            else:
                raw_target_items = growth_route_preflight_payload_items(payload)
                target_items = raw_target_items
                if strict_route_target_name_requires_exact(
                    route,
                    current_level,
                    party_size,
                    realm.key,
                ):
                    target_items = tuple(
                        item
                        for item in target_items
                        if growth_route_preflight_item_matches_name(
                            route,
                            item,
                            name,
                            exact=True,
                        )
                    )
                status = bool(target_items)
            cache[cache_key] = status
            items_cache[cache_key] = target_items
            raw_items_cache[cache_key] = raw_target_items
        if status is True:
            all_target_items = target_items
            target_items, z_mismatches = growth_route_preflight_z_viable_items(
                args,
                route,
                target_items,
                realm=realm,
                current_level=current_level,
                party_size=party_size,
            )
            if z_mismatches and growth_route_preflight_anchor_enabled(
                args,
                route=route,
                current_level=current_level,
                party_size=party_size,
            ):
                mismatch = z_mismatches[0]
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    route=route,
                    status="warn",
                    reason=(
                        f"live_target_z_preserved:{name}:count={len(z_mismatches)}:"
                        f"target_z={mismatch.get('target_z', 0)}:"
                        f"ground_z={mismatch.get('ground_z', 0)}:"
                        f"delta={mismatch.get('delta', 0)}:"
                        f"max={mismatch.get('max_delta', 0)}:"
                        f"level={min_level}-{max_level}:radius={radius}"
                    ),
                    url=url,
                )
                target_items = all_target_items
            elif not target_items:
                mismatch = z_mismatches[0] if z_mismatches else {}
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    route=route,
                    status="skip",
                    reason=(
                        f"live_target_z_mismatch:{name}:count={len(z_mismatches)}:"
                        f"target_z={mismatch.get('target_z', 0)}:"
                        f"ground_z={mismatch.get('ground_z', 0)}:"
                        f"delta={mismatch.get('delta', 0)}:"
                        f"max={mismatch.get('max_delta', 0)}:"
                        f"level={min_level}-{max_level}:radius={radius}"
                    ),
                    url=url,
                )
                saw_positive_not_found = True
                continue
            available_target_items = tuple(
                item for item in target_items if growth_route_preflight_item_available(item)
            )
            if len(available_target_items) < min_available_targets:
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    route=route,
                    status="skip",
                    reason=(
                        f"live_target_insufficient:{name}:available={len(available_target_items)}:"
                        f"required={min_available_targets}:level={min_level}-{max_level}:radius={radius}"
                    ),
                    url=url,
                )
                saw_positive_not_found = True
                continue
            startup_pressure_items = available_target_items
            if nearby_avoid_radius > 0 and nearby_avoid_names:
                safe_target_items, nearby_blocked_count = growth_route_preflight_filter_nearby_avoid_pressure(
                    available_target_items
                )
                if nearby_blocked_count > 0:
                    if len(safe_target_items) < min_available_targets:
                        log_growth_route_preflight(
                            args,
                            realm_key=realm.key,
                            current_level=current_level,
                            party_size=party_size,
                            route=route,
                            status="skip",
                            reason=(
                                f"live_target_nearby_avoid_pressure:{name}:"
                                f"blocked={nearby_blocked_count}:"
                                f"available={len(available_target_items)}:"
                                f"safe={len(safe_target_items)}:"
                                f"required={min_available_targets}:radius={nearby_avoid_radius}"
                            ),
                            url=url,
                        )
                        saw_positive_not_found = True
                        continue
                    log_growth_route_preflight(
                        args,
                        realm_key=realm.key,
                        current_level=current_level,
                        party_size=party_size,
                        route=route,
                        status="warn",
                        reason=(
                            f"live_target_nearby_avoid_filtered:{name}:"
                            f"blocked={nearby_blocked_count}:"
                            f"available={len(available_target_items)}:"
                            f"safe={len(safe_target_items)}:"
                            f"radius={nearby_avoid_radius}"
                        ),
                        url=url,
                    )
                    available_target_items = safe_target_items
            same_base_prefix_radius = min(float(hazard_radius), 1800.0)
            same_base_prefix_raw_items = raw_target_items
            if same_base_prefix_radius > 0.0 and not growth_route_preflight_same_base_growth_prefix_items(
                name,
                same_base_prefix_raw_items,
            ):
                prefix_scan_items: list[dict[str, object]] = []
                prefix_scan_radius = int(math.ceil(same_base_prefix_radius))
                prefix_scan_max_level = max(max_level, int(current_level or 0) + 5, 12)
                for prefix_name in growth_route_preflight_same_base_growth_prefix_scan_names(name):
                    query = {
                        "region": int(realm.region),
                        "x": int(route.x),
                        "y": int(route.y),
                        "radius": prefix_scan_radius,
                        "minLevel": min_level,
                        "maxLevel": prefix_scan_max_level,
                        "limit": hazard_limit,
                        "name": prefix_name,
                    }
                    prefix_url = f"{endpoint}?{urllib.parse.urlencode(query)}"
                    prefix_cache_key = (
                        "same_base_growth_prefix",
                        endpoint,
                        int(realm.region),
                        int(route.x),
                        int(route.y),
                        int(prefix_scan_radius),
                        int(min_level),
                        int(prefix_scan_max_level),
                        int(hazard_limit),
                        prefix_name.lower(),
                    )
                    if prefix_cache_key in cache:
                        cached_prefix_items = items_cache.get(prefix_cache_key, ())
                        if isinstance(cached_prefix_items, tuple):
                            prefix_items = cached_prefix_items
                        else:
                            prefix_items = ()
                    else:
                        payload = fetch_growth_route_preflight_payload(prefix_url, timeout)
                        prefix_items = growth_route_preflight_payload_items(payload)
                        cache[prefix_cache_key] = None if payload is None else bool(prefix_items)
                        items_cache[prefix_cache_key] = prefix_items
                    prefix_scan_items.extend(prefix_items)
                if prefix_scan_items:
                    same_base_prefix_raw_items = tuple((*same_base_prefix_raw_items, *prefix_scan_items))
            safe_target_items, same_base_prefix_items = (
                growth_route_preflight_filter_same_base_growth_prefix_pressure(
                    name,
                    available_target_items,
                    same_base_prefix_raw_items,
                    radius=same_base_prefix_radius,
                )
            )
            if same_base_prefix_items:
                startup_pressure_items = tuple((*startup_pressure_items, *same_base_prefix_items))
                if len(safe_target_items) < min_available_targets:
                    log_growth_route_preflight(
                        args,
                        realm_key=realm.key,
                        current_level=current_level,
                        party_size=party_size,
                        route=route,
                        status="skip",
                        reason=(
                            f"live_growth_prefix_pressure:{name}:"
                            f"prefixed={len(same_base_prefix_items)}:"
                            f"available={len(available_target_items)}:"
                            f"safe={len(safe_target_items)}:"
                            f"required={min_available_targets}:radius={same_base_prefix_radius:.0f}"
                        ),
                        url=url,
                    )
                    saw_positive_not_found = True
                    continue
                if len(safe_target_items) < len(available_target_items):
                    log_growth_route_preflight(
                        args,
                        realm_key=realm.key,
                        current_level=current_level,
                        party_size=party_size,
                        route=route,
                        status="warn",
                        reason=(
                            f"live_growth_prefix_anchor_filtered:{name}:"
                            f"prefixed={len(same_base_prefix_items)}:"
                            f"available={len(available_target_items)}:"
                            f"safe={len(safe_target_items)}:"
                            f"radius={same_base_prefix_radius:.0f}"
                        ),
                        url=url,
                    )
                available_target_items = safe_target_items
            if startup_safety_radius > 0.0 and startup_pressure_items:
                safer_anchor_found = False
                nearest_available_distance = min(
                    math.hypot(int(item.get("x", 0) or 0) - int(route.x), int(item.get("y", 0) or 0) - int(route.y))
                    for item in startup_pressure_items
                )
                startup_overlap_distance = startup_safety_radius
                if nearest_available_distance <= startup_overlap_distance:
                    candidate_route = growth_route_preflight_startup_safe_anchor_route(
                        args,
                        route,
                        startup_pressure_items,
                        realm=realm,
                        current_level=current_level,
                        party_size=party_size,
                        safety_radius=startup_safety_radius,
                    )
                    if candidate_route is not None:
                        store_growth_route_preflight_anchor_route(
                            args,
                            route,
                            candidate_route,
                            realm_key=realm.key,
                            current_level=current_level,
                            party_size=party_size,
                        )
                        log_growth_route_preflight(
                            args,
                            realm_key=realm.key,
                            current_level=current_level,
                            party_size=party_size,
                            route=candidate_route,
                            status="warn",
                            reason=(
                                f"live_startup_anchor_replaced:spawn_overlap:"
                                f"from={route.x},{route.y}:"
                                f"distance={nearest_available_distance:.0f}:"
                                f"radius={startup_safety_radius:.0f}:"
                                f"target={name}"
                            ),
                            url=url,
                        )
                        preselected_anchor_route = candidate_route
                        safer_anchor_found = True
                    if not safer_anchor_found:
                        log_growth_route_preflight(
                            args,
                            realm_key=realm.key,
                            current_level=current_level,
                            party_size=party_size,
                            route=route,
                            status="skip",
                            reason=(
                                f"live_startup_spawn_overlap:{name}:"
                                f"distance={nearest_available_distance:.0f}:"
                                f"radius={startup_safety_radius:.0f}"
                            ),
                            url=url,
                        )
                        saw_positive_not_found = True
                        continue
            runtime_distance_route = preselected_anchor_route
            if runtime_distance_route is None and growth_route_preflight_anchor_enabled(
                args,
                route=route,
                current_level=current_level,
                party_size=party_size,
            ):
                anchor_pool = growth_route_preflight_anchor_pool(
                    args,
                    route,
                    available_target_items,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                )
                if anchor_pool:
                    runtime_distance_route = growth_route_preflight_item_route(route, anchor_pool[0])
            if runtime_distance_route is None:
                runtime_distance_route = route
            runtime_target_items = growth_route_preflight_runtime_distance_items(
                args,
                runtime_distance_route,
                available_target_items,
                realm_key=realm.key,
                current_level=current_level,
                party_size=party_size,
            )
            if len(runtime_target_items) < min_available_targets:
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    route=runtime_distance_route,
                    status="skip",
                    reason=(
                        f"live_target_runtime_distance_mismatch:{name}:"
                        f"available={len(available_target_items)}:"
                        f"runtime={len(runtime_target_items)}:"
                        f"required={min_available_targets}:"
                        f"max={growth_max_target_distance(args, current_level, party_size, realm.key, runtime_distance_route):.0f}:"
                        f"home={growth_target_home_max_distance(args, current_level, party_size, realm.key, runtime_distance_route):.0f}:"
                        f"radius={radius}"
                    ),
                    url=url,
                )
                saw_positive_not_found = True
                continue
            if len(runtime_target_items) < len(available_target_items):
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    route=runtime_distance_route,
                    status="warn",
                    reason=(
                        f"live_target_runtime_distance_filtered:{name}:"
                        f"available={len(available_target_items)}:"
                        f"runtime={len(runtime_target_items)}:"
                        f"max={growth_max_target_distance(args, current_level, party_size, realm.key, runtime_distance_route):.0f}:"
                        f"home={growth_target_home_max_distance(args, current_level, party_size, realm.key, runtime_distance_route):.0f}:"
                        f"radius={radius}"
                    ),
                    url=url,
                )
                available_target_items = runtime_target_items
            target_name = name
            target_url = url
            target_anchor_items = available_target_items
            if preselected_anchor_route is not None:
                store_growth_route_preflight_anchor_route(
                    args,
                    route,
                    preselected_anchor_route,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                )
            else:
                store_growth_route_preflight_anchor(
                    args,
                    route,
                    available_target_items,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                )
            break
        if status is None:
            log_growth_route_preflight(
                args,
                realm_key=realm.key,
                current_level=current_level,
                party_size=party_size,
                route=route,
                status="unknown",
                reason=f"api_unavailable_or_error:{name}:level={min_level}-{max_level}:radius={radius}",
                url=url,
            )
            return None
        saw_positive_not_found = True
    if target_name:
        if hazard_scan_radius > 0 and hazard_token_limit > 0:
            def hazard_for_route(hazard_route: RoutePoint) -> tuple[bool | None, str, str, int]:
                all_hazard_tokens = growth_route_preflight_hazard_tokens(
                    hazard_route,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    allow_lower_xp_target_plan=bool(getattr(args, "growth_allow_lower_xp_target_plan", False))
                    and bool(getattr(args, "growth_allow_lower_xp_gear_farm", True)),
                )
                if growth_route_preflight_strict_required(
                    args,
                    route,
                    current_level=current_level,
                    party_size=party_size,
                ):
                    hazard_tokens = all_hazard_tokens
                else:
                    hazard_tokens = all_hazard_tokens[:hazard_token_limit]
                hazard_max_level = max(max_level, int(current_level or 0) + 5, 12)
                for hazard in hazard_tokens:
                    query = {
                        "region": int(realm.region),
                        "x": int(hazard_route.x),
                        "y": int(hazard_route.y),
                        "radius": hazard_scan_radius,
                        "minLevel": 1,
                        "maxLevel": hazard_max_level,
                        "limit": hazard_limit,
                        "name": hazard,
                    }
                    url = f"{endpoint}?{urllib.parse.urlencode(query)}"
                    cache_key = (
                        "hazard",
                        endpoint,
                        int(realm.region),
                        int(hazard_route.x),
                        int(hazard_route.y),
                        int(hazard_scan_radius),
                        1,
                        int(hazard_max_level),
                        int(hazard_limit),
                        hazard.lower(),
                    )
                    if cache_key in cache:
                        hazard_status = cache[cache_key]
                    else:
                        payload = fetch_growth_route_preflight_payload(url, timeout)
                        if payload is None:
                            hazard_status = None
                        else:
                            hazard_status = growth_route_preflight_payload_has_items(payload)
                        cache[cache_key] = hazard_status
                    if hazard_status is True:
                        return True, hazard, url, hazard_max_level
                    if hazard_status is None:
                        return None, hazard, url, hazard_max_level
                return False, "", "", hazard_max_level

            hazard_route = growth_route_preflight_adjusted_route(
                args,
                route,
                realm=realm,
                current_level=current_level,
                party_size=party_size,
            )
            hazard_status, hazard, url, hazard_max_level = hazard_for_route(hazard_route)
            if hazard_status is True and target_anchor_items:
                for item in growth_route_preflight_anchor_pool(
                    args,
                    route,
                    target_anchor_items,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                ):
                    candidate_route = growth_route_preflight_item_route(route, item)
                    if candidate_route is None:
                        continue
                    if int(candidate_route.x) == int(hazard_route.x) and int(candidate_route.y) == int(hazard_route.y):
                        continue
                    candidate_hazard_status, _candidate_hazard, _candidate_url, _candidate_hazard_max = hazard_for_route(
                        candidate_route
                    )
                    if candidate_hazard_status is False:
                        store_growth_route_preflight_anchor_route(
                            args,
                            route,
                            candidate_route,
                            realm_key=realm.key,
                            current_level=current_level,
                            party_size=party_size,
                        )
                        log_growth_route_preflight(
                            args,
                            realm_key=realm.key,
                            current_level=current_level,
                            party_size=party_size,
                            route=candidate_route,
                            status="warn",
                            reason=(
                                f"live_hazard_anchor_replaced:{hazard}:"
                                f"from={hazard_route.x},{hazard_route.y}:"
                                f"target={target_name}:radius={hazard_radius}"
                            ),
                            url=url,
                        )
                        hazard_status, hazard, url, hazard_max_level = False, "", "", _candidate_hazard_max
                        break
            if hazard_status is True:
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    route=hazard_route,
                    status="skip",
                    reason=(
                        f"live_hazard_present:{hazard}:level=1-{hazard_max_level}:"
                        f"radius={hazard_scan_radius}:target={target_name}"
                    ),
                    url=url,
                )
                return False
            if hazard_status is None:
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=current_level,
                    party_size=party_size,
                    route=hazard_route,
                    status="unknown",
                    reason=(
                        f"hazard_api_unavailable_or_error:{hazard}:level=1-{hazard_max_level}:"
                        f"radius={hazard_scan_radius}:target={target_name}"
                    ),
                    url=url,
                )
                return None
        log_growth_route_preflight(
            args,
            realm_key=realm.key,
            current_level=current_level,
            party_size=party_size,
            route=growth_route_preflight_adjusted_route(
                args,
                route,
                realm=realm,
                current_level=current_level,
                party_size=party_size,
            ),
            status="ok",
            reason=f"live_target_present:{target_name}:level={min_level}-{max_level}:radius={radius}",
            url=target_url,
        )
        return True
    if saw_positive_not_found:
        log_growth_route_preflight(
            args,
            realm_key=realm.key,
            current_level=current_level,
            party_size=party_size,
            route=route,
            status="skip",
            reason=f"live_target_missing:level={min_level}-{max_level}:radius={radius}",
        )
        return False
    return None


def growth_route_preflight_allows(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
) -> bool:
    return growth_route_preflight_status(
        args,
        route,
        realm=realm,
        current_level=current_level,
        party_size=party_size,
    ) is not False


def low_alb_solo_level_seven_route(args: argparse.Namespace, level: int, party_size: int) -> RoutePoint:
    failed_tokens = preferred_target_tokens(
        growth_failed_target_memory_avoid_targets(args, "alb", int(level or 0), int(party_size or 0))
    )
    no_engagement_count = growth_runtime_failure_memory_downgrade_count(
        args,
        "alb",
        int(level or 0),
        int(party_size or 0),
    )
    if target_name_matches_any("emerald snake", failed_tokens):
        return route_point(
            7,
            595117,
            506793,
            2562,
            "dragon ant worker",
            "dragon ant soldier,노련한 dragon ant soldier,노련한 dragon ant worker,adder,노련한 adder,veteran adder,spirit,노련한 spirit,bandit,노련한 도적,rot worm,veteran rot worm,노련한 rot worm,faerie bell-wether,zombie boar,tree spirit,giant spider,young cutpurse,river sprite,emerald snake,undead filidh,dappled lynx cub,brownie nomad",
            "Castle Sauvage",
            source="hunting-index",
            mob_level=5,
            mob_count=30,
        )
    if target_name_matches_any("rot worm", failed_tokens) or no_engagement_count >= 2:
        return route_point(
            7,
            491304,
            592010,
            1793,
            "emerald snake",
            "rot worm,veteran rot worm,노련한 rot worm,faerie bell-wether,zombie boar,tree spirit,giant spider,adder,young cutpurse,river sprite,bandit,undead filidh,dappled lynx cub",
            "Campacorentin Station",
            source="hunting-index",
            mob_level=5,
            mob_count=20,
        )
    prefer = "rot worm"
    avoid = "faerie bell-wether,emerald snake,zombie boar,tree spirit,giant spider,young cutpurse,river sprite,bandit,undead filidh"
    routes = (
        route_point(
            7,
            464792,
            645770,
            1699,
            prefer,
            avoid,
            "Avalon Marsh",
            source="hunting-index",
            mob_level=6,
            mob_count=28,
        ),
        route_point(
            7,
            464792,
            645770,
            1699,
            prefer,
            avoid,
            "Avalon Marsh",
            source="hunting-index",
            mob_level=6,
            mob_count=28,
        ),
        route_point(
            7,
            464792,
            645770,
            1699,
            prefer,
            avoid,
            "Avalon Marsh",
            source="hunting-index",
            mob_level=6,
            mob_count=28,
        ),
        route_point(
            7,
            464792,
            645770,
            1699,
            prefer,
            avoid,
            "Avalon Marsh",
            source="hunting-index",
            mob_level=6,
            mob_count=28,
        ),
    )
    return routes[
        growth_route_selection_index(
            args,
            realm_key="alb",
            level=int(level or 0),
            party_size=int(party_size or 0),
            modulo=len(routes),
            salt="low-alb-solo-seven",
        )
    ]


def low_alb_solo_level_eight_route(args: argparse.Namespace, level: int, party_size: int) -> RoutePoint:
    failed_tokens = preferred_target_tokens(
        growth_failed_target_memory_avoid_targets(args, "alb", int(level or 0), int(party_size or 0))
    )
    no_engagement_count = growth_runtime_failure_memory_downgrade_count(
        args,
        "alb",
        int(level or 0),
        int(party_size or 0),
    )
    if target_name_matches_any("rot worm", failed_tokens) or no_engagement_count >= 1:
        return route_point(
            8,
            600781,
            529920,
            3234,
            "undead filidh",
            "tree spirit,emerald snake,giant spider,dappled lynx cub,bogman grappler,bandit,shady pilferer,spriggarn stalker,skeleton,worker ant,faerie bell-wether,young cutpurse,Heretical Hermit,large skeleton,sylvan goblin hunter,river sprite,rot worm",
            "Prydwen Keep",
            source="hunting-index",
            mob_level=6,
            mob_count=8,
        )
    return route_point(
        8,
        486334,
        592350,
        1821,
        "rot worm",
        "tree spirit,emerald snake,giant spider,dappled lynx cub,bogman grappler,bandit,shady pilferer,spriggarn stalker,skeleton,worker ant,faerie bell-wether,young cutpurse,Heretical Hermit,large skeleton,sylvan goblin hunter,river sprite",
        "Campacorentin Station",
        source="hunting-index",
        mob_level=6,
        mob_count=2,
    )


def low_alb_solo_level_nine_route(args: argparse.Namespace, level: int, party_size: int) -> RoutePoint:
    current_level = int(level or 0)
    current_party_size = int(party_size or 0)
    failed_tokens = preferred_target_tokens(
        growth_failed_target_memory_avoid_targets(args, "alb", current_level, current_party_size)
    )
    river_racer_failed = any(
        growth_failure_memory_target_phrase_matches(token, "river racer")
        for token in failed_tokens
    ) or growth_runtime_failure_memory_has_hard_target_failure(
        args,
        "alb",
        current_level,
        current_party_size,
        "river racer",
    )
    undead_filidh_failed = any(
        growth_failure_memory_target_phrase_matches(token, "undead filidh")
        for token in failed_tokens
    ) or growth_runtime_failure_memory_has_hard_target_failure(
        args,
        "alb",
        current_level,
        current_party_size,
        "undead filidh",
    )
    rotting_zombie_failed = any(
        growth_failure_memory_target_phrase_matches(token, "rotting zombie")
        for token in failed_tokens
    ) or growth_runtime_failure_memory_has_hard_target_failure(
        args,
        "alb",
        current_level,
        current_party_size,
        "rotting zombie",
    )
    if rotting_zombie_failed:
        return route_point(
            9,
            513958,
            638406,
            2416,
            "sylvan goblin hunter",
            "rotting zombie,forest bear,undead filidh,river racer,bandit,spirit,giant spider,adder,young cutpurse,fading spirit,spectral hound,large skeleton,tree spirit,dryad,filidh,ant drone,devout filidh,pixie scout,픽시 정찰병,faerie bell-wether",
            "Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
            mob_count=1,
        )
    if undead_filidh_failed:
        return route_point(
            9,
            527242,
            624780,
            1971,
            "rotting zombie",
            "forest bear,undead filidh,river racer,bandit,spirit,giant spider,adder,young cutpurse,fading spirit,spectral hound,large skeleton,tree spirit,dryad,filidh,ant drone,devout filidh,pixie scout,픽시 정찰병,faerie bell-wether",
            "Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
            mob_count=2,
        )
    if river_racer_failed:
        return route_point(
            9,
            518282,
            609298,
            2155,
            "undead filidh",
            "river racer,bandit,spirit,giant spider,adder,young cutpurse,fading spirit,spectral hound,large skeleton,forest bear,tree spirit,dryad,ant drone,devout filidh,pixie scout,픽시 정찰병,faerie bell-wether",
            "Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
            mob_count=6,
        )
    return route_point(
        9,
        592858,
        549006,
        2762,
        "river racer",
        "large skeleton,emerald snake,faerie bell-wether,giant spider,tree spirit,bandit,spirit,cutpurse,dragon ant soldier,river sprite,rot worm,adder,veteran adder,노련한 adder,filidh,devout filidh,brownie,manes demon",
        "Prydwen Keep",
        source="hunting-index",
        mob_level=7,
        mob_count=13,
    )


def low_alb_solo_level_ten_route(args: argparse.Namespace, level: int, party_size: int) -> RoutePoint:
    current_level = int(level or 0)
    current_party_size = int(party_size or 0)
    clean_level_ten_start = (
        current_level == 10
        and current_party_size <= 1
        and (
            current_level in [int(checkpoint) for checkpoint in getattr(args, "checkpoint_levels_parsed", []) or []]
            or (
                int(getattr(args, "reset_level", 0) or 0) == 10
                and int(getattr(args, "growth_current_segment_index", 0) or 0) <= 1
                and not bool(getattr(args, "resume", False))
            )
        )
    )
    adder_failed = growth_runtime_failure_memory_has_hard_target_failure(
        args,
        "alb",
        current_level,
        current_party_size,
        "adder",
    )
    rotting_zombie_failed = growth_runtime_failure_memory_has_hard_target_failure(
        args,
        "alb",
        current_level,
        current_party_size,
        "rotting zombie",
    )
    forest_lion_failed = growth_runtime_failure_memory_has_hard_target_failure(
        args,
        "alb",
        current_level,
        current_party_size,
        "forest lion",
    )
    bear_failed = growth_runtime_failure_memory_has_hard_target_failure(
        args,
        "alb",
        current_level,
        current_party_size,
        "bear",
    )
    if forest_lion_failed and bear_failed:
        return route_point(
            10,
            440220,
            619503,
            1863,
            "river racer",
            "bear,forest bear,forest lion,forest cat,rotting zombie,undead filidh,bandit,spirit,giant spider,adder,young cutpurse,fading spirit,spectral hound,large skeleton,tree spirit,dryad,filidh,ant drone,devout filidh,pixie scout,픽시 정찰병,faerie bell-wether",
            "Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
            mob_count=2,
        )
    if clean_level_ten_start:
        return route_point(
            10,
            527242,
            624780,
            1971,
            "rotting zombie",
            "death grip vines,bloody-bones,river racer,bear,forest bear,forest lion,forest cat,undead filidh,bandit,spirit,giant spider,adder,young cutpurse,fading spirit,spectral hound,large skeleton,tree spirit,dryad,filidh,ant drone,devout filidh,pixie scout,픽시 정찰병,faerie bell-wether",
            "Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
            mob_count=2,
        )
    if forest_lion_failed:
        return route_point(
            10,
            552382,
            557133,
            3149,
            "bear",
            "forest lion,forest cat,rotting zombie,undead filidh,river racer,bandit,spirit,giant spider,adder,young cutpurse,fading spirit,spectral hound,large skeleton,tree spirit,dryad,filidh,ant drone,devout filidh,pixie scout,픽시 정찰병,faerie bell-wether",
            "Prydwen Keep",
            source="hunting-index",
            mob_level=8,
            mob_count=10,
        )
    if rotting_zombie_failed:
        return route_point(
            10,
            496809,
            640112,
            1877,
            "forest lion",
            "forest cat,rotting zombie,forest bear,undead filidh,river racer,bandit,spirit,giant spider,adder,young cutpurse,fading spirit,spectral hound,large skeleton,tree spirit,dryad,filidh,ant drone,devout filidh,pixie scout,픽시 정찰병,faerie bell-wether",
            "Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
            mob_count=3,
        )
    if adder_failed:
        return route_point(
            10,
            527242,
            624780,
            1971,
            "rotting zombie",
            "forest bear,undead filidh,river racer,bandit,spirit,giant spider,adder,young cutpurse,fading spirit,spectral hound,large skeleton,tree spirit,dryad,filidh,ant drone,devout filidh,pixie scout,픽시 정찰병,faerie bell-wether",
            "Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
            mob_count=2,
        )
    return select_route_point(REALMS["alb"], 10, party_size)


def growth_objective_entry_aggro_avoid_radius(
    current_level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint,
) -> float:
    if (
        realm_key == "alb"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("river racer", preferred_target_tokens(route.prefer))
    ):
        return 1600.0
    if (
        realm_key == "alb"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("rotting zombie", preferred_target_tokens(route.prefer))
    ):
        return 2200.0
    if (
        realm_key == "alb"
        and int(current_level or 0) == 9
        and int(party_size or 0) <= 1
        and (
            target_name_matches_any("adder", preferred_target_tokens(route.prefer))
            or target_name_matches_any("river racer", preferred_target_tokens(route.prefer))
        )
    ):
        return 1800.0
    if (
        realm_key == "alb"
        and int(current_level or 0) == 9
        and int(party_size or 0) <= 1
        and (
            target_name_matches_any("undead filidh", preferred_target_tokens(route.prefer))
            or target_name_matches_any("rotting zombie", preferred_target_tokens(route.prefer))
            or target_name_matches_any("sylvan goblin hunter", preferred_target_tokens(route.prefer))
        )
    ):
        return 2200.0
    if (
        realm_key == "alb"
        and int(current_level or 0) == 10
        and int(party_size or 0) <= 1
        and (
            target_name_matches_any("rotting zombie", preferred_target_tokens(route.prefer))
            or target_name_matches_any("sylvan goblin hunter", preferred_target_tokens(route.prefer))
        )
    ):
        return 2200.0
    if (
        realm_key == "alb"
        and int(current_level or 0) == 10
        and int(party_size or 0) <= 1
        and target_name_matches_any("adder", preferred_target_tokens(route.prefer))
    ):
        return 2200.0
    if (
        realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and (
            target_name_matches_any("large sveawolf", preferred_target_tokens(route.prefer))
            or target_name_matches_any("spindly rock crab", preferred_target_tokens(route.prefer))
            or target_name_matches_any("tawny lynx", preferred_target_tokens(route.prefer))
            or target_name_matches_any("svartalf outcast", preferred_target_tokens(route.prefer))
        )
    ):
        return 1800.0
    if (
        realm_key == "hib"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and (
            target_name_matches_any("barca", preferred_target_tokens(route.prefer))
            or target_name_matches_any("water beetle", preferred_target_tokens(route.prefer))
        )
    ):
        return 1800.0
    return 0.0


def is_alb_duo_level_ten_river_racer_route(
    level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint | None,
) -> bool:
    return bool(
        str(realm_key or "").strip().lower() == "alb"
        and int(level or 0) == 10
        and int(party_size or 0) == 2
        and route is not None
        and target_name_matches_any("river racer", preferred_target_tokens(getattr(route, "prefer", "")))
    )


def is_alb_duo_level_ten_low_power_carry_route(
    level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint | None,
) -> bool:
    return bool(
        str(realm_key or "").strip().lower() == "alb"
        and int(level or 0) == 10
        and int(party_size or 0) == 2
        and route is not None
        and (
            target_name_matches_any("river racer", preferred_target_tokens(getattr(route, "prefer", "")))
            or target_name_matches_any("rotting zombie", preferred_target_tokens(getattr(route, "prefer", "")))
        )
    )


def is_mid_duo_level_ten_tawny_lynx_route(
    level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint | None,
) -> bool:
    return bool(
        str(realm_key or "").strip().lower() == "mid"
        and int(level or 0) in {9, 10}
        and int(party_size or 0) == 2
        and route is not None
        and target_name_matches_any("tawny lynx", preferred_target_tokens(getattr(route, "prefer", "")))
    )


def is_mid_duo_level_ten_short_engage_route(
    level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint | None,
) -> bool:
    return bool(
        str(realm_key or "").strip().lower() == "mid"
        and int(level or 0) in {9, 10}
        and int(party_size or 0) == 2
        and route is not None
        and getattr(route, "source", "") == "hunting-index"
    )


def growth_target_nearby_avoid_names_for_route(
    current_level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint,
) -> str:
    if (
        realm_key == "alb"
        and int(current_level or 0) in {9, 10}
        and int(party_size or 0) <= 1
        and target_name_matches_any("river racer", preferred_target_tokens(route.prefer))
    ):
        return "river racer"
    if (
        realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) <= 1
        and target_name_matches_any("rock crab", preferred_target_tokens(route.prefer))
    ):
        return "army ant worker,army ant soldier,black mauler juvenile,roaming thrall"
    if (
        realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) <= 1
        and target_name_matches_any("nordic dirge", preferred_target_tokens(route.prefer))
    ):
        return "roaming dirge,lake serpent,rock crab,black mauler juvenile"
    if (
        realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("tomte", preferred_target_tokens(route.prefer))
    ):
        return "tomte aggressor,tomte skirmisher,tomte pillager,tomte plunderer"
    if (
        realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("large sveawolf", preferred_target_tokens(route.prefer))
    ):
        return "black mauler,blodfelag,lake serpent,ribbon toad,water sprite,army ant soldier,ghost light,host of the wind,seithr orb"
    if (
        realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("spindly rock crab", preferred_target_tokens(route.prefer))
    ):
        return "rock crab,carrion crawler,ghost light,wind wisp,army ant soldier,large sveawolf,lake serpent,host of the wind,seithr orb,black mauler,blodfelag"
    if (
        realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("hobgoblin prowler", preferred_target_tokens(route.prefer))
    ):
        return "노련한,돌연변이,흉포한,우두머리,정예,챔피언,ghost light,nacken,haunt,wind wisp,seithr orb,svartalf guard,svartalf outcast"
    if (
        realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("manes demon", preferred_target_tokens(route.prefer))
    ):
        return "노련한,돌연변이,흉포한,우두머리,정예,챔피언,hill cat,small hill cat,grumoz demon"
    if (
        realm_key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("tawny lynx", preferred_target_tokens(route.prefer))
    ):
        return "노련한,돌연변이,흉포한,우두머리,정예,챔피언,tawny lynx cub,young lynx,green serpent,nacken,wolf spiderling,wind wisp,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,wood-eater alate,small hill cat"
    if (
        realm_key == "hib"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("barca", preferred_target_tokens(route.prefer))
    ):
        return "red wolfhound,wild lucradan,badger,young badger,anger sprite,ghostly siabra,ghastly siabra,curmudgeon,lough wolf,large eirebug"
    if (
        realm_key == "hib"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("water beetle", preferred_target_tokens(route.prefer))
    ):
        return "lunantishee,blackthorn,Clik,lough wolf,red wolfhound,ghostly siabra,rat boy,badger,young badger"
    return ""


def growth_runtime_target_nearby_avoid_names_for_route(
    current_level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint,
    *,
    allow_lower_xp_target_plan: bool = False,
) -> str:
    return merge_target_name_csv(
        growth_avoid_targets_for_current_context(
            route,
            realm_key,
            current_level,
            party_size,
            allow_lower_xp_target_plan=allow_lower_xp_target_plan,
        ),
        growth_target_nearby_avoid_names_for_route(
            current_level,
            party_size,
            realm_key,
            route,
        ),
    )


def low_mid_solo_level_ten_route(args: argparse.Namespace, level: int, party_size: int) -> RoutePoint:
    return route_point(
        10,
        721568,
        750610,
        4552,
        "nordic dirge",
        "tomte skirmisher,tomte thug,tomte pillager,tomte plunderer,Brut,host of the earth,hill person,ghost light,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,wood-eater alate,small hill cat,wind wisp,envy drakeling",
        "Audliten",
        source="hunting-index",
        mob_level=7,
        mob_count=1,
    )


def low_hib_solo_level_seven_route(args: argparse.Namespace, level: int, party_size: int) -> RoutePoint:
    low_avoid = "water beetle,water beetle collector,minor changeling,eriu waylayer,rat boy,lough wolf,red wolfhound,underhill companion,wolf cub,wild crouch,spraggon,spraggonoll,villainous youth"
    level_six_avoid = f"{low_avoid},eirebug"
    level_nine_avoid = "water beetle,water beetle collector,hill toad,lugradan whelp,minor changeling,eriu waylayer,red wolfhound,underhill companion,wolf cub,wild crouch,spraggon,spraggonoll,villainous youth"
    allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
        getattr(args, "growth_allow_lower_xp_gear_farm", True)
    )
    if allow_lower_xp_target_plan and int(level or 0) == 7:
        routes = (
            route_point(
                7,
                329667,
                470837,
                5616,
                "eirebug",
                low_avoid,
                "",
                source="hunting-index",
                mob_level=5,
                mob_count=18,
            ),
        )
    elif int(level or 0) == 8:
        routes = (
            route_point(
                7,
                309663,
                647096,
                5234,
                "hill toad",
                level_six_avoid,
                "Shannon Estuary",
                source="hunting-index",
                mob_level=6,
                mob_count=37,
            ),
            route_point(
                7,
                314344,
                631044,
                5037,
                "hill toad",
                level_six_avoid,
                "Shannon Estuary",
                source="hunting-index",
                mob_level=6,
                mob_count=16,
            ),
            route_point(
                7,
                307930,
                634160,
                4972,
                "lugradan whelp",
                level_six_avoid,
                "Shannon Estuary",
                source="hunting-index",
                mob_level=6,
                mob_count=12,
            ),
        )
    elif int(level or 0) >= 9:
        routes = (
            route_point(
                9,
                349869,
                494579,
                5191,
                "lough wolf",
                level_nine_avoid,
                "Mag Mell",
                source="hunting-index",
                mob_level=7,
                mob_count=3,
            ),
            route_point(
                9,
                348590,
                491555,
                5746,
                "rat boy",
                level_nine_avoid,
                "Mag Mell",
                source="hunting-index",
                mob_level=8,
                mob_count=3,
            ),
        )
    else:
        routes = (
            route_point(
                7,
                309663,
                647096,
                5234,
                "hill toad",
                level_six_avoid,
                "Shannon Estuary",
                source="hunting-index",
            ),
            route_point(
                7,
                307930,
                634160,
                4972,
                "lugradan whelp",
                level_six_avoid,
                "Shannon Estuary",
                source="hunting-index",
            ),
        )
    return routes[
        growth_route_selection_index(
            args,
            realm_key="hib",
            level=int(level or 0),
            party_size=int(party_size or 0),
            modulo=len(routes),
            salt="low-hib-solo-seven",
        )
    ]


def preferred_growth_hunting_candidates(realm_key: str, level: int, party_size: int) -> tuple[str, ...]:
    if realm_key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 8:
        return ("bandit",)
    if realm_key == "alb" and int(party_size or 0) == 2 and int(level or 0) == 7:
        return ("rot worm", "gray wolf", "small bear", "faerie bell-wether")
    if realm_key == "alb" and int(party_size or 0) == 2 and int(level or 0) in {6, 7, 8}:
        return ("rot worm", "emerald snake", "small bear", "gray wolf", "tree spirit")
    if realm_key == "alb" and 4 <= int(party_size or 0) < 8 and int(level or 0) == 6:
        return ("emerald snake", "faerie bell-wether", "zombie boar", "gray wolf", "small bear")
    if realm_key == "alb" and 4 <= int(party_size or 0) < 8 and int(level or 0) in {4, 5}:
        return ("gray wolf", "small bear", "emerald snake", "tree spirit", "rot worm")
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(level or 0) == 9:
        return ("red wolfhound", "water beetle", "large eirebug", "lough wolf")
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(level or 0) in {7, 8}:
        return ("water beetle", "large eirebug", "red wolfhound", "lough wolf")
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(level or 0) == 1:
        return ("water beetle larva",)
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) == 1:
        return ("black wolf pup", "boar piglet", "green snake")
    if realm_key == "hib" and int(party_size or 0) == 4 and int(level or 0) == 9:
        return ("lough wolf", "hill toad", "large eirebug", "badger")
    if realm_key == "hib" and int(party_size or 0) == 4 and int(level or 0) in {7, 8}:
        return ("hill toad", "lugradan whelp", "water beetle")
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) <= 3:
        return ("skeleton", "spriggarn", "decayed zombie", "black wolf pup")
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) == 4:
        return ("rot worm", "gray wolf", "small bear", "ant drone", "bandit")
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) == 5:
        return ("gray wolf", "emerald snake", "small bear", "rot worm")
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) == 6:
        return ("ant drone", "rot worm", "gray wolf", "small bear", "bandit")
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) == 7:
        return ("ant drone", "bandit", "rot worm", "gray wolf", "small bear")
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) == 8:
        return ("ant drone", "bandit", "rot worm", "gray wolf", "small bear")
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) == 9:
        return ("red dwarf leader", "will o' wisp", "bear", "devout filidh", "wild boar")
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 7:
        return ("carrion crawler", "young grendelorm", "vein spider")
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 6:
        return ("wayward ghoul", "dryad sprig", "rugged dwarven pony", "skeletal seafarer")
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 8:
        return ("carrion crawler", "army ant worker")
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return ("ghost light", "wood-eater alate", "host of the wind")
    if realm_key == "mid" and int(party_size or 0) == 4 and int(level or 0) == 9:
        return ("army ant soldier", "lake serpent", "seithr orb", "black mauler juvenile")
    if realm_key == "hib" and int(party_size or 0) == 4 and int(level or 0) == 10:
        return ("red wolfhound", "large eirebug", "ghostly siabra", "anger sprite")
    if realm_key == "mid" and int(party_size or 0) >= 8 and int(level or 0) in {6, 7, 8, 9}:
        return ("lake serpent", "army ant soldier", "seithr orb", "black mauler juvenile")
    if realm_key == "mid" and int(party_size or 0) == 2 and int(level or 0) == 4:
        return ("wood-eater", "wood-eater worker", "wayward ghoul", "hobgoblin prankster")
    if realm_key == "mid" and int(party_size or 0) == 2 and int(level or 0) == 7:
        return ("black mauler juvenile", "carrion crawler", "vein spider", "young grendelorm")
    if realm_key == "mid" and int(party_size or 0) == 2 and int(level or 0) == 6:
        return ("wood-eater worker", "wood-eater hunter", "vein spider", "young grendelorm")
    if realm_key == "mid" and int(party_size or 0) == 4 and int(level or 0) == 7:
        return ("army ant soldier", "lake serpent", "ghost light", "tawny lynx cub")
    if realm_key == "mid" and int(party_size or 0) >= 8 and int(level or 0) in {3, 4}:
        return ("wood-eater", "hobgoblin prankster", "wood-eater worker")
    if realm_key == "mid" and int(party_size or 0) == 4 and int(level or 0) <= 4:
        return ("wood-eater", "wood-eater worker", "hobgoblin prankster", "wayward ghoul", "black mauler juvenile")
    if realm_key == "mid" and int(party_size or 0) in {2, 4} and int(level or 0) <= 4:
        return ("wood-eater", "hobgoblin prankster", "wild hog", "army ant worker", "wayward ghoul")
    if realm_key == "mid" and int(party_size or 0) in {2, 4} and int(level or 0) in {5, 6}:
        return ("wood-eater worker", "wood-eater", "phantom hound", "young grendelorm", "black mauler juvenile")
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 7:
        return ("eirebug",)
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 8:
        return ("hill toad", "lugradan whelp")
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 6:
        return ("hill toad", "lugradan whelp")
    if realm_key == "hib" and int(party_size or 0) == 2 and int(level or 0) == 8:
        return ("rat boy", "lough wolf")
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return ("lough wolf", "rat boy")
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 10:
        return ("hill toad", "lugradan whelp", "lough wolf", "rat boy")
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 11:
        return ("hill toad", "lough wolf", "large eirebug")
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(level or 0) in {2, 3}:
        return ("large frog", "water beetle larva", "skeletal pawn", "badger cub", "water beetle collector")
    if realm_key == "hib" and int(party_size or 0) in {2, 4} and int(level or 0) in {4, 5}:
        return ("mudman", "small freshwater crab")
    if realm_key == "hib" and int(party_size or 0) in {2, 4} and int(level or 0) == 6:
        return ("hill toad", "lugradan whelp", "mudman", "small freshwater crab")
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(level or 0) in {4, 5}:
        return ("mudman", "small freshwater crab", "villainous youth", "water beetle collector", "spraggon", "water beetle")
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(level or 0) == 6:
        return ("mudman", "small freshwater crab", "water beetle collector", "spraggon", "hill toad")
    if realm_key == "mid" and int(party_size or 0) == 4 and int(level or 0) <= 3:
        return ("wild hog", "hobgoblin snagger", "water strider", "rattling skeleton", "hobgoblin prankster")
    if realm_key == "hib" and int(party_size or 0) == 4 and int(level or 0) <= 3:
        return ("large frog", "water beetle larva", "skeletal pawn", "minor changeling", "badger cub")
    if realm_key == "mid" and int(level or 0) == 5 and int(party_size or 0) >= 8:
        return ("carrion crawler", "ghost light", "army ant soldier", "wind wisp")
    if realm_key == "hib" and int(level or 0) == 1 and int(party_size or 0) <= 2:
        return ("water beetle larva", "annoying lucradan", "badger cub")
    if realm_key == "hib" and int(level or 0) == 3 and int(party_size or 0) <= 1:
        return ("water beetle larva", "skeletal pawn", "large frog", "sand crab")
    if realm_key == "hib" and int(level or 0) == 4 and int(party_size or 0) <= 1:
        return ("lough wolf cadger", "haunted driftwood", "skeletal pawn", "minor changeling", "beach rat", "mudman")
    return ()


def preferred_growth_carry_hunting_candidates(realm_key: str, target_level: int, party_size: int) -> tuple[str, ...]:
    if realm_key == "hib" and int(party_size or 0) == 2 and int(target_level or 0) <= 1:
        return ("large frog", "water beetle larva", "badger cub")
    if realm_key == "hib" and int(party_size or 0) == 2 and int(target_level or 0) <= 2:
        return ("skeletal pawn", "large frog", "water beetle larva")
    if realm_key == "hib" and int(party_size or 0) in {2, 4} and int(target_level or 0) <= 4:
        return ("mudman", "small freshwater crab")
    if realm_key == "hib" and int(party_size or 0) in {2, 4} and int(target_level or 0) == 5:
        return ("mudman", "small freshwater crab")
    if realm_key == "hib" and int(party_size or 0) in {2, 4} and int(target_level or 0) == 6:
        return ("water beetle", "hill toad", "lugradan whelp")
    if realm_key == "hib" and int(party_size or 0) == 2 and int(target_level or 0) == 8:
        return ("water beetle", "lough wolf", "rat boy")
    if realm_key == "hib" and int(party_size or 0) in {2, 4} and int(target_level or 0) == 7:
        return ("hill toad", "lugradan whelp")
    if realm_key == "hib" and int(party_size or 0) == 2 and int(target_level or 0) in {9, 10}:
        return ("lough wolf", "eirebug", "large eirebug", "water beetle")
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(target_level or 0) in {7, 8}:
        return ("red wolfhound", "lough wolf", "water beetle")
    if realm_key == "mid" and int(party_size or 0) == 2 and int(target_level or 0) in {9, 10}:
        return ("army ant soldier",)
    if realm_key == "mid" and int(party_size or 0) == 2 and int(target_level or 0) == 11:
        return ("lake serpent", "army ant soldier", "seithr orb")
    if realm_key == "mid" and int(party_size or 0) == 4 and int(target_level or 0) in {8, 9}:
        return ("army ant soldier",)
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(target_level or 0) <= 5:
        return ("small freshwater crab", "mudman", "hill toad")
    if realm_key == "mid" and int(party_size or 0) >= 8 and int(target_level or 0) <= 4:
        return ("wood-eater worker", "wayward ghoul", "dryad sprig")
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(target_level or 0) <= 4:
        return ("gray wolf", "small bear", "skeleton", "spriggarn", "decayed zombie")
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(target_level or 0) <= 6:
        return ("ant drone", "bandit", "worker ant", "gray wolf", "small bear")
    return ()


def growth_party_carry_target_level_for_realm(
    tracked_level: int,
    party_size: int,
    realm_key: str = "",
) -> int:
    realm = str(realm_key or "").lower()
    party = int(party_size or 0)
    level = max(1, int(tracked_level or 1))
    if realm == "mid" and party in {2, 4} and level <= 6:
        return 5
    if realm == "mid" and party in {2, 4} and level == 7:
        return 6
    if realm == "mid" and party >= 8 and level <= 5:
        return 4
    if realm == "alb" and 2 <= party <= 4 and level <= 7:
        return 6
    if realm == "alb" and party == 2 and level == 10:
        return 8
    if str(realm_key or "").lower() == "hib" and int(party_size or 0) == 2 and int(tracked_level or 0) <= 2:
        return max(1, int(tracked_level or 1))
    if str(realm_key or "").lower() == "mid" and int(party_size or 0) >= 8 and int(tracked_level or 0) <= 2:
        return 12
    return growth_party_carry_target_level(tracked_level, party_size)


def growth_hunting_index_avoid_targets(realm_key: str, level: int, party_size: int) -> str:
    if realm_key == "hib" and int(party_size or 0) <= 2 and int(level or 0) == 1:
        return "large frog,skeletal pawn,feccan,ambient,Lance Settler,lunantishee,blackthorn"
    if realm_key == "hib" and int(party_size or 0) == 2 and int(level or 0) == 6:
        return "orchard nipper,blackthorn"
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(level or 0) == 1:
        return "large frog,skeletal pawn,badger cub,feccan,annoying lucradan,blackthorn,lunantishee,ambient,Lance Settler,hazard,red wolfhound,large eirebug,underhill companion,wolf cub"
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) == 1:
        return "skeleton,spriggarn,spriggarn elder,decayed zombie,small bear,gray wolf"
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(level or 0) == 9:
        return "blackthorn,lunantishee,feccan,ambient,Lance Settler,hazard,lough wolf,cluricaun trip,spraggonoll,large eirebug,underhill companion,wolf cub"
    if realm_key == "hib" and int(party_size or 0) >= 8 and int(level or 0) <= 10:
        return "blackthorn,lunantishee,feccan,ambient,Lance Settler,hazard,red wolfhound,large eirebug,underhill companion,wolf cub"
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) in {6, 7, 8}:
        return "filidh,devout filidh,bear,wild boar,poacher,brownie nomad,boulderling,undead goblin warrior,large skeleton,tree spirit,giant spider,adder"
    if realm_key == "alb" and int(party_size or 0) >= 8 and int(level or 0) == 9:
        return "cart horse,slave,wild boar,poacher,brownie nomad,bandit,boulderling,undead goblin warrior,large skeleton"
    if realm_key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 8:
        return "giant spider,tree spirit,worker ant,young cutpurse,large skeleton,sylvan goblin hunter,river sprite"
    if realm_key == "alb" and int(party_size or 0) == 2 and int(level or 0) == 7:
        return "tree spirit,bandit,ant drone,giant spider,adder,young cutpurse"
    if realm_key == "alb" and int(party_size or 0) == 2 and int(level or 0) == 4:
        return "dappled lynx cub"
    if realm_key == "alb" and int(party_size or 0) == 2 and int(level or 0) in {6, 8}:
        return "faerie bell-wether,ant drone,tree spirit,giant spider,adder,dappled lynx cub"
    if realm_key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 10:
        return "giant spider,bandit henchman,moldy skeleton,goblin scout,spectral hound,Slith,tree spirit,shady pilferer,spriggarn stalker,skeleton,rot worm,emerald snake,faerie bell-wether,young cutpurse"
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return "haunt,svartalf,svartalf outcast,nacken,wolf spiderling,wind wisp,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,small hill cat,tawny lynx cub,vein spiderling,young lynx,green serpent"
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 8:
        return "host of the earth,hill person,nordic dirge,ghost light,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,wood-eater alate,small hill cat"
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 7:
        return "black mauler juvenile,wood-eater worker,wood-eater,wood-eater hunter,wayward ghoul,dryad sprig,wolf spiderling,hill person,army ant worker,rock crab,roaming thrall,wood-eater soldier,wood-eater alate,wood-eater king,huldu,small hill cat,sapherd,pine imp,ghost light,haunt,roaming dirge,carrion eater,tawny lynx"
    if realm_key == "mid" and int(party_size or 0) == 2 and int(level or 0) == 7:
        return "ghost light,wood-eater,wood-eater alate,wood-eater hunter,wood-eater king,wood-eater soldier"
    if realm_key == "mid" and int(party_size or 0) == 2 and int(level or 0) == 6:
        return "black mauler juvenile,wood-eater worker,wood-eater,wood-eater hunter,wayward ghoul,dryad sprig,wolf spiderling,hill person,army ant worker,rock crab,roaming thrall,wood-eater soldier,wood-eater alate,wood-eater king,huldu,small hill cat"
    if realm_key == "mid" and int(party_size or 0) == 4 and int(level or 0) == 7:
        return "ghost light,host of the wind,wind wisp,wolf spiderling,black mauler juvenile,vein spider,huldu,small hill cat"
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return "water beetle,water beetle collector,hill toad,lugradan whelp,red wolfhound,eriu waylayer,minor changeling,wild crouch,spraggon,spraggonoll,villainous youth"
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 8:
        return "water beetle,water beetle collector,eirebug,lough wolf,red wolfhound,minor changeling,eriu waylayer,rat boy,wild crouch,spraggon,spraggonoll,villainous youth"
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) in {7, 8}:
        return "water beetle,water beetle collector,red wolfhound,minor changeling,eriu waylayer,rat boy,wild crouch,spraggon,spraggonoll,villainous youth"
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 10:
        return "lough wolf,red wolfhound,minor changeling,eriu waylayer,rat boy"
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 11:
        return "water beetle,red wolfhound,ghostly siabra,roane maiden,anger sprite"
    if realm_key == "hib" and int(party_size or 0) == 2 and int(level or 0) == 8:
        return "water beetle,minor changeling,water beetle larva,large frog,badger cub"
    if realm_key == "hib" and int(party_size or 0) == 2 and int(level or 0) == 7:
        return "underhill companion,wolf cub,lough wolf"
    if realm_key == "hib" and int(party_size or 0) == 2 and int(level or 0) in {9, 10}:
        return "water beetle,rat boy,red wolfhound,underhill companion,wolf cub,cluricaun trip,wild crouch,lough wolf"
    if realm_key == "mid" and int(party_size or 0) == 2 and int(level or 0) in {9, 10, 11}:
        return "seithr orb,black mauler juvenile,wind wisp,ghost light,host of the wind,carrion crawler,Svartmoln,wood-eater soldier,wood-eater alate,small hill cat"
    if realm_key == "hib" and int(party_size or 0) == 4 and int(level or 0) == 9:
        return "red wolfhound,water beetle,young badger,badger,underhill companion"
    if realm_key == "hib" and int(party_size or 0) == 4 and int(level or 0) == 10:
        return "anger sprite,ghostly siabra,roane maiden,fishing bear forager,lough wolf,underhill companion"
    if realm_key == "hib" and int(party_size or 0) == 4 and int(level or 0) in {7, 8}:
        return "large eirebug,red wolfhound,lough wolf,young badger,underhill companion,water beetle"
    if realm_key == "hib" and int(party_size or 0) == 4 and int(level or 0) in {5, 6}:
        return "feccan,underhill companion,wolf cub,water beetle"
    if realm_key == "alb" and 4 <= int(party_size or 0) < 8 and int(level or 0) in {7, 8}:
        return "tree spirit,wild boar,poacher,brownie nomad,bandit,boulderling,undead goblin warrior,large skeleton"
    if realm_key == "alb" and 4 <= int(party_size or 0) < 8 and int(level or 0) == 6:
        return "tree spirit,giant spider,rot worm,veteran rot worm,노련한 rot worm,adder,dappled lynx cub"
    if realm_key == "alb" and int(party_size or 0) >= 4 and int(level or 0) <= 6:
        return "adder"
    if realm_key == "mid" and int(party_size or 0) == 4 and int(level or 0) <= 4:
        return "black mauler juvenile,vein spider,huldu,small hill cat"
    if realm_key == "mid" and int(party_size or 0) in {2, 4} and int(level or 0) <= 6:
        return "black mauler juvenile,vein spider,huldu,small hill cat"
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 7:
        return "carrion crawler,vein spider,huldu,huldu hunter,huldu stalker,small hill cat"
    if realm_key == "mid" and int(party_size or 0) >= 8 and int(level or 0) in {3, 4}:
        return "wood-eater hunter,wood-eater soldier,wood-eater royal guard,young grendelorm,huldu,huldu hunter,huldu stalker,small hill cat,wild hog,green serpent,spectral hog"
    if realm_key == "mid" and int(party_size or 0) >= 8 and int(level or 0) in {7, 8, 9}:
        return "shadow,blodfelag oathbreaker,water snake,nordic dirge,mindless thrall,smiera-gatto,sveawolf mother,huldu stalker"
    if realm_key == "hib" and int(party_size or 0) in {2, 4} and int(level or 0) == 4:
        return "spraggon,spraggonoll,feccan,water beetle,water beetle collector,villainous youth,underhill companion,wild crouch"
    if realm_key == "hib" and int(party_size or 0) in {2, 4} and int(level or 0) in {5, 6}:
        return "spraggon,spraggonoll,feccan,underhill companion,wolf cub,water beetle,water beetle collector,villainous youth,wild crouch"
    if realm_key == "hib" and int(party_size or 0) > 1 and int(level or 0) <= 10:
        return "underhill companion,wolf cub"
    return ""


def merge_target_name_csv(*values: str) -> str:
    merged: list[str] = []
    seen: set[str] = set()
    for value in values:
        for name in str(value or "").split(","):
            clean = name.strip()
            if not clean:
                continue
            key = clean.lower()
            if key in seen:
                continue
            seen.add(key)
            merged.append(clean)
    return ",".join(merged)


def remove_matching_target_names_csv(value: str, protected_tokens: Iterable[str]) -> str:
    tokens = [str(token or "").strip().lower() for token in protected_tokens if str(token or "").strip()]
    if not tokens:
        return str(value or "")
    return ",".join(
        name.strip()
        for name in str(value or "").split(",")
        if name.strip() and not target_name_matches_any(name.strip(), tokens)
    )


GROWTH_FAILED_TARGET_MEMORY_SUCCESS_OUTCOMES = {
    "kill",
    "killed",
    "removed",
    "success",
    "target_removed",
    "target_object_removed",
}


GROWTH_FAILED_TARGET_MEMORY_XP_VOID_OUTCOMES = GROWTH_FAILED_TARGET_MEMORY_SUCCESS_OUTCOMES | {
    "target_removed_no_reward",
}


GROWTH_FAILED_TARGET_MEMORY_HARD_FAILURE_OUTCOMES = {
    "critical_health_drop",
    "critical_health_drop_aggro",
    "death",
    "died",
    "player_death",
    "target_removed_no_reward",
}


GROWTH_RUNTIME_FAILURE_MEMORY_FIELDS = [
    "timestamp_utc",
    "case",
    "realm",
    "party_size",
    "segment",
    "level",
    "reason",
    "action",
    "target_name",
    "target_level",
    "source",
    "expires_segment",
]
GROWTH_RUNTIME_FAILURE_MEMORY_TTL_SEGMENTS = 3


def growth_failed_target_memory_row_counts(row: dict[str, str], outcome: str) -> bool:
    if outcome in GROWTH_FAILED_TARGET_MEMORY_SUCCESS_OUTCOMES:
        return True
    if outcome in GROWTH_FAILED_TARGET_MEMORY_HARD_FAILURE_OUTCOMES:
        return True
    attacks = to_int(row.get("attacks"))
    skills = to_int(row.get("skills"))
    try:
        duration = float(row.get("duration_seconds") or 0.0)
    except (TypeError, ValueError):
        duration = 0.0
    return attacks > 0 or skills > 0 or duration >= 3.0


def growth_combat_target_stats(path: Path) -> dict[str, dict[str, int | str]]:
    stats: dict[str, dict[str, int | str]] = {}
    if not path.exists():
        return stats
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return stats
    for row in rows:
        target_name = str(row.get("target_name") or row.get("target") or "").strip()
        if not target_name:
            continue
        outcome = str(row.get("outcome") or "").strip().lower()
        if not growth_failed_target_memory_row_counts(row, outcome):
            continue
        key = target_name.lower()
        target_stats = stats.setdefault(
            key,
            {
                "name": target_name,
                "level": to_int(row.get("target_level")),
                "engagements": 0,
                "successes": 0,
                "failures": 0,
                "xp_void_candidates": 0,
            },
        )
        target_stats["engagements"] = int(target_stats["engagements"]) + 1
        if outcome in GROWTH_FAILED_TARGET_MEMORY_XP_VOID_OUTCOMES:
            target_stats["xp_void_candidates"] = int(target_stats["xp_void_candidates"]) + 1
        if outcome in GROWTH_FAILED_TARGET_MEMORY_SUCCESS_OUTCOMES:
            target_stats["successes"] = int(target_stats["successes"]) + 1
        else:
            target_stats["failures"] = int(target_stats["failures"]) + 1
        if not int(target_stats.get("level", 0) or 0):
            target_stats["level"] = to_int(row.get("target_level"))
    return stats


GROWTH_DEATH_KILLER_PATTERNS = [
    re.compile(r"^(?P<victim>.+?)(?:\uC774|\uAC00|\uC774\(\uAC00\))\s+(?P<killer>.+?)\uC5D0\uAC8C\s+\uC0AC\uB9DD\uD588\uC2B5\uB2C8\uB2E4[.!]?$", re.IGNORECASE),
    re.compile(r"^(?P<victim>.+?) was (?:just )?killed by (?P<killer>.+?)(?: in .+)?[.!]?$", re.IGNORECASE),
]


def growth_clean_failure_actor_name(value: str) -> str:
    name = " ".join(str(value or "").strip().split())
    name = re.sub(r"^(?:a|an|the)\s+", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"^[\uFFFD?]+(?:\s+|$)", "", name).strip()
    name = re.sub(r"^(?:[^\x00-\x7F]+\s+)+(?=[A-Za-z0-9])", "", name).strip()
    return name


def parse_growth_death_victim_killer_names(text: str) -> tuple[str, str]:
    normalized = str(text or "").strip()
    if not normalized:
        return "", ""
    for pattern in GROWTH_DEATH_KILLER_PATTERNS:
        match = pattern.match(normalized)
        if match is not None:
            return (
                growth_clean_failure_actor_name(match.group("victim")),
                growth_clean_failure_actor_name(match.group("killer")),
            )
    return "", ""


def parse_growth_death_killer_name(text: str) -> str:
    _victim_name, killer_name = parse_growth_death_victim_killer_names(text)
    return killer_name


def growth_case_actor_keys(case_dir: Path | None) -> set[str]:
    if case_dir is None:
        return set()
    accounts_path = case_dir / "primary-accounts.csv"
    if not accounts_path.exists():
        return set()
    keys: set[str] = set()
    try:
        rows = read_accounts(accounts_path)
    except OSError:
        return set()
    for row in rows:
        account = str(row.get("username") or row.get("account") or "").strip()
        if not account:
            continue
        keys.add(normalize_growth_target_name(account))
        keys.add(normalize_growth_target_name(character_name_from_account(account)))
    return {key for key in keys if key}


def growth_add_failure_actor_stat(
    stats: dict[str, dict[str, int | str]],
    name: str,
    *,
    level: int = 0,
    source: str,
) -> None:
    actor_name = growth_clean_failure_actor_name(name)
    key = normalize_growth_target_name(actor_name)
    if not key:
        return
    actor_stats = stats.setdefault(
        key,
        {
            "name": actor_name,
            "level": int(level or 0),
            "count": 0,
            "source": source,
        },
    )
    actor_stats["count"] = int(actor_stats.get("count", 0) or 0) + 1
    if not int(actor_stats.get("level", 0) or 0) and int(level or 0) > 0:
        actor_stats["level"] = int(level or 0)


GROWTH_OFFTARGET_FAILURE_ACTOR_FIELDS = (
    "rescue_target_name",
    "off_target_attacker",
    "off_target_attacker_name",
    "recent_incoming_attacker",
    "party_attack_attacker",
    "attacker_name",
    "blocked_target_name",
    "target",
)

GROWTH_FALLBACK_FAILURE_ACTOR_FIELDS = (
    "active_target_name",
    "current_target_name",
    "target_name",
    "leader_target_focus_name",
    "leader_target_name",
)

GROWTH_FAILURE_ACTOR_LEVEL_FIELDS = (
    "rescue_target_level",
    "off_target_attacker_level",
    "attacker_level",
    "target_level",
    "active_target_level",
    "current_target_level",
    "leader_target_level",
)


def growth_failure_actor_names_from_row(row: dict[str, object]) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add_from_fields(fields: Iterable[str]) -> None:
        for field in fields:
            actor_name = growth_clean_failure_actor_name(str(row.get(field, "") or ""))
            key = normalize_growth_target_name(actor_name)
            if not key or key in seen:
                continue
            seen.add(key)
            names.append(actor_name)

    add_from_fields(GROWTH_OFFTARGET_FAILURE_ACTOR_FIELDS)
    if names:
        return names
    add_from_fields(GROWTH_FALLBACK_FAILURE_ACTOR_FIELDS)
    return names


def growth_failure_actor_level_from_row(row: dict[str, object]) -> int:
    for field in GROWTH_FAILURE_ACTOR_LEVEL_FIELDS:
        level = to_int(row.get(field))
        if level > 0:
            return level
    return 0


def growth_encounter_failure_actor_stats(case_dir: Path | None, segment_index: int) -> dict[str, dict[str, int | str]]:
    stats: dict[str, dict[str, int | str]] = {}
    if case_dir is None:
        return stats
    encounter_dir = case_dir / "encounters"
    if not encounter_dir.exists():
        return stats
    case_actor_keys = growth_case_actor_keys(case_dir)
    pattern = f"segment-{int(segment_index or 0):03d}-*.jsonl"
    for path in sorted(encounter_dir.glob(pattern)):
        for row in jsonl_rows(path):
            event = str(row.get("event", "") or "")
            if event == "server_message":
                victim_name, killer_name = parse_growth_death_victim_killer_names(str(row.get("text", "") or ""))
                victim_key = normalize_growth_target_name(victim_name)
                if case_actor_keys and victim_key not in case_actor_keys:
                    continue
                if killer_name:
                    growth_add_failure_actor_stat(
                        stats,
                        killer_name,
                        level=to_int(row.get("target_level")),
                        source="encounter_death_message",
                    )
                continue
            if event not in {"flee_start", "unengaged_pull_offtarget_damage"}:
                continue
            reason = str(row.get("reason", "") or "")
            if reason != "unengaged_pull_offtarget_damage" and event != "unengaged_pull_offtarget_damage":
                continue
            for actor_name in growth_failure_actor_names_from_row(row):
                if normalize_growth_target_name(actor_name) in case_actor_keys:
                    continue
                growth_add_failure_actor_stat(
                    stats,
                    actor_name,
                    level=growth_failure_actor_level_from_row(row),
                    source="encounter_offtarget_damage",
                )
    return stats


def growth_failed_target_memory_enabled(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "growth_failure_target_memory", True))


def growth_failed_attempts_root(args: argparse.Namespace) -> Path | None:
    case_name = str(getattr(args, "case_name", "") or "").strip()
    run_dir_text = str(getattr(args, "run_dir", "") or "").strip()
    if not case_name or not run_dir_text:
        return None
    run_dir = Path(run_dir_text)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    if len(run_dir.parents) < 2:
        return None
    return run_dir.parent.parent / "failed-attempts" / case_name


def growth_failed_target_memory_attempt_dirs(args: argparse.Namespace) -> list[Path]:
    root = growth_failed_attempts_root(args)
    if root is None or not root.exists():
        return []
    segment_index = to_int(getattr(args, "growth_current_segment_index", 0))
    if segment_index > 0:
        candidates = [path for path in root.glob(f"segment-{segment_index:03d}-attempt-*") if path.is_dir()]
    else:
        candidates = [path for path in root.glob("segment-*-attempt-*") if path.is_dir()]
    candidates.sort(key=lambda path: path.name, reverse=True)
    limit = max(1, to_int(getattr(args, "growth_failure_target_memory_attempts", 8)) or 8)
    return candidates[:limit]


def growth_runtime_failure_memory_path(args: argparse.Namespace) -> Path | None:
    explicit = str(getattr(args, "growth_runtime_failure_memory_csv", "") or "").strip()
    if explicit:
        path = Path(explicit)
        return path if path.is_absolute() else ROOT / path
    case_name = str(getattr(args, "case_name", "") or "").strip()
    run_dir_text = str(getattr(args, "run_dir", "") or "").strip()
    if not case_name or not run_dir_text:
        return None
    run_dir = Path(run_dir_text)
    if not run_dir.is_absolute():
        run_dir = ROOT / run_dir
    return run_dir / case_name / "runtime-failure-memory.csv"


def read_growth_runtime_failure_memory(args: argparse.Namespace) -> list[dict[str, str]]:
    path = growth_runtime_failure_memory_path(args)
    if path is None or not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return []


def growth_runtime_failure_memory_row_applies(
    row: dict[str, str],
    realm_key: str,
    level: int,
    party_size: int,
    current_segment: int,
) -> bool:
    row_realm = str(row.get("realm", "") or "").strip().lower()
    if row_realm and row_realm != str(realm_key or "").strip().lower():
        return False
    row_party_size = to_int(row.get("party_size"))
    if row_party_size and row_party_size != int(party_size or 0):
        return False
    row_level = to_int(row.get("level"))
    if row_level and row_level != int(level or 0):
        return False
    expires_segment = to_int(row.get("expires_segment"))
    if expires_segment and current_segment and expires_segment < current_segment:
        return False
    return True


def growth_runtime_failure_memory_row_blocked_by_reward_floor(
    args: argparse.Namespace,
    row: dict[str, str],
    realm_key: str,
    level: int,
    party_size: int,
) -> bool:
    reason = str(row.get("reason", "") or "").strip().lower()
    if not ({"target_removed_no_xp", "combat_no_kill"} & {part.strip() for part in reason.split(";") if part.strip()}):
        return False
    reward_floor = growth_party_carry_reward_floor(args, level, party_size, realm_key)
    if reward_floor <= 0:
        return False
    target_level = to_int(row.get("target_level"))
    return target_level > 0 and target_level < reward_floor


def growth_runtime_failure_memory_row_has_successful_segment_target(
    args: argparse.Namespace,
    row: dict[str, str],
) -> bool:
    reasons = {part.strip() for part in str(row.get("reason", "") or "").split(";") if part.strip()}
    if "death_pressure" not in reasons:
        return False
    if str(row.get("source", "") or "").strip() != "encounter_death_message":
        return False
    target_key = normalize_growth_target_name(str(row.get("target_name", "") or ""))
    if not target_key:
        return False
    segment_index = to_int(row.get("segment"))
    if segment_index <= 0:
        return False
    memory_path = growth_runtime_failure_memory_path(args)
    if memory_path is None:
        return False
    combat_csv = memory_path.parent / f"segment-{segment_index:03d}-combat.csv"
    stats = growth_combat_target_stats(combat_csv)
    target_stats = stats.get(target_key)
    return bool(target_stats and int(target_stats.get("successes", 0) or 0) > 0)


def growth_failure_memory_target_phrase_matches(target_name: str, expected_name: str) -> bool:
    target = normalize_growth_target_name(target_name)
    expected = normalize_growth_target_name(expected_name)
    if not target or not expected:
        return False
    return target == expected or target.endswith(f" {expected}") or target.startswith(f"{expected} ")


def growth_runtime_failure_memory_row_applies_without_expiry(
    row: dict[str, str],
    realm_key: str,
    level: int,
    party_size: int,
) -> bool:
    row_realm = str(row.get("realm", "") or "").strip().lower()
    if row_realm and row_realm != str(realm_key or "").strip().lower():
        return False
    row_party_size = to_int(row.get("party_size"))
    if row_party_size and row_party_size != int(party_size or 0):
        return False
    row_level = to_int(row.get("level"))
    if row_level and row_level != int(level or 0):
        return False
    return True


def growth_runtime_failure_memory_has_hard_target_failure(
    args: argparse.Namespace,
    realm_key: str,
    level: int,
    party_size: int,
    target_name: str,
) -> bool:
    if not growth_failed_target_memory_enabled(args):
        return False
    hard_reasons = {"combat_no_kill", "combat_pressure_no_kill", "death_pressure", "target_timeout"}
    for row in read_growth_runtime_failure_memory(args):
        if str(row.get("action", "") or "").strip() != "avoid_target":
            continue
        if not growth_runtime_failure_memory_row_applies_without_expiry(row, realm_key, level, party_size):
            continue
        reasons = {part.strip() for part in str(row.get("reason", "") or "").split(";") if part.strip()}
        if not (reasons & hard_reasons):
            continue
        if growth_runtime_failure_memory_row_blocked_by_reward_floor(args, row, realm_key, level, party_size):
            continue
        if growth_runtime_failure_memory_row_has_successful_segment_target(args, row):
            continue
        if growth_failure_memory_target_phrase_matches(str(row.get("target_name", "") or ""), target_name):
            return True
    return False


def growth_runtime_failure_memory_avoid_targets(
    args: argparse.Namespace,
    realm_key: str,
    level: int,
    party_size: int,
) -> str:
    if not growth_failed_target_memory_enabled(args):
        return ""
    current_segment = to_int(getattr(args, "growth_current_segment_index", 0))
    targets: list[str] = []
    for row in read_growth_runtime_failure_memory(args):
        if str(row.get("action", "") or "").strip() != "avoid_target":
            continue
        if not growth_runtime_failure_memory_row_applies(row, realm_key, level, party_size, current_segment):
            continue
        if growth_runtime_failure_memory_row_blocked_by_reward_floor(args, row, realm_key, level, party_size):
            continue
        if growth_runtime_failure_memory_row_has_successful_segment_target(args, row):
            continue
        target = str(row.get("target_name", "") or "").strip()
        if target:
            targets.append(target)
    return merge_target_name_csv(",".join(targets))


def growth_runtime_failure_memory_downgrade_count(args: argparse.Namespace, realm_key: str, level: int, party_size: int) -> int:
    if not growth_failed_target_memory_enabled(args):
        return 0
    current_segment = to_int(getattr(args, "growth_current_segment_index", 0))
    count = 0
    for row in read_growth_runtime_failure_memory(args):
        if str(row.get("action", "") or "").strip() != "downgrade_target_plan":
            continue
        if not growth_runtime_failure_memory_row_applies(row, realm_key, level, party_size, current_segment):
            continue
        count += 1
    return count


def growth_runtime_failure_memory_reason_count(
    args: argparse.Namespace,
    realm_key: str,
    level: int,
    party_size: int,
    reason_token: str,
) -> int:
    if not growth_failed_target_memory_enabled(args):
        return 0
    current_segment = to_int(getattr(args, "growth_current_segment_index", 0))
    token = str(reason_token or "").strip()
    if not token:
        return 0
    count = 0
    for row in read_growth_runtime_failure_memory(args):
        if not growth_runtime_failure_memory_row_applies(row, realm_key, level, party_size, current_segment):
            continue
        reasons = {part.strip() for part in str(row.get("reason", "") or "").split(";") if part.strip()}
        if token in reasons:
            count += 1
    return count


def append_growth_runtime_failure_memory(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GROWTH_RUNTIME_FAILURE_MEMORY_FIELDS)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in GROWTH_RUNTIME_FAILURE_MEMORY_FIELDS})


def record_growth_runtime_failure_memory_for_segment(
    path: Path,
    *,
    case_name: str,
    realm_key: str,
    party_size: int,
    segment_index: int,
    current_level: int,
    bottleneck_reasons: set[str],
    combat_csv: Path,
    case_dir: Path | None = None,
) -> None:
    if not bottleneck_reasons:
        return
    rows: list[dict[str, object]] = []
    expires_segment = int(segment_index or 0) + GROWTH_RUNTIME_FAILURE_MEMORY_TTL_SEGMENTS
    stats = growth_combat_target_stats(combat_csv)
    successful_target_keys = {
        normalize_growth_target_name(str(target_stats.get("name", "") or ""))
        for target_stats in stats.values()
        if int(target_stats.get("successes", 0) or 0) > 0
    }
    if "target_removed_no_xp" in bottleneck_reasons:
        for target_stats in stats.values():
            if int(target_stats.get("engagements", 0) or 0) <= 0:
                continue
            if int(target_stats.get("xp_void_candidates", 0) or 0) <= 0:
                continue
            rows.append(
                {
                    "timestamp_utc": utc_now(),
                    "case": case_name,
                    "realm": realm_key,
                    "party_size": int(party_size or 0),
                    "segment": int(segment_index or 0),
                    "level": int(current_level or 0),
                    "reason": "target_removed_no_xp",
                    "action": "avoid_target",
                    "target_name": target_stats.get("name", ""),
                    "target_level": target_stats.get("level", ""),
                    "source": "combat_csv",
                    "expires_segment": expires_segment,
                }
            )
    hard_combat_reasons = {
        "combat_no_kill",
        "combat_pressure_no_kill",
        "death_pressure",
        "target_timeout",
    }
    encounter_actor_reasons = bottleneck_reasons & (hard_combat_reasons | {"target_removed_no_xp"})
    failure_actor_stats = (
        growth_encounter_failure_actor_stats(case_dir, segment_index)
        if encounter_actor_reasons
        else {}
    )
    failure_actor_keys = set(failure_actor_stats.keys())
    off_target_actor_failure = any(
        str(actor_stats.get("source", "") or "") == "encounter_offtarget_damage"
        for actor_stats in failure_actor_stats.values()
    )
    encounter_actor_reason_text = (
        "death_pressure"
        if "death_pressure" in bottleneck_reasons
        else ";".join(sorted(encounter_actor_reasons))
    )
    for actor_stats in failure_actor_stats.values():
        actor_key = normalize_growth_target_name(str(actor_stats.get("name", "") or ""))
        if (
            str(actor_stats.get("source", "") or "") == "encounter_death_message"
            and actor_key
            and actor_key in successful_target_keys
        ):
            continue
        rows.append(
            {
                "timestamp_utc": utc_now(),
                "case": case_name,
                "realm": realm_key,
                "party_size": int(party_size or 0),
                "segment": int(segment_index or 0),
                "level": int(current_level or 0),
                "reason": encounter_actor_reason_text,
                "action": "avoid_target",
                "target_name": actor_stats.get("name", ""),
                "target_level": actor_stats.get("level", ""),
                "source": actor_stats.get("source", "encounter"),
                "expires_segment": expires_segment,
            }
        )
    if bottleneck_reasons & hard_combat_reasons:
        if off_target_actor_failure:
            append_growth_runtime_failure_memory(path, rows)
            return
        for target_stats in stats.values():
            if normalize_growth_target_name(str(target_stats.get("name", "") or "")) in failure_actor_keys:
                continue
            if int(target_stats.get("successes", 0) or 0) > 0:
                continue
            if int(target_stats.get("engagements", 0) or 0) <= 0:
                continue
            rows.append(
                {
                    "timestamp_utc": utc_now(),
                    "case": case_name,
                    "realm": realm_key,
                    "party_size": int(party_size or 0),
                    "segment": int(segment_index or 0),
                    "level": int(current_level or 0),
                    "reason": ";".join(sorted(bottleneck_reasons & hard_combat_reasons)),
                    "action": "avoid_target",
                    "target_name": target_stats.get("name", ""),
                    "target_level": target_stats.get("level", ""),
                    "source": "combat_csv",
                    "expires_segment": expires_segment,
                }
            )
    if {"no_engagement", "scan_empty:level"} & bottleneck_reasons:
        rows.append(
            {
                "timestamp_utc": utc_now(),
                "case": case_name,
                "realm": realm_key,
                "party_size": int(party_size or 0),
                "segment": int(segment_index or 0),
                "level": int(current_level or 0),
                "reason": ";".join(sorted({"no_engagement", "scan_empty:level"} & bottleneck_reasons)),
                "action": "downgrade_target_plan",
                "source": "timeline",
                "expires_segment": expires_segment,
            }
        )
    append_growth_runtime_failure_memory(path, rows)


def growth_runtime_failure_memory_summary(
    args: argparse.Namespace,
    realm_key: str,
    level: int,
    party_size: int,
    *,
    limit: int = 12,
) -> list[dict[str, object]]:
    if not growth_failed_target_memory_enabled(args):
        return []
    current_segment = to_int(getattr(args, "growth_current_segment_index", 0))
    rows: list[dict[str, object]] = []
    for row in read_growth_runtime_failure_memory(args):
        if not growth_runtime_failure_memory_row_applies(row, realm_key, level, party_size, current_segment):
            continue
        rows.append(
            {
                "segment": to_int(row.get("segment")),
                "reason": str(row.get("reason", "") or ""),
                "action": str(row.get("action", "") or ""),
                "target_name": str(row.get("target_name", "") or ""),
                "target_level": to_int(row.get("target_level")),
                "source": str(row.get("source", "") or ""),
                "expires_segment": to_int(row.get("expires_segment")),
            }
        )
    return rows[-max(1, int(limit or 1)) :]


def growth_combat_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return []


def growth_segment_combat_summary(path: Path) -> dict[str, object]:
    rows = growth_combat_rows(path)
    outcomes: dict[str, int] = {}
    targets: dict[str, dict[str, object]] = {}
    failure_rows: list[dict[str, object]] = []
    for row in rows:
        outcome = str(row.get("outcome", "") or "").strip() or "unknown"
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
        target_name = str(row.get("target_name", "") or "").strip() or "none"
        target_level = to_int(row.get("target_level"))
        target = targets.setdefault(
            target_name,
            {
                "name": target_name,
                "level": target_level,
                "engagements": 0,
                "removed": 0,
                "failures": 0,
            },
        )
        target["engagements"] = int(target["engagements"]) + 1
        if target_level and not int(target.get("level", 0) or 0):
            target["level"] = target_level
        if outcome == "target_removed":
            target["removed"] = int(target["removed"]) + 1
        else:
            target["failures"] = int(target["failures"]) + 1
            failure_rows.append(
                {
                    "target_name": target_name,
                    "target_level": target_level,
                    "outcome": outcome,
                    "duration_seconds": str(row.get("duration_seconds", "") or ""),
                    "attacks": to_int(row.get("attacks")),
                    "skills": to_int(row.get("skills")),
                    "start_distance": str(row.get("start_distance", "") or ""),
                }
            )
    return {
        "engagements": len(rows),
        "outcomes": outcomes,
        "targets": list(targets.values()),
        "failures": failure_rows[:8],
    }


def growth_segment_action_summary(metrics: dict[str, float]) -> dict[str, int]:
    interesting = (
        "action_required_target_pre_hunt_recover",
        "action_rest",
        "action_rest_complete",
        "action_low_health_rest",
        "action_critical_health_drop_aggro",
        "action_flee_start",
        "action_objective_entry_aggro_detour",
        "action_travel_aggro_detour_direct_move",
        "action_attack_z_mismatch",
        "action_server_los_failure_retry",
        "action_target_timeout",
        "action_target_removed",
        "action_loot_acquired",
        "action_death_detected",
        "action_route_home_fast_travel_reposition",
    )
    return {key.removeprefix("action_"): to_int(metrics.get(key)) for key in interesting if to_int(metrics.get(key)) > 0}


def growth_segment_next_recommendation(
    *,
    rc: int,
    require_kill: bool,
    require_xp: bool,
    aggregate_xp_ok: bool,
    account_xp_ok: bool,
    bottleneck_reasons: set[str],
    metrics: dict[str, float],
) -> str:
    if rc == 0 and to_int(metrics.get("target_removed")) > 0 and aggregate_xp_ok and account_xp_ok:
        if to_int(metrics.get("action_critical_health_drop_aggro")) > 0:
            return "continue_same_route_once_watch_health_pressure"
        return "continue_next_segment"
    if any(str(reason).startswith("live_abort_") for reason in bottleneck_reasons):
        return "inspect_live_abort_json_and_fix_root_cause_before_rerun"
    if "movement_failure" in bottleneck_reasons:
        return "inspect_movement_trace_path_z_or_graph_gap"
    if "target_timeout" in bottleneck_reasons or to_int(metrics.get("target_timeouts")) > 0:
        return "inspect_visibility_los_z_and_target_refresh"
    if "death_pressure" in bottleneck_reasons or to_int(metrics.get("player_deaths")) > 0:
        return "classify_aggro_vs_combat_power_before_route_change"
    if "combat_no_kill" in bottleneck_reasons or "combat_pressure_no_kill" in bottleneck_reasons:
        return "check_combat_power_then_runtime_failure_fallback"
    if "no_engagement" in bottleneck_reasons:
        return "verify_live_candidates_and_route_prefer_require_tokens"
    if require_kill and to_int(metrics.get("target_removed")) <= 0:
        return "require_kill_failed_inspect_report_and_combat"
    if require_xp and not aggregate_xp_ok:
        return "require_xp_failed_check_xp_messages_and_reward_floor"
    return "inspect_segment_summary"


def write_growth_segment_summary_json(
    path: Path,
    *,
    args: argparse.Namespace,
    case_name: str,
    realm: RealmProfile,
    party_size: int,
    segment_index: int,
    current_level: int,
    route_level: int,
    route: RoutePoint,
    metrics: dict[str, float],
    combat_csv: Path,
    bottleneck_reasons: set[str],
    xp_effective_delta: int | float,
    xp_effective_by_account: dict[str, int | float],
    require_kill: bool,
    require_xp: bool,
    aggregate_xp_ok: bool,
    account_xp_ok: bool,
    rc: int,
    live_abort_reason: str = "",
) -> None:
    payload = {
        "case": case_name,
        "segment": int(segment_index or 0),
        "realm": realm.key,
        "party_size": int(party_size or 0),
        "level": int(current_level or 0),
        "route_level": int(route_level or 0),
        "route": {
            "prefer": route.prefer,
            "avoid": route.avoid,
            "teleport": route.teleport_destination,
            "x": route.x,
            "y": route.y,
            "z": route.z,
            "source": route.source,
            "mob_level": route.mob_level,
            "mob_count": route.mob_count,
            "nearby_avoid": growth_target_nearby_avoid_names_for_route(current_level, party_size, realm.key, route),
            "objective_entry_aggro_avoid_radius": growth_objective_entry_aggro_avoid_radius(
                current_level,
                party_size,
                realm.key,
                route,
            ),
        },
        "failure_memory": growth_runtime_failure_memory_summary(args, realm.key, current_level, party_size),
        "requirements": {
            "kill": bool(require_kill),
            "xp": bool(require_xp),
            "aggregate_xp_ok": bool(aggregate_xp_ok),
            "account_xp_ok": bool(account_xp_ok),
        },
        "result": {
            "rc": int(rc or 0),
            "live_abort_reason": live_abort_reason,
            "target_removed": to_int(metrics.get("target_removed")),
            "loot_acquired": to_int(metrics.get("loot_acquired")),
            "combat_engagements": to_int(metrics.get("combat_engagements")),
            "damage_done": to_int(metrics.get("damage_done")),
            "damage_taken": to_int(metrics.get("damage_taken")),
            "player_deaths": to_int(metrics.get("player_deaths")),
            "movement_failures": to_int(metrics.get("movement_failures")),
            "target_timeouts": to_int(metrics.get("target_timeouts")),
            "xp_effective_delta": to_int(xp_effective_delta),
            "xp_effective_by_account": {key: to_int(value) for key, value in xp_effective_by_account.items()},
        },
        "combat": growth_segment_combat_summary(combat_csv),
        "actions": growth_segment_action_summary(metrics),
        "bottleneck_reasons": sorted(bottleneck_reasons),
        "next_recommendation": growth_segment_next_recommendation(
            rc=rc,
            require_kill=require_kill,
            require_xp=require_xp,
            aggregate_xp_ok=aggregate_xp_ok,
            account_xp_ok=account_xp_ok,
            bottleneck_reasons=bottleneck_reasons,
            metrics=metrics,
        ),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def growth_failed_attempt_bottleneck_reasons(attempt_dir: Path) -> set[str]:
    reasons: set[str] = set()
    timeline_csv = attempt_dir / "timeline.csv"
    if not timeline_csv.exists():
        return reasons
    try:
        with timeline_csv.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                for token in str(row.get("bottleneck_reason", "") or "").split(";"):
                    token = token.strip()
                    if token:
                        reasons.add(token)
    except (OSError, csv.Error):
        return reasons
    return reasons


def growth_failed_attempt_scan_empty_level_count(args: argparse.Namespace) -> int:
    if not growth_failed_target_memory_enabled(args):
        return 0
    root = growth_failed_attempts_root(args)
    segment_index = to_int(getattr(args, "growth_current_segment_index", 0))
    cache_key = (str(root or ""), int(segment_index or 0))
    raw_cached = getattr(args, "_growth_failed_scan_empty_level_count_cache", None)
    if isinstance(raw_cached, dict) and cache_key in raw_cached:
        return int(raw_cached[cache_key])
    count = 0
    for attempt_dir in growth_failed_target_memory_attempt_dirs(args):
        encounter_dir = attempt_dir / "encounters"
        if not encounter_dir.exists():
            continue
        for encounter_path in sorted(encounter_dir.glob("segment-*-*.jsonl")):
            try:
                with encounter_path.open("r", encoding="utf-8", errors="replace") as handle:
                    for line in handle:
                        try:
                            row = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if str(row.get("event", "") or "") != "hunter_target_scan_empty":
                            continue
                        if to_int(row.get("hunter_eligible_npcs")) > 0:
                            continue
                        reject_counts = row.get("hunter_reject_counts")
                        if isinstance(reject_counts, dict) and to_int(reject_counts.get("level")) > 0:
                            count += 1
            except OSError:
                continue
    if not isinstance(raw_cached, dict):
        raw_cached = {}
    raw_cached[cache_key] = count
    setattr(args, "_growth_failed_scan_empty_level_count_cache", raw_cached)
    return count


def adjust_growth_target_plan_for_failed_level_scan(
    args: argparse.Namespace,
    current_level: int,
    party_size: int,
    min_target: int,
    ideal_target: int,
    max_delta: int,
) -> tuple[int, int, int]:
    realm_key = str(getattr(args, "current_realm_key", "") or "").lower()
    runtime_death_pressure_count = growth_runtime_failure_memory_reason_count(
        args,
        realm_key,
        current_level,
        party_size,
        "death_pressure",
    )
    downgrade_count = growth_failed_attempt_scan_empty_level_count(args) + growth_runtime_failure_memory_downgrade_count(
        args,
        realm_key,
        current_level,
        party_size,
    )
    if downgrade_count <= 0 and runtime_death_pressure_count <= 0:
        return min_target, ideal_target, max_delta
    level = max(1, int(current_level or 1))
    allow_lower_xp_gear_farm = bool(getattr(args, "growth_allow_lower_xp_gear_farm", True))
    floor_level = minimum_growth_effective_target_level(level, party_size, realm_key)
    if allow_lower_xp_gear_farm:
        floor_level = max(1, minimum_non_grey_target_level(level))
    if runtime_death_pressure_count > 0:
        if allow_lower_xp_gear_farm and growth_party_uses_carry_tuning(args, level, party_size):
            floor_level = max(floor_level, min(level, int(min_target or level)))
        if floor_level <= 0:
            return min_target, ideal_target, max_delta
        floor_target = max(1, int(floor_level))
        return floor_target, floor_target, 0
    if (
        int(current_level or 0) > 1
        and growth_party_uses_carry_tuning(args, current_level, party_size)
        and not bool(getattr(args, "growth_equip_party_carry_gear", False))
    ):
        return min_target, ideal_target, max_delta
    relax_steps = max(1, min(8, int(downgrade_count or 1)))
    if int(party_size or 0) >= 8:
        relax_steps = max(2, relax_steps)
        relaxed_min = max(1, int(min_target or 1) - relax_steps)
        relaxed_ideal = max(relaxed_min, min(int(ideal_target or relaxed_min) - relax_steps, max(1, level - 1)))
        if floor_level > 0:
            relaxed_min = max(relaxed_min, floor_level)
            relaxed_ideal = max(relaxed_ideal, relaxed_min)
        return relaxed_min, relaxed_ideal, max(int(max_delta or 0), 2)
    relaxed_min = max(1, int(min_target or 1) - relax_steps)
    relaxed_ideal = max(relaxed_min, int(ideal_target or relaxed_min) - relax_steps)
    if floor_level > 0:
        relaxed_min = max(relaxed_min, floor_level)
        relaxed_ideal = max(relaxed_ideal, relaxed_min)
    return relaxed_min, relaxed_ideal, max(int(max_delta or 0), 1)


def growth_failed_target_memory_avoid_targets(
    args: argparse.Namespace,
    realm_key: str,
    level: int,
    party_size: int,
) -> str:
    if not growth_failed_target_memory_enabled(args):
        return ""
    cache_key = (
        str(realm_key or "").strip().lower(),
        int(level or 0),
        int(party_size or 0),
        int(getattr(args, "growth_shortage_recovery_player_level", 0) or 0),
        str(getattr(args, "growth_target_plan_override", "") or ""),
        int(getattr(args, "growth_current_segment_index", 0) or 0),
    )
    cached = getattr(args, "_growth_failed_target_memory_avoid_targets_cache", None)
    if isinstance(cached, dict) and cache_key in cached:
        return str(cached[cache_key])
    raw_cache_key = (
        str(growth_failed_attempts_root(args) or ""),
        str(realm_key or "").strip().lower(),
        int(level or 0),
        int(party_size or 0),
        int(getattr(args, "growth_party_carry_level_offset", 0) or 0),
        int(getattr(args, "growth_party_carry_count", 0) or 0),
        bool(getattr(args, "growth_equip_party_carry_gear", False)),
        int(getattr(args, "growth_current_segment_index", 0) or 0),
    )
    raw_cached = getattr(args, "_growth_failed_target_memory_avoid_targets_raw_cache", None)
    if isinstance(raw_cached, dict) and raw_cache_key in raw_cached:
        raw_result = str(raw_cached[raw_cache_key])
    else:
        stats: dict[str, dict[str, int | str]] = {}
        reward_floor = growth_party_carry_reward_floor(args, level, party_size, realm_key)
        for attempt_dir in growth_failed_target_memory_attempt_dirs(args):
            bottleneck_reasons = growth_failed_attempt_bottleneck_reasons(attempt_dir)
            xp_void_attempt = "target_removed_no_xp" in bottleneck_reasons
            for combat_csv in sorted(attempt_dir.glob("segment-*-combat.csv")):
                try:
                    with combat_csv.open("r", encoding="utf-8-sig", newline="") as handle:
                        rows = list(csv.DictReader(handle))
                except (OSError, csv.Error):
                    continue
                for row in rows:
                    target_name = str(row.get("target_name") or row.get("target") or "").strip()
                    if not target_name:
                        continue
                    outcome = str(row.get("outcome") or "").strip().lower()
                    if not growth_failed_target_memory_row_counts(row, outcome):
                        continue
                    key = target_name.lower()
                    target_stats = stats.setdefault(
                        key,
                        {
                            "name": target_name,
                            "level": to_int(row.get("target_level")),
                            "engagements": 0,
                            "successes": 0,
                            "hard_failures": 0,
                            "xp_void_failures": 0,
                        },
                    )
                    target_stats["engagements"] = int(target_stats["engagements"]) + 1
                    if not int(target_stats.get("level", 0) or 0):
                        target_stats["level"] = to_int(row.get("target_level"))
                    if outcome == "target_removed_no_reward":
                        target_stats["xp_void_failures"] = int(target_stats["xp_void_failures"]) + 1
                    elif outcome in GROWTH_FAILED_TARGET_MEMORY_HARD_FAILURE_OUTCOMES or outcome == "flee":
                        target_stats["hard_failures"] = int(target_stats["hard_failures"]) + 1
                    elif xp_void_attempt and outcome in GROWTH_FAILED_TARGET_MEMORY_SUCCESS_OUTCOMES:
                        target_stats["xp_void_failures"] = int(target_stats["xp_void_failures"]) + 1
                    elif outcome in GROWTH_FAILED_TARGET_MEMORY_SUCCESS_OUTCOMES:
                        target_stats["successes"] = int(target_stats["successes"]) + 1
        min_engagements = max(1, to_int(getattr(args, "growth_failure_target_memory_min_engagements", 2)) or 2)
        blocked: list[str] = []
        for target_stats in stats.values():
            if int(target_stats.get("hard_failures", 0)) > 0:
                blocked.append(str(target_stats["name"]))
                continue
            if int(target_stats.get("xp_void_failures", 0) or 0) > 0:
                target_level = to_int(target_stats.get("level"))
                if reward_floor > 0 and target_level > 0 and target_level < reward_floor:
                    continue
                blocked.append(str(target_stats["name"]))
                continue
            if int(target_stats["engagements"]) < min_engagements:
                continue
            if int(target_stats["successes"]) > 0:
                continue
            blocked.append(str(target_stats["name"]))
        raw_result = merge_target_name_csv(",".join(blocked))
        if not isinstance(raw_cached, dict):
            raw_cached = {}
        raw_cached[raw_cache_key] = raw_result
        setattr(args, "_growth_failed_target_memory_avoid_targets_raw_cache", raw_cached)
    raw_result = merge_target_name_csv(
        raw_result,
        growth_runtime_failure_memory_avoid_targets(args, realm_key, level, party_size),
    )
    result = growth_filter_shortage_recovery_failed_avoid_targets(
        args,
        raw_result,
        realm_key,
        level,
        party_size,
    )
    if not isinstance(cached, dict):
        cached = {}
    cached[cache_key] = result
    setattr(args, "_growth_failed_target_memory_avoid_targets_cache", cached)
    return result


def growth_filter_shortage_recovery_failed_avoid_targets(
    args: argparse.Namespace,
    targets: str,
    realm_key: str,
    level: int,
    party_size: int,
    *,
    route: RoutePoint | None = None,
) -> str:
    tokens = [token.strip() for token in str(targets or "").split(",") if token.strip()]
    if not tokens:
        return ""
    recovery_level = int(getattr(args, "growth_shortage_recovery_player_level", 0) or 0)
    allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
        getattr(args, "growth_allow_lower_xp_gear_farm", True)
    )
    if (
        not allow_lower_xp_target_plan
        or str(realm_key or "").strip().lower() != "mid"
        or int(party_size or 0) > 1
        or recovery_level != 7
    ):
        return merge_target_name_csv(",".join(tokens))
    allowed: set[str] = set()
    if route is not None:
        allowed.update(token.strip().lower() for token in str(route.prefer or "").split(",") if token.strip())
    if not allowed:
        return merge_target_name_csv(",".join(tokens))
    return ",".join(
        token
        for token in tokens
        if not target_name_matches_any(token, allowed)
    )


def growth_route_blocked_by_failed_target_memory(
    args: argparse.Namespace,
    route: RoutePoint,
    realm_key: str,
    level: int,
    party_size: int,
) -> bool:
    failed_targets = growth_failed_target_memory_avoid_targets(args, realm_key, level, party_size)
    failed_tokens = preferred_target_tokens(failed_targets)
    return bool(
        failed_tokens
        and target_name_csv_matches_any(route.prefer, failed_tokens)
    )


def filter_routes_blocked_by_failed_target_memory(
    args: argparse.Namespace,
    routes: Iterable[RoutePoint],
    realm_key: str,
    level: int,
    party_size: int,
) -> list[RoutePoint]:
    return [
        route
        for route in routes
        if not growth_route_blocked_by_failed_target_memory(args, route, realm_key, level, party_size)
    ]


def growth_avoid_targets_for_current_context(
    route: RoutePoint,
    realm_key: str,
    level: int,
    party_size: int,
    *,
    allow_lower_xp_target_plan: bool = False,
) -> str:
    merged = merge_target_name_csv(
        route.avoid,
        growth_hunting_index_avoid_targets(realm_key, level, party_size),
    )
    allowed = {token.strip().lower() for token in route.prefer.split(",") if token.strip()}
    if allow_lower_xp_target_plan and realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 7:
        allowed.update({"carrion crawler", "sapherd", "pine imp"})
    if not allowed:
        return merged
    return ",".join(
        token.strip()
        for token in merged.split(",")
        if token.strip() and not target_name_csv_matches_any(route.prefer, [token])
    )


def distributed_growth_hunting_index_route(
    args: argparse.Namespace,
    realm: RealmProfile,
    level: int,
    party_size: int,
) -> RoutePoint | None:
    if not str(getattr(args, "growth_hunting_index", "") or "").strip():
        return None
    if int(getattr(args, "growth_route_case_index", 0) or 0) <= 0:
        return None
    carry_route_mode = (
        bool(getattr(args, "growth_route_level_is_carry_target", False))
        or growth_party_uses_carry_tuning(
            args,
            int(getattr(args, "growth_target_level_override", 0) or level or 1),
            int(party_size or 0),
        )
    ) and int(party_size or 0) > 1
    route_target_level = int(level or 0)
    caller_player_level: int | None = None
    if not carry_route_mode:
        caller_player_level = int(level or 0)
        allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
            getattr(args, "growth_allow_lower_xp_gear_farm", True)
        )
        if allow_lower_xp_target_plan:
            target_plan_override = getattr(args, "growth_target_plan_override", None)
            if target_plan_override is not None:
                _, plan_ideal_target, _ = target_plan_override
            else:
                _, plan_ideal_target, _ = target_levels(int(level or 0), int(party_size or 0), realm.key)
            route_target_level = max(1, int(plan_ideal_target or route_target_level))
        elif int(party_size or 0) <= 1 and int(level or 0) >= 5:
            route_target_level = no_lower_xp_route_target_level(args, realm.key, int(level or 0), party_size)
    route = select_growth_hunting_index_point_for_target(
        args,
        realm.key,
        route_target_level,
        party_size,
        caller_player_level=caller_player_level,
    )
    if route is None:
        return None
    if growth_route_preflight_enabled(args):
        preflight_level = growth_route_preflight_policy_level(
            args,
            int(level or 0),
            int(party_size or 0),
        )
        checked = growth_route_preflight_checked_route(
            args,
            route,
            realm=realm,
            current_level=preflight_level,
            party_size=int(party_size or 0),
        )
        if checked is not None:
            return checked
        if growth_route_preflight_strict_required(
            args,
            route,
            current_level=preflight_level,
            party_size=int(party_size or 0),
        ):
            return None
    return route


def growth_static_route_or_preflight_fallback(
    args: argparse.Namespace,
    realm: RealmProfile,
    route: RoutePoint,
    *,
    current_level: int,
    party_size: int,
    target_level: int,
) -> RoutePoint:
    preflight_level = growth_route_preflight_policy_level(args, current_level, party_size)
    if growth_route_preflight_enabled(args):
        checked = growth_route_preflight_checked_route(
            args,
            route,
            realm=realm,
            current_level=preflight_level,
            party_size=int(party_size or 0),
        )
        if checked is not None:
            return checked
        if growth_route_preflight_strict_required(
            args,
            route,
            current_level=preflight_level,
            party_size=int(party_size or 0),
        ):
            if not str(getattr(args, "growth_hunting_index", "") or "").strip():
                log_growth_route_preflight(
                    args,
                    realm_key=realm.key,
                    current_level=preflight_level,
                    party_size=int(party_size or 0),
                    route=route,
                    status="skip",
                    reason="route_unsuitable_live_world:static_route_failed:no_growth_hunting_index_for_fallback",
                )
                raise RuntimeError(
                    "growth party carry route_unsuitable_live_world after preflight; "
                    "no growth_hunting_index fallback seed was provided: "
                    f"realm={realm.key} party={int(party_size or 0)} level={preflight_level} "
                    f"target_level={int(target_level or 0)} route={route.prefer or route.source}"
                )
            replacement = select_growth_hunting_index_point_for_target(
                args,
                realm.key,
                int(target_level or getattr(route, "mob_level", 0) or current_level or 1),
                int(party_size or 0),
                caller_player_level=preflight_level,
                allow_player_reward_floor_fallback=True,
            )
            if replacement is not None:
                return replacement
            log_growth_route_preflight(
                args,
                realm_key=realm.key,
                current_level=preflight_level,
                party_size=int(party_size or 0),
                route=route,
                status="skip",
                reason="route_unsuitable_live_world:static_route_failed:no_verified_fallback",
            )
            raise RuntimeError(
                "growth party carry route_unsuitable_live_world after preflight; refusing static route: "
                f"realm={realm.key} party={int(party_size or 0)} level={preflight_level} "
                f"target_level={int(target_level or 0)} route={route.prefer or route.source}"
            )
    return route


def select_growth_route_point(
    args: argparse.Namespace,
    realm: RealmProfile,
    level: int,
    party_size: int = 0,
) -> RoutePoint:
    allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
        getattr(args, "growth_allow_lower_xp_gear_farm", True)
    )
    if (
        allow_lower_xp_target_plan
        and realm.key == "mid"
        and int(party_size or 0) <= 1
        and int(level or 0) == 7
    ):
        target_plan_override = getattr(args, "growth_target_plan_override", None)
        target_plan_ideal = 0
        if isinstance(target_plan_override, (list, tuple)) and len(target_plan_override) >= 2:
            target_plan_ideal = int(target_plan_override[1] or 0)
        prefer_lower_shortage_recovery = 0 < target_plan_ideal <= 5
        if not prefer_lower_shortage_recovery:
            recovery_route = route_point(
                7,
                787192,
                868637,
                6698,
                "carrion crawler",
                "vein spider,young grendelorm,black mauler juvenile,wood-eater worker,wood-eater,wood-eater hunter,wayward ghoul,dryad sprig,wolf spiderling,hill person,army ant worker,rock crab,roaming thrall,wood-eater soldier,wood-eater alate,wood-eater king,huldu,small hill cat,sapherd,pine imp,ghost light,haunt,roaming dirge,carrion eater,tawny lynx",
                "Gotar",
                source="hunting-index",
                mob_level=6,
                mob_count=33,
            )
            recovery_route_blocked = growth_route_blocked_by_failed_target_memory(
                args,
                recovery_route,
                realm.key,
                int(level or 0),
                int(party_size or 0),
            )
            if growth_route_preflight_enabled(args):
                checked_recovery_route = None
                if not recovery_route_blocked:
                    checked_recovery_route = growth_route_preflight_checked_route(
                        args,
                        recovery_route,
                        realm=realm,
                        current_level=int(level or 0),
                        party_size=int(party_size or 0),
                    )
                if checked_recovery_route is not None:
                    return checked_recovery_route
                if not recovery_route_blocked and not str(getattr(args, "growth_hunting_index", "") or "").strip():
                    return recovery_route
            else:
                if not recovery_route_blocked:
                    return recovery_route
        for shortage_target_level in ((5,) if prefer_lower_shortage_recovery else (6,)):
            target_route = select_growth_hunting_index_point_for_target(
                args,
                realm.key,
                shortage_target_level,
                party_size,
                caller_player_level=int(level or 0),
            )
            if target_route is not None:
                return target_route
        failed_target_tokens = preferred_target_tokens(
            growth_failed_target_memory_avoid_targets(args, realm.key, int(level or 0), int(party_size or 0))
        )
        recovery_routes = [
            route_point(
                7,
                776006,
                724447,
                4719,
                "young grendelorm",
                "vein spider,black mauler juvenile,wood-eater worker,wood-eater,wood-eater hunter,wayward ghoul,dryad sprig,wolf spiderling,hill person,army ant worker,rock crab,roaming thrall,carrion crawler,wood-eater soldier,wood-eater alate,wood-eater king,nacken,huldu,huldu hunter,huldu stalker,small hill cat,sapherd,pine imp,ghost light",
                "Mularn",
                source="hunting-index",
                mob_level=5,
                mob_count=15,
            ),
            route_point(
                7,
                787192,
                868637,
                6698,
                "carrion crawler",
                "black mauler juvenile,wood-eater worker,wood-eater,wood-eater hunter,wayward ghoul,dryad sprig,wolf spiderling,hill person,army ant worker,rock crab,roaming thrall,young grendelorm,vein spider,wood-eater soldier,wood-eater alate,wood-eater king,nacken,huldu,huldu hunter,huldu stalker,small hill cat",
                "Gotar",
                source="hunting-index",
                mob_level=6,
            ),
            route_point(
                7,
                777576,
                869618,
                5947,
                "carrion crawler",
                "black mauler juvenile,wood-eater worker,wood-eater,wood-eater hunter,wayward ghoul,dryad sprig,wolf spiderling,hill person,army ant worker,rock crab,roaming thrall,young grendelorm,vein spider,wood-eater soldier,wood-eater alate,wood-eater king,nacken,huldu,huldu hunter,huldu stalker,small hill cat",
                "Gotar",
                source="hunting-index",
                mob_level=6,
            ),
        ]
        recovery_routes = [
            route for route in recovery_routes if not target_name_matches_any(route.prefer, failed_target_tokens)
        ]
        checked_recovery_routes = growth_route_preflight_filter_routes(
            args,
            recovery_routes,
            realm=realm,
            current_level=int(level or 0),
            party_size=int(party_size or 0),
        )
        if checked_recovery_routes:
            return checked_recovery_routes[0]
        allow_index_after_preflight_miss = bool(
            growth_route_preflight_enabled(args)
            and str(getattr(args, "growth_hunting_index", "") or "").strip()
        )
        if recovery_routes and growth_route_preflight_strict_required(
            args,
            recovery_routes[0],
            current_level=int(level or 0),
            party_size=int(party_size or 0),
        ):
            if not allow_index_after_preflight_miss:
                return recovery_routes[0]
        elif recovery_routes and not allow_index_after_preflight_miss:
            return recovery_routes[-1]
    distributed_route = distributed_growth_hunting_index_route(args, realm, int(level or 0), int(party_size or 0))
    if distributed_route is not None:
        return distributed_route
    carry_index_route_mode = bool(
        int(party_size or 0) > 1
        and str(getattr(args, "growth_hunting_index", "") or "").strip()
        and (
            bool(getattr(args, "growth_route_level_is_carry_target", False))
            or growth_party_uses_carry_tuning(args, int(level or 0), int(party_size or 0))
        )
    )
    if (
        realm.key == "mid"
        and int(party_size or 0) <= 1
        and int(level or 0) == 9
        and int(getattr(args, "growth_shortage_recovery_player_level", 0) or 0) == 9
    ):
        return route_point(
            9,
            719301,
            770132,
            4506,
            "army ant worker",
            "host of the earth,hill person,nordic dirge,ghost light,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,wood-eater alate,small hill cat,tawny lynx cub,vein spiderling,young lynx,green serpent,wind wisp,envy drakeling",
            "Audliten",
            source="hunting-index",
            mob_level=7,
            mob_count=6,
        )
    if realm.key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return route_point(
            7,
            757484,
            847726,
            4650,
            "ghost light",
            "hill person,tawny lynx cub,vein spiderling,tawny lynx,nacken,wolf spiderling,wind wisp,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,wood-eater alate,small hill cat,young lynx,green serpent",
            "Gotar",
            source="hunting-index",
            mob_level=7,
            mob_count=19,
        )
    if realm.key == "hib" and int(party_size or 0) <= 1 and int(level or 0) in {8, 9}:
        return low_hib_solo_level_seven_route(args, level, party_size)
    if realm.key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 10:
        return low_alb_solo_level_ten_route(args, level, party_size)
    if realm.key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return low_alb_solo_level_nine_route(args, level, party_size)
    if realm.key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 8:
        return low_alb_solo_level_eight_route(args, level, party_size)
    if realm.key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 7:
        return low_alb_solo_level_seven_route(args, level, party_size)
    if realm.key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 10:
        return low_mid_solo_level_ten_route(args, level, party_size)
    if realm.key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 10:
        return route_point(
            8,
            352178,
            532352,
            4598,
            "water beetle",
            "lough wolf,red wolfhound,eriu waylayer,rat boy,minor changeling",
            "Tir na mBeo",
            source="hunting-index",
            mob_level=7,
            mob_count=1,
            live_anchor_z=True,
        )
    if (
        realm.key == "hib"
        and int(party_size or 0) <= 1
        and int(level or 0) == 5
        and int(getattr(args, "growth_shortage_recovery_player_level", 0) or 0) == 7
    ):
        return route_point(
            5,
            348637,
            479175,
            5742,
            "mudman",
            "feccan,lough wolf,wild crouch,water beetle,eirebug,spraggon,villainous youth",
            "",
            source="hunting-index",
            mob_level=4,
        )
    if (
        not allow_lower_xp_target_plan
        and int(party_size or 0) <= 1
        and int(level or 0) >= 5
    ):
        route_target_level = no_lower_xp_route_target_level(args, realm.key, int(level or 0), party_size)
        target_route = select_growth_hunting_index_point_for_target(
            args,
            realm.key,
            route_target_level,
            party_size,
            caller_player_level=int(level or 0),
        )
        if target_route is not None:
            return target_route
    if (
        realm.key == "mid"
        and int(party_size or 0) >= 8
        and int(level or 0) == 3
        and not bool(getattr(args, "growth_route_level_is_carry_target", False))
    ):
        return route_point(
            3,
            744988,
            807603,
            4548,
            "wild hog",
            "green serpent,spectral hog,huldu",
            "Fort Atla",
            source="hunting-index",
            mob_level=2,
            mob_count=32,
        )
    if (
        realm.key == "hib"
        and int(party_size or 0) == 2
        and int(level or 0) == 3
        and not bool(getattr(args, "growth_route_level_is_carry_target", False))
    ):
        return route_point(
            3,
            345100,
            474178,
            5473,
            "large frog,badger cub",
            "feccan,mudman,villainous youth,spraggon,water beetle collector,underhill companion,wolf cub",
            "Mag Mell",
            source="starter-safe",
            mob_level=2,
            mob_count=20,
        )
    if (
        realm.key == "hib"
        and int(party_size or 0) == 4
        and int(level or 0) == 4
        and not bool(getattr(args, "growth_route_level_is_carry_target", False))
    ):
        return route_point(
            4,
            361545,
            491812,
            4659,
            "small freshwater crab",
            "feccan,mudman,villainous youth,spraggon,water beetle collector,underhill companion,wolf cub",
            "Mag Mell",
            source="hunting-index",
            mob_level=4,
            mob_count=25,
        )
    if realm.key == "alb" and int(party_size or 0) == 4 and int(level or 0) in {6, 7}:
        return route_point(
            6,
            491813,
            601083,
            1858,
            "emerald snake",
            "rot worm,veteran rot worm,노련한 rot worm,rock imp,tree spirit,giant spider,adder,young cutpurse,river drakeling,river sprite,bear,carrion drake,dappled lynx cub,bandit",
            "Campacorentin Station",
            source="hunting-index",
            mob_level=5,
            mob_count=20,
        )
    if realm.key == "hib" and int(party_size or 0) >= 8 and int(level or 0) in {4, 5}:
        return route_point(
            int(level or 0),
            361545,
            491812,
            4659,
            "small freshwater crab",
            "",
            "Mag Mell",
            source="hunting-index",
        )
    if (
        realm.key == "alb"
        and int(party_size or 0) == 2
        and int(level or 0) == 6
        and not bool(getattr(args, "growth_route_level_is_carry_target", False))
    ):
        return route_point(
            6,
            464792,
            645770,
            1699,
            "rot worm",
            "faerie bell-wether,emerald snake,tree spirit,giant spider,adder,young cutpurse,river sprite,bandit,undead filidh,zombie boar,dappled lynx cub",
            "Avalon Marsh",
            source="hunting-index",
            mob_level=5,
            mob_count=28,
        )
    if realm.key == "mid" and int(party_size or 0) == 2 and int(level or 0) in {5, 6}:
        return route_point(
            5,
            731633,
            814288,
            5479,
            "black mauler juvenile",
            "wood-eater worker,wood-eater hunter,wood-eater soldier,hill person,young grendelorm,vein spider,huldu hunter,huldu stalker,small hill cat,young lynx,green serpent,lupine snarler,young sveawolf,huldu,wood-eater royal guard",
            "Fort Atla",
            source="hunting-index",
            mob_level=5,
            mob_count=26,
        )
    if realm.key == "mid" and int(party_size or 0) == 4 and int(level or 0) in {5, 6}:
        return route_point(
            5,
            731633,
            814288,
            5479,
            "black mauler juvenile",
            "wood-eater worker,wood-eater hunter,wood-eater soldier,hill person,young grendelorm,vein spider,huldu hunter,huldu stalker,small hill cat,young lynx,green serpent,lupine snarler,young sveawolf,huldu,wood-eater royal guard",
            "Fort Atla",
            source="hunting-index",
            mob_level=5,
            mob_count=26,
        )
    if realm.key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return route_point(
            7,
            770541,
            749708,
            4552,
            "tawny lynx cub,vein spiderling",
            "tawny lynx,nacken,ghost light,wolf spiderling,wind wisp,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,wood-eater alate,small hill cat,young lynx,green serpent",
            "Bind Start",
            source="hunting-index",
            mob_level=7,
            mob_count=6,
        )
    index = load_growth_hunting_index(args)
    index_level = int(level or 0)
    if bool(getattr(args, "growth_route_level_is_carry_target", False)) and int(party_size or 0) > 1:
        if realm.key == "alb" and int(party_size or 0) >= 8 and index_level == 7:
            return route_point(
                7,
                526821,
                614578,
                1847,
                "bandit",
                "ant drone,wild boar,tree spirit,adder,giant spider",
                "Caer Ulfwych",
                source="hunting-index",
            )
        if realm.key == "alb" and int(party_size or 0) == 2 and index_level == 5:
            return route_point(
                4,
                495960,
                596970,
                1961,
                "gray wolf",
                "rot worm,faerie bell-wether,tree spirit,adder,giant spider",
                "Campacorentin Station",
                source="hunting-index",
            )
        if realm.key == "alb" and int(party_size or 0) == 2 and index_level in {6, 7}:
            return route_point(
                6,
                489000,
                600500,
                1900,
                "emerald snake",
                "faerie bell-wether,worker ant,rot worm,bogman grappler,tree spirit,bandit,ant drone,giant spider,adder,young cutpurse,river sprite,zombie boar,dappled lynx cub",
                "Campacorentin Station",
                source="hunting-index",
                mob_level=6,
                mob_count=20,
            )
        if realm.key == "alb" and int(party_size or 0) == 2 and index_level == 8:
            return growth_static_route_or_preflight_fallback(
                args,
                realm,
                route_point(
                    8,
                    527242,
                    624780,
                    1971,
                    "rotting zombie",
                    "death grip vines,bloody-bones,river racer,bear,forest bear,forest lion,forest cat,undead filidh,bandit,spirit,giant spider,adder,young cutpurse,fading spirit,spectral hound,large skeleton,tree spirit,dryad,filidh,ant drone,devout filidh,pixie scout,픽시 정찰병,faerie bell-wether",
                    "Caer Ulfwych",
                    source="hunting-index",
                    mob_level=7,
                    mob_count=2,
                ),
                current_level=index_level,
                party_size=party_size,
                target_level=index_level,
            )
        if realm.key == "alb" and int(party_size or 0) == 2 and index_level == 9:
            return growth_static_route_or_preflight_fallback(
                args,
                realm,
                route_point(
                    9,
                    496426,
                    593548,
                    1904,
                    "giant spider",
                    "dappled lynx cub,노련한 giant spider,veteran giant spider,노련한 거대 거미,bear,young boar,adder,filidh,devout filidh,cutpurse,spirit,dryad invert,wandering spirit,undead druid,boulderling",
                    "Campacorentin Station",
                    source="hunting-index",
                    mob_level=8,
                    mob_count=3,
                ),
                current_level=index_level,
                party_size=party_size,
                target_level=index_level,
            )
        if realm.key == "alb" and int(party_size or 0) >= 8 and index_level == 9:
            return route_point(
                9,
                575246,
                547179,
                2594,
                "bear",
                "cart horse,slave,wild boar,poacher,brownie nomad,bandit,boulderling,undead goblin warrior,large skeleton,filidh,devout filidh",
                "Prydwen Keep",
                source="hunting-index",
            )
        if realm.key == "alb" and int(party_size or 0) == 4 and index_level == 7:
            return route_point(
                8,
                575246,
                547179,
                2594,
                "bear",
                "tree spirit,filidh,devout filidh,wild boar,poacher,brownie nomad,bandit,boulderling,undead goblin warrior,large skeleton,cart horse,slave",
                "Prydwen Keep",
                source="hunting-index",
            )
        if realm.key == "mid" and int(party_size or 0) == 2 and index_level == 5:
            return route_point(
                5,
                786637,
                723034,
                4722,
                "wood-eater worker",
                "hill person,young grendelorm,vein spider,huldu hunter,huldu stalker,small hill cat,young lynx,green serpent,lupine snarler,young sveawolf",
                "Mularn",
                source="hunting-index",
                mob_level=4,
            )
        if realm.key == "hib" and int(party_size or 0) in {2, 4} and index_level == 5:
            low_hib_route = route_point(
                5,
                361545,
                491812,
                4659,
                "small freshwater crab",
                "feccan,spraggon,water beetle,water beetle collector,hill toad,lugradan whelp,villainous youth,wild crouch,underhill companion,wolf cub",
                "Mag Mell",
                source="hunting-index",
                mob_level=4,
                mob_count=8,
            )
            if bool(getattr(args, "growth_route_level_is_carry_target", False)) or growth_party_uses_carry_tuning(
                args,
                index_level,
                int(party_size or 0),
            ):
                reward_floor = growth_party_carry_reward_floor(args, index_level, int(party_size or 0), realm.key)
                if reward_floor > 0 and 0 < int(low_hib_route.mob_level or 0) < reward_floor:
                    target_route = select_growth_hunting_index_point_for_target(args, realm.key, index_level, party_size)
                    if target_route is not None:
                        return target_route
                    safe_hib_route = route_point(
                        5,
                        348694,
                        498242,
                        4620,
                        "water beetle collector",
                        "lough wolf,rat boy,red wolfhound,underhill companion,wolf cub,cluricaun trip,wild crouch,large eirebug,badger,young badger,spraggon,villainous youth,small freshwater crab,skeletal minion,Summoner",
                        "Mag Mell",
                        source="hunting-index",
                        mob_level=5,
                        mob_count=10,
                    )
                    if growth_route_preflight_enabled(args):
                        checked_safe_route = growth_route_preflight_checked_route(
                            args,
                            safe_hib_route,
                            realm=realm,
                            current_level=index_level,
                            party_size=int(party_size or 0),
                        )
                        if checked_safe_route is not None and int(getattr(checked_safe_route, "mob_level", 0) or 0) >= reward_floor:
                            return checked_safe_route
                        checked_route = growth_route_preflight_checked_route(
                            args,
                            low_hib_route,
                            realm=realm,
                            current_level=index_level,
                            party_size=int(party_size or 0),
                        )
                        if checked_route is not None and int(getattr(checked_route, "mob_level", 0) or 0) >= reward_floor:
                            return checked_route
                        raise RuntimeError(
                            "growth party carry route unavailable above reward floor: "
                            f"realm={realm.key} party={int(party_size or 0)} level={index_level} floor={reward_floor}"
                        )
                    return safe_hib_route
                    # Do not fall back to this stale L4 camp for carry mode; L5 runs have recorded no XP here.
                else:
                    return low_hib_route
            else:
                return low_hib_route
        if realm.key == "hib" and int(party_size or 0) == 2 and index_level == 7:
            return route_point(
                6,
                309663,
                647096,
                5234,
                "hill toad",
                "feccan,underhill companion,wolf cub",
                "Shannon Estuary",
                source="hunting-index",
            )
        if realm.key == "hib" and int(party_size or 0) == 2 and index_level in {8, 9, 10}:
            return growth_static_route_or_preflight_fallback(
                args,
                realm,
                route_point(
                    8,
                    347282,
                    504287,
                    4841,
                    "water beetle",
                    "lunantishee,blackthorn,Clik,lough wolf,red wolfhound,ghostly siabra,rat boy,badger,young badger,underhill companion,wolf cub,cluricaun trip,wild crouch,large eirebug",
                    "Mag Mell",
                    source="hunting-index",
                    mob_level=7,
                    mob_count=17,
                ),
                current_level=index_level,
                party_size=party_size,
                target_level=index_level,
            )
        if realm.key == "hib" and int(party_size or 0) == 2 and index_level == 11:
            return growth_static_route_or_preflight_fallback(
                args,
                realm,
                route_point(
                    11,
                    399151,
                    531103,
                    2926,
                    "barca",
                    "red wolfhound,wild lucradan,badger,young badger,anger sprite,ghostly siabra,ghastly siabra,roane maiden,fishing bear forager,lough wolf,large eirebug,curmudgeon harvester,curmudgeon fighter,curmudgeon crab-catcher,curmudgeon trapper,curmudgeon skinner",
                    "Tir na mBeo",
                    source="hunting-index",
                    mob_level=11,
                    mob_count=4,
                ),
                current_level=index_level,
                party_size=party_size,
                target_level=index_level,
            )
        if realm.key == "mid" and int(party_size or 0) == 2 and index_level in {8, 9, 10}:
            return growth_static_route_or_preflight_fallback(
                args,
                realm,
                mid_level_ten_tawny_lynx_party_route(),
                current_level=index_level,
                party_size=party_size,
                target_level=index_level,
            )
        if realm.key == "hib" and int(party_size or 0) == 4 and index_level == 6:
            return route_point(
                6,
                309663,
                647096,
                5234,
                "hill toad",
                "feccan,underhill companion,wolf cub,water beetle collector,spraggon",
                "Shannon Estuary",
                source="hunting-index",
            )
        if realm.key == "mid" and int(party_size or 0) >= 8 and index_level == 7:
            return route_point(
                7,
                757484,
                847726,
                4650,
                "ghost light",
                "wind wisp,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,wood-eater alate,small hill cat",
                "Gotar",
                source="hunting-index",
            )
        if realm.key == "mid" and int(party_size or 0) == 4 and index_level == 7:
            return route_point(
                8,
                739371,
                789159,
                4714,
                "army ant soldier",
                "ghost light,host of the wind,wind wisp,lake serpent,large sveawolf,blodfelag oathbreaker,water snake,nordic dirge,mindless thrall,smiera-gatto,black mauler juvenile,sveawolf mother,huldu stalker,seithr orb",
                "Huginfell",
                source="hunting-index",
            )
        if realm.key == "hib" and int(party_size or 0) >= 8 and index_level in {7, 8}:
            return route_point(
                8,
                352162,
                527862,
                4679,
                "water beetle",
                "lough wolf,red wolfhound,underhill companion,wolf cub,cluricaun trip,wild crouch,large eirebug,badger,young badger,water beetle collector",
                "Tir na mBeo",
                source="hunting-index",
                mob_level=8,
                mob_count=13,
            )
        target_route = select_growth_hunting_index_point_for_target(args, realm.key, index_level, party_size)
        if target_route is not None:
            return target_route
        if carry_index_route_mode:
            raise RuntimeError(
                "growth party carry hunting-index route unavailable after preflight; refusing static route: "
                f"realm={realm.key} party={int(party_size or 0)} level={index_level}"
            )
    if realm.key == "alb" and int(party_size or 0) <= 1 and index_level == 6:
        index_level = 4
    if realm.key == "alb" and int(party_size or 0) <= 1 and index_level == 7:
        return low_alb_solo_level_seven_route(args, index_level, party_size)
    if realm.key == "hib" and int(party_size or 0) <= 1 and index_level in {7, 8}:
        return low_hib_solo_level_seven_route(args, index_level, party_size)
    if realm.key in {"mid", "hib"} and int(party_size or 0) == 4 and index_level == 3:
        index_level = 2
    if realm.key == "hib" and int(party_size or 0) >= 8 and index_level == 3:
        index_level = 2
    if realm.key == "alb" and int(party_size or 0) == 2 and index_level == 6:
        index_level = 5
    if realm.key == "alb" and int(party_size or 0) == 2 and index_level == 7:
        return route_point(
            6,
            464792,
            645770,
            1699,
            "rot worm",
            "tree spirit,bandit,ant drone,giant spider,adder,young cutpurse,emerald snake,river drakeling",
            "Avalon Marsh",
            source="hunting-index",
        )
    if realm.key == "alb" and int(party_size or 0) == 2 and index_level in {8, 9, 10, 11}:
        return route_point(
            8,
            575246,
            547179,
            2594,
            "bear",
            "filidh,devout filidh,cutpurse,spirit,dryad invert,wandering spirit,undead druid,boulderling",
            "Prydwen Keep",
            source="hunting-index",
        )
    if realm.key == "alb" and int(party_size or 0) == 4 and index_level == 7:
        return route_point(
            6,
            491813,
            601083,
            1858,
            "emerald snake",
            "rot worm,veteran rot worm,노련한 rot worm,bandit,boulderling,undead goblin warrior,will o' wisp,tree spirit,giant spider,adder",
            "Campacorentin Station",
            source="hunting-index",
            mob_level=5,
            mob_count=20,
        )
    if realm.key == "alb" and int(party_size or 0) == 4 and index_level == 8:
        return route_point(
            8,
            575246,
            547179,
            2594,
            "bear",
            "filidh,devout filidh,cutpurse,spirit,dryad invert,wandering spirit,undead druid,boulderling",
            "Prydwen Keep",
            source="hunting-index",
        )
    if realm.key == "alb" and int(party_size or 0) == 4 and index_level in {9, 10, 11, 12, 13, 14}:
        return route_point(
            11,
            606316,
            562852,
            2066,
            "slave",
            "giant wolf,cutpurse,spirit,dryad invert,wandering spirit,undead druid,boulderling,bandit leader",
            "Prydwen Keep",
            source="hunting-index",
        )
    if realm.key == "alb" and int(party_size or 0) >= 8 and index_level in {6, 7}:
        return route_point(
            7,
            517887,
            630221,
            1765,
            "ant drone",
            "filidh,devout filidh,bear,wild boar,poacher,brownie nomad,boulderling,undead goblin warrior,large skeleton,tree spirit,giant spider,adder",
            "Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
            mob_count=10,
        )
    if realm.key == "alb" and int(party_size or 0) >= 8 and index_level == 8:
        return route_point(
            7,
            517887,
            630221,
            1765,
            "ant drone",
            "filidh,devout filidh,bear,wild boar,poacher,brownie nomad,boulderling,undead goblin warrior,large skeleton,tree spirit,giant spider,adder",
            "Caer Ulfwych",
            source="hunting-index",
            mob_level=7,
            mob_count=10,
        )
    if realm.key == "alb" and int(party_size or 0) >= 8 and index_level == 9:
        return route_point(
            11,
            541297,
            485811,
            4807,
            "red dwarf leader",
            "wild boar,poacher,brownie nomad,bandit,boulderling,undead goblin warrior,large skeleton",
            "Bind Start",
            source="hunting-index",
        )
    if realm.key == "alb" and int(party_size or 0) <= 1 and index_level == 8:
        return route_point(
            6,
            538820,
            482013,
            3073,
            "young cutpurse",
            "giant spider,tree spirit,large skeleton,sylvan goblin hunter,river sprite",
            "Bind Start",
            source="hunting-index",
        )
    if realm.key == "mid" and int(party_size or 0) <= 1 and index_level == 9:
        return route_point(
            7,
            757484,
            847726,
            4650,
            "ghost light",
            "hill person,tawny lynx cub,vein spiderling,tawny lynx,nacken,wolf spiderling,wind wisp,host of the wind,Svartmoln,army ant soldier,wood-eater soldier,wood-eater alate,small hill cat,young lynx,green serpent",
            "Gotar",
            source="hunting-index",
            mob_level=7,
            mob_count=19,
        )
    if realm.key == "hib" and int(party_size or 0) <= 1 and index_level in {9, 10}:
        return route_point(
            9,
            349869,
            494579,
            5191,
            "lough wolf",
            "water beetle,water beetle collector,hill toad,lugradan whelp,minor changeling,eriu waylayer,rat boy,red wolfhound",
            "Mag Mell",
            source="hunting-index",
            mob_level=7,
            mob_count=3,
        )
    if realm.key == "hib" and int(party_size or 0) <= 1 and index_level == 11:
        return route_point(
            11,
            356325,
            491544,
            5405,
            "hill toad",
            "water beetle,minor changeling,eriu waylayer,rat boy",
            "Mag Mell",
            source="hunting-index",
        )
    if realm.key == "hib" and int(party_size or 0) == 2 and index_level == 8:
        return route_point(
            8,
            347102,
            496129,
            5127,
            "lough wolf",
            "water beetle,large frog,badger cub,minor changeling,rat boy",
            "Mag Mell",
            source="hunting-index",
        )
    if realm.key == "mid" and int(party_size or 0) == 4 and index_level == 9:
        return route_point(
            8,
            739371,
            789159,
            4714,
            "army ant soldier",
            "wind wisp,ghost light,host of the wind,lake serpent,large sveawolf,blodfelag oathbreaker,water snake,nordic dirge,mindless thrall,smiera-gatto,black mauler juvenile,sveawolf mother,huldu stalker,seithr orb",
            "Huginfell",
            source="hunting-index",
        )
    if realm.key == "mid" and int(party_size or 0) == 2 and index_level == 8:
        return route_point(
            8,
            739371,
            789159,
            4714,
            "army ant soldier",
            "wind wisp,ghost light,host of the wind,carrion crawler,Svartmoln,wood-eater soldier,wood-eater alate,small hill cat",
            "Huginfell",
            source="hunting-index",
        )
    if realm.key == "mid" and int(party_size or 0) == 2 and index_level in {9, 10, 11}:
        return route_point(
            8,
            739371,
            789159,
            4714,
            "army ant soldier",
            "wind wisp,ghost light,host of the wind,carrion crawler,Svartmoln,wood-eater soldier,wood-eater alate,small hill cat,lake serpent,seithr orb,hobgoblin prowler",
            "Huginfell",
            source="hunting-index",
        )
    if realm.key == "mid" and int(party_size or 0) >= 8 and index_level in {7, 8, 9}:
        return route_point(
            10,
            713945,
            769705,
            4191,
            "lake serpent",
            "wind wisp,ghost light,host of the wind,seithr orb,hobgoblin prowler,wood-eater soldier,wood-eater alate,small hill cat,Svartmoln",
            "Huginfell",
            source="hunting-index",
        )
    if realm.key == "hib" and int(party_size or 0) == 4 and index_level == 9:
        return route_point(
            9,
            336058,
            505394,
            5210,
            "lough wolf",
            "red wolfhound,water beetle,young badger,badger",
            "Tir na mBeo",
            source="hunting-index",
        )
    if realm.key == "hib" and int(party_size or 0) >= 8 and index_level == 9:
        return route_point(
            10,
            334856,
            531370,
            5456,
            "red wolfhound",
            "lough wolf,large eirebug,young badger,badger,water beetle,cluricaun trip,spraggonoll,curmudgeon harvester,curmudgeon fighter",
            "Tir na mBeo",
            source="hunting-index",
        )
    if realm.key == "hib" and int(party_size or 0) == 4 and index_level == 10:
        return route_point(
            10,
            334856,
            531370,
            5456,
            "red wolfhound",
            "anger sprite,ghostly siabra,roane maiden,fishing bear forager,lough wolf,badger,young badger,curmudgeon harvester,curmudgeon fighter",
            "Tir na mBeo",
            source="hunting-index",
        )
    if realm.key == "hib" and int(party_size or 0) == 4 and index_level == 8:
        index_level = 7
    mid_duo_level_seven_index = realm.key == "mid" and int(party_size or 0) == 2 and index_level == 7
    if mid_duo_level_seven_index:
        index_level = 6
    if (
        not mid_duo_level_seven_index
        and realm.key in {"mid", "hib"}
        and int(party_size or 0) in {2, 4}
        and index_level == 6
    ):
        index_level = 5
    index_party_size = int(party_size or 0)
    candidates = index.get((realm.key, index_party_size, index_level))
    if not candidates and index_party_size > 0:
        candidates = index.get((realm.key, 0, index_level))
    original_candidates = list(candidates or [])
    candidates = filter_growth_hunting_index_candidates_for_target_band(
        args,
        list(candidates or []),
        realm_key=realm.key,
        level=int(level or 0),
        party_size=int(party_size or 0),
    )
    level_one_target_band: tuple[int, int] | None = None

    def filter_level_one_party_candidates(route_candidates: Iterable[RoutePoint]) -> list[RoutePoint]:
        nonlocal level_one_target_band
        if level_one_target_band is None:
            level_one_target_band = growth_hunting_index_candidate_target_band(
                args,
                realm_key=realm.key,
                level=int(level or 1),
                party_size=int(party_size or 0),
            )
        level_one_min_mob_level, level_one_max_mob_level = level_one_target_band
        return [
            candidate
            for candidate in route_candidates
            if int(level_one_min_mob_level)
            <= int(getattr(candidate, "mob_level", 0) or 0)
            <= int(level_one_max_mob_level)
        ]

    if candidates and int(party_size or 0) >= 4 and int(level or 0) <= 1:
        candidates = filter_level_one_party_candidates(candidates)
        if not candidates and index_party_size > 0:
            fallback_candidates = index.get((realm.key, 0, index_level))
            candidates = filter_level_one_party_candidates(list(fallback_candidates or []))
    if not candidates and int(party_size or 0) >= 4 and int(level or 0) <= 1:
        for fallback_party_size in (4, 2, 1, 0):
            if fallback_party_size == index_party_size:
                continue
            fallback_candidates = filter_level_one_party_candidates(
                list(index.get((realm.key, fallback_party_size, index_level)) or [])
            )
            if fallback_candidates:
                candidates = fallback_candidates
                break
    if candidates and realm.key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 7:
        allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
            getattr(args, "growth_allow_lower_xp_gear_farm", True)
        )
        target_plan_override = getattr(args, "growth_target_plan_override", None)
        if allow_lower_xp_target_plan and isinstance(target_plan_override, (list, tuple)) and target_plan_override:
            min_effective = int(target_plan_override[0])
        else:
            min_effective = minimum_growth_effective_target_level(level, party_size, realm.key)
        candidates = [
            candidate
            for candidate in candidates
            if int(getattr(candidate, "mob_level", 0) or 0) >= min_effective
        ]
    preflight_fallback_candidates = list(candidates or [])
    if candidates:
        candidates = growth_route_preflight_filter_routes(
            args,
            candidates,
            realm=realm,
            current_level=int(level or 1),
            party_size=int(party_size or 0),
        )
        if not candidates and int(party_size or 0) >= 4 and int(level or 0) <= 1:
            for fallback_party_size in (4, 2, 1, 0):
                if fallback_party_size == index_party_size:
                    continue
                fallback_candidates = filter_level_one_party_candidates(
                    list(index.get((realm.key, fallback_party_size, index_level)) or [])
                )
                if not fallback_candidates:
                    continue
                fallback_candidates = growth_route_preflight_filter_routes(
                    args,
                    fallback_candidates,
                    realm=realm,
                    current_level=int(level or 1),
                    party_size=int(party_size or 0),
                )
                if fallback_candidates:
                    candidates = fallback_candidates
                    break
    if candidates:
        allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
            getattr(args, "growth_allow_lower_xp_gear_farm", True)
        )
        target_plan_override = getattr(args, "growth_target_plan_override", None)
        prefer_lower_shortage_recovery = (
            allow_lower_xp_target_plan
            and isinstance(target_plan_override, (list, tuple))
            and len(target_plan_override) >= 2
            and 0 < int(target_plan_override[1] or 0) <= 5
        )
        if allow_lower_xp_target_plan and realm.key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 7:
            if prefer_lower_shortage_recovery:
                preferred_names = ("black mauler juvenile", "young grendelorm", "vein spider")
            else:
                preferred_names = ("carrion crawler", "young grendelorm", "vein spider")
        else:
            preferred_names = preferred_growth_hunting_candidates(realm.key, int(level or 0), int(party_size or 0))
        for preferred_name in rotate_growth_preferred_names(
            args,
            preferred_names,
            realm_key=realm.key,
            level=int(level or 0),
            party_size=int(party_size or 0),
        ):
            preferred_pool = [
                candidate for candidate in candidates if candidate.prefer.strip().lower() == preferred_name
            ]
            if prefer_lower_shortage_recovery and preferred_name == "black mauler juvenile":
                preferred_pool = sorted(preferred_pool, key=lambda route: int(getattr(route, "mob_count", 0) or 0))
            if preferred_pool:
                return preferred_pool[
                    growth_route_selection_index(
                        args,
                        realm_key=realm.key,
                        level=int(level or 0),
                        party_size=int(party_size or 0),
                        modulo=len(preferred_pool),
                        salt=f"index-preferred:{preferred_name}",
                    )
                ]
        return candidates[
            growth_route_selection_index(
                args,
                realm_key=realm.key,
                level=int(level or 0),
                party_size=int(party_size or 0),
                modulo=len(candidates),
                salt="index-candidates",
            )
        ]
    if original_candidates and growth_route_preflight_strict_required(
        args,
        original_candidates[0],
        current_level=int(level or 0),
        party_size=int(party_size or 0),
    ):
        if (
            realm.key == "mid"
            and int(party_size or 0) <= 1
            and int(level or 0) == 7
        ):
            fallback_candidates = index.get((realm.key, int(party_size or 0), int(index_level or 0) + 1))
            if not fallback_candidates and int(party_size or 0) > 0:
                fallback_candidates = index.get((realm.key, 0, int(index_level or 0) + 1))
            fallback_filtered = growth_route_preflight_filter_routes(
                args,
                list(fallback_candidates or []),
                realm=realm,
                current_level=int(level or 0),
                party_size=int(party_size or 0),
            )
            if fallback_filtered:
                return fallback_filtered[
                    growth_route_selection_index(
                        args,
                        realm_key=realm.key,
                        level=int(level or 0),
                        party_size=int(party_size or 0),
                        modulo=len(fallback_filtered),
                        salt="index-next-level-fallback",
                    )
                ]
            return route_point(
                7,
                772957,
                725582,
                4754,
                "vein spider",
                "black mauler juvenile,wood-eater worker,wood-eater,wood-eater hunter,wayward ghoul,dryad sprig,wolf spiderling,hill person,army ant worker,rock crab,roaming thrall,young grendelorm,carrion crawler,wood-eater soldier,wood-eater alate,wood-eater king,nacken,huldu,huldu hunter,huldu stalker,small hill cat,sapherd,pine imp,ghost light",
                "",
                source="hunting-index-preflight-fallback",
                mob_level=5,
                mob_count=9,
            )
        fallback_pool = filter_routes_blocked_by_failed_target_memory(
            args,
            preflight_fallback_candidates or original_candidates,
            realm.key,
            int(level or 0),
            int(party_size or 0),
        )
        if fallback_pool:
            for preferred_name in rotate_growth_preferred_names(
                args,
                preferred_growth_hunting_candidates(realm.key, int(level or 0), int(party_size or 0)),
                realm_key=realm.key,
                level=int(level or 0),
                party_size=int(party_size or 0),
            ):
                preferred_pool = [
                    candidate for candidate in fallback_pool if candidate.prefer.strip().lower() == preferred_name
                ]
                if preferred_pool:
                    fallback_pool = preferred_pool
                    break
            selected = fallback_pool[
                growth_route_selection_index(
                    args,
                    realm_key=realm.key,
                    level=int(level or 0),
                    party_size=int(party_size or 0),
                    modulo=len(fallback_pool),
                    salt="index-preflight-unverified-fallback",
                )
            ]
            source = str(selected.source or "hunting-index")
            if not source.endswith("-preflight-unverified-fallback"):
                source = f"{source}-preflight-unverified-fallback"
            return route_point(
                selected.level,
                selected.x,
                selected.y,
                selected.z,
                selected.prefer,
                selected.avoid,
                selected.teleport_destination,
                selected.objective_adds,
                source=source,
                mob_level=selected.mob_level,
                mob_count=selected.mob_count,
            )
        return select_route_point(realm, level, party_size)
    if realm.key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 7:
        fallback_routes = [
            route_point(
                7,
                776006,
                724447,
                4719,
                "young grendelorm",
                "vein spider,black mauler juvenile,carrion crawler,wood-eater worker,wood-eater,wood-eater hunter,wayward ghoul,dryad sprig,wolf spiderling,hill person,army ant worker,rock crab,roaming thrall,wood-eater soldier,wood-eater alate,wood-eater king,nacken,huldu,huldu hunter,huldu stalker,small hill cat,sapherd,pine imp,ghost light,haunt,roaming dirge,carrion eater,tawny lynx",
                "Mularn",
                source="hunting-index",
                mob_level=5,
                mob_count=15,
            ),
            route_point(
                7,
                787192,
                868637,
                6698,
                "carrion crawler",
                "black mauler juvenile,wood-eater worker,wood-eater,wood-eater hunter,wayward ghoul,dryad sprig,wolf spiderling,hill person,army ant worker,rock crab,roaming thrall,young grendelorm,vein spider,wood-eater soldier,wood-eater alate,wood-eater king,nacken,huldu,huldu hunter,huldu stalker,small hill cat",
                "Gotar",
                source="hunting-index",
                mob_level=6,
            ),
        ]
        target_plan_override = getattr(args, "growth_target_plan_override", None)
        target_plan_ideal = 0
        if isinstance(target_plan_override, (list, tuple)) and len(target_plan_override) >= 2:
            target_plan_ideal = int(target_plan_override[1] or 0)
        prefer_lower_shortage_recovery = bool(allow_lower_xp_target_plan and 0 < target_plan_ideal <= 5)
        if not prefer_lower_shortage_recovery:
            fallback_routes = [fallback_routes[1], fallback_routes[0]]
        for fallback_route in fallback_routes:
            if not growth_route_blocked_by_failed_target_memory(
                args,
                fallback_route,
                realm.key,
                int(level or 0),
                int(party_size or 0),
            ):
                return fallback_route
        return fallback_routes[-1]
    return select_route_point(realm, level, party_size)


def relocate_growth_characters_to_route(
    args: argparse.Namespace,
    accounts: Iterable[str],
    realm: RealmProfile,
    route: RoutePoint,
) -> None:
    account_names = [account for account in accounts if account]
    if not account_names or getattr(args, "dry_run", False):
        return
    quoted = ", ".join(sql_quote(account) for account in account_names)
    step = int(getattr(args, "position_step", 0) or 0)
    z = route_position_z_for_point(
        realm,
        route,
        ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
    )
    x_cases = " ".join(
        f"WHEN {sql_quote(account)} THEN {route.x + step * index}"
        for index, account in enumerate(account_names)
    )
    y_cases = " ".join(
        f"WHEN {sql_quote(account)} THEN {route.y + step * index}"
        for index, account in enumerate(account_names)
    )
    sql = f"""
        UPDATE DOLCharacters
        SET
            Xpos = CASE AccountName {x_cases} ELSE Xpos END,
            Ypos = CASE AccountName {y_cases} ELSE Ypos END,
            Zpos = {z},
            Region = {realm.region},
            BindXpos = CASE AccountName {x_cases} ELSE BindXpos END,
            BindYpos = CASE AccountName {y_cases} ELSE BindYpos END,
            BindZpos = {z},
            BindRegion = {realm.region},
            Health = 1000000,
            Mana = 1000000,
            Endurance = 1000000
        WHERE AccountName IN ({quoted});
    """
    run_mysql(args, sql)


def should_use_growth_gear_farm_route(
    args: argparse.Namespace,
    realm: RealmProfile,
    *,
    current_level: int,
    party_size: int,
    item_plans: dict[str, GrowthItemPlan],
    snapshots: dict[str, CharacterSnapshot] | None = None,
) -> bool:
    if not bool(getattr(args, "growth_allow_lower_xp_gear_farm", True)):
        return False
    if realm.key != "alb" or int(party_size or 0) > 1 or int(current_level or 0) != 8:
        return False
    if any(parse_specs(snapshot.specs).get("Shields", 0) >= 6 for snapshot in (snapshots or {}).values()):
        return False
    return any(int(plan.buy_shortage_copper or 0) > 0 for plan in item_plans.values())


def growth_shortage_recovery_route_override(
    args: argparse.Namespace,
    realm: RealmProfile,
    *,
    current_level: int,
    party_size: int,
    item_plans: dict[str, GrowthItemPlan],
) -> tuple[int, int] | None:
    if not bool(getattr(args, "growth_allow_lower_xp_gear_farm", True)):
        return None
    if int(party_size or 0) != 1:
        return None
    if not any(int(plan.buy_shortage_copper or 0) > 0 for plan in item_plans.values()):
        return None
    if any(plan.buy_slots for plan in item_plans.values()):
        return None
    if realm.key == "hib" and int(current_level or 0) <= 2:
        return 1, 1
    if realm.key == "mid" and int(current_level or 0) == 7:
        return 7, 5
    if realm.key == "alb" and int(current_level or 0) == 7:
        return 7, 5
    if realm.key == "hib" and int(current_level or 0) == 7:
        return 7, 5
    if realm.key == "mid" and int(current_level or 0) == 8:
        return 8, 6
    if realm.key == "alb" and int(current_level or 0) in {8, 9}:
        return 8, 6
    if realm.key == "hib" and int(current_level or 0) == 9:
        return 8, 8
    if realm.key == "mid" and int(current_level or 0) == 9:
        return 9, 7
    if realm.key == "mid" and int(current_level or 0) == 10:
        return 10, 7
    return None


def apply_growth_shortage_recovery_route_override(
    behavior_args: argparse.Namespace,
    args: argparse.Namespace,
    realm: RealmProfile,
    *,
    current_level: int,
    party_size: int,
    item_plans: dict[str, GrowthItemPlan],
) -> bool:
    override = growth_shortage_recovery_route_override(
        args,
        realm,
        current_level=current_level,
        party_size=party_size,
        item_plans=item_plans,
    )
    if override is None:
        return False
    route_level, target_level = override
    behavior_args.growth_route_level_override = route_level
    behavior_args.growth_target_level_override = target_level
    behavior_args.growth_allow_lower_xp_target_plan = True
    behavior_args.growth_shortage_recovery_player_level = int(current_level or 0)
    if realm.key == "mid" and int(current_level or 0) == 7:
        behavior_args.growth_target_plan_override = (5, 5, 0)
    elif realm.key == "alb" and int(current_level or 0) == 7:
        behavior_args.growth_target_plan_override = (5, 5, 1)
    elif realm.key == "hib" and int(current_level or 0) == 7:
        behavior_args.growth_target_plan_override = (5, 5, 0)
    elif realm.key == "mid" and int(current_level or 0) == 8:
        behavior_args.growth_target_plan_override = (6, 6, 1)
    elif realm.key == "alb" and int(current_level or 0) in {8, 9}:
        behavior_args.growth_target_plan_override = (6, 6, 0)
    elif realm.key == "mid" and int(current_level or 0) == 9:
        behavior_args.growth_target_plan_override = (7, 7, 0)
    elif realm.key == "mid" and int(current_level or 0) == 10:
        behavior_args.growth_target_plan_override = (7, 7, 0)
    if realm.key == "hib" and int(current_level or 0) <= 2:
        behavior_args.growth_target_plan_override = (0, 0, 0)
    return True


def growth_survival_route_override(realm_key: str, current_level: int, party_size: int) -> tuple[int, int] | None:
    if str(realm_key or "").lower() == "mid" and int(party_size or 0) == 2 and int(current_level or 0) == 4:
        return 5, 5
    return None


def growth_effective_party_level(
    snapshots: dict[str, CharacterSnapshot],
    observed_level: int,
    party_size: int,
) -> int:
    max_level = max(1, int(observed_level or 1))
    if int(party_size or 0) < 4:
        return max_level
    return max_level


def apply_growth_survival_route_override(
    behavior_args: argparse.Namespace,
    realm: RealmProfile,
    *,
    current_level: int,
    party_size: int,
) -> bool:
    override = growth_survival_route_override(realm.key, current_level, party_size)
    if override is None:
        return False
    route_level, target_level = override
    behavior_args.growth_route_level_override = route_level
    behavior_args.growth_target_level_override = target_level
    return True


def should_stage_route_home_after_startup_services(
    args: argparse.Namespace,
    realm: RealmProfile,
    level: int,
    party_size: int = 0,
) -> bool:
    if str(getattr(args, "growth_fast_travel", "") or "").strip().lower() != "route-home":
        return False
    if str(getattr(args, "checkpoint_start_location", "realm-start") or "realm-start").strip().lower() != "route-home":
        return False
    if int(level or 0) >= 50:
        return False
    return bool(should_train_at_level(level) or (realm.startup_service_npc_name and int(level or 0) < 50))


def checkpoint_start_point(args: argparse.Namespace, realm: RealmProfile, level: int, party_size: int = 0) -> RoutePoint:
    location = str(getattr(args, "checkpoint_start_location", "realm-start") or "realm-start").strip().lower()
    if should_stage_route_home_after_startup_services(args, realm, level, party_size):
        return RoutePoint(level=0, x=realm.start[0], y=realm.start[1], z=realm.start[2])
    if location == "route-home":
        route_args = args
        route_level = level
        if growth_party_uses_carry_tuning(args, level, party_size):
            route_args = argparse.Namespace(**vars(args))
            route_args.growth_route_level_is_carry_target = True
            route_args.growth_route_player_level = level
            route_level = growth_party_behavior_route_level_for_start(args, level, party_size, realm.key)
        route = select_growth_route_point(route_args, realm, route_level, party_size)
        route = startup_route_home_after_services_point(
            realm,
            route,
            current_level=level,
            party_size=party_size,
            ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
        )
        if realm.key == "alb" and int(level or 0) == 10 and int(party_size or 0) <= 1 and "adder" in route.prefer.lower():
            x = 593200
            y = 499000
            z = sample_route_z(
                realm,
                build_realm_height_samplers(),
                x,
                y,
                route.z,
                ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
            )
            return replace(route, x=x, y=y, z=z)
        return route
    if location == "teleport":
        route = select_route_point(realm, level, party_size)
        destination_name = nearest_teleport_destination(realm, route)
        destination = teleport_destination_point(realm, destination_name)
        if destination is not None:
            x, y, z = destination
            return RoutePoint(level=0, x=x, y=y, z=z, teleport_destination=destination_name)
    return RoutePoint(level=0, x=realm.start[0], y=realm.start[1], z=realm.start[2])


def growth_party_leech_start_distance(level: int, party_size: int) -> int:
    if uses_growth_party_carry_tuning(level, party_size):
        return 450
    return 0


def growth_party_route_home_start_position(
    args: argparse.Namespace,
    row: dict[str, str],
    realm: RealmProfile,
    point: RoutePoint,
    *,
    level: int,
    party_size: int,
    row_index: int,
    tracked_index: int,
    carry_index: int,
) -> tuple[int, int, int]:
    step = int(getattr(args, "position_step", 0) or 0)
    role = str(row.get("growth_role", "") or "").strip().lower()
    leech_distance = growth_party_leech_start_distance(level, party_size)
    if role == "tracked" and leech_distance > 0:
        x = point.x + leech_distance
        y = point.y + step * tracked_index
    else:
        formation_index = carry_index if role == "carry" else row_index
        x = point.x + step * formation_index
        y = point.y + step * formation_index
    if bool(getattr(point, "live_anchor_z", False)):
        z = int(point.z) + int(getattr(args, "ground_z_offset", 0) or 0)
    else:
        z = sample_route_z(
            realm,
            build_realm_height_samplers(),
            x,
            y,
            point.z,
            ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
        )
    return x, y, z


def apply_checkpoint_start_to_account_rows(
    args: argparse.Namespace,
    rows: list[dict[str, str]],
    realm: RealmProfile,
    level: int,
    party_size: int = 0,
    *,
    start_point: RoutePoint | None = None,
) -> None:
    if not rows:
        return
    point = start_point or checkpoint_start_point(args, realm, level, party_size)
    tracked_index = 0
    carry_index = 0
    for index, row in enumerate(rows):
        x, y, z = growth_party_route_home_start_position(
            args,
            row,
            realm,
            point,
            level=level,
            party_size=party_size,
            row_index=index,
            tracked_index=tracked_index,
            carry_index=carry_index,
        )
        row["start_x"] = str(x)
        row["start_y"] = str(y)
        row["start_z"] = str(z)
        row["zone_id"] = str(realm.region)
        role = str(row.get("growth_role", "") or "").strip().lower()
        if role == "tracked":
            tracked_index += 1
        elif role == "carry":
            carry_index += 1


def skip_startup_teleport_for_checkpoint_start(args: argparse.Namespace) -> bool:
    location = str(getattr(args, "checkpoint_start_location", "realm-start") or "realm-start").strip().lower()
    return location in {"route-home", "teleport"}


def route_variant_node_id(realm: RealmProfile, point: RoutePoint) -> str:
    return f"{realm.key}_{point.level}_{point.x}_{point.y}"


def route_variant_points_for_graph(realm: RealmProfile) -> list[RoutePoint]:
    seen = {(point.level, point.x, point.y, point.z) for point in realm.points}
    variants: list[RoutePoint] = []
    for variant_group in (LEVEL_ONE_PARTY_ROUTE_VARIANTS, LEVEL_FOUR_PARTY_ROUTE_VARIANTS, LEVEL_TEN_PARTY_ROUTE_VARIANTS):
        for _party_size, variant in sorted(variant_group.get(realm.key, {}).items()):
            key = (variant.level, variant.x, variant.y, variant.z)
            if key in seen:
                continue
            variants.append(variant)
            seen.add(key)
    return variants


def route_travel_detours(realm: RealmProfile, source_id: str, destination: RoutePoint) -> tuple[RoutePoint, ...]:
    if (
        realm.key == "alb"
        and source_id == "alb_teleport_yarley_s_farm"
        and destination.level == 50
        and destination.x == 332701
        and destination.y == 669142
    ):
        return (
            RoutePoint(0, 368000, 676000, 5751),
            RoutePoint(0, 360000, 672000, 5958),
            RoutePoint(0, 350000, 668000, 6234),
            RoutePoint(0, 340000, 670000, 2556),
        )
    if (
        realm.key == "hib"
        and source_id == "hib_teleport_tir_na_mbeo"
        and destination.level == 10
        and destination.x == 336157
        and destination.y == 532604
    ):
        return (
            RoutePoint(0, 333500, 529000, 5278),
            RoutePoint(0, 333500, 531300, 5349),
        )
    return ()


def route_variant_travel_detours(realm: RealmProfile, source_id: str, variant: RoutePoint) -> tuple[RoutePoint, ...]:
    return route_travel_detours(realm, source_id, variant)


def target_levels(level: int, party_size: int, realm_key: str = "") -> tuple[int, int, int]:
    player_level = max(1, min(level, 50))
    if player_level <= 1:
        if party_size <= 1:
            return 0, 0, 1
        if party_size <= 4:
            return 1, 1, 0
        if realm_key == "hib":
            return 1, 1, 0
        return 1, 1, 0

    if player_level < 5:
        if party_size <= 1:
            if player_level == 2:
                return 1, 1, 0
            if realm_key == "hib" and player_level == 3:
                return 1, 1, 0
            if player_level == 3:
                return 2, 2, 0
            if player_level == 4:
                return 2, 2, 0
            return max(1, player_level - 2), player_level, 0
        if realm_key == "hib" and player_level == 3 and party_size == 2:
            return 2, 3, 1
        if realm_key == "hib" and player_level == 3 and party_size >= 8:
            return 1, 2, 1
        if realm_key == "mid" and party_size >= 8 and player_level >= 3:
            if player_level == 3:
                return 2, 3, 1
            return player_level, player_level, 0
        if party_size <= 2:
            target = max(1, player_level - 1)
            return target, target, 0
        if party_size <= 4:
            target = max(1, player_level - 1)
            return target, player_level, 0
        target = max(1, player_level - 1)
        return target, player_level, 0

    if player_level == 5 and party_size <= 1:
        if realm_key == "alb":
            return 3, 3, 0
        if realm_key == "mid":
            return 3, 3, 0
        if realm_key == "hib":
            return 4, 4, 0
        return 2, 2, 0

    if realm_key == "hib" and party_size <= 1 and player_level == 11:
        return 7, 8, 1

    if 5 <= player_level <= 10 and party_size > 1:
        if party_size <= 2:
            if realm_key == "mid" and player_level == 5:
                return 4, 5, 1
            if realm_key == "mid" and player_level == 6:
                return 4, 5, 1
            if realm_key == "alb" and player_level == 6:
                return 5, 6, 1
            if realm_key == "alb" and player_level == 7:
                return 5, 6, 1
            elif realm_key == "hib" and player_level == 8:
                return 7, 8, 0
            elif realm_key == "mid" and player_level == 7:
                return 5, 6, 1
            elif realm_key == "mid" and player_level == 8:
                return 6, 7, 1
            elif player_level <= 5:
                target = 4
            elif player_level <= 9:
                target = max(1, player_level - 2)
            else:
                target = 7
        elif party_size <= 4:
            if realm_key == "mid" and player_level == 5:
                return 4, 5, 1
            if realm_key == "mid" and player_level == 6:
                return 4, 5, 1
            if realm_key == "alb" and player_level == 7:
                return 5, 6, 1
            if realm_key == "mid" and player_level == 9:
                return 8, 8, 0
            if realm_key == "hib" and player_level == 10:
                return 10, 10, 0
            if realm_key == "hib" and player_level == 9:
                return 8, 8, 0
            if realm_key == "hib" and player_level == 8:
                target = 7
            elif realm_key == "alb" and player_level == 6:
                target = 5
            elif realm_key == "mid" and player_level == 7:
                target = 7
            elif player_level <= 5:
                target = 4
            elif player_level <= 7:
                target = 5
            elif player_level <= 9:
                target = max(1, player_level - 2)
            else:
                target = 8
        else:
            if realm_key == "alb" and party_size >= 8 and player_level == 5:
                return 4, 4, 0
            target = player_level
            return target, target, 1
        return target, target, 0

    if player_level == 6 and party_size <= 1:
        if realm_key == "alb":
            return 4, 4, 0
        return 4, 4, 0

    if player_level == 7 and party_size <= 1 and realm_key == "alb":
        return 5, 5, 0

    if player_level == 7 and party_size <= 1 and realm_key == "mid":
        return 6, 6, 0

    if player_level in {7, 8} and party_size <= 1 and realm_key == "hib":
        return 5, 6, 1

    if player_level <= 7 and party_size <= 1:
        target = max(1, player_level - 1)
        return target, target, 0

    if player_level == 8 and party_size <= 1 and realm_key == "alb":
        return 6, 6, 0

    if player_level == 8 and party_size <= 1 and realm_key == "mid":
        return 6, 7, 1

    if player_level == 8 and party_size <= 1:
        return 6, 6, 0

    if player_level == 9 and party_size <= 1 and realm_key == "alb":
        return 7, 7, 0

    if player_level == 9 and party_size <= 1 and realm_key == "mid":
        return 7, 8, 1

    if player_level == 10 and party_size <= 1 and realm_key == "mid":
        return 7, 7, 0

    if player_level <= 10 and party_size <= 1:
        target = max(1, player_level - 2)
        if realm_key == "hib" and player_level == 9:
            return 6, 6, 0
        if realm_key == "hib" and player_level == 10:
            return 6, 6, 0
        if realm_key == "alb" and player_level == 10:
            return 7, 7, 0
        if player_level == 10:
            return max(1, target - 1), target, 1
        return max(1, target - 1), target, 0

    if player_level >= 50:
        if party_size <= 2:
            return 46, 47, 1
        return 46, 48, 2

    ideal_bonus = 1 if party_size == 1 else 1 if party_size <= 2 else 2 if party_size <= 4 else 3
    max_delta = 1 if party_size == 1 else 2 if party_size <= 2 else 3 if party_size <= 4 else 5
    return max(1, player_level - 1), min(50, player_level + ideal_bonus), max_delta


def uses_level_one_starter_survival_tuning(level: int, party_size: int) -> bool:
    return max(1, int(level or 1)) <= 1 and int(party_size or 0) <= 2


def uses_low_solo_flee_tuning(level: int, party_size: int, realm_key: str = "") -> bool:
    realm = str(realm_key or "").lower()
    player_level = max(1, int(level or 1))
    return uses_level_one_starter_survival_tuning(level, party_size) or (
        int(party_size or 0) <= 1 and realm == "hib" and player_level == 4
    )


def uses_low_small_party_commit_tuning(level: int, party_size: int, realm_key: str = "") -> bool:
    del realm_key
    player_level = max(1, int(level or 1))
    return 2 <= int(party_size or 0) <= 4 and 4 <= player_level <= 7


def uses_hib_low_duo_recovery_tuning(level: int, party_size: int, realm_key: str = "") -> bool:
    return str(realm_key or "").lower() == "hib" and int(party_size or 0) == 2 and max(1, int(level or 1)) <= 2


def uses_growth_party_carry_tuning(level: int, party_size: int) -> bool:
    del level
    return int(party_size or 0) > 1


def growth_party_carry_count(party_size: int) -> int:
    if int(party_size or 0) <= 1:
        return 0
    return max(1, int(party_size or 0) - 1)


def growth_party_carry_party_slots(party_size: int) -> list[int]:
    return list(range(growth_party_carry_count(party_size)))


GROWTH_PARTY_CARRY_GREY_SPANS_BY_PLAYER_LEVEL = (
    0,  # 0, unused
    0,
    0,
    1,
    2,
    3,
    4,
    5,
    6,
    7,
    7,
    7,
    7,
    8,
    9,
    10,
    11,
    12,
    13,
    14,
    14,
    14,
    14,
    15,
    16,
    17,
    18,
    19,
    20,
    21,
    22,
    23,
    24,
    25,
    26,
    26,
    26,
    26,
    26,
    26,
    26,
    27,
    28,
    29,
    30,
    31,
    32,
    33,
    34,
    35,
    36,
)


def growth_party_carry_level(args: argparse.Namespace, tracked_level: int, party_size: int | None = None) -> int:
    active_party_size = int(party_size if party_size is not None else getattr(args, "current_party_size", 0) or 0)
    if active_party_size <= 1:
        return max(1, int(tracked_level or 1))
    base_level = growth_party_carry_level_for_party(tracked_level, active_party_size)
    target_level = growth_party_carry_target_level(tracked_level, active_party_size)
    lowest_target_level, _, _ = growth_party_carry_target_plan(tracked_level, active_party_size)
    offset = max(0, int(getattr(args, "growth_party_carry_level_offset", 0) or 0))
    level = min(50, max(base_level, target_level + offset))
    return min(level, growth_party_carry_max_non_grey_level_for_target(lowest_target_level))


def growth_party_carry_level_for_realm(
    args: argparse.Namespace,
    tracked_level: int,
    party_size: int | None = None,
    realm_key: str = "",
) -> int:
    active_party_size = int(party_size if party_size is not None else getattr(args, "current_party_size", 0) or 0)
    if active_party_size > 1:
        base_level = growth_party_carry_level_for_party(tracked_level, active_party_size)
        target_level = growth_party_carry_target_level_for_realm(tracked_level, active_party_size, realm_key)
        target_plan = growth_party_carry_target_plan_for_realm(
            tracked_level,
            active_party_size,
            realm_key,
        )
        no_injected_carry_gear = not bool(getattr(args, "growth_equip_party_carry_gear", False))
        if no_injected_carry_gear:
            target_plan = growth_ungeared_party_carry_target_plan(
                tracked_level,
                active_party_size,
                realm_key,
                target_plan,
            )
            target_level = int(target_plan[1])
            ungeared_bonus = 1 if active_party_size <= 2 else 2 if active_party_size <= 4 else 3
            base_level = max(target_level, target_level + ungeared_bonus)
        lowest_target_level, _, _ = target_plan
        offset = max(0, int(getattr(args, "growth_party_carry_level_offset", 0) or 0))
        offset_target_level = target_level + offset
        level = min(50, max(base_level, offset_target_level))
        if no_injected_carry_gear:
            level = min(level, growth_party_carry_max_non_grey_level_for_target(lowest_target_level))
        return level
    return growth_party_carry_level(args, tracked_level, active_party_size)


def growth_party_carry_max_non_grey_level_for_target(target_level: int) -> int:
    target = max(1, int(target_level or 1))
    max_level = 1
    for player_level, grey_span in enumerate(GROWTH_PARTY_CARRY_GREY_SPANS_BY_PLAYER_LEVEL):
        if player_level <= 0:
            continue
        if target >= grey_span:
            max_level = player_level
    return min(50, max_level)


def growth_party_carry_target_gap(party_size: int) -> int:
    if int(party_size or 0) >= 8:
        return 10
    if int(party_size or 0) >= 4:
        return 8
    if int(party_size or 0) >= 2:
        return 5
    return 0


def growth_party_carry_target_gap_for_level(tracked_level: int, party_size: int) -> int:
    party = int(party_size or 0)
    if party <= 1:
        return 0
    level = max(1, int(tracked_level or 1))
    if level <= 4:
        if party >= 8:
            if level <= 2:
                return 5
            return 3
        if party >= 4:
            return 3 if level <= 1 else 2
        return 2 if level <= 1 else 1
    if level <= 6:
        if party >= 8:
            return 3
        if party >= 4:
            return 2
        return 1
    if level <= 8:
        if party >= 8:
            return 4
        if party >= 4:
            return 3
        return 2
    if level <= 10:
        if party >= 8:
            return 5
        if party >= 4:
            return 4
        return 3
    return growth_party_carry_target_gap(party)


def growth_party_carry_challenge_target_offset(party_size: int) -> int:
    del party_size
    return 0


def growth_party_carry_level_bonus(party_size: int) -> int:
    party = int(party_size or 0)
    if party <= 1:
        return 0
    if party >= 8:
        return 6
    return 5


def growth_party_carry_target_level(tracked_level: int, party_size: int) -> int:
    player_level = max(1, int(tracked_level or 1))
    if int(party_size or 0) <= 1:
        return player_level
    target_level = max(1, player_level + growth_party_carry_target_gap_for_level(player_level, party_size))
    return min(50, target_level)


def growth_party_carry_base_level(tracked_level: int, party_size: int) -> int:
    target_level = growth_party_carry_target_level(tracked_level, party_size)
    if int(party_size or 0) <= 1:
        return target_level
    challenge_offset = growth_party_carry_challenge_target_offset(party_size)
    level_bonus = growth_party_carry_level_bonus(party_size)
    return min(49, max(1, target_level - challenge_offset + level_bonus))


def growth_party_carry_level_for_party(tracked_level: int, party_size: int) -> int:
    return growth_party_carry_base_level(tracked_level, party_size)


def growth_party_combat_level(
    snapshots: dict[str, CharacterSnapshot],
    current_level: int,
    party_size: int,
) -> int:
    del snapshots, party_size
    return max(1, int(current_level or 1))


def growth_party_carry_target_plan(tracked_level: int, party_size: int = 0) -> tuple[int, int, int]:
    target = growth_party_carry_target_level(tracked_level, party_size)
    party = int(party_size or 0)
    level = max(1, int(tracked_level or 1))
    min_target_fallback = 1 if 1 < party <= 2 else 0
    if party > 1 and level <= 6:
        max_delta = 1
    elif party > 1 and level <= 8:
        max_delta = 2
    else:
        max_delta = 3
    return max(1, target - min_target_fallback), target, max_delta


def growth_party_carry_target_plan_for_realm(
    tracked_level: int,
    party_size: int = 0,
    realm_key: str = "",
) -> tuple[int, int, int]:
    realm = str(realm_key or "").lower()
    party = int(party_size or 0)
    level = max(1, int(tracked_level or 1))
    if str(realm_key or "").lower() == "hib" and int(party_size or 0) == 2 and int(tracked_level or 0) <= 2:
        target = max(1, int(tracked_level or 1))
        return 1, target, 0
    if realm == "mid" and party in {2, 4} and level <= 6:
        return 4, 5, 1
    if realm == "mid" and party in {2, 4} and level == 7:
        return 5, 6, 1
    if realm == "mid" and party == 2 and level == 10:
        return 8, 9, 1
    if realm == "mid" and party >= 8 and level <= 5:
        return 3, 4, 1
    if realm == "alb" and 2 <= party <= 4 and level <= 7:
        return 5, 6, 1
    if realm == "alb" and party == 2 and level == 10:
        return 7, 8, 1
    if realm == "hib" and party == 2 and level == 10:
        return 7, 8, 1
    plan = growth_party_carry_target_plan(tracked_level, party_size)
    if str(realm_key or "").lower() == "hib" and int(party_size or 0) >= 8 and int(tracked_level or 0) <= 6:
        return plan[0], plan[1], max(plan[2], 3)
    return plan


def growth_ungeared_party_carry_target_plan(
    tracked_level: int,
    party_size: int,
    realm_key: str,
    plan: tuple[int, int, int],
) -> tuple[int, int, int]:
    party = int(party_size or 0)
    level = max(1, int(tracked_level or 1))
    if party <= 1 or level > 10:
        return plan

    floor = max(1, minimum_growth_effective_target_level(level, party, realm_key))
    if party <= 2:
        if uses_growth_party_carry_tuning(level, party) and level >= 5:
            ideal_ceiling = level + 1
            delta_ceiling = 1
        else:
            ideal_ceiling = level
            delta_ceiling = 0
    else:
        ideal_ceiling = level + 1 if party <= 4 else level + 2
        delta_ceiling = 1 if party <= 4 else 2

    raw_min, raw_ideal, raw_delta = plan
    ideal = max(floor, min(int(raw_ideal), ideal_ceiling))
    min_target = max(floor, min(int(raw_min), ideal))
    max_delta = min(max(0, int(raw_delta)), delta_ceiling)
    return min_target, ideal, max_delta


def growth_party_carry_target_plan_for_combat_level(
    plan: tuple[int, int, int],
    combat_level: int,
) -> tuple[int, int, int]:
    min_target, ideal_target, max_delta = plan
    floor = minimum_non_grey_target_level(combat_level)
    if floor <= 0:
        return min_target, ideal_target, max_delta
    min_target = max(int(min_target), floor)
    ideal_target = max(int(ideal_target), min_target)
    return min_target, ideal_target, max_delta


def enforce_party_carry_non_grey_target_plan(
    args: argparse.Namespace,
    current_level: int,
    party_size: int,
    min_target: int,
    ideal_target: int,
    max_delta: int,
    realm_key: str = "",
) -> tuple[int, int, int]:
    if not growth_party_uses_carry_tuning(args, current_level, party_size):
        return min_target, ideal_target, max_delta
    carry_level = growth_party_carry_level_for_realm(args, current_level, party_size, realm_key)
    adjusted = growth_party_carry_target_plan_for_combat_level(
        (min_target, ideal_target, max_delta),
        carry_level,
    )
    if int(party_size or 0) == 2 and int(current_level or 0) <= 6:
        adjusted_min, adjusted_ideal, adjusted_delta = adjusted
        carry_ceiling = min(50, max(1, int(carry_level or 1)) + 1)
        adjusted_delta = max(int(adjusted_delta), max(0, carry_ceiling - int(adjusted_ideal)))
        return adjusted_min, adjusted_ideal, adjusted_delta
    return adjusted


def growth_party_carry_reward_floor(
    args: argparse.Namespace,
    current_level: int,
    party_size: int,
    realm_key: str = "",
) -> int:
    if not growth_party_uses_carry_tuning(args, current_level, party_size):
        return 0
    carry_level = growth_party_carry_level_for_realm(args, current_level, party_size, realm_key)
    return max(1, minimum_non_grey_target_level(carry_level))


def growth_party_carry_verified_route_reward_floor(
    args: argparse.Namespace,
    current_level: int,
    party_size: int,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> int:
    floor = growth_party_carry_reward_floor(args, current_level, party_size, realm_key)
    if floor <= 0 or route is None:
        return floor
    route_mob_level = int(getattr(route, "mob_level", 0) or 0)
    if route_mob_level <= 0:
        return floor
    if (
        int(current_level or 0) < 10
        or int(party_size or 0) <= 1
        or str(getattr(route, "source", "") or "") != "hunting-index"
        or str(getattr(args, "growth_fast_travel", "") or "").strip().lower() != "route-home"
        or not bool(getattr(args, "growth_route_level_is_carry_target", False))
        or not growth_route_preflight_enabled(args)
        or not growth_route_preflight_strict_required(
            args,
            route,
            current_level=current_level,
            party_size=party_size,
        )
    ):
        return floor
    player_floor = minimum_growth_effective_target_level(current_level, party_size, realm_key)
    if player_floor <= 0 or route_mob_level < player_floor:
        return floor
    if int(getattr(args, "growth_route_player_level", 0) or 0) > 0:
        return max(int(floor), int(player_floor))
    return min(int(floor), int(player_floor))


def growth_party_behavior_carry_target_plan(
    args: argparse.Namespace,
    current_level: int,
    party_size: int,
    realm_key: str,
    combat_level: int = 0,
) -> tuple[int, int, int]:
    level = max(1, int(current_level or 1))
    party = int(party_size or 0)
    plan = growth_party_carry_target_plan_for_realm(level, party, realm_key)
    if bool(getattr(args, "growth_equip_party_carry_gear", False)):
        plan = growth_party_carry_target_plan_for_combat_level(
            plan,
            max(1, int(combat_level or level)),
        )
        plan = enforce_party_carry_non_grey_target_plan(
            args,
            level,
            party,
            int(plan[0]),
            int(plan[1]),
            int(plan[2]),
            realm_key,
        )
    else:
        plan = growth_ungeared_party_carry_target_plan(level, party, realm_key, plan)
    return adjust_growth_target_plan_for_failed_level_scan(
        args,
        level,
        party,
        int(plan[0]),
        int(plan[1]),
        int(plan[2]),
    )


def growth_party_behavior_route_level_for_start(
    args: argparse.Namespace,
    current_level: int,
    party_size: int,
    realm_key: str,
    combat_level: int = 0,
) -> int:
    level = max(1, int(current_level or 1))
    if not growth_party_uses_carry_tuning(args, level, party_size):
        return level
    plan = growth_party_behavior_carry_target_plan(
        args,
        level,
        party_size,
        realm_key,
        combat_level or level,
    )
    return max(1, int(plan[1]))


def growth_party_carry_count_from_args(args: argparse.Namespace, party_size: int) -> int:
    raw_override = getattr(args, "growth_party_carry_count", -1)
    override = int(raw_override if raw_override is not None else -1)
    if override < 0:
        return growth_party_carry_count(party_size)
    return min(max(0, override), max(0, int(party_size or 0) - 1))


def growth_party_uses_carry_tuning(args: argparse.Namespace, level: int, party_size: int) -> bool:
    return uses_growth_party_carry_tuning(level, party_size) and growth_party_carry_count_from_args(args, party_size) > 0


def growth_party_carry_route_policy_level(
    args: argparse.Namespace,
    current_level: int,
    route_level: int,
    party_size: int,
    *,
    carry_tuning: bool = False,
) -> int:
    if (
        carry_tuning
        and bool(getattr(args, "growth_route_level_is_carry_target", False))
        and int(party_size or 0) > 1
    ):
        return max(1, int(route_level or current_level or 1))
    return max(1, int(current_level or 1))


def growth_party_account_roles(
    account_names: list[str],
    party_size: int,
    carry_count_override: int | None = None,
) -> dict[str, str]:
    if carry_count_override is None:
        carry_count = growth_party_carry_count(party_size)
    else:
        carry_count = max(0, int(carry_count_override or 0))
    carry_count = min(carry_count, len(account_names), max(0, int(party_size or 0) - 1))
    carry_accounts = set(account_names[:carry_count])
    return {
        account: "carry" if account in carry_accounts else "tracked"
        for account in account_names
    }


def mark_growth_party_account_roles(rows: list[dict[str, str]], roles: dict[str, str]) -> None:
    for row in rows:
        account = row.get("username", "")
        row["growth_role"] = roles.get(account, "tracked")


def tracked_growth_accounts(account_names: list[str], roles: dict[str, str]) -> list[str]:
    tracked = [account for account in account_names if roles.get(account, "tracked") != "carry"]
    return tracked or list(account_names)


def carry_growth_accounts(account_names: list[str], roles: dict[str, str]) -> list[str]:
    return [account for account in account_names if roles.get(account) == "carry"]


def growth_item_plan_account_names(
    account_names: list[str],
    tracked_account_names: list[str],
    party_size: int,
) -> list[str]:
    if int(party_size or 0) > 1:
        return list(account_names)
    return list(tracked_account_names)


def observed_growth_level(
    before: dict[str, CharacterSnapshot],
    account_names: list[str],
    roles: dict[str, str],
    checkpoint_level: int | None,
    party_size: int = 0,
) -> int:
    if checkpoint_level is not None:
        return max(1, int(checkpoint_level or 1))
    tracked_names = tracked_growth_accounts(account_names, roles)
    tracked_levels = [
        before[account].level
        for account in tracked_names
        if account in before and before[account].level > 0
    ]
    if tracked_levels:
        if int(party_size or 0) >= 8:
            return max(tracked_levels)
        return min(tracked_levels)
    all_levels = [snapshot.level for snapshot in before.values() if snapshot.level > 0]
    return min(all_levels, default=1)


def growth_low_health_rest_percent(level: int, party_size: int, realm_key: str = "") -> int:
    if uses_hib_low_duo_recovery_tuning(level, party_size, realm_key):
        return 25
    if uses_low_solo_flee_tuning(level, party_size, realm_key) or uses_low_small_party_commit_tuning(
        level, party_size, realm_key
    ):
        return 30
    if int(party_size or 0) <= 1 and 5 <= int(level or 0) <= 9:
        return 60
    if uses_growth_party_carry_tuning(level, party_size):
        return 25
    return 70


def growth_low_health_rest_resume_percent(level: int, party_size: int, realm_key: str = "") -> int:
    if uses_hib_low_duo_recovery_tuning(level, party_size, realm_key):
        return 65
    if uses_low_solo_flee_tuning(level, party_size, realm_key) or uses_low_small_party_commit_tuning(
        level, party_size, realm_key
    ):
        return 75
    if uses_growth_party_carry_tuning(level, party_size):
        return 65
    if int(party_size or 0) <= 1 and 5 <= int(level or 0) <= 9:
        return 70
    return 88


def growth_required_target_recover_before_hunt_endurance_percent(level: int, party_size: int, realm_key: str = "") -> int:
    del realm_key
    if int(party_size or 0) <= 1 and 5 <= int(level or 0) <= 9:
        return 40
    if int(level or 0) >= 10:
        return 40
    return 0


def growth_required_target_recover_before_home_health_percent(level: int, party_size: int, realm_key: str = "") -> int:
    if uses_hib_low_duo_recovery_tuning(level, party_size, realm_key):
        return 30
    if uses_growth_party_carry_tuning(level, party_size):
        return 30
    if int(party_size or 0) <= 1 and int(level or 0) >= 10:
        return 95
    if int(party_size or 0) <= 1 and 5 <= int(level or 0) <= 10:
        return 60
    return 88


def growth_flee_health_percent(level: int, party_size: int, realm_key: str = "") -> int:
    if uses_hib_low_duo_recovery_tuning(level, party_size, realm_key):
        return 15
    if uses_low_solo_flee_tuning(level, party_size, realm_key) or uses_low_small_party_commit_tuning(
        level, party_size, realm_key
    ):
        return 30
    if uses_growth_party_carry_tuning(level, party_size):
        return 15
    return 55


def growth_flee_health_percent_for_route(
    level: int,
    party_size: int,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> int:
    if is_alb_duo_level_ten_low_power_carry_route(level, party_size, realm_key, route):
        return 45
    return growth_flee_health_percent(level, party_size, realm_key)


def growth_flee_pressure_health_percent(level: int, party_size: int, realm_key: str = "") -> int:
    if uses_hib_low_duo_recovery_tuning(level, party_size, realm_key):
        return 20
    if str(realm_key or "").lower() == "hib" and int(party_size or 0) >= 8 and int(level or 0) <= 5:
        return 55
    if str(realm_key or "").lower() == "alb" and int(party_size or 0) >= 8 and int(level or 0) >= 7:
        return 85
    if uses_low_solo_flee_tuning(level, party_size, realm_key) or uses_low_small_party_commit_tuning(
        level, party_size, realm_key
    ):
        return 30
    if uses_growth_party_carry_tuning(level, party_size):
        return 20
    return 85


def growth_flee_pressure_health_percent_for_route(
    args: argparse.Namespace,
    level: int,
    party_size: int,
    realm_key: str,
    route: RoutePoint | None = None,
) -> int:
    if is_mid_solo_level_seven_lower_xp_route(args, level, party_size, realm_key, route):
        return 60
    if is_alb_duo_level_ten_low_power_carry_route(level, party_size, realm_key, route):
        return 55
    return growth_flee_pressure_health_percent(level, party_size, realm_key)


def growth_flee_critical_health_percent(level: int, party_size: int, realm_key: str = "") -> int:
    if str(realm_key or "").lower() == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return 35
    if uses_hib_low_duo_recovery_tuning(level, party_size, realm_key):
        return 5
    if uses_low_solo_flee_tuning(level, party_size, realm_key) or uses_low_small_party_commit_tuning(
        level, party_size, realm_key
    ):
        return 20
    if uses_growth_party_carry_tuning(level, party_size):
        return 5
    return 45


def growth_flee_critical_health_percent_for_route(
    level: int,
    party_size: int,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> int:
    if is_alb_duo_level_ten_low_power_carry_route(level, party_size, realm_key, route):
        return 25
    return growth_flee_critical_health_percent(level, party_size, realm_key)


def growth_flee_step(level: int, party_size: int, realm_key: str = "") -> int:
    if str(realm_key or "").lower() == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 10:
        return 1600
    return 900


def growth_flee_movement_speed(level: int, party_size: int, realm_key: str = "") -> int:
    if str(realm_key or "").lower() == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 10:
        return 360
    return 280


def growth_flee_melee_counterattack_health_floor(level: int, party_size: int, realm_key: str = "") -> int:
    if uses_hib_low_duo_recovery_tuning(level, party_size, realm_key):
        return 5
    if uses_low_solo_flee_tuning(level, party_size, realm_key) or uses_low_small_party_commit_tuning(
        level, party_size, realm_key
    ):
        return 20
    if uses_growth_party_carry_tuning(level, party_size):
        return 5
    return 55


def growth_flee_melee_counterattack_health_floor_for_route(
    level: int,
    party_size: int,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> int:
    if is_alb_duo_level_ten_low_power_carry_route(level, party_size, realm_key, route):
        return 25
    return growth_flee_melee_counterattack_health_floor(level, party_size, realm_key)


def target_max_level(level: int, ideal_target: int, max_delta: int) -> int:
    if max_delta <= 0:
        return max(0, int(ideal_target))
    if int(ideal_target) < int(level):
        return min(50, max(1, int(ideal_target) + int(max_delta)))
    return min(50, max(1, int(level)) + int(max_delta))


def growth_command_max_target_level(level: int, ideal_target: int, max_delta: int, party_size: int) -> int:
    if (
        uses_growth_party_carry_tuning(level, party_size)
        and int(ideal_target or 0) > int(level or 0)
    ):
        return min(50, max(1, int(ideal_target)) + max(0, int(max_delta or 0)))
    return target_max_level(level, ideal_target, max_delta)


def adjust_growth_target_plan_for_required_route(
    route: RoutePoint,
    *,
    current_level: int,
    party_size: int,
    realm_key: str,
    min_target: int,
    ideal_target: int,
    max_delta: int,
) -> tuple[int, int, int]:
    if route.source != "hunting-index":
        return min_target, ideal_target, max_delta
    route_mob_level = max(0, int(getattr(route, "mob_level", 0) or 0))
    required_target_name = strict_route_target_name(route, current_level, party_size, realm_key)
    if (
        route_mob_level == 0
        and str(getattr(route, "prefer", "") or "").strip()
        and int(current_level or 0) <= 1
        and int(party_size or 0) <= 2
    ):
        return 0, max(int(ideal_target or 0), route_mob_level), max_delta
    if route_mob_level <= 0 or route_mob_level >= int(min_target or 0):
        return min_target, ideal_target, max_delta
    if not required_target_name:
        return min_target, ideal_target, max_delta
    return route_mob_level, max(int(ideal_target or 0), route_mob_level), max_delta


def adjust_low_solo_hunting_target_plan(
    args: argparse.Namespace,
    route: RoutePoint,
    *,
    current_level: int,
    party_size: int,
    realm_key: str,
    min_target: int,
    ideal_target: int,
    max_delta: int,
) -> tuple[int, int, int]:
    allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
        getattr(args, "growth_allow_lower_xp_gear_farm", True)
    )
    player_level = max(1, int(current_level or 1))
    if (
        allow_lower_xp_target_plan
        or route.source != "hunting-index"
        or int(party_size or 0) > 1
        or not (5 <= player_level <= 10)
    ):
        return min_target, ideal_target, max_delta
    minimum_effective = minimum_growth_effective_target_level(player_level, party_size, realm_key)
    effective_floor = minimum_effective if minimum_effective > 0 else int(min_target or 0)
    route_mob_level = max(0, int(getattr(route, "mob_level", 0) or 0))
    if (
        str(realm_key or "").lower() == "mid"
        and player_level == 10
        and route_mob_level >= 7
        and int(ideal_target or 0) == 7
        and "small hill cat" in str(getattr(route, "prefer", "") or "").lower()
    ):
        return min_target, ideal_target, max_delta
    if route_mob_level > 0 and route_mob_level < effective_floor:
        return min_target, ideal_target, max_delta
    target = max(1, min(50, max(int(min_target or 0), int(effective_floor or 0))))
    return target, target, 0


def inferred_party_carry_fallback_mob_level(route: RoutePoint, *, realm_key: str, party_size: int) -> int:
    if not uses_growth_party_carry_tuning(1, party_size):
        return 0
    if getattr(route, "source", "") == "hunting-index":
        return max(0, int(getattr(route, "mob_level", 0) or 0))

    prefer = str(getattr(route, "prefer", "") or "").lower()
    if not prefer:
        return 0
    if str(realm_key or "").lower() == "mid" and "small hill cat" in prefer:
        return 8
    return max(0, int(getattr(route, "level", 0) or 0))


def adjust_party_carry_target_plan_for_route_fallback(
    route: RoutePoint,
    *,
    current_level: int,
    party_size: int,
    realm_key: str,
    min_target: int,
    ideal_target: int,
    max_delta: int,
) -> tuple[int, int, int]:
    if not uses_growth_party_carry_tuning(1, party_size):
        return min_target, ideal_target, max_delta
    route_mob_level = inferred_party_carry_fallback_mob_level(route, realm_key=realm_key, party_size=party_size)
    if route_mob_level <= 0 or route_mob_level >= int(min_target or 0):
        return min_target, ideal_target, max_delta
    carry_target_context = int(party_size or 0) >= 8 and int(current_level or 0) >= 10
    if route_mob_level <= max(1, int(current_level or 1)) and not carry_target_context:
        return min_target, ideal_target, max_delta
    xp_floor = max(1, minimum_growth_effective_target_level(current_level, party_size, realm_key))
    if route_mob_level < xp_floor:
        return min_target, ideal_target, max_delta
    party = int(party_size or 0)
    below_span = 4 if party >= 8 else 3 if party >= 4 else 2
    fallback_min = max(xp_floor, route_mob_level - below_span)
    fallback_delta = max(int(max_delta or 0), 2 if party >= 4 else 1)
    return fallback_min, route_mob_level, fallback_delta


def enforce_no_lower_xp_target_plan(
    args: argparse.Namespace,
    current_level: int,
    party_size: int,
    min_target: int,
    ideal_target: int,
    max_delta: int,
    realm_key: str = "",
) -> tuple[int, int, int]:
    allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
        getattr(args, "growth_allow_lower_xp_gear_farm", True)
    )
    if allow_lower_xp_target_plan:
        return min_target, ideal_target, max_delta

    player_level = max(1, int(current_level or 1))
    if player_level < 5:
        return min_target, ideal_target, max_delta

    if uses_growth_party_carry_tuning(player_level, party_size):
        return min_target, ideal_target, max_delta

    if int(party_size or 0) > 1:
        ideal_target = max(int(ideal_target), min(50, player_level + 2))
        max_delta = max(3, int(max_delta))
        return min_target, ideal_target, max_delta

    minimum_effective = minimum_growth_effective_target_level(player_level, party_size, realm_key)
    effective_floor = minimum_effective if minimum_effective > 0 else player_level
    min_target = max(int(min_target), effective_floor)
    ideal_target = max(int(ideal_target), effective_floor)
    max_delta = max(0, int(max_delta))
    if int(party_size or 0) >= 2 and 5 <= player_level <= 10:
        ideal_target = max(ideal_target, min(50, player_level + 2))
        max_delta = max(max_delta, 3)
    return min_target, ideal_target, max_delta


def no_lower_xp_route_target_level(
    args: argparse.Namespace,
    realm_key: str,
    current_level: int,
    party_size: int,
) -> int:
    player_level = max(1, int(current_level or 1))
    allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
        getattr(args, "growth_allow_lower_xp_gear_farm", True)
    )
    if allow_lower_xp_target_plan or int(party_size or 0) > 1 or player_level < 5:
        return player_level
    if uses_growth_party_carry_tuning(player_level, party_size):
        return player_level
    min_target, ideal_target, max_delta = target_levels(player_level, party_size, realm_key)
    min_target, ideal_target, _ = enforce_no_lower_xp_target_plan(
        args,
        player_level,
        party_size,
        min_target,
        ideal_target,
        max_delta,
        realm_key,
    )
    return max(1, min(50, max(int(min_target), int(ideal_target))))


_MIN_NON_GREY_TARGET_LEVEL_BY_PLAYER_LEVEL = (
    0,  # 0
    0,  # 1
    0,  # 2
    1,  # 3
    2,  # 4
    3,  # 5
    4,  # 6
    5,  # 7
    6,  # 8
    7,  # 9
    7,  # 10
    7,  # 11
    7,  # 12
    8,  # 13
    9,  # 14
    10,  # 15
    11,  # 16
    12,  # 17
    13,  # 18
    14,  # 19
    14,  # 20
    14,  # 21
    14,  # 22
    15,  # 23
    16,  # 24
    17,  # 25
    18,  # 26
    19,  # 27
    20,  # 28
    21,  # 29
    22,  # 30
    23,  # 31
    24,  # 32
    25,  # 33
    26,  # 34
    26,  # 35
    26,  # 36
    26,  # 37
    26,  # 38
    26,  # 39
    26,  # 40
    27,  # 41
    28,  # 42
    29,  # 43
    30,  # 44
    31,  # 45
    32,  # 46
    33,  # 47
    34,  # 48
    35,  # 49
    36,  # 50
)


def minimum_non_grey_target_level(player_level: int) -> int:
    level = max(0, int(player_level or 0))
    if level < len(_MIN_NON_GREY_TARGET_LEVEL_BY_PLAYER_LEVEL):
        return _MIN_NON_GREY_TARGET_LEVEL_BY_PLAYER_LEVEL[level]
    return max(0, level - 14)


def enforce_reward_non_grey_target_plan(
    player_level: int,
    min_target: int,
    ideal_target: int,
    max_delta: int,
) -> tuple[int, int, int]:
    floor = minimum_non_grey_target_level(player_level)
    if floor <= 0:
        return int(min_target), int(ideal_target), int(max_delta)
    min_target = max(int(min_target), floor)
    ideal_target = max(int(ideal_target), min_target)
    return min_target, ideal_target, int(max_delta)


def minimum_growth_effective_target_level(level: int, party_size: int, realm_key: str = "") -> int:
    player_level = max(1, int(level or 1))
    non_grey_floor = minimum_non_grey_target_level(player_level)

    def floor(value: int) -> int:
        return max(int(value or 0), non_grey_floor)

    if realm_key == "alb" and int(party_size or 0) <= 1 and player_level == 8:
        return floor(6)
    if realm_key == "alb" and int(party_size or 0) <= 1 and player_level == 7:
        return floor(5)
    if realm_key == "alb" and int(party_size or 0) <= 1 and player_level == 10:
        return floor(7)
    if realm_key == "mid" and int(party_size or 0) <= 1 and player_level == 9:
        return floor(7)
    if realm_key == "mid" and int(party_size or 0) <= 1 and player_level == 10:
        return floor(7)
    if realm_key == "mid" and int(party_size or 0) <= 1 and player_level == 7:
        return floor(6)
    if realm_key == "hib" and int(party_size or 0) <= 1 and player_level == 8:
        return floor(6)
    if realm_key == "hib" and int(party_size or 0) <= 1 and player_level == 9:
        return floor(6)
    if realm_key == "hib" and int(party_size or 0) <= 1 and player_level == 10:
        return floor(7)
    if realm_key == "hib" and int(party_size or 0) <= 1 and player_level in {7, 8}:
        return floor(5)
    if int(party_size or 0) <= 2 and 5 <= player_level <= 10:
        if int(party_size or 0) == 2:
            if realm_key == "alb" and player_level == 6:
                return floor(5)
            if realm_key == "alb" and player_level == 7:
                return floor(5)
            if realm_key == "mid" and player_level == 7:
                return floor(5)
            if realm_key == "hib" and player_level == 8:
                return floor(7)
            if player_level <= 5:
                return floor(4)
            if player_level <= 9:
                return floor(max(1, player_level - 2))
            return floor(7)
        return floor(max(1, player_level - 2))
    if int(party_size or 0) <= 4 and 5 <= player_level <= 10:
        if realm_key == "mid" and player_level == 9:
            return floor(8)
        if realm_key == "hib" and player_level == 9:
            return floor(8)
        if realm_key == "hib" and player_level == 8:
            return floor(7)
        if realm_key == "alb" and player_level == 6:
            return floor(5)
        if realm_key == "mid" and player_level == 7:
            return floor(7)
        if player_level <= 5:
            return floor(4)
        if player_level <= 7:
            return floor(5)
        if player_level <= 9:
            return floor(max(1, player_level - 2))
        return floor(8)
    if int(party_size or 0) >= 8 and 5 <= player_level <= 10:
        if realm_key == "alb" and player_level == 5:
            return floor(4)
        return floor(player_level)
    if player_level <= 10:
        return non_grey_floor
    return 0


def validate_growth_target_plan(
    *,
    realm_key: str,
    current_level: int,
    party_size: int,
    route_level: int,
    min_target: int,
    ideal_target: int,
    max_delta: int,
) -> None:
    min_effective = minimum_growth_effective_target_level(current_level, party_size, realm_key)
    if min_effective <= 0:
        return
    max_target = target_max_level(current_level, ideal_target, max_delta)
    route_level_too_low = int(route_level or 0) < min_effective and int(party_size or 0) < 8
    if max_target < min_effective or route_level_too_low:
        raise ValueError(
            "invalid growth target plan: "
            f"realm={realm_key} level={current_level} party={party_size} "
            f"route_level={route_level} target={min_target}-{max_target} "
            f"minimum_effective={min_effective}"
        )


def early_growth_party_slot_rotations(level: int, party_size: int, *, carry_tuning: bool | None = None) -> str:
    if level50_party_boss_rules_enabled(level, party_size) and party_size == 4:
        return "melee-basic,healer-support,melee-basic,melee-burst"
    if carry_tuning is None:
        carry_tuning = uses_growth_party_carry_tuning(level, party_size)
    if carry_tuning:
        if int(party_size or 0) >= 8:
            base_rotations = [
                "melee-burst",
                "healer-support",
                "melee-basic",
                "melee-basic",
                "melee-basic",
                "healer-support",
                "caster-basic",
                "melee-basic",
            ]
            carry_count = growth_party_carry_count(party_size)
            rotations = [
                base_rotations[slot_index] if slot_index < carry_count and slot_index < len(base_rotations) else "none"
                for slot_index in range(max(0, int(party_size or 0)))
            ]
            return ",".join(rotations)
        carry_count = growth_party_carry_count(party_size)
        rotations: list[str] = []
        for slot_index in range(max(0, int(party_size or 0))):
            if slot_index == 0:
                rotations.append("melee-burst")
            elif slot_index < carry_count:
                rotations.append("melee-basic")
            elif int(party_size or 0) == 2:
                rotations.append("healer-support")
            else:
                rotations.append("none")
        return ",".join(rotations)
    if int(party_size or 0) >= 8:
        return "melee-burst,healer-support,melee-basic,melee-basic,melee-basic,healer-support,caster-basic,melee-basic"
    if party_size >= 8 and 5 <= level <= 10:
        return "melee-basic,healer-support,melee-basic,melee-burst,melee-basic,healer-support,caster-basic,healer-support"
    if party_size <= 1 or level > 4:
        return ""
    if party_size == 2:
        return "melee-basic,healer-support"
    if party_size == 3:
        return "melee-basic,healer-support,melee-basic"
    return "melee-basic,healer-support,melee-basic,melee-burst"


def party_min_ready(level: int, party_size: int, *, carry_tuning: bool | None = None) -> int:
    if party_size <= 1:
        return party_size
    if level50_party_boss_rules_enabled(level, party_size):
        return party_size
    if carry_tuning is None:
        carry_tuning = uses_growth_party_carry_tuning(level, party_size)
    if int(party_size or 0) >= 8:
        return party_size
    if carry_tuning:
        return min(party_size, growth_party_carry_count(party_size) + 1)
    if level <= 4:
        return min(party_size, 4)
    return party_size


def growth_party_form_up_timeout(level: int, party_size: int, *, level50_boss_party: bool = False, carry_tuning: bool = False) -> str:
    if party_size <= 1:
        return "0"
    if level50_boss_party:
        return "45"
    if carry_tuning:
        return "12"
    if level <= 4:
        return "25"
    return "35"


def growth_party_assist_interval(
    level: int,
    party_size: int,
    *,
    level50_boss_party: bool = False,
    carry_tuning: bool | None = None,
) -> str:
    if level50_boss_party:
        return "0.6"
    if carry_tuning is None:
        carry_tuning = uses_growth_party_carry_tuning(level, party_size)
    if carry_tuning:
        return "0.6"
    if party_size > 1 and level <= 4:
        return "0.4"
    return "3"


def growth_party_assist_attack_delay(level: int, party_size: int) -> str:
    if uses_growth_party_carry_tuning(level, party_size):
        return "0.0"
    return "0.0"


def growth_attack_target_in_view_prime_delay(level: int, party_size: int, *, carry_tuning: bool | None = None) -> str:
    if carry_tuning is None:
        carry_tuning = uses_growth_party_carry_tuning(level, party_size)
    if carry_tuning:
        return "0.0"
    if party_size > 1 and level <= 4:
        return "0.0"
    return "1.1"


def growth_party_ready_max_leader_distance(level: int, party_size: int, *, carry_tuning: bool | None = None) -> str:
    if carry_tuning is None:
        carry_tuning = uses_growth_party_carry_tuning(level, party_size)
    if carry_tuning:
        return "1800"
    return "1500"


def growth_party_follow_distance(level: int, party_size: int, *, carry_tuning: bool | None = None) -> str:
    if carry_tuning is None:
        carry_tuning = uses_growth_party_carry_tuning(level, party_size)
    if carry_tuning:
        return "600"
    return "500"


def growth_passive_xp_leech_follow_distance(level: int, party_size: int) -> int:
    if not uses_growth_party_carry_tuning(level, party_size):
        return 0
    if int(party_size or 0) >= 8:
        return 1400
    if int(party_size or 0) >= 4:
        return 1200
    return 900


def growth_hunter_min_time_left_for_new_target(level: int, party_size: int) -> str:
    if int(party_size or 0) <= 1 and 5 <= int(level or 0) <= 6:
        return "75"
    return "55"


def growth_party_pre_pull_home_stop_distance(level: int, party_size: int, *, carry_tuning: bool | None = None) -> str:
    if carry_tuning is None:
        carry_tuning = uses_growth_party_carry_tuning(level, party_size)
    if carry_tuning:
        return "1600"
    return "1800"


def level50_party_boss_rules_enabled(level: int, party_size: int) -> bool:
    return level >= 50 and party_size >= 4


def watcher_count_for_party(args: argparse.Namespace, party_size: int) -> int:
    if not getattr(args, "watch_movement", False):
        return 0
    return 1 if party_size > 0 else 0


def watcher_observer_follow_distance(args: argparse.Namespace) -> float:
    return max(float(getattr(args, "watcher_follow_distance", 0.0) or 0.0), 8000.0)


def watcher_observer_max_distance(args: argparse.Namespace) -> float:
    return max(float(getattr(args, "watcher_follow_max_distance", 0.0) or 0.0), 60000.0)


def watcher_observer_movement_speed(args: argparse.Namespace) -> float:
    return max(float(getattr(args, "watcher_movement_speed", 0.0) or 0.0), 240.0)


def growth_stage_for_level(level: int) -> str:
    level = max(1, int(level or 1))
    if level <= 4:
        return "stabilize"
    if level == 5:
        return "train"
    if level <= 10:
        return "gear"
    return "long"


def apply_growth_stage_defaults(args: argparse.Namespace) -> None:
    defaults = GROWTH_STAGE_DEFAULTS.get(getattr(args, "growth_stage", "custom"))
    if defaults is None:
        return

    for name, value in defaults.items():
        setattr(args, name, value)


def apply_l10_checkpoint_route_home_defaults(args: argparse.Namespace, explicit_options: set[str]) -> None:
    if int(getattr(args, "reset_level", 1) or 1) < 10:
        return
    if parse_checkpoint_levels(str(getattr(args, "checkpoint_levels", "") or "")):
        return
    if getattr(args, "resume", False):
        return
    if int(getattr(args, "first_segment", 0) or 0) > 0:
        return
    location = str(getattr(args, "checkpoint_start_location", "realm-start") or "realm-start").strip().lower()
    if location == "realm-start":
        if "checkpoint_start_location" not in explicit_options:
            args.checkpoint_start_location = "route-home"
            location = "route-home"
    if (
        location == "route-home"
        and "growth_fast_travel" not in explicit_options
        and str(getattr(args, "growth_fast_travel", "off") or "off").strip().lower() == "off"
    ):
        args.growth_fast_travel = "route-home"


def apply_growth_speed_profile(args: argparse.Namespace, explicit_options: set[str]) -> None:
    if getattr(args, "growth_speed_profile", "debug") != "fast-balance":
        return

    if "segment_seconds" not in explicit_options:
        args.segment_seconds = min(int(args.segment_seconds), 180)
    if "startup_delay" not in explicit_options:
        args.startup_delay = min(float(args.startup_delay), 4.0)
    if "post_segment_snapshot_delay" not in explicit_options:
        args.post_segment_snapshot_delay = min(float(args.post_segment_snapshot_delay), 0.5)
    if "post_segment_snapshot_timeout" not in explicit_options:
        args.post_segment_snapshot_timeout = min(float(args.post_segment_snapshot_timeout), 15.0)
    if "post_segment_snapshot_poll_interval" not in explicit_options:
        args.post_segment_snapshot_poll_interval = min(float(args.post_segment_snapshot_poll_interval), 0.5)
    if "inter_segment_delay" not in explicit_options:
        args.inter_segment_delay = min(float(args.inter_segment_delay), 5.0)
    if "safe_exit_max_seconds" not in explicit_options:
        if getattr(args, "growth_fast_travel", "off") == "route-home":
            args.safe_exit_max_seconds = max(float(args.safe_exit_max_seconds), GROWTH_SAFE_EXIT_MAX_SECONDS)
        else:
            args.safe_exit_max_seconds = min(float(args.safe_exit_max_seconds), 25.0)
    if "safe_exit_recent_damage_grace" not in explicit_options:
        if getattr(args, "growth_fast_travel", "off") == "route-home":
            args.safe_exit_recent_damage_grace = max(
                float(args.safe_exit_recent_damage_grace),
                GROWTH_SAFE_EXIT_RECENT_DAMAGE_GRACE,
            )
        else:
            args.safe_exit_recent_damage_grace = min(float(args.safe_exit_recent_damage_grace), 5.0)

    for name in ("watch_movement", "live_supervisor", "fail_on_regression", "require_segment_kill", "require_segment_xp"):
        if name not in explicit_options:
            setattr(args, name, False)


def parse_checkpoint_levels(value: str) -> list[int]:
    if not value.strip():
        return []
    levels: list[int] = []
    for token in value.split(","):
        text = token.strip()
        if not text:
            continue
        try:
            level = int(text)
        except ValueError as exc:
            raise SystemExit(f"invalid --checkpoint-levels value: {text}") from exc
        if level < 1:
            raise SystemExit("--checkpoint-levels must be positive")
        if level not in levels:
            levels.append(level)
    return levels


def should_train_at_level(level: int) -> bool:
    return 2 <= int(level) < 50


def parse_specs(specs: str | None) -> dict[str, int]:
    parsed: dict[str, int] = {}
    for part in (specs or "").split(";"):
        if "|" not in part:
            continue
        name, value = part.split("|", 1)
        name = name.strip()
        if not name:
            continue
        parsed[name] = to_int(value)
    return parsed


CASTER_SPEC_NAME_TOKENS = (
    "magic",
    "runecarving",
    "darkness",
    "suppression",
    "summoning",
    "body",
    "mind",
    "matter",
    "spirit",
    "fire",
    "earth",
    "cold",
    "wind",
    "void",
    "mana",
    "light",
    "enchant",
    "mental",
    "animism",
    "arboreal",
    "creeping",
    "verdant",
    "painworking",
    "death servant",
    "death sight",
)
HEALER_SPEC_NAME_TOKENS = (
    "rejuvenation",
    "enhancement",
    "regrowth",
    "nurture",
    "mending",
    "augmentation",
    "pacification",
    "healing",
)
CASTER_STATIONARY_CAST_HOLD_SECONDS = 3.4


def first_trainable_spec_name(specs: str | None) -> str:
    for name, value in parse_specs(specs).items():
        if value > 1:
            return name.strip().lower()
    return ""


def solo_action_rotation_for_accounts(accounts_csv: Path, party_size: int) -> str:
    if party_size != 1 or not accounts_csv.exists():
        return "melee-basic" if party_size == 1 else "auto"
    rows = read_accounts(accounts_csv)
    if not rows:
        return "melee-basic"
    spec_name = first_trainable_spec_name(rows[0].get("specs") or rows[0].get("SerializedSpecs"))
    if spec_name and any(token in spec_name for token in HEALER_SPEC_NAME_TOKENS):
        return "healer-support"
    if spec_name and any(token in spec_name for token in CASTER_SPEC_NAME_TOKENS):
        return "caster-basic"
    return "melee-basic"


def spec_gain_summary(before_specs: str | None, after_specs: str | None) -> str:
    before = parse_specs(before_specs)
    after = parse_specs(after_specs)
    changes: list[str] = []
    for name in sorted(after):
        delta = after[name] - before.get(name, 0)
        if delta > 0:
            changes.append(f"{name}+{delta}")
    return ";".join(changes)


def baseline_specs(specs: str | None) -> str:
    parsed = parse_specs(specs)
    return ";".join(f"{name}|1" for name in parsed)


def capped_specs_for_level(specs: str | None, level: int) -> str:
    cap = max(1, int(level or 1))
    parsed = parse_specs(specs)
    return ";".join(f"{name}|{min(max(1, value), cap)}" for name, value in parsed.items())


def low_level_tank_growth_specs(
    specs: str | None,
    *,
    realm_key: str,
    class_id: int,
    level: int,
    party_size: int,
    growth_stage: str = "",
) -> str:
    if (
        str(realm_key or "").lower() != "alb"
        or int(class_id or 0) != 1
        or int(level or 0) != 7
        or int(party_size or 0) != 1
        or str(growth_stage or "").strip().lower() != "gear"
    ):
        return ""
    parsed = parse_specs(specs)
    if not parsed:
        return ""

    targets = {
        "Slash": 5,
        "Chants": 4,
        "Shields": 5,
        "Parry": 1,
    }
    parts: list[str] = []
    for name, target in parsed.items():
        parts.append(f"{name}|{max(1, min(int(target), int(parsed.get(name, target) or target)))}")
    by_name: dict[str, str] = {}
    for part in parts:
        name, _sep, value = part.partition("|")
        by_name[name] = value
    for name, target in targets.items():
        if name in parsed:
            by_name[name] = str(max(1, min(target, int(parsed.get(name, target) or target))))
    return ";".join(f"{name}|{by_name.get(name, '1')}" for name in parsed)


def low_level_tank_growth_ability_updates(
    *,
    realm_key: str,
    class_id: int,
    level: int,
    party_size: int,
    growth_stage: str = "",
) -> dict[str, int]:
    return {}


def apply_growth_low_level_spec_plan(
    args: argparse.Namespace,
    rows: list[dict[str, str]],
    snapshots: dict[str, CharacterSnapshot],
    *,
    realm: RealmProfile,
    current_level: int,
    party_size: int,
) -> int:
    updates: list[str] = []
    changed = 0
    growth_stage = str(getattr(args, "growth_stage", "") or "")
    for row in rows:
        account = row.get("username", "")
        if not account:
            continue
        class_id = target_growth_class_id(row)
        planned_specs = low_level_tank_growth_specs(
            row.get("specs", ""),
            realm_key=realm.key,
            class_id=class_id,
            level=current_level,
            party_size=party_size,
            growth_stage=growth_stage,
        )
        if not planned_specs:
            continue
        row["specs"] = planned_specs
        changed += 1
        if getattr(args, "dry_run", False):
            continue
        snapshot = snapshots.get(account)
        serialized_abilities = snapshot.serialized_abilities if snapshot is not None else ""
        for ability_name, minimum in low_level_tank_growth_ability_updates(
            realm_key=realm.key,
            class_id=class_id,
            level=current_level,
            party_size=party_size,
            growth_stage=growth_stage,
        ).items():
            serialized_abilities = serialized_abilities_with_minimum(
                serialized_abilities,
                ability_name,
                minimum,
            )
        updates.append(
            "UPDATE DOLCharacters "
            f"SET SerializedSpecs = {sql_quote(planned_specs)}, "
            f"SerializedAbilities = {sql_quote(serialized_abilities)} "
            f"WHERE AccountName = {sql_quote(account)};"
        )
    if updates:
        run_mysql(args, "\n".join(updates))
    return changed


def train_verified(before: CharacterSnapshot | None, after: CharacterSnapshot | None, current_level: int) -> bool:
    if not should_train_at_level(current_level) or before is None or after is None:
        return False
    if after.class_id != before.class_id:
        return True
    return bool(spec_gain_summary(before.specs, after.specs))


def target_growth_class_id(row: dict[str, str]) -> int:
    return to_int(row.get("class_id"))


def promotion_right_hand_weapon_template_id(target_class_id: int, specs: str | None = None) -> str:
    return PROMOTION_RIGHT_HAND_WEAPON_BY_TARGET_CLASS.get(target_class_id, "")


def promotion_right_hand_weapon_sql(account: str, target_class_id: int, template_id: str) -> str:
    quoted_account = sql_quote(account)
    quoted_template = sql_quote(template_id)
    return f"""
        UPDATE inventory inv
        JOIN DOLCharacters c ON c.DOLCharacters_ID = inv.OwnerID
        JOIN itemtemplate gift ON gift.Id_nb = {quoted_template}
        LEFT JOIN itemtemplate current_item ON current_item.Id_nb = inv.ITemplate_Id
        SET
            inv.ITemplate_Id = gift.Id_nb,
            inv.UTemplate_Id = NULL,
            inv.Count = 1,
            inv.SellPrice = 0,
            inv.Color = gift.Color,
            inv.Emblem = gift.Emblem,
            inv.Extension = gift.Extension,
            inv.Condition = gift.MaxCondition,
            inv.Durability = gift.MaxDurability,
            inv.PoisonSpellID = gift.PoisonSpellID,
            inv.PoisonMaxCharges = gift.PoisonMaxCharges,
            inv.PoisonCharges = gift.PoisonCharges,
            inv.Charges = IF(gift.Charges > 0, gift.Charges, gift.MaxCharges),
            inv.Charges1 = IF(gift.Charges1 > 0, gift.Charges1, gift.MaxCharges1),
            inv.LastTimeRowUpdated = NOW(),
            inv.IsROG = 0,
            inv.SalvageExtension = gift.SalvageExtension
        WHERE c.AccountName = {quoted_account}
          AND c.Class = {int(target_class_id)}
          AND inv.SlotPosition = 10
          AND COALESCE(current_item.DPS_AF, 0) < gift.DPS_AF;
        UPDATE DOLCharacters
        SET ActiveWeaponSlot = 0
        WHERE AccountName = {quoted_account}
          AND Class = {int(target_class_id)};
    """


def replace_equipped_inventory_template_sql(account: str, slot: int, template_id: str, creator: str) -> str:
    quoted_account = sql_quote(account)
    quoted_template = sql_quote(template_id)
    return f"""
        UPDATE inventory inv
        JOIN DOLCharacters c ON c.DOLCharacters_ID = inv.OwnerID
        JOIN itemtemplate gift ON gift.Id_nb = {quoted_template}
        SET
            inv.ITemplate_Id = gift.Id_nb,
            inv.UTemplate_Id = NULL,
            inv.Count = GREATEST(gift.PackSize, 1),
            inv.SellPrice = 0,
            inv.Color = gift.Color,
            inv.Emblem = gift.Emblem,
            inv.Extension = gift.Extension,
            inv.Condition = gift.MaxCondition,
            inv.Durability = gift.MaxDurability,
            inv.PoisonSpellID = gift.PoisonSpellID,
            inv.PoisonMaxCharges = gift.PoisonMaxCharges,
            inv.PoisonCharges = gift.PoisonCharges,
            inv.Charges = IF(gift.Charges > 0, gift.Charges, gift.MaxCharges),
            inv.Charges1 = IF(gift.Charges1 > 0, gift.Charges1, gift.MaxCharges1),
            inv.LastTimeRowUpdated = NOW(),
            inv.Creator = {sql_quote(creator)},
            inv.IsROG = 0,
            inv.SalvageExtension = gift.SalvageExtension
        WHERE c.AccountName = {quoted_account}
          AND inv.SlotPosition = {int(slot)};
    """


def merchant_candidate_inventory_item(account: str, candidate: MerchantItemCandidate, slot: int) -> InventoryItem:
    return InventoryItem(
        account=account,
        slot=slot,
        template_id=candidate.template_id,
        name=candidate.name,
        level=candidate.level,
        dps_af=candidate.dps_af,
        spd_abs=candidate.spd_abs,
        object_type=candidate.object_type,
        item_type=candidate.item_type,
        quality=candidate.quality,
        bonus=candidate.bonus,
        allowed_classes=candidate.allowed_classes,
        count=1,
        sell_price=0,
        realm=candidate.realm,
        type_damage=candidate.type_damage,
    )


def serialized_abilities_with_minimum(serialized_abilities: str, ability_name: str, minimum_level: int) -> str:
    ability = str(ability_name or "").strip()
    if not ability:
        return serialized_abilities
    minimum = max(0, int(minimum_level or 0))
    parts = [part.strip() for part in re.split(r"[;,]", serialized_abilities or "") if part.strip()]
    updated: list[str] = []
    found = False
    for part in parts:
        name, sep, value = part.partition("|")
        if name.strip() != ability:
            updated.append(part)
            continue
        found = True
        current = to_int(value) if sep else 0
        updated.append(f"{ability}|{max(current, minimum)}")
    if not found:
        updated.append(f"{ability}|{minimum}")
    return ";".join(updated)


def growth_checkpoint_equipment_snapshot(
    snapshot: CharacterSnapshot,
    realm: RealmProfile,
    *,
    current_level: int,
) -> CharacterSnapshot:
    armor_ability = ARMOR_ABILITY_BY_REALM.get(int(realm.realm_id or snapshot.realm or 0), "")
    if not armor_ability or int(current_level or 0) not in {6, 7, 10}:
        return snapshot
    serialized_abilities = serialized_abilities_with_minimum(
        snapshot.serialized_abilities,
        armor_ability,
        4,
    )
    for spec_name, spec_level in parse_specs(snapshot.specs).items():
        if int(spec_level or 0) <= 1:
            continue
        weapon_ability = WEAPON_ABILITY_BY_SPEC_NAME.get(spec_name)
        if weapon_ability:
            serialized_abilities = serialized_abilities_with_minimum(
                serialized_abilities,
                weapon_ability,
                0,
            )
    if serialized_abilities == snapshot.serialized_abilities:
        return snapshot
    return replace(snapshot, serialized_abilities=serialized_abilities)


def is_base_class_for_target(current_class_id: int, target_class_id: int) -> bool:
    return BASE_CLASS_BY_TARGET_CLASS.get(target_class_id) == current_class_id


def promote_growth_classes_for_level(
    args: argparse.Namespace,
    account_rows: list[dict[str, str]],
    current_level: int,
    *,
    trained_specs: bool = False,
) -> int:
    if current_level < 5:
        return 0

    updates: list[str] = []
    for row in account_rows:
        account = row.get("username", "")
        target_class_id = target_growth_class_id(row)
        if not account or target_class_id <= 0:
            continue
        base_class_id = BASE_CLASS_BY_TARGET_CLASS.get(target_class_id)
        if not base_class_id:
            continue
        specs = (
            capped_specs_for_level(row.get("specs", ""), current_level)
            if trained_specs
            else baseline_specs(row.get("specs", ""))
        )
        spec_sql = f", SerializedSpecs = {sql_quote(specs)}" if specs else ""
        updates.append(
            "UPDATE DOLCharacters "
            f"SET Class = {target_class_id}{spec_sql} "
            f"WHERE AccountName = {sql_quote(account)} AND Class = {base_class_id};"
        )
        weapon_template_id = promotion_right_hand_weapon_template_id(target_class_id, row.get("specs", ""))
        if weapon_template_id:
            updates.append(promotion_right_hand_weapon_sql(account, target_class_id, weapon_template_id))

    if updates and not getattr(args, "dry_run", False):
        run_mysql(args, "\n".join(updates))
    return len(updates)


def waypoint_offsets(level: int) -> tuple[tuple[int, int], ...]:
    if level <= 4:
        return (
            (0, 0),
            (1400, 0),
            (1400, 1400),
            (0, 1400),
            (-1400, 1400),
            (-1400, 0),
            (-1400, -1400),
            (0, -1400),
            (1400, -1400),
            (2400, 0),
            (0, 2400),
            (-2400, 0),
            (0, -2400),
        )
    return ((0, 0), (360, 0), (360, 360), (0, 360))


def growth_target_home_max_distance(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    base = float(getattr(args, "target_home_max_distance", 0.0) or 0.0)
    if is_mid_duo_level_ten_short_engage_route(level, party_size, realm_key, route):
        return 2200.0
    runtime_cap = growth_runtime_low_solo_target_cap(args, level, party_size, realm_key, route)
    if runtime_cap > 0.0:
        return runtime_cap
    route_home_cap = growth_route_home_low_solo_target_cap(args, level, party_size, realm_key, route)
    if route_home_cap > 0.0:
        return route_home_cap
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and bool(getattr(args, "growth_route_level_is_carry_target", False))
        and int(party_size or 0) > 1
    ):
        if 5 <= int(level or 0) <= 9:
            return max(base, 10000.0)
        return max(base, 6500.0)
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) in {9, 10, 11}:
        return max(base, 6500.0)
    if (
        int(level or 0) == 10
        and int(party_size or 0) > 1
        and str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
    ):
        return max(base, 6500.0)
    if level == 10 and party_size > 1 and base > 0.0:
        return min(base, 1800.0)
    if level >= 45:
        return max(base, 2800.0)
    if 5 <= level <= 9:
        return max(base, 10000.0)
    if level <= 10:
        return max(base, 6200.0)
    return base


def growth_max_target_distance(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    base = float(getattr(args, "max_target_distance", 0.0) or 0.0)
    if is_mid_duo_level_ten_short_engage_route(level, party_size, realm_key, route):
        return 2200.0
    runtime_cap = growth_runtime_low_solo_target_cap(args, level, party_size, realm_key, route)
    if runtime_cap > 0.0:
        return runtime_cap
    route_home_cap = growth_route_home_low_solo_target_cap(args, level, party_size, realm_key, route)
    if route_home_cap > 0.0:
        return route_home_cap
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and int(party_size or 0) > 1
        and int(level or 0) <= 10
        and base > 0.0
    ):
        return max(base, 6500.0)
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and bool(getattr(args, "growth_route_level_is_carry_target", False))
        and getattr(route, "source", "") == "hunting-index"
        and int(party_size or 0) > 1
        and base > 0.0
    ):
        if (
            realm_key == "hib"
            and int(party_size or 0) == 2
            and 7 <= int(level or 0) <= 9
            and "water beetle" in str(getattr(route, "prefer", "") or "").lower()
        ):
            return max(base, 6500.0)
        if (
            realm_key == "mid"
            and int(party_size or 0) == 2
            and int(level or 0) <= 7
            and "carrion crawler" in str(getattr(route, "prefer", "") or "").lower()
        ):
            return max(base, 6500.0)
        if realm_key == "mid" and int(party_size or 0) >= 4 and int(level or 0) <= 4:
            return max(base, 6500.0)
        if int(party_size or 0) >= 4 and int(level or 0) <= 9:
            return max(base, 6500.0)
        if int(level or 0) <= 9:
            return max(base, 3600.0)
        return max(base, 6500.0)
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and getattr(route, "source", "") == "hunting-index"
        and int(party_size or 0) > 1
        and int(level or 0) <= 10
        and base > 0.0
    ):
        return max(base, growth_target_home_max_distance(args, level, party_size, realm_key))
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) <= 4 and getattr(route, "source", "") == "hunting-index" and base > 0.0:
        return max(base, 6500.0)
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 5 and base > 0.0:
        return max(base, 5200.0)
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 6 and base > 0.0:
        return 3600.0
    if (
        getattr(route, "source", "") == "hunting-index"
        and realm_key in {"alb", "mid"}
        and int(party_size or 0) <= 1
        and int(level or 0) in {5, 6}
        and base > 0.0
    ):
        return max(base, 6500.0)
    if getattr(route, "source", "") == "hunting-index" and realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 9 and base > 0.0:
        return max(base, 10000.0)
    if getattr(route, "source", "") == "hunting-index" and realm_key == "alb" and int(party_size or 0) == 2 and int(level or 0) == 7 and base > 0.0:
        return max(base, 10000.0)
    if getattr(route, "source", "") == "hunting-index" and level <= 9 and int(party_size or 0) >= 4 and base > 0.0:
        return max(base, 6500.0)
    if getattr(route, "source", "") == "hunting-index" and level == 10 and int(party_size or 0) > 1 and base > 0.0:
        return max(base, 6500.0)
    if getattr(route, "source", "") == "hunting-index" and level <= 9 and base > 0.0:
        return max(base, 5200.0)
    if (
        realm_key == "hib"
        and int(party_size or 0) <= 1
        and int(level or 0) in {10, 11}
        and getattr(route, "source", "") == "hunting-index"
        and base > 0.0
    ):
        return max(base, 5200.0)
    if level <= 4 and base > 0.0:
        return min(base, 1500.0)
    if level <= 9 and base > 0.0:
        return 2800.0
    if level == 10 and party_size > 1 and base > 0.0:
        return min(base, 1500.0)
    return base


def growth_segment_hold_seconds(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
) -> int:
    base = int(getattr(args, "segment_seconds", 0) or 0)
    if bool(getattr(args, "watch_movement", False)) and int(party_size or 0) <= 1 and 6 <= int(level or 0) <= 10:
        return max(base, 240)
    if int(party_size or 0) >= 4 and int(level or 0) <= 4:
        return max(base, 360)
    if int(party_size or 0) >= 2 and int(level or 0) <= 4:
        return max(base, 300)
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 4:
        return max(base, 300)
    return base


def growth_combat_home_leash_distance(args: argparse.Namespace, level: int, party_size: int = 0) -> float:
    base = float(getattr(args, "combat_home_leash_distance", 1200.0) or 0.0)
    if (
        int(level or 0) == 10
        and int(party_size or 0) > 1
        and str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
    ):
        return max(base, 6500.0)
    if level == 10 and party_size > 1:
        return min(max(base, 1800.0), 1800.0)
    if level >= 45:
        return max(base, 2800.0)
    if 5 <= level <= 9:
        return max(base, 10000.0)
    if level <= 10:
        return max(base, 6200.0)
    return base


def growth_combat_home_leash_distance_for_route(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    if is_mid_duo_level_ten_short_engage_route(level, party_size, realm_key, route):
        return 2200.0
    runtime_cap = growth_runtime_low_solo_target_cap(args, level, party_size, realm_key, route)
    if runtime_cap > 0.0:
        return max(900.0, runtime_cap)
    leash_distance = growth_combat_home_leash_distance(args, level, party_size)
    if getattr(route, "source", "") == "hunting-index" and int(party_size or 0) > 1 and int(level or 0) <= 10:
        return max(leash_distance, growth_max_target_distance(args, level, party_size, realm_key, route))
    return leash_distance


def growth_combat_direct_move_distance(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    base = 1500.0
    if level <= 10:
        return max(base, growth_max_target_distance(args, level, party_size, realm_key, route))
    return base


def growth_target_loss_grace(args: argparse.Namespace, level: int, party_size: int) -> str:
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and int(party_size or 0) > 1
        and int(level or 0) <= 10
    ):
        return "24"
    return "1"


def growth_path_last_mile_distance(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    base = float(getattr(args, "path_last_mile_distance", 0.0) or 0.0)
    if (
        str(realm_key or "").strip().lower() == "mid"
        and int(level or 0) == 10
        and int(party_size or 0) <= 1
        and target_name_matches_any("rock crab", preferred_target_tokens(str(getattr(route, "prefer", "") or "")))
    ):
        return max(base, 3200.0)
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and int(party_size or 0) > 1
        and int(level or 0) <= 10
    ):
        return max(base, 2200.0)
    return base


def growth_required_target_home_hunt_distance(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    if is_mid_duo_level_ten_short_engage_route(level, party_size, realm_key, route):
        return 2200.0
    runtime_cap = growth_runtime_low_solo_target_cap(args, level, party_size, realm_key, route)
    if runtime_cap > 0.0:
        return runtime_cap
    route_home_cap = growth_route_home_low_solo_target_cap(args, level, party_size, realm_key, route)
    if route_home_cap > 0.0:
        return route_home_cap
    base = max(900.0, growth_combat_home_leash_distance_for_route(args, level, party_size, realm_key, route))
    if (
        getattr(route, "source", "") == "hunting-index"
        and realm_key == "hib"
        and int(party_size or 0) <= 1
        and int(level or 0) in {9, 10, 11}
    ):
        return max(base, growth_max_target_distance(args, level, party_size, realm_key, route))
    if getattr(route, "source", "") == "hunting-index" and int(level or 0) <= 10:
        return max(base, growth_max_target_distance(args, level, party_size, realm_key, route))
    return base


def route_home_xy_distance(snapshot: CharacterSnapshot, route: RoutePoint) -> float:
    return math.hypot(float(snapshot.x - route.x), float(snapshot.y - route.y))


def latest_timeline_row_for_case(timeline_csv: Path, case_name: str) -> dict[str, str]:
    if not timeline_csv.exists():
        return {}
    last_row: dict[str, str] = {}
    with timeline_csv.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("case") == case_name:
                last_row = row
    return last_row


def latest_timeline_row_leveled(row: dict[str, str]) -> bool:
    return to_int(row.get("level_delta")) > 0


def should_skip_growth_startup_teleport_near_route_home(
    args: argparse.Namespace,
    snapshots: dict[str, CharacterSnapshot],
    *,
    realm: RealmProfile,
    route_level: int,
    current_level: int,
    party_size: int,
    previous_segment_leveled: bool = False,
    planned_merchant_transaction: bool = False,
) -> bool:
    if getattr(args, "growth_speed_profile", "debug") != "fast-balance":
        return False
    if previous_segment_leveled or planned_merchant_transaction:
        return False
    if realm.startup_service_npc_name and getattr(args, "growth_auto_equip_slots", None):
        return False
    if not snapshots:
        return False
    route = select_growth_route_point(args, realm, route_level, party_size)
    threshold = growth_required_target_home_hunt_distance(args, current_level, party_size, realm.key, route)
    for snapshot in snapshots.values():
        if int(snapshot.region or 0) != int(realm.region):
            return False
        if route_home_xy_distance(snapshot, route) > threshold:
            return False
    return True


def growth_hunter_target_api_radius(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and int(party_size or 0) > 1
        and int(level or 0) <= 10
    ):
        return growth_max_target_distance(args, level, party_size, realm_key, route)
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and realm_key == "hib"
        and int(party_size or 0) <= 1
        and int(level or 0) == 4
        and getattr(route, "source", "") == "hunting-index"
    ):
        return max(5000.0, growth_max_target_distance(args, level, party_size, realm_key, route))
    if 5 <= level <= 9 or (realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 10):
        return growth_max_target_distance(args, level, party_size, realm_key, route)
    return 2200.0


def growth_hunter_target_api_engage_distance(
    args: argparse.Namespace,
    level: int,
    party_size: int = 0,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and int(party_size or 0) > 1
        and int(level or 0) <= 10
    ):
        return growth_max_target_distance(args, level, party_size, realm_key, route)
    if (
        str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and realm_key == "hib"
        and int(party_size or 0) <= 1
        and int(level or 0) == 4
        and getattr(route, "source", "") == "hunting-index"
    ):
        return max(5000.0, growth_max_target_distance(args, level, party_size, realm_key, route))
    if 5 <= level <= 9 or (realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 10):
        return growth_max_target_distance(args, level, party_size, realm_key, route)
    return 1500.0


def growth_allows_avoid_target_fallback(level: int, party_size: int = 0, realm_key: str = "") -> bool:
    if uses_growth_party_carry_tuning(level, party_size):
        return False
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 4:
        return False
    if realm_key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 8:
        return False
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return False
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) in {9, 10}:
        return False
    return True


def growth_hunter_target_max_ground_z_delta(level: int, party_size: int, realm_key: str = "") -> int:
    if realm_key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 6:
        return 650
    if realm_key == "mid" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return 1200
    if realm_key == "mid" and int(party_size or 0) >= 8 and int(level or 0) in {6, 7, 8, 9}:
        return 500
    if realm_key == "hib" and int(level or 0) in {5, 6}:
        return 500
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) in {9, 10, 11}:
        return 1200
    if realm_key == "hib" and int(level or 0) in {7, 8, 9, 10}:
        return 1200
    return 220


def growth_hunter_target_max_ground_z_delta_for_route(
    args: argparse.Namespace,
    level: int,
    party_size: int,
    realm: RealmProfile,
    route: RoutePoint | None,
) -> int:
    base_delta = int(growth_hunter_target_max_ground_z_delta(level, party_size, realm.key))
    if route is None or not bool(getattr(route, "live_anchor_z", False)):
        return base_delta

    try:
        ground_z = sample_route_z(
            realm,
            build_realm_height_samplers(),
            int(route.x),
            int(route.y),
            int(route.z),
            ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
        )
    except Exception:
        return base_delta

    live_delta = abs(int(route.z) - int(ground_z))
    if live_delta <= base_delta:
        return base_delta
    return max(base_delta, live_delta + 80)


def growth_hunter_target_max_attack_z_delta(level: int, party_size: int, realm_key: str = "") -> int:
    if realm_key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 6:
        return 650
    if realm_key == "alb" and int(party_size or 0) <= 1 and int(level or 0) == 9:
        return 360
    if realm_key == "hib" and int(party_size or 0) <= 1 and int(level or 0) == 10:
        return 360
    return 220


def growth_combat_chase_max_distance(
    level: int,
    party_size: int = 0,
    args: argparse.Namespace | None = None,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> float:
    if (
        args is not None
        and str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and int(party_size or 0) > 1
        and int(level or 0) <= 10
    ):
        return max(2200.0, growth_max_target_distance(args, level, party_size, realm_key, route))
    if (
        args is not None
        and str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and realm_key == "hib"
        and int(party_size or 0) <= 1
        and int(level or 0) == 4
        and getattr(route, "source", "") == "hunting-index"
    ):
        return max(5000.0, growth_max_target_distance(args, level, party_size, realm_key, route))
    if (
        args is not None
        and str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
        and realm_key == "hib"
        and int(party_size or 0) <= 1
        and int(level or 0) <= 2
        and getattr(route, "source", "") == "hunting-index"
    ):
        return max(2200.0, growth_max_target_distance(args, level, party_size, realm_key, route))
    if level <= 4:
        return 2200.0
    return 0.0


def waypoint_string(realm: RealmProfile, level: int, party_size: int = 0, *, ground_z_offset: int = 0) -> str:
    point = select_route_point(realm, level, party_size)
    return waypoint_string_for_point(realm, level, point, ground_z_offset=ground_z_offset)


def waypoint_string_for_point(
    realm: RealmProfile,
    level: int,
    point: RoutePoint,
    *,
    ground_z_offset: int = 0,
) -> str:
    height_samplers = build_realm_height_samplers()
    waypoints: list[str] = []
    for dx, dy in waypoint_offsets(level):
        x = point.x + dx
        y = point.y + dy
        if bool(getattr(point, "live_anchor_z", False)):
            z = int(point.z) + int(ground_z_offset or 0)
        else:
            z = sample_route_z(realm, height_samplers, x, y, point.z, ground_z_offset=ground_z_offset)
        waypoints.append(f"{x},{y},{z}")
    return "|".join(waypoints)


def route_home_string(realm: RealmProfile, level: int, party_size: int = 0, *, ground_z_offset: int = 0) -> str:
    point = select_route_point(realm, level, party_size)
    return route_home_string_for_point(realm, point, ground_z_offset=ground_z_offset)


def route_home_string_for_point(
    realm: RealmProfile,
    point: RoutePoint,
    *,
    ground_z_offset: int = 0,
) -> str:
    z = route_position_z_for_point(realm, point, ground_z_offset=ground_z_offset)
    return f"{point.x},{point.y},{z}"


def route_home_safe_landing_from_teleporter(
    realm: RealmProfile,
    route: RoutePoint,
    *,
    distance: float,
    ground_z_offset: int = 0,
) -> RoutePoint | None:
    if not route.teleport_destination:
        return None
    destination = teleport_destination_point(realm, route.teleport_destination)
    if destination is None:
        return None
    anchor_x, anchor_y, _anchor_z = destination
    dx = anchor_x - route.x
    dy = anchor_y - route.y
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return None
    safe_distance = min(max(0.0, float(distance or 0.0)), length * 0.75)
    x = int(round(route.x + dx / length * safe_distance))
    y = int(round(route.y + dy / length * safe_distance))
    z = sample_route_z(
        realm,
        build_realm_height_samplers(),
        x,
        y,
        route.z,
        ground_z_offset=ground_z_offset,
    )
    return replace(route, x=x, y=y, z=z)


def alb_rotting_zombie_safe_landing_point(
    realm: RealmProfile,
    route: RoutePoint,
    *,
    ground_z_offset: int = 0,
) -> RoutePoint | None:
    destination = teleport_destination_point(realm, route.teleport_destination or "Caer Ulfwych")
    if destination is None:
        return None
    _teleport_x, teleport_y, _teleport_z = destination
    y_direction = -1 if teleport_y < route.y else 1
    x = int(route.x)
    y = int(route.y + y_direction * 1300)
    z = sample_route_z(
        realm,
        build_realm_height_samplers(),
        x,
        y,
        route.z,
        ground_z_offset=ground_z_offset,
    )
    return replace(route, x=x, y=y, z=z)


def alb_river_racer_safe_landing_point(
    realm: RealmProfile,
    route: RoutePoint,
    *,
    ground_z_offset: int = 0,
) -> RoutePoint:
    x = int(route.x)
    y = int(route.y) + 1461
    z = sample_route_z(
        realm,
        build_realm_height_samplers(),
        x,
        y,
        route.z,
        ground_z_offset=ground_z_offset,
    )
    return replace(route, x=x, y=y, z=z)


def hib_water_beetle_safe_landing_point(route: RoutePoint) -> RoutePoint:
    return replace(route, x=int(route.x), y=int(route.y) - 1300, z=int(route.z), live_anchor_z=True)


def hib_party_water_beetle_safe_landing_point(
    realm: RealmProfile,
    route: RoutePoint,
    *,
    ground_z_offset: int = 0,
) -> RoutePoint | None:
    return route_home_safe_landing_from_teleporter(
        realm,
        route,
        distance=1800,
        ground_z_offset=ground_z_offset,
    )


def mid_spindly_rock_crab_safe_landing_point(
    realm: RealmProfile,
    route: RoutePoint,
    *,
    ground_z_offset: int = 0,
) -> RoutePoint | None:
    return route_home_safe_landing_from_teleporter(
        realm,
        route,
        distance=1800,
        ground_z_offset=ground_z_offset,
    )


def mid_nordic_dirge_safe_landing_point(
    realm: RealmProfile,
    route: RoutePoint,
    *,
    ground_z_offset: int = 0,
) -> RoutePoint | None:
    return route_home_safe_landing_from_teleporter(
        realm,
        route,
        distance=2000,
        ground_z_offset=ground_z_offset,
    )


def live_anchor_party_safe_landing_point(
    realm: RealmProfile,
    route: RoutePoint,
    *,
    current_level: int,
    party_size: int,
    ground_z_offset: int = 0,
) -> RoutePoint | None:
    if (
        not bool(getattr(route, "live_anchor_z", False))
        or int(party_size or 0) <= 1
        or str(getattr(route, "source", "") or "") != "hunting-index"
    ):
        return None
    landing_route = route
    destination_name = str(getattr(route, "teleport_destination", "") or "").strip()
    if not destination_name or teleport_destination_point(realm, destination_name) is None:
        destination_name = nearest_teleport_destination(realm, replace(route, teleport_destination=""))
        if destination_name:
            landing_route = replace(route, teleport_destination=destination_name)
    entry_avoid_radius = growth_objective_entry_aggro_avoid_radius(
        current_level,
        party_size,
        realm.key,
        route,
    )
    formation_radius = float(growth_party_leech_start_distance(current_level, party_size))
    landing_distance = max(
        float(entry_avoid_radius) + formation_radius + 350.0,
        float(entry_avoid_radius) * 1.4,
        2200.0,
    )
    if is_mid_duo_level_ten_short_engage_route(current_level, party_size, realm.key, route):
        max_home_distance = growth_required_target_home_hunt_distance(
            argparse.Namespace(),
            current_level,
            party_size,
            realm.key,
            route,
        )
        landing_distance = min(
            landing_distance,
            max(float(entry_avoid_radius) + 200.0, float(max_home_distance) - 200.0),
        )
    return route_home_safe_landing_from_teleporter(
        realm,
        landing_route,
        distance=landing_distance,
        ground_z_offset=ground_z_offset,
    )


def startup_route_home_after_services_point(
    realm: RealmProfile,
    route: RoutePoint,
    *,
    current_level: int,
    party_size: int,
    ground_z_offset: int = 0,
) -> RoutePoint:
    if (
        bool(getattr(route, "startup_anchor", False))
        and bool(getattr(route, "live_anchor_z", False))
        and realm.key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("envy drakeling", preferred_target_tokens(route.prefer))
    ):
        safe_landing = live_anchor_party_safe_landing_point(
            realm,
            route,
            current_level=current_level,
            party_size=party_size,
            ground_z_offset=ground_z_offset,
        )
        if safe_landing is not None:
            return safe_landing
    if bool(getattr(route, "startup_anchor", False)):
        return route
    if (
        realm.key == "alb"
        and int(current_level or 0) == 10
        and int(party_size or 0) <= 2
        and target_name_matches_any("rotting zombie", preferred_target_tokens(route.prefer))
    ):
        safe_landing = alb_rotting_zombie_safe_landing_point(
            realm,
            route,
            ground_z_offset=ground_z_offset,
        )
        if safe_landing is not None:
            return safe_landing
    if (
        realm.key == "alb"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("river racer", preferred_target_tokens(route.prefer))
    ):
        return alb_river_racer_safe_landing_point(
            realm,
            route,
            ground_z_offset=ground_z_offset,
        )
    if (
        realm.key == "alb"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("giant spider", preferred_target_tokens(route.prefer))
    ):
        safe_landing = route_home_safe_landing_from_teleporter(
            realm,
            route,
            distance=1800,
            ground_z_offset=ground_z_offset,
        )
        if safe_landing is not None:
            return safe_landing
    if (
        realm.key == "hib"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("water beetle", preferred_target_tokens(route.prefer))
    ):
        safe_landing = hib_party_water_beetle_safe_landing_point(
            realm,
            route,
            ground_z_offset=ground_z_offset,
        )
        if safe_landing is not None:
            return safe_landing
    if (
        realm.key == "hib"
        and int(current_level or 0) == 10
        and int(party_size or 0) <= 1
        and target_name_matches_any("water beetle", preferred_target_tokens(route.prefer))
        and bool(getattr(route, "live_anchor_z", False))
    ):
        return hib_water_beetle_safe_landing_point(route)
    if (
        realm.key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) == 2
        and target_name_matches_any("spindly rock crab", preferred_target_tokens(route.prefer))
    ):
        safe_landing = mid_spindly_rock_crab_safe_landing_point(
            realm,
            route,
            ground_z_offset=ground_z_offset,
        )
        if safe_landing is not None:
            return safe_landing
    if (
        realm.key == "mid"
        and int(current_level or 0) == 10
        and int(party_size or 0) <= 1
        and target_name_matches_any("nordic dirge", preferred_target_tokens(route.prefer))
    ):
        safe_landing = mid_nordic_dirge_safe_landing_point(
            realm,
            route,
            ground_z_offset=ground_z_offset,
        )
        if safe_landing is not None:
            return safe_landing
    live_anchor_landing = live_anchor_party_safe_landing_point(
        realm,
        route,
        current_level=current_level,
        party_size=party_size,
        ground_z_offset=ground_z_offset,
    )
    if live_anchor_landing is not None:
        return live_anchor_landing
    if (
        realm.key == "alb"
        and int(current_level or 0) == 7
        and int(party_size or 0) == 1
        and (
            target_name_matches_any("emerald snake", preferred_target_tokens(route.prefer))
            or target_name_matches_any("dragon ant worker", preferred_target_tokens(route.prefer))
        )
    ):
        destination = teleport_destination_point(realm, route.teleport_destination or "Campacorentin Station")
        if destination is not None:
            x, y, z = destination
            return RoutePoint(
                level=route.level,
                x=x,
                y=y,
                z=z,
                prefer=route.prefer,
                avoid=route.avoid,
                teleport_destination=route.teleport_destination,
                objective_adds=route.objective_adds,
                source=route.source,
                mob_level=route.mob_level,
                mob_count=route.mob_count,
                live_anchor_z=route.live_anchor_z,
            )
    return route


def route_position_z_for_point(
    realm: RealmProfile,
    point: RoutePoint,
    *,
    ground_z_offset: int = 0,
) -> int:
    if bool(getattr(point, "live_anchor_z", False)):
        return int(point.z) + int(ground_z_offset or 0)
    return sample_route_z(
        realm,
        build_realm_height_samplers(),
        point.x,
        point.y,
        point.z,
        ground_z_offset=ground_z_offset,
    )


def growth_flee_home_string(
    realm: RealmProfile,
    level: int,
    party_size: int = 0,
    *,
    ground_z_offset: int = 0,
) -> str:
    route = select_route_point(realm, level, party_size)
    return growth_flee_home_string_for_route(realm, route, ground_z_offset=ground_z_offset)


def growth_flee_home_string_for_route(
    realm: RealmProfile,
    route: RoutePoint,
    *,
    ground_z_offset: int = 0,
) -> str:
    if route.teleport_destination:
        destination = teleport_destination_point(realm, route.teleport_destination)
        if destination is not None:
            x, y, z = destination
            return f"{x},{y},{z + ground_z_offset}"
    if str(getattr(route, "source", "") or "").startswith("hunting-index"):
        return route_home_string_for_point(realm, route, ground_z_offset=ground_z_offset)
    return f"{realm.start[0]},{realm.start[1]},{realm.start[2] + ground_z_offset}"


def growth_flee_town_health_percent(level: int) -> int:
    return 99 if level >= 10 else 10


def growth_flee_home_stop_distance(level: int) -> int:
    return 120 if level >= 10 else 900


def growth_flee_safe_point_distance(level: int) -> int:
    if level >= 45:
        return 9000
    return 5200


def growth_flee_critical_safe_point_distance(level: int) -> int:
    if level >= 45:
        return 14000
    return 9000


def growth_required_target_tank_commit_health_percent(level: int, party_size: int, realm_key: str = "") -> int:
    if uses_hib_low_duo_recovery_tuning(level, party_size, realm_key):
        return 55
    if uses_low_solo_flee_tuning(level, party_size, realm_key) or uses_low_small_party_commit_tuning(
        level, party_size, realm_key
    ):
        return 10
    if uses_growth_party_carry_tuning(level, party_size):
        return 5
    if level <= 10 and party_size > 1:
        return 70
    return 55


def growth_required_target_tank_commit_health_percent_for_route(
    level: int,
    party_size: int,
    realm_key: str = "",
    route: RoutePoint | None = None,
) -> int:
    if is_alb_duo_level_ten_low_power_carry_route(level, party_size, realm_key, route):
        return 45
    return growth_required_target_tank_commit_health_percent(level, party_size, realm_key)


def watcher_observer_home_string(
    realm: RealmProfile,
    level: int,
    party_size: int = 0,
    *,
    observer_distance: float = 5000.0,
    ground_z_offset: int = 0,
) -> str:
    point = select_route_point(realm, level, party_size)
    if realm.key == "alb" and int(level or 0) == 10 and int(party_size or 0) <= 1 and "adder" in point.prefer.lower():
        x = 590500
        y = 499932
        z = sample_route_z(
            realm,
            build_realm_height_samplers(),
            x,
            y,
            point.z,
            ground_z_offset=ground_z_offset,
        )
        return f"{x},{y},{z}"
    anchor_x, anchor_y, _anchor_z = realm.start
    teleport_destination = nearest_teleport_destination(realm, point) if level >= 10 else point.teleport_destination
    teleport_point = teleport_destination_point(realm, teleport_destination)
    if teleport_point is not None:
        anchor_x, anchor_y, _anchor_z = teleport_point
    dx = anchor_x - point.x
    dy = anchor_y - point.y
    length = math.hypot(dx, dy)
    if length <= 0.0:
        x = point.x
        y = point.y
    else:
        distance = max(0.0, float(observer_distance or 0.0))
        if teleport_point is not None:
            distance = min(distance, length * 0.75)
        x = int(round(point.x + dx / length * distance))
        y = int(round(point.y + dy / length * distance))
    z = sample_route_z(
        realm,
        build_realm_height_samplers(),
        x,
        y,
        point.z,
        ground_z_offset=ground_z_offset,
    )
    return f"{x},{y},{z}"


def watcher_observer_home_point(
    args: argparse.Namespace,
    realm: RealmProfile,
    level: int,
    party_size: int = 0,
) -> RoutePoint:
    x_text, y_text, z_text = watcher_observer_home_string(
        realm,
        level,
        party_size,
        observer_distance=watcher_observer_follow_distance(args),
        ground_z_offset=args.ground_z_offset,
    ).split(",", 2)
    return RoutePoint(level=0, x=int(x_text), y=int(y_text), z=int(z_text))


def resolve_root_path(value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (ROOT / candidate).resolve()


def build_realm_height_samplers() -> dict[str, ClientZoneHeightSampler]:
    samplers: dict[str, ClientZoneHeightSampler] = {}
    for realm in REALMS.values():
        if not realm.ground_z_map:
            continue
        map_path = resolve_root_path(realm.ground_z_map)
        if map_path.exists():
            samplers[realm.key] = ClientZoneHeightSampler.from_config(map_path)
    return samplers


def sample_route_z(
    realm: RealmProfile,
    samplers: dict[str, ClientZoneHeightSampler],
    x: int,
    y: int,
    fallback_z: int,
    *,
    ground_z_offset: int = 0,
) -> int:
    sampler = samplers.get(realm.key)
    if sampler is None:
        return int(fallback_z)
    sampled = sampler.sample(int(x), int(y), realm.region)
    return int(sampled + ground_z_offset) if sampled is not None else int(fallback_z)


def growth_hunting_index_points_for_realm(
    growth_hunting_index: str,
    realm_key: str,
) -> list[RoutePoint]:
    if not str(growth_hunting_index or "").strip():
        return []
    index = load_growth_hunting_index(argparse.Namespace(growth_hunting_index=growth_hunting_index))
    points: list[RoutePoint] = []
    seen: set[tuple[int, int, int, int]] = set()
    for (candidate_realm, _party_size, level), candidates in sorted(index.items()):
        if candidate_realm != realm_key:
            continue
        for candidate in candidates:
            key = (int(level), candidate.x, candidate.y, candidate.z)
            if key in seen:
                continue
            seen.add(key)
            points.append(candidate)
    return points


def write_growth_path_graph(path: Path, *, ground_z_offset: int = 0, growth_hunting_index: str = "") -> None:
    height_samplers = build_realm_height_samplers()
    regions: dict[str, dict[str, object]] = {}
    for realm in REALMS.values():
        nodes_by_id: dict[str, dict[str, object]] = {}
        edges_by_pair: dict[tuple[str, str], dict[str, object]] = {}

        def add_node(node_id: str, x: int, y: int, z: int, *, sample_height: bool = True) -> None:
            sampled_z = (
                sample_route_z(
                    realm,
                    height_samplers,
                    x,
                    y,
                    z,
                    ground_z_offset=ground_z_offset,
                )
                if sample_height
                else int(z)
            )
            nodes_by_id.setdefault(node_id, {"id": node_id, "x": x, "y": y, "z": sampled_z})

        def add_edge(src: str, dst: str) -> None:
            if src == dst:
                return
            edges_by_pair.setdefault((src, dst), {"from": src, "to": dst, "max_height_delta": 2500})
            edges_by_pair.setdefault((dst, src), {"from": dst, "to": src, "max_height_delta": 2500})

        def add_segment(
            *,
            source_id: str,
            source: RoutePoint,
            dest_id: str,
            dest: RoutePoint,
            mid_prefix: str,
            sample_mid_height: bool = False,
        ) -> None:
            dx = dest.x - source.x
            dy = dest.y - source.y
            distance = max((dx * dx + dy * dy) ** 0.5, 1.0)
            step_distance = 120 if sample_mid_height else 350
            steps = max(1, int(distance // step_distance) + 1)
            last_id = source_id
            for step in range(1, steps):
                ratio = step / steps
                mid_id = f"{mid_prefix}_{step}"
                add_node(
                    mid_id,
                    int(round(source.x + dx * ratio)),
                    int(round(source.y + dy * ratio)),
                    int(round(source.z + (dest.z - source.z) * ratio)),
                    sample_height=sample_mid_height,
                )
                add_edge(last_id, mid_id)
                last_id = mid_id
            add_edge(last_id, dest_id)

        start_id = f"{realm.key}_start"
        start_point = RoutePoint(0, realm.start[0], realm.start[1], realm.start[2])
        add_node(start_id, start_point.x, start_point.y, start_point.z, sample_height=False)
        hub_x, hub_y, hub_z = STARTUP_TELEPORTER_HUBS[realm.key]
        hub_id = f"{realm.key}_teleporter_hub"
        add_node(hub_id, hub_x, hub_y, hub_z, sample_height=False)
        destination_nodes: dict[str, tuple[str, RoutePoint]] = {}
        for destination_name, dest_x, dest_y, dest_z in TELEPORT_DESTINATIONS.get(realm.key, ()):
            destination_key = normalize_identifier(destination_name)
            destination_id = f"{realm.key}_teleport_{destination_key}"
            destination_point = RoutePoint(0, dest_x, dest_y, dest_z)
            add_node(destination_id, dest_x, dest_y, dest_z, sample_height=False)
            destination_nodes[normalize_teleport_destination(destination_name)] = (destination_id, destination_point)
        add_segment(
            source_id=start_id,
            source=start_point,
            dest_id=hub_id,
            dest=RoutePoint(0, hub_x, hub_y, hub_z),
            mid_prefix=f"{realm.key}_start_teleporter_hub",
        )
        previous_node_id = start_id
        variant_points = route_variant_points_for_graph(realm)
        hunting_index_points = growth_hunting_index_points_for_realm(growth_hunting_index, realm.key)

        for index, point in enumerate(realm.points):
            node_id = f"{realm.key}_{point.level}"
            add_node(node_id, point.x, point.y, point.z, sample_height=False)
            if point.teleport_destination:
                destination = destination_nodes.get(normalize_teleport_destination(point.teleport_destination))
                if destination is not None:
                    destination_id, destination_point = destination
                    detours = route_travel_detours(realm, destination_id, point)
                    last_id = destination_id
                    last_point = destination_point
                    for detour_index, detour in enumerate(detours, start=1):
                        detour_id = f"{realm.key}_{destination_id}_{point.x}_{point.y}_detour_{detour_index}"
                        add_node(detour_id, detour.x, detour.y, detour.z)
                        add_segment(
                            source_id=last_id,
                            source=last_point,
                            dest_id=detour_id,
                            dest=detour,
                            mid_prefix=f"{detour_id}_path",
                            sample_mid_height=True,
                        )
                        last_id = detour_id
                        last_point = detour
                    add_segment(
                        source_id=last_id,
                        source=last_point,
                        dest_id=node_id,
                        dest=point,
                        mid_prefix=f"{realm.key}_teleport_{normalize_identifier(point.teleport_destination)}_{point.level}",
                        sample_mid_height=point.level >= 50 or bool(detours),
                    )
            if index > 0:
                source = realm.points[index - 1]
                source_node_id = previous_node_id or f"{realm.key}_{source.level}"
            else:
                source = start_point
                source_node_id = previous_node_id
            if index > 0 or previous_node_id == start_id:
                add_segment(
                    source_id=source_node_id,
                    source=source,
                    dest_id=node_id,
                    dest=point,
                    mid_prefix=f"{realm.key}_{source.level}_{point.level}",
                )
            if (
                index > 0
                and not point.teleport_destination
                and ((point.x - start_point.x) ** 2 + (point.y - start_point.y) ** 2) ** 0.5 <= 12000
            ):
                add_segment(
                    source_id=start_id,
                    source=start_point,
                    dest_id=node_id,
                    dest=point,
                    mid_prefix=f"{realm.key}_start_{point.level}",
                )
            previous_node_id = node_id

        for variant in variant_points:
            variant_id = route_variant_node_id(realm, variant)
            add_node(variant_id, variant.x, variant.y, variant.z, sample_height=False)
            source_id = start_id
            source = start_point
            if variant.teleport_destination:
                destination = destination_nodes.get(normalize_teleport_destination(variant.teleport_destination))
                if destination is not None:
                    source_id, source = destination
            detours = route_variant_travel_detours(realm, source_id, variant)
            last_id = source_id
            last_point = source
            for detour_index, detour in enumerate(detours, start=1):
                detour_id = f"{realm.key}_{source_id}_{variant.x}_{variant.y}_detour_{detour_index}"
                add_node(detour_id, detour.x, detour.y, detour.z)
                add_segment(
                    source_id=last_id,
                    source=last_point,
                    dest_id=detour_id,
                    dest=detour,
                    mid_prefix=f"{detour_id}_path",
                    sample_mid_height=True,
                )
                last_id = detour_id
                last_point = detour
            add_segment(
                source_id=last_id,
                source=last_point,
                dest_id=variant_id,
                dest=variant,
                mid_prefix=f"{realm.key}_{last_id}_{variant.x}_{variant.y}",
                sample_mid_height=bool(detours),
            )

        local_step = 350
        local_radius = 5600

        for index, point in enumerate(hunting_index_points):
            point_id = f"{realm.key}_hunting_index_{point.level}_{index}"
            add_node(point_id, point.x, point.y, point.z, sample_height=False)
            for base_point in realm.points:
                if math.hypot(base_point.x - point.x, base_point.y - point.y) <= local_step:
                    add_edge(f"{realm.key}_{base_point.level}", point_id)
                    break
            last_waypoint_id = point_id
            last_waypoint_point = point
            for waypoint_index, (dx, dy) in enumerate(waypoint_offsets(point.level), start=1):
                if dx == 0 and dy == 0:
                    continue
                waypoint_id = f"{point_id}_w_{waypoint_index}"
                waypoint_point = RoutePoint(point.level, point.x + dx, point.y + dy, point.z)
                add_node(
                    waypoint_id,
                    waypoint_point.x,
                    waypoint_point.y,
                    waypoint_point.z,
                    sample_height=True,
                )
                add_segment(
                    source_id=last_waypoint_id,
                    source=last_waypoint_point,
                    dest_id=waypoint_id,
                    dest=waypoint_point,
                    mid_prefix=f"{waypoint_id}_path",
                    sample_mid_height=True,
                )
                last_waypoint_id = waypoint_id
                last_waypoint_point = waypoint_point
            add_segment(
                source_id=last_waypoint_id,
                source=last_waypoint_point,
                dest_id=point_id,
                dest=point,
                mid_prefix=f"{point_id}_return_path",
                sample_mid_height=True,
            )

        hunt_centers = [(f"{realm.key}_{point.level}", point) for point in realm.points]
        hunt_centers.extend(
            (route_variant_node_id(realm, variant), variant)
            for variant in variant_points
            if variant.level >= 10
        )
        for center_id, point in hunt_centers:
            grid_prefix = center_id
            grid_ids: dict[tuple[int, int], str] = {(0, 0): center_id}
            for dx in range(-local_radius, local_radius + 1, local_step):
                for dy in range(-local_radius, local_radius + 1, local_step):
                    if dx == 0 and dy == 0:
                        continue
                    grid_id = f"{grid_prefix}_g_{dx}_{dy}"
                    grid_ids[(dx, dy)] = grid_id
                    add_node(grid_id, point.x + dx, point.y + dy, point.z)
            for (dx, dy), grid_id in grid_ids.items():
                for neighbor in ((dx + local_step, dy), (dx, dy + local_step)):
                    neighbor_id = grid_ids.get(neighbor)
                    if neighbor_id:
                        add_edge(grid_id, neighbor_id)

        regions[str(realm.region)] = {
            "nodes": list(nodes_by_id.values()),
            "edges": list(edges_by_pair.values()),
            "collisions": [],
        }
    payload = {
        "description": "Sparse realm growth route seeds for dummy 1-50 hunting tests. These are not full navmeshes.",
        "regions": regions,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def build_provision_command(
    args: argparse.Namespace,
    realm: RealmProfile,
    accounts_csv: Path,
    count: int,
    start: int,
    party_size: int = 1,
) -> list[str]:
    start_point = RoutePoint(level=1, x=realm.start[0], y=realm.start[1], z=realm.start[2])
    target_class_cycle = growth_cycle(realm.growth_class_cycle, realm.class_cycle)
    provision_class_cycle = base_class_cycle_for_growth(target_class_cycle) if should_provision_base_classes(args) else target_class_cycle
    start_z = sample_route_z(
        realm,
        build_realm_height_samplers(),
        start_point.x,
        start_point.y,
        start_point.z,
        ground_z_offset=getattr(args, "ground_z_offset", 0),
    )
    command = [
        sys.executable,
        str(TOOLS / "provision-dummy-accounts.py"),
        "--mysql-bin",
        args.mysql_bin,
        "--db-host",
        args.db_host,
        "--db-port",
        str(args.db_port),
        "--db-name",
        args.db_name,
        "--db-user",
        args.db_user,
        "--db-password",
        args.db_password,
        "--template-account",
        args.template_account,
        "--template-character",
        args.template_character,
        "--prefix",
        realm.prefix,
        "--character-prefix",
        realm.character_prefix,
        "--realm",
        str(realm.realm_id),
        "--class-cycle",
        provision_class_cycle,
        "--csv-class-cycle",
        target_class_cycle,
        "--race-cycle",
        growth_cycle(realm.growth_race_cycle, realm.race_cycle),
        "--spec-cycle",
        growth_cycle(realm.growth_spec_cycle, realm.spec_cycle),
        "--start",
        str(start),
        "--count",
        str(count),
        "--password",
        args.password,
        "--slot-index",
        "0",
        "--start-x",
        str(start_point.x),
        "--start-y",
        str(start_point.y),
        "--start-z",
        str(start_z),
        "--start-region",
        str(realm.region),
        "--position-step",
        str(args.position_step),
        "--csv",
        str(accounts_csv),
    ]
    if args.replace:
        command.append("--replace")
    if args.no_starter_equipment:
        command.append("--no-starter-equipment")
    return command


def select_growth_segment_route(
    args: argparse.Namespace,
    realm: RealmProfile,
    route_level: int,
    party_size: int,
    *,
    current_level: int,
    segment_index: int = 0,
) -> RoutePoint:
    route = select_growth_route_point(args, realm, route_level, party_size)
    if not growth_party_uses_carry_tuning(args, current_level, party_size):
        return route

    carry_reward_floor = growth_party_carry_verified_route_reward_floor(
        args,
        current_level,
        party_size,
        realm.key,
        route,
    )
    route_mob_level = int(getattr(route, "mob_level", 0) or 0)
    route_missing_floor_metadata = bool(
        carry_reward_floor > 0
        and route_mob_level <= 0
        and str(getattr(args, "growth_hunting_index", "") or "").strip()
        and str(getattr(route, "prefer", "") or "").strip()
    )
    if carry_reward_floor > 0 and (0 < route_mob_level < carry_reward_floor or route_missing_floor_metadata):
        replacement_route = select_growth_hunting_index_point_for_target(
            args,
            realm.key,
            carry_reward_floor,
            party_size,
            caller_player_level=current_level,
        )
        if replacement_route is not None:
            print(
                "growth party carry route floor replacement: "
                f"case={getattr(args, 'case_name', '')} segment={segment_index} realm={realm.key} "
                f"party={party_size} floor={carry_reward_floor} "
                f"from={route.prefer or route.source}/L{route_mob_level} "
                f"to={replacement_route.prefer or replacement_route.source}/L{getattr(replacement_route, 'mob_level', 0)}"
            )
            route = replacement_route
    route_mob_level = int(getattr(route, "mob_level", 0) or 0)
    if carry_reward_floor > 0 and 0 < route_mob_level < carry_reward_floor:
        raise RuntimeError(
            "growth party carry route below reward floor: "
            f"case={getattr(args, 'case_name', '')} segment={segment_index} realm={realm.key} "
            f"party={party_size} level={current_level} "
            f"route={route.prefer or route.source}/L{route_mob_level} floor={carry_reward_floor}"
        )
    if route_missing_floor_metadata and int(getattr(route, "mob_level", 0) or 0) <= 0:
        raise RuntimeError(
            "growth party carry route missing mob level after replacement failed: "
            f"case={getattr(args, 'case_name', '')} segment={segment_index} realm={realm.key} "
            f"party={party_size} level={current_level} route={route.prefer or route.source}"
        )
    return route


def build_behavior_command(
    args: argparse.Namespace,
    realm: RealmProfile,
    accounts_csv: Path,
    case_dir: Path,
    segment_index: int,
    party_size: int,
    current_level: int,
    path_graph: Path,
    selected_route: RoutePoint | None = None,
) -> list[str]:
    route_level = int(getattr(args, "growth_route_level_override", 0) or current_level)
    target_level = int(getattr(args, "growth_target_level_override", 0) or current_level)
    party_carry_tuning = growth_party_uses_carry_tuning(args, current_level, party_size)
    setattr(args, "growth_route_player_level", current_level)
    if party_carry_tuning and int(party_size or 0) > 1:
        setattr(args, "growth_route_level_is_carry_target", True)
    fast_party_invites = party_carry_tuning or int(party_size or 0) >= 8
    target_plan_override = getattr(args, "growth_target_plan_override", None)
    if target_plan_override is not None:
        min_target, ideal_target, max_delta = target_plan_override
    else:
        min_target, ideal_target, max_delta = target_levels(target_level, party_size, realm.key)
    min_target, ideal_target, max_delta = enforce_no_lower_xp_target_plan(
        args,
        target_level,
        party_size,
        min_target,
        ideal_target,
        max_delta,
        realm.key,
    )
    min_target, ideal_target, max_delta = enforce_reward_non_grey_target_plan(
        current_level,
        int(min_target),
        int(ideal_target),
        int(max_delta),
    )
    allow_lower_xp_target_plan = bool(getattr(args, "growth_allow_lower_xp_target_plan", False)) and bool(
        getattr(args, "growth_allow_lower_xp_gear_farm", True)
    )
    low_carry_survival_plan = bool(
        party_carry_tuning
        and int(current_level or 0) <= 7
        and realm.key in {"alb", "mid"}
        and int(min_target or 0) < minimum_growth_effective_target_level(current_level, party_size, realm.key)
    )
    if not allow_lower_xp_target_plan and not low_carry_survival_plan:
        validate_growth_target_plan(
            realm_key=realm.key,
            current_level=target_level,
            party_size=party_size,
            route_level=route_level,
            min_target=min_target,
            ideal_target=ideal_target,
            max_delta=max_delta,
        )
    metrics_csv = case_dir / f"segment-{segment_index:03d}-metrics.csv"
    combat_csv = case_dir / f"segment-{segment_index:03d}-combat.csv"
    report_md = case_dir / f"segment-{segment_index:03d}-report.md"
    live_control_json = case_dir / "live-control.json"
    trace_pattern = case_dir / "movement" / f"segment-{segment_index:03d}-{{username}}-{{round}}.jsonl"
    encounter_pattern = case_dir / "encounters" / f"segment-{segment_index:03d}-{{username}}-{{round}}.jsonl"
    trace_pattern.parent.mkdir(parents=True, exist_ok=True)
    encounter_pattern.parent.mkdir(parents=True, exist_ok=True)
    route = selected_route or select_growth_segment_route(
        args,
        realm,
        route_level,
        party_size,
        current_level=current_level,
        segment_index=segment_index,
    )

    def failure_avoid_targets_for_route(selected_route: RoutePoint) -> str:
        targets = growth_failed_target_memory_avoid_targets(args, realm.key, current_level, party_size)
        return growth_filter_shortage_recovery_failed_avoid_targets(
            args,
            targets,
            realm.key,
            current_level,
            party_size,
            route=selected_route,
        )

    route_blocked_by_failed_memory = growth_route_blocked_by_failed_target_memory(
        args,
        route,
        realm.key,
        current_level,
        party_size,
    )
    if route_blocked_by_failed_memory:
        replacement_route = select_growth_hunting_index_point_for_target(
            args,
            realm.key,
            route_level,
            party_size,
            caller_player_level=current_level,
        )
        if replacement_route is not None and not growth_route_blocked_by_failed_target_memory(
            args,
            replacement_route,
            realm.key,
            current_level,
            party_size,
        ):
            print(
                "growth route failed-memory replacement: "
                f"case={getattr(args, 'case_name', '')} segment={segment_index} realm={realm.key} "
                f"party={party_size} level={current_level} "
                f"from={route.prefer or route.source} to={replacement_route.prefer or replacement_route.source}"
            )
            route = replacement_route
            route_blocked_by_failed_memory = False

    failure_avoid_targets = failure_avoid_targets_for_route(route)
    failure_avoid_tokens = preferred_target_tokens(failure_avoid_targets)
    route_prefer_tokens = preferred_target_tokens(route.prefer)
    if route_prefer_tokens and not route_blocked_by_failed_memory:
        failure_avoid_targets = remove_matching_target_names_csv(failure_avoid_targets, route_prefer_tokens)
        failure_avoid_tokens = preferred_target_tokens(failure_avoid_targets)
    live_anchor_prefer_tokens = (
        preferred_target_tokens(route.prefer) if bool(getattr(route, "live_anchor_z", False)) else []
    )
    if live_anchor_prefer_tokens:
        failure_avoid_targets = remove_matching_target_names_csv(failure_avoid_targets, live_anchor_prefer_tokens)
        failure_avoid_tokens = preferred_target_tokens(failure_avoid_targets)
    required_target_name = strict_route_target_name(route, current_level, party_size, realm.key)
    keep_required_lower_xp_target = (
        (
            realm.key in {"alb", "hib"}
            and int(party_size or 0) <= 1
            and int(current_level or 0) == 7
        )
        or (
            int(party_size or 0) <= 1
            and int(current_level or 0) >= 8
            and route.source == "hunting-index"
            and bool(str(route.prefer or "").strip())
        )
    )
    if allow_lower_xp_target_plan and not keep_required_lower_xp_target:
        required_target_name = ""
    if required_target_name and target_name_matches_any(required_target_name, failure_avoid_tokens):
        required_target_name = ""
    min_target, ideal_target, max_delta = adjust_growth_target_plan_for_required_route(
        route,
        current_level=current_level,
        party_size=party_size,
        realm_key=realm.key,
        min_target=min_target,
        ideal_target=ideal_target,
        max_delta=max_delta,
    )
    min_target, ideal_target, max_delta = adjust_low_solo_hunting_target_plan(
        args,
        route,
        current_level=current_level,
        party_size=party_size,
        realm_key=realm.key,
        min_target=min_target,
        ideal_target=ideal_target,
        max_delta=max_delta,
    )
    if party_carry_tuning:
        min_target, ideal_target, max_delta = adjust_party_carry_target_plan_for_route_fallback(
            route,
            current_level=current_level,
            party_size=party_size,
            realm_key=realm.key,
            min_target=min_target,
            ideal_target=ideal_target,
            max_delta=max_delta,
        )
    if not party_carry_tuning or bool(getattr(args, "growth_equip_party_carry_gear", False)):
        min_target, ideal_target, max_delta = enforce_party_carry_non_grey_target_plan(
            args,
            current_level,
            party_size,
            min_target,
            ideal_target,
            max_delta,
            realm.key,
        )
    if uses_hib_low_duo_recovery_tuning(current_level, party_size, realm.key):
        ideal_target = min(int(ideal_target), 3)
        min_target = min(int(min_target), ideal_target)
        max_delta = 0
    min_target, ideal_target, max_delta = adjust_growth_target_plan_for_failed_level_scan(
        args,
        current_level,
        party_size,
        int(min_target),
        int(ideal_target),
        int(max_delta),
    )
    command_max_target_level = growth_command_max_target_level(target_level, ideal_target, max_delta, party_size)
    if growth_route_home_low_solo_anchor_search_enabled(
        args,
        route,
        current_level=current_level,
        party_size=party_size,
    ):
        route_mob_level = int(getattr(route, "mob_level", 0) or 0)
        if route_mob_level > 0:
            command_max_target_level = max(command_max_target_level, route_mob_level)
    min_target, command_max_target_level = include_verified_route_mob_level_in_target_band(
        route,
        int(min_target),
        int(command_max_target_level),
        realm_key=realm.key,
        current_level=current_level,
        party_size=party_size,
        allow_lower_xp_route_mob=allow_lower_xp_target_plan
        or growth_allows_verified_route_mob_below_current_level(args),
    )
    if party_carry_tuning:
        carry_reward_floor = growth_party_carry_verified_route_reward_floor(
            args,
            current_level,
            party_size,
            realm.key,
            route,
        )
        if carry_reward_floor > 0:
            min_target = max(int(min_target), carry_reward_floor)
            ideal_target = max(int(ideal_target), int(min_target))
            command_max_target_level = max(int(command_max_target_level), int(ideal_target))
    live_control_json.write_text(
        json.dumps(
            {
                "revision": f"segment-{segment_index:03d}-level-{current_level}",
                "baseline_min_target_level": min_target,
                "baseline_max_target_level": command_max_target_level,
                "baseline_player_level": current_level,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    level50_boss_party = level50_party_boss_rules_enabled(current_level, party_size)
    startup_train_level = (
        growth_party_carry_level_for_realm(args, current_level, party_size, realm.key) if party_carry_tuning else current_level
    )
    passive_leech_follow_distance = (
        growth_passive_xp_leech_follow_distance(current_level, party_size) if party_carry_tuning else 0
    )
    party_assist_interval = growth_party_assist_interval(
        current_level,
        party_size,
        level50_boss_party=level50_boss_party,
        carry_tuning=party_carry_tuning,
    )
    party_form_up_delay = "8" if level50_boss_party else "4"
    party_rescue_max_age = str(
        getattr(args, "party_rescue_max_age", 0.0) or (14 if level50_boss_party else 10)
    )
    party_rescue_assist_after = str(
        getattr(args, "party_rescue_assist_after", 0.0) or (3 if level50_boss_party else 6)
    )
    action_rotation = solo_action_rotation_for_accounts(accounts_csv, party_size)
    segment_hold_seconds = growth_segment_hold_seconds(args, current_level, party_size, realm.key)
    merchant_only_segment = bool(getattr(args, "growth_merchant_only_segment", False))
    route_policy_level = growth_party_carry_route_policy_level(
        args,
        current_level,
        route_level,
        party_size,
        carry_tuning=party_carry_tuning,
    )

    def distance_policy_value(policy_func) -> float:
        current_value = float(policy_func(args, current_level, party_size, realm.key, route))
        if int(route_policy_level or 0) == int(current_level or 0):
            return current_value
        route_value = float(policy_func(args, route_policy_level, party_size, realm.key, route))
        return max(current_value, route_value)

    command = [
        sys.executable,
        str(TOOLS / "behavior-dummy-client.py"),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--accounts",
        str(accounts_csv),
        "--concurrency",
        str(party_size),
        "--rounds",
        "1",
        "--hold",
        str(segment_hold_seconds),
        "--safe-exit-max-seconds",
        str(int(getattr(args, "safe_exit_max_seconds", GROWTH_SAFE_EXIT_MAX_SECONDS))),
        "--safe-exit-recent-damage-grace",
        str(int(getattr(args, "safe_exit_recent_damage_grace", GROWTH_SAFE_EXIT_RECENT_DAMAGE_GRACE))),
        "--no-safe-exit-disengage-current-target",
        "--ramp-up",
        str(args.ramp_up),
        "--party-size",
        str(party_size),
        "--login-retries",
        str(args.login_retries),
        "--login-retry-delay",
        str(args.login_retry_delay),
        "--ping-interval",
        "5",
        "--turn-interval",
        "0",
        "--behavior-profile",
        "custom" if merchant_only_segment else ("solo-melee" if party_size == 1 else "party-dps"),
        "--action-rotation",
        action_rotation,
        "--party-role-strategy",
        "same" if party_size == 1 else "mixed",
        "--realm-strategy",
        "fixed",
        "--api-port",
        str(args.api_port),
        "--player-level",
        str(current_level),
        "--ideal-target-level",
        str(ideal_target),
        "--min-target-level",
        str(min_target),
        "--max-target-level",
        str(command_max_target_level),
        "--max-target-level-delta",
        str(max_delta),
        "--max-target-distance",
        str(distance_policy_value(growth_max_target_distance)),
        "--target-home-max-distance",
        str(distance_policy_value(growth_target_home_max_distance)),
        "--combat-home-leash-distance",
        str(distance_policy_value(growth_combat_home_leash_distance_for_route)),
        "--combat-chase-max-distance",
        str(
            max(
                float(growth_combat_chase_max_distance(current_level, party_size, args, realm.key, route)),
                float(growth_combat_chase_max_distance(route_policy_level, party_size, args, realm.key, route))
                if int(route_policy_level or 0) != int(current_level or 0)
                else 0.0,
            )
        ),
        "--combat-chase-max-distance-grace",
        "3",
        "--target-timeout",
        str(args.target_timeout),
        "--target-loss-grace",
        growth_target_loss_grace(args, current_level, party_size),
        "--target-death-cooldown",
        "24",
        "--target-retreat-cooldown",
        "18",
        "--reject-target-on-server-los-failure",
        "--server-los-failure-target-cooldown",
        "45",
        "--server-los-failure-kind-cooldown",
        "20",
        "--server-los-failure-grace",
        "10",
        "--target-selection",
        "smart",
        "--include-peace-npcs",
        "--current-target-api-refresh",
        "--hunter-target-api-scout",
        "--hunter-target-api-radius",
        str(distance_policy_value(growth_hunter_target_api_radius)),
        "--hunter-target-api-engage-distance",
        str(distance_policy_value(growth_hunter_target_api_engage_distance)),
        "--hunter-target-max-ground-z-delta",
        str(growth_hunter_target_max_ground_z_delta_for_route(args, current_level, party_size, realm, route)),
        "--hunter-target-max-attack-z-delta",
        str(growth_hunter_target_max_attack_z_delta(current_level, party_size, realm.key)),
        "--hunter-min-time-left-for-new-target",
        growth_hunter_min_time_left_for_new_target(current_level, party_size),
        "--combat-interval",
        str(args.combat_interval),
        "--target-pool",
        str(args.target_pool),
        "--attack-range",
        "350",
        "--combat-direct-move-distance",
        str(growth_combat_direct_move_distance(args, current_level, party_size, realm.key, route)),
        "--attack-target-in-view-prime-delay",
        growth_attack_target_in_view_prime_delay(current_level, party_size, carry_tuning=party_carry_tuning),
        "--melee-stick-attack",
        "--melee-stick-attack-distance",
        "1800",
        "--target-face-command-interval",
        "0.8",
        "--melee-range-buffer",
        "300",
        "--minimum-melee-stop-distance",
        "60",
        "--move-step",
        "260",
        "--smooth-movement",
        "--smooth-move-interval",
        str(args.smooth_move_interval),
        "--movement-speed",
        str(args.movement_speed),
        "--movement-update-interval",
        str(args.smooth_move_interval),
        "--path-graph",
        str(path_graph),
        "--path-region",
        str(realm.region),
        "--path-last-mile-distance",
        str(distance_policy_value(growth_path_last_mile_distance)),
        "--path-node-arrival-distance",
        "80",
        "--path-max-height-delta",
        "900",
        "--path-waypoint-ground-z-skip-delta",
        "500",
        "--waypoints",
        waypoint_string_for_point(realm, route_level, route, ground_z_offset=args.ground_z_offset),
        "--waypoint-mode",
        "loop",
        "--waypoint-continuous-turns",
        "--waypoint-advance-distance",
        "35",
        "--waypoint-stop-distance",
        "12",
        "--required-target-home",
        route_home_string_for_point(realm, route, ground_z_offset=args.ground_z_offset),
        "--required-target-home-stop-distance",
        "900",
        "--required-target-home-hunt-distance",
        str(distance_policy_value(growth_required_target_home_hunt_distance)),
        "--required-target-recover-before-home-health-percent",
        str(growth_required_target_recover_before_home_health_percent(current_level, party_size, realm.key)),
        "--required-target-recover-before-hunt-endurance-percent",
        str(growth_required_target_recover_before_hunt_endurance_percent(current_level, party_size, realm.key)),
        "--use-skills",
        "--combat-usable-api",
        "--skill-interval",
        "3.0",
        "--skill-indexes",
        "0,1,2",
        "--skill-type",
        "1",
        "--allow-unvalidated-skills",
        "--startup-self-buff-count",
        "2",
        "--startup-self-buff-delay",
        "0.8",
        "--party-invite-interval",
        "1" if fast_party_invites else "6",
        "--party-accept-interval",
        "0.5" if fast_party_invites else "3",
        "--party-assist-interval",
        party_assist_interval,
        "--party-follow-interval",
        "0.2",
        "--party-follow-step",
        "320",
        "--party-follow-distance",
        growth_party_follow_distance(current_level, party_size, carry_tuning=party_carry_tuning),
        *(
            [
                "--passive-xp-leech-follow-distance",
                str(passive_leech_follow_distance),
                "--party-follow-teleport-distance",
                "0",
                "--party-follow-teleport-stop-distance",
                str(passive_leech_follow_distance),
            ]
            if party_carry_tuning
            else []
        ),
        "--party-use-assist-command",
        "--auto-loot",
        "--auto-release-on-death",
        "--death-release-delay",
        "2",
        "--death-recovery-cooldown",
        "8",
        "--post-release-rest",
        "3",
        "--rest-chance",
        "0",
        "--rest-min",
        "1",
        "--rest-max",
        "3",
        "--low-health-rest-percent",
        str(growth_low_health_rest_percent(current_level, party_size, realm.key)),
        "--low-health-rest-resume-percent",
        str(growth_low_health_rest_resume_percent(current_level, party_size, realm.key)),
        "--low-health-rest-min",
        "6",
        "--low-health-rest-max",
        "14",
        "--flee-health-percent",
        str(growth_flee_health_percent_for_route(current_level, party_size, realm.key, route)),
        "--flee-pressure-health-percent",
        str(growth_flee_pressure_health_percent_for_route(args, current_level, party_size, realm.key, route)),
        "--flee-duration",
        "24",
        "--flee-step",
        str(growth_flee_step(current_level, party_size, realm.key)),
        "--flee-move-interval",
        "0.35",
        "--flee-movement-speed",
        str(growth_flee_movement_speed(current_level, party_size, realm.key)),
        "--flee-use-sprint",
        "--flee-home",
        growth_flee_home_string_for_route(realm, route, ground_z_offset=args.ground_z_offset),
        "--flee-home-stop-distance",
        str(growth_flee_home_stop_distance(current_level)),
        "--flee-dynamic-safe-point",
        "--flee-safe-threat-radius",
        "6000",
        "--flee-safe-point-distance",
        str(growth_flee_safe_point_distance(current_level)),
        "--flee-critical-health-percent",
        str(growth_flee_critical_health_percent_for_route(current_level, party_size, realm.key, route)),
        "--flee-critical-safe-point-distance",
        str(growth_flee_critical_safe_point_distance(current_level)),
        "--flee-safe-api-scout",
        "--flee-safe-replan-damage-grace",
        "6",
        "--travel-aggro-clear-grace",
        str(getattr(args, "travel_aggro_clear_grace", 24.0)),
        "--travel-aggro-avoid-seconds",
        "30",
        "--travel-aggro-avoid-radius",
        "5200",
        "--target-nearby-avoid-radius",
        "1800",
        "--flee-town-health-percent",
        str(growth_flee_town_health_percent(current_level)),
        "--flee-min-combat-seconds",
        "4",
        "--flee-min-damage-taken",
        "20",
        "--flee-damage-taken-ratio",
        "1.5",
        "--flee-melee-counterattack-min-attacks",
        "3",
        "--flee-melee-counterattack-health-floor",
        str(growth_flee_melee_counterattack_health_floor_for_route(current_level, party_size, realm.key, route)),
        "--flee-melee-counterattack-max-distance",
        "1800",
        "--required-target-tank-commit-health-percent",
        str(growth_required_target_tank_commit_health_percent_for_route(current_level, party_size, realm.key, route)),
        "--think-min",
        "0.25",
        "--think-max",
        "0.9",
        "--startup-command",
        "/bind",
        "--startup-command",
        "/sprint",
        "--startup-delay",
        str(getattr(args, "startup_delay", 0.0)),
        "--greet-nearby-player",
        "--player-greet-chance",
        "0.35",
        "--command",
        "",
        "--jitter",
        "0.2",
        "--tick",
        "0.05",
        "--metrics-csv",
        str(metrics_csv),
        "--combat-csv",
        str(combat_csv),
        "--report-md",
        str(report_md),
        "--trace-movement-log",
        str(trace_pattern),
        "--encounter-log",
        str(encounter_pattern),
        "--encounter-log-interval",
        str(args.encounter_log_interval),
        "--live-control-file",
        str(live_control_json),
        "--live-control-interval",
        str(getattr(args, "live_control_interval", 1.0)),
    ]
    objective_entry_radius = growth_objective_entry_aggro_avoid_radius(current_level, party_size, realm.key, route)
    if objective_entry_radius > 0:
        command += ["--objective-entry-aggro-avoid-radius", f"{objective_entry_radius:.0f}"]
    target_nearby_avoid_names = growth_target_nearby_avoid_names_for_route(
        current_level,
        party_size,
        realm.key,
        route,
    )
    if target_nearby_avoid_names:
        command += ["--target-nearby-avoid-name", target_nearby_avoid_names]
    if not merchant_only_segment:
        command.append("--hunter")
    if bool(getattr(route, "live_anchor_z", False)):
        command.append("--route-home-preserve-z")
    if growth_allows_avoid_target_fallback(current_level, party_size, realm.key):
        command.append("--allow-avoid-target-fallback")
    if action_rotation in {"caster-basic", "healer-support", "hybrid"}:
        command += ["--stationary-cast-actions", "--cast-action-hold", f"{CASTER_STATIONARY_CAST_HOLD_SECONDS:.1f}"]
    if party_size == 1 and action_rotation == "healer-support":
        command += [
            "--support-spell-chance",
            "1.0",
            "--healer-self-health-percent",
            "80",
        ]
    if realm.ground_z_map:
        command += [
            "--ground-z-map",
            realm.ground_z_map,
            "--ground-z-offset",
            str(args.ground_z_offset),
            "--server-correction-smoothing",
        ]
    if realm.startup_service_npc_name and current_level < 50:
        command += [
            "--startup-service-npc-name",
            realm.startup_service_npc_name,
            "--startup-service-interact",
            "--startup-service-accept-dialog",
        ]
    route_home_fast_travel = str(getattr(args, "growth_fast_travel", "") or "").strip().lower() == "route-home"
    if route_home_fast_travel and not merchant_only_segment:
        wall_timeout = (
            float(segment_hold_seconds)
            + min(max(0.0, float(getattr(args, "safe_exit_max_seconds", 0.0) or 0.0)), 30.0)
            + (30.0 if int(party_size or 0) >= 8 else 20.0)
        )
        command += [
            "--startup-route-home-after-services",
            route_home_string_for_point(
                realm,
                startup_route_home_after_services_point(
                    realm,
                    route,
                    current_level=current_level,
                    party_size=party_size,
                    ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
                ),
                ground_z_offset=args.ground_z_offset,
            ),
            "--allow-network-disconnect-success",
            "--allow-party-safe-exit-partial-success",
            "--round-wall-timeout-seconds",
            f"{wall_timeout:.0f}",
            "--allow-round-wall-timeout-success",
        ]
        if int(party_size or 0) > 1:
            command += [
                "--route-home-api-retries",
                "5",
                "--route-home-api-retry-delay",
                "1.0",
            ]
    auto_equip_slots = getattr(args, "growth_auto_equip_slots", [])
    if party_carry_tuning:
        auto_equip_slots = sorted({*auto_equip_slots, 41})
    if auto_equip_slots:
        command += ["--startup-service-equip-slot", ",".join(str(slot) for slot in auto_equip_slots)]
        if party_carry_tuning:
            carry_slots = list(range(growth_party_carry_count_from_args(args, party_size)))
            if carry_slots:
                command += [
                    "--startup-service-equip-party-slot",
                    ",".join(str(slot) for slot in carry_slots),
                ]
    append_repeated_values(
        command,
        "--startup-service-equip-party-slot-map",
        getattr(args, "growth_auto_equip_party_slot_maps", []),
    )
    auto_sell_slots = getattr(args, "growth_auto_sell_slots", [])
    merchant_npc_name = str(getattr(args, "growth_merchant_npc_name", "") or "")
    merchant_buy_slots = getattr(args, "growth_merchant_buy_slots", [])
    merchant_equip_slots = getattr(args, "growth_merchant_equip_slots", [])
    merchant_sell_party_slot_maps = getattr(args, "growth_merchant_sell_party_slot_maps", [])
    merchant_buy_party_slot_maps = getattr(args, "growth_merchant_buy_party_slot_maps", [])
    merchant_equip_party_slot_maps = getattr(args, "growth_merchant_equip_party_slot_maps", [])
    if merchant_npc_name and (
        auto_sell_slots
        or merchant_buy_slots
        or merchant_equip_slots
        or merchant_sell_party_slot_maps
        or merchant_buy_party_slot_maps
        or merchant_equip_party_slot_maps
    ):
        command += [
            "--startup-merchant-npc-name",
            merchant_npc_name,
            "--startup-merchant-scan-seconds",
            str(getattr(args, "growth_merchant_scan_seconds", 1.0)),
            "--startup-merchant-approach-distance",
            str(getattr(args, "growth_merchant_approach_distance", 150.0)),
            "--startup-merchant-approach-timeout",
            str(getattr(args, "growth_merchant_approach_timeout", 90.0)),
        ]
        if auto_sell_slots:
            command += ["--startup-merchant-sell-slot", ",".join(str(slot) for slot in auto_sell_slots)]
        if merchant_buy_slots:
            command += ["--startup-merchant-buy-slot", ",".join(str(slot) for slot in merchant_buy_slots)]
        if merchant_equip_slots:
            command += ["--startup-merchant-equip-slot", ",".join(str(slot) for slot in merchant_equip_slots)]
        append_repeated_values(command, "--startup-merchant-sell-party-slot", merchant_sell_party_slot_maps)
        append_repeated_values(command, "--startup-merchant-buy-party-slot", merchant_buy_party_slot_maps)
        append_repeated_values(command, "--startup-merchant-equip-party-slot", merchant_equip_party_slot_maps)
    if should_train_at_level(current_level):
        command += ["--startup-train-full-specs", "--startup-train-level", str(startup_train_level)]
    elif current_level >= 50:
        command += ["--startup-train-full-specs", "--startup-train-level", str(startup_train_level)]
    teleport_destination = nearest_teleport_destination(realm, route) if current_level >= 10 else route.teleport_destination
    if (
        not route_home_fast_travel
        and not skip_startup_teleport_for_checkpoint_start(args)
        and not bool(getattr(args, "growth_skip_startup_teleport", False))
    ):
        append_startup_teleport_command(command, args, teleport_destination, realm=realm)
    if args.nav_api_url:
        command += ["--nav-api-url", args.nav_api_url]
    if args.live_api_url:
        command += ["--live-api-url", args.live_api_url]
    if required_target_name:
        command += ["--require-target-name", required_target_name]
        if strict_route_target_name_requires_exact(route, current_level, party_size, realm.key):
            command.append("--require-target-name-exact")
    suppress_carry_prefer = bool(
        party_carry_tuning
        and route.source == "hunting-index"
        and int(current_level or 0) >= 8
        and not (
            realm.key == "alb"
            and int(current_level or 0) == 10
            and int(party_size or 0) == 2
            and (
                target_name_matches_any("river racer", preferred_target_tokens(route.prefer))
                or target_name_matches_any("rotting zombie", preferred_target_tokens(route.prefer))
            )
        )
        and not (
            realm.key == "hib"
            and int(current_level or 0) == 10
            and int(party_size or 0) == 2
            and (
                target_name_matches_any("red wolfhound", preferred_target_tokens(route.prefer))
                or target_name_matches_any("water beetle", preferred_target_tokens(route.prefer))
            )
        )
        and not (
            realm.key == "mid"
            and int(current_level or 0) == 10
            and int(party_size or 0) == 2
            and (
                target_name_matches_any("spindly rock crab", preferred_target_tokens(route.prefer))
                or target_name_matches_any("wind wisp", preferred_target_tokens(route.prefer))
                or target_name_matches_any("hobgoblin prowler", preferred_target_tokens(route.prefer))
                or target_name_matches_any("tawny lynx", preferred_target_tokens(route.prefer))
                or target_name_matches_any("svartalf outcast", preferred_target_tokens(route.prefer))
            )
        )
    )
    prefer_target_name = "" if suppress_carry_prefer else route.prefer
    if prefer_target_name and failure_avoid_tokens:
        filtered_prefer_target_name = ",".join(
            token.strip()
            for token in prefer_target_name.split(",")
            if token.strip() and not target_name_matches_any(token.strip(), failure_avoid_tokens)
        )
        if filtered_prefer_target_name:
            prefer_target_name = filtered_prefer_target_name
        else:
            prefer_target_name = ""
    if prefer_target_name:
        explicit_xp_required = (
            segment_requirement_explicit(args, "require_segment_xp")
            and segment_requires_xp(args, current_level)
        )
        allow_shortage_recovery_fallback = (
            allow_lower_xp_target_plan
            and realm.key in {"alb", "hib"}
            and int(party_size or 0) <= 1
            and int(current_level or 0) == 7
        )
        allow_preferred_low_con_fallback = (
            (not allow_lower_xp_target_plan or allow_shortage_recovery_fallback)
            and not (realm.key == "hib" and party_size <= 1 and current_level in {5, 6})
            and not required_target_name
            and not explicit_xp_required
        )
        command += ["--prefer-target-name", prefer_target_name]
        if allow_preferred_low_con_fallback:
            command += ["--target-auto-lowest-visible-level"]
        if current_level >= 5 and allow_preferred_low_con_fallback:
            preferred_low_con_min_level = min_target
            if party_size <= 1 and current_level in {5, 6}:
                preferred_low_con_min_level = max(1, min_target - 1)
            command += [
                "--allow-preferred-low-con-fallback",
                "--preferred-low-con-min-level",
                str(preferred_low_con_min_level),
            ]
    if route.objective_adds:
        command += ["--objective-add-target-name", route.objective_adds]
    avoid_target_names = merge_target_name_csv(
        growth_avoid_targets_for_current_context(
            route,
            realm.key,
            current_level,
            party_size,
            allow_lower_xp_target_plan=allow_lower_xp_target_plan,
        ),
        failure_avoid_targets,
    )
    if avoid_target_names:
        command += ["--avoid-target-name", avoid_target_names]
    if party_size > 1:
        command += [
            "--party-assist-only",
            "--party-min-ready",
            str(party_min_ready(current_level, party_size, carry_tuning=party_carry_tuning)),
            "--party-form-up-delay",
            party_form_up_delay,
            "--party-form-up-timeout",
            growth_party_form_up_timeout(
                current_level,
                party_size,
                level50_boss_party=level50_boss_party,
                carry_tuning=party_carry_tuning,
            ),
            "--party-assist-attack-delay",
            growth_party_assist_attack_delay(current_level, party_size),
            "--party-ready-max-leader-distance",
            growth_party_ready_max_leader_distance(current_level, party_size, carry_tuning=party_carry_tuning),
            "--party-pre-pull-home-stop-distance",
            growth_party_pre_pull_home_stop_distance(current_level, party_size, carry_tuning=party_carry_tuning),
            "--party-mark-pull-engaged",
            "--party-pull-engage-distance",
            "1800",
            "--party-active-tank-reaggro-taunt-interval",
            "0.8",
        ]
        command += [
            "--party-rescue-aggro",
            "--party-rescue-before-objective-engaged",
            *([] if party_carry_tuning else ["--party-clear-objective-adds-before-engage"]),
            "--party-rescue-max-distance",
            "2200" if party_carry_tuning else "1400",
            "--party-rescue-engaged-distance",
            "650" if party_carry_tuning else "350",
            "--party-rescue-objective-max-distance",
            "2400" if party_carry_tuning else "1800",
            "--party-rescue-min-hold",
            "3" if party_carry_tuning else "4",
            "--party-rescue-max-age",
            party_rescue_max_age,
            "--party-rescue-assist-after",
            party_rescue_assist_after,
            "--party-rescue-emergency-assist-after",
            str(getattr(args, "party_rescue_emergency_assist_after", 2.0)),
            "--party-local-rescue-target",
            "--party-local-rescue-max-distance",
            "1200" if party_carry_tuning else "900",
            "--party-healer-local-rescue-health-percent",
            "45" if party_carry_tuning else "35",
        ]
        if not party_carry_tuning:
            command += [
                "--party-require-leader-engaged",
                "--party-block-solo-required-retaliation",
            ]
        else:
            command += [
                "--party-disable-required-home-anchor-defer",
                "--party-carry-counterattack-travel-aggro",
                "--companion-initial-command-mode",
                "attack",
                "--party-resurrect-interval",
                "0",
            ]
        if level50_boss_party:
            command += [
                "--party-encounter-mode",
                "boss",
                "--boss-ranged-safe-distance",
                "1000",
                "--boss-hazard-message-backoff-duration",
                "9",
                "--boss-hazard-message-backoff-distance",
                "2400",
                "--party-focus-target-backoff",
                "--party-focus-target-max-age",
                "6",
                "--party-focus-target-backoff-distance",
                "1400",
                "--party-melee-survival-health-percent",
                "45",
                "--party-melee-survival-resume-health-percent",
                "80",
                "--party-melee-survival-backoff-duration",
                "12",
                "--party-survival-death-count",
                "2",
                "--party-survival-death-window",
                "75",
                "--party-survival-active-tank-health-percent",
                "35",
                "--party-survival-backoff-distance",
                "1000",
                "--stop-after-required-target-removed",
            ]
        slot_rotations = early_growth_party_slot_rotations(current_level, party_size, carry_tuning=party_carry_tuning)
        if slot_rotations:
            command += [
                "--party-slot-rotations",
                slot_rotations,
            ]
    external_member_names = "|".join(
        part.strip()
        for part in re.split(r"[|,]", str(getattr(args, "party_external_member_names", "") or ""))
        if part.strip()
    )
    if external_member_names:
        command += [
            "--party-external-member-names",
            external_member_names,
        ]
    return command


def append_startup_teleport_command(
    command: list[str],
    args: argparse.Namespace,
    teleport_destination: str,
    *,
    realm: RealmProfile | None = None,
) -> None:
    if not teleport_destination:
        return

    command += [
        "--startup-teleporter-npc-name",
        getattr(
            args,
            "growth_teleporter_npc_name",
            "master visur,stor gothi annark,channeler glasny,teleporter,porter,텔레포터",
        ),
        "--startup-teleport-destination",
        teleport_destination,
        "--startup-teleport-warmup-delay",
        str(getattr(args, "growth_teleport_warmup_delay", 1.6)),
        "--startup-teleport-scan-seconds",
        str(getattr(args, "growth_teleport_scan_seconds", 1.0)),
        "--startup-teleport-approach-distance",
        str(getattr(args, "growth_teleport_approach_distance", 80.0)),
        "--startup-teleport-approach-timeout",
        str(getattr(args, "growth_teleport_approach_timeout", 20.0)),
        "--startup-teleport-wait-seconds",
        str(getattr(args, "growth_teleport_wait_seconds", 2.0)),
    ]
    if normalize_teleport_destination(teleport_destination) not in DIRECT_STARTUP_TELEPORT_DESTINATIONS:
        command += ["--startup-teleport-warmup-whisper", "towns"]
    if realm is not None:
        command += [
            "--startup-teleporter-home",
            startup_teleporter_home(realm),
            "--startup-teleporter-home-stop-distance",
            str(getattr(args, "growth_teleporter_home_stop_distance", 900.0)),
            "--startup-teleporter-home-timeout",
            str(getattr(args, "growth_teleporter_home_timeout", 90.0)),
        ]


def build_watcher_command(
    *,
    args: argparse.Namespace,
    realm: RealmProfile,
    watcher_csv: Path,
    case_dir: Path,
    segment_index: int,
    watcher_index: int,
    primary_account: str,
    current_level: int,
    path_graph: Path,
    party_size: int = 0,
    selected_route: RoutePoint | None = None,
) -> list[str]:
    metrics_csv = case_dir / f"segment-{segment_index:03d}-watcher-{watcher_index + 1:02d}-metrics.csv"
    report_md = case_dir / f"segment-{segment_index:03d}-watcher-{watcher_index + 1:02d}-report.md"
    trace_pattern = case_dir / "movement" / f"segment-{segment_index:03d}-{{username}}-{{round}}.jsonl"
    encounter_pattern = case_dir / "watcher-encounters" / f"segment-{segment_index:03d}-{{username}}-{{round}}.jsonl"
    trace_pattern.parent.mkdir(parents=True, exist_ok=True)
    encounter_pattern.parent.mkdir(parents=True, exist_ok=True)
    observer_follow_distance = watcher_observer_follow_distance(args)
    observer_max_distance = watcher_observer_max_distance(args)
    observer_movement_speed = watcher_observer_movement_speed(args)
    observer_home = watcher_observer_home_string(
        realm,
        current_level,
        party_size,
        observer_distance=observer_follow_distance,
        ground_z_offset=args.ground_z_offset,
    )
    command = [
        sys.executable,
        str(TOOLS / "behavior-dummy-client.py"),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--accounts",
        str(watcher_csv),
        "--concurrency",
        "1",
        "--rounds",
        "1",
        "--hold",
        str(args.segment_seconds),
        "--safe-exit-max-seconds",
        str(int(getattr(args, "safe_exit_max_seconds", GROWTH_SAFE_EXIT_MAX_SECONDS))),
        "--safe-exit-recent-damage-grace",
        str(int(getattr(args, "safe_exit_recent_damage_grace", GROWTH_SAFE_EXIT_RECENT_DAMAGE_GRACE))),
        "--ramp-up",
        str(max(0.0, float(args.ramp_up) + 1.0 + watcher_index * 0.2)),
        "--party-size",
        "1",
        "--login-retries",
        str(args.login_retries),
        "--login-retry-delay",
        str(args.login_retry_delay),
        "--ping-interval",
        "5",
        "--turn-interval",
        "0",
        "--realm-strategy",
        "fixed",
        "--api-port",
        str(args.api_port),
        "--player-level",
        str(current_level),
        "--move",
        "--smooth-movement",
        "--smooth-move-interval",
        str(args.smooth_move_interval),
        "--movement-speed",
        str(observer_movement_speed),
        "--movement-update-interval",
        str(args.smooth_move_interval),
        "--path-graph",
        str(path_graph),
        "--path-region",
        str(realm.region),
        "--path-last-mile-distance",
        str(max(float(args.path_last_mile_distance), observer_follow_distance)),
        "--path-node-arrival-distance",
        "80",
        "--path-max-height-delta",
        "900",
        "--path-waypoint-ground-z-skip-delta",
        "500",
        "--waypoints",
        observer_home,
        "--waypoint-mode",
        "loop",
        "--waypoint-advance-distance",
        "35",
        "--waypoint-stop-distance",
        "12",
        "--required-target-home",
        observer_home,
        "--required-target-home-stop-distance",
        str(observer_follow_distance),
        "--low-health-rest-percent",
        "70",
        "--low-health-rest-resume-percent",
        "88",
        "--low-health-rest-min",
        "6",
        "--low-health-rest-max",
        "14",
        "--flee-health-percent",
        "90",
        "--flee-pressure-health-percent",
        "99",
        "--flee-duration",
        "32",
        "--flee-step",
        "1200",
        "--flee-move-interval",
        "0.35",
        "--flee-movement-speed",
        str(observer_movement_speed),
        "--flee-use-sprint",
        "--flee-home",
        growth_flee_home_string(realm, current_level, party_size, ground_z_offset=args.ground_z_offset),
        "--flee-home-stop-distance",
        str(growth_flee_home_stop_distance(current_level)),
        "--flee-dynamic-safe-point",
        "--flee-safe-threat-radius",
        "6000",
        "--flee-safe-point-distance",
        "8000",
        "--flee-critical-health-percent",
        "90",
        "--flee-critical-safe-point-distance",
        "10000",
        "--flee-safe-api-scout",
        "--flee-safe-replan-damage-grace",
        "6",
        "--travel-aggro-clear-grace",
        "24",
        "--travel-aggro-avoid-seconds",
        "30",
        "--travel-aggro-avoid-radius",
        "5200",
        "--flee-town-health-percent",
        "10",
        "--follow-nearby-player",
        "--follow-player-name",
        character_name_from_account(primary_account),
        "--player-follow-interval",
        str(args.watcher_follow_interval),
        "--player-follow-distance",
        str(observer_follow_distance),
        "--player-follow-step",
        "240",
        "--follow-player-max-distance",
        str(observer_max_distance),
        "--follow-player-hold-allows-waypoint",
        "--player-state-max-age",
        "60",
        "--startup-command",
        "/sprint",
        "--startup-delay",
        "0.5",
        "--jitter",
        "0.05",
        "--tick",
        "0.05",
        "--metrics-csv",
        str(metrics_csv),
        "--report-md",
        str(report_md),
        "--trace-movement-log",
        str(trace_pattern),
        "--encounter-log",
        str(encounter_pattern),
        "--encounter-log-interval",
        str(args.encounter_log_interval),
        "--trace-observed-player-positions",
    ]
    if realm.ground_z_map:
        command += [
            "--ground-z-map",
            realm.ground_z_map,
            "--ground-z-offset",
            str(args.ground_z_offset),
            "--server-correction-smoothing",
        ]
    route = selected_route or select_route_point(realm, current_level, party_size)
    teleport_destination = nearest_teleport_destination(realm, route) if current_level >= 10 else route.teleport_destination
    append_startup_teleport_command(command, args, teleport_destination, realm=realm)
    if args.nav_api_url:
        command += ["--nav-api-url", args.nav_api_url]
    if args.live_api_url:
        command += ["--live-api-url", args.live_api_url]
    return command


def build_live_supervisor_command(
    args: argparse.Namespace,
    case_dir: Path,
    *,
    current_level: int | None = None,
    party_size: int = 0,
    realm_key: str = "",
    selected_route: RoutePoint | None = None,
) -> list[str]:
    max_engage = float(getattr(args, "live_supervisor_max_engage", 2800.0) or 2800.0)
    if current_level is not None:
        level_max_engage = growth_max_target_distance(args, current_level, party_size, realm_key, selected_route)
        if level_max_engage > 0.0:
            max_engage = level_max_engage
    return [
        sys.executable,
        str(TOOLS / "monitor-dummy-growth-live.py"),
        "--case-dir",
        str(case_dir),
        "--interval",
        str(getattr(args, "live_supervisor_interval", 3.0)),
        "--step",
        str(getattr(args, "live_supervisor_step", 350.0)),
        "--max-engage",
        str(max_engage),
        "--max-radius",
        str(getattr(args, "live_supervisor_max_radius", 5200.0)),
        "--hold",
        str(
            max(
                1.0,
                args.segment_seconds
                + getattr(args, "startup_delay", 0.0)
                + getattr(args, "ramp_up", 0.0)
                + GROWTH_STARTUP_TELEPORTER_HOME_TIMEOUT
                + GROWTH_SAFE_EXIT_MAX_SECONDS
                + 8.0,
            )
        ),
    ]


def command_for_metadata(command: list[str]) -> str:
    redacted: list[str] = []
    skip_next = False
    secret_flags = {"--db-password", "--password", "--api-password"}
    for index, part in enumerate(command):
        if skip_next:
            skip_next = False
            continue
        if part in secret_flags:
            redacted += [part, "***"]
            skip_next = True
        elif index > 0 and command[index - 1] in secret_flags:
            continue
        else:
            redacted.append(part)
    return shlex.join(redacted)


def build_failure_reproduction_command(
    args: argparse.Namespace,
    *,
    realm: RealmProfile,
    party_size: int,
    case_index: int,
    current_level: int,
    output_dir: Path,
) -> str:
    start = int(args.start) + case_index * int(args.start_stride)
    repro_dir = output_dir / f"failure-repro-{realm.key}-p{party_size}-l{current_level}"
    command = [
        sys.executable,
        str(TOOLS / "run-dummy-growth-suite.py"),
        "--host",
        str(args.host),
        "--port",
        str(args.port),
        "--api-port",
        str(args.api_port),
        "--nav-api-url",
        str(args.nav_api_url),
        "--db-host",
        str(args.db_host),
        "--db-port",
        str(args.db_port),
        "--db-name",
        str(args.db_name),
        "--db-user",
        str(args.db_user),
        "--db-password",
        str(args.db_password),
        "--template-account",
        str(args.template_account),
        "--template-character",
        str(args.template_character),
        "--password",
        str(args.password),
        "--realms",
        realm.key,
        "--party-sizes",
        str(party_size),
        "--start",
        str(start),
        "--start-stride",
        str(args.start_stride),
        "--segment-seconds",
        str(args.segment_seconds),
        "--max-segments",
        "1",
        "--max-level",
        str(min(50, current_level + 1)),
        "--reset-level",
        str(current_level),
        "--parallel-cases",
        "1",
        "--run-dir",
        str(repro_dir),
    ]
    return command_for_metadata(command)


def write_failure_reproduction_command(path: Path, command: str) -> None:
    path.write_text(command + "\n", encoding="utf-8")


def run_command(command: list[str], dry_run: bool) -> int:
    print(command_for_metadata(command))
    if dry_run:
        return 0
    process = subprocess.run(command)
    return process.returncode


def live_abort_path_for_commands(commands: list[list[str]]) -> Path | None:
    for command in commands:
        if not any(str(part).endswith("monitor-dummy-growth-live.py") for part in command):
            continue
        if "--case-dir" not in command:
            continue
        index = command.index("--case-dir")
        if index + 1 >= len(command):
            continue
        return Path(command[index + 1]) / "live-abort.json"
    return None


def read_live_abort_reason(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "live_abort"
    if not isinstance(payload, dict):
        return "live_abort"
    return str(payload.get("reason", "") or "live_abort")


def live_abort_bottleneck_reason(reason: str) -> str:
    token = re.sub(r"[^A-Za-z0-9_]+", "_", str(reason or "live_abort")).strip("_").lower()
    return f"live_abort_{token or 'live_abort'}"


def terminate_live_process(process: subprocess.Popen[object], *, timeout: float = 8.0) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def should_equip_level50_party_gear(args: argparse.Namespace, *, current_level: int, party_size: int) -> bool:
    return bool(
        getattr(args, "level50_party_gear", False)
        and party_size >= 2
        and current_level >= 50
    )


def should_equip_growth_party_carry_gear(args: argparse.Namespace, *, carry_level: int, party_size: int) -> bool:
    return bool(
        getattr(args, "growth_equip_party_carry_gear", False)
        and party_size >= 2
        and int(carry_level or 0) > 0
    )


def build_level50_party_gear_command(
    args: argparse.Namespace,
    accounts_csv: Path,
    *,
    template_level_cap: int = 0,
) -> list[str]:
    command = [
        sys.executable,
        str(TOOLS / "equip-dummy-boss-gear.py"),
    ]
    if getattr(args, "mysql_bin", None):
        command += ["--mysql-bin", str(args.mysql_bin)]
    command += [
        "--db-host",
        str(args.db_host),
        "--db-port",
        str(args.db_port),
        "--db-name",
        str(args.db_name),
        "--db-user",
        str(args.db_user),
        "--db-password",
        str(args.db_password),
    ]
    if int(template_level_cap or 0) > 0:
        command += ["--template-level-cap", str(int(template_level_cap))]
    command += [str(accounts_csv)]
    return command


def build_growth_party_carry_gear_command(args: argparse.Namespace, carry_accounts_csv: Path, carry_level: int) -> list[str]:
    return build_level50_party_gear_command(
        args,
        carry_accounts_csv,
        template_level_cap=max(1, int(carry_level or 1)),
    )


def run_commands_concurrently(commands: list[list[str]], dry_run: bool) -> int:
    if dry_run or len(commands) <= 1:
        rc = 0
        for command in commands:
            rc = max(rc, run_command(command, dry_run))
        return rc

    for command in commands:
        print(command_for_metadata(command))

    processes = [subprocess.Popen(command) for command in commands]
    live_abort_path = live_abort_path_for_commands(commands)
    live_abort_handled = False
    rc = 0
    while True:
        all_done = True
        for process in processes:
            current_rc = process.poll()
            if current_rc is None:
                all_done = False
                continue
            rc = max(rc, current_rc)
        if live_abort_path is not None and not live_abort_handled and live_abort_path.exists():
            reason = read_live_abort_reason(live_abort_path)
            print(f"live supervisor early abort: reason={reason} path={live_abort_path}")
            for process in processes:
                terminate_live_process(process)
                current_rc = process.poll()
                if current_rc is not None:
                    rc = max(rc, current_rc)
            rc = max(rc, 1)
            live_abort_handled = True
            all_done = True
        if all_done:
            break
        time.sleep(0.5)
    return rc


def trace_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event") not in {"move_step", "send_position", "ground_z_sample"}:
            continue
        if all(key in row for key in ("x", "y", "z")):
            rows.append(row)
    return rows


def jsonl_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def numeric(row: dict[str, object], key: str) -> float:
    value = row.get(key, 0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def movement_step_rows(path: Path) -> list[dict[str, object]]:
    return [row for row in trace_rows(path) if row.get("event") == "move_step"]


def movement_pair_step_rows(path: Path) -> list[dict[str, object]]:
    rows = jsonl_rows(path)
    last_startup_teleport_index = -1
    for index, row in enumerate(rows):
        if row.get("event") == "startup_teleport_sync":
            last_startup_teleport_index = index
    return [
        row
        for index, row in enumerate(rows)
        if index > last_startup_teleport_index
        and row.get("event") == "move_step"
        and all(key in row for key in ("x", "y", "z"))
    ]


def watcher_pair_observer_rows(path: Path) -> list[dict[str, object]]:
    rows = movement_pair_step_rows(path)
    if rows:
        return rows

    all_rows = jsonl_rows(path)
    last_startup_teleport_index = -1
    for index, row in enumerate(all_rows):
        if row.get("event") == "startup_teleport_sync":
            last_startup_teleport_index = index
    return [
        row
        for index, row in enumerate(all_rows)
        if index > last_startup_teleport_index
        and row.get("event") in {"send_position", "observe_self_position"}
        and all(key in row for key in ("x", "y", "z"))
    ]


def paired_movement_rows(
    primary: list[dict[str, object]],
    watcher: list[dict[str, object]],
) -> list[tuple[dict[str, object], dict[str, object]]]:
    if not primary or not watcher:
        return []

    if not all("t" in row for row in primary + watcher):
        return list(zip(primary, watcher))

    pairs: list[tuple[dict[str, object], dict[str, object]]] = []
    watcher_index = 0
    for left in primary:
        left_t = numeric(left, "t")
        while watcher_index + 1 < len(watcher):
            current_delta = abs(numeric(watcher[watcher_index], "t") - left_t)
            next_delta = abs(numeric(watcher[watcher_index + 1], "t") - left_t)
            if next_delta > current_delta:
                break
            watcher_index += 1
        pairs.append((left, watcher[watcher_index]))
    return pairs


XY_STATUS_RECOVERY_STATES = {"DropAggroAndRecover", "RestRecover", "DeadReleaseRecover", "ReturnToObjective"}


def primary_behavior_state_timeline(path: Path | None) -> list[tuple[float, str]]:
    if path is None:
        return []

    timeline: list[tuple[float, str]] = []
    for row in jsonl_rows(path):
        state = str(row.get("behavior_state", "") or "")
        timestamp = numeric(row, "t")
        if state and timestamp > 0.0:
            timeline.append((timestamp, state))
    timeline.sort(key=lambda item: item[0])
    return timeline


def behavior_state_at(timeline: list[tuple[float, str]], timestamp: float) -> str:
    state = ""
    for event_time, event_state in timeline:
        if event_time > timestamp:
            break
        state = event_state
    return state


def xy_status_deltas(
    pairs: list[tuple[dict[str, object], dict[str, object]]],
    raw_xy_deltas: list[float],
    *,
    primary_encounter_path: Path | None,
) -> list[float]:
    timeline = primary_behavior_state_timeline(primary_encounter_path)
    if not timeline:
        return raw_xy_deltas

    filtered: list[float] = []
    for (left, _right), xy_delta in zip(pairs, raw_xy_deltas):
        state = behavior_state_at(timeline, numeric(left, "t"))
        if state in XY_STATUS_RECOVERY_STATES:
            continue
        filtered.append(xy_delta)

    return filtered or raw_xy_deltas


def movement_anomaly_summary(path: Path, *, rewind_warn_distance: float) -> dict[str, object]:
    rows = jsonl_rows(path)
    max_step = 0.0
    large_steps = 0
    reverse_spikes = 0
    previous_dx = 0.0
    previous_dy = 0.0
    previous_distance = 0.0
    move_samples = 0
    previous_move: dict[str, object] | None = None

    for current in rows:
        event = str(current.get("event", ""))
        if event == "startup_teleport_sync":
            previous_move = None
            previous_dx = 0.0
            previous_dy = 0.0
            previous_distance = 0.0
            continue
        if event != "move_step":
            continue

        move_samples += 1
        if previous_move is None:
            previous_move = current
            continue

        before = previous_move
        dx = numeric(current, "x") - numeric(before, "x")
        dy = numeric(current, "y") - numeric(before, "y")
        distance = math.sqrt(dx * dx + dy * dy)
        max_step = max(max_step, distance)
        if distance > rewind_warn_distance:
            large_steps += 1
        if distance > rewind_warn_distance * 0.5 and previous_distance > rewind_warn_distance * 0.5:
            if dx * previous_dx + dy * previous_dy < 0:
                reverse_spikes += 1
        previous_dx = dx
        previous_dy = dy
        previous_distance = distance
        previous_move = current

    return {
        "move_samples": move_samples,
        "max_step_distance": max_step,
        "large_step_events": large_steps,
        "reverse_spike_events": reverse_spikes,
    }


def primary_encounter_anomaly_summary(path: Path) -> dict[str, object]:
    rows = jsonl_rows(path)
    idle_ready_ticks = 0
    scan_empty_visible_events = 0
    scan_empty_eligible_zero_events = 0
    reject_reasons: dict[str, int] = {}
    last_finish_at: float | None = None
    max_combat_gap = 0.0
    last_event_at = 0.0
    objective_satisfied = False

    for row in rows:
        event = str(row.get("event", ""))
        timestamp = numeric(row, "t")
        if timestamp > 0:
            last_event_at = timestamp

        if event == "combat_finish" and str(row.get("outcome", "") or "") == "target_removed":
            objective_satisfied = True
            last_finish_at = timestamp
            continue
        if objective_satisfied and event in {"encounter_tick", "hunter_target_scan_empty"}:
            continue

        if event == "encounter_tick":
            current_target = int(numeric(row, "current_target"))
            health = numeric(row, "health_percent")
            is_dead = bool(row.get("is_dead", False))
            if current_target <= 0 and health >= 80 and not is_dead:
                idle_ready_ticks += 1
        elif event == "hunter_target_scan_empty":
            visible = int(numeric(row, "hunter_visible_npcs"))
            eligible = int(numeric(row, "hunter_eligible_npcs"))
            if visible > 0:
                scan_empty_visible_events += 1
            if visible > 0 and eligible <= 0:
                scan_empty_eligible_zero_events += 1
                counts = row.get("hunter_reject_counts", {})
                if isinstance(counts, dict):
                    for reason, value in counts.items():
                        if reason in {"visible", "eligible"}:
                            continue
                        try:
                            reject_reasons[reason] = reject_reasons.get(reason, 0) + int(value)
                        except (TypeError, ValueError):
                            continue
        elif event == "combat_finish":
            last_finish_at = timestamp
        elif event == "combat_start" and last_finish_at is not None and timestamp >= last_finish_at:
            max_combat_gap = max(max_combat_gap, timestamp - last_finish_at)
            last_finish_at = None

    top_reason = ""
    if reject_reasons:
        top_reason = max(reject_reasons.items(), key=lambda item: item[1])[0]

    reasons: list[str] = []
    critical_reasons: list[str] = []
    if scan_empty_eligible_zero_events:
        reasons.append(f"scan_empty:{top_reason or 'unknown'}")
        if scan_empty_eligible_zero_events >= 3:
            critical_reasons.append(f"scan_empty:{top_reason or 'unknown'}")
    if max_combat_gap >= 10.0:
        reasons.append("combat_gap")
    if idle_ready_ticks >= 3 and scan_empty_visible_events:
        reasons.append("idle_ready")
        if scan_empty_visible_events >= 3:
            critical_reasons.append("idle_ready")

    return {
        "primary_idle_ready_ticks": idle_ready_ticks,
        "primary_scan_empty_visible_events": scan_empty_visible_events,
        "primary_scan_empty_eligible_zero_events": scan_empty_eligible_zero_events,
        "primary_scan_empty_top_reason": top_reason,
        "primary_combat_gap_max_seconds": max_combat_gap,
        "primary_anomaly_status": "critical" if critical_reasons else "warn" if reasons else "ok",
        "primary_anomaly_reason": ";".join(reasons),
    }


def preferred_target_tokens(prefer_target_name: str) -> list[str]:
    return [token.strip().lower() for token in prefer_target_name.split(",") if token.strip()]


def normalize_target_match_text(value: str) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"^[^0-9a-z가-힣']+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def target_name_matches_any(name: str, tokens: list[str]) -> bool:
    normalized = normalize_target_match_text(name)
    if not normalized:
        return False
    for token in tokens:
        normalized_token = normalize_target_match_text(token)
        if not normalized_token:
            continue
        if normalized_token in normalized:
            return True
        if len(normalized) >= 4 and normalized in normalized_token:
            return True
    return False


def target_name_csv_matches_any(value: str, tokens: list[str]) -> bool:
    return any(
        target_name_matches_any(part.strip(), tokens)
        for part in str(value or "").split(",")
        if part.strip()
    )


def primary_behavior_anomaly_summary(path: Path, *, prefer_target_name: str = "") -> dict[str, object]:
    rows = jsonl_rows(path)
    prefer_tokens = preferred_target_tokens(prefer_target_name)
    reasons: set[str] = set()
    last_flee_at: float | None = None
    last_flee_x = 0.0
    last_flee_y = 0.0
    flee_window_recovered = False
    flee_window_active_threat_observed = False
    flee_window_aggro_not_dropped = False
    flee_window_too_short = False
    combat_attempts_by_target: dict[str, int] = {}
    weak_flee_finishes_by_target: dict[str, int] = {}
    target_removed_finishes_by_target: dict[str, int] = {}
    last_target_removed_finish_at: float | None = None
    post_target_removed_pressure_pending = False
    post_removed_pressure_window = 45.0

    for row in rows:
        event = str(row.get("event", ""))
        timestamp = numeric(row, "t")
        target_name = str(row.get("target_name") or row.get("active_target_name") or "")

        if event == "combat_start" and target_name:
            last_target_removed_finish_at = None
            post_target_removed_pressure_pending = False
            normalized_target = target_name.lower()
            combat_attempts_by_target[normalized_target] = combat_attempts_by_target.get(normalized_target, 0) + 1

        elif event == "combat_finish":
            outcome = str(row.get("outcome", ""))
            duration = numeric(row, "duration_seconds")
            damage_done = numeric(row, "damage_done")
            damage_taken = numeric(row, "damage_taken")
            if outcome == "target_removed":
                last_target_removed_finish_at = timestamp
                if target_name:
                    normalized_target = target_name.lower()
                    target_removed_finishes_by_target[normalized_target] = (
                        target_removed_finishes_by_target.get(normalized_target, 0) + 1
                    )
            if (
                target_name
                and outcome in {"flee", "target_timeout", "target_home_leash"}
                and duration >= 8.0
                and damage_taken >= 40.0
                and damage_done <= max(12.0, damage_taken * 0.35)
            ):
                normalized_target = target_name.lower()
                weak_flee_finishes_by_target[normalized_target] = weak_flee_finishes_by_target.get(normalized_target, 0) + 1

        elif event == "combat_start":
            last_target_removed_finish_at = None
            post_target_removed_pressure_pending = False

        elif event == "flee_start":
            if last_target_removed_finish_at is not None and timestamp - last_target_removed_finish_at <= post_removed_pressure_window:
                post_target_removed_pressure_pending = True
            last_flee_at = timestamp
            last_flee_x = numeric(row, "x")
            last_flee_y = numeric(row, "y")
            flee_window_recovered = False
            flee_window_active_threat_observed = False
            flee_window_aggro_not_dropped = False
            flee_window_too_short = False

        elif event == "flee_threat_pressure" and last_flee_at is not None:
            age = timestamp - last_flee_at
            threat_target = str(row.get("flee_threat_target", ""))
            character = str(row.get("character", ""))
            active = bool(row.get("flee_threat_active") or row.get("flee_threat_has_aggro") or row.get("flee_threat_in_combat"))
            if active and threat_target and character and threat_target.lower() == character.lower() and age >= 12.0:
                flee_window_active_threat_observed = True
                threat_distance = numeric(row, "flee_threat_distance")
                if threat_distance <= 1200.0 or age >= 48.0:
                    flee_window_aggro_not_dropped = True
            if active and age >= 12.0:
                threat_distance = numeric(row, "flee_threat_distance")
                dx = numeric(row, "x") - last_flee_x
                dy = numeric(row, "y") - last_flee_y
                flee_distance = math.sqrt(dx * dx + dy * dy)
                if threat_distance <= 1200.0 or flee_distance < 1600.0:
                    flee_window_too_short = True

        elif event == "flee_recovered" and last_flee_at is not None:
            flee_window_recovered = True
            post_target_removed_pressure_pending = False

        elif event == "flee_finished" and last_flee_at is not None:
            if not flee_window_recovered:
                if flee_window_aggro_not_dropped or flee_window_active_threat_observed:
                    reasons.add("aggro_not_dropped")
                if flee_window_too_short:
                    reasons.add("flee_too_short")
            last_flee_at = None
            flee_window_recovered = False
            flee_window_active_threat_observed = False
            flee_window_aggro_not_dropped = False
            flee_window_too_short = False

        elif event == "low_health_rest":
            if row.get("flee_threat_active") or row.get("flee_threat_has_aggro") or row.get("flee_threat_target"):
                if last_target_removed_finish_at is not None and timestamp - last_target_removed_finish_at <= post_removed_pressure_window:
                    reasons.add("post_target_removed_pressure")
                reasons.add("unsafe_rest")
            elif last_flee_at is not None:
                last_flee_at = None
                flee_window_recovered = False
                flee_window_active_threat_observed = False
                flee_window_aggro_not_dropped = False
                flee_window_too_short = False
                post_target_removed_pressure_pending = False
            else:
                post_target_removed_pressure_pending = False

        elif event in {
            "required_target_complete",
            "required_target_complete_pending_safe_exit",
            "required_target_complete_shared",
        }:
            post_target_removed_pressure_pending = False

        elif event == "safe_exit_complete":
            deadline_reached = str(row.get("safe_exit_deadline_reached", "")).lower() in {"1", "true", "yes"} or bool(
                row.get("safe_exit_deadline_reached")
            )
            completed_recovered = str(row.get("safe_exit_deadline_completed_recovered", "")).lower() in {
                "1",
                "true",
                "yes",
            } or bool(row.get("safe_exit_deadline_completed_recovered"))
            if deadline_reached and not completed_recovered:
                reasons.add("safe_exit_deadline")
            else:
                post_target_removed_pressure_pending = False

    if post_target_removed_pressure_pending:
        reasons.add("post_target_removed_pressure")

    if last_flee_at is not None and not flee_window_recovered:
        if flee_window_aggro_not_dropped:
            reasons.add("aggro_not_dropped")
        if flee_window_too_short:
            reasons.add("flee_too_short")

    for target_name, weak_finishes in weak_flee_finishes_by_target.items():
        successful_finishes = target_removed_finishes_by_target.get(target_name, 0)
        repeated_failed_attempts = weak_finishes >= 2
        unresolved_failed_retries = weak_finishes >= 1 and combat_attempts_by_target.get(target_name, 0) >= 2 and successful_finishes <= 0
        if repeated_failed_attempts or unresolved_failed_retries:
            reasons.add("target_stuck")
        if prefer_tokens and weak_finishes >= 1 and combat_attempts_by_target.get(target_name, 0) >= 2:
            if not target_name_matches_any(target_name, prefer_tokens):
                reasons.add("bad_target_choice")

    status = "critical" if reasons else "ok"
    return {
        "primary_behavior_anomaly_status": status,
        "primary_behavior_anomaly_reason": ";".join(sorted(reasons)),
        "primary_behavior_bad_target_choice": 1 if "bad_target_choice" in reasons else 0,
        "primary_behavior_aggro_not_dropped": 1 if "aggro_not_dropped" in reasons else 0,
        "primary_behavior_flee_too_short": 1 if "flee_too_short" in reasons else 0,
        "primary_behavior_target_stuck": 1 if "target_stuck" in reasons else 0,
        "primary_behavior_unsafe_rest": 1 if "unsafe_rest" in reasons else 0,
        "primary_behavior_safe_exit_deadline": 1 if "safe_exit_deadline" in reasons else 0,
        "primary_behavior_post_target_removed_pressure": 1 if "post_target_removed_pressure" in reasons else 0,
    }


def empty_primary_encounter_anomaly_summary() -> dict[str, object]:
    return {
        "primary_idle_ready_ticks": 0,
        "primary_scan_empty_visible_events": 0,
        "primary_scan_empty_eligible_zero_events": 0,
        "primary_scan_empty_top_reason": "",
        "primary_combat_gap_max_seconds": 0.0,
        "primary_anomaly_status": "ok",
        "primary_anomaly_reason": "",
    }


def empty_primary_behavior_anomaly_summary() -> dict[str, object]:
    return {
        "primary_behavior_anomaly_status": "ok",
        "primary_behavior_anomaly_reason": "",
        "primary_behavior_bad_target_choice": 0,
        "primary_behavior_aggro_not_dropped": 0,
        "primary_behavior_flee_too_short": 0,
        "primary_behavior_target_stuck": 0,
        "primary_behavior_unsafe_rest": 0,
        "primary_behavior_safe_exit_deadline": 0,
        "primary_behavior_post_target_removed_pressure": 0,
    }


def ground_z_deltas(rows: list[dict[str, object]]) -> list[float]:
    deltas: list[float] = []
    for row in rows:
        if row.get("event") != "move_step" or "sampled_ground_z" not in row:
            continue
        try:
            z = float(row.get("z", ""))
            sampled_ground_z = float(row.get("sampled_ground_z", ""))
        except (TypeError, ValueError):
            continue
        deltas.append(abs(z - sampled_ground_z))
    return deltas


def compare_watcher_pair(
    primary_path: Path,
    watcher_path: Path,
    *,
    primary_encounter_path: Path | None = None,
    prefer_target_name: str = "",
    z_warn_delta: float,
    xy_warn_delta: float,
    rewind_warn_distance: float,
    z_compare_xy_distance: float,
) -> dict[str, object]:
    primary_all = movement_step_rows(primary_path)
    watcher_all = movement_step_rows(watcher_path)
    primary = movement_pair_step_rows(primary_path)
    watcher = watcher_pair_observer_rows(watcher_path)
    primary_ground_deltas = ground_z_deltas(primary_all)
    watcher_ground_deltas = ground_z_deltas(watcher_all)
    all_ground_deltas = primary_ground_deltas + watcher_ground_deltas
    pairs = paired_movement_rows(primary, watcher)
    samples = len(pairs)
    z_deltas: list[float] = []
    xy_deltas: list[float] = []

    for left, right in pairs:
        dx = numeric(left, "x") - numeric(right, "x")
        dy = numeric(left, "y") - numeric(right, "y")
        dz = numeric(left, "z") - numeric(right, "z")
        xy_deltas.append(math.sqrt(dx * dx + dy * dy))
        z_deltas.append(abs(dz))

    close_z_deltas = [
        z_delta
        for z_delta, xy_delta in zip(z_deltas, xy_deltas)
        if xy_delta <= z_compare_xy_distance
    ]

    all_rows = trace_rows(primary_path) + trace_rows(watcher_path)
    z_source_counts: dict[str, int] = {}
    for row in all_rows:
        source = str(row.get("z_source", ""))
        if source:
            z_source_counts[source] = z_source_counts.get(source, 0) + 1

    primary_anomaly = movement_anomaly_summary(primary_path, rewind_warn_distance=rewind_warn_distance)
    watcher_anomaly = movement_anomaly_summary(watcher_path, rewind_warn_distance=rewind_warn_distance)
    max_z = max(z_deltas) if z_deltas else 0.0
    max_close_z = max(close_z_deltas) if close_z_deltas else 0.0
    max_ground_z = max(all_ground_deltas) if all_ground_deltas else 0.0
    max_xy = max(xy_deltas) if xy_deltas else 0.0
    status_xy_deltas = xy_status_deltas(
        pairs,
        xy_deltas,
        primary_encounter_path=primary_encounter_path,
    )
    max_status_xy = max(status_xy_deltas) if status_xy_deltas else 0.0
    rewind_events = (
        int(primary_anomaly["large_step_events"])
        + int(primary_anomaly["reverse_spike_events"])
        + int(watcher_anomaly["large_step_events"])
        + int(watcher_anomaly["reverse_spike_events"])
    )
    encounter_anomaly = (
        primary_encounter_anomaly_summary(primary_encounter_path)
        if primary_encounter_path is not None
        else empty_primary_encounter_anomaly_summary()
    )
    behavior_anomaly = (
        primary_behavior_anomaly_summary(primary_encounter_path, prefer_target_name=prefer_target_name)
        if primary_encounter_path is not None
        else empty_primary_behavior_anomaly_summary()
    )
    return {
        "samples": samples,
        "primary_moves": len(primary_all),
        "watcher_moves": len(watcher_all),
        "avg_abs_z_delta": sum(z_deltas) / len(z_deltas) if z_deltas else 0.0,
        "max_abs_z_delta": max_z,
        "close_xy_samples": len(close_z_deltas),
        "max_close_abs_z_delta": max_close_z,
        "max_ground_abs_z_delta": max_ground_z,
        "ground_z_delta_samples": len(all_ground_deltas),
        "avg_xy_delta": sum(xy_deltas) / len(xy_deltas) if xy_deltas else 0.0,
        "max_xy_delta": max_xy,
        "ground_z_sample_events": sum(1 for row in all_rows if row.get("event") == "ground_z_sample"),
        "ground_z_sampler_moves": z_source_counts.get("ground_z_sampler", 0),
        "interpolated_moves": z_source_counts.get("interpolated", 0),
        "primary_max_step_distance": primary_anomaly["max_step_distance"],
        "watcher_max_step_distance": watcher_anomaly["max_step_distance"],
        "rewind_events": rewind_events,
        "watcher_status": "warn" if len(primary_all) > 0 and (len(watcher) == 0 or samples == 0 or not close_z_deltas) else "ok",
        "z_status": "warn" if (max_ground_z if all_ground_deltas else max_close_z) > z_warn_delta else "ok",
        "xy_status": "warn" if max_status_xy > xy_warn_delta else "ok",
        "rewind_status": "warn" if rewind_events else "ok",
        **encounter_anomaly,
        **behavior_anomaly,
    }


def write_watcher_summary(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "case",
        "segment",
        "primary_account",
        "watcher_account",
        "samples",
        "primary_moves",
        "watcher_moves",
        "avg_abs_z_delta",
        "max_abs_z_delta",
        "close_xy_samples",
        "max_close_abs_z_delta",
        "max_ground_abs_z_delta",
        "ground_z_delta_samples",
        "avg_xy_delta",
        "max_xy_delta",
        "ground_z_sample_events",
        "ground_z_sampler_moves",
        "interpolated_moves",
        "primary_max_step_distance",
        "watcher_max_step_distance",
        "rewind_events",
        "watcher_status",
        "z_status",
        "xy_status",
        "rewind_status",
        "primary_idle_ready_ticks",
        "primary_scan_empty_visible_events",
        "primary_scan_empty_eligible_zero_events",
        "primary_scan_empty_top_reason",
        "primary_combat_gap_max_seconds",
        "primary_anomaly_status",
        "primary_anomaly_reason",
        "primary_behavior_anomaly_status",
        "primary_behavior_anomaly_reason",
        "primary_behavior_bad_target_choice",
        "primary_behavior_aggro_not_dropped",
        "primary_behavior_flee_too_short",
        "primary_behavior_target_stuck",
        "primary_behavior_unsafe_rest",
        "primary_behavior_safe_exit_deadline",
        "primary_behavior_post_target_removed_pressure",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, object]] = []
    if path.exists():
        with path.open(encoding="utf-8", newline="") as handle:
            existing = list(csv.DictReader(handle))
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in existing + rows:
            writer.writerow(row)


def empty_metric_summary() -> dict[str, float]:
    summary = {
        "metric_rows": 0,
        "ok_rows": 0,
        "actions": 0,
        "elapsed_seconds": 0.0,
        "combat_engagements": 0,
        "target_removed": 0,
        "player_deaths": 0,
        "target_timeouts": 0,
        "combat_failures": 0,
        "server_los_failures": 0,
        "target_home_leashes": 0,
        "movement_failures": 0,
        "loot_acquired": 0,
        "damage_done": 0,
        "damage_taken": 0,
        "healing_done": 0,
        "healing_received": 0,
        "target_removed_no_reward": 0,
        "startup_merchant_sell": 0,
        "startup_merchant_buy": 0,
        "startup_merchant_equip": 0,
        "startup_merchant_npc_missing": 0,
        "startup_merchant_too_far": 0,
        "startup_service_dialog_settle": 0,
        "startup_service_equip": 0,
        "startup_service_equip_skipped_party_slot": 0,
    }
    for field in RANDOM_LOOT_FIELDS:
        summary[field] = 0
    return summary


def add_loot_tier_metrics_from_metric_row(summary: dict[str, float], row: dict[str, str]) -> None:
    for tier_label, field_name in RANDOM_LOOT_TIER_FIELDS.items():
        value = to_int(row.get(f"action_loot_tier_{tier_label}"))
        summary[field_name] = summary.get(field_name, 0) + value
        summary["random_loot_total"] = summary.get("random_loot_total", 0) + value


COMBAT_FAILURE_OUTCOMES = {"server_los_failure", "target_timeout", "target_home_leash"}


def aggregate_combat_metrics(path: Path) -> dict[str, int]:
    summary = {
        "combat_failures": 0,
        "server_los_failures": 0,
        "target_home_leashes": 0,
    }
    if not path.exists():
        return summary

    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            outcome = str(row.get("outcome", "") or "").strip()
            if outcome in COMBAT_FAILURE_OUTCOMES:
                summary["combat_failures"] += 1
            if outcome == "server_los_failure":
                summary["server_los_failures"] += 1
            elif outcome == "target_home_leash":
                summary["target_home_leashes"] += 1
    return summary


def aggregate_metrics(path: Path) -> dict[str, float]:
    summary = empty_metric_summary()
    if not path.exists():
        return summary
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            summary["metric_rows"] += 1
            if row.get("ok", "").lower() in {"1", "true", "yes"}:
                summary["ok_rows"] += 1
            summary["elapsed_seconds"] += float(row.get("elapsed_seconds") or 0.0)
            for key in (
                "actions",
                "combat_engagements",
                "target_removed",
                "player_deaths",
                "target_timeouts",
                "movement_failures",
                "loot_acquired",
                "damage_done",
                "damage_taken",
                "healing_done",
                "healing_received",
                "target_removed_no_reward",
                "startup_merchant_sell",
                "startup_merchant_buy",
                "startup_merchant_equip",
                "startup_merchant_npc_missing",
                "startup_merchant_too_far",
                "startup_service_dialog_settle",
                "startup_service_equip",
                "startup_service_equip_skipped_party_slot",
            ):
                summary[key] += to_int(row.get(key) if row.get(key) is not None else row.get(f"action_{key}"))
            add_loot_tier_metrics_from_metric_row(summary, row)
    return summary


def segment_regression_passed(metrics: dict[str, object], *, require_kill: bool) -> bool:
    target_removed = to_int(metrics.get("target_removed"))
    if to_int(metrics.get("player_deaths")) > 0 and target_removed <= 0:
        return False
    if to_int(metrics.get("movement_failures")) > 0 and require_kill and target_removed <= 0:
        return False
    if to_int(metrics.get("target_timeouts")) > 0:
        return False
    combat_failures = to_int(metrics.get("combat_failures"))
    if target_removed > 0:
        recovered_failures = to_int(metrics.get("server_los_failures")) + to_int(metrics.get("target_home_leashes"))
        combat_failures = max(0, combat_failures - recovered_failures)
    if combat_failures > 0:
        return False
    if require_kill and target_removed <= 0:
        return False
    return True


def segment_requires_kill(args: argparse.Namespace, current_level: int) -> bool:
    if not bool(getattr(args, "require_segment_kill", True)):
        return False
    return int(current_level) != 5


def segment_requirement_explicit(args: argparse.Namespace, name: str) -> bool:
    return name in set(getattr(args, "explicit_options", set()) or set())


def segment_xp_regression_passed(xp_effective_delta: int | float, *, require_xp: bool) -> bool:
    if not require_xp:
        return True
    return to_int(xp_effective_delta) > 0


def segment_account_xp_regression_passed(
    xp_effective_by_account: dict[str, int | float],
    *,
    require_xp: bool,
) -> bool:
    if not require_xp:
        return True
    return all(to_int(xp) > 0 for xp in xp_effective_by_account.values())


def segment_requires_xp(args: argparse.Namespace, current_level: int) -> bool:
    if not bool(getattr(args, "require_segment_xp", True)):
        return False
    level = int(current_level)
    if level == 5:
        return False
    if level >= 50:
        return False
    return True


def growth_item_plans_have_merchant_transaction(item_plans: dict[str, GrowthItemPlan]) -> bool:
    return any(plan.buy_slots or plan.sell_slots for plan in item_plans.values())


def growth_item_plans_have_merchant_buy(item_plans: dict[str, GrowthItemPlan]) -> bool:
    return any(plan.buy_slots for plan in item_plans.values())


def growth_item_plans_have_executable_merchant_transaction(
    item_plans: dict[str, GrowthItemPlan],
    *,
    party_size: int,
    planned_party_merchant_maps: bool = False,
) -> bool:
    if not growth_item_plans_have_merchant_transaction(item_plans):
        return False
    return int(party_size or 0) <= 1 or bool(planned_party_merchant_maps)


def growth_party_share_status(plan: GrowthItemPlan) -> str:
    if plan.party_share_executed_slots and plan.party_share_failed_slots:
        return "partial_db_transfer"
    if plan.party_share_executed_slots:
        return "executed_db_transfer"
    if plan.party_share_received_slots:
        return "received_db_transfer"
    if plan.party_share_failed_slots:
        return "failed_db_transfer"
    if plan.party_share_slots:
        return "pending_hold_not_traded"
    return "none"


def growth_merchant_transaction_status(
    plan: GrowthItemPlan,
    metrics: dict[str, float],
    *,
    party_size: int,
) -> str:
    if int(plan.buy_shortage_copper or 0) > 0:
        return "shortage"
    if plan.buy_reason == "party_merchant_routing_pending":
        return "party_pending_not_executed"
    if not (plan.sell_slots or plan.buy_slots or plan.buy_inventory_slots):
        return "none"
    merchant_actions = growth_merchant_action_count(metrics)
    if merchant_actions > 0:
        return "executed_actions_seen"
    if plan.merchant_npc_name:
        return "planned_no_action_seen"
    return "planned_missing_merchant"


def growth_merchant_action_count(metrics: dict[str, float]) -> int:
    return (
        to_int(metrics.get("startup_merchant_sell"))
        + to_int(metrics.get("startup_merchant_buy"))
        + to_int(metrics.get("startup_merchant_equip"))
    )


def growth_merchant_transaction_regression_passed(
    metrics: dict[str, float],
    *,
    planned_merchant_execution: bool,
) -> bool:
    if not planned_merchant_execution:
        return True
    return growth_merchant_action_count(metrics) > 0


def growth_data_integrity_flags(
    args: argparse.Namespace,
    plan: GrowthItemPlan,
    *,
    party_size: int,
    promoted_count: int,
    equipped_growth_party_carry_gear: bool,
    equipped_growth_checkpoint_gear: bool,
    equipped_level50_party_gear: bool,
) -> str:
    flags: list[str] = []
    if not bool(getattr(args, "no_starter_equipment", False)):
        flags.append("starter_equipment_allowed")
    if int(promoted_count or 0) > 0:
        flags.append("class_promotion_or_weapon_db_update")
    if equipped_growth_party_carry_gear:
        flags.append("injected_carry_gear")
    if equipped_growth_checkpoint_gear:
        flags.append("injected_checkpoint_gear")
    if equipped_level50_party_gear:
        flags.append("injected_level50_party_gear")
    if plan.party_share_slots and not plan.party_share_executed_slots:
        flags.append("party_share_pending_hold")
    if plan.party_share_executed_slots or plan.party_share_received_slots:
        flags.append("party_share_db_transfer")
    if int(party_size or 0) > 1 and (plan.sell_slots or plan.buy_slots) and not plan.merchant_npc_name:
        flags.append("party_merchant_pending")
    return ",".join(flags)


def growth_bottleneck_reason(
    plan: GrowthItemPlan,
    inventory_delta: dict[str, int],
    metrics: dict[str, float],
    *,
    party_size: int,
    xp_effective_delta: int | float,
    effective_death_delta: int,
    planned_merchant_transaction: bool,
) -> str:
    reasons: list[str] = []
    buy_shortage = to_int(plan.buy_shortage_copper)
    target_removed = to_int(metrics.get("target_removed"))
    combat_engagements = to_int(metrics.get("combat_engagements"))
    loot_acquired = to_int(metrics.get("loot_acquired"))
    damage_done = to_int(metrics.get("damage_done"))
    damage_taken = to_int(metrics.get("damage_taken"))
    attack_actions = (
        to_int(metrics.get("action_attack_on"))
        + to_int(metrics.get("action_attack_off"))
        + to_int(metrics.get("action_attack_target_in_view_update"))
        + to_int(metrics.get("action_attack_target_in_view_prime"))
    )
    sellable_value_after = to_int(inventory_delta.get("sellable_junk_value_copper_after"))
    zero_value_junk_after = to_int(inventory_delta.get("zero_value_junk_items_after"))
    target_removed_no_reward = to_int(metrics.get("target_removed_no_reward"))
    effective_target_removed = target_removed + target_removed_no_reward
    xp_progress_made = to_int(xp_effective_delta) > 0
    merchant_action_seen = any(
        to_int(metrics.get(key)) > 0
        for key in (
            "startup_merchant_sell",
            "startup_merchant_buy",
            "startup_merchant_equip",
            "startup_service_equip",
        )
    )
    suppress_combat_idle_for_merchant = planned_merchant_transaction and merchant_action_seen

    if buy_shortage > 0:
        if zero_value_junk_after > 0 and sellable_value_after <= 0:
            reasons.append("gear_money_shortage_zero_value_junk")
        elif sellable_value_after > 0:
            reasons.append("gear_money_shortage_pending_sale")
        else:
            reasons.append("gear_money_shortage_no_sellable_junk")
    if effective_target_removed > 0 and to_int(xp_effective_delta) <= 0:
        reasons.append("target_removed_no_xp")
    if not suppress_combat_idle_for_merchant and not xp_progress_made:
        if effective_target_removed <= 0 and combat_engagements > 0:
            reasons.append("combat_no_kill")
        elif effective_target_removed <= 0 and (damage_done > 0 or damage_taken > 0 or attack_actions > 0):
            if damage_taken > damage_done:
                reasons.append("combat_pressure_no_kill")
            else:
                reasons.append("combat_untracked_no_kill")
        elif effective_target_removed <= 0 and combat_engagements <= 0:
            reasons.append("no_engagement")
    if target_removed > 0 and loot_acquired <= 0:
        reasons.append("no_loot_from_kills")
    if effective_death_delta > 0 or to_int(metrics.get("player_deaths")) > 0:
        reasons.append("death_pressure")
    if to_int(metrics.get("movement_failures")) > 0:
        reasons.append("movement_failure")
    if to_int(metrics.get("target_timeouts")) > 0:
        reasons.append("target_timeout")
    if to_int(metrics.get("combat_failures")) > 0:
        reasons.append("combat_failure")
    if plan.party_share_slots:
        reasons.append("party_share_pending")
    if int(party_size or 0) > 1 and (plan.sell_slots or plan.buy_slots) and not plan.merchant_npc_name:
        reasons.append("party_merchant_pending")
    return ";".join(dict.fromkeys(reasons)) if reasons else "none"


def watcher_regression_passed(case_dir: Path, segment_index: int, watcher_pairs: list[tuple[str, str, Path]]) -> bool:
    segment_primary_success = False
    timeline_path = case_dir.parent / "timeline.csv"
    if timeline_path.exists():
        with timeline_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if row.get("case") != case_dir.name or to_int(row.get("segment")) != segment_index:
                    continue
                segment_primary_success = (
                    to_int(row.get("target_removed")) > 0
                    and to_int(row.get("xp_effective_delta")) > 0
                    and to_int(row.get("death_delta")) <= 0
                    and to_int(row.get("movement_failures")) <= 0
                    and str(row.get("bottleneck_reason", "") or "none") in {"", "none"}
                )
                break

    unique_watchers: list[tuple[str, Path]] = []
    seen_watchers: set[tuple[str, str]] = set()
    for _primary_account, watcher_account, watcher_csv in watcher_pairs:
        key = (watcher_account, str(watcher_csv))
        if key in seen_watchers:
            continue
        seen_watchers.add(key)
        unique_watchers.append((watcher_account, watcher_csv))

    for watcher_index, (_watcher_account, _watcher_csv) in enumerate(unique_watchers):
        metrics = aggregate_metrics(case_dir / f"segment-{segment_index:03d}-watcher-{watcher_index + 1:02d}-metrics.csv")
        if to_int(metrics.get("player_deaths")) > 0 or to_int(metrics.get("movement_failures")) > 0:
            return False
    summary_path = case_dir / "watcher-movement-summary.csv"
    if summary_path.exists():
        with summary_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if to_int(row.get("segment")) != segment_index:
                    continue
                if str(row.get("primary_behavior_anomaly_status", "")).lower() == "critical":
                    behavior_reason = str(row.get("primary_behavior_anomaly_reason", "") or "")
                    behavior_reasons = {part.strip() for part in behavior_reason.split(";") if part.strip()}
                    if segment_primary_success and behavior_reasons <= {"post_target_removed_pressure", "flee_too_short"}:
                        continue
                    return False
                if str(row.get("primary_anomaly_status", "")).lower() == "critical":
                    return False
    return True


def metrics_by_account(path: Path) -> dict[str, dict[str, float]]:
    summaries: dict[str, dict[str, float]] = {}
    if not path.exists():
        return summaries
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            username = row.get("username", "")
            if not username:
                continue
            summary = summaries.setdefault(username, empty_metric_summary())
            summary["metric_rows"] += 1
            if row.get("ok", "").lower() in {"1", "true", "yes"}:
                summary["ok_rows"] += 1
            summary["elapsed_seconds"] += float(row.get("elapsed_seconds") or 0.0)
            for key in (
                "actions",
                "combat_engagements",
                "target_removed",
                "player_deaths",
                "target_timeouts",
                "movement_failures",
                "loot_acquired",
                "target_removed_no_reward",
                "startup_merchant_sell",
                "startup_merchant_buy",
                "startup_merchant_equip",
                "startup_merchant_npc_missing",
                "startup_merchant_too_far",
                "startup_service_dialog_settle",
                "startup_service_equip",
                "startup_service_equip_skipped_party_slot",
            ):
                summary[key] += to_int(row.get(key) if row.get(key) is not None else row.get(f"action_{key}"))
            add_loot_tier_metrics_from_metric_row(summary, row)
    return summaries


def parse_xp_from_server_text(text: str) -> int:
    for pattern in XP_MESSAGE_PATTERNS:
        match = pattern.search(text)
        if match:
            return to_int(match.group(1).replace(",", ""))
    return 0


def encounter_text_metrics(case_dir: Path, segment_index: int, account: str) -> dict[str, int]:
    metrics = {
        "text_xp_delta": 0,
        "text_xp_messages": 0,
    }
    encounter_dir = case_dir / "encounters"
    if not encounter_dir.exists():
        return metrics
    pattern = f"segment-{segment_index:03d}-{account}-*.jsonl"
    for path in sorted(encounter_dir.glob(pattern)):
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("event") != "server_message":
                    continue
                xp = parse_xp_from_server_text(str(event.get("text", "")))
                if xp <= 0:
                    continue
                metrics["text_xp_delta"] += xp
                metrics["text_xp_messages"] += 1
    return metrics


def movement_trace_player_deaths(case_dir: Path, segment_index: int, account: str) -> int:
    movement_dir = case_dir / "movement"
    if not movement_dir.exists():
        return 0
    deaths = 0
    pattern = f"segment-{segment_index:03d}-{account}-*.jsonl"
    for path in sorted(movement_dir.glob(pattern)):
        for row in jsonl_rows(path):
            if str(row.get("event", "")) in {"player_death", "death_detected"}:
                deaths += 1
    return deaths


def apply_movement_trace_deaths_to_metrics(
    metrics_by_user: dict[str, dict[str, float]],
    fallback_metrics: dict[str, float],
    case_dir: Path,
    segment_index: int,
    account_names: list[str],
) -> dict[str, int]:
    movement_deaths_by_account: dict[str, int] = {}
    for account in account_names:
        movement_deaths = movement_trace_player_deaths(case_dir, segment_index, account)
        if movement_deaths <= 0:
            continue
        movement_deaths_by_account[account] = movement_deaths
        account_metrics = metrics_by_user.setdefault(account, empty_metric_summary())
        account_metrics["player_deaths"] = max(float(account_metrics.get("player_deaths", 0.0)), float(movement_deaths))
    if movement_deaths_by_account:
        fallback_metrics["player_deaths"] = max(
            float(fallback_metrics.get("player_deaths", 0.0)),
            float(sum(movement_deaths_by_account.values())),
        )
    return movement_deaths_by_account


def snapshot_delta(before: CharacterSnapshot | None, after: CharacterSnapshot | None) -> dict[str, int]:
    if before is None or after is None:
        return {
            "level_delta": 0,
            "xp_delta": 0,
            "money_delta_copper": 0,
            "inventory_rows_delta": 0,
            "inventory_items_delta": 0,
            "death_delta": 0,
        }
    return {
        "level_delta": after.level - before.level,
        "xp_delta": after.experience - before.experience,
        "money_delta_copper": after.money_copper - before.money_copper,
        "inventory_rows_delta": after.inventory_rows - before.inventory_rows,
        "inventory_items_delta": after.inventory_items - before.inventory_items,
        "death_delta": after.deaths - before.deaths,
    }


def snapshot_deltas_cover_text_xp(
    before: dict[str, CharacterSnapshot],
    after: dict[str, CharacterSnapshot],
    text_metrics_by_account: dict[str, dict[str, int]],
) -> bool:
    for account, text_metrics in text_metrics_by_account.items():
        text_xp = text_metrics.get("text_xp_delta", 0)
        if text_xp <= 0:
            continue
        delta = snapshot_delta(before.get(account), after.get(account))
        if delta["xp_delta"] < text_xp:
            return False
    return True


def snapshot_characters_after_segment(
    args: argparse.Namespace,
    account_names: list[str],
    before: dict[str, CharacterSnapshot],
    text_metrics_by_account: dict[str, dict[str, int]],
) -> dict[str, CharacterSnapshot]:
    deadline = time.monotonic() + max(0.0, float(args.post_segment_snapshot_timeout))
    after = snapshot_characters(args, account_names)
    while (
        time.monotonic() < deadline
        and text_metrics_by_account
        and not snapshot_deltas_cover_text_xp(before, after, text_metrics_by_account)
    ):
        time.sleep(max(0.1, float(args.post_segment_snapshot_poll_interval)))
        after = snapshot_characters(args, account_names)
    return after


def per_hour(value: float, seconds: float) -> float:
    if seconds <= 0:
        return 0.0
    return value * 3600.0 / seconds


def format_rate(value: float) -> str:
    return f"{value:.3f}"


def per_target_removed(value: float, target_removed: float) -> float:
    if target_removed <= 0:
        return 0.0
    return value / target_removed


def write_timeline_row(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp_utc",
        "case",
        "realm",
        "party_size",
        "segment",
        "account",
        "character",
        "growth_role",
        "growth_stage",
        "class_id",
        "specs_before",
        "specs_after",
        "spec_gain",
        "level_before",
        "level_after",
        "level_delta",
        "xp_before",
        "xp_after",
        "xp_delta",
        "text_xp_delta",
        "text_xp_messages",
        "xp_effective_delta",
        "xp_persist_lag",
        "xp_persist_status",
        "money_before_copper",
        "money_after_copper",
        "money_delta_copper",
        "inventory_rows_before",
        "inventory_rows_after",
        "inventory_rows_delta",
        "inventory_items_before",
        "inventory_items_after",
        "inventory_items_delta",
        "weapon_items_before",
        "weapon_items_after",
        "weapon_items_delta",
        "armor_items_before",
        "armor_items_after",
        "armor_items_delta",
        "equipment_other_items_before",
        "equipment_other_items_after",
        "equipment_other_items_delta",
        "junk_items_before",
        "junk_items_after",
        "junk_items_delta",
        "zero_value_junk_items_before",
        "zero_value_junk_items_after",
        "zero_value_junk_items_delta",
        "sellable_junk_items_before",
        "sellable_junk_items_after",
        "sellable_junk_items_delta",
        "sellable_junk_value_copper_before",
        "sellable_junk_value_copper_after",
        "sellable_junk_value_copper_delta",
        "total_sell_value_copper_before",
        "total_sell_value_copper_after",
        "total_sell_value_copper_delta",
        "train_command_sent",
        "train_verified",
        "equip_candidate_count",
        "equip_candidate_slots",
        "equip_candidate_reason",
        "sell_candidate_count",
        "sell_candidate_slots",
        "sell_candidate_reason",
        "party_share_candidate_count",
        "party_share_candidate_slots",
        "party_share_candidate_reason",
        "party_share_status",
        "party_share_executed_count",
        "party_share_executed_slots",
        "party_share_received_count",
        "party_share_received_slots",
        "party_share_failed_count",
        "party_share_failed_slots",
        "party_share_execution_reason",
        "merchant_npc",
        "buy_candidate_count",
        "buy_candidate_slots",
        "buy_candidate_inventory_count",
        "buy_candidate_inventory_slots",
        "buy_candidate_reason",
        "buy_shortage_copper",
        "merchant_transaction_status",
        "data_integrity_flags",
        "bottleneck_reason",
        "death_before",
        "death_after",
        "death_delta",
        "region_after",
        "x_after",
        "y_after",
        "z_after",
        "metric_rows",
        "ok_rows",
        "actions",
        "elapsed_seconds",
        "combat_engagements",
        "target_removed",
        "target_removed_no_reward",
        "player_deaths",
        "target_timeouts",
        "combat_failures",
        "server_los_failures",
        "target_home_leashes",
        "movement_failures",
        "loot_acquired",
        *RANDOM_LOOT_FIELDS,
        "startup_merchant_sell",
        "startup_merchant_buy",
        "startup_merchant_equip",
        "startup_merchant_npc_missing",
        "startup_merchant_too_far",
        "startup_service_dialog_settle",
        "startup_service_equip",
        "startup_service_equip_skipped_party_slot",
        "loot_per_target_removed",
        "weapon_items_per_target_removed",
        "armor_items_per_target_removed",
        "equipment_items_per_target_removed",
        "junk_items_per_target_removed",
        "random_loot_per_target_removed",
        "levels_per_hour",
        "xp_per_hour",
        "text_xp_per_hour",
        "xp_effective_per_hour",
        "money_copper_per_hour",
        "inventory_items_per_hour",
        "target_removed_per_hour",
        "deaths_per_hour",
    ]
    fieldnames.extend(fieldname for fieldname in row if fieldname not in fieldnames)
    with TIMELINE_WRITE_LOCK:
        exists = path.exists()
        if exists:
            with path.open(encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                existing_fieldnames = list(reader.fieldnames or [])
                if existing_fieldnames and existing_fieldnames != fieldnames:
                    merged_fieldnames = existing_fieldnames + [
                        fieldname for fieldname in fieldnames if fieldname not in existing_fieldnames
                    ]
                    existing_rows = list(reader)
                    with path.open("w", encoding="utf-8", newline="") as rewrite_handle:
                        writer = csv.DictWriter(rewrite_handle, fieldnames=merged_fieldnames)
                        writer.writeheader()
                        for existing_row in existing_rows:
                            writer.writerow(existing_row)
                    fieldnames = merged_fieldnames
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerow(row)


def is_carry_timeline_row(row: dict[str, str]) -> bool:
    return str(row.get("growth_role") or "tracked").strip().lower() == "carry"


def write_summary(report_path: Path, timeline_csv: Path, metadata: dict[str, object]) -> None:
    rows: list[dict[str, str]] = []
    if timeline_csv.exists():
        with timeline_csv.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    growth_rows = [row for row in rows if not is_carry_timeline_row(row)]
    total_xp = sum(to_int(row.get("xp_delta")) for row in growth_rows)
    total_text_xp = sum(to_int(row.get("text_xp_delta")) for row in growth_rows)
    total_effective_xp = sum(to_int(row.get("xp_effective_delta")) for row in growth_rows)
    total_train_verified = sum(to_int(row.get("train_verified")) for row in growth_rows)
    total_money = sum(to_int(row.get("money_delta_copper")) for row in growth_rows)
    total_items = sum(to_int(row.get("inventory_items_delta")) for row in growth_rows)
    total_weapon_items = sum(to_int(row.get("weapon_items_delta")) for row in growth_rows)
    total_armor_items = sum(to_int(row.get("armor_items_delta")) for row in growth_rows)
    total_equipment_other_items = sum(to_int(row.get("equipment_other_items_delta")) for row in growth_rows)
    total_junk_items = sum(to_int(row.get("junk_items_delta")) for row in growth_rows)
    total_zero_value_junk_items = sum(to_int(row.get("zero_value_junk_items_delta")) for row in growth_rows)
    total_sellable_junk_items = sum(to_int(row.get("sellable_junk_items_delta")) for row in growth_rows)
    total_sellable_junk_value = sum(to_int(row.get("sellable_junk_value_copper_delta")) for row in growth_rows)
    total_loot_acquired = sum(to_int(row.get("loot_acquired")) for row in growth_rows)
    total_random_loot = sum(to_int(row.get("random_loot_total")) for row in growth_rows)
    total_target_removed = sum(to_int(row.get("target_removed")) for row in growth_rows)
    total_buy_shortage = sum(to_int(row.get("buy_shortage_copper")) for row in growth_rows)
    total_merchant_sell_actions = sum(to_int(row.get("startup_merchant_sell")) for row in growth_rows)
    total_merchant_buy_actions = sum(to_int(row.get("startup_merchant_buy")) for row in growth_rows)
    total_equip_candidates = sum(to_int(row.get("equip_candidate_count")) for row in growth_rows)
    total_sell_candidates = sum(to_int(row.get("sell_candidate_count")) for row in growth_rows)
    total_party_share_candidates = sum(to_int(row.get("party_share_candidate_count")) for row in growth_rows)
    total_party_share_executed = sum(to_int(row.get("party_share_executed_count")) for row in growth_rows)
    total_party_share_received = sum(to_int(row.get("party_share_received_count")) for row in growth_rows)
    total_buy_candidates = sum(to_int(row.get("buy_candidate_count")) for row in growth_rows)
    bottleneck_rows = [row for row in growth_rows if str(row.get("bottleneck_reason") or "none") != "none"]
    total_deaths = sum(to_int(row.get("death_delta")) for row in growth_rows)
    levels = [to_int(row.get("level_after")) for row in growth_rows]
    lines = [
        "# Dummy Growth Suite",
        "",
        f"- Started: `{metadata.get('started_at_utc', '')}`",
        f"- Cases: `{metadata.get('cases', 0)}`",
        f"- Timeline rows: `{len(rows)}`",
        f"- Tracked growth rows: `{len(growth_rows)}`",
        f"- Highest observed level: `{max(levels) if levels else 0}`",
        f"- XP gained: `{total_xp}`",
        f"- Text XP gained: `{total_text_xp}`",
        f"- Effective XP gained: `{total_effective_xp}`",
        f"- Verified train/spec changes: `{total_train_verified}`",
        f"- Money gained copper: `{total_money}`",
        f"- Inventory item delta: `{total_items}`",
        f"- Loot acquired: `{total_loot_acquired}`",
        f"- Loot per target removed: `{format_rate(per_target_removed(total_loot_acquired, total_target_removed))}`",
        f"- Random loot acquired: `{total_random_loot}`",
        f"- Random loot per target removed: `{format_rate(per_target_removed(total_random_loot, total_target_removed))}`",
        f"- Weapon item delta: `{total_weapon_items}`",
        f"- Armor item delta: `{total_armor_items}`",
        f"- Other equipment item delta: `{total_equipment_other_items}`",
        f"- Junk item delta: `{total_junk_items}`",
        f"- Zero-value junk delta: `{total_zero_value_junk_items}`",
        f"- Sellable junk delta/value copper: `{total_sellable_junk_items}` / `{total_sellable_junk_value}`",
        f"- Equip/sell candidate slots: `{total_equip_candidates}` / `{total_sell_candidates}`",
        f"- Party share candidate/executed/received slots: `{total_party_share_candidates}` / `{total_party_share_executed}` / `{total_party_share_received}`",
        f"- Merchant buy candidate slots: `{total_buy_candidates}`",
        f"- Merchant sell/buy actions: `{total_merchant_sell_actions}` / `{total_merchant_buy_actions}`",
        f"- Planned merchant buy shortage copper: `{total_buy_shortage}`",
        f"- Bottleneck rows: `{len(bottleneck_rows)}`",
        f"- Death delta: `{total_deaths}`",
        "",
        "## Files",
        "",
        f"- Timeline CSV: `{timeline_csv}`",
        f"- Case summary CSV: `{report_path.with_name('case-summary.csv')}`",
        f"- Metadata JSON: `{report_path.with_name('metadata.json')}`",
        "",
        "## Recent Rows",
        "",
        "| Case | Account | Level | DB XP | Text XP | Effective XP | Train | Spec Gain | XP/h | Money Delta | Money/h | Items Delta | Loot/Kill | Gear/Kill | Deaths | Removed | Move Fail |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in growth_rows[-20:]:
        display_row = {
            **{field: "0" for field in (
                "loot_per_target_removed",
                "equipment_items_per_target_removed",
            )},
            **row,
        }
        lines.append(
            "| {case} | `{account}` | {level_after} | {xp_delta} | {text_xp_delta} | {xp_effective_delta} | "
            "{train_verified} | {spec_gain} | {xp_effective_per_hour} | {money_delta_copper} | "
            "{money_copper_per_hour} | {inventory_items_delta} | {loot_per_target_removed} | "
            "{equipment_items_per_target_removed} | {death_delta} | {target_removed} | "
            "{movement_failures} |".format(**display_row)
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_case_summary(path: Path, timeline_csv: Path) -> None:
    rows: list[dict[str, str]] = []
    if timeline_csv.exists():
        with timeline_csv.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        if is_carry_timeline_row(row):
            continue
        case = row.get("case", "")
        if not case:
            continue
        summary = grouped.setdefault(
            case,
            {
                "case": case,
                "realm": row.get("realm", ""),
                "party_size": row.get("party_size", ""),
                "rows": 0,
                "accounts": set(),
                "segments": set(),
                "elapsed_seconds": 0.0,
                "metric_rows": 0,
                "ok_rows": 0,
                "level_delta": 0,
                "xp_delta": 0,
                "text_xp_delta": 0,
                "text_xp_messages": 0,
                "xp_effective_delta": 0,
                "xp_persist_lag": 0,
                "money_delta_copper": 0,
                "inventory_items_delta": 0,
                "weapon_items_delta": 0,
                "armor_items_delta": 0,
                "equipment_other_items_delta": 0,
                "junk_items_delta": 0,
                "zero_value_junk_items_delta": 0,
                "sellable_junk_items_delta": 0,
                "sellable_junk_value_copper_delta": 0,
                "total_sell_value_copper_delta": 0,
                "equip_candidate_count": 0,
                "sell_candidate_count": 0,
                "party_share_candidate_count": 0,
                "party_share_executed_count": 0,
                "party_share_received_count": 0,
                "party_share_failed_count": 0,
                "buy_candidate_count": 0,
                "buy_candidate_inventory_count": 0,
                "death_delta": 0,
                "train_verified": 0,
                "target_removed": 0,
                "movement_failures": 0,
                "loot_acquired": 0,
                **{field: 0 for field in RANDOM_LOOT_FIELDS},
                "startup_merchant_sell": 0,
                "startup_merchant_buy": 0,
                "startup_merchant_equip": 0,
                "startup_service_dialog_settle": 0,
                "startup_service_equip": 0,
                "startup_service_equip_skipped_party_slot": 0,
                "bottleneck_rows": 0,
                "latest_bottleneck_reason": "",
                "max_level": 0,
            },
        )
        summary["rows"] = int(summary["rows"]) + 1
        summary["accounts"].add(row.get("account", ""))  # type: ignore[union-attr]
        summary["segments"].add(row.get("segment", ""))  # type: ignore[union-attr]
        summary["metric_rows"] = int(summary["metric_rows"]) + to_int(row.get("metric_rows"))
        summary["ok_rows"] = int(summary["ok_rows"]) + to_int(row.get("ok_rows"))
        for key in (
            "elapsed_seconds",
            "level_delta",
            "xp_delta",
            "text_xp_delta",
            "text_xp_messages",
            "xp_effective_delta",
            "xp_persist_lag",
            "money_delta_copper",
            "inventory_items_delta",
            "weapon_items_delta",
            "armor_items_delta",
            "equipment_other_items_delta",
            "junk_items_delta",
            "zero_value_junk_items_delta",
            "sellable_junk_items_delta",
            "sellable_junk_value_copper_delta",
            "total_sell_value_copper_delta",
            "equip_candidate_count",
            "sell_candidate_count",
            "party_share_candidate_count",
            "party_share_executed_count",
            "party_share_received_count",
            "party_share_failed_count",
            "buy_candidate_count",
            "buy_candidate_inventory_count",
            "death_delta",
            "train_verified",
            "target_removed",
            "movement_failures",
            "loot_acquired",
            *RANDOM_LOOT_FIELDS,
            "startup_merchant_sell",
            "startup_merchant_buy",
            "startup_merchant_equip",
            "startup_service_dialog_settle",
            "startup_service_equip",
            "startup_service_equip_skipped_party_slot",
        ):
            if key == "elapsed_seconds":
                summary[key] = float(summary[key]) + float(row.get(key) or 0.0)
            else:
                summary[key] = int(summary[key]) + to_int(row.get(key))
        bottleneck_reason = str(row.get("bottleneck_reason") or "none")
        if bottleneck_reason != "none":
            summary["bottleneck_rows"] = int(summary["bottleneck_rows"]) + 1
            summary["latest_bottleneck_reason"] = bottleneck_reason
        summary["max_level"] = max(int(summary["max_level"]), to_int(row.get("level_after")))

    fieldnames = [
        "case",
        "realm",
        "party_size",
        "accounts",
        "segments",
        "elapsed_seconds",
        "metric_rows",
        "ok_rows",
        "failed_rows",
        "ok_percent",
        "max_level",
        "level_delta",
        "xp_delta",
        "text_xp_delta",
        "text_xp_messages",
        "xp_effective_delta",
        "xp_persist_lag",
        "money_delta_copper",
        "inventory_items_delta",
        "weapon_items_delta",
        "armor_items_delta",
        "equipment_other_items_delta",
        "junk_items_delta",
        "zero_value_junk_items_delta",
        "sellable_junk_items_delta",
        "sellable_junk_value_copper_delta",
        "total_sell_value_copper_delta",
        "equip_candidate_count",
        "sell_candidate_count",
        "party_share_candidate_count",
        "party_share_executed_count",
        "party_share_received_count",
        "party_share_failed_count",
        "buy_candidate_count",
        "buy_candidate_inventory_count",
        "death_delta",
        "train_verified",
        "target_removed",
        "movement_failures",
        "loot_acquired",
        *RANDOM_LOOT_FIELDS,
        "startup_merchant_sell",
        "startup_merchant_buy",
        "startup_merchant_equip",
        "startup_service_dialog_settle",
        "startup_service_equip",
        "startup_service_equip_skipped_party_slot",
        "bottleneck_rows",
        "latest_bottleneck_reason",
        "loot_per_target_removed",
        "weapon_items_per_target_removed",
        "armor_items_per_target_removed",
        "equipment_items_per_target_removed",
        "junk_items_per_target_removed",
        "random_loot_per_target_removed",
        "levels_per_hour",
        "xp_per_hour",
        "text_xp_per_hour",
        "xp_effective_per_hour",
        "money_copper_per_hour",
        "inventory_items_per_hour",
        "target_removed_per_hour",
        "deaths_per_hour",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for case in sorted(grouped):
            summary = grouped[case]
            elapsed = float(summary["elapsed_seconds"])
            writer.writerow(
                {
                    "case": summary["case"],
                    "realm": summary["realm"],
                    "party_size": summary["party_size"],
                    "accounts": len([account for account in summary["accounts"] if account]),  # type: ignore[union-attr]
                    "segments": len([segment for segment in summary["segments"] if segment]),  # type: ignore[union-attr]
                    "elapsed_seconds": format_rate(elapsed),
                    "metric_rows": summary["metric_rows"],
                    "ok_rows": summary["ok_rows"],
                    "failed_rows": int(summary["metric_rows"]) - int(summary["ok_rows"]),
                    "ok_percent": format_rate(
                        (float(summary["ok_rows"]) * 100.0 / float(summary["metric_rows"]))
                        if int(summary["metric_rows"]) > 0
                        else 0.0
                    ),
                    "max_level": summary["max_level"],
                    "level_delta": summary["level_delta"],
                    "xp_delta": summary["xp_delta"],
                    "text_xp_delta": summary["text_xp_delta"],
                    "text_xp_messages": summary["text_xp_messages"],
                    "xp_effective_delta": summary["xp_effective_delta"],
                    "xp_persist_lag": summary["xp_persist_lag"],
                    "money_delta_copper": summary["money_delta_copper"],
                    "inventory_items_delta": summary["inventory_items_delta"],
                    "weapon_items_delta": summary["weapon_items_delta"],
                    "armor_items_delta": summary["armor_items_delta"],
                    "equipment_other_items_delta": summary["equipment_other_items_delta"],
                    "junk_items_delta": summary["junk_items_delta"],
                    "zero_value_junk_items_delta": summary["zero_value_junk_items_delta"],
                    "sellable_junk_items_delta": summary["sellable_junk_items_delta"],
                    "sellable_junk_value_copper_delta": summary["sellable_junk_value_copper_delta"],
                    "total_sell_value_copper_delta": summary["total_sell_value_copper_delta"],
                    "equip_candidate_count": summary["equip_candidate_count"],
                    "sell_candidate_count": summary["sell_candidate_count"],
                    "party_share_candidate_count": summary["party_share_candidate_count"],
                    "party_share_executed_count": summary["party_share_executed_count"],
                    "party_share_received_count": summary["party_share_received_count"],
                    "party_share_failed_count": summary["party_share_failed_count"],
                    "buy_candidate_count": summary["buy_candidate_count"],
                    "buy_candidate_inventory_count": summary["buy_candidate_inventory_count"],
                    "death_delta": summary["death_delta"],
                    "train_verified": summary["train_verified"],
                    "target_removed": summary["target_removed"],
                    "movement_failures": summary["movement_failures"],
                    "loot_acquired": summary["loot_acquired"],
                    **{field: summary[field] for field in RANDOM_LOOT_FIELDS},
                    "startup_merchant_sell": summary["startup_merchant_sell"],
                    "startup_merchant_buy": summary["startup_merchant_buy"],
                    "startup_merchant_equip": summary["startup_merchant_equip"],
                    "startup_service_dialog_settle": summary["startup_service_dialog_settle"],
                    "startup_service_equip": summary["startup_service_equip"],
                    "startup_service_equip_skipped_party_slot": summary["startup_service_equip_skipped_party_slot"],
                    "bottleneck_rows": summary["bottleneck_rows"],
                    "latest_bottleneck_reason": summary["latest_bottleneck_reason"],
                    "loot_per_target_removed": format_rate(
                        per_target_removed(float(summary["loot_acquired"]), float(summary["target_removed"]))
                    ),
                    "weapon_items_per_target_removed": format_rate(
                        per_target_removed(float(summary["weapon_items_delta"]), float(summary["target_removed"]))
                    ),
                    "armor_items_per_target_removed": format_rate(
                        per_target_removed(float(summary["armor_items_delta"]), float(summary["target_removed"]))
                    ),
                    "equipment_items_per_target_removed": format_rate(
                        per_target_removed(
                            float(summary["weapon_items_delta"])
                            + float(summary["armor_items_delta"])
                            + float(summary["equipment_other_items_delta"]),
                            float(summary["target_removed"]),
                        )
                    ),
                    "junk_items_per_target_removed": format_rate(
                        per_target_removed(float(summary["junk_items_delta"]), float(summary["target_removed"]))
                    ),
                    "random_loot_per_target_removed": format_rate(
                        per_target_removed(float(summary["random_loot_total"]), float(summary["target_removed"]))
                    ),
                    "levels_per_hour": format_rate(per_hour(float(summary["level_delta"]), elapsed)),
                    "xp_per_hour": format_rate(per_hour(float(summary["xp_delta"]), elapsed)),
                    "text_xp_per_hour": format_rate(per_hour(float(summary["text_xp_delta"]), elapsed)),
                    "xp_effective_per_hour": format_rate(per_hour(float(summary["xp_effective_delta"]), elapsed)),
                    "money_copper_per_hour": format_rate(per_hour(float(summary["money_delta_copper"]), elapsed)),
                    "inventory_items_per_hour": format_rate(per_hour(float(summary["inventory_items_delta"]), elapsed)),
                    "target_removed_per_hour": format_rate(per_hour(float(summary["target_removed"]), elapsed)),
                    "deaths_per_hour": format_rate(per_hour(float(summary["death_delta"]), elapsed)),
                }
            )


def next_segment_index(case_dir: Path) -> int:
    indexes: list[int] = []
    for path in case_dir.glob("segment-*-metrics.csv"):
        match = re.match(r"segment-(\d+)-metrics\.csv$", path.name)
        if match:
            indexes.append(int(match.group(1)))
    return max(indexes, default=0) + 1


def growth_case_name(realm: RealmProfile, party_size: int, repeat_index: int = 0, case_repeats: int = 1) -> str:
    base = f"{realm.key}-p{party_size}"
    if case_repeats <= 1:
        return base
    return f"{base}-r{repeat_index + 1:03d}"


def run_case(
    args: argparse.Namespace,
    realm: RealmProfile,
    party_size: int,
    case_index: int,
    output_dir: Path,
    path_graph: Path,
    timeline_csv: Path,
    repeat_index: int = 0,
    case_repeats: int = 1,
) -> int:
    case_name = args.case_name or growth_case_name(realm, party_size, repeat_index, case_repeats)
    case_dir = output_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    accounts_csv = case_dir / "accounts.csv"
    primary_accounts_csv = case_dir / "primary-accounts.csv"
    watcher_accounts_dir = case_dir / "watcher-accounts"
    watcher_accounts_csv = watcher_accounts_dir / "watcher-accounts.csv"
    start = args.start + case_index * args.start_stride
    requested_watcher_count = watcher_count_for_party(args, party_size)
    checkpoint_levels = list(getattr(args, "checkpoint_levels_parsed", []))
    account_segments = checkpoint_account_segment_count(checkpoint_levels, args.max_segments)
    provision_count = (party_size + requested_watcher_count) * account_segments
    provision_command = build_provision_command(args, realm, accounts_csv, provision_count, start, party_size)
    if not args.skip_provision:
        rc = run_command(provision_command, args.dry_run)
        if rc != 0:
            return rc
    elif args.dry_run:
        print(f"skip provisioning: {accounts_csv}")
    if args.skip_provision and not args.dry_run and not accounts_csv.exists():
        raise FileNotFoundError(f"--skip-provision needs existing accounts csv: {accounts_csv}")
    if args.dry_run and not accounts_csv.exists():
        account_rows = [
            {
                "username": f"{realm.prefix}{start + offset:03d}",
                "password": args.password,
                "realm": str(realm.realm_id),
                "char_index": "0",
            }
            for offset in range(provision_count)
        ]
    else:
        account_rows = read_accounts(accounts_csv)
    primary_rows, watcher_rows = select_segment_account_rows(
        account_rows,
        party_size=party_size,
        watcher_count=requested_watcher_count,
        segment_ordinal=0,
        account_segments=account_segments,
    )
    account_names = [row["username"] for row in primary_rows]
    watcher_account_names = [row["username"] for row in watcher_rows]
    if not args.skip_provision and args.reset_progress and not args.dry_run and not checkpoint_levels:
        initial_account_roles = growth_party_account_roles(
            account_names,
            party_size,
            carry_count_override=growth_party_carry_count_from_args(args, party_size),
        )
        mark_growth_party_account_roles(primary_rows, initial_account_roles)
        reset_growth_characters(args, account_names + watcher_account_names, level=args.reset_level, realm=realm, party_size=party_size)
        if str(getattr(args, "checkpoint_start_location", "") or "").lower() == "route-home":
            apply_checkpoint_start_to_account_rows(args, primary_rows, realm, args.reset_level, party_size)
            if primary_rows:
                write_accounts(primary_accounts_csv, primary_rows)
            if watcher_rows:
                watcher_start = watcher_observer_home_point(args, realm, args.reset_level, party_size)
                apply_checkpoint_start_to_account_rows(
                    args,
                    watcher_rows,
                    realm,
                    args.reset_level,
                    party_size,
                    start_point=watcher_start,
                )
                watcher_accounts_dir.mkdir(parents=True, exist_ok=True)
                write_accounts(watcher_accounts_csv, watcher_rows)

    if args.first_segment:
        first_segment = args.first_segment
    else:
        first_segment = next_segment_index(case_dir) if args.resume else 1
    last_segment = first_segment + args.max_segments - 1
    segment_plan: list[tuple[int, int | None]]
    if checkpoint_levels:
        segment_plan = [
            (first_segment + offset, level)
            for offset, level in enumerate(checkpoint_levels[: args.max_segments])
        ]
    else:
        segment_plan = [(segment_index, None) for segment_index in range(first_segment, last_segment + 1)]
    for plan_index, (segment_index, checkpoint_level) in enumerate(segment_plan):
        primary_rows, watcher_rows = select_segment_account_rows(
            account_rows,
            party_size=party_size,
            watcher_count=requested_watcher_count,
            segment_ordinal=plan_index,
            account_segments=account_segments,
        )
        account_names = [row["username"] for row in primary_rows]
        watcher_account_names = [row["username"] for row in watcher_rows]
        account_roles = growth_party_account_roles(
            account_names,
            party_size,
            carry_count_override=growth_party_carry_count_from_args(args, party_size),
        )
        tracked_account_names = tracked_growth_accounts(account_names, account_roles)
        carry_account_names = carry_growth_accounts(account_names, account_roles)
        mark_growth_party_account_roles(primary_rows, account_roles)
        if primary_rows:
            write_accounts(primary_accounts_csv, primary_rows)
        if watcher_rows:
            watcher_accounts_dir.mkdir(parents=True, exist_ok=True)
            rename_watcher_characters(args, watcher_account_names)
        if checkpoint_level is not None and args.reset_progress and not args.dry_run:
            checkpoint_specs = {
                row["username"]: row.get("specs", "")
                for row in primary_rows + watcher_rows
                if row.get("username")
            }
            reset_growth_characters(
                args,
                account_names + watcher_account_names,
                level=checkpoint_level,
                realm=realm,
                party_size=party_size,
                target_specs_by_account=checkpoint_specs,
            )
            if watcher_account_names and str(getattr(args, "checkpoint_start_location", "") or "").lower() == "route-home":
                reset_growth_characters(
                    args,
                    watcher_account_names,
                    level=checkpoint_level,
                    realm=realm,
                    party_size=party_size,
                    target_specs_by_account=checkpoint_specs,
                    start_point=watcher_observer_home_point(args, realm, checkpoint_level, party_size),
                )
        if checkpoint_level is not None:
            apply_checkpoint_start_to_account_rows(args, primary_rows, realm, checkpoint_level, party_size)
            if primary_rows:
                write_accounts(primary_accounts_csv, primary_rows)
            if watcher_rows:
                watcher_start = (
                    watcher_observer_home_point(args, realm, checkpoint_level, party_size)
                    if str(getattr(args, "checkpoint_start_location", "") or "").lower() == "route-home"
                    else None
                )
                apply_checkpoint_start_to_account_rows(
                    args,
                    watcher_rows,
                    realm,
                    checkpoint_level,
                    party_size,
                    start_point=watcher_start,
                )
                watcher_accounts_dir.mkdir(parents=True, exist_ok=True)
                write_accounts(watcher_accounts_csv, watcher_rows)
        before = {} if args.dry_run else snapshot_characters(args, account_names)
        observed_level = observed_growth_level(
            before,
            account_names,
            account_roles,
            checkpoint_level,
            party_size=party_size,
        )
        if checkpoint_level is None and observed_level >= args.max_level:
            break
        current_level = growth_effective_party_level(before, observed_level, party_size)
        if current_level != max(1, observed_level):
            print(
                "growth party level catch-up: "
                f"case={case_name} segment={segment_index} realm={realm.key} party={party_size} "
                f"observed_tracked={observed_level} effective={current_level}"
            )
        args.current_party_size = party_size
        carry_level = growth_party_carry_level_for_realm(args, current_level, party_size, realm.key) if carry_account_names else 0
        if carry_account_names and not args.dry_run:
            carry_specs = {
                row["username"]: capped_specs_for_level(row.get("specs", ""), carry_level)
                for row in primary_rows
                if row.get("username") in carry_account_names
            }
            reset_growth_characters(
                args,
                carry_account_names,
                level=carry_level,
                realm=realm,
                party_size=party_size,
                target_specs_by_account=carry_specs,
                reset_money=False,
            )
        tracked_rows = [row for row in primary_rows if row.get("username") in tracked_account_names]
        carry_rows = [row for row in primary_rows if row.get("username") in carry_account_names]
        promoted_count = promote_growth_classes_for_level(args, tracked_rows, current_level)
        promoted_count += (
            promote_growth_classes_for_level(args, carry_rows, carry_level, trained_specs=True)
            if carry_level
            else 0
        )
        low_level_spec_updates = apply_growth_low_level_spec_plan(
            args,
            tracked_rows,
            snapshot_characters(args, account_names) if promoted_count and not args.dry_run else before,
            realm=realm,
            current_level=current_level,
            party_size=party_size,
        )
        if low_level_spec_updates and primary_rows:
            write_accounts(primary_accounts_csv, primary_rows)
        equipped_growth_party_carry_gear = False
        if (
            carry_account_names
            and should_equip_growth_party_carry_gear(args, carry_level=carry_level, party_size=party_size)
            and not args.dry_run
        ):
            carry_accounts_csv = case_dir / f"segment-{segment_index:03d}-carry-accounts.csv"
            write_accounts(carry_accounts_csv, carry_rows)
            rc = run_command(build_growth_party_carry_gear_command(args, carry_accounts_csv, carry_level), args.dry_run)
            if rc != 0:
                return rc
            equipped_growth_party_carry_gear = True
        equipped_growth_checkpoint_gear = False
        if should_equip_growth_checkpoint_gear(args, realm, current_level=current_level, party_size=party_size):
            checkpoint_snapshots = (
                snapshot_characters(args, account_names)
                if (promoted_count or low_level_spec_updates) and not args.dry_run
                else before
            )
            checkpoint_inventory_items = snapshot_inventory_items(args, account_names)
            checkpoint_equipped = equip_growth_checkpoint_gear(
                args,
                realm,
                checkpoint_snapshots,
                checkpoint_inventory_items,
                current_level=current_level,
                party_size=party_size,
            )
            equipped_growth_checkpoint_gear = checkpoint_equipped > 0
        equipped_level50_party_gear = False
        if should_equip_level50_party_gear(args, current_level=current_level, party_size=party_size):
            rc = run_command(build_level50_party_gear_command(args, primary_accounts_csv), args.dry_run)
            if rc != 0:
                return rc
            equipped_level50_party_gear = True
        active_before = (
            snapshot_characters(args, account_names)
            if (
                promoted_count
                or low_level_spec_updates
                or equipped_growth_party_carry_gear
                or equipped_growth_checkpoint_gear
                or equipped_level50_party_gear
                or carry_account_names
            )
            and not args.dry_run
            else before
        )
        before = active_before
        segment_restore_state = (
            SegmentDbRestoreState([], [], [])
            if args.dry_run
            else snapshot_segment_db_restore_state(args, account_names)
        )
        item_plan_account_names = growth_item_plan_account_names(account_names, tracked_account_names, party_size)
        item_plans = build_growth_item_plans(
            args,
            item_plan_account_names,
            active_before,
            realm=realm,
            current_level=current_level,
            party_size=party_size,
        )
        if party_size > 1:
            item_plans = execute_growth_party_share_transfers(
                args,
                item_plans,
                active_before,
                case_dir / f"segment-{segment_index:03d}-party-share.csv",
            )
            active_before = snapshot_characters(args, account_names) if not args.dry_run else active_before
            before = active_before
        before_inventory_items = (
            {}
            if args.dry_run
            else snapshot_inventory_items(args, account_names)
        )
        behavior_args = argparse.Namespace(**vars(args))
        behavior_args.case_name = case_name
        behavior_args.run_dir = str(output_dir)
        behavior_args.current_realm_key = realm.key
        behavior_args.growth_runtime_failure_memory_csv = str(case_dir / "runtime-failure-memory.csv")
        behavior_args.growth_route_case_index = int(getattr(args, "growth_route_case_index", 0) or 0) + case_index
        behavior_args.growth_current_segment_index = segment_index
        behavior_args.growth_route_player_level = current_level
        party_slot_by_account = party_slot_by_account_from_rows(primary_rows, party_size)
        if carry_account_names:
            combat_level = growth_party_combat_level(active_before, current_level, party_size)
            carry_target_plan = growth_party_behavior_carry_target_plan(
                behavior_args,
                current_level,
                party_size,
                realm.key,
                combat_level,
            )
            carry_target_level = max(1, int(carry_target_plan[1]))
            behavior_args.growth_route_level_override = carry_target_level
            behavior_args.growth_route_level_is_carry_target = True
            behavior_args.growth_target_level_override = current_level
            behavior_args.growth_target_plan_override = carry_target_plan
            if combat_level != current_level or carry_target_level != current_level:
                print(
                    "growth party combat target level: "
                    f"case={case_name} segment={segment_index} realm={realm.key} party={party_size} "
                    f"tracked_level={current_level} combat_level={combat_level} carry_target_level={carry_target_level} "
                    f"target_plan={behavior_args.growth_target_plan_override}"
                )
        equip_mode = getattr(args, "growth_auto_equip_mode", "candidate")
        if equip_mode == "off":
            behavior_args.growth_auto_equip_slots = []
            behavior_args.growth_auto_equip_party_slot_maps = []
        elif equip_mode == "slots":
            behavior_args.growth_auto_equip_slots = list(getattr(args, "growth_auto_equip_slots", []))
            behavior_args.growth_auto_equip_party_slot_maps = []
        elif party_size > 1:
            behavior_args.growth_auto_equip_slots = []
            behavior_args.growth_auto_equip_party_slot_maps = party_slot_slot_maps(
                item_plans,
                "equip_slots",
                party_slot_by_account,
            )
        else:
            behavior_args.growth_auto_equip_slots = union_plan_slots(item_plans, "equip_slots")
            behavior_args.growth_auto_equip_party_slot_maps = []
        behavior_args.growth_merchant_npc_name = first_growth_merchant_name(item_plans)
        if args.growth_auto_sell_junk and party_size == 1:
            behavior_args.growth_auto_sell_slots = union_plan_slots(item_plans, "sell_slots")
            behavior_args.growth_merchant_sell_party_slot_maps = []
        elif args.growth_auto_sell_junk and party_size > 1:
            behavior_args.growth_auto_sell_slots = []
            behavior_args.growth_merchant_sell_party_slot_maps = party_slot_slot_maps(
                item_plans,
                "sell_slots",
                party_slot_by_account,
                merchant_name=behavior_args.growth_merchant_npc_name,
            )
        else:
            behavior_args.growth_auto_sell_slots = []
            behavior_args.growth_merchant_sell_party_slot_maps = []
        if party_size > 1:
            behavior_args.growth_merchant_buy_slots = []
            behavior_args.growth_merchant_equip_slots = []
            behavior_args.growth_merchant_buy_party_slot_maps = party_slot_slot_maps(
                item_plans,
                "buy_slots",
                party_slot_by_account,
                merchant_name=behavior_args.growth_merchant_npc_name,
            )
            behavior_args.growth_merchant_equip_party_slot_maps = party_slot_slot_maps(
                item_plans,
                "buy_inventory_slots",
                party_slot_by_account,
                merchant_name=behavior_args.growth_merchant_npc_name,
            )
        else:
            behavior_args.growth_merchant_buy_slots = union_plan_slots(item_plans, "buy_slots")
            behavior_args.growth_merchant_equip_slots = union_plan_slots(item_plans, "buy_inventory_slots")
            behavior_args.growth_merchant_buy_party_slot_maps = []
            behavior_args.growth_merchant_equip_party_slot_maps = []
        gear_farm_mode = should_use_growth_gear_farm_route(
            args,
            realm,
            current_level=current_level,
            party_size=party_size,
            item_plans=item_plans,
            snapshots=active_before,
        )
        shortage_recovery_override = growth_shortage_recovery_route_override(
            args,
            realm,
            current_level=current_level,
            party_size=party_size,
            item_plans=item_plans,
        )
        if apply_growth_survival_route_override(
            behavior_args,
            realm,
            current_level=current_level,
            party_size=party_size,
        ):
            gear_farm_mode = False
        elif gear_farm_mode:
            if shortage_recovery_override is not None:
                route_level, target_level = shortage_recovery_override
                behavior_args.growth_route_level_override = route_level
                behavior_args.growth_target_level_override = target_level
                behavior_args.growth_allow_lower_xp_target_plan = True
                behavior_args.growth_shortage_recovery_player_level = int(current_level or 0)
                if realm.key == "mid" and int(current_level or 0) == 7:
                    behavior_args.growth_target_plan_override = (5, 5, 0)
                elif realm.key == "alb" and int(current_level or 0) == 7:
                    behavior_args.growth_target_plan_override = (5, 5, 1)
                elif realm.key == "hib" and int(current_level or 0) == 7:
                    behavior_args.growth_target_plan_override = (5, 5, 0)
                elif realm.key == "mid" and int(current_level or 0) == 8:
                    behavior_args.growth_target_plan_override = (6, 6, 1)
                elif realm.key == "alb" and int(current_level or 0) == 8:
                    behavior_args.growth_target_plan_override = (6, 6, 0)
                elif realm.key == "alb" and int(current_level or 0) == 9:
                    behavior_args.growth_target_plan_override = (6, 6, 0)
                elif realm.key == "mid" and int(current_level or 0) == 9:
                    behavior_args.growth_target_plan_override = (7, 7, 0)
                elif realm.key == "mid" and int(current_level or 0) == 10:
                    behavior_args.growth_target_plan_override = (7, 7, 0)
                elif hasattr(behavior_args, "growth_target_plan_override"):
                    delattr(behavior_args, "growth_target_plan_override")
            elif carry_account_names:
                gear_min, gear_ideal, gear_delta = growth_party_behavior_carry_target_plan(
                    behavior_args,
                    current_level,
                    party_size,
                    realm.key,
                    combat_level,
                )
                gear_floor = max(
                    1,
                    minimum_growth_effective_target_level(current_level, party_size, realm.key),
                )
                gear_min = max(gear_min, gear_floor)
                gear_ideal = max(gear_ideal, gear_min)
                behavior_args.growth_target_plan_override = (gear_min, gear_ideal, gear_delta)
            else:
                gear_target_level = max(
                    1,
                    minimum_growth_effective_target_level(current_level, party_size, realm.key),
                )
                if realm.key == "mid" and int(party_size or 0) <= 1 and int(current_level or 0) == 10:
                    gear_target_level = 7
                behavior_args.growth_route_level_override = current_level
                behavior_args.growth_target_level_override = current_level
                behavior_args.growth_target_plan_override = (gear_target_level, gear_target_level, 0)
                behavior_args.growth_allow_lower_xp_target_plan = False
        elif apply_growth_shortage_recovery_route_override(
            behavior_args,
            args,
            realm,
            current_level=current_level,
            party_size=party_size,
            item_plans=item_plans,
        ):
            gear_farm_mode = True
        route_level = int(getattr(behavior_args, "growth_route_level_override", 0) or current_level)
        selected_segment_route: RoutePoint | None = None

        def segment_route() -> RoutePoint:
            nonlocal selected_segment_route
            if selected_segment_route is None:
                selected_segment_route = select_growth_segment_route(
                    behavior_args,
                    realm,
                    route_level,
                    party_size,
                    current_level=current_level,
                    segment_index=segment_index,
                )
            return selected_segment_route

        previous_timeline_row = latest_timeline_row_for_case(timeline_csv, case_name)
        planned_merchant_transaction = growth_item_plans_have_merchant_transaction(item_plans)
        planned_merchant_buy = growth_item_plans_have_merchant_buy(item_plans)
        planned_party_merchant_maps = bool(
            getattr(behavior_args, "growth_merchant_sell_party_slot_maps", [])
            or getattr(behavior_args, "growth_merchant_buy_party_slot_maps", [])
            or getattr(behavior_args, "growth_merchant_equip_party_slot_maps", [])
        )
        planned_merchant_execution = growth_item_plans_have_executable_merchant_transaction(
            item_plans,
            party_size=party_size,
            planned_party_merchant_maps=planned_party_merchant_maps,
        )
        if not planned_merchant_transaction:
            behavior_args.growth_merchant_npc_name = ""
            behavior_args.growth_auto_sell_slots = []
            behavior_args.growth_merchant_sell_party_slot_maps = []
            behavior_args.growth_merchant_buy_slots = []
            behavior_args.growth_merchant_equip_slots = []
            behavior_args.growth_merchant_buy_party_slot_maps = []
            behavior_args.growth_merchant_equip_party_slot_maps = []
        growth_route_home_start_applied = False
        stage_route_home_after_services = should_stage_route_home_after_startup_services(
            args,
            realm,
            route_level,
            party_size,
        )
        if (
            str(getattr(args, "growth_fast_travel", "off") or "off").lower() == "route-home"
            and not planned_merchant_execution
            and not stage_route_home_after_services
        ):
            route_for_fast_travel = segment_route()
            fast_travel_start_point = startup_route_home_after_services_point(
                realm,
                route_for_fast_travel,
                current_level=current_level,
                party_size=party_size,
                ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
            )
            relocate_growth_characters_to_route(behavior_args, account_names, realm, fast_travel_start_point)
            apply_checkpoint_start_to_account_rows(
                behavior_args,
                primary_rows,
                realm,
                route_level,
                party_size,
                start_point=fast_travel_start_point,
            )
            if primary_rows:
                write_accounts(primary_accounts_csv, primary_rows)
            print(
                "growth fast travel route-home: "
                f"case={case_name} segment={segment_index} realm={realm.key} "
                f"level={route_level} x={fast_travel_start_point.x} y={fast_travel_start_point.y} z={fast_travel_start_point.z}"
            )
            growth_route_home_start_applied = True
            active_before = snapshot_characters(args, account_names) if not args.dry_run else active_before
        elif (
            str(getattr(args, "growth_fast_travel", "off") or "off").lower() == "route-home"
            and planned_merchant_execution
            and behavior_args.growth_merchant_npc_name
        ):
            merchant_point = growth_merchant_npc_point(behavior_args, realm, behavior_args.growth_merchant_npc_name)
            if merchant_point is not None:
                relocate_growth_characters_to_route(behavior_args, account_names, realm, merchant_point)
                apply_checkpoint_start_to_account_rows(
                    behavior_args,
                    primary_rows,
                    realm,
                    route_level,
                    party_size,
                    start_point=merchant_point,
                )
                if primary_rows:
                    write_accounts(primary_accounts_csv, primary_rows)
                print(
                    "growth fast travel merchant-home: "
                    f"case={case_name} segment={segment_index} realm={realm.key} "
                    f"merchant={behavior_args.growth_merchant_npc_name} "
                    f"x={merchant_point.x} y={merchant_point.y} z={merchant_point.z}"
                )
                growth_route_home_start_applied = True
                active_before = snapshot_characters(args, account_names) if not args.dry_run else active_before
        if (
            str(getattr(args, "growth_fast_travel", "off") or "off").lower() == "route-home"
            and carry_account_names
            and not growth_route_home_start_applied
        ):
            route_for_fast_travel = segment_route()
            fast_travel_start_point = startup_route_home_after_services_point(
                realm,
                route_for_fast_travel,
                current_level=current_level,
                party_size=party_size,
                ground_z_offset=int(getattr(args, "ground_z_offset", 0) or 0),
            )
            relocate_growth_characters_to_route(behavior_args, account_names, realm, fast_travel_start_point)
            apply_checkpoint_start_to_account_rows(
                behavior_args,
                primary_rows,
                realm,
                route_level,
                party_size,
                start_point=fast_travel_start_point,
            )
            if primary_rows:
                write_accounts(primary_accounts_csv, primary_rows)
            print(
                "growth fast travel carry route-home fallback: "
                f"case={case_name} segment={segment_index} realm={realm.key} "
                f"level={route_level} x={fast_travel_start_point.x} y={fast_travel_start_point.y} z={fast_travel_start_point.z}"
            )
            active_before = snapshot_characters(args, account_names) if not args.dry_run else active_before
        behavior_args.growth_skip_startup_teleport = should_skip_growth_startup_teleport_near_route_home(
            behavior_args,
            active_before,
            realm=realm,
            route_level=route_level,
            current_level=current_level,
            party_size=party_size,
            previous_segment_leveled=latest_timeline_row_leveled(previous_timeline_row),
            planned_merchant_transaction=planned_merchant_execution,
        )
        if planned_merchant_execution:
            behavior_args.growth_skip_startup_teleport = True
            behavior_args.growth_merchant_approach_distance = max(
                350.0,
                float(getattr(behavior_args, "growth_merchant_approach_distance", 0.0) or 0.0),
            )
        behavior_args.growth_merchant_only_segment = planned_merchant_execution
        behavior_command = build_behavior_command(
            args=behavior_args,
            realm=realm,
            accounts_csv=primary_accounts_csv,
            case_dir=case_dir,
            segment_index=segment_index,
            party_size=party_size,
            current_level=current_level,
            path_graph=path_graph,
            selected_route=segment_route(),
        )
        commands = [behavior_command]
        if args.live_supervisor:
            commands.append(
                build_live_supervisor_command(
                    args,
                    case_dir,
                    current_level=current_level,
                    party_size=party_size,
                    realm_key=realm.key,
                    selected_route=segment_route(),
                )
            )
        watcher_pairs: list[tuple[str, str, Path]] = []
        if args.watch_movement:
            for watcher_index, watcher_row in enumerate(watcher_rows[:1]):
                watcher_csv = watcher_accounts_dir / f"watcher-{watcher_index + 1:02d}.csv"
                write_accounts(watcher_csv, [watcher_row])
                primary_account = account_names[0]
                for observed_account in account_names:
                    watcher_pairs.append((observed_account, watcher_row["username"], watcher_csv))
                commands.append(
                    build_watcher_command(
                        args=args,
                        realm=realm,
                        watcher_csv=watcher_csv,
                        case_dir=case_dir,
                        segment_index=segment_index,
                        watcher_index=watcher_index,
                        primary_account=primary_account,
                        current_level=current_level,
                        path_graph=path_graph,
                        party_size=party_size,
                        selected_route=selected_segment_route,
                    )
                )
        rc = run_commands_concurrently(commands, args.dry_run)
        if watcher_pairs:
            watcher_summary_rows: list[dict[str, object]] = []
            route = selected_segment_route or select_route_point(realm, current_level, party_size)
            for primary_account, watcher_account, _watcher_csv in watcher_pairs:
                primary_path = case_dir / "movement" / f"segment-{segment_index:03d}-{primary_account}-1.jsonl"
                watcher_path = case_dir / "movement" / f"segment-{segment_index:03d}-{watcher_account}-1.jsonl"
                primary_encounter_path = case_dir / "encounters" / f"segment-{segment_index:03d}-{primary_account}-1.jsonl"
                watcher_summary_rows.append(
                    {
                        "case": case_name,
                        "segment": segment_index,
                        "primary_account": primary_account,
                        "watcher_account": watcher_account,
                        **compare_watcher_pair(
                            primary_path,
                            watcher_path,
                            primary_encounter_path=primary_encounter_path,
                            prefer_target_name=route.prefer,
                            z_warn_delta=args.watcher_z_warn_delta,
                            xy_warn_delta=args.watcher_xy_warn_delta,
                            rewind_warn_distance=args.watcher_rewind_warn_distance,
                            z_compare_xy_distance=args.watcher_z_compare_xy_distance,
                        ),
                    }
                )
            write_watcher_summary(case_dir / "watcher-movement-summary.csv", watcher_summary_rows)
        if not args.dry_run and args.post_segment_snapshot_delay > 0:
            time.sleep(args.post_segment_snapshot_delay)
        segment_metrics = case_dir / f"segment-{segment_index:03d}-metrics.csv"
        segment_combat = case_dir / f"segment-{segment_index:03d}-combat.csv"
        metrics_by_user = metrics_by_account(segment_metrics)
        fallback_metrics = aggregate_metrics(segment_metrics)
        fallback_metrics.update(aggregate_combat_metrics(segment_combat))
        movement_deaths_by_account = apply_movement_trace_deaths_to_metrics(
            metrics_by_user,
            fallback_metrics,
            case_dir,
            segment_index,
            account_names,
        )
        require_kill = segment_requires_kill(args, current_level)
        if planned_merchant_execution and not segment_requirement_explicit(args, "require_segment_kill"):
            require_kill = False
        if not args.dry_run and getattr(args, "fail_on_regression", True) and not segment_regression_passed(
            fallback_metrics,
            require_kill=require_kill,
        ):
            repro_command = build_failure_reproduction_command(
                args,
                realm=realm,
                party_size=party_size,
                case_index=case_index,
                current_level=current_level,
                output_dir=output_dir,
            )
            write_failure_reproduction_command(case_dir / "failure-reproduction-command.txt", repro_command)
            rc = rc or 1
        if (
            not args.dry_run
            and getattr(args, "fail_on_regression", True)
            and not growth_merchant_transaction_regression_passed(
                fallback_metrics,
                planned_merchant_execution=planned_merchant_execution,
            )
        ):
            repro_command = build_failure_reproduction_command(
                args,
                realm=realm,
                party_size=party_size,
                case_index=case_index,
                current_level=current_level,
                output_dir=output_dir,
            )
            write_failure_reproduction_command(case_dir / "failure-reproduction-command.txt", repro_command)
            rc = rc or 1
        if (
            watcher_pairs
            and not args.dry_run
            and getattr(args, "fail_on_regression", True)
            and not watcher_regression_passed(case_dir, segment_index, watcher_pairs)
        ):
            repro_command = build_failure_reproduction_command(
                args,
                realm=realm,
                party_size=party_size,
                case_index=case_index,
                current_level=current_level,
                output_dir=output_dir,
            )
            write_failure_reproduction_command(case_dir / "failure-reproduction-command.txt", repro_command)
            rc = rc or 1
        text_metrics_by_account = {
            account: encounter_text_metrics(case_dir, segment_index, account)
            for account in account_names
        }
        after = (
            before
            if args.dry_run
            else snapshot_characters_after_segment(args, account_names, before, text_metrics_by_account)
        )
        after_inventory_items = (
            before_inventory_items
            if args.dry_run
            else snapshot_inventory_items(args, account_names)
        )
        if not args.dry_run:
            write_segment_inventory_csv(
                case_dir / f"segment-{segment_index:03d}-inventory.csv",
                after_inventory_items,
        )
        segment_xp_effective_delta = 0
        segment_xp_effective_by_account: dict[str, int | float] = {}
        segment_runtime_bottleneck_reasons: set[str] = set()
        live_abort_reason = ""
        live_abort_path = case_dir / "live-abort.json"
        if live_abort_path.exists():
            live_abort_reason = read_live_abort_reason(live_abort_path)
        for account in account_names:
            growth_role = account_roles.get(account, "tracked")
            before_row = before.get(account)
            after_row = after.get(account)
            delta = snapshot_delta(before_row, after_row)
            inventory_delta = inventory_category_delta(
                before_inventory_items.get(account, []),
                after_inventory_items.get(account, []),
            )
            text_metrics = text_metrics_by_account.get(account, {"text_xp_delta": 0, "text_xp_messages": 0})
            xp_effective_delta = max(delta["xp_delta"], text_metrics["text_xp_delta"])
            if growth_role != "carry":
                segment_xp_effective_delta += xp_effective_delta
                segment_xp_effective_by_account[account] = xp_effective_delta
            xp_persist_lag = max(0, text_metrics["text_xp_delta"] - delta["xp_delta"])
            xp_persist_status = "lagging" if xp_persist_lag > 0 else "synced"
            spec_gain = spec_gain_summary(before_row.specs if before_row else "", after_row.specs if after_row else "")
            metrics = metrics_by_user.get(account, fallback_metrics if len(account_names) == 1 else empty_metric_summary())
            elapsed_seconds = float(metrics["elapsed_seconds"])
            target_removed = float(metrics.get("target_removed", 0) or 0)
            weapon_item_delta = float(inventory_delta.get("weapon_items_delta", 0) or 0)
            armor_item_delta = float(inventory_delta.get("armor_items_delta", 0) or 0)
            equipment_item_delta = (
                weapon_item_delta
                + armor_item_delta
                + float(inventory_delta.get("equipment_other_items_delta", 0) or 0)
            )
            junk_item_delta = float(inventory_delta.get("junk_items_delta", 0) or 0)
            loot_acquired = float(metrics.get("loot_acquired", 0) or 0)
            effective_death_delta = max(delta["death_delta"], movement_deaths_by_account.get(account, 0))
            item_plan = item_plans.get(account, GrowthItemPlan([], []))
            merchant_transaction_status = growth_merchant_transaction_status(
                item_plan,
                metrics,
                party_size=party_size,
            )
            data_integrity_flags = growth_data_integrity_flags(
                args,
                item_plan,
                party_size=party_size,
                promoted_count=promoted_count,
                equipped_growth_party_carry_gear=equipped_growth_party_carry_gear,
                equipped_growth_checkpoint_gear=equipped_growth_checkpoint_gear,
                equipped_level50_party_gear=equipped_level50_party_gear,
            )
            bottleneck_reason = growth_bottleneck_reason(
                item_plan,
                inventory_delta,
                metrics,
                party_size=party_size,
                xp_effective_delta=xp_effective_delta,
                effective_death_delta=effective_death_delta,
                planned_merchant_transaction=planned_merchant_execution,
            )
            for token in bottleneck_reason.split(";"):
                token = token.strip()
                if token and token != "none":
                    segment_runtime_bottleneck_reasons.add(token)
            if live_abort_reason:
                bottleneck_reason = append_reason(bottleneck_reason, live_abort_bottleneck_reason(live_abort_reason))
                segment_runtime_bottleneck_reasons.add(live_abort_bottleneck_reason(live_abort_reason))
            write_timeline_row(
                timeline_csv,
                {
                    "timestamp_utc": utc_now(),
                    "case": case_name,
                    "realm": realm.key,
                    "party_size": party_size,
                    "segment": segment_index,
                    "account": account,
                    "character": after_row.name if after_row else "",
                    "growth_role": growth_role,
                    "growth_stage": growth_stage_for_level(current_level),
                    "class_id": after_row.class_id if after_row else "",
                    "specs_before": before_row.specs if before_row else "",
                    "specs_after": after_row.specs if after_row else "",
                    "spec_gain": spec_gain,
                    "level_before": before_row.level if before_row else "",
                    "level_after": after_row.level if after_row else "",
                    "level_delta": delta["level_delta"],
                    "xp_before": before_row.experience if before_row else "",
                    "xp_after": after_row.experience if after_row else "",
                    "xp_delta": delta["xp_delta"],
                    "text_xp_delta": text_metrics["text_xp_delta"],
                    "text_xp_messages": text_metrics["text_xp_messages"],
                    "xp_effective_delta": xp_effective_delta,
                    "xp_persist_lag": xp_persist_lag,
                    "xp_persist_status": xp_persist_status,
                    "money_before_copper": before_row.money_copper if before_row else "",
                    "money_after_copper": after_row.money_copper if after_row else "",
                    "money_delta_copper": delta["money_delta_copper"],
                    "inventory_rows_before": before_row.inventory_rows if before_row else "",
                    "inventory_rows_after": after_row.inventory_rows if after_row else "",
                    "inventory_rows_delta": delta["inventory_rows_delta"],
                    "inventory_items_before": before_row.inventory_items if before_row else "",
                    "inventory_items_after": after_row.inventory_items if after_row else "",
                    "inventory_items_delta": delta["inventory_items_delta"],
                    **inventory_delta,
                    "train_command_sent": "1" if should_train_at_level(current_level) else "0",
                    "train_verified": "1" if train_verified(before_row, after_row, current_level) else "0",
                    "equip_candidate_count": len(item_plan.equip_slots),
                    "equip_candidate_slots": ",".join(str(slot) for slot in item_plan.equip_slots),
                    "equip_candidate_reason": item_plan.equip_reason,
                    "sell_candidate_count": len(item_plan.sell_slots),
                    "sell_candidate_slots": ",".join(str(slot) for slot in item_plan.sell_slots),
                    "sell_candidate_reason": item_plan.sell_reason,
                    "party_share_candidate_count": len(item_plan.party_share_slots),
                    "party_share_candidate_slots": ",".join(str(slot) for slot in item_plan.party_share_slots),
                    "party_share_candidate_reason": item_plan.party_share_reason,
                    "party_share_status": growth_party_share_status(item_plan),
                    "party_share_executed_count": len(item_plan.party_share_executed_slots),
                    "party_share_executed_slots": ",".join(str(slot) for slot in item_plan.party_share_executed_slots),
                    "party_share_received_count": len(item_plan.party_share_received_slots),
                    "party_share_received_slots": ",".join(str(slot) for slot in item_plan.party_share_received_slots),
                    "party_share_failed_count": len(item_plan.party_share_failed_slots),
                    "party_share_failed_slots": ",".join(str(slot) for slot in item_plan.party_share_failed_slots),
                    "party_share_execution_reason": item_plan.party_share_execution_reason,
                    "merchant_npc": item_plan.merchant_npc_name,
                    "buy_candidate_count": len(item_plan.buy_slots),
                    "buy_candidate_slots": ",".join(str(slot) for slot in item_plan.buy_slots),
                    "buy_candidate_inventory_count": len(item_plan.buy_inventory_slots),
                    "buy_candidate_inventory_slots": ",".join(str(slot) for slot in item_plan.buy_inventory_slots),
                    "buy_candidate_reason": item_plan.buy_reason,
                    "buy_shortage_copper": item_plan.buy_shortage_copper,
                    "merchant_transaction_status": merchant_transaction_status,
                    "data_integrity_flags": data_integrity_flags,
                    "bottleneck_reason": bottleneck_reason,
                    "death_before": before_row.deaths if before_row else "",
                    "death_after": after_row.deaths if after_row else "",
                    "death_delta": effective_death_delta,
                    "region_after": after_row.region if after_row else "",
                    "x_after": after_row.x if after_row else "",
                    "y_after": after_row.y if after_row else "",
                    "z_after": after_row.z if after_row else "",
                    **metrics,
                    "elapsed_seconds": format_rate(elapsed_seconds),
                    "loot_per_target_removed": format_rate(per_target_removed(loot_acquired, target_removed)),
                    "weapon_items_per_target_removed": format_rate(per_target_removed(weapon_item_delta, target_removed)),
                    "armor_items_per_target_removed": format_rate(per_target_removed(armor_item_delta, target_removed)),
                    "equipment_items_per_target_removed": format_rate(per_target_removed(equipment_item_delta, target_removed)),
                    "junk_items_per_target_removed": format_rate(per_target_removed(junk_item_delta, target_removed)),
                    "random_loot_per_target_removed": format_rate(
                        per_target_removed(float(metrics.get("random_loot_total", 0) or 0), target_removed)
                    ),
                    "levels_per_hour": format_rate(per_hour(delta["level_delta"], elapsed_seconds)),
                    "xp_per_hour": format_rate(per_hour(delta["xp_delta"], elapsed_seconds)),
                    "text_xp_per_hour": format_rate(per_hour(text_metrics["text_xp_delta"], elapsed_seconds)),
                    "xp_effective_per_hour": format_rate(per_hour(xp_effective_delta, elapsed_seconds)),
                    "money_copper_per_hour": format_rate(per_hour(delta["money_delta_copper"], elapsed_seconds)),
                    "inventory_items_per_hour": format_rate(per_hour(delta["inventory_items_delta"], elapsed_seconds)),
                    "target_removed_per_hour": format_rate(per_hour(float(metrics["target_removed"]), elapsed_seconds)),
                    "deaths_per_hour": format_rate(per_hour(effective_death_delta, elapsed_seconds)),
                },
            )
        if not args.dry_run:
            record_growth_runtime_failure_memory_for_segment(
                case_dir / "runtime-failure-memory.csv",
                case_name=case_name,
                realm_key=realm.key,
                party_size=party_size,
                segment_index=segment_index,
                current_level=current_level,
                bottleneck_reasons=segment_runtime_bottleneck_reasons,
                combat_csv=segment_combat,
                case_dir=case_dir,
            )
        require_xp = segment_requires_xp(args, current_level) and not gear_farm_mode
        if planned_merchant_execution and not segment_requirement_explicit(args, "require_segment_xp"):
            require_xp = False
        aggregate_xp_ok = segment_xp_regression_passed(segment_xp_effective_delta, require_xp=require_xp)
        account_xp_ok = segment_account_xp_regression_passed(
            segment_xp_effective_by_account,
            require_xp=require_xp and bool(getattr(args, "require_account_segment_xp", False)),
        )
        if not args.dry_run:
            summary_route = select_growth_route_point(behavior_args, realm, route_level, party_size)
            write_growth_segment_summary_json(
                case_dir / f"segment-{segment_index:03d}-summary.json",
                args=behavior_args,
                case_name=case_name,
                realm=realm,
                party_size=party_size,
                segment_index=segment_index,
                current_level=current_level,
                route_level=route_level,
                route=summary_route,
                metrics=fallback_metrics,
                combat_csv=segment_combat,
                bottleneck_reasons=segment_runtime_bottleneck_reasons,
                xp_effective_delta=segment_xp_effective_delta,
                xp_effective_by_account=segment_xp_effective_by_account,
                require_kill=require_kill,
                require_xp=require_xp,
                aggregate_xp_ok=aggregate_xp_ok,
                account_xp_ok=account_xp_ok,
                rc=rc,
                live_abort_reason=live_abort_reason,
            )
        if not args.dry_run and getattr(args, "fail_on_regression", True) and not (aggregate_xp_ok and account_xp_ok):
            repro_command = build_failure_reproduction_command(
                args,
                realm=realm,
                party_size=party_size,
                case_index=case_index,
                current_level=current_level,
                output_dir=output_dir,
            )
            write_failure_reproduction_command(case_dir / "failure-reproduction-command.txt", repro_command)
            rc = rc or 1
        if rc != 0 or args.once:
            if rc != 0 and not args.dry_run:
                restore_segment_db_state(args, segment_restore_state)
                print(f"growth failed segment DB state restored: case={case_name} segment={segment_index}")
            return rc
        if plan_index + 1 < len(segment_plan) and args.inter_segment_delay > 0:
            time.sleep(args.inter_segment_delay)
    return 0


def build_case_plan(
    selected_realms: list[str],
    party_sizes: list[int],
    case_repeats: int = 1,
) -> list[tuple[RealmProfile, int, int, int, int]]:
    if case_repeats < 1:
        raise SystemExit("case repeats must be positive")
    cases: list[tuple[RealmProfile, int, int, int, int]] = []
    case_index = 0
    for realm_key in selected_realms:
        realm = REALMS[realm_key]
        for party_size in party_sizes:
            if party_size < 1:
                raise SystemExit("party sizes must be positive")
            for repeat_index in range(case_repeats):
                cases.append((realm, party_size, case_index, repeat_index, case_repeats))
                case_index += 1
    return cases


def run_case_plan(
    *,
    args: argparse.Namespace,
    cases: list[tuple[RealmProfile, int, int, int, int]],
    output_dir: Path,
    path_graph: Path,
    timeline_csv: Path,
) -> int:
    if args.parallel_cases <= 1 or len(cases) <= 1:
        exit_code = 0
        for realm, party_size, case_index, repeat_index, case_repeats in cases:
            rc = run_case(
                args,
                realm,
                party_size,
                case_index,
                output_dir,
                path_graph,
                timeline_csv,
                repeat_index=repeat_index,
                case_repeats=case_repeats,
            )
            exit_code = exit_code or rc
            if rc != 0:
                break
        return exit_code

    max_workers = min(args.parallel_cases, len(cases))
    print(f"running {len(cases)} growth cases with parallel_cases={max_workers}")
    exit_code = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                run_case,
                args,
                realm,
                party_size,
                case_index,
                output_dir,
                path_graph,
                timeline_csv,
                repeat_index,
                case_repeats,
            ): (
                realm.key,
                party_size,
                case_index,
                repeat_index,
                case_repeats,
            )
            for realm, party_size, case_index, repeat_index, case_repeats in cases
        }
        for future in concurrent.futures.as_completed(futures):
            realm_key, party_size, case_index, repeat_index, case_repeats = futures[future]
            try:
                rc = future.result()
            except Exception as exc:
                case_name = growth_case_name(REALMS[realm_key], party_size, repeat_index, case_repeats)
                print(f"case {case_name} index={case_index} failed: {exc}")
                rc = 1
            exit_code = exit_code or rc
    return exit_code


def cli_option_was_explicit(raw_argv: list[str], option: str) -> bool:
    return any(token == option or token.startswith(f"{option}=") for token in raw_argv)


def cli_bool_option_was_explicit(raw_argv: list[str], option: str) -> bool:
    return cli_option_was_explicit(raw_argv, option) or cli_option_was_explicit(raw_argv, f"--no-{option[2:]}")


def host_is_loopback(host: str) -> bool:
    normalized = str(host or "").strip().lower()
    return normalized in {"", "localhost", "127.0.0.1", "::1"}


def api_url_uses_loopback(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
    except Exception:
        return False
    return host_is_loopback(parsed.hostname or "")


def apply_growth_api_host_defaults(args: argparse.Namespace, explicit_options: set[str]) -> None:
    if "nav_api_url" in explicit_options:
        return
    if host_is_loopback(getattr(args, "host", "")):
        return
    if not api_url_uses_loopback(getattr(args, "nav_api_url", "")):
        return
    args.nav_api_url = f"http://{args.host}:{int(getattr(args, 'api_port', 5000) or 5000)}"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    explicit_segment_seconds = cli_option_was_explicit(raw_argv, "--segment-seconds")
    explicit_reset_level = cli_option_was_explicit(raw_argv, "--reset-level")
    explicit_max_level = cli_option_was_explicit(raw_argv, "--max-level")
    explicit_max_segments = cli_option_was_explicit(raw_argv, "--max-segments")
    explicit_inter_segment_delay = cli_option_was_explicit(raw_argv, "--inter-segment-delay")
    explicit_options = {
        name
        for name, option in (
            ("segment_seconds", "--segment-seconds"),
            ("startup_delay", "--startup-delay"),
            ("post_segment_snapshot_delay", "--post-segment-snapshot-delay"),
            ("post_segment_snapshot_timeout", "--post-segment-snapshot-timeout"),
            ("post_segment_snapshot_poll_interval", "--post-segment-snapshot-poll-interval"),
            ("inter_segment_delay", "--inter-segment-delay"),
            ("safe_exit_max_seconds", "--safe-exit-max-seconds"),
            ("safe_exit_recent_damage_grace", "--safe-exit-recent-damage-grace"),
            ("nav_api_url", "--nav-api-url"),
            ("checkpoint_start_location", "--checkpoint-start-location"),
            ("growth_fast_travel", "--growth-fast-travel"),
        )
        if cli_option_was_explicit(raw_argv, option)
    }
    for name, option in (
        ("watch_movement", "--watch-movement"),
        ("live_supervisor", "--live-supervisor"),
        ("fail_on_regression", "--fail-on-regression"),
        ("require_segment_kill", "--require-segment-kill"),
        ("require_segment_xp", "--require-segment-xp"),
    ):
        if cli_bool_option_was_explicit(raw_argv, option):
            explicit_options.add(name)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_DUMMY_HOST)
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--live-api-url", default="")
    parser.add_argument("--nav-api-url", default="http://127.0.0.1:5000")
    parser.add_argument(
        "--growth-route-preflight",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="verify hunting-index route candidates against live /api/dummy/combat/npcs before launching a segment",
    )
    parser.add_argument("--growth-route-preflight-timeout", type=float, default=1.5)
    parser.add_argument("--growth-route-preflight-radius", type=float, default=0.0)
    parser.add_argument("--growth-route-preflight-low-solo-radius", type=float, default=2500.0)
    parser.add_argument("--growth-route-preflight-limit", type=int, default=3)
    parser.add_argument("--growth-route-preflight-min-available-targets", type=int, default=0)
    parser.add_argument("--growth-route-preflight-hazard-radius", type=float, default=2500.0)
    parser.add_argument("--growth-route-preflight-hazard-limit", type=int, default=3)
    parser.add_argument("--growth-route-preflight-hazard-token-limit", type=int, default=12)
    parser.add_argument(
        "--growth-route-preflight-anchor",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="for low solo hunting-index routes, use the live preflight NPC coordinates as the segment route home",
    )
    parser.add_argument(
        "--growth-failure-target-memory",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="avoid targets that repeatedly produced failed combat with no kill in prior attempts for this case segment",
    )
    parser.add_argument("--growth-failure-target-memory-attempts", type=int, default=8)
    parser.add_argument("--growth-failure-target-memory-min-engagements", type=int, default=2)
    parser.add_argument("--mysql-bin", default=os.environ.get("MYSQL_BIN"))
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT", "3306")))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME", "opendaoc"))
    parser.add_argument("--db-user", default=os.environ.get("DB_USER", "root"))
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD", read_serverconfig_password()))
    parser.add_argument("--template-account", default="dummy040")
    parser.add_argument("--template-character", default="Dummy040")
    parser.add_argument("--password", default=os.environ.get("OPENDAOC_DUMMY_PASSWORD", "dummy-pass"))
    parser.add_argument("--realms", default="alb,mid,hib", help="comma-separated: alb,mid,hib")
    parser.add_argument("--party-sizes", default="1,2,4,8", help="comma-separated party sizes")
    parser.add_argument(
        "--party-external-member-names",
        default="",
        help="comma-separated real player names to include as support-only party members",
    )
    parser.add_argument("--start", type=int, default=701)
    parser.add_argument("--start-stride", type=int, default=20)
    parser.add_argument(
        "--growth-teleporter-npc-name",
        default="master visur,stor gothi annark,channeler glasny,teleporter,porter,텔레포터",
    )
    parser.add_argument("--growth-teleport-scan-seconds", type=float, default=1.0)
    parser.add_argument("--growth-teleport-approach-distance", type=float, default=80.0)
    parser.add_argument("--growth-teleport-approach-timeout", type=float, default=20.0)
    parser.add_argument("--growth-teleport-warmup-delay", type=float, default=1.6)
    parser.add_argument("--growth-teleport-wait-seconds", type=float, default=2.0)
    parser.add_argument("--growth-teleporter-home-stop-distance", type=float, default=900.0)
    parser.add_argument("--growth-teleporter-home-timeout", type=float, default=90.0)
    parser.add_argument("--position-step", type=int, default=80)
    parser.add_argument("--segment-seconds", type=int, default=600)
    parser.add_argument("--max-segments", type=int, default=60)
    parser.add_argument("--max-level", type=int, default=50)
    parser.add_argument("--growth-stage", choices=sorted(GROWTH_STAGE_DEFAULTS), default="custom", help="apply a checkpoint preset: stabilize(1-4), train(5), gear(6-10), long(10-50), or custom")
    parser.add_argument(
        "--growth-speed-profile",
        choices=sorted(GROWTH_SPEED_PROFILES),
        default="debug",
        help="debug keeps strict timing; fast-balance shortens batch collection overhead while preserving real combat/economy loops",
    )
    parser.add_argument("--checkpoint-levels", default="", help="comma-separated forced levels for fast 1-50 checkpoint probes, e.g. 1,5,6,10,20,35,49")
    parser.add_argument("--checkpoint-seed-copper", type=int, default=-1, help="forced checkpoint starting money in copper; -1 uses the suite default policy")
    parser.add_argument(
        "--checkpoint-start-location",
        choices=["realm-start", "teleport", "route-home"],
        default="realm-start",
        help="where checkpoint-reset characters begin; route-home skips startup teleporter for fast combat FSM repros",
    )
    parser.add_argument(
        "--growth-hunting-index",
        default="",
        help="CSV produced by analyze-dummy-growth-hunting-grounds.py; case index spreads non-party cases across candidates",
    )
    parser.add_argument(
        "--growth-route-case-index",
        type=int,
        default=0,
        help="base candidate-spread index for selecting a DB-backed growth hunting route",
    )
    parser.add_argument(
        "--growth-fast-travel",
        choices=["off", "route-home", "teleport"],
        default="off",
        help="route-home repositions characters to the selected hunting ground before non-merchant growth segments",
    )
    parser.add_argument("--ramp-up", type=int, default=5)
    parser.add_argument("--login-retries", type=int, default=12)
    parser.add_argument("--login-retry-delay", type=float, default=5.0)
    parser.add_argument("--max-target-distance", type=float, default=2200)
    parser.add_argument("--target-home-max-distance", type=float, default=1400.0)
    parser.add_argument("--combat-home-leash-distance", type=float, default=1200.0)
    parser.add_argument("--target-timeout", type=float, default=65)
    parser.add_argument("--combat-interval", type=float, default=1.5)
    parser.add_argument("--target-pool", type=int, default=5)
    parser.add_argument("--smooth-move-interval", type=float, default=0.20)
    parser.add_argument("--movement-speed", type=float, default=240.0)
    parser.add_argument("--path-last-mile-distance", type=float, default=1200.0)
    parser.add_argument("--ground-z-offset", type=int, default=0)
    parser.add_argument("--encounter-log-interval", type=float, default=3.0)
    parser.add_argument("--live-control-interval", type=float, default=1.0, help="seconds between behavior client live-control JSON polls")
    parser.add_argument("--live-supervisor", action=argparse.BooleanOptionalAction, default=True, help="tail live encounter logs and retune live-control JSON during each segment")
    parser.add_argument("--live-supervisor-interval", type=float, default=3.0)
    parser.add_argument("--live-supervisor-step", type=float, default=350.0)
    parser.add_argument("--live-supervisor-max-engage", type=float, default=2800.0)
    parser.add_argument("--live-supervisor-max-radius", type=float, default=5200.0)
    parser.add_argument("--startup-delay", type=float, default=12.0, help="seconds growth dummies wait after login/services so PvP enter immunity expires before hunting")
    parser.add_argument("--post-segment-snapshot-delay", type=float, default=2.0, help="seconds to wait after dummy logout before DB-backed XP/money/inventory snapshots")
    parser.add_argument("--post-segment-snapshot-timeout", type=float, default=90.0, help="maximum seconds to poll DB snapshots until server-message XP is persisted")
    parser.add_argument("--post-segment-snapshot-poll-interval", type=float, default=2.0, help="seconds between DB snapshot polls while waiting for persisted XP")
    parser.add_argument("--inter-segment-delay", type=float, default=75.0, help="seconds to wait between repeated login segments so linkdead server-side sessions are fully released")
    parser.add_argument("--safe-exit-max-seconds", type=float, default=GROWTH_SAFE_EXIT_MAX_SECONDS, help="maximum behavior-client safe-exit wait after each segment")
    parser.add_argument("--safe-exit-recent-damage-grace", type=float, default=GROWTH_SAFE_EXIT_RECENT_DAMAGE_GRACE, help="recent-damage grace window used by behavior-client safe-exit")
    parser.add_argument("--travel-aggro-clear-grace", type=float, default=24.0, help="seconds without new travel-add damage before returning to objective")
    parser.add_argument("--party-rescue-max-age", type=float, default=0.0, help="override behavior-client party rescue max age; 0 keeps the growth default")
    parser.add_argument("--party-rescue-assist-after", type=float, default=0.0, help="override seconds before non-healer damage roles assist rescue targets; 0 keeps the growth default")
    parser.add_argument("--party-rescue-emergency-assist-after", type=float, default=2.0, help="seconds before emergency rescue focus for healer/caster pressure")
    parser.add_argument("--watch-movement", action=argparse.BooleanOptionalAction, default=True, help="run one non-combat watcher dummy behind each growth dummy and compare movement/Z traces")
    parser.add_argument("--watcher-follow-interval", type=float, default=0.4)
    parser.add_argument("--watcher-follow-distance", type=float, default=5000.0)
    parser.add_argument("--watcher-follow-max-distance", type=float, default=60000.0)
    parser.add_argument("--watcher-movement-speed", type=float, default=240.0)
    parser.add_argument("--watcher-z-warn-delta", type=float, default=180.0)
    parser.add_argument("--watcher-z-compare-xy-distance", type=float, default=5600.0)
    parser.add_argument("--watcher-xy-warn-delta", type=float, default=18000.0)
    parser.add_argument("--watcher-rewind-warn-distance", type=float, default=650.0)
    parser.add_argument("--growth-auto-equip-mode", choices=["candidate", "slots", "off"], default="candidate", help="candidate uses DB item scoring, slots tries --growth-auto-equip-slots directly, off disables segment-start equipment changes")
    parser.add_argument("--growth-auto-equip-slots", type=parse_slot_list, default=parse_slot_list("40-55"), help="manual backpack slots used only with --growth-auto-equip-mode slots")
    parser.add_argument("--growth-auto-sell-junk", action=argparse.BooleanOptionalAction, default=True, help="sell DB-scored junk slots during merchant stops; parties use per-party-slot sell maps so one member cannot sell another member's slot")
    parser.add_argument("--growth-auto-buy-merchant-gear", action=argparse.BooleanOptionalAction, default=True, help="buy one affordable DB-scored armor/shield upgrade from a visible merchant using earned money and planned sell proceeds")
    parser.add_argument("--growth-allow-lower-xp-gear-farm", action=argparse.BooleanOptionalAction, default=True, help="when solo gear-stage progress is blocked by an affordable-upgrade shortage, allow a lower safe farm route and do not require XP for that farm segment")
    parser.add_argument("--growth-party-carry-level-offset", type=int, default=12, help="party growth carry character level offset above the selected carry target level")
    parser.add_argument("--growth-party-carry-count", type=int, default=-1, help="-1 keeps legacy N-1 carry party growth; 0 makes every party member a tracked growth target")
    parser.add_argument("--growth-merchant-max-distance", type=float, default=8000.0, help="maximum distance from the expected startup/teleport point when selecting a growth merchant")
    parser.add_argument("--growth-merchant-scan-seconds", type=float, default=1.0, help="seconds the behavior client scans for the selected growth merchant before selling/buying")
    parser.add_argument("--growth-merchant-approach-distance", type=float, default=150.0, help="distance the behavior client moves within before sending merchant buy/sell packets")
    parser.add_argument("--growth-merchant-approach-timeout", type=float, default=90.0, help="maximum seconds spent approaching the selected growth merchant")
    parser.add_argument("--growth-merchant-sell-ratio-percent", type=int, default=50, help="planning estimate for merchant sell value; server default item_sell_ratio is 50")
    parser.add_argument("--growth-equip-party-carry-gear", action=argparse.BooleanOptionalAction, default=False, help="equip party carry characters with injected template gear; official economy/drop runs keep this disabled")
    parser.add_argument("--level50-party-gear", action=argparse.BooleanOptionalAction, default=False, help="equip party checkpoint characters with validated level-50 boss-test gear")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--run-dir", type=Path, help="reuse a specific output directory instead of creating a timestamped run")
    parser.add_argument("--resume", action="store_true", help="continue an existing --run-dir from the next missing segment")
    parser.add_argument("--case-name", default="", help="override the generated realm/party case directory name")
    parser.add_argument("--first-segment", type=int, default=0, help="start from this explicit segment index instead of segment 1 or --resume auto-detection")
    parser.add_argument("--skip-provision", action="store_true")
    parser.add_argument("--reset-progress", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--reset-level", type=int, default=1, help="level used when resetting provisioned growth characters")
    parser.add_argument(
        "--no-growth-start-base-classes",
        dest="growth_start_base_classes",
        action="store_false",
        default=True,
        help="provision growth characters directly as target classes instead of starter/base classes below level 5",
    )
    parser.add_argument("--replace", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--no-starter-equipment", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--once", action="store_true", help="run only one segment per case")
    parser.add_argument(
        "--case-repeats",
        type=int,
        default=1,
        help="repeat each realm/party case this many times; use 100 with --party-sizes 1 for 100 independent solo runs per realm",
    )
    parser.add_argument("--parallel-cases", type=int, default=1, help="number of realm/party cases to run concurrently; each case still launches its own party and watcher dummies")
    parser.add_argument("--fail-on-regression", action=argparse.BooleanOptionalAction, default=True, help="fail a segment and write a reproduction command when deaths, movement failures, or no kills are observed")
    parser.add_argument("--require-segment-kill", action=argparse.BooleanOptionalAction, default=True, help="with --fail-on-regression, require at least one target_removed per segment")
    parser.add_argument("--require-segment-xp", action=argparse.BooleanOptionalAction, default=True, help="with --fail-on-regression, require XP progress for growth hunting segments below level 50")
    parser.add_argument("--require-account-segment-xp", action=argparse.BooleanOptionalAction, default=False, help="with --fail-on-regression, require every account to gain XP in each required growth segment")
    parser.add_argument("--smoke", action="store_true", help="quick albion solo smoke: 1 realm, 1 party size, 1 short segment")
    parser.add_argument("--fast-flee-debug", action="store_true", help="quick solo flee-loop repro: short segment, no watcher/snapshot/live retuning, fail only on deaths or movement failures")
    args = parser.parse_args(argv)
    args.explicit_options = set(explicit_options)
    if args.growth_fast_travel == "teleport":
        args.growth_fast_travel = "route-home"
    apply_growth_api_host_defaults(args, explicit_options)
    explicit_segment_seconds_value = args.segment_seconds
    explicit_reset_level_value = args.reset_level
    explicit_max_level_value = args.max_level
    explicit_max_segments_value = args.max_segments
    apply_growth_stage_defaults(args)
    apply_l10_checkpoint_route_home_defaults(args, explicit_options)
    if explicit_segment_seconds:
        args.segment_seconds = explicit_segment_seconds_value
    if explicit_reset_level:
        args.reset_level = explicit_reset_level_value
    if explicit_max_level:
        args.max_level = explicit_max_level_value
    if explicit_max_segments:
        args.max_segments = explicit_max_segments_value
    apply_growth_speed_profile(args, explicit_options)
    args.checkpoint_levels_parsed = parse_checkpoint_levels(args.checkpoint_levels)
    if args.checkpoint_levels_parsed:
        if args.resume:
            raise SystemExit("--checkpoint-levels cannot be combined with --resume")
        if not explicit_max_segments:
            args.max_segments = len(args.checkpoint_levels_parsed)
        if not explicit_inter_segment_delay:
            args.inter_segment_delay = 0.0
    args.mysql_bin = resolve_mysql_bin(args.mysql_bin)
    if args.resume:
        args.skip_provision = True
        args.reset_progress = False
        args.replace = False
        if args.run_dir is None:
            raise SystemExit("--resume requires --run-dir")
    if args.smoke:
        args.realms = "alb"
        args.party_sizes = "1"
        if not explicit_segment_seconds:
            args.segment_seconds = min(args.segment_seconds, 45)
        args.max_segments = 1
        args.once = True
        args.parallel_cases = 1
    if args.fast_flee_debug:
        args.party_sizes = "1"
        if not explicit_segment_seconds:
            args.segment_seconds = min(args.segment_seconds, 90)
        args.max_segments = 1
        args.once = True
        args.parallel_cases = 1
        args.watch_movement = False
        args.live_supervisor = False
        args.require_segment_kill = False
        args.post_segment_snapshot_delay = 0.0
        args.post_segment_snapshot_timeout = 0.0
        args.post_segment_snapshot_poll_interval = 0.5
        args.ramp_up = min(args.ramp_up, 2)
        args.startup_delay = min(args.startup_delay, 4.0)
    if args.parallel_cases < 1:
        raise SystemExit("--parallel-cases must be positive")
    if args.case_repeats < 1:
        raise SystemExit("--case-repeats must be positive")
    if args.reset_level < 1:
        raise SystemExit("--reset-level must be positive")
    if args.first_segment < 0:
        raise SystemExit("--first-segment cannot be negative")
    if args.growth_party_carry_count < -1:
        raise SystemExit("--growth-party-carry-count cannot be less than -1")
    if args.first_segment and args.resume:
        raise SystemExit("--first-segment cannot be combined with --resume")
    if args.case_name:
        selected_realms = parse_csv_list(args.realms)
        party_sizes = parse_int_list(args.party_sizes)
        if len(selected_realms) * len(party_sizes) * args.case_repeats != 1:
            raise SystemExit("--case-name requires exactly one realm/party/repeat case")
    return args


def parse_args_for_tests(argv: list[str]) -> argparse.Namespace:
    return parse_args(argv)


def validate_growth_suite_runtime(args: argparse.Namespace, *, platform: str = sys.platform) -> None:
    if platform.startswith("win") and not args.dry_run:
        raise SystemExit(
            "Run dummy growth suites from WSL bash so DB and nav API both use the verified localhost path. "
            "Example: bash -lc \"cd /mnt/c/Users/uihan/Desktop/다옥프리서버/OpenDAoC-Core && "
            "python3 tools/run-dummy-growth-suite.py --growth-stage train --realms alb --party-sizes 1 --start 1\""
        )


def main() -> int:
    args = parse_args()
    validate_growth_suite_runtime(args)
    selected_realms = parse_csv_list(args.realms)
    party_sizes = parse_int_list(args.party_sizes)
    unknown = [realm for realm in selected_realms if realm not in REALMS]
    if unknown:
        raise SystemExit(f"unknown realm key(s): {', '.join(unknown)}")
    if not Path(args.mysql_bin).exists() and not args.dry_run:
        raise SystemExit(f"mysql client not found: {args.mysql_bin}")
    cases = build_case_plan(selected_realms, party_sizes, case_repeats=args.case_repeats)

    output_dir = args.run_dir if args.run_dir is not None else args.output_root / timestamp()
    output_dir.mkdir(parents=True, exist_ok=True)
    path_graph = output_dir / "growth-route-graph.json"
    write_growth_path_graph(
        path_graph,
        ground_z_offset=args.ground_z_offset,
        growth_hunting_index=getattr(args, "growth_hunting_index", ""),
    )
    timeline_csv = output_dir / "timeline.csv"
    metadata = {
        "started_at_utc": utc_now(),
        "realms": selected_realms,
        "party_sizes": party_sizes,
        "segment_seconds": args.segment_seconds,
        "max_segments": args.max_segments,
        "max_level": args.max_level,
        "growth_stage": args.growth_stage,
        "growth_speed_profile": args.growth_speed_profile,
        "growth_hunting_index": getattr(args, "growth_hunting_index", ""),
        "growth_fast_travel": getattr(args, "growth_fast_travel", "off"),
        "checkpoint_levels": getattr(args, "checkpoint_levels_parsed", []),
        "case_repeats": args.case_repeats,
        "cases": len(cases),
        "parallel_cases": min(args.parallel_cases, len(cases)) if cases else 0,
        "dry_run": args.dry_run,
        "path_graph": str(path_graph),
    }
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")

    exit_code = run_case_plan(
        args=args,
        cases=cases,
        output_dir=output_dir,
        path_graph=path_graph,
        timeline_csv=timeline_csv,
    )

    write_case_summary(output_dir / "case-summary.csv", timeline_csv)
    write_summary(output_dir / "summary.md", timeline_csv, metadata)
    print(f"growth suite output: {output_dir}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
