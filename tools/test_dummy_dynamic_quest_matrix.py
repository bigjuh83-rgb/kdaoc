#!/usr/bin/env python3
"""Unit checks for the dynamic quest dummy matrix runner."""

from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


def load_module():
    module_path = Path(__file__).with_name("run-dummy-dynamic-quest-matrix.py")
    spec = importlib.util.spec_from_file_location("run_dummy_dynamic_quest_matrix_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


matrix = load_module()


class DummyDynamicQuestMatrixTests(unittest.TestCase):
    def test_realm_smoke_expands_all_starter_realms(self) -> None:
        args = matrix.parse_args(["--matrix", "realm-smoke", "--party-sizes", "1,2"])

        cases = matrix.build_cases(args)

        self.assertEqual(len(cases), 6)
        self.assertEqual({case.realm for case in cases}, {"Albion", "Midgard", "Hibernia"})
        self.assertIn("alb-p1", {case.name for case in cases})
        self.assertIn("mid-p2", {case.name for case in cases})
        self.assertIn("hib-p2", {case.name for case in cases})

    def test_realm_filter_limits_cases_by_key(self) -> None:
        args = matrix.parse_args(["--matrix", "realm-smoke", "--party-sizes", "2", "--realms", "mid"])

        cases = matrix.build_cases(args)

        self.assertEqual([case.name for case in cases], ["mid-p2"])

    def test_behavior_command_uses_real_interaction_dynamic_quest_flow(self) -> None:
        args = matrix.parse_args(["--matrix", "realm-smoke", "--party-sizes", "2", "--accounts-pattern", "accounts-{realm}-p{party_size}.csv"])
        case = next(case for case in matrix.build_cases(args) if case.key == "alb")

        command = matrix.build_behavior_command(case, args)
        rendered = " ".join(command)

        self.assertIn("--startup-service-interact", command)
        self.assertIn("--startup-service-accept-dialog", command)
        self.assertIn("--dynamic-quest-return-after-required-target", command)
        self.assertIn("--dynamic-quest-return-npc-name", command)
        self.assertIn("Brother Penric", command)
        self.assertIn("--dynamic-quest-return-home", command)
        self.assertIn("518850,494050,3352", command)
        self.assertIn("--require-target-name", command)
        self.assertIn("black wolf pup", command)
        self.assertIn("--party-role-strategy", command)
        self.assertIn("same", command)
        self.assertIn("--party-min-ready", command)
        self.assertEqual(command[command.index("--party-min-ready") + 1], "2")
        self.assertIn("--party-form-up-delay", command)
        self.assertIn("--party-form-up-timeout", command)
        self.assertEqual(command[command.index("--party-form-up-timeout") + 1], "0.0")
        self.assertIn("--hold", command)
        self.assertIn("260", command)
        self.assertIn("--safe-exit-max-seconds", command)
        self.assertIn("240", command)
        self.assertIn("--smooth-movement", command)
        self.assertIn("--movement-speed", command)
        self.assertIn("240.0", command)
        self.assertIn("--smooth-move-interval", command)
        self.assertIn("0.2", command)
        self.assertIn("--movement-update-interval", command)
        self.assertIn("--encounter-log-interval", command)
        self.assertIn("1.0", command)
        self.assertIn("--metrics-csv", command)
        self.assertIn("--report-md", command)
        self.assertIn("--encounter-log", command)
        self.assertNotIn("fakekill", rendered.lower())
        self.assertNotIn("/dynamicquest", rendered.lower())

    def test_behavior_command_forwards_case_realm_to_report(self) -> None:
        args = matrix.parse_args(["--matrix", "realm-smoke", "--party-sizes", "2"])
        case = next(case for case in matrix.build_cases(args) if case.key == "mid")

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--realm", command)
        self.assertEqual(command[command.index("--realm") + 1], "2")

    def test_behavior_command_forwards_party_slot_rotations(self) -> None:
        args = matrix.parse_args([
            "--matrix",
            "quick",
            "--party-sizes",
            "2",
            "--party-role-strategy",
            "mixed",
            "--party-slot-rotations",
            "melee-basic,melee-basic",
        ])
        case = matrix.build_cases(args)[0]

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--party-role-strategy", command)
        self.assertIn("mixed", command)
        self.assertIn("--party-slot-rotations", command)
        self.assertIn("melee-basic,melee-basic", command)

    def test_behavior_command_defaults_to_melee_rotation_for_quest_smoke(self) -> None:
        args = matrix.parse_args(["--matrix", "realm-smoke", "--party-sizes", "2"])
        case = next(case for case in matrix.build_cases(args) if case.key == "alb")

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--party-slot-rotations", command)
        self.assertEqual(command[command.index("--party-slot-rotations") + 1], "melee-basic,melee-basic")

    def test_behavior_command_enables_combat_recovery_for_e2e_smoke(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "1"])
        case = matrix.build_cases(args)[0]

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--use-skills", command)
        self.assertIn("--low-health-rest-percent", command)
        self.assertIn("75", command)
        self.assertIn("--low-health-rest-resume-percent", command)
        self.assertIn("95", command)
        self.assertIn("--reject-target-on-server-los-failure", command)
        self.assertIn("--server-los-failure-grace", command)
        self.assertEqual(command[command.index("--server-los-failure-grace") + 1], "10")
        self.assertIn("--target-loss-grace", command)
        self.assertEqual(command[command.index("--target-loss-grace") + 1], "1")
        self.assertIn("--melee-stick-attack", command)
        self.assertIn("--melee-range-buffer", command)
        self.assertEqual(command[command.index("--melee-range-buffer") + 1], "300")
        self.assertIn("--minimum-melee-stop-distance", command)
        self.assertEqual(command[command.index("--minimum-melee-stop-distance") + 1], "60")

    def test_autoaccept_command_observes_final_progress_without_npc_dialog(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--quest-start-mode", "autoaccept"])
        case = matrix.build_cases(args)[0]

        command = matrix.build_behavior_command(case, args)
        rendered = " ".join(command)

        self.assertIn("--dynamic-quest-observe-final-progress", command)
        self.assertNotIn("--startup-service-interact", command)
        self.assertNotIn("--startup-service-accept-dialog", command)
        self.assertNotIn("--dynamic-quest-return-after-required-target", command)
        self.assertNotIn("/dynamicquest", rendered.lower())

    def test_autoaccept_command_forwards_followup_branch_dialog_response_for_followup_target(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--quest-start-mode", "autoaccept"])
        case = matrix.build_cases(args)[0]
        case = matrix.replace(case, followup_target="흉포한 black wolf pup")

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--dynamic-quest-observe-final-progress", command)
        self.assertIn("--dynamic-quest-return-dialog-response", command)
        self.assertEqual(command[command.index("--dynamic-quest-return-dialog-response") + 1], "decline")
        self.assertNotIn("--dynamic-quest-return-after-required-target", command)

    def test_autoaccept_command_forwards_requested_branch_dialog_response(self) -> None:
        args = matrix.parse_args([
            "--matrix",
            "quick",
            "--quest-start-mode",
            "autoaccept",
            "--dynamic-quest-return-dialog-response",
            "decline",
            "--dynamic-quest-expected-final-node",
            "observe_signal",
        ])
        case = matrix.build_cases(args)[0]

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--dynamic-quest-return-dialog-response", command)
        self.assertEqual(command[command.index("--dynamic-quest-return-dialog-response") + 1], "decline")

    def test_npc_command_forwards_dynamic_quest_return_dialog_response(self) -> None:
        args = matrix.parse_args([
            "--matrix",
            "quick",
            "--dynamic-quest-return-dialog-response",
            "decline",
        ])
        case = matrix.build_cases(args)[0]

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--dynamic-quest-return-dialog-response", command)
        self.assertIn("decline", command)

    def test_npc_command_uses_followup_branch_dialog_response_for_followup_target(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])
        case = matrix.build_cases(args)[0]
        case = matrix.replace(case, followup_target="흉포한 black wolf pup")

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--dynamic-quest-return-dialog-response", command)
        self.assertEqual(command[command.index("--dynamic-quest-return-dialog-response") + 1], "decline")

    def test_extract_live_binding_keeps_observe_signal_position_as_followup_reference(self) -> None:
        case = matrix.build_cases(matrix.parse_args(["--matrix", "quick"]))[0]
        payload = {
            "quests": [
                {
                    "id": "quest-branch",
                    "startRegionId": case.region,
                    "startNpcName": "Captain Prahlion",
                    "startNpcInternalId": "npc-1",
                    "targetName": "slime lizard",
                    "tags": ["branch:mob-growth", "world-signal:mob-growth:killed:region:1"],
                    "nodes": [
                        {
                            "id": "observe_signal",
                            "objective": {"regionId": 1, "x": 467238, "y": 632158, "z": 1784},
                        },
                        {
                            "id": "explore",
                            "objective": {"regionId": 1, "x": 510381, "y": 492106, "z": 2811},
                        },
                    ],
                }
            ]
        }

        binding = matrix.extract_live_quest_binding(
            payload,
            case,
            "npc",
            required_tag="branch:mob-growth",
            required_world_signal="mob-growth:killed:region:1",
        )

        self.assertIsNotNone(binding)
        self.assertEqual(binding.followup_reference, matrix.StartPosition(1, 467238, 632158, 1784))

    def test_extract_autoaccept_live_binding_allows_realm_match_outside_starter_region(self) -> None:
        args = matrix.parse_args(["--matrix", "realm-smoke", "--realms", "mid"])
        case = matrix.build_cases(args)[0]
        payload = {
            "quests": [
                {
                    "id": "quest-auto-mid-frontier",
                    "realm": "Midgard",
                    "startRegionId": 151,
                    "startNpcName": "",
                    "targetName": "lost pysling",
                    "tags": [
                        "start-mode:AutoAccept",
                        "branch:mob-growth",
                        "world-signal:mob-growth:killed:region:151",
                    ],
                    "nodes": [
                        {
                            "id": "explore",
                            "objective": {"regionId": 151, "x": 295664, "y": 363104, "z": 4298},
                        }
                    ],
                    "startNodeId": "explore",
                }
            ]
        }

        binding = matrix.extract_live_quest_binding(
            payload,
            case,
            "autoaccept",
            required_tag="branch:mob-growth",
            required_world_signal="mob-growth:killed:region:151",
        )

        self.assertIsNotNone(binding)
        self.assertEqual(binding.start_position, matrix.StartPosition(151, 295664, 363104, 4298))

    def test_extract_mob_growth_followup_prefers_near_reference_target(self) -> None:
        payload = {
            "top": [
                {
                    "mobId": "far-high-score",
                    "name": "흉포한 black wolf pup",
                    "stage": "Champion",
                    "regionId": 1,
                    "isAlive": True,
                    "x": 510381,
                    "y": 492106,
                    "z": 2811,
                    "effectiveLevel": 4,
                    "growthScore": 5000,
                },
                {
                    "mobId": "near-lower-score",
                    "name": "흉포한 river spriteling",
                    "stage": "Champion",
                    "regionId": 1,
                    "isAlive": True,
                    "x": 472338,
                    "y": 619435,
                    "z": 1717,
                    "effectiveLevel": 6,
                    "growthScore": 4500,
                },
            ]
        }

        target = matrix.extract_live_mob_growth_target(
            payload,
            "mob-growth:killed:region:1",
            max_preferred_level=10,
            reference_position=(467238, 632158, 1784),
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.mob_id, "near-lower-score")

    def test_extract_mob_growth_followup_prefers_level_allowed_target_over_near_high_target(self) -> None:
        payload = {
            "top": [
                {
                    "mobId": "near-too-high",
                    "name": "흉포한 river spriteling",
                    "stage": "Champion",
                    "regionId": 1,
                    "isAlive": True,
                    "x": 472338,
                    "y": 619435,
                    "z": 1717,
                    "effectiveLevel": 6,
                    "growthScore": 4500,
                },
                {
                    "mobId": "allowed-level",
                    "name": "흉포한 creeping crud",
                    "stage": "Champion",
                    "regionId": 1,
                    "isAlive": True,
                    "x": 462585,
                    "y": 628386,
                    "z": 1601,
                    "effectiveLevel": 5,
                    "growthScore": 3000,
                },
            ]
        }

        target = matrix.extract_live_mob_growth_target(
            payload,
            "mob-growth:killed:region:1",
            max_preferred_level=5,
            reference_position=(467238, 632158, 1784),
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.mob_id, "allowed-level")

    def test_extract_mob_growth_followup_rejects_overlevel_targets_when_level_cap_is_set(self) -> None:
        payload = {
            "top": [
                {
                    "mobId": "too-high",
                    "name": "흉포한 vendo warrior",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 782673,
                    "y": 683146,
                    "z": 4776,
                    "effectiveLevel": 14,
                    "growthScore": 6000,
                },
            ]
        }

        target = matrix.extract_live_mob_growth_target(
            payload,
            "mob-growth:killed:region:100",
            max_preferred_level=1,
            reference_position=(772240, 755512, 4656),
        )

        self.assertIsNone(target)

    def test_followup_binding_keeps_starter_quest_player_level(self) -> None:
        case = matrix.QuestCase(
            name="mid-p1",
            key="mid",
            realm="Midgard",
            region=100,
            seed_npc="Finn",
            target="soft-shelled crab",
            return_home=(772240, 755512, 4656),
            party_size=1,
            accounts_csv=Path("accounts.csv"),
            output_dir=Path("out"),
            player_level=1,
        )
        target = matrix.LiveMobGrowthTarget(
            name="노련한 black mauler",
            region=100,
            x=707076,
            y=792727,
            z=4499,
            min_level=13,
            max_level=13,
        )

        bound = matrix.bind_case_to_mob_growth_followup(case, target)

        self.assertEqual(bound.player_level, 1)

    def test_followup_binding_passes_nearby_growth_aliases(self) -> None:
        case = matrix.QuestCase(
            name="mid-p1",
            key="mid",
            realm="Midgard",
            region=100,
            seed_npc="Finn",
            target="soft-shelled crab",
            return_home=(772240, 755512, 4656),
            party_size=1,
            accounts_csv=Path("accounts.csv"),
            output_dir=Path("out"),
            player_level=16,
        )
        payload = {
            "top": [
                {
                    "mobId": "vestus",
                    "name": "노련한 Vestus",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 777409,
                    "y": 685458,
                    "z": 4707,
                    "effectiveLevel": 16,
                    "growthScore": 4000,
                    "combatCount": 0,
                    "playerKills": 0,
                },
                {
                    "mobId": "vendo-flayer",
                    "name": "노련한 vendo flayer",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 777632,
                    "y": 684107,
                    "z": 4707,
                    "effectiveLevel": 15,
                    "growthScore": 3000,
                    "combatCount": 1,
                    "playerKills": 0,
                },
                {
                    "mobId": "far-growth",
                    "name": "노련한 far target",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 790000,
                    "y": 700000,
                    "z": 4707,
                    "effectiveLevel": 14,
                    "growthScore": 3000,
                    "combatCount": 0,
                    "playerKills": 0,
                },
            ]
        }

        target = matrix.extract_live_mob_growth_target(
            payload,
            "mob-growth:killed:region:100",
            max_preferred_level=16,
            reference_position=(777409, 685458, 4707),
            cluster_radius=0,
            alias_radius=3500,
            max_aliases=8,
        )
        self.assertIsNotNone(target)

        bound = matrix.bind_case_to_mob_growth_followup(case, target)

        self.assertEqual(bound.followup_target, "노련한 Vestus,노련한 vendo flayer")
        self.assertEqual(bound.followup_min_target_level, 15)
        self.assertEqual(bound.followup_max_target_level, 16)

    def test_extract_mob_growth_followup_prefers_low_kill_history_over_near_high_score(self) -> None:
        payload = {
            "top": [
                {
                    "mobId": "near-dangerous",
                    "name": "흉포한 creeping crud",
                    "stage": "Champion",
                    "regionId": 1,
                    "isAlive": True,
                    "x": 462585,
                    "y": 628386,
                    "z": 1601,
                    "effectiveLevel": 5,
                    "growthScore": 5300,
                    "combatCount": 5,
                    "playerKills": 4,
                },
                {
                    "mobId": "far-clean",
                    "name": "흉포한 skeleton",
                    "stage": "Champion",
                    "regionId": 1,
                    "isAlive": True,
                    "x": 520593,
                    "y": 585588,
                    "z": 3091,
                    "effectiveLevel": 5,
                    "growthScore": 5076,
                    "combatCount": 0,
                    "playerKills": 0,
                },
            ]
        }

        target = matrix.extract_live_mob_growth_target(
            payload,
            "mob-growth:killed:region:1",
            max_preferred_level=5,
            reference_position=(474770, 628824, 1724),
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.mob_id, "far-clean")

    def test_extract_mob_growth_followup_rejects_far_low_history_target_when_close_candidate_exists(self) -> None:
        payload = {
            "top": [
                {
                    "mobId": "far-clean",
                    "name": "노련한 black mauler",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 707076,
                    "y": 792727,
                    "z": 4499,
                    "effectiveLevel": 13,
                    "growthScore": 5100,
                    "combatCount": 0,
                    "playerKills": 0,
                },
                {
                    "mobId": "close-busier",
                    "name": "노련한 vendo flayer",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 770400,
                    "y": 672200,
                    "z": 5743,
                    "effectiveLevel": 13,
                    "growthScore": 4300,
                    "combatCount": 8,
                    "playerKills": 3,
                },
            ]
        }

        target = matrix.extract_live_mob_growth_target(
            payload,
            "mob-growth:killed:region:100",
            max_preferred_level=13,
            reference_position=(765741, 668745, 5743),
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.mob_id, "close-busier")

    def test_extract_mob_growth_followup_prefers_isolated_candidate_over_dense_cluster(self) -> None:
        payload = {
            "top": [
                {
                    "mobId": "cluster-clean",
                    "name": "노련한 vendo warrior",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 782756,
                    "y": 682891,
                    "z": 4757,
                    "effectiveLevel": 12,
                    "growthScore": 5200,
                    "combatCount": 0,
                    "playerKills": 0,
                },
                {
                    "mobId": "cluster-add-1",
                    "name": "흉포한 vendo warrior",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 782673,
                    "y": 683146,
                    "z": 4776,
                    "effectiveLevel": 12,
                    "growthScore": 6000,
                    "combatCount": 12,
                    "playerKills": 12,
                },
                {
                    "mobId": "cluster-add-2",
                    "name": "노련한 vendo frightener",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 782263,
                    "y": 682720,
                    "z": 4771,
                    "effectiveLevel": 12,
                    "growthScore": 4800,
                    "combatCount": 5,
                    "playerKills": 3,
                },
                {
                    "mobId": "cluster-add-3",
                    "name": "흉포한 rabid wolfhound",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 783378,
                    "y": 683344,
                    "z": 4787,
                    "effectiveLevel": 12,
                    "growthScore": 5100,
                    "combatCount": 7,
                    "playerKills": 7,
                },
                {
                    "mobId": "isolated-clean",
                    "name": "노련한 black mauler",
                    "stage": "Champion",
                    "regionId": 100,
                    "isAlive": True,
                    "x": 790000,
                    "y": 700000,
                    "z": 4500,
                    "effectiveLevel": 12,
                    "growthScore": 5000,
                    "combatCount": 0,
                    "playerKills": 0,
                },
            ]
        }

        target = matrix.extract_live_mob_growth_target(
            payload,
            "mob-growth:killed:region:100",
            max_preferred_level=12,
            reference_position=(765741, 668745, 5743),
        )

        self.assertIsNotNone(target)
        self.assertEqual(target.mob_id, "isolated-clean")

    def test_npc_command_forwards_expected_quest_id_and_timeline_requirements(self) -> None:
        args = matrix.parse_args([
            "--matrix",
            "quick",
            "--dynamic-quest-return-dialog-response",
            "decline",
            "--dynamic-quest-require-timeline-events",
            "choice_selected,world_signal",
            "--dynamic-quest-require-presentation-triggers",
            "OnAccept,OnComplete",
            "--dynamic-quest-expected-final-node",
            "observe_signal",
        ])
        case = matrix.build_cases(args)[0]
        case = matrix.replace(case, quest_id="quest-branch")

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--dynamic-quest-return-dialog-response", command)
        self.assertIn("decline", command)
        self.assertIn("--dynamic-quest-expected-quest-id", command)
        self.assertIn("quest-branch", command)
        self.assertIn("--dynamic-quest-require-timeline-events", command)
        self.assertIn("choice_selected,world_signal", command)
        self.assertIn("--dynamic-quest-require-presentation-triggers", command)
        self.assertIn("OnAccept,OnComplete", command)
        self.assertIn("--dynamic-quest-expected-final-node", command)
        self.assertIn("observe_signal", command)

    def test_autoaccept_command_forwards_return_dialog_response(self) -> None:
        args = matrix.parse_args([
            "--matrix",
            "quick",
            "--quest-start-mode",
            "autoaccept",
            "--dynamic-quest-return-dialog-response",
            "decline",
        ])
        case = matrix.build_cases(args)[0]

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--dynamic-quest-return-dialog-response", command)
        self.assertEqual(command[command.index("--dynamic-quest-return-dialog-response") + 1], "decline")

    def test_start_position_reset_sql_places_party_near_quest_npc(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "2"])
        case = matrix.build_cases(args)[0]
        account_rows = [
            {"username": "albtest001"},
            {"username": "albtest002"},
            {"username": "albtest003"},
        ]

        sql = matrix.build_start_position_update_sql(case, account_rows, position_step=20)

        self.assertIn("UPDATE `dolcharacters`", sql)
        self.assertIn("`Region` = 1", sql)
        self.assertIn("WHEN 'albtest001' THEN 518850", sql)
        self.assertIn("WHEN 'albtest002' THEN 518870", sql)
        self.assertNotIn("albtest003", sql)
        self.assertIn("`BindRegion` = 1", sql)
        self.assertNotIn("/dynamicquest", sql.lower())
        self.assertNotIn("fakekill", sql.lower())

    def test_start_position_reset_sql_sets_character_level_from_player_level(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--player-level", "7"])
        case = matrix.build_cases(args)[0]
        account_rows = [{"username": "albtest001"}]

        sql = matrix.build_start_position_update_sql(
            case,
            account_rows,
            position_step=20,
            player_level=args.player_level,
        )

        self.assertIn("`Level` = 7", sql)

    def test_start_position_reset_sql_restores_combat_resources(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "1"])
        case = matrix.build_cases(args)[0]

        sql = matrix.build_start_position_update_sql(
            case,
            [{"username": "albtest001"}],
            position_step=20,
            player_level=5,
        )

        self.assertIn("`Health` = 10000", sql)
        self.assertIn("`Mana` = 10000", sql)
        self.assertIn("`Endurance` = 10000", sql)

    def test_prepare_case_accounts_csv_skips_completed_live_quest_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"username": "albtest001", "password": "x", "realm": "1"},
                        {"username": "albtest002", "password": "x", "realm": "1"},
                        {"username": "albtest003", "password": "x", "realm": "1"},
                    ]
                )
            case = matrix.QuestCase(
                name="alb-p2",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Eabae Egesa",
                target="black wolf pup",
                return_home=(532069, 479749, 2220),
                party_size=2,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=5,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "2"])

            with (
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(
                    matrix,
                    "account_has_completed_or_active_dynamic_quest",
                    side_effect=lambda _args, username, _quest_id: username == "albtest001",
                ),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["albtest002", "albtest003"])

    def test_prepare_case_accounts_csv_skips_any_active_dynamic_quest_account(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"username": "albtest001", "password": "x", "realm": "1"},
                        {"username": "albtest002", "password": "x", "realm": "1"},
                    ]
                )
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Eabae Egesa",
                target="black wolf pup",
                return_home=(532069, 479749, 2220),
                party_size=1,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=5,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "1"])

            with (
                mock.patch.object(
                    matrix,
                    "account_has_any_active_dynamic_quest",
                    side_effect=lambda _args, username: username == "albtest001",
                ),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["albtest002"])

    def test_prepare_case_accounts_csv_prefers_melee_smoke_accounts_for_live_quest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm", "class_name"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"username": "albtest001", "password": "x", "realm": "1", "class_name": "Wizard"},
                        {"username": "albtest002", "password": "x", "realm": "1", "class_name": "Paladin"},
                        {"username": "albtest003", "password": "x", "realm": "1", "class_name": "Armsman"},
                    ]
                )
            case = matrix.QuestCase(
                name="alb-p2",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Eabae Egesa",
                target="black wolf pup",
                return_home=(532069, 479749, 2220),
                party_size=2,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=5,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "2"])

            with (
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["albtest002", "albtest003"])

    def test_prepare_case_accounts_csv_enriches_missing_class_data_from_db(self) -> None:
        class FakeProvision:
            @staticmethod
            def resolve_mysql_bin(_value):
                return "mysql"

            @staticmethod
            def read_serverconfig_password():
                return ""

            @staticmethod
            def mysql_bin_available(_value):
                return True

            @staticmethod
            def run_mysql(_args, _sql):
                return ""

            @staticmethod
            def parse_mysql_rows(_output):
                return [
                    {"AccountName": "midtest041", "Class": "24", "Level": "16"},
                    {"AccountName": "midtest042", "Class": "22", "Level": "16"},
                    {"AccountName": "midtest043", "Class": "31", "Level": "16"},
                ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"username": "midtest041", "password": "x", "realm": "2"},
                        {"username": "midtest042", "password": "x", "realm": "2"},
                        {"username": "midtest043", "password": "x", "realm": "2"},
                    ]
                )
            case = matrix.QuestCase(
                name="mid-p2",
                key="mid",
                realm="Midgard",
                region=100,
                seed_npc="Gothi of Odin",
                target="Birk",
                return_home=(765637, 668599, 5759),
                party_size=2,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=14,
                max_target_level=14,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "2"])

            with (
                mock.patch.object(matrix, "load_provision_module", return_value=FakeProvision),
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["midtest042", "midtest043"])
            self.assertEqual([row["class_name"] for row in rows], ["Warrior", "Berserker"])

    def test_prepare_case_accounts_csv_puts_support_melee_after_core_melee_for_live_quest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm", "class_name"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"username": "albtest001", "password": "x", "realm": "1", "class_name": "Friar"},
                        {"username": "albtest002", "password": "x", "realm": "1", "class_name": "Minstrel"},
                        {"username": "albtest003", "password": "x", "realm": "1", "class_name": "Mercenary"},
                        {"username": "albtest004", "password": "x", "realm": "1", "class_name": "Paladin"},
                    ]
                )
            case = matrix.QuestCase(
                name="alb-p2",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Eabae Egesa",
                target="black wolf pup",
                return_home=(532069, 479749, 2220),
                party_size=2,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=5,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "2"])

            with (
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["albtest004", "albtest003"])

    def test_prepare_case_accounts_csv_requires_melee_smoke_accounts_when_class_data_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm", "class_name"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"username": "albtest001", "password": "x", "realm": "1", "class_name": "Cleric"},
                        {"username": "albtest002", "password": "x", "realm": "1", "class_name": "Wizard"},
                    ]
                )
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Eabae Egesa",
                target="black wolf pup",
                return_home=(532069, 479749, 2220),
                party_size=1,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=5,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "1"])

            with (
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
            ):
                with self.assertRaisesRegex(RuntimeError, "not enough melee smoke account rows"):
                    matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

    def test_prepare_case_accounts_csv_can_disable_required_melee_smoke_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm", "class_name"])
                writer.writeheader()
                writer.writerow({"username": "albtest001", "password": "x", "realm": "1", "class_name": "Cleric"})
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Eabae Egesa",
                target="black wolf pup",
                return_home=(532069, 479749, 2220),
                party_size=1,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=5,
            )
            args = matrix.parse_args(
                ["--matrix", "quick", "--party-sizes", "1", "--no-require-melee-smoke-accounts"]
            )

            with (
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["albtest001"])

    def test_format_case_text_template_supports_region_token(self) -> None:
        case = matrix.QuestCase(
            name="hib-p1",
            key="hib",
            realm="Hibernia",
            region=200,
            seed_npc="Ionhar",
            target="water beetle larva",
            return_home=(344500, 474500, 5372),
            party_size=1,
            accounts_csv=Path("accounts.csv"),
            output_dir=Path("out"),
            min_target_level=1,
            max_target_level=5,
        )

        value = matrix.format_case_text_template("mob-growth:killed:region:{region}", case)

        self.assertEqual(value, "mob-growth:killed:region:200")

    def test_mob_growth_summary_url_can_filter_top_mobs_by_region(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--api-port", "5000"])

        value = matrix.build_mob_growth_summary_api_url(args, region_id=100)

        self.assertIn("limit=100", value)
        self.assertIn("region=100", value)

    def test_prepare_case_accounts_csv_prefers_midgard_melee_smoke_accounts_for_live_quest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm", "class_name"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"username": "midtest007", "password": "x", "realm": "2", "class_name": "Shaman"},
                        {"username": "midtest008", "password": "x", "realm": "2", "class_name": "Runemaster"},
                        {"username": "midtest009", "password": "x", "realm": "2", "class_name": "Warrior"},
                        {"username": "midtest011", "password": "x", "realm": "2", "class_name": "Berserker"},
                    ]
                )
            case = matrix.QuestCase(
                name="mid-p2",
                key="mid",
                realm="Midgard",
                region=100,
                seed_npc="Aud",
                target="young sveawolf",
                return_home=(773327, 749653, 4552),
                party_size=2,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=5,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "2"])

            with (
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["midtest009", "midtest011"])

    def test_prepare_case_accounts_csv_prefers_hibernia_melee_smoke_accounts_for_live_quest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm", "class_name"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"username": "hibtest007", "password": "x", "realm": "3", "class_name": "Eldritch"},
                        {"username": "hibtest008", "password": "x", "realm": "3", "class_name": "Enchanter"},
                        {"username": "hibtest009", "password": "x", "realm": "3", "class_name": "Hero"},
                        {"username": "hibtest010", "password": "x", "realm": "3", "class_name": "Blademaster"},
                    ]
                )
            case = matrix.QuestCase(
                name="hib-p2",
                key="hib",
                realm="Hibernia",
                region=200,
                seed_npc="Ionhar",
                target="water beetle larva",
                return_home=(344500, 474500, 5372),
                party_size=2,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=5,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "2"])

            with (
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["hibtest009", "hibtest010"])

    def test_account_filter_uses_read_only_db_progress_when_api_has_no_memory_timeline(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])

        with (
            mock.patch.object(matrix, "fetch_dynamic_quest_player_api", return_value={}),
            mock.patch.object(matrix, "account_has_dynamic_quest_progress_row", return_value=True),
        ):
            self.assertTrue(
                matrix.account_has_completed_or_active_dynamic_quest(
                    args,
                    "albtest002",
                    "seed-1-e0795a280b420cd5",
                )
            )

    def test_progress_filter_treats_completed_quest_ids_as_used(self) -> None:
        payload = {
            "active": [],
            "completedQuestIds": ["seed-1-e0795a280b420cd5"],
        }

        self.assertTrue(
            matrix.dynamic_quest_progress_has_active_quest(
                payload,
                "seed-1-e0795a280b420cd5",
            )
        )

    def test_start_position_reset_sql_can_use_live_objective(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "2"])
        case = matrix.build_cases(args)[0]
        account_rows = [{"username": "albtest001"}, {"username": "albtest002"}]

        sql = matrix.build_start_position_update_sql(
            case,
            account_rows,
            position_step=20,
            start_position=matrix.StartPosition(region=1, x=512226, y=481628, z=2222),
        )

        self.assertIn("WHEN 'albtest001' THEN 512226", sql)
        self.assertIn("WHEN 'albtest002' THEN 512246", sql)
        self.assertIn("WHEN 'albtest001' THEN 481628", sql)
        self.assertIn("`BindRegion` = 1", sql)

    def test_extract_live_start_position_uses_current_start_node_objective(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])
        case = matrix.build_cases(args)[0]
        payload = {
            "quests": [
                {
                    "startRegionId": 1,
                    "targetName": "black wolf pup",
                    "startNodeId": "explore",
                    "nodes": [
                        {
                            "id": "explore",
                            "objective": {
                                "regionId": 1,
                                "x": 512226,
                                "y": 481628,
                                "z": 2222,
                            },
                        }
                    ],
                }
            ]
        }

        position = matrix.extract_live_start_position(payload, case)

        self.assertEqual(position, matrix.StartPosition(1, 512226, 481628, 2222))

    def test_extract_live_quest_binding_uses_current_selector_npc_offer(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])
        case = matrix.build_cases(args)[0]
        payload = {
            "quests": [
                {
                    "startRegionId": 1,
                    "startNpcName": "Bowman Commander",
                    "startNpcInternalId": "selector-start-1",
                    "targetName": "dragon ant worker",
                    "minLevel": 1,
                    "maxLevel": 5,
                    "startNodeId": "talk",
                    "tags": [
                        "selector:start:town-npc",
                        "selector:target:hostile-near-start",
                    ],
                }
            ]
        }

        binding = matrix.extract_live_quest_binding(payload, case, "npc")

        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.seed_npc, "Bowman Commander")
        self.assertEqual(binding.start_npc_internal_id, "selector-start-1")
        self.assertEqual(binding.target, "dragon ant worker")
        self.assertEqual(binding.min_target_level, 1)
        self.assertEqual(binding.max_target_level, 5)
        self.assertEqual(binding.min_player_level, 1)
        self.assertEqual(binding.max_player_level, 5)

    def test_extract_live_quest_binding_prefers_kill_objective_level_bounds(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])
        case = matrix.build_cases(args)[0]
        payload = {
            "quests": [
                {
                    "startRegionId": 1,
                    "startNpcName": "Bowman Commander",
                    "startNpcInternalId": "selector-start-1",
                    "targetName": "large ant",
                    "minLevel": 1,
                    "maxLevel": 5,
                    "startNodeId": "talk",
                    "tags": ["branch:mob-growth"],
                    "nodes": [
                        {
                            "id": "hunt_base",
                            "type": "kill",
                            "objective": {
                                "targetName": "large ant",
                                "minLevel": 1,
                                "maxLevel": 1,
                            },
                        },
                        {
                            "id": "observe_signal",
                            "type": "world_signal",
                        },
                    ],
                }
            ]
        }

        binding = matrix.extract_live_quest_binding(payload, case, "npc")

        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.target, "large ant")
        self.assertEqual(binding.min_target_level, 1)
        self.assertEqual(binding.max_target_level, 1)
        self.assertEqual(binding.min_player_level, 1)
        self.assertEqual(binding.max_player_level, 5)

    def test_extract_live_quest_binding_can_require_mob_growth_branch_tag(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])
        case = matrix.build_cases(args)[0]
        payload = {
            "quests": [
                {
                    "id": "quest-plain",
                    "startRegionId": 1,
                    "startNpcName": "Plain Questgiver",
                    "targetName": "plain wolf",
                    "tags": ["starter"],
                },
                {
                    "id": "quest-branch",
                    "startRegionId": 1,
                    "startNpcName": "Branch Questgiver",
                    "targetName": "branch wolf",
                    "minLevel": 2,
                    "maxLevel": 4,
                    "tags": [
                        "branch:mob-growth",
                        "world-signal:mob-growth:killed:region:1",
                    ],
                },
            ]
        }

        binding = matrix.extract_live_quest_binding(
            payload,
            case,
            "npc",
            required_tag="branch:mob-growth",
            required_world_signal="mob-growth:killed:region:1",
        )

        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.quest_id, "quest-branch")
        self.assertEqual(binding.seed_npc, "Branch Questgiver")
        self.assertEqual(binding.target, "branch wolf")
        self.assertEqual(binding.min_target_level, 2)
        self.assertEqual(binding.max_target_level, 4)
        self.assertEqual(binding.min_player_level, 2)
        self.assertEqual(binding.max_player_level, 4)

    def test_extract_live_quest_binding_can_require_target_name(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])
        case = matrix.build_cases(args)[0]
        payload = {
            "quests": [
                {
                    "id": "quest-starter",
                    "startRegionId": 1,
                    "startNpcName": "Starter Questgiver",
                    "targetName": "soft-shelled crab",
                    "minLevel": 1,
                    "maxLevel": 5,
                    "tags": [
                        "branch:mob-growth",
                        "world-signal:mob-growth:killed:region:1",
                    ],
                },
                {
                    "id": "quest-growth",
                    "startRegionId": 1,
                    "startNpcName": "Growth Questgiver",
                    "targetName": "vendo flayer",
                    "minLevel": 15,
                    "maxLevel": 17,
                    "tags": [
                        "branch:mob-growth",
                        "world-signal:mob-growth:killed:region:1",
                    ],
                },
            ]
        }

        binding = matrix.extract_live_quest_binding(
            payload,
            case,
            "npc",
            required_tag="branch:mob-growth",
            required_world_signal="mob-growth:killed:region:1",
            required_target_name="vendo flayer",
        )

        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.quest_id, "quest-growth")
        self.assertEqual(binding.target, "vendo flayer")
        self.assertEqual(binding.min_player_level, 15)
        self.assertEqual(binding.max_player_level, 17)

    def test_bind_case_to_live_npc_offer_updates_command_names_position_and_levels(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])
        case = matrix.build_cases(args)[0]
        binding = matrix.LiveQuestBinding(
            seed_npc="Bowman Commander",
            target="dragon ant worker",
            min_target_level=1,
            max_target_level=5,
            start_npc_internal_id="selector-start-1",
            start_position=matrix.StartPosition(region=1, x=591197, y=494172, z=2302),
        )

        bound_case, start_position = matrix.bind_case_to_live_quest(case, binding)
        command = matrix.build_behavior_command(bound_case, args)

        self.assertEqual(start_position, matrix.StartPosition(1, 591197, 494172, 2302))
        self.assertIn("Bowman Commander", command)
        self.assertIn("dragon ant worker", command)
        self.assertNotIn("Brother Penric", command)
        self.assertNotIn("black wolf pup", command)
        self.assertIn("--dynamic-quest-return-home", command)
        self.assertIn("591197,494172,2302", command)
        self.assertIn("--max-target-level", command)
        self.assertIn("5", command)

    def test_bind_case_to_live_quest_raises_underleveled_player_to_quest_range(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--player-level", "1"])
        case = matrix.build_cases(args)[0]
        binding = matrix.LiveQuestBinding(
            seed_npc="",
            target="amadan touched",
            min_target_level=27,
            max_target_level=31,
            start_position=matrix.StartPosition(region=200, x=344500, y=474500, z=5372),
        )

        bound_case, _ = matrix.bind_case_to_live_quest(case, binding)
        command = matrix.build_behavior_command(bound_case, args)
        sql = matrix.build_start_position_update_sql(
            bound_case,
            [{"username": "hibtest001"}],
            position_step=20,
            player_level=bound_case.player_level,
        )

        player_level_index = command.index("--player-level") + 1
        self.assertEqual(bound_case.player_level, 31)
        self.assertEqual(command[player_level_index], "31")
        self.assertIn("`Level` = 31", sql)

    def test_bind_case_to_live_quest_keeps_requested_overleveled_player_level(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--player-level", "15"])
        case = matrix.build_cases(args)[0]
        binding = matrix.LiveQuestBinding(
            seed_npc="",
            target="convert guard",
            min_target_level=8,
            max_target_level=9,
            start_position=matrix.StartPosition(region=1, x=577400, y=491609, z=2649),
        )

        bound_case, _ = matrix.bind_case_to_live_quest(case, binding)
        command = matrix.build_behavior_command(bound_case, args)
        sql = matrix.build_start_position_update_sql(
            bound_case,
            [{"username": "albtest001"}],
            position_step=20,
            player_level=bound_case.player_level,
        )

        player_level_index = command.index("--player-level") + 1
        self.assertEqual(bound_case.player_level, 15)
        self.assertEqual(command[player_level_index], "15")
        self.assertIn("`Level` = 15", sql)

    def test_bind_case_to_live_npc_offer_clamps_overleveled_player_to_offer_range(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--player-level", "15"])
        case = matrix.build_cases(args)[0]
        binding = matrix.LiveQuestBinding(
            seed_npc="Devyn Godric",
            target="puny skeleton",
            min_target_level=1,
            max_target_level=5,
            start_npc_internal_id="selector-start-1",
            start_position=matrix.StartPosition(region=1, x=474770, y=628824, z=1724),
        )

        bound_case, _ = matrix.bind_case_to_live_quest(case, binding, preserve_overlevel=False)
        command = matrix.build_behavior_command(bound_case, args)
        sql = matrix.build_start_position_update_sql(
            bound_case,
            [{"username": "albtest001"}],
            position_step=20,
            player_level=bound_case.player_level,
        )

        player_level_index = command.index("--player-level") + 1
        self.assertEqual(bound_case.player_level, 5)
        self.assertEqual(command[player_level_index], "5")
        self.assertIn("`Level` = 5", sql)

    def test_followup_preserve_overlevel_flag_keeps_requested_player_level(self) -> None:
        args = matrix.parse_args([
            "--matrix",
            "quick",
            "--player-level",
            "15",
            "--dynamic-quest-followup-growth-target",
            "--dynamic-quest-followup-preserve-overlevel",
        ])
        case = matrix.build_cases(args)[0]
        binding = matrix.LiveQuestBinding(
            seed_npc="Devyn Godric",
            target="puny skeleton",
            min_target_level=1,
            max_target_level=5,
            start_npc_internal_id="selector-start-1",
            start_position=matrix.StartPosition(region=1, x=474770, y=628824, z=1724),
        )

        bound_case, _ = matrix.bind_case_to_live_quest(
            case,
            binding,
            preserve_overlevel=matrix.should_preserve_live_quest_overlevel("npc", args),
        )

        self.assertEqual(bound_case.player_level, 15)

    def test_account_offset_selects_later_party_rows(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "2", "--account-offset", "1"])
        case = matrix.build_cases(args)[0]
        account_rows = [
            {"username": "albtest001"},
            {"username": "albtest002"},
            {"username": "albtest003"},
            {"username": "albtest004"},
        ]

        sql = matrix.build_start_position_update_sql(case, account_rows, position_step=20, account_offset=args.account_offset)
        command = matrix.build_behavior_command(case, args)

        self.assertNotIn("albtest001", sql)
        self.assertIn("WHEN 'albtest002' THEN 518850", sql)
        self.assertIn("WHEN 'albtest003' THEN 518870", sql)
        self.assertNotIn("albtest004", sql)
        self.assertIn(str(case.output_dir / "accounts-offset-1-p2.csv"), command)

    def test_summarize_case_counts_completion_reward_target_and_deaths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_reward_observed",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "elapsed_seconds": "42.5",
                        "action_dynamic_quest_complete_verified": "1",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_reward_observed": "1",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.players, 1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.reward_observed, 1)
        self.assertEqual(summary.target_removed, 1)
        self.assertEqual(summary.player_deaths, 0)

    def test_summarize_case_accepts_followup_requirement_when_world_signal_already_arrived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_reward_observed",
                        "action_dynamic_quest_timeline_choice_selected",
                        "action_dynamic_quest_timeline_world_signal",
                        "action_dynamic_quest_followup_hunt_start",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "154.5",
                        "action_dynamic_quest_complete_verified": "0",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_reward_observed": "1",
                        "action_dynamic_quest_timeline_choice_selected": "1",
                        "action_dynamic_quest_timeline_world_signal": "1",
                        "action_dynamic_quest_followup_hunt_start": "0",
                    }
                )

            summary = matrix.summarize_case(case_dir, require_followup_hunt=True)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.choice_selected, 1)
        self.assertEqual(summary.world_signal, 1)
        self.assertEqual(summary.followup_hunt_start, 0)

    def test_summarize_case_fails_quality_gate_when_player_died(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_final_inactive",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "1",
                        "elapsed_seconds": "42.5",
                        "action_dynamic_quest_complete_verified": "1",
                        "action_dynamic_quest_final_inactive": "1",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertFalse(summary.passed)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.ok_players, 1)
        self.assertEqual(summary.player_deaths, 1)

    def test_summarize_case_can_require_dynamic_quest_followup_hunt_start(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_followup_hunt_start",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "42.5",
                        "action_dynamic_quest_complete_verified": "1",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_followup_hunt_start": "0",
                    }
                )

            default_summary = matrix.summarize_case(case_dir)
            required_summary = matrix.summarize_case(case_dir, require_followup_hunt=True)

        self.assertTrue(default_summary.passed)
        self.assertFalse(required_summary.passed)
        self.assertEqual(required_summary.followup_hunt_start, 0)

    def test_summarize_case_does_not_require_reward_chat_observation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_reward_observed",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "elapsed_seconds": "42.5",
                        "action_dynamic_quest_complete_verified": "1",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_reward_observed": "0",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.reward_observed, 0)

    def test_summarize_case_does_not_require_target_removed_counter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_reward_observed",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "42.5",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_reward_observed": "1",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.target_removed, 0)

    def test_summarize_case_counts_expected_active_node_as_dynamic_quest_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_expected_active_node_verified",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_final_expected_active_node",
                        "action_dynamic_quest_reward_observed",
                        "action_dynamic_quest_timeline_choice_selected",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "elapsed_seconds": "42.5",
                        "action_dynamic_quest_complete_verified": "0",
                        "action_dynamic_quest_expected_active_node_verified": "1",
                        "action_dynamic_quest_final_inactive": "0",
                        "action_dynamic_quest_final_expected_active_node": "0",
                        "action_dynamic_quest_reward_observed": "0",
                        "action_dynamic_quest_timeline_choice_selected": "1",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.choice_selected, 1)

    def test_summarize_case_accepts_completion_even_when_final_progress_is_inactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_final_never_active",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "elapsed_seconds": "42.5",
                        "action_dynamic_quest_complete_verified": "1",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_final_never_active": "0",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.completed, 1)

    def test_summarize_case_fails_when_completion_verified_but_never_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_final_never_active",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "elapsed_seconds": "42.5",
                        "action_dynamic_quest_complete_verified": "1",
                        "action_dynamic_quest_final_inactive": "0",
                        "action_dynamic_quest_final_never_active": "1",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertFalse(summary.passed)
        self.assertEqual(summary.completed, 1)

    def test_summarize_case_fails_when_dynamic_quest_never_became_active_without_completion(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "username",
                        "ok",
                        "target_removed",
                        "player_deaths",
                        "elapsed_seconds",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_final_never_active",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "elapsed_seconds": "42.5",
                        "action_dynamic_quest_complete_verified": "0",
                        "action_dynamic_quest_final_inactive": "0",
                        "action_dynamic_quest_final_never_active": "1",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertFalse(summary.passed)
        self.assertEqual(summary.completed, 0)

    def test_dry_run_writes_commands_without_launching_dummy_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            args = matrix.parse_args(
                [
                    "--matrix",
                    "quick",
                    "--party-sizes",
                    "1",
                    "--output-root",
                    str(output_root),
                    "--accounts-pattern",
                    "accounts-{realm}-p{party_size}.csv",
                    "--dry-run",
                ]
            )

            with mock.patch.object(matrix.subprocess, "run") as run:
                rc = matrix.run_matrix(args)

            commands = (output_root / "commands.txt").read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        run.assert_not_called()
        self.assertIn("behavior-dummy-client.py", commands)
        self.assertIn("--startup-service-accept-dialog", commands)

    def test_dry_run_autoaccept_binds_live_quest_before_writing_command(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            args = matrix.parse_args(
                [
                    "--matrix",
                    "quick",
                    "--party-sizes",
                    "1",
                    "--output-root",
                    str(output_root),
                    "--accounts-pattern",
                    "missing-{realm}-p{party_size}.csv",
                    "--quest-start-mode",
                    "autoaccept",
                    "--require-quest-tag",
                    "target:Agisthil",
                    "--player-level",
                    "15",
                    "--dry-run",
                ]
            )
            payload = {
                "quests": [
                    {
                        "id": "quest-default-npc",
                        "startRegionId": 1,
                        "startNpcName": "Brother Penric",
                        "targetName": "black wolf pup",
                        "tags": ["target:black wolf pup"],
                    },
                    {
                        "id": "seed-1-auto-Agisthil",
                        "startRegionId": 1,
                        "startNpcName": "",
                        "targetName": "Agisthil",
                        "minLevel": 11,
                        "maxLevel": 15,
                        "startNodeId": "approach",
                        "tags": ["target:Agisthil"],
                        "nodes": [
                            {
                                "id": "approach",
                                "type": "travel",
                                "objective": {
                                    "regionId": 1,
                                    "x": 505000,
                                    "y": 502000,
                                    "z": 3200,
                                },
                            },
                            {
                                "id": "kill",
                                "type": "kill",
                                "objective": {
                                    "targetName": "Agisthil",
                                    "minLevel": 13,
                                    "maxLevel": 13,
                                },
                            },
                        ],
                    },
                ]
            }

            with (
                mock.patch.object(matrix, "fetch_live_dynamic_quests", return_value=payload),
                mock.patch.object(matrix.subprocess, "run") as run,
            ):
                rc = matrix.run_matrix(args)

            commands = (output_root / "commands.txt").read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        run.assert_not_called()
        self.assertIn("--require-target-name Agisthil", commands)
        self.assertIn("--dynamic-quest-expected-quest-id seed-1-auto-Agisthil", commands)
        self.assertIn("--min-target-level 13", commands)
        self.assertIn("--max-target-level 13", commands)
        self.assertIn("--player-level 15", commands)
        self.assertIn("--dynamic-quest-observe-final-progress", commands)
        self.assertNotIn("black wolf pup", commands)
        self.assertNotIn("--startup-service-accept-dialog", commands)


if __name__ == "__main__":
    unittest.main()
