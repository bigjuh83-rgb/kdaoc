#!/usr/bin/env python3
"""Smoke-check live companion personality behavior profiles."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "tools" / "dummy-companion-service.py"
BEHAVIOR_PATH = ROOT / "tools" / "behavior-dummy-client.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def flag_values(flags: list[str]) -> dict[str, float | str | bool]:
    values: dict[str, float | str | bool] = {}
    index = 0
    while index < len(flags):
        key = flags[index]
        if not key.startswith("--"):
            index += 1
            continue
        name = key[2:].replace("-", "_")
        if index + 1 >= len(flags) or flags[index + 1].startswith("--"):
            values[name] = True
            index += 1
            continue
        raw = flags[index + 1]
        try:
            values[name] = float(raw)
        except ValueError:
            values[name] = raw
        index += 2
    return values


def default_role_for_personality(personality: str) -> tuple[str, str]:
    if personality in {"calm_support"}:
        return "healer", "healer-support"
    if personality in {"steady_protector", "bold_vanguard", "loyal_guardian", "reckless_berserker"}:
        return "tank", "melee-basic"
    if personality in {"cautious_scout", "wary_survivor", "lazy_veteran"}:
        return "fill", "hybrid"
    return "dps", "caster-basic"


def build_rows() -> list[dict[str, Any]]:
    service = load_module(SERVICE_PATH, "dummy_companion_service_for_personality_matrix")
    behavior = load_module(BEHAVIOR_PATH, "behavior_dummy_client_for_personality_matrix")

    rows: list[dict[str, Any]] = []
    for personality in behavior.COMPANION_PERSONALITIES:
        role, action_rotation = default_role_for_personality(personality)
        flags = service.companion_personality_behavior_flags(personality, role, action_rotation)
        values = flag_values(flags)
        rows.append(
            {
                "personality": personality,
                "role": role,
                "action_rotation": action_rotation,
                "flags": flags,
                "values": values,
                "signature": tuple(sorted(values.items())),
            }
        )
    return rows


def build_payload() -> dict[str, Any]:
    rows = build_rows()
    signatures = {tuple(row["signature"]) for row in rows}
    serializable_rows = []
    for row in rows:
        serializable = dict(row)
        serializable["signature"] = [list(item) for item in row["signature"]]
        serializable_rows.append(serializable)
    return {
        "count": len(rows),
        "unique_signatures": len(signatures),
        "rows": serializable_rows,
    }


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rows = payload["rows"]
    if payload["count"] != 12:
        errors.append(f"expected 12 personalities, got {payload['count']}")
    if payload["unique_signatures"] != payload["count"]:
        errors.append("personality behavior signatures must be distinct")
    for row in rows:
        if not row["values"]:
            errors.append(f"{row['personality']} has no behavior values")
    return errors


def print_table(payload: dict[str, Any]) -> None:
    print("personality role rotation attack_delay flee_hp pressure_hp follow_step skill combat")
    for row in payload["rows"]:
        values = row["values"]
        print(
            row["personality"],
            row["role"],
            row["action_rotation"],
            values.get("party_assist_attack_delay", "-"),
            values.get("flee_health_percent", "-"),
            values.get("flee_pressure_health_percent", "-"),
            values.get("party_follow_step", "-"),
            values.get("skill_interval", "-"),
            values.get("combat_interval", "-"),
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="print the matrix as JSON")
    args = parser.parse_args(argv)

    payload = build_payload()
    errors = validate_payload(payload)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print_table(payload)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
