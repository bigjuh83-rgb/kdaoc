#!/usr/bin/env python3
"""Run deterministic dummy-client dynamic quest E2E matrix cases."""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace


DYNAMIC_QUEST_PRESENTATION_TIMELINE_MIN_LIMIT = 2000


@dataclass(frozen=True)
class RealmQuest:
    key: str
    realm: str
    region: int
    seed_npc: str
    target: str
    return_home: tuple[int, int, int]


@dataclass(frozen=True)
class QuestCase:
    name: str
    key: str
    realm: str
    region: int
    seed_npc: str
    target: str
    return_home: tuple[int, int, int]
    party_size: int
    accounts_csv: Path
    output_dir: Path
    min_target_level: int = 1
    max_target_level: int = 1
    player_level: int = 1
    quest_id: str = ""
    target_home: tuple[int, int, int] | None = None
    target_home_radius: int = 0
    followup_target: str = ""
    followup_home: tuple[int, int, int] | None = None
    followup_reference: tuple[int, int, int] | None = None
    followup_min_target_level: int = 0
    followup_max_target_level: int = 0
    followup_object_id: int = 0
    quest_start_mode: str = ""
    require_quest_tag: str = ""
    require_world_signal: str = ""
    return_dialog_response: str = ""
    require_timeline_events: str = ""
    require_presentation_triggers: str = ""
    expected_final_node: str = ""
    followup_growth_target: bool = False
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class StartPosition:
    region: int
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class LiveQuestBinding:
    seed_npc: str
    target: str
    min_target_level: int
    max_target_level: int
    min_player_level: int = 0
    max_player_level: int = 0
    start_npc_internal_id: str = ""
    start_position: StartPosition | None = None
    target_position: StartPosition | None = None
    target_radius: int = 0
    followup_reference: StartPosition | None = None
    quest_id: str = ""
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class LiveMobGrowthTarget:
    name: str
    region: int
    x: int
    y: int
    z: int
    min_level: int
    max_level: int
    stage: str = ""
    mob_id: str = ""
    object_id: int = 0
    aliases: tuple[str, ...] = ()


DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_REFERENCE_DISTANCE = 90000
DEFAULT_MOB_GROWTH_FOLLOWUP_CLUSTER_RADIUS = 5000
DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_CLUSTER_NEIGHBORS = 2
DEFAULT_MOB_GROWTH_FOLLOWUP_ALIAS_RADIUS = 3500
DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_ALIASES = 8
REALM_IDS_BY_KEY = {"alb": 1, "mid": 2, "hib": 3}


@dataclass(frozen=True)
class CaseSummary:
    players: int
    ok_players: int
    completed: int
    reward_observed: int
    target_removed: int
    player_deaths: int
    choice_selected: int
    world_signal: int
    presentation_beat: int
    world_impact: int
    world_impact_summary: int
    narrative_scene: int
    cinematic_action: int
    scene_director_beat: int
    scene_beat_outcome: int
    scene_choreography_phase: int = 0
    scene_actor_exchange: int = 0
    scene_exchange_outcome: int = 0
    scene_outcome_signal: int = 0
    scene_consequence: int = 0
    scene_world_signal: int = 0
    world_signal_scene_shift: int = 0
    cinematic_cleanup: int = 0
    followup_hunt_start: int = 0
    elapsed_seconds: float = 0.0
    passed: bool = False
    evaluation_score: int = 0
    skyrim_grade_score: int = 0
    cinematic_density_score: int = 0
    kill_confirmed: int = 0
    choice_outcome_scene: int = 0
    choice_consequence: int = 0
    world_memory_marked: int = 0
    cinematic_variety: int = 0
    cinematic_motion_variety: int = 0
    cinematic_staggered_scene: int = 0
    cinematic_objective_focal_scene: int = 0
    cinematic_actor_role_variety: int = 0
    cinematic_choreographed_scene: int = 0
    cinematic_interaction_scene: int = 0
    cinematic_tactic_variety: int = 0
    story_continuity_score: int = 0
    story_archetype_score: int = 0
    cinematic_actor_instances: int = 0
    cinematic_actor_peak: int = 0
    cinematic_actor_spawn_summary: int = 0
    cinematic_actor_spawned_total: int = 0
    cinematic_actor_spawned_peak: int = 0
    cinematic_actor_spawn_failed: int = 0
    cinematic_actor_cleanup_scheduled: int = 0
    cinematic_actor_motion_summary: int = 0
    cinematic_actor_motion_commands: int = 0
    cinematic_actor_motion_commands_peak: int = 0
    cinematic_actor_motion_commands_per_actor_peak: int = 0
    cinematic_actor_motion_spawned_total: int = 0
    cinematic_actor_engagement_summary: int = 0
    cinematic_actor_engagement_pairs: int = 0
    cinematic_actor_engagement_pairs_peak: int = 0
    cinematic_actor_engaged_total: int = 0
    cinematic_actor_engagement_spawned_total: int = 0
    cinematic_actor_budget_score: int = 0
    action_scene_cohesion_score: int = 0
    cinematic_catalog_role_variety: int = 0
    cinematic_model_role_fit_score: int = 0
    min_narrative_scene_per_player: int = -1
    min_presentation_beat_per_player: int = -1
    min_cinematic_action_per_player: int = -1
    presentation_speaker_variety: int = -1
    cinematic_marker_scene: int = -1
    cinematic_marker_variety: int = -1
    cinematic_phase_coverage: int = -1
    cinematic_setpiece_phase_coverage: int = -1
    cinematic_marker_phase_coverage: int = -1
    cinematic_story_chain: int = -1
    presentation_staged_beat: int = -1
    presentation_staged_actor_total: int = -1
    presentation_staged_actor_peak: int = -1
    presentation_staged_action_variety: int = -1
    presentation_staged_role_variety: int = -1
    presentation_staged_formation_variety: int = -1
    presentation_staged_delayed_beat: int = -1
    world_signal_scene_shift_detail: int = -1
    world_signal_scene_shift_phase_variety: int = -1
    world_signal_scene_shift_source_variety: int = -1
    world_signal_scene_shift_target_variety: int = -1
    choice_ids: tuple[str, ...] = ()
    safe_choice_seen: int = 0


