#!/usr/bin/env python3
"""Focused tests for dummy world-speed vs packet-speed separation."""

from __future__ import annotations

import importlib.util
import struct
import sys
import time
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


behavior = load_module("behavior_dummy_for_speed_tests", "behavior-dummy-client.py")
headless = load_module("headless_for_speed_tests", "headless-daoc-client.py")


class DummyMovementSpeedDecoupleTests(unittest.TestCase):
    def test_dummy_packet_movement_speed_uses_modern_world_speed(self):
        self.assertEqual(behavior.dummy_packet_movement_speed(191.0), 191.0)
        self.assertEqual(behavior.dummy_packet_movement_speed(48896.0), 191.0)
        self.assertEqual(behavior.dummy_packet_movement_speed(None), None)

    def test_dummy_coerce_world_movement_speed_strips_packet_scale(self):
        self.assertEqual(behavior.dummy_coerce_world_movement_speed(48896.0), 191.0)
        self.assertEqual(behavior.dummy_coerce_world_movement_speed(191.0), 191.0)

    def test_dummy_movement_kwargs_split(self):
        args = Namespace(movement_speed=191.0, movement_update_interval=0.0)
        kwargs = behavior.dummy_movement_kwargs(args)
        self.assertEqual(kwargs["movement_speed"], 191.0)
        self.assertEqual(kwargs["packet_speed"], 191.0)

    def test_resolve_movement_speeds_recovers_from_packet_leak(self):
        travel, packet = headless.resolve_movement_speeds(48896.0, None)
        self.assertEqual(travel, 191.0)
        self.assertEqual(packet, 191.0)

        travel, packet = headless.resolve_movement_speeds(191.0, 48896.0)
        self.assertEqual(travel, 191.0)
        self.assertEqual(packet, 191.0)

    def test_move_towards_position_does_not_travel_packet_scale(self):
        client = headless.HeadlessDaocClient("127.0.0.1", 10300, 1.0, verbose=False)
        client.x = 525160
        client.y = 490319
        client.z = 2638
        client.last_local_move_at = time.monotonic() - 1.0
        client.last_position_update_sent_at = time.monotonic() - 1.0

        sent: list[float] = []
        client.send_position_update = lambda speed=0.0, target_in_view=False: sent.append(float(speed)) or 0
        client.send_heading = lambda *_args, **_kwargs: 0

        target_dx = 489420 - 525160
        target_dy = 456950 - 490319
        client.heading = headless.heading_from_delta(target_dx, target_dy)

        moved = client.move_towards_position(
            489420,
            456950,
            2458,
            step=48.0,
            stop_distance=120.0,
            movement_speed=191.0,
            packet_speed=48896.0,
            target_in_view=True,
        )

        self.assertTrue(moved)
        delta = ((client.x - 525160) ** 2 + (client.y - 490319) ** 2) ** 0.5
        self.assertLess(delta, 500.0)
        self.assertGreater(delta, 1.0)
        self.assertEqual(sent, [191.0])

    def test_move_towards_position_guards_accidental_packet_speed_argument(self):
        client = headless.HeadlessDaocClient("127.0.0.1", 10300, 1.0, verbose=False)
        client.x = 525160
        client.y = 490319
        client.z = 2638
        client.last_local_move_at = time.monotonic() - 1.0
        client.last_position_update_sent_at = time.monotonic() - 1.0

        client.send_position_update = lambda *_args, **_kwargs: 0
        client.send_heading = lambda *_args, **_kwargs: 0

        client.move_towards_position(
            489420,
            456950,
            2458,
            step=48.0,
            stop_distance=120.0,
            movement_speed=48896.0,
            target_in_view=True,
        )

        delta = ((client.x - 525160) ** 2 + (client.y - 490319) ** 2) ** 0.5
        self.assertLess(delta, 500.0)

    def test_move_towards_position_uses_ground_z_sampler_for_physical_z(self):
        client = headless.HeadlessDaocClient("127.0.0.1", 10300, 1.0, verbose=False)
        client.x = 523520
        client.y = 490520
        client.z = 2543
        client.zone_id = 1
        client.ground_z_sampler = lambda x, y, zone_id: 2495
        client.last_local_move_at = time.monotonic() - 1.0
        client.last_position_update_sent_at = time.monotonic() - 1.0

        client.send_position_update = lambda *_args, **_kwargs: 0
        client.send_heading = lambda *_args, **_kwargs: 0

        moved = client.move_towards_position(
            524250,
            490650,
            3000,
            step=48.0,
            stop_distance=120.0,
            movement_speed=191.0,
            packet_speed=191.0,
            target_in_view=True,
        )

        self.assertTrue(moved)
        self.assertEqual(client.z, 2495)

    def test_move_towards_position_preserves_target_z_when_ground_sampler_spikes(self):
        client = headless.HeadlessDaocClient("127.0.0.1", 10300, 1.0, verbose=False)
        client.x = 349259
        client.y = 533169
        client.z = 4598
        client.zone_id = 200
        client.ground_z_sampler = lambda x, y, zone_id: 3787
        client.last_local_move_at = time.monotonic() - 1.0
        client.last_position_update_sent_at = time.monotonic() - 1.0

        client.send_position_update = lambda *_args, **_kwargs: 0
        client.send_heading = lambda *_args, **_kwargs: 0

        moved = client.move_towards_position(
            349158,
            532766,
            4598,
            step=48.0,
            stop_distance=12.0,
            movement_speed=240.0,
            packet_speed=240.0,
            target_in_view=True,
            prefer_target_z=True,
        )

        self.assertTrue(moved)
        self.assertEqual(client.z, 4598)


if __name__ == "__main__":
    unittest.main()
