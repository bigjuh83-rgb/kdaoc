#!/usr/bin/env python3
"""Waypoint graph and A* pathing helpers for OpenDAoC dummy clients."""

from __future__ import annotations

import heapq
import json
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path


HARD_BLOCKING_FLAGS = frozenset({"wall", "blocked", "obstacle"})
DOOR_FLAGS = frozenset({"door", "closed_door"})


@dataclass(frozen=True)
class PathPoint:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class PathNode:
    id: str
    region: int
    x: int
    y: int
    z: int
    tags: frozenset[str] = frozenset()

    @property
    def point(self) -> PathPoint:
        return PathPoint(self.x, self.y, self.z)


@dataclass(frozen=True)
class PathEdge:
    to: str
    cost: float
    flags: frozenset[str] = frozenset()
    max_height_delta: int | None = None


@dataclass(frozen=True)
class CollisionSegment:
    id: str
    region: int
    kind: str
    ax: int
    ay: int
    bx: int
    by: int
    min_z: int | None = None
    max_z: int | None = None
    flags: frozenset[str] = frozenset()

    def blocks(self, safety: "PathSafety") -> bool:
        flags = self.flags or frozenset({self.kind})
        return not flags_allowed(flags, safety)

    def intersects(self, start: PathPoint, goal: PathPoint) -> bool:
        if self.min_z is not None and max(start.z, goal.z) < self.min_z:
            return False

        if self.max_z is not None and min(start.z, goal.z) > self.max_z:
            return False

        return segments_intersect(
            float(start.x),
            float(start.y),
            float(goal.x),
            float(goal.y),
            float(self.ax),
            float(self.ay),
            float(self.bx),
            float(self.by),
        )


@dataclass(frozen=True)
class PathSafety:
    max_edge_length: float = 1800.0
    max_direct_distance: float = 450.0
    max_height_delta: int = 450
    allow_water: bool = False
    allow_closed_door: bool = False
    allow_keep_door: bool = False
    allow_cliff: bool = False
    blocked_tags: frozenset[str] = frozenset({"blocked", "wall", "obstacle"})


@dataclass
class PathRoute:
    nodes: list[PathNode]
    reason: str = ""

    @property
    def ok(self) -> bool:
        return bool(self.nodes)


