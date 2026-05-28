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
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DEFAULT_LEADER_CANDIDATES = TOOLS / "dummy-party-albion-pve8.csv"
DEFAULT_COMPANION_POOL = TOOLS / "dummy-live-companions.csv"
BARFOG_HOME = (332701, 669142, 2660)
BARFOG_STAGING_HOME = (343893, 672100, 2659)
BARFOG_WAYPOINTS = "332701,669142,2660|333061,669142,2668|333061,669502,2702|332701,669502,2694"
ALBION_SAFE_FLEE_HOME = "369957,679721,5540"
DEFAULT_ROLES = ["tank", "healer", "dps"]
LEADER_SAFE_EXIT_MAX_SECONDS = 30.0
COMPANION_LEADER_EXIT_BUFFER_SECONDS = 45.0
SERVICE_LEADER_EXIT_BUFFER_SECONDS = 75.0


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


growth = load_module(TOOLS / "run-dummy-growth-suite.py", "dummy_growth_suite_for_live_companion_smoke")


def parse_roles(value: str) -> list[str]:
    roles = [part.strip().lower() for part in str(value or "").replace("|", ",").split(",") if part.strip()]
    return roles or list(DEFAULT_ROLES)


def read_accounts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


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

    rows = read_accounts(args.leader_candidates_csv)
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

    rows = read_accounts(args.leader_candidates_csv)
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


def reset_live_accounts(args: argparse.Namespace, leader_account: str, joiner_account: str = "") -> None:
    companion_accounts = companion_accounts_for_realm(args.companion_accounts_csv, 1)
    accounts = [leader_account]
    if joiner_account and joiner_account not in accounts:
        accounts.append(joiner_account)
    accounts += [account for account in companion_accounts if account not in accounts]
    db_args = build_db_args(args)
    realm = growth.REALMS["alb"]
    start_point = growth.RoutePoint(50, *BARFOG_STAGING_HOME)
    growth.reset_growth_characters(db_args, accounts, level=50, realm=realm, party_size=len(accounts), start_point=start_point)


def run_command(command: list[str], *, dry_run: bool) -> int:
    print(growth.command_for_metadata(command))
    if dry_run:
        return 0
    return subprocess.run(command, cwd=ROOT).returncode


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
        str(LEADER_SAFE_EXIT_MAX_SECONDS),
        "--safe-exit-recent-damage-grace",
        "8",
        "--party-size",
        "1",
        "--login-retries",
        str(args.login_retries),
        "--login-retry-delay",
        str(args.login_retry_delay),
        "--ping-interval",
        "5",
        "--hunter",
        "--combat",
        "--behavior-profile",
        "party-dps",
        "--action-rotation",
        "melee-burst",
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
        "240",
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
        "280",
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
        "--speak-state-changes",
        "--state-speech-min-interval",
        "3.0",
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
    if args.real_player_join:
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
    case_dir: Path,
) -> list[str]:
    joiner_dir = case_dir / "joiner"
    joiner_dir.mkdir(parents=True, exist_ok=True)
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
        "1",
        "--login-retries",
        str(args.login_retries),
        "--login-retry-delay",
        str(args.login_retry_delay),
        "--ping-interval",
        "5",
        "--player-level",
        "50",
        "--move",
        "--smooth-movement",
        "--movement-speed",
        "240",
        "--movement-update-interval",
        "0.2",
        "--move-step",
        "240",
        "--startup-command",
        "/bind",
        "--startup-command",
        f"/say {joiner_name} live join smoke start",
        "--startup-delay",
        str(args.joiner_startup_delay),
        "--live-control-file",
        str(joiner_dir / "joiner-control.json"),
        "--live-control-interval",
        "0.5",
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


def build_service_command(args: argparse.Namespace, service_dir: Path) -> list[str]:
    companion_hold = effective_companion_hold(args)
    service_max_runtime = effective_service_max_runtime(args)
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
        str(args.companion_accounts_csv),
        "--hold",
        str(companion_hold),
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
    command += [
        "--ai-gateway-timeout",
        str(args.ai_gateway_timeout),
        "--dialogue-min-interval",
        str(args.dialogue_min_interval),
    ]
    return command


