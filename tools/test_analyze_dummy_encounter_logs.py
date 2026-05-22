#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("analyze-dummy-encounter-logs.py")
spec = importlib.util.spec_from_file_location("analyze_dummy_encounter_logs", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class AnalyzeDummyEncounterLogsTests(unittest.TestCase):
    def test_summarizes_attack_visibility_messages_and_health(self) -> None:
        events = [
            {
                "event": "combat_start",
                "username": "dummy040",
                "role": "melee-basic",
                "target_visible": True,
                "target_name": "Lord Elidyn",
                "target_distance": 300,
            },
            {
                "event": "attack_decision",
                "username": "dummy040",
                "role": "melee-basic",
                "attack_enabled": True,
                "reason": "combat_tick_visible_target",
                "target_visible": True,
            },
            {
                "event": "server_message",
                "username": "dummy040",
                "role": "melee-basic",
                "categories": ["out_of_range", "damage_done"],
                "target_visible": False,
            },
            {
                "event": "boss_api_sample",
                "name": "Lord Elidyn",
                "target_name": "Lord Elidyn",
                "healthPercent": 42,
                "health": 420,
                "maxHealth": 1000,
                "isAlive": True,
            },
        ]

        summary = module.analyze(events)

        self.assertEqual(summary["event_counts"]["combat_start"], 1)
        self.assertEqual(summary["attack"]["enabled_counts"]["on"], 1)
        self.assertEqual(summary["attack"]["reasons"]["combat_tick_visible_target"], 1)
        self.assertEqual(summary["target_visibility"]["visible"], 2)
        self.assertEqual(summary["target_visibility"]["not_visible"], 2)
        self.assertEqual(summary["server_message_categories"]["out_of_range"], 1)
        self.assertEqual(summary["last_target_health"]["Lord Elidyn"]["health_percent"], 42)
        self.assertEqual(summary["min_target_health"]["Lord Elidyn"]["health_percent"], 42)

    def test_reads_jsonl_and_ignores_empty_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "encounter.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"event": "round_start", "username": "dummy040"}),
                        "",
                        json.dumps({"event": "death_detected", "username": "dummy040"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            events = module.read_events([path])
            summary = module.analyze(events)

        self.assertEqual(len(events), 2)
        self.assertEqual(summary["users"]["dummy040"]["deaths"], 1)

    def test_replays_server_snapshot_to_classify_boss_focus_death(self) -> None:
        events = [
            {
                "event": "boss_api_sample",
                "elapsed": 10.0,
                "target_name": "KDAOC_TEST_boss",
                "healthPercent": 80.0,
                "snapshot": {
                    "target": {"target": "Caster001", "healthPercent": 80.0},
                    "players": [
                        {
                            "name": "Caster001",
                            "healthPercent": 20.0,
                            "distance": 145.0,
                            "isDead": False,
                            "targetName": "KDAOC_TEST_boss",
                        }
                    ],
                    "npcs": [],
                },
            },
            {
                "event": "death_detected",
                "elapsed": 10.2,
                "username": "caster001",
                "character": "Caster001",
                "role": "caster-basic",
                "active_tank_name": "Tank001",
                "active_tank_health_percent": 97,
            },
        ]

        summary = module.analyze(events)

        self.assertEqual(summary["death_diagnosis"][0]["cause"], "boss_focus")
        self.assertEqual(summary["death_diagnosis"][0]["boss_target"], "Caster001")
        self.assertEqual(summary["death_causes"]["boss_focus"], 1)

    def test_replays_server_snapshot_to_classify_add_focus_death(self) -> None:
        events = [
            {
                "event": "boss_api_sample",
                "elapsed": 20.0,
                "target_name": "KDAOC_TEST_boss",
                "healthPercent": 90.0,
                "snapshot": {
                    "target": {"target": "Tank001", "healthPercent": 90.0},
                    "players": [
                        {"name": "Healer001", "healthPercent": 12.0, "distance": 900.0, "isDead": False}
                    ],
                    "npcs": [
                        {
                            "name": "glimmer deathwatcher",
                            "targetName": "Healer001",
                            "distance": 250.0,
                            "healthPercent": 100.0,
                            "hasAggro": True,
                        }
                    ],
                },
            },
            {
                "event": "death_detected",
                "elapsed": 20.1,
                "username": "healer001",
                "character": "Healer001",
                "role": "healer-support",
            },
        ]

        summary = module.analyze(events)

        self.assertEqual(summary["death_diagnosis"][0]["cause"], "add_focus")
        self.assertEqual(summary["death_diagnosis"][0]["attackers"][0]["name"], "glimmer deathwatcher")
        self.assertEqual(summary["death_causes"]["add_focus"], 1)


if __name__ == "__main__":
    unittest.main()
