#!/usr/bin/env python3
"""Unit checks for dynamic quest story-cache evaluation planning."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("plan-dummy-dynamic-quest-cache-evaluation.py")
    spec = importlib.util.spec_from_file_location("dynamic_quest_cache_evaluation_plan_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


planner = load_module()


class DynamicQuestCacheEvaluationPlanTests(unittest.TestCase):
    def test_build_plans_selects_unevaluated_ready_rows(self) -> None:
        args = planner.parse_args(["--max-plans", "10"])
        payload = {
            "items": [
                {
                    "templateId": "ready-unevaluated",
                    "readyForUse": True,
                    "dummyEvaluationCount": 0,
                    "realm": "Albion",
                    "targetNameHint": "forest spiderling",
                    "startMode": "AutoAccept",
                    "branchWorldSignal": "mob-growth:killed:region:1",
                    "tags": ["branch:mob-growth", "world-signal:mob-growth:killed:region:1"],
                },
                {
                    "templateId": "ready-evaluated",
                    "readyForUse": True,
                    "dummyEvaluationCount": 1,
                    "realm": "Albion",
                    "targetNameHint": "river spraggon",
                    "startMode": "AutoAccept",
                    "tags": ["branch:mob-growth"],
                },
                {
                    "templateId": "not-ready",
                    "readyForUse": False,
                    "dummyEvaluationCount": 0,
                    "realm": "Midgard",
                    "targetNameHint": "young lynx",
                    "startMode": "AutoAccept",
                    "tags": ["branch:time-window"],
                },
            ]
        }

        plans = planner.build_plans(payload, args)

        self.assertEqual([plan.template_id for plan in plans], ["ready-unevaluated"])
        command = plans[0].command
        self.assertIn("--require-live-quest-target", command)
        self.assertIn("forest spiderling", command)
        self.assertIn("--dynamic-quest-followup-growth-target", command)
        self.assertIn("--require-world-signal", command)
        self.assertIn("mob-growth:killed:region:1", command)

    def test_item_acquired_plan_requires_world_signal_timeline_and_trigger(self) -> None:
        args = planner.parse_args(["--realm", "hib", "--party-size", "2", "--player-level", "7"])
        payload = {
            "items": [
                {
                    "templateId": "hib-item",
                    "readyForUse": True,
                    "dummyEvaluationCount": 0,
                    "realm": "Hibernia",
                    "targetNameHint": "lough wolf cadger",
                    "startMode": "AutoAccept",
                    "branchWorldSignal": "item-acquired",
                    "tags": ["branch:item-acquired", "world-signal:item-acquired"],
                }
            ]
        }

        plan = planner.build_plans(payload, args)[0]
        command_text = " ".join(plan.command)

        self.assertEqual(plan.realm_key, "hib")
        self.assertIn("--party-sizes 2", command_text)
        self.assertIn("--player-level 7", command_text)
        self.assertIn("quest_accepted,node_advanced,choice_selected,world_signal,quest_completed", command_text)
        self.assertIn("OnAccept,OnExplore,OnChoiceShown,OnChoiceSelected,OnWorldSignal,OnComplete", command_text)

    def test_include_evaluated_allows_rechecking_passing_rows(self) -> None:
        args = planner.parse_args(["--include-evaluated"])
        payload = {
            "items": [
                {
                    "templateId": "evaluated",
                    "readyForUse": True,
                    "dummyEvaluationCount": 3,
                    "dummyEvaluationScore": 100,
                    "realm": "Midgard",
                    "targetNameHint": "young lynx",
                    "startMode": "NpcOffer",
                    "branchWorldSignal": "time-window",
                    "tags": ["branch:time-window", "world-signal:time-window"],
                }
            ]
        }

        plans = planner.build_plans(payload, args)

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].start_mode, "NpcOffer")
        self.assertIn("--quest-start-mode", plans[0].command)
        self.assertIn("npc", plans[0].command)

    def test_build_plans_round_robins_across_realms_and_branches(self) -> None:
        args = planner.parse_args(["--max-plans", "3"])
        payload = {
            "items": [
                {
                    "templateId": "alb-high",
                    "readyForUse": True,
                    "dummyEvaluationCount": 0,
                    "realm": "Albion",
                    "targetNameHint": "aged beech",
                    "startMode": "AutoAccept",
                    "branchWorldSignal": "mob-growth:killed:region:1",
                    "minLevel": 30,
                    "maxLevel": 35,
                    "tags": ["branch:mob-growth"],
                },
                {
                    "templateId": "alb-low",
                    "readyForUse": True,
                    "dummyEvaluationCount": 0,
                    "realm": "Albion",
                    "targetNameHint": "ant drone",
                    "startMode": "AutoAccept",
                    "branchWorldSignal": "mob-growth:killed:region:1",
                    "minLevel": 1,
                    "maxLevel": 3,
                    "tags": ["branch:mob-growth"],
                },
                {
                    "templateId": "hib-low",
                    "readyForUse": True,
                    "dummyEvaluationCount": 0,
                    "realm": "Hibernia",
                    "targetNameHint": "lough wolf cadger",
                    "startMode": "AutoAccept",
                    "branchWorldSignal": "item-acquired",
                    "minLevel": 1,
                    "maxLevel": 3,
                    "tags": ["branch:item-acquired"],
                },
                {
                    "templateId": "mid-low",
                    "readyForUse": True,
                    "dummyEvaluationCount": 0,
                    "realm": "Midgard",
                    "targetNameHint": "young lynx",
                    "startMode": "AutoAccept",
                    "branchWorldSignal": "time-window",
                    "minLevel": 1,
                    "maxLevel": 3,
                    "tags": ["branch:time-window"],
                },
            ]
        }

        plans = planner.build_plans(payload, args)

        self.assertEqual([plan.template_id for plan in plans], ["alb-low", "hib-low", "mid-low"])
        self.assertEqual({plan.realm_key for plan in plans}, {"alb", "hib", "mid"})

    def test_live_only_requires_matching_current_offer(self) -> None:
        args = planner.parse_args(["--live-only", "--max-plans", "10"])
        payload = {
            "items": [
                {
                    "templateId": "matching-cache-row",
                    "readyForUse": True,
                    "dummyEvaluationCount": 0,
                    "realm": "Albion",
                    "targetNameHint": "forest spiderling",
                    "startMode": "AutoAccept",
                    "branchWorldSignal": "mob-growth:killed:region:1",
                    "tags": ["branch:mob-growth", "world-signal:mob-growth:killed:region:1"],
                },
                {
                    "templateId": "missing-live-row",
                    "readyForUse": True,
                    "dummyEvaluationCount": 0,
                    "realm": "Albion",
                    "targetNameHint": "river spraggon",
                    "startMode": "AutoAccept",
                    "branchWorldSignal": "mob-growth:killed:region:1",
                    "tags": ["branch:mob-growth", "world-signal:mob-growth:killed:region:1"],
                },
                {
                    "templateId": "wrong-branch-row",
                    "readyForUse": True,
                    "dummyEvaluationCount": 0,
                    "realm": "Albion",
                    "targetNameHint": "forest spiderling",
                    "startMode": "AutoAccept",
                    "branchWorldSignal": "item-acquired",
                    "tags": ["branch:item-acquired", "world-signal:item-acquired"],
                },
            ]
        }
        live_payload = {
            "quests": [
                {
                    "id": "live-quest-1",
                    "realm": "Albion",
                    "targetName": "forest spiderling",
                    "startMode": 2,
                    "tags": ["branch:mob-growth", "world-signal:mob-growth:killed:region:1"],
                }
            ]
        }

        plans = planner.build_plans(payload, args, live_payload)

        self.assertEqual([plan.template_id for plan in plans], ["matching-cache-row"])
        self.assertEqual(plans[0].live_quest_id, "live-quest-1")
        self.assertEqual(planner.plan_to_dict(plans[0])["liveQuestId"], "live-quest-1")


if __name__ == "__main__":
    unittest.main()
