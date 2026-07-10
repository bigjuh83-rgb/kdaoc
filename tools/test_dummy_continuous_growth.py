#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from tools import dummy_continuous_growth as continuous
    from tools.dummy_progression_audit import ProgressionSnapshot
except ModuleNotFoundError:
    import dummy_continuous_growth as continuous
    from dummy_progression_audit import ProgressionSnapshot


def quest_payload(*, target_count: int = 3, min_level: int = 5) -> dict[str, object]:
    return {
        "enabled": True,
        "active": [
            {
                "questId": "quest-1",
                "title": "Road Test",
                "currentNodeId": "hunt",
                "currentNodeType": "Kill",
                "count": 1,
                "currentNodeElapsedSeconds": 12,
                "currentObjective": {
                    "targetName": "young grendelorm",
                    "targetCount": target_count,
                    "minLevel": min_level,
                    "maxLevel": 10,
                    "regionId": 100,
                    "x": 1000,
                    "y": 2000,
                    "z": 3000,
                    "radius": 600,
                },
            }
        ],
        "completedQuestIds": [],
    }


def autoaccept_diagnostics(*, player_level_matches: bool) -> dict[str, object]:
    reasons = [] if player_level_matches else ["player_level_mismatch"]
    if player_level_matches:
        reasons.append("outside_start_scope")
    return {
        "enabled": True,
        "playerLevel": 8 if player_level_matches else 1,
        "regionId": 100,
        "triggers": [
            {
                "trigger": "region:100",
                "candidates": [
                    {
                        "questId": "quest-offer-1",
                        "title": "Road Offer",
                        "targetName": "young grendelorm",
                        "minLevel": 7,
                        "maxLevel": 10,
                        "triggerMatches": True,
                        "playerLevelMatches": player_level_matches,
                        "hasCompleted": False,
                        "hasCompletedStoryFamily": False,
                        "hasProgress": False,
                        "hasActiveStoryFamily": False,
                        "insideStartScope": False,
                        "offerBlockedReasons": reasons,
                        "startScopes": [
                            {
                                "regionId": 100,
                                "x": 4000,
                                "y": 5000,
                                "z": 6000,
                                "radius": 450,
                                "locationName": "road marker",
                            }
                        ],
                        "tags": ["region:100", "start-mode:AutoAccept"],
                    }
                ],
            }
        ],
    }


class RunningProcess:
    returncode = None

    def poll(self) -> None:
        return None


