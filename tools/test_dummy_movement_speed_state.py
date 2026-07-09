#!/usr/bin/env python3
"""Tests for dummy movement speed state handling (max_speed_percent caps)."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace


TOOLS = Path(__file__).resolve().parent


def load_module(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, TOOLS / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


behavior = load_module("behavior_dummy_for_speed_state_tests", "behavior_dummy_client.py")


class DummyMovementSpeedStateTests(unittest.TestCase):
    def _args(self, **overrides) -> Namespace:
        values = {
            "base_movement_speed": 191.0,
            "movement_speed": 191.0,
            "movement_update_interval": 0.0,
            "flee_movement_speed": 240.0,
        }
        values.update(overrides)
        return Namespace(**values)

    def _client(self, percent: int) -> SimpleNamespace:
        return SimpleNamespace(max_speed_percent=percent)

    def test_state_cap_at_fifty_percent(self):
        args = self._args(movement_speed=95.5)
        client = self._client(50)

        kwargs = behavior.dummy_movement_kwargs(args, client=client)
        self.assertAlmostEqual(kwargs["movement_speed"], 95.5, places=3)
        self.assertAlmostEqual(kwargs["packet_speed"], 95.5, places=3)

    def test_flee_override_clamps_to_state_cap(self):
        args = self._args(movement_speed=95.5)
        client = self._client(50)

        kwargs = behavior.dummy_movement_kwargs(args, args.flee_movement_speed, client)
        self.assertAlmostEqual(kwargs["movement_speed"], 95.5, places=3)
        self.assertLess(kwargs["movement_speed"], args.flee_movement_speed)

    def test_normal_speed_at_one_hundred_percent(self):
        args = self._args()
        client = self._client(100)

        kwargs = behavior.dummy_movement_kwargs(args, client=client)
        self.assertAlmostEqual(kwargs["movement_speed"], 191.0, places=3)

    def test_speed_song_percent_increases_travel_speed(self):
        args = self._args(movement_speed=248.3)
        client = self._client(130)

        kwargs = behavior.dummy_movement_kwargs(args, client=client)
        self.assertAlmostEqual(kwargs["movement_speed"], 248.3, places=1)

    def test_flee_override_respects_speed_song_cap(self):
        args = self._args(movement_speed=248.3, flee_movement_speed=300.0)
        client = self._client(130)

        kwargs = behavior.dummy_movement_kwargs(args, args.flee_movement_speed, client)
        self.assertAlmostEqual(kwargs["movement_speed"], 248.3, places=1)

    def test_combat_chase_uses_state_cap_not_local_sprint_math(self):
        args = self._args(movement_speed=95.5)
        speed = behavior.combat_chase_movement_speed(args, "melee-basic", 900.0)
        self.assertAlmostEqual(speed, 95.5, places=3)


if __name__ == "__main__":
    unittest.main()