@dataclass
class PathGraph:
    nodes: dict[str, PathNode] = field(default_factory=dict)
    edges: dict[str, list[PathEdge]] = field(default_factory=dict)
    collisions: list[CollisionSegment] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str | Path) -> "PathGraph":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_payload(payload)

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> "PathGraph":
        graph = cls()

        if isinstance(payload.get("regions"), dict):
            for raw_region_id, raw_region in payload["regions"].items():  # type: ignore[index,union-attr]
                region_id = int(raw_region_id)
                if not isinstance(raw_region, dict):
                    continue
                graph._load_region(region_id, raw_region)
        else:
            graph._load_region(None, payload)

        return graph

    def _load_region(self, default_region: int | None, payload: dict[str, object]) -> None:
        for raw_node in payload.get("nodes", []):  # type: ignore[union-attr]
            if not isinstance(raw_node, dict):
                continue

            region = int(raw_node.get("region", default_region if default_region is not None else 0))
            node = PathNode(
                id=str(raw_node["id"]),
                region=region,
                x=int(raw_node["x"]),
                y=int(raw_node["y"]),
                z=int(raw_node["z"]),
                tags=normalize_flags(raw_node.get("tags", [])),
            )
            self.nodes[node.id] = node
            self.edges.setdefault(node.id, [])

        for raw_edge in payload.get("edges", []):  # type: ignore[union-attr]
            if not isinstance(raw_edge, dict):
                continue

            src = str(raw_edge["from"])
            dst = str(raw_edge["to"])

            if src not in self.nodes or dst not in self.nodes:
                raise ValueError(f"edge references unknown node: {src}->{dst}")

            flags = normalize_flags(raw_edge.get("flags", []))
            max_height_delta = raw_edge.get("max_height_delta")
            cost = float(raw_edge.get("cost", 0.0)) or self.distance_between_ids(src, dst)
            bidirectional = bool(raw_edge.get("bidirectional", True))
            edge = PathEdge(
                to=dst,
                cost=cost,
                flags=flags,
                max_height_delta=int(max_height_delta) if max_height_delta is not None else None,
            )
            self.edges.setdefault(src, []).append(edge)

            if bidirectional:
                self.edges.setdefault(dst, []).append(
                    PathEdge(
                        to=src,
                        cost=cost,
                        flags=flags,
                        max_height_delta=int(max_height_delta) if max_height_delta is not None else None,
                    )
                )

        for raw_collision in payload.get("collisions", []):  # type: ignore[union-attr]
            if not isinstance(raw_collision, dict):
                continue

            region = int(raw_collision.get("region", default_region if default_region is not None else 0))
            self.collisions.append(
                CollisionSegment(
                    id=str(raw_collision.get("id", f"collision-{len(self.collisions) + 1}")),
                    region=region,
                    kind=str(raw_collision.get("kind", "blocked")).lower(),
                    ax=int(raw_collision["ax"]),
                    ay=int(raw_collision["ay"]),
                    bx=int(raw_collision["bx"]),
                    by=int(raw_collision["by"]),
                    min_z=int(raw_collision["min_z"]) if raw_collision.get("min_z") is not None else None,
                    max_z=int(raw_collision["max_z"]) if raw_collision.get("max_z") is not None else None,
                    flags=normalize_flags(raw_collision.get("flags", [raw_collision.get("kind", "blocked")])),
                )
            )

    def distance_between_ids(self, left_id: str, right_id: str) -> float:
        return distance(self.nodes[left_id].point, self.nodes[right_id].point)

    def nearest_node(
        self,
        region: int,
        point: PathPoint,
        *,
        max_distance: float,
        max_height_delta: int,
        safety: PathSafety,
    ) -> PathNode | None:
        candidates = [
            node
            for node in self.nodes.values()
            if node.region == region
            and abs(node.z - point.z) <= max_height_delta
            and self.node_allowed(node, safety)
        ]

        if not candidates:
            return None

        best = min(candidates, key=lambda node: distance(point, node.point))

        if distance(point, best.point) > max_distance:
            return None

        return best

    def astar(self, start_id: str, goal_id: str, safety: PathSafety) -> PathRoute:
        if start_id not in self.nodes:
            return PathRoute([], f"missing start node {start_id}")

        if goal_id not in self.nodes:
            return PathRoute([], f"missing goal node {goal_id}")

        if start_id == goal_id:
            return PathRoute([self.nodes[start_id]])

        frontier: list[tuple[float, str]] = [(0.0, start_id)]
        came_from: dict[str, str | None] = {start_id: None}
        cost_so_far: dict[str, float] = {start_id: 0.0}

        while frontier:
            _, current = heapq.heappop(frontier)

            if current == goal_id:
                break

            for edge in self.edges.get(current, []):
                if not self.edge_allowed(current, edge, safety):
                    continue

                next_cost = cost_so_far[current] + edge.cost

                if edge.to not in cost_so_far or next_cost < cost_so_far[edge.to]:
                    cost_so_far[edge.to] = next_cost
                    priority = next_cost + distance(self.nodes[edge.to].point, self.nodes[goal_id].point)
                    heapq.heappush(frontier, (priority, edge.to))
                    came_from[edge.to] = current

        if goal_id not in came_from:
            return PathRoute([], f"no route {start_id}->{goal_id}")

        return PathRoute([self.nodes[node_id] for node_id in rebuild_path(came_from, goal_id)])

    def route_between_points(
        self,
        region: int,
        start: PathPoint,
        goal: PathPoint,
        *,
        max_node_distance: float,
        safety: PathSafety,
    ) -> PathRoute:
        start_node = self.nearest_node(
            region,
            start,
            max_distance=max_node_distance,
            max_height_delta=safety.max_height_delta,
            safety=safety,
        )
        goal_node = self.nearest_node(
            region,
            goal,
            max_distance=max_node_distance,
            max_height_delta=safety.max_height_delta,
            safety=safety,
        )

        if start_node is None:
            return PathRoute([], "no nearby start graph node")

        if goal_node is None:
            return PathRoute([], "no nearby goal graph node")

        return self.astar(start_node.id, goal_node.id, safety)

    def node_allowed(self, node: PathNode, safety: PathSafety) -> bool:
        if node.tags.intersection(safety.blocked_tags):
            return False

        return flags_allowed(node.tags, safety)

    def edge_allowed(self, from_id: str, edge: PathEdge, safety: PathSafety) -> bool:
        if edge.to not in self.nodes or from_id not in self.nodes:
            return False

        from_node = self.nodes[from_id]
        to_node = self.nodes[edge.to]

        if not self.node_allowed(from_node, safety) or not self.node_allowed(to_node, safety):
            return False

        if not flags_allowed(edge.flags, safety):
            return False

        if distance(from_node.point, to_node.point) > safety.max_edge_length:
            return False

        allowed_height = edge.max_height_delta if edge.max_height_delta is not None else safety.max_height_delta
        return abs(from_node.z - to_node.z) <= allowed_height

    def direct_path_allowed(
        self,
        region: int,
        start: PathPoint,
        goal: PathPoint,
        safety: PathSafety,
        *,
        max_distance: float | None = None,
    ) -> bool:
        allowed_distance = safety.max_direct_distance if max_distance is None else max_distance

        if distance(start, goal) > allowed_distance:
            return False

        if abs(start.z - goal.z) > safety.max_height_delta:
            return False

        for collision in self.collisions:
            if collision.region == region and collision.blocks(safety) and collision.intersects(start, goal):
                return False

        return True


