#!/usr/bin/env python3
"""Run multiple dummy-client balance scenarios and summarize the results."""

from __future__ import annotations

import argparse
import csv
import json
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DEFAULT_SCENARIOS = ["newbie-solo", "solo-melee", "ai-pve-casual", "ai-party-casual", "party-assist", "mobgrowth-pressure"]


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def parse_csv_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def run(command: list[str], log_path: Path) -> int:
    print("+ " + shlex.join(command))
    with log_path.open("a", encoding="utf-8") as log:
        log.write("+ " + shlex.join(command) + "\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        assert process.stdout is not None
        for line in process.stdout:
            print(line, end="")
            log.write(line)

        return process.wait()


def find_new_run_dir(run_root: Path, before: set[Path]) -> Path | None:
    after = {path for path in run_root.iterdir() if path.is_dir()} if run_root.exists() else set()
    created = sorted(after - before, key=lambda path: path.stat().st_mtime, reverse=True)
    return created[0] if created else None


def read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def scenario_account_count(args: argparse.Namespace) -> int:
    return max(1, args.count or args.concurrency or 1)


def slice_accounts_csv(args: argparse.Namespace, scenario: str, index: int, suite_dir: Path) -> str | None:
    if not args.accounts_csv or args.reuse_accounts:
        return args.accounts_csv

    source = Path(args.accounts_csv)
    if not source.exists():
        return args.accounts_csv

    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames

    needed = scenario_account_count(args)
    start = args.account_start_offset + index * needed
    end = start + needed
    if not fieldnames or end > len(rows):
        return args.accounts_csv

    accounts_dir = suite_dir / "accounts"
    accounts_dir.mkdir(parents=True, exist_ok=True)
    safe_scenario = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in scenario)
    target = accounts_dir / f"{index + 1:02d}-{safe_scenario}.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows[start:end])

    return str(target)


def summarize_run(scenario: str, run_dir: Path | None, exit_code: int) -> dict[str, object]:
    row: dict[str, object] = {
        "scenario": scenario,
        "exit_code": exit_code,
        "run_dir": str(run_dir) if run_dir else "",
        "report": str(run_dir / "report.md") if run_dir else "",
        "status": "NO_OUTPUT",
        "rounds": "0/0",
        "actions": 0,
        "engagements": 0,
        "target_removed": 0,
        "player_deaths": 0,
        "target_timeouts": 0,
        "max_clients": "",
        "min_tps10": "",
        "min_tps30": "",
        "min_tps60": "",
        "max_process_cpu": "",
        "max_system_cpu": "",
        "max_memory_used_mb": "",
        "issues": "",
    }

    if run_dir is None:
        return row

    assessment = read_json(run_dir / "assessment.json")
    if assessment is None:
        row["status"] = "DRY_RUN" if exit_code == 0 else "NO_ASSESSMENT"
        return row

    metrics = assessment.get("metrics") if isinstance(assessment, dict) else None
    server_stats = assessment.get("server_stats") if isinstance(assessment, dict) else None
    issues = assessment.get("issues") if isinstance(assessment, dict) else []

    if isinstance(metrics, dict):
        row["rounds"] = f"{metrics.get('ok_rows', 0)}/{metrics.get('rows', 0)}"
        row["actions"] = metrics.get("actions", 0)
        row["engagements"] = metrics.get("combat_engagements", 0)
        row["target_removed"] = metrics.get("target_removed", 0)
        row["player_deaths"] = metrics.get("player_deaths", 0)
        row["target_timeouts"] = metrics.get("target_timeouts", 0)

    if isinstance(server_stats, dict):
        for key in [
            "max_clients",
            "min_tps10",
            "min_tps30",
            "min_tps60",
            "max_process_cpu",
            "max_system_cpu",
            "max_memory_used_mb",
        ]:
            row[key] = server_stats.get(key, "")

    row["status"] = str(assessment.get("status", "UNKNOWN"))
    if isinstance(issues, list):
        row["issues"] = "; ".join(str(issue.get("message", issue)) for issue in issues)

    return row


def write_summary_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "scenario",
        "status",
        "exit_code",
        "rounds",
        "actions",
        "engagements",
        "target_removed",
        "player_deaths",
        "target_timeouts",
        "max_clients",
        "min_tps10",
        "min_tps30",
        "min_tps60",
        "max_process_cpu",
        "max_system_cpu",
        "max_memory_used_mb",
        "report",
        "run_dir",
        "issues",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_summary_csv(path: str | None) -> dict[str, dict[str, str]]:
    if not path:
        return {}
    source = Path(path)
    if not source.exists():
        return {}

    with source.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return {row.get("scenario", ""): row for row in reader if row.get("scenario")}


def int_value(row: dict[str, object] | dict[str, str], key: str) -> int:
    try:
        return int(str(row.get(key, 0) or 0))
    except ValueError:
        return 0


