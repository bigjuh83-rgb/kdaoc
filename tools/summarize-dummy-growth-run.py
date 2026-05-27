#!/usr/bin/env python3
"""Summarize dummy growth run outputs without assuming optional CSV columns."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


METRIC_SUM_COLUMNS = (
    "combat_engagements",
    "target_removed",
    "player_deaths",
    "target_timeouts",
    "movement_failures",
    "loot_acquired",
    "damage_done",
    "damage_taken",
)
FLEE_ACTION_COLUMNS = (
    "action_flee_start",
    "action_flee_extend",
    "action_flee_home_overrun",
    "action_flee_rest_pressure",
)


def to_int(value: object) -> int:
    if value is None:
        return 0
    text = str(value).strip()
    if not text or text.upper() == "NULL":
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize_metrics(case_dir: Path) -> dict[str, int]:
    summary = {key: 0 for key in METRIC_SUM_COLUMNS}
    summary["metric_rows"] = 0
    summary["flee_events"] = 0
    for path in sorted(case_dir.glob("segment-*-metrics.csv")):
        if "-watcher-" in path.name:
            continue
        for row in read_csv_rows(path):
            summary["metric_rows"] += 1
            for key in METRIC_SUM_COLUMNS:
                summary[key] += to_int(row.get(key))
            for key in FLEE_ACTION_COLUMNS:
                summary["flee_events"] += to_int(row.get(key))
    return summary


def summarize_watcher(case_dir: Path) -> dict[str, int]:
    summary = {
        "watcher_rows": 0,
        "watcher_xy_warn": 0,
        "watcher_z_warn": 0,
        "watcher_rewind_warn": 0,
        "watcher_behavior_critical": 0,
        "watcher_bad_target_choice": 0,
        "watcher_aggro_not_dropped": 0,
        "watcher_flee_too_short": 0,
        "watcher_target_stuck": 0,
        "watcher_unsafe_rest": 0,
        "watcher_safe_exit_deadline": 0,
        "watcher_post_target_removed_pressure": 0,
    }
    for row in read_csv_rows(case_dir / "watcher-movement-summary.csv"):
        summary["watcher_rows"] += 1
        if str(row.get("xy_status", "")).lower() == "warn":
            summary["watcher_xy_warn"] += 1
        if str(row.get("z_status", "")).lower() == "warn":
            summary["watcher_z_warn"] += 1
        if str(row.get("rewind_status", "")).lower() == "warn":
            summary["watcher_rewind_warn"] += 1
        if str(row.get("primary_behavior_anomaly_status", "")).lower() == "critical":
            summary["watcher_behavior_critical"] += 1
        summary["watcher_bad_target_choice"] += to_int(row.get("primary_behavior_bad_target_choice"))
        summary["watcher_aggro_not_dropped"] += to_int(row.get("primary_behavior_aggro_not_dropped"))
        summary["watcher_flee_too_short"] += to_int(row.get("primary_behavior_flee_too_short"))
        summary["watcher_target_stuck"] += to_int(row.get("primary_behavior_target_stuck"))
        summary["watcher_unsafe_rest"] += to_int(row.get("primary_behavior_unsafe_rest"))
        summary["watcher_safe_exit_deadline"] += to_int(row.get("primary_behavior_safe_exit_deadline"))
        summary["watcher_post_target_removed_pressure"] += to_int(row.get("primary_behavior_post_target_removed_pressure"))
    return summary


def summarize_run(run_dir: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for case_dir in sorted(path for path in run_dir.iterdir() if path.is_dir()):
        row: dict[str, object] = {"case": case_dir.name}
        row.update(summarize_metrics(case_dir))
        row.update(summarize_watcher(case_dir))
        rows.append(row)
    return rows


def print_table(rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "case",
        "metric_rows",
        "target_removed",
        "player_deaths",
        "target_timeouts",
        "movement_failures",
        "loot_acquired",
        "damage_taken",
        "flee_events",
        "watcher_xy_warn",
        "watcher_z_warn",
        "watcher_rewind_warn",
        "watcher_behavior_critical",
        "watcher_bad_target_choice",
        "watcher_aggro_not_dropped",
        "watcher_flee_too_short",
        "watcher_target_stuck",
        "watcher_unsafe_rest",
        "watcher_safe_exit_deadline",
        "watcher_post_target_removed_pressure",
    ]
    print("\t".join(fieldnames))
    for row in rows:
        print("\t".join(str(row.get(field, 0)) for field in fieldnames))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "case",
        "metric_rows",
        *METRIC_SUM_COLUMNS,
        "flee_events",
        "watcher_rows",
        "watcher_xy_warn",
        "watcher_z_warn",
        "watcher_rewind_warn",
        "watcher_behavior_critical",
        "watcher_bad_target_choice",
        "watcher_aggro_not_dropped",
        "watcher_flee_too_short",
        "watcher_target_stuck",
        "watcher_unsafe_rest",
        "watcher_safe_exit_deadline",
        "watcher_post_target_removed_pressure",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--csv-out", type=Path)
    args = parser.parse_args()

    rows = summarize_run(args.run_dir)
    if args.csv_out:
        write_csv(args.csv_out, rows)
    else:
        print_table(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