def request_id_from_payload(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    request = payload.get("request") or payload.get("Request") or payload
    if not isinstance(request, dict):
        return ""
    return str(request.get("id") or request.get("Id") or "")


def create_companion_request(args: argparse.Namespace, leader_name: str, role: str, source: str) -> str:
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
            "x": BARFOG_HOME[0],
            "y": BARFOG_HOME[1],
            "z": BARFOG_HOME[2],
            "createdBy": "codex-live-smoke",
        },
    )
    request_id = request_id_from_payload(payload)
    if not request_id:
        raise RuntimeError(f"companion request for role {role} did not return an id: {payload}")
    return request_id


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
        "party_external_visible": 0,
        "heal": 0,
        "resurrect": 0,
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
        "death": 0,
    }
    death_events = 0
    death_metrics = 0
    for path in run_dir.rglob("*.jsonl"):
        if "service" not in path.parts:
            continue
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
                if "res" in key_text or "revive" in key_text:
                    counts["resurrect"] += amount
                if "combat_damage_done" in key_text:
                    counts["damage_done"] += amount
                if "target_gate_rejected" in key_text or "target_rejected" in key_text:
                    counts["target_rejected"] += amount
                if "live_control_say" in key_text:
                    counts["dialogue_live_control_say"] += amount
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
                counts["damage_done"] += int(float(row.get("damage_done") or 0))
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
                    if "target_rejected" in key:
                        counts["target_rejected"] += amount
                    if "live_control_say" in key:
                        counts["dialogue_live_control_say"] += amount
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
) -> tuple[int, list[str]]:
    notes: list[str] = []
    if any(status.lower() != "active" for status in active_statuses.values()):
        return 2, notes

    real_join_released = real_player_join and release_completed(release_statuses)
    if real_player_join and not real_join_released:
        return 4, notes

    if dialogue_enabled and summary["dialogue_live_control"] <= 0:
        return 5, notes
    if dialogue_enabled and summary["dialogue_live_control_applied"] <= 0:
        return 6, notes
    if int(summary.get("death", 0) or 0) > 0:
        notes.append(f"companion_death_detected={int(summary.get('death', 0) or 0)}")
        return 8, notes
    if leader_deaths > 0:
        notes.append(f"leader_death_detected={leader_deaths}")
        return 10, notes
    if real_player_join and joiner_deaths > 0:
        notes.append(f"joiner_death_detected={joiner_deaths}")
        return 11, notes
    if companion_errors:
        notes.append(f"companion_errors={json.dumps(companion_errors, ensure_ascii=False)}")
        return 9, notes
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
    parser.add_argument("--leader-hold", type=float, default=150.0)
    parser.add_argument("--leader-startup-delay", type=float, default=60.0)
    parser.add_argument("--leader-online-timeout", type=float, default=35.0)
    parser.add_argument("--joiner-hold", type=float, default=70.0)
    parser.add_argument("--joiner-startup-delay", type=float, default=1.0)
    parser.add_argument("--joiner-online-timeout", type=float, default=35.0)
    parser.add_argument("--joiner-invite-delay", type=float, default=2.0)
    parser.add_argument("--joiner-accept-attempts", type=int, default=4)
    parser.add_argument("--joiner-accept-confirm-timeout", type=float, default=3.0)
    parser.add_argument("--leader-control-apply-timeout", type=float, default=8.0)
    parser.add_argument("--release-timeout", type=float, default=35.0)
    parser.add_argument("--min-start-health-percent", type=float, default=90.0)
    parser.add_argument("--request-active-timeout", type=float, default=55.0)
    parser.add_argument("--companion-hold", type=float, default=105.0)
    parser.add_argument("--service-max-runtime", type=float, default=150.0)
    parser.add_argument("--service-poll-interval", type=float, default=1.0)
    parser.add_argument("--attach-timeout", type=float, default=20.0)
    parser.add_argument("--combat-home-leash-distance", type=float, default=4500.0)
    parser.add_argument("--dialogue-enabled", action="store_true")
    parser.add_argument("--ai-gateway-config", default="")
    parser.add_argument("--ai-gateway-model-alias", default="small-dialogue")
    parser.add_argument("--ai-gateway-timeout", type=float, default=5.0)
    parser.add_argument("--dialogue-min-interval", type=float, default=30.0)
    parser.add_argument("--target-name", default="moorlich")
    parser.add_argument("--requested-capabilities", default="", help="optional pipe/comma-separated live companion capability filter, e.g. speed_song|stealth")
    parser.add_argument("--waypoints", default=BARFOG_WAYPOINTS)
    parser.add_argument("--login-retries", type=int, default=12)
    parser.add_argument("--login-retry-delay", type=float, default=3.0)
    parser.add_argument("--position-step", type=int, default=80)
    parser.add_argument("--mysql-bin", default=None)
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-name", default="opendaoc")
    parser.add_argument("--db-user", default="root")
    parser.add_argument("--db-password", default=growth.read_serverconfig_password())
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
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

    if not args.skip_reset and not args.dry_run:
        reset_live_accounts(args, leader_account, joiner_account)
    if not args.skip_gear:
        rc = equip_live_accounts(args, leader_account, run_dir, joiner_account)
        if rc != 0:
            return rc

    leader_command = build_leader_command(args, leader_account, leader_name, run_dir)
    joiner_command = build_joiner_command(args, joiner_account, joiner_name, run_dir) if args.real_player_join else []
    service_command = build_service_command(args, run_dir / "service")
    if args.dry_run:
        print(growth.command_for_metadata(leader_command))
        if joiner_command:
            print(growth.command_for_metadata(joiner_command))
        print(growth.command_for_metadata(service_command))
        for role in args.roles:
            print(f"POST /api/dummy/companions/requests player={leader_name} role={role} source={source}")
        return 0

    fail_if_existing_queued_requests(args)
    leader_control_file = run_dir / "leader" / "leader-control.json"
    joiner_control_file = run_dir / "joiner" / "joiner-control.json"
    if args.real_player_join:
        write_live_control(leader_control_file, {})
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

        if args.real_player_join:
            joiner_process = subprocess.Popen(joiner_command, cwd=ROOT)
            wait_for_player_online(args, joiner_account, args.joiner_online_timeout, "joiner")
            latest_leader_state = fetch_state(args, account=leader_account) or leader_state
            leader_player = latest_leader_state.get("player", {}) if isinstance(latest_leader_state, dict) else {}
            leader_session_id = int(leader_player.get("sessionId") or 0)
            if leader_session_id <= 0:
                raise RuntimeError(f"leader session id unavailable for invite: {latest_leader_state}")

            invite_revision = write_live_control(
                leader_control_file,
                {
                    "commands": [f"/invite {joiner_name}"],
                    "say": f"inviting {joiner_name}",
                },
            )
            if not wait_for_live_control_applied(run_dir / "leader", invite_revision, args.leader_control_apply_timeout):
                time.sleep(max(0.1, args.joiner_invite_delay))
            grouped_with_leader = player_is_grouped_with(args, joiner_account, leader_name)
            for attempt in range(max(1, int(args.joiner_accept_attempts or 1))):
                if grouped_with_leader:
                    break
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
            release_statuses = wait_for_real_join_release(args, request_ids)
            print(f"real_join_release={release_statuses}")

        if joiner_process is not None:
            joiner_rc = joiner_process.wait(timeout=max(args.joiner_hold + args.joiner_startup_delay + 30.0, 30.0))
        leader_rc = leader_process.wait(timeout=max(args.leader_hold + args.leader_startup_delay + 60.0, 60.0))
        service_rc = service_process.wait(timeout=service_wait_timeout(args))
    finally:
        if joiner_process is not None and joiner_process.poll() is None:
            joiner_process.terminate()
            joiner_process.wait(timeout=10)
        if leader_process.poll() is None:
            leader_process.terminate()
            leader_process.wait(timeout=10)
        if service_process is not None and service_process.poll() is None:
            service_process.terminate()
            service_process.wait(timeout=10)

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
    )
    for note in notes:
        print(note)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
