#!/usr/bin/env python3
"""Compact pre-service growth case logs for low-token triage."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_PATTERNS = (
    "attack_z_mismatch_rejected",
    "target_commit_wait_range",
    "hunter_target_api_refresh_lost",
    "hunter_target_scan_empty",
    "server_los",
    "combat_not_visible_msg",
    "combat_out_of_range_msg",
    "target_removed",
    "target_removed_no_reward",
    "player_death",
    "death_detected",
    "flee_start",
    "validated_party_heal",
    "party_heal_target_approach",
    "party_support_preengage_position_deferred",
    "party_form_up_timeout_force_pull",
    "party_form_up_wait",
    "combat_damage_done",
    "combat_damage_taken",
    "loot",
)

SAMPLE_EVENTS = {
    "attack_z_mismatch_rejected",
    "target_commit_wait_range",
    "hunter_target_scan_empty",
    "player_death",
    "flee_start",
    "target_removed",
    "target_removed_no_reward",
    "combat_damage_done",
    "combat_damage_taken",
    "server_los_failure",
}

EVENT_SAMPLE_FIELDS = (
    "event",
    "elapsed",
    "username",
    "role",
    "behavior_state",
    "reason",
    "x",
    "y",
    "z",
    "target_name",
    "target_level",
    "target_x",
    "target_y",
    "target_z",
    "distance",
    "server_range_distance",
    "combat_start_distance",
    "attack_range",
    "combat_direct_move_distance",
    "target_z_delta",
    "attack_z_limit",
    "health_percent",
    "damage_done",
    "damage_taken",
)

METRIC_FIELDS = (
    "username",
    "ok",
    "elapsed_seconds",
    "combat_engagements",
    "target_removed",
    "player_deaths",
    "target_timeouts",
    "movement_failures",
    "loot_acquired",
    "damage_done",
    "damage_taken",
    "healing_done",
    "healing_received",
    "error",
)


def to_int(value: object) -> int:
    text = str(value or "").strip()
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


def compact_event(event: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for field in EVENT_SAMPLE_FIELDS:
        value = event.get(field)
        if value not in (None, ""):
            result[field] = value
    return result


def latest_segment_indexes(case_dir: Path) -> list[int]:
    indexes: set[int] = set()
    for path in case_dir.glob("segment-*-metrics.csv"):
        match = re.match(r"segment-(\d+)-metrics\.csv$", path.name)
        if match:
            indexes.add(int(match.group(1)))
    return sorted(indexes)


def resolve_segments(case_dir: Path, segment: int | None, last_segments: int) -> list[int]:
    indexes = latest_segment_indexes(case_dir)
    if segment is not None:
        return [segment]
    if last_segments > 0:
        return indexes[-last_segments:]
    return indexes


def summarize_segment(case_dir: Path, segment: int, sample_limit: int) -> dict[str, Any]:
    prefix = f"segment-{segment:03d}"
    metrics_path = case_dir / f"{prefix}-metrics.csv"
    combat_path = case_dir / f"{prefix}-combat.csv"
    inventory_path = case_dir / f"{prefix}-inventory.csv"
    report_path = case_dir / f"{prefix}-report.md"

    metrics_rows = read_csv_rows(metrics_path)
    combat_rows = read_csv_rows(combat_path)
    inventory_rows = read_csv_rows(inventory_path)
    action_counts: dict[str, int] = {}
    totals = {
        "combat_engagements": 0,
        "target_removed": 0,
        "player_deaths": 0,
        "target_timeouts": 0,
        "movement_failures": 0,
        "loot_acquired": 0,
        "damage_done": 0,
        "damage_taken": 0,
        "healing_done": 0,
        "healing_received": 0,
    }

    compact_metrics: list[dict[str, str | None]] = []
    for row in metrics_rows:
        compact_metrics.append({field: row.get(field) for field in METRIC_FIELDS})
        for key in totals:
            totals[key] += to_int(row.get(key))
        for key, value in row.items():
            if key.startswith("action_"):
                count = to_int(value)
                if count:
                    action_counts[key[7:]] = action_counts.get(key[7:], 0) + count

    patterns = {pattern: 0 for pattern in DEFAULT_PATTERNS}
    samples: dict[str, list[dict[str, Any]]] = {event: [] for event in SAMPLE_EVENTS}
    log_files: list[Path] = []
    for subdir in ("encounters", "movement"):
        log_files.extend(sorted((case_dir / subdir).glob(f"{prefix}-*.jsonl")))

    for path in log_files:
        with path.open(encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if len(line) > 4096:
                    line = line[:4096]
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    for pattern in DEFAULT_PATTERNS:
                        if pattern in line:
                            patterns[pattern] += 1
                    continue
                event_name = str(event.get("event", ""))
                if event_name in patterns:
                    patterns[event_name] += 1
                if event_name in samples and len(samples[event_name]) < sample_limit:
                    samples[event_name].append(compact_event(event))

    samples = {key: value for key, value in samples.items() if value}
    top_actions = dict(sorted(action_counts.items(), key=lambda item: item[1], reverse=True)[:40])
    verdict = classify_segment(totals, patterns, top_actions)

    return {
        "segment": segment,
        "files": {
            "metrics": str(metrics_path) if metrics_path.exists() else "",
            "combat": str(combat_path) if combat_path.exists() else "",
            "inventory": str(inventory_path) if inventory_path.exists() else "",
            "report": str(report_path) if report_path.exists() else "",
        },
        "totals": totals,
        "metrics": compact_metrics,
        "combat": combat_rows[: max(sample_limit, 5)],
        "inventory_rows": len(inventory_rows),
        "top_actions": top_actions,
        "patterns": patterns,
        "samples": samples,
        "verdict": verdict,
    }


def classify_segment(totals: dict[str, int], patterns: dict[str, int], actions: dict[str, int]) -> dict[str, str]:
    if totals["target_removed"] > 0 or totals["loot_acquired"] > 0:
        return {"state": "progressing", "primary_bottleneck": ""}
    if totals["combat_engagements"] <= 0:
        if actions.get("target_commit_wait_range", 0) > 0:
            return {"state": "stalled", "primary_bottleneck": "target_commit_wait_range"}
        if actions.get("party_support_preengage_position_deferred", 0) > 0:
            return {"state": "stalled", "primary_bottleneck": "party_support_preengage_position_deferred"}
        if patterns.get("hunter_target_scan_empty", 0) > 0:
            return {"state": "stalled", "primary_bottleneck": "hunter_target_scan_empty"}
        return {"state": "stalled", "primary_bottleneck": "no_combat_engagements"}
    if patterns.get("attack_z_mismatch_rejected", 0) > 0:
        return {"state": "blocked", "primary_bottleneck": "attack_z_mismatch_rejected"}
    if totals["player_deaths"] > 0:
        return {"state": "blocked", "primary_bottleneck": "player_deaths"}
    return {"state": "stalled", "primary_bottleneck": "no_target_removed"}


def call_chat_completion(base_url: str, model: str, api_key: str, payload: dict[str, Any], timeout: float) -> str:
    prompt = (
        "Return concise Korean JSON with keys verdict, primary_bottleneck, evidence, next_action. "
        "Use only the provided compact growth triage JSON. Do not invent facts."
    )
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)[:24000]},
        ],
        "temperature": 0.1,
        "max_tokens": 700,
    }
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    url = base_url.rstrip("/") + "/chat/completions"
    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read().decode("utf-8"))
    return str(result["choices"][0]["message"]["content"])


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_summary(args: argparse.Namespace) -> dict[str, Any]:
    case_dir = args.case_dir.resolve()
    segments = resolve_segments(case_dir, args.segment, args.last_segments)
    return {
        "case_dir": str(case_dir),
        "case": case_dir.name,
        "segments": [summarize_segment(case_dir, segment, args.sample_limit) for segment in segments],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("--segment", type=int)
    parser.add_argument("--last-segments", type=int, default=1)
    parser.add_argument("--sample-limit", type=int, default=3)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--local-llm-url", default="")
    parser.add_argument("--local-llm-model", default="gemma-4-12b-it")
    parser.add_argument("--cerebras", action="store_true")
    parser.add_argument("--cerebras-model", default="gemma-4-31b")
    parser.add_argument("--llm-timeout", type=float, default=45.0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    summary = build_summary(args)
    out_path = args.out or (args.case_dir / "triage-summary.json")
    write_json(out_path, summary)

    llm_results: dict[str, str] = {}
    if args.local_llm_url:
        try:
            llm_results["local"] = call_chat_completion(
                args.local_llm_url.rstrip("/") + "/v1",
                args.local_llm_model,
                "",
                summary,
                args.llm_timeout,
            )
        except Exception as exc:
            llm_results["local"] = f"ERROR {type(exc).__name__}: {exc}"
    if args.cerebras:
        api_key = os.environ.get("CEREBRAS_API_KEY", "").strip()
        if api_key:
            try:
                llm_results["cerebras"] = call_chat_completion(
                    "https://api.cerebras.ai/v1",
                    args.cerebras_model,
                    api_key,
                    summary,
                    args.llm_timeout,
                )
            except Exception as exc:
                llm_results["cerebras"] = f"ERROR {type(exc).__name__}: {exc}"
        else:
            llm_results["cerebras"] = "ERROR missing CEREBRAS_API_KEY"
    if llm_results:
        write_json(out_path.with_name(out_path.stem + "-llm.json"), llm_results)

    if not args.quiet:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
