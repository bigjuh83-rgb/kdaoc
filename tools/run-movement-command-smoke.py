#!/usr/bin/env python3
"""Run a movement-only companion command smoke.

This smoke is intentionally separate from combat role smokes.  It drives one
leader with live-control speech and one companion that listens for movement
commands, then summarizes movement trace and encounter JSONL artifacts.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DEFAULT_WAYPOINTS = "581632,581632,2192|582432,581632,2008|582432,582432,1968|581632,581632,2192"
DEFAULT_GROUND_Z_MAP = "tools/pathing/heightmaps/region001_client_zones.json"
DEFAULT_COMMANDS = ["따라와", "대기", "여기로", "소환"]
DEFAULT_AUDIT_LOG_DIR = ROOT / "Debug" / "logs"
DEFAULT_LEADER_START_ANCHOR = "581632,581632,2192"
DEFAULT_COMPANION_START_ANCHOR = "581432,581632,2223"


def character_name_from_account(account: str) -> str:
    text = str(account or "").strip()
    if text.lower().startswith("dummy"):
        return "Dummy" + text[5:]
    return text[:1].upper() + text[1:]


def apply_accounts_csv(args: argparse.Namespace) -> None:
    csv_path = str(getattr(args, "accounts_csv", "") or "").strip()
    if not csv_path:
        return
    path = Path(csv_path)
    if not path.is_absolute():
        path = ROOT / path
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [row for row in csv.DictReader(handle) if str(row.get("username") or "").strip()]
    if len(rows) < 2:
        raise RuntimeError(f"--accounts-csv requires at least two account rows: {path}")
    leader = rows[0]
    companion = rows[1]
    args.leader_account = str(leader.get("username") or "").strip()
    args.companion_account = str(companion.get("username") or "").strip()
    args.leader_name = str(leader.get("name") or leader.get("character") or "").strip() or character_name_from_account(args.leader_account)
    args.companion_name = str(companion.get("name") or companion.get("character") or "").strip() or character_name_from_account(args.companion_account)
    args.leader_password = str(leader.get("password") or getattr(args, "password", "") or "")
    args.companion_password = str(companion.get("password") or getattr(args, "password", "") or "")
    try:
        args.realm = int(leader.get("realm") or args.realm)
    except (TypeError, ValueError):
        pass


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


def append_start_position_args(command: list[str], args: argparse.Namespace, anchor: str) -> None:
    if not bool(getattr(args, "reset_start_position", True)):
        return
    start_anchor = str(anchor or "").strip()
    if not start_anchor:
        return
    command += [
        "--startup-route-home-after-services",
        start_anchor,
        "--startup-route-home-reset-player",
        "--route-home-api-retries",
        str(max(1, int(getattr(args, "start_position_api_retries", 3) or 3))),
        "--route-home-api-retry-delay",
        str(max(0.0, float(getattr(args, "start_position_api_retry_delay", 0.75) or 0.0))),
    ]


def shutdown_wait_timeout(args: argparse.Namespace, process_started_at: float, now: float | None = None) -> float:
    elapsed = max(0.0, float((time.monotonic() if now is None else now) - process_started_at))
    configured = max(5.0, float(getattr(args, "shutdown_timeout", 20.0) or 20.0))
    expected_lifetime = (
        max(0.0, float(getattr(args, "hold", 0.0) or 0.0))
        + max(0.0, float(getattr(args, "leader_startup_delay", 0.0) or 0.0))
        + 10.0
    )
    return max(configured, expected_lifetime - elapsed)


def leader_command_payloads(args: argparse.Namespace) -> list[dict[str, str]]:
    commands = [str(command).strip() for command in getattr(args, "commands", []) if str(command).strip()]
    return [
        {
            "revision": f"cmd-{index:03d}",
            "say_text": command,
            "say_channel": args.command_channel,
        }
        for index, command in enumerate(commands, 1)
    ]


def build_leader_command(args: argparse.Namespace, run_dir: Path) -> list[str]:
    leader_dir = run_dir / "leader"
    command = [
        sys.executable,
        "tools/behavior-dummy-client.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--nav-api-url",
        str(args.api_url),
        "--username",
        args.leader_account,
        "--password",
        args.leader_password,
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
    append_start_position_args(command, args, getattr(args, "leader_start_anchor", DEFAULT_LEADER_START_ANCHOR))
    if bool(getattr(args, "audit", False)):
        command += ["--startup-command", "/movementaudit on {character} full"]
    return command


def build_companion_command(args: argparse.Namespace, run_dir: Path) -> list[str]:
    companion_dir = run_dir / "companion"
    command = [
        sys.executable,
        "tools/behavior-dummy-client.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--nav-api-url",
        str(args.api_url),
        "--username",
        args.companion_account,
        "--password",
        args.companion_password,
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
        "--smooth-movement",
        "--movement-speed",
        str(args.movement_speed),
        "--movement-update-interval",
        str(args.movement_update_interval),
        "--ground-z-map",
        DEFAULT_GROUND_Z_MAP,
        "--server-correction-smoothing",
        "--live-control-file",
        str(companion_dir / "companion-control.json"),
        "--live-control-interval",
        "0.5",
        "--trace-movement-log",
        str(companion_dir / "companion-{username}-{round}-movement.jsonl"),
        "--encounter-log",
        str(companion_dir / "companion-{username}-{round}-encounters.jsonl"),
        "--report-md",
        str(companion_dir / "companion-report.md"),
        "--command",
        "",
    ]
    append_start_position_args(command, args, getattr(args, "companion_start_anchor", DEFAULT_COMPANION_START_ANCHOR))
    if bool(getattr(args, "trace_observed_player_positions", False)):
        command.append("--trace-observed-player-positions")
    if bool(getattr(args, "audit", False)):
        command += ["--startup-command", "/movementaudit on {character} full"]
    return command


def audit_log_path(args: argparse.Namespace, character_name: str) -> Path:
    log_dir = Path(getattr(args, "audit_log_dir", "") or DEFAULT_AUDIT_LOG_DIR)
    if not log_dir.is_absolute():
        log_dir = ROOT / log_dir
    return log_dir / f"movement-audit-{character_name}.jsonl"


def snapshot_audit_offsets(args: argparse.Namespace) -> dict[Path, int]:
    if not bool(getattr(args, "audit", False)):
        return {}
    offsets: dict[Path, int] = {}
    for character_name in (args.leader_name, args.companion_name):
        path = audit_log_path(args, character_name)
        try:
            offsets[path] = path.stat().st_size
        except OSError:
            offsets[path] = 0
    return offsets


def collect_audit_logs(args: argparse.Namespace, run_dir: Path, offsets: dict[Path, int]) -> None:
    if not offsets:
        return
    for source, offset in offsets.items():
        try:
            with source.open("rb") as handle:
                handle.seek(max(0, int(offset)))
                data = handle.read()
        except OSError:
            continue
        if not data.strip():
            continue
        if offset > 0:
            first_newline = data.find(b"\n")
            if first_newline >= 0 and not data.lstrip().startswith(b"{"):
                data = data[first_newline + 1:]
            elif first_newline < 0:
                continue
        target = run_dir / source.name
        target.write_bytes(data)


def write_live_control_payload(path: Path, payload: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def api_json(args: argparse.Namespace, method: str, path: str, query: dict[str, Any] | None = None) -> Any:
    base = str(args.api_url).rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    request_query = {key: value for key, value in (query or {}).items() if value not in (None, "")}
    api_password = str(getattr(args, "api_password", "") or "")
    if api_password and "password" not in request_query:
        request_query["password"] = api_password
    query_string = urllib.parse.urlencode(request_query)
    url = f"{base}{suffix}" + (f"?{query_string}" if query_string else "")
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=float(args.api_timeout)) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail or f"{method} {url} failed with HTTP {exc.code}") from exc
    return json.loads(payload) if payload else None


def fetch_state(args: argparse.Namespace, *, account: str = "", name: str = "") -> dict[str, Any] | None:
    query: dict[str, Any] = {}
    if account:
        query["account"] = account
    if name:
        query["name"] = name
    state = api_json(args, "GET", "/api/dummy/combat/usable", query)
    return state if isinstance(state, dict) and isinstance(state.get("player"), dict) else None


def wait_for_player_online(args: argparse.Namespace, account: str, timeout: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + max(1.0, float(timeout))
    while time.monotonic() <= deadline:
        state = fetch_state(args, account=account)
        if state is not None:
            return state
        time.sleep(0.5)
    return None


def group_member_names(state: dict[str, Any] | None) -> set[str]:
    if not isinstance(state, dict):
        return set()
    names: set[str] = set()
    for member in state.get("groupMembers", []) or []:
        if not isinstance(member, dict):
            continue
        name = str(member.get("name") or member.get("Name") or "").strip().lower()
        if name:
            names.add(name)
    return names


def wait_for_grouped(args: argparse.Namespace, account: str, member_name: str, timeout: float) -> bool:
    member_key = str(member_name or "").strip().lower()
    deadline = time.monotonic() + max(0.0, float(timeout))
    while time.monotonic() <= deadline:
        if member_key in group_member_names(fetch_state(args, account=account)):
            return True
        time.sleep(0.5)
    return False


def wait_for_live_control_applied(log_dir: Path, revision: str, timeout: float) -> bool:
    deadline = time.monotonic() + max(0.0, float(timeout))
    while time.monotonic() <= deadline:
        for path in log_dir.rglob("*.jsonl"):
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
        time.sleep(0.2)
    return False


def group_players_before_commands(args: argparse.Namespace, run_dir: Path) -> list[str]:
    if not bool(getattr(args, "group_before_commands", True)):
        return []
    failures: list[str] = []
    leader_state = wait_for_player_online(args, args.leader_account, args.group_setup_timeout)
    companion_state = wait_for_player_online(args, args.companion_account, args.group_setup_timeout)
    if leader_state is None:
        failures.append("leader not online for group setup")
    if companion_state is None:
        failures.append("companion not online for group setup")
    if failures:
        return failures

    leader_player = leader_state.get("player", {}) if isinstance(leader_state, dict) else {}
    leader_session_id = int(leader_player.get("sessionId") or leader_player.get("SessionId") or 0)
    if leader_session_id <= 0:
        return ["leader session id missing for group setup"]

    leader_control = run_dir / "leader" / "leader-control.json"
    companion_control = run_dir / "companion" / "companion-control.json"
    invite_revision = "group-invite-001"
    write_live_control_payload(
        leader_control,
        {"revision": invite_revision, "commands": [f"/invite {args.companion_name}"]},
    )
    if not wait_for_live_control_applied(run_dir / "leader", invite_revision, args.live_control_apply_timeout):
        failures.append("leader invite live-control not applied")

    accept_revision = "group-accept-001"
    write_live_control_payload(
        companion_control,
        {"revision": accept_revision, "accept_group_invite_session_id": str(leader_session_id)},
    )
    if not wait_for_live_control_applied(run_dir / "companion", accept_revision, args.live_control_apply_timeout):
        failures.append("companion accept live-control not applied")
    if not wait_for_grouped(args, args.companion_account, args.leader_name, args.group_confirm_timeout):
        failures.append("companion not grouped with leader")
    return failures


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
    process_timeouts: list[str] | None = None,
    setup_failures: list[str] | None = None,
) -> dict[str, Any]:
    movement_paths = sorted(path for path in run_dir.rglob("*movement*.jsonl") if not path.name.startswith("movement-audit"))
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
    if process_timeouts:
        failures.append("process shutdown timeout")
    if setup_failures:
        failures.extend(setup_failures)

    return {
        "ok": not failures,
        "failures": failures,
        "process_timeouts": process_timeouts or [],
        "setup_failures": setup_failures or [],
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
        f"- Process shutdown timeouts: `{len(summary.get('process_timeouts', []))}`",
        f"- Setup failures: `{len(summary.get('setup_failures', []))}`",
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
    companion_control = run_dir / "companion" / "companion-control.json"
    audit_offsets = snapshot_audit_offsets(args)

    process_started_at = time.monotonic()
    processes = [
        subprocess.Popen(build_leader_command(args, run_dir), cwd=ROOT),
        subprocess.Popen(build_companion_command(args, run_dir), cwd=ROOT),
    ]
    process_timeouts: list[str] = []
    setup_failures: list[str] = []
    try:
        time.sleep(max(0.0, float(args.command_start_delay)))
        setup_failures = group_players_before_commands(args, run_dir)
        for payload in leader_command_payloads(args):
            write_live_control_payload(leader_control, payload)
            time.sleep(max(0.5, float(args.command_gap)))
        time.sleep(max(0.0, float(args.post_command_hold)))
        write_live_control_payload(
            leader_control,
            {"revision": "quit-leader", "command": "/quit", "quit_after_sit_seconds": "1.0"},
        )
        write_live_control_payload(
            companion_control,
            {"revision": "quit-companion", "command": "/quit", "quit_after_sit_seconds": "1.0"},
        )
        for proc in processes:
            try:
                proc.wait(timeout=shutdown_wait_timeout(args, process_started_at))
            except subprocess.TimeoutExpired:
                process_timeouts.append(" ".join(str(part) for part in proc.args[:3]))
    finally:
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
    collect_audit_logs(args, run_dir, audit_offsets)

    summary = summarize_movement_command_run(
        run_dir,
        teleport_threshold=args.teleport_threshold,
        z_threshold=args.z_threshold,
        repeat_rewind_threshold=args.repeat_rewind_threshold,
        process_timeouts=process_timeouts,
        setup_failures=setup_failures,
    )
    write_summary(run_dir, summary)
    return 0 if summary["ok"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", default=str(TOOLS / "test-output" / "movement-command-smoke"))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-url", default="http://localhost:5000")
    parser.add_argument("--api-timeout", type=float, default=5.0)
    parser.add_argument("--api-password", default="")
    parser.add_argument("--leader-account", default="dummy001")
    parser.add_argument("--leader-name", default="Dummy001")
    parser.add_argument("--companion-account", default="dummy002")
    parser.add_argument("--companion-name", default="Dummy002")
    parser.add_argument("--password", default="dummy-pass")
    parser.add_argument("--accounts-csv", default="")
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
    parser.add_argument("--party-follow-teleport-distance", type=float, default=0.0)
    parser.add_argument("--party-follow-teleport-stop-distance", type=float, default=120.0)
    parser.add_argument("--waypoints", default=DEFAULT_WAYPOINTS)
    parser.add_argument("--reset-start-position", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--leader-start-anchor", default=DEFAULT_LEADER_START_ANCHOR)
    parser.add_argument("--companion-start-anchor", default=DEFAULT_COMPANION_START_ANCHOR)
    parser.add_argument("--start-position-api-retries", type=int, default=3)
    parser.add_argument("--start-position-api-retry-delay", type=float, default=0.75)
    parser.add_argument("--command", dest="commands", action="append", default=None)
    parser.add_argument("--command-channel", choices=["say", "party"], default="party")
    parser.add_argument("--group-before-commands", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--group-setup-timeout", type=float, default=20.0)
    parser.add_argument("--group-confirm-timeout", type=float, default=10.0)
    parser.add_argument("--live-control-apply-timeout", type=float, default=8.0)
    parser.add_argument("--trace-observed-player-positions", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--audit", action="store_true", help="enable /movementaudit on leader and companion and collect new server audit rows")
    parser.add_argument("--audit-log-dir", default=str(DEFAULT_AUDIT_LOG_DIR))
    parser.add_argument("--teleport-threshold", type=float, default=800.0)
    parser.add_argument("--z-threshold", type=float, default=250.0)
    parser.add_argument("--repeat-rewind-threshold", type=int, default=3)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.leader_password = args.password
    args.companion_password = args.password
    apply_accounts_csv(args)
    if args.commands is None:
        args.commands = list(DEFAULT_COMMANDS)
    return run_smoke(args)


if __name__ == "__main__":
    raise SystemExit(main())
