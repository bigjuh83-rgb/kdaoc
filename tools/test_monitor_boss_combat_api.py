#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("monitor-boss-combat-api.py")
spec = importlib.util.spec_from_file_location("monitor_boss_combat_api", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class MonitorBossCombatApiTests(unittest.TestCase):
    def test_build_snapshot_url_derives_endpoint_from_npc_api_url(self) -> None:
        url = module.build_snapshot_url(
            "http://127.0.0.1:5000/api/dummy/combat/npcs",
            "",
            "KDAOC_TEST_hib_cuuldurach40",
            200,
            5000,
            80,
        )

        self.assertTrue(url.startswith("http://127.0.0.1:5000/api/dummy/combat/encounter-snapshot?"))
        self.assertIn("name=KDAOC_TEST_hib_cuuldurach40", url)
        self.assertIn("region=200", url)
        self.assertIn("radius=5000", url)
        self.assertIn("limit=80", url)

    def test_build_snapshot_url_allows_explicit_snapshot_api_url(self) -> None:
        url = module.build_snapshot_url(
            "http://127.0.0.1:5000/api/dummy/combat/npcs",
            "http://server.local/snapshot",
            "Boss",
            None,
            2500,
            20,
        )

        self.assertTrue(url.startswith("http://server.local/snapshot?"))
        self.assertNotIn("region=", url)


if __name__ == "__main__":
    unittest.main()
