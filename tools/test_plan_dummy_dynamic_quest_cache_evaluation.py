#!/usr/bin/env python3
"""Unit checks for dynamic quest story-cache evaluation planning."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


def load_module():
    module_path = Path(__file__).with_name("plan-dummy-dynamic-quest-cache-evaluation.py")
    spec = importlib.util.spec_from_file_location("plan_dynamic_quest_cache_evaluation_for_tests", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


planner = load_module()


class DynamicQuestCacheEvaluationPlanTests(unittest.TestCase):
    def test_linear_plan_does_not_require_choice_events(self) -> None:
        args = planner.parse_args(["--include-offer-blocked"])
        row = {
            "templateId": "seed-1-linear",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "ant drone",
            "readyForUse": True,
            "offerEligible": False,
            "dummyEvaluationCount": 0,
        }

        plans = planner.build_plans({"items": [row]}, args)

        self.assertEqual(len(plans), 1)
        events = plans[0].command[plans[0].command.index("--dynamic-quest-require-timeline-events") + 1]
        triggers = plans[0].command[plans[0].command.index("--dynamic-quest-require-presentation-triggers") + 1]
        self.assertNotIn("choice_selected", events)
        self.assertNotIn("OnChoiceShown", triggers)
        self.assertNotIn("OnChoiceSelected", triggers)
        self.assertIn("quest_completed", events)
        self.assertIn("quest_rewarded", events)
        self.assertIn("OnComplete", triggers)

    def test_branch_plan_requires_choice_events(self) -> None:
        args = planner.parse_args(["--include-offer-blocked"])
        row = {
            "templateId": "seed-1-branch",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "ant drone",
            "branchWorldSignal": "item-acquired:quest-token",
            "tags": ["branch:item-acquired"],
            "readyForUse": True,
            "offerEligible": False,
            "dummyEvaluationCount": 0,
        }

        plans = planner.build_plans({"items": [row]}, args)

        self.assertEqual(len(plans), 1)
        events = plans[0].command[plans[0].command.index("--dynamic-quest-require-timeline-events") + 1]
        triggers = plans[0].command[plans[0].command.index("--dynamic-quest-require-presentation-triggers") + 1]
        self.assertIn("choice_selected", events)
        self.assertIn("world_signal", events)
        self.assertIn("OnChoiceShown", triggers)
        self.assertIn("OnChoiceSelected", triggers)
        self.assertIn("OnWorldSignal", triggers)

    def test_live_only_matches_rebound_quest_by_template_tag_and_uses_live_target(self) -> None:
        args = planner.parse_args(["--live-only", "--accounts-pattern", "tools/dummy-accounts-dq-{realm_slug}-12.csv"])
        row = {
            "templateId": "seed-1-rebound",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "old unsafe target",
            "branchWorldSignal": "mob-growth:killed:region:1",
            "tags": ["branch:mob-growth"],
            "readyForUse": True,
            "dummyEvaluationCount": 0,
        }
        live_payload = {
            "quests": [
                {
                    "id": "runtime-quest-1",
                    "realm": "Albion",
                    "startMode": "AutoAccept",
                    "targetName": "safe rebound target",
                    "minLevel": 2,
                    "maxLevel": 2,
                    "tags": ["template:seed-1-rebound", "branch:mob-growth", "world-signal:mob-growth:killed:region:1"],
                }
            ]
        }

        plans = planner.build_plans({"items": [row]}, args, live_payload)

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].live_quest_id, "runtime-quest-1")
        self.assertEqual(plans[0].target_name, "safe rebound target")
        self.assertEqual(plans[0].player_level, 2)
        target_index = plans[0].command.index("--require-live-quest-target") + 1
        self.assertEqual(plans[0].command[target_index], "safe rebound target")
        template_index = plans[0].command.index("--require-live-quest-template") + 1
        self.assertEqual(plans[0].command[template_index], "seed-1-rebound")
        level_index = plans[0].command.index("--player-level") + 1
        self.assertEqual(plans[0].command[level_index], "2")
        accounts_index = plans[0].command.index("--accounts-pattern") + 1
        self.assertEqual(plans[0].command[accounts_index], "tools/dummy-accounts-dq-{realm_slug}-12.csv")
        self.assertIn("--prefer-melee-smoke-accounts", plans[0].command)
        self.assertIn("--no-require-melee-smoke-accounts", plans[0].command)

    def test_offer_blocked_rows_are_excluded_by_default(self) -> None:
        args = planner.parse_args([])
        row = {
            "templateId": "seed-1-needs-dummy",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "forest spiderling",
            "readyForUse": True,
            "offerEligible": False,
            "offerBlockReasons": ["dummy_evaluation_required"],
            "dummyEvaluationCount": 0,
        }

        plans = planner.build_plans({"items": [row]}, args)

        self.assertEqual(plans, [])

    def test_offer_blocked_rows_can_be_included_explicitly(self) -> None:
        args = planner.parse_args(["--include-offer-blocked"])
        row = {
            "templateId": "seed-1-needs-dummy",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "forest spiderling",
            "readyForUse": True,
            "offerEligible": False,
            "offerBlockReasons": ["dummy_evaluation_required"],
            "dummyEvaluationCount": 0,
        }

        plans = planner.build_plans({"items": [row]}, args)

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].template_id, "seed-1-needs-dummy")

    def test_prepare_evaluation_offers_builds_runnable_plan_for_offer_blocked_row(self) -> None:
        args = planner.parse_args(["--prepare-evaluation-offers"])
        row = {
            "templateId": "seed-1-needs-dummy",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "old target",
            "readyForUse": True,
            "offerEligible": False,
            "offerBlockReasons": ["dummy_evaluation_required"],
            "dummyEvaluationCount": 0,
        }
        original_prepare = planner.prepare_evaluation_offer

        def fake_prepare(_row, _args):
            return {
                "id": "runtime-seed-1-needs-dummy",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetName": "prepared target",
                "minLevel": 2,
                "maxLevel": 2,
                "tags": ["template:seed-1-needs-dummy"],
            }

        try:
            planner.prepare_evaluation_offer = fake_prepare
            plans = planner.build_plans({"items": [row]}, args, {"quests": []})
        finally:
            planner.prepare_evaluation_offer = original_prepare

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].live_quest_id, "runtime-seed-1-needs-dummy")
        self.assertEqual(plans[0].target_name, "prepared target")
        self.assertEqual(plans[0].player_level, 2)
        target_index = plans[0].command.index("--require-live-quest-target") + 1
        self.assertEqual(plans[0].command[target_index], "prepared target")
        template_index = plans[0].command.index("--require-live-quest-template") + 1
        self.assertEqual(plans[0].command[template_index], "seed-1-needs-dummy")
        level_index = plans[0].command.index("--player-level") + 1
        self.assertEqual(plans[0].command[level_index], "2")

    def test_prepare_evaluation_offers_skips_failed_prepare_until_max_plans_are_filled(self) -> None:
        args = planner.parse_args(["--prepare-evaluation-offers", "--max-plans", "2"])
        rows = [
            {
                "templateId": "seed-1-prepare-fails",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "old target",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
            },
            {
                "templateId": "seed-100-prepared",
                "realm": "Midgard",
                "startMode": "AutoAccept",
                "targetNameHint": "old target",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
            },
            {
                "templateId": "seed-200-prepared",
                "realm": "Hibernia",
                "startMode": "AutoAccept",
                "targetNameHint": "old target",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
            },
        ]
        original_prepare = planner.prepare_evaluation_offer

        def fake_prepare(row, _args):
            template_id = planner.text_value(row.get("templateId"))
            if template_id == "seed-1-prepare-fails":
                return None
            return {
                "id": template_id,
                "realm": row["realm"],
                "startMode": "AutoAccept",
                "targetName": f"{template_id}-target",
                "minLevel": 5,
                "maxLevel": 5,
                "tags": [f"template:{template_id}"],
            }

        try:
            planner.prepare_evaluation_offer = fake_prepare
            plans = planner.build_plans({"items": rows}, args, {"quests": []})
        finally:
            planner.prepare_evaluation_offer = original_prepare

        self.assertEqual(
            sorted(plan.template_id for plan in plans),
            ["seed-100-prepared", "seed-200-prepared"],
        )
        self.assertEqual(len(plans), 2)

    def test_prepare_evaluation_offers_stops_at_max_prepare_attempts(self) -> None:
        args = planner.parse_args(["--prepare-evaluation-offers", "--max-plans", "2", "--max-prepare-attempts", "2"])
        rows = [
            {
                "templateId": "seed-1-prepare-fails-a",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "old target",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
            },
            {
                "templateId": "seed-1-prepare-fails-b",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "old target",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
            },
            {
                "templateId": "seed-1-prepared-after-limit",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "old target",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
            },
        ]
        original_prepare = planner.prepare_evaluation_offer
        seen: list[str] = []

        def fake_prepare(row, _args):
            template_id = planner.text_value(row.get("templateId"))
            seen.append(template_id)
            if template_id.startswith("seed-1-prepare-fails"):
                return None
            return {
                "id": template_id,
                "realm": row["realm"],
                "startMode": "AutoAccept",
                "targetName": f"{template_id}-target",
                "minLevel": 5,
                "maxLevel": 5,
                "tags": [f"template:{template_id}"],
            }

        try:
            planner.prepare_evaluation_offer = fake_prepare
            plans = planner.build_plans({"items": rows}, args, {"quests": []})
        finally:
            planner.prepare_evaluation_offer = original_prepare

        self.assertEqual(plans, [])
        self.assertEqual(seen, ["seed-1-prepare-fails-a", "seed-1-prepare-fails-b"])

    def test_prepare_evaluation_offer_uses_configured_timeout_and_failed_evaluation_flag(self) -> None:
        args = planner.parse_args([
            "--prepare-evaluation-offers",
            "--evaluation-offer-timeout",
            "90",
            "--allow-failed-evaluation-offers",
        ])
        row = {"templateId": "seed-1-timeout"}
        original_urlopen = planner.urllib.request.urlopen
        seen: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def read(self):
                return b'{"success":true,"quest":{"id":"runtime","tags":["template:seed-1-timeout"]}}'

        def fake_urlopen(request, timeout=0):
            seen["timeout"] = timeout
            seen["body"] = planner.json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        try:
            planner.urllib.request.urlopen = fake_urlopen
            quest = planner.prepare_evaluation_offer(row, args)
        finally:
            planner.urllib.request.urlopen = original_urlopen

        self.assertEqual(seen["timeout"], 90.0)
        self.assertEqual(seen["body"]["templateId"], "seed-1-timeout")
        self.assertTrue(seen["body"]["allowFailedDummyEvaluation"])
        self.assertEqual(quest["id"], "runtime")

    def test_prepare_evaluation_offer_respects_short_configured_timeout(self) -> None:
        args = planner.parse_args(["--prepare-evaluation-offers", "--evaluation-offer-timeout", "3"])
        row = {"templateId": "seed-1-short-timeout"}
        original_urlopen = planner.urllib.request.urlopen
        seen: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def read(self):
                return b'{"success":true,"quest":{"id":"runtime","tags":["template:seed-1-short-timeout"]}}'

        def fake_urlopen(request, timeout=0):
            seen["timeout"] = timeout
            return FakeResponse()

        try:
            planner.urllib.request.urlopen = fake_urlopen
            quest = planner.prepare_evaluation_offer(row, args)
        finally:
            planner.urllib.request.urlopen = original_urlopen

        self.assertEqual(seen["timeout"], 3.0)
        self.assertEqual(quest["id"], "runtime")

    def test_prepare_evaluation_offer_auto_allows_filtered_dummy_failure_reevaluation(self) -> None:
        args = planner.parse_args([
            "--prepare-evaluation-offers",
            "--offer-block-reason",
            "dummy_evaluation_difficulty_failed",
        ])
        row = {
            "templateId": "seed-1-difficulty-reeval",
            "offerBlockReasons": ["dummy_evaluation_difficulty_failed", "dummy_evaluation_not_passing"],
        }
        original_urlopen = planner.urllib.request.urlopen
        seen: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def read(self):
                return b'{"success":true,"quest":{"id":"runtime","tags":["template:seed-1-difficulty-reeval"]}}'

        def fake_urlopen(request, timeout=0):
            seen["body"] = planner.json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        try:
            planner.urllib.request.urlopen = fake_urlopen
            quest = planner.prepare_evaluation_offer(row, args)
        finally:
            planner.urllib.request.urlopen = original_urlopen

        self.assertTrue(seen["body"]["allowFailedDummyEvaluation"])
        self.assertEqual(quest["id"], "runtime")

    def test_prepare_evaluation_offer_does_not_auto_allow_required_dummy_evaluation(self) -> None:
        args = planner.parse_args(["--prepare-evaluation-offers"])
        row = {
            "templateId": "seed-1-needs-first-eval",
            "offerBlockReasons": ["dummy_evaluation_required"],
        }
        original_urlopen = planner.urllib.request.urlopen
        seen: dict[str, object] = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_exc):
                return False

            def read(self):
                return b'{"success":true,"quest":{"id":"runtime","tags":["template:seed-1-needs-first-eval"]}}'

        def fake_urlopen(request, timeout=0):
            seen["body"] = planner.json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        try:
            planner.urllib.request.urlopen = fake_urlopen
            quest = planner.prepare_evaluation_offer(row, args)
        finally:
            planner.urllib.request.urlopen = original_urlopen

        self.assertFalse(seen["body"]["allowFailedDummyEvaluation"])
        self.assertEqual(quest["id"], "runtime")

    def test_default_player_level_uses_cache_min_level(self) -> None:
        args = planner.parse_args(["--include-offer-blocked"])
        row = {
            "templateId": "seed-1-level-17",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "aged basilisk",
            "readyForUse": True,
            "offerEligible": False,
            "dummyEvaluationCount": 0,
            "minLevel": 17,
            "maxLevel": 21,
        }

        plans = planner.build_plans({"items": [row]}, args)

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].player_level, 17)
        level_index = plans[0].command.index("--player-level") + 1
        self.assertEqual(plans[0].command[level_index], "17")

    def test_explicit_player_level_overrides_cache_level(self) -> None:
        args = planner.parse_args(["--include-offer-blocked", "--player-level", "5"])
        row = {
            "templateId": "seed-1-level-17",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "aged basilisk",
            "readyForUse": True,
            "offerEligible": False,
            "dummyEvaluationCount": 0,
            "minLevel": 17,
            "maxLevel": 21,
        }

        plans = planner.build_plans({"items": [row]}, args)

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].player_level, 5)
        level_index = plans[0].command.index("--player-level") + 1
        self.assertEqual(plans[0].command[level_index], "5")

    def test_dummy_failure_reevaluation_player_level_keeps_cache_minimum_floor(self) -> None:
        args = planner.parse_args(["--include-evaluated", "--include-not-ready", "--include-offer-blocked"])
        row = {
            "templateId": "seed-1-difficulty-repair",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "ant drone",
            "readyForUse": False,
            "offerEligible": False,
            "offerBlockReasons": ["dummy_evaluation_difficulty_failed", "dummy_evaluation_not_passing"],
            "dummyEvaluationCount": 2,
            "minLevel": 8,
            "maxLevel": 12,
        }
        live_quest = {
            "id": "seed-1-difficulty-repair",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetName": "ant drone",
            "minLevel": 1,
            "maxLevel": 2,
            "tags": ["template:seed-1-difficulty-repair"],
        }

        plans = planner.build_plans({"items": [row]}, args, {"quests": [live_quest]})

        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].player_level, 8)
        level_index = plans[0].command.index("--player-level") + 1
        self.assertEqual(plans[0].command[level_index], "8")

    def test_offer_block_reason_and_level_filters_select_reevaluation_candidates(self) -> None:
        args = planner.parse_args([
            "--include-evaluated",
            "--include-not-ready",
            "--include-offer-blocked",
            "--offer-block-reason",
            "dummy_evaluation_difficulty_failed",
            "--min-player-level",
            "8",
            "--max-player-level",
            "12",
        ])
        rows = [
            {
                "templateId": "seed-1-too-low",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "ant drone",
                "readyForUse": False,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_difficulty_failed", "dummy_evaluation_not_passing"],
                "dummyEvaluationCount": 1,
                "minLevel": 1,
                "maxLevel": 4,
            },
            {
                "templateId": "seed-1-selected",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "Aithne Con",
                "readyForUse": False,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_difficulty_failed", "dummy_evaluation_not_passing"],
                "dummyEvaluationCount": 1,
                "minLevel": 8,
                "maxLevel": 12,
            },
            {
                "templateId": "seed-1-runtime",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "Aldous Wynedd",
                "readyForUse": False,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_runtime_failed", "dummy_evaluation_not_passing"],
                "dummyEvaluationCount": 1,
                "minLevel": 8,
                "maxLevel": 12,
            },
        ]

        plans = planner.build_plans({"items": rows}, args)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-selected"])
        self.assertEqual(plans[0].player_level, 8)

    def test_max_dummy_evaluation_count_filter_skips_over_retried_rows(self) -> None:
        args = planner.parse_args([
            "--include-evaluated",
            "--include-not-ready",
            "--include-offer-blocked",
            "--offer-block-reason",
            "dummy_evaluation_difficulty_failed",
            "--max-dummy-evaluation-count",
            "2",
        ])
        rows = [
            {
                "templateId": "seed-1-over-retried",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "ant drone",
                "readyForUse": False,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_difficulty_failed"],
                "dummyEvaluationCount": 3,
                "minLevel": 1,
                "maxLevel": 4,
            },
            {
                "templateId": "seed-1-under-limit",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "black wolf pup",
                "readyForUse": False,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_difficulty_failed"],
                "dummyEvaluationCount": 2,
                "minLevel": 1,
                "maxLevel": 4,
            },
        ]

        plans = planner.build_plans({"items": rows}, args)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-under-limit"])

    def test_dummy_failure_reevaluation_does_not_reuse_target_only_live_quest(self) -> None:
        row = {
            "templateId": "seed-1-failed-template",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "ant drone",
            "offerBlockReasons": ["dummy_evaluation_difficulty_failed", "dummy_evaluation_not_passing"],
        }
        live_payload = {
            "quests": [
                {
                    "id": "seed-1-other-live",
                    "realm": "Albion",
                    "startMode": "AutoAccept",
                    "targetName": "ant drone",
                    "tags": ["template:seed-1-other-live"],
                }
            ]
        }

        self.assertIsNone(planner.find_live_quest(row, live_payload))

    def test_dummy_failure_reevaluation_reuses_exact_template_live_quest(self) -> None:
        row = {
            "templateId": "seed-1-failed-template",
            "realm": "Albion",
            "startMode": "AutoAccept",
            "targetNameHint": "ant drone",
            "offerBlockReasons": ["dummy_evaluation_difficulty_failed", "dummy_evaluation_not_passing"],
        }
        live_payload = {
            "quests": [
                {
                    "id": "runtime-quest",
                    "realm": "Albion",
                    "startMode": "AutoAccept",
                    "targetName": "ant drone",
                    "tags": ["template:seed-1-failed-template"],
                }
            ]
        }

        quest = planner.find_live_quest(row, live_payload)

        self.assertIsNotNone(quest)
        self.assertEqual(quest["id"], "runtime-quest")

    def test_dummy_failure_reevaluation_prioritizes_low_retry_rows(self) -> None:
        args = planner.parse_args([
            "--include-evaluated",
            "--include-not-ready",
            "--include-offer-blocked",
            "--offer-block-reason",
            "dummy_evaluation_difficulty_failed",
            "--max-plans",
            "2",
        ])
        rows = [
            {
                "templateId": "seed-1-many-failures",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "ant drone",
                "readyForUse": False,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_difficulty_failed"],
                "dummyEvaluationCount": 12,
                "minLevel": 1,
                "maxLevel": 4,
            },
            {
                "templateId": "seed-1-fresh-failure",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "black wolf pup",
                "readyForUse": False,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_difficulty_failed"],
                "dummyEvaluationCount": 1,
                "minLevel": 8,
                "maxLevel": 12,
            },
        ]

        plans = planner.build_plans({"items": rows}, args)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-fresh-failure", "seed-1-many-failures"])

    def test_action_scene_cohesion_filters_select_missing_metric_rows(self) -> None:
        args = planner.parse_args([
            "--include-evaluated",
            "--include-not-ready",
            "--include-offer-blocked",
            "--missing-action-scene-cohesion",
            "--max-action-scene-cohesion",
            "0",
        ])
        rows = [
            {
                "templateId": "seed-1-missing-action-scene",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "ant drone",
                "readyForUse": False,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_difficulty_failed"],
                "dummyEvaluationCount": 1,
                "dummyActionSceneCohesionScore": 0,
                "minLevel": 1,
            },
            {
                "templateId": "seed-1-good-action-scene",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "black wolf pup",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationCount": 2,
                "dummyActionSceneCohesionScore": 100,
                "minLevel": 1,
            },
            {
                "templateId": "seed-1-unevaluated",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "forest spiderling",
                "readyForUse": True,
                "offerEligible": False,
                "dummyEvaluationCount": 0,
                "dummyActionSceneCohesionScore": 0,
                "minLevel": 1,
            },
        ]

        plans = planner.build_plans({"items": rows}, args)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-missing-action-scene"])
        self.assertEqual(plans[0].dummy_action_scene_cohesion_score, 0)
        self.assertEqual(planner.plan_to_dict(plans[0])["dummyActionSceneCohesionScore"], 0)

    def test_model_role_fit_filters_select_missing_metric_rows(self) -> None:
        args = planner.parse_args([
            "--include-evaluated",
            "--include-not-ready",
            "--include-offer-blocked",
            "--missing-cinematic-model-role-fit",
            "--max-cinematic-model-role-fit",
            "0",
        ])
        rows = [
            {
                "templateId": "seed-1-missing-model-role-fit",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "ant drone",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationCount": 1,
                "dummyActionSceneCohesionScore": 100,
                "dummyCinematicCatalogRoleVariety": 0,
                "dummyCinematicModelRoleFitScore": 0,
                "minLevel": 1,
            },
            {
                "templateId": "seed-1-good-model-role-fit",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "black wolf pup",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationCount": 2,
                "dummyActionSceneCohesionScore": 100,
                "dummyCinematicCatalogRoleVariety": 3,
                "dummyCinematicModelRoleFitScore": 100,
                "minLevel": 1,
            },
            {
                "templateId": "seed-1-unevaluated",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "forest spiderling",
                "readyForUse": True,
                "offerEligible": False,
                "dummyEvaluationCount": 0,
                "dummyActionSceneCohesionScore": 0,
                "dummyCinematicCatalogRoleVariety": 0,
                "dummyCinematicModelRoleFitScore": 0,
                "minLevel": 1,
            },
        ]

        plans = planner.build_plans({"items": rows}, args)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-missing-model-role-fit"])
        self.assertEqual(plans[0].dummy_cinematic_catalog_role_variety, 0)
        self.assertEqual(plans[0].dummy_cinematic_model_role_fit_score, 0)
        plan_dict = planner.plan_to_dict(plans[0])
        self.assertEqual(plan_dict["dummyCinematicCatalogRoleVariety"], 0)
        self.assertEqual(plan_dict["dummyCinematicModelRoleFitScore"], 0)
        catalog_index = plans[0].command.index("--dynamic-quest-min-cinematic-catalog-role-variety") + 1
        role_fit_index = plans[0].command.index("--dynamic-quest-min-cinematic-model-role-fit") + 1
        self.assertEqual(plans[0].command[catalog_index], "2")
        self.assertEqual(plans[0].command[role_fit_index], "75")

    def test_model_role_fit_threshold_filters_select_low_score_rows(self) -> None:
        args = planner.parse_args([
            "--include-evaluated",
            "--include-not-ready",
            "--include-offer-blocked",
            "--max-cinematic-model-role-fit",
            "69",
        ])
        rows = [
            {
                "templateId": "seed-1-low-model-role-fit",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "ant drone",
                "readyForUse": False,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_cinematic_model_role_fit_low"],
                "dummyEvaluationCount": 2,
                "dummyActionSceneCohesionScore": 100,
                "dummyCinematicCatalogRoleVariety": 3,
                "dummyCinematicModelRoleFitScore": 55,
                "minLevel": 1,
            },
            {
                "templateId": "seed-1-good-model-role-fit",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "targetNameHint": "black wolf pup",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationCount": 2,
                "dummyActionSceneCohesionScore": 100,
                "dummyCinematicCatalogRoleVariety": 3,
                "dummyCinematicModelRoleFitScore": 100,
                "minLevel": 1,
            },
        ]

        plans = planner.build_plans({"items": rows}, args)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-low-model-role-fit"])
        self.assertEqual(plans[0].dummy_cinematic_model_role_fit_score, 55)

    def test_planner_skips_unevaluated_repeat_when_target_family_already_passed(self) -> None:
        args = planner.parse_args([])
        rows = [
            {
                "templateId": "seed-1-passed-dappled",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "",
                "targetNameHint": "dappled lynx",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationScore": 100,
                "dummyEvaluationCount": 1,
                "minLevel": 24,
            },
            {
                "templateId": "seed-1-repeat-dappled",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "",
                "targetNameHint": "dappled lynx",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationScore": 0,
                "dummyEvaluationCount": 0,
                "minLevel": 25,
            },
            {
                "templateId": "seed-1-fresh-forest",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "",
                "targetNameHint": "forest snake",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationScore": 0,
                "dummyEvaluationCount": 0,
                "minLevel": 10,
            },
        ]

        plans = planner.build_plans({"items": rows}, args)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-fresh-forest"])

    def test_planner_can_include_evaluated_target_family_repeats_when_requested(self) -> None:
        args = planner.parse_args(["--include-evaluated-target-family-repeats"])
        rows = [
            {
                "templateId": "seed-1-passed-dappled",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "",
                "targetNameHint": "dappled lynx",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationScore": 100,
                "dummyEvaluationCount": 1,
                "minLevel": 24,
            },
            {
                "templateId": "seed-1-repeat-dappled",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "",
                "targetNameHint": "dappled lynx",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationScore": 0,
                "dummyEvaluationCount": 0,
                "minLevel": 25,
            },
        ]

        plans = planner.build_plans({"items": rows}, args)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-repeat-dappled"])

    def test_planner_emits_one_unevaluated_row_per_target_family_per_batch(self) -> None:
        args = planner.parse_args(["--max-plans", "3"])
        rows = [
            {
                "templateId": "seed-1-forest-snake-a",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "time-window",
                "targetNameHint": "forest snake",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationCount": 0,
                "minLevel": 10,
            },
            {
                "templateId": "seed-1-forest-snake-b",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "time-window",
                "targetNameHint": "forest snake",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationCount": 0,
                "minLevel": 11,
            },
            {
                "templateId": "seed-1-great-boar",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "",
                "targetNameHint": "great boar",
                "readyForUse": True,
                "offerEligible": True,
                "dummyEvaluationCount": 0,
                "minLevel": 43,
            },
        ]

        plans = planner.build_plans({"items": rows}, args)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-great-boar", "seed-1-forest-snake-a"])

    def test_prepared_live_target_family_deduplicates_rows_with_different_hints(self) -> None:
        args = planner.parse_args(["--prepare-evaluation-offers", "--max-plans", "3"])
        rows = [
            {
                "templateId": "seed-100-drone",
                "realm": "Midgard",
                "startMode": "AutoAccept",
                "branchWorldSignal": "time-window",
                "targetNameHint": "Arcsinimpede's Drone",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
                "minLevel": 48,
            },
            {
                "templateId": "seed-100-master",
                "realm": "Midgard",
                "startMode": "AutoAccept",
                "branchWorldSignal": "time-window",
                "targetNameHint": "Arcsinimpede",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
                "minLevel": 48,
            },
        ]

        original_prepare = planner.prepare_evaluation_offer

        def fake_prepare(row: dict[str, object], _args: object) -> dict[str, object]:
            return {
                "id": row["templateId"],
                "templateId": row["templateId"],
                "targetName": "frost bound bear",
                "minLevel": 48,
            }

        try:
            planner.prepare_evaluation_offer = fake_prepare
            plans = planner.build_plans({"items": rows}, args, {"quests": []})
        finally:
            planner.prepare_evaluation_offer = original_prepare

        self.assertEqual([plan.template_id for plan in plans], ["seed-100-drone"])

    def test_autoaccept_live_offer_preemption_skips_later_conflicting_branch_offer(self) -> None:
        args = planner.parse_args(["--prepare-evaluation-offers", "--max-plans", "3"])
        rows = [
            {
                "templateId": "seed-1-linear-priestess",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "",
                "targetNameHint": "priestess",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
                "minLevel": 42,
                "maxLevel": 46,
            },
            {
                "templateId": "seed-1-branch-priestess",
                "realm": "Albion",
                "startMode": "AutoAccept",
                "branchWorldSignal": "time-window",
                "targetNameHint": "priestess",
                "readyForUse": True,
                "offerEligible": False,
                "offerBlockReasons": ["dummy_evaluation_required"],
                "dummyEvaluationCount": 0,
                "minLevel": 42,
                "maxLevel": 46,
            },
        ]
        live_payload = {
            "quests": [
                {
                    "id": "seed-1-linear-priestess",
                    "realm": "Albion",
                    "startMode": 2,
                    "targetName": "priestess",
                    "createdAt": "2026-06-23T19:50:23Z",
                    "tags": [
                        "template:seed-1-linear-priestess",
                        "dummy-evaluation-offer",
                        "trigger:region:1",
                    ],
                },
                {
                    "id": "seed-1-branch-priestess",
                    "realm": "Albion",
                    "startMode": 2,
                    "targetName": "priestess",
                    "createdAt": "2026-06-23T19:59:09Z",
                    "tags": [
                        "template:seed-1-branch-priestess",
                        "dummy-evaluation-offer",
                        "trigger:region:1",
                        "world-signal:time-window",
                    ],
                },
            ]
        }

        plans = planner.build_plans({"items": rows}, args, live_payload)

        self.assertEqual([plan.template_id for plan in plans], ["seed-1-linear-priestess"])


if __name__ == "__main__":
    unittest.main()
