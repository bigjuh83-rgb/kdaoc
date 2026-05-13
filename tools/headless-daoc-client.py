#!/usr/bin/env python3
"""Minimal OpenDAoC headless client for local server smoke tests.

This is intentionally tiny and only drives the login/character-enter path used by
OpenDAoC development. It is not a game client replacement.
"""

from __future__ import annotations

import argparse
import math
import os
import socket
import struct
import time
from dataclasses import dataclass


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
    "dialog_response": 0x82,
    "use_slot": 0x71,
    "use_spell": 0x7D,
    "use_skill": 0xBB,
    "interact": 0x7A,
    "check_los": 0xD0,
    "command": 0xAF,
}

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
        self.sock: socket.socket | None = None
        self.recv_buffer = bytearray()
        self.npcs: dict[int, KnownNpc] = {}
        self.players: dict[int, KnownPlayer] = {}
        self.removed_object_ids: list[int] = []
        self.messages: list[ChatMessage] = []

    def connect(self) -> None:
        self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self.sock.settimeout(0.15)

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

    def read_packets_for(self, seconds: float) -> list[ServerPacket]:
        if self.sock is None:
            raise RuntimeError("client is not connected")

        deadline = time.monotonic() + seconds
        packets: list[ServerPacket] = []

        while time.monotonic() < deadline:
            try:
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

    def send_heading(self, heading: int) -> int:
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
        return self.drain(0.05)

    def send_position_update(self, speed: float = 0.0, target_in_view: bool = False) -> int:
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
        self.send_packet(CLIENT_PACKETS["attack"], bytes([1 if enabled else 0, 0]))
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

    def use_skill(self, index: int, skill_type: int = 1, target_in_view: bool = True) -> int:
        data = self.build_action_payload(target_in_view=target_in_view)
        data += bytes([index & 0xFF, skill_type & 0xFF])
        self.send_packet(CLIENT_PACKETS["use_skill"], bytes(data))
        return self.drain(0.05)

    def use_spell(self, spell_level: int, spell_line_index: int = 0, target_in_view: bool = True) -> int:
        data = self.build_action_payload(target_in_view=target_in_view)
        data += bytes([spell_level & 0xFF, spell_line_index & 0xFF])
        data += b"\x00\x00"
        self.send_packet(CLIENT_PACKETS["use_spell"], bytes(data))
        return self.drain(0.05)

    def use_slot(self, slot: int, use_type: int = 0, target_in_view: bool = True) -> int:
        data = self.build_action_payload(target_in_view=target_in_view)
        data += bytes([slot & 0xFF, use_type & 0xFF])
        self.send_packet(CLIENT_PACKETS["use_slot"], bytes(data))
        return self.drain(0.05)

    def build_action_payload(self, target_in_view: bool = True) -> bytearray:
        flag_speed_data = 0xA000 if target_in_view else 0
        data = bytearray()
        data += struct.pack("<f", float(self.x))
        data += struct.pack("<f", float(self.y))
        data += struct.pack("<f", float(self.z))
        data += struct.pack("<f", 0.0)
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

    def move_towards(self, obj, step: float = 250.0, stop_distance: float = 250.0) -> bool:
        return self.move_towards_position(obj.x, obj.y, obj.z, step=step, stop_distance=stop_distance)

    def move_towards_position(self, x: int, y: int, z: int, step: float = 250.0, stop_distance: float = 250.0) -> bool:
        dx = x - self.x
        dy = y - self.y
        dz = z - self.z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if distance <= stop_distance or distance <= 0:
            if distance > 0:
                self.heading = heading_from_delta(dx, dy)
            self.send_position_update(speed=0.0, target_in_view=True)
            return False

        travel = min(step, max(distance - stop_distance, 0))
        ratio = travel / distance
        self.x = int(self.x + dx * ratio)
        self.y = int(self.y + dy * ratio)
        self.z = int(self.z + dz * ratio)
        self.heading = heading_from_delta(dx, dy)
        self.send_position_update(speed=travel, target_in_view=True)
        return True

    def wander(self, heading: int, step: float = 250.0) -> None:
        self.heading = heading & 0x0FFF
        radians = self.heading / 4096 * (math.pi * 2)
        self.x = int(self.x + math.sin(radians) * step)
        self.y = int(self.y + math.cos(radians) * step)
        self.send_position_update(speed=step, target_in_view=False)

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

        self.x = int(struct.unpack_from("<f", data, 0)[0])
        self.y = int(struct.unpack_from("<f", data, 4)[0])
        self.z = int(struct.unpack_from("<f", data, 8)[0])
        self.player_object_id = struct.unpack_from(">H", data, 12)[0]
        self.heading = struct.unpack_from(">H", data, 14)[0]
        self.zone_id = struct.unpack_from(">H", data, 20)[0]

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

        player.x = int(struct.unpack_from("<f", data, 0)[0])
        player.y = int(struct.unpack_from("<f", data, 4)[0])
        player.z = int(struct.unpack_from("<f", data, 8)[0])
        player.heading = struct.unpack_from(">H", data, 30)[0]
        player.last_seen = time.monotonic()

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

    def observe_player_revive(self, data: bytes) -> None:
        if len(data) < 2:
            return

        object_id = struct.unpack_from(">H", data, 0)[0]

        if object_id == self.player_object_id:
            self.is_dead = False

    def observe_message(self, data: bytes) -> None:
        if len(data) < 2:
            return

        chat_type = data[0]
        text = data[1:].split(b"\x00", 1)[0].decode("utf-8", errors="replace")
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

    radians = math.atan2(dx, dy)
    heading = int((radians % (math.pi * 2)) / (math.pi * 2) * 4096)
    return heading & 0x0FFF


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
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
