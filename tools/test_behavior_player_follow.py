#!/usr/bin/env python3
"""Unit checks for behavior dummy player-follow selection."""

from __future__ import annotations

import importlib.util
import csv
import random
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


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


class AccountCsvTests(unittest.TestCase):
    def test_load_accounts_reads_position_seed_columns(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False) as handle:
            handle.write("username,password,realm,char_index,class_id,class_name,specs,start_x,start_y,start_z,zone_id\n")
            handle.write("midtest001,dummy-pass,2,0,26,Healer,Mending|40;Pacification|36,707611,1020259,3007,116\n")
            path = handle.name

        account = behavior.load_accounts(path, SimpleNamespace(realm=1, char_index=0))[0]

        self.assertEqual(account.username, "midtest001")
        self.assertEqual(account.realm, 2)
        self.assertEqual(account.class_id, 26)
        self.assertEqual(account.class_name, "Healer")
        self.assertEqual(account.specs, "Mending|40;Pacification|36")
        self.assertEqual(account.start_x, 707611)
        self.assertEqual(account.start_y, 1020259)
        self.assertEqual(account.start_z, 3007)
        self.assertEqual(account.zone_id, 116)

    def test_auto_train_command_uses_highest_configured_spec_line(self) -> None:
        command = behavior.auto_train_command_from_specs("Slash|1;Crush|50;Polearm|1", 5)

        self.assertEqual(command, "/train Crush 5")

    def test_auto_train_command_caps_to_configured_spec_level(self) -> None:
        command = behavior.auto_train_command_from_specs("Slash|3;Parry|1", 5)

        self.assertEqual(command, "/train Slash 3")

    def test_format_say_command_uses_player_say_slash_command(self) -> None:
        self.assertEqual(behavior.format_say_command("state: attacking wolf"), "/say state: attacking wolf")

    def test_format_say_command_normalizes_empty_and_long_messages(self) -> None:
        command = behavior.format_say_command("  hello   there  ", max_message_length=5)

        self.assertEqual(command, "/say hello")
        self.assertEqual(behavior.format_say_command(""), "/say ...")

    def test_live_control_overrides_runtime_tuning_fields(self) -> None:
        args = SimpleNamespace(
            max_target_distance=1500.0,
            max_target_level_delta=1,
            hunter_target_api_radius=2200.0,
            hunter_target_api_scout=False,
        )

        updates = behavior.apply_live_control_overrides(
            args,
            {
                "max-target-distance": "2100",
                "max-target-level-delta": "0",
                "hunter_target_api_radius": 3500,
                "hunter-target-api-scout": True,
                "unknown": 1,
            },
        )

        self.assertEqual(args.max_target_distance, 2100.0)
        self.assertEqual(args.max_target_level_delta, 0)
        self.assertEqual(args.hunter_target_api_radius, 3500.0)
        self.assertTrue(args.hunter_target_api_scout)
        self.assertEqual(
            set(updates),
            {"max_target_distance", "max_target_level_delta", "hunter_target_api_radius", "hunter_target_api_scout"},
        )


class FakeClient:
    def __init__(self, players: list[FakePlayer] | None = None, npcs: list[FakeNpc] | None = None) -> None:
        self.players = players or []
        self.npcs = npcs or []
        self.x = 0
        self.y = 0
        self.z = 0

    def visible_players(self, max_age: float = 30.0):
        return list(self.players)

    def visible_npcs(self, max_age: float = 60.0, include_peace: bool = False):
        return list(self.npcs)

    def distance_to(self, actor) -> float:
        return actor.distance

    def horizontal_distance_to(self, actor) -> float:
        return actor.distance


class FakeCombatClient:
    def __init__(self) -> None:
        self.health_percent = 100
        self.last_position_speed = 0.0
        self.spells: list[tuple[int, int]] = []
        self.skills: list[tuple[int, int]] = []
        self.spell_calls: list[dict[str, object]] = []
        self.skill_calls: list[dict[str, object]] = []
        self.position_updates: list[tuple[float, bool]] = []

    def send_position_update(self, speed: float = 0.0, target_in_view: bool = False) -> int:
        self.last_position_speed = speed
        self.position_updates.append((speed, target_in_view))
        return 0

    def use_spell(self, spell_level: int, spell_line_index: int = 0, **kwargs) -> None:
        self.spells.append((spell_level, spell_line_index))
        self.spell_calls.append(
            {
                "spell_level": spell_level,
                "spell_line_index": spell_line_index,
                **kwargs,
            }
        )

    def use_skill(self, skill_index: int, skill_type: int = 1, **kwargs) -> None:
        self.skills.append((skill_index, skill_type))
        self.skill_calls.append(
            {
                "skill_index": skill_index,
                "skill_type": skill_type,
                **kwargs,
            }
        )


class StartupServiceTests(unittest.TestCase):
    def test_startup_service_targets_interacts_buys_sells_equips_and_accepts(self) -> None:
        client = FakeClient(npcs=[FakeNpc(10, "Brother Willem", 23, 120.0), FakeNpc(11, "Other NPC", 1, 40.0)])
        calls = []
        client.read_packets_for = lambda seconds: calls.append(("read", seconds)) or []
        client.target_object = lambda object_id: calls.append(("target", object_id)) or 0
        client.interact_object = lambda object_id: calls.append(("interact", object_id)) or 0
        client.buy_item = lambda slot, count=1: calls.append(("buy", slot, count)) or 0
        client.sell_item = lambda slot: calls.append(("sell", slot)) or 0
        client.move_item = lambda from_slot, to_slot, count=1: calls.append(("move", from_slot, to_slot, count)) or 0
        client.accept_custom_dialog = lambda: calls.append(("dialog",)) or 0
        action_counts: dict[str, int] = {}

        actions = behavior.run_startup_service_actions(
            client,
            SimpleNamespace(
                startup_service_npc_name="willem",
                startup_service_scan_seconds=0.25,
                startup_service_interact=True,
                startup_service_buy_slot=[[3, 4]],
                startup_service_buy_count=2,
                startup_service_sell_slot=[[40]],
                startup_service_equip_slot=[[41]],
                startup_service_accept_dialog=True,
                npc_max_age=30.0,
            ),
            action_counts,
        )

        self.assertEqual(actions, 7)
        self.assertIn(("target", 10), calls)
        self.assertIn(("interact", 10), calls)
        self.assertIn(("buy", 3, 2), calls)
        self.assertIn(("buy", 4, 2), calls)
        self.assertIn(("sell", 40), calls)
        self.assertIn(("move", 41, 100, 1), calls)
        self.assertIn(("dialog",), calls)
        self.assertEqual(action_counts["startup_service_target"], 1)