STARTER_REALMS: tuple[RealmQuest, ...] = (
    RealmQuest("alb", "Albion", 1, "Brother Penric", "black wolf pup", (518850, 494050, 3352)),
    RealmQuest("mid", "Midgard", 100, "Aud", "young sveawolf", (773327, 749653, 4552)),
    RealmQuest("hib", "Hibernia", 200, "Ionhar", "water beetle larva", (344500, 474500, 5372)),
)
DUMMY_RESET_RESOURCE_VALUE = 10000
MELEE_SMOKE_CLASS_NAMES = {
    "armsman",
    "berserker",
    "blademaster",
    "champion",
    "friar",
    "hero",
    "mercenary",
    "minstrel",
    "paladin",
    "skald",
    "warrior",
}
MELEE_SMOKE_CLASS_PRIORITY = {
    "paladin": 0,
    "armsman": 1,
    "mercenary": 2,
    "warrior": 0,
    "berserker": 1,
    "skald": 2,
    "hero": 0,
    "blademaster": 1,
    "champion": 2,
    "friar": 50,
    "minstrel": 51,
}
CLASS_ID_TO_NAME = {
    2: "Armsman",
    6: "Cleric",
    7: "Wizard",
    10: "Paladin",
    11: "Mercenary",
    22: "Warrior",
    24: "Skald",
    26: "Healer",
    28: "Shaman",
    29: "Runemaster",
    31: "Berserker",
    33: "Hero",
    40: "Eldritch",
    41: "Enchanter",
    43: "Blademaster",
    44: "Hero",
    45: "Champion",
    47: "Druid",
    48: "Bard",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matrix", choices=("quick", "realm-smoke", "standard-smoke"), default="quick")
    parser.add_argument("--realms", default="", help="comma-separated realm keys or names to run, e.g. alb,mid,Hibernia")
    parser.add_argument("--party-sizes", default="1", help="comma-separated party sizes")
    parser.add_argument("--output-root", type=Path, default=Path("test-output/dynamic-quest-matrix"))
    parser.add_argument(
        "--accounts-pattern",
        default="tools/dummy-accounts-{realm_slug}-40.csv",
        help="CSV path pattern. Fields: {key}, {realm}, {realm_slug}, {party_size}",
    )
    parser.add_argument("--account-offset", type=int, default=0, help="skip this many rows from the accounts CSV before selecting the party")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument(
        "--dynamic-quest-submit-evaluation",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="submit the dummy case quality score to the dynamic quest evaluation API",
    )
    parser.add_argument(
        "--dynamic-quest-evaluation-min-score",
        type=int,
        default=70,
        help="minimum score the server should require before keeping a story-cache quest active",
    )
    parser.add_argument(
        "--dynamic-quest-min-action-scene-cohesion",
        type=int,
        default=70,
        help="minimum action-scene cohesion score for Skyrim-grade dynamic quest E2E; 0 disables this quality gate",
    )
    parser.add_argument(
        "--dynamic-quest-min-cinematic-catalog-role-variety",
        type=int,
        default=2,
        help="minimum distinct catalogRole values observed in cinematic timeline details; 0 disables this quality gate",
    )
    parser.add_argument(
        "--dynamic-quest-min-cinematic-model-role-fit",
        type=int,
        default=70,
        help="minimum cinematic model-role fit score for Skyrim-grade dynamic quest E2E; 0 disables this quality gate",
    )
    parser.add_argument(
        "--dynamic-quest-evaluation-api-url",
        default="",
        help="override the dynamic quest evaluation API URL",
    )
    parser.add_argument(
        "--dynamic-quest-submit-setup-failure-evaluation",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="submit low scores even when the dummy run failed before a valid quest-quality observation",
    )
    parser.add_argument(
        "--dynamic-quest-cleanup-active-after-case",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="cancel active dynamic quest progress left by selected dummy accounts after each case",
    )
    parser.add_argument("--quest-start-mode", choices=("npc", "autoaccept"), default="npc")
    parser.add_argument("--dynamic-quest-return-dialog-response", choices=("accept", "decline"), default="accept")
    parser.add_argument("--require-quest-tag", default="", help="require a live dynamic quest tag when binding cases, e.g. branch:mob-growth")
    parser.add_argument("--require-world-signal", default="", help="require a live dynamic quest world-signal tag value, e.g. mob-growth:killed:region:1")
    parser.add_argument("--require-live-quest-target", default="", help="require an exact live dynamic quest target name when binding cases")
    parser.add_argument("--require-live-quest-template", default="", help="require a live dynamic quest template tag when binding cases")
    parser.add_argument(
        "--dynamic-quest-followup-growth-target",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="bind a live mob-growth target from the read-only summary API and hunt it after the expected branch node",
    )
    parser.add_argument(
        "--dynamic-quest-followup-preserve-overlevel",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="when hunting a live mob-growth followup target, keep the requested player level instead of clamping to the starter quest range",
    )
    parser.add_argument(
        "--dynamic-quest-followup-max-reference-distance",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_REFERENCE_DISTANCE,
        help="maximum live mob-growth followup target distance from the quest branch reference; <=0 disables the reachability filter",
    )
    parser.add_argument(
        "--dynamic-quest-followup-cluster-radius",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_CLUSTER_RADIUS,
        help="radius used to detect add-heavy live mob-growth followup target clusters; <=0 disables cluster scoring",
    )
    parser.add_argument(
        "--dynamic-quest-followup-max-cluster-neighbors",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_CLUSTER_NEIGHBORS,
        help="prefer live mob-growth followup targets with at most this many nearby growth neighbors; <0 disables the safety preference",
    )
    parser.add_argument(
        "--dynamic-quest-followup-alias-radius",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_ALIAS_RADIUS,
        help="nearby live mob-growth targets within this radius are accepted as equivalent followup signal targets; <=0 disables aliases",
    )
    parser.add_argument(
        "--dynamic-quest-followup-max-aliases",
        type=int,
        default=DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_ALIASES,
        help="maximum comma-separated live mob-growth followup target names to pass to the dummy; <=1 keeps only the selected target",
    )
    parser.add_argument(
        "--dynamic-quest-require-timeline-events",
        default="",
        help="forwarded to behavior dummy; requires read-only timeline event types at round end",
    )
    parser.add_argument(
        "--dynamic-quest-require-presentation-triggers",
        default="",
        help="forwarded to behavior dummy; requires read-only presentation triggers at round end",
    )
    parser.add_argument(
        "--dynamic-quest-timeline-limit",
        type=int,
        default=500,
        help="forwarded to behavior dummy; timeline API event limit for presentation-heavy quests",
    )
    parser.add_argument(
        "--dynamic-quest-expected-final-node",
        default="",
        help="forwarded to behavior dummy; treats an active quest at this final node as a successful branch wait",
    )
    parser.add_argument(
        "--skip-completed-dynamic-quest-accounts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use read-only quest APIs to avoid dummy accounts that already completed the live quest id",
    )
    parser.add_argument(
        "--skip-active-dynamic-quest-accounts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="use read-only quest APIs to avoid dummy accounts that already have any active dynamic quest",
    )
    parser.add_argument(
        "--prefer-melee-smoke-accounts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="for live dynamic quest smoke runs, prefer melee-capable dummy accounts after completed accounts are skipped",
    )
    parser.add_argument(
        "--require-melee-smoke-accounts",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="when class data is available for a live smoke run, fail instead of filling with non-melee smoke accounts",
    )
    parser.add_argument("--live-quest-start-position", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--live-quest-api-timeout", type=float, default=2.0)
    parser.add_argument(
        "--live-quest-seed-wait-seconds",
        type=float,
        default=90.0,
        help="when live quest binding is empty while the server seed is still running, wait this many seconds before failing",
    )
    parser.add_argument(
        "--live-quest-seed-wait-interval",
        type=float,
        default=3.0,
        help="poll interval while waiting for the dynamic quest seed to finish",
    )
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument("--hold", type=int, default=260)
    parser.add_argument("--safe-exit-max-seconds", type=int, default=240)
    parser.add_argument("--target-timeout", type=int, default=70)
    parser.add_argument("--max-target-distance", type=int, default=6500)
    parser.add_argument("--combat-interval", type=float, default=1.5)
    parser.add_argument("--movement-speed", type=float, default=240.0)
    parser.add_argument("--smooth-move-interval", type=float, default=0.20)
    parser.add_argument("--encounter-log-interval", type=float, default=1.0)
    parser.add_argument("--low-health-rest-percent", type=int, default=75)
    parser.add_argument("--low-health-rest-resume-percent", type=int, default=95)
    parser.add_argument("--low-health-rest-min", type=float, default=6.0)
    parser.add_argument("--low-health-rest-max", type=float, default=14.0)
    parser.add_argument("--flee-health-percent", type=int, default=55)
    parser.add_argument("--flee-pressure-health-percent", type=int, default=85)
    parser.add_argument("--flee-duration", type=float, default=24.0)
    parser.add_argument("--flee-step", type=float, default=900.0)
    parser.add_argument("--flee-move-interval", type=float, default=0.35)
    parser.add_argument("--flee-movement-speed", type=float, default=280.0)
    parser.add_argument("--flee-safe-threat-radius", type=float, default=6000.0)
    parser.add_argument("--flee-safe-point-distance", type=float, default=0.0)
    parser.add_argument("--flee-critical-health-percent", type=int, default=45)
    parser.add_argument("--flee-critical-safe-point-distance", type=float, default=0.0)
    parser.add_argument("--flee-safe-replan-damage-grace", type=float, default=6.0)
    parser.add_argument("--flee-min-damage-taken", type=int, default=20)
    parser.add_argument("--flee-damage-taken-ratio", type=float, default=1.5)
    parser.add_argument("--player-level", type=int, default=1)
    parser.add_argument("--min-target-level", type=int, default=1)
    parser.add_argument("--max-target-level", type=int, default=1)
    parser.add_argument(
        "--party-role-strategy",
        choices=("same", "mixed"),
        default="same",
        help="forwarded to behavior dummy; quest matrix defaults to same-role parties for deterministic E2E flow",
    )
    parser.add_argument(
        "--party-slot-rotations",
        default="",
        help="forwarded comma-separated action rotations, e.g. melee-basic,melee-basic",
    )
    parser.add_argument("--reset-start-positions", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--start-position-step", type=int, default=20)
    parser.add_argument("--mysql-bin", default=os.environ.get("MYSQL_BIN"))
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT", "3306")))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME", "opendaoc"))
    parser.add_argument("--db-user", default=os.environ.get("DB_USER", "root"))
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD", ""))
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def parse_party_sizes(raw: str) -> list[int]:
    sizes: list[int] = []
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        size = int(item)
        if size < 1:
            raise ValueError(f"party size must be >= 1: {size}")
        sizes.append(size)
    return sizes or [1]


def parse_realm_filter(raw: str) -> set[str]:
    return {item.strip().lower() for item in str(raw or "").split(",") if item.strip()}


def build_cases(args: argparse.Namespace) -> list[QuestCase]:
    if args.matrix == "standard-smoke":
        return build_standard_smoke_cases(args)

    realms = STARTER_REALMS[:1] if args.matrix == "quick" else STARTER_REALMS
    realm_filter = parse_realm_filter(getattr(args, "realms", ""))
    if realm_filter:
        realms = tuple(
            realm
            for realm in realms
            if realm.key.lower() in realm_filter or realm.realm.lower() in realm_filter
        )
    cases: list[QuestCase] = []
    for realm in realms:
        for party_size in parse_party_sizes(args.party_sizes):
            name = f"{realm.key}-p{party_size}"
            accounts_csv = Path(
                args.accounts_pattern.format(
                    key=realm.key,
                    realm=realm.realm,
                    realm_slug=realm.realm.lower(),
                    party_size=party_size,
                )
            )
            cases.append(
                QuestCase(
                    name=name,
                    key=realm.key,
                    realm=realm.realm,
                    region=realm.region,
                    seed_npc=realm.seed_npc,
                    target=realm.target,
                    return_home=realm.return_home,
                    party_size=party_size,
                    accounts_csv=accounts_csv,
                    output_dir=args.output_root / name,
                    min_target_level=args.min_target_level,
                    max_target_level=args.max_target_level,
                    player_level=args.player_level,
                )
            )
    return cases


def build_standard_smoke_cases(args: argparse.Namespace) -> list[QuestCase]:
    branch_by_key = {
        "alb": ("branch:mob-growth", "mob-growth:killed:region:1", True),
        "mid": ("branch:time-window", "time-window:night", False),
        "hib": ("branch:item-acquired", "item-acquired", False),
    }
    realm_filter = parse_realm_filter(getattr(args, "realms", ""))
    cases: list[QuestCase] = []
    for realm in STARTER_REALMS:
        if realm_filter and realm.key.lower() not in realm_filter and realm.realm.lower() not in realm_filter:
            continue

        require_tag, require_signal, followup_growth = branch_by_key[realm.key]
        required_timeline_events = "quest_accepted,node_advanced,choice_selected,world_impact,world_impact_summary,quest_completed,quest_rewarded"
        required_presentation_triggers = "OnAccept,OnChoiceSelected,OnComplete"
        expected_final_node = "complete"
        if require_signal != "time-window:night":
            required_timeline_events = required_timeline_events.replace(
                "choice_selected,",
                "choice_selected,world_signal,",
            )
            required_presentation_triggers = "OnAccept,OnChoiceSelected,OnWorldSignal,OnComplete"
        else:
            expected_final_node = ""

        for party_size in parse_party_sizes(args.party_sizes):
            name = f"{realm.key}-{require_tag.split(':', 1)[1]}-followup-p{party_size}"
            accounts_csv = Path(
                args.accounts_pattern.format(
                    key=realm.key,
                    realm=realm.realm,
                    realm_slug=realm.realm.lower(),
                    party_size=party_size,
                )
            )
            cases.append(
                QuestCase(
                    name=name,
                    key=realm.key,
                    realm=realm.realm,
                    region=realm.region,
                    seed_npc=realm.seed_npc,
                    target=realm.target,
                    return_home=realm.return_home,
                    party_size=party_size,
                    accounts_csv=accounts_csv,
                    output_dir=args.output_root / name,
                    min_target_level=args.min_target_level,
                    max_target_level=args.max_target_level,
                    player_level=max(args.player_level, 5),
                    quest_start_mode="npc",
                    require_quest_tag=require_tag,
                    require_world_signal=require_signal,
                    return_dialog_response="decline",
                    require_timeline_events=required_timeline_events,
                    require_presentation_triggers=required_presentation_triggers,
                    expected_final_node=expected_final_node,
                    followup_growth_target=followup_growth,
                )
            )
    return cases


def player_level_for_live_quest(
    requested_level: int,
    min_level: int,
    max_level: int,
    *,
    preserve_overlevel: bool = True,
) -> int:
    requested = max(1, min(50, int(requested_level or 1)))
    lower = max(1, min(50, int(min_level or 1)))
    upper = max(lower, min(50, int(max_level or lower)))
    if not preserve_overlevel and requested > upper:
        return upper
    if requested >= lower:
        return requested
    return upper


def case_quest_start_mode(case: QuestCase, args: argparse.Namespace) -> str:
    return text_value(getattr(case, "quest_start_mode", "")) or getattr(args, "quest_start_mode", "npc")


def case_return_dialog_response(case: QuestCase, args: argparse.Namespace) -> str:
    return text_value(getattr(case, "return_dialog_response", "")) or getattr(args, "dynamic_quest_return_dialog_response", "accept")


def case_required_quest_tag(case: QuestCase, args: argparse.Namespace) -> str:
    return text_value(getattr(case, "require_quest_tag", "")) or text_value(getattr(args, "require_quest_tag", ""))


def case_required_world_signal(case: QuestCase, args: argparse.Namespace) -> str:
    return text_value(getattr(case, "require_world_signal", "")) or text_value(getattr(args, "require_world_signal", ""))


def case_required_timeline_events(case: QuestCase, args: argparse.Namespace) -> str:
    return text_value(getattr(case, "require_timeline_events", "")) or text_value(getattr(args, "dynamic_quest_require_timeline_events", ""))


def case_required_presentation_triggers(case: QuestCase, args: argparse.Namespace) -> str:
    return text_value(getattr(case, "require_presentation_triggers", "")) or text_value(getattr(args, "dynamic_quest_require_presentation_triggers", ""))


def quest_case_expects_branch_choice(case: QuestCase | None) -> bool:
    if case is None:
        return False

    required_tag = text_value(getattr(case, "require_quest_tag", "")).lower()
    if required_tag.startswith("branch:"):
        return True

    tags = {text_value(tag).lower() for tag in getattr(case, "tags", ()) if text_value(tag)}
    return any(tag.startswith("branch:") for tag in tags)


def quest_case_expects_world_signal(case: QuestCase | None) -> bool:
    if case is None:
        return False

    if text_value(getattr(case, "require_world_signal", "")):
        return True

    tags = {text_value(tag).lower() for tag in getattr(case, "tags", ()) if text_value(tag)}
    return any(tag.startswith("world-signal:") for tag in tags)


def dynamic_quest_timeline_limit(args: argparse.Namespace) -> int:
    return max(
        DYNAMIC_QUEST_PRESENTATION_TIMELINE_MIN_LIMIT,
        int(getattr(args, "dynamic_quest_timeline_limit", 500) or 500),
    )


def case_return_complete_wait(case: QuestCase) -> float:
    if text_value(getattr(case, "require_world_signal", "")).lower() == "time-window:night":
        return 70.0
    return 2.0


def case_expected_final_node(case: QuestCase, args: argparse.Namespace) -> str:
    return text_value(getattr(case, "expected_final_node", "")) or text_value(getattr(args, "dynamic_quest_expected_final_node", ""))


def case_followup_growth_target(case: QuestCase, args: argparse.Namespace) -> bool:
    return bool(getattr(case, "followup_growth_target", False)) or bool(getattr(args, "dynamic_quest_followup_growth_target", False))


def flee_safe_point_distance_for_case(case: QuestCase, args: argparse.Namespace) -> float:
    configured = float(getattr(args, "flee_safe_point_distance", 0.0) or 0.0)
    if configured > 0.0:
        return configured
    if int(case.player_level or 0) >= 45:
        return 9000.0
    return 1400.0 if is_low_level_solo_case(case) else 5200.0


def flee_critical_safe_point_distance_for_case(case: QuestCase, args: argparse.Namespace) -> float:
    configured = float(getattr(args, "flee_critical_safe_point_distance", 0.0) or 0.0)
    if configured > 0.0:
        return configured
    if int(case.player_level or 0) >= 45:
        return 14000.0
    return 2200.0 if is_low_level_solo_case(case) else 9000.0


def is_low_level_solo_case(case: QuestCase) -> bool:
    return int(case.player_level or 0) <= 4 and int(case.party_size or 1) <= 1


def low_level_cap(case: QuestCase, value: int, cap: int) -> int:
    return min(int(value or 0), cap) if is_low_level_solo_case(case) else int(value or 0)


def low_level_float_cap(case: QuestCase, value: float, cap: float) -> float:
    return min(float(value or 0.0), cap) if is_low_level_solo_case(case) else float(value or 0.0)


def low_level_required_target_commit_floor(case: QuestCase) -> int:
    return 25 if is_low_level_solo_case(case) else 0


def required_target_home_radius_for_case(case: QuestCase, args: argparse.Namespace) -> int:
    target_radius = max(int(args.max_target_distance or 0), int(case.target_home_radius or 0))
    if case_quest_start_mode(case, args) == "autoaccept" and text_value(case.quest_id):
        target_radius = max(target_radius, 9000)
    if target_radius <= 0:
        target_radius = 6500
    return target_radius


def build_behavior_command(case: QuestCase, args: argparse.Namespace) -> list[str]:
    case.output_dir.mkdir(parents=True, exist_ok=True)
    accounts_csv = case_accounts_csv(case, args)
    command = [
        sys.executable,
        "tools/behavior-dummy-client.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--api-port",
        str(args.api_port),
        "--realm",
        str(REALM_IDS_BY_KEY.get(case.key, 1)),
        "--accounts",
        str(accounts_csv),
        "--concurrency",
        str(case.party_size),
        "--party-size",
        str(case.party_size),
        "--party-role-strategy",
        args.party_role_strategy,
        "--rounds",
        str(args.rounds),
        "--hold",
        str(args.hold),
        "--safe-exit-max-seconds",
        str(args.safe_exit_max_seconds),
        "--hunter",
        "--combat",
        "--use-skills",
        "--startup-auto-train",
        "--startup-train-level",
        str(case.player_level),
        "--player-level",
        str(case.player_level),
        "--low-health-rest-percent",
        str(low_level_cap(case, args.low_health_rest_percent, 45)),
        "--low-health-rest-resume-percent",
        str(args.low_health_rest_resume_percent),
        "--low-health-rest-min",
        str(args.low_health_rest_min),
        "--low-health-rest-max",
        str(args.low_health_rest_max),
        "--flee-health-percent",
        str(low_level_cap(case, args.flee_health_percent, 35)),
        "--flee-pressure-health-percent",
        str(low_level_cap(case, args.flee_pressure_health_percent, 60)),
        "--flee-duration",
        str(low_level_float_cap(case, args.flee_duration, 8.0)),
        "--flee-step",
        str(args.flee_step),
        "--flee-move-interval",
        str(args.flee_move_interval),
        "--flee-movement-speed",
        str(args.flee_movement_speed),
        "--flee-use-sprint",
        "--flee-dynamic-safe-point",
        "--flee-safe-threat-radius",
        str(args.flee_safe_threat_radius),
        "--flee-safe-point-distance",
        str(flee_safe_point_distance_for_case(case, args)),
        "--flee-critical-health-percent",
        str(low_level_cap(case, args.flee_critical_health_percent, 30)),
        "--flee-critical-safe-point-distance",
        str(flee_critical_safe_point_distance_for_case(case, args)),
        "--flee-safe-api-scout",
        "--flee-safe-replan-damage-grace",
        str(low_level_float_cap(case, args.flee_safe_replan_damage_grace, 3.0)),
        "--flee-min-damage-taken",
        str(args.flee_min_damage_taken),
        "--flee-damage-taken-ratio",
        str(args.flee_damage_taken_ratio),
        "--required-target-tank-commit-health-percent",
        str(low_level_required_target_commit_floor(case)),
        "--min-target-level",
        str(case.min_target_level),
        "--max-target-level",
        str(case.max_target_level),
        "--target-selection",
        "nearest",
        "--target-pool",
        "1",
        "--max-target-distance",
        str(args.max_target_distance),
        "--target-timeout",
        str(args.target_timeout),
        "--combat-interval",
        str(args.combat_interval),
        "--target-loss-grace",
        "1",
        "--reject-target-on-server-los-failure",
        "--server-los-failure-target-cooldown",
        "4",
        "--server-los-failure-grace",
        "10",
        "--attack-range",
        "350",
        "--melee-stick-attack",
        "--melee-stick-attack-distance",
        "1800",
        "--target-face-command-interval",
        "0.8",
        "--melee-range-buffer",
        "300",
        "--minimum-melee-stop-distance",
        "60",
        "--smooth-movement",
        "--movement-speed",
        str(args.movement_speed),
        "--smooth-move-interval",
        str(args.smooth_move_interval),
        "--movement-update-interval",
        str(args.smooth_move_interval),
        "--require-target-name",
        case.target,
        "--stop-after-required-target-removed",
        "--no-required-target-removed-api-confirm",
        "--metrics-csv",
        str(case.output_dir / "metrics.csv"),
        "--combat-csv",
        str(case.output_dir / "combat.csv"),
        "--report-md",
        str(case.output_dir / "report.md"),
        "--encounter-log",
        str(case.output_dir / "encounters-{username}-{round}.jsonl"),
        "--encounter-log-interval",
        str(args.encounter_log_interval),
        "--trace-movement-log",
        str(case.output_dir / "trace-{username}-{round}.jsonl"),
    ]

    if case.target_home is not None:
        target_home = ",".join(str(value) for value in case.target_home)
        target_radius = required_target_home_radius_for_case(case, args)
        command.extend(
            [
                "--required-target-home",
                target_home,
                "--target-home-max-distance",
                str(target_radius),
                "--required-target-home-hunt-distance",
                str(target_radius),
            ]
        )

    party_slot_rotations = args.party_slot_rotations.strip()
    if not party_slot_rotations:
        party_slot_rotations = ",".join("melee-basic" for _ in range(case.party_size))
    if party_slot_rotations:
        command.extend(["--party-slot-rotations", party_slot_rotations])

    if case.party_size > 1:
        command.extend(
            [
                "--party-min-ready",
                str(case.party_size),
                "--party-form-up-delay",
                "1.0",
                "--party-form-up-timeout",
                "0.0",
            ]
        )

    return_dialog_response = case_return_dialog_response(case, args)
    if case.followup_target and return_dialog_response == "accept":
        return_dialog_response = "decline"

    if case_quest_start_mode(case, args) == "autoaccept":
        command.extend([
            "--dynamic-quest-observe-final-progress",
            "--dynamic-quest-return-dialog-response",
            return_dialog_response,
            "--startup-service-progress-wait-seconds",
            "12",
            "--startup-service-progress-poll-interval",
            "0.5",
            "--startup-service-progress-max-retries",
            "0",
        ])
    else:
        return_home = ",".join(str(value) for value in case.return_home)
        command.extend(
            [
                "--dynamic-quest-return-after-required-target",
                "--dynamic-quest-return-npc-name",
                case.seed_npc,
                "--dynamic-quest-return-home",
                return_home,
                "--dynamic-quest-return-complete-wait",
                str(case_return_complete_wait(case)),
                "--dynamic-quest-return-dialog-response",
                return_dialog_response,
                "--startup-service-npc-name",
                case.seed_npc,
                "--startup-service-scan-seconds",
                "2",
                "--startup-service-interact",
                "--startup-service-accept-dialog",
            ]
        )

    if case.quest_id:
        command.extend(["--dynamic-quest-expected-quest-id", case.quest_id])

    required_timeline_events = case_required_timeline_events(case, args)
    if required_timeline_events:
        command.extend(["--dynamic-quest-require-timeline-events", required_timeline_events])

    required_presentation_triggers = case_required_presentation_triggers(case, args)
    if required_presentation_triggers:
        command.extend(["--dynamic-quest-require-presentation-triggers", required_presentation_triggers])
    command.extend(["--dynamic-quest-timeline-limit", str(dynamic_quest_timeline_limit(args))])

    expected_final_node = case_expected_final_node(case, args)
    if expected_final_node:
        command.extend(["--dynamic-quest-expected-final-node", expected_final_node])

    if case.followup_target:
        command.extend(["--dynamic-quest-followup-target-name", case.followup_target])
        if case.followup_home is not None:
            command.extend([
                "--dynamic-quest-followup-target-home",
                ",".join(str(value) for value in case.followup_home),
            ])
        if case.followup_min_target_level > 0:
            command.extend(["--dynamic-quest-followup-min-target-level", str(case.followup_min_target_level)])
        if case.followup_max_target_level > 0:
            command.extend(["--dynamic-quest-followup-max-target-level", str(case.followup_max_target_level)])
        if case.followup_object_id > 0:
            api_host = args.host if args.host in ("127.0.0.1", "localhost", "::1") else "127.0.0.1"
            query = urllib.parse.urlencode(
                {
                    "region": max(0, int(case.region or 0)),
                    "objectId": case.followup_object_id,
                    "limit": 1,
                }
            )
            command.extend([
                "--required-target-api",
                "--required-target-api-url",
                f"http://{api_host}:{int(args.api_port)}/api/dummy/combat/npcs?{query}",
                "--required-target-api-name",
                case.followup_target.split(",", 1)[0].strip(),
                "--required-target-api-region",
                str(max(0, int(case.region or 0))),
                "--required-target-api-limit",
                "1",
                "--required-target-api-interval",
                "0.5",
                "--required-target-api-timeout",
                "1.5",
            ])

    return command


def sql_quote(value: object) -> str:
    return "'" + str(value or "").replace("\\", "\\\\").replace("'", "''") + "'"


def build_case_expression(column: str, account_rows: list[dict[str, str]], values: list[int]) -> str:
    whens = " ".join(
        f"WHEN {sql_quote(row.get('username'))} THEN {value}"
        for row, value in zip(account_rows, values, strict=False)
    )
    return f"CASE `AccountName` {whens} ELSE `{column}` END"


def build_start_position_update_sql(
    case: QuestCase,
    account_rows: list[dict[str, str]],
    position_step: int,
    account_offset: int = 0,
    start_position: StartPosition | None = None,
    player_level: int | None = None,
) -> str:
    offset = max(0, int(account_offset))
    selected_rows = [
        row
        for row in account_rows[offset : offset + case.party_size]
        if str(row.get("username") or "").strip()
    ]
    if not selected_rows:
        return ""

    position = start_position or StartPosition(case.region, *case.return_home)
    x, y, z = position.x, position.y, position.z
    step = max(0, int(position_step))
    x_values = [x + index * step for index, _ in enumerate(selected_rows)]
    y_values = [y + index * step for index, _ in enumerate(selected_rows)]
    z_values = [z for _ in selected_rows]
    accounts = ", ".join(sql_quote(row.get("username")) for row in selected_rows)
    level_assignment = ""
    if player_level is not None:
        level = max(1, min(50, int(player_level)))
        level_assignment = f"  `Level` = {level},\n"

    return (
        "UPDATE `dolcharacters`\n"
        "SET\n"
        f"{level_assignment}"
        f"  `Health` = {DUMMY_RESET_RESOURCE_VALUE},\n"
        f"  `Mana` = {DUMMY_RESET_RESOURCE_VALUE},\n"
        f"  `Endurance` = {DUMMY_RESET_RESOURCE_VALUE},\n"
        f"  `Region` = {position.region},\n"
        f"  `Xpos` = {build_case_expression('Xpos', selected_rows, x_values)},\n"
        f"  `Ypos` = {build_case_expression('Ypos', selected_rows, y_values)},\n"
        f"  `Zpos` = {build_case_expression('Zpos', selected_rows, z_values)},\n"
        f"  `BindRegion` = {position.region},\n"
        f"  `BindXpos` = {build_case_expression('BindXpos', selected_rows, x_values)},\n"
        f"  `BindYpos` = {build_case_expression('BindYpos', selected_rows, y_values)},\n"
        f"  `BindZpos` = {build_case_expression('BindZpos', selected_rows, z_values)}\n"
        f"WHERE `AccountName` IN ({accounts});"
    )


def build_dynamic_quest_api_url(args: argparse.Namespace) -> str:
    return f"http://{args.host}:{int(args.api_port)}/api/world/dynamic-quests"


def build_dynamic_quest_seed_status_api_url(args: argparse.Namespace) -> str:
    return f"{build_dynamic_quest_api_url(args)}/seed/status"


def build_dynamic_quest_evaluation_api_url(args: argparse.Namespace) -> str:
    configured = text_value(getattr(args, "dynamic_quest_evaluation_api_url", ""))
    if configured:
        return configured
    return f"http://{args.host}:{int(args.api_port)}/api/world/dynamic-quests/evaluation"


def fetch_live_dynamic_quests(args: argparse.Namespace) -> dict[str, object]:
    request = urllib.request.Request(build_dynamic_quest_api_url(args), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=float(args.live_quest_api_timeout)) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_dynamic_quest_seed_status(args: argparse.Namespace) -> dict[str, object]:
    request = urllib.request.Request(build_dynamic_quest_seed_status_api_url(args), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=float(args.live_quest_api_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def dynamic_quest_seed_is_running(status: dict[str, object]) -> bool:
    messages = status.get("messages", []) if isinstance(status, dict) else []
    if not isinstance(messages, list):
        return False

    return any("seed running" in text_value(message).lower() for message in messages)


def build_mob_growth_summary_api_url(args: argparse.Namespace, region_id: int = 0) -> str:
    query_values: dict[str, int] = {"limit": 100}
    if int(region_id or 0) > 0:
        query_values["region"] = int(region_id)
    query = urllib.parse.urlencode(query_values)
    return f"http://{args.host}:{int(args.api_port)}/api/world/mob-growth/summary?{query}"


def fetch_mob_growth_summary(args: argparse.Namespace, region_id: int = 0) -> dict[str, object]:
    request = urllib.request.Request(build_mob_growth_summary_api_url(args, region_id), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=float(args.live_quest_api_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def world_signal_region(signal: str) -> int:
    prefix = "mob-growth:killed:region:"
    signal = text_value(signal).lower()
    if not signal.startswith(prefix):
        return 0
    return int_value(signal[len(prefix):])


def world_signal_stage(signal: str) -> str:
    signal = text_value(signal).lower()
    for prefix in ("mob-growth:killed:stage:", "mob-growth:killed:"):
        if signal.startswith(prefix):
            stage = signal[len(prefix):]
            if stage in {"elite", "champion", "boss"}:
                return stage
    return ""


def mob_growth_target_matches_signal(item: dict[str, object], signal: str) -> bool:
    signal = text_value(signal).lower()
    if not signal:
        return True

    region = world_signal_region(signal)
    if region > 0 and int_value(item.get("regionId")) != region:
        return False

    stage = world_signal_stage(signal)
    item_stage = text_value(item.get("stage")).lower()
    if stage and item_stage != stage:
        return False

    if signal == "mob-growth:killed:mutant" and not truthy(item.get("isMutant")):
        return False

    if signal.startswith("mob-growth:killed:mob:"):
        mob_id = signal.removeprefix("mob-growth:killed:mob:")
        if text_value(item.get("mobId")).lower() != mob_id:
            return False

    return True


def distance_squared_to_point(item: dict[str, object], point: tuple[int, int, int] | None) -> int:
    if point is None:
        return 0

    dx = int_value(item.get("x")) - int(point[0])
    dy = int_value(item.get("y")) - int(point[1])
    dz = int_value(item.get("z")) - int(point[2])
    return dx * dx + dy * dy + dz * dz


def distance_squared_between_mob_growth_items(left: dict[str, object], right: dict[str, object]) -> int:
    dx = int_value(left.get("x")) - int_value(right.get("x"))
    dy = int_value(left.get("y")) - int_value(right.get("y"))
    dz = int_value(left.get("z")) - int_value(right.get("z"))
    return dx * dx + dy * dy + dz * dz


def mob_growth_followup_cluster_neighbors(
    item: dict[str, object],
    candidates: list[dict[str, object]],
    *,
    radius: int,
) -> int:
    if radius <= 0:
        return 0

    radius_squared = radius * radius
    region_id = int_value(item.get("regionId")) or int_value(item.get("region"))
    neighbors = 0
    for other in candidates:
        if other is item:
            continue
        other_region_id = int_value(other.get("regionId")) or int_value(other.get("region"))
        if region_id and other_region_id and region_id != other_region_id:
            continue
        if distance_squared_between_mob_growth_items(item, other) <= radius_squared:
            neighbors += 1
    return neighbors


def prefer_less_clustered_mob_growth_candidates(
    candidates: list[dict[str, object]],
    *,
    radius: int,
    max_cluster_neighbors: int,
) -> list[dict[str, object]]:
    if radius <= 0 or max_cluster_neighbors < 0:
        return candidates

    less_clustered = [
        item for item in candidates
        if mob_growth_followup_cluster_neighbors(item, candidates, radius=radius) <= max_cluster_neighbors
    ]
    return less_clustered or candidates


def mob_growth_followup_sort_key(
    item: dict[str, object],
    *,
    preferred_level: int,
    reference_position: tuple[int, int, int] | None,
) -> tuple[int, int, int, int, int, int, int, str]:
    level = int_value(item.get("effectiveLevel")) or int_value(item.get("baseLevel")) or 1
    over_preferred_level = max(0, level - preferred_level) if preferred_level > 0 else 0
    stage = text_value(item.get("stage")).lower()
    return (
        int_value(item.get("playerKills")),
        int_value(item.get("combatCount")),
        1 if stage == "boss" else 0,
        over_preferred_level,
        distance_squared_to_point(item, reference_position),
        level,
        -int_value(item.get("growthScore")),
        text_value(item.get("mobId")),
    )


def live_mob_growth_candidate_items(payload: dict[str, object], signal: str) -> list[dict[str, object]]:
    top = payload.get("top", []) if isinstance(payload, dict) else []
    candidates: list[dict[str, object]] = []
    for item in top if isinstance(top, list) else []:
        if not isinstance(item, dict):
            continue
        if not truthy(item.get("isAlive")):
            continue
        if int_value(item.get("x")) <= 0 or int_value(item.get("y")) <= 0:
            continue
        stage = text_value(item.get("stage")).lower()
        if stage in {"", "normal"} and not truthy(item.get("isMutant")):
            continue
        if not mob_growth_target_matches_signal(item, signal):
            continue
        candidates.append(item)
    return candidates


def mob_growth_candidate_level(item: dict[str, object]) -> int:
    return int_value(item.get("effectiveLevel")) or int_value(item.get("baseLevel")) or 1


def mob_growth_candidate_name(item: dict[str, object]) -> str:
    return text_value(item.get("name")) or text_value(item.get("mobId"))


def build_mob_growth_followup_aliases(
    selected: dict[str, object],
    candidates: list[dict[str, object]],
    *,
    alias_radius: int,
    max_aliases: int,
) -> tuple[tuple[str, ...], int, int]:
    selected_name = mob_growth_candidate_name(selected)
    selected_level = max(1, mob_growth_candidate_level(selected))
    if max_aliases <= 1 or alias_radius <= 0:
        return ((selected_name,) if selected_name else ()), selected_level, selected_level

    selected_point = (
        int_value(selected.get("x")),
        int_value(selected.get("y")),
        int_value(selected.get("z")),
    )
    selected_region = int_value(selected.get("regionId")) or int_value(selected.get("region"))
    radius_squared = alias_radius * alias_radius
    nearby: list[dict[str, object]] = []
    for item in candidates:
        name = mob_growth_candidate_name(item)
        if not name:
            continue
        item_region = int_value(item.get("regionId")) or int_value(item.get("region"))
        if selected_region and item_region and selected_region != item_region:
            continue
        if distance_squared_to_point(item, selected_point) > radius_squared:
            continue
        nearby.append(item)

    nearby.sort(
        key=lambda item: (
            0 if item is selected else 1,
            distance_squared_to_point(item, selected_point),
            mob_growth_candidate_level(item),
            mob_growth_candidate_name(item).lower(),
        )
    )

    names: list[str] = []
    levels: list[int] = []
    seen: set[str] = set()
    for item in nearby:
        name = mob_growth_candidate_name(item)
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        names.append(name)
        levels.append(max(1, mob_growth_candidate_level(item)))
        if len(names) >= max_aliases:
            break

    if selected_name and selected_name.lower() not in seen:
        names.insert(0, selected_name)
        levels.insert(0, selected_level)

    return tuple(names), min(levels or [selected_level]), max(levels or [selected_level])


def extract_live_mob_growth_target(
    payload: dict[str, object],
    signal: str,
    *,
    max_preferred_level: int = 0,
    reference_position: tuple[int, int, int] | None = None,
    max_reference_distance: int = DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_REFERENCE_DISTANCE,
    cluster_radius: int = DEFAULT_MOB_GROWTH_FOLLOWUP_CLUSTER_RADIUS,
    max_cluster_neighbors: int = DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_CLUSTER_NEIGHBORS,
    alias_radius: int = DEFAULT_MOB_GROWTH_FOLLOWUP_ALIAS_RADIUS,
    max_aliases: int = DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_ALIASES,
) -> LiveMobGrowthTarget | None:
    candidates = live_mob_growth_candidate_items(payload, signal)
    if not candidates:
        return None

    preferred_level = max(0, int(max_preferred_level or 0))
    if preferred_level > 0:
        preferred_candidates = [
            item for item in candidates
            if mob_growth_candidate_level(item) <= preferred_level
        ]
        if not preferred_candidates:
            return None
        candidates = preferred_candidates

    max_distance = int(max_reference_distance or 0)
    if reference_position is not None and max_distance > 0:
        max_distance_squared = max_distance * max_distance
        reachable_candidates = [
            item for item in candidates
            if distance_squared_to_point(item, reference_position) <= max_distance_squared
        ]
        if not reachable_candidates:
            return None
        candidates = reachable_candidates

    alias_candidates = list(candidates)
    candidates = prefer_less_clustered_mob_growth_candidates(
        candidates,
        radius=int(cluster_radius or 0),
        max_cluster_neighbors=int(max_cluster_neighbors),
    )

    candidates.sort(
        key=lambda item: mob_growth_followup_sort_key(
            item,
            preferred_level=preferred_level,
            reference_position=reference_position,
        )
    )
    item = candidates[0]
    aliases, min_level, max_level = build_mob_growth_followup_aliases(
        item,
        alias_candidates,
        alias_radius=int(alias_radius or 0),
        max_aliases=int(max_aliases or 0),
    )
    return LiveMobGrowthTarget(
        name=mob_growth_candidate_name(item),
        region=int_value(item.get("regionId")),
        x=int_value(item.get("x")),
        y=int_value(item.get("y")),
        z=int_value(item.get("z")),
        min_level=max(1, min_level),
        max_level=max(1, max_level),
        stage=text_value(item.get("stage")),
        mob_id=text_value(item.get("mobId")),
        object_id=int_value(item.get("objectId")),
        aliases=aliases,
    )


def build_dynamic_quest_player_api_url(args: argparse.Namespace, path: str, username: str) -> str:
    query_args = {"player": username}
    if text_value(path).lower() == "timeline":
        query_args["limit"] = str(dynamic_quest_timeline_limit(args))
    query = urllib.parse.urlencode(query_args)
    return f"http://{args.host}:{int(args.api_port)}/api/world/dynamic-quests/{path}?{query}"


def build_dynamic_quest_progress_cancel_api_url(args: argparse.Namespace, player: str, reason: str) -> str:
    query = urllib.parse.urlencode({"player": player, "reason": reason})
    return f"http://{args.host}:{int(args.api_port)}/api/world/dynamic-quests/progress/cancel?{query}"


def fetch_dynamic_quest_player_api(args: argparse.Namespace, path: str, username: str) -> dict[str, object]:
    request = urllib.request.Request(build_dynamic_quest_player_api_url(args, path, username), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=float(args.live_quest_api_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def cancel_dynamic_quest_progress(args: argparse.Namespace, player: str, reason: str) -> dict[str, object]:
    request = urllib.request.Request(
        build_dynamic_quest_progress_cancel_api_url(args, player, reason),
        headers={"Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=float(args.live_quest_api_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def cleanup_active_dynamic_quest_progress_for_accounts(
    args: argparse.Namespace,
    usernames: list[str],
    *,
    reason: str,
) -> list[dict[str, object]]:
    results: list[dict[str, object]] = []
    for username in usernames:
        username = text_value(username)
        if not username:
            continue

        try:
            progress = fetch_dynamic_quest_player_api(args, "progress", username)
        except Exception as exc:  # noqa: BLE001 - cleanup should report and keep the matrix result.
            results.append({"account": username, "error": f"progress lookup failed: {exc}"})
            continue

        active = progress.get("active", []) if isinstance(progress, dict) else []
        for item in active if isinstance(active, list) else []:
            if not isinstance(item, dict):
                continue
            player = text_value(item.get("player")) or username
            quest_id = text_value(item.get("questId"))
            try:
                response = cancel_dynamic_quest_progress(args, player, reason)
                results.append(
                    {
                        "account": username,
                        "player": player,
                        "questId": quest_id,
                        "cancelled": int(response.get("cancelled", 0) or 0) if isinstance(response, dict) else 0,
                    }
                )
            except Exception as exc:  # noqa: BLE001 - cleanup should report and keep the matrix result.
                results.append({"account": username, "player": player, "questId": quest_id, "error": str(exc)})
    return results


def dynamic_quest_timeline_has_terminal_event(payload: dict[str, object], quest_id: str) -> bool:
    quest_id = text_value(quest_id)
    if not quest_id:
        return False

    events = payload.get("events", []) if isinstance(payload, dict) else []
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        if text_value(event.get("questId")).lower() != quest_id.lower():
            continue
        if text_value(event.get("eventType")).lower() in {"quest_completed", "quest_rewarded"}:
            return True

    return False


def summarize_dynamic_quest_timeline_observations(payload: dict[str, object], quest_id: str) -> dict[str, int]:
    quest_id = text_value(quest_id).lower()
    counts = {
        "completed": 0,
        "choice_selected": 0,
        "choice_outcome_scene": 0,
        "choice_consequence": 0,
        "world_signal": 0,
        "presentation_beat": 0,
        "presentation_speaker_variety": 0,
        "world_impact": 0,
        "world_impact_summary": 0,
        "world_memory_marked": 0,
        "narrative_scene": 0,
        "cinematic_action": 0,
        "scene_director_beat": 0,
        "scene_beat_outcome": 0,
        "scene_choreography_phase": 0,
        "scene_actor_exchange": 0,
        "scene_exchange_outcome": 0,
        "scene_outcome_signal": 0,
        "scene_consequence": 0,
        "scene_world_signal": 0,
        "world_signal_scene_shift": 0,
        "cinematic_cleanup": 0,
        "kill_confirmed": 0,
        "cinematic_variety": 0,
        "cinematic_motion_variety": 0,
        "cinematic_staggered_scene": 0,
        "cinematic_objective_focal_scene": 0,
        "cinematic_actor_role_variety": 0,
        "cinematic_choreographed_scene": 0,
        "cinematic_interaction_scene": 0,
        "cinematic_tactic_variety": 0,
        "cinematic_actor_instances": 0,
        "cinematic_actor_peak": 0,
        "cinematic_actor_spawn_summary": 0,
        "cinematic_actor_spawned_total": 0,
        "cinematic_actor_spawned_peak": 0,
        "cinematic_actor_spawn_failed": 0,
        "cinematic_actor_cleanup_scheduled": 0,
        "cinematic_actor_motion_summary": 0,
        "cinematic_actor_motion_commands": 0,
        "cinematic_actor_motion_commands_peak": 0,
        "cinematic_actor_motion_commands_per_actor_peak": 0,
        "cinematic_actor_motion_spawned_total": 0,
        "cinematic_actor_engagement_summary": 0,
        "cinematic_actor_engagement_pairs": 0,
        "cinematic_actor_engagement_pairs_peak": 0,
        "cinematic_actor_engaged_total": 0,
        "cinematic_actor_engagement_spawned_total": 0,
        "cinematic_catalog_role_variety": 0,
        "cinematic_marker_scene": 0,
        "cinematic_marker_variety": 0,
        "cinematic_phase_coverage": 0,
        "cinematic_setpiece_phase_coverage": 0,
        "cinematic_marker_phase_coverage": 0,
        "cinematic_story_chain": 0,
        "presentation_staged_beat": 0,
        "presentation_staged_actor_total": 0,
        "presentation_staged_actor_peak": 0,
        "presentation_staged_action_variety": 0,
        "presentation_staged_role_variety": 0,
        "presentation_staged_formation_variety": 0,
        "presentation_staged_delayed_beat": 0,
        "world_signal_scene_shift_detail": 0,
        "world_signal_scene_shift_phase_variety": 0,
        "world_signal_scene_shift_source_variety": 0,
        "world_signal_scene_shift_target_variety": 0,
    }
    if not quest_id or not isinstance(payload, dict):
        return counts

    events = payload.get("events", [])
    kill_confirmed = False
    scene_actions: set[str] = set()
    scene_motions: set[str] = set()
    scene_actor_roles: set[str] = set()
    scene_tactics: set[str] = set()
    scene_catalog_roles: set[str] = set()
    presentation_speakers: set[str] = set()
    presentation_actions: set[str] = set()
    presentation_roles: set[str] = set()
    presentation_formations: set[str] = set()
    marker_names: set[str] = set()
    cinematic_phases: set[str] = set()
    cinematic_setpiece_phases: set[str] = set()
    cinematic_marker_phases: set[str] = set()
    world_signal_scene_shift_phases: set[str] = set()
    world_signal_scene_shift_sources: set[str] = set()
    world_signal_scene_shift_targets: set[str] = set()
    cinematic_story_chain = 0
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        if text_value(event.get("questId")).lower() != quest_id:
            continue

        event_type = text_value(event.get("eventType")).lower()
        detail = text_value(event.get("detail"))
        node_id = text_value(event.get("nodeId")).lower()
        from_node_id = text_value(event.get("fromNodeId")).lower()
        if event_type in {"quest_completed", "quest_rewarded"}:
            counts["completed"] = 1
        elif event_type == "node_advanced" and from_node_id == "kill":
            kill_confirmed = True
        elif event_type in counts:
            counts[event_type] += 1
            if event_type == "cinematic_actor_spawn_summary":
                spawned = max(0, to_int(cinematic_scene_token(detail, "spawned")))
                failed = max(0, to_int(cinematic_scene_token(detail, "failed")))
                cleanup = max(0, to_int(cinematic_scene_token(detail, "cleanup")))
                counts["cinematic_actor_spawned_total"] += spawned
                counts["cinematic_actor_spawned_peak"] = max(counts["cinematic_actor_spawned_peak"], spawned)
                counts["cinematic_actor_spawn_failed"] += failed
                counts["cinematic_actor_cleanup_scheduled"] += cleanup
            if event_type == "cinematic_actor_motion_summary":
                commands = max(0, to_int(cinematic_scene_token(detail, "commands")))
                commands_per_actor = max(0, to_int(cinematic_scene_token(detail, "commandsPerActor")))
                spawned = max(0, to_int(cinematic_scene_token(detail, "spawned")))
                counts["cinematic_actor_motion_commands"] += commands
                counts["cinematic_actor_motion_commands_peak"] = max(counts["cinematic_actor_motion_commands_peak"], commands)
                counts["cinematic_actor_motion_commands_per_actor_peak"] = max(
                    counts["cinematic_actor_motion_commands_per_actor_peak"],
                    commands_per_actor,
                )
                counts["cinematic_actor_motion_spawned_total"] += spawned
            if event_type == "cinematic_actor_engagement_summary":
                pairs = max(0, to_int(cinematic_scene_token(detail, "pairs")))
                engaged_actors = max(0, to_int(cinematic_scene_token(detail, "engagedActors")))
                spawned = max(0, to_int(cinematic_scene_token(detail, "spawned")))
                counts["cinematic_actor_engagement_pairs"] += pairs
                counts["cinematic_actor_engagement_pairs_peak"] = max(counts["cinematic_actor_engagement_pairs_peak"], pairs)
                counts["cinematic_actor_engaged_total"] += engaged_actors
                counts["cinematic_actor_engagement_spawned_total"] += spawned
            if event_type == "cinematic_action" and "scene_beat:" in detail:
                phase = cinematic_story_phase(node_id)
                if phase:
                    cinematic_phases.add(phase)
                    cinematic_setpiece_phases.add(phase)
                    cinematic_story_chain = advance_cinematic_story_chain(cinematic_story_chain, phase)
                counts["scene_director_beat"] += 1
                actor_count = cinematic_scene_actor_count(detail)
                if actor_count > 0:
                    counts["cinematic_actor_instances"] += actor_count
                    counts["cinematic_actor_peak"] = max(counts["cinematic_actor_peak"], actor_count)
                scene_action = cinematic_scene_action_token(detail)
                if scene_action:
                    scene_actions.add(scene_action)
                scene_motion = cinematic_scene_token(detail, "motion")
                if scene_motion:
                    scene_motions.add(scene_motion)
                if cinematic_scene_stagger_ms(detail) > 0:
                    counts["cinematic_staggered_scene"] += 1
                if cinematic_scene_token(detail, "focal") == "objective":
                    counts["cinematic_objective_focal_scene"] += 1
                actor_role = cinematic_scene_token(detail, "actorRole")
                if actor_role:
                    scene_actor_roles.add(actor_role)
                if cinematic_scene_choreography_phases(detail) >= 2:
                    counts["cinematic_choreographed_scene"] += 1
                interaction = cinematic_scene_token(detail, "interact")
                if interaction and interaction != "none":
                    counts["cinematic_interaction_scene"] += 1
                tactic = cinematic_scene_token(detail, "tactic")
                if tactic and tactic not in {"none", "support"}:
                    scene_tactics.add(tactic)
                catalog_role = cinematic_scene_token(detail, "catalogRole")
                if catalog_role:
                    scene_catalog_roles.add(catalog_role)
            elif event_type == "cinematic_action" and detail.lower().startswith("marker:"):
                phase = cinematic_story_phase(node_id)
                if phase:
                    cinematic_phases.add(phase)
                    cinematic_marker_phases.add(phase)
                    cinematic_story_chain = advance_cinematic_story_chain(cinematic_story_chain, phase)
                counts["cinematic_marker_scene"] += 1
                marker_name = cinematic_marker_name(detail)
                if marker_name:
                    marker_names.add(marker_name)
            elif event_type == "cinematic_action":
                phase = cinematic_story_phase(node_id)
                if phase:
                    cinematic_phases.add(phase)
                    cinematic_story_chain = advance_cinematic_story_chain(cinematic_story_chain, phase)
                catalog_role = cinematic_scene_token(detail, "catalogRole")
                if catalog_role:
                    scene_catalog_roles.add(catalog_role)
            if event_type == "scene_world_signal" and is_scene_outcome_signal(detail):
                counts["scene_outcome_signal"] += 1
            if event_type == "world_signal_scene_shift":
                shift_phase = cinematic_scene_token(detail, "phase")
                shift_source = cinematic_scene_token(detail, "source")
                shift_target = cinematic_scene_token(detail, "target")
                if shift_phase and shift_source and shift_target:
                    counts["world_signal_scene_shift_detail"] += 1
                if shift_phase:
                    world_signal_scene_shift_phases.add(shift_phase)
                if shift_source:
                    world_signal_scene_shift_sources.add(shift_source)
                if shift_target:
                    world_signal_scene_shift_targets.add(shift_target)
            if event_type == "presentation_beat" and detail.lower().startswith("onkill|"):
                kill_confirmed = True
        elif event_type in {"kill_complete", "kill_completed"} or (event_type == "presentation_spotlight" and node_id == "kill"):
            kill_confirmed = True

    beats = payload.get("presentationBeats", payload.get("presentation_beats", []))
    beat_count = 0
    for beat in beats if isinstance(beats, list) else []:
        if not isinstance(beat, dict):
            continue
        if text_value(beat.get("questId")).lower() == quest_id:
            beat_count += 1
            speaker = text_value(beat.get("speaker"))
            if speaker:
                presentation_speakers.add(speaker.lower())
            presentation_action = text_value(beat.get("cinematicAction", beat.get("cinematic_action"))).lower()
            presentation_role = text_value(beat.get("sceneRole", beat.get("scene_role"))).lower()
            presentation_formation = text_value(beat.get("formation")).lower()
            presentation_actor_count = to_int(beat.get("actorCount", beat.get("actor_count")))
            presentation_delay_ms = to_int(beat.get("delayMs", beat.get("delay_ms")))
            if presentation_action or presentation_role or presentation_formation or presentation_actor_count > 0:
                counts["presentation_staged_beat"] += 1
                counts["presentation_staged_actor_total"] += max(0, presentation_actor_count)
                counts["presentation_staged_actor_peak"] = max(
                    counts["presentation_staged_actor_peak"],
                    max(0, presentation_actor_count),
                )
            if presentation_action:
                presentation_actions.add(presentation_action)
            if presentation_role:
                presentation_roles.add(presentation_role)
            if presentation_formation:
                presentation_formations.add(presentation_formation)
            if presentation_delay_ms > 0:
                counts["presentation_staged_delayed_beat"] += 1
            if text_value(beat.get("trigger")).lower() == "onkill":
                kill_confirmed = True
    counts["presentation_beat"] = max(counts["presentation_beat"], beat_count)
    counts["presentation_speaker_variety"] = len(presentation_speakers)
    counts["kill_confirmed"] = 1 if kill_confirmed else 0
    counts["cinematic_variety"] = len(scene_actions)
    counts["cinematic_motion_variety"] = len(scene_motions)
    counts["cinematic_actor_role_variety"] = len(scene_actor_roles)
    counts["cinematic_tactic_variety"] = len(scene_tactics)
    counts["cinematic_catalog_role_variety"] = len(scene_catalog_roles)
    counts["cinematic_marker_variety"] = len(marker_names)
    counts["cinematic_phase_coverage"] = len(cinematic_phases)
    counts["cinematic_setpiece_phase_coverage"] = len(cinematic_setpiece_phases)
    counts["cinematic_marker_phase_coverage"] = len(cinematic_marker_phases)
    counts["cinematic_story_chain"] = cinematic_story_chain
    counts["presentation_staged_action_variety"] = len(presentation_actions)
    counts["presentation_staged_role_variety"] = len(presentation_roles)
    counts["presentation_staged_formation_variety"] = len(presentation_formations)
    counts["world_signal_scene_shift_phase_variety"] = len(world_signal_scene_shift_phases)
    counts["world_signal_scene_shift_source_variety"] = len(world_signal_scene_shift_sources)
    counts["world_signal_scene_shift_target_variety"] = len(world_signal_scene_shift_targets)
    return counts


def cinematic_scene_action_token(detail: str) -> str:
    return cinematic_scene_token(detail, "action")


def cinematic_story_phase(node_id: str) -> str:
    node_id = text_value(node_id).lower()
    if node_id in {"talk", "explore"}:
        return "discovery"
    if node_id == "kill":
        return "battle"
    if node_id in {"return", "choice", "observe_signal", "complete"}:
        return "aftermath"
    return ""


def advance_cinematic_story_chain(current: int, phase: str) -> int:
    phase = text_value(phase).lower()
    if phase == "discovery":
        return max(current, 1)
    if phase == "battle" and current >= 1:
        return max(current, 2)
    if phase == "aftermath" and current >= 2:
        return max(current, 3)
    return current


def cinematic_marker_name(detail: str) -> str:
    parts = [text_value(part).lower() for part in text_value(detail).split(":")]
    if len(parts) < 4 or parts[0] != "marker":
        return ""
    return parts[3]


def is_scene_outcome_signal(detail: str) -> bool:
    value = text_value(detail).lower()
    return value in {
        "scene:line_breached",
        "scene:strike_checked",
        "scene:line_held",
        "scene:ritual_disrupted",
        "scene:escape_cutoff",
        "scene:standoff_escalated",
        "scene:pressure_shifted",
    }


def cinematic_scene_token(detail: str, key: str) -> str:
    parts = [text_value(part).lower() for part in text_value(detail).split(":")]
    key = text_value(key).lower()
    for index, part in enumerate(parts[:-1]):
        if part == key:
            return parts[index + 1]
    return ""


def cinematic_scene_stagger_ms(detail: str) -> int:
    value = cinematic_scene_token(detail, "stagger")
    try:
        return max(0, int(value))
    except ValueError:
        return 0


def cinematic_scene_choreography_phases(detail: str) -> int:
    value = cinematic_scene_token(detail, "choreo")
    try:
        return max(0, int(value))
    except ValueError:
        return 0


def cinematic_scene_actor_count(detail: str) -> int:
    value = cinematic_scene_token(detail, "actors")
    try:
        return max(0, int(value))
    except ValueError:
        return 0


def dynamic_quest_progress_has_active_quest(payload: dict[str, object], quest_id: str) -> bool:
    quest_id = text_value(quest_id)
    if not quest_id:
        return False

    completed = payload.get("completedQuestIds", payload.get("completed_quest_ids", [])) if isinstance(payload, dict) else []
    if any(text_value(item).lower() == quest_id.lower() for item in completed if isinstance(completed, list)):
        return True

    active = payload.get("active", []) if isinstance(payload, dict) else []
    return any(
        isinstance(item, dict) and text_value(item.get("questId")).lower() == quest_id.lower()
        for item in active if isinstance(active, list)
    )


def dynamic_quest_progress_has_any_active_quest(payload: dict[str, object]) -> bool:
    active = payload.get("active", []) if isinstance(payload, dict) else []
    return any(isinstance(item, dict) and text_value(item.get("questId")) for item in active if isinstance(active, list))


def account_has_completed_or_active_dynamic_quest(args: argparse.Namespace, username: str, quest_id: str) -> bool:
    username = text_value(username)
    quest_id = text_value(quest_id)
    if not username or not quest_id:
        return False

    try:
        timeline = fetch_dynamic_quest_player_api(args, "timeline", username)
        if dynamic_quest_timeline_has_terminal_event(timeline, quest_id):
            return True

        progress = fetch_dynamic_quest_player_api(args, "progress", username)
        if dynamic_quest_progress_has_active_quest(progress, quest_id):
            return True
    except Exception:
        pass

    return account_has_dynamic_quest_progress_row(args, username, quest_id)


def account_has_any_active_dynamic_quest(args: argparse.Namespace, username: str) -> bool:
    username = text_value(username)
    if not username:
        return False

    try:
        progress = fetch_dynamic_quest_player_api(args, "progress", username)
        if dynamic_quest_progress_has_any_active_quest(progress):
            return True
    except Exception:
        pass

    return account_has_any_active_dynamic_quest_progress_row(args, username)


def account_has_dynamic_quest_progress_row(args: argparse.Namespace, username: str, quest_id: str) -> bool:
    username = text_value(username)
    quest_id = text_value(quest_id)
    if not username or not quest_id:
        return False

    try:
        provision_module = load_provision_module()
        db_args = build_db_args(args, provision_module)
        if not provision_module.mysql_bin_available(db_args.mysql_bin):
            return False

        sql = (
            "SELECT IsActive, IsComplete, Completed, Failed "
            "FROM dynamic_quest_progress "
            f"WHERE QuestId = {sql_quote(quest_id)} "
            f"AND LOWER(PlayerName) = LOWER({sql_quote(username)}) "
            "ORDER BY UpdatedAt DESC LIMIT 10;"
        )
        rows = provision_module.parse_mysql_rows(provision_module.run_mysql(db_args, sql))
    except Exception:
        return False

    for row in rows:
        if truthy(row.get("Failed")):
            continue
        if truthy(row.get("IsActive")) or truthy(row.get("IsComplete")) or truthy(row.get("Completed")):
            return True

    return False


def account_has_any_active_dynamic_quest_progress_row(args: argparse.Namespace, username: str) -> bool:
    username = text_value(username)
    if not username:
        return False

    try:
        provision_module = load_provision_module()
        db_args = build_db_args(args, provision_module)
        if not provision_module.mysql_bin_available(db_args.mysql_bin):
            return False

        sql = (
            "SELECT IsActive, Failed "
            "FROM dynamic_quest_progress "
            f"WHERE LOWER(PlayerName) = LOWER({sql_quote(username)}) "
            "ORDER BY UpdatedAt DESC LIMIT 20;"
        )
        rows = provision_module.parse_mysql_rows(provision_module.run_mysql(db_args, sql))
    except Exception:
        return False

    for row in rows:
        if truthy(row.get("Failed")):
            continue
        if truthy(row.get("IsActive")):
            return True

    return False


def existing_world_character_accounts(args: argparse.Namespace, usernames: list[str]) -> set[str] | None:
    normalized = sorted({text_value(username).lower() for username in usernames if text_value(username)})
    if not normalized:
        return set()

    try:
        provision_module = load_provision_module()
        db_args = build_db_args(args, provision_module)
        if not provision_module.mysql_bin_available(db_args.mysql_bin):
            return None

        account_list = ", ".join(sql_quote(username) for username in normalized)
        sql = (
            "SELECT AccountName, Name "
            "FROM DOLCharacters "
            f"WHERE LOWER(AccountName) IN ({account_list}) "
            f"OR LOWER(Name) IN ({account_list});"
        )
        rows = provision_module.parse_mysql_rows(provision_module.run_mysql(db_args, sql))
    except Exception:
        return None

    existing: set[str] = set()
    for row in rows:
        account_name = text_value(row.get("AccountName")).lower()
        character_name = text_value(row.get("Name")).lower()
        if account_name:
            existing.add(account_name)
        if character_name:
            existing.add(character_name)
    return existing


def filter_rows_with_existing_world_characters(
    rows: list[dict[str, str]],
    args: argparse.Namespace,
) -> tuple[list[dict[str, str]], list[str]]:
    usernames = [text_value(row.get("username")) for row in rows if text_value(row.get("username"))]
    existing = existing_world_character_accounts(args, usernames)
    if existing is None:
        return rows, []

    filtered: list[dict[str, str]] = []
    missing: list[str] = []
    for row in rows:
        username = text_value(row.get("username"))
        if not username:
            continue
        if username.lower() in existing:
            filtered.append(row)
        else:
            missing.append(username)
    return filtered, missing


def int_value(value: object) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def text_value(value: object) -> str:
    return str(value or "").strip()


def quest_tags(quest: dict[str, object]) -> list[str]:
    tags = quest.get("tags", [])
    if not isinstance(tags, list):
        return []
    return [text_value(tag) for tag in tags if text_value(tag)]


def quest_has_selector_tag(quest: dict[str, object]) -> bool:
    return any(tag.lower().startswith("selector:") for tag in quest_tags(quest))


def quest_has_required_live_filters(
    quest: dict[str, object],
    *,
    required_tag: str = "",
    required_world_signal: str = "",
    required_target_name: str = "",
    required_template: str = "",
) -> bool:
    tags = [tag.lower() for tag in quest_tags(quest)]
    tag = text_value(required_tag).lower()
    if tag and tag not in tags:
        return False

    template = text_value(required_template).lower()
    if template and f"template:{template}" not in tags:
        return False

    world_signal = text_value(required_world_signal).lower()
    if world_signal:
        required_signal_tag = f"world-signal:{world_signal}"
        if not any(tag == required_signal_tag or tag.startswith(f"{required_signal_tag}:") for tag in tags):
            return False

    target_name = text_value(required_target_name).lower()
    if target_name and text_value(quest.get("targetName")).lower() != target_name:
        return False

    return True


def extract_quest_start_position(quest: dict[str, object], case: QuestCase) -> StartPosition | None:
    start_node_id = text_value(quest.get("startNodeId"))
    nodes = quest.get("nodes", [])
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict) or text_value(node.get("id")) != start_node_id:
            continue
        objective = node.get("objective", {})
        if not isinstance(objective, dict):
            continue
        x = int_value(objective.get("x"))
        y = int_value(objective.get("y"))
        z = int_value(objective.get("z"))
        region = int_value(objective.get("regionId")) or case.region
        if x and y:
            return StartPosition(region, x, y, z)

    return None


def objective_position_from_node(node: dict[str, object], fallback_region: int) -> StartPosition | None:
    objective = node.get("objective", {})
    if not isinstance(objective, dict):
        return None

    x = int_value(objective.get("x"))
    y = int_value(objective.get("y"))
    z = int_value(objective.get("z"))
    region = int_value(objective.get("regionId")) or fallback_region
    if x and y:
        return StartPosition(region, x, y, z)
    return None


def extract_quest_followup_reference(quest: dict[str, object], case: QuestCase) -> StartPosition | None:
    nodes = quest.get("nodes", [])
    typed_nodes = [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []
    for preferred_id in ("observe_signal", "explore"):
        for node in typed_nodes:
            if text_value(node.get("id")).lower() != preferred_id:
                continue
            position = objective_position_from_node(node, case.region)
            if position is not None:
                return position

    return None


def extract_quest_kill_level_bounds(quest: dict[str, object]) -> tuple[int, int]:
    nodes = quest.get("nodes", [])
    typed_nodes = [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []
    for node in typed_nodes:
        if text_value(node.get("type")).lower() not in {"1", "kill"}:
            continue
        objective = node.get("objective", {})
        if not isinstance(objective, dict):
            continue
        min_level = int_value(objective.get("minLevel"))
        max_level = int_value(objective.get("maxLevel"))
        if min_level or max_level:
            if min_level <= 0:
                min_level = max_level
            if max_level <= 0:
                max_level = min_level
            if max_level < min_level:
                max_level = min_level
            return min_level, max_level

    return 0, 0


def extract_quest_kill_position(quest: dict[str, object], fallback_region: int) -> tuple[StartPosition | None, int]:
    nodes = quest.get("nodes", [])
    typed_nodes = [node for node in nodes if isinstance(node, dict)] if isinstance(nodes, list) else []
    for node in typed_nodes:
        if text_value(node.get("type")).lower() not in {"1", "kill"}:
            continue
        objective = node.get("objective", {})
        if not isinstance(objective, dict):
            continue
        x = int_value(objective.get("x"))
        y = int_value(objective.get("y"))
        z = int_value(objective.get("z"))
        region = int_value(objective.get("regionId")) or fallback_region
        radius = int_value(objective.get("radius"))
        if x and y:
            return StartPosition(region, x, y, z), max(0, radius)

    return None, 0


def extract_live_start_position(payload: dict[str, object], case: QuestCase) -> StartPosition | None:
    binding = extract_live_quest_binding(payload, case, "autoaccept")
    return binding.start_position if binding else None


def extract_live_quest_binding(
    payload: dict[str, object],
    case: QuestCase,
    quest_start_mode: str,
    *,
    required_tag: str = "",
    required_world_signal: str = "",
    required_target_name: str = "",
    required_template: str = "",
) -> LiveQuestBinding | None:
    quests = payload.get("quests", []) if isinstance(payload, dict) else []
    candidates: list[dict[str, object]] = []
    for quest in quests if isinstance(quests, list) else []:
        if not isinstance(quest, dict):
            continue
        if not quest_has_required_live_filters(
            quest,
            required_tag=required_tag,
            required_world_signal=required_world_signal,
            required_target_name=required_target_name,
            required_template=required_template,
        ):
            continue
        quest_region = int_value(quest.get("startRegionId"))
        if quest_region != case.region:
            if quest_start_mode != "autoaccept" or text_value(quest.get("realm")).lower() != case.realm.lower():
                continue
        target = text_value(quest.get("targetName"))
        if not target:
            continue
        seed_npc = text_value(quest.get("startNpcName"))
        if quest_start_mode == "npc" and not seed_npc:
            continue
        if quest_start_mode == "autoaccept" and seed_npc:
            continue
        candidates.append(quest)

    if not candidates:
        return None

    candidates.sort(
        key=lambda quest: (
            text_value(quest.get("targetName")).lower() == case.target.lower(),
            quest_has_selector_tag(quest),
        ),
        reverse=True,
    )
    quest = candidates[0]
    kill_min_level, kill_max_level = extract_quest_kill_level_bounds(quest)
    player_min_level = int_value(quest.get("minLevel")) or case.min_target_level
    player_max_level = int_value(quest.get("maxLevel")) or case.max_target_level
    if player_max_level < player_min_level:
        player_max_level = player_min_level
    min_level = kill_min_level or int_value(quest.get("minLevel")) or case.min_target_level
    max_level = kill_max_level or int_value(quest.get("maxLevel")) or case.max_target_level
    if max_level < min_level:
        max_level = min_level
    target_position, target_radius = extract_quest_kill_position(quest, case.region)

    return LiveQuestBinding(
        quest_id=text_value(quest.get("id")),
        seed_npc=text_value(quest.get("startNpcName")),
        target=text_value(quest.get("targetName")),
        min_target_level=min_level,
        max_target_level=max_level,
        min_player_level=player_min_level,
        max_player_level=player_max_level,
        start_npc_internal_id=text_value(quest.get("startNpcInternalId")),
        start_position=extract_quest_start_position(quest, case) if quest_start_mode == "autoaccept" else None,
        target_position=target_position,
        target_radius=target_radius,
        followup_reference=extract_quest_followup_reference(quest, case),
        tags=tuple(quest_tags(quest)),
    )


def fetch_live_quest_binding_with_seed_wait(
    args: argparse.Namespace,
    case: QuestCase,
    mode: str,
    *,
    required_tag: str = "",
    required_world_signal: str = "",
    required_target_name: str = "",
    required_template: str = "",
) -> LiveQuestBinding | None:
    wait_seconds = max(0.0, float(getattr(args, "live_quest_seed_wait_seconds", 0.0) or 0.0))
    wait_interval = max(0.25, float(getattr(args, "live_quest_seed_wait_interval", 3.0) or 3.0))
    deadline = time.monotonic() + wait_seconds
    last_binding: LiveQuestBinding | None = None

    while True:
        payload = fetch_live_dynamic_quests(args)
        last_binding = extract_live_quest_binding(
            payload,
            case,
            mode,
            required_tag=required_tag,
            required_world_signal=required_world_signal,
            required_target_name=required_target_name,
            required_template=required_template,
        )
        if last_binding is not None or time.monotonic() >= deadline:
            return last_binding

        try:
            status = fetch_dynamic_quest_seed_status(args)
        except Exception:  # noqa: BLE001 - keep the original no-binding failure path.
            return last_binding

        if not dynamic_quest_seed_is_running(status):
            return last_binding

        time.sleep(min(wait_interval, max(0.0, deadline - time.monotonic())))


def fetch_start_npc_position(args: argparse.Namespace, internal_id: str) -> StartPosition | None:
    if not text_value(internal_id):
        return None

    provision_module = load_provision_module()
    db_args = build_db_args(args, provision_module)
    if not provision_module.mysql_bin_available(db_args.mysql_bin):
        raise RuntimeError(f"mysql client not found: {db_args.mysql_bin}")

    sql = (
        "SELECT `Region`, `X`, `Y`, `Z` "
        "FROM `Mob` "
        f"WHERE `Mob_ID` = {sql_quote(internal_id)} "
        "LIMIT 1;"
    )
    rows = provision_module.parse_mysql_rows(provision_module.run_mysql(db_args, sql))
    if not rows:
        return None

    row = rows[0]
    x = int_value(row.get("X"))
    y = int_value(row.get("Y"))
    z = int_value(row.get("Z"))
    region = int_value(row.get("Region"))
    if not x or not y or not region:
        return None
    return StartPosition(region, x, y, z)


def bind_case_to_live_quest(
    case: QuestCase,
    binding: LiveQuestBinding,
    *,
    preserve_overlevel: bool = True,
) -> tuple[QuestCase, StartPosition | None]:
    start_position = binding.start_position
    return_home = case.return_home
    if start_position is not None and binding.seed_npc:
        return_home = (start_position.x, start_position.y, start_position.z)

    return (
        replace(
            case,
            seed_npc=binding.seed_npc or case.seed_npc,
            target=binding.target or case.target,
            return_home=return_home,
            min_target_level=binding.min_target_level,
            max_target_level=binding.max_target_level,
            player_level=player_level_for_live_quest(
                case.player_level,
                binding.min_player_level or binding.min_target_level,
                binding.max_player_level or binding.max_target_level,
                preserve_overlevel=preserve_overlevel,
            ),
            quest_id=binding.quest_id,
            target_home=(
                (binding.target_position.x, binding.target_position.y, binding.target_position.z)
                if binding.target_position is not None
                else case.target_home
            ),
            target_home_radius=binding.target_radius or case.target_home_radius,
            followup_reference=(
                (binding.followup_reference.x, binding.followup_reference.y, binding.followup_reference.z)
                if binding.followup_reference is not None
                else case.followup_reference
            ),
            tags=binding.tags,
        ),
        start_position,
    )


def bind_case_to_mob_growth_followup(case: QuestCase, target: LiveMobGrowthTarget) -> QuestCase:
    followup_names = [name for name in target.aliases if text_value(name)]
    if not followup_names and target.name:
        followup_names = [target.name]
    return replace(
        case,
        followup_target=",".join(followup_names),
        followup_home=(target.x, target.y, target.z),
        followup_min_target_level=target.min_level,
        followup_max_target_level=target.max_level,
        followup_object_id=max(0, int(target.object_id or 0)),
    )


def live_mob_growth_target_from_binding(binding: LiveQuestBinding) -> LiveMobGrowthTarget | None:
    if not text_value(binding.target) or binding.target_position is None:
        return None

    return LiveMobGrowthTarget(
        name=binding.target,
        region=binding.target_position.region,
        x=binding.target_position.x,
        y=binding.target_position.y,
        z=binding.target_position.z,
        min_level=max(1, int(binding.min_target_level or 1)),
        max_level=max(1, int(binding.max_target_level or binding.min_target_level or 1)),
        aliases=(binding.target,),
    )


def should_preserve_live_quest_overlevel(mode: str, args: argparse.Namespace) -> bool:
    return bool(getattr(args, "dynamic_quest_followup_preserve_overlevel", False))


def live_quest_binding_allows_overlevel(binding: LiveQuestBinding) -> bool:
    for tag in binding.tags:
        value = text_value(tag).lower()
        if (
            value == "branch:mob-growth"
            or value.startswith("world-signal:mob-growth:")
            or value.startswith("signal:mob-growth:")
        ):
            return True
    return False


def resolve_live_case(case: QuestCase, args: argparse.Namespace) -> tuple[QuestCase, StartPosition | None]:
    if not getattr(args, "live_quest_start_position", True):
        return case, None

    mode = case_quest_start_mode(case, args)
    required_world_signal = format_case_text_template(case_required_world_signal(case, args), case)
    binding = fetch_live_quest_binding_with_seed_wait(
        args,
        case,
        mode,
        required_tag=case_required_quest_tag(case, args),
        required_world_signal=required_world_signal,
        required_target_name=getattr(args, "require_live_quest_target", ""),
        required_template=getattr(args, "require_live_quest_template", ""),
    )
    if binding is None:
        raise RuntimeError(f"no live dynamic quest found for {case.realm} mode={mode}")

    if mode == "npc" and binding.start_position is None:
        position = fetch_start_npc_position(args, binding.start_npc_internal_id)
        if position is None:
            raise RuntimeError(
                f"no live start npc position found for {case.realm} npc {binding.seed_npc!r} "
                f"internal_id={binding.start_npc_internal_id!r}"
            )
        binding = replace(binding, start_position=position)

    bound_case, start_position = bind_case_to_live_quest(
        case,
        binding,
        preserve_overlevel=(
            should_preserve_live_quest_overlevel(mode, args)
            or live_quest_binding_allows_overlevel(binding)
        ),
    )

    if case_followup_growth_target(case, args):
        try:
            target = extract_live_mob_growth_target(
                fetch_mob_growth_summary(args, world_signal_region(required_world_signal)),
                required_world_signal,
                max_preferred_level=max(1, int(bound_case.player_level or 1)),
                reference_position=bound_case.followup_reference or bound_case.return_home,
                max_reference_distance=getattr(args, "dynamic_quest_followup_max_reference_distance", 0),
                cluster_radius=getattr(args, "dynamic_quest_followup_cluster_radius", 0),
                max_cluster_neighbors=getattr(args, "dynamic_quest_followup_max_cluster_neighbors", -1),
                alias_radius=getattr(args, "dynamic_quest_followup_alias_radius", DEFAULT_MOB_GROWTH_FOLLOWUP_ALIAS_RADIUS),
                max_aliases=getattr(args, "dynamic_quest_followup_max_aliases", DEFAULT_MOB_GROWTH_FOLLOWUP_MAX_ALIASES),
            )
        except Exception:  # noqa: BLE001 - summary API is optional for live quest bound fallback.
            target = None
        target = target or live_mob_growth_target_from_binding(binding)
        if target is None:
            raise RuntimeError(
                f"no live mob-growth followup target found for {case.realm} "
                f"signal={required_world_signal!r}"
            )
        bound_case = bind_case_to_mob_growth_followup(bound_case, target)

    return bound_case, start_position


def resolve_case_start_position(case: QuestCase, args: argparse.Namespace) -> StartPosition | None:
    if case_quest_start_mode(case, args) != "autoaccept" or not getattr(args, "live_quest_start_position", True):
        return None

    _, position = resolve_live_case(case, args)
    if position is None:
        raise RuntimeError(f"no live start objective found for {case.realm} target {case.target!r}")
    return position


def should_resolve_live_case(args: argparse.Namespace) -> bool:
    if not getattr(args, "live_quest_start_position", True):
        return False

    if not bool(getattr(args, "dry_run", False)):
        return True

    return (
        getattr(args, "quest_start_mode", "npc") == "autoaccept"
        or getattr(args, "matrix", "") == "standard-smoke"
        or bool(text_value(getattr(args, "require_quest_tag", "")))
        or bool(text_value(getattr(args, "require_world_signal", "")))
        or bool(getattr(args, "dynamic_quest_followup_growth_target", False))
    )


def read_account_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_account_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def account_row_is_melee_smoke_preferred(row: dict[str, str]) -> bool:
    class_name = text_value(row.get("class_name") or row.get("class") or row.get("ClassName")).lower()
    return class_name in MELEE_SMOKE_CLASS_NAMES


def account_row_melee_smoke_priority(row: dict[str, str]) -> tuple[int, str]:
    class_name = text_value(row.get("class_name") or row.get("class") or row.get("ClassName")).lower()
    if class_name not in MELEE_SMOKE_CLASS_NAMES:
        return (100, class_name)
    return (MELEE_SMOKE_CLASS_PRIORITY.get(class_name, 20), class_name)


def order_account_rows_for_dynamic_quest_smoke(
    rows: list[dict[str, str]],
    args: argparse.Namespace,
    *,
    live_quest_filter_active: bool,
) -> list[dict[str, str]]:
    if not live_quest_filter_active or not bool(getattr(args, "prefer_melee_smoke_accounts", True)):
        return rows

    preferred = [row for row in rows if account_row_is_melee_smoke_preferred(row)]
    preferred.sort(key=account_row_melee_smoke_priority)
    fallback = [row for row in rows if not account_row_is_melee_smoke_preferred(row)]
    return preferred + fallback


def account_rows_have_class_data(rows: list[dict[str, str]]) -> bool:
    return any(
        text_value(row.get("class_name") or row.get("class") or row.get("ClassName"))
        for row in rows
    )


def enrich_account_rows_with_db_class_data(
    rows: list[dict[str, str]],
    args: argparse.Namespace,
) -> list[dict[str, str]]:
    usernames = sorted({text_value(row.get("username")) for row in rows if text_value(row.get("username"))})
    if not usernames:
        return rows

    try:
        provision_module = load_provision_module()
        db_args = build_db_args(args, provision_module)
        if not provision_module.mysql_bin_available(db_args.mysql_bin):
            return rows

        account_list = ", ".join(sql_quote(username) for username in usernames)
        sql = (
            "SELECT AccountName, Class, Level, SerializedSpecs "
            "FROM DOLCharacters "
            f"WHERE AccountName IN ({account_list}) "
            "ORDER BY AccountName, Level DESC;"
        )
        db_rows = provision_module.parse_mysql_rows(provision_module.run_mysql(db_args, sql))
    except Exception:
        return rows

    by_account: dict[str, dict[str, str]] = {}
    for db_row in db_rows:
        account_name = text_value(db_row.get("AccountName")).lower()
        if not account_name or account_name in by_account:
            continue
        by_account[account_name] = db_row

    enriched: list[dict[str, str]] = []
    for row in rows:
        updated = dict(row)
        account_name = text_value(row.get("username")).lower()
        db_row = by_account.get(account_name)
        class_id = int_value(db_row.get("Class")) if db_row else 0
        class_name = CLASS_ID_TO_NAME.get(class_id, "")
        if class_id:
            updated["class_id"] = str(class_id)
            updated["class_name"] = class_name
        specs = text_value(db_row.get("SerializedSpecs")) if db_row else ""
        if specs:
            updated["specs"] = specs
        enriched.append(updated)

    return enriched


def format_case_text_template(value: str, case: QuestCase) -> str:
    text = text_value(value)
    if not text:
        return ""

    try:
        return text.format(
            key=case.key,
            realm=case.realm,
            region=case.region,
            party_size=case.party_size,
        )
    except (KeyError, IndexError, ValueError):
        return text


def case_accounts_csv(case: QuestCase, args: argparse.Namespace) -> Path:
    if bool(getattr(args, "skip_completed_dynamic_quest_accounts", True)) and bool(text_value(getattr(case, "quest_id", ""))):
        return case.output_dir / f"accounts-selected-p{case.party_size}.csv"

    if max(0, int(getattr(args, "account_offset", 0) or 0)) <= 0:
        return case.accounts_csv

    return case.output_dir / f"accounts-offset-{int(args.account_offset)}-p{case.party_size}.csv"


def prepare_case_accounts_csv(case: QuestCase, args: argparse.Namespace, quest_id: str = "") -> Path:
    account_offset = max(0, int(getattr(args, "account_offset", 0) or 0))
    skip_completed = bool(getattr(args, "skip_completed_dynamic_quest_accounts", True)) and bool(text_value(quest_id))
    skip_any_active = bool(getattr(args, "skip_active_dynamic_quest_accounts", True)) and bool(text_value(quest_id))

    fieldnames, rows = read_account_csv(case.accounts_csv)
    rows = enrich_account_rows_with_db_class_data(rows, args)
    for extra_field in ("class_id", "class_name", "specs"):
        if any(text_value(row.get(extra_field)) for row in rows) and extra_field not in fieldnames:
            fieldnames.append(extra_field)
    rows, skipped_missing = filter_rows_with_existing_world_characters(rows, args)
    candidate_rows = []
    skipped_completed = []
    skipped_active = []
    for row in rows[account_offset:]:
        username = text_value(row.get("username"))
        if not username:
            continue

        if skip_any_active and account_has_any_active_dynamic_quest(args, username):
            skipped_active.append(username)
            continue

        if skip_completed and account_has_completed_or_active_dynamic_quest(args, username, quest_id):
            skipped_completed.append(username)
            continue

        candidate_rows.append(row)

    live_smoke_melee_required = (
        skip_completed
        and bool(getattr(args, "prefer_melee_smoke_accounts", True))
        and bool(getattr(args, "require_melee_smoke_accounts", True))
        and account_rows_have_class_data(rows)
    )
    if live_smoke_melee_required:
        preferred_candidate_count = sum(1 for row in candidate_rows if account_row_is_melee_smoke_preferred(row))
        if preferred_candidate_count < case.party_size:
            skipped_names = skipped_completed + skipped_active
            skipped_note = f"; skipped completed/active accounts: {', '.join(skipped_names)}" if skipped_names else ""
            raise RuntimeError(
                f"not enough melee smoke account rows after offset {account_offset}: "
                f"{case.accounts_csv} has {preferred_candidate_count}/{case.party_size}{skipped_note}"
            )

    selected_rows = order_account_rows_for_dynamic_quest_smoke(
        candidate_rows,
        args,
        live_quest_filter_active=skip_completed,
    )[: case.party_size]

    if len(selected_rows) < case.party_size:
        skipped_names = skipped_completed + skipped_active
        skipped_note = f"; skipped completed/active accounts: {', '.join(skipped_names)}" if skipped_names else ""
        raise RuntimeError(
            f"not enough account rows after offset {account_offset}: "
            f"{case.accounts_csv} has {len(selected_rows)}/{case.party_size}{skipped_note}"
        )

    case.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = case.output_dir / f"accounts-selected-p{case.party_size}.csv"
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(selected_rows)
    skipped_names = skipped_completed + skipped_active
    if skipped_names:
        (case.output_dir / "accounts-skipped-completed.txt").write_text(
            "\n".join(skipped_names) + "\n",
            encoding="utf-8",
        )
    if skipped_missing:
        (case.output_dir / "accounts-skipped-missing.txt").write_text(
            "\n".join(skipped_missing) + "\n",
            encoding="utf-8",
        )
    return output_path


def load_provision_module():
    module_path = Path(__file__).with_name("provision-dummy-accounts.py")
    spec = importlib.util.spec_from_file_location("provision_dummy_accounts_for_dynamic_quest_matrix", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_db_args(args: argparse.Namespace, provision_module) -> SimpleNamespace:
    mysql_bin_value = args.mysql_bin
    if mysql_bin_value and not provision_module.mysql_bin_available(mysql_bin_value):
        mysql_bin_value = None
    mysql_bin = provision_module.resolve_mysql_bin(mysql_bin_value)
    db_password = args.db_password or provision_module.read_serverconfig_password()
    return SimpleNamespace(
        mysql_bin=mysql_bin,
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=db_password,
    )


def reset_case_start_positions(
    case: QuestCase,
    args: argparse.Namespace,
    start_position: StartPosition | None = None,
) -> None:
    accounts_csv = case_accounts_csv(case, args)
    account_rows = read_account_rows(accounts_csv if accounts_csv.exists() else case.accounts_csv)
    using_prepared_accounts = accounts_csv.exists() and (
        accounts_csv != case.accounts_csv
        or case.accounts_csv.parent == case.output_dir
    )
    account_offset = 0 if using_prepared_accounts else args.account_offset
    if start_position is None:
        start_position = resolve_case_start_position(case, args)
    sql = build_start_position_update_sql(
        case,
        account_rows,
        args.start_position_step,
        account_offset,
        start_position,
        player_level=case.player_level,
    )
    if not sql:
        raise RuntimeError(f"no account rows available for start-position reset: {case.accounts_csv}")

    case.output_dir.mkdir(parents=True, exist_ok=True)
    (case.output_dir / "start-position-reset.sql").write_text(sql + "\n", encoding="utf-8")

    provision_module = load_provision_module()
    db_args = build_db_args(args, provision_module)
    if not provision_module.mysql_bin_available(db_args.mysql_bin):
        raise RuntimeError(f"mysql client not found: {db_args.mysql_bin}")

    provision_module.run_mysql(db_args, sql)


def to_int(value: object) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def to_float(value: object) -> float:
    try:
        return float(str(value or "0"))
    except ValueError:
        return 0.0


def truthy(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "ok"}


SETUP_FAILURE_ACTIONS = {
    "action_dynamic_quest_progress_api_error",
    "action_dynamic_quest_final_progress_api_error",
    "action_startup_service_progress_wait_api_error",
    "action_startup_service_progress_wait_timeout",
    "action_startup_service_progress_timeout_hard_fail",
    "action_startup_service_progress_timeout_exit",
    "action_required_target_api_error",
}
SETUP_FAILURE_ERROR_FRAGMENTS = (
    "playernotfound",
    "http error 404",
    "connection aborted",
    "connection reset",
    "forcibly closed",
    "winerror 10053",
    "mysql client not found",
    "access denied for user",
)

DUMMY_DIFFICULTY_PRESSURE_ACTIONS = (
    "action_attack_on",
    "action_combat_damage_done",
    "action_combat_damage_taken",
    "action_incoming_attack_msg",
    "action_flee_start",
    "action_flee_home_overrun",
    "action_safe_exit_hold",
    "action_critical_health_drop_aggro",
    "action_low_health_rest",
    "action_low_health_rest_extend",
    "action_behavior_state_DropAggroAndRecover",
    "action_drop_aggro_flee_start",
)

INITIAL_TIMELINE_OBSERVATION_GAP_TOKENS = {
    "quest_accepted",
    "presentation:onaccept",
    "presentation:onexplore",
}


def metric_row_has_setup_failure(row: dict[str, object]) -> bool:
    if metric_row_has_setup_failure_action(row):
        return True

    error = text_value(row.get("error")).lower()
    return any(fragment in error for fragment in SETUP_FAILURE_ERROR_FRAGMENTS)


def metric_row_has_setup_failure_action(row: dict[str, object]) -> bool:
    return any(to_int(row.get(action)) > 0 for action in SETUP_FAILURE_ACTIONS)


def case_has_setup_failure(case_dir: Path) -> bool:
    metrics_path = case_dir / "metrics.csv"
    if not metrics_path.exists():
        return False

    with metrics_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    return any(metric_row_has_setup_failure(row) for row in rows)


def case_has_setup_failure_action(case_dir: Path) -> bool:
    metrics_path = case_dir / "metrics.csv"
    if not metrics_path.exists():
        return False

    with metrics_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    return any(metric_row_has_setup_failure_action(row) for row in rows)


def metric_row_has_dummy_difficulty_pressure(row: dict[str, object]) -> bool:
    if any(to_int(row.get(action)) > 0 for action in DUMMY_DIFFICULTY_PRESSURE_ACTIONS):
        return True

    error = text_value(row.get("error")).lower()
    return "critical_health" in error or "low health" in error or "drop aggro" in error


def case_has_dummy_difficulty_pressure(case_dir: Path) -> bool:
    metrics_path = case_dir / "metrics.csv"
    if not metrics_path.exists():
        return False

    with metrics_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    return any(metric_row_has_dummy_difficulty_pressure(row) for row in rows)


def summary_has_complete_objective_closure(summary: CaseSummary) -> bool:
    return (
        summary.players > 0
        and summary.completed >= summary.players
        and summary.reward_observed >= summary.players
        and summary.target_removed >= summary.players
        and summary.player_deaths <= 0
    )


def case_has_only_initial_timeline_observation_gap(case_dir: Path) -> bool:
    metrics_path = case_dir / "metrics.csv"
    if not metrics_path.exists():
        return False

    observed_gap = False
    with metrics_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if truthy(row.get("ok")):
                continue

            error = text_value(row.get("error")).lower()
            prefix = "dynamic quest timeline check failed:"
            if not error.startswith(prefix):
                return False

            missing = {
                token.strip()
                for token in error[len(prefix):].split(",")
                if token.strip()
            }
            if not missing or not missing.issubset(INITIAL_TIMELINE_OBSERVATION_GAP_TOKENS):
                return False
            observed_gap = True

    return observed_gap


def min_action_scene_cohesion_from_args(args: argparse.Namespace | None) -> int:
    if args is None:
        return 70
    return max(0, min(100, int(getattr(args, "dynamic_quest_min_action_scene_cohesion", 70) or 0)))


def min_cinematic_catalog_role_variety_from_args(args: argparse.Namespace | None) -> int:
    if args is None:
        return 2
    return max(0, int(getattr(args, "dynamic_quest_min_cinematic_catalog_role_variety", 2) or 0))


def min_cinematic_model_role_fit_from_args(args: argparse.Namespace | None) -> int:
    if args is None:
        return 70
    return max(0, min(100, int(getattr(args, "dynamic_quest_min_cinematic_model_role_fit", 70) or 0)))


def summary_has_cinematic_scene_signal(summary: CaseSummary) -> bool:
    if summary.players <= 0 or summary.completed <= 0:
        return False
    return (
        summary.scene_director_beat >= max(3, summary.players)
        or summary.cinematic_action >= max(3, summary.players)
    )


def summary_fails_action_scene_cohesion(summary: CaseSummary, minimum_score: int = 70) -> bool:
    minimum_score = max(0, min(100, int(minimum_score)))
    if minimum_score <= 0 or not summary_has_cinematic_scene_signal(summary):
        return False
    return 0 <= summary.action_scene_cohesion_score < minimum_score


def summary_fails_cinematic_catalog_role_variety(summary: CaseSummary, minimum_variety: int = 2) -> bool:
    minimum_variety = max(0, int(minimum_variety))
    if minimum_variety <= 0 or not summary_has_cinematic_scene_signal(summary):
        return False
    return summary.cinematic_catalog_role_variety < minimum_variety


def summary_fails_cinematic_model_role_fit(summary: CaseSummary, minimum_score: int = 70) -> bool:
    minimum_score = max(0, min(100, int(minimum_score)))
    if minimum_score <= 0 or not summary_has_cinematic_scene_signal(summary):
        return False
    return 0 <= summary.cinematic_model_role_fit_score < minimum_score


def summary_fails_cinematic_role_quality(
    summary: CaseSummary,
    minimum_catalog_role_variety: int = 2,
    minimum_model_role_fit: int = 70,
) -> bool:
    return (
        summary_fails_cinematic_catalog_role_variety(summary, minimum_catalog_role_variety)
        or summary_fails_cinematic_model_role_fit(summary, minimum_model_role_fit)
    )


def summary_fails_cinematic_actor_spawn_quality(summary: CaseSummary) -> bool:
    severe_spawn_shortfall = (
        summary.cinematic_actor_instances > 0
        and summary.cinematic_actor_spawn_summary > 0
        and summary.cinematic_actor_spawned_total < int(summary.cinematic_actor_instances * 0.9)
    )
    return (
        summary.cinematic_actor_spawn_failed > 0
        or (
            summary.cinematic_actor_spawned_total > 0
            and summary.cinematic_actor_cleanup_scheduled < summary.cinematic_actor_spawned_total
        )
        or severe_spawn_shortfall
        or (
            summary.cinematic_actor_spawned_total > 0
            and summary.cinematic_actor_motion_summary <= 0
        )
        or (
            summary.cinematic_actor_motion_summary > 0
            and summary.cinematic_actor_motion_commands < summary.cinematic_actor_spawned_total
        )
        or (
            summary.cinematic_actor_motion_summary > 0
            and summary.cinematic_actor_motion_spawned_total > 0
            and summary.cinematic_actor_motion_spawned_total < summary.cinematic_actor_spawned_total
        )
        or (
            summary.cinematic_actor_spawned_total > 0
            and summary.cinematic_interaction_scene > 0
            and summary.cinematic_actor_engagement_summary <= 0
        )
        or (
            summary.cinematic_actor_spawned_total > 0
            and summary.cinematic_interaction_scene > 0
            and summary.cinematic_actor_engagement_summary > 0
            and summary.cinematic_actor_engagement_pairs <= 0
        )
        or (
            summary.cinematic_interaction_scene > 0
            and summary.scene_actor_exchange <= 0
        )
        or (
            summary.scene_actor_exchange > 0
            and summary.scene_exchange_outcome <= 0
        )
    )


def effective_case_passed(
    summary: CaseSummary,
    minimum_action_scene_cohesion: int = 70,
    minimum_catalog_role_variety: int = 2,
    minimum_model_role_fit: int = 70,
    case_dir: Path | None = None,
) -> bool:
    runtime_passed = bool(summary.passed)
    if (
        not runtime_passed
        and case_dir is not None
        and summary_has_complete_objective_closure(summary)
        and case_has_only_initial_timeline_observation_gap(case_dir)
    ):
        runtime_passed = True

    return (
        runtime_passed
        and not summary_fails_action_scene_cohesion(summary, minimum_action_scene_cohesion)
        and not summary_fails_cinematic_role_quality(
            summary,
            minimum_catalog_role_variety=minimum_catalog_role_variety,
            minimum_model_role_fit=minimum_model_role_fit,
        )
        and not summary_fails_cinematic_actor_spawn_quality(summary)
    )


def classify_case_failure(
    summary: CaseSummary,
    case_dir: Path,
    *,
    minimum_action_scene_cohesion: int = 70,
    minimum_catalog_role_variety: int = 2,
    minimum_model_role_fit: int = 70,
) -> str:
    initial_timeline_observation_gap_passed = (
        summary_has_complete_objective_closure(summary)
        and case_has_only_initial_timeline_observation_gap(case_dir)
    )
    if summary.passed or initial_timeline_observation_gap_passed:
        return "quest_quality" if (
            summary_fails_action_scene_cohesion(summary, minimum_action_scene_cohesion)
            or summary_fails_cinematic_role_quality(
                summary,
                minimum_catalog_role_variety=minimum_catalog_role_variety,
                minimum_model_role_fit=minimum_model_role_fit,
            )
            or summary_fails_cinematic_actor_spawn_quality(summary)
        ) else "passed"

    if summary.players <= 0 or case_has_setup_failure_action(case_dir):
        return "infrastructure"

    quest_signal = summary_has_observable_runtime_signal(summary)

    if summary.player_deaths > 0 and summary.completed < summary.players:
        return "dummy_difficulty"

    if summary.completed < summary.players and case_has_dummy_difficulty_pressure(case_dir):
        return "dummy_difficulty"

    if case_has_setup_failure(case_dir):
        return "infrastructure"

    if summary.ok_players < summary.players and not quest_signal:
        return "dummy_runtime"

    if (
        summary.reward_observed < summary.completed
        and summary.target_removed <= 0
        and case_has_dummy_difficulty_pressure(case_dir)
    ):
        return "dummy_difficulty"

    if summary.completed < summary.players or summary.reward_observed < summary.completed:
        return "quest_runtime"

    if summary.player_deaths > 0:
        return "dummy_difficulty"

    if summary.ok_players < summary.players:
        return "quest_runtime"

    return "quest_quality"


def summary_has_observable_runtime_signal(summary: CaseSummary) -> bool:
    return (
        summary.reward_observed > 0
        or summary.choice_selected > 0
        or summary.world_signal > 0
        or summary.presentation_beat > 0
        or summary.narrative_scene > 0
        or summary.cinematic_action > 0
        or summary.scene_director_beat > 0
        or summary.scene_beat_outcome > 0
        or summary.scene_world_signal > 0
        or summary.world_memory_marked > 0
        or summary.cinematic_cleanup > 0
    )


def row_has_dynamic_quest_completion(row: dict[str, object]) -> bool:
    if to_int(row.get("action_dynamic_quest_final_never_active")) > 0:
        return False

    return (
        to_int(row.get("action_dynamic_quest_complete_verified")) > 0
        or to_int(row.get("action_dynamic_quest_final_inactive")) > 0
    )


def row_has_dynamic_quest_expected_active_node(row: dict[str, object]) -> bool:
    if to_int(row.get("action_dynamic_quest_final_never_active")) > 0:
        return False

    return (
        to_int(row.get("action_dynamic_quest_expected_active_node_verified")) > 0
        or to_int(row.get("action_dynamic_quest_final_expected_active_node")) > 0
    )


def row_target_removed_count(row: dict[str, object]) -> int:
    target_removed = to_int(row.get("target_removed"))
    pending_confirmation = to_int(row.get("action_target_removed_pending_confirmation"))
    confirmed_completion = (
        to_int(row.get("action_required_target_complete_exit")) > 0
        or to_int(row.get("action_dynamic_quest_complete_verified")) > 0
        or to_int(row.get("action_dynamic_quest_reward_observed")) > 0
        or row_has_dynamic_quest_completion(row)
    )
    if target_removed <= 0 and pending_confirmation > 0 and confirmed_completion:
        return pending_confirmation
    return target_removed


def calculate_case_evaluation_score(summary: CaseSummary, *, require_followup_hunt: bool = False) -> int:
    if summary.players <= 0:
        return 0

    return max(0, min(100, int(summary.skyrim_grade_score)))


def calculate_dummy_operational_evaluation(
    summary: CaseSummary,
    case: QuestCase | None = None,
    *,
    failure_category: str = "",
) -> dict[str, object]:
    if summary.players <= 0:
        return {
            "totalScore": 0,
            "grade": "discard",
            "passed": False,
            "feasibilityScore": 0,
            "difficultyScore": 0,
            "rewardBalanceScore": 0,
            "routeScore": 0,
            "varietyScore": 0,
            "loreScore": 0,
            "exploitPenalty": 0,
            "failReasons": ["no dummy metrics were produced"],
            "warnings": [],
            "suggestedFixes": ["더미 실행 로그가 생성되는지 먼저 확인하기"],
        }

    fail_reasons: list[str] = []
    warnings: list[str] = []
    suggested_fixes: list[str] = []
    quest_signal = summary_has_observable_runtime_signal(summary)

    if not quest_signal:
        fail_reasons.append("quest produced no observable runtime signal")
        suggested_fixes.append("퀘스트 수락, node advance, timeline event가 발생하는지 확인하기")

    feasibility = 100
    if summary.completed < summary.players:
        feasibility -= 25
        fail_reasons.append("quest completion was not observed for every player")
        warnings.append("dummy did not observe completion for every player")
        suggested_fixes.append("완료 조건이 서버 timeline/progress로 확인 가능한지 점검하기")
    if summary.ok_players < summary.players:
        feasibility -= 10
        warnings.append("not every dummy ended with ok status")

    difficulty = 100
    if summary.player_deaths > 0:
        difficulty -= 10
        if summary.completed < summary.players:
            fail_reasons.append("dummy died before quest completion")
        warnings.append("dummy death observed; kept out of story score and treated as difficulty signal only")
        suggested_fixes.append("난이도 판정은 Average/LowSpec 더미 레벨과 목표 레벨을 분리해서 재검증하기")
    if failure_category == "dummy_difficulty" and summary.completed < summary.players:
        difficulty -= 35
        warnings.append("dummy difficulty pressure prevented quest completion")
        suggested_fixes.append("목표 몹을 더 낮은 체력/공격력의 spawn cluster로 바꾸거나 group recommended로 분류하기")
        if summary.target_removed <= 0:
            suggested_fixes.append("저스펙 더미가 목표 처치에 실패했으므로 target level뿐 아니라 실제 전투 로그 기반 난이도를 반영하기")

    reward_balance = 100
    if summary.completed > 0 and summary.reward_observed <= 0:
        reward_balance -= 20
        warnings.append("completion observed without reward observation")
        suggested_fixes.append("quest_rewarded timeline 또는 보상 지급 로그를 확인하기")

    route = 100
    if summary.elapsed_seconds > 0 and summary.elapsed_seconds > 900:
        route -= 20
        warnings.append("dummy run took a long time")
        suggested_fixes.append("시작 지점, 목표 위치, 완료 NPC 동선을 줄이기")

    variety = 100
    branch_choice_expected = quest_case_expects_branch_choice(case)
    world_signal_expected = quest_case_expects_world_signal(case)
    if summary.choice_selected <= 0 and summary.world_signal <= 0 and summary.cinematic_action <= 0:
        variety -= 25
        warnings.append("limited quest variety observed")
    if branch_choice_expected and summary.completed > 0 and summary.choice_selected <= 0:
        variety -= 20
        warnings.append("branch quest completed without an observed player choice")
        suggested_fixes.append("branch:* 템플릿은 choice_selected timeline과 OnChoiceSelected 세트피스가 실제 더미 진행에서 관측되게 만들기")
    if summary.choice_selected > 0 and summary.choice_outcome_scene <= 0:
        variety -= 10
        warnings.append("choice was selected without an outcome set-piece")
        suggested_fixes.append("선택 직후 choice_outcome_scene을 기록하고 선택 결과별 actor 세트피스를 재생하기")
    if summary.choice_selected > 0 and summary.choice_outcome_scene > 0 and summary.choice_consequence <= 0:
        variety -= 8
        warnings.append("choice outcome was observed without a consequence marker")
        suggested_fixes.append("선택 직후 choice_consequence timeline을 기록해 선택 결과가 후속 서사에 남는지 확인하기")
    if world_signal_expected and summary.completed > 0 and summary.world_signal <= 0 and summary.followup_hunt_start <= 0:
        variety -= 20
        warnings.append("world-signal branch completed without an observed world signal")
        suggested_fixes.append("world-signal:* 템플릿은 OnWorldSignal 소비와 world_signal_scene_shift가 실제 timeline에 남게 만들기")
    if 0 < summary.cinematic_density_score < 70:
        variety -= 15
        warnings.append("cinematic density is below Skyrim-grade threshold")
        suggested_fixes.append("narrative scene, presentation beat, actor action, world impact를 더 촘촘히 배치하기")
    if (
        summary.completed > 0
        and summary.presentation_beat >= max(2, summary.players)
        and 0 <= summary.presentation_speaker_variety <= 1
    ):
        variety -= 15
        warnings.append("presentation speaker variety is low")
        suggested_fixes.append("presentation beat가 System 독백에 머무르지 않도록 StartNpc/Companion/TargetNpc 화자를 섞기")
    if (
        summary.completed > 0
        and summary.presentation_beat >= max(3, summary.players)
        and 0 <= summary.presentation_staged_beat <= 0
    ):
        variety -= 12
        warnings.append("presentation beats lack staged action metadata")
        suggested_fixes.append("presentation beat에 cinematicAction, sceneRole, formation, actorCount, delayMs를 넣어 대사와 액션 지시가 함께 관측되게 만들기")
    if summary.presentation_staged_beat >= max(3, summary.players) and 0 <= summary.presentation_staged_action_variety <= 1:
        variety -= 6
        warnings.append("presentation staged action variety is low")
        suggested_fixes.append("presentation beat의 cinematicAction이 한 종류에만 몰리지 않도록 매복/방어선/추격/대치/후퇴를 섞기")
    if summary.presentation_staged_beat >= max(3, summary.players) and 0 <= summary.presentation_staged_role_variety <= 1:
        variety -= 6
        warnings.append("presentation staged scene role variety is low")
        suggested_fixes.append("presentation beat의 sceneRole을 witness, ambush, counterline, fallout처럼 장면 기능별로 나누기")
    if summary.completed > 0 and 0 < summary.story_continuity_score < 70:
        variety -= 15
        warnings.append("story continuity is below Skyrim-grade threshold")
        suggested_fixes.append("선택 결과, 장면 교환 결과, 월드 신호 변화, 완료 여파가 하나의 후속 흐름으로 이어지게 만들기")
    if summary.completed > 0 and 0 < summary.story_archetype_score < 70:
        variety -= 15
        warnings.append("story archetype expression is below Skyrim-grade threshold")
        suggested_fixes.append("story-archetype, story-arc 태그와 아키타입별 장면 제목/선택 대사/후일담이 실제 timeline에 드러나게 만들기")
    if summary.scene_director_beat >= max(3, summary.players) and 0 <= summary.cinematic_marker_scene <= 0:
        variety -= 12
        warnings.append("cinematic marker scenes are missing despite staged scene beats")
        suggested_fixes.append("탐색/처치/선택/완료 장면에 단서, 성물, 전투 흔적, 구조물 표식 같은 marker action을 남기기")
    if summary.cinematic_marker_scene >= 3 and summary.cinematic_marker_variety <= 1:
        variety -= 8
        warnings.append("cinematic marker variety is low")
        suggested_fixes.append("Quest trace, Threat sign, Decision point, Relic sign 같은 서로 다른 marker를 섞기")
    if summary.scene_director_beat >= max(3, summary.players) and 0 <= summary.cinematic_phase_coverage < 3:
        variety -= 12
        warnings.append("cinematic phase coverage is incomplete")
        suggested_fixes.append("연출을 discovery, battle, aftermath 세 단계에 모두 배치해 도입-교전-여파가 이어지게 만들기")
    if summary.scene_director_beat >= max(3, summary.players) and 0 <= summary.cinematic_story_chain < 3:
        variety -= 12
        warnings.append("cinematic story chain order is incomplete")
        suggested_fixes.append("timeline에서 discovery 연출 뒤 battle 세트피스가 오고, 그 뒤 aftermath/complete 연출이 이어지게 만들기")
    if summary.scene_director_beat >= max(3, summary.players) and 0 <= summary.cinematic_setpiece_phase_coverage < 2:
        variety -= 10
        warnings.append("cinematic set-piece phase coverage is thin")
        suggested_fixes.append("최소 탐색과 교전 단계에는 scene_beat 기반 actor 세트피스를 각각 배치하기")
    if summary.cinematic_marker_scene >= 3 and 0 <= summary.cinematic_marker_phase_coverage < 2:
        variety -= 8
        warnings.append("cinematic marker phase coverage is thin")
        suggested_fixes.append("단서/전투 흔적 marker가 한 단계에만 몰리지 않도록 탐색과 전투 현장에 나누어 배치하기")
    if summary.players >= 2 and summary.completed >= summary.players:
        minimum_narrative_coverage = summary.players * 2
        minimum_presentation_coverage = summary.players * 3
        minimum_cinematic_coverage = summary.players * 3
        narrative_coverage_thin = (
            0 <= summary.min_narrative_scene_per_player < 2
            or (summary.min_narrative_scene_per_player < 0 and summary.narrative_scene < minimum_narrative_coverage)
        )
        presentation_coverage_thin = (
            0 <= summary.min_presentation_beat_per_player < 3
            or (summary.min_presentation_beat_per_player < 0 and summary.presentation_beat < minimum_presentation_coverage)
        )
        cinematic_coverage_thin = (
            0 <= summary.min_cinematic_action_per_player < 3
            or (summary.min_cinematic_action_per_player < 0 and summary.cinematic_action < minimum_cinematic_coverage)
        )
        if narrative_coverage_thin:
            variety -= 8
            warnings.append("party quest narrative coverage is thin per player")
            suggested_fixes.append("파티형 퀘스트는 각 플레이어가 최소 2개 이상의 narrative scene을 보도록 노드별 서사 beat를 보강하기")
        if presentation_coverage_thin:
            variety -= 8
            warnings.append("party quest presentation coverage is thin per player")
            suggested_fixes.append("파티형 퀘스트는 수락/탐색/처치/선택/완료 trigger별 presentation beat가 모든 더미에게 관측되게 만들기")
        if cinematic_coverage_thin:
            variety -= 8
            warnings.append("party quest cinematic coverage is thin per player")
            suggested_fixes.append("파티형 퀘스트는 actor action이 한 명에게만 몰리지 않도록 파티 인원수 기준 최소 연출 밀도를 맞추기")
    if summary.scene_director_beat >= max(3, summary.players) and summary.cinematic_variety <= 1:
        variety -= 10
        warnings.append("cinematic scene variety is low despite staged scene beats")
        suggested_fixes.append("매복, 목격자, 방어선, 대치, 후퇴 같은 서로 다른 cinematic action을 섞기")
    if summary.scene_director_beat >= max(3, summary.players) and summary.cinematic_motion_variety <= 1:
        variety -= 10
        warnings.append("cinematic motion variety is low despite staged scene beats")
        suggested_fixes.append("pincer, retreat, standoff, ritual-break 같은 서로 다른 motion profile을 섞기")
    if summary.scene_director_beat >= max(3, summary.players) and summary.cinematic_staggered_scene <= 0:
        variety -= 10
        warnings.append("staged scene beats did not use actor stagger timing")
        suggested_fixes.append("대규모 actor 연출은 stagger delay를 사용해 wave처럼 순차 반응하게 만들기")
    if summary.scene_director_beat >= max(3, summary.players) and summary.cinematic_objective_focal_scene <= 0:
        variety -= 10
        warnings.append("staged scene beats did not use an objective focal point")
        suggested_fixes.append("단서/성물/위협 표식 같은 objective focal point 중심으로 actor를 배치하기")
    if summary.scene_director_beat >= max(3, summary.players) and summary.cinematic_actor_role_variety <= 1:
        variety -= 10
        warnings.append("staged scene beats did not use varied actor roles")
        suggested_fixes.append("공격대, 방어선, 의식 차단, 후퇴 정찰, 목격자 같은 actorRole을 섞기")
    if summary.scene_director_beat >= max(3, summary.players) and summary.cinematic_choreographed_scene <= 0:
        variety -= 10
        warnings.append("staged scene beats did not use multi-phase actor choreography")
        suggested_fixes.append("actorRole별 후속 emote/재배치 phase를 넣어 액션 시퀀스를 만들기")
    if summary.scene_director_beat >= max(3, summary.players) and summary.cinematic_interaction_scene <= 0:
        variety -= 10
        warnings.append("staged scene beats did not use actor interaction choreography")
        suggested_fixes.append("매복 충돌, 방어선 차단, 의식 차단, 추격, 대치 같은 interact 스타일을 넣기")
    if summary.scene_director_beat >= max(3, summary.players) and summary.cinematic_tactic_variety <= 1:
        variety -= 10
        warnings.append("staged scene beats did not use varied tactical roles")
        suggested_fixes.append("flank, screen, suppress, withdraw, pressure 같은 tactic 역할을 섞어 액션씬의 임무 차이를 만들기")
    if summary.completed > 0 and summary.world_impact_summary <= 0:
        variety -= 10
        warnings.append("completed quest did not leave a world impact summary")
        suggested_fixes.append("완료 시 world_impact_summary가 남도록 선택 결과 또는 지역 여파 기록을 보강하기")
    if summary.completed > 0 and summary.world_memory_marked <= 0:
        variety -= 10
        warnings.append("completed quest did not leave a world memory marker")
        suggested_fixes.append("완료 시 world_memory_marked timeline이 남아 후속 에피소드 prerequisite이 검증되게 만들기")
    if summary.cinematic_action > 0 and summary.scene_director_beat <= 0:
        warnings.append("cinematic actions were observed, but no staged scene director beat was detected")
        suggested_fixes.append("암살/목격자/매복/탈출 같은 순차 scene_beat 연출을 추가하기")
    if summary.scene_director_beat > 0 and summary.scene_beat_outcome <= 0:
        warnings.append("scene director beats were observed without scene beat outcome events")
        suggested_fixes.append("scene_beat 실행 결과가 timeline에 scene_beat_outcome으로 기록되는지 확인하기")
    if summary.cinematic_choreographed_scene > 0 and summary.scene_choreography_phase <= 0:
        variety -= 10
        warnings.append("multi-phase choreography was planned but no choreography phase wave was observed")
        suggested_fixes.append("scene_beat의 choreo phase가 scene_choreography_phase timeline으로 남는지 확인하기")
    if summary.cinematic_interaction_scene > 0 and summary.scene_actor_exchange <= 0:
        variety -= 10
        warnings.append("actor interaction choreography was planned but no actor exchange was observed")
        suggested_fixes.append("clash/block/interrupt/pursuit/standoff 연출이 scene_actor_exchange timeline으로 남는지 확인하기")
    if summary.scene_actor_exchange > 0 and summary.scene_exchange_outcome <= 0:
        variety -= 10
        warnings.append("actor exchange was observed without a scene exchange outcome")
        suggested_fixes.append("actor 교환 뒤 line_held, escape_cutoff, ritual_disrupted 같은 결과를 scene_exchange_outcome으로 남기기")
    if summary.scene_exchange_outcome > 0 and summary.scene_outcome_signal <= 0:
        variety -= 10
        warnings.append("scene exchange outcome was observed without an outcome world signal")
        suggested_fixes.append("scene_exchange_outcome 뒤에 scene:<outcome> 신호를 남겨 후속 분기가 재사용하게 만들기")
    if summary.scene_exchange_outcome > 0 and summary.scene_consequence <= 0:
        variety -= 10
        warnings.append("scene exchange outcome was observed without a scene consequence")
        suggested_fixes.append("scene_exchange_outcome 뒤에 scene_consequence를 남겨 장면 결과가 서사 여파로 이어지게 만들기")
    if summary.world_signal > 0 and summary.world_signal_scene_shift <= 0:
        variety -= 10
        warnings.append("world signal was consumed without a scene shift")
        suggested_fixes.append("OnWorldSignal 소비 시 world_signal_scene_shift를 남겨 후속 신호가 현장 변화로 보이게 만들기")
    if (
        summary.world_signal_scene_shift > 0
        and 0 <= summary.world_signal_scene_shift_detail < summary.world_signal_scene_shift
    ):
        variety -= 8
        warnings.append("world signal scene shift lacks phase/source/target detail")
        suggested_fixes.append("world_signal_scene_shift detail에 phase, source, target, region을 남겨 후속 장면 전환의 원인과 목적지를 추적 가능하게 만들기")
    if summary.world_signal_scene_shift >= 2 and 0 <= summary.world_signal_scene_shift_phase_variety <= 1:
        variety -= 6
        warnings.append("world signal scene shift phase variety is low")
        suggested_fixes.append("world_signal_scene_shift가 discovery/pursuit/blockade/aftermath 같은 서로 다른 phase로 분화되게 만들기")
    if summary.world_signal_scene_shift >= 2 and 0 <= summary.world_signal_scene_shift_source_variety <= 1:
        variety -= 4
        warnings.append("world signal scene shift source variety is low")
        suggested_fixes.append("장면 전환 source가 같은 신호 하나에만 몰리지 않도록 actor exchange, scene consequence, branch signal을 섞기")
    if summary.world_signal_scene_shift >= 2 and 0 <= summary.world_signal_scene_shift_target_variety <= 1:
        variety -= 4
        warnings.append("world signal scene shift target variety is low")
        suggested_fixes.append("장면 전환 target을 시작 NPC, 목표 지점, 결과 확인 지점으로 나누어 장면이 공간적으로 이동하게 만들기")
    if summary.cinematic_action > 0 and summary.cinematic_cleanup <= 0:
        warnings.append("cinematic actions were observed without cinematic cleanup events")
        suggested_fixes.append("임시 actor/marker 연출은 완료 또는 타이머 cleanup이 timeline에 기록되는지 확인하기")
    high_cinematic_density_needs_review = (
        summary.cinematic_cleanup <= 0
        or summary.cinematic_actor_peak > 100
        or (0 < summary.cinematic_actor_budget_score < 70)
    )
    if summary.players > 0 and summary.cinematic_action > summary.players * 80 and high_cinematic_density_needs_review:
        warnings.append("cinematic action density is very high; verify actor budget and cleanup")
        suggested_fixes.append("대규모 actor 연출은 cinematic-actors 태그와 cleanup 이벤트를 함께 확인하기")
    if summary.cinematic_actor_peak > 100:
        variety -= 15
        warnings.append("cinematic actor peak exceeded the 100 actor budget cap")
        suggested_fixes.append("cinematic-actors 태그 또는 서버 설정을 action당 최대 100명 이하로 제한하기")
    if summary.players > 0 and summary.cinematic_actor_instances >= summary.players * 80 and summary.cinematic_cleanup <= 0:
        variety -= 15
        warnings.append("large cinematic actor budget was observed without cleanup")
        suggested_fixes.append("대규모 actor 연출은 완료/타이머 cleanup timeline을 반드시 남기기")
    if summary.cinematic_actor_spawn_failed > 0:
        variety -= 20
        warnings.append("cinematic actor spawn failures were observed")
        suggested_fixes.append("actor spawn 위치, 모델, region, AddToWorld 실패 원인을 점검하기")
    if summary.cinematic_actor_spawned_total > 0 and summary.cinematic_actor_cleanup_scheduled < summary.cinematic_actor_spawned_total:
        variety -= 15
        warnings.append("not every spawned cinematic actor had cleanup scheduled")
        suggested_fixes.append("대규모 actor는 spawn 성공 수와 cleanup 예약 수가 일치하도록 보장하기")
    if (
        summary.cinematic_actor_instances > 0
        and summary.cinematic_actor_spawn_summary > 0
        and summary.cinematic_actor_spawned_total < summary.cinematic_actor_instances
    ):
        variety -= 10
        warnings.append("fewer cinematic actors spawned than were planned")
        suggested_fixes.append("planned actor count 대비 spawned count가 낮은 세트피스의 formation/anchor를 조정하기")
    if (
        summary.cinematic_actor_spawned_total > 0
        and summary.cinematic_actor_motion_summary <= 0
    ):
        variety -= 12
        warnings.append("spawned cinematic actors did not report motion choreography")
        suggested_fixes.append("대규모 actor 연출은 cinematic_actor_motion_summary로 이동 phase 예약 수를 남기기")
    if (
        summary.cinematic_actor_motion_summary > 0
        and summary.cinematic_actor_motion_commands < summary.cinematic_actor_spawned_total
    ):
        variety -= 8
        warnings.append("cinematic actor motion command density is low")
        suggested_fixes.append("actor당 최소 1개 이상의 접근/후퇴/대치 이동 phase가 예약되도록 motion profile을 조정하기")
    if (
        summary.cinematic_actor_spawned_total > 0
        and summary.cinematic_interaction_scene > 0
        and summary.cinematic_actor_engagement_summary <= 0
    ):
        variety -= 12
        warnings.append("spawned cinematic actors did not report tactical engagement pairs")
        suggested_fixes.append("대규모 actor 연출은 cinematic_actor_engagement_summary로 대치/충돌 pair 수를 남기기")
    if (
        summary.cinematic_actor_engagement_summary > 0
        and summary.cinematic_actor_engaged_total < cinematic_actor_engagement_expected_total(summary)
    ):
        variety -= 6
        warnings.append("cinematic actor engagement coverage is low")
        suggested_fixes.append("대규모 액션씬에서 spawn actor 대부분이 clash/block/pursuit/standoff pair에 포함되도록 조정하기")
    if 0 < summary.cinematic_actor_budget_score < 70:
        variety -= 10
        warnings.append("cinematic actor budget score is below operational threshold")
        suggested_fixes.append("actor peak, actor 누계, stagger/choreo, cleanup 균형을 맞추기")
    if (
        summary.scene_director_beat >= max(3, summary.players)
        and 0 < summary.action_scene_cohesion_score < 70
    ):
        variety -= 12
        warnings.append("action scene cohesion is below Skyrim-grade threshold")
        suggested_fixes.append("motion, tactic, actorRole, stagger, focal point, choreo/interact를 함께 섞어 실제 전투 장면처럼 보이게 만들기")

    lore = 100
    if case is not None and not text_value(getattr(case, "realm", "")):
        lore -= 20
        warnings.append("case has no realm metadata")

    exploit_penalty = 0
    if summary.completed > 0 and summary.reward_observed > 0 and 0 < summary.elapsed_seconds < 45:
        exploit_penalty += 10
        warnings.append("very short rewarded completion observed")
        suggested_fixes.append("반복 가능 퀘스트라면 보상 multiplier 또는 재수락 조건을 낮추기")
    if summary.target_removed <= 1 and summary.reward_observed > 0 and summary.elapsed_seconds > 0 and summary.elapsed_seconds < 60:
        exploit_penalty += 5

    feasibility = max(0, min(100, feasibility))
    difficulty = max(0, min(100, difficulty))
    reward_balance = max(0, min(100, reward_balance))
    route = max(0, min(100, route))
    variety = max(0, min(100, variety))
    lore = max(0, min(100, lore))
    total = round(
        feasibility * 0.35
        + difficulty * 0.30
        + reward_balance * 0.20
        + route * 0.10
        + ((variety + lore) / 2.0) * 0.05
    )
    total = max(0, min(100, int(total) - exploit_penalty))
    hard_filter_failed = bool(fail_reasons) or feasibility < 70 or reward_balance < 50 or exploit_penalty >= 25
    if hard_filter_failed:
        total = min(total, 39)
    passed = not hard_filter_failed
    if hard_filter_failed:
        grade = "discard"
    elif total >= 90:
        grade = "excellent"
    elif total >= 75:
        grade = "usable"
    elif total >= 60:
        grade = "conditional"
    elif total >= 40:
        grade = "needs-work"
    else:
        grade = "discard"

    return {
        "totalScore": total,
        "grade": grade,
        "passed": passed,
        "feasibilityScore": feasibility,
        "difficultyScore": difficulty,
        "rewardBalanceScore": reward_balance,
        "routeScore": route,
        "varietyScore": variety,
        "loreScore": lore,
        "exploitPenalty": exploit_penalty,
        "failReasons": fail_reasons,
        "warnings": warnings,
        "suggestedFixes": suggested_fixes,
    }


def calculate_skyrim_grade_score(
    summary: CaseSummary,
    *,
    require_followup_hunt: bool = False,
    require_branch_choice: bool = False,
    require_world_signal: bool = False,
) -> int:
    if summary.players <= 0:
        return 0

    score = 0
    if summary.narrative_scene > 0:
        score += 25
    if summary.presentation_beat > 0:
        score += 20
    if summary.presentation_staged_beat > 0:
        score += 4
    elif summary.presentation_beat >= max(3, summary.players) and summary.presentation_staged_beat >= 0:
        score -= 6
    if summary.presentation_speaker_variety >= 3:
        score += 5
    elif summary.presentation_speaker_variety >= 2:
        score += 3
    elif summary.presentation_speaker_variety >= 0 and summary.presentation_beat >= max(2, summary.players):
        score -= 8
    if summary.cinematic_action > 0:
        score += 20
    if summary.presentation_staged_action_variety >= 3:
        score += 3
    elif summary.presentation_staged_action_variety >= 2:
        score += 2
    if summary.presentation_staged_role_variety >= 3:
        score += 3
    elif summary.presentation_staged_role_variety >= 2:
        score += 2
    if summary.presentation_staged_formation_variety >= 2:
        score += 2
    if summary.presentation_staged_delayed_beat > 0:
        score += 2
    if summary.cinematic_variety >= 4:
        score += 7
    elif summary.cinematic_variety >= 2:
        score += 4
    if summary.cinematic_motion_variety >= 4:
        score += 5
    elif summary.cinematic_motion_variety >= 2:
        score += 3
    if summary.cinematic_staggered_scene > 0:
        score += 3
    if summary.cinematic_objective_focal_scene > 0:
        score += 3
    if summary.cinematic_marker_scene >= max(3, summary.players):
        score += 4
    elif summary.cinematic_marker_scene >= 0 and summary.scene_director_beat >= max(3, summary.players):
        score -= 6
    if summary.cinematic_marker_variety >= 3:
        score += 3
    elif summary.cinematic_marker_scene >= 3 and summary.cinematic_marker_variety <= 1:
        score -= 4
    if summary.cinematic_phase_coverage >= 3:
        score += 5
    elif 0 <= summary.cinematic_phase_coverage < 3 and summary.scene_director_beat >= max(3, summary.players):
        score -= 5
    if summary.cinematic_story_chain >= 3:
        score += 5
    elif 0 <= summary.cinematic_story_chain < 3 and summary.scene_director_beat >= max(3, summary.players):
        score -= 5
    if summary.cinematic_setpiece_phase_coverage >= 2:
        score += 3
    elif 0 <= summary.cinematic_setpiece_phase_coverage < 2 and summary.scene_director_beat >= max(3, summary.players):
        score -= 3
    if summary.cinematic_marker_phase_coverage >= 2:
        score += 2
    elif summary.cinematic_marker_scene >= 3 and 0 <= summary.cinematic_marker_phase_coverage < 2:
        score -= 2
    if summary.cinematic_actor_role_variety >= 4:
        score += 4
    elif summary.cinematic_actor_role_variety >= 2:
        score += 2
    if summary.cinematic_choreographed_scene > 0:
        score += 3
    if summary.cinematic_interaction_scene > 0:
        score += 3
    if summary.cinematic_tactic_variety >= 4:
        score += 4
    elif summary.cinematic_tactic_variety >= 2:
        score += 2
    if summary.cinematic_model_role_fit_score >= 80:
        score += 4
    elif summary.cinematic_model_role_fit_score >= 60:
        score += 2
    if summary.action_scene_cohesion_score >= 90:
        score += 5
    elif summary.action_scene_cohesion_score >= 70:
        score += 3
    elif summary.scene_director_beat >= max(3, summary.players) and 0 < summary.action_scene_cohesion_score < 70:
        score -= 8
    if summary.scene_director_beat > 0:
        score += 8
    if summary.scene_beat_outcome > 0:
        score += 4
    if summary.scene_choreography_phase > 0:
        score += 4
    if summary.scene_actor_exchange > 0:
        score += 4
    if summary.scene_exchange_outcome > 0:
        score += 4
    if summary.scene_outcome_signal > 0:
        score += 4
    if summary.scene_consequence > 0:
        score += 4
    if summary.scene_world_signal > 0:
        score += 3
    if summary.world_signal_scene_shift > 0:
        score += 4
    if summary.world_signal_scene_shift_detail >= summary.world_signal_scene_shift > 0:
        score += 3
    elif summary.world_signal_scene_shift > 0 and 0 <= summary.world_signal_scene_shift_detail < summary.world_signal_scene_shift:
        score -= 3
    if summary.world_signal_scene_shift_phase_variety >= 2:
        score += 2
    elif summary.world_signal_scene_shift >= 2 and 0 <= summary.world_signal_scene_shift_phase_variety <= 1:
        score -= 2
    if summary.cinematic_cleanup > 0:
        score += 3
    if summary.choice_selected > 0:
        score += 10
    elif require_branch_choice and summary.completed > 0:
        score -= 10
    if summary.choice_outcome_scene > 0:
        score += 4
    if summary.choice_consequence > 0:
        score += 3
    if summary.world_impact > 0:
        score += 10
    if summary.world_impact_summary > 0:
        score += 5
    if summary.world_memory_marked > 0:
        score += 3
    if summary.world_signal > 0 or summary.followup_hunt_start > 0:
        score += 5
    elif require_world_signal and summary.completed > 0:
        score -= 8
    if summary.story_archetype_score >= 90:
        score += 5
    elif 0 < summary.story_archetype_score < 70:
        score -= 5
    if summary.completed > 0 or summary.reward_observed > 0:
        score += 10
    if require_followup_hunt and summary.world_signal <= 0 and summary.followup_hunt_start <= 0:
        score -= 5
    if score > 0 and summary.choice_selected <= 0 and not require_branch_choice:
        score += 5
    if summary.players >= 2 and summary.completed >= summary.players:
        if 0 <= summary.min_narrative_scene_per_player < 2:
            score -= 12
        if 0 <= summary.min_presentation_beat_per_player < 3:
            score -= 12
        if 0 <= summary.min_cinematic_action_per_player < 3:
            score -= 12

    if summary.scene_director_beat >= max(3, summary.players) and 0 < summary.action_scene_cohesion_score < 70:
        score = min(score, 89)
    if summary.scene_director_beat >= max(3, summary.players):
        if summary.scene_beat_outcome <= 0:
            score = min(score, 89)
        if summary.cinematic_choreographed_scene > 0 and summary.scene_choreography_phase <= 0:
            score = min(score, 89)
        if summary.cinematic_interaction_scene > 0 and summary.scene_actor_exchange <= 0:
            score = min(score, 89)
        if summary.scene_actor_exchange > 0 and summary.scene_exchange_outcome <= 0:
            score = min(score, 89)
        if summary.scene_exchange_outcome > 0 and summary.scene_outcome_signal <= 0:
            score = min(score, 94)
        if summary.scene_exchange_outcome > 0 and summary.scene_consequence <= 0:
            score = min(score, 94)
    if summary.cinematic_actor_peak >= 80:
        if summary.cinematic_cleanup <= 0:
            score = min(score, 89)
        if summary.cinematic_actor_motion_summary <= 0:
            score = min(score, 89)
        if summary.cinematic_interaction_scene > 0 and summary.cinematic_actor_engagement_summary <= 0:
            score = min(score, 89)

    return max(0, min(100, score))


def calculate_cinematic_density_score(summary: CaseSummary) -> int:
    if summary.players <= 0:
        return 0

    score = 0
    narrative_per_player = summary.narrative_scene / max(1, summary.players)
    presentation_per_player = summary.presentation_beat / max(1, summary.players)
    cinematic_per_player = summary.cinematic_action / max(1, summary.players)

    if narrative_per_player >= 5:
        score += 25
    elif narrative_per_player >= 3:
        score += 22
    elif narrative_per_player > 0:
        score += 15

    if presentation_per_player >= 8:
        score += 25
    elif presentation_per_player >= 4:
        score += 22
    elif presentation_per_player > 0:
        score += 15
    if summary.presentation_staged_beat > 0:
        staged_per_player = summary.presentation_staged_beat / max(1, summary.players)
        if staged_per_player >= 4:
            score += 6
        elif staged_per_player >= 2:
            score += 4
        else:
            score += 2

    if cinematic_per_player >= 12:
        score += 30
    elif cinematic_per_player >= 6:
        score += 26
    elif cinematic_per_player >= 3:
        score += 22
    elif cinematic_per_player > 0:
        score += 15

    if summary.choice_selected > 0:
        score += 8
    if summary.choice_outcome_scene > 0:
        score += 4
    if summary.choice_consequence > 0:
        score += 3
    if summary.world_signal > 0 or summary.followup_hunt_start > 0:
        score += 5
    if summary.world_impact > 0:
        score += 8
    if summary.world_impact_summary > 0:
        score += 4
    if summary.world_memory_marked > 0:
        score += 3
    if summary.scene_director_beat > 0:
        score += 8
    if summary.scene_beat_outcome > 0:
        score += 4
    if summary.scene_choreography_phase > 0:
        score += 4
    if summary.scene_actor_exchange > 0:
        score += 4
    if summary.scene_exchange_outcome > 0:
        score += 4
    if summary.scene_outcome_signal > 0:
        score += 4
    if summary.scene_consequence > 0:
        score += 4
    if summary.scene_world_signal > 0:
        score += 3
    if summary.world_signal_scene_shift > 0:
        score += 4
    if summary.cinematic_cleanup > 0:
        score += 3
    if summary.cinematic_variety >= 4:
        score += 7
    elif summary.cinematic_variety >= 2:
        score += 4
    if summary.cinematic_motion_variety >= 4:
        score += 5
    elif summary.cinematic_motion_variety >= 2:
        score += 3
    if summary.cinematic_staggered_scene > 0:
        score += 3
    if summary.cinematic_objective_focal_scene > 0:
        score += 3
    if summary.cinematic_actor_role_variety >= 4:
        score += 4
    elif summary.cinematic_actor_role_variety >= 2:
        score += 2
    if summary.cinematic_choreographed_scene > 0:
        score += 3
    if summary.cinematic_interaction_scene > 0:
        score += 3
    if summary.cinematic_tactic_variety >= 4:
        score += 4
    elif summary.cinematic_tactic_variety >= 2:
        score += 2
    if summary.cinematic_model_role_fit_score >= 80:
        score += 4
    elif summary.cinematic_model_role_fit_score >= 60:
        score += 2
    if summary.completed > 0 or summary.reward_observed > 0:
        score += 5

    return max(0, min(100, int(score)))


def calculate_cinematic_actor_budget_score(summary: CaseSummary) -> int:
    if summary.cinematic_actor_instances <= 0 and summary.cinematic_actor_peak <= 0:
        return 0

    players = max(1, summary.players)
    score = 45
    if summary.cinematic_actor_peak > 100:
        score -= 40
    elif summary.cinematic_actor_peak >= 80:
        score += 25
    elif summary.cinematic_actor_peak >= 40:
        score += 18
    elif summary.cinematic_actor_peak >= 8:
        score += 10
    else:
        score += 5

    if summary.cinematic_actor_instances >= players * 100:
        score += 20
    elif summary.cinematic_actor_instances >= players * 40:
        score += 12
    else:
        score += 5

    if summary.cinematic_cleanup > 0:
        score += 15
    elif summary.cinematic_actor_peak >= 80 or summary.cinematic_actor_instances >= players * 80:
        score -= 25
    else:
        score -= 10

    if summary.cinematic_actor_spawn_summary > 0:
        if summary.cinematic_actor_spawn_failed > 0:
            score -= min(35, 10 + summary.cinematic_actor_spawn_failed)
        if summary.cinematic_actor_spawned_peak >= 80:
            score += 8
        elif summary.cinematic_actor_spawned_total > 0:
            score += 4
        if summary.cinematic_actor_cleanup_scheduled >= summary.cinematic_actor_spawned_total:
            score += 7
        else:
            score -= 20
        if summary.cinematic_actor_motion_summary > 0 and summary.cinematic_actor_motion_commands >= summary.cinematic_actor_spawned_total:
            score += 8
        elif summary.cinematic_actor_spawned_total > 0:
            score -= 12
        engagement_expected_total = cinematic_actor_engagement_expected_total(summary)
        if summary.cinematic_actor_engagement_summary > 0 and summary.cinematic_actor_engaged_total >= engagement_expected_total:
            score += 6
        elif summary.cinematic_interaction_scene > 0:
            score -= 10

    if summary.scene_director_beat > 0:
        score += 5

    return max(0, min(100, int(score)))


def cinematic_actor_engagement_expected_total(summary: CaseSummary) -> int:
    if summary.cinematic_actor_engagement_spawned_total > 0:
        return summary.cinematic_actor_engagement_spawned_total

    players = max(1, summary.players)
    return max(0, summary.cinematic_actor_spawned_total - players)


def calculate_action_scene_cohesion_score(summary: CaseSummary) -> int:
    if summary.scene_director_beat <= 0 and summary.cinematic_action <= 0:
        return 0

    score = 0
    if summary.cinematic_motion_variety >= 4:
        score += 20
    elif summary.cinematic_motion_variety >= 2:
        score += 12
    elif summary.cinematic_motion_variety >= 1:
        score += 5

    if summary.cinematic_tactic_variety >= 4:
        score += 20
    elif summary.cinematic_tactic_variety >= 2:
        score += 12
    elif summary.cinematic_tactic_variety >= 1:
        score += 5

    if summary.cinematic_actor_role_variety >= 4:
        score += 15
    elif summary.cinematic_actor_role_variety >= 2:
        score += 8
    elif summary.cinematic_actor_role_variety >= 1:
        score += 4

    if summary.cinematic_staggered_scene > 0:
        score += 8
    if summary.cinematic_objective_focal_scene > 0:
        score += 7
    if summary.cinematic_choreographed_scene > 0:
        score += 15
    if summary.cinematic_interaction_scene > 0:
        score += 15
    if summary.cinematic_model_role_fit_score >= 80:
        score += 8
    elif summary.cinematic_model_role_fit_score >= 60:
        score += 5
    elif summary.cinematic_model_role_fit_score >= 30:
        score += 2

    return max(0, min(100, int(score)))


def calculate_cinematic_model_role_fit_score(summary: CaseSummary) -> int:
    if summary.scene_director_beat <= 0 and summary.cinematic_action <= 0:
        return 0
    if summary.cinematic_catalog_role_variety <= 0:
        return 0

    score = 0
    if summary.cinematic_catalog_role_variety >= 4:
        score += 40
    elif summary.cinematic_catalog_role_variety >= 3:
        score += 32
    elif summary.cinematic_catalog_role_variety >= 2:
        score += 22
    else:
        score += 12

    if summary.cinematic_actor_role_variety >= 4:
        score += 20
    elif summary.cinematic_actor_role_variety >= 2:
        score += 12
    elif summary.cinematic_actor_role_variety >= 1:
        score += 6

    if summary.cinematic_tactic_variety >= 3:
        score += 15
    elif summary.cinematic_tactic_variety >= 1:
        score += 8

    if summary.presentation_staged_role_variety >= 3:
        score += 10
    elif summary.presentation_staged_role_variety >= 1:
        score += 5

    if summary.cinematic_marker_variety >= 2:
        score += 10
    elif summary.cinematic_marker_scene > 0:
        score += 5

    if summary.cinematic_objective_focal_scene > 0:
        score += 10
    if summary.cinematic_interaction_scene > 0:
        score += 10

    return max(0, min(100, int(score)))


def calculate_story_continuity_score(
    summary: CaseSummary,
    *,
    require_branch_choice: bool = False,
    require_world_signal: bool = False,
) -> int:
    if summary.players <= 0:
        return 0

    score = 0
    narrative_per_player = summary.narrative_scene / max(1, summary.players)
    presentation_per_player = summary.presentation_beat / max(1, summary.players)

    if narrative_per_player >= 4:
        score += 20
    elif narrative_per_player >= 2:
        score += 15
    elif summary.narrative_scene > 0:
        score += 8

    if presentation_per_player >= 6:
        score += 15
    elif presentation_per_player >= 3:
        score += 12
    elif summary.presentation_beat > 0:
        score += 6

    if summary.choice_selected > 0:
        if summary.choice_outcome_scene > 0:
            score += 15
        if summary.choice_consequence > 0:
            score += 5
    elif require_branch_choice and summary.completed > 0:
        score -= 10
    else:
        score += 10

    if summary.scene_actor_exchange > 0 or summary.scene_exchange_outcome > 0:
        if summary.scene_exchange_outcome > 0 and summary.scene_consequence > 0:
            score += 20
        elif summary.scene_exchange_outcome > 0:
            score += 8
    elif summary.scene_director_beat > 0 and summary.scene_beat_outcome > 0:
        score += 12
    else:
        score += 8

    if summary.world_signal > 0:
        if summary.world_signal_scene_shift > 0:
            score += 15
    elif require_world_signal and summary.completed > 0:
        score -= 10
    else:
        score += 10

    if summary.completed > 0 and summary.world_impact_summary > 0:
        score += 20
    elif summary.completed > 0 and summary.world_impact > 0:
        score += 10
    if summary.completed > 0 and summary.world_memory_marked > 0:
        score += 5

    return max(0, min(100, int(score)))


def calculate_story_archetype_score(summary: CaseSummary, case: QuestCase | None = None) -> int:
    if summary.players <= 0:
        return 0

    tags = {text_value(tag).lower() for tag in getattr(case, "tags", ()) if text_value(tag)}
    score = 0
    if any(tag.startswith("story-archetype:") for tag in tags):
        score += 25
    for arc in ("motive", "conflict", "reversal", "consequence"):
        if f"story-arc:{arc}" in tags:
            score += 5
    if "story-cinematic" in tags:
        score += 10
    if "scene-director" in tags:
        score += 10
    if "mass-cinematic" in tags and summary.cinematic_actor_peak >= 80:
        score += 10

    narrative_per_player = summary.narrative_scene / max(1, summary.players)
    presentation_per_player = summary.presentation_beat / max(1, summary.players)
    if narrative_per_player >= 5:
        score += 10
    elif narrative_per_player >= 3:
        score += 6
    if presentation_per_player >= 8:
        score += 10
    elif presentation_per_player >= 4:
        score += 6
    if summary.choice_outcome_scene > 0 and summary.scene_consequence > 0:
        score += 5
    if summary.world_signal > 0 and summary.world_signal_scene_shift > 0:
        score += 5

    return max(0, min(100, int(score)))


def finalize_case_summary_scores(
    summary: CaseSummary,
    *,
    require_followup_hunt: bool = False,
    require_branch_choice: bool = False,
    require_world_signal: bool = False,
) -> CaseSummary:
    with_density = replace(
        summary,
        cinematic_density_score=calculate_cinematic_density_score(summary),
    )
    with_actor_budget = replace(
        with_density,
        cinematic_actor_budget_score=calculate_cinematic_actor_budget_score(with_density),
    )
    with_action_scene = replace(
        with_actor_budget,
        action_scene_cohesion_score=calculate_action_scene_cohesion_score(with_actor_budget),
    )
    with_model_role_fit = replace(
        with_action_scene,
        cinematic_model_role_fit_score=calculate_cinematic_model_role_fit_score(with_action_scene),
    )
    with_action_scene = replace(
        with_model_role_fit,
        action_scene_cohesion_score=calculate_action_scene_cohesion_score(with_model_role_fit),
    )
    with_continuity = replace(
        with_action_scene,
        story_continuity_score=calculate_story_continuity_score(
            with_action_scene,
            require_branch_choice=require_branch_choice,
            require_world_signal=require_world_signal,
        ),
    )
    with_skyrim = replace(
        with_continuity,
        skyrim_grade_score=calculate_skyrim_grade_score(
            with_continuity,
            require_followup_hunt=require_followup_hunt,
            require_branch_choice=require_branch_choice,
            require_world_signal=require_world_signal,
        ),
    )
    return replace(
        with_skyrim,
        evaluation_score=calculate_case_evaluation_score(with_skyrim, require_followup_hunt=require_followup_hunt),
    )


def ensure_case_story_archetype_score(
    summary: CaseSummary,
    case: QuestCase | None,
    *,
    require_followup_hunt: bool = False,
) -> CaseSummary:
    score = calculate_story_archetype_score(summary, case)
    updated = summary if score == summary.story_archetype_score else replace(summary, story_archetype_score=score)
    return finalize_case_summary_scores(
        updated,
        require_followup_hunt=require_followup_hunt,
        require_branch_choice=quest_case_expects_branch_choice(case),
        require_world_signal=quest_case_expects_world_signal(case) or require_followup_hunt,
    )


def summarize_case(case_dir: Path, *, require_followup_hunt: bool = False) -> CaseSummary:
    metrics_path = case_dir / "metrics.csv"
    if not metrics_path.exists():
        return CaseSummary(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0.0, False)

    with metrics_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    players = len(rows)
    ok_players = sum(1 for row in rows if truthy(row.get("ok")))
    completed = sum(1 for row in rows if row_has_dynamic_quest_completion(row))
    expected_active_node = sum(1 for row in rows if row_has_dynamic_quest_expected_active_node(row))
    reward_observed = sum(1 for row in rows if to_int(row.get("action_dynamic_quest_reward_observed")) > 0)
    target_removed = sum(row_target_removed_count(row) for row in rows)
    player_deaths = sum(to_int(row.get("player_deaths")) for row in rows)
    choice_selected = sum(to_int(row.get("action_dynamic_quest_timeline_choice_selected")) for row in rows)
    choice_ids = collect_dynamic_quest_choice_ids(case_dir)
    safe_choice_seen = 1 if any(choice_id.lower() == "safe" for choice_id in choice_ids) else 0
    choice_outcome_scene = sum(to_int(row.get("action_dynamic_quest_timeline_choice_outcome_scene")) for row in rows)
    choice_consequence = sum(to_int(row.get("action_dynamic_quest_timeline_choice_consequence")) for row in rows)
    world_signal = sum(to_int(row.get("action_dynamic_quest_timeline_world_signal")) for row in rows)
    presentation_beat = sum(to_int(row.get("action_dynamic_quest_timeline_presentation_beat")) for row in rows)
    world_impact = sum(to_int(row.get("action_dynamic_quest_timeline_world_impact")) for row in rows)
    world_impact_summary = sum(to_int(row.get("action_dynamic_quest_timeline_world_impact_summary")) for row in rows)
    world_memory_marked = sum(to_int(row.get("action_dynamic_quest_timeline_world_memory_marked")) for row in rows)
    narrative_scene = sum(to_int(row.get("action_dynamic_quest_timeline_narrative_scene")) for row in rows)
    cinematic_action = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_action")) for row in rows)
    min_narrative_scene_per_player = min(
        (to_int(row.get("action_dynamic_quest_timeline_narrative_scene")) for row in rows),
        default=-1,
    )
    min_presentation_beat_per_player = min(
        (to_int(row.get("action_dynamic_quest_timeline_presentation_beat")) for row in rows),
        default=-1,
    )
    min_cinematic_action_per_player = min(
        (to_int(row.get("action_dynamic_quest_timeline_cinematic_action")) for row in rows),
        default=-1,
    )
    scene_director_beat = sum(to_int(row.get("action_dynamic_quest_timeline_scene_director_beat")) for row in rows)
    scene_beat_outcome = sum(to_int(row.get("action_dynamic_quest_timeline_scene_beat_outcome")) for row in rows)
    scene_choreography_phase = sum(to_int(row.get("action_dynamic_quest_timeline_scene_choreography_phase")) for row in rows)
    scene_actor_exchange = sum(to_int(row.get("action_dynamic_quest_timeline_scene_actor_exchange")) for row in rows)
    scene_exchange_outcome = sum(to_int(row.get("action_dynamic_quest_timeline_scene_exchange_outcome")) for row in rows)
    scene_outcome_signal = sum(to_int(row.get("action_dynamic_quest_timeline_scene_outcome_signal")) for row in rows)
    scene_consequence = sum(to_int(row.get("action_dynamic_quest_timeline_scene_consequence")) for row in rows)
    scene_world_signal = sum(to_int(row.get("action_dynamic_quest_timeline_scene_world_signal")) for row in rows)
    world_signal_scene_shift = sum(to_int(row.get("action_dynamic_quest_timeline_world_signal_scene_shift")) for row in rows)
    cinematic_cleanup = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_cleanup")) for row in rows)
    cinematic_variety = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_variety")) for row in rows)
    cinematic_motion_variety = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_motion_variety")) for row in rows)
    cinematic_staggered_scene = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_staggered_scene")) for row in rows)
    cinematic_objective_focal_scene = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_objective_focal_scene")) for row in rows)
    cinematic_actor_role_variety = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_role_variety")) for row in rows)
    cinematic_choreographed_scene = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_choreographed_scene")) for row in rows)
    cinematic_interaction_scene = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_interaction_scene")) for row in rows)
    cinematic_tactic_variety = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_tactic_variety")) for row in rows)
    cinematic_actor_instances = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_instances")) for row in rows)
    cinematic_actor_peak = max((to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_peak")) for row in rows), default=0)
    cinematic_actor_spawn_summary = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_spawn_summary")) for row in rows)
    cinematic_actor_spawned_total = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_spawned_total")) for row in rows)
    cinematic_actor_spawned_peak = max((to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_spawned_peak")) for row in rows), default=0)
    cinematic_actor_spawn_failed = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_spawn_failed")) for row in rows)
    cinematic_actor_cleanup_scheduled = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_cleanup_scheduled")) for row in rows)
    cinematic_actor_motion_summary = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_motion_summary")) for row in rows)
    cinematic_actor_motion_commands = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_motion_commands")) for row in rows)
    cinematic_actor_motion_commands_peak = max((to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_motion_commands_peak")) for row in rows), default=0)
    cinematic_actor_motion_commands_per_actor_peak = max((to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_motion_commands_per_actor_peak")) for row in rows), default=0)
    cinematic_actor_motion_spawned_total = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_motion_spawned_total")) for row in rows)
    cinematic_actor_engagement_summary = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_engagement_summary")) for row in rows)
    cinematic_actor_engagement_pairs = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_engagement_pairs")) for row in rows)
    cinematic_actor_engagement_pairs_peak = max((to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_engagement_pairs_peak")) for row in rows), default=0)
    cinematic_actor_engaged_total = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_engaged_total")) for row in rows)
    cinematic_actor_engagement_spawned_total = sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_actor_engagement_spawned_total")) for row in rows)
    cinematic_catalog_role_variety = max((to_int(row.get("action_dynamic_quest_timeline_cinematic_catalog_role_variety")) for row in rows), default=0)
    cinematic_model_role_fit_score = max((to_int(row.get("action_dynamic_quest_timeline_cinematic_model_role_fit_score")) for row in rows), default=0)
    has_marker_scene_metric = any("action_dynamic_quest_timeline_cinematic_marker_scene" in row for row in rows)
    has_marker_variety_metric = any("action_dynamic_quest_timeline_cinematic_marker_variety" in row for row in rows)
    has_phase_coverage_metric = any("action_dynamic_quest_timeline_cinematic_phase_coverage" in row for row in rows)
    has_setpiece_phase_metric = any("action_dynamic_quest_timeline_cinematic_setpiece_phase_coverage" in row for row in rows)
    has_marker_phase_metric = any("action_dynamic_quest_timeline_cinematic_marker_phase_coverage" in row for row in rows)
    has_story_chain_metric = any("action_dynamic_quest_timeline_cinematic_story_chain" in row for row in rows)
    has_presentation_staged_metric = any("action_dynamic_quest_timeline_presentation_staged_beat" in row for row in rows)
    cinematic_marker_scene = (
        sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_marker_scene")) for row in rows)
        if has_marker_scene_metric
        else -1
    )
    cinematic_marker_variety = (
        sum(to_int(row.get("action_dynamic_quest_timeline_cinematic_marker_variety")) for row in rows)
        if has_marker_variety_metric
        else -1
    )
    cinematic_phase_coverage = (
        max((to_int(row.get("action_dynamic_quest_timeline_cinematic_phase_coverage")) for row in rows), default=0)
        if has_phase_coverage_metric
        else -1
    )
    cinematic_setpiece_phase_coverage = (
        max((to_int(row.get("action_dynamic_quest_timeline_cinematic_setpiece_phase_coverage")) for row in rows), default=0)
        if has_setpiece_phase_metric
        else -1
    )
    cinematic_marker_phase_coverage = (
        max((to_int(row.get("action_dynamic_quest_timeline_cinematic_marker_phase_coverage")) for row in rows), default=0)
        if has_marker_phase_metric
        else -1
    )
    cinematic_story_chain = (
        max((to_int(row.get("action_dynamic_quest_timeline_cinematic_story_chain")) for row in rows), default=0)
        if has_story_chain_metric
        else -1
    )
    presentation_staged_beat = (
        sum(to_int(row.get("action_dynamic_quest_timeline_presentation_staged_beat")) for row in rows)
        if has_presentation_staged_metric
        else -1
    )
    presentation_staged_actor_total = (
        sum(to_int(row.get("action_dynamic_quest_timeline_presentation_staged_actor_total")) for row in rows)
        if has_presentation_staged_metric
        else -1
    )
    presentation_staged_actor_peak = (
        max((to_int(row.get("action_dynamic_quest_timeline_presentation_staged_actor_peak")) for row in rows), default=0)
        if has_presentation_staged_metric
        else -1
    )
    presentation_staged_action_variety = (
        max((to_int(row.get("action_dynamic_quest_timeline_presentation_staged_action_variety")) for row in rows), default=0)
        if has_presentation_staged_metric
        else -1
    )
    presentation_staged_role_variety = (
        max((to_int(row.get("action_dynamic_quest_timeline_presentation_staged_role_variety")) for row in rows), default=0)
        if has_presentation_staged_metric
        else -1
    )
    presentation_staged_formation_variety = (
        max((to_int(row.get("action_dynamic_quest_timeline_presentation_staged_formation_variety")) for row in rows), default=0)
        if has_presentation_staged_metric
        else -1
    )
    presentation_staged_delayed_beat = (
        sum(to_int(row.get("action_dynamic_quest_timeline_presentation_staged_delayed_beat")) for row in rows)
        if has_presentation_staged_metric
        else -1
    )
    followup_hunt_start = sum(to_int(row.get("action_dynamic_quest_followup_hunt_start")) for row in rows)
    never_active = sum(
        1
        for row in rows
        if to_int(row.get("action_dynamic_quest_final_never_active")) > 0
    )
    elapsed_seconds = max((to_float(row.get("elapsed_seconds")) for row in rows), default=0.0)
    passed = (
        players > 0
        and ok_players == players
        and completed + expected_active_node >= players
        and never_active == 0
        and (
            not require_followup_hunt
            or followup_hunt_start >= players
            or world_signal >= players
        )
    )
    summary = CaseSummary(
        players,
        ok_players,
        completed,
        reward_observed,
        target_removed,
        player_deaths,
        choice_selected,
        world_signal,
        presentation_beat,
        world_impact,
        world_impact_summary,
        narrative_scene,
        cinematic_action,
        scene_director_beat,
        scene_beat_outcome,
        scene_choreography_phase,
        scene_actor_exchange,
        scene_exchange_outcome,
        scene_outcome_signal,
        scene_consequence,
        scene_world_signal,
        world_signal_scene_shift,
        cinematic_cleanup,
        followup_hunt_start,
        elapsed_seconds,
        passed,
        choice_outcome_scene=choice_outcome_scene,
        choice_consequence=choice_consequence,
        world_memory_marked=world_memory_marked,
        cinematic_variety=cinematic_variety,
        cinematic_motion_variety=cinematic_motion_variety,
        cinematic_staggered_scene=cinematic_staggered_scene,
        cinematic_objective_focal_scene=cinematic_objective_focal_scene,
        cinematic_actor_role_variety=cinematic_actor_role_variety,
        cinematic_choreographed_scene=cinematic_choreographed_scene,
        cinematic_interaction_scene=cinematic_interaction_scene,
        cinematic_tactic_variety=cinematic_tactic_variety,
        cinematic_actor_instances=cinematic_actor_instances,
        cinematic_actor_peak=cinematic_actor_peak,
        cinematic_actor_spawn_summary=cinematic_actor_spawn_summary,
        cinematic_actor_spawned_total=cinematic_actor_spawned_total,
        cinematic_actor_spawned_peak=cinematic_actor_spawned_peak,
        cinematic_actor_spawn_failed=cinematic_actor_spawn_failed,
        cinematic_actor_cleanup_scheduled=cinematic_actor_cleanup_scheduled,
        cinematic_actor_motion_summary=cinematic_actor_motion_summary,
        cinematic_actor_motion_commands=cinematic_actor_motion_commands,
        cinematic_actor_motion_commands_peak=cinematic_actor_motion_commands_peak,
        cinematic_actor_motion_commands_per_actor_peak=cinematic_actor_motion_commands_per_actor_peak,
        cinematic_actor_motion_spawned_total=cinematic_actor_motion_spawned_total,
        cinematic_actor_engagement_summary=cinematic_actor_engagement_summary,
        cinematic_actor_engagement_pairs=cinematic_actor_engagement_pairs,
        cinematic_actor_engagement_pairs_peak=cinematic_actor_engagement_pairs_peak,
        cinematic_actor_engaged_total=cinematic_actor_engaged_total,
        cinematic_actor_engagement_spawned_total=cinematic_actor_engagement_spawned_total,
        cinematic_catalog_role_variety=cinematic_catalog_role_variety,
        cinematic_model_role_fit_score=cinematic_model_role_fit_score,
        min_narrative_scene_per_player=min_narrative_scene_per_player,
        min_presentation_beat_per_player=min_presentation_beat_per_player,
        min_cinematic_action_per_player=min_cinematic_action_per_player,
        cinematic_marker_scene=cinematic_marker_scene,
        cinematic_marker_variety=cinematic_marker_variety,
        cinematic_phase_coverage=cinematic_phase_coverage,
        cinematic_setpiece_phase_coverage=cinematic_setpiece_phase_coverage,
        cinematic_marker_phase_coverage=cinematic_marker_phase_coverage,
        cinematic_story_chain=cinematic_story_chain,
        presentation_staged_beat=presentation_staged_beat,
        presentation_staged_actor_total=presentation_staged_actor_total,
        presentation_staged_actor_peak=presentation_staged_actor_peak,
        presentation_staged_action_variety=presentation_staged_action_variety,
        presentation_staged_role_variety=presentation_staged_role_variety,
        presentation_staged_formation_variety=presentation_staged_formation_variety,
        presentation_staged_delayed_beat=presentation_staged_delayed_beat,
        choice_ids=choice_ids,
        safe_choice_seen=safe_choice_seen,
    )
    return finalize_case_summary_scores(summary, require_followup_hunt=require_followup_hunt)


def collect_dynamic_quest_choice_ids(case_dir: Path) -> tuple[str, ...]:
    seen: set[str] = set()
    choice_ids: list[str] = []
    for log_path in sorted(case_dir.glob("encounters-*.jsonl")):
        try:
            lines = log_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("event") != "dynamic_quest_timeline_snapshot":
                continue
            raw_choice_ids = event.get("choice_ids")
            if not isinstance(raw_choice_ids, list):
                continue
            for raw_choice_id in raw_choice_ids:
                choice_id = text_value(raw_choice_id)
                if not choice_id:
                    continue
                key = choice_id.lower()
                if key in seen:
                    continue
                seen.add(key)
                choice_ids.append(choice_id)
    return tuple(choice_ids)


def metric_usernames(case_dir: Path) -> list[str]:
    metrics_path = case_dir / "metrics.csv"
    if not metrics_path.exists():
        return []

    with metrics_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    seen: set[str] = set()
    usernames: list[str] = []
    for row in rows:
        username = text_value(row.get("username"))
        if not username:
            continue
        key = username.lower()
        if key in seen:
            continue
        seen.add(key)
        usernames.append(username)
    return usernames


def enrich_summary_from_dynamic_quest_api(
    case: QuestCase,
    args: argparse.Namespace,
    summary: CaseSummary,
    *,
    require_followup_hunt: bool = False,
) -> CaseSummary:
    quest_id = text_value(getattr(case, "quest_id", ""))
    if not quest_id or summary.players <= 0:
        return summary

    aggregate = {
        "completed": 0,
        "choice_selected": 0,
        "choice_outcome_scene": 0,
        "choice_consequence": 0,
        "world_signal": 0,
        "presentation_beat": 0,
        "presentation_speaker_variety": -1,
        "world_impact": 0,
        "world_impact_summary": 0,
        "world_memory_marked": 0,
        "narrative_scene": 0,
        "cinematic_action": 0,
        "scene_director_beat": 0,
        "scene_beat_outcome": 0,
        "scene_choreography_phase": 0,
        "scene_actor_exchange": 0,
        "scene_exchange_outcome": 0,
        "scene_outcome_signal": 0,
        "scene_consequence": 0,
        "scene_world_signal": 0,
        "world_signal_scene_shift": 0,
        "cinematic_cleanup": 0,
        "kill_confirmed": 0,
        "cinematic_variety": 0,
        "cinematic_motion_variety": 0,
        "cinematic_staggered_scene": 0,
        "cinematic_objective_focal_scene": 0,
        "cinematic_actor_role_variety": 0,
        "cinematic_choreographed_scene": 0,
        "cinematic_interaction_scene": 0,
        "cinematic_tactic_variety": 0,
        "cinematic_actor_instances": 0,
        "cinematic_actor_peak": 0,
        "cinematic_actor_spawn_summary": 0,
        "cinematic_actor_spawned_total": 0,
        "cinematic_actor_spawned_peak": 0,
        "cinematic_actor_spawn_failed": 0,
        "cinematic_actor_cleanup_scheduled": 0,
        "cinematic_actor_motion_summary": 0,
        "cinematic_actor_motion_commands": 0,
        "cinematic_actor_motion_commands_peak": 0,
        "cinematic_actor_motion_commands_per_actor_peak": 0,
        "cinematic_actor_motion_spawned_total": 0,
        "cinematic_actor_engagement_summary": 0,
        "cinematic_actor_engagement_pairs": 0,
        "cinematic_actor_engagement_pairs_peak": 0,
        "cinematic_actor_engaged_total": 0,
        "cinematic_actor_engagement_spawned_total": 0,
        "cinematic_catalog_role_variety": 0,
        "cinematic_marker_scene": 0,
        "cinematic_marker_variety": 0,
        "cinematic_phase_coverage": 0,
        "cinematic_setpiece_phase_coverage": 0,
        "cinematic_marker_phase_coverage": 0,
        "cinematic_story_chain": 0,
        "presentation_staged_beat": 0,
        "presentation_staged_actor_total": 0,
        "presentation_staged_actor_peak": 0,
        "presentation_staged_action_variety": 0,
        "presentation_staged_role_variety": 0,
        "presentation_staged_formation_variety": 0,
        "presentation_staged_delayed_beat": 0,
        "world_signal_scene_shift_detail": 0,
        "world_signal_scene_shift_phase_variety": 0,
        "world_signal_scene_shift_source_variety": 0,
        "world_signal_scene_shift_target_variety": 0,
    }

    for username in metric_usernames(case.output_dir):
        try:
            observations = summarize_dynamic_quest_timeline_observations(
                fetch_dynamic_quest_player_api(args, "timeline", username),
                quest_id,
            )
        except Exception:  # noqa: BLE001 - API enrichment must not hide the original run result.
            continue

        for key in aggregate:
            value = int(observations.get(key, 0) or 0)
            if key in {
                "cinematic_actor_peak",
                "cinematic_actor_spawned_peak",
                "cinematic_actor_motion_commands_peak",
                "cinematic_actor_motion_commands_per_actor_peak",
                "cinematic_actor_engagement_pairs_peak",
                "cinematic_catalog_role_variety",
                "presentation_speaker_variety",
                "presentation_staged_actor_peak",
                "presentation_staged_action_variety",
                "presentation_staged_role_variety",
                "presentation_staged_formation_variety",
            }:
                aggregate[key] = max(aggregate[key], value)
            else:
                aggregate[key] += value

    if not any(aggregate.values()):
        return summary

    completed = max(summary.completed, aggregate["completed"])
    passed = (
        bool(summary.passed)
        or (
            summary.players > 0
            and summary.ok_players == summary.players
            and completed == summary.players
            and summary.player_deaths == 0
            and (
                not require_followup_hunt
                or summary.followup_hunt_start >= summary.players
                or max(summary.world_signal, aggregate["world_signal"]) >= summary.players
            )
        )
    )
    enriched = replace(
        summary,
        completed=completed,
        choice_selected=max(summary.choice_selected, aggregate["choice_selected"]),
        choice_outcome_scene=max(summary.choice_outcome_scene, aggregate["choice_outcome_scene"]),
        choice_consequence=max(summary.choice_consequence, aggregate["choice_consequence"]),
        world_signal=max(summary.world_signal, aggregate["world_signal"]),
        presentation_beat=max(summary.presentation_beat, aggregate["presentation_beat"]),
        presentation_speaker_variety=max(summary.presentation_speaker_variety, aggregate["presentation_speaker_variety"]),
        world_impact=max(summary.world_impact, aggregate["world_impact"]),
        world_impact_summary=max(summary.world_impact_summary, aggregate["world_impact_summary"]),
        world_memory_marked=max(summary.world_memory_marked, aggregate["world_memory_marked"]),
        narrative_scene=max(summary.narrative_scene, aggregate["narrative_scene"]),
        cinematic_action=max(summary.cinematic_action, aggregate["cinematic_action"]),
        scene_director_beat=max(summary.scene_director_beat, aggregate["scene_director_beat"]),
        scene_beat_outcome=max(summary.scene_beat_outcome, aggregate["scene_beat_outcome"]),
        scene_choreography_phase=max(summary.scene_choreography_phase, aggregate["scene_choreography_phase"]),
        scene_actor_exchange=max(summary.scene_actor_exchange, aggregate["scene_actor_exchange"]),
        scene_exchange_outcome=max(summary.scene_exchange_outcome, aggregate["scene_exchange_outcome"]),
        scene_outcome_signal=max(summary.scene_outcome_signal, aggregate["scene_outcome_signal"]),
        scene_consequence=max(summary.scene_consequence, aggregate["scene_consequence"]),
        scene_world_signal=max(summary.scene_world_signal, aggregate["scene_world_signal"]),
        world_signal_scene_shift=max(summary.world_signal_scene_shift, aggregate["world_signal_scene_shift"]),
        world_signal_scene_shift_detail=max(
            summary.world_signal_scene_shift_detail,
            aggregate["world_signal_scene_shift_detail"],
        ),
        world_signal_scene_shift_phase_variety=max(
            summary.world_signal_scene_shift_phase_variety,
            aggregate["world_signal_scene_shift_phase_variety"],
        ),
        world_signal_scene_shift_source_variety=max(
            summary.world_signal_scene_shift_source_variety,
            aggregate["world_signal_scene_shift_source_variety"],
        ),
        world_signal_scene_shift_target_variety=max(
            summary.world_signal_scene_shift_target_variety,
            aggregate["world_signal_scene_shift_target_variety"],
        ),
        cinematic_cleanup=max(summary.cinematic_cleanup, aggregate["cinematic_cleanup"]),
        kill_confirmed=max(summary.kill_confirmed, aggregate["kill_confirmed"]),
        cinematic_variety=max(summary.cinematic_variety, aggregate["cinematic_variety"]),
        cinematic_motion_variety=max(summary.cinematic_motion_variety, aggregate["cinematic_motion_variety"]),
        cinematic_staggered_scene=max(summary.cinematic_staggered_scene, aggregate["cinematic_staggered_scene"]),
        cinematic_objective_focal_scene=max(summary.cinematic_objective_focal_scene, aggregate["cinematic_objective_focal_scene"]),
        cinematic_actor_role_variety=max(summary.cinematic_actor_role_variety, aggregate["cinematic_actor_role_variety"]),
        cinematic_choreographed_scene=max(summary.cinematic_choreographed_scene, aggregate["cinematic_choreographed_scene"]),
        cinematic_interaction_scene=max(summary.cinematic_interaction_scene, aggregate["cinematic_interaction_scene"]),
        cinematic_tactic_variety=max(summary.cinematic_tactic_variety, aggregate["cinematic_tactic_variety"]),
        cinematic_actor_instances=max(summary.cinematic_actor_instances, aggregate["cinematic_actor_instances"]),
        cinematic_actor_peak=max(summary.cinematic_actor_peak, aggregate["cinematic_actor_peak"]),
        cinematic_actor_spawn_summary=max(summary.cinematic_actor_spawn_summary, aggregate["cinematic_actor_spawn_summary"]),
        cinematic_actor_spawned_total=max(summary.cinematic_actor_spawned_total, aggregate["cinematic_actor_spawned_total"]),
        cinematic_actor_spawned_peak=max(summary.cinematic_actor_spawned_peak, aggregate["cinematic_actor_spawned_peak"]),
        cinematic_actor_spawn_failed=max(summary.cinematic_actor_spawn_failed, aggregate["cinematic_actor_spawn_failed"]),
        cinematic_actor_cleanup_scheduled=max(
            summary.cinematic_actor_cleanup_scheduled,
            aggregate["cinematic_actor_cleanup_scheduled"],
        ),
        cinematic_actor_motion_summary=max(summary.cinematic_actor_motion_summary, aggregate["cinematic_actor_motion_summary"]),
        cinematic_actor_motion_commands=max(summary.cinematic_actor_motion_commands, aggregate["cinematic_actor_motion_commands"]),
        cinematic_actor_motion_commands_peak=max(
            summary.cinematic_actor_motion_commands_peak,
            aggregate["cinematic_actor_motion_commands_peak"],
        ),
        cinematic_actor_motion_commands_per_actor_peak=max(
            summary.cinematic_actor_motion_commands_per_actor_peak,
            aggregate["cinematic_actor_motion_commands_per_actor_peak"],
        ),
        cinematic_actor_motion_spawned_total=max(
            summary.cinematic_actor_motion_spawned_total,
            aggregate["cinematic_actor_motion_spawned_total"],
        ),
        cinematic_actor_engagement_summary=max(summary.cinematic_actor_engagement_summary, aggregate["cinematic_actor_engagement_summary"]),
        cinematic_actor_engagement_pairs=max(summary.cinematic_actor_engagement_pairs, aggregate["cinematic_actor_engagement_pairs"]),
        cinematic_actor_engagement_pairs_peak=max(
            summary.cinematic_actor_engagement_pairs_peak,
            aggregate["cinematic_actor_engagement_pairs_peak"],
        ),
        cinematic_actor_engaged_total=max(summary.cinematic_actor_engaged_total, aggregate["cinematic_actor_engaged_total"]),
        cinematic_actor_engagement_spawned_total=max(
            summary.cinematic_actor_engagement_spawned_total,
            aggregate["cinematic_actor_engagement_spawned_total"],
        ),
        cinematic_catalog_role_variety=max(summary.cinematic_catalog_role_variety, aggregate["cinematic_catalog_role_variety"]),
        cinematic_marker_scene=max(summary.cinematic_marker_scene, aggregate["cinematic_marker_scene"]),
        cinematic_marker_variety=max(summary.cinematic_marker_variety, aggregate["cinematic_marker_variety"]),
        cinematic_phase_coverage=max(summary.cinematic_phase_coverage, aggregate["cinematic_phase_coverage"]),
        cinematic_setpiece_phase_coverage=max(
            summary.cinematic_setpiece_phase_coverage,
            aggregate["cinematic_setpiece_phase_coverage"],
        ),
        cinematic_marker_phase_coverage=max(summary.cinematic_marker_phase_coverage, aggregate["cinematic_marker_phase_coverage"]),
        cinematic_story_chain=max(summary.cinematic_story_chain, aggregate["cinematic_story_chain"]),
        presentation_staged_beat=max(summary.presentation_staged_beat, aggregate["presentation_staged_beat"]),
        presentation_staged_actor_total=max(summary.presentation_staged_actor_total, aggregate["presentation_staged_actor_total"]),
        presentation_staged_actor_peak=max(summary.presentation_staged_actor_peak, aggregate["presentation_staged_actor_peak"]),
        presentation_staged_action_variety=max(summary.presentation_staged_action_variety, aggregate["presentation_staged_action_variety"]),
        presentation_staged_role_variety=max(summary.presentation_staged_role_variety, aggregate["presentation_staged_role_variety"]),
        presentation_staged_formation_variety=max(summary.presentation_staged_formation_variety, aggregate["presentation_staged_formation_variety"]),
        presentation_staged_delayed_beat=max(summary.presentation_staged_delayed_beat, aggregate["presentation_staged_delayed_beat"]),
        passed=passed,
    )
    return finalize_case_summary_scores(enriched, require_followup_hunt=require_followup_hunt)


def write_case_summary(
    case: QuestCase,
    summary: CaseSummary,
    *,
    minimum_action_scene_cohesion: int = 70,
    minimum_catalog_role_variety: int = 2,
    minimum_model_role_fit: int = 70,
) -> None:
    summary = ensure_case_story_archetype_score(
        summary,
        case,
        require_followup_hunt=bool(getattr(case, "followup_growth_target", False)),
    )
    status = "passed" if effective_case_passed(
        summary,
        minimum_action_scene_cohesion=minimum_action_scene_cohesion,
        minimum_catalog_role_variety=minimum_catalog_role_variety,
        minimum_model_role_fit=minimum_model_role_fit,
        case_dir=case.output_dir,
    ) else "failed"
    operational = calculate_dummy_operational_evaluation(summary, case)
    failure_category = classify_case_failure(
        summary,
        case.output_dir,
        minimum_action_scene_cohesion=minimum_action_scene_cohesion,
        minimum_catalog_role_variety=minimum_catalog_role_variety,
        minimum_model_role_fit=minimum_model_role_fit,
    )
    text = (
        f"# {case.name}\n\n"
        f"- realm: {case.realm}\n"
        f"- party_size: {case.party_size}\n"
        f"- status: {status}\n"
        f"- failure_category: {failure_category}\n"
        f"- players: {summary.players}\n"
        f"- ok_players: {summary.ok_players}\n"
        f"- completed: {summary.completed}\n"
        f"- reward_observed: {summary.reward_observed}\n"
        f"- target_removed: {summary.target_removed}\n"
        f"- kill_confirmed: {summary.kill_confirmed}\n"
        f"- player_deaths: {summary.player_deaths}\n"
        f"- choice_selected: {summary.choice_selected}\n"
        f"- choice_ids: {', '.join(summary.choice_ids) if summary.choice_ids else 'none'}\n"
        f"- safe_choice_seen: {summary.safe_choice_seen}\n"
        f"- choice_outcome_scene: {summary.choice_outcome_scene}\n"
        f"- world_signal: {summary.world_signal}\n"
        f"- presentation_beat: {summary.presentation_beat}\n"
        f"- presentation_speaker_variety: {summary.presentation_speaker_variety}\n"
        f"- presentation_staged_beat: {summary.presentation_staged_beat}\n"
        f"- presentation_staged_actor_total: {summary.presentation_staged_actor_total}\n"
        f"- presentation_staged_actor_peak: {summary.presentation_staged_actor_peak}\n"
        f"- presentation_staged_action_variety: {summary.presentation_staged_action_variety}\n"
        f"- presentation_staged_role_variety: {summary.presentation_staged_role_variety}\n"
        f"- presentation_staged_formation_variety: {summary.presentation_staged_formation_variety}\n"
        f"- presentation_staged_delayed_beat: {summary.presentation_staged_delayed_beat}\n"
        f"- world_impact: {summary.world_impact}\n"
        f"- world_impact_summary: {summary.world_impact_summary}\n"
        f"- narrative_scene: {summary.narrative_scene}\n"
        f"- cinematic_action: {summary.cinematic_action}\n"
        f"- min_narrative_scene_per_player: {summary.min_narrative_scene_per_player}\n"
        f"- min_presentation_beat_per_player: {summary.min_presentation_beat_per_player}\n"
        f"- min_cinematic_action_per_player: {summary.min_cinematic_action_per_player}\n"
        f"- cinematic_variety: {summary.cinematic_variety}\n"
        f"- cinematic_motion_variety: {summary.cinematic_motion_variety}\n"
        f"- cinematic_staggered_scene: {summary.cinematic_staggered_scene}\n"
        f"- cinematic_objective_focal_scene: {summary.cinematic_objective_focal_scene}\n"
        f"- cinematic_actor_role_variety: {summary.cinematic_actor_role_variety}\n"
        f"- cinematic_choreographed_scene: {summary.cinematic_choreographed_scene}\n"
        f"- cinematic_interaction_scene: {summary.cinematic_interaction_scene}\n"
        f"- cinematic_tactic_variety: {summary.cinematic_tactic_variety}\n"
        f"- cinematic_actor_instances: {summary.cinematic_actor_instances}\n"
        f"- cinematic_actor_peak: {summary.cinematic_actor_peak}\n"
        f"- cinematic_actor_spawn_summary: {summary.cinematic_actor_spawn_summary}\n"
        f"- cinematic_actor_spawned_total: {summary.cinematic_actor_spawned_total}\n"
        f"- cinematic_actor_spawned_peak: {summary.cinematic_actor_spawned_peak}\n"
        f"- cinematic_actor_spawn_failed: {summary.cinematic_actor_spawn_failed}\n"
        f"- cinematic_actor_cleanup_scheduled: {summary.cinematic_actor_cleanup_scheduled}\n"
        f"- cinematic_actor_motion_summary: {summary.cinematic_actor_motion_summary}\n"
        f"- cinematic_actor_motion_commands: {summary.cinematic_actor_motion_commands}\n"
        f"- cinematic_actor_motion_commands_peak: {summary.cinematic_actor_motion_commands_peak}\n"
        f"- cinematic_actor_motion_commands_per_actor_peak: {summary.cinematic_actor_motion_commands_per_actor_peak}\n"
        f"- cinematic_actor_motion_spawned_total: {summary.cinematic_actor_motion_spawned_total}\n"
        f"- cinematic_actor_engagement_summary: {summary.cinematic_actor_engagement_summary}\n"
        f"- cinematic_actor_engagement_pairs: {summary.cinematic_actor_engagement_pairs}\n"
        f"- cinematic_actor_engagement_pairs_peak: {summary.cinematic_actor_engagement_pairs_peak}\n"
        f"- cinematic_actor_engaged_total: {summary.cinematic_actor_engaged_total}\n"
        f"- cinematic_actor_engagement_spawned_total: {summary.cinematic_actor_engagement_spawned_total}\n"
        f"- cinematic_actor_budget_score: {summary.cinematic_actor_budget_score}\n"
        f"- action_scene_cohesion_score: {summary.action_scene_cohesion_score}\n"
        f"- cinematic_catalog_role_variety: {summary.cinematic_catalog_role_variety}\n"
        f"- cinematic_model_role_fit_score: {summary.cinematic_model_role_fit_score}\n"
        f"- cinematic_marker_scene: {summary.cinematic_marker_scene}\n"
        f"- cinematic_marker_variety: {summary.cinematic_marker_variety}\n"
        f"- cinematic_phase_coverage: {summary.cinematic_phase_coverage}\n"
        f"- cinematic_setpiece_phase_coverage: {summary.cinematic_setpiece_phase_coverage}\n"
        f"- cinematic_marker_phase_coverage: {summary.cinematic_marker_phase_coverage}\n"
        f"- cinematic_story_chain: {summary.cinematic_story_chain}\n"
        f"- scene_director_beat: {summary.scene_director_beat}\n"
        f"- scene_beat_outcome: {summary.scene_beat_outcome}\n"
        f"- scene_choreography_phase: {summary.scene_choreography_phase}\n"
        f"- scene_actor_exchange: {summary.scene_actor_exchange}\n"
        f"- scene_exchange_outcome: {summary.scene_exchange_outcome}\n"
        f"- scene_outcome_signal: {summary.scene_outcome_signal}\n"
        f"- scene_consequence: {summary.scene_consequence}\n"
        f"- scene_world_signal: {summary.scene_world_signal}\n"
        f"- world_signal_scene_shift: {summary.world_signal_scene_shift}\n"
        f"- world_signal_scene_shift_detail: {summary.world_signal_scene_shift_detail}\n"
        f"- world_signal_scene_shift_phase_variety: {summary.world_signal_scene_shift_phase_variety}\n"
        f"- world_signal_scene_shift_source_variety: {summary.world_signal_scene_shift_source_variety}\n"
        f"- world_signal_scene_shift_target_variety: {summary.world_signal_scene_shift_target_variety}\n"
        f"- cinematic_cleanup: {summary.cinematic_cleanup}\n"
        f"- followup_hunt_start: {summary.followup_hunt_start}\n"
        f"- cinematic_density_score: {summary.cinematic_density_score}\n"
        f"- story_continuity_score: {summary.story_continuity_score}\n"
        f"- story_archetype_score: {summary.story_archetype_score}\n"
        f"- skyrim_grade_score: {summary.skyrim_grade_score}\n"
        f"- evaluation_score: {summary.evaluation_score}\n"
        f"- operational_score: {operational['totalScore']}\n"
        f"- operational_grade: {operational['grade']}\n"
        f"- operational_passed: {str(bool(operational['passed'])).lower()}\n"
        f"- operational_exploit_penalty: {operational['exploitPenalty']}\n"
        f"- elapsed_seconds: {summary.elapsed_seconds:.3f}\n"
    )
    (case.output_dir / "matrix-summary.md").write_text(text, encoding="utf-8")


def submit_dynamic_quest_evaluation(case: QuestCase, args: argparse.Namespace, summary: CaseSummary) -> None:
    if not bool(getattr(args, "dynamic_quest_submit_evaluation", True)):
        return
    summary = ensure_case_story_archetype_score(
        summary,
        case,
        require_followup_hunt=case_followup_growth_target(case, args),
    )

    quest_id = text_value(getattr(case, "quest_id", ""))
    if not quest_id or summary.players <= 0:
        return

    minimum_score = max(1, min(100, int(getattr(args, "dynamic_quest_evaluation_min_score", 70) or 70)))
    minimum_action_scene_cohesion = min_action_scene_cohesion_from_args(args)
    minimum_catalog_role_variety = min_cinematic_catalog_role_variety_from_args(args)
    minimum_model_role_fit = min_cinematic_model_role_fit_from_args(args)
    failure_category = classify_case_failure(
        summary,
        case.output_dir,
        minimum_action_scene_cohesion=minimum_action_scene_cohesion,
        minimum_catalog_role_variety=minimum_catalog_role_variety,
        minimum_model_role_fit=minimum_model_role_fit,
    )
    operational_evaluation = calculate_dummy_operational_evaluation(summary, case, failure_category=failure_category)
    initial_timeline_observation_gap_accepted = (
        not bool(summary.passed)
        and summary_has_complete_objective_closure(summary)
        and case_has_only_initial_timeline_observation_gap(case.output_dir)
    )
    effective_passed = effective_case_passed(
        summary,
        minimum_action_scene_cohesion=minimum_action_scene_cohesion,
        minimum_catalog_role_variety=minimum_catalog_role_variety,
        minimum_model_role_fit=minimum_model_role_fit,
        case_dir=case.output_dir,
    )
    payload = {
        "questId": quest_id,
        "templateId": "",
        "source": "run-dummy-dynamic-quest-matrix",
        "targetName": text_value(getattr(case, "target", "")),
        "score": int(summary.evaluation_score),
        "minimumScore": minimum_score,
        "passed": bool(effective_passed),
        "completed": summary.completed >= summary.players,
        "players": int(summary.players),
        "okPlayers": int(summary.ok_players),
        "initialTimelineObservationGapAccepted": bool(initial_timeline_observation_gap_accepted),
        "playerDeaths": int(summary.player_deaths),
        "targetRemoved": int(summary.target_removed),
        "killConfirmed": int(summary.kill_confirmed),
        "branchChoiceExpected": bool(quest_case_expects_branch_choice(case)),
        "choiceSelected": int(summary.choice_selected),
        "choiceOutcomeScene": int(summary.choice_outcome_scene),
        "choiceConsequence": int(summary.choice_consequence),
        "worldSignalExpected": bool(quest_case_expects_world_signal(case)),
        "worldSignal": int(summary.world_signal),
        "presentationBeat": int(summary.presentation_beat),
        "presentationSpeakerVariety": int(summary.presentation_speaker_variety),
        "presentationStagedBeat": int(summary.presentation_staged_beat),
        "presentationStagedActorTotal": int(summary.presentation_staged_actor_total),
        "presentationStagedActorPeak": int(summary.presentation_staged_actor_peak),
        "presentationStagedActionVariety": int(summary.presentation_staged_action_variety),
        "presentationStagedRoleVariety": int(summary.presentation_staged_role_variety),
        "presentationStagedFormationVariety": int(summary.presentation_staged_formation_variety),
        "presentationStagedDelayedBeat": int(summary.presentation_staged_delayed_beat),
        "worldImpact": int(summary.world_impact),
        "worldImpactSummary": int(summary.world_impact_summary),
        "worldMemoryMarked": int(summary.world_memory_marked),
        "narrativeScene": int(summary.narrative_scene),
        "cinematicAction": int(summary.cinematic_action),
        "minNarrativeScenePerPlayer": int(summary.min_narrative_scene_per_player),
        "minPresentationBeatPerPlayer": int(summary.min_presentation_beat_per_player),
        "minCinematicActionPerPlayer": int(summary.min_cinematic_action_per_player),
        "cinematicVariety": int(summary.cinematic_variety),
        "cinematicMotionVariety": int(summary.cinematic_motion_variety),
        "cinematicStaggeredScene": int(summary.cinematic_staggered_scene),
        "cinematicObjectiveFocalScene": int(summary.cinematic_objective_focal_scene),
        "cinematicActorRoleVariety": int(summary.cinematic_actor_role_variety),
        "cinematicChoreographedScene": int(summary.cinematic_choreographed_scene),
        "cinematicInteractionScene": int(summary.cinematic_interaction_scene),
        "cinematicTacticVariety": int(summary.cinematic_tactic_variety),
        "cinematicActorInstances": int(summary.cinematic_actor_instances),
        "cinematicActorPeak": int(summary.cinematic_actor_peak),
        "cinematicActorSpawnSummary": int(summary.cinematic_actor_spawn_summary),
        "cinematicActorSpawnedTotal": int(summary.cinematic_actor_spawned_total),
        "cinematicActorSpawnedPeak": int(summary.cinematic_actor_spawned_peak),
        "cinematicActorSpawnFailed": int(summary.cinematic_actor_spawn_failed),
        "cinematicActorCleanupScheduled": int(summary.cinematic_actor_cleanup_scheduled),
        "cinematicActorMotionSummary": int(summary.cinematic_actor_motion_summary),
        "cinematicActorMotionCommands": int(summary.cinematic_actor_motion_commands),
        "cinematicActorMotionCommandsPeak": int(summary.cinematic_actor_motion_commands_peak),
        "cinematicActorMotionCommandsPerActorPeak": int(summary.cinematic_actor_motion_commands_per_actor_peak),
        "cinematicActorMotionSpawnedTotal": int(summary.cinematic_actor_motion_spawned_total),
        "cinematicActorEngagementSummary": int(summary.cinematic_actor_engagement_summary),
        "cinematicActorEngagementPairs": int(summary.cinematic_actor_engagement_pairs),
        "cinematicActorEngagementPairsPeak": int(summary.cinematic_actor_engagement_pairs_peak),
        "cinematicActorEngagedTotal": int(summary.cinematic_actor_engaged_total),
        "cinematicActorEngagementSpawnedTotal": int(summary.cinematic_actor_engagement_spawned_total),
        "cinematicActorBudgetScore": int(summary.cinematic_actor_budget_score),
        "actionSceneCohesionScore": int(summary.action_scene_cohesion_score),
        "cinematicCatalogRoleVariety": int(summary.cinematic_catalog_role_variety),
        "cinematicModelRoleFitScore": int(summary.cinematic_model_role_fit_score),
        "cinematicMarkerScene": int(summary.cinematic_marker_scene),
        "cinematicMarkerVariety": int(summary.cinematic_marker_variety),
        "cinematicPhaseCoverage": int(summary.cinematic_phase_coverage),
        "cinematicSetpiecePhaseCoverage": int(summary.cinematic_setpiece_phase_coverage),
        "cinematicMarkerPhaseCoverage": int(summary.cinematic_marker_phase_coverage),
        "cinematicStoryChain": int(summary.cinematic_story_chain),
        "sceneDirectorBeat": int(summary.scene_director_beat),
        "sceneBeatOutcome": int(summary.scene_beat_outcome),
        "sceneChoreographyPhase": int(summary.scene_choreography_phase),
        "sceneActorExchange": int(summary.scene_actor_exchange),
        "sceneExchangeOutcome": int(summary.scene_exchange_outcome),
        "sceneOutcomeSignal": int(summary.scene_outcome_signal),
        "sceneConsequence": int(summary.scene_consequence),
        "sceneWorldSignal": int(summary.scene_world_signal),
        "worldSignalSceneShift": int(summary.world_signal_scene_shift),
        "worldSignalSceneShiftDetail": int(summary.world_signal_scene_shift_detail),
        "worldSignalSceneShiftPhaseVariety": int(summary.world_signal_scene_shift_phase_variety),
        "worldSignalSceneShiftSourceVariety": int(summary.world_signal_scene_shift_source_variety),
        "worldSignalSceneShiftTargetVariety": int(summary.world_signal_scene_shift_target_variety),
        "cinematicCleanup": int(summary.cinematic_cleanup),
        "followupHuntStart": int(summary.followup_hunt_start),
        "cinematicDensityScore": int(summary.cinematic_density_score),
        "storyContinuityScore": int(summary.story_continuity_score),
        "storyArchetypeScore": int(summary.story_archetype_score),
        "skyrimGradeScore": int(summary.skyrim_grade_score),
        "operationalEvaluation": operational_evaluation,
        "failureCategory": failure_category,
        "elapsedSeconds": float(summary.elapsed_seconds),
        "details": str(case.output_dir),
    }
    output_path = case.output_dir / "dynamic-quest-evaluation.json"
    setup_failure = (
        not effective_passed
        and summary.ok_players <= 0
        and case_has_setup_failure_action(case.output_dir)
    )
    if (setup_failure or failure_category == "infrastructure") and not bool(getattr(args, "dynamic_quest_submit_setup_failure_evaluation", False)):
        output_path.write_text(
            json.dumps(
                {
                    "request": payload,
                    "skipped": True,
                    "reason": "infrastructure_or_setup_failure",
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return

    try:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            build_dynamic_quest_evaluation_api_url(args),
            data=data,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=10) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
        output_path.write_text(
            json.dumps({"request": payload, "response": response_payload}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception as exc:  # noqa: BLE001 - keep the matrix result visible even if the API is unavailable.
        output_path.write_text(
            json.dumps({"request": payload, "error": str(exc)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def run_matrix(args: argparse.Namespace) -> int:
    args.output_root.mkdir(parents=True, exist_ok=True)
    commands_path = args.output_root / "commands.txt"
    failures = 0
    command_lines: list[str] = []

    for case in build_cases(args):
        case.output_dir.mkdir(parents=True, exist_ok=True)
        runtime_case = case
        start_position = None
        if should_resolve_live_case(args):
            try:
                runtime_case, start_position = resolve_live_case(case, args)
            except Exception as exc:  # noqa: BLE001 - matrix should keep reporting case failures.
                (case.output_dir / "matrix-summary.md").write_text(
                    f"# {case.name}\n\nfailed to resolve live dynamic quest binding: {exc}\n",
                    encoding="utf-8",
                )
                failures += 1
                continue

        if not case.accounts_csv.exists():
            command = build_behavior_command(runtime_case, args)
            command_lines.append(shlex.join(command))
            if args.dry_run:
                continue

            (case.output_dir / "matrix-summary.md").write_text(
                f"# {case.name}\n\nmissing accounts CSV: {case.accounts_csv}\n",
                encoding="utf-8",
            )
            failures += 1
            continue

        if not args.dry_run:
            try:
                selected_accounts = prepare_case_accounts_csv(
                    runtime_case,
                    args,
                    quest_id=getattr(runtime_case, "quest_id", ""),
                )
                runtime_case = replace(runtime_case, accounts_csv=selected_accounts)
            except Exception as exc:  # noqa: BLE001 - matrix should keep reporting case failures.
                (case.output_dir / "matrix-summary.md").write_text(
                    f"# {case.name}\n\nfailed to prepare accounts CSV: {exc}\n",
                    encoding="utf-8",
                )
                failures += 1
                continue

        command = build_behavior_command(runtime_case, args)
        command_lines.append(shlex.join(command))
        if args.dry_run:
            continue

        if args.reset_start_positions:
            try:
                reset_case_start_positions(runtime_case, args, start_position)
            except Exception as exc:  # noqa: BLE001 - matrix should keep reporting case failures.
                (case.output_dir / "matrix-summary.md").write_text(
                    f"# {case.name}\n\nfailed to reset start positions: {exc}\n",
                    encoding="utf-8",
                )
                failures += 1
                continue

        # The client may exit non-zero when its local timeline window misses early
        # events. The enriched server API summary below is the authoritative result.
        subprocess.run(command)

        if bool(getattr(args, "dynamic_quest_cleanup_active_after_case", True)):
            try:
                _, selected_rows = read_account_csv(runtime_case.accounts_csv)
                cleanup_results = cleanup_active_dynamic_quest_progress_for_accounts(
                    args,
                    [text_value(row.get("username")) for row in selected_rows],
                    reason="dynamic_quest_matrix_case_cleanup",
                )
                if cleanup_results:
                    (case.output_dir / "dynamic-quest-cleanup.json").write_text(
                        json.dumps(cleanup_results, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
            except Exception as exc:  # noqa: BLE001 - cleanup failure should not hide the case result.
                (case.output_dir / "dynamic-quest-cleanup.json").write_text(
                    json.dumps({"error": str(exc)}, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

        summary = summarize_case(
            case.output_dir,
            require_followup_hunt=case_followup_growth_target(runtime_case, args),
        )
        summary = enrich_summary_from_dynamic_quest_api(
            runtime_case,
            args,
            summary,
            require_followup_hunt=case_followup_growth_target(runtime_case, args),
        )
        summary = finalize_case_summary_scores(
            replace(summary, story_archetype_score=calculate_story_archetype_score(summary, runtime_case)),
            require_followup_hunt=case_followup_growth_target(runtime_case, args),
        )
        minimum_action_scene_cohesion = min_action_scene_cohesion_from_args(args)
        minimum_catalog_role_variety = min_cinematic_catalog_role_variety_from_args(args)
        minimum_model_role_fit = min_cinematic_model_role_fit_from_args(args)
        write_case_summary(
            runtime_case,
            summary,
            minimum_action_scene_cohesion=minimum_action_scene_cohesion,
            minimum_catalog_role_variety=minimum_catalog_role_variety,
            minimum_model_role_fit=minimum_model_role_fit,
        )
        submit_dynamic_quest_evaluation(runtime_case, args, summary)
        if not effective_case_passed(
            summary,
            minimum_action_scene_cohesion=minimum_action_scene_cohesion,
            minimum_catalog_role_variety=minimum_catalog_role_variety,
            minimum_model_role_fit=minimum_model_role_fit,
            case_dir=runtime_case.output_dir,
        ):
            failures += 1

    commands_path.write_text("\n".join(command_lines) + ("\n" if command_lines else ""), encoding="utf-8")
    return 1 if failures else 0


def main() -> int:
    return run_matrix(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
