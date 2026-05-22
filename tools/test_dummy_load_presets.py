#!/usr/bin/env python3
"""Unit checks for dummy load-test presets."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


def load_module():
    module_path = Path(__file__).with_name("run-dummy-load-test.py")
    spec = importlib.util.spec_from_file_location("run_dummy_load_test_for_tests", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


loadtest = load_module()


class DummyLoadPresetTests(unittest.TestCase):
    def test_ai_filler_presets_exist(self):
        self.assertIn("ai-filler-small", loadtest.PRESETS)
        self.assertIn("ai-filler-medium", loadtest.PRESETS)
        self.assertEqual(loadtest.PRESETS["ai-filler-small"].party_size, 1)

    def test_ai_filler_scenario_uses_ai_player(self):
        scenario = loadtest.SCENARIOS["ai-filler-casual"]

        self.assertTrue(scenario.ai_player)
        self.assertEqual(scenario.behavior_profile, "pve-casual")
        self.assertEqual(scenario.party_role_strategy, "same")

    def test_melee_scenarios_use_realistic_attack_range(self):
        for scenario in loadtest.SCENARIOS.values():
            with self.subTest(scenario=scenario.name):
                self.assertLessEqual(scenario.attack_range, 130)
                self.assertGreaterEqual(scenario.target_timeout, 45)

    def test_beginner_scenarios_can_cap_targets_to_level_zero(self):
        for name in ("newbie-solo", "solo-melee", "ai-pve-casual", "ai-filler-casual"):
            with self.subTest(scenario=name):
                self.assertEqual(loadtest.SCENARIOS[name].min_target_level, 0)
                self.assertEqual(loadtest.SCENARIOS[name].max_target_level, 0)
                self.assertTrue(loadtest.SCENARIOS[name].smooth_movement)

    def test_ai_filler_command_defaults_to_quiet_single_party(self):
        args = SimpleNamespace(
            count=None,
            concurrency=None,
            hold=None,
            party_size=None,
            ramp_up=None,
            rounds=None,
            host="127.0.0.1",
            port=10300,
            behavior_profile=None,
            action_rotation=None,
            realm_strategy="least-populated",
            api_port=5000,
            live_api_url="http://127.0.0.1:5000/api/dashboard/live",
            nav_api_url="http://127.0.0.1:5000",
            ai_player=False,
            ai_persona="auto",
            target_examine_chance=0.20,
            social_interval=75.0,
            social_chance=0.08,
            player_greet_interval=45.0,
            player_greet_chance=0.06,
            emote_interval=55.0,
            emote_chance=0.12,
            look_around_interval=12.0,
            long_rest_chance=0.06,
            follow_player_name="",
            player_follow_interval=2.0,
            player_follow_distance=850.0,
            follow_player_max_distance=3500.0,
            fresh_account_per_round=False,
        )
        command = loadtest.build_behavior_command(
            args,
            loadtest.PRESETS["ai-filler-small"],
            loadtest.SCENARIOS["ai-filler-casual"],
            Path("accounts.csv"),
            Path("metrics.csv"),
            Path("combat.csv"),
            Path("report.md"),
        )

        self.assertIn("--ai-player", command)
        self.assertEqual(command[command.index("--party-size") + 1], "1")
        self.assertEqual(command[command.index("--realm-strategy") + 1], "least-populated")
        self.assertEqual(command[command.index("--max-target-level") + 1], "0")
        self.assertIn("--smooth-movement", command)
        self.assertIn("--ground-z-map", command)
        self.assertIn(loadtest.REGION001_CLIENT_GROUND_Z_MAP, command)
        self.assertIn("--path-graph", command)
        self.assertIn(loadtest.ALBION_LOW_LEVEL_PATH_GRAPH, command)
        self.assertIn("--client-grid-nav-map", command)
        self.assertIn(loadtest.REGION001_CLIENT_GROUND_Z_MAP, command)
        self.assertIn("--path-region", command)
        self.assertIn("--nav-api-url", command)
        self.assertIn("http://127.0.0.1:5000", command)
        self.assertIn("--ai-persona", command)
        self.assertIn("--waypoints", command)
        self.assertIn("--avoid-target-name", command)
        self.assertIn("green snake", command)

    def test_low_level_scenario_provisions_newbie_hunting_ground(self):
        args = SimpleNamespace(
            start=100,
            count=None,
            password="dummy-pass",
            character_name_mode=None,
            character_names="",
            character_name_file="",
            mysql_bin="",
            db_password="",
            ai_player=False,
        )

        command = loadtest.build_provision_command(
            args,
            loadtest.PRESETS["smoke"],
            loadtest.SCENARIOS["newbie-solo"],
            Path("accounts.csv"),
        )

        self.assertIn("--start-x", command)
        self.assertIn(str(loadtest.ALBION_LOW_LEVEL_START[0]), command)
        self.assertIn("--start-y", command)
        self.assertIn(str(loadtest.ALBION_LOW_LEVEL_START[1]), command)
        self.assertIn("--start-region", command)
        self.assertIn("1", command)
        self.assertIn("--position-step", command)
        self.assertIn("650", command)

    def test_run_metadata_keeps_ai_filler_knobs(self):
        args = SimpleNamespace(
            host="127.0.0.1",
            port=10300,
            start=100,
            count=10,
            concurrency=10,
            hold=1800,
            party_size=1,
            ramp_up=120,
            rounds=None,
            server_log=None,
            server_log_time_offset_hours=0.0,
            accounts_csv=None,
            scenario="ai-filler-casual",
            behavior_profile=None,
            action_rotation=None,
            ai_player=False,
            ai_persona="auto",
            realm_strategy="least-populated",
            live_api_url="http://127.0.0.1:5000/api/dashboard/live",
            nav_api_url="",
            character_name_mode="natural",
            target_examine_chance=0.20,
            social_interval=75.0,
            social_chance=0.08,
            player_greet_interval=45.0,
            player_greet_chance=0.06,
            emote_interval=55.0,
            emote_chance=0.12,
            look_around_interval=12.0,
            long_rest_chance=0.06,
            follow_player_name="",
            player_follow_interval=2.0,
            player_follow_distance=850.0,
            follow_player_max_distance=3500.0,
        )
        path = Path("dummy-run-metadata-test.json")

        try:
            loadtest.write_run_metadata(
                path,
                args,
                loadtest.PRESETS["ai-filler-small"],
                loadtest.SCENARIOS["ai-filler-casual"],
                {"behavior": ["python", "dummy"]},
            )
            payload = path.read_text(encoding="utf-8")
        finally:
            path.unlink(missing_ok=True)

        self.assertIn('"player_greet_chance": 0.06', payload)
        self.assertIn('"player_follow_distance": 850.0', payload)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
