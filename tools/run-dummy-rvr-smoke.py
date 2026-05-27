#!/usr/bin/env python3
"""Fast New Frontiers dummy RvR smoke runner."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
FRONTIER_REGION = 163
FRONTIER_PATROL_CENTER = (535000, 535000, 9800)
FRONTIER_MEET_POINTS = {
    "alb": (534700, 535000, 9800),
    "mid": (535300, 535000, 9800),
    "hib": (535000, 535520, 9800),
}


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


growth = load_module(TOOLS / "run-dummy-growth-suite.py", "dummy_growth_suite_for_rvr")
provision = load_module(TOOLS / "provision-dummy-accounts.py", "dummy_provision_for_rvr")


def parse_realm_list(value: str) -> list[str]:
    realms = [part.strip().lower() for part in str(value or "").replace("|", ",").split(",") if part.strip()]
    unknown = [realm for realm in realms if realm not in growth.REALMS]
    if unknown:
        raise argparse.ArgumentTypeError(f"unknown realm(s): {', '.join(unknown)}")
    return realms


def accounts_from_csv(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return [row["username"] for row in csv.DictReader(handle) if row.get("username")]


def run_command(command: list[str], *, dry_run: bool) -> int:
    print(growth.command_for_metadata(command))
    if dry_run:
        return 0
    return subprocess.run(command).returncode


def rvr_waypoints(x: int, y: int, z: int) -> str:
    center_x, center_y, center_z = FRONTIER_PATROL_CENTER
    points = [
        (x, y, z),
        (center_x, center_y, center_z),
        (center_x + 450, center_y + 160, center_z),
        (center_x, center_y - 420, center_z),
        (center_x - 420, center_y + 120, center_z),
    ]
    return "|".join(f"{px},{py},{pz}" for px, py, pz in points)


def build_behavior_command(
    args: argparse.Namespace,
    realm_key: str,
    accounts_csv: Path,
    case_dir: Path,
    party_size: int,
) -> list[str]:
    base_x, base_y, base_z = FRONTIER_MEET_POINTS[realm_key]
    metrics_csv = case_dir / "metrics.csv"
    combat_csv = case_dir / "combat.csv"
    report_md = case_dir / "report.md"
    trace_pattern = case_dir / "movement" / "{username}-{round}.jsonl"
    encounter_pattern = case_dir / "encounters" / "{username}-{round}.jsonl"
    trace_pattern.parent.mkdir(parents=True, exist_ok=True)
    encounter_pattern.parent.mkdir(parents=True, exist_ok=True)

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
        str(args.hold),
        "--ramp-up",
        str(args.ramp_up),
        "--party-size",
        str(party_size),
        "--login-retries",
        str(args.login_retries),
        "--login-retry-delay",
        str(args.login_retry_delay),
        "--realm-strategy",
        "fixed",
        "--player-level",
        "50",
        "--hunter",
        "--rvr-enemy-player-hunter",
        "--rvr-enemy-player-max-distance",
        str(args.enemy_player_max_distance),
        "--combat",
        "--move",
        "--smooth-movement",
        "--smooth-move-interval",
        "0.12",
        "--movement-update-interval",
        "0.12",
        "--movement-speed",
        "260",
        "--move-step",
        "320",
        "--waypoints",
        rvr_waypoints(base_x, base_y, base_z),
        "--waypoint-mode",
        "loop",
        "--waypoint-interval",
        "0.2",
        "--waypoint-advance-distance",
        "40",
        "--attack-range",
        "350",
        "--combat-direct-move-distance",
        "2600",
        "--melee-stick-attack",
        "--melee-stick-attack-distance",
        "1800",
        "--attack-target-in-view-prime-delay",
        "0.5",
        "--melee-range-buffer",
        "300",
        "--minimum-melee-stop-distance",
        "60",
        "--target-timeout",
        "45",
        "--target-loss-grace",
        "8",
        "--use-skills",
        "--combat-usable-api",
        "--combat-usable-api-retries",
        "4",
        "--combat-usable-api-retry-delay",
        "0.4",
        "--api-port",
        str(args.api_port),
        "--behavior-profile",
        "party-dps" if party_size > 1 else "solo-melee",
        "--action-rotation",
        "auto",
        "--party-role-strategy",
        "mixed" if party_size > 1 else "same",
        "--party-invite-interval",
        "4",
        "--party-accept-interval",
        "2",
        "--party-assist-interval",
        "0.5",
        "--party-assist-attack-delay",
        "0.4",
        "--party-follow-interval",
        "0.2",
        "--party-follow-step",
        "320",
        "--party-follow-distance",
        "500",
        "--party-use-assist-command",
        "--auto-release-on-death",
        "--death-release-delay",
        "2",
        "--death-recovery-cooldown",
        "6",
        "--startup-command",
        "/sprint",
        "--greet-nearby-player",
        "--player-greet-chance",
        "0.05",
        "--speak-state-changes",
        "--state-speech-min-interval",
        "3",
        "--trace-observed-player-positions",
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
        "1",
        "--tick",
        "0.05",
        "--jitter",
        "0.1",
        "--command",
        "",
    ]
    if party_size > 1:
        command += [
            "--party-assist-only",
            "--party-min-ready",
            str(party_size),
            "--party-form-up-delay",
            "3",
            "--party-ready-max-leader-distance",
            "2200",
        ]
    return command


def summarize_case(case_dir: Path) -> dict[str, int]:
    counts = {
        "enemy_target_committed": 0,
        "enemy_player_visible": 0,
        "attack_on": 0,
        "damage_done": 0,
        "incoming_counterattack": 0,
        "api_attacker_miss": 0,
        "skills": 0,
        "friendly_rejections": 0,
        "party_member_target_rejections": 0,
    }
    for path in (case_dir / "encounters").glob("*.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = str(row.get("event", "") or "")
            actions = row.get("action_counts", {}) or row.get("actions", {}) or {}
            if not isinstance(actions, dict):
                actions = {}
            if event == "rvr_enemy_player_target_committed":
                counts["enemy_target_committed"] += 1
            if event == "incoming_damage_player_counterattack":
                counts["incoming_counterattack"] += 1
            if event == "rvr_enemy_player_api_attacker_miss":
                counts["api_attacker_miss"] += 1
            if actions.get("rvr_enemy_player_visible"):
                counts["enemy_player_visible"] += int(actions.get("rvr_enemy_player_visible") or 0)
            if actions.get("attack_on"):
                counts["attack_on"] += int(actions.get("attack_on") or 0)
            if actions.get("combat_damage_done"):
                counts["damage_done"] += int(actions.get("combat_damage_done") or 0)
            if actions.get("incoming_damage_player_counterattack"):
                counts["incoming_counterattack"] += int(actions.get("incoming_damage_player_counterattack") or 0)
            if actions.get("rvr_enemy_player_api_attacker_miss"):
                counts["api_attacker_miss"] += int(actions.get("rvr_enemy_player_api_attacker_miss") or 0)
            if str(row.get("current_target_intent", "") or "") == "enemy_player" and row.get("target_visible"):
                counts["enemy_player_visible"] += 1
            counts["attack_on"] = max(counts["attack_on"], int(row.get("attack_on_count", 0) or 0))
            counts["skills"] = max(counts["skills"], int(row.get("skills_count", 0) or 0))
            counts["damage_done"] = max(counts["damage_done"], int(row.get("damage_done", 0) or 0))
            if event == "friendly_target_feedback":
                counts["friendly_rejections"] += 1
            if event == "hostile_party_member_target_rejected":
                counts["party_member_target_rejections"] += 1
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=growth.DEFAULT_DUMMY_HOST)
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--realms", type=parse_realm_list, default=parse_realm_list("alb,mid,hib"))
    parser.add_argument("--party-size", type=int, default=2)
    parser.add_argument("--start", type=int, default=9000)
    parser.add_argument("--hold", type=float, default=90.0)
    parser.add_argument("--ramp-up", type=float, default=2.0)
    parser.add_argument("--process-stagger", type=float, default=2.0)
    parser.add_argument("--enemy-player-max-distance", type=float, default=3600.0)
    parser.add_argument("--run-dir", type=Path, default=Path("tools/test-output/rvr-smoke"))
    parser.add_argument("--replace", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-provision", action="store_true")
    parser.add_argument("--skip-gear", action="store_true")
    parser.add_argument("--login-retries", type=int, default=6)
    parser.add_argument("--login-retry-delay", type=float, default=1.0)
    parser.add_argument("--mysql-bin", default=None)
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-name", default="opendaoc")
    parser.add_argument("--db-user", default="root")
    parser.add_argument("--db-password", default=provision.read_serverconfig_password())
    parser.add_argument("--template-account", default="bigjuh")
    parser.add_argument("--template-character", default="Caraenry")
    parser.add_argument("--password", default="dummy-pass")
    parser.add_argument("--position-step", type=int, default=180)
    parser.add_argument("--ground-z-offset", type=int, default=0)
    parser.add_argument("--no-starter-equipment", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.mysql_bin = provision.resolve_mysql_bin(args.mysql_bin)
    args.provision_target_classes = True
    args.level50_party_gear = not args.skip_gear

    run_dir = args.run_dir
    if args.replace and run_dir.exists() and not args.dry_run:
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    commands: list[list[str]] = []
    for realm_offset, realm_key in enumerate(args.realms):
        realm = growth.REALMS[realm_key]
        accounts_csv = run_dir / f"{realm_key}-accounts.csv"
        count = max(1, int(args.party_size))
        start = int(args.start) + realm_offset * 100
        if not args.skip_provision:
            provision_command = growth.build_provision_command(args, realm, accounts_csv, count, start, count)
            rc = run_command(provision_command, dry_run=args.dry_run)
            if rc != 0:
                return rc
        elif not accounts_csv.exists():
            raise FileNotFoundError(f"--skip-provision needs existing accounts csv: {accounts_csv}")

        accounts = (
            [f"{realm.prefix}{start + index:03d}" for index in range(count)]
            if args.dry_run and not accounts_csv.exists()
            else accounts_from_csv(accounts_csv)
        )
        frontier_realm = replace(realm, region=FRONTIER_REGION)
        start_point = growth.RoutePoint(50, *FRONTIER_MEET_POINTS[realm_key])
        if not args.dry_run:
            growth.reset_growth_characters(
                args,
                accounts,
                level=50,
                realm=frontier_realm,
                party_size=count,
                start_point=start_point,
            )
        if count >= 2 and not args.skip_gear:
            rc = run_command(growth.build_level50_party_gear_command(args, accounts_csv), dry_run=args.dry_run)
            if rc != 0:
                return rc

        case_dir = run_dir / realm_key
        case_dir.mkdir(parents=True, exist_ok=True)
        commands.append(build_behavior_command(args, realm_key, accounts_csv, case_dir, count))

    if args.dry_run:
        for command in commands:
            print(growth.command_for_metadata(command))
        return 0

    processes = []
    for command in commands:
        processes.append(subprocess.Popen(command))
        if len(processes) < len(commands):
            time.sleep(max(0.0, float(args.process_stagger or 0.0)))
    return_code = 0
    for process in processes:
        return_code = max(return_code, process.wait())
    if return_code != 0:
        return return_code

    aggregate = {
        "enemy_target_committed": 0,
        "enemy_player_visible": 0,
        "attack_on": 0,
        "damage_done": 0,
        "incoming_counterattack": 0,
        "api_attacker_miss": 0,
        "skills": 0,
        "friendly_rejections": 0,
        "party_member_target_rejections": 0,
    }
    for realm_key in args.realms:
        summary = summarize_case(run_dir / realm_key)
        print(f"{realm_key}: {summary}")
        for key, value in summary.items():
            aggregate[key] += value
    print(f"aggregate: {aggregate}")

    if aggregate["enemy_target_committed"] <= 0 or (aggregate["attack_on"] <= 0 and aggregate["damage_done"] <= 0):
        print("rvr smoke failed: no enemy player target commit or combat damage")
        return 1
    if aggregate["friendly_rejections"] > 0 or aggregate["party_member_target_rejections"] > 0:
        print("rvr smoke failed: friendly/party-member hostile target rejection observed")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
