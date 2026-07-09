#!/usr/bin/env python3
"""Unit checks for dynamic quest dialog handling in the behavior dummy."""

from __future__ import annotations

import argparse
import importlib.util
import sys
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("behavior-dummy-client.py")
    spec = importlib.util.spec_from_file_location("behavior_dummy_client_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


behavior = load_module()


class DialogClient:
    def __init__(self) -> None:
        self.responses: list[int] = []

    def accept_custom_dialog(self, response: int = 1) -> int:
        self.responses.append(response)
        return 0


class PositionClient:
    def __init__(self, x: int, y: int) -> None:
        self.x = x
        self.y = y


class BehaviorDummyDynamicQuestDialogTests(unittest.TestCase):
    def test_return_dialog_response_decline_sends_zero(self) -> None:
        client = DialogClient()
        args = argparse.Namespace(
            dynamic_quest_return_accept_dialog=True,
            dynamic_quest_return_dialog_response="decline",
        )

        count = behavior.accept_dynamic_quest_return_dialog(client, args, {})

        self.assertEqual(count, 1)
        self.assertEqual(client.responses, [0])

    def test_return_dialog_response_accept_sends_one(self) -> None:
        client = DialogClient()
        args = argparse.Namespace(
            dynamic_quest_return_accept_dialog=True,
            dynamic_quest_return_dialog_response="accept",
        )

        count = behavior.accept_dynamic_quest_return_dialog(client, args, {})

        self.assertEqual(count, 1)
        self.assertEqual(client.responses, [1])

    def test_timeline_snapshot_marks_choice_and_world_signal(self) -> None:
        args = argparse.Namespace(
            dynamic_quest_expected_quest_id="quest-branch",
            dynamic_quest_require_timeline_events="choice_selected,world_signal",
        )
        action_counts: dict[str, int] = {}
        logged: list[dict[str, object]] = []

        seen, missing = behavior.mark_dynamic_quest_timeline_snapshot(
            args,
            {
                "events": [
                    {
                        "questId": "old-quest",
                        "eventType": "choice_selected",
                        "choiceId": "followup",
                    },
                    {
                        "questId": "quest-branch",
                        "eventType": "choice_selected",
                        "choiceId": "followup",
                    },
                    {
                        "questId": "quest-branch",
                        "eventType": "world_signal",
                        "detail": "mob-growth:killed:region:1",
                    },
                    {
                        "questId": "quest-branch",
                        "eventType": "world_signal_scene_shift",
                        "detail": "world_signal_scene_shift:signal:mob-growth:killed:region:1",
                    },
                    {
                        "questId": "quest-branch",
                        "eventType": "scene_world_signal",
                        "detail": "scene:line_held",
                    },
                    {
                        "questId": "quest-branch",
                        "eventType": "scene_choreography_phase",
                        "detail": "scene_choreography_phase:role:ambush_wave:phase:1:action:ambush_reveal",
                    },
                    {
                        "questId": "quest-branch",
                        "eventType": "scene_actor_exchange",
                        "detail": "scene_actor_exchange:role:ambush_wave:interact:clash:actors:12",
                    },
                    {
                        "questId": "quest-branch",
                        "eventType": "scene_exchange_outcome",
                        "detail": "scene_exchange_outcome:role:ambush_wave:outcome:line_held",
                    },
                    {"questId": "quest-branch", "eventType": "scene_consequence"},
                ]
            },
            action_counts,
            now=123.0,
            source="final",
            log_encounter_event=lambda event, now=None, **fields: logged.append({"event": event, **fields}),
        )

        self.assertEqual(missing, [])
        self.assertEqual(
            seen,
            {
                "choice_selected",
                "world_signal",
                "world_signal_scene_shift",
                "scene_world_signal",
                "scene_choreography_phase",
                "scene_actor_exchange",
                "scene_exchange_outcome",
                "scene_consequence",
            },
        )
        self.assertEqual(action_counts["dynamic_quest_timeline_choice_selected"], 1)
        self.assertEqual(action_counts["dynamic_quest_timeline_world_signal"], 1)
        self.assertEqual(action_counts["dynamic_quest_timeline_world_signal_scene_shift"], 1)
        self.assertEqual(action_counts["dynamic_quest_timeline_scene_choreography_phase"], 1)
        self.assertEqual(action_counts["dynamic_quest_timeline_scene_actor_exchange"], 1)
        self.assertEqual(action_counts["dynamic_quest_timeline_scene_exchange_outcome"], 1)
        self.assertEqual(action_counts["dynamic_quest_timeline_scene_outcome_signal"], 1)
        self.assertEqual(action_counts["dynamic_quest_timeline_scene_consequence"], 1)
        self.assertEqual(logged[0]["choice_ids"], ["followup"])

    def test_timeline_snapshot_requires_detail_for_action_scene_counters(self) -> None:
        args = argparse.Namespace(
            dynamic_quest_expected_quest_id="quest-branch",
            dynamic_quest_require_timeline_events="scene_choreography_phase,scene_actor_exchange,scene_exchange_outcome",
        )
        action_counts: dict[str, int] = {}

        seen, missing = behavior.mark_dynamic_quest_timeline_snapshot(
            args,
            {
                "events": [
                    {"questId": "quest-branch", "eventType": "scene_choreography_phase"},
                    {"questId": "quest-branch", "eventType": "scene_actor_exchange", "detail": ""},
                    {"questId": "quest-branch", "eventType": "scene_exchange_outcome"},
                ]
            },
            action_counts,
            now=123.0,
            source="final",
            log_encounter_event=lambda *_args, **_fields: None,
        )

        self.assertEqual(missing, [])
        self.assertEqual(
            seen,
            {"scene_choreography_phase", "scene_actor_exchange", "scene_exchange_outcome"},
        )
        self.assertNotIn("dynamic_quest_timeline_scene_choreography_phase", action_counts)
        self.assertNotIn("dynamic_quest_timeline_scene_actor_exchange", action_counts)
        self.assertNotIn("dynamic_quest_timeline_scene_exchange_outcome", action_counts)

    def test_timeline_snapshot_tracks_hundred_actor_cinematic_budget(self) -> None:
        args = argparse.Namespace(
            dynamic_quest_expected_quest_id="quest-cinematic",
            dynamic_quest_require_timeline_events="cinematic_action",
            dynamic_quest_require_presentation_triggers="",
        )
        action_counts: dict[str, int] = {}

        seen, missing = behavior.mark_dynamic_quest_timeline_snapshot(
            args,
            {
                "events": [
                    {
                        "questId": "quest-cinematic",
                        "eventType": "cinematic_action",
                        "detail": "scene_beat:OnKill:kill:beat:1:delay:0:role:ambush:action:ambush_reveal:formation:ambush:motion:pincer:stagger:90:focal:objective:actorRole:strike:choreo:3:interact:clash:tactic:flank:model:1:actors:100",
                    },
                    {
                        "questId": "quest-cinematic",
                        "eventType": "cinematic_actor_motion_summary",
                        "detail": "action:ambush_reveal:role:fighter:motion:pincer:interact:clash:tactic:flank:actors:100:spawned:100:commandsPerActor:3:commands:300:formation:ambush",
                    },
                    {
                        "questId": "quest-cinematic",
                        "eventType": "cinematic_actor_engagement_summary",
                        "detail": "action:ambush_reveal:role:fighter:exchange:ambush_clash:interact:clash:tactic:flank:actors:100:spawned:100:engagedActors:100:pairs:50:choreo:3:formation:ambush",
                    }
                ]
            },
            action_counts,
            now=123.0,
            source="final",
            log_encounter_event=lambda *_, **__: None,
        )

        self.assertEqual(missing, [])
        self.assertIn("cinematic_action", seen)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_instances"], 100)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_peak"], 100)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_motion_summary"], 1)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_motion_commands"], 300)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_motion_commands_peak"], 300)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_motion_commands_per_actor_peak"], 3)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_motion_spawned_total"], 100)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_engagement_summary"], 1)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_engagement_pairs"], 50)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_engagement_pairs_peak"], 50)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_engaged_total"], 100)
        self.assertEqual(action_counts["dynamic_quest_timeline_cinematic_actor_engagement_spawned_total"], 100)

    def test_timeline_snapshot_reports_missing_required_event(self) -> None:
        args = argparse.Namespace(
            dynamic_quest_expected_quest_id="quest-branch",
            dynamic_quest_require_timeline_events="choice_selected,world_signal",
            dynamic_quest_require_presentation_triggers="",
        )
        action_counts: dict[str, int] = {}

        _, missing = behavior.mark_dynamic_quest_timeline_snapshot(
            args,
            {"events": [{"questId": "quest-branch", "eventType": "choice_selected"}]},
            action_counts,
            now=123.0,
            source="final",
            log_encounter_event=lambda *_, **__: None,
        )

        self.assertEqual(missing, ["world_signal"])
        self.assertEqual(action_counts["dynamic_quest_timeline_required_missing"], 1)

    def test_timeline_snapshot_marks_required_presentation_triggers(self) -> None:
        args = argparse.Namespace(
            dynamic_quest_expected_quest_id="quest-branch",
            dynamic_quest_require_timeline_events="",
            dynamic_quest_require_presentation_triggers="OnAccept,OnComplete",
        )
        action_counts: dict[str, int] = {}
        logged: list[dict[str, object]] = []

        seen, missing = behavior.mark_dynamic_quest_timeline_snapshot(
            args,
            {
                "presentationBeats": [
                    {
                        "questId": "old-quest",
                        "nodeId": "explore",
                        "trigger": "OnAccept",
                    },
                    {
                        "questId": "quest-branch",
                        "nodeId": "explore",
                        "trigger": "OnAccept",
                        "speaker": "System",
                        "emotion": "hope",
                        "emote": "Cheer",
                        "cinematicAction": "witness_point",
                        "sceneRole": "witness",
                        "formation": "escort",
                        "actorCount": 4,
                        "delayMs": 700,
                    },
                    {
                        "questId": "quest-branch",
                        "nodeId": "complete",
                        "trigger": "OnComplete",
                        "speaker": "StartNpc",
                        "emotion": "gratitude",
                        "emote": "Bow",
                        "cinematicAction": "hold_ground",
                        "sceneRole": "aftermath_guard",
                        "formation": "line",
                        "actorCount": 6,
                        "delayMs": 0,
                    },
                ]
            },
            action_counts,
            now=123.0,
            source="final",
            log_encounter_event=lambda event, now=None, **fields: logged.append({"event": event, **fields}),
        )

        self.assertEqual(missing, [])
        self.assertEqual(seen, {"presentation:onaccept", "presentation:oncomplete"})
        self.assertEqual(action_counts["dynamic_quest_timeline_presentation_beat"], 2)
        self.assertEqual(action_counts["dynamic_quest_timeline_presentation_staged_beat"], 2)
        self.assertEqual(action_counts["dynamic_quest_timeline_presentation_staged_actor_total"], 10)
        self.assertEqual(action_counts["dynamic_quest_timeline_presentation_staged_actor_peak"], 6)
        self.assertEqual(action_counts["dynamic_quest_timeline_presentation_staged_action_variety"], 2)
        self.assertEqual(action_counts["dynamic_quest_timeline_presentation_staged_role_variety"], 2)
        self.assertEqual(action_counts["dynamic_quest_timeline_presentation_staged_formation_variety"], 2)
        self.assertEqual(action_counts["dynamic_quest_timeline_presentation_staged_delayed_beat"], 1)
        self.assertEqual(logged[0]["presentation_triggers"], ["OnAccept", "OnComplete"])

    def test_timeline_snapshot_reports_missing_required_presentation_trigger(self) -> None:
        args = argparse.Namespace(
            dynamic_quest_expected_quest_id="quest-branch",
            dynamic_quest_require_timeline_events="",
            dynamic_quest_require_presentation_triggers="OnAccept,OnComplete",
        )
        action_counts: dict[str, int] = {}

        _, missing = behavior.mark_dynamic_quest_timeline_snapshot(
            args,
            {"presentationBeats": [{"questId": "quest-branch", "trigger": "OnAccept"}]},
            action_counts,
            now=123.0,
            source="final",
            log_encounter_event=lambda *_, **__: None,
        )

        self.assertEqual(missing, ["presentation:oncomplete"])
        self.assertEqual(action_counts["dynamic_quest_timeline_required_missing"], 1)

    def test_expected_final_active_node_allows_dynamic_quest_e2e_round(self) -> None:
        ok, error = behavior.final_round_completion_status(
            safe_exit_failed=False,
            safe_exit_error="",
            dynamic_quest_e2e_enabled=True,
            dynamic_quest_active_count=1,
            dynamic_quest_progress_seen=True,
            dynamic_quest_final_active_allowed=True,
        )

        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_completed_dynamic_quest_allows_e2e_round_even_when_active_complete_node_remains(self) -> None:
        ok, error = behavior.final_round_completion_status(
            safe_exit_failed=False,
            safe_exit_error="",
            dynamic_quest_e2e_enabled=True,
            dynamic_quest_active_count=1,
            dynamic_quest_progress_seen=True,
            dynamic_quest_completed=True,
        )

        self.assertTrue(ok)
        self.assertEqual(error, "")

    def test_expected_final_active_node_requires_matching_active_node(self) -> None:
        self.assertFalse(
            behavior.dynamic_quest_active_items_match_expected_final_node(
                [{"currentNodeId": "return"}],
                "observe_signal",
            )
        )
        self.assertTrue(
            behavior.dynamic_quest_active_items_match_expected_final_node(
                [{"currentNodeId": "observe_signal"}],
                "observe_signal",
            )
        )

    def test_followup_start_node_allows_wait_node_that_leads_to_expected_complete(self) -> None:
        active_items = [
            {
                "currentNodeId": "observe_signal",
                "currentNodeType": 6,
                "nodes": [
                    {
                        "id": "observe_signal",
                        "type": 6,
                        "edges": [
                            {
                                "toNodeId": "complete",
                                "condition": 6,
                                "conditionValue": "mob-growth:killed:region:100",
                            }
                        ],
                    },
                    {"id": "complete", "type": 4, "edges": []},
                ],
            }
        ]

        self.assertFalse(
            behavior.dynamic_quest_active_items_match_expected_final_node(
                active_items,
                "complete",
            )
        )
        self.assertTrue(
            behavior.dynamic_quest_active_items_match_followup_start_node(
                active_items,
                "complete",
            )
        )

    def test_followup_start_node_does_not_start_hunt_from_terminal_complete(self) -> None:
        self.assertFalse(
            behavior.dynamic_quest_active_items_match_followup_start_node(
                [{"currentNodeId": "complete", "currentNodeType": 4}],
                "complete",
            )
        )

    def test_active_items_have_choice_node_detects_choice_progress(self) -> None:
        self.assertTrue(
            behavior.dynamic_quest_active_items_have_choice_node(
                [
                    {
                        "currentNodeId": "choice",
                        "currentNodeType": 3,
                        "choices": [{"id": "safe"}, {"id": "followup"}],
                    }
                ]
            )
        )
        self.assertFalse(
            behavior.dynamic_quest_active_items_have_choice_node(
                [{"currentNodeId": "observe_signal", "currentNodeType": 6, "choices": []}]
            )
        )

    def test_followup_observe_final_requires_terminal_completion_after_hunt_started(self) -> None:
        args = argparse.Namespace(
            dynamic_quest_expected_final_node="complete",
            dynamic_quest_followup_target_name="노련한 vendo warrior",
        )
        observe_items = [
            {
                "currentNodeId": "observe_signal",
                "currentNodeType": 6,
                "count": 1,
                "currentObjective": {"targetCount": 1},
            }
        ]
        complete_items = [{"currentNodeId": "complete", "currentNodeType": 4, "isComplete": True}]

        self.assertFalse(
            behavior.dynamic_quest_observe_final_completion_item_allowed(
                args,
                observe_items,
                completion_item_seen=True,
                followup_hunt_started=True,
            )
        )
        self.assertTrue(
            behavior.dynamic_quest_observe_final_completion_item_allowed(
                args,
                complete_items,
                completion_item_seen=True,
                followup_hunt_started=True,
            )
        )

    def test_hunter_api_rescan_lost_target_requires_stale_unseen_target(self) -> None:
        args = argparse.Namespace(
            hunter=True,
            target_loss_rescan=True,
            hunter_target_api_scout=True,
            dynamic_quest_target_api_scout=False,
            dynamic_quest_return_after_required_target=False,
            dynamic_quest_observe_final_progress=False,
        )

        self.assertTrue(
            behavior.should_hunter_api_rescan_lost_target(
                args,
                current_target=123,
                current_target_visible=False,
                fresh_api_observation=False,
                selected_npc=None,
            )
        )
        self.assertFalse(
            behavior.should_hunter_api_rescan_lost_target(
                args,
                current_target=123,
                current_target_visible=True,
                fresh_api_observation=False,
                selected_npc=None,
            )
        )
        self.assertFalse(
            behavior.should_hunter_api_rescan_lost_target(
                args,
                current_target=123,
                current_target_visible=False,
                fresh_api_observation=True,
                selected_npc=None,
            )
        )

    def test_expected_final_match_waits_only_for_nonterminal_followup_wait_node(self) -> None:
        self.assertTrue(
            behavior.dynamic_quest_expected_final_match_is_followup_wait_node(
                [{"currentNodeId": "observe_signal", "currentNodeType": 6}],
                "observe_signal",
            )
        )
        self.assertFalse(
            behavior.dynamic_quest_expected_final_match_is_followup_wait_node(
                [{"currentNodeId": "complete", "currentNodeType": 4}],
                "complete",
            )
        )

    def test_followup_hunt_keeps_close_arrival_but_wide_engagement_defaults(self) -> None:
        followup_home = behavior.PathPoint(510381, 492106, 2811)
        args = argparse.Namespace(
            dynamic_quest_expected_final_node="observe_signal",
            dynamic_quest_followup_target_name="흉포한 black wolf pup",
            dynamic_quest_followup_target_home=followup_home,
            dynamic_quest_followup_min_target_level=4,
            dynamic_quest_followup_max_target_level=4,
            dynamic_quest_followup_target_home_stop_distance=650.0,
            dynamic_quest_followup_target_home_hunt_distance=0.0,
            dynamic_quest_followup_target_home_max_distance=9000.0,
            dynamic_quest_followup_max_target_distance=9000.0,
            require_target_name="large ant",
            prefer_target_name="",
            required_target_home=None,
            required_target_home_stop_distance=2500.0,
            required_target_home_hunt_distance=9000.0,
            min_target_level=1,
            max_target_level=5,
            target_home_max_distance=9000.0,
            max_target_distance=9000.0,
            hunter_target_api_scout=False,
            hunter_target_api_radius=0.0,
            flee_home=None,
            flee_dynamic_safe_point=False,
        )

        previous = behavior.apply_dynamic_quest_followup_hunt_args(args)

        self.assertEqual(previous["required_target_home_stop_distance"], 2500.0)
        self.assertEqual(previous["required_target_home_hunt_distance"], 9000.0)
        self.assertFalse(previous["hunter_target_api_scout"])
        self.assertIsNone(previous["flee_home"])
        self.assertFalse(previous["flee_dynamic_safe_point"])
        self.assertEqual(args.required_target_home, followup_home)
        self.assertIsNone(args.flee_home)
        self.assertTrue(args.flee_dynamic_safe_point)
        self.assertEqual(args.required_target_home_stop_distance, 650.0)
        self.assertEqual(args.required_target_home_hunt_distance, 9000.0)
        self.assertEqual(args.require_target_name, "흉포한 black wolf pup")
        self.assertEqual(args.min_target_level, 4)
        self.assertEqual(args.max_target_level, 4)
        self.assertTrue(args.hunter_target_api_scout)
        self.assertEqual(args.hunter_target_api_radius, 9000.0)

    def test_followup_hunt_keeps_existing_flee_home_separate_from_target_home(self) -> None:
        followup_home = behavior.PathPoint(510381, 492106, 2811)
        safe_home = behavior.PathPoint(532069, 479749, 2220)
        args = argparse.Namespace(
            dynamic_quest_expected_final_node="observe_signal",
            dynamic_quest_followup_target_name="흉포한 black wolf pup",
            dynamic_quest_followup_target_home=followup_home,
            dynamic_quest_followup_min_target_level=4,
            dynamic_quest_followup_max_target_level=4,
            dynamic_quest_followup_target_home_stop_distance=650.0,
            dynamic_quest_followup_target_home_hunt_distance=9000.0,
            dynamic_quest_followup_target_home_max_distance=9000.0,
            dynamic_quest_followup_max_target_distance=9000.0,
            require_target_name="large ant",
            prefer_target_name="",
            required_target_home=None,
            required_target_home_stop_distance=2500.0,
            required_target_home_hunt_distance=9000.0,
            min_target_level=1,
            max_target_level=5,
            target_home_max_distance=9000.0,
            max_target_distance=9000.0,
            flee_home=safe_home,
            flee_dynamic_safe_point=False,
        )

        behavior.apply_dynamic_quest_followup_hunt_args(args)

        self.assertEqual(args.required_target_home, followup_home)
        self.assertEqual(args.flee_home, safe_home)
        self.assertTrue(args.flee_dynamic_safe_point)

    def test_cached_explore_destination_reached_uses_radius_stop_distance(self) -> None:
        destination = (
            behavior.destination_from_point("dynamic-quest-explore", 1000, 1000, 0),
            450,
            1,
            "trace",
        )

        self.assertTrue(
            behavior.dynamic_quest_explore_cached_destination_reached(
                PositionClient(1440, 1000),
                destination,
            )
        )
        self.assertFalse(
            behavior.dynamic_quest_explore_cached_destination_reached(
                PositionClient(1460, 1000),
                destination,
            )
        )

    def test_explore_move_stop_distance_stays_inside_server_radius(self) -> None:
        self.assertEqual(behavior.dynamic_quest_explore_move_stop_distance(450), 225.0)
        self.assertEqual(behavior.dynamic_quest_explore_progress_reached_distance(450), 450.0)

    def test_explore_movement_yields_when_rescue_target_is_active(self) -> None:
        args = argparse.Namespace(
            party_rescue_aggro=True,
            party_rescue_max_age=10.0,
            require_target_name="",
            dynamic_quest_followup_target_name="",
        )
        snapshot = {
            "rescue_target_id": 17582,
            "rescue_target_name": "vendo flayer",
            "rescue_requested_at": 95.0,
        }

        self.assertTrue(
            behavior.dynamic_quest_explore_should_yield_to_rescue(
                args,
                snapshot,
                now=100.0,
            )
        )

    def test_explore_movement_keeps_driving_when_rescue_target_is_expired(self) -> None:
        args = argparse.Namespace(
            party_rescue_aggro=True,
            party_rescue_max_age=2.0,
            require_target_name="",
            dynamic_quest_followup_target_name="",
        )
        snapshot = {
            "rescue_target_id": 17582,
            "rescue_target_name": "vendo flayer",
            "rescue_requested_at": 95.0,
        }

        self.assertFalse(
            behavior.dynamic_quest_explore_should_yield_to_rescue(
                args,
                snapshot,
                now=100.0,
            )
        )

    def test_explore_movement_yields_to_current_quest_target_without_party_rescue_aggro(self) -> None:
        args = argparse.Namespace(
            party_rescue_aggro=False,
            party_rescue_max_age=10.0,
            require_target_name="vendo flayer",
            dynamic_quest_followup_target_name="",
        )
        snapshot = {
            "rescue_target_id": 17582,
            "rescue_target_name": "vendo flayer",
            "rescue_requested_at": 95.0,
        }

        self.assertTrue(
            behavior.dynamic_quest_explore_should_yield_to_rescue(
                args,
                snapshot,
                now=100.0,
            )
        )

    def test_explore_movement_ignores_unrelated_rescue_without_party_rescue_aggro(self) -> None:
        args = argparse.Namespace(
            party_rescue_aggro=False,
            party_rescue_max_age=10.0,
            require_target_name="vendo flayer",
            dynamic_quest_followup_target_name="",
        )
        snapshot = {
            "rescue_target_id": 17582,
            "rescue_target_name": "unrelated add",
            "rescue_requested_at": 95.0,
        }

        self.assertFalse(
            behavior.dynamic_quest_explore_should_yield_to_rescue(
                args,
                snapshot,
                now=100.0,
            )
        )

    def test_expected_quest_id_keeps_progress_item_after_followup_target_swap(self) -> None:
        args = argparse.Namespace(
            dynamic_quest_expected_quest_id="seed-1",
            require_target_name="흉포한 black wolf pup",
            startup_service_npc_name="Sir Lukas",
        )
        snapshot = {
            "active": [
                {
                    "questId": "seed-1",
                    "targetName": "large ant",
                    "startNpcName": "Sir Lukas",
                    "isComplete": True,
                    "currentNodeId": "complete",
                    "currentNodeType": 4,
                }
            ]
        }

        active = behavior.dynamic_quest_progress_active_items(snapshot, args)

        self.assertEqual(len(active), 1)
        self.assertTrue(behavior.dynamic_quest_progress_has_completed_item(snapshot, args))


if __name__ == "__main__":
    unittest.main()
