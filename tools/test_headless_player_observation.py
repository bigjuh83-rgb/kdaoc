#!/usr/bin/env python3
"""Unit checks for headless dummy client world observation parsing."""

from __future__ import annotations

import importlib.util
import json
import socket
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
TEST_TEMP_DIR = Path(__file__).resolve().parent


def fresh_trace_path(name: str) -> Path:
    path = TEST_TEMP_DIR / name
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    return path


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
        data += pascal("?쇱삩")
        data += pascal("湲몃뱶")
        data += pascal("")
        data += pascal("")
        data += pascal("")
        data += b"\x00"

        client.observe_packet(headless.ServerPacket(0x4B, bytes(data)))

        player = client.players[0x5678]
        self.assertEqual(player.name, "?쇱삩")
        self.assertEqual(player.realm, 2)
        self.assertEqual(player.level, 12)
        self.assertEqual(player.x, 1000)
        self.assertEqual(player.y, 2000)
        self.assertEqual(player.z, 300)
        self.assertEqual(player.heading, 0x0200)

    def test_removes_observed_player(self):
        client = self.make_client()
        client.players[222] = headless.KnownPlayer(222, "removed-player", 10, 20, 30, 0, 1, 1, time.monotonic())

        client.observe_packet(headless.ServerPacket(0xA2, struct.pack(">HH", 222, 2)))

        self.assertNotIn(222, client.players)
        self.assertIn(222, client.consume_removed_object_ids())

    def test_dead_client_can_send_single_corpse_position_update(self):
        client = self.make_client()
        client.session_id = 0x1234
        client.player_object_id = 0x5678
        client.zone_id = 1
        client.x = 1000
        client.y = 2000
        client.z = 300
        client.heading = 0x0200
        client.is_dead = True
        packets = []

        def capture_packet(packet_id, data):
            packets.append((packet_id, data))

        client.send_packet = capture_packet
        client.drain = lambda seconds: 0

        client.send_corpse_position_update()

        self.assertEqual(packets[0][0], headless.CLIENT_PACKETS["position"])
        data = packets[0][1]
        self.assertEqual(data[26], 0x14)
        self.assertEqual(data[35], 0)

    def test_buy_sell_move_item_and_custom_dialog_helpers_send_expected_payloads(self):
        client = self.make_client()
        client.player_object_id = 0x5678
        client.x = 1000
        client.y = 2000
        packets = []

        def capture_packet(packet_id, data):
            packets.append((packet_id, data))

        client.send_packet = capture_packet
        client.drain = lambda seconds: 0

        client.buy_item(slot=12, count=3, menu_id=0)
        client.sell_item(slot=40)
        client.move_item(from_slot=40, to_slot=100, count=1)
        client.accept_custom_dialog()

        self.assertEqual(packets[0][0], headless.CLIENT_PACKETS["buy"])
        self.assertEqual(packets[0][1], struct.pack(">IIHHBB", 1000, 2000, 0x5678, 12, 3, 0))
        self.assertEqual(packets[1][0], headless.CLIENT_PACKETS["sell"])
        self.assertEqual(packets[1][1], struct.pack(">IIHH", 1000, 2000, 0x5678, 40))
        self.assertEqual(packets[2][0], headless.CLIENT_PACKETS["move_item"])
        self.assertEqual(packets[2][1], struct.pack(">HHHH", 0, 100, 40, 1))
        self.assertEqual(packets[3][0], headless.CLIENT_PACKETS["dialog_response"])
        self.assertEqual(packets[3][1], b"\x00\x00\x00\x01\x00\x00\x06\x01")

    def test_send_command_encodes_korean_chat_as_cp949(self):
        client = self.make_client()
        packets = []

        def capture_packet(packet_id, data):
            packets.append((packet_id, data))

        client.send_packet = capture_packet
        client.read_packets_for = lambda seconds: []

        client.send_command("/g 따라가겠습니다")

        self.assertEqual(packets[0][0], headless.CLIENT_PACKETS["command"])
        self.assertEqual(packets[0][1], b"\x00&g " + "따라가겠습니다".encode("cp949") + b"\x00")
        self.assertNotIn("따라가겠습니다".encode("utf-8"), packets[0][1])

    def test_status_update_marks_self_dead_at_zero_health(self):
        client = self.make_client()
        client.is_dead = False

        client.observe_packet(headless.ServerPacket(0xAD, bytes([0, 77, 0, 88])))

        self.assertTrue(client.is_dead)
        self.assertEqual(client.health_percent, 0)
        self.assertEqual(client.mana_percent, 77)
        self.assertEqual(client.endurance_percent, 88)

    def test_player_death_and_revive_toggle_self_dead_state(self):
        client = self.make_client()
        client.player_object_id = 0x5678
        trace_events = []
        client.trace_movement = lambda event, **fields: trace_events.append((event, fields))

        client.observe_packet(headless.ServerPacket(0xAE, struct.pack(">H", 0x5678)))

        self.assertTrue(client.is_dead)
        self.assertEqual(client.health_percent, 0)
        self.assertEqual(trace_events[-1][0], "player_death")

        client.observe_packet(headless.ServerPacket(0x89, struct.pack(">H", 0x5678)))

        self.assertFalse(client.is_dead)
        self.assertEqual(trace_events[-1][0], "player_revive")

    def test_player_death_ignores_other_player_object_id(self):
        client = self.make_client()
        client.player_object_id = 0x5678

        client.observe_packet(headless.ServerPacket(0xAE, struct.pack(">H", 0x1111)))

        self.assertFalse(client.is_dead)

    def test_updates_observed_player_position(self):
        client = self.make_client()
        client.players[333] = headless.KnownPlayer(333, "?대뱺", 10, 20, 30, 0, 1, 1, time.monotonic())
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

    def test_traces_observed_player_position_delta(self):
        client = self.make_client()
        client.players[333] = headless.KnownPlayer(333, "?대뱺", 10, 20, 30, 0, 1, 1, time.monotonic())
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

        trace_path = fresh_trace_path("test-traces-observed-player-position.jsonl")
        client.trace_movement_path = str(trace_path)
        client.trace_observed_player_positions = True
        client.observe_packet(headless.ServerPacket(0xA9, bytes(data)))
        payload = json.loads(trace_path.read_text(encoding="utf-8").strip())
        trace_path.unlink(missing_ok=True)

        self.assertEqual(payload["event"], "observe_player_position")
        self.assertEqual(payload["object_id"], 333)
        self.assertEqual(payload["name"], "?대뱺")
        self.assertEqual(payload["delta_x"], 1190)
        self.assertEqual(payload["delta_y"], 2080)
        self.assertEqual(payload["delta_z"], 300)
        self.assertGreater(float(payload["horizontal_delta"]), 0)

    def test_horizontal_distance_ignores_z_offset(self):
        client = self.make_client()
        client.x = 1000
        client.y = 1000
        client.z = 5000
        npc = headless.KnownNpc(10, "target", 1060, 1080, 100, 1, 0, time.monotonic())

        self.assertEqual(client.horizontal_distance_to(npc), 100.0)
        self.assertGreater(client.distance_to(npc), 100.0)

    def test_visible_players_are_sorted_by_distance(self):
        client = self.make_client()
        now = time.monotonic()
        client.x = 0
        client.y = 0
        client.z = 0
        client.players[1] = headless.KnownPlayer(1, "far-player", 1000, 0, 0, 0, 1, 1, now)
        client.players[2] = headless.KnownPlayer(2, "near-player", 100, 0, 0, 0, 1, 1, now)

        self.assertEqual([player.name for player in client.visible_players()], ["near-player", "far-player"])

    def test_self_position_correction_can_be_smoothed(self):
        client = self.make_client()
        client.x = 1000
        client.y = 1000
        client.z = 100
        client.heading = 0
        client.zone_id = 1
        client.server_correction_smoothing = True
        client.server_correction_min_distance = 20.0
        client.server_correction_step = 40.0
        client.server_correction_max_snap_distance = 500.0
        data = bytearray()
        data += struct.pack("<f", 1100.0)
        data += struct.pack("<f", 1000.0)
        data += struct.pack("<f", 120.0)
        data += struct.pack(">H", client.player_object_id)
        data += struct.pack(">H", 0x0300)
        data += b"\x00\x00\x00\x00"
        data += struct.pack(">H", 2)

        client.observe_packet(headless.ServerPacket(0x20, bytes(data)))

        self.assertEqual((client.x, client.y, client.z), (1040, 1000, 108))
        self.assertEqual(client.heading, 0x0300)
        self.assertEqual(client.zone_id, 2)

    def test_large_self_position_correction_still_snaps(self):
        client = self.make_client()
        client.x = 1000
        client.y = 1000
        client.z = 100
        client.server_correction_smoothing = True
        client.server_correction_max_snap_distance = 50.0
        data = bytearray()
        data += struct.pack("<f", 1300.0)
        data += struct.pack("<f", 1000.0)
        data += struct.pack("<f", 130.0)
        data += struct.pack(">H", client.player_object_id)
        data += struct.pack(">H", 0x0200)
        data += b"\x00\x00\x00\x00"
        data += struct.pack(">H", 1)

        client.observe_packet(headless.ServerPacket(0x20, bytes(data)))

        self.assertEqual((client.x, client.y, client.z), (1300, 1000, 130))

    def test_hold_position_still_faces_target(self):
        client = self.make_client()
        client.x = 100
        client.y = 100
        client.z = 0
        sent_updates: list[tuple[float, bool]] = []
        sent_headings: list[int] = []

        def capture_position_update(speed: float = 0.0, target_in_view: bool = False):
            sent_updates.append((speed, target_in_view))
            return 0

        def capture_heading(heading: int, **_kwargs):
            sent_headings.append(heading)
            client.heading = heading & 0x0FFF
            return 0

        client.send_position_update = capture_position_update
        client.send_heading = capture_heading

        moved = client.move_towards_position(100, 200, 0, step=250, stop_distance=150)

        self.assertFalse(moved)
        self.assertEqual(client.heading, headless.heading_from_delta(0, 100))
        self.assertEqual(sent_headings, [])
        self.assertEqual(sent_updates, [(0.0, False)])

    def test_movement_sends_position_only_when_advancing_with_constant_speed(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        events: list[tuple[str, float | int, bool | None]] = []

        def capture_heading(heading: int, **_kwargs):
            events.append(("heading", heading, None))
            client.heading = heading & 0x0FFF
            return 0

        def capture_position_update(speed: float = 0.0, target_in_view: bool = False):
            events.append(("position", speed, target_in_view))
            client.last_position_speed = speed
            return 0

        client.send_heading = capture_heading
        client.send_position_update = capture_position_update

        moved = client.move_towards_position(0, 1000, 300, step=55, stop_distance=0, movement_speed=220.0)

        self.assertTrue(moved)
        self.assertEqual((client.x, client.y), (0, 55))
        self.assertEqual(client.z, 111)
        self.assertEqual(
            events,
            [
                ("position", 220.0, False),
            ],
        )
        self.assertEqual(client.last_position_speed, 220.0)

    def test_movement_clears_target_in_view_for_plain_travel(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 0
        updates: list[tuple[float, bool]] = []

        client.send_heading = lambda *_args, **_kwargs: 0

        def capture_position_update(speed: float = 0.0, target_in_view: bool = False):
            updates.append((speed, target_in_view))
            client.last_position_speed = speed
            return 0

        client.send_position_update = capture_position_update

        moved = client.move_towards_position(0, 1000, 0, step=55, stop_distance=0, movement_speed=220.0)

        self.assertTrue(moved)
        self.assertEqual(
            updates,
            [
                (220.0, False),
            ],
        )
        self.assertEqual(client.last_position_speed, 220.0)

    def test_movement_interpolates_shallow_z_change_instead_of_fixed_drop(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda *_args, **_kwargs: 0

        moved = client.move_towards_position(0, 1000, 120, step=55, stop_distance=0, movement_speed=220.0)

        self.assertTrue(moved)
        self.assertEqual((client.x, client.y), (0, 55))
        self.assertEqual(client.z, 101)

    def test_movement_can_snap_to_explicit_ground_z(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda *_args, **_kwargs: 0

        moved = client.move_towards_position(
            0,
            1000,
            300,
            step=55,
            stop_distance=0,
            movement_speed=220.0,
            ground_z=140,
        )

        self.assertTrue(moved)
        self.assertEqual((client.x, client.y, client.z), (0, 55, 140))

    def test_movement_can_sample_ground_z_from_next_xy(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        client.zone_id = 2
        sampled: list[tuple[int, int, int]] = []
        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda *_args, **_kwargs: 0

        def sample_ground_z(x: int, y: int, zone_id: int) -> int:
            sampled.append((x, y, zone_id))
            return 222

        client.ground_z_sampler = sample_ground_z

        moved = client.move_towards_position(0, 1000, 300, step=55, stop_distance=0, movement_speed=220.0)

        self.assertTrue(moved)
        self.assertEqual((client.x, client.y, client.z), (0, 55, 222))
        self.assertEqual(sampled, [(0, 55, 2)])

    def test_movement_can_prefer_target_z_over_stale_ground_sample(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        client.zone_id = 2
        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda *_args, **_kwargs: 0
        client.ground_z_sampler = lambda _x, _y, _zone_id: 222

        moved = client.move_towards_position(
            0,
            1000,
            300,
            step=55,
            stop_distance=0,
            movement_speed=220.0,
            prefer_target_z=True,
        )

        self.assertTrue(moved)
        self.assertEqual((client.x, client.y, client.z), (0, 55, 300))

    def test_movement_rejects_implausible_target_z_when_ground_sample_exists(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 2400
        client.zone_id = 2
        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda *_args, **_kwargs: 0
        client.ground_z_sampler = lambda _x, _y, _zone_id: 2400

        moved = client.move_towards_position(
            0,
            1000,
            2200,
            step=55,
            stop_distance=0,
            movement_speed=220.0,
            prefer_target_z=True,
        )

        self.assertTrue(moved)
        self.assertEqual((client.x, client.y, client.z), (0, 55, 2400))

    def test_heading_from_delta_matches_server_dol_grid(self):
        self.assertEqual(headless.heading_from_delta(0, 100), 0)
        self.assertEqual(headless.heading_from_delta(-100, 0), 1024)
        self.assertEqual(headless.heading_from_delta(0, -100), 2048)
        self.assertEqual(headless.heading_from_delta(100, 0), 3072)

    def test_wander_uses_server_heading_axis(self):
        client = self.make_client()
        client.x = 1000
        client.y = 1000
        client.z = 0
        events: list[str] = []

        def capture_heading(heading: int, **_kwargs):
            events.append("heading")
            client.heading = heading & 0x0FFF
            return 0

        def capture_position_update(speed: float = 0.0, target_in_view: bool = False):
            events.append("position")
            client.last_position_speed = speed
            return 0

        client.send_heading = capture_heading
        client.send_position_update = capture_position_update

        client.wander(3072, step=100, movement_speed=220.0)

        self.assertEqual((client.x, client.y), (1100, 1000))
        self.assertEqual(events, ["position"])

    def test_wander_samples_ground_z_after_move(self):
        client = self.make_client()
        client.x = 561900
        client.y = 357450
        client.z = 4826

        def sample_ground_z(x: int, y: int, zone_id: int) -> int | None:
            self.assertEqual((x, y), (562000, 357450))
            return 4868

        client.ground_z_sampler = sample_ground_z
        client.send_position_update = lambda **kwargs: 0
        client.wander(3072, step=100, movement_speed=220.0)

        self.assertEqual(client.z, 4868)

    def test_wander_accepts_elapsed_movement_time_kwargs(self):
        client = self.make_client()
        client.x = 1000
        client.y = 1000
        client.z = 0
        speeds: list[float] = []

        def capture_position_update(speed: float = 0.0, target_in_view: bool = False):
            speeds.append(speed)
            client.last_position_speed = speed
            return 0

        client.send_position_update = capture_position_update

        client.wander(
            3072,
            step=100,
            movement_speed=220.0,
            use_elapsed_movement_time=True,
            max_elapsed_movement_seconds=1.0,
        )

        self.assertEqual((client.x, client.y), (1100, 1000))
        self.assertEqual(speeds, [220.0])

    def test_refresh_ground_z_here_snaps_spawn_z(self):
        client = self.make_client()
        client.x = 561900
        client.y = 357450
        client.z = 4826
        client.ground_z_sampler = lambda x, y, zone_id: 4868

        self.assertTrue(client.refresh_ground_z_here())
        self.assertEqual(client.z, 4868)

    def test_send_position_update_coerces_legacy_packet_speed(self):
        client = self.make_client()
        client.x = 1000
        client.y = 1000
        client.z = 100
        client.last_sent_position = (900, 900, 100)
        sent_speeds: list[float] = []

        def capture_packet(code: int, data: bytes = b"", session_id: int | None = None) -> None:
            if code == headless.CLIENT_PACKETS["position"]:
                sent_speeds.append(struct.unpack_from("<f", data, 12)[0])

        client.send_packet = capture_packet
        client.drain = lambda seconds=0.05: 0
        client.send_position_update(speed=48896.0, target_in_view=False)

        self.assertEqual(sent_speeds, [191.0])
        self.assertEqual(client.last_position_speed, 191.0)

    def test_send_position_update_zeros_speed_when_xy_unchanged(self):
        client = self.make_client()
        client.x = 1000
        client.y = 1000
        client.z = 100
        client.last_sent_position = (1000, 1000, 100)
        sent_speeds: list[float] = []

        def capture_packet(code: int, data: bytes = b"", session_id: int | None = None) -> None:
            if code == headless.CLIENT_PACKETS["position"]:
                sent_speeds.append(struct.unpack_from("<f", data, 12)[0])

        client.send_packet = capture_packet
        client.drain = lambda seconds=0.05: 0
        client.send_position_update(speed=191.0, target_in_view=True)

        self.assertEqual(sent_speeds, [0.0])
        self.assertEqual(client.last_position_speed, 0.0)

    def test_action_payload_reuses_last_position_speed(self):
        client = self.make_client()
        client.x = 10
        client.y = 20
        client.z = 30
        client.heading = 40
        client.last_position_speed = 220.0

        payload = client.build_action_payload(target_in_view=True)

        self.assertEqual(struct.unpack_from("<f", payload, 12)[0], 220.0)

    def test_action_payload_can_override_speed(self):
        client = self.make_client()
        client.last_position_speed = 220.0

        payload = client.build_action_payload(speed=0.0)

        self.assertEqual(struct.unpack_from("<f", payload, 12)[0], 0.0)

    def test_action_payload_reuses_last_sent_position_for_unsent_movement(self):
        client = self.make_client()
        client.x = 0
        client.y = 55
        client.z = 100
        client.last_sent_position = (0, 0, 100)
        client.last_position_speed = 0.0
        client.last_local_movement_speed = 220.0

        payload = client.build_action_payload(speed=0.0)

        self.assertEqual(struct.unpack_from("<f", payload, 0)[0], 0.0)
        self.assertEqual(struct.unpack_from("<f", payload, 4)[0], 0.0)
        self.assertEqual(struct.unpack_from("<f", payload, 8)[0], 100.0)
        self.assertEqual(struct.unpack_from("<f", payload, 12)[0], 0.0)

    def test_movement_can_throttle_mid_position_updates(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        client.last_position_speed = 220.0
        client.last_position_update_sent_at = time.monotonic() - 0.25
        events: list[str] = []

        client.send_heading = lambda *_args, **_kwargs: events.append("heading") or 0
        client.send_position_update = lambda *args, **kwargs: events.append("position") or 0

        moved = client.move_towards_position(
            0,
            1000,
            100,
            step=55,
            stop_distance=0,
            movement_speed=220.0,
            min_position_send_interval=10.0,
        )

        self.assertFalse(moved)
        self.assertEqual((client.x, client.y), (0, 0))
        self.assertEqual(events, [])

    def test_movement_uses_fixed_step_not_elapsed_catchup(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        now = time.monotonic()
        client.last_local_move_at = now - 0.5
        client.last_position_update_sent_at = now - 0.5

        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda *_args, **_kwargs: 0

        moved = client.move_towards_position(
            0,
            1000,
            100,
            step=55,
            stop_distance=0,
            movement_speed=220.0,
            movement_step_seconds=0.05,
            min_position_send_interval=0.0,
        )

        self.assertTrue(moved)
        self.assertGreaterEqual(client.y, 8)
        self.assertLessEqual(client.y, 15)

    def test_movement_does_not_catch_up_after_long_loop_delay(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        client.last_local_move_at = time.monotonic() - 0.5

        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda *_args, **_kwargs: 0

        moved = client.move_towards_position(
            0,
            1000,
            100,
            step=55,
            stop_distance=0,
            movement_speed=220.0,
            movement_step_seconds=0.05,
            min_position_send_interval=0.0,
        )

        self.assertTrue(moved)
        self.assertGreaterEqual(client.y, 8)
        self.assertLessEqual(client.y, 15)

    def test_movement_uses_elapsed_time_for_continuing_packet_speed_run(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        now = time.monotonic()
        client.last_local_move_at = now - 0.5
        client.last_position_update_sent_at = now - 0.5
        client.last_position_speed = 220.0

        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda *_args, **_kwargs: 0

        moved = client.move_towards_position(
            0,
            1000,
            100,
            step=250,
            stop_distance=0,
            movement_speed=220.0,
            packet_speed=220.0,
            movement_step_seconds=0.05,
            min_position_send_interval=0.0,
        )

        self.assertTrue(moved)
        self.assertGreaterEqual(client.y, 90)
        self.assertLessEqual(client.y, 130)

    def test_movement_does_not_elapsed_catchup_from_stopped_state(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        now = time.monotonic()
        client.last_local_move_at = now - 0.5
        client.last_position_update_sent_at = now - 0.5
        client.last_position_speed = 0.0

        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda *_args, **_kwargs: 0

        moved = client.move_towards_position(
            0,
            1000,
            100,
            step=250,
            stop_distance=0,
            movement_speed=220.0,
            packet_speed=220.0,
            movement_step_seconds=0.05,
            min_position_send_interval=0.0,
        )

        self.assertTrue(moved)
        self.assertGreaterEqual(client.y, 8)
        self.assertLessEqual(client.y, 15)

    def test_movement_final_trim_uses_effective_packet_speed(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        now = time.monotonic()
        client.last_local_move_at = now - 0.8
        client.last_position_update_sent_at = now - 0.8
        client.last_position_speed = 191.0
        sent_speeds: list[float] = []

        client.send_heading = lambda *_args, **_kwargs: 0
        client.send_position_update = lambda speed=0.0, target_in_view=False: sent_speeds.append(float(speed)) or 0

        moved = client.move_towards_position(
            0,
            456,
            100,
            step=500,
            stop_distance=455,
            movement_speed=191.0,
            packet_speed=191.0,
            movement_step_seconds=0.18,
            min_position_send_interval=0.0,
        )

        self.assertTrue(moved)
        self.assertEqual(client.y, 1)
        self.assertEqual(len(sent_speeds), 1)
        self.assertLess(sent_speeds[0], 5.0)

    def test_movement_stops_when_integer_quantization_blocks_last_small_step(self):
        client = self.make_client()
        client.x = 523815
        client.y = 490815
        client.z = 2543
        updates: list[tuple[float, bool]] = []

        def capture_position_update(speed: float = 0.0, target_in_view: bool = False):
            updates.append((speed, target_in_view))
            client.last_position_speed = speed
            return 0

        client.send_position_update = capture_position_update
        client.send_heading = lambda *_args, **_kwargs: 0

        moved = client.move_towards_position(
            523900,
            490900,
            2543,
            step=38.2,
            stop_distance=120.0,
            movement_speed=191.0,
        )

        self.assertFalse(moved)
        self.assertEqual((client.x, client.y, client.z), (523815, 490815, 2543))
        self.assertEqual(updates, [(0.0, False)])

    def test_trace_movement_writes_json_lines(self):
        client = self.make_client()

        trace_path = fresh_trace_path("test-trace-movement.jsonl")
        client.trace_movement_path = str(trace_path)
        client.trace_movement("send_position", x=1, y=2, text="?쒓?")

        payload = json.loads(trace_path.read_text(encoding="utf-8").strip())
        trace_path.unlink(missing_ok=True)

        self.assertEqual(payload["event"], "send_position")
        self.assertEqual(payload["x"], 1)
        self.assertEqual(payload["y"], 2)
        self.assertEqual(payload["text"], "?쒓?")
        self.assertIsInstance(payload["t"], float)

    def test_move_step_trace_includes_z_source_and_target(self):
        client = self.make_client()
        client.x = 0
        client.y = 0
        client.z = 100
        client.send_position_update = lambda *_args, **_kwargs: 0

        trace_path = fresh_trace_path("test-move-step-trace.jsonl")
        client.trace_movement_path = str(trace_path)

        moved = client.move_towards_position(0, 1000, 120, step=55, stop_distance=0, movement_speed=220.0)

        events = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        trace_path.unlink(missing_ok=True)

        move_step = next(event for event in events if event["event"] == "move_step")
        self.assertTrue(moved)
        self.assertEqual(move_step["from_y"], 0)
        self.assertEqual(move_step["y"], 55)
        self.assertEqual(move_step["target_y"], 1000)
        self.assertEqual(move_step["z_source"], "interpolated")

    def test_read_packets_for_limits_socket_timeout_to_requested_window(self):
        class TimeoutSocket:
            def __init__(self) -> None:
                self.timeout = 0.15
                self.calls: list[float] = []

            def settimeout(self, value: float) -> None:
                self.timeout = value
                self.calls.append(value)

            def recv(self, _size: int) -> bytes:
                time.sleep(self.timeout)
                raise socket.timeout()

        client = self.make_client()
        fake_socket = TimeoutSocket()
        client.sock = fake_socket
        client.read_timeout = 0.15

        started = time.monotonic()
        packets = client.read_packets_for(0.02)
        elapsed = time.monotonic() - started

        self.assertEqual(packets, [])
        self.assertLess(elapsed, 0.08)
        self.assertLessEqual(min(fake_socket.calls), 0.03)
        self.assertAlmostEqual(fake_socket.calls[-1], 0.15, places=2)
        self.assertLessEqual(client.y, 125)

    def test_observes_chat_message(self):
        client = self.make_client()

        client.observe_packet(headless.ServerPacket(0xAF, bytes([7]) + "??곸씠 ?ш굅由?諛뽰뿉 ?덉뒿?덈떎".encode("utf-8") + b"\x00"))

        messages = client.consume_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].chat_type, 7)
        self.assertEqual(messages[0].text, "??곸씠 ?ш굅由?諛뽰뿉 ?덉뒿?덈떎")
        self.assertEqual(client.consume_messages(), [])

    def test_observes_cp949_chat_message(self):
        client = self.make_client()
        text = "획득: 검을 얻어 가방에 넣었습니다"

        client.observe_packet(
            headless.ServerPacket(
                0xAF,
                bytes([18]) + text.encode("cp949") + b"\x00",
            )
        )

        messages = client.consume_messages()
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0].chat_type, 18)
        self.assertEqual(messages[0].text, text)


class HeadlessGracefulDisconnectTests(unittest.TestCase):
    class _ClosingSocket:
        def __init__(self) -> None:
            self.sent: list[bytes] = []
            self.closed = False
            self.timeout = None
            self.recv_calls = 0

        def settimeout(self, value) -> None:
            self.timeout = value

        def sendall(self, payload: bytes) -> None:
            self.sent.append(payload)

        def recv(self, _size: int) -> bytes:
            self.recv_calls += 1
            return b""

        def close(self) -> None:
            self.closed = True

    def test_disconnect_gracefully_sends_quit_and_waits_for_close(self):
        client = headless.HeadlessDaocClient("127.0.0.1", 10300, 1.0, verbose=False)
        mock = self._ClosingSocket()
        client.session_id = 42
        client.sequence = 1
        client.x = 523520
        client.y = 490520
        client.z = 2543
        client.sock = mock

        self.assertTrue(client.disconnect_gracefully(timeout=1.0))
        self.assertIsNone(client.sock)

        payloads = b"".join(mock.sent)
        self.assertIn(b"&sit\x00", payloads)
        self.assertIn(b"&quit\x00", payloads)
        self.assertTrue(mock.closed)


if __name__ == "__main__":
    raise SystemExit(unittest.main())
