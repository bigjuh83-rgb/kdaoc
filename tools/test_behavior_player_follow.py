#!/usr/bin/env python3
"""Unit checks for behavior dummy player-follow selection."""

from __future__ import annotations

import importlib.util
import csv
import json
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
    def __init__(self, object_id: int, name: str, distance: float, realm: int = 1, level: int = 50) -> None:
        self.object_id = object_id
        self.name = name
        self.distance = distance
        self.realm = realm
        self.level = level
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

    def test_auto_train_command_uses_first_configured_combat_spec_line(self) -> None:
        command = behavior.auto_train_command_from_specs("Slash|1;Crush|50;Polearm|1", 5)

        self.assertEqual(command, "/train Crush 5")

    def test_auto_train_command_prefers_ordered_weapon_spec_over_higher_buff_spec(self) -> None:
        command = behavior.auto_train_command_from_specs("Staff|39;Enhancement|45;Rejuvenation|30;Parry|18", 6)

        self.assertEqual(command, "/train Staff 6")

    def test_recent_flee_combat_promotes_to_target_removed_when_object_dies(self) -> None:
        metric = behavior.CombatMetric(
            target_id=22674,
            target_name="giant spider",
            target_level=7,
            outcome="flee",
            duration=64.0,
        )

        promoted = behavior.promote_recent_finished_combat_to_target_removed(
            metric,
            finished_at=100.0,
            now=102.5,
            damage_done=116,
        )

        self.assertTrue(promoted)
        self.assertEqual(metric.outcome, "target_removed")
        self.assertEqual(metric.duration, 66.5)

    def test_recent_flee_combat_without_damage_does_not_promote(self) -> None:
        metric = behavior.CombatMetric(
            target_id=22674,
            target_name="giant spider",
            target_level=7,
            outcome="flee",
            duration=64.0,
        )

        promoted = behavior.promote_recent_finished_combat_to_target_removed(
            metric,
            finished_at=100.0,
            now=102.5,
            damage_done=0,
        )

        self.assertFalse(promoted)
        self.assertEqual(metric.outcome, "flee")

    def test_target_removed_credit_requires_contact_or_close_range(self) -> None:
        args = SimpleNamespace(
            attack_range=350.0,
            max_target_distance=2200.0,
            party_rescue_max_distance=1400.0,
            party_rescue_objective_max_distance=1800.0,
        )
        untouched_far = {"damage_done": 0, "attacks": 0, "skills": 0}
        attacked_far = {"damage_done": 0, "attacks": 1, "skills": 0}
        untouched_close = {"damage_done": 0, "attacks": 0, "skills": 0}

        self.assertFalse(behavior.target_removed_creditable(args, untouched_far, 8500.0))
        self.assertTrue(behavior.target_removed_creditable(args, attacked_far, 8500.0))
        self.assertTrue(behavior.target_removed_creditable(args, untouched_close, 1200.0))

    def test_required_target_completion_waits_for_safe_exit_after_recent_damage(self) -> None:
        args = SimpleNamespace(
            safe_exit_max_seconds=90.0,
            safe_exit_recent_damage_grace=12.0,
            low_health_rest_resume_percent=88,
        )

        self.assertTrue(
            behavior.required_target_completion_needs_safe_exit(
                args,
                now=100.0,
                health_percent=70,
                last_damage_taken_at=95.0,
                last_incoming_damage_at=0.0,
            )
        )
        self.assertFalse(
            behavior.required_target_completion_safe_after_removed(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                now=100.0,
                health_percent=70,
                current_target=0,
                last_damage_taken_at=95.0,
                last_incoming_damage_at=0.0,
                flee_until=0.0,
                rest_until=0.0,
            )
        )

    def test_required_target_completion_allows_exit_after_recovery_and_damage_grace(self) -> None:
        args = SimpleNamespace(
            safe_exit_max_seconds=90.0,
            safe_exit_recent_damage_grace=12.0,
            low_health_rest_resume_percent=88,
        )

        self.assertFalse(
            behavior.required_target_completion_needs_safe_exit(
                args,
                now=120.0,
                health_percent=90,
                last_damage_taken_at=100.0,
                last_incoming_damage_at=0.0,
            )
        )
        self.assertTrue(
            behavior.required_target_completion_safe_after_removed(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                now=120.0,
                health_percent=90,
                current_target=0,
                last_damage_taken_at=100.0,
                last_incoming_damage_at=0.0,
                flee_until=0.0,
                rest_until=0.0,
            )
        )

    def test_auto_train_command_caps_to_configured_spec_level(self) -> None:
        command = behavior.auto_train_command_from_specs("Slash|3;Parry|1", 5)

        self.assertEqual(command, "/train Slash 3")

    def test_auto_train_commands_can_train_all_configured_spec_lines(self) -> None:
        commands = behavior.auto_train_commands_from_specs(
            "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13",
            50,
            full_spec=True,
        )

        self.assertEqual(commands, ["/train Slash 39", "/train Chants 48", "/train Shields 42", "/train Parry 13"])

    def test_format_say_command_uses_player_say_slash_command(self) -> None:
        self.assertEqual(behavior.format_say_command("state: attacking wolf"), "/say state: attacking wolf")

    def test_format_say_command_normalizes_empty_and_long_messages(self) -> None:
        command = behavior.format_say_command("  hello   there  ", max_message_length=5)

        self.assertEqual(command, "/say hello")
        self.assertEqual(behavior.format_say_command(""), "/say ...")

    def test_format_live_control_speech_command_supports_party_and_say_channels(self) -> None:
        self.assertEqual(behavior.format_live_control_speech_command("party", "hello party"), "/g hello party")
        self.assertEqual(behavior.format_live_control_speech_command("say", "hello there"), "/say hello there")

    def test_format_live_control_speech_command_ignores_none_unknown_and_blank_channels(self) -> None:
        self.assertEqual(behavior.format_live_control_speech_command("none", "quiet"), "")
        self.assertEqual(behavior.format_live_control_speech_command("guild", "quiet"), "")
        self.assertEqual(behavior.format_live_control_speech_command("", "quiet"), "")
        self.assertEqual(behavior.format_live_control_speech_command(None, "quiet"), "")

    def test_format_live_control_speech_command_preserves_old_say_channel_behavior(self) -> None:
        self.assertEqual(behavior.format_live_control_speech_command("say", "old payload"), "/say old payload")

    def test_safe_live_control_command_allows_only_operational_allowlist(self) -> None:
        self.assertEqual(behavior.safe_live_control_command("/invite PlayerOne"), "/invite PlayerOne")
        self.assertEqual(behavior.safe_live_control_command("/g hold here"), "/g hold here")
        self.assertEqual(behavior.safe_live_control_command("/say ready"), "/say ready")
        self.assertEqual(behavior.safe_live_control_command("/release"), "")
        self.assertEqual(behavior.safe_live_control_command("/quit"), "")
        self.assertEqual(behavior.safe_live_control_command("hello"), "")

    def test_parse_live_control_bool_handles_false_strings(self) -> None:
        self.assertFalse(behavior.parse_live_control_bool("false"))
        self.assertFalse(behavior.parse_live_control_bool("0"))
        self.assertFalse(behavior.parse_live_control_bool("no"))
        self.assertTrue(behavior.parse_live_control_bool("true"))
        self.assertTrue(behavior.parse_live_control_bool(1))

    def test_live_control_intent_hint_maps_to_action_timers(self) -> None:
        self.assertEqual(behavior.live_control_intent_timer_updates("heal_priority"), {"party_heal"})
        self.assertEqual(behavior.live_control_intent_timer_updates("resurrect_priority"), {"party_resurrect"})
        self.assertEqual(behavior.live_control_intent_timer_updates("cc_add"), {"crowd_control"})
        self.assertEqual(behavior.live_control_intent_timer_updates("cure_priority"), {"party_cure"})
        self.assertEqual(behavior.live_control_intent_timer_updates("unknown"), set())

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

    def test_live_control_overrides_false_string_bool_fields(self) -> None:
        args = SimpleNamespace(hunter_target_api_scout=True)

        updates = behavior.apply_live_control_overrides(args, {"hunter_target_api_scout": "false"})

        self.assertFalse(args.hunter_target_api_scout)
        self.assertEqual(updates["hunter_target_api_scout"], (True, False))


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
        if hasattr(actor, "distance"):
            return actor.distance
        return behavior.horizontal_distance_between_points(self.x, self.y, actor.x, actor.y)

    def horizontal_distance_to(self, actor) -> float:
        if hasattr(actor, "distance"):
            return actor.distance
        return behavior.horizontal_distance_between_points(self.x, self.y, actor.x, actor.y)


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

    def test_startup_service_whispers_teleport_destination_to_nearest_teleporter(self) -> None:
        client = FakeClient(
            npcs=[
                FakeNpc(10, "Town Teleporter", 23, 120.0),
                FakeNpc(11, "Far Teleporter", 23, 900.0),
                FakeNpc(12, "Trainer", 23, 30.0),
            ]
        )
        calls = []
        client.read_packets_for = lambda seconds: calls.append(("read", seconds)) or []
        client.target_object = lambda object_id: calls.append(("target", object_id)) or 0
        client.interact_object = lambda object_id: calls.append(("interact", object_id)) or 0
        client.send_command = lambda command: calls.append(("command", command)) or 0
        action_counts: dict[str, int] = {}

        actions = behavior.run_startup_service_actions(
            client,
            SimpleNamespace(
                startup_service_npc_name="",
                startup_service_scan_seconds=0.0,
                startup_service_interact=False,
                startup_service_buy_slot=[],
                startup_service_buy_count=1,
                startup_service_sell_slot=[],
                startup_service_equip_slot=[],
                startup_service_accept_dialog=False,
                startup_teleporter_npc_name="teleporter",
                startup_teleport_destination="Cotswold Village",
                startup_teleport_scan_seconds=0.5,
                startup_teleport_approach_distance=150.0,
                startup_teleport_approach_timeout=20.0,
                startup_teleport_interact=True,
                startup_teleport_warmup_whisper=[],
                startup_teleport_warmup_delay=1.6,
                startup_teleport_wait_seconds=1.25,
                npc_max_age=30.0,
            ),
            action_counts,
        )

        self.assertEqual(actions, 4)
        self.assertIn(("target", 10), calls)
        self.assertIn(("interact", 10), calls)
        self.assertIn(("command", '/whisper "Cotswold Village"'), calls)
        self.assertEqual(action_counts["startup_teleport_target"], 1)
        self.assertEqual(action_counts["startup_teleport_whisper"], 1)
        self.assertEqual(action_counts["startup_teleport_wait"], 1)

    def test_startup_teleporter_home_keeps_closing_until_teleporter_visible(self) -> None:
        class HomeSearchClient(StepPathClient):
            def __init__(self) -> None:
                super().__init__()
                self.npc = FakeNpc(10, "Town Teleporter", 23, 0.0)
                self.npc.x = 1000
                self.npc.y = 0
                self.npc.z = 0
                self.calls: list[tuple[str, object]] = []
                self.messages = []

            def read_packets_for(self, seconds: float):
                self.calls.append(("read", seconds))
                return []

            def visible_npcs(self, max_age: float = 60.0, include_peace: bool = False):
                return [self.npc] if self.distance_to(self.npc) <= 80.0 else []

            def distance_to(self, actor) -> float:
                return behavior.horizontal_distance_between_points(self.x, self.y, int(actor.x), int(actor.y))

            def target_object(self, object_id: int) -> int:
                self.calls.append(("target", object_id))
                return 0

            def interact_object(self, object_id: int) -> int:
                self.calls.append(("interact", object_id))
                return 0

            def send_command(self, command: str) -> int:
                self.calls.append(("command", command))
                return 0

        client = HomeSearchClient()
        action_counts: dict[str, int] = {}

        behavior.run_startup_service_actions(
            client,
            SimpleNamespace(
                startup_service_npc_name="",
                startup_service_scan_seconds=0.0,
                startup_service_interact=False,
                startup_service_buy_slot=[],
                startup_service_buy_count=1,
                startup_service_sell_slot=[],
                startup_service_equip_slot=[],
                startup_service_accept_dialog=False,
                startup_teleporter_npc_name="teleporter",
                startup_teleport_destination="Cotswold Village",
                startup_teleport_scan_seconds=0.0,
                startup_teleport_approach_distance=80.0,
                startup_teleport_approach_timeout=20.0,
                startup_teleporter_home=behavior.Waypoint(1000, 0, 0),
                startup_teleporter_home_stop_distance=900.0,
                startup_teleporter_home_timeout=1.0,
                startup_teleport_interact=True,
                startup_teleport_warmup_whisper=[],
                startup_teleport_warmup_delay=0.0,
                startup_teleport_wait_seconds=0.0,
                smooth_move_interval=0.0,
                smooth_movement=False,
                move_step=500.0,
                movement_speed=None,
                movement_update_interval=0.0,
                nav_api_url=None,
                npc_max_age=30.0,
            ),
            action_counts,
            path_state=behavior.PathMovementState(None, 1, None),
        )

        self.assertLessEqual(client.distance_to(client.npc), 80.0)
        self.assertIn(("target", 10), client.calls)
        self.assertNotIn("startup_teleporter_missing", action_counts)

    def test_startup_teleporter_home_timeout_scales_with_far_home(self) -> None:
        fake_now = 0.0

        class FarHomeSearchClient(StepPathClient):
            def __init__(self) -> None:
                super().__init__()
                self.npc = FakeNpc(10, "Town Teleporter", 23, 0.0)
                self.npc.x = 16000
                self.npc.y = 0
                self.npc.z = 0
                self.calls: list[tuple[str, object]] = []
                self.messages = []

            def read_packets_for(self, seconds: float):
                nonlocal fake_now
                fake_now += max(0.0, seconds)
                return []

            def visible_npcs(self, max_age: float = 60.0, include_peace: bool = False):
                return [self.npc] if self.distance_to(self.npc) <= 80.0 else []

            def distance_to(self, actor) -> float:
                return behavior.horizontal_distance_between_points(self.x, self.y, int(actor.x), int(actor.y))

            def target_object(self, object_id: int) -> int:
                self.calls.append(("target", object_id))
                return 0

            def interact_object(self, object_id: int) -> int:
                self.calls.append(("interact", object_id))
                return 0

            def send_command(self, command: str) -> int:
                self.calls.append(("command", command))
                return 0

        client = FarHomeSearchClient()
        action_counts: dict[str, int] = {}
        args = SimpleNamespace(
            startup_service_npc_name="",
            startup_service_scan_seconds=0.0,
            startup_service_interact=False,
            startup_service_buy_slot=[],
            startup_service_buy_count=1,
            startup_service_sell_slot=[],
            startup_service_equip_slot=[],
            startup_service_accept_dialog=False,
            startup_teleporter_npc_name="teleporter",
            startup_teleport_destination="Cotswold Village",
            startup_teleport_scan_seconds=0.0,
            startup_teleport_approach_distance=80.0,
            startup_teleport_approach_timeout=20.0,
            startup_teleporter_home=behavior.Waypoint(16000, 0, 0),
            startup_teleporter_home_stop_distance=900.0,
            startup_teleporter_home_timeout=1.0,
            startup_teleport_interact=True,
            startup_teleport_warmup_whisper=[],
            startup_teleport_warmup_delay=0.0,
            startup_teleport_wait_seconds=0.0,
            smooth_move_interval=0.2,
            smooth_movement=False,
            move_step=500.0,
            movement_speed=None,
            movement_update_interval=0.0,
            nav_api_url=None,
            npc_max_age=30.0,
        )

        with patch.object(behavior.time, "monotonic", lambda: fake_now):
            behavior.run_startup_service_actions(
                client,
                args,
                action_counts,
                path_state=behavior.PathMovementState(None, 1, None),
            )

        self.assertLessEqual(client.distance_to(client.npc), 80.0)
        self.assertIn(("target", 10), client.calls)
        self.assertNotIn("startup_teleporter_missing", action_counts)

    def test_startup_teleporter_home_timeout_zero_disables_home_search(self) -> None:
        class DisabledHomeSearchClient(StepPathClient):
            def __init__(self) -> None:
                super().__init__()
                self.messages = []

            def read_packets_for(self, seconds: float):
                return []

            def visible_npcs(self, max_age: float = 60.0, include_peace: bool = False):
                return []

        client = DisabledHomeSearchClient()
        action_counts: dict[str, int] = {}

        behavior.run_startup_service_actions(
            client,
            SimpleNamespace(
                startup_service_npc_name="",
                startup_service_scan_seconds=0.0,
                startup_service_interact=False,
                startup_service_buy_slot=[],
                startup_service_buy_count=1,
                startup_service_sell_slot=[],
                startup_service_equip_slot=[],
                startup_service_accept_dialog=False,
                startup_teleporter_npc_name="teleporter",
                startup_teleport_destination="Cotswold Village",
                startup_teleport_scan_seconds=0.0,
                startup_teleport_approach_distance=80.0,
                startup_teleport_approach_timeout=20.0,
                startup_teleporter_home=behavior.Waypoint(16000, 0, 0),
                startup_teleporter_home_stop_distance=900.0,
                startup_teleporter_home_timeout=0.0,
                startup_teleport_interact=True,
                startup_teleport_warmup_whisper=[],
                startup_teleport_warmup_delay=0.0,
                startup_teleport_wait_seconds=0.0,
                smooth_move_interval=0.2,
                smooth_movement=False,
                move_step=500.0,
                movement_speed=None,
                movement_update_interval=0.0,
                nav_api_url=None,
                npc_max_age=30.0,
            ),
            action_counts,
            path_state=behavior.PathMovementState(None, 1, None),
        )

        self.assertEqual(client.moves, [])
        self.assertEqual(action_counts["startup_teleporter_missing"], 1)
        self.assertNotIn("startup_teleporter_home_move", action_counts)

    def test_startup_teleporter_home_skips_when_objective_is_closer(self) -> None:
        class ObjectiveCloserClient(StepPathClient):
            def __init__(self) -> None:
                super().__init__()
                self.messages = []

            def read_packets_for(self, seconds: float):
                return []

            def visible_npcs(self, max_age: float = 60.0, include_peace: bool = False):
                return []

            def distance_to(self, actor) -> float:
                return behavior.horizontal_distance_between_points(self.x, self.y, int(actor.x), int(actor.y))

        client = ObjectiveCloserClient()
        action_counts: dict[str, int] = {}

        behavior.run_startup_service_actions(
            client,
            SimpleNamespace(
                startup_service_npc_name="",
                startup_service_scan_seconds=0.0,
                startup_service_interact=False,
                startup_service_buy_slot=[],
                startup_service_buy_count=1,
                startup_service_sell_slot=[],
                startup_service_equip_slot=[],
                startup_service_accept_dialog=False,
                startup_teleporter_npc_name="teleporter",
                startup_teleport_destination="Vindsaul Faste",
                startup_teleport_scan_seconds=0.0,
                startup_teleport_approach_distance=80.0,
                startup_teleport_approach_timeout=20.0,
                startup_teleporter_home=behavior.Waypoint(10000, 0, 0),
                startup_teleporter_home_stop_distance=900.0,
                startup_teleporter_home_timeout=90.0,
                startup_teleport_interact=True,
                startup_teleport_warmup_whisper=[],
                startup_teleport_warmup_delay=0.0,
                startup_teleport_wait_seconds=0.0,
                required_target_home=behavior.Waypoint(1000, 0, 0),
                required_target_home_stop_distance=900.0,
                required_target_home_hunt_distance=0.0,
                target_home_max_distance=0.0,
                smooth_move_interval=0.2,
                smooth_movement=False,
                move_step=500.0,
                movement_speed=None,
                movement_update_interval=0.0,
                nav_api_url=None,
                npc_max_age=30.0,
            ),
            action_counts,
            path_state=behavior.PathMovementState(None, 1, None),
        )

        self.assertEqual(client.moves, [])
        self.assertEqual(action_counts["startup_teleporter_home_skip"], 1)
        self.assertEqual(action_counts["startup_teleporter_missing"], 1)

    def test_startup_teleporter_home_moves_when_teleporter_is_closer_than_objective(self) -> None:
        class TeleporterCloserClient(StepPathClient):
            def __init__(self) -> None:
                super().__init__()
                self.npc = FakeNpc(10, "Town Teleporter", 23, 0.0)
                self.npc.x = 1000
                self.npc.y = 0
                self.npc.z = 0
                self.calls: list[tuple[str, object]] = []
                self.messages = []

            def read_packets_for(self, seconds: float):
                return []

            def visible_npcs(self, max_age: float = 60.0, include_peace: bool = False):
                return [self.npc] if self.distance_to(self.npc) <= 80.0 else []

            def distance_to(self, actor) -> float:
                return behavior.horizontal_distance_between_points(self.x, self.y, int(actor.x), int(actor.y))

            def target_object(self, object_id: int) -> int:
                self.calls.append(("target", object_id))
                return 0

            def interact_object(self, object_id: int) -> int:
                self.calls.append(("interact", object_id))
                return 0

            def send_command(self, command: str) -> int:
                self.calls.append(("command", command))
                return 0

        client = TeleporterCloserClient()
        action_counts: dict[str, int] = {}

        behavior.run_startup_service_actions(
            client,
            SimpleNamespace(
                startup_service_npc_name="",
                startup_service_scan_seconds=0.0,
                startup_service_interact=False,
                startup_service_buy_slot=[],
                startup_service_buy_count=1,
                startup_service_sell_slot=[],
                startup_service_equip_slot=[],
                startup_service_accept_dialog=False,
                startup_teleporter_npc_name="teleporter",
                startup_teleport_destination="Vindsaul Faste",
                startup_teleport_scan_seconds=0.0,
                startup_teleport_approach_distance=80.0,
                startup_teleport_approach_timeout=20.0,
                startup_teleporter_home=behavior.Waypoint(1000, 0, 0),
                startup_teleporter_home_stop_distance=900.0,
                startup_teleporter_home_timeout=90.0,
                startup_teleport_interact=True,
                startup_teleport_warmup_whisper=[],
                startup_teleport_warmup_delay=0.0,
                startup_teleport_wait_seconds=0.0,
                required_target_home=behavior.Waypoint(10000, 0, 0),
                required_target_home_stop_distance=900.0,
                required_target_home_hunt_distance=0.0,
                target_home_max_distance=0.0,
                smooth_move_interval=0.0,
                smooth_movement=False,
                move_step=500.0,
                movement_speed=None,
                movement_update_interval=0.0,
                nav_api_url=None,
                npc_max_age=30.0,
            ),
            action_counts,
            path_state=behavior.PathMovementState(None, 1, None),
        )

        self.assertLessEqual(client.distance_to(client.npc), 80.0)
        self.assertIn(("target", 10), client.calls)
        self.assertIn(("command", '/whisper "Vindsaul Faste"'), client.calls)
        self.assertGreaterEqual(action_counts["startup_teleporter_home_move"], 1)
        self.assertNotIn("startup_teleporter_home_skip", action_counts)

    def test_startup_teleport_success_message_syncs_local_position(self) -> None:
        client = FakeClient(npcs=[FakeNpc(10, "Town Teleporter", 23, 120.0)])
        calls = []
        client.x = 531637
        client.y = 479005
        client.z = 2200
        client.zone_id = 1
        client.messages = [
            SimpleNamespace(text='Master Visur says, "Cotswold Village(으)로 순간이동시켜 드리겠습니다."')
        ]
        client.read_packets_for = lambda seconds: calls.append(("read", seconds)) or []
        client.target_object = lambda object_id: calls.append(("target", object_id)) or 0
        client.interact_object = lambda object_id: calls.append(("interact", object_id)) or 0
        client.send_command = lambda command: calls.append(("command", command)) or 0
        client.send_position_update = lambda speed=0.0, target_in_view=False: calls.append(
            ("position", client.zone_id, client.x, client.y, client.z, speed, target_in_view)
        ) or 0
        client.trace_movement = lambda event, **fields: calls.append(("trace", event, fields))
        action_counts: dict[str, int] = {}

        actions = behavior.run_startup_service_actions(
            client,
            SimpleNamespace(
                startup_service_npc_name="",
                startup_service_scan_seconds=0.0,
                startup_service_interact=False,
                startup_service_buy_slot=[],
                startup_service_buy_count=1,
                startup_service_sell_slot=[],
                startup_service_equip_slot=[],
                startup_service_accept_dialog=False,
                startup_teleporter_npc_name="teleporter",
                startup_teleport_destination="Cotswold Village",
                startup_teleport_scan_seconds=0.0,
                startup_teleport_approach_distance=150.0,
                startup_teleport_approach_timeout=20.0,
                startup_teleport_interact=True,
                startup_teleport_warmup_whisper=[],
                startup_teleport_warmup_delay=1.6,
                startup_teleport_wait_seconds=1.25,
                npc_max_age=30.0,
            ),
            action_counts,
        )

        self.assertEqual(actions, 5)
        self.assertEqual((client.zone_id, client.x, client.y, client.z), (1, 560574, 511800, 2280))
        self.assertIn(("trace", "startup_teleport_sync", {"destination": "Cotswold Village", "zone_id": 1, "x": 560574, "y": 511800, "z": 2280}), calls)
        self.assertIn(("position", 1, 560574, 511800, 2280, 0.0, False), calls)
        self.assertEqual(action_counts["startup_teleport_sync"], 1)

    def test_startup_teleport_sync_uses_client_zone_from_ground_map(self) -> None:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", delete=False) as handle:
            json.dump(
                {
                    "type": "daoc-client-zone-mpk",
                    "zones_root": ".",
                    "zones": {
                        "100": {"name": "Vale of Mularn", "offset_x": 92, "offset_y": 82, "width": 8, "height": 8},
                        "111": {"name": "Uppland", "offset_x": 88, "offset_y": 74, "width": 8, "height": 8},
                    },
                },
                handle,
            )
            ground_z_map = handle.name

        client = FakeClient(npcs=[FakeNpc(10, "Stor Gothi Annark", 23, 120.0)])
        client.x = 773327
        client.y = 749653
        client.z = 4552
        client.zone_id = 100
        client.messages = [SimpleNamespace(text='Stor Gothi Annark says, "Svasud Faste(으)로 순간이동시켜 드리겠습니다."')]
        calls = []
        client.read_packets_for = lambda seconds: calls.append(("read", seconds)) or []
        client.target_object = lambda object_id: calls.append(("target", object_id)) or 0
        client.interact_object = lambda object_id: calls.append(("interact", object_id)) or 0
        client.send_command = lambda command: calls.append(("command", command)) or 0
        client.send_position_update = lambda speed=0.0, target_in_view=False: calls.append(
            ("position", client.zone_id, client.x, client.y, client.z, speed, target_in_view)
        ) or 0
        client.trace_movement = lambda event, **fields: calls.append(("trace", event, fields))
        action_counts: dict[str, int] = {}

        behavior.run_startup_service_actions(
            client,
            SimpleNamespace(
                startup_service_npc_name="",
                startup_service_scan_seconds=0.0,
                startup_service_interact=False,
                startup_service_buy_slot=[],
                startup_service_buy_count=1,
                startup_service_sell_slot=[],
                startup_service_equip_slot=[],
                startup_service_accept_dialog=False,
                startup_teleporter_npc_name="gothi",
                startup_teleport_destination="Svasud Faste",
                startup_teleport_scan_seconds=0.0,
                startup_teleport_approach_distance=150.0,
                startup_teleport_approach_timeout=20.0,
                startup_teleport_interact=True,
                startup_teleport_warmup_whisper=[],
                startup_teleport_warmup_delay=1.6,
                startup_teleport_wait_seconds=0.0,
                ground_z_map=ground_z_map,
                npc_max_age=30.0,
            ),
            action_counts,
        )

        self.assertEqual((client.zone_id, client.x, client.y, client.z), (111, 767242, 669591, 5736))
        self.assertIn(("position", 111, 767242, 669591, 5736, 0.0, False), calls)

    def test_startup_teleport_warmup_waits_before_destination_whisper(self) -> None:
        client = FakeClient(npcs=[FakeNpc(10, "Town Teleporter", 23, 120.0)])
        calls = []
        client.read_packets_for = lambda seconds: calls.append(("read", seconds)) or []
        client.target_object = lambda object_id: calls.append(("target", object_id)) or 0
        client.interact_object = lambda object_id: calls.append(("interact", object_id)) or 0
        client.send_command = lambda command: calls.append(("command", command)) or 0
        action_counts: dict[str, int] = {}

        actions = behavior.run_startup_service_actions(
            client,
            SimpleNamespace(
                startup_service_npc_name="",
                startup_service_scan_seconds=0.0,
                startup_service_interact=False,
                startup_service_buy_slot=[],
                startup_service_buy_count=1,
                startup_service_sell_slot=[],
                startup_service_equip_slot=[],
                startup_service_accept_dialog=False,
                startup_teleporter_npc_name="teleporter",
                startup_teleport_destination="Cotswold Village",
                startup_teleport_scan_seconds=0.0,
                startup_teleport_approach_distance=150.0,
                startup_teleport_approach_timeout=20.0,
                startup_teleport_interact=True,
                startup_teleport_warmup_whisper=["towns"],
                startup_teleport_warmup_delay=1.6,
                startup_teleport_wait_seconds=0.0,
                npc_max_age=30.0,
            ),
            action_counts,
        )

        self.assertEqual(actions, 6)
        self.assertEqual(
            [call for call in calls if call[0] in {"command", "read"}],
            [("command", "/whisper towns"), ("read", 1.6), ("command", '/whisper "Cotswold Village"')],
        )
        self.assertEqual(calls.count(("target", 10)), 2)
        self.assertEqual(action_counts["startup_teleport_warmup_whisper"], 1)
        self.assertEqual(action_counts["startup_teleport_warmup_wait"], 1)
        self.assertEqual(action_counts["startup_teleport_retarget"], 1)

    def test_startup_teleport_approach_timeout_scales_with_visible_far_teleporter(self) -> None:
        client = FakeClient(npcs=[FakeNpc(10, "Stor Gothi Annark", 23, 4300.0)])
        target = client.npcs[0]

        timeout = behavior.startup_teleport_approach_timeout(
            SimpleNamespace(
                startup_teleport_approach_timeout=20.0,
                movement_speed=240.0,
                move_step=260.0,
            ),
            client,
            target,
            approach_distance=80.0,
        )

        self.assertGreaterEqual(timeout, 31.0)

    def test_startup_teleport_approach_timeout_keeps_configured_value_for_near_teleporter(self) -> None:
        client = FakeClient(npcs=[FakeNpc(10, "Town Teleporter", 23, 120.0)])
        target = client.npcs[0]

        timeout = behavior.startup_teleport_approach_timeout(
            SimpleNamespace(
                startup_teleport_approach_timeout=20.0,
                movement_speed=240.0,
                move_step=260.0,
            ),
            client,
            target,
            approach_distance=150.0,
        )

        self.assertEqual(timeout, 20.0)


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
        self.heading = 0
        self.zone_id = 1
        self.moves: list[tuple[int, int, int, float, float]] = []
        self.movement_speeds: list[float | None] = []
        self.headings: list[int] = []

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

    def send_heading(self, heading: int, *, drain_after: bool = True) -> int:
        self.heading = heading
        self.headings.append(heading)
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

    def test_required_target_home_hunt_ready_allows_search_inside_hunt_radius_without_visible_target(self):
        client = FakeClient(npcs=[])
        client.x = 348378
        client.y = 478312
        client.z = 5749
        args = SimpleNamespace(
            required_target_home=behavior.Waypoint(348637, 479175, 5744),
            required_target_home_hunt_distance=6200.0,
            target_home_max_distance=6200.0,
            npc_max_age=60.0,
            include_peace_npcs=True,
            min_target_level=5,
            max_target_level=7,
            player_level=6,
            max_target_level_delta=1,
            require_target_name="",
            prefer_target_name="eirebug,spraggon,large frog",
            avoid_target_name="",
            max_target_distance=2200.0,
        )

        self.assertTrue(behavior.required_target_home_hunt_ready(client, args))

    def test_required_target_home_hunt_ready_stays_false_outside_hunt_radius(self):
        client = FakeClient(npcs=[])
        client.x = 344500
        client.y = 474500
        client.z = 5372
        args = SimpleNamespace(
            required_target_home=behavior.Waypoint(348637, 479175, 5744),
            required_target_home_hunt_distance=1000.0,
            target_home_max_distance=1000.0,
            npc_max_age=60.0,
            include_peace_npcs=True,
            min_target_level=5,
            max_target_level=7,
            player_level=6,
            max_target_level_delta=1,
            require_target_name="",
            prefer_target_name="eirebug,spraggon,large frog",
            avoid_target_name="",
            max_target_distance=2200.0,
        )

        self.assertFalse(behavior.required_target_home_hunt_ready(client, args))

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

    def test_dynamic_flee_destination_overrides_town_threshold_when_not_critical(self):
        threat = FakeNpc(10, "wild lucradan", 12, 250.0)
        threat.x = 335100
        threat.y = 532100
        threat.z = 5520
        threat.has_aggro = True
        client = FakeClient(npcs=[threat])
        client.x = 335457
        client.y = 532254
        client.z = 5510
        client.health_percent = 81
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=6000.0,
            flee_safe_point_distance=5200.0,
            flee_critical_health_percent=45,
            flee_critical_safe_point_distance=9000.0,
            flee_town_health_percent=99,
            flee_home=behavior.Waypoint(344580, 474580, 5372),
            required_target_home=behavior.Waypoint(335831, 533105, 5612),
            npc_max_age=30.0,
            player_level=10,
            avoid_target_name="",
            flee_safe_api_scout=False,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        self.assertNotEqual((destination.x, destination.y, destination.z), (344580, 474580, 5372))

    def test_critical_health_flee_stages_egress_away_from_objective_before_home(self):
        threat = FakeNpc(10, "spindly rock crab", 9, 108.0)
        threat.x = 772543
        threat.y = 834197
        threat.z = 4390
        threat.has_aggro = True
        client = FakeClient(npcs=[threat])
        client.x = 772223
        client.y = 834734
        client.z = 4470
        client.health_percent = 40
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=6000.0,
            flee_safe_point_distance=5200.0,
            flee_critical_health_percent=45,
            flee_critical_safe_point_distance=9000.0,
            flee_town_health_percent=99,
            flee_home=behavior.Waypoint(771152, 836380, 4624),
            required_target_home=behavior.Waypoint(772717, 833982, 4348),
            npc_max_age=30.0,
            player_level=10,
            avoid_target_name="",
            flee_safe_api_scout=False,
            target_home_max_distance=2800.0,
            combat_home_leash_distance=2800.0,
            required_target_home_hunt_distance=2800.0,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        before = behavior.horizontal_distance_between_points(client.x, client.y, args.required_target_home.x, args.required_target_home.y)
        after = behavior.horizontal_distance_between_points(destination.x, destination.y, args.required_target_home.x, args.required_target_home.y)
        self.assertGreater(after, before)
        self.assertNotEqual((destination.x, destination.y, destination.z), (771152, 836380, 4624))

    def test_combat_flee_destination_stages_egress_before_home_near_objective(self):
        threat = FakeNpc(10, "moorlich", 48, 120.0)
        threat.x = 333352
        threat.y = 670001
        threat.z = 2734
        threat.has_aggro = True
        client = FakeClient(npcs=[threat])
        client.x = 333580
        client.y = 669906
        client.z = 2734
        client.health_percent = 39
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=6000.0,
            flee_safe_point_distance=9000.0,
            flee_critical_health_percent=45,
            flee_critical_safe_point_distance=14000.0,
            flee_town_health_percent=99,
            flee_home=behavior.Waypoint(369957, 679721, 5540),
            required_target_home=behavior.Waypoint(332701, 669142, 2712),
            npc_max_age=30.0,
            player_level=50,
            avoid_target_name="",
            flee_safe_api_scout=False,
            target_home_max_distance=2800.0,
            combat_home_leash_distance=2800.0,
            required_target_home_hunt_distance=2800.0,
        )
        active_combat = {
            "target_x": threat.x,
            "target_y": threat.y,
        }

        destination = behavior.flee_escape_destination_for_combat(args, client, active_combat)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        before = behavior.horizontal_distance_between_points(client.x, client.y, args.required_target_home.x, args.required_target_home.y)
        after = behavior.horizontal_distance_between_points(destination.x, destination.y, args.required_target_home.x, args.required_target_home.y)
        self.assertGreater(after, before)
        self.assertNotEqual((destination.x, destination.y, destination.z), (369957, 679721, 5540))

    def test_active_combat_flee_destination_runs_away_from_current_attacker(self):
        client = FakeClient(npcs=[])
        client.x = 510012
        client.y = 612605
        client.z = 1827
        client.health_percent = 78
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_point_distance=5200.0,
            flee_critical_health_percent=65,
            flee_critical_safe_point_distance=9000.0,
        )
        active_combat = {
            "target_x": 509490,
            "target_y": 612324,
        }

        destination = behavior.flee_escape_destination_from_active_combat(args, client, active_combat)

        self.assertIsNotNone(destination)
        before = behavior.horizontal_distance_between_points(client.x, client.y, active_combat["target_x"], active_combat["target_y"])
        after = behavior.horizontal_distance_between_points(destination.x, destination.y, active_combat["target_x"], active_combat["target_y"])
        self.assertGreater(after, before)
        self.assertGreater(destination.x, client.x)
        self.assertGreater(destination.y, client.y)

    def test_active_combat_flee_destination_prefers_town_when_health_is_low(self):
        client = FakeClient(npcs=[])
        client.x = 770081
        client.y = 830802
        client.z = 4624
        client.health_percent = 34
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_point_distance=5200.0,
            flee_town_health_percent=99,
            flee_home=behavior.Waypoint(771152, 836380, 4624),
            required_target_home=None,
        )
        active_combat = {
            "target_x": 772717,
            "target_y": 833982,
        }

        destination = behavior.flee_escape_destination_from_active_combat(args, client, active_combat)

        self.assertIsNotNone(destination)
        self.assertEqual((destination.x, destination.y, destination.z), (771152, 836380, 4624))
        self.assertTrue(destination.key.startswith("flee-home:"))

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

    def test_critical_health_flee_keeps_using_safe_point_when_threat_is_visible(self):
        threat = FakeNpc(10, "orchard nipper", 6, 120.0)
        threat.x = 335448
        threat.y = 521292
        threat.z = 4911
        client = FakeClient(npcs=[threat])
        client.x = 335720
        client.y = 521630
        client.z = 4971
        client.health_percent = 22
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=3200.0,
            flee_safe_point_distance=2200.0,
            flee_critical_health_percent=65,
            flee_critical_safe_point_distance=4200.0,
            flee_town_health_percent=10,
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            required_target_home=behavior.Waypoint(335600, 521600, 4959),
            npc_max_age=30.0,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        self.assertNotEqual((destination.x, destination.y, destination.z), (344500, 474500, 5372))

    def test_critical_health_flee_falls_back_to_town_path_when_no_dynamic_safe_point_exists(self):
        client = FakeClient(npcs=[])
        client.x = 335720
        client.y = 521630
        client.z = 4971
        client.health_percent = 9
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=3200.0,
            flee_safe_point_distance=2200.0,
            flee_critical_health_percent=65,
            flee_critical_safe_point_distance=4200.0,
            flee_town_health_percent=10,
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            required_target_home=behavior.Waypoint(335600, 521600, 4959),
            npc_max_age=30.0,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertEqual((destination.x, destination.y, destination.z), (344500, 474500, 5372))
        self.assertTrue(destination.key.startswith("flee-home:"))

    def test_critical_flee_under_pressure_keeps_safe_point_outside_objective_egress_radius(self):
        threat = FakeNpc(10, "moorlich", 48, 120.0)
        threat.x = 330601
        threat.y = 666011
        threat.z = 2671
        threat.has_aggro = True
        client = FakeClient(npcs=[threat])
        client.x = 329565
        client.y = 663867
        client.z = 2845
        client.health_percent = 23
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=6000.0,
            flee_safe_point_distance=9000.0,
            flee_critical_health_percent=45,
            flee_critical_safe_point_distance=14000.0,
            flee_town_health_percent=99,
            flee_home=behavior.Waypoint(369957, 679721, 5540),
            required_target_home=behavior.Waypoint(332701, 669142, 2712),
            npc_max_age=30.0,
            player_level=50,
            avoid_target_name="",
            flee_safe_api_scout=False,
            target_home_max_distance=2800.0,
            combat_home_leash_distance=2800.0,
            required_target_home_hunt_distance=2800.0,
        )

        normal_destination = behavior.flee_escape_destination(args, client)
        pressure_destination = behavior.flee_escape_destination_under_pressure(args, client)

        self.assertIsNotNone(normal_destination)
        self.assertTrue(normal_destination.key.startswith("flee-home:"))
        self.assertIsNotNone(pressure_destination)
        self.assertTrue(pressure_destination.key.startswith("flee-safe:"))
        before = behavior.horizontal_distance_between_points(client.x, client.y, threat.x, threat.y)
        after = behavior.horizontal_distance_between_points(pressure_destination.x, pressure_destination.y, threat.x, threat.y)
        self.assertGreater(after, before)

    def test_critical_health_dynamic_flee_uses_longer_safe_point(self):
        threat = FakeNpc(10, "orchard nipper", 6, 120.0)
        threat.x = 335448
        threat.y = 521292
        threat.z = 4911
        client = FakeClient(npcs=[threat])
        client.x = 335720
        client.y = 521630
        client.z = 4971
        client.health_percent = 30
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=5200.0,
            flee_safe_point_distance=2200.0,
            flee_critical_health_percent=65,
            flee_critical_safe_point_distance=4200.0,
            flee_town_health_percent=10,
            flee_home=None,
            required_target_home=None,
            npc_max_age=30.0,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        travelled = behavior.horizontal_distance_between_points(client.x, client.y, destination.x, destination.y)
        self.assertGreater(travelled, 4000.0)

    def test_dynamic_flee_destination_avoids_hazard_along_escape_corridor(self):
        pressure = FakeNpc(10, "moorlich", 48, 1000.0)
        pressure.x = 1000
        pressure.y = 0
        pressure.has_aggro = True
        corridor_hazard = FakeNpc(11, "pikeman", 50, 3000.0)
        corridor_hazard.x = -3000
        corridor_hazard.y = 0
        client = FakeClient(npcs=[pressure, corridor_hazard])
        client.x = 0
        client.y = 0
        client.z = 100
        client.health_percent = 50
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=1200.0,
            flee_safe_point_distance=5000.0,
            flee_critical_health_percent=0,
            flee_critical_safe_point_distance=0.0,
            player_level=50,
            flee_home=None,
            required_target_home=None,
            npc_max_age=30.0,
            avoid_target_name="",
            flee_safe_api_scout=False,
            flee_path_threat_corridor_radius=900.0,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        path_distance = behavior.point_to_segment_distance(
            corridor_hazard.x,
            corridor_hazard.y,
            client.x,
            client.y,
            destination.x,
            destination.y,
        )
        self.assertGreater(path_distance, args.flee_path_threat_corridor_radius)

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

    def test_dynamic_flee_destination_scores_mobs_near_candidate_not_only_current_position(self):
        chasing_target = FakeNpc(10, "orchard nipper", 6, 250.0)
        chasing_target.x = 0
        chasing_target.y = 0
        high_threat = FakeNpc(11, "cluricaun trip", 9, 4200.0)
        high_threat.x = 4200
        high_threat.y = 0
        client = FakeClient(npcs=[chasing_target, high_threat])
        client.x = 0
        client.y = 0
        client.z = 100
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=3200.0,
            flee_safe_point_distance=4200.0,
            player_level=6,
            flee_home=None,
            required_target_home=None,
            npc_max_age=30.0,
            avoid_target_name="",
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        self.assertLess(destination.x, 0)

    def test_dynamic_flee_destination_prioritizes_active_aggro_vector(self):
        chasing_target = FakeNpc(10, "wild boar", 10, 250.0)
        chasing_target.x = 509490
        chasing_target.y = 612324
        chasing_target.has_aggro = True
        high_threat = FakeNpc(11, "nearby boar", 10, 2000.0)
        high_threat.x = 515000
        high_threat.y = 614000
        client = FakeClient(npcs=[chasing_target, high_threat])
        client.x = 509606
        client.y = 612358
        client.z = 1832
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=6000.0,
            flee_safe_point_distance=5200.0,
            player_level=10,
            flee_home=None,
            required_target_home=None,
            npc_max_age=30.0,
            avoid_target_name="",
            flee_safe_api_scout=False,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        before = behavior.horizontal_distance_between_points(client.x, client.y, chasing_target.x, chasing_target.y)
        after = behavior.horizontal_distance_between_points(destination.x, destination.y, chasing_target.x, chasing_target.y)
        self.assertGreater(after, before)
        self.assertGreater(destination.x, client.x)

    def test_dynamic_flee_destination_avoids_hazard_when_active_vector_runs_into_it(self):
        chasing_target = FakeNpc(10, "bandit", 6, 250.0)
        chasing_target.x = 0
        chasing_target.y = -200
        chasing_target.has_aggro = True
        chasing_target.in_combat = True
        high_threat = FakeNpc(11, "devout filidh", 20, 3800.0)
        high_threat.x = 0
        high_threat.y = 4200
        client = FakeClient(npcs=[chasing_target, high_threat])
        client.x = 0
        client.y = 0
        client.z = 100
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=6000.0,
            flee_safe_point_distance=5200.0,
            player_level=10,
            flee_home=None,
            required_target_home=None,
            npc_max_age=30.0,
            avoid_target_name="",
            flee_safe_api_scout=False,
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        before = behavior.horizontal_distance_between_points(client.x, client.y, high_threat.x, high_threat.y)
        after = behavior.horizontal_distance_between_points(destination.x, destination.y, high_threat.x, high_threat.y)
        self.assertGreater(after, before)

    def test_combat_flee_uses_dynamic_safe_point_before_blind_attacker_vector(self):
        chasing_target = FakeNpc(10, "bandit", 6, 250.0)
        chasing_target.x = 0
        chasing_target.y = -200
        chasing_target.has_aggro = True
        chasing_target.in_combat = True
        high_threat = FakeNpc(11, "devout filidh", 20, 3800.0)
        high_threat.x = 0
        high_threat.y = 4200
        client = FakeClient(npcs=[chasing_target, high_threat])
        client.x = 0
        client.y = 0
        client.z = 100
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=6000.0,
            flee_safe_point_distance=5200.0,
            flee_critical_health_percent=65,
            flee_critical_safe_point_distance=9000.0,
            player_level=10,
            flee_home=None,
            required_target_home=None,
            npc_max_age=30.0,
            avoid_target_name="",
            flee_safe_api_scout=False,
        )
        active_combat = {
            "target_x": 0,
            "target_y": -200,
        }

        destination = behavior.flee_escape_destination_for_combat(args, client, active_combat)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        before = behavior.horizontal_distance_between_points(client.x, client.y, high_threat.x, high_threat.y)
        after = behavior.horizontal_distance_between_points(destination.x, destination.y, high_threat.x, high_threat.y)
        self.assertGreater(after, before)

    def test_dynamic_flee_destination_keeps_moving_when_threat_pressure_remains(self):
        chasing_target = FakeNpc(10, "orchard nipper", 6, 250.0)
        chasing_target.x = 0
        chasing_target.y = 0
        client = FakeClient(npcs=[chasing_target])
        client.x = 0
        client.y = 0
        client.z = 100
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=10000.0,
            flee_safe_point_distance=2200.0,
            player_level=6,
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            required_target_home=behavior.Waypoint(335600, 521600, 4959),
            npc_max_age=30.0,
            avoid_target_name="",
        )

        destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        self.assertNotEqual((destination.x, destination.y, destination.z), (344500, 474500, 5372))

    def test_dynamic_flee_destination_falls_back_to_pressure_away_point_before_home(self):
        chasing_target = FakeNpc(10, "orchard nipper", 6, 250.0)
        chasing_target.x = 1000
        chasing_target.y = 0
        client = FakeClient(npcs=[chasing_target])
        client.x = 0
        client.y = 0
        client.z = 100
        args = SimpleNamespace(
            flee_dynamic_safe_point=True,
            flee_safe_threat_radius=3200.0,
            flee_safe_point_distance=2200.0,
            player_level=6,
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            required_target_home=behavior.Waypoint(335600, 521600, 4959),
            npc_max_age=30.0,
            avoid_target_name="",
            flee_safe_api_scout=False,
        )

        with patch.object(behavior, "select_dynamic_flee_destination_from_npcs", return_value=None):
            destination = behavior.flee_escape_destination(args, client)

        self.assertIsNotNone(destination)
        self.assertTrue(destination.key.startswith("flee-safe:"))
        self.assertLess(destination.x, 0)
        self.assertNotEqual((destination.x, destination.y, destination.z), (344500, 474500, 5372))

    def test_flee_threat_snapshot_detects_nearby_visible_threat(self):
        threat = FakeNpc(10, "orchard nipper", 6, 900.0)
        client = FakeClient(npcs=[threat])
        args = SimpleNamespace(
            flee_safe_threat_radius=3200.0,
            flee_safe_point_distance=2200.0,
            player_level=6,
            avoid_target_name="",
            flee_safe_api_scout=False,
            npc_max_age=30.0,
            include_peace_npcs=False,
        )

        snapshot = behavior.flee_threat_snapshot(args, client, member_name="GrowthHib701")

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["flee_threat_name"], "orchard nipper")
        self.assertEqual(snapshot["flee_threat_distance"], 900.0)

    def test_flee_threat_snapshot_prioritizes_active_aggro_over_closer_passive_threat(self):
        passive = FakeNpc(10, "red wolfhound", 6, 300.0)
        active = FakeNpc(11, "orchard nipper", 6, 900.0)
        active.has_aggro = True
        active.in_combat = True
        active.target = "GrowthHib701"
        client = FakeClient(npcs=[passive, active])
        args = SimpleNamespace(
            flee_safe_threat_radius=3200.0,
            flee_safe_point_distance=2200.0,
            player_level=6,
            avoid_target_name="",
            flee_safe_api_scout=False,
            npc_max_age=30.0,
            include_peace_npcs=False,
        )

        snapshot = behavior.flee_threat_snapshot(args, client, member_name="GrowthHib701")

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["flee_threat_id"], 11)
        self.assertEqual(snapshot["flee_threat_name"], "orchard nipper")

    def test_flee_threat_snapshot_is_active_requires_aggro_combat_or_dummy_target(self):
        self.assertFalse(behavior.flee_threat_snapshot_is_active(None))
        self.assertFalse(
            behavior.flee_threat_snapshot_is_active(
                {
                    "flee_threat_active": False,
                    "flee_threat_has_aggro": False,
                    "flee_threat_in_combat": False,
                    "flee_threat_target": "",
                }
            )
        )
        self.assertTrue(behavior.flee_threat_snapshot_is_active({"flee_threat_has_aggro": True}))
        self.assertTrue(behavior.flee_threat_snapshot_is_active({"flee_threat_in_combat": True}))
        self.assertTrue(behavior.flee_threat_snapshot_is_active({"flee_threat_targets_dummy": True}))
        self.assertFalse(behavior.flee_threat_snapshot_is_active({"flee_threat_target": "OtherPlayer"}))

    def test_flee_pressure_replan_cooldown_keeps_escape_direction_stable(self):
        args = SimpleNamespace(flee_duration=16.0, flee_move_interval=0.35)

        self.assertGreaterEqual(behavior.flee_pressure_replan_cooldown(args), 8.0)
        self.assertGreaterEqual(behavior.flee_pressure_replan_cooldown(args), 12.0)

    def test_flee_threat_snapshot_detects_chasing_api_threat_beyond_near_radius(self):
        client = FakeClient(npcs=[])
        client.health_percent = 70
        args = SimpleNamespace(
            flee_safe_threat_radius=1200.0,
            flee_safe_point_distance=2500.0,
            flee_critical_health_percent=65,
            flee_critical_safe_point_distance=4200.0,
            player_level=6,
            avoid_target_name="",
            flee_safe_api_scout=True,
            npc_max_age=30.0,
            include_peace_npcs=False,
        )
        chasing = SimpleNamespace(
            object_id=11,
            name="orchard nipper",
            x=0,
            y=0,
            z=0,
            level=6,
            distance=2500.0,
            has_aggro=True,
            in_combat=True,
            target="GrowthHib701",
        )

        with patch.object(behavior, "fetch_flee_safe_api_observations", return_value=[chasing]):
            snapshot = behavior.flee_threat_snapshot(args, client, member_name="GrowthHib701")

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["flee_threat_id"], 11)
        self.assertTrue(snapshot["flee_threat_has_aggro"])

    def test_flee_threat_snapshot_uses_critical_distance_for_chasing_api_threat(self):
        client = FakeClient(npcs=[])
        client.health_percent = 30
        args = SimpleNamespace(
            flee_safe_threat_radius=1200.0,
            flee_safe_point_distance=2200.0,
            flee_critical_health_percent=65,
            flee_critical_safe_point_distance=4200.0,
            player_level=6,
            avoid_target_name="",
            flee_safe_api_scout=True,
            npc_max_age=30.0,
            include_peace_npcs=False,
        )
        chasing = SimpleNamespace(
            object_id=12,
            name="orchard nipper",
            x=0,
            y=0,
            z=0,
            level=6,
            distance=5000.0,
            has_aggro=True,
            in_combat=True,
            target="GrowthHib701",
        )

        with patch.object(behavior, "fetch_flee_safe_api_observations", return_value=[chasing]):
            snapshot = behavior.flee_threat_snapshot(args, client, member_name="GrowthHib701")

        self.assertIsNotNone(snapshot)
        self.assertEqual(snapshot["flee_threat_id"], 12)

    def test_flee_safe_api_url_uses_critical_flee_distance_for_scan_radius(self):
        client = FakeClient(npcs=[])
        client.x = 335720
        client.y = 521630
        client.health_percent = 30
        args = SimpleNamespace(
            host="localhost",
            api_port=10300,
            flee_safe_threat_radius=3200.0,
            flee_safe_point_distance=2200.0,
            flee_critical_health_percent=65,
            flee_critical_safe_point_distance=4200.0,
            player_level=6,
            flee_safe_api_limit=80,
        )

        url = behavior.build_flee_safe_api_url(args, client, 1)

        self.assertIn("radius=7400", url)

    def test_flee_threat_snapshot_ignores_far_passive_threat(self):
        threat = FakeNpc(10, "orchard nipper", 6, 5000.0)
        client = FakeClient(npcs=[threat])
        args = SimpleNamespace(
            flee_safe_threat_radius=1200.0,
            flee_safe_point_distance=2500.0,
            player_level=6,
            avoid_target_name="",
            flee_safe_api_scout=False,
            npc_max_age=30.0,
            include_peace_npcs=False,
        )

        self.assertIsNone(behavior.flee_threat_snapshot(args, client, member_name="GrowthHib701"))

    def test_should_flee_losing_combat_requires_low_health_and_pressure(self):
        args = SimpleNamespace(
            flee_health_percent=35,
            low_health_rest_percent=70,
            flee_pressure_health_percent=85,
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
        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=84, now=20.0))
        self.assertTrue(behavior.should_flee_losing_combat(args, active_combat, health_percent=70, now=20.0))
        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=86, now=20.0))
        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=30, now=14.0))

        active_combat["damage_taken"] = 12
        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=30, now=20.0))

    def test_should_flee_losing_combat_counts_healing_as_pressure_relief(self):
        args = SimpleNamespace(
            flee_health_percent=55,
            low_health_rest_percent=70,
            flee_pressure_health_percent=85,
            flee_min_combat_seconds=4.0,
            flee_min_damage_taken=20,
            flee_damage_taken_ratio=1.5,
        )
        active_combat = {
            "started": 10.0,
            "damage_done": 128,
            "damage_taken": 195,
            "healing_received": 28,
        }

        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=70, now=20.0))

    def test_should_flee_losing_combat_retreats_early_when_ambushed_before_dealing_damage(self):
        args = SimpleNamespace(
            flee_health_percent=35,
            flee_pressure_health_percent=85,
            flee_min_combat_seconds=8.0,
            flee_min_damage_taken=20,
            flee_damage_taken_ratio=1.5,
        )
        active_combat = {
            "started": 10.0,
            "damage_done": 0,
            "damage_taken": 31,
        }

        self.assertTrue(behavior.should_flee_losing_combat(args, active_combat, health_percent=85, now=12.0))
        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=86, now=12.0))

    def test_should_flee_losing_combat_retreats_at_critical_health_even_when_trading_damage(self):
        args = SimpleNamespace(
            flee_health_percent=55,
            flee_pressure_health_percent=85,
            flee_critical_health_percent=65,
            flee_min_combat_seconds=8.0,
            flee_min_damage_taken=20,
            flee_damage_taken_ratio=1.5,
        )
        active_combat = {
            "started": 10.0,
            "damage_done": 54,
            "damage_taken": 42,
        }

        self.assertTrue(behavior.should_flee_losing_combat(args, active_combat, health_percent=60, now=12.0))
        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=66, now=20.0))

    def test_required_target_commit_blocks_losing_combat_flee_above_floor(self):
        args = SimpleNamespace(
            flee_health_percent=55,
            low_health_rest_percent=70,
            flee_pressure_health_percent=85,
            flee_critical_health_percent=65,
            flee_min_combat_seconds=4.0,
            flee_min_damage_taken=20,
            flee_damage_taken_ratio=1.5,
            require_target_name="frost spectre",
            required_target_tank_commit_health_percent=45,
        )
        active_combat = {
            "started": 10.0,
            "target_name": "frost spectre",
            "damage_done": 0,
            "damage_taken": 3601,
        }

        self.assertFalse(behavior.should_flee_losing_combat(args, active_combat, health_percent=55, now=20.0))
        self.assertTrue(behavior.should_flee_losing_combat(args, active_combat, health_percent=45, now=20.0))

    def test_party_tank_holds_required_objective_when_healer_alive(self):
        args = SimpleNamespace(
            require_target_name="moorlich",
            flee_critical_health_percent=45,
        )
        active_combat = {"target_name": "moorlich", "damage_done": 465, "damage_taken": 1287}
        snapshot = {
            "active_tank_name": "tank",
            "members": [
                {"name": "tank", "object_id": 1, "health_percent": 53, "role": "melee-basic"},
                {"name": "cleric", "object_id": 2, "health_percent": 100, "role": "healer-support"},
            ],
        }

        self.assertTrue(
            behavior.should_party_tank_hold_required_objective_for_healer(
                args,
                snapshot,
                "tank",
                active_combat,
                health_percent=53,
            )
        )
        self.assertFalse(
            behavior.should_party_tank_hold_required_objective_for_healer(
                args,
                snapshot,
                "tank",
                active_combat,
                health_percent=45,
            )
        )

    def test_party_tank_holds_required_objective_above_boss_survival_floor(self):
        args = SimpleNamespace(
            require_target_name="moorlich",
            flee_critical_health_percent=45,
            party_survival_active_tank_health_percent=35,
        )
        active_combat = {"target_name": "moorlich", "damage_done": 465, "damage_taken": 1287}
        snapshot = {
            "active_tank_name": "tank",
            "members": [
                {"name": "tank", "object_id": 1, "health_percent": 40, "role": "melee-basic"},
                {"name": "cleric", "object_id": 2, "health_percent": 100, "role": "healer-support"},
            ],
        }

        self.assertTrue(
            behavior.should_party_tank_hold_required_objective_for_healer(
                args,
                snapshot,
                "tank",
                active_combat,
                health_percent=40,
            )
        )
        self.assertFalse(
            behavior.should_party_tank_hold_required_objective_for_healer(
                args,
                snapshot,
                "tank",
                active_combat,
                health_percent=35,
            )
        )

    def test_active_tank_match_is_case_insensitive(self):
        snapshot = {"active_tank_name": "Growthalb1301"}

        self.assertTrue(behavior.party_member_is_active_tank(snapshot, "GrowthAlb1301"))

    def test_party_tank_does_not_abandon_required_rescue_focus_with_live_healer(self):
        args = SimpleNamespace(
            require_target_name="moorlich",
            flee_melee_counterattack_health_floor=55,
            flee_critical_health_percent=45,
            party_rescue_aggro=True,
        )
        snapshot = {
            "active_tank_name": "Growthalb1301",
            "leader_target_id": 3723,
            "leader_target_name": "moorlich",
            "rescue_target_id": 3723,
            "rescue_target_name": "moorlich",
            "members": [
                {"name": "Growthalb1301", "object_id": 1, "health_percent": 53, "role": "melee-basic"},
                {"name": "Growthalb1302", "object_id": 2, "health_percent": 91, "role": "healer-support"},
            ],
        }

        self.assertFalse(
            behavior.should_abandon_party_rescue_counterattack_for_flee(
                args,
                snapshot,
                current_target=3723,
                current_health_percent=53,
                previous_health_percent=92,
                member_name="GrowthAlb1301",
            )
        )
        self.assertTrue(
            behavior.should_abandon_party_rescue_counterattack_for_flee(
                args,
                snapshot,
                current_target=3723,
                current_health_percent=44,
                previous_health_percent=53,
                member_name="GrowthAlb1301",
            )
        )

    def test_hunter_wind_down_only_after_a_kill_when_segment_is_almost_over(self):
        args = SimpleNamespace(hunter_min_time_left_for_new_target=55.0)

        self.assertTrue(
            behavior.should_hunter_wind_down_before_segment_end(
                args,
                time_left_seconds=40.0,
                target_removed_count=1,
                current_target=0,
            )
        )
        self.assertFalse(
            behavior.should_hunter_wind_down_before_segment_end(
                args,
                time_left_seconds=40.0,
                target_removed_count=0,
                current_target=0,
            )
        )
        self.assertFalse(
            behavior.should_hunter_wind_down_before_segment_end(
                args,
                time_left_seconds=70.0,
                target_removed_count=1,
                current_target=0,
            )
        )
        self.assertFalse(
            behavior.should_hunter_wind_down_before_segment_end(
                args,
                time_left_seconds=40.0,
                target_removed_count=1,
                current_target=123,
            )
        )

    def test_recent_melee_contact_delays_early_flee_until_critical_health(self):
        args = SimpleNamespace(
            flee_critical_health_percent=65,
        )
        active_combat = {
            "damage_done": 0,
            "damage_taken": 31,
        }

        self.assertTrue(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=84,
                recent_incoming_melee=True,
                target_distance=0.0,
            )
        )
        self.assertFalse(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=65,
                recent_incoming_melee=True,
            )
        )
        self.assertFalse(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=84,
                recent_incoming_melee=False,
                target_distance=0.0,
            )
        )

    def test_recent_melee_contact_does_not_delay_flee_when_still_out_of_counterattack_range(self):
        args = SimpleNamespace(
            flee_critical_health_percent=65,
            flee_melee_counterattack_health_floor=75,
            flee_melee_counterattack_max_distance=450.0,
        )
        active_combat = {
            "damage_done": 0,
            "damage_taken": 31,
        }

        self.assertFalse(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=84,
                recent_incoming_melee=True,
                target_distance=661.0,
            )
        )
        self.assertTrue(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=84,
                recent_incoming_melee=True,
                target_distance=250.0,
            )
        )

    def test_recent_melee_contact_delays_flee_when_player_is_still_trading_well(self):
        args = SimpleNamespace(
            flee_critical_health_percent=65,
        )
        active_combat = {
            "damage_done": 70,
            "damage_taken": 57,
        }

        self.assertTrue(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=81,
                recent_incoming_melee=True,
                target_distance=250.0,
            )
        )

    def test_recent_melee_contact_delays_flee_until_minimum_counterattacks(self):
        args = SimpleNamespace(
            flee_critical_health_percent=65,
            flee_melee_counterattack_min_attacks=3,
            flee_melee_counterattack_health_floor=75,
        )
        active_combat = {
            "damage_done": 4,
            "damage_taken": 95,
            "attacks": 1,
        }

        self.assertTrue(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=81,
                recent_incoming_melee=True,
                target_distance=250.0,
            )
        )

        self.assertFalse(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=70,
                recent_incoming_melee=True,
                target_distance=250.0,
            )
        )

        active_combat["attacks"] = 3
        self.assertFalse(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=81,
                recent_incoming_melee=True,
                target_distance=250.0,
            )
        )

    def test_required_target_melee_counterattack_ignores_noncritical_health_floor(self):
        args = SimpleNamespace(
            require_target_name="frost spectre",
            flee_critical_health_percent=65,
            flee_melee_counterattack_health_floor=75,
            flee_melee_counterattack_max_distance=1800,
        )
        active_combat = {
            "target_name": "frost spectre",
            "damage_done": 0,
            "damage_taken": 290,
        }

        self.assertTrue(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=68,
                recent_incoming_melee=True,
                target_distance=1608.0,
            )
        )
        self.assertFalse(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=64,
                recent_incoming_melee=True,
                target_distance=1608.0,
            )
        )

    def test_required_target_tank_commit_extends_counterattack_below_critical_floor(self):
        args = SimpleNamespace(
            require_target_name="frost spectre",
            flee_critical_health_percent=65,
            required_target_tank_commit_health_percent=45,
            flee_melee_counterattack_health_floor=75,
            flee_melee_counterattack_max_distance=1800,
        )
        active_combat = {
            "target_name": "frost spectre",
            "damage_done": 0,
            "damage_taken": 580,
        }

        self.assertTrue(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=55,
                recent_incoming_melee=True,
                target_distance=350.0,
            )
        )
        self.assertFalse(
            behavior.should_delay_early_flee_for_melee_counterattack(
                args,
                active_combat,
                health_percent=45,
                recent_incoming_melee=True,
                target_distance=350.0,
            )
        )

    def test_off_target_add_damage_triggers_pressure_flee(self):
        args = SimpleNamespace(
            flee_pressure_health_percent=85,
            flee_min_damage_taken=20,
        )
        active_combat = {
            "damage_done": 160,
            "damage_taken": 53,
            "off_target_damage_taken": 35,
        }

        self.assertTrue(behavior.should_flee_multi_aggro_combat(args, active_combat, health_percent=82))
        self.assertFalse(behavior.should_flee_multi_aggro_combat(args, active_combat, health_percent=90))
        self.assertTrue(
            behavior.should_attempt_multi_aggro_crowd_control(
                crowd_control_due=True,
                multi_aggro_counterattack_hold=False,
            )
        )

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
        self.assertFalse(
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

    def test_should_flee_instead_of_low_health_rest_after_recent_damage(self):
        args = SimpleNamespace(low_health_rest_percent=70, incoming_damage_melee_grace=4.0)

        self.assertTrue(
            behavior.should_flee_instead_of_low_health_rest(
                args,
                current_health_percent=47,
                previous_health_percent=60,
                recent_damage_age_seconds=0.2,
                active_threat=False,
            )
        )
        self.assertTrue(
            behavior.should_flee_instead_of_low_health_rest(
                args,
                current_health_percent=47,
                previous_health_percent=47,
                recent_damage_age_seconds=0.2,
                active_threat=False,
            )
        )
        self.assertFalse(
            behavior.should_flee_instead_of_low_health_rest(
                args,
                current_health_percent=47,
                previous_health_percent=47,
                recent_damage_age_seconds=12.0,
                active_threat=False,
            )
        )
        self.assertFalse(
            behavior.should_flee_instead_of_low_health_rest(
                args,
                current_health_percent=88,
                previous_health_percent=100,
                recent_damage_age_seconds=0.2,
                active_threat=True,
            )
        )

    def test_should_flee_untracked_damage_when_target_is_lost(self):
        args = SimpleNamespace(flee_health_percent=55, low_health_rest_percent=70, flee_pressure_health_percent=85)

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
        self.assertTrue(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=68,
                last_health_percent=76,
                current_target=0,
                flee_until=0.0,
                now=10.0,
            )
        )
        self.assertTrue(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=84,
                last_health_percent=90,
                current_target=0,
                flee_until=0.0,
                now=10.0,
            )
        )
        self.assertFalse(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=86,
                last_health_percent=90,
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

    def test_required_target_recent_damage_commits_before_low_health_flee(self):
        args = SimpleNamespace(require_target_name="frost spectre", required_target_tank_commit_health_percent=45)

        self.assertTrue(
            behavior.should_commit_required_target_from_recent_damage(
                args,
                current_health_percent=63,
                previous_health_percent=79,
                current_target=0,
                last_damage_attacker_name="frost spectre",
            )
        )
        self.assertFalse(
            behavior.should_commit_required_target_from_recent_damage(
                args,
                current_health_percent=45,
                previous_health_percent=79,
                current_target=0,
                last_damage_attacker_name="frost spectre",
            )
        )
        self.assertFalse(
            behavior.should_commit_required_target_from_recent_damage(
                args,
                current_health_percent=63,
                previous_health_percent=79,
                current_target=123,
                last_damage_attacker_name="frost spectre",
            )
        )
        self.assertFalse(
            behavior.should_commit_required_target_from_recent_damage(
                args,
                current_health_percent=63,
                previous_health_percent=79,
                current_target=0,
                last_damage_attacker_name="fenrir snowscout",
            )
        )
        self.assertFalse(
            behavior.should_commit_required_target_from_recent_damage(
                args,
                current_health_percent=63,
                previous_health_percent=79,
                current_target=0,
                last_damage_attacker_name="frost spectre",
                required_home_hunt_ready=False,
            )
        )

    def test_required_target_recent_damage_does_not_commit_while_drop_aggro_recovering(self):
        args = SimpleNamespace(require_target_name="frost spectre", required_target_tank_commit_health_percent=45)

        self.assertFalse(
            behavior.should_commit_required_target_from_recent_damage(
                args,
                current_health_percent=63,
                previous_health_percent=79,
                current_target=0,
                last_damage_attacker_name="frost spectre",
                behavior_state=behavior.DummyBehaviorState.DropAggroAndRecover,
            )
        )

    def test_should_hold_untracked_damage_flee_for_party_rescue_counterattack(self):
        args = SimpleNamespace(
            party_rescue_aggro=False,
            flee_health_percent=55,
            low_health_rest_percent=70,
            flee_pressure_health_percent=85,
            flee_melee_counterattack_health_floor=75,
        )

        self.assertFalse(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=84,
                last_health_percent=90,
                current_target=0,
                flee_until=0.0,
                now=10.0,
                party_rescue_target_id=123,
            )
        )
        self.assertTrue(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=75,
                last_health_percent=84,
                current_target=0,
                flee_until=0.0,
                now=11.0,
                party_rescue_target_id=123,
            )
        )

    def test_recent_party_rescue_intent_holds_untracked_flee_above_counterattack_floor(self):
        args = SimpleNamespace(
            flee_health_percent=55,
            low_health_rest_percent=70,
            flee_pressure_health_percent=85,
            flee_melee_counterattack_health_floor=55,
        )

        self.assertFalse(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=84,
                last_health_percent=86,
                current_target=0,
                flee_until=0.0,
                now=10.0,
                current_target_intent=behavior.TargetIntent.party_rescue,
            )
        )
        self.assertTrue(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=55,
                last_health_percent=84,
                current_target=0,
                flee_until=0.0,
                now=11.0,
                current_target_intent=behavior.TargetIntent.party_rescue,
            )
        )

    def test_active_party_rescue_focus_holds_untracked_flee_above_counterattack_floor(self):
        args = SimpleNamespace(
            party_rescue_aggro=True,
            flee_health_percent=55,
            low_health_rest_percent=70,
            flee_pressure_health_percent=85,
            flee_melee_counterattack_health_floor=55,
        )
        active = {
            "target_id": 200,
            "target_name": "fenrir snowscout",
            "target_level": 38,
            "target_intent": "party_rescue",
            "attacks": 1,
            "skills": 0,
            "damage_done": 492,
            "damage_taken": 354,
        }

        self.assertFalse(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=84,
                last_health_percent=90,
                current_target=0,
                flee_until=0.0,
                now=10.0,
                party_rescue_target_id=8346,
                last_damage_attacker_name="fenrir tracker",
                force_flee_from_health_drop=True,
                active_combat=active,
                current_target_intent=behavior.TargetIntent.party_rescue,
            )
        )
        self.assertTrue(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=55,
                last_health_percent=84,
                current_target=0,
                flee_until=0.0,
                now=11.0,
                party_rescue_target_id=8346,
                last_damage_attacker_name="fenrir tracker",
                force_flee_from_health_drop=True,
                active_combat=active,
                current_target_intent=behavior.TargetIntent.party_rescue,
            )
        )

    def test_objective_add_damage_does_not_force_untracked_flee(self):
        args = SimpleNamespace(
            objective_add_target_name="fenrir snowscout,fenrir prophet",
            require_target_name="fenrir tracker",
            flee_pressure_health_percent=85,
            flee_untracked_health_drop_percent=15,
        )

        self.assertFalse(
            behavior.should_force_flee_from_non_required_health_drop(
                args,
                current_health_percent=84,
                previous_health_percent=100,
                last_damage_attacker_name="fenrir snowscout",
            )
        )
        self.assertFalse(
            behavior.should_force_flee_from_non_required_health_drop(
                args,
                current_health_percent=84,
                previous_health_percent=100,
                last_damage_attacker_name="",
            )
        )
        self.assertTrue(
            behavior.should_force_flee_from_non_required_health_drop(
                args,
                current_health_percent=84,
                previous_health_percent=100,
                last_damage_attacker_name="winter wolf",
            )
        )

    def test_should_hold_untracked_damage_flee_for_required_target_commit(self):
        args = SimpleNamespace(
            require_target_name="frost spectre",
            required_target_tank_commit_health_percent=45,
            flee_health_percent=55,
            low_health_rest_percent=70,
            flee_pressure_health_percent=85,
        )

        self.assertFalse(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=67,
                last_health_percent=78,
                current_target=0,
                flee_until=0.0,
                now=10.0,
                last_damage_attacker_name="frost spectre",
            )
        )
        self.assertTrue(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=45,
                last_health_percent=67,
                current_target=0,
                flee_until=0.0,
                now=11.0,
                last_damage_attacker_name="frost spectre",
            )
        )

    def test_non_tank_can_flee_required_target_damage_at_pressure_threshold(self):
        args = SimpleNamespace(
            require_target_name="frost spectre",
            required_target_tank_commit_health_percent=45,
            flee_health_percent=55,
            low_health_rest_percent=70,
            flee_pressure_health_percent=85,
        )

        self.assertTrue(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=84,
                last_health_percent=90,
                current_target=0,
                flee_until=0.0,
                now=10.0,
                last_damage_attacker_name="frost spectre",
                allow_required_target_flee=True,
            )
        )

    def test_party_reaggro_holds_non_tank_required_target_generic_flee(self):
        args = SimpleNamespace(
            require_target_name="frost spectre",
            party_focus_target_backoff=True,
            party_active_tank_reaggro_taunt_interval=0.8,
        )
        snapshot = {
            "leader_target_id": 200,
            "leader_target_name": "frost spectre",
            "active_tank_name": "Tank",
            "active_tank_object_id": 10,
        }

        self.assertTrue(
            behavior.should_hold_required_target_untracked_flee_for_party_reaggro(
                args,
                snapshot,
                member_name="Cleric",
                attacker_name="frost spectre",
                party_ready_for_objective=True,
            )
        )

    def test_party_reaggro_does_not_hold_required_target_flee_when_party_not_ready(self):
        args = SimpleNamespace(
            require_target_name="frost spectre",
            party_focus_target_backoff=True,
            party_active_tank_reaggro_taunt_interval=0.8,
        )
        snapshot = {
            "leader_target_id": 200,
            "leader_target_name": "frost spectre",
            "active_tank_name": "Tank",
            "active_tank_object_id": 10,
        }

        self.assertFalse(
            behavior.should_hold_required_target_untracked_flee_for_party_reaggro(
                args,
                snapshot,
                member_name="Cleric",
                attacker_name="frost spectre",
                party_ready_for_objective=False,
            )
        )

    def test_party_rescue_snapshot_actor_allows_active_tank_to_counterattack_cached_threat(self):
        args = SimpleNamespace(
            party_rescue_aggro=True,
            party_rescue_max_age=10.0,
            flee_melee_counterattack_health_floor=75,
        )
        snapshot = {
            "active_tank_name": "Tank",
            "leader_name": "Tank",
            "rescue_target_id": 123,
            "rescue_target_name": "fenrir snowscout",
            "rescue_target_x": 755944,
            "rescue_target_y": 656441,
            "rescue_target_z": 6572,
            "rescue_target_level": 48,
            "rescue_requested_at": 95.0,
        }

        actor = behavior.party_rescue_actor_from_snapshot(
            args,
            snapshot,
            member_name="Tank",
            action_rotation="melee-basic",
            health_percent=93,
            now=100.0,
        )

        self.assertIsNotNone(actor)
        self.assertEqual(actor.object_id, 123)
        self.assertEqual(actor.name, "fenrir snowscout")
        self.assertEqual((actor.x, actor.y, actor.z), (755944, 656441, 6572))

    def test_party_rescue_snapshot_actor_allows_id_only_counterattack(self):
        args = SimpleNamespace(
            party_rescue_aggro=True,
            party_rescue_max_age=10.0,
            flee_melee_counterattack_health_floor=75,
        )
        snapshot = {
            "active_tank_name": "Tank",
            "rescue_target_id": 123,
            "rescue_target_name": "fenrir snowscout",
            "rescue_requested_at": 95.0,
        }

        actor = behavior.party_rescue_actor_from_snapshot(
            args,
            snapshot,
            member_name="Tank",
            action_rotation="melee-basic",
            health_percent=93,
            now=100.0,
        )

        self.assertIsNotNone(actor)
        self.assertEqual(actor.object_id, 123)
        self.assertEqual((actor.x, actor.y, actor.z), (0, 0, 0))

    def test_party_rescue_snapshot_actor_allows_melee_to_recover_unanchored_objective_pressure(self):
        args = SimpleNamespace(
            party_rescue_aggro=True,
            party_rescue_max_age=10.0,
            flee_melee_counterattack_health_floor=55,
            party_assist_only=True,
            require_target_name="moorlich",
            party_encounter_mode="standard",
            party_rescue_assist_after=4.0,
            party_assist_rescue_target=False,
            party_local_rescue_target=False,
        )
        snapshot = {
            "active_tank_name": "Tank",
            "leader_target_id": 0,
            "rescue_target_id": 9458,
            "rescue_target_name": "moorlich",
            "rescue_target_x": 333966,
            "rescue_target_y": 669529,
            "rescue_target_z": 2707,
            "rescue_target_level": 48,
            "rescue_target_objective_add": True,
            "rescue_member_name": "Dps",
            "rescue_requested_at": 95.0,
        }

        actor = behavior.party_rescue_actor_from_snapshot(
            args,
            snapshot,
            member_name="Dps",
            action_rotation="melee-burst",
            health_percent=82,
            now=100.0,
        )

        self.assertIsNotNone(actor)
        self.assertEqual(actor.object_id, 9458)
        self.assertEqual(actor.name, "moorlich")

    def test_party_rescue_snapshot_actor_keeps_non_objective_cached_add_on_tank(self):
        args = SimpleNamespace(
            party_rescue_aggro=True,
            party_rescue_max_age=10.0,
            flee_melee_counterattack_health_floor=55,
            party_assist_only=True,
            require_target_name="moorlich",
            party_encounter_mode="standard",
            party_rescue_assist_after=4.0,
            party_assist_rescue_target=False,
            party_local_rescue_target=False,
        )
        snapshot = {
            "active_tank_name": "Tank",
            "leader_target_id": 0,
            "rescue_target_id": 321,
            "rescue_target_name": "hamadryad",
            "rescue_target_objective_add": False,
            "rescue_requested_at": 95.0,
        }

        self.assertIsNone(
            behavior.party_rescue_actor_from_snapshot(
                args,
                snapshot,
                member_name="Dps",
                action_rotation="melee-burst",
                health_percent=82,
                now=100.0,
            )
        )
        self.assertIsNotNone(
            behavior.party_rescue_actor_from_snapshot(
                args,
                snapshot,
                member_name="Tank",
                action_rotation="melee-basic",
                health_percent=82,
                now=100.0,
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
            flee_health_percent=55,
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

    def test_dynamic_flee_safe_point_does_not_extend_without_new_damage_when_above_flee_threshold(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            flee_health_percent=55,
            low_health_rest_resume_percent=88,
            flee_safe_replan_damage_grace=6.0,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertFalse(
            behavior.should_extend_flee(
                args,
                health_percent=70,
                flee_until=100.0,
                now=101.0,
                flee_destination=destination,
            )
        )

    def test_dynamic_flee_safe_point_extends_when_health_is_still_urgent(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(344500, 477500, 2200),
            flee_health_percent=55,
            low_health_rest_resume_percent=88,
            flee_safe_replan_damage_grace=6.0,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertTrue(
            behavior.should_extend_flee(
                args,
                health_percent=20,
                flee_until=100.0,
                now=101.0,
                flee_destination=destination,
                active_threat=True,
            )
        )

    def test_dynamic_flee_safe_point_does_not_extend_urgent_health_after_aggro_clears(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(344500, 477500, 2200),
            flee_health_percent=55,
            low_health_rest_resume_percent=88,
            flee_safe_replan_damage_grace=6.0,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertFalse(
            behavior.should_extend_flee(
                args,
                health_percent=20,
                flee_until=100.0,
                now=101.0,
                flee_destination=destination,
                active_threat=False,
            )
        )

    def test_dynamic_flee_safe_point_extends_when_recent_damage_continues(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(344500, 474500, 5372),
            flee_health_percent=55,
            low_health_rest_resume_percent=88,
            flee_safe_replan_damage_grace=6.0,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertTrue(
            behavior.should_extend_flee(
                args,
                health_percent=40,
                flee_until=100.0,
                now=101.0,
                flee_destination=destination,
                recent_damage_age_seconds=3.0,
            )
        )

    def test_dynamic_flee_safe_point_extends_when_untracked_health_drops(self):
        args = SimpleNamespace(
            flee_home=behavior.Waypoint(344500, 474500, 2200),
            flee_health_percent=55,
            low_health_rest_resume_percent=88,
            flee_safe_replan_damage_grace=6.0,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertTrue(
            behavior.should_extend_flee(
                args,
                health_percent=30,
                previous_health_percent=47,
                flee_until=100.0,
                now=101.0,
                flee_destination=destination,
            )
        )

    def test_dynamic_flee_safe_point_replans_on_arrival_when_health_is_still_low(self):
        args = SimpleNamespace(
            flee_health_percent=55,
            low_health_rest_resume_percent=88,
            flee_safe_replan_damage_grace=6.0,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertFalse(behavior.should_replan_flee_safe_after_arrival(args, destination, health_percent=40))
        self.assertTrue(
            behavior.should_replan_flee_safe_after_arrival(
                args,
                destination,
                health_percent=40,
                recent_damage_age_seconds=3.0,
            )
        )
        self.assertFalse(
            behavior.should_replan_flee_safe_after_arrival(
                args,
                destination,
                health_percent=40,
                recent_damage_age_seconds=8.0,
            )
        )
        self.assertTrue(
            behavior.should_replan_flee_safe_after_arrival(
                args,
                destination,
                health_percent=40,
                previous_health_percent=50,
            )
        )
        self.assertFalse(behavior.should_replan_flee_safe_after_arrival(args, destination, health_percent=55))
        self.assertFalse(behavior.should_replan_flee_safe_after_arrival(args, destination, health_percent=56))
        self.assertTrue(
            behavior.should_replan_flee_safe_after_arrival(
                args,
                destination,
                health_percent=56,
                previous_health_percent=70,
            )
        )
        self.assertFalse(behavior.should_replan_flee_safe_after_arrival(args, destination, health_percent=90))
        self.assertFalse(
            behavior.should_replan_flee_safe_after_arrival(
                args,
                behavior.MovementDestination("flee-home:1", 344500, 474500, 5372),
                health_percent=40,
            )
        )

    def test_dynamic_flee_safe_point_replans_mid_flee_when_aggro_stays_close(self):
        args = SimpleNamespace(
            low_health_rest_resume_percent=88,
            flee_safe_threat_radius=3200.0,
            flee_critical_health_percent=65,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertTrue(
            behavior.should_replan_flee_safe_under_pressure(
                args,
                destination,
                health_percent=52,
                threat_snapshot={
                    "flee_threat_active": True,
                    "flee_threat_distance": 300.0,
                },
            )
        )

    def test_flee_home_replans_on_arrival_when_recent_damage_continues(self):
        args = SimpleNamespace(flee_safe_replan_damage_grace=6.0)
        destination = behavior.MovementDestination("flee-home:771:836:4", 771152, 836380, 4624)

        self.assertTrue(
            behavior.should_replan_flee_home_after_arrival(
                args,
                destination,
                health_percent=51,
                recent_damage_age_seconds=3.0,
            )
        )
        self.assertFalse(
            behavior.should_replan_flee_home_after_arrival(
                args,
                destination,
                health_percent=51,
                recent_damage_age_seconds=8.0,
            )
        )
        self.assertFalse(
            behavior.should_replan_flee_home_after_arrival(
                args,
                behavior.MovementDestination("flee-safe:1", 771152, 836380, 4624),
                health_percent=51,
                recent_damage_age_seconds=3.0,
            )
        )

    def test_flee_home_overrun_runs_past_town_away_from_objective(self):
        client = FakeClient(npcs=[])
        client.x = 771215
        client.y = 836278
        client.z = 4624
        args = SimpleNamespace(
            flee_safe_point_distance=5200.0,
            flee_critical_safe_point_distance=0.0,
            flee_step=900.0,
            required_target_home=behavior.Waypoint(772717, 833982, 4348),
        )
        destination = behavior.MovementDestination("flee-home:771:836:4", 771152, 836380, 4624)

        overrun = behavior.flee_home_overrun_destination(args, client, destination)

        self.assertIsNotNone(overrun)
        self.assertTrue(overrun.key.startswith("flee-safe:"))
        self.assertLess(overrun.x, destination.x)
        self.assertGreater(overrun.y, destination.y)
        before = behavior.horizontal_distance_between_points(destination.x, destination.y, args.required_target_home.x, args.required_target_home.y)
        after = behavior.horizontal_distance_between_points(overrun.x, overrun.y, args.required_target_home.x, args.required_target_home.y)
        self.assertGreater(after, before)

    def test_active_flee_threat_keeps_running_even_after_health_recovers(self):
        threat_snapshot = {
            "flee_threat_active": True,
            "flee_threat_has_aggro": True,
            "flee_threat_target": "GrowthMid701",
        }

        self.assertTrue(behavior.should_continue_flee_for_active_threat(threat_snapshot))
        self.assertTrue(behavior.should_extend_flee_after_duration(threat_snapshot))
        self.assertFalse(behavior.should_continue_flee_for_active_threat(None))
        self.assertFalse(behavior.should_extend_flee_after_duration(None))
        args = SimpleNamespace(
            low_health_rest_resume_percent=88,
            flee_safe_threat_radius=3200.0,
            flee_critical_health_percent=65,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)
        self.assertTrue(
            behavior.should_replan_flee_safe_under_pressure(
                args,
                destination,
                health_percent=30,
                threat_snapshot={
                    "flee_threat_has_aggro": True,
                    "flee_threat_distance": 2000.0,
                },
            )
        )
        self.assertFalse(
            behavior.should_replan_flee_safe_under_pressure(
                args,
                destination,
                health_percent=52,
                threat_snapshot={
                    "flee_threat_active": False,
                    "flee_threat_distance": 300.0,
                },
            )
        )
        self.assertFalse(
            behavior.should_replan_flee_safe_under_pressure(
                args,
                behavior.MovementDestination("flee-home:1", 344500, 474500, 5372),
                health_percent=52,
                threat_snapshot={
                    "flee_threat_active": True,
                    "flee_threat_distance": 300.0,
                },
            )
        )

    def test_flee_recovery_rests_until_resume_health_before_returning(self):
        args = SimpleNamespace(low_health_rest_resume_percent=88)

        self.assertTrue(behavior.should_rest_after_flee_recovery(args, health_percent=82))
        self.assertFalse(behavior.should_rest_after_flee_recovery(args, health_percent=90))
        self.assertFalse(behavior.should_rest_after_flee_recovery(args, health_percent=0))

    def test_flee_recovery_does_not_rest_above_low_health_threshold(self):
        args = SimpleNamespace(low_health_rest_percent=70, low_health_rest_resume_percent=88)

        self.assertFalse(behavior.should_rest_after_flee_recovery(args, health_percent=86))
        self.assertTrue(behavior.should_rest_after_flee_recovery(args, health_percent=62))

    def test_required_target_recovery_threshold_rests_before_returning_home(self):
        args = SimpleNamespace(
            low_health_rest_percent=70,
            low_health_rest_resume_percent=88,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_recover_before_home_health_percent=88,
        )

        self.assertTrue(behavior.should_rest_after_flee_recovery(args, health_percent=86))
        self.assertFalse(behavior.should_rest_after_flee_recovery(args, health_percent=90))

    def test_recovery_rest_timer_extends_until_resume_health(self):
        args = SimpleNamespace(low_health_rest_resume_percent=88, low_health_rest_min=6.0)

        self.assertTrue(behavior.should_extend_recovery_rest(args, health_percent=82))
        self.assertFalse(behavior.should_extend_recovery_rest(args, health_percent=90))

    def test_recovery_rest_timer_stops_when_above_low_health_threshold(self):
        args = SimpleNamespace(low_health_rest_percent=70, low_health_rest_resume_percent=88, low_health_rest_min=6.0)

        self.assertFalse(behavior.should_extend_recovery_rest(args, health_percent=86))
        self.assertTrue(behavior.should_extend_recovery_rest(args, health_percent=62))

    def test_required_target_recovery_threshold_extends_rest_before_home(self):
        args = SimpleNamespace(
            low_health_rest_percent=70,
            low_health_rest_resume_percent=88,
            low_health_rest_min=6.0,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_recover_before_home_health_percent=88,
        )

        self.assertTrue(behavior.should_extend_recovery_rest(args, health_percent=86))
        self.assertFalse(behavior.should_extend_recovery_rest(args, health_percent=90))


    def test_dynamic_flee_safe_point_replans_immediately_on_new_flee_damage(self):
        args = SimpleNamespace(
            low_health_rest_resume_percent=88,
            flee_safe_replan_damage_grace=6.0,
        )
        destination = behavior.MovementDestination("flee-safe:3365:5189:48", 336535, 518970, 4882)

        self.assertTrue(
            behavior.should_replan_flee_safe_after_recent_damage(
                args,
                destination,
                health_percent=70,
                recent_damage_age_seconds=1.0,
                damage_seen_at=123.0,
                last_replanned_damage_at=100.0,
            )
        )
        self.assertFalse(
            behavior.should_replan_flee_safe_after_recent_damage(
                args,
                destination,
                health_percent=70,
                recent_damage_age_seconds=1.0,
                damage_seen_at=123.0,
                last_replanned_damage_at=123.0,
            )
        )
        self.assertFalse(
            behavior.should_replan_flee_safe_after_recent_damage(
                args,
                destination,
                health_percent=70,
                recent_damage_age_seconds=8.0,
                damage_seen_at=123.0,
                last_replanned_damage_at=100.0,
            )
        )
        self.assertFalse(
            behavior.should_replan_flee_safe_after_recent_damage(
                args,
                behavior.MovementDestination("flee-home:1", 344500, 474500, 5372),
                health_percent=70,
                recent_damage_age_seconds=1.0,
                damage_seen_at=123.0,
                last_replanned_damage_at=100.0,
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

    def test_party_assist_member_follows_leader_before_ready_pull(self):
        args = SimpleNamespace(
            party_assist_only=True,
            party_min_ready=2,
            party_size=2,
            required_target_home=behavior.Waypoint(391326, 755351, 388),
        )

        self.assertFalse(behavior.should_approach_required_target_home(args, is_party_leader=False, current_target=0))
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

    def test_choose_hunter_target_rejects_ground_z_mismatched_visible_npc(self):
        args = SimpleNamespace(
            max_target_level=8,
            player_level=10,
            max_target_level_delta=0,
            ideal_target_level=8,
            prefer_target_name="water beetle",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=7,
            max_target_distance=2200.0,
            target_auto_lowest_visible_level=False,
            allow_avoid_target_fallback=False,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=None,
            target_home_max_distance=0.0,
            hunter_target_max_ground_z_delta=220.0,
        )
        bad = FakeNpc(1, "water beetle", 7, 100.0)
        bad.x = 292898
        bad.y = 647251
        bad.z = 4598
        good = FakeNpc(2, "water beetle", 7, 300.0)
        good.x = 292028
        good.y = 650121
        good.z = 4625
        client = FakeClient(npcs=[bad, good])
        client.zone_id = 200
        client.ground_z_sampler = lambda x, y, zone: 4320 if x == bad.x and y == bad.y else 4607

        selected = behavior.choose_hunter_target(client, random.Random(1), args, {}, {}, now=100.0)

        self.assertEqual(selected.object_id, good.object_id)

    def test_hunter_target_scan_snapshot_reports_ground_z_rejections(self):
        args = SimpleNamespace(
            max_target_level=8,
            player_level=10,
            max_target_level_delta=0,
            prefer_target_name="water beetle",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=7,
            max_target_distance=2200.0,
            target_home_max_distance=0.0,
            required_target_home=None,
            include_peace_npcs=True,
            hunter_target_max_ground_z_delta=220.0,
        )
        bad = FakeNpc(1, "water beetle", 7, 100.0)
        bad.x = 292898
        bad.y = 647251
        bad.z = 4598
        client = FakeClient(npcs=[bad])
        client.zone_id = 200
        client.ground_z_sampler = lambda x, y, zone: 4320

        snapshot = behavior.hunter_target_scan_snapshot(client, args, {}, {}, now=100.0)

        self.assertEqual(snapshot["hunter_eligible_npcs"], 0)
        self.assertEqual(snapshot["hunter_reject_counts"]["ground_z"], 1)
        self.assertEqual(snapshot["hunter_nearest_rejected"][0]["reason"], "ground_z")

    def test_choose_hunter_target_does_not_prefer_below_minimum_target(self):
        args = SimpleNamespace(
            max_target_level=5,
            player_level=6,
            max_target_level_delta=0,
            ideal_target_level=5,
            prefer_target_name="huldu hunter,phantom hound",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=5,
            max_target_distance=6000.0,
            target_auto_lowest_visible_level=True,
            allow_avoid_target_fallback=False,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=None,
            target_home_max_distance=0.0,
        )
        exact_unpreferred = FakeNpc(1, "huldu stalker", 5, 100.0)
        lower_preferred = FakeNpc(2, "huldu hunter", 4, 400.0)

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=[exact_unpreferred, lower_preferred]),
            random.Random(1),
            args,
            {},
            {},
            now=100.0,
        )

        self.assertEqual(selected.object_id, exact_unpreferred.object_id)

    def test_choose_hunter_target_auto_lowest_does_not_exceed_configured_max_level(self):
        args = SimpleNamespace(
            max_target_level=4,
            player_level=5,
            max_target_level_delta=0,
            ideal_target_level=4,
            prefer_target_name="eirebug",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=4,
            max_target_distance=6000.0,
            target_auto_lowest_visible_level=True,
            allow_avoid_target_fallback=False,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=None,
            target_home_max_distance=0.0,
        )
        over_cap_preferred = FakeNpc(1, "eirebug", 5, 100.0)

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=[over_cap_preferred]),
            random.Random(1),
            args,
            {},
            {},
            now=100.0,
        )

        self.assertIsNone(selected)

    def test_choose_hunter_target_auto_lowest_can_use_unpreferred_fallback(self):
        args = SimpleNamespace(
            max_target_level=8,
            player_level=10,
            max_target_level_delta=0,
            ideal_target_level=8,
            prefer_target_name="wild boar",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=7,
            max_target_distance=6000.0,
            target_auto_lowest_visible_level=True,
            allow_avoid_target_fallback=False,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=None,
            target_home_max_distance=0.0,
        )
        too_high_preferred = FakeNpc(1, "wild boar", 10, 100.0)
        weak_unpreferred = FakeNpc(2, "weak skeleton", 7, 400.0)

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=[too_high_preferred, weak_unpreferred]),
            random.Random(1),
            args,
            {},
            {},
            now=100.0,
        )

        self.assertEqual(selected.object_id, weak_unpreferred.object_id)

    def test_choose_hunter_target_auto_lowest_prefers_lowest_preferred_target(self):
        args = SimpleNamespace(
            max_target_level=4,
            player_level=4,
            max_target_level_delta=0,
            ideal_target_level=4,
            prefer_target_name="mudman,villainous youth",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=2,
            max_target_distance=6000.0,
            target_auto_lowest_visible_level=True,
            allow_avoid_target_fallback=False,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=None,
            target_home_max_distance=0.0,
        )
        safer_preferred = FakeNpc(1, "mudman", 3, 500.0)
        ideal_preferred = FakeNpc(2, "villainous youth", 4, 100.0)

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=[ideal_preferred, safer_preferred]),
            random.Random(1),
            args,
            {},
            {},
            now=100.0,
        )

        self.assertEqual(selected.object_id, safer_preferred.object_id)

    def test_choose_hunter_target_auto_lowest_fallback_respects_min_level(self):
        args = SimpleNamespace(
            max_target_level=8,
            player_level=10,
            max_target_level_delta=0,
            ideal_target_level=8,
            prefer_target_name="wild boar",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=7,
            max_target_distance=6000.0,
            target_auto_lowest_visible_level=True,
            allow_avoid_target_fallback=False,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=None,
            target_home_max_distance=0.0,
        )
        too_high_preferred = FakeNpc(1, "wild boar", 10, 100.0)
        gray_unpreferred = FakeNpc(2, "weak skeleton", 1, 400.0)

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=[too_high_preferred, gray_unpreferred]),
            random.Random(1),
            args,
            {},
            {},
            now=100.0,
        )

        self.assertIsNone(selected)

    def test_choose_hunter_target_can_use_preferred_low_con_fallback_when_enabled(self):
        args = SimpleNamespace(
            max_target_level=8,
            player_level=10,
            max_target_level_delta=0,
            ideal_target_level=8,
            prefer_target_name="mudman",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=7,
            max_target_distance=2200.0,
            target_auto_lowest_visible_level=True,
            allow_preferred_low_con_fallback=True,
            preferred_low_con_min_level=0,
            allow_avoid_target_fallback=False,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=None,
            target_home_max_distance=0.0,
        )
        reported_low_preferred = FakeNpc(1, "mudman", 4, 200.0)

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=[reported_low_preferred]),
            random.Random(1),
            args,
            {},
            {},
            now=100.0,
        )

        self.assertEqual(selected.object_id, reported_low_preferred.object_id)
        self.assertTrue(behavior.preferred_low_con_fallback_allowed(args, FakeClient(), reported_low_preferred))

    def test_preferred_low_con_fallback_does_not_use_unpreferred_gray(self):
        args = SimpleNamespace(
            max_target_level=8,
            player_level=10,
            max_target_level_delta=0,
            ideal_target_level=8,
            prefer_target_name="mudman",
            require_target_name="",
            avoid_target_name="",
            npc_max_age=30.0,
            min_target_level=7,
            max_target_distance=2200.0,
            target_auto_lowest_visible_level=True,
            allow_preferred_low_con_fallback=True,
            preferred_low_con_min_level=0,
            allow_avoid_target_fallback=False,
            target_pool=5,
            target_selection="smart",
            target_level_weight=80.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
            required_target_home=None,
            target_home_max_distance=0.0,
        )
        unpreferred = FakeNpc(1, "large frog", 1, 200.0)

        selected = behavior.choose_hunter_target(
            FakeClient(npcs=[unpreferred]),
            random.Random(1),
            args,
            {},
            {},
            now=100.0,
        )

        self.assertIsNone(selected)

    def test_hunter_target_api_scout_does_not_exceed_configured_max_level(self):
        args = SimpleNamespace(
            hunter_target_api_scout=True,
            path_region=200,
            hunter_target_api_timeout=1.0,
            hunter_target_api_url="",
            host="127.0.0.1",
            api_port=5000,
            hunter_target_api_radius=2200,
            hunter_target_api_limit=5,
            hunter_target_api_engage_distance=1500.0,
            min_target_level=4,
            max_target_level=4,
            player_level=5,
            max_target_level_delta=0,
            prefer_target_name="eirebug,large frog",
            require_target_name="",
            avoid_target_name="",
            target_home_max_distance=0.0,
            required_target_home=None,
            max_target_distance=2200.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
        )
        payload = (
            b'{"items":['
            b'{"objectId":1,"name":"eirebug","level":5,"x":100,"y":0,"z":0},'
            b'{"objectId":2,"name":"large frog","level":4,"x":300,"y":0,"z":0}'
            b"]}"
        )

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return payload

        with patch.object(behavior.urllib.request, "urlopen", return_value=FakeResponse()):
            selected = behavior.fetch_hunter_target_api_observation(
                args,
                FakeClient(),
                random.Random(1),
                {},
                {},
                now=100.0,
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.object_id, 2)
        self.assertEqual(selected.level, 4)

    def test_hunter_target_api_scout_rejects_ground_z_mismatched_candidate(self):
        args = SimpleNamespace(
            hunter_target_api_scout=True,
            path_region=200,
            hunter_target_api_timeout=1.0,
            hunter_target_api_url="",
            host="127.0.0.1",
            api_port=5000,
            hunter_target_api_radius=2200,
            hunter_target_api_limit=5,
            hunter_target_api_engage_distance=4000.0,
            hunter_target_max_ground_z_delta=220.0,
            min_target_level=7,
            max_target_level=8,
            player_level=10,
            max_target_level_delta=0,
            prefer_target_name="water beetle",
            require_target_name="",
            avoid_target_name="",
            target_home_max_distance=0.0,
            required_target_home=None,
            max_target_distance=2200.0,
            target_distance_weight=1000.0,
            prefer_target_bonus=400.0,
            target_randomness=0.0,
        )
        payload = (
            b'{"items":['
            b'{"objectId":1,"name":"water beetle","level":7,"x":292898,"y":647251,"z":4598},'
            b'{"objectId":2,"name":"water beetle","level":7,"x":292028,"y":650121,"z":4625}'
            b"]}"
        )
        client = SimpleNamespace(x=0, y=0, horizontal_distance_to=lambda actor: 100.0)
        client.zone_id = 200
        client.x = 292800
        client.y = 647200
        client.ground_z_sampler = lambda x, y, zone: 4320 if x == 292898 and y == 647251 else 4607

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return payload

        with patch.object(behavior.urllib.request, "urlopen", return_value=FakeResponse()):
            selected = behavior.fetch_hunter_target_api_observation(
                args,
                client,
                random.Random(1),
                {},
                {},
                now=100.0,
            )

        self.assertIsNotNone(selected)
        self.assertEqual(selected.object_id, 2)

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

    def test_actor_from_active_combat_keeps_last_known_position(self):
        active_combat = {
            "target_id": 42,
            "target_name": "current piglet",
            "target_level": 1,
            "target_x": 123,
            "target_y": 456,
            "target_z": 789,
        }

        actor = behavior.actor_from_active_combat(active_combat)

        self.assertEqual(actor.object_id, 42)
        self.assertEqual(actor.name, "current piglet")
        self.assertEqual(actor.x, 123)
        self.assertEqual(actor.y, 456)
        self.assertEqual(actor.z, 789)

    def test_live_control_cannot_lower_target_level_below_segment_baseline(self):
        args = SimpleNamespace(
            min_target_level=7,
            max_target_level_delta=0,
            player_level=10,
        )

        updates = behavior.apply_live_control_overrides(
            args,
            {
                "min_target_level": 1,
                "max_target_level_delta": 5,
                "baseline_min_target_level": 7,
                "baseline_max_target_level": 8,
            },
        )

        self.assertEqual(args.min_target_level, 7)
        self.assertEqual(args.max_target_level_delta, -2)
        self.assertNotIn("min_target_level", updates)
        self.assertIn("max_target_level_delta", updates)

    def test_classify_combat_server_message_marks_korean_too_far(self):
        categories = behavior.classify_combat_server_message("boar piglet은(는) 너무 멀어 공격할 수 없습니다!")

        self.assertIn("out_of_range", categories)

    def test_classify_combat_server_message_marks_korean_not_visible(self):
        categories = behavior.classify_combat_server_message("boar piglet이(가) 시야에 없습니다!")

        self.assertIn("not_visible", categories)

    def test_classify_combat_server_message_marks_cast_interrupt_and_not_ready(self):
        interrupted = behavior.classify_combat_server_message("small gray wolf이(가) 당신을 공격해 주문이 중단되었습니다!")
        not_ready = behavior.classify_combat_server_message("주문을 시전하려면 0초 기다려야 합니다!")

        self.assertIn("cast_interrupted", interrupted)
        self.assertIn("spell_not_ready", not_ready)

    def test_classify_combat_server_message_marks_friendly_target_feedback(self):
        categories = behavior.classify_combat_server_message("같은 렐름 구성원은 공격할 수 없습니다!")

        self.assertIn("friendly_target", categories)
        self.assertTrue(behavior.should_reject_current_target_for_friendly_feedback(categories))

    def test_active_target_combat_contact_accepts_chat_type_thirty_for_target_name(self):
        active_combat = {"target_name": "water beetle"}

        self.assertTrue(
            behavior.is_active_target_combat_contact_message(
                active_combat,
                "water beetle??怨듦꺽???쏅굹媛붿뒿?덈떎!",
                30,
            )
        )

    def test_active_target_combat_contact_ignores_unrelated_target(self):
        active_combat = {"target_name": "water beetle"}

        self.assertFalse(
            behavior.is_active_target_combat_contact_message(
                active_combat,
                "hill toad??怨듦꺽???쏅굹媛붿뒿?덈떎!",
                30,
            )
        )

    def test_server_los_failure_grace_has_fast_retarget_default(self):
        args = behavior.build_parser().parse_args([])

        self.assertEqual(args.server_los_failure_grace, 8.0)

    def test_server_los_failure_kind_cooldown_defaults_to_object_only(self):
        args = behavior.build_parser().parse_args([])

        self.assertEqual(args.server_los_failure_kind_cooldown, 0.0)

    def test_close_server_los_failure_repositions_sideways(self):
        client = PathClient()
        client.x = 50
        target = SimpleNamespace(object_id=2, x=0, y=0, z=0)
        args = SimpleNamespace(
            attack_range=350.0,
            minimum_melee_stop_distance=60.0,
            movement_speed=240.0,
            movement_update_interval=0.0,
        )
        action_counts: dict[str, int] = {}

        moved = behavior.reposition_after_close_server_los_failure(
            client,
            args,
            target,
            action_counts,
        )

        self.assertTrue(moved)
        self.assertEqual(client.moves[-1][:3], (50, 140, 0))
        self.assertEqual(client.movement_speeds[-1], 240.0)
        self.assertEqual(action_counts["server_los_failure_reposition_move"], 1)
        self.assertTrue(client.headings)

    def test_server_los_retry_keeps_closing_until_retry_stop_distance(self):
        args = SimpleNamespace(
            minimum_melee_stop_distance=60.0,
            attack_range=350.0,
            melee_range_buffer=50.0,
            ranged_stop_distance=1100.0,
            spell_range=1500.0,
        )

        self.assertEqual(behavior.server_los_retry_stop_distance(args, "melee-basic"), 30.0)
        self.assertTrue(behavior.should_close_for_server_los_retry(args, "melee-basic", 51.0))
        self.assertFalse(behavior.should_close_for_server_los_retry(args, "melee-basic", 31.0))

    def test_repeated_server_los_failure_stops_retrying_even_after_damage_done(self):
        active_combat = {
            "target_id": 42,
            "target_name": "bandit",
            "target_level": 7,
            "damage_done": 7,
            "last_combat_message_at": 0.0,
            "server_los_failures": 8,
        }

        self.assertFalse(
            behavior.should_retry_server_los_failure(
                active_combat,
                now=120.0,
                target_age=15.0,
                los_failure_grace=8.0,
                max_retries_after_hit=8,
            )
        )

    def test_recent_server_los_failure_still_retries_during_grace(self):
        active_combat = {
            "target_id": 42,
            "target_name": "bandit",
            "target_level": 7,
            "damage_done": 0,
            "last_combat_message_at": 0.0,
            "server_los_failures": 20,
        }

        self.assertTrue(
            behavior.should_retry_server_los_failure(
                active_combat,
                now=102.0,
                target_age=2.0,
                los_failure_grace=8.0,
                max_retries_after_hit=8,
            )
        )

    def test_target_loss_after_repeated_los_and_damage_is_los_failure(self):
        active_combat = {
            "target_id": 42,
            "target_name": "bandit",
            "target_level": 7,
            "damage_taken": 64,
            "server_los_failures": 5,
        }

        self.assertTrue(
            behavior.should_treat_target_loss_as_server_los_failure(
                active_combat,
                max_retries_after_hit=8,
            )
        )

    def test_drop_aggro_recovery_duration_covers_clear_grace(self):
        args = SimpleNamespace(
            flee_duration=8.0,
            low_health_rest_min=6.0,
            travel_aggro_clear_grace=24.0,
        )

        self.assertEqual(behavior.drop_aggro_recovery_duration(args), 24.0)

    def test_drop_aggro_recovery_duration_does_not_use_rest_min_when_healthy(self):
        args = SimpleNamespace(
            flee_duration=4.0,
            low_health_rest_min=20.0,
            travel_aggro_clear_grace=3.0,
            low_health_rest_resume_percent=80,
            low_health_rest_percent=35,
        )

        self.assertEqual(behavior.drop_aggro_recovery_duration(args, health_percent=91), 4.0)

    def test_drop_aggro_recovery_duration_uses_rest_min_when_health_is_low(self):
        args = SimpleNamespace(
            flee_duration=4.0,
            low_health_rest_min=20.0,
            travel_aggro_clear_grace=3.0,
            low_health_rest_resume_percent=80,
            low_health_rest_percent=35,
        )

        self.assertEqual(behavior.drop_aggro_recovery_duration(args, health_percent=25), 20.0)

    def test_drop_aggro_clear_hold_duration_uses_only_remaining_grace_when_healthy(self):
        args = SimpleNamespace(
            low_health_rest_min=20.0,
            low_health_rest_resume_percent=80,
            low_health_rest_percent=35,
        )

        self.assertEqual(
            behavior.drop_aggro_clear_hold_duration(args, clear_remaining=1.25, health_percent=91),
            1.25,
        )

    def test_server_los_retry_prefers_live_visible_target_over_stale_snapshot(self):
        live = FakeNpc(42, "bandit", 7, 90.0)
        live.x = 100
        live.y = 200
        live.z = 30
        client = FakeClient(npcs=[live])
        active_combat = {
            "target_id": 42,
            "target_name": "bandit",
            "target_level": 7,
            "target_x": 900,
            "target_y": 900,
            "target_z": 30,
        }

        retry_target, source = behavior.server_los_retry_target(
            client,
            SimpleNamespace(npc_max_age=60.0),
            current_target=42,
            active_combat=active_combat,
            observed_target=None,
        )

        self.assertEqual(source, "visible_npc")
        self.assertEqual(retry_target.x, 100)
        self.assertEqual(retry_target.y, 200)

    def test_api_region_prefers_path_region_over_client_zone(self):
        args = SimpleNamespace(path_region=1, required_target_api_region=-1)
        client = SimpleNamespace(zone_id=8)

        self.assertEqual(behavior.api_region_for_client(args, client), 1)

    def test_range_only_server_message_does_not_count_as_los_failure(self):
        self.assertFalse(behavior.should_count_server_los_failure({"out_of_range"}))
        self.assertTrue(behavior.should_count_server_los_failure({"not_visible"}))
        self.assertTrue(behavior.should_count_server_los_failure({"out_of_range", "not_visible"}))
        self.assertFalse(
            behavior.should_count_server_los_failure(
                {"not_visible"},
                target_distance=260.0,
                close_distance=140.0,
            )
        )
        self.assertTrue(
            behavior.should_count_server_los_failure(
                {"not_visible"},
                target_distance=90.0,
                close_distance=140.0,
            )
        )

    def test_follow_player_hold_allows_waypoint_defaults_off(self):
        args = behavior.build_parser().parse_args([])

        self.assertFalse(args.follow_player_hold_allows_waypoint)

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

    def test_recent_incoming_melee_proof_allows_healer_close_counterattack(self):
        args = SimpleNamespace(
            attack_range=350.0,
            melee_range_buffer=250.0,
            minimum_melee_stop_distance=70.0,
            incoming_damage_melee_grace=4.0,
            incoming_damage_melee_max_distance=650.0,
        )
        actor = SimpleNamespace(name="small gray wolf")

        effective_distance = behavior.effective_attack_distance_for_recent_incoming_damage(
            args,
            "healer-support",
            actor,
            distance=505.0,
            recent_incoming_attacker_name="small gray wolf",
            last_incoming_damage_at=8.0,
            now=10.0,
        )

        self.assertLessEqual(effective_distance, args.attack_range)
        self.assertTrue(behavior.should_enable_attack_mode(args, "healer-support", effective_distance))

    def test_melee_stick_attack_counts_approach_as_attack_attempt(self):
        args = SimpleNamespace(
            attack_range=350.0,
            melee_range_buffer=250.0,
            minimum_melee_stop_distance=70.0,
            melee_stick_attack=True,
            melee_stick_attack_distance=1800.0,
        )

        self.assertTrue(behavior.should_enable_attack_mode(args, "melee-basic", 1500.0))
        self.assertTrue(
            behavior.should_count_attack_attempt(
                args,
                "melee-basic",
                attack_enabled=True,
                action_distance=1500.0,
            )
        )
        self.assertFalse(behavior.should_enable_attack_mode(args, "melee-basic", 1900.0))

    def test_melee_stick_attack_does_not_mark_leader_engaged_outside_real_attack_range(self):
        args = SimpleNamespace(
            attack_range=350.0,
            melee_stick_attack=True,
            melee_stick_attack_distance=1800.0,
        )

        self.assertTrue(behavior.should_enable_attack_mode(args, "melee-basic", 1500.0))
        self.assertFalse(
            behavior.should_mark_leader_target_engaged(
                args,
                "melee-basic",
                attack_enabled=True,
                action_distance=1500.0,
            )
        )
        self.assertTrue(
            behavior.should_mark_leader_target_engaged(
                args,
                "melee-basic",
                attack_enabled=True,
                action_distance=300.0,
            )
        )

    def test_party_pull_flag_marks_melee_leader_engaged_while_closing(self):
        args = SimpleNamespace(
            attack_range=350.0,
            melee_stick_attack=True,
            melee_stick_attack_distance=1800.0,
            party_mark_pull_engaged=True,
            party_pull_engage_distance=1800.0,
        )

        self.assertTrue(behavior.should_enable_attack_mode(args, "melee-basic", 1500.0))
        self.assertTrue(
            behavior.should_mark_leader_target_engaged(
                args,
                "melee-basic",
                attack_enabled=True,
                action_distance=1500.0,
            )
        )
        self.assertFalse(
            behavior.should_mark_leader_target_engaged(
                args,
                "melee-basic",
                attack_enabled=True,
                action_distance=1900.0,
            )
        )

    def test_melee_combat_chase_uses_sprint_speed_only_while_closing(self):
        args = SimpleNamespace(attack_range=350.0, movement_speed=240.0, smooth_move_interval=0.2)

        self.assertEqual(behavior.combat_chase_movement_speed(args, "melee-basic", 900.0), 600.0)
        self.assertEqual(behavior.combat_chase_step(args, "melee-basic", 900.0, 48.0), 120.0)
        self.assertEqual(behavior.combat_chase_movement_speed(args, "melee-basic", 200.0), 240.0)

    def test_recent_incoming_damage_from_target_counts_as_melee_contact(self):
        args = SimpleNamespace(
            attack_range=120.0,
            melee_range_buffer=25.0,
            minimum_melee_stop_distance=70.0,
        )
        npc = FakeNpc(10, "orchard nipper", 6, 250.0)

        self.assertTrue(
            behavior.recent_incoming_damage_matches_actor(
                npc,
                "orchard nipper",
                last_damage_at=98.0,
                now=100.0,
                grace_seconds=4.0,
            )
        )
        self.assertEqual(
            behavior.effective_attack_distance_for_recent_incoming_damage(
                args,
                "melee-basic",
                npc,
                distance=250.0,
                recent_incoming_attacker_name="orchard nipper",
                last_incoming_damage_at=98.0,
                now=100.0,
            ),
            behavior.melee_stop_distance(args),
        )

    def test_recent_incoming_damage_does_not_shorten_stale_far_target_distance(self):
        args = SimpleNamespace(
            attack_range=120.0,
            melee_range_buffer=25.0,
            minimum_melee_stop_distance=70.0,
        )
        npc = FakeNpc(10, "orchard nipper", 6, 950.0)

        self.assertEqual(
            behavior.effective_attack_distance_for_recent_incoming_damage(
                args,
                "melee-basic",
                npc,
                distance=950.0,
                recent_incoming_attacker_name="orchard nipper",
                last_incoming_damage_at=98.0,
                now=100.0,
            ),
            950.0,
        )

    def test_recent_incoming_damage_does_not_shorten_unrelated_target_distance(self):
        args = SimpleNamespace(
            attack_range=120.0,
            melee_range_buffer=25.0,
            minimum_melee_stop_distance=70.0,
        )
        npc = FakeNpc(10, "orchard nipper", 6, 950.0)

        self.assertEqual(
            behavior.effective_attack_distance_for_recent_incoming_damage(
                args,
                "melee-basic",
                npc,
                distance=950.0,
                recent_incoming_attacker_name="water beetle",
                last_incoming_damage_at=98.0,
                now=100.0,
            ),
            950.0,
        )

    def test_target_timeout_preserves_recent_same_attacker_damage(self):
        args = SimpleNamespace(incoming_damage_melee_grace=4.0, target_timeout_active_combat_grace=8.0)
        active_combat = {
            "target_id": 10,
            "target_name": "bandit",
            "target_level": 7,
            "last_combat_message_at": 0.0,
            "last_damage_done_at": 0.0,
        }

        self.assertTrue(
            behavior.should_preserve_target_timeout_for_combat_progress(
                args,
                active_combat,
                behavior.actor_from_active_combat(active_combat),
                recent_incoming_attacker_name="bandit",
                last_incoming_damage_at=98.0,
                now=100.0,
            )
        )

    def test_target_timeout_preserves_recent_damage_done_progress(self):
        args = SimpleNamespace(incoming_damage_melee_grace=4.0, target_timeout_active_combat_grace=8.0)
        active_combat = {
            "target_id": 10,
            "target_name": "bandit",
            "target_level": 7,
            "last_combat_message_at": 0.0,
            "last_damage_done_at": 96.5,
        }

        self.assertTrue(
            behavior.should_preserve_target_timeout_for_combat_progress(
                args,
                active_combat,
                behavior.actor_from_active_combat(active_combat),
                recent_incoming_attacker_name="",
                last_incoming_damage_at=0.0,
                now=100.0,
            )
        )

    def test_target_timeout_does_not_preserve_stale_or_unrelated_combat(self):
        args = SimpleNamespace(incoming_damage_melee_grace=4.0, target_timeout_active_combat_grace=8.0)
        active_combat = {
            "target_id": 10,
            "target_name": "bandit",
            "target_level": 7,
            "last_combat_message_at": 80.0,
            "last_damage_done_at": 80.0,
        }

        self.assertFalse(
            behavior.should_preserve_target_timeout_for_combat_progress(
                args,
                active_combat,
                behavior.actor_from_active_combat(active_combat),
                recent_incoming_attacker_name="water beetle",
                last_incoming_damage_at=99.0,
                now=100.0,
            )
        )

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

    def test_startup_teleporter_home_uses_direct_town_move_before_graph_route(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "detour", "x": 0, "y": 1000, "z": 0},
                            {"id": "goal", "x": 1000, "y": -1000, "z": 0},
                        ],
                        "edges": [
                            {"from": "start", "to": "detour"},
                            {"from": "detour", "to": "goal"},
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
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        client = PathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("startup-teleporter-home:1", 1000, -1000, 0),
            step=250.0,
            stop_distance=80.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (1000, -1000, 0))
        self.assertEqual(action_counts["startup_teleporter_home_direct_move"], 1)
        self.assertNotIn("path_plan", action_counts)

    def test_move_towards_flee_destination_uses_flee_speed_and_counts_move(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "road", "x": 1000, "y": 0, "z": 0},
                        ],
                        "edges": [
                            {"from": "start", "to": "road"},
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
            path_node_arrival_distance=80.0,
            path_max_edge_length=1500.0,
            flee_step=900.0,
            flee_movement_speed=520.0,
            flee_safe_point_distance=5200.0,
            flee_home_stop_distance=900.0,
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0))
        client = PathClient()
        action_counts: dict[str, int] = {}

        outcome, actions = behavior.move_towards_flee_destination(
            client,
            args,
            state,
            action_counts,
            behavior.MovementDestination("flee-safe:1", 1000, -1000, 0),
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(actions, 2)
        self.assertEqual(client.moves[-1], (1000, -1000, 0, 900.0, 80.0))
        self.assertEqual(client.movement_speeds[-1], 520.0)
        self.assertEqual(action_counts["flee_safe_direct_move"], 1)
        self.assertEqual(action_counts["flee_home_move"], 1)

    def test_critical_flee_safe_destination_uses_direct_emergency_move_before_graph_route(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "danger-road", "x": 2000, "y": 0, "z": 0},
                            {"id": "goal", "x": 4200, "y": -100, "z": 0},
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
            path_max_node_distance=2500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=2500.0,
            flee_safe_point_distance=2200.0,
            flee_critical_safe_point_distance=4200.0,
        )
        state = behavior.PathMovementState(graph, 1, behavior.PathSafety(max_direct_distance=150.0, max_edge_length=2500.0))
        client = PathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("flee-safe:1", 4200, -100, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
            movement_speed=240.0,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (4200, -100, 0))
        self.assertEqual(client.movement_speeds[-1], 240.0)
        self.assertEqual(action_counts["flee_safe_direct_move"], 1)
        self.assertNotIn("path_plan", action_counts)

    def test_required_home_rejoins_graph_after_flee_safe_ends_off_graph(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "road", "x": 0, "y": 2600, "z": 0},
                            {"id": "mid", "x": 0, "y": 1300, "z": 0},
                            {"id": "camp", "x": 0, "y": 0, "z": 0},
                        ],
                        "edges": [
                            {"from": "road", "to": "mid"},
                            {"from": "mid", "to": "camp"},
                        ],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=60.0,
            path_max_node_distance=400.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            flee_safe_point_distance=2200.0,
            flee_critical_safe_point_distance=4200.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=900.0),
        )
        client = StepPathClient()
        client.x = 0
        client.y = 5200
        client.z = 0
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("required-target-home:0:0:0", 0, 0, 0),
            step=500.0,
            stop_distance=900.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertFalse(outcome.arrived)
        self.assertEqual(client.moves[-1][:3], (0, 2600, 0))
        self.assertEqual(action_counts["path_rejoin_graph"], 1)
        self.assertNotIn("path_failed", action_counts)

    def test_required_home_rejoin_graph_prefers_progress_toward_goal(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "behind", "x": -1000, "y": 0, "z": 0},
                            {"id": "ahead", "x": 3000, "y": 0, "z": 0},
                            {"id": "camp", "x": 10000, "y": 0, "z": 0},
                        ],
                        "edges": [],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=60.0,
            path_max_node_distance=100.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            flee_safe_point_distance=2200.0,
            flee_critical_safe_point_distance=4200.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=900.0),
        )
        client = StepPathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("required-target-home:10000:0:0", 10000, 0, 0),
            step=500.0,
            stop_distance=900.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (3000, 0, 0))
        self.assertEqual(action_counts["path_rejoin_graph"], 1)
        self.assertNotIn("path_offgraph_return_move", action_counts)

    def test_required_home_rejoins_first_graph_step_when_route_start_is_beyond_edge_limit(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "road", "x": 0, "y": 2600, "z": 0},
                            {"id": "mid", "x": 0, "y": 1300, "z": 0},
                            {"id": "camp", "x": 0, "y": 0, "z": 0},
                        ],
                        "edges": [
                            {"from": "road", "to": "mid"},
                            {"from": "mid", "to": "camp"},
                        ],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=60.0,
            path_max_node_distance=2500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            flee_safe_point_distance=2200.0,
            flee_critical_safe_point_distance=4200.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=900.0),
        )
        client = StepPathClient()
        client.x = 0
        client.y = 4700
        client.z = 0
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("required-target-home:0:0:0", 0, 0, 0),
            step=500.0,
            stop_distance=900.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (0, 2600, 0))
        self.assertEqual(action_counts["path_plan"], 1)
        self.assertEqual(action_counts["path_rejoin_graph"], 1)
        self.assertNotIn("path_blocked", action_counts)

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

    def test_path_movement_advances_xy_reached_waypoint_with_bad_z(self):
        class HorizontalOnlyClient(PathClient):
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
                if self.x == x and self.y == y:
                    return False
                self.x = x
                self.y = y
                self.z = z
                return True

        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=0.0,
            path_replan_interval=60.0,
            path_max_node_distance=700.0,
            path_node_arrival_distance=80.0,
            path_max_edge_length=1500.0,
        )
        state = behavior.PathMovementState(
            behavior.PathGraph(),
            1,
            behavior.PathSafety(max_direct_distance=0.0, max_edge_length=1500.0, max_height_delta=2000.0),
        )
        state.destination_key = "flee-home:1"
        state.resolved_goal = behavior.PathPoint(300, 0, 0)
        state.follower.set_route([behavior.PathPoint(100, 0, 1200), behavior.PathPoint(300, 0, 0)])
        client = HorizontalOnlyClient()
        client.x = 100
        client.y = 0
        client.z = 0
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("flee-home:1", 300, 0, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
            movement_speed=360.0,
        )

        self.assertTrue(outcome.moved)
        self.assertFalse(outcome.arrived)
        self.assertEqual(state.follower.index, 1)
        self.assertEqual(action_counts["path_waypoint_xy_reached"], 1)

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

    def test_party_follower_marks_ready_after_following_leader_into_home_range(self):
        args = SimpleNamespace(
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=100.0,
            required_target_home_hunt_distance=300.0,
            target_home_max_distance=0.0,
        )
        client = SimpleNamespace(x=750, y=0, z=0)

        self.assertTrue(
            behavior.should_mark_party_ready_after_follow(
                client,
                args,
                is_party_follower=True,
                current_target=0,
            )
        )
        self.assertTrue(
            behavior.should_mark_party_ready_after_follow(
                client,
                args,
                is_party_follower=True,
                current_target=99,
            )
        )
        self.assertFalse(
            behavior.should_mark_party_ready_after_follow(
                client,
                args,
                is_party_follower=False,
                current_target=0,
            )
        )

    def test_party_member_can_form_up_before_required_target_is_visible(self):
        args = SimpleNamespace(
            party_size=2,
            party_assist_only=True,
            party_min_ready=2,
            party_pre_pull_home_stop_distance=1800.0,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=6200.0,
            target_home_max_distance=0.0,
        )
        client = SimpleNamespace(x=2500, y=0, z=0, visible_npcs=lambda **_kwargs: [])

        self.assertTrue(behavior.party_member_ready_for_pull(client, args))

    def test_party_follower_moves_to_pre_pull_home_ring_until_ready(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        state.update_leader(SimpleNamespace(session_id=1, player_object_id=10, health_percent=100, x=-800, y=0, z=0, heading=0))
        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=-1200, y=0, z=0))
        args = SimpleNamespace(
            party_size=2,
            party_assist_only=True,
            party_min_ready=2,
            party_ready_max_leader_distance=1500.0,
            party_pre_pull_home_stop_distance=1800.0,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=1800.0,
            target_home_max_distance=0.0,
        )
        client = SimpleNamespace(x=-1200, y=0, z=0)

        self.assertFalse(behavior.party_member_ready_for_pull(client, args))
        self.assertTrue(
            behavior.should_move_to_required_target_home(
                client,
                args,
                is_party_leader=False,
                current_target=0,
            )
        )
        self.assertEqual(
            behavior.required_target_home_move_stop_distance(
                args,
                state,
                is_party_leader=False,
                current_target=0,
            ),
            1800.0,
        )

        client.x = -800
        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=-800, y=0, z=0))
        state.mark_ready("member")

        self.assertTrue(behavior.party_member_ready_for_pull(client, args))
        self.assertTrue(behavior.party_ready_for_pull(args, state))

    def test_party_follower_required_home_starts_in_travel_state_until_leader_engages(self):
        args = SimpleNamespace(
            party_size=4,
            party_assist_only=True,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=100.0,
            required_target_home_hunt_distance=300.0,
            target_home_max_distance=0.0,
        )
        client = SimpleNamespace(x=1000, y=0, z=0)

        self.assertEqual(
            behavior.initial_behavior_state_for_objective(
                client,
                args,
                is_party_leader=False,
                current_target=0,
            ),
            behavior.DummyBehaviorState.TravelToObjective,
        )
        self.assertEqual(
            behavior.initial_behavior_state_for_objective(
                client,
                args,
                is_party_leader=True,
                current_target=0,
            ),
            behavior.DummyBehaviorState.HuntObjective,
        )

    def test_required_home_movement_continues_until_stop_range_even_if_hunt_ready(self):
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

        self.assertTrue(behavior.required_target_home_hunt_ready(client, args))
        self.assertTrue(behavior.should_move_to_required_target_home(client, args, is_party_leader=True, current_target=0))
        self.assertFalse(behavior.should_move_to_required_target_home(client, args, is_party_leader=False, current_target=0))

        client.x = 500
        self.assertTrue(behavior.should_move_to_required_target_home(client, args, is_party_leader=True, current_target=0))
        self.assertFalse(behavior.should_move_to_required_target_home(client, args, is_party_leader=False, current_target=0))

    def test_required_home_hunt_ring_keeps_moving_until_required_target_visible(self):
        args = SimpleNamespace(
            party_size=2,
            party_assist_only=True,
            party_min_ready=2,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=100.0,
            required_target_home_hunt_distance=600.0,
            target_home_max_distance=800.0,
            require_target_name="icestrider",
            prefer_target_name="",
            avoid_target_name="",
            min_target_level=0,
            max_target_level=0,
            player_level=50,
            max_target_level_delta=0,
            max_target_distance=2000.0,
            npc_max_age=60.0,
            scan_peace_npcs=False,
        )
        client = SimpleNamespace(
            x=500,
            y=0,
            z=0,
            visible_npcs=lambda **_kwargs: [],
            distance_to=lambda npc: behavior.horizontal_distance_between_points(500, 0, npc.x, npc.y),
        )

        self.assertFalse(behavior.required_target_home_hunt_ready(client, args))
        self.assertTrue(behavior.should_move_to_required_target_home(client, args, is_party_leader=True, current_target=0))
        self.assertFalse(behavior.should_move_to_required_target_home(client, args, is_party_leader=False, current_target=0))

        client.visible_npcs = lambda **_kwargs: [
            SimpleNamespace(object_id=77, name="icestrider interceptor", level=47, x=1000, y=0, z=0)
        ]
        self.assertTrue(behavior.required_target_home_hunt_ready(client, args))
        self.assertTrue(behavior.should_move_to_required_target_home(client, args, is_party_leader=True, current_target=0))
        self.assertFalse(behavior.should_move_to_required_target_home(client, args, is_party_leader=False, current_target=0))

        client.x = 950
        self.assertFalse(behavior.should_move_to_required_target_home(client, args, is_party_leader=True, current_target=0))
        self.assertFalse(behavior.should_move_to_required_target_home(client, args, is_party_leader=False, current_target=0))

    def test_required_home_hunt_ring_allows_api_scout_to_find_target(self):
        args = SimpleNamespace(
            party_size=2,
            party_assist_only=True,
            party_min_ready=2,
            hunter_target_api_scout=True,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=100.0,
            required_target_home_hunt_distance=600.0,
            target_home_max_distance=800.0,
            require_target_name="icestrider",
            prefer_target_name="",
            avoid_target_name="",
            min_target_level=0,
            max_target_level=0,
            player_level=50,
            max_target_level_delta=0,
            max_target_distance=2200.0,
            npc_max_age=60.0,
            include_peace_npcs=True,
        )
        client = SimpleNamespace(
            x=500,
            y=0,
            z=0,
            visible_npcs=lambda **_kwargs: [],
            distance_to=lambda npc: behavior.horizontal_distance_between_points(500, 0, npc.x, npc.y),
        )

        self.assertTrue(behavior.required_target_home_hunt_ready(client, args))
        client.x = 950
        self.assertFalse(behavior.should_move_to_required_target_home(client, args, is_party_leader=True, current_target=0))

    def test_healer_defer_required_home_move_while_precasting_party_heal(self):
        self.assertTrue(
            behavior.should_defer_required_home_move_for_friendly_cast(
                is_party_follower=True,
                action_rotation="healer-support",
                precast_movement_hold=True,
            )
        )
        self.assertFalse(
            behavior.should_defer_required_home_move_for_friendly_cast(
                is_party_follower=False,
                action_rotation="healer-support",
                precast_movement_hold=True,
            )
        )
        self.assertFalse(
            behavior.should_defer_required_home_move_for_friendly_cast(
                is_party_follower=True,
                action_rotation="melee-basic",
                precast_movement_hold=True,
            )
        )
        self.assertTrue(
            behavior.should_defer_required_home_move_for_friendly_cast(
                is_party_follower=True,
                action_rotation="healer-support",
                precast_movement_hold=False,
                friendly_target_pending=True,
            )
        )

    def test_rescue_counterattack_starts_combat_metric_when_untracked_damage_targets_actor(self):
        actor = SimpleNamespace(object_id=200)

        self.assertTrue(behavior.should_start_rescue_counterattack_combat(None, 200, actor))
        self.assertFalse(behavior.should_start_rescue_counterattack_combat({"target_id": 100}, 200, actor))
        self.assertFalse(behavior.should_start_rescue_counterattack_combat(None, 0, actor))
        self.assertFalse(behavior.should_start_rescue_counterattack_combat(None, 200, None))

    def test_objective_damage_counterattack_uses_shared_required_target_before_flee(self):
        args = SimpleNamespace(
            flee_health_percent=55,
            require_target_name="frost spectre",
            prefer_target_name="",
        )
        snapshot = {
            "active_tank_name": "Tank",
            "leader_target_id": 13617,
            "leader_target_name": "frost spectre",
            "leader_target_x": 727359,
            "leader_target_y": 623174,
            "leader_target_z": 6655,
            "leader_target_level": 47,
        }

        actor = behavior.party_objective_actor_from_snapshot_for_counterattack(
            args,
            snapshot,
            member_name="Tank",
            action_rotation="melee-basic",
            health_percent=75,
        )

        self.assertIsNotNone(actor)
        self.assertEqual(actor.object_id, 13617)
        self.assertEqual(actor.name, "frost spectre")
        self.assertIsNone(
            behavior.party_objective_actor_from_snapshot_for_counterattack(
                args,
                snapshot,
                member_name="Tank",
                action_rotation="melee-basic",
                health_percent=55,
            )
        )

    def test_objective_damage_counterattack_waits_until_returned_to_hunt_area(self):
        args = SimpleNamespace(
            flee_health_percent=55,
            require_target_name="sylvan goblin warrior",
            prefer_target_name="",
        )
        snapshot = {
            "active_tank_name": "Tank",
            "leader_target_id": 2197,
            "leader_target_name": "sylvan goblin warrior",
            "leader_target_x": 517757,
            "leader_target_y": 625728,
            "leader_target_z": 1985,
            "leader_target_level": 9,
        }

        actor = behavior.party_objective_actor_from_snapshot_for_counterattack(
            args,
            snapshot,
            member_name="Tank",
            action_rotation="melee-basic",
            health_percent=90,
            behavior_state=behavior.DummyBehaviorState.ReturnToObjective,
            required_home_hunt_ready=False,
            party_ready_for_objective=True,
        )

        self.assertIsNone(actor)

    def test_party_heal_target_range_blocks_precast_hold_when_leader_too_far(self):
        args = SimpleNamespace(spell_range=1500.0)
        client = SimpleNamespace(x=0, y=0)
        near_member = {"name": "Leader", "object_id": 7, "health_percent": 50, "x": 1200, "y": 0, "z": 0}
        marginal_member = {"name": "Leader", "object_id": 7, "health_percent": 50, "x": 1450, "y": 0, "z": 0}
        far_member = {"name": "Leader", "object_id": 7, "health_percent": 50, "x": 2200, "y": 0, "z": 0}

        self.assertTrue(behavior.party_heal_target_in_cast_range(client, args, near_member))
        self.assertFalse(behavior.party_heal_target_in_cast_range(client, args, marginal_member))
        self.assertFalse(behavior.party_heal_target_in_cast_range(client, args, far_member))
        self.assertFalse(behavior.party_heal_target_in_cast_range(client, args, None))

    def test_party_healer_can_approach_out_of_range_heal_target_during_recovery(self):
        args = SimpleNamespace(
            spell_range=1500.0,
            party_heal_cast_range_buffer=200.0,
            party_follow_step=320.0,
            nav_api_url="",
            movement_speed=None,
            movement_update_interval=0.0,
        )
        path_state = SimpleNamespace(graph=None, client_grid=None)
        action_counts: dict[str, int] = {}
        hurt_member = {"name": "Leader", "object_id": 7, "health_percent": 50, "x": 3000, "y": 100, "z": 40}

        class HealMoveClient:
            def __init__(self) -> None:
                self.x = 0
                self.y = 0
                self.z = 0
                self.attack_modes: list[bool] = []
                self.moves: list[dict[str, float | int | bool | None]] = []

            def set_attack_mode(self, enabled: bool) -> None:
                self.attack_modes.append(enabled)

            def move_towards_position(
                self,
                x: int,
                y: int,
                z: int,
                *,
                step: float,
                stop_distance: float,
                movement_speed: float | None = None,
                min_position_send_interval: float = 0.0,
                target_in_view: bool = False,
            ) -> bool:
                self.moves.append(
                    {
                        "x": x,
                        "y": y,
                        "z": z,
                        "step": step,
                        "stop_distance": stop_distance,
                        "movement_speed": movement_speed,
                        "min_position_send_interval": min_position_send_interval,
                        "target_in_view": target_in_view,
                    }
                )
                return True

        client = HealMoveClient()

        self.assertTrue(
            behavior.should_approach_party_heal_target(
                args,
                action_rotation="healer-support",
                hurt_member=hurt_member,
                current_target=0,
                behavior_state=behavior.DummyBehaviorState.RestRecover,
            )
        )

        outcome = behavior.move_towards_party_heal_target(client, args, path_state, action_counts, hurt_member)

        self.assertIsNotNone(outcome)
        self.assertTrue(outcome.moved)
        self.assertEqual(client.attack_modes, [False])
        self.assertEqual(client.moves[0]["x"], 3000)
        self.assertEqual(client.moves[0]["y"], 100)
        self.assertEqual(client.moves[0]["z"], 40)
        self.assertEqual(client.moves[0]["stop_distance"], 1300.0)
        self.assertEqual(client.moves[0]["target_in_view"], False)

    def test_party_heal_approach_uses_direct_member_move_when_path_graph_cannot_route(self):
        args = SimpleNamespace(
            spell_range=1500.0,
            party_heal_cast_range_buffer=200.0,
            party_follow_step=320.0,
            nav_api_url="",
            movement_speed=240.0,
            movement_update_interval=0.2,
        )
        path_state = SimpleNamespace(graph=object(), client_grid=None)
        action_counts: dict[str, int] = {}
        hurt_member = {"name": "Leader", "object_id": 7, "health_percent": 50, "x": 2100, "y": 0, "z": 0}

        class DirectHealMoveClient:
            def __init__(self) -> None:
                self.x = 0
                self.y = 0
                self.z = 0
                self.moves: list[dict[str, float | int | bool | None]] = []

            def set_attack_mode(self, _enabled: bool) -> None:
                pass

            def move_towards_position(
                self,
                x: int,
                y: int,
                z: int,
                *,
                step: float,
                stop_distance: float,
                movement_speed: float | None = None,
                min_position_send_interval: float = 0.0,
                target_in_view: bool = False,
            ) -> bool:
                self.moves.append(
                    {
                        "x": x,
                        "y": y,
                        "z": z,
                        "step": step,
                        "stop_distance": stop_distance,
                        "movement_speed": movement_speed,
                        "min_position_send_interval": min_position_send_interval,
                        "target_in_view": target_in_view,
                    }
                )
                return True

        client = DirectHealMoveClient()

        outcome = behavior.move_towards_party_heal_target(client, args, path_state, action_counts, hurt_member)

        self.assertIsNotNone(outcome)
        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[0]["x"], 2100)
        self.assertEqual(client.moves[0]["stop_distance"], 1300.0)
        self.assertEqual(client.moves[0]["movement_speed"], 240.0)

    def test_party_healer_approaches_support_target_even_with_enemy_target(self):
        args = SimpleNamespace()
        hurt_member = {"name": "Leader", "object_id": 7, "health_percent": 50, "x": 3000, "y": 100, "z": 40}

        self.assertFalse(
            behavior.should_approach_party_heal_target(
                args,
                action_rotation="healer-support",
                hurt_member=hurt_member,
                current_target=0,
                behavior_state=behavior.DummyBehaviorState.DropAggroAndRecover,
            )
        )
        self.assertTrue(
            behavior.should_approach_party_heal_target(
                args,
                action_rotation="healer-support",
                hurt_member=hurt_member,
                current_target=22,
                behavior_state=behavior.DummyBehaviorState.RestRecover,
            )
        )
        self.assertFalse(
            behavior.should_approach_party_heal_target(
                args,
                action_rotation="melee-basic",
                hurt_member=hurt_member,
                current_target=0,
                behavior_state=behavior.DummyBehaviorState.RestRecover,
            )
        )
        self.assertTrue(
            behavior.should_approach_party_resurrection_target(
                args,
                action_rotation="healer-support",
                dead_member=hurt_member,
                current_target=22,
                behavior_state=behavior.DummyBehaviorState.RestRecover,
            )
        )

    def test_healer_self_preserve_can_cast_while_recovery_resting(self):
        args = SimpleNamespace(healer_self_health_percent=65)

        self.assertTrue(
            behavior.should_healer_self_preserve_during_rest(
                args,
                action_rotation="healer-support",
                current_health_percent=20,
                now=10.0,
                next_self_preserve_heal=9.0,
            )
        )
        self.assertFalse(
            behavior.should_healer_self_preserve_during_rest(
                args,
                action_rotation="melee-basic",
                current_health_percent=20,
                now=10.0,
                next_self_preserve_heal=9.0,
            )
        )
        self.assertFalse(
            behavior.should_healer_self_preserve_during_rest(
                args,
                action_rotation="healer-support",
                current_health_percent=90,
                now=10.0,
                next_self_preserve_heal=9.0,
            )
        )
        self.assertFalse(
            behavior.should_healer_self_preserve_during_rest(
                args,
                action_rotation="healer-support",
                current_health_percent=20,
                now=10.0,
                next_self_preserve_heal=11.0,
            )
        )

    def test_healer_aborts_recovery_rest_for_hurt_party_member_when_self_stable(self):
        args = SimpleNamespace(healer_self_health_percent=65)
        hurt_member = {"name": "Leader", "health_percent": 40}

        self.assertTrue(
            behavior.should_healer_abort_rest_for_party_heal(
                args,
                action_rotation="healer-support",
                current_health_percent=74,
                hurt_member=hurt_member,
            )
        )
        self.assertFalse(
            behavior.should_healer_abort_rest_for_party_heal(
                args,
                action_rotation="healer-support",
                current_health_percent=50,
                hurt_member=hurt_member,
            )
        )
        self.assertFalse(
            behavior.should_healer_abort_rest_for_party_heal(
                args,
                action_rotation="melee-basic",
                current_health_percent=74,
                hurt_member=hurt_member,
            )
        )
        self.assertFalse(
            behavior.should_healer_abort_rest_for_party_heal(
                args,
                action_rotation="healer-support",
                current_health_percent=74,
                hurt_member=None,
            )
        )

    def test_healer_aborts_recovery_rest_for_resurrection_or_cure_when_self_stable(self):
        args = SimpleNamespace(healer_self_health_percent=65)
        target = {"name": "Leader", "health_percent": 0}
        spell = object()

        self.assertTrue(
            behavior.should_healer_abort_rest_for_party_resurrection(
                args,
                action_rotation="healer-support",
                current_health_percent=74,
                dead_member=target,
                resurrection_spells=[spell],
            )
        )
        self.assertFalse(
            behavior.should_healer_abort_rest_for_party_resurrection(
                args,
                action_rotation="healer-support",
                current_health_percent=50,
                dead_member=target,
                resurrection_spells=[spell],
            )
        )
        self.assertTrue(
            behavior.should_healer_abort_rest_for_party_cure(
                args,
                action_rotation="healer-support",
                current_health_percent=74,
                cure_target=target,
                cure_spell=spell,
            )
        )
        self.assertFalse(
            behavior.should_healer_abort_rest_for_party_cure(
                args,
                action_rotation="healer-support",
                current_health_percent=74,
                cure_target=target,
                cure_spell=None,
            )
        )

    def test_validated_party_buff_source_does_not_require_raw_spell_levels(self):
        args = SimpleNamespace(party_buff_spell_levels=[])

        self.assertTrue(
            behavior.has_party_buff_cast_source(
                args,
                behavior.CombatUsablePlan(
                    buff_spells=[behavior.UsableSpellRef(line_index=1, spell_level=5, name="Blessing", level=5)]
                ),
            )
        )
        self.assertFalse(behavior.has_party_buff_cast_source(args, behavior.CombatUsablePlan()))

    def test_healer_prioritizes_critical_party_heal_over_self_preserve(self):
        args = SimpleNamespace(healer_self_health_percent=65, flee_health_percent=35, party_heal_leader_health_percent=80)
        hurt_member = {"name": "Leader", "health_percent": 13}

        self.assertTrue(
            behavior.should_healer_prioritize_party_heal_during_rest(
                args,
                action_rotation="healer-support",
                current_health_percent=61,
                hurt_member=hurt_member,
            )
        )
        self.assertFalse(
            behavior.should_healer_prioritize_party_heal_during_rest(
                args,
                action_rotation="healer-support",
                current_health_percent=30,
                hurt_member=hurt_member,
            )
        )

    def test_support_priority_critical_self_heal_beats_cure(self):
        args = SimpleNamespace(healer_self_health_percent=65, flee_health_percent=35, party_heal_leader_health_percent=80)
        hurt_member = {"name": "cleric", "health_percent": 52}

        priority = behavior.choose_party_support_action_priority(
            args,
            action_rotation="healer-support",
            current_health_percent=52,
            hurt_member=hurt_member,
            heal_due=True,
            cure_due=True,
            resurrection_due=False,
            crowd_control_due=False,
        )

        self.assertEqual(priority, "heal")

    def test_support_priority_active_tank_heal_beats_resurrection(self):
        args = SimpleNamespace(healer_self_health_percent=65, flee_health_percent=35, party_heal_leader_health_percent=80)
        hurt_member = {"name": "tank", "health_percent": 28}

        priority = behavior.choose_party_support_action_priority(
            args,
            action_rotation="healer-support",
            current_health_percent=92,
            hurt_member=hurt_member,
            heal_due=True,
            cure_due=False,
            resurrection_due=True,
            crowd_control_due=False,
        )

        self.assertEqual(priority, "heal")

    def test_support_priority_critical_heal_defers_crowd_control_add(self):
        args = SimpleNamespace(healer_self_health_percent=65, flee_health_percent=35, party_heal_leader_health_percent=80)
        hurt_member = {"name": "leader", "health_percent": 24}

        priority = behavior.choose_party_support_action_priority(
            args,
            action_rotation="healer-support",
            current_health_percent=88,
            hurt_member=hurt_member,
            heal_due=True,
            cure_due=False,
            resurrection_due=False,
            crowd_control_due=True,
        )

        self.assertEqual(priority, "heal")

    def test_external_leader_critical_heal_beats_external_member_cure(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=22, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        state.update_external_member(
            "RealPlayer",
            SimpleNamespace(object_id=90, health_percent=100, x=25, y=0, z=0),
            role="external",
        )
        state.update_member_condition(
            "RealPlayer",
            behavior.PlayerConditionSnapshot(name="RealPlayer", object_id=90, health_percent=100, is_diseased=True),
        )
        args = SimpleNamespace(healer_self_health_percent=65, flee_health_percent=35, party_heal_leader_health_percent=80)
        plan = behavior.CombatUsablePlan(
            cure_spells=[
                behavior.UsableSpellRef(line_index=2, spell_level=8, name="Cure Disease", level=8, spell_type="CureDisease")
            ]
        )

        hurt_member = behavior.choose_party_heal_target(state, args, exclude_name="cleric")
        cure_target, cure_spell = behavior.choose_party_cure_target(state, plan, exclude_name="cleric")
        priority = behavior.choose_party_support_action_priority(
            args,
            action_rotation="healer-support",
            current_health_percent=100,
            hurt_member=hurt_member,
            heal_due=True,
            cure_due=cure_target is not None and cure_spell is not None,
            resurrection_due=False,
            crowd_control_due=False,
        )

        self.assertEqual(hurt_member["name"], "leader")
        self.assertEqual(cure_target["name"], "RealPlayer")
        self.assertEqual(priority, "heal")

    def test_party_resurrection_without_spell_does_not_apply_retry_cooldown(self):
        self.assertFalse(behavior.should_apply_party_resurrection_cooldown(None))
        self.assertTrue(behavior.should_apply_party_resurrection_cooldown("validated_party_resurrect_member"))

    def test_healer_self_preserves_while_fleeing(self):
        args = SimpleNamespace(healer_self_health_percent=65)

        self.assertTrue(
            behavior.should_healer_self_preserve_while_fleeing(
                args,
                action_rotation="healer-support",
                current_health_percent=63,
                now=20.0,
                flee_until=30.0,
                next_self_preserve_heal=10.0,
            )
        )
        self.assertFalse(
            behavior.should_healer_self_preserve_while_fleeing(
                args,
                action_rotation="melee-basic",
                current_health_percent=63,
                now=20.0,
                flee_until=30.0,
                next_self_preserve_heal=10.0,
            )
        )

    def test_healer_self_preserve_cast_uses_validated_heal_spell_stationary(self):
        client = FakeCombatClient()
        client.commands = []
        client.send_command = client.commands.append
        args = SimpleNamespace(
            combat_plan_spell_pool=1,
            stationary_cast_actions=True,
            allow_unvalidated_spells=False,
            heal_spell_levels=[1],
            heal_spell_line_index=0,
        )
        plan = behavior.CombatUsablePlan(
            heal_spells=[behavior.UsableSpellRef(line_index=2, spell_level=7, name="Minor Emendation", level=5)]
        )

        action = behavior.perform_healer_self_preserve_cast(client, random.Random(1), args, plan)

        self.assertEqual(action, "validated_self_preserve_heal_spell")
        self.assertEqual(client.commands, ["/stand"])
        self.assertEqual(client.spells, [(7, 2)])
        self.assertEqual(client.position_updates, [(0.0, True)])

    def test_healer_self_preserve_targets_self_before_cast(self):
        client = FakeCombatClient()
        client.player_object_id = 77
        client.target_calls = []
        client.target_object = lambda object_id, **_kwargs: client.target_calls.append(object_id) or 0
        client.send_command = lambda _command: None
        args = SimpleNamespace(
            combat_plan_spell_pool=2,
            stationary_cast_actions=False,
            allow_unvalidated_spells=False,
        )
        plan = behavior.CombatUsablePlan(
            heal_spells=[behavior.UsableSpellRef(line_index=2, spell_level=7, name="Minor Emendation", level=5)]
        )

        action = behavior.perform_healer_self_preserve_cast(client, random.Random(1), args, plan)

        self.assertEqual(action, "validated_self_preserve_heal_spell")
        self.assertEqual(client.target_calls, [77])

    def test_low_health_far_from_home_keeps_moving_before_rest_even_inside_hunt_ring(self):
        args = SimpleNamespace(
            party_size=1,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=6200.0,
            combat_home_leash_distance=1200.0,
            target_home_max_distance=1400.0,
        )
        client = SimpleNamespace(x=2500, y=0, z=0)

        self.assertTrue(behavior.required_target_home_hunt_ready(client, args))
        self.assertTrue(behavior.should_return_home_before_low_health_rest(client, args))
        self.assertTrue(behavior.should_move_to_required_target_home(client, args, is_party_leader=False, current_target=0))

    def test_required_target_recover_before_home_can_override_low_health_return(self):
        args = SimpleNamespace(
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_recover_before_home_health_percent=88,
        )

        self.assertTrue(behavior.should_recover_before_required_target_home(args, health_percent=70))
        self.assertFalse(behavior.should_recover_before_required_target_home(args, health_percent=90))

    def test_low_health_near_home_allows_rest_inside_hunt_ring(self):
        args = SimpleNamespace(
            party_size=1,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=6200.0,
            combat_home_leash_distance=1200.0,
            target_home_max_distance=1400.0,
        )
        client = SimpleNamespace(x=1800, y=0, z=0)

        self.assertTrue(behavior.required_target_home_hunt_ready(client, args))
        self.assertFalse(behavior.should_return_home_before_low_health_rest(client, args))
        self.assertFalse(behavior.should_move_to_required_target_home(client, args, is_party_leader=False, current_target=0))

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

    def test_target_home_leash_finish_outcome_distinguishes_mob_wander_from_player_chase(self):
        self.assertEqual(
            behavior.target_home_leash_finish_outcome("target"),
            "target_home_guard_abandon",
        )
        self.assertEqual(
            behavior.target_home_leash_finish_outcome("player"),
            "target_home_leash",
        )

    def test_far_committed_target_waits_for_range_before_active_combat(self):
        args = SimpleNamespace(max_target_distance=1500.0)

        self.assertFalse(behavior.should_start_combat_after_target_commit(args, 2600.0))
        self.assertTrue(behavior.should_start_combat_after_target_commit(args, 1400.0))
        self.assertTrue(behavior.should_start_combat_after_target_commit(SimpleNamespace(max_target_distance=0.0), 2600.0))

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
        calls: list[int] = []

        def fake_request_nav_path(_args, _region, _start, _goal):
            calls.append(_region)
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
        self.assertEqual(calls, [1])
        self.assertIn(1, state.navmesh_unavailable_regions)
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

    def test_stale_z_reached_graph_node_can_continue_to_next_edge(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "previous", "x": 50, "y": 0, "z": 100},
                            {"id": "next", "x": 900, "y": 0, "z": 1200},
                        ],
                        "edges": [
                            {"from": "previous", "to": "next", "max_height_delta": 1500},
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
            path_max_edge_length=2000.0,
            path_waypoint_ground_z_skip_delta=500,
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=2000.0, max_height_delta=900.0),
        )
        state.destination_key = "target:stale-z-edge"
        state.resolved_goal = behavior.PathPoint(900, 0, 1200)
        state.follower.set_route([
            graph.nodes["previous"],
            graph.nodes["next"],
        ])
        state.follower.index = 1
        client = PathClient()
        client.x = 55
        client.y = 0
        client.z = 260
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("target:stale-z-edge", 900, 0, 1200),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (900, 0, 1200))
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

    def test_cached_navmesh_unavailable_skips_last_mile_segment_validation(self):
        args = SimpleNamespace(
            nav_api_url="http://127.0.0.1:5000",
            path_last_mile_distance=1500.0,
            path_replan_interval=0.0,
            path_max_node_distance=200.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            nav_segment_validate=True,
            movement_speed=None,
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(None, 1, behavior.PathSafety(max_direct_distance=1500.0, max_edge_length=1500.0))
        state.navmesh_unavailable_regions.add(1)
        client = PathClient()
        action_counts: dict[str, int] = {}
        original_request_nav_path = behavior.request_nav_path

        def fake_request_nav_path(_args, _region, _start, _goal):
            raise AssertionError("cached NavmeshUnavailable should skip nav segment validation")

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

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (1000, 0, 0))
        self.assertEqual(action_counts["path_last_mile"], 1)
        self.assertNotIn("nav_segment_blocked", action_counts)

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

    def test_graph_path_can_move_when_nav_api_connection_fails(self):
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
            return behavior.NavPathResult(False, "nav api error: [Errno 104] Connection reset by peer", [])

        behavior.request_nav_path = fake_request_nav_path

        try:
            outcome = behavior.move_towards_destination(
                client,
                behavior.MovementDestination("waypoint:far", 1000, 0, 0),
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

    def test_offgraph_return_home_rejoins_graph_with_relaxed_height_after_flee(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "rejoin", "x": 1000, "y": 0, "z": 0},
                            {"id": "home", "x": 2000, "y": 0, "z": 0},
                        ],
                        "edges": [{"from": "rejoin", "to": "home"}],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            flee_safe_point_distance=0.0,
            flee_critical_safe_point_distance=9000.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=500),
        )
        client = StepPathClient()
        client.z = 6000
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("required-target-home:1", 2000, 0, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (1000, 0, 0))
        self.assertEqual(action_counts["path_rejoin_graph"], 1)
        self.assertNotIn("path_failed", action_counts)

    def test_offgraph_waypoint_rejoins_graph_instead_of_failing(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "offgraph-high", "x": 0, "y": 0, "z": 6000},
                            {"id": "rejoin", "x": 1000, "y": 0, "z": 0},
                            {"id": "goal", "x": 2000, "y": 0, "z": 0},
                        ],
                        "edges": [{"from": "rejoin", "to": "goal"}],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            flee_safe_point_distance=0.0,
            flee_critical_safe_point_distance=9000.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=500),
        )
        client = StepPathClient()
        client.z = 6000
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("waypoint:observer", 2000, 0, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (1000, 0, 0))
        self.assertEqual(action_counts["path_rejoin_graph"], 1)
        self.assertNotIn("path_failed", action_counts)

    def test_offgraph_party_target_last_known_rejoins_graph_instead_of_failing(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "offgraph-high", "x": 0, "y": 0, "z": 6000},
                            {"id": "rejoin", "x": 1000, "y": 0, "z": 0},
                            {"id": "target", "x": 2000, "y": 0, "z": 0},
                        ],
                        "edges": [{"from": "rejoin", "to": "target"}],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            flee_safe_point_distance=0.0,
            flee_critical_safe_point_distance=9000.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=500),
        )
        client = StepPathClient()
        client.z = 6000
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("party-target-last-known:2660:2908:26", 2000, 0, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
            target_in_view=True,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (1000, 0, 0))
        self.assertEqual(action_counts["path_rejoin_graph"], 1)
        self.assertNotIn("path_failed", action_counts)

    def test_far_offgraph_return_home_walks_toward_home_until_graph_rejoins(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "home", "x": 20000, "y": 0, "z": 0},
                        ],
                        "edges": [],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            flee_safe_point_distance=3000.0,
            flee_critical_safe_point_distance=4000.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=500),
        )
        client = StepPathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("required-target-home:far", 20000, 0, 0),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (20000, 0, 0))
        self.assertEqual(action_counts["path_offgraph_return_move"], 1)
        self.assertNotIn("path_failed", action_counts)

    def test_party_anchor_offgraph_goal_uses_direct_regroup_fallback(self):
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
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=1500.0,
            party_follow_step=320.0,
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=500),
        )
        client = StepPathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("party-anchor:offgraph", 3000, 0, 0),
            step=320.0,
            stop_distance=500.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (3000, 0, 0))
        self.assertEqual(action_counts["path_party_anchor_direct_fallback"], 1)
        self.assertNotIn("path_failed", action_counts)

    def test_party_anchor_route_end_uses_direct_regroup_fallback_to_actual_leader(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "start", "x": 0, "y": 0, "z": 0},
                            {"id": "last", "x": 2000, "y": 0, "z": 0},
                        ],
                        "edges": [{"from": "start", "to": "last"}],
                    }
                }
            }
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=150.0,
            path_replan_interval=0.0,
            path_max_node_distance=500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=2500.0,
            party_follow_step=320.0,
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=2500.0, max_height_delta=500),
        )
        state.destination_key = "party-anchor:leader"
        state.resolved_goal = behavior.PathPoint(2000, 0, 0)
        state.follower.set_route([behavior.PathPoint(2000, 0, 0)])
        client = StepPathClient()
        client.x = 2000
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("party-anchor:leader", 3600, 0, 0),
            step=320.0,
            stop_distance=500.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (3600, 0, 0))
        self.assertEqual(action_counts["path_party_anchor_direct_fallback"], 1)
        self.assertNotIn("path_hold", action_counts)

    def test_party_anchor_direct_regroup_allows_long_emergency_flee_gap(self):
        graph = behavior.PathGraph.from_payload(
            {"regions": {"1": {"nodes": [{"id": "start", "x": 0, "y": 0, "z": 0}], "edges": []}}}
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=1200.0,
            path_replan_interval=0.0,
            path_max_node_distance=500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=2500.0,
            party_follow_step=320.0,
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=1200.0, max_edge_length=2500.0, max_height_delta=500),
        )
        client = StepPathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("party-anchor:flee-regroup", 12000, 0, 0),
            step=320.0,
            stop_distance=500.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (12000, 0, 0))
        self.assertEqual(action_counts["path_party_anchor_direct_fallback"], 1)

    def test_party_anchor_direct_regroup_allows_vindsaul_safe_flee_gap(self):
        graph = behavior.PathGraph.from_payload(
            {"regions": {"1": {"nodes": [{"id": "start", "x": 0, "y": 0, "z": 0}], "edges": []}}}
        )
        args = SimpleNamespace(
            nav_api_url="",
            path_last_mile_distance=1200.0,
            path_replan_interval=0.0,
            path_max_node_distance=500.0,
            path_node_arrival_distance=100.0,
            path_max_edge_length=2500.0,
            party_follow_step=320.0,
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=1200.0, max_edge_length=2500.0, max_height_delta=500),
        )
        client = StepPathClient()
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("party-anchor:vindsaul-regroup", 22000, 0, 0),
            step=320.0,
            stop_distance=500.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (22000, 0, 0))
        self.assertEqual(action_counts["path_party_anchor_direct_fallback"], 1)
        self.assertNotIn("path_failed", action_counts)

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

    def test_graph_step_uses_edge_height_override_after_reaching_previous_node(self):
        graph = behavior.PathGraph.from_payload(
            {
                "regions": {
                    "1": {
                        "nodes": [
                            {"id": "low", "x": 0, "y": 0, "z": 0},
                            {"id": "high", "x": 350, "y": 0, "z": 1200},
                        ],
                        "edges": [
                            {"from": "low", "to": "high", "max_height_delta": 2500},
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
            path_max_edge_length=1500.0,
            nav_segment_validate=False,
            movement_speed=None,
            movement_update_interval=0.0,
        )
        state = behavior.PathMovementState(
            graph,
            1,
            behavior.PathSafety(max_direct_distance=150.0, max_edge_length=1500.0, max_height_delta=500),
        )
        state.destination_key = "waypoint:high"
        state.resolved_goal = behavior.PathPoint(350, 0, 1200)
        state.follower.set_route([graph.nodes["low"], graph.nodes["high"]])
        state.follower.index = 1
        client = StepPathClient()
        client.x = 0
        client.y = 50
        client.z = 0
        action_counts: dict[str, int] = {}

        outcome = behavior.move_towards_destination(
            client,
            behavior.MovementDestination("waypoint:high", 350, 0, 1200),
            step=250.0,
            stop_distance=100.0,
            args=args,
            path_state=state,
            action_counts=action_counts,
        )

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (350, 0, 1200))
        self.assertEqual(action_counts["path_step"], 1)
        self.assertNotIn("path_blocked", action_counts)

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

    def test_cross_zone_required_home_uses_direct_return_fallback_when_graph_has_no_route(self):
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
            return behavior.NavPathResult(False, "CrossZonePathUnsupported", [])

        behavior.request_nav_path = fake_request_nav_path

        try:
            outcome = behavior.move_towards_destination(
                client,
                behavior.MovementDestination("required-target-home:far", 5000, 0, 0),
                step=250.0,
                stop_distance=95.0,
                args=args,
                path_state=state,
                action_counts=action_counts,
            )
        finally:
            behavior.request_nav_path = original_request_nav_path

        self.assertTrue(outcome.moved)
        self.assertEqual(client.moves[-1][:3], (5000, 0, 0))
        self.assertEqual(action_counts["nav_path_failed"], 1)
        self.assertEqual(action_counts["path_offgraph_return_move"], 1)
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
        self.assertEqual(behavior.parse_combat_text_metric("bear에게 62 피해를 입혔습니다!"), ("damage_done", 62))
        self.assertEqual(
            behavior.parse_combat_text_metric("공격합니다이(가) boar piglet 당신의 sword하여 5 (-1) 피해를 입혔습니다!"),
            ("damage_done", 5),
        )
        self.assertEqual(behavior.parse_combat_text_metric("당신은 45 피해를 받았습니다."), ("damage_taken", 45))
        self.assertEqual(
            behavior.parse_combat_text_metric("drakulv executioner이(가) 당신의 몸통에게 195 (-27) 피해를 입혔습니다!"),
            ("damage_taken", 195),
        )
        self.assertEqual(
            behavior.parse_combat_text_metric("wintery dirge이(가) 당신에게 106 (-6) 피해를 입혔습니다!"),
            ("damage_taken", 106),
        )
        self.assertEqual(
            behavior.parse_incoming_damage_attacker_name("wintery dirge이(가) 당신에게 106 (-6) 피해를 입혔습니다!"),
            "wintery dirge",
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

    def test_incoming_attack_attempt_parser_extracts_miss_attacker_name(self):
        korean_miss = (
            "arawnite headhunter"
            "\uc774(\uac00) \uacf5\uaca9\ud588\uc9c0\ub9cc "
            "\ube57\ub098\uac14\uc2b5\ub2c8\ub2e4! (45.9%)"
        )

        self.assertEqual(
            behavior.parse_incoming_attack_attacker_name(korean_miss),
            "arawnite headhunter",
        )
        self.assertEqual(
            behavior.parse_incoming_attack_attacker_name("arawnite headhunter attacks you and misses!"),
            "arawnite headhunter",
        )

    def test_aggro_pressure_uses_recent_attack_attempt_when_damage_is_stale(self):
        self.assertEqual(
            behavior.latest_aggro_pressure_at(last_damage_taken_at=10.0, last_incoming_damage_at=17.5),
            17.5,
        )

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

    def test_auto_rotation_uses_account_class_profile_before_slot_mix(self):
        args = SimpleNamespace(
            party_slot_rotations=[],
            action_rotation="auto",
            party_size=4,
            party_role_strategy="mixed",
            behavior_profile="custom",
        )
        cleric = behavior.DummyAccount("cleric", "pass", 1, 0, class_id=6, class_name="Cleric")
        wizard = behavior.DummyAccount("wizard", "pass", 1, 0, class_id=7, class_name="Wizard")
        thane = behavior.DummyAccount("thane", "pass", 2, 0, class_id=21, class_name="Thane")

        self.assertEqual(behavior.resolve_action_rotation(args, 0, account=cleric), "healer-support")
        self.assertEqual(behavior.resolve_action_rotation(args, 0, account=wizard), "caster-basic")
        self.assertEqual(behavior.resolve_action_rotation(args, 0, account=thane), "hybrid")

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

    def test_effective_rotation_keeps_healer_with_support_spells_without_heal(self):
        args = SimpleNamespace(allow_unvalidated_spells=False, allow_unvalidated_skills=False)
        plan = behavior.CombatUsablePlan(
            attack_spells=[
                behavior.UsableSpellRef(
                    line_index=2,
                    spell_level=35,
                    name="Smite",
                    level=35,
                )
            ],
            cure_spells=[
                behavior.UsableSpellRef(
                    line_index=3,
                    spell_level=20,
                    name="Cure Poison",
                    level=20,
                    spell_type="CurePoison",
                )
            ],
        )

        self.assertEqual(behavior.resolve_effective_action_rotation(args, "healer-support", plan, True), "healer-support")

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

    def test_active_party_rescue_focus_survives_empty_shared_party_target(self):
        args = SimpleNamespace(
            party_assist_only=True,
            party_rescue_aggro=True,
            require_target_name="fenrir snowscout",
        )
        active = {
            "target_id": 24443,
            "target_name": "fenrir snowscout",
            "target_level": 36,
            "target_intent": "party_rescue",
            "attacks": 1,
            "skills": 0,
            "damage_done": 492,
            "damage_taken": 354,
        }
        state = behavior.PartyState("leader", ["leader", "member"])

        self.assertTrue(behavior.should_preserve_unshared_party_target(args, 24443, active))
        self.assertTrue(behavior.should_preserve_current_party_target(args, state, 24443, active))

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

    def test_incoming_melee_damage_skips_attack_prime_delay(self):
        args = SimpleNamespace(attack_target_in_view_prime_delay=1.1)

        self.assertEqual(behavior.attack_target_in_view_prime_delay(args, recent_incoming_melee=True), 0.0)
        self.assertEqual(behavior.attack_target_in_view_prime_delay(args, recent_incoming_melee=False), 1.1)

    def test_zero_attack_prime_delay_allows_immediate_new_target_attack(self):
        self.assertFalse(
            behavior.should_wait_for_attack_target_prime(
                primed_target=0,
                current_target=123,
                primed_at=0.0,
                now=10.0,
                prime_delay=0.0,
            )
        )

    def test_positive_attack_prime_delay_waits_for_new_target(self):
        self.assertTrue(
            behavior.should_wait_for_attack_target_prime(
                primed_target=0,
                current_target=123,
                primed_at=0.0,
                now=10.0,
                prime_delay=1.1,
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

    def test_party_objective_scan_rejects_named_add_outside_engage_range_without_objective(self):
        add = FakeNpc(20, "fenrir prophet", 45, 8500.0)
        args = SimpleNamespace(
            require_target_name="fenrir tracker",
            objective_add_target_name="fenrir prophet",
            npc_max_age=30.0,
            include_peace_npcs=False,
            party_assist_only=True,
            party_encounter_mode="boss",
            party_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
            party_rescue_objective_max_distance=1800.0,
            max_target_distance=2200.0,
        )
        snapshot = {"leader_target_id": 0, "leader_target_name": "", "leader_target_x": 0, "leader_target_y": 0}

        selected = behavior.choose_party_rescue_attacker(
            FakeClient(npcs=[add]),
            args,
            leader_target_id=0,
            party_snapshot=snapshot,
            objective_scan_only=True,
        )

        self.assertIsNone(selected)

    def test_party_rescue_threat_target_rejects_distant_objective_add(self):
        add = FakeNpc(20, "fenrir prophet", 45, 8500.0)
        args = SimpleNamespace(
            party_rescue_aggro=True,
            require_target_name="fenrir tracker",
            objective_add_target_name="fenrir prophet",
            party_rescue_max_age=14.0,
            party_rescue_max_distance=1400.0,
            party_rescue_engaged_distance=250.0,
            party_rescue_objective_max_distance=1800.0,
            max_target_distance=2200.0,
            party_encounter_mode="boss",
        )
        snapshot = {
            "leader_target_id": 0,
            "leader_target_name": "",
            "leader_target_x": 0,
            "leader_target_y": 0,
            "rescue_threats": [
                {
                    "object_id": 20,
                    "requested_at": 100.0,
                    "objective_add": True,
                    "member_name": "leader",
                }
            ],
        }

        selected = behavior.choose_party_rescue_threat_target(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            member_name="leader",
            action_rotation="melee-basic",
            health_percent=95,
            now=101.0,
        )

        self.assertIsNone(selected)

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

    def test_named_rescue_attacker_accepts_required_target_that_hits_player(self):
        required = FakeNpc(20, "bone-eater clanmother", 47, 250.0)
        args = SimpleNamespace(
            require_target_name="bone-eater clanmother",
            party_encounter_mode="standard",
            player_level=50,
            max_target_level=48,
            max_target_level_delta=1,
        )

        selected = behavior.choose_named_rescue_attacker(
            [required],
            FakeClient(npcs=[required]),
            args,
            leader_target_id=0,
            attacker_name="bone-eater clanmother",
        )

        self.assertEqual(selected.object_id, 20)

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
            party_encounter_mode="boss",
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

    def test_pre_objective_add_target_skips_ambient_adds_for_standard_growth_route(self):
        objective = FakeNpc(10, "sylvan goblin warrior", 9, 650.0)
        objective.x = 1000
        objective.y = 1000
        hunter = FakeNpc(20, "sylvan goblin hunter", 7, 180.0)
        hunter.x = 1025
        hunter.y = 990
        args = SimpleNamespace(
            require_target_name="sylvan goblin warrior",
            avoid_target_name="",
            objective_add_target_name="",
            party_clear_objective_adds_before_engage=True,
            party_rescue_objective_max_distance=950.0,
            party_rescue_ignore_low_level_delta=8,
            party_encounter_mode="standard",
            player_level=10,
            max_target_level=12,
            max_target_level_delta=2,
            hunter_target_max_ground_z_delta=0.0,
        )

        selected = behavior.choose_pre_objective_add_target([objective, hunter], FakeClient(npcs=[objective, hunter]), args, objective)

        self.assertIsNone(selected)

    def test_pre_objective_add_target_skips_unsafe_or_rejected_ambient_adds(self):
        objective = FakeNpc(10, "sylvan goblin warrior", 9, 650.0)
        objective.x = 1000
        objective.y = 1000
        rejected_hunter = FakeNpc(20, "sylvan goblin hunter", 7, 180.0)
        rejected_hunter.x = 1025
        rejected_hunter.y = 990
        avoided_chief = FakeNpc(21, "sylvan goblin chief", 16, 220.0)
        avoided_chief.x = 1040
        avoided_chief.y = 1000
        trivial_ant = FakeNpc(22, "ant drone", 2, 120.0)
        trivial_ant.x = 1010
        trivial_ant.y = 1010
        args = SimpleNamespace(
            require_target_name="sylvan goblin warrior",
            avoid_target_name="sylvan goblin chief",
            objective_add_target_name="",
            party_clear_objective_adds_before_engage=True,
            party_rescue_objective_max_distance=950.0,
            party_rescue_ignore_low_level_delta=8,
            party_encounter_mode="standard",
            player_level=10,
            max_target_level=12,
            max_target_level_delta=2,
            hunter_target_max_ground_z_delta=0.0,
        )

        selected = behavior.choose_pre_objective_add_target(
            [objective, rejected_hunter, avoided_chief, trivial_ant],
            FakeClient(npcs=[objective, rejected_hunter, avoided_chief, trivial_ant]),
            args,
            objective,
            rejected_targets={20: 125.0},
            rejected_target_kinds={},
            now=120.0,
        )

        self.assertIsNone(selected)

    def test_pre_objective_rescue_can_enter_hunt_after_party_and_home_are_ready(self):
        args = SimpleNamespace(required_target_home=SimpleNamespace(x=1000, y=1000, z=500))

        self.assertTrue(
            behavior.should_enter_hunt_for_objective_area_rescue(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                selected_npc_is_rescue=True,
                required_home_hunt_ready=True,
                party_ready_for_objective=True,
            )
        )

    def test_pre_objective_required_rescue_waits_for_active_tank_not_dps_follower(self):
        args = SimpleNamespace(required_target_home=SimpleNamespace(x=1000, y=1000, z=500))

        self.assertFalse(
            behavior.should_enter_hunt_for_objective_area_rescue(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                selected_npc_is_rescue=True,
                selected_npc_is_required=True,
                is_party_follower=True,
                is_active_tank=False,
                required_home_hunt_ready=True,
                party_ready_for_objective=True,
            )
        )
        self.assertTrue(
            behavior.should_enter_hunt_for_objective_area_rescue(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                selected_npc_is_rescue=True,
                selected_npc_is_required=True,
                is_party_follower=True,
                is_active_tank=True,
                required_home_hunt_ready=True,
                party_ready_for_objective=True,
            )
        )

    def test_pre_objective_rescue_stays_gated_until_party_and_home_are_ready(self):
        args = SimpleNamespace(required_target_home=SimpleNamespace(x=1000, y=1000, z=500))

        self.assertFalse(
            behavior.should_enter_hunt_for_objective_area_rescue(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                selected_npc_is_rescue=True,
                required_home_hunt_ready=False,
                party_ready_for_objective=True,
            )
        )

    def test_choose_party_rescue_threat_target_can_return_required_target_that_hit_tank(self):
        required = FakeNpc(20, "bone-eater clanmother", 47, 250.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 0,
            "active_tank_name": "GrowthMid4320",
            "rescue_tank_name": "GrowthMid4320",
            "rescue_member_name": "GrowthMid4320",
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": False, "member_name": "GrowthMid4320"},
            ],
        }
        args = SimpleNamespace(
            require_target_name="bone-eater clanmother",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=1400.0,
            party_rescue_assist_after=0.0,
            party_assist_rescue_target=True,
            party_encounter_mode="standard",
            player_level=50,
            max_target_level=48,
            max_target_level_delta=1,
        )

        selected = behavior.choose_party_rescue_threat_target(
            [required],
            FakeClient(npcs=[required]),
            args,
            snapshot,
            member_name="GrowthMid4320",
            action_rotation="melee-basic",
            health_percent=40,
            now=now,
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

    def test_pre_objective_add_target_waits_for_required_target_before_clearing_adds(self):
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

        self.assertIsNone(selected)

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

    def test_travel_state_routes_non_objective_add_to_handle_travel_aggro(self):
        add = FakeNpc(20, "wintery dirge", 44, 140.0)
        args = SimpleNamespace(require_target_name="icestrider interceptor")

        self.assertTrue(
            behavior.should_handle_travel_aggro_target(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                add,
                behavior.TargetIntent.party_rescue,
            )
        )

    def test_travel_state_routes_non_preferred_add_without_required_name(self):
        add = FakeNpc(20, "wood imp", 5, 140.0)
        args = SimpleNamespace(require_target_name="", prefer_target_name="pine imp")

        self.assertEqual(
            behavior.target_intent_for_selected_npc(
                args,
                add,
                selected_npc_is_rescue=False,
                behavior_state=behavior.DummyBehaviorState.TravelToObjective,
            ),
            behavior.TargetIntent.travel_aggro,
        )
        self.assertTrue(
            behavior.should_handle_travel_aggro_target(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                add,
                behavior.TargetIntent.travel_aggro,
            )
        )

    def test_travel_state_marks_avoid_list_target_as_avoided_add(self):
        add = FakeNpc(20, "feccan", 4, 140.0)
        args = SimpleNamespace(
            require_target_name="",
            prefer_target_name="eirebug,spraggon,large frog",
            avoid_target_name="feccan,lough wolf,wild crouch,water beetle",
        )

        self.assertEqual(
            behavior.target_intent_for_selected_npc(
                args,
                add,
                selected_npc_is_rescue=False,
                behavior_state=behavior.DummyBehaviorState.TravelToObjective,
            ),
            behavior.TargetIntent.avoided_add,
        )

    def test_passive_avoided_add_during_travel_is_suppressed_without_flee(self):
        add = FakeNpc(20, "feccan", 4, 140.0)
        args = SimpleNamespace(
            avoid_target_name="feccan,lough wolf",
            incoming_damage_melee_grace=4.0,
        )

        self.assertTrue(
            behavior.should_suppress_passive_avoided_travel_target(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                add,
                behavior.TargetIntent.avoided_add,
                current_target=0,
                now=100.0,
                last_damage_taken_at=0.0,
            )
        )
        self.assertFalse(
            behavior.should_suppress_passive_avoided_travel_target(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                add,
                behavior.TargetIntent.avoided_add,
                current_target=add.object_id,
                now=100.0,
                last_damage_taken_at=0.0,
            )
        )
        self.assertFalse(
            behavior.should_suppress_passive_avoided_travel_target(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                add,
                behavior.TargetIntent.avoided_add,
                current_target=0,
                now=100.0,
                last_damage_taken_at=98.5,
            )
        )

    def test_passive_non_objective_target_during_travel_is_suppressed_without_flee(self):
        add = FakeNpc(20, "mudman", 4, 140.0)
        args = SimpleNamespace(
            require_target_name="",
            prefer_target_name="eirebug,spraggon,large frog",
            objective_add_target_name="",
            avoid_target_name="",
            incoming_damage_melee_grace=4.0,
        )
        intent = behavior.target_intent_for_selected_npc(
            args,
            add,
            selected_npc_is_rescue=False,
            behavior_state=behavior.DummyBehaviorState.ReturnToObjective,
        )

        self.assertEqual(intent, behavior.TargetIntent.travel_aggro)
        self.assertTrue(
            behavior.should_suppress_passive_travel_target(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                add,
                intent,
                current_target=0,
                now=100.0,
                last_damage_taken_at=0.0,
            )
        )
        self.assertFalse(
            behavior.should_suppress_passive_travel_target(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                add,
                intent,
                current_target=add.object_id,
                now=100.0,
                last_damage_taken_at=0.0,
            )
        )

    def test_travel_state_allows_preferred_target_without_required_name(self):
        target = FakeNpc(21, "pine imp", 6, 140.0)
        args = SimpleNamespace(require_target_name="", prefer_target_name="pine imp")

        self.assertEqual(
            behavior.target_intent_for_selected_npc(
                args,
                target,
                selected_npc_is_rescue=False,
                behavior_state=behavior.DummyBehaviorState.TravelToObjective,
            ),
            behavior.TargetIntent.objective,
        )
        self.assertFalse(
            behavior.should_handle_travel_aggro_target(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                target,
                behavior.TargetIntent.objective,
            )
        )

    def test_travel_state_damage_from_non_preferred_add_without_required_name(self):
        args = SimpleNamespace(require_target_name="", prefer_target_name="pine imp")

        self.assertTrue(
            behavior.should_handle_travel_aggro_damage(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                "wood imp",
            )
        )
        self.assertFalse(
            behavior.should_handle_travel_aggro_damage(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                "pine imp",
            )
        )

    def test_travel_state_ignores_minor_low_level_add_damage_while_healthy(self):
        args = SimpleNamespace(
            require_target_name="Tylwyth Teg ranger",
            player_level=50,
            flee_pressure_health_percent=85,
            travel_aggro_ignore_low_level_delta=8,
            travel_aggro_minor_health_drop_percent=5,
        )

        self.assertFalse(
            behavior.should_handle_travel_aggro_damage(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                "arawnite headhunter",
                attacker_level=39,
                player_level=50,
                health_percent=97,
                previous_health_percent=100,
            )
        )
        self.assertTrue(
            behavior.should_handle_travel_aggro_damage(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                "arawnite headhunter",
                attacker_level=47,
                player_level=50,
                health_percent=97,
                previous_health_percent=100,
            )
        )
        self.assertTrue(
            behavior.should_handle_travel_aggro_damage(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                "arawnite headhunter",
                attacker_level=39,
                player_level=50,
                health_percent=84,
                previous_health_percent=90,
            )
        )

    def test_party_rescue_ignores_trivial_low_level_non_objective_adds(self):
        args = SimpleNamespace(
            require_target_name="Tylwyth Teg ranger",
            objective_add_target_name="",
            player_level=50,
            party_rescue_ignore_low_level_delta=8,
            party_encounter_mode="boss",
        )

        self.assertFalse(behavior.should_accept_party_rescue_target(args, FakeNpc(31, "arawnite headhunter", 39, 150.0)))
        self.assertTrue(behavior.should_accept_party_rescue_target(args, FakeNpc(32, "arawnite headhunter", 47, 150.0)))
        self.assertTrue(behavior.should_accept_party_rescue_target(args, FakeNpc(33, "Tylwyth Teg ranger", 47, 150.0)))

    def test_travel_state_allows_required_target_retaliation(self):
        required = FakeNpc(21, "icestrider interceptor", 47, 140.0)
        args = SimpleNamespace(require_target_name="icestrider interceptor")

        self.assertEqual(
            behavior.target_intent_for_selected_npc(
                args,
                required,
                selected_npc_is_rescue=True,
                behavior_state=behavior.DummyBehaviorState.HandleTravelAggro,
                recent_incoming_attacker_name="icestrider interceptor",
            ),
            behavior.TargetIntent.required_retaliation,
        )
        self.assertFalse(
            behavior.should_handle_travel_aggro_target(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required,
                behavior.TargetIntent.required_retaliation,
            )
        )

    def test_travel_state_allows_configured_objective_add_retaliation(self):
        add = FakeNpc(20, "fenrir snowscout", 41, 300.0)
        args = SimpleNamespace(
            require_target_name="fenrir tracker",
            objective_add_target_name="fenrir snowscout,fenrir prophet",
        )

        self.assertFalse(
            behavior.should_handle_travel_aggro_damage(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                "fenrir snowscout",
            )
        )
        self.assertFalse(
            behavior.should_handle_travel_aggro_target(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                add,
                behavior.TargetIntent.party_rescue,
            )
        )
        self.assertTrue(behavior.npc_name_matches_party_objective_add(args, None, add))

    def test_configured_objective_add_rescue_bypasses_distance_before_objective_targeted(self):
        add = FakeNpc(20, "fenrir snowscout", 41, 2200.0)
        now = 100.0
        snapshot = {
            "leader_target_id": 0,
            "leader_target_x": 0,
            "leader_target_y": 0,
            "leader_target_engaged_at": 0.0,
            "active_tank_name": "GrowthMid4530",
            "rescue_tank_name": "GrowthMid4531",
            "rescue_member_name": "GrowthMid4530",
            "rescue_threats": [
                {"object_id": 20, "requested_at": now - 1.0, "objective_add": True, "member_name": "GrowthMid4530"},
            ],
            "members": [
                {"name": "GrowthMid4530", "role": "melee-basic", "health_percent": 100},
                {"name": "GrowthMid4531", "role": "melee-basic", "health_percent": 100},
            ],
        }
        args = SimpleNamespace(
            require_target_name="fenrir tracker",
            objective_add_target_name="fenrir snowscout,fenrir prophet",
            party_encounter_mode="standard",
            party_rescue_aggro=True,
            party_rescue_max_age=8.0,
            party_rescue_max_distance=1400.0,
            party_local_rescue_target=False,
            party_assist_rescue_target=False,
            party_rescue_assist_after=0.0,
            party_rescue_emergency_assist_after=0.0,
            party_caster_assist_rescue_target=False,
            party_preserve_target_on_loss=True,
            player_level=50,
            max_target_level=-1,
            max_target_level_delta=2,
        )

        self.assertTrue(behavior.is_combat_proven_party_objective_add(args, snapshot, add))
        selected = behavior.choose_party_rescue_threat_target(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            member_name="GrowthMid4530",
            action_rotation="melee-basic",
            health_percent=100,
            now=now,
        )

        self.assertEqual(selected.object_id, 20)

    def test_incoming_damage_counterattack_selects_configured_objective_add_immediately(self):
        add = FakeNpc(20, "fenrir snowscout", 41, 900.0)
        snapshot = {
            "leader_target_id": 0,
            "active_tank_name": "GrowthMid4530",
            "rescue_tank_name": "GrowthMid4531",
            "members": [
                {"name": "GrowthMid4530", "role": "melee-basic", "health_percent": 92},
                {"name": "GrowthMid4531", "role": "healer-support", "health_percent": 100},
            ],
        }
        args = SimpleNamespace(
            require_target_name="fenrir tracker",
            objective_add_target_name="fenrir snowscout,fenrir prophet",
            party_encounter_mode="standard",
            party_rescue_aggro=True,
            party_rescue_max_age=10.0,
            flee_melee_counterattack_health_floor=55,
            player_level=50,
            max_target_level=-1,
            max_target_level_delta=2,
        )

        selected = behavior.choose_incoming_damage_counterattack_target(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            member_name="GrowthMid4530",
            action_rotation="melee-basic",
            health_percent=92,
            attacker_name="fenrir snowscout",
            current_target=0,
            behavior_state=behavior.DummyBehaviorState.ReturnToObjective,
        )

        self.assertEqual(selected.object_id, 20)

    def test_incoming_damage_counterattack_skips_rejected_attacker(self):
        add = FakeNpc(20, "fenrir snowscout", 41, 900.0)
        snapshot = {
            "leader_target_id": 0,
            "active_tank_name": "GrowthMid4530",
            "rescue_tank_name": "GrowthMid4531",
            "members": [
                {"name": "GrowthMid4530", "role": "melee-basic", "health_percent": 92},
                {"name": "GrowthMid4531", "role": "healer-support", "health_percent": 100},
            ],
        }
        args = SimpleNamespace(
            require_target_name="fenrir tracker",
            objective_add_target_name="fenrir snowscout,fenrir prophet",
            party_encounter_mode="standard",
            party_rescue_aggro=True,
            party_rescue_max_age=10.0,
            flee_melee_counterattack_health_floor=55,
            player_level=50,
            max_target_level=-1,
            max_target_level_delta=2,
        )

        selected = behavior.choose_incoming_damage_counterattack_target(
            [add],
            FakeClient(npcs=[add]),
            args,
            snapshot,
            member_name="GrowthMid4530",
            action_rotation="melee-basic",
            health_percent=92,
            attacker_name="fenrir snowscout",
            current_target=0,
            behavior_state=behavior.DummyBehaviorState.ReturnToObjective,
            rejected_targets={20: 200.0},
            now=100.0,
        )

        self.assertIsNone(selected)

    def test_incoming_damage_counterattack_ignores_required_attacker_outside_home_limit(self):
        attacker = FakeNpc(10289, "spindly rock crab", 9, 5522.0)
        attacker.x = 777136
        attacker.y = 837296
        client = FakeClient(npcs=[attacker])
        client.x = 772594
        client.y = 834154
        snapshot = {
            "leader_target_id": 0,
            "active_tank_name": "GrowthMid1340",
            "rescue_tank_name": "GrowthMid1340",
            "members": [{"name": "GrowthMid1340", "role": "melee-basic", "health_percent": 85}],
        }
        args = SimpleNamespace(
            require_target_name="spindly rock crab",
            objective_add_target_name="",
            party_encounter_mode="standard",
            party_rescue_aggro=True,
            party_rescue_max_age=10.0,
            flee_melee_counterattack_health_floor=55,
            player_level=10,
            max_target_level=9,
            max_target_level_delta=0,
            max_target_distance=1500.0,
            required_target_home=SimpleNamespace(x=772717, y=833982, z=4348),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=1800.0,
            target_home_max_distance=1400.0,
        )

        selected = behavior.choose_incoming_damage_counterattack_target(
            [attacker],
            client,
            args,
            snapshot,
            member_name="GrowthMid1340",
            action_rotation="melee-basic",
            health_percent=85,
            attacker_name="spindly rock crab",
            current_target=0,
            behavior_state=behavior.DummyBehaviorState.HuntObjective,
        )

        self.assertIsNone(selected)

    def test_incoming_damage_counterattack_ignores_required_attacker_outside_combat_leash(self):
        attacker = FakeNpc(18029, "spindly rock crab", 9, 4397.0)
        attacker.x = 777338
        attacker.y = 837934
        client = FakeClient(npcs=[attacker])
        client.x = 773767
        client.y = 835368
        snapshot = {
            "leader_target_id": 0,
            "active_tank_name": "GrowthMid1340",
            "rescue_tank_name": "GrowthMid1340",
            "members": [{"name": "GrowthMid1340", "role": "melee-basic", "health_percent": 65}],
        }
        args = SimpleNamespace(
            require_target_name="spindly rock crab",
            objective_add_target_name="",
            party_encounter_mode="standard",
            party_rescue_aggro=True,
            party_rescue_max_age=10.0,
            flee_melee_counterattack_health_floor=55,
            player_level=10,
            max_target_level=9,
            max_target_level_delta=0,
            max_target_distance=6000.0,
            required_target_home=SimpleNamespace(x=772717, y=833982, z=4348),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=1800.0,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=1800.0,
        )

        selected = behavior.choose_incoming_damage_counterattack_target(
            [attacker],
            client,
            args,
            snapshot,
            member_name="GrowthMid1340",
            action_rotation="melee-basic",
            health_percent=65,
            attacker_name="spindly rock crab",
            current_target=0,
            behavior_state=behavior.DummyBehaviorState.TravelToObjective,
        )

        self.assertIsNone(selected)

    def test_exact_rescue_threat_ignores_required_attacker_outside_combat_leash(self):
        attacker = FakeNpc(18029, "spindly rock crab", 9, 4397.0)
        attacker.x = 777338
        attacker.y = 837934
        client = FakeClient(npcs=[attacker])
        client.x = 773767
        client.y = 835368
        party_state = behavior.PartyState("GrowthMid1340", ["GrowthMid1340", "GrowthMid1341"])
        args = SimpleNamespace(
            npc_max_age=60.0,
            require_target_name="spindly rock crab",
            objective_add_target_name="",
            party_encounter_mode="standard",
            party_rescue_min_hold=0.0,
            player_level=10,
            max_target_level=9,
            max_target_level_delta=0,
            max_target_distance=6000.0,
            required_target_home=SimpleNamespace(x=772717, y=833982, z=4348),
            required_target_home_stop_distance=900.0,
            required_target_home_hunt_distance=1800.0,
            target_home_max_distance=6200.0,
            combat_home_leash_distance=1800.0,
        )

        recorded = behavior.refresh_exact_rescue_threat_from_attacker_name(
            party_state,
            client,
            args,
            "GrowthMid1340",
            "spindly rock crab",
        )

        self.assertFalse(recorded)
        self.assertEqual(party_state.snapshot()["rescue_target_id"], 0)

    def test_fsm_policy_blocks_hostile_commit_in_recovery_states(self):
        self.assertFalse(behavior.can_select_hostile_target(behavior.DummyBehaviorState.DropAggroAndRecover))
        self.assertFalse(behavior.can_select_hostile_target(behavior.DummyBehaviorState.RestRecover))
        self.assertFalse(behavior.can_select_hostile_target(behavior.DummyBehaviorState.DeadReleaseRecover))
        self.assertTrue(behavior.can_select_hostile_target(behavior.DummyBehaviorState.HuntObjective))

    def test_fsm_policy_blocks_party_assist_outside_hunt(self):
        self.assertFalse(behavior.can_party_assist(behavior.DummyBehaviorState.RestRecover))
        self.assertFalse(behavior.can_party_assist(behavior.DummyBehaviorState.DropAggroAndRecover))
        self.assertFalse(behavior.can_party_assist(behavior.DummyBehaviorState.TravelToObjective))
        self.assertTrue(behavior.can_party_assist(behavior.DummyBehaviorState.HuntObjective))

    def test_fsm_policy_ignores_non_objective_targets_while_traveling(self):
        self.assertTrue(
            behavior.should_ignore_non_objective_target(
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.travel_aggro,
            )
        )
        self.assertTrue(
            behavior.should_ignore_non_objective_target(
                behavior.DummyBehaviorState.ReturnToObjective,
                behavior.TargetIntent.avoided_add,
            )
        )
        self.assertFalse(
            behavior.should_ignore_non_objective_target(
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.required_retaliation,
            )
        )
        self.assertFalse(
            behavior.should_ignore_non_objective_target(
                behavior.DummyBehaviorState.HuntObjective,
                behavior.TargetIntent.travel_aggro,
            )
        )

    def test_fsm_policy_allows_flee_refresh_only_in_live_states(self):
        self.assertFalse(behavior.can_start_or_refresh_flee(behavior.DummyBehaviorState.Startup))
        self.assertFalse(behavior.can_start_or_refresh_flee(behavior.DummyBehaviorState.DeadReleaseRecover))
        self.assertTrue(behavior.can_start_or_refresh_flee(behavior.DummyBehaviorState.TravelToObjective))
        self.assertTrue(behavior.can_start_or_refresh_flee(behavior.DummyBehaviorState.DropAggroAndRecover))

    def test_safe_exit_extends_round_while_dropping_aggro(self):
        args = SimpleNamespace(
            safe_exit_max_seconds=90.0,
            safe_exit_recent_damage_grace=12.0,
            low_health_rest_resume_percent=88,
        )

        self.assertTrue(
            behavior.should_extend_round_for_safe_exit(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                now=105.0,
                end_time=100.0,
                safe_exit_deadline=190.0,
                health_percent=69,
                current_target=0,
                last_damage_taken_at=99.0,
                last_incoming_damage_at=99.0,
                flee_until=130.0,
                rest_until=0.0,
            )
        )

    def test_safe_exit_allows_round_to_end_after_recovery_clear(self):
        args = SimpleNamespace(
            safe_exit_max_seconds=90.0,
            safe_exit_recent_damage_grace=12.0,
            low_health_rest_resume_percent=88,
        )

        self.assertFalse(
            behavior.should_extend_round_for_safe_exit(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                now=140.0,
                end_time=100.0,
                safe_exit_deadline=190.0,
                health_percent=95,
                current_target=0,
                last_damage_taken_at=100.0,
                last_incoming_damage_at=100.0,
                flee_until=120.0,
                rest_until=0.0,
            )
        )

    def test_safe_exit_stops_extending_at_deadline(self):
        args = SimpleNamespace(
            safe_exit_max_seconds=90.0,
            safe_exit_recent_damage_grace=12.0,
            low_health_rest_resume_percent=88,
        )

        self.assertFalse(
            behavior.should_extend_round_for_safe_exit(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                now=190.0,
                end_time=100.0,
                safe_exit_deadline=190.0,
                health_percent=69,
                current_target=0,
                last_damage_taken_at=189.0,
                last_incoming_damage_at=189.0,
                flee_until=220.0,
                rest_until=0.0,
            )
        )

    def test_safe_exit_deadline_refreshes_after_post_end_target_removed(self):
        args = SimpleNamespace(safe_exit_max_seconds=90.0)

        self.assertEqual(
            behavior.refresh_safe_exit_deadline_after_target_removed(
                args,
                safe_exit_active=True,
                safe_exit_deadline=190.0,
                now=150.0,
            ),
            240.0,
        )
        self.assertEqual(
            behavior.refresh_safe_exit_deadline_after_target_removed(
                args,
                safe_exit_active=False,
                safe_exit_deadline=190.0,
                now=150.0,
            ),
            190.0,
        )

    def test_safe_exit_deadline_refreshes_for_recovery_combat_outcome(self):
        args = SimpleNamespace(safe_exit_max_seconds=90.0)

        self.assertIn("flee", behavior.SAFE_EXIT_RECOVERY_COMBAT_OUTCOMES)
        self.assertEqual(
            behavior.refresh_safe_exit_deadline_for_recovery(
                args,
                safe_exit_active=True,
                safe_exit_deadline=190.0,
                now=150.0,
            ),
            240.0,
        )

    def test_safe_exit_deadline_can_complete_when_recovered_above_floor(self):
        args = SimpleNamespace(low_health_rest_percent=70, safe_exit_recent_damage_grace=12.0)

        self.assertTrue(
            behavior.safe_exit_deadline_can_complete_recovered(
                args,
                behavior.DummyBehaviorState.RestRecover,
                now=230.0,
                health_percent=86,
                current_target=0,
                flee_until=0.0,
                last_damage_taken_at=180.0,
                last_incoming_damage_at=180.0,
            )
        )
        self.assertFalse(
            behavior.safe_exit_deadline_can_complete_recovered(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                now=230.0,
                health_percent=86,
                current_target=0,
                flee_until=240.0,
                last_damage_taken_at=229.0,
                last_incoming_damage_at=229.0,
            )
        )

    def test_safe_exit_deadline_can_complete_while_safely_resting_below_floor(self):
        args = SimpleNamespace(low_health_rest_percent=70, safe_exit_recent_damage_grace=12.0)

        self.assertTrue(
            behavior.safe_exit_deadline_can_complete_recovered(
                args,
                behavior.DummyBehaviorState.RestRecover,
                now=230.0,
                health_percent=55,
                current_target=0,
                flee_until=0.0,
                last_damage_taken_at=180.0,
                last_incoming_damage_at=180.0,
                rest_until=260.0,
            )
        )

    def test_safe_exit_drops_new_damage_instead_of_starting_new_fight(self):
        self.assertTrue(
            behavior.should_drop_new_damage_during_safe_exit(
                safe_exit_active=True,
                current_target=0,
                current_health_percent=80,
                previous_health_percent=86,
                last_damage_attacker_name="giant spider",
            )
        )
        self.assertFalse(
            behavior.should_drop_new_damage_during_safe_exit(
                safe_exit_active=False,
                current_target=0,
                current_health_percent=80,
                previous_health_percent=86,
                last_damage_attacker_name="giant spider",
            )
        )
        self.assertFalse(
            behavior.should_drop_new_damage_during_safe_exit(
                safe_exit_active=True,
                current_target=123,
                current_health_percent=80,
                previous_health_percent=86,
                last_damage_attacker_name="giant spider",
            )
        )

    def test_safe_exit_disengages_current_target_in_hunt_state(self):
        args = SimpleNamespace(
            safe_exit_disengage_current_target=True,
            safe_exit_recent_damage_grace=12.0,
            low_health_rest_resume_percent=88,
        )

        self.assertTrue(
            behavior.should_disengage_current_target_for_safe_exit(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                current_target=23268,
                health_percent=100,
                recent_damage_age_seconds=None,
            )
        )

    def test_safe_exit_disengage_policy_respects_recovery_state_and_flag(self):
        args = SimpleNamespace(
            safe_exit_disengage_current_target=True,
            safe_exit_recent_damage_grace=12.0,
            low_health_rest_resume_percent=88,
        )

        self.assertFalse(
            behavior.should_disengage_current_target_for_safe_exit(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                current_target=23268,
                health_percent=100,
                recent_damage_age_seconds=1.0,
            )
        )

        args.safe_exit_disengage_current_target = False
        self.assertFalse(
            behavior.should_disengage_current_target_for_safe_exit(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                current_target=23268,
                health_percent=100,
                recent_damage_age_seconds=1.0,
            )
        )

    def test_recent_safe_exit_damage_age_uses_latest_damage_source(self):
        self.assertEqual(
            behavior.recent_safe_exit_damage_age(
                now=120.0,
                last_damage_taken_at=100.0,
                last_incoming_damage_at=115.0,
            ),
            5.0,
        )
        self.assertIsNone(
            behavior.recent_safe_exit_damage_age(
                now=120.0,
                last_damage_taken_at=0.0,
                last_incoming_damage_at=0.0,
            )
        )

    def test_fsm_policy_objective_pressure_interrupt_respects_recovery_floor(self):
        args = SimpleNamespace(
            required_target_tank_commit_health_percent=55,
            low_health_rest_resume_percent=88,
        )
        context = SimpleNamespace(required_home_hunt_ready=True)

        self.assertFalse(
            behavior.can_objective_pressure_interrupt(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                57,
                context,
                args,
            )
        )
        self.assertTrue(
            behavior.can_objective_pressure_interrupt(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                88,
                context,
                args,
            )
        )

    def test_flee_plan_blocks_lower_priority_home_while_pressure_locked(self):
        plan = behavior.FleePlan(priority=80, reason="recent_damage", locked_until=130.0)

        self.assertFalse(
            behavior.should_replace_flee_plan(
                plan,
                now=120.0,
                priority=20,
            )
        )
        self.assertTrue(
            behavior.should_replace_flee_plan(
                plan,
                now=120.0,
                priority=100,
            )
        )
        self.assertFalse(
            behavior.should_replace_flee_plan(
                behavior.FleePlan(priority=100, reason="recent_damage", locked_until=130.0),
                now=120.0,
                priority=100,
            )
        )
        self.assertTrue(
            behavior.should_replace_flee_plan(
                plan,
                now=131.0,
                priority=20,
            )
        )

    def test_flee_damage_replan_priority_escalates_at_critical_health(self):
        args = SimpleNamespace(flee_critical_health_percent=45)

        self.assertEqual(behavior.flee_damage_replan_priority(args, 70), 100)
        self.assertEqual(behavior.flee_damage_replan_priority(args, 45), 120)
        self.assertEqual(behavior.flee_damage_replan_priority(args, 0), 100)

    def test_drop_aggro_state_blocks_non_objective_target_reengage(self):
        add = FakeNpc(20, "wyvern", 39, 300.0)
        args = SimpleNamespace(require_target_name="icestrider interceptor")

        self.assertFalse(
            behavior.should_allow_target_selection_for_behavior_state(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                args,
                add,
                behavior.TargetIntent.travel_aggro,
            )
        )

    def test_drop_aggro_state_blocks_required_target_reengage_until_recovered(self):
        target = FakeNpc(20, "icestrider interceptor", 39, 300.0)
        args = SimpleNamespace(require_target_name="icestrider interceptor")

        self.assertFalse(
            behavior.should_allow_target_selection_for_behavior_state(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                args,
                target,
                behavior.TargetIntent.objective,
            )
        )
        self.assertFalse(
            behavior.should_allow_counterattack_for_behavior_state(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                args,
                target,
                behavior.TargetIntent.required_retaliation,
            )
        )

    def test_required_objective_pressure_can_interrupt_drop_aggro_at_hunt_area(self):
        target = FakeNpc(20, "moorlich", 48, 300.0)
        args = SimpleNamespace(
            require_target_name="moorlich",
            required_target_tank_commit_health_percent=55,
        )

        self.assertTrue(
            behavior.should_interrupt_drop_aggro_for_required_objective_pressure(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                target,
                behavior.TargetIntent.objective,
                current_health_percent=92,
                required_home_hunt_ready=True,
            )
        )

    def test_required_objective_pressure_interrupt_waits_for_recovery_floor(self):
        target = FakeNpc(20, "moorlich", 48, 300.0)
        args = SimpleNamespace(
            require_target_name="moorlich",
            required_target_tank_commit_health_percent=55,
            low_health_rest_resume_percent=88,
        )

        self.assertFalse(
            behavior.should_interrupt_drop_aggro_for_required_objective_pressure(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                target,
                behavior.TargetIntent.required_retaliation,
                current_health_percent=57,
                required_home_hunt_ready=True,
            )
        )
        self.assertTrue(
            behavior.should_interrupt_drop_aggro_for_required_objective_pressure(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                target,
                behavior.TargetIntent.required_retaliation,
                current_health_percent=88,
                required_home_hunt_ready=True,
            )
        )

    def test_required_objective_pressure_interrupt_keeps_floor_and_name_gate(self):
        target = FakeNpc(20, "moorlich", 48, 300.0)
        add = FakeNpc(21, "lesser telamon", 48, 300.0)
        args = SimpleNamespace(
            require_target_name="moorlich",
            required_target_tank_commit_health_percent=55,
        )

        self.assertFalse(
            behavior.should_interrupt_drop_aggro_for_required_objective_pressure(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                target,
                behavior.TargetIntent.objective,
                current_health_percent=55,
                required_home_hunt_ready=True,
            )
        )
        self.assertFalse(
            behavior.should_interrupt_drop_aggro_for_required_objective_pressure(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                add,
                behavior.TargetIntent.party_rescue,
                current_health_percent=92,
                required_home_hunt_ready=True,
            )
        )

    def test_rest_recover_state_blocks_objective_target_selection_until_recovered(self):
        target = FakeNpc(20, "icestrider interceptor", 39, 300.0)
        args = SimpleNamespace(require_target_name="icestrider interceptor")

        self.assertFalse(
            behavior.should_allow_target_selection_for_behavior_state(
                behavior.DummyBehaviorState.RestRecover,
                args,
                target,
                behavior.TargetIntent.objective,
            )
        )

    def test_rest_recover_state_blocks_untracked_damage_counterattack(self):
        self.assertFalse(
            behavior.should_allow_untracked_damage_counterattack(
                behavior.DummyBehaviorState.RestRecover,
                flee_until=0.0,
                now=100.0,
            )
        )

    def test_drop_aggro_state_blocks_party_rescue_counterattack(self):
        add = FakeNpc(20, "wyvern", 39, 300.0)
        args = SimpleNamespace(require_target_name="icestrider interceptor")

        self.assertFalse(
            behavior.should_allow_counterattack_for_behavior_state(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                args,
                add,
                behavior.TargetIntent.party_rescue,
            )
        )

    def test_drop_aggro_state_blocks_party_assist(self):
        self.assertFalse(
            behavior.should_allow_party_assist_for_behavior_state(
                behavior.DummyBehaviorState.DropAggroAndRecover
            )
        )
        self.assertTrue(
            behavior.should_allow_party_assist_for_behavior_state(
                behavior.DummyBehaviorState.HuntObjective
            )
        )

    def _engagement_context(self, *, state=behavior.DummyBehaviorState.HuntObjective, **overrides):
        values = {
            "behavior_state": state,
            "current_target": 0,
            "current_target_intent": behavior.TargetIntent.none,
            "is_party_leader": False,
            "is_party_follower": False,
            "party_ready": True,
            "leader_engaged": False,
            "current_health_percent": 100,
            "objective_home_reached": True,
            "objective_hunt_ready": True,
            "drop_aggro_active": state == behavior.DummyBehaviorState.DropAggroAndRecover,
            "rest_active": False,
            "flee_active": False,
        }
        values.update(overrides)
        return behavior.EngagementContext(**values)

    def _engagement_candidate(self, npc, *, source, intent):
        return behavior.EngagementCandidate(
            object_id=npc.object_id,
            name=npc.name,
            level=npc.level,
            x=npc.x,
            y=npc.y,
            z=npc.z,
            source=source,
            intent=intent,
            npc=npc,
        )

    def test_required_target_api_publish_candidate_uses_engagement_gate(self):
        npc = FakeNpc(298, "moorlich", 48, 300.0)
        args = SimpleNamespace(require_target_name="moorlich", max_target_distance=1500.0)
        client = FakeClient(npcs=[npc])

        drop_decision = behavior.evaluate_required_target_api_observation(
            args,
            npc,
            self._engagement_context(state=behavior.DummyBehaviorState.DropAggroAndRecover),
            client,
            {},
        )
        self.assertFalse(drop_decision.allowed)
        self.assertEqual(drop_decision.reject_reason, "drop_aggro_active")

        flee_decision = behavior.evaluate_required_target_api_observation(
            args,
            npc,
            self._engagement_context(flee_active=True),
            client,
            {},
        )
        self.assertFalse(flee_decision.allowed)
        self.assertEqual(flee_decision.reject_reason, "flee_active")

        allowed_decision = behavior.evaluate_required_target_api_observation(
            args,
            npc,
            self._engagement_context(state=behavior.DummyBehaviorState.HuntObjective),
            client,
            {},
        )
        self.assertTrue(allowed_decision.allowed)
        self.assertEqual(allowed_decision.source, behavior.TargetSource.current_target_api_refresh)
        self.assertEqual(allowed_decision.intent, behavior.TargetIntent.required_retaliation)

    def test_objective_pressure_interrupt_candidate_evaluates_before_clearing_recovery(self):
        npc = FakeNpc(299, "moorlich", 48, 300.0)
        args = SimpleNamespace(
            require_target_name="moorlich",
            max_target_distance=1500.0,
            required_target_tank_commit_health_percent=55,
            low_health_rest_resume_percent=88,
        )
        client = FakeClient(npcs=[npc])

        below_floor = behavior.evaluate_objective_pressure_interrupt_candidate(
            args,
            npc,
            source=behavior.TargetSource.required_retaliation,
            intent=behavior.TargetIntent.required_retaliation,
            current_health_percent=57,
            required_home_hunt_ready=True,
            context=self._engagement_context(
                state=behavior.DummyBehaviorState.DropAggroAndRecover,
                flee_active=True,
            ),
            client=client,
            party_snapshot={},
        )
        self.assertIsNone(below_floor)

        allowed = behavior.evaluate_objective_pressure_interrupt_candidate(
            args,
            npc,
            source=behavior.TargetSource.required_retaliation,
            intent=behavior.TargetIntent.required_retaliation,
            current_health_percent=90,
            required_home_hunt_ready=True,
            context=self._engagement_context(
                state=behavior.DummyBehaviorState.DropAggroAndRecover,
                flee_active=True,
            ),
            client=client,
            party_snapshot={},
        )
        self.assertIsNotNone(allowed)
        self.assertTrue(allowed.allowed)

    def test_objective_pressure_interrupt_candidate_still_respects_target_gate(self):
        npc = FakeNpc(300, "moorlich", 48, 300.0)
        npc.x = 2200
        npc.y = 0
        args = SimpleNamespace(
            require_target_name="moorlich",
            max_target_distance=5000.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=5000.0,
            combat_home_leash_distance=500.0,
            required_target_tank_commit_health_percent=55,
            low_health_rest_resume_percent=88,
        )
        decision = behavior.evaluate_objective_pressure_interrupt_candidate(
            args,
            npc,
            source=behavior.TargetSource.required_retaliation,
            intent=behavior.TargetIntent.required_retaliation,
            current_health_percent=90,
            required_home_hunt_ready=True,
            context=self._engagement_context(state=behavior.DummyBehaviorState.DropAggroAndRecover),
            client=FakeClient(npcs=[npc]),
            party_snapshot={},
        )

        self.assertIsNotNone(decision)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "combat_home_leash")

    def test_preserve_committed_hostile_target_blocks_recovery_and_travel_adds(self):
        self.assertFalse(
            behavior.can_preserve_committed_hostile_target(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                behavior.TargetIntent.objective,
            )
        )
        self.assertFalse(
            behavior.can_preserve_committed_hostile_target(
                behavior.DummyBehaviorState.HuntObjective,
                behavior.TargetIntent.objective,
                flee_active=True,
            )
        )
        self.assertFalse(
            behavior.can_preserve_committed_hostile_target(
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.travel_aggro,
            )
        )
        self.assertTrue(
            behavior.can_preserve_committed_hostile_target(
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.objective,
            )
        )

    def test_attack_mode_policy_blocks_recovery_and_travel_adds(self):
        self.assertFalse(
            behavior.can_enable_hostile_attack_mode(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                410,
                behavior.TargetIntent.objective,
            )
        )
        self.assertFalse(
            behavior.can_enable_hostile_attack_mode(
                behavior.DummyBehaviorState.RestRecover,
                410,
                behavior.TargetIntent.objective,
            )
        )
        self.assertFalse(
            behavior.can_enable_hostile_attack_mode(
                behavior.DummyBehaviorState.HuntObjective,
                410,
                behavior.TargetIntent.objective,
                flee_active=True,
            )
        )
        self.assertFalse(
            behavior.can_enable_hostile_attack_mode(
                behavior.DummyBehaviorState.TravelToObjective,
                410,
                behavior.TargetIntent.travel_aggro,
            )
        )
        self.assertTrue(
            behavior.can_enable_hostile_attack_mode(
                behavior.DummyBehaviorState.HuntObjective,
                410,
                behavior.TargetIntent.objective,
            )
        )

    def test_attack_mode_policy_requires_committed_target(self):
        self.assertFalse(
            behavior.can_enable_hostile_attack_mode(
                behavior.DummyBehaviorState.HuntObjective,
                0,
                behavior.TargetIntent.objective,
            )
        )

    def test_friendly_cast_restore_uses_hostile_target_policy_helper(self):
        source = Path(behavior.__file__).read_text(encoding="utf-8")
        direct_lines = [
            line_number
            for line_number, line in enumerate(source.splitlines(), start=1)
            if "client.target_object(friendly_cast_restore_target)" in line
        ]
        restore_block_start = source.find("if friendly_cast_restore_target:")
        restore_block = source[restore_block_start : restore_block_start + 420]

        self.assertEqual([], direct_lines)
        self.assertIn("target_current_hostile_if_allowed(", restore_block)
        self.assertIn('"friendly_cast_retarget_enemy"', restore_block)
        self.assertIn("target_id=friendly_cast_restore_target", restore_block)

    def test_party_leader_engaged_marking_uses_single_helper(self):
        source = Path(behavior.__file__).read_text(encoding="utf-8")
        direct_calls = [
            (line_number, line.strip())
            for line_number, line in enumerate(source.splitlines(), start=1)
            if ".mark_leader_target_engaged(" in line
        ]

        self.assertEqual(
            ["party_state.mark_leader_target_engaged(target_id)"],
            [line for _line_number, line in direct_calls],
        )

    def test_flee_move_cadence_uses_single_scheduler_helper(self):
        source = Path(behavior.__file__).read_text(encoding="utf-8")
        direct_reschedules = [
            line_number
            for line_number, line in enumerate(source.splitlines(), start=1)
            if "next_flee_move = now + args.flee_move_interval" in line
        ]

        self.assertEqual([], direct_reschedules)
        self.assertIn("def schedule_next_flee_move(", source)

    def test_hostile_intent_refresh_uses_single_helper(self):
        source = Path(behavior.__file__).read_text(encoding="utf-8")

        self.assertNotIn("current_target_intent = observed_intent", source)
        self.assertNotIn("current_target_intent = selected_target_decision.intent", source)
        self.assertNotIn("current_target_intent = TargetIntent.required_retaliation", source)
        self.assertIn("def refresh_committed_current_target_intent(", source)

    def test_drop_aggro_grace_uses_flee_until_mutator(self):
        source = Path(behavior.__file__).read_text(encoding="utf-8")
        hold_start = source.find("def hold_flee_for_drop_aggro_clear_grace(")
        hold_end = source.find("def clear_shared_leader_target_on_abandon(", hold_start)
        hold_block = source[hold_start:hold_end]

        self.assertIn("def extend_flee_until_for_clear_grace(", source)
        self.assertIn("extend_flee_until_for_clear_grace(", hold_block)
        self.assertNotIn("flee_until = max(flee_until, hold_until)", hold_block)

    def test_commit_target_publishes_shared_target_only_through_allowed_decision(self):
        npc = FakeNpc(411, "moorlich", 48, 300.0)
        args = SimpleNamespace(require_target_name="moorlich", max_target_distance=1500.0)
        client = FakeClient(npcs=[npc])
        party = behavior.PartyState("leader", ["leader", "follower"])
        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.current_target_preserve,
                intent=behavior.TargetIntent.required_retaliation,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.HuntObjective,
                is_party_follower=True,
            ),
            client,
            args,
            {},
        )

        result = behavior.commit_target(
            behavior.party_shared_target_publish_decision(decision, engaged=True),
            client,
            party,
            now=12.5,
            current_target=0,
            current_target_since=0.0,
            current_target_last_visible_at=0.0,
            current_target_intent=behavior.TargetIntent.none,
        )

        snapshot = party.snapshot()
        self.assertTrue(result.party_shared_target_published)
        self.assertFalse(result.target_object_called)
        self.assertFalse(result.current_target_updated)
        self.assertEqual(result.current_target, 0)
        self.assertEqual(snapshot["leader_target_id"], 411)
        self.assertGreater(snapshot["leader_target_engaged_at"], 0.0)

    def test_rejected_shared_target_decision_does_not_publish(self):
        npc = FakeNpc(412, "wintery dirge", 11, 300.0)
        args = SimpleNamespace(require_target_name="moorlich", max_target_distance=1500.0)
        client = FakeClient(npcs=[npc])
        party = behavior.PartyState("leader", ["leader", "follower"])
        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.current_target_preserve,
                intent=behavior.TargetIntent.travel_aggro,
            ),
            self._engagement_context(state=behavior.DummyBehaviorState.DropAggroAndRecover),
            client,
            args,
            {},
        )

        result = behavior.commit_target(
            behavior.party_shared_target_publish_decision(decision, engaged=True),
            client,
            party,
            now=12.5,
            current_target=0,
            current_target_since=0.0,
            current_target_last_visible_at=0.0,
            current_target_intent=behavior.TargetIntent.none,
        )

        self.assertFalse(result.party_shared_target_published)
        self.assertEqual(party.snapshot()["leader_target_id"], 0)

    def test_last_known_shared_target_preserve_respects_fsm_gate(self):
        snapshot = {"leader_target_id": 410}

        self.assertFalse(
            behavior.should_chase_last_known_shared_target(
                snapshot,
                current_target=410,
                tactical_backoff=False,
                behavior_state=behavior.DummyBehaviorState.RestRecover,
                current_target_intent=behavior.TargetIntent.objective,
            )
        )
        self.assertFalse(
            behavior.should_chase_last_known_shared_target(
                snapshot,
                current_target=410,
                tactical_backoff=False,
                behavior_state=behavior.DummyBehaviorState.TravelToObjective,
                current_target_intent=behavior.TargetIntent.travel_aggro,
            )
        )
        self.assertTrue(
            behavior.should_chase_last_known_shared_target(
                snapshot,
                current_target=410,
                tactical_backoff=False,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                current_target_intent=behavior.TargetIntent.objective,
            )
        )

    def test_engagement_gate_rejects_candidate_outside_combat_home_leash(self):
        npc = FakeNpc(301, "spindly rock crab", 9, 900.0)
        npc.x = 2200
        npc.y = 0
        client = FakeClient(npcs=[npc])
        args = SimpleNamespace(
            max_target_distance=5000.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=5000.0,
            combat_home_leash_distance=500.0,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.hunter_selection,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(),
            client,
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "combat_home_leash")

    def test_party_assist_only_follower_rejects_own_hunter_selection_quietly(self):
        npc = FakeNpc(300, "giant boar", 35, 300.0)
        args = SimpleNamespace(party_assist_only=True, max_target_distance=1500.0)
        client = FakeClient(npcs=[npc])

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.hunter_selection,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(is_party_follower=True),
            client,
            args,
            {},
        )
        events = []
        action_counts = {}

        result = behavior.commit_target(
            decision,
            client,
            None,
            now=12.5,
            current_target=0,
            current_target_since=0.0,
            current_target_last_visible_at=0.0,
            current_target_intent=behavior.TargetIntent.none,
            action_counts=action_counts,
            log_event=lambda *event: events.append(event),
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "party_assist_only")
        self.assertFalse(result.current_target_updated)
        self.assertEqual(action_counts, {})
        self.assertEqual(events, [])

    def test_engagement_gate_rejects_travel_non_objective_damage_candidate(self):
        npc = FakeNpc(302, "wintery dirge", 11, 350.0)
        args = SimpleNamespace(require_target_name="spindly rock crab", max_target_distance=1500.0)

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.incoming_damage_counterattack,
                intent=behavior.TargetIntent.travel_aggro,
            ),
            self._engagement_context(state=behavior.DummyBehaviorState.TravelToObjective),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "travel_non_objective")

    def test_engagement_gate_rejects_engaged_party_assist_during_travel(self):
        npc = FakeNpc(332, "fenrir snowscout", 37, 350.0)
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            party_require_leader_engaged=True,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_assist,
                intent=behavior.TargetIntent.party_assist,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                party_ready=True,
                leader_engaged=True,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "state_blocks_party_assist")

    def test_engagement_gate_allows_engaged_leader_objective_assist_chase(self):
        npc = FakeNpc(333, "shady pilferer", 5, 3600.0)
        npc.x = 1000
        npc.y = 1000
        client = FakeClient(npcs=[npc])
        client.x = 1000
        client.y = 1000
        args = SimpleNamespace(
            min_target_level=5,
            max_target_level=6,
            player_level=5,
            max_target_level_delta=1,
            max_target_distance=2800.0,
            party_require_leader_engaged=True,
            party_encounter_mode="standard",
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            target_home_max_distance=6200.0,
            combat_home_leash_distance=6200.0,
            require_target_name="",
            prefer_target_name="shady pilferer",
            avoid_target_name="",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_assist,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                is_party_follower=True,
                party_ready=False,
                leader_engaged=True,
                objective_home_reached=False,
                objective_hunt_ready=False,
            ),
            client,
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_rejects_leader_initial_objective_pull_before_home_ready(self):
        npc = FakeNpc(345, "far darrig", 48, 350.0)
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            party_require_leader_engaged=True,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.leader_target_reacquire,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                is_party_leader=True,
                party_ready=True,
                leader_engaged=False,
                objective_home_reached=False,
                objective_hunt_ready=False,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "objective_home_not_ready")

    def test_engagement_gate_allows_leader_objective_reacquire_during_travel_when_ready(self):
        npc = FakeNpc(346, "far darrig", 48, 350.0)
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            party_require_leader_engaged=True,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.leader_target_reacquire,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                is_party_leader=True,
                party_ready=True,
                leader_engaged=False,
                objective_home_reached=True,
                objective_hunt_ready=True,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertTrue(decision.allowed)
        self.assertTrue(decision.should_publish_party_leader_target)

    def test_engagement_gate_allows_ready_objective_party_assist_during_travel(self):
        npc = FakeNpc(347, "far darrig", 48, 350.0)
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            party_require_leader_engaged=True,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_assist,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                is_party_follower=True,
                party_ready=True,
                leader_engaged=True,
                objective_home_reached=True,
                objective_hunt_ready=True,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertTrue(decision.allowed)
        self.assertFalse(decision.should_publish_party_leader_target)

    def test_engagement_gate_allows_engaged_party_rescue_during_travel(self):
        npc = FakeNpc(333, "fenrir snowscout", 37, 350.0)
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            party_require_leader_engaged=True,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_rescue,
                intent=behavior.TargetIntent.party_rescue,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                party_ready=True,
                leader_engaged=True,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_allows_engaged_party_rescue_when_follower_trails_combat_home(self):
        npc = FakeNpc(334, "fenrir snowscout", 37, 350.0)
        npc.x = 400
        npc.y = 0
        client = FakeClient(npcs=[npc])
        client.x = 800
        client.y = 0
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=5000.0,
            combat_home_leash_distance=500.0,
            party_require_leader_engaged=True,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_rescue,
                intent=behavior.TargetIntent.party_rescue,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                party_ready=True,
                leader_engaged=True,
            ),
            client,
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_rejects_engaged_party_rescue_when_target_left_combat_home(self):
        npc = FakeNpc(335, "fenrir snowscout", 37, 350.0)
        npc.x = 700
        npc.y = 0
        client = FakeClient(npcs=[npc])
        client.x = 800
        client.y = 0
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=5000.0,
            combat_home_leash_distance=500.0,
            party_require_leader_engaged=True,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_rescue,
                intent=behavior.TargetIntent.party_rescue,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                party_ready=True,
                leader_engaged=True,
            ),
            client,
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "combat_home_leash")

    def test_engagement_gate_allows_engaged_party_rescue_objective_add_outside_target_home(self):
        npc = FakeNpc(336, "fenrir snowscout", 37, 350.0)
        npc.x = 700
        npc.y = 0
        client = FakeClient(npcs=[npc])
        client.x = 800
        client.y = 0
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=500.0,
            combat_home_leash_distance=1000.0,
            party_require_leader_engaged=True,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir snowscout",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_rescue,
                intent=behavior.TargetIntent.party_rescue,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                party_ready=True,
                leader_engaged=True,
            ),
            client,
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_allows_engaged_party_rescue_to_close_distance_inside_combat_home(self):
        npc = FakeNpc(339, "fenrir snowscout", 37, 2600.0)
        npc.x = 700
        npc.y = 0
        client = FakeClient(npcs=[npc])
        client.x = 2600
        client.y = 0
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=1000.0,
            combat_home_leash_distance=1000.0,
            party_require_leader_engaged=True,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir snowscout",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_rescue,
                intent=behavior.TargetIntent.party_rescue,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                party_ready=True,
                leader_engaged=True,
            ),
            client,
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_rejects_far_non_rescue_candidate_outside_max_distance(self):
        npc = FakeNpc(340, "wintery dirge", 11, 2600.0)
        args = SimpleNamespace(
            max_target_distance=1500.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=5000.0,
            combat_home_leash_distance=5000.0,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.hunter_selection,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "max_target_distance")

    def test_engagement_gate_allows_current_target_preserve_chase_outside_max_distance(self):
        npc = FakeNpc(341, "shady pilferer", 5, 3600.0)
        npc.x = 1000
        npc.y = 1000
        client = FakeClient(npcs=[npc])
        client.x = 1000
        client.y = 1000
        args = SimpleNamespace(
            min_target_level=5,
            max_target_level=8,
            player_level=5,
            max_target_level_delta=3,
            max_target_distance=2800.0,
            party_encounter_mode="standard",
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            target_home_max_distance=6200.0,
            combat_home_leash_distance=6200.0,
            require_target_name="",
            prefer_target_name="shady pilferer",
            avoid_target_name="young cutpurse",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.current_target_preserve,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.HuntObjective,
                current_target=341,
                current_target_intent=behavior.TargetIntent.objective,
                objective_home_reached=False,
                objective_hunt_ready=False,
            ),
            client,
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_allows_preferred_low_con_fallback_candidate(self):
        npc = FakeNpc(348, "rock imp", 4, 300.0)
        npc.x = 1000
        npc.y = 1000
        client = FakeClient(npcs=[npc])
        client.x = 1000
        client.y = 1000
        args = SimpleNamespace(
            min_target_level=5,
            max_target_level=5,
            player_level=6,
            max_target_level_delta=0,
            max_target_distance=2800.0,
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            target_home_max_distance=6200.0,
            combat_home_leash_distance=6200.0,
            require_target_name="",
            prefer_target_name="rock imp",
            avoid_target_name="",
            allow_preferred_low_con_fallback=True,
            preferred_low_con_min_level=4,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.hunter_selection,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(state=behavior.DummyBehaviorState.HuntObjective),
            client,
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_rejects_unpreferred_low_con_candidate(self):
        npc = FakeNpc(349, "worker ant", 4, 300.0)
        args = SimpleNamespace(
            min_target_level=5,
            max_target_level=5,
            player_level=6,
            max_target_level_delta=0,
            max_target_distance=2800.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=6200.0,
            combat_home_leash_distance=6200.0,
            require_target_name="",
            prefer_target_name="rock imp",
            avoid_target_name="",
            allow_preferred_low_con_fallback=True,
            preferred_low_con_min_level=4,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.hunter_selection,
                intent=behavior.TargetIntent.objective,
            ),
            self._engagement_context(state=behavior.DummyBehaviorState.HuntObjective),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "level_filter")

    def test_engagement_gate_allows_engaged_local_rescue_party_rescue_during_travel(self):
        npc = FakeNpc(337, "fenrir snowscout", 37, 350.0)
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            party_require_leader_engaged=True,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir snowscout",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.local_rescue,
                intent=behavior.TargetIntent.party_rescue,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                party_ready=True,
                leader_engaged=True,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_allows_engaged_local_rescue_required_retaliation_during_travel(self):
        npc = FakeNpc(338, "fenrir snowscout", 37, 350.0)
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            party_require_leader_engaged=True,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir snowscout",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.local_rescue,
                intent=behavior.TargetIntent.required_retaliation,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                party_ready=True,
                leader_engaged=True,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_allows_accepted_party_rescue_after_leader_target_clears(self):
        npc = FakeNpc(341, "fenrir snowscout", 37, 350.0)
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir snowscout",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_rescue,
                intent=behavior.TargetIntent.party_rescue,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.HuntObjective,
                party_ready=True,
                leader_engaged=False,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_allows_accepted_party_rescue_required_retaliation_after_leader_target_clears(self):
        npc = FakeNpc(342, "fenrir prophet", 37, 350.0)
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir prophet",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_rescue,
                intent=behavior.TargetIntent.required_retaliation,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.HuntObjective,
                party_ready=True,
                leader_engaged=False,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_rejects_unengaged_party_rescue_required_retaliation_outside_home(self):
        npc = FakeNpc(344, "fenrir snowscout", 37, 350.0)
        npc.x = 3800
        npc.y = 0
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=2800.0,
            combat_home_leash_distance=2800.0,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir snowscout",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_rescue,
                intent=behavior.TargetIntent.required_retaliation,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                party_ready=True,
                leader_engaged=False,
            ),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "target_home_max_distance")

    def test_engagement_gate_allows_accepted_party_rescue_when_follower_trails_combat_home(self):
        npc = FakeNpc(343, "fenrir snowscout", 37, 350.0)
        npc.x = 400
        npc.y = 0
        client = FakeClient(npcs=[npc])
        client.x = 800
        client.y = 0
        args = SimpleNamespace(
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            max_target_distance=1500.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=1000.0,
            combat_home_leash_distance=500.0,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir snowscout",
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.party_rescue,
                intent=behavior.TargetIntent.party_rescue,
            ),
            self._engagement_context(
                state=behavior.DummyBehaviorState.HuntObjective,
                party_ready=True,
                leader_engaged=False,
            ),
            client,
            args,
            {},
        )

        self.assertTrue(decision.allowed)

    def test_engagement_gate_rejects_drop_aggro_non_objective_candidate(self):
        npc = FakeNpc(303, "wyvern", 39, 300.0)
        args = SimpleNamespace(require_target_name="icestrider interceptor")

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.local_rescue,
                intent=behavior.TargetIntent.travel_aggro,
            ),
            self._engagement_context(state=behavior.DummyBehaviorState.DropAggroAndRecover),
            FakeClient(npcs=[npc]),
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "drop_aggro_active")

    def test_engagement_gate_rejects_required_target_outside_combat_home_leash(self):
        npc = FakeNpc(304, "spindly rock crab", 9, 900.0)
        npc.x = 2200
        npc.y = 0
        client = FakeClient(npcs=[npc])
        args = SimpleNamespace(
            require_target_name="spindly rock crab",
            max_target_distance=5000.0,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            target_home_max_distance=5000.0,
            combat_home_leash_distance=500.0,
        )

        decision = behavior.evaluate_engagement_candidate(
            self._engagement_candidate(
                npc,
                source=behavior.TargetSource.required_retaliation,
                intent=behavior.TargetIntent.required_retaliation,
            ),
            self._engagement_context(),
            client,
            args,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "combat_home_leash")

    def test_commit_target_updates_party_leader_only_after_allowed_decision(self):
        npc = FakeNpc(305, "spindly rock crab", 9, 200.0)
        candidate = self._engagement_candidate(
            npc,
            source=behavior.TargetSource.hunter_selection,
            intent=behavior.TargetIntent.objective,
        )
        client = SimpleNamespace(target_calls=[])
        client.target_object = lambda object_id, **kwargs: client.target_calls.append((object_id, kwargs)) or 0
        party_state = SimpleNamespace(update_calls=[])
        party_state.update_leader = lambda leader, target=None: party_state.update_calls.append(target)

        rejected = behavior.TargetDecision(
            allowed=False,
            candidate=candidate,
            intent=behavior.TargetIntent.objective,
            source=behavior.TargetSource.hunter_selection,
            priority=0,
            reject_reason="combat_home_leash",
            should_target_object=False,
            should_update_current_target=False,
            should_publish_party_leader_target=True,
            should_mark_leader_engaged=False,
        )
        behavior.commit_target(
            rejected,
            client,
            party_state,
            now=10.0,
            current_target=0,
            current_target_since=0.0,
            current_target_last_visible_at=0.0,
            current_target_intent=behavior.TargetIntent.none,
            action_counts={},
        )
        self.assertEqual(client.target_calls, [])
        self.assertEqual(party_state.update_calls, [])

        allowed = behavior.TargetDecision(
            allowed=True,
            candidate=candidate,
            intent=behavior.TargetIntent.objective,
            source=behavior.TargetSource.hunter_selection,
            priority=100,
            reject_reason="",
            should_target_object=True,
            should_update_current_target=True,
            should_publish_party_leader_target=True,
            should_mark_leader_engaged=False,
        )
        behavior.commit_target(
            allowed,
            client,
            party_state,
            now=11.0,
            current_target=0,
            current_target_since=0.0,
            current_target_last_visible_at=0.0,
            current_target_intent=behavior.TargetIntent.none,
            action_counts={},
        )

        self.assertEqual(client.target_calls[0][0], 305)
        self.assertEqual(party_state.update_calls[0].object_id, 305)

    def test_leader_current_target_republish_uses_commit_gate_without_retarget(self):
        npc = FakeNpc(307, "spindly rock crab", 9, 200.0)
        allowed = behavior.TargetDecision(
            allowed=True,
            candidate=self._engagement_candidate(
                npc,
                source=behavior.TargetSource.hunter_selection,
                intent=behavior.TargetIntent.objective,
            ),
            intent=behavior.TargetIntent.objective,
            source=behavior.TargetSource.hunter_selection,
            priority=100,
            reject_reason="",
            should_target_object=True,
            should_update_current_target=True,
            should_publish_party_leader_target=True,
            should_mark_leader_engaged=False,
        )

        republish = behavior.leader_current_target_republish_decision(allowed)

        self.assertTrue(republish.allowed)
        self.assertFalse(republish.should_target_object)
        self.assertFalse(republish.should_update_current_target)
        self.assertTrue(republish.should_publish_party_leader_target)

        client = SimpleNamespace(target_calls=[])
        client.target_object = lambda object_id, **kwargs: client.target_calls.append((object_id, kwargs)) or 0
        party_state = SimpleNamespace(update_calls=[])
        party_state.update_leader = lambda leader, target=None: party_state.update_calls.append(target)

        result = behavior.commit_target(
            republish,
            client,
            party_state,
            now=12.0,
            current_target=307,
            current_target_since=8.0,
            current_target_last_visible_at=9.0,
            current_target_intent=behavior.TargetIntent.objective,
            action_counts={},
        )

        self.assertEqual(client.target_calls, [])
        self.assertEqual(result.current_target, 307)
        self.assertEqual(result.current_target_since, 8.0)
        self.assertEqual(result.current_target_last_visible_at, 9.0)
        self.assertEqual(party_state.update_calls[0].object_id, 307)

    def test_friendly_heal_target_source_does_not_use_engagement_gate(self):
        self.assertFalse(behavior.should_use_engagement_gate_for_target_source("friendly_heal"))

    def test_rejected_target_decision_does_not_change_current_target(self):
        npc = FakeNpc(306, "wintery dirge", 11, 300.0)
        candidate = self._engagement_candidate(
            npc,
            source=behavior.TargetSource.incoming_damage_counterattack,
            intent=behavior.TargetIntent.travel_aggro,
        )
        client = SimpleNamespace(target_calls=[])
        client.target_object = lambda object_id, **kwargs: client.target_calls.append((object_id, kwargs)) or 0
        action_counts = {}
        events = []

        result = behavior.commit_target(
            behavior.TargetDecision(
                allowed=False,
                candidate=candidate,
                intent=behavior.TargetIntent.travel_aggro,
                source=behavior.TargetSource.incoming_damage_counterattack,
                priority=0,
                reject_reason="travel_non_objective",
                should_target_object=False,
                should_update_current_target=False,
                should_publish_party_leader_target=False,
                should_mark_leader_engaged=False,
            ),
            client,
            None,
            now=12.0,
            current_target=77,
            current_target_since=5.0,
            current_target_last_visible_at=6.0,
            current_target_intent=behavior.TargetIntent.objective,
            action_counts=action_counts,
            log_event=lambda name, timestamp, **fields: events.append((name, timestamp, fields)),
        )

        self.assertEqual(result.current_target, 77)
        self.assertEqual(result.current_target_since, 5.0)
        self.assertEqual(result.current_target_last_visible_at, 6.0)
        self.assertEqual(result.current_target_intent, behavior.TargetIntent.objective)
        self.assertEqual(client.target_calls, [])
        self.assertEqual(action_counts["target_gate_rejected"], 1)
        self.assertEqual(events[0][0], "target_gate_rejected")

    def test_active_combat_focus_restore_uses_engagement_gate(self):
        active = {
            "target_id": 501,
            "target_name": "fenrir snowscout",
            "target_level": 38,
            "target_x": 120,
            "target_y": 80,
            "target_z": 5,
            "target_intent": "party_rescue",
        }
        args = SimpleNamespace(
            party_rescue_aggro=True,
            max_target_distance=1500.0,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir snowscout",
        )
        client = SimpleNamespace(x=0, y=0, horizontal_distance_to=lambda actor: 100.0)
        context = self._engagement_context(
            state=behavior.DummyBehaviorState.HuntObjective,
            current_target=99,
            current_target_intent=behavior.TargetIntent.party_rescue,
        )

        decision = behavior.evaluate_active_combat_focus_commit(
            args,
            active,
            context,
            client,
            {},
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.candidate.object_id, 501)
        self.assertEqual(decision.source, behavior.TargetSource.current_target_preserve)
        self.assertEqual(decision.intent, behavior.TargetIntent.party_rescue)
        self.assertTrue(decision.should_target_object)
        self.assertTrue(decision.should_update_current_target)
        self.assertFalse(decision.should_publish_party_leader_target)

    def test_active_combat_focus_restore_respects_recovery_state_gate(self):
        active = {
            "target_id": 502,
            "target_name": "fenrir prophet",
            "target_level": 39,
            "target_x": 120,
            "target_y": 80,
            "target_z": 5,
            "target_intent": "required_retaliation",
        }
        args = SimpleNamespace(
            party_rescue_aggro=True,
            max_target_distance=1500.0,
            party_encounter_mode="boss",
            objective_add_target_name="fenrir prophet",
        )
        client = FakeClient()
        context = self._engagement_context(
            state=behavior.DummyBehaviorState.DropAggroAndRecover,
            current_target=99,
            current_target_intent=behavior.TargetIntent.party_rescue,
        )

        decision = behavior.evaluate_active_combat_focus_commit(
            args,
            active,
            context,
            client,
            {},
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "drop_aggro_active")

    def test_party_assist_leader_target_uses_engagement_gate(self):
        snapshot = {
            "leader_target_id": 601,
            "leader_target_name": "drakulv berserker",
            "leader_target_x": 100,
            "leader_target_y": 100,
            "leader_target_z": 0,
            "leader_target_level": 50,
        }
        args = SimpleNamespace(max_target_distance=1500.0, player_level=50, max_target_level_delta=2)
        client = SimpleNamespace(x=0, y=0, horizontal_distance_to=lambda actor: 150.0)

        decision = behavior.evaluate_party_assist_leader_target(
            args,
            snapshot,
            self._engagement_context(
                state=behavior.DummyBehaviorState.HuntObjective,
                is_party_follower=True,
                party_ready=True,
                leader_engaged=True,
            ),
            client,
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.candidate.object_id, 601)
        self.assertEqual(decision.source, behavior.TargetSource.party_assist)
        self.assertEqual(decision.intent, behavior.TargetIntent.party_assist)

    def test_party_assist_leader_target_gate_blocks_travel_state(self):
        snapshot = {
            "leader_target_id": 602,
            "leader_target_name": "drakulv berserker",
            "leader_target_x": 100,
            "leader_target_y": 100,
            "leader_target_z": 0,
            "leader_target_level": 50,
        }
        args = SimpleNamespace(max_target_distance=1500.0, player_level=50, max_target_level_delta=2)
        client = SimpleNamespace(x=0, y=0, horizontal_distance_to=lambda actor: 150.0)

        decision = behavior.evaluate_party_assist_leader_target(
            args,
            snapshot,
            self._engagement_context(
                state=behavior.DummyBehaviorState.TravelToObjective,
                is_party_follower=True,
                party_ready=True,
                leader_engaged=True,
            ),
            client,
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reject_reason, "state_blocks_party_assist")

    def test_party_assist_command_waits_for_leader_engaged_when_required(self):
        args = SimpleNamespace(party_use_assist_command=True, party_require_leader_engaged=True)

        self.assertFalse(
            behavior.should_send_party_assist_command(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                leader_target_id=44,
                leader_engaged=False,
            )
        )
        self.assertFalse(
            behavior.should_send_party_assist_command(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                leader_target_id=44,
                leader_engaged=True,
            )
        )
        self.assertTrue(
            behavior.should_send_party_assist_command(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                leader_target_id=44,
                leader_engaged=True,
            )
        )
        self.assertFalse(
            behavior.should_send_party_assist_command(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                leader_target_id=44,
                leader_engaged=True,
            )
        )

    def test_leader_abandon_clears_shared_party_target(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=76, x=10, y=20, z=30, heading=40)
        target = SimpleNamespace(
            object_id=99,
            name="Ellyll windchaser",
            x=100,
            y=200,
            z=300,
            health_percent=44.0,
            health=440,
            max_health=1000,
            target="member",
        )

        state.update_leader(client, target)
        state.mark_leader_target_engaged(99)
        self.assertEqual(state.snapshot()["leader_target_focus_name"], "member")

        self.assertTrue(
            behavior.clear_party_leader_target_on_abandon(
                state,
                is_party_leader=True,
                target_id=99,
            )
        )
        snapshot = state.snapshot()
        self.assertEqual(snapshot["leader_target_id"], 0)
        self.assertEqual(snapshot["leader_target_engaged_at"], 0.0)
        self.assertEqual(snapshot["leader_target_focus_name"], "")
        self.assertEqual(snapshot["leader_target_focus_updated_at"], 0.0)
        self.assertEqual(snapshot["leader_target_health"], 0)
        self.assertEqual(snapshot["leader_target_max_health"], 0)

    def test_combat_start_publish_only_marks_already_committed_leader_target(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=76, x=10, y=20, z=30, heading=40)
        committed = SimpleNamespace(
            object_id=410,
            name="far darrig",
            x=100,
            y=200,
            z=300,
            health_percent=90.0,
            health=900,
            max_health=1000,
        )
        uncommitted = SimpleNamespace(
            object_id=411,
            name="wyvern",
            x=400,
            y=500,
            z=600,
            health_percent=90.0,
            health=900,
            max_health=1000,
        )

        state.update_leader(client, committed)
        self.assertFalse(
            behavior.publish_combat_start_as_leader_target(
                state,
                client,
                uncommitted,
                is_party_leader=True,
                current_target_intent=behavior.TargetIntent.objective,
            )
        )
        snapshot = state.snapshot()
        self.assertEqual(snapshot["leader_target_id"], 410)
        self.assertEqual(snapshot["leader_target_engaged_at"], 0.0)

        self.assertTrue(
            behavior.publish_combat_start_as_leader_target(
                state,
                client,
                committed,
                is_party_leader=True,
                current_target_intent=behavior.TargetIntent.objective,
            )
        )
        snapshot = state.snapshot()
        self.assertEqual(snapshot["leader_target_id"], 410)
        self.assertGreater(snapshot["leader_target_engaged_at"], 0.0)

    def test_leader_abandon_keeps_newer_shared_party_target(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=76, x=10, y=20, z=30, heading=40)
        target = SimpleNamespace(object_id=100, name="newer target", x=100, y=200, z=300)

        state.update_leader(client, target)

        self.assertFalse(
            behavior.clear_party_leader_target_on_abandon(
                state,
                is_party_leader=True,
                target_id=99,
            )
        )
        self.assertEqual(state.snapshot()["leader_target_id"], 100)

    def test_non_leader_abandon_does_not_clear_shared_party_target(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=76, x=10, y=20, z=30, heading=40)
        target = SimpleNamespace(object_id=99, name="Ellyll windchaser", x=100, y=200, z=300)

        state.update_leader(client, target)

        self.assertFalse(
            behavior.clear_party_leader_target_on_abandon(
                state,
                is_party_leader=False,
                target_id=99,
            )
        )
        self.assertEqual(state.snapshot()["leader_target_id"], 99)

    def test_party_assist_follower_keeps_engaged_removed_shared_party_target(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=76, x=10, y=20, z=30, heading=40)
        target = SimpleNamespace(object_id=99, name="Ellyll windchaser", x=100, y=200, z=300)

        state.update_leader(client, target)
        state.mark_leader_target_engaged(99)

        self.assertFalse(
            behavior.clear_party_leader_target_on_removed_object(
                state,
                is_party_leader=False,
                party_assist_only=True,
                removed_object_id=99,
            )
        )
        snapshot = state.snapshot()
        self.assertEqual(snapshot["leader_target_id"], 99)
        self.assertGreater(snapshot["leader_target_engaged_at"], 0.0)

    def test_party_assist_follower_clears_unengaged_removed_shared_party_target(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=76, x=10, y=20, z=30, heading=40)
        target = SimpleNamespace(object_id=99, name="Ellyll windchaser", x=100, y=200, z=300)

        state.update_leader(client, target)

        self.assertTrue(
            behavior.clear_party_leader_target_on_removed_object(
                state,
                is_party_leader=False,
                party_assist_only=True,
                removed_object_id=99,
            )
        )
        snapshot = state.snapshot()
        self.assertEqual(snapshot["leader_target_id"], 0)
        self.assertEqual(snapshot["leader_target_engaged_at"], 0.0)

    def test_non_assist_follower_keeps_removed_shared_party_target(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=76, x=10, y=20, z=30, heading=40)
        target = SimpleNamespace(object_id=99, name="Ellyll windchaser", x=100, y=200, z=300)

        state.update_leader(client, target)

        self.assertFalse(
            behavior.clear_party_leader_target_on_removed_object(
                state,
                is_party_leader=False,
                party_assist_only=False,
                removed_object_id=99,
            )
        )
        self.assertEqual(state.snapshot()["leader_target_id"], 99)

    def test_flee_start_moves_hunt_state_to_drop_aggro_recovery(self):
        self.assertEqual(
            behavior.state_after_flee_start(behavior.DummyBehaviorState.HuntObjective),
            behavior.DummyBehaviorState.DropAggroAndRecover,
        )
        self.assertEqual(
            behavior.state_after_flee_start(behavior.DummyBehaviorState.RestRecover),
            behavior.DummyBehaviorState.DropAggroAndRecover,
        )

    def test_death_recovery_escapes_when_flee_destination_available(self):
        self.assertTrue(
            behavior.should_escape_after_death_recovery(
                SimpleNamespace(flee_dynamic_safe_point=True, flee_home=None)
            )
        )
        self.assertTrue(
            behavior.should_escape_after_death_recovery(
                SimpleNamespace(flee_dynamic_safe_point=False, flee_home=SimpleNamespace(x=1, y=2, z=3))
            )
        )
        self.assertFalse(
            behavior.should_escape_after_death_recovery(
                SimpleNamespace(flee_dynamic_safe_point=False, flee_home=None)
            )
        )

    def test_active_flee_blocks_untracked_damage_counterattack(self):
        self.assertFalse(
            behavior.should_allow_untracked_damage_counterattack(
                behavior.DummyBehaviorState.HuntObjective,
                flee_until=105.0,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_allow_untracked_damage_counterattack(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                flee_until=0.0,
                now=100.0,
            )
        )
        self.assertTrue(
            behavior.should_allow_untracked_damage_counterattack(
                behavior.DummyBehaviorState.HuntObjective,
                flee_until=95.0,
                now=100.0,
            )
        )

    def test_critical_health_forces_drop_aggro_from_hunt_objective(self):
        args = SimpleNamespace(flee_critical_health_percent=12)

        self.assertTrue(
            behavior.should_force_drop_aggro_for_critical_health(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                health_percent=9,
            )
        )
        self.assertFalse(
            behavior.should_force_drop_aggro_for_critical_health(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                health_percent=13,
            )
        )
        self.assertFalse(
            behavior.should_force_drop_aggro_for_critical_health(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                health_percent=9,
            )
        )

    def test_critical_health_does_not_make_supported_active_tank_drag_required_boss(self):
        args = SimpleNamespace(
            require_target_name="moorlich",
            party_assist_only=True,
            party_encounter_mode="boss",
            flee_critical_health_percent=45,
            party_survival_active_tank_health_percent=35,
        )
        snapshot = {
            "leader_target_id": 77,
            "leader_target_name": "moorlich",
            "active_tank_name": "tank",
            "members": [
                {"name": "tank", "object_id": 1, "health_percent": 40, "role": "melee-basic"},
                {"name": "cleric", "object_id": 2, "health_percent": 100, "role": "healer-support"},
            ],
        }

        self.assertFalse(
            behavior.should_force_drop_aggro_for_critical_health(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                health_percent=40,
                party_snapshot=snapshot,
                member_name="tank",
                action_rotation="melee-basic",
                current_target=77,
                current_target_intent=behavior.TargetIntent.required_retaliation,
            )
        )
        self.assertTrue(
            behavior.should_force_drop_aggro_for_critical_health(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                health_percent=34,
                party_snapshot=snapshot,
                member_name="tank",
                action_rotation="melee-basic",
                current_target=77,
                current_target_intent=behavior.TargetIntent.required_retaliation,
            )
        )

    def test_required_retaliation_waits_for_home_and_party_ready_while_traveling(self):
        args = SimpleNamespace()

        self.assertFalse(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=False,
                party_ready_for_objective=True,
            )
        )
        self.assertFalse(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
            )
        )
        self.assertTrue(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=True,
            )
        )

    def test_active_tank_required_retaliation_can_commit_before_full_party_ready(self):
        args = SimpleNamespace()

        self.assertTrue(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
                direct_required_damage_to_active_tank=True,
            )
        )

    def test_party_min_ready_does_not_block_active_tank_retaliation_at_hunt_area(self):
        args = SimpleNamespace(party_min_ready=4)

        self.assertTrue(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
                direct_required_damage_to_active_tank=True,
            )
        )

    def test_solo_required_retaliation_block_keeps_active_tank_from_pulling_before_party_ready(self):
        args = SimpleNamespace(party_block_solo_required_retaliation=True)

        self.assertFalse(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
                direct_required_damage_to_active_tank=True,
            )
        )

    def test_active_tank_required_retaliation_waits_under_objective_pressure_when_solo_pull_blocked(self):
        args = SimpleNamespace(party_block_solo_required_retaliation=True)

        self.assertFalse(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
                direct_required_damage_to_active_tank=True,
                objective_pressure_active=True,
            )
        )

    def test_party_objective_counterattack_uses_objective_pressure_bypass(self):
        args = SimpleNamespace(
            require_target_name="fenrir tracker",
            party_block_solo_required_retaliation=True,
        )
        snapshot = {
            "active_tank_name": "tank",
            "leader_target_id": 77,
            "leader_target_name": "fenrir tracker",
            "leader_target_x": 666382,
            "leader_target_y": 727923,
            "leader_target_z": 6507,
            "leader_target_level": 40,
        }

        self.assertIsNone(
            behavior.party_objective_actor_from_snapshot_for_counterattack(
                args,
                snapshot,
                member_name="tank",
                action_rotation="melee-basic",
                health_percent=84,
                behavior_state=behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
            )
        )

        self.assertIsNone(
            behavior.party_objective_actor_from_snapshot_for_counterattack(
                args,
                snapshot,
                member_name="tank",
                action_rotation="melee-basic",
                health_percent=84,
                behavior_state=behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
                objective_pressure_active=True,
            )
        )

        actor = behavior.party_objective_actor_from_snapshot_for_counterattack(
            args,
            snapshot,
            member_name="tank",
            action_rotation="melee-basic",
            health_percent=84,
            behavior_state=behavior.DummyBehaviorState.TravelToObjective,
            required_home_hunt_ready=True,
            party_ready_for_objective=True,
            objective_pressure_active=True,
        )
        self.assertIsNotNone(actor)
        self.assertEqual(actor.object_id, 77)

    def test_non_tank_required_retaliation_still_waits_for_party_ready(self):
        args = SimpleNamespace()

        self.assertFalse(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
                direct_required_damage_to_active_tank=False,
            )
        )

    def test_non_tank_required_retaliation_waits_under_objective_pressure_when_solo_pull_blocked(self):
        args = SimpleNamespace(party_block_solo_required_retaliation=True)

        self.assertFalse(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
                direct_required_damage_to_active_tank=False,
                objective_pressure_active=True,
            )
        )

    def test_recovery_states_clear_follower_party_ready(self):
        self.assertTrue(
            behavior.should_clear_party_ready_for_behavior_state(
                behavior.DummyBehaviorState.DropAggroAndRecover
            )
        )
        self.assertTrue(
            behavior.should_clear_party_ready_for_behavior_state(
                behavior.DummyBehaviorState.HandleTravelAggro
            )
        )
        self.assertTrue(
            behavior.should_clear_party_ready_for_behavior_state(
                behavior.DummyBehaviorState.DeadReleaseRecover
            )
        )
        self.assertFalse(
            behavior.should_clear_party_ready_for_behavior_state(
                behavior.DummyBehaviorState.ReturnToObjective
            )
        )

    def test_party_follower_defers_required_home_when_ahead_of_tank(self):
        args = SimpleNamespace(
            required_target_home=SimpleNamespace(x=664136, y=726812, z=6512),
            party_assist_only=True,
            party_min_ready=4,
            party_pre_pull_home_stop_distance=1800,
            required_target_home_stop_distance=900,
            party_follow_distance=500,
            party_ready_max_leader_distance=1500,
        )
        party_state = behavior.PartyState("tank", ["tank", "follower"])
        party_state.update_leader(
            SimpleNamespace(
                session_id=1,
                player_object_id=11,
                x=680247,
                y=731659,
                z=8066,
                heading=0,
                health_percent=100,
            )
        )
        follower_client = SimpleNamespace(x=667031, y=726807, z=6365)

        self.assertTrue(
            behavior.should_defer_required_home_move_for_party_anchor(
                follower_client,
                args,
                party_state,
                is_party_follower=True,
                current_target=0,
            )
        )

    def test_party_follower_defers_required_home_while_tank_is_far_even_when_trailing(self):
        args = SimpleNamespace(
            required_target_home=SimpleNamespace(x=664136, y=726812, z=6512),
            party_assist_only=True,
            party_min_ready=4,
            party_pre_pull_home_stop_distance=1800,
            required_target_home_stop_distance=900,
            party_follow_distance=500,
            party_ready_max_leader_distance=1500,
        )
        party_state = behavior.PartyState("tank", ["tank", "follower"])
        party_state.update_leader(
            SimpleNamespace(
                session_id=1,
                player_object_id=11,
                x=680247,
                y=731659,
                z=8066,
                heading=0,
                health_percent=100,
            )
        )
        follower_client = SimpleNamespace(x=682000, y=732000, z=8066)

        self.assertTrue(
            behavior.should_defer_required_home_move_for_party_anchor(
                follower_client,
                args,
                party_state,
                is_party_follower=True,
                current_target=0,
            )
        )

    def test_party_follower_moves_to_required_home_once_tank_is_near(self):
        args = SimpleNamespace(
            required_target_home=SimpleNamespace(x=664136, y=726812, z=6512),
            party_assist_only=True,
            party_min_ready=4,
            party_pre_pull_home_stop_distance=1800,
            required_target_home_stop_distance=900,
            party_follow_distance=500,
            party_ready_max_leader_distance=1500,
        )
        party_state = behavior.PartyState("tank", ["tank", "follower"])
        party_state.update_leader(
            SimpleNamespace(
                session_id=1,
                player_object_id=11,
                x=665100,
                y=726900,
                z=6512,
                heading=0,
                health_percent=100,
            )
        )
        follower_client = SimpleNamespace(x=667031, y=726807, z=6365)

        self.assertFalse(
            behavior.should_defer_required_home_move_for_party_anchor(
                follower_client,
                args,
                party_state,
                is_party_follower=True,
                current_target=0,
            )
        )

    def test_party_follower_defers_required_home_when_tank_is_engaged_near_home(self):
        args = SimpleNamespace(
            required_target_home=SimpleNamespace(x=664136, y=726812, z=6512),
            party_assist_only=True,
            party_min_ready=4,
            party_pre_pull_home_stop_distance=1800,
            required_target_home_stop_distance=900,
            party_follow_distance=500,
            party_ready_max_leader_distance=1500,
        )
        party_state = behavior.PartyState("tank", ["tank", "follower"])
        party_state.update_leader(
            SimpleNamespace(
                session_id=1,
                player_object_id=11,
                x=665100,
                y=726900,
                z=6512,
                heading=0,
                health_percent=100,
            ),
            target=SimpleNamespace(
                object_id=99,
                name="camp raider",
                x=664200,
                y=726850,
                z=6512,
                health_percent=100,
                health=100,
                max_health=100,
            ),
            engaged=True,
        )
        follower_client = SimpleNamespace(x=667031, y=726807, z=6365)

        self.assertTrue(
            behavior.should_defer_required_home_move_for_party_anchor(
                follower_client,
                args,
                party_state,
                is_party_follower=True,
                current_target=0,
            )
        )

    def test_recent_objective_pressure_defers_required_home_move_after_target_removed(self):
        self.assertTrue(
            behavior.should_defer_required_home_move_for_recent_objective_pressure(
                behavior.DummyBehaviorState.HuntObjective,
                behavior.TargetIntent.required_retaliation,
                last_damage_taken_at=99.0,
                now=100.0,
            )
        )
        self.assertTrue(
            behavior.should_defer_required_home_move_for_recent_objective_pressure(
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.party_rescue,
                last_damage_taken_at=99.8,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_defer_required_home_move_for_recent_objective_pressure(
                behavior.DummyBehaviorState.HuntObjective,
                behavior.TargetIntent.required_retaliation,
                last_damage_taken_at=90.0,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_defer_required_home_move_for_recent_objective_pressure(
                behavior.DummyBehaviorState.DropAggroAndRecover,
                behavior.TargetIntent.required_retaliation,
                last_damage_taken_at=99.8,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_defer_required_home_move_for_recent_objective_pressure(
                behavior.DummyBehaviorState.HuntObjective,
                behavior.TargetIntent.travel_aggro,
                last_damage_taken_at=99.8,
                now=100.0,
            )
        )

    def test_objective_wait_recent_damage_never_drops_objective_commit(self):
        self.assertFalse(
            behavior.should_drop_objective_wait_for_recent_damage(
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.required_retaliation,
                last_damage_taken_at=98.5,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_drop_objective_wait_for_recent_damage(
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.party_rescue,
                last_damage_taken_at=98.5,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_drop_objective_wait_for_recent_damage(
                behavior.DummyBehaviorState.ReturnToObjective,
                behavior.TargetIntent.objective,
                last_damage_taken_at=99.8,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_drop_objective_wait_for_recent_damage(
                behavior.DummyBehaviorState.HuntObjective,
                behavior.TargetIntent.required_retaliation,
                last_damage_taken_at=99.8,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_drop_objective_wait_for_recent_damage(
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.travel_aggro,
                last_damage_taken_at=99.8,
                now=100.0,
            )
        )
        self.assertFalse(
            behavior.should_drop_objective_wait_for_recent_damage(
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.required_retaliation,
                last_damage_taken_at=90.0,
                now=100.0,
            )
        )

    def test_party_state_can_clear_stale_ready_member(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        state.mark_ready("member")
        self.assertIn("member", state.snapshot()["ready_names"])

        state.clear_ready("member")
        self.assertNotIn("member", state.snapshot()["ready_names"])

    def test_leader_damage_counterattack_publishes_required_target_to_party(self):
        self.assertTrue(
            behavior.should_publish_damage_counterattack_as_leader_target(
                is_party_leader=True,
                party_state=object(),
                current_target_intent=behavior.TargetIntent.required_retaliation,
            )
        )
        self.assertFalse(
            behavior.should_publish_damage_counterattack_as_leader_target(
                is_party_leader=False,
                party_state=object(),
                current_target_intent=behavior.TargetIntent.required_retaliation,
            )
        )
        self.assertFalse(
            behavior.should_publish_damage_counterattack_as_leader_target(
                is_party_leader=True,
                party_state=object(),
                current_target_intent=behavior.TargetIntent.travel_aggro,
            )
        )

    def test_leader_combat_start_publishes_party_objective_target(self):
        self.assertTrue(
            behavior.should_publish_combat_start_as_leader_target(
                is_party_leader=True,
                party_state=object(),
                current_target_intent=behavior.TargetIntent.required_retaliation,
            )
        )
        self.assertTrue(
            behavior.should_publish_combat_start_as_leader_target(
                is_party_leader=True,
                party_state=object(),
                current_target_intent=behavior.TargetIntent.party_rescue,
            )
        )
        self.assertFalse(
            behavior.should_publish_combat_start_as_leader_target(
                is_party_leader=True,
                party_state=object(),
                current_target_intent=behavior.TargetIntent.travel_aggro,
            )
        )

    def test_combat_start_shares_leader_target_as_engaged(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=80, x=10, y=20, z=30, heading=40)
        target = SimpleNamespace(object_id=99, name="ellyll guard", x=100, y=200, z=300)
        state.update_leader(client, target)

        self.assertTrue(
            behavior.publish_combat_start_as_leader_target(
                state,
                client,
                target,
                is_party_leader=True,
                current_target_intent=behavior.TargetIntent.objective,
            )
        )

        snapshot = state.snapshot()
        self.assertEqual(snapshot["leader_target_id"], 99)
        self.assertGreater(snapshot["leader_target_engaged_at"], 0.0)

    def test_party_state_update_leader_marks_new_combat_target_engaged(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        client = SimpleNamespace(session_id=1, player_object_id=7, health_percent=80, x=10, y=20, z=30, heading=40)
        first = SimpleNamespace(object_id=99, name="ellyll guard", x=100, y=200, z=300)
        second = SimpleNamespace(object_id=100, name="ellyll guard", x=120, y=220, z=320)

        state.update_leader(client, first, engaged=True)
        first_snapshot = state.snapshot()
        self.assertEqual(first_snapshot["leader_target_id"], 99)
        self.assertGreater(first_snapshot["leader_target_engaged_at"], 0.0)

        state.update_leader(client, second)
        second_snapshot = state.snapshot()
        self.assertEqual(second_snapshot["leader_target_id"], 100)
        self.assertEqual(second_snapshot["leader_target_engaged_at"], 0.0)

        state.update_leader(client, second, engaged=True)
        self.assertEqual(state.snapshot()["leader_target_id"], 100)
        self.assertGreater(state.snapshot()["leader_target_engaged_at"], 0.0)

    def test_active_tank_holds_initial_required_retaliation_multi_aggro_above_flee_health(self):
        args = SimpleNamespace(flee_health_percent=55, party_rescue_assist_after=3)
        active_combat = {"started": 10.0}

        self.assertTrue(
            behavior.should_hold_initial_required_retaliation_multi_aggro(
                args,
                active_combat,
                current_target_intent=behavior.TargetIntent.required_retaliation,
                is_active_tank=True,
                health_percent=70,
                now=12.0,
            )
        )
        self.assertFalse(
            behavior.should_hold_initial_required_retaliation_multi_aggro(
                args,
                active_combat,
                current_target_intent=behavior.TargetIntent.required_retaliation,
                is_active_tank=True,
                health_percent=54,
                now=12.0,
            )
        )
        self.assertFalse(
            behavior.should_hold_initial_required_retaliation_multi_aggro(
                args,
                active_combat,
                current_target_intent=behavior.TargetIntent.travel_aggro,
                is_active_tank=True,
                health_percent=70,
                now=12.0,
            )
        )
        self.assertFalse(
            behavior.should_hold_initial_required_retaliation_multi_aggro(
                args,
                active_combat,
                current_target_intent=behavior.TargetIntent.required_retaliation,
                is_active_tank=True,
                health_percent=70,
                now=20.0,
            )
        )

    def test_required_retaliation_does_not_commit_while_drop_aggro_recovering(self):
        args = SimpleNamespace()

        self.assertFalse(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.DropAggroAndRecover,
                required_home_hunt_ready=True,
                party_ready_for_objective=True,
            )
        )

    def test_required_retaliation_can_continue_once_hunting(self):
        args = SimpleNamespace()

        self.assertTrue(
            behavior.should_commit_required_retaliation_for_objective(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                required_home_hunt_ready=False,
                party_ready_for_objective=True,
            )
        )

    def test_objective_selection_waits_for_home_and_party_ready_while_traveling(self):
        args = SimpleNamespace(required_target_home=SimpleNamespace(x=1000, y=1000, z=0))

        self.assertTrue(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.objective,
                current_target=0,
                required_home_hunt_ready=False,
                party_ready_for_objective=True,
            )
        )
        self.assertTrue(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                behavior.TargetIntent.party_rescue,
                current_target=0,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
            )
        )
        self.assertFalse(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.objective,
                current_target=0,
                required_home_hunt_ready=True,
                party_ready_for_objective=True,
            )
        )
        self.assertFalse(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                behavior.TargetIntent.objective,
                current_target=0,
                required_home_hunt_ready=False,
                party_ready_for_objective=False,
            )
        )

    def test_objective_selection_does_not_bypass_travel_ready_gate_with_existing_target(self):
        args = SimpleNamespace(required_target_home=SimpleNamespace(x=1000, y=1000, z=0))

        self.assertTrue(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                behavior.TargetIntent.objective,
                current_target=42,
                required_home_hunt_ready=False,
                party_ready_for_objective=True,
            )
        )
        self.assertFalse(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.ReturnToObjective,
                behavior.TargetIntent.party_rescue,
                current_target=42,
                required_home_hunt_ready=False,
                party_ready_for_objective=True,
            )
        )

    def test_follower_party_rescue_bypasses_ready_gate_after_leader_engages(self):
        args = SimpleNamespace(required_target_home=SimpleNamespace(x=1000, y=1000, z=0))

        self.assertFalse(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.party_rescue,
                current_target=0,
                required_home_hunt_ready=False,
                party_ready_for_objective=False,
                is_party_follower=True,
                leader_engaged=True,
            )
        )
        self.assertTrue(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.party_rescue,
                current_target=0,
                required_home_hunt_ready=False,
                party_ready_for_objective=False,
                is_party_follower=True,
                leader_engaged=False,
            )
        )

    def test_follower_required_retaliation_bypasses_ready_gate_after_leader_engages(self):
        args = SimpleNamespace(required_target_home=SimpleNamespace(x=1000, y=1000, z=0))

        self.assertFalse(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.required_retaliation,
                current_target=0,
                required_home_hunt_ready=False,
                party_ready_for_objective=False,
                is_party_follower=True,
                leader_engaged=True,
            )
        )
        self.assertTrue(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.required_retaliation,
                current_target=0,
                required_home_hunt_ready=False,
                party_ready_for_objective=False,
                is_party_follower=True,
                leader_engaged=False,
            )
        )

    def test_required_retaliation_under_objective_pressure_respects_solo_pull_block(self):
        args = SimpleNamespace(required_target_home=SimpleNamespace(x=1000, y=1000, z=0))

        self.assertFalse(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.required_retaliation,
                current_target=0,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
                is_party_follower=True,
                leader_engaged=False,
                objective_pressure_active=True,
            )
        )
        self.assertTrue(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.required_retaliation,
                current_target=0,
                required_home_hunt_ready=False,
                party_ready_for_objective=False,
                is_party_follower=True,
                leader_engaged=False,
                objective_pressure_active=True,
            )
        )

        blocked_args = SimpleNamespace(
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            party_block_solo_required_retaliation=True,
        )
        self.assertTrue(
            behavior.should_delay_target_selection_until_objective_ready(
                blocked_args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.required_retaliation,
                current_target=0,
                required_home_hunt_ready=True,
                party_ready_for_objective=False,
                is_party_follower=True,
                leader_engaged=False,
                objective_pressure_active=True,
            )
        )

    def test_follower_objective_reacquire_waits_for_leader_engaged(self):
        args = SimpleNamespace(
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            party_require_leader_engaged=True,
        )

        self.assertTrue(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.objective,
                current_target=0,
                required_home_hunt_ready=True,
                party_ready_for_objective=True,
                is_party_follower=True,
                leader_engaged=False,
            )
        )
        self.assertFalse(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.objective,
                current_target=0,
                required_home_hunt_ready=True,
                party_ready_for_objective=True,
                is_party_follower=True,
                leader_engaged=True,
            )
        )

    def test_follower_objective_assist_bypasses_party_ready_after_leader_engages(self):
        args = SimpleNamespace(
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            party_require_leader_engaged=True,
        )

        self.assertFalse(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.objective,
                current_target=0,
                required_home_hunt_ready=False,
                party_ready_for_objective=False,
                is_party_follower=True,
                leader_engaged=True,
            )
        )
        self.assertTrue(
            behavior.should_delay_target_selection_until_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                behavior.TargetIntent.objective,
                current_target=0,
                required_home_hunt_ready=False,
                party_ready_for_objective=False,
                is_party_follower=True,
                leader_engaged=False,
            )
        )

    def test_required_retaliation_before_ready_drops_aggro_while_traveling(self):
        args = SimpleNamespace()

        self.assertTrue(
            behavior.should_drop_required_retaliation_before_objective_ready(
                args,
                behavior.DummyBehaviorState.TravelToObjective,
                required_home_hunt_ready=False,
                party_ready_for_objective=True,
            )
        )
        self.assertFalse(
            behavior.should_drop_required_retaliation_before_objective_ready(
                args,
                behavior.DummyBehaviorState.HuntObjective,
                required_home_hunt_ready=False,
                party_ready_for_objective=True,
            )
        )

    def test_scheduled_rest_is_blocked_while_traveling_to_objective(self):
        for state in (
            behavior.DummyBehaviorState.Startup,
            behavior.DummyBehaviorState.TravelToObjective,
            behavior.DummyBehaviorState.ReturnToObjective,
            behavior.DummyBehaviorState.HandleTravelAggro,
            behavior.DummyBehaviorState.DropAggroAndRecover,
            behavior.DummyBehaviorState.DeadReleaseRecover,
        ):
            with self.subTest(state=state):
                self.assertFalse(behavior.should_allow_scheduled_rest(state, 0))

        self.assertTrue(behavior.should_allow_scheduled_rest(behavior.DummyBehaviorState.HuntObjective, 0))
        self.assertFalse(behavior.should_allow_scheduled_rest(behavior.DummyBehaviorState.HuntObjective, 1234))

    def test_timed_scheduled_rest_completes_recovery_state(self):
        self.assertTrue(
            behavior.should_complete_timed_rest_recovery(
                behavior.DummyBehaviorState.RestRecover,
                rest_until=100.0,
                stand_after_rest=False,
                now=101.0,
            )
        )
        self.assertFalse(
            behavior.should_complete_timed_rest_recovery(
                behavior.DummyBehaviorState.RestRecover,
                rest_until=100.0,
                stand_after_rest=True,
                now=101.0,
            )
        )
        self.assertFalse(
            behavior.should_complete_timed_rest_recovery(
                behavior.DummyBehaviorState.HuntObjective,
                rest_until=100.0,
                stand_after_rest=False,
                now=101.0,
            )
        )

    def test_rest_recovery_completion_returns_to_home_until_hunt_ready(self):
        client = FakeClient(npcs=[])
        client.x = 1000
        client.y = 0
        client.z = 0
        args = SimpleNamespace(
            required_target_home=behavior.Waypoint(5000, 0, 0),
            required_target_home_stop_distance=500.0,
            required_target_home_hunt_distance=1200.0,
            target_home_max_distance=1200.0,
            party_size=1,
            party_assist_only=False,
            party_min_ready=0,
        )

        self.assertEqual(
            behavior.next_state_after_rest_recovery_completion(
                args,
                client,
                is_party_leader=False,
                current_target=0,
            ),
            behavior.DummyBehaviorState.ReturnToObjective,
        )

        client.x = 4500
        self.assertEqual(
            behavior.next_state_after_rest_recovery_completion(
                args,
                client,
                is_party_leader=False,
                current_target=0,
            ),
            behavior.DummyBehaviorState.HuntObjective,
        )

    def test_drop_aggro_clear_returns_to_objective_when_safe(self):
        args = SimpleNamespace(
            low_health_rest_resume_percent=80,
            low_health_rest_percent=35,
        )

        self.assertEqual(
            behavior.next_state_after_drop_aggro_recovery(
                args,
                health_percent=90,
                now=100.0,
                last_damage_taken_at=80.0,
                active_threat=False,
            ),
            behavior.DummyBehaviorState.ReturnToObjective,
        )

    def test_drop_aggro_clear_grace_keeps_recovery_active(self):
        args = SimpleNamespace(
            low_health_rest_resume_percent=80,
            low_health_rest_percent=35,
            travel_aggro_clear_grace=24.0,
        )

        self.assertEqual(
            behavior.next_state_after_drop_aggro_recovery(
                args,
                health_percent=90,
                now=100.0,
                last_damage_taken_at=90.0,
                active_threat=False,
            ),
            behavior.DummyBehaviorState.DropAggroAndRecover,
        )
        self.assertEqual(
            behavior.drop_aggro_clear_grace_remaining(
                args,
                now=100.0,
                last_damage_taken_at=90.0,
            ),
            14.0,
        )

    def test_drop_aggro_low_health_rest_requires_extended_damage_clear_grace(self):
        args = SimpleNamespace(
            low_health_rest_resume_percent=88,
            low_health_rest_percent=70,
            travel_aggro_clear_grace=24.0,
        )

        self.assertEqual(
            behavior.next_state_after_drop_aggro_recovery(
                args,
                health_percent=15,
                now=100.0,
                last_damage_taken_at=65.0,
                active_threat=False,
            ),
            behavior.DummyBehaviorState.DropAggroAndRecover,
        )
        self.assertEqual(
            behavior.next_state_after_drop_aggro_recovery(
                args,
                health_percent=15,
                now=130.0,
                last_damage_taken_at=65.0,
                active_threat=False,
            ),
            behavior.DummyBehaviorState.RestRecover,
        )

    def test_drop_aggro_recovery_uses_required_target_recovery_threshold(self):
        args = SimpleNamespace(
            low_health_rest_resume_percent=88,
            low_health_rest_percent=70,
            required_target_home=behavior.Waypoint(1000, 0, 0),
            required_target_recover_before_home_health_percent=88,
        )

        self.assertEqual(
            behavior.next_state_after_drop_aggro_recovery(
                args,
                health_percent=86,
                now=100.0,
                last_damage_taken_at=70.0,
                active_threat=False,
            ),
            behavior.DummyBehaviorState.RestRecover,
        )

    def test_travel_aggro_detour_inserted_when_return_path_crosses_danger(self):
        args = SimpleNamespace(
            travel_aggro_avoid_radius=5000.0,
            travel_aggro_detour_distance=6000.0,
            flee_safe_point_distance=5200.0,
            flee_safe_threat_radius=6000.0,
        )
        client = SimpleNamespace(x=684500, y=698500, z=6300)
        objective = behavior.MovementDestination("required-target-home:1", 681000, 690000, 7200)

        detour = behavior.travel_aggro_detour_destination(
            args,
            client,
            objective,
            danger_x=682800,
            danger_y=694200,
            danger_z=7500,
            attempt_count=2,
        )

        self.assertIsNotNone(detour)
        self.assertEqual(detour.key.split(":")[0], "travel-aggro-detour")
        self.assertGreaterEqual(
            behavior.horizontal_distance_between_points(detour.x, detour.y, 682800, 694200),
            6000.0,
        )

    def test_travel_aggro_detour_ignored_when_return_path_is_clear(self):
        args = SimpleNamespace(
            travel_aggro_avoid_radius=1200.0,
            travel_aggro_detour_distance=6000.0,
            flee_safe_point_distance=5200.0,
            flee_safe_threat_radius=6000.0,
        )
        client = SimpleNamespace(x=684500, y=698500, z=6300)
        objective = behavior.MovementDestination("required-target-home:1", 681000, 690000, 7200)

        self.assertIsNone(
            behavior.travel_aggro_detour_destination(
                args,
                client,
                objective,
                danger_x=690000,
                danger_y=690000,
                danger_z=7500,
                attempt_count=1,
            )
        )

    def test_travel_aggro_detour_is_stable_for_nearby_return_origins(self):
        args = SimpleNamespace(
            travel_aggro_avoid_radius=5200.0,
            travel_aggro_detour_distance=7000.0,
            flee_safe_point_distance=5200.0,
            flee_safe_threat_radius=6000.0,
        )
        objective = behavior.MovementDestination("required-target-home:1", 553322, 363914, 3320)
        first = behavior.travel_aggro_detour_destination(
            args,
            SimpleNamespace(x=550608, y=361118, z=2302),
            objective,
            danger_x=550656,
            danger_y=363315,
            danger_z=3344,
            attempt_count=1,
        )
        second = behavior.travel_aggro_detour_destination(
            args,
            SimpleNamespace(x=550499, y=361271, z=2330),
            objective,
            danger_x=550656,
            danger_y=363315,
            danger_z=3344,
            attempt_count=1,
        )

        self.assertIsNotNone(first)
        self.assertIsNotNone(second)
        self.assertLess(
            behavior.horizontal_distance_between_points(first.x, first.y, second.x, second.y),
            1000.0,
        )

    def test_travel_aggro_avoid_memory_clears_after_safe_distance_and_damage_grace(self):
        args = SimpleNamespace(
            travel_aggro_avoid_radius=2500.0,
            flee_safe_threat_radius=3000.0,
            travel_aggro_detour_distance=3500.0,
            travel_aggro_clear_grace=8.0,
        )
        client = SimpleNamespace(x=11000, y=1000)

        self.assertTrue(
            behavior.should_clear_travel_aggro_avoid_memory(
                args,
                client,
                now=120.0,
                danger_until=180.0,
                danger_x=1000,
                danger_y=1000,
                last_damage_taken_at=100.0,
            )
        )
        self.assertFalse(
            behavior.should_clear_travel_aggro_avoid_memory(
                args,
                client,
                now=120.0,
                danger_until=180.0,
                danger_x=1000,
                danger_y=1000,
                last_damage_taken_at=116.0,
            )
        )

    def test_watcher_wrong_target_feedback_routes_to_handle_travel_aggro(self):
        self.assertEqual(
            behavior.state_after_watcher_feedback(
                behavior.DummyBehaviorState.ReturnToObjective,
                "bad_target_choice",
            ),
            behavior.DummyBehaviorState.HandleTravelAggro,
        )

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

    def test_precast_movement_hold_keeps_support_stationary_for_cure_or_res(self):
        args = SimpleNamespace(allow_unvalidated_spells=False)
        combat_plan = SimpleNamespace(
            heal_spells=[],
            buff_spells=[],
            attack_spells=[],
            cure_spells=[object()],
            resurrection_spells=[object()],
        )

        self.assertTrue(
            behavior.should_hold_precast_movement(
                args,
                "healer-support",
                combat_plan=combat_plan,
                heal_due=False,
                buff_due=False,
                cure_due=True,
                resurrection_due=False,
                offensive_due=False,
                current_target_distance=900.0,
                tactical_backoff=False,
            )
        )
        self.assertTrue(
            behavior.should_hold_precast_movement(
                args,
                "healer-support",
                combat_plan=combat_plan,
                heal_due=False,
                buff_due=False,
                cure_due=False,
                resurrection_due=True,
                offensive_due=False,
                current_target_distance=900.0,
                tactical_backoff=False,
            )
        )

    def test_cast_action_hold_suppresses_movement_until_hold_expires(self):
        self.assertTrue(behavior.should_continue_cast_action_hold(cast_action_hold_until=12.0, now=10.0))
        self.assertFalse(behavior.should_continue_cast_action_hold(cast_action_hold_until=12.0, now=12.0))
        self.assertFalse(behavior.should_continue_cast_action_hold(cast_action_hold_until=0.0, now=10.0))

    def test_cast_action_hold_cancels_on_interrupt_or_not_ready_feedback(self):
        self.assertTrue(behavior.should_cancel_cast_action_hold_for_message({"cast_interrupted"}))
        self.assertTrue(behavior.should_cancel_cast_action_hold_for_message({"spell_not_ready"}))
        self.assertFalse(behavior.should_cancel_cast_action_hold_for_message({"damage"}))

    def test_stationary_spell_cast_hold_extends_to_real_cast_window(self):
        args = SimpleNamespace(cast_action_hold=1.6, stationary_cast_actions=True)

        self.assertEqual(behavior.effective_cast_action_hold_seconds(args, "validated_spell"), 3.4)

    def test_non_stationary_spell_cast_hold_uses_configured_value(self):
        args = SimpleNamespace(cast_action_hold=1.6, stationary_cast_actions=False)

        self.assertEqual(behavior.effective_cast_action_hold_seconds(args, "validated_spell"), 1.6)

    def test_cast_action_hold_ignores_non_spell_actions(self):
        args = SimpleNamespace(cast_action_hold=3.4, stationary_cast_actions=True)

        self.assertEqual(behavior.effective_cast_action_hold_seconds(args, "validated_skill"), 0.0)

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
            ranged_target_backoff_due=False,
        )

        self.assertEqual(reason, "boss_ranged")
        self.assertEqual(distance, 1600)

    def test_ranged_target_backoff_uses_combat_stop_distance(self):
        args = SimpleNamespace(
            attack_range=350,
            melee_range_buffer=250,
            minimum_melee_stop_distance=85,
            ranged_stop_distance=1000,
            spell_range=1500,
            boss_ranged_safe_distance=0,
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
            ranged_safety_backoff_due=False,
            ranged_target_backoff_due=True,
        )

        self.assertEqual(reason, "ranged_target")
        self.assertEqual(distance, 1000)

    def test_required_target_matches_configured_boss_name(self):
        args = SimpleNamespace(require_target_name="Lord Elidyn,King of the Barfog Hills")

        self.assertTrue(behavior.is_required_target(args, FakeNpc(10, "Lord Elidyn", 59, 100.0)))
        self.assertFalse(behavior.is_required_target(args, FakeNpc(20, "ellyll guard", 50, 100.0)))

    def test_named_boss_required_target_bypasses_upper_level_window_but_not_minimum(self):
        args = SimpleNamespace(
            require_target_name="fenrir tracker",
            min_target_level=46,
            max_target_level=50,
            player_level=50,
            max_target_level_delta=2,
            party_encounter_mode="boss",
        )
        high_boss = FakeNpc(10, "fenrir tracker", 59, 100.0)
        low_tracker = FakeNpc(11, "fenrir tracker", 41, 100.0)
        snowscout = FakeNpc(20, "fenrir snowscout", 41, 100.0)

        self.assertFalse(behavior.passes_hunter_target_level_filter(args, high_boss))
        self.assertTrue(behavior.required_target_level_allowed(args, high_boss))
        self.assertFalse(behavior.passes_hunter_target_level_filter(args, low_tracker))
        self.assertFalse(behavior.required_target_level_allowed(args, low_tracker))
        self.assertFalse(behavior.required_target_level_allowed(args, snowscout))

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
            max_target_level=43,
            player_level=50,
            max_target_level_delta=0,
            ideal_target_level=43,
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

    def test_party_damage_response_keeps_rescue_snapshot_for_followers(self):
        state = behavior.PartyState("leader", ["leader", "dps", "cleric"])
        state.update_member_role("leader", "melee-basic")
        state.update_member_role("dps", "melee-burst")
        state.update_member_role("cleric", "healer-support")
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=80, x=1, y=2, z=3))
        state.update_member("dps", SimpleNamespace(player_object_id=11, health_percent=84, x=4, y=5, z=6))
        state.update_member("cleric", SimpleNamespace(player_object_id=12, health_percent=100, x=7, y=8, z=9))
        state.request_rescue("dps", FakeNpc(200, "fenrir tracker", 41, 100.0))

        tank_snapshot, flee_snapshot = behavior.party_damage_response_snapshots(state, "dps")

        self.assertIsNone(tank_snapshot)
        self.assertIsNotNone(flee_snapshot)
        self.assertEqual(flee_snapshot["rescue_target_id"], 200)
        self.assertFalse(
            behavior.should_flee_untracked_damage(
                SimpleNamespace(
                    flee_health_percent=55,
                    low_health_rest_percent=70,
                    flee_pressure_health_percent=85,
                    flee_melee_counterattack_health_floor=55,
                ),
                current_health_percent=84,
                last_health_percent=86,
                current_target=0,
                flee_until=0.0,
                now=10.0,
                party_rescue_target_id=int(flee_snapshot["rescue_target_id"]),
            )
        )

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

    def test_party_anchor_falls_back_to_leader_when_active_tank_position_is_unknown(self):
        snapshot = {
            "active_tank_name": "leader",
            "active_tank_object_id": 10,
            "active_tank_x": 0,
            "active_tank_y": 0,
            "active_tank_z": 0,
            "leader_name": "leader",
            "leader_object_id": 10,
            "leader_x": 400,
            "leader_y": 500,
            "leader_z": 600,
        }

        anchor = behavior.party_anchor_from_snapshot(snapshot)

        self.assertEqual(anchor["name"], "leader")
        self.assertEqual((anchor["x"], anchor["y"], anchor["z"]), (400, 500, 600))

    def test_party_anchor_is_not_valid_until_a_real_position_exists(self):
        self.assertFalse(
            behavior.party_anchor_position_valid(
                {
                    "active_tank_object_id": 10,
                    "active_tank_x": 0,
                    "active_tank_y": 0,
                    "leader_object_id": 10,
                    "leader_x": 0,
                    "leader_y": 0,
                }
            )
        )
        self.assertTrue(
            behavior.party_anchor_position_valid(
                {
                    "active_tank_object_id": 10,
                    "active_tank_x": 0,
                    "active_tank_y": 0,
                    "leader_object_id": 10,
                    "leader_x": 400,
                    "leader_y": 500,
                }
            )
        )

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

    def test_party_follower_waits_to_reacquire_shared_objective_until_leader_engages(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="wild lucradan",
            party_encounter_mode="standard",
            party_require_leader_engaged=True,
        )

        self.assertFalse(
            behavior.should_reacquire_shared_objective_visible_target(
                args,
                {"leader_target_id": 0, "leader_target_engaged_at": 0.0},
                is_party_follower=True,
            )
        )
        self.assertFalse(
            behavior.should_reacquire_shared_objective_visible_target(
                args,
                {"leader_target_id": 77, "leader_target_engaged_at": 0.0},
                is_party_follower=True,
            )
        )
        self.assertTrue(
            behavior.should_reacquire_shared_objective_visible_target(
                args,
                {"leader_target_id": 77, "leader_target_engaged_at": 100.0},
                is_party_follower=True,
            )
        )

    def test_shared_objective_visible_target_does_not_switch_to_same_name_when_shared_id_missing(self):
        args = SimpleNamespace(
            require_target_name="grimwood",
            party_encounter_mode="standard",
            required_target_home=None,
            max_target_distance=400.0,
        )
        other = FakeNpc(88, "grimwood", 48, 100.0)

        selected = behavior.choose_shared_objective_visible_target(FakeClient(npcs=[other]), [other], args, 77)

        self.assertIsNone(selected)

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

    def test_required_visible_target_respects_growth_level_window(self):
        args = SimpleNamespace(
            require_target_name="bone-eater clanmother",
            required_target_home=None,
            min_target_level=46,
            max_target_level=48,
            max_target_level_delta=1,
            player_level=50,
            max_target_distance=2200.0,
        )
        low = FakeNpc(77, "bone-eater clanmother", 42, 100.0)
        valid = FakeNpc(88, "bone-eater clanmother", 47, 400.0)

        selected = behavior.choose_required_visible_target(FakeClient(npcs=[low, valid]), [low, valid], args)

        self.assertEqual(selected.object_id, 88)

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

    def test_follower_does_not_republish_abandoned_leader_target_when_leader_must_engage(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="sylvan goblin warrior",
            party_encounter_mode="standard",
            party_require_leader_engaged=True,
        )
        snapshot = {"leader_target_engaged_at": 0.0}

        self.assertFalse(
            behavior.should_share_selected_target(
                args,
                selected_npc_is_rescue=False,
                is_party_leader=False,
                party_snapshot=snapshot,
            )
        )

    def test_follower_does_not_refresh_visible_required_target_after_leader_clear(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="sylvan goblin warrior",
            party_encounter_mode="standard",
            party_require_leader_engaged=True,
        )
        boss = FakeNpc(2001, "sylvan goblin warrior", 65, 100.0)
        snapshot = {"leader_target_id": 0, "leader_target_engaged_at": 0.0}

        self.assertFalse(
            behavior.should_refresh_shared_required_target(
                args,
                boss,
                is_party_leader=False,
                party_snapshot=snapshot,
            )
        )

    def test_leader_can_refresh_visible_required_target_after_leader_clear(self):
        args = SimpleNamespace(
            party_assist_only=True,
            require_target_name="sylvan goblin warrior",
            party_encounter_mode="standard",
            party_require_leader_engaged=True,
        )
        boss = FakeNpc(2001, "sylvan goblin warrior", 65, 100.0)
        snapshot = {"leader_target_id": 0, "leader_target_engaged_at": 0.0}

        self.assertTrue(
            behavior.should_refresh_shared_required_target(
                args,
                boss,
                is_party_leader=True,
                party_snapshot=snapshot,
            )
        )

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

    def test_party_rescue_target_bypasses_target_home_leash(self):
        args = SimpleNamespace(party_rescue_aggro=True)
        snapshot = {"rescue_target_id": 200}

        self.assertTrue(behavior.current_target_bypasses_target_home_leash(args, snapshot, 200))
        self.assertFalse(behavior.current_target_bypasses_target_home_leash(args, snapshot, 100))
        self.assertFalse(
            behavior.current_target_bypasses_target_home_leash(
                SimpleNamespace(party_rescue_aggro=False),
                snapshot,
                200,
            )
        )

    def test_party_rescue_leader_target_bypasses_only_player_home_leash(self):
        args = SimpleNamespace(
            party_rescue_aggro=True,
            required_target_home=SimpleNamespace(x=0, y=0, z=0),
            combat_home_leash_distance=500.0,
        )
        target = FakeNpc(200, "fenrir snowscout", 38, 200.0)
        target.x = 250
        snapshot = {
            "rescue_target_id": 300,
            "leader_target_id": 200,
            "leader_target_engaged_at": 10.0,
        }

        self.assertTrue(
            behavior.current_target_bypasses_target_home_leash(
                args,
                snapshot,
                200,
                current_target_intent=behavior.TargetIntent.party_rescue,
                npc=target,
                leash_reason="player",
            )
        )
        self.assertFalse(
            behavior.current_target_bypasses_target_home_leash(
                args,
                snapshot,
                200,
                current_target_intent=behavior.TargetIntent.party_rescue,
                npc=target,
                leash_reason="target",
            )
        )
        target.x = 700
        self.assertFalse(
            behavior.current_target_bypasses_target_home_leash(
                args,
                snapshot,
                200,
                current_target_intent=behavior.TargetIntent.party_rescue,
                npc=target,
                leash_reason="player",
            )
        )

    def test_active_party_rescue_focus_preserves_contact_target(self):
        args = SimpleNamespace(party_rescue_aggro=True)
        active = {
            "target_id": 200,
            "target_name": "fenrir snowscout",
            "target_level": 38,
            "target_intent": "party_rescue",
            "attacks": 1,
            "skills": 0,
            "damage_done": 0,
            "damage_taken": 0,
        }

        self.assertTrue(
            behavior.should_preserve_active_party_rescue_focus(
                args,
                active,
                200,
                behavior.TargetIntent.party_rescue,
            )
        )
        self.assertTrue(
            behavior.should_preserve_active_party_rescue_focus(
                args,
                active,
                0,
                behavior.TargetIntent.none,
            )
        )
        self.assertFalse(
            behavior.should_preserve_active_party_rescue_focus(
                args,
                active,
                201,
                behavior.TargetIntent.party_rescue,
            )
        )
        self.assertFalse(
            behavior.should_preserve_active_party_rescue_focus(
                args,
                {**active, "attacks": 0},
                200,
                behavior.TargetIntent.party_rescue,
            )
        )

    def test_active_party_rescue_focus_blocks_switch_to_other_target(self):
        args = SimpleNamespace(party_rescue_aggro=True)
        active = {
            "target_id": 200,
            "target_name": "fenrir snowscout",
            "target_level": 38,
            "target_intent": "party_rescue",
            "attacks": 1,
            "skills": 0,
            "damage_done": 0,
            "damage_taken": 0,
        }

        self.assertTrue(
            behavior.should_block_active_combat_target_switch(
                args,
                active,
                candidate_target_id=201,
                candidate_target_intent=behavior.TargetIntent.required_retaliation,
                current_target=200,
                current_target_intent=behavior.TargetIntent.party_rescue,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                flee_active=False,
                rest_active=False,
                drop_aggro_active=False,
            )
        )
        self.assertFalse(
            behavior.should_block_active_combat_target_switch(
                args,
                active,
                candidate_target_id=200,
                candidate_target_intent=behavior.TargetIntent.party_rescue,
                current_target=200,
                current_target_intent=behavior.TargetIntent.party_rescue,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                flee_active=False,
                rest_active=False,
                drop_aggro_active=False,
            )
        )

    def test_active_party_rescue_focus_switch_block_allows_escape_states_and_no_contact(self):
        args = SimpleNamespace(party_rescue_aggro=True)
        active = {
            "target_id": 200,
            "target_name": "fenrir snowscout",
            "target_level": 38,
            "target_intent": "party_rescue",
            "attacks": 1,
            "skills": 0,
            "damage_done": 0,
            "damage_taken": 0,
        }

        self.assertFalse(
            behavior.should_block_active_combat_target_switch(
                args,
                active,
                candidate_target_id=201,
                candidate_target_intent=behavior.TargetIntent.party_rescue,
                current_target=200,
                current_target_intent=behavior.TargetIntent.party_rescue,
                behavior_state=behavior.DummyBehaviorState.DropAggroAndRecover,
                flee_active=True,
                rest_active=False,
                drop_aggro_active=True,
            )
        )
        self.assertFalse(
            behavior.should_block_active_combat_target_switch(
                args,
                {**active, "attacks": 0},
                candidate_target_id=201,
                candidate_target_intent=behavior.TargetIntent.party_rescue,
                current_target=200,
                current_target_intent=behavior.TargetIntent.party_rescue,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                flee_active=False,
                rest_active=False,
                drop_aggro_active=False,
            )
        )

    def test_active_combat_switch_block_does_not_freeze_plain_objective_combat(self):
        args = SimpleNamespace(party_rescue_aggro=True, require_target_name="fenrir tracker")
        active = {
            "target_id": 200,
            "target_name": "plain wolf",
            "target_level": 38,
            "target_intent": "objective",
            "attacks": 1,
            "skills": 0,
            "damage_done": 0,
            "damage_taken": 0,
        }

        self.assertFalse(
            behavior.should_block_active_combat_target_switch(
                args,
                active,
                candidate_target_id=201,
                candidate_target_intent=behavior.TargetIntent.party_rescue,
                current_target=200,
                current_target_intent=behavior.TargetIntent.objective,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                flee_active=False,
                rest_active=False,
                drop_aggro_active=False,
            )
        )

    def test_active_preferred_objective_focus_blocks_switch_to_other_target(self):
        args = SimpleNamespace(
            party_rescue_aggro=True,
            require_target_name="",
            prefer_target_name="shady pilferer",
        )
        active = {
            "target_id": 200,
            "target_name": "shady pilferer",
            "target_level": 5,
            "target_intent": "objective",
            "attacks": 1,
            "skills": 0,
            "damage_done": 0,
            "damage_taken": 0,
        }

        self.assertTrue(
            behavior.should_block_active_combat_target_switch(
                args,
                active,
                candidate_target_id=201,
                candidate_target_intent=behavior.TargetIntent.objective,
                current_target=200,
                current_target_intent=behavior.TargetIntent.objective,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                flee_active=False,
                rest_active=False,
                drop_aggro_active=False,
            )
        )
        self.assertFalse(
            behavior.should_block_active_combat_target_switch(
                args,
                active,
                candidate_target_id=201,
                candidate_target_intent=behavior.TargetIntent.required_retaliation,
                current_target=200,
                current_target_intent=behavior.TargetIntent.objective,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                flee_active=False,
                rest_active=False,
                drop_aggro_active=False,
            )
        )

    def test_low_health_rescue_counterattack_abandons_to_flee(self):
        args = SimpleNamespace(party_rescue_aggro=True, flee_melee_counterattack_health_floor=75)
        snapshot = {"rescue_target_id": 200}

        self.assertTrue(
            behavior.should_abandon_party_rescue_counterattack_for_flee(
                args,
                snapshot,
                current_target=200,
                current_health_percent=71,
                previous_health_percent=78,
            )
        )
        self.assertFalse(
            behavior.should_abandon_party_rescue_counterattack_for_flee(
                args,
                snapshot,
                current_target=200,
                current_health_percent=80,
                previous_health_percent=90,
            )
        )

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

    def test_party_focus_target_backoff_stops_before_dragging_boss_out_of_home(self):
        args = SimpleNamespace(
            required_target_home=SimpleNamespace(x=1000, y=1000, z=0),
            combat_home_leash_distance=2800.0,
            target_home_max_distance=2800.0,
            party_focus_target_home_max_distance=0.0,
        )
        client = FakeClient()
        client.x = 2261
        client.y = 1000
        client.z = 0

        self.assertTrue(behavior.should_hold_party_focus_target_backoff_at_home_limit(args, client))

        client.x = 1900

        self.assertFalse(behavior.should_hold_party_focus_target_backoff_at_home_limit(args, client))

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

    def test_healer_support_suppresses_boss_required_objective_target(self):
        args = SimpleNamespace(
            party_encounter_mode="boss",
            require_target_name="moorlich",
            objective_add_target_name="",
        )
        npc = FakeNpc(77, "moorlich", 48, 500.0)

        self.assertTrue(
            behavior.should_healer_support_suppress_hostile_commit(
                args,
                "healer-support",
                npc,
                behavior.TargetIntent.objective,
                {"leader_target_id": 77, "active_tank_name": "leader"},
            )
        )

    def test_healer_support_does_not_suppress_boss_add_control_target(self):
        args = SimpleNamespace(
            party_encounter_mode="boss",
            require_target_name="moorlich",
            objective_add_target_name="moorlich add",
        )
        npc = FakeNpc(78, "moorlich add", 48, 500.0)

        self.assertFalse(
            behavior.should_healer_support_suppress_hostile_commit(
                args,
                "healer-support",
                npc,
                behavior.TargetIntent.party_rescue,
                {"leader_target_id": 77, "active_tank_name": "leader"},
            )
        )

    def test_party_heal_spell_prefers_strongest_spell_in_pool(self):
        args = SimpleNamespace(combat_plan_spell_pool=3)
        weak = behavior.UsableSpellRef(0, 12, "Minor Heal", 12, damage=80.0, cast_time=2500)
        slow = behavior.UsableSpellRef(0, 44, "Slow Big Heal", 44, damage=330.0, cast_time=4000)
        strong = behavior.UsableSpellRef(0, 44, "Fast Big Heal", 44, damage=330.0, cast_time=2500)

        self.assertIs(
            behavior.choose_party_heal_spell(args, [weak, slow, strong]),
            strong,
        )

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

    def test_healer_breaks_non_heal_friendly_hold_for_wounded_active_tank(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member("leader", SimpleNamespace(player_object_id=1, health_percent=75, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=2, health_percent=100, x=0, y=0, z=0))
        args = SimpleNamespace(party_heal_leader_interval=1.8, party_heal_leader_health_percent=80)

        self.assertTrue(
            behavior.should_break_friendly_cast_hold_for_party_heal(
                state,
                args,
                action_rotation="healer-support",
                is_party_follower=True,
                friendly_cast_hold_until=12.0,
                friendly_cast_hold_reason="party_protection",
                now=10.0,
                exclude_name="cleric",
            )
        )

    def test_healer_keeps_existing_heal_hold_until_cast_can_land(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member("leader", SimpleNamespace(player_object_id=1, health_percent=55, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=2, health_percent=100, x=0, y=0, z=0))
        args = SimpleNamespace(party_heal_leader_interval=1.8, party_heal_leader_health_percent=80)

        self.assertFalse(
            behavior.should_break_friendly_cast_hold_for_party_heal(
                state,
                args,
                action_rotation="healer-support",
                is_party_follower=True,
                friendly_cast_hold_until=12.0,
                friendly_cast_hold_reason="party_heal",
                now=10.0,
                exclude_name="cleric",
            )
        )

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

    def test_party_heal_target_self_preserves_low_healer_without_focus(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "wizard"])
        state.update_member("leader", SimpleNamespace(player_object_id=1, health_percent=95, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=2, health_percent=40, x=0, y=0, z=0))
        state.update_member("wizard", SimpleNamespace(player_object_id=3, health_percent=60, x=0, y=0, z=0))
        args = SimpleNamespace(party_heal_leader_health_percent=80, healer_self_health_percent=65)

        target = behavior.choose_party_heal_target(state, args, exclude_name="cleric")

        self.assertIsNotNone(target)
        self.assertEqual(target["name"], "cleric")

    def test_party_heal_target_self_preserve_beats_wounded_active_tank(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "wizard"])
        state.update_member("leader", SimpleNamespace(player_object_id=1, health_percent=75, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=2, health_percent=20, x=0, y=0, z=0))
        state.update_member("wizard", SimpleNamespace(player_object_id=3, health_percent=60, x=0, y=0, z=0))
        args = SimpleNamespace(party_heal_leader_health_percent=80, healer_self_health_percent=65)

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

    def test_server_los_retry_keeps_ranged_roles_at_cast_distance(self):
        args = SimpleNamespace(
            attack_range=350,
            melee_range_buffer=250,
            minimum_melee_stop_distance=85,
            ranged_stop_distance=1000,
            spell_range=1500,
        )

        self.assertEqual(behavior.server_los_retry_stop_distance(args, "caster-basic"), 1000)
        self.assertEqual(behavior.server_los_retry_stop_distance(args, "healer-support"), 1000)
        self.assertEqual(behavior.server_los_retry_stop_distance(args, "melee-basic"), 42.5)

    def test_ranged_target_safety_backs_off_when_target_gets_too_close(self):
        args = SimpleNamespace(
            attack_range=350,
            melee_range_buffer=250,
            minimum_melee_stop_distance=85,
            ranged_stop_distance=1000,
            spell_range=1500,
        )

        self.assertTrue(behavior.should_back_off_for_ranged_combat_target(args, "caster-basic", 500))
        self.assertTrue(behavior.should_back_off_for_ranged_combat_target(args, "healer-support", 500))
        self.assertFalse(behavior.should_back_off_for_ranged_combat_target(args, "caster-basic", 900))
        self.assertFalse(behavior.should_back_off_for_ranged_combat_target(args, "melee-basic", 50))

    def test_melee_attack_action_distance_uses_actual_distance_not_incoming_grace(self):
        self.assertEqual(behavior.attack_action_distance("melee-basic", 534.0, 60.0), 534.0)
        self.assertEqual(behavior.attack_action_distance("melee-burst", 392.0, 60.0), 392.0)

    def test_caster_attack_action_distance_can_use_effective_distance(self):
        self.assertEqual(behavior.attack_action_distance("caster-basic", 534.0, 60.0), 60.0)

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

    def test_party_assist_follows_anchor_until_unseen_target_is_visible(self):
        args = SimpleNamespace(party_follow_distance=450)

        self.assertTrue(
            behavior.should_follow_party_anchor_for_unseen_assist_target(
                args,
                current_target=77,
                current_target_intent=behavior.TargetIntent.party_assist,
                target_visible=False,
                anchor_distance=950,
            )
        )
        self.assertFalse(
            behavior.should_follow_party_anchor_for_unseen_assist_target(
                args,
                current_target=77,
                current_target_intent=behavior.TargetIntent.party_assist,
                target_visible=True,
                anchor_distance=950,
            )
        )
        self.assertFalse(
            behavior.should_follow_party_anchor_for_unseen_assist_target(
                args,
                current_target=77,
                current_target_intent=behavior.TargetIntent.objective,
                target_visible=False,
                anchor_distance=950,
            )
        )
        self.assertFalse(
            behavior.should_follow_party_anchor_for_unseen_assist_target(
                args,
                current_target=77,
                current_target_intent=behavior.TargetIntent.party_assist,
                target_visible=False,
                anchor_distance=300,
            )
        )

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

    def test_party_ready_gate_requires_ready_member_near_leader_when_configured(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        state.update_leader(SimpleNamespace(session_id=1, player_object_id=10, health_percent=100, x=0, y=0, z=0, heading=0))
        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=2500, y=0, z=0))
        state.mark_ready("member")
        args = SimpleNamespace(party_min_ready=2, party_ready_max_leader_distance=1500.0)

        self.assertFalse(behavior.party_ready_for_pull(args, state))

        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=1200, y=0, z=0))
        self.assertTrue(behavior.party_ready_for_pull(args, state))

    def test_party_form_up_delay_waits_for_near_ready_members(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        state.update_leader(SimpleNamespace(session_id=1, player_object_id=10, health_percent=100, x=0, y=0, z=0, heading=0))
        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=2600, y=0, z=0))
        state.mark_ready("member")
        args = SimpleNamespace(
            party_size=2,
            party_min_ready=2,
            party_ready_max_leader_distance=1500.0,
            party_form_up_delay=4.0,
            required_target_home=behavior.Waypoint(1000, 0, 0),
        )

        self.assertFalse(
            behavior.should_start_party_form_up_delay(
                args,
                state,
                is_party_leader=True,
                current_target=0,
            )
        )

        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=1000, y=0, z=0))
        self.assertTrue(
            behavior.should_start_party_form_up_delay(
                args,
                state,
                is_party_leader=True,
                current_target=0,
            )
        )

    def test_required_target_recent_damage_does_not_commit_when_party_far(self):
        args = SimpleNamespace(
            required_target_tank_commit_health_percent=35,
            require_target_name="frost spectre",
            prefer_target_name="",
        )

        self.assertFalse(
            behavior.should_commit_required_target_from_recent_damage(
                args,
                current_health_percent=89,
                previous_health_percent=100,
                current_target=0,
                last_damage_attacker_name="frost spectre",
                party_ready_for_objective=False,
            )
        )

    def test_required_target_untracked_damage_can_flee_when_party_far(self):
        args = SimpleNamespace(
            required_target_tank_commit_health_percent=35,
            flee_health_percent=55,
            low_health_rest_percent=70,
            flee_pressure_health_percent=85,
            require_target_name="frost spectre",
            prefer_target_name="",
        )

        self.assertTrue(
            behavior.should_flee_untracked_damage(
                args,
                current_health_percent=73,
                last_health_percent=89,
                current_target=0,
                flee_until=0.0,
                now=10.0,
                last_damage_attacker_name="frost spectre",
                party_ready_for_objective=False,
            )
        )

    def test_non_required_large_health_drop_forces_flee_over_rescue_counterattack(self):
        args = SimpleNamespace(
            flee_pressure_health_percent=85,
            flee_untracked_health_drop_percent=15,
            require_target_name="frost spectre",
            prefer_target_name="",
        )

        self.assertTrue(
            behavior.should_force_flee_from_non_required_health_drop(
                args,
                current_health_percent=64,
                previous_health_percent=85,
                last_damage_attacker_name="fenrir snowscout",
            )
        )
        self.assertFalse(
            behavior.should_force_flee_from_non_required_health_drop(
                args,
                current_health_percent=74,
                previous_health_percent=84,
                last_damage_attacker_name="frost spectre",
            )
        )

    def test_party_ready_gate_can_be_disabled(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        args = SimpleNamespace(party_min_ready=0)

        self.assertTrue(behavior.party_ready_for_pull(args, state))

    def test_party_follower_waypoint_is_suppressed_until_party_forms(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        state.update_leader(SimpleNamespace(session_id=1, player_object_id=10, health_percent=100, x=0, y=0, z=0, heading=0))
        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=3500, y=0, z=0))
        args = SimpleNamespace(party_assist_only=True, party_min_ready=2, party_ready_max_leader_distance=1500.0)

        self.assertTrue(
            behavior.should_suppress_party_follower_waypoint(
                args,
                state,
                is_party_follower=True,
                current_target=0,
            )
        )

        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=900, y=0, z=0))
        state.mark_ready("member")
        self.assertTrue(
            behavior.should_suppress_party_follower_waypoint(
                args,
                state,
                is_party_follower=True,
                current_target=0,
            )
        )

    def test_party_pre_pull_home_stop_distance_keeps_leader_outside_aggro_until_ready(self):
        state = behavior.PartyState("leader", ["leader", "member"])
        state.update_leader(SimpleNamespace(session_id=1, player_object_id=10, health_percent=100, x=0, y=0, z=0, heading=0))
        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=3500, y=0, z=0))
        args = SimpleNamespace(
            party_min_ready=2,
            party_ready_max_leader_distance=1500.0,
            required_target_home_stop_distance=900.0,
            party_pre_pull_home_stop_distance=1800.0,
        )

        self.assertEqual(
            behavior.required_target_home_move_stop_distance(
                args,
                state,
                is_party_leader=True,
                current_target=0,
            ),
            1800.0,
        )

        state.update_member("member", SimpleNamespace(player_object_id=11, health_percent=100, x=900, y=0, z=0))
        state.mark_ready("member")
        self.assertEqual(
            behavior.required_target_home_move_stop_distance(
                args,
                state,
                is_party_leader=True,
                current_target=0,
            ),
            900.0,
        )

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
            use_skills=True,
            allow_unvalidated_skills=True,
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "melee-basic", 80)

        self.assertEqual(action, "skill")
        self.assertEqual(client.skills, [(2, 1)])

    def test_due_rotation_uses_skill_during_smooth_melee_engage(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            skill_indexes=[2],
            skill_type=1,
            use_skills=True,
            allow_unvalidated_skills=True,
            allow_unvalidated_spells=False,
            combat_plan_skill_pool=4,
            combat_plan_spell_pool=3,
            hybrid_melee_chance=1.0,
            healer_self_health_percent=60,
            support_spell_chance=0.0,
            stationary_cast_actions=False,
            party_active_tank_reaggro_taunt_interval=4.0,
            jitter=0.0,
            skill_interval=4.0,
        )
        active_combat = {"skills": 0}

        action, next_skill, _next_taunt = behavior.perform_due_rotation_action(
            client,
            behavior.random.Random(1),
            args,
            "melee-basic",
            60.0,
            behavior.CombatUsablePlan(),
            active_combat=active_combat,
            now=10.0,
            next_skill=9.0,
            reaggro_taunt_due=False,
            prefer_taunt_skill=False,
            next_active_tank_reaggro_taunt=0.0,
        )

        self.assertEqual(action, "skill")
        self.assertEqual(client.skills, [(2, 1)])
        self.assertEqual(active_combat["skills"], 1)
        self.assertEqual(next_skill, 14.0)

    def test_due_rotation_keeps_skill_ready_when_melee_target_out_of_range(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            skill_indexes=[2],
            skill_type=1,
            use_skills=True,
            allow_unvalidated_skills=True,
            allow_unvalidated_spells=False,
            combat_plan_skill_pool=4,
            combat_plan_spell_pool=3,
            hybrid_melee_chance=1.0,
            healer_self_health_percent=60,
            support_spell_chance=0.0,
            stationary_cast_actions=False,
            party_active_tank_reaggro_taunt_interval=4.0,
            jitter=0.0,
            skill_interval=4.0,
        )
        active_combat = {"skills": 0}

        action, next_skill, _next_taunt = behavior.perform_due_rotation_action(
            client,
            behavior.random.Random(1),
            args,
            "melee-basic",
            300.0,
            behavior.CombatUsablePlan(),
            active_combat=active_combat,
            now=10.0,
            next_skill=9.0,
            reaggro_taunt_due=False,
            prefer_taunt_skill=False,
            next_active_tank_reaggro_taunt=0.0,
        )

        self.assertIsNone(action)
        self.assertEqual(client.skills, [])
        self.assertEqual(active_combat["skills"], 0)
        self.assertEqual(next_skill, 9.0)

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

    def test_combat_plan_parses_resurrection_and_crowd_control_spells(self):
        payload = {
            "skills": [],
            "spellLines": [
                {
                    "entries": [
                        {
                            "kind": "Spell",
                            "lineIndex": 1,
                            "spellLevel": 18,
                            "name": "Resurrection",
                            "level": 18,
                            "spell": {
                                "spellType": "Resurrect",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": False,
                                "damage": 0,
                                "range": 1500,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 2,
                            "spellLevel": 23,
                            "name": "Mesmerize",
                            "level": 23,
                            "spell": {
                                "spellType": "Mesmerize",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 0,
                                "range": 1500,
                                "radius": 350,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 3,
                            "spellLevel": 14,
                            "name": "Root",
                            "level": 14,
                            "spell": {
                                "spellType": "Root",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 0,
                                "range": 1500,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 4,
                            "spellLevel": 8,
                            "name": "Minor Heal",
                            "level": 8,
                            "spell": {
                                "spellType": "Heal",
                                "isHealing": True,
                                "isBuff": False,
                                "isHarmful": False,
                                "damage": 0,
                                "range": 1500,
                            },
                        },
                    ]
                }
            ],
        }

        plan = behavior.parse_combat_usable_plan(payload)

        self.assertEqual([spell.name for spell in plan.resurrection_spells], ["Resurrection"])
        self.assertEqual([spell.name for spell in plan.crowd_control_spells], ["Mesmerize", "Root"])
        self.assertEqual([spell.name for spell in plan.heal_spells], ["Minor Heal"])

    def test_combat_plan_uses_capability_tags_for_speed_song_and_stealth(self):
        payload = {
            "skills": [],
            "spellLines": [
                {
                    "entries": [
                        {
                            "kind": "Spell",
                            "lineIndex": 1,
                            "spellLevel": 5,
                            "name": "Traveler's Chant",
                            "level": 5,
                            "spell": {
                                "spellType": "UnknownPulseBuff",
                                "capabilityTags": ["speedSong", "speed"],
                                "isHealing": False,
                                "isBuff": True,
                                "isHarmful": False,
                                "damage": 0,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 2,
                            "spellLevel": 12,
                            "name": "Shadow Walk",
                            "level": 12,
                            "spell": {
                                "spellType": "UnknownSelfBuff",
                                "capabilityTags": ["stealth"],
                                "isHealing": False,
                                "isBuff": True,
                                "isHarmful": False,
                                "damage": 0,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 3,
                            "spellLevel": 18,
                            "name": "Raise Ally",
                            "level": 18,
                            "spell": {
                                "spellType": "UnknownHelpful",
                                "target": "Corpse",
                                "capabilityTags": ["resurrection"],
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": False,
                                "damage": 0,
                            },
                        },
                    ]
                }
            ],
        }

        plan = behavior.parse_combat_usable_plan(payload)

        self.assertEqual([spell.name for spell in plan.speed_song_spells], ["Traveler's Chant"])
        self.assertEqual([spell.name for spell in plan.speed_spells], ["Traveler's Chant"])
        self.assertEqual([spell.name for spell in plan.stealth_spells], ["Shadow Walk"])
        self.assertEqual([spell.name for spell in plan.resurrection_spells], ["Raise Ally"])
        self.assertIn("speed_song", plan.speed_song_spells[0].capability_tags)
        self.assertIn("stealth", plan.stealth_spells[0].capability_tags)

    def test_combat_plan_uses_capability_tags_for_pet_charm_and_bladeturn(self):
        payload = {
            "skills": [],
            "spellLines": [
                {
                    "entries": [
                        {
                            "kind": "Spell",
                            "lineIndex": 1,
                            "spellLevel": 7,
                            "name": "Call Ally",
                            "level": 7,
                            "spell": {
                                "spellType": "UnknownUtility",
                                "capabilityTags": ["pet", "summon"],
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": False,
                                "damage": 0,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 2,
                            "spellLevel": 18,
                            "name": "Compelling Song",
                            "level": 18,
                            "spell": {
                                "spellType": "UnknownControl",
                                "capabilityTags": ["charm"],
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 0,
                                "range": 1500,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 3,
                            "spellLevel": 20,
                            "name": "Blade Barrier",
                            "level": 20,
                            "spell": {
                                "spellType": "UnknownBuff",
                                "capabilityTags": ["bladeturn"],
                                "isHealing": False,
                                "isBuff": True,
                                "isHarmful": False,
                                "damage": 0,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 4,
                            "spellLevel": 22,
                            "name": "Draining Touch",
                            "level": 22,
                            "spell": {
                                "spellType": "UnknownDamage",
                                "capabilityTags": ["lifedrain"],
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 35,
                                "range": 1500,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 5,
                            "spellLevel": 24,
                            "name": "Wasting Breath",
                            "level": 24,
                            "spell": {
                                "spellType": "UnknownDebuff",
                                "capabilityTags": ["disease"],
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 0,
                                "range": 1500,
                            },
                        },
                    ]
                }
            ],
        }

        plan = behavior.parse_combat_usable_plan(payload)

        self.assertEqual([spell.name for spell in plan.summon_spells], ["Call Ally"])
        self.assertEqual([spell.name for spell in plan.crowd_control_spells], ["Compelling Song"])
        self.assertEqual([spell.name for spell in plan.buff_spells], ["Blade Barrier"])
        self.assertEqual([spell.name for spell in plan.attack_spells], ["Draining Touch"])
        self.assertEqual([spell.name for spell in plan.debuff_spells], ["Wasting Breath"])
        self.assertIn("pet", plan.summon_spells[0].capability_tags)
        self.assertIn("charm", plan.crowd_control_spells[0].capability_tags)
        self.assertIn("bladeturn", plan.buff_spells[0].capability_tags)
        self.assertIn("lifedrain", plan.attack_spells[0].capability_tags)
        self.assertIn("disease", plan.debuff_spells[0].capability_tags)

    def test_pet_prefix_spell_types_do_not_become_summons_unless_tagged(self):
        payload = {
            "skills": [],
            "spellLines": [
                {
                    "entries": [
                        {
                            "kind": "Spell",
                            "lineIndex": 1,
                            "spellLevel": 22,
                            "name": "Pet Drain",
                            "level": 22,
                            "spell": {
                                "spellType": "PetLifedrain",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 35,
                                "range": 1500,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 2,
                            "spellLevel": 18,
                            "name": "Pet Mesmerize",
                            "level": 18,
                            "spell": {
                                "spellType": "PetMesmerize",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 0,
                                "range": 1500,
                            },
                        },
                    ]
                }
            ],
        }

        plan = behavior.parse_combat_usable_plan(payload)

        self.assertEqual(plan.summon_spells, [])
        self.assertEqual([spell.name for spell in plan.attack_spells], ["Pet Drain"])
        self.assertEqual([spell.name for spell in plan.crowd_control_spells], ["Pet Mesmerize"])

    def test_precombat_self_buffs_cast_speed_song_and_optional_stealth(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            startup_self_buff_count=1,
            startup_self_buff_delay=0.0,
            startup_speed_song=True,
            startup_stealth=True,
        )
        plan = behavior.CombatUsablePlan(
            speed_song_spells=[
                behavior.UsableSpellRef(line_index=4, spell_level=5, name="Traveler's Chant", level=5),
            ],
            stealth_spells=[
                behavior.UsableSpellRef(line_index=5, spell_level=12, name="Shadow Walk", level=12),
            ],
            buff_spells=[
                behavior.UsableSpellRef(line_index=6, spell_level=20, name="Self Shield", level=20),
            ],
        )
        action_counts: dict[str, int] = {}

        actions = behavior.cast_precombat_self_buffs(client, args, plan, action_counts)

        self.assertEqual(actions, 3)
        self.assertEqual(client.spells, [(5, 4), (12, 5), (20, 6)])
        self.assertEqual(action_counts["precombat_speed_song_spell"], 1)
        self.assertEqual(action_counts["precombat_stealth_spell"], 1)
        self.assertEqual(action_counts["precombat_self_buff_spell"], 1)

    def test_precombat_self_buffs_cast_summon_before_other_startup_buffs(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            startup_self_buff_count=1,
            startup_self_buff_delay=0.0,
            startup_summon_pet=True,
            startup_speed_song=True,
            startup_stealth=False,
        )
        plan = behavior.CombatUsablePlan(
            summon_spells=[
                behavior.UsableSpellRef(line_index=1, spell_level=7, name="Call Ally", level=7),
            ],
            speed_song_spells=[
                behavior.UsableSpellRef(line_index=2, spell_level=5, name="Traveler's Chant", level=5),
            ],
            buff_spells=[
                behavior.UsableSpellRef(line_index=3, spell_level=20, name="Blade Barrier", level=20),
            ],
        )
        action_counts: dict[str, int] = {}

        actions = behavior.cast_precombat_self_buffs(client, args, plan, action_counts)

        self.assertEqual(actions, 3)
        self.assertEqual(client.spells, [(7, 1), (5, 2), (20, 3)])
        self.assertEqual(action_counts["precombat_summon_spell"], 1)
        self.assertEqual(action_counts["precombat_speed_song_spell"], 1)
        self.assertEqual(action_counts["precombat_self_buff_spell"], 1)

    def test_combat_plan_classifies_cure_debuff_taunt_and_area_damage_spells(self):
        payload = {
            "skills": [],
            "spellLines": [
                {
                    "entries": [
                        {
                            "kind": "Spell",
                            "lineIndex": 1,
                            "spellLevel": 12,
                            "name": "Cure Mezz",
                            "level": 12,
                            "spell": {
                                "spellType": "CureMezz",
                                "isHealing": True,
                                "isBuff": False,
                                "isHarmful": False,
                                "damage": 0,
                                "range": 1500,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 2,
                            "spellLevel": 18,
                            "name": "Weakness",
                            "level": 18,
                            "spell": {
                                "spellType": "StrengthDebuff",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "isDebuff": True,
                                "damage": 0,
                                "range": 1500,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 3,
                            "spellLevel": 22,
                            "name": "Taunt",
                            "level": 22,
                            "spell": {
                                "spellType": "Taunt",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 0,
                                "range": 1200,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 4,
                            "spellLevel": 24,
                            "name": "Point Blank Blast",
                            "level": 24,
                            "spell": {
                                "spellType": "PBAEDamage",
                                "target": "AREA",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 90,
                                "range": 0,
                                "radius": 350,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 5,
                            "spellLevel": 25,
                            "name": "Lingering Venom",
                            "level": 25,
                            "spell": {
                                "spellType": "DamageOverTime",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 12,
                                "range": 1500,
                                "duration": 24000,
                            },
                        },
                        {
                            "kind": "Spell",
                            "lineIndex": 6,
                            "spellLevel": 26,
                            "name": "Storm Burst",
                            "level": 26,
                            "spell": {
                                "spellType": "DirectDamage",
                                "target": "Enemy",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 70,
                                "range": 1500,
                                "radius": 350,
                            },
                        },
                    ]
                }
            ],
        }

        plan = behavior.parse_combat_usable_plan(payload)

        self.assertEqual([spell.name for spell in plan.cure_spells], ["Cure Mezz"])
        self.assertEqual([spell.name for spell in plan.debuff_spells], ["Weakness"])
        self.assertEqual([spell.name for spell in plan.taunt_spells], ["Taunt"])
        self.assertEqual([spell.name for spell in plan.dot_spells], ["Lingering Venom"])
        self.assertEqual([spell.name for spell in plan.area_attack_spells], ["Storm Burst", "Point Blank Blast"])
        self.assertEqual(plan.heal_spells, [])

    def test_combat_plan_classifies_area_dot_as_dot_for_refresh_tracking(self):
        payload = {
            "skills": [],
            "spellLines": [
                {
                    "entries": [
                        {
                            "kind": "Spell",
                            "lineIndex": 1,
                            "spellLevel": 24,
                            "name": "Rotting Cloud",
                            "level": 24,
                            "spell": {
                                "spellType": "AOEDamageOverTime",
                                "target": "AREA",
                                "isHealing": False,
                                "isBuff": False,
                                "isHarmful": True,
                                "damage": 18,
                                "range": 1500,
                                "radius": 350,
                                "duration": 24000,
                            },
                        }
                    ]
                }
            ],
        }

        plan = behavior.parse_combat_usable_plan(payload)

        self.assertEqual([spell.name for spell in plan.dot_spells], ["Rotting Cloud"])
        self.assertEqual(plan.area_attack_spells, [])

    def test_party_state_returns_resurrection_targets_for_dead_members(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "dps"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=0, x=1, y=2, z=3))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=4, y=5, z=6))
        state.update_member("dps", SimpleNamespace(player_object_id=12, health_percent=0, x=7, y=8, z=9))

        targets = state.resurrection_targets(exclude_name="cleric")

        self.assertEqual([target["name"] for target in targets], ["leader", "dps"])
        self.assertEqual(targets[0]["object_id"], 10)

    def test_party_state_treats_is_alive_false_condition_as_resurrection_target(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "RealPlayer"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=1, y=2, z=3))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=4, y=5, z=6))
        state.update_external_member("RealPlayer", SimpleNamespace(object_id=90, health_percent=100, x=7, y=8, z=9))

        state.update_member_condition(
            "RealPlayer",
            behavior.PlayerConditionSnapshot(
                name="RealPlayer",
                object_id=90,
                health_percent=100,
                is_alive=False,
                x=7,
                y=8,
                z=9,
            ),
        )

        targets = state.resurrection_targets(exclude_name="cleric")

        self.assertEqual([target["name"] for target in targets], ["RealPlayer"])
        self.assertEqual(targets[0]["health_percent"], 0)

    def test_party_resurrection_cast_targets_dead_member(self):
        client = FakeCombatClient()
        client.target_calls = []
        client.target_object = lambda object_id, **_kwargs: client.target_calls.append(object_id) or 0
        args = behavior.build_parser().parse_args([])
        spell = behavior.UsableSpellRef(line_index=1, spell_level=18, name="Resurrection", level=18)
        dead_member = {"name": "leader", "object_id": 10, "health_percent": 0, "x": 0, "y": 0, "z": 0}

        action = behavior.perform_party_resurrection_cast(client, spell, args, dead_member)

        self.assertEqual(action, "validated_party_resurrect_leader")
        self.assertEqual(client.target_calls, [10])
        self.assertEqual(client.spells, [(18, 1)])

    def test_party_resurrection_target_cooldown_skips_recent_target(self):
        state = behavior.PartyState("leader", ["leader", "cleric", "dps"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=0, x=1, y=2, z=3))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=4, y=5, z=6))
        state.update_member("dps", SimpleNamespace(player_object_id=12, health_percent=0, x=7, y=8, z=9))

        target = behavior.choose_party_resurrection_target(
            state,
            behavior.build_parser().parse_args([]),
            exclude_name="cleric",
            cooldowns={10: 30.0},
            now=20.0,
        )

        self.assertEqual(target["name"], "dps")

    def test_crowd_control_cast_targets_add_then_restores_committed_target(self):
        client = FakeCombatClient()
        client.target_calls = []
        client.target_object = lambda object_id, **_kwargs: client.target_calls.append(object_id) or 0
        args = behavior.build_parser().parse_args([])
        spell = behavior.UsableSpellRef(line_index=2, spell_level=23, name="Mesmerize", level=23, spell_type="Mesmerize")
        add = FakeNpc(22, "winter wolf", 48, 800.0)

        action = behavior.perform_crowd_control_cast(client, spell, args, add)

        self.assertEqual(action, "validated_crowd_control_spell")
        self.assertEqual(client.target_calls, [22])
        self.assertEqual(client.spells, [(23, 2)])

    def test_crowd_control_due_when_api_add_targets_party_member_before_damage(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        plan = behavior.CombatUsablePlan(
            crowd_control_spells=[
                behavior.UsableSpellRef(line_index=2, spell_level=23, name="Mesmerize", level=23, spell_type="Mesmerize")
            ]
        )
        add = behavior.RequiredTargetObservation(
            object_id=22,
            name="winter wolf",
            x=500,
            y=0,
            z=0,
            level=48,
            has_aggro=True,
            target="cleric",
        )
        args = SimpleNamespace(crowd_control_interval=3.0, crowd_control_health_floor=0)

        self.assertTrue(
            behavior.should_use_crowd_control_for_multi_aggro(
                args,
                plan,
                {"target_id": 99, "target_name": "moorlich"},
                current_target=99,
                health_percent=100,
                now=10.0,
                next_crowd_control=0.0,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                party_snapshot=state.snapshot(),
                observed_npcs=[add],
            )
        )

    def test_crowd_control_due_before_primary_target_when_multiple_adds_have_aggro(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        plan = behavior.CombatUsablePlan(
            crowd_control_spells=[
                behavior.UsableSpellRef(line_index=2, spell_level=23, name="Mesmerize", level=23, spell_type="Mesmerize")
            ]
        )
        first_add = behavior.RequiredTargetObservation(
            object_id=22,
            name="winter wolf",
            x=500,
            y=0,
            z=0,
            level=48,
            has_aggro=True,
            target="cleric",
        )
        second_add = behavior.RequiredTargetObservation(
            object_id=23,
            name="winter dirge",
            x=700,
            y=0,
            z=0,
            level=48,
            has_aggro=True,
            target="leader",
        )
        args = SimpleNamespace(
            crowd_control_interval=3.0,
            crowd_control_health_floor=0,
            crowd_control_preemptive_min_threats=2,
            player_level=50,
            party_rescue_ignore_low_level_delta=0,
            party_encounter_mode="boss",
            max_target_level=50,
            max_target_level_delta=0,
        )

        self.assertTrue(
            behavior.should_use_crowd_control_for_multi_aggro(
                args,
                plan,
                None,
                current_target=0,
                health_percent=100,
                now=10.0,
                next_crowd_control=0.0,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                party_snapshot=state.snapshot(),
                observed_npcs=[first_add, second_add],
            )
        )

    def test_crowd_control_target_prefers_add_targeting_party_member(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        client = FakeClient()
        args = SimpleNamespace(
            player_level=50,
            party_rescue_ignore_low_level_delta=0,
            party_encounter_mode="boss",
            max_target_level=50,
            max_target_level_delta=0,
            required_target_home=None,
            combat_home_leash_distance=0.0,
            require_target_name="moorlich",
            objective_add_target_name="",
        )
        random_aggro = behavior.RequiredTargetObservation(
            object_id=21,
            name="nearby drake",
            x=100,
            y=0,
            z=0,
            level=48,
            has_aggro=True,
            target="",
        )
        party_aggro = behavior.RequiredTargetObservation(
            object_id=22,
            name="winter wolf",
            x=800,
            y=0,
            z=0,
            level=48,
            has_aggro=True,
            target="cleric",
        )

        target = behavior.choose_multi_aggro_crowd_control_target(
            client,
            args,
            {"target_id": 99, "target_name": "moorlich"},
            current_target=99,
            party_snapshot=state.snapshot(),
            api_observations=[random_aggro, party_aggro],
        )

        self.assertEqual(target.object_id, 22)

    def test_crowd_control_target_can_be_selected_before_primary_target(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        client = FakeClient()
        args = SimpleNamespace(
            player_level=50,
            party_rescue_ignore_low_level_delta=0,
            party_encounter_mode="boss",
            max_target_level=50,
            max_target_level_delta=0,
            required_target_home=None,
            combat_home_leash_distance=0.0,
            require_target_name="",
            objective_add_target_name="",
            hunter_target_api_max_age=60.0,
        )
        party_aggro = behavior.RequiredTargetObservation(
            object_id=22,
            name="winter wolf",
            x=800,
            y=0,
            z=0,
            level=48,
            has_aggro=True,
            target="cleric",
        )

        target = behavior.choose_multi_aggro_crowd_control_target(
            client,
            args,
            None,
            current_target=0,
            party_snapshot=state.snapshot(),
            api_observations=[party_aggro],
        )

        self.assertEqual(target.object_id, 22)

    def test_crowd_control_spell_prefers_stun_for_add_targeting_party_member(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        add = FakeNpc(22, "winter wolf", 48, 800.0)
        add.target = "cleric"
        spells = [
            behavior.UsableSpellRef(line_index=1, spell_level=23, name="Mesmerize", level=23, spell_type="Mesmerize"),
            behavior.UsableSpellRef(line_index=2, spell_level=17, name="Stun", level=17, spell_type="Stun"),
            behavior.UsableSpellRef(line_index=3, spell_level=30, name="Root", level=30, spell_type="SpeedDecrease"),
        ]

        spell = behavior.choose_crowd_control_spell(
            SimpleNamespace(combat_plan_spell_pool=3),
            spells,
            add,
            party_snapshot=state.snapshot(),
        )

        self.assertEqual(spell.name, "Stun")

    def test_crowd_control_spell_prefers_mez_for_unfocused_add(self):
        add = FakeNpc(22, "winter wolf", 48, 800.0)
        spells = [
            behavior.UsableSpellRef(line_index=2, spell_level=17, name="Stun", level=17, spell_type="Stun"),
            behavior.UsableSpellRef(line_index=3, spell_level=30, name="Root", level=30, spell_type="SpeedDecrease"),
            behavior.UsableSpellRef(line_index=1, spell_level=23, name="Mesmerize", level=23, spell_type="Mesmerize"),
        ]

        spell = behavior.choose_crowd_control_spell(
            SimpleNamespace(combat_plan_spell_pool=3),
            spells,
            add,
            party_snapshot={},
        )

        self.assertEqual(spell.name, "Mesmerize")

    def test_crowd_control_retry_delay_is_shorter_than_full_interval(self):
        self.assertEqual(behavior.crowd_control_retry_delay(SimpleNamespace(crowd_control_interval=10.0)), 5.0)
        self.assertEqual(behavior.crowd_control_retry_delay(SimpleNamespace(crowd_control_interval=0.0)), 1.0)

    def test_rotation_prefers_validated_taunt_spell_when_taunt_requested(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            combat_plan_spell_pool=3,
            combat_plan_skill_pool=3,
            support_spell_chance=0.0,
            healer_self_health_percent=65,
            allow_unvalidated_spells=False,
            allow_unvalidated_skills=False,
            stationary_cast_actions=False,
        )
        plan = behavior.CombatUsablePlan(
            attack_spells=[behavior.UsableSpellRef(line_index=1, spell_level=10, name="Smite", level=10)],
            taunt_spells=[behavior.UsableSpellRef(line_index=2, spell_level=14, name="Taunt", level=14, spell_type="Taunt")],
        )

        action = behavior.perform_rotation_action(
            client,
            __import__("random").Random(1),
            args,
            "caster-basic",
            800,
            plan,
            prefer_taunt_skill=True,
        )

        self.assertEqual(action, "validated_taunt_spell")
        self.assertEqual(client.spells, [(14, 2)])

    def test_rotation_uses_validated_debuff_spell_when_no_damage_spell_available(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            combat_plan_spell_pool=3,
            support_spell_chance=1.0,
            healer_self_health_percent=65,
            allow_unvalidated_spells=False,
            stationary_cast_actions=False,
        )
        plan = behavior.CombatUsablePlan(
            debuff_spells=[
                behavior.UsableSpellRef(line_index=4, spell_level=18, name="Weakness", level=18, spell_type="StrengthDebuff")
            ]
        )

        action = behavior.perform_rotation_action(client, __import__("random").Random(1), args, "caster-basic", 800, plan)

        self.assertEqual(action, "validated_debuff_spell")
        self.assertEqual(client.spells, [(18, 4)])

    def test_rotation_uses_dot_once_then_direct_spell_until_refresh(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            combat_plan_spell_pool=3,
            support_spell_chance=1.0,
            healer_self_health_percent=65,
            allow_unvalidated_spells=False,
            stationary_cast_actions=False,
        )
        plan = behavior.CombatUsablePlan(
            dot_spells=[
                behavior.UsableSpellRef(
                    line_index=3,
                    spell_level=14,
                    name="Lingering Venom",
                    level=14,
                    spell_type="DamageOverTime",
                    range=1500,
                    duration=24000,
                )
            ],
            attack_spells=[behavior.UsableSpellRef(line_index=1, spell_level=10, name="Smite", level=10, range=1500)],
        )
        active_combat: dict[str, object] = {"target_id": 22}

        first = behavior.perform_rotation_action(
            client,
            __import__("random").Random(1),
            args,
            "caster-basic",
            800,
            plan,
            active_combat=active_combat,
            now=10.0,
        )
        second = behavior.perform_rotation_action(
            client,
            __import__("random").Random(1),
            args,
            "caster-basic",
            800,
            plan,
            active_combat=active_combat,
            now=12.0,
        )

        self.assertEqual(first, "validated_dot_spell")
        self.assertEqual(second, "validated_spell")
        self.assertEqual(client.spells, [(14, 3), (10, 1)])

    def test_rotation_area_spell_requires_multiple_enemies(self):
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            combat_plan_spell_pool=3,
            support_spell_chance=1.0,
            healer_self_health_percent=65,
            allow_unvalidated_spells=False,
            stationary_cast_actions=False,
        )
        plan = behavior.CombatUsablePlan(
            area_attack_spells=[
                behavior.UsableSpellRef(
                    line_index=4,
                    spell_level=18,
                    name="Storm Burst",
                    level=18,
                    target="Enemy",
                    range=1500,
                    radius=350,
                )
            ],
            attack_spells=[behavior.UsableSpellRef(line_index=1, spell_level=10, name="Smite", level=10, range=1500)],
        )
        single_client = FakeCombatClient()
        multi_client = FakeCombatClient()

        single = behavior.perform_rotation_action(
            single_client,
            __import__("random").Random(1),
            args,
            "caster-basic",
            800,
            plan,
            area_enemy_count=1,
        )
        multi = behavior.perform_rotation_action(
            multi_client,
            __import__("random").Random(1),
            args,
            "caster-basic",
            800,
            plan,
            area_enemy_count=2,
        )

        self.assertEqual(single, "validated_spell")
        self.assertEqual(single_client.spells, [(10, 1)])
        self.assertEqual(multi, "validated_area_spell")
        self.assertEqual(multi_client.spells, [(18, 4)])

    def test_area_dot_requires_multiple_enemies_and_refreshes(self):
        client = FakeCombatClient()
        args = SimpleNamespace(
            attack_range=120,
            spell_range=1500,
            combat_plan_spell_pool=3,
            support_spell_chance=1.0,
            healer_self_health_percent=65,
            allow_unvalidated_spells=False,
            stationary_cast_actions=False,
            area_spell_min_targets=2,
        )
        plan = behavior.CombatUsablePlan(
            dot_spells=[
                behavior.UsableSpellRef(
                    line_index=4,
                    spell_level=18,
                    name="Rotting Cloud",
                    level=18,
                    spell_type="AOEDamageOverTime",
                    target="AREA",
                    range=1500,
                    radius=350,
                    duration=24000,
                )
            ],
            attack_spells=[behavior.UsableSpellRef(line_index=1, spell_level=10, name="Smite", level=10, range=1500)],
        )
        active_combat: dict[str, object] = {"target_id": 22}

        single = behavior.perform_rotation_action(
            client,
            __import__("random").Random(1),
            args,
            "caster-basic",
            800,
            plan,
            active_combat=active_combat,
            now=10.0,
            area_enemy_count=1,
        )
        multi = behavior.perform_rotation_action(
            client,
            __import__("random").Random(1),
            args,
            "caster-basic",
            800,
            plan,
            active_combat=active_combat,
            now=12.0,
            area_enemy_count=2,
        )
        refreshed = behavior.perform_rotation_action(
            client,
            __import__("random").Random(1),
            args,
            "caster-basic",
            800,
            plan,
            active_combat=active_combat,
            now=14.0,
            area_enemy_count=2,
        )

        self.assertEqual(single, "validated_spell")
        self.assertEqual(multi, "validated_dot_spell")
        self.assertEqual(refreshed, "validated_spell")

    def test_combat_plan_classifies_party_protection_abilities(self):
        payload = {
            "skills": [
                {
                    "kind": "Ability",
                    "useSkillIndex": 8,
                    "useSkillType": 1,
                    "name": "Guard",
                    "id": 8,
                    "internalId": "Guard",
                    "level": 5,
                    "ability": {"specLevelRequirement": 5, "spec": "Shield"},
                },
                {
                    "kind": "Ability",
                    "useSkillIndex": 7,
                    "useSkillType": 1,
                    "name": "Protect",
                    "id": 7,
                    "internalId": "Protect",
                    "level": 3,
                    "ability": {"specLevelRequirement": 3, "spec": "Shield"},
                },
            ],
            "spellLines": [],
        }

        plan = behavior.parse_combat_usable_plan(payload)

        self.assertEqual([ability.name for ability in plan.guard_abilities], ["Guard"])
        self.assertEqual([ability.name for ability in plan.protect_abilities], ["Protect"])
        self.assertEqual([ability.name for ability in plan.party_protection_abilities], ["Guard", "Protect"])

    def test_party_protection_ability_targets_alive_support_member(self):
        client = FakeCombatClient()
        client.target_calls = []
        client.target_object = lambda object_id, **_kwargs: client.target_calls.append(object_id) or 0
        state = behavior.PartyState("tank", ["tank", "cleric", "dps"])
        state.update_member_role("tank", "melee-basic")
        state.update_member_role("cleric", "healer-support")
        state.update_member_role("dps", "melee-burst")
        state.update_member("tank", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        state.update_member("dps", SimpleNamespace(player_object_id=12, health_percent=100, x=0, y=0, z=0))
        ability = behavior.UsableAbilityRef(use_skill_index=8, use_skill_type=1, name="Guard", level=5, category="guard")

        target = behavior.choose_party_protection_target(state, exclude_name="tank")
        action = behavior.perform_party_protection_ability(client, ability, target)

        self.assertEqual(target["name"], "cleric")
        self.assertEqual(action, "validated_party_guard_member")
        self.assertEqual(client.target_calls, [11])
        self.assertEqual(client.skills, [(8, 1)])

    def test_party_protection_can_run_while_tank_has_enemy_target(self):
        state = behavior.PartyState("tank", ["tank", "cleric"])
        state.update_member_role("tank", "melee-basic")
        state.update_member_role("cleric", "healer-support")
        state.update_member("tank", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        ability = behavior.UsableAbilityRef(use_skill_index=8, use_skill_type=1, name="Guard", level=5, category="guard")
        plan = behavior.CombatUsablePlan(party_protection_abilities=[ability])

        self.assertTrue(
            behavior.should_use_party_protection_ability(
                SimpleNamespace(party_protection_interval=10.0),
                plan,
                state,
                action_rotation="melee-basic",
                is_party_leader=True,
                party_member_name="tank",
                current_target=23268,
                behavior_state=behavior.DummyBehaviorState.HuntObjective,
                now=30.0,
                next_party_protection=20.0,
            )
        )

    def test_party_protection_target_prefers_external_member_under_pressure(self):
        state = behavior.PartyState("tank", ["tank", "cleric", "dps"])
        state.update_member_role("tank", "melee-basic")
        state.update_member_role("cleric", "healer-support")
        state.update_member_role("dps", "melee-burst")
        state.update_member("tank", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        state.update_member("dps", SimpleNamespace(player_object_id=12, health_percent=100, x=0, y=0, z=0))
        state.update_external_member(
            "RealPlayer",
            SimpleNamespace(object_id=90, health_percent=35, x=20, y=0, z=0),
            role="external",
        )
        state.update_shared_target(
            behavior.RequiredTargetObservation(
                object_id=100,
                name="Moran the Mighty",
                x=10,
                y=20,
                z=30,
                level=73,
                target="RealPlayer",
            ),
            engaged=True,
        )

        target = behavior.choose_party_protection_target(state, exclude_name="tank")

        self.assertIsNotNone(target)
        self.assertEqual(target["name"], "RealPlayer")

    def test_player_condition_snapshot_parses_curable_status_flags(self):
        payload = {
            "player": {
                "name": "Cleric",
                "account": "cleric001",
                "objectId": 77,
                "healthPercent": 90,
                "x": 10,
                "y": 20,
                "z": 30,
                "isAlive": True,
                "isMezzed": True,
                "isDiseased": False,
                "isPoisoned": True,
                "isNearsighted": False,
                "isSilenced": False,
            }
        }

        snapshot = behavior.parse_player_condition_snapshot(payload)

        self.assertEqual(snapshot.name, "Cleric")
        self.assertEqual(snapshot.object_id, 77)
        self.assertEqual((snapshot.x, snapshot.y, snapshot.z), (10, 20, 30))
        self.assertTrue(snapshot.is_mezzed)
        self.assertTrue(snapshot.is_poisoned)
        self.assertEqual(snapshot.curable_conditions(), {"mezz", "poison"})

    def test_player_condition_snapshots_parse_group_members(self):
        payload = {
            "player": {
                "name": "Cleric",
                "account": "cleric001",
                "objectId": 77,
                "healthPercent": 90,
                "isAlive": True,
            },
            "groupMembers": [
                {
                    "name": "Cleric",
                    "account": "cleric001",
                    "objectId": 77,
                    "healthPercent": 90,
                    "isAlive": True,
                },
                {
                    "name": "RealPlayer",
                    "account": "real001",
                    "objectId": 91,
                    "healthPercent": 0,
                    "x": 10,
                    "y": 20,
                    "z": 30,
                    "isAlive": False,
                    "isMezzed": True,
                },
            ],
        }

        snapshots = behavior.parse_player_condition_snapshots(payload)

        self.assertEqual([snapshot.name for snapshot in snapshots], ["Cleric", "RealPlayer"])
        self.assertFalse(snapshots[1].is_alive)
        self.assertIn("mezz", snapshots[1].curable_conditions())

    def test_player_condition_snapshot_keeps_combat_role_metadata(self):
        snapshot = behavior.parse_player_condition_snapshot(
            {
                "player": {
                    "name": "RealTank",
                    "objectId": 91,
                    "class": "Armsman",
                    "classId": 2,
                    "isCompanion": False,
                    "companionRole": "",
                }
            }
        )

        self.assertEqual(snapshot.class_name, "Armsman")
        self.assertEqual(snapshot.class_id, 2)
        self.assertFalse(snapshot.is_companion)
        self.assertEqual(behavior.party_role_from_condition(snapshot), "melee-basic")

    def test_party_class_profile_identifies_stealth_and_speed_song_classes(self):
        speed_classes = [
            ("Minstrel", 4),
            ("Skald", 24),
            ("Bard", 48),
        ]
        stealth_classes = [
            ("Scout", 3),
            ("Infiltrator", 9),
            ("Shadowblade", 23),
            ("Hunter", 25),
            ("Nightshade", 49),
            ("Ranger", 50),
        ]

        for class_name, class_id in speed_classes:
            with self.subTest(class_name=class_name):
                capabilities = behavior.party_class_capabilities_from_class(class_name, class_id)
                self.assertIn("speed_song", capabilities)

        for class_name, class_id in stealth_classes:
            with self.subTest(class_name=class_name):
                capabilities = behavior.party_class_capabilities_from_class(class_name, class_id)
                self.assertIn("stealth", capabilities)

        minstrel_profile = behavior.party_class_role_profile_from_class("Minstrel", 4)
        scout_profile = behavior.party_class_role_profile_from_class("Scout", 3)
        bard_profile = behavior.party_class_role_profile_from_class("Bard", 48)

        self.assertEqual(minstrel_profile.role_group, "speed-support")
        self.assertIn("stealth", minstrel_profile.capabilities)
        self.assertEqual(scout_profile.role_group, "stealth-scout")
        self.assertIn("ranged", scout_profile.capabilities)
        self.assertEqual(bard_profile.action_rotation, "healer-support")
        self.assertEqual(behavior.party_role_from_class("Bard", 48), "healer-support")

    def test_party_class_profile_covers_core_daoc_class_features(self):
        expected = {
            "Paladin": {"tank", "shield", "melee_dps", "buff", "chant", "resurrection"},
            "Theurgist": {"caster", "pet", "crowd_control", "bladeturn"},
            "Sorcerer": {"caster", "crowd_control", "charm", "debuff"},
            "Heretic": {"healer", "resurrection", "caster", "debuff"},
            "Bonedancer": {"caster", "pet", "lifedrain"},
            "Healer": {"healer", "resurrection", "cure", "crowd_control"},
            "Shaman": {"healer", "resurrection", "cure", "buff", "disease"},
            "Valkyrie": {"tank", "shield", "melee_dps", "healer", "caster"},
            "Animist": {"caster", "pet", "turret", "crowd_control"},
            "Druid": {"healer", "resurrection", "cure", "buff", "pet"},
            "Warden": {"healer", "resurrection", "cure", "buff", "bladeturn"},
            "Vampiir": {"melee_dps", "caster", "buff", "debuff", "stealth_detection"},
        }

        for class_name, tags in expected.items():
            with self.subTest(class_name=class_name):
                capabilities = behavior.party_class_capabilities_from_class(class_name)
                self.assertTrue(tags.issubset(capabilities), f"{class_name}: {tags - capabilities}")

    def test_party_cure_target_prefers_member_with_matching_cure_spell(self):
        state = behavior.PartyState("tank", ["tank", "cleric", "dps"])
        state.update_member("tank", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        state.update_member("dps", SimpleNamespace(player_object_id=12, health_percent=100, x=0, y=0, z=0))
        state.update_member_condition(
            "dps",
            behavior.PlayerConditionSnapshot(name="dps", object_id=12, is_poisoned=True),
        )
        plan = behavior.CombatUsablePlan(
            cure_spells=[
                behavior.UsableSpellRef(line_index=2, spell_level=8, name="Cure Disease", level=8, spell_type="CureDisease"),
                behavior.UsableSpellRef(line_index=3, spell_level=9, name="Cure Poison", level=9, spell_type="CurePoison"),
            ]
        )

        target, spell = behavior.choose_party_cure_target(state, plan, exclude_name="cleric")

        self.assertEqual(target["name"], "dps")
        self.assertEqual(spell.name, "Cure Poison")

    def test_party_cure_cast_targets_condition_member(self):
        client = FakeCombatClient()
        client.target_calls = []
        client.target_object = lambda object_id, **_kwargs: client.target_calls.append(object_id) or 0
        args = behavior.build_parser().parse_args([])
        target = {"name": "dps", "object_id": 12, "condition": "poison", "x": 0, "y": 0, "z": 0}
        spell = behavior.UsableSpellRef(line_index=3, spell_level=9, name="Cure Poison", level=9, spell_type="CurePoison")

        action = behavior.perform_party_cure_cast(client, spell, args, target)

        self.assertEqual(action, "validated_party_cure_poison")
        self.assertEqual(client.target_calls, [12])
        self.assertEqual(client.spells, [(9, 3)])

    def test_external_party_member_is_supported_but_not_counted_ready(self):
        state = behavior.PartyState("leader", ["leader", "dummy"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("dummy", SimpleNamespace(player_object_id=11, health_percent=100, x=10, y=0, z=0))
        state.update_external_member(
            "RealPlayer",
            SimpleNamespace(object_id=90, health_percent=35, x=20, y=0, z=0),
            role="external",
        )
        state.mark_ready("RealPlayer")

        snapshot = state.snapshot()
        target = behavior.choose_party_heal_target(
            state,
            SimpleNamespace(party_heal_leader_health_percent=80, healer_self_health_percent=65),
            exclude_name="dummy",
        )
        buff_targets = state.buff_targets(exclude_name="dummy")

        self.assertIn("RealPlayer", [member["name"] for member in snapshot["members"]])
        self.assertEqual(snapshot["external_member_names"], ["RealPlayer"])
        self.assertEqual(snapshot["managed_member_names"], ["leader", "dummy"])
        self.assertEqual(snapshot["ready_names"], ["leader"])
        self.assertEqual(target["name"], "RealPlayer")
        self.assertIn("RealPlayer", [member["name"] for member in buff_targets])

    def test_external_party_member_can_be_resurrected_and_cured(self):
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_member("leader", SimpleNamespace(player_object_id=10, health_percent=100, x=0, y=0, z=0))
        state.update_member("cleric", SimpleNamespace(player_object_id=11, health_percent=100, x=0, y=0, z=0))
        state.update_external_member(
            "RealPlayer",
            SimpleNamespace(object_id=90, health_percent=0, x=25, y=0, z=0),
            role="external",
        )
        resurrect_targets = state.resurrection_targets(exclude_name="cleric")
        state.update_member_condition(
            "RealPlayer",
            behavior.PlayerConditionSnapshot(name="RealPlayer", object_id=90, health_percent=100, is_diseased=True),
        )
        plan = behavior.CombatUsablePlan(
            cure_spells=[
                behavior.UsableSpellRef(line_index=2, spell_level=8, name="Cure Disease", level=8, spell_type="CureDisease")
            ]
        )

        cure_target, cure_spell = behavior.choose_party_cure_target(state, plan, exclude_name="cleric")

        self.assertEqual(resurrect_targets[0]["name"], "RealPlayer")
        self.assertEqual(cure_target["name"], "RealPlayer")
        self.assertEqual(cure_spell.name, "Cure Disease")

    def test_party_healer_support_policy_allows_leader_support_actions(self):
        state = behavior.PartyState("cleric", ["cleric", "tank"])

        self.assertTrue(behavior.is_party_support_healer_member(state, "healer-support"))
        self.assertFalse(behavior.is_party_support_healer_member(state, "melee-basic"))
        self.assertFalse(behavior.is_party_support_healer_member(None, "healer-support"))

    def test_party_state_managed_invite_names_excludes_external_players(self):
        state = behavior.PartyState("leader", ["leader", "dummy"])
        state.update_external_member("RealPlayer", SimpleNamespace(object_id=90, health_percent=100, x=0, y=0, z=0))

        self.assertEqual(state.managed_invite_names(), ["dummy"])

    def test_build_party_states_registers_configured_external_players_as_support_only(self):
        args = SimpleNamespace(
            party_size=2,
            party_active_tank_handoff_health_percent=0,
            party_external_member_names=["RealPlayer", "Dummy001"],
        )
        account_plans = [
            [behavior.DummyAccount("dummy001", "", 1, 0)],
            [behavior.DummyAccount("dummy002", "", 1, 0)],
        ]

        states = behavior.build_party_states(account_plans, args)
        snapshot = states[0].snapshot()

        self.assertIs(states[0], states[1])
        self.assertEqual(snapshot["managed_member_names"], ["Dummy001", "Dummy002"])
        self.assertEqual(snapshot["external_member_names"], ["RealPlayer"])
        self.assertEqual(snapshot["ready_names"], ["Dummy001"])
        self.assertEqual(states[0].managed_invite_names(), ["Dummy002"])
        self.assertIn("RealPlayer", [member["name"] for member in snapshot["members"]])

    def test_build_party_states_uses_external_player_as_leader_for_single_live_companion(self):
        args = SimpleNamespace(
            party_size=1,
            party_active_tank_handoff_health_percent=0,
            party_external_member_names=["RealLeader"],
        )
        account_plans = [[behavior.DummyAccount("albtest002", "", 1, 0)]]

        states = behavior.build_party_states(account_plans, args)
        snapshot = states[0].snapshot()

        self.assertEqual(snapshot["leader_name"], "RealLeader")
        self.assertEqual(snapshot["managed_member_names"], ["Albtest002"])
        self.assertEqual(snapshot["external_member_names"], ["RealLeader"])
        self.assertTrue(behavior.party_state_member_is_leader(states[0], "RealLeader"))
        self.assertFalse(behavior.party_state_member_is_leader(states[0], "Albtest002"))

    def test_parser_accepts_external_party_member_names(self):
        args = behavior.build_parser().parse_args(["--party-external-member-names", "RealPlayer|Friend,Other"])

        self.assertEqual(args.party_external_member_names, ["RealPlayer", "Friend", "Other"])

    def test_parser_accepts_party_cure_and_condition_refresh_intervals(self):
        args = behavior.build_parser().parse_args(
            ["--party-cure-interval", "1.5", "--party-condition-refresh-interval", "2.5"]
        )

        self.assertEqual(args.party_cure_interval, 1.5)
        self.assertEqual(args.party_condition_refresh_interval, 2.5)

    def test_party_buff_candidate_respects_per_target_spell_cooldown(self):
        target = {"name": "RealPlayer", "object_id": 90}
        spell = behavior.UsableSpellRef(line_index=3, spell_level=8, name="Shield Aura", level=8)
        cooldowns = {behavior.party_buff_key(target, spell): 40.0}

        self.assertFalse(behavior.party_buff_candidate_available(target, spell, cooldowns, now=20.0))
        self.assertTrue(behavior.party_buff_candidate_available(target, spell, cooldowns, now=41.0))

    def test_external_party_visible_player_update_uses_configured_name_and_preserves_health(self):
        args = SimpleNamespace(party_external_member_names=["RealPlayer"], player_state_max_age=5.0)
        state = behavior.PartyState("leader", ["leader"])
        state.update_external_member("RealPlayer", SimpleNamespace(object_id=90, health_percent=35, x=1, y=2, z=3))
        player = FakePlayer(91, "realplayer", 100)
        player.x = 40
        player.y = 50
        player.z = 60
        client = FakeClient(players=[player])

        updated = behavior.update_external_party_members_from_visible_players(state, client, args)
        member = next(member for member in state.snapshot()["members"] if member["name"] == "RealPlayer")

        self.assertEqual(updated, 1)
        self.assertEqual(member["object_id"], 91)
        self.assertEqual(member["health_percent"], 35)
        self.assertEqual((member["x"], member["y"], member["z"]), (40, 50, 60))

    def test_external_party_visible_player_update_ignores_unconfigured_players(self):
        args = SimpleNamespace(party_external_member_names=["RealPlayer"], player_state_max_age=5.0)
        state = behavior.PartyState("leader", ["leader"])
        client = FakeClient(players=[FakePlayer(91, "Stranger", 100)])

        updated = behavior.update_external_party_members_from_visible_players(state, client, args)

        self.assertEqual(updated, 0)
        self.assertEqual(state.snapshot()["external_member_names"], [])

    def test_choose_rvr_enemy_player_filters_same_realm_and_party_members(self):
        args = SimpleNamespace(
            player_state_max_age=5.0,
            rvr_enemy_player_max_distance=2500.0,
            rvr_enemy_player_min_level=0,
            rvr_enemy_player_max_level=0,
            rvr_enemy_player_name="",
        )
        state = behavior.PartyState("leader", ["leader"])
        state.update_external_member("RealPlayer", SimpleNamespace(object_id=91, health_percent=100, x=0, y=0, z=0))
        same_realm = FakePlayer(90, "AlbFriend", 50, realm=1, level=50)
        external_party = FakePlayer(91, "RealPlayer", 40, realm=2, level=50)
        enemy = FakePlayer(92, "MidEnemy", 120, realm=2, level=50)
        client = FakeClient(players=[same_realm, external_party, enemy])

        selected = behavior.choose_rvr_enemy_player(
            client,
            args,
            own_realm=1,
            party_snapshot=state.snapshot(),
            rejected_targets={},
            now=100.0,
        )

        self.assertIs(selected, enemy)

    def test_choose_rvr_enemy_player_prefers_shared_enemy_target(self):
        args = SimpleNamespace(
            player_state_max_age=5.0,
            rvr_enemy_player_max_distance=2500.0,
            rvr_enemy_player_min_level=0,
            rvr_enemy_player_max_level=0,
            rvr_enemy_player_name="",
        )
        near_enemy = FakePlayer(92, "NearEnemy", 80, realm=2, level=50)
        shared_enemy = FakePlayer(93, "SharedEnemy", 500, realm=2, level=50)
        client = FakeClient(players=[near_enemy, shared_enemy])

        selected = behavior.choose_rvr_enemy_player(
            client,
            args,
            own_realm=1,
            party_snapshot={},
            rejected_targets={},
            now=100.0,
            prefer_object_id=93,
        )

        self.assertIs(selected, shared_enemy)

    def test_choose_named_rvr_enemy_player_matches_incoming_attacker_name(self):
        args = SimpleNamespace(
            player_state_max_age=5.0,
            rvr_enemy_player_max_distance=2500.0,
            rvr_enemy_player_min_level=0,
            rvr_enemy_player_max_level=0,
            rvr_enemy_player_name="",
        )
        enemy = FakePlayer(92, "GrowthAlb9800", 180, realm=1, level=50)
        client = FakeClient(players=[enemy])

        selected = behavior.choose_named_rvr_enemy_player(
            client,
            args,
            "GrowthAlb9800",
            own_realm=2,
            party_snapshot={},
            rejected_targets={},
            now=100.0,
        )

        self.assertIs(selected, enemy)

    def test_player_condition_snapshot_actor_can_confirm_rvr_damage_attacker(self):
        args = SimpleNamespace(
            rvr_enemy_player_max_distance=2500.0,
            rvr_enemy_player_min_level=0,
            rvr_enemy_player_max_level=0,
            rvr_enemy_player_name="",
        )
        snapshot = behavior.parse_player_condition_snapshot(
            {
                "player": {
                    "name": "GrowthAlb9800",
                    "objectId": 92,
                    "level": 50,
                    "realm": "Albion",
                    "x": 100,
                    "y": 0,
                    "z": 10,
                    "isAlive": True,
                }
            }
        )
        actor = behavior.rvr_enemy_player_actor_from_condition_snapshot(snapshot)
        client = FakeClient()

        self.assertEqual(snapshot.realm, 1)
        self.assertIsNotNone(actor)
        self.assertTrue(
            behavior.player_is_rvr_enemy_candidate(
                client,
                args,
                actor,
                own_realm=2,
                party_snapshot={},
                rejected_targets={},
                now=100.0,
            )
        )

    def test_parse_player_condition_snapshot_accepts_api_realm_enum_names(self):
        self.assertEqual(behavior.parse_realm_id_value("_FirstPlayerRealm"), 1)
        self.assertEqual(behavior.parse_realm_id_value("_SecondPlayerRealm"), 2)
        self.assertEqual(behavior.parse_realm_id_value("_ThirdPlayerRealm"), 3)

    def test_probable_account_from_character_name_keeps_dummy_growth_mapping(self):
        self.assertEqual(behavior.probable_account_from_character_name("GrowthMid10100"), "growthmid10100")
        self.assertEqual(behavior.probable_account_from_character_name("Dummy040"), "dummy040")

    def test_target_id_is_party_member_includes_external_members(self):
        state = behavior.PartyState("leader", ["leader"])
        state.update_external_member("RealPlayer", SimpleNamespace(object_id=91, health_percent=100, x=0, y=0, z=0))

        self.assertTrue(behavior.target_id_is_party_member(91, state.snapshot()))
        self.assertFalse(behavior.target_id_is_party_member(92, state.snapshot()))

    def test_refresh_party_condition_snapshots_updates_managed_and_external_members(self):
        args = SimpleNamespace(combat_usable_api=True, party_external_member_names=["RealPlayer"])
        account = behavior.DummyAccount("cleric", "", 1, 0)
        state = behavior.PartyState("leader", ["leader", "cleric"])
        state.update_external_member("RealPlayer", SimpleNamespace(object_id=90, health_percent=100, x=0, y=0, z=0))

        def fake_fetch(_args, name, account_name=""):
            if name == "cleric" and account_name == "cleric":
                return behavior.PlayerConditionSnapshot(name="cleric", object_id=11, health_percent=100, is_poisoned=True, x=1, y=2, z=3)
            if name == "RealPlayer":
                return behavior.PlayerConditionSnapshot(name="RealPlayer", object_id=90, health_percent=75, is_mezzed=True, x=4, y=5, z=6)
            return None

        updated = behavior.refresh_party_condition_snapshots(
            state,
            args,
            account,
            "cleric",
            fetch_condition=fake_fetch,
        )
        snapshot = state.snapshot()

        self.assertEqual(updated, 2)
        self.assertIn("poison", state.member_conditions["cleric"].curable_conditions())
        self.assertIn("mezz", state.member_conditions["RealPlayer"].curable_conditions())
        real_member = next(member for member in snapshot["members"] if member["name"] == "RealPlayer")
        self.assertEqual(real_member["health_percent"], 75)
        self.assertEqual((real_member["x"], real_member["y"], real_member["z"]), (4, 5, 6))

    def test_parse_party_condition_snapshot_keeps_external_leader_target(self):
        snapshot = behavior.parse_player_condition_snapshot(
            {
                "player": {
                    "name": "RealLeader",
                    "objectId": 90,
                    "targetObjectId": 345,
                    "targetName": "moorlich",
                }
            }
        )

        self.assertEqual(snapshot.target_object_id, 345)
        self.assertEqual(snapshot.target_name, "moorlich")

    def test_external_leader_condition_updates_party_leader_target(self):
        state = behavior.PartyState("RealLeader", ["Albtest002"])
        state.update_external_member("RealLeader", SimpleNamespace(object_id=90, health_percent=100, x=0, y=0, z=0))
        state.update_member_condition(
            "RealLeader",
            behavior.PlayerConditionSnapshot(
                name="RealLeader",
                object_id=90,
                health_percent=100,
                x=100,
                y=200,
                z=300,
                target_object_id=345,
                target_name="moorlich",
            ),
        )
        snapshot = state.snapshot()

        self.assertEqual(snapshot["leader_object_id"], 90)
        self.assertEqual((snapshot["leader_x"], snapshot["leader_y"], snapshot["leader_z"]), (100, 200, 300))
        self.assertEqual(snapshot["leader_target_id"], 345)
        self.assertEqual(snapshot["leader_target_name"], "moorlich")
        self.assertGreater(snapshot["leader_target_engaged_at"], 0.0)

    def test_external_leader_condition_clears_stale_party_leader_target(self):
        state = behavior.PartyState("RealLeader", ["Albtest002"])
        state.update_external_member("RealLeader", SimpleNamespace(object_id=90, health_percent=100, x=0, y=0, z=0))
        state.update_member_condition(
            "RealLeader",
            behavior.PlayerConditionSnapshot(name="RealLeader", object_id=90, target_object_id=345, target_name="moorlich"),
        )
        state.update_member_condition(
            "RealLeader",
            behavior.PlayerConditionSnapshot(name="RealLeader", object_id=90, target_object_id=0, target_name=""),
        )

        self.assertEqual(state.snapshot()["leader_target_id"], 0)

    def test_party_anchor_prefers_external_leader_over_managed_tank(self):
        state = behavior.PartyState("RealLeader", ["Albtest002"])
        state.update_external_member("RealLeader", SimpleNamespace(object_id=90, health_percent=100, x=1000, y=2000, z=3000))
        state.update_member_role("Albtest002", "melee-basic")
        state.update_member("Albtest002", SimpleNamespace(player_object_id=11, health_percent=100, x=4000, y=5000, z=6000))

        anchor = behavior.party_anchor_from_snapshot(state.snapshot())

        self.assertEqual(anchor["name"], "RealLeader")
        self.assertEqual((anchor["x"], anchor["y"], anchor["z"]), (1000, 2000, 3000))

    def test_party_anchor_keeps_managed_leader_anchor_for_managed_party(self):
        state = behavior.PartyState("Leader", ["Leader", "Tank"])
        state.update_member("Leader", SimpleNamespace(player_object_id=90, health_percent=100, x=1000, y=2000, z=3000))
        state.update_member_role("Tank", "melee-basic")
        state.update_member("Tank", SimpleNamespace(player_object_id=11, health_percent=100, x=4000, y=5000, z=6000))

        anchor = behavior.party_anchor_from_snapshot(state.snapshot())

        self.assertEqual(anchor["name"], "Leader")
        self.assertEqual((anchor["x"], anchor["y"], anchor["z"]), (1000, 2000, 3000))

    def test_refresh_party_condition_snapshots_auto_registers_group_player_as_external(self):
        args = SimpleNamespace(
            combat_usable_api=True,
            party_external_member_names=[],
            party_auto_external_members=True,
        )
        account = behavior.DummyAccount("cleric", "", 1, 0)
        state = behavior.PartyState("leader", ["leader", "cleric"])

        def fake_fetch_many(_args, name, account_name=""):
            self.assertEqual((name, account_name), ("cleric", "cleric"))
            return [
                behavior.PlayerConditionSnapshot(name="cleric", object_id=11, health_percent=100, x=1, y=2, z=3),
                behavior.PlayerConditionSnapshot(
                    name="RealPlayer",
                    object_id=90,
                    health_percent=35,
                    is_diseased=True,
                    x=4,
                    y=5,
                    z=6,
                ),
            ]

        updated = behavior.refresh_party_condition_snapshots(
            state,
            args,
            account,
            "cleric",
            fetch_condition=lambda *_args, **_kwargs: None,
            fetch_condition_snapshots=fake_fetch_many,
        )
        snapshot = state.snapshot()

        self.assertEqual(updated, 2)
        self.assertEqual(snapshot["external_member_names"], ["RealPlayer"])
        self.assertEqual(snapshot["managed_member_names"], ["leader", "cleric"])
        self.assertEqual(snapshot["ready_names"], ["leader"])
        real_member = next(member for member in snapshot["members"] if member["name"] == "RealPlayer")
        self.assertEqual(real_member["health_percent"], 35)
        self.assertIn("disease", state.member_conditions["RealPlayer"].curable_conditions())

    def test_refresh_party_condition_snapshots_uses_real_player_tank_role(self):
        args = SimpleNamespace(
            combat_usable_api=True,
            party_external_member_names=[],
            party_auto_external_members=True,
        )
        account = behavior.DummyAccount("cleric", "", 1, 0)
        state = behavior.PartyState("RealLeader", ["cleric"])
        state.update_external_member(
            "RealLeader",
            SimpleNamespace(object_id=80, health_percent=100, x=10, y=20, z=30),
            role="external",
        )

        def fake_fetch_many(_args, name, account_name=""):
            self.assertEqual((name, account_name), ("cleric", "cleric"))
            return [
                behavior.PlayerConditionSnapshot(
                    name="cleric",
                    object_id=11,
                    health_percent=100,
                    x=1,
                    y=2,
                    z=3,
                    class_name="Cleric",
                ),
                behavior.PlayerConditionSnapshot(
                    name="RealLeader",
                    object_id=80,
                    health_percent=100,
                    x=10,
                    y=20,
                    z=30,
                    class_name="Wizard",
                ),
                behavior.PlayerConditionSnapshot(
                    name="RealTank",
                    object_id=90,
                    health_percent=88,
                    x=40,
                    y=50,
                    z=60,
                    class_name="Armsman",
                ),
            ]

        updated = behavior.refresh_party_condition_snapshots(
            state,
            args,
            account,
            "cleric",
            fetch_condition=lambda *_args, **_kwargs: None,
            fetch_condition_snapshots=fake_fetch_many,
        )
        snapshot = state.snapshot()

        self.assertEqual(updated, 3)
        self.assertEqual(snapshot["active_tank_name"], "RealTank")
        roles = {member["name"]: member["role"] for member in snapshot["members"]}
        self.assertEqual(roles["RealLeader"], "caster-basic")
        self.assertEqual(roles["RealTank"], "melee-basic")

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

    def test_precombat_self_buffs_casts_validated_buff_spells_stationary(self):
        client = FakeCombatClient()
        client.last_position_speed = 165.0
        args = SimpleNamespace(startup_self_buff_count=2, startup_self_buff_delay=0.0)
        plan = behavior.CombatUsablePlan(
            buff_spells=[
                behavior.UsableSpellRef(
                    line_index=-1,
                    spell_level=10,
                    name="Chant of Battle",
                    level=10,
                    use_skill_index=21,
                    use_skill_type=1,
                ),
                behavior.UsableSpellRef(line_index=3, spell_level=8, name="Shield Aura", level=8),
            ]
        )
        action_counts: dict[str, int] = {}

        actions = behavior.cast_precombat_self_buffs(client, args, plan, action_counts)

        self.assertEqual(actions, 2)
        self.assertEqual(action_counts["precombat_self_buff_spell"], 2)
        self.assertEqual(client.skills, [(21, 1)])
        self.assertEqual(client.spells, [(8, 3)])
        self.assertEqual(client.position_updates[-1], (0.0, True))

    def test_precombat_self_buffs_respects_count_limit(self):
        client = FakeCombatClient()
        args = SimpleNamespace(startup_self_buff_count=1, startup_self_buff_delay=0.0)
        plan = behavior.CombatUsablePlan(
            buff_spells=[
                behavior.UsableSpellRef(line_index=3, spell_level=8, name="Shield Aura", level=8),
                behavior.UsableSpellRef(line_index=4, spell_level=9, name="Might Aura", level=9),
            ]
        )
        action_counts: dict[str, int] = {}

        actions = behavior.cast_precombat_self_buffs(client, args, plan, action_counts)

        self.assertEqual(actions, 1)
        self.assertEqual(client.spells, [(8, 3)])

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

    def test_friendly_party_cast_holds_even_without_enemy_target(self):
        args = behavior.build_parser().parse_args([])

        hold_until, restore_target = behavior.plan_friendly_cast_target_hold(args, now=10.0, current_target=0)

        self.assertEqual(restore_target, 0)
        self.assertGreater(hold_until, 10.0)

    def test_friendly_party_cast_hold_extends_for_validated_spell_cast_time(self):
        args = behavior.build_parser().parse_args([])
        spell = behavior.UsableSpellRef(
            line_index=1,
            spell_level=30,
            name="Major Heal",
            level=30,
            cast_time=3000,
        )

        hold_until, restore_target = behavior.plan_friendly_cast_target_hold(
            args,
            now=10.0,
            current_target=77,
            minimum_hold_seconds=behavior.friendly_usable_spell_hold_seconds(args, spell),
        )

        self.assertEqual(restore_target, 77)
        self.assertGreaterEqual(hold_until - 10.0, 3.5)

    def test_friendly_party_ability_hold_uses_base_hold_without_spell_cast_time(self):
        args = behavior.build_parser().parse_args(["--party-friendly-cast-target-hold", "1.25"])
        ability = behavior.UsableAbilityRef(
            use_skill_index=8,
            use_skill_type=1,
            name="Guard",
            level=5,
            category="guard",
        )

        hold_until, restore_target = behavior.plan_friendly_cast_target_hold(
            args,
            now=10.0,
            current_target=77,
            minimum_hold_seconds=behavior.friendly_usable_ability_hold_seconds(args, ability),
        )

        self.assertEqual(restore_target, 77)
        self.assertAlmostEqual(hold_until - 10.0, 1.25)

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

    def test_hostile_usable_spell_hold_uses_cast_time_without_stationary_casts(self):
        args = behavior.build_parser().parse_args([])
        spell = behavior.UsableSpellRef(
            line_index=2,
            spell_level=23,
            name="Mesmerize",
            level=23,
            spell_type="Mesmerize",
            cast_time=3000,
        )

        hold_seconds = behavior.hostile_usable_spell_hold_seconds(
            args,
            "validated_crowd_control_spell",
            spell,
        )

        self.assertGreaterEqual(hold_seconds, 3.5)

    def test_hostile_usable_spell_hold_keeps_configured_stationary_minimum(self):
        args = behavior.build_parser().parse_args(["--stationary-cast-actions", "--stationary-cast-min-hold", "4.2"])
        spell = behavior.UsableSpellRef(
            line_index=2,
            spell_level=23,
            name="Quick Stun",
            level=23,
            spell_type="Stun",
            cast_time=1500,
        )

        hold_seconds = behavior.hostile_usable_spell_hold_seconds(
            args,
            "validated_crowd_control_spell",
            spell,
        )

        self.assertAlmostEqual(hold_seconds, 4.2)

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
