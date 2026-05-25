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
import threading
import time
from dataclasses import dataclass
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
COPPER_PER_SILVER = 100
COPPER_PER_GOLD = 10_000
COPPER_PER_PLATINUM = 10_000_000
TIMELINE_WRITE_LOCK = threading.Lock()
GROWTH_STAGE_DEFAULTS = {
    "custom": None,
    "stabilize": {"reset_level": 1, "max_level": 4, "segment_seconds": 90, "max_segments": 1},
    "train": {"reset_level": 5, "max_level": 6, "segment_seconds": 120, "max_segments": 2},
    "gear": {"reset_level": 6, "max_level": 10, "segment_seconds": 300, "max_segments": 10},
    "long": {"reset_level": 10, "max_level": 50, "segment_seconds": 600, "max_segments": 60},
}
EQUIPMENT_SLOTS = {7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 21, 22, 23, 24, 25, 26, 27, 28, 29, 32, 33, 34, 35, 36, 37}
BACKPACK_FIRST_SLOT = 40
BACKPACK_LAST_SLOT = 79
ARMOR_OBJECT_TYPE_MIN = 31
ARMOR_OBJECT_TYPE_MAX = 38
SHIELD_OBJECT_TYPE = 42
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


@dataclass(frozen=True)
class GrowthItemPlan:
    equip_slots: list[int]
    sell_slots: list[int]
    equip_reason: str = ""
    sell_reason: str = ""


