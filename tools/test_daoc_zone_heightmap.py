#!/usr/bin/env python3
"""Unit checks for DAoC client terrain height sampling."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_heightmap_module():
    module_path = Path(__file__).with_name("daoc_zone_heightmap.py")
    spec = importlib.util.spec_from_file_location("daoc_zone_heightmap_for_tests", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


heightmap = load_heightmap_module()


class DaocZoneHeightMapTests(unittest.TestCase):
    def test_region001_config_matches_known_camelot_hills_loc(self):
        config_path = Path(__file__).parent / "pathing" / "heightmaps" / "region001_client_zones.json"
        client_dat = Path(__file__).parents[2] / "OpenDAoCClient" / "zones" / "zone000" / "dat000.mpk"

        if not client_dat.exists():
            self.skipTest(f"client zone archive not found: {client_dat}")

        sampler = heightmap.ClientZoneHeightSampler.from_config(config_path)

        self.assertEqual(sampler.sample(552563, 513585, 0), 2896)

    def test_region001_config_falls_back_from_region_id_to_coordinate_zone(self):
        config_path = Path(__file__).parent / "pathing" / "heightmaps" / "region001_client_zones.json"
        client_dat = Path(__file__).parents[2] / "OpenDAoCClient" / "zones" / "zone000" / "dat000.mpk"

        if not client_dat.exists():
            self.skipTest(f"client zone archive not found: {client_dat}")

        sampler = heightmap.ClientZoneHeightSampler.from_config(config_path)

        self.assertEqual(sampler.sample(552563, 513585, 1), 2896)

    def test_unknown_zone_returns_none(self):
        sampler = heightmap.ClientZoneHeightSampler(Path("/missing"), {})

        self.assertIsNone(sampler.sample(1, 2, 999))

    def test_region001_config_matches_salisbury_cell_sampling(self):
        config_path = Path(__file__).parent / "pathing" / "heightmaps" / "region001_client_zones.json"
        client_dat = Path(__file__).parents[2] / "OpenDAoCClient" / "zones" / "zone001" / "dat001.mpk"

        if not client_dat.exists():
            self.skipTest(f"client zone archive not found: {client_dat}")

        sampler = heightmap.ClientZoneHeightSampler.from_config(config_path)

        self.assertEqual(sampler.sample(581632, 581632, 1), 2192)

    def test_region100_config_samples_midgard_start_from_region_id(self):
        config_path = Path(__file__).parent / "pathing" / "heightmaps" / "region100_client_zones.json"
        client_dat = Path(__file__).parents[2] / "OpenDAoCClient" / "zones" / "zone100" / "dat100.mpk"

        if not client_dat.exists():
            self.skipTest(f"client zone archive not found: {client_dat}")

        sampler = heightmap.ClientZoneHeightSampler.from_config(config_path)

        self.assertIsNotNone(sampler.sample(771748, 770026, 100))

    def test_region200_config_samples_hibernia_start_from_region_id(self):
        config_path = Path(__file__).parent / "pathing" / "heightmaps" / "region200_client_zones.json"
        client_dat = Path(__file__).parents[2] / "OpenDAoCClient" / "zones" / "zone200" / "dat200.mpk"

        if not client_dat.exists():
            self.skipTest(f"client zone archive not found: {client_dat}")

        sampler = heightmap.ClientZoneHeightSampler.from_config(config_path)

        self.assertIsNotNone(sampler.sample(335580, 536978, 200))

    def test_correction_point_can_adjust_local_visual_ground(self):
        zone = heightmap.ZoneDefinition(zone_id=1, offset_x=0, offset_y=0)

        class FakeMap:
            def sample(self, _x: int, _y: int) -> int:
                return 100

        sampler = heightmap.ClientZoneHeightSampler(
            Path("/missing"),
            {1: zone},
            corrections={1: [(100, 100, -12)]},
            correction_max_distance=300,
        )
        sampler._maps[1] = FakeMap()

        self.assertEqual(sampler.sample(100, 100, 1), 88)


if __name__ == "__main__":
    unittest.main()
