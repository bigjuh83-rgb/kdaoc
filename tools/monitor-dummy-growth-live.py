#!/usr/bin/env python3
"""Watch a growth case in real time and tune behavior live-control knobs."""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path


DISTANCE_EVENTS = {"hunter_target_scan_empty", "attack_decision"}
BAD_IDLE_REASONS = {"distance", "combat_gap", "idle_ready", "level"}
OBJECTIVE_TRAVEL_STATES = {"TravelToObjective", "ReturnToObjective", "DropAggroAndRecover"}


def jsonl_tail(path: Path, max_lines: int = 80) -> list[dict[str, object]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()[-max_lines:]
    except OSError:
        return []

    rows: list[dict[str, object]] = []
    for line in lines:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def load_control(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def max_numeric(payload: dict[str, object], key: str, fallback: float) -> float:
    try:
        return max(float(payload.get(key, fallback) or fallback), fallback)
    except (TypeError, ValueError):
        return fallback


def write_control(path: Path, payload: dict[str, object], reason: str, *, say: bool = True) -> None:
    payload["revision"] = int(time.time() * 1000)
    if say:
        payload["say"] = f"state: live supervisor adjusted {reason}"
    else:
        payload.pop("say", None)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def recent_case_rows(case_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    paths = sorted((case_dir / "encounters").glob("*.jsonl"), key=lambda item: item.stat().st_mtime, reverse=True)
    if not paths:
        return rows

    newest_prefix = paths[0].name.split("-", 3)[:2]
    for path in paths:
        if path.name.split("-", 3)[:2] != newest_prefix:
            continue
        rows.extend(jsonl_tail(path))
    rows.sort(key=lambda row: float(row.get("elapsed", 0.0) or 0.0))
    return rows


def primary_metrics_complete(case_dir: Path) -> bool:
    for path in sorted(case_dir.glob("segment-*-metrics.csv")):
        if re.fullmatch(r"segment-\d{3}-metrics\.csv", path.name) is None:
            continue
        try:
            lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except OSError:
            continue
        if len(lines) >= 2:
            return True
    return False


def row_reason(row: dict[str, object]) -> str:
    reason = str(row.get("reason", "") or "")
    if reason:
        return reason
    reject_counts = row.get("hunter_reject_counts", {})
    if isinstance(reject_counts, dict):
        candidates = {
            str(key): int(value)
            for key, value in reject_counts.items()
            if key not in {"visible", "eligible"} and isinstance(value, int) and value > 0
        }
        if candidates:
            return max(candidates.items(), key=lambda item: item[1])[0]
    return ""


def has_lower_level_targets(row: dict[str, object]) -> bool:
    try:
        min_level = int(row.get("hunter_min_level", 1) or 1)
    except (TypeError, ValueError):
        return False
    if min_level <= 1:
        return False

    rejected = row.get("hunter_nearest_rejected", [])
    if not isinstance(rejected, list):
        return False
    for item in rejected:
        if not isinstance(item, dict) or item.get("reason") != "level":
            continue
        try:
            level = int(item.get("level", 0) or 0)
        except (TypeError, ValueError):
            continue
        if 0 < level < min_level:
            return True
    return False


def is_objective_travel_row(row: dict[str, object]) -> bool:
    return str(row.get("behavior_state", "") or "") in OBJECTIVE_TRAVEL_STATES


def row_has_active_target(row: dict[str, object]) -> bool:
    for key in ("current_target", "active_target_id", "target_id"):
        try:
            if int(row.get(key, 0) or 0) > 0:
                return True
        except (TypeError, ValueError):
            continue
    return False


def tune_control(case_dir: Path, *, max_engage: float, max_radius: float, step: float) -> tuple[bool, str]:
    control_path = case_dir / "live-control.json"
    payload = load_control(control_path)
    rows = recent_case_rows(case_dir)
    if not rows:
        return False, "no_rows"

    latest = rows[-1]
    latest_event = str(latest.get("event", "") or "")
    latest_reason = row_reason(latest)
    recent_deaths = [row for row in rows[-120:] if row.get("event") == "death_detected"]
    recent_kills = [row for row in rows[-120:] if row.get("event") in {"target_removed", "target_object_removed"}]
    recent_empty = [
        row
        for row in rows[-80:]
        if row.get("event") in DISTANCE_EVENTS and (row_reason(row) in BAD_IDLE_REASONS or row.get("event") == "hunter_target_scan_empty")
    ]

    if recent_deaths and not recent_kills:
        death_count = len(recent_deaths)
        if int(payload.get("death_backoff_death_count", 0) or 0) >= death_count:
            return False, "death_backoff_already_applied"

        changed = int(payload.get("death_backoff_death_count", 0) or 0) != death_count
        desired_values = {
            "target_timeout": 16.0,
            "max_target_level_delta": 0,
            "hunter_target_api_engage_distance": 1500.0,
            "max_target_distance": 1500.0,
            "combat_direct_move_distance": 1500.0,
        }
        for key, desired in desired_values.items():
            if payload.get(key) != desired:
                payload[key] = desired
                changed = True
        payload["death_backoff_death_count"] = death_count
        if changed:
            write_control(control_path, payload, "death_backoff", say=False)
            return True, "death_backoff"
        return False, "death_backoff_capped"

    if latest_event == "live_control_applied":
        return False, "already_applied"

    if row_has_active_target(latest):
        return False, "active_combat"

    if len(recent_empty) >= 2 and is_objective_travel_row(latest):
        return False, "traveling_to_objective"

    recent_lower_level = [row for row in recent_empty if has_lower_level_targets(row)]
    if len(recent_lower_level) >= 2 and not recent_kills:
        old_min = int(max_numeric(payload, "min_target_level", float(latest.get("hunter_min_level", 1) or 1)))
        baseline_min = int(max_numeric(payload, "baseline_min_target_level", float(latest.get("hunter_min_level", 1) or 1)))
        new_min = max(1, baseline_min, old_min - 1)
        if new_min < old_min:
            payload["min_target_level"] = new_min
            write_control(control_path, payload, "lower_min_level")
            return True, "lower_min_level"
        return False, "min_level_capped"

    if len(recent_empty) >= 2:
        old_engage = max_numeric(payload, "hunter_target_api_engage_distance", 1500.0)
        old_max_target = max_numeric(payload, "max_target_distance", 1500.0)
        old_direct = max_numeric(payload, "combat_direct_move_distance", 1500.0)
        old_radius = max_numeric(payload, "hunter_target_api_radius", 2200.0)
        payload["hunter_target_api_engage_distance"] = new_engage = clamp(old_engage + step, 600.0, max_engage)
        payload["max_target_distance"] = new_max_target = clamp(old_max_target + step, 600.0, max_engage)
        payload["combat_direct_move_distance"] = new_direct = clamp(old_direct + step, 600.0, max_engage)
        payload["hunter_target_api_radius"] = new_radius = clamp(old_radius + step * 1.5, 1000.0, max_radius)
        if (new_engage, new_max_target, new_direct, new_radius) == (old_engage, old_max_target, old_direct, old_radius):
            return False, "distance_capped"
        write_control(control_path, payload, latest_reason or "idle")
        return True, latest_reason or "idle"

    return False, "stable"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-dir", required=True, type=Path)
    parser.add_argument("--interval", type=float, default=3.0)
    parser.add_argument("--step", type=float, default=350.0)
    parser.add_argument("--max-engage", type=float, default=2800.0)
    parser.add_argument("--max-radius", type=float, default=5200.0)
    parser.add_argument("--hold", type=float, default=0.0, help="seconds to run; 0 runs until interrupted")
    args = parser.parse_args()

    end_at = time.monotonic() + args.hold if args.hold > 0 else float("inf")
    args.case_dir.mkdir(parents=True, exist_ok=True)
    control_path = args.case_dir / "live-control.json"
    if not control_path.exists():
        control_path.write_text("{}\n", encoding="utf-8")

    while time.monotonic() < end_at:
        if primary_metrics_complete(args.case_dir):
            print(f"{time.strftime('%H:%M:%S')} changed=0 reason=metrics_complete", flush=True)
            return 0
        changed, reason = tune_control(args.case_dir, max_engage=args.max_engage, max_radius=args.max_radius, step=args.step)
        print(f"{time.strftime('%H:%M:%S')} changed={int(changed)} reason={reason}", flush=True)
        time.sleep(max(0.5, args.interval))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