def route_point(
    level: int,
    x: int,
    y: int,
    z: int,
    prefer: str = "",
    avoid: str = "",
    teleport_destination: str = "",
    objective_adds: str = "",
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
    return bool(getattr(args, "growth_start_base_classes", True)) and int(getattr(args, "reset_level", 1) or 1) < 5


def strict_route_target_name(route: RoutePoint, current_level: int) -> str:
    if current_level >= 10 and route.prefer:
        return route.prefer
    return ""


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
            route_point(2, 534900, 478900, 2310, "small gray wolf,skeleton,black wolf pup", "young cutpurse,green snake"),
            route_point(3, 534900, 478900, 2310, "small gray wolf,skeleton,black wolf pup", "young cutpurse,green snake"),
            route_point(5, 533895, 472812, 2654, "shady pilferer,spriggarn stalker,skeleton", "young cutpurse,river drakeling,river sprite,bear,carrion drake"),
            route_point(
                10,
                517187,
                627281,
                1701,
                "sylvan goblin warrior",
                "devout filidh,sylvan goblin chief,wood ogre,bloated spider,red lion",
                teleport_destination="Caer Ulfwych",
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
                504923,
                344510,
                2833,
                "Tylwyth Teg ranger",
                "ellyll sage,cyhraeth,ravenclan giant",
                teleport_destination="Snowdonia Fortress",
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
        growth_class_cycle="22|26|31|24|22|28|29|26",
        growth_race_cycle="5|7|6|5|7|8|5|7",
        growth_spec_cycle=(
            "Hammer|50;Shields|42;Parry|39;Sword|1;Axe|1;Thrown Weapons|1||"
            "Mending|40;Augmentation|36;Pacification|1||"
            "Axe|50;Left Axe|50;Parry|28;Sword|1;Hammer|1||"
            "Sword|44;Battlesongs|46;Parry|21;Hammer|1;Axe|1||"
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
                765794,
                742802,
                5205,
                "impling",
                "small hill cat,young lynx,green serpent,lupine snarler,young sveawolf,vein spiderling,harvestman,wildling",
            ),
            route_point(
                6,
                783163,
                751764,
                5074,
                "vein spider",
                "small hill cat,young lynx,green serpent,lupine snarler,young sveawolf",
            ),
            route_point(10, 800176, 675574, 5316, "wolf spiderling", teleport_destination="Fort Veldon"),
            route_point(15, 736792, 836202, 5159, teleport_destination="Fort Veldon"),
            route_point(20, 783734, 797071, 5282, teleport_destination="Audliten"),
            route_point(25, 779270, 829104, 4856, teleport_destination="Huginfell"),
            route_point(30, 733576, 760848, 5342, teleport_destination="Fort Atla"),
            route_point(35, 709212, 769221, 5283, teleport_destination="Gna Faste"),
            route_point(40, 681918, 728644, 5595, teleport_destination="Vindsaul Faste"),
            route_point(45, 674302, 736960, 5227, teleport_destination="Raumarik"),
            route_point(
                50,
                664136,
                726812,
                6510,
                "fenrir tracker",
                "wyvern,torpor worm,winter wolf,bone-eater clanmother,ghostly Hibernian invader",
                teleport_destination="Vindsaul Faste",
                objective_adds="fenrir snowscout,fenrir prophet",
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
        growth_class_cycle="44|47|43|45|48|40|41|47",
        growth_race_cycle="9|9|9|9|9|11|11|9",
        growth_spec_cycle=(
            "Blades|50;Shields|42;Parry|39;Large Weapons|1;Celtic Spear|1||"
            "Regrowth|40;Nurture|36;Nature|1||"
            "Blades|50;Celtic Dual|50;Parry|28;Shields|1||"
            "Large Weapons|50;Valor|40;Parry|23;Shields|1;Blades|1||"
            "Music|43;Nurture|37;Regrowth|33;Blades|1||"
            "Light|50;Mana|15;Void|10||"
            "Mana|50;Enchantments|20;Light|1||"
            "Regrowth|40;Nurture|36;Nature|1"
        ),
        start=(344500, 474500, 5372),
        points=(
            route_point(1, 344500, 474500, 5372, "large frog,skeletal pawn,water beetle larva", "feccan,annoying lucradan,ambient,Lance Settler,lunantishee,blackthorn"),
            route_point(2, 345100, 474178, 5473, "villainous youth,skeletal pawn,water beetle larva", "feccan,annoying lucradan,ambient,Lance Settler,lunantishee,blackthorn"),
            route_point(3, 347024, 473748, 6055, "mudman,villainous youth,skeletal pawn", "feccan,annoying lucradan,ambient,Lance Settler,lunantishee,blackthorn"),
            route_point(5, 348637, 479175, 5742, "eirebug,spraggon,large frog", "feccan,lough wolf,wild crouch,water beetle"),
            route_point(8, 292688, 648549, 4928, "water beetle", teleport_destination="Connla"),
            route_point(10, 292688, 648549, 4928, "water beetle", teleport_destination="Connla"),
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
        1: route_point(1, 534900, 477500, 2200, "black wolf pup", "young cutpurse,weak skeleton,green snake,small gray wolf"),
        2: route_point(1, 534250, 478100, 2200, "boar piglet,black wolf pup", "young cutpurse,weak skeleton,green snake,small gray wolf"),
        4: route_point(1, 534520, 477220, 2200, "black wolf pup", "young cutpurse,weak skeleton,green snake,small gray wolf"),
        8: route_point(1, 534650, 477500, 2200, "black wolf pup", "young cutpurse,weak skeleton,green snake,small gray wolf"),
    },
    "mid": {
        1: route_point(1, 770900, 746700, 4620, "young sveawolf", "soft-shelled crab,vein spiderling,lupine gnawer,lupine snarler"),
        2: route_point(1, 775980, 751320, 4538, "soft-shelled crab", "sveawolf cub,vein spiderling,lupine gnawer,lupine snarler"),
        4: route_point(1, 775217, 751401, 4390, "soft-shelled crab", "sveawolf cub,vein spiderling,lupine gnawer,lupine snarler"),
        8: route_point(1, 776800, 752135, 4595, "sveawolf cub", "soft-shelled crab,vein spiderling,lupine gnawer,lupine snarler"),
    },
    "hib": {
        1: route_point(1, 344500, 474500, 5372, "large frog,skeletal pawn,water beetle larva", "feccan,annoying lucradan,ambient,Lance Settler,lunantishee,blackthorn"),
        2: route_point(1, 344500, 474500, 5372, "large frog,skeletal pawn,water beetle larva", "feccan,annoying lucradan,ambient,Lance Settler,lunantishee,blackthorn"),
        4: route_point(1, 344500, 474500, 5372, "large frog,skeletal pawn,water beetle larva", "feccan,annoying lucradan,ambient,Lance Settler,lunantishee,blackthorn"),
        8: route_point(1, 344500, 474500, 5372, "large frog,skeletal pawn,water beetle larva", "feccan,annoying lucradan,ambient,Lance Settler,lunantishee,blackthorn"),
    },
}


LEVEL_TEN_PARTY_ROUTE_VARIANTS: dict[str, dict[int, RoutePoint]] = {
    "alb": {
        2: route_point(
            10,
            517187,
            627281,
            1701,
            "sylvan goblin warrior",
            "devout filidh,sylvan goblin chief,wood ogre,bloated spider,red lion",
            teleport_destination="Caer Ulfwych",
        ),
        4: route_point(10, 511763, 615379, 1779, "wild boar", "brownie,river sprite,bandit", teleport_destination="Caer Ulfwych"),
        8: route_point(10, 511763, 615379, 1779, "wild boar", "brownie,river sprite,bandit", teleport_destination="Caer Ulfwych"),
    },
    "mid": {
        2: route_point(10, 772717, 833982, 4374, "spindly rock crab", "perfidious pook,tawny lynx,army ant soldier,army ant worker", teleport_destination="Gotar"),
        4: route_point(10, 772717, 833982, 4374, "spindly rock crab", "perfidious pook,tawny lynx,army ant soldier,army ant worker", teleport_destination="Gotar"),
        8: route_point(10, 772717, 833982, 4374, "spindly rock crab", "perfidious pook,tawny lynx,army ant soldier,army ant worker", teleport_destination="Gotar"),
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


def read_serverconfig_password() -> str:
    config_path = ROOT / "CoreServer" / "config" / "serverconfig.xml"
    if not config_path.exists():
        return "opendaoc-local"
    text = config_path.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r"Password=([^;]+)", text)
    return match.group(1) if match else "opendaoc-local"


def run_mysql(args: argparse.Namespace, sql: str) -> str:
    env = os.environ.copy()
    env["MYSQL_PWD"] = args.db_password
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
        "--default-character-set=utf8mb4",
        args.db_name,
        "-e",
        sql,
    ]
    return subprocess.run(command, check=True, capture_output=True, text=True, env=env).stdout


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


def money_to_copper(row: dict[str, str]) -> int:
    return (
        to_int(row.get("Copper"))
        + to_int(row.get("Silver")) * COPPER_PER_SILVER
        + to_int(row.get("Gold")) * COPPER_PER_GOLD
        + to_int(row.get("Platinum")) * COPPER_PER_PLATINUM
    )


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
    if not checkpoint_levels:
        return 1
    return max(1, min(len(checkpoint_levels), max(1, int(max_segments))))


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
    if account.lower().startswith("dummy"):
        return "Dummy" + account[5:]
    return account[:1].upper() + account[1:]


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


def item_target_slot(item: InventoryItem) -> int | None:
    if item.item_type not in EQUIPMENT_SLOTS or item.object_type <= 0:
        return None
    return item.item_type


def is_backpack_slot(slot: int) -> bool:
    return BACKPACK_FIRST_SLOT <= slot <= BACKPACK_LAST_SLOT


def is_armor_or_shield(item: InventoryItem) -> bool:
    return ARMOR_OBJECT_TYPE_MIN <= item.object_type <= ARMOR_OBJECT_TYPE_MAX or item.object_type == SHIELD_OBJECT_TYPE


def is_growth_auto_equip_safe(item: InventoryItem) -> bool:
    return is_armor_or_shield(item)


def item_score(item: InventoryItem) -> int:
    stat = max(0, item.dps_af)
    quality = max(0, item.quality)
    bonus = max(0, item.bonus)
    level = max(0, item.level)
    if is_armor_or_shield(item):
        return stat * 1000 + quality * 10 + bonus * 25 + level
    speed_bonus = max(0, 100 - item.spd_abs)
    return stat * 1000 + quality * 10 + bonus * 30 + level + speed_bonus


def build_growth_item_plan(items: list[InventoryItem], *, class_id: int, level: int) -> GrowthItemPlan:
    equipped_by_slot: dict[int, InventoryItem] = {
        item.slot: item for item in items if item.slot in EQUIPMENT_SLOTS
    }
    equip_slots: list[int] = []
    sell_slots: list[int] = []
    equip_reasons: list[str] = []
    sell_reasons: list[str] = []

    for item in sorted((candidate for candidate in items if is_backpack_slot(candidate.slot)), key=lambda candidate: candidate.slot):
        target_slot = item_target_slot(item)
        if target_slot is None:
            continue
        if not class_allows_item(item.allowed_classes, class_id):
            sell_slots.append(item.slot)
            sell_reasons.append(f"{item.slot}:{item.name}:class")
            continue
        if item.level > max(1, level):
            continue
        if not is_growth_auto_equip_safe(item):
            sell_reasons.append(f"{item.slot}:{item.name}:manual_weapon_check")
            continue
        equipped = equipped_by_slot.get(target_slot)
        equipped_score = item_score(equipped) if equipped else 0
        candidate_score = item_score(item)
        if candidate_score > equipped_score:
            equip_slots.append(item.slot)
            equip_reasons.append(f"{item.slot}->{target_slot}:{candidate_score}>{equipped_score}")
            equipped_by_slot[target_slot] = item
        elif item.sell_price > 0 and candidate_score <= equipped_score:
            sell_slots.append(item.slot)
            sell_reasons.append(f"{item.slot}:{item.name}:worse")

    return GrowthItemPlan(
        equip_slots=sorted(set(equip_slots)),
        sell_slots=sorted(set(sell_slots) - set(equip_slots)),
        equip_reason=";".join(equip_reasons),
        sell_reason=";".join(sell_reasons),
    )


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
            COALESCE(iu.Object_Type, it.Object_Type, 0) AS ObjectType,
            COALESCE(iu.Item_Type, it.Item_Type, 0) AS ItemType,
            COALESCE(iu.Quality, it.Quality, 0) AS Quality,
            COALESCE(iu.Bonus, it.Bonus, 0) AS Bonus,
            COALESCE(iu.AllowedClasses, it.AllowedClasses, '') AS AllowedClasses,
            COALESCE(inv.Count, 1) AS ItemCount,
            COALESCE(inv.SellPrice, iu.Price, it.Price, 0) AS SellPrice
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
                object_type=to_int(row.get("ObjectType")),
                item_type=to_int(row.get("ItemType")),
                quality=to_int(row.get("Quality")),
                bonus=to_int(row.get("Bonus")),
                allowed_classes=row.get("AllowedClasses", ""),
                count=to_int(row.get("ItemCount")),
                sell_price=to_int(row.get("SellPrice")),
            )
        )
    return by_account


def build_growth_item_plans(
    args: argparse.Namespace,
    accounts: Iterable[str],
    snapshots: dict[str, CharacterSnapshot],
) -> dict[str, GrowthItemPlan]:
    if args.dry_run:
        return {}
    inventory_by_account = snapshot_inventory_items(args, accounts)
    plans: dict[str, GrowthItemPlan] = {}
    for account, items in inventory_by_account.items():
        snapshot = snapshots.get(account)
        if snapshot is None:
            continue
        plans[account] = build_growth_item_plan(items, class_id=snapshot.class_id, level=snapshot.level)
    return plans


def union_plan_slots(plans: dict[str, GrowthItemPlan], attr: str, fallback: list[int] | None = None) -> list[int]:
    slots: set[int] = set()
    for plan in plans.values():
        slots.update(getattr(plan, attr))
    if not slots and fallback:
        slots.update(fallback)
    return sorted(slots)


