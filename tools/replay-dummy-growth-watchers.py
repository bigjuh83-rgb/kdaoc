#!/usr/bin/env python3
"""Replay growth-suite watcher summaries from existing movement/encounter logs."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import sys
from pathlib import Path


TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent


def load_growth_module():
    module_path = TOOLS / "run-dummy-growth-suite.py"
    spec = importlib.util.spec_from_file_location("run_dummy_growth_suite_replay", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


growth = load_growth_module()


def timeline_level_map(run_dir: Path) -> dict[tuple[str, int], int]:
    path = run_dir / "timeline.csv"
    levels: dict[tuple[str, int], int] = {}
    if not path.exists():
        return levels
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            case_name = row.get("case", "")
            segment = growth.to_int(row.get("segment"))
            level = growth.to_int(row.get("level_before")) or growth.to_int(row.get("level_after")) or 1
            if case_name and segment:
                levels[(case_name, segment)] = level
    return levels


def prefer_for_case(case_name: str, segment: int, levels: dict[tuple[str, int], int]) -> str:
    realm_key = case_name.split("-", 1)[0]
    if realm_key not in growth.REALMS:
        return ""
    party_size = 1
    if "-p" in case_name:
        party_size = max(1, growth.to_int(case_name.rsplit("-p", 1)[-1]) or 1)
    route = growth.select_route_point(growth.REALMS[realm_key], levels.get((case_name, segment), 1), party_size)
    return route.prefer


def replay_case(run_dir: Path, case_dir: Path, args: argparse.Namespace) -> tuple[int, int]:
    summary_path = case_dir / "watcher-movement-summary.csv"
    if not summary_path.exists():
        return (0, 0)
    levels = timeline_level_map(run_dir)
    rows: list[dict[str, object]] = []
    with summary_path.open(encoding="utf-8", newline="") as handle:
        source_rows = list(csv.DictReader(handle))
    for row in source_rows:
        case_name = row.get("case") or case_dir.name
        segment = growth.to_int(row.get("segment"))
        primary_account = row.get("primary_account", "")
        watcher_account = row.get("watcher_account", "")
        if not segment or not primary_account or not watcher_account:
            continue
        primary_path = case_dir / "movement" / f"segment-{segment:03d}-{primary_account}-1.jsonl"
        watcher_path = case_dir / "movement" / f"segment-{segment:03d}-{watcher_account}-1.jsonl"
        primary_encounter_path = case_dir / "encounters" / f"segment-{segment:03d}-{primary_account}-1.jsonl"
        rows.append(
            {
                "case": case_name,
                "segment": segment,
                "primary_account": primary_account,
                "watcher_account": watcher_account,
                **growth.compare_watcher_pair(
                    primary_path,
                    watcher_path,
                    primary_encounter_path=primary_encounter_path,
                    prefer_target_name=prefer_for_case(case_name, segment, levels),
                    z_warn_delta=args.watcher_z_warn_delta,
                    xy_warn_delta=args.watcher_xy_warn_delta,
                    rewind_warn_distance=args.watcher_rewind_warn_distance,
                    z_compare_xy_distance=args.watcher_z_compare_xy_distance,
                ),
            }
        )
    if rows:
        summary_path.unlink()
        growth.write_watcher_summary(summary_path, rows)
    critical = sum(1 for row in rows if str(row.get("primary_behavior_anomaly_status", "")).lower() == "critical")
    return (len(rows), critical)


def replay_run(run_dir: Path, args: argparse.Namespace) -> tuple[int, int]:
    total_rows = 0
    total_critical = 0
    for case_dir in sorted(path for path in run_dir.iterdir() if path.is_dir()):
        rows, critical = replay_case(run_dir, case_dir, args)
        total_rows += rows
        total_critical += critical
    return (total_rows, total_critical)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--watcher-z-warn-delta", type=float, default=96.0)
    parser.add_argument("--watcher-z-compare-xy-distance", type=float, default=850.0)
    parser.add_argument("--watcher-xy-warn-delta", type=float, default=3000.0)
    parser.add_argument("--watcher-rewind-warn-distance", type=float, default=900.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    rows, critical = replay_run(args.run_dir, args)
    print(f"replayed watcher rows={rows} behavior_critical={critical} run_dir={args.run_dir}")
    return 1 if critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
