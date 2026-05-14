#!/usr/bin/env python3
"""Unit checks for behavior dummy player-follow selection."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


def load_behavior_module():
    module_path = Path(__file__).with_name("behavior-dummy-client.py")
    spec = importlib.util.spec_from_file_location("behavior_dummy_client_for_tests", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


behavior = load_behavior_module()


class FakePlayer:
    def __init__(self, object_id: int, name: str, distance: float) -> None:
        self.object_id = object_id
        self.name = name
        self.distance = distance
        self.x = 0
        self.y = 0
        self.z = 0


class FakeNpc:
    def __init__(self, object_id: int, name: str, level: int, distance: float) -> None:
        self.object_id = object_id
        self.name = name
        self.level = level
        self.distance = distance
        self.x = 0
        self.y = 0
        self.z = 0


class FakeClient:
    def __init__(self, players: list[FakePlayer] | None = None, npcs: list[FakeNpc] | None = None) -> None:
        self.players = players or []
        self.npcs = npcs or []

    def visible_players(self, max_age: float = 30.0):
        return list(self.players)

    def visible_npcs(self, max_age: float = 60.0, include_peace: bool = False):
        return list(self.npcs)

    def distance_to(self, actor) -> float:
        return actor.distance


class PathClient:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.z = 0
        self.zone_id = 1
        self.moves: list[tuple[int, int, int, float, float]] = []

    def move_towards_position(self, x: int, y: int, z: int, step: float = 250.0, stop_distance: float = 250.0) -> bool:
        self.moves.append((x, y, z, step, stop_distance))
        self.x = x
        self.y = y
        self.z = z
        return True

    def send_position_update(self, speed: float = 0.0, target_in_view: bool = False) -> int:
        return 0


class StepPathClient:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.z = 0
        self.zone_id = 1
        self.moves: list[tuple[int, int, int, float, float]] = []

    def move_towards_position(self, x: int, y: int, z: int, step: float = 250.0, stop_distance: float = 250.0) -> bool:
        self.moves.append((x, y, z, step, stop_distance))
        dx = x - self.x
        dy = y - self.y
        dz = z - self.z
        distance = (dx * dx + dy * dy + dz * dz) ** 0.5

        if distance <= stop_distance or distance <= 0:
            return False

        ratio = min(step, distance - stop_distance) / distance
        self.x = int(self.x + dx * ratio)
        self.y = int(self.y + dy * ratio)
        self.z = int(self.z + dz * ratio)
        return True

    def send_position_update(self, speed: float = 0.0, target_in_view: bool = False) -> int:
        return 0


class BehaviorPlayerFollowTests(unittest.TestCase):
    def test_choose_named_visible_player(self):
        args = SimpleNamespace(follow_player_name="라온", player_state_max_age=9.0, follow_player_max_distance=0.0)
        players = [FakePlayer(1, "가온", 100), FakePlayer(2, "라온", 900)]

        selected = behavior.choose_follow_player(FakeClient(players), args)

        self.assertEqual(selected.name, "라온")

    def test_choose_nearest_player_with_distance_cap(self):
        args = SimpleNamespace(follow_player_name="", player_state_max_age=9.0, follow_player_max_distance=500.0)
        players = [FakePlayer(1, "멀리", 900), FakePlayer(2, "근처", 120)]

        selected = behavior.choose_follow_player(FakeClient(players), args)

        self.assertEqual(selected.name, "근처")

    def test_choose_greet_player_respects_distance_and_cooldown(self):
        args = SimpleNamespace(player_state_max_age=9.0, player_greet_distance=500.0)
        players = [FakePlayer(1, "가온", 200), FakePlayer(2, "라온", 300)]
        greeted_until = {1: 200.0}

        selected = behavior.choose_greet_player(FakeClient(players), args, greeted_until, now=100.0)

        self.assertEqual(selected.name, "라온")

    def test_applies_named_ai_persona_without_mutating_base_args(self):
        args = SimpleNamespace(
            ai_player=True,
            ai_persona="social-roamer",
            social_chance=0.10,
            emote_chance=0.10,
            long_rest_chance=0.05,
            rest_chance=0.05,
            target_examine_chance=0.10,
            player_greet_chance=0.05,
            player_follow_interval=2.0,
            player_follow_distance=850.0,
            follow_player_max_distance=3500.0,
            look_around_interval=12.0,
            think_min=0.5,
            think_max=1.0,
        )

        tuned = behavior.apply_ai_persona(args, SimpleNamespace(username="dummy001"), 0)

        self.assertIsNot(tuned, args)
        self.assertEqual(tuned.ai_persona_name, "social-roamer")
        self.assertGreater(tuned.social_chance, args.social_chance)
        self.assertGreater(tuned.player_greet_chance, args.player_greet_chance)
        self.assertLess(tuned.player_follow_interval, args.player_follow_interval)
        self.assertEqual(args.ai_persona, "social-roamer")

    def test_auto_ai_persona_is_deterministic_per_account(self):
        args = SimpleNamespace(
            ai_player=True,
            ai_persona="auto",
            social_chance=0.10,
            emote_chance=0.10,
            long_rest_chance=0.05,
            rest_chance=0.05,
            target_examine_chance=0.10,
            player_greet_chance=0.05,
            player_follow_interval=2.0,
            player_follow_distance=850.0,
            follow_player_max_distance=3500.0,
            look_around_interval=12.0,
            think_min=0.5,
            think_max=1.0,
            seed=20260513,
        )

        first = behavior.apply_ai_persona(args, SimpleNamespace(username="dummy001"), 0)
        second = behavior.apply_ai_persona(args, SimpleNamespace(username="dummy001"), 0)

        self.assertEqual(first.ai_persona_name, second.ai_persona_name)
        self.assertIn(first.ai_persona_name, behavior.AI_PERSONAS)

    def test_hunting_profiles_keep_targets_and_use_melee_range(self):
        for profile in ("solo-melee", "pve-casual", "party-tank", "party-dps"):
            with self.subTest(profile=profile):
                args = SimpleNamespace(behavior_profile=profile)

                behavior.apply_behavior_profile(args)

                self.assertGreaterEqual(args.stick_to_target_chance, 0.98)
                if hasattr(args, "attack_range"):
                    self.assertLessEqual(args.attack_range, 130)
                if hasattr(args, "target_timeout"):
                    self.assertGreaterEqual(args.target_timeout, 45.0)

    def test_hunter_avoids_rejected_target_name_and_level(self):
        args = SimpleNamespace(
            npc_max_age=60.0,
            include_peace_npcs=False,
            player_level=1,
            ideal_target_level=1,
            min_target_level=0,
            max_target_level=-1,
            max_target_level_delta=1,
            max_target_distance=0.0,
            target_pool=5,
            target_selection="smart",
            target_level_weight=120.0,
            target_distance_weight=120.0,
            target_randomness=0.0,
            prefer_target_name="",
            avoid_target_name="",
            prefer_target_bonus=300.0,
        )
        npcs = [
            FakeNpc(1, "spriggarn", 2, 100),
            FakeNpc(2, "green snake", 0, 300),
        ]

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=npcs),
            behavior.random.Random(1),
            args,
            rejected_targets={},
            rejected_target_kinds={("spriggarn", 2): 999.0},
            now=100.0,
        )

        self.assertEqual(selected.name, "green snake")

    def test_hunter_target_pool_uses_nearest_candidates_first(self):
        args = SimpleNamespace(
            npc_max_age=60.0,
            include_peace_npcs=False,
            player_level=1,
            ideal_target_level=1,
            min_target_level=0,
            max_target_level=-1,
            max_target_level_delta=1,
            max_target_distance=0.0,
            target_pool=1,
            target_selection="nearest",
            target_level_weight=120.0,
            target_distance_weight=120.0,
            target_randomness=0.0,
            prefer_target_name="",
            avoid_target_name="",
            prefer_target_bonus=300.0,
        )
        npcs = [
            FakeNpc(1, "far snake", 0, 900),
            FakeNpc(2, "near snake", 0, 150),
        ]

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=npcs),
            behavior.random.Random(1),
            args,
            rejected_targets={},
            rejected_target_kinds={},
            now=100.0,
        )

        self.assertEqual(selected.name, "near snake")

    def test_hunter_respects_absolute_max_target_level(self):
        args = SimpleNamespace(
            npc_max_age=60.0,
            include_peace_npcs=False,
            player_level=1,
            ideal_target_level=0,
            min_target_level=0,
            max_target_level=0,
            max_target_level_delta=4,
            max_target_distance=0.0,
            target_pool=5,
            target_selection="smart",
            target_level_weight=120.0,
            target_distance_weight=120.0,
            target_randomness=0.0,
            prefer_target_name="",
            avoid_target_name="",
            prefer_target_bonus=300.0,
        )
        npcs = [
            FakeNpc(1, "near wolf pup", 1, 100),
            FakeNpc(2, "green snake", 0, 300),
        ]

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=npcs),
            behavior.random.Random(1),
            args,
            rejected_targets={},
            rejected_target_kinds={},
            now=100.0,
        )

        self.assertEqual(selected.name, "green snake")

    def test_melee_stop_distance_stays_inside_attack_range(self):
        args = SimpleNamespace(attack_range=120.0, melee_range_buffer=25.0, minimum_melee_stop_distance=70.0)

        self.assertEqual(behavior.melee_stop_distance(args), 95.0)

    def test_smooth_movement_step_uses_speed_and_interval(self):
        args = SimpleNamespace(movement_speed=220.0, smooth_move_interval=0.25)

        self.assertEqual(behavior.smooth_movement_step(args), 55.0)

    def test_path_movement_uses_graph_waypoint_before_goal(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "bend", "x": 0, "y": 1000, "z": 0},
                            {"id": "goal", "x": 1000, "y": 1000, "z": 0},
                        ],
                        "edges": [
                            {"from": "start", "to": "bend"},
                            {"from": "bend", "to": "goal"},
                        ],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=60.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        client = PathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("target:1", 1000, 1000, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (0, 1000, 0))
        self.assertEqual(action_counts["path_plan"], 1)
        self.assertEqual(action_counts["path_step"], 1)

    def test_path_movement_keeps_existing_route_between_nodes(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "bend", "x": 0, "y": 1000, "z": 0},
                            {"id": "goal", "x": 1000, "y": 1000, "z": 0},
                        ],
                        "edges": [
                            {"from": "start", "to": "bend"},
                            {"from": "bend", "to": "goal"},
                        ],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=700.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        client = StepPathClient()
        action_counts: dict[str, int] = {}
        destination = behavior.MovementDestination("target:1", 1000, 1000, 0)

        first = behavior.move_towards_destination(
            client,
            destination,
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )
        second = behavior.move_towards_destination(
            client,
            destination,
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(first.moved)
        self.assertTrue(second.moved)
        self.assertEqual(action_counts["path_plan"], 1)
        self.assertEqual(client.moves[0][:3], (0, 1000, 0))
        self.assertEqual(client.moves[1][:3], (0, 1000, 0))
        self.assertGreater(client.y, 250)

    def test_parse_nav_response_returns_path_points(self):
        result = behavior.parse_nav_path_response(
            {
                "ok": True,
                "status": "PathFound",
                "lineOfSight": False,
                "snappedStart": {"x": 8, "y": 18, "z": 28},
                "snappedEnd": {"x": 44, "y": 54, "z": 64},
                "floor": {"x": 9, "y": 19, "z": 25},
                "points": [
                    {"x": 10, "y": 20, "z": 30},
                    {"x": 40, "y": 50, "z": 60, "flags": "Walk"},
                ],
            }
        )
        ok, status, points = result

        self.assertTrue(ok)
        self.assertEqual(status, "PathFound")
        self.assertEqual(
            [(point.x, point.y, point.z) for point in points],
            [(8, 18, 28), (10, 20, 30), (40, 50, 60), (44, 54, 64)],
        )
        self.assertFalse(result.line_of_sight)
        self.assertEqual((result.snapped_start.x, result.snapped_start.y, result.snapped_start.z), (8, 18, 28))
        self.assertEqual((result.snapped_end.x, result.snapped_end.y, result.snapped_end.z), (44, 54, 64))
        self.assertEqual((result.floor.x, result.floor.y, result.floor.z), (9, 19, 25))

    def test_nav_response_route_includes_snapped_end_when_path_omits_it(self):
        result = behavior.parse_nav_path_response(
            {
                "ok": True,
                "status": "PathFound",
                "lineOfSight": True,
                "snappedEnd": {"x": 1000, "y": 0, "z": 80},
                "points": [{"x": 500, "y": 0, "z": 80}],
            }
        )

        self.assertTrue(result.ok)
        self.assertEqual([(point.x, point.y, point.z) for point in result.points], [(500, 0, 80), (1000, 0, 80)])

    def test_nav_response_rejects_snapped_only_route_without_line_of_sight(self):
        result = behavior.parse_nav_path_response(
            {
                "ok": True,
                "status": "PathFound",
                "lineOfSight": False,
                "snappedEnd": {"x": 1000, "y": 0, "z": 80},
                "points": [],
            }
        )

        self.assertFalse(result.ok)
        self.assertEqual(result.points, [])

    def test_nav_only_path_state_keeps_client_region_without_graph(self):
        args = SimpleNamespace(
            disable_graph_pathing=False,
            path_graph="",
            path_region=0,
            path_max_edge_length=1500.0,
            path_last_mile_distance=150.0,
            path_max_height_delta=450,
            path_allow_water=False,
            path_allow_closed_door=False,
            path_allow_keep_door=False,
            path_allow_cliff=False,
        )
        client = SimpleNamespace(zone_id=7)

        state = behavior.build_path_movement_state(args, client)

        self.assertIsNone(state.graph)
        self.assertEqual(state.region, 7)

    def test_failed_nav_path_waits_before_replanning_same_destination(self):
        args = SimpleNamespace(
            nav_api_url="http://127.0.0.1:5000",
            path_last_mile_distance=150.0,
            path_replan_interval=60.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
        )
        state = behavior.PathMovementState(None, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        client = PathClient()
        action_counts: dict[str, int] = {}
        original_request_nav_path = behavior.request_nav_path
        calls: list[tuple[int, int]] = []

        def fake_request_nav_path(_args, _region, start, goal):
            calls.append((start.x, goal.x))
            return False, "NavmeshUnavailable", []

        behavior.request_nav_path = fake_request_nav_path

        try:
            destination = behavior.MovementDestination("target:far", 1000, 0, 0)
            first = behavior.move_towards_destination(
                client,
                destination,
                step=250.0,
                stop_distance=100.0,
                args=args,
                path_state=state,
                action_counts=action_counts,
            )
            second = behavior.move_towards_destination(
                client,
                destination,
                step=250.0,
                stop_distance=100.0,
                args=args,
                path_state=state,
                action_counts=action_counts,
            )
        finally:
            behavior.request_nav_path = original_request_nav_path

        self.assertFalse(first.moved)
        self.assertFalse(second.moved)
        self.assertEqual(len(calls), 1)
        self.assertEqual(action_counts["nav_path_failed"], 1)
        self.assertEqual(action_counts["path_failed"], 1)
        self.assertEqual(action_counts["path_replan_wait"], 1)

    def test_nav_segment_validation_blocks_next_step(self):
        args = SimpleNamespace(
            nav_api_url="http://127.0.0.1:5000",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            nav_segment_validate=True,
        )
        state = behavior.PathMovementState(None, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        client = PathClient()
        action_counts: dict[str, int] = {}
        original_request_nav_path = behavior.request_nav_path
        calls: list[tuple[int, int]] = []

        def fake_request_nav_path(_args, _region, start, goal):
            calls.append((start.x, goal.x))

            if len(calls) == 1:
                return True, "PathFound", [
                    behavior.PathPoint(500, 0, 0),
                    behavior.PathPoint(1000, 0, 0),
                ]

            return False, "SegmentBlocked", []

        behavior.request_nav_path = fake_request_nav_path

        try:
            outcome = behavior.move_towards_destination(
                client,
                behavior.MovementDestination("target:far", 1000, 0, 0),
                step=250.0,
                stop_distance=100.0,
                args=args,
                path_state=state,
                action_counts=action_counts,
            )
        finally:
            behavior.request_nav_path = original_request_nav_path

        self.assertFalse(outcome.moved)
        self.assertEqual(client.moves, [])
        self.assertEqual(len(calls), 2)
        self.assertEqual(action_counts["nav_path_plan"], 1)
        self.assertEqual(action_counts["nav_segment_blocked"], 1)

    def test_nav_segment_validation_blocks_last_mile(self):
        args = SimpleNamespace(
            nav_api_url="http://127.0.0.1:5000",
            path_last_mile_distance=1500.0,
            path_replan_interval=0.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            nav_segment_validate=True,
        )
        state = behavior.PathMovementState(None, 1, behavior.PathSafety(max_direct_distance=1500.0, max_edge_length=1500.0))
        client = PathClient()
        action_counts: dict[str, int] = {}
        original_request_nav_path = behavior.request_nav_path

        def fake_request_nav_path(_args, _region, _start, _goal):
            return False, "LastMileBlocked", []

        behavior.request_nav_path = fake_request_nav_path

        try:
            outcome = behavior.move_towards_destination(
                client,
                behavior.MovementDestination("target:near", 1000, 0, 0),
                step=250.0,
                stop_distance=100.0,
                args=args,
                path_state=state,
                action_counts=action_counts,
            )
        finally:
            behavior.request_nav_path = original_request_nav_path

        self.assertFalse(outcome.moved)
        self.assertEqual(client.moves, [])
        self.assertEqual(action_counts["nav_segment_blocked"], 1)

    def test_metrics_csv_includes_movement_failure_sample(self):
        path = Path("behavior-movement-failure-test.csv")
        results = [
            behavior.DummyResult(
                "dummy001",
                ok=True,
                rounds=1,
                successful_rounds=1,
                metrics=[
                    behavior.RoundMetric(
                        "dummy001",
                        1,
                        True,
                        3,
                        1.25,
                        "",
                        {"nav_segment_blocked": 1},
                        [],
                        "none",
                        [
                            behavior.MovementFailure(
                                "target",
                                "SegmentBlocked",
                                "target:42",
                                10,
                                20,
                                30,
                                100,
                                200,
                                300,
                            )
                        ],
                    )
                ],
            )
        ]

        try:
            behavior.write_metrics_csv(str(path), results)
            payload = path.read_text(encoding="utf-8")
        finally:
            path.unlink(missing_ok=True)

        self.assertIn("movement_failures", payload)
        self.assertIn("movement_failure_sample", payload)
        self.assertIn("target:SegmentBlocked 10,20,30->100,200,300", payload)

    def test_report_includes_movement_failure_section(self):
        path = Path("behavior-movement-failure-report-test.md")
        results = [
            behavior.DummyResult(
                "dummy001",
                ok=True,
                actions=3,
                rounds=1,
                successful_rounds=1,
                metrics=[
                    behavior.RoundMetric(
                        "dummy001",
                        1,
                        True,
                        3,
                        1.25,
                        "",
                        {"path_failed": 1},
                        [],
                        "none",
                        [
                            behavior.MovementFailure(
                                "waypoint",
                                "no nearby start graph node",
                                "waypoint:0:100:200:300",
                                10,
                                20,
                                30,
                                100,
                                200,
                                300,
                            )
                        ],
                    )
                ],
            )
        ]
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            concurrency=1,
            behavior_profile="cautious-solo",
            ai_player=False,
            hunter=True,
            combat=True,
            move=True,
            use_skills=True,
            recovery=False,
            party_size=1,
            ai_persona="auto",
            realm_strategy="fixed",
            realm=1,
            waypoints=[behavior.Waypoint(100, 200, 300)],
        )

        try:
            behavior.write_report_md(str(path), results, 1.25, args)
            payload = path.read_text(encoding="utf-8")
        finally:
            path.unlink(missing_ok=True)

        self.assertIn("## Movement Failures", payload)
        self.assertIn("no nearby start graph node", payload)
        self.assertIn("waypoint:0:100:200:300", payload)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