def write_comparison_md(path: Path, rows: list[dict[str, object]], baseline: dict[str, dict[str, str]]) -> None:
    if not baseline:
        return

    lines = [
        "# Baseline Comparison",
        "",
        "| Scenario | Engagements | Removed | Deaths | Timeouts |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]

    for row in rows:
        scenario = str(row["scenario"])
        old = baseline.get(scenario)
        if old is None:
            lines.append(
                f"| `{scenario}` | new `{row['engagements']}` | new `{row['target_removed']}` | "
                f"new `{row['player_deaths']}` | new `{row['target_timeouts']}` |"
            )
            continue

        lines.append(
            f"| `{scenario}` | {int_value(row, 'engagements') - int_value(old, 'engagements'):+d} | "
            f"{int_value(row, 'target_removed') - int_value(old, 'target_removed'):+d} | "
            f"{int_value(row, 'player_deaths') - int_value(old, 'player_deaths'):+d} | "
            f"{int_value(row, 'target_timeouts') - int_value(old, 'target_timeouts'):+d} |"
        )

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_summary_md(path: Path, rows: list[dict[str, object]], suite_name: str) -> None:
    lines = [
        f"# Dummy Balance Suite - {suite_name}",
        "",
        "| Scenario | Status | Rounds | Engagements | Removed | Deaths | Timeouts | TPS 10/30/60 | CPU Max | Memory Max | Report |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- |",
    ]

    for row in rows:
        report = str(row["report"])
        report_link = f"[report]({report})" if report else ""
        tps = f"{row['min_tps10']}/{row['min_tps30']}/{row['min_tps60']}" if row["min_tps10"] != "" else ""
        cpu = f"{row['max_process_cpu']}/{row['max_system_cpu']}" if row["max_process_cpu"] != "" else ""
        lines.append(
            f"| `{row['scenario']}` | `{row['status']}` | {row['rounds']} | {row['engagements']} | "
            f"{row['target_removed']} | {row['player_deaths']} | {row['target_timeouts']} | "
            f"{tps} | {cpu} | {row['max_memory_used_mb']} | {report_link} |"
        )

    failures = [row for row in rows if row["status"] not in {"PASS", "WARN", "DRY_RUN"} or int(row["exit_code"]) != 0]
    warnings = [row for row in rows if row["status"] == "WARN"]

    lines += ["", "## Notes", ""]
    if failures:
        lines.append(f"- Failures: `{len(failures)}`")
    if warnings:
        lines.append(f"- Warnings: `{len(warnings)}`")
    if not failures and not warnings:
        lines.append("- No failures or warnings.")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_run_command(args: argparse.Namespace, scenario: str, run_root: Path, accounts_csv: str | None) -> list[str]:
    command = [
        sys.executable,
        str(TOOLS / "run-dummy-load-test.py"),
        args.preset,
        "--scenario",
        scenario,
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--report-root",
        str(run_root),
        "--name",
        args.name,
        "--no-fail-on-assessment",
    ]

    passthroughs = [
        ("--start", args.start),
        ("--count", args.count),
        ("--concurrency", args.concurrency),
        ("--hold", args.hold),
        ("--party-size", args.party_size),
        ("--ramp-up", args.ramp_up),
        ("--rounds", args.rounds),
        ("--accounts-csv", accounts_csv),
        ("--server-log", args.server_log),
        ("--server-log-time-offset-hours", args.server_log_time_offset_hours),
        ("--warn-process-cpu", args.warn_process_cpu),
        ("--warn-system-cpu", args.warn_system_cpu),
        ("--warn-memory-used-mb", args.warn_memory_used_mb),
        ("--max-memory-used-mb", args.max_memory_used_mb),
        ("--min-target-removed", args.min_target_removed),
        ("--max-player-deaths", args.max_player_deaths),
    ]

    for flag, value in passthroughs:
        if value is not None:
            command += [flag, str(value)]

    if args.fresh_account_per_round:
        command.append("--fresh-account-per-round")
    if args.skip_provision:
        command.append("--skip-provision")
    if args.dry_run:
        command.append("--dry-run")

    return command


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preset", default="smoke")
    parser.add_argument("--scenarios", default=",".join(DEFAULT_SCENARIOS))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--start", type=int)
    parser.add_argument("--count", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--hold", type=int)
    parser.add_argument("--party-size", type=int)
    parser.add_argument("--ramp-up", type=int)
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--fresh-account-per-round", action="store_true")
    parser.add_argument("--accounts-csv")
    parser.add_argument("--account-start-offset", type=int, default=0)
    parser.add_argument("--reuse-accounts", action="store_true")
    parser.add_argument("--server-log")
    parser.add_argument("--server-log-time-offset-hours", type=float)
    parser.add_argument("--warn-process-cpu", type=float)
    parser.add_argument("--warn-system-cpu", type=float)
    parser.add_argument("--warn-memory-used-mb", type=int)
    parser.add_argument("--max-memory-used-mb", type=int)
    parser.add_argument("--min-target-removed", type=int)
    parser.add_argument("--max-player-deaths", type=int)
    parser.add_argument("--baseline-summary")
    parser.add_argument("--report-root", default=str(TOOLS / "reports" / "dummy-balance-suite"))
    parser.add_argument("--name", default="suite")
    parser.add_argument("--skip-provision", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    scenarios = parse_csv_list(args.scenarios)
    suite_dir = Path(args.report_root) / f"{timestamp()}-{args.name}"
    run_root = suite_dir / "runs"
    suite_dir.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)
    log_path = suite_dir / "suite.log"
    rows: list[dict[str, object]] = []

    for index, scenario in enumerate(scenarios):
        before = {path for path in run_root.iterdir() if path.is_dir()}
        scenario_accounts = slice_accounts_csv(args, scenario, index, suite_dir)
        command = build_run_command(args, scenario, run_root, scenario_accounts)
        exit_code = run(command, log_path)
        run_dir = find_new_run_dir(run_root, before)
        rows.append(summarize_run(scenario, run_dir, exit_code))

    summary_csv = suite_dir / "summary.csv"
    summary_md = suite_dir / "summary.md"
    comparison_md = suite_dir / "comparison.md"
    write_summary_csv(summary_csv, rows)
    write_summary_md(summary_md, rows, args.name)
    write_comparison_md(comparison_md, rows, read_summary_csv(args.baseline_summary))

    print(f"summary: {summary_md}")
    print(f"summary csv: {summary_csv}")
    if comparison_md.exists():
        print(f"comparison: {comparison_md}")
    print(f"log: {log_path}")

    return 0 if all(int(row["exit_code"]) == 0 for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
