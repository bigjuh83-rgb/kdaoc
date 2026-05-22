#!/usr/bin/env python3
"""DAoC client zone terrain height sampling helpers."""

from __future__ import annotations

import json
import re
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path


MPK_HEADER_SIZE = 0x11C
ZONE_TILE_SIZE = 8192


@dataclass(frozen=True)
class ZoneDefinition:
    zone_id: int
    offset_x: int
    offset_y: int
    width: int = 8
    height: int = 8

    @property
    def world_x(self) -> int:
        return self.offset_x * ZONE_TILE_SIZE

    @property
    def world_y(self) -> int:
        return self.offset_y * ZONE_TILE_SIZE

    @property
    def world_width(self) -> int:
        return self.width * ZONE_TILE_SIZE

    @property
    def world_height(self) -> int:
        return self.height * ZONE_TILE_SIZE


class MpkArchive:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._files: dict[str, bytes] | None = None

    def files(self) -> dict[str, bytes]:
        if self._files is None:
            self._files = self._read_files()

        return self._files

    def _read_files(self) -> dict[str, bytes]:
        data = self.path.read_bytes()

        if struct.unpack_from("<I", data, 0)[0] != 0x4B41504D:
            raise ValueError(f"{self.path} is not an MPAK archive")

        archive_header = bytearray(data[5:21])
        for index in range(len(archive_header)):
            archive_header[index] ^= index

        _crc, directory_size, name_size, file_count = struct.unpack("<IIII", archive_header)
        directory_start = 21 + name_size
        directory = zlib.decompress(data[directory_start : directory_start + directory_size])
        file_offset = directory_start + directory_size
        files: dict[str, bytes] = {}

        for index in range(file_count):
            header = directory[index * MPK_HEADER_SIZE : (index + 1) * MPK_HEADER_SIZE]
            name = header[:256].split(b"\0", 1)[0].decode("latin1").lower()
            _timestamp, _unknown, _offset, _uncompressed_size, _directory_offset, compressed_size, _file_crc = (
                struct.unpack_from("<IIIIIII", header, 256)
            )
            compressed = data[file_offset : file_offset + compressed_size]
            file_offset += compressed_size
            files[name] = zlib.decompress(compressed)

        return files


class PcxImage:
    def __init__(self, data: bytes) -> None:
        self.width, self.height, self.rows = self._decode(data)

    @staticmethod
    def _decode(data: bytes) -> tuple[int, int, list[bytes]]:
        _manufacturer, _version, _encoding, bits_per_pixel = struct.unpack_from("<BBBB", data, 0)
        xmin, ymin, xmax, ymax = struct.unpack_from("<HHHH", data, 4)
        planes = data[65]
        bytes_per_line = struct.unpack_from("<H", data, 66)[0]

        if bits_per_pixel != 8 or planes != 1:
            raise ValueError("only 8-bit single-plane PCX maps are supported")

        width = xmax - xmin + 1
        height = ymax - ymin + 1
        end = len(data)

        if len(data) >= 769 and data[-769] == 12:
            end -= 769

        decoded = bytearray()
        cursor = 128
        expected = height * planes * bytes_per_line

        while cursor < end and len(decoded) < expected:
            byte = data[cursor]
            cursor += 1

            if byte >= 0xC0:
                run_length = byte & 0x3F
                if cursor >= end:
                    break
                value = data[cursor]
                cursor += 1
                decoded.extend([value] * run_length)
            else:
                decoded.append(byte)

        if len(decoded) < expected:
            raise ValueError("truncated PCX image data")

        rows: list[bytes] = []
        row_stride = planes * bytes_per_line

        for y in range(height):
            row_start = y * row_stride
            rows.append(bytes(decoded[row_start : row_start + width]))

        return width, height, rows

    def sample_nearest(self, x_pixel: float, y_pixel: float) -> int:
        px = round(max(0.0, min(self.width - 1, x_pixel)))
        py = round(max(0.0, min(self.height - 1, y_pixel)))
        return self.rows[py][px]

    def sample_bilinear(self, x_pixel: float, y_pixel: float) -> float:
        x = max(0.0, min(self.width - 1, x_pixel))
        y = max(0.0, min(self.height - 1, y_pixel))
        x0 = int(x)
        y0 = int(y)
        x1 = min(x0 + 1, self.width - 1)
        y1 = min(y0 + 1, self.height - 1)
        tx = x - x0
        ty = y - y0
        top = self.rows[y0][x0] * (1.0 - tx) + self.rows[y0][x1] * tx
        bottom = self.rows[y1][x0] * (1.0 - tx) + self.rows[y1][x1] * tx
        return top * (1.0 - ty) + bottom * ty


class ClientZoneHeightMap:
    def __init__(self, zone_path: Path, zone: ZoneDefinition) -> None:
        self.zone_path = zone_path
        self.zone = zone
        self.scale_factor = 8
        self.offset_factor = 32
        self.terrain: PcxImage | None = None
        self.offset: PcxImage | None = None
        self._loaded = False

    def sample(self, world_x: int, world_y: int) -> int | None:
        if not self._loaded:
            self._load()

        if self.terrain is None or self.offset is None:
            return None

        local_x = world_x - self.zone.world_x
        local_y = world_y - self.zone.world_y

        if local_x < 0 or local_y < 0 or local_x > self.zone.world_width or local_y > self.zone.world_height:
            return None

        # Classic DAoC outdoor zones are 8*8192 world units with 256 terrain pixels.
        # Treat PCX samples as 256 cells, not 0..255 vertices, or samples drift by
        # roughly half a tile near the zone center and visibly float/sink on slopes.
        x_pixel = local_x / max(1.0, self.zone.world_width / self.terrain.width)
        y_pixel = local_y / max(1.0, self.zone.world_height / self.terrain.height)
        terrain = self.terrain.sample_bilinear(x_pixel, y_pixel)
        offset = self.offset.sample_bilinear(x_pixel, y_pixel)
        return int(round(terrain * self.scale_factor + offset * self.offset_factor))

    def _load(self) -> None:
        zone_number = f"{self.zone.zone_id:03d}"
        archive = MpkArchive(self.zone_path / f"dat{zone_number}.mpk")
        files = archive.files()
        sector = files.get("sector.dat", b"").decode("latin1", "replace")
        scale = re.search(r"(?im)^scalefactor\s*=\s*(-?\d+)\s*$", sector)
        offset = re.search(r"(?im)^offsetfactor\s*=\s*(-?\d+)\s*$", sector)

        if scale:
            self.scale_factor = int(scale.group(1))
        if offset:
            self.offset_factor = int(offset.group(1))

        self.terrain = PcxImage(files["terrain.pcx"])
        self.offset = PcxImage(files["offset.pcx"])
        self._loaded = True


