#!/usr/bin/env python3
"""Analyze headless dummy movement trace JSONL files.

The report focuses on the two artifacts that are visible in-game:
large horizontal jumps that look like teleporting, and sudden Z changes
that make characters float or sink.
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Iterable


def to_float(value, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * (percent / 100.0)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = rank - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def expand_paths(patterns: Iterable[str | Path]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        text = str(pattern)
        matches = sorted(Path(match) for match in glob.glob(text))
        if matches:
            paths.extend(matches)
            continue
        path = Path(text)
        if path.exists():
            paths.append(path)
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.resolve()
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def analyze_paths(
    patterns: Iterable[str | Path],
    *,
    teleport_threshold: float = 800.0,
    z_threshold: float = 250.0,
) -> dict:
    paths = expand_paths(patterns)
    observed_horizontal: list[float] = []
    observed_abs_z: list[float] = []
    self_horizontal: list[float] = []
    self_abs_z: list[float] = []
    events_by_name: dict[str, dict[str, int]] = {}
    worst_events: list[dict] = []
    malformed_lines = 0

    def record_name(name: str, key: str) -> None:
        if not name:
            name = "unknown"
        bucket = events_by_name.setdefault(name, {"samples": 0, "teleports": 0, "z_spikes": 0})
        bucket[key] = bucket.get(key, 0) + 1

    for path in paths:
        saw_self_position = False
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    malformed_lines += 1
                    continue

                event = row.get("event")
                if event == "observe_player_position":
                    horizontal = to_float(row.get("horizontal_delta"))
                    abs_z = abs(to_float(row.get("delta_z")))
                    observed_horizontal.append(horizontal)
                    observed_abs_z.append(abs_z)
                    name = str(row.get("name") or row.get("object_id") or "unknown")
                    record_name(name, "samples")
                    severe = False
                    if horizontal > teleport_threshold:
                        record_name(name, "teleports")
                        severe = True
                    if abs_z > z_threshold:
                        record_name(name, "z_spikes")
                        severe = True
                    if severe:
                        worst_events.append(
                            {
                                "file": str(path),
                                "line": line_number,
                                "event": event,
                                "name": name,
                                "horizontal_delta": horizontal,
                                "abs_delta_z": abs_z,
                                "x": row.get("x"),
                                "y": row.get("y"),
                                "z": row.get("z"),
                            }
                        )
                elif event in {"observe_self_position", "observe_self_position_smooth"}:
                    previous_x = to_float(row.get("previous_x"))
                    previous_y = to_float(row.get("previous_y"))
                    previous_z = to_float(row.get("previous_z"))
                    is_initial_snap = (
                        not saw_self_position
                        and event == "observe_self_position"
                        and previous_x == 0.0
                        and previous_y == 0.0
                        and previous_z == 0.0
                    )
                    saw_self_position = True
                    if is_initial_snap:
                        continue
                    self_horizontal.append(to_float(row.get("horizontal_delta") or row.get("distance")))
                    self_abs_z.append(abs(to_float(row.get("delta_z"))))

    observed_teleports = sum(1 for value in observed_horizontal if value > teleport_threshold)
    observed_z_spikes = sum(1 for value in observed_abs_z if value > z_threshold)
    self_snaps = sum(
        1
        for horizontal, abs_z in zip(self_horizontal, self_abs_z)
        if horizontal > teleport_threshold or abs_z > z_threshold
    )
    worst_events.sort(key=lambda row: (row["horizontal_delta"], row["abs_delta_z"]), reverse=True)

    return {
        "files": len(paths),
        "malformed_lines": malformed_lines,
        "teleport_threshold": teleport_threshold,
        "z_threshold": z_threshold,
        "observed_samples": len(observed_horizontal),
        "observed_teleports": observed_teleports,
        "observed_z_spikes": observed_z_spikes,
        "observed_horizontal_max": max(observed_horizontal, default=0.0),
        "observed_horizontal_p95": percentile(observed_horizontal, 95),
        "observed_abs_z_max": max(observed_abs_z, default=0.0),
        "observed_abs_z_p95": percentile(observed_abs_z, 95),
        "self_position_samples": len(self_horizontal),
        "self_snaps": self_snaps,
        "self_horizontal_max": max(self_horizontal, default=0.0),
        "self_abs_z_max": max(self_abs_z, default=0.0),
        "events_by_name": events_by_name,
        "worst_events": worst_events[:20],
    }


def write_markdown(path: str | Path, result: dict) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Dummy Movement Trace Analysis",
        "",
        "## Summary",
        "",
        f"- Files: `{result['files']}`",
        f"- Malformed lines: `{result['malformed_lines']}`",
        f"- Observed samples: `{result['observed_samples']}`",
        f"- Severe observed teleports: `{result['observed_teleports']}` (`>{result['teleport_threshold']}` world units)",
        f"- Severe observed Z spikes: `{result['observed_z_spikes']}` (`>{result['z_threshold']}` world units)",
        f"- Self correction samples: `{result['self_position_samples']}`",
        f"- Severe self snaps: `{result['self_snaps']}`",
        "",
        "## Distribution",
        "",
        "| Metric | Max | P95 |",
        "| --- | ---: | ---: |",
        f"| Observed horizontal delta | {result['observed_horizontal_max']:.1f} | {result['observed_horizontal_p95']:.1f} |",
        f"| Observed abs Z delta | {result['observed_abs_z_max']:.1f} | {result['observed_abs_z_p95']:.1f} |",
        f"| Self horizontal correction | {result['self_horizontal_max']:.1f} | n/a |",
        f"| Self abs Z correction | {result['self_abs_z_max']:.1f} | n/a |",
        "",
        "## Observed Player Breakdown",
        "",
        "| Name | Samples | Teleports | Z Spikes |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, row in sorted(result["events_by_name"].items(), key=lambda item: item[0]):
        lines.append(f"| `{name}` | {row.get('samples', 0)} | {row.get('teleports', 0)} | {row.get('z_spikes', 0)} |")

    lines.extend(["", "## Worst Events", "", "| File | Line | Name | Horizontal | Abs Z | Position |", "| --- | ---: | --- | ---: | ---: | --- |"])
    if result["worst_events"]:
        for event in result["worst_events"]:
            position = f"{event.get('x')},{event.get('y')},{event.get('z')}"
            lines.append(
                f"| `{event['file']}` | {event['line']} | `{event['name']}` | "
                f"{event['horizontal_delta']:.1f} | {event['abs_delta_z']:.1f} | `{position}` |"
            )
    else:
        lines.append("| `none` | 0 | `none` | 0.0 | 0.0 | `none` |")

    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("patterns", nargs="+", help="trace JSONL file paths or glob patterns")
    parser.add_argument("--teleport-threshold", type=float, default=800.0)
    parser.add_argument("--z-threshold", type=float, default=250.0)
    parser.add_argument("--json-out", default="")
    parser.add_argument("--report-md", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = analyze_paths(args.patterns, teleport_threshold=args.teleport_threshold, z_threshold=args.z_threshold)
    if args.json_out:
        path = Path(args.json_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report_md:
        write_markdown(args.report_md, result)
    if not args.json_out and not args.report_md:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["observed_teleports"] or result["observed_z_spikes"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
