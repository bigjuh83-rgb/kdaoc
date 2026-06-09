#!/usr/bin/env python3
"""Run a movement-only companion command smoke.

This smoke is intentionally separate from combat role smokes.  It drives one
leader with live-control party chat and one companion that listens for movement
commands, then summarizes movement trace and encounter JSONL artifacts.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DEFAULT_WAYPOINTS = "581632,581632,2192|582432,581632,2008|582432,582432,1968|581632,581632,2192"
DEFAULT_GROUND_Z_MAP = "tools/pathing/heightmaps/region001_client_zones.json"
DEFAULT_COMMANDS = ["따라와", "대기", "여기로", "소환"]


def load_analyzer():
    path = TOOLS / "analyze-dummy-movement-traces.py"
    spec = importlib.util.spec_from_file_location("analyze_dummy_movement_traces_for_movement_command_smoke", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


movement_analyzer = load_analyzer()


def cli_number(value: float) -> str:
    number = float(value)
    return str(int(number)) if number.is_integer() else str(number)


def leader_command_payloads(args: argparse.Namespace) -> list[dict[str, str]]:
    commands = [str(command).strip() for command in getattr(args, "commands", []) if str(command).strip()]
    return [
        {
            "revision": f"cmd-{index:03d}",
            "say_text": command,
            "say_channel": "party",
        }
        for index, command in enumerate(commands, 1)
    ]


def build_leader_command(args: argparse.Namespace, run_dir: Path) -> list[str]:
    leader_dir = run_dir / "leader"
    return [
        sys.executable,
        "tools/behavior-dummy-client.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--username",
        args.leader_account,
        "--password",
        args.password,
        "--realm",
        str(args.realm),
        "--char-index",
        "0",
        "--concurrency",
        "1",
        "--rounds",
        "1",
        "--hold",
        str(args.hold),
        "--party-size",
        "2",
        "--move",
        "--waypoints",
        args.waypoints,
        "--waypoint-mode",
        "loop",
        "--waypoint-stop-distance",
        "120",
        "--waypoint-step",
        "240",
        "--smooth-movement",
        "--movement-speed",
        str(args.movement_speed),
        "--movement-update-interval",
        str(args.movement_update_interval),
        "--ground-z-map",
        DEFAULT_GROUND_Z_MAP,
        "--server-correction-smoothing",
        "--startup-command",
        "/sprint",
        "--startup-delay",
        str(args.leader_startup_delay),
        "--live-control-file",
        str(leader_dir / "leader-control.json"),
        "--live-control-interval",
        "0.5",
        "--trace-movement-log",
        str(leader_dir / "leader-{username}-{round}-movement.jsonl"),
        "--encounter-log",
        str(leader_dir / "leader-{username}-{round}-encounters.jsonl"),
        "--report-md",
        str(leader_dir / "leader-report.md"),
        "--command",
        "",
    ]


def build_companion_command(args: argparse.Namespace, run_dir: Path) -> list[str]:
    companion_dir = run_dir / "companion"
    command = [
        sys.executable,
        "tools/behavior-dummy-client.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--username",
        args.companion_account,
        "--password",
        args.password,
        "--realm",
        str(args.realm),
        "--char-index",
        "0",
        "--concurrency",
        "1",
        "--rounds",
        "1",
        "--hold",
        str(args.hold),
        "--party-size",
        "2",
        "--move",
        "--follow-nearby-player",
        "--follow-player-name",
        args.leader_name,
        "--follow-player-required-for-objective-move",
        "--party-external-member-names",
        args.leader_name,
        "--party-follow-interval",
        "0.6",
        "--party-follow-distance",
        cli_number(args.party_follow_distance),
        "--party-follow-step",
        "260",
        "--party-follow-catchup-distance",
        cli_number(args.party_follow_catchup_distance),
        "--party-follow-catchup-speed-multiplier",
        "1.4",
        "--party-follow-hard-catchup-distance",
        cli_number(args.party_follow_hard_catchup_distance),
        "--party-follow-hard-catchup-speed-multiplier",
        "1.8",
        "--party-follow-teleport-distance",
        cli_number(args.party_follow_teleport_distance),
        "--party-follow-teleport-stop-distance",
        cli_number(args.party_follow_teleport_stop_distance),
        "--companion-chat-reply",
        "--companion-chat-reply-channel",
        "party",
        "--companion-chat-reply-cooldown",
        "1.0",
        "--live-companion-role",
        "dps",
        "--smooth-movement",
        "--movement-speed",
        str(args.movement_speed),
        "--movement-update-interval",
        str(args.movement_update_interval),
        "--ground-z-map",
        DEFAULT_GROUND_Z_MAP,
        "--server-correction-smoothing",
        "--trace-movement-log",
        str(companion_dir / "companion-{username}-{round}-movement.jsonl"),
        "--encounter-log",
        str(companion_dir / "companion-{username}-{round}-encounters.jsonl"),
        "--report-md",
        str(companion_dir / "companion-report.md"),
        "--command",
        "",
    ]
    if bool(getattr(args, "trace_observed_player_positions", False)):
        command.append("--trace-observed-player-positions")
    return command


def write_live_control_payload(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def iter_jsonl(run_dir: Path) -> Iterable[dict[str, Any]]:
    for path in run_dir.rglob("*.jsonl"):
        if "movement" in path.name:
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def summarize_server_movement_audit(
    patterns: Iterable[str | Path],
    *,
    rewind_threshold: float,
    z_threshold: float,
) -> dict[str, Any]:
    paths = movement_analyzer.expand_paths(patterns)
    samples = 0
    rewinds = 0
    z_spikes = 0
    malformed_lines = 0
    horizontal_max = 0.0
    abs_z_max = 0.0
    for path in paths:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    malformed_lines += 1
                    continue
                if str(row.get("event") or "") != "c2s_position":
                    continue
                horizontal = to_float(row.get("horizontalDelta", row.get("horizontal_delta")))
                abs_z = abs(to_float(row.get("deltaZ", row.get("delta_z"))))
                samples += 1
                horizontal_max = max(horizontal_max, horizontal)
                abs_z_max = max(abs_z_max, abs_z)
                if horizontal > rewind_threshold:
                    rewinds += 1
                if abs_z > z_threshold:
                    z_spikes += 1
    return {
        "files": len(paths),
        "samples": samples,
        "malformed_lines": malformed_lines,
        "rewind_threshold": rewind_threshold,
        "z_threshold": z_threshold,
        "rewinds": rewinds,
        "z_spikes": z_spikes,
        "horizontal_max": horizontal_max,
        "abs_z_max": abs_z_max,
    }


def action_keys(row: dict[str, Any]) -> set[str]:
    actions = row.get("action_counts") or row.get("actions") or {}
    if not isinstance(actions, dict):
        return set()
    return {str(key) for key, value in actions.items() if value}


def row_is_combat_context(row: dict[str, Any]) -> bool:
    if str(row.get("event") or "") == "attack_decision":
        return True
    for key in ("current_target", "active_target_id", "leader_target_id"):
        try:
            if int(row.get(key) or 0) > 0:
                return True
        except (TypeError, ValueError):
            pass
    return bool(row.get("leader_engaged"))


def summarize_movement_command_run(
    run_dir: Path,
    *,
    teleport_threshold: float = 800.0,
    z_threshold: float = 250.0,
    repeat_rewind_threshold: int = 3,
) -> dict[str, Any]:
    movement_paths = sorted(run_dir.rglob("*movement*.jsonl"))
    movement = movement_analyzer.analyze_paths(
        movement_paths,
        teleport_threshold=teleport_threshold,
        z_threshold=z_threshold,
    )
    server_audit = summarize_server_movement_audit(
        sorted(run_dir.rglob("movement-audit*.jsonl")),
        rewind_threshold=teleport_threshold,
        z_threshold=z_threshold,
    )
    counts = {
        "companion_command_stay": 0,
        "companion_command_follow": 0,
        "companion_command_summon": 0,
        "stay_follow_actions": 0,
        "combat_catchup_actions": 0,
    }
    mode = "defensive"
    for row in iter_jsonl(run_dir):
        event = str(row.get("event") or "")
        keys = action_keys(row)
        if event == "companion_command_mode_change":
            intent = str(row.get("intent") or "")
            mode = str(row.get("mode") or mode)
            if mode == "stay":
                counts["companion_command_stay"] += 1
            if mode == "follow":
                counts["companion_command_follow"] += 1
            if intent == "summon":
                counts["companion_command_summon"] += 1
        if event == "companion_chat_reply" and str(row.get("intent") or "") == "summon":
            counts["companion_command_summon"] += 1
        if mode == "stay" and any(
            key.startswith("party_follow") or key in {"player_follow", "party_follow_teleport_catchup"}
            for key in keys
        ):
            counts["stay_follow_actions"] += 1
        if row_is_combat_context(row) and any(
            key in {"party_follow_teleport_catchup", "party_follow_speed_catchup"}
            for key in keys
        ):
            counts["combat_catchup_actions"] += 1

    failures: list[str] = []
    if movement["observed_teleports"] > 0:
        failures.append("near follow teleport")
    if counts["stay_follow_actions"] > 0:
        failures.append("stay mode following")
    if counts["combat_catchup_actions"] > 0:
        failures.append("combat catchup or teleport")
    if movement["self_snaps"] + server_audit["rewinds"] >= repeat_rewind_threshold:
        failures.append("large repeated rewind")
    if movement["observed_z_spikes"] > 0 or movement["self_abs_z_max"] > z_threshold or server_audit["z_spikes"] > 0:
        failures.append("excessive Z mismatch")
    if counts["companion_command_follow"] <= 0:
        failures.append("missing follow command")
    if counts["companion_command_stay"] <= 0:
        failures.append("missing stay command")
    if counts["companion_command_summon"] <= 0:
        failures.append("missing summon command")

    return {
        "ok": not failures,
        "failures": failures,
        "counts": counts,
        "movement": movement,
        "server_audit": server_audit,
    }


def write_summary(run_dir: Path, summary: dict[str, Any]) -> None:
    (run_dir / "movement-command-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    lines = [
        "# Movement Command Smoke Summary",
        "",
        f"- OK: `{str(summary['ok']).lower()}`",
        f"- Failures: `{', '.join(summary['failures']) if summary['failures'] else 'none'}`",
        f"- Movement files: `{summary['movement']['files']}`",
        f"- Observed teleports: `{summary['movement']['observed_teleports']}`",
        f"- Observed Z spikes: `{summary['movement']['observed_z_spikes']}`",
        f"- Self snaps: `{summary['movement']['self_snaps']}`",
        f"- Server audit files: `{summary['server_audit']['files']}`",
        f"- Server audit rewinds: `{summary['server_audit']['rewinds']}`",
        f"- Server audit Z spikes: `{summary['server_audit']['z_spikes']}`",
        "",
    ]
    for key, value in sorted(summary["counts"].items()):
        lines.append(f"- {key}: `{value}`")
    (run_dir / "movement-command-summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_smoke(args: argparse.Namespace) -> int:
    run_dir = Path(args.run_dir)
    (run_dir / "leader").mkdir(parents=True, exist_ok=True)
    (run_dir / "companion").mkdir(parents=True, exist_ok=True)
    leader_control = run_dir / "leader" / "leader-control.json"

    processes = [
        subprocess.Popen(build_leader_command(args, run_dir), cwd=ROOT),
        subprocess.Popen(build_companion_command(args, run_dir), cwd=ROOT),
    ]
    try:
        time.sleep(max(0.0, float(args.command_start_delay)))
        for payload in leader_command_payloads(args):
            write_live_control_payload(leader_control, payload)
            time.sleep(max(0.5, float(args.command_gap)))
        time.sleep(max(0.0, float(args.post_command_hold)))
        write_live_control_payload(
            leader_control,
            {"revision": "quit-leader", "command": "/quit", "quit_after_sit_seconds": "1.0"},
        )
        for proc in processes:
            proc.wait(timeout=max(5.0, float(args.shutdown_timeout)))
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    proc.kill()

    summary = summarize_movement_command_run(
        run_dir,
        teleport_threshold=args.teleport_threshold,
        z_threshold=args.z_threshold,
        repeat_rewind_threshold=args.repeat_rewind_threshold,
    )
    write_summary(run_dir, summary)
    return 0 if summary["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default=str(TOOLS / "test-output" / "movement-command-smoke"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--leader-account", default="dummy001")
    parser.add_argument("--leader-name", default="Dummy001")
    parser.add_argument("--companion-account", default="dummy002")
    parser.add_argument("--companion-name", default="Dummy002")
    parser.add_argument("--password", default="dummy-pass")
    parser.add_argument("--realm", type=int, default=1)
    parser.add_argument("--hold", type=float, default=60.0)
    parser.add_argument("--leader-startup-delay", type=float, default=5.0)
    parser.add_argument("--command-start-delay", type=float, default=12.0)
    parser.add_argument("--command-gap", type=float, default=6.0)
    parser.add_argument("--post-command-hold", type=float, default=10.0)
    parser.add_argument("--shutdown-timeout", type=float, default=20.0)
    parser.add_argument("--movement-speed", type=float, default=191.0)
    parser.add_argument("--movement-update-interval", type=float, default=0.2)
    parser.add_argument("--party-follow-distance", type=float, default=450.0)
    parser.add_argument("--party-follow-catchup-distance", type=float, default=900.0)
    parser.add_argument("--party-follow-hard-catchup-distance", type=float, default=1600.0)
    parser.add_argument("--party-follow-teleport-distance", type=float, default=2500.0)
    parser.add_argument("--party-follow-teleport-stop-distance", type=float, default=120.0)
    parser.add_argument("--waypoints", default=DEFAULT_WAYPOINTS)
    parser.add_argument("--command", dest="commands", action="append", default=None)
    parser.add_argument("--trace-observed-player-positions", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--teleport-threshold", type=float, default=800.0)
    parser.add_argument("--z-threshold", type=float, default=250.0)
    parser.add_argument("--repeat-rewind-threshold", type=int, default=3)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.commands is None:
        args.commands = list(DEFAULT_COMMANDS)
    return run_smoke(args)


if __name__ == "__main__":
    raise SystemExit(main())
