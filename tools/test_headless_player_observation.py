#!/usr/bin/env python3
"""Unit checks for headless dummy client world observation parsing."""

from __future__ import annotations

import importlib.util
import struct
import sys
import time
import unittest
from pathlib import Path


def load_headless_module():
    module_path = Path(__file__).with_name("headless-daoc-client.py")
    spec = importlib.util.spec_from_file_location("headless_daoc_client_for_tests", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


headless = load_headless_module()


def pascal(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return bytes([len(encoded)]) + encoded


class HeadlessPlayerObservationTests(unittest.TestCase):
    def make_client(self):
        client = headless.HeadlessDaocClient("127.0.0.1", 10300, 1.0, verbose=False)
        client.player_object_id = 100
        return client

    def test_observes_1124_player_create(self):
        client = self.make_client()
        data = bytearray()
        data += struct.pack("<f", 1000.0)
        data += struct.pack("<f", 2000.0)
        data += struct.pack("<f", 300.0)
        data += struct.pack(">H", 0x1234)
        data += struct.pack(">H", 0x5678)
        data += struct.pack(">H", 0x0200)
        data += struct.pack(">H", 99)
        data += bytes([12])
        data += bytes([(2 & 0x03) << 2])
        data += b"\x00" * 10
        data += pascal("라온")
        data += pascal("길드")
        data += pascal("")
        data += pascal("")
        data += pascal("")
        data += b"\x00"

        client.observe_packet(headless.ServerPacket(0x4B, bytes(data)))

        player = client.players[0x5678]
        self.assertEqual(player.name, "라온")
        self.assertEqual(player.realm, 2)
        self.assertEqual(player.level, 12)
        self.assertEqual(player.x, 1000)
        self.assertEqual(player.y, 2000)
        self.assertEqual(player.z, 300)
        self.assertEqual(player.heading, 0x0200)

    def test_removes_observed_player(self):
        client = self.make_client()
        client.players[222] = headless.KnownPlayer(222, "가온", 10, 20, 30, 0, 1, 1, time.monotonic())

        client.observe_packet(headless.ServerPacket(0xA2, struct.pack(">HH", 222, 2)))

        self.assertNotIn(222, client.players)
        self.assertIn(222, client.consume_removed_object_ids())

    def test_updates_observed_player_position(self):
        client = self.make_client()
        client.players[333] = headless.KnownPlayer(333, "이든", 10, 20, 30, 0, 1, 1, time.monotonic())
        data = bytearray()
        data += struct.pack("<f", 1200.0)
        data += struct.pack("<f", 2100.0)
        data += struct.pack("<f", 330.0)
        data += struct.pack("<f", 250.0)
        data += struct.pack("<f", 0.0)
        data += struct.pack(">H", 0x1111)
        data += struct.pack(">H", 333)
        data += struct.pack(">H", 1)
        data += b"\x00\x00\x00\x00"
        data += struct.pack(">H", 0x0400)
        data += b"\x00\x00\x00"
        data += b"\x64\x64\x64"
        data += b"\x00\x00"

        client.observe_packet(headless.ServerPacket(0xA9, bytes(data)))

        player = client.players[333]
        self.assertEqual((player.x, player.y, player.z), (1200, 2100, 330))
        self.assertEqual(player.heading, 0x0400)

    def test_visible_players_are_sorted_by_distance(self):
        client = self.make_client()
        now = time.monotonic()
        client.x = 0
        client.y = 0
        client.z = 0
        client.players[1] = headless.KnownPlayer(1, "멀리", 1000, 0, 0, 0, 1, 1, now)
        client.players[2] = headless.KnownPlayer(2, "근처", 100, 0, 0, 0, 1, 1, now)

        self.assertEqual([player.name for player in client.visible_players()], ["근처", "멀리"])

    def test_hold_position_still_faces_target(self):
        client = self.make_client()
        client.x = 100
        client.y = 100
        client.z = 0
        sent_updates: list[tuple[float, bool]] = []

        def capture_position_update(speed: float = 0.0, target_in_view: bool = False):
            sent_updates.append((speed, target_in_view))
            return 0

        client.send_position_update = capture_position_update

        moved = client.move_towards_position(100, 200, 0, step=250, stop_distance=150)

        self.assertFalse(moved)
        self.assertEqual(client.heading, headless.heading_from_delta(0, 100))
        self.assertEqual(sent_updates, [(0.0, True)])

    def test_observes_chat_message(self):
        client = self.make_client()

        client.observe_packet(headless.ServerPacket(0xAF, bytes([7]) + "대상이 사거리 밖에 있습니다".encode("utf-8") + b"\x00"))

        messages = client.consume_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].chat_type, 7)
        self.assertEqual(messages[0].text, "대상이 사거리 밖에 있습니다")
        self.assertEqual(client.consume_messages(), [])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
