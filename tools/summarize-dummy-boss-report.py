#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Iterable


def int_value(value: object) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


ROLE_METRICS = (
    "attack_on",
    "damage_done",
    "damage_taken",
    "healing_done",
    "healing_received",
    "combat_not_visible_msg",
    "party_assist",
    "party_assist_delay",
    "party_assist_leader_wait",
    "party_assist_wait",
    "party_follow_suppressed_combat",
    "party_focus_pressure_backoff",
    "party_focus_pressure_hold",
    "party_focus_target_backoff",
    "party_focus_target_hold",
    "party_melee_survival_backoff",
    "party_melee_survival_hold",
    "party_survival_backoff",
    "party_survival_hold",
    "validated_spell",
    "validated_taunt_skill",
    "boss_ranged_backoff",
    "smooth_move",
    "smooth_hold",
)


def role_from_row(row: dict[str, str]) -> str:
    for key, value in sorted(row.items()):
        if key.startswith("rotation_") and int_value(value) > 0:
            return key.removeprefix("rotation_")
        if key.startswith("action_rotation_") and int_value(value) > 0:
            return key.removeprefix("action_rotation_")
    return "unknown"


def metric_value(row: dict[str, str], metric: str) -> int:
    return int_value(row.get(metric) or row.get(f"action_{metric}"))


def new_role_summary() -> dict[str, int]:
    role_summary = {
        "workers_total": 0,
        "workers_ok": 0,
        "deaths": 0,
        "timeouts": 0,
        "target_removed": 0,
        "loot": 0,
        "not_visible": 0,
    }
    for metric in ROLE_METRICS:
        role_summary[metric] = 0
    return role_summary


def update_role_summary(role_summary: dict[str, int], row: dict[str, str], deaths: int) -> None:
    role_summary["workers_total"] += 1
    role_summary["workers_ok"] += int(row.get("ok") == "true")
    role_summary["deaths"] += deaths
    role_summary["timeouts"] += int_value(row.get("target_timeouts"))
    role_summary["target_removed"] += int_value(row.get("target_removed"))
    role_summary["loot"] += int_value(row.get("loot_acquired"))
    for metric in ROLE_METRICS:
        role_summary[metric] += metric_value(row, metric)
    role_summary["not_visible"] = role_summary["combat_not_visible_msg"]


def detect_case_warnings(case_summary: dict[str, object]) -> list[str]:
    warnings: list[str] = []
    boss_alive = case_summary.get("required_target_alive") is True
    boss_health_percent = float(case_summary.get("required_target_health_percent", 0.0) or 0.0)
    boss_alive_high_health = (
        boss_alive
        and boss_health_percent >= 80.0
    )
    boss_alive_low_health = (
        boss_alive
        and 0.0 < boss_health_percent <= 30.0
        and int(case_summary.get("target_removed", 0) or 0) == 0
    )
    add_overrun = (
        boss_alive_high_health
        and int(case_summary.get("target_removed", 0) or 0) >= max(20, int(case_summary.get("workers_total", 0) or 0))
    )

    if boss_alive_high_health:
        warnings.append("boss_alive_high_health")
    if boss_alive_low_health:
        warnings.append("boss_alive_low_health")
    if add_overrun:
        warnings.append("add_overrun")

    return warnings


