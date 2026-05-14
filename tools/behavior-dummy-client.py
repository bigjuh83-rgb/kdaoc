#!/usr/bin/env python3
"""Behavior dummy runner for OpenDAoC local stress/smoke testing."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import random
import sys
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path


def load_headless_client_class():
    module_path = Path(__file__).with_name("headless-daoc-client.py")
    spec = importlib.util.spec_from_file_location("headless_daoc_client", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.HeadlessDaocClient


def load_dummy_pathing_module():
    module_path = Path(__file__).with_name("dummy_pathing.py")
    spec = importlib.util.spec_from_file_location("dummy_pathing", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HeadlessDaocClient = load_headless_client_class()
dummy_pathing = load_dummy_pathing_module()
PathFollower = dummy_pathing.PathFollower
PathGraph = dummy_pathing.PathGraph
PathPoint = dummy_pathing.PathPoint
PathSafety = dummy_pathing.PathSafety
path_distance = dummy_pathing.distance

DEFAULT_COMMANDS = ["/mobgrowth status", "/worldnews", "/worldai jobs"]
REALM_NAMES = {1: "Albion", 2: "Midgard", 3: "Hibernia"}
REALM_IDS_BY_NAME = {name.lower(): realm_id for realm_id, name in REALM_NAMES.items()}
PATH_GRAPH_CACHE: dict[str, object] = {}
PATH_GRAPH_CACHE_LOCK = threading.Lock()
DEFAULT_SOCIAL_LINES = [
    "안녕하세요",
    "사냥 자리 지나갈게요",
    "조심하세요",
    "몹이 좀 아프네요",
    "잠깐 쉬었다 갈게요",
]
DEFAULT_PLAYER_GREET_LINES = ["안녕하세요", "수고하세요", "지나갈게요"]
DEFAULT_EMOTE_COMMANDS = ["/wave", "/bow", "/cheer", "/sit"]


@dataclass(frozen=True)
class DummyAccount:
    username: str
    password: str
    realm: int
    char_index: int


@dataclass
class DummyResult:
    username: str
    ok: bool
    actions: int = 0
    rounds: int = 0
    successful_rounds: int = 0
    elapsed: float = 0.0
    error: str = ""
    metrics: list["RoundMetric"] | None = None


@dataclass
class RoundMetric:
    username: str
    round_index: int
    ok: bool
    actions: int
    elapsed: float
    error: str
    action_counts: dict[str, int] | None = None
    combat_metrics: list["CombatMetric"] | None = None
    persona: str = ""
    movement_failures: list["MovementFailure"] | None = None


@dataclass(frozen=True)
class MovementFailure:
    context: str
    reason: str
    destination_key: str
    start_x: int
    start_y: int
    start_z: int
    goal_x: int
    goal_y: int
    goal_z: int


@dataclass
class CombatMetric:
    target_id: int
    target_name: str
    target_level: int
    outcome: str
    duration: float
    attacks: int = 0
    skills: int = 0
    start_distance: float = 0.0
    end_distance: float = 0.0


@dataclass(frozen=True)
class Waypoint:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class MovementDestination:
    key: str
    x: int
    y: int
    z: int


@dataclass
class MovementOutcome:
    moved: bool
    arrived: bool
    actions: int = 0
    reason: str = ""


@dataclass
class PathMovementState:
    graph: object | None
    region: int
    safety: object
    follower: object = field(default_factory=PathFollower)
    destination_key: str = ""
    last_plan_at: float = 0.0
    last_reason: str = ""


@dataclass(frozen=True)
class NavPathResult:
    ok: bool
    status: str
    points: list[object]
    line_of_sight: bool = False
    snapped_start: object | None = None
    snapped_end: object | None = None
    floor: object | None = None

    def __iter__(self):
        yield self.ok
        yield self.status
        yield self.points


@dataclass(frozen=True)
class AiPersona:
    social_chance_multiplier: float = 1.0
    player_greet_chance_multiplier: float = 1.0
    emote_chance_multiplier: float = 1.0
    long_rest_chance_multiplier: float = 1.0
    rest_chance_multiplier: float = 1.0
    target_examine_multiplier: float = 1.0
    player_follow_interval_multiplier: float = 1.0
    player_follow_distance_multiplier: float = 1.0
    follow_player_max_distance_multiplier: float = 1.0
    look_around_interval_multiplier: float = 1.0
    think_window_multiplier: float = 1.0


AI_PERSONAS = {
    "quiet-grinder": AiPersona(
        social_chance_multiplier=0.35,
        player_greet_chance_multiplier=0.45,
        emote_chance_multiplier=0.40,
        long_rest_chance_multiplier=0.65,
        rest_chance_multiplier=0.75,
        target_examine_multiplier=0.70,
        player_follow_interval_multiplier=1.35,
        player_follow_distance_multiplier=1.10,
        look_around_interval_multiplier=1.25,
        think_window_multiplier=0.85,
    ),
    "social-roamer": AiPersona(
        social_chance_multiplier=2.00,
        player_greet_chance_multiplier=2.20,
        emote_chance_multiplier=1.60,
        long_rest_chance_multiplier=1.25,
        rest_chance_multiplier=1.10,
        target_examine_multiplier=1.40,
        player_follow_interval_multiplier=0.70,
        player_follow_distance_multiplier=1.00,
        follow_player_max_distance_multiplier=1.20,
        look_around_interval_multiplier=0.80,
        think_window_multiplier=1.15,
    ),
    "cautious-hunter": AiPersona(
        social_chance_multiplier=0.75,
        player_greet_chance_multiplier=0.85,
        emote_chance_multiplier=0.80,
        long_rest_chance_multiplier=1.45,
        rest_chance_multiplier=1.50,
        target_examine_multiplier=1.65,
        player_follow_interval_multiplier=1.10,
        player_follow_distance_multiplier=1.35,
        look_around_interval_multiplier=0.90,
        think_window_multiplier=1.35,
    ),
    "helpful-follower": AiPersona(
        social_chance_multiplier=1.20,
        player_greet_chance_multiplier=1.50,
        emote_chance_multiplier=1.20,
        long_rest_chance_multiplier=0.90,
        rest_chance_multiplier=0.95,
        target_examine_multiplier=1.20,
        player_follow_interval_multiplier=0.55,
        player_follow_distance_multiplier=0.80,
        follow_player_max_distance_multiplier=1.35,
        look_around_interval_multiplier=0.75,
        think_window_multiplier=1.00,
    ),
}


class PartyState:
    def __init__(self, leader_name: str, member_names: list[str]) -> None:
        self.leader_name = leader_name
        self.member_names = member_names
        self.lock = threading.Lock()
        self.leader_session_id = 0
        self.leader_x = 0
        self.leader_y = 0
        self.leader_z = 0
        self.leader_heading = 0
        self.leader_target_id = 0
        self.leader_target_x = 0
        self.leader_target_y = 0
        self.leader_target_z = 0
        self.updated_at = 0.0

    def update_leader(self, client, target=None) -> None:
        with self.lock:
            self.leader_session_id = client.session_id
            self.leader_x = client.x
            self.leader_y = client.y
            self.leader_z = client.z
            self.leader_heading = client.heading

            if target is not None:
                self.leader_target_id = target.object_id
                self.leader_target_x = target.x
                self.leader_target_y = target.y
                self.leader_target_z = target.z

            self.updated_at = time.monotonic()

    def snapshot(self) -> dict[str, int | float | str]:
        with self.lock:
            return {
                "leader_name": self.leader_name,
                "leader_session_id": self.leader_session_id,
                "leader_x": self.leader_x,
                "leader_y": self.leader_y,
                "leader_z": self.leader_z,
                "leader_heading": self.leader_heading,
                "leader_target_id": self.leader_target_id,
                "leader_target_x": self.leader_target_x,
                "leader_target_y": self.leader_target_y,
                "leader_target_z": self.leader_target_z,
                "updated_at": self.updated_at,
            }


def character_name_from_account(username: str) -> str:
    if username.lower().startswith("dummy"):
        return "Dummy" + username[5:]

    return username[:1].upper() + username[1:]


def choose_hunter_target(
    client,
    rng: random.Random,
    args: argparse.Namespace,
    rejected_targets: dict[int, float],
    rejected_target_kinds: dict[tuple[str, int], float],
    now: float,
):
    max_level = args.max_target_level if args.max_target_level >= 0 else args.player_level + args.max_target_level_delta
    ideal_level = args.ideal_target_level or args.player_level
    prefer_tokens = [token.strip().lower() for token in args.prefer_target_name.split(",") if token.strip()]
    avoid_tokens = [token.strip().lower() for token in args.avoid_target_name.split(",") if token.strip()]
    candidates = [
        npc
        for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=args.include_peace_npcs)
        if rejected_targets.get(npc.object_id, 0.0) <= now
        and rejected_target_kinds.get((npc.name.lower(), npc.level), 0.0) <= now
        and npc.level >= args.min_target_level
        and npc.level <= max_level
        and (args.max_target_distance <= 0 or client.distance_to(npc) <= args.max_target_distance)
        and not any(token in npc.name.lower() for token in avoid_tokens)
    ]

    if not candidates:
        return None

    nearest_candidates = sorted(candidates, key=lambda npc: client.distance_to(npc))
    pool = nearest_candidates[: max(args.target_pool, 1)]

    if args.target_selection == "random":
        return rng.choice(pool)

    def score(npc) -> float:
        distance = client.distance_to(npc)
        level_delta = abs(npc.level - ideal_level)
        value = 1000.0
        value -= level_delta * args.target_level_weight
        value -= distance / max(args.target_distance_weight, 1.0)

        if npc.level < args.min_target_level:
            value -= 500.0

        if prefer_tokens and any(token in npc.name.lower() for token in prefer_tokens):
            value += args.prefer_target_bonus

        value += rng.uniform(0.0, args.target_randomness)
        return value

    if args.target_selection == "nearest":
        return min(pool, key=lambda npc: client.distance_to(npc))

    return max(pool, key=score)


def choose_follow_player(client, args: argparse.Namespace):
    candidates = client.visible_players(max_age=args.player_state_max_age)

    if args.follow_player_max_distance > 0:
        candidates = [player for player in candidates if client.distance_to(player) <= args.follow_player_max_distance]

    if not candidates:
        return None

    name_token = args.follow_player_name.strip().lower()

    if name_token:
        for player in candidates:
            if name_token in player.name.lower():
                return player

    return min(candidates, key=lambda player: client.distance_to(player))


def choose_greet_player(
    client,
    args: argparse.Namespace,
    greeted_until: dict[int, float],
    now: float,
):
    candidates = [
        player
        for player in client.visible_players(max_age=args.player_state_max_age)
        if client.distance_to(player) <= args.player_greet_distance
        and greeted_until.get(player.object_id, 0.0) <= now
    ]

    if not candidates:
        return None

    return min(candidates, key=lambda player: client.distance_to(player))


def choose_ai_persona_name(args: argparse.Namespace, account: DummyAccount, index: int) -> str:
    if not args.ai_player or args.ai_persona == "none":
        return "none"

    if args.ai_persona != "auto":
        return args.ai_persona

    digest = hashlib.sha256(f"{args.seed}:{index}:{account.username}".encode("utf-8")).digest()
    names = sorted(AI_PERSONAS)
    return names[int.from_bytes(digest[:4], "big") % len(names)]


def clamp_chance(value: float) -> float:
    return max(0.0, min(1.0, value))


def apply_ai_persona(args: argparse.Namespace, account: DummyAccount, index: int) -> argparse.Namespace:
    persona_name = choose_ai_persona_name(args, account, index)
    tuned = argparse.Namespace(**vars(args))
    tuned.ai_persona_name = persona_name

    if persona_name == "none":
        return tuned

    persona = AI_PERSONAS[persona_name]
    tuned.social_chance = clamp_chance(args.social_chance * persona.social_chance_multiplier)
    tuned.player_greet_chance = clamp_chance(args.player_greet_chance * persona.player_greet_chance_multiplier)
    tuned.emote_chance = clamp_chance(args.emote_chance * persona.emote_chance_multiplier)
    tuned.long_rest_chance = clamp_chance(args.long_rest_chance * persona.long_rest_chance_multiplier)
    tuned.rest_chance = clamp_chance(args.rest_chance * persona.rest_chance_multiplier)
    tuned.target_examine_chance = clamp_chance(args.target_examine_chance * persona.target_examine_multiplier)
    tuned.player_follow_interval = max(0.5, args.player_follow_interval * persona.player_follow_interval_multiplier)
    tuned.player_follow_distance = max(150.0, args.player_follow_distance * persona.player_follow_distance_multiplier)
    tuned.follow_player_max_distance = max(
        tuned.player_follow_distance,
        args.follow_player_max_distance * persona.follow_player_max_distance_multiplier,
    )
    tuned.look_around_interval = max(2.0, args.look_around_interval * persona.look_around_interval_multiplier)
    tuned.think_min = max(0.0, args.think_min * persona.think_window_multiplier)
    tuned.think_max = max(tuned.think_min, args.think_max * persona.think_window_multiplier)
    return tuned


def apply_behavior_profile(args: argparse.Namespace) -> None:
    if args.behavior_profile == "custom":
        return

    profiles = {
        "solo-melee": {
            "hunter": True,
            "combat": True,
            "move": True,
            "wander": True,
            "use_skills": True,
            "auto_release_on_death": True,
            "stick_to_target_chance": 0.99,
            "rest_chance": 0.05,
            "think_min": 0.15,
            "think_max": 0.55,
        },
        "cautious-solo": {
            "hunter": True,
            "combat": True,
            "move": True,
            "wander": True,
            "use_skills": True,
            "auto_release_on_death": True,
            "stick_to_target_chance": 0.995,
            "flee_health_percent": 35,
            "flee_duration": 4.0,
            "max_target_level_delta": 1,
            "rest_chance": 0.12,
            "think_min": 0.35,
            "think_max": 1.0,
        },
        "pve-casual": {
            "hunter": True,
            "combat": True,
            "move": True,
            "wander": True,
            "use_skills": True,
            "auto_release_on_death": True,
            "stick_to_target_chance": 0.99,
            "flee_health_percent": 28,
            "flee_duration": 5.0,
            "target_selection": "smart",
            "target_pool": 4,
            "target_timeout": 60.0,
            "rest_chance": 0.10,
            "think_min": 0.35,
            "think_max": 1.35,
        },
        "party-tank": {
            "hunter": True,
            "combat": True,
            "move": True,
            "wander": True,
            "use_skills": True,
            "auto_release_on_death": True,
            "stick_to_target_chance": 0.98,
            "attack_range": 120,
            "skill_interval": 3.5,
            "rest_chance": 0.03,
        },
        "party-dps": {
            "hunter": True,
            "combat": True,
            "move": True,
            "wander": True,
            "use_skills": True,
            "auto_release_on_death": True,
            "stick_to_target_chance": 0.98,
            "attack_range": 120,
            "skill_interval": 2.3,
            "rest_chance": 0.04,
        },
    }

    for name, value in profiles[args.behavior_profile].items():
        setattr(args, name.replace("-", "_"), value)


def resolve_action_rotation(args: argparse.Namespace, party_slot: int) -> str:
    if args.action_rotation != "auto":
        return args.action_rotation

    if args.party_size > 1 and args.party_role_strategy == "mixed":
        if party_slot == 0:
            return "melee-basic"
        if party_slot == args.party_size - 1:
            return "healer-support"
        if party_slot % 2 == 0:
            return "caster-basic"
        return "melee-burst"

    if args.behavior_profile == "party-dps":
        return "melee-burst"
    if args.behavior_profile == "cautious-solo":
        return "hybrid"
    return "melee-basic"


def perform_rotation_action(client, rng: random.Random, args: argparse.Namespace, rotation: str, distance: float) -> str | None:
    if rotation == "none":
        return None

    target_in_view = distance <= max(args.attack_range, args.spell_range)

    if rotation == "melee-basic":
        if distance > args.attack_range:
            return None
        client.use_skill(rng.choice(args.skill_indexes), skill_type=args.skill_type)
        return "skill"

    if rotation == "melee-burst":
        if distance > args.attack_range:
            return None
        client.use_skill(rng.choice(args.skill_indexes), skill_type=args.skill_type)
        return "burst_skill"

    if rotation == "caster-basic":
        if distance > args.spell_range:
            return None
        client.use_spell(rng.choice(args.spell_levels), spell_line_index=args.spell_line_index, target_in_view=target_in_view)
        return "spell"

    if rotation == "healer-support":
        if client.health_percent <= args.healer_self_health_percent:
            client.use_spell(rng.choice(args.heal_spell_levels), spell_line_index=args.heal_spell_line_index, target_in_view=False)
            return "self_heal_spell"

        if args.support_spell_chance > 0 and rng.random() < args.support_spell_chance:
            client.use_spell(rng.choice(args.spell_levels), spell_line_index=args.spell_line_index, target_in_view=target_in_view)
            return "support_spell"

        return None

    if rotation == "hybrid":
        if distance <= args.attack_range and rng.random() < args.hybrid_melee_chance:
            client.use_skill(rng.choice(args.skill_indexes), skill_type=args.skill_type)
            return "skill"

        if distance <= args.spell_range:
            client.use_spell(rng.choice(args.spell_levels), spell_line_index=args.spell_line_index, target_in_view=target_in_view)
            return "spell"

    return None


def melee_stop_distance(args: argparse.Namespace) -> float:
    return max(args.minimum_melee_stop_distance, args.attack_range - args.melee_range_buffer)


def smooth_movement_step(args: argparse.Namespace) -> float:
    return max(1.0, args.movement_speed * args.smooth_move_interval)


def parse_int_list(value: str) -> list[int]:
    numbers: list[int] = []

    for part in value.split(","):
        part = part.strip()

        if not part:
            continue

        numbers.append(int(part))

    if not numbers:
        raise ValueError("empty integer list")

    return numbers


def parse_text_list(value: str) -> list[str]:
    return [part.strip() for part in value.split("|") if part.strip()]


def parse_waypoints(value: str) -> list[Waypoint]:
    waypoints: list[Waypoint] = []

    for part in value.split("|"):
        part = part.strip()

        if not part:
            continue

        pieces = [piece.strip() for piece in part.split(",")]

        if len(pieces) != 3:
            raise ValueError(f"invalid waypoint '{part}', expected x,y,z")

        waypoints.append(Waypoint(int(pieces[0]), int(pieces[1]), int(pieces[2])))

    return waypoints


def resolve_path_graph_path(value: str) -> Path:
    graph_path = Path(value)

    if graph_path.is_absolute() and graph_path.exists():
        return graph_path

    candidates = [
        Path.cwd() / graph_path,
        Path(__file__).resolve().parents[1] / graph_path,
        Path(__file__).resolve().parent / graph_path,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return graph_path


def load_path_graph(value: str):
    if not value:
        return None

    graph_path = resolve_path_graph_path(value)
    cache_key = str(graph_path.resolve()) if graph_path.exists() else str(graph_path)

    with PATH_GRAPH_CACHE_LOCK:
        if cache_key not in PATH_GRAPH_CACHE:
            PATH_GRAPH_CACHE[cache_key] = PathGraph.from_file(graph_path)

        return PATH_GRAPH_CACHE[cache_key]


def build_nav_path_url(args: argparse.Namespace, region: int, start: object, goal: object) -> str:
    query = urllib.parse.urlencode(
        {
            "region": region,
            "startX": int(start.x),
            "startY": int(start.y),
            "startZ": int(start.z),
            "endX": int(goal.x),
            "endY": int(goal.y),
            "endZ": int(goal.z),
            "maxNodes": args.nav_api_max_nodes,
            "snap": "true" if args.nav_api_snap else "false",
            "avoidBlockingDoors": "true" if args.nav_api_avoid_blocking_doors else "false",
        }
    )
    return f"{args.nav_api_url.rstrip('/')}/api/dummy/nav/path?{query}"


def parse_nav_point(value: object) -> object | None:
    if not isinstance(value, dict):
        return None

    try:
        return PathPoint(int(value["x"]), int(value["y"]), int(value["z"]))
    except (KeyError, TypeError, ValueError):
        return None


def same_path_point(left: object, right: object) -> bool:
    return int(left.x) == int(right.x) and int(left.y) == int(right.y) and int(left.z) == int(right.z)


def parse_nav_path_response(payload: dict[str, object]) -> NavPathResult:
    ok = bool(payload.get("ok"))
    status = str(payload.get("status", "Unknown"))
    raw_points = payload.get("points", [])
    snapped_start = parse_nav_point(payload.get("snappedStart"))
    snapped_end = parse_nav_point(payload.get("snappedEnd"))
    floor = parse_nav_point(payload.get("floor"))

    if not ok or not isinstance(raw_points, list):
        return NavPathResult(False, status, [], floor=floor, snapped_start=snapped_start, snapped_end=snapped_end)

    points: list[object] = []
    raw_point_count = 0

    for raw_point in raw_points:
        point = parse_nav_point(raw_point)

        if point is None:
            continue

        raw_point_count += 1
        points.append(point)

    if snapped_start is not None and (not points or not same_path_point(points[0], snapped_start)):
        points.insert(0, snapped_start)

    if snapped_end is not None and raw_point_count == 0 and not bool(payload.get("lineOfSight")):
        points.clear()
    elif snapped_end is not None and (not points or not same_path_point(points[-1], snapped_end)):
        points.append(snapped_end)

    return NavPathResult(
        bool(points),
        status,
        points,
        line_of_sight=bool(payload.get("lineOfSight")),
        snapped_start=snapped_start,
        snapped_end=snapped_end,
        floor=floor,
    )


def request_nav_path(args: argparse.Namespace, region: int, start: object, goal: object) -> tuple[bool, str, list[object]]:
    if not args.nav_api_url:
        return False, "disabled", []

    request = urllib.request.Request(build_nav_path_url(args, region, start, goal), headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=args.nav_api_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return False, f"nav api error: {exc}", []

    if not isinstance(payload, dict):
        return False, "nav api returned a non-object response", []

    return parse_nav_path_response(payload)


def nav_segment_allowed(args: argparse.Namespace, region: int, start: object, goal: object) -> tuple[bool, str]:
    if not args.nav_api_url or not getattr(args, "nav_segment_validate", False):
        return True, "disabled"

    ok, reason, _points = request_nav_path(args, region, start, goal)
    return ok, reason


def graph_can_fallback_from_nav_failure(path_state: PathMovementState, reason: str) -> bool:
    return path_state.graph is not None and reason in {"NavmeshUnavailable", "ZoneNotFound", "CrossZonePathUnsupported"}


def build_path_safety(args: argparse.Namespace):
    return PathSafety(
        max_edge_length=args.path_max_edge_length,
        max_direct_distance=args.path_last_mile_distance,
        max_height_delta=args.path_max_height_delta,
        allow_water=args.path_allow_water,
        allow_closed_door=args.path_allow_closed_door,
        allow_keep_door=args.path_allow_keep_door,
        allow_cliff=args.path_allow_cliff,
    )


def build_path_movement_state(args: argparse.Namespace, client) -> PathMovementState:
    region = args.path_region or client.zone_id or 0

    if args.disable_graph_pathing or not args.path_graph:
        return PathMovementState(None, region, build_path_safety(args))

    return PathMovementState(load_path_graph(args.path_graph), region, build_path_safety(args))


def destination_from_actor(kind: str, actor, *, bucket: int = 250) -> MovementDestination:
    return MovementDestination(
        key=f"{kind}:{getattr(actor, 'object_id', 0)}:{int(actor.x // bucket)}:{int(actor.y // bucket)}:{int(actor.z // bucket)}",
        x=int(actor.x),
        y=int(actor.y),
        z=int(actor.z),
    )


def destination_from_point(kind: str, x: int, y: int, z: int, *, bucket: int = 250) -> MovementDestination:
    return MovementDestination(
        key=f"{kind}:{int(x // bucket)}:{int(y // bucket)}:{int(z // bucket)}",
        x=int(x),
        y=int(y),
        z=int(z),
    )


def move_towards_destination(
    client,
    destination: MovementDestination,
    *,
    step: float,
    stop_distance: float,
    args: argparse.Namespace,
    path_state: PathMovementState,
    action_counts: dict[str, int],
) -> MovementOutcome:
    if path_state.graph is None and not args.nav_api_url:
        moved = client.move_towards_position(destination.x, destination.y, destination.z, step=step, stop_distance=stop_distance)
        return MovementOutcome(moved=moved, arrived=not moved)

    graph = path_state.graph
    safety = path_state.safety
    current = PathPoint(int(client.x), int(client.y), int(client.z))
    goal = PathPoint(destination.x, destination.y, destination.z)
    direct_distance = path_distance(current, goal)
    actions = 0

    if direct_distance <= stop_distance:
        client.move_towards_position(goal.x, goal.y, goal.z, step=0.0, stop_distance=stop_distance)
        actions += add_action(action_counts, "path_arrived")
        return MovementOutcome(moved=False, arrived=True, actions=actions)

    if direct_path_allowed_for_state(path_state, current, goal, args.path_last_mile_distance):
        segment_ok, segment_reason = nav_segment_allowed(args, path_state.region, current, goal)

        if not segment_ok and not graph_can_fallback_from_nav_failure(path_state, segment_reason):
            client.send_position_update(speed=0.0, target_in_view=False)
            actions += add_action(action_counts, "nav_segment_blocked")
            return MovementOutcome(moved=False, arrived=False, actions=actions, reason=segment_reason)

        moved = client.move_towards_position(goal.x, goal.y, goal.z, step=step, stop_distance=stop_distance)
        actions += add_action(action_counts, "path_last_mile" if moved else "path_arrived")
        return MovementOutcome(moved=moved, arrived=not moved, actions=actions)

    needs_plan = (
        path_state.destination_key != destination.key
        or not getattr(path_state.follower, "route", [])
    )

    if needs_plan:
        now = time.monotonic()

        if (
            path_state.destination_key == destination.key
            and not getattr(path_state.follower, "route", [])
            and path_state.last_plan_at > 0
            and now - path_state.last_plan_at < args.path_replan_interval
        ):
            client.send_position_update(speed=0.0, target_in_view=False)
            actions += add_action(action_counts, "path_replan_wait")
            return MovementOutcome(moved=False, arrived=False, actions=actions, reason=path_state.last_reason)

        path_state.destination_key = destination.key
        path_state.last_plan_at = now

        if args.nav_api_url:
            nav_ok, nav_reason, nav_points = request_nav_path(args, path_state.region, current, goal)
            path_state.last_reason = nav_reason

            if nav_ok:
                path_state.follower.set_route(nav_points)
                actions += add_action(action_counts, "nav_path_plan")
            else:
                actions += add_action(action_counts, "nav_path_failed")

        if not getattr(path_state.follower, "route", []) and graph is not None:
            route = graph.route_between_points(
                path_state.region,
                current,
                goal,
                max_node_distance=args.path_max_node_distance,
                safety=safety,
            )
            path_state.last_reason = route.reason

            if route.ok:
                path_state.follower.set_route(route.nodes)
                actions += add_action(action_counts, "path_plan")

        if not getattr(path_state.follower, "route", []):
            path_state.follower.clear()
            client.send_position_update(speed=0.0, target_in_view=False)
            actions += add_action(action_counts, "path_failed")
            return MovementOutcome(moved=False, arrived=False, actions=actions, reason=path_state.last_reason)

    next_point = path_state.follower.next_point(current, args.path_node_arrival_distance)

    if next_point is None:
        if direct_path_allowed_for_state(path_state, current, goal, args.path_last_mile_distance):
            segment_ok, segment_reason = nav_segment_allowed(args, path_state.region, current, goal)

            if not segment_ok and not graph_can_fallback_from_nav_failure(path_state, segment_reason):
                path_state.destination_key = ""
                path_state.last_reason = segment_reason
                client.send_position_update(speed=0.0, target_in_view=False)
                actions += add_action(action_counts, "nav_segment_blocked")
                return MovementOutcome(moved=False, arrived=False, actions=actions, reason=segment_reason)

            moved = client.move_towards_position(goal.x, goal.y, goal.z, step=step, stop_distance=stop_distance)
            actions += add_action(action_counts, "path_last_mile" if moved else "path_arrived")
            return MovementOutcome(moved=moved, arrived=not moved, actions=actions)

        path_state.destination_key = ""
        client.send_position_update(speed=0.0, target_in_view=False)
        actions += add_action(action_counts, "path_hold")
        return MovementOutcome(moved=False, arrived=False, actions=actions, reason="route ended before last mile")

    if not direct_path_allowed_for_state(path_state, current, next_point, args.path_max_edge_length):
        path_state.follower.clear()
        path_state.destination_key = ""
        client.send_position_update(speed=0.0, target_in_view=False)
        actions += add_action(action_counts, "path_blocked")
        return MovementOutcome(moved=False, arrived=False, actions=actions, reason="next graph step failed safety check")

    segment_ok, segment_reason = nav_segment_allowed(args, path_state.region, current, next_point)

    if not segment_ok and not graph_can_fallback_from_nav_failure(path_state, segment_reason):
        path_state.follower.clear()
        path_state.destination_key = ""
        path_state.last_reason = segment_reason
        client.send_position_update(speed=0.0, target_in_view=False)
        actions += add_action(action_counts, "nav_segment_blocked")
        return MovementOutcome(moved=False, arrived=False, actions=actions, reason=segment_reason)

    moved = client.move_towards_position(next_point.x, next_point.y, next_point.z, step=step, stop_distance=0.0)
    actions += add_action(action_counts, "path_step" if moved else "path_waypoint_reached")
    return MovementOutcome(moved=moved, arrived=False, actions=actions)


def record_movement_failure(
    failures: list[MovementFailure],
    client,
    destination: MovementDestination,
    outcome: MovementOutcome,
    context: str,
    *,
    limit: int = 25,
) -> None:
    if outcome.moved or outcome.arrived or not outcome.reason or len(failures) >= limit:
        return

    failures.append(
        MovementFailure(
            context=context,
            reason=outcome.reason,
            destination_key=destination.key,
            start_x=int(client.x),
            start_y=int(client.y),
            start_z=int(client.z),
            goal_x=int(destination.x),
            goal_y=int(destination.y),
            goal_z=int(destination.z),
        )
    )


def direct_path_allowed_for_state(path_state: PathMovementState, start: object, goal: object, max_distance: float) -> bool:
    if path_state.graph is not None:
        return path_state.graph.direct_path_allowed(path_state.region, start, goal, path_state.safety, max_distance=max_distance)

    return path_distance(start, goal) <= max_distance and abs(start.z - goal.z) <= path_state.safety.max_height_delta


def build_live_api_url(args: argparse.Namespace) -> str:
    if args.live_api_url:
        return args.live_api_url

    return f"http://{args.host}:{args.api_port}/api/dashboard/live"


def realm_id_from_live_row(row: dict[str, object]) -> int | None:
    realm_id = row.get("realmId")

    if isinstance(realm_id, int) and realm_id in REALM_NAMES:
        return realm_id

    realm_name = str(row.get("realmName", "")).strip().lower()
    return REALM_IDS_BY_NAME.get(realm_name)


def fetch_realm_counts(args: argparse.Namespace) -> dict[int, int]:
    url = build_live_api_url(args)

    with urllib.request.urlopen(url, timeout=args.realm_api_timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    counts = {realm_id: 0 for realm_id in REALM_NAMES}

    for row in payload.get("realms", []):
        if not isinstance(row, dict):
            continue

        realm_id = realm_id_from_live_row(row)

        if realm_id is None:
            continue

        counts[realm_id] = int(row.get("players", 0) or 0)

    return counts


def apply_realm_strategy(accounts: list[DummyAccount], args: argparse.Namespace) -> list[DummyAccount]:
    args.selected_realm = args.realm
    args.realm_counts = {}

    if args.realm_strategy == "fixed":
        return accounts

    try:
        counts = fetch_realm_counts(args)
    except Exception as exc:  # noqa: BLE001 - operator-facing runner should continue with a clear fallback.
        print(f"realm strategy fallback: failed to read live API ({exc}); using fixed realm/account order")
        return accounts

    args.realm_counts = counts
    realm_order = sorted(REALM_NAMES, key=lambda realm_id: (counts.get(realm_id, 0), realm_id))

    if args.accounts:
        by_realm = {
            realm_id: [account for account in accounts if account.realm == realm_id]
            for realm_id in REALM_NAMES
        }

        for realm_id in realm_order:
            if len(by_realm[realm_id]) >= args.concurrency:
                args.selected_realm = realm_id
                print(
                    "realm strategy: selected "
                    f"{REALM_NAMES[realm_id]} ({counts.get(realm_id, 0)} online), "
                    f"using {len(by_realm[realm_id])} account(s)"
                )
                return by_realm[realm_id]

        available = ", ".join(f"{REALM_NAMES[realm]}={len(rows)}" for realm, rows in by_realm.items())
        raise ValueError(
            "least-populated realm strategy could not find enough accounts "
            f"for concurrency={args.concurrency}; available: {available}"
        )

    selected = realm_order[0]
    args.realm = selected
    args.selected_realm = selected
    print(f"realm strategy: selected {REALM_NAMES[selected]} ({counts.get(selected, 0)} online)")
    return accounts


def apply_ai_player_defaults(args: argparse.Namespace) -> None:
    if not args.ai_player:
        return

    args.hunter = True
    args.combat = True
    args.move = True
    args.wander = True
    args.use_skills = True
    args.auto_release_on_death = True

    if args.command == list(DEFAULT_COMMANDS):
        args.command = []

    args.jitter = max(args.jitter, 1.0)
    args.position_heartbeat_interval = max(args.position_heartbeat_interval, 3.0)
    args.follow_nearby_player = True
    args.greet_nearby_player = True


def add_action(action_counts: dict[str, int], name: str) -> int:
    action_counts[name] = action_counts.get(name, 0) + 1
    return 1


def percentile(values: list[float], ratio: float) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * ratio)))
    return ordered[index]


def run_dummy_round(
    index: int,
    round_index: int,
    account: DummyAccount,
    args: argparse.Namespace,
    party_state: PartyState | None = None,
) -> RoundMetric:
    args = apply_ai_persona(args, account, index)
    rng = random.Random(args.seed + index * 100000 + round_index)
    client = HeadlessDaocClient(args.host, args.port, args.timeout, verbose=args.verbose)
    actions = 0
    action_counts: dict[str, int] = {}
    combat_metrics: list[CombatMetric] = []
    movement_failures: list[MovementFailure] = []
    started = time.monotonic()

    try:
        client.drive_login(account.username, account.password, account.realm, account.char_index)

        path_state = build_path_movement_state(args, client)
        if path_state.graph is not None:
            actions += add_action(action_counts, "path_graph_loaded")

        commands = list(args.command)
        next_ping = time.monotonic() + rng.uniform(0.2, max(args.ping_interval, 0.2))
        next_turn = time.monotonic() + rng.uniform(0.2, max(args.turn_interval, 0.2))
        next_command = time.monotonic() + rng.uniform(0.5, max(args.command_interval, 0.5))
        next_clear_target = time.monotonic() + max(args.clear_target_interval, 0.2)
        next_combat = time.monotonic() + rng.uniform(0.5, max(args.combat_interval, 0.5))
        next_skill = time.monotonic() + rng.uniform(1.0, max(args.skill_interval, 1.0))
        next_recovery = time.monotonic() + rng.uniform(5.0, max(args.recovery_interval, 5.0))
        next_invite = time.monotonic() + rng.uniform(1.0, max(args.party_invite_interval, 1.0))
        next_accept = time.monotonic() + rng.uniform(1.5, max(args.party_accept_interval, 1.5))
        next_assist = time.monotonic() + rng.uniform(2.0, max(args.party_assist_interval, 2.0))
        next_follow = time.monotonic() + rng.uniform(0.8, max(args.party_follow_interval, 0.8))
        next_think = time.monotonic() + rng.uniform(args.think_min, args.think_max)
        next_rest_check = time.monotonic() + rng.uniform(3.0, 8.0)
        next_social = time.monotonic() + rng.uniform(8.0, max(args.social_interval, 8.0))
        next_emote = time.monotonic() + rng.uniform(6.0, max(args.emote_interval, 6.0))
        next_look_around = time.monotonic() + rng.uniform(2.0, max(args.look_around_interval, 2.0))
        next_long_rest = time.monotonic() + rng.uniform(20.0, 45.0)
        initial_waypoint_interval = args.smooth_move_interval if args.smooth_movement else args.waypoint_interval
        next_waypoint_move = time.monotonic() + rng.uniform(0.05, max(initial_waypoint_interval, 0.05))
        next_smooth_move = time.monotonic() + rng.uniform(0.05, max(args.smooth_move_interval, 0.05))
        next_player_follow = time.monotonic() + rng.uniform(1.0, max(args.player_follow_interval, 1.0))
        next_player_greet = time.monotonic() + rng.uniform(8.0, max(args.player_greet_interval, 8.0))
        next_position_heartbeat = (
            time.monotonic() + rng.uniform(0.5, max(args.position_heartbeat_interval, 0.5))
            if args.position_heartbeat_interval > 0
            else float("inf")
        )
        heading = rng.randrange(0, 4096)
        current_target = 0
        current_target_since = time.monotonic()
        rejected_targets: dict[int, float] = {}
        rejected_target_kinds: dict[tuple[str, int], float] = {}
        greeted_players: dict[int, float] = {}
        rest_until = 0.0
        death_seen = False
        death_release_after = 0.0
        next_death_release = 0.0
        flee_until = 0.0
        next_flee_move = 0.0
        stand_after_rest = False
        active_combat: dict[str, float | int | str] | None = None
        waypoint_index = rng.randrange(0, len(args.waypoints)) if args.waypoints and args.waypoint_mode == "random" else 0
        end_time = time.monotonic() + args.hold
        party_slot = index % max(args.party_size, 1)
        is_party_leader = party_state is not None and party_slot == 0
        is_party_follower = party_state is not None and party_slot != 0
        action_rotation = resolve_action_rotation(args, party_slot)

        if party_state is not None:
            party_state.update_leader(client)

        def send_position_heartbeat(now: float) -> None:
            nonlocal actions, next_position_heartbeat

            if args.position_heartbeat_interval <= 0 or now < next_position_heartbeat:
                return

            client.send_position_update(speed=0.0, target_in_view=current_target != 0)
            actions += add_action(action_counts, "position_heartbeat")
            next_position_heartbeat = (
                now
                + args.position_heartbeat_interval
                + rng.uniform(0.0, min(args.jitter, max(args.position_heartbeat_interval * 0.5, 0.0)))
            )

        def start_combat(npc, distance: float, now: float) -> None:
            nonlocal active_combat
            active_combat = {
                "target_id": npc.object_id,
                "target_name": npc.name,
                "target_level": npc.level,
                "started": now,
                "attacks": 0,
                "skills": 0,
                "start_distance": distance,
                "end_distance": distance,
            }

        def finish_combat(outcome: str, now: float, end_distance: float = 0.0) -> bool:
            nonlocal active_combat

            if active_combat is None:
                return False

            duration = max(0.0, now - float(active_combat["started"]))
            final_distance = end_distance if end_distance > 0 else float(active_combat["end_distance"])
            combat_metrics.append(
                CombatMetric(
                    target_id=int(active_combat["target_id"]),
                    target_name=str(active_combat["target_name"]),
                    target_level=int(active_combat["target_level"]),
                    outcome=outcome,
                    duration=duration,
                    attacks=int(active_combat["attacks"]),
                    skills=int(active_combat["skills"]),
                    start_distance=float(active_combat["start_distance"]),
                    end_distance=final_distance,
                )
            )
            active_combat = None
            return True

        def reject_active_target_kind(now: float, cooldown: float) -> None:
            if active_combat is None or cooldown <= 0:
                return

            target_name = str(active_combat["target_name"]).lower()
            target_level = int(active_combat["target_level"])
            rejected_target_kinds[(target_name, target_level)] = now + cooldown

        def consume_removed_objects(now: float) -> None:
            nonlocal actions, current_target

            for object_id in client.consume_removed_object_ids():
                if object_id != current_target:
                    continue

                recorded = finish_combat("target_removed", now)
                current_target = 0
                rejected_targets.pop(object_id, None)
                if recorded:
                    actions += add_action(action_counts, "target_removed")

        def consume_messages() -> None:
            nonlocal actions

            for message in client.consume_messages():
                text = message.text.lower()
                actions += add_action(action_counts, "server_message")

                if "사거리" in text or "out of range" in text or "too far" in text:
                    actions += add_action(action_counts, "combat_out_of_range_msg")
                elif "보이지" in text or "not visible" in text or "not in view" in text:
                    actions += add_action(action_counts, "combat_not_visible_msg")
                elif "피해" in text or "damage" in text or "hit" in text:
                    actions += add_action(action_counts, "combat_damage_msg")

        while time.monotonic() < end_time:
            now = time.monotonic()
            consume_removed_objects(now)
            consume_messages()

            if stand_after_rest and now >= rest_until:
                stand_after_rest = False
                client.send_command("/stand")
                actions += add_action(action_counts, "stand")

            if now < rest_until:
                send_position_heartbeat(now)
                client.drain(args.tick)
                continue

            if client.is_dead:
                if not death_seen:
                    death_seen = True
                    death_release_after = now + args.death_release_delay
                    next_death_release = death_release_after
                    reject_active_target_kind(now, args.target_death_cooldown)
                    finish_combat("player_death", now)
                    current_target = 0
                    client.set_attack_mode(False)
                    actions += add_action(action_counts, "death_detected")

                if args.auto_release_on_death and now >= next_death_release:
                    client.send_command("/release")
                    actions += add_action(action_counts, "death_release")
                    next_death_release = now + args.death_recovery_cooldown

                client.drain(args.tick)
                continue

            if death_seen and not client.is_dead:
                death_seen = False
                rest_until = now + args.post_release_rest
                actions += add_action(action_counts, "death_recovered")
                client.drain(args.tick)
                continue

            send_position_heartbeat(now)

            if (
                args.flee_health_percent > 0
                and current_target
                and client.health_percent > 0
                and client.health_percent <= args.flee_health_percent
            ):
                reject_active_target_kind(now, args.target_retreat_cooldown)
                finish_combat("retreat", now)
                current_target = 0
                client.clear_target()
                client.set_attack_mode(False)
                flee_until = now + args.flee_duration
                next_flee_move = now
                actions += add_action(action_counts, "retreat")

            if now < flee_until:
                if now >= next_flee_move:
                    heading = (heading + rng.randrange(768, 1536)) & 0x0FFF
                    client.wander(heading, step=args.flee_step)
                    actions += add_action(action_counts, "flee_move")
                    next_flee_move = now + args.flee_move_interval + rng.uniform(0, args.jitter)

                client.drain(args.tick)
                continue

            if now >= next_rest_check:
                if args.rest_chance > 0 and rng.random() < args.rest_chance:
                    rest_until = now + rng.uniform(args.rest_min, args.rest_max)
                    client.set_attack_mode(False)
                    actions += add_action(action_counts, "rest")

                next_rest_check = now + rng.uniform(3.0, 8.0)

            if args.ai_player and args.long_rest_chance > 0 and now >= next_long_rest and not current_target:
                if rng.random() < args.long_rest_chance:
                    client.send_command("/sit")
                    rest_until = now + rng.uniform(args.long_rest_min, args.long_rest_max)
                    stand_after_rest = True
                    actions += add_action(action_counts, "long_rest")

                next_long_rest = now + rng.uniform(45.0, 120.0)

            if args.hunter and now < next_think and not current_target:
                client.drain(args.tick)
                continue

            if args.ai_player and args.look_around_interval > 0 and now >= next_look_around and not current_target:
                heading = (heading + rng.randrange(-384, 385)) & 0x0FFF
                client.send_heading(heading)
                actions += add_action(action_counts, "look_around")
                next_look_around = now + args.look_around_interval + rng.uniform(0, args.jitter)

            if (
                args.greet_nearby_player
                and args.player_greet_interval > 0
                and now >= next_player_greet
                and not current_target
                and args.player_greet_lines
            ):
                greet_player = choose_greet_player(client, args, greeted_players, now)

                if greet_player is not None and args.player_greet_chance > 0 and rng.random() < args.player_greet_chance:
                    client.send_command(rng.choice(args.player_greet_lines))
                    greeted_players[greet_player.object_id] = now + args.player_greet_cooldown
                    actions += add_action(action_counts, "player_greet")

                next_player_greet = now + args.player_greet_interval + rng.uniform(0, args.jitter)

            if (
                args.follow_nearby_player
                and args.player_follow_interval > 0
                and now >= next_player_follow
                and not current_target
                and not is_party_follower
            ):
                follow_player = choose_follow_player(client, args)

                if follow_player is not None:
                    follow_destination = destination_from_actor("follow-player", follow_player)
                    outcome = move_towards_destination(
                        client,
                        follow_destination,
                        step=args.player_follow_step,
                        stop_distance=args.player_follow_distance,
                        args=args,
                        path_state=path_state,
                        action_counts=action_counts,
                    )
                    actions += outcome.actions
                    record_movement_failure(movement_failures, client, follow_destination, outcome, "player_follow")
                    actions += add_action(action_counts, "player_follow" if outcome.moved else "player_hold")

                next_player_follow = now + args.player_follow_interval + rng.uniform(0, args.jitter)

            if args.waypoints and args.waypoint_interval > 0 and now >= next_waypoint_move and not current_target:
                waypoint = args.waypoints[waypoint_index]
                waypoint_destination = MovementDestination(
                    key=f"waypoint:{waypoint_index}:{waypoint.x}:{waypoint.y}:{waypoint.z}",
                    x=waypoint.x,
                    y=waypoint.y,
                    z=waypoint.z,
                )
                waypoint_step = smooth_movement_step(args) if args.smooth_movement else args.waypoint_step
                outcome = move_towards_destination(
                    client,
                    waypoint_destination,
                    step=waypoint_step,
                    stop_distance=args.waypoint_stop_distance,
                    args=args,
                    path_state=path_state,
                    action_counts=action_counts,
                )
                actions += outcome.actions
                record_movement_failure(movement_failures, client, waypoint_destination, outcome, "waypoint")

                if outcome.moved:
                    actions += add_action(action_counts, "waypoint_move")
                elif outcome.arrived:
                    actions += add_action(action_counts, "waypoint_reached")

                    if args.waypoint_mode == "random":
                        waypoint_index = rng.randrange(0, len(args.waypoints))
                    else:
                        waypoint_index = (waypoint_index + 1) % len(args.waypoints)
                else:
                    actions += add_action(action_counts, "waypoint_hold")

                waypoint_delay = args.smooth_move_interval if args.smooth_movement else args.waypoint_interval
                next_waypoint_move = now + waypoint_delay + rng.uniform(0, min(args.jitter, waypoint_delay))

            if (
                args.smooth_movement
                and current_target
                and (args.move or args.hunter)
                and args.smooth_move_interval > 0
                and now >= next_smooth_move
            ):
                target_npc = next(
                    (
                        npc
                        for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=args.include_peace_npcs)
                        if npc.object_id == current_target
                    ),
                    None,
                )

                if target_npc is not None:
                    target_destination = destination_from_actor("target", target_npc)
                    outcome = move_towards_destination(
                        client,
                        target_destination,
                        step=smooth_movement_step(args),
                        stop_distance=melee_stop_distance(args),
                        args=args,
                        path_state=path_state,
                        action_counts=action_counts,
                    )
                    actions += outcome.actions
                    record_movement_failure(movement_failures, client, target_destination, outcome, "smooth_target")
                    distance = client.distance_to(target_npc)
                    actions += add_action(action_counts, "smooth_move" if outcome.moved else "smooth_hold")

                    if active_combat is not None:
                        active_combat["end_distance"] = distance

                    if distance <= args.attack_range:
                        client.set_attack_mode(True)

                next_smooth_move = now + args.smooth_move_interval + rng.uniform(0.0, min(args.jitter, args.smooth_move_interval))

            if args.ping_interval > 0 and now >= next_ping:
                client.send_ping()
                actions += add_action(action_counts, "ping")
                next_ping = now + args.ping_interval + rng.uniform(0, args.jitter)

            if args.turn_interval > 0 and now >= next_turn:
                heading = (heading + rng.randrange(128, 768)) & 0x0FFF
                client.send_heading(heading)
                actions += add_action(action_counts, "turn")
                next_turn = now + args.turn_interval + rng.uniform(0, args.jitter)

            if commands and args.command_interval > 0 and now >= next_command:
                client.send_command(rng.choice(commands))
                actions += add_action(action_counts, "command")
                next_command = now + args.command_interval + rng.uniform(0, args.jitter)

            if args.ai_player and args.social_interval > 0 and now >= next_social and not current_target:
                if args.social_chance > 0 and args.social_lines and rng.random() < args.social_chance:
                    client.send_command(rng.choice(args.social_lines))
                    actions += add_action(action_counts, "social_chat")

                next_social = now + args.social_interval + rng.uniform(0, args.jitter)

            if args.ai_player and args.emote_interval > 0 and now >= next_emote and not current_target:
                if args.emote_chance > 0 and args.emote_commands and rng.random() < args.emote_chance:
                    client.send_command(rng.choice(args.emote_commands))
                    actions += add_action(action_counts, "social_emote")

                next_emote = now + args.emote_interval + rng.uniform(0, args.jitter)

            if args.clear_target_interval > 0 and now >= next_clear_target:
                client.clear_target()
                current_target = 0
                actions += add_action(action_counts, "clear_target")
                next_clear_target = now + args.clear_target_interval + rng.uniform(0, args.jitter)

            if args.recovery and args.recovery_interval > 0 and now >= next_recovery:
                client.send_command(rng.choice(["/release", "/pray"]))
                actions += add_action(action_counts, "recovery")
                next_recovery = now + args.recovery_interval + rng.uniform(0, args.jitter)

            if is_party_leader and args.party_invite_interval > 0 and now >= next_invite:
                for member_name in party_state.member_names[1:]:
                    client.send_command(f"/invite {member_name}")
                    actions += add_action(action_counts, "party_invite")

                next_invite = now + args.party_invite_interval + rng.uniform(0, args.jitter)

            if is_party_follower and args.party_accept_interval > 0 and now >= next_accept:
                party_snapshot = party_state.snapshot()
                leader_session_id = int(party_snapshot["leader_session_id"])

                if leader_session_id:
                    client.accept_group_invite(leader_session_id)
                    actions += add_action(action_counts, "party_accept")

                next_accept = now + args.party_accept_interval + rng.uniform(0, args.jitter)

            if is_party_follower and args.party_assist_interval > 0 and now >= next_assist:
                party_snapshot = party_state.snapshot()
                leader_target_id = int(party_snapshot["leader_target_id"])

                if args.party_use_assist_command:
                    client.send_command(f"/assist {party_state.leader_name}")
                    actions += add_action(action_counts, "party_assist_command")

                if leader_target_id:
                    client.target_object(leader_target_id)
                    current_target = leader_target_id
                    current_target_since = now
                    actions += add_action(action_counts, "party_assist")

                next_assist = now + args.party_assist_interval + rng.uniform(0, args.jitter)

            if is_party_follower and args.party_follow_interval > 0 and now >= next_follow:
                party_snapshot = party_state.snapshot()

                if time.monotonic() - float(party_snapshot["updated_at"]) <= args.party_state_max_age:
                    leader_x = int(party_snapshot["leader_x"])
                    leader_y = int(party_snapshot["leader_y"])
                    leader_z = int(party_snapshot["leader_z"])
                    leader_destination = destination_from_point("party-leader", leader_x, leader_y, leader_z)
                    outcome = move_towards_destination(
                        client,
                        leader_destination,
                        step=args.party_follow_step,
                        stop_distance=args.party_follow_distance,
                        args=args,
                        path_state=path_state,
                        action_counts=action_counts,
                    )
                    actions += outcome.actions
                    record_movement_failure(movement_failures, client, leader_destination, outcome, "party_follow")
                    actions += add_action(action_counts, "party_follow" if outcome.moved else "party_hold")

                next_follow = now + args.party_follow_interval + rng.uniform(0, args.jitter)

            if (args.combat or args.hunter) and args.combat_interval > 0 and now >= next_combat:
                if current_target and now - current_target_since > args.target_timeout:
                    rejected_targets[current_target] = now + args.target_failure_cooldown
                    reject_active_target_kind(now, args.target_failure_name_cooldown)
                    finish_combat("target_timeout", now)
                    client.clear_target()
                    current_target = 0
                    actions += add_action(action_counts, "reject_target")

                npcs = client.visible_npcs(max_age=args.npc_max_age, include_peace=args.include_peace_npcs)

                if args.hunter:
                    selected_npc = None

                    if current_target and rng.random() < args.stick_to_target_chance:
                        selected_npc = next((npc for npc in npcs if npc.object_id == current_target), None)

                    if is_party_follower:
                        party_snapshot = party_state.snapshot()
                        leader_target_id = int(party_snapshot["leader_target_id"])
                        selected_npc = next((npc for npc in npcs if npc.object_id == leader_target_id), selected_npc)

                    if selected_npc is None:
                        selected_npc = choose_hunter_target(
                            client,
                            rng,
                            args,
                            rejected_targets,
                            rejected_target_kinds,
                            now,
                        )

                    npcs = [selected_npc] if selected_npc is not None else []

                if npcs:
                    npc = rng.choice(npcs[: max(args.target_pool, 1)])
                    distance = client.distance_to(npc)

                    if current_target != npc.object_id:
                        finish_combat("target_switched", now, distance)
                        examine = args.target_examine_chance > 0 and rng.random() < args.target_examine_chance
                        client.target_object(npc.object_id, examine=examine)
                        current_target = npc.object_id
                        current_target_since = now
                        start_combat(npc, distance, now)
                        actions += add_action(action_counts, "examine_target" if examine else "target")

                    if is_party_leader:
                        party_state.update_leader(client, npc)

                    if (args.move or args.hunter) and not args.smooth_movement:
                        target_destination = destination_from_actor("target", npc)
                        outcome = move_towards_destination(
                            client,
                            target_destination,
                            step=args.move_step,
                            stop_distance=melee_stop_distance(args),
                            args=args,
                            path_state=path_state,
                            action_counts=action_counts,
                        )
                        actions += outcome.actions
                        record_movement_failure(movement_failures, client, target_destination, outcome, "target")
                        actions += add_action(action_counts, "move" if outcome.moved else "hold_position")

                        if outcome.moved:
                            distance = client.distance_to(npc)

                    if args.interact:
                        client.interact_object(npc.object_id)
                        actions += add_action(action_counts, "interact")

                    client.set_attack_mode(distance <= args.attack_range)
                    actions += add_action(action_counts, "attack_on" if distance <= args.attack_range else "attack_off")

                    if active_combat is not None:
                        active_combat["end_distance"] = distance

                        if distance <= args.attack_range:
                            active_combat["attacks"] = int(active_combat["attacks"]) + 1

                    if args.use_skills and now >= next_skill:
                        rotation_action = perform_rotation_action(client, rng, args, action_rotation, distance)

                        if rotation_action is not None:
                            if active_combat is not None:
                                active_combat["skills"] = int(active_combat["skills"]) + 1
                            actions += add_action(action_counts, rotation_action)

                        next_skill = now + args.skill_interval + rng.uniform(0, args.jitter)
                else:
                    client.set_attack_mode(False)
                    actions += add_action(action_counts, "attack_off")

                    if args.wander:
                        if path_state.graph is not None:
                            actions += add_action(action_counts, "wander_path_guard")
                        else:
                            heading = (heading + rng.randrange(-512, 513)) & 0x0FFF
                            client.wander(heading, step=args.wander_step)
                            actions += add_action(action_counts, "wander")

                next_combat = now + args.combat_interval + rng.uniform(0, args.jitter)
                next_think = now + rng.uniform(args.think_min, args.think_max)

            client.drain(args.tick)
            consume_removed_objects(time.monotonic())

            if is_party_leader:
                party_state.update_leader(client)

        finish_combat("round_end", time.monotonic())
        actions += add_action(action_counts, f"rotation_{action_rotation}")
        return RoundMetric(
            account.username,
            round_index,
            True,
            actions,
            time.monotonic() - started,
            "",
            action_counts,
            combat_metrics,
            args.ai_persona_name,
            movement_failures,
        )

    except Exception as exc:  # noqa: BLE001 - test runner should report and continue.
        try:
            actions += add_action(action_counts, f"rotation_{resolve_action_rotation(args, index % max(args.party_size, 1))}")
        except Exception:
            pass
        return RoundMetric(
            account.username,
            round_index,
            False,
            actions,
            time.monotonic() - started,
            str(exc),
            action_counts,
            combat_metrics,
            args.ai_persona_name,
            movement_failures,
        )
    finally:
        try:
            client.set_attack_mode(False)
        except Exception:
            pass

        client.close()


def run_dummy(index: int, account: DummyAccount, args: argparse.Namespace, results: list[DummyResult]) -> None:
    run_dummy_plan(index, [account], args, results)


def run_dummy_plan(
    index: int,
    accounts: list[DummyAccount],
    args: argparse.Namespace,
    results: list[DummyResult],
    party_state: PartyState | None = None,
) -> None:
    if args.ramp_up > 0:
        time.sleep(args.ramp_up * index / max(args.concurrency, 1))

    metrics: list[RoundMetric] = []
    started = time.monotonic()

    for round_index in range(1, args.rounds + 1):
        account = accounts[round_index - 1] if round_index <= len(accounts) else accounts[-1]
        metric = run_dummy_round(index, round_index, account, args, party_state)
        metrics.append(metric)

        if round_index < args.rounds and args.round_delay > 0:
            time.sleep(args.round_delay)

    successful_rounds = sum(1 for metric in metrics if metric.ok)
    errors = [metric.error for metric in metrics if metric.error]
    results[index] = DummyResult(
        accounts[0].username if len(accounts) == 1 else f"worker{index + 1}",
        ok=successful_rounds == len(metrics),
        actions=sum(metric.actions for metric in metrics),
        rounds=len(metrics),
        successful_rounds=successful_rounds,
        elapsed=time.monotonic() - started,
        error="; ".join(errors[:3]),
        metrics=metrics,
    )


def load_accounts(path: str | None, args: argparse.Namespace) -> list[DummyAccount]:
    if not path:
        return [DummyAccount(args.username, args.password, args.realm, args.char_index)]

    rows: list[DummyAccount] = []

    with Path(path).open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        for row in reader:
            rows.append(
                DummyAccount(
                    username=row["username"],
                    password=row["password"],
                    realm=int(row.get("realm") or args.realm),
                    char_index=int(row.get("char_index") or args.char_index),
                )
            )

    if not rows:
        raise ValueError(f"no accounts found in {path}")

    return rows


def write_metrics_csv(path: str, results: list[DummyResult]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    action_names = sorted(
        {
            action_name
            for result in results
            for metric in result.metrics or []
            for action_name in (metric.action_counts or {}).keys()
        }
    )

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "username",
                "round",
                "persona",
                "ok",
                "actions",
                "elapsed_seconds",
                "combat_engagements",
                "target_removed",
                "player_deaths",
                "target_timeouts",
                "avg_combat_seconds",
                "movement_failures",
                "movement_failure_sample",
                "error",
                *action_names,
            ]
        )

        for result in results:
            for metric in result.metrics or []:
                combats = metric.combat_metrics or []
                durations = [combat.duration for combat in combats if combat.outcome == "target_removed"]
                writer.writerow(
                    [
                        metric.username,
                        metric.round_index,
                        metric.persona,
                        "true" if metric.ok else "false",
                        metric.actions,
                        f"{metric.elapsed:.3f}",
                        len(combats),
                        sum(1 for combat in combats if combat.outcome == "target_removed"),
                        sum(1 for combat in combats if combat.outcome == "player_death"),
                        sum(1 for combat in combats if combat.outcome == "target_timeout"),
                        f"{(sum(durations) / len(durations)):.3f}" if durations else "0.000",
                        len(metric.movement_failures or []),
                        format_movement_failure_sample(metric.movement_failures or []),
                        metric.error,
                        *[(metric.action_counts or {}).get(action_name, 0) for action_name in action_names],
                    ]
                )


def write_combat_csv(path: str, results: list[DummyResult]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "username",
                "round",
                "target_id",
                "target_name",
                "target_level",
                "outcome",
                "duration_seconds",
                "attacks",
                "skills",
                "start_distance",
                "end_distance",
            ]
        )

        for result in results:
            for metric in result.metrics or []:
                for combat in metric.combat_metrics or []:
                    writer.writerow(
                        [
                            metric.username,
                            metric.round_index,
                            combat.target_id,
                            combat.target_name,
                            combat.target_level,
                            combat.outcome,
                            f"{combat.duration:.3f}",
                            combat.attacks,
                            combat.skills,
                            f"{combat.start_distance:.1f}",
                            f"{combat.end_distance:.1f}",
                        ]
                    )


def iter_combat_metrics(results: list[DummyResult]):
    for result in results:
        for metric in result.metrics or []:
            for combat in metric.combat_metrics or []:
                yield combat


def iter_movement_failures(results: list[DummyResult]):
    for result in results:
        for metric in result.metrics or []:
            for failure in metric.movement_failures or []:
                yield metric, failure


def format_movement_failure_sample(failures: list[MovementFailure]) -> str:
    if not failures:
        return ""

    failure = failures[0]
    return (
        f"{failure.context}:{failure.reason} "
        f"{failure.start_x},{failure.start_y},{failure.start_z}"
        f"->{failure.goal_x},{failure.goal_y},{failure.goal_z}"
    )


def summarize_combat(results: list[DummyResult]) -> dict[str, object]:
    combats = list(iter_combat_metrics(results))
    kills = [combat for combat in combats if combat.outcome == "target_removed"]
    kill_durations = [combat.duration for combat in kills]
    player_deaths = sum(1 for combat in combats if combat.outcome == "player_death")
    target_timeouts = sum(1 for combat in combats if combat.outcome == "target_timeout")

    by_target: dict[tuple[str, int], dict[str, float | int | str]] = {}

    for combat in combats:
        key = (combat.target_name, combat.target_level)
        row = by_target.setdefault(
            key,
            {
                "target_name": combat.target_name,
                "target_level": combat.target_level,
                "engagements": 0,
                "kills": 0,
                "player_deaths": 0,
                "timeouts": 0,
                "kill_duration_total": 0.0,
            },
        )
        row["engagements"] = int(row["engagements"]) + 1

        if combat.outcome == "target_removed":
            row["kills"] = int(row["kills"]) + 1
            row["kill_duration_total"] = float(row["kill_duration_total"]) + combat.duration
        elif combat.outcome == "player_death":
            row["player_deaths"] = int(row["player_deaths"]) + 1
        elif combat.outcome == "target_timeout":
            row["timeouts"] = int(row["timeouts"]) + 1

    return {
        "engagements": len(combats),
        "kills": len(kills),
        "player_deaths": player_deaths,
        "target_timeouts": target_timeouts,
        "avg_kill_seconds": sum(kill_durations) / len(kill_durations) if kill_durations else 0.0,
        "p50_kill_seconds": percentile(kill_durations, 0.50),
        "p90_kill_seconds": percentile(kill_durations, 0.90),
        "by_target": sorted(
            by_target.values(),
            key=lambda row: (int(row["kills"]), int(row["engagements"])),
            reverse=True,
        ),
    }


def summarize_action_counts(results: list[DummyResult]) -> dict[str, int]:
    totals: dict[str, int] = {}

    for result in results:
        for metric in result.metrics or []:
            for action_name, count in (metric.action_counts or {}).items():
                totals[action_name] = totals.get(action_name, 0) + count

    return dict(sorted(totals.items()))


def summarize_rotations(action_totals: dict[str, int]) -> dict[str, int]:
    return {
        action_name.removeprefix("rotation_"): count
        for action_name, count in action_totals.items()
        if action_name.startswith("rotation_")
    }


def summarize_personas(results: list[DummyResult]) -> dict[str, int]:
    totals: dict[str, int] = {}

    for result in results:
        for metric in result.metrics or []:
            persona = metric.persona or "none"
            totals[persona] = totals.get(persona, 0) + 1

    return dict(sorted(totals.items()))


def write_report_md(path: str, results: list[DummyResult], elapsed: float, args: argparse.Namespace) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ok_count = sum(1 for result in results if result.ok and not result.error)
    round_count = sum(result.rounds for result in results)
    successful_round_count = sum(result.successful_rounds for result in results)
    action_count = sum(result.actions for result in results)
    action_totals = summarize_action_counts(results)
    rotation_totals = summarize_rotations(action_totals)
    persona_totals = summarize_personas(results)
    combat_summary = summarize_combat(results)
    lines = [
        "# Dummy Client Report",
        "",
        "## Summary",
        "",
        f"- Host: `{args.host}:{args.port}`",
        f"- Concurrency: `{args.concurrency}`",
        f"- Rounds: `{successful_round_count}/{round_count}`",
        f"- Workers OK: `{ok_count}/{len(results)}`",
        f"- Actions: `{action_count}`",
        f"- Elapsed: `{elapsed:.1f}s`",
        f"- Mode: `profile={args.behavior_profile}`, `ai_player={args.ai_player}`, `hunter={args.hunter}`, `combat={args.combat}`, `move={args.move}`, `use_skills={args.use_skills}`, `recovery={args.recovery}`, `party_size={args.party_size}`",
        f"- AI persona: `{args.ai_persona}`",
        f"- Realm strategy: `{args.realm_strategy}`, selected `{REALM_NAMES.get(getattr(args, 'selected_realm', args.realm), getattr(args, 'selected_realm', args.realm))}`, counts `{getattr(args, 'realm_counts', {})}`",
        f"- Waypoints: `{len(args.waypoints)}`",
        "",
        "## Actions",
        "",
        "| Action | Count |",
        "| --- | ---: |",
    ]

    if action_totals:
        for action_name, count in action_totals.items():
            lines.append(f"| `{action_name}` | {count} |")
    else:
        lines.append("| `none` | 0 |")

    lines += [
        "",
        "## Role Rotations",
        "",
        "| Rotation | Workers |",
        "| --- | ---: |",
    ]

    if rotation_totals:
        for rotation_name, count in sorted(rotation_totals.items()):
            lines.append(f"| `{rotation_name}` | {count} |")
    else:
        lines.append("| `none` | 0 |")

    lines += [
        "",
        "## AI Personas",
        "",
        "| Persona | Rounds |",
        "| --- | ---: |",
    ]

    if persona_totals:
        for persona_name, count in persona_totals.items():
            lines.append(f"| `{persona_name}` | {count} |")
    else:
        lines.append("| `none` | 0 |")

    lines += [
        "",
        "## Balance Metrics",
        "",
        f"- Engagements: `{combat_summary['engagements']}`",
        f"- Target removed: `{combat_summary['kills']}`",
        f"- Player deaths during combat: `{combat_summary['player_deaths']}`",
        f"- Target timeouts: `{combat_summary['target_timeouts']}`",
        f"- Kill time avg/p50/p90: `{combat_summary['avg_kill_seconds']:.2f}s` / `{combat_summary['p50_kill_seconds']:.2f}s` / `{combat_summary['p90_kill_seconds']:.2f}s`",
        "",
        "## Target Summary",
        "",
        "| Target | Level | Engagements | Removed | Deaths | Timeouts | Avg Kill Time |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]

    target_rows = combat_summary["by_target"]

    if target_rows:
        for row in target_rows[:25]:
            kills = int(row["kills"])
            avg_kill_time = float(row["kill_duration_total"]) / kills if kills else 0.0
            lines.append(
                f"| `{str(row['target_name']).replace('|', '\\|')}` | {int(row['target_level'])} | "
                f"{int(row['engagements'])} | {kills} | {int(row['player_deaths'])} | "
                f"{int(row['timeouts'])} | {avg_kill_time:.2f}s |"
            )
    else:
        lines.append("| `none` | 0 | 0 | 0 | 0 | 0 | 0.00s |")

    movement_failures = list(iter_movement_failures(results))
    lines += [
        "",
        "## Movement Failures",
        "",
        f"- Samples captured: `{len(movement_failures)}`",
        "",
        "| Account | Round | Context | Reason | From | To | Destination |",
        "| --- | ---: | --- | --- | --- | --- | --- |",
    ]

    if movement_failures:
        for metric, failure in movement_failures[:25]:
            reason = failure.reason.replace("|", "\\|")
            destination_key = failure.destination_key.replace("|", "\\|")
            lines.append(
                f"| `{metric.username}` | {metric.round_index} | `{failure.context}` | {reason} | "
                f"`{failure.start_x},{failure.start_y},{failure.start_z}` | "
                f"`{failure.goal_x},{failure.goal_y},{failure.goal_z}` | `{destination_key}` |"
            )
    else:
        lines.append("| `none` | 0 | `none` | none | `0,0,0` | `0,0,0` | `none` |")

    lines += [
        "",
        "## Rounds",
        "",
        "| Account | Round | Result | Actions | Elapsed | Error |",
        "| --- | ---: | --- | ---: | ---: | --- |",
    ]

    for result in results:
        for metric in result.metrics or []:
            status = "ok" if metric.ok else "failed"
            error = metric.error.replace("|", "\\|") if metric.error else ""
            lines.append(
                f"| `{metric.username}` | {metric.round_index} | {status} | "
                f"{metric.actions} | {metric.elapsed:.3f}s | {error} |"
            )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_account_plans(accounts: list[DummyAccount], args: argparse.Namespace) -> list[list[DummyAccount]]:
    if args.fresh_account_per_round:
        needed = args.concurrency * args.rounds

        if len(accounts) < needed:
            raise ValueError(
                f"--fresh-account-per-round needs {needed} accounts "
                f"for concurrency={args.concurrency}, rounds={args.rounds}; got {len(accounts)}"
            )

        return [
            [accounts[round_index * args.concurrency + worker_index] for round_index in range(args.rounds)]
            for worker_index in range(args.concurrency)
        ]

    return [[account] for account in accounts[: args.concurrency]]


def build_party_states(account_plans: list[list[DummyAccount]], args: argparse.Namespace) -> list[PartyState | None]:
    party_states: list[PartyState | None] = [None] * len(account_plans)

    if args.party_size <= 1:
        return party_states

    for party_start in range(0, len(account_plans), args.party_size):
        party_end = min(party_start + args.party_size, len(account_plans))
        member_names = [character_name_from_account(account_plans[index][0].username) for index in range(party_start, party_end)]

        if not member_names:
            continue

        party_state = PartyState(member_names[0], member_names)

        for index in range(party_start, party_end):
            party_states[index] = party_state

    return party_states


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--accounts")
    parser.add_argument("--username", default=os.environ.get("OPENDAOC_USERNAME", "bigjuh"))
    parser.add_argument("--password", default=os.environ.get("OPENDAOC_PASSWORD", ""))
    parser.add_argument("--realm", type=int, default=1)
    parser.add_argument(
        "--realm-strategy",
        choices=["fixed", "least-populated"],
        default="fixed",
        help="fixed uses CSV/default realm; least-populated reads the dashboard live API and picks the lowest-population realm with enough accounts",
    )
    parser.add_argument("--live-api-url", default="", help="dashboard live API URL; default is http://HOST:API_PORT/api/dashboard/live")
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--realm-api-timeout", type=float, default=2.0)
    parser.add_argument("--char-index", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--hold", type=float, default=60.0)
    parser.add_argument("--rounds", type=int, default=1, help="repeat each dummy session this many times")
    parser.add_argument("--round-delay", type=float, default=5.0)
    parser.add_argument(
        "--fresh-account-per-round",
        action="store_true",
        help="use a different account for each worker round to avoid linkdead reconnect delay",
    )
    parser.add_argument("--ramp-up", type=float, default=0.0)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--ping-interval", type=float, default=15.0)
    parser.add_argument("--turn-interval", type=float, default=5.0)
    parser.add_argument(
        "--position-heartbeat-interval",
        type=float,
        default=3.0,
        help="send an idle position update at this interval so the server does not soft-linkdead stationary dummy clients",
    )
    parser.add_argument("--command-interval", type=float, default=30.0)
    parser.add_argument("--clear-target-interval", type=int, default=0)
    parser.add_argument("--combat", action="store_true", help="target nearby NPCs and toggle attack mode")
    parser.add_argument("--hunter", action="store_true", help="beginner hunter behavior: choose level-appropriate NPCs, approach, attack, wander")
    parser.add_argument("--combat-interval", type=float, default=8.0)
    parser.add_argument("--target-pool", type=int, default=5, help="randomly pick from the nearest N known NPCs")
    parser.add_argument("--npc-max-age", type=float, default=60.0)
    parser.add_argument("--player-level", type=int, default=1)
    parser.add_argument("--ideal-target-level", type=int, default=0, help="preferred NPC level for smart target scoring; 0 uses --player-level")
    parser.add_argument("--min-target-level", type=int, default=1)
    parser.add_argument("--max-target-level", type=int, default=-1, help="absolute maximum NPC level; -1 uses player level plus delta")
    parser.add_argument("--max-target-level-delta", type=int, default=2)
    parser.add_argument("--max-target-distance", type=float, default=0.0, help="ignore targets farther than this distance; 0 disables the cap")
    parser.add_argument("--target-timeout", type=float, default=20.0)
    parser.add_argument("--target-failure-cooldown", type=float, default=25.0, help="seconds to avoid a target after timing out on it")
    parser.add_argument(
        "--target-failure-name-cooldown",
        type=float,
        default=120.0,
        help="seconds to avoid the same target name/level after timing out on it",
    )
    parser.add_argument(
        "--target-death-cooldown",
        type=float,
        default=300.0,
        help="seconds to avoid the same target name/level after dying to it",
    )
    parser.add_argument(
        "--target-retreat-cooldown",
        type=float,
        default=60.0,
        help="seconds to avoid the same target name/level after retreating from it",
    )
    parser.add_argument(
        "--target-selection",
        choices=["smart", "nearest", "random"],
        default="smart",
        help="how hunter mode chooses among visible target candidates",
    )
    parser.add_argument("--target-level-weight", type=float, default=120.0)
    parser.add_argument("--target-distance-weight", type=float, default=120.0)
    parser.add_argument("--target-randomness", type=float, default=35.0)
    parser.add_argument("--prefer-target-name", default="", help="comma-separated lowercase/name fragments to prefer")
    parser.add_argument("--avoid-target-name", default="", help="comma-separated lowercase/name fragments to ignore")
    parser.add_argument("--prefer-target-bonus", type=float, default=300.0)
    parser.add_argument("--target-examine-chance", type=float, default=0.0, help="chance to examine a newly selected target like a player checking it")
    parser.add_argument(
        "--stick-to-target-chance",
        type=float,
        default=0.80,
        help="chance to keep fighting the current visible target instead of picking a new one",
    )
    parser.add_argument("--include-peace-npcs", action="store_true")
    parser.add_argument("--interact", action="store_true", help="send ObjectInteractRequest before attacking the selected NPC")
    parser.add_argument("--move", action="store_true", help="send position updates toward the selected NPC")
    parser.add_argument("--move-step", type=float, default=300.0)
    parser.add_argument("--smooth-movement", action="store_true", help="send smaller frequent movement packets instead of large jumps")
    parser.add_argument("--smooth-move-interval", type=float, default=0.25)
    parser.add_argument("--movement-speed", type=float, default=220.0, help="movement units per second for --smooth-movement")
    parser.add_argument("--path-graph", default="", help="JSON waypoint graph used for A* dummy movement")
    parser.add_argument("--path-region", type=int, default=0, help="region id inside --path-graph; 0 uses the client's current zone id")
    parser.add_argument("--disable-graph-pathing", action="store_true")
    parser.add_argument("--path-max-node-distance", type=float, default=2500.0)
    parser.add_argument("--path-node-arrival-distance", type=float, default=160.0)
    parser.add_argument("--path-last-mile-distance", type=float, default=450.0)
    parser.add_argument("--path-max-edge-length", type=float, default=1800.0)
    parser.add_argument("--path-max-height-delta", type=int, default=450)
    parser.add_argument("--path-replan-interval", type=float, default=3.0)
    parser.add_argument("--path-allow-water", action="store_true")
    parser.add_argument("--path-allow-closed-door", action="store_true")
    parser.add_argument("--path-allow-keep-door", action="store_true")
    parser.add_argument("--path-allow-cliff", action="store_true")
    parser.add_argument("--nav-api-url", default="", help="server API root used for navmesh path queries, for example http://127.0.0.1:5000")
    parser.add_argument("--nav-api-timeout", type=float, default=1.0)
    parser.add_argument("--nav-api-max-nodes", type=int, default=128)
    parser.add_argument("--nav-api-snap", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--nav-api-avoid-blocking-doors", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--nav-segment-validate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--attack-range", type=float, default=350.0)
    parser.add_argument("--melee-range-buffer", type=float, default=25.0, help="stand this much inside attack range before attacking")
    parser.add_argument("--minimum-melee-stop-distance", type=float, default=70.0)
    parser.add_argument("--wander", action="store_true", help="wander when no suitable target is known")
    parser.add_argument("--wander-step", type=float, default=220.0)
    parser.add_argument(
        "--waypoints",
        type=parse_waypoints,
        default=[],
        help="pipe-separated x,y,z waypoint route used when idle, for example '1000,2000,300|1200,2200,300'",
    )
    parser.add_argument("--waypoint-mode", choices=["loop", "random"], default="loop")
    parser.add_argument("--waypoint-interval", type=float, default=1.5)
    parser.add_argument("--waypoint-step", type=float, default=360.0)
    parser.add_argument("--waypoint-stop-distance", type=float, default=450.0)
    parser.add_argument("--flee-health-percent", type=int, default=0, help="retreat when health is at or below this percent; 0 disables fleeing")
    parser.add_argument("--flee-duration", type=float, default=4.0)
    parser.add_argument("--flee-step", type=float, default=360.0)
    parser.add_argument("--flee-move-interval", type=float, default=0.8)
    parser.add_argument("--rest-chance", type=float, default=0.0)
    parser.add_argument("--rest-min", type=float, default=1.0)
    parser.add_argument("--rest-max", type=float, default=3.0)
    parser.add_argument("--think-min", type=float, default=0.0)
    parser.add_argument("--think-max", type=float, default=0.0)
    parser.add_argument("--ai-player", action="store_true", help="enable higher-level human-like PvE pacing, social idle actions, and long rests")
    parser.add_argument(
        "--ai-persona",
        choices=["auto", "none", *sorted(AI_PERSONAS)],
        default="auto",
        help="AI behavior flavor. auto picks a stable account-based persona; none keeps all AI players on the same knobs",
    )
    parser.add_argument("--social-interval", type=float, default=75.0)
    parser.add_argument("--social-chance", type=float, default=0.08)
    parser.add_argument(
        "--social-lines",
        type=parse_text_list,
        default=DEFAULT_SOCIAL_LINES,
        help="pipe-separated normal chat lines for --ai-player, for example '안녕하세요|잠깐 쉬어요'",
    )
    parser.add_argument("--emote-interval", type=float, default=55.0)
    parser.add_argument("--emote-chance", type=float, default=0.12)
    parser.add_argument(
        "--emote-commands",
        type=parse_text_list,
        default=DEFAULT_EMOTE_COMMANDS,
        help="pipe-separated slash emotes/commands for --ai-player",
    )
    parser.add_argument("--look-around-interval", type=float, default=12.0)
    parser.add_argument("--long-rest-chance", type=float, default=0.06)
    parser.add_argument("--long-rest-min", type=float, default=8.0)
    parser.add_argument("--long-rest-max", type=float, default=25.0)
    parser.add_argument("--greet-nearby-player", action="store_true", help="send a short normal chat greeting to a nearby visible player with cooldown")
    parser.add_argument("--player-greet-interval", type=float, default=45.0)
    parser.add_argument("--player-greet-chance", type=float, default=0.06)
    parser.add_argument("--player-greet-distance", type=float, default=950.0)
    parser.add_argument("--player-greet-cooldown", type=float, default=600.0)
    parser.add_argument(
        "--player-greet-lines",
        type=parse_text_list,
        default=DEFAULT_PLAYER_GREET_LINES,
        help="pipe-separated short normal chat greetings for nearby players",
    )
    parser.add_argument("--follow-nearby-player", action="store_true", help="when idle, move near the closest visible player to look like a social PvE player")
    parser.add_argument("--follow-player-name", default="", help="optional visible player name fragment to prefer for idle follow behavior")
    parser.add_argument("--player-follow-interval", type=float, default=2.0)
    parser.add_argument("--player-follow-step", type=float, default=260.0)
    parser.add_argument("--player-follow-distance", type=float, default=850.0)
    parser.add_argument("--follow-player-max-distance", type=float, default=3500.0)
    parser.add_argument("--player-state-max-age", type=float, default=30.0)
    parser.add_argument("--use-skills", action="store_true", help="press usable skill/style buttons while in attack range")
    parser.add_argument("--skill-interval", type=float, default=4.0)
    parser.add_argument(
        "--action-rotation",
        choices=["auto", "none", "melee-basic", "melee-burst", "caster-basic", "healer-support", "hybrid"],
        default="auto",
        help="role-like action rotation to use when --use-skills is enabled",
    )
    parser.add_argument(
        "--skill-indexes",
        type=parse_int_list,
        default=parse_int_list("0,1,2"),
        help="comma-separated UseSkill indexes to rotate, for example 0,1,2",
    )
    parser.add_argument("--skill-type", type=int, default=1, help="UseSkill type byte. 1 means non-specialization usable skills")
    parser.add_argument("--spell-levels", type=parse_int_list, default=parse_int_list("1,2"), help="comma-separated UseSpell levels for caster/hybrid rotations")
    parser.add_argument("--spell-line-index", type=int, default=0)
    parser.add_argument("--spell-range", type=float, default=1500.0)
    parser.add_argument("--heal-spell-levels", type=parse_int_list, default=parse_int_list("1"), help="comma-separated UseSpell levels for healer-support self heal attempts")
    parser.add_argument("--heal-spell-line-index", type=int, default=0)
    parser.add_argument("--healer-self-health-percent", type=int, default=65)
    parser.add_argument("--support-spell-chance", type=float, default=0.35)
    parser.add_argument("--hybrid-melee-chance", type=float, default=0.65)
    parser.add_argument("--recovery", action="store_true", help="occasionally send /release or /pray like a player recovering from death")
    parser.add_argument("--recovery-interval", type=float, default=45.0)
    parser.add_argument("--auto-release-on-death", action="store_true", help="detect PlayerDeath packets and send /release")
    parser.add_argument("--death-release-delay", type=float, default=2.0)
    parser.add_argument("--death-recovery-cooldown", type=float, default=8.0)
    parser.add_argument("--post-release-rest", type=float, default=3.0)
    parser.add_argument("--party-size", type=int, default=1, help="group workers into leader/follower parties of this size")
    parser.add_argument("--party-invite-interval", type=float, default=10.0)
    parser.add_argument("--party-accept-interval", type=float, default=4.0)
    parser.add_argument("--party-assist-interval", type=float, default=3.0)
    parser.add_argument("--party-follow-interval", type=float, default=1.2)
    parser.add_argument("--party-follow-step", type=float, default=320.0)
    parser.add_argument("--party-follow-distance", type=float, default=550.0)
    parser.add_argument("--party-state-max-age", type=float, default=10.0)
    parser.add_argument("--party-use-assist-command", action="store_true")
    parser.add_argument(
        "--party-role-strategy",
        choices=["same", "mixed"],
        default="mixed",
        help="when action rotation is auto, assign mixed party roles by slot or use the same role for everyone",
    )
    parser.add_argument("--jitter", type=float, default=1.5)
    parser.add_argument("--tick", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=20260513)
    parser.add_argument(
        "--behavior-profile",
        choices=["custom", "solo-melee", "cautious-solo", "pve-casual", "party-tank", "party-dps"],
        default="custom",
        help="apply a bundled behavior/balance-test profile",
    )
    parser.add_argument("--metrics-csv", help="write per-account/per-round results to this CSV file")
    parser.add_argument("--combat-csv", help="write per-combat target/outcome rows to this CSV file")
    parser.add_argument("--report-md", help="write a human-readable markdown summary report")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--command",
        action="append",
        default=None,
        help="repeatable command. Use --command '' to disable defaults.",
    )
    args = parser.parse_args()

    if args.ai_player and args.behavior_profile == "custom":
        args.behavior_profile = "pve-casual"

    apply_behavior_profile(args)

    if args.hunter:
        args.combat = True
        args.move = True
        args.wander = True

    if args.think_max < args.think_min:
        raise ValueError("--think-max must be >= --think-min")

    if args.party_size < 1:
        raise ValueError("--party-size must be >= 1")

    if args.command is None:
        args.command = list(DEFAULT_COMMANDS)
    elif args.command == [""]:
        args.command = []
    else:
        args.command = [command for command in args.command if command]

    apply_ai_player_defaults(args)

    accounts = load_accounts(args.accounts, args)
    accounts = apply_realm_strategy(accounts, args)

    if not args.accounts and not args.password:
        raise SystemExit("missing password: pass --password, set OPENDAOC_PASSWORD, or use --accounts")

    if args.concurrency > len(accounts):
        raise ValueError(f"concurrency={args.concurrency} needs at least {args.concurrency} accounts; got {len(accounts)}")

    account_plans = build_account_plans(accounts, args)
    party_states = build_party_states(account_plans, args)
    results = [DummyResult(plan[0].username, ok=False, error="not started") for plan in account_plans]
    threads = [
        threading.Thread(target=run_dummy_plan, args=(index, plan, args, results, party_states[index]), daemon=True)
        for index, plan in enumerate(account_plans)
    ]

    started = time.monotonic()

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    elapsed = time.monotonic() - started
    ok_count = sum(1 for result in results if result.ok and not result.error)
    action_count = sum(result.actions for result in results)
    round_count = sum(result.rounds for result in results)
    successful_round_count = sum(result.successful_rounds for result in results)
    print(
        "dummy run completed: "
        f"ok={ok_count}/{len(results)} "
        f"rounds={successful_round_count}/{round_count} "
        f"actions={action_count} "
        f"elapsed={elapsed:.1f}s"
    )

    for result in results:
        status = "ok" if result.ok and not result.error else "failed"
        suffix = (
            f" rounds={result.successful_rounds}/{result.rounds} actions={result.actions} elapsed={result.elapsed:.1f}s"
            if result.ok
            else f" rounds={result.successful_rounds}/{result.rounds} actions={result.actions} error={result.error}"
        )
        print(f"- {result.username}: {status}{suffix}")

    if args.metrics_csv:
        write_metrics_csv(args.metrics_csv, results)
        print(f"metrics written: {args.metrics_csv}")

    if args.combat_csv:
        write_combat_csv(args.combat_csv, results)
        print(f"combat metrics written: {args.combat_csv}")

    if args.report_md:
        write_report_md(args.report_md, results, elapsed, args)
        print(f"report written: {args.report_md}")

    return 0 if ok_count == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
