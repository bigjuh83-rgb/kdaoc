#!/usr/bin/env python3
"""Unit checks for the dynamic quest dummy matrix runner."""

from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
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

    def test_standard_smoke_builds_branch_followup_cases(self) -> None:
        args = matrix.parse_args(["--matrix", "standard-smoke", "--party-sizes", "1,2"])

        cases = matrix.build_cases(args)

        self.assertEqual(len(cases), 6)
        self.assertEqual(
            {(case.key, case.require_quest_tag, case.require_world_signal, case.return_dialog_response) for case in cases if case.party_size == 1},
            {
                ("alb", "branch:mob-growth", "mob-growth:killed:region:1", "decline"),
                ("mid", "branch:time-window", "time-window:night", "decline"),
                ("hib", "branch:item-acquired", "item-acquired", "decline"),
            },
        )
        self.assertTrue(next(case for case in cases if case.key == "alb").followup_growth_target)
        self.assertFalse(next(case for case in cases if case.key == "hib").followup_growth_target)
        self.assertEqual(
            next(case for case in cases if case.key == "hib").require_presentation_triggers,
            "OnAccept,OnChoiceSelected,OnWorldSignal,OnComplete",
        )
        self.assertEqual(
            next(case for case in cases if case.key == "mid").require_presentation_triggers,
            "OnAccept,OnChoiceSelected,OnComplete",
        )
        self.assertEqual(next(case for case in cases if case.key == "mid").expected_final_node, "")

    def test_standard_smoke_command_forwards_case_timeline_and_followup_choice(self) -> None:
        args = matrix.parse_args(["--matrix", "standard-smoke", "--party-sizes", "1"])
        case = next(case for case in matrix.build_cases(args) if case.key == "hib")
        case = matrix.replace(case, quest_id="quest-item")

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--dynamic-quest-return-dialog-response", command)
        self.assertEqual(command[command.index("--dynamic-quest-return-dialog-response") + 1], "decline")
        self.assertIn("--dynamic-quest-require-timeline-events", command)
        self.assertIn("choice_selected", command[command.index("--dynamic-quest-require-timeline-events") + 1])
        self.assertIn("world_signal", command[command.index("--dynamic-quest-require-timeline-events") + 1])
        self.assertIn("world_impact", command[command.index("--dynamic-quest-require-timeline-events") + 1])
        self.assertIn("world_impact_summary", command[command.index("--dynamic-quest-require-timeline-events") + 1])
        self.assertIn("--dynamic-quest-require-presentation-triggers", command)
        self.assertIn("OnWorldSignal", command[command.index("--dynamic-quest-require-presentation-triggers") + 1])
        self.assertIn("--dynamic-quest-expected-final-node", command)
        self.assertEqual(command[command.index("--dynamic-quest-expected-final-node") + 1], "complete")

    def test_standard_smoke_midgard_waits_for_time_window_timeout_fallback(self) -> None:
        args = matrix.parse_args(["--matrix", "standard-smoke", "--party-sizes", "1"])
        case = next(case for case in matrix.build_cases(args) if case.key == "mid")
        case = matrix.replace(case, quest_id="quest-time")

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--dynamic-quest-return-complete-wait", command)
        self.assertEqual(command[command.index("--dynamic-quest-return-complete-wait") + 1], "70.0")
        self.assertIn("--dynamic-quest-require-timeline-events", command)
        required_events = command[command.index("--dynamic-quest-require-timeline-events") + 1]
        self.assertNotIn("world_signal", required_events)
        self.assertIn("world_impact_summary", required_events)
        self.assertNotIn("--dynamic-quest-expected-final-node", command)

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
        self.assertIn("--dynamic-quest-timeline-limit", command)
        self.assertEqual(command[command.index("--dynamic-quest-timeline-limit") + 1], "2000")
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
        self.assertEqual(command[command.index("--low-health-rest-percent") + 1], "45")
        self.assertIn("--low-health-rest-resume-percent", command)
        self.assertIn("95", command)
        self.assertIn("--low-health-rest-min", command)
        self.assertEqual(command[command.index("--low-health-rest-min") + 1], "6.0")
        self.assertIn("--low-health-rest-max", command)
        self.assertEqual(command[command.index("--low-health-rest-max") + 1], "14.0")
        self.assertIn("--flee-dynamic-safe-point", command)
        self.assertIn("--flee-safe-threat-radius", command)
        self.assertEqual(command[command.index("--flee-safe-threat-radius") + 1], "6000.0")
        self.assertIn("--flee-safe-point-distance", command)
        self.assertEqual(command[command.index("--flee-safe-point-distance") + 1], "1400.0")
        self.assertIn("--flee-critical-health-percent", command)
        self.assertEqual(command[command.index("--flee-critical-health-percent") + 1], "30")
        self.assertIn("--flee-critical-safe-point-distance", command)
        self.assertEqual(command[command.index("--flee-critical-safe-point-distance") + 1], "2200.0")
        self.assertIn("--flee-safe-api-scout", command)
        self.assertIn("--flee-safe-replan-damage-grace", command)
        self.assertEqual(command[command.index("--flee-safe-replan-damage-grace") + 1], "3.0")
        self.assertIn("--flee-min-damage-taken", command)
        self.assertEqual(command[command.index("--flee-min-damage-taken") + 1], "20")
        self.assertIn("--flee-damage-taken-ratio", command)
        self.assertEqual(command[command.index("--flee-damage-taken-ratio") + 1], "1.5")
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

    def test_behavior_command_allows_explicit_flee_safe_distance_override(self) -> None:
        args = matrix.parse_args([
            "--matrix",
            "quick",
            "--party-sizes",
            "1",
            "--flee-safe-point-distance",
            "5200",
            "--flee-critical-safe-point-distance",
            "9000",
        ])
        case = matrix.build_cases(args)[0]

        command = matrix.build_behavior_command(case, args)

        self.assertEqual(command[command.index("--flee-safe-point-distance") + 1], "5200.0")
        self.assertEqual(command[command.index("--flee-critical-safe-point-distance") + 1], "9000.0")

    def test_autoaccept_command_observes_final_progress_without_npc_dialog(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--quest-start-mode", "autoaccept"])
        case = matrix.build_cases(args)[0]

        command = matrix.build_behavior_command(case, args)
        rendered = " ".join(command)

        self.assertIn("--dynamic-quest-observe-final-progress", command)
        self.assertIn("--startup-service-progress-wait-seconds", command)
        self.assertEqual(command[command.index("--startup-service-progress-wait-seconds") + 1], "12")

    def test_autoaccept_live_bound_target_home_uses_wider_radius(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--quest-start-mode", "autoaccept", "--max-target-distance", "6500"])
        case = matrix.replace(
            matrix.build_cases(args)[0],
            quest_id="seed-live",
            target_home=(574776, 561705, 2327),
            target_home_radius=0,
        )

        command = matrix.build_behavior_command(case, args)
        rendered = " ".join(command)

        self.assertIn("--target-home-max-distance", command)
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "9000")
        self.assertIn("--required-target-home-hunt-distance", command)
        self.assertEqual(command[command.index("--required-target-home-hunt-distance") + 1], "9000")
        self.assertIn("--startup-service-progress-max-retries", command)
        self.assertEqual(command[command.index("--startup-service-progress-max-retries") + 1], "0")
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

    def test_followup_object_id_adds_exact_required_target_api(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])
        case = matrix.build_cases(args)[0]
        case = matrix.replace(
            case,
            followup_target="boar piglet",
            followup_home=(504376, 489100, 2470),
            followup_min_target_level=1,
            followup_max_target_level=1,
            followup_object_id=12818,
        )

        command = matrix.build_behavior_command(case, args)

        self.assertIn("--required-target-api", command)
        self.assertIn("--required-target-api-url", command)
        api_url = command[command.index("--required-target-api-url") + 1]
        self.assertIn("objectId=12818", api_url)
        self.assertIn("region=1", api_url)
        self.assertEqual(command[command.index("--required-target-api-name") + 1], "boar piglet")
        self.assertEqual(command[command.index("--required-target-api-limit") + 1], "1")

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

    def test_extract_live_binding_allows_world_signal_prefix_filter(self) -> None:
        args = matrix.parse_args(["--matrix", "realm-smoke", "--realms", "mid"])
        case = matrix.build_cases(args)[0]
        payload = {
            "quests": [
                {
                    "id": "quest-time-window-night",
                    "startRegionId": case.region,
                    "startNpcName": "Aud",
                    "startNpcInternalId": "npc-mid-1",
                    "targetName": "hobgoblin snake-finder",
                    "tags": ["branch:time-window", "world-signal:time-window:night"],
                    "nodes": [],
                }
            ]
        }

        binding = matrix.extract_live_quest_binding(
            payload,
            case,
            "npc",
            required_tag="branch:time-window",
            required_world_signal="time-window",
        )

        self.assertIsNotNone(binding)
        self.assertEqual(binding.quest_id, "quest-time-window-night")

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
            object_id=4242,
        )

        bound = matrix.bind_case_to_mob_growth_followup(case, target)

        self.assertEqual(bound.player_level, 1)
        self.assertEqual(bound.followup_object_id, 4242)

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
                mock.patch.object(matrix, "load_provision_module", side_effect=RuntimeError("db unavailable")),
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "filter_rows_with_existing_world_characters", side_effect=lambda rows, _args: (rows, [])),
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

    def test_prepare_case_accounts_csv_overwrites_stale_class_data_from_db(self) -> None:
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
                    {
                        "AccountName": "hibtest025",
                        "Class": "41",
                        "Level": "2",
                        "SerializedSpecs": "Light|1;Mana|1;Enchantments|1",
                    },
                    {
                        "AccountName": "hibtest001",
                        "Class": "44",
                        "Level": "2",
                        "SerializedSpecs": "Blades|2;Shields|1",
                    },
                ]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=["username", "password", "realm", "class_id", "class_name", "specs"],
                )
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "username": "hibtest025",
                            "password": "x",
                            "realm": "3",
                            "class_id": "44",
                            "class_name": "Hero",
                            "specs": "Blades|50",
                        },
                        {
                            "username": "hibtest001",
                            "password": "x",
                            "realm": "3",
                            "class_id": "44",
                            "class_name": "Hero",
                            "specs": "Blades|50",
                        },
                    ]
                )
            case = matrix.QuestCase(
                name="hib-p1",
                key="hib",
                realm="Hibernia",
                region=200,
                seed_npc="Gormghlaith",
                target="skeletal pawn",
                return_home=(341224, 593868, 5464),
                party_size=1,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=2,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "1"])

            with (
                mock.patch.object(matrix, "load_provision_module", return_value=FakeProvision),
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "filter_rows_with_existing_world_characters", side_effect=lambda rows, _args: (rows, [])),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual(rows[0]["username"], "hibtest001")
            self.assertEqual(rows[0]["class_id"], "44")
            self.assertEqual(rows[0]["class_name"], "Hero")
            self.assertEqual(rows[0]["specs"], "Blades|2;Shields|1")

    def test_build_db_args_ignores_missing_mysql_bin_value(self) -> None:
        class FakeProvision:
            resolved_with = object()

            @staticmethod
            def mysql_bin_available(_value):
                return False

            @classmethod
            def resolve_mysql_bin(cls, value):
                cls.resolved_with = value
                return "fallback-mysql"

            @staticmethod
            def read_serverconfig_password():
                return "server-password"

        args = matrix.parse_args(["--mysql-bin", "/missing/wsl/mariadb"])

        db_args = matrix.build_db_args(args, FakeProvision)

        self.assertIsNone(FakeProvision.resolved_with)
        self.assertEqual(db_args.mysql_bin, "fallback-mysql")
        self.assertEqual(db_args.db_password, "server-password")

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
                mock.patch.object(matrix, "load_provision_module", side_effect=RuntimeError("db unavailable")),
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "filter_rows_with_existing_world_characters", side_effect=lambda rows, _args: (rows, [])),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["albtest004", "albtest003"])

    def test_prepare_case_accounts_csv_skips_rows_missing_world_characters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            accounts = root / "accounts.csv"
            with accounts.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "password", "realm", "class_name"])
                writer.writeheader()
                writer.writerows(
                    [
                        {"username": "albtest017", "password": "x", "realm": "1", "class_name": "Paladin"},
                        {"username": "albtest009", "password": "x", "realm": "1", "class_name": "Paladin"},
                    ]
                )
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Sir Lukas",
                target="black wolf pup",
                return_home=(518850, 494050, 3352),
                party_size=1,
                accounts_csv=accounts,
                output_dir=root / "case",
                min_target_level=1,
                max_target_level=5,
            )
            args = matrix.parse_args(["--matrix", "quick", "--party-sizes", "1"])

            with (
                mock.patch.object(matrix, "existing_world_character_accounts", return_value={"albtest009"}),
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
            ):
                selected_csv = matrix.prepare_case_accounts_csv(case, args, quest_id="q1")

            with selected_csv.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))

            self.assertEqual([row["username"] for row in rows], ["albtest009"])
            self.assertEqual((root / "case" / "accounts-skipped-missing.txt").read_text(encoding="utf-8"), "albtest017\n")

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
                mock.patch.object(matrix, "load_provision_module", side_effect=RuntimeError("db unavailable")),
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
                mock.patch.object(matrix, "filter_rows_with_existing_world_characters", side_effect=lambda rows, _args: (rows, [])),
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
                mock.patch.object(matrix, "load_provision_module", side_effect=RuntimeError("db unavailable")),
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "filter_rows_with_existing_world_characters", side_effect=lambda rows, _args: (rows, [])),
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
                mock.patch.object(matrix, "load_provision_module", side_effect=RuntimeError("db unavailable")),
                mock.patch.object(matrix, "account_has_any_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "account_has_completed_or_active_dynamic_quest", return_value=False),
                mock.patch.object(matrix, "filter_rows_with_existing_world_characters", side_effect=lambda rows, _args: (rows, [])),
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

    def test_player_api_url_includes_player_for_timeline_lookup(self) -> None:
        args = matrix.parse_args(["--host", "127.0.0.1", "--api-port", "5000", "--dynamic-quest-timeline-limit", "900"])

        url = matrix.build_dynamic_quest_player_api_url(args, "timeline", "albtest003")

        self.assertIn("/api/world/dynamic-quests/timeline?", url)
        self.assertIn("player=albtest003", url)
        self.assertIn("limit=2000", url)
        self.assertNotIn("account=albtest003", url)

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
                                "regionId": 1,
                                "x": 591500,
                                "y": 494400,
                                "z": 2300,
                                "radius": 6500,
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
        self.assertEqual(binding.target_position, matrix.StartPosition(1, 591500, 494400, 2300))
        self.assertEqual(binding.target_radius, 6500)

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

    def test_extract_live_quest_binding_can_require_template_tag(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])
        case = matrix.build_cases(args)[0]
        payload = {
            "quests": [
                {
                    "id": "quest-old-template",
                    "startRegionId": 1,
                    "startNpcName": "Old Questgiver",
                    "targetName": "forest spiderling",
                    "minLevel": 1,
                    "maxLevel": 5,
                    "tags": ["template:seed-1-old"],
                },
                {
                    "id": "quest-required-template",
                    "startRegionId": 1,
                    "startNpcName": "New Questgiver",
                    "targetName": "forest spiderling",
                    "minLevel": 2,
                    "maxLevel": 6,
                    "tags": ["template:seed-1-required"],
                },
            ]
        }

        binding = matrix.extract_live_quest_binding(
            payload,
            case,
            "npc",
            required_target_name="forest spiderling",
            required_template="seed-1-required",
        )

        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.quest_id, "quest-required-template")
        self.assertEqual(binding.seed_npc, "New Questgiver")
        self.assertEqual(binding.min_player_level, 2)

    def test_fetch_live_quest_binding_waits_while_seed_is_running(self) -> None:
        args = matrix.parse_args(
            [
                "--matrix",
                "realm-smoke",
                "--realms",
                "hib",
                "--quest-start-mode",
                "autoaccept",
                "--live-quest-seed-wait-seconds",
                "10",
                "--live-quest-seed-wait-interval",
                "1",
            ]
        )
        case = matrix.build_cases(args)[0]
        empty_payload = {"quests": []}
        ready_payload = {
            "quests": [
                {
                    "id": "quest-hib-item",
                    "realm": "Hibernia",
                    "startRegionId": 200,
                    "startNpcName": "",
                    "targetName": "lough wolf cadger",
                    "tags": ["branch:item-acquired", "world-signal:item-acquired"],
                    "startNodeId": "explore",
                    "nodes": [
                        {
                            "id": "explore",
                            "objective": {"regionId": 200, "x": 292411, "y": 458413, "z": 6630},
                        }
                    ],
                }
            ]
        }

        with (
            mock.patch.object(matrix, "fetch_live_dynamic_quests", side_effect=[empty_payload, ready_payload]) as fetch_quests,
            mock.patch.object(matrix, "fetch_dynamic_quest_seed_status", return_value={"messages": ["seed running: seedFromWorld"]}) as fetch_seed,
            mock.patch.object(matrix.time, "monotonic", side_effect=[0.0, 0.0, 0.0]),
            mock.patch.object(matrix.time, "sleep") as sleep,
        ):
            binding = matrix.fetch_live_quest_binding_with_seed_wait(
                args,
                case,
                "autoaccept",
                required_tag="branch:item-acquired",
            )

        self.assertIsNotNone(binding)
        assert binding is not None
        self.assertEqual(binding.quest_id, "quest-hib-item")
        self.assertEqual(binding.start_position, matrix.StartPosition(200, 292411, 458413, 6630))
        self.assertEqual(fetch_quests.call_count, 2)
        fetch_seed.assert_called_once()
        sleep.assert_called_once()

    def test_fetch_live_quest_binding_does_not_wait_after_seed_finished(self) -> None:
        args = matrix.parse_args(["--matrix", "realm-smoke", "--realms", "hib", "--quest-start-mode", "autoaccept"])
        case = matrix.build_cases(args)[0]

        with (
            mock.patch.object(matrix, "fetch_live_dynamic_quests", return_value={"quests": []}) as fetch_quests,
            mock.patch.object(matrix, "fetch_dynamic_quest_seed_status", return_value={"messages": ["seed complete"]}) as fetch_seed,
            mock.patch.object(matrix.time, "monotonic", side_effect=[0.0, 0.0]),
            mock.patch.object(matrix.time, "sleep") as sleep,
        ):
            binding = matrix.fetch_live_quest_binding_with_seed_wait(
                args,
                case,
                "autoaccept",
                required_tag="branch:item-acquired",
            )

        self.assertIsNone(binding)
        fetch_quests.assert_called_once()
        fetch_seed.assert_called_once()
        sleep.assert_not_called()

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

    def test_bind_case_to_live_quest_forwards_kill_objective_home_to_dummy(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--max-target-distance", "6500"])
        case = matrix.build_cases(args)[0]
        binding = matrix.LiveQuestBinding(
            seed_npc="Bowman Commander",
            target="black wolf pup",
            min_target_level=1,
            max_target_level=1,
            start_npc_internal_id="selector-start-1",
            start_position=matrix.StartPosition(region=1, x=518850, y=494050, z=3352),
            target_position=matrix.StartPosition(region=1, x=509819, y=492466, z=2763),
            target_radius=6500,
        )

        bound_case, _ = matrix.bind_case_to_live_quest(case, binding)
        command = matrix.build_behavior_command(bound_case, args)

        self.assertIn("--required-target-home", command)
        self.assertEqual(command[command.index("--required-target-home") + 1], "509819,492466,2763")
        self.assertEqual(command[command.index("--target-home-max-distance") + 1], "6500")
        self.assertEqual(command[command.index("--required-target-home-hunt-distance") + 1], "6500")

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

    def test_cleanup_active_dynamic_quest_progress_cancels_active_player_records(self) -> None:
        args = matrix.parse_args(["--matrix", "quick"])

        with (
            mock.patch.object(
                matrix,
                "fetch_dynamic_quest_player_api",
                return_value={"active": [{"player": "DqIhb002", "questId": "quest-1"}]},
            ) as fetch,
            mock.patch.object(matrix, "cancel_dynamic_quest_progress", return_value={"cancelled": 1}) as cancel,
        ):
            results = matrix.cleanup_active_dynamic_quest_progress_for_accounts(
                args,
                ["dqihb002"],
                reason="unit-test-cleanup",
            )

        fetch.assert_called_once_with(args, "progress", "dqihb002")
        cancel.assert_called_once_with(args, "DqIhb002", "unit-test-cleanup")
        self.assertEqual(results, [{"account": "dqihb002", "player": "DqIhb002", "questId": "quest-1", "cancelled": 1}])

    def test_autoaccept_live_binding_clamps_overleveled_player_to_offer_range(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--player-level", "5"])
        case = matrix.build_cases(args)[0]
        binding = matrix.LiveQuestBinding(
            seed_npc="",
            target="young lynx",
            min_target_level=2,
            max_target_level=2,
            min_player_level=2,
            max_player_level=2,
            start_position=matrix.StartPosition(region=100, x=797022, y=725025, z=4684),
        )

        bound_case, _ = matrix.bind_case_to_live_quest(
            case,
            binding,
            preserve_overlevel=matrix.should_preserve_live_quest_overlevel("autoaccept", args),
        )

        self.assertEqual(bound_case.player_level, 2)

    def test_mob_growth_live_binding_allows_requested_overleveled_player_level(self) -> None:
        args = matrix.parse_args(["--matrix", "quick", "--player-level", "10"])
        case = matrix.build_cases(args)[0]
        binding = matrix.LiveQuestBinding(
            seed_npc="",
            target="ant drone",
            min_target_level=2,
            max_target_level=2,
            min_player_level=2,
            max_player_level=2,
            start_position=matrix.StartPosition(region=1, x=518296, y=629644, z=1765),
            tags=("branch:mob-growth", "world-signal:mob-growth:killed:region:1"),
        )

        bound_case, _ = matrix.bind_case_to_live_quest(
            case,
            binding,
            preserve_overlevel=matrix.live_quest_binding_allows_overlevel(binding),
        )

        self.assertEqual(bound_case.player_level, 10)

    def test_mob_growth_followup_falls_back_to_live_binding_when_summary_api_unavailable(self) -> None:
        args = matrix.parse_args([
            "--matrix",
            "quick",
            "--quest-start-mode",
            "autoaccept",
            "--dynamic-quest-followup-growth-target",
            "--require-quest-tag",
            "branch:mob-growth",
            "--require-world-signal",
            "mob-growth:killed:region:1",
        ])
        case = matrix.build_cases(args)[0]
        binding = matrix.LiveQuestBinding(
            seed_npc="",
            target="ant drone",
            min_target_level=2,
            max_target_level=2,
            min_player_level=2,
            max_player_level=2,
            start_position=matrix.StartPosition(region=1, x=518296, y=629644, z=1765),
            target_position=matrix.StartPosition(region=1, x=519000, y=630000, z=1800),
            tags=("branch:mob-growth", "world-signal:mob-growth:killed:region:1"),
        )

        with (
            mock.patch.object(matrix, "fetch_live_quest_binding_with_seed_wait", return_value=binding),
            mock.patch.object(matrix, "fetch_mob_growth_summary", side_effect=RuntimeError("summary unavailable")),
        ):
            bound_case, _ = matrix.resolve_live_case(case, args)

        self.assertEqual(bound_case.followup_target, "ant drone")
        self.assertEqual(bound_case.followup_home, (519000, 630000, 1800))
        self.assertEqual(bound_case.followup_min_target_level, 2)
        self.assertEqual(bound_case.followup_max_target_level, 2)

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
                        "action_dynamic_quest_timeline_choice_selected",
                        "action_dynamic_quest_timeline_world_signal",
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_world_impact",
                        "action_dynamic_quest_timeline_world_impact_summary",
                        "action_dynamic_quest_timeline_narrative_scene",
                        "action_dynamic_quest_timeline_cinematic_action",
                        "action_dynamic_quest_timeline_cinematic_actor_instances",
                        "action_dynamic_quest_timeline_cinematic_actor_peak",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_summary",
                        "action_dynamic_quest_timeline_cinematic_cleanup",
                        "action_dynamic_quest_timeline_scene_director_beat",
                        "action_dynamic_quest_timeline_scene_beat_outcome",
                        "action_dynamic_quest_timeline_scene_world_signal",
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
                        "action_dynamic_quest_timeline_choice_selected": "1",
                        "action_dynamic_quest_timeline_world_signal": "1",
                        "action_dynamic_quest_timeline_presentation_beat": "1",
                        "action_dynamic_quest_timeline_world_impact": "1",
                        "action_dynamic_quest_timeline_world_impact_summary": "1",
                        "action_dynamic_quest_timeline_narrative_scene": "1",
                        "action_dynamic_quest_timeline_cinematic_action": "1",
                        "action_dynamic_quest_timeline_scene_director_beat": "0",
                        "action_dynamic_quest_timeline_scene_beat_outcome": "0",
                        "action_dynamic_quest_timeline_scene_world_signal": "0",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.players, 1)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.reward_observed, 1)
        self.assertEqual(summary.target_removed, 1)
        self.assertEqual(summary.player_deaths, 0)
        self.assertEqual(summary.cinematic_density_score, 75)
        self.assertEqual(summary.skyrim_grade_score, 100)
        self.assertEqual(summary.evaluation_score, 100)

    def test_summarize_case_counts_pending_target_removed_when_completion_confirmed(self) -> None:
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
                        "action_target_removed_pending_confirmation",
                        "action_required_target_complete_exit",
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
                        "elapsed_seconds": "72.3",
                        "action_target_removed_pending_confirmation": "1",
                        "action_required_target_complete_exit": "1",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_reward_observed": "1",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.reward_observed, 1)
        self.assertEqual(summary.target_removed, 1)

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
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_world_impact",
                        "action_dynamic_quest_timeline_world_impact_summary",
                        "action_dynamic_quest_timeline_narrative_scene",
                        "action_dynamic_quest_timeline_cinematic_action",
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
                        "action_dynamic_quest_timeline_presentation_beat": "1",
                        "action_dynamic_quest_timeline_world_impact": "1",
                        "action_dynamic_quest_timeline_world_impact_summary": "1",
                        "action_dynamic_quest_timeline_narrative_scene": "1",
                        "action_dynamic_quest_timeline_cinematic_action": "1",
                        "action_dynamic_quest_followup_hunt_start": "0",
                    }
                )

            summary = matrix.summarize_case(case_dir, require_followup_hunt=True)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.choice_selected, 1)
        self.assertEqual(summary.world_signal, 1)
        self.assertEqual(summary.followup_hunt_start, 0)
        self.assertGreaterEqual(summary.evaluation_score, 70)

    def test_summarize_case_scores_story_core_independent_of_player_death(self) -> None:
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
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_world_impact",
                        "action_dynamic_quest_timeline_world_impact_summary",
                        "action_dynamic_quest_timeline_narrative_scene",
                        "action_dynamic_quest_timeline_cinematic_action",
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
                        "action_dynamic_quest_reward_observed": "1",
                        "action_dynamic_quest_timeline_choice_selected": "1",
                        "action_dynamic_quest_timeline_world_signal": "1",
                        "action_dynamic_quest_timeline_presentation_beat": "1",
                        "action_dynamic_quest_timeline_world_impact": "1",
                        "action_dynamic_quest_timeline_world_impact_summary": "1",
                        "action_dynamic_quest_timeline_narrative_scene": "1",
                        "action_dynamic_quest_timeline_cinematic_action": "1",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertTrue(summary.passed)
        self.assertEqual(summary.completed, 1)
        self.assertEqual(summary.ok_players, 1)
        self.assertEqual(summary.player_deaths, 1)
        self.assertEqual(summary.cinematic_density_score, 75)
        self.assertEqual(summary.skyrim_grade_score, 100)
        self.assertEqual(summary.evaluation_score, 100)
        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])
        self.assertEqual(operational["passed"], True)
        self.assertLess(operational["difficultyScore"], 100)
        self.assertIn("dummy death observed; kept out of story score and treated as difficulty signal only", operational["warnings"])

    def test_branch_expected_summary_penalizes_missing_choice_and_world_signal(self) -> None:
        case = matrix.replace(
            matrix.build_cases(matrix.parse_args([]))[0],
            tags=("branch:time-window", "world-signal:time-window"),
        )
        summary = matrix.CaseSummary(
            players=1,
            ok_players=1,
            completed=1,
            reward_observed=1,
            target_removed=1,
            player_deaths=0,
            choice_selected=0,
            world_signal=0,
            presentation_beat=8,
            world_impact=1,
            world_impact_summary=1,
            narrative_scene=5,
            cinematic_action=12,
            scene_director_beat=4,
            scene_beat_outcome=4,
            scene_actor_exchange=1,
            scene_exchange_outcome=1,
            scene_consequence=1,
            cinematic_cleanup=1,
            passed=True,
        )

        evaluated = matrix.ensure_case_story_archetype_score(summary, case)
        operational = matrix.calculate_dummy_operational_evaluation(evaluated, case)

        self.assertLess(evaluated.story_continuity_score, 70)
        self.assertIn("branch quest completed without an observed player choice", operational["warnings"])
        self.assertIn("world-signal branch completed without an observed world signal", operational["warnings"])

    def test_summarize_case_penalizes_skewed_party_scene_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            fieldnames = [
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
                "action_dynamic_quest_timeline_presentation_beat",
                "action_dynamic_quest_timeline_world_impact",
                "action_dynamic_quest_timeline_world_impact_summary",
                "action_dynamic_quest_timeline_narrative_scene",
                "action_dynamic_quest_timeline_cinematic_action",
                "action_dynamic_quest_timeline_scene_director_beat",
                "action_dynamic_quest_timeline_scene_beat_outcome",
                "action_dynamic_quest_timeline_scene_world_signal",
                "action_dynamic_quest_timeline_cinematic_cleanup",
            ]
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "elapsed_seconds": "120",
                        "action_dynamic_quest_complete_verified": "1",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_reward_observed": "1",
                        "action_dynamic_quest_timeline_choice_selected": "1",
                        "action_dynamic_quest_timeline_world_signal": "1",
                        "action_dynamic_quest_timeline_presentation_beat": "12",
                        "action_dynamic_quest_timeline_world_impact": "1",
                        "action_dynamic_quest_timeline_world_impact_summary": "1",
                        "action_dynamic_quest_timeline_narrative_scene": "8",
                        "action_dynamic_quest_timeline_cinematic_action": "24",
                        "action_dynamic_quest_timeline_scene_director_beat": "12",
                        "action_dynamic_quest_timeline_scene_beat_outcome": "12",
                        "action_dynamic_quest_timeline_scene_world_signal": "12",
                        "action_dynamic_quest_timeline_cinematic_cleanup": "1",
                    }
                )
                writer.writerow(
                    {
                        "username": "dq002",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "elapsed_seconds": "120",
                        "action_dynamic_quest_complete_verified": "1",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_reward_observed": "1",
                        "action_dynamic_quest_timeline_choice_selected": "1",
                        "action_dynamic_quest_timeline_world_signal": "1",
                        "action_dynamic_quest_timeline_presentation_beat": "0",
                        "action_dynamic_quest_timeline_world_impact": "1",
                        "action_dynamic_quest_timeline_world_impact_summary": "1",
                        "action_dynamic_quest_timeline_narrative_scene": "0",
                        "action_dynamic_quest_timeline_cinematic_action": "0",
                        "action_dynamic_quest_timeline_scene_director_beat": "0",
                        "action_dynamic_quest_timeline_scene_beat_outcome": "0",
                        "action_dynamic_quest_timeline_scene_world_signal": "0",
                        "action_dynamic_quest_timeline_cinematic_cleanup": "1",
                    }
                )

            summary = matrix.summarize_case(case_dir)
            operational = matrix.calculate_dummy_operational_evaluation(
                summary,
                matrix.build_cases(matrix.parse_args([]))[0],
            )

        self.assertTrue(summary.passed)
        self.assertEqual(summary.min_narrative_scene_per_player, 0)
        self.assertEqual(summary.min_presentation_beat_per_player, 0)
        self.assertEqual(summary.min_cinematic_action_per_player, 0)
        self.assertLess(summary.skyrim_grade_score, 100)
        self.assertIn("party quest narrative coverage is thin per player", operational["warnings"])
        self.assertIn("party quest presentation coverage is thin per player", operational["warnings"])
        self.assertIn("party quest cinematic coverage is thin per player", operational["warnings"])

    def test_summarize_case_counts_cinematic_actor_spawn_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            fieldnames = [
                "username",
                "ok",
                "target_removed",
                "player_deaths",
                "elapsed_seconds",
                "action_dynamic_quest_final_inactive",
                "action_dynamic_quest_reward_observed",
                "action_dynamic_quest_timeline_presentation_beat",
                "action_dynamic_quest_timeline_cinematic_action",
                "action_dynamic_quest_timeline_scene_director_beat",
                "action_dynamic_quest_timeline_scene_beat_outcome",
                "action_dynamic_quest_timeline_scene_world_signal",
                "action_dynamic_quest_timeline_cinematic_actor_instances",
                "action_dynamic_quest_timeline_cinematic_actor_peak",
                "action_dynamic_quest_timeline_cinematic_actor_spawn_summary",
                "action_dynamic_quest_timeline_cinematic_actor_spawned_total",
                "action_dynamic_quest_timeline_cinematic_actor_spawned_peak",
                "action_dynamic_quest_timeline_cinematic_actor_spawn_failed",
                "action_dynamic_quest_timeline_cinematic_actor_cleanup_scheduled",
                "action_dynamic_quest_timeline_cinematic_actor_motion_summary",
                "action_dynamic_quest_timeline_cinematic_actor_motion_commands",
                "action_dynamic_quest_timeline_cinematic_actor_motion_commands_peak",
                "action_dynamic_quest_timeline_cinematic_actor_motion_commands_per_actor_peak",
                "action_dynamic_quest_timeline_cinematic_actor_motion_spawned_total",
                "action_dynamic_quest_timeline_cinematic_actor_engagement_summary",
                "action_dynamic_quest_timeline_cinematic_actor_engagement_pairs",
                "action_dynamic_quest_timeline_cinematic_actor_engagement_pairs_peak",
                "action_dynamic_quest_timeline_cinematic_actor_engaged_total",
                "action_dynamic_quest_timeline_cinematic_actor_engagement_spawned_total",
            ]
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "dq001",
                        "ok": "true",
                        "target_removed": "1",
                        "player_deaths": "0",
                        "elapsed_seconds": "120",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_reward_observed": "1",
                        "action_dynamic_quest_timeline_presentation_beat": "8",
                        "action_dynamic_quest_timeline_cinematic_action": "20",
                        "action_dynamic_quest_timeline_scene_director_beat": "8",
                        "action_dynamic_quest_timeline_scene_beat_outcome": "8",
                        "action_dynamic_quest_timeline_scene_world_signal": "8",
                        "action_dynamic_quest_timeline_cinematic_actor_instances": "140",
                        "action_dynamic_quest_timeline_cinematic_actor_peak": "100",
                        "action_dynamic_quest_timeline_cinematic_actor_spawn_summary": "3",
                        "action_dynamic_quest_timeline_cinematic_actor_spawned_total": "140",
                        "action_dynamic_quest_timeline_cinematic_actor_spawned_peak": "100",
                        "action_dynamic_quest_timeline_cinematic_actor_spawn_failed": "0",
                        "action_dynamic_quest_timeline_cinematic_actor_cleanup_scheduled": "140",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_summary": "3",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_commands": "420",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_commands_peak": "300",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_commands_per_actor_peak": "3",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_spawned_total": "140",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_summary": "3",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_pairs": "70",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_pairs_peak": "50",
                        "action_dynamic_quest_timeline_cinematic_actor_engaged_total": "140",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_spawned_total": "140",
                    }
                )

            summary = matrix.summarize_case(case_dir)

        self.assertEqual(summary.cinematic_actor_spawn_summary, 3)
        self.assertEqual(summary.cinematic_actor_spawned_total, 140)
        self.assertEqual(summary.cinematic_actor_spawned_peak, 100)
        self.assertEqual(summary.cinematic_actor_spawn_failed, 0)
        self.assertEqual(summary.cinematic_actor_cleanup_scheduled, 140)
        self.assertEqual(summary.cinematic_actor_motion_summary, 3)
        self.assertEqual(summary.cinematic_actor_motion_commands, 420)
        self.assertEqual(summary.cinematic_actor_motion_commands_peak, 300)
        self.assertEqual(summary.cinematic_actor_motion_commands_per_actor_peak, 3)
        self.assertEqual(summary.cinematic_actor_motion_spawned_total, 140)
        self.assertEqual(summary.cinematic_actor_engagement_summary, 3)
        self.assertEqual(summary.cinematic_actor_engagement_pairs, 70)
        self.assertEqual(summary.cinematic_actor_engagement_pairs_peak, 50)
        self.assertEqual(summary.cinematic_actor_engaged_total, 140)
        self.assertEqual(summary.cinematic_actor_engagement_spawned_total, 140)
        self.assertEqual(summary.cinematic_actor_budget_score, 99)
        self.assertTrue(
            matrix.effective_case_passed(
                summary,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
            )
        )

    def test_calculate_dummy_operational_evaluation_warns_on_low_cinematic_density(self) -> None:
        summary = matrix.CaseSummary(
            players=1,
            ok_players=1,
            completed=1,
            reward_observed=1,
            target_removed=1,
            player_deaths=0,
            choice_selected=1,
            world_signal=0,
            presentation_beat=1,
            world_impact=0,
            world_impact_summary=0,
            narrative_scene=1,
            cinematic_action=1,
            scene_director_beat=0,
            scene_beat_outcome=0,
            scene_world_signal=0,
            cinematic_cleanup=0,
            followup_hunt_start=0,
            elapsed_seconds=90.0,
            passed=True,
            evaluation_score=90,
            skyrim_grade_score=90,
            cinematic_density_score=45,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("cinematic density is below Skyrim-grade threshold", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_missing_presentation_staging(self) -> None:
        summary = matrix.CaseSummary(
            players=1,
            ok_players=1,
            completed=1,
            reward_observed=1,
            target_removed=1,
            player_deaths=0,
            choice_selected=1,
            world_signal=1,
            presentation_beat=6,
            world_impact=1,
            world_impact_summary=1,
            narrative_scene=4,
            cinematic_action=12,
            scene_director_beat=4,
            scene_beat_outcome=4,
            scene_choreography_phase=4,
            scene_actor_exchange=4,
            scene_exchange_outcome=4,
            scene_outcome_signal=4,
            scene_consequence=4,
            cinematic_cleanup=1,
            elapsed_seconds=90.0,
            passed=True,
            evaluation_score=95,
            skyrim_grade_score=95,
            cinematic_density_score=95,
            presentation_speaker_variety=3,
            presentation_staged_beat=0,
            presentation_staged_action_variety=0,
            presentation_staged_role_variety=0,
            cinematic_variety=4,
            cinematic_motion_variety=4,
            cinematic_staggered_scene=4,
            cinematic_objective_focal_scene=4,
            cinematic_actor_role_variety=4,
            cinematic_choreographed_scene=4,
            cinematic_interaction_scene=4,
            cinematic_tactic_variety=4,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("presentation beats lack staged action metadata", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_low_action_scene_cohesion(self) -> None:
        summary = matrix.finalize_case_summary_scores(
            matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=6,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=4,
                cinematic_action=12,
                scene_director_beat=4,
                scene_beat_outcome=4,
                scene_world_signal=1,
                cinematic_cleanup=1,
                elapsed_seconds=90.0,
                passed=True,
                cinematic_variety=4,
                cinematic_motion_variety=1,
                cinematic_actor_role_variety=1,
                cinematic_tactic_variety=1,
            )
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertLess(summary.action_scene_cohesion_score, 70)
        self.assertLess(summary.skyrim_grade_score, 100)
        self.assertIn("action scene cohesion is below Skyrim-grade threshold", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_uses_engagement_spawned_total_for_coverage(self) -> None:
        summary = matrix.finalize_case_summary_scores(
            matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=14,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=5,
                cinematic_action=67,
                scene_director_beat=28,
                scene_beat_outcome=24,
                scene_choreography_phase=48,
                scene_actor_exchange=20,
                scene_exchange_outcome=20,
                scene_outcome_signal=20,
                scene_consequence=14,
                scene_world_signal=44,
                cinematic_cleanup=3,
                elapsed_seconds=90.0,
                passed=True,
                evaluation_score=100,
                skyrim_grade_score=100,
                cinematic_density_score=100,
                story_continuity_score=100,
                story_archetype_score=100,
                presentation_speaker_variety=2,
                presentation_staged_beat=11,
                presentation_staged_action_variety=9,
                presentation_staged_role_variety=11,
                cinematic_variety=10,
                cinematic_motion_variety=10,
                cinematic_staggered_scene=28,
                cinematic_objective_focal_scene=11,
                cinematic_actor_role_variety=6,
                cinematic_choreographed_scene=28,
                cinematic_interaction_scene=28,
                cinematic_tactic_variety=6,
                cinematic_actor_instances=972,
                cinematic_actor_peak=100,
                cinematic_actor_spawn_summary=38,
                cinematic_actor_spawned_total=972,
                cinematic_actor_spawned_peak=100,
                cinematic_actor_spawn_failed=0,
                cinematic_actor_cleanup_scheduled=972,
                cinematic_actor_motion_summary=38,
                cinematic_actor_motion_commands=2916,
                cinematic_actor_engagement_summary=34,
                cinematic_actor_engaged_total=896,
                cinematic_actor_engagement_spawned_total=896,
            )
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertEqual(matrix.cinematic_actor_engagement_expected_total(summary), 896)
        self.assertNotIn("cinematic actor engagement coverage is low", operational["warnings"])
        self.assertEqual(summary.cinematic_actor_budget_score, 100)

    def test_calculate_dummy_operational_evaluation_warns_on_low_story_continuity(self) -> None:
        summary = matrix.finalize_case_summary_scores(
            matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=6,
                world_impact=1,
                world_impact_summary=0,
                narrative_scene=4,
                cinematic_action=12,
                scene_director_beat=4,
                scene_beat_outcome=4,
                scene_world_signal=1,
                cinematic_cleanup=1,
                followup_hunt_start=0,
                elapsed_seconds=90.0,
                passed=True,
                choice_outcome_scene=0,
                scene_exchange_outcome=1,
                scene_consequence=0,
                world_signal_scene_shift=0,
                cinematic_variety=4,
                cinematic_motion_variety=4,
                cinematic_staggered_scene=2,
                cinematic_objective_focal_scene=2,
                cinematic_actor_role_variety=4,
                cinematic_choreographed_scene=2,
                cinematic_interaction_scene=2,
                cinematic_tactic_variety=4,
            )
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertLess(summary.story_continuity_score, 70)
        self.assertIn("story continuity is below Skyrim-grade threshold", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_thin_party_scene_coverage(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=2,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=2,
            cinematic_action=2,
            scene_director_beat=3,
            scene_beat_outcome=3,
            scene_world_signal=3,
            cinematic_cleanup=3,
            followup_hunt_start=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            story_continuity_score=100,
            story_archetype_score=100,
            cinematic_variety=4,
            cinematic_motion_variety=4,
            cinematic_staggered_scene=3,
            cinematic_objective_focal_scene=3,
            cinematic_actor_role_variety=4,
            cinematic_choreographed_scene=3,
            cinematic_interaction_scene=3,
            cinematic_tactic_variety=4,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("party quest narrative coverage is thin per player", operational["warnings"])
        self.assertIn("party quest presentation coverage is thin per player", operational["warnings"])
        self.assertIn("party quest cinematic coverage is thin per player", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_low_cinematic_variety(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=12,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=9,
            cinematic_action=30,
            scene_director_beat=12,
            scene_beat_outcome=12,
            scene_world_signal=12,
            cinematic_cleanup=3,
            followup_hunt_start=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            cinematic_variety=1,
            cinematic_motion_variety=3,
            cinematic_staggered_scene=6,
            cinematic_objective_focal_scene=6,
            cinematic_actor_role_variety=3,
            cinematic_choreographed_scene=6,
            cinematic_interaction_scene=6,
            cinematic_tactic_variety=3,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("cinematic scene variety is low despite staged scene beats", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_low_motion_variety_and_no_stagger(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=12,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=9,
            cinematic_action=30,
            scene_director_beat=12,
            scene_beat_outcome=12,
            scene_world_signal=12,
            cinematic_cleanup=3,
            followup_hunt_start=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            cinematic_variety=4,
            cinematic_motion_variety=1,
            cinematic_staggered_scene=0,
            cinematic_objective_focal_scene=6,
            cinematic_actor_role_variety=3,
            cinematic_choreographed_scene=6,
            cinematic_interaction_scene=6,
            cinematic_tactic_variety=3,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("cinematic motion variety is low despite staged scene beats", operational["warnings"])
        self.assertIn("staged scene beats did not use actor stagger timing", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_missing_objective_focal_scene(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=12,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=9,
            cinematic_action=30,
            scene_director_beat=12,
            scene_beat_outcome=12,
            scene_world_signal=12,
            cinematic_cleanup=3,
            followup_hunt_start=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            cinematic_variety=4,
            cinematic_motion_variety=4,
            cinematic_staggered_scene=6,
            cinematic_objective_focal_scene=0,
            cinematic_actor_role_variety=3,
            cinematic_choreographed_scene=6,
            cinematic_interaction_scene=6,
            cinematic_tactic_variety=3,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("staged scene beats did not use an objective focal point", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_low_actor_role_variety(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=12,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=9,
            cinematic_action=30,
            scene_director_beat=12,
            scene_beat_outcome=12,
            scene_world_signal=12,
            cinematic_cleanup=3,
            followup_hunt_start=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            cinematic_variety=4,
            cinematic_motion_variety=4,
            cinematic_staggered_scene=6,
            cinematic_objective_focal_scene=6,
            cinematic_actor_role_variety=1,
            cinematic_choreographed_scene=6,
            cinematic_interaction_scene=6,
            cinematic_tactic_variety=3,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("staged scene beats did not use varied actor roles", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_missing_choreography(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=12,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=9,
            cinematic_action=30,
            scene_director_beat=12,
            scene_beat_outcome=12,
            scene_world_signal=12,
            cinematic_cleanup=3,
            followup_hunt_start=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            cinematic_variety=4,
            cinematic_motion_variety=4,
            cinematic_staggered_scene=6,
            cinematic_objective_focal_scene=6,
            cinematic_actor_role_variety=4,
            cinematic_choreographed_scene=0,
            cinematic_interaction_scene=6,
            cinematic_tactic_variety=3,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("staged scene beats did not use multi-phase actor choreography", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_missing_actor_interaction(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=12,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=9,
            cinematic_action=30,
            scene_director_beat=12,
            scene_beat_outcome=12,
            scene_world_signal=12,
            cinematic_cleanup=3,
            followup_hunt_start=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            cinematic_variety=4,
            cinematic_motion_variety=4,
            cinematic_staggered_scene=6,
            cinematic_objective_focal_scene=6,
            cinematic_actor_role_variety=4,
            cinematic_choreographed_scene=6,
            cinematic_interaction_scene=0,
            cinematic_tactic_variety=3,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("staged scene beats did not use actor interaction choreography", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_on_low_tactic_variety(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=12,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=9,
            cinematic_action=30,
            scene_director_beat=12,
            scene_beat_outcome=12,
            scene_world_signal=12,
            cinematic_cleanup=3,
            followup_hunt_start=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            cinematic_variety=4,
            cinematic_motion_variety=4,
            cinematic_staggered_scene=6,
            cinematic_objective_focal_scene=6,
            cinematic_actor_role_variety=4,
            cinematic_choreographed_scene=6,
            cinematic_interaction_scene=6,
            cinematic_tactic_variety=1,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("staged scene beats did not use varied tactical roles", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_warns_when_completed_without_world_impact_summary(self) -> None:
        summary = matrix.CaseSummary(
            players=1,
            ok_players=1,
            completed=1,
            reward_observed=1,
            target_removed=1,
            player_deaths=0,
            choice_selected=1,
            world_signal=1,
            presentation_beat=4,
            world_impact=1,
            world_impact_summary=0,
            narrative_scene=3,
            cinematic_action=8,
            scene_director_beat=4,
            scene_beat_outcome=4,
            scene_world_signal=4,
            cinematic_cleanup=1,
            followup_hunt_start=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            cinematic_variety=3,
            cinematic_motion_variety=3,
            cinematic_staggered_scene=3,
            cinematic_objective_focal_scene=3,
            cinematic_actor_role_variety=3,
            cinematic_choreographed_scene=3,
            cinematic_interaction_scene=3,
            cinematic_tactic_variety=3,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("completed quest did not leave a world impact summary", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_calculate_dummy_operational_evaluation_allows_high_density_when_budget_and_cleanup_are_verified(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=42,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=15,
            cinematic_action=246,
            scene_director_beat=135,
            scene_beat_outcome=135,
            scene_choreography_phase=186,
            scene_actor_exchange=90,
            scene_exchange_outcome=90,
            scene_outcome_signal=90,
            scene_consequence=90,
            scene_world_signal=90,
            world_signal_scene_shift=12,
            cinematic_cleanup=3,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            kill_confirmed=3,
            choice_outcome_scene=3,
            choice_consequence=3,
            world_memory_marked=3,
            cinematic_variety=10,
            cinematic_motion_variety=10,
            cinematic_staggered_scene=20,
            cinematic_objective_focal_scene=20,
            cinematic_actor_role_variety=6,
            cinematic_choreographed_scene=20,
            cinematic_interaction_scene=20,
            cinematic_tactic_variety=6,
            story_continuity_score=100,
            story_archetype_score=100,
            cinematic_actor_instances=7284,
            cinematic_actor_peak=100,
            cinematic_actor_budget_score=100,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertNotIn("cinematic action density is very high; verify actor budget and cleanup", operational["warnings"])
        self.assertEqual(operational["varietyScore"], 100)

    def test_skyrim_grade_caps_when_action_scene_has_no_observed_outcome_closure(self) -> None:
        summary = matrix.finalize_case_summary_scores(
            matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=12,
                presentation_speaker_variety=3,
                presentation_staged_beat=8,
                presentation_staged_action_variety=4,
                presentation_staged_role_variety=4,
                presentation_staged_formation_variety=2,
                presentation_staged_delayed_beat=4,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=8,
                cinematic_action=48,
                scene_director_beat=12,
                scene_beat_outcome=12,
                scene_choreography_phase=12,
                scene_actor_exchange=8,
                scene_exchange_outcome=8,
                scene_outcome_signal=0,
                scene_consequence=0,
                scene_world_signal=8,
                world_signal_scene_shift=3,
                world_signal_scene_shift_detail=3,
                world_signal_scene_shift_phase_variety=3,
                cinematic_cleanup=1,
                passed=True,
                choice_outcome_scene=1,
                cinematic_variety=6,
                cinematic_motion_variety=6,
                cinematic_staggered_scene=6,
                cinematic_objective_focal_scene=6,
                cinematic_actor_role_variety=5,
                cinematic_choreographed_scene=6,
                cinematic_interaction_scene=6,
                cinematic_tactic_variety=5,
                cinematic_marker_scene=4,
                cinematic_marker_variety=4,
                cinematic_phase_coverage=3,
                cinematic_setpiece_phase_coverage=3,
                cinematic_marker_phase_coverage=3,
                cinematic_story_chain=3,
                cinematic_catalog_role_variety=5,
            )
        )

        self.assertEqual(summary.action_scene_cohesion_score, 100)
        self.assertLess(summary.skyrim_grade_score, 100)
        self.assertLessEqual(summary.skyrim_grade_score, 94)

    def test_skyrim_grade_caps_large_actor_scene_without_spawn_lifecycle_evidence(self) -> None:
        summary = matrix.finalize_case_summary_scores(
            matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=12,
                presentation_speaker_variety=3,
                presentation_staged_beat=8,
                presentation_staged_action_variety=4,
                presentation_staged_role_variety=4,
                presentation_staged_formation_variety=2,
                presentation_staged_delayed_beat=4,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=8,
                cinematic_action=80,
                scene_director_beat=12,
                scene_beat_outcome=12,
                scene_choreography_phase=12,
                scene_actor_exchange=8,
                scene_exchange_outcome=8,
                scene_outcome_signal=8,
                scene_consequence=8,
                scene_world_signal=8,
                world_signal_scene_shift=3,
                world_signal_scene_shift_detail=3,
                world_signal_scene_shift_phase_variety=3,
                cinematic_cleanup=0,
                passed=True,
                choice_outcome_scene=1,
                cinematic_variety=6,
                cinematic_motion_variety=6,
                cinematic_staggered_scene=6,
                cinematic_objective_focal_scene=6,
                cinematic_actor_role_variety=5,
                cinematic_choreographed_scene=6,
                cinematic_interaction_scene=6,
                cinematic_tactic_variety=5,
                cinematic_marker_scene=4,
                cinematic_marker_variety=4,
                cinematic_phase_coverage=3,
                cinematic_setpiece_phase_coverage=3,
                cinematic_marker_phase_coverage=3,
                cinematic_story_chain=3,
                cinematic_actor_instances=100,
                cinematic_actor_peak=100,
                cinematic_actor_spawn_summary=1,
                cinematic_actor_spawned_total=100,
                cinematic_actor_spawned_peak=100,
                cinematic_actor_cleanup_scheduled=0,
                cinematic_actor_motion_summary=0,
                cinematic_actor_engagement_summary=0,
                cinematic_catalog_role_variety=5,
            )
        )

        self.assertEqual(summary.action_scene_cohesion_score, 100)
        self.assertLess(summary.skyrim_grade_score, 100)
        self.assertLessEqual(summary.skyrim_grade_score, 89)

    def test_calculate_dummy_operational_evaluation_warns_on_actor_spawn_failure(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=24,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=12,
            cinematic_action=105,
            scene_director_beat=45,
            scene_beat_outcome=45,
            scene_choreography_phase=45,
            scene_actor_exchange=30,
            scene_exchange_outcome=30,
            scene_outcome_signal=30,
            scene_consequence=30,
            scene_world_signal=45,
            world_signal_scene_shift=6,
            cinematic_cleanup=3,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            kill_confirmed=3,
            choice_outcome_scene=3,
            cinematic_variety=8,
            cinematic_motion_variety=8,
            cinematic_staggered_scene=12,
            cinematic_objective_focal_scene=12,
            cinematic_actor_role_variety=5,
            cinematic_choreographed_scene=12,
            cinematic_interaction_scene=12,
            cinematic_tactic_variety=5,
            story_continuity_score=100,
            story_archetype_score=100,
            cinematic_actor_instances=300,
            cinematic_actor_peak=100,
            cinematic_actor_spawn_summary=3,
            cinematic_actor_spawned_total=285,
            cinematic_actor_spawned_peak=100,
            cinematic_actor_spawn_failed=15,
            cinematic_actor_cleanup_scheduled=285,
            cinematic_actor_budget_score=65,
            action_scene_cohesion_score=100,
            cinematic_catalog_role_variety=5,
            cinematic_model_role_fit_score=100,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertFalse(matrix.effective_case_passed(summary, minimum_action_scene_cohesion=70))
        self.assertIn("cinematic actor spawn failures were observed", operational["warnings"])
        self.assertLess(operational["varietyScore"], 100)

    def test_effective_case_passed_requires_actor_motion_summary_for_spawned_actors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            summary = matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=8,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=5,
                cinematic_action=20,
                scene_director_beat=8,
                scene_beat_outcome=8,
                scene_world_signal=8,
                cinematic_cleanup=1,
                elapsed_seconds=120.0,
                passed=True,
                cinematic_actor_instances=100,
                cinematic_actor_peak=100,
                cinematic_actor_spawn_summary=1,
                cinematic_actor_spawned_total=100,
                cinematic_actor_spawned_peak=100,
                cinematic_actor_spawn_failed=0,
                cinematic_actor_cleanup_scheduled=100,
                action_scene_cohesion_score=100,
                cinematic_catalog_role_variety=5,
                cinematic_model_role_fit_score=100,
            )

            failure_category = matrix.classify_case_failure(summary, case_dir)
            operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertFalse(matrix.effective_case_passed(summary))
        self.assertEqual(failure_category, "quest_quality")
        self.assertIn("spawned cinematic actors did not report motion choreography", operational["warnings"])

    def test_effective_case_passed_requires_engagement_summary_for_interaction_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            summary = matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=8,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=5,
                cinematic_action=20,
                scene_director_beat=8,
                scene_beat_outcome=8,
                scene_actor_exchange=8,
                scene_exchange_outcome=8,
                scene_world_signal=8,
                cinematic_cleanup=1,
                elapsed_seconds=120.0,
                passed=True,
                cinematic_interaction_scene=8,
                cinematic_actor_instances=100,
                cinematic_actor_peak=100,
                cinematic_actor_spawn_summary=1,
                cinematic_actor_spawned_total=100,
                cinematic_actor_spawned_peak=100,
                cinematic_actor_spawn_failed=0,
                cinematic_actor_cleanup_scheduled=100,
                cinematic_actor_motion_summary=1,
                cinematic_actor_motion_commands=300,
                cinematic_actor_motion_commands_peak=300,
                cinematic_actor_motion_commands_per_actor_peak=3,
                cinematic_actor_motion_spawned_total=100,
                action_scene_cohesion_score=100,
                cinematic_catalog_role_variety=5,
                cinematic_model_role_fit_score=100,
            )

            failure_category = matrix.classify_case_failure(summary, case_dir)
            operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertFalse(matrix.effective_case_passed(summary))
        self.assertEqual(failure_category, "quest_quality")
        self.assertIn("spawned cinematic actors did not report tactical engagement pairs", operational["warnings"])

    def test_effective_case_passed_requires_motion_spawned_total_to_cover_spawned_actors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            summary = matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=8,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=5,
                cinematic_action=20,
                scene_director_beat=8,
                scene_beat_outcome=8,
                scene_world_signal=8,
                cinematic_cleanup=1,
                elapsed_seconds=120.0,
                passed=True,
                cinematic_actor_instances=100,
                cinematic_actor_peak=100,
                cinematic_actor_spawn_summary=1,
                cinematic_actor_spawned_total=100,
                cinematic_actor_spawned_peak=100,
                cinematic_actor_spawn_failed=0,
                cinematic_actor_cleanup_scheduled=100,
                cinematic_actor_motion_summary=1,
                cinematic_actor_motion_commands=100,
                cinematic_actor_motion_spawned_total=40,
                action_scene_cohesion_score=100,
                cinematic_catalog_role_variety=5,
                cinematic_model_role_fit_score=100,
            )

            failure_category = matrix.classify_case_failure(summary, case_dir)

        self.assertFalse(matrix.effective_case_passed(summary))
        self.assertEqual(failure_category, "quest_quality")

    def test_effective_case_passed_requires_engagement_pairs_for_interaction_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            summary = matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=8,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=5,
                cinematic_action=20,
                scene_director_beat=8,
                scene_beat_outcome=8,
                scene_actor_exchange=8,
                scene_exchange_outcome=8,
                scene_world_signal=8,
                cinematic_cleanup=1,
                elapsed_seconds=120.0,
                passed=True,
                cinematic_interaction_scene=8,
                cinematic_actor_instances=100,
                cinematic_actor_peak=100,
                cinematic_actor_spawn_summary=1,
                cinematic_actor_spawned_total=100,
                cinematic_actor_spawned_peak=100,
                cinematic_actor_spawn_failed=0,
                cinematic_actor_cleanup_scheduled=100,
                cinematic_actor_motion_summary=1,
                cinematic_actor_motion_commands=300,
                cinematic_actor_motion_commands_peak=300,
                cinematic_actor_motion_commands_per_actor_peak=3,
                cinematic_actor_motion_spawned_total=100,
                cinematic_actor_engagement_summary=1,
                cinematic_actor_engagement_pairs=0,
                cinematic_actor_engaged_total=100,
                cinematic_actor_engagement_spawned_total=100,
                action_scene_cohesion_score=100,
                cinematic_catalog_role_variety=5,
                cinematic_model_role_fit_score=100,
            )

            failure_category = matrix.classify_case_failure(summary, case_dir)

        self.assertFalse(matrix.effective_case_passed(summary))
        self.assertEqual(failure_category, "quest_quality")

    def test_effective_case_passed_requires_actor_exchange_for_interaction_scenes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            summary = matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=8,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=5,
                cinematic_action=20,
                scene_director_beat=8,
                scene_beat_outcome=8,
                scene_actor_exchange=0,
                scene_exchange_outcome=0,
                scene_world_signal=8,
                cinematic_cleanup=1,
                elapsed_seconds=120.0,
                passed=True,
                cinematic_interaction_scene=8,
                cinematic_actor_instances=100,
                cinematic_actor_peak=100,
                cinematic_actor_spawn_summary=1,
                cinematic_actor_spawned_total=100,
                cinematic_actor_spawned_peak=100,
                cinematic_actor_spawn_failed=0,
                cinematic_actor_cleanup_scheduled=100,
                cinematic_actor_motion_summary=1,
                cinematic_actor_motion_commands=300,
                cinematic_actor_motion_commands_peak=300,
                cinematic_actor_motion_commands_per_actor_peak=3,
                cinematic_actor_motion_spawned_total=100,
                cinematic_actor_engagement_summary=1,
                cinematic_actor_engagement_pairs=50,
                cinematic_actor_engaged_total=100,
                cinematic_actor_engagement_spawned_total=100,
                action_scene_cohesion_score=100,
                cinematic_catalog_role_variety=5,
                cinematic_model_role_fit_score=100,
            )

            failure_category = matrix.classify_case_failure(summary, case_dir)

        self.assertFalse(matrix.effective_case_passed(summary))
        self.assertEqual(failure_category, "quest_quality")

    def test_calculate_dummy_operational_evaluation_warns_on_high_density_without_cleanup(self) -> None:
        summary = matrix.CaseSummary(
            players=3,
            ok_players=3,
            completed=3,
            reward_observed=3,
            target_removed=3,
            player_deaths=0,
            choice_selected=3,
            world_signal=3,
            presentation_beat=42,
            world_impact=3,
            world_impact_summary=3,
            narrative_scene=15,
            cinematic_action=246,
            scene_director_beat=135,
            scene_beat_outcome=135,
            scene_choreography_phase=186,
            scene_actor_exchange=90,
            scene_exchange_outcome=90,
            scene_outcome_signal=90,
            scene_consequence=90,
            scene_world_signal=90,
            world_signal_scene_shift=12,
            cinematic_cleanup=0,
            elapsed_seconds=120.0,
            passed=True,
            skyrim_grade_score=100,
            cinematic_density_score=100,
            kill_confirmed=3,
            choice_outcome_scene=3,
            cinematic_variety=10,
            cinematic_motion_variety=10,
            cinematic_staggered_scene=20,
            cinematic_objective_focal_scene=20,
            cinematic_actor_role_variety=6,
            cinematic_choreographed_scene=20,
            cinematic_interaction_scene=20,
            cinematic_tactic_variety=6,
            story_continuity_score=100,
            story_archetype_score=100,
            cinematic_actor_instances=7284,
            cinematic_actor_peak=100,
            cinematic_actor_budget_score=70,
        )

        operational = matrix.calculate_dummy_operational_evaluation(summary, matrix.build_cases(matrix.parse_args([]))[0])

        self.assertIn("cinematic action density is very high; verify actor budget and cleanup", operational["warnings"])
        self.assertIn("cinematic actions were observed without cinematic cleanup events", operational["warnings"])

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
        self.assertLess(required_summary.evaluation_score, 70)

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

    def test_summarize_case_counts_expected_active_node_as_passed_but_not_completed(self) -> None:
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
        self.assertEqual(summary.completed, 0)
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

    def test_summarize_case_does_not_count_completion_when_never_active(self) -> None:
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
        self.assertEqual(summary.completed, 0)

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

    def test_submit_evaluation_skips_setup_failure_without_posting(self) -> None:
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
                        "error",
                        "action_dynamic_quest_progress_api_error",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "midtest001",
                        "ok": "false",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "271.281",
                        "error": "dynamic quest progress check failed: HTTP Error 404: Not Found",
                        "action_dynamic_quest_progress_api_error": "1",
                    }
                )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                    "--dynamic-quest-min-action-scene-cohesion",
                    "0",
                    "--dynamic-quest-min-cinematic-catalog-role-variety",
                    "0",
                    "--dynamic-quest-min-cinematic-model-role-fit",
                    "0",
                ]
            )
            case = matrix.QuestCase(
                name="mid-p1",
                key="mid",
                realm="Midgard",
                region=100,
                seed_npc="Aud",
                target="young sveawolf",
                return_home=(773327, 749653, 4552),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                quest_id="seed-100-test",
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(
                case,
                summary,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
            )
            failure_category = matrix.classify_case_failure(
                summary,
                case_dir,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
            )

            with mock.patch.object(matrix.urllib.request, "urlopen") as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_not_called()
        self.assertEqual(failure_category, "infrastructure")
        self.assertIn("- failure_category: infrastructure", summary_text)
        self.assertTrue(payload["skipped"])
        self.assertEqual(payload["reason"], "infrastructure_or_setup_failure")
        self.assertEqual(payload["request"]["questId"], "seed-100-test")
        self.assertEqual(payload["request"]["failureCategory"], "infrastructure")

    def test_submit_evaluation_skips_infrastructure_failure_even_with_partial_observation(self) -> None:
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
                        "error",
                        "action_dynamic_quest_progress_api_error",
                        "action_dynamic_quest_reward_observed",
                        "action_dynamic_quest_timeline_presentation_beat",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "midtest001",
                        "ok": "true",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "120",
                        "error": "",
                        "action_dynamic_quest_progress_api_error": "0",
                        "action_dynamic_quest_reward_observed": "1",
                        "action_dynamic_quest_timeline_presentation_beat": "7",
                    }
                )
                writer.writerow(
                    {
                        "username": "midtest002",
                        "ok": "false",
                        "target_removed": "0",
                        "player_deaths": "1",
                        "elapsed_seconds": "300",
                        "error": "dynamic quest progress check failed: HTTP Error 404: Not Found",
                        "action_dynamic_quest_progress_api_error": "1",
                        "action_dynamic_quest_reward_observed": "0",
                        "action_dynamic_quest_timeline_presentation_beat": "0",
                    }
                )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                    "--dynamic-quest-min-action-scene-cohesion",
                    "0",
                    "--dynamic-quest-min-cinematic-catalog-role-variety",
                    "0",
                    "--dynamic-quest-min-cinematic-model-role-fit",
                    "0",
                ]
            )
            case = matrix.QuestCase(
                name="mid-p2",
                key="mid",
                realm="Midgard",
                region=100,
                seed_npc="Finn",
                target="soft-shelled crab",
                return_home=(773327, 749653, 4552),
                party_size=2,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                quest_id="seed-100-test",
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(case, summary)
            failure_category = matrix.classify_case_failure(summary, case_dir)

            with mock.patch.object(matrix.urllib.request, "urlopen") as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))

        urlopen.assert_not_called()
        self.assertEqual(failure_category, "infrastructure")
        self.assertTrue(payload["skipped"])
        self.assertEqual(payload["reason"], "infrastructure_or_setup_failure")
        self.assertEqual(payload["request"]["failureCategory"], "infrastructure")

    def test_submit_evaluation_posts_story_core_score_even_when_player_died(self) -> None:
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
                        "action_dynamic_quest_timeline_choice_selected",
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_world_impact",
                        "action_dynamic_quest_timeline_world_impact_summary",
                        "action_dynamic_quest_timeline_narrative_scene",
                        "action_dynamic_quest_timeline_cinematic_action",
                        "action_dynamic_quest_timeline_cinematic_actor_instances",
                        "action_dynamic_quest_timeline_cinematic_actor_peak",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_summary",
                        "action_dynamic_quest_timeline_cinematic_cleanup",
                        "action_dynamic_quest_timeline_scene_director_beat",
                        "action_dynamic_quest_timeline_scene_beat_outcome",
                        "action_dynamic_quest_timeline_scene_world_signal",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "albtest001",
                        "ok": "true",
                        "target_removed": "0",
                        "player_deaths": "1",
                        "elapsed_seconds": "359.828",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_reward_observed": "1",
                        "action_dynamic_quest_timeline_choice_selected": "1",
                        "action_dynamic_quest_timeline_presentation_beat": "12",
                        "action_dynamic_quest_timeline_world_impact": "1",
                        "action_dynamic_quest_timeline_world_impact_summary": "1",
                        "action_dynamic_quest_timeline_narrative_scene": "6",
                        "action_dynamic_quest_timeline_cinematic_action": "22",
                        "action_dynamic_quest_timeline_cinematic_actor_instances": "120",
                        "action_dynamic_quest_timeline_cinematic_actor_peak": "100",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_summary": "3",
                        "action_dynamic_quest_timeline_cinematic_cleanup": "1",
                        "action_dynamic_quest_timeline_scene_director_beat": "3",
                        "action_dynamic_quest_timeline_scene_beat_outcome": "3",
                        "action_dynamic_quest_timeline_scene_world_signal": "3",
                    }
                )
            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                    "--dynamic-quest-min-action-scene-cohesion",
                    "0",
                    "--dynamic-quest-min-cinematic-catalog-role-variety",
                    "0",
                    "--dynamic-quest-min-cinematic-model-role-fit",
                    "0",
                ]
            )
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Sir Lukas",
                target="black wolf pup",
                return_home=(518850, 494050, 3352),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=1,
                quest_id="seed-1-test",
                tags=(
                    "story-archetype:witness-conspiracy",
                    "story-arc:motive",
                    "story-arc:conflict",
                    "story-arc:reversal",
                    "story-arc:consequence",
                    "story-cinematic",
                    "scene-director",
                    "mass-cinematic",
                ),
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(
                case,
                summary,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
            )
            failure_category = matrix.classify_case_failure(
                summary,
                case_dir,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
            )

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertNotIn("skipped", payload)
        self.assertEqual(failure_category, "passed")
        self.assertIn("- failure_category: passed", summary_text)
        self.assertEqual(payload["request"]["questId"], "seed-1-test")
        self.assertEqual(payload["request"]["targetName"], "black wolf pup")
        self.assertEqual(payload["request"]["passed"], True)
        self.assertEqual(payload["request"]["score"], 100)
        self.assertEqual(payload["request"]["skyrimGradeScore"], 100)
        self.assertEqual(payload["request"]["cinematicDensityScore"], 100)
        self.assertEqual(payload["request"]["cinematicActorInstances"], 120)
        self.assertEqual(payload["request"]["cinematicActorPeak"], 100)
        self.assertEqual(payload["request"]["cinematicActorBudgetScore"], 100)
        self.assertEqual(payload["request"]["storyContinuityScore"], 77)
        self.assertEqual(payload["request"]["storyArchetypeScore"], 95)
        self.assertEqual(payload["request"]["sceneDirectorBeat"], 3)
        self.assertEqual(payload["request"]["sceneBeatOutcome"], 3)
        self.assertEqual(payload["request"]["sceneWorldSignal"], 3)
        self.assertIn("- cinematic_density_score: 100", summary_text)
        self.assertIn("- cinematic_actor_instances: 120", summary_text)
        self.assertIn("- cinematic_actor_peak: 100", summary_text)
        self.assertIn("- cinematic_actor_budget_score: 100", summary_text)
        self.assertIn("- story_continuity_score: 77", summary_text)
        self.assertIn("- story_archetype_score: 95", summary_text)
        self.assertIn("- scene_director_beat: 3", summary_text)
        self.assertIn("- scene_beat_outcome: 3", summary_text)
        self.assertIn("- scene_world_signal: 3", summary_text)
        self.assertIn("operationalEvaluation", payload["request"])
        self.assertGreaterEqual(payload["request"]["operationalEvaluation"]["totalScore"], 75)

    def test_submit_evaluation_marks_low_action_scene_cohesion_as_quality_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                    "--dynamic-quest-min-action-scene-cohesion",
                    "70",
                ]
            )
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Sir Lukas",
                target="black wolf pup",
                return_home=(518850, 494050, 3352),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=1,
                quest_id="seed-1-low-action-scene",
                tags=("story-cinematic", "scene-director", "story-archetype:witness-conspiracy"),
            )
            summary = matrix.finalize_case_summary_scores(
                matrix.CaseSummary(
                    players=1,
                    ok_players=1,
                    completed=1,
                    reward_observed=1,
                    target_removed=1,
                    player_deaths=0,
                    choice_selected=1,
                    world_signal=1,
                    presentation_beat=6,
                    world_impact=1,
                    world_impact_summary=1,
                    narrative_scene=4,
                    cinematic_action=12,
                    scene_director_beat=4,
                    scene_beat_outcome=4,
                    scene_world_signal=1,
                    cinematic_cleanup=1,
                    elapsed_seconds=90.0,
                    passed=True,
                    cinematic_variety=4,
                    cinematic_motion_variety=1,
                    cinematic_actor_role_variety=1,
                    cinematic_tactic_variety=1,
                )
            )
            summary = matrix.ensure_case_story_archetype_score(summary, case)
            matrix.write_case_summary(case, summary, minimum_action_scene_cohesion=70)
            failure_category = matrix.classify_case_failure(
                summary,
                case_dir,
                minimum_action_scene_cohesion=70,
            )

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertTrue(summary.passed)
        self.assertEqual(failure_category, "quest_quality")
        self.assertIn("- status: failed", summary_text)
        self.assertIn("- failure_category: quest_quality", summary_text)
        self.assertEqual(payload["request"]["passed"], False)
        self.assertEqual(payload["request"]["completed"], True)
        self.assertEqual(payload["request"]["failureCategory"], "quest_quality")
        self.assertLess(payload["request"]["actionSceneCohesionScore"], 70)

    def test_submit_evaluation_posts_actor_spawn_summary_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                    "--dynamic-quest-min-action-scene-cohesion",
                    "70",
                ]
            )
            case = matrix.QuestCase(
                name="alb-p3",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Sir Lukas",
                target="ant drone",
                return_home=(518850, 494050, 3352),
                party_size=3,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=5,
                quest_id="seed-1-actors",
            )
            summary = matrix.CaseSummary(
                players=3,
                ok_players=3,
                completed=3,
                reward_observed=3,
                target_removed=3,
                player_deaths=0,
                choice_selected=3,
                world_signal=3,
                presentation_beat=24,
                world_impact=3,
                world_impact_summary=3,
                narrative_scene=12,
                cinematic_action=105,
                scene_director_beat=45,
                scene_beat_outcome=45,
                scene_choreography_phase=45,
                scene_actor_exchange=30,
                scene_exchange_outcome=30,
                scene_outcome_signal=30,
                scene_consequence=30,
                scene_world_signal=45,
                world_signal_scene_shift=6,
                cinematic_cleanup=3,
                elapsed_seconds=120.0,
                passed=True,
                evaluation_score=100,
                skyrim_grade_score=100,
                cinematic_density_score=100,
                kill_confirmed=3,
                choice_outcome_scene=3,
                cinematic_variety=8,
                cinematic_motion_variety=8,
                cinematic_staggered_scene=12,
                cinematic_objective_focal_scene=12,
                cinematic_actor_role_variety=5,
                cinematic_choreographed_scene=12,
                cinematic_interaction_scene=12,
                cinematic_tactic_variety=5,
                story_continuity_score=100,
                story_archetype_score=100,
                cinematic_actor_instances=300,
                cinematic_actor_peak=100,
                cinematic_actor_spawn_summary=3,
                cinematic_actor_spawned_total=300,
                cinematic_actor_spawned_peak=100,
                cinematic_actor_spawn_failed=0,
                cinematic_actor_cleanup_scheduled=300,
                cinematic_actor_motion_summary=3,
                cinematic_actor_motion_commands=900,
                cinematic_actor_motion_commands_peak=300,
                cinematic_actor_motion_commands_per_actor_peak=3,
                cinematic_actor_motion_spawned_total=300,
                cinematic_actor_engagement_summary=3,
                cinematic_actor_engagement_pairs=150,
                cinematic_actor_engagement_pairs_peak=50,
                cinematic_actor_engaged_total=300,
                cinematic_actor_engagement_spawned_total=300,
                cinematic_actor_budget_score=100,
                action_scene_cohesion_score=100,
                cinematic_catalog_role_variety=5,
                cinematic_model_role_fit_score=100,
            )
            matrix.write_case_summary(case, summary)

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertEqual(payload["request"]["cinematicActorSpawnSummary"], 3)
        self.assertEqual(payload["request"]["cinematicActorSpawnedTotal"], 300)
        self.assertEqual(payload["request"]["cinematicActorSpawnedPeak"], 100)
        self.assertEqual(payload["request"]["cinematicActorSpawnFailed"], 0)
        self.assertEqual(payload["request"]["cinematicActorCleanupScheduled"], 300)
        self.assertEqual(payload["request"]["cinematicActorMotionSummary"], 3)
        self.assertEqual(payload["request"]["cinematicActorMotionCommands"], 900)
        self.assertEqual(payload["request"]["cinematicActorMotionCommandsPeak"], 300)
        self.assertEqual(payload["request"]["cinematicActorMotionCommandsPerActorPeak"], 3)
        self.assertEqual(payload["request"]["cinematicActorMotionSpawnedTotal"], 300)
        self.assertEqual(payload["request"]["cinematicActorEngagementSummary"], 3)
        self.assertEqual(payload["request"]["cinematicActorEngagementPairs"], 150)
        self.assertEqual(payload["request"]["cinematicActorEngagementPairsPeak"], 50)
        self.assertEqual(payload["request"]["cinematicActorEngagedTotal"], 300)
        self.assertEqual(payload["request"]["cinematicActorEngagementSpawnedTotal"], 300)
        self.assertIn("- cinematic_actor_spawn_summary: 3", summary_text)
        self.assertIn("- cinematic_actor_spawned_total: 300", summary_text)
        self.assertIn("- cinematic_actor_spawn_failed: 0", summary_text)
        self.assertIn("- cinematic_actor_motion_summary: 3", summary_text)
        self.assertIn("- cinematic_actor_motion_commands: 900", summary_text)
        self.assertIn("- cinematic_actor_engagement_summary: 3", summary_text)
        self.assertIn("- cinematic_actor_engagement_pairs: 150", summary_text)

    def test_submit_evaluation_marks_low_model_role_fit_as_quality_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                    "--dynamic-quest-min-action-scene-cohesion",
                    "70",
                    "--dynamic-quest-min-cinematic-catalog-role-variety",
                    "2",
                    "--dynamic-quest-min-cinematic-model-role-fit",
                    "70",
                ]
            )
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Sir Lukas",
                target="black wolf pup",
                return_home=(518850, 494050, 3352),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=1,
                quest_id="seed-1-low-model-role-fit",
                tags=("story-cinematic", "scene-director", "story-archetype:witness-conspiracy"),
            )
            summary = matrix.replace(
                matrix.finalize_case_summary_scores(
                    matrix.CaseSummary(
                        players=1,
                        ok_players=1,
                        completed=1,
                        reward_observed=1,
                        target_removed=1,
                        player_deaths=0,
                        choice_selected=1,
                        world_signal=1,
                        presentation_beat=9,
                        world_impact=1,
                        world_impact_summary=1,
                        narrative_scene=4,
                        cinematic_action=24,
                        cinematic_variety=6,
                        cinematic_motion_variety=6,
                        cinematic_staggered_scene=6,
                        cinematic_objective_focal_scene=4,
                        cinematic_actor_role_variety=4,
                        cinematic_choreographed_scene=6,
                        cinematic_interaction_scene=6,
                        cinematic_tactic_variety=4,
                        cinematic_actor_instances=120,
                        cinematic_actor_peak=40,
                        cinematic_actor_budget_score=100,
                        scene_director_beat=6,
                        scene_beat_outcome=6,
                        scene_choreography_phase=12,
                        scene_actor_exchange=6,
                        scene_exchange_outcome=6,
                        scene_outcome_signal=6,
                        scene_consequence=4,
                        scene_world_signal=4,
                        cinematic_cleanup=1,
                        elapsed_seconds=90.0,
                        passed=True,
                    )
                ),
                action_scene_cohesion_score=100,
                cinematic_catalog_role_variety=1,
                cinematic_model_role_fit_score=55,
            )
            summary = matrix.ensure_case_story_archetype_score(summary, case)
            matrix.write_case_summary(
                case,
                summary,
                minimum_action_scene_cohesion=70,
                minimum_catalog_role_variety=2,
                minimum_model_role_fit=70,
            )
            failure_category = matrix.classify_case_failure(
                summary,
                case_dir,
                minimum_action_scene_cohesion=70,
                minimum_catalog_role_variety=2,
                minimum_model_role_fit=70,
            )

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertTrue(summary.passed)
        self.assertEqual(failure_category, "quest_quality")
        self.assertIn("- status: failed", summary_text)
        self.assertIn("- failure_category: quest_quality", summary_text)
        self.assertEqual(payload["request"]["passed"], False)
        self.assertEqual(payload["request"]["completed"], True)
        self.assertEqual(payload["request"]["failureCategory"], "quest_quality")
        self.assertEqual(payload["request"]["actionSceneCohesionScore"], 100)
        self.assertEqual(payload["request"]["cinematicCatalogRoleVariety"], 1)
        self.assertLess(payload["request"]["cinematicModelRoleFitScore"], 70)

    def test_submit_evaluation_posts_unfinished_dummy_difficulty_as_operational_failure(self) -> None:
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
                        "error",
                        "action_dynamic_quest_timeline_presentation_beat",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "midtest001",
                        "ok": "false",
                        "target_removed": "0",
                        "player_deaths": "2",
                        "elapsed_seconds": "305.953",
                        "error": "dynamic quest incomplete",
                        "action_dynamic_quest_timeline_presentation_beat": "0",
                    }
                )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                ]
            )
            case = matrix.QuestCase(
                name="mid-p1",
                key="mid",
                realm="Midgard",
                region=100,
                seed_npc="Aud",
                target="soft-shelled crab",
                return_home=(773327, 749653, 4552),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                quest_id="seed-100-test",
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(case, summary)
            failure_category = matrix.classify_case_failure(summary, case_dir)

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertEqual(failure_category, "dummy_difficulty")
        self.assertIn("- failure_category: dummy_difficulty", summary_text)
        self.assertNotIn("skipped", payload)
        self.assertEqual(payload["request"]["questId"], "seed-100-test")
        self.assertEqual(payload["request"]["failureCategory"], "dummy_difficulty")
        self.assertFalse(payload["request"]["passed"])
        self.assertEqual(payload["request"]["operationalEvaluation"]["grade"], "discard")
        self.assertFalse(payload["request"]["operationalEvaluation"]["passed"])
        self.assertLess(payload["request"]["operationalEvaluation"]["difficultyScore"], 100)
        self.assertIn(
            "dummy difficulty pressure prevented quest completion",
            payload["request"]["operationalEvaluation"]["warnings"],
        )

    def test_submit_evaluation_posts_low_spec_pressure_as_operational_failure(self) -> None:
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
                        "error",
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_cinematic_action",
                        "action_safe_exit_hold",
                        "action_behavior_state_DropAggroAndRecover",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "hibtest012",
                        "ok": "false",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "327.89",
                        "error": "dynamic quest incomplete after low-spec combat pressure",
                        "action_dynamic_quest_timeline_presentation_beat": "8",
                        "action_dynamic_quest_timeline_cinematic_action": "22",
                        "action_safe_exit_hold": "19",
                        "action_behavior_state_DropAggroAndRecover": "1",
                    }
                )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                ]
            )
            case = matrix.QuestCase(
                name="hib-p1",
                key="hib",
                realm="Hibernia",
                region=200,
                seed_npc="Gormghlaith",
                target="water beetle larva",
                return_home=(341224, 593868, 5464),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=5,
                quest_id="seed-200-low-spec",
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(case, summary)
            failure_category = matrix.classify_case_failure(summary, case_dir)

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertEqual(failure_category, "dummy_difficulty")
        self.assertIn("- failure_category: dummy_difficulty", summary_text)
        self.assertNotIn("skipped", payload)
        self.assertEqual(payload["request"]["questId"], "seed-200-low-spec")
        self.assertEqual(payload["request"]["failureCategory"], "dummy_difficulty")
        self.assertFalse(payload["request"]["passed"])
        self.assertEqual(payload["request"]["operationalEvaluation"]["grade"], "discard")
        self.assertFalse(payload["request"]["operationalEvaluation"]["passed"])
        self.assertLess(payload["request"]["operationalEvaluation"]["difficultyScore"], 100)
        self.assertTrue(
            any(
                "spawn cluster" in fix or "전투 로그 기반 난이도" in fix
                for fix in payload["request"]["operationalEvaluation"]["suggestedFixes"]
            )
        )

    def test_submit_evaluation_treats_connection_abort_with_combat_pressure_as_dummy_difficulty(self) -> None:
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
                        "error",
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_cinematic_action",
                        "action_critical_health_drop_aggro",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "midtest002",
                        "ok": "false",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "196.312",
                        "error": "[WinError 10053] 현재 연결은 사용자의 호스트 시스템의 소프트웨어의 의해 중단되었습니다",
                        "action_dynamic_quest_timeline_presentation_beat": "4",
                        "action_dynamic_quest_timeline_cinematic_action": "37",
                        "action_critical_health_drop_aggro": "1",
                    }
                )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                ]
            )
            case = matrix.QuestCase(
                name="mid-p1",
                key="mid",
                realm="Midgard",
                region=100,
                seed_npc="Aud",
                target="vendo grunt",
                return_home=(773327, 749653, 4552),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=2,
                quest_id="seed-100-combat-abort",
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(case, summary)
            failure_category = matrix.classify_case_failure(summary, case_dir)

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertEqual(failure_category, "dummy_difficulty")
        self.assertIn("- failure_category: dummy_difficulty", summary_text)
        self.assertNotIn("skipped", payload)
        self.assertEqual(payload["request"]["questId"], "seed-100-combat-abort")
        self.assertEqual(payload["request"]["failureCategory"], "dummy_difficulty")
        self.assertFalse(payload["request"]["operationalEvaluation"]["passed"])

    def test_submit_evaluation_treats_timeline_failure_after_combat_as_dummy_difficulty(self) -> None:
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
                        "error",
                        "action_dynamic_quest_timeline_required_missing",
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_cinematic_action",
                        "action_attack_on",
                        "action_combat_damage_done",
                        "action_combat_damage_taken",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "midtest021",
                        "ok": "false",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "295.640",
                        "error": "dynamic quest timeline check failed",
                        "action_dynamic_quest_timeline_required_missing": "1",
                        "action_dynamic_quest_timeline_presentation_beat": "5",
                        "action_dynamic_quest_timeline_cinematic_action": "22",
                        "action_attack_on": "189",
                        "action_combat_damage_done": "8",
                        "action_combat_damage_taken": "12",
                    }
                )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                ]
            )
            case = matrix.QuestCase(
                name="mid-p1",
                key="mid",
                realm="Midgard",
                region=100,
                seed_npc="Bolli",
                target="rattling skeleton",
                return_home=(773327, 749653, 4552),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=1,
                quest_id="seed-100-timeline-combat-pressure",
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(case, summary)
            failure_category = matrix.classify_case_failure(summary, case_dir)

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertEqual(failure_category, "dummy_difficulty")
        self.assertIn("- failure_category: dummy_difficulty", summary_text)
        self.assertEqual(payload["request"]["failureCategory"], "dummy_difficulty")
        self.assertFalse(payload["request"]["passed"])

    def test_submit_evaluation_treats_inactive_without_reward_after_combat_as_dummy_difficulty(self) -> None:
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
                        "error",
                        "action_dynamic_quest_final_inactive",
                        "action_dynamic_quest_timeline_required_missing",
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_cinematic_action",
                        "action_attack_on",
                        "action_combat_damage_done",
                        "action_combat_damage_taken",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "albtest008",
                        "ok": "false",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "296.609",
                        "error": "dynamic quest timeline check failed: quest_completed,quest_rewarded",
                        "action_dynamic_quest_final_inactive": "1",
                        "action_dynamic_quest_timeline_required_missing": "1",
                        "action_dynamic_quest_timeline_presentation_beat": "5",
                        "action_dynamic_quest_timeline_cinematic_action": "22",
                        "action_attack_on": "68",
                        "action_combat_damage_done": "2",
                        "action_combat_damage_taken": "8",
                    }
                )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                ]
            )
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Sir Lukas",
                target="black wolf pup",
                return_home=(518850, 494050, 3352),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=1,
                quest_id="seed-1-inactive-combat-pressure",
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(case, summary)
            failure_category = matrix.classify_case_failure(summary, case_dir)

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertEqual(failure_category, "dummy_difficulty")
        self.assertIn("- failure_category: dummy_difficulty", summary_text)
        self.assertEqual(payload["request"]["failureCategory"], "dummy_difficulty")
        self.assertFalse(payload["request"]["passed"])

    def test_submit_evaluation_accepts_complete_autoaccept_with_only_initial_timeline_gap(self) -> None:
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
                        "error",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_reward_observed",
                        "action_dynamic_quest_timeline_choice_selected",
                        "action_dynamic_quest_timeline_world_signal",
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_cinematic_action",
                        "action_dynamic_quest_timeline_scene_beat_outcome",
                        "action_dynamic_quest_timeline_scene_world_signal",
                        "action_dynamic_quest_timeline_cinematic_actor_instances",
                        "action_dynamic_quest_timeline_cinematic_actor_peak",
                        "action_dynamic_quest_timeline_cinematic_actor_cleanup_scheduled",
                        "action_dynamic_quest_timeline_cinematic_actor_spawn_summary",
                        "action_dynamic_quest_timeline_cinematic_actor_spawned_total",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_summary",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_commands",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_spawned_total",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_summary",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_pairs",
                        "action_dynamic_quest_timeline_cinematic_actor_engaged_total",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_spawned_total",
                    ],
                )
                writer.writeheader()
                rows = [
                    ("albtest006", "false", "dynamic quest timeline check failed: presentation:onaccept,quest_accepted", "50"),
                    ("albtest010", "true", "", "64"),
                    ("albtest016", "false", "dynamic quest timeline check failed: presentation:onaccept,presentation:onexplore,quest_accepted", "47"),
                ]
                for username, ok, error, cinematic_action in rows:
                    writer.writerow(
                        {
                            "username": username,
                            "ok": ok,
                            "target_removed": "1",
                            "player_deaths": "0",
                            "elapsed_seconds": "91.5",
                            "error": error,
                            "action_dynamic_quest_complete_verified": "1",
                            "action_dynamic_quest_reward_observed": "1",
                            "action_dynamic_quest_timeline_choice_selected": "1",
                            "action_dynamic_quest_timeline_world_signal": "1",
                            "action_dynamic_quest_timeline_presentation_beat": "12",
                            "action_dynamic_quest_timeline_cinematic_action": cinematic_action,
                            "action_dynamic_quest_timeline_scene_beat_outcome": "12",
                            "action_dynamic_quest_timeline_scene_world_signal": "12",
                            "action_dynamic_quest_timeline_cinematic_actor_instances": "900",
                            "action_dynamic_quest_timeline_cinematic_actor_peak": "100",
                            "action_dynamic_quest_timeline_cinematic_actor_cleanup_scheduled": "900",
                            "action_dynamic_quest_timeline_cinematic_actor_spawn_summary": "36",
                            "action_dynamic_quest_timeline_cinematic_actor_spawned_total": "900",
                            "action_dynamic_quest_timeline_cinematic_actor_motion_summary": "36",
                            "action_dynamic_quest_timeline_cinematic_actor_motion_commands": "2700",
                            "action_dynamic_quest_timeline_cinematic_actor_motion_spawned_total": "900",
                            "action_dynamic_quest_timeline_cinematic_actor_engagement_summary": "30",
                            "action_dynamic_quest_timeline_cinematic_actor_engagement_pairs": "450",
                            "action_dynamic_quest_timeline_cinematic_actor_engaged_total": "900",
                            "action_dynamic_quest_timeline_cinematic_actor_engagement_spawned_total": "900",
                        }
                    )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                    "--dynamic-quest-evaluation-min-score",
                    "90",
                    "--dynamic-quest-min-action-scene-cohesion",
                    "0",
                    "--dynamic-quest-min-cinematic-catalog-role-variety",
                    "0",
                    "--dynamic-quest-min-cinematic-model-role-fit",
                    "0",
                ]
            )
            case = matrix.QuestCase(
                name="alb-p3",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="",
                target="ant drone",
                return_home=(518850, 494050, 3352),
                party_size=3,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=8,
                quest_id="seed-1-initial-gap",
                tags=("branch:time-window", "story-cinematic", "scene-director", "mass-cinematic"),
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(
                case,
                summary,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
            )
            failure_category = matrix.classify_case_failure(
                summary,
                case_dir,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
            )
            effective_passed = matrix.effective_case_passed(
                summary,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
                case_dir=case_dir,
            )

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertTrue(effective_passed)
        self.assertEqual(failure_category, "passed")
        self.assertIn("- status: passed", summary_text)
        self.assertIn("- failure_category: passed", summary_text)
        self.assertEqual(payload["request"]["failureCategory"], "passed")
        self.assertTrue(payload["request"]["passed"])
        self.assertTrue(payload["request"]["initialTimelineObservationGapAccepted"])

    def test_submit_evaluation_accepts_all_players_initial_gap_with_minor_actor_spawn_shortfall(self) -> None:
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
                        "error",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_reward_observed",
                        "action_dynamic_quest_timeline_choice_selected",
                        "action_dynamic_quest_timeline_world_signal",
                        "action_dynamic_quest_timeline_presentation_beat",
                        "action_dynamic_quest_timeline_cinematic_action",
                        "action_dynamic_quest_timeline_scene_beat_outcome",
                        "action_dynamic_quest_timeline_scene_world_signal",
                        "action_dynamic_quest_timeline_cinematic_actor_instances",
                        "action_dynamic_quest_timeline_cinematic_actor_peak",
                        "action_dynamic_quest_timeline_cinematic_actor_cleanup_scheduled",
                        "action_dynamic_quest_timeline_cinematic_actor_spawn_summary",
                        "action_dynamic_quest_timeline_cinematic_actor_spawned_total",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_summary",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_commands",
                        "action_dynamic_quest_timeline_cinematic_actor_motion_spawned_total",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_summary",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_pairs",
                        "action_dynamic_quest_timeline_cinematic_actor_engaged_total",
                        "action_dynamic_quest_timeline_cinematic_actor_engagement_spawned_total",
                    ],
                )
                writer.writeheader()
                rows = [
                    ("albtest006", "dynamic quest timeline check failed: quest_accepted", "936", "944"),
                    ("albtest010", "dynamic quest timeline check failed: quest_accepted", "936", "944"),
                    ("albtest016", "dynamic quest timeline check failed: presentation:onaccept,presentation:onexplore,quest_accepted", "936", "944"),
                ]
                for username, error, spawned, instances in rows:
                    writer.writerow(
                        {
                            "username": username,
                            "ok": "false",
                            "target_removed": "1",
                            "player_deaths": "0",
                            "elapsed_seconds": "35.5",
                            "error": error,
                            "action_dynamic_quest_complete_verified": "1",
                            "action_dynamic_quest_reward_observed": "1",
                            "action_dynamic_quest_timeline_choice_selected": "1",
                            "action_dynamic_quest_timeline_world_signal": "1",
                            "action_dynamic_quest_timeline_presentation_beat": "12",
                            "action_dynamic_quest_timeline_cinematic_action": "55",
                            "action_dynamic_quest_timeline_scene_beat_outcome": "20",
                            "action_dynamic_quest_timeline_scene_world_signal": "20",
                            "action_dynamic_quest_timeline_cinematic_actor_instances": instances,
                            "action_dynamic_quest_timeline_cinematic_actor_peak": "100",
                            "action_dynamic_quest_timeline_cinematic_actor_cleanup_scheduled": spawned,
                            "action_dynamic_quest_timeline_cinematic_actor_spawn_summary": "35",
                            "action_dynamic_quest_timeline_cinematic_actor_spawned_total": spawned,
                            "action_dynamic_quest_timeline_cinematic_actor_motion_summary": "35",
                            "action_dynamic_quest_timeline_cinematic_actor_motion_commands": "2808",
                            "action_dynamic_quest_timeline_cinematic_actor_motion_spawned_total": instances,
                            "action_dynamic_quest_timeline_cinematic_actor_engagement_summary": "34",
                            "action_dynamic_quest_timeline_cinematic_actor_engagement_pairs": "450",
                            "action_dynamic_quest_timeline_cinematic_actor_engaged_total": spawned,
                            "action_dynamic_quest_timeline_cinematic_actor_engagement_spawned_total": spawned,
                        }
                    )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                    "--dynamic-quest-evaluation-min-score",
                    "75",
                    "--dynamic-quest-min-action-scene-cohesion",
                    "0",
                    "--dynamic-quest-min-cinematic-catalog-role-variety",
                    "0",
                    "--dynamic-quest-min-cinematic-model-role-fit",
                    "0",
                ]
            )
            case = matrix.QuestCase(
                name="alb-p3",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="",
                target="forest snake",
                return_home=(518850, 494050, 3352),
                party_size=3,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=10,
                quest_id="seed-1-minor-spawn-shortfall",
                tags=("branch:time-window", "story-cinematic", "scene-director", "mass-cinematic"),
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(
                case,
                summary,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
            )
            failure_category = matrix.classify_case_failure(
                summary,
                case_dir,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
            )
            effective_passed = matrix.effective_case_passed(
                summary,
                minimum_action_scene_cohesion=0,
                minimum_catalog_role_variety=0,
                minimum_model_role_fit=0,
                case_dir=case_dir,
            )

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertTrue(effective_passed)
        self.assertEqual(failure_category, "passed")
        self.assertIn("- status: passed", summary_text)
        self.assertIn("- failure_category: passed", summary_text)
        self.assertEqual(payload["request"]["failureCategory"], "passed")
        self.assertTrue(payload["request"]["passed"])
        self.assertTrue(payload["request"]["initialTimelineObservationGapAccepted"])

    def test_submit_evaluation_posts_completion_only_no_fresh_runtime_signal(self) -> None:
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
                        "error",
                        "action_dynamic_quest_complete_verified",
                        "action_dynamic_quest_final_never_active",
                        "action_dynamic_quest_timeline_required_missing",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "username": "albtest001",
                        "ok": "false",
                        "target_removed": "0",
                        "player_deaths": "0",
                        "elapsed_seconds": "24.344",
                        "error": "dynamic quest timeline check failed",
                        "action_dynamic_quest_complete_verified": "1",
                        "action_dynamic_quest_final_never_active": "1",
                        "action_dynamic_quest_timeline_required_missing": "1",
                    }
                )

            args = matrix.parse_args(
                [
                    "--dynamic-quest-evaluation-api-url",
                    "http://127.0.0.1:5000/api/world/dynamic-quests/evaluation",
                ]
            )
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Sir Lukas",
                target="ant drone",
                return_home=(518850, 494050, 3352),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                player_level=5,
                quest_id="seed-1-completed-before-run",
            )
            summary = matrix.summarize_case(case_dir)
            matrix.write_case_summary(case, summary)
            failure_category = matrix.classify_case_failure(summary, case_dir)

            class FakeResponse:
                def __enter__(self):
                    return self

                def __exit__(self, _exc_type, _exc, _traceback):
                    return False

                def read(self):
                    return b'{"accepted":true,"belowThreshold":false}'

            with mock.patch.object(matrix.urllib.request, "urlopen", return_value=FakeResponse()) as urlopen:
                matrix.submit_dynamic_quest_evaluation(case, args, summary)

            payload = json.loads((case_dir / "dynamic-quest-evaluation.json").read_text(encoding="utf-8"))
            summary_text = (case_dir / "matrix-summary.md").read_text(encoding="utf-8")

        urlopen.assert_called_once()
        self.assertEqual(failure_category, "dummy_runtime")
        self.assertIn("- failure_category: dummy_runtime", summary_text)
        self.assertNotIn("skipped", payload)
        self.assertEqual(payload["request"]["questId"], "seed-1-completed-before-run")
        self.assertEqual(payload["request"]["completed"], False)
        self.assertEqual(payload["request"]["cinematicAction"], 0)
        self.assertEqual(payload["request"]["presentationBeat"], 0)
        self.assertEqual(payload["request"]["operationalEvaluation"]["grade"], "discard")
        self.assertFalse(payload["request"]["operationalEvaluation"]["passed"])

    def test_classify_case_failure_keeps_cinematic_ok_player_mismatch_out_of_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            summary = matrix.CaseSummary(
                players=2,
                ok_players=0,
                completed=2,
                reward_observed=2,
                target_removed=2,
                player_deaths=0,
                choice_selected=1,
                world_signal=1,
                presentation_beat=12,
                world_impact=2,
                world_impact_summary=1,
                narrative_scene=4,
                cinematic_action=48,
                scene_director_beat=16,
                scene_beat_outcome=8,
                scene_world_signal=3,
                cinematic_cleanup=4,
                elapsed_seconds=180.0,
                passed=False,
                evaluation_score=100,
                skyrim_grade_score=100,
                cinematic_density_score=100,
            )

            failure_category = matrix.classify_case_failure(summary, case_dir)

        self.assertEqual(failure_category, "quest_runtime")

    def test_api_enrichment_preserves_scene_event_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            case_dir = Path(tmp)
            metrics_path = case_dir / "metrics.csv"
            with metrics_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["username", "ok", "elapsed_seconds"])
                writer.writeheader()
                writer.writerow({"username": "albtest001", "ok": "true", "elapsed_seconds": "12.5"})

            args = matrix.parse_args(["--live-quest-api-timeout", "1"])
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Sir Lukas",
                target="black wolf pup",
                return_home=(518850, 494050, 3352),
                party_size=1,
                accounts_csv=case_dir / "accounts.csv",
                output_dir=case_dir,
                quest_id="seed-1-test",
            )
            summary = matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=0,
                reward_observed=0,
                target_removed=0,
                player_deaths=0,
                choice_selected=0,
                world_signal=0,
                presentation_beat=0,
                world_impact=0,
                world_impact_summary=0,
                narrative_scene=0,
                cinematic_action=0,
                scene_director_beat=0,
                scene_beat_outcome=0,
                scene_world_signal=0,
                cinematic_cleanup=0,
                followup_hunt_start=0,
                elapsed_seconds=12.5,
                passed=False,
            )
            payload = {
                "events": [
                    {"questId": "seed-1-test", "eventType": "quest_rewarded"},
                    {
                        "questId": "seed-1-test",
                        "eventType": "cinematic_action",
                        "nodeId": "kill",
                        "detail": "scene_beat:OnKill:kill:beat:1:delay:0:role:ambush:action:ambush_reveal:formation:ambush:motion:pincer:stagger:90:focal:objective:actorRole:strike:choreo:3:interact:clash:tactic:flank:model:1:catalogRole:fighter:actors:5",
                    },
                    {
                        "questId": "seed-1-test",
                        "eventType": "cinematic_action",
                        "nodeId": "choice",
                        "detail": "scene_beat:OnChoiceShown:choice:beat:1:delay:0:role:standoff:action:threat_standoff:formation:line:motion:standoff:stagger:80:focal:objective:actorRole:brace:choreo:3:interact:standoff:tactic:pressure:model:1:catalogRole:threat:actors:2",
                    },
                    {
                        "questId": "seed-1-test",
                        "eventType": "cinematic_action",
                        "nodeId": "explore",
                        "detail": "marker:OnExplore:explore:Quest trace: black wolf pup:model:488",
                    },
                    {
                        "questId": "seed-1-test",
                        "eventType": "cinematic_action",
                        "nodeId": "kill",
                        "detail": "marker:OnKill:kill:Threat sign: black wolf pup:model:489",
                    },
                    {"questId": "seed-1-test", "eventType": "scene_beat_outcome"},
                    {"questId": "seed-1-test", "eventType": "scene_world_signal"},
                    {
                        "questId": "seed-1-test",
                        "eventType": "world_signal_scene_shift",
                        "detail": "world_signal_scene_shift:signal:scene-witness:action:witness_point:role:witness:beats:1:actors:4:actions:1:formations:1:trigger:onexplore:phase:discovery:source:witness-witness_point:target:quest-trace:region:1",
                    },
                    {
                        "questId": "seed-1-test",
                        "eventType": "world_signal_scene_shift",
                        "detail": "world_signal_scene_shift:signal:scene-escape_cutoff:action:guard_advance:role:signal_counterline:beats:1:actors:7:actions:1:formations:1:trigger:onworldsignal:phase:blockade:source:scene-escape_cutoff:target:escape-route:region:1",
                    },
                ],
                "presentationBeats": [
                    {
                        "questId": "seed-1-test",
                        "trigger": "OnKill",
                        "speaker": "System",
                        "cinematicAction": "ambush_reveal",
                        "sceneRole": "ambush_wave",
                        "formation": "ambush",
                        "actorCount": 5,
                        "delayMs": 700,
                    },
                    {
                        "questId": "seed-1-test",
                        "trigger": "OnComplete",
                        "speaker": "StartNpc",
                        "cinematicAction": "defender_intercept",
                        "sceneRole": "debrief_guard",
                        "formation": "escort",
                        "actorCount": 2,
                        "delayMs": 0,
                    },
                ],
            }

            with mock.patch.object(matrix, "fetch_dynamic_quest_player_api", return_value=payload):
                enriched = matrix.enrich_summary_from_dynamic_quest_api(case, args, summary)

        self.assertEqual(enriched.completed, 1)
        self.assertEqual(enriched.presentation_beat, 2)
        self.assertEqual(enriched.presentation_speaker_variety, 2)
        self.assertEqual(enriched.presentation_staged_beat, 2)
        self.assertEqual(enriched.presentation_staged_actor_total, 7)
        self.assertEqual(enriched.presentation_staged_actor_peak, 5)
        self.assertEqual(enriched.presentation_staged_action_variety, 2)
        self.assertEqual(enriched.presentation_staged_role_variety, 2)
        self.assertEqual(enriched.presentation_staged_formation_variety, 2)
        self.assertEqual(enriched.presentation_staged_delayed_beat, 1)
        self.assertEqual(enriched.cinematic_action, 4)
        self.assertEqual(enriched.scene_director_beat, 2)
        self.assertEqual(enriched.cinematic_variety, 2)
        self.assertEqual(enriched.cinematic_motion_variety, 2)
        self.assertEqual(enriched.cinematic_staggered_scene, 2)
        self.assertEqual(enriched.cinematic_objective_focal_scene, 2)
        self.assertEqual(enriched.cinematic_actor_role_variety, 2)
        self.assertEqual(enriched.cinematic_choreographed_scene, 2)
        self.assertEqual(enriched.cinematic_interaction_scene, 2)
        self.assertEqual(enriched.cinematic_tactic_variety, 2)
        self.assertEqual(enriched.cinematic_catalog_role_variety, 2)
        self.assertGreaterEqual(enriched.cinematic_model_role_fit_score, 60)
        self.assertEqual(enriched.cinematic_actor_instances, 7)
        self.assertEqual(enriched.cinematic_actor_peak, 5)
        self.assertEqual(enriched.cinematic_marker_scene, 2)
        self.assertEqual(enriched.cinematic_marker_variety, 2)
        self.assertEqual(enriched.cinematic_phase_coverage, 3)
        self.assertEqual(enriched.cinematic_setpiece_phase_coverage, 2)
        self.assertEqual(enriched.cinematic_marker_phase_coverage, 2)
        self.assertEqual(enriched.cinematic_story_chain, 2)
        self.assertEqual(enriched.scene_beat_outcome, 1)
        self.assertEqual(enriched.scene_world_signal, 1)
        self.assertEqual(enriched.world_signal_scene_shift, 2)
        self.assertEqual(enriched.world_signal_scene_shift_detail, 2)
        self.assertEqual(enriched.world_signal_scene_shift_phase_variety, 2)
        self.assertEqual(enriched.world_signal_scene_shift_source_variety, 2)
        self.assertEqual(enriched.world_signal_scene_shift_target_variety, 2)
        self.assertEqual(enriched.kill_confirmed, 1)
        self.assertTrue(enriched.passed)

    def test_timeline_story_chain_requires_ordered_cinematic_phases(self) -> None:
        payload = {
            "events": [
                {
                    "questId": "seed-1-test",
                    "eventType": "cinematic_action",
                    "nodeId": "kill",
                    "detail": "scene_beat:OnKill:kill:beat:1:action:ambush_reveal",
                },
                {
                    "questId": "seed-1-test",
                    "eventType": "cinematic_action",
                    "nodeId": "explore",
                    "detail": "scene_beat:OnExplore:explore:beat:1:action:witness_point",
                },
                {
                    "questId": "seed-1-test",
                    "eventType": "cinematic_action",
                    "nodeId": "complete",
                    "detail": "npc_action:OnComplete:complete:focus:Bow",
                },
            ],
        }

        observations = matrix.summarize_dynamic_quest_timeline_observations(payload, "seed-1-test")

        self.assertEqual(observations["cinematic_phase_coverage"], 3)
        self.assertEqual(observations["cinematic_setpiece_phase_coverage"], 2)
        self.assertEqual(observations["cinematic_story_chain"], 1)

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

    def test_run_matrix_uses_enriched_summary_instead_of_raw_client_returncode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp)
            accounts_csv = output_root / "accounts.csv"
            accounts_csv.write_text(
                "username,password,realm,char_index,class_id,class_name,specs\n"
                "albtest007,dummy-pass,1,0,7,Wizard,Fire Magic|50\n",
                encoding="utf-8",
            )
            args = matrix.parse_args(
                [
                    "--matrix",
                    "quick",
                    "--party-sizes",
                    "1",
                    "--output-root",
                    str(output_root),
                    "--accounts-pattern",
                    str(accounts_csv),
                    "--no-reset-start-positions",
                    "--dynamic-quest-min-action-scene-cohesion",
                    "0",
                    "--dynamic-quest-min-cinematic-catalog-role-variety",
                    "0",
                    "--dynamic-quest-min-cinematic-model-role-fit",
                    "0",
                ]
            )
            case = matrix.QuestCase(
                name="alb-p1",
                key="alb",
                realm="Albion",
                region=1,
                seed_npc="Sir Lukas",
                target="black wolf pup",
                return_home=(505313, 496252, 2432),
                party_size=1,
                accounts_csv=accounts_csv,
                output_dir=output_root / "alb-p1",
                quest_id="seed-1-e0795a280b420cd5",
            )
            raw_summary = matrix.CaseSummary(
                players=1,
                ok_players=0,
                completed=0,
                reward_observed=0,
                target_removed=0,
                player_deaths=0,
                choice_selected=0,
                world_signal=0,
                presentation_beat=0,
                world_impact=0,
                world_impact_summary=0,
                narrative_scene=0,
                cinematic_action=0,
                scene_director_beat=0,
                scene_beat_outcome=0,
                passed=False,
            )
            enriched_summary = matrix.CaseSummary(
                players=1,
                ok_players=1,
                completed=1,
                reward_observed=1,
                target_removed=1,
                player_deaths=0,
                choice_selected=1,
                world_signal=0,
                presentation_beat=14,
                world_impact=1,
                world_impact_summary=1,
                narrative_scene=6,
                cinematic_action=72,
                scene_director_beat=35,
                scene_beat_outcome=26,
                scene_choreography_phase=52,
                scene_actor_exchange=24,
                scene_exchange_outcome=24,
                scene_outcome_signal=21,
                scene_consequence=17,
                scene_world_signal=50,
                world_signal_scene_shift=42,
                cinematic_cleanup=3,
                elapsed_seconds=221.609,
                passed=True,
                evaluation_score=100,
                skyrim_grade_score=100,
                cinematic_density_score=100,
                kill_confirmed=1,
                choice_outcome_scene=1,
                cinematic_variety=10,
                cinematic_motion_variety=10,
                cinematic_staggered_scene=35,
                cinematic_objective_focal_scene=16,
                cinematic_actor_role_variety=6,
                cinematic_choreographed_scene=35,
                cinematic_interaction_scene=35,
                cinematic_tactic_variety=6,
                story_continuity_score=100,
                story_archetype_score=100,
                cinematic_actor_instances=1900,
                cinematic_actor_peak=100,
                cinematic_actor_budget_score=100,
            )

            with (
                mock.patch.object(matrix, "build_cases", return_value=[case]),
                mock.patch.object(matrix, "should_resolve_live_case", return_value=False),
                mock.patch.object(matrix, "prepare_case_accounts_csv", return_value=accounts_csv),
                mock.patch.object(matrix, "build_behavior_command", return_value=["python", "dummy"]),
                mock.patch.object(matrix.subprocess, "run", return_value=SimpleNamespace(returncode=1)) as run,
                mock.patch.object(matrix, "cleanup_active_dynamic_quest_progress_for_accounts", return_value=[]),
                mock.patch.object(matrix, "summarize_case", return_value=raw_summary),
                mock.patch.object(matrix, "enrich_summary_from_dynamic_quest_api", return_value=enriched_summary),
                mock.patch.object(matrix, "finalize_case_summary_scores", side_effect=lambda summary, **_kwargs: summary),
                mock.patch.object(matrix, "calculate_story_archetype_score", return_value=100),
                mock.patch.object(matrix, "submit_dynamic_quest_evaluation") as submit,
            ):
                rc = matrix.run_matrix(args)

            summary_text = (case.output_dir / "matrix-summary.md").read_text(encoding="utf-8")

        self.assertEqual(rc, 0)
        run.assert_called_once()
        submit.assert_called_once()
        self.assertIn("- status: passed", summary_text)
        self.assertIn("- completed: 1", summary_text)
        self.assertIn("- scene_choreography_phase: 52", summary_text)

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