class RequiredTargetApiTests(unittest.TestCase):
    def test_facegloc_command_uses_region_global_coordinates(self) -> None:
        self.assertEqual(behavior.facegloc_command_for_point(552595, 513584), "/facegloc 552595 513584")

    def make_args(self, **overrides):
        values = {
            "required_target_api_name": "",
            "require_target_name": "Fester",
            "prefer_target_name": "",
            "required_target_api_url": "",
            "required_target_api_limit": 20,
            "required_target_api_region": -1,
            "host": "127.0.0.1",
            "api_port": 5000,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_parse_required_target_observation_picks_matching_name(self) -> None:
        args = self.make_args(require_target_name="Fester")
        payload = [
            {"objectId": 11, "name": "diamondback toad", "x": 1, "y": 2, "z": 3, "level": 55},
            {
                "objectId": 11794,
                "name": "Fester",
                "x": 438166,
                "y": 384393,
                "z": 5176,
                "level": 64,
                "healthPercent": 67.89,
                "inCombat": True,
                "target": "Dummy414",
            },
        ]

        observed = behavior.parse_required_target_observation(args, payload)

        self.assertIsNotNone(observed)
        self.assertEqual(observed.object_id, 11794)
        self.assertEqual(observed.name, "Fester")
        self.assertEqual(observed.x, 438166)
        self.assertAlmostEqual(observed.health_percent, 67.89)
        self.assertTrue(observed.in_combat)

    def test_build_required_target_api_url_uses_region_and_exact_name(self) -> None:
        args = self.make_args(required_target_api_name="Lord Elidyn", required_target_api_region=1)

        url = behavior.build_required_target_api_url(args, region=73)

        self.assertIn("name=Lord+Elidyn", url)
        self.assertIn("region=1", url)
        self.assertIn("limit=20", url)


class PathClient:
    def __init__(self) -> None:
        self.x = 0
        self.y = 0
        self.z = 0
        self.zone_id = 1
        self.moves: list[tuple[int, int, int, float, float]] = []
        self.movement_speeds: list[float | None] = []

    def move_towards_position(
        self,
        x: int,
        y: int,
        z: int,
        step: float = 250.0,
        stop_distance: float = 250.0,
        **kwargs,
    ) -> bool:
        self.moves.append((x, y, z, step, stop_distance))
        self.movement_speeds.append(kwargs.get("movement_speed"))
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

    def move_towards_position(
        self,
        x: int,
        y: int,
        z: int,
        step: float = 250.0,
        stop_distance: float = 250.0,
        **kwargs,
    ) -> bool:
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


class CaptureGroundZClient(PathClient):
    def __init__(self) -> None:
        super().__init__()
        self.last_kwargs: dict[str, object] = {}

    def move_towards_position(
        self,
        x: int,
        y: int,
        z: int,
        step: float = 250.0,
        stop_distance: float = 250.0,
        **kwargs,
    ) -> bool:
        self.last_kwargs = dict(kwargs)
        return super().move_towards_position(x, y, z, step=step, stop_distance=stop_distance, **kwargs)


class FakeClientGrid:
    def __init__(self, route) -> None:
        self.route = route
        self.calls: list[tuple[int, int, int, int, int]] = []

    def find_path(self, zone_id: int, start_x: int, start_y: int, end_x: int, end_y: int):
        self.calls.append((zone_id, start_x, start_y, end_x, end_y))
        return self.route


class BehaviorPlayerFollowTests(unittest.TestCase):
    def test_parser_defaults_disable_random_turns(self):
        args = behavior.build_parser().parse_args([])

        self.assertEqual(args.turn_interval, 0.0)

    def test_parser_collects_startup_commands(self):
        args = behavior.build_parser().parse_args(["--startup-command", "/whisper Green Knight defend", "--startup-command", "/bow"])

        self.assertEqual(args.startup_command, ["/whisper Green Knight defend", "/bow"])

    def test_parser_accepts_required_target_home_point(self):
        args = behavior.build_parser().parse_args(["--required-target-home", "391326,755351,388"])

        self.assertEqual((args.required_target_home.x, args.required_target_home.y, args.required_target_home.z), (391326, 755351, 388))

    def test_required_target_home_destination_is_optional(self):
        args = SimpleNamespace(required_target_home=None)

        self.assertIsNone(behavior.required_target_home_destination(args))

    def test_required_target_home_destination_uses_named_objective_point(self):
        args = SimpleNamespace(required_target_home=behavior.Waypoint(391326, 755351, 388))

        destination = behavior.required_target_home_destination(args)

        self.assertIsNotNone(destination)
        self.assertEqual((destination.x, destination.y, destination.z), (391326, 755351, 388))
        self.assertTrue(destination.key.startswith("required-target-home:"))

    def test_flee_escape_destination_prefers_required_target_home(self):
        args = SimpleNamespace(required_target_home=behavior.Waypoint(391326, 755351, 388))

        destination = behavior.flee_escape_destination(args)

        self.assertIsNotNone(destination)
        self.assertEqual((destination.x, destination.y, destination.z), (391326, 755351, 388))
        self.assertTrue(destination.key.startswith("flee-home:"))

    def test_flee_escape_destination_prefers_explicit_flee_home(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(534900, 477500, 2200),
            required_target_home=behavior.Waypoint(560244, 532267, 2195),
            flee_dynamic_safe_point=False,
        )

        destination = behavior.flee_escape_destination(args)

        self.assertIsNotNone(destination)
        self.assertEqual((destination.x, destination.y, destination.z), (534900, 477500, 2200))
        self.assertTrue(destination.key.startswith("flee-home:"))

    def test_dynamic_flee_destination_runs_away_from_nearby_threats_before_town(self):
        threat = FakeNpc(10, "blackthorn", 6, 120.0)
        threat.x = 343334
        threat.y = 522935
        threat.z = 5379
        client = FakeClient(npcs=[threat])
        client.x = 343316
        client.y = 522884
        client.z = 5380
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=2500.0,
            flee_safe_point_distance=1800.0,
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            required_target_home=behavior.Waypoint(335600, 521600, 4959),
            npc_max_age=30.0,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        self.assertNotEqual((destination.x, destination.y, destination.z), (344500, 474500, 5372))
        before = behavior.horizontal_distance_between_points(client.x, client.y, threat.x, threat.y)
        after = behavior.horizontal_distance_between_points(destination.x, destination.y, threat.x, threat.y)
        self.assertGreater(after, before)

    def test_dynamic_flee_destination_falls_back_to_flee_home_without_threats(self):
        client = FakeClient(npcs=[])
        client.x = 343316
        client.y = 522884
        client.z = 5380
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=2500.0,
            flee_safe_point_distance=1800.0,
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            required_target_home=behavior.Waypoint(335600, 521600, 4959),
            npc_max_age=30.0,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertEqual((destination.x, destination.y, destination.z), (344500, 474500, 5372))
        self.assertTrue(destination.key.startswith("flee-home:"))

    def test_dynamic_flee_destination_avoids_higher_level_threat_zone(self):
        low_target = FakeNpc(10, "orchard nipper", 6, 280.0)
        low_target.x = 335448
        low_target.y = 521292
        low_target.z = 4911
        high_threat = FakeNpc(11, "cluricaun trip", 9, 1900.0)
        high_threat.x = 337617
        high_threat.y = 522467
        high_threat.z = 5130
        client = FakeClient(npcs=[low_target, high_threat])
        client.x = 335720
        client.y = 521630
        client.z = 4971
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=3200.0,
            flee_safe_point_distance=2200.0,
            player_level=6,
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            required_target_home=behavior.Waypoint(335600, 521600, 4959),
            npc_max_age=30.0,
            avoid_target_name="lough wolf,wild crouch,water beetle",
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        self.assertLess(destination.x, client.x)

    def test_should_flee_losing_combat_requires_low_health_and_pressure(self):
        args = SimpleNamespace(
            flee_health_percent=35,
            flee_min_combat_seconds=8.0,
            flee_min_damage_taken=20,
            flee_damage_taken_ratio=1.5,
        )
        active_combat = {
            "started": 10.0,
            "damage_done": 10,
            "damage_taken": 40,
        }

        self.assertTrue(behavior.should_flee_losing_combat(args, active_combat, health_percent=30, now=20.0))
        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=55, now=20.0))
        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=30, now=14.0))

        active_combat["damage_taken"] = 12
        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=30, now=20.0))

    def test_should_flee_rest_pressure_when_health_drops_while_resting(self):
        args = SimpleNamespace(
            flee_health_percent=35,
            low_health_rest_percent=65,
        )

        self.assertTrue(
            behavior.should_flee_rest_pressure(
                args,
                current_health_percent=50,
                last_health_percent=61,
                local_rescue_until=0.0,
                now=100.0,
            )
        )
        self.assertTrue(
            behavior.should_flee_rest_pressure(
                args,
                current_health_percent=34,
                last_health_percent=34,
                local_rescue_until=0.0,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_flee_rest_pressure(
                args,
                current_health_percent=62,
                last_health_percent=50,
                local_rescue_until=0.0,
                now=100.0,
            )
        )

    def test_should_flee_untracked_damage_when_target_is_lost(self):
        args = SimpleNamespace(flee_health_percent=55)

        self.assertTrue(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=48,
                last_health_percent=60,
                current_target=0,
                flee_until=0.0,
                now=10.0,
            )
        )
        self.assertFalse(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=48,
                last_health_percent=60,
                current_target=123,
                flee_until=0.0,
                now=10.0,
            )
        )
        self.assertFalse(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=58,
                last_health_percent=60,
                current_target=0,
                flee_until=0.0,
                now=10.0,
            )
        )
        self.assertFalse(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=48,
                last_health_percent=60,
                current_target=0,
                flee_until=12.0,
                now=10.0,
            )
        )

    def test_should_overrun_flee_home_when_still_hurt_at_home(self):
        args = SimpleNamespace(low_health_rest_resume_percent=88)

        self.assertTrue(behavior.should_overrun_flee_home(args, health_percent=40))
        self.assertFalse(behavior.should_overrun_flee_home(args, health_percent=90))
        self.assertFalse(behavior.should_overrun_flee_home(args, health_percent=0))

    def test_explicit_flee_home_does_not_overrun_to_random_wander(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(534900, 477500, 2200),
            low_health_rest_resume_percent=88,
        )

        self.assertFalse(behavior.should_overrun_flee_home(args, health_percent=40))

    def test_should_extend_flee_until_health_is_safe(self):
        args = SimpleNamespace(low_health_rest_resume_percent=88)

        self.assertTrue(behavior.should_extend_flee(args, health_percent=40, flee_until=100.0, now=101.0))
        self.assertFalse(behavior.should_extend_flee(args, health_percent=90, flee_until=100.0, now=101.0))
        self.assertFalse(behavior.should_extend_flee(args, health_percent=40, flee_until=100.0, now=99.0))

    def test_explicit_flee_home_extends_until_arrival(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            low_health_rest_resume_percent=88,
        )
        destination = behavior.flee_escape_destination(args)

        self.assertTrue(
            behavior.should_extend_flee(
                args,
                health_percent=100,
                flee_until=100.0,
                now=101.0,
                flee_destination=destination,
            )
        )
        self.assertFalse(
            behavior.should_extend_flee(
                args,
                health_percent=100,
                flee_until=100.0,
                now=101.0,
                flee_destination=None,
            )
        )

    def test_dynamic_flee_safe_point_does_not_extend_like_town_route(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            low_health_rest_resume_percent=88,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertFalse(
            behavior.should_extend_flee(
                args,
                health_percent=100,
                flee_until=100.0,
                now=101.0,
                flee_destination=destination,
            )
        )

    def test_dynamic_flee_safe_point_extends_while_health_is_still_low(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            low_health_rest_resume_percent=88,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertTrue(
            behavior.should_extend_flee(
                args,
                health_percent=40,
                flee_until=100.0,
                now=101.0,
                flee_destination=destination,
            )
        )

    def test_dynamic_flee_safe_point_replans_on_arrival_when_health_is_still_low(self):
        args = SimpleNamespace(low_health_rest_resume_percent=88)
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertTrue(behavior.should_replan_flee_safe_after_arrival(args, destination, health_percent=40))
        self.assertFalse(behavior.should_replan_flee_safe_after_arrival(args, destination, health_percent=90))
        self.assertFalse(
            behavior.should_replan_flee_safe_after_arrival(
                args,
                behavior.MovementDestination("flee-home:1", 344500, 474500, 5372),
                health_percent=40,
            )
        )

    def test_flee_safe_destination_uses_small_arrival_radius(self):
        args = SimpleNamespace(flee_home_stop_distance=900.0, path_node_arrival_distance=80.0)

        self.assertEqual(
            behavior.flee_destination_stop_distance(
                args,
                behavior.MovementDestination("flee-safe:1", 1000, 0, 0),
            ),
            80.0,
        )
        self.assertEqual(
            behavior.flee_destination_stop_distance(
                args,
                behavior.MovementDestination("flee-home:1", 1000, 0, 0),
            ),
            900.0,
        )

    def test_should_abort_rest_for_death_while_resting(self):
        self.assertTrue(behavior.should_abort_rest_for_death(is_dead=True, rest_until=100.0, now=90.0))
        self.assertFalse(behavior.should_abort_rest_for_death(is_dead=False, rest_until=100.0, now=90.0))
        self.assertFalse(behavior.should_abort_rest_for_death(is_dead=True, rest_until=100.0, now=101.0))

    def test_should_refresh_flee_wander_heading_only_after_hold(self):
        self.assertTrue(behavior.should_refresh_flee_wander_heading(now=10.0, hold_until=0.0))
        self.assertFalse(behavior.should_refresh_flee_wander_heading(now=10.0, hold_until=14.0))
        self.assertTrue(behavior.should_refresh_flee_wander_heading(now=14.0, hold_until=14.0))

    def test_party_leader_approaches_required_home_before_target_visible(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="Golestandt",
            party_encounter_mode="boss",
            required_target_home=behavior.Waypoint(391326, 755351, 388),
        )

        self.assertTrue(behavior.should_approach_required_target_home(args, is_party_leader=True, current_target=0))
        self.assertFalse(behavior.should_approach_required_target_home(args, is_party_leader=False, current_target=0))
        self.assertFalse(behavior.should_approach_required_target_home(args, is_party_leader=True, current_target=77))

    def test_party_assist_member_approaches_required_home_before_ready_pull(self):
        args = SimpleNamespace(
            party_assist_only=True,
            party_min_ready=2,
            party_size=2,
            required_target_home=behavior.Waypoint(391326, 755351, 388),
        )

        self.assertTrue(behavior.should_approach_required_target_home(args, is_party_leader=False, current_target=0))
        self.assertFalse(behavior.should_approach_required_target_home(args, is_party_leader=False, current_target=77))

    def test_party_leader_does_not_idle_wander_while_holding_required_home(self):
        args = SimpleNamespace(
            wander=True,
            party_assist_only=True,
            require_target_name="Golestandt",
            party_encounter_mode="boss",
            required_target_home=behavior.Waypoint(391326, 755351, 388),
        )

        self.assertFalse(behavior.should_idle_wander(args, is_party_leader=True, current_target=0))
        self.assertTrue(behavior.should_idle_wander(args, is_party_leader=False, current_target=0))
        self.assertTrue(behavior.should_idle_wander(args, is_party_leader=True, current_target=77))

    def test_required_filter_keeps_shared_objective_when_rejecting_rescue_target(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="Moran the Mighty",
            party_encounter_mode="boss",
        )
        snapshot = {"leader_target_id": 100}

        self.assertFalse(
            behavior.should_clear_leader_target_after_required_filter(args, snapshot, rejected_target_id=200)
        )
        self.assertTrue(
            behavior.should_clear_leader_target_after_required_filter(args, snapshot, rejected_target_id=100)
        )

    def test_standard_filter_rejection_clears_leader_target(self):
        args = SimpleNamespace(
            party_assist_only=False,
            require_target_name="",
            party_encounter_mode="standard",
        )

        self.assertTrue(
            behavior.should_clear_leader_target_after_required_filter(args, {"leader_target_id": 100}, rejected_target_id=200)
        )

    def test_parser_collects_target_start_commands(self):
        args = behavior.build_parser().parse_args(["--target-start-command", "/whisper defend", "--target-start-command", "/bow"])

        self.assertEqual(args.target_start_command, ["/whisper defend", "/bow"])

    def test_target_start_command_runs_once_per_target(self):
        args = SimpleNamespace(target_start_command=["/whisper defend"])
        sent_targets = {77}

        self.assertTrue(behavior.should_send_target_start_commands(args, current_target=77, sent_target_start_command_targets=set()))
        self.assertFalse(behavior.should_send_target_start_commands(args, current_target=77, sent_target_start_command_targets=sent_targets))
        self.assertFalse(behavior.should_send_target_start_commands(args, current_target=0, sent_target_start_command_targets=set()))

    def test_parser_defaults_to_standard_party_encounter_mode(self):
        args = behavior.build_parser().parse_args([])

        self.assertEqual(args.party_encounter_mode, "standard")

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

    def test_choose_hunter_target_respects_required_home_radius(self):
        args = SimpleNamespace(
            max_target_level=3,
            player_level=1,
            max_target_level_delta=2,
            ideal_target_level=1,
            prefer_target_name="",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=1,
            max_target_distance=6000.0,
            target_auto_lowest_visible_level=False,
            allow_avoid_target_fallback=False,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=behavior.Waypoint(1000, 1000, 0),
            target_home_max_distance=1500.0,
        )
        near = FakeNpc(1, "near piglet", 1, 800.0)
        near.x = 1800
        near.y = 1000
        far = FakeNpc(2, "far piglet", 1, 500.0)
        far.x = 4000
        far.y = 1000
        client = FakeClient(npcs=[far, near])

        selected = behavior.choose_hunter_target(client, random.Random(1), args, {}, {}, now=100.0)

        self.assertEqual(selected.object_id, near.object_id)

    def test_choose_hunter_target_uses_avoided_target_only_as_fallback(self):
        args = SimpleNamespace(
            max_target_level=3,
            player_level=1,
            max_target_level_delta=2,
            ideal_target_level=1,
            prefer_target_name="",
            require_target_name="",
            avoid_target_name="risky",
            npc_max_age=30.0,
            min_target_level=1,
            max_target_distance=6000.0,
            target_auto_lowest_visible_level=False,
            allow_avoid_target_fallback=True,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=None,
            target_home_max_distance=0.0,
        )
        safe = FakeNpc(1, "safe piglet", 1, 1200.0)
        risky = FakeNpc(2, "risky piglet", 1, 100.0)

        selected = behavior.choose_hunter_target(FakeClient(npcs=[risky, safe]), random.Random(1), args, {}, {}, now=100.0)
        self.assertEqual(selected.object_id, safe.object_id)

        selected = behavior.choose_hunter_target(FakeClient(npcs=[risky]), random.Random(1), args, {}, {}, now=100.0)
        self.assertEqual(selected.object_id, risky.object_id)

    def test_choose_current_visible_target_keeps_active_target(self):
        current = FakeNpc(42, "current piglet", 1, 900.0)
        other = FakeNpc(77, "closer ant", 1, 120.0)

        selected = behavior.choose_current_visible_target([other, current], 42)

        self.assertEqual(selected.object_id, 42)

    def test_active_combat_last_known_destination_uses_target_position(self):
        active_combat = {
            "target_id": 42,
            "target_name": "current piglet",
            "target_level": 1,
            "target_x": 123,
            "target_y": 456,
            "target_z": 789,
        }

        destination = behavior.active_combat_last_known_destination(active_combat)

        self.assertEqual(destination.x, 123)
        self.assertEqual(destination.y, 456)
        self.assertEqual(destination.z, 789)

    def test_classify_combat_server_message_marks_korean_too_far(self):
        categories = behavior.classify_combat_server_message("boar piglet은(는) 너무 멀어 공격할 수 없습니다!")

        self.assertIn("out_of_range", categories)

    def test_classify_combat_server_message_marks_korean_not_visible(self):
        categories = behavior.classify_combat_server_message("boar piglet이(가) 시야에 없습니다!")

        self.assertIn("not_visible", categories)

    def test_server_los_failure_grace_has_fast_retarget_default(self):
        args = behavior.build_parser().parse_args([])

        self.assertEqual(args.server_los_failure_grace, 8.0)

    def test_server_los_failure_kind_cooldown_defaults_to_object_only(self):
        args = behavior.build_parser().parse_args([])

        self.assertEqual(args.server_los_failure_kind_cooldown, 0.0)

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

    def test_continuous_waypoints_advance_before_stop_radius(self):
        args = SimpleNamespace(
            waypoint_continuous_turns=True,
            waypoint_advance_distance=0.0,
            waypoint_stop_distance=50.0,
            waypoint_mode="loop",
            waypoints=[
                behavior.Waypoint(100, 100, 0),
                behavior.Waypoint(200, 100, 0),
                behavior.Waypoint(200, 200, 0),
            ],
        )
        client = SimpleNamespace(x=108, y=102, z=0)

        index = behavior.advance_continuous_waypoint_index(client, args, 0)

        self.assertEqual(index, 1)

    def test_continuous_waypoints_do_not_advance_when_far(self):
        args = SimpleNamespace(
            waypoint_continuous_turns=True,
            waypoint_advance_distance=25.0,
            waypoint_stop_distance=50.0,
            waypoint_mode="loop",
            waypoints=[
                behavior.Waypoint(100, 100, 0),
                behavior.Waypoint(200, 100, 0),
            ],
        )
        client = SimpleNamespace(x=140, y=100, z=0)

        index = behavior.advance_continuous_waypoint_index(client, args, 0)

        self.assertEqual(index, 0)

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
            require_target_name="",
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
            require_target_name="",
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
            require_target_name="",
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

    def test_hunter_can_require_target_name_for_boss_runs(self):
        args = SimpleNamespace(
            npc_max_age=60.0,
            include_peace_npcs=False,
            player_level=50,
            ideal_target_level=59,
            min_target_level=59,
            max_target_level=59,
            max_target_level_delta=0,
            max_target_distance=0.0,
            target_pool=5,
            target_selection="smart",
            target_level_weight=120.0,
            target_distance_weight=120.0,
            target_randomness=0.0,
            prefer_target_name="",
            require_target_name="lord elidyn",
            avoid_target_name="",
            prefer_target_bonus=300.0,
        )
        npcs = [
            FakeNpc(1, "Ellyl hero", 59, 100),
            FakeNpc(2, "Lord Elidyn", 59, 300),
        ]

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=npcs),
            behavior.random.Random(1),
            args,
            rejected_targets={},
            rejected_target_kinds={},
            now=100.0,
        )

        self.assertEqual(selected.name, "Lord Elidyn")

    def test_melee_stop_distance_stays_inside_attack_range(self):
        args = SimpleNamespace(attack_range=120.0, melee_range_buffer=25.0, minimum_melee_stop_distance=70.0)

        self.assertEqual(behavior.melee_stop_distance(args), 95.0)

    def test_melee_attack_mode_waits_until_melee_stop_distance(self):
        args = SimpleNamespace(
            attack_range=350.0,
            melee_range_buffer=250.0,
            minimum_melee_stop_distance=70.0,
            melee_stick_attack=False,
            melee_stick_attack_distance=1200.0,
        )

        self.assertFalse(behavior.should_enable_attack_mode(args, "melee-basic", 145.0))
        self.assertTrue(behavior.should_enable_attack_mode(args, "melee-basic", 100.0))
        self.assertTrue(behavior.should_enable_attack_mode(args, "melee-basic", 120.0))

    def test_combat_distance_uses_horizontal_distance_when_available(self):
        client = SimpleNamespace(
            x=1000,
            y=1000,
            z=5000,
            horizontal_distance_to=lambda _actor: 100.0,
            distance_to=lambda _actor: 4901.0,
        )
        actor = SimpleNamespace(x=1060, y=1080, z=100)

        self.assertEqual(behavior.combat_distance_to(client, actor), 100.0)

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

    def test_flee_safe_destination_uses_direct_emergency_move_before_graph_route(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "danger-road", "x": 1000, "y": 0, "z": 0},
                            {"id": "goal", "x": 1000, "y": -1000, "z": 0},
                        ],
                        "edges": [
                            {"from": "start", "to": "danger-road"},
                            {"from": "danger-road", "to": "goal"},
                        ],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=60.0,
            path_max_node_distance=1200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            flee_safe_point_distance=1200.0,
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        client = PathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("flee-safe:1", 1000, -1000, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
            movement_speed=360.0,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (1000, -1000, 0))
        self.assertEqual(client.movement_speeds[-1], 360.0)
        self.assertEqual(action_counts["flee_safe_direct_move"], 1)
        self.assertNotIn("path_plan", action_counts)

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

    def test_required_target_home_applies_to_solo_growth_runner(self):
        args = SimpleNamespace(
            party_size=1,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=900.0,
            required_target_preserve_on_loss=True,
        )
        client = PathClient()

        self.assertTrue(behavior.should_approach_required_target_home(args, is_party_leader=False, current_target=0))
        self.assertFalse(behavior.required_target_home_reached(client, args))

        client.x = 200
        self.assertTrue(behavior.required_target_home_reached(client, args))

    def test_party_member_ready_for_pull_requires_required_home_range(self):
        args = SimpleNamespace(
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=100.0,
            required_target_home_hunt_distance=300.0,
            target_home_max_distance=0.0,
        )
        client = SimpleNamespace(x=0, y=0, z=0)

        self.assertFalse(behavior.party_member_ready_for_pull(client, args))
        client.x = 750
        self.assertTrue(behavior.party_member_ready_for_pull(client, args))

    def test_required_home_movement_stops_when_hunt_ready_even_if_stop_not_reached(self):
        args = SimpleNamespace(
            party_size=2,
            party_assist_only=True,
            party_min_ready=2,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=100.0,
            required_target_home_hunt_distance=300.0,
            target_home_max_distance=0.0,
        )
        client = SimpleNamespace(x=750, y=0, z=0)

        self.assertFalse(
            behavior.should_move_to_required_target_home(client, args, is_party_leader=False, current_target=0)
        )

        client.x = 500
        self.assertTrue(behavior.should_move_to_required_target_home(client, args, is_party_leader=False, current_target=0))

    def test_target_home_leash_rejects_targets_that_drag_combat_out_of_camp(self):
        args = SimpleNamespace(
            required_target_home=behavior.Waypoint(1000, 1000, 0),
            combat_home_leash_distance=500.0,
        )
        client = SimpleNamespace(x=1200, y=1000, z=0)
        npc = SimpleNamespace(x=1701, y=1000, z=0)

        violated, reason, distance = behavior.target_home_leash_violation(client, args, npc)

        self.assertTrue(violated)
        self.assertEqual(reason, "target")
        self.assertGreater(distance, 500.0)

    def test_target_home_leash_rejects_player_that_chases_too_far_from_camp(self):
        args = SimpleNamespace(
            required_target_home=behavior.Waypoint(1000, 1000, 0),
            combat_home_leash_distance=500.0,
        )
        client = SimpleNamespace(x=1601, y=1000, z=0)
        npc = SimpleNamespace(x=1100, y=1000, z=0)

        violated, reason, distance = behavior.target_home_leash_violation(client, args, npc)

        self.assertTrue(violated)
        self.assertEqual(reason, "player")
        self.assertGreater(distance, 500.0)

    def test_overextended_combat_abort_only_applies_to_unproven_chase(self):
        args = SimpleNamespace(combat_chase_max_distance=1600.0, combat_chase_max_distance_grace=3.0)

        self.assertFalse(behavior.should_abort_overextended_combat(args, None, 1500.0, 10.0))
        self.assertFalse(behavior.should_abort_overextended_combat(args, None, 2000.0, 1.0))
        self.assertFalse(
            behavior.should_abort_overextended_combat(
                args,
                {"damage_done": 1, "damage_taken": 0},
                2000.0,
                10.0,
            )
        )
        self.assertTrue(behavior.should_abort_overextended_combat(args, {"damage_done": 0, "damage_taken": 0}, 2000.0, 10.0))

    def test_destination_change_clears_stale_route_before_nav_fallback(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "target", "x": 1000, "y": 0, "z": 0},
                        ],
                        "edges": [{"from": "start", "to": "target"}],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="http://127.0.0.1:5000",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            nav_segment_validate=True,
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        state.destination_key = "waypoint:old"
        state.follower.set_route([behavior.PathPoint(0, 1000, 0)])
        client = PathClient()
        action_counts: dict[str, int] = {}
        original_request_nav_path = behavior.request_nav_path

        def fake_request_nav_path(_args, _region, _start, _goal):
            return behavior.NavPathResult(False, "NavmeshUnavailable", [])

        behavior.request_nav_path = fake_request_nav_path

        try:
            outcome = behavior.move_towards_destination(
                client,
                behavior.MovementDestination("target:14001", 1000, 0, 0),
                step=250.0,
                stop_distance=100.0,
                args=args,
                path_state=state,
                action_counts=action_counts,
            )
        finally:
            behavior.request_nav_path = original_request_nav_path

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (1000, 0, 0))
        self.assertEqual(action_counts["nav_path_failed"], 1)
        self.assertEqual(action_counts["path_plan"], 1)
        self.assertEqual(action_counts["path_step"], 1)

    def test_path_step_does_not_snap_to_waypoint_ground_z_mid_segment(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 100},
                            {"id": "bend", "x": 0, "y": 1000, "z": 80},
                            {"id": "goal", "x": 1000, "y": 1000, "z": 75},
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
        client = CaptureGroundZClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("target:1", 1000, 1000, 75),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (0, 1000, 80))
        self.assertNotIn("ground_z", client.last_kwargs)

    def test_same_xy_stale_waypoint_z_is_skipped(self):
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=60.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            path_waypoint_ground_z_skip_delta=500,
        )
        state = behavior.PathMovementState(
            behavior.PathGraph(),
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=2500.0),
        )
        state.destination_key = "target:stale-z"
        state.resolved_goal = behavior.PathPoint(1000, 0, -300)
        state.follower.set_route([
            behavior.PathPoint(0, 0, -300),
            behavior.PathPoint(1000, 0, -300),
        ])
        client = PathClient()
        client.z = 120
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("target:stale-z", 1000, 0, -300),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (1000, 0, -300))
        self.assertEqual(action_counts["path_waypoint_ground_z_skip"], 1)
        self.assertEqual(action_counts["path_step"], 1)

    def test_close_xy_large_waypoint_z_delta_is_not_skipped(self):
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=60.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=160.0,
            path_max_edge_length=1500.0,
            path_waypoint_ground_z_skip_delta=80,
        )
        state = behavior.PathMovementState(
            behavior.PathGraph(),
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=2500.0),
        )
        state.destination_key = "target:downhill"
        state.resolved_goal = behavior.PathPoint(1000, 0, 0)
        state.follower.set_route([
            behavior.PathPoint(50, 0, -180),
            behavior.PathPoint(1000, 0, 0),
        ])
        client = PathClient()
        client.z = 0
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("target:downhill", 1000, 0, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (50, 0, -180))
        self.assertNotIn("path_waypoint_ground_z_skip", action_counts)

    def test_path_arrival_snaps_to_goal_ground_z(self):
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=60.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(behavior.PathGraph(), 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        client = CaptureGroundZClient()
        client.x = 100
        client.y = 100
        client.z = 60
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("target:arrive", 100, 150, 95),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertFalse(outcome.moved)
        self.assertTrue(outcome.arrived)
        self.assertNotIn("ground_z", client.last_kwargs)
        self.assertNotIn("snap_ground_z_on_stop", client.last_kwargs)

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
            return behavior.NavPathResult(False, "NavmeshUnavailable", [])

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
                points = [
                    behavior.PathPoint(500, 0, 0),
                    behavior.PathPoint(1000, 0, 0),
                ]
                return behavior.NavPathResult(True, "PathFound", points, snapped_end=points[-1])

            return behavior.NavPathResult(False, "SegmentBlocked", [])

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

    def test_target_destination_uses_nav_resolved_route_before_direct_last_mile(self):
        args = SimpleNamespace(
            nav_api_url="http://127.0.0.1:5000",
            path_last_mile_distance=1500.0,
            path_replan_interval=0.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            nav_segment_validate=False,
        )
        state = behavior.PathMovementState(None, 1, behavior.PathSafety(max_direct_distance=1500.0, max_edge_length=1500.0))
        client = PathClient()
        action_counts: dict[str, int] = {}
        original_request_nav_path = behavior.request_nav_path

        def fake_request_nav_path(_args, _region, _start, _goal):
            points = [
                behavior.PathPoint(500, 0, 80),
                behavior.PathPoint(1000, 0, 80),
            ]
            return behavior.NavPathResult(True, "PathFound", points, snapped_end=points[-1])

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

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (500, 0, 80))
        self.assertEqual(action_counts["nav_path_plan"], 1)

    def test_graph_path_can_move_when_navmesh_is_unavailable(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "goal", "x": 1000, "y": 0, "z": 0},
                        ],
                        "edges": [{"from": "start", "to": "goal"}],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="http://127.0.0.1:5000",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            nav_segment_validate=True,
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        client = StepPathClient()
        action_counts: dict[str, int] = {}
        original_request_nav_path = behavior.request_nav_path

        def fake_request_nav_path(_args, _region, _start, _goal):
            return behavior.NavPathResult(False, "NavmeshUnavailable", [])

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

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (1000, 0, 0))
        self.assertEqual(action_counts["nav_path_failed"], 1)
        self.assertEqual(action_counts["path_plan"], 1)
        self.assertEqual(action_counts["path_step"], 1)
        self.assertNotIn("nav_segment_blocked", action_counts)

    def test_stale_unsafe_graph_step_replans_without_movement_failure(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "mid", "x": 0, "y": 500, "z": 0},
                            {"id": "goal", "x": 0, "y": 1000, "z": 0},
                            {"id": "stale", "x": 2000, "y": 0, "z": 0},
                        ],
                        "edges": [
                            {"from": "start", "to": "mid"},
                            {"from": "mid", "to": "goal"},
                        ],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=600.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=600.0,
            nav_segment_validate=False,
            movement_speed=None,
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=600.0))
        state.destination_key = "waypoint:goal"
        state.follower.set_route([behavior.PathPoint(2000, 0, 0)])
        client = StepPathClient()
        action_counts: dict[str, int] = {}
        failures: list[behavior.MovementFailure] = []

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("waypoint:goal", 0, 1000, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )
        behavior.record_movement_failure(
            failures,
            client,
            behavior.MovementDestination("waypoint:goal", 0, 1000, 0),
            outcome,
            "waypoint",
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (0, 500, 0))
        self.assertEqual(action_counts["path_blocked"], 1)
        self.assertEqual(action_counts["path_plan"], 1)
        self.assertEqual(action_counts["path_step"], 1)
        self.assertEqual(failures, [])

    def test_client_grid_path_moves_when_navmesh_and_graph_are_unavailable(self):
        route = SimpleNamespace(
            ok=True,
            status="PathFound",
            points=[
                behavior.PathPoint(500, 0, 80),
                behavior.PathPoint(1000, 0, 80),
            ],
        )
        grid = FakeClientGrid(route)
        args = SimpleNamespace(
            nav_api_url="http://127.0.0.1:5000",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            nav_segment_validate=True,
        )
        state = behavior.PathMovementState(
            None,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0),
            client_grid=grid,
        )
        client = StepPathClient()
        action_counts: dict[str, int] = {}
        original_request_nav_path = behavior.request_nav_path

        def fake_request_nav_path(_args, _region, _start, _goal):
            return behavior.NavPathResult(False, "NavmeshUnavailable", [])

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

        self.assertTrue(outcome.moved)
        self.assertEqual(grid.calls, [(1, 0, 0, 1000, 0)])
        self.assertEqual(client.moves[-1][:3], (500, 0, 80))
        self.assertEqual(action_counts["nav_path_failed"], 1)
        self.assertEqual(action_counts["client_grid_path_plan"], 1)
        self.assertEqual(action_counts["path_step"], 1)

    def test_navmesh_unavailable_target_uses_direct_last_mile_when_graph_has_no_goal_node(self):
        args = SimpleNamespace(
            nav_api_url="http://127.0.0.1:5000",
            path_last_mile_distance=1200.0,
            path_replan_interval=0.0,
            path_max_node_distance=100.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            nav_segment_validate=True,
            movement_speed=None,
            movement_update_interval=0.0,
        )
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                        ],
                        "edges": [],
                    }
                }
            }
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=1200.0, max_edge_length=1500.0, max_height_delta=2500.0),
        )
        client = StepPathClient()
        client.x = 0
        client.y = 0
        client.z = 0
        action_counts: dict[str, int] = {}
        original_request_nav_path = behavior.request_nav_path

        def fake_request_nav_path(_args, _region, _start, _goal):
            return behavior.NavPathResult(False, "NavmeshUnavailable", [])

        behavior.request_nav_path = fake_request_nav_path

        try:
            outcome = behavior.move_towards_destination(
                client,
                behavior.MovementDestination("target:near", 500, 0, 0),
                step=250.0,
                stop_distance=95.0,
                args=args,
                path_state=state,
                action_counts=action_counts,
            )
        finally:
            behavior.request_nav_path = original_request_nav_path

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (500, 0, 0))
        self.assertEqual(action_counts["nav_path_failed"], 1)
        self.assertEqual(action_counts["path_direct_fallback"], 1)
        self.assertNotIn("path_failed", action_counts)

    def test_route_end_before_last_mile_clears_stale_route_for_replan(self):
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
        )
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "goal", "x": 1000, "y": 0, "z": 0},
                        ],
                        "edges": [{"from": "start", "to": "goal"}],
                    }
                }
            }
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        state.follower.set_route([behavior.PathPoint(0, 0, 0)])
        state.destination_key = "target:stale"
        state.last_plan_at = 1.0
        client = PathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("target:stale", 1000, 0, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertFalse(outcome.moved)
        self.assertEqual(outcome.reason, "route ended before last mile")
        self.assertEqual(state.follower.route, [])
        self.assertEqual(state.destination_key, "")

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
            return behavior.NavPathResult(False, "LastMileBlocked", [])

        behavior.request_nav_path = fake_request_nav_path

        try:
            outcome = behavior.move_towards_destination(
                client,
                behavior.MovementDestination("waypoint:near", 1000, 0, 0),
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

    def test_metrics_csv_includes_class_metadata(self):
        path = Path("behavior-class-metadata-test.csv")
        results = [
            behavior.DummyResult(
                "albtest005",
                ok=True,
                rounds=1,
                successful_rounds=1,
                metrics=[
                    behavior.RoundMetric(
                        "albtest005",
                        1,
                        True,
                        3,
                        1.25,
                        "",
                        {},
                        [],
                        "none",
                        [],
                        [],
                        0,
                        0,
                        0,
                        0,
                        5,
                        "Theurgist",
                        "Earth Magic|45;Ice Magic|25;Wind Magic|8",
                    )
                ],
            )
        ]

        try:
            behavior.write_metrics_csv(str(path), results)
            payload = path.read_text(encoding="utf-8")
        finally:
            path.unlink(missing_ok=True)

        self.assertIn("username,class_id,class_name,specs,round", payload)
        self.assertIn("albtest005,5,Theurgist", payload)

    def test_metrics_csv_counts_death_detected_as_player_death(self):
        path = Path("behavior-death-detected-test.csv")
        results = [
            behavior.DummyResult(
                "hibtest001",
                ok=True,
                rounds=1,
                successful_rounds=1,
                metrics=[
                    behavior.RoundMetric(
                        "hibtest001",
                        1,
                        True,
                        3,
                        1.25,
                        "",
                        {"death_detected": 1},
                        [],
                    )
                ],
            )
        ]

        try:
            behavior.write_metrics_csv(str(path), results)
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
        finally:
            path.unlink(missing_ok=True)

        self.assertEqual(rows[0]["player_deaths"], "1")
        self.assertEqual(rows[0]["action_death_detected"], "1")

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

    def test_loot_message_parser_detects_random_item_tiers(self):
        rare = behavior.parse_loot_message("희귀: 숲지기의 장검을(를) 얻어 가방에 넣었습니다.")
        mythic = behavior.parse_loot_message("신화: 별빛 반지를 얻어 가방에 넣었습니다.")
        article = behavior.parse_loot_message("a 마력: Focus Staff을(를) 얻어 가방에 넣었습니다.")
        party_broadcast = behavior.parse_loot_message("Dummy040이(가) a 마력: Edgebender Plate Arms을(를) 얻어 가방에 넣었습니다.")
        damage = behavior.parse_loot_message("당신은 12 피해를 입혔습니다.")

        self.assertEqual(rare.item_name, "희귀: 숲지기의 장검")
        self.assertEqual(rare.tier, "희귀")
        self.assertEqual(mythic.item_name, "신화: 별빛 반지")
        self.assertEqual(mythic.tier, "신화")
        self.assertEqual(article.item_name, "a 마력: Focus Staff")
        self.assertEqual(article.tier, "마력")
        self.assertIsNone(party_broadcast)
        self.assertIsNone(damage)

    def test_combat_text_metric_parser_tracks_damage_and_healing_amounts(self):
        self.assertEqual(behavior.parse_combat_text_metric("당신은 123 피해를 입혔습니다."), ("damage_done", 123))
        self.assertEqual(
            behavior.parse_combat_text_metric("공격합니다이(가) boar piglet 당신의 sword하여 5 (-1) 피해를 입혔습니다!"),
            ("damage_done", 5),
        )
        self.assertEqual(behavior.parse_combat_text_metric("당신은 45 피해를 받았습니다."), ("damage_taken", 45))
        self.assertEqual(
            behavior.parse_combat_text_metric("drakulv executioner이(가) 당신의 몸통에게 195 (-27) 피해를 입혔습니다!"),
            ("damage_taken", 195),
        )
        self.assertEqual(behavior.parse_combat_text_metric("You hit Ellyll froglord for 67 damage!"), ("damage_done", 67))
        self.assertEqual(behavior.parse_combat_text_metric("Ellyll froglord hits you for 89 damage!"), ("damage_taken", 89))
        self.assertEqual(behavior.parse_combat_text_metric("당신은 Dummy040을 150 회복시켰습니다."), ("healing_done", 150))
        self.assertEqual(behavior.parse_combat_text_metric("You heal Dummy040 for 160 hit points."), ("healing_done", 160))
        self.assertEqual(behavior.parse_combat_text_metric("자신의 생명력을 155점 회복했습니다."), ("healing_done", 155))
        self.assertEqual(behavior.parse_combat_text_metric("Dummy040의 생명력을 156점 회복했습니다!"), ("healing_done", 156))
        self.assertEqual(behavior.parse_combat_text_metric("추가로 생명력 20점을 회복했습니다! (10%)"), ("healing_done", 20))
        self.assertEqual(behavior.parse_combat_text_metric("Dummy041이(가) 당신의 생명력을 157점 회복했습니다."), ("healing_received", 157))
        self.assertEqual(behavior.parse_combat_text_metric("You are healed by Dummy041 for 158 hit points."), ("healing_received", 158))
        self.assertEqual(behavior.parse_combat_text_metric("Dummy041 heals you for 159 hit points."), ("healing_received", 159))
        self.assertIsNone(behavior.parse_combat_text_metric("희귀: 숲지기의 장검을 얻었습니다."))

    def test_korean_incoming_damage_parser_extracts_attacker_name(self):
        self.assertEqual(
            behavior.parse_incoming_damage_attacker_name("drakulv executioner이(가) 당신의 다리에게 223 (-5) 피해를 입혔습니다!"),
            "drakulv executioner",
        )
        self.assertEqual(
            behavior.parse_korean_incoming_damage_amount("drakulv executioner이(가) 당신의 다리에게 223 (-5) 피해를 입혔습니다!"),
            223,
        )
        self.assertEqual(behavior.parse_incoming_damage_attacker_name("당신은 123 피해를 입혔습니다."), "")

    def test_party_state_returns_buff_targets_with_known_object_ids(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "dps"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=1, y=2, z=3))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=4, y=5, z=6))
        state.update_member("dps", SimpleNamespace(player_object_id=12, health_percent=100, x=7, y=8, z=9))

        targets = state.buff_targets(exclude_name="cleric")

        self.assertEqual([target["name"] for target in targets], ["leader", "dps"])
        self.assertEqual([target["object_id"] for target in targets], [10, 12])

    def test_party_state_records_rescue_target_for_tank(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "dps"])
        attacker = SimpleNamespace(object_id=99, name="add mob", x=100, y=200, z=300, level=54)
        boss = SimpleNamespace(object_id=77, name="boss", x=101, y=201, z=301, level=59)

        self.assertTrue(state.request_rescue("cleric", attacker, leader_target_id=77))
        self.assertEqual(state.snapshot()["rescue_target_id"], 99)
        self.assertEqual(state.snapshot()["rescue_member_name"], "cleric")

        self.assertFalse(state.request_rescue("dps", boss, leader_target_id=77))
        self.assertEqual(state.snapshot()["rescue_target_id"], 99)

        state.clear_rescue_target(99)
        self.assertEqual(state.snapshot()["rescue_target_id"], 0)

    def test_report_includes_loot_summary(self):
        path = Path("dummy-report-loot-test.md")
        results = [
            behavior.DummyResult(
                "dummy001",
                ok=True,
                actions=2,
                rounds=1,
                successful_rounds=1,
                metrics=[
                    behavior.RoundMetric(
                        "dummy001",
                        1,
                        True,
                        2,
                        1.25,
                        "",
                        {"loot_acquired": 2},
                        [],
                        "none",
                        [],
                        [
                            behavior.LootMetric("희귀: 숲지기의 장검", "희귀"),
                            behavior.LootMetric("전설: 달빛 망토", "전설"),
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
            waypoints=[],
        )

        try:
            behavior.write_report_md(str(path), results, 1.25, args)
            payload = path.read_text(encoding="utf-8")
        finally:
            path.unlink(missing_ok=True)

        self.assertIn("## Loot Summary", payload)
        self.assertIn("희귀: 숲지기의 장검", payload)
        self.assertIn("전설: 달빛 망토", payload)

    def test_party_slot_rotations_override_mixed_strategy(self):
        args = SimpleNamespace(
            party_slot_rotations=["melee-basic", "melee-burst", "healer-support"],
            action_rotation="auto",
            party_size=6,
            party_role_strategy="mixed",
            behavior_profile="custom",
        )

        self.assertEqual(behavior.resolve_action_rotation(args, 0), "melee-basic")
        self.assertEqual(behavior.resolve_action_rotation(args, 1), "melee-burst")
        self.assertEqual(behavior.resolve_action_rotation(args, 2), "healer-support")
        self.assertEqual(behavior.resolve_action_rotation(args, 4), "melee-burst")

    def test_effective_rotation_replaces_healer_without_heal_spells_with_caster(self):
        args = SimpleNamespace(allow_unvalidated_spells=False, allow_unvalidated_skills=False)
        plan = behavior.CombatUsablePlan(
            attack_spells=[
                behavior.UsableSpellRef(
                    line_index=2,
                    spell_level=35,
                    name="Smite",
                    level=35,
                )
            ]
        )

        self.assertEqual(behavior.resolve_effective_action_rotation(args, "healer-support", plan, True), "caster-basic")

    def test_effective_rotation_replaces_melee_without_styles_with_caster(self):
        args = SimpleNamespace(allow_unvalidated_spells=False, allow_unvalidated_skills=False)
        plan = behavior.CombatUsablePlan(
            attack_spells=[
                behavior.UsableSpellRef(
                    line_index=3,
                    spell_level=44,
                    name="Lifetap",
                    level=44,
                )
            ]
        )

        self.assertEqual(behavior.resolve_effective_action_rotation(args, "melee-burst", plan, True), "caster-basic")

    def test_effective_rotation_keeps_requested_role_when_plan_not_loaded(self):
        args = SimpleNamespace(allow_unvalidated_spells=False, allow_unvalidated_skills=False)

        self.assertEqual(behavior.resolve_effective_action_rotation(args, "healer-support", behavior.CombatUsablePlan(), False), "healer-support")

    def test_combat_plan_exposes_taunt_skills_for_tank_reaggro(self):
        plan = behavior.parse_combat_usable_plan(
            {
                "skills": [
                    {"kind": "Style", "useSkillIndex": 1, "useSkillType": 1, "name": "Slash", "level": 50},
                    {"kind": "Style", "useSkillIndex": 2, "useSkillType": 1, "name": "Provoke", "level": 15},
                ]
            }
        )

        self.assertEqual([skill.name for skill in plan.taunt_skills], ["Provoke"])

    def test_party_assist_target_requires_leader_target(self):
        npcs = [FakeNpc(10, "one", 40, 100.0), FakeNpc(20, "two", 40, 150.0)]

        self.assertIsNone(behavior.choose_party_assist_target(npcs, 0))
        self.assertIsNone(behavior.choose_party_assist_target(npcs, 999))
        self.assertEqual(behavior.choose_party_assist_target(npcs, 20).name, "two")

    def test_party_shared_target_refreshes_required_boss_coordinates(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "dps"])
        boss = FakeNpc(77, "King of the Barfog Hills", 80, 100.0)
        boss.x = 445069
        boss.y = 378519
        boss.z = 6897
        state.update_shared_target(boss, engaged=True)
        first = state.snapshot()

        boss.x = 444611
        boss.y = 377353
        boss.z = 6810
        state.update_shared_target(boss, engaged=True)
        second = state.snapshot()

        self.assertEqual(second["leader_target_id"], 77)
        self.assertEqual((second["leader_target_x"], second["leader_target_y"], second["leader_target_z"]), (444611, 377353, 6810))
        self.assertGreater(second["leader_target_updated_at"], first["leader_target_updated_at"])
        self.assertEqual(second["leader_target_engaged_at"], first["leader_target_engaged_at"])

    def test_required_boss_target_loss_is_preservable_from_active_combat(self):
        args = SimpleNamespace(party_assist_only=True, require_target_name="king of the barfog hills")
        active = {"target_name": "King of the Barfog Hills", "target_level": 80}

        self.assertTrue(behavior.should_preserve_party_target_on_loss(args))
        self.assertTrue(behavior.active_combat_matches_required_target(args, active))
        self.assertFalse(behavior.active_combat_matches_required_target(args, {"target_name": "forest add", "target_level": 45}))

    def test_required_boss_target_loss_is_preservable_from_party_target_id(self):
        args = SimpleNamespace(party_assist_only=True, require_target_name="king of the barfog hills")
        state = behavior.PartyState("leader", ["leader", "member"])
        boss = FakeNpc(77, "King of the Barfog Hills", 65, 100.0)
        state.update_shared_target(boss)

        self.assertTrue(behavior.should_preserve_current_party_target(args, state, 77, None))
        self.assertFalse(behavior.should_preserve_current_party_target(args, state, 78, None))

    def test_required_boss_current_target_survives_empty_party_target_if_combat_matches(self):
        args = SimpleNamespace(party_assist_only=True, require_target_name="king of the barfog hills")
        active = {"target_name": "King of the Barfog Hills", "target_level": 65}

        self.assertTrue(behavior.should_preserve_unshared_party_target(args, 77, active))
        self.assertFalse(behavior.should_preserve_unshared_party_target(args, 0, active))
        self.assertFalse(behavior.should_preserve_unshared_party_target(args, 77, {"target_name": "forest add"}))

    def test_removed_party_target_preserve_allows_short_visible_loss_under_limit(self):
        args = SimpleNamespace(party_target_loss_grace=4.0, party_target_removed_preserve_limit=3)

        self.assertTrue(behavior.target_removed_preserve_allowed(args, now=10.0, last_visible_at=7.0, preserve_count=2))

    def test_removed_party_target_preserve_expires_after_hidden_too_long(self):
        args = SimpleNamespace(party_target_loss_grace=4.0, party_target_removed_preserve_limit=3)

        self.assertFalse(behavior.target_removed_preserve_allowed(args, now=10.1, last_visible_at=6.0, preserve_count=0))

    def test_removed_party_target_preserve_stops_after_repeated_remove_events(self):
        args = SimpleNamespace(party_target_loss_grace=4.0, party_target_removed_preserve_limit=3)

        self.assertFalse(behavior.target_removed_preserve_allowed(args, now=10.0, last_visible_at=9.0, preserve_count=3))

    def test_required_boss_scans_peaceful_npcs_after_aggro_reset(self):
        required = SimpleNamespace(party_assist_only=True, require_target_name="king of the barfog hills", include_peace_npcs=False)
        normal = SimpleNamespace(party_assist_only=False, require_target_name="", include_peace_npcs=False)
        explicit = SimpleNamespace(party_assist_only=False, require_target_name="", include_peace_npcs=True)

        self.assertTrue(behavior.should_scan_peace_npcs(required))
        self.assertFalse(behavior.should_scan_peace_npcs(normal))
        self.assertTrue(behavior.should_scan_peace_npcs(explicit))

    def test_party_rescue_attacker_ignores_leader_target_and_distance(self):
        npcs = [
            FakeNpc(10, "boss", 60, 100.0),
            FakeNpc(20, "add near", 45, 250.0),
            FakeNpc(30, "add far", 45, 1800.0),
        ]
        args = SimpleNamespace(
            npc_max_age=60.0,
            include_peace_npcs=False,
            party_rescue_max_distance=1000.0,
            party_rescue_engaged_distance=300.0,
            require_target_name="boss",
        )

        selected = behavior.choose_party_rescue_attacker(FakeClient(npcs=npcs), args, leader_target_id=10)
        self.assertEqual(selected.object_id, 20)

    def test_local_rescue_target_prefers_nearby_non_boss_threat(self):
        npcs = [
            FakeNpc(10, "Green Knight", 79, 100.0),
            FakeNpc(20, "rotting downy felwood near", 47, 300.0),
            FakeNpc(30, "rotting downy felwood far", 47, 1300.0),
        ]
        args = SimpleNamespace(
            require_target_name="green knight",
            party_local_rescue_max_distance=1200.0,
            party_rescue_engaged_distance=350.0,
        )

        selected = behavior.choose_local_rescue_target(npcs, FakeClient(npcs=npcs), args, leader_target_id=10)

        self.assertEqual(selected.object_id, 20)

    def test_local_rescue_target_keeps_current_add_when_still_dangerous(self):
        npcs = [
            FakeNpc(20, "rotting downy felwood current", 47, 500.0),
            FakeNpc(30, "rotting downy felwood closer", 47, 100.0),
        ]
        args = SimpleNamespace(
            require_target_name="green knight",
            party_local_rescue_max_distance=1200.0,
            party_rescue_engaged_distance=600.0,
        )

        selected = behavior.choose_local_rescue_target(npcs, FakeClient(npcs=npcs), args, leader_target_id=10, current_target=20)

        self.assertEqual(selected.object_id, 20)

    def test_local_rescue_ignores_non_boss_outside_close_threat_distance(self):
        npcs = [
            FakeNpc(10, "Lord Elidyn", 59, 100.0),
            FakeNpc(20, "ellyll guard", 50, 430.0),
        ]
        args = SimpleNamespace(
            require_target_name="lord elidyn",
            party_local_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
        )

        self.assertIsNone(behavior.choose_local_rescue_target(npcs, FakeClient(npcs=npcs), args, leader_target_id=10))

    def test_support_evasion_picks_nearest_recent_rescue_threat(self):
        adds = [
            FakeNpc(20, "granite giant oracle", 60, 350.0),
            FakeNpc(21, "granite giant stonelord", 60, 220.0),
        ]
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True},
                {"object_id": 21, "requested_at": now - 1.0, "objective_add": True},
            ],
        }
        args = SimpleNamespace(
            party_support_evasion=True,
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=900.0,
            require_target_name="moran the mighty",
        )

        selected = behavior.choose_party_support_evasion_threat(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            action_rotation="healer-support",
            now=now,
            local_rescue_until=now + 4.0,
        )

        self.assertEqual(selected.object_id, 21)

    def test_support_evasion_accepts_combat_proven_objective_add_outside_close_rescue_distance(self):
        add = FakeNpc(20, "granite giant stonelord", 60, 1800.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "leader_target_engaged_at": now - 10.0,
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True},
            ],
        }
        args = SimpleNamespace(
            require_target_name="golestandt",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_support_evasion=True,
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=900.0,
        )

        selected = behavior.choose_party_support_evasion_threat(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            action_rotation="healer-support",
            now=now,
            local_rescue_until=now + 4.0,
        )

        self.assertEqual(selected, add)

    def test_support_evasion_still_rejects_far_ambient_rescue_threat(self):
        add = FakeNpc(20, "granite giant stonelord", 60, 1800.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "leader_target_engaged_at": now - 10.0,
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": False},
            ],
        }
        args = SimpleNamespace(
            require_target_name="golestandt",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_support_evasion=True,
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=900.0,
        )

        selected = behavior.choose_party_support_evasion_threat(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            action_rotation="healer-support",
            now=now,
            local_rescue_until=now + 4.0,
        )

        self.assertIsNone(selected)

    def test_support_evasion_accepts_objective_add_without_local_damage_window(self):
        add = FakeNpc(20, "granite giant oracle", 60, 220.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "leader_target_engaged_at": now - 10.0,
            "rescue_threats": [{"object_id": 20, "requested_at": now - 1.0, "objective_add": True}],
        }
        args = SimpleNamespace(
            party_assist_only=True,
            party_encounter_mode="boss",
            party_support_evasion=True,
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=900.0,
            require_target_name="moran the mighty",
        )

        self.assertEqual(
            behavior.choose_party_support_evasion_threat(
                [add],
                FakeClient(npcs=[add]),
                args,
                snapshot,
                action_rotation="caster-basic",
                now=now,
                local_rescue_until=0.0,
            ),
            add,
        )

    def test_support_evasion_still_requires_recent_window_for_ambient_threat(self):
        add = FakeNpc(20, "granite giant oracle", 60, 220.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "leader_target_engaged_at": now - 10.0,
            "rescue_threats": [{"object_id": 20, "requested_at": now - 1.0, "objective_add": False}],
        }
        args = SimpleNamespace(
            party_assist_only=True,
            party_encounter_mode="boss",
            party_support_evasion=True,
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=900.0,
            require_target_name="moran the mighty",
        )

        self.assertIsNone(
            behavior.choose_party_support_evasion_threat(
                [add],
                FakeClient(npcs=[add]),
                args,
                snapshot,
                action_rotation="caster-basic",
                now=now,
                local_rescue_until=0.0,
            )
        )

    def test_support_evasion_overrides_precast_movement_hold_for_nearby_adds(self):
        add = FakeNpc(20, "granite giant oracle", 60, 220.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "leader_target_engaged_at": now - 10.0,
            "rescue_threats": [{"object_id": 20, "requested_at": now - 1.0, "objective_add": True}],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_support_evasion=True,
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=900.0,
        )

        self.assertEqual(
            behavior.choose_party_support_evasion_threat(
                [add],
                FakeClient(npcs=[add]),
                args,
                snapshot,
                action_rotation="caster-basic",
                now=now,
                local_rescue_until=now + 4.0,
                precast_movement_hold=True,
            ),
            add,
        )

    def test_support_evasion_smooth_movement_runs_without_current_target(self):
        args = SimpleNamespace(party_support_evasion=True, party_rescue_aggro=True)

        self.assertTrue(behavior.should_run_smooth_combat_movement(args, "caster-basic", 0, object()))
        self.assertTrue(behavior.should_run_smooth_combat_movement(args, "healer-support", 0, object()))
        self.assertFalse(behavior.should_run_smooth_combat_movement(args, "melee-basic", 0, object()))
        self.assertFalse(behavior.should_run_smooth_combat_movement(args, "caster-basic", 0, None))

    def test_support_evasion_is_disabled_by_default(self):
        add = FakeNpc(20, "granite giant oracle", 60, 220.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "rescue_threats": [{"object_id": 20, "requested_at": now - 1.0, "objective_add": True}],
        }
        args = SimpleNamespace(
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=900.0,
            require_target_name="moran the mighty",
        )

        self.assertIsNone(
            behavior.choose_party_support_evasion_threat(
                [add],
                FakeClient(npcs=[add]),
                args,
                snapshot,
                action_rotation="healer-support",
                now=now,
                local_rescue_until=now + 4.0,
            )
        )

    def test_healer_local_rescue_is_disabled_during_required_boss(self):
        args = SimpleNamespace(
            party_local_rescue_target=True,
            party_assist_only=True,
            require_target_name="moran the mighty",
            party_encounter_mode="boss",
            party_healer_local_rescue_health_percent=35,
        )

        self.assertFalse(behavior.should_party_member_use_local_rescue_target(args, "healer-support", 20))

    def test_party_rescue_attacker_uses_close_threat_distance(self):
        npcs = [
            FakeNpc(10, "Lord Elidyn", 59, 100.0),
            FakeNpc(20, "ellyll guard far", 50, 430.0),
            FakeNpc(30, "ellyll guard close", 50, 240.0),
        ]
        args = SimpleNamespace(
            require_target_name="lord elidyn",
            npc_max_age=30.0,
            include_peace_npcs=False,
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
        )

        selected = behavior.choose_party_rescue_attacker(FakeClient(npcs=npcs), args, leader_target_id=10)

        self.assertEqual(selected.object_id, 30)

    def test_party_rescue_attacker_accepts_add_near_shared_objective(self):
        boss = FakeNpc(10, "Mouth", 65, 100.0)
        near_objective_add = FakeNpc(20, "Mouth's minion", 56, 900.0)
        far_add = FakeNpc(30, "unrelated guard", 50, 700.0)
        boss.x = 1000
        boss.y = 1000
        near_objective_add.x = 1250
        near_objective_add.y = 1110
        far_add.x = 4000
        far_add.y = 4000
        args = SimpleNamespace(
            require_target_name="mouth",
            npc_max_age=30.0,
            include_peace_npcs=False,
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
            party_rescue_objective_max_distance=450.0,
        )
        snapshot = {"leader_target_id": 10, "leader_target_x": 1000, "leader_target_y": 1000}

        selected = behavior.choose_party_rescue_attacker(
            FakeClient(npcs=[boss, near_objective_add, far_add]),
            args,
            leader_target_id=10,
            party_snapshot=snapshot,
        )

        self.assertEqual(selected.object_id, 20)

    def test_party_rescue_attacker_rejects_ambient_mob_near_shared_objective(self):
        boss = FakeNpc(10, "Fester", 64, 100.0)
        ambient = FakeNpc(20, "diamondback toad", 52, 900.0)
        boss.x = 1000
        boss.y = 1000
        ambient.x = 1250
        ambient.y = 1110
        args = SimpleNamespace(
            require_target_name="fester",
            npc_max_age=30.0,
            include_peace_npcs=False,
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
            party_rescue_objective_max_distance=450.0,
        )
        snapshot = {"leader_target_id": 10, "leader_target_name": "Fester", "leader_target_x": 1000, "leader_target_y": 1000}

        selected = behavior.choose_party_rescue_attacker(
            FakeClient(npcs=[boss, ambient]),
            args,
            leader_target_id=10,
            party_snapshot=snapshot,
        )

        self.assertIsNone(selected)

    def test_party_rescue_attacker_rejects_foreign_test_clone_near_objective(self):
        boss = FakeNpc(10, "KDAOC_TEST_mid_assist5_8", 80, 100.0)
        foreign_clone = FakeNpc(20, "KDAOC_TEST_mid_radius2600_8", 80, 200.0)
        boss.x = 1000
        boss.y = 1000
        foreign_clone.x = 1100
        foreign_clone.y = 1050
        args = SimpleNamespace(
            require_target_name="KDAOC_TEST_mid_assist5_8",
            npc_max_age=30.0,
            include_peace_npcs=False,
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
            party_rescue_objective_max_distance=450.0,
        )
        snapshot = {
            "leader_target_id": 10,
            "leader_target_name": "KDAOC_TEST_mid_assist5_8",
            "leader_target_x": 1000,
            "leader_target_y": 1000,
        }

        selected = behavior.choose_party_rescue_attacker(
            FakeClient(npcs=[boss, foreign_clone]),
            args,
            leader_target_id=10,
            party_snapshot=snapshot,
        )

        self.assertIsNone(selected)

    def test_party_objective_scan_rejects_close_ambient_mob(self):
        boss = FakeNpc(10, "Fester", 64, 100.0)
        ambient = FakeNpc(20, "diamondback toad", 52, 200.0)
        boss.x = 1000
        boss.y = 1000
        ambient.x = 1050
        ambient.y = 1050
        args = SimpleNamespace(
            require_target_name="fester",
            npc_max_age=30.0,
            include_peace_npcs=False,
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
            party_rescue_objective_max_distance=450.0,
        )
        snapshot = {"leader_target_id": 10, "leader_target_name": "Fester", "leader_target_x": 1000, "leader_target_y": 1000}

        selected = behavior.choose_party_rescue_attacker(
            FakeClient(npcs=[boss, ambient]),
            args,
            leader_target_id=10,
            party_snapshot=snapshot,
            objective_scan_only=True,
        )

        self.assertIsNone(selected)

    def test_party_objective_scan_accepts_boss_named_add(self):
        boss = FakeNpc(10, "Mouth", 65, 100.0)
        add = FakeNpc(20, "Mouth's minion", 56, 900.0)
        boss.x = 1000
        boss.y = 1000
        add.x = 1250
        add.y = 1110
        args = SimpleNamespace(
            require_target_name="mouth",
            npc_max_age=30.0,
            include_peace_npcs=False,
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
            party_rescue_objective_max_distance=450.0,
        )
        snapshot = {"leader_target_id": 10, "leader_target_name": "Mouth", "leader_target_x": 1000, "leader_target_y": 1000}

        selected = behavior.choose_party_rescue_attacker(
            FakeClient(npcs=[boss, add]),
            args,
            leader_target_id=10,
            party_snapshot=snapshot,
            objective_scan_only=True,
        )

        self.assertEqual(selected.object_id, 20)

    def test_party_rescue_attacker_rejects_far_add_outside_close_and_objective_distance(self):
        boss = FakeNpc(10, "Mouth", 65, 100.0)
        far_add = FakeNpc(30, "unrelated guard", 50, 700.0)
        boss.x = 1000
        boss.y = 1000
        far_add.x = 4000
        far_add.y = 4000
        args = SimpleNamespace(
            require_target_name="mouth",
            npc_max_age=30.0,
            include_peace_npcs=False,
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
            party_rescue_objective_max_distance=450.0,
        )
        snapshot = {"leader_target_id": 10, "leader_target_x": 1000, "leader_target_y": 1000}

        selected = behavior.choose_party_rescue_attacker(
            FakeClient(npcs=[boss, far_add]),
            args,
            leader_target_id=10,
            party_snapshot=snapshot,
        )

        self.assertIsNone(selected)

    def test_parse_party_attack_message_extracts_attacker_and_member_victim(self):
        attack = behavior.parse_party_attack_message(
            "granite giant oracle attacks Dummy417 and hits!",
            ["Dummy040", "Dummy417"],
        )

        self.assertIsNotNone(attack)
        self.assertEqual(attack.attacker_name, "granite giant oracle")
        self.assertEqual(attack.victim_name, "Dummy417")

    def test_parse_party_attack_message_ignores_non_party_victim(self):
        attack = behavior.parse_party_attack_message(
            "granite giant oracle attacks random traveler and hits!",
            ["Dummy040", "Dummy417"],
        )

        self.assertIsNone(attack)

    def test_attack_message_rescue_accepts_message_proven_add_outside_close_distance(self):
        boss = FakeNpc(10, "Moran the Mighty", 73, 100.0)
        add = FakeNpc(20, "granite giant oracle", 60, 800.0)
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_rescue_max_distance=1400.0,
        )

        selected = behavior.choose_attack_message_rescue_attacker(
            [boss, add],
            FakeClient(npcs=[boss, add]),
            args,
            leader_target_id=10,
            attacker_name="granite giant oracle",
        )

        self.assertEqual(selected.object_id, 20)

    def test_attack_message_rescue_rejects_required_boss_attack(self):
        boss = FakeNpc(10, "Moran the Mighty", 73, 100.0)
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_rescue_max_distance=1400.0,
        )

        selected = behavior.choose_attack_message_rescue_attacker(
            [boss],
            FakeClient(npcs=[boss]),
            args,
            leader_target_id=10,
            attacker_name="Moran the Mighty",
        )

        self.assertIsNone(selected)

    def test_named_rescue_attacker_accepts_korean_damage_attacker(self):
        boss = FakeNpc(10, "Gjalpinulva", 80, 100.0)
        add = FakeNpc(20, "drakulv executioner", 65, 800.0)
        args = SimpleNamespace(
            require_target_name="Gjalpinulva",
        )

        selected = behavior.choose_named_rescue_attacker(
            [boss, add],
            FakeClient(npcs=[boss, add]),
            args,
            leader_target_id=10,
            attacker_name="drakulv executioner",
        )

        self.assertEqual(selected.object_id, 20)

    def test_korean_damage_refreshes_exact_rescue_threat_as_combat_proven_encounter_add(self):
        boss = FakeNpc(10, "Gjalpinulva", 80, 100.0)
        boss.x = 1000
        boss.y = 1000
        add = FakeNpc(20, "drakulv executioner", 65, 800.0)
        add.x = 1200
        add.y = 1000
        state = behavior.PartyState("Tank", ["Tank", "Healer"])
        state.update_shared_target(boss, engaged=True)
        args = SimpleNamespace(
            require_target_name="Gjalpinulva",
            npc_max_age=60.0,
            party_rescue_min_hold=5.0,
            party_rescue_objective_max_distance=650.0,
            required_target_add_name="drakulv",
        )

        refreshed = behavior.refresh_exact_rescue_threat_from_attacker_name(
            state,
            FakeClient(npcs=[boss, add]),
            args,
            "Healer",
            "drakulv executioner",
        )

        snapshot = state.snapshot()
        self.assertTrue(refreshed)
        self.assertEqual(snapshot["rescue_target_id"], 20)
        self.assertEqual(snapshot["rescue_member_name"], "Healer")
        self.assertTrue(snapshot["rescue_target_objective_add"])

    def test_korean_damage_does_not_promote_combat_add_before_boss_engaged(self):
        boss = FakeNpc(10, "Gjalpinulva", 80, 100.0)
        add = FakeNpc(20, "drakulv executioner", 65, 800.0)
        state = behavior.PartyState("Tank", ["Tank", "Healer"])
        state.update_shared_target(boss, engaged=False)
        args = SimpleNamespace(
            require_target_name="Gjalpinulva",
            npc_max_age=60.0,
            party_rescue_min_hold=5.0,
            party_rescue_objective_max_distance=650.0,
            required_target_add_name="",
        )

        refreshed = behavior.refresh_exact_rescue_threat_from_attacker_name(
            state,
            FakeClient(npcs=[boss, add]),
            args,
            "Healer",
            "drakulv executioner",
        )

        snapshot = state.snapshot()
        self.assertTrue(refreshed)
        self.assertEqual(snapshot["rescue_target_id"], 20)
        self.assertFalse(snapshot["rescue_target_objective_add"])

    def test_local_rescue_role_policy_keeps_support_and_casters_out_by_default(self):
        args = SimpleNamespace(
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_healer_local_rescue_health_percent=0,
            party_rescue_assist_after=0.0,
        )

        self.assertTrue(behavior.should_party_member_use_local_rescue_target(args, "melee-burst", 100))
        self.assertFalse(behavior.should_party_member_use_local_rescue_target(args, "caster-basic", 100))
        self.assertFalse(behavior.should_party_member_use_local_rescue_target(args, "healer-support", 20))

    def test_local_rescue_can_allow_caster_chase_with_explicit_opt_in(self):
        args = SimpleNamespace(
            party_local_rescue_target=True,
            party_caster_assist_rescue_target=True,
            party_healer_local_rescue_health_percent=0,
        )

        self.assertTrue(behavior.should_party_member_use_local_rescue_target(args, "caster-basic", 100))

    def test_local_rescue_can_allow_critical_healer_self_defense(self):
        args = SimpleNamespace(
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_healer_local_rescue_health_percent=25,
            party_rescue_assist_after=0.0,
        )

        self.assertTrue(behavior.should_party_member_use_local_rescue_target(args, "healer-support", 20))
        self.assertFalse(behavior.should_party_member_use_local_rescue_target(args, "healer-support", 80))

    def test_local_rescue_window_only_active_after_recent_damage(self):
        self.assertTrue(behavior.local_rescue_window_active(10.0, 12.0))
        self.assertFalse(behavior.local_rescue_window_active(13.0, 12.0))
        self.assertFalse(behavior.local_rescue_window_active(10.0, 0.0))

    def test_party_rescue_target_bypasses_required_boss_filter(self):
        args = SimpleNamespace(require_target_name="green knight")

        self.assertTrue(behavior.should_accept_party_rescue_target(args, FakeNpc(20, "rotting downy felwood", 49, 250.0)))
        self.assertFalse(behavior.passes_required_target_filter(args, FakeNpc(20, "rotting downy felwood", 49, 250.0)))

    def test_required_filter_does_not_reject_rescue_target(self):
        args = SimpleNamespace(require_target_name="green knight")
        add = FakeNpc(20, "rotting downy felwood", 49, 250.0)

        self.assertFalse(behavior.should_reject_selected_target_for_required_filter(args, add, selected_npc_is_rescue=True))
        self.assertTrue(behavior.should_reject_selected_target_for_required_filter(args, add, selected_npc_is_rescue=False))

    def test_pre_objective_add_target_picks_nearby_non_required_npc(self):
        objective = FakeNpc(10, "Moran the Mighty", 73, 800.0)
        objective.x = 1000
        objective.y = 1000
        nearby_add = FakeNpc(20, "granite giant stonelord", 60, 200.0)
        nearby_add.x = 1300
        nearby_add.y = 1000
        far_add = FakeNpc(21, "granite giant elder", 60, 100.0)
        far_add.x = 4000
        far_add.y = 1000
        args = SimpleNamespace(
            require_target_name="Moran the Mighty",
            party_clear_objective_adds_before_engage=True,
            party_rescue_objective_max_distance=950.0,
        )

        selected = behavior.choose_pre_objective_add_target(
            [objective, far_add, nearby_add],
            FakeClient(npcs=[objective, far_add, nearby_add]),
            args,
            objective,
        )

        self.assertEqual(selected.object_id, 20)

    def test_pre_objective_add_target_is_disabled_without_flag(self):
        objective = FakeNpc(10, "Moran the Mighty", 73, 800.0)
        add = FakeNpc(20, "granite giant stonelord", 60, 200.0)
        args = SimpleNamespace(
            require_target_name="Moran the Mighty",
            party_clear_objective_adds_before_engage=False,
            party_rescue_objective_max_distance=950.0,
        )

        self.assertIsNone(behavior.choose_pre_objective_add_target([objective, add], FakeClient(), args, objective))

    def test_pre_objective_add_target_can_use_required_home_before_boss_visible(self):
        nearby_add = FakeNpc(20, "granite giant stonelord", 60, 200.0)
        nearby_add.x = 1300
        nearby_add.y = 1000
        far_add = FakeNpc(21, "granite giant elder", 60, 100.0)
        far_add.x = 4000
        far_add.y = 1000
        args = SimpleNamespace(
            require_target_name="Moran the Mighty",
            required_target_home=SimpleNamespace(x=1000, y=1000, z=500),
            party_clear_objective_adds_before_engage=True,
            party_rescue_objective_max_distance=950.0,
        )

        selected = behavior.choose_pre_objective_add_target(
            [far_add, nearby_add],
            FakeClient(npcs=[far_add, nearby_add]),
            args,
            None,
        )

        self.assertEqual(selected.object_id, 20)

    def test_rescue_target_does_not_replace_party_objective(self):
        self.assertFalse(behavior.should_update_party_objective_target(selected_npc_is_rescue=True))
        self.assertTrue(behavior.should_update_party_objective_target(selected_npc_is_rescue=False))

    def test_removed_rescue_target_is_not_preserved_as_required_objective(self):
        args = SimpleNamespace(party_assist_only=True, require_target_name="green knight", party_encounter_mode="boss")
        state = behavior.PartyState("Dummy040", ["Dummy040", "Dummy041"])
        add = FakeNpc(20, "rotting downy felwood", 49, 250.0)
        self.assertTrue(state.request_rescue("Dummy041", add, leader_target_id=10))

        self.assertFalse(behavior.should_preserve_current_party_target(args, state, 20, None))

    def test_target_start_command_skips_rescue_targets(self):
        args = SimpleNamespace(require_target_name="green knight")
        boss = FakeNpc(10, "Green Knight", 79, 500.0)
        add = FakeNpc(20, "rotting downy felwood", 49, 250.0)

        self.assertTrue(behavior.should_send_target_start_command_for_npc(args, boss, selected_npc_is_rescue=False))
        self.assertFalse(behavior.should_send_target_start_command_for_npc(args, add, selected_npc_is_rescue=True))
        self.assertFalse(behavior.should_send_target_start_command_for_npc(args, add, selected_npc_is_rescue=False))

    def test_dead_dummy_suppresses_position_heartbeat(self):
        self.assertFalse(behavior.should_send_position_heartbeat_for_client(SimpleNamespace(is_dead=True)))
        self.assertTrue(behavior.should_send_position_heartbeat_for_client(SimpleNamespace(is_dead=False)))

    def test_headless_client_does_not_send_position_when_dead(self):
        client = behavior.HeadlessDaocClient("127.0.0.1", 10300, 1.0, verbose=False)
        client.is_dead = True

        def fail_send_packet(*args, **kwargs):
            raise AssertionError("dead clients must not send position packets")

        client.send_packet = fail_send_packet

        self.assertEqual(client.send_position_update(speed=120.0, target_in_view=True), 0)

    def test_dead_disconnect_is_completed_round(self):
        self.assertTrue(
            behavior.should_treat_disconnect_as_completed(BrokenPipeError(), SimpleNamespace(is_dead=True), False)
        )
        self.assertTrue(
            behavior.should_treat_disconnect_as_completed(ConnectionResetError(), SimpleNamespace(is_dead=False), True)
        )
        self.assertFalse(
            behavior.should_treat_disconnect_as_completed(BrokenPipeError(), SimpleNamespace(is_dead=False), False)
        )

    def test_party_rescue_target_respects_min_hold(self):
        state = behavior.PartyState("Dummy040", ["Dummy040", "Dummy041"])
        first = FakeNpc(20, "rotting downy felwood", 49, 250.0)
        second = FakeNpc(21, "rotting downy felwood", 49, 300.0)

        self.assertTrue(state.request_rescue("Dummy041", first, leader_target_id=10, min_hold=5.0))
        self.assertFalse(state.request_rescue("Dummy041", second, leader_target_id=10, min_hold=5.0))
        snapshot = state.snapshot()
        threat_ids = {int(threat["object_id"]) for threat in snapshot["rescue_threats"]}
        self.assertEqual(snapshot["rescue_target_id"], 20)
        self.assertEqual(threat_ids, {20, 21})

    def test_party_rescue_target_can_refresh_same_target_during_hold(self):
        state = behavior.PartyState("Dummy040", ["Dummy040", "Dummy041"])
        first = FakeNpc(20, "rotting downy felwood", 49, 250.0)
        moved = FakeNpc(20, "rotting downy felwood", 49, 200.0)
        moved.x = 11
        moved.y = 22

        self.assertTrue(state.request_rescue("Dummy041", first, leader_target_id=10, min_hold=5.0))
        first_requested_at = state.snapshot()["rescue_requested_at"]
        self.assertTrue(state.request_rescue("Dummy041", moved, leader_target_id=10, min_hold=5.0))
        snapshot = state.snapshot()
        self.assertEqual(snapshot["rescue_target_id"], 20)
        self.assertEqual(snapshot["rescue_target_x"], 11)
        self.assertEqual(snapshot["rescue_requested_at"], first_requested_at)

    def test_party_state_records_multiple_rescue_threats_while_primary_is_held(self):
        state = behavior.PartyState("Dummy040", ["Dummy040", "Dummy041", "Dummy042"])
        first = FakeNpc(20, "granite giant oracle", 60, 250.0)
        second = FakeNpc(21, "granite giant stonelord", 60, 300.0)

        self.assertTrue(state.request_rescue("Dummy041", first, leader_target_id=10, min_hold=5.0))
        self.assertTrue(state.record_rescue_threat("Dummy042", second, objective_add=True))

        snapshot = state.snapshot()
        threat_ids = {int(threat["object_id"]) for threat in snapshot["rescue_threats"]}
        self.assertEqual(snapshot["rescue_target_id"], 20)
        self.assertEqual(threat_ids, {20, 21})

    def test_party_rescue_target_age_uses_recent_threat_refresh(self):
        snapshot = {
            "rescue_requested_at": 100.0,
            "rescue_threats": [
                {"object_id": 20, "requested_at": 118.0, "objective_add": False, "member_name": "Dummy041"},
            ],
        }

        self.assertEqual(behavior.party_rescue_target_age(snapshot, 20, 120.0), 2.0)
        self.assertEqual(behavior.party_rescue_target_age(snapshot, 21, 120.0), 20.0)

    def test_party_state_updates_boss_focus_from_attack_message(self):
        state = behavior.PartyState("Dummy040", ["Dummy040", "Dummy041", "Dummy042"])
        boss = FakeNpc(10, "Golestandt", 80, 1000.0)
        state.update_shared_target(boss, engaged=True)

        self.assertTrue(state.update_leader_target_focus_from_attack("Golestandt", "Dummy042"))
        snapshot = state.snapshot()

        self.assertEqual(snapshot["leader_target_focus_name"], "Dummy042")
        self.assertGreater(snapshot["leader_target_focus_updated_at"], 0)

    def test_party_state_snapshot_exposes_members_for_rescue_distribution(self):
        state = behavior.PartyState("Dummy040", ["Dummy040", "Dummy041"])
        leader = FakeClient()
        leader.session_id = 1
        leader.player_object_id = 1001
        leader.health_percent = 100
        leader.heading = 512
        leader.x = 11
        leader.y = 22
        leader.z = 33
        member = FakeClient()
        member.session_id = 2
        member.player_object_id = 1002
        member.health_percent = 75
        member.heading = 1024
        member.x = 44
        member.y = 55
        member.z = 66

        state.update_leader(leader)
        state.update_member("Dummy041", member)
        state.update_member_role("Dummy041", "melee-burst")

        members = state.snapshot()["members"]

        self.assertEqual(
            next(item for item in members if item["name"] == "Dummy041"),
            {
                "name": "Dummy041",
                "object_id": 1002,
                "health_percent": 75,
                "x": 44,
                "y": 55,
                "z": 66,
                "role": "melee-burst",
            },
        )

    def test_choose_party_rescue_threat_target_prefers_current_visible_threat(self):
        boss = FakeNpc(10, "Moran the Mighty", 73, 100.0)
        current_add = FakeNpc(20, "granite giant oracle", 60, 500.0)
        closer_add = FakeNpc(21, "granite giant stonelord", 60, 200.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True},
                {"object_id": 21, "requested_at": now - 1.0, "objective_add": True},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_rescue_assist_after=3.0,
            party_healer_local_rescue_health_percent=35,
        )

        selected = behavior.choose_party_rescue_threat_target(
            [boss, current_add, closer_add],
            FakeClient(npcs=[boss, current_add, closer_add]),
            args,
            snapshot,
            member_name="Dummy041",
            action_rotation="melee-burst",
            health_percent=100,
            now=now,
            current_target=20,
        )

        self.assertEqual(selected.object_id, 20)

    def test_choose_party_rescue_threat_target_handles_travel_add_before_objective(self):
        add = FakeNpc(20, "lunantishee", 2, 140.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 0,
            "active_tank_name": "GrowthHib1511",
            "rescue_tank_name": "GrowthHib1512",
            "rescue_member_name": "GrowthHib1512",
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": False, "member_name": "GrowthHib1512"},
            ],
            "members": [
                {"name": "GrowthHib1511", "role": "melee-basic", "health_percent": 100},
                {"name": "GrowthHib1512", "role": "melee-basic", "health_percent": 82},
            ],
        }
        args = SimpleNamespace(
            require_target_name="lough wolf cadger",
            party_encounter_mode="standard",
            party_assist_only=True,
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=1400.0,
            party_local_rescue_target=False,
            party_assist_rescue_target=False,
            party_rescue_assist_after=0.0,
            party_rescue_emergency_assist_after=0.0,
            party_caster_assist_rescue_target=False,
        )

        selected = behavior.choose_party_rescue_threat_target(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            member_name="GrowthHib1511",
            action_rotation="melee-basic",
            health_percent=100,
            now=now,
        )

        self.assertEqual(selected.object_id, 20)

    def test_choose_party_rescue_threat_target_rejects_far_travel_add_before_objective(self):
        far_add = FakeNpc(20, "orchard nipper", 5, 2400.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 0,
            "rescue_tank_name": "GrowthHib1512",
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": False, "member_name": "GrowthHib1512"},
            ],
            "members": [
                {"name": "GrowthHib1511", "role": "melee-basic", "health_percent": 100},
                {"name": "GrowthHib1512", "role": "melee-basic", "health_percent": 82},
            ],
        }
        args = SimpleNamespace(
            require_target_name="lough wolf cadger",
            party_encounter_mode="standard",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=1400.0,
            party_local_rescue_target=False,
            party_assist_rescue_target=False,
            party_rescue_assist_after=0.0,
            party_rescue_emergency_assist_after=0.0,
            party_caster_assist_rescue_target=False,
        )

        selected = behavior.choose_party_rescue_threat_target(
            [far_add],
            FakeClient(npcs=[far_add]),
            args,
            snapshot,
            member_name="GrowthHib1511",
            action_rotation="melee-basic",
            health_percent=100,
            now=now,
        )

        self.assertIsNone(selected)

    def test_choose_party_rescue_threat_target_keeps_focus_for_healthy_melee_peer(self):
        add = FakeNpc(20, "black wolf pup", 1, 140.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "GrowthAlb1821",
            "rescue_tank_name": "GrowthAlb1821",
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True, "member_name": "GrowthAlb1822"},
            ],
            "members": [
                {"name": "GrowthAlb1821", "role": "melee-basic", "health_percent": 100},
                {"name": "GrowthAlb1822", "role": "melee-basic", "health_percent": 88},
            ],
        }
        args = SimpleNamespace(
            require_target_name="boar piglet",
            party_encounter_mode="standard",
            party_assist_only=True,
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=1400.0,
            party_rescue_peer_health_percent=45,
            party_local_rescue_target=False,
            party_assist_rescue_target=False,
            party_rescue_assist_after=0.0,
            party_rescue_emergency_assist_after=0.0,
            party_caster_assist_rescue_target=False,
        )

        selected = behavior.choose_party_rescue_threat_target(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            member_name="GrowthAlb1821",
            action_rotation="melee-basic",
            health_percent=100,
            now=now,
        )

        self.assertIsNone(selected)

    def test_choose_party_rescue_threat_target_handles_low_health_melee_peer(self):
        add = FakeNpc(20, "black wolf pup", 1, 140.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "GrowthAlb1821",
            "rescue_tank_name": "GrowthAlb1823",
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True, "member_name": "GrowthAlb1822"},
            ],
            "members": [
                {"name": "GrowthAlb1821", "role": "melee-basic", "health_percent": 100},
                {"name": "GrowthAlb1822", "role": "melee-basic", "health_percent": 40},
                {"name": "GrowthAlb1823", "role": "melee-basic", "health_percent": 100},
            ],
        }
        args = SimpleNamespace(
            require_target_name="boar piglet",
            party_encounter_mode="standard",
            party_assist_only=True,
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=1400.0,
            party_rescue_peer_health_percent=45,
            party_local_rescue_target=False,
            party_assist_rescue_target=False,
            party_rescue_assist_after=0.0,
            party_rescue_emergency_assist_after=0.0,
            party_caster_assist_rescue_target=False,
        )

        selected = behavior.choose_party_rescue_threat_target(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            member_name="GrowthAlb1822",
            action_rotation="melee-basic",
            health_percent=40,
            now=now,
        )

        self.assertEqual(selected.object_id, 20)

    def test_standard_party_rescue_rejects_targets_above_growth_level_cap(self):
        args = SimpleNamespace(
            party_encounter_mode="standard",
            player_level=1,
            max_target_level=-1,
            max_target_level_delta=2,
        )

        self.assertTrue(behavior.should_accept_party_rescue_target(args, FakeNpc(20, "lough wolf cadger", 3, 300.0)))
        self.assertFalse(behavior.should_accept_party_rescue_target(args, FakeNpc(21, "orchard nipper", 5, 300.0)))

    def test_choose_party_rescue_threat_target_keeps_active_tank_on_boss(self):
        add = FakeNpc(20, "granite giant oracle", 60, 200.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_rescue_assist_after=3.0,
            party_healer_local_rescue_health_percent=35,
        )

        selected = behavior.choose_party_rescue_threat_target(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            member_name="Dummy040",
            action_rotation="melee-basic",
            health_percent=100,
            now=now,
        )

        self.assertIsNone(selected)

    def test_choose_party_rescue_threat_target_distributes_melee_handlers(self):
        adds = [
            FakeNpc(20, "granite giant oracle", 60, 200.0),
            FakeNpc(21, "granite giant stonelord", 60, 220.0),
            FakeNpc(22, "granite giant elder", 60, 240.0),
        ]
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "rescue_tank_name": "Dummy300",
            "members": [
                {"name": "Dummy040", "role": "melee-basic", "health_percent": 100, "object_id": 1},
                {"name": "Dummy300", "role": "melee-burst", "health_percent": 100, "object_id": 2},
                {"name": "Dummy041", "role": "melee-burst", "health_percent": 100, "object_id": 3},
                {"name": "Dummy042", "role": "melee-burst", "health_percent": 100, "object_id": 4},
                {"name": "Dummy403", "role": "caster-basic", "health_percent": 100, "object_id": 5},
            ],
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 5.0, "objective_add": True},
                {"object_id": 21, "requested_at": now - 5.0, "objective_add": True},
                {"object_id": 22, "requested_at": now - 5.0, "objective_add": True},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_rescue_assist_after=3.0,
            party_healer_local_rescue_health_percent=35,
        )

        selections = [
            behavior.choose_party_rescue_threat_target(
                adds,
                FakeClient(npcs=adds),
                args,
                snapshot,
                member_name=name,
                action_rotation="melee-burst",
                health_percent=100,
                now=now,
            ).object_id
            for name in ("Dummy300", "Dummy041", "Dummy042")
        ]

        self.assertEqual(selections, [20, 21, 22])

    def test_choose_party_rescue_threat_target_distributes_rescue_and_off_tanks_before_assist_delay(self):
        adds = [
            FakeNpc(20, "granite giant oracle", 60, 200.0),
            FakeNpc(21, "granite giant stonelord", 60, 220.0),
        ]
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "rescue_tank_name": "Dummy300",
            "members": [
                {"name": "Dummy040", "role": "melee-basic", "health_percent": 100, "object_id": 1},
                {"name": "Dummy300", "role": "melee-burst", "health_percent": 100, "object_id": 2},
                {"name": "Dummy041", "role": "melee-burst", "health_percent": 100, "object_id": 3},
                {"name": "Dummy042", "role": "melee-basic", "health_percent": 100, "object_id": 4},
                {"name": "Dummy402", "role": "healer-support", "health_percent": 100, "object_id": 5},
            ],
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True},
                {"object_id": 21, "requested_at": now - 1.0, "objective_add": True},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_rescue_assist_after=6.0,
            party_healer_local_rescue_health_percent=35,
        )

        rescue_tank = behavior.choose_party_rescue_threat_target(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            member_name="Dummy300",
            action_rotation="melee-burst",
            health_percent=100,
            now=now,
        )
        burst_dps = behavior.choose_party_rescue_threat_target(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            member_name="Dummy041",
            action_rotation="melee-burst",
            health_percent=100,
            now=now,
        )
        off_tank = behavior.choose_party_rescue_threat_target(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            member_name="Dummy042",
            action_rotation="melee-basic",
            health_percent=100,
            now=now,
        )

        self.assertIsNotNone(rescue_tank)
        self.assertEqual(rescue_tank.object_id, 20)
        self.assertIsNone(burst_dps)
        self.assertIsNotNone(off_tank)
        self.assertEqual(off_tank.object_id, 21)
        self.assertIsNone(
            behavior.choose_party_rescue_threat_target(
                adds,
                FakeClient(npcs=adds),
                args,
                snapshot,
                member_name="Dummy402",
                action_rotation="healer-support",
                health_percent=100,
                now=now,
            )
        )

    def test_objective_add_rescue_keeps_melee_burst_on_boss_until_assist_linger(self):
        adds = [
            FakeNpc(20, "granite giant oracle", 60, 200.0),
            FakeNpc(21, "granite giant stonelord", 60, 220.0),
        ]
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "rescue_tank_name": "Dummy300",
            "members": [
                {"name": "Dummy040", "role": "melee-basic", "health_percent": 100, "object_id": 1},
                {"name": "Dummy300", "role": "melee-burst", "health_percent": 100, "object_id": 2},
                {"name": "Dummy041", "role": "melee-burst", "health_percent": 100, "object_id": 3},
                {"name": "Dummy042", "role": "melee-basic", "health_percent": 100, "object_id": 4},
            ],
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True},
                {"object_id": 21, "requested_at": now - 1.0, "objective_add": True},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_rescue_assist_after=6.0,
            party_healer_local_rescue_health_percent=35,
        )

        self.assertIsNone(
            behavior.choose_party_rescue_threat_target(
                adds,
                FakeClient(npcs=adds),
                args,
                snapshot,
                member_name="Dummy041",
                action_rotation="melee-burst",
                health_percent=100,
                now=now,
            )
        )
        selected = behavior.choose_party_rescue_threat_target(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            member_name="Dummy042",
            action_rotation="melee-basic",
            health_percent=100,
            now=now,
        )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.object_id, 21)

    def test_choose_party_rescue_threat_target_does_not_keep_wrong_current_target_after_assignment(self):
        adds = [
            FakeNpc(20, "granite giant oracle", 60, 200.0),
            FakeNpc(21, "granite giant stonelord", 60, 220.0),
        ]
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "rescue_tank_name": "Dummy300",
            "members": [
                {"name": "Dummy040", "role": "melee-basic", "health_percent": 100, "object_id": 1},
                {"name": "Dummy300", "role": "melee-burst", "health_percent": 100, "object_id": 2},
                {"name": "Dummy041", "role": "melee-burst", "health_percent": 100, "object_id": 3},
            ],
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 5.0, "objective_add": True},
                {"object_id": 21, "requested_at": now - 5.0, "objective_add": True},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_rescue_assist_after=3.0,
            party_healer_local_rescue_health_percent=35,
        )

        selected = behavior.choose_party_rescue_threat_target(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            member_name="Dummy041",
            action_rotation="melee-burst",
            health_percent=100,
            now=now,
            current_target=20,
        )

        self.assertEqual(selected.object_id, 21)

    def test_choose_party_rescue_threat_target_keeps_current_message_proven_add(self):
        adds = [
            FakeNpc(20, "granite giant oracle", 60, 200.0),
            FakeNpc(21, "granite giant stonelord", 60, 220.0),
        ]
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "rescue_tank_name": "Dummy300",
            "members": [
                {"name": "Dummy040", "role": "melee-basic", "health_percent": 100, "object_id": 1},
                {"name": "Dummy300", "role": "melee-burst", "health_percent": 100, "object_id": 2},
                {"name": "Dummy041", "role": "melee-burst", "health_percent": 100, "object_id": 3},
            ],
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 5.0, "objective_add": False, "member_name": "Dummy041"},
                {"object_id": 21, "requested_at": now - 5.0, "objective_add": False, "member_name": "Dummy300"},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_rescue_assist_after=3.0,
            party_healer_local_rescue_health_percent=35,
        )

        selected = behavior.choose_party_rescue_threat_target(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            member_name="Dummy041",
            action_rotation="melee-burst",
            health_percent=100,
            now=now,
            current_target=20,
        )

        self.assertEqual(selected.object_id, 20)

    def test_choose_party_rescue_threat_target_assignment_is_stable_when_visibility_order_changes(self):
        adds = [
            FakeNpc(21, "granite giant stonelord", 60, 220.0),
            FakeNpc(20, "granite giant oracle", 60, 200.0),
        ]
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "rescue_tank_name": "Dummy300",
            "members": [
                {"name": "Dummy040", "role": "melee-basic", "health_percent": 100, "object_id": 1},
                {"name": "Dummy300", "role": "melee-burst", "health_percent": 100, "object_id": 2},
                {"name": "Dummy041", "role": "melee-burst", "health_percent": 100, "object_id": 3},
            ],
            "rescue_threats": [
                {"object_id": 21, "requested_at": now - 1.0, "objective_add": True},
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_rescue_assist_after=6.0,
            party_healer_local_rescue_health_percent=35,
        )

        first = behavior.choose_party_rescue_threat_target(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            member_name="Dummy300",
            action_rotation="melee-burst",
            health_percent=100,
            now=now,
        )
        second = behavior.choose_party_rescue_threat_target(
            list(reversed(adds)),
            FakeClient(npcs=list(reversed(adds))),
            args,
            snapshot,
            member_name="Dummy300",
            action_rotation="melee-burst",
            health_percent=100,
            now=now,
        )

        self.assertEqual(first.object_id, 20)
        self.assertEqual(second.object_id, 20)

    def test_choose_party_rescue_threat_target_focuses_support_pressure_add_after_emergency_delay(self):
        adds = [
            FakeNpc(20, "granite giant stonelord", 60, 220.0),
            FakeNpc(21, "granite giant oracle", 60, 200.0),
        ]
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "rescue_tank_name": "Dummy300",
            "members": [
                {"name": "Dummy040", "role": "melee-basic", "health_percent": 100, "object_id": 1},
                {"name": "Dummy041", "role": "melee-burst", "health_percent": 100, "object_id": 2},
                {"name": "Dummy042", "role": "melee-burst", "health_percent": 100, "object_id": 3},
                {"name": "Dummy050", "role": "healer-support", "health_percent": 55, "object_id": 4},
            ],
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 4.0, "objective_add": False, "member_name": "Dummy050"},
                {"object_id": 21, "requested_at": now - 4.0, "objective_add": False, "member_name": "Dummy041"},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=14.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_rescue_assist_after=6.0,
            party_rescue_emergency_assist_after=1.0,
            party_healer_local_rescue_health_percent=35,
        )

        selected = behavior.choose_party_rescue_threat_target(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            member_name="Dummy042",
            action_rotation="melee-burst",
            health_percent=100,
            now=now,
        )

        self.assertEqual(selected.object_id, 20)

    def test_support_pressure_rescue_assist_keeps_casters_out_without_opt_in(self):
        args = SimpleNamespace(
            party_rescue_emergency_assist_after=1.0,
            party_caster_assist_rescue_target=False,
        )

        self.assertTrue(
            behavior.should_assist_dangerous_support_rescue_threat(args, "melee-burst", 2.0, "healer-support")
        )
        self.assertFalse(
            behavior.should_assist_dangerous_support_rescue_threat(args, "caster-basic", 2.0, "healer-support")
        )
        self.assertFalse(
            behavior.should_assist_dangerous_support_rescue_threat(args, "melee-burst", 0.5, "healer-support")
        )

    def test_support_pressure_focus_keeps_current_support_add_to_reduce_churn(self):
        adds = [
            FakeNpc(20, "granite giant stonelord", 60, 220.0),
            FakeNpc(21, "granite giant oracle", 60, 200.0),
        ]
        now = 100.0
        snapshot = {
            "leader_target_id": 10,
            "active_tank_name": "Dummy040",
            "members": [
                {"name": "Dummy040", "role": "melee-basic", "health_percent": 100, "object_id": 1},
                {"name": "Dummy041", "role": "melee-burst", "health_percent": 100, "object_id": 2},
                {"name": "Dummy050", "role": "healer-support", "health_percent": 55, "object_id": 3},
                {"name": "Dummy051", "role": "healer-support", "health_percent": 70, "object_id": 4},
            ],
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 4.0, "objective_add": False, "member_name": "Dummy050"},
                {"object_id": 21, "requested_at": now - 6.0, "objective_add": False, "member_name": "Dummy051"},
            ],
        }
        args = SimpleNamespace(
            require_target_name="moran the mighty",
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=14.0,
            party_local_rescue_target=True,
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_rescue_assist_after=6.0,
            party_rescue_emergency_assist_after=1.0,
            party_healer_local_rescue_health_percent=35,
        )

        selected = behavior.choose_party_rescue_threat_target(
            adds,
            FakeClient(npcs=adds),
            args,
            snapshot,
            member_name="Dummy041",
            action_rotation="melee-burst",
            health_percent=100,
            now=now,
            current_target=20,
        )

        self.assertEqual(selected.object_id, 20)

    def test_precast_movement_hold_keeps_support_stationary_when_cast_is_due(self):
        args = SimpleNamespace(allow_unvalidated_spells=False)
        combat_plan = SimpleNamespace(heal_spells=[object()], buff_spells=[], attack_spells=[])

        self.assertTrue(
            behavior.should_hold_precast_movement(
                args,
                "healer-support",
                combat_plan=combat_plan,
                heal_due=True,
                buff_due=False,
                offensive_due=False,
                current_target_distance=900.0,
                tactical_backoff=False,
            )
        )

    def test_precast_movement_hold_does_not_block_survival_backoff(self):
        args = SimpleNamespace(allow_unvalidated_spells=False)
        combat_plan = SimpleNamespace(heal_spells=[object()], buff_spells=[], attack_spells=[])

        self.assertFalse(
            behavior.should_hold_precast_movement(
                args,
                "healer-support",
                combat_plan=combat_plan,
                heal_due=True,
                buff_due=False,
                offensive_due=False,
                current_target_distance=900.0,
                tactical_backoff=True,
            )
        )

    def test_cast_action_hold_suppresses_movement_until_hold_expires(self):
        self.assertTrue(behavior.should_continue_cast_action_hold(cast_action_hold_until=12.0, now=10.0))
        self.assertFalse(behavior.should_continue_cast_action_hold(cast_action_hold_until=12.0, now=12.0))
        self.assertFalse(behavior.should_continue_cast_action_hold(cast_action_hold_until=0.0, now=10.0))

    def test_ranged_boss_safety_uses_tactical_backoff_distance(self):
        args = SimpleNamespace(
            attack_range=350,
            melee_range_buffer=250,
            minimum_melee_stop_distance=85,
            ranged_stop_distance=1000,
            spell_range=1500,
            boss_ranged_safe_distance=1600,
            boss_hazard_message_backoff_distance=2600,
            party_focus_target_backoff_distance=1900,
            party_boss_melee_backoff_distance=0,
            party_survival_backoff_distance=1000,
            party_melee_survival_backoff_distance=0,
        )

        reason, distance = behavior.party_smooth_tactical_backoff_reason_and_distance(
            args,
            "caster-basic",
            party_melee_survival_backoff=False,
            boss_hazard_backoff=False,
            party_focus_target_backoff=False,
            party_focus_pressure_backoff=False,
            party_boss_melee_backoff=False,
            party_survival_backoff=False,
            ranged_safety_backoff_due=True,
        )

        self.assertEqual(reason, "boss_ranged")
        self.assertEqual(distance, 1600)

    def test_required_target_matches_configured_boss_name(self):
        args = SimpleNamespace(require_target_name="Lord Elidyn,King of the Barfog Hills")

        self.assertTrue(behavior.is_required_target(args, FakeNpc(10, "Lord Elidyn", 59, 100.0)))
        self.assertFalse(behavior.is_required_target(args, FakeNpc(20, "ellyll guard", 50, 100.0)))

    def test_required_target_does_not_match_named_boss_minions(self):
        args = SimpleNamespace(require_target_name="Legendary Afanc")

        self.assertTrue(behavior.is_required_target(args, FakeNpc(10, "Legendary Afanc", 70, 100.0)))
        self.assertFalse(behavior.is_required_target(args, FakeNpc(20, "Legendary Afanc's minion", 43, 100.0)))
        self.assertFalse(behavior.passes_required_target_filter(args, FakeNpc(21, "Legendary Afanc minion", 44, 100.0)))

    def test_hunter_can_fallback_to_lowest_visible_preferred_level(self):
        npcs = [
            FakeNpc(10, "gabriel hound", 47, 200.0),
            FakeNpc(20, "gabriel hound", 43, 400.0),
            FakeNpc(30, "moorlich", 40, 100.0),
        ]
        args = SimpleNamespace(
            max_target_level=40,
            player_level=50,
            max_target_level_delta=0,
            ideal_target_level=40,
            prefer_target_name="gabriel hound",
            avoid_target_name="moorlich",
            min_target_level=40,
            max_target_distance=1000.0,
            target_pool=2,
            target_selection="nearest",
            target_level_weight=120.0,
            target_distance_weight=120.0,
            target_randomness=0.0,
            prefer_target_bonus=300.0,
            npc_max_age=60.0,
            include_peace_npcs=False,
            target_auto_lowest_visible_level=True,
        )

        selected = behavior.choose_hunter_target(FakeClient(npcs=npcs), __import__("random").Random(1), args, {}, {}, 1.0)
        self.assertEqual(selected.object_id, 20)

    def test_party_state_clears_leader_target_when_no_target_is_shared(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=88, x=10, y=20, z=30, heading=40)
        target = SimpleNamespace(object_id=99, x=100, y=200, z=300)

        state.update_leader(client, target)
        self.assertEqual(state.snapshot()["leader_object_id"], 7)
        self.assertEqual(state.snapshot()["leader_health_percent"], 88)
        self.assertEqual(state.snapshot()["leader_target_id"], 99)
        self.assertGreater(state.snapshot()["leader_target_updated_at"], 0)
        self.assertEqual(state.snapshot()["leader_target_engaged_at"], 0)

        state.mark_leader_target_engaged(99)
        self.assertGreater(state.snapshot()["leader_target_engaged_at"], 0)

        state.update_leader(client)
        self.assertEqual(state.snapshot()["leader_target_id"], 99)

        state.clear_leader_target()
        self.assertEqual(state.snapshot()["leader_target_id"], 0)
        self.assertEqual(state.snapshot()["leader_target_updated_at"], 0)
        self.assertEqual(state.snapshot()["leader_target_engaged_at"], 0)

    def test_party_state_tracks_lowest_hurt_member(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "dps"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=92, x=1, y=2, z=3))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=65, x=4, y=5, z=6))
        state.update_member("dps", SimpleNamespace(player_object_id=12, health_percent=44, x=7, y=8, z=9))

        member = state.lowest_hurt_member(80)

        self.assertEqual(member["name"], "dps")
        self.assertEqual(member["object_id"], 12)
        self.assertEqual(member["health_percent"], 44)
        self.assertIsNone(state.lowest_hurt_member(40))

    def test_party_state_lowest_hurt_member_ignores_self_dead_and_unknown_members(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "dps", "wizard"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=30, x=1, y=2, z=3))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=20, x=4, y=5, z=6))
        state.update_member("dps", SimpleNamespace(player_object_id=12, health_percent=0, x=7, y=8, z=9))
        state.update_member("wizard", SimpleNamespace(player_object_id=0, health_percent=10, x=10, y=11, z=12))
        state.update_member("stranger", SimpleNamespace(player_object_id=99, health_percent=1, x=13, y=14, z=15))

        member = state.lowest_hurt_member(80, exclude_name="cleric")

        self.assertEqual(member["name"], "leader")
        self.assertEqual(member["object_id"], 10)
        self.assertEqual(member["health_percent"], 30)

    def test_party_state_promotes_alive_melee_member_as_active_tank(self):
        state = behavior.PartyState("leader", ["leader", "offtank", "cleric"])
        state.update_member_role("leader", "melee-basic")
        state.update_member_role("offtank", "melee-burst")
        state.update_member_role("cleric", "healer-support")
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=0, x=1, y=2, z=3))
        state.update_member("offtank", SimpleNamespace(player_object_id=11, health_percent=90, x=4, y=5, z=6))
        state.update_member("cleric", SimpleNamespace(player_object_id=12, health_percent=100, x=7, y=8, z=9))

        active_tank = state.active_tank()
        snapshot = state.snapshot()

        self.assertEqual(active_tank["name"], "offtank")
        self.assertEqual(active_tank["object_id"], 11)
        self.assertEqual((snapshot["active_tank_x"], snapshot["active_tank_y"], snapshot["active_tank_z"]), (4, 5, 6))

    def test_party_state_keeps_alive_leader_as_active_tank_when_boss_focuses_offtank(self):
        state = behavior.PartyState("leader", ["leader", "offtank", "cleric"])
        state.update_member_role("leader", "melee-basic")
        state.update_member_role("offtank", "melee-burst")
        state.update_member_role("cleric", "healer-support")
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=1, y=2, z=3))
        state.update_member("offtank", SimpleNamespace(player_object_id=11, health_percent=90, x=4, y=5, z=6))
        state.update_member("cleric", SimpleNamespace(player_object_id=12, health_percent=100, x=7, y=8, z=9))
        state.update_shared_target(
            behavior.RequiredTargetObservation(
                object_id=100,
                name="Fester",
                x=10,
                y=20,
                z=30,
                level=64,
                target="offtank",
            ),
            engaged=True,
        )

        snapshot = state.snapshot()

        self.assertEqual(snapshot["active_tank_name"], "leader")
        self.assertEqual(snapshot["active_tank_object_id"], 10)

    def test_party_state_hands_off_low_health_active_tank_to_healthy_offtank(self):
        state = behavior.PartyState(
            "leader",
            ["leader", "offtank", "cleric"],
            active_tank_handoff_health_percent=35,
        )
        state.update_member_role("leader", "melee-basic")
        state.update_member_role("offtank", "melee-burst")
        state.update_member_role("cleric", "healer-support")
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=16, x=1, y=2, z=3))
        state.update_member("offtank", SimpleNamespace(player_object_id=11, health_percent=90, x=4, y=5, z=6))
        state.update_member("cleric", SimpleNamespace(player_object_id=12, health_percent=100, x=7, y=8, z=9))

        snapshot = state.snapshot()

        self.assertEqual(snapshot["active_tank_name"], "offtank")
        self.assertEqual(snapshot["active_tank_object_id"], 11)
        self.assertEqual(snapshot["active_tank_health_percent"], 90)

    def test_party_state_does_not_promote_focused_non_tank_as_active_tank(self):
        state = behavior.PartyState("leader", ["leader", "wizard"])
        state.update_member_role("leader", "melee-basic")
        state.update_member_role("wizard", "caster-basic")
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=1, y=2, z=3))
        state.update_member("wizard", SimpleNamespace(player_object_id=11, health_percent=100, x=4, y=5, z=6))
        state.update_shared_target(
            behavior.RequiredTargetObservation(
                object_id=100,
                name="Fester",
                x=10,
                y=20,
                z=30,
                level=64,
                target="wizard",
            ),
            engaged=True,
        )

        self.assertEqual(state.snapshot()["active_tank_name"], "leader")

    def test_party_anchor_uses_active_tank_when_original_leader_is_dead(self):
        state = behavior.PartyState("leader", ["leader", "offtank"])
        state.update_member_role("leader", "melee-basic")
        state.update_member_role("offtank", "melee-burst")
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=0, x=1, y=2, z=3))
        state.update_member("offtank", SimpleNamespace(player_object_id=11, health_percent=90, x=400, y=500, z=600))

        anchor = behavior.party_anchor_from_snapshot(state.snapshot())

        self.assertEqual(anchor["name"], "offtank")
        self.assertEqual((anchor["x"], anchor["y"], anchor["z"]), (400, 500, 600))

    def test_only_active_tank_handles_party_rescue_target(self):
        state = behavior.PartyState("leader", ["leader", "offtank", "cleric"])
        state.update_member_role("leader", "melee-basic")
        state.update_member_role("offtank", "melee-burst")
        state.update_member_role("cleric", "healer-support")
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=0, x=1, y=2, z=3))
        state.update_member("offtank", SimpleNamespace(player_object_id=11, health_percent=90, x=4, y=5, z=6))
        state.update_member("cleric", SimpleNamespace(player_object_id=12, health_percent=100, x=7, y=8, z=9))

        snapshot = state.snapshot()

        self.assertFalse(behavior.party_member_is_active_tank(snapshot, "leader"))
        self.assertTrue(behavior.party_member_is_active_tank(snapshot, "offtank"))
        self.assertFalse(behavior.party_member_is_active_tank(snapshot, "cleric"))

    def test_party_state_prefers_offtank_as_rescue_tank_when_leader_is_alive(self):
        state = behavior.PartyState("leader", ["leader", "offtank", "cleric"])
        state.update_member_role("leader", "melee-basic")
        state.update_member_role("offtank", "melee-burst")
        state.update_member_role("cleric", "healer-support")
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=95, x=1, y=2, z=3))
        state.update_member("offtank", SimpleNamespace(player_object_id=11, health_percent=90, x=4, y=5, z=6))
        state.update_member("cleric", SimpleNamespace(player_object_id=12, health_percent=100, x=7, y=8, z=9))

        snapshot = state.snapshot()
        rescue_tank = state.rescue_tank()

        self.assertEqual(snapshot["active_tank_name"], "leader")
        self.assertEqual(rescue_tank["name"], "offtank")
        self.assertFalse(behavior.party_member_is_rescue_tank(snapshot, "leader"))
        self.assertTrue(behavior.party_member_is_rescue_tank(snapshot, "offtank"))

    def test_party_state_uses_leader_as_rescue_tank_without_offtank(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member_role("leader", "melee-basic")
        state.update_member_role("cleric", "healer-support")
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=95, x=1, y=2, z=3))
        state.update_member("cleric", SimpleNamespace(player_object_id=12, health_percent=100, x=7, y=8, z=9))

        snapshot = state.snapshot()

        self.assertTrue(behavior.party_member_is_rescue_tank(snapshot, "leader"))
        self.assertFalse(behavior.party_member_is_rescue_tank(snapshot, "cleric"))

    def test_party_state_tracks_encounter_deaths_and_resets_on_new_shared_target(self):
        state = behavior.PartyState("leader", ["leader", "merc", "cleric"])
        first_boss = SimpleNamespace(object_id=77, name="Fester", x=1, y=2, z=3)
        second_boss = SimpleNamespace(object_id=88, name="Barfog", x=4, y=5, z=6)

        state.update_shared_target(first_boss)
        state.update_member("merc", SimpleNamespace(player_object_id=11, health_percent=100, x=1, y=2, z=3))
        state.update_member("merc", SimpleNamespace(player_object_id=11, health_percent=0, x=1, y=2, z=3))
        snapshot = state.snapshot()

        self.assertEqual(snapshot["encounter_death_count"], 1)
        self.assertGreater(snapshot["last_encounter_death_at"], 0)

        state.update_shared_target(second_boss)
        snapshot = state.snapshot()

        self.assertEqual(snapshot["encounter_death_count"], 0)
        self.assertEqual(snapshot["last_encounter_death_at"], 0)

    def test_party_encounter_survival_pressure_uses_recent_deaths(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="fester",
            party_encounter_mode="boss",
            party_survival_death_count=1,
            party_survival_death_window=30.0,
            party_survival_active_tank_health_percent=0,
        )
        snapshot = {
            "leader_target_id": 77,
            "encounter_death_count": 1,
            "last_encounter_death_at": 95.0,
            "active_tank_health_percent": 100,
        }

        self.assertTrue(behavior.party_encounter_survival_pressure(args, snapshot, now=100.0))
        self.assertFalse(behavior.party_encounter_survival_pressure(args, snapshot, now=130.1))

    def test_low_health_required_target_burn_ignores_recent_death_survival_pressure(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="fester",
            party_encounter_mode="boss",
            party_survival_death_count=1,
            party_survival_death_window=30.0,
            party_survival_active_tank_health_percent=0,
            party_burn_required_target_health_percent=30.0,
        )
        snapshot = {
            "leader_target_id": 77,
            "leader_target_health_percent": 25.0,
            "encounter_death_count": 1,
            "last_encounter_death_at": 95.0,
            "active_tank_health_percent": 100,
        }

        self.assertFalse(behavior.party_encounter_survival_pressure(args, snapshot, now=100.0))

        snapshot["leader_target_health_percent"] = 35.0
        self.assertTrue(behavior.party_encounter_survival_pressure(args, snapshot, now=100.0))

    def test_low_health_required_target_burn_keeps_active_tank_emergency_pressure(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="fester",
            party_encounter_mode="boss",
            party_survival_death_count=1,
            party_survival_death_window=30.0,
            party_survival_active_tank_health_percent=35,
            party_burn_required_target_health_percent=30.0,
        )
        snapshot = {
            "leader_target_id": 77,
            "leader_target_health_percent": 25.0,
            "encounter_death_count": 0,
            "last_encounter_death_at": 0.0,
            "active_tank_health_percent": 20,
        }

        self.assertTrue(behavior.party_encounter_survival_pressure(args, snapshot, now=100.0))

    def test_party_encounter_survival_backoff_applies_to_non_active_melee_only(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="fester",
            party_encounter_mode="boss",
            party_survival_death_count=1,
            party_survival_death_window=30.0,
            party_survival_active_tank_health_percent=0,
        )
        snapshot = {
            "leader_target_id": 77,
            "active_tank_name": "leader",
            "encounter_death_count": 1,
            "last_encounter_death_at": 95.0,
            "active_tank_health_percent": 100,
        }

        self.assertTrue(
            behavior.should_back_off_for_party_encounter_survival(
                args, snapshot, "merc", "melee-burst", now=100.0
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_encounter_survival(
                args, snapshot, "leader", "melee-basic", now=100.0
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_encounter_survival(
                args, snapshot, "cleric", "healer-support", now=100.0
            )
        )

    def test_party_encounter_mode_preserves_shared_target_without_boss_name(self):
        args = SimpleNamespace(party_assist_only=True, require_target_name="", party_encounter_mode="boss")

        self.assertTrue(behavior.should_preserve_party_target_on_loss(args))

    def test_shared_objective_visible_target_reacquires_by_shared_id_without_name_filter(self):
        args = SimpleNamespace(require_target_name="", party_encounter_mode="boss")
        npcs = [FakeNpc(77, "King of the Barfog Hills", 80, 100.0), FakeNpc(88, "forest add", 55, 50.0)]

        selected = behavior.choose_shared_objective_visible_target(FakeClient(npcs=npcs), npcs, args, 77)

        self.assertEqual(selected.object_id, 77)

    def test_shared_objective_visible_target_respects_required_home_limit(self):
        args = SimpleNamespace(
            require_target_name="young sveawolf",
            party_encounter_mode="standard",
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=1200.0,
            target_home_max_distance=400.0,
        )
        client = FakeClient()
        client.x = 1000
        client.y = 1000
        far = FakeNpc(77, "young sveawolf", 1, 100.0)
        far.x = 2000
        far.y = 1000
        near = FakeNpc(88, "young sveawolf", 1, 200.0)
        near.x = 1200
        near.y = 1000

        selected = behavior.choose_shared_objective_visible_target(client, [far, near], args, 77)

        self.assertEqual(selected.object_id, 88)

    def test_shared_objective_visible_target_respects_max_target_distance(self):
        args = SimpleNamespace(
            require_target_name="young sveawolf",
            party_encounter_mode="standard",
            required_target_home=None,
            max_target_distance=400.0,
        )
        far = FakeNpc(77, "young sveawolf", 1, 500.0)
        near = FakeNpc(88, "young sveawolf", 1, 200.0)

        selected = behavior.choose_shared_objective_visible_target(FakeClient(npcs=[far, near]), [far, near], args, 77)

        self.assertEqual(selected.object_id, 88)

    def test_shared_objective_visible_target_waits_until_required_home_hunt_range(self):
        args = SimpleNamespace(
            require_target_name="young sveawolf",
            party_encounter_mode="standard",
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=1200.0,
            target_home_max_distance=400.0,
        )
        client = FakeClient()
        client.x = 0
        client.y = 0
        near = FakeNpc(88, "young sveawolf", 1, 200.0)
        near.x = 1200
        near.y = 1000

        selected = behavior.choose_shared_objective_visible_target(client, [near], args, 88)

        self.assertIsNone(selected)

    def test_required_visible_target_ignores_required_name_outside_home_limit(self):
        args = SimpleNamespace(
            require_target_name="young sveawolf",
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=1200.0,
            target_home_max_distance=400.0,
        )
        client = FakeClient()
        client.x = 1000
        client.y = 1000
        far = FakeNpc(77, "young sveawolf", 1, 50.0)
        far.x = 2000
        far.y = 1000

        selected = behavior.choose_required_visible_target(client, [far], args)

        self.assertIsNone(selected)

    def test_required_visible_target_ignores_required_name_outside_max_target_distance(self):
        args = SimpleNamespace(
            require_target_name="young sveawolf",
            required_target_home=None,
            max_target_distance=400.0,
        )
        far = FakeNpc(77, "young sveawolf", 1, 500.0)

        selected = behavior.choose_required_visible_target(FakeClient(npcs=[far]), [far], args)

        self.assertIsNone(selected)

    def test_required_visible_target_waits_until_required_home_hunt_range(self):
        args = SimpleNamespace(
            require_target_name="young sveawolf",
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=1200.0,
            target_home_max_distance=400.0,
        )
        client = FakeClient()
        client.x = 0
        client.y = 0
        near = FakeNpc(88, "young sveawolf", 1, 200.0)
        near.x = 1200
        near.y = 1000

        selected = behavior.choose_required_visible_target(client, [near], args)

        self.assertIsNone(selected)

    def test_active_combat_matches_shared_objective_without_required_name(self):
        args = SimpleNamespace(require_target_name="", party_encounter_mode="siege")
        active = {"target_id": 2001, "target_name": "keep door", "target_level": 99}

        self.assertTrue(behavior.active_combat_matches_required_target(args, active))

    def test_required_name_still_filters_active_combat_in_boss_mode(self):
        args = SimpleNamespace(require_target_name="lord elidyn", party_encounter_mode="boss")
        boss = {"target_id": 10, "target_name": "Lord Elidyn", "target_level": 59}
        add = {"target_id": 20, "target_name": "ellyll guard", "target_level": 51}

        self.assertTrue(behavior.active_combat_matches_required_target(args, boss))
        self.assertFalse(behavior.active_combat_matches_required_target(args, add))

    def test_required_name_active_combat_rejects_possessive_minion(self):
        args = SimpleNamespace(require_target_name="legendary afanc", party_encounter_mode="boss")
        boss = {"target_id": 10, "target_name": "Legendary Afanc", "target_level": 70}
        minion = {"target_id": 20, "target_name": "Legendary Afanc's minion", "target_level": 43}

        self.assertTrue(behavior.active_combat_matches_required_target(args, boss))
        self.assertFalse(behavior.active_combat_matches_required_target(args, minion))

    def test_boss_rescue_waits_until_required_objective_engaged_except_active_or_urgent(self):
        args = SimpleNamespace(
            party_rescue_before_objective_engaged=False,
            party_rescue_objective_engaged_grace=8.0,
            require_target_name="lord elidyn",
            party_encounter_mode="boss",
            party_assist_only=True,
        )
        unengaged = {"leader_target_engaged_at": 0.0}
        engaged = {"leader_target_engaged_at": 10.0}
        recently_engaged = {"leader_target_engaged_at": 9.0}
        active_boss = {"target_id": 10, "target_name": "Lord Elidyn", "target_level": 59}

        self.assertFalse(behavior.should_allow_party_rescue_before_objective_engaged(args, unengaged, None, now=20.0))
        self.assertTrue(behavior.should_allow_party_rescue_before_objective_engaged(args, engaged, None, now=20.0))
        self.assertFalse(behavior.should_allow_party_rescue_before_objective_engaged(args, recently_engaged, None, now=12.0))
        self.assertTrue(behavior.should_allow_party_rescue_before_objective_engaged(args, unengaged, active_boss, now=20.0))
        self.assertTrue(
            behavior.should_allow_party_rescue_before_objective_engaged(
                args,
                recently_engaged,
                None,
                now=12.0,
                urgent=True,
            )
        )

    def test_boss_rescue_allows_recent_message_proven_travel_add_before_objective(self):
        args = SimpleNamespace(
            party_rescue_before_objective_engaged=False,
            party_rescue_objective_engaged_grace=8.0,
            party_rescue_max_age=8.0,
            require_target_name="lough wolf cadger",
            party_encounter_mode="standard",
            party_assist_only=True,
        )
        now = 20.0
        snapshot = {
            "leader_target_engaged_at": 0.0,
            "rescue_target_id": 21225,
            "rescue_requested_at": now - 30.0,
            "rescue_threats": [
                {"object_id": 21225, "requested_at": now - 1.0, "objective_add": False},
            ],
        }
        stale_snapshot = {
            **snapshot,
            "rescue_threats": [
                {"object_id": 21225, "requested_at": now - 20.0, "objective_add": False},
            ],
        }

        self.assertTrue(behavior.should_allow_party_rescue_before_objective_engaged(args, snapshot, None, now=now))
        self.assertFalse(behavior.should_allow_party_rescue_before_objective_engaged(args, stale_snapshot, None, now=now))

    def test_stop_after_required_target_removed_requires_enabled_matching_objective(self):
        active = {"target_id": 2001, "target_name": "King of the Barfog Hills", "target_level": 65}
        disabled = SimpleNamespace(
            stop_after_required_target_removed=False,
            require_target_name="barfog",
            party_encounter_mode="standard",
        )
        enabled = SimpleNamespace(
            stop_after_required_target_removed=True,
            require_target_name="barfog",
            party_encounter_mode="standard",
        )
        unrelated = SimpleNamespace(
            stop_after_required_target_removed=True,
            require_target_name="elidyn",
            party_encounter_mode="standard",
        )

        self.assertFalse(behavior.should_stop_after_required_target_removed(disabled, active))
        self.assertTrue(behavior.should_stop_after_required_target_removed(enabled, active))
        self.assertTrue(behavior.should_stop_after_required_target_removed(enabled, active, removed_object_id=2001))
        self.assertFalse(behavior.should_stop_after_required_target_removed(enabled, active, removed_object_id=3001))
        self.assertFalse(behavior.should_stop_after_required_target_removed(unrelated, active))

    def test_required_target_removed_api_completion_requires_confirmed_death(self):
        active = {"target_id": 2001, "target_name": "King of the Barfog Hills", "target_level": 65}
        args = SimpleNamespace(required_target_api=True, require_target_name="barfog")
        alive = behavior.RequiredTargetObservation(
            object_id=2001,
            name="King of the Barfog Hills",
            x=0,
            y=0,
            z=0,
            level=65,
            health_percent=99.5,
            health=298500,
            max_health=300000,
            is_alive=True,
        )
        dead_flag = behavior.RequiredTargetObservation(
            object_id=2001,
            name="King of the Barfog Hills",
            x=0,
            y=0,
            z=0,
            level=65,
            health=1,
            max_health=300000,
            is_alive=False,
        )
        dead_health = behavior.RequiredTargetObservation(
            object_id=2001,
            name="King of the Barfog Hills",
            x=0,
            y=0,
            z=0,
            level=65,
            health=0,
            max_health=300000,
            is_alive=True,
        )
        wrong_object = behavior.RequiredTargetObservation(
            object_id=3001,
            name="Unrelated Boss",
            x=0,
            y=0,
            z=0,
            level=65,
            health=0,
            max_health=300000,
            is_alive=False,
        )

        self.assertFalse(behavior.required_target_removed_api_confirms_completion(args, active, None, 2001))
        self.assertFalse(behavior.required_target_removed_api_confirms_completion(args, active, alive, 2001))
        self.assertFalse(behavior.required_target_removed_api_confirms_completion(args, active, wrong_object, 2001))
        self.assertTrue(behavior.required_target_removed_api_confirms_completion(args, active, dead_flag, 2001))
        self.assertTrue(behavior.required_target_removed_api_confirms_completion(args, active, dead_health, 2001))

    def test_required_target_removed_without_api_keeps_legacy_completion(self):
        active = {"target_id": 2001, "target_name": "King of the Barfog Hills", "target_level": 65}
        args = SimpleNamespace(required_target_api=False, require_target_name="barfog")

        self.assertTrue(behavior.required_target_removed_api_confirms_completion(args, active, None, 2001))

    def test_required_target_completion_prevents_removed_target_preserve(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="barfog",
            party_encounter_mode="standard",
            party_target_loss_grace=4.0,
            party_target_removed_preserve_limit=3,
        )
        active = {"target_id": 2001, "target_name": "King of the Barfog Hills", "target_level": 65}

        self.assertFalse(
            behavior.should_preserve_removed_party_target(
                args,
                party_state=None,
                current_target=2001,
                active_combat=active,
                stop_after_removed=True,
                now=10.0,
                last_visible_at=9.0,
                preserve_count=0,
            )
        )
        self.assertTrue(
            behavior.should_preserve_removed_party_target(
                args,
                party_state=None,
                current_target=2001,
                active_combat=active,
                stop_after_removed=False,
                now=10.0,
                last_visible_at=9.0,
                preserve_count=0,
            )
        )

    def test_party_state_shares_required_objective_completion(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        boss = FakeNpc(2001, "King of the Barfog Hills", 65, 100.0)
        state.update_shared_target(boss, engaged=True)

        state.mark_objective_complete(2001, "King of the Barfog Hills")
        snapshot = state.snapshot()

        self.assertEqual(snapshot["objective_complete_target_id"], 2001)
        self.assertEqual(snapshot["objective_complete_name"], "King of the Barfog Hills")
        self.assertGreater(snapshot["objective_completed_at"], 0.0)
        self.assertEqual(snapshot["leader_target_id"], 0)

    def test_rescue_target_does_not_replace_shared_party_objective(self):
        args = SimpleNamespace(party_assist_only=True, require_target_name="", party_encounter_mode="boss")

        self.assertTrue(behavior.should_share_selected_target(args, selected_npc_is_rescue=False))
        self.assertFalse(behavior.should_share_selected_target(args, selected_npc_is_rescue=True))

    def test_non_healer_damage_roles_temporarily_assist_rescue_target(self):
        args = SimpleNamespace(party_assist_rescue_target=True, party_caster_assist_rescue_target=False)

        self.assertTrue(behavior.should_party_member_assist_rescue_target(args, "melee-burst"))
        self.assertFalse(behavior.should_party_member_assist_rescue_target(args, "caster-basic"))
        self.assertFalse(behavior.should_party_member_assist_rescue_target(args, "healer-support"))

    def test_caster_rescue_assist_requires_explicit_opt_in(self):
        args = SimpleNamespace(party_assist_rescue_target=True, party_caster_assist_rescue_target=True)

        self.assertTrue(behavior.should_party_member_assist_rescue_target(args, "caster-basic"))

    def test_rescue_assist_can_be_disabled(self):
        args = SimpleNamespace(party_assist_rescue_target=False)

        self.assertFalse(behavior.should_party_member_assist_rescue_target(args, "melee-burst"))

    def test_rescue_assist_defaults_to_active_tank_only(self):
        args = SimpleNamespace()

        self.assertFalse(behavior.should_party_member_assist_rescue_target(args, "melee-burst"))
        self.assertFalse(behavior.should_party_member_use_local_rescue_target(args, "caster-basic", 100))

    def test_local_rescue_can_hold_personal_add_without_shared_rescue(self):
        args = SimpleNamespace(party_local_rescue_target=True)

        self.assertTrue(
            behavior.should_hold_party_assist_for_local_rescue(
                args,
                now=10.0,
                local_rescue_until=12.0,
                current_target=200,
                leader_target_id=100,
            )
        )
        self.assertFalse(
            behavior.should_hold_party_assist_for_local_rescue(
                args,
                now=13.0,
                local_rescue_until=12.0,
                current_target=200,
                leader_target_id=100,
            )
        )
        self.assertFalse(
            behavior.should_hold_party_assist_for_local_rescue(
                args,
                now=10.0,
                local_rescue_until=12.0,
                current_target=100,
                leader_target_id=100,
            )
        )

    def test_current_target_is_party_rescue_target(self):
        snapshot = {"rescue_target_id": 200}

        self.assertTrue(behavior.current_target_is_party_rescue_target(snapshot, 200))
        self.assertFalse(behavior.current_target_is_party_rescue_target(snapshot, 100))
        self.assertFalse(behavior.current_target_is_party_rescue_target(snapshot, 0))

    def test_party_assist_holds_shared_rescue_target_for_rescue_tank(self):
        snapshot = {
            "leader_target_id": 100,
            "active_tank_name": "leader",
            "rescue_target_id": 200,
            "rescue_requested_at": 10.0,
            "rescue_tank_name": "offtank",
        }
        args = SimpleNamespace(
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_assist_rescue_target=False,
            party_rescue_assist_after=0.0,
            party_local_rescue_target=False,
        )

        self.assertTrue(
            behavior.should_hold_party_assist_for_rescue_target(
                args,
                snapshot,
                now=12.0,
                current_target=200,
                party_member_name="offtank",
                action_rotation="melee-burst",
                health_percent=100,
            )
        )
        self.assertFalse(
            behavior.should_hold_party_assist_for_rescue_target(
                args,
                snapshot,
                now=12.0,
                current_target=200,
                party_member_name="dps",
                action_rotation="melee-burst",
                health_percent=100,
            )
        )

    def test_boss_active_tank_does_not_leave_objective_for_rescue_target(self):
        snapshot = {
            "leader_target_id": 100,
            "active_tank_name": "leader",
            "rescue_target_id": 200,
            "rescue_requested_at": 10.0,
            "rescue_tank_name": "leader",
        }
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="mouth",
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_assist_rescue_target=False,
            party_rescue_assist_after=0.0,
            party_local_rescue_target=False,
        )

        self.assertFalse(behavior.should_party_member_tank_rescue_target(args, snapshot, "leader"))
        self.assertFalse(
            behavior.should_hold_party_assist_for_rescue_target(
                args,
                snapshot,
                now=12.0,
                current_target=200,
                party_member_name="leader",
                action_rotation="melee-basic",
                health_percent=100,
            )
        )

    def test_rescue_assist_escalates_to_damage_roles_after_add_lingers(self):
        args = SimpleNamespace(
            party_assist_rescue_target=False,
            party_caster_assist_rescue_target=False,
            party_rescue_assist_after=6.0,
        )

        self.assertFalse(behavior.should_party_member_assist_rescue_target(args, "melee-burst", rescue_age=5.0, objective_add=True))
        self.assertTrue(behavior.should_party_member_assist_rescue_target(args, "melee-burst", rescue_age=6.1, objective_add=True))
        self.assertFalse(behavior.should_party_member_assist_rescue_target(args, "caster-basic", rescue_age=8.0, objective_add=True))
        self.assertFalse(behavior.should_party_member_assist_rescue_target(args, "healer-support", rescue_age=8.0, objective_add=True))

    def test_rescue_tank_prefers_taunt_skill_on_adds(self):
        snapshot = {"active_tank_name": "leader", "rescue_tank_name": "offtank"}
        args = SimpleNamespace(party_rescue_aggro=True)

        self.assertTrue(
            behavior.should_prefer_taunt_skill_for_target(
                args,
                snapshot,
                member_name="offtank",
                action_rotation="melee-burst",
                selected_npc_is_rescue=True,
                selected_npc_is_required=False,
                reaggro_taunt_due=False,
            )
        )
        self.assertFalse(
            behavior.should_prefer_taunt_skill_for_target(
                args,
                snapshot,
                member_name="wizard",
                action_rotation="caster-basic",
                selected_npc_is_rescue=True,
                selected_npc_is_required=False,
                reaggro_taunt_due=False,
            )
        )

    def test_rescue_assist_does_not_escalate_ambient_threats_to_damage_roles(self):
        args = SimpleNamespace(party_assist_rescue_target=False, party_rescue_assist_after=6.0)

        self.assertFalse(behavior.should_party_member_assist_rescue_target(args, "melee-burst", rescue_age=8.0, objective_add=False))
        self.assertFalse(behavior.should_party_member_assist_rescue_target(args, "caster-basic", rescue_age=8.0, objective_add=False))

    def test_active_tank_stays_on_shared_objective_even_after_rescue_lingers(self):
        snapshot = {
            "leader_target_id": 100,
            "active_tank_name": "leader",
            "rescue_target_id": 200,
            "rescue_requested_at": 10.0,
            "rescue_tank_name": "offtank",
            "rescue_target_objective_add": True,
        }
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="mouth",
            party_encounter_mode="boss",
            party_rescue_aggro=True,
            party_rescue_max_age=12.0,
            party_assist_rescue_target=False,
            party_rescue_assist_after=6.0,
            party_local_rescue_target=False,
        )

        self.assertFalse(
            behavior.should_hold_party_assist_for_rescue_target(
                args,
                snapshot,
                now=18.0,
                current_target=200,
                party_member_name="leader",
                action_rotation="melee-basic",
                health_percent=100,
            )
        )

    def test_non_active_melee_backs_off_from_shared_boss_objective(self):
        snapshot = {"leader_target_id": 100, "active_tank_name": "leader"}
        args = SimpleNamespace(
            party_boss_non_tank_melee_backoff=True,
            party_assist_only=True,
            require_target_name="mouth",
            party_encounter_mode="boss",
        )

        self.assertTrue(
            behavior.should_back_off_for_party_boss_melee_limit(
                args,
                snapshot,
                "dps",
                "melee-burst",
                100,
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_boss_melee_limit(
                args,
                snapshot,
                "leader",
                "melee-basic",
                100,
            )
        )

    def test_non_active_melee_does_not_back_off_from_rescue_add(self):
        snapshot = {"leader_target_id": 100, "active_tank_name": "leader"}
        args = SimpleNamespace(
            party_boss_non_tank_melee_backoff=True,
            party_assist_only=True,
            require_target_name="mouth",
            party_encounter_mode="boss",
        )

        self.assertFalse(
            behavior.should_back_off_for_party_boss_melee_limit(
                args,
                snapshot,
                "dps",
                "melee-burst",
                200,
            )
        )

    def test_party_state_tracks_required_target_focus_name_from_api_observation(self):
        state = behavior.PartyState("leader", ["leader", "Dummy409"])
        observed = behavior.RequiredTargetObservation(
            object_id=100,
            name="Fester",
            x=10,
            y=20,
            z=30,
            level=64,
            target="Dummy409",
        )

        state.update_shared_target(observed, engaged=True)

        snapshot = state.snapshot()
        self.assertEqual(snapshot["leader_target_focus_name"], "Dummy409")
        self.assertGreater(snapshot["leader_target_focus_updated_at"], 0.0)

    def test_party_state_tracks_required_target_health_from_api_observation(self):
        state = behavior.PartyState("leader", ["leader", "Dummy409"])
        observed = behavior.RequiredTargetObservation(
            object_id=100,
            name="Fester",
            x=10,
            y=20,
            z=30,
            level=64,
            health_percent=3.5,
            health=171,
            max_health=4882,
        )

        state.update_shared_target(observed, engaged=True)

        snapshot = state.snapshot()
        self.assertEqual(snapshot["leader_target_health_percent"], 3.5)
        self.assertEqual(snapshot["leader_target_health"], 171)
        self.assertEqual(snapshot["leader_target_max_health"], 4882)

    def test_party_state_refreshes_same_focus_timestamp_from_api_observation(self):
        state = behavior.PartyState("leader", ["leader", "Dummy409"])
        observed = behavior.RequiredTargetObservation(
            object_id=100,
            name="Fester",
            x=10,
            y=20,
            z=30,
            level=64,
            target="Dummy409",
        )

        with patch.object(behavior.time, "monotonic", side_effect=[10.0, 11.0, 12.0, 13.0, 20.0, 21.0]):
            state.update_shared_target(observed, engaged=True)
            first = state.snapshot()["leader_target_focus_updated_at"]
            state.update_shared_target(observed, engaged=True)
            second = state.snapshot()["leader_target_focus_updated_at"]

        self.assertEqual(first, 12.0)
        self.assertEqual(second, 20.0)

    def test_non_active_member_focused_by_shared_objective_backs_off(self):
        snapshot = {
            "leader_target_id": 100,
            "leader_target_focus_name": "Dummy409",
            "leader_target_focus_updated_at": 100.0,
            "active_tank_name": "leader",
        }
        args = SimpleNamespace(
            party_focus_target_backoff=True,
            party_focus_target_max_age=5.0,
            party_assist_only=True,
            require_target_name="fester",
            party_encounter_mode="boss",
        )

        self.assertTrue(
            behavior.should_back_off_for_party_focus_target(
                args,
                snapshot,
                "Dummy409",
                now=102.0,
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_focus_target(
                args,
                snapshot,
                "leader",
                now=102.0,
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_focus_target(
                args,
                snapshot,
                "Dummy409",
                now=106.0,
            )
        )

    def test_non_active_melee_backs_off_when_shared_objective_focuses_any_non_tank(self):
        snapshot = {
            "leader_target_id": 100,
            "leader_target_focus_name": "cleric",
            "leader_target_focus_updated_at": 100.0,
            "active_tank_name": "leader",
        }
        args = SimpleNamespace(
            party_focus_pressure_melee_backoff=True,
            party_focus_target_max_age=5.0,
            party_assist_only=True,
            require_target_name="fester",
            party_encounter_mode="boss",
        )

        self.assertTrue(
            behavior.should_back_off_for_party_focus_pressure(
                args,
                snapshot,
                "merc",
                "melee-basic",
                now=102.0,
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_focus_pressure(
                args,
                snapshot,
                "leader",
                "melee-basic",
                now=102.0,
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_focus_pressure(
                args,
                snapshot,
                "wizard",
                "caster-basic",
                now=102.0,
            )
        )

    def test_focus_pressure_offtank_reaggro_keeps_melee_basic_on_boss(self):
        snapshot = {
            "leader_target_id": 100,
            "leader_target_focus_name": "cleric",
            "leader_target_focus_updated_at": 100.0,
            "active_tank_name": "leader",
            "rescue_tank_name": "merc",
        }
        args = SimpleNamespace(
            party_focus_pressure_melee_backoff=True,
            party_focus_pressure_offtank_reaggro=True,
            party_focus_target_max_age=5.0,
            party_assist_only=True,
            require_target_name="fester",
            party_encounter_mode="boss",
        )

        self.assertFalse(
            behavior.should_back_off_for_party_focus_pressure(
                args,
                snapshot,
                "merc",
                "melee-basic",
                now=102.0,
            )
        )
        self.assertTrue(
            behavior.should_back_off_for_party_focus_pressure(
                args,
                snapshot,
                "blademaster",
                "melee-burst",
                now=102.0,
            )
        )

    def test_focus_pressure_offtank_reaggro_taunt_is_due_for_melee_basic(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="fester",
            party_active_tank_reaggro_taunt_interval=1.2,
            party_focus_pressure_offtank_reaggro=True,
            party_focus_target_max_age=5.0,
        )
        snapshot = {
            "active_tank_name": "leader",
            "leader_target_focus_name": "cleric",
            "leader_target_focus_updated_at": 100.0,
        }

        self.assertTrue(
            behavior.should_active_tank_reaggro_taunt(
                args,
                snapshot,
                "merc",
                "melee-basic",
                now=102.0,
                next_taunt=101.0,
            )
        )
        self.assertFalse(
            behavior.should_active_tank_reaggro_taunt(
                args,
                snapshot,
                "blademaster",
                "melee-burst",
                now=102.0,
                next_taunt=101.0,
            )
        )
        self.assertTrue(
            behavior.should_active_tank_reaggro_taunt(
                args,
                snapshot,
                "armsman",
                "melee-basic",
                now=102.0,
                next_taunt=101.0,
            )
        )

    def test_low_health_required_target_burn_holds_non_active_melee_pressure(self):
        args = SimpleNamespace(
            party_focus_pressure_melee_backoff=True,
            party_focus_target_max_age=5.0,
            party_assist_only=True,
            require_target_name="fester",
            party_encounter_mode="boss",
            party_burn_required_target_health_percent=5.0,
        )
        snapshot = {
            "leader_target_id": 100,
            "leader_target_focus_name": "cleric",
            "leader_target_focus_updated_at": 100.0,
            "leader_target_health_percent": 3.5,
            "active_tank_name": "leader",
        }

        self.assertFalse(
            behavior.should_back_off_for_party_focus_pressure(
                args,
                snapshot,
                "merc",
                "melee-basic",
                now=102.0,
            )
        )

        snapshot["leader_target_health_percent"] = 8.0
        self.assertTrue(
            behavior.should_back_off_for_party_focus_pressure(
                args,
                snapshot,
                "merc",
                "melee-basic",
                now=102.0,
            )
        )

    def test_drive_login_with_retries_reconnects_after_missing_session_id(self):
        class FlakyLoginClient:
            def __init__(self):
                self.attempts = 0
                self.closed = 0
                self.sequence = 99
                self.session_id = 123
                self.recv_buffer = bytearray(b"stale")

            def drive_login(self, username, password, realm, char_index):
                self.attempts += 1
                if self.attempts == 1:
                    raise RuntimeError("server did not send a session id")
                self.sequence = 7

            def close(self):
                self.closed += 1

        client = FlakyLoginClient()
        args = SimpleNamespace(login_retries=2, login_retry_delay=0.0)
        account = behavior.DummyAccount("dummy001", "pw", 1, 0)

        behavior.drive_login_with_retries(client, account, args)

        self.assertEqual(client.attempts, 2)
        self.assertEqual(client.closed, 1)
        self.assertEqual(client.sequence, 7)
        self.assertEqual(client.session_id, 0)
        self.assertEqual(client.recv_buffer, bytearray())

    def test_drive_login_with_retries_preserves_non_session_errors(self):
        class BadPasswordClient:
            def drive_login(self, username, password, realm, char_index):
                raise RuntimeError("login failed")

            def close(self):
                raise AssertionError("non-session errors should not reconnect")

        args = SimpleNamespace(login_retries=3, login_retry_delay=0.0)
        account = behavior.DummyAccount("dummy001", "pw", 1, 0)

        with self.assertRaisesRegex(RuntimeError, "login failed"):
            behavior.drive_login_with_retries(BadPasswordClient(), account, args)

    def test_ranged_party_assist_uses_extra_opening_delay(self):
        args = SimpleNamespace(
            party_assist_attack_delay=0.2,
            party_ranged_assist_extra_delay=4.0,
        )

        self.assertEqual(behavior.party_role_assist_attack_delay(args, "melee-basic"), 0.2)
        self.assertEqual(behavior.party_role_assist_attack_delay(args, "melee-burst"), 0.2)
        self.assertEqual(behavior.party_role_assist_attack_delay(args, "caster-basic"), 4.2)
        self.assertEqual(behavior.party_role_assist_attack_delay(args, "healer-support"), 4.2)

    def test_party_state_prefers_focused_hurt_member_for_healing(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "wizard"])
        state.update_shared_target(
            behavior.RequiredTargetObservation(
                object_id=100,
                name="Fester",
                x=10,
                y=20,
                z=30,
                level=64,
                target="wizard",
            ),
            engaged=True,
        )
        state.update_member("cleric", SimpleNamespace(player_object_id=2, health_percent=20, x=0, y=0, z=0))
        state.update_member("wizard", SimpleNamespace(player_object_id=3, health_percent=70, x=0, y=0, z=0))

        focused = state.focused_hurt_member(90)

        self.assertIsNotNone(focused)
        self.assertEqual(focused["name"], "wizard")

    def test_party_heal_target_prioritizes_critical_active_tank_over_focused_member(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "wizard"])
        state.update_shared_target(
            behavior.RequiredTargetObservation(
                object_id=100,
                name="Moran the Mighty",
                x=10,
                y=20,
                z=30,
                level=73,
                target="wizard",
            ),
            engaged=True,
        )
        state.update_member("leader", SimpleNamespace(player_object_id=1, health_percent=2, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=2, health_percent=100, x=0, y=0, z=0))
        state.update_member("wizard", SimpleNamespace(player_object_id=3, health_percent=60, x=0, y=0, z=0))
        args = SimpleNamespace(party_heal_leader_health_percent=80)

        target = behavior.choose_party_heal_target(state, args, exclude_name="cleric")

        self.assertIsNotNone(target)
        self.assertEqual(target["name"], "leader")

    def test_party_heal_target_prioritizes_wounded_active_tank_over_lower_focused_member(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "wizard"])
        state.update_shared_target(
            behavior.RequiredTargetObservation(
                object_id=100,
                name="Moran the Mighty",
                x=10,
                y=20,
                z=30,
                level=73,
                target="wizard",
            ),
            engaged=True,
        )
        state.update_member("leader", SimpleNamespace(player_object_id=1, health_percent=75, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=2, health_percent=100, x=0, y=0, z=0))
        state.update_member("wizard", SimpleNamespace(player_object_id=3, health_percent=60, x=0, y=0, z=0))
        args = SimpleNamespace(party_heal_leader_health_percent=80)

        target = behavior.choose_party_heal_target(state, args, exclude_name="cleric")

        self.assertIsNotNone(target)
        self.assertEqual(target["name"], "leader")

    def test_party_heal_target_uses_focused_member_when_active_tank_is_healthy(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "wizard"])
        state.update_shared_target(
            behavior.RequiredTargetObservation(
                object_id=100,
                name="Moran the Mighty",
                x=10,
                y=20,
                z=30,
                level=73,
                target="wizard",
            ),
            engaged=True,
        )
        state.update_member("leader", SimpleNamespace(player_object_id=1, health_percent=95, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=2, health_percent=100, x=0, y=0, z=0))
        state.update_member("wizard", SimpleNamespace(player_object_id=3, health_percent=60, x=0, y=0, z=0))
        args = SimpleNamespace(party_heal_leader_health_percent=80)

        target = behavior.choose_party_heal_target(state, args, exclude_name="cleric")

        self.assertIsNotNone(target)
        self.assertEqual(target["name"], "wizard")

    def test_party_heal_target_allows_focused_healer_to_self_preserve(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "wizard"])
        state.update_shared_target(
            behavior.RequiredTargetObservation(
                object_id=100,
                name="Moran the Mighty",
                x=10,
                y=20,
                z=30,
                level=73,
                target="cleric",
            ),
            engaged=True,
        )
        state.update_member("leader", SimpleNamespace(player_object_id=1, health_percent=95, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=2, health_percent=70, x=0, y=0, z=0))
        state.update_member("wizard", SimpleNamespace(player_object_id=3, health_percent=60, x=0, y=0, z=0))
        args = SimpleNamespace(party_heal_leader_health_percent=80, healer_self_health_percent=80)

        target = behavior.choose_party_heal_target(state, args, exclude_name="cleric")

        self.assertIsNotNone(target)
        self.assertEqual(target["name"], "cleric")

    def test_party_assist_holds_shared_rescue_target_for_damage_roles_after_linger(self):
        snapshot = {
            "leader_target_id": 100,
            "active_tank_name": "leader",
            "rescue_target_id": 200,
            "rescue_requested_at": 10.0,
            "rescue_tank_name": "offtank",
            "rescue_target_objective_add": True,
        }
        args = SimpleNamespace(
            party_rescue_aggro=True,
            party_rescue_max_age=12.0,
            party_assist_rescue_target=False,
            party_rescue_assist_after=6.0,
            party_local_rescue_target=False,
        )

        self.assertFalse(
            behavior.should_hold_party_assist_for_rescue_target(
                args,
                snapshot,
                now=15.0,
                current_target=200,
                party_member_name="dps",
                action_rotation="melee-burst",
                health_percent=100,
            )
        )
        self.assertTrue(
            behavior.should_hold_party_assist_for_rescue_target(
                args,
                snapshot,
                now=16.1,
                current_target=200,
                party_member_name="dps",
                action_rotation="melee-burst",
                health_percent=100,
            )
        )
        self.assertFalse(
            behavior.should_hold_party_assist_for_rescue_target(
                args,
                snapshot,
                now=16.1,
                current_target=200,
                party_member_name="healer",
                action_rotation="healer-support",
                health_percent=100,
            )
        )

    def test_party_assist_keeps_damage_roles_on_boss_for_ambient_rescue(self):
        snapshot = {
            "leader_target_id": 100,
            "active_tank_name": "leader",
            "rescue_target_id": 200,
            "rescue_requested_at": 10.0,
            "rescue_tank_name": "offtank",
            "rescue_target_objective_add": False,
        }
        args = SimpleNamespace(
            party_rescue_aggro=True,
            party_rescue_max_age=12.0,
            party_assist_rescue_target=False,
            party_rescue_assist_after=6.0,
            party_local_rescue_target=False,
        )

        self.assertFalse(
            behavior.should_hold_party_assist_for_rescue_target(
                args,
                snapshot,
                now=18.0,
                current_target=200,
                party_member_name="dps",
                action_rotation="melee-burst",
                health_percent=100,
            )
        )

    def test_tank_skill_choice_prefers_taunt_outside_high_level_pool(self):
        rng = behavior.random.Random(1)
        args = SimpleNamespace(combat_plan_skill_pool=2)
        skills = [
            behavior.UsableSkillRef(0, 1, "High Damage Style", 50),
            behavior.UsableSkillRef(1, 1, "Another High Style", 45),
            behavior.UsableSkillRef(2, 1, "Enrage", 8),
        ]

        selected, taunt_selected = behavior.choose_combat_skill(rng, args, skills, prefer_taunt_skill=True)

        self.assertTrue(taunt_selected)
        self.assertEqual(selected.name, "Enrage")

    def test_non_tank_skill_choice_uses_normal_high_level_pool(self):
        rng = behavior.random.Random(1)
        args = SimpleNamespace(combat_plan_skill_pool=2)
        skills = [
            behavior.UsableSkillRef(0, 1, "High Damage Style", 50),
            behavior.UsableSkillRef(1, 1, "Another High Style", 45),
            behavior.UsableSkillRef(2, 1, "Enrage", 8),
        ]

        selected, taunt_selected = behavior.choose_combat_skill(rng, args, skills, prefer_taunt_skill=False)

        self.assertFalse(taunt_selected)
        self.assertIn(selected.name, {"High Damage Style", "Another High Style"})

    def test_combat_stop_distance_keeps_casters_and_healers_outside_melee(self):
        args = SimpleNamespace(
            attack_range=145,
            melee_range_buffer=25,
            minimum_melee_stop_distance=65,
            ranged_stop_distance=900,
            spell_range=1500,
        )

        self.assertEqual(behavior.combat_stop_distance(args, "melee-basic"), 120)
        self.assertEqual(behavior.combat_stop_distance(args, "melee-burst"), 120)
        self.assertEqual(behavior.combat_stop_distance(args, "caster-basic"), 900)
        self.assertEqual(behavior.combat_stop_distance(args, "healer-support"), 900)

    def test_active_tank_uses_tighter_last_known_stop_distance(self):
        args = SimpleNamespace(
            attack_range=350,
            melee_range_buffer=250,
            minimum_melee_stop_distance=85,
            ranged_stop_distance=1000,
            spell_range=1500,
            party_assist_only=True,
            require_target_name="moran the mighty",
            party_active_tank_last_known_stop_distance=25,
        )
        snapshot = {"active_tank_name": "leader"}

        self.assertEqual(
            behavior.party_last_known_stop_distance(args, "melee-basic", snapshot, "leader"),
            25,
        )
        self.assertEqual(
            behavior.party_last_known_stop_distance(args, "melee-basic", snapshot, "dps"),
            100,
        )

    def test_active_tank_last_known_stop_distance_derives_safe_default(self):
        args = SimpleNamespace(
            attack_range=350,
            melee_range_buffer=250,
            minimum_melee_stop_distance=85,
            ranged_stop_distance=1000,
            spell_range=1500,
            party_assist_only=True,
            require_target_name="moran the mighty",
            party_active_tank_last_known_stop_distance=0,
        )
        snapshot = {"active_tank_name": "leader"}

        self.assertAlmostEqual(
            behavior.party_last_known_stop_distance(args, "melee-basic", snapshot, "leader"),
            29.75,
        )

    def test_active_tank_uses_faster_reaggro_chase_when_boss_focuses_support(self):
        args = SimpleNamespace(
            attack_range=350,
            require_target_name="golestandt",
        )
        snapshot = {
            "active_tank_name": "leader",
            "leader_target_focus_name": "cleric",
            "leader_target_focus_updated_at": 98.0,
        }
        boss = FakeNpc(10, "Golestandt", 80, 1800.0)

        self.assertEqual(
            behavior.active_tank_reaggro_chase_step(
                args,
                snapshot,
                "leader",
                "melee-basic",
                boss,
                distance=1800.0,
                base_step=40.0,
                now=100.0,
            ),
            160.0,
        )

    def test_active_tank_reaggro_chase_keeps_normal_step_when_boss_focuses_tank(self):
        args = SimpleNamespace(
            attack_range=350,
            require_target_name="golestandt",
        )
        snapshot = {
            "active_tank_name": "leader",
            "leader_target_focus_name": "leader",
            "leader_target_focus_updated_at": 98.0,
        }
        boss = FakeNpc(10, "Golestandt", 80, 1800.0)

        self.assertEqual(
            behavior.active_tank_reaggro_chase_step(
                args,
                snapshot,
                "leader",
                "melee-basic",
                boss,
                distance=1800.0,
                base_step=40.0,
                now=100.0,
            ),
            40.0,
        )

    def test_last_known_chase_is_suppressed_during_tactical_backoff(self):
        snapshot = {"leader_target_id": 77}

        self.assertFalse(
            behavior.should_chase_last_known_shared_target(
                snapshot,
                current_target=77,
                tactical_backoff=True,
            )
        )

    def test_last_known_chase_requires_matching_shared_target(self):
        snapshot = {"leader_target_id": 77}

        self.assertTrue(
            behavior.should_chase_last_known_shared_target(
                snapshot,
                current_target=77,
                tactical_backoff=False,
            )
        )
        self.assertFalse(
            behavior.should_chase_last_known_shared_target(
                snapshot,
                current_target=78,
                tactical_backoff=False,
            )
        )

    def test_shared_target_backoff_point_allows_empty_current_target(self):
        snapshot = {"leader_target_id": 77}

        self.assertTrue(behavior.should_use_shared_target_backoff_point(snapshot, current_target=0))
        self.assertTrue(behavior.should_use_shared_target_backoff_point(snapshot, current_target=77))
        self.assertFalse(behavior.should_use_shared_target_backoff_point(snapshot, current_target=78))

    def test_party_rescue_threat_last_known_destination_uses_shared_add_position(self):
        snapshot = {
            "rescue_threats": [
                {"object_id": 20, "x": 1234, "y": 5678, "z": 90},
                {"object_id": 21, "x": 2234, "y": 6678, "z": 190},
            ],
        }

        destination = behavior.party_rescue_threat_last_known_destination(snapshot, 21)

        self.assertIsNotNone(destination)
        self.assertEqual((destination.x, destination.y, destination.z), (2234, 6678, 190))

    def test_party_rescue_threat_last_known_destination_ignores_unknown_target(self):
        snapshot = {"rescue_threats": [{"object_id": 20, "x": 1234, "y": 5678, "z": 90}]}

        self.assertIsNone(behavior.party_rescue_threat_last_known_destination(snapshot, 22))

    def test_active_tank_reaggro_taunt_is_due_when_boss_focuses_non_tank(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="moran the mighty",
            party_active_tank_reaggro_taunt_interval=1.2,
            party_focus_target_max_age=5.0,
        )
        snapshot = {
            "active_tank_name": "leader",
            "leader_target_focus_name": "dps",
            "leader_target_focus_updated_at": 10.0,
        }

        self.assertTrue(
            behavior.should_active_tank_reaggro_taunt(
                args,
                snapshot,
                "leader",
                "melee-basic",
                now=12.0,
                next_taunt=11.5,
            )
        )
        self.assertFalse(
            behavior.should_active_tank_reaggro_taunt(
                args,
                snapshot,
                "dps",
                "melee-burst",
                now=12.0,
                next_taunt=11.5,
            )
        )
        self.assertFalse(
            behavior.should_active_tank_reaggro_taunt(
                args,
                snapshot,
                "leader",
                "melee-basic",
                now=12.0,
                next_taunt=13.0,
            )
        )

    def test_party_melee_survival_backoff_only_affects_low_health_non_tanks(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="king of the barfog hills",
            party_encounter_mode="boss",
            party_melee_survival_health_percent=55,
            party_melee_survival_resume_health_percent=85,
        )
        snapshot = {
            "active_tank_name": "leader",
        }

        self.assertTrue(
            behavior.should_back_off_for_party_melee_survival(
                args, snapshot, "dps", "melee-burst", 45, now=10.0, backoff_until=0.0
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_melee_survival(
                args, snapshot, "leader", "melee-basic", 45, now=10.0, backoff_until=0.0
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_melee_survival(
                args, snapshot, "wizard", "caster-basic", 45, now=10.0, backoff_until=0.0
            )
        )

    def test_party_melee_survival_backoff_uses_resume_hysteresis(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="king of the barfog hills",
            party_encounter_mode="boss",
            party_melee_survival_health_percent=55,
            party_melee_survival_resume_health_percent=85,
        )
        snapshot = {"active_tank_name": "leader"}

        self.assertTrue(
            behavior.should_back_off_for_party_melee_survival(
                args, snapshot, "dps", "melee-basic", 70, now=10.0, backoff_until=12.0
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_melee_survival(
                args, snapshot, "dps", "melee-basic", 86, now=10.0, backoff_until=12.0
            )
        )
        self.assertFalse(
            behavior.should_back_off_for_party_melee_survival(
                args, snapshot, "dps", "melee-basic", 70, now=13.0, backoff_until=12.0
            )
        )

    def test_ranged_roles_back_off_when_combat_follow_stacks_too_close(self):
        args = SimpleNamespace(
            attack_range=145,
            melee_range_buffer=25,
            minimum_melee_stop_distance=65,
            ranged_stop_distance=900,
            spell_range=1500,
        )

        self.assertTrue(behavior.should_back_off_for_ranged_combat_follow(args, "caster-basic", 300))
        self.assertTrue(behavior.should_back_off_for_ranged_combat_follow(args, "healer-support", 300))
        self.assertFalse(behavior.should_back_off_for_ranged_combat_follow(args, "caster-basic", 900))
        self.assertFalse(behavior.should_back_off_for_ranged_combat_follow(args, "melee-basic", 300))

    def test_ranged_roles_back_off_from_required_boss_target_distance(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="barfog",
            party_encounter_mode="boss",
            attack_range=350,
            melee_range_buffer=250,
            minimum_melee_stop_distance=85,
            ranged_stop_distance=900,
            spell_range=1500,
            boss_ranged_safe_distance=1000,
        )

        self.assertTrue(behavior.should_back_off_from_boss_target(args, "caster-basic", 850))
        self.assertFalse(behavior.should_back_off_from_boss_target(args, "caster-basic", 950))
        self.assertFalse(behavior.should_back_off_from_boss_target(args, "melee-basic", 100))

    def test_ranged_roles_back_off_from_required_home_before_engage(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="barfog",
            party_encounter_mode="boss",
            party_preengage_ranged_safe_distance=1200,
        )

        self.assertTrue(behavior.should_back_off_from_required_home_before_engage(args, "caster-basic", 900, current_target=0))
        self.assertTrue(behavior.should_back_off_from_required_home_before_engage(args, "healer-support", 900, current_target=0))
        self.assertFalse(behavior.should_back_off_from_required_home_before_engage(args, "caster-basic", 1250, current_target=0))
        self.assertFalse(behavior.should_back_off_from_required_home_before_engage(args, "caster-basic", 900, current_target=77))
        self.assertFalse(behavior.should_back_off_from_required_home_before_engage(args, "melee-basic", 900, current_target=0))

    def test_required_boss_non_tanks_regroup_near_leader(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="king of the barfog hills",
            boss_non_tank_follow_distance=450,
            attack_range=145,
            melee_range_buffer=25,
            minimum_melee_stop_distance=65,
            ranged_stop_distance=900,
            spell_range=1500,
        )

        self.assertTrue(behavior.should_follow_leader_during_required_boss(args, "caster-basic", 950))
        self.assertTrue(behavior.should_follow_leader_during_required_boss(args, "healer-support", 950))
        self.assertFalse(behavior.should_follow_leader_during_required_boss(args, "caster-basic", 800))
        self.assertFalse(behavior.should_follow_leader_during_required_boss(args, "healer-support", 800))
        self.assertFalse(behavior.should_follow_leader_during_required_boss(args, "caster-basic", 300))
        self.assertFalse(behavior.should_follow_leader_during_required_boss(args, "melee-basic", 800))

    def test_boss_hazard_message_detects_dragon_telegraphs(self):
        args = SimpleNamespace(boss_hazard_message_backoff_duration=9.0)

        self.assertEqual(behavior.boss_hazard_message_duration(args, "Golestandt takes another powerful breath."), 9.0)
        self.assertEqual(behavior.boss_hazard_message_duration(args, "Golestandt이(가) 주의 깊게 주변을 둘러봅니다."), 9.0)
        self.assertEqual(behavior.boss_hazard_message_duration(args, "Golestandt prepares a massive attack."), 9.0)
        self.assertEqual(behavior.boss_hazard_message_duration(args, "ordinary chat"), 0.0)

    def test_boss_hazard_backoff_applies_to_non_active_tanks_only(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="golestandt",
            party_encounter_mode="boss",
            boss_hazard_message_backoff_distance=2400,
        )
        snapshot = {"active_tank_name": "leader"}

        self.assertTrue(behavior.should_back_off_for_boss_hazard(args, snapshot, "wizard", "caster-basic", now=10.0, hazard_until=12.0))
        self.assertTrue(behavior.should_back_off_for_boss_hazard(args, snapshot, "merc", "melee-burst", now=10.0, hazard_until=12.0))
        self.assertFalse(behavior.should_back_off_for_boss_hazard(args, snapshot, "leader", "melee-basic", now=10.0, hazard_until=12.0))
        self.assertFalse(behavior.should_back_off_for_boss_hazard(args, snapshot, "wizard", "caster-basic", now=13.0, hazard_until=12.0))

    def test_move_away_from_point_increases_distance_from_last_known_boss(self):
        client = StepPathClient()
        client.x = 100
        client.y = 0
        args = SimpleNamespace(movement_speed=165, movement_update_interval=0.25)

        moved = behavior.move_away_from_point(
            client,
            0,
            0,
            step=50,
            min_distance=240,
            args=args,
            target_in_view=False,
        )

        self.assertTrue(moved)
        self.assertGreater(client.x, 100)

    def test_party_state_ready_members_gate_pull(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        args = SimpleNamespace(party_min_ready=2)

        self.assertEqual(state.snapshot()["ready_count"], 1)
        self.assertFalse(behavior.party_ready_for_pull(args, state))

        state.mark_ready("member")
        self.assertEqual(state.snapshot()["ready_count"], 2)
        self.assertTrue(behavior.party_ready_for_pull(args, state))

    def test_party_ready_gate_can_be_disabled(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        args = SimpleNamespace(party_min_ready=0)

        self.assertTrue(behavior.party_ready_for_pull(args, state))

    def test_rotation_skips_unvalidated_spell_requests_by_default(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            spell_levels=[40],
            spell_line_index=9,
            allow_unvalidated_spells=False,
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "caster-basic", 800)

        self.assertIsNone(action)
        self.assertEqual(client.spells, [])

    def test_rotation_can_still_send_raw_spell_requests_when_explicitly_enabled(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            spell_levels=[40],
            spell_line_index=9,
            allow_unvalidated_spells=True,
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "caster-basic", 800)

        self.assertEqual(action, "spell")
        self.assertEqual(client.spells, [(40, 9)])

    def test_rotation_skips_unvalidated_skill_requests_by_default(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            skill_indexes=[2],
            skill_type=1,
            allow_unvalidated_skills=False,
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "melee-basic", 80)

        self.assertIsNone(action)
        self.assertEqual(client.skills, [])

    def test_rotation_can_still_send_raw_skill_requests_when_explicitly_enabled(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            skill_indexes=[2],
            skill_type=1,
            allow_unvalidated_skills=True,
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "melee-basic", 80)

        self.assertEqual(action, "skill")
        self.assertEqual(client.skills, [(2, 1)])

    def test_combat_plan_parses_hybrid_skill_spells_for_healing(self):
        payload = {
            "skills": [
                {
                    "kind": "Spell",
                    "useSkillIndex": 12,
                    "useSkillType": 1,
                    "name": "Greater Reviction",
                    "level": 32,
                    "spell": {
                        "isHealing": True,
                        "isBuff": False,
                        "isHarmful": False,
                        "damage": 0,
                        "range": 1500,
                    },
                }
            ],
            "spellLines": [],
        }

        plan = behavior.parse_combat_usable_plan(payload)

        self.assertEqual(len(plan.heal_spells), 1)
        self.assertEqual(plan.heal_spells[0].use_skill_index, 12)
        self.assertEqual(plan.heal_spells[0].line_index, -1)

    def test_rotation_casts_hybrid_spell_refs_with_use_skill_packet(self):
        client = FakeCombatClient()
        client.last_position_speed = 165.0
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            combat_plan_spell_pool=3,
            support_spell_chance=1.0,
            healer_self_health_percent=65,
            allow_unvalidated_spells=False,
            stationary_cast_actions=True,
        )
        plan = behavior.CombatUsablePlan(
            attack_spells=[
                behavior.UsableSpellRef(
                    line_index=-1,
                    spell_level=50,
                    name="Supreme Judgement",
                    level=50,
                    use_skill_index=48,
                    use_skill_type=1,
                )
            ]
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "caster-basic", 800, plan)

        self.assertEqual(action, "validated_spell")
        self.assertEqual(client.skills, [(48, 1)])
        self.assertEqual(client.spells, [])
        self.assertEqual(client.position_updates[-1], (0.0, True))
        self.assertEqual(client.skill_calls[-1]["speed"], 0.0)

    def test_rotation_spell_actions_preserve_speed_by_default(self):
        client = FakeCombatClient()
        client.last_position_speed = 165.0
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            combat_plan_spell_pool=3,
            support_spell_chance=1.0,
            healer_self_health_percent=65,
            allow_unvalidated_spells=False,
        )
        plan = behavior.CombatUsablePlan(
            attack_spells=[
                behavior.UsableSpellRef(
                    line_index=-1,
                    spell_level=50,
                    name="Supreme Judgement",
                    level=50,
                    use_skill_index=48,
                    use_skill_type=1,
                )
            ]
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "caster-basic", 800, plan)

        self.assertEqual(action, "validated_spell")
        self.assertEqual(client.position_updates, [])
        self.assertEqual(client.skill_calls[-1]["speed"], 165.0)

    def test_rotation_validated_self_heal_marks_target_in_view(self):
        client = FakeCombatClient()
        client.health_percent = 40
        client.last_position_speed = 165.0
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            combat_plan_spell_pool=3,
            healer_self_health_percent=65,
            support_spell_chance=0.0,
            allow_unvalidated_spells=False,
            stationary_cast_actions=True,
        )
        plan = behavior.CombatUsablePlan(
            heal_spells=[
                behavior.UsableSpellRef(
                    line_index=7,
                    spell_level=32,
                    name="Major Heal",
                    level=32,
                )
            ]
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "healer-support", 800, plan)

        self.assertEqual(action, "validated_self_heal_spell")
        self.assertEqual(client.spells, [(32, 7)])
        self.assertTrue(client.spell_calls[-1]["target_in_view"])
        self.assertEqual(client.position_updates[-1], (0.0, True))
        self.assertEqual(client.spell_calls[-1]["speed"], 0.0)

    def test_rotation_raw_self_heal_marks_target_in_view(self):
        client = FakeCombatClient()
        client.health_percent = 40
        client.last_position_speed = 165.0
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            heal_spell_levels=[18],
            heal_spell_line_index=5,
            healer_self_health_percent=65,
            support_spell_chance=0.0,
            allow_unvalidated_spells=True,
            stationary_cast_actions=True,
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "healer-support", 800)

        self.assertEqual(action, "self_heal_spell")
        self.assertEqual(client.spells, [(18, 5)])
        self.assertTrue(client.spell_calls[-1]["target_in_view"])
        self.assertEqual(client.position_updates[-1], (0.0, True))
        self.assertEqual(client.spell_calls[-1]["speed"], 0.0)

    def test_party_friendly_usable_spell_stops_before_cast_by_default(self):
        client = FakeCombatClient()
        client.last_position_speed = 165.0
        args = behavior.build_parser().parse_args([])
        spell = behavior.UsableSpellRef(line_index=7, spell_level=32, name="Major Heal", level=32)

        behavior.cast_party_friendly_usable_spell(client, spell, args, target_in_view=True)

        self.assertEqual(client.position_updates[-1], (0.0, True))
        self.assertEqual(client.spell_calls[-1]["speed"], 0.0)

    def test_party_friendly_cast_hold_covers_normal_cast_time_by_default(self):
        args = behavior.build_parser().parse_args([])

        hold_until, restore_target = behavior.plan_friendly_cast_target_hold(args, now=10.0, current_target=77)

        self.assertEqual(restore_target, 77)
        self.assertGreaterEqual(hold_until - 10.0, 2.4)

    def test_friendly_party_cast_plans_short_enemy_retarget_hold_by_default(self):
        args = behavior.build_parser().parse_args([])

        hold_until, restore_target = behavior.plan_friendly_cast_target_hold(args, now=10.0, current_target=77)

        self.assertEqual(restore_target, 77)
        self.assertGreater(hold_until, 10.0)

    def test_friendly_party_cast_hold_can_be_disabled(self):
        args = behavior.build_parser().parse_args(["--party-friendly-cast-target-hold", "0"])

        hold_until, restore_target = behavior.plan_friendly_cast_target_hold(args, now=10.0, current_target=77)

        self.assertEqual(hold_until, 0.0)
        self.assertEqual(restore_target, 0)

    def test_friendly_party_cast_hold_is_suppressed_during_tactical_backoff(self):
        self.assertTrue(
            behavior.should_hold_friendly_cast_target(
                friendly_cast_hold_until=12.0,
                now=10.0,
                tactical_backoff=False,
            )
        )
        self.assertFalse(
            behavior.should_hold_friendly_cast_target(
                friendly_cast_hold_until=12.0,
                now=10.0,
                tactical_backoff=True,
            )
        )

    def test_friendly_party_cast_hold_is_not_suppressed_by_ranged_spacing_only(self):
        self.assertFalse(
            behavior.friendly_cast_hold_breaking_backoff(
                party_melee_survival_backoff=False,
                boss_hazard_backoff=False,
                party_survival_backoff=False,
                party_focus_target_backoff=False,
                party_focus_pressure_backoff=False,
                ranged_safety_backoff_due=True,
            )
        )


if __name__ == "__main__":
    raise SystemExit(unittest.main())
