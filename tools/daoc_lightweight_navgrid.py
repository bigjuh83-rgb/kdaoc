#!/usr/bin/env python3
"""Lightweight A* grid pathing from DAoC client zone archives.

This is not a replacement for server navmesh collision. It gives dummy clients a
cheap outdoor fallback by using the client MPK terrain/water/fixture metadata.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import importlib.util
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


def load_heightmap_module():
    module_path = Path(__file__).with_name("daoc_zone_heightmap.py")
    spec = importlib.util.spec_from_file_location("daoc_zone_heightmap_for_navgrid", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


heightmap = load_heightmap_module()


@dataclass(frozen=True)
class GridPoint:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class GridRoute:
    ok: bool
    status: str
    points: list[GridPoint]
    visited: int = 0


@dataclass(frozen=True)
class FixtureBlocker:
    x: int
    y: int
    radius: int


class ZoneNavData:
    def __init__(self, zone_path: Path, zone) -> None:
        self.zone_path = zone_path
        self.zone = zone
        self.water = None
        self.fixtures: list[FixtureBlocker] = []
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return

        archive = heightmap.MpkArchive(self.zone_path / f"dat{self.zone.zone_id:03d}.mpk")
        files = archive.files()

        if "water.pcx" in files:
            self.water = heightmap.PcxImage(files["water.pcx"])

        self.fixtures = load_fixture_blockers(files.get("fixtures.csv"), self.zone)
        self._loaded = True

    def is_water(self, world_x: int, world_y: int) -> bool:
        self.load()

        if self.water is None:
            return False

        local_x = world_x - self.zone.world_x
        local_y = world_y - self.zone.world_y
        if local_x < 0 or local_y < 0 or local_x > self.zone.world_width or local_y > self.zone.world_height:
            return True

        x_pixel = local_x / max(1.0, self.zone.world_width / self.water.width)
        y_pixel = local_y / max(1.0, self.zone.world_height / self.water.height)
        return self.water.sample_nearest(x_pixel, y_pixel) != 255

    def fixture_blocked(self, world_x: int, world_y: int, padding: int) -> bool:
        self.load()

        if padding <= 0:
            return False

        for fixture in self.fixtures:
            radius = fixture.radius + padding
            if (fixture.x - world_x) ** 2 + (fixture.y - world_y) ** 2 <= radius * radius:
                return True

        return False


class ClientNavGridPathfinder:
    def __init__(
        self,
        config_path: Path,
        *,
        cell_size: int = 256,
        max_step_z: int = 240,
        allow_water: bool = False,
        fixture_padding: int = 160,
        max_visited: int = 20000,
    ) -> None:
        self.config_path = config_path
        self.sampler = heightmap.ClientZoneHeightSampler.from_config(config_path)
        self.cell_size = max(64, int(cell_size))
        self.max_step_z = max(0, int(max_step_z))
        self.allow_water = allow_water
        self.fixture_padding = max(0, int(fixture_padding))
        self.max_visited = max(100, int(max_visited))
        self._zone_data: dict[int, ZoneNavData] = {}
        self._cell_cache: dict[tuple[int, int, int], GridPoint | None] = {}

    def find_path(self, zone_id: int, start_x: int, start_y: int, end_x: int, end_y: int) -> GridRoute:
        start_cell = self.world_to_cell(zone_id, start_x, start_y)
        goal_cell = self.world_to_cell(zone_id, end_x, end_y)

        if start_cell is None:
            return GridRoute(False, "StartOutsideZone", [])

        if goal_cell is None:
            return GridRoute(False, "GoalOutsideZone", [])

        start_point = self.cell_point(zone_id, *start_cell)
        goal_point = self.cell_point(zone_id, *goal_cell)

        if start_point is None:
            return GridRoute(False, "StartBlocked", [])

        if goal_point is None:
            return GridRoute(False, "GoalBlocked", [])

        if start_cell == goal_cell:
            return GridRoute(True, "AlreadyThere", [start_point, goal_point])

        frontier: list[tuple[float, int, tuple[int, int]]] = [(0.0, 0, start_cell)]
        came_from: dict[tuple[int, int], tuple[int, int] | None] = {start_cell: None}
        cost_so_far: dict[tuple[int, int], float] = {start_cell: 0.0}
        sequence = 0
        visited = 0

        while frontier and visited < self.max_visited:
            _priority, _sequence, current = heapq.heappop(frontier)
            visited += 1

            if current == goal_cell:
                points = [self.cell_point(zone_id, *cell) for cell in rebuild_path(came_from, goal_cell)]
                return GridRoute(True, "PathFound", [point for point in points if point is not None], visited)

            for neighbor, step_cost in self.neighbors(zone_id, current):
                next_cost = cost_so_far[current] + step_cost

                if neighbor not in cost_so_far or next_cost < cost_so_far[neighbor]:
                    cost_so_far[neighbor] = next_cost
                    priority = next_cost + cell_distance(neighbor, goal_cell) * self.cell_size
                    sequence += 1
                    heapq.heappush(frontier, (priority, sequence, neighbor))
                    came_from[neighbor] = current

        status = "SearchLimitExceeded" if visited >= self.max_visited else "NoRoute"
        return GridRoute(False, status, [], visited)

    def neighbors(self, zone_id: int, cell: tuple[int, int]) -> Iterable[tuple[tuple[int, int], float]]:
        current = self.cell_point(zone_id, *cell)

        if current is None:
            return

        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue

                next_cell = (cell[0] + dx, cell[1] + dy)
                point = self.cell_point(zone_id, *next_cell)

                if point is None:
                    continue

                z_delta = abs(point.z - current.z)
                if z_delta > self.max_step_z:
                    continue

                distance_cost = math.sqrt(dx * dx + dy * dy) * self.cell_size
                slope_cost = z_delta * 1.75
                yield next_cell, distance_cost + slope_cost

    def world_to_cell(self, zone_id: int, world_x: int, world_y: int) -> tuple[int, int] | None:
        zone = self.sampler.zones.get(zone_id)

        if zone is None:
            return None

        local_x = world_x - zone.world_x
        local_y = world_y - zone.world_y

        if local_x < 0 or local_y < 0 or local_x > zone.world_width or local_y > zone.world_height:
            return None

        return (int(local_x // self.cell_size), int(local_y // self.cell_size))

    def cell_point(self, zone_id: int, cell_x: int, cell_y: int) -> GridPoint | None:
        cache_key = (zone_id, cell_x, cell_y)

        if cache_key in self._cell_cache:
            return self._cell_cache[cache_key]

        zone = self.sampler.zones.get(zone_id)

        if zone is None or cell_x < 0 or cell_y < 0:
            self._cell_cache[cache_key] = None
            return None

        world_x = zone.world_x + cell_x * self.cell_size + self.cell_size // 2
        world_y = zone.world_y + cell_y * self.cell_size + self.cell_size // 2

        if world_x > zone.world_x + zone.world_width or world_y > zone.world_y + zone.world_height:
            self._cell_cache[cache_key] = None
            return None

        zone_data = self.zone_data(zone_id)

        if zone_data is None:
            self._cell_cache[cache_key] = None
            return None

        if not self.allow_water and zone_data.is_water(world_x, world_y):
            self._cell_cache[cache_key] = None
            return None

        if zone_data.fixture_blocked(world_x, world_y, self.fixture_padding):
            self._cell_cache[cache_key] = None
            return None

        sampled_z = self.sampler.sample(world_x, world_y, zone_id)
        point = None if sampled_z is None else GridPoint(world_x, world_y, sampled_z)
        self._cell_cache[cache_key] = point
        return point

    def zone_data(self, zone_id: int) -> ZoneNavData | None:
        if zone_id in self._zone_data:
            return self._zone_data[zone_id]

        zone = self.sampler.zones.get(zone_id)
        if zone is None:
            return None

        zone_path = self.sampler._find_zone_path(zone_id)
        if zone_path is None:
            return None

        data = ZoneNavData(zone_path, zone)
        self._zone_data[zone_id] = data
        return data


def load_fixture_blockers(data: bytes | None, zone) -> list[FixtureBlocker]:
    if not data:
        return []

    text = data.decode("latin1", "replace").splitlines()
    if len(text) < 3:
        return []

    blockers: list[FixtureBlocker] = []
    reader = csv.DictReader(text[1:])

    for row in reader:
        try:
            if int(float(row.get("Collide", "0") or "0")) == 0:
                continue

            local_x = float(row.get("X", "0") or "0")
            local_y = float(row.get("Y", "0") or "0")
            radius = int(max(0.0, float(row.get("Radius", "0") or "0")))
        except ValueError:
            continue

        blockers.append(
            FixtureBlocker(
                int(round(zone.world_x + local_x)),
                int(round(zone.world_y + local_y)),
                radius,
            )
        )

    return blockers


def rebuild_path(came_from: dict[tuple[int, int], tuple[int, int] | None], goal: tuple[int, int]) -> list[tuple[int, int]]:
    current: tuple[int, int] | None = goal
    path: list[tuple[int, int]] = []

    while current is not None:
        path.append(current)
        current = came_from[current]

    path.reverse()
    return path


def cell_distance(left: tuple[int, int], right: tuple[int, int]) -> float:
    return math.sqrt((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2)


def parse_xy(value: str) -> tuple[int, int]:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("expected X,Y")
    return int(parts[0]), int(parts[1])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--zone", type=int, required=True)
    parser.add_argument("--start", type=parse_xy, required=True, help="world X,Y")
    parser.add_argument("--end", type=parse_xy, required=True, help="world X,Y")
    parser.add_argument("--cell-size", type=int, default=256)
    parser.add_argument("--max-step-z", type=int, default=240)
    parser.add_argument("--fixture-padding", type=int, default=160)
    parser.add_argument("--max-visited", type=int, default=20000)
    parser.add_argument("--allow-water", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    pathfinder = ClientNavGridPathfinder(
        Path(args.config),
        cell_size=args.cell_size,
        max_step_z=args.max_step_z,
        allow_water=args.allow_water,
        fixture_padding=args.fixture_padding,
        max_visited=args.max_visited,
    )
    route = pathfinder.find_path(args.zone, args.start[0], args.start[1], args.end[0], args.end[1])
    print(
        json.dumps(
            {
                "ok": route.ok,
                "status": route.status,
                "visited": route.visited,
                "points": [{"x": point.x, "y": point.y, "z": point.z} for point in route.points],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if route.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