def reset_growth_characters(
    args: argparse.Namespace,
    accounts: Iterable[str],
    level: int = 1,
    realm: RealmProfile | None = None,
    target_specs_by_account: dict[str, str] | None = None,
) -> None:
    account_names = [account for account in accounts if account]
    if not account_names:
        return
    quoted = ", ".join(sql_quote(account) for account in account_names)
    reset_level = max(1, level)
    reset_experience = experience_floor_for_level(reset_level)
    position_assignments = ""
    if realm is not None:
        base_x, base_y, base_z = realm.start
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
    sql = f"""
        UPDATE DOLCharacters
        SET
            Level = {reset_level},
            Experience = {reset_experience},
            Health = 1000000,
            Mana = 1000000,
            MaxEndurance = GREATEST(MaxEndurance, 100),
            Endurance = 1000000,
            PlayedTimeSinceLevel = 0,
            DeathCount = 0,
            Copper = 0,
            Silver = 0,
            Gold = 0,
            Platinum = 0,
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
        if reset_level >= 50
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
    if level <= 1 and party_size > 0:
        route = LEVEL_ONE_PARTY_ROUTE_VARIANTS.get(realm.key, {}).get(party_size)
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


def route_variant_node_id(realm: RealmProfile, point: RoutePoint) -> str:
    return f"{realm.key}_{point.level}_{point.x}_{point.y}"


def route_variant_points_for_graph(realm: RealmProfile) -> list[RoutePoint]:
    seen = {(point.level, point.x, point.y, point.z) for point in realm.points}
    variants: list[RoutePoint] = []
    for variant_group in (LEVEL_ONE_PARTY_ROUTE_VARIANTS, LEVEL_TEN_PARTY_ROUTE_VARIANTS):
        for _party_size, variant in sorted(variant_group.get(realm.key, {}).items()):
            key = (variant.level, variant.x, variant.y, variant.z)
            if key in seen:
                continue
            variants.append(variant)
            seen.add(key)
    return variants


def route_variant_travel_detours(realm: RealmProfile, source_id: str, variant: RoutePoint) -> tuple[RoutePoint, ...]:
    if (
        realm.key == "hib"
        and source_id == "hib_teleport_tir_na_mbeo"
        and variant.level == 10
        and variant.x == 336157
        and variant.y == 532604
    ):
        return (
            RoutePoint(0, 333500, 529000, 5278),
            RoutePoint(0, 333500, 531300, 5349),
        )
    return ()


def target_levels(level: int, party_size: int) -> tuple[int, int, int]:
    player_level = max(1, min(level, 50))
    if player_level <= 1:
        if party_size <= 1:
            return 1, 1, 0
        if party_size <= 2:
            return 1, 2, 1
        if party_size <= 4:
            return 1, 3, 2
        return 1, 4, 3

    if player_level < 5:
        if party_size <= 1:
            return max(1, player_level - 2), player_level, 0
        if party_size <= 2:
            return max(1, player_level - 1), min(50, player_level + 1), 1
        if party_size <= 4:
            return max(1, player_level - 1), min(50, player_level + 2), 2
        return max(1, player_level - 1), min(50, player_level + 3), 3

    if player_level == 5 and party_size <= 1:
        return 4, 5, 1

    if player_level == 6 and party_size <= 1:
        return 4, 5, 1

    if player_level <= 7 and party_size <= 1:
        target = max(1, player_level - 1)
        return target, target, 0

    if player_level <= 10 and party_size <= 1:
        target = max(1, player_level - 2)
        if player_level == 10:
            return max(1, target - 1), target, 1
        return max(1, target - 1), target, 0

    if player_level == 10 and party_size <= 2:
        return 8, 9, 0

    if 5 <= player_level <= 10 and party_size <= 2:
        return max(1, player_level - 1), player_level, 0

    if player_level >= 50:
        if party_size <= 2:
            return 46, 47, 1
        return 46, 48, 2

    ideal_bonus = 1 if party_size == 1 else 1 if party_size <= 2 else 2 if party_size <= 4 else 3
    max_delta = 1 if party_size == 1 else 2 if party_size <= 2 else 3 if party_size <= 4 else 5
    return max(1, player_level - 1), min(50, player_level + ideal_bonus), max_delta


def target_max_level(level: int, ideal_target: int, max_delta: int) -> int:
    if max_delta <= 0:
        return max(0, int(ideal_target))
    if int(ideal_target) < int(level):
        return min(50, max(1, int(ideal_target) + int(max_delta)))
    return min(50, max(1, int(level)) + int(max_delta))


def early_growth_party_slot_rotations(level: int, party_size: int) -> str:
    if level50_party_boss_rules_enabled(level, party_size) and party_size == 4:
        return "melee-basic,healer-support,melee-basic,melee-burst"
    if party_size <= 1 or level > 4:
        return ""
    return "melee-basic,melee-burst"


def party_min_ready(level: int, party_size: int) -> int:
    if party_size <= 1:
        return party_size
    if level <= 4:
        return min(party_size, 4)
    return party_size


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
    return 5 <= int(level) < 50


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


def train_verified(before: CharacterSnapshot | None, after: CharacterSnapshot | None, current_level: int) -> bool:
    if not should_train_at_level(current_level) or before is None or after is None:
        return False
    if after.class_id != before.class_id:
        return True
    return bool(spec_gain_summary(before.specs, after.specs))


def target_growth_class_id(row: dict[str, str]) -> int:
    return to_int(row.get("class_id"))


def is_base_class_for_target(current_class_id: int, target_class_id: int) -> bool:
    return BASE_CLASS_BY_TARGET_CLASS.get(target_class_id) == current_class_id


def promote_growth_classes_for_level(args: argparse.Namespace, account_rows: list[dict[str, str]], current_level: int) -> int:
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
        specs = baseline_specs(row.get("specs", ""))
        spec_sql = f", SerializedSpecs = {sql_quote(specs)}" if specs else ""
        updates.append(
            "UPDATE DOLCharacters "
            f"SET Class = {target_class_id}{spec_sql} "
            f"WHERE AccountName = {sql_quote(account)} AND Class = {base_class_id};"
        )

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


def growth_target_home_max_distance(args: argparse.Namespace, level: int, party_size: int = 0) -> float:
    base = float(getattr(args, "target_home_max_distance", 0.0) or 0.0)
    if level == 10 and party_size > 1 and base > 0.0:
        return min(base, 1800.0)
    if level >= 45:
        return max(base, 2800.0)
    if level <= 10:
        return max(base, 6200.0)
    return base


def growth_max_target_distance(args: argparse.Namespace, level: int, party_size: int = 0) -> float:
    base = float(getattr(args, "max_target_distance", 0.0) or 0.0)
    if level <= 4 and base > 0.0:
        return min(base, 1500.0)
    if level <= 9 and base > 0.0:
        return 2800.0
    if level == 10 and party_size > 1 and base > 0.0:
        return min(base, 1500.0)
    return base


def growth_combat_home_leash_distance(args: argparse.Namespace, level: int, party_size: int = 0) -> float:
    base = float(getattr(args, "combat_home_leash_distance", 1200.0) or 0.0)
    if level == 10 and party_size > 1:
        return min(max(base, 1800.0), 1800.0)
    if level >= 45:
        return max(base, 2800.0)
    if level <= 10:
        return max(base, 6200.0)
    return base


def growth_combat_direct_move_distance(args: argparse.Namespace, level: int, party_size: int = 0) -> float:
    base = 1500.0
    if level <= 10:
        return max(base, growth_max_target_distance(args, level, party_size))
    return base


def growth_required_target_home_hunt_distance(args: argparse.Namespace, level: int, party_size: int = 0) -> float:
    return max(900.0, growth_combat_home_leash_distance(args, level, party_size))


def growth_hunter_target_api_radius(args: argparse.Namespace, level: int) -> float:
    if 5 <= level <= 9:
        return growth_max_target_distance(args, level)
    return 2200.0


def growth_hunter_target_api_engage_distance(args: argparse.Namespace, level: int) -> float:
    if 5 <= level <= 9:
        return growth_max_target_distance(args, level)
    return 1500.0


def growth_combat_chase_max_distance(level: int) -> float:
    if level <= 4:
        return 2200.0
    return 0.0


def waypoint_string(realm: RealmProfile, level: int, party_size: int = 0, *, ground_z_offset: int = 0) -> str:
    point = select_route_point(realm, level, party_size)
    height_samplers = build_realm_height_samplers()
    waypoints: list[str] = []
    for dx, dy in waypoint_offsets(level):
        x = point.x + dx
        y = point.y + dy
        z = sample_route_z(realm, height_samplers, x, y, point.z, ground_z_offset=ground_z_offset)
        waypoints.append(f"{x},{y},{z}")
    return "|".join(waypoints)


def route_home_string(realm: RealmProfile, level: int, party_size: int = 0, *, ground_z_offset: int = 0) -> str:
    point = select_route_point(realm, level, party_size)
    z = sample_route_z(
        realm,
        build_realm_height_samplers(),
        point.x,
        point.y,
        point.z,
        ground_z_offset=ground_z_offset,
    )
    return f"{point.x},{point.y},{z}"


def growth_flee_home_string(
    realm: RealmProfile,
    level: int,
    party_size: int = 0,
    *,
    ground_z_offset: int = 0,
) -> str:
    route = select_route_point(realm, level, party_size)
    if level >= 10 and route.teleport_destination:
        destination = teleport_destination_point(realm, route.teleport_destination)
        if destination is not None:
            x, y, z = destination
            return f"{x},{y},{z + ground_z_offset}"
    return f"{realm.start[0]},{realm.start[1]},{realm.start[2] + ground_z_offset}"


def growth_flee_town_health_percent(level: int) -> int:
    return 99 if level >= 10 else 10


def growth_flee_home_stop_distance(level: int) -> int:
    return 120 if level >= 10 else 900


def growth_required_target_tank_commit_health_percent(level: int, party_size: int) -> int:
    if level <= 10 and party_size > 1:
        return 70
    return 55


def watcher_observer_home_string(
    realm: RealmProfile,
    level: int,
    party_size: int = 0,
    *,
    observer_distance: float = 5000.0,
    ground_z_offset: int = 0,
) -> str:
    point = select_route_point(realm, level, party_size)
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


def write_growth_path_graph(path: Path, *, ground_z_offset: int = 0) -> None:
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
            steps = max(1, int(distance // 350) + 1)
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
        add_node(start_id, realm.start[0], realm.start[1], realm.start[2], sample_height=False)
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
            source=RoutePoint(0, realm.start[0], realm.start[1], realm.start[2]),
            dest_id=hub_id,
            dest=RoutePoint(0, hub_x, hub_y, hub_z),
            mid_prefix=f"{realm.key}_start_teleporter_hub",
        )
        previous_node_id = start_id
        variant_points = route_variant_points_for_graph(realm)

        for index, point in enumerate(realm.points):
            node_id = f"{realm.key}_{point.level}"
            add_node(node_id, point.x, point.y, point.z, sample_height=False)
            if point.teleport_destination:
                destination = destination_nodes.get(normalize_teleport_destination(point.teleport_destination))
                if destination is not None:
                    destination_id, destination_point = destination
                    add_segment(
                        source_id=destination_id,
                        source=destination_point,
                        dest_id=node_id,
                        dest=point,
                        mid_prefix=f"{realm.key}_teleport_{normalize_identifier(point.teleport_destination)}_{point.level}",
                        sample_mid_height=point.level >= 50,
                    )
            if index > 0:
                source = realm.points[index - 1]
                source_node_id = previous_node_id or f"{realm.key}_{source.level}"
            else:
                source = RoutePoint(0, realm.start[0], realm.start[1], realm.start[2])
                source_node_id = previous_node_id
            if index > 0 or previous_node_id == start_id:
                add_segment(
                    source_id=source_node_id,
                    source=source,
                    dest_id=node_id,
                    dest=point,
                    mid_prefix=f"{realm.key}_{source.level}_{point.level}",
                )
            previous_node_id = node_id

        for variant in variant_points:
            variant_id = route_variant_node_id(realm, variant)
            add_node(variant_id, variant.x, variant.y, variant.z, sample_height=False)
            source_id = start_id
            source = RoutePoint(0, realm.start[0], realm.start[1], realm.start[2])
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


def build_behavior_command(
    args: argparse.Namespace,
    realm: RealmProfile,
    accounts_csv: Path,
    case_dir: Path,
    segment_index: int,
    party_size: int,
    current_level: int,
    path_graph: Path,
) -> list[str]:
    min_target, ideal_target, max_delta = target_levels(current_level, party_size)
    metrics_csv = case_dir / f"segment-{segment_index:03d}-metrics.csv"
    combat_csv = case_dir / f"segment-{segment_index:03d}-combat.csv"
    report_md = case_dir / f"segment-{segment_index:03d}-report.md"
    live_control_json = case_dir / "live-control.json"
    trace_pattern = case_dir / "movement" / f"segment-{segment_index:03d}-{{username}}-{{round}}.jsonl"
    encounter_pattern = case_dir / "encounters" / f"segment-{segment_index:03d}-{{username}}-{{round}}.jsonl"
    trace_pattern.parent.mkdir(parents=True, exist_ok=True)
    encounter_pattern.parent.mkdir(parents=True, exist_ok=True)
    live_control_json.write_text(
        json.dumps(
            {
                "revision": f"segment-{segment_index:03d}-level-{current_level}",
                "baseline_min_target_level": min_target,
                "baseline_max_target_level": target_max_level(current_level, ideal_target, max_delta),
                "baseline_player_level": current_level,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    route = select_route_point(realm, current_level, party_size)
    level50_boss_party = level50_party_boss_rules_enabled(current_level, party_size)
    party_assist_interval = "0.6" if level50_boss_party else "3"
    party_form_up_delay = "8" if level50_boss_party else "4"
    party_rescue_max_age = "14" if level50_boss_party else "10"
    party_rescue_assist_after = "3" if level50_boss_party else "6"
    action_rotation = solo_action_rotation_for_accounts(accounts_csv, party_size)
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
        str(args.segment_seconds),
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
        "--hunter",
        "--behavior-profile",
        "solo-melee" if party_size == 1 else "party-dps",
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
        str(target_max_level(current_level, ideal_target, max_delta)),
        "--max-target-level-delta",
        str(max_delta),
        "--max-target-distance",
        str(growth_max_target_distance(args, current_level, party_size)),
        "--target-home-max-distance",
        str(growth_target_home_max_distance(args, current_level, party_size)),
        "--combat-home-leash-distance",
        str(growth_combat_home_leash_distance(args, current_level, party_size)),
        "--combat-chase-max-distance",
        str(growth_combat_chase_max_distance(current_level)),
        "--combat-chase-max-distance-grace",
        "3",
        "--target-timeout",
        str(args.target_timeout),
        "--target-loss-grace",
        "1",
        "--reject-target-on-server-los-failure",
        "--server-los-failure-target-cooldown",
        "4",
        "--server-los-failure-grace",
        "10",
        "--target-selection",
        "smart",
        "--include-peace-npcs",
        "--current-target-api-refresh",
        "--hunter-target-api-scout",
        "--hunter-target-api-radius",
        str(growth_hunter_target_api_radius(args, current_level)),
        "--hunter-target-api-engage-distance",
        str(growth_hunter_target_api_engage_distance(args, current_level)),
        "--hunter-target-max-ground-z-delta",
        "220",
        "--hunter-min-time-left-for-new-target",
        "55",
        "--allow-avoid-target-fallback",
        "--combat-interval",
        str(args.combat_interval),
        "--target-pool",
        str(args.target_pool),
        "--attack-range",
        "350",
        "--combat-direct-move-distance",
        str(growth_combat_direct_move_distance(args, current_level, party_size)),
        "--attack-target-in-view-prime-delay",
        "1.1",
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
        str(args.path_last_mile_distance),
        "--path-node-arrival-distance",
        "80",
        "--path-max-height-delta",
        "900",
        "--path-waypoint-ground-z-skip-delta",
        "500",
        "--waypoints",
        waypoint_string(realm, current_level, party_size, ground_z_offset=args.ground_z_offset),
        "--waypoint-mode",
        "loop",
        "--waypoint-continuous-turns",
        "--waypoint-advance-distance",
        "35",
        "--waypoint-stop-distance",
        "12",
        "--required-target-home",
        route_home_string(realm, current_level, party_size, ground_z_offset=args.ground_z_offset),
        "--required-target-home-stop-distance",
        "900",
        "--required-target-home-hunt-distance",
        str(growth_required_target_home_hunt_distance(args, current_level, party_size)),
        "--required-target-recover-before-home-health-percent",
        "88",
        "--use-skills",
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
        "6",
        "--party-accept-interval",
        "3",
        "--party-assist-interval",
        party_assist_interval,
        "--party-follow-interval",
        "0.2",
        "--party-follow-step",
        "320",
        "--party-follow-distance",
        "500",
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
        "0.08",
        "--rest-min",
        "1",
        "--rest-max",
        "3",
        "--low-health-rest-percent",
        "70",
        "--low-health-rest-resume-percent",
        "88",
        "--low-health-rest-min",
        "6",
        "--low-health-rest-max",
        "14",
        "--flee-health-percent",
        "55",
        "--flee-pressure-health-percent",
        "85",
        "--flee-duration",
        "24",
        "--flee-step",
        "900",
        "--flee-move-interval",
        "0.35",
        "--flee-movement-speed",
        "360",
        "--flee-use-sprint",
        "--flee-home",
        growth_flee_home_string(realm, current_level, party_size, ground_z_offset=args.ground_z_offset),
        "--flee-home-stop-distance",
        str(growth_flee_home_stop_distance(current_level)),
        "--flee-dynamic-safe-point",
        "--flee-safe-threat-radius",
        "6000",
        "--flee-safe-point-distance",
        "5200",
        "--flee-critical-health-percent",
        "45",
        "--flee-critical-safe-point-distance",
        "9000",
        "--flee-safe-api-scout",
        "--flee-safe-replan-damage-grace",
        "6",
        "--travel-aggro-clear-grace",
        "24",
        "--travel-aggro-avoid-seconds",
        "150",
        "--travel-aggro-avoid-radius",
        "5200",
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
        "55",
        "--flee-melee-counterattack-max-distance",
        "1800",
        "--required-target-tank-commit-health-percent",
        str(growth_required_target_tank_commit_health_percent(current_level, party_size)),
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
        "--speak-state-changes",
        "--state-speech-min-interval",
        "3.0",
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
    if action_rotation == "caster-basic":
        command += ["--stationary-cast-actions", "--cast-action-hold", f"{CASTER_STATIONARY_CAST_HOLD_SECONDS:.1f}"]
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
    auto_equip_slots = getattr(args, "growth_auto_equip_slots", [])
    if auto_equip_slots:
        command += ["--startup-service-equip-slot", ",".join(str(slot) for slot in auto_equip_slots)]
    auto_sell_slots = getattr(args, "growth_auto_sell_slots", [])
    if auto_sell_slots:
        command += ["--startup-service-sell-slot", ",".join(str(slot) for slot in auto_sell_slots)]
    if should_train_at_level(current_level):
        command += ["--startup-auto-train", "--startup-train-level", str(current_level)]
    elif current_level >= 50:
        command += ["--startup-train-full-specs", "--startup-train-level", str(current_level)]
    teleport_destination = nearest_teleport_destination(realm, route) if current_level >= 10 else route.teleport_destination
    append_startup_teleport_command(command, args, teleport_destination, realm=realm)
    if args.nav_api_url:
        command += ["--nav-api-url", args.nav_api_url]
    if args.live_api_url:
        command += ["--live-api-url", args.live_api_url]
    required_target_name = strict_route_target_name(route, current_level)
    if required_target_name:
        command += ["--require-target-name", required_target_name]
    if route.prefer:
        command += ["--prefer-target-name", route.prefer, "--target-auto-lowest-visible-level"]
        if current_level >= 6:
            command += ["--allow-preferred-low-con-fallback", "--preferred-low-con-min-level", str(min_target)]
    if route.objective_adds:
        command += ["--objective-add-target-name", route.objective_adds]
    if route.avoid:
        command += ["--avoid-target-name", route.avoid]
    if party_size > 1:
        command += [
            "--party-assist-only",
            "--party-min-ready",
            str(party_min_ready(current_level, party_size)),
            "--party-form-up-delay",
            party_form_up_delay,
            "--party-ready-max-leader-distance",
            "1500",
            "--party-pre-pull-home-stop-distance",
            "1800",
            "--party-require-leader-engaged",
            "--party-mark-pull-engaged",
            "--party-pull-engage-distance",
            "1800",
            "--party-block-solo-required-retaliation",
            "--party-rescue-aggro",
            "--party-rescue-before-objective-engaged",
            "--party-clear-objective-adds-before-engage",
            "--party-local-rescue-target",
            "--party-local-rescue-max-distance",
            "900",
            "--party-healer-local-rescue-health-percent",
            "35",
            "--party-rescue-max-distance",
            "1400",
            "--party-rescue-engaged-distance",
            "350",
            "--party-rescue-objective-max-distance",
            "1800",
            "--party-rescue-min-hold",
            "4",
            "--party-rescue-max-age",
            party_rescue_max_age,
            "--party-rescue-assist-after",
            party_rescue_assist_after,
            "--party-rescue-emergency-assist-after",
            "2",
            "--party-active-tank-reaggro-taunt-interval",
            "0.8",
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
            ]
        slot_rotations = early_growth_party_slot_rotations(current_level, party_size)
        if slot_rotations:
            command += [
                "--party-slot-rotations",
                slot_rotations,
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
        "150",
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
    route = select_route_point(realm, current_level, party_size)
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
) -> list[str]:
    max_engage = float(getattr(args, "live_supervisor_max_engage", 2800.0) or 2800.0)
    if current_level is not None:
        level_max_engage = growth_max_target_distance(args, current_level, party_size)
        if level_max_engage > 0.0:
            max_engage = min(max_engage, level_max_engage)
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
        str(max(1.0, args.segment_seconds + getattr(args, "startup_delay", 0.0) + 8.0)),
    ]


def command_for_metadata(command: list[str]) -> str:
    redacted: list[str] = []
    skip_next = False
    for index, part in enumerate(command):
        if skip_next:
            skip_next = False
            continue
        if part == "--db-password":
            redacted += [part, "***"]
            skip_next = True
        elif index > 0 and command[index - 1] == "--db-password":
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


def should_equip_level50_party_gear(args: argparse.Namespace, *, current_level: int, party_size: int) -> bool:
    return bool(
        getattr(args, "level50_party_gear", True)
        and party_size >= 2
        and current_level >= 50
    )


def build_level50_party_gear_command(args: argparse.Namespace, accounts_csv: Path) -> list[str]:
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
        str(accounts_csv),
    ]
    return command


def run_commands_concurrently(commands: list[list[str]], dry_run: bool) -> int:
    if dry_run or len(commands) <= 1:
        rc = 0
        for command in commands:
            rc = max(rc, run_command(command, dry_run))
        return rc

    for command in commands:
        print(command_for_metadata(command))

    processes = [subprocess.Popen(command) for command in commands]
    rc = 0
    for process in processes:
        rc = max(rc, process.wait())
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

    for row in rows:
        event = str(row.get("event", ""))
        timestamp = numeric(row, "t")
        if timestamp > 0:
            last_event_at = timestamp

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
    if scan_empty_eligible_zero_events:
        reasons.append(f"scan_empty:{top_reason or 'unknown'}")
    if max_combat_gap >= 10.0:
        reasons.append("combat_gap")
    if idle_ready_ticks >= 3 and scan_empty_visible_events:
        reasons.append("idle_ready")

    return {
        "primary_idle_ready_ticks": idle_ready_ticks,
        "primary_scan_empty_visible_events": scan_empty_visible_events,
        "primary_scan_empty_eligible_zero_events": scan_empty_eligible_zero_events,
        "primary_scan_empty_top_reason": top_reason,
        "primary_combat_gap_max_seconds": max_combat_gap,
        "primary_anomaly_status": "warn" if reasons else "ok",
        "primary_anomaly_reason": ";".join(reasons),
    }


def preferred_target_tokens(prefer_target_name: str) -> list[str]:
    return [token.strip().lower() for token in prefer_target_name.split(",") if token.strip()]


def target_name_matches_any(name: str, tokens: list[str]) -> bool:
    normalized = name.lower()
    return bool(tokens and any(token in normalized for token in tokens))


def primary_behavior_anomaly_summary(path: Path, *, prefer_target_name: str = "") -> dict[str, object]:
    rows = jsonl_rows(path)
    prefer_tokens = preferred_target_tokens(prefer_target_name)
    reasons: set[str] = set()
    last_flee_at: float | None = None
    last_flee_x = 0.0
    last_flee_y = 0.0
    flee_window_recovered = False
    flee_window_aggro_not_dropped = False
    flee_window_too_short = False
    combat_attempts_by_target: dict[str, int] = {}
    weak_flee_finishes_by_target: dict[str, int] = {}

    for row in rows:
        event = str(row.get("event", ""))
        timestamp = numeric(row, "t")
        target_name = str(row.get("target_name") or row.get("active_target_name") or "")

        if event == "combat_start" and target_name:
            normalized_target = target_name.lower()
            combat_attempts_by_target[normalized_target] = combat_attempts_by_target.get(normalized_target, 0) + 1

        elif event == "combat_finish":
            outcome = str(row.get("outcome", ""))
            duration = numeric(row, "duration_seconds")
            damage_done = numeric(row, "damage_done")
            damage_taken = numeric(row, "damage_taken")
            if (
                target_name
                and outcome in {"flee", "target_timeout", "target_home_leash"}
                and duration >= 8.0
                and damage_taken >= 40.0
                and damage_done <= max(12.0, damage_taken * 0.35)
            ):
                normalized_target = target_name.lower()
                weak_flee_finishes_by_target[normalized_target] = weak_flee_finishes_by_target.get(normalized_target, 0) + 1

        elif event == "flee_start":
            last_flee_at = timestamp
            last_flee_x = numeric(row, "x")
            last_flee_y = numeric(row, "y")
            flee_window_recovered = False
            flee_window_aggro_not_dropped = False
            flee_window_too_short = False

        elif event == "flee_threat_pressure" and last_flee_at is not None:
            age = timestamp - last_flee_at
            threat_target = str(row.get("flee_threat_target", ""))
            character = str(row.get("character", ""))
            active = bool(row.get("flee_threat_active") or row.get("flee_threat_has_aggro") or row.get("flee_threat_in_combat"))
            if active and threat_target and character and threat_target.lower() == character.lower() and age >= 12.0:
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

        elif event == "flee_finished" and last_flee_at is not None:
            if not flee_window_recovered:
                if flee_window_aggro_not_dropped:
                    reasons.add("aggro_not_dropped")
                if flee_window_too_short:
                    reasons.add("flee_too_short")
            last_flee_at = None
            flee_window_recovered = False
            flee_window_aggro_not_dropped = False
            flee_window_too_short = False

        elif event == "low_health_rest":
            if row.get("flee_threat_active") or row.get("flee_threat_has_aggro") or row.get("flee_threat_target"):
                reasons.add("unsafe_rest")
            elif last_flee_at is not None:
                last_flee_at = None
                flee_window_recovered = False
                flee_window_aggro_not_dropped = False
                flee_window_too_short = False

    if last_flee_at is not None and not flee_window_recovered:
        if flee_window_aggro_not_dropped:
            reasons.add("aggro_not_dropped")
        if flee_window_too_short:
            reasons.add("flee_too_short")

    for target_name, weak_finishes in weak_flee_finishes_by_target.items():
        if weak_finishes >= 1 and combat_attempts_by_target.get(target_name, 0) >= 1:
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
    watcher = movement_pair_step_rows(watcher_path)
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
        "xy_status": "warn" if max_xy > xy_warn_delta else "ok",
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
    return {
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
    }


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
            ):
                summary[key] += to_int(row.get(key))
    return summary


def segment_regression_passed(metrics: dict[str, object], *, require_kill: bool) -> bool:
    if to_int(metrics.get("player_deaths")) > 0:
        return False
    if to_int(metrics.get("movement_failures")) > 0:
        return False
    if to_int(metrics.get("target_timeouts")) > 0:
        return False
    combat_failures = to_int(metrics.get("combat_failures"))
    if to_int(metrics.get("target_removed")) > 0:
        combat_failures = max(0, combat_failures - to_int(metrics.get("server_los_failures")))
    if combat_failures > 0:
        return False
    if require_kill and to_int(metrics.get("target_removed")) <= 0:
        return False
    return True


def segment_requires_kill(args: argparse.Namespace, current_level: int) -> bool:
    if not bool(getattr(args, "require_segment_kill", True)):
        return False
    return int(current_level) != 5


def segment_xp_regression_passed(xp_effective_delta: int | float, *, require_xp: bool) -> bool:
    if not require_xp:
        return True
    return to_int(xp_effective_delta) > 0


def segment_requires_xp(args: argparse.Namespace, current_level: int) -> bool:
    if not bool(getattr(args, "require_segment_xp", True)):
        return False
    level = int(current_level)
    if level == 5:
        return False
    if level >= 50:
        return False
    return True


def watcher_regression_passed(case_dir: Path, segment_index: int, watcher_pairs: list[tuple[str, str, Path]]) -> bool:
    for watcher_index, (_primary_account, _watcher_account, _watcher_csv) in enumerate(watcher_pairs):
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
            ):
                summary[key] += to_int(row.get(key))
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
        "train_command_sent",
        "train_verified",
        "equip_candidate_slots",
        "equip_candidate_reason",
        "sell_candidate_slots",
        "sell_candidate_reason",
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
        "player_deaths",
        "target_timeouts",
        "combat_failures",
        "server_los_failures",
        "target_home_leashes",
        "movement_failures",
        "loot_acquired",
        "levels_per_hour",
        "xp_per_hour",
        "text_xp_per_hour",
        "xp_effective_per_hour",
        "money_copper_per_hour",
        "inventory_items_per_hour",
        "target_removed_per_hour",
        "deaths_per_hour",
    ]
    with TIMELINE_WRITE_LOCK:
        exists = path.exists()
        with path.open("a", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerow(row)


def write_summary(report_path: Path, timeline_csv: Path, metadata: dict[str, object]) -> None:
    rows: list[dict[str, str]] = []
    if timeline_csv.exists():
        with timeline_csv.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    total_xp = sum(to_int(row.get("xp_delta")) for row in rows)
    total_text_xp = sum(to_int(row.get("text_xp_delta")) for row in rows)
    total_effective_xp = sum(to_int(row.get("xp_effective_delta")) for row in rows)
    total_train_verified = sum(to_int(row.get("train_verified")) for row in rows)
    total_money = sum(to_int(row.get("money_delta_copper")) for row in rows)
    total_items = sum(to_int(row.get("inventory_items_delta")) for row in rows)
    total_deaths = sum(to_int(row.get("death_delta")) for row in rows)
    levels = [to_int(row.get("level_after")) for row in rows]
    lines = [
        "# Dummy Growth Suite",
        "",
        f"- Started: `{metadata.get('started_at_utc', '')}`",
        f"- Cases: `{metadata.get('cases', 0)}`",
        f"- Timeline rows: `{len(rows)}`",
        f"- Highest observed level: `{max(levels) if levels else 0}`",
        f"- XP gained: `{total_xp}`",
        f"- Text XP gained: `{total_text_xp}`",
        f"- Effective XP gained: `{total_effective_xp}`",
        f"- Verified train/spec changes: `{total_train_verified}`",
        f"- Money gained copper: `{total_money}`",
        f"- Inventory item delta: `{total_items}`",
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
        "| Case | Account | Level | DB XP | Text XP | Effective XP | Train | Spec Gain | XP/h | Money Delta | Money/h | Items Delta | Deaths | Removed | Move Fail |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows[-20:]:
        lines.append(
            "| {case} | `{account}` | {level_after} | {xp_delta} | {text_xp_delta} | {xp_effective_delta} | "
            "{train_verified} | {spec_gain} | {xp_effective_per_hour} | {money_delta_copper} | "
            "{money_copper_per_hour} | {inventory_items_delta} | {death_delta} | {target_removed} | "
            "{movement_failures} |".format(**row)
        )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_case_summary(path: Path, timeline_csv: Path) -> None:
    rows: list[dict[str, str]] = []
    if timeline_csv.exists():
        with timeline_csv.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))

    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
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
                "death_delta": 0,
                "train_verified": 0,
                "target_removed": 0,
                "movement_failures": 0,
                "loot_acquired": 0,
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
            "death_delta",
            "train_verified",
            "target_removed",
            "movement_failures",
            "loot_acquired",
        ):
            if key == "elapsed_seconds":
                summary[key] = float(summary[key]) + float(row.get(key) or 0.0)
            else:
                summary[key] = int(summary[key]) + to_int(row.get(key))
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
        "death_delta",
        "train_verified",
        "target_removed",
        "movement_failures",
        "loot_acquired",
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
                    "death_delta": summary["death_delta"],
                    "train_verified": summary["train_verified"],
                    "target_removed": summary["target_removed"],
                    "movement_failures": summary["movement_failures"],
                    "loot_acquired": summary["loot_acquired"],
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


def run_case(
    args: argparse.Namespace,
    realm: RealmProfile,
    party_size: int,
    case_index: int,
    output_dir: Path,
    path_graph: Path,
    timeline_csv: Path,
) -> int:
    case_name = f"{realm.key}-p{party_size}"
    case_dir = output_dir / case_name
    case_dir.mkdir(parents=True, exist_ok=True)
    accounts_csv = case_dir / "accounts.csv"
    primary_accounts_csv = case_dir / "primary-accounts.csv"
    watcher_accounts_dir = case_dir / "watcher-accounts"
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
        reset_growth_characters(args, account_names + watcher_account_names, level=args.reset_level, realm=realm)

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
                target_specs_by_account=checkpoint_specs,
            )
        before = {} if args.dry_run else snapshot_characters(args, account_names)
        observed_level = checkpoint_level if checkpoint_level is not None and args.dry_run else max([snap.level for snap in before.values()] or [1])
        if checkpoint_level is None and observed_level >= args.max_level:
            break
        current_level = max(1, observed_level)
        promoted_count = promote_growth_classes_for_level(args, primary_rows, current_level)
        equipped_level50_party_gear = False
        if should_equip_level50_party_gear(args, current_level=current_level, party_size=party_size):
            rc = run_command(build_level50_party_gear_command(args, primary_accounts_csv), args.dry_run)
            if rc != 0:
                return rc
            equipped_level50_party_gear = True
        active_before = (
            snapshot_characters(args, account_names)
            if (promoted_count or equipped_level50_party_gear) and not args.dry_run
            else before
        )
        item_plans = build_growth_item_plans(args, account_names, active_before)
        behavior_args = argparse.Namespace(**vars(args))
        equip_mode = getattr(args, "growth_auto_equip_mode", "candidate")
        if equip_mode == "off":
            behavior_args.growth_auto_equip_slots = []
        elif equip_mode == "slots":
            behavior_args.growth_auto_equip_slots = list(getattr(args, "growth_auto_equip_slots", []))
        else:
            behavior_args.growth_auto_equip_slots = union_plan_slots(item_plans, "equip_slots")
        behavior_args.growth_auto_sell_slots = (
            union_plan_slots(item_plans, "sell_slots")
            if args.growth_auto_sell_junk and party_size == 1
            else []
        )
        behavior_command = build_behavior_command(
            args=behavior_args,
            realm=realm,
            accounts_csv=primary_accounts_csv,
            case_dir=case_dir,
            segment_index=segment_index,
            party_size=party_size,
            current_level=current_level,
            path_graph=path_graph,
        )
        commands = [behavior_command]
        if args.live_supervisor:
            commands.append(build_live_supervisor_command(args, case_dir, current_level=current_level, party_size=party_size))
        watcher_pairs: list[tuple[str, str, Path]] = []
        if args.watch_movement:
            for watcher_index, watcher_row in enumerate(watcher_rows[:1]):
                watcher_csv = watcher_accounts_dir / f"watcher-{watcher_index + 1:02d}.csv"
                write_accounts(watcher_csv, [watcher_row])
                primary_account = account_names[0]
                watcher_pairs.append((primary_account, watcher_row["username"], watcher_csv))
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
                    )
                )
        rc = run_commands_concurrently(commands, args.dry_run)
        if watcher_pairs:
            watcher_summary_rows: list[dict[str, object]] = []
            route = select_route_point(realm, current_level, party_size)
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
        if not args.dry_run and getattr(args, "fail_on_regression", True) and not segment_regression_passed(
            fallback_metrics,
            require_kill=segment_requires_kill(args, current_level),
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
        segment_xp_effective_delta = 0
        for account in account_names:
            before_row = before.get(account)
            after_row = after.get(account)
            delta = snapshot_delta(before_row, after_row)
            text_metrics = text_metrics_by_account.get(account, {"text_xp_delta": 0, "text_xp_messages": 0})
            xp_effective_delta = max(delta["xp_delta"], text_metrics["text_xp_delta"])
            segment_xp_effective_delta += xp_effective_delta
            xp_persist_lag = max(0, text_metrics["text_xp_delta"] - delta["xp_delta"])
            xp_persist_status = "lagging" if xp_persist_lag > 0 else "synced"
            spec_gain = spec_gain_summary(before_row.specs if before_row else "", after_row.specs if after_row else "")
            metrics = metrics_by_user.get(account, fallback_metrics if len(account_names) == 1 else empty_metric_summary())
            elapsed_seconds = float(metrics["elapsed_seconds"])
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
                    "train_command_sent": "1" if should_train_at_level(current_level) else "0",
                    "train_verified": "1" if train_verified(before_row, after_row, current_level) else "0",
                    "equip_candidate_slots": ",".join(str(slot) for slot in item_plans.get(account, GrowthItemPlan([], [])).equip_slots),
                    "equip_candidate_reason": item_plans.get(account, GrowthItemPlan([], [])).equip_reason,
                    "sell_candidate_slots": ",".join(str(slot) for slot in item_plans.get(account, GrowthItemPlan([], [])).sell_slots),
                    "sell_candidate_reason": item_plans.get(account, GrowthItemPlan([], [])).sell_reason,
                    "death_before": before_row.deaths if before_row else "",
                    "death_after": after_row.deaths if after_row else "",
                    "death_delta": delta["death_delta"],
                    "region_after": after_row.region if after_row else "",
                    "x_after": after_row.x if after_row else "",
                    "y_after": after_row.y if after_row else "",
                    "z_after": after_row.z if after_row else "",
                    **metrics,
                    "elapsed_seconds": format_rate(elapsed_seconds),
                    "levels_per_hour": format_rate(per_hour(delta["level_delta"], elapsed_seconds)),
                    "xp_per_hour": format_rate(per_hour(delta["xp_delta"], elapsed_seconds)),
                    "text_xp_per_hour": format_rate(per_hour(text_metrics["text_xp_delta"], elapsed_seconds)),
                    "xp_effective_per_hour": format_rate(per_hour(xp_effective_delta, elapsed_seconds)),
                    "money_copper_per_hour": format_rate(per_hour(delta["money_delta_copper"], elapsed_seconds)),
                    "inventory_items_per_hour": format_rate(per_hour(delta["inventory_items_delta"], elapsed_seconds)),
                    "target_removed_per_hour": format_rate(per_hour(float(metrics["target_removed"]), elapsed_seconds)),
                    "deaths_per_hour": format_rate(per_hour(delta["death_delta"], elapsed_seconds)),
                },
            )
        if (
            not args.dry_run
            and getattr(args, "fail_on_regression", True)
            and not segment_xp_regression_passed(
                segment_xp_effective_delta,
                require_xp=segment_requires_xp(args, current_level),
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
        if rc != 0 or args.once:
            return rc
        if plan_index + 1 < len(segment_plan) and args.inter_segment_delay > 0:
            time.sleep(args.inter_segment_delay)
    return 0


def build_case_plan(selected_realms: list[str], party_sizes: list[int]) -> list[tuple[RealmProfile, int, int]]:
    cases: list[tuple[RealmProfile, int, int]] = []
    case_index = 0
    for realm_key in selected_realms:
        realm = REALMS[realm_key]
        for party_size in party_sizes:
            if party_size < 1:
                raise SystemExit("party sizes must be positive")
            cases.append((realm, party_size, case_index))
            case_index += 1
    return cases


def run_case_plan(
    *,
    args: argparse.Namespace,
    cases: list[tuple[RealmProfile, int, int]],
    output_dir: Path,
    path_graph: Path,
    timeline_csv: Path,
) -> int:
    if args.parallel_cases <= 1 or len(cases) <= 1:
        exit_code = 0
        for realm, party_size, case_index in cases:
            rc = run_case(args, realm, party_size, case_index, output_dir, path_graph, timeline_csv)
            exit_code = exit_code or rc
            if rc != 0:
                break
        return exit_code

    max_workers = min(args.parallel_cases, len(cases))
    print(f"running {len(cases)} growth cases with parallel_cases={max_workers}")
    exit_code = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_case, args, realm, party_size, case_index, output_dir, path_graph, timeline_csv): (
                realm.key,
                party_size,
                case_index,
            )
            for realm, party_size, case_index in cases
        }
        for future in concurrent.futures.as_completed(futures):
            realm_key, party_size, case_index = futures[future]
            try:
                rc = future.result()
            except Exception as exc:
                print(f"case {realm_key}-p{party_size} index={case_index} failed: {exc}")
                rc = 1
            exit_code = exit_code or rc
    return exit_code


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    explicit_segment_seconds = any(
        token == "--segment-seconds" or token.startswith("--segment-seconds=")
        for token in raw_argv
    )
    explicit_reset_level = any(token == "--reset-level" or token.startswith("--reset-level=") for token in raw_argv)
    explicit_max_level = any(token == "--max-level" or token.startswith("--max-level=") for token in raw_argv)
    explicit_max_segments = any(token == "--max-segments" or token.startswith("--max-segments=") for token in raw_argv)
    explicit_inter_segment_delay = any(
        token == "--inter-segment-delay" or token.startswith("--inter-segment-delay=") for token in raw_argv
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_DUMMY_HOST)
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--live-api-url", default="")
    parser.add_argument("--nav-api-url", default="http://127.0.0.1:5000")
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
    parser.add_argument("--position-step", type=int, default=80)
    parser.add_argument("--segment-seconds", type=int, default=600)
    parser.add_argument("--max-segments", type=int, default=60)
    parser.add_argument("--max-level", type=int, default=50)
    parser.add_argument("--growth-stage", choices=sorted(GROWTH_STAGE_DEFAULTS), default="custom", help="apply a checkpoint preset: stabilize(1-4), train(5), gear(6-10), long(10-50), or custom")
    parser.add_argument("--checkpoint-levels", default="", help="comma-separated forced levels for fast 1-50 checkpoint probes, e.g. 1,5,6,10,20,35,49")
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
    parser.add_argument("--growth-auto-sell-junk", action=argparse.BooleanOptionalAction, default=True, help="sell DB-scored junk slots during solo service stops; party selling is logged but not executed until per-account trade/sell routing is available")
    parser.add_argument("--level50-party-gear", action=argparse.BooleanOptionalAction, default=True, help="equip party checkpoint characters with validated level-50 boss-test gear")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--run-dir", type=Path, help="reuse a specific output directory instead of creating a timestamped run")
    parser.add_argument("--resume", action="store_true", help="continue an existing --run-dir from the next missing segment")
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
    parser.add_argument("--parallel-cases", type=int, default=1, help="number of realm/party cases to run concurrently; each case still launches its own party and watcher dummies")
    parser.add_argument("--fail-on-regression", action=argparse.BooleanOptionalAction, default=True, help="fail a segment and write a reproduction command when deaths, movement failures, or no kills are observed")
    parser.add_argument("--require-segment-kill", action=argparse.BooleanOptionalAction, default=True, help="with --fail-on-regression, require at least one target_removed per segment")
    parser.add_argument("--require-segment-xp", action=argparse.BooleanOptionalAction, default=True, help="with --fail-on-regression, require XP progress for growth hunting segments below level 50")
    parser.add_argument("--smoke", action="store_true", help="quick albion solo smoke: 1 realm, 1 party size, 1 short segment")
    parser.add_argument("--fast-flee-debug", action="store_true", help="quick solo flee-loop repro: short segment, no watcher/snapshot/live retuning, fail only on deaths or movement failures")
    args = parser.parse_args(argv)
    explicit_segment_seconds_value = args.segment_seconds
    explicit_reset_level_value = args.reset_level
    explicit_max_level_value = args.max_level
    apply_growth_stage_defaults(args)
    if explicit_segment_seconds:
        args.segment_seconds = explicit_segment_seconds_value
    if explicit_reset_level:
        args.reset_level = explicit_reset_level_value
    if explicit_max_level:
        args.max_level = explicit_max_level_value
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
    if args.reset_level < 1:
        raise SystemExit("--reset-level must be positive")
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
    cases = build_case_plan(selected_realms, party_sizes)

    output_dir = args.run_dir if args.run_dir is not None else args.output_root / timestamp()
    output_dir.mkdir(parents=True, exist_ok=True)
    path_graph = output_dir / "growth-route-graph.json"
    write_growth_path_graph(path_graph, ground_z_offset=args.ground_z_offset)
    timeline_csv = output_dir / "timeline.csv"
    metadata = {
        "started_at_utc": utc_now(),
        "realms": selected_realms,
        "party_sizes": party_sizes,
        "segment_seconds": args.segment_seconds,
        "max_segments": args.max_segments,
        "max_level": args.max_level,
        "growth_stage": args.growth_stage,
        "checkpoint_levels": getattr(args, "checkpoint_levels_parsed", []),
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