def summarize_rows(rows: Iterable[dict[str, str]]) -> dict[str, object]:
    summary: dict[str, object] = {
        "workers_ok": 0,
        "workers_total": 0,
        "deaths": 0,
        "timeouts": 0,
        "target_removed": 0,
        "required_targets_alive": 0,
        "loot": 0,
        "damage_done": 0,
        "damage_taken": 0,
        "healing_done": 0,
        "healing_received": 0,
        "not_visible": 0,
        "tiers": {},
        "roles": {},
        "cases": {},
    }
    tiers: dict[str, int] = {}
    roles: dict[str, dict[str, int]] = {}
    cases: dict[str, dict[str, object]] = {}

    for row in rows:
        case_name = row.get("__case", "")
        case_summary = None
        if case_name:
            case_summary = cases.setdefault(
                case_name,
                {
                    "workers_ok": 0,
                    "workers_total": 0,
                    "deaths": 0,
                    "timeouts": 0,
                    "target_removed": 0,
                    "required_target_alive": None,
                    "required_target_health": 0,
                    "required_target_health_percent": 0.0,
                    "loot": 0,
                    "damage_done": 0,
                    "damage_taken": 0,
                    "healing_done": 0,
                    "healing_received": 0,
                    "not_visible": 0,
                    "roles": {},
                    "warnings": [],
                    "add_overrun": False,
                    "score": 0,
                },
            )

        deaths = max(int_value(row.get("death_detected")), int_value(row.get("player_deaths")))
        target_removed = int_value(row.get("target_removed"))
        loot = int_value(row.get("loot_acquired"))
        damage_done = int_value(row.get("damage_done"))
        damage_taken = int_value(row.get("damage_taken"))
        healing_done = int_value(row.get("healing_done"))
        healing_received = int_value(row.get("healing_received"))
        not_visible = int_value(row.get("combat_not_visible_msg"))
        required_target_alive_raw = row.get("__required_target_alive", "")
        has_required_target_liveness = required_target_alive_raw != ""
        required_target_alive = required_target_alive_raw == "true"
        required_target_health = int_value(row.get("__required_target_health"))
        try:
            required_target_health_percent = float(row.get("__required_target_health_percent") or 0.0)
        except ValueError:
            required_target_health_percent = 0.0

        summary["workers_total"] = int(summary["workers_total"]) + 1
        summary["workers_ok"] = int(summary["workers_ok"]) + int(row.get("ok") == "true")
        summary["deaths"] = int(summary["deaths"]) + deaths
        summary["timeouts"] = int(summary["timeouts"]) + int_value(row.get("target_timeouts"))
        summary["target_removed"] = int(summary["target_removed"]) + target_removed
        summary["required_targets_alive"] = int(summary["required_targets_alive"]) + int(has_required_target_liveness and required_target_alive)
        summary["loot"] = int(summary["loot"]) + loot
        summary["damage_done"] = int(summary["damage_done"]) + damage_done
        summary["damage_taken"] = int(summary["damage_taken"]) + damage_taken
        summary["healing_done"] = int(summary["healing_done"]) + healing_done
        summary["healing_received"] = int(summary["healing_received"]) + healing_received
        summary["not_visible"] = int(summary["not_visible"]) + not_visible

        role = role_from_row(row)
        update_role_summary(roles.setdefault(role, new_role_summary()), row, deaths)

        if case_summary is not None:
            case_summary["workers_total"] = int(case_summary["workers_total"]) + 1
            case_summary["workers_ok"] = int(case_summary["workers_ok"]) + int(row.get("ok") == "true")
            case_summary["deaths"] = int(case_summary["deaths"]) + deaths
            case_summary["timeouts"] = int(case_summary["timeouts"]) + int_value(row.get("target_timeouts"))
            case_summary["target_removed"] = int(case_summary["target_removed"]) + target_removed
            if has_required_target_liveness:
                case_summary["required_target_alive"] = required_target_alive
                case_summary["required_target_health"] = required_target_health
                case_summary["required_target_health_percent"] = required_target_health_percent
            case_summary["loot"] = int(case_summary["loot"]) + loot
            case_summary["damage_done"] = int(case_summary["damage_done"]) + damage_done
            case_summary["damage_taken"] = int(case_summary["damage_taken"]) + damage_taken
            case_summary["healing_done"] = int(case_summary["healing_done"]) + healing_done
            case_summary["healing_received"] = int(case_summary["healing_received"]) + healing_received
            case_summary["not_visible"] = int(case_summary["not_visible"]) + not_visible
            case_roles = case_summary["roles"]
            assert isinstance(case_roles, dict)
            update_role_summary(case_roles.setdefault(role, new_role_summary()), row, deaths)

        for key, value in row.items():
            if key.startswith("loot_tier_") and value:
                tier = key.removeprefix("loot_tier_")
                tiers[tier] = tiers.get(tier, 0) + int_value(value)

    summary["tiers"] = tiers
    summary["roles"] = dict(sorted(roles.items()))
    for case_summary in cases.values():
        case_roles = case_summary["roles"]
        assert isinstance(case_roles, dict)
        case_summary["roles"] = dict(sorted(case_roles.items()))
        warnings = detect_case_warnings(case_summary)
        case_summary["warnings"] = warnings
        case_summary["add_overrun"] = "add_overrun" in warnings
        case_summary["score"] = (
            int(case_summary["target_removed"]) * 100000
            + int(case_summary["loot"]) * 5000
            + int(case_summary["damage_done"])
            + int(case_summary["healing_done"]) // 4
            - int(case_summary["deaths"]) * 10000
            - int(case_summary["timeouts"]) * 3000
            - int(case_summary["not_visible"]) * 10
            - (1000000 if case_summary["add_overrun"] else 0)
            - (50000 if "boss_alive_low_health" in warnings else 0)
        )
    summary["cases"] = dict(sorted(cases.items(), key=lambda item: int(item[1]["score"]), reverse=True))
    return summary


def read_metrics_rows(root: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for metrics_path in sorted(root.glob("*/metrics.csv")):
        boss_liveness = read_required_target_liveness(metrics_path.parent)
        first_case_row = True
        with metrics_path.open(encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                row["__case"] = metrics_path.parent.name
                if first_case_row and boss_liveness is not None:
                    row.update(boss_liveness)
                first_case_row = False
                rows.append(row)
    return rows


def read_required_target_liveness(case_dir: Path) -> dict[str, str] | None:
    path = case_dir / "boss-api.jsonl"
    if not path.exists():
        return None

    last: dict[str, object] | None = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = str(event.get("name", "") or "")
            query_name = str(event.get("query_name", "") or "")
            if not bool(event.get("found")):
                if query_name.startswith("KDAOC_TEST_"):
                    last = {
                        "isAlive": False,
                        "health": 0,
                        "healthPercent": 0.0,
                    }
                continue
            if not name.startswith("KDAOC_TEST_"):
                continue
            last = event

    if last is None:
        return None

    return {
        "__required_target_alive": "true" if bool(last.get("isAlive")) else "false",
        "__required_target_health": str(int_value(last.get("health"))),
        "__required_target_health_percent": str(last.get("healthPercent") or 0.0),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: summarize-dummy-boss-report.py REPORT_ROOT", file=sys.stderr)
        return 2

    root = Path(argv[1])
    summary = summarize_rows(read_metrics_rows(root))
    root.joinpath("boss-summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
