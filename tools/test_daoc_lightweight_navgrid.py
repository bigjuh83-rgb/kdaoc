#!/usr/bin/env python3
"""Unit checks for client MPK lightweight nav grid pathing."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_navgrid_module():
    module_path = Path(__file__).with_name("daoc_lightweight_navgrid.py")
    spec = importlib.util.spec_from_file_location("daoc_lightweight_navgrid_for_tests", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


navgrid = load_navgrid_module()


class DaocLightweightNavGridTests(unittest.TestCase):
    def test_salisbury_real_client_grid_finds_nearby_route(self):
        config_path = Path(__file__).parent / "pathing" / "heightmaps" / "region001_client_zones.json"
        client_dat = Path(__file__).parents[2] / "OpenDAoCClient" / "zones" / "zone001" / "dat001.mpk"

        if not client_dat.exists():
            self.skipTest(f"client zone archive not found: {client_dat}")

        pathfinder = navgrid.ClientNavGridPathfinder(
            config_path,
            cell_size=256,
            max_step_z=240,
            fixture_padding=0,
            max_visited=5000,
        )

        route = pathfinder.find_path(1, 581632, 581632, 582400, 581632)

        self.assertTrue(route.ok, route.status)
        self.assertGreaterEqual(len(route.points), 2)
        self.assertTrue(all(point.z > 0 for point in route.points))

    def test_unknown_zone_fails_without_route(self):
        config_path = Path(__file__).parent / "pathing" / "heightmaps" / "region001_client_zones.json"
        pathfinder = navgrid.ClientNavGridPathfinder(config_path)

        route = pathfinder.find_path(999, 0, 0, 100, 100)

        self.assertFalse(route.ok)
        self.assertEqual(route.status, "StartOutsideZone")
        self.assertEqual(route.points, [])


if __name__ == "__main__":
    raise SystemExit(unittest.main())
