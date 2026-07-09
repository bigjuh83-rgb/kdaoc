#!/usr/bin/env python3
"""Rank DB-backed hunting ground candidates for dummy growth routes."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import math
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GROWTH_SUITE = ROOT / "tools" / "dummy_growth_suite.py"


def load_growth_suite():
    spec = importlib.util.spec_from_file_location("dummy_growth_suite_for_hunting_ground_analysis", GROWTH_SUITE)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {GROWTH_SUITE}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


growth = load_growth_suite()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mysql-bin", default=growth.resolve_mysql_bin(None))
    parser.add_argument("--db-host", default="127.0.0.1")
    parser.add_argument("--db-port", type=int, default=3306)
    parser.add_argument("--db-name", default="opendaoc")
    parser.add_argument("--db-user", default="root")
    parser.add_argument("--db-password", default=growth.read_serverconfig_password())
    parser.add_argument("--realms", default="alb,mid,hib")
    parser.add_argument("--party-size", type=int, default=1)
    parser.add_argument("--party-sizes", default="", help="comma-separated party sizes to index; overrides --party-size")
    parser.add_argument("--level-min", type=int, default=1)
    parser.add_argument("--level-max", type=int, default=50)
    parser.add_argument("--min-cluster-count", type=int, default=2)
    parser.add_argument("--cluster-size", type=int, default=20000)
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument(
        "--route-top",
        type=int,
        default=0,
        help="candidate rows to keep per route checkpoint; defaults to --top",
    )
    parser.add_argument(
        "--live-preflight",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="filter candidates through the same live route preflight used by the growth suite",
    )
    parser.add_argument(
        "--live-preflight-filter",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="when --live-preflight is enabled, omit candidates that fail live preflight",
    )
    parser.add_argument("--live-api-url", default="", help="base API URL such as http://192.168.0.4:5000")
    parser.add_argument("--api-host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument(
        "--live-preflight-current-level",
        type=int,
        default=0,
        help="override the runtime current level used by live preflight checks",
    )
    parser.add_argument("--live-preflight-timeout", type=float, default=1.5)
    parser.add_argument("--live-preflight-radius", type=float, default=0.0)
    parser.add_argument("--live-preflight-limit", type=int, default=3)
    parser.add_argument("--live-preflight-min-available-targets", type=int, default=0)
    parser.add_argument("--live-preflight-hazard-radius", type=float, default=2500.0)
    parser.add_argument("--live-preflight-hazard-limit", type=int, default=3)
    parser.add_argument("--live-preflight-hazard-token-limit", type=int, default=12)
    parser.add_argument("--live-preflight-log-dir", default="")
    parser.add_argument("--output", default="tools/test-output/dummy-growth-hunting-ground-candidates.csv")
    parser.add_argument("--route-output", default="tools/test-output/dummy-growth-route-recommendations.csv")
    return parser.parse_args()


def nearest_teleporter(realm_key: str, x: int, y: int) -> tuple[str, float]:
    destinations = list(growth.TELEPORT_DESTINATIONS.get(realm_key, ()))
    realm = growth.REALMS.get(realm_key)
    if realm is not None:
        destinations.append(("Bind Start", realm.start[0], realm.start[1], realm.start[2]))
    if not destinations:
        return "", 0.0
    name, tx, ty, _tz = min(destinations, key=lambda item: math.hypot(item[1] - x, item[2] - y))
    return str(name), math.hypot(tx - x, ty - y)


def score_candidate(
    *,
    target_level: int,
    candidate_level: int,
    count: int,
    teleporter_distance: float,
    neutral_count: int = 0,
) -> float:
    level_penalty = abs(candidate_level - target_level) * 500.0
    distance_penalty = teleporter_distance / 15.0
    density_bonus = min(count, 40) * 30.0
    neutral_bonus = min(neutral_count, 40) * 80.0
    hostile_penalty = max(0, count - neutral_count) * 90.0
    return density_bonus + neutral_bonus - hostile_penalty - distance_penalty - level_penalty


def cluster_size(args: argparse.Namespace) -> int:
    return max(1000, int(getattr(args, "cluster_size", 20000) or 20000))


def analyzer_target_plan(level: int, party_size: int, realm_key: str) -> tuple[int, int, int]:
    if int(party_size or 0) > 1:
        return growth.growth_party_carry_target_plan_for_realm(level, party_size, realm_key)
    return growth.target_levels(level, party_size, realm_key)


def candidate_rows(args: argparse.Namespace, realm_key: str, level: int, party_size: int | None = None) -> list[dict[str, object]]:
    realm = growth.REALMS[realm_key]
    effective_party_size = int(args.party_size if party_size is None else party_size)
    min_target, ideal_target, max_delta = analyzer_target_plan(level, effective_party_size, realm_key)
    max_target = growth.target_max_level(level, ideal_target, max_delta)
    query_min = min_target
    query_max = max_target
    if query_max <= 0:
        query_min = 1
        query_max = min(2, max(1, level + 1))
        ideal_target = query_min
    cluster = cluster_size(args)
    sql = f"""
