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
GROWTH_SUITE = ROOT / "tools" / "run-dummy-growth-suite.py"


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
    parser.add_argument("--level-min", type=int, default=1)
    parser.add_argument("--level-max", type=int, default=50)
    parser.add_argument("--min-cluster-count", type=int, default=2)
    parser.add_argument("--cluster-size", type=int, default=20000)
    parser.add_argument("--top", type=int, default=5)
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


def candidate_rows(args: argparse.Namespace, realm_key: str, level: int) -> list[dict[str, object]]:
    realm = growth.REALMS[realm_key]
    min_target, ideal_target, max_delta = growth.target_levels(level, args.party_size)
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
                "player_level": level,
                "target_min": min_target,
                "target_ideal": ideal_target,
                "target_max": max_target,
                "name": row["Name"],
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


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "realm",
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
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def route_levels(level_min: int, level_max: int) -> list[int]:
    levels = [1, 2, 3, 5, 6]
    levels.extend(range(10, 51, 5))
    return [level for level in levels if level_min <= level <= level_max]


def main() -> int:
    args = parse_args()
    realms = [realm.strip().lower() for realm in args.realms.split(",") if realm.strip()]
    all_rows: list[dict[str, object]] = []
    route_rows: list[dict[str, object]] = []
    for realm_key in realms:
        if realm_key not in growth.REALMS:
            raise SystemExit(f"unknown realm: {realm_key}")
        for level in range(args.level_min, args.level_max + 1):
            rows = candidate_rows(args, realm_key, level)
            all_rows.extend(rows)
            if level in route_levels(args.level_min, args.level_max) and rows:
                route_rows.append(rows[0])
    write_csv(ROOT / args.output, all_rows)
    write_csv(ROOT / args.route_output, route_rows)
    print(f"candidate rows: {len(all_rows)} -> {args.output}")
    print(f"route rows: {len(route_rows)} -> {args.route_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
