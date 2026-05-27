#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


VALID_ROLES = {"fill", "healer", "tank", "dps", "support"}
ROLE_ROTATIONS = {
    "fill": "auto",
    "healer": "healer-support",
    "support": "healer-support",
    "tank": "melee-basic",
    "dps": "melee-burst",
}
RELEASE_PRIORITY = {
    "dps": 0,
    "fill": 1,
    "support": 2,
    "tank": 3,
    "healer": 4,
}
CLASS_ROLE_HINTS = {
    "armsman": {"tank", "dps"},
    "hero": {"tank", "dps"},
    "paladin": {"tank", "support"},
    "warrior": {"tank", "dps"},
    "cleric": {"healer", "support"},
    "druid": {"healer", "support"},
    "friar": {"healer", "support", "dps"},
    "healer": {"healer", "support"},
    "shaman": {"healer", "support"},
    "bard": {"healer", "support"},
    "skald": {"support", "dps"},
    "berserker": {"dps"},
    "blademaster": {"dps"},
    "cabalist": {"dps"},
    "champion": {"dps", "tank"},
    "eldritch": {"dps"},
    "enchanter": {"dps"},
    "mercenary": {"dps"},
    "minstrel": {"support", "dps"},
    "runemaster": {"dps"},
    "sorcerer": {"support", "dps"},
    "theurgist": {"support", "dps"},
    "wizard": {"dps"},
}
LIVE_COMPANION_FLEE_FLAGS = [
    "--flee-dynamic-safe-point",
    "--flee-safe-api-scout",
    "--flee-pressure-health-percent",
    "90",
    "--flee-safe-threat-radius",
    "6500",
    "--flee-safe-point-distance",
    "7000",
    "--flee-duration",
    "14",
]
ROOT = Path(__file__).resolve().parents[1]


class ActiveCompanion:
    def __init__(self, request: dict[str, Any], process: subprocess.Popen, account: str = "") -> None:
        self.request = request
        self.process = process
        self.account = account
        self.last_lease_refresh = time.monotonic()


def normalize_role(role: Any) -> str:
    normalized = str(role or "").strip().lower()
    return normalized if normalized in VALID_ROLES else "fill"


def role_to_rotation(role: Any) -> str:
    return ROLE_ROTATIONS[normalize_role(role)]


def party_vacancy(max_members: Any, group_size: Any) -> int:
    try:
        max_count = int(max_members)
        current_count = int(group_size)
    except (TypeError, ValueError):
        return 0
    return max(0, max_count - max(0, current_count))


def choose_release_candidate(members: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [member for member in members if bool(member.get("is_dummy") or member.get("isCompanion"))]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda member: (
            RELEASE_PRIORITY.get(normalize_role(member.get("role")), RELEASE_PRIORITY["fill"]),
            str(member.get("name") or ""),
        ),
    )[0]


