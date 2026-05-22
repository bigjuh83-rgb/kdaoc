#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import shutil
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("summarize-dummy-boss-report.py")
TEST_ROOT = Path(__file__).resolve().parents[1] / "tools" / "test-output" / "summarize-dummy-boss-report"
spec = importlib.util.spec_from_file_location("summarize_dummy_boss_report", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SummarizeDummyBossReportTests(unittest.TestCase):
    def fresh_root(self, name: str) -> Path:
        root = TEST_ROOT / name
        shutil.rmtree(root, ignore_errors=True)
        root.mkdir(parents=True)
        self.addCleanup(lambda: shutil.rmtree(root, ignore_errors=True))
        return root

    def test_deaths_use_death_detected_when_combat_deaths_are_under_counted(self) -> None:
        rows = [
            {
                "ok": "true",
                "player_deaths": "1",
                "death_detected": "38",
                "target_timeouts": "0",
                "target_removed": "0",
                "loot_acquired": "0",
            }
        ]

        summary = module.summarize_rows(rows)

        self.assertEqual(summary["workers_ok"], 1)
        self.assertEqual(summary["workers_total"], 1)
        self.assertEqual(summary["deaths"], 38)

    def test_deaths_fall_back_to_player_deaths_for_old_metrics(self) -> None:
        rows = [
            {
                "ok": "true",
                "player_deaths": "2",
                "target_timeouts": "1",
                "target_removed": "1",
                "loot_acquired": "3",
                "loot_tier_legendary": "1",
            }
        ]

        summary = module.summarize_rows(rows)

        self.assertEqual(summary["deaths"], 2)
        self.assertEqual(summary["timeouts"], 1)
        self.assertEqual(summary["target_removed"], 1)
        self.assertEqual(summary["loot"], 3)
        self.assertEqual(summary["tiers"]["legendary"], 1)

    def test_reads_realm_case_metrics_directories(self) -> None:
        root = self.fresh_root("realm-case-metrics")
        case = root / "alb_golestandt40"
        case.mkdir()
        (case / "metrics.csv").write_text(
            "username,ok,player_deaths,death_detected,target_timeouts,target_removed,loot_acquired,damage_done,healing_done,combat_not_visible_msg\n"
            "albtest001,true,0,1,0,0,0,123,40,2\n",
            encoding="utf-8",
        )

        rows = module.read_metrics_rows(root)
        summary = module.summarize_rows(rows)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["username"], "albtest001")
        self.assertEqual(rows[0]["__case"], "alb_golestandt40")
        self.assertEqual(summary["damage_done"], 123)
        self.assertEqual(summary["cases"]["alb_golestandt40"]["healing_done"], 40)

    def test_reads_required_target_liveness_from_boss_api(self) -> None:
        root = self.fresh_root("required-target-live")
        case = root / "hib_cuuldurach40"
        case.mkdir()
        (case / "metrics.csv").write_text(
            "username,ok,player_deaths,death_detected,target_timeouts,target_removed,loot_acquired,damage_done,healing_done,combat_not_visible_msg\n"
            "hibtest001,true,0,0,0,0,0,100,20,0\n",
            encoding="utf-8",
        )
        (case / "boss-api.jsonl").write_text(
            '{"found": true, "name": "KDAOC_TEST_hib_cuuldurach40", "health": 1229, "maxHealth": 4882, "healthPercent": 25.17, "isAlive": true}\n',
            encoding="utf-8",
        )

        rows = module.read_metrics_rows(root)
        summary = module.summarize_rows(rows)

        case_summary = summary["cases"]["hib_cuuldurach40"]
        self.assertEqual(summary["required_targets_alive"], 1)
        self.assertTrue(case_summary["required_target_alive"])
        self.assertEqual(case_summary["required_target_health"], 1229)
        self.assertAlmostEqual(case_summary["required_target_health_percent"], 25.17)

    def test_required_target_404_after_seen_counts_as_removed(self) -> None:
        root = self.fresh_root("required-target-404")
        case = root / "alb_golestandt40"
        case.mkdir()
        (case / "metrics.csv").write_text(
            "username,ok,player_deaths,death_detected,target_timeouts,target_removed,loot_acquired,damage_done,healing_done,combat_not_visible_msg\n"
            "albtest001,true,0,0,0,0,0,100,20,0\n",
            encoding="utf-8",
        )
        (case / "boss-api.jsonl").write_text(
            '{"found": true, "query_name": "KDAOC_TEST_alb_golestandt40", "name": "KDAOC_TEST_alb_golestandt40", "health": 74, "maxHealth": 4882, "healthPercent": 1.52, "isAlive": true}\n'
            '{"ok": false, "found": false, "query_name": "KDAOC_TEST_alb_golestandt40", "error": "HTTP Error 404: Not Found"}\n',
            encoding="utf-8",
        )

        rows = module.read_metrics_rows(root)
        summary = module.summarize_rows(rows)

        case_summary = summary["cases"]["alb_golestandt40"]
        self.assertEqual(summary["required_targets_alive"], 0)
        self.assertFalse(case_summary["required_target_alive"])
        self.assertEqual(case_summary["required_target_health"], 0)
        self.assertAlmostEqual(case_summary["required_target_health_percent"], 0.0)

    def test_summarizes_role_breakdowns_from_rotation_columns(self) -> None:
        rows = [
            {
                "__case": "hib_cuuldurach40",
                "ok": "true",
                "player_deaths": "0",
                "death_detected": "0",
                "rotation_melee-burst": "1",
                "attack_on": "0",
                "damage_done": "132",
                "damage_taken": "0",
                "healing_done": "0",
                "combat_not_visible_msg": "3",
                "party_follow_suppressed_combat": "12",
                "party_focus_pressure_backoff": "7",
                "party_survival_hold": "4",
                "party_assist_delay": "9",
                "validated_taunt_skill": "0",
                "smooth_move": "5",
            },
            {
                "__case": "hib_cuuldurach40",
                "ok": "true",
                "player_deaths": "0",
                "death_detected": "1",
                "rotation_healer-support": "1",
                "attack_on": "1",
                "damage_done": "0",
                "damage_taken": "1200",
                "healing_done": "900",
                "combat_not_visible_msg": "0",
                "party_follow_suppressed_combat": "0",
                "validated_spell": "8",
                "boss_ranged_backoff": "4",
            },
        ]

        summary = module.summarize_rows(rows)

        top_role = summary["roles"]["melee-burst"]
        case_role = summary["cases"]["hib_cuuldurach40"]["roles"]["melee-burst"]
        healer_role = summary["cases"]["hib_cuuldurach40"]["roles"]["healer-support"]
        self.assertEqual(top_role["workers_total"], 1)
        self.assertEqual(case_role["damage_done"], 132)
        self.assertEqual(case_role["attack_on"], 0)
        self.assertEqual(case_role["party_follow_suppressed_combat"], 12)
        self.assertEqual(case_role["party_focus_pressure_backoff"], 7)
        self.assertEqual(case_role["party_survival_hold"], 4)
        self.assertEqual(case_role["party_assist_delay"], 9)
        self.assertEqual(case_role["smooth_move"], 5)
        self.assertEqual(healer_role["deaths"], 1)
        self.assertEqual(healer_role["healing_done"], 900)
        self.assertEqual(healer_role["boss_ranged_backoff"], 4)

    def test_summarizes_prefixed_action_columns(self) -> None:
        rows = [
            {
                "__case": "alb_golestandt40",
                "ok": "true",
                "player_deaths": "0",
                "death_detected": "0",
                "target_removed": "1",
                "loot_acquired": "0",
                "damage_done": "50",
                "action_rotation_caster-basic": "1",
                "action_validated_spell": "6",
                "action_combat_not_visible_msg": "2",
                "action_boss_ranged_backoff": "3",
            }
        ]

        summary = module.summarize_rows(rows)
        role = summary["cases"]["alb_golestandt40"]["roles"]["caster-basic"]

        self.assertEqual(role["workers_total"], 1)
        self.assertEqual(role["validated_spell"], 6)
        self.assertEqual(role["not_visible"], 2)
        self.assertEqual(role["boss_ranged_backoff"], 3)

    def test_flags_add_overrun_when_boss_remains_untouched(self) -> None:
        rows = [
            {
                "__case": "mid_gjalpinulva40",
                "ok": "true",
                "player_deaths": "0",
                "death_detected": "1",
                "target_removed": "45",
                "loot_acquired": "0",
                "damage_done": "100",
                "__required_target_alive": "true",
                "__required_target_health": "4882",
                "__required_target_health_percent": "100.0",
            },
            {
                "__case": "mid_gjalpinulva40",
                "ok": "true",
                "player_deaths": "0",
                "death_detected": "0",
                "target_removed": "5",
                "loot_acquired": "0",
                "damage_done": "20",
            },
        ]

        summary = module.summarize_rows(rows)
        case_summary = summary["cases"]["mid_gjalpinulva40"]

        self.assertTrue(case_summary["add_overrun"])
        self.assertIn("boss_alive_high_health", case_summary["warnings"])

    def test_does_not_flag_add_overrun_after_boss_progress(self) -> None:
        rows = [
            {
                "__case": "alb_golestandt40",
                "ok": "true",
                "target_removed": "45",
                "loot_acquired": "0",
                "damage_done": "500",
                "__required_target_alive": "true",
                "__required_target_health": "1506",
                "__required_target_health_percent": "30.85",
            }
        ]

        summary = module.summarize_rows(rows)
        case_summary = summary["cases"]["alb_golestandt40"]

        self.assertFalse(case_summary["add_overrun"])
        self.assertEqual(case_summary["warnings"], [])

    def test_flags_low_health_boss_finish_failure(self) -> None:
        rows = [
            {
                "__case": "hib_cuuldurach40",
                "ok": "true",
                "target_removed": "0",
                "loot_acquired": "0",
                "damage_done": "2968",
                "__required_target_alive": "true",
                "__required_target_health": "468",
                "__required_target_health_percent": "9.59",
            }
        ]

        summary = module.summarize_rows(rows)
        case_summary = summary["cases"]["hib_cuuldurach40"]

        self.assertFalse(case_summary["add_overrun"])
        self.assertIn("boss_alive_low_health", case_summary["warnings"])


if __name__ == "__main__":
    unittest.main()
