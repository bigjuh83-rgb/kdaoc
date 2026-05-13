#!/usr/bin/env python3
"""Summarize OpenDAoC StatPrint blocks from server.log."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean


STAT_START_RE = re.compile(r"(?P<time>\d{2}:\d{2}:\d{2}) \| .*?DOL\.GS\.StatPrint \|")
CPU_RE = re.compile(r"CPU \(process/system\):\s*(?P<process>[0-9.]+)%\s*/\s*(?P<system>[0-9.]+)%")
MEMORY_RE = re.compile(r"Memory \(used/commit\):\s*(?P<used>\d+) MB\s*/\s*(?P<commit>\d+) MB")
CLIENTS_RE = re.compile(r"Clients:\s*(?P<clients>\d+)")
TPS_RE = re.compile(
    r"Game loop TPS \(10/30/60\)s:\s*"
    r"(?P<tps10>[0-9.]+)%\s*/\s*(?P<tps30>[0-9.]+)%\s*/\s*(?P<tps60>[0-9.]+)%"
)


@dataclass(frozen=True)
class StatSample:
    time: str
    process_cpu: float
    system_cpu: float
    memory_used_mb: int
    memory_commit_mb: int
    clients: int
    tps10: float
    tps30: float
    tps60: float


def seconds_of_day(value: str) -> int:
    hour, minute, second = (int(part) for part in value.split(":"))
    return hour * 3600 + minute * 60 + second


def in_time_window(value: str, since_time: str | None, until_time: str | None) -> bool:
    if not since_time and not until_time:
        return True

    current = seconds_of_day(value)
    since = seconds_of_day(since_time) if since_time else 0
    until = seconds_of_day(until_time) if until_time else 24 * 3600 - 1

    if since <= until:
        return since <= current <= until

    return current >= since or current <= until


def parse_samples(log_path: Path, since_time: str | None = None, until_time: str | None = None) -> list[StatSample]:
    samples: list[StatSample] = []
    current_time: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        nonlocal current_time, current_lines
        if not current_time or not current_lines:
            current_time = None
            current_lines = []
            return

        block = "\n".join(current_lines)
        cpu = CPU_RE.search(block)
        memory = MEMORY_RE.search(block)
        clients = CLIENTS_RE.search(block)
        tps = TPS_RE.search(block)

        if cpu and memory and clients and tps and in_time_window(current_time, since_time, until_time):
            samples.append(
                StatSample(
                    time=current_time,
                    process_cpu=float(cpu.group("process")),
                    system_cpu=float(cpu.group("system")),
                    memory_used_mb=int(memory.group("used")),
                    memory_commit_mb=int(memory.group("commit")),
                    clients=int(clients.group("clients")),
                    tps10=float(tps.group("tps10")),
                    tps30=float(tps.group("tps30")),
                    tps60=float(tps.group("tps60")),
                )
            )

        current_time = None
        current_lines = []

    with log_path.open("r", encoding="utf-8", errors="replace") as log:
        for line in log:
            start = STAT_START_RE.search(line)
            if start:
                flush()
                current_time = start.group("time")
                current_lines = [line.rstrip("\n")]
                continue

            if current_time:
                current_lines.append(line.rstrip("\n"))

    flush()
    return samples


def summarize(samples: list[StatSample]) -> dict[str, object]:
    if not samples:
        return {"samples": 0}

    return {
        "samples": len(samples),
        "time_start": samples[0].time,
        "time_end": samples[-1].time,
        "max_clients": max(sample.clients for sample in samples),
        "avg_process_cpu": round(mean(sample.process_cpu for sample in samples), 2),
        "max_process_cpu": max(sample.process_cpu for sample in samples),
        "avg_system_cpu": round(mean(sample.system_cpu for sample in samples), 2),
        "max_system_cpu": max(sample.system_cpu for sample in samples),
        "max_memory_used_mb": max(sample.memory_used_mb for sample in samples),
        "max_memory_commit_mb": max(sample.memory_commit_mb for sample in samples),
        "min_tps10": min(sample.tps10 for sample in samples),
        "avg_tps10": round(mean(sample.tps10 for sample in samples), 2),
        "min_tps30": min(sample.tps30 for sample in samples),
        "avg_tps30": round(mean(sample.tps30 for sample in samples), 2),
        "min_tps60": min(sample.tps60 for sample in samples),
        "avg_tps60": round(mean(sample.tps60 for sample in samples), 2),
    }


def render_markdown(summary: dict[str, object]) -> str:
    if summary.get("samples", 0) == 0:
        return "\n## Server Stats\n\nNo StatPrint samples found for this test window.\n"

    return (
        "\n## Server Stats\n\n"
        f"- Samples: `{summary['samples']}` (`{summary['time_start']}` - `{summary['time_end']}`)\n"
        f"- Max clients: `{summary['max_clients']}`\n"
        f"- CPU process avg/max: `{summary['avg_process_cpu']}%` / `{summary['max_process_cpu']}%`\n"
        f"- CPU system avg/max: `{summary['avg_system_cpu']}%` / `{summary['max_system_cpu']}%`\n"
        f"- Memory used/commit max: `{summary['max_memory_used_mb']} MB` / `{summary['max_memory_commit_mb']} MB`\n"
        f"- TPS 10s min/avg: `{summary['min_tps10']}%` / `{summary['avg_tps10']}%`\n"
        f"- TPS 30s min/avg: `{summary['min_tps30']}%` / `{summary['avg_tps30']}%`\n"
        f"- TPS 60s min/avg: `{summary['min_tps60']}%` / `{summary['avg_tps60']}%`\n"
    )


def write_csv(path: Path, samples: list[StatSample]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(StatSample.__dataclass_fields__))
        writer.writeheader()
        for sample in samples:
            writer.writerow(asdict(sample))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("log")
    parser.add_argument("--since-time", help="include samples at or after HH:MM:SS")
    parser.add_argument("--until-time", help="include samples at or before HH:MM:SS")
    parser.add_argument("--csv")
    parser.add_argument("--json")
    parser.add_argument("--append-report")
    args = parser.parse_args()

    samples = parse_samples(Path(args.log), args.since_time, args.until_time)
    summary = summarize(samples)

    if args.csv:
        write_csv(Path(args.csv), samples)

    if args.json:
        json_path = Path(args.json)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    markdown = render_markdown(summary)

    if args.append_report:
        with Path(args.append_report).open("a", encoding="utf-8") as report:
            report.write(markdown)
    else:
        print(markdown, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
