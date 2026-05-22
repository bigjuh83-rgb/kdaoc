#!/usr/bin/env python3
"""Minimal OpenDAoC headless client for local server smoke tests.

This is intentionally tiny and only drives the login/character-enter path used by
OpenDAoC development. It is not a game client replacement.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import socket
import struct
import time
from dataclasses import dataclass
from typing import Callable


CLIENT_PACKETS = {
    "crypt_key_request": 0xF4,
    "login_request": 0xA7,
    "character_overview_request": 0xFC,
    "character_select_request": 0x10,
    "world_init_request": 0xD4,
    "game_open_request": 0xBF,
    "player_init_request": 0xE8,
    "ping": 0xA3,
    "position": 0xA9,
    "heading": 0xBA,
    "target": 0xB0,
    "attack": 0x74,
    "buy": 0x78,
    "sell": 0x79,
    "dialog_response": 0x82,
    "move_item": 0xDD,
    "use_slot": 0x71,
    "use_spell": 0x7D,
    "use_skill": 0xBB,
    "interact": 0x7A,
    "check_los": 0xD0,
    "command": 0xAF,
}

DEFAULT_DUMMY_HOST = os.environ.get("OPENDAOC_DUMMY_HOST", "192.168.0.42")

SERVER_PACKETS = {
    0x22: "CryptKey",
    0x28: "SessionID",
    0x2A: "LoginGranted",
    0x4B: "PlayerCreate172",
    0xAF: "Message",
    0x89: "PlayerRevive",
    0xA9: "PlayerPosition",
    0xAD: "CharacterStatusUpdate",
    0xAE: "PlayerDeath",
    0xD0: "CheckLOSRequest",
    0xD4: "PlayerCreate",
    0xFE: "Realm",
    0xFC: "CharacterOverview1126",
}


@dataclass
class KnownNpc:
    object_id: int
    name: str
    x: int
    y: int
    z: int
    level: int
    flags: int
    last_seen: float


@dataclass
class KnownPlayer:
    object_id: int
    name: str
    x: int
    y: int
    z: int
    heading: int
    realm: int
    level: int
    last_seen: float


@dataclass
class ServerPacket:
    code: int
    data: bytes

    @property
    def name(self) -> str:
        return SERVER_PACKETS.get(self.code, f"0x{self.code:02X}")


@dataclass
class ChatMessage:
    chat_type: int
    text: str
    last_seen: float


class HeadlessDaocClient:
    def __init__(self, host: str, port: int, timeout: float, verbose: bool = True) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.verbose = verbose
        self.sequence = 0
        self.session_id = 0
        self.player_object_id = 0
        self.x = 0
        self.y = 0
        self.z = 0
        self.heading = 0
        self.zone_id = 0
        self.health_percent = 100
        self.mana_percent = 100
        self.endurance_percent = 100
        self.is_dead = False
        self.attack_mode_enabled: bool | None = None
        self.last_position_speed = 0.0
        self.last_position_target_in_view = False
        self.last_position_update_sent_at = 0.0
        self.last_local_move_at = 0.0
        self.last_sent_position = (0, 0, 0)
        self.last_local_movement_speed = 0.0
        self.server_correction_smoothing = False
        self.server_correction_min_distance = 20.0
        self.server_correction_step = 45.0
        self.server_correction_max_snap_distance = 800.0
        self.ground_z_sampler: Callable[[int, int, int], int | None] | None = None
        self.trace_movement_path: str | None = None
        self.trace_observed_player_positions = False
        self.read_timeout = 0.15
        self.sock: socket.socket | None = None
        self.recv_buffer = bytearray()
        self.npcs: dict[int, KnownNpc] = {}
        self.players: dict[int, KnownPlayer] = {}
        self.removed_object_ids: list[int] = []
        self.messages: list[ChatMessage] = []

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.read_timeout = min(0.15, max(self.timeout, 0.01))
        self.sock.settimeout(self.read_timeout)

    def close(self) -> None:
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

    def send_packet(self, code: int, data: bytes = b"", session_id: int | None = None) -> None:
        if self.sock is None:
            raise RuntimeError("client is not connected")

        packet_session = self.session_id if session_id is None else session_id
        header = bytearray()
        header += struct.pack(">H", len(data))
        header += struct.pack(">H", self.sequence & 0xFFFF)
        header += struct.pack(">H", packet_session & 0xFFFF)
        header += b"\x00\x00"
        header += b"\x00"
        header += bytes([code])
        packet = header + data
        checksum = self.calculate_checksum(packet)
        packet += struct.pack(">H", checksum)
        self.sock.sendall(packet)
        self.sequence += 1

    def trace_movement(self, event: str, **fields) -> None:
        if not self.trace_movement_path:
            return

        payload = {"t": time.monotonic(), "event": event}
        payload.update(fields)

        with open(self.trace_movement_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")

    def read_packets_for(self, seconds: float) -> list[ServerPacket]:
        if self.sock is None:
            raise RuntimeError("client is not connected")

        deadline = time.monotonic() + seconds
        packets: list[ServerPacket] = []

        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()

            if remaining <= 0:
                break

            try:
                self.sock.settimeout(min(self.read_timeout, max(remaining, 0.001)))
                chunk = self.sock.recv(65535)
            except socket.timeout:
                continue

            if not chunk:
                break

            self.recv_buffer += chunk

            while len(self.recv_buffer) >= 3:
                packet_size = int.from_bytes(self.recv_buffer[0:2], "big") + 3

                if len(self.recv_buffer) < packet_size:
                    break

                raw = bytes(self.recv_buffer[:packet_size])
                del self.recv_buffer[:packet_size]
                packet = ServerPacket(raw[2], raw[3:])
                packets.append(packet)
                self.observe_packet(packet)

                if packet.code == 0x28 and len(packet.data) >= 2:
                    self.session_id = int.from_bytes(packet.data[:2], "little")

        self.sock.settimeout(self.read_timeout)
        return packets

    def drain(self, seconds: float = 0.05) -> int:
        return len(self.read_packets_for(seconds))

    def drive_login(self, username: str, password: str, realm: int, char_index: int) -> None:
        self.connect()
        self.send_packet(CLIENT_PACKETS["crypt_key_request"], bytes([0x36, 1, 1, 27, 0, 0, 0]), session_id=0)
        self.print_packets("crypt", self.read_packets_for(0.5))

        self.send_packet(CLIENT_PACKETS["login_request"], int_pascal(username) + int_pascal(password), session_id=0)
        self.print_packets("login", self.read_packets_for(1.0))

        self.send_packet(CLIENT_PACKETS["character_overview_request"], bytes([realm]), session_id=0)
        self.print_packets("overview", self.read_packets_for(1.0))

        self.send_packet(CLIENT_PACKETS["character_select_request"], b"", session_id=0)
        self.print_packets("select", self.read_packets_for(1.0))

        if self.session_id == 0:
            raise RuntimeError("server did not send a session id")

        self.send_packet(CLIENT_PACKETS["world_init_request"], bytes([char_index]))
        self.print_packets("world_init", self.read_packets_for(1.5))

        self.send_packet(CLIENT_PACKETS["game_open_request"], b"\x00")
        self.print_packets("game_open", self.read_packets_for(0.5))

        self.send_packet(CLIENT_PACKETS["player_init_request"], b"")
        self.print_packets("player_init", self.read_packets_for(1.0))

    def send_command(self, command: str) -> None:
        if command.startswith("/"):
            command = "&" + command[1:]
        self.send_packet(CLIENT_PACKETS["command"], b"\x00" + command.encode("utf-8") + b"\x00")
        self.print_packets(f"command {command}", self.read_packets_for(1.0))

    def send_ping(self) -> int:
        timestamp = int(time.monotonic() * 1000) & 0xFFFFFFFF
        self.send_packet(CLIENT_PACKETS["ping"], b"\x00\x00\x00\x00" + struct.pack(">I", timestamp))
        return self.drain(0.05)

    def send_heading(self, heading: int, *, drain_after: bool = True) -> int:
        self.heading = heading & 0x0FFF
        data = bytearray()
        data += struct.pack(">H", self.session_id & 0xFFFF)
        data += b"\x00\x00"  # target/object id for 1.127.
        data += struct.pack(">H", self.heading)
        data += b"\x00"  # unknown.
        data += b"\x00"  # action flags.
        data += b"\x00"  # steed slot.
        data += b"\x00"  # state flags.
        self.send_packet(CLIENT_PACKETS["heading"], bytes(data))
        return self.drain(0.05) if drain_after else 0

    def send_position_update(self, speed: float = 0.0, target_in_view: bool = False) -> int:
        if self.is_dead:
            self.trace_movement(
                "skip_send_position_dead",
                x=int(self.x),
                y=int(self.y),
                z=int(self.z),
                speed=f"{float(speed):.3f}",
                heading=int(self.heading & 0x0FFF),
                target_in_view=int(target_in_view),
            )
            return 0

        self.last_position_speed = float(speed)
        self.last_position_target_in_view = bool(target_in_view)
        self.last_position_update_sent_at = time.monotonic()
        self.last_sent_position = (int(self.x), int(self.y), int(self.z))
        self.trace_movement(
            "send_position",
            x=int(self.x),
            y=int(self.y),
            z=int(self.z),
            speed=f"{float(speed):.3f}",
            heading=int(self.heading & 0x0FFF),
            target_in_view=int(target_in_view),
        )
        action_flags = 0x30 if target_in_view else 0
        data = bytearray()
        data += struct.pack("<f", float(self.x))
        data += struct.pack("<f", float(self.y))
        data += struct.pack("<f", float(self.z))
        data += struct.pack("<f", float(speed))
        data += struct.pack("<f", 0.0)  # fall speed.
        data += struct.pack(">H", self.session_id & 0xFFFF)
        data += struct.pack(">H", self.player_object_id & 0xFFFF)
        data += struct.pack(">H", self.zone_id & 0xFFFF)
        data += b"\x00"  # state flags.
        data += b"\x00"  # unknown.
        data += b"\x00\x00"  # falling damage / steed seat.
        data += struct.pack(">H", self.heading & 0x0FFF)
        data += bytes([action_flags])
        data += b"\x00\x00"  # rp flag / unknown.
        data += b"\x64"  # health byte.
        data += b"\x64"  # mana percent.
        data += b"\x64"  # endurance percent.
        data += b"\x00\x00"
        self.send_packet(CLIENT_PACKETS["position"], bytes(data))
        return self.drain(0.05)

    def send_corpse_position_update(self) -> int:
        self.last_position_speed = 0.0
        self.last_position_target_in_view = False
        self.last_position_update_sent_at = time.monotonic()
        self.last_sent_position = (int(self.x), int(self.y), int(self.z))
        self.trace_movement(
            "send_corpse_position",
            x=int(self.x),
            y=int(self.y),
            z=int(self.z),
            heading=int(self.heading & 0x0FFF),
        )
        data = bytearray()
        data += struct.pack("<f", float(self.x))
        data += struct.pack("<f", float(self.y))
        data += struct.pack("<f", float(self.z))
        data += struct.pack("<f", 0.0)
        data += struct.pack("<f", 0.0)
        data += struct.pack(">H", self.session_id & 0xFFFF)
        data += struct.pack(">H", self.player_object_id & 0xFFFF)
        data += struct.pack(">H", self.zone_id & 0xFFFF)
        data += b"\x14"  # SITTING | SWIMMING: client corpse/death pose.
        data += b"\x00"
        data += b"\x00\x00"
        data += struct.pack(">H", self.heading & 0x0FFF)
        data += b"\x00"
        data += b"\x00\x00"
        data += b"\x00"
        data += b"\x64"
        data += b"\x64"
        data += b"\x00\x00"
        self.send_packet(CLIENT_PACKETS["position"], bytes(data))
        return self.drain(0.05)

    def clear_target(self) -> int:
        self.send_packet(CLIENT_PACKETS["target"], b"\x00\x00\x00\x00")
        return self.drain(0.05)

    def target_object(self, object_id: int, examine: bool = False) -> int:
        flags = 0x6000

        if examine:
            flags |= 0x8000

        self.send_packet(CLIENT_PACKETS["target"], struct.pack(">HH", object_id & 0xFFFF, flags))
        return self.drain(0.05)

    def interact_object(self, object_id: int) -> int:
        data = bytearray()
        data += struct.pack(">I", max(self.x, 0) & 0xFFFFFFFF)
        data += struct.pack(">I", max(self.y, 0) & 0xFFFFFFFF)
        data += struct.pack(">H", self.session_id & 0xFFFF)
        data += struct.pack(">H", object_id & 0xFFFF)
        self.send_packet(CLIENT_PACKETS["interact"], bytes(data))
        return self.drain(0.05)

    def set_attack_mode(self, enabled: bool) -> int:
        if self.attack_mode_enabled == bool(enabled):
            self.trace_movement("attack_mode_skip", enabled=bool(enabled))
            return 0

        self.attack_mode_enabled = bool(enabled)
        self.send_packet(CLIENT_PACKETS["attack"], bytes([1 if enabled else 0, 0]))
        self.trace_movement("attack_mode", enabled=bool(enabled))
        return self.drain(0.05)

    def accept_group_invite(self, leader_session_id: int) -> int:
        data = bytearray()
        data += struct.pack(">H", leader_session_id & 0xFFFF)
        data += b"\x00\x00"
        data += b"\x00\x00"
        data += b"\x05"  # eDialogCode.GroupInvite
        data += b"\x01"  # accept
        self.send_packet(CLIENT_PACKETS["dialog_response"], bytes(data))
        return self.drain(0.05)

    def accept_custom_dialog(self, response: int = 1) -> int:
        data = bytearray()
        data += b"\x00\x00"
        data += b"\x00\x01"
        data += b"\x00\x00"
        data += b"\x01"  # eDialogCode.CustomDialog
        data += bytes([response & 0xFF])
        self.send_packet(CLIENT_PACKETS["dialog_response"], bytes(data))
        return self.drain(0.05)

    def buy_item(self, slot: int, count: int = 1, menu_id: int = 0) -> int:
        data = bytearray()
        data += struct.pack(">I", max(self.x, 0) & 0xFFFFFFFF)
        data += struct.pack(">I", max(self.y, 0) & 0xFFFFFFFF)
        data += struct.pack(">H", self.player_object_id & 0xFFFF)
        data += struct.pack(">H", slot & 0xFFFF)
        data += bytes([max(1, min(count, 255)) & 0xFF])
        data += bytes([menu_id & 0xFF])
        self.send_packet(CLIENT_PACKETS["buy"], bytes(data))
        return self.drain(0.05)

    def sell_item(self, slot: int) -> int:
        data = bytearray()
        data += struct.pack(">I", max(self.x, 0) & 0xFFFFFFFF)
        data += struct.pack(">I", max(self.y, 0) & 0xFFFFFFFF)
        data += struct.pack(">H", self.player_object_id & 0xFFFF)
        data += struct.pack(">H", slot & 0xFFFF)
        self.send_packet(CLIENT_PACKETS["sell"], bytes(data))
        return self.drain(0.05)

    def move_item(self, from_slot: int, to_slot: int, count: int = 1) -> int:
        data = bytearray()
        data += b"\x00\x00"
        data += struct.pack(">H", to_slot & 0xFFFF)
        data += struct.pack(">H", from_slot & 0xFFFF)
        data += struct.pack(">H", max(1, min(count, 0xFFFF)) & 0xFFFF)
        self.send_packet(CLIENT_PACKETS["move_item"], bytes(data))
        return self.drain(0.05)

    def use_skill(self, index: int, skill_type: int = 1, target_in_view: bool = True, speed: float | None = None) -> int:
        data = self.build_action_payload(target_in_view=target_in_view, speed=speed)
        data += bytes([index & 0xFF, skill_type & 0xFF])
        self.send_packet(CLIENT_PACKETS["use_skill"], bytes(data))
        return self.drain(0.05)

    def use_spell(self, spell_level: int, spell_line_index: int = 0, target_in_view: bool = True, speed: float | None = None) -> int:
        data = self.build_action_payload(target_in_view=target_in_view, speed=speed)
        data += bytes([spell_level & 0xFF, spell_line_index & 0xFF])
        data += b"\x00\x00"
        self.send_packet(CLIENT_PACKETS["use_spell"], bytes(data))
        return self.drain(0.05)

    def use_slot(self, slot: int, use_type: int = 0, target_in_view: bool = True, speed: float | None = None) -> int:
        data = self.build_action_payload(target_in_view=target_in_view, speed=speed)
        data += bytes([slot & 0xFF, use_type & 0xFF])
        self.send_packet(CLIENT_PACKETS["use_slot"], bytes(data))
        return self.drain(0.05)

    def build_action_payload(self, target_in_view: bool = True, speed: float | None = None) -> bytearray:
        flag_speed_data = 0xA000 if target_in_view else 0
        movement_speed = self.last_position_speed if speed is None else speed
        last_sent_x, last_sent_y, last_sent_z = self.last_sent_position
        has_unsent_position = (int(self.x), int(self.y), int(self.z)) != (last_sent_x, last_sent_y, last_sent_z)
        payload_x = self.x
        payload_y = self.y
        payload_z = self.z

        if has_unsent_position:
            payload_x = last_sent_x
            payload_y = last_sent_y
            payload_z = last_sent_z

        data = bytearray()
        data += struct.pack("<f", float(payload_x))
        data += struct.pack("<f", float(payload_y))
        data += struct.pack("<f", float(payload_z))
        data += struct.pack("<f", float(movement_speed))
        data += struct.pack(">H", self.heading & 0x0FFF)
        data += struct.pack(">H", flag_speed_data)
        return data

    def visible_npcs(self, max_age: float = 30.0, include_peace: bool = False) -> list[KnownNpc]:
        now = time.monotonic()
        npcs = [
            npc
            for npc in self.npcs.values()
            if now - npc.last_seen <= max_age and (include_peace or (npc.flags & 0x10) == 0)
        ]
        npcs.sort(key=lambda npc: self.distance_squared(npc))
        return npcs

    def visible_players(self, max_age: float = 30.0) -> list[KnownPlayer]:
        now = time.monotonic()
        players = [
            player
            for player in self.players.values()
            if now - player.last_seen <= max_age and player.object_id != self.player_object_id
        ]
        players.sort(key=lambda player: self.distance_squared(player))
        return players

    def distance_squared(self, obj) -> int:
        return (obj.x - self.x) ** 2 + (obj.y - self.y) ** 2 + (obj.z - self.z) ** 2

    def distance_to(self, obj) -> float:
        return math.sqrt(self.distance_squared(obj))

    def horizontal_distance_to(self, obj) -> float:
        return math.sqrt((obj.x - self.x) ** 2 + (obj.y - self.y) ** 2)

    def move_towards(self, obj, step: float = 250.0, stop_distance: float = 250.0, movement_speed: float | None = None) -> bool:
        return self.move_towards_position(obj.x, obj.y, obj.z, step=step, stop_distance=stop_distance, movement_speed=movement_speed)

    def move_towards_position(
        self,
        x: int,
        y: int,
        z: int,
        step: float = 250.0,
        stop_distance: float = 250.0,
        movement_speed: float | None = None,
        max_z_step: float = 0.0,
        min_position_send_interval: float = 0.0,
        ground_z: int | None = None,
        snap_ground_z_on_stop: bool = False,
        target_in_view: bool = False,
    ) -> bool:
        start_x = int(self.x)
        start_y = int(self.y)
        start_z = int(self.z)
        dx = x - self.x
        dy = y - self.y
        horizontal_distance = math.sqrt(dx * dx + dy * dy)

        if horizontal_distance <= stop_distance or horizontal_distance <= 0:
            if ground_z is not None and snap_ground_z_on_stop:
                self.z = int(ground_z)
            should_send_stop = (
                self.last_position_speed != 0.0
                or (target_in_view and not self.last_position_target_in_view)
                or min_position_send_interval <= 0
                or time.monotonic() - self.last_position_update_sent_at >= min_position_send_interval
            )
            if horizontal_distance > 0:
                self.heading = heading_from_delta(dx, dy)
                if not should_send_stop:
                    self.send_heading(self.heading, drain_after=False)
            if should_send_stop:
                self.send_position_update(speed=0.0, target_in_view=target_in_view)
            else:
                self.trace_movement(
                    "skip_stop_send",
                    x=int(self.x),
                    y=int(self.y),
                    z=int(self.z),
                    heading=int(self.heading & 0x0FFF),
                )
            return False

        now = time.monotonic()
        travel_limit = step

        movement_reference_time = max(self.last_local_move_at, self.last_position_update_sent_at)

        if movement_speed is not None and movement_speed > 0 and movement_reference_time > 0.0:
            elapsed = max(0.0, now - movement_reference_time)
            # Follow elapsed wall-clock time instead of forcing a full smooth step every tick.
            # Forcing `step` here makes a 55-unit smooth step fire every 0.05s tick, which
            # overshoots the advertised speed and looks like forward walking mixed with teleporting.
            travel_limit = min(max(1.0, movement_speed * elapsed), max(1.0, movement_speed * 1.0))

        travel = min(travel_limit, max(horizontal_distance - stop_distance, 0))
        ratio = travel / horizontal_distance
        next_x = int(self.x + dx * ratio)
        next_y = int(self.y + dy * ratio)
        sampled_ground_z = self.ground_z_sampler(next_x, next_y, self.zone_id) if self.ground_z_sampler else None

        # Near the stop boundary, integer world coordinates can quantize a valid sub-unit move
        # into "no position change". Treat that as arrival instead of repeatedly advertising run
        # speed at the same coordinates, which looks like in-place rewind/rubber-banding in game.
        if next_x == self.x and next_y == self.y:
            self.heading = heading_from_delta(dx, dy)
            self.send_position_update(speed=0.0, target_in_view=target_in_view)
            return False

        self.x = next_x
        self.y = next_y
        self.last_local_move_at = now
        z_source = "interpolated"

        if sampled_ground_z is not None:
            self.z = int(sampled_ground_z)
            z_source = "ground_z_sampler"
            self.trace_movement(
                "ground_z_sample",
                x=int(self.x),
                y=int(self.y),
                z=int(self.z),
                target_x=int(x),
                target_y=int(y),
                zone=int(self.zone_id),
            )
        elif ground_z is not None:
            self.z = int(ground_z)
            z_source = "explicit_ground_z"
        else:
            dz = z - self.z

            if dz:
                z_step = dz * ratio

                if max_z_step > 0:
                    z_step = max(-max_z_step, min(max_z_step, z_step))

                self.z = int(self.z + z_step)

        self.heading = heading_from_delta(dx, dy)
        display_speed = movement_speed if movement_speed is not None and movement_speed > 0 else travel
        self.last_local_movement_speed = float(display_speed)
        self.trace_movement(
            "move_step",
            from_x=start_x,
            from_y=start_y,
            from_z=start_z,
            x=int(self.x),
            y=int(self.y),
            z=int(self.z),
            target_x=int(x),
            target_y=int(y),
            target_z=int(z),
            horizontal_distance=f"{float(horizontal_distance):.3f}",
            travel=f"{float(travel):.3f}",
            ratio=f"{float(ratio):.6f}",
            heading=int(self.heading & 0x0FFF),
            speed=f"{float(display_speed):.3f}",
            z_source=z_source,
            sampled_ground_z="" if sampled_ground_z is None else int(sampled_ground_z),
            zone=int(self.zone_id),
        )
        should_send_position = (
            min_position_send_interval <= 0
            or self.last_position_speed == 0.0
            or (target_in_view and not self.last_position_target_in_view)
            or now - self.last_position_update_sent_at >= min_position_send_interval
        )

        if not should_send_position:
            self.trace_movement(
                "skip_move_send",
                x=int(self.x),
                y=int(self.y),
                z=int(self.z),
                heading=int(self.heading & 0x0FFF),
                speed=f"{float(display_speed):.3f}",
            )
            return True

        self.send_position_update(speed=display_speed, target_in_view=target_in_view)
        return True

    def wander(
        self,
        heading: int,
        step: float = 250.0,
        movement_speed: float | None = None,
        min_position_send_interval: float = 0.0,
    ) -> None:
        self.heading = heading & 0x0FFF
        radians = self.heading / 4096 * (math.pi * 2)
        now = time.monotonic()
        travel = step

        movement_reference_time = max(self.last_local_move_at, self.last_position_update_sent_at)

        if movement_speed is not None and movement_speed > 0 and movement_reference_time > 0.0:
            elapsed = max(0.0, now - movement_reference_time)
            travel = min(step, max(1.0, movement_speed * elapsed), max(1.0, movement_speed * 1.0))

        self.x = int(self.x - math.sin(radians) * travel)
        self.y = int(self.y + math.cos(radians) * travel)
        self.last_local_move_at = now
        self.last_local_movement_speed = float(movement_speed if movement_speed is not None and movement_speed > 0 else travel)

        if (
            min_position_send_interval > 0
            and self.last_position_speed != 0.0
            and time.monotonic() - self.last_position_update_sent_at < min_position_send_interval
        ):
            return

        self.send_position_update(speed=movement_speed if movement_speed is not None and movement_speed > 0 else travel, target_in_view=False)

    def observe_packet(self, packet: ServerPacket) -> None:
        if packet.code == 0x20:
            self.observe_position_and_object_id(packet.data)
        elif packet.code in {0x4B, 0xD4}:
            self.observe_player_create(packet.data, modern=packet.code == 0x4B)
        elif packet.code == 0xA9:
            self.observe_player_position(packet.data)
        elif packet.code == 0xDA:
            self.observe_npc_create(packet.data)
        elif packet.code in {0xA2, 0xE1}:
            self.observe_object_remove(packet.data)
        elif packet.code == 0xD0:
            self.send_los_response(packet.data)
        elif packet.code == 0x89:
            self.observe_player_revive(packet.data)
        elif packet.code == 0xAD:
            self.observe_status_update(packet.data)
        elif packet.code == 0xAE:
            self.observe_player_death(packet.data)
        elif packet.code == 0xAF:
            self.observe_message(packet.data)

    def observe_position_and_object_id(self, data: bytes) -> None:
        if len(data) < 22:
            return

        server_x = int(struct.unpack_from("<f", data, 0)[0])
        server_y = int(struct.unpack_from("<f", data, 4)[0])
        server_z = int(struct.unpack_from("<f", data, 8)[0])
        object_id = struct.unpack_from(">H", data, 12)[0]
        server_heading = struct.unpack_from(">H", data, 14)[0]
        server_zone_id = struct.unpack_from(">H", data, 20)[0]
        should_smooth = self.server_correction_smoothing and self.player_object_id != 0
        previous_x = int(self.x)
        previous_y = int(self.y)
        previous_z = int(self.z)
        delta_x = server_x - previous_x
        delta_y = server_y - previous_y
        delta_z = server_z - previous_z
        horizontal_delta = math.sqrt(delta_x * delta_x + delta_y * delta_y)

        if should_smooth:
            dx = delta_x
            dy = delta_y
            dz = delta_z
            horizontal_distance = horizontal_delta

            if self.server_correction_min_distance <= horizontal_distance <= self.server_correction_max_snap_distance:
                correction = min(self.server_correction_step, horizontal_distance)
                ratio = correction / horizontal_distance if horizontal_distance > 0 else 0.0
                self.x = int(self.x + dx * ratio)
                self.y = int(self.y + dy * ratio)
                self.z = int(self.z + dz * ratio)
                self.heading = server_heading
                self.zone_id = server_zone_id
                self.trace_movement(
                    "observe_self_position_smooth",
                    x=int(self.x),
                    y=int(self.y),
                    z=int(self.z),
                    server_x=int(server_x),
                    server_y=int(server_y),
                    server_z=int(server_z),
                    correction=f"{float(correction):.3f}",
                    distance=f"{float(horizontal_distance):.3f}",
                    heading=int(self.heading & 0x0FFF),
                    zone=int(self.zone_id),
                )
                return

        self.x = server_x
        self.y = server_y
        self.z = server_z
        self.player_object_id = object_id
        self.heading = server_heading
        self.zone_id = server_zone_id
        self.trace_movement(
            "observe_self_position",
            x=int(self.x),
            y=int(self.y),
            z=int(self.z),
            previous_x=previous_x,
            previous_y=previous_y,
            previous_z=previous_z,
            delta_x=int(delta_x),
            delta_y=int(delta_y),
            delta_z=int(delta_z),
            horizontal_delta=f"{float(horizontal_delta):.3f}",
            heading=int(self.heading & 0x0FFF),
            zone=int(self.zone_id),
        )

    def observe_status_update(self, data: bytes) -> None:
        if len(data) < 4:
            return

        self.health_percent = data[0]
        self.mana_percent = data[1]
        self.endurance_percent = data[3]

        if self.health_percent == 0:
            self.is_dead = True

    def observe_npc_create(self, data: bytes) -> None:
        if len(data) < 29:
            return

        object_id = struct.unpack_from(">H", data, 0)[0]

        if object_id == 0 or object_id == self.player_object_id:
            return

        z = struct.unpack_from(">h", data, 6)[0]
        x = struct.unpack_from(">I", data, 8)[0]
        y = struct.unpack_from(">I", data, 12)[0]
        level = data[21] & 0x7F
        flags = data[22]
        name_offset = 28
        name_length = data[name_offset]
        name_start = name_offset + 1
        name_end = min(name_start + name_length, len(data))
        name = data[name_start:name_end].decode("utf-8", errors="replace") or f"npc-{object_id}"
        self.npcs[object_id] = KnownNpc(object_id, name, x, y, z, level, flags, time.monotonic())

    def observe_player_create(self, data: bytes, modern: bool = True) -> None:
        if modern:
            self.observe_player_create_1124(data)
        else:
            self.observe_player_create_168(data)

    def observe_player_create_1124(self, data: bytes) -> None:
        if len(data) < 33:
            return

        object_id = struct.unpack_from(">H", data, 14)[0]

        if object_id == 0 or object_id == self.player_object_id:
            return

        x = int(struct.unpack_from("<f", data, 0)[0])
        y = int(struct.unpack_from("<f", data, 4)[0])
        z = int(struct.unpack_from("<f", data, 8)[0])
        heading = struct.unpack_from(">H", data, 16)[0]
        level = data[20]
        flags = data[21]
        realm = (flags >> 2) & 0x03
        name, _ = read_pascal_string(data, 32)
        self.players[object_id] = KnownPlayer(
            object_id=object_id,
            name=name or f"player-{object_id}",
            x=x,
            y=y,
            z=z,
            heading=heading,
            realm=realm,
            level=level,
            last_seen=time.monotonic(),
        )

    def observe_player_create_168(self, data: bytes) -> None:
        if len(data) < 23:
            return

        object_id = struct.unpack_from(">H", data, 2)[0]

        if object_id == 0 or object_id == self.player_object_id:
            return

        x = struct.unpack_from(">H", data, 4)[0]
        y = struct.unpack_from(">H", data, 6)[0]
        z = struct.unpack_from(">H", data, 10)[0]
        heading = struct.unpack_from(">H", data, 12)[0]
        realm = data[18]
        level = data[19]
        name, _ = read_pascal_string(data, 22)
        self.players[object_id] = KnownPlayer(
            object_id=object_id,
            name=name or f"player-{object_id}",
            x=x,
            y=y,
            z=z,
            heading=heading,
            realm=realm,
            level=level,
            last_seen=time.monotonic(),
        )

    def observe_player_position(self, data: bytes) -> None:
        if len(data) < 39:
            return

        object_id = struct.unpack_from(">H", data, 22)[0]
        player = self.players.get(object_id)

        if player is None:
            return

        previous_x = int(player.x)
        previous_y = int(player.y)
        previous_z = int(player.z)
        player.x = int(struct.unpack_from("<f", data, 0)[0])
        player.y = int(struct.unpack_from("<f", data, 4)[0])
        player.z = int(struct.unpack_from("<f", data, 8)[0])
        player.heading = struct.unpack_from(">H", data, 30)[0]
        player.last_seen = time.monotonic()
        delta_x = int(player.x - previous_x)
        delta_y = int(player.y - previous_y)
        delta_z = int(player.z - previous_z)
        horizontal_delta = math.sqrt(delta_x * delta_x + delta_y * delta_y)
        if self.trace_observed_player_positions:
            self.trace_movement(
                "observe_player_position",
                object_id=int(object_id),
                name=player.name,
                x=int(player.x),
                y=int(player.y),
                z=int(player.z),
                previous_x=previous_x,
                previous_y=previous_y,
                previous_z=previous_z,
                delta_x=delta_x,
                delta_y=delta_y,
                delta_z=delta_z,
                horizontal_delta=f"{float(horizontal_delta):.3f}",
                heading=int(player.heading & 0x0FFF),
            )

    def observe_object_remove(self, data: bytes) -> None:
        if len(data) < 2:
            return

        object_id = struct.unpack_from(">H", data, 0)[0]
        self.removed_object_ids.append(object_id)
        self.npcs.pop(object_id, None)
        self.players.pop(object_id, None)

    def consume_removed_object_ids(self) -> list[int]:
        object_ids = self.removed_object_ids
        self.removed_object_ids = []
        return object_ids

    def observe_player_death(self, data: bytes) -> None:
        if len(data) < 2:
            return

        object_id = struct.unpack_from(">H", data, 0)[0]

        if object_id == self.player_object_id:
            self.health_percent = 0
            self.is_dead = True
            self.trace_movement("player_death", object_id=int(object_id), health_percent=0)

    def observe_player_revive(self, data: bytes) -> None:
        if len(data) < 2:
            return

        object_id = struct.unpack_from(">H", data, 0)[0]

        if object_id == self.player_object_id:
            self.is_dead = False
            self.trace_movement("player_revive", object_id=int(object_id), health_percent=int(self.health_percent))

    def observe_message(self, data: bytes) -> None:
        if len(data) < 2:
            return

        chat_type = data[0]
        text = decode_daoc_text(data[1:].split(b"\x00", 1)[0])
        self.messages.append(ChatMessage(chat_type, text, time.monotonic()))

    def consume_messages(self) -> list[ChatMessage]:
        messages = self.messages
        self.messages = []
        return messages

    def send_los_response(self, data: bytes, has_los: bool = True) -> None:
        if len(data) < 4:
            return

        source_object_id = struct.unpack_from(">H", data, 0)[0]
        target_object_id = struct.unpack_from(">H", data, 2)[0]
        response = 0x0100 if has_los else 0x0000
        self.send_packet(
            CLIENT_PACKETS["check_los"],
            struct.pack(">HHH", source_object_id, target_object_id, response),
        )

    def print_packets(self, stage: str, packets: list[ServerPacket]) -> None:
        if not self.verbose:
            return

        names = ", ".join(packet.name for packet in packets[:12])
        extra = "" if len(packets) <= 12 else f", ... +{len(packets) - 12}"
        print(f"{stage}: {len(packets)} packet(s){': ' + names + extra if packets else ''}")

    @staticmethod
    def calculate_checksum(packet: bytes) -> int:
        val1 = 0x7E
        val2 = 0x7E

        for value in packet:
            val1 = (val1 + value) & 0xFF
            val2 = (val2 + val1) & 0xFF

        return (val2 - (((val1 + val2) & 0xFFFF) << 8)) & 0xFFFF


def int_pascal(value: str) -> bytes:
    encoded = value.encode("utf-8")
    return struct.pack("<I", len(encoded)) + encoded


def decode_daoc_text(data: bytes) -> str:
    if not data:
        return ""

    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp949", errors="replace")


def read_pascal_string(data: bytes, offset: int) -> tuple[str, int]:
    if offset >= len(data):
        return "", offset

    length = data[offset]
    start = offset + 1
    end = min(start + length, len(data))
    return data[start:end].decode("utf-8", errors="replace"), end


def heading_from_delta(dx: float, dy: float) -> int:
    if dx == 0 and dy == 0:
        return 0

    radians = math.atan2(-dx, dy)
    heading = int((radians % (math.pi * 2)) / (math.pi * 2) * 4096)
    return heading & 0x0FFF


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_DUMMY_HOST)
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--username", default=os.environ.get("OPENDAOC_USERNAME", "bigjuh"))
    parser.add_argument("--password", default=os.environ.get("OPENDAOC_PASSWORD", ""))
    parser.add_argument("--realm", type=int, default=1, help="1 Albion, 2 Midgard, 3 Hibernia")
    parser.add_argument("--char-index", type=int, default=0)
    parser.add_argument("--command", action="append", default=[])
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--hold", type=float, default=2.0)
    parser.add_argument("--ping-interval", type=float, default=20.0)
    parser.add_argument("--turn-interval", type=float, default=0.0)
    parser.add_argument("--show-npcs", action="store_true")
    parser.add_argument("--show-players", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if not args.password:
        raise SystemExit("missing password: pass --password or set OPENDAOC_PASSWORD")

    client = HeadlessDaocClient(args.host, args.port, args.timeout, verbose=not args.quiet)

    try:
        client.drive_login(args.username, args.password, args.realm, args.char_index)

        for command in args.command:
            client.send_command(command)

        print(f"entered session={client.session_id}; holding {args.hold:.1f}s")
        end_time = time.monotonic() + args.hold
        next_ping = time.monotonic() + max(args.ping_interval, 0.1)
        next_turn = time.monotonic() + max(args.turn_interval, 0.1)
        heading = 0

        while time.monotonic() < end_time:
            now = time.monotonic()

            if args.ping_interval > 0 and now >= next_ping:
                client.send_ping()
                next_ping = now + args.ping_interval

            if args.turn_interval > 0 and now >= next_turn:
                heading = (heading + 512) & 0x0FFF
                client.send_heading(heading)
                next_turn = now + args.turn_interval

            client.drain(0.05)

        if args.show_npcs:
            for npc in client.visible_npcs(include_peace=True)[:20]:
                peace = " peace" if npc.flags & 0x10 else ""
                print(f"npc oid={npc.object_id} level={npc.level}{peace} name={npc.name}")

        if args.show_players:
            for player in client.visible_players()[:20]:
                print(
                    f"player oid={player.object_id} level={player.level} "
                    f"realm={player.realm} name={player.name}"
                )

        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
