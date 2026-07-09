#!/usr/bin/env python3
"""Tests for dummy heading policy (Antigravity-approved fix)."""

from __future__ import annotations

import importlib.util
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


behavior = load_module("behavior_dummy_for_heading_tests", "behavior_dummy_client.py")
headless = load_module("headless_for_heading_tests", "headless-daoc-client.py")


def make_args(**overrides) -> Namespace:
    values = {
        "attack_range": 120.0,
        "minimum_melee_stop_distance": 70.0,
        "melee_range_buffer": 25.0,
        "ranged_stop_distance": 350.0,
        "spell_range": 1500.0,
    }
    values.update(overrides)
    return Namespace(**values)


class DummyHeadingPolicyTests(unittest.TestCase):
    def test_should_not_send_face_heading_while_moving_outside_melee(self):
        client = SimpleNamespace(last_position_speed=191.0, heading=0)
        args = make_args()
        self.assertFalse(
            behavior.should_send_combat_face_heading(
                client,
                distance=500.0,
                melee_stop_distance=behavior.melee_face_distance(args, "melee-basic"),
            )
        )

    def test_should_send_face_heading_when_stationary_in_melee(self):
        client = SimpleNamespace(last_position_speed=0.0, heading=0)
        args = make_args()
        self.assertTrue(
            behavior.should_send_combat_face_heading(
                client,
                distance=80.0,
                melee_stop_distance=behavior.melee_face_distance(args, "melee-basic"),
            )
        )

    def test_face_target_for_attack_skips_heading_while_chasing(self):
        client = SimpleNamespace(x=0, y=0, heading=0, last_position_speed=191.0)
        actor = SimpleNamespace(x=1000, y=0)
        sent: list[int] = []
        client.send_heading = lambda heading, **kwargs: sent.append(int(heading)) or 0

        behavior.face_target_for_attack(client, actor, args=make_args(), action_rotation="melee-basic")
        self.assertEqual(sent, [])

    def test_face_target_for_attack_sends_heading_in_melee_while_stopped(self):
        client = SimpleNamespace(x=0, y=0, heading=0, last_position_speed=0.0)
        actor = SimpleNamespace(x=80, y=0)
        sent: list[int] = []
        client.send_heading = lambda heading, **kwargs: sent.append(int(heading)) or 0

        behavior.face_target_for_attack(client, actor, args=make_args(), action_rotation="melee-basic")
        self.assertEqual(len(sent), 1)

    def test_heading_delta_shortest_path(self):
        self.assertEqual(headless.heading_delta(100, 3900), -296)
        self.assertEqual(headless.heading_delta(3900, 100), 296)

    def test_step_heading_towards_limits_turn_rate(self):
        result = headless.step_heading_towards(0, 2048, 768)
        self.assertEqual(result, 768)

    def test_send_heading_suppressed_after_conflicting_position_packet(self):
        client = headless.HeadlessDaocClient("127.0.0.1", 10300, 1.0, verbose=False)
        events: list[str] = []
        client.trace_movement = lambda event, **fields: events.append(event)
        client.send_packet = lambda *_args, **_kwargs: None
        client.drain = lambda *_args, **_kwargs: 0
        client._last_position_packet_at = time.monotonic()
        client._last_position_packet_heading = 0

        client.send_heading(2048, drain_after=False)
        self.assertIn("skip_send_heading_dual_conflict", events)

    def test_large_turn_rotates_in_place_before_travel(self):
        client = headless.HeadlessDaocClient("127.0.0.1", 10300, 1.0, verbose=False)
        client.x = 1000
        client.y = 1000
        client.z = 2000
        client.heading = 0
        client.last_local_move_at = time.monotonic() - 1.0
        client.last_position_update_sent_at = time.monotonic() - 1.0

        speeds: list[float] = []
        client.send_position_update = lambda speed=0.0, target_in_view=False: speeds.append(float(speed)) or 0
        client.send_heading = lambda *_args, **_kwargs: 0

        start_x = client.x
        start_y = client.y
        moved = client.move_towards_position(
            1000,
            0,
            2000,
            step=48.0,
            stop_distance=120.0,
            movement_speed=191.0,
            packet_speed=191.0,
            target_in_view=False,
        )

        self.assertTrue(moved)
        self.assertEqual(client.x, start_x)
        self.assertEqual(client.y, start_y)
        self.assertEqual(speeds, [0.0])
        self.assertGreater(client.heading, 512)

    def test_target_loss_rescan_skips_grace_wait_for_hunter(self):
        args = Namespace(hunter=True, target_loss_rescan=True, target_loss_grace=8.0)
        now = 100.0
        self.assertFalse(behavior.should_hold_target_loss_grace(args, now, now - 1.0))

    def test_target_loss_grace_wait_when_rescan_disabled(self):
        args = Namespace(hunter=True, target_loss_rescan=False, target_loss_grace=8.0)
        now = 100.0
        self.assertTrue(behavior.should_hold_target_loss_grace(args, now, now - 1.0))
        self.assertFalse(behavior.should_hold_target_loss_grace(args, now, now - 9.0))

    def test_target_loss_scan_heading_step(self):
        self.assertEqual(behavior.target_loss_scan_heading_step(4000, 512), 416)

    def test_should_chase_committed_target_last_known_while_rescanning(self):
        args = make_args(hunter=True, target_loss_rescan=True, target_loss_grace=1.5, move=False)
        client = SimpleNamespace(x=1000, y=1000, z=2000)
        active_combat = {"target_x": 1400, "target_y": 1400, "target_z": 2000}
        now = 100.0
        self.assertTrue(
            behavior.should_chase_committed_target_last_known(
                args,
                client,
                "melee-basic",
                current_target=42,
                active_combat=active_combat,
                target_visible=False,
                now=now,
                last_visible_at=now - 30.0,
            )
        )

    def test_should_not_chase_committed_target_when_visible(self):
        args = make_args(hunter=True, target_loss_rescan=True, target_loss_grace=1.5, move=False)
        client = SimpleNamespace(x=1000, y=1000, z=2000)
        active_combat = {"target_x": 1400, "target_y": 1400, "target_z": 2000}
        self.assertFalse(
            behavior.should_chase_committed_target_last_known(
                args,
                client,
                "melee-basic",
                current_target=42,
                active_combat=active_combat,
                target_visible=True,
                now=100.0,
                last_visible_at=99.0,
            )
        )

    def test_should_not_chase_committed_target_when_already_in_melee_range(self):
        args = make_args(hunter=True, target_loss_rescan=True, target_loss_grace=1.5, move=False)
        client = SimpleNamespace(x=1000, y=1000, z=2000)
        active_combat = {"target_x": 1050, "target_y": 1000, "target_z": 2000}
        self.assertFalse(
            behavior.should_chase_committed_target_last_known(
                args,
                client,
                "melee-basic",
                current_target=42,
                active_combat=active_combat,
                target_visible=False,
                now=100.0,
                last_visible_at=99.0,
            )
        )


if __name__ == "__main__":
    unittest.main()
