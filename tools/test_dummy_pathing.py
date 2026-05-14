#!/usr/bin/env python3
"""Unit checks for dummy waypoint graph and A* pathing."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_pathing_module():
    module_path = Path(__file__).with_name("dummy_pathing.py")
    spec = importlib.util.spec_from_file_location("dummy_pathing_for_tests", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


pathing = load_pathing_module()


class DummyPathingTests(unittest.TestCase):
    def make_graph(self):
        return pathing.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "a", "x": 0, "y": 0, "z": 100},
                            {"id": "b", "x": 1000, "y": 0, "z": 100},
                            {"id": "c", "x": 1000, "y": 1000, "z": 100},
                            {"id": "d", "x": 0, "y": 1000, "z": 100},
                            {"id": "water", "x": 500, "y": 500, "z": 100, "tags": ["water"]},
                        ],
                        "edges": [
                            {"from": "a", "to": "b", "flags": ["wall"]},
                            {"from": "a", "to": "d"},
                            {"from": "d", "to": "c"},
                            {"from": "b", "to": "c"},
                            {"from": "a", "to": "water", "flags": ["water"]},
                        ],
                        "collisions": [
                            {
                                "id": "keep-door",
                                "kind": "keep_door",
                                "ax": 400,
                                "ay": -200,
                                "bx": 400,
                                "by": 200,
                            }
                        ],
                    }
                }
            }
        )

    def test_region_payload_loads_nodes_and_edges(self):
        graph = self.make_graph()

        self.assertEqual(graph.nodes["a"].region, 1)
        self.assertEqual(len(graph.edges["a"]), 3)

    def test_astar_avoids_blocked_direct_edge(self):
        graph = self.make_graph()
        route = graph.astar("a", "c", pathing.PathSafety())

        self.assertTrue(route.ok, route.reason)
        self.assertEqual([node.id for node in route.nodes], ["a", "d", "c"])

    def test_water_and_keep_door_are_blocked_unless_allowed(self):
        graph = self.make_graph()
        safety = pathing.PathSafety()

        self.assertFalse(graph.edge_allowed("a", graph.edges["a"][2], safety))
        self.assertFalse(
            graph.direct_path_allowed(
                1,
                pathing.PathPoint(0, 0, 100),
                pathing.PathPoint(800, 0, 100),
                safety,
                max_distance=1200,
            )
        )

        relaxed = pathing.PathSafety(allow_water=True, allow_keep_door=True, max_direct_distance=1200)
        self.assertTrue(graph.edge_allowed("a", graph.edges["a"][2], relaxed))
        self.assertTrue(
            graph.direct_path_allowed(
                1,
                pathing.PathPoint(0, 0, 100),
                pathing.PathPoint(800, 0, 100),
                relaxed,
            )
        )

    def test_height_check_blocks_cliff_like_step(self):
        graph = pathing.PathGraph.from_payload(
            {
                "nodes": [
                    {"id": "low", "region": 1, "x": 0, "y": 0, "z": 0},
                    {"id": "high", "region": 1, "x": 100, "y": 0, "z": 900},
                ],
                "edges": [{"from": "low", "to": "high"}],
            }
        )

        self.assertFalse(graph.edge_allowed("low", graph.edges["low"][0], pathing.PathSafety(max_height_delta=300)))
        self.assertFalse(
            graph.direct_path_allowed(
                1,
                pathing.PathPoint(0, 0, 0),
                pathing.PathPoint(100, 0, 900),
                pathing.PathSafety(max_height_delta=300),
                max_distance=1000,
            )
        )

    def test_box_collision_blocks_direct_path(self):
        graph = pathing.PathGraph.from_payload(
            {
                "nodes": [
                    {"id": "a", "region": 1, "x": 0, "y": 0, "z": 0},
                    {"id": "b", "region": 1, "x": 1000, "y": 0, "z": 0},
                ],
                "edges": [{"from": "a", "to": "b"}],
                "collisions": [
                    {
                        "id": "asset-box",
                        "region": 1,
                        "kind": "blocked",
                        "min_x": 400,
                        "min_y": -100,
                        "max_x": 600,
                        "max_y": 100,
                    }
                ],
            }
        )

        self.assertFalse(
            graph.direct_path_allowed(
                1,
                pathing.PathPoint(0, 0, 0),
                pathing.PathPoint(1000, 0, 0),
                pathing.PathSafety(),
                max_distance=1200,
            )
        )

    def test_route_between_points_uses_nearest_region_nodes(self):
        graph = self.make_graph()
        route = graph.route_between_points(
            1,
            pathing.PathPoint(25, 25, 100),
            pathing.PathPoint(950, 950, 100),
            max_node_distance=200,
            safety=pathing.PathSafety(),
        )

        self.assertTrue(route.ok, route.reason)
        self.assertEqual([node.id for node in route.nodes], ["a", "d", "c"])

    def test_route_between_points_ignores_nearby_node_behind_collision(self):
        graph = pathing.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "blocked_near", "x": 100, "y": 0, "z": 0},
                            {"id": "reachable_start", "x": 0, "y": 300, "z": 0},
                            {"id": "goal", "x": 1000, "y": 300, "z": 0},
                        ],
                        "edges": [
                            {"from": "blocked_near", "to": "goal"},
                            {"from": "reachable_start", "to": "goal"},
                        ],
                        "collisions": [
                            {
                                "id": "wall",
                                "kind": "wall",
                                "ax": 50,
                                "ay": -100,
                                "bx": 50,
                                "by": 120,
                            }
                        ],
                    }
                }
            }
        )

        route = graph.route_between_points(
            1,
            pathing.PathPoint(0, 0, 0),
            pathing.PathPoint(1000, 300, 0),
            max_node_distance=500,
            safety=pathing.PathSafety(max_direct_distance=500, max_edge_length=1200),
        )

        self.assertTrue(route.ok, route.reason)
        self.assertEqual([node.id for node in route.nodes], ["reachable_start", "goal"])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
