#!/usr/bin/env python3
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import daoc_zone_heightmap as dzh

Z = 8192
cfg = json.loads((ROOT / "tools/pathing/heightmaps/region001_client_zones.json").read_text())
x, y = 561900, 357450
print(f"point ({x},{y})")
for zid, p in cfg["zones"].items():
    wx, wy = p["offset_x"] * Z, p["offset_y"] * Z
    ww, wh = p.get("width", 8) * Z, p.get("height", 8) * Z
    inside = wx <= x <= wx + ww and wy <= y <= wy + wh
    print(f"  zone {zid} {p['name']}: inside={inside}")

sampler = dzh.ClientZoneHeightSampler.from_config(ROOT / "tools/pathing/heightmaps/region001_client_zones.json")
for dx, dy, label in [(0, 0, "spawn"), (300, 150, "east"), (-200, 500, "nw"), (0, 800, "north"), (500, 500, "ne"), (-500, -500, "sw")]:
    px, py = x + dx, y + dy
    z = sampler.sample(px, py, 1)
    print(f"  {label} ({px},{py}) z={z}")

none_count = 0
for dx in range(-1000, 1001, 200):
    for dy in range(-1000, 1001, 200):
        if sampler.sample(x + dx, y + dy, 1) is None:
            none_count += 1
print(f"  null samples in 200-step grid +/-1000: {none_count}")