SELECT Name, Level,
       FLOOR(X / {cluster}) AS grid_x, FLOOR(Y / {cluster}) AS grid_y,
       COUNT(*) AS mob_count,
       ROUND(AVG(X)) AS avg_x, ROUND(AVG(Y)) AS avg_y, ROUND(AVG(Z)) AS avg_z,
       SUM(CASE WHEN AggroLevel = 0 OR AggroRange = 0 THEN 1 ELSE 0 END) AS neutral_count,
       MIN(AggroLevel) AS min_aggro, MAX(AggroLevel) AS max_aggro,
       MAX(AggroRange) AS max_aggro_range,
       MAX(X) - MIN(X) AS span_x, MAX(Y) - MIN(Y) AS span_y
FROM Mob
WHERE Region = {realm.region}
  AND Level BETWEEN {query_min} AND {query_max}
  AND Realm <> {realm.realm_id}
  AND LOWER(Name) NOT LIKE '%dummy%'
  AND LOWER(Name) NOT LIKE 'total:%'
GROUP BY Name, Level, grid_x, grid_y
HAVING mob_count >= {max(1, args.min_cluster_count)}
ORDER BY ABS(CAST(Level AS SIGNED) - {ideal_target}), neutral_count DESC, mob_count DESC
LIMIT {max(100, args.top * 20)};
"""
    raw = growth.run_mysql(args, sql)
    rows: list[dict[str, object]] = []
    for row in csv.DictReader(raw.splitlines(), delimiter="\t"):
        x = int(float(row["avg_x"]))
        y = int(float(row["avg_y"]))
        z = int(float(row["avg_z"]))
        candidate_level = int(row["Level"])
        count = int(row["mob_count"])
        name = str(row["Name"] or "").strip()
        avoid_text = growth.growth_hunting_index_avoid_targets(realm_key, level, effective_party_size)
        if growth.target_name_matches_any(name, growth.preferred_target_tokens(avoid_text)) and not (
            growth.growth_hunting_index_allows_static_avoid_candidate(
                args,
                realm_key=realm_key,
                level=level,
                party_size=effective_party_size,
                name=name,
                mob_level=candidate_level,
                mob_count=count,
            )
        ):
            continue
        neutral_count = int(row.get("neutral_count") or 0)
        teleporter, teleporter_distance = nearest_teleporter(realm_key, x, y)
        score = score_candidate(
            target_level=ideal_target,
            candidate_level=candidate_level,
            count=count,
            teleporter_distance=teleporter_distance,
            neutral_count=neutral_count,
        )
        rows.append(
            {
                "realm": realm_key,
                "party_size": effective_party_size,
                "player_level": level,
                "target_min": min_target,
                "target_ideal": ideal_target,
                "target_max": max_target,
                "name": name,
                "mob_level": candidate_level,
                "mob_count": count,
                "x": x,
                "y": y,
                "z": z,
                "neutral_count": neutral_count,
                "min_aggro": int(row["min_aggro"]),
                "max_aggro": int(row.get("max_aggro") or row["min_aggro"]),
                "max_aggro_range": int(row["max_aggro_range"]),
                "nearest_teleporter": teleporter,
                "teleporter_distance": int(round(teleporter_distance)),
                "score": round(score, 3),
            }
        )
    rows.sort(key=lambda item: float(item["score"]), reverse=True)
    return rows[: args.top]


def live_preflight_args(
    args: argparse.Namespace,
    *,
    player_level: int,
    party_size: int,
    realm_key: str,
) -> argparse.Namespace:
    api_base = str(getattr(args, "live_api_url", "") or "").strip()
    if not api_base:
        api_base = f"http://{getattr(args, 'api_host', '127.0.0.1')}:{int(getattr(args, 'api_port', 5000) or 5000)}"
    target_plan = analyzer_target_plan(player_level, party_size, realm_key)
    return argparse.Namespace(
        dry_run=False,
        host=str(getattr(args, "api_host", "127.0.0.1") or "127.0.0.1"),
        api_port=int(getattr(args, "api_port", 5000) or 5000),
        nav_api_url=api_base.rstrip("/"),
        run_dir=str(getattr(args, "live_preflight_log_dir", "") or ""),
        max_target_distance=2200.0,
        target_home_max_distance=1400.0,
        combat_home_leash_distance=1200.0,
        ground_z_offset=0,
        growth_fast_travel="route-home",
        growth_route_level_is_carry_target=int(party_size or 0) > 1,
        growth_route_player_level=max(1, int(player_level or 1)),
        growth_target_level_override=max(1, int(player_level or 1)),
        growth_target_plan_override=target_plan,
        growth_equip_party_carry_gear=False,
        growth_party_carry_count=-1,
        growth_party_carry_level_offset=12,
        growth_allow_lower_xp_target_plan=False,
        growth_allow_lower_xp_gear_farm=True,
        growth_failure_target_memory=False,
        growth_runtime_failure_memory_csv="",
        growth_current_segment_index=0,
        growth_route_preflight=True,
        growth_route_preflight_anchor=True,
        growth_route_preflight_timeout=float(getattr(args, "live_preflight_timeout", 1.5) or 1.5),
        growth_route_preflight_radius=float(getattr(args, "live_preflight_radius", 0.0) or 0.0),
        growth_route_preflight_low_solo_radius=2500.0,
        growth_route_preflight_limit=int(getattr(args, "live_preflight_limit", 3) or 3),
        growth_route_preflight_min_available_targets=int(
            getattr(args, "live_preflight_min_available_targets", 0) or 0
        ),
        growth_route_preflight_hazard_radius=float(
            getattr(args, "live_preflight_hazard_radius", 2500.0) or 0.0
        ),
        growth_route_preflight_hazard_limit=int(getattr(args, "live_preflight_hazard_limit", 3) or 3),
        growth_route_preflight_hazard_token_limit=int(
            getattr(args, "live_preflight_hazard_token_limit", 12) or 0
        ),
    )


def route_from_candidate_row(row: dict[str, object]) -> object:
    realm_key = str(row.get("realm", "") or "").strip().lower()
    level = int(row.get("player_level", 0) or 0)
    party_size = int(row.get("party_size", 0) or 0)
    avoid_text = growth.growth_hunting_index_avoid_targets(realm_key, level, party_size)
    return growth.route_point(
        level,
        int(row.get("x", 0) or 0),
        int(row.get("y", 0) or 0),
        int(row.get("z", 0) or 0),
        str(row.get("name", "") or "").strip(),
        avoid_text,
        str(row.get("nearest_teleporter", "") or "").strip(),
        source="hunting-index",
        mob_level=int(row.get("mob_level", 0) or 0),
        mob_count=int(row.get("mob_count", 0) or 0),
    )


def apply_live_preflight_to_row(
    args: argparse.Namespace,
    row: dict[str, object],
) -> dict[str, object] | None:
    if not bool(getattr(args, "live_preflight", False)):
        return row
    realm_key = str(row.get("realm", "") or "").strip().lower()
    realm = growth.REALMS.get(realm_key)
    if realm is None:
        row["live_preflight_status"] = "unknown_realm"
        return None if bool(getattr(args, "live_preflight_filter", True)) else row
    row_level = int(row.get("player_level", 0) or 0)
    level = int(getattr(args, "live_preflight_current_level", 0) or row_level)
    party_size = int(row.get("party_size", 0) or 0)
    preflight_args = live_preflight_args(args, player_level=level, party_size=party_size, realm_key=realm_key)
    route = route_from_candidate_row(row)
    original_route = route
    checked_route = growth.growth_route_preflight_checked_route(
        preflight_args,
        route,
        realm=realm,
        current_level=level,
        party_size=party_size,
    )
    row["live_preflight_current_level"] = level
    row["live_preflight_status"] = "ok" if checked_route is not None else "skip"
    if checked_route is not None:
        final_route = checked_route
        for _attempt in range(3):
            if (
                int(getattr(final_route, "x", 0) or 0) == int(getattr(original_route, "x", 0) or 0)
                and int(getattr(final_route, "y", 0) or 0) == int(getattr(original_route, "y", 0) or 0)
                and int(getattr(final_route, "z", 0) or 0) == int(getattr(original_route, "z", 0) or 0)
            ):
                break
            next_route = growth.growth_route_preflight_checked_route(
                preflight_args,
                final_route,
                realm=realm,
                current_level=level,
                party_size=party_size,
            )
            if next_route is None:
                row["live_preflight_status"] = "skip_adjusted"
                row["live_preflight_adjusted"] = 1
                if bool(getattr(args, "live_preflight_filter", True)):
                    return None
                return row
            if (
                int(getattr(next_route, "x", 0) or 0) == int(getattr(final_route, "x", 0) or 0)
                and int(getattr(next_route, "y", 0) or 0) == int(getattr(final_route, "y", 0) or 0)
                and int(getattr(next_route, "z", 0) or 0) == int(getattr(final_route, "z", 0) or 0)
            ):
                final_route = next_route
                break
            final_route = next_route
        row["live_preflight_adjusted"] = int(
            int(getattr(final_route, "x", 0) or 0) != int(getattr(original_route, "x", 0) or 0)
            or int(getattr(final_route, "y", 0) or 0) != int(getattr(original_route, "y", 0) or 0)
            or int(getattr(final_route, "z", 0) or 0) != int(getattr(original_route, "z", 0) or 0)
        )
        row["x"] = int(getattr(final_route, "x", row.get("x", 0)) or row.get("x", 0) or 0)
        row["y"] = int(getattr(final_route, "y", row.get("y", 0)) or row.get("y", 0) or 0)
        row["z"] = int(getattr(final_route, "z", row.get("z", 0)) or row.get("z", 0) or 0)
        row["name"] = str(getattr(final_route, "prefer", row.get("name", "")) or row.get("name", ""))
        row["mob_level"] = int(getattr(final_route, "mob_level", row.get("mob_level", 0)) or row.get("mob_level", 0) or 0)
        row["mob_count"] = int(getattr(final_route, "mob_count", row.get("mob_count", 0)) or row.get("mob_count", 0) or 0)
        return row
    row["live_preflight_adjusted"] = 0
    if bool(getattr(args, "live_preflight_filter", True)):
        return None
    return row


def apply_live_preflight_to_rows(
    args: argparse.Namespace,
    rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for row in rows:
        checked = apply_live_preflight_to_row(args, row)
        if checked is not None:
            filtered.append(checked)
    return filtered


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "realm",
        "party_size",
        "player_level",
        "target_min",
        "target_ideal",
        "target_max",
        "name",
        "mob_level",
        "mob_count",
        "x",
        "y",
        "z",
        "neutral_count",
        "min_aggro",
        "max_aggro",
        "max_aggro_range",
        "nearest_teleporter",
        "teleporter_distance",
        "score",
        "live_preflight_status",
        "live_preflight_adjusted",
        "live_preflight_current_level",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def route_levels(level_min: int, level_max: int) -> list[int]:
    levels = [1, 2, 3, 5, 6]
    levels.extend(range(10, 51, 5))
    return [level for level in levels if level_min <= level <= level_max]


def route_row_limit(args: argparse.Namespace) -> int:
    configured = int(getattr(args, "route_top", 0) or 0)
    if configured > 0:
        return configured
    return max(1, int(getattr(args, "top", 1) or 1))


def route_recommendation_rows(args: argparse.Namespace, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    return rows[: route_row_limit(args)]


def main() -> int:
    args = parse_args()
    realms = [realm.strip().lower() for realm in args.realms.split(",") if realm.strip()]
    party_sizes = [
        int(part.strip())
        for part in str(getattr(args, "party_sizes", "") or "").split(",")
        if part.strip()
    ] or [int(args.party_size)]
    all_rows: list[dict[str, object]] = []
    route_rows: list[dict[str, object]] = []
    for party_size in party_sizes:
        args.party_size = party_size
        for realm_key in realms:
            if realm_key not in growth.REALMS:
                raise SystemExit(f"unknown realm: {realm_key}")
            for level in range(args.level_min, args.level_max + 1):
                rows = candidate_rows(args, realm_key, level, party_size)
                rows = apply_live_preflight_to_rows(args, rows)
                all_rows.extend(rows)
                if level in route_levels(args.level_min, args.level_max) and rows:
                    route_rows.extend(route_recommendation_rows(args, rows))
    write_csv(ROOT / args.output, all_rows)
    write_csv(ROOT / args.route_output, route_rows)
    print(f"candidate rows: {len(all_rows)} -> {args.output}")
    print(f"route rows: {len(route_rows)} -> {args.route_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
