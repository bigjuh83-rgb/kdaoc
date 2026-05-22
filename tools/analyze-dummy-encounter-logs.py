#!/usr/bin/env python3
"""Summarize dummy encounter JSONL logs.

The movement trace tells us where a dummy moved.  This analyzer focuses on
combat intent: target visibility, attack toggles, rescue/backoff reasons,
deaths, server combat messages, and loot.
"""

from __future__ import annotations

import argparse
import glob
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


def expand_paths(patterns: list[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        matches = [Path(match) for match in glob.glob(pattern)]
        if not matches:
            candidate = Path(pattern)
            if candidate.exists():
                matches = [candidate]
        for match in matches:
            if match.is_file() and match not in seen:
                seen.add(match)
                paths.append(match)
    return sorted(paths)


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_name(value: Any) -> str:
    return str(value or "").strip().lower()


def read_events(paths: list[Path]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in paths:
        with path.open(encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    events.append({"event": "malformed_json", "source": str(path), "line": line_no})
                    continue
                if isinstance(event, dict):
                    event.setdefault("source", str(path))
                    events.append(event)
    return events


def analyze(events: list[dict[str, Any]]) -> dict[str, Any]:
    event_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    user_counts: Counter[str] = Counter()
    attack_reasons: Counter[str] = Counter()
    attack_enabled: Counter[str] = Counter()
    server_categories: Counter[str] = Counter()
    loot_tiers: Counter[str] = Counter()
    target_visibility: Counter[str] = Counter()
    backoff_counts: Counter[str] = Counter()
    per_user: dict[str, Counter[str]] = defaultdict(Counter)
    max_distance_by_target: dict[str, float] = {}
    last_target_health: dict[str, dict[str, Any]] = {}
    min_target_health: dict[str, dict[str, Any]] = {}
    server_snapshots: list[dict[str, Any]] = []
    death_events: list[dict[str, Any]] = []

    for event in events:
        event_name = str(event.get("event", "unknown"))
        event_counts[event_name] += 1
        role = str(event.get("role", "") or "unknown")
        user = str(event.get("username", "") or event.get("character", "") or "unknown")
        if event_name != "boss_api_sample":
            role_counts[role] += 1
            user_counts[user] += 1
            per_user[user][event_name] += 1

        visible = bool(event.get("target_visible", False))
        target_visibility["visible" if visible else "not_visible"] += 1

        target_name = str(event.get("target_name", "") or event.get("leader_target_name", "") or "")
        if target_name:
            distance = safe_float(event.get("target_distance"), -1.0)
            if distance >= 0:
                max_distance_by_target[target_name] = max(max_distance_by_target.get(target_name, 0.0), distance)

        if event_name == "attack_decision":
            reason = str(event.get("reason", "unknown") or "unknown")
            attack_reasons[reason] += 1
            attack_enabled["on" if event.get("attack_enabled") else "off"] += 1

        if event_name == "server_message":
            for category in event.get("categories", []) or []:
                server_categories[str(category)] += 1
            tier = str(event.get("loot_tier", "") or "")
            if tier:
                loot_tiers[tier] += 1

        for key in (
            "party_melee_survival_backoff",
            "boss_hazard_backoff",
            "party_focus_target_backoff",
            "party_focus_pressure_backoff",
            "party_boss_melee_backoff",
            "party_survival_backoff",
            "tactical_backoff",
        ):
            if event.get(key):
                backoff_counts[key] += 1

        if event_name == "boss_api_sample" and target_name:
            if isinstance(event.get("snapshot"), dict):
                server_snapshots.append(event)

            health_percent = event.get("healthPercent", event.get("health_percent"))
            last_target_health[target_name] = {
                "health_percent": health_percent,
                "health": event.get("health"),
                "max_health": event.get("maxHealth", event.get("max_health")),
                "is_alive": event.get("isAlive", event.get("is_alive")),
                "in_combat": event.get("inCombat", event.get("in_combat")),
                "target": event.get("target", ""),
                "elapsed": event.get("elapsed", 0),
            }
            if target_name not in min_target_health or safe_float(health_percent, 101.0) < safe_float(
                min_target_health[target_name].get("health_percent"),
                101.0,
            ):
                min_target_health[target_name] = dict(last_target_health[target_name])

        if event_name == "death_detected":
            death_events.append(event)

    server_snapshots.sort(key=lambda event: safe_float(event.get("elapsed"), 0.0))
    death_diagnosis: list[dict[str, Any]] = []
    death_causes: Counter[str] = Counter()

    for death in sorted(death_events, key=lambda event: safe_float(event.get("elapsed"), 0.0)):
        death_elapsed = safe_float(death.get("elapsed"), 0.0)
        character = str(death.get("character") or death.get("username") or "")
        character_key = normalize_name(character)
        nearest_snapshot = None
        if server_snapshots:
            nearest_snapshot = min(
                server_snapshots,
                key=lambda event: abs(safe_float(event.get("elapsed"), 0.0) - death_elapsed),
            )

        diagnosis = {
            "elapsed": death_elapsed,
            "character": character,
            "username": death.get("username", ""),
            "role": death.get("role", ""),
            "active_tank": death.get("active_tank_name", ""),
            "active_tank_health_percent": death.get("active_tank_health_percent", 0),
            "cause": "unknown",
            "snapshot_elapsed": None,
            "boss_health_percent": None,
            "boss_target": "",
            "player_health_percent": None,
            "player_distance": None,
            "attackers": [],
        }

        if nearest_snapshot is not None:
            snapshot = nearest_snapshot.get("snapshot") or {}
            target = snapshot.get("target") if isinstance(snapshot, dict) else {}
            players = snapshot.get("players", []) if isinstance(snapshot, dict) else []
            npcs = snapshot.get("npcs", []) if isinstance(snapshot, dict) else []
            boss_target = str((target or {}).get("target", "") or nearest_snapshot.get("target", "") or "")
            player = next(
                (
                    item
                    for item in players
                    if isinstance(item, dict) and normalize_name(item.get("name")) == character_key
                ),
                None,
            )
            attackers = [
                {
                    "name": item.get("name", ""),
                    "level": item.get("level", 0),
                    "distance": item.get("distance", 0),
                    "health_percent": item.get("healthPercent", item.get("health_percent")),
                    "target": item.get("targetName", item.get("target", "")),
                }
                for item in npcs
                if isinstance(item, dict) and normalize_name(item.get("targetName", item.get("target", ""))) == character_key
            ]

            diagnosis.update(
                {
                    "snapshot_elapsed": nearest_snapshot.get("elapsed"),
                    "boss_health_percent": (target or {}).get(
                        "healthPercent",
                        nearest_snapshot.get("healthPercent", nearest_snapshot.get("health_percent")),
                    ),
                    "boss_target": boss_target,
                    "player_health_percent": (player or {}).get("healthPercent", (player or {}).get("health_percent")),
                    "player_distance": (player or {}).get("distance"),
                    "attackers": attackers,
                }
            )

            if normalize_name(boss_target) == character_key:
                diagnosis["cause"] = "boss_focus"
            elif attackers:
                diagnosis["cause"] = "add_focus"
            else:
                diagnosis["cause"] = "unknown_snapshot"

        death_causes[str(diagnosis["cause"])] += 1
        death_diagnosis.append(diagnosis)

    users = {
        user: {
            "events": sum(counter.values()),
            "deaths": counter.get("death_detected", 0),
            "combat_starts": counter.get("combat_start", 0),
            "combat_finishes": counter.get("combat_finish", 0),
            "target_timeouts": counter.get("target_timeout_rejected", 0)
            + counter.get("target_timeout_preserved", 0),
            "target_removed": counter.get("required_target_complete", 0)
            + counter.get("target_object_removed", 0),
            "server_messages": counter.get("server_message", 0),
        }
        for user, counter in sorted(per_user.items())
    }

    hints: list[str] = []
    if event_counts.get("combat_start", 0) == 0:
        hints.append("combat_start가 없어서 타겟 획득이나 보스 발견 단계부터 의심해야 합니다.")
    if attack_enabled.get("on", 0) == 0 and event_counts.get("combat_start", 0) > 0:
        hints.append("combat_start는 있지만 attack on이 없어 사거리/시야/백오프/페이스 판단을 먼저 봐야 합니다.")
    if server_categories.get("out_of_range", 0) > 0:
        hints.append("out_of_range 메시지가 있어 추적 거리나 stick/face 재시도 간격을 확인해야 합니다.")
    if server_categories.get("not_visible", 0) > 0:
        hints.append("not_visible 메시지가 있어 시야각, 지형, 대상 object 보존 로직을 확인해야 합니다.")
    if event_counts.get("death_detected", 0) > 0:
        hints.append("사망 이벤트가 있어 탱커 어그로, 힐 우선순위, 구조 타겟 전환을 같이 봐야 합니다.")
    if (
        event_counts.get("target_removed_preserved", 0) > event_counts.get("required_target_complete", 0)
        and event_counts.get("required_target_complete", 0) == 0
    ):
        hints.append("target_removed_preserved가 완료보다 많아 object 제거 보존이 과하거나 루팅/종료 관측이 늦을 수 있습니다.")

    return {
        "events_total": len(events),
        "event_counts": dict(event_counts),
        "role_counts": dict(role_counts),
        "users_total": len(user_counts),
        "users": users,
        "attack": {
            "enabled_counts": dict(attack_enabled),
            "reasons": dict(attack_reasons),
        },
        "target_visibility": dict(target_visibility),
        "server_message_categories": dict(server_categories),
        "loot_tiers": dict(loot_tiers),
        "backoffs": dict(backoff_counts),
        "max_distance_by_target": {key: round(value, 2) for key, value in sorted(max_distance_by_target.items())},
        "last_target_health": last_target_health,
        "min_target_health": min_target_health,
        "death_causes": dict(death_causes),
        "death_diagnosis": death_diagnosis,
        "hints": hints,
    }


def write_report(summary: dict[str, Any], output: Path) -> None:
    lines = [
        "# Dummy Encounter Analysis",
        "",
        f"- Events: {summary['events_total']}",
        f"- Users: {summary['users_total']}",
        f"- Attack on/off: {summary['attack']['enabled_counts']}",
        f"- Target visibility: {summary['target_visibility']}",
        f"- Server categories: {summary['server_message_categories']}",
        f"- Loot tiers: {summary['loot_tiers']}",
        "",
        "## Event Counts",
        "",
    ]
    for name, count in sorted(summary["event_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    lines.extend(["", "## Attack Reasons", ""])
    for name, count in sorted(summary["attack"]["reasons"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {name}: {count}")

    if summary["last_target_health"]:
        lines.extend(["", "## Last Boss API Health", ""])
        for name, health in sorted(summary["last_target_health"].items()):
            lines.append(f"- {name}: {health}")

    if summary.get("death_diagnosis"):
        lines.extend(["", "## Death Diagnosis", ""])
        lines.append(f"- Causes: {summary.get('death_causes', {})}")
        for death in summary["death_diagnosis"][:20]:
            lines.append(
                "- "
                f"{death.get('elapsed')}s {death.get('character')} "
                f"({death.get('role')}): {death.get('cause')}, "
                f"boss_target={death.get('boss_target')}, "
                f"boss_hp={death.get('boss_health_percent')}, "
                f"player_hp={death.get('player_health_percent')}, "
                f"distance={death.get('player_distance')}, "
                f"attackers={death.get('attackers')}"
            )

    if summary["min_target_health"]:
        lines.extend(["", "## Minimum Boss API Health", ""])
        for name, health in sorted(summary["min_target_health"].items()):
            lines.append(f"- {name}: {health}")

    if summary["hints"]:
        lines.extend(["", "## Diagnosis Hints", ""])
        for hint in summary["hints"]:
            lines.append(f"- {hint}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("logs", nargs="+", help="encounter JSONL files or glob patterns")
    parser.add_argument("--json-out", default="", help="write machine-readable summary JSON")
    parser.add_argument("--report-md", default="", help="write markdown summary")
    args = parser.parse_args()

    paths = expand_paths(args.logs)
    if not paths:
        raise SystemExit("No encounter logs matched.")

    summary = analyze(read_events(paths))
    summary["files"] = [str(path) for path in paths]

    if args.json_out:
        output = Path(args.json_out)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.report_md:
        write_report(summary, Path(args.report_md))
    if not args.json_out and not args.report_md:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
