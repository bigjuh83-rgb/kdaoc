#!/usr/bin/env python3
"""Preflight audit for 1-50 dummy growth routes.

This does not change dummy behavior or grant items.  It checks whether the
configured growth route plan has plausible hunting targets before long runs.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def load_growth_module():
    module_path = TOOLS / "dummy_growth_suite.py"
    spec = importlib.util.spec_from_file_location("run_dummy_growth_suite", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


growth = load_growth_module()


@dataclass(frozen=True)
class IndexedMob:
    realm: str
    party_size: int
    player_level: int
    target_min: int
    target_ideal: int
    target_max: int
    name: str
    mob_level: int
    mob_count: int
    x: int
    y: int
    z: int
    nearest_teleporter: str
    score: float


def as_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value or "").strip()))
    except ValueError:
        return default


def as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value or "").strip())
    except ValueError:
        return default


def normalize_name(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def split_tokens(value: str) -> list[str]:
    return [normalize_name(part) for part in str(value or "").split(",") if normalize_name(part)]


def load_index(path: Path) -> list[IndexedMob]:
    rows: list[IndexedMob] = []
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append(
                IndexedMob(
                    realm=normalize_name(row.get("realm", "")),
                    party_size=as_int(row.get("party_size")),
                    player_level=as_int(row.get("player_level")),
                    target_min=as_int(row.get("target_min")),
                    target_ideal=as_int(row.get("target_ideal")),
                    target_max=as_int(row.get("target_max")),
                    name=normalize_name(row.get("name", "")),
                    mob_level=as_int(row.get("mob_level")),
                    mob_count=as_int(row.get("mob_count")),
                    x=as_int(row.get("x")),
                    y=as_int(row.get("y")),
                    z=as_int(row.get("z")),
                    nearest_teleporter=str(row.get("nearest_teleporter", "") or "").strip(),
                    score=as_float(row.get("score")),
                )
            )
    return rows


def route_distance(route: Any, mob: IndexedMob) -> float:
    return math.hypot(int(route.x) - mob.x, int(route.y) - mob.y)


def name_matches(name: str, tokens: list[str]) -> bool:
    normalized = normalize_name(name)
    return bool(not tokens or any(token in normalized for token in tokens))


def token_exact_matches(name: str, token: str) -> bool:
    return normalize_name(name) == normalize_name(token)


def candidate_mobs(
    rows: list[IndexedMob],
    *,
    realm: str,
    party_size: int,
    level: int,
) -> list[IndexedMob]:
    exact = [row for row in rows if row.realm == realm and row.party_size == party_size and row.player_level == level]
    if exact:
        return exact
    if party_size > 0:
        fallback = [row for row in rows if row.realm == realm and row.party_size == 0 and row.player_level == level]
        if fallback:
            return fallback
    return []


def severity_from_issues(issues: list[str]) -> str:
    if any(issue.startswith(("NO_", "STRICT_", "TELEPORT_UNKNOWN")) for issue in issues):
        return "critical"
    if any(issue.startswith(("LOW_", "PREFER_", "ROUTE_")) for issue in issues):
        return "warning"
    return "ok"


def audit_one(args: argparse.Namespace, rows: list[IndexedMob], realm_key: str, party_size: int, level: int) -> dict[str, Any]:
    realm = growth.REALMS[realm_key]
    growth_args = SimpleNamespace(
        growth_hunting_index=str(args.growth_hunting_index),
        growth_route_case_index=0,
        max_target_distance=args.max_target_distance,
        target_home_max_distance=args.target_home_max_distance,
        combat_home_leash_distance=args.combat_home_leash_distance,
        segment_seconds=args.segment_seconds,
        ground_z_offset=0,
    )
    route = growth.select_growth_route_point(growth_args, realm, level, party_size)
    min_target, ideal_target, max_delta = growth.target_levels(level, party_size, realm_key)
    max_target = growth.target_max_level(level, ideal_target, max_delta)
    max_distance = growth.growth_max_target_distance(growth_args, level, party_size, realm_key)
    z_delta = growth.growth_hunter_target_max_ground_z_delta(level, party_size, realm_key)
    strict_name = growth.strict_route_target_name(route, level, party_size, realm_key)
    prefer_tokens = split_tokens(route.prefer)
    avoid_tokens = split_tokens(route.avoid)
    strict_tokens = split_tokens(strict_name)
    index_candidates = candidate_mobs(rows, realm=realm_key, party_size=party_size, level=level)

    level_ok = [mob for mob in index_candidates if min_target <= mob.mob_level <= max_target]
    distance_ok = [mob for mob in level_ok if route_distance(route, mob) <= max_distance]
    prefer_ok = [mob for mob in distance_ok if name_matches(mob.name, prefer_tokens)]
    strict_ok = [mob for mob in distance_ok if name_matches(mob.name, strict_tokens)]
    avoided_hits = [mob for mob in distance_ok if avoid_tokens and name_matches(mob.name, avoid_tokens)]
    exact_preferred = [
        mob
        for mob in distance_ok
        if any(token_exact_matches(mob.name, token) for token in prefer_tokens)
    ]

    selected_name = normalize_name(route.prefer.split(",", 1)[0] if route.prefer else "")
    selected_matches = [mob for mob in distance_ok if mob.name == selected_name] if selected_name else []

    issues: list[str] = []
    if route.teleport_destination:
        known_destinations = {name for name, *_ in growth.TELEPORT_DESTINATIONS.get(realm_key, ())}
        if route.teleport_destination not in known_destinations:
            issues.append("TELEPORT_UNKNOWN")
    if not index_candidates:
        issues.append("NO_INDEX_ROWS")
    elif not level_ok:
        issues.append("NO_LEVEL_MATCH")
    elif not distance_ok:
        issues.append("NO_DISTANCE_MATCH")
    if strict_tokens and not strict_ok:
        issues.append("STRICT_TARGET_ZERO_MATCH")
    if prefer_tokens and not prefer_ok:
        issues.append("PREFER_TARGET_ZERO_MATCH")
    if prefer_tokens and not exact_preferred:
        issues.append("PREFER_EXACT_ZERO_MATCH")
    if selected_name and not selected_matches:
        issues.append("FIRST_PREFERRED_ZERO_MATCH")
    if distance_ok and len(distance_ok) < args.min_candidate_count:
        issues.append("LOW_DISTANCE_CANDIDATES")
    if selected_matches and sum(mob.mob_count for mob in selected_matches) < args.min_mob_count:
        issues.append("LOW_FIRST_PREFERRED_MOB_COUNT")
    if avoided_hits and len(avoided_hits) == len(distance_ok):
        issues.append("ROUTE_ONLY_AVOIDED_TARGETS")

    nearest = sorted(distance_ok, key=lambda mob: (route_distance(route, mob), -mob.mob_count))[:5]
    return {
        "realm": realm_key,
        "party_size": party_size,
        "level": level,
        "severity": severity_from_issues(issues),
        "issues": ";".join(issues),
        "route_x": route.x,
        "route_y": route.y,
        "route_z": route.z,
        "teleport_destination": route.teleport_destination,
        "prefer": route.prefer,
        "avoid": route.avoid,
        "strict_target": strict_name,
        "min_target": min_target,
        "ideal_target": ideal_target,
        "max_target": max_target,
        "max_distance": max_distance,
        "z_delta": z_delta,
        "index_candidates": len(index_candidates),
        "level_matches": len(level_ok),
        "distance_matches": len(distance_ok),
        "prefer_matches": len(prefer_ok),
        "strict_matches": len(strict_ok),
        "first_preferred_matches": len(selected_matches),
        "first_preferred_mob_count": sum(mob.mob_count for mob in selected_matches),
        "nearest_candidates": " | ".join(
            f"{mob.name}:L{mob.mob_level}:n{mob.mob_count}:d{int(route_distance(route, mob))}"
            for mob in nearest
        ),
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "severity",
        "issues",
        "realm",
        "party_size",
        "level",
        "route_x",
        "route_y",
        "route_z",
        "teleport_destination",
        "prefer",
        "avoid",
        "strict_target",
        "min_target",
        "ideal_target",
        "max_target",
        "max_distance",
        "z_delta",
        "index_candidates",
        "level_matches",
        "distance_matches",
        "prefer_matches",
        "strict_matches",
        "first_preferred_matches",
        "first_preferred_mob_count",
        "nearest_candidates",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    critical = [row for row in rows if row["severity"] == "critical"]
    warning = [row for row in rows if row["severity"] == "warning"]
    with path.open("w", encoding="utf-8") as handle:
        handle.write("# Preservice Growth Readiness Audit\n\n")
        handle.write(f"- Total checks: `{len(rows)}`\n")
        handle.write(f"- Critical: `{len(critical)}`\n")
        handle.write(f"- Warning: `{len(warning)}`\n\n")
        handle.write("## Critical / Warning Rows\n\n")
        handle.write("| Severity | Realm | Party | Level | Issues | Prefer | Strict | Matches | Nearest |\n")
        handle.write("| --- | --- | ---: | ---: | --- | --- | --- | ---: | --- |\n")
        for row in critical + warning:
            handle.write(
                "| {severity} | {realm} | {party_size} | {level} | `{issues}` | `{prefer}` | `{strict_target}` | {distance_matches} | {nearest_candidates} |\n".format(
                    **row
                )
            )


def parse_csv_ints(value: str) -> list[int]:
    return [int(part.strip()) for part in str(value or "").split(",") if part.strip()]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--growth-hunting-index", required=True, type=Path)
    parser.add_argument("--realms", default="alb,mid,hib")
    parser.add_argument("--party-sizes", default="1,2,4,8")
    parser.add_argument("--min-level", type=int, default=1)
    parser.add_argument("--max-level", type=int, default=50)
    parser.add_argument("--output-csv", type=Path, default=Path("test-output/preservice-growth-readiness-audit.csv"))
    parser.add_argument("--output-md", type=Path, default=Path("test-output/preservice-growth-readiness-audit.md"))
    parser.add_argument("--max-target-distance", type=float, default=2200.0)
    parser.add_argument("--target-home-max-distance", type=float, default=1400.0)
    parser.add_argument("--combat-home-leash-distance", type=float, default=1200.0)
    parser.add_argument("--segment-seconds", type=int, default=150)
    parser.add_argument("--min-candidate-count", type=int, default=2)
    parser.add_argument("--min-mob-count", type=int, default=3)
    parser.add_argument("--fail-on-critical", action=argparse.BooleanOptionalAction, default=False)
    args = parser.parse_args(argv)

    rows = load_index(args.growth_hunting_index)
    audits: list[dict[str, Any]] = []
    for realm_key in [part.strip().lower() for part in args.realms.split(",") if part.strip()]:
        if realm_key not in growth.REALMS:
            raise SystemExit(f"unknown realm: {realm_key}")
        for party_size in parse_csv_ints(args.party_sizes):
            for level in range(args.min_level, args.max_level + 1):
                audits.append(audit_one(args, rows, realm_key, party_size, level))

    write_csv(args.output_csv, audits)
    write_markdown(args.output_md, audits)
    critical = sum(1 for row in audits if row["severity"] == "critical")
    warning = sum(1 for row in audits if row["severity"] == "warning")
    print(f"readiness audit written: {args.output_csv}")
    print(f"readiness report written: {args.output_md}")
    print(f"checks={len(audits)} critical={critical} warning={warning}")
    return 1 if args.fail_on_critical and critical else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