class ClientZoneHeightSampler:
    def __init__(
        self,
        zones_root: Path,
        zones: dict[int, ZoneDefinition],
        corrections: dict[int, list[tuple[int, int, int]]] | None = None,
        correction_max_distance: float = 0.0,
        correction_sample_count: int = 4,
    ) -> None:
        self.zones_root = zones_root
        self.zones = zones
        self._maps: dict[int, ClientZoneHeightMap] = {}
        self.corrections = corrections or {}
        self.correction_max_distance = correction_max_distance
        self.correction_sample_count = max(1, correction_sample_count)

    @classmethod
    def from_config(cls, config_path: Path) -> "ClientZoneHeightSampler":
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        zones_root = Path(payload["zones_root"])

        if not zones_root.is_absolute():
            zones_root = (config_path.parent / zones_root).resolve()

        zones: dict[int, ZoneDefinition] = {}
        for zone_key, zone_payload in payload.get("zones", {}).items():
            zone_id = int(zone_key)
            zones[zone_id] = ZoneDefinition(
                zone_id=zone_id,
                offset_x=int(zone_payload["offset_x"]),
                offset_y=int(zone_payload["offset_y"]),
                width=int(zone_payload.get("width", 8)),
                height=int(zone_payload.get("height", 8)),
            )

        corrections: dict[int, list[tuple[int, int, int]]] = {}

        for correction in payload.get("correction_points", []):
            if not all(key in correction for key in ("zone", "x", "y")):
                continue

            zone_id = int(correction["zone"])
            x = int(correction["x"])
            y = int(correction["y"])

            if "delta_z" in correction:
                delta_z = int(correction["delta_z"])
            elif "z" in correction:
                base_sampler = cls(zones_root, zones)
                sampled = base_sampler.sample(x, y, zone_id)
                if sampled is None:
                    continue
                delta_z = int(correction["z"]) - sampled
            else:
                continue

            corrections.setdefault(zone_id, []).append((x, y, delta_z))

        return cls(
            zones_root,
            zones,
            corrections=corrections,
            correction_max_distance=float(payload.get("correction_max_distance", 0.0)),
            correction_sample_count=int(payload.get("correction_sample_count", 4)),
        )

    def sample(self, world_x: int, world_y: int, zone_id: int) -> int | None:
        sampled = self._sample_zone(world_x, world_y, zone_id)

        if sampled is not None:
            return sampled

        for fallback_zone_id, zone in self.zones.items():
            if fallback_zone_id == zone_id:
                continue
            if (
                world_x < zone.world_x
                or world_y < zone.world_y
                or world_x > zone.world_x + zone.world_width
                or world_y > zone.world_y + zone.world_height
            ):
                continue
            sampled = self._sample_zone(world_x, world_y, fallback_zone_id)
            if sampled is not None:
                return sampled

        return None

    def _sample_zone(self, world_x: int, world_y: int, zone_id: int) -> int | None:
        zone = self.zones.get(zone_id)

        if zone is None:
            return None

        heightmap = self._maps.get(zone_id)

        if heightmap is None:
            zone_path = self._find_zone_path(zone_id)
            if zone_path is None:
                return None
            heightmap = ClientZoneHeightMap(zone_path, zone)
            self._maps[zone_id] = heightmap

        sampled = heightmap.sample(world_x, world_y)
        if sampled is None:
            return None

        correction = self._sample_correction(world_x, world_y, zone_id)
        return sampled if correction is None else int(round(sampled + correction))

    def _sample_correction(self, world_x: int, world_y: int, zone_id: int) -> float | None:
        points = self.corrections.get(zone_id, [])

        if not points:
            return None

        nearest_points = sorted(points, key=lambda point: (point[0] - world_x) ** 2 + (point[1] - world_y) ** 2)[
            : self.correction_sample_count
        ]
        nearest_distance = ((nearest_points[0][0] - world_x) ** 2 + (nearest_points[0][1] - world_y) ** 2) ** 0.5

        if self.correction_max_distance > 0 and nearest_distance > self.correction_max_distance:
            return None

        weighted_delta = 0.0
        total_weight = 0.0

        for point_x, point_y, delta_z in nearest_points:
            distance = max(1.0, ((point_x - world_x) ** 2 + (point_y - world_y) ** 2) ** 0.5)
            weight = 1.0 / (distance * distance)
            weighted_delta += delta_z * weight
            total_weight += weight

        return weighted_delta / total_weight if total_weight > 0 else None

    def _find_zone_path(self, zone_id: int) -> Path | None:
        names = [f"zone{zone_id:03d}", f"Zone{zone_id:03d}", f"ZONE{zone_id:03d}"]

        for name in names:
            candidate = self.zones_root / name
            if candidate.exists():
                return candidate

        return None
