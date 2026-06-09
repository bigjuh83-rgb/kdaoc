#!/usr/bin/env python3
"""Focused tests for multi-dummy movement command construction."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from argparse import Namespace
from pathlib import Path


TOOLS = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


session = load_module("run_multi_dummy_movement_session_for_tests", "run-multi-dummy-movement-session.py")


def make_args(**overrides) -> Namespace:
    values = {
        "host": "127.0.0.1",
        "port": 10300,
        "count": 4,
        "hold": 30.0,
        "ramp_up": 1.0,
        "party": 4,
        "realm": 1,
        "movement_speed": 191.0,
        "move_interval": 0.25,
        "move_update_interval": 0.0,
        "combat_direct_move_distance": 180.0,
        "path_last_mile_distance": 180.0,
        "path_max_edge_length": 220.0,
        "visible_movement": True,
        "tick": 0.05,
        "mode": "hunt",
        "hunt_profile": "low",
        "waypoints": "",
        "audit": False,
    }
    values.update(overrides)
    return Namespace(**values)


class MultiDummyMovementSessionTests(unittest.TestCase):
    def test_visible_party_hunt_keeps_ground_z_sampling_without_nav_snap(self):
        command = session.build_behavior_command(make_args(visible_movement=True), Path("accounts.csv"))

        self.assertIn("--ground-z-map", command)
        self.assertEqual(command[command.index("--ground-z-map") + 1], session.HUNT_GROUND_Z)
        self.assertIn("--target-face-command-interval", command)
        self.assertEqual(command[command.index("--target-face-command-interval") + 1], "0")
        self.assertNotIn("--client-grid-nav-map", command)
        self.assertNotIn("--path-graph", command)

    def test_non_visible_party_hunt_uses_ground_z_and_nav_graph(self):
        command = session.build_behavior_command(make_args(visible_movement=False), Path("accounts.csv"))

        self.assertIn("--ground-z-map", command)
        self.assertIn("--client-grid-nav-map", command)
        self.assertIn("--path-graph", command)

    def test_visible_party_hunt_uses_rewind_safe_movement_defaults(self):
        command = session.build_behavior_command(
            make_args(visible_movement=True, move_update_interval=0.20),
            Path("accounts.csv"),
        )

        self.assertIn("--server-correction-smoothing", command)
        self.assertEqual(command[command.index("--movement-update-interval") + 1], "0.2")

    def test_apply_movement_session_defaults_bumps_zero_interval(self):
        args = make_args(visible_movement=True, move_update_interval=0.0, move_interval=0.25)
        session.apply_movement_session_defaults(args)
        self.assertEqual(args.move_update_interval, 0.20)
        self.assertEqual(args.move_interval, 0.20)

    def test_default_priv_level_is_one(self):
        help_proc = __import__("subprocess").run(
            [sys.executable, str(TOOLS / "run-multi-dummy-movement-session.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertIn("--priv-level", help_proc.stdout)
        self.assertRegex(help_proc.stdout, r"--priv-level[\s\S]*default:\s*1")

    def test_audit_does_not_add_priv_level_flag(self):
        command = session.build_behavior_command(make_args(audit=True, priv_level=1), Path("accounts.csv"))
        self.assertIn("/movementaudit on {character} full", command)
        self.assertNotIn("--priv-level", command)


if __name__ == "__main__":
    unittest.main()
