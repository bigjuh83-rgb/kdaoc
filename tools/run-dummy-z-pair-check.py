#!/usr/bin/env python3
"""Run paired nearby dummies and compare their movement/Z traces."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import os
import subprocess
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DEFAULT_REPORT_ROOT = TOOLS / "reports" / "dummy-z-pair"


def load_growth_module():
    module_path = Path(__file__).with_name("dummy_growth_suite.py")
    spec = importlib.util.spec_from_file_location("run_dummy_growth_suite_for_pair_check", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


growth = load_growth_module()


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def unique_output_dir(root: Path, realm: str, pairs: int) -> Path:
    base_name = f"{timestamp()}-{realm}-pairs{pairs}"
    candidate = root / base_name
    suffix = 2

    while candidate.exists():
        candidate = root / f"{base_name}-{suffix}"
        suffix += 1

    return candidate


def duplicate_cycle(cycle: str, pairs: int, delimiter: str = "|") -> str:
    values = [part for part in cycle.split(delimiter) if part != ""]
    if not values:
        return ""
    duplicated: list[str] = []
    for index in range(pairs):
        value = values[index % len(values)]
        duplicated.extend([value, value])
    return delimiter.join(duplicated)


def duplicate_spec_cycle(cycle: str, pairs: int) -> str:
    values = [part for part in cycle.split("||") if part != ""]
    if not values:
        return ""
    duplicated: list[str] = []
    for index in range(pairs):
        value = values[index % len(values)]
        duplicated.extend([value, value])
    return "||".join(duplicated)


def build_pair_profile(realm_key: str, pairs: int):
    realm = growth.REALMS[realm_key]
    return replace(
        realm,
        prefix=f"zpair{realm.key}",
        character_prefix=f"ZPair{realm.key.capitalize()}",
        class_cycle=duplicate_cycle(realm.class_cycle, pairs),
        race_cycle=duplicate_cycle(realm.race_cycle, pairs),
        spec_cycle=duplicate_spec_cycle(realm.spec_cycle, pairs),
    )


def trace_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("event") not in {"move_step", "send_position", "ground_z_sample"}:
            continue
        if all(key in row for key in ("x", "y", "z")):
            rows.append(row)
    return rows


def numeric(row: dict[str, object], key: str) -> float:
    value = row.get(key, 0)
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def compare_trace_pair(first_path: Path, second_path: Path) -> dict[str, object]:
    first = [row for row in trace_rows(first_path) if row.get("event") == "move_step"]
    second = [row for row in trace_rows(second_path) if row.get("event") == "move_step"]
    samples = min(len(first), len(second))
    z_deltas: list[float] = []
    xy_deltas: list[float] = []

    for index in range(samples):
        left = first[index]
        right = second[index]
        dx = numeric(left, "x") - numeric(right, "x")
        dy = numeric(left, "y") - numeric(right, "y")
        dz = numeric(left, "z") - numeric(right, "z")
        xy_deltas.append(math.sqrt(dx * dx + dy * dy))
        z_deltas.append(abs(dz))

    all_rows = trace_rows(first_path) + trace_rows(second_path)
    z_source_counts: dict[str, int] = {}
    for row in all_rows:
        source = str(row.get("z_source", ""))
        if source:
            z_source_counts[source] = z_source_counts.get(source, 0) + 1

    return {
        "samples": samples,
        "first_moves": len(first),
        "second_moves": len(second),
        "avg_abs_z_delta": sum(z_deltas) / len(z_deltas) if z_deltas else 0.0,
        "max_abs_z_delta": max(z_deltas) if z_deltas else 0.0,
        "avg_xy_delta": sum(xy_deltas) / len(xy_deltas) if xy_deltas else 0.0,
        "max_xy_delta": max(xy_deltas) if xy_deltas else 0.0,
        "ground_z_sample_events": sum(1 for row in all_rows if row.get("event") == "ground_z_sample"),
        "ground_z_sampler_moves": z_source_counts.get("ground_z_sampler", 0),
        "interpolated_moves": z_source_counts.get("interpolated", 0),
    }


def run_command(command: list[str], dry_run: bool) -> int:
    print(growth.command_for_metadata(command))
    if dry_run:
        return 0
    return subprocess.run(command).returncode


def write_pair_summary(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "pair",
        "first_account",
        "second_account",
        "samples",
        "first_moves",
        "second_moves",
        "avg_abs_z_delta",
        "max_abs_z_delta",
        "avg_xy_delta",
        "max_xy_delta",
        "ground_z_sample_events",
        "ground_z_sampler_moves",
        "interpolated_moves",
        "z_status",
        "xy_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_report(path: Path, rows: list[dict[str, object]], summary_csv: Path) -> None:
    lines = [
        "# Dummy Z Pair Check",
        "",
        f"- Pair summary CSV: `{summary_csv}`",
        "",
        "| Pair | Accounts | Samples | Avg Z Delta | Max Z Delta | Avg XY Delta | Ground Z Samples | Z | XY |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {pair} | `{first_account}` / `{second_account}` | {samples} | {avg_abs_z_delta:.2f} | "
            "{max_abs_z_delta:.2f} | {avg_xy_delta:.2f} | {ground_z_sample_events} | {z_status} | {xy_status} |".format(
                **row
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--realm", choices=sorted(growth.REALMS), default="alb")
    parser.add_argument("--pairs", type=int, default=1)
    parser.add_argument("--host", default=growth.DEFAULT_DUMMY_HOST)
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--nav-api-url", default="http://127.0.0.1:5000")
    parser.add_argument("--mysql-bin", default=os.environ.get("MYSQL_BIN"))
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT", "3306")))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME", "opendaoc"))
    parser.add_argument("--db-user", default=os.environ.get("DB_USER", "root"))
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD", growth.read_serverconfig_password()))
    parser.add_argument("--template-account", default="dummy040")
    parser.add_argument("--template-character", default="Dummy040")
    parser.add_argument("--password", default=os.environ.get("OPENDAOC_DUMMY_PASSWORD", "dummy-pass"))
    parser.add_argument("--start", type=int, default=1601)
    parser.add_argument("--position-step", type=int, default=80)
    parser.add_argument("--segment-seconds", type=int, default=45)
    parser.add_argument("--ramp-up", type=int, default=3)
    parser.add_argument("--z-warn-delta", type=float, default=180.0)
    parser.add_argument("--xy-warn-delta", type=float, default=1500.0)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_REPORT_ROOT)
    parser.add_argument("--replace", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--no-starter-equipment", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.mysql_bin = growth.resolve_mysql_bin(args.mysql_bin)
    return args


def main() -> int:
    args = parse_args()
    if args.pairs < 1:
        raise SystemExit("--pairs must be >= 1")

    output_dir = unique_output_dir(args.output_root, args.realm, args.pairs)
    case_dir = output_dir / f"{args.realm}-pairs{args.pairs}"
    case_dir.mkdir(parents=True, exist_ok=True)
    accounts_csv = case_dir / "accounts.csv"
    path_graph = output_dir / "growth-route-graph.json"
    growth.write_growth_path_graph(path_graph)

    profile = build_pair_profile(args.realm, args.pairs)
    count = args.pairs * 2
    provision_command = growth.build_provision_command(args, profile, accounts_csv, count, args.start)
    rc = run_command(provision_command, args.dry_run)
    if rc != 0:
        return rc

    if not args.dry_run:
        accounts = [row["username"] for row in growth.read_accounts(accounts_csv)]
        growth.reset_growth_characters(args, accounts, level=1)
    else:
        accounts = [f"{profile.prefix}{args.start + index:03d}" for index in range(count)]

    behavior_args = argparse.Namespace(
        host=args.host,
        port=args.port,
        segment_seconds=args.segment_seconds,
        ramp_up=args.ramp_up,
        login_retries=5,
        login_retry_delay=3.0,
        api_port=args.api_port,
        max_target_distance=5200,
        target_timeout=65,
        combat_interval=1.5,
        target_pool=5,
        smooth_move_interval=0.2,
        movement_speed=191.0,
        path_last_mile_distance=1200.0,
        ground_z_offset=0,
        encounter_log_interval=2.0,
        nav_api_url=args.nav_api_url,
        live_api_url="",
    )
    behavior_command = growth.build_behavior_command(
        args=behavior_args,
        realm=profile,
        accounts_csv=accounts_csv,
        case_dir=case_dir,
        segment_index=1,
        party_size=count,
        current_level=1,
        path_graph=path_graph,
    )
    behavior_command[behavior_command.index("--party-size") + 1] = "1"
    behavior_command[behavior_command.index("--party-role-strategy") + 1] = "same"
    behavior_command[behavior_command.index("--behavior-profile") + 1] = "solo-melee"
    behavior_command[behavior_command.index("--action-rotation") + 1] = "melee-basic"
    rc = run_command(behavior_command, args.dry_run)

    rows: list[dict[str, object]] = []
    for pair_index in range(args.pairs):
        first = accounts[pair_index * 2]
        second = accounts[pair_index * 2 + 1]
        first_path = case_dir / "movement" / f"segment-001-{first}-1.jsonl"
        second_path = case_dir / "movement" / f"segment-001-{second}-1.jsonl"
        row = {
            "pair": pair_index + 1,
            "first_account": first,
            "second_account": second,
            **compare_trace_pair(first_path, second_path),
        }
        row["z_status"] = "warn" if float(row["max_abs_z_delta"]) > args.z_warn_delta else "ok"
        row["xy_status"] = "warn" if float(row["max_xy_delta"]) > args.xy_warn_delta else "ok"
        rows.append(row)

    summary_csv = output_dir / "pair-z-summary.csv"
    write_pair_summary(summary_csv, rows)
    write_report(output_dir / "summary.md", rows, summary_csv)
    print(f"z pair output: {output_dir}")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