class ContinuousGrowthTests(unittest.TestCase):
    def test_command_option_helpers_replace_without_string_parsing(self) -> None:
        command = ["python", "runner.py", "--hold", "30", "--hunter"]

        updated = continuous.replace_command_option(command, "--hold", 999)

        self.assertEqual(continuous.command_option_value(updated, "--hold"), "999")
        self.assertTrue(continuous.command_has_flag(updated, "--hunter"))
        self.assertEqual(command[3], "30")

    def test_parse_dynamic_quest_observation_keeps_difficulty_fields(self) -> None:
        observation = continuous.parse_dynamic_quest_observations(quest_payload())[0]

        self.assertEqual(observation.node_type, "kill")
        self.assertEqual(observation.target_name, "young grendelorm")
        self.assertEqual(observation.target_count, 3)
        self.assertEqual((observation.region, observation.x, observation.y), (100, 1000, 2000))

    def test_dynamic_quest_difficulty_skips_excessive_count_and_level(self) -> None:
        observation = continuous.parse_dynamic_quest_observations(
            quest_payload(target_count=12, min_level=20)
        )[0]
        snapshot = ProgressionSnapshot(level=8, region=100, x=900, y=1900)
        options = continuous.ContinuousSupervisorOptions(
            api_base_url="http://localhost:5000",
            dynamic_quest_max_target_count=8,
            dynamic_quest_max_level_delta=2,
        )

        reasons = continuous.dynamic_quest_difficulty_reasons(observation, snapshot, options)

        self.assertTrue(any(reason.startswith("target_count:") for reason in reasons))
        self.assertTrue(any(reason.startswith("target_min_level:") for reason in reasons))

    def test_dynamic_quest_explore_wait_routes_instead_of_difficulty_skip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coordinator = continuous.DynamicQuestCoordinator(
                options=continuous.ContinuousSupervisorOptions(api_base_url="http://localhost:5000"),
                accounts={"growthmid001": "GrowthMid001"},
                case_name="mid-solo",
                party_size=1,
                live_control_path=root / "live-control.json",
                timeline_path=root / "dynamic-quest-timeline.csv",
            )
            snapshot = ProgressionSnapshot(
                name="GrowthMid001",
                account="growthmid001",
                level=8,
                region=100,
                x=900,
                y=1900,
            )
            progress = {
                "enabled": True,
                "active": [
                    {
                        "questId": "quest-explore-1",
                        "title": "Road Marker",
                        "currentNodeId": "explore",
                        "currentNodeType": "Explore",
                        "stalledReason": "waiting_for_location",
                        "currentObjective": {
                            "regionId": 100,
                            "x": 4000,
                            "y": 5000,
                            "z": 6000,
                            "radius": 450,
                            "locationName": "road marker",
                        },
                    }
                ],
                "completedQuestIds": [],
            }

            with (
                patch.object(continuous, "fetch_dynamic_quest_progress", return_value=progress),
                patch.object(continuous, "cancel_dynamic_quest_progress") as cancel,
            ):
                anomalies = coordinator.poll({"growthmid001": snapshot})

            control = json.loads((root / "live-control.json").read_text(encoding="utf-8"))
            timeline = (root / "dynamic-quest-timeline.csv").read_text(encoding="utf-8")

        self.assertEqual(anomalies, [])
        self.assertFalse(cancel.called)
        self.assertEqual(control["progressionHunt"]["huntLocation"]["x"], 4000)
        self.assertIn("__dynamic_quest_explore_probe__", control["progressionHunt"]["requireTargetName"])
        self.assertIn("routed", timeline)

    def test_dynamic_quest_choice_wait_remains_a_difficulty_skip_reason(self) -> None:
        observation = continuous.parse_dynamic_quest_observations(
            {
                "active": [
                    {
                        "questId": "quest-choice-1",
                        "currentNodeId": "choice",
                        "currentNodeType": "Choice",
                        "stalledReason": "waiting_for_choice",
                    }
                ]
            }
        )[0]

        reasons = continuous.dynamic_quest_difficulty_reasons(
            observation,
            ProgressionSnapshot(level=8, region=100),
            continuous.ContinuousSupervisorOptions(api_base_url="http://localhost:5000"),
        )

        self.assertEqual(reasons, ["stalled:waiting_for_choice"])

    def test_dynamic_quest_timeout_scales_with_remaining_kills(self) -> None:
        options = continuous.ContinuousSupervisorOptions(
            api_base_url="http://localhost:5000",
            dynamic_quest_timeout=240.0,
        )
        one_kill = continuous.parse_dynamic_quest_observations(
            quest_payload(target_count=1)
        )[0]
        eight_kills = continuous.parse_dynamic_quest_observations(
            quest_payload(target_count=8)
        )[0]
        explore = continuous.DynamicQuestObservation(
            quest_id="explore-1",
            title="Explore",
            node_id="explore",
            node_type="explore",
            target_name="",
            target_count=0,
            current_count=0,
            min_level=0,
            max_level=0,
            region=100,
            x=1,
            y=2,
            z=3,
            radius=400,
            npc_name="",
            npc_internal_id="",
            stalled_reason="waiting_for_location",
            failed=False,
            elapsed_seconds=0,
        )

        self.assertEqual(continuous.dynamic_quest_progress_timeout(one_kill, options), 90.0)
        self.assertEqual(continuous.dynamic_quest_progress_timeout(eight_kills, options), 240.0)
        self.assertEqual(continuous.dynamic_quest_progress_timeout(explore, options), 60.0)

    def test_no_active_quest_records_level_not_eligible_without_model_or_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coordinator = continuous.DynamicQuestCoordinator(
                options=continuous.ContinuousSupervisorOptions(api_base_url="http://localhost:5000"),
                accounts={"growthmid001": "GrowthMid001"},
                case_name="mid-solo",
                party_size=1,
                live_control_path=root / "live-control.json",
                timeline_path=root / "dynamic-quest-timeline.csv",
            )
            snapshot = ProgressionSnapshot(
                name="GrowthMid001",
                account="growthmid001",
                level=1,
                region=100,
                x=900,
                y=1900,
            )
            with (
                patch.object(
                    continuous,
                    "fetch_dynamic_quest_progress",
                    return_value={"enabled": True, "active": [], "completedQuestIds": []},
                ),
                patch.object(
                    continuous,
                    "fetch_dynamic_quest_autoaccept_diagnostics",
                    return_value=autoaccept_diagnostics(player_level_matches=False),
                ),
            ):
                anomalies = coordinator.poll({"growthmid001": snapshot})

            timeline = (root / "dynamic-quest-timeline.csv").read_text(encoding="utf-8")

        self.assertEqual(anomalies, [])
        self.assertIn("not_eligible", timeline)
        self.assertIn("player_level_mismatch:level=1", timeline)

    def test_eligible_autoaccept_offer_routes_to_compact_start_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coordinator = continuous.DynamicQuestCoordinator(
                options=continuous.ContinuousSupervisorOptions(api_base_url="http://localhost:5000"),
                accounts={"growthmid001": "GrowthMid001"},
                case_name="mid-solo",
                party_size=1,
                live_control_path=root / "live-control.json",
                timeline_path=root / "dynamic-quest-timeline.csv",
            )
            snapshot = ProgressionSnapshot(
                name="GrowthMid001",
                account="growthmid001",
                level=8,
                region=100,
                x=900,
                y=1900,
            )
            with (
                patch.object(
                    continuous,
                    "fetch_dynamic_quest_progress",
                    return_value={"enabled": True, "active": [], "completedQuestIds": []},
                ),
                patch.object(
                    continuous,
                    "fetch_dynamic_quest_autoaccept_diagnostics",
                    return_value=autoaccept_diagnostics(player_level_matches=True),
                ),
            ):
                anomalies = coordinator.poll({"growthmid001": snapshot})

            control = json.loads((root / "live-control.json").read_text(encoding="utf-8"))
            timeline = (root / "dynamic-quest-timeline.csv").read_text(encoding="utf-8")

        self.assertEqual(anomalies, [])
        self.assertEqual(control["progressionHunt"]["huntLocation"]["x"], 4000)
        self.assertIn("__dynamic_quest_scope_probe__", control["progressionHunt"]["requireTargetName"])
        self.assertIn("offer_routed", timeline)

    def test_autoaccept_activation_timer_starts_after_party_reaches_scope(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coordinator = continuous.DynamicQuestCoordinator(
                options=continuous.ContinuousSupervisorOptions(
                    api_base_url="http://localhost:5000",
                    dynamic_quest_poll_interval=2.0,
                ),
                accounts={
                    "growthmid001": "GrowthMid001",
                    "growthmid002": "GrowthMid002",
                },
                case_name="mid-p2",
                party_size=2,
                live_control_path=root / "live-control.json",
                timeline_path=root / "dynamic-quest-timeline.csv",
            )
            outside = {
                "growthmid001": ProgressionSnapshot(
                    name="GrowthMid001",
                    account="growthmid001",
                    level=8,
                    region=100,
                    x=900,
                    y=1900,
                ),
                "growthmid002": ProgressionSnapshot(
                    name="GrowthMid002",
                    account="growthmid002",
                    level=8,
                    region=100,
                    x=950,
                    y=1950,
                ),
            }
            diagnostics = autoaccept_diagnostics(player_level_matches=True)

            first = coordinator.handle_no_active_offer(diagnostics, outside, 100.0)
            before_arrival = coordinator.handle_no_active_offer(diagnostics, outside, 120.0)
            inside = {
                account: ProgressionSnapshot(
                    name=snapshot.name,
                    account=account,
                    level=8,
                    region=100,
                    x=4000,
                    y=5000,
                    z=6000,
                )
                for account, snapshot in outside.items()
            }
            arrived = coordinator.handle_no_active_offer(diagnostics, inside, 121.0)
            timed_out = coordinator.handle_no_active_offer(diagnostics, inside, 137.0)

        self.assertEqual(first, [])
        self.assertEqual(before_arrival, [])
        self.assertEqual(arrived, [])
        self.assertEqual(
            [row.code for row in timed_out],
            ["dynamic_quest_offer_activation_timeout"],
        )

    def test_dynamic_quest_progress_api_failure_is_fail_fast_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coordinator = continuous.DynamicQuestCoordinator(
                options=continuous.ContinuousSupervisorOptions(api_base_url="http://localhost:5000"),
                accounts={"growthmid001": "GrowthMid001"},
                case_name="mid-solo",
                party_size=1,
                live_control_path=root / "live-control.json",
                timeline_path=root / "dynamic-quest-timeline.csv",
            )
            snapshot = ProgressionSnapshot(account="growthmid001", level=8)

            with patch.object(
                continuous,
                "fetch_dynamic_quest_progress",
                side_effect=RuntimeError("progress down"),
            ):
                anomalies = coordinator.poll({"growthmid001": snapshot})

        self.assertEqual([row.code for row in anomalies], ["dynamic_quest_progress_api_error"])
        self.assertEqual(anomalies[0].severity, "error")

    def test_checkpoint_service_payload_becomes_route_only_payload(self) -> None:
        payload = {
            "progressionService": {
                "level": 9,
                "serviceLocation": {"region": 100, "x": 1, "y": 2, "z": 3},
                "huntLocation": {"region": 100, "x": 4, "y": 5, "z": 6},
                "requireTargetName": "tawny lynx",
                "members": {"growthmid001": {"level": 9, "sellSlots": [40]}},
            }
        }

        route = continuous.checkpoint_service_to_hunt_payload(payload, request_id="regular-9")

        self.assertNotIn("serviceLocation", route["progressionHunt"])
        self.assertEqual(route["progressionHunt"]["huntLocation"]["x"], 4)
        self.assertEqual(route["progressionHunt"]["requestId"], "regular-9")

    def test_dynamic_quest_reward_amount_reads_exact_server_timeline_values(self) -> None:
        reward = continuous.dynamic_quest_reward_amount(
            {
                "events": [
                    {
                        "questId": "quest-1",
                        "eventType": "quest_reward_amount",
                        "detail": "xp=1234;money_copper=567",
                    }
                ]
            },
            "quest-1",
        )

        self.assertEqual(reward, (1234, 567))

    def test_coordinator_routes_feasible_quest_without_a_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = continuous.ContinuousSupervisorOptions(api_base_url="http://localhost:5000")
            coordinator = continuous.DynamicQuestCoordinator(
                options=options,
                accounts={"growthmid001": "GrowthMid001"},
                case_name="mid-solo",
                party_size=1,
                live_control_path=root / "live-control.json",
                timeline_path=root / "dynamic-quest-timeline.csv",
            )
            coordinator.set_regular_hunt_payload(
                {
                    "revision": "regular",
                    "progressionHunt": {
                        "requestId": "regular",
                        "level": 8,
                        "huntLocation": {"region": 100, "x": 10, "y": 20, "z": 30},
                    },
                }
            )
            snapshot = ProgressionSnapshot(
                name="GrowthMid001",
                account="growthmid001",
                level=8,
                region=100,
                x=900,
                y=1900,
            )

            with patch.object(continuous, "fetch_dynamic_quest_progress", return_value=quest_payload()):
                anomalies = coordinator.poll({"growthmid001": snapshot})

            control = json.loads((root / "live-control.json").read_text(encoding="utf-8"))
            first_revision = control["revision"]
            coordinator.set_regular_hunt_payload(coordinator.regular_hunt_payload or {})
            coordinator.next_poll_at = 0.0
            with patch.object(continuous, "fetch_dynamic_quest_progress", return_value=quest_payload()):
                coordinator.poll({"growthmid001": snapshot})
            rerouted = json.loads((root / "live-control.json").read_text(encoding="utf-8"))

        self.assertEqual(anomalies, [])
        self.assertEqual(
            control["progressionHunt"]["requireTargetName"],
            "young grendelorm",
        )
        self.assertNotEqual(first_revision, rerouted["revision"])

    def test_difficulty_skip_is_not_recorded_when_cancel_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            options = continuous.ContinuousSupervisorOptions(
                api_base_url="http://localhost:5000",
                dynamic_quest_max_target_count=2,
            )
            coordinator = continuous.DynamicQuestCoordinator(
                options=options,
                accounts={"growthmid001": "GrowthMid001"},
                case_name="mid-solo",
                party_size=1,
                live_control_path=root / "live-control.json",
                timeline_path=root / "dynamic-quest-timeline.csv",
            )
            snapshot = ProgressionSnapshot(
                name="GrowthMid001",
                account="growthmid001",
                level=8,
                region=100,
                x=900,
                y=1900,
            )

            with (
                patch.object(continuous, "fetch_dynamic_quest_progress", return_value=quest_payload()),
                patch.object(continuous, "cancel_dynamic_quest_progress", side_effect=RuntimeError("cancel down")),
            ):
                anomalies = coordinator.poll({"growthmid001": snapshot})

            timeline = (root / "dynamic-quest-timeline.csv").read_text(encoding="utf-8")

        self.assertEqual([row.code for row in anomalies], ["dynamic_quest_cancel_failed"])
        self.assertNotIn("difficulty_skip", timeline)
        self.assertNotIn("quest-1", coordinator.skipped_quest_ids["growthmid001"])

    def test_disabled_dynamic_quests_are_reported_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coordinator = continuous.DynamicQuestCoordinator(
                options=continuous.ContinuousSupervisorOptions(
                    api_base_url="http://localhost:5000",
                    dynamic_quest_poll_interval=0.0,
                ),
                accounts={"growthmid001": "GrowthMid001"},
                case_name="mid-solo",
                party_size=1,
                live_control_path=root / "live-control.json",
                timeline_path=root / "dynamic-quest-timeline.csv",
            )
            snapshot = ProgressionSnapshot(account="growthmid001", level=8)

            with patch.object(
                continuous,
                "fetch_dynamic_quest_progress",
                return_value={"enabled": False, "active": []},
            ):
                first = coordinator.poll({"growthmid001": snapshot})
                coordinator.next_poll_at = 0.0
                second = coordinator.poll({"growthmid001": snapshot})

        self.assertEqual([row.code for row in first], ["dynamic_quests_disabled"])
        self.assertEqual(second, [])

    def test_mercenary_coordinator_uses_real_request_and_separate_checkpoint_control(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coordinator = continuous.MercenaryCoordinator(
                options=continuous.ContinuousSupervisorOptions(
                    api_base_url="http://localhost:5000",
                    request_timeout=0.1,
                ),
                case_name="alb-p1-mercenary",
                leader_account="growthalb001",
                leader_character="GrowthAlb001",
                role="tank",
                contract_tier="legendary",
                companion_account="albtest002",
                companion_specs="Crush|50;Shields|42",
                service_process=RunningProcess(),
                service_run_directory=root / "service",
                status_directory=root / "status",
                timeline_path=root / "mercenary-timeline.csv",
                poll_interval=0.5,
            )
            leader = ProgressionSnapshot(
                name="GrowthAlb001",
                account="growthalb001",
                level=7,
                region=1,
                x=100,
                y=200,
                z=300,
            )
            leader_payload = {
                "groupMembers": [
                    {
                        "name": "AlbTest002",
                        "account": "albtest002",
                        "isCompanion": True,
                    }
                ]
            }
            companion_payload = {
                "player": {
                    "name": "AlbTest002",
                    "account": "albtest002",
                    "level": 7,
                    "class": "Armsman",
                    "region": 1,
                    "experience": 100,
                    "moneyCopper": 100,
                    "isCompanion": True,
                    "companionRole": "tank",
                    "specializations": [
                        {"name": "Crush", "keyName": "Crush", "level": 6, "trainable": True}
                    ],
                },
                "skills": [{"name": "Guard"}],
                "spellLines": [],
            }

            with patch.object(
                continuous,
                "api_json_request",
                side_effect=[
                    {"request": {"id": "request-1", "status": "queued"}},
                    {
                        "id": "request-1",
                        "status": "active",
                        "assignedCompanionName": "AlbTest002",
                    },
                ],
            ), patch.object(
                continuous,
                "fetch_progression_payload",
                return_value=companion_payload,
            ):
                self.assertEqual(coordinator.poll(leader_payload, leader), [])
                coordinator.next_poll_at = 0.0
                self.assertEqual(coordinator.poll(leader_payload, leader), [])

            checkpoint = {
                "progressionService": {
                    "level": 7,
                    "serviceLocation": {"region": 1, "x": 1, "y": 2, "z": 3},
                    "huntLocation": {"region": 1, "x": 4, "y": 5, "z": 6},
                    "members": {"growthalb001": {"level": 7, "train": True}},
                }
            }
            with patch.object(
                continuous,
                "fetch_progression_payload",
                return_value=companion_payload,
            ):
                before = coordinator.prepare_checkpoint(checkpoint, "level-7")
            control = json.loads(
                (root / "service" / "request-1" / "live-control.json").read_text(
                    encoding="utf-8"
                )
            )
            after_payload = json.loads(json.dumps(companion_payload))
            after_payload["player"]["moneyCopper"] = 90
            after_payload["player"]["specializations"][0]["level"] = 7
            with (
                patch.object(
                    continuous,
                    "wait_for_statuses",
                    return_value={"albtest002": {"ok": True, "errors": []}},
                ),
                patch.object(
                    continuous,
                    "fetch_progression_payload",
                    return_value=after_payload,
                ),
            ):
                checkpoint_anomalies = coordinator.finish_checkpoint("level-7", before, leader)
            timeline = (root / "mercenary-timeline.csv").read_text(encoding="utf-8")

        self.assertTrue(coordinator.ready)
        self.assertEqual(before.account, "albtest002")
        self.assertEqual(
            list(control["progressionService"]["members"]),
            ["albtest002"],
        )
        self.assertEqual(
            control["progressionService"]["members"]["albtest002"]["specs"],
            "Crush|50;Shields|42",
        )
        self.assertEqual(
            [row.code for row in checkpoint_anomalies],
            ["mercenary_service_economy_mismatch"],
        )
        self.assertIn("-10", timeline)

    def test_mercenary_coordinator_routes_far_companion_before_ready(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            initial_hunt = {
                "revision": "initial-hunt",
                "progressionHunt": {
                    "requestId": "initial-hunt",
                    "level": 1,
                    "huntLocation": {"region": 1, "x": 534900, "y": 478900, "z": 2200},
                    "preferTargetName": "black wolf pup",
                    "members": {"growthalb001": {"level": 1}},
                },
            }
            coordinator = continuous.MercenaryCoordinator(
                options=continuous.ContinuousSupervisorOptions(
                    api_base_url="http://localhost:5000",
                    request_timeout=0.1,
                ),
                case_name="alb-p1-mercenary",
                leader_account="growthalb001",
                leader_character="GrowthAlb001",
                role="fill",
                contract_tier="legendary",
                companion_account="albtest002",
                companion_specs="Crush|50;Shields|42",
                service_process=RunningProcess(),
                service_run_directory=root / "service",
                status_directory=root / "status",
                timeline_path=root / "mercenary-timeline.csv",
                initial_hunt_payload=initial_hunt,
                poll_interval=0.5,
                attach_max_distance=4000.0,
            )
            leader = ProgressionSnapshot(
                name="GrowthAlb001",
                account="growthalb001",
                level=1,
                region=1,
                x=534900,
                y=478900,
                z=2200,
            )
            leader_payload = {
                "groupMembers": [
                    {
                        "name": "AlbTest002",
                        "account": "albtest002",
                        "isCompanion": True,
                    }
                ]
            }
            companion_payload = {
                "player": {
                    "name": "AlbTest002",
                    "account": "albtest002",
                    "level": 1,
                    "class": "Armsman",
                    "region": 1,
                    "x": 518933,
                    "y": 494112,
                    "z": 3352,
                    "isCompanion": True,
                    "companionRole": "fill",
                    "specializations": [],
                },
                "skills": [],
                "spellLines": [],
            }
            active_request = {
                "id": "request-1",
                "status": "active",
                "assignedCompanionName": "AlbTest002",
            }

            with (
                patch.object(
                    continuous,
                    "api_json_request",
                    side_effect=[
                        {"request": {"id": "request-1", "status": "queued"}},
                        active_request,
                        active_request,
                    ],
                ),
                patch.object(
                    continuous,
                    "fetch_progression_payload",
                    return_value=companion_payload,
                ),
            ):
                self.assertEqual(coordinator.poll(leader_payload, leader), [])
                coordinator.next_poll_at = 0.0
                self.assertEqual(coordinator.poll(leader_payload, leader), [])
                self.assertFalse(coordinator.ready)
                control = json.loads(
                    (root / "service" / "request-1" / "live-control.json").read_text(
                        encoding="utf-8"
                    )
                )
                companion_payload["player"]["x"] = 534900
                companion_payload["player"]["y"] = 478900
                coordinator.next_poll_at = 0.0
                self.assertEqual(coordinator.poll(leader_payload, leader), [])

            timeline = (root / "mercenary-timeline.csv").read_text(encoding="utf-8")

        self.assertEqual(list(control["progressionHunt"]["members"]), ["albtest002"])
        self.assertEqual(control["progressionHunt"]["huntLocation"]["x"], 534900)
        self.assertIn("hunt_routed", timeline)
        self.assertTrue(coordinator.ready)


if __name__ == "__main__":
    unittest.main()
