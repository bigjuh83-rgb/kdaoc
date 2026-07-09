#!/usr/bin/env python3
"""Plan dummy-client E2E runs for unevaluated dynamic quest story-cache rows."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path


REALM_KEYS = {
    "albion": "alb",
    "midgard": "mid",
    "hibernia": "hib",
}

BASE_TIMELINE_EVENTS = (
    "quest_accepted",
    "node_advanced",
    "quest_completed",
    "quest_rewarded",
    "presentation_beat",
    "cinematic_action",
    "scene_beat_outcome",
    "scene_world_signal",
)

CHOICE_TIMELINE_EVENTS = (
    "choice_selected",
)

BASE_PRESENTATION_TRIGGERS = (
    "OnAccept",
    "OnExplore",
    "OnComplete",
)

CHOICE_PRESENTATION_TRIGGERS = (
    "OnChoiceShown",
    "OnChoiceSelected",
)


@dataclass(frozen=True)
class CacheEvaluationPlan:
    template_id: str
    realm: str
    realm_key: str
    target_name: str
    start_mode: str
    branch_tag: str
    world_signal: str
    dummy_score: int
    dummy_count: int
    dummy_action_scene_cohesion_score: int
    dummy_cinematic_catalog_role_variety: int
    dummy_cinematic_model_role_fit_score: int
    live_quest_id: str
    player_level: int
    command: list[str]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--max-plans", type=int, default=12)
    parser.add_argument("--party-size", type=int, default=3)
    parser.add_argument("--player-level", type=int, default=0, help="player level for dummy runs; 0 chooses the prepared live quest minLevel, then the cache row minLevel")
    parser.add_argument("--min-player-level", type=int, default=0, help="minimum effective dummy player level for planned rows; 0 disables")
    parser.add_argument("--max-player-level", type=int, default=0, help="maximum effective dummy player level for planned rows; 0 disables")
    parser.add_argument("--min-action-scene-cohesion", type=int, default=-1, help="minimum dummyActionSceneCohesionScore for planned rows; -1 disables")
    parser.add_argument("--max-action-scene-cohesion", type=int, default=-1, help="maximum dummyActionSceneCohesionScore for planned rows; -1 disables")
    parser.add_argument("--missing-action-scene-cohesion", action="store_true", help="only include evaluated rows whose action-scene cohesion metric is missing or zero")
    parser.add_argument("--min-cinematic-model-role-fit", type=int, default=-1, help="minimum dummyCinematicModelRoleFitScore for planned rows; -1 disables")
    parser.add_argument("--max-cinematic-model-role-fit", type=int, default=-1, help="maximum dummyCinematicModelRoleFitScore for planned rows; -1 disables")
    parser.add_argument("--missing-cinematic-model-role-fit", action="store_true", help="only include evaluated rows whose cinematic model-role fit metric is missing or zero")
    parser.add_argument("--evaluation-min-score", type=int, default=75)
    parser.add_argument("--output-root", default="test-output\\dynamic-quest-cache-evaluation")
    parser.add_argument("--timeline-limit", type=int, default=900)
    parser.add_argument("--target-timeout", type=int, default=220)
    parser.add_argument("--safe-exit-max-seconds", type=int, default=25)
    parser.add_argument("--live-quest-seed-wait-seconds", type=int, default=60)
    parser.add_argument(
        "--evaluation-offer-timeout",
        type=int,
        default=120,
        help="seconds to wait for internal story-cache evaluation-offer binding",
    )
    parser.add_argument(
        "--max-prepare-attempts",
        type=int,
        default=0,
        help="maximum internal evaluation-offer POST attempts while planning; 0 disables",
    )
    parser.add_argument(
        "--accounts-pattern",
        default="",
        help="optional accounts CSV pattern forwarded to run-dummy-dynamic-quest-matrix.py",
    )
    parser.add_argument("--include-evaluated", action="store_true", help="include rows that already have a dummy evaluation")
    parser.add_argument(
        "--max-dummy-evaluation-count",
        type=int,
        default=0,
        help="maximum existing dummyEvaluationCount for planned rows; 0 disables",
    )
    parser.add_argument("--include-not-ready", action="store_true", help="include rows that are not currently ready for use")
    parser.add_argument(
        "--include-offer-blocked",
        action="store_true",
        help="include rows blocked by the live-offer gate, such as rows still missing a passing dummy evaluation",
    )
    parser.add_argument("--live-only", action="store_true", help="only emit plans for story-cache rows that currently have a matching live offer")
    parser.add_argument(
        "--prepare-evaluation-offers",
        action="store_true",
        help="POST an internal evaluation-offer for selected offer-blocked rows before emitting runnable plans",
    )
    parser.add_argument(
        "--allow-failed-evaluation-offers",
        action="store_true",
        help="when preparing evaluation offers, allow rows blocked only by a previous dummy_evaluation_* failure",
    )
    parser.add_argument(
        "--include-evaluated-target-family-repeats",
        action="store_true",
        help="include unevaluated rows whose target family already has a passing dummy evaluation",
    )
    parser.add_argument("--realm", action="append", default=[], help="limit to a realm key/name; may be repeated")
    parser.add_argument("--start-mode", action="append", default=[], help="limit to NpcOffer or AutoAccept; may be repeated")
    parser.add_argument(
        "--offer-block-reason",
        action="append",
        default=[],
        help="limit to story-cache rows containing this offerBlockReasons value; may be repeated",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON instead of a shell command list")
    return parser.parse_args(argv)


def text_value(value: object) -> str:
    return str(value or "").strip()


def int_value(value: object) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def list_text_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text_value(item) for item in value if text_value(item)]


def has_dummy_evaluation_block_reason(row: dict[str, object]) -> bool:
    return any(
        reason.lower().startswith("dummy_evaluation_")
        for reason in list_text_values(row.get("offerBlockReasons"))
    )


def target_family_fingerprint(target_name: str) -> str:
    normalized = " ".join(text_value(target_name).lower().split())
    if not normalized:
        return ""
    first_token = normalized.split(" ", 1)[0].strip("'\".,:;()[]{}")
    return first_token if len(first_token) >= 5 else normalized


def target_family_key_for_name(row: dict[str, object], target_name: str) -> tuple[str, str, str, str]:
    return (
        normalize_realm_key(text_value(row.get("realm"))),
        start_mode_arg(text_value(row.get("startMode"))),
        text_value(row.get("branchWorldSignal")).lower(),
        target_family_fingerprint(target_name),
    )


def target_family_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return target_family_key_for_name(row, text_value(row.get("targetNameHint")))


def live_start_mode_arg(quest: dict[str, object]) -> str:
    value = quest.get("startMode")
    if isinstance(value, int):
        return "autoaccept" if value == 2 else text_value(value).lower()
    return start_mode_arg(text_value(value))


def live_tags(quest: dict[str, object]) -> list[str]:
    return list_text_values(quest.get("tags"))


def live_template_id(quest: dict[str, object]) -> str:
    for tag in live_tags(quest):
        value = tag.strip()
        if value.lower().startswith("template:"):
            return value.split(":", 1)[1].strip()
    return text_value(quest.get("templateId")) or text_value(quest.get("id"))


def live_is_dummy_evaluation_offer(quest: dict[str, object]) -> bool:
    return any(tag.lower() == "dummy-evaluation-offer" for tag in live_tags(quest))


def live_region_triggers(quest: dict[str, object]) -> set[str]:
    triggers: set[str] = set()
    for tag in live_tags(quest):
        value = tag.strip().lower()
        if value.startswith("trigger:region:"):
            triggers.add(value.removeprefix("trigger:"))
        elif value.startswith("region:"):
            triggers.add(value)
    return triggers


def live_autoaccept_conflict_keys(quest: dict[str, object]) -> set[tuple[str, str, str, str]]:
    if live_start_mode_arg(quest) != "autoaccept" or not live_is_dummy_evaluation_offer(quest):
        return set()

    realm = normalize_realm_key(text_value(quest.get("realm")))
    family = target_family_fingerprint(text_value(quest.get("targetName")))
    if not realm or not family:
        return set()

    return {
        (realm, "autoaccept", trigger, family)
        for trigger in live_region_triggers(quest)
        if trigger
    }


def live_created_sort_value(quest: dict[str, object]) -> str:
    return text_value(quest.get("createdAt"))


def find_preempting_live_evaluation_offer(
    live_quest: dict[str, object],
    live_payload: dict[str, object] | None,
) -> dict[str, object] | None:
    if not isinstance(live_quest, dict) or not isinstance(live_payload, dict):
        return None

    current_keys = live_autoaccept_conflict_keys(live_quest)
    if not current_keys:
        return None

    current_id = text_value(live_quest.get("id"))
    current_created = live_created_sort_value(live_quest)
    quests = live_payload.get("quests", [])
    typed_quests = [quest for quest in quests if isinstance(quest, dict)] if isinstance(quests, list) else []
    for candidate in typed_quests:
        if text_value(candidate.get("id")) == current_id:
            continue
        if not current_keys.intersection(live_autoaccept_conflict_keys(candidate)):
            continue

        candidate_created = live_created_sort_value(candidate)
        if not current_created or not candidate_created or candidate_created <= current_created:
            return candidate

    return None


def has_passing_dummy_evaluation(row: dict[str, object], args: argparse.Namespace) -> bool:
    if int_value(row.get("dummyEvaluationCount")) <= 0:
        return False
    if int_value(row.get("dummyEvaluationScore")) < max(0, int(getattr(args, "evaluation_min_score", 0) or 0)):
        return False
    return bool(row.get("readyForUse")) and bool(row.get("offerEligible"))


def passing_evaluated_target_family_keys(
    rows: list[dict[str, object]],
    args: argparse.Namespace,
) -> set[tuple[str, str, str, str]]:
    return {
        key
        for row in rows
        if has_passing_dummy_evaluation(row, args)
        for key in [target_family_key(row)]
        if key[-1]
    }


def should_skip_evaluated_target_family_repeat(
    row: dict[str, object],
    evaluated_target_families: set[tuple[str, str, str, str]],
) -> bool:
    if int_value(row.get("dummyEvaluationCount")) > 0:
        return False
    key = target_family_key(row)
    return bool(key[-1]) and key in evaluated_target_families


def should_allow_failed_evaluation_offer(row: dict[str, object], args: argparse.Namespace) -> bool:
    if bool(getattr(args, "allow_failed_evaluation_offers", False)):
        return True

    block_reason_filters = {
        text_value(item).lower()
        for item in getattr(args, "offer_block_reason", [])
        if text_value(item)
    }
    return bool(block_reason_filters) and has_dummy_evaluation_block_reason(row)


def story_cache_url(args: argparse.Namespace) -> str:
    return f"http://{args.host}:{int(args.api_port)}/api/world/dynamic-quests/story-cache?limit={int(args.limit)}&includeText=false"


def fetch_story_cache(args: argparse.Namespace) -> dict[str, object]:
    request = urllib.request.Request(story_cache_url(args), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def dynamic_quests_url(args: argparse.Namespace) -> str:
    return f"http://{args.host}:{int(args.api_port)}/api/world/dynamic-quests"


def fetch_live_dynamic_quests(args: argparse.Namespace) -> dict[str, object]:
    request = urllib.request.Request(dynamic_quests_url(args), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def story_cache_evaluation_offer_url(args: argparse.Namespace) -> str:
    return f"http://{args.host}:{int(args.api_port)}/api/world/dynamic-quests/story-cache/evaluation-offer"


def prepare_evaluation_offer(row: dict[str, object], args: argparse.Namespace) -> dict[str, object] | None:
    template_id = text_value(row.get("templateId"))
    if not template_id:
        return None

    body = json.dumps(
        {
            "templateId": template_id,
            "allowFailedDummyEvaluation": should_allow_failed_evaluation_offer(row, args),
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        story_cache_evaluation_offer_url(args),
        data=body,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        timeout_seconds = max(1, int(getattr(args, "evaluation_offer_timeout", 120) or 120))
        with urllib.request.urlopen(request, timeout=float(timeout_seconds)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict) or not payload.get("success"):
        return None
    quest = payload.get("quest")
    return quest if isinstance(quest, dict) else None


def normalize_realm_key(value: str) -> str:
    lowered = text_value(value).lower()
    if lowered in {"alb", "mid", "hib"}:
        return lowered
    return REALM_KEYS.get(lowered, "")


def row_tags(row: dict[str, object]) -> list[str]:
    tags = row.get("tags", [])
    if not isinstance(tags, list):
        return []
    return [text_value(tag) for tag in tags if text_value(tag)]


def live_quest_tags(quest: dict[str, object]) -> list[str]:
    tags = quest.get("tags", [])
    if not isinstance(tags, list):
        return []
    return [text_value(tag) for tag in tags if text_value(tag)]


def branch_tag_for(row: dict[str, object]) -> str:
    for tag in row_tags(row):
        if tag.lower().startswith("branch:"):
            return tag
    return ""


def start_mode_arg(value: str) -> str:
    value = text_value(value).lower()
    if value in {"autoaccept", "auto", "2"}:
        return "autoaccept"
    return "npc"


def is_item_acquired(world_signal: str, branch_tag: str) -> bool:
    return "item-acquired" in text_value(world_signal).lower() or branch_tag.lower() == "branch:item-acquired"


def is_mob_growth(world_signal: str, branch_tag: str) -> bool:
    return "mob-growth" in text_value(world_signal).lower() or branch_tag.lower() == "branch:mob-growth"


def has_choice_branch(branch_tag: str) -> bool:
    return bool(text_value(branch_tag))


def timeline_events_for(world_signal: str, branch_tag: str) -> str:
    events = list(BASE_TIMELINE_EVENTS)
    if has_choice_branch(branch_tag):
        insert_at = events.index("quest_completed")
        events[insert_at:insert_at] = CHOICE_TIMELINE_EVENTS
    if is_item_acquired(world_signal, branch_tag):
        events.insert(3, "world_signal")
    return ",".join(events)


def presentation_triggers_for(world_signal: str, branch_tag: str) -> str:
    triggers = list(BASE_PRESENTATION_TRIGGERS)
    if has_choice_branch(branch_tag):
        insert_at = triggers.index("OnComplete")
        triggers[insert_at:insert_at] = CHOICE_PRESENTATION_TRIGGERS
    if is_item_acquired(world_signal, branch_tag):
        triggers.insert(-1, "OnWorldSignal")
    return ",".join(triggers)


def player_level_for(row: dict[str, object], args: argparse.Namespace, live_quest: dict[str, object] | None = None) -> int:
    explicit = int_value(args.player_level)
    if explicit > 0:
        return max(1, explicit)

    row_min_level = int_value(row.get("minLevel"))
    row_max_level = int_value(row.get("maxLevel"))
    if isinstance(live_quest, dict):
        min_level = int_value(live_quest.get("minLevel"))
        max_level = int_value(live_quest.get("maxLevel"))
        selected = min_level if min_level > 0 else max_level
        if has_dummy_evaluation_block_reason(row) and row_min_level > 0:
            selected = max(selected, row_min_level)
        if selected > 0:
            return max(1, min(50, selected))

    selected = row_min_level if row_min_level > 0 else row_max_level
    if selected <= 0:
        selected = 5
    return max(1, min(50, selected))


def row_is_candidate(row: dict[str, object], args: argparse.Namespace) -> bool:
    if not args.include_not_ready and not bool(row.get("readyForUse")):
        return False
    if (
        not args.include_offer_blocked
        and not args.prepare_evaluation_offers
        and "offerEligible" in row
        and not bool(row.get("offerEligible"))
    ):
        return False
    if not args.include_evaluated and int_value(row.get("dummyEvaluationCount")) > 0:
        return False
    max_dummy_evaluation_count = max(0, int_value(getattr(args, "max_dummy_evaluation_count", 0)))
    if max_dummy_evaluation_count > 0 and int_value(row.get("dummyEvaluationCount")) > max_dummy_evaluation_count:
        return False

    realm_key = normalize_realm_key(text_value(row.get("realm")))
    if not realm_key:
        return False
    realm_filters = {normalize_realm_key(item) for item in args.realm if normalize_realm_key(item)}
    if realm_filters and realm_key not in realm_filters:
        return False

    start_mode = text_value(row.get("startMode")) or "NpcOffer"
    start_filters = {text_value(item).lower() for item in args.start_mode if text_value(item)}
    if start_filters and start_mode.lower() not in start_filters:
        return False

    block_reason_filters = {text_value(item).lower() for item in args.offer_block_reason if text_value(item)}
    if block_reason_filters:
        row_block_reasons = {reason.lower() for reason in list_text_values(row.get("offerBlockReasons"))}
        if not row_block_reasons.intersection(block_reason_filters):
            return False

    planned_level = player_level_for(row, args)
    min_player_level = max(0, int_value(getattr(args, "min_player_level", 0)))
    max_player_level = max(0, int_value(getattr(args, "max_player_level", 0)))
    if min_player_level > 0 and planned_level < min_player_level:
        return False
    if max_player_level > 0 and planned_level > max_player_level:
        return False

    action_scene_cohesion = int_value(row.get("dummyActionSceneCohesionScore"))
    if bool(getattr(args, "missing_action_scene_cohesion", False)):
        if int_value(row.get("dummyEvaluationCount")) <= 0 or action_scene_cohesion > 0:
            return False
    min_action_scene = int_value(getattr(args, "min_action_scene_cohesion", -1))
    max_action_scene = int_value(getattr(args, "max_action_scene_cohesion", -1))
    if min_action_scene >= 0 and action_scene_cohesion < min_action_scene:
        return False
    if max_action_scene >= 0 and action_scene_cohesion > max_action_scene:
        return False

    model_role_fit = int_value(row.get("dummyCinematicModelRoleFitScore"))
    if bool(getattr(args, "missing_cinematic_model_role_fit", False)):
        if int_value(row.get("dummyEvaluationCount")) <= 0 or model_role_fit > 0:
            return False
    min_model_role_fit = int_value(getattr(args, "min_cinematic_model_role_fit", -1))
    max_model_role_fit = int_value(getattr(args, "max_cinematic_model_role_fit", -1))
    if min_model_role_fit >= 0 and model_role_fit < min_model_role_fit:
        return False
    if max_model_role_fit >= 0 and model_role_fit > max_model_role_fit:
        return False

    return bool(text_value(row.get("templateId")) and text_value(row.get("targetNameHint")))


def live_quest_start_mode(quest: dict[str, object]) -> str:
    mode = text_value(quest.get("startMode"))
    if mode:
        return mode
    return "AutoAccept" if not text_value(quest.get("startNpcName")) else "NpcOffer"


def live_quest_template_ids(quest: dict[str, object]) -> set[str]:
    ids = {text_value(quest.get("id")).lower()}
    for tag in live_quest_tags(quest):
        value = text_value(tag)
        if value.lower().startswith("template:"):
            ids.add(value.split(":", 1)[1].strip().lower())
    return {item for item in ids if item}


def find_live_quest(row: dict[str, object], live_payload: dict[str, object] | None) -> dict[str, object] | None:
    quests = live_payload.get("quests", []) if isinstance(live_payload, dict) else []
    if not isinstance(quests, list):
        return None

    template_id = text_value(row.get("templateId")).lower()
    row_realm = text_value(row.get("realm")).lower()
    row_target = text_value(row.get("targetNameHint")).lower()
    row_start_mode = start_mode_arg(text_value(row.get("startMode")))
    branch_tag = branch_tag_for(row).lower()
    world_signal = text_value(row.get("branchWorldSignal")).lower()

    for quest in quests:
        if not isinstance(quest, dict):
            continue
        if row_realm and text_value(quest.get("realm")).lower() != row_realm:
            continue
        if start_mode_arg(live_quest_start_mode(quest)) != row_start_mode:
            continue

        tags = [tag.lower() for tag in live_quest_tags(quest)]
        if template_id and template_id in live_quest_template_ids(quest):
            return quest

        if has_dummy_evaluation_block_reason(row):
            continue

        if row_target and text_value(quest.get("targetName")).lower() != row_target:
            continue
        if branch_tag and branch_tag not in tags:
            continue
        if world_signal and f"world-signal:{world_signal}" not in tags:
            continue
        return quest

    return None


def find_live_quest_id(row: dict[str, object], live_payload: dict[str, object] | None) -> str:
    quest = find_live_quest(row, live_payload)
    if quest is None:
        return ""
    return text_value(quest.get("id"))


def build_command(row: dict[str, object], args: argparse.Namespace, live_quest: dict[str, object] | None = None) -> list[str]:
    template_id = text_value(row.get("templateId"))
    realm = text_value(row.get("realm"))
    realm_key = normalize_realm_key(realm)
    start_mode = text_value(row.get("startMode")) or "NpcOffer"
    start_mode_cli = start_mode_arg(start_mode)
    target = text_value(live_quest.get("targetName")) if isinstance(live_quest, dict) else ""
    if not target:
        target = text_value(row.get("targetNameHint"))
    world_signal = text_value(row.get("branchWorldSignal"))
    branch_tag = branch_tag_for(row)
    output_root = str(Path(args.output_root) / template_id)

    command = [
        sys.executable,
        "tools\\run-dummy-dynamic-quest-matrix.py",
        "--matrix",
        "realm-smoke",
        "--realms",
        realm_key,
        "--party-sizes",
        str(max(1, int(args.party_size))),
        "--quest-start-mode",
        start_mode_cli,
        "--player-level",
        str(player_level_for(row, args, live_quest=live_quest)),
        "--output-root",
        output_root,
        "--prefer-melee-smoke-accounts",
        "--no-require-melee-smoke-accounts",
        "--dynamic-quest-submit-evaluation",
        "--dynamic-quest-evaluation-min-score",
        str(max(1, int(args.evaluation_min_score))),
        "--dynamic-quest-min-cinematic-catalog-role-variety",
        "2",
        "--dynamic-quest-min-cinematic-model-role-fit",
        str(max(1, min(100, int(args.evaluation_min_score)))),
        "--require-live-quest-target",
        target,
        "--require-live-quest-template",
        template_id,
        "--dynamic-quest-require-timeline-events",
        timeline_events_for(world_signal, branch_tag),
        "--dynamic-quest-require-presentation-triggers",
        presentation_triggers_for(world_signal, branch_tag),
        "--dynamic-quest-timeline-limit",
        str(max(50, int(args.timeline_limit))),
        "--target-timeout",
        str(max(1, int(args.target_timeout))),
        "--safe-exit-max-seconds",
        str(max(0, int(args.safe_exit_max_seconds))),
        "--live-quest-seed-wait-seconds",
        str(max(0, int(args.live_quest_seed_wait_seconds))),
    ]

    if branch_tag:
        command.extend(["--require-quest-tag", branch_tag])
    if world_signal:
        command.extend(["--require-world-signal", world_signal])
    if text_value(getattr(args, "accounts_pattern", "")):
        command.extend(["--accounts-pattern", text_value(args.accounts_pattern)])
    if is_mob_growth(world_signal, branch_tag):
        command.append("--dynamic-quest-followup-growth-target")

    return command


def build_plans(
    payload: dict[str, object],
    args: argparse.Namespace,
    live_payload: dict[str, object] | None = None,
) -> list[CacheEvaluationPlan]:
    rows = payload.get("items", [])
    typed_rows = [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []
    evaluated_target_families = (
        set()
        if bool(getattr(args, "include_evaluated_target_family_repeats", False))
        else passing_evaluated_target_family_keys(typed_rows, args)
    )
    candidates = [
        row
        for row in typed_rows
        if row_is_candidate(row, args)
        and not should_skip_evaluated_target_family_repeat(row, evaluated_target_families)
    ]
    if args.live_only:
        candidates = [row for row in candidates if find_live_quest_id(row, live_payload)]
    candidates = round_robin_candidates(candidates)

    plans: list[CacheEvaluationPlan] = []
    planned_target_families: set[tuple[str, str, str, str]] = set()
    prepare_attempts = 0
    max_prepare_attempts = max(0, int(getattr(args, "max_prepare_attempts", 0) or 0))
    for row in candidates:
        if args.max_plans > 0 and len(plans) >= int(args.max_plans):
            break
        family_key = target_family_key(row)
        if family_key[-1] and family_key in planned_target_families:
            continue

        realm = text_value(row.get("realm"))
        world_signal = text_value(row.get("branchWorldSignal"))
        branch_tag = branch_tag_for(row)
        live_quest = find_live_quest(row, live_payload)
        if live_quest is None and args.prepare_evaluation_offers:
            if max_prepare_attempts > 0 and prepare_attempts >= max_prepare_attempts:
                break
            prepare_attempts += 1
            live_quest = prepare_evaluation_offer(row, args)
        if args.prepare_evaluation_offers and live_quest is None:
            continue
        if isinstance(live_quest, dict):
            live_family_key = target_family_key_for_name(row, text_value(live_quest.get("targetName")))
            if live_family_key[-1]:
                if live_family_key in planned_target_families:
                    continue
                family_key = live_family_key
            if find_preempting_live_evaluation_offer(live_quest, live_payload) is not None:
                continue
        plans.append(
            CacheEvaluationPlan(
                template_id=text_value(row.get("templateId")),
                realm=realm,
                realm_key=normalize_realm_key(realm),
                target_name=text_value(live_quest.get("targetName")) if isinstance(live_quest, dict) else text_value(row.get("targetNameHint")),
                start_mode=text_value(row.get("startMode")) or "NpcOffer",
                branch_tag=branch_tag,
                world_signal=world_signal,
                dummy_score=int_value(row.get("dummyEvaluationScore")),
                dummy_count=int_value(row.get("dummyEvaluationCount")),
                dummy_action_scene_cohesion_score=int_value(row.get("dummyActionSceneCohesionScore")),
                dummy_cinematic_catalog_role_variety=int_value(row.get("dummyCinematicCatalogRoleVariety")),
                dummy_cinematic_model_role_fit_score=int_value(row.get("dummyCinematicModelRoleFitScore")),
                live_quest_id=text_value(live_quest.get("id")) if isinstance(live_quest, dict) else "",
                player_level=player_level_for(row, args, live_quest=live_quest),
                command=build_command(row, args, live_quest=live_quest),
            )
        )
        if family_key[-1]:
            planned_target_families.add(family_key)
    return plans


def candidate_group_key(row: dict[str, object]) -> tuple[str, str, str]:
    return (
        normalize_realm_key(text_value(row.get("realm"))),
        start_mode_arg(text_value(row.get("startMode"))),
        text_value(row.get("branchWorldSignal")).lower(),
    )


def candidate_sort_key(row: dict[str, object]) -> tuple[int, int, int, str]:
    min_level = int_value(row.get("minLevel"))
    max_level = int_value(row.get("maxLevel"))
    if min_level <= 0:
        min_level = max_level
    if max_level <= 0:
        max_level = min_level
    retry_penalty = int_value(row.get("dummyEvaluationCount")) if has_dummy_evaluation_block_reason(row) else 0
    return (
        retry_penalty,
        max_level or 99,
        min_level or 99,
        text_value(row.get("templateId")).lower(),
    )


def round_robin_candidates(candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    groups: dict[tuple[str, str, str], list[dict[str, object]]] = {}
    for row in candidates:
        groups.setdefault(candidate_group_key(row), []).append(row)

    for group_rows in groups.values():
        group_rows.sort(key=candidate_sort_key)

    group_keys = sorted(groups)
    ordered: list[dict[str, object]] = []
    while any(groups[key] for key in group_keys):
        for key in group_keys:
            if groups[key]:
                ordered.append(groups[key].pop(0))
    return ordered


def plan_to_dict(plan: CacheEvaluationPlan) -> dict[str, object]:
    return {
        "templateId": plan.template_id,
        "realm": plan.realm,
        "realmKey": plan.realm_key,
        "targetName": plan.target_name,
        "startMode": plan.start_mode,
        "branchTag": plan.branch_tag,
        "worldSignal": plan.world_signal,
        "dummyEvaluationScore": plan.dummy_score,
        "dummyEvaluationCount": plan.dummy_count,
        "dummyActionSceneCohesionScore": plan.dummy_action_scene_cohesion_score,
        "dummyCinematicCatalogRoleVariety": plan.dummy_cinematic_catalog_role_variety,
        "dummyCinematicModelRoleFitScore": plan.dummy_cinematic_model_role_fit_score,
        "liveQuestId": plan.live_quest_id,
        "playerLevel": plan.player_level,
        "command": plan.command,
        "commandText": shlex.join(plan.command),
    }


def emit_text(plans: list[CacheEvaluationPlan]) -> str:
    lines: list[str] = []
    for index, plan in enumerate(plans, start=1):
        lines.append(
            f"# {index}. {plan.template_id} {plan.realm}/{plan.start_mode} target={plan.target_name!r} "
            f"branch={plan.branch_tag or '-'} signal={plan.world_signal or '-'} live={plan.live_quest_id or '-'} "
            f"level={plan.player_level} actionScene={plan.dummy_action_scene_cohesion_score} "
            f"modelRoleFit={plan.dummy_cinematic_model_role_fit_score}"
        )
        lines.append(shlex.join(plan.command))
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = fetch_story_cache(args)
    live_payload = fetch_live_dynamic_quests(args) if args.live_only or args.prepare_evaluation_offers else None
    plans = build_plans(payload, args, live_payload)
    if args.json:
        print(json.dumps([plan_to_dict(plan) for plan in plans], ensure_ascii=False, indent=2))
    else:
        print(emit_text(plans))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
