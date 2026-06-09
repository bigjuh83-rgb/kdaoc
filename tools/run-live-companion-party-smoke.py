#!/usr/bin/env python3
"""Run a fast live-companion party smoke with one dummy acting as the real player."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def load_env_file_defaults(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


load_env_file_defaults(ROOT / ".env")

DEFAULT_LEADER_CANDIDATES = TOOLS / "dummy-party-albion-pve8.csv"
DEFAULT_COMPANION_POOL = TOOLS / "dummy-live-companions.csv"
BARFOG_HOME = (332701, 669142, 2660)
BARFOG_STAGING_HOME = (343893, 672100, 2659)
BARFOG_WAYPOINTS = "332701,669142,2660|333061,669142,2668|333061,669502,2702|332701,669502,2694"
ALBION_SAFE_FLEE_HOME = "369957,679721,5540"
DEFAULT_ROLES = ["tank", "healer", "dps"]
DEFAULT_LEADER_HOLD_SECONDS = 150.0
DEFAULT_LEADER_STARTUP_DELAY_SECONDS = 60.0
DEFAULT_COMPANION_HOLD_SECONDS = 105.0
DEFAULT_SERVICE_MAX_RUNTIME_SECONDS = 150.0
STEALTH_PASSIVE_LEADER_HOLD_SECONDS = 55.0
STEALTH_PASSIVE_LEADER_STARTUP_DELAY_SECONDS = 25.0
STEALTH_PASSIVE_COMPANION_HOLD_SECONDS = 55.0
STEALTH_PASSIVE_SERVICE_MAX_RUNTIME_SECONDS = 90.0
ROLE_SMOKE_LEADER_HOLD_SECONDS = 90.0
ROLE_SMOKE_LEADER_STARTUP_DELAY_SECONDS = 35.0
ROLE_SMOKE_COMPANION_HOLD_SECONDS = 90.0
ROLE_SMOKE_SERVICE_MAX_RUNTIME_SECONDS = 120.0
PLAYER_COMMAND_LEADER_HOLD_SECONDS = 90.0
PLAYER_COMMAND_LEADER_STARTUP_DELAY_SECONDS = 35.0
PLAYER_COMMAND_COMPANION_HOLD_SECONDS = 90.0
PLAYER_COMMAND_SERVICE_MAX_RUNTIME_SECONDS = 120.0
PLAYER_COMMAND_DEFAULT_PARTY_COMMANDS = ["명령어", "ㄱㄱ"]
PLAYER_COMMAND_MODES_DEFAULT_PARTY_COMMANDS = ["명령어", "수동태세", "방어태세", "대기", "여기로", "따라와"]
PLAYER_COMMAND_ALL_ROLES_DEFAULT_PARTY_COMMANDS = ["명령어", "수동태세", "방어태세", "대기", "여기로", "따라와", "ㄱㄱ"]
PLAYER_CHAT_ONLY_DEFAULT_PARTY_COMMANDS = ["용병아 너 어디 출신이야?", "용병아 오늘 어때?", "대기"]
PLAYER_COMMAND_DEFAULT_COMMAND_START_DELAY_AFTER_STARTUP_SECONDS = 8.0
PLAYER_COMMAND_DEFAULT_COMMAND_GAP_SECONDS = 5.0
PLAYER_COMMAND_DEFAULT_CONTROL_APPLY_TIMEOUT_SECONDS = 20.0
# Boss-fight role smokes routinely see 1-2 companion deaths without invalidating the
# expected role action. The matrix should fail on missing actions, not on this noise.
ROLE_SMOKE_ALLOW_COMPANION_DEATHS = 2
CASTER_DPS_LEADER_HOLD_SECONDS = 80.0
CASTER_DPS_COMPANION_HOLD_SECONDS = 90.0
CASTER_DPS_SERVICE_MAX_RUNTIME_SECONDS = 120.0
MIXED_REAL_JOIN_LEADER_HOLD_SECONDS = 120.0
MIXED_REAL_JOIN_LEADER_STARTUP_DELAY_SECONDS = 45.0
MIXED_REAL_JOIN_COMPANION_HOLD_SECONDS = 125.0
MIXED_REAL_JOIN_SERVICE_MAX_RUNTIME_SECONDS = 170.0
MIXED_REAL_JOIN_JOINER_HOLD_SECONDS = 85.0
MIXED_REAL_JOIN_RELEASE_TIMEOUT_SECONDS = 45.0
MIXED_REAL_JOIN_ACTIVE_TIMEOUT_SECONDS = 60.0
HEALER_RESURRECTION_REAL_JOIN_JOINER_HOLD_SECONDS = 175.0
HEALER_RESURRECTION_REAL_JOIN_JOINER_FOLLOW_DISTANCE = 450.0
HEALER_RESURRECTION_REAL_JOIN_JOINER_ASSIST_ATTACK_DELAY = 0.3
HEALER_RESURRECTION_REAL_JOIN_JOINER_DEATH_RELEASE_DELAY = 90.0
HEALER_RESURRECTION_REAL_JOIN_JOINER_FLEE_PRESSURE_HEALTH_PERCENT = 0.0
HEALER_RESURRECTION_REAL_JOIN_JOINER_FLEE_HEALTH_PERCENT = 0.0
# The joiner is the designated resurrection victim. A live boss fight will not
# reliably kill a specific party member (the party AI is built to survive), so
# the smoke deterministically kills the joiner once via the server test hook
# (POST /api/dummy/companions/test/kill). The joiner keeps a 90s release delay so
# it stays a resolvable corpse, and the healer resurrects it.
HEALER_RESURRECTION_VICTIM_KILL_DELAY_SECONDS = 45.0
HEALER_RESURRECTION_SERVICE_HEALER_FLEE_PRESSURE_HEALTH_PERCENT = 50.0
HEALER_RESURRECTION_SERVICE_HEALER_FLEE_HEALTH_PERCENT = 32.0
HEALER_RESURRECTION_SERVICE_FLEE_PRESSURE_HEALTH_PERCENT = 50.0
HEALER_RESURRECTION_SERVICE_FLEE_HEALTH_PERCENT = 32.0
HEALER_RESURRECTION_LEADER_FLEE_PRESSURE_HEALTH_PERCENT = 50.0
HEALER_RESURRECTION_LEADER_FLEE_HEALTH_PERCENT = 32.0
HEALER_RESURRECTION_ALLOW_COMPANION_DEATHS = 3
HEALER_RESURRECTION_LEADER_HOLD_SECONDS = 180.0
HEALER_RESURRECTION_LEADER_STARTUP_DELAY_SECONDS = 20.0
HEALER_RESURRECTION_COMPANION_HOLD_SECONDS = 180.0
HEALER_RESURRECTION_SERVICE_MAX_RUNTIME_SECONDS = 210.0
HEALER_RESURRECTION_LEADER_SAFE_EXIT_MAX_SECONDS = 60.0
HEALER_RESURRECTION_LEADER_PARTY_MIN_READY = 2
HEALER_RESURRECTION_LEADER_PARTY_READY_MAX_DISTANCE = 2800.0
HEALER_RESURRECTION_LEADER_PARTY_FORM_UP_DELAY = 4.0
HEALER_RESURRECTION_LEADER_PARTY_FORM_UP_TIMEOUT = 45.0
HEALER_RESURRECTION_LEADER_PRE_PULL_HOME_STOP_DISTANCE = 1800.0
# Baseline safe-staging spacing. The healer holds here and only darts in to the
# corpse via the resurrection-target approach once a dead member is resolved, so
# these do not need to sit inside cast range. (Earlier 2800/3000 tuning was a
# band-aid that pushed the healer even further out; reverted to baseline.)
HEALER_RESURRECTION_SERVICE_HEALER_BOSS_RANGED_SAFE_DISTANCE = 2200.0
HEALER_RESURRECTION_SERVICE_HEALER_PARTY_PREENGAGE_RANGED_SAFE_DISTANCE = 2400.0
HEALER_RESURRECTION_SERVICE_HEALER_BOSS_NON_TANK_FOLLOW_DISTANCE = 2200.0
LEADER_SAFE_EXIT_MAX_SECONDS = 30.0
COMPANION_LEADER_EXIT_BUFFER_SECONDS = 45.0
SERVICE_LEADER_EXIT_BUFFER_SECONDS = 75.0
SUMMARY_EXPECTATION_KEYS = {
    "party_follow",
    "party_assist",
    "party_protection",
    "heal",
    "resurrect",
    "cure",
    "crowd_control",
    "speed_song",
    "stealth",
    "taunt",
    "damage_done",
    "target_rejected",
    "party_member_target_rejected",
    "dialogue_live_control",
    "dialogue_party",
    "dialogue_say",
    "dialogue_heal_priority",
    "dialogue_resurrect_priority",
    "dialogue_cc_add",
    "dialogue_cure_priority",
    "companion_chat_reply",
    "companion_command_attack",
    "companion_command_passive",
    "companion_command_defensive",
    "companion_command_stay",
    "companion_command_follow",
    "companion_command_help",
    "companion_command_summon",
    "companion_command_wait",
    "companion_command_clear_target",
}
EXPECTED_ACTION_ALIASES = {
    "cc": "crowd_control",
    "crowdcontrol": "crowd_control",
    "crowd_control": "crowd_control",
    "crowd-control": "crowd_control",
    "guard": "party_protection",
    "protect": "party_protection",
    "party_protect": "party_protection",
    "party-protect": "party_protection",
    "party_protection": "party_protection",
    "party-protection": "party_protection",
    "res": "resurrect",
    "rez": "resurrect",
    "speedsong": "speed_song",
    "speed_song": "speed_song",
    "speed-song": "speed_song",
    "tank_taunt": "taunt",
    "chat_reply": "companion_chat_reply",
    "chat-reply": "companion_chat_reply",
    "command_attack": "companion_command_attack",
    "command-attack": "companion_command_attack",
    "command_passive": "companion_command_passive",
    "command-passive": "companion_command_passive",
    "command_defensive": "companion_command_defensive",
    "command-defensive": "companion_command_defensive",
    "command_stay": "companion_command_stay",
    "command-stay": "companion_command_stay",
    "command_follow": "companion_command_follow",
    "command-follow": "companion_command_follow",
    "command_help": "companion_command_help",
    "command-help": "companion_command_help",
    "command_summon": "companion_command_summon",
    "command-summon": "companion_command_summon",
    "command_wait": "companion_command_wait",
    "command-wait": "companion_command_wait",
    "command_clear": "companion_command_clear_target",
    "command-clear": "companion_command_clear_target",
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


growth = load_module(TOOLS / "run-dummy-growth-suite.py", "dummy_growth_suite_for_live_companion_smoke")
companion_service = load_module(
    TOOLS / "dummy-companion-service.py",
    "dummy_companion_service_for_live_companion_smoke",
)


def effective_party_size(args: argparse.Namespace) -> int:
    size = 1 + len(getattr(args, "roles", []) or [])
    if getattr(args, "real_player_join", False):
        size += 1
    return size


def leader_party_command_texts(args: argparse.Namespace) -> list[str]:
    commands = getattr(args, "leader_party_commands", []) or []
    if isinstance(commands, str):
        commands = [commands]
    return [str(command or "").strip() for command in commands if str(command or "").strip()]


def leader_live_control_enabled(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "real_player_join", False) or leader_party_command_texts(args))


def leader_chat_only_enabled(args: argparse.Namespace) -> bool:
    profile = str(getattr(args, "smoke_profile", "") or "").strip().lower().replace("_", "-")
    return bool(getattr(args, "leader_chat_only", False) or profile in {"player-chat-only", "player-command-chat", "chat-only"})


CHAT_ONLY_LEADER_FLAG_OPTIONS = {
    "--hunter",
    "--combat",
    "--party-local-rescue-target",
    "--reject-target-on-server-los-failure",
    "--include-peace-npcs",
    "--current-target-api-refresh",
    "--hunter-target-api-scout",
    "--allow-avoid-target-fallback",
    "--combat-usable-api",
    "--melee-stick-attack",
    "--smooth-movement",
    "--waypoint-continuous-turns",
    "--use-skills",
    "--allow-unvalidated-skills",
    "--auto-loot",
    "--auto-release-on-death",
    "--flee-use-sprint",
    "--flee-dynamic-safe-point",
    "--flee-safe-api-scout",
    "--target-auto-lowest-visible-level",
    "--allow-preferred-low-con-fallback",
}


CHAT_ONLY_LEADER_VALUE_OPTIONS = {
    "--ideal-target-level",
    "--min-target-level",
    "--max-target-level",
    "--max-target-level-delta",
    "--max-target-distance",
    "--target-home-max-distance",
    "--combat-home-leash-distance",
    "--target-timeout",
    "--target-loss-grace",
    "--server-los-failure-target-cooldown",
    "--server-los-failure-grace",
    "--target-selection",
    "--hunter-target-api-radius",
    "--hunter-target-api-engage-distance",
    "--hunter-target-max-ground-z-delta",
    "--hunter-min-time-left-for-new-target",
    "--combat-usable-api-retries",
    "--combat-usable-api-retry-delay",
    "--combat-interval",
    "--target-pool",
    "--attack-range",
    "--combat-direct-move-distance",
    "--attack-target-in-view-prime-delay",
    "--melee-stick-attack-distance",
    "--target-face-command-interval",
    "--melee-range-buffer",
    "--minimum-melee-stop-distance",
    "--move-step",
    "--smooth-move-interval",
    "--movement-speed",
    "--movement-update-interval",
    "--waypoints",
    "--waypoint-mode",
    "--waypoint-advance-distance",
    "--waypoint-stop-distance",
    "--required-target-home",
    "--required-target-home-stop-distance",
    "--required-target-home-hunt-distance",
    "--required-target-recover-before-home-health-percent",
    "--skill-interval",
    "--skill-indexes",
    "--skill-type",
    "--startup-self-buff-count",
    "--startup-self-buff-delay",
    "--death-release-delay",
    "--death-recovery-cooldown",
    "--post-release-rest",
    "--low-health-rest-percent",
    "--low-health-rest-resume-percent",
    "--flee-health-percent",
    "--flee-pressure-health-percent",
    "--flee-duration",
    "--flee-step",
    "--flee-move-interval",
    "--flee-movement-speed",
    "--flee-home",
    "--flee-home-stop-distance",
    "--flee-safe-threat-radius",
    "--flee-safe-point-distance",
    "--flee-critical-health-percent",
    "--flee-critical-safe-point-distance",
    "--flee-safe-replan-damage-grace",
    "--travel-aggro-clear-grace",
    "--travel-aggro-avoid-seconds",
    "--travel-aggro-avoid-radius",
    "--flee-town-health-percent",
    "--flee-min-combat-seconds",
    "--flee-min-damage-taken",
    "--flee-damage-taken-ratio",
    "--flee-melee-counterattack-health-floor",
    "--required-target-tank-commit-health-percent",
    "--nav-api-url",
    "--require-target-name",
    "--prefer-target-name",
    "--preferred-low-con-min-level",
    "--avoid-target-name",
}


def strip_cli_options(command: list[str], *, flags: set[str], options_with_values: set[str]) -> list[str]:
    stripped: list[str] = []
    index = 0
    while index < len(command):
        option = command[index]
        if option in flags:
            index += 1
            continue
        if option in options_with_values:
            index += 2
            continue
        stripped.append(option)
        index += 1
    return stripped


def parse_roles(value: str) -> list[str]:
    roles = [part.strip().lower() for part in str(value or "").replace("|", ",").split(",") if part.strip()]
    return roles or list(DEFAULT_ROLES)


def normalize_expected_action(value: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    return EXPECTED_ACTION_ALIASES.get(normalized, normalized)


def parse_expected_actions(value: str) -> list[str]:
    actions: list[str] = []
    for part in str(value or "").replace("|", ",").split(","):
        normalized = normalize_expected_action(part)
        if not normalized:
            continue
        if normalized not in SUMMARY_EXPECTATION_KEYS:
            raise argparse.ArgumentTypeError(
                f"unsupported expected companion action '{part.strip()}'; choose from {', '.join(sorted(SUMMARY_EXPECTATION_KEYS))}"
            )
        if normalized not in actions:
            actions.append(normalized)
    return actions


def cli_number(value: float, *, whole: bool = False) -> str:
    if whole:
        return str(int(round(float(value))))
    return str(value)


def read_accounts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_accounts_or_empty(path: Path) -> list[dict[str, str]]:
    try:
        return read_accounts(path)
    except OSError:
        return []


def row_roles(row: dict[str, Any] | None) -> set[str]:
    roles: set[str] = set()
    for part in str((row or {}).get("roles") or (row or {}).get("Roles") or "").replace("|", ",").split(","):
        normalized = part.strip().lower()
        if normalized:
            roles.add(normalized)
    return roles


def account_row_for_username(paths: list[Path], username: str) -> dict[str, str]:
    target = str(username or "").strip().lower()
    if not target:
        return {}

    seen: set[Path] = set()
    for path in paths:
        candidate_path = Path(path)
        if candidate_path in seen:
            continue
        seen.add(candidate_path)
        for row in read_accounts_or_empty(candidate_path):
            if str(row.get("username") or "").strip().lower() == target:
                return row
    return {}


def resolve_joiner_row(args: argparse.Namespace, joiner_account: str) -> dict[str, str]:
    return account_row_for_username(
        [Path(args.leader_candidates_csv), Path(args.companion_accounts_csv)],
        joiner_account,
    )


def primary_joiner_role(row: dict[str, Any] | None) -> str:
    roles = set(companion_service.companion_row_roles(row or {}))
    for role in ("dps", "tank", "healer", "support"):
        if role in roles:
            return role
    return "dps"


def joiner_behavior_profile(role: str) -> str:
    return "party-tank" if str(role or "").strip().lower() == "tank" else "party-dps"


def candidate_priority(row: dict[str, Any], *, preferred_roles: set[str], avoided_roles: set[str]) -> tuple[int, int, int]:
    roles = row_roles(row)
    has_preferred = 0 if preferred_roles.intersection(roles) else 1
    has_avoided = 1 if avoided_roles.intersection(roles) else 0
    role_count = len(roles)
    return has_preferred, has_avoided, role_count


def ordered_leader_candidate_rows(args: argparse.Namespace, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    smoke_profile = str(getattr(args, "smoke_profile", "") or "").strip().lower().replace("_", "-")
    if smoke_profile == "tank-protection":
        ranked = sorted(
            enumerate(rows),
            key=lambda item: (
                *candidate_priority(item[1], preferred_roles={"dps"}, avoided_roles={"tank", "healer", "support"}),
                item[0],
            ),
        )
        return [row for _, row in ranked]
    if str(getattr(args, "leader_behavior_profile", "") or "") != "party-tank":
        return rows
    ranked = sorted(
        enumerate(rows),
        key=lambda item: (
            *candidate_priority(item[1], preferred_roles={"tank"}, avoided_roles={"healer", "support"}),
            item[0],
        ),
    )
    return [row for _, row in ranked]


def ordered_joiner_candidate_rows(args: argparse.Namespace, rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not getattr(args, "real_player_join", False):
        return rows
    smoke_profile = str(getattr(args, "smoke_profile", "") or "").strip().lower().replace("_", "-")
    preferred_roles = {"dps"}
    avoided_roles = {"tank", "healer"}
    if smoke_profile == "mixed-real-join":
        preferred_roles = {"tank"}
        avoided_roles = {"healer", "support"}
    ranked = sorted(
        enumerate(rows),
        key=lambda item: (
            *candidate_priority(item[1], preferred_roles=preferred_roles, avoided_roles=avoided_roles),
            item[0],
        ),
    )
    return [row for _, row in ranked]


def write_accounts(path: Path, rows: list[dict[str, Any]]) -> None:
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
        writer.writerows(rows)


def prepare_service_accounts_csv(
    args: argparse.Namespace,
    run_dir: Path,
    *excluded_accounts: str,
) -> Path:
    source_path = Path(args.companion_accounts_csv)
    excluded = {str(account or "").strip().lower() for account in excluded_accounts if str(account or "").strip()}
    if not excluded:
        return source_path

    rows = read_accounts_or_empty(source_path)
    filtered_rows = [
        row
        for row in rows
        if str(row.get("username") or "").strip().lower() not in excluded
    ]
    if len(filtered_rows) == len(rows):
        return source_path
    if not filtered_rows:
        raise RuntimeError("no companion accounts remain after excluding leader/joiner smoke accounts")

    filtered_path = run_dir / "service-companion-accounts.csv"
    write_accounts(filtered_path, filtered_rows)
    return filtered_path


def character_name_from_account(account: str) -> str:
    text = str(account or "").strip()
    if text.lower().startswith("dummy"):
        return "Dummy" + text[5:]
    return text[:1].upper() + text[1:]


def encode_query(query: dict[str, Any] | None = None) -> str:
    clean = {key: value for key, value in (query or {}).items() if value not in (None, "")}
    return urllib.parse.urlencode(clean)


def api_json(args: argparse.Namespace, method: str, path: str, query: dict[str, Any] | None = None) -> Any:
    base = str(args.api_url).rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    request_query = dict(query or {})
    api_password = str(getattr(args, "api_password", "") or "")
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
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail or f"{method} {url} failed with HTTP {exc.code}") from exc
    if not payload:
        return None
    return json.loads(payload)


def kill_player_via_test_hook(args: argparse.Namespace, *, name: str, account: str = "") -> Any:
    query: dict[str, Any] = {}
    if name:
        query["player"] = name
    if account:
        query["account"] = account
    return api_json(args, "POST", "/api/dummy/companions/test/kill", query)


def damage_player_via_test_hook(
    args: argparse.Namespace,
    *,
    name: str,
    account: str = "",
    health_percent: float,
) -> Any:
    query: dict[str, Any] = {"healthPercent": health_percent}
    if name:
        query["player"] = name
    if account:
        query["account"] = account
    return api_json(args, "POST", "/api/dummy/companions/test/damage", query)


def schedule_healer_test_damage(
    args: argparse.Namespace,
    *,
    name: str,
    account: str,
    delay: float,
    health_percent: float,
) -> threading.Thread:
    """Lower a live smoke leader's health without killing them so healer
    companions get a deterministic heal opportunity."""

    def _run() -> None:
        try:
            time.sleep(max(0.0, float(delay)))
            result = damage_player_via_test_hook(args, name=name, account=account, health_percent=health_percent)
            print(
                f"healer_test_damage name={name} account={account} healthPercent={health_percent:g} "
                f"result={json.dumps(result, ensure_ascii=False)}"
            )
        except Exception as exc:  # background best-effort; never crash the run
            print(f"healer_test_damage_error name={name} error={exc}")

    thread = threading.Thread(target=_run, name="healer-test-damage", daemon=True)
    thread.start()
    return thread


def schedule_resurrection_victim_kill(
    args: argparse.Namespace,
    *,
    name: str,
    account: str,
    delay: float,
) -> threading.Thread:
    """Deterministically kill the designated resurrection victim once combat is
    underway. A live boss fight will not reliably kill a specific party member,
    so the smoke triggers a server-side death via the test hook and lets the
    healer resurrect the resolvable corpse."""

    def _run() -> None:
        try:
            time.sleep(max(0.0, float(delay)))
            result = kill_player_via_test_hook(args, name=name, account=account)
            print(f"resurrection_victim_kill name={name} account={account} result={json.dumps(result, ensure_ascii=False)}")
        except Exception as exc:  # background best-effort; never crash the run
            print(f"resurrection_victim_kill_error name={name} error={exc}")

    thread = threading.Thread(target=_run, name="resurrection-victim-kill", daemon=True)
    thread.start()
    return thread


def fetch_state(args: argparse.Namespace, *, account: str = "", name: str = "") -> dict[str, Any] | None:
    query: dict[str, Any] = {}
    if account:
        query["account"] = account
    if name:
        query["name"] = name
    state = api_json(args, "GET", "/api/dummy/combat/usable", query)
    return state if isinstance(state, dict) and isinstance(state.get("player"), dict) else None


def choose_leader_account(args: argparse.Namespace) -> str:
    if args.leader_account:
        return args.leader_account

    rows = ordered_leader_candidate_rows(args, read_accounts(args.leader_candidates_csv))
    candidates = [str(row.get("username") or "").strip() for row in rows if row.get("username")]
    if args.dry_run:
        return candidates[0]

    for account in candidates:
        if fetch_state(args, account=account) is None:
            return account
    raise RuntimeError("no offline leader candidate is available; wait for linkdead release or pass --leader-account")


def choose_joiner_account(args: argparse.Namespace, leader_account: str) -> str:
    if args.joiner_account:
        return args.joiner_account

    rows = ordered_joiner_candidate_rows(args, read_accounts(args.leader_candidates_csv))
    candidates = [str(row.get("username") or "").strip() for row in rows if row.get("username")]
    if args.dry_run:
        return next((account for account in candidates if account != leader_account), "")

    for account in candidates:
        if account == leader_account:
            continue
        if fetch_state(args, account=account) is None:
            return account
    raise RuntimeError("no offline joiner candidate is available; wait for linkdead release or pass --joiner-account")


def companion_accounts_for_realm(path: Path, realm: int) -> list[str]:
    rows = read_accounts(path)
    accounts: list[str] = []
    for row in rows:
        try:
            row_realm = int(row.get("realm") or row.get("Realm") or 0)
        except ValueError:
            row_realm = 0
        if row_realm == realm and row.get("username"):
            accounts.append(str(row["username"]).strip())
    return accounts


def build_db_args(args: argparse.Namespace) -> argparse.Namespace:
    return argparse.Namespace(
        mysql_bin=args.mysql_bin,
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
        dry_run=args.dry_run,
        position_step=args.position_step,
        checkpoint_start_location="route-home",
    )


def smoke_reset_start_point(args: argparse.Namespace) -> growth.RoutePoint:
    location = str(getattr(args, "reset_start_location", "staging") or "staging").strip().lower()
    coordinates = BARFOG_HOME if location == "objective" else BARFOG_STAGING_HOME
    return growth.RoutePoint(50, *coordinates)


def reset_live_accounts(args: argparse.Namespace, leader_account: str, joiner_account: str = "") -> None:
    companion_accounts = companion_accounts_for_realm(args.companion_accounts_csv, 1)
    accounts = [leader_account]
    if joiner_account and joiner_account not in accounts:
        accounts.append(joiner_account)
    accounts += [account for account in companion_accounts if account not in accounts]
    db_args = build_db_args(args)
    realm = growth.REALMS["alb"]
    start_point = smoke_reset_start_point(args)
    growth.reset_growth_characters(db_args, accounts, level=50, realm=realm, party_size=len(accounts), start_point=start_point)


def run_command(command: list[str], *, dry_run: bool) -> int:
    print(growth.command_for_metadata(command))
    if dry_run:
        return 0
    return subprocess.run(command, cwd=ROOT).returncode


def stop_process(process: subprocess.Popen | None, *, timeout: float = 10.0) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=max(0.1, float(timeout)))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)


def equip_live_accounts(args: argparse.Namespace, leader_account: str, run_dir: Path, joiner_account: str = "") -> int:
    db_args = build_db_args(args)
    leader_csv = run_dir / "player-accounts.csv"
    player_rows = [
        {
            "username": leader_account,
            "password": args.password,
            "realm": 1,
            "char_index": args.leader_char_index,
        }
    ]
    if joiner_account:
        player_rows.append(
            {
                "username": joiner_account,
                "password": args.password,
                "realm": 1,
                "char_index": args.joiner_char_index,
            }
        )
    write_accounts(
        leader_csv,
        player_rows,
    )
    rc = run_command(growth.build_level50_party_gear_command(db_args, leader_csv), dry_run=args.dry_run)
    if rc != 0:
        return rc
    return run_command(growth.build_level50_party_gear_command(db_args, args.companion_accounts_csv), dry_run=args.dry_run)


def build_leader_command(
    args: argparse.Namespace,
    leader_account: str,
    leader_name: str,
    case_dir: Path,
) -> list[str]:
    leader_dir = case_dir / "leader"
    leader_dir.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "tools/behavior-dummy-client.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--api-port",
        str(args.api_port),
        "--username",
        leader_account,
        "--password",
        args.password,
        "--realm",
        "1",
        "--char-index",
        str(args.leader_char_index),
        "--concurrency",
        "1",
        "--rounds",
        "1",
        "--hold",
        str(args.leader_hold),
        "--safe-exit-max-seconds",
        str(
            HEALER_RESURRECTION_LEADER_SAFE_EXIT_MAX_SECONDS
            if str(getattr(args, "smoke_profile", "") or "").strip().lower().replace("_", "-") == "healer-resurrection"
            else LEADER_SAFE_EXIT_MAX_SECONDS
        ),
        "--safe-exit-recent-damage-grace",
        "8",
        "--party-size",
        str(effective_party_size(args)),
        "--login-retries",
        str(args.login_retries),
        "--login-retry-delay",
        str(args.login_retry_delay),
        "--ping-interval",
        "5",
        "--hunter",
        "--combat",
        "--party-local-rescue-target",
        "--behavior-profile",
        str(args.leader_behavior_profile),
        "--action-rotation",
        str(args.leader_action_rotation),
        "--realm-strategy",
        "fixed",
        "--player-level",
        "50",
        "--ideal-target-level",
        "48",
        "--min-target-level",
        "46",
        "--max-target-level",
        "50",
        "--max-target-level-delta",
        "2",
        "--max-target-distance",
        "2200",
        "--target-home-max-distance",
        "2800",
        "--combat-home-leash-distance",
        "2800",
        "--target-timeout",
        "65",
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
        "2200",
        "--hunter-target-api-engage-distance",
        "1500",
        "--hunter-target-max-ground-z-delta",
        "220",
        "--hunter-min-time-left-for-new-target",
        "55",
        "--allow-avoid-target-fallback",
        "--combat-usable-api",
        "--combat-usable-api-retries",
        "4",
        "--combat-usable-api-retry-delay",
        "0.4",
        "--combat-interval",
        "1.5",
        "--target-pool",
        "5",
        "--attack-range",
        "350",
        "--combat-direct-move-distance",
        "1500",
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
        "0.2",
        "--movement-speed",
        "191",
        "--movement-update-interval",
        "0.2",
        "--waypoints",
        args.waypoints,
        "--waypoint-mode",
        "loop",
        "--waypoint-continuous-turns",
        "--waypoint-advance-distance",
        "35",
        "--waypoint-stop-distance",
        "12",
        "--required-target-home",
        ",".join(str(part) for part in BARFOG_HOME),
        "--required-target-home-stop-distance",
        "900",
        "--required-target-home-hunt-distance",
        "2800",
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
        "--auto-loot",
        "--auto-release-on-death",
        "--death-release-delay",
        "2",
        "--death-recovery-cooldown",
        "8",
        "--post-release-rest",
        "3",
        "--low-health-rest-percent",
        "70",
        "--low-health-rest-resume-percent",
        "88",
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
        "220",
        "--flee-use-sprint",
        "--flee-home",
        ALBION_SAFE_FLEE_HOME,
        "--flee-home-stop-distance",
        "120",
        "--flee-dynamic-safe-point",
        "--flee-safe-threat-radius",
        "6000",
        "--flee-safe-point-distance",
        "9000",
        "--flee-critical-health-percent",
        "45",
        "--flee-critical-safe-point-distance",
        "14000",
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
        "99",
        "--flee-min-combat-seconds",
        "4",
        "--flee-min-damage-taken",
        "20",
        "--flee-damage-taken-ratio",
        "1.5",
        "--flee-melee-counterattack-health-floor",
        "45",
        "--required-target-tank-commit-health-percent",
        "45",
        "--think-min",
        "0.25",
        "--think-max",
        "0.9",
        "--startup-command",
        "/bind",
        "--startup-command",
        "/sprint",
        "--startup-command",
        f"/say {leader_name} live companion smoke start",
        "--startup-delay",
        str(args.leader_startup_delay),
        "--jitter",
        "0.2",
        "--tick",
        "0.05",
        "--metrics-csv",
        str(leader_dir / f"{leader_account}-metrics.csv"),
        "--combat-csv",
        str(leader_dir / f"{leader_account}-combat.csv"),
        "--report-md",
        str(leader_dir / f"{leader_account}-report.md"),
        "--trace-movement-log",
        str(leader_dir / f"{leader_account}-{{username}}-{{round}}-movement.jsonl"),
        "--encounter-log",
        str(leader_dir / f"{leader_account}-{{username}}-{{round}}-encounters.jsonl"),
        "--encounter-log-interval",
        "2",
        "--ground-z-map",
        "tools/pathing/heightmaps/region001_client_zones.json",
        "--server-correction-smoothing",
        "--startup-train-full-specs",
        "--startup-train-level",
        "50",
        "--nav-api-url",
        args.api_url,
        "--require-target-name",
        args.target_name,
        "--prefer-target-name",
        args.target_name,
        "--target-auto-lowest-visible-level",
        "--allow-preferred-low-con-fallback",
        "--preferred-low-con-min-level",
        "46",
        "--avoid-target-name",
        "gabriel hound,woodeworm,peallaidh,pygmy goblin,archer,footman",
        "--command",
        "",
    ]
    if leader_chat_only_enabled(args):
        command = strip_cli_options(
            command,
            flags=CHAT_ONLY_LEADER_FLAG_OPTIONS,
            options_with_values=CHAT_ONLY_LEADER_VALUE_OPTIONS,
        )
        command.append("--no-auto-loot")
    if str(getattr(args, "smoke_profile", "") or "") == "healer-resurrection":
        command += [
            "--party-min-ready",
            str(HEALER_RESURRECTION_LEADER_PARTY_MIN_READY),
            "--party-ready-max-leader-distance",
            str(HEALER_RESURRECTION_LEADER_PARTY_READY_MAX_DISTANCE),
            "--party-form-up-delay",
            str(HEALER_RESURRECTION_LEADER_PARTY_FORM_UP_DELAY),
            "--party-form-up-timeout",
            str(HEALER_RESURRECTION_LEADER_PARTY_FORM_UP_TIMEOUT),
            "--party-pre-pull-home-stop-distance",
            str(HEALER_RESURRECTION_LEADER_PRE_PULL_HOME_STOP_DISTANCE),
            "--flee-pressure-health-percent",
            str(int(HEALER_RESURRECTION_LEADER_FLEE_PRESSURE_HEALTH_PERCENT)),
            "--flee-health-percent",
            str(int(HEALER_RESURRECTION_LEADER_FLEE_HEALTH_PERCENT)),
        ]
    if leader_live_control_enabled(args):
        command += [
            "--live-control-file",
            str(leader_dir / "leader-control.json"),
            "--live-control-interval",
            "0.5",
        ]
    return command


def build_joiner_command(
    args: argparse.Namespace,
    joiner_account: str,
    joiner_name: str,
    leader_name: str,
    case_dir: Path,
) -> list[str]:
    joiner_dir = case_dir / "joiner"
    joiner_dir.mkdir(parents=True, exist_ok=True)
    joiner_row = resolve_joiner_row(args, joiner_account)
    joiner_role = primary_joiner_role(joiner_row)
    action_rotation = companion_service.role_to_rotation_for_row(joiner_role, joiner_row)
    behavior_profile = joiner_behavior_profile(joiner_role)
    joiner_capabilities = companion_service.companion_row_capabilities(joiner_row)
    return [
        sys.executable,
        "tools/behavior-dummy-client.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--api-port",
        str(args.api_port),
        "--username",
        joiner_account,
        "--password",
        args.password,
        "--realm",
        "1",
        "--char-index",
        str(args.joiner_char_index),
        "--concurrency",
        "1",
        "--rounds",
        "1",
        "--hold",
        str(args.joiner_hold),
        "--safe-exit-max-seconds",
        "20",
        "--party-size",
        str(effective_party_size(args)),
        "--login-retries",
        str(args.login_retries),
        "--login-retry-delay",
        str(args.login_retry_delay),
        "--ping-interval",
        "5",
        "--player-level",
        "50",
        "--behavior-profile",
        behavior_profile,
        "--action-rotation",
        action_rotation,
        "--hunter",
        "--combat",
        "--use-skills",
        "--skill-interval",
        "1.5",
        "--skill-indexes",
        "0,1,2",
        "--skill-type",
        "1",
        "--allow-unvalidated-skills",
        "--move",
        "--follow-nearby-player",
        "--follow-player-name",
        leader_name,
        "--follow-player-required-for-objective-move",
        "--party-external-member-names",
        leader_name,
        "--party-assist-only",
        "--party-use-assist-command",
        "--party-follow-interval",
        "0.6",
        "--party-follow-distance",
        cli_number(args.joiner_party_follow_distance),
        "--party-follow-step",
        "260",
        "--party-assist-interval",
        "0.6",
        "--party-assist-attack-delay",
        cli_number(args.joiner_party_assist_attack_delay),
        "--party-target-loss-grace",
        "12",
        "--party-target-removed-preserve-limit",
        "12",
        "--target-timeout",
        "65",
        "--target-loss-grace",
        "8",
        "--current-target-api-refresh",
        "--combat-usable-api",
        "--combat-usable-api-retries",
        "4",
        "--combat-usable-api-retry-delay",
        "0.4",
        "--reject-target-on-server-los-failure",
        "--server-los-failure-grace",
        "12",

        "--flee-home",
        ALBION_SAFE_FLEE_HOME,
        "--flee-dynamic-safe-point",
        "--flee-safe-api-scout",
        "--flee-pressure-health-percent",
        cli_number(args.joiner_flee_pressure_health_percent, whole=True),
        "--flee-health-percent",
        cli_number(args.joiner_flee_health_percent, whole=True),
        "--smooth-movement",
        "--movement-speed",
        "191",
        "--movement-update-interval",
        "0.2",
        "--move-step",
        "240",
        "--startup-command",
        "/bind",
        "--startup-command",
        "/sprint",
        "--startup-command",
        f"/say {joiner_name} live join smoke start",
        "--startup-delay",
        str(args.joiner_startup_delay),
        "--startup-self-buff-count",
        "2",
        *(["--startup-stealth"] if "stealth" in joiner_capabilities else []),
        *(["--startup-speed-song"] if "speed_song" in joiner_capabilities else []),
        "--startup-train-full-specs",
        "--startup-train-level",
        "50",
        "--live-control-file",
        str(joiner_dir / "joiner-control.json"),
        "--live-control-interval",
        "0.5",
        "--no-auto-loot",
        "--metrics-csv",
        str(joiner_dir / f"{joiner_account}-metrics.csv"),
        "--report-md",
        str(joiner_dir / f"{joiner_account}-report.md"),
        "--encounter-log",
        str(joiner_dir / f"{joiner_account}-{{username}}-{{round}}-encounters.jsonl"),
        "--trace-movement-log",
        str(joiner_dir / f"{joiner_account}-{{username}}-{{round}}-movement.jsonl"),
        "--ground-z-map",
        "tools/pathing/heightmaps/region001_client_zones.json",
        "--server-correction-smoothing",
        "--command",
        "",
    ]
    if str(getattr(args, "smoke_profile", "") or "").strip().lower().replace("_", "-") == "healer-resurrection":
        command += [
            "--low-health-rest-percent",
            "0",
            "--low-health-rest-resume-percent",
            "0",
            "--auto-release-on-death",
            "--death-release-delay",
            str(HEALER_RESURRECTION_REAL_JOIN_JOINER_DEATH_RELEASE_DELAY),
            "--flee-town-health-percent",
            "100",
            "--flee-critical-health-percent",
            "0",
        ]
    return command


def effective_companion_hold(args: argparse.Namespace) -> float:
    return max(
        float(args.companion_hold),
        float(args.leader_hold) + COMPANION_LEADER_EXIT_BUFFER_SECONDS,
    )


def effective_service_max_runtime(args: argparse.Namespace) -> float:
    return max(
        float(args.service_max_runtime),
        float(args.leader_startup_delay) + float(args.leader_hold) + SERVICE_LEADER_EXIT_BUFFER_SECONDS,
    )


def service_wait_timeout(args: argparse.Namespace) -> float:
    return max(effective_service_max_runtime(args) + 20.0, 20.0)


def build_service_command(
    args: argparse.Namespace,
    service_dir: Path,
    accounts_csv: Path | None = None,
) -> list[str]:
    companion_hold = effective_companion_hold(args)
    service_max_runtime = effective_service_max_runtime(args)
    selected_accounts_csv = Path(accounts_csv or args.companion_accounts_csv)
    command = [
        sys.executable,
        "tools/dummy-companion-service.py",
        "--api-url",
        args.api_url,
        "--repo-root",
        str(ROOT),
        "--run-dir",
        str(service_dir),
        "--accounts-csv",
        str(selected_accounts_csv),
        "--hold",
        str(companion_hold),
        "--party-size",
        str(effective_party_size(args)),
        "--poll-interval",
        str(args.service_poll_interval),
        "--attach-timeout",
        str(args.attach_timeout),
        "--combat-home-leash-distance",
        str(args.combat_home_leash_distance),
        "--max-runtime",
        str(service_max_runtime),
    ]
    if getattr(args, "api_password", ""):
        command += ["--api-password", str(args.api_password)]
    if getattr(args, "dialogue_enabled", False):
        command.append("--dialogue-enabled")
    if getattr(args, "ai_gateway_config", ""):
        command += ["--ai-gateway-config", str(args.ai_gateway_config)]
    if getattr(args, "ai_gateway_model_alias", ""):
        command += ["--ai-gateway-model-alias", str(args.ai_gateway_model_alias)]
    if getattr(args, "ai_guide_model_alias", ""):
        command += ["--ai-guide-model-alias", str(args.ai_guide_model_alias)]
    command += [
        "--ai-gateway-timeout",
        str(args.ai_gateway_timeout),
        "--dialogue-min-interval",
        str(args.dialogue_min_interval),
    ]
    if float(getattr(args, "service_healer_boss_ranged_safe_distance", 0.0) or 0.0) > 0.0:
        command += [
            "--healer-boss-ranged-safe-distance",
            str(float(args.service_healer_boss_ranged_safe_distance)),
        ]
    if float(getattr(args, "service_healer_party_preengage_ranged_safe_distance", 0.0) or 0.0) > 0.0:
        command += [
            "--healer-party-preengage-ranged-safe-distance",
            str(float(args.service_healer_party_preengage_ranged_safe_distance)),
        ]
    if float(getattr(args, "service_healer_boss_non_tank_follow_distance", 0.0) or 0.0) > 0.0:
        command += [
            "--healer-boss-non-tank-follow-distance",
            str(float(args.service_healer_boss_non_tank_follow_distance)),
        ]
    if float(getattr(args, "service_healer_flee_pressure_health_percent", 0.0) or 0.0) > 0.0:
        command += [
            "--healer-flee-pressure-health-percent",
            str(float(args.service_healer_flee_pressure_health_percent)),
        ]
    if float(getattr(args, "service_healer_flee_health_percent", 0.0) or 0.0) > 0.0:
        command += [
            "--healer-flee-health-percent",
            str(float(args.service_healer_flee_health_percent)),
        ]
    if float(getattr(args, "service_flee_pressure_health_percent", 0.0) or 0.0) > 0.0:
        command += [
            "--companion-flee-pressure-health-percent",
            str(float(args.service_flee_pressure_health_percent)),
        ]
    if float(getattr(args, "service_flee_health_percent", 0.0) or 0.0) > 0.0:
        command += [
            "--companion-flee-health-percent",
            str(float(args.service_flee_health_percent)),
        ]
    force_personality_raw = getattr(args, "force_companion_personality", "")
    force_personality = force_personality_raw.strip() if isinstance(force_personality_raw, str) else ""
    if force_personality:
        command += ["--force-companion-personality", force_personality]
    healer_heal_exclude_names = str(getattr(args, "service_healer_heal_exclude_names", "") or "").strip()
    if healer_heal_exclude_names:
        command += ["--healer-heal-exclude-names", healer_heal_exclude_names]
    return command


def request_id_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    request = payload.get("request") or payload.get("Request") or payload
    if not isinstance(request, dict):
        return ""
    return str(request.get("id") or request.get("Id") or "")


def create_companion_request(args: argparse.Namespace, leader_name: str, role: str, source: str) -> str:
    request_point = growth.RoutePoint(50, *BARFOG_HOME) if str(args.target_name or "").strip() else smoke_reset_start_point(args)
    payload = api_json(
        args,
        "POST",
        "/api/dummy/companions/requests",
        {
            "player": leader_name,
            "role": role,
            "source": source,
            "contentType": "pve",
            "objectiveTarget": args.target_name,
            "requestedCapabilities": args.requested_capabilities,
            "region": 1,
            "x": request_point.x,
            "y": request_point.y,
            "z": request_point.z,
            "createdBy": "codex-live-smoke",
        },
    )
    request_id = request_id_from_payload(payload)
    if not request_id:
        raise RuntimeError(f"companion request for role {role} did not return an id: {payload}")
    return request_id


def apply_smoke_profile(args: argparse.Namespace) -> argparse.Namespace:
    profile = str(getattr(args, "smoke_profile", "") or "").strip().lower().replace("_", "-")

    def ensure_role_smoke_companion_death_allowance() -> None:
        if int(getattr(args, "allow_companion_deaths", 0) or 0) < ROLE_SMOKE_ALLOW_COMPANION_DEATHS:
            args.allow_companion_deaths = ROLE_SMOKE_ALLOW_COMPANION_DEATHS

    if profile == "stealth-passive":
        args.target_name = ""
        if not str(getattr(args, "requested_capabilities", "") or "").strip():
            args.requested_capabilities = "stealth"
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["stealth"]
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = STEALTH_PASSIVE_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = STEALTH_PASSIVE_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = STEALTH_PASSIVE_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = STEALTH_PASSIVE_SERVICE_MAX_RUNTIME_SECONDS
        ensure_role_smoke_companion_death_allowance()
        return args

    if profile == "healer-tankleader":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["healer"]
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["heal"]
        if str(getattr(args, "leader_behavior_profile", "") or "") == "party-dps":
            args.leader_behavior_profile = "party-tank"
        if str(getattr(args, "leader_action_rotation", "") or "") == "melee-burst":
            args.leader_action_rotation = "melee-basic"
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = ROLE_SMOKE_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = ROLE_SMOKE_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = ROLE_SMOKE_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = ROLE_SMOKE_SERVICE_MAX_RUNTIME_SECONDS
        return args

    if profile == "healer-forced-heal":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["healer"]
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["heal"]
        if str(getattr(args, "leader_behavior_profile", "") or "") == "party-dps":
            args.leader_behavior_profile = "party-tank"
        if str(getattr(args, "leader_action_rotation", "") or "") == "melee-burst":
            args.leader_action_rotation = "melee-basic"
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = ROLE_SMOKE_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = ROLE_SMOKE_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = ROLE_SMOKE_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = ROLE_SMOKE_SERVICE_MAX_RUNTIME_SECONDS
        if float(getattr(args, "healer_test_damage_delay", 0.0) or 0.0) <= 0.0:
            args.healer_test_damage_delay = 2.0
        if float(getattr(args, "healer_test_damage_percent", 0.0) or 0.0) <= 0.0:
            args.healer_test_damage_percent = 35.0
        return args

    if profile in {"player-chat-only", "player-command-chat", "chat-only"}:
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["tank"]
        args.target_name = ""
        args.reset_start_location = "staging"
        args.leader_chat_only = True
        args.leader_behavior_profile = "custom"
        args.leader_action_rotation = "none"
        if not list(getattr(args, "leader_party_commands", []) or []):
            args.leader_party_commands = list(PLAYER_CHAT_ONLY_DEFAULT_PARTY_COMMANDS)
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["companion_chat_reply"]
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = 40.0
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = 8.0
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = 40.0
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = 70.0
        if float(getattr(args, "leader_party_command_start_delay", 0.0) or 0.0) <= 0.0:
            args.leader_party_command_start_delay = 1.0
        if float(getattr(args, "leader_party_command_gap", 0.0) or 0.0) <= 0.0:
            args.leader_party_command_gap = 1.0
        if float(getattr(args, "leader_control_apply_timeout", 8.0) or 8.0) == 8.0:
            args.leader_control_apply_timeout = PLAYER_COMMAND_DEFAULT_CONTROL_APPLY_TIMEOUT_SECONDS
        return args

    if profile == "player-command-combat":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["healer"]
        args.target_name = "moorlich"
        if not list(getattr(args, "leader_party_commands", []) or []):
            args.leader_party_commands = list(PLAYER_COMMAND_DEFAULT_PARTY_COMMANDS)
        if str(getattr(args, "reset_start_location", "staging") or "staging") == "staging":
            args.reset_start_location = "objective"
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = [
                "companion_chat_reply",
                "companion_command_attack",
                "party_assist",
                "damage_done",
            ]
        if int(getattr(args, "allow_leader_deaths", 0) or 0) == 0:
            args.allow_leader_deaths = 1
        if str(getattr(args, "leader_behavior_profile", "") or "") == "party-dps":
            args.leader_behavior_profile = "party-tank"
        if str(getattr(args, "leader_action_rotation", "") or "") == "melee-burst":
            args.leader_action_rotation = "melee-basic"
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = PLAYER_COMMAND_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = PLAYER_COMMAND_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = PLAYER_COMMAND_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = PLAYER_COMMAND_SERVICE_MAX_RUNTIME_SECONDS
        if float(getattr(args, "leader_party_command_start_delay", 0.0) or 0.0) <= 0.0:
            args.leader_party_command_start_delay = (
                float(args.leader_startup_delay)
                + PLAYER_COMMAND_DEFAULT_COMMAND_START_DELAY_AFTER_STARTUP_SECONDS
            )
        if float(getattr(args, "leader_party_command_gap", 0.0) or 0.0) <= 0.0:
            args.leader_party_command_gap = PLAYER_COMMAND_DEFAULT_COMMAND_GAP_SECONDS
        if (
            float(getattr(args, "leader_control_apply_timeout", 8.0) or 8.0)
            == 8.0
        ):
            args.leader_control_apply_timeout = PLAYER_COMMAND_DEFAULT_CONTROL_APPLY_TIMEOUT_SECONDS
        ensure_role_smoke_companion_death_allowance()
        return args

    if profile == "player-command-modes":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["tank"]
        args.target_name = ""
        if not list(getattr(args, "leader_party_commands", []) or []):
            args.leader_party_commands = list(PLAYER_COMMAND_MODES_DEFAULT_PARTY_COMMANDS)
        if str(getattr(args, "reset_start_location", "staging") or "staging") == "staging":
            args.reset_start_location = "objective"
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = [
                "companion_chat_reply",
                "companion_command_passive",
                "companion_command_defensive",
                "companion_command_stay",
                "companion_command_follow",
                "companion_command_help",
                "companion_command_summon",
                "companion_command_wait",
                "companion_command_clear_target",
            ]
        if int(getattr(args, "allow_leader_deaths", 0) or 0) == 0:
            args.allow_leader_deaths = 1
        if str(getattr(args, "leader_behavior_profile", "") or "") == "party-dps":
            args.leader_behavior_profile = "party-tank"
        if str(getattr(args, "leader_action_rotation", "") or "") == "melee-burst":
            args.leader_action_rotation = "melee-basic"
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = 85.0
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = PLAYER_COMMAND_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = 85.0
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = 115.0
        if float(getattr(args, "leader_party_command_start_delay", 0.0) or 0.0) <= 0.0:
            args.leader_party_command_start_delay = (
                float(args.leader_startup_delay)
                + PLAYER_COMMAND_DEFAULT_COMMAND_START_DELAY_AFTER_STARTUP_SECONDS
            )
        if float(getattr(args, "leader_party_command_gap", 0.0) or 0.0) <= 0.0:
            args.leader_party_command_gap = 4.0
        if float(getattr(args, "leader_control_apply_timeout", 8.0) or 8.0) == 8.0:
            args.leader_control_apply_timeout = PLAYER_COMMAND_DEFAULT_CONTROL_APPLY_TIMEOUT_SECONDS
        ensure_role_smoke_companion_death_allowance()
        return args

    if profile == "player-command-all-roles":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["tank", "healer", "dps", "support"]
        args.target_name = "moorlich"
        if not str(getattr(args, "requested_capabilities", "") or "").strip():
            args.requested_capabilities = "defensive_tank|healer|caster_dps|speed_song"
        if not list(getattr(args, "leader_party_commands", []) or []):
            args.leader_party_commands = list(PLAYER_COMMAND_ALL_ROLES_DEFAULT_PARTY_COMMANDS)
        if str(getattr(args, "reset_start_location", "staging") or "staging") == "staging":
            args.reset_start_location = "objective"
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = [
                "companion_chat_reply",
                "companion_command_attack",
                "companion_command_passive",
                "companion_command_defensive",
                "companion_command_stay",
                "companion_command_follow",
                "companion_command_summon",
                "party_assist",
                "damage_done",
                "heal",
            ]
        if int(getattr(args, "allow_leader_deaths", 0) or 0) == 0:
            args.allow_leader_deaths = 1
        if str(getattr(args, "leader_behavior_profile", "") or "") == "party-dps":
            args.leader_behavior_profile = "party-tank"
        if str(getattr(args, "leader_action_rotation", "") or "") == "melee-burst":
            args.leader_action_rotation = "melee-basic"
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = 130.0
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = PLAYER_COMMAND_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = 130.0
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = 170.0
        if float(getattr(args, "leader_party_command_start_delay", 0.0) or 0.0) <= 0.0:
            args.leader_party_command_start_delay = (
                float(args.leader_startup_delay)
                + PLAYER_COMMAND_DEFAULT_COMMAND_START_DELAY_AFTER_STARTUP_SECONDS
            )
        if float(getattr(args, "leader_party_command_gap", 0.0) or 0.0) <= 0.0:
            args.leader_party_command_gap = 4.0
        if float(getattr(args, "leader_control_apply_timeout", 8.0) or 8.0) == 8.0:
            args.leader_control_apply_timeout = PLAYER_COMMAND_DEFAULT_CONTROL_APPLY_TIMEOUT_SECONDS
        ensure_role_smoke_companion_death_allowance()
        return args

    if profile == "support-speed-song":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["support"]
        args.target_name = ""
        if not str(getattr(args, "requested_capabilities", "") or "").strip():
            args.requested_capabilities = "speed_song"
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["speed_song"]
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = STEALTH_PASSIVE_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = STEALTH_PASSIVE_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = STEALTH_PASSIVE_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = STEALTH_PASSIVE_SERVICE_MAX_RUNTIME_SECONDS
        ensure_role_smoke_companion_death_allowance()
        return args

    if profile == "support-crowd-control":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["support"]
        args.target_name = "moorlich"
        if not str(getattr(args, "requested_capabilities", "") or "").strip():
            args.requested_capabilities = "speed_song"
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["speed_song", "crowd_control"]
        if int(getattr(args, "allow_leader_deaths", 0) or 0) == 0:
            args.allow_leader_deaths = 1
        if str(getattr(args, "leader_behavior_profile", "") or "") == "party-dps":
            args.leader_behavior_profile = "party-tank"
        if str(getattr(args, "leader_action_rotation", "") or "") == "melee-burst":
            args.leader_action_rotation = "melee-basic"
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = ROLE_SMOKE_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = ROLE_SMOKE_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = ROLE_SMOKE_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = ROLE_SMOKE_SERVICE_MAX_RUNTIME_SECONDS
        ensure_role_smoke_companion_death_allowance()
        return args

    if profile == "tank-protection":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["tank"]
        args.target_name = "moorlich"
        if not str(getattr(args, "requested_capabilities", "") or "").strip():
            args.requested_capabilities = "defensive_tank"
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["taunt", "party_protection"]
        if int(getattr(args, "allow_leader_deaths", 0) or 0) == 0:
            args.allow_leader_deaths = 1
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = ROLE_SMOKE_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = ROLE_SMOKE_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = ROLE_SMOKE_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = ROLE_SMOKE_SERVICE_MAX_RUNTIME_SECONDS
        ensure_role_smoke_companion_death_allowance()
        return args

    if profile == "caster-dps":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["dps"]
        args.target_name = "moorlich"
        if not str(getattr(args, "requested_capabilities", "") or "").strip():
            args.requested_capabilities = "caster_dps"
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["damage_done"]
        if str(getattr(args, "leader_behavior_profile", "") or "") == "party-dps":
            args.leader_behavior_profile = "party-tank"
        if str(getattr(args, "leader_action_rotation", "") or "") == "melee-burst":
            args.leader_action_rotation = "melee-basic"
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = CASTER_DPS_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = ROLE_SMOKE_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = CASTER_DPS_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = CASTER_DPS_SERVICE_MAX_RUNTIME_SECONDS
        ensure_role_smoke_companion_death_allowance()
        return args

    if profile == "healer-resurrection":
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["tank", "healer", "dps"]
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["resurrect"]
        if str(getattr(args, "leader_behavior_profile", "") or "") == "party-dps":
            args.leader_behavior_profile = "party-tank"
        if str(getattr(args, "leader_action_rotation", "") or "") == "melee-burst":
            args.leader_action_rotation = "melee-basic"
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = HEALER_RESURRECTION_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = HEALER_RESURRECTION_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = HEALER_RESURRECTION_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = HEALER_RESURRECTION_SERVICE_MAX_RUNTIME_SECONDS
        if float(getattr(args, "service_healer_boss_ranged_safe_distance", 0.0) or 0.0) <= 0.0:
            args.service_healer_boss_ranged_safe_distance = (
                HEALER_RESURRECTION_SERVICE_HEALER_BOSS_RANGED_SAFE_DISTANCE
            )
        if float(getattr(args, "service_healer_party_preengage_ranged_safe_distance", 0.0) or 0.0) <= 0.0:
            args.service_healer_party_preengage_ranged_safe_distance = (
                HEALER_RESURRECTION_SERVICE_HEALER_PARTY_PREENGAGE_RANGED_SAFE_DISTANCE
            )
        if float(getattr(args, "service_healer_boss_non_tank_follow_distance", 0.0) or 0.0) <= 0.0:
            args.service_healer_boss_non_tank_follow_distance = (
                HEALER_RESURRECTION_SERVICE_HEALER_BOSS_NON_TANK_FOLLOW_DISTANCE
            )
        if float(getattr(args, "service_healer_flee_pressure_health_percent", 0.0) or 0.0) <= 0.0:
            args.service_healer_flee_pressure_health_percent = (
                HEALER_RESURRECTION_SERVICE_HEALER_FLEE_PRESSURE_HEALTH_PERCENT
            )
        if float(getattr(args, "service_healer_flee_health_percent", 0.0) or 0.0) <= 0.0:
            args.service_healer_flee_health_percent = HEALER_RESURRECTION_SERVICE_HEALER_FLEE_HEALTH_PERCENT
        if float(getattr(args, "service_flee_pressure_health_percent", 0.0) or 0.0) <= 0.0:
            args.service_flee_pressure_health_percent = HEALER_RESURRECTION_SERVICE_FLEE_PRESSURE_HEALTH_PERCENT
        if float(getattr(args, "service_flee_health_percent", 0.0) or 0.0) <= 0.0:
            args.service_flee_health_percent = HEALER_RESURRECTION_SERVICE_FLEE_HEALTH_PERCENT
        if int(getattr(args, "allow_leader_deaths", 0) or 0) == 0:
            args.allow_leader_deaths = 1
        if int(getattr(args, "allow_companion_deaths", 0) or 0) < HEALER_RESURRECTION_ALLOW_COMPANION_DEATHS:
            args.allow_companion_deaths = HEALER_RESURRECTION_ALLOW_COMPANION_DEATHS
        if getattr(args, "real_player_join", False):
            if int(getattr(args, "allow_joiner_deaths", 0) or 0) == 0:
                args.allow_joiner_deaths = 3
            if float(getattr(args, "joiner_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
                args.joiner_hold = HEALER_RESURRECTION_REAL_JOIN_JOINER_HOLD_SECONDS
            if float(getattr(args, "joiner_party_follow_distance", 600.0)) == 600.0:
                args.joiner_party_follow_distance = HEALER_RESURRECTION_REAL_JOIN_JOINER_FOLLOW_DISTANCE
            if float(getattr(args, "joiner_party_assist_attack_delay", 0.6)) == 0.6:
                args.joiner_party_assist_attack_delay = HEALER_RESURRECTION_REAL_JOIN_JOINER_ASSIST_ATTACK_DELAY
            if float(getattr(args, "joiner_flee_pressure_health_percent", 85.0)) == 85.0:
                args.joiner_flee_pressure_health_percent = (
                    HEALER_RESURRECTION_REAL_JOIN_JOINER_FLEE_PRESSURE_HEALTH_PERCENT
                )
            if float(getattr(args, "joiner_flee_health_percent", 55.0)) == 55.0:
                args.joiner_flee_health_percent = HEALER_RESURRECTION_REAL_JOIN_JOINER_FLEE_HEALTH_PERCENT
            if float(getattr(args, "resurrection_victim_kill_delay", 0.0) or 0.0) <= 0.0:
                args.resurrection_victim_kill_delay = HEALER_RESURRECTION_VICTIM_KILL_DELAY_SECONDS
        return args

    if profile == "mixed-real-join":
        args.real_player_join = True
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = list(DEFAULT_ROLES)
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = ["party_follow", "party_assist"]
        if int(getattr(args, "allow_leader_deaths", 0) or 0) == 0:
            args.allow_leader_deaths = 1
        if int(getattr(args, "allow_joiner_deaths", 0) or 0) == 0:
            args.allow_joiner_deaths = 1
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = MIXED_REAL_JOIN_LEADER_HOLD_SECONDS
        if (
            float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS))
            == DEFAULT_LEADER_STARTUP_DELAY_SECONDS
        ):
            args.leader_startup_delay = MIXED_REAL_JOIN_LEADER_STARTUP_DELAY_SECONDS
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = MIXED_REAL_JOIN_COMPANION_HOLD_SECONDS
        if (
            float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS))
            == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS
        ):
            args.service_max_runtime = MIXED_REAL_JOIN_SERVICE_MAX_RUNTIME_SECONDS
        if float(getattr(args, "joiner_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.joiner_hold = MIXED_REAL_JOIN_JOINER_HOLD_SECONDS
        if float(getattr(args, "release_timeout", 35.0)) == 35.0:
            args.release_timeout = MIXED_REAL_JOIN_RELEASE_TIMEOUT_SECONDS
        if float(getattr(args, "request_active_timeout", 55.0)) == 55.0:
            args.request_active_timeout = MIXED_REAL_JOIN_ACTIVE_TIMEOUT_SECONDS
        ensure_role_smoke_companion_death_allowance()
        return args

    if profile == "dialogue-combat":
        args.dialogue_enabled = True
        args.target_name = "moorlich"
        if list(getattr(args, "roles", []) or []) == list(DEFAULT_ROLES):
            args.roles = ["tank", "healer", "dps"]
        if str(getattr(args, "leader_behavior_profile", "") or "") == "party-dps":
            args.leader_behavior_profile = "party-tank"
        if str(getattr(args, "leader_action_rotation", "") or "") == "melee-burst":
            args.leader_action_rotation = "melee-basic"
        if not list(getattr(args, "expect_companion_actions", []) or []):
            args.expect_companion_actions = [
                "party_follow", "party_assist", "party_protection", "taunt",
                "heal", "damage_done", "dialogue_say", "dialogue_party",
            ]
        if int(getattr(args, "allow_leader_deaths", 0) or 0) == 0:
            args.allow_leader_deaths = 1
        if float(getattr(args, "leader_hold", DEFAULT_LEADER_HOLD_SECONDS)) == DEFAULT_LEADER_HOLD_SECONDS:
            args.leader_hold = 120.0
        if float(getattr(args, "leader_startup_delay", DEFAULT_LEADER_STARTUP_DELAY_SECONDS)) == DEFAULT_LEADER_STARTUP_DELAY_SECONDS:
            args.leader_startup_delay = 40.0
        if float(getattr(args, "companion_hold", DEFAULT_COMPANION_HOLD_SECONDS)) == DEFAULT_COMPANION_HOLD_SECONDS:
            args.companion_hold = 120.0
        if float(getattr(args, "service_max_runtime", DEFAULT_SERVICE_MAX_RUNTIME_SECONDS)) == DEFAULT_SERVICE_MAX_RUNTIME_SECONDS:
            args.service_max_runtime = 160.0
        ensure_role_smoke_companion_death_allowance()
        return args

    return args


def request_status(args: argparse.Namespace, request_id: str) -> dict[str, Any] | None:
    status = api_json(args, "GET", f"/api/dummy/companions/requests/{urllib.parse.quote(request_id)}")
    return status if isinstance(status, dict) else None


def request_status_text(row: dict[str, Any] | None) -> str:
    return str((row or {}).get("status") or (row or {}).get("Status") or "").strip().lower()


def release_completed(statuses: dict[str, str]) -> bool:
    return any(str(status).lower() in {"completed", "leaving"} for status in statuses.values())


def has_companion_activity(summary: dict[str, int]) -> bool:
    return (
        summary["damage_done"] > 0
        or summary["heal"] > 0
        or summary["party_assist"] > 0
        or summary["party_follow"] > 0
        or int(summary.get("companion_chat_reply", 0) or 0) > 0
        or any(
            int(summary.get(key, 0) or 0) > 0
            for key in (
                "companion_command_attack",
                "companion_command_passive",
                "companion_command_defensive",
                "companion_command_stay",
                "companion_command_follow",
                "companion_command_help",
                "companion_command_summon",
                "companion_command_wait",
                "companion_command_clear_target",
            )
        )
    )


def missing_expected_companion_actions(summary: dict[str, int], expected_actions: set[str] | None) -> list[str]:
    return sorted(
        action
        for action in (expected_actions or set())
        if int(summary.get(action, 0) or 0) <= 0
    )


def write_live_control(path: Path, payload: dict[str, Any]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    revision = str(time.time_ns())
    data = {"revision": revision, **payload}
    path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return revision


def wait_for_live_control_applied(log_dir: Path, revision: str, timeout: float) -> bool:
    deadline = time.monotonic() + max(0.0, timeout)
    seen: set[Path] = set()
    while time.monotonic() <= deadline:
        for path in log_dir.rglob("*.jsonl"):
            if path in seen and path.stat().st_size == 0:
                continue
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("event") == "live_control_applied" and str(row.get("revision") or "") == str(revision):
                    return True
            seen.add(path)
        time.sleep(0.2)
    return False


def validate_replace_run_dir(run_dir: Path) -> None:
    allowed_root = (ROOT / "test-output" / "live-companion-selftest").resolve()
    resolved = run_dir.resolve()
    if resolved == allowed_root or allowed_root not in resolved.parents:
        raise ValueError(f"--replace run-dir must be below {allowed_root}")


def wait_for_leader_online(args: argparse.Namespace, leader_account: str) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, args.leader_online_timeout)
    last_state: dict[str, Any] | None = None
    while time.monotonic() <= deadline:
        state = fetch_state(args, account=leader_account)
        if state is not None:
            last_state = state
            player = state.get("player", {})
            if float(player.get("healthPercent") or 0.0) >= args.min_start_health_percent:
                return state
        time.sleep(0.5)
    raise RuntimeError(f"leader did not become healthy online: {last_state}")


def wait_for_player_online(args: argparse.Namespace, account: str, timeout: float, label: str) -> dict[str, Any]:
    deadline = time.monotonic() + max(1.0, timeout)
    last_state: dict[str, Any] | None = None
    while time.monotonic() <= deadline:
        state = fetch_state(args, account=account)
        if state is not None:
            last_state = state
            player = state.get("player", {})
            if player and bool(player.get("isAlive", True)):
                return state
        time.sleep(0.5)
    raise RuntimeError(f"{label} did not become online: {last_state}")


def player_group_member_names(state: dict[str, Any] | None) -> set[str]:
    if not isinstance(state, dict):
        return set()
    names: set[str] = set()
    for member in state.get("groupMembers", []) or []:
        if not isinstance(member, dict):
            continue
        name = str(member.get("name") or member.get("Name") or "").strip()
        if name:
            names.add(name.lower())
    return names


def player_is_grouped_with(args: argparse.Namespace, account: str, member_name: str) -> bool:
    member_key = str(member_name or "").strip().lower()
    if not member_key:
        return False
    return member_key in player_group_member_names(fetch_state(args, account=account))


def wait_for_player_grouped_with(args: argparse.Namespace, account: str, member_name: str, timeout: float) -> bool:
    deadline = time.monotonic() + max(0.0, timeout)
    while time.monotonic() <= deadline:
        if player_is_grouped_with(args, account, member_name):
            return True
        time.sleep(0.5)
    return False


def attempt_real_player_join(
    args: argparse.Namespace,
    *,
    run_dir: Path,
    leader_control_file: Path,
    joiner_control_file: Path,
    joiner_account: str,
    joiner_name: str,
    leader_name: str,
    leader_session_id: int,
) -> bool:
    grouped_with_leader = player_is_grouped_with(args, joiner_account, leader_name)
    for attempt in range(max(1, int(args.joiner_accept_attempts or 1))):
        if grouped_with_leader:
            break

        invite_revision = write_live_control(
            leader_control_file,
            {
                "commands": [f"/invite {joiner_name}"],
                "say": f"inviting {joiner_name}" if attempt == 0 else "",
            },
        )
        if not wait_for_live_control_applied(run_dir / "leader", invite_revision, args.leader_control_apply_timeout):
            time.sleep(max(0.1, args.joiner_invite_delay))

        write_live_control(
            joiner_control_file,
            {
                "accept_group_invite_session_id": leader_session_id,
                "say": f"joining {leader_name}" if attempt == 0 else "",
            },
        )
        grouped_with_leader = wait_for_player_grouped_with(
            args,
            joiner_account,
            leader_name,
            args.joiner_accept_confirm_timeout,
        )
        if not grouped_with_leader:
            time.sleep(max(0.1, args.joiner_invite_delay))

    return grouped_with_leader


def send_leader_party_commands(args: argparse.Namespace, run_dir: Path, leader_control_file: Path) -> list[tuple[str, bool]]:
    commands = leader_party_command_texts(args)
    if not commands:
        return []

    start_delay = max(0.0, float(getattr(args, "leader_party_command_start_delay", 0.0) or 0.0))
    gap = max(0.0, float(getattr(args, "leader_party_command_gap", 0.0) or 0.0))
    if start_delay > 0.0:
        time.sleep(start_delay)

    results: list[tuple[str, bool]] = []
    for index, command_text in enumerate(commands):
        revision = write_live_control(
            leader_control_file,
            {
                "say_text": command_text,
                "say_channel": "party",
            },
        )
        applied = wait_for_live_control_applied(
            run_dir / "leader",
            revision,
            float(getattr(args, "leader_control_apply_timeout", 8.0) or 8.0),
        )
        print(f"leader_party_command={json.dumps(command_text, ensure_ascii=False)} applied={str(applied).lower()}")
        results.append((command_text, applied))
        if not applied:
            raise RuntimeError(f"leader party command live-control was not applied: {command_text}")
        if index + 1 < len(commands) and gap > 0.0:
            time.sleep(gap)
    return results


def wait_for_requests_active(args: argparse.Namespace, request_ids: list[str]) -> dict[str, str]:
    deadline = time.monotonic() + max(1.0, args.request_active_timeout)
    statuses = {request_id: "" for request_id in request_ids}
    while time.monotonic() <= deadline:
        for request_id in request_ids:
            row = request_status(args, request_id)
            if row:
                statuses[request_id] = str(row.get("status") or row.get("Status") or "")
        if statuses and all(status.lower() == "active" for status in statuses.values()):
            return statuses
        time.sleep(1.0)
    return statuses


def wait_for_real_join_release(args: argparse.Namespace, request_ids: list[str]) -> dict[str, str]:
    deadline = time.monotonic() + max(1.0, args.release_timeout)
    statuses = {request_id: "" for request_id in request_ids}
    while time.monotonic() <= deadline:
        for request_id in request_ids:
            row = request_status(args, request_id)
            if row:
                statuses[request_id] = request_status_text(row)
        if release_completed(statuses):
            return statuses
        time.sleep(1.0)
    return statuses


def fail_if_existing_queued_requests(args: argparse.Namespace) -> None:
    if args.allow_existing_queued:
        return
    rows = api_json(args, "GET", "/api/dummy/companions/requests", {"status": "queued", "limit": 20})
    if isinstance(rows, list) and rows:
        ids = ", ".join(str(row.get("id") or row.get("Id") or "") for row in rows)
        raise RuntimeError(f"existing queued companion requests would pollute this smoke: {ids}")


def summarize_encounters(run_dir: Path) -> dict[str, int]:
    counts = {
        "party_follow": 0,
        "party_assist": 0,
        "party_protection": 0,
        "party_external_visible": 0,
        "heal": 0,
        "resurrect": 0,
        "cure": 0,
        "crowd_control": 0,
        "speed_song": 0,
        "stealth": 0,
        "taunt": 0,
        "damage_done": 0,
        "target_rejected": 0,
        "party_member_target_rejected": 0,
        "dialogue_live_control": 0,
        "dialogue_party": 0,
        "dialogue_say": 0,
        "dialogue_heal_priority": 0,
        "dialogue_resurrect_priority": 0,
        "dialogue_cc_add": 0,
        "dialogue_cure_priority": 0,
        "dialogue_live_control_applied": 0,
        "dialogue_live_control_say": 0,
        "companion_chat_reply": 0,
        "companion_command_attack": 0,
        "companion_command_passive": 0,
        "companion_command_defensive": 0,
        "companion_command_stay": 0,
        "companion_command_follow": 0,
        "companion_command_help": 0,
        "companion_command_summon": 0,
        "companion_command_wait": 0,
        "companion_command_clear_target": 0,
        "death": 0,
    }
    death_events = 0
    death_metrics = 0
    for path in run_dir.rglob("*.jsonl"):
        if "service" not in path.parts:
            continue
        has_metrics_in_request_dir = any(path.parent.rglob("*metrics.csv"))
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = str(row.get("event") or "")
            actions = row.get("action_counts") or row.get("actions") or {}
            if not isinstance(actions, dict):
                actions = {}
            for key, value in actions.items():
                try:
                    amount = int(value)
                except (TypeError, ValueError):
                    amount = 1
                key_text = str(key)
                if "party_follow" in key_text or "party_anchor" in key_text:
                    counts["party_follow"] += amount
                if "party_assist" in key_text:
                    counts["party_assist"] += amount
                if "party_external_member_visible" in key_text:
                    counts["party_external_visible"] += amount
                if "heal" in key_text:
                    counts["heal"] += amount
                if key_text.startswith("validated_party_resurrect_") or key_text.startswith("validated_revive_"):
                    counts["resurrect"] += amount
                if "validated_party_cure_" in key_text:
                    counts["cure"] += amount
                if "validated_crowd_control_spell" in key_text:
                    counts["crowd_control"] += amount
                if key_text.startswith("validated_party_") and key_text.endswith("_member") and any(
                    token in key_text for token in ("guard", "protect", "intercept", "bodyguard", "protection")
                ):
                    counts["party_protection"] += amount
                if "speed_song_spell" in key_text:
                    counts["speed_song"] += amount
                if "stealth_spell" in key_text:
                    counts["stealth"] += amount
                if key_text.startswith("validated_taunt_") or key_text == "party_active_tank_reaggro_taunt":
                    counts["taunt"] += amount
                if "combat_damage_done" in key_text:
                    counts["damage_done"] += amount
                if "target_gate_rejected" in key_text or "target_rejected" in key_text:
                    counts["target_rejected"] += amount
                if "live_control_say" in key_text:
                    counts["dialogue_live_control_say"] += amount
                if "companion_chat_reply" in key_text:
                    counts["companion_chat_reply"] += amount
                if "companion_command_attack" in key_text or "companion_command_mode_attack" in key_text:
                    counts["companion_command_attack"] += amount
                if "companion_command_mode_passive" in key_text:
                    counts["companion_command_passive"] += amount
                if "companion_command_mode_defensive" in key_text:
                    counts["companion_command_defensive"] += amount
                if "companion_command_mode_stay" in key_text:
                    counts["companion_command_stay"] += amount
                if "companion_command_mode_follow" in key_text:
                    counts["companion_command_follow"] += amount
                if "companion_command_clear_target" in key_text:
                    counts["companion_command_clear_target"] += amount
            if event == "companion_command_mode_change":
                mode = str(row.get("mode") or "").strip().lower()
                if mode in {"passive", "defensive", "stay", "follow"}:
                    counts[f"companion_command_{mode}"] += 1
            if event == "companion_chat_reply":
                if not has_metrics_in_request_dir:
                    counts["companion_chat_reply"] += 1
                intent = str(row.get("intent") or "").strip().lower()
                if intent == "help":
                    counts["companion_command_help"] += 1
                elif intent == "summon":
                    counts["companion_command_summon"] += 1
                elif intent == "wait":
                    counts["companion_command_wait"] += 1
            if not has_metrics_in_request_dir:
                if event.startswith("companion_command_attack") or event == "companion_command_mode_attack":
                    counts["companion_command_attack"] += 1
                if event == "companion_command_clear_target":
                    counts["companion_command_clear_target"] += 1
                if event == "party_assist":
                    counts["party_assist"] += 1
                if event in {"party_follow", "party_anchor"}:
                    counts["party_follow"] += 1
            if event == "hostile_party_member_target_rejected":
                counts["party_member_target_rejected"] += 1
            if event == "live_control_applied":
                counts["dialogue_live_control_applied"] += 1
            if event == "death_detected":
                death_events += 1
    for path in run_dir.rglob("*metrics.csv"):
        if "service" not in path.parts:
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                row_damage_done = int(float(row.get("damage_done") or 0))
                damage_message_count = 0
                counts["heal"] += int(float(row.get("healing_done") or 0))
                counts["resurrect"] += int(float(row.get("action_party_resurrect") or 0))
                death_metrics += int(float(row.get("action_death_detected") or row.get("death_count") or 0))
                for key, value in row.items():
                    if not key.startswith("action_"):
                        continue
                    try:
                        amount = int(float(value or 0))
                    except ValueError:
                        amount = 0
                    if "party_follow" in key or "party_anchor" in key:
                        counts["party_follow"] += amount
                    if "party_assist" in key:
                        counts["party_assist"] += amount
                    if "party_external_member_visible" in key:
                        counts["party_external_visible"] += amount
                    if key.startswith("action_validated_party_resurrect_") or key.startswith("action_validated_revive_"):
                        counts["resurrect"] += amount
                    if "validated_party_cure_" in key:
                        counts["cure"] += amount
                    if "validated_crowd_control_spell" in key:
                        counts["crowd_control"] += amount
                    if key.startswith("action_validated_party_") and key.endswith("_member") and any(
                        token in key for token in ("guard", "protect", "intercept", "bodyguard", "protection")
                    ):
                        counts["party_protection"] += amount
                    if "speed_song_spell" in key:
                        counts["speed_song"] += amount
                    if "stealth_spell" in key:
                        counts["stealth"] += amount
                    if key.startswith("action_validated_taunt_") or key == "action_party_active_tank_reaggro_taunt":
                        counts["taunt"] += amount
                    if key == "action_combat_damage_msg":
                        damage_message_count += amount
                    if "target_rejected" in key:
                        counts["target_rejected"] += amount
                    if "live_control_say" in key:
                        counts["dialogue_live_control_say"] += amount
                    if "companion_chat_reply" in key:
                        counts["companion_chat_reply"] += amount
                    if "companion_command_attack" in key or "companion_command_mode_attack" in key:
                        counts["companion_command_attack"] += amount
                    if "companion_command_mode_passive" in key:
                        counts["companion_command_passive"] += amount
                    if "companion_command_mode_defensive" in key:
                        counts["companion_command_defensive"] += amount
                    if "companion_command_mode_stay" in key:
                        counts["companion_command_stay"] += amount
                    if "companion_command_mode_follow" in key:
                        counts["companion_command_follow"] += amount
                    if "companion_command_clear_target" in key:
                        counts["companion_command_clear_target"] += amount
                counts["damage_done"] += max(row_damage_done, damage_message_count)
    for path in run_dir.rglob("live-control.json"):
        if "service" not in path.parts:
            continue
        try:
            row = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(row, dict):
            continue
        channel = str(row.get("say_channel") or "").strip().lower()
        hint = str(row.get("intent_hint") or "").strip().lower()
        if channel:
            counts["dialogue_live_control"] += 1
        if channel == "party":
            counts["dialogue_party"] += 1
        if channel == "say":
            counts["dialogue_say"] += 1
        if hint == "heal_priority":
            counts["dialogue_heal_priority"] += 1
        if hint == "resurrect_priority":
            counts["dialogue_resurrect_priority"] += 1
        if hint == "cc_add":
            counts["dialogue_cc_add"] += 1
        if hint == "cure_priority":
            counts["dialogue_cure_priority"] += 1
    counts["death"] = max(death_events, death_metrics)
    return counts


def metrics_errors(run_dir: Path, subdir: str) -> list[str]:
    errors: list[str] = []
    for path in (run_dir / subdir).rglob("*metrics.csv"):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                error = str(row.get("error") or "").strip()
                if error:
                    errors.append(error)
    return errors


def leader_errors(run_dir: Path) -> list[str]:
    return metrics_errors(run_dir, "leader")


def companion_errors(run_dir: Path) -> list[str]:
    return metrics_errors(run_dir, "service")


def missing_companion_metrics(run_dir: Path, request_ids: list[str]) -> list[str]:
    missing: list[str] = []
    for request_id in request_ids:
        request_dir = run_dir / "service" / request_id
        if not request_dir.exists():
            missing.append(f"{request_id}: service log directory missing")
            continue
        if not any(request_dir.rglob("*metrics.csv")):
            if any(path.stat().st_size > 0 for path in request_dir.rglob("*.jsonl")):
                continue
            missing.append(f"{request_id}: companion metrics missing")
    return missing


def joiner_errors(run_dir: Path) -> list[str]:
    return metrics_errors(run_dir, "joiner")


def death_count_in_subdir(run_dir: Path, subdir: str) -> int:
    root = run_dir / subdir
    death_events = 0
    death_metrics = 0
    for path in root.rglob("*.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("event") or "") == "death_detected":
                death_events += 1
    for path in root.rglob("*metrics.csv"):
        with path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                death_metrics += int(float(row.get("action_death_detected") or row.get("death_count") or 0))
    return max(death_events, death_metrics)


def safe_exit_deadline_only(errors: list[str]) -> bool:
    return bool(errors) and set(errors) == {"safe_exit_deadline_reached"}


def smoke_exit_code(
    *,
    active_statuses: dict[str, str],
    release_statuses: dict[str, str],
    summary: dict[str, int],
    leader_errors: list[str],
    joiner_errors: list[str],
    leader_rc: int,
    service_rc: int,
    joiner_rc: int,
    real_player_join: bool,
    dialogue_enabled: bool,
    companion_errors: list[str] | None = None,
    leader_deaths: int = 0,
    joiner_deaths: int = 0,
    expected_actions: set[str] | None = None,
    allowed_companion_deaths: int = 0,
    allowed_leader_deaths: int = 0,
    allowed_joiner_deaths: int = 0,
) -> tuple[int, list[str]]:
    notes: list[str] = []
    if any(status.lower() != "active" for status in active_statuses.values()):
        return 2, notes

    real_join_released = real_player_join and release_completed(release_statuses)

    if dialogue_enabled and summary["dialogue_live_control"] <= 0 and summary["dialogue_live_control_applied"] <= 0:
        return 5, notes
    if dialogue_enabled and summary["dialogue_live_control_applied"] <= 0:
        return 6, notes
    companion_deaths = int(summary.get("death", 0) or 0)
    if companion_deaths > max(0, int(allowed_companion_deaths or 0)):
        notes.append(f"companion_death_detected={companion_deaths}")
        return 8, notes
    if leader_deaths > max(0, int(allowed_leader_deaths or 0)):
        notes.append(f"leader_death_detected={leader_deaths}")
        return 10, notes
    if real_player_join and joiner_deaths > max(0, int(allowed_joiner_deaths or 0)):
        notes.append(f"joiner_death_detected={joiner_deaths}")
        return 11, notes
    if companion_errors:
        notes.append(f"companion_errors={json.dumps(companion_errors, ensure_ascii=False)}")
        return 9, notes
    missing_expected_actions = missing_expected_companion_actions(summary, expected_actions)
    if missing_expected_actions:
        notes.append(f"missing_expected_actions={','.join(missing_expected_actions)}")
        return 12, notes
    if not real_join_released and not has_companion_activity(summary):
        return 3, notes

    if leader_rc != 0 and safe_exit_deadline_only(leader_errors):
        notes.append("leader_safe_exit_warning=safe_exit_deadline_reached")
        leader_rc = 0
    if real_player_join and joiner_rc != 0 and safe_exit_deadline_only(joiner_errors):
        notes.append("joiner_safe_exit_warning=safe_exit_deadline_reached")
        joiner_rc = 0

    notes.append(f"return_codes=leader:{leader_rc},service:{service_rc},joiner:{joiner_rc}")
    return max(leader_rc, service_rc, joiner_rc), notes


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:5000")
    parser.add_argument("--api-timeout", type=float, default=2.0)
    parser.add_argument("--api-password", default=os.environ.get("OPENDAOC_API_PASSWORD", ""))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--leader-candidates-csv", type=Path, default=DEFAULT_LEADER_CANDIDATES)
    parser.add_argument("--leader-account", default="")
    parser.add_argument("--leader-name", default="")
    parser.add_argument("--leader-char-index", type=int, default=0)
    parser.add_argument("--leader-behavior-profile", default="party-dps")
    parser.add_argument("--leader-action-rotation", default="melee-burst")
    parser.add_argument(
        "--leader-party-command",
        dest="leader_party_commands",
        action="append",
        default=[],
        help="repeatable party chat line the dummy leader should send after companions become active, e.g. 명령어 or ㄱㄱ",
    )
    parser.add_argument("--leader-party-command-start-delay", type=float, default=0.0)
    parser.add_argument("--leader-party-command-gap", type=float, default=0.0)
    parser.add_argument("--real-player-join", action="store_true")
    parser.add_argument("--joiner-account", default="")
    parser.add_argument("--joiner-name", default="")
    parser.add_argument("--joiner-char-index", type=int, default=0)
    parser.add_argument("--companion-accounts-csv", type=Path, default=DEFAULT_COMPANION_POOL)
    parser.add_argument("--roles", type=parse_roles, default=list(DEFAULT_ROLES))
    parser.add_argument("--password", default="dummy-pass")
    parser.add_argument("--run-dir", type=Path, default=Path("test-output/live-companion-selftest/player-party-smoke"))
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-reset", action="store_true")
    parser.add_argument("--skip-gear", action="store_true")
    parser.add_argument("--allow-existing-queued", action="store_true")
    parser.add_argument("--smoke-profile", default="standard")
    parser.add_argument("--leader-hold", type=float, default=DEFAULT_LEADER_HOLD_SECONDS)
    parser.add_argument("--leader-startup-delay", type=float, default=DEFAULT_LEADER_STARTUP_DELAY_SECONDS)
    parser.add_argument("--leader-chat-only", action="store_true", help="run the leader as an idle chat driver without hunter/combat")
    parser.add_argument("--leader-online-timeout", type=float, default=35.0)
    parser.add_argument("--joiner-hold", type=float, default=DEFAULT_LEADER_HOLD_SECONDS)
    parser.add_argument("--joiner-startup-delay", type=float, default=1.0)
    parser.add_argument("--joiner-online-timeout", type=float, default=35.0)
    parser.add_argument("--joiner-party-follow-distance", type=float, default=600.0)
    parser.add_argument("--joiner-party-assist-attack-delay", type=float, default=0.6)
    parser.add_argument("--joiner-flee-pressure-health-percent", type=float, default=85.0)
    parser.add_argument("--joiner-flee-health-percent", type=float, default=55.0)
    parser.add_argument("--joiner-invite-delay", type=float, default=2.0)
    parser.add_argument("--joiner-accept-attempts", type=int, default=4)
    parser.add_argument("--joiner-accept-confirm-timeout", type=float, default=3.0)
    parser.add_argument("--leader-control-apply-timeout", type=float, default=8.0)
    parser.add_argument("--release-timeout", type=float, default=35.0)
    parser.add_argument("--min-start-health-percent", type=float, default=90.0)
    parser.add_argument("--request-active-timeout", type=float, default=55.0)
    parser.add_argument("--companion-hold", type=float, default=DEFAULT_COMPANION_HOLD_SECONDS)
    parser.add_argument("--service-max-runtime", type=float, default=DEFAULT_SERVICE_MAX_RUNTIME_SECONDS)
    parser.add_argument("--service-poll-interval", type=float, default=1.0)
    parser.add_argument("--attach-timeout", type=float, default=20.0)
    parser.add_argument("--combat-home-leash-distance", type=float, default=4500.0)
    parser.add_argument("--dialogue-enabled", action="store_true")
    parser.add_argument(
        "--ai-gateway-config",
        default=os.environ.get("OPENDAOC_COMPANION_AI_GATEWAY_CONFIG", os.environ.get("OPENDAOC_AI_GATEWAY_CONFIG", "")),
    )
    parser.add_argument("--ai-gateway-model-alias", default=os.environ.get("OPENDAOC_COMPANION_AI_GATEWAY_MODEL_ALIAS", "small-dialogue"))
    parser.add_argument("--ai-guide-model-alias", default=os.environ.get("OPENDAOC_COMPANION_AI_GUIDE_MODEL_ALIAS", "openai-small-guide"))
    parser.add_argument("--ai-gateway-timeout", type=float, default=5.0)
    parser.add_argument("--dialogue-min-interval", type=float, default=30.0)
    parser.add_argument("--service-healer-boss-ranged-safe-distance", type=float, default=0.0)
    parser.add_argument("--service-healer-party-preengage-ranged-safe-distance", type=float, default=0.0)
    parser.add_argument("--service-healer-boss-non-tank-follow-distance", type=float, default=0.0)
    parser.add_argument("--service-healer-flee-pressure-health-percent", type=float, default=0.0)
    parser.add_argument("--service-healer-flee-health-percent", type=float, default=0.0)
    parser.add_argument("--service-flee-pressure-health-percent", type=float, default=0.0)
    parser.add_argument("--service-flee-health-percent", type=float, default=0.0)
    parser.add_argument("--force-companion-personality", default="")
    parser.add_argument("--target-name", default="moorlich")
    parser.add_argument("--requested-capabilities", default="", help="optional pipe/comma-separated live companion capability filter, e.g. speed_song|stealth")
    parser.add_argument("--allow-companion-deaths", type=int, default=0)
    parser.add_argument("--allow-leader-deaths", type=int, default=0)
    parser.add_argument("--allow-joiner-deaths", type=int, default=0)
    parser.add_argument(
        "--resurrection-victim-kill-delay",
        type=float,
        default=0.0,
        help="healer-resurrection: seconds after the joiner groups before the server test hook kills it so the healer can resurrect; 0 uses the profile default",
    )
    parser.add_argument(
        "--healer-test-damage-delay",
        type=float,
        default=0.0,
        help="healer-forced-heal: seconds after companion requests become active before lowering leader health; 0 uses the profile default",
    )
    parser.add_argument(
        "--healer-test-damage-percent",
        type=float,
        default=0.0,
        help="healer-forced-heal: target leader health percent for the server damage hook; 0 uses the profile default",
    )
    parser.add_argument(
        "--expect-companion-actions",
        type=parse_expected_actions,
        default=[],
        help="optional pipe/comma-separated summary actions that must occur, e.g. heal|speed_song|stealth",
    )
    parser.add_argument("--waypoints", default=BARFOG_WAYPOINTS)
    parser.add_argument("--login-retries", type=int, default=12)
    parser.add_argument("--login-retry-delay", type=float, default=3.0)
    parser.add_argument("--position-step", type=int, default=80)
    parser.add_argument("--reset-start-location", choices=["staging", "objective"], default="staging")
    parser.add_argument("--mysql-bin", default=None)
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-name", default="opendaoc")
    parser.add_argument("--db-user", default="root")
    parser.add_argument("--db-password", default=growth.read_serverconfig_password())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = apply_smoke_profile(build_parser().parse_args(argv))
    args.mysql_bin = growth.resolve_mysql_bin(args.mysql_bin)
    run_dir = args.run_dir
    if args.replace and run_dir.exists() and not args.dry_run:
        validate_replace_run_dir(run_dir)
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    leader_account = choose_leader_account(args)
    leader_name = args.leader_name or character_name_from_account(leader_account)
    joiner_account = choose_joiner_account(args, leader_account) if args.real_player_join else ""
    joiner_name = args.joiner_name or character_name_from_account(joiner_account) if joiner_account else ""
    source = f"codex_live_party_smoke_{leader_account}_{int(time.time())}"
    print(f"leader={leader_account} name={leader_name} source={source}")
    if args.real_player_join:
        print(f"joiner={joiner_account} name={joiner_name}")

    # Healer-resurrection profile: the joiner is the designated resurrection victim.
    # Tell the service's healer companion to never heal the joiner so the boss can
    # land the kill; the joiner stays a resolvable corpse via its 90s release delay.
    if (
        str(getattr(args, "smoke_profile", "") or "").strip().lower().replace("_", "-") == "healer-resurrection"
        and joiner_name
    ):
        args.service_healer_heal_exclude_names = joiner_name

    if not args.skip_reset and not args.dry_run:
        reset_live_accounts(args, leader_account, joiner_account)
    if not args.skip_gear:
        rc = equip_live_accounts(args, leader_account, run_dir, joiner_account)
        if rc != 0:
            return rc

    service_accounts_csv = prepare_service_accounts_csv(args, run_dir, leader_account, joiner_account)
    leader_command = build_leader_command(args, leader_account, leader_name, run_dir)
    joiner_command = build_joiner_command(args, joiner_account, joiner_name, leader_name, run_dir) if args.real_player_join else []
    service_command = build_service_command(args, run_dir / "service", service_accounts_csv)
    if args.dry_run:
        print(growth.command_for_metadata(leader_command))
        if joiner_command:
            print(growth.command_for_metadata(joiner_command))
        print(growth.command_for_metadata(service_command))
        for role in args.roles:
            print(f"POST /api/dummy/companions/requests player={leader_name} role={role} source={source}")
        for command_text in leader_party_command_texts(args):
            print(f"LIVE_CONTROL leader party: {command_text}")
        return 0

    fail_if_existing_queued_requests(args)
    leader_control_file = run_dir / "leader" / "leader-control.json"
    joiner_control_file = run_dir / "joiner" / "joiner-control.json"
    if leader_live_control_enabled(args):
        write_live_control(leader_control_file, {})
    if args.real_player_join:
        write_live_control(joiner_control_file, {})
    leader_process = subprocess.Popen(leader_command, cwd=ROOT)
    service_process: subprocess.Popen | None = None
    joiner_process: subprocess.Popen | None = None
    request_ids: list[str] = []
    statuses: dict[str, str] = {}
    release_statuses: dict[str, str] = {}
    joiner_rc = 0
    try:
        leader_state = wait_for_leader_online(args, leader_account)
        for role in args.roles:
            request_ids.append(create_companion_request(args, leader_name, role, source))

        service_process = subprocess.Popen(service_command, cwd=ROOT)
        statuses = wait_for_requests_active(args, request_ids)
        print(f"requests={statuses}")
        healer_damage_delay = float(getattr(args, "healer_test_damage_delay", 0.0) or 0.0)
        healer_damage_percent = float(getattr(args, "healer_test_damage_percent", 0.0) or 0.0)
        if healer_damage_delay > 0.0 and healer_damage_percent > 0.0:
            schedule_healer_test_damage(
                args,
                name=leader_name,
                account=leader_account,
                delay=healer_damage_delay,
                health_percent=healer_damage_percent,
            )
        send_leader_party_commands(args, run_dir, leader_control_file)

        if args.real_player_join:
            joiner_process = subprocess.Popen(joiner_command, cwd=ROOT)
            wait_for_player_online(args, joiner_account, args.joiner_online_timeout, "joiner")
            latest_leader_state = fetch_state(args, account=leader_account) or leader_state
            leader_player = latest_leader_state.get("player", {}) if isinstance(latest_leader_state, dict) else {}
            leader_session_id = int(leader_player.get("sessionId") or 0)
            if leader_session_id <= 0:
                raise RuntimeError(f"leader session id unavailable for invite: {latest_leader_state}")

            grouped_with_leader = attempt_real_player_join(
                args,
                run_dir=run_dir,
                leader_control_file=leader_control_file,
                joiner_control_file=joiner_control_file,
                joiner_account=joiner_account,
                joiner_name=joiner_name,
                leader_name=leader_name,
                leader_session_id=leader_session_id,
            )
            if not grouped_with_leader:
                raise RuntimeError(f"joiner failed to group with leader after {max(1, int(args.joiner_accept_attempts or 1))} attempts")
            release_statuses = wait_for_real_join_release(args, request_ids)
            print(f"real_join_release={release_statuses}")

            victim_kill_delay = float(getattr(args, "resurrection_victim_kill_delay", 0.0) or 0.0)
            if (
                str(getattr(args, "smoke_profile", "") or "").strip().lower().replace("_", "-")
                == "healer-resurrection"
                and joiner_name
                and victim_kill_delay > 0.0
            ):
                schedule_resurrection_victim_kill(
                    args,
                    name=joiner_name,
                    account=joiner_account,
                    delay=victim_kill_delay,
                )

        if joiner_process is not None:
            joiner_rc = joiner_process.wait(timeout=max(args.joiner_hold + args.joiner_startup_delay + 30.0, 30.0))
        leader_rc = leader_process.wait(timeout=max(args.leader_hold + args.leader_startup_delay + 60.0, 60.0))
        service_rc = service_process.wait(timeout=service_wait_timeout(args))
    finally:
        stop_process(joiner_process)
        stop_process(leader_process)
        stop_process(service_process)

    summary = summarize_encounters(run_dir)
    errors = leader_errors(run_dir)
    companion_error_rows = companion_errors(run_dir)
    companion_error_rows.extend(missing_companion_metrics(run_dir, request_ids))
    joiner_error_rows = joiner_errors(run_dir)
    leader_deaths = death_count_in_subdir(run_dir, "leader")
    joiner_deaths = death_count_in_subdir(run_dir, "joiner") if args.real_player_join else 0
    print(f"summary={json.dumps(summary, ensure_ascii=False, sort_keys=True)}")
    if errors:
        print(f"leader_errors={json.dumps(errors, ensure_ascii=False)}")
    if companion_error_rows:
        print(f"companion_errors={json.dumps(companion_error_rows, ensure_ascii=False)}")
    if joiner_error_rows:
        print(f"joiner_errors={json.dumps(joiner_error_rows, ensure_ascii=False)}")
    exit_code, notes = smoke_exit_code(
        active_statuses=statuses,
        release_statuses=release_statuses,
        summary=summary,
        leader_errors=errors,
        joiner_errors=joiner_error_rows,
        companion_errors=companion_error_rows,
        leader_rc=leader_rc,
        service_rc=service_rc,
        joiner_rc=joiner_rc,
        real_player_join=args.real_player_join,
        dialogue_enabled=args.dialogue_enabled,
        leader_deaths=leader_deaths,
        joiner_deaths=joiner_deaths,
        expected_actions=set(args.expect_companion_actions or []),
        allowed_companion_deaths=args.allow_companion_deaths,
        allowed_leader_deaths=args.allow_leader_deaths,
        allowed_joiner_deaths=args.allow_joiner_deaths,
    )
    for note in notes:
        print(note)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
