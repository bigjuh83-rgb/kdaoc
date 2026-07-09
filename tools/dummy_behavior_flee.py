"""Pure threat scoring for behavior dummy flee planning."""

from __future__ import annotations

import argparse
import math
from collections.abc import Callable


def flee_threat_weight(
    args: argparse.Namespace,
    npc,
    *,
    growth_prefix_predicate: Callable[[str], bool],
) -> float:
    player_level = int(getattr(args, "player_level", 1) or 1)
    npc_level = int(getattr(npc, "level", 0) or 0)
    name = str(getattr(npc, "name", "") or "").lower()
    avoid_tokens = [
        token.strip().lower()
        for token in str(getattr(args, "avoid_target_name", "") or "").split(",")
        if token.strip()
    ]
    weight = 1.0

    if growth_prefix_predicate(name):
        weight += 12.0
    if npc_level > player_level:
        weight += float(npc_level - player_level) * 6.0
    if any(token in name for token in avoid_tokens):
        weight += 8.0
    if bool(getattr(npc, "has_aggro", False)) or bool(getattr(npc, "in_combat", False)):
        weight += 30.0

    return weight


def flee_candidate_risk(
    args: argparse.Namespace,
    candidate_x: int,
    candidate_y: int,
    npcs: list[object],
    *,
    horizontal_distance: Callable[[int | float, int | float, int | float, int | float], float],
    threat_weight: Callable[[object], float],
) -> float:
    threat_radius = float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0)
    if threat_radius <= 0.0:
        return 0.0

    risk = 0.0
    for npc in npcs:
        npc_x = int(getattr(npc, "x", 0) or 0)
        npc_y = int(getattr(npc, "y", 0) or 0)
        distance = horizontal_distance(candidate_x, candidate_y, npc_x, npc_y)
        if distance > threat_radius:
            continue

        weight = threat_weight(npc)
        risk += weight * (threat_radius - distance) / threat_radius
        if distance < 900.0:
            risk += weight * (900.0 - distance) / 90.0

    return risk


def flee_candidate_path_risk(
    args: argparse.Namespace,
    origin_x: int,
    origin_y: int,
    candidate_x: int,
    candidate_y: int,
    npcs: list[object],
    *,
    horizontal_distance: Callable[[int | float, int | float, int | float, int | float], float],
    point_to_segment_distance: Callable[
        [int | float, int | float, int | float, int | float, int | float, int | float],
        float,
    ],
    threat_weight: Callable[[object], float],
) -> float:
    corridor_radius = float(getattr(args, "flee_path_threat_corridor_radius", 0.0) or 0.0)
    if corridor_radius <= 0.0:
        step_distance = float(getattr(args, "flee_step", 0.0) or 0.0)
        corridor_radius = max(900.0, step_distance * 1.5)
    if corridor_radius <= 0.0:
        return 0.0

    risk = 0.0
    for npc in npcs:
        npc_x = int(getattr(npc, "x", 0) or 0)
        npc_y = int(getattr(npc, "y", 0) or 0)
        origin_distance = horizontal_distance(origin_x, origin_y, npc_x, npc_y)
        if origin_distance < float(getattr(args, "flee_path_origin_ignore_radius", 300.0) or 300.0):
            continue
        distance = point_to_segment_distance(npc_x, npc_y, origin_x, origin_y, candidate_x, candidate_y)
        if distance > corridor_radius:
            continue

        weight = threat_weight(npc)
        risk += weight * (corridor_radius - distance) / corridor_radius * 4.0
        if distance < 300.0:
            risk += weight * (300.0 - distance) / 30.0

    return risk


def rank_flee_candidate_points(
    *,
    origin_x: int,
    origin_y: int,
    flee_distance: float,
    threat_radius: float,
    npcs: list[object],
    current_risk: float,
    candidate_allowed: Callable[[int, int], bool],
    candidate_total_risk: Callable[[int, int], float],
    horizontal_distance: Callable[[int | float, int | float, int | float, int | float], float],
    threat_weight: Callable[[object], float],
    require_risk_improvement: bool = True,
) -> list[tuple[int, int]]:
    candidates: list[tuple[float, float, int, int]] = []
    clearance_limit = threat_radius + flee_distance
    for index in range(16):
        angle = math.tau * index / 16
        candidate_x = int(origin_x + math.cos(angle) * flee_distance)
        candidate_y = int(origin_y + math.sin(angle) * flee_distance)
        if not candidate_allowed(candidate_x, candidate_y):
            continue
        risk = candidate_total_risk(candidate_x, candidate_y)
        clearance = sum(
            threat_weight(npc)
            * min(
                horizontal_distance(
                    candidate_x,
                    candidate_y,
                    int(getattr(npc, "x", 0) or 0),
                    int(getattr(npc, "y", 0) or 0),
                ),
                clearance_limit,
            )
            for npc in npcs
        )
        candidates.append((risk, -clearance, candidate_x, candidate_y))

    candidates.sort(key=lambda item: (item[0], item[1]))
    if require_risk_improvement:
        candidates = [candidate for candidate in candidates if candidate[0] < current_risk]
    return [(candidate_x, candidate_y) for _risk, _clearance, candidate_x, candidate_y in candidates]