def request_value(request: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in request and request[key] not in (None, ""):
            return request[key]
    return default


def is_mock_value(value: Any) -> bool:
    return value.__class__.__module__ == "unittest.mock"


def arg_string(args: argparse.Namespace, name: str, default: str = "") -> str:
    value = getattr(args, name, default)
    if is_mock_value(value):
        return default
    return str(value)


def arg_float(args: argparse.Namespace, name: str, default: float) -> float:
    value = getattr(args, name, default)
    if is_mock_value(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def arg_bool(args: argparse.Namespace, name: str, default: bool = False) -> bool:
    value = getattr(args, name, default)
    if is_mock_value(value):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def request_requester_key(request: dict[str, Any]) -> str:
    account = str(request_value(request, "requesterAccount", "RequesterAccount", default="")).strip().lower()
    if account:
        return f"account:{account}"
    name = str(request_value(request, "requesterName", "RequesterName", default="")).strip().lower()
    return f"name:{name}" if name else ""


def request_matches_requester(request: dict[str, Any], key: str) -> bool:
    return bool(key) and request_requester_key(request) == key


def member_identity_keys(member: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    account = str(member.get("account") or member.get("Account") or "").strip().lower()
    name = str(member.get("name") or member.get("Name") or "").strip().lower()
    if account:
        keys.add(f"account:{account}")
    if name:
        keys.add(f"name:{name}")
    return keys


def active_companion_member_rows(active: dict[str, ActiveCompanion], requester_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_id, companion in active.items():
        request = companion.request
        if not request_matches_requester(request, requester_key):
            continue
        rows.append(
            {
                "request_id": request_id,
                "name": request_value(request, "assignedCompanionName", "AssignedCompanionName", default=companion.account),
                "account": companion.account,
                "role": request_value(request, "requestedRole", "RequestedRole", default="fill"),
                "isCompanion": True,
            }
        )
    return rows


def active_companion_identity_keys(active: dict[str, ActiveCompanion], requester_key: str) -> set[str]:
    keys: set[str] = set()
    for row in active_companion_member_rows(active, requester_key):
        keys.update(member_identity_keys(row))
    return keys


def real_group_member_count(
    requester_state: dict[str, Any] | None,
    requester_key: str,
    active: dict[str, ActiveCompanion],
) -> int:
    if not isinstance(requester_state, dict):
        return 0

    companion_keys = active_companion_identity_keys(active, requester_key)
    count = 0
    for member in requester_state.get("groupMembers", []) or []:
        if not isinstance(member, dict):
            continue
        member_keys = member_identity_keys(member)
        if requester_key and requester_key in member_keys:
            continue
        if member_keys & companion_keys:
            continue
        if bool(member.get("isCompanion") or member.get("is_dummy")):
            continue
        count += 1
    return count


def choose_release_request_for_real_player_join(
    active: dict[str, ActiveCompanion],
    requester_key: str,
    requester_state: dict[str, Any] | None,
    release_counts: dict[str, int],
) -> str:
    real_count = real_group_member_count(requester_state, requester_key, active)
    already_released = int(release_counts.get(requester_key, 0) or 0)
    if real_count <= already_released:
        return ""

    candidate = choose_release_candidate(active_companion_member_rows(active, requester_key))
    return str(candidate.get("request_id") or "") if candidate else ""


def is_leave_request(request: dict[str, Any]) -> bool:
    role = str(request_value(request, "requestedRole", "RequestedRole", default="")).strip().lower()
    status = str(request_value(request, "status", "Status", default="")).strip().lower()
    return role == "leave" or status == "leaving"


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def split_words(value: Any) -> set[str]:
    return {
        part.strip().lower()
        for part in str(value or "").replace("|", ",").replace(";", ",").split(",")
        if part.strip()
    }


def companion_row_roles(row: dict[str, Any]) -> set[str]:
    explicit = split_words(row.get("role") or row.get("roles"))
    if explicit:
        return {normalize_role(role) for role in explicit}

    class_name = str(row.get("class_name") or row.get("class") or "").strip().lower()
    return set(CLASS_ROLE_HINTS.get(class_name, set()))


def row_matches_request_realm(row: dict[str, Any], request: dict[str, Any]) -> bool:
    request_realm = parse_int(request_value(request, "realm", "Realm", default=0))
    row_realm = parse_int(row.get("realm") or row.get("Realm"), default=0)
    return request_realm <= 0 or row_realm <= 0 or row_realm == request_realm


def row_matches_requested_role(row: dict[str, Any], requested_role: str) -> bool:
    role = normalize_role(requested_role)
    if role == "fill":
        return True

    row_roles = companion_row_roles(row)
    return not row_roles or role in row_roles


def row_home_position(row: dict[str, Any]) -> tuple[int, int, int] | None:
    x = row.get("home_x", row.get("x"))
    y = row.get("home_y", row.get("y"))
    z = row.get("home_z", row.get("z"))
    if x in (None, "") or y in (None, ""):
        return None
    return (parse_int(x), parse_int(y), parse_int(z))


def request_position(request: dict[str, Any]) -> tuple[int, int, int] | None:
    x = parse_int(request_value(request, "x", "X", default=0))
    y = parse_int(request_value(request, "y", "Y", default=0))
    z = parse_int(request_value(request, "z", "Z", default=0))
    if x == 0 and y == 0 and z == 0:
        return None
    return (x, y, z)


def first_account_home_waypoint(account_csv: str | Path) -> str:
    try:
        with Path(account_csv).open(encoding="utf-8-sig", newline="") as handle:
            row = next(csv.DictReader(handle), None)
    except (OSError, StopIteration):
        return ""
    if not row:
        return ""

    x = parse_int(row.get("home_x") or row.get("HomeX"))
    y = parse_int(row.get("home_y") or row.get("HomeY"))
    z = parse_int(row.get("home_z") or row.get("HomeZ"))
    if x <= 0 or y <= 0:
        return ""
    return f"{x},{y},{z}"


def requester_player_level(request: dict[str, Any], requester_state: dict[str, Any] | None = None) -> int:
    player = requester_state.get("player") if isinstance(requester_state, dict) else None
    if isinstance(player, dict):
        level = parse_int(player.get("level") or player.get("Level"))
        if level > 0:
            return level

    return parse_int(
        request_value(
            request,
            "playerLevel",
            "PlayerLevel",
            "requesterLevel",
            "RequesterLevel",
            "level",
            "Level",
            default=0,
        )
    )


def distance_squared(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def rank_companion_rows(request: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    realm_rows = [row for row in rows if row_matches_request_realm(row, request)]
    if realm_rows:
        rows = realm_rows

    requested_role = normalize_role(request_value(request, "requestedRole", "RequestedRole", default="fill"))
    role_rows = [row for row in rows if row_matches_requested_role(row, requested_role)]
    if role_rows:
        rows = role_rows

    target_position = request_position(request)
    if target_position is None:
        return rows

    indexed_rows = list(enumerate(rows))

    def sort_key(item: tuple[int, dict[str, Any]]) -> tuple[int, int, int]:
        index, row = item
        home = row_home_position(row)
        if home is None:
            return (1, 0, index)
        return (0, distance_squared(target_position, home), index)

    return [row for _, row in sorted(indexed_rows, key=sort_key)]


def select_companion_accounts_csv(
    request: dict[str, Any],
    account_csv: str | Path,
    run_dir: str | Path,
    excluded_accounts: set[str] | None = None,
) -> Path:
    source_path = Path(account_csv)
    requester_account = str(request_value(request, "requesterAccount", "RequesterAccount", default="")).strip().lower()
    requester_name = str(request_value(request, "requesterName", "RequesterName", default="")).strip().lower()
    excluded = {account.strip().lower() for account in (excluded_accounts or set()) if account.strip()}

    with source_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [row for row in reader]

    if not fieldnames:
        raise ValueError(f"account csv has no header: {source_path}")

    candidates = []
    for row in rows:
        username = str(row.get("username") or "").strip().lower()
        character = str(row.get("character") or row.get("name") or "").strip().lower()
        if requester_account and username == requester_account:
            continue
        if username in excluded:
            continue
        if requester_name and character == requester_name:
            continue
        candidates.append(row)

    candidates = rank_companion_rows(request, candidates)

    if not candidates:
        raise ValueError(f"no companion accounts left after excluding requester from {source_path}")

    target_path = Path(run_dir) / "companion-accounts.csv"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)
    return target_path


def first_account_username(account_csv: str | Path) -> str:
    with Path(account_csv).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            return str(row.get("username") or "").strip()
    return ""


def account_usernames_from_csv(account_csv: str | Path) -> list[str]:
    usernames: list[str] = []
    try:
        with Path(account_csv).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                username = str(row.get("username") or "").strip()
                if username:
                    usernames.append(username)
    except OSError:
        return []
    return usernames


def build_behavior_command(
    args: argparse.Namespace,
    request: dict[str, Any],
    account_csv: str | Path,
    run_dir: str | Path,
    requester_state: dict[str, Any] | None = None,
) -> list[str]:
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)

    request_id = str(request_value(request, "id", "Id", default="live-companion"))
    leader_name = str(request_value(request, "requesterName", "RequesterName", default="")).strip()
    role = normalize_role(request_value(request, "requestedRole", "RequestedRole", default="fill"))
    hold = str(getattr(args, "hold", 3600))
    combat_home = str(getattr(args, "combat_home_leash_distance", 4500))
    leader_waypoint = request_waypoint(request)
    companion_home_waypoint = first_account_home_waypoint(account_csv)
    player_level = requester_player_level(request, requester_state)

    command = [
        sys.executable,
        "tools/behavior-dummy-client.py",
        "--host",
        str(getattr(args, "host", "127.0.0.1")),
        "--port",
        str(getattr(args, "port", 10300)),
        "--api-port",
        str(getattr(args, "api_port", 5000)),
        "--accounts",
        str(account_csv),
        "--concurrency",
        "1",
        "--rounds",
        "1",
        "--hold",
        hold,
        "--party-size",
        "1",
        "--party-external-member-names",
        leader_name,
        "--party-auto-external-members",
        "--party-assist-only",
        "--party-use-assist-command",
        "--party-assist-interval",
        "0.6",
        "--party-assist-attack-delay",
        "0.3",
        "--party-follow-interval",
        "0.25",
        "--party-follow-step",
        "360",
        "--party-follow-distance",
        "450",
        "--follow-nearby-player",
        "--follow-player-name",
        leader_name,
        "--follow-player-max-distance",
        "12000",
        "--follow-player-hold-allows-waypoint",
        "--combat",
        "--move",
        "--smooth-movement",
        "--smooth-move-interval",
        "0.18",
        "--movement-speed",
        "280",
        "--movement-update-interval",
        "0.18",
        "--move-step",
        "320",
        "--use-skills",
        "--combat-usable-api",
        "--combat-usable-api-retries",
        "4",
        "--combat-usable-api-retry-delay",
        "0.4",
        "--action-rotation",
        role_to_rotation(role),
        *(
            [
                "--player-level",
                str(player_level),
                "--ideal-target-level",
                str(player_level),
                "--min-target-level",
                str(max(1, player_level - 8)),
            ]
            if player_level > 0
            else []
        ),
        "--auto-release-on-death",
        "--speak-state-changes",
        "--no-auto-loot",
        "--combat-home-leash-distance",
        combat_home,
        "--attack-range",
        "350",
        "--combat-direct-move-distance",
        "2200",
        "--melee-stick-attack",
        "--melee-stick-attack-distance",
        "1800",
        "--target-face-command-interval",
        "0.8",
        "--melee-range-buffer",
        "300",
        "--minimum-melee-stop-distance",
        "60",
        "--target-loss-grace",
        "2",
        "--live-control-file",
        str(run_path / "live-control.json"),
        "--live-control-interval",
        "0.5",
        *LIVE_COMPANION_FLEE_FLAGS,
        "--metrics-csv",
        str(run_path / f"{request_id}-metrics.csv"),
        "--report-md",
        str(run_path / f"{request_id}-report.md"),
        "--encounter-log",
        str(run_path / f"{request_id}-{{username}}-{{round}}-encounters.jsonl"),
        "--trace-movement-log",
        str(run_path / f"{request_id}-{{username}}-{{round}}-movement.jsonl"),
    ]
    if leader_waypoint:
        command += [
            "--waypoints",
            leader_waypoint,
            "--waypoint-interval",
            "0.6",
            "--waypoint-step",
            "520",
            "--waypoint-stop-distance",
            "650",
        ]
        if companion_home_waypoint:
            command += [
                "--flee-home",
                companion_home_waypoint,
            ]

    return [part for part in command if part != ""]


def request_waypoint(request: dict[str, Any]) -> str:
    try:
        x = int(request_value(request, "x", "X", default=0))
        y = int(request_value(request, "y", "Y", default=0))
        z = int(request_value(request, "z", "Z", default=0))
    except (TypeError, ValueError):
        return ""
    if x == 0 and y == 0 and z == 0:
        return ""
    return f"{x},{y},{z}"


def encode_query(query: dict[str, Any]) -> str:
    clean = {key: value for key, value in query.items() if value not in (None, "")}
    return urllib.parse.urlencode(clean)


def api_request(args: argparse.Namespace, method: str, path: str, query: dict[str, Any] | None = None) -> Any:
    base = str(args.api_url).rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    request_query = dict(query or {})
    api_password = arg_string(args, "api_password", "")
    if api_password and "password" not in request_query:
        request_query["password"] = api_password
    query_string = encode_query(request_query)
    url = f"{base}{suffix}" + (f"?{query_string}" if query_string else "")
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=args.api_timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    if not payload:
        return None
    return json.loads(payload)


def claim_next_request(args: argparse.Namespace) -> dict[str, Any] | None:
    return api_request(args, "POST", "/api/dummy/companions/requests/claim")


def update_request_status(
    args: argparse.Namespace,
    request_id: str,
    status: str,
    message: str = "",
    companion: str = "",
) -> None:
    api_request(
        args,
        "POST",
        f"/api/dummy/companions/requests/{urllib.parse.quote(request_id)}/status",
        {"status": status, "message": message, "companion": companion},
    )


def health_band_from_percent(value: Any) -> str:
    try:
        percent = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if percent <= 0:
        return "dead"
    if percent < 30:
        return "critical"
    if percent < 55:
        return "low"
    if percent < 85:
        return "normal"
    return "high"


def player_row(state: dict[str, Any] | None) -> dict[str, Any]:
    player = state.get("player") if isinstance(state, dict) else None
    return player if isinstance(player, dict) else {}


def numeric_percent(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def group_member_rows(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(state, dict):
        return []
    raw_members = state.get("groupMembers") or state.get("group_members") or state.get("partyMembers") or []
    return [member for member in raw_members if isinstance(member, dict)]


def party_dead_count(state: dict[str, Any] | None) -> int:
    return sum(1 for member in group_member_rows(state) if bool(member.get("isDead")) or bool(member.get("dead")))


def member_is_crowd_controlled(member: dict[str, Any]) -> bool:
    return any(
        bool(member.get(key))
        for key in ("isCrowdControlled", "isMezzed", "isStunned", "isDiseased", "isPoisoned", "isSilenced", "isNearsighted")
    )


def party_crowd_controlled_count(state: dict[str, Any] | None) -> int:
    return sum(1 for member in group_member_rows(state) if member_is_crowd_controlled(member))


def party_lowest_health_percent(state: dict[str, Any] | None) -> float | None:
    values = [
        percent
        for member in group_member_rows(state)
        if (percent := numeric_percent(member, "healthPercent", "health_percent")) is not None
    ]
    return min(values) if values else None


def estimate_add_count(state: dict[str, Any] | None) -> int:
    if not isinstance(state, dict):
        return 0
    for key in ("adds", "addCount", "add_count", "nearbyAddCount", "nearby_add_count"):
        try:
            return max(0, int(float(state.get(key))))
        except (TypeError, ValueError):
            continue

    target_ids: set[int] = set()
    for member in group_member_rows(state):
        try:
            target_id = int(member.get("targetObjectId") or member.get("target_object_id") or 0)
        except (TypeError, ValueError):
            target_id = 0
        if target_id <= 0:
            continue
        target_type = str(member.get("targetType") or member.get("target_type") or "").lower()
        if "gameplayer" in target_type:
            continue
        target_ids.add(target_id)
    return max(0, len(target_ids) - 1)


def dialogue_command_intent(event_type: str) -> str:
    event_type = str(event_type or "").strip().lower()
    if event_type in {"player_requested_heal", "leader_critical", "party_member_low_health"}:
        return "heal_priority"
    if event_type == "party_member_dead":
        return "resurrect_priority"
    if event_type == "add_pressure":
        return "cc_add"
    if event_type in {"party_member_crowd_controlled", "player_crowd_controlled"}:
        return "cure_priority"
    if event_type == "companion_joined":
        return "follow"
    if event_type in {"player_requested_wait", "companion_low_mana"}:
        return "wait"
    if event_type in {"leader_fleeing", "companion_fleeing"}:
        return "flee"
    return "none"


def companion_personality_for_role(role: Any) -> str:
    role = normalize_role(role)
    return {
        "tank": "steady_protector",
        "healer": "calm_support",
        "support": "tactical_support",
        "dps": "confident_striker",
        "fill": "steady_companion",
    }.get(role, "steady_companion")


def build_companion_dialogue_payload(
    companion: ActiveCompanion,
    requester_state: dict[str, Any] | None,
    event_type: str,
    companion_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    player = player_row(requester_state)
    companion_player = player_row(companion_state)
    role = request_value(companion.request, "requestedRole", "RequestedRole", default="fill")
    event_type = str(event_type or "status")
    return {
        "feature": "companion_dialogue",
        "event_type": event_type,
        "realm": str(request_value(companion.request, "realm", "Realm", default="unknown")),
        "role": normalize_role(role),
        "personality": companion_personality_for_role(role),
        "state": {
            "combat": bool(player.get("inCombat")),
            "leader_health_band": health_band_from_percent(player.get("healthPercent")),
            "party_lowest_health_band": health_band_from_percent(party_lowest_health_percent(requester_state)),
            "companion_health_band": health_band_from_percent(companion_player.get("healthPercent")),
            "companion_mana_band": health_band_from_percent(
                numeric_percent(companion_player, "manaPercent", "powerPercent", "mana_percent", "power_percent")
            ),
            "adds": estimate_add_count(requester_state),
            "party_dead": max(0, party_dead_count(requester_state)),
            "party_crowd_controlled": max(0, party_crowd_controlled_count(requester_state)),
            "player_called": event_type.startswith("player_requested_"),
            "command_intent": dialogue_command_intent(event_type),
        },
        "memory": "",
    }


SERVICE_ALLOWED_CHANNELS = {"party", "say", "none"}
SERVICE_ALLOWED_HINTS = {
    "none",
    "heal_priority",
    "resurrect_priority",
    "follow",
    "wait",
    "assist",
    "flee",
    "cc_add",
    "cure_priority",
}
SERVICE_ALLOWED_URGENCY = {"low", "normal", "high"}


def normalize_dialogue_intent_hint(value: Any) -> str:
    hint = str(value or "none").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "heal": "heal_priority",
        "healing": "heal_priority",
        "res": "resurrect_priority",
        "rez": "resurrect_priority",
        "resurrect": "resurrect_priority",
        "cc": "cc_add",
        "crowd_control": "cc_add",
        "mez": "cc_add",
        "stun": "cc_add",
        "cure": "cure_priority",
        "cleanse": "cure_priority",
        "purge": "cure_priority",
        "attack": "assist",
        "attack_assist": "assist",
        "escape": "flee",
    }
    hint = aliases.get(hint, hint)
    return hint if hint in SERVICE_ALLOWED_HINTS else "none"


def sanitize_companion_dialogue_response(response: dict[str, Any]) -> dict[str, str] | None:
    channel = str(response.get("say_channel") or "none").strip().lower()
    if channel not in SERVICE_ALLOWED_CHANNELS:
        return None
    urgency = str(response.get("urgency") or "normal").strip().lower()
    if urgency not in SERVICE_ALLOWED_URGENCY:
        return None
    text = " ".join(str(response.get("say_text") or "").split())
    if len(text) > 80:
        return None
    if text.startswith("/") or "\n/" in text or " /" in text:
        return None
    lowered = text.lower()
    forbidden = ("gold", "realm point", "drop rate", "ban", "gm", "보상", "골드", "추방")
    if any(word in lowered for word in forbidden):
        return None
    return {
        "say_channel": channel,
        "say_text": text,
        "intent_hint": normalize_dialogue_intent_hint(response.get("intent_hint")),
        "urgency": urgency,
    }


def write_companion_live_control(path: Path, response: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "revision": time.time_ns(),
        "say_channel": str(response.get("say_channel") or "none"),
        "say_text": str(response.get("say_text") or ""),
        "intent_hint": str(response.get("intent_hint") or "none"),
        "urgency": str(response.get("urgency") or "normal"),
    }
    path.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def companion_control_path(args: argparse.Namespace, request_id: str) -> Path:
    return Path(arg_string(args, "run_dir", "test-output/live-companions")) / request_id / "live-control.json"


def call_ai_gateway(args: argparse.Namespace, payload: dict[str, Any]) -> dict[str, Any]:
    command = [sys.executable, "tools/opendaoc-ai-gateway.py"]
    config = arg_string(args, "ai_gateway_config", "")
    if config:
        command += ["--config", config]
    command += [
        "generate",
        "--feature",
        "companion_dialogue",
        "--model-alias",
        arg_string(args, "ai_gateway_model_alias", "small-dialogue") or "small-dialogue",
        "--payload-json",
        json.dumps(payload, ensure_ascii=False),
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=arg_string(args, "repo_root", str(ROOT)),
            text=True,
            capture_output=True,
            timeout=arg_float(args, "ai_gateway_timeout", 5.0),
        )
    except subprocess.TimeoutExpired:
        return {"allowed": False, "blocked_reason": "gateway_timeout"}
    except OSError:
        return {"allowed": False, "blocked_reason": "gateway_process_failed"}
    if completed.returncode != 0:
        return {"allowed": False, "blocked_reason": "gateway_process_failed"}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"allowed": False, "blocked_reason": "gateway_invalid_stdout"}


def request_companion_dialogue(args: argparse.Namespace, payload: dict[str, Any], control_path: Path) -> bool:
    if not arg_bool(args, "dialogue_enabled", False):
        return False
    result = call_ai_gateway(args, payload)
    if not result.get("allowed"):
        return False
    response = result.get("response")
    if not isinstance(response, dict):
        return False
    sanitized = sanitize_companion_dialogue_response(response)
    if sanitized is None:
        return False
    write_companion_live_control(control_path, sanitized)
    return True


def emit_companion_dialogue(
    args: argparse.Namespace,
    companion: ActiveCompanion,
    requester_state: dict[str, Any] | None,
    event_type: str,
) -> bool:
    request_id = str(request_value(companion.request, "id", "Id", default=""))
    if not request_id:
        return False
    companion_state: dict[str, Any] | None = None
    if companion.account:
        try:
            companion_state = fetch_player_state_by_account(args, companion.account)
        except Exception:
            companion_state = None
    payload = build_companion_dialogue_payload(companion, requester_state, event_type, companion_state)
    return request_companion_dialogue(args, payload, companion_control_path(args, request_id))


def should_emit_dialogue(dialogue_state: dict[str, float], key: str, now: float, interval: float) -> bool:
    previous = float(dialogue_state.get(key, 0.0) or 0.0)
    if now - previous < max(0.0, interval):
        return False
    return True


def dialogue_event_for_requester_state(requester_state: dict[str, Any] | None) -> str:
    player = player_row(requester_state)
    try:
        health_percent = float(player.get("healthPercent") or 100)
    except (TypeError, ValueError):
        health_percent = 100
    if party_dead_count(requester_state) > 0:
        return "party_member_dead"
    if party_crowd_controlled_count(requester_state) > 0:
        return "party_member_crowd_controlled"
    if estimate_add_count(requester_state) > 0 and bool(player.get("inCombat")):
        return "add_pressure"
    if bool(player.get("inCombat")) and health_percent < 30:
        return "leader_critical"
    if bool(player.get("inCombat")) and health_percent < 55:
        return "player_requested_heal"
    lowest = party_lowest_health_percent(requester_state)
    if bool(player.get("inCombat")) and lowest is not None and lowest < 55:
        return "party_member_low_health"
    return ""


def fetch_requester_state(args: argparse.Namespace, request: dict[str, Any]) -> dict[str, Any] | None:
    requester_account = str(request_value(request, "requesterAccount", "RequesterAccount", default="")).strip()
    requester_name = str(request_value(request, "requesterName", "RequesterName", default="")).strip()
    query: dict[str, Any] = {}
    if requester_account:
        query["account"] = requester_account
    elif requester_name:
        query["name"] = requester_name
    else:
        return None

    state = api_request(args, "GET", "/api/dummy/combat/usable", query)
    if not isinstance(state, dict) or state.get("error"):
        return None
    player = state.get("player")
    return state if isinstance(player, dict) else None


def requester_spawn_ready(state: dict[str, Any] | None) -> tuple[bool, str]:
    if state is None:
        return False, "requester offline"
    player = state.get("player") if isinstance(state, dict) else None
    if not isinstance(player, dict):
        return False, "requester unavailable"
    if bool(player.get("isDead")) or bool(player.get("isAlive")) is False:
        return False, "requester dead"
    return True, ""


def fetch_player_state_by_account(args: argparse.Namespace, account: str) -> dict[str, Any] | None:
    if not account:
        return None
    state = api_request(args, "GET", "/api/dummy/combat/usable", {"account": account})
    if not isinstance(state, dict) or state.get("error"):
        return None
    player = state.get("player")
    return state if isinstance(player, dict) else None


def online_accounts_from_pool(args: argparse.Namespace, account_csv: str | Path) -> set[str]:
    online: set[str] = set()
    for account in account_usernames_from_csv(account_csv):
        try:
            if fetch_player_state_by_account(args, account) is not None:
                online.add(account.strip().lower())
        except Exception:
            continue
    return online


def wait_for_companion_online(args: argparse.Namespace, account_csv: str | Path) -> str:
    account = first_account_username(account_csv)
    if not account:
        return ""
    deadline = time.monotonic() + max(0.0, float(getattr(args, "attach_timeout", 0.0)))
    while time.monotonic() <= deadline:
        if fetch_player_state_by_account(args, account) is not None:
            return account
        time.sleep(0.5)
    return ""


def attach_companion_to_request(args: argparse.Namespace, request_id: str, account: str) -> tuple[bool, str]:
    try:
        payload = api_request(
            args,
            "POST",
            f"/api/dummy/companions/requests/{urllib.parse.quote(request_id)}/attach",
            {"account": account},
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return False, detail or f"attach failed with HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)
    if payload is None:
        return False, "attach failed: request or companion not found"
    return True, ""


def detach_companion_from_request(args: argparse.Namespace, request_id: str, account: str) -> tuple[bool, str]:
    try:
        payload = api_request(
            args,
            "POST",
            f"/api/dummy/companions/requests/{urllib.parse.quote(request_id)}/detach",
            {"account": account},
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return False, detail or f"detach failed with HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)
    if payload is None:
        return False, "detach failed: request or companion not found"
    return True, ""


def stop_companion(process: subprocess.Popen, timeout: float = 5.0) -> None:
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=timeout)


def stop_all_active_companions(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    reason: str,
) -> None:
    for request_id, companion in list(active.items()):
        stop_companion(companion.process)
        try:
            update_request_status(args, request_id, "completed", reason, companion.account)
        finally:
            active.pop(request_id, None)


def release_active_companions_for_leave_request(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    leave_request: dict[str, Any],
) -> int:
    requester_key = request_requester_key(leave_request)
    if not requester_key:
        return 0

    released = 0
    for request_id, companion in list(active.items()):
        if not request_matches_requester(companion.request, requester_key):
            continue

        detached, message = detach_companion_from_request(args, request_id, companion.account)
        stop_companion(companion.process)
        status_message = "leave request; companion released"
        if not detached and message:
            status_message = f"{status_message}; detach warning: {message}"
        update_request_status(args, request_id, "completed", status_message, companion.account)
        active.pop(request_id, None)
        released += 1
    return released


def handle_request(
    args: argparse.Namespace,
    request: dict[str, Any],
    active: dict[str, ActiveCompanion],
) -> None:
    request_id = str(request_value(request, "id", "Id", default=""))
    if is_leave_request(request):
        released = release_active_companions_for_leave_request(args, active, request)
        message = (
            f"leave request acknowledged; released {released} companion(s)"
            if released
            else "leave request acknowledged; no active companion"
        )
        update_request_status(args, request_id, "completed", message)
        return

    requester_state = fetch_requester_state(args, request)
    ready, reason = requester_spawn_ready(requester_state)
    if not ready:
        update_request_status(args, request_id, "failed", f"cannot spawn companion: {reason}")
        return

    run_dir = Path(args.run_dir) / request_id
    active_accounts = {companion.account.lower() for companion in active.values() if companion.account}
    active_accounts.update(online_accounts_from_pool(args, args.accounts_csv))
    try:
        companion_accounts_csv = select_companion_accounts_csv(request, args.accounts_csv, run_dir, active_accounts)
        companion_account = first_account_username(companion_accounts_csv)
        if not companion_account:
            raise ValueError("selected companion account csv has no usable account")
        command = build_behavior_command(args, request, companion_accounts_csv, run_dir, requester_state=requester_state)
    except (OSError, ValueError) as exc:
        update_request_status(args, request_id, "failed", f"cannot spawn companion: {exc}")
        return

    if args.dry_run:
        print(json.dumps({"request": request, "command": command}, ensure_ascii=False))
        return

    update_request_status(args, request_id, "spawning", "starting live companion behavior client")
    process = subprocess.Popen(command, cwd=args.repo_root)
    active[request_id] = ActiveCompanion(request=request, process=process, account=companion_account)
    update_request_status(args, request_id, "grouping", "live companion behavior client started; waiting for grouping", companion_account)
    companion = active[request_id]

    if getattr(args, "attach_group", True):
        account = wait_for_companion_online(args, companion_accounts_csv)
        if not account:
            stop_companion(process)
            active.pop(request_id, None)
            update_request_status(args, request_id, "failed", "companion did not appear online before grouping timeout")
            return

        attached, message = attach_companion_to_request(args, request_id, account)
        if not attached:
            stop_companion(process)
            active.pop(request_id, None)
            update_request_status(args, request_id, "failed", f"group attach failed: {message}", account)
            return
        emit_companion_dialogue(args, companion, requester_state, "companion_joined")
    else:
        update_request_status(args, request_id, "active", "live companion behavior client started")
        emit_companion_dialogue(args, companion, requester_state, "companion_joined")


def release_companion_for_real_player(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    request_id: str,
    release_counts: dict[str, int],
    requester_key: str,
) -> None:
    companion = active.get(request_id)
    if companion is None:
        return

    detached, message = detach_companion_from_request(args, request_id, companion.account)
    stop_companion(companion.process)
    status_message = "real player joined; companion released"
    if not detached and message:
        status_message = f"{status_message}; detach warning: {message}"
    update_request_status(args, request_id, "completed", status_message, companion.account)
    active.pop(request_id, None)
    release_counts[requester_key] = int(release_counts.get(requester_key, 0) or 0) + 1


def refresh_active_companion_lease(
    args: argparse.Namespace,
    request_id: str,
    companion: ActiveCompanion,
    now: float,
) -> None:
    interval = arg_float(args, "active_lease_refresh_interval", 30.0)
    if companion.last_lease_refresh and now - companion.last_lease_refresh < max(1.0, interval):
        return
    update_request_status(args, request_id, "active", "live companion heartbeat", companion.account)
    companion.last_lease_refresh = now


def poll_active(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    release_counts: dict[str, int] | None = None,
    dialogue_state: dict[str, float] | None = None,
) -> None:
    release_counts = release_counts if release_counts is not None else {}
    dialogue_state = dialogue_state if dialogue_state is not None else {}
    finished: list[str] = []
    requester_states: dict[str, dict[str, Any] | None] = {}
    for request_id, companion in list(active.items()):
        process = companion.process
        return_code = process.poll()
        if return_code is None:
            requester_key = request_requester_key(companion.request)
            requester_state = requester_states.setdefault(requester_key, fetch_requester_state(args, companion.request))
            if requester_state is None:
                stop_companion(process)
                update_request_status(args, request_id, "completed", "requester offline; companion stopped")
                finished.append(request_id)
            else:
                refresh_active_companion_lease(args, request_id, companion, time.monotonic())
                event_type = dialogue_event_for_requester_state(requester_state)
                if event_type:
                    dialogue_key = f"{request_id}:{event_type}"
                    if should_emit_dialogue(
                        dialogue_state,
                        dialogue_key,
                        time.monotonic(),
                        arg_float(args, "dialogue_min_interval", 5.0),
                    ):
                        if emit_companion_dialogue(args, companion, requester_state, event_type):
                            dialogue_state[dialogue_key] = time.monotonic()
            continue
        status = "completed" if return_code == 0 else "failed"
        update_request_status(args, request_id, status, f"behavior client exited with {return_code}")
        finished.append(request_id)
    for request_id in finished:
        active.pop(request_id, None)

    for requester_key, requester_state in requester_states.items():
        request_id = choose_release_request_for_real_player_join(active, requester_key, requester_state, release_counts)
        if request_id:
            release_companion_for_real_player(args, active, request_id, release_counts, requester_key)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run live companion behavior clients from server companion requests.")
    parser.add_argument("--api-url", default="http://localhost:5000")
    parser.add_argument("--api-timeout", type=float, default=2.0)
    parser.add_argument("--api-password", default=os.environ.get("OPENDAOC_API_PASSWORD", ""))
    parser.add_argument("--accounts-csv", default=str(Path(__file__).resolve().with_name("dummy-live-companions.csv")))
    parser.add_argument("--run-dir", default="test-output/live-companions")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--hold", type=float, default=3600.0)
    parser.add_argument("--combat-home-leash-distance", type=float, default=4500.0)
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--attach-timeout", type=float, default=15.0)
    parser.add_argument("--attach-group", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--active-lease-refresh-interval", type=float, default=30.0)
    parser.add_argument("--dialogue-enabled", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--ai-gateway-config", default="")
    parser.add_argument("--ai-gateway-model-alias", default="small-dialogue")
    parser.add_argument("--ai-gateway-timeout", type=float, default=5.0)
    parser.add_argument("--dialogue-min-interval", type=float, default=5.0)
    parser.add_argument("--max-runtime", type=float, default=0.0, help="stop the service after this many seconds; 0 runs until interrupted")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    active: dict[str, ActiveCompanion] = {}
    release_counts: dict[str, int] = {}
    dialogue_state: dict[str, float] = {}
    deadline = time.monotonic() + max(0.0, float(args.max_runtime)) if args.max_runtime else None

    try:
        while True:
            poll_active(args, active, release_counts, dialogue_state)
            request = claim_next_request(args)
            if request is not None:
                handle_request(args, request, active)
            elif args.once:
                return 0

            if deadline is not None and time.monotonic() >= deadline:
                return 0

            if args.once:
                poll_active(args, active, release_counts, dialogue_state)
                return 0
            time.sleep(max(0.25, args.poll_interval))
    finally:
        if active:
            stop_all_active_companions(args, active, "companion service stopped; companion stopped")


if __name__ == "__main__":
    raise SystemExit(main())
