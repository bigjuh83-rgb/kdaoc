#!/usr/bin/env python3
"""Unit checks for the pre-service growth case supervisor."""

from __future__ import annotations

import importlib.util
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


def load_supervisor_module():
    module_path = Path(__file__).with_name("run-preservice-growth-case-supervisor.py")
    spec = importlib.util.spec_from_file_location("preservice_growth_case_supervisor_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


supervisor = load_supervisor_module()


class PreserviceGrowthCaseSupervisorTests(unittest.TestCase):
    def make_case(self, case_data_dir: Path):
        return supervisor.CaseRecord(
            case_id="solo-s150-r2-mid-r001",
            variant="solo-s150-r2",
            realm="mid",
            party_size=1,
            repeat_index=1,
            case_index=1,
            start=60081,
            segment_seconds=150,
            max_segments=99,
            max_level=50,
            reset_level=1,
            extra_args=[],
            run_dir=str(case_data_dir.parent),
            run_dir_arg=str(case_data_dir.parent),
            case_data_dir=str(case_data_dir),
            next_segment=20,
        )

    def test_live_fatal_detects_repeated_route_home_fast_travel_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            movement_dir = case_data_dir / "movement"
            movement_dir.mkdir(parents=True)
            movement_path = movement_dir / "segment-020-growthmid60081-1.jsonl"
            with movement_path.open("w", encoding="utf-8") as handle:
                for index in range(3):
                    handle.write(
                        json.dumps(
                            {
                                "t": float(index + 1),
                                "event": "route_home_fast_travel_reposition",
                                "moved": 0,
                                "reason": "player move api error: HTTP Error 500: Internal Server Error",
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )

            reason = supervisor.case_live_fatal_reason(
                SimpleNamespace(live_route_home_failed_fatal_count=3),
                self.make_case(case_data_dir),
            )

        self.assertIn("repeated route_home_fast_travel failed count=3", reason)
        self.assertIn("HTTP Error 500", reason)

    def test_live_fatal_ignores_successful_route_home_fast_travel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            movement_dir = case_data_dir / "movement"
            movement_dir.mkdir(parents=True)
            movement_path = movement_dir / "segment-020-growthmid60081-1.jsonl"
            with movement_path.open("w", encoding="utf-8") as handle:
                for index in range(3):
                    handle.write(
                        json.dumps(
                            {
                                "t": float(index + 1),
                                "event": "route_home_fast_travel_reposition",
                                "moved": 1,
                            },
                            sort_keys=True,
                        )
                        + "\n"
                    )

            reason = supervisor.case_live_fatal_reason(
                SimpleNamespace(live_route_home_failed_fatal_count=3),
                self.make_case(case_data_dir),
            )

        self.assertEqual(reason, "")

    def test_live_fatal_quarantines_solo_death_without_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            encounter_path = encounter_dir / "segment-020-growthmid60081-1.jsonl"
            rows = [
                {"t": 1.0, "event": "round_start", "behavior_state": "HuntObjective"},
                {"t": 10.0, "event": "combat_start", "behavior_state": "HuntObjective"},
                {"t": 20.0, "event": "death_detected", "behavior_state": "DeadReleaseRecover", "damage_done": 0},
                {"t": 70.0, "event": "encounter_tick", "behavior_state": "RestRecover", "damage_done": 0},
            ]
            encounter_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )

            reason = supervisor.case_live_fatal_reason(
                SimpleNamespace(
                    live_solo_death_no_progress_fatal_count=1,
                    live_solo_death_no_progress_fatal_seconds=55.0,
                    live_death_loop_fatal_count=3,
                ),
                self.make_case(case_data_dir),
            )

        self.assertIn("solo death without progress", reason)

    def test_live_fatal_records_runtime_failure_memory_before_quarantine(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            encounter_path = encounter_dir / "segment-020-growthalb60081-1.jsonl"
            rows = [
                {
                    "t": 10.0,
                    "event": "server_message",
                    "text": "GrowthAlb60081이 \uFFFD\uFFFD\uFFFD\uFFFD\uFFFD bandit에게 사망했습니다.",
                },
                {
                    "t": 11.0,
                    "event": "death_detected",
                    "behavior_state": "DeadReleaseRecover",
                    "rescue_target_name": "노련한 emerald snake",
                    "target_level": 7,
                },
            ]
            encounter_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
            case = self.make_case(case_data_dir)
            case.case_id = "party8-s240-alb-r001"
            case.realm = "alb"
            case.party_size = 8

            recorded = supervisor.record_live_fatal_runtime_failure_memory(
                case,
                "live fatal: repeated deaths count=12",
            )
            memory_path = case_data_dir / "runtime-failure-memory.csv"
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                memory_rows = list(csv.DictReader(handle))

        self.assertEqual(recorded, 2)
        self.assertEqual({row["target_name"] for row in memory_rows}, {"bandit", "emerald snake"})
        self.assertTrue(all(row["level"] == "0" for row in memory_rows))
        self.assertTrue(all(row["reason"] == "death_pressure" for row in memory_rows))
        self.assertTrue(all(row["expires_segment"] == "23" for row in memory_rows))

    def test_live_fatal_offtarget_damage_records_rescue_actor_before_objective(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            encounter_path = encounter_dir / "segment-020-growthhib70481-1.jsonl"
            rows = [
                {
                    "t": 10.0,
                    "event": "unengaged_pull_offtarget_damage",
                    "reason": "unengaged_pull_offtarget_damage",
                    "rescue_target_name": "feckless lucragan",
                    "rescue_target_level": 5,
                    "target_name": "mudman",
                    "target_level": 4,
                },
            ]
            encounter_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
            case = self.make_case(case_data_dir)
            case.case_id = "duo-s150-hib-r001"
            case.realm = "hib"
            case.party_size = 2

            recorded = supervisor.record_live_fatal_runtime_failure_memory(
                case,
                "live fatal: combat_pressure_no_kill",
            )
            memory_path = case_data_dir / "runtime-failure-memory.csv"
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                memory_rows = list(csv.DictReader(handle))

        self.assertEqual(recorded, 1)
        self.assertEqual([row["target_name"] for row in memory_rows], ["feckless lucragan"])
        self.assertEqual(memory_rows[0]["source"], "live_fatal_offtarget_damage")
        self.assertEqual(memory_rows[0]["reason"], "live_fatal")

    def test_live_fatal_does_not_record_party_members_as_avoid_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            case_data_dir.mkdir(parents=True)
            (case_data_dir / "primary-accounts.csv").write_text(
                "username,password,realm,char_index,class_id,class_name,specs,start_x,start_y,start_z,zone_id,growth_role\n"
                "growthalb60081,dummy-pass,1,0,1,Paladin,Slash|39,0,0,0,1,carry\n"
                "growthalb60082,dummy-pass,1,0,6,Cleric,Rejuvenation|40,0,0,0,1,tracked\n",
                encoding="utf-8",
            )
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            encounter_path = encounter_dir / "segment-020-growthalb60081-1.jsonl"
            rows = [
                {
                    "t": 10.0,
                    "event": "combat_finish",
                    "outcome": "critical_health_drop_aggro",
                    "active_target_name": "GrowthAlb60081",
                    "active_target_level": 7,
                },
                {
                    "t": 11.0,
                    "event": "death_detected",
                    "target_name": "GrowthAlb60082",
                    "target_level": 7,
                },
                {
                    "t": 12.0,
                    "event": "death_detected",
                    "rescue_target_name": "emerald snake",
                    "target_level": 7,
                },
            ]
            encounter_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
            case = self.make_case(case_data_dir)
            case.case_id = "party8-s240-alb-r001"
            case.realm = "alb"
            case.party_size = 8

            recorded = supervisor.record_live_fatal_runtime_failure_memory(
                case,
                "live fatal: repeated deaths count=12",
            )
            memory_path = case_data_dir / "runtime-failure-memory.csv"
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                memory_rows = list(csv.DictReader(handle))

        self.assertEqual(recorded, 1)
        self.assertEqual([row["target_name"] for row in memory_rows], ["emerald snake"])

    def test_live_fatal_ignores_other_case_death_messages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            case_data_dir.mkdir(parents=True)
            (case_data_dir / "primary-accounts.csv").write_text(
                "username,password,realm,char_index,class_id,class_name,specs,start_x,start_y,start_z,zone_id,growth_role\n"
                "growthhib70481,dummy-pass,3,20,44,Hero,Blades|50,0,0,0,200,carry\n"
                "growthhib70482,dummy-pass,3,20,47,Druid,Regrowth|40,0,0,0,200,tracked\n",
                encoding="utf-8",
            )
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            encounter_path = encounter_dir / "segment-020-growthhib70481-1.jsonl"
            rows = [
                {
                    "t": 10.0,
                    "event": "server_message",
                    "text": "GrowthHib70241이 a 노련한 eirebug에게 사망했습니다.",
                },
                {
                    "t": 11.0,
                    "event": "server_message",
                    "text": "GrowthHib70481이 a 노련한 water beetle에게 사망했습니다.",
                },
            ]
            encounter_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
            case = self.make_case(case_data_dir)
            case.case_id = "duo-s150-hib-r001"
            case.realm = "hib"
            case.party_size = 2

            recorded = supervisor.record_live_fatal_runtime_failure_memory(
                case,
                "live fatal: repeated deaths count=12",
            )
            memory_path = case_data_dir / "runtime-failure-memory.csv"
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                memory_rows = list(csv.DictReader(handle))

        self.assertEqual(recorded, 1)
        self.assertEqual([row["target_name"] for row in memory_rows], ["water beetle"])

    def test_live_fatal_scan_empty_records_target_plan_downgrade_memory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            case.realm = "hib"
            case.party_size = 2

            recorded = supervisor.record_live_fatal_runtime_failure_memory(
                case,
                "live fatal: repeated target scan empty eligible=0 count=3 reason=level",
            )
            memory_path = case_data_dir / "runtime-failure-memory.csv"
            with memory_path.open("r", encoding="utf-8", newline="") as handle:
                memory_rows = list(csv.DictReader(handle))

        self.assertEqual(recorded, 1)
        self.assertEqual(memory_rows[0]["action"], "downgrade_target_plan")
        self.assertEqual(memory_rows[0]["reason"], "scan_empty")
        self.assertEqual(memory_rows[0]["level"], "0")
        self.assertEqual(memory_rows[0]["expires_segment"], "23")

    def test_live_fatal_quarantines_solo_gear_economy_bottleneck(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            case_data_dir.mkdir(parents=True)
            (case_data_dir.parent / "summary.md").write_text(
                "- Planned merchant buy shortage copper: `324`\n",
                encoding="utf-8",
            )
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            encounter_path = encounter_dir / "segment-020-growthmid60081-1.jsonl"
            rows = [
                {"t": 1.0, "event": "round_start", "behavior_state": "HuntObjective"},
                {"t": 10.0, "event": "combat_start", "behavior_state": "HuntObjective", "damage_done": 0},
                {
                    "t": 41.0,
                    "event": "combat_finish",
                    "behavior_state": "HuntObjective",
                    "outcome": "critical_health_drop_aggro",
                    "damage_done": 56,
                    "active_target_remaining_health_percent": 51.72,
                },
                {"t": 45.0, "event": "encounter_tick", "behavior_state": "HuntObjective", "damage_done": 56},
            ]
            encounter_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )

            reason = supervisor.case_live_fatal_reason(
                SimpleNamespace(
                    live_solo_gear_bottleneck_fatal_count=1,
                    live_solo_gear_bottleneck_fatal_seconds=30.0,
                    live_death_loop_fatal_count=3,
                ),
                self.make_case(case_data_dir),
            )

        self.assertIn("solo gear/economy bottleneck", reason)
        self.assertIn("buy_shortage_copper=324", reason)

    def test_live_fatal_does_not_quarantine_solo_gear_bottleneck_while_recovering(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            case_data_dir.mkdir(parents=True)
            (case_data_dir.parent / "summary.md").write_text(
                "- Planned merchant buy shortage copper: `324`\n",
                encoding="utf-8",
            )
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            encounter_path = encounter_dir / "segment-020-growthmid60081-1.jsonl"
            rows = [
                {"t": 1.0, "event": "round_start", "behavior_state": "HuntObjective"},
                {"t": 10.0, "event": "combat_start", "behavior_state": "HuntObjective", "damage_done": 0},
                {
                    "t": 41.0,
                    "event": "combat_finish",
                    "behavior_state": "HuntObjective",
                    "outcome": "critical_health_drop_aggro",
                    "damage_done": 56,
                    "active_target_remaining_health_percent": 51.72,
                },
                {"t": 45.0, "event": "encounter_tick", "behavior_state": "RestRecover", "damage_done": 56},
            ]
            encounter_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )

            reason = supervisor.case_live_fatal_reason(
                SimpleNamespace(
                    live_solo_gear_bottleneck_fatal_count=1,
                    live_solo_gear_bottleneck_fatal_seconds=30.0,
                    live_death_loop_fatal_count=3,
                ),
                self.make_case(case_data_dir),
            )

        self.assertEqual(reason, "")

    def test_live_fatal_quarantines_solo_target_removed_without_combat_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            encounter_path = encounter_dir / "segment-020-growthmid60081-1.jsonl"
            rows = [{"t": float(index + 1), "event": "target_object_removed"} for index in range(12)]
            encounter_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )

            reason = supervisor.case_live_fatal_reason(
                SimpleNamespace(live_target_removed_no_combat_fatal_count=12),
                self.make_case(case_data_dir),
            )

        self.assertIn("target_object_removed without combat", reason)

    def test_live_fatal_does_not_quarantine_party_target_removed_observer_noise(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            encounter_path = encounter_dir / "segment-020-growthmid60081-1.jsonl"
            rows = [{"t": float(index + 1), "event": "target_object_removed"} for index in range(20)]
            encounter_path.write_text(
                "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                encoding="utf-8",
            )
            case = self.make_case(case_data_dir)
            case.party_size = 8

            reason = supervisor.case_live_fatal_reason(
                SimpleNamespace(live_target_removed_no_combat_fatal_count=12),
                case,
            )

        self.assertEqual(reason, "")

    def test_worker_startup_no_output_quarantines_silent_worker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            case.stdout_log = str(temp_path / "attempt.stdout.log")
            case.stderr_log = str(temp_path / "attempt.stderr.log")
            Path(case.stdout_log).write_text("", encoding="utf-8")
            Path(case.stderr_log).write_text("", encoding="utf-8")
            args = SimpleNamespace(worker_startup_no_output_fatal_seconds=45.0)

            early = supervisor.worker_startup_no_output_fatal_reason(args, case, 44.0)
            late = supervisor.worker_startup_no_output_fatal_reason(args, case, 45.1)

        self.assertEqual(early, "")
        self.assertIn("worker startup produced no output/artifacts", late)

    def test_worker_startup_no_output_allows_started_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            case.stdout_log = str(temp_path / "attempt.stdout.log")
            case.stderr_log = str(temp_path / "attempt.stderr.log")
            Path(case.stdout_log).write_text("", encoding="utf-8")
            Path(case.stderr_log).write_text("", encoding="utf-8")
            (encounter_dir / "segment-020-growthmid60081-1.jsonl").write_text(
                json.dumps({"event": "round_start"}) + "\n",
                encoding="utf-8",
            )

            reason = supervisor.worker_startup_no_output_fatal_reason(
                SimpleNamespace(worker_startup_no_output_fatal_seconds=45.0),
                case,
                80.0,
            )

        self.assertEqual(reason, "")

    def test_bottleneck_retry_records_ledger_and_intervention(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            case.status = "quarantined"
            case.attempt = 1
            case.max_observed_level = 9
            args = SimpleNamespace(
                base_run_dir_path=temp_path / "run",
                max_concurrent_cases=1,
                max_concurrent_per_realm=0,
                continue_after_bottleneck=True,
                bottleneck_auto_resume_attempts=3,
            )
            manager = supervisor.CaseSupervisor(args, [case], stale_process_cleaner=lambda *_args, **_kwargs: [])

            retried = manager.queue_bottleneck_retry("case_completed_stall", case, "no xp progress")
            manager.record_bottleneck("case_completed_stall", case, "no xp progress")

            ledger_rows = supervisor.read_csv_rows(manager.bottleneck_ledger_path)
            intervention_lines = manager.interventions_path.read_text(encoding="utf-8").splitlines()

        self.assertTrue(retried)
        self.assertEqual(case.status, "queued")
        self.assertEqual(ledger_rows[0]["status_after"], "queued")
        self.assertEqual(ledger_rows[0]["reason"], "no xp progress")
        self.assertIn("bottleneck_retry_queued", intervention_lines[0])

    def test_completed_stall_does_not_ignore_recovery_after_deaths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            encounter_dir = case_data_dir / "encounters"
            encounter_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            timeline_path = case_data_dir.parent / "timeline.csv"
            timeline_path.write_text(
                "\n".join(
                    [
                        "segment,xp_effective_delta,text_xp_delta,xp_delta,level_delta,target_removed,death_delta,loot_acquired,money_delta_copper,inventory_rows_delta,inventory_items_delta,weapon_items_delta,armor_items_delta,equipment_other_items_delta,junk_items_delta",
                        "19,0,0,0,0,0,1,0,0,0,0,0,0,0,0",
                        "20,0,0,0,0,0,1,0,0,0,0,0,0,0,0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            (encounter_dir / "segment-020-growthmid60081-1.jsonl").write_text(
                json.dumps({"event": "encounter_tick", "behavior_state": "RestRecover"}) + "\n",
                encoding="utf-8",
            )

            reason = supervisor.completed_segment_stall_reason(
                SimpleNamespace(completed_stall_fatal_segments=2),
                case,
            )

        self.assertIn("completed stall: no tracked xp/level/target_removed across 2 segments 19-20", reason)
        self.assertIn("deaths=2", reason)

    def test_completed_stall_uses_tracked_growth_not_carry_xp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            case.party_size = 2
            (case_data_dir / "primary-accounts.csv").write_text(
                "username,password,realm,char_index,class_id,class_name,specs,start_x,start_y,start_z,zone_id,growth_role\n"
                "growthalb70361,dummy-pass,1,0,1,Paladin,Slash|39,0,0,0,1,carry\n"
                "growthalb70362,dummy-pass,1,0,6,Cleric,Rejuvenation|40,0,0,0,1,tracked\n",
                encoding="utf-8",
            )
            timeline_path = case_data_dir.parent / "timeline.csv"
            timeline_path.write_text(
                "\n".join(
                    [
                        "segment,account,growth_role,xp_effective_delta,text_xp_delta,xp_delta,level_delta,target_removed,target_removed_no_reward,bottleneck_reason,death_delta,loot_acquired,money_delta_copper,inventory_rows_delta,inventory_items_delta,weapon_items_delta,armor_items_delta,equipment_other_items_delta,junk_items_delta,startup_merchant_sell,startup_merchant_buy,startup_merchant_equip",
                        "20,growthalb70361,carry,1000,1000,1000,0,1,0,,0,0,0,0,0,0,0,0,0,0,0,0",
                        "20,growthalb70362,tracked,0,0,0,0,0,0,,0,0,0,0,0,0,0,0,0,0,0,0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            reason = supervisor.completed_segment_stall_reason(
                SimpleNamespace(completed_stall_fatal_segments=1),
                case,
            )

        self.assertIn("no tracked xp/level", reason)
        self.assertIn("target_removed=1", reason)

    def test_completed_stall_does_not_treat_loot_as_progress_for_no_reward_kills(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            timeline_path = case_data_dir.parent / "timeline.csv"
            timeline_path.write_text(
                "\n".join(
                    [
                        "segment,account,growth_role,xp_effective_delta,text_xp_delta,xp_delta,level_delta,target_removed,target_removed_no_reward,bottleneck_reason,death_delta,loot_acquired,money_delta_copper,inventory_rows_delta,inventory_items_delta,weapon_items_delta,armor_items_delta,equipment_other_items_delta,junk_items_delta,startup_merchant_sell,startup_merchant_buy,startup_merchant_equip",
                        "20,growthmid60081,tracked,0,0,0,0,2,2,target_removed_no_xp,0,1,12,1,1,0,0,0,1,0,0,0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            reason = supervisor.completed_segment_stall_reason(
                SimpleNamespace(completed_stall_fatal_segments=1),
                case,
            )

        self.assertIn("no tracked xp/level", reason)
        self.assertIn("target_removed_no_reward=2", reason)
        self.assertIn("target_removed_no_xp=1", reason)

    def test_completed_stall_allows_actual_merchant_action_without_xp(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            timeline_path = case_data_dir.parent / "timeline.csv"
            timeline_path.write_text(
                "\n".join(
                    [
                        "segment,account,growth_role,xp_effective_delta,text_xp_delta,xp_delta,level_delta,target_removed,target_removed_no_reward,bottleneck_reason,death_delta,loot_acquired,money_delta_copper,inventory_rows_delta,inventory_items_delta,weapon_items_delta,armor_items_delta,equipment_other_items_delta,junk_items_delta,startup_merchant_sell,startup_merchant_buy,startup_merchant_equip",
                        "20,growthmid60081,tracked,0,0,0,0,0,0,,0,0,25,1,1,0,0,0,1,1,0,0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            reason = supervisor.completed_segment_stall_reason(
                SimpleNamespace(completed_stall_fatal_segments=1),
                case,
            )

        self.assertEqual(reason, "")

    def test_party_member_stuck_ignores_group_progress_for_zero_xp_member(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            case_data_dir = Path(temp_dir) / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            case.party_size = 4
            case.zero_xp_members = 1
            case.min_observed_level = 1
            case.max_observed_level = 4
            case.lowest_members = "growthmid60084:L1 XP0"
            timeline_path = case_data_dir.parent / "timeline.csv"
            timeline_path.write_text(
                "\n".join(
                    [
                        "segment,account,level_after,xp_after,xp_effective_delta,text_xp_delta,xp_delta,level_delta,target_removed",
                        "19,growthmid60081,4,1000,500,500,500,0,1",
                        "19,growthmid60084,1,0,0,0,0,0,0",
                        "20,growthmid60081,4,1500,500,500,500,0,1",
                        "20,growthmid60084,1,0,0,0,0,0,0",
                        "",
                    ]
                ),
                encoding="utf-8",
            )

            reason = supervisor.completed_party_member_stuck_reason(
                SimpleNamespace(party_member_stuck_fatal_segments=2),
                case,
            )

        self.assertIn("party member stuck", reason)
        self.assertIn("zero_xp_members=1", reason)

    def test_bottleneck_retry_limit_is_per_segment_not_total_case_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            case.status = "quarantined"
            case.attempt = 18
            case.next_segment = 8
            args = SimpleNamespace(
                base_run_dir_path=temp_path / "run",
                max_concurrent_cases=1,
                max_concurrent_per_realm=0,
                continue_after_bottleneck=True,
                bottleneck_auto_resume_attempts=3,
            )
            manager = supervisor.CaseSupervisor(args, [case], stale_process_cleaner=lambda *_args, **_kwargs: [])
            manager.prepare()
            manager.record_event("case_started", case_id=case.case_id, segment=8, attempt=17)
            manager.record_event("case_started", case_id=case.case_id, segment=8, attempt=18)

            retried = manager.queue_bottleneck_retry("case_live_fatal", case, "gear bottleneck")

        self.assertTrue(retried)
        self.assertEqual(case.status, "queued")

    def test_command_can_raise_bottleneck_auto_resume_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            args = SimpleNamespace(
                base_run_dir_path=temp_path / "run",
                max_concurrent_cases=1,
                max_concurrent_per_realm=0,
                bottleneck_auto_resume_attempts=0,
            )
            manager = supervisor.CaseSupervisor(args, [case], stale_process_cleaner=lambda *_args, **_kwargs: [])
            manager.prepare()

            manager.handle_command({"command": "set_bottleneck_auto_resume_attempts", "value": 4})

            events = [
                json.loads(line)
                for line in manager.events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(args.bottleneck_auto_resume_attempts, 4)
        self.assertEqual(events[-1]["event"], "bottleneck_auto_resume_attempts_changed")
        self.assertEqual(events[-1]["bottleneck_auto_resume_attempts"], 4)

    def test_worker_command_preserves_party_carry_level_offset(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            case.party_size = 8
            args = SimpleNamespace(
                base_run_dir_path=temp_path / "run",
                max_concurrent_cases=1,
                max_concurrent_per_realm=0,
                fake_worker=False,
                wsl_exe="wsl",
                wsl_work_dir="/repo",
                python_exe="python3",
                mysql_bin="mysql",
                growth_fast_travel="route-home",
                growth_hunting_index="index.csv",
                host_address="127.0.0.1",
                nav_api_url="http://127.0.0.1:5000",
                api_port=5000,
                case_start_stride=40,
                growth_party_carry_level_offset=12,
                skip_provision=False,
                reset_progress=True,
                dry_run=False,
                worker_extra_args=[],
            )
            manager = supervisor.CaseSupervisor(args, [case], stale_process_cleaner=lambda *_args, **_kwargs: [])

            command = manager.worker_command(case)

        self.assertEqual(command[command.index("--growth-party-carry-level-offset") + 1], "12")
        self.assertEqual(command[command.index("--growth-party-carry-count") + 1], "-1")

    def test_reattach_running_worker_rejects_reused_non_worker_pid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            case.status = "running"
            case.pid = 12345
            args = SimpleNamespace(
                base_run_dir_path=temp_path / "run",
                max_concurrent_cases=1,
                max_concurrent_per_realm=0,
            )
            manager = supervisor.CaseSupervisor(args, [case], stale_process_cleaner=lambda *_args, **_kwargs: [])
            original_process_exists = supervisor.process_exists
            original_process_command_line = supervisor.process_command_line
            supervisor.process_exists = lambda pid: pid == 12345
            supervisor.process_command_line = lambda pid: "python tools/run-preservice-growth-case-supervisor.py"
            try:
                manager.reattach_running_workers()
            finally:
                supervisor.process_exists = original_process_exists
                supervisor.process_command_line = original_process_command_line

        self.assertEqual(case.status, "queued")
        self.assertEqual(case.pid, 0)
        self.assertEqual(manager.processes, {})
        self.assertIn("pid was reused", case.last_error)

    def test_worker_command_enables_route_home_preflight_for_hunting_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            case_data_dir = temp_path / "case" / "case"
            case_data_dir.mkdir(parents=True)
            case = self.make_case(case_data_dir)
            args = SimpleNamespace(
                base_run_dir_path=temp_path / "run",
                max_concurrent_cases=1,
                max_concurrent_per_realm=0,
                fake_worker=False,
                wsl_exe="wsl",
                wsl_work_dir="/repo",
                python_exe="python3",
                mysql_bin="mysql",
                growth_fast_travel="route-home",
                growth_hunting_index="index.csv",
                host_address="127.0.0.1",
                nav_api_url="http://127.0.0.1:5000",
                api_port=5000,
                case_start_stride=40,
                growth_party_carry_level_offset=12,
                skip_provision=False,
                reset_progress=True,
                dry_run=False,
                worker_extra_args=[],
            )
            manager = supervisor.CaseSupervisor(args, [case], stale_process_cleaner=lambda *_args, **_kwargs: [])

            command = manager.worker_command(case)

        self.assertIn("--growth-route-preflight", command)
        self.assertIn("--growth-route-preflight-anchor", command)

    def test_growth_fast_travel_teleport_alias_normalizes_to_route_home(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            args = supervisor.parse_args(
                [
                    "--base-run-dir",
                    temp_dir,
                    "--growth-fast-travel",
                    "teleport",
                    "--dry-run",
                ]
            )

        self.assertEqual(args.growth_fast_travel, "route-home")


if __name__ == "__main__":
    unittest.main()