@dataclass
class PathFollower:
    route: list[PathNode | PathPoint] = field(default_factory=list)
    index: int = 0

    def set_route(self, route: Iterable[PathNode | PathPoint]) -> None:
        self.route = list(route)
        self.index = 0

    def clear(self) -> None:
        self.route = []
        self.index = 0

    def next_point(self, current: PathPoint, arrival_distance: float) -> PathPoint | None:
        while self.index < len(self.route):
            node = self.route[self.index]
            point = node.point if isinstance(node, PathNode) else node

            if distance(current, point) <= arrival_distance:
                self.index += 1
                continue

            return point

        return None


def normalize_flags(value: object) -> frozenset[str]:
    if value is None:
        return frozenset()

    if isinstance(value, str):
        return frozenset(part.strip().lower() for part in value.split(",") if part.strip())

    if isinstance(value, Iterable):
        return frozenset(str(part).strip().lower() for part in value if str(part).strip())

    return frozenset({str(value).strip().lower()})


def flags_allowed(flags: frozenset[str], safety: PathSafety) -> bool:
    if flags.intersection(HARD_BLOCKING_FLAGS):
        return False

    if "cliff" in flags and not safety.allow_cliff:
        return False

    if "water" in flags and not safety.allow_water:
        return False

    if flags.intersection(DOOR_FLAGS) and not safety.allow_closed_door:
        return False

    if "keep_door" in flags and not safety.allow_keep_door:
        return False

    return True


def distance(left: PathPoint, right: PathPoint) -> float:
    return math.sqrt((left.x - right.x) ** 2 + (left.y - right.y) ** 2 + (left.z - right.z) ** 2)


def rebuild_path(came_from: dict[str, str | None], goal_id: str) -> list[str]:
    current: str | None = goal_id
    path: list[str] = []

    while current is not None:
        path.append(current)
        current = came_from[current]

    path.reverse()
    return path


def segments_intersect(ax: float, ay: float, bx: float, by: float, cx: float, cy: float, dx: float, dy: float) -> bool:
    def orientation(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> int:
        value = (qy - py) * (rx - qx) - (qx - px) * (ry - qy)

        if abs(value) < 1e-9:
            return 0

        return 1 if value > 0 else 2

    def on_segment(px: float, py: float, qx: float, qy: float, rx: float, ry: float) -> bool:
        return min(px, rx) <= qx <= max(px, rx) and min(py, ry) <= qy <= max(py, ry)

    o1 = orientation(ax, ay, bx, by, cx, cy)
    o2 = orientation(ax, ay, bx, by, dx, dy)
    o3 = orientation(cx, cy, dx, dy, ax, ay)
    o4 = orientation(cx, cy, dx, dy, bx, by)

    if o1 != o2 and o3 != o4:
        return True

    if o1 == 0 and on_segment(ax, ay, cx, cy, bx, by):
        return True

    if o2 == 0 and on_segment(ax, ay, dx, dy, bx, by):
        return True

    if o3 == 0 and on_segment(cx, cy, ax, ay, dx, dy):
        return True

    return o4 == 0 and on_segment(cx, cy, bx, by, dx, dy)
