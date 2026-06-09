#!/usr/bin/env python3
"""Run deterministic dummy-client dynamic quest E2E matrix cases."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shlex
import subprocess
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace


@dataclass(frozen=True)
class RealmQuest:
    key: str
    realm: str
    region: int
    seed_npc: str
    target: str
    return_home: tuple[int, int, int]


@dataclass(frozen=True)
class QuestCase:
    name: str
    key: str
    realm: str
    region: int
    seed_npc: str
    target: str
    return_home: tuple[int, int, int]
    party_size: int
    accounts_csv: Path
    output_dir: Path
    min_target_level: int = 1
    max_target_level: int = 1
    player_level: int = 1
    quest_id: str = ""
    followup_target: str = ""
    followup_home: tuple[int, int, int] | None = None
    followup_reference: tuple[int, int, int] | None = None
    followup_min_target_level: int = 0
    followup_max_target_level: int = 0


@dataclass(frozen=True)
class StartPosition:
    region: int
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class LiveQuestBinding:
    seed_npc: str
    target: str
    min_target_level: int
    max_target_level: int
    min_player_level: int = 0
    max_player_level: int = 0
    start_npc_internal_id: str = ""
    start_position: StartPosition | None = None
    followup_reference: StartPosition | None = None
    quest_id: str = ""


@dataclass(frozen=True)
class LiveMobGrowthTarget:
    name: str
    region: int
    x: int
    y: int
    z: int
    min_level: int
    max_level: int
    stage: str = ""
    mob_id: str = ""
    aliases: tuple[str, ...] = ()


DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_REFERENCE_DISTANCE = 90000
DEFAULT_MOB_GROWTH_FOLLOWUP_CLUSTER_RADIUS = 5000
DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_CLUSTER_NEIGHBORS = 2
DEFAULT_MOB_GROWTH_FOLLOWUP_ALIAS_RADIUS = 3500
DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_ALIASES = 8
REALM_IDS_BY_KEY = {"alb": 1, "mid": 2, "hib": 3}


@dataclass(frozen=True)
class CaseSummary:
    players: int
    ok_players: int
    completed: int
    reward_observed: int
    target_removed: int
    player_deaths: int
    choice_selected: int
    world_signal: int
    followup_hunt_start: int
    elapsed_seconds: float
    passed: bool


STARTER_REALMS: tuple[RealmQuest, ...] = (
    RealmQuest("alb", "Albion", 1, "Brother Penric", "black wolf pup", (518850, 494050, 3352)),
    RealmQuest("mid", "Midgard", 100, "Aud", "young sveawolf", (773327, 749653, 4552)),
    RealmQuest("hib", "Hibernia", 200, "Ionhar", "water beetle larva", (344500, 474500, 5372)),
)
DUMMY_RESET_RESOURCE_VALUE = 10000
MELEE_SMOKE_CLASS_NAMES = {
    "armsman",
    "berserker",
    "blademaster",
    "champion",
    "friar",
    "hero",
    "mercenary",
    "minstrel",
    "paladin",
    "skald",
    "warrior",
}
MELEE_SMOKE_CLASS_PRIORITY = {
    "paladin": 0,
    "armsman": 1,
    "mercenary": 2,
    "warrior": 0,
    "berserker": 1,
    "skald": 2,
    "hero": 0,
    "blademaster": 1,
    "champion": 2,
    "friar": 50,
    "minstrel": 51,
}
CLASS_ID_TO_NAME = {
    2: "Armsman",
    6: "Cleric",
    7: "Wizard",
    10: "Paladin",
    11: "Mercenary",
    22: "Warrior",
    24: "Skald",
    26: "Healer",
    28: "Shaman",
    29: "Runemaster",
    31: "Berserker",
    33: "Hero",
    45: "Blademaster",
    48: "Champion",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", choices=("quick", "realm-smoke"), default="quick")
    parser.add_argument("--realms", default="", help="comma-separated realm keys or names to run, e.g. alb,mid,Hibernia")
    parser.add_argument("--party-sizes", default="1", help="comma-separated party sizes")
    parser.add_argument("--output-root", type=Path, default=Path("test-output/dynamic-quest-matrix"))
    parser.add_argument(
        "--accounts-pattern",
        default="tools/dummy-accounts-{realm_slug}-40.csv",
        help="CSV path pattern. Fields: {key}, {realm}, {realm_slug}, {party_size}",
    )
    parser.add_argument("--account-offset", type=int, default=0, help="skip this many rows from the accounts CSV before selecting the party")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--quest-start-mode", choices=("npc", "autoaccept"), default="npc")
    parser.add_argument("--dynamic-quest-return-dialog-response", choices=("accept", "decline"), default="accept")
    parser.add_argument("--require-quest-tag", default="", help="require a live dynamic quest tag when binding cases, e.g. branch:mob-growth")
    parser.add_argument("--require-world-signal", default="", help="require a live dynamic quest world-signal tag value, e.g. mob-growth:killed:region:1")
    parser.add_argument("--require-live-quest-target", default="", help="require an exact live dynamic quest target name when binding cases")
    parser.add_argument(
        "--dynamic-quest-followup-growth-target",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="bind a live mob-growth target from the read-only summary API and hunt it after the expected branch node",
    )
    parser.add_argument(
        "--dynamic-quest-followup-preserve-overlevel",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="when hunting a live mob-growth followup target, keep the requested player level instead of clamping to the starter quest range",
    )
    parser.add_argument(
        "--dynamic-quest-followup-max-reference-distance",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_REFERENCE_DISTANCE,
        help="maximum live mob-growth followup target distance from the quest branch reference; <=0 disables the reachability filter",
    )
    parser.add_argument(
        "--dynamic-quest-followup-cluster-radius",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_CLUSTER_RADIUS,
        help="radius used to detect add-heavy live mob-growth followup target clusters; <=0 disables cluster scoring",
    )
    parser.add_argument(
        "--dynamic-quest-followup-max-cluster-neighbors",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_CLUSTER_NEIGHBORS,
        help="prefer live mob-growth followup targets with at most this many nearby growth neighbors; <0 disables the safety preference",
    )
    parser.add_argument(
        "--dynamic-quest-followup-alias-radius",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_ALIAS_RADIUS,
        help="nearby live mob-growth targets within this radius are accepted as equivalent followup signal targets; <=0 disables aliases",
    )
    parser.add_argument(
        "--dynamic-quest-followup-max-aliases",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_ALIASES,
        help="maximum comma-separated live mob-growth followup target names to pass to the dummy; <=1 keeps only the selected target",
    )
    parser.add_argument(
        "--dynamic-quest-require-timeline-events",
        default="",
        help="forwarded to behavior dummy; requires read-only timeline event types at round end",
    )
    parser.add_argument(
        "--dynamic-quest-require-presentation-triggers",
        default="",
        help="forwarded to behavior dummy; requires read-only presentation triggers at round end",
    )
    parser.add_argument(
        "--dynamic-quest-expected-final-node",
        default="",
        help="forwarded to behavior dummy; treats an active quest at this final node as a successful branch wait",
    )
    parser.add_argument(
        "--skip-completed-dynamic-quest-accounts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use read-only quest APIs to avoid dummy accounts that already completed the live quest id",
    )
    parser.add_argument(
        "--skip-active-dynamic-quest-accounts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use read-only quest APIs to avoid dummy accounts that already have any active dynamic quest",
    )
    parser.add_argument(
        "--prefer-melee-smoke-accounts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="for live dynamic quest smoke runs, prefer melee-capable dummy accounts after completed accounts are skipped",
    )
    parser.add_argument(
        "--require-melee-smoke-accounts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="when class data is available for a live smoke run, fail instead of filling with non-melee smoke accounts",
    )
    parser.add_argument("--live-quest-start-position", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--live-quest-api-timeout", type=float, default=2.0)
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--hold", type=int, default=260)
    parser.add_argument("--safe-exit-max-seconds", type=int, default=240)
    parser.add_argument("--target-timeout", type=int, default=70)
    parser.add_argument("--max-target-distance", type=int, default=6500)
    parser.add_argument("--combat-interval", type=float, default=1.5)
    parser.add_argument("--movement-speed", type=float, default=240.0)
    parser.add_argument("--smooth-move-interval", type=float, default=0.20)
    parser.add_argument("--encounter-log-interval", type=float, default=1.0)
    parser.add_argument("--player-level", type=int, default=1)
    parser.add_argument("--min-target-level", type=int, default=1)
    parser.add_argument("--max-target-level", type=int, default=1)
    parser.add_argument(
        "--party-role-strategy",
        choices=("same", "mixed"),
        default="same",
        help="forwarded to behavior dummy; quest matrix defaults to same-role parties for deterministic E2E flow",
    )
    parser.add_argument(
        "--party-slot-rotations",
        default="",
        help="forwarded comma-separated action rotations, e.g. melee-basic,melee-basic",
    )
    parser.add_argument("--reset-start-positions", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--start-position-step", type=int, default=20)
    parser.add_argument("--mysql-bin", default=os.environ.get("MYSQL_BIN"))
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT", "3306")))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME", "opendaoc"))
    parser.add_argument("--db-user", default=os.environ.get("DB_USER", "root"))
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD", ""))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def parse_party_sizes(raw: str) -> list[int]:
    sizes: list[int] = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        size = int(item)
        if size < 1:
            raise ValueError(f"party size must be >= 1: {size}")
        sizes.append(size)
    return sizes or [1]


def parse_realm_filter(raw: str) -> set[str]:
    return {item.strip().lower() for item in str(raw or "").split(",") if item.strip()}


def build_cases(args: argparse.Namespace) -> list[QuestCase]:
    realms = STARTER_REALMS[:1] if args.matrix == "quick" else STARTER_REALMS
    realm_filter = parse_realm_filter(getattr(args, "realms", ""))
    if realm_filter:
        realms = tuple(
            realm
            for realm in realms
            if realm.key.lower() in realm_filter or realm.realm.lower() in realm_filter
        )
    cases: list[QuestCase] = []
    for realm in realms:
        for party_size in parse_party_sizes(args.party_sizes):
            name = f"{realm.key}-p{party_size}"
            accounts_csv = Path(
                args.accounts_pattern.format(
                    key=realm.key,
                    realm=realm.realm,
                    realm_slug=realm.realm.lower(),
                    party_size=party_size,
                )
            )
            cases.append(
                QuestCase(
                    name=name,
                    key=realm.key,
                    realm=realm.realm,
                    region=realm.region,
                    seed_npc=realm.seed_npc,
                    target=realm.target,
                    return_home=realm.return_home,
                    party_size=party_size,
                    accounts_csv=accounts_csv,
                    output_dir=args.output_root / name,
                    min_target_level=args.min_target_level,
                    max_target_level=args.max_target_level,
                    player_level=args.player_level,
                )
            )
    return cases


def player_level_for_live_quest(
    requested_level: int,
    min_level: int,
    max_level: int,
    *,
    preserve_overlevel: bool = True,
) -> int:
    requested = max(1, min(50, int(requested_level or 1)))
    lower = max(1, min(50, int(min_level or 1)))
    upper = max(lower, min(50, int(max_level or lower)))
    if not preserve_overlevel and requested > upper:
        return upper
    if requested >= lower:
        return requested
    return upper


def build_behavior_command(case: QuestCase, args: argparse.Namespace) -> list[str]:
    case.output_dir.mkdir(parents=True, exist_ok=True)
    accounts_csv = case_accounts_csv(case, args)
    command = [
        "python3",
        "tools/behavior-dummy-client.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--api-port",
        str(args.api_port),
        "--realm",
        str(REALM_IDS_BY_KEY.get(case.key, 1)),
        "--accounts",
        str(accounts_csv),
        "--concurrency",
        str(case.party_size),
        "--party-size",
        str(case.party_size),
        "--party-role-strategy",
        args.party_role_strategy,
        "--rounds",
        str(args.rounds),
        "--hold",
        str(args.hold),
        "--safe-exit-max-seconds",
        str(args.safe_exit_max_seconds),
        "--hunter",
        "--combat",
        "--use-skills",
        "--player-level",
        str(case.player_level),
        "--low-health-rest-percent",
        "75",
        "--low-health-rest-resume-percent",
        "95",
        "--min-target-level",
        str(case.min_target_level),
        "--max-target-level",
        str(case.max_target_level),
        "--target-selection",
        "nearest",
        "--target-pool",
        "1",
        "--max-target-distance",
        str(args.max_target_distance),
        "--target-timeout",
        str(args.target_timeout),
        "--combat-interval",
        str(args.combat_interval),
        "--target-loss-grace",
        "1",
        "--reject-target-on-server-los-failure",
        "--server-los-failure-target-cooldown",
        "4",
        "--server-los-failure-grace",
        "10",
        "--attack-range",
        "350",
        "--melee-stick-attack",
        "--melee-stick-attack-distance",
        "1800",
        "--target-face-command-interval",
        "0.8",
        "--melee-range-buffer",
        "300",
        "--minimum-melee-stop-distance",
        "60",
        "--smooth-movement",
        "--movement-speed",
        str(args.movement_speed),
        "--smooth-move-interval",
        str(args.smooth_move_interval),
        "--movement-update-interval",
        str(args.smooth_move_interval),
        "--require-target-name",
        case.target,
        "--stop-after-required-target-removed",
        "--no-required-target-removed-api-confirm",
        "--metrics-csv",
        str(case.output_dir / "metrics.csv"),
        "--combat-csv",
        str(case.output_dir / "combat.csv"),
        "--report-md",
        str(case.output_dir / "report.md"),
        "--encounter-log",
        str(case.output_dir / "encounters-{username}-{round}.jsonl"),
        "--encounter-log-interval",
        str(args.encounter_log_interval),
        "--trace-movement-log",
        str(case.output_dir / "trace-{username}-{round}.jsonl"),
    ]

    party_slot_rotations = args.party_slot_rotations.strip()
    if not party_slot_rotations:
        party_slot_rotations = ",".join("melee-basic" for _ in range(case.party_size))
    if party_slot_rotations:
        command.extend(["--party-slot-rotations", party_slot_rotations])

    if case.party_size > 1:
        command.extend(
            [
                "--party-min-ready",
                str(case.party_size),
                "--party-form-up-delay",
                "1.0",
                "--party-form-up-timeout",
                "0.0",
            ]
        )

    return_dialog_response = args.dynamic_quest_return_dialog_response
    if case.followup_target and return_dialog_response == "accept":
        return_dialog_response = "decline"

    if getattr(args, "quest_start_mode", "npc") == "autoaccept":
        command.extend([
            "--dynamic-quest-observe-final-progress",
            "--dynamic-quest-return-dialog-response",
            return_dialog_response,
        ])
    else:
        return_home = ",".join(str(value) for value in case.return_home)
        command.extend(
            [
                "--dynamic-quest-return-after-required-target",
                "--dynamic-quest-return-npc-name",
                case.seed_npc,
                "--dynamic-quest-return-home",
                return_home,
                "--dynamic-quest-return-complete-wait",
                "2",
                "--dynamic-quest-return-dialog-response",
                return_dialog_response,
                "--startup-service-npc-name",
                case.seed_npc,
                "--startup-service-scan-seconds",
                "2",
                "--startup-service-interact",
                "--startup-service-accept-dialog",
            ]
        )

    if case.quest_id:
        command.extend(["--dynamic-quest-expected-quest-id", case.quest_id])

    required_timeline_events = str(getattr(args, "dynamic_quest_require_timeline_events", "") or "").strip()
    if required_timeline_events:
        command.extend(["--dynamic-quest-require-timeline-events", required_timeline_events])

    required_presentation_triggers = str(getattr(args, "dynamic_quest_require_presentation_triggers", "") or "").strip()
    if required_presentation_triggers:
        command.extend(["--dynamic-quest-require-presentation-triggers", required_presentation_triggers])

    expected_final_node = str(getattr(args, "dynamic_quest_expected_final_node", "") or "").strip()
    if expected_final_node:
        command.extend(["--dynamic-quest-expected-final-node", expected_final_node])

    if case.followup_target:
        command.extend(["--dynamic-quest-followup-target-name", case.followup_target])
        if case.followup_home is not None:
            command.extend([
                "--dynamic-quest-followup-target-home",
                ",".join(str(value) for value in case.followup_home),
            ])
        if case.followup_min_target_level > 0:
            command.extend(["--dynamic-quest-followup-min-target-level", str(case.followup_min_target_level)])
        if case.followup_max_target_level > 0:
            command.extend(["--dynamic-quest-followup-max-target-level", str(case.followup_max_target_level)])

    return command


def sql_quote(value: object) -> str:
    return "'" + str(value or "").replace("\\", "\\\\").replace("'", "''") + "'"


def build_case_expression(column: str, account_rows: list[dict[str, str]], values: list[int]) -> str:
    whens = " ".join(
        f"WHEN {sql_quote(row.get('username'))} THEN {value}"
        for row, value in zip(account_rows, values, strict=False)
    )
    return f"CASE `AccountName` {whens} ELSE `{column}` END"


def build_start_position_update_sql(
    case: QuestCase,
    account_rows: list[dict[str, str]],
    position_step: int,
    account_offset: int = 0,
    start_position: StartPosition | None = None,
    player_level: int | None = None,
) -> str:
    offset = max(0, int(account_offset))
    selected_rows = [
        row
        for row in account_rows[offset : offset + case.party_size]
        if str(row.get("username") or "").strip()
    ]
    if not selected_rows:
        return ""

    position = start_position or StartPosition(case.region, *case.return_home)
    x, y, z = position.x, position.y, position.z
    step = max(0, int(position_step))
    x_values = [x + index * step for index, _ in enumerate(selected_rows)]
    y_values = [y + index * step for index, _ in enumerate(selected_rows)]
    z_values = [z for _ in selected_rows]
    accounts = ", ".join(sql_quote(row.get("username")) for row in selected_rows)
    level_assignment = ""
    if player_level is not None:
        level = max(1, min(50, int(player_level)))
        level_assignment = f"  `Level` = {level},\n"

    return (
        "UPDATE `dolcharacters`\n"
        "SET\n"
        f"{level_assignment}"
        f"  `Health` = {DUMMY_RESET_RESOURCE_VALUE},\n"
        f"  `Mana` = {DUMMY_RESET_RESOURCE_VALUE},\n"
        f"  `Endurance` = {DUMMY_RESET_RESOURCE_VALUE},\n"
        f"  `Region` = {position.region},\n"
        f"  `Xpos` = {build_case_expression('Xpos', selected_rows, x_values)},\n"
        f"  `Ypos` = {build_case_expression('Ypos', selected_rows, y_values)},\n"
        f"  `Zpos` = {build_case_expression('Zpos', selected_rows, z_values)},\n"
        f"  `BindRegion` = {position.region},\n"
        f"  `BindXpos` = {build_case_expression('BindXpos', selected_rows, x_values)},\n"
        f"  `BindYpos` = {build_case_expression('BindYpos', selected_rows, y_values)},\n"
        f"  `BindZpos` = {build_case_expression('BindZpos', selected_rows, z_values)}\n"
        f"WHERE `AccountName` IN ({accounts});"
    )


def build_dynamic_quest_api_url(args: argparse.Namespace) -> str:
    return f"http://{args.host}:{int(args.api_port)}/api/world/dynamic-quests"


def fetch_live_dynamic_quests(args: argparse.Namespace) -> dict[str, object]:
    request = urllib.request.Request(build_dynamic_quest_api_url(args), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=float(args.live_quest_api_timeout)) as response:
        return json.loads(response.read().decode("utf-8"))


def build_mob_growth_summary_api_url(args: argparse.Namespace, region_id: int = 0) -> str:
    query_values: dict[str, int] = {"limit": 100}
    if int(region_id or 0) > 0:
        query_values["region"] = int(region_id)
    query = urllib.parse.urlencode(query_values)
    return f"http://{args.host}:{int(args.api_port)}/api/world/mob-growth/summary?{query}"


def fetch_mob_growth_summary(args: argparse.Namespace, region_id: int = 0) -> dict[str, object]:
    request = urllib.request.Request(build_mob_growth_summary_api_url(args, region_id), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=float(args.live_quest_api_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def world_signal_region(signal: str) -> int:
    prefix = "mob-growth:killed:region:"
    signal = text_value(signal).lower()
    if not signal.startswith(prefix):
        return 0
    return int_value(signal[len(prefix):])


def world_signal_stage(signal: str) -> str:
    signal = text_value(signal).lower()
    for prefix in ("mob-growth:killed:stage:", "mob-growth:killed:"):
        if signal.startswith(prefix):
            stage = signal[len(prefix):]
            if stage in {"elite", "champion", "boss"}:
                return stage
    return ""


def mob_growth_target_matches_signal(item: dict[str, object], signal: str) -> bool:
    signal = text_value(signal).lower()
    if not signal:
        return True

    region = world_signal_region(signal)
    if region > 0 and int_value(item.get("regionId")) != region:
        return False

    stage = world_signal_stage(signal)
    item_stage = text_value(item.get("stage")).lower()
    if stage and item_stage != stage:
        return False

    if signal == "mob-growth:killed:mutant" and not truthy(item.get("isMutant")):
        return False

    if signal.startswith("mob-growth:killed:mob:"):
        mob_id = signal.removeprefix("mob-growth:killed:mob:")
        if text_value(item.get("mobId")).lower() != mob_id:
            return False

    return True


def distance_squared_to_point(item: dict[str, object], point: tuple[int, int, int] | None) -> int:
    if point is None:
        return 0

    dx = int_value(item.get("x")) - int(point[0])
    dy = int_value(item.get("y")) - int(point[1])
    dz = int_value(item.get("z")) - int(point[2])
    return dx * dx + dy * dy + dz * dz


def distance_squared_between_mob_growth_items(left: dict[str, object], right: dict[str, object]) -> int:
    dx = int_value(left.get("x")) - int_value(right.get("x"))
    dy = int_value(left.get("y")) - int_value(right.get("y"))
    dz = int_value(left.get("z")) - int_value(right.get("z"))
    return dx * dx + dy * dy + dz * dz


def mob_growth_followup_cluster_neighbors(
    item: dict[str, object],
    candidates: list[dict[str, object]],
    *,
    radius: int,
) -> int:
    if radius <= 0:
        return 0

    radius_squared = radius * radius
    region_id = int_value(item.get("regionId")) or int_value(item.get("region"))
    neighbors = 0
    for other in candidates:
        if other is item:
            continue
        other_region_id = int_value(other.get("regionId")) or int_value(other.get("region"))
        if region_id and other_region_id and region_id != other_region_id:
            continue
        if distance_squared_between_mob_growth_items(item, other) <= radius_squared:
            neighbors += 1
    return neighbors


def prefer_less_clustered_mob_growth_candidates(
    candidates: list[dict[str, object]],
    *,
    radius: int,
    max_cluster_neighbors: int,
) -> list[dict[str, object]]:
    if radius <= 0 or max_cluster_neighbors < 0:
        return candidates

    less_clustered = [
        item for item in candidates
        if mob_growth_followup_cluster_neighbors(item, candidates, radius=radius) <= max_cluster_neighbors
    ]
    return less_clustered or candidates


def mob_growth_followup_sort_key(
    item: dict[str, object],
    *,
    preferred_level: int,
    reference_position: tuple[int, int, int] | None,
) -> tuple[int, int, int, int, int, int, int, str]:
    level = int_value(item.get("effectiveLevel")) or int_value(item.get("baseLevel")) or 1
    over_preferred_level = max(0, level - preferred_level) if preferred_level > 0 else 0
    stage = text_value(item.get("stage")).lower()
    return (
        int_value(item.get("playerKills")),
        int_value(item.get("combatCount")),
        1 if stage == "boss" else 0,
        over_preferred_level,
        distance_squared_to_point(item, reference_position),
        level,
        -int_value(item.get("growthScore")),
        text_value(item.get("mobId")),
    )


def live_mob_growth_candidate_items(payload: dict[str, object], signal: str) -> list[dict[str, object]]:
    top = payload.get("top", []) if isinstance(payload, dict) else []
    candidates: list[dict[str, object]] = []
    for item in top if isinstance(top, list) else []:
        if not isinstance(item, dict):
            continue
        if not truthy(item.get("isAlive")):
            continue
        if int_value(item.get("x")) <= 0 or int_value(item.get("y")) <= 0:
            continue
        stage = text_value(item.get("stage")).lower()
        if stage in {"", "normal"} and not truthy(item.get("isMutant")):
            continue
        if not mob_growth_target_matches_signal(item, signal):
            continue
        candidates.append(item)
    return candidates


def mob_growth_candidate_level(item: dict[str, object]) -> int:
    return int_value(item.get("effectiveLevel")) or int_value(item.get("baseLevel")) or 1


def mob_growth_candidate_name(item: dict[str, object]) -> str:
    return text_value(item.get("name")) or text_value(item.get("mobId"))


def build_mob_growth_followup_aliases(
    selected: dict[str, object],
    candidates: list[dict[str, object]],
    *,
    alias_radius: int,
    max_aliases: int,
) -> tuple[tuple[str, ...], int, int]:
    selected_name = mob_growth_candidate_name(selected)
    selected_level = max(1, mob_growth_candidate_level(selected))
    if max_aliases <= 1 or alias_radius <= 0:
        return ((selected_name,) if selected_name else ()), selected_level, selected_level

    selected_point = (
        int_value(selected.get("x")),
        int_value(selected.get("y")),
        int_value(selected.get("z")),
    )
    selected_region = int_value(selected.get("regionId")) or int_value(selected.get("region"))
    radius_squared = alias_radius * alias_radius
    nearby: list[dict[str, object]] = []
    for item in candidates:
        name = mob_growth_candidate_name(item)
        if not name:
            continue
        item_region = int_value(item.get("regionId")) or int_value(item.get("region"))
        if selected_region and item_region and selected_region != item_region:
            continue
        if distance_squared_to_point(item, selected_point) > radius_squared:
            continue
        nearby.append(item)

    nearby.sort(
        key=lambda item: (
            0 if item is selected else 1,
            distance_squared_to_point(item, selected_point),
            mob_growth_candidate_level(item),
            mob_growth_candidate_name(item).lower(),
        )
    )

    names: list[str] = []
    levels: list[int] = []
    seen: set[str] = set()
    for item in nearby:
        name = mob_growth_candidate_name(item)
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
        levels.append(max(1, mob_growth_candidate_level(item)))
        if len(names) >= max_aliases:
            break

    if selected_name and selected_name.lower() not in seen:
        names.insert(0, selected_name)
        levels.insert(0, selected_level)

    return tuple(names), min(levels or [selected_level]), max(levels or [selected_level])


def extract_live_mob_growth_target(
    payload: dict[str, object],
    signal: str,
    *,
    max_preferred_level: int = 0,
    reference_position: tuple[int, int, int] | None = None,
    max_reference_distance: int = DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_REFERENCE_DISTANCE,
    cluster_radius: int = DEFAULT_MOB_GROWTH_FOLLOWUP_CLUSTER_RADIUS,
    max_cluster_neighbors: int = DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_CLUSTER_NEIGHBORS,
    alias_radius: int = DEFAULT_MOB_GROWTH_FOLLOWUP_ALIAS_RADIUS,
    max_aliases: int = DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_ALIASES,
) -> LiveMobGrowthTarget | None:
    candidates = live_mob_growth_candidate_items(payload, signal)
    if not candidates:
        return None

    preferred_level = max(0, int(max_preferred_level or 0))
    if preferred_level > 0:
        preferred_candidates = [
            item for item in candidates
            if mob_growth_candidate_level(item) <= preferred_level
        ]
        if not preferred_candidates:
            return None
        candidates = preferred_candidates

    max_distance = int(max_reference_distance or 0)
    if reference_position is not None and max_distance > 0:
        max_distance_squared = max_distance * max_distance
        reachable_candidates = [
            item for item in candidates
            if distance_squared_to_point(item, reference_position) <= max_distance_squared
        ]
        if not reachable_candidates:
            return None
        candidates = reachable_candidates

    alias_candidates = list(candidates)
    candidates = prefer_less_clustered_mob_growth_candidates(
        candidates,
        radius=int(cluster_radius or 0),
        max_cluster_neighbors=int(max_cluster_neighbors),
    )

    candidates.sort(
        key=lambda item: mob_growth_followup_sort_key(
            item,
            preferred_level=preferred_level,
            reference_position=reference_position,
        )
    )
    item = candidates[0]
    aliases, min_level, max_level = build_mob_growth_followup_aliases(
        item,
        alias_candidates,
        alias_radius=int(alias_radius or 0),
        max_aliases=int(max_aliases or 0),
    )
    return LiveMobGrowthTarget(
        name=mob_growth_candidate_name(item),
        region=int_value(item.get("regionId")),
        x=int_value(item.get("x")),
        y=int_value(item.get("y")),
        z=int_value(item.get("z")),
        min_level=max(1, min_level),
        max_level=max(1, max_level),
        stage=text_value(item.get("stage")),
        mob_id=text_value(item.get("mobId")),
        aliases=aliases,
    )


def build_dynamic_quest_player_api_url(args: argparse.Namespace, path: str, username: str) -> str:
    query = urllib.parse.urlencode({"account": username})
    return f"http://{args.host}:{int(args.api_port)}/api/world/dynamic-quests/{path}?{query}"


def fetch_dynamic_quest_player_api(args: argparse.Namespace, path: str, username: str) -> dict[str, object]:
    request = urllib.request.Request(build_dynamic_quest_player_api_url(args, path, username), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=float(args.live_quest_api_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def dynamic_quest_timeline_has_terminal_event(payload: dict[str, object], quest_id: str) -> bool:
    quest_id = text_value(quest_id)
    if not quest_id:
        return False

    events = payload.get("events", []) if isinstance(payload, dict) else []
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        if text_value(event.get("questId")).lower() != quest_id.lower():
            continue
        if text_value(event.get("eventType")).lower() in {"quest_completed", "quest_rewarded"}:
            return True

    return False


def dynamic_quest_progress_has_active_quest(payload: dict[str, object], quest_id: str) -> bool:
    quest_id = text_value(quest_id)
    if not quest_id:
        return False

    completed = payload.get("completedQuestIds", payload.get("completed_quest_ids", [])) if isinstance(payload, dict) else []
    if any(text_value(item).lower() == quest_id.lower() for item in completed if isinstance(completed, list)):
        return True

    active = payload.get("active", []) if isinstance(payload, dict) else []
    return any(
        isinstance(item, dict) and text_value(item.get("questId")).lower() == quest_id.lower()
        for item in active if isinstance(active, list)
    )


def dynamic_quest_progress_has_any_active_quest(payload: dict[str, object]) -> bool:
    active = payload.get("active", []) if isinstance(payload, dict) else []
    return any(isinstance(item, dict) and text_value(item.get("questId")) for item in active if isinstance(active, list))


def account_has_completed_or_active_dynamic_quest(args: argparse.Namespace, username: str, quest_id: str) -> bool:
    username = text_value(username)
    quest_id = text_value(quest_id)
    if not username or not quest_id:
        return False

    try:
        timeline = fetch_dynamic_quest_player_api(args, "timeline", username)
        if dynamic_quest_timeline_has_terminal_event(timeline, quest_id):
            return True

        progress = fetch_dynamic_quest_player_api(args, "progress", username)
        if dynamic_quest_progress_has_active_quest(progress, quest_id):
            return True
    except Exception:
        pass

    return account_has_dynamic_quest_progress_row(args, username, quest_id)


def account_has_any_active_dynamic_quest(args: argparse.Namespace, username: str) -> bool:
    username = text_value(username)
    if not username:
        return False

    try:
        progress = fetch_dynamic_quest_player_api(args, "progress", username)
        if dynamic_quest_progress_has_any_active_quest(progress):
            return True
    except Exception:
        pass

    return account_has_any_active_dynamic_quest_progress_row(args, username)


def account_has_dynamic_quest_progress_row(args: argparse.Namespace, username: str, quest_id: str) -> bool:
    username = text_value(username)
    quest_id = text_value(quest_id)
    if not username or not quest_id:
        return False

    try:
        provision_module = load_provision_module()
        db_args = build_db_args(args, provision_module)
        if not provision_module.mysql_bin_available(db_args.mysql_bin):
            return False

        sql = (
            "SELECT IsActive, IsComplete, Completed, Failed "
            "FROM dynamic_quest_progress "
            f"WHERE QuestId = {sql_quote(quest_id)} "
            f"AND LOWER(PlayerName) = LOWER({sql_quote(username)}) "
            "ORDER BY UpdatedAt DESC LIMIT 10;"
        )
        rows = provision_module.parse_mysql_rows(provision_module.run_mysql(db_args, sql))
    except Exception:
        return False

    for row in rows:
        if truthy(row.get("Failed")):
            continue
        if truthy(row.get("IsActive")) or truthy(row.get("IsComplete")) or truthy(row.get("Completed")):
            return True

    return False


def account_has_any_active_dynamic_quest_progress_row(args: argparse.Namespace, username: str) -> bool:
    username = text_value(username)
    if not username:
        return False

    try:
        provision_module = load_provision_module()
        db_args = build_db_args(args, provision_module)
        if not provision_module.mysql_bin_available(db_args.mysql_bin):
            return False

        sql = (
            "SELECT IsActive, Failed "
            "FROM dynamic_quest_progress "
            f"WHERE LOWER(PlayerName) = LOWER({sql_quote(username)}) "
            "ORDER BY UpdatedAt DESC LIMIT 20;"
        )
        rows = provision_module.parse_mysql_rows(provision_module.run_mysql(db_args, sql))
    except Exception:
        return False

    for row in rows:
        if truthy(row.get("Failed")):
            continue
        if truthy(row.get("IsActive")):
            return True

    return False


def int_value(value: object) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def text_value(value: object) -> str:
    return str(value or "").strip()


def quest_tags(quest: dict[str, object]) -> list[str]:
    tags = quest.get("tags", [])
    if not isinstance(tags, list):
        return []
    return [text_value(tag) for tag in tags if text_value(tag)]


def quest_has_selector_tag(quest: dict[str, object]) -> bool:
    return any(tag.lower().startswith("selector:") for tag in quest_tags(quest))


def quest_has_required_live_filters(
    quest: dict[str, object],
    *,
    required_tag: str = "",
    required_world_signal: str = "",
    required_target_name: str = "",
) -> bool:
    tags = [tag.lower() for tag in quest_tags(quest)]
    tag = text_value(required_tag).lower()
    if tag and tag not in tags:
        return False

    world_signal = text_value(required_world_signal).lower()
    if world_signal and f"world-signal:{world_signal}" not in tags:
        return False

    target_name = text_value(required_target_name).lower()
    if target_name and text_value(quest.get("targetName")).lower() != target_name:
        return False

    return True


def extract_quest_start_position(quest: dict[str, object], case: QuestCase) -> StartPosition | None:
    start_node_id = text_value(quest.get("startNodeId"))
    nodes = quest.get("nodes", [])
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict) or text_value(node.get("id")) != start_node_id:
            continue
        objective = node.get("objective", {})
        if not isinstance(objective, dict):
            continue
        x = int_value(objective.get("x"))
        y = int_value(objective.get("y"))
        z = int_value(objective.get("z"))
        region = int_value(objective.get("regionId")) or case.region
        if x and y:
            return StartPosition(region, x, y, z)

    return None


def objective_position_from_node(node: dict[str, object], fallback_region: int) -> StartPosition | None:
    objective = node.get("objective", {})
    if not isinstance(objective, dict):
        return None

    x = int_value(objective.get("x"))
    y = int_value(objective.get("y"))
    z = int_value(objective.get("z"))
    region = int_value(objective.get("regionId")) or fallback_region
    if x and y:
        return StartPosition(region, x, y, z)
    return None


def extract_quest_followup_reference(quest: dict[str, object], case: QuestCase) -> StartPosition | None:
    nodes = quest.get("nodes", [])
    typed_nodes = [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []
    for preferred_id in ("observe_signal", "explore"):
        for node in typed_nodes:
            if text_value(node.get("id")).lower() != preferred_id:
                continue
            position = objective_position_from_node(node, case.region)
            if position is not None:
                return position

    return None


def extract_quest_kill_level_bounds(quest: dict[str, object]) -> tuple[int, int]:
    nodes = quest.get("nodes", [])
    typed_nodes = [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []
    for node in typed_nodes:
        if text_value(node.get("type")).lower() not in {"1", "kill"}:
            continue
        objective = node.get("objective", {})
        if not isinstance(objective, dict):
            continue
        min_level = int_value(objective.get("minLevel"))
        max_level = int_value(objective.get("maxLevel"))
        if min_level or max_level:
            if min_level <= 0:
                min_level = max_level
            if max_level <= 0:
                max_level = min_level
            if max_level < min_level:
                max_level = min_level
            return min_level, max_level

    return 0, 0


def extract_live_start_position(payload: dict[str, object], case: QuestCase) -> StartPosition | None:
    binding = extract_live_quest_binding(payload, case, "autoaccept")
    return binding.start_position if binding else None


def extract_live_quest_binding(
    payload: dict[str, object],
    case: QuestCase,
    quest_start_mode: str,
    *,
    required_tag: str = "",
    required_world_signal: str = "",
    required_target_name: str = "",
) -> LiveQuestBinding | None:
    quests = payload.get("quests", []) if isinstance(payload, dict) else []
    candidates: list[dict[str, object]] = []
    for quest in quests if isinstance(quests, list) else []:
        if not isinstance(quest, dict):
            continue
        if not quest_has_required_live_filters(
            quest,
            required_tag=required_tag,
            required_world_signal=required_world_signal,
            required_target_name=required_target_name,
        ):
            continue
        quest_region = int_value(quest.get("startRegionId"))
        if quest_region != case.region:
            if quest_start_mode != "autoaccept" or text_value(quest.get("realm")).lower() != case.realm.lower():
                continue
        target = text_value(quest.get("targetName"))
        if not target:
            continue
        seed_npc = text_value(quest.get("startNpcName"))
        if quest_start_mode == "npc" and not seed_npc:
            continue
        if quest_start_mode == "autoaccept" and seed_npc:
            continue
        candidates.append(quest)

    if not candidates:
        return None

    candidates.sort(
        key=lambda quest: (
            text_value(quest.get("targetName")).lower() == case.target.lower(),
            quest_has_selector_tag(quest),
        ),
        reverse=True,
    )
    quest = candidates[0]
    kill_min_level, kill_max_level = extract_quest_kill_level_bounds(quest)
    player_min_level = int_value(quest.get("minLevel")) or case.min_target_level
    player_max_level = int_value(quest.get("maxLevel")) or case.max_target_level
    if player_max_level < player_min_level:
        player_max_level = player_min_level
    min_level = kill_min_level or int_value(quest.get("minLevel")) or case.min_target_level
    max_level = kill_max_level or int_value(quest.get("maxLevel")) or case.max_target_level
    if max_level < min_level:
        max_level = min_level

    return LiveQuestBinding(
        quest_id=text_value(quest.get("id")),
        seed_npc=text_value(quest.get("startNpcName")),
        target=text_value(quest.get("targetName")),
        min_target_level=min_level,
        max_target_level=max_level,
        min_player_level=player_min_level,
        max_player_level=player_max_level,
        start_npc_internal_id=text_value(quest.get("startNpcInternalId")),
        start_position=extract_quest_start_position(quest, case) if quest_start_mode == "autoaccept" else None,
        followup_reference=extract_quest_followup_reference(quest, case),
    )


def fetch_start_npc_position(args: argparse.Namespace, internal_id: str) -> StartPosition | None:
    if not text_value(internal_id):
        return None

    provision_module = load_provision_module()
    db_args = build_db_args(args, provision_module)
    if not provision_module.mysql_bin_available(db_args.mysql_bin):
        raise RuntimeError(f"mysql client not found: {db_args.mysql_bin}")

    sql = (
        "SELECT `Region`, `X`, `Y`, `Z` "
        "FROM `Mob` "
        f"WHERE `Mob_ID` = {sql_quote(internal_id)} "
        "LIMIT 1;"
    )
    rows = provision_module.parse_mysql_rows(provision_module.run_mysql(db_args, sql))
    if not rows:
        return None

    row = rows[0]
    x = int_value(row.get("X"))
    y = int_value(row.get("Y"))
    z = int_value(row.get("Z"))
    region = int_value(row.get("Region"))
    if not x or not y or not region:
        return None
    return StartPosition(region, x, y, z)


def bind_case_to_live_quest(
    case: QuestCase,
    binding: LiveQuestBinding,
    *,
    preserve_overlevel: bool = True,
) -> tuple[QuestCase, StartPosition | None]:
    start_position = binding.start_position
    return_home = case.return_home
    if start_position is not None and binding.seed_npc:
        return_home = (start_position.x, start_position.y, start_position.z)

    return (
        replace(
            case,
            seed_npc=binding.seed_npc or case.seed_npc,
            target=binding.target or case.target,
            return_home=return_home,
            min_target_level=binding.min_target_level,
            max_target_level=binding.max_target_level,
            player_level=player_level_for_live_quest(
                case.player_level,
                binding.min_player_level or binding.min_target_level,
                binding.max_player_level or binding.max_target_level,
                preserve_overlevel=preserve_overlevel,
            ),
            quest_id=binding.quest_id,
            followup_reference=(
                (binding.followup_reference.x, binding.followup_reference.y, binding.followup_reference.z)
                if binding.followup_reference is not None
                else case.followup_reference
            ),
        ),
        start_position,
    )


def bind_case_to_mob_growth_followup(case: QuestCase, target: LiveMobGrowthTarget) -> QuestCase:
    followup_names = [name for name in target.aliases if text_value(name)]
    if not followup_names and target.name:
        followup_names = [target.name]
    return replace(
        case,
        followup_target=",".join(followup_names),
        followup_home=(target.x, target.y, target.z),
        followup_min_target_level=target.min_level,
        followup_max_target_level=target.max_level,
    )


def should_preserve_live_quest_overlevel(mode: str, args: argparse.Namespace) -> bool:
    return mode == "autoaccept" or bool(getattr(args, "dynamic_quest_followup_preserve_overlevel", False))


def resolve_live_case(case: QuestCase, args: argparse.Namespace) -> tuple[QuestCase, StartPosition | None]:
    if not getattr(args, "live_quest_start_position", True):
        return case, None

    mode = getattr(args, "quest_start_mode", "npc")
    required_world_signal = format_case_text_template(getattr(args, "require_world_signal", ""), case)
    binding = extract_live_quest_binding(
        fetch_live_dynamic_quests(args),
        case,
        mode,
        required_tag=getattr(args, "require_quest_tag", ""),
        required_world_signal=required_world_signal,
        required_target_name=getattr(args, "require_live_quest_target", ""),
    )
    if binding is None:
        raise RuntimeError(f"no live dynamic quest found for {case.realm} mode={mode}")

    if mode == "npc" and binding.start_position is None:
        position = fetch_start_npc_position(args, binding.start_npc_internal_id)
        if position is None:
            raise RuntimeError(
                f"no live start npc position found for {case.realm} npc {binding.seed_npc!r} "
                f"internal_id={binding.start_npc_internal_id!r}"
            )
        binding = replace(binding, start_position=position)

    bound_case, start_position = bind_case_to_live_quest(
        case,
        binding,
        preserve_overlevel=should_preserve_live_quest_overlevel(mode, args),
    )

    if bool(getattr(args, "dynamic_quest_followup_growth_target", False)):
        target = extract_live_mob_growth_target(
            fetch_mob_growth_summary(args, world_signal_region(required_world_signal)),
            required_world_signal,
            max_preferred_level=max(1, int(bound_case.player_level or 1)),
            reference_position=bound_case.followup_reference or bound_case.return_home,
            max_reference_distance=getattr(args, "dynamic_quest_followup_max_reference_distance", 0),
            cluster_radius=getattr(args, "dynamic_quest_followup_cluster_radius", 0),
            max_cluster_neighbors=getattr(args, "dynamic_quest_followup_max_cluster_neighbors", -1),
            alias_radius=getattr(args, "dynamic_quest_followup_alias_radius", DEFAULT_MOB_GROWTH_FOLLOWUP_ALIAS_RADIUS),
            max_aliases=getattr(args, "dynamic_quest_followup_max_aliases", DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_ALIASES),
        )
        if target is None:
            raise RuntimeError(
                f"no live mob-growth followup target found for {case.realm} "
                f"signal={required_world_signal!r}"
            )
        bound_case = bind_case_to_mob_growth_followup(bound_case, target)

    return bound_case, start_position


def resolve_case_start_position(case: QuestCase, args: argparse.Namespace) -> StartPosition | None:
    if getattr(args, "quest_start_mode", "npc") != "autoaccept" or not getattr(args, "live_quest_start_position", True):
        return None

    _, position = resolve_live_case(case, args)
    if position is None:
        raise RuntimeError(f"no live start objective found for {case.realm} target {case.target!r}")
    return position


def should_resolve_live_case(args: argparse.Namespace) -> bool:
    if not getattr(args, "live_quest_start_position", True):
        return False

    if not bool(getattr(args, "dry_run", False)):
        return True

    return (
        getattr(args, "quest_start_mode", "npc") == "autoaccept"
        or bool(text_value(getattr(args, "require_quest_tag", "")))
        or bool(text_value(getattr(args, "require_world_signal", "")))
        or bool(getattr(args, "dynamic_quest_followup_growth_target", False))
    )


def read_account_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_account_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def account_row_is_melee_smoke_preferred(row: dict[str, str]) -> bool:
    class_name = text_value(row.get("class_name") or row.get("class") or row.get("ClassName")).lower()
    return class_name in MELEE_SMOKE_CLASS_NAMES


def account_row_melee_smoke_priority(row: dict[str, str]) -> tuple[int, str]:
    class_name = text_value(row.get("class_name") or row.get("class") or row.get("ClassName")).lower()
    if class_name not in MELEE_SMOKE_CLASS_NAMES:
        return (100, class_name)
    return (MELEE_SMOKE_CLASS_PRIORITY.get(class_name, 20), class_name)


def order_account_rows_for_dynamic_quest_smoke(
    rows: list[dict[str, str]],
    args: argparse.Namespace,
    *,
    live_quest_filter_active: bool,
) -> list[dict[str, str]]:
    if not live_quest_filter_active or not bool(getattr(args, "prefer_melee_smoke_accounts", True)):
        return rows

    preferred = [row for row in rows if account_row_is_melee_smoke_preferred(row)]
    preferred.sort(key=account_row_melee_smoke_priority)
    fallback = [row for row in rows if not account_row_is_melee_smoke_preferred(row)]
    return preferred + fallback


def account_rows_have_class_data(rows: list[dict[str, str]]) -> bool:
    return any(
        text_value(row.get("class_name") or row.get("class") or row.get("ClassName"))
        for row in rows
    )


def enrich_account_rows_with_db_class_data(
    rows: list[dict[str, str]],
    args: argparse.Namespace,
) -> list[dict[str, str]]:
    missing_rows = [
        row for row in rows
        if text_value(row.get("username"))
        and not text_value(row.get("class_name") or row.get("class") or row.get("ClassName"))
    ]
    if not missing_rows:
        return rows

    usernames = sorted({text_value(row.get("username")) for row in missing_rows if text_value(row.get("username"))})
    if not usernames:
        return rows

    try:
        provision_module = load_provision_module()
        db_args = build_db_args(args, provision_module)
        if not provision_module.mysql_bin_available(db_args.mysql_bin):
            return rows

        account_list = ", ".join(sql_quote(username) for username in usernames)
        sql = (
            "SELECT AccountName, Class, Level, SerializedSpecs "
            "FROM DOLCharacters "
            f"WHERE AccountName IN ({account_list}) "
            "ORDER BY AccountName, Level DESC;"
        )
        db_rows = provision_module.parse_mysql_rows(provision_module.run_mysql(db_args, sql))
    except Exception:
        return rows

    by_account: dict[str, dict[str, str]] = {}
    for db_row in db_rows:
        account_name = text_value(db_row.get("AccountName")).lower()
        if not account_name or account_name in by_account:
            continue
        by_account[account_name] = db_row

    enriched: list[dict[str, str]] = []
    for row in rows:
        updated = dict(row)
        account_name = text_value(row.get("username")).lower()
        db_row = by_account.get(account_name)
        class_id = int_value(db_row.get("Class")) if db_row else 0
        class_name = CLASS_ID_TO_NAME.get(class_id, "")
        if class_id and not text_value(updated.get("class_id")):
            updated["class_id"] = str(class_id)
        if class_name and not text_value(updated.get("class_name") or updated.get("class") or updated.get("ClassName")):
            updated["class_name"] = class_name
        specs = text_value(db_row.get("SerializedSpecs")) if db_row else ""
        if specs and not text_value(updated.get("specs")):
            updated["specs"] = specs
        enriched.append(updated)

    return enriched


def format_case_text_template(value: str, case: QuestCase) -> str:
    text = text_value(value)
    if not text:
        return ""

    try:
        return text.format(
            key=case.key,
            realm=case.realm,
            region=case.region,
            party_size=case.party_size,
        )
    except (KeyError, IndexError, ValueError):
        return text


def case_accounts_csv(case: QuestCase, args: argparse.Namespace) -> Path:
    if bool(getattr(args, "skip_completed_dynamic_quest_accounts", True)) and bool(text_value(getattr(case, "quest_id", ""))):
        return case.output_dir / f"accounts-selected-p{case.party_size}.csv"

    if max(0, int(getattr(args, "account_offset", 0) or 0)) <= 0:
        return case.accounts_csv

    return case.output_dir / f"accounts-offset-{int(args.account_offset)}-p{case.party_size}.csv"


def prepare_case_accounts_csv(case: QuestCase, args: argparse.Namespace, quest_id: str = "") -> Path:
    account_offset = max(0, int(getattr(args, "account_offset", 0) or 0))
    skip_completed = bool(getattr(args, "skip_completed_dynamic_quest_accounts", True)) and bool(text_value(quest_id))
    skip_any_active = bool(getattr(args, "skip_active_dynamic_quest_accounts", True)) and bool(text_value(quest_id))
    if account_offset <= 0 and not skip_completed and not skip_any_active:
        return case.accounts_csv

    fieldnames, rows = read_account_csv(case.accounts_csv)
    rows = enrich_account_rows_with_db_class_data(rows, args)
    for extra_field in ("class_id", "class_name", "specs"):
        if any(text_value(row.get(extra_field)) for row in rows) and extra_field not in fieldnames:
            fieldnames.append(extra_field)
    candidate_rows = []
    skipped_completed = []
    skipped_active = []
    for row in rows[account_offset:]:
        username = text_value(row.get("username"))
        if not username:
            continue

        if skip_any_active and account_has_any_active_dynamic_quest(args, username):
            skipped_active.append(username)
            continue

        if skip_completed and account_has_completed_or_active_dynamic_quest(args, username, quest_id):
            skipped_completed.append(username)
            continue

        candidate_rows.append(row)

    live_smoke_melee_required = (
        skip_completed
        and bool(getattr(args, "prefer_melee_smoke_accounts", True))
        and bool(getattr(args, "require_melee_smoke_accounts", True))
        and account_rows_have_class_data(rows)
    )
    if live_smoke_melee_required:
        preferred_candidate_count = sum(1 for row in candidate_rows if account_row_is_melee_smoke_preferred(row))
        if preferred_candidate_count < case.party_size:
            skipped_names = skipped_completed + skipped_active
            skipped_note = f"; skipped completed/active accounts: {', '.join(skipped_names)}" if skipped_names else ""
            raise RuntimeError(
                f"not enough melee smoke account rows after offset {account_offset}: "
                f"{case.accounts_csv} has {preferred_candidate_count}/{case.party_size}{skipped_note}"
            )

    selected_rows = order_account_rows_for_dynamic_quest_smoke(
        candidate_rows,
        args,
        live_quest_filter_active=skip_completed,
    )[: case.party_size]

    if len(selected_rows) < case.party_size:
        skipped_names = skipped_completed + skipped_active
        skipped_note = f"; skipped completed/active accounts: {', '.join(skipped_names)}" if skipped_names else ""
        raise RuntimeError(
            f"not enough account rows after offset {account_offset}: "
            f"{case.accounts_csv} has {len(selected_rows)}/{case.party_size}{skipped_note}"
        )

    case.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = (
        case.output_dir / f"accounts-selected-p{case.party_size}.csv"
        if skip_completed
        else case_accounts_csv(case, args)
    )
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected_rows)
    skipped_names = skipped_completed + skipped_active
    if skipped_names:
        (case.output_dir / "accounts-skipped-completed.txt").write_text(
            "\n".join(skipped_names) + "\n",
            encoding="utf-8",
        )
    return output_path


def load_provision_module():
    module_path = Path(__file__).with_name("provision-dummy-accounts.py")
    spec = importlib.util.spec_from_file_location("provision_dummy_accounts_for_dynamic_quest_matrix", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_db_args(args: argparse.Namespace, provision_module) -> SimpleNamespace:
    mysql_bin = provision_module.resolve_mysql_bin(args.mysql_bin)
    db_password = args.db_password or provision_module.read_serverconfig_password()
    return SimpleNamespace(
        mysql_bin=mysql_bin,
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=db_password,
    )


def reset_case_start_positions(
    case: QuestCase,
    args: argparse.Namespace,
    start_position: StartPosition | None = None,
) -> None:
    accounts_csv = case_accounts_csv(case, args)
    account_rows = read_account_rows(accounts_csv if accounts_csv.exists() else case.accounts_csv)
    account_offset = 0 if accounts_csv.exists() and accounts_csv != case.accounts_csv else args.account_offset
    if start_position is None:
        start_position = resolve_case_start_position(case, args)
    sql = build_start_position_update_sql(
        case,
        account_rows,
        args.start_position_step,
        account_offset,
        start_position,
        player_level=case.player_level,
    )
    if not sql:
        raise RuntimeError(f"no account rows available for start-position reset: {case.accounts_csv}")

    case.output_dir.mkdir(parents=True, exist_ok=True)
    (case.output_dir / "start-position-reset.sql").write_text(sql + "\n", encoding="utf-8")

    provision_module = load_provision_module()
    db_args = build_db_args(args, provision_module)
    if not provision_module.mysql_bin_available(db_args.mysql_bin):
        raise RuntimeError(f"mysql client not found: {db_args.mysql_bin}")

    provision_module.run_mysql(db_args, sql)


def to_int(value: object) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def to_float(value: object) -> float:
    try:
        return float(str(value or "0"))
    except ValueError:
        return 0.0


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "ok"}


def row_has_dynamic_quest_completion(row: dict[str, object]) -> bool:
    return (
        to_int(row.get("action_dynamic_quest_complete_verified")) > 0
        or to_int(row.get("action_dynamic_quest_expected_active_node_verified")) > 0
        or to_int(row.get("action_dynamic_quest_final_inactive")) > 0
        or to_int(row.get("action_dynamic_quest_final_expected_active_node")) > 0
    )


def summarize_case(case_dir: Path, *, require_followup_hunt: bool = False) -> CaseSummary:
    metrics_path = case_dir / "metrics.csv"
    if not metrics_path.exists():
        return CaseSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0, False)

    with metrics_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    players = len(rows)
    ok_players = sum(1 for row in rows if truthy(row.get("ok")))
    completed = sum(1 for row in rows if row_has_dynamic_quest_completion(row))
    reward_observed = sum(1 for row in rows if to_int(row.get("action_dynamic_quest_reward_observed")) > 0)
    target_removed = sum(to_int(row.get("target_removed")) for row in rows)
    player_deaths = sum(to_int(row.get("player_deaths")) for row in rows)
    choice_selected = sum(to_int(row.get("action_dynamic_quest_timeline_choice_selected")) for row in rows)
    world_signal = sum(to_int(row.get("action_dynamic_quest_timeline_world_signal")) for row in rows)
    followup_hunt_start = sum(to_int(row.get("action_dynamic_quest_followup_hunt_start")) for row in rows)
    never_active = sum(
        1
        for row in rows
        if to_int(row.get("action_dynamic_quest_final_never_active")) > 0
    )
    elapsed_seconds = max((to_float(row.get("elapsed_seconds")) for row in rows), default=0.0)
    passed = (
        players > 0
        and ok_players == players
        and completed == players
        and player_deaths == 0
        and never_active == 0
        and (
            not require_followup_hunt
            or followup_hunt_start >= players
            or world_signal >= players
        )
    )
    return CaseSummary(
        players,
        ok_players,
        completed,
        reward_observed,
        target_removed,
        player_deaths,
        choice_selected,
        world_signal,
        followup_hunt_start,
        elapsed_seconds,
        passed,
    )


def write_case_summary(case: QuestCase, summary: CaseSummary) -> None:
    status = "passed" if summary.passed else "failed"
    text = (
        f"# {case.name}\n\n"
        f"- realm: {case.realm}\n"
        f"- party_size: {case.party_size}\n"
        f"- status: {status}\n"
        f"- players: {summary.players}\n"
        f"- ok_players: {summary.ok_players}\n"
        f"- completed: {summary.completed}\n"
        f"- reward_observed: {summary.reward_observed}\n"
        f"- target_removed: {summary.target_removed}\n"
        f"- player_deaths: {summary.player_deaths}\n"
        f"- choice_selected: {summary.choice_selected}\n"
        f"- world_signal: {summary.world_signal}\n"
        f"- followup_hunt_start: {summary.followup_hunt_start}\n"
        f"- elapsed_seconds: {summary.elapsed_seconds:.3f}\n"
    )
    (case.output_dir / "matrix-summary.md").write_text(text, encoding="utf-8")


def run_matrix(args: argparse.Namespace) -> int:
    args.output_root.mkdir(parents=True, exist_ok=True)
    commands_path = args.output_root / "commands.txt"
    failures = 0
    command_lines: list[str] = []

    for case in build_cases(args):
        case.output_dir.mkdir(parents=True, exist_ok=True)
        runtime_case = case
        start_position = None
        if should_resolve_live_case(args):
            try:
                runtime_case, start_position = resolve_live_case(case, args)
            except Exception as exc:  # noqa: BLE001 - matrix should keep reporting case failures.
                (case.output_dir / "matrix-summary.md").write_text(
                    f"# {case.name}\n\nfailed to resolve live dynamic quest binding: {exc}\n",
                    encoding="utf-8",
                )
                failures += 1
                continue

        if not case.accounts_csv.exists():
            command = build_behavior_command(runtime_case, args)
            command_lines.append(shlex.join(command))
            if args.dry_run:
                continue

            (case.output_dir / "matrix-summary.md").write_text(
                f"# {case.name}\n\nmissing accounts CSV: {case.accounts_csv}\n",
                encoding="utf-8",
            )
            failures += 1
            continue

        should_prepare_accounts = (
            int(getattr(args, "account_offset", 0) or 0) > 0
            or (
                bool(getattr(args, "skip_completed_dynamic_quest_accounts", True))
                and bool(text_value(getattr(runtime_case, "quest_id", "")))
            )
        )
        if not args.dry_run and should_prepare_accounts:
            try:
                prepare_case_accounts_csv(runtime_case, args, quest_id=getattr(runtime_case, "quest_id", ""))
            except Exception as exc:  # noqa: BLE001 - matrix should keep reporting case failures.
                (case.output_dir / "matrix-summary.md").write_text(
                    f"# {case.name}\n\nfailed to prepare accounts CSV: {exc}\n",
                    encoding="utf-8",
                )
                failures += 1
                continue

        command = build_behavior_command(runtime_case, args)
        command_lines.append(shlex.join(command))
        if args.dry_run:
            continue

        if args.reset_start_positions:
            try:
                reset_case_start_positions(runtime_case, args, start_position)
            except Exception as exc:  # noqa: BLE001 - matrix should keep reporting case failures.
                (case.output_dir / "matrix-summary.md").write_text(
                    f"# {case.name}\n\nfailed to reset start positions: {exc}\n",
                    encoding="utf-8",
                )
                failures += 1
                continue

        result = subprocess.run(command)
        if result.returncode != 0:
            failures += 1

        summary = summarize_case(
            case.output_dir,
            require_followup_hunt=bool(getattr(args, "dynamic_quest_followup_growth_target", False)),
        )
        write_case_summary(runtime_case, summary)
        if not summary.passed:
            failures += 1

    commands_path.write_text("\n".join(command_lines) + ("\n" if command_lines else ""), encoding="utf-8")
    return 1 if failures else 0


def main() -> int:
    return run_matrix(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
