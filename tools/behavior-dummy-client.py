#!/usr/bin/env python3
"""Behavior dummy runner for OpenDAoC local stress/smoke testing."""

from __future__ import annotations

import argparse
import csv
import errno
import hashlib
import importlib.util
import json
import os
import random
import re
import sys
import threading
import time
import urllib.parse
import urllib.request
import math
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from types import SimpleNamespace


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


def load_daoc_zone_heightmap_module():
    module_path = Path(__file__).with_name("daoc_zone_heightmap.py")
    spec = importlib.util.spec_from_file_location("daoc_zone_heightmap", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_daoc_lightweight_navgrid_module():
    module_path = Path(__file__).with_name("daoc_lightweight_navgrid.py")
    spec = importlib.util.spec_from_file_location("daoc_lightweight_navgrid", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


HeadlessDaocClient = load_headless_client_class()
dummy_pathing = load_dummy_pathing_module()
daoc_zone_heightmap = load_daoc_zone_heightmap_module()
daoc_lightweight_navgrid = load_daoc_lightweight_navgrid_module()
PathFollower = dummy_pathing.PathFollower
PathGraph = dummy_pathing.PathGraph
DEFAULT_DUMMY_HOST = os.environ.get("OPENDAOC_DUMMY_HOST", "192.168.0.42")
DEFAULT_PLAYER_MOVEMENT_SPEED = 191.0
DEFAULT_PLAYER_MOVEMENT_INTERVAL = 0.20
PathPoint = dummy_pathing.PathPoint
PathSafety = dummy_pathing.PathSafety
path_distance = dummy_pathing.distance


class DummyBehaviorState(str, Enum):
    Startup = "Startup"
    TravelToObjective = "TravelToObjective"
    HandleTravelAggro = "HandleTravelAggro"
    DropAggroAndRecover = "DropAggroAndRecover"
    ReturnToObjective = "ReturnToObjective"
    HuntObjective = "HuntObjective"
    RestRecover = "RestRecover"
    DeadReleaseRecover = "DeadReleaseRecover"


class TargetIntent(str, Enum):
    none = "none"
    objective = "objective"
    required_retaliation = "required_retaliation"
    party_assist = "party_assist"
    party_rescue = "party_rescue"
    travel_aggro = "travel_aggro"
    avoided_add = "avoided_add"
    current_target_confirm = "current_target_confirm"


class TargetSource(str, Enum):
    hunter_selection = "hunter_selection"
    party_assist = "party_assist"
    party_rescue = "party_rescue"
    local_rescue = "local_rescue"
    incoming_damage_counterattack = "incoming_damage_counterattack"
    leader_target_reacquire = "leader_target_reacquire"
    current_target_api_refresh = "current_target_api_refresh"
    required_retaliation = "required_retaliation"
    current_target_preserve = "current_target_preserve"


@dataclass(frozen=True)
class EngagementCandidate:
    object_id: int
    name: str
    level: int
    x: int
    y: int
    z: int
    source: TargetSource | str
    intent: TargetIntent | str
    npc: object | None = None


@dataclass(frozen=True)
class EngagementContext:
    behavior_state: DummyBehaviorState | str
    current_target: int
    current_target_intent: TargetIntent | str
    is_party_leader: bool
    is_party_follower: bool
    party_ready: bool
    leader_engaged: bool
    current_health_percent: int
    objective_home_reached: bool
    objective_hunt_ready: bool
    drop_aggro_active: bool
    rest_active: bool
    flee_active: bool


@dataclass(frozen=True)
class TargetDecision:
    allowed: bool
    candidate: EngagementCandidate
    intent: TargetIntent | str
    source: TargetSource | str
    priority: int
    reject_reason: str
    should_target_object: bool
    should_update_current_target: bool
    should_publish_party_leader_target: bool
    should_mark_leader_engaged: bool


@dataclass(frozen=True)
class TargetCommitResult:
    current_target: int
    current_target_since: float
    current_target_last_visible_at: float
    current_target_intent: TargetIntent | str
    target_object_called: bool
    current_target_updated: bool
    party_leader_target_published: bool


DEFAULT_COMMANDS = ["/worldnews"]
REALM_NAMES = {1: "Albion", 2: "Midgard", 3: "Hibernia"}
REALM_IDS_BY_NAME = {name.lower(): realm_id for realm_id, name in REALM_NAMES.items()}
TELEPORT_DESTINATION_COORDS: dict[str, tuple[int, int, int, int]] = {
    "adribard's retreat": (1, 472348, 629103, 1724),
    "avalon marsh": (1, 462144, 633058, 1739),
    "caer ulfwych": (1, 521393, 616461, 1784),
    "campacorentin station": (1, 493679, 591770, 1819),
    "castle sauvage": (1, 584151, 477177, 2600),
    "cotswold village": (1, 560574, 511800, 2280),
    "prydwen keep": (1, 574199, 528948, 2863),
    "snowdonia fortress": (1, 527543, 358900, 8320),
    "yarley's farm": (1, 369957, 679721, 5540),
    "audliten": (100, 729152, 760225, 4573),
    "fort atla": (100, 749218, 817547, 4408),
    "fort veldon": (100, 801046, 678588, 5299),
    "gotar": (100, 771152, 836380, 4624),
    "huginfell": (100, 712192, 783970, 4672),
    "mularn": (100, 803612, 726671, 4743),
    "svasud faste": (100, 767242, 669591, 5736),
    "vindsaul faste": (100, 703389, 738621, 5704),
    "west skona": (100, 712345, 923847, 5043),
    "ardagh": (200, 350446, 553634, 5120),
    "connla": (200, 295765, 642599, 4849),
    "druim cain": (200, 421264, 486315, 1824),
    "druim ligen": (200, 334342, 419994, 5184),
    "howth": (200, 343184, 592636, 5456),
    "innis carthaig": (200, 334622, 720123, 4296),
    "mag mell": (200, 346100, 491380, 5210),
    "shannon estuary": (200, 309968, 645164, 4848),
    "tir na mbeo": (200, 345698, 528897, 5448),
}
PATH_GRAPH_CACHE: dict[str, object] = {}
PATH_GRAPH_CACHE_LOCK = threading.Lock()
GROUND_Z_MAP_CACHE: dict[str, object] = {}
GROUND_Z_MAP_CACHE_LOCK = threading.Lock()
CLIENT_ZONE_ID_CACHE: dict[str, list[tuple[int, int, int, int, int]]] = {}
CLIENT_ZONE_ID_CACHE_LOCK = threading.Lock()
CLIENT_GRID_NAV_CACHE: dict[str, object] = {}
CLIENT_GRID_NAV_CACHE_LOCK = threading.Lock()
DEFAULT_SOCIAL_LINES = [
    "안녕하세요",
    "사냥 자리 지나갈게요",
    "조심하세요",
    "몹이 좀 아프네요",
    "잠깐 쉬었다 갈게요",
]
DEFAULT_PLAYER_GREET_LINES = ["안녕하세요", "수고하세요", "지나갈게요"]
DEFAULT_EMOTE_COMMANDS = ["/wave", "/bow", "/cheer", "/sit"]
RANDOM_ITEM_TIERS = ("마력", "희귀", "영웅", "전설", "신화")
LOOT_KOREAN_PATTERNS = (
    re.compile(r"^(?P<item>.+?)(?:을\(를\)|를|을)\s*얻어\s*가방에\s*넣었습니다\.?$"),
    re.compile(r"^(?P<item>.+?)(?:을\(를\)|를|을)\s*주웠습니다\.?$"),
)
LOOT_ENGLISH_PATTERNS = (
    re.compile(r"^you (?:get|pick up|pick up and put|receive)\s+(?P<item>.+?)(?:\.|$)", re.IGNORECASE),
)


def format_say_command(text: str, *, max_message_length: int = 120) -> str:
    message = " ".join(str(text or "").split())
    if not message:
        message = "..."
    return f"/say {message[:max_message_length]}"


LIVE_CONTROL_NUMERIC_FIELDS = {
    "combat_chase_max_distance": float,
    "combat_direct_move_distance": float,
    "combat_home_leash_distance": float,
    "hunter_target_api_engage_distance": float,
    "hunter_target_api_radius": float,
    "hunter_target_max_ground_z_delta": float,
    "max_target_distance": float,
    "min_target_level": int,
    "max_target_level_delta": int,
    "required_target_home_hunt_distance": float,
    "target_home_max_distance": float,
    "target_timeout": float,
}


LIVE_CONTROL_BOOL_FIELDS = {
    "allow_avoid_target_fallback",
    "current_target_api_refresh",
    "hunter_target_api_scout",
    "reject_target_on_server_los_failure",
}


def normalize_live_control_key(key: object) -> str:
    return str(key or "").strip().replace("-", "_")


def live_control_revision(payload: dict[str, object], mtime_ns: int) -> str:
    revision = payload.get("revision", payload.get("rev", ""))
    return str(revision) if str(revision).strip() else str(mtime_ns)


def read_live_control_payload(path: str) -> tuple[dict[str, object] | None, int]:
    if not path:
        return None, 0

    control_path = Path(path)
    try:
        stat = control_path.stat()
    except FileNotFoundError:
        return None, 0

    try:
        payload = json.loads(control_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, stat.st_mtime_ns

    return (payload if isinstance(payload, dict) else None), stat.st_mtime_ns


def apply_live_control_overrides(args: argparse.Namespace, payload: dict[str, object]) -> dict[str, tuple[object, object]]:
    updates: dict[str, tuple[object, object]] = {}
    normalized = {normalize_live_control_key(key): value for key, value in payload.items()}

    for field, caster in LIVE_CONTROL_NUMERIC_FIELDS.items():
        if field not in normalized:
            continue
        try:
            value = caster(normalized[field])
        except (TypeError, ValueError):
            continue
        if field == "min_target_level" and "baseline_min_target_level" in normalized:
            try:
                value = max(value, caster(normalized["baseline_min_target_level"]))
            except (TypeError, ValueError):
                pass
        if field == "max_target_level_delta" and "baseline_max_target_level" in normalized:
            try:
                baseline_max = int(normalized["baseline_max_target_level"])
                player_level = int(getattr(args, "player_level", 0) or 0)
                if player_level > 0:
                    value = min(value, baseline_max - player_level)
            except (TypeError, ValueError):
                pass
        previous = getattr(args, field, None)
        if previous != value:
            setattr(args, field, value)
            updates[field] = (previous, value)

    for field in LIVE_CONTROL_BOOL_FIELDS:
        if field not in normalized:
            continue
        value = bool(normalized[field])
        previous = getattr(args, field, None)
        if previous != value:
            setattr(args, field, value)
            updates[field] = (previous, value)

    return updates


@dataclass(frozen=True)
class DummyAccount:
    username: str
    password: str
    realm: int
    char_index: int
    class_id: int | None = None
    class_name: str = ""
    specs: str = ""
    start_x: int | None = None
    start_y: int | None = None
    start_z: int | None = None
    zone_id: int | None = None


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
    loot_metrics: list["LootMetric"] | None = None
    damage_done: int = 0
    damage_taken: int = 0
    healing_done: int = 0
    healing_received: int = 0
    class_id: int | None = None
    class_name: str = ""
    specs: str = ""


@dataclass(frozen=True)
class LootMetric:
    item_name: str
    tier: str = "일반"


@dataclass(frozen=True)
class PartyAttackMessage:
    attacker_name: str
    victim_name: str


@dataclass(frozen=True)
class UsableSkillRef:
    use_skill_index: int
    use_skill_type: int
    name: str
    level: int


@dataclass(frozen=True)
class UsableSpellRef:
    line_index: int
    spell_level: int
    name: str
    level: int
    use_skill_index: int = -1
    use_skill_type: int = 1


@dataclass(frozen=True)
class CombatUsablePlan:
    skills: list[UsableSkillRef] = field(default_factory=list)
    taunt_skills: list[UsableSkillRef] = field(default_factory=list)
    attack_spells: list[UsableSpellRef] = field(default_factory=list)
    heal_spells: list[UsableSpellRef] = field(default_factory=list)
    buff_spells: list[UsableSpellRef] = field(default_factory=list)


@dataclass(frozen=True)
class RequiredTargetObservation:
    object_id: int
    name: str
    x: int
    y: int
    z: int
    level: int
    flags: int = 0
    last_seen: float = 0.0
    health_percent: float = 0.0
    health: int = 0
    max_health: int = 0
    is_alive: bool = True
    in_combat: bool = False
    has_aggro: bool = False
    target: str = ""


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


POST_ABANDON_TARGET_REMOVED_OUTCOMES = frozenset(
    {
        "critical_health_drop_aggro",
        "flee",
        "travel_aggro_drop",
    }
)
POST_ABANDON_TARGET_REMOVED_GRACE_SECONDS = 8.0


def promote_recent_finished_combat_to_target_removed(
    metric: CombatMetric,
    *,
    finished_at: float,
    now: float,
    damage_done: int,
    grace_seconds: float = POST_ABANDON_TARGET_REMOVED_GRACE_SECONDS,
) -> bool:
    if metric.outcome not in POST_ABANDON_TARGET_REMOVED_OUTCOMES:
        return False
    if damage_done <= 0:
        return False
    if now - finished_at > grace_seconds:
        return False

    metric.duration += max(0.0, now - finished_at)
    metric.outcome = "target_removed"
    return True


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
    client_grid: object | None = None
    follower: object = field(default_factory=PathFollower)
    destination_key: str = ""
    last_plan_at: float = 0.0
    last_reason: str = ""
    resolved_goal: object | None = None
    navmesh_unavailable_regions: set[int] = field(default_factory=set)


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
    def __init__(
        self,
        leader_name: str,
        member_names: list[str],
        *,
        active_tank_handoff_health_percent: int = 0,
    ) -> None:
        self.leader_name = leader_name
        self.member_names = member_names
        self.active_tank_handoff_health_percent = max(0, int(active_tank_handoff_health_percent or 0))
        self.lock = threading.Lock()
        self.leader_session_id = 0
        self.leader_object_id = 0
        self.leader_x = 0
        self.leader_y = 0
        self.leader_z = 0
        self.leader_heading = 0
        self.leader_health_percent = 100
        self.leader_target_id = 0
        self.leader_target_name = ""
        self.leader_target_x = 0
        self.leader_target_y = 0
        self.leader_target_z = 0
        self.leader_target_health_percent = 0.0
        self.leader_target_health = 0
        self.leader_target_max_health = 0
        self.leader_target_updated_at = 0.0
        self.leader_target_engaged_at = 0.0
        self.leader_target_focus_name = ""
        self.leader_target_focus_updated_at = 0.0
        self.objective_complete_target_id = 0
        self.objective_complete_name = ""
        self.objective_completed_at = 0.0
        self.member_object_ids: dict[str, int] = {name: 0 for name in member_names}
        self.member_health_percents: dict[str, int] = {name: 100 for name in member_names}
        self.member_positions: dict[str, tuple[int, int, int]] = {name: (0, 0, 0) for name in member_names}
        self.member_roles: dict[str, str] = {name: "" for name in member_names}
        self.rescue_target_id = 0
        self.rescue_target_name = ""
        self.rescue_target_x = 0
        self.rescue_target_y = 0
        self.rescue_target_z = 0
        self.rescue_target_level = 0
        self.rescue_target_objective_add = False
        self.rescue_member_name = ""
        self.rescue_requested_at = 0.0
        self.rescue_threats: dict[int, dict[str, int | float | str | bool]] = {}
        self.ready_names = {leader_name}
        self.encounter_death_count = 0
        self.last_encounter_death_at = 0.0
        self.updated_at = 0.0

    def update_leader(self, client, target=None, *, engaged: bool = False) -> None:
        with self.lock:
            self.leader_session_id = client.session_id
            self.leader_object_id = getattr(client, "player_object_id", 0)
            self.leader_x = client.x
            self.leader_y = client.y
            self.leader_z = client.z
            self.leader_heading = client.heading
            self.leader_health_percent = getattr(client, "health_percent", 100)
            self._update_member_locked(self.leader_name, client)

            if target is not None:
                self._update_leader_target_locked(target, engaged=engaged)

            self.updated_at = time.monotonic()

    def _update_leader_target_locked(self, target, engaged: bool = False) -> None:
        target_id = int(getattr(target, "object_id", 0) or 0)
        target_name = str(getattr(target, "name", "") or "")
        target_x = int(getattr(target, "x", 0) or 0)
        target_y = int(getattr(target, "y", 0) or 0)
        target_z = int(getattr(target, "z", 0) or 0)
        target_health_percent = float(getattr(target, "health_percent", 0.0) or 0.0)
        target_health = int(getattr(target, "health", 0) or 0)
        target_max_health = int(getattr(target, "max_health", 0) or 0)
        target_changed = self.leader_target_id != target_id
        position_changed = (
            self.leader_target_x != target_x
            or self.leader_target_y != target_y
            or self.leader_target_z != target_z
        )

        if target_changed or position_changed:
            self.leader_target_updated_at = time.monotonic()

        if target_changed:
            self.leader_target_engaged_at = 0.0
            self.leader_target_focus_name = ""
            self.leader_target_focus_updated_at = 0.0
            self.encounter_death_count = 0
            self.last_encounter_death_at = 0.0

        self.leader_target_id = target_id
        self.leader_target_name = target_name
        self.leader_target_x = target_x
        self.leader_target_y = target_y
        self.leader_target_z = target_z
        self.leader_target_health_percent = target_health_percent
        self.leader_target_health = target_health
        self.leader_target_max_health = target_max_health

        if engaged and self.leader_target_engaged_at <= 0.0:
            self.leader_target_engaged_at = time.monotonic()

        focus_name = str(getattr(target, "target", "") or "").strip()
        if focus_name:
            self.leader_target_focus_name = focus_name
            self.leader_target_focus_updated_at = time.monotonic()

    def update_shared_target(self, target, engaged: bool = False) -> None:
        with self.lock:
            if self.objective_completed_at > 0.0:
                return

            self._update_leader_target_locked(target, engaged=engaged)
            self.updated_at = time.monotonic()

    def update_leader_target_focus_from_attack(self, attacker_name: str, victim_name: str) -> bool:
        with self.lock:
            if self.leader_target_id <= 0:
                return False

            normalized_attacker = normalize_target_name(attacker_name)
            normalized_target = normalize_target_name(self.leader_target_name)
            if not normalized_attacker or not normalized_target:
                return False

            if normalized_attacker != normalized_target and normalized_attacker not in normalized_target and normalized_target not in normalized_attacker:
                return False

            if victim_name not in self.member_names:
                return False

            self.leader_target_focus_name = victim_name
            self.leader_target_focus_updated_at = time.monotonic()
            self.updated_at = self.leader_target_focus_updated_at
            return True

    def _update_member_locked(self, member_name: str, client) -> None:
        if member_name not in self.member_names:
            return

        previous_health_percent = self.member_health_percents.get(member_name, 100)
        health_percent = int(getattr(client, "health_percent", 100) or 0)
        self.member_object_ids[member_name] = int(getattr(client, "player_object_id", 0) or 0)
        self.member_health_percents[member_name] = health_percent
        self.member_positions[member_name] = (
            int(getattr(client, "x", 0) or 0),
            int(getattr(client, "y", 0) or 0),
            int(getattr(client, "z", 0) or 0),
        )
        if self.leader_target_id > 0 and previous_health_percent > 0 and health_percent <= 0:
            self.encounter_death_count += 1
            self.last_encounter_death_at = time.monotonic()

    def update_member(self, member_name: str, client) -> None:
        with self.lock:
            self._update_member_locked(member_name, client)
            self.updated_at = time.monotonic()

    def update_member_role(self, member_name: str, role: str) -> None:
        with self.lock:
            if member_name in self.member_names:
                self.member_roles[member_name] = role
            self.updated_at = time.monotonic()

    def _is_tank_role_locked(self, member_name: str) -> bool:
        role = self.member_roles.get(member_name, "")
        return member_name == self.leader_name or role in {"melee-basic", "melee-burst", "hybrid"}

    def _active_tank_locked(self) -> dict[str, int | str]:
        candidates: list[tuple[int, int, str, int, int, int, int]] = []

        for order, member_name in enumerate(self.member_names):
            object_id = self.member_object_ids.get(member_name, 0)
            health_percent = self.member_health_percents.get(member_name, 0)

            if not object_id or health_percent <= 0 or not self._is_tank_role_locked(member_name):
                continue

            x, y, z = self.member_positions.get(member_name, (0, 0, 0))
            priority = 0 if member_name == self.leader_name else 1
            candidates.append((priority, order, member_name, object_id, health_percent, x, y, z))

        if not candidates:
            return {"name": "", "object_id": 0, "health_percent": 0, "x": 0, "y": 0, "z": 0}

        handoff_threshold = self.active_tank_handoff_health_percent
        healthy_tank_available = handoff_threshold > 0 and any(
            health_percent > handoff_threshold
            for _priority, _order, _member_name, _object_id, health_percent, _x, _y, _z in candidates
        )

        _, _, _, member_name, object_id, health_percent, x, y, z = min(
            (
                (
                    1 if healthy_tank_available and health_percent <= handoff_threshold else 0,
                    priority,
                    order,
                    member_name,
                    object_id,
                    health_percent,
                    x,
                    y,
                    z,
                )
                for priority, order, member_name, object_id, health_percent, x, y, z in candidates
            )
        )
        return {
            "name": member_name,
            "object_id": object_id,
            "health_percent": health_percent,
            "x": x,
            "y": y,
            "z": z,
        }

    def _rescue_tank_locked(self) -> dict[str, int | str]:
        candidates: list[tuple[int, int, str, int, int, int, int]] = []

        for order, member_name in enumerate(self.member_names):
            object_id = self.member_object_ids.get(member_name, 0)
            health_percent = self.member_health_percents.get(member_name, 0)

            if not object_id or health_percent <= 0 or not self._is_tank_role_locked(member_name):
                continue

            x, y, z = self.member_positions.get(member_name, (0, 0, 0))
            priority = 1 if member_name == self.leader_name else 0
            candidates.append((priority, order, member_name, object_id, health_percent, x, y, z))

        if not candidates:
            return {"name": "", "object_id": 0, "health_percent": 0, "x": 0, "y": 0, "z": 0}

        _, _, member_name, object_id, health_percent, x, y, z = min(candidates)
        return {
            "name": member_name,
            "object_id": object_id,
            "health_percent": health_percent,
            "x": x,
            "y": y,
            "z": z,
        }

    def active_tank(self) -> dict[str, int | str]:
        with self.lock:
            return self._active_tank_locked()

    def rescue_tank(self) -> dict[str, int | str]:
        with self.lock:
            return self._rescue_tank_locked()

    def lowest_hurt_member(self, max_health_percent: int, exclude_name: str = "") -> dict[str, int | str] | None:
        with self.lock:
            candidates: list[tuple[int, str, int, int, int, int]] = []

            for member_name in self.member_names:
                if member_name == exclude_name:
                    continue

                object_id = self.member_object_ids.get(member_name, 0)
                health_percent = self.member_health_percents.get(member_name, 100)

                if object_id and 0 < health_percent <= max_health_percent:
                    x, y, z = self.member_positions.get(member_name, (0, 0, 0))
                    candidates.append((health_percent, member_name, object_id, x, y, z))

            if not candidates:
                return None

            health_percent, member_name, object_id, x, y, z = min(candidates)
            return {
                "name": member_name,
                "object_id": object_id,
                "health_percent": health_percent,
                "x": x,
                "y": y,
                "z": z,
            }

    def focused_hurt_member(self, max_health_percent: int, exclude_name: str = "") -> dict[str, int | str] | None:
        with self.lock:
            focus_name = normalize_target_name(self.leader_target_focus_name)
            if not focus_name:
                return None

            for member_name in self.member_names:
                if member_name == exclude_name or normalize_target_name(member_name) != focus_name:
                    continue

                object_id = self.member_object_ids.get(member_name, 0)
                health_percent = self.member_health_percents.get(member_name, 100)
                if object_id and 0 < health_percent <= max_health_percent:
                    x, y, z = self.member_positions.get(member_name, (0, 0, 0))
                    return {
                        "name": member_name,
                        "object_id": object_id,
                        "health_percent": health_percent,
                        "x": x,
                        "y": y,
                        "z": z,
                    }

            return None

    def buff_targets(self, exclude_name: str = "") -> list[dict[str, int | str]]:
        with self.lock:
            targets: list[dict[str, int | str]] = []

            for member_name in self.member_names:
                if member_name == exclude_name:
                    continue

                object_id = self.member_object_ids.get(member_name, 0)

                if object_id:
                    targets.append({"name": member_name, "object_id": object_id})

            return targets

    def request_rescue(
        self,
        member_name: str,
        attacker,
        leader_target_id: int = 0,
        min_hold: float = 0.0,
        objective_add: bool = False,
    ) -> bool:
        attacker_id = int(getattr(attacker, "object_id", 0) or 0)

        if not attacker_id or attacker_id == leader_target_id:
            return False

        with self.lock:
            if member_name not in self.member_names:
                return False

            now = time.monotonic()
            if (
                self.rescue_target_id
                and self.rescue_target_id != attacker_id
                and min_hold > 0
                and now - self.rescue_requested_at < min_hold
            ):
                self._record_rescue_threat_locked(member_name, attacker, objective_add=objective_add, now=now)
                self.updated_at = now
                return False

            if self.rescue_target_id == attacker_id:
                self.rescue_target_name = str(getattr(attacker, "name", ""))
                self.rescue_target_x = int(getattr(attacker, "x", 0) or 0)
                self.rescue_target_y = int(getattr(attacker, "y", 0) or 0)
                self.rescue_target_z = int(getattr(attacker, "z", 0) or 0)
                self.rescue_target_level = int(getattr(attacker, "level", 0) or 0)
                self.rescue_target_objective_add = self.rescue_target_objective_add or objective_add
                self._record_rescue_threat_locked(member_name, attacker, objective_add=objective_add, now=now)
                self.updated_at = now
                return True

            self.rescue_target_id = attacker_id
            self.rescue_target_name = str(getattr(attacker, "name", ""))
            self.rescue_target_x = int(getattr(attacker, "x", 0) or 0)
            self.rescue_target_y = int(getattr(attacker, "y", 0) or 0)
            self.rescue_target_z = int(getattr(attacker, "z", 0) or 0)
            self.rescue_target_level = int(getattr(attacker, "level", 0) or 0)
            self.rescue_target_objective_add = objective_add
            self.rescue_member_name = member_name
            self.rescue_requested_at = now
            self._record_rescue_threat_locked(member_name, attacker, objective_add=objective_add, now=now)
            self.updated_at = self.rescue_requested_at
            return True

    def _record_rescue_threat_locked(
        self,
        member_name: str,
        attacker,
        objective_add: bool = False,
        now: float | None = None,
    ) -> bool:
        attacker_id = int(getattr(attacker, "object_id", 0) or 0)
        if not attacker_id:
            return False

        now = time.monotonic() if now is None else now
        self.rescue_threats[attacker_id] = {
            "object_id": attacker_id,
            "name": str(getattr(attacker, "name", "")),
            "x": int(getattr(attacker, "x", 0) or 0),
            "y": int(getattr(attacker, "y", 0) or 0),
            "z": int(getattr(attacker, "z", 0) or 0),
            "level": int(getattr(attacker, "level", 0) or 0),
            "member_name": member_name,
            "requested_at": now,
            "objective_add": bool(objective_add),
        }
        return True

    def record_rescue_threat(self, member_name: str, attacker, objective_add: bool = False) -> bool:
        with self.lock:
            if member_name not in self.member_names:
                return False

            recorded = self._record_rescue_threat_locked(member_name, attacker, objective_add=objective_add)
            if recorded:
                self.updated_at = time.monotonic()
            return recorded

    def clear_rescue_target(self, target_id: int = 0) -> None:
        with self.lock:
            if target_id and self.rescue_target_id != target_id:
                return

            self.rescue_target_id = 0
            self.rescue_target_name = ""
            self.rescue_target_x = 0
            self.rescue_target_y = 0
            self.rescue_target_z = 0
            self.rescue_target_level = 0
            self.rescue_target_objective_add = False
            self.rescue_member_name = ""
            self.rescue_requested_at = 0.0
            if target_id:
                self.rescue_threats.pop(target_id, None)
            self.updated_at = time.monotonic()

    def mark_leader_target_engaged(self, target_id: int) -> None:
        with self.lock:
            if self.leader_target_id == target_id and self.leader_target_engaged_at <= 0.0:
                self.leader_target_engaged_at = time.monotonic()
            self.updated_at = time.monotonic()

    def clear_leader_target(self) -> None:
        with self.lock:
            self.leader_target_id = 0
            self.leader_target_name = ""
            self.leader_target_x = 0
            self.leader_target_y = 0
            self.leader_target_z = 0
            self.leader_target_health_percent = 0.0
            self.leader_target_health = 0
            self.leader_target_max_health = 0
            self.leader_target_updated_at = 0.0
            self.leader_target_engaged_at = 0.0
            self.leader_target_focus_name = ""
            self.leader_target_focus_updated_at = 0.0
            self.updated_at = time.monotonic()

    def mark_objective_complete(self, target_id: int, target_name: str = "") -> None:
        with self.lock:
            if self.objective_completed_at <= 0.0:
                self.objective_completed_at = time.monotonic()
                self.objective_complete_target_id = int(target_id or 0)
                self.objective_complete_name = str(target_name or "")

            self.leader_target_id = 0
            self.leader_target_name = ""
            self.leader_target_x = 0
            self.leader_target_y = 0
            self.leader_target_z = 0
            self.leader_target_health_percent = 0.0
            self.leader_target_health = 0
            self.leader_target_max_health = 0
            self.leader_target_updated_at = 0.0
            self.leader_target_engaged_at = 0.0
            self.leader_target_focus_name = ""
            self.leader_target_focus_updated_at = 0.0
            self.rescue_target_id = 0
            self.rescue_target_name = ""
            self.rescue_target_x = 0
            self.rescue_target_y = 0
            self.rescue_target_z = 0
            self.rescue_target_level = 0
            self.rescue_target_objective_add = False
            self.rescue_member_name = ""
            self.rescue_requested_at = 0.0
            self.rescue_threats.clear()
            self.updated_at = time.monotonic()

    def mark_ready(self, member_name: str) -> None:
        with self.lock:
            if member_name in self.member_names:
                self.ready_names.add(member_name)
            self.updated_at = time.monotonic()

    def clear_ready(self, member_name: str) -> None:
        with self.lock:
            if member_name != self.leader_name:
                self.ready_names.discard(member_name)
            self.updated_at = time.monotonic()

    def snapshot(self) -> dict[str, int | float | str]:
        with self.lock:
            active_tank = self._active_tank_locked()
            rescue_tank = self._rescue_tank_locked()
            return {
                "leader_name": self.leader_name,
                "leader_session_id": self.leader_session_id,
                "leader_object_id": self.leader_object_id,
                "leader_x": self.leader_x,
                "leader_y": self.leader_y,
                "leader_z": self.leader_z,
                "leader_heading": self.leader_heading,
                "leader_health_percent": self.leader_health_percent,
                "leader_target_id": self.leader_target_id,
                "leader_target_name": self.leader_target_name,
                "leader_target_x": self.leader_target_x,
                "leader_target_y": self.leader_target_y,
                "leader_target_z": self.leader_target_z,
                "leader_target_health_percent": self.leader_target_health_percent,
                "leader_target_health": self.leader_target_health,
                "leader_target_max_health": self.leader_target_max_health,
                "leader_target_updated_at": self.leader_target_updated_at,
                "leader_target_engaged_at": self.leader_target_engaged_at,
                "leader_target_focus_name": self.leader_target_focus_name,
                "leader_target_focus_updated_at": self.leader_target_focus_updated_at,
                "objective_complete_target_id": self.objective_complete_target_id,
                "objective_complete_name": self.objective_complete_name,
                "objective_completed_at": self.objective_completed_at,
                "active_tank_name": active_tank["name"],
                "active_tank_object_id": active_tank["object_id"],
                "active_tank_health_percent": active_tank["health_percent"],
                "active_tank_x": active_tank["x"],
                "active_tank_y": active_tank["y"],
                "active_tank_z": active_tank["z"],
                "rescue_tank_name": rescue_tank["name"],
                "rescue_tank_object_id": rescue_tank["object_id"],
                "rescue_tank_health_percent": rescue_tank["health_percent"],
                "rescue_tank_x": rescue_tank["x"],
                "rescue_tank_y": rescue_tank["y"],
                "rescue_tank_z": rescue_tank["z"],
                "rescue_target_id": self.rescue_target_id,
                "rescue_target_name": self.rescue_target_name,
                "rescue_target_x": self.rescue_target_x,
                "rescue_target_y": self.rescue_target_y,
                "rescue_target_z": self.rescue_target_z,
                "rescue_target_level": self.rescue_target_level,
                "rescue_target_objective_add": self.rescue_target_objective_add,
                "rescue_member_name": self.rescue_member_name,
                "rescue_requested_at": self.rescue_requested_at,
                "rescue_threats": list(self.rescue_threats.values()),
                "members": [
                    {
                        "name": member_name,
                        "object_id": self.member_object_ids.get(member_name, 0),
                        "health_percent": self.member_health_percents.get(member_name, 0),
                        "x": self.member_positions.get(member_name, (0, 0, 0))[0],
                        "y": self.member_positions.get(member_name, (0, 0, 0))[1],
                        "z": self.member_positions.get(member_name, (0, 0, 0))[2],
                        "role": self.member_roles.get(member_name, ""),
                    }
                    for member_name in self.member_names
                ],
                "ready_names": list(self.ready_names),
                "encounter_death_count": self.encounter_death_count,
                "last_encounter_death_at": self.last_encounter_death_at,
                "ready_count": len(self.ready_names),
                "updated_at": self.updated_at,
            }


def party_ready_for_pull(args: argparse.Namespace, party_state: PartyState | None) -> bool:
    if party_state is None or getattr(args, "party_min_ready", 0) <= 0:
        return True

    snapshot = party_state.snapshot()
    max_leader_distance = float(getattr(args, "party_ready_max_leader_distance", 0.0) or 0.0)
    if max_leader_distance <= 0.0:
        return int(snapshot["ready_count"]) >= args.party_min_ready

    ready_names = set(snapshot.get("ready_names", []) or [])
    leader_name = str(snapshot.get("leader_name", "") or "")
    leader_x = int(snapshot.get("leader_x", 0) or 0)
    leader_y = int(snapshot.get("leader_y", 0) or 0)
    near_ready_count = 1 if leader_name in ready_names else 0
    for member in snapshot.get("members", []) or []:
        member_name = str(member.get("name", "") or "")
        if member_name == leader_name or member_name not in ready_names:
            continue
        if int(member.get("object_id", 0) or 0) <= 0 or int(member.get("health_percent", 0) or 0) <= 0:
            continue
        distance = horizontal_distance_between_points(
            leader_x,
            leader_y,
            int(member.get("x", 0) or 0),
            int(member.get("y", 0) or 0),
        )
        if distance <= max_leader_distance:
            near_ready_count += 1

    return near_ready_count >= args.party_min_ready


def party_ready_count(party_state: PartyState | None) -> int:
    if party_state is None:
        return 0

    return int(party_state.snapshot()["ready_count"])


def party_member_ready_for_pull(client, args: argparse.Namespace) -> bool:
    if required_target_home_destination(args) is None:
        return True

    if required_target_home_reached(client, args):
        return True

    if (
        int(getattr(args, "party_size", 0) or 0) > 1
        and getattr(args, "party_assist_only", False)
        and float(getattr(args, "party_pre_pull_home_stop_distance", 0.0) or 0.0) > 0.0
    ):
        hunt_distance = float(getattr(args, "required_target_home_hunt_distance", 0.0) or 0.0)
        if hunt_distance <= 0.0:
            hunt_distance = float(getattr(args, "target_home_max_distance", 0.0) or 0.0)
        if hunt_distance > 0.0 and required_target_home_distance(client, args) <= hunt_distance:
            return True

    return required_target_home_hunt_ready(client, args)


def should_mark_party_ready_after_follow(
    client,
    args: argparse.Namespace,
    *,
    is_party_follower: bool,
    current_target: int,
) -> bool:
    return bool(is_party_follower and party_member_ready_for_pull(client, args))


def should_start_party_form_up_delay(
    args: argparse.Namespace,
    party_state: PartyState | None,
    *,
    is_party_leader: bool,
    current_target: int,
) -> bool:
    return bool(
        should_approach_required_target_home(args, is_party_leader=is_party_leader, current_target=current_target)
        and int(getattr(args, "party_min_ready", 0) or 0) > 0
        and party_ready_for_pull(args, party_state)
        and float(getattr(args, "party_form_up_delay", 0.0) or 0.0) > 0.0
    )


def should_suppress_party_follower_waypoint(
    args: argparse.Namespace,
    party_state: PartyState | None,
    *,
    is_party_follower: bool,
    current_target: int,
) -> bool:
    return bool(
        is_party_follower
        and party_state is not None
        and current_target <= 0
        and getattr(args, "party_assist_only", False)
        and int(getattr(args, "party_min_ready", 0) or 0) > 0
    )


def initial_behavior_state_for_objective(
    client,
    args: argparse.Namespace,
    *,
    is_party_leader: bool,
    current_target: int,
) -> DummyBehaviorState:
    if current_target > 0:
        return DummyBehaviorState.HuntObjective

    if required_target_home_destination(args) is None:
        return DummyBehaviorState.HuntObjective

    if is_party_leader or int(getattr(args, "party_size", 0) or 0) == 1:
        if should_approach_required_target_home(
            args,
            is_party_leader=is_party_leader,
            current_target=current_target,
        ) and not required_target_home_hunt_ready(client, args):
            return DummyBehaviorState.TravelToObjective
        return DummyBehaviorState.HuntObjective

    return DummyBehaviorState.TravelToObjective


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
    require_tokens = [token.strip().lower() for token in getattr(args, "require_target_name", "").split(",") if token.strip()]
    avoid_tokens = [token.strip().lower() for token in args.avoid_target_name.split(",") if token.strip()]
    target_home = getattr(args, "required_target_home", None)
    target_home_max_distance = float(getattr(args, "target_home_max_distance", 0.0) or 0.0)

    def within_target_home(npc) -> bool:
        if target_home is None or target_home_max_distance <= 0.0:
            return True

        return (
            horizontal_distance_between_points(
                int(getattr(target_home, "x", 0) or 0),
                int(getattr(target_home, "y", 0) or 0),
                int(getattr(npc, "x", 0) or 0),
                int(getattr(npc, "y", 0) or 0),
            )
            <= target_home_max_distance
        )

    def is_avoided(npc) -> bool:
        return any(token in npc.name.lower() for token in avoid_tokens)

    def ground_z_ok(npc) -> bool:
        return hunter_target_ground_z_aligned(args, client, npc)

    def candidate_npcs(*, allow_avoided: bool) -> list[object]:
        return [
            npc
            for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
            if rejected_targets.get(npc.object_id, 0.0) <= now
            and rejected_target_kinds.get((npc.name.lower(), npc.level), 0.0) <= now
            and npc.level >= args.min_target_level
            and npc.level <= max_level
            and (args.max_target_distance <= 0 or combat_distance_to(client, npc) <= args.max_target_distance)
            and within_target_home(npc)
            and (not require_tokens or any(token in npc.name.lower() for token in require_tokens))
            and ground_z_ok(npc)
            and (allow_avoided or not is_avoided(npc))
        ]

    candidates = candidate_npcs(allow_avoided=False)
    if not candidates and getattr(args, "allow_avoid_target_fallback", False):
        candidates = candidate_npcs(allow_avoided=True)

    if candidates and prefer_tokens and getattr(args, "target_auto_lowest_visible_level", False):
        preferred_candidates = [npc for npc in candidates if any(token in npc.name.lower() for token in prefer_tokens)]
        if preferred_candidates:
            preferred_candidates.sort(key=lambda npc: (npc.level, combat_distance_to(client, npc)))
            return preferred_candidates[0]
        if not preferred_candidates:
            fallback_candidates = [
                npc
                for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
                if rejected_targets.get(npc.object_id, 0.0) <= now
                and rejected_target_kinds.get((npc.name.lower(), npc.level), 0.0) <= now
                and npc.level >= args.min_target_level
                and npc.level <= max_level
                and (args.max_target_distance <= 0 or combat_distance_to(client, npc) <= args.max_target_distance)
                and within_target_home(npc)
                and (not require_tokens or any(token in npc.name.lower() for token in require_tokens))
                and ground_z_ok(npc)
                and not any(token in npc.name.lower() for token in avoid_tokens)
            ]
            if fallback_candidates:
                fallback_candidates.sort(key=lambda npc: (npc.level, combat_distance_to(client, npc)))
                return fallback_candidates[0]

    if not candidates:
        if not getattr(args, "target_auto_lowest_visible_level", False):
            return None

        fallback_candidates = [
            npc
            for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
            if rejected_targets.get(npc.object_id, 0.0) <= now
            and rejected_target_kinds.get((npc.name.lower(), npc.level), 0.0) <= now
            and npc.level >= args.min_target_level
            and npc.level <= max_level
            and (args.max_target_distance <= 0 or combat_distance_to(client, npc) <= args.max_target_distance)
            and within_target_home(npc)
            and (not require_tokens or any(token in npc.name.lower() for token in require_tokens))
            and ground_z_ok(npc)
            and not any(token in npc.name.lower() for token in avoid_tokens)
        ]

        if not fallback_candidates:
            if getattr(args, "allow_preferred_low_con_fallback", False) and prefer_tokens:
                preferred_low_con_candidates = [
                    npc
                    for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
                    if rejected_targets.get(npc.object_id, 0.0) <= now
                    and rejected_target_kinds.get((npc.name.lower(), npc.level), 0.0) <= now
                    and any(token in npc.name.lower() for token in prefer_tokens)
                    and preferred_low_con_fallback_allowed(args, client, npc)
                    and (not require_tokens or any(token in npc.name.lower() for token in require_tokens))
                    and ground_z_ok(npc)
                    and not any(token in npc.name.lower() for token in avoid_tokens)
                ]
                if preferred_low_con_candidates:
                    preferred_low_con_candidates.sort(key=lambda npc: (combat_distance_to(client, npc), npc.level))
                    return preferred_low_con_candidates[0]
            return None

        fallback_candidates.sort(key=lambda npc: (npc.level, combat_distance_to(client, npc)))
        return fallback_candidates[0]

    nearest_candidates = sorted(candidates, key=lambda npc: combat_distance_to(client, npc))
    pool = nearest_candidates[: max(args.target_pool, 1)]

    if args.target_selection == "random":
        return rng.choice(pool)

    def score(npc) -> float:
        distance = combat_distance_to(client, npc)
        level_delta = abs(npc.level - ideal_level)
        value = 1000.0
        value -= level_delta * args.target_level_weight
        value -= distance / max(args.target_distance_weight, 1.0)

        if npc.level < args.min_target_level:
            value -= 500.0

        if prefer_tokens and any(token in npc.name.lower() for token in prefer_tokens):
            value += args.prefer_target_bonus

        if is_avoided(npc):
            value -= args.prefer_target_bonus * 2.0

        value += rng.uniform(0.0, args.target_randomness)
        return value

    if args.target_selection == "nearest":
        return min(pool, key=lambda npc: combat_distance_to(client, npc))

    return max(pool, key=score)


def hunter_target_scan_snapshot(
    client,
    args: argparse.Namespace,
    rejected_targets: dict[int, float],
    rejected_target_kinds: dict[tuple[str, int], float],
    now: float,
    *,
    limit: int = 5,
) -> dict[str, object]:
    max_level = args.max_target_level if args.max_target_level >= 0 else args.player_level + args.max_target_level_delta
    prefer_tokens = [token.strip().lower() for token in args.prefer_target_name.split(",") if token.strip()]
    require_tokens = [token.strip().lower() for token in getattr(args, "require_target_name", "").split(",") if token.strip()]
    avoid_tokens = [token.strip().lower() for token in args.avoid_target_name.split(",") if token.strip()]
    target_home = getattr(args, "required_target_home", None)
    target_home_max_distance = float(getattr(args, "target_home_max_distance", 0.0) or 0.0)
    visible = client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
    counts = {
        "visible": len(visible),
        "rejected_recent": 0,
        "kind_rejected_recent": 0,
        "level": 0,
        "distance": 0,
        "home": 0,
        "require_name": 0,
        "avoid_name": 0,
        "ground_z": 0,
        "eligible": 0,
    }

    def home_distance(npc) -> float:
        if target_home is None:
            return 0.0

        return horizontal_distance_between_points(
            int(getattr(target_home, "x", 0) or 0),
            int(getattr(target_home, "y", 0) or 0),
            int(getattr(npc, "x", 0) or 0),
            int(getattr(npc, "y", 0) or 0),
        )

    def compact(npc, *, reason: str = "") -> dict[str, object]:
        item: dict[str, object] = {
            "id": int(getattr(npc, "object_id", 0) or 0),
            "name": str(getattr(npc, "name", "") or ""),
            "level": int(getattr(npc, "level", 0) or 0),
            "distance": round(combat_distance_to(client, npc), 1),
            "home_distance": round(home_distance(npc), 1),
            "flags": int(getattr(npc, "flags", 0) or 0),
            "x": int(getattr(npc, "x", 0) or 0),
            "y": int(getattr(npc, "y", 0) or 0),
            "z": int(getattr(npc, "z", 0) or 0),
        }
        ground_delta = hunter_target_ground_z_delta(args, client, npc)
        if ground_delta is not None:
            item["ground_z_delta"] = round(ground_delta, 1)
        if reason:
            item["reason"] = reason
        return item

    nearest_visible = [compact(npc) for npc in visible[:limit]]
    eligible = []
    nearest_rejected = []
    for npc in visible:
        reason = ""
        name = npc.name.lower()
        distance = combat_distance_to(client, npc)
        npc_home_distance = home_distance(npc)

        if rejected_targets.get(npc.object_id, 0.0) > now:
            counts["rejected_recent"] += 1
            reason = "rejected_recent"
        elif rejected_target_kinds.get((name, npc.level), 0.0) > now:
            counts["kind_rejected_recent"] += 1
            reason = "kind_rejected_recent"
        elif args.max_target_distance > 0 and distance > args.max_target_distance:
            counts["distance"] += 1
            reason = "distance"
        elif npc.level < args.min_target_level or npc.level > max_level:
            counts["level"] += 1
            reason = "level"
        elif target_home_max_distance > 0 and npc_home_distance > target_home_max_distance:
            counts["home"] += 1
            reason = "home"
        elif require_tokens and not any(token in name for token in require_tokens):
            counts["require_name"] += 1
            reason = "require_name"
        elif any(token in name for token in avoid_tokens):
            counts["avoid_name"] += 1
            reason = "avoid_name"
        elif not hunter_target_ground_z_aligned(args, client, npc):
            counts["ground_z"] += 1
            reason = "ground_z"
        else:
            eligible.append(npc)
            continue

        if len(nearest_rejected) < limit:
            nearest_rejected.append(compact(npc, reason=reason))

    counts["eligible"] = len(eligible)
    return {
        "hunter_visible_npcs": counts["visible"],
        "hunter_eligible_npcs": counts["eligible"],
        "hunter_reject_counts": counts,
        "hunter_nearest_visible": nearest_visible,
        "hunter_nearest_rejected": nearest_rejected,
        "hunter_nearest_eligible": [compact(npc) for npc in sorted(eligible, key=lambda npc: combat_distance_to(client, npc))[:limit]],
        "hunter_prefer_tokens": prefer_tokens,
        "hunter_require_tokens": require_tokens,
        "hunter_avoid_tokens": avoid_tokens,
        "hunter_min_level": int(args.min_target_level),
        "hunter_max_level": int(max_level),
        "hunter_max_distance": float(args.max_target_distance),
        "hunter_home_max_distance": float(target_home_max_distance),
        "hunter_include_peace": bool(should_scan_peace_npcs(args)),
    }


def choose_party_assist_target(npcs, leader_target_id: int):
    if leader_target_id <= 0:
        return None

    return next((npc for npc in npcs if npc.object_id == leader_target_id), None)


def choose_current_visible_target(npcs, current_target: int):
    if current_target <= 0:
        return None

    return next((npc for npc in npcs if npc.object_id == current_target), None)


def classify_combat_server_message(text: str) -> set[str]:
    normalized = text.lower()
    categories: set[str] = set()

    if (
        "사거리" in normalized
        or "너무 멀" in normalized
        or "out of range" in normalized
        or "too far" in normalized
    ):
        categories.add("out_of_range")
    if (
        "보이지" in normalized
        or "시야" in normalized
        or "not visible" in normalized
        or "not in view" in normalized
    ):
        categories.add("not_visible")
    if "피해" in normalized or "damage" in normalized or "hit" in normalized:
        categories.add("damage")

    return categories


def is_active_target_combat_contact_message(
    active_combat: dict[str, object] | None,
    text: str,
    chat_type: int,
) -> bool:
    if active_combat is None:
        return False

    active_target_name = normalize_target_name(str(active_combat.get("target_name", "") or ""))
    normalized_message = normalize_target_name(text)
    if not active_target_name or active_target_name not in normalized_message:
        return False

    if int(chat_type or 0) == 30:
        return True

    lower = normalized_message.lower()
    return any(token in lower for token in ("miss", "evade", "parry", "block"))


def server_los_failure_count_distance(args: argparse.Namespace, action_rotation: str) -> float:
    if is_melee_rotation(action_rotation):
        return max(
            120.0,
            float(getattr(args, "minimum_melee_stop_distance", 60.0) or 60.0) + 80.0,
            float(getattr(args, "attack_range", 350.0) or 350.0) * 0.4,
        )

    return max(
        float(getattr(args, "attack_range", 350.0) or 350.0),
        float(getattr(args, "spell_range", 1500.0) or 0.0),
    )


def server_los_retry_stop_distance(args: argparse.Namespace, action_rotation: str) -> float:
    if is_melee_rotation(action_rotation):
        return max(24.0, float(getattr(args, "minimum_melee_stop_distance", 60.0) or 60.0) * 0.5)

    return combat_stop_distance(args, action_rotation)


def should_count_server_los_failure(
    combat_categories: set[str],
    *,
    target_distance: float | None = None,
    close_distance: float | None = None,
) -> bool:
    if "not_visible" not in combat_categories:
        return False

    if target_distance is not None and close_distance is not None and close_distance > 0:
        return target_distance <= close_distance

    return True


def choose_required_visible_target(client, npcs, args: argparse.Namespace):
    if not required_target_home_allows_selection(client, args):
        return None

    targets = [
        npc
        for npc in npcs
        if is_required_target(args, npc)
        and target_within_required_home(args, npc)
        and target_within_selection_distance(client, args, npc)
        and required_target_level_allowed(args, npc)
    ]

    if not targets:
        return None

    return min(targets, key=lambda npc: combat_distance_to(client, npc))


def pre_objective_add_target_allowed(
    args: argparse.Namespace,
    client,
    npc,
    *,
    rejected_targets: dict[int, float] | None = None,
    rejected_target_kinds: dict[tuple[str, int], float] | None = None,
    now: float = 0.0,
) -> bool:
    if npc is None:
        return False

    object_id = int(getattr(npc, "object_id", 0) or 0)
    if object_id <= 0:
        return False

    if rejected_targets is not None and rejected_targets.get(object_id, 0.0) > now:
        return False

    name = str(getattr(npc, "name", "") or "").lower()
    level = int(getattr(npc, "level", 0) or 0)
    if rejected_target_kinds is not None and rejected_target_kinds.get((name, level), 0.0) > now:
        return False

    if is_avoid_target(args, npc):
        return False

    if getattr(args, "party_encounter_mode", "standard") == "standard" and not is_objective_add_target(args, npc):
        return False

    if not should_accept_party_rescue_target(args, npc):
        return False

    return hunter_target_ground_z_aligned(args, client, npc)


def choose_pre_objective_add_target(
    npcs,
    client,
    args: argparse.Namespace,
    objective_npc=None,
    *,
    rejected_targets: dict[int, float] | None = None,
    rejected_target_kinds: dict[tuple[str, int], float] | None = None,
    now: float = 0.0,
):
    if not getattr(args, "party_clear_objective_adds_before_engage", False):
        return None

    if objective_npc is not None:
        objective_id = int(getattr(objective_npc, "object_id", 0) or 0)
        objective_x = int(getattr(objective_npc, "x", 0) or 0)
        objective_y = int(getattr(objective_npc, "y", 0) or 0)
    else:
        objective_id = 0
        if required_target_tokens(args):
            return None
        objective_home = getattr(args, "required_target_home", None)
        if objective_home is None:
            return None
        objective_x = int(getattr(objective_home, "x", 0) or 0)
        objective_y = int(getattr(objective_home, "y", 0) or 0)

    max_distance = float(getattr(args, "party_rescue_objective_max_distance", 0.0) or 0.0)
    candidates = [
        npc
        for npc in npcs
        if int(getattr(npc, "object_id", 0) or 0) > 0
        and int(getattr(npc, "object_id", 0) or 0) != objective_id
        and not is_required_target(args, npc)
        and pre_objective_add_target_allowed(
            args,
            client,
            npc,
            rejected_targets=rejected_targets,
            rejected_target_kinds=rejected_target_kinds,
            now=now,
        )
        and (
            max_distance <= 0.0
            or horizontal_distance_between_points(
                objective_x,
                objective_y,
                int(getattr(npc, "x", 0) or 0),
                int(getattr(npc, "y", 0) or 0),
            )
            <= max_distance
        )
    ]

    if not candidates:
        return None

    return min(candidates, key=lambda npc: (combat_distance_to(client, npc), int(getattr(npc, "object_id", 0) or 0)))


def choose_shared_objective_visible_target(client, npcs, args: argparse.Namespace, shared_target_id: int):
    if not required_target_home_allows_selection(client, args):
        return None

    if shared_target_id > 0:
        target = choose_party_assist_target(npcs, shared_target_id)
        if target is None:
            return None

        if (
            target is not None
            and target_within_required_home(args, target)
            and target_within_selection_distance(client, args, target)
        ):
            return target

    return choose_required_visible_target(client, npcs, args)


def should_reacquire_shared_objective_visible_target(
    args: argparse.Namespace,
    party_snapshot: dict[str, object],
    *,
    is_party_follower: bool,
) -> bool:
    if not should_preserve_party_target_on_loss(args):
        return False

    if (
        is_party_follower
        and getattr(args, "party_require_leader_engaged", False)
        and (
            int(party_snapshot.get("leader_target_id", 0) or 0) <= 0
            or float(party_snapshot.get("leader_target_engaged_at", 0.0) or 0.0) <= 0.0
        )
    ):
        return False

    return True


def required_target_level_allowed(args: argparse.Namespace, npc) -> bool:
    has_explicit_level_window = (
        hasattr(args, "min_target_level")
        or hasattr(args, "max_target_level")
        or hasattr(args, "player_level")
        or hasattr(args, "max_target_level_delta")
    )
    return not has_explicit_level_window or passes_hunter_target_level_filter(args, npc)


def required_target_home_allows_selection(client, args: argparse.Namespace) -> bool:
    if required_target_home_destination(args) is None:
        return True

    return required_target_home_reached(client, args) or required_target_home_hunt_ready(client, args)


def target_within_required_home(args: argparse.Namespace, npc) -> bool:
    target_home = getattr(args, "required_target_home", None)
    target_home_max_distance = float(getattr(args, "target_home_max_distance", 0.0) or 0.0)
    if target_home is None or target_home_max_distance <= 0.0:
        return True

    return (
        horizontal_distance_between_points(
            int(getattr(target_home, "x", 0) or 0),
            int(getattr(target_home, "y", 0) or 0),
            int(getattr(npc, "x", 0) or 0),
            int(getattr(npc, "y", 0) or 0),
        )
        <= target_home_max_distance
    )


def target_within_selection_distance(client, args: argparse.Namespace, npc) -> bool:
    max_distance = float(getattr(args, "max_target_distance", 0.0) or 0.0)
    return max_distance <= 0.0 or combat_distance_to(client, npc) <= max_distance


def hunter_target_ground_z_delta(
    args: argparse.Namespace,
    client,
    npc,
    *,
    region: int | None = None,
) -> float | None:
    max_delta = float(getattr(args, "hunter_target_max_ground_z_delta", 0.0) or 0.0)
    if max_delta <= 0.0:
        return None

    sampler = getattr(client, "ground_z_sampler", None)
    if sampler is None or npc is None:
        return None

    x = int(getattr(npc, "x", 0) or 0)
    y = int(getattr(npc, "y", 0) or 0)
    if x <= 0 or y <= 0:
        return None

    npc_z = int(getattr(npc, "z", 0) or 0)
    sample_region = int(region or getattr(client, "zone_id", 0) or getattr(args, "path_region", 0) or 0)
    try:
        sampled_z = sampler(x, y, sample_region)
    except TypeError:
        try:
            sampled_z = sampler(x, y)
        except Exception:
            return None
    except Exception:
        return None

    if sampled_z is None:
        return None

    return abs(float(sampled_z) - float(npc_z))


def hunter_target_ground_z_aligned(
    args: argparse.Namespace,
    client,
    npc,
    *,
    region: int | None = None,
) -> bool:
    max_delta = float(getattr(args, "hunter_target_max_ground_z_delta", 0.0) or 0.0)
    if max_delta <= 0.0:
        return True

    delta = hunter_target_ground_z_delta(args, client, npc, region=region)
    return delta is None or delta <= max_delta


def required_target_tokens(args: argparse.Namespace) -> list[str]:
    return [token.strip().lower() for token in getattr(args, "require_target_name", "").split(",") if token.strip()]


def preferred_target_tokens(args: argparse.Namespace) -> list[str]:
    return [token.strip().lower() for token in getattr(args, "prefer_target_name", "").split(",") if token.strip()]


def objective_add_target_tokens(args: argparse.Namespace) -> list[str]:
    return [token.strip().lower() for token in getattr(args, "objective_add_target_name", "").split(",") if token.strip()]


def avoid_target_tokens(args: argparse.Namespace) -> list[str]:
    return [token.strip().lower() for token in getattr(args, "avoid_target_name", "").split(",") if token.strip()]


def normalize_target_name(value: str) -> str:
    return " ".join(str(value or "").replace("’", "'").lower().split())


def required_target_name_matches(target_name: str, token: str) -> bool:
    target_name = normalize_target_name(target_name)
    token = normalize_target_name(token)
    if not target_name or not token or token not in target_name:
        return False

    start = target_name.find(token)
    suffix = target_name[start + len(token) :]
    if target_name == token:
        return True

    # Boss summons often inherit the boss name ("X's minion"). Treat those as
    # adds/rescue targets, not as completion objectives.
    if suffix.startswith(("'s", "’s", "s'")):
        return False

    add_suffixes = (
        " add",
        " adds",
        " ally",
        " guardian",
        " helper",
        " messenger",
        " minion",
        " pet",
        " spawn",
    )
    if any(suffix.startswith(add_suffix) for add_suffix in add_suffixes):
        return False

    return True


def name_matches_objective_add_target(args: argparse.Namespace, target_name: str) -> bool:
    normalized_name = normalize_target_name(target_name)
    return bool(
        normalized_name
        and any(required_target_name_matches(normalized_name, token) for token in objective_add_target_tokens(args))
    )


def is_objective_add_target(args: argparse.Namespace, npc) -> bool:
    return bool(npc is not None and name_matches_objective_add_target(args, str(getattr(npc, "name", "") or "")))


def name_matches_avoid_target(args: argparse.Namespace, target_name: str) -> bool:
    normalized_name = normalize_target_name(target_name)
    return bool(normalized_name and any(normalize_target_name(token) in normalized_name for token in avoid_target_tokens(args)))


def is_avoid_target(args: argparse.Namespace, npc) -> bool:
    return bool(npc is not None and name_matches_avoid_target(args, str(getattr(npc, "name", "") or "")))


def party_objective_name_tokens(args: argparse.Namespace, party_snapshot: dict[str, int | float | str] | None) -> list[str]:
    tokens: list[str] = []

    if party_snapshot is not None:
        leader_target_name = normalize_target_name(str(party_snapshot.get("leader_target_name", "") or ""))
        if leader_target_name:
            tokens.append(leader_target_name)

    tokens.extend(normalize_target_name(token) for token in required_target_tokens(args))
    return sorted({token for token in tokens if token}, key=len, reverse=True)


def npc_name_matches_party_objective_add(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str] | None,
    npc,
) -> bool:
    npc_name = normalize_target_name(str(getattr(npc, "name", "") or ""))
    if not npc_name:
        return False

    if name_matches_objective_add_target(args, npc_name):
        return True

    possessive_suffixes = ("'s", "s'")
    add_suffixes = (
        " add",
        " adds",
        " ally",
        " guardian",
        " helper",
        " messenger",
        " minion",
        " pet",
        " spawn",
    )

    for token in party_objective_name_tokens(args, party_snapshot):
        if npc_name == token:
            continue

        token_index = npc_name.find(token)
        if token_index < 0:
            continue

        suffix = npc_name[token_index + len(token) :]
        if suffix.startswith(possessive_suffixes):
            return True

        if any(suffix.startswith(add_suffix) for add_suffix in add_suffixes):
            return True

    return False


def is_required_target(args: argparse.Namespace, npc) -> bool:
    tokens = required_target_tokens(args)
    return bool(tokens and any(required_target_name_matches(npc.name, token) for token in tokens))


def name_matches_preferred_target(args: argparse.Namespace, target_name: str) -> bool:
    normalized_name = normalize_target_name(target_name)
    return bool(
        normalized_name
        and any(required_target_name_matches(normalized_name, token) for token in preferred_target_tokens(args))
    )


def is_preferred_target(args: argparse.Namespace, npc) -> bool:
    return bool(npc is not None and name_matches_preferred_target(args, str(getattr(npc, "name", "") or "")))


def is_route_objective_target(args: argparse.Namespace, npc) -> bool:
    if is_required_target(args, npc):
        return True
    return bool(not required_target_tokens(args) and is_preferred_target(args, npc))


def behavior_state_value(state: DummyBehaviorState | str) -> str:
    return state.value if isinstance(state, DummyBehaviorState) else str(state or "")


def target_intent_value(intent: TargetIntent | str) -> str:
    return intent.value if isinstance(intent, TargetIntent) else str(intent or "")


def target_source_value(source: TargetSource | str) -> str:
    return source.value if isinstance(source, TargetSource) else str(source or "")


def should_use_engagement_gate_for_target_source(source: TargetSource | str) -> bool:
    return target_source_value(source) in {item.value for item in TargetSource}


def _target_gate_actor(candidate: EngagementCandidate):
    if candidate.npc is not None:
        return candidate.npc
    return SimpleNamespace(
        object_id=candidate.object_id,
        name=candidate.name,
        level=candidate.level,
        x=candidate.x,
        y=candidate.y,
        z=candidate.z,
        flags=0,
    )


def engagement_candidate_from_actor(
    npc,
    *,
    source: TargetSource | str,
    intent: TargetIntent | str,
) -> EngagementCandidate:
    return EngagementCandidate(
        object_id=int(getattr(npc, "object_id", 0) or 0),
        name=str(getattr(npc, "name", "") or ""),
        level=int(getattr(npc, "level", 0) or 0),
        x=int(getattr(npc, "x", 0) or 0),
        y=int(getattr(npc, "y", 0) or 0),
        z=int(getattr(npc, "z", 0) or 0),
        source=source,
        intent=intent,
        npc=npc,
    )


def _target_decision(
    *,
    allowed: bool,
    candidate: EngagementCandidate,
    intent: TargetIntent | str,
    source: TargetSource | str,
    priority: int = 0,
    reject_reason: str = "",
    should_target_object: bool = False,
    should_update_current_target: bool = False,
    should_publish_party_leader_target: bool = False,
    should_mark_leader_engaged: bool = False,
) -> TargetDecision:
    return TargetDecision(
        allowed=allowed,
        candidate=candidate,
        intent=intent,
        source=source,
        priority=priority,
        reject_reason=reject_reason,
        should_target_object=should_target_object,
        should_update_current_target=should_update_current_target,
        should_publish_party_leader_target=should_publish_party_leader_target,
        should_mark_leader_engaged=should_mark_leader_engaged,
    )


def _reject_engagement_candidate(
    candidate: EngagementCandidate,
    *,
    intent: TargetIntent | str,
    source: TargetSource | str,
    reason: str,
) -> TargetDecision:
    return _target_decision(
        allowed=False,
        candidate=candidate,
        intent=intent,
        source=source,
        reject_reason=reason,
    )


def evaluate_engagement_candidate(
    candidate: EngagementCandidate,
    context: EngagementContext,
    client,
    args: argparse.Namespace,
    party_snapshot,
) -> TargetDecision:
    source = candidate.source
    intent = candidate.intent
    intent_name = target_intent_value(intent)
    source_name = target_source_value(source)
    actor = _target_gate_actor(candidate)

    if int(candidate.object_id or 0) <= 0:
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="invalid_target")

    if not should_use_engagement_gate_for_target_source(source):
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="non_hostile_target_source")

    if context.flee_active:
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="flee_active")

    if context.rest_active or behavior_state_value(context.behavior_state) == DummyBehaviorState.RestRecover.value:
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="rest_active")

    if context.drop_aggro_active or behavior_state_value(context.behavior_state) == DummyBehaviorState.DropAggroAndRecover.value:
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="drop_aggro_active")

    if is_objective_travel_state(context.behavior_state) and intent_name not in {
        TargetIntent.objective.value,
        TargetIntent.required_retaliation.value,
        TargetIntent.current_target_confirm.value,
    }:
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="travel_non_objective")

    if not required_target_level_allowed(args, actor):
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="level_filter")

    if not target_within_required_home(args, actor):
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="target_home_max_distance")

    if not target_within_selection_distance(client, args, actor):
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="max_target_distance")

    leash_violated, _leash_kind, _leash_distance = target_home_leash_violation(client, args, actor)
    if leash_violated:
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="combat_home_leash")

    if (
        required_target_home_destination(args) is not None
        and intent_name in {TargetIntent.objective.value, TargetIntent.required_retaliation.value}
        and not (context.objective_home_reached or context.objective_hunt_ready)
    ):
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="objective_home_not_ready")

    if (
        source_name in {TargetSource.party_assist.value, TargetSource.leader_target_reacquire.value}
        and not context.party_ready
    ):
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="party_not_ready")

    if (
        source_name in {TargetSource.party_assist.value, TargetSource.leader_target_reacquire.value}
        and bool(getattr(args, "party_require_leader_engaged", False))
        and not context.leader_engaged
    ):
        return _reject_engagement_candidate(candidate, intent=intent, source=source, reason="leader_not_engaged")

    should_publish_leader_target = bool(
        context.is_party_leader
        and intent_name
        in {
            TargetIntent.objective.value,
            TargetIntent.required_retaliation.value,
            TargetIntent.party_assist.value,
            TargetIntent.current_target_confirm.value,
        }
    )
    priority = 100
    if intent_name == TargetIntent.required_retaliation.value:
        priority = 120
    elif intent_name == TargetIntent.party_rescue.value:
        priority = 90
    elif intent_name in {TargetIntent.travel_aggro.value, TargetIntent.avoided_add.value}:
        priority = 10

    return _target_decision(
        allowed=True,
        candidate=candidate,
        intent=intent,
        source=source,
        priority=priority,
        should_target_object=True,
        should_update_current_target=True,
        should_publish_party_leader_target=should_publish_leader_target,
        should_mark_leader_engaged=False,
    )


def _target_gate_reject_action_name(reason: str) -> str:
    suffix = re.sub(r"[^a-z0-9_]+", "_", str(reason or "unknown").strip().lower()).strip("_")
    return f"target_gate_rejected_{suffix or 'unknown'}"


def commit_target(
    decision: TargetDecision,
    client,
    party_state,
    *,
    now: float,
    current_target: int,
    current_target_since: float,
    current_target_last_visible_at: float,
    current_target_intent: TargetIntent | str,
    action_counts: dict[str, int] | None = None,
    log_event=None,
    examine: bool | None = None,
) -> TargetCommitResult:
    candidate = decision.candidate

    if not decision.allowed:
        if action_counts is not None:
            add_action(action_counts, "target_gate_rejected")
            add_action(action_counts, _target_gate_reject_action_name(decision.reject_reason))
        if log_event is not None:
            log_event(
                "target_gate_rejected",
                now,
                target_id=int(candidate.object_id or 0),
                target_name=str(candidate.name or ""),
                target_level=int(candidate.level or 0),
                target_source=target_source_value(decision.source),
                target_intent=target_intent_value(decision.intent),
                reject_reason=str(decision.reject_reason or ""),
            )
        return TargetCommitResult(
            current_target=current_target,
            current_target_since=current_target_since,
            current_target_last_visible_at=current_target_last_visible_at,
            current_target_intent=current_target_intent,
            target_object_called=False,
            current_target_updated=False,
            party_leader_target_published=False,
        )

    target_object_called = False
    if decision.should_target_object:
        if examine is None:
            client.target_object(candidate.object_id)
        else:
            client.target_object(candidate.object_id, examine=examine)
        target_object_called = True

    updated_current_target = current_target
    updated_current_target_since = current_target_since
    updated_current_target_last_visible_at = current_target_last_visible_at
    updated_current_target_intent = current_target_intent
    current_target_updated = False
    if decision.should_update_current_target:
        updated_current_target = int(candidate.object_id or 0)
        updated_current_target_since = now
        updated_current_target_last_visible_at = now
        updated_current_target_intent = decision.intent
        current_target_updated = True

    party_leader_target_published = False
    if decision.should_publish_party_leader_target and party_state is not None:
        target_actor = candidate.npc if candidate.npc is not None else _target_gate_actor(candidate)
        party_state.update_leader(client, target_actor)
        party_leader_target_published = True

    if (
        decision.should_mark_leader_engaged
        and party_state is not None
        and hasattr(party_state, "mark_leader_target_engaged")
    ):
        party_state.mark_leader_target_engaged(candidate.object_id)

    return TargetCommitResult(
        current_target=updated_current_target,
        current_target_since=updated_current_target_since,
        current_target_last_visible_at=updated_current_target_last_visible_at,
        current_target_intent=updated_current_target_intent,
        target_object_called=target_object_called,
        current_target_updated=current_target_updated,
        party_leader_target_published=party_leader_target_published,
    )


def is_objective_travel_state(state: DummyBehaviorState | str) -> bool:
    return behavior_state_value(state) in {
        DummyBehaviorState.TravelToObjective.value,
        DummyBehaviorState.ReturnToObjective.value,
    }


def should_allow_scheduled_rest(behavior_state: DummyBehaviorState | str, current_target: int) -> bool:
    if current_target:
        return False
    return behavior_state_value(behavior_state) not in {
        DummyBehaviorState.Startup.value,
        DummyBehaviorState.TravelToObjective.value,
        DummyBehaviorState.HandleTravelAggro.value,
        DummyBehaviorState.DropAggroAndRecover.value,
        DummyBehaviorState.ReturnToObjective.value,
        DummyBehaviorState.DeadReleaseRecover.value,
    }


def should_complete_timed_rest_recovery(
    behavior_state: DummyBehaviorState | str,
    *,
    rest_until: float,
    stand_after_rest: bool,
    now: float,
) -> bool:
    return bool(
        behavior_state_value(behavior_state) == DummyBehaviorState.RestRecover.value
        and rest_until > 0.0
        and now >= rest_until
        and not stand_after_rest
    )


def next_state_after_rest_recovery_completion(
    args: argparse.Namespace,
    client,
    *,
    is_party_leader: bool,
    current_target: int,
) -> DummyBehaviorState:
    if (
        should_approach_required_target_home(args, is_party_leader=is_party_leader, current_target=current_target)
        and not required_target_home_hunt_ready(client, args)
    ):
        return DummyBehaviorState.ReturnToObjective

    return DummyBehaviorState.HuntObjective


def target_intent_for_selected_npc(
    args: argparse.Namespace,
    npc,
    *,
    selected_npc_is_rescue: bool,
    behavior_state: DummyBehaviorState | str = DummyBehaviorState.HuntObjective,
    recent_incoming_attacker_name: str = "",
) -> TargetIntent:
    if npc is None:
        return TargetIntent.none

    if is_required_target(args, npc):
        if (
            behavior_state_value(behavior_state) == DummyBehaviorState.HandleTravelAggro.value
            or name_matches_required_target(args, recent_incoming_attacker_name)
        ):
            return TargetIntent.required_retaliation
        return TargetIntent.objective

    if not required_target_tokens(args) and is_preferred_target(args, npc):
        return TargetIntent.objective

    if is_objective_add_target(args, npc):
        if (
            behavior_state_value(behavior_state) == DummyBehaviorState.HandleTravelAggro.value
            or name_matches_objective_add_target(args, recent_incoming_attacker_name)
        ):
            return TargetIntent.required_retaliation
        return TargetIntent.party_rescue

    if is_objective_travel_state(behavior_state) and is_avoid_target(args, npc):
        return TargetIntent.avoided_add

    if is_objective_travel_state(behavior_state):
        return TargetIntent.travel_aggro

    if selected_npc_is_rescue:
        return TargetIntent.party_rescue

    return TargetIntent.objective


def should_handle_travel_aggro_target(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    npc,
    current_target_intent: TargetIntent | str = TargetIntent.none,
) -> bool:
    if not is_objective_travel_state(behavior_state):
        return False

    intent = target_intent_value(current_target_intent)
    if intent in {TargetIntent.objective.value, TargetIntent.required_retaliation.value}:
        return False

    if npc is not None and is_route_objective_target(args, npc):
        return False

    if npc is not None and is_objective_add_target(args, npc):
        return False

    return npc is not None or intent == TargetIntent.travel_aggro.value


def should_handle_travel_aggro_damage(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    attacker_name: str,
    *,
    attacker_level: int = 0,
    player_level: int = 0,
    health_percent: int = 100,
    previous_health_percent: int = 100,
) -> bool:
    if not (
        is_objective_travel_state(behavior_state)
        and attacker_name
        and not name_matches_required_target(args, attacker_name)
        and (required_target_tokens(args) or not name_matches_preferred_target(args, attacker_name))
        and not name_matches_objective_add_target(args, attacker_name)
    ):
        return False

    low_level_delta = int(getattr(args, "travel_aggro_ignore_low_level_delta", 8) or 0)
    minor_drop_percent = int(getattr(args, "travel_aggro_minor_health_drop_percent", 5) or 0)
    pressure_health_percent = int(getattr(args, "flee_pressure_health_percent", 0) or 0)
    health_drop = max(0, int(previous_health_percent or 0) - int(health_percent or 0))
    if (
        low_level_delta > 0
        and minor_drop_percent > 0
        and int(attacker_level or 0) > 0
        and int(player_level or 0) > 0
        and int(player_level) - int(attacker_level) >= low_level_delta
        and health_drop <= minor_drop_percent
        and (pressure_health_percent <= 0 or int(health_percent or 0) > pressure_health_percent)
    ):
        return False

    return True


def visible_npc_level_by_name(npcs, target_name: str) -> int:
    target_key = normalize_target_name(target_name)
    if not target_key:
        return 0

    levels = [
        int(getattr(npc, "level", 0) or 0)
        for npc in npcs
        if normalize_target_name(str(getattr(npc, "name", "") or "")) == target_key
    ]
    return max(levels, default=0)


def should_suppress_passive_travel_target(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    npc,
    current_target_intent: TargetIntent | str = TargetIntent.none,
    *,
    current_target: int = 0,
    now: float = 0.0,
    last_damage_taken_at: float = 0.0,
) -> bool:
    if not is_objective_travel_state(behavior_state):
        return False
    if target_intent_value(current_target_intent) not in {
        TargetIntent.avoided_add.value,
        TargetIntent.travel_aggro.value,
    }:
        return False
    if npc is None or is_route_objective_target(args, npc) or is_objective_add_target(args, npc):
        return False
    if current_target:
        return False

    damage_grace = max(0.0, float(getattr(args, "incoming_damage_melee_grace", 4.0) or 0.0))
    if last_damage_taken_at > 0.0 and now - last_damage_taken_at <= damage_grace:
        return False

    return True


def should_suppress_passive_avoided_travel_target(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    npc,
    current_target_intent: TargetIntent | str = TargetIntent.none,
    *,
    current_target: int = 0,
    now: float = 0.0,
    last_damage_taken_at: float = 0.0,
) -> bool:
    return should_suppress_passive_travel_target(
        args,
        behavior_state,
        npc,
        current_target_intent,
        current_target=current_target,
        now=now,
        last_damage_taken_at=last_damage_taken_at,
    )


def should_allow_target_selection_for_behavior_state(
    behavior_state: DummyBehaviorState | str,
    args: argparse.Namespace,
    npc,
    current_target_intent: TargetIntent | str = TargetIntent.none,
) -> bool:
    state = behavior_state_value(behavior_state)
    if state in {
        DummyBehaviorState.DropAggroAndRecover.value,
        DummyBehaviorState.RestRecover.value,
    }:
        return False

    if should_handle_travel_aggro_target(args, behavior_state, npc, current_target_intent):
        return False

    return True


def should_allow_counterattack_for_behavior_state(
    behavior_state: DummyBehaviorState | str,
    args: argparse.Namespace,
    npc,
    current_target_intent: TargetIntent | str = TargetIntent.none,
) -> bool:
    return should_allow_target_selection_for_behavior_state(behavior_state, args, npc, current_target_intent)


def should_allow_party_assist_for_behavior_state(behavior_state: DummyBehaviorState | str) -> bool:
    return behavior_state_value(behavior_state) != DummyBehaviorState.DropAggroAndRecover.value


def should_clear_party_ready_for_behavior_state(behavior_state: DummyBehaviorState | str) -> bool:
    return behavior_state_value(behavior_state) in {
        DummyBehaviorState.HandleTravelAggro.value,
        DummyBehaviorState.DropAggroAndRecover.value,
        DummyBehaviorState.RestRecover.value,
        DummyBehaviorState.DeadReleaseRecover.value,
    }


def should_send_party_assist_command(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    *,
    leader_target_id: int,
    leader_engaged: bool,
) -> bool:
    if not getattr(args, "party_use_assist_command", False):
        return False

    if not should_allow_party_assist_for_behavior_state(behavior_state):
        return False

    if int(leader_target_id or 0) <= 0:
        return False

    if getattr(args, "party_require_leader_engaged", False) and not leader_engaged:
        return False

    return True


def clear_party_leader_target_on_abandon(
    party_state: PartyState | None,
    *,
    is_party_leader: bool,
    target_id: int = 0,
) -> bool:
    if party_state is None or not is_party_leader:
        return False

    if target_id:
        snapshot = party_state.snapshot()
        if int(snapshot.get("leader_target_id", 0) or 0) != int(target_id):
            return False

    party_state.clear_leader_target()
    return True


def should_commit_required_retaliation_for_objective(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    *,
    required_home_hunt_ready: bool,
    party_ready_for_objective: bool,
    direct_required_damage_to_active_tank: bool = False,
) -> bool:
    state = behavior_state_value(behavior_state)
    if state == DummyBehaviorState.DropAggroAndRecover.value:
        return False

    block_direct_tank_retaliation = (
        bool(getattr(args, "party_block_solo_required_retaliation", False))
        and is_objective_travel_state(state)
    )
    allow_direct_tank_retaliation = (
        direct_required_damage_to_active_tank
        and required_home_hunt_ready
        and not block_direct_tank_retaliation
    )
    if not party_ready_for_objective and not allow_direct_tank_retaliation:
        return False

    if state in {
        DummyBehaviorState.Startup.value,
        DummyBehaviorState.TravelToObjective.value,
        DummyBehaviorState.ReturnToObjective.value,
        DummyBehaviorState.HandleTravelAggro.value,
        DummyBehaviorState.RestRecover.value,
    }:
        return bool(required_home_hunt_ready)

    return True


def should_publish_damage_counterattack_as_leader_target(
    *,
    is_party_leader: bool,
    party_state: PartyState | None,
    current_target_intent: TargetIntent | str,
) -> bool:
    return bool(
        is_party_leader
        and party_state is not None
        and target_intent_value(current_target_intent)
        in {TargetIntent.objective.value, TargetIntent.required_retaliation.value}
    )


def should_publish_combat_start_as_leader_target(
    *,
    is_party_leader: bool,
    party_state: PartyState | None,
    current_target_intent: TargetIntent | str,
) -> bool:
    return bool(
        is_party_leader
        and party_state is not None
        and target_intent_value(current_target_intent)
        in {
            TargetIntent.objective.value,
            TargetIntent.required_retaliation.value,
            TargetIntent.party_rescue.value,
        }
    )


def publish_combat_start_as_leader_target(
    party_state: PartyState | None,
    client,
    target,
    *,
    is_party_leader: bool,
    current_target_intent: TargetIntent | str,
) -> bool:
    if not should_publish_combat_start_as_leader_target(
        is_party_leader=is_party_leader,
        party_state=party_state,
        current_target_intent=current_target_intent,
    ):
        return False

    party_state.update_leader(client, target, engaged=False)
    return True


def should_hold_initial_required_retaliation_multi_aggro(
    args: argparse.Namespace,
    active_combat,
    *,
    current_target_intent: TargetIntent | str,
    is_active_tank: bool,
    health_percent: int,
    now: float,
) -> bool:
    if active_combat is None or not is_active_tank:
        return False

    if target_intent_value(current_target_intent) != TargetIntent.required_retaliation.value:
        return False

    flee_health_percent = int(getattr(args, "flee_health_percent", 0) or 0)
    if flee_health_percent > 0 and health_percent <= flee_health_percent:
        return False

    started = float(active_combat.get("started", 0.0) or 0.0)
    if started <= 0.0:
        return False

    assist_after = float(getattr(args, "party_rescue_assist_after", 0.0) or 0.0)
    hold_grace = max(3.0, assist_after + 2.0)
    return now - started <= hold_grace


def should_delay_target_selection_until_objective_ready(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    selected_target_intent: TargetIntent | str,
    *,
    current_target: int,
    required_home_hunt_ready: bool,
    party_ready_for_objective: bool,
    is_party_follower: bool = False,
    leader_engaged: bool = True,
) -> bool:
    if getattr(args, "required_target_home", None) is None:
        return False

    if not is_objective_travel_state(behavior_state):
        return False

    target_intent = target_intent_value(selected_target_intent)
    if target_intent not in {
        TargetIntent.objective.value,
        TargetIntent.required_retaliation.value,
        TargetIntent.party_rescue.value,
    }:
        return False

    if current_target > 0 and target_intent == TargetIntent.party_rescue.value:
        return False

    if (
        is_party_follower
        and getattr(args, "party_require_leader_engaged", False)
        and target_intent == TargetIntent.objective.value
        and not leader_engaged
    ):
        return True

    return not (required_home_hunt_ready and party_ready_for_objective)


def should_enter_hunt_for_objective_area_rescue(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    *,
    selected_npc_is_rescue: bool,
    required_home_hunt_ready: bool,
    party_ready_for_objective: bool,
) -> bool:
    return bool(
        selected_npc_is_rescue
        and getattr(args, "required_target_home", None) is not None
        and is_objective_travel_state(behavior_state)
        and required_home_hunt_ready
        and party_ready_for_objective
    )


def should_drop_objective_wait_for_recent_damage(
    behavior_state: DummyBehaviorState | str,
    selected_target_intent: TargetIntent | str,
    *,
    last_damage_taken_at: float,
    now: float,
    damage_grace_seconds: float = 3.0,
) -> bool:
    if not is_objective_travel_state(behavior_state):
        return False

    if last_damage_taken_at <= 0.0 or now - last_damage_taken_at > max(0.0, damage_grace_seconds):
        return False

    return target_intent_value(selected_target_intent) in {
        TargetIntent.objective.value,
        TargetIntent.required_retaliation.value,
        TargetIntent.party_rescue.value,
    }


def should_drop_required_retaliation_before_objective_ready(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    *,
    required_home_hunt_ready: bool,
    party_ready_for_objective: bool,
) -> bool:
    return bool(
        is_objective_travel_state(behavior_state)
        and not should_commit_required_retaliation_for_objective(
            args,
            behavior_state,
            required_home_hunt_ready=required_home_hunt_ready,
            party_ready_for_objective=party_ready_for_objective,
        )
    )


def should_mark_leader_target_engaged(
    args: argparse.Namespace,
    action_rotation: str,
    *,
    attack_enabled: bool,
    action_distance: float,
) -> bool:
    if not attack_enabled:
        return False

    if is_melee_rotation(action_rotation):
        attack_range = float(getattr(args, "attack_range", 0.0) or 0.0)
        if action_distance <= attack_range:
            return True
        if not getattr(args, "party_mark_pull_engaged", False):
            return False
        pull_distance = float(getattr(args, "party_pull_engage_distance", 0.0) or 0.0)
        if pull_distance <= 0.0:
            pull_distance = float(getattr(args, "melee_stick_attack_distance", 0.0) or 0.0)
        return pull_distance > 0.0 and action_distance <= pull_distance

    return True


def state_after_flee_start(behavior_state: DummyBehaviorState | str) -> DummyBehaviorState:
    if behavior_state_value(behavior_state) == DummyBehaviorState.DeadReleaseRecover.value:
        return DummyBehaviorState.DeadReleaseRecover
    return DummyBehaviorState.DropAggroAndRecover


def should_escape_after_death_recovery(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "flee_dynamic_safe_point", False) or getattr(args, "flee_home", None) is not None)


def should_allow_untracked_damage_counterattack(
    behavior_state: DummyBehaviorState | str,
    *,
    flee_until: float,
    now: float,
) -> bool:
    if now < flee_until:
        return False
    return behavior_state_value(behavior_state) not in {
        DummyBehaviorState.DropAggroAndRecover.value,
        DummyBehaviorState.RestRecover.value,
    }


def should_force_drop_aggro_for_critical_health(
    args: argparse.Namespace,
    behavior_state: DummyBehaviorState | str,
    *,
    health_percent: int,
) -> bool:
    critical_health = int(getattr(args, "flee_critical_health_percent", 0) or 0)
    return bool(
        critical_health > 0
        and 0 < health_percent <= critical_health
        and behavior_state_value(behavior_state) == DummyBehaviorState.HuntObjective.value
    )


def next_state_after_drop_aggro_recovery(
    args: argparse.Namespace,
    *,
    health_percent: int,
    now: float,
    last_damage_taken_at: float,
    active_threat: bool,
) -> DummyBehaviorState:
    if active_threat:
        return DummyBehaviorState.DropAggroAndRecover

    clear_grace = float(getattr(args, "travel_aggro_clear_grace", 3.0) or 0.0)
    if last_damage_taken_at > 0.0 and now - last_damage_taken_at < clear_grace:
        return DummyBehaviorState.DropAggroAndRecover

    if should_rest_after_flee_recovery(args, health_percent=health_percent):
        return DummyBehaviorState.RestRecover

    return DummyBehaviorState.ReturnToObjective


def drop_aggro_clear_grace_remaining(
    args: argparse.Namespace,
    *,
    now: float,
    last_damage_taken_at: float,
) -> float:
    clear_grace = float(getattr(args, "travel_aggro_clear_grace", 3.0) or 0.0)
    if clear_grace <= 0.0 or last_damage_taken_at <= 0.0:
        return 0.0

    return max(0.0, clear_grace - (now - last_damage_taken_at))


def drop_aggro_recovery_duration(args: argparse.Namespace, *, health_percent: int | None = None) -> float:
    durations = [
        1.0,
        float(getattr(args, "flee_duration", 0.0) or 0.0),
        float(getattr(args, "travel_aggro_clear_grace", 0.0) or 0.0),
    ]
    if health_percent is None or should_rest_after_flee_recovery(args, health_percent=health_percent):
        durations.append(float(getattr(args, "low_health_rest_min", 0.0) or 0.0))

    return max(durations)


def drop_aggro_clear_hold_duration(
    args: argparse.Namespace,
    *,
    clear_remaining: float,
    health_percent: int,
) -> float:
    if should_rest_after_flee_recovery(args, health_percent=health_percent):
        return max(float(clear_remaining or 0.0), float(getattr(args, "low_health_rest_min", 0.0) or 0.0), 1.0)

    return max(float(clear_remaining or 0.0), 0.5)


def point_to_segment_distance(
    px: int | float,
    py: int | float,
    ax: int | float,
    ay: int | float,
    bx: int | float,
    by: int | float,
) -> float:
    abx = float(bx) - float(ax)
    aby = float(by) - float(ay)
    apx = float(px) - float(ax)
    apy = float(py) - float(ay)
    length_sq = abx * abx + aby * aby
    if length_sq <= 0.0:
        return math.hypot(apx, apy)

    t = max(0.0, min(1.0, (apx * abx + apy * aby) / length_sq))
    closest_x = float(ax) + abx * t
    closest_y = float(ay) + aby * t
    return math.hypot(float(px) - closest_x, float(py) - closest_y)


def travel_aggro_detour_destination(
    args: argparse.Namespace,
    client,
    objective: MovementDestination | None,
    *,
    danger_x: int,
    danger_y: int,
    danger_z: int,
    attempt_count: int = 1,
) -> MovementDestination | None:
    if client is None or objective is None or danger_x <= 0 or danger_y <= 0:
        return None

    origin_x = int(getattr(client, "x", 0) or 0)
    origin_y = int(getattr(client, "y", 0) or 0)
    origin_z = int(getattr(client, "z", 0) or danger_z or 0)
    if origin_x <= 0 or origin_y <= 0:
        return None

    avoid_radius = float(getattr(args, "travel_aggro_avoid_radius", 0.0) or 0.0)
    if avoid_radius <= 0.0:
        avoid_radius = max(2600.0, float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0) * 0.65)

    path_distance = point_to_segment_distance(
        danger_x,
        danger_y,
        origin_x,
        origin_y,
        objective.x,
        objective.y,
    )
    if path_distance > avoid_radius:
        return None

    route_x = float(objective.x - danger_x)
    route_y = float(objective.y - danger_y)
    route_len = math.hypot(route_x, route_y)
    if route_len <= 0.0:
        return None

    detour_distance = float(getattr(args, "travel_aggro_detour_distance", 0.0) or 0.0)
    if detour_distance <= 0.0:
        detour_distance = max(
            avoid_radius * 1.35,
            float(getattr(args, "flee_safe_point_distance", 0.0) or 0.0) * 0.75,
        )
    detour_distance *= 1.0 + max(0, int(attempt_count) - 1) * 0.25

    perp_x = -route_y / route_len
    perp_y = route_x / route_len
    sign = 1.0 if (
        (int(danger_x) // 100 + int(danger_y) // 100 + int(objective.x) // 100 + int(objective.y) // 100) % 2 == 0
    ) else -1.0
    best_x, best_y = (
        int(danger_x + perp_x * detour_distance * sign),
        int(danger_y + perp_y * detour_distance * sign),
    )
    return destination_from_point("travel-aggro-detour", best_x, best_y, origin_z, bucket=100)


def should_clear_travel_aggro_avoid_memory(
    args: argparse.Namespace,
    client,
    *,
    now: float,
    danger_until: float,
    danger_x: int,
    danger_y: int,
    last_damage_taken_at: float,
) -> bool:
    if client is None or danger_until <= 0.0 or now >= danger_until:
        return False

    if danger_x <= 0 or danger_y <= 0:
        return False

    clear_grace = float(getattr(args, "travel_aggro_clear_grace", 3.0) or 0.0)
    if last_damage_taken_at > 0.0 and now - last_damage_taken_at <= max(0.0, clear_grace):
        return False

    current_x = int(getattr(client, "x", 0) or 0)
    current_y = int(getattr(client, "y", 0) or 0)
    if current_x <= 0 or current_y <= 0:
        return False

    avoid_radius = float(getattr(args, "travel_aggro_avoid_radius", 0.0) or 0.0)
    if avoid_radius <= 0.0:
        avoid_radius = max(2600.0, float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0) * 0.65)

    detour_distance = float(getattr(args, "travel_aggro_detour_distance", 0.0) or 0.0)
    threat_radius = float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0)
    clear_distance = max(avoid_radius * 1.1, 3200.0)
    if detour_distance > 0.0:
        clear_distance = max(clear_distance, min(detour_distance, avoid_radius * 1.35))
    if threat_radius > 0.0:
        clear_distance = max(clear_distance, threat_radius * 0.75)

    return horizontal_distance_between_points(current_x, current_y, danger_x, danger_y) >= clear_distance


WATCHER_TRAVEL_AGGRO_FEEDBACK = {
    "bad_target_choice",
    "target_stuck",
    "wrong_target",
    "wrong-target",
}


def state_after_watcher_feedback(
    behavior_state: DummyBehaviorState | str,
    feedback_reason: str,
) -> DummyBehaviorState | str:
    if is_objective_travel_state(behavior_state) and str(feedback_reason or "").strip().lower() in WATCHER_TRAVEL_AGGRO_FEEDBACK:
        return DummyBehaviorState.HandleTravelAggro

    return behavior_state


def first_configured_target_name(*values: str) -> str:
    for value in values:
        for part in str(value or "").split(","):
            token = part.strip()
            if token:
                return token
    return ""


def passes_required_target_filter(args: argparse.Namespace, npc) -> bool:
    tokens = required_target_tokens(args)
    return not tokens or any(required_target_name_matches(npc.name, token) for token in tokens)


def passes_hunter_target_level_filter(args: argparse.Namespace, npc) -> bool:
    if npc is None:
        return False
    min_level = int(getattr(args, "min_target_level", 0) or 0)
    max_level = int(getattr(args, "max_target_level", -1) or -1)
    if max_level < 0:
        max_level = int(getattr(args, "player_level", 0) or 0) + int(getattr(args, "max_target_level_delta", 0) or 0)
    npc_level = int(getattr(npc, "level", 0) or 0)
    return npc_level >= min_level and (max_level < 0 or npc_level <= max_level)


def preferred_low_con_fallback_allowed(args: argparse.Namespace, client, npc) -> bool:
    if npc is None or not getattr(args, "allow_preferred_low_con_fallback", False):
        return False
    prefer_tokens = preferred_target_tokens(args)
    if not prefer_tokens or not any(token in str(getattr(npc, "name", "") or "").lower() for token in prefer_tokens):
        return False
    min_level = int(getattr(args, "preferred_low_con_min_level", 0) or 0)
    npc_level = int(getattr(npc, "level", 0) or 0)
    if npc_level < min_level:
        return False
    if getattr(args, "max_target_distance", 0.0) > 0 and combat_distance_to(client, npc) > float(args.max_target_distance):
        return False
    target_home = getattr(args, "required_target_home", None)
    target_home_max_distance = float(getattr(args, "target_home_max_distance", 0.0) or 0.0)
    if target_home is not None and target_home_max_distance > 0.0:
        home_distance = horizontal_distance_between_points(
            int(getattr(target_home, "x", 0) or 0),
            int(getattr(target_home, "y", 0) or 0),
            int(getattr(npc, "x", 0) or 0),
            int(getattr(npc, "y", 0) or 0),
        )
        if home_distance > target_home_max_distance:
            return False
    if not hunter_target_ground_z_aligned(args, client, npc):
        return False
    max_level = int(getattr(args, "max_target_level", -1) or -1)
    if max_level < 0:
        max_level = int(getattr(args, "player_level", 0) or 0) + int(getattr(args, "max_target_level_delta", 0) or 0)
    return max_level < 0 or npc_level <= max_level


def should_accept_party_rescue_target(args: argparse.Namespace, npc) -> bool:
    if npc is None or is_foreign_required_test_clone(args, npc):
        return False

    player_level = int(getattr(args, "player_level", 0) or 0)
    npc_level = int(getattr(npc, "level", 0) or 0)
    low_level_delta = int(getattr(args, "party_rescue_ignore_low_level_delta", 8) or 0)
    if (
        low_level_delta > 0
        and player_level > 0
        and npc_level > 0
        and player_level - npc_level >= low_level_delta
        and not is_required_target(args, npc)
        and not is_objective_add_target(args, npc)
    ):
        return False

    if getattr(args, "party_encounter_mode", "standard") == "standard":
        if player_level > 0:
            max_level = int(getattr(args, "max_target_level", -1) or -1)
            if max_level < 0:
                max_level = player_level + int(getattr(args, "max_target_level_delta", 0) or 0)
            if max_level >= 0 and int(getattr(npc, "level", 0) or 0) > max_level:
                return False

    return True


def is_foreign_required_test_clone(args: argparse.Namespace, npc) -> bool:
    name = str(getattr(npc, "name", "") or "")
    return bool(name.startswith("KDAOC_TEST_") and not is_required_target(args, npc))


def horizontal_distance_between_points(ax: int | float, ay: int | float, bx: int | float, by: int | float) -> float:
    return math.hypot(float(ax) - float(bx), float(ay) - float(by))


def party_objective_distance_to_npc(party_snapshot: dict[str, int | float | str], npc) -> float:
    return horizontal_distance_between_points(
        int(party_snapshot.get("leader_target_x", 0) or 0),
        int(party_snapshot.get("leader_target_y", 0) or 0),
        int(getattr(npc, "x", 0) or 0),
        int(getattr(npc, "y", 0) or 0),
    )


def is_rescue_threat_near_party_objective(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str] | None,
    npc,
) -> bool:
    max_distance = float(getattr(args, "party_rescue_objective_max_distance", 0.0) or 0.0)
    if max_distance <= 0 or party_snapshot is None:
        return False

    if int(party_snapshot.get("leader_target_id", 0) or 0) <= 0:
        return False

    if int(party_snapshot.get("leader_target_x", 0) or 0) == 0 and int(party_snapshot.get("leader_target_y", 0) or 0) == 0:
        return False

    return party_objective_distance_to_npc(party_snapshot, npc) <= max_distance


def is_party_objective_add_rescue_threat(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str] | None,
    npc,
) -> bool:
    if is_foreign_required_test_clone(args, npc):
        return False

    if is_objective_add_target(args, npc):
        return True

    return bool(
        is_rescue_threat_near_party_objective(args, party_snapshot, npc)
        and npc_name_matches_party_objective_add(args, party_snapshot, npc)
    )


def is_party_combat_proven_encounter_add(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str] | None,
    npc,
) -> bool:
    if party_snapshot is None or npc is None:
        return False

    if int(party_snapshot.get("leader_target_id", 0) or 0) <= 0:
        return False

    if float(party_snapshot.get("leader_target_engaged_at", 0.0) or 0.0) <= 0.0:
        return False

    return bool(
        not is_required_target(args, npc)
        and not is_foreign_required_test_clone(args, npc)
        and should_accept_party_rescue_target(args, npc)
    )


def is_combat_proven_party_objective_add(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str] | None,
    npc,
) -> bool:
    return bool(
        is_party_objective_add_rescue_threat(args, party_snapshot, npc)
        or is_party_combat_proven_encounter_add(args, party_snapshot, npc)
    )


def choose_party_rescue_attacker(
    client,
    args: argparse.Namespace,
    leader_target_id: int,
    party_snapshot: dict[str, int | float | str] | None = None,
    objective_scan_only: bool = False,
):
    rescue_candidates = [
        npc
        for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
        if npc.object_id != leader_target_id
        and not is_required_target(args, npc)
        and should_accept_party_rescue_target(args, npc)
        and (
            is_party_objective_add_rescue_threat(args, party_snapshot, npc)
            if objective_scan_only
            else is_rescue_threat_in_range(
                client,
                npc,
                args,
                args.party_rescue_max_distance,
                party_snapshot=party_snapshot,
            )
        )
    ]

    if not rescue_candidates:
        return None

    return min(
        rescue_candidates,
        key=lambda npc: (
            0 if is_party_objective_add_rescue_threat(args, party_snapshot, npc) else 1,
            combat_distance_to(client, npc),
        ),
    )


PARTY_ATTACK_PATTERNS = (
    re.compile(
        r"^(?P<attacker>.+?)\s+attacks\s+(?P<victim>.+?)\s+and\s+"
        r"(?:hits|misses|is\s+blocked|is\s+parried|is\s+evaded)!?$",
        re.IGNORECASE,
    ),
)


KOREAN_INCOMING_DAMAGE_ATTACKER_PATTERN = re.compile(
    r"^(?P<attacker>.+?)이\(가\)\s*당신(?:의\s*.+?에게|에게)\s+(?P<amount>\d+)(?:\s*\([^)]*\))?\s*피해를\s+입혔습니다!?\s*$",
    re.IGNORECASE,
)


def parse_incoming_damage_attacker_name(text: str) -> str:
    match = KOREAN_INCOMING_DAMAGE_ATTACKER_PATTERN.match(str(text or "").strip())
    if match is None:
        return ""

    return match.group("attacker").strip()


def parse_korean_incoming_damage_amount(text: str) -> int:
    match = KOREAN_INCOMING_DAMAGE_ATTACKER_PATTERN.match(str(text or "").strip())
    if match is None:
        return 0

    return int(match.group("amount"))


def parse_party_attack_message(text: str, member_names: list[str]) -> PartyAttackMessage | None:
    normalized = str(text or "").strip()
    if not normalized:
        return None

    member_names_by_normalized = {
        normalize_target_name(member_name): member_name
        for member_name in member_names
        if normalize_target_name(member_name)
    }

    if not member_names_by_normalized:
        return None

    for pattern in PARTY_ATTACK_PATTERNS:
        match = pattern.match(normalized)
        if match is None:
            continue

        victim_name = member_names_by_normalized.get(normalize_target_name(match.group("victim")))
        if not victim_name:
            return None

        return PartyAttackMessage(match.group("attacker").strip(), victim_name)

    return None


def choose_attack_message_rescue_attacker(
    npcs,
    client,
    args: argparse.Namespace,
    leader_target_id: int,
    attacker_name: str,
):
    attacker_key = normalize_target_name(attacker_name)
    if not attacker_key:
        return None

    candidates = [
        npc
        for npc in npcs
        if int(getattr(npc, "object_id", 0) or 0) > 0
        and int(getattr(npc, "object_id", 0) or 0) != leader_target_id
        and normalize_target_name(str(getattr(npc, "name", "") or "")) == attacker_key
        and should_accept_party_rescue_target(args, npc)
        and not target_home_leash_violation(client, args, npc)[0]
        and (
            float(getattr(args, "party_rescue_max_distance", 0.0) or 0.0) <= 0.0
            or combat_distance_to(client, npc) <= float(getattr(args, "party_rescue_max_distance", 0.0) or 0.0)
        )
    ]

    if not candidates:
        return None

    return min(candidates, key=lambda npc: combat_distance_to(client, npc))


def choose_named_rescue_attacker(
    npcs,
    client,
    args: argparse.Namespace,
    leader_target_id: int,
    attacker_name: str,
):
    attacker_key = normalize_target_name(attacker_name)
    if not attacker_key:
        return None

    candidates = [
        npc
        for npc in npcs
        if int(getattr(npc, "object_id", 0) or 0) > 0
        and int(getattr(npc, "object_id", 0) or 0) != leader_target_id
        and normalize_target_name(str(getattr(npc, "name", "") or "")) == attacker_key
        and should_accept_party_rescue_target(args, npc)
        and not target_home_leash_violation(client, args, npc)[0]
    ]

    if not candidates:
        return None

    return min(candidates, key=lambda npc: combat_distance_to(client, npc))


def refresh_exact_rescue_threat_from_attacker_name(
    party_state: PartyState | None,
    client,
    args: argparse.Namespace,
    party_member_name: str,
    attacker_name: str,
) -> bool:
    if party_state is None or not attacker_name:
        return False

    party_snapshot = party_state.snapshot()
    leader_target_id = int(party_snapshot.get("leader_target_id", 0) or 0)
    attacker = choose_named_rescue_attacker(
        client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args)),
        client,
        args,
        leader_target_id,
        attacker_name,
    )
    if attacker is None:
        return False

    objective_add = is_combat_proven_party_objective_add(args, party_snapshot, attacker)
    if party_state.request_rescue(
        party_member_name,
        attacker,
        leader_target_id=leader_target_id,
        min_hold=args.party_rescue_min_hold,
        objective_add=objective_add,
    ):
        return True

    return party_state.record_rescue_threat(party_member_name, attacker, objective_add=objective_add)


def should_party_member_use_local_rescue_target(args: argparse.Namespace, action_rotation: str, health_percent: int) -> bool:
    if not getattr(args, "party_local_rescue_target", False):
        return False

    if action_rotation == "healer-support":
        if should_preserve_party_target_on_loss(args):
            return False

        threshold = int(getattr(args, "party_healer_local_rescue_health_percent", 0) or 0)
        return threshold > 0 and 0 < health_percent <= threshold

    if action_rotation == "caster-basic":
        return bool(getattr(args, "party_caster_assist_rescue_target", False))

    return True


def local_rescue_window_active(now: float, local_rescue_until: float) -> bool:
    return local_rescue_until > 0 and now <= local_rescue_until


def should_hold_party_assist_for_local_rescue(
    args: argparse.Namespace,
    *,
    now: float,
    local_rescue_until: float,
    current_target: int,
    leader_target_id: int,
) -> bool:
    return bool(
        getattr(args, "party_local_rescue_target", False)
        and local_rescue_window_active(now, local_rescue_until)
        and current_target > 0
        and current_target != leader_target_id
    )


def should_hold_party_assist_for_rescue_target(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str],
    *,
    now: float,
    current_target: int,
    party_member_name: str,
    action_rotation: str,
    health_percent: int,
) -> bool:
    if not getattr(args, "party_rescue_aggro", False) or current_target <= 0:
        return False

    rescue_target_id = int(party_snapshot.get("rescue_target_id", 0) or 0)
    leader_target_id = int(party_snapshot.get("leader_target_id", 0) or 0)

    if rescue_target_id <= 0 or current_target != rescue_target_id or current_target == leader_target_id:
        return False

    rescue_age = party_rescue_target_age(party_snapshot, rescue_target_id, now)
    max_age = max(0.0, float(getattr(args, "party_rescue_max_age", 0.0) or 0.0))

    if rescue_age < 0.0 or (max_age > 0.0 and rescue_age > max_age):
        return False

    return should_party_member_handle_rescue_target(
        args,
        party_snapshot,
        party_member_name,
        action_rotation,
        health_percent,
        rescue_age=rescue_age,
    )


def choose_party_rescue_threat_target(
    npcs,
    client,
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str],
    *,
    member_name: str,
    action_rotation: str,
    health_percent: int,
    now: float,
    current_target: int = 0,
):
    if not getattr(args, "party_rescue_aggro", False):
        return None

    leader_target_id = int(party_snapshot.get("leader_target_id", 0) or 0)
    visible_by_id = {
        int(getattr(npc, "object_id", 0) or 0): npc
        for npc in npcs
        if int(getattr(npc, "object_id", 0) or 0) > 0
    }
    max_age = max(0.0, float(getattr(args, "party_rescue_max_age", 0.0) or 0.0))
    max_distance = max(0.0, float(getattr(args, "party_rescue_max_distance", 0.0) or 0.0))
    candidates: list[dict[str, object]] = []

    for threat in party_snapshot.get("rescue_threats", []) or []:
        if not isinstance(threat, dict):
            continue

        threat_id = int(threat.get("object_id", 0) or 0)
        if threat_id <= 0 or threat_id == leader_target_id:
            continue

        requested_at = float(threat.get("requested_at", 0.0) or 0.0)
        threat_age = now - requested_at
        if threat_age < 0.0 or (max_age > 0.0 and threat_age > max_age):
            continue

        npc = visible_by_id.get(threat_id)
        if npc is None or not should_accept_party_rescue_target(args, npc):
            continue

        objective_add = bool(threat.get("objective_add", True))
        distance = combat_distance_to(client, npc)
        if not objective_add and max_distance > 0.0 and distance > max_distance:
            continue

        candidates.append(
            {
                "id": threat_id,
                "age": threat_age,
                "objective_add": objective_add,
                "member_name": str(threat.get("member_name", "") or ""),
                "victim_role": party_member_role(party_snapshot, str(threat.get("member_name", "") or "")),
                "distance": distance,
                "npc": npc,
            }
        )

    if not candidates:
        return None

    def can_handle(candidate: dict[str, object], name: str, role: str, hp: int) -> bool:
        if leader_target_id <= 0 and is_party_tank_role(role):
            return True

        victim_name = str(candidate.get("member_name", "") or "")
        victim_role = str(candidate.get("victim_role", "") or "")
        victim_health = party_member_health_percent(party_snapshot, victim_name)
        peer_rescue_threshold = int(getattr(args, "party_rescue_peer_health_percent", 0) or 0)
        peer_rescue_is_urgent = bool(
            victim_name
            and peer_rescue_threshold > 0
            and 0 < victim_health <= peer_rescue_threshold
        )

        if (
            bool(candidate["objective_add"])
            and (party_member_is_rescue_tank(party_snapshot, name) or role in {"melee-basic", "hybrid"})
            and not should_party_member_hold_shared_objective(args, party_snapshot, name)
            and (
                not victim_name
                or is_support_pressure_role(victim_role)
                or peer_rescue_is_urgent
            )
        ):
            return True

        return should_party_member_handle_rescue_target(
            args,
            {
                **party_snapshot,
                "rescue_target_objective_add": bool(candidate["objective_add"]),
                "rescue_member_name": victim_name,
            },
            name,
            role,
            hp,
            rescue_age=float(candidate["age"]),
        )

    if current_target:
        current_candidate = next(
            (
                candidate
                for candidate in candidates
                if int(candidate["id"]) == current_target
                and str(candidate.get("member_name", "") or "")
                and can_handle(candidate, member_name, action_rotation, health_percent)
            ),
            None,
        )
        if current_candidate is not None:
            return current_candidate["npc"]

    support_focus_candidates = [
        candidate
        for candidate in candidates
        if should_assist_dangerous_support_rescue_threat(
            args,
            action_rotation,
            float(candidate["age"]),
            str(candidate.get("victim_role", "") or ""),
        )
    ]
    if (
        support_focus_candidates
        and not should_party_member_hold_shared_objective(args, party_snapshot, member_name)
    ):
        return min(
            support_focus_candidates,
            key=lambda candidate: (
                0 if current_target and int(candidate["id"]) == current_target else 1,
                -float(candidate["age"]),
                float(candidate["distance"]),
                int(candidate["id"]),
            ),
        )["npc"]

    if not can_handle(
        min(candidates, key=lambda candidate: (float(candidate["distance"]), int(candidate["id"]))),
        member_name,
        action_rotation,
        health_percent,
    ) and not any(can_handle(candidate, member_name, action_rotation, health_percent) for candidate in candidates):
        return None

    members = party_snapshot.get("members", []) or []
    if isinstance(members, list) and len(members) > 1:
        eligible_names: list[str] = []

        for member in members:
            if not isinstance(member, dict):
                continue

            candidate_name = str(member.get("name", "") or "")
            candidate_role = str(member.get("role", "") or "")
            candidate_health = int(member.get("health_percent", 0) or 0)
            if not candidate_name or candidate_health <= 0:
                continue

            if any(can_handle(candidate, candidate_name, candidate_role, candidate_health) for candidate in candidates):
                eligible_names.append(candidate_name)

        if member_name not in eligible_names:
            return None

        member_index = eligible_names.index(member_name)
        assigned_candidates = [
            candidate
            for index, candidate in enumerate(sorted(candidates, key=lambda item: int(item["id"])))
            if index % len(eligible_names) == member_index
        ]
        for candidate in assigned_candidates:
            if can_handle(candidate, member_name, action_rotation, health_percent):
                return candidate["npc"]

        return None

    fallback_candidates = [
        (
            0 if current_target and int(candidate["id"]) == current_target else 1,
            float(candidate["distance"]),
            int(candidate["id"]),
            candidate["npc"],
        )
        for candidate in candidates
        if can_handle(candidate, member_name, action_rotation, health_percent)
    ]
    if not fallback_candidates:
        return None

    return min(fallback_candidates, key=lambda candidate: (candidate[0], candidate[1], candidate[2]))[3]


def current_target_is_party_rescue_target(party_snapshot: dict[str, int | float | str], current_target: int) -> bool:
    return bool(current_target > 0 and int(party_snapshot.get("rescue_target_id", 0) or 0) == current_target)


def current_target_bypasses_target_home_leash(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str],
    current_target: int,
) -> bool:
    return bool(
        getattr(args, "party_rescue_aggro", False)
        and current_target_is_party_rescue_target(party_snapshot, current_target)
    )


def should_abandon_party_rescue_counterattack_for_flee(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str],
    *,
    current_target: int,
    current_health_percent: int,
    previous_health_percent: int,
) -> bool:
    health_floor = int(getattr(args, "flee_melee_counterattack_health_floor", 0) or 0)
    return bool(
        health_floor > 0
        and current_target_bypasses_target_home_leash(args, party_snapshot, current_target)
        and previous_health_percent > 0
        and current_health_percent > 0
        and current_health_percent < previous_health_percent
        and current_health_percent <= health_floor
    )


def party_member_role(snapshot: dict[str, int | float | str], member_name: str) -> str:
    if not member_name:
        return ""

    for member in snapshot.get("members", []) or []:
        if not isinstance(member, dict):
            continue

        if str(member.get("name", "") or "") == member_name:
            return str(member.get("role", "") or "")

    return ""


def party_member_health_percent(snapshot: dict[str, int | float | str], member_name: str) -> int:
    if not member_name:
        return 0

    for member in snapshot.get("members", []) or []:
        if not isinstance(member, dict):
            continue

        if str(member.get("name", "") or "") == member_name:
            return int(member.get("health_percent", 0) or 0)

    return 0


def is_support_pressure_role(role: str) -> bool:
    return role in {"healer-support", "caster-basic"}


def party_rescue_threat_victim_role(
    snapshot: dict[str, int | float | str],
    target_id: int,
) -> str:
    threat = party_rescue_threat_snapshot(snapshot, target_id)
    if threat is None:
        return ""

    return party_member_role(snapshot, str(threat.get("member_name", "") or ""))


def should_assist_dangerous_support_rescue_threat(
    args: argparse.Namespace,
    action_rotation: str,
    rescue_age: float,
    victim_role: str,
) -> bool:
    if action_rotation == "healer-support" or not is_support_pressure_role(victim_role):
        return False

    if action_rotation == "caster-basic" and not getattr(args, "party_caster_assist_rescue_target", False):
        return False

    if not is_party_tank_role(action_rotation) and action_rotation != "caster-basic":
        return False

    assist_after = max(0.0, float(getattr(args, "party_rescue_emergency_assist_after", 0.0) or 0.0))
    if assist_after <= 0.0:
        return False

    return rescue_age >= assist_after


def is_rescue_threat_in_range(
    client,
    npc,
    args: argparse.Namespace,
    max_distance: float,
    party_snapshot: dict[str, int | float | str] | None = None,
) -> bool:
    distance = combat_distance_to(client, npc)

    if max_distance > 0 and distance > max_distance:
        return False

    engaged_distance = float(getattr(args, "party_rescue_engaged_distance", 0.0) or 0.0)
    return engaged_distance <= 0 or distance <= engaged_distance or is_party_objective_add_rescue_threat(args, party_snapshot, npc)


def choose_local_rescue_target(npcs, client, args: argparse.Namespace, leader_target_id: int, current_target: int = 0):
    max_distance = float(getattr(args, "party_local_rescue_max_distance", 0.0) or 0.0)
    rescue_candidates = [
        npc
        for npc in npcs
        if int(getattr(npc, "object_id", 0) or 0) > 0
        and npc.object_id != leader_target_id
        and not is_required_target(args, npc)
        and should_accept_party_rescue_target(args, npc)
        and is_rescue_threat_in_range(client, npc, args, max_distance)
    ]

    if not rescue_candidates:
        return None

    if current_target:
        for npc in rescue_candidates:
            if npc.object_id == current_target:
                return npc

    return min(rescue_candidates, key=lambda npc: combat_distance_to(client, npc))


def choose_party_support_evasion_threat(
    npcs,
    client,
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str],
    *,
    action_rotation: str,
    now: float,
    local_rescue_until: float,
    precast_movement_hold: bool = False,
):
    if not bool(getattr(args, "party_support_evasion", False)):
        return None

    del precast_movement_hold

    if action_rotation not in {"caster-basic", "healer-support"}:
        return None

    if not getattr(args, "party_rescue_aggro", False):
        return None

    if should_preserve_party_target_on_loss(args) and float(party_snapshot.get("leader_target_engaged_at", 0.0) or 0.0) <= 0.0:
        return None

    local_rescue_active = local_rescue_window_active(now, local_rescue_until)
    leader_target_id = int(party_snapshot.get("leader_target_id", 0) or 0)
    max_age = max(0.0, float(getattr(args, "party_rescue_max_age", 0.0) or 0.0))
    max_distance = max(0.0, float(getattr(args, "party_rescue_max_distance", 0.0) or 0.0))
    visible_by_id = {
        int(getattr(npc, "object_id", 0) or 0): npc
        for npc in npcs
        if int(getattr(npc, "object_id", 0) or 0) > 0
    }
    candidates = []

    for threat in party_snapshot.get("rescue_threats", []) or []:
        if not isinstance(threat, dict):
            continue

        threat_id = int(threat.get("object_id", 0) or 0)
        if threat_id <= 0 or threat_id == leader_target_id:
            continue

        requested_at = float(threat.get("requested_at", 0.0) or 0.0)
        threat_age = now - requested_at
        if threat_age < 0.0 or (max_age > 0.0 and threat_age > max_age):
            continue

        npc = visible_by_id.get(threat_id)
        if npc is None or is_required_target(args, npc) or not should_accept_party_rescue_target(args, npc):
            continue

        objective_add = bool(threat.get("objective_add", False))
        if not local_rescue_active and not objective_add:
            continue

        distance = combat_distance_to(client, npc)
        if not objective_add and max_distance > 0.0 and distance > max_distance:
            continue

        candidates.append((distance, threat_id, npc))

    if not candidates:
        return None

    return min(candidates, key=lambda candidate: (candidate[0], candidate[1]))[2]


def should_run_smooth_combat_movement(
    args: argparse.Namespace,
    action_rotation: str,
    current_target: int,
    party_state,
) -> bool:
    if current_target:
        return True

    return bool(
        party_state is not None
        and action_rotation in {"caster-basic", "healer-support"}
        and getattr(args, "party_support_evasion", False)
        and getattr(args, "party_rescue_aggro", False)
    )


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
    if args.party_slot_rotations:
        rotations = args.party_slot_rotations
        return rotations[party_slot % len(rotations)]

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


def resolve_effective_action_rotation(
    args: argparse.Namespace,
    requested_rotation: str,
    combat_plan: CombatUsablePlan,
    combat_plan_loaded: bool,
) -> str:
    if requested_rotation in {"auto", "none"} or not combat_plan_loaded:
        return requested_rotation

    can_use_raw_spells = bool(getattr(args, "allow_unvalidated_spells", False))
    can_use_raw_skills = bool(getattr(args, "allow_unvalidated_skills", False))
    has_attack_spell = bool(combat_plan.attack_spells) or can_use_raw_spells
    has_heal_spell = bool(combat_plan.heal_spells) or can_use_raw_spells
    has_skill = bool(combat_plan.skills) or can_use_raw_skills

    if requested_rotation == "healer-support" and not has_heal_spell:
        if has_attack_spell:
            return "caster-basic"
        if has_skill:
            return "melee-basic"

    if requested_rotation in {"caster-basic", "hybrid"} and not has_attack_spell:
        if has_skill:
            return "melee-basic"

    if is_melee_rotation(requested_rotation) and not has_skill:
        if has_attack_spell:
            return "caster-basic"

    return requested_rotation


TAUNT_SKILL_NAME_TOKENS = ("taunt", "provoke", "enrage", "draw out", "engage")


def is_taunt_skill(skill: UsableSkillRef) -> bool:
    name = " ".join(str(skill.name or "").lower().split())
    return any(token in name for token in TAUNT_SKILL_NAME_TOKENS)


def choose_combat_skill(
    rng: random.Random,
    args: argparse.Namespace,
    skills: list[UsableSkillRef],
    *,
    taunt_skills: list[UsableSkillRef] | None = None,
    prefer_taunt_skill: bool = False,
) -> tuple[UsableSkillRef, bool]:
    if prefer_taunt_skill:
        taunt_skills = taunt_skills if taunt_skills is not None else [skill for skill in skills if is_taunt_skill(skill)]

        if taunt_skills:
            return max(taunt_skills, key=lambda skill: (skill.level, skill.name)), True

    pool = skills[: min(len(skills), args.combat_plan_skill_pool)]
    return rng.choice(pool), False


def perform_rotation_action(
    client,
    rng: random.Random,
    args: argparse.Namespace,
    rotation: str,
    distance: float,
    combat_plan: CombatUsablePlan | None = None,
    prefer_taunt_skill: bool = False,
) -> str | None:
    if rotation == "none":
        return None

    target_in_view = distance <= max(args.attack_range, args.spell_range)
    movement_speed = getattr(client, "last_position_speed", 0.0)
    stationary_cast = bool(getattr(args, "stationary_cast_actions", False))
    allow_unvalidated_skills = bool(getattr(args, "allow_unvalidated_skills", False))
    allow_unvalidated_spells = bool(getattr(args, "allow_unvalidated_spells", False))

    if rotation == "melee-basic":
        if distance > args.attack_range:
            return None
        if combat_plan is not None and combat_plan.skills:
            skill, taunt_selected = choose_combat_skill(
                rng,
                args,
                combat_plan.skills,
                taunt_skills=combat_plan.taunt_skills,
                prefer_taunt_skill=prefer_taunt_skill,
            )
            client.use_skill(skill.use_skill_index, skill_type=skill.use_skill_type, speed=movement_speed)
            return "validated_taunt_skill" if taunt_selected else "validated_skill"
        if not allow_unvalidated_skills:
            return None
        client.use_skill(rng.choice(args.skill_indexes), skill_type=args.skill_type, speed=movement_speed)
        return "skill"

    if rotation == "melee-burst":
        if distance > args.attack_range:
            return None
        if combat_plan is not None and combat_plan.skills:
            skill, taunt_selected = choose_combat_skill(
                rng,
                args,
                combat_plan.skills,
                taunt_skills=combat_plan.taunt_skills,
                prefer_taunt_skill=prefer_taunt_skill,
            )
            client.use_skill(skill.use_skill_index, skill_type=skill.use_skill_type, speed=movement_speed)
            return "validated_taunt_skill" if taunt_selected else "validated_burst_skill"
        if not allow_unvalidated_skills:
            return None
        client.use_skill(rng.choice(args.skill_indexes), skill_type=args.skill_type, speed=movement_speed)
        return "burst_skill"

    if rotation == "caster-basic":
        if distance > args.spell_range:
            return None
        if combat_plan is not None and combat_plan.attack_spells:
            spell = rng.choice(combat_plan.attack_spells[: min(len(combat_plan.attack_spells), args.combat_plan_spell_pool)])
            cast_usable_spell(client, spell, target_in_view=target_in_view, speed=movement_speed, stationary=stationary_cast)
            return "validated_spell"
        if not allow_unvalidated_spells:
            return None
        cast_raw_spell(
            client,
            rng.choice(args.spell_levels),
            spell_line_index=args.spell_line_index,
            target_in_view=target_in_view,
            speed=movement_speed,
            stationary=stationary_cast,
        )
        return "spell"

    if rotation == "healer-support":
        if client.health_percent <= args.healer_self_health_percent:
            if combat_plan is not None and combat_plan.heal_spells:
                spell = rng.choice(combat_plan.heal_spells[: min(len(combat_plan.heal_spells), args.combat_plan_spell_pool)])
                cast_usable_spell(client, spell, target_in_view=True, speed=movement_speed, stationary=stationary_cast)
                return "validated_self_heal_spell"
            if not allow_unvalidated_spells:
                return None
            cast_raw_spell(
                client,
                rng.choice(args.heal_spell_levels),
                spell_line_index=args.heal_spell_line_index,
                target_in_view=True,
                speed=movement_speed,
                stationary=stationary_cast,
            )
            return "self_heal_spell"

        if args.support_spell_chance > 0 and rng.random() < args.support_spell_chance:
            if combat_plan is not None and combat_plan.attack_spells:
                spell = rng.choice(combat_plan.attack_spells[: min(len(combat_plan.attack_spells), args.combat_plan_spell_pool)])
                cast_usable_spell(client, spell, target_in_view=target_in_view, speed=movement_speed, stationary=stationary_cast)
                return "validated_support_spell"
            if not allow_unvalidated_spells:
                return None
            cast_raw_spell(
                client,
                rng.choice(args.spell_levels),
                spell_line_index=args.spell_line_index,
                target_in_view=target_in_view,
                speed=movement_speed,
                stationary=stationary_cast,
            )
            return "support_spell"

        return None

    if rotation == "hybrid":
        if distance <= args.attack_range and rng.random() < args.hybrid_melee_chance:
            if combat_plan is not None and combat_plan.skills:
                skill, taunt_selected = choose_combat_skill(
                    rng,
                    args,
                    combat_plan.skills,
                    taunt_skills=combat_plan.taunt_skills,
                    prefer_taunt_skill=prefer_taunt_skill,
                )
                client.use_skill(skill.use_skill_index, skill_type=skill.use_skill_type, speed=movement_speed)
                return "validated_taunt_skill" if taunt_selected else "validated_skill"
            if not allow_unvalidated_skills:
                return None
            client.use_skill(rng.choice(args.skill_indexes), skill_type=args.skill_type, speed=movement_speed)
            return "skill"

        if distance <= args.spell_range:
            if combat_plan is not None and combat_plan.attack_spells:
                spell = rng.choice(combat_plan.attack_spells[: min(len(combat_plan.attack_spells), args.combat_plan_spell_pool)])
                cast_usable_spell(client, spell, target_in_view=target_in_view, speed=movement_speed, stationary=stationary_cast)
                return "validated_spell"
            if not allow_unvalidated_spells:
                return None
            cast_raw_spell(
                client,
                rng.choice(args.spell_levels),
                spell_line_index=args.spell_line_index,
                target_in_view=target_in_view,
                speed=movement_speed,
                stationary=stationary_cast,
            )
            return "spell"

    return None


def should_healer_self_preserve_during_rest(
    args: argparse.Namespace,
    *,
    action_rotation: str,
    current_health_percent: int,
    now: float,
    next_self_preserve_heal: float,
) -> bool:
    return bool(
        action_rotation == "healer-support"
        and current_health_percent > 0
        and current_health_percent <= int(getattr(args, "healer_self_health_percent", 0) or 0)
        and now >= next_self_preserve_heal
    )


def should_healer_abort_rest_for_party_heal(
    args: argparse.Namespace,
    *,
    action_rotation: str,
    current_health_percent: int,
    hurt_member,
) -> bool:
    return bool(
        action_rotation == "healer-support"
        and hurt_member is not None
        and current_health_percent > int(getattr(args, "healer_self_health_percent", 0) or 0)
    )


def should_healer_prioritize_party_heal_during_rest(
    args: argparse.Namespace,
    *,
    action_rotation: str,
    current_health_percent: int,
    hurt_member,
) -> bool:
    if action_rotation != "healer-support" or not isinstance(hurt_member, dict):
        return False

    self_emergency_floor = int(getattr(args, "flee_health_percent", 0) or 0)
    if current_health_percent <= self_emergency_floor:
        return False

    hurt_health = int(hurt_member.get("health_percent", 0) or 0)
    if hurt_health <= 0:
        return False

    heal_threshold = int(getattr(args, "party_heal_leader_health_percent", 0) or 0)
    critical_party_health = max(self_emergency_floor, min(50, int(heal_threshold * 0.5) if heal_threshold > 0 else 35))
    return hurt_health <= critical_party_health


def perform_healer_self_preserve_cast(
    client,
    rng: random.Random,
    args: argparse.Namespace,
    combat_plan: CombatUsablePlan | None,
) -> str | None:
    movement_speed = 0.0
    stationary_cast = bool(getattr(args, "stationary_cast_actions", False))
    allow_unvalidated_spells = bool(getattr(args, "allow_unvalidated_spells", False))
    if hasattr(client, "send_command"):
        client.send_command("/stand")
    self_object_id = int(getattr(client, "player_object_id", 0) or 0)
    if self_object_id > 0 and hasattr(client, "target_object"):
        client.target_object(self_object_id)

    if combat_plan is not None and combat_plan.heal_spells:
        spell = rng.choice(combat_plan.heal_spells[: min(len(combat_plan.heal_spells), args.combat_plan_spell_pool)])
        cast_usable_spell(client, spell, target_in_view=True, speed=movement_speed, stationary=stationary_cast)
        return "validated_self_preserve_heal_spell"

    if not allow_unvalidated_spells:
        return None

    cast_raw_spell(
        client,
        rng.choice(args.heal_spell_levels),
        spell_line_index=args.heal_spell_line_index,
        target_in_view=True,
        speed=movement_speed,
        stationary=stationary_cast,
    )
    return "self_preserve_heal_spell"


def perform_due_rotation_action(
    client,
    rng: random.Random,
    args: argparse.Namespace,
    rotation: str,
    distance: float,
    combat_plan: CombatUsablePlan | None,
    *,
    active_combat,
    now: float,
    next_skill: float,
    reaggro_taunt_due: bool,
    prefer_taunt_skill: bool,
    next_active_tank_reaggro_taunt: float,
) -> tuple[str | None, float, float]:
    if not args.use_skills or (now < next_skill and not reaggro_taunt_due):
        return None, next_skill, next_active_tank_reaggro_taunt

    rotation_action = perform_rotation_action(
        client,
        rng,
        args,
        rotation,
        distance,
        combat_plan,
        prefer_taunt_skill=prefer_taunt_skill,
    )

    if rotation_action is not None and active_combat is not None:
        active_combat["skills"] = int(active_combat.get("skills", 0) or 0) + 1

    if rotation_action is not None:
        if reaggro_taunt_due:
            next_active_tank_reaggro_taunt = now + args.party_active_tank_reaggro_taunt_interval
        else:
            next_skill = now + args.skill_interval + rng.uniform(0, args.jitter)

    return rotation_action, next_skill, next_active_tank_reaggro_taunt


def rotation_action_is_spell(action_name: str | None) -> bool:
    return bool(action_name and "spell" in action_name)


def should_hold_precast_movement(
    args: argparse.Namespace,
    action_rotation: str,
    *,
    combat_plan: CombatPlan | None,
    heal_due: bool,
    buff_due: bool,
    offensive_due: bool,
    current_target_distance: float,
    tactical_backoff: bool,
) -> bool:
    if tactical_backoff:
        return False

    allow_unvalidated_spells = bool(getattr(args, "allow_unvalidated_spells", False))

    if action_rotation == "healer-support":
        has_heal = bool(getattr(combat_plan, "heal_spells", None)) or allow_unvalidated_spells
        has_buff = bool(getattr(combat_plan, "buff_spells", None)) or allow_unvalidated_spells
        has_attack = bool(getattr(combat_plan, "attack_spells", None)) or allow_unvalidated_spells
        in_spell_range = current_target_distance <= float(getattr(args, "spell_range", 1500.0) or 1500.0)
        return bool((heal_due and has_heal) or (buff_due and has_buff) or (offensive_due and has_attack and in_spell_range))

    if action_rotation == "caster-basic":
        has_attack = bool(getattr(combat_plan, "attack_spells", None)) or allow_unvalidated_spells
        in_spell_range = current_target_distance <= float(getattr(args, "spell_range", 1500.0) or 1500.0)
        return bool(offensive_due and has_attack and in_spell_range)

    return False


def should_continue_cast_action_hold(cast_action_hold_until: float, now: float) -> bool:
    return bool(cast_action_hold_until > 0.0 and now < cast_action_hold_until)


def effective_cast_action_hold_seconds(args: argparse.Namespace, action_name: str | None) -> float:
    if not rotation_action_is_spell(action_name):
        return 0.0

    configured = max(0.0, float(getattr(args, "cast_action_hold", 0.0) or 0.0))
    if not bool(getattr(args, "stationary_cast_actions", False)):
        return configured

    minimum = max(0.0, float(getattr(args, "stationary_cast_min_hold", 3.4) or 3.4))
    return max(configured, minimum)


def combat_distance_to(client, actor) -> float:
    if hasattr(client, "horizontal_distance_to"):
        return float(client.horizontal_distance_to(actor))

    return float(client.distance_to(actor))


def heading_from_delta(dx: float, dy: float) -> int:
    if dx == 0 and dy == 0:
        return 0

    radians = math.atan2(-dx, dy)
    return int((radians % (math.pi * 2)) / (math.pi * 2) * 4096) & 0x0FFF


def face_target_for_attack(client, actor) -> None:
    dx = actor.x - client.x
    dy = actor.y - client.y

    if dx or dy:
        client.heading = heading_from_delta(dx, dy)

    client.send_heading(client.heading, drain_after=False)


def move_away_from_actor(
    client,
    actor,
    *,
    step: float,
    min_distance: float,
    args: argparse.Namespace,
    target_in_view: bool = True,
) -> bool:
    dx = int(client.x) - int(getattr(actor, "x", 0) or 0)
    dy = int(client.y) - int(getattr(actor, "y", 0) or 0)
    distance = math.sqrt(dx * dx + dy * dy)

    if min_distance <= 0 or distance >= min_distance:
        client.send_position_update(speed=0.0, target_in_view=target_in_view)
        return False

    if distance <= 0:
        radians = (int(client.heading) & 0x0FFF) / 4096.0 * math.pi * 2
        dx = int(-math.sin(radians) * 100)
        dy = int(math.cos(radians) * 100)
        distance = max(1.0, math.sqrt(dx * dx + dy * dy))

    safe_step = max(step, min_distance - distance)
    target_x = int(client.x + dx / distance * safe_step)
    target_y = int(client.y + dy / distance * safe_step)

    return client.move_towards_position(
        target_x,
        target_y,
        int(client.z),
        step=step,
        stop_distance=0.0,
        movement_speed=getattr(args, "movement_speed", None),
        min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
        target_in_view=target_in_view,
    )


def move_away_from_point(
    client,
    x: int,
    y: int,
    *,
    step: float,
    min_distance: float,
    args: argparse.Namespace,
    target_in_view: bool = False,
) -> bool:
    dx = int(client.x) - int(x)
    dy = int(client.y) - int(y)
    distance = math.sqrt(dx * dx + dy * dy)

    if min_distance <= 0 or distance >= min_distance:
        client.send_position_update(speed=0.0, target_in_view=target_in_view)
        return False

    if distance <= 0:
        radians = (int(client.heading) & 0x0FFF) / 4096.0 * math.pi * 2
        dx = int(-math.sin(radians) * 100)
        dy = int(math.cos(radians) * 100)
        distance = max(1.0, math.sqrt(dx * dx + dy * dy))

    safe_step = max(step, min_distance - distance)
    target_x = int(client.x + dx / distance * safe_step)
    target_y = int(client.y + dy / distance * safe_step)

    return client.move_towards_position(
        target_x,
        target_y,
        int(client.z),
        step=step,
        stop_distance=0.0,
        movement_speed=getattr(args, "movement_speed", None),
        min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
        target_in_view=target_in_view,
    )


def face_point_for_attack(client, x: int, y: int) -> None:
    dx = int(x) - int(client.x)
    dy = int(y) - int(client.y)

    if dx or dy:
        client.heading = heading_from_delta(dx, dy)

    client.send_heading(client.heading, drain_after=False)


def close_server_los_reposition_step(args: argparse.Namespace) -> float:
    return max(80.0, min(160.0, float(getattr(args, "attack_range", 350.0) or 350.0) * 0.4))


def reposition_after_close_server_los_failure(
    client,
    args: argparse.Namespace,
    target,
    action_counts: dict[str, int],
) -> bool:
    target_base_x = int(getattr(target, "x", client.x))
    target_base_y = int(getattr(target, "y", client.y))
    target_base_z = int(getattr(target, "z", client.z))
    dx = int(client.x) - target_base_x
    dy = int(client.y) - target_base_y
    distance = math.sqrt(dx * dx + dy * dy)
    close_limit = max(32.0, float(getattr(args, "minimum_melee_stop_distance", 60.0) or 60.0))
    if distance > close_limit:
        return False

    if distance <= 0.0:
        radians = (int(getattr(client, "heading", 0)) & 0x0FFF) / 4096.0 * math.pi * 2
        dx = int(-math.sin(radians) * 100)
        dy = int(math.cos(radians) * 100)
        distance = max(1.0, math.sqrt(dx * dx + dy * dy))

    step = close_server_los_reposition_step(args)
    side = -1.0 if int(getattr(target, "object_id", 0) or 0) % 2 else 1.0
    sidestep_x = -dy / distance * step * side
    sidestep_y = dx / distance * step * side
    target_x = int(client.x + sidestep_x)
    target_y = int(client.y + sidestep_y)
    moved = client.move_towards_position(
        target_x,
        target_y,
        target_base_z,
        step=step,
        stop_distance=0.0,
        movement_speed=getattr(args, "movement_speed", None),
        min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
        target_in_view=True,
    )
    face_point_for_attack(client, target_base_x, target_base_y)
    client.send_position_update(speed=0.0, target_in_view=True)
    add_action(action_counts, "server_los_failure_reposition_move" if moved else "server_los_failure_reposition_hold")
    return moved


def should_retry_server_los_failure(
    active_combat: dict[str, object] | None,
    *,
    now: float,
    target_age: float,
    los_failure_grace: float,
    max_retries_after_hit: int,
) -> bool:
    if active_combat is None:
        return False

    if target_age < los_failure_grace:
        return True

    los_failures = max(0, int(active_combat.get("server_los_failures", 0) or 0))
    if max_retries_after_hit > 0 and los_failures >= max_retries_after_hit:
        return False

    last_damage_done_at = float(active_combat.get("last_damage_done_at", 0.0) or 0.0)
    if last_damage_done_at > 0.0 and now - last_damage_done_at <= los_failure_grace:
        return True

    last_combat_message_at = float(active_combat.get("last_combat_message_at", 0.0) or 0.0)
    if last_combat_message_at > 0.0 and now - last_combat_message_at <= los_failure_grace:
        return True

    return int(active_combat.get("damage_done", 0) or 0) > 0 and (
        max_retries_after_hit <= 0 or los_failures < max_retries_after_hit
    )


def should_treat_target_loss_as_server_los_failure(
    active_combat: dict[str, object] | None,
    *,
    max_retries_after_hit: int,
) -> bool:
    if active_combat is None:
        return False

    if int(active_combat.get("damage_taken", 0) or 0) <= 0:
        return False

    los_failures = max(0, int(active_combat.get("server_los_failures", 0) or 0))
    required_failures = max(3, int(math.ceil(max(1, max_retries_after_hit) / 2.0)))
    return los_failures >= required_failures


def active_combat_target_snapshot(active_combat: dict[str, object] | None, current_target: int):
    if active_combat is None:
        return None

    try:
        target_x = int(active_combat.get("target_x", 0) or 0)
        target_y = int(active_combat.get("target_y", 0) or 0)
        target_z = int(active_combat.get("target_z", 0) or 0)
    except (TypeError, ValueError):
        return None

    if target_x == 0 and target_y == 0:
        return None

    return SimpleNamespace(
        object_id=int(current_target),
        name=str(active_combat.get("target_name", "") or ""),
        level=int(active_combat.get("target_level", 0) or 0),
        x=target_x,
        y=target_y,
        z=target_z,
    )


def server_los_retry_target(
    client,
    args: argparse.Namespace,
    *,
    current_target: int,
    active_combat: dict[str, object] | None,
    observed_target,
):
    try:
        visible_target = choose_current_visible_target(
            client.visible_npcs(max_age=getattr(args, "npc_max_age", 60.0), include_peace=should_scan_peace_npcs(args)),
            current_target,
        )
    except Exception:
        visible_target = None

    if visible_target is not None:
        return visible_target, "visible_npc"

    if observed_target is not None:
        return observed_target, "api"

    snapshot = active_combat_target_snapshot(active_combat, current_target)
    if snapshot is not None:
        return snapshot, "last_known"

    return None, "none"


def facegloc_command_for_point(x: int, y: int) -> str:
    return f"/facegloc {int(x)} {int(y)}"


def melee_stop_distance(args: argparse.Namespace) -> float:
    return max(args.minimum_melee_stop_distance, args.attack_range - args.melee_range_buffer)


def combat_stop_distance(args: argparse.Namespace, action_rotation: str) -> float:
    if action_rotation in {"caster-basic", "healer-support"}:
        return max(melee_stop_distance(args), min(args.ranged_stop_distance, args.spell_range - 100.0))

    return melee_stop_distance(args)


def attack_action_distance(action_rotation: str, distance: float, effective_attack_distance: float) -> float:
    if is_melee_rotation(action_rotation):
        return distance

    return effective_attack_distance


def party_last_known_stop_distance(
    args: argparse.Namespace,
    action_rotation: str,
    snapshot: dict[str, int | float | str],
    member_name: str,
) -> float:
    normal_distance = combat_stop_distance(args, action_rotation)
    if not party_member_is_active_tank(snapshot, member_name) or not is_melee_rotation(action_rotation):
        return normal_distance

    configured = float(getattr(args, "party_active_tank_last_known_stop_distance", 0.0) or 0.0)
    if configured > 0:
        return min(normal_distance, configured)

    return min(normal_distance, max(20.0, float(args.minimum_melee_stop_distance) * 0.35))


def party_rescue_threat_snapshot(
    snapshot: dict[str, int | float | str],
    target_id: int,
) -> dict[str, object] | None:
    if target_id <= 0:
        return None

    for threat in snapshot.get("rescue_threats", []) or []:
        if not isinstance(threat, dict):
            continue

        if int(threat.get("object_id", 0) or 0) == target_id:
            return threat

    return None


def party_rescue_threat_last_known_destination(
    snapshot: dict[str, int | float | str],
    target_id: int,
):
    threat = party_rescue_threat_snapshot(snapshot, target_id)
    if threat is None:
        return None

    return destination_from_point(
        "party-rescue-last-known",
        int(threat.get("x", 0) or 0),
        int(threat.get("y", 0) or 0),
        int(threat.get("z", 0) or 0),
    )


def active_combat_last_known_destination(active_combat: dict[str, float | int | str] | None):
    if active_combat is None:
        return None

    return destination_from_point(
        "target-last-known",
        int(active_combat.get("target_x", 0) or 0),
        int(active_combat.get("target_y", 0) or 0),
        int(active_combat.get("target_z", 0) or 0),
    )


def party_rescue_target_age(
    snapshot: dict[str, int | float | str],
    target_id: int,
    now: float,
) -> float:
    threat = party_rescue_threat_snapshot(snapshot, target_id)
    if threat is not None:
        requested_at = float(threat.get("requested_at", 0.0) or 0.0)
        if requested_at > 0.0:
            return now - requested_at

    return now - float(snapshot.get("rescue_requested_at", 0.0) or 0.0)


def is_melee_rotation(action_rotation: str) -> bool:
    return action_rotation.startswith("melee")


def should_enable_attack_mode(args: argparse.Namespace, action_rotation: str, distance: float) -> bool:
    if is_melee_rotation(action_rotation) and args.melee_stick_attack:
        if args.melee_stick_attack_distance <= 0:
            return True

        return distance <= args.melee_stick_attack_distance
    if is_melee_rotation(action_rotation):
        return distance <= melee_stop_distance(args) + 25.0

    return distance <= args.attack_range


def should_count_attack_attempt(
    args: argparse.Namespace,
    action_rotation: str,
    *,
    attack_enabled: bool,
    action_distance: float,
) -> bool:
    if not attack_enabled:
        return False

    if action_distance <= args.attack_range:
        return True

    return bool(
        is_melee_rotation(action_rotation)
        and getattr(args, "melee_stick_attack", False)
        and (
            float(getattr(args, "melee_stick_attack_distance", 0.0) or 0.0) <= 0.0
            or action_distance <= float(getattr(args, "melee_stick_attack_distance", 0.0) or 0.0)
        )
    )


def recent_incoming_damage_matches_actor(
    actor,
    attacker_name: str,
    *,
    last_damage_at: float,
    now: float,
    grace_seconds: float = 4.0,
) -> bool:
    if actor is None or not attacker_name or last_damage_at <= 0.0 or grace_seconds <= 0.0:
        return False

    if now - last_damage_at > grace_seconds:
        return False

    actor_name = normalize_target_name(str(getattr(actor, "name", "") or ""))
    attacker = normalize_target_name(attacker_name)
    return bool(actor_name and attacker and actor_name == attacker)


def should_preserve_target_timeout_for_combat_progress(
    args: argparse.Namespace,
    active_combat: dict[str, float | int | str] | None,
    actor,
    *,
    recent_incoming_attacker_name: str,
    last_incoming_damage_at: float,
    now: float,
) -> bool:
    if active_combat is None or actor is None:
        return False

    active_target_id = int(active_combat.get("target_id", 0) or 0)
    actor_id = int(getattr(actor, "object_id", 0) or 0)
    if active_target_id > 0 and actor_id > 0 and active_target_id != actor_id:
        return False

    incoming_grace = max(0.0, float(getattr(args, "incoming_damage_melee_grace", 4.0) or 4.0))
    progress_grace = max(
        incoming_grace,
        max(0.0, float(getattr(args, "target_loss_grace", 0.0) or 0.0)),
        max(0.0, float(getattr(args, "target_timeout_active_combat_grace", 8.0) or 8.0)),
    )

    if recent_incoming_damage_matches_actor(
        actor,
        recent_incoming_attacker_name,
        last_damage_at=last_incoming_damage_at,
        now=now,
        grace_seconds=progress_grace,
    ):
        return True

    for key in ("last_damage_done_at", "last_combat_message_at"):
        timestamp = float(active_combat.get(key, 0.0) or 0.0)
        if timestamp > 0.0 and now - timestamp <= progress_grace:
            return True

    return False


def effective_attack_distance_for_recent_incoming_damage(
    args: argparse.Namespace,
    action_rotation: str,
    actor,
    *,
    distance: float,
    recent_incoming_attacker_name: str,
    last_incoming_damage_at: float,
    now: float,
) -> float:
    if not is_melee_rotation(action_rotation):
        return distance

    grace_seconds = float(getattr(args, "incoming_damage_melee_grace", 4.0) or 4.0)
    if not recent_incoming_damage_matches_actor(
        actor,
        recent_incoming_attacker_name,
        last_damage_at=last_incoming_damage_at,
        now=now,
        grace_seconds=grace_seconds,
    ):
        return distance

    max_melee_proof_distance = float(getattr(args, "incoming_damage_melee_max_distance", 650.0) or 650.0)
    if max_melee_proof_distance > 0.0 and distance > max_melee_proof_distance:
        return distance

    return min(distance, melee_stop_distance(args))


def attack_target_in_view_prime_delay(args: argparse.Namespace, *, recent_incoming_melee: bool) -> float:
    if recent_incoming_melee:
        return 0.0
    return max(0.0, float(getattr(args, "attack_target_in_view_prime_delay", 0.0) or 0.0))


def should_wait_for_attack_target_prime(
    *,
    primed_target: int,
    current_target: int,
    primed_at: float,
    now: float,
    prime_delay: float,
) -> bool:
    if prime_delay <= 0.0:
        return False
    if primed_target != current_target:
        return True
    return now - primed_at < prime_delay


def should_back_off_for_ranged_combat_follow(args: argparse.Namespace, action_rotation: str, leader_distance: float) -> bool:
    if action_rotation not in {"caster-basic", "healer-support"}:
        return False

    return leader_distance < combat_stop_distance(args, action_rotation) * 0.85


def should_back_off_for_ranged_combat_target(args: argparse.Namespace, action_rotation: str, target_distance: float) -> bool:
    if action_rotation not in {"caster-basic", "healer-support"}:
        return False

    safe_distance = combat_stop_distance(args, action_rotation)
    return safe_distance > 0.0 and target_distance < safe_distance * 0.85


def party_role_assist_attack_delay(args: argparse.Namespace, action_rotation: str) -> float:
    base_delay = max(0.0, float(getattr(args, "party_assist_attack_delay", 0.0) or 0.0))
    if action_rotation not in {"caster-basic", "healer-support"}:
        return base_delay

    extra_delay = max(0.0, float(getattr(args, "party_ranged_assist_extra_delay", 0.0) or 0.0))
    return base_delay + extra_delay


def boss_ranged_safe_distance(args: argparse.Namespace, action_rotation: str) -> float:
    configured = float(getattr(args, "boss_ranged_safe_distance", 0.0) or 0.0)
    return max(configured, combat_stop_distance(args, action_rotation))


def should_back_off_from_boss_target(args: argparse.Namespace, action_rotation: str, target_distance: float) -> bool:
    if not should_preserve_party_target_on_loss(args) or action_rotation not in {"caster-basic", "healer-support"}:
        return False

    safe_distance = boss_ranged_safe_distance(args, action_rotation)
    return safe_distance > 0 and target_distance < safe_distance * 0.9


def should_back_off_from_required_home_before_engage(
    args: argparse.Namespace,
    action_rotation: str,
    home_distance: float,
    *,
    current_target: int,
) -> bool:
    if current_target > 0:
        return False

    if not should_preserve_party_target_on_loss(args) or action_rotation not in {"caster-basic", "healer-support"}:
        return False

    safe_distance = float(getattr(args, "party_preengage_ranged_safe_distance", 0.0) or 0.0)
    return safe_distance > 0 and home_distance < safe_distance * 0.9


def should_follow_leader_during_required_boss(args: argparse.Namespace, action_rotation: str, leader_distance: float) -> bool:
    if not should_preserve_party_target_on_loss(args) or action_rotation.startswith("melee"):
        return False

    return leader_distance > max(args.boss_non_tank_follow_distance, combat_stop_distance(args, action_rotation))


def should_back_off_for_party_melee_survival(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    action_rotation: str,
    health_percent: int,
    now: float,
    backoff_until: float,
) -> bool:
    if not should_preserve_party_target_on_loss(args) or not is_melee_rotation(action_rotation):
        return False

    if party_member_is_active_tank(snapshot, member_name):
        return False

    if health_percent <= 0:
        return False

    threshold = int(getattr(args, "party_melee_survival_health_percent", 0) or 0)
    if threshold <= 0:
        return False

    if health_percent <= threshold:
        return True

    resume_threshold = max(threshold, int(getattr(args, "party_melee_survival_resume_health_percent", threshold) or threshold))
    return backoff_until > now and health_percent < resume_threshold


def boss_hazard_message_duration(args: argparse.Namespace, text: str) -> float:
    duration = float(getattr(args, "boss_hazard_message_backoff_duration", 0.0) or 0.0)

    if duration <= 0:
        return 0.0

    lowered = str(text or "").lower()
    hazard_tokens = (
        "prepares a massive attack",
        "powerful breath",
        "rush of air",
        "inhales deeply",
        "looks mindfully around",
        "begins flapping",
        "강력한 공격",
        "숨을 들이",
        "주의 깊게 주변",
        "날개를 퍼덕",
        "치명적인 공격",
        "공기의 흐름",
    )

    return duration if any(token in lowered for token in hazard_tokens) else 0.0


def should_back_off_for_boss_hazard(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    action_rotation: str,
    *,
    now: float,
    hazard_until: float,
) -> bool:
    if not should_preserve_party_target_on_loss(args):
        return False

    if hazard_until <= now:
        return False

    if action_rotation == "healer-support":
        return True

    return not party_member_is_active_tank(snapshot, member_name)


def boss_hazard_backoff_distance(args: argparse.Namespace, action_rotation: str) -> float:
    configured = float(getattr(args, "boss_hazard_message_backoff_distance", 0.0) or 0.0)

    if configured > 0:
        return configured

    return max(boss_ranged_safe_distance(args, action_rotation), party_melee_survival_distance(args))


def should_refresh_party_melee_survival_backoff(args: argparse.Namespace, health_percent: int) -> bool:
    threshold = int(getattr(args, "party_melee_survival_health_percent", 0) or 0)
    return threshold > 0 and 0 < health_percent <= threshold


def party_melee_survival_distance(args: argparse.Namespace) -> float:
    configured_distance = float(getattr(args, "party_melee_survival_distance", 0.0) or 0.0)
    if configured_distance > 0:
        return configured_distance

    return max(args.attack_range * 1.75, combat_stop_distance(args, "healer-support") * 0.75)


def party_boss_melee_backoff_distance(args: argparse.Namespace) -> float:
    configured_distance = float(getattr(args, "party_boss_non_tank_melee_backoff_distance", 0.0) or 0.0)
    if configured_distance > 0:
        return configured_distance

    return max(args.attack_range * 2.5, combat_stop_distance(args, "healer-support"))


def should_back_off_for_party_boss_melee_limit(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    action_rotation: str,
    current_target: int,
) -> bool:
    if not bool(getattr(args, "party_boss_non_tank_melee_backoff", False)):
        return False

    if not should_preserve_party_target_on_loss(args) or not is_melee_rotation(action_rotation):
        return False

    if party_member_is_active_tank(snapshot, member_name):
        return False

    leader_target_id = int(snapshot.get("leader_target_id", 0) or 0)
    return bool(leader_target_id > 0 and current_target == leader_target_id)


def should_back_off_for_party_focus_target(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    *,
    now: float,
) -> bool:
    if not bool(getattr(args, "party_focus_target_backoff", False)):
        return False

    if not should_preserve_party_target_on_loss(args):
        return False

    if party_member_is_active_tank(snapshot, member_name):
        return False

    focus_name = normalize_target_name(str(snapshot.get("leader_target_focus_name", "") or ""))
    if not focus_name or normalize_target_name(member_name) != focus_name:
        return False

    focus_updated_at = float(snapshot.get("leader_target_focus_updated_at", 0.0) or 0.0)
    max_age = max(0.0, float(getattr(args, "party_focus_target_max_age", 0.0) or 0.0))
    if focus_updated_at <= 0.0:
        return False

    return max_age <= 0.0 or now - focus_updated_at <= max_age


def party_focus_is_recent(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    *,
    now: float,
) -> bool:
    focus_name = normalize_target_name(str(snapshot.get("leader_target_focus_name", "") or ""))
    if not focus_name:
        return False

    focus_updated_at = float(snapshot.get("leader_target_focus_updated_at", 0.0) or 0.0)
    max_age = max(0.0, float(getattr(args, "party_focus_target_max_age", 0.0) or 0.0))
    if focus_updated_at <= 0.0:
        return False

    return max_age <= 0.0 or now - focus_updated_at <= max_age


def should_offtank_reaggro_shared_objective(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    action_rotation: str,
    *,
    now: float,
) -> bool:
    if not bool(getattr(args, "party_focus_pressure_offtank_reaggro", False)):
        return False

    if not should_preserve_party_target_on_loss(args) or action_rotation != "melee-basic":
        return False

    if party_member_is_active_tank(snapshot, member_name):
        return False

    focus_name = normalize_target_name(str(snapshot.get("leader_target_focus_name", "") or ""))
    active_tank_name = normalize_target_name(str(snapshot.get("active_tank_name", "") or ""))
    if not focus_name or focus_name == active_tank_name:
        return False

    return party_focus_is_recent(args, snapshot, now=now)


def party_required_target_low_health_burn(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
) -> bool:
    threshold = float(getattr(args, "party_burn_required_target_health_percent", 0.0) or 0.0)
    if threshold <= 0.0:
        return False

    if not should_preserve_party_target_on_loss(args):
        return False

    if int(snapshot.get("leader_target_id", 0) or 0) <= 0:
        return False

    health_percent = float(snapshot.get("leader_target_health_percent", 0.0) or 0.0)
    return 0.0 < health_percent <= threshold


def should_back_off_for_party_focus_pressure(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    action_rotation: str,
    *,
    now: float,
) -> bool:
    if not bool(getattr(args, "party_focus_pressure_melee_backoff", False)):
        return False

    if not should_preserve_party_target_on_loss(args) or not is_melee_rotation(action_rotation):
        return False

    if party_member_is_active_tank(snapshot, member_name):
        return False

    if should_offtank_reaggro_shared_objective(args, snapshot, member_name, action_rotation, now=now):
        return False

    focus_name = normalize_target_name(str(snapshot.get("leader_target_focus_name", "") or ""))
    if not focus_name or normalize_target_name(member_name) == focus_name:
        return False

    active_tank_name = normalize_target_name(str(snapshot.get("active_tank_name", "") or ""))
    if focus_name == active_tank_name:
        return False

    if party_required_target_low_health_burn(args, snapshot):
        return False

    return party_focus_is_recent(args, snapshot, now=now)


def should_active_tank_reaggro_taunt(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    action_rotation: str,
    *,
    now: float,
    next_taunt: float,
) -> bool:
    if not should_preserve_party_target_on_loss(args) or not is_melee_rotation(action_rotation):
        return False

    if not party_member_is_active_tank(snapshot, member_name):
        if not should_offtank_reaggro_shared_objective(args, snapshot, member_name, action_rotation, now=now):
            return False

    interval = float(getattr(args, "party_active_tank_reaggro_taunt_interval", 0.0) or 0.0)
    if interval <= 0 or now < next_taunt:
        return False

    focus_name = normalize_target_name(str(snapshot.get("leader_target_focus_name", "") or ""))
    active_tank_name = normalize_target_name(str(snapshot.get("active_tank_name", "") or ""))
    if not focus_name or focus_name == active_tank_name:
        return False

    return party_focus_is_recent(args, snapshot, now=now)


def party_focus_target_backoff_distance(args: argparse.Namespace, action_rotation: str) -> float:
    configured_distance = float(getattr(args, "party_focus_target_backoff_distance", 0.0) or 0.0)
    if configured_distance > 0:
        return configured_distance

    return max(
        party_encounter_survival_distance(args),
        boss_ranged_safe_distance(args, action_rotation),
    )


def party_smooth_tactical_backoff_reason_and_distance(
    args: argparse.Namespace,
    action_rotation: str,
    *,
    party_melee_survival_backoff: bool,
    boss_hazard_backoff: bool,
    party_focus_target_backoff: bool,
    party_focus_pressure_backoff: bool,
    party_boss_melee_backoff: bool,
    party_survival_backoff: bool,
    ranged_safety_backoff_due: bool,
    ranged_target_backoff_due: bool = False,
) -> tuple[str, float]:
    if boss_hazard_backoff:
        return "boss_hazard", boss_hazard_backoff_distance(args, action_rotation)

    if party_focus_target_backoff:
        return "party_focus_target", party_focus_target_backoff_distance(args, action_rotation)

    if party_focus_pressure_backoff:
        return "party_focus_pressure", party_focus_target_backoff_distance(args, action_rotation)

    if ranged_safety_backoff_due:
        return "boss_ranged", boss_ranged_safe_distance(args, action_rotation)

    if ranged_target_backoff_due:
        return "ranged_target", combat_stop_distance(args, action_rotation)

    if party_boss_melee_backoff:
        return "party_boss_melee", party_boss_melee_backoff_distance(args)

    if party_survival_backoff:
        return "party_survival", party_encounter_survival_distance(args)

    if party_melee_survival_backoff:
        return "party_melee_survival", party_melee_survival_distance(args)

    return "", 0.0


def party_encounter_survival_pressure(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    *,
    now: float,
) -> bool:
    if not should_preserve_party_target_on_loss(args):
        return False

    encounter_active = (
        int(snapshot.get("leader_target_id", 0) or 0) > 0
        or float(snapshot.get("encounter_started_at", 0.0) or 0.0) > 0.0
    )
    if not encounter_active:
        return False

    active_tank_threshold = int(getattr(args, "party_survival_active_tank_health_percent", 0) or 0)
    active_tank_health = int(snapshot.get("active_tank_health_percent", 100) or 0)
    if active_tank_threshold > 0 and 0 < active_tank_health <= active_tank_threshold:
        return True

    if party_required_target_low_health_burn(args, snapshot):
        return False

    death_count_threshold = int(getattr(args, "party_survival_death_count", 0) or 0)
    if death_count_threshold <= 0:
        return False

    death_count = int(snapshot.get("encounter_death_count", 0) or 0)
    last_death_at = float(snapshot.get("last_encounter_death_at", 0.0) or 0.0)
    death_window = max(0.0, float(getattr(args, "party_survival_death_window", 0.0) or 0.0))
    if death_count < death_count_threshold or last_death_at <= 0.0:
        return False

    return death_window <= 0.0 or now - last_death_at <= death_window


def should_back_off_for_party_encounter_survival(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    action_rotation: str,
    *,
    now: float,
) -> bool:
    if not is_melee_rotation(action_rotation):
        return False

    if party_member_is_active_tank(snapshot, member_name):
        return False

    return party_encounter_survival_pressure(args, snapshot, now=now)


def party_encounter_survival_distance(args: argparse.Namespace) -> float:
    configured_distance = float(getattr(args, "party_survival_backoff_distance", 0.0) or 0.0)
    if configured_distance > 0:
        return configured_distance

    return max(party_boss_melee_backoff_distance(args), party_melee_survival_distance(args))


def should_preserve_party_target_on_loss(args: argparse.Namespace) -> bool:
    return bool(
        getattr(args, "party_assist_only", False)
        and (getattr(args, "require_target_name", "") or getattr(args, "party_encounter_mode", "standard") != "standard")
    )


def plan_friendly_cast_target_hold(args: argparse.Namespace, now: float, current_target: int) -> tuple[float, int]:
    hold_seconds = max(0.0, float(getattr(args, "party_friendly_cast_target_hold", 0.0)))

    if hold_seconds <= 0:
        return 0.0, 0

    return now + hold_seconds, max(0, int(current_target or 0))


def should_hold_friendly_cast_target(
    *,
    friendly_cast_hold_until: float,
    now: float,
    tactical_backoff: bool,
) -> bool:
    return bool(friendly_cast_hold_until > now and not tactical_backoff)


def friendly_cast_hold_breaking_backoff(
    *,
    party_melee_survival_backoff: bool,
    boss_hazard_backoff: bool,
    party_survival_backoff: bool,
    party_focus_target_backoff: bool,
    party_focus_pressure_backoff: bool,
    ranged_safety_backoff_due: bool,
) -> bool:
    del ranged_safety_backoff_due
    return bool(
        party_melee_survival_backoff
        or boss_hazard_backoff
        or party_survival_backoff
        or party_focus_target_backoff
        or party_focus_pressure_backoff
    )


def should_chase_last_known_shared_target(
    snapshot: dict[str, int | float | str],
    *,
    current_target: int,
    tactical_backoff: bool,
) -> bool:
    if tactical_backoff:
        return False

    return int(snapshot.get("leader_target_id", 0) or 0) == current_target


def should_use_shared_target_backoff_point(
    snapshot: dict[str, int | float | str],
    current_target: int,
) -> bool:
    leader_target_id = int(snapshot.get("leader_target_id", 0) or 0)
    return bool(leader_target_id > 0 and (current_target <= 0 or current_target == leader_target_id))


def choose_party_heal_target(
    party_state: PartyState,
    args: argparse.Namespace,
    *,
    exclude_name: str = "",
) -> dict[str, int | str] | None:
    max_health_percent = int(getattr(args, "party_heal_leader_health_percent", 0) or 0)
    snapshot = party_state.snapshot()
    active_tank_name = str(snapshot.get("active_tank_name", "") or "")
    active_tank_object_id = int(snapshot.get("active_tank_object_id", 0) or 0)
    active_tank_health = int(snapshot.get("active_tank_health_percent", 100) or 0)

    if (
        active_tank_name
        and active_tank_name != exclude_name
        and active_tank_object_id > 0
        and 0 < active_tank_health <= max_health_percent
    ):
        return {
            "name": active_tank_name,
            "object_id": active_tank_object_id,
            "health_percent": active_tank_health,
            "x": int(snapshot.get("active_tank_x", 0) or 0),
            "y": int(snapshot.get("active_tank_y", 0) or 0),
            "z": int(snapshot.get("active_tank_z", 0) or 0),
        }

    self_heal_threshold = int(getattr(args, "healer_self_health_percent", 0) or 0)
    if exclude_name and self_heal_threshold > 0:
        self_object_id = party_state.member_object_ids.get(exclude_name, 0)
        self_health = party_state.member_health_percents.get(exclude_name, 100)
        if self_object_id and 0 < self_health <= self_heal_threshold:
            self_x, self_y, self_z = party_state.member_positions.get(exclude_name, (0, 0, 0))
            return {
                "name": exclude_name,
                "object_id": self_object_id,
                "health_percent": self_health,
                "x": self_x,
                "y": self_y,
                "z": self_z,
            }

    return party_state.focused_hurt_member(
        max_health_percent,
        exclude_name=exclude_name,
    ) or party_state.lowest_hurt_member(
        max_health_percent,
        exclude_name=exclude_name,
    )


def party_heal_target_in_cast_range(client, args: argparse.Namespace, hurt_member: dict[str, int | str] | None) -> bool:
    if hurt_member is None:
        return False

    target_x = int(hurt_member.get("x", 0) or 0)
    target_y = int(hurt_member.get("y", 0) or 0)
    if target_x == 0 and target_y == 0:
        return True

    spell_range = float(getattr(args, "spell_range", 1500.0) or 1500.0)
    buffer = max(0.0, float(getattr(args, "party_heal_cast_range_buffer", 200.0) or 0.0))
    safe_spell_range = max(0.0, spell_range - buffer)
    return horizontal_distance_between_points(int(client.x), int(client.y), target_x, target_y) <= safe_spell_range


def party_heal_target_approach_stop_distance(args: argparse.Namespace) -> float:
    spell_range = float(getattr(args, "spell_range", 1500.0) or 1500.0)
    buffer = max(0.0, float(getattr(args, "party_heal_cast_range_buffer", 200.0) or 0.0))
    return max(0.0, spell_range - buffer)


def party_heal_target_destination(hurt_member: dict[str, int | str] | None) -> MovementDestination | None:
    if hurt_member is None:
        return None

    target_x = int(hurt_member.get("x", 0) or 0)
    target_y = int(hurt_member.get("y", 0) or 0)
    target_z = int(hurt_member.get("z", 0) or 0)
    if target_x == 0 and target_y == 0:
        return None

    return destination_from_point("party-heal-target", target_x, target_y, target_z)


def should_approach_party_heal_target(
    args: argparse.Namespace,
    *,
    action_rotation: str,
    hurt_member: dict[str, int | str] | None,
    current_target: int,
    behavior_state: DummyBehaviorState | str,
) -> bool:
    del args
    if action_rotation != "healer-support" or hurt_member is None:
        return False

    if current_target > 0:
        return False

    state = behavior_state_value(behavior_state)
    if state in {
        DummyBehaviorState.DropAggroAndRecover.value,
        DummyBehaviorState.DeadReleaseRecover.value,
    }:
        return False

    return party_heal_target_destination(hurt_member) is not None


def move_towards_party_heal_target(
    client,
    args: argparse.Namespace,
    path_state: PathMovementState,
    action_counts: dict[str, int],
    hurt_member: dict[str, int | str] | None,
) -> MovementOutcome | None:
    del path_state, action_counts
    destination = party_heal_target_destination(hurt_member)
    if destination is None:
        return None

    set_attack_mode = getattr(client, "set_attack_mode", None)
    if callable(set_attack_mode):
        set_attack_mode(False)

    moved = client.move_towards_position(
        destination.x,
        destination.y,
        destination.z,
        step=float(getattr(args, "party_follow_step", 320.0) or 320.0),
        stop_distance=party_heal_target_approach_stop_distance(args),
        movement_speed=getattr(args, "movement_speed", None),
        min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
        target_in_view=False,
    )
    return MovementOutcome(moved=moved, arrived=not moved)


def should_send_target_start_commands(
    args: argparse.Namespace,
    current_target: int,
    sent_target_start_command_targets: set[int],
) -> bool:
    return bool(getattr(args, "target_start_command", []) and current_target > 0 and current_target not in sent_target_start_command_targets)


def should_party_member_assist_rescue_target(
    args: argparse.Namespace,
    action_rotation: str,
    rescue_age: float = 0.0,
    objective_add: bool = True,
    victim_role: str = "",
) -> bool:
    if action_rotation == "healer-support":
        return False

    if action_rotation == "caster-basic" and not getattr(args, "party_caster_assist_rescue_target", False):
        return False

    if should_assist_dangerous_support_rescue_threat(args, action_rotation, rescue_age, victim_role):
        return True

    if not objective_add:
        return False

    if getattr(args, "party_assist_rescue_target", False):
        return True

    assist_after = max(0.0, float(getattr(args, "party_rescue_assist_after", 0.0) or 0.0))
    return assist_after > 0.0 and rescue_age >= assist_after


def should_prefer_taunt_skill_for_target(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    *,
    member_name: str,
    action_rotation: str,
    selected_npc_is_rescue: bool,
    selected_npc_is_required: bool,
    reaggro_taunt_due: bool,
) -> bool:
    if reaggro_taunt_due:
        return True

    if action_rotation not in {"melee-basic", "melee-burst", "hybrid"}:
        return False

    if selected_npc_is_rescue:
        return bool(
            getattr(args, "party_rescue_aggro", False)
            and (
                party_member_is_rescue_tank(snapshot, member_name)
                or (
                    is_party_tank_role(action_rotation)
                    and not should_party_member_hold_shared_objective(args, snapshot, member_name)
                )
                or should_party_member_assist_rescue_target(
                    args,
                    action_rotation,
                    rescue_age=float("inf"),
                    objective_add=True,
                )
            )
        )

    return bool(
        selected_npc_is_required
        and party_member_is_active_tank(snapshot, member_name)
    )



def should_reject_selected_target_for_required_filter(args: argparse.Namespace, npc, selected_npc_is_rescue: bool) -> bool:
    return npc is not None and not selected_npc_is_rescue and not passes_required_target_filter(args, npc)


def should_send_target_start_command_for_npc(args: argparse.Namespace, npc, selected_npc_is_rescue: bool) -> bool:
    return not selected_npc_is_rescue and passes_required_target_filter(args, npc)


def should_send_position_heartbeat_for_client(client) -> bool:
    return not bool(getattr(client, "is_dead", False))


def should_treat_disconnect_as_completed(exc: BaseException, client, death_seen: bool) -> bool:
    if not (death_seen or bool(getattr(client, "is_dead", False))):
        return False

    if isinstance(exc, (BrokenPipeError, ConnectionResetError, ConnectionAbortedError)):
        return True

    return isinstance(exc, OSError) and getattr(exc, "errno", None) in {
        errno.EPIPE,
        errno.ECONNRESET,
        errno.ECONNABORTED,
    }


def party_anchor_from_snapshot(snapshot: dict[str, int | float | str]) -> dict[str, int | str]:
    active_tank_id = int(snapshot.get("active_tank_object_id", 0) or 0)
    active_tank_x = int(snapshot.get("active_tank_x", 0) or 0)
    active_tank_y = int(snapshot.get("active_tank_y", 0) or 0)
    active_tank_z = int(snapshot.get("active_tank_z", 0) or 0)

    if active_tank_id and (active_tank_x != 0 or active_tank_y != 0):
        return {
            "name": str(snapshot.get("active_tank_name", "")),
            "object_id": active_tank_id,
            "x": active_tank_x,
            "y": active_tank_y,
            "z": active_tank_z,
        }

    return {
        "name": str(snapshot.get("leader_name", "")),
        "object_id": int(snapshot.get("leader_object_id", 0) or 0),
        "x": int(snapshot.get("leader_x", 0) or 0),
        "y": int(snapshot.get("leader_y", 0) or 0),
        "z": int(snapshot.get("leader_z", 0) or 0),
    }


def party_anchor_position_valid(snapshot: dict[str, int | float | str]) -> bool:
    if int(snapshot.get("active_tank_object_id", 0) or 0) > 0 and (
        int(snapshot.get("active_tank_x", 0) or 0) != 0
        or int(snapshot.get("active_tank_y", 0) or 0) != 0
    ):
        return True

    return bool(
        int(snapshot.get("leader_object_id", 0) or 0) > 0
        and (
            int(snapshot.get("leader_x", 0) or 0) != 0
            or int(snapshot.get("leader_y", 0) or 0) != 0
        )
    )


def party_member_is_active_tank(snapshot: dict[str, int | float | str], member_name: str) -> bool:
    return bool(member_name and str(snapshot.get("active_tank_name", "")) == member_name)


def party_member_is_rescue_tank(snapshot: dict[str, int | float | str], member_name: str) -> bool:
    return bool(member_name and str(snapshot.get("rescue_tank_name", "")) == member_name)


def is_party_tank_role(action_rotation: str) -> bool:
    return action_rotation in {"melee-basic", "melee-burst", "hybrid"}


def should_party_member_tank_rescue_target(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
) -> bool:
    if not party_member_is_rescue_tank(snapshot, member_name):
        return False

    if (
        should_preserve_party_target_on_loss(args)
        and int(snapshot.get("leader_target_id", 0) or 0) > 0
        and str(snapshot.get("active_tank_name", "")) == member_name
    ):
        return False

    return True


def should_party_member_hold_shared_objective(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
) -> bool:
    return bool(
        should_preserve_party_target_on_loss(args)
        and int(snapshot.get("leader_target_id", 0) or 0) > 0
        and party_member_is_active_tank(snapshot, member_name)
    )


def should_party_member_handle_rescue_target(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    action_rotation: str,
    health_percent: int,
    *,
    rescue_age: float,
) -> bool:
    if should_party_member_hold_shared_objective(args, snapshot, member_name):
        return False

    objective_add = bool(snapshot.get("rescue_target_objective_add", True))
    return bool(
        should_party_member_tank_rescue_target(args, snapshot, member_name)
        or should_party_member_assist_rescue_target(
            args,
            action_rotation,
            rescue_age=rescue_age,
            objective_add=objective_add,
            victim_role=party_member_role(snapshot, str(snapshot.get("rescue_member_name", "") or "")),
        )
        or (
            (not objective_add or not should_preserve_party_target_on_loss(args))
            and should_party_member_use_local_rescue_target(args, action_rotation, health_percent)
        )
    )


def choose_incoming_damage_counterattack_target(
    npcs,
    client,
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str] | None,
    *,
    member_name: str,
    action_rotation: str,
    health_percent: int,
    attacker_name: str,
    current_target: int,
    behavior_state: DummyBehaviorState | str,
    rejected_targets: dict[int, float] | None = None,
    now: float = 0.0,
):
    if current_target > 0 or party_snapshot is None or not attacker_name:
        return None

    if not getattr(args, "party_rescue_aggro", False):
        return None

    if not party_member_is_active_tank(party_snapshot, member_name):
        return None

    if not is_melee_rotation(action_rotation):
        return None

    health_floor = int(getattr(args, "flee_melee_counterattack_health_floor", 0) or 0)
    if health_floor > 0 and health_percent <= health_floor:
        return None

    leader_target_id = int(party_snapshot.get("leader_target_id", 0) or 0)
    attacker = choose_named_rescue_attacker(
        npcs,
        client,
        args,
        leader_target_id,
        attacker_name,
    )
    if attacker is None:
        return None

    if rejected_targets is not None and rejected_targets.get(attacker.object_id, 0.0) > now:
        return None

    if not (is_required_target(args, attacker) or is_objective_add_target(args, attacker)):
        return None

    if not target_within_required_home(args, attacker):
        return None

    if not target_within_selection_distance(client, args, attacker):
        return None

    if target_home_leash_violation(client, args, attacker)[0]:
        return None

    attacker_intent = target_intent_for_selected_npc(
        args,
        attacker,
        selected_npc_is_rescue=True,
        behavior_state=behavior_state,
        recent_incoming_attacker_name=attacker_name,
    )
    if not should_allow_counterattack_for_behavior_state(
        behavior_state,
        args,
        attacker,
        attacker_intent,
    ):
        return None

    return attacker


def should_share_selected_target(
    args: argparse.Namespace,
    selected_npc_is_rescue: bool,
    *,
    is_party_leader: bool = True,
    party_snapshot: dict[str, int | float | str] | None = None,
) -> bool:
    if not should_preserve_party_target_on_loss(args) or selected_npc_is_rescue:
        return False

    if not is_party_leader and getattr(args, "party_require_leader_engaged", False):
        snapshot = party_snapshot or {}
        if float(snapshot.get("leader_target_engaged_at", 0.0) or 0.0) <= 0.0:
            return False

    return True


def should_update_party_objective_target(selected_npc_is_rescue: bool) -> bool:
    return not selected_npc_is_rescue


def should_clear_leader_target_after_required_filter(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str],
    rejected_target_id: int,
) -> bool:
    if not should_preserve_party_target_on_loss(args):
        return True

    leader_target_id = int(party_snapshot.get("leader_target_id", 0) or 0)
    return bool(leader_target_id and leader_target_id == int(rejected_target_id or 0))


def should_scan_peace_npcs(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "include_peace_npcs", False) or should_preserve_party_target_on_loss(args))


def should_preserve_current_party_target(
    args: argparse.Namespace,
    party_state: PartyState | None,
    current_target: int,
    active_combat: dict[str, float | int | str] | None,
) -> bool:
    if not should_preserve_party_target_on_loss(args) or current_target <= 0:
        return False

    if active_combat_matches_required_target(args, active_combat):
        return True

    if active_combat is not None:
        return False

    if party_state is None:
        return False

    snapshot = party_state.snapshot()
    if int(snapshot["rescue_target_id"]) == current_target:
        return False

    return int(snapshot["leader_target_id"]) == current_target


def target_removed_preserve_allowed(
    args: argparse.Namespace,
    now: float,
    last_visible_at: float,
    preserve_count: int,
) -> bool:
    grace = max(0.0, float(getattr(args, "party_target_loss_grace", 0.0)))
    if grace > 0 and last_visible_at > 0 and now - last_visible_at > grace:
        return False

    limit = max(0, int(getattr(args, "party_target_removed_preserve_limit", 0)))
    if limit > 0 and preserve_count >= limit:
        return False

    return True


def should_preserve_removed_party_target(
    args: argparse.Namespace,
    party_state: PartyState | None,
    current_target: int,
    active_combat: dict[str, float | int | str] | None,
    stop_after_removed: bool,
    now: float,
    last_visible_at: float,
    preserve_count: int,
) -> bool:
    if stop_after_removed:
        return False

    return (
        should_preserve_current_party_target(args, party_state, current_target, active_combat)
        and target_removed_preserve_allowed(args, now, last_visible_at, preserve_count)
    )


def should_preserve_unshared_party_target(
    args: argparse.Namespace,
    current_target: int,
    active_combat: dict[str, float | int | str] | None,
) -> bool:
    return (
        should_preserve_party_target_on_loss(args)
        and current_target > 0
        and active_combat_matches_required_target(args, active_combat)
    )


def active_combat_matches_required_target(args: argparse.Namespace, active_combat: dict[str, float | int | str] | None) -> bool:
    if active_combat is None:
        return False

    target_name = str(active_combat.get("target_name", "")).lower()
    tokens = required_target_tokens(args)
    if tokens:
        return bool(target_name and any(required_target_name_matches(target_name, token) for token in tokens))

    if getattr(args, "party_encounter_mode", "standard") != "standard":
        return int(active_combat.get("target_id", 0) or 0) > 0

    return False


def name_matches_required_target(args: argparse.Namespace, target_name: str) -> bool:
    normalized_name = normalize_target_name(target_name)
    tokens = required_target_tokens(args)
    return bool(normalized_name and tokens and any(required_target_name_matches(normalized_name, token) for token in tokens))


def should_allow_party_rescue_before_objective_engaged(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str],
    active_combat: dict[str, float | int | str] | None,
    now: float | None = None,
    *,
    urgent: bool = False,
) -> bool:
    if getattr(args, "party_rescue_before_objective_engaged", False):
        return True

    if urgent:
        return True

    if active_combat_matches_required_target(args, active_combat):
        return True

    rescue_target_id = int(party_snapshot.get("rescue_target_id", 0) or 0)
    if rescue_target_id > 0:
        rescue_age = party_rescue_target_age(
            party_snapshot,
            rescue_target_id,
            time.monotonic() if now is None else now,
        )
        max_age = max(0.0, float(getattr(args, "party_rescue_max_age", 0.0) or 0.0))
        if rescue_age >= 0.0 and (max_age <= 0.0 or rescue_age <= max_age):
            return True

    if not should_preserve_party_target_on_loss(args) or not required_target_tokens(args):
        return True

    engaged_at = float(party_snapshot.get("leader_target_engaged_at", 0.0) or 0.0)
    if engaged_at <= 0.0:
        return False

    grace = max(0.0, float(getattr(args, "party_rescue_objective_engaged_grace", 0.0) or 0.0))
    if grace > 0.0:
        current_time = time.monotonic() if now is None else now
        if current_time - engaged_at < grace:
            return False

    return True


def should_stop_after_required_target_removed(
    args: argparse.Namespace,
    active_combat: dict[str, float | int | str] | None,
    removed_object_id: int = 0,
) -> bool:
    if removed_object_id > 0 and active_combat is not None:
        active_target_id = int(active_combat.get("target_id", 0) or 0)
        if active_target_id > 0 and active_target_id != removed_object_id:
            return False

    return bool(
        getattr(args, "stop_after_required_target_removed", False)
        and active_combat_matches_required_target(args, active_combat)
    )


def required_target_removed_api_confirms_completion(
    args: argparse.Namespace,
    active_combat: dict[str, float | int | str] | None,
    observation: RequiredTargetObservation | None,
    removed_object_id: int = 0,
) -> bool:
    if not getattr(args, "required_target_api", False):
        return True

    if active_combat is None or observation is None or observation.object_id <= 0:
        return False

    active_target_id = int(active_combat.get("target_id", 0) or 0)
    if removed_object_id > 0 and active_target_id > 0 and removed_object_id != active_target_id:
        return False

    active_target_name = str(active_combat.get("target_name", "") or "")
    if (
        active_target_id > 0
        and observation.object_id != active_target_id
        and active_target_name
        and not required_target_name_matches(observation.name, active_target_name)
    ):
        return False

    if observation.is_alive is False:
        return True

    if observation.max_health > 0 and observation.health <= 0:
        return True

    return False


def smooth_movement_step(args: argparse.Namespace) -> float:
    return max(1.0, args.movement_speed * args.smooth_move_interval)


def combat_chase_movement_speed(args: argparse.Namespace, action_rotation: str, distance: float) -> float:
    base_speed = float(getattr(args, "movement_speed", 0.0) or 0.0)
    if is_melee_rotation(action_rotation) and distance > float(getattr(args, "attack_range", 0.0) or 0.0):
        return max(base_speed, 600.0)
    return base_speed


def combat_chase_step(args: argparse.Namespace, action_rotation: str, distance: float, base_step: float) -> float:
    speed = combat_chase_movement_speed(args, action_rotation, distance)
    return max(base_step, speed * float(getattr(args, "smooth_move_interval", 0.0) or 0.0))


def active_tank_reaggro_chase_step(
    args: argparse.Namespace,
    snapshot: dict[str, int | float | str],
    member_name: str,
    action_rotation: str,
    target_npc,
    *,
    distance: float,
    base_step: float,
    now: float,
) -> float:
    if not party_member_is_active_tank(snapshot, member_name) or not is_melee_rotation(action_rotation):
        return base_step

    if not is_required_target(args, target_npc):
        return base_step

    focus_name = normalize_target_name(str(snapshot.get("leader_target_focus_name", "") or ""))
    active_tank_name = normalize_target_name(str(snapshot.get("active_tank_name", "") or ""))
    if not focus_name or focus_name == active_tank_name:
        return base_step

    max_age = float(getattr(args, "party_focus_target_max_age", 0.0) or 0.0)
    updated_at = float(snapshot.get("leader_target_focus_updated_at", 0.0) or 0.0)
    if max_age > 0.0 and updated_at > 0.0 and now - updated_at > max_age:
        return base_step

    if distance <= float(getattr(args, "attack_range", 0.0) or 0.0):
        return base_step

    return max(base_step, min(distance, base_step * 4.0))


def waypoint_distance_from_client(client, waypoint: Waypoint) -> float:
    return path_distance(PathPoint(int(client.x), int(client.y), int(client.z)), PathPoint(waypoint.x, waypoint.y, waypoint.z))


def advance_continuous_waypoint_index(client, args: argparse.Namespace, waypoint_index: int) -> int:
    if not getattr(args, "waypoint_continuous_turns", False) or not args.waypoints:
        return waypoint_index

    configured_distance = getattr(args, "waypoint_advance_distance", 0.0)
    advance_distance = configured_distance if configured_distance > 0 else args.waypoint_stop_distance
    max_advances = len(args.waypoints)

    for _ in range(max_advances):
        waypoint = args.waypoints[waypoint_index]

        if waypoint_distance_from_client(client, waypoint) > advance_distance:
            break

        if args.waypoint_mode == "random":
            waypoint_index = random.randrange(0, len(args.waypoints))
        else:
            waypoint_index = (waypoint_index + 1) % len(args.waypoints)

    return waypoint_index


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


def parse_optional_int_list(value: str) -> list[int]:
    if not value.strip():
        return []

    return parse_int_list(value)


def flatten_int_groups(groups: list[list[int]] | None) -> list[int]:
    return [value for group in (groups or []) for value in group]


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


def parse_waypoint(value: str) -> Waypoint:
    waypoints = parse_waypoints(value)

    if len(waypoints) != 1:
        raise ValueError(f"invalid point '{value}', expected one x,y,z coordinate")

    return waypoints[0]


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


def load_ground_z_sampler(value: str, z_offset: int = 0):
    if not value:
        return None

    map_path = resolve_path_graph_path(value)
    base_cache_key = str(map_path.resolve()) if map_path.exists() else str(map_path)
    cache_key = f"{base_cache_key}|z_offset={z_offset}"

    with GROUND_Z_MAP_CACHE_LOCK:
        if cache_key in GROUND_Z_MAP_CACHE:
            return GROUND_Z_MAP_CACHE[cache_key]

        payload = json.loads(map_path.read_text(encoding="utf-8"))
        if str(payload.get("type", "")).lower() == "daoc-client-zone-mpk":
            sampler = daoc_zone_heightmap.ClientZoneHeightSampler.from_config(map_path)
            base_sample = sampler.sample

            def sample_with_offset(x: int, y: int, zone_id: int) -> int | None:
                sampled = base_sample(x, y, zone_id)
                return None if sampled is None else sampled + z_offset

            GROUND_Z_MAP_CACHE[cache_key] = sample_with_offset
            return sample_with_offset

        max_distance = float(payload.get("max_distance", 600.0))
        method = str(payload.get("method", "nearest")).lower()
        sample_count = max(1, int(payload.get("sample_count", 4)))
        points = [
            (int(point["x"]), int(point["y"]), int(point["z"]))
            for point in payload.get("points", [])
            if all(key in point for key in ("x", "y", "z"))
        ]

        def sample(x: int, y: int, zone_id: int) -> int | None:
            if not points:
                return None

            nearest_points = sorted(points, key=lambda point: (point[0] - x) ** 2 + (point[1] - y) ** 2)[:sample_count]
            nearest = nearest_points[0]
            distance = ((nearest[0] - x) ** 2 + (nearest[1] - y) ** 2) ** 0.5

            if distance > max_distance:
                return None

            if method == "idw":
                weighted_z = 0.0
                total_weight = 0.0

                for point_x, point_y, point_z in nearest_points:
                    point_distance = max(1.0, ((point_x - x) ** 2 + (point_y - y) ** 2) ** 0.5)
                    weight = 1.0 / (point_distance * point_distance)
                    weighted_z += point_z * weight
                    total_weight += weight

                if total_weight > 0:
                    return int(round(weighted_z / total_weight))

            return nearest[2]

        if z_offset:
            base_sample = sample

            def sample_with_offset(x: int, y: int, zone_id: int) -> int | None:
                sampled = base_sample(x, y, zone_id)
                return None if sampled is None else sampled + z_offset

            GROUND_Z_MAP_CACHE[cache_key] = sample_with_offset
            return sample_with_offset

        GROUND_Z_MAP_CACHE[cache_key] = sample
        return sample


def load_client_grid_nav(args: argparse.Namespace):
    value = getattr(args, "client_grid_nav_map", "")

    if not value:
        return None

    map_path = resolve_path_graph_path(value)
    base_cache_key = str(map_path.resolve()) if map_path.exists() else str(map_path)
    cache_key = "|".join(
        [
            base_cache_key,
            f"cell={getattr(args, 'client_grid_nav_cell_size', 256)}",
            f"max_step_z={getattr(args, 'client_grid_nav_max_step_z', 240)}",
            f"water={getattr(args, 'client_grid_nav_allow_water', False)}",
            f"fixture={getattr(args, 'client_grid_nav_fixture_padding', 160)}",
            f"visited={getattr(args, 'client_grid_nav_max_visited', 20000)}",
        ]
    )

    with CLIENT_GRID_NAV_CACHE_LOCK:
        if cache_key not in CLIENT_GRID_NAV_CACHE:
            CLIENT_GRID_NAV_CACHE[cache_key] = daoc_lightweight_navgrid.ClientNavGridPathfinder(
                map_path,
                cell_size=getattr(args, "client_grid_nav_cell_size", 256),
                max_step_z=getattr(args, "client_grid_nav_max_step_z", 240),
                allow_water=getattr(args, "client_grid_nav_allow_water", False),
                fixture_padding=getattr(args, "client_grid_nav_fixture_padding", 160),
                max_visited=getattr(args, "client_grid_nav_max_visited", 20000),
            )

        return CLIENT_GRID_NAV_CACHE[cache_key]


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


def request_nav_path(args: argparse.Namespace, region: int, start: object, goal: object) -> NavPathResult:
    if not args.nav_api_url:
        return NavPathResult(False, "disabled", [])

    request = urllib.request.Request(build_nav_path_url(args, region, start, goal), headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=args.nav_api_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        return NavPathResult(False, f"nav api error: {exc}", [])

    if not isinstance(payload, dict):
        return NavPathResult(False, "nav api returned a non-object response", [])

    return parse_nav_path_response(payload)


def build_combat_usable_api_url(args: argparse.Namespace, account: DummyAccount) -> str:
    if args.combat_usable_api_url:
        base_url = args.combat_usable_api_url
    else:
        api_host = args.host if args.host in ("127.0.0.1", "localhost", "::1") else "127.0.0.1"
        base_url = f"http://{api_host}:{args.api_port}/api/dummy/combat/usable"

    query = urllib.parse.urlencode({"name": character_name_from_account(account.username), "account": account.username})
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{query}"


def required_target_api_name(args: argparse.Namespace) -> str:
    return first_configured_target_name(
        getattr(args, "required_target_api_name", ""),
        getattr(args, "require_target_name", ""),
        getattr(args, "prefer_target_name", ""),
    )


def build_required_target_api_url(args: argparse.Namespace, region: int = 0) -> str:
    if args.required_target_api_url:
        base_url = args.required_target_api_url
    else:
        api_host = args.host if args.host in ("127.0.0.1", "localhost", "::1") else "127.0.0.1"
        base_url = f"http://{api_host}:{args.api_port}/api/dummy/combat/npcs"

    query: dict[str, str] = {"limit": str(max(1, int(args.required_target_api_limit)))}
    name = required_target_api_name(args)
    if name:
        query["name"] = name
    api_region = int(getattr(args, "required_target_api_region", -1) or -1)
    if api_region > 0:
        query["region"] = str(api_region)
    elif region > 0:
        query["region"] = str(region)
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urllib.parse.urlencode(query)}"


def build_current_target_api_url(args: argparse.Namespace, region: int, object_id: int) -> str:
    api_host = args.host if args.host in ("127.0.0.1", "localhost", "::1") else "127.0.0.1"
    base_url = f"http://{api_host}:{args.api_port}/api/dummy/combat/npcs"
    query = urllib.parse.urlencode(
        {
            "region": max(0, int(region)),
            "objectId": max(0, int(object_id)),
            "limit": 1,
        }
    )
    return f"{base_url}?{query}"


def api_region_for_client(args: argparse.Namespace, client) -> int:
    for value in (
        getattr(args, "path_region", 0),
        getattr(args, "required_target_api_region", 0),
        getattr(client, "region_id", 0),
        getattr(client, "zone_id", 0),
    ):
        try:
            region = int(value or 0)
        except (TypeError, ValueError):
            region = 0
        if region > 0:
            return region

    return 0


def build_hunter_target_api_url(args: argparse.Namespace, client, region: int) -> str:
    api_host = args.host if args.host in ("127.0.0.1", "localhost", "::1") else "127.0.0.1"
    base_url = f"http://{api_host}:{args.api_port}/api/dummy/combat/npcs"
    max_level = args.max_target_level if args.max_target_level >= 0 else args.player_level + args.max_target_level_delta
    query = urllib.parse.urlencode(
        {
            "region": max(0, int(region)),
            "x": int(getattr(client, "x", 0) or 0),
            "y": int(getattr(client, "y", 0) or 0),
            "radius": max(250, int(getattr(args, "hunter_target_api_radius", 0) or 0)),
            "minLevel": max(1, int(args.min_target_level)),
            "maxLevel": max(1, int(max_level)),
            "limit": max(1, int(getattr(args, "hunter_target_api_limit", 1) or 1)),
        }
    )
    return f"{base_url}?{query}"


def effective_flee_safe_point_distance(args: argparse.Namespace, client=None) -> float:
    flee_distance = float(getattr(args, "flee_safe_point_distance", 0.0) or 0.0)
    critical_threshold = int(getattr(args, "flee_critical_health_percent", 0) or 0)
    critical_distance = float(getattr(args, "flee_critical_safe_point_distance", 0.0) or 0.0)
    health_percent = int(getattr(client, "health_percent", 0) or 0) if client is not None else 0
    if critical_threshold > 0 and 0 < health_percent <= critical_threshold and critical_distance > flee_distance:
        return critical_distance
    return flee_distance


def build_flee_safe_api_url(args: argparse.Namespace, client, region: int) -> str:
    api_host = args.host if args.host in ("127.0.0.1", "localhost", "::1") else "127.0.0.1"
    base_url = f"http://{api_host}:{args.api_port}/api/dummy/combat/npcs"
    radius = max(
        int(float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0) + effective_flee_safe_point_distance(args, client)),
        2500,
    )
    player_level = max(1, int(getattr(args, "player_level", 1) or 1))
    query = urllib.parse.urlencode(
        {
            "region": max(0, int(region)),
            "x": int(getattr(client, "x", 0) or 0),
            "y": int(getattr(client, "y", 0) or 0),
            "radius": radius,
            "minLevel": 1,
            "maxLevel": min(80, player_level + 8),
            "limit": max(20, int(getattr(args, "flee_safe_api_limit", 80) or 80)),
        }
    )
    return f"{base_url}?{query}"


def required_target_observation_matches(args: argparse.Namespace, item: dict[str, object]) -> bool:
    name = str(item.get("name", "") or "")
    configured_name = required_target_api_name(args)
    if configured_name and required_target_name_matches(name, configured_name):
        return True
    return passes_required_target_filter(args, type("NpcName", (), {"name": name})())


def parse_required_target_observation(args: argparse.Namespace, payload: object) -> RequiredTargetObservation | None:
    if isinstance(payload, dict):
        raw_items = payload.get("items") or payload.get("npcs") or payload.get("results") or [payload]
    else:
        raw_items = payload

    if not isinstance(raw_items, list):
        return None

    items = [item for item in raw_items if isinstance(item, dict)]
    if not items:
        return None

    matching_items = [item for item in items if required_target_observation_matches(args, item)]
    item = matching_items[0] if matching_items else items[0]

    try:
        return RequiredTargetObservation(
            object_id=int(item.get("objectId", item.get("object_id", 0)) or 0),
            name=str(item.get("name", "") or ""),
            x=int(item.get("x", 0) or 0),
            y=int(item.get("y", 0) or 0),
            z=int(item.get("z", 0) or 0),
            level=int(item.get("level", 0) or 0),
            flags=int(item.get("flags", 0) or 0),
            last_seen=time.monotonic(),
            health_percent=float(item.get("healthPercent", item.get("health_percent", 0.0)) or 0.0),
            health=int(item.get("health", 0) or 0),
            max_health=int(item.get("maxHealth", item.get("max_health", 0)) or 0),
            is_alive=bool(item.get("isAlive", item.get("is_alive", True))),
            in_combat=bool(item.get("inCombat", item.get("in_combat", False))),
            has_aggro=bool(item.get("hasAggro", item.get("has_aggro", False))),
            target=str(item.get("target", "") or ""),
        )
    except (TypeError, ValueError):
        return None


def fetch_required_target_observation(
    args: argparse.Namespace,
    region: int = 0,
) -> RequiredTargetObservation | None:
    if not args.required_target_api:
        return None

    if not required_target_api_name(args):
        return None

    request = urllib.request.Request(build_required_target_api_url(args, region), headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=args.required_target_api_timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    return parse_required_target_observation(args, payload)


def fetch_current_target_observation(
    args: argparse.Namespace,
    region: int,
    object_id: int,
) -> RequiredTargetObservation | None:
    if not getattr(args, "current_target_api_refresh", False) or object_id <= 0 or region <= 0:
        return None

    request = urllib.request.Request(
        build_current_target_api_url(args, region, object_id),
        headers={"Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=args.current_target_api_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    return parse_required_target_observation(args, payload)


def fetch_hunter_target_api_observation(
    args: argparse.Namespace,
    client,
    rng: random.Random,
    rejected_targets: dict[int, float],
    rejected_target_kinds: dict[tuple[str, int], float],
    now: float,
) -> RequiredTargetObservation | None:
    if not getattr(args, "hunter_target_api_scout", False):
        return None

    region = int(getattr(client, "zone_id", 0) or args.path_region or 0)
    if region <= 0:
        return None

    request = urllib.request.Request(
        build_hunter_target_api_url(args, client, region),
        headers={"Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=args.hunter_target_api_timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return None

    if isinstance(payload, dict):
        raw_items = payload.get("items") or payload.get("npcs") or payload.get("results") or [payload]
    else:
        raw_items = payload
    if not isinstance(raw_items, list):
        return None

    prefer_tokens = [token.strip().lower() for token in args.prefer_target_name.split(",") if token.strip()]
    avoid_tokens = [token.strip().lower() for token in args.avoid_target_name.split(",") if token.strip()]
    require_tokens = [token.strip().lower() for token in getattr(args, "require_target_name", "").split(",") if token.strip()]
    max_level = args.max_target_level if args.max_target_level >= 0 else args.player_level + args.max_target_level_delta
    target_home = getattr(args, "required_target_home", None)
    target_home_max_distance = float(getattr(args, "target_home_max_distance", 0.0) or 0.0)
    engage_distance = float(getattr(args, "hunter_target_api_engage_distance", 0.0) or 0.0)
    if engage_distance <= 0.0:
        engage_distance = float(getattr(args, "max_target_distance", 0.0) or 0.0)

    def home_ok(item: RequiredTargetObservation) -> bool:
        if target_home is None or target_home_max_distance <= 0.0:
            return True
        return (
            horizontal_distance_between_points(
                int(getattr(target_home, "x", 0) or 0),
                int(getattr(target_home, "y", 0) or 0),
                item.x,
                item.y,
            )
            <= target_home_max_distance
        )

    def candidate_items(*, allow_avoided: bool) -> list[RequiredTargetObservation]:
        candidates: list[RequiredTargetObservation] = []
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            parsed = parse_required_target_observation(args, [raw_item])
            if parsed is None or parsed.object_id <= 0:
                continue
            name = parsed.name.lower()
            if rejected_targets.get(parsed.object_id, 0.0) > now:
                continue
            if rejected_target_kinds.get((name, parsed.level), 0.0) > now:
                continue
            if parsed.level < args.min_target_level or parsed.level > max_level:
                continue
            if require_tokens and not any(token in name for token in require_tokens):
                continue
            if not allow_avoided and any(token in name for token in avoid_tokens):
                continue
            if not home_ok(parsed):
                continue
            if engage_distance > 0.0:
                distance = horizontal_distance_between_points(
                    int(getattr(client, "x", 0) or 0),
                    int(getattr(client, "y", 0) or 0),
                    parsed.x,
                    parsed.y,
                )
                if distance > engage_distance:
                    continue
            if not hunter_target_ground_z_aligned(args, client, parsed, region=region):
                continue
            candidates.append(parsed)
        return candidates

    candidates = candidate_items(allow_avoided=False)
    if not candidates and getattr(args, "allow_avoid_target_fallback", False):
        candidates = candidate_items(allow_avoided=True)

    if not candidates:
        return None

    def score(item: RequiredTargetObservation) -> float:
        distance = horizontal_distance_between_points(
            int(getattr(client, "x", 0) or 0),
            int(getattr(client, "y", 0) or 0),
            item.x,
            item.y,
        )
        value = 1000.0 - distance / max(args.target_distance_weight, 1.0)
        if prefer_tokens and any(token in item.name.lower() for token in prefer_tokens):
            value += args.prefer_target_bonus
        value += rng.uniform(0.0, args.target_randomness)
        return value

    return max(candidates, key=score)


def fetch_flee_safe_api_observations(args: argparse.Namespace, client) -> list[RequiredTargetObservation]:
    if not getattr(args, "flee_safe_api_scout", False):
        return []

    region = int(getattr(client, "zone_id", 0) or getattr(args, "path_region", 0) or 0)
    if region <= 0:
        return []

    request = urllib.request.Request(
        build_flee_safe_api_url(args, client, region),
        headers={"Accept": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=getattr(args, "flee_safe_api_timeout", 1.0)) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    if isinstance(payload, dict):
        raw_items = payload.get("items") or payload.get("npcs") or payload.get("results") or [payload]
    else:
        raw_items = payload

    if not isinstance(raw_items, list):
        return []

    observations: list[RequiredTargetObservation] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            continue
        parsed = parse_required_target_observation(args, [raw_item])
        if parsed is not None and parsed.object_id > 0:
            observations.append(parsed)
    return observations


def flee_threat_snapshot(args: argparse.Namespace, client, *, member_name: str = "") -> dict[str, object] | None:
    threat_radius = float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0)
    if threat_radius <= 0.0:
        return None

    aggro_radius = threat_radius + effective_flee_safe_point_distance(args, client)
    candidates: list[tuple[int, float, float, object]] = []

    visible = client.visible_npcs(max_age=getattr(args, "npc_max_age", 60.0), include_peace=should_scan_peace_npcs(args))
    api_observations = fetch_flee_safe_api_observations(args, client)
    member_key = normalize_target_name(member_name)

    for npc in list(visible) + list(api_observations):
        weight = flee_threat_weight(args, npc)
        if weight <= 0.0:
            continue

        distance = combat_distance_to(client, npc)
        target_name = normalize_target_name(str(getattr(npc, "target", "") or ""))
        chasing_this_dummy = bool(
            member_key
            and target_name
            and (target_name == member_key or member_key in target_name or target_name in member_key)
        )
        active_aggro = bool(getattr(npc, "has_aggro", False) or getattr(npc, "in_combat", False) or chasing_this_dummy)

        if distance <= threat_radius or (active_aggro and distance <= aggro_radius):
            candidates.append((1 if active_aggro else 0, distance, weight, npc))

    if not candidates:
        return None

    active_aggro, distance, weight, npc = min(candidates, key=lambda item: (-item[0], item[1], -item[2]))
    return {
        "flee_threat_id": int(getattr(npc, "object_id", 0) or 0),
        "flee_threat_name": str(getattr(npc, "name", "") or ""),
        "flee_threat_level": int(getattr(npc, "level", 0) or 0),
        "flee_threat_distance": round(distance, 1),
        "flee_threat_weight": round(weight, 2),
        "flee_threat_active": bool(active_aggro),
        "flee_threat_has_aggro": bool(getattr(npc, "has_aggro", False)),
        "flee_threat_in_combat": bool(getattr(npc, "in_combat", False)),
        "flee_threat_targets_dummy": bool(chasing_this_dummy),
        "flee_threat_target": str(getattr(npc, "target", "") or ""),
    }


def flee_threat_snapshot_is_active(snapshot: dict[str, object] | None) -> bool:
    if snapshot is None:
        return False

    return bool(
        snapshot.get("flee_threat_active")
        or snapshot.get("flee_threat_has_aggro")
        or snapshot.get("flee_threat_in_combat")
        or snapshot.get("flee_threat_targets_dummy")
    )


def should_continue_flee_for_active_threat(threat_snapshot: dict[str, object] | None) -> bool:
    return flee_threat_snapshot_is_active(threat_snapshot)


def should_extend_flee_after_duration(threat_snapshot: dict[str, object] | None) -> bool:
    return should_continue_flee_for_active_threat(threat_snapshot)


def should_rest_after_flee_recovery(args: argparse.Namespace, *, health_percent: int) -> bool:
    required_recover_threshold = int(getattr(args, "required_target_recover_before_home_health_percent", 0) or 0)
    if (
        required_recover_threshold > 0
        and getattr(args, "required_target_home", None) is not None
        and 0 < health_percent <= required_recover_threshold
    ):
        return True

    resume_threshold = int(getattr(args, "low_health_rest_resume_percent", 0) or 0)
    rest_threshold = int(getattr(args, "low_health_rest_percent", 0) or 0) or resume_threshold
    return bool(resume_threshold > 0 and 0 < health_percent < resume_threshold and health_percent <= rest_threshold)


def should_extend_recovery_rest(args: argparse.Namespace, *, health_percent: int) -> bool:
    return should_rest_after_flee_recovery(args, health_percent=health_percent)


def target_actor_with_server_observation(actor, observation: RequiredTargetObservation | None):
    if observation is None or int(getattr(actor, "object_id", 0) or 0) != observation.object_id:
        return actor

    return SimpleNamespace(
        object_id=observation.object_id,
        name=observation.name or getattr(actor, "name", ""),
        x=observation.x,
        y=observation.y,
        z=observation.z,
        level=observation.level or int(getattr(actor, "level", 0) or 0),
        flags=int(getattr(actor, "flags", 0) or 0),
    )


def actor_from_target_observation(observation: RequiredTargetObservation):
    return SimpleNamespace(
        object_id=observation.object_id,
        name=observation.name,
        x=observation.x,
        y=observation.y,
        z=observation.z,
        level=observation.level,
        flags=observation.flags,
    )


def actor_from_active_combat(active_combat):
    if active_combat is None:
        return None
    return SimpleNamespace(
        object_id=int(active_combat.get("target_id", 0) or 0),
        name=str(active_combat.get("target_name", "") or ""),
        x=int(active_combat.get("target_x", 0) or 0),
        y=int(active_combat.get("target_y", 0) or 0),
        z=int(active_combat.get("target_z", 0) or 0),
        level=int(active_combat.get("target_level", 0) or 0),
        flags=0,
    )


def party_rescue_actor_from_snapshot(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str],
    *,
    member_name: str,
    action_rotation: str,
    health_percent: int,
    now: float,
):
    if not getattr(args, "party_rescue_aggro", False):
        return None
    if not party_member_is_active_tank(party_snapshot, member_name):
        return None
    if not is_melee_rotation(action_rotation):
        return None

    health_floor = int(getattr(args, "flee_melee_counterattack_health_floor", 0) or 0)
    if health_floor > 0 and health_percent <= health_floor:
        return None

    target_id = int(party_snapshot.get("rescue_target_id", 0) or 0)
    if target_id <= 0:
        return None

    target_x = int(party_snapshot.get("rescue_target_x", 0) or 0)
    target_y = int(party_snapshot.get("rescue_target_y", 0) or 0)
    target_z = int(party_snapshot.get("rescue_target_z", 0) or 0)

    requested_at = float(party_snapshot.get("rescue_requested_at", 0.0) or 0.0)
    target_age = now - requested_at if requested_at > 0.0 else 0.0
    max_age = max(0.0, float(getattr(args, "party_rescue_max_age", 0.0) or 0.0))
    if target_age < 0.0 or (max_age > 0.0 and target_age > max_age):
        return None

    return SimpleNamespace(
        object_id=target_id,
        name=str(party_snapshot.get("rescue_target_name", "") or "rescue target"),
        x=target_x,
        y=target_y,
        z=target_z,
        level=int(party_snapshot.get("rescue_target_level", 0) or 0),
        flags=0,
    )


def party_objective_actor_from_snapshot_for_counterattack(
    args: argparse.Namespace,
    party_snapshot: dict[str, int | float | str],
    *,
    member_name: str,
    action_rotation: str,
    health_percent: int,
    behavior_state: DummyBehaviorState | str = DummyBehaviorState.HuntObjective,
    required_home_hunt_ready: bool = True,
    party_ready_for_objective: bool = True,
):
    if not party_member_is_active_tank(party_snapshot, member_name):
        return None
    if not is_melee_rotation(action_rotation):
        return None

    flee_threshold = int(getattr(args, "flee_health_percent", 0) or 0)
    if flee_threshold > 0 and health_percent <= flee_threshold:
        return None

    target_id = int(party_snapshot.get("leader_target_id", 0) or 0)
    if target_id <= 0:
        return None

    if not should_commit_required_retaliation_for_objective(
        args,
        behavior_state,
        required_home_hunt_ready=required_home_hunt_ready,
        party_ready_for_objective=party_ready_for_objective,
        direct_required_damage_to_active_tank=True,
    ):
        return None

    target_name = str(party_snapshot.get("leader_target_name", "") or "")
    required_tokens = required_target_tokens(args)
    if target_name and required_tokens and not any(required_target_name_matches(target_name, token) for token in required_tokens):
        return None

    return SimpleNamespace(
        object_id=target_id,
        name=target_name or "objective target",
        x=int(party_snapshot.get("leader_target_x", 0) or 0),
        y=int(party_snapshot.get("leader_target_y", 0) or 0),
        z=int(party_snapshot.get("leader_target_z", 0) or 0),
        level=int(party_snapshot.get("leader_target_level", 0) or 0),
        flags=0,
    )


def fresh_hunter_target_observation(args: argparse.Namespace, observation: RequiredTargetObservation | None, now: float) -> bool:
    if observation is None:
        return False
    max_age = max(
        float(getattr(args, "current_target_api_max_age", 0.0) or 0.0),
        float(getattr(args, "hunter_target_api_max_age", 0.0) or 0.0),
    )
    return max_age <= 0.0 or now - observation.last_seen <= max_age


def parse_usable_skill(value: object) -> UsableSkillRef | None:
    if not isinstance(value, dict) or str(value.get("kind", "")) != "Style":
        return None

    style = value.get("style")
    if isinstance(style, dict):
        if str(style.get("openingRequirementType", "")) == "Positional":
            return None
        if str(style.get("attackResultRequirement", "")) not in ("", "Any"):
            return None

    try:
        return UsableSkillRef(
            use_skill_index=int(value["useSkillIndex"]),
            use_skill_type=int(value["useSkillType"]),
            name=str(value.get("name", "")),
            level=int(value.get("level", 0) or 0),
        )
    except (KeyError, TypeError, ValueError):
        return None


def parse_usable_spell(value: object) -> tuple[str, UsableSpellRef] | None:
    if not isinstance(value, dict) or str(value.get("kind", "")) != "Spell":
        return None

    spell = value.get("spell")
    if not isinstance(spell, dict):
        return None

    try:
        ref = UsableSpellRef(
            line_index=int(value["lineIndex"]),
            spell_level=int(value["spellLevel"]),
            name=str(value.get("name", "")),
            level=int(value.get("level", 0) or 0),
        )
    except (KeyError, TypeError, ValueError):
        return None

    return bucket_usable_spell(spell, ref)


def parse_usable_hybrid_spell(value: object) -> tuple[str, UsableSpellRef] | None:
    if not isinstance(value, dict) or str(value.get("kind", "")) != "Spell":
        return None

    spell = value.get("spell")
    if not isinstance(spell, dict):
        return None

    try:
        ref = UsableSpellRef(
            line_index=-1,
            spell_level=int(value.get("level", 0) or 0),
            name=str(value.get("name", "")),
            level=int(value.get("level", 0) or 0),
            use_skill_index=int(value["useSkillIndex"]),
            use_skill_type=int(value["useSkillType"]),
        )
    except (KeyError, TypeError, ValueError):
        return None

    return bucket_usable_spell(spell, ref)


def bucket_usable_spell(spell: dict, ref: UsableSpellRef) -> tuple[str, UsableSpellRef] | None:
    is_harmful = bool(spell.get("isHarmful"))
    is_healing = bool(spell.get("isHealing"))
    is_buff = bool(spell.get("isBuff"))
    damage = float(spell.get("damage", 0) or 0)
    spell_range = int(spell.get("range", 0) or 0)

    if is_healing:
        return "heal", ref
    if is_buff:
        return "buff", ref
    if is_harmful and spell_range > 0 and damage > 0:
        return "attack", ref

    return None


def parse_combat_usable_plan(payload: object) -> CombatUsablePlan:
    if not isinstance(payload, dict):
        return CombatUsablePlan()

    skills = [
        skill
        for raw_skill in payload.get("skills", [])
        if (skill := parse_usable_skill(raw_skill)) is not None
    ]
    attack_spells: list[UsableSpellRef] = []
    heal_spells: list[UsableSpellRef] = []
    buff_spells: list[UsableSpellRef] = []

    for raw_skill in payload.get("skills", []):
        parsed = parse_usable_hybrid_spell(raw_skill)

        if parsed is None:
            continue

        bucket, spell = parsed
        if bucket == "heal":
            heal_spells.append(spell)
        elif bucket == "buff":
            buff_spells.append(spell)
        elif bucket == "attack":
            attack_spells.append(spell)

    for raw_line in payload.get("spellLines", []):
        if not isinstance(raw_line, dict):
            continue

        for raw_entry in raw_line.get("entries", []):
            parsed = parse_usable_spell(raw_entry)

            if parsed is None:
                continue

            bucket, spell = parsed
            if bucket == "heal":
                heal_spells.append(spell)
            elif bucket == "buff":
                buff_spells.append(spell)
            elif bucket == "attack":
                attack_spells.append(spell)

    sort_key = lambda item: (item.level, item.name)
    sorted_skills = sorted(skills, key=sort_key, reverse=True)
    return CombatUsablePlan(
        skills=sorted_skills,
        taunt_skills=sorted([skill for skill in sorted_skills if is_taunt_skill(skill)], key=sort_key, reverse=True),
        attack_spells=sorted(attack_spells, key=sort_key, reverse=True),
        heal_spells=sorted(heal_spells, key=sort_key, reverse=True),
        buff_spells=sorted(buff_spells, key=sort_key, reverse=True),
    )


def fetch_combat_usable_plan(args: argparse.Namespace, account: DummyAccount) -> CombatUsablePlan:
    if not args.combat_usable_api:
        return CombatUsablePlan()

    request = urllib.request.Request(build_combat_usable_api_url(args, account), headers={"Accept": "application/json"})
    attempts = max(int(getattr(args, "combat_usable_api_retries", 1) or 1), 1)
    delay = max(float(getattr(args, "combat_usable_api_retry_delay", 0.0) or 0.0), 0.0)

    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=args.combat_usable_api_timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return parse_combat_usable_plan(payload)
        except Exception as exc:
            last_error = exc
            if attempt + 1 < attempts and delay > 0:
                time.sleep(delay)

    if last_error is not None:
        raise last_error

    return CombatUsablePlan()


def spell_action_speed(client, target_in_view: bool, speed: float | None = None, stationary: bool = False) -> float | None:
    if stationary and hasattr(client, "send_position_update"):
        client.send_position_update(speed=0.0, target_in_view=target_in_view)
        return 0.0

    return speed


def cast_raw_spell(
    client,
    spell_level: int,
    *,
    spell_line_index: int,
    target_in_view: bool,
    speed: float | None = None,
    stationary: bool = False,
) -> int:
    return client.use_spell(
        spell_level,
        spell_line_index=spell_line_index,
        target_in_view=target_in_view,
        speed=spell_action_speed(client, target_in_view, speed=speed, stationary=stationary),
    )


def cast_usable_spell(
    client,
    spell: UsableSpellRef,
    target_in_view: bool,
    speed: float | None = None,
    stationary: bool = False,
) -> int:
    cast_speed = spell_action_speed(client, target_in_view, speed=speed, stationary=stationary)

    if spell.use_skill_index >= 0:
        return client.use_skill(
            spell.use_skill_index,
            skill_type=spell.use_skill_type,
            target_in_view=target_in_view,
            speed=cast_speed,
        )

    return client.use_spell(
        spell.spell_level,
        spell_line_index=spell.line_index,
        target_in_view=target_in_view,
        speed=cast_speed,
    )


def cast_party_friendly_usable_spell(
    client,
    spell: UsableSpellRef,
    args: argparse.Namespace,
    *,
    target_in_view: bool,
) -> int:
    return cast_usable_spell(
        client,
        spell,
        target_in_view=target_in_view,
        speed=getattr(client, "last_position_speed", 0.0),
        stationary=True,
    )


def cast_precombat_self_buffs(
    client,
    args: argparse.Namespace,
    combat_plan: CombatUsablePlan,
    action_counts: dict[str, int],
) -> int:
    count = max(0, int(getattr(args, "startup_self_buff_count", 0) or 0))
    if count <= 0 or not combat_plan.buff_spells:
        return 0

    actions = 0
    delay = max(0.0, float(getattr(args, "startup_self_buff_delay", 0.0) or 0.0))
    for spell in combat_plan.buff_spells[:count]:
        cast_usable_spell(client, spell, target_in_view=True, speed=0.0, stationary=True)
        actions += add_action(action_counts, "precombat_self_buff_spell")
        if delay > 0.0:
            time.sleep(delay)

    return actions


def cast_party_friendly_raw_spell(
    client,
    spell_level: int,
    args: argparse.Namespace,
    *,
    spell_line_index: int,
    target_in_view: bool,
) -> int:
    return cast_raw_spell(
        client,
        spell_level,
        spell_line_index=spell_line_index,
        target_in_view=target_in_view,
        speed=getattr(client, "last_position_speed", 0.0),
        stationary=True,
    )


def nav_segment_allowed(
    args: argparse.Namespace,
    region: int,
    start: object,
    goal: object,
    path_state: PathMovementState | None = None,
) -> tuple[bool, str]:
    if not args.nav_api_url or not getattr(args, "nav_segment_validate", False):
        return True, "disabled"
    if path_state is not None and int(region) in path_state.navmesh_unavailable_regions:
        return True, "NavmeshUnavailableCached"

    result = request_nav_path(args, region, start, goal)
    if path_state is not None:
        remember_nav_path_failure(path_state, result.status)
    return result.ok, result.status


def should_request_nav_path(args: argparse.Namespace, path_state: PathMovementState) -> bool:
    if not args.nav_api_url:
        return False
    return int(path_state.region) not in path_state.navmesh_unavailable_regions


def remember_nav_path_failure(path_state: PathMovementState, status: str) -> None:
    if status == "NavmeshUnavailable":
        path_state.navmesh_unavailable_regions.add(int(path_state.region))


def graph_can_fallback_from_nav_failure(path_state: PathMovementState, reason: str) -> bool:
    if path_state.graph is None and path_state.client_grid is None:
        return False

    if reason.startswith("nav api error:"):
        return True

    return reason in {
        "NavmeshUnavailable",
        "ZoneNotFound",
        "CrossZonePathUnsupported",
    }


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
    client_grid = load_client_grid_nav(args)

    if args.disable_graph_pathing or not args.path_graph:
        return PathMovementState(None, region, build_path_safety(args), client_grid)

    return PathMovementState(load_path_graph(args.path_graph), region, build_path_safety(args), client_grid)


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


def required_target_home_destination(args: argparse.Namespace) -> MovementDestination | None:
    home = getattr(args, "required_target_home", None)

    if home is None:
        return None

    return destination_from_point("required-target-home", home.x, home.y, home.z)


def flee_threat_weight(args: argparse.Namespace, npc) -> float:
    player_level = int(getattr(args, "player_level", 1) or 1)
    npc_level = int(getattr(npc, "level", 0) or 0)
    name = str(getattr(npc, "name", "") or "").lower()
    avoid_tokens = [token.strip().lower() for token in str(getattr(args, "avoid_target_name", "") or "").split(",") if token.strip()]
    weight = 1.0

    if npc_level > player_level:
        weight += float(npc_level - player_level) * 6.0

    if any(token in name for token in avoid_tokens):
        weight += 8.0

    if bool(getattr(npc, "has_aggro", False)) or bool(getattr(npc, "in_combat", False)):
        weight += 30.0

    return weight


def flee_candidate_risk(args: argparse.Namespace, candidate_x: int, candidate_y: int, npcs: list[object]) -> float:
    threat_radius = float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0)
    if threat_radius <= 0.0:
        return 0.0

    risk = 0.0
    for npc in npcs:
        npc_x = int(getattr(npc, "x", 0) or 0)
        npc_y = int(getattr(npc, "y", 0) or 0)
        distance = horizontal_distance_between_points(candidate_x, candidate_y, npc_x, npc_y)
        if distance > threat_radius:
            continue

        weight = flee_threat_weight(args, npc)
        risk += weight * (threat_radius - distance) / threat_radius
        if distance < 900.0:
            risk += weight * (900.0 - distance) / 90.0

    return risk


def select_dynamic_flee_destination_from_npcs(args: argparse.Namespace, client, npcs: list[object]) -> MovementDestination | None:
    flee_distance = effective_flee_safe_point_distance(args, client)
    threat_radius = float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0)
    if flee_distance <= 0.0 or threat_radius <= 0.0 or not npcs:
        return None

    origin_x = int(getattr(client, "x", 0) or 0)
    origin_y = int(getattr(client, "y", 0) or 0)
    origin_z = int(getattr(client, "z", 0) or 0)
    nearby_npcs = [
        npc
        for npc in npcs
        if horizontal_distance_between_points(origin_x, origin_y, int(getattr(npc, "x", 0) or 0), int(getattr(npc, "y", 0) or 0))
        <= threat_radius
    ]
    if not nearby_npcs:
        return None

    directions = 16
    candidates: list[tuple[float, int, int]] = []
    for index in range(directions):
        angle = math.tau * index / directions
        candidate_x = int(origin_x + math.cos(angle) * flee_distance)
        candidate_y = int(origin_y + math.sin(angle) * flee_distance)
        risk = flee_candidate_risk(args, candidate_x, candidate_y, npcs)
        candidates.append((risk, candidate_x, candidate_y))

    current_risk = flee_candidate_risk(args, origin_x, origin_y, npcs)
    best_risk, target_x, target_y = min(candidates)
    if best_risk >= current_risk:
        return None

    return destination_from_point("flee-safe", target_x, target_y, origin_z, bucket=100)


def fallback_flee_pressure_destination_from_npcs(args: argparse.Namespace, client, npcs: list[object]) -> MovementDestination | None:
    flee_distance = effective_flee_safe_point_distance(args, client)
    threat_radius = float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0)
    if flee_distance <= 0.0 or threat_radius <= 0.0 or not npcs:
        return None

    origin_x = int(getattr(client, "x", 0) or 0)
    origin_y = int(getattr(client, "y", 0) or 0)
    origin_z = int(getattr(client, "z", 0) or 0)
    pressure_radius = threat_radius + flee_distance
    pressure_npcs = [
        npc
        for npc in npcs
        if flee_threat_weight(args, npc) > 0.0 and combat_distance_to(client, npc) <= pressure_radius
    ]
    if not pressure_npcs:
        return None

    threat = min(
        pressure_npcs,
        key=lambda npc: (
            not (bool(getattr(npc, "has_aggro", False)) or bool(getattr(npc, "in_combat", False))),
            combat_distance_to(client, npc),
        ),
    )
    threat_x = int(getattr(threat, "x", origin_x) or origin_x)
    threat_y = int(getattr(threat, "y", origin_y) or origin_y)
    dx = origin_x - threat_x
    dy = origin_y - threat_y
    length = math.hypot(dx, dy)
    if length <= 0.0:
        dx, dy, length = 1.0, 0.0, 1.0

    target_x = int(origin_x + dx / length * flee_distance)
    target_y = int(origin_y + dy / length * flee_distance)
    return destination_from_point("flee-safe", target_x, target_y, origin_z, bucket=100)


def has_active_flee_pressure_npc(npcs: list[object]) -> bool:
    for npc in npcs:
        if bool(getattr(npc, "has_aggro", False)) or bool(getattr(npc, "in_combat", False)):
            return True
        if str(getattr(npc, "target", "") or "").strip():
            return True
    return False


def dynamic_flee_safe_destination(args: argparse.Namespace, client) -> MovementDestination | None:
    if not getattr(args, "flee_dynamic_safe_point", False) or client is None:
        return None

    visible_npcs = getattr(client, "visible_npcs", None)
    if not callable(visible_npcs):
        return None

    try:
        npcs = visible_npcs(max_age=getattr(args, "npc_max_age", 60.0), include_peace=False)
    except TypeError:
        npcs = visible_npcs()

    api_npcs = fetch_flee_safe_api_observations(args, client)
    combined_npcs = list(npcs) + [npc for npc in api_npcs if all(getattr(existing, "object_id", 0) != npc.object_id for existing in npcs)]

    destination = select_dynamic_flee_destination_from_npcs(args, client, combined_npcs)
    if has_active_flee_pressure_npc(combined_npcs):
        pressure_destination = fallback_flee_pressure_destination_from_npcs(args, client, combined_npcs)
        if pressure_destination is not None:
            if destination is None:
                return pressure_destination
            pressure_risk = flee_candidate_risk(args, pressure_destination.x, pressure_destination.y, combined_npcs)
            destination_risk = flee_candidate_risk(args, destination.x, destination.y, combined_npcs)
            if pressure_risk <= destination_risk:
                return pressure_destination

    if destination is not None:
        return destination

    return fallback_flee_pressure_destination_from_npcs(args, client, combined_npcs)


def should_prefer_flee_home_before_dynamic(args: argparse.Namespace, client) -> bool:
    home = getattr(args, "flee_home", None) or getattr(args, "required_target_home", None)
    if home is None or client is None:
        return False

    health_percent = int(getattr(client, "health_percent", 0) or 0)
    town_threshold = int(getattr(args, "flee_town_health_percent", 0) or 0)
    if health_percent <= 0 or town_threshold <= 0 or health_percent > town_threshold:
        return False

    if not getattr(args, "flee_dynamic_safe_point", False):
        return True

    critical_threshold = int(getattr(args, "flee_critical_health_percent", 0) or 0)
    return critical_threshold <= 0 or health_percent <= critical_threshold



def flee_escape_destination(args: argparse.Namespace, client=None) -> MovementDestination | None:
    home = getattr(args, "flee_home", None) or getattr(args, "required_target_home", None)

    dynamic_destination = dynamic_flee_safe_destination(args, client)
    if dynamic_destination is not None:
        return dynamic_destination

    if home is None:
        return None

    return destination_from_point("flee-home", home.x, home.y, home.z)


def flee_escape_destination_from_active_combat(
    args: argparse.Namespace,
    client,
    active_combat,
) -> MovementDestination | None:
    if not getattr(args, "flee_dynamic_safe_point", False) or client is None or active_combat is None:
        return None

    home = getattr(args, "flee_home", None) or getattr(args, "required_target_home", None)
    if should_prefer_flee_home_before_dynamic(args, client):
        return destination_from_point("flee-home", home.x, home.y, home.z)

    flee_distance = effective_flee_safe_point_distance(args, client)
    if flee_distance <= 0.0:
        return None

    origin_x = int(getattr(client, "x", 0) or 0)
    origin_y = int(getattr(client, "y", 0) or 0)
    origin_z = int(getattr(client, "z", 0) or 0)
    threat_x = int(active_combat.get("target_x", origin_x) or origin_x)
    threat_y = int(active_combat.get("target_y", origin_y) or origin_y)
    dx = origin_x - threat_x
    dy = origin_y - threat_y
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return None

    target_x = int(origin_x + dx / length * flee_distance)
    target_y = int(origin_y + dy / length * flee_distance)
    return destination_from_point("flee-safe", target_x, target_y, origin_z, bucket=100)


def flee_escape_destination_for_combat(
    args: argparse.Namespace,
    client,
    active_combat,
) -> MovementDestination | None:
    dynamic_destination = flee_escape_destination(args, client)
    if dynamic_destination is not None and destination_kind(dynamic_destination) == "flee-safe":
        return dynamic_destination
    return flee_escape_destination_from_active_combat(args, client, active_combat) or dynamic_destination


def should_flee_losing_combat(
    args: argparse.Namespace,
    active_combat,
    *,
    health_percent: int,
    now: float,
) -> bool:
    if active_combat is None:
        return False

    active_target_name = normalize_target_name(str(active_combat.get("target_name", "") or ""))
    commit_floor = int(getattr(args, "required_target_tank_commit_health_percent", 0) or 0)
    if commit_floor > 0 and health_percent > commit_floor and name_matches_required_target(args, active_target_name):
        return False

    damage_done = max(0, int(active_combat.get("damage_done", 0) or 0))
    pressure_threshold = int(getattr(args, "flee_pressure_health_percent", 0) or 0)
    if damage_done <= 0:
        threshold = max(
            int(getattr(args, "flee_health_percent", 0) or 0),
            int(getattr(args, "low_health_rest_percent", 0) or 0),
            pressure_threshold,
        )
    else:
        threshold = max(
            int(getattr(args, "flee_health_percent", 0) or 0),
            int(getattr(args, "low_health_rest_percent", 0) or 0),
        )
    critical_health = int(getattr(args, "flee_critical_health_percent", 0) or 0)
    if critical_health > 0 and 0 < health_percent <= critical_health:
        return True

    if threshold <= 0 or health_percent <= 0 or health_percent > threshold:
        return False

    started = float(active_combat.get("started", now) or now)
    min_age = max(0.0, float(getattr(args, "flee_min_combat_seconds", 0.0) or 0.0))

    raw_damage_taken = max(0, int(active_combat.get("damage_taken", 0) or 0))
    healing_received = max(0, int(active_combat.get("healing_received", 0) or 0))
    damage_taken = max(0, raw_damage_taken - healing_received)
    min_damage_taken = max(0, int(getattr(args, "flee_min_damage_taken", 0) or 0))
    if raw_damage_taken < min_damage_taken:
        return False

    if damage_done <= 0 and pressure_threshold > 0 and health_percent <= pressure_threshold:
        return True

    if now - started < min_age:
        return False

    ratio = max(0.0, float(getattr(args, "flee_damage_taken_ratio", 0.0) or 0.0))
    if ratio <= 0.0:
        return True

    if damage_done <= 0:
        return damage_taken > 0

    return damage_taken >= damage_done * ratio


def should_delay_early_flee_for_melee_counterattack(
    args: argparse.Namespace,
    active_combat,
    *,
    health_percent: int,
    recent_incoming_melee: bool,
    target_distance: float = 0.0,
) -> bool:
    if not recent_incoming_melee or active_combat is None:
        return False

    active_target_name = normalize_target_name(str(active_combat.get("target_name", "") or ""))
    is_required_objective = name_matches_required_target(args, active_target_name)

    critical_health = int(getattr(args, "flee_critical_health_percent", 0) or 0)
    commit_floor = int(getattr(args, "required_target_tank_commit_health_percent", 0) or 0)
    if critical_health > 0 and health_percent <= critical_health:
        if not (is_required_objective and commit_floor > 0 and health_percent > commit_floor):
            return False

    health_floor = int(getattr(args, "flee_melee_counterattack_health_floor", 0) or 0)
    if not is_required_objective and health_floor > 0 and health_percent <= health_floor:
        return False

    damage_done = max(0, int(active_combat.get("damage_done", 0) or 0))
    damage_taken = max(0, int(active_combat.get("damage_taken", 0) or 0))
    if damage_done <= 0:
        max_counterattack_distance = max(
            0.0,
            float(getattr(args, "flee_melee_counterattack_max_distance", 0.0) or 0.0),
        )
        if max_counterattack_distance > 0.0 and target_distance > max_counterattack_distance:
            return False
        return damage_taken > 0

    min_attacks = max(0, int(getattr(args, "flee_melee_counterattack_min_attacks", 0) or 0))
    attacks = max(0, int(active_combat.get("attacks", 0) or 0))
    if min_attacks > 0 and attacks < min_attacks:
        return True

    return damage_done >= max(1, int(damage_taken * 0.75))


def should_flee_multi_aggro_combat(
    args: argparse.Namespace,
    active_combat,
    *,
    health_percent: int,
) -> bool:
    if active_combat is None or health_percent <= 0:
        return False

    pressure_threshold = int(getattr(args, "flee_pressure_health_percent", 0) or 0)
    if pressure_threshold <= 0 or health_percent > pressure_threshold:
        return False

    off_target_damage = max(0, int(active_combat.get("off_target_damage_taken", 0) or 0))
    if off_target_damage <= 0:
        return False

    min_damage_taken = max(0, int(getattr(args, "flee_min_damage_taken", 0) or 0))
    total_damage_taken = max(0, int(active_combat.get("damage_taken", 0) or 0))
    return total_damage_taken >= min_damage_taken


def should_flee_rest_pressure(
    args: argparse.Namespace,
    *,
    current_health_percent: int,
    last_health_percent: int,
    local_rescue_until: float,
    now: float,
) -> bool:
    if current_health_percent <= 0:
        return False

    rest_threshold = int(getattr(args, "low_health_rest_percent", 0) or 0)
    if rest_threshold > 0 and current_health_percent > rest_threshold:
        return False

    if last_health_percent > 0 and current_health_percent < last_health_percent:
        return True

    return local_rescue_until > now and (rest_threshold <= 0 or current_health_percent <= rest_threshold)


def should_flee_instead_of_low_health_rest(
    args: argparse.Namespace,
    *,
    current_health_percent: int,
    previous_health_percent: int = 0,
    recent_damage_age_seconds: float | None = None,
    active_threat: bool = False,
) -> bool:
    if current_health_percent <= 0:
        return False

    rest_threshold = int(getattr(args, "low_health_rest_percent", 0) or 0)
    if rest_threshold > 0 and current_health_percent > rest_threshold:
        return False

    if active_threat:
        return True

    if previous_health_percent > 0 and current_health_percent < previous_health_percent:
        return True

    damage_grace = max(0.0, float(getattr(args, "incoming_damage_melee_grace", 4.0) or 4.0))
    return (
        recent_damage_age_seconds is not None
        and damage_grace > 0.0
        and 0.0 <= recent_damage_age_seconds <= damage_grace
    )


def should_hunter_wind_down_before_segment_end(
    args: argparse.Namespace,
    *,
    time_left_seconds: float,
    target_removed_count: int,
    current_target: int,
) -> bool:
    min_time_left = float(getattr(args, "hunter_min_time_left_for_new_target", 0.0) or 0.0)
    return bool(
        min_time_left > 0.0
        and time_left_seconds > 0.0
        and time_left_seconds < min_time_left
        and target_removed_count > 0
        and current_target <= 0
    )


def should_flee_untracked_damage(
    args: argparse.Namespace,
    *,
    current_health_percent: int,
    last_health_percent: int,
    current_target: int,
    flee_until: float,
    now: float,
    party_rescue_target_id: int = 0,
    last_damage_attacker_name: str = "",
    party_ready_for_objective: bool = True,
    force_flee_from_health_drop: bool = False,
) -> bool:
    if current_target or current_health_percent <= 0 or now < flee_until:
        return False

    commit_floor = int(getattr(args, "required_target_tank_commit_health_percent", 0) or 0)
    if (
        commit_floor > 0
        and current_health_percent > commit_floor
        and name_matches_required_target(args, last_damage_attacker_name)
        and party_ready_for_objective
    ):
        return False

    counterattack_floor = int(getattr(args, "flee_melee_counterattack_health_floor", 0) or 0)
    if (
        party_rescue_target_id > 0
        and counterattack_floor > 0
        and current_health_percent > counterattack_floor
        and not force_flee_from_health_drop
    ):
        return False

    threshold = max(
        int(getattr(args, "flee_health_percent", 0) or 0),
        int(getattr(args, "low_health_rest_percent", 0) or 0),
        int(getattr(args, "flee_pressure_health_percent", 0) or 0),
    )
    if threshold <= 0 or current_health_percent > threshold:
        return False

    return last_health_percent > 0 and current_health_percent < last_health_percent


def should_force_flee_from_non_required_health_drop(
    args: argparse.Namespace,
    *,
    current_health_percent: int,
    previous_health_percent: int,
    last_damage_attacker_name: str,
) -> bool:
    if current_health_percent <= 0 or previous_health_percent <= 0:
        return False

    if name_matches_required_target(args, last_damage_attacker_name):
        return False

    pressure_threshold = int(getattr(args, "flee_pressure_health_percent", 0) or 0)
    if pressure_threshold <= 0 or current_health_percent > pressure_threshold:
        return False

    drop_threshold = int(getattr(args, "flee_untracked_health_drop_percent", 15) or 15)
    return previous_health_percent - current_health_percent >= max(1, drop_threshold)


def should_commit_required_target_from_recent_damage(
    args: argparse.Namespace,
    *,
    current_health_percent: int,
    previous_health_percent: int,
    current_target: int,
    last_damage_attacker_name: str,
    party_ready_for_objective: bool = True,
    required_home_hunt_ready: bool = True,
    behavior_state: DummyBehaviorState | str = DummyBehaviorState.HuntObjective,
) -> bool:
    if current_target > 0 or current_health_percent <= 0:
        return False

    if behavior_state_value(behavior_state) == DummyBehaviorState.DropAggroAndRecover.value:
        return False

    if not party_ready_for_objective:
        return False

    if not required_home_hunt_ready:
        return False

    commit_floor = int(getattr(args, "required_target_tank_commit_health_percent", 0) or 0)
    if commit_floor <= 0 or current_health_percent <= commit_floor:
        return False

    if previous_health_percent <= 0 or current_health_percent >= previous_health_percent:
        return False

    return name_matches_required_target(args, last_damage_attacker_name)


def should_overrun_flee_home(args: argparse.Namespace, *, health_percent: int) -> bool:
    if health_percent <= 0:
        return False

    if getattr(args, "flee_home", None) is not None:
        return False

    resume_threshold = int(getattr(args, "low_health_rest_resume_percent", 0) or 0)
    if resume_threshold <= 0:
        return False

    return health_percent < resume_threshold


def should_extend_flee(
    args: argparse.Namespace,
    *,
    health_percent: int,
    flee_until: float,
    now: float,
    flee_destination: MovementDestination | None = None,
    previous_health_percent: int = 0,
    recent_damage_age_seconds: float | None = None,
    active_threat: bool = False,
) -> bool:
    if flee_until <= 0 or now < flee_until:
        return False

    if flee_destination is not None and should_replan_flee_home_after_arrival(
        args,
        flee_destination,
        health_percent=health_percent,
        previous_health_percent=previous_health_percent,
        recent_damage_age_seconds=recent_damage_age_seconds,
        active_threat=active_threat,
    ):
        return True

    if flee_destination is not None and should_replan_flee_safe_after_arrival(
        args,
        flee_destination,
        health_percent=health_percent,
        previous_health_percent=previous_health_percent,
        recent_damage_age_seconds=recent_damage_age_seconds,
        active_threat=active_threat,
    ):
        return True

    if (
        getattr(args, "flee_home", None) is not None
        and flee_destination is not None
        and destination_kind(flee_destination) == "flee-home"
    ):
        return True

    return should_overrun_flee_home(args, health_percent=health_percent)


def should_replan_flee_home_after_arrival(
    args: argparse.Namespace,
    flee_destination: MovementDestination | None,
    *,
    health_percent: int,
    previous_health_percent: int = 0,
    recent_damage_age_seconds: float | None = None,
    active_threat: bool = False,
) -> bool:
    if flee_destination is None or destination_kind(flee_destination) != "flee-home":
        return False

    if health_percent <= 0:
        return False

    if active_threat:
        return True

    damage_grace = max(0.0, float(getattr(args, "flee_safe_replan_damage_grace", 0.0) or 0.0))
    if recent_damage_age_seconds is not None and 0.0 <= recent_damage_age_seconds <= damage_grace:
        return True

    return previous_health_percent > 0 and health_percent < previous_health_percent


def should_replan_flee_safe_after_arrival(
    args: argparse.Namespace,
    flee_destination: MovementDestination | None,
    *,
    health_percent: int,
    previous_health_percent: int = 0,
    recent_damage_age_seconds: float | None = None,
    active_threat: bool = False,
) -> bool:
    if flee_destination is None or destination_kind(flee_destination) != "flee-safe":
        return False

    if health_percent <= 0:
        return False

    resume_threshold = int(getattr(args, "low_health_rest_resume_percent", 0) or 0)
    if resume_threshold <= 0 or health_percent >= resume_threshold:
        return False

    urgent_threshold = max(
        int(getattr(args, "flee_health_percent", 0) or 0),
        int(getattr(args, "flee_critical_health_percent", 0) or 0),
    )
    if active_threat and urgent_threshold > 0 and health_percent <= urgent_threshold:
        return True

    damage_grace = max(0.0, float(getattr(args, "flee_safe_replan_damage_grace", 0.0) or 0.0))
    if recent_damage_age_seconds is not None and 0.0 <= recent_damage_age_seconds <= damage_grace:
        return True

    return previous_health_percent > 0 and health_percent < previous_health_percent


def should_replan_flee_safe_under_pressure(
    args: argparse.Namespace,
    flee_destination: MovementDestination | None,
    *,
    health_percent: int,
    threat_snapshot: dict[str, object] | None,
) -> bool:
    if flee_destination is None or destination_kind(flee_destination) != "flee-safe":
        return False

    if health_percent <= 0:
        return False

    resume_threshold = int(getattr(args, "low_health_rest_resume_percent", 0) or 0)
    if resume_threshold > 0 and health_percent >= resume_threshold:
        return False

    if not flee_threat_snapshot_is_active(threat_snapshot):
        return False

    threat_distance = float((threat_snapshot or {}).get("flee_threat_distance", 0.0) or 0.0)
    pressure_distance = max(1200.0, float(getattr(args, "flee_safe_threat_radius", 0.0) or 0.0) * 0.35)
    if threat_distance > 0.0 and threat_distance <= pressure_distance:
        return True

    critical_threshold = int(getattr(args, "flee_critical_health_percent", 0) or 0)
    return critical_threshold > 0 and health_percent <= critical_threshold


def should_replan_flee_safe_after_recent_damage(
    args: argparse.Namespace,
    flee_destination: MovementDestination | None,
    *,
    health_percent: int,
    recent_damage_age_seconds: float | None,
    damage_seen_at: float,
    last_replanned_damage_at: float,
) -> bool:
    if flee_destination is None or destination_kind(flee_destination) != "flee-safe":
        return False

    if health_percent <= 0 or damage_seen_at <= 0.0 or damage_seen_at <= last_replanned_damage_at:
        return False

    resume_threshold = int(getattr(args, "low_health_rest_resume_percent", 0) or 0)
    if resume_threshold > 0 and health_percent >= resume_threshold:
        return False

    damage_grace = max(0.0, float(getattr(args, "flee_safe_replan_damage_grace", 0.0) or 0.0))
    return recent_damage_age_seconds is not None and 0.0 <= recent_damage_age_seconds <= damage_grace


def flee_home_overrun_destination(
    args: argparse.Namespace,
    client,
    flee_destination: MovementDestination | None,
) -> MovementDestination | None:
    if flee_destination is None or destination_kind(flee_destination) != "flee-home":
        return None

    danger = getattr(args, "required_target_home", None)
    if danger is None:
        return dynamic_flee_safe_destination(args, client)

    origin_x = int(getattr(client, "x", flee_destination.x) or flee_destination.x)
    origin_y = int(getattr(client, "y", flee_destination.y) or flee_destination.y)
    origin_z = int(getattr(client, "z", flee_destination.z) or flee_destination.z)
    dx = origin_x - int(danger.x)
    dy = origin_y - int(danger.y)
    length = math.hypot(dx, dy)
    if length <= 0.0:
        return dynamic_flee_safe_destination(args, client)

    flee_distance = max(
        effective_flee_safe_point_distance(args, client),
        float(getattr(args, "flee_step", 0.0) or 0.0) * 3.0,
        2400.0,
    )
    target_x = int(origin_x + dx / length * flee_distance)
    target_y = int(origin_y + dy / length * flee_distance)
    return destination_from_point("flee-safe", target_x, target_y, origin_z, bucket=100)


def flee_pressure_replan_cooldown(args: argparse.Namespace) -> float:
    flee_duration = max(0.0, float(getattr(args, "flee_duration", 0.0) or 0.0))
    move_interval = max(0.0, float(getattr(args, "flee_move_interval", 0.0) or 0.0))
    return max(8.0, flee_duration * 0.75, move_interval * 12.0)


def flee_destination_stop_distance(args: argparse.Namespace, flee_destination: MovementDestination | None) -> float:
    if flee_destination is not None and destination_kind(flee_destination) == "flee-safe":
        return float(getattr(args, "path_node_arrival_distance", 80.0) or 80.0)

    return float(getattr(args, "flee_home_stop_distance", 900.0) or 900.0)


def should_abort_rest_for_death(*, is_dead: bool, rest_until: float, now: float) -> bool:
    return bool(is_dead) and now < rest_until


def should_refresh_flee_wander_heading(*, now: float, hold_until: float) -> bool:
    return hold_until <= 0.0 or now >= hold_until


def required_target_home_distance(client, args: argparse.Namespace) -> float:
    home = getattr(args, "required_target_home", None)

    if home is None:
        return 0.0

    current = PathPoint(int(client.x), int(client.y), int(client.z))
    goal = PathPoint(int(home.x), int(home.y), int(home.z))
    return horizontal_path_distance(current, goal)


def required_target_home_reached(client, args: argparse.Namespace) -> bool:
    if required_target_home_destination(args) is None:
        return True

    return required_target_home_distance(client, args) <= float(getattr(args, "required_target_home_stop_distance", 0) or 0)


def party_pre_pull_form_up_enabled(args: argparse.Namespace) -> bool:
    return bool(
        int(getattr(args, "party_size", 0) or 0) > 1
        and getattr(args, "party_assist_only", False)
        and int(getattr(args, "party_min_ready", 0) or 0) > 0
        and float(getattr(args, "party_pre_pull_home_stop_distance", 0.0) or 0.0) > 0.0
        and required_target_home_destination(args) is not None
    )


def required_target_home_move_stop_distance(
    args: argparse.Namespace,
    party_state: PartyState | None = None,
    *,
    is_party_leader: bool = False,
    current_target: int = 0,
) -> float:
    base = float(getattr(args, "required_target_home_stop_distance", 0.0) or 0.0)
    pre_pull = float(getattr(args, "party_pre_pull_home_stop_distance", 0.0) or 0.0)
    if (
        pre_pull > base
        and (is_party_leader or party_pre_pull_form_up_enabled(args))
        and current_target <= 0
        and party_state is not None
        and int(getattr(args, "party_min_ready", 0) or 0) > 0
        and not party_ready_for_pull(args, party_state)
    ):
        return pre_pull
    return base


def required_target_home_visible_hunt_target(client, args: argparse.Namespace) -> bool:
    visible_npcs = getattr(client, "visible_npcs", None)
    if not callable(visible_npcs):
        return True

    try:
        npcs = visible_npcs(max_age=getattr(args, "npc_max_age", 60.0), include_peace=should_scan_peace_npcs(args))
    except TypeError:
        npcs = visible_npcs()

    min_level = int(getattr(args, "min_target_level", 0) or 0)
    max_level = int(getattr(args, "max_target_level", 0) or 0)
    if max_level < 0:
        max_level = int(getattr(args, "player_level", 0) or 0) + int(getattr(args, "max_target_level_delta", 0) or 0)

    for npc in npcs:
        if min_level > 0 and int(getattr(npc, "level", 0) or 0) < min_level:
            continue
        if max_level > 0 and int(getattr(npc, "level", 0) or 0) > max_level:
            continue
        if not is_required_target(args, npc):
            continue
        if not target_within_required_home(args, npc):
            continue
        if not target_within_selection_distance(client, args, npc):
            continue
        return True

    return False


def required_target_home_hunt_ready(client, args: argparse.Namespace) -> bool:
    if required_target_home_destination(args) is None:
        return True

    hunt_distance = float(getattr(args, "required_target_home_hunt_distance", 0.0) or 0.0)
    if hunt_distance <= 0.0:
        hunt_distance = float(getattr(args, "target_home_max_distance", 0.0) or 0.0)

    if hunt_distance <= 0.0 or required_target_home_distance(client, args) > hunt_distance:
        return False

    if (
        int(getattr(args, "party_size", 0) or 0) > 1
        and getattr(args, "party_assist_only", False)
        and int(getattr(args, "party_min_ready", 0) or 0) > 0
    ):
        if getattr(args, "hunter_target_api_scout", False):
            return True
        return required_target_home_visible_hunt_target(client, args)

    return True


def should_return_home_before_low_health_rest(client, args: argparse.Namespace) -> bool:
    if required_target_home_destination(args) is None or required_target_home_reached(client, args):
        return False

    home_distance = required_target_home_distance(client, args)
    return_threshold = max(
        float(getattr(args, "required_target_home_stop_distance", 0.0) or 0.0),
        float(getattr(args, "combat_home_leash_distance", 0.0) or 0.0),
        float(getattr(args, "target_home_max_distance", 0.0) or 0.0),
    )
    return return_threshold > 0.0 and home_distance > return_threshold


def should_recover_before_required_target_home(args: argparse.Namespace, *, health_percent: int) -> bool:
    threshold = int(getattr(args, "required_target_recover_before_home_health_percent", 0) or 0)
    return bool(
        threshold > 0
        and health_percent > 0
        and health_percent <= threshold
        and required_target_home_destination(args) is not None
    )


def target_home_leash_violation(client, args: argparse.Namespace, npc) -> tuple[bool, str, float]:
    home = getattr(args, "required_target_home", None)
    leash_distance = float(getattr(args, "combat_home_leash_distance", 0.0) or 0.0)
    if home is None or leash_distance <= 0.0:
        return False, "", 0.0

    player_distance = horizontal_distance_between_points(
        int(getattr(client, "x", 0) or 0),
        int(getattr(client, "y", 0) or 0),
        int(getattr(home, "x", 0) or 0),
        int(getattr(home, "y", 0) or 0),
    )
    if player_distance > leash_distance:
        return True, "player", player_distance

    if npc is None:
        return False, "", player_distance

    target_distance = horizontal_distance_between_points(
        int(getattr(npc, "x", 0) or 0),
        int(getattr(npc, "y", 0) or 0),
        int(getattr(home, "x", 0) or 0),
        int(getattr(home, "y", 0) or 0),
    )
    if target_distance > leash_distance:
        return True, "target", target_distance

    return False, "", max(player_distance, target_distance)


def should_abort_overextended_combat(args: argparse.Namespace, active_combat, distance: float, target_age: float) -> bool:
    max_distance = float(getattr(args, "combat_chase_max_distance", 0.0) or 0.0)
    if max_distance <= 0.0 or distance <= max_distance:
        return False

    grace = max(0.0, float(getattr(args, "combat_chase_max_distance_grace", 3.0) or 0.0))
    if target_age < grace:
        return False

    if active_combat is not None and (
        int(active_combat.get("damage_done", 0) or 0) > 0
        or int(active_combat.get("damage_taken", 0) or 0) > 0
    ):
        return False

    return True


def should_approach_required_target_home(args: argparse.Namespace, *, is_party_leader: bool, current_target: int) -> bool:
    return bool(
        current_target <= 0
        and required_target_home_destination(args) is not None
        and (
            is_party_leader
            or int(getattr(args, "party_size", 0) or 0) == 1
            or party_pre_pull_form_up_enabled(args)
        )
    )


def should_move_to_required_target_home(client, args: argparse.Namespace, *, is_party_leader: bool, current_target: int) -> bool:
    return bool(
        should_approach_required_target_home(args, is_party_leader=is_party_leader, current_target=current_target)
        and not required_target_home_reached(client, args)
    )


def should_defer_required_home_move_for_friendly_cast(
    *,
    is_party_follower: bool,
    action_rotation: str,
    precast_movement_hold: bool,
    friendly_target_pending: bool = False,
) -> bool:
    return bool(
        is_party_follower
        and action_rotation == "healer-support"
        and (precast_movement_hold or friendly_target_pending)
    )


def should_start_rescue_counterattack_combat(active_combat, current_target: int, actor) -> bool:
    return bool(active_combat is None and current_target > 0 and actor is not None)


def should_idle_wander(args: argparse.Namespace, *, is_party_leader: bool, current_target: int) -> bool:
    if should_approach_required_target_home(args, is_party_leader=is_party_leader, current_target=current_target):
        return False
    return bool(getattr(args, "wander", False))


def destination_kind(destination: MovementDestination) -> str:
    return destination.key.split(":", 1)[0]


def horizontal_path_distance(left: PathPoint, right: PathPoint) -> float:
    return ((left.x - right.x) ** 2 + (left.y - right.y) ** 2) ** 0.5


def resolved_goal_for_destination(path_state: PathMovementState, destination: MovementDestination, fallback: object) -> object:
    if path_state.destination_key == destination.key and path_state.resolved_goal is not None:
        return path_state.resolved_goal

    return fallback


def should_force_nav_route(args: argparse.Namespace, destination: MovementDestination) -> bool:
    if not args.nav_api_url:
        return False

    return destination_kind(destination) in {"target", "follow-player", "party-leader"}


def should_use_direct_flee_safe_move(args: argparse.Namespace, destination: MovementDestination, distance: float) -> bool:
    if destination_kind(destination) != "flee-safe":
        return False

    safe_point_distance = float(getattr(args, "flee_safe_point_distance", 0.0) or 0.0)
    critical_distance = float(getattr(args, "flee_critical_safe_point_distance", 0.0) or 0.0)
    safe_point_distance = max(safe_point_distance, critical_distance)
    max_direct_distance = max(safe_point_distance * 1.5, float(getattr(args, "path_last_mile_distance", 0.0) or 0.0))
    return max_direct_distance <= 0.0 or distance <= max_direct_distance


def destination_allows_offgraph_rejoin(destination: MovementDestination) -> bool:
    return destination_kind(destination) in {
        "required-target-home",
        "flee-home",
        "waypoint",
        "party-target-last-known",
    }


def should_attempt_offgraph_rejoin(
    path_state: PathMovementState,
    destination: MovementDestination,
    nav_fallback_reason: str,
) -> bool:
    if path_state.last_reason == "no nearby start graph node":
        return True

    if not destination_allows_offgraph_rejoin(destination):
        return False

    return bool(
        graph_can_fallback_from_nav_failure(path_state, nav_fallback_reason)
        or path_state.last_reason not in {"", "PathFound"}
    )


def expanded_graph_rejoin_distance(args: argparse.Namespace) -> float:
    return max(
        float(getattr(args, "path_max_node_distance", 0.0) or 0.0),
        float(getattr(args, "path_last_mile_distance", 0.0) or 0.0),
        float(getattr(args, "path_max_edge_length", 0.0) or 0.0) * 2.0,
        float(getattr(args, "flee_safe_point_distance", 0.0) or 0.0) * 1.5,
        float(getattr(args, "flee_critical_safe_point_distance", 0.0) or 0.0),
    )


def graph_rejoin_point_after_offgraph_flee(
    args: argparse.Namespace,
    path_state: PathMovementState,
    current: PathPoint,
    goal: PathPoint | None = None,
) -> PathPoint | None:
    graph = path_state.graph
    if graph is None:
        return None

    normal_distance = float(getattr(args, "path_max_node_distance", 0.0) or 0.0)
    expanded_distance = expanded_graph_rejoin_distance(args)
    if expanded_distance <= normal_distance:
        return None

    safety_options = [
        path_state.safety,
        replace(
            path_state.safety,
            max_direct_distance=max(path_state.safety.max_direct_distance, expanded_distance),
            max_height_delta=max(path_state.safety.max_height_delta, int(expanded_distance)),
        ),
    ]
    current_goal_distance = horizontal_path_distance(current, goal) if goal is not None else 0.0
    progress_margin = max(float(getattr(args, "path_node_arrival_distance", 0.0) or 0.0), 1.0)

    for safety in safety_options:
        candidates = [
            node
            for node in graph.nodes.values()
            if node.region == path_state.region
            and abs(node.z - current.z) <= safety.max_height_delta
            and graph.node_allowed(node, safety)
        ]
        candidates.sort(key=lambda node: path_distance(current, node.point))

        for node in candidates:
            node_distance = path_distance(current, node.point)
            if node_distance > expanded_distance:
                break
            if node_distance <= normal_distance:
                continue
            if goal is not None and horizontal_path_distance(node.point, goal) >= current_goal_distance - progress_margin:
                continue
            if graph.direct_path_allowed(
                path_state.region,
                current,
                node.point,
                safety,
                max_distance=expanded_distance,
            ):
                return node.point

    return None


def can_rejoin_first_graph_step(
    args: argparse.Namespace,
    path_state: PathMovementState,
    current: PathPoint,
    next_point: PathPoint,
) -> bool:
    if getattr(path_state.follower, "index", 0) != 0:
        return False

    max_distance = expanded_graph_rejoin_distance(args)
    normal_edge = float(getattr(args, "path_max_edge_length", 0.0) or 0.0)
    if max_distance <= normal_edge:
        return False

    return direct_path_allowed_for_state(path_state, current, next_point, max_distance)


def graph_route_edge_allows_reached_transition(
    path_state: PathMovementState,
    current: PathPoint,
    arrival_distance: float,
    waypoint_z_skip_delta: float = 80.0,
) -> bool:
    graph = path_state.graph
    route = getattr(path_state.follower, "route", [])
    index = int(getattr(path_state.follower, "index", 0) or 0)
    if graph is None or index <= 0 or index >= len(route):
        return False

    previous_node = route[index - 1]
    next_node = route[index]
    if not all(hasattr(node, "id") and hasattr(node, "point") for node in (previous_node, next_node)):
        return False

    previous_point = previous_node.point
    reached_previous = path_distance(current, previous_point) <= arrival_distance
    reached_previous_xy_with_stale_z = (
        horizontal_path_distance(current, previous_point) <= arrival_distance
        and abs(int(current.z) - int(previous_point.z)) <= int(waypoint_z_skip_delta)
    )
    if not reached_previous and not reached_previous_xy_with_stale_z:
        return False

    for edge in getattr(graph, "edges", {}).get(previous_node.id, []):
        if getattr(edge, "to", None) == next_node.id and graph.edge_allowed(previous_node.id, edge, path_state.safety):
            return True

    return False


def move_towards_destination(
    client,
    destination: MovementDestination,
    *,
    step: float,
    stop_distance: float,
    args: argparse.Namespace,
    path_state: PathMovementState,
    action_counts: dict[str, int],
    target_in_view: bool = False,
    retry_after_block: bool = False,
    movement_speed: float | None = None,
) -> MovementOutcome:
    def trace_path(event: str, **fields) -> None:
        trace = getattr(client, "trace_movement", None)

        if callable(trace):
            trace(event, **fields)

    def try_party_anchor_direct_fallback(current_point: PathPoint, goal_point: PathPoint, reason: str) -> MovementOutcome | None:
        if destination_kind(destination) != "party-anchor":
            return None

        party_direct_limit = max(
            float(getattr(args, "party_follow_step", step) or step) * 64.0,
            float(getattr(args, "path_max_node_distance", 0.0) or 0.0) * 2.0,
            float(getattr(args, "path_last_mile_distance", 0.0) or 0.0),
        )
        if horizontal_path_distance(current_point, goal_point) > party_direct_limit:
            return None

        moved = client.move_towards_position(
            goal_point.x,
            goal_point.y,
            goal_point.z,
            step=step,
            stop_distance=stop_distance,
            movement_speed=packet_movement_speed,
            min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
            target_in_view=target_in_view,
        )
        path_state.follower.clear()
        path_state.destination_key = ""
        path_state.resolved_goal = None
        path_state.last_plan_at = 0.0
        actions = add_action(action_counts, "path_party_anchor_direct_fallback" if moved else "path_arrived")
        trace_path(
            "path_party_anchor_direct_fallback",
            destination=destination.key,
            start_x=current_point.x,
            start_y=current_point.y,
            start_z=current_point.z,
            goal_x=goal_point.x,
            goal_y=goal_point.y,
            goal_z=goal_point.z,
            reason=reason,
            moved=int(moved),
        )
        return MovementOutcome(moved=moved, arrived=not moved, actions=actions)

    packet_movement_speed = movement_speed if movement_speed is not None else getattr(args, "movement_speed", None)

    if path_state.graph is None and path_state.client_grid is None and not args.nav_api_url:
        moved = client.move_towards_position(
            destination.x,
            destination.y,
            destination.z,
            step=step,
            stop_distance=stop_distance,
            movement_speed=packet_movement_speed,
            min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
            target_in_view=target_in_view,
        )
        return MovementOutcome(moved=moved, arrived=not moved)

    graph = path_state.graph
    safety = path_state.safety
    current = PathPoint(int(client.x), int(client.y), int(client.z))
    goal = PathPoint(destination.x, destination.y, destination.z)
    effective_goal = resolved_goal_for_destination(path_state, destination, goal)
    if destination_kind(destination) == "party-anchor":
        effective_goal = goal
    direct_distance = path_distance(current, effective_goal)
    actions = 0
    force_nav_route = should_force_nav_route(args, destination)

    if direct_distance <= stop_distance:
        client.move_towards_position(
            effective_goal.x,
            effective_goal.y,
            effective_goal.z,
            step=0.0,
            stop_distance=stop_distance,
            min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
            target_in_view=target_in_view,
        )
        actions += add_action(action_counts, "path_arrived")
        return MovementOutcome(moved=False, arrived=True, actions=actions)

    if destination_kind(destination) == "startup-teleporter-home":
        path_state.follower.clear()
        path_state.destination_key = destination.key
        path_state.resolved_goal = goal
        moved = client.move_towards_position(
            goal.x,
            goal.y,
            goal.z,
            step=step,
            stop_distance=stop_distance,
            movement_speed=packet_movement_speed,
            min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
            target_in_view=target_in_view,
        )
        actions += add_action(action_counts, "startup_teleporter_home_direct_move" if moved else "path_arrived")
        trace_path(
            "startup_teleporter_home_direct_move",
            destination=destination.key,
            start_x=current.x,
            start_y=current.y,
            start_z=current.z,
            goal_x=goal.x,
            goal_y=goal.y,
            goal_z=goal.z,
            moved=int(moved),
        )
        return MovementOutcome(moved=moved, arrived=not moved, actions=actions)

    if should_use_direct_flee_safe_move(args, destination, direct_distance):
        path_state.follower.clear()
        path_state.destination_key = destination.key
        path_state.resolved_goal = goal
        moved = client.move_towards_position(
            goal.x,
            goal.y,
            goal.z,
            step=step,
            stop_distance=stop_distance,
            movement_speed=packet_movement_speed,
            min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
            target_in_view=target_in_view,
        )
        actions += add_action(action_counts, "flee_safe_direct_move" if moved else "path_arrived")
        trace_path(
            "flee_safe_direct_move",
            destination=destination.key,
            start_x=current.x,
            start_y=current.y,
            start_z=current.z,
            goal_x=goal.x,
            goal_y=goal.y,
            goal_z=goal.z,
            moved=int(moved),
        )
        return MovementOutcome(moved=moved, arrived=not moved, actions=actions)

    if not force_nav_route and direct_path_allowed_for_state(path_state, current, effective_goal, args.path_last_mile_distance):
        segment_ok, segment_reason = nav_segment_allowed(args, path_state.region, current, effective_goal, path_state)

        if not segment_ok and not graph_can_fallback_from_nav_failure(path_state, segment_reason):
            client.send_position_update(speed=0.0, target_in_view=target_in_view)
            actions += add_action(action_counts, "nav_segment_blocked")
            return MovementOutcome(moved=False, arrived=False, actions=actions, reason=segment_reason)

        moved = client.move_towards_position(
            effective_goal.x,
            effective_goal.y,
            effective_goal.z,
            step=step,
            stop_distance=stop_distance,
            movement_speed=packet_movement_speed,
            min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
            target_in_view=target_in_view,
        )
        actions += add_action(action_counts, "path_last_mile" if moved else "path_arrived")
        return MovementOutcome(moved=moved, arrived=not moved, actions=actions)

    destination_changed = path_state.destination_key != destination.key
    if destination_changed:
        path_state.follower.clear()
        path_state.resolved_goal = None

    needs_plan = (
        destination_changed
        or not getattr(path_state.follower, "route", [])
    )

    if needs_plan:
        now = time.monotonic()
        nav_fallback_reason = ""

        if (
            path_state.destination_key == destination.key
            and not getattr(path_state.follower, "route", [])
            and path_state.last_plan_at > 0
            and now - path_state.last_plan_at < args.path_replan_interval
        ):
            client.send_position_update(speed=0.0, target_in_view=target_in_view)
            actions += add_action(action_counts, "path_replan_wait")
            return MovementOutcome(moved=False, arrived=False, actions=actions, reason=path_state.last_reason)

        path_state.destination_key = destination.key
        path_state.last_plan_at = now
        path_state.resolved_goal = None

        if should_request_nav_path(args, path_state):
            nav_result = request_nav_path(args, path_state.region, current, goal)
            path_state.last_reason = nav_result.status

            if nav_result.ok:
                path_state.follower.set_route(nav_result.points)
                if nav_result.snapped_end is not None:
                    path_state.resolved_goal = nav_result.snapped_end
                elif nav_result.points:
                    path_state.resolved_goal = nav_result.points[-1]
                actions += add_action(action_counts, "nav_path_plan")
                trace_path(
                    "path_plan",
                    source="nav_api",
                    destination=destination.key,
                    start_x=current.x,
                    start_y=current.y,
                    start_z=current.z,
                    goal_x=goal.x,
                    goal_y=goal.y,
                    goal_z=goal.z,
                    status=nav_result.status,
                    points=len(nav_result.points),
                )
            else:
                actions += add_action(action_counts, "nav_path_failed")
                nav_fallback_reason = nav_result.status
                remember_nav_path_failure(path_state, nav_result.status)
                trace_path(
                    "path_plan_failed",
                    source="nav_api",
                    destination=destination.key,
                    start_x=current.x,
                    start_y=current.y,
                    start_z=current.z,
                    goal_x=goal.x,
                    goal_y=goal.y,
                    goal_z=goal.z,
                    status=nav_result.status,
                )
        elif args.nav_api_url:
            path_state.last_reason = "NavmeshUnavailableCached"

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
                final_node = route.nodes[-1]
                path_state.resolved_goal = final_node.point if hasattr(final_node, "point") else final_node
                actions += add_action(action_counts, "path_plan")
                trace_path(
                    "path_plan",
                    source="path_graph",
                    destination=destination.key,
                    start_x=current.x,
                    start_y=current.y,
                    start_z=current.z,
                    goal_x=goal.x,
                    goal_y=goal.y,
                    goal_z=goal.z,
                    status=route.reason or "PathFound",
                    points=len(route.nodes),
                )

        if not getattr(path_state.follower, "route", []) and path_state.client_grid is not None:
            route = path_state.client_grid.find_path(path_state.region, current.x, current.y, goal.x, goal.y)
            path_state.last_reason = route.status

            if route.ok:
                path_state.follower.set_route(route.points)
                if route.points:
                    path_state.resolved_goal = route.points[-1]
                actions += add_action(action_counts, "client_grid_path_plan")
                trace_path(
                    "path_plan",
                    source="client_grid",
                    destination=destination.key,
                    start_x=current.x,
                    start_y=current.y,
                    start_z=current.z,
                    goal_x=goal.x,
                    goal_y=goal.y,
                    goal_z=goal.z,
                    status=route.status,
                    points=len(route.points),
                    visited=getattr(route, "visited", 0),
                )

        if not getattr(path_state.follower, "route", []):
            can_direct_return_after_nav_failure = (
                destination_kind(destination) in {"required-target-home", "flee-home"}
                and (
                    graph_can_fallback_from_nav_failure(path_state, nav_fallback_reason)
                    or path_state.last_reason not in {"", "PathFound"}
                )
            )
            if should_attempt_offgraph_rejoin(path_state, destination, nav_fallback_reason):
                rejoin_point = graph_rejoin_point_after_offgraph_flee(args, path_state, current, goal)
                if rejoin_point is not None:
                    moved = client.move_towards_position(
                        rejoin_point.x,
                        rejoin_point.y,
                        rejoin_point.z,
                        step=step,
                        stop_distance=args.path_node_arrival_distance,
                        movement_speed=packet_movement_speed,
                        min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                        target_in_view=target_in_view,
                    )
                    path_state.follower.clear()
                    path_state.destination_key = ""
                    path_state.resolved_goal = None
                    path_state.last_plan_at = 0.0
                    actions += add_action(action_counts, "path_rejoin_graph" if moved else "path_rejoin_graph_hold")
                    trace_path(
                        "path_rejoin_graph",
                        destination=destination.key,
                        start_x=current.x,
                        start_y=current.y,
                        start_z=current.z,
                        goal_x=goal.x,
                        goal_y=goal.y,
                        goal_z=goal.z,
                        rejoin_x=rejoin_point.x,
                        rejoin_y=rejoin_point.y,
                        rejoin_z=rejoin_point.z,
                        moved=int(moved),
                    )
                    return MovementOutcome(moved=moved, arrived=False, actions=actions)

                if destination_kind(destination) in {"required-target-home", "flee-home"}:
                    moved = client.move_towards_position(
                        goal.x,
                        goal.y,
                        goal.z,
                        step=step,
                        stop_distance=stop_distance,
                        movement_speed=packet_movement_speed,
                        min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                        target_in_view=target_in_view,
                    )
                    path_state.follower.clear()
                    path_state.destination_key = ""
                    path_state.resolved_goal = None
                    path_state.last_plan_at = 0.0
                    actions += add_action(action_counts, "path_offgraph_return_move" if moved else "path_arrived")
                    trace_path(
                        "path_offgraph_return_move",
                        destination=destination.key,
                        start_x=current.x,
                        start_y=current.y,
                        start_z=current.z,
                        goal_x=goal.x,
                        goal_y=goal.y,
                        goal_z=goal.z,
                        moved=int(moved),
                    )
                    return MovementOutcome(moved=moved, arrived=not moved, actions=actions)

            if (
                force_nav_route
                and graph_can_fallback_from_nav_failure(path_state, nav_fallback_reason)
                and direct_path_allowed_for_state(path_state, current, goal, args.path_last_mile_distance)
            ):
                moved = client.move_towards_position(
                    goal.x,
                    goal.y,
                    goal.z,
                    step=step,
                    stop_distance=stop_distance,
                    movement_speed=packet_movement_speed,
                    min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                    target_in_view=target_in_view,
                )
                actions += add_action(action_counts, "path_direct_fallback" if moved else "path_arrived")
                trace_path(
                    "path_direct_fallback",
                    destination=destination.key,
                    start_x=current.x,
                    start_y=current.y,
                    start_z=current.z,
                    goal_x=goal.x,
                    goal_y=goal.y,
                    goal_z=goal.z,
                    reason=nav_fallback_reason,
                    moved=int(moved),
                )
                return MovementOutcome(moved=moved, arrived=not moved, actions=actions)

            party_anchor_fallback = try_party_anchor_direct_fallback(current, goal, path_state.last_reason)
            if party_anchor_fallback is not None:
                return replace(party_anchor_fallback, actions=actions + party_anchor_fallback.actions)

            path_state.follower.clear()
            path_state.resolved_goal = None
            client.send_position_update(speed=0.0, target_in_view=target_in_view)
            actions += add_action(action_counts, "path_failed")
            trace_path(
                "path_failed",
                destination=destination.key,
                start_x=current.x,
                start_y=current.y,
                start_z=current.z,
                goal_x=goal.x,
                goal_y=goal.y,
                goal_z=goal.z,
                reason=path_state.last_reason,
            )
            return MovementOutcome(moved=False, arrived=False, actions=actions, reason=path_state.last_reason)

    next_point = path_state.follower.next_point(current, args.path_node_arrival_distance)
    while (
        next_point is not None
        and horizontal_path_distance(current, next_point) <= args.path_node_arrival_distance
        and path_distance(current, next_point) > args.path_node_arrival_distance
        and abs(int(current.z) - int(next_point.z)) <= int(getattr(args, "path_waypoint_ground_z_skip_delta", 80))
    ):
        trace_path(
            "path_waypoint_ground_z_skip",
            destination=destination.key,
            next_x=int(next_point.x),
            next_y=int(next_point.y),
            next_z=int(next_point.z),
            current_x=current.x,
            current_y=current.y,
            current_z=current.z,
            follower_index=getattr(path_state.follower, "index", 0),
            route_points=len(getattr(path_state.follower, "route", [])),
        )
        path_state.follower.index += 1
        actions += add_action(action_counts, "path_waypoint_ground_z_skip")
        next_point = path_state.follower.next_point(current, args.path_node_arrival_distance)

    if next_point is None:
        effective_goal = resolved_goal_for_destination(path_state, destination, goal)
        if destination_kind(destination) == "party-anchor":
            effective_goal = goal

        if direct_path_allowed_for_state(path_state, current, effective_goal, args.path_last_mile_distance):
            segment_ok, segment_reason = nav_segment_allowed(args, path_state.region, current, effective_goal)

            if not segment_ok and not graph_can_fallback_from_nav_failure(path_state, segment_reason):
                path_state.destination_key = ""
                path_state.resolved_goal = None
                path_state.last_reason = segment_reason
                client.send_position_update(speed=0.0, target_in_view=target_in_view)
                actions += add_action(action_counts, "nav_segment_blocked")
                return MovementOutcome(moved=False, arrived=False, actions=actions, reason=segment_reason)

            moved = client.move_towards_position(
                effective_goal.x,
                effective_goal.y,
                effective_goal.z,
                step=step,
                stop_distance=stop_distance,
                movement_speed=packet_movement_speed,
                min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                target_in_view=target_in_view,
            )
            actions += add_action(action_counts, "path_last_mile" if moved else "path_arrived")
            return MovementOutcome(moved=moved, arrived=not moved, actions=actions)

        path_state.follower.clear()
        path_state.destination_key = ""
        path_state.resolved_goal = None
        party_anchor_fallback = try_party_anchor_direct_fallback(current, goal, "route ended before last mile")
        if party_anchor_fallback is not None:
            return replace(party_anchor_fallback, actions=actions + party_anchor_fallback.actions)
        client.send_position_update(speed=0.0, target_in_view=target_in_view)
        actions += add_action(action_counts, "path_hold")
        return MovementOutcome(moved=False, arrived=False, actions=actions, reason="route ended before last mile")

    if not direct_path_allowed_for_state(path_state, current, next_point, args.path_max_edge_length):
        if graph_route_edge_allows_reached_transition(
            path_state,
            current,
            args.path_node_arrival_distance,
            getattr(args, "path_waypoint_ground_z_skip_delta", 80),
        ):
            moved = client.move_towards_position(
                next_point.x,
                next_point.y,
                next_point.z,
                step=step,
                stop_distance=0.0,
                movement_speed=packet_movement_speed,
                min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                target_in_view=target_in_view,
            )
            trace_path(
                "path_step_target",
                destination=destination.key,
                next_x=int(next_point.x),
                next_y=int(next_point.y),
                next_z=int(next_point.z),
                current_x=current.x,
                current_y=current.y,
                current_z=current.z,
                moved=int(moved),
                follower_index=getattr(path_state.follower, "index", 0),
                route_points=len(getattr(path_state.follower, "route", [])),
                edge_height_override=1,
            )
            actions += add_action(action_counts, "path_step" if moved else "path_waypoint_reached")
            return MovementOutcome(moved=moved, arrived=False, actions=actions)

        if can_rejoin_first_graph_step(args, path_state, current, next_point):
            moved = client.move_towards_position(
                next_point.x,
                next_point.y,
                next_point.z,
                step=step,
                stop_distance=args.path_node_arrival_distance,
                movement_speed=packet_movement_speed,
                min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                target_in_view=target_in_view,
            )
            actions += add_action(action_counts, "path_rejoin_graph" if moved else "path_rejoin_graph_hold")
            trace_path(
                "path_rejoin_graph",
                destination=destination.key,
                start_x=current.x,
                start_y=current.y,
                start_z=current.z,
                rejoin_x=int(next_point.x),
                rejoin_y=int(next_point.y),
                rejoin_z=int(next_point.z),
                moved=int(moved),
                follower_index=getattr(path_state.follower, "index", 0),
                route_points=len(getattr(path_state.follower, "route", [])),
            )
            return MovementOutcome(moved=moved, arrived=False, actions=actions)

        path_state.follower.clear()
        path_state.destination_key = ""
        path_state.resolved_goal = None
        actions += add_action(action_counts, "path_blocked")

        if not retry_after_block:
            retry_outcome = move_towards_destination(
                client,
                destination,
                step=step,
                stop_distance=stop_distance,
                args=args,
                path_state=path_state,
                action_counts=action_counts,
                target_in_view=target_in_view,
                retry_after_block=True,
            )
            return replace(retry_outcome, actions=actions + retry_outcome.actions)

        client.send_position_update(speed=0.0, target_in_view=target_in_view)
        return MovementOutcome(moved=False, arrived=False, actions=actions, reason="next graph step failed safety check")

    segment_ok, segment_reason = nav_segment_allowed(args, path_state.region, current, next_point, path_state)

    if not segment_ok and not graph_can_fallback_from_nav_failure(path_state, segment_reason):
        path_state.follower.clear()
        path_state.destination_key = ""
        path_state.resolved_goal = None
        path_state.last_reason = segment_reason
        client.send_position_update(speed=0.0, target_in_view=target_in_view)
        actions += add_action(action_counts, "nav_segment_blocked")
        return MovementOutcome(moved=False, arrived=False, actions=actions, reason=segment_reason)

    moved = client.move_towards_position(
        next_point.x,
        next_point.y,
        next_point.z,
        step=step,
        stop_distance=0.0,
        movement_speed=packet_movement_speed,
        min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
        target_in_view=target_in_view,
    )
    if not moved and horizontal_path_distance(current, next_point) <= args.path_node_arrival_distance:
        path_state.follower.index += 1
        actions += add_action(action_counts, "path_waypoint_xy_reached")
        trace_path(
            "path_waypoint_xy_reached",
            destination=destination.key,
            next_x=int(next_point.x),
            next_y=int(next_point.y),
            next_z=int(next_point.z),
            current_x=current.x,
            current_y=current.y,
            current_z=current.z,
            follower_index=getattr(path_state.follower, "index", 0),
            route_points=len(getattr(path_state.follower, "route", [])),
        )
        return MovementOutcome(moved=True, arrived=False, actions=actions)

    trace_path(
        "path_step_target",
        destination=destination.key,
        next_x=int(next_point.x),
        next_y=int(next_point.y),
        next_z=int(next_point.z),
        current_x=current.x,
        current_y=current.y,
        current_z=current.z,
        moved=int(moved),
        follower_index=getattr(path_state.follower, "index", 0),
        route_points=len(getattr(path_state.follower, "route", [])),
    )
    actions += add_action(action_counts, "path_step" if moved else "path_waypoint_reached")
    return MovementOutcome(moved=moved, arrived=False, actions=actions)


def move_towards_flee_destination(
    client,
    args: argparse.Namespace,
    path_state: PathMovementState,
    action_counts: dict[str, int],
    flee_destination: MovementDestination,
) -> tuple[MovementOutcome, int]:
    outcome = move_towards_destination(
        client,
        flee_destination,
        step=float(getattr(args, "flee_step", 0.0) or 0.0),
        stop_distance=flee_destination_stop_distance(args, flee_destination),
        args=args,
        path_state=path_state,
        action_counts=action_counts,
        movement_speed=getattr(args, "flee_movement_speed", None),
    )
    actions = outcome.actions
    actions += add_action(action_counts, "flee_home_move" if outcome.moved else "flee_home_hold")
    return outcome, actions


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


def normalize_destination_name(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def format_whisper_argument(value: str) -> str:
    message = str(value or "").strip()
    if any(char.isspace() for char in message) and not (message.startswith('"') and message.endswith('"')):
        return '"' + message.replace('"', "") + '"'
    return message


def startup_teleport_approach_timeout(args: argparse.Namespace, client, target, approach_distance: float) -> float:
    configured_timeout = max(0.0, float(getattr(args, "startup_teleport_approach_timeout", 0.0) or 0.0))
    current_distance = max(0.0, float(client.distance_to(target)))
    remaining_distance = max(0.0, current_distance - max(0.0, approach_distance))
    if remaining_distance <= 0.0:
        return configured_timeout

    movement_speed = float(
        getattr(args, "movement_speed", None)
        or getattr(args, "move_step", None)
        or DEFAULT_PLAYER_MOVEMENT_SPEED
        or 1.0
    )
    movement_speed = max(1.0, movement_speed)
    estimated_seconds = (remaining_distance / movement_speed) * 1.5 + 5.0
    return max(configured_timeout, estimated_seconds)


def startup_teleporter_home_search_stop_distance(args: argparse.Namespace) -> float:
    home_stop = max(0.0, float(getattr(args, "startup_teleporter_home_stop_distance", 0.0) or 0.0))
    approach_stop = max(0.0, float(getattr(args, "startup_teleport_approach_distance", 0.0) or 0.0))
    if home_stop > 0.0 and approach_stop > 0.0:
        return min(home_stop, approach_stop)
    return home_stop


def startup_teleporter_home_timeout(args: argparse.Namespace, client, teleporter_home) -> float:
    configured_timeout = max(0.0, float(getattr(args, "startup_teleporter_home_timeout", 0.0) or 0.0))
    if teleporter_home is None:
        return configured_timeout

    current_distance = max(0.0, float(client.distance_to(teleporter_home)))
    remaining_distance = max(0.0, current_distance - startup_teleporter_home_search_stop_distance(args))
    if remaining_distance <= 0.0:
        return configured_timeout

    movement_speed = float(
        getattr(args, "movement_speed", None)
        or getattr(args, "move_step", None)
        or DEFAULT_PLAYER_MOVEMENT_SPEED
        or 1.0
    )
    movement_speed = max(1.0, movement_speed)
    estimated_seconds = (remaining_distance / movement_speed) * 3.0 + 15.0
    return max(configured_timeout, estimated_seconds)


def startup_teleport_confirmed(client, teleport_destination: str) -> bool:
    destination = normalize_destination_name(teleport_destination)
    if not destination:
        return False

    failure_markers = ("too far", "너무 멀", "멀리 떨어져", "cannot teleport", "can't teleport")
    success_markers = ("teleport", "순간이동", "이동시켜")
    for message in getattr(client, "messages", []) or []:
        text = str(getattr(message, "text", "") or "")
        normalized_text = normalize_destination_name(text)
        if destination not in normalized_text:
            continue
        if any(marker in normalized_text for marker in failure_markers):
            continue
        if any(marker in normalized_text for marker in success_markers):
            return True
    return False


def client_zone_id_for_world_position(ground_z_map: str, x: int, y: int) -> int | None:
    if not ground_z_map:
        return None

    map_path = resolve_path_graph_path(ground_z_map)
    cache_key = str(map_path.resolve()) if map_path.exists() else str(map_path)
    with CLIENT_ZONE_ID_CACHE_LOCK:
        if cache_key not in CLIENT_ZONE_ID_CACHE:
            try:
                payload = json.loads(map_path.read_text(encoding="utf-8"))
            except OSError:
                CLIENT_ZONE_ID_CACHE[cache_key] = []
            else:
                zones: list[tuple[int, int, int, int, int]] = []
                if str(payload.get("type", "")).lower() == "daoc-client-zone-mpk":
                    for zone_key, zone_payload in payload.get("zones", {}).items():
                        zone_id = int(zone_key)
                        world_x = int(zone_payload["offset_x"]) * daoc_zone_heightmap.ZONE_TILE_SIZE
                        world_y = int(zone_payload["offset_y"]) * daoc_zone_heightmap.ZONE_TILE_SIZE
                        width = int(zone_payload.get("width", 8)) * daoc_zone_heightmap.ZONE_TILE_SIZE
                        height = int(zone_payload.get("height", 8)) * daoc_zone_heightmap.ZONE_TILE_SIZE
                        zones.append((zone_id, world_x, world_y, width, height))
                CLIENT_ZONE_ID_CACHE[cache_key] = zones
        zones = list(CLIENT_ZONE_ID_CACHE[cache_key])

    for zone_id, world_x, world_y, width, height in zones:
        if world_x <= x <= world_x + width and world_y <= y <= world_y + height:
            return zone_id
    return None


def sync_startup_teleport_position(
    client,
    teleport_destination: str,
    action_counts: dict[str, int],
    args: argparse.Namespace | None = None,
) -> int:
    coords = TELEPORT_DESTINATION_COORDS.get(normalize_destination_name(teleport_destination))
    if coords is None or not startup_teleport_confirmed(client, teleport_destination):
        return 0

    zone_id, x, y, z = coords
    resolved_zone_id = client_zone_id_for_world_position(str(getattr(args, "ground_z_map", "") or ""), x, y) if args else None
    if resolved_zone_id is not None:
        zone_id = resolved_zone_id
    client.zone_id = int(zone_id)
    client.x = int(x)
    client.y = int(y)
    client.z = int(z)
    if hasattr(client, "trace_movement"):
        client.trace_movement(
            "startup_teleport_sync",
            destination=teleport_destination,
            zone_id=int(zone_id),
            x=int(x),
            y=int(y),
            z=int(z),
        )
    if hasattr(client, "send_position_update"):
        client.send_position_update(speed=0.0, target_in_view=False)
    return add_action(action_counts, "startup_teleport_sync")


def run_startup_service_actions(
    client,
    args: argparse.Namespace,
    action_counts: dict[str, int],
    path_state: PathMovementState | None = None,
    movement_failures: list[MovementFailure] | None = None,
) -> int:
    actions = 0
    name_tokens = [
        token.strip().lower()
        for token in getattr(args, "startup_service_npc_name", "").split(",")
        if token.strip()
    ]

    if name_tokens:
        scan_seconds = max(0.0, float(getattr(args, "startup_service_scan_seconds", 0.0) or 0.0))
        if scan_seconds:
            client.read_packets_for(scan_seconds)

        candidates = []
        for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=True):
            npc_name = str(getattr(npc, "name", "") or "").lower()
            if any(token in npc_name for token in name_tokens):
                candidates.append(npc)

        if candidates:
            target = min(candidates, key=client.distance_to)
            client.target_object(target.object_id)
            actions += add_action(action_counts, "startup_service_target")

            if getattr(args, "startup_service_interact", False):
                client.interact_object(target.object_id)
                actions += add_action(action_counts, "startup_service_interact")
        else:
            actions += add_action(action_counts, "startup_service_npc_missing")

    for slot in flatten_int_groups(getattr(args, "startup_service_buy_slot", [])):
        client.buy_item(slot, count=getattr(args, "startup_service_buy_count", 1))
        actions += add_action(action_counts, "startup_service_buy")

    for slot in flatten_int_groups(getattr(args, "startup_service_sell_slot", [])):
        client.sell_item(slot)
        actions += add_action(action_counts, "startup_service_sell")

    for slot in flatten_int_groups(getattr(args, "startup_service_equip_slot", [])):
        client.move_item(from_slot=slot, to_slot=100, count=1)
        actions += add_action(action_counts, "startup_service_equip")

    if getattr(args, "startup_service_accept_dialog", False):
        client.accept_custom_dialog()
        actions += add_action(action_counts, "startup_service_accept_dialog")

    teleport_destination = str(getattr(args, "startup_teleport_destination", "") or "").strip()
    if teleport_destination:
        teleporter_tokens = [
            token.strip().lower()
            for token in getattr(args, "startup_teleporter_npc_name", "").split(",")
            if token.strip()
        ]

        def scan_teleporter_candidates() -> list[object]:
            return [
                npc
                for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=True)
                if not teleporter_tokens
                or any(token in str(getattr(npc, "name", "") or "").lower() for token in teleporter_tokens)
            ]

        scan_seconds = max(0.0, float(getattr(args, "startup_teleport_scan_seconds", 0.0) or 0.0))
        if scan_seconds:
            client.read_packets_for(scan_seconds)

        candidates = scan_teleporter_candidates()
        teleporter_home = getattr(args, "startup_teleporter_home", None)
        if not candidates and teleporter_home is not None and path_state is not None:
            destination = destination_from_point(
                "startup-teleporter-home",
                int(teleporter_home.x),
                int(teleporter_home.y),
                int(teleporter_home.z),
            )
            stop_distance = startup_teleporter_home_search_stop_distance(args)
            deadline = time.monotonic() + startup_teleporter_home_timeout(args, client, teleporter_home)
            while time.monotonic() < deadline:
                client.read_packets_for(max(0.0, float(getattr(args, "smooth_move_interval", 0.2) or 0.2)))
                candidates = scan_teleporter_candidates()
                if candidates:
                    break
                if client.distance_to(teleporter_home) <= stop_distance:
                    actions += add_action(action_counts, "startup_teleporter_home_wait")
                    break
                outcome = move_towards_destination(
                    client,
                    destination,
                    step=smooth_movement_step(args) if getattr(args, "smooth_movement", False) else getattr(args, "move_step", 260.0),
                    stop_distance=stop_distance,
                    args=args,
                    path_state=path_state,
                    action_counts=action_counts,
                    target_in_view=False,
                )
                actions += outcome.actions
                if movement_failures is not None:
                    record_movement_failure(movement_failures, client, destination, outcome, "startup_teleporter_home")
                actions += add_action(
                    action_counts,
                    "startup_teleporter_home_move" if outcome.moved else "startup_teleporter_home_wait",
                )
                if not outcome.moved and not outcome.arrived:
                    break
            if scan_seconds:
                client.read_packets_for(scan_seconds)
            candidates = scan_teleporter_candidates()

        if candidates:
            target = min(candidates, key=client.distance_to)
            approach_distance = max(
                0.0,
                float(getattr(args, "startup_teleport_approach_distance", 0.0) or 0.0),
            )
            approach_deadline = time.monotonic() + startup_teleport_approach_timeout(
                args,
                client,
                target,
                approach_distance,
            )
            while approach_distance > 0.0 and client.distance_to(target) > approach_distance:
                moved = client.move_towards_position(
                    int(getattr(target, "x", client.x)),
                    int(getattr(target, "y", client.y)),
                    int(getattr(target, "z", client.z)),
                    step=smooth_movement_step(args) if getattr(args, "smooth_movement", False) else getattr(args, "move_step", 260.0),
                    stop_distance=approach_distance,
                    movement_speed=getattr(args, "movement_speed", None),
                    min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                    target_in_view=False,
                )
                if not moved or time.monotonic() >= approach_deadline:
                    break
                client.read_packets_for(max(0.0, float(getattr(args, "smooth_move_interval", 0.2) or 0.2)))
                actions += add_action(action_counts, "startup_teleport_approach")
                fresh = [
                    npc
                    for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=True)
                    if getattr(npc, "object_id", 0) == getattr(target, "object_id", 0)
                ]
                if fresh:
                    target = fresh[0]
            if approach_distance > 0.0 and hasattr(client, "move_towards_position"):
                client.move_towards_position(
                    int(getattr(target, "x", client.x)),
                    int(getattr(target, "y", client.y)),
                    int(getattr(target, "z", client.z)),
                    step=1.0,
                    stop_distance=approach_distance,
                    movement_speed=0.0,
                    min_position_send_interval=0.0,
                    target_in_view=True,
                )
            client.target_object(target.object_id)
            actions += add_action(action_counts, "startup_teleport_target")
            if getattr(args, "startup_teleport_interact", True):
                client.interact_object(target.object_id)
                actions += add_action(action_counts, "startup_teleport_interact")
            for whisper in getattr(args, "startup_teleport_warmup_whisper", []) or []:
                whisper = str(whisper or "").strip()
                if whisper:
                    client.send_command(f"/whisper {format_whisper_argument(whisper)}")
                    actions += add_action(action_counts, "startup_teleport_warmup_whisper")
                    warmup_delay = max(
                        0.0,
                        float(getattr(args, "startup_teleport_warmup_delay", 0.0) or 0.0),
                    )
                    if warmup_delay:
                        client.read_packets_for(warmup_delay)
                        actions += add_action(action_counts, "startup_teleport_warmup_wait")
            if getattr(args, "startup_teleport_warmup_whisper", []) or []:
                client.target_object(target.object_id)
                actions += add_action(action_counts, "startup_teleport_retarget")
            client.send_command(f"/whisper {format_whisper_argument(teleport_destination)}")
            actions += add_action(action_counts, "startup_teleport_whisper")
            wait_seconds = max(0.0, float(getattr(args, "startup_teleport_wait_seconds", 0.0) or 0.0))
            if wait_seconds:
                client.read_packets_for(wait_seconds)
                actions += add_action(action_counts, "startup_teleport_wait")
            actions += sync_startup_teleport_position(client, teleport_destination, action_counts, args)
        else:
            actions += add_action(action_counts, "startup_teleporter_missing")

    return actions


def write_jsonl(path: str, payload: dict[str, object]) -> None:
    if not path:
        return

    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def short_text(value: str, limit: int = 180) -> str:
    normalized = " ".join(str(value or "").split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1] + "…"


def detect_random_item_tier(item_name: str) -> str:
    normalized = item_name.strip()
    for article in ("a ", "an ", "the "):
        if normalized.lower().startswith(article):
            normalized = normalized[len(article):].strip()
            break

    for tier in RANDOM_ITEM_TIERS:
        if normalized.startswith(f"{tier}:"):
            return tier

    return "일반"


def parse_loot_message(text: str) -> LootMetric | None:
    clean_text = " ".join(text.strip().split())

    if not clean_text:
        return None

    if "이(가)" in clean_text:
        return None

    for pattern in LOOT_KOREAN_PATTERNS:
        match = pattern.match(clean_text)

        if match:
            item_name = match.group("item").strip()
            return LootMetric(item_name, detect_random_item_tier(item_name))

    for pattern in LOOT_ENGLISH_PATTERNS:
        match = pattern.match(clean_text)

        if match:
            item_name = match.group("item").strip()
            return LootMetric(item_name, detect_random_item_tier(item_name))

    return None


COMBAT_AMOUNT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("damage_taken", re.compile(r"(?:받았습니다|입었습니다|hits?\s+you|hit\s+you).{0,40}?(\d+).{0,20}?(?:피해|damage)?", re.IGNORECASE)),
    ("damage_taken", re.compile(r"(\d+).{0,20}?(?:피해|damage).{0,20}?(?:받았습니다|입었습니다|받음)", re.IGNORECASE)),
    ("damage_done", re.compile(r"^(?!.*당신)(?:.+?)에게\s*(\d+)\s*(?:\([^)]*\)\s*)?피해를\s*입혔", re.IGNORECASE)),
    ("damage_done", re.compile(r"(?:공격합니다|당신).{0,100}?하여\s*(\d+)\s*(?:\([^)]*\)\s*)?피해를\s*입혔", re.IGNORECASE)),
    ("damage_done", re.compile(r"(?:당신|you).{0,40}?(\d+).{0,20}?(?:피해|damage)", re.IGNORECASE)),
    ("damage_done", re.compile(r"(?:당신|you).{0,20}?(?:hit|hits).{0,60}?(?:for\s+)?(\d+)", re.IGNORECASE)),
    ("healing_received", re.compile(r".+이\(가\)\s*당신의\s*생명력을\s*(\d+)점\s*회복했습니다", re.IGNORECASE)),
    ("healing_received", re.compile(r"you\s+are\s+healed\s+by\s+.+?\s+for\s+(\d+)\s+hit\s+points", re.IGNORECASE)),
    ("healing_received", re.compile(r".+\s+heals\s+you\s+for\s+(\d+)\s+(?:hit|health)?\s*points?", re.IGNORECASE)),
    ("healing_done", re.compile(r"자신의\s*생명력을\s*(\d+)점\s*회복했습니다", re.IGNORECASE)),
    ("healing_done", re.compile(r".+의\s*생명력을\s*(\d+)점\s*회복했습니다!?", re.IGNORECASE)),
    ("healing_done", re.compile(r"당신.{0,80}?(\d+)\s*(?:점\s*)?(?:치유|회복)", re.IGNORECASE)),
    ("healing_done", re.compile(r"추가로\s*생명력\s*(\d+)점을\s*회복했습니다", re.IGNORECASE)),
    ("healing_done", re.compile(r"you\s+heal\s+yourself\s+for\s+(\d+)\s+hit\s+points", re.IGNORECASE)),
    ("healing_done", re.compile(r"you\s+heal\s+.+?\s+for\s+(\d+)\s+hit\s+points!?", re.IGNORECASE)),
    ("healing_done", re.compile(r"you\s+heal\s+for\s+an\s+extra\s+(\d+)\s+hit\s+points", re.IGNORECASE)),
]


def parse_combat_text_metric(text: str) -> tuple[str, int] | None:
    normalized = text.strip()

    if not normalized:
        return None

    lower = normalized.lower()

    if any(skip in lower for skip in ("얻어", "가방", "loot", "item")):
        return None

    numbers = [int(value) for value in re.findall(r"\d+", normalized)]

    korean_incoming_damage = parse_korean_incoming_damage_amount(normalized)
    if korean_incoming_damage > 0:
        return "damage_taken", korean_incoming_damage

    if numbers and any(keyword in lower for keyword in ("치유", "회복", "heal")):
        for metric_name, pattern in COMBAT_AMOUNT_PATTERNS:
            if not metric_name.startswith("healing_"):
                continue
            match = pattern.search(normalized)

            if match:
                return metric_name, int(match.group(1))

        if any(keyword in lower for keyword in ("받았습니다", "받음", "received")):
            return "healing_received", numbers[-1]

    if numbers and any(keyword in lower for keyword in ("피해", "damage")):
        if any(keyword in lower for keyword in ("받았습니다", "입었습니다", "받음", "hits you", "hit you")):
            return "damage_taken", numbers[-1]
        if "당신" in normalized or "you" in lower:
            return "damage_done", numbers[0]

    for metric_name, pattern in COMBAT_AMOUNT_PATTERNS:
        match = pattern.search(normalized)

        if match:
            return metric_name, int(match.group(1))

    return None


def drive_login_with_retries(client, account: DummyAccount, args: argparse.Namespace) -> None:
    attempts = max(1, int(getattr(args, "login_retries", 1) or 1))
    delay = max(0.0, float(getattr(args, "login_retry_delay", 0.0) or 0.0))
    last_error: Exception | None = None

    def reset_login_state() -> None:
        for name, value in (
            ("sequence", 0),
            ("session_id", 0),
            ("recv_buffer", bytearray()),
        ):
            if hasattr(client, name):
                setattr(client, name, value)

    for attempt in range(attempts):
        try:
            client.drive_login(account.username, account.password, account.realm, account.char_index)
            return
        except (RuntimeError, OSError) as exc:
            last_error = exc
            message = str(exc).lower()
            transient = (
                "server did not send a session id" in message
                or "broken pipe" in message
                or "connection reset" in message
                or isinstance(exc, BrokenPipeError)
                or getattr(exc, "errno", None) in {errno.EPIPE, errno.ECONNRESET}
            )
            if not transient or attempt + 1 >= attempts:
                raise
            try:
                client.close()
            except OSError:
                pass
            reset_login_state()
            if delay > 0.0:
                time.sleep(delay)

    if last_error is not None:
        raise last_error


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
    client.server_correction_smoothing = args.server_correction_smoothing
    client.server_correction_min_distance = args.server_correction_min_distance
    client.server_correction_step = args.server_correction_step
    client.server_correction_max_snap_distance = args.server_correction_max_snap_distance
    client.ground_z_sampler = load_ground_z_sampler(args.ground_z_map, args.ground_z_offset)
    client.trace_observed_player_positions = args.trace_observed_player_positions
    if getattr(args, "trace_movement_log", ""):
        client.trace_movement_path = args.trace_movement_log.format(
            username=account.username,
            round=round_index,
            index=index,
        )
    encounter_log_path = ""
    if getattr(args, "encounter_log", ""):
        encounter_log_path = args.encounter_log.format(
            username=account.username,
            round=round_index,
            index=index,
        )
        Path(encounter_log_path).parent.mkdir(parents=True, exist_ok=True)
    actions = 0
    action_counts: dict[str, int] = {}
    combat_metrics: list[CombatMetric] = []
    movement_failures: list[MovementFailure] = []
    loot_metrics: list[LootMetric] = []
    combat_text_totals = {
        "damage_done": 0,
        "damage_taken": 0,
        "healing_done": 0,
        "healing_received": 0,
        }
    started = time.monotonic()
    combat_plan_loaded = False
    death_seen = False
    active_combat: dict[str, float | int | str] | None = None
    recent_finished_combats: dict[int, tuple[CombatMetric, float, int]] = {}
    last_spoken_state = ""
    last_state_speech_at = 0.0

    try:
        drive_login_with_retries(client, account, args)
        if account.start_x is not None and account.start_y is not None and account.start_z is not None:
            client.x = int(account.start_x)
            client.y = int(account.start_y)
            client.z = int(account.start_z)
            if account.zone_id is not None:
                client.zone_id = int(account.zone_id)
        client.send_position_update(speed=0.0, target_in_view=False)
        actions += add_action(action_counts, "initial_position_heartbeat")
        for startup_command in args.startup_command:
            client.send_command(startup_command)
            actions += add_action(action_counts, "startup_command")
        startup_train_level = int(getattr(args, "startup_train_level", 0) or 0)
        startup_train_delay = max(0.0, float(getattr(args, "startup_train_command_delay", 0.0) or 0.0))
        if getattr(args, "startup_auto_train", False):
            for train_command in auto_train_commands_from_specs(account.specs, startup_train_level):
                client.send_command(train_command)
                actions += add_action(action_counts, "startup_auto_train")
                if getattr(args, "speak_state_changes", False):
                    client.send_command(format_say_command(f"state: training {train_command}"))
                    actions += add_action(action_counts, "state_speech")
        if getattr(args, "startup_train_full_specs", False):
            for train_command in auto_train_commands_from_specs(account.specs, startup_train_level, full_spec=True):
                client.send_command(train_command)
                actions += add_action(action_counts, "startup_train_full_spec")
                if getattr(args, "speak_state_changes", False):
                    client.send_command(format_say_command(f"state: training {train_command}"))
                    actions += add_action(action_counts, "state_speech")
                if startup_train_delay > 0.0:
                    time.sleep(startup_train_delay)
        path_state = build_path_movement_state(args, client)
        actions += run_startup_service_actions(client, args, action_counts, path_state, movement_failures)
        startup_delay = max(0.0, float(getattr(args, "startup_delay", 0.0) or 0.0))
        if startup_delay > 0.0:
            time.sleep(startup_delay)
            actions += add_action(action_counts, "startup_delay")
        combat_plan = CombatUsablePlan()

        if args.use_skills and args.combat_usable_api:
            try:
                combat_plan = fetch_combat_usable_plan(args, account)
                combat_plan_loaded = True
                actions += add_action(action_counts, "combat_plan_loaded")
                if combat_plan.skills:
                    actions += add_action(action_counts, "combat_plan_has_skills")
                if combat_plan.attack_spells:
                    actions += add_action(action_counts, "combat_plan_has_attack_spells")
                if combat_plan.heal_spells:
                    actions += add_action(action_counts, "combat_plan_has_heal_spells")
                if combat_plan.buff_spells:
                    actions += add_action(action_counts, "combat_plan_has_buff_spells")
            except Exception:
                actions += add_action(action_counts, "combat_plan_failed")
        actions += cast_precombat_self_buffs(client, args, combat_plan, action_counts)

        if args.auto_loot:
            client.send_command("/autoloot on")
            actions += add_action(action_counts, "autoloot_on")
        if path_state.graph is not None:
            actions += add_action(action_counts, "path_graph_loaded")

        commands = list(args.command)
        next_ping = time.monotonic() + rng.uniform(0.2, max(args.ping_interval, 0.2))
        next_turn = time.monotonic() + rng.uniform(0.2, max(args.turn_interval, 0.2))
        next_command = time.monotonic() + rng.uniform(0.5, max(args.command_interval, 0.5))
        next_clear_target = time.monotonic() + max(args.clear_target_interval, 0.2)
        next_combat = time.monotonic() + rng.uniform(0.5, max(args.combat_interval, 0.5))
        next_skill = time.monotonic() + rng.uniform(1.0, max(args.skill_interval, 1.0))
        next_active_tank_reaggro_taunt = 0.0
        cast_action_hold_until = 0.0
        next_party_heal = time.monotonic() + rng.uniform(1.0, max(args.party_heal_leader_interval, 1.0))
        next_recovery = time.monotonic() + rng.uniform(5.0, max(args.recovery_interval, 5.0))
        next_invite = time.monotonic() + rng.uniform(1.0, max(args.party_invite_interval, 1.0))
        next_accept = time.monotonic() + rng.uniform(1.5, max(args.party_accept_interval, 1.5))
        next_assist = time.monotonic() + rng.uniform(2.0, max(args.party_assist_interval, 2.0))
        next_follow = time.monotonic() + rng.uniform(0.8, max(args.party_follow_interval, 0.8))
        next_party_buff = time.monotonic() + rng.uniform(1.0, max(args.party_buff_interval, 1.0))
        next_party_rescue_request = 0.0
        next_self_preserve_heal = 0.0
        local_rescue_until = 0.0
        party_melee_survival_backoff_until = 0.0
        boss_hazard_backoff_until = 0.0
        party_buff_index = 0
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
        next_face_command = 0.0
        next_stick_command = 0.0
        next_required_target_api = time.monotonic() + rng.uniform(0.2, max(args.required_target_api_interval, 0.2))
        latest_required_target_api_observation: RequiredTargetObservation | None = None
        server_target_observations: dict[int, RequiredTargetObservation] = {}
        next_position_heartbeat = (
            time.monotonic() + rng.uniform(0.5, max(args.position_heartbeat_interval, 0.5))
            if args.position_heartbeat_interval > 0
            else float("inf")
        )
        next_encounter_log = time.monotonic()
        next_hunter_scan_log = 0.0
        next_live_control_check = 0.0
        last_live_control_revision = ""
        last_attack_enabled: bool | None = None
        heading = rng.randrange(0, 4096)
        current_target = 0
        current_target_since = time.monotonic()
        current_target_last_visible_at = current_target_since
        current_target_removed_preserve_count = 0
        behavior_state = DummyBehaviorState.Startup
        state_entered_at = current_target_since
        state_reason = "startup"
        current_target_intent = TargetIntent.none
        actions += add_action(action_counts, f"behavior_state_{behavior_state.value}")
        attack_target_in_view_primed_at = 0.0
        attack_target_in_view_primed_target = 0
        sent_target_start_command_targets: set[int] = set()
        rejected_targets: dict[int, float] = {}
        rejected_target_kinds: dict[tuple[str, int], float] = {}
        greeted_players: dict[int, float] = {}
        rest_until = 0.0
        death_release_after = 0.0
        next_death_release = 0.0
        corpse_position_sent = False
        flee_until = 0.0
        next_flee_move = 0.0
        next_flee_pressure_replan = 0.0
        flee_destination: MovementDestination | None = None
        flee_wander_heading = heading
        flee_wander_heading_hold_until = 0.0
        last_flee_damage_replan_at = 0.0
        flee_damage_replan_suppressed_until = 0.0
        friendly_cast_hold_until = 0.0
        friendly_cast_restore_target = 0
        party_pull_ready_since = 0.0
        stand_after_rest = False
        last_health_percent = int(getattr(client, "health_percent", 100) or 100)
        last_damage_taken_at = 0.0
        last_incoming_damage_attacker_name = ""
        last_incoming_damage_at = 0.0
        travel_aggro_danger_x = 0
        travel_aggro_danger_y = 0
        travel_aggro_danger_z = 0
        travel_aggro_danger_until = 0.0
        travel_aggro_repeat_count = 0
        travel_aggro_last_at = 0.0
        travel_aggro_last_name = ""
        objective_complete_at = 0.0
        waypoint_index = rng.randrange(0, len(args.waypoints)) if args.waypoints and args.waypoint_mode == "random" else 0
        end_time = time.monotonic() + args.hold
        party_slot = index % max(args.party_size, 1)
        is_party_leader = party_state is not None and party_slot == 0
        is_party_follower = party_state is not None and party_slot != 0
        party_member_name = character_name_from_account(account.username)
        requested_action_rotation = resolve_action_rotation(args, party_slot)
        action_rotation = resolve_effective_action_rotation(args, requested_action_rotation, combat_plan, combat_plan_loaded)

        if action_rotation != requested_action_rotation:
            actions += add_action(action_counts, f"rotation_adjusted_{requested_action_rotation}_to_{action_rotation}")

        if party_state is not None:
            party_state.update_member_role(party_member_name, action_rotation)

        if is_party_leader:
            party_state.update_leader(client)
        elif party_state is not None:
            party_state.update_member(party_member_name, client)

        def current_visible_target_npc():
            if not current_target:
                return None

            return next(
                (
                    npc
                    for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
                    if npc.object_id == current_target
                ),
                None,
            )

        def log_encounter_event(event: str, now: float | None = None, **fields) -> None:
            if not encounter_log_path:
                return

            now = time.monotonic() if now is None else now
            party_snapshot = fields.pop("party_snapshot", None)
            if party_snapshot is None and party_state is not None:
                party_snapshot = party_state.snapshot()

            npc = fields.pop("npc", None)
            if npc is None:
                npc = current_visible_target_npc()

            target_age = now - current_target_since if current_target else 0.0
            last_visible_age = now - current_target_last_visible_at if current_target else 0.0
            payload: dict[str, object] = {
                "t": round(now, 6),
                "elapsed": round(now - started, 3),
                "event": event,
                "username": account.username,
                "character": party_member_name,
                "round": round_index,
                "worker_index": index,
                "role": action_rotation,
                "party_slot": party_slot,
                "is_leader": is_party_leader,
                "is_follower": is_party_follower,
                "x": int(client.x),
                "y": int(client.y),
                "z": int(client.z),
                "heading": int(client.heading & 0x0FFF),
                "health_percent": int(getattr(client, "health_percent", 0) or 0),
                "mana_percent": int(getattr(client, "mana_percent", 0) or 0),
                "endurance_percent": int(getattr(client, "endurance_percent", 0) or 0),
                "is_dead": bool(getattr(client, "is_dead", False)),
                "current_target": int(current_target),
                "current_target_intent": target_intent_value(current_target_intent if current_target else TargetIntent.none),
                "current_target_age": round(target_age, 3),
                "current_target_last_visible_age": round(last_visible_age, 3),
                "current_target_removed_preserve_count": int(current_target_removed_preserve_count),
                "behavior_state": behavior_state_value(behavior_state),
                "behavior_state_age": round(now - state_entered_at, 3),
                "behavior_state_reason": state_reason,
                "objective_complete": objective_complete_at > 0,
                "actions": actions,
                "attack_on_count": action_counts.get("attack_on", 0),
                "attack_off_count": action_counts.get("attack_off", 0),
                "skills_count": sum(count for name, count in action_counts.items() if "skill" in name or "spell" in name),
                "loot_count": len(loot_metrics),
                "damage_done": combat_text_totals["damage_done"],
                "damage_taken": combat_text_totals["damage_taken"],
                "healing_done": combat_text_totals["healing_done"],
                "healing_received": combat_text_totals["healing_received"],
            }

            if active_combat is not None:
                payload.update(
                    {
                        "active_target_id": int(active_combat["target_id"]),
                        "active_target_name": str(active_combat["target_name"]),
                        "active_target_level": int(active_combat["target_level"]),
                        "active_combat_seconds": round(now - float(active_combat["started"]), 3),
                        "active_attacks": int(active_combat["attacks"]),
                        "active_skills": int(active_combat["skills"]),
                    }
                )

            if npc is not None:
                payload.update(
                    {
                        "target_visible": True,
                        "target_id": int(npc.object_id),
                        "target_name": str(npc.name),
                        "target_level": int(npc.level),
                        "target_x": int(npc.x),
                        "target_y": int(npc.y),
                        "target_z": int(npc.z),
                        "target_distance": round(combat_distance_to(client, npc), 2),
                        "target_flags": int(getattr(npc, "flags", 0) or 0),
                    }
                )
            else:
                payload["target_visible"] = False

            if isinstance(party_snapshot, dict):
                payload.update(
                    {
                        "leader_target_id": int(party_snapshot.get("leader_target_id", 0) or 0),
                        "leader_target_name": str(party_snapshot.get("leader_target_name", "") or ""),
                        "leader_target_age": round(now - float(party_snapshot.get("leader_target_updated_at", 0.0) or 0.0), 3)
                        if party_snapshot.get("leader_target_updated_at", 0.0)
                        else 0.0,
                        "leader_target_focus_name": str(party_snapshot.get("leader_target_focus_name", "") or ""),
                        "leader_target_focus_age": round(
                            now - float(party_snapshot.get("leader_target_focus_updated_at", 0.0) or 0.0),
                            3,
                        )
                        if party_snapshot.get("leader_target_focus_updated_at", 0.0)
                        else 0.0,
                        "leader_engaged": float(party_snapshot.get("leader_target_engaged_at", 0.0) or 0.0) > 0.0,
                        "leader_health_percent": int(party_snapshot.get("leader_health_percent", 0) or 0),
                        "active_tank_name": str(party_snapshot.get("active_tank_name", "") or ""),
                        "active_tank_health_percent": int(party_snapshot.get("active_tank_health_percent", 0) or 0),
                        "rescue_target_id": int(party_snapshot.get("rescue_target_id", 0) or 0),
                        "rescue_target_name": str(party_snapshot.get("rescue_target_name", "") or ""),
                        "rescue_member_name": str(party_snapshot.get("rescue_member_name", "") or ""),
                        "encounter_death_count": int(party_snapshot.get("encounter_death_count", 0) or 0),
                    }
                )

            payload.update(fields)
            write_jsonl(encounter_log_path, payload)

        def log_encounter_tick_if_due(
            now: float,
            *,
            party_snapshot: dict[str, object],
            party_melee_survival_backoff: bool,
            boss_hazard_backoff: bool,
            party_survival_backoff: bool,
            party_focus_target_backoff: bool,
            party_focus_pressure_backoff: bool,
        ) -> None:
            nonlocal next_encounter_log

            if not encounter_log_path or args.encounter_log_interval <= 0 or now < next_encounter_log:
                return

            log_encounter_event(
                "encounter_tick",
                now,
                party_snapshot=party_snapshot,
                party_melee_survival_backoff=party_melee_survival_backoff,
                boss_hazard_backoff=boss_hazard_backoff,
                party_survival_backoff=party_survival_backoff,
                party_focus_target_backoff=party_focus_target_backoff,
                party_focus_pressure_backoff=party_focus_pressure_backoff,
            )
            next_encounter_log = now + args.encounter_log_interval

        def log_attack_decision(
            now: float,
            attack_enabled: bool,
            reason: str,
            *,
            npc=None,
            party_snapshot: dict[str, object] | None = None,
            **fields,
        ) -> None:
            nonlocal last_attack_enabled

            changed = last_attack_enabled is None or last_attack_enabled != attack_enabled
            if changed or args.encounter_log_attack_decisions:
                log_encounter_event(
                    "attack_decision",
                    now,
                    npc=npc,
                    party_snapshot=party_snapshot,
                    attack_enabled=attack_enabled,
                    reason=reason,
                    **fields,
                )
            last_attack_enabled = attack_enabled

        def transition_to(new_state: DummyBehaviorState, reason: str, now: float | None = None) -> bool:
            nonlocal actions, behavior_state, state_entered_at, state_reason

            now = time.monotonic() if now is None else now
            if behavior_state == new_state:
                return False

            previous_state = behavior_state
            behavior_state = new_state
            state_entered_at = now
            state_reason = reason
            actions += add_action(action_counts, f"behavior_state_{new_state.value}")
            log_encounter_event(
                "behavior_state_change",
                now,
                previous_behavior_state=previous_state.value,
                behavior_state=new_state.value,
                reason=reason,
                current_target_intent=target_intent_value(current_target_intent),
            )
            if (
                is_party_follower
                and party_state is not None
                and should_clear_party_ready_for_behavior_state(new_state)
            ):
                party_state.clear_ready(party_member_name)
                actions += add_action(action_counts, "party_ready_cleared")
            return True

        def clear_shared_leader_target_on_abandon(now: float, reason: str, target_id: int = 0) -> None:
            nonlocal actions

            if clear_party_leader_target_on_abandon(
                party_state,
                is_party_leader=is_party_leader,
                target_id=target_id,
            ):
                actions += add_action(action_counts, "party_leader_target_abandon_clear")
                log_encounter_event(
                    "party_leader_target_abandon_clear",
                    now,
                    reason=reason,
                    abandoned_target_id=int(target_id or 0),
                )

        def refresh_required_target_from_api(
            now: float,
            party_snapshot: dict[str, object],
        ) -> RequiredTargetObservation | None:
            nonlocal actions, current_target, current_target_since, current_target_last_visible_at, latest_required_target_api_observation, next_required_target_api

            if (
                not args.required_target_api
                or party_state is None
                or not should_preserve_party_target_on_loss(args)
                or args.required_target_api_interval <= 0
                or now < next_required_target_api
                or float(party_snapshot.get("objective_completed_at", 0.0) or 0.0) > 0.0
            ):
                return None

            next_required_target_api = now + args.required_target_api_interval + rng.uniform(
                0.0,
                min(args.jitter, args.required_target_api_interval),
            )

            member_may_publish = is_party_leader or party_member_is_active_tank(party_snapshot, party_member_name)
            old_leader_target_id = int(party_snapshot.get("leader_target_id", 0) or 0)
            rescue_target_id = int(party_snapshot.get("rescue_target_id", 0) or 0)

            try:
                observed = fetch_required_target_observation(args, api_region_for_client(args, client))
            except Exception as exc:
                actions += add_action(action_counts, "required_target_api_error")
                log_encounter_event("required_target_api_error", now, error=short_text(str(exc), 220))
                return None

            if observed is None or observed.object_id <= 0 or not observed.is_alive:
                latest_required_target_api_observation = observed
                actions += add_action(action_counts, "required_target_api_miss")
                log_encounter_event("required_target_api_miss", now)
                return None

            observed = replace(observed, last_seen=now)
            latest_required_target_api_observation = observed
            client.npcs[observed.object_id] = observed

            catchup_distance = float(getattr(args, "required_target_catchup_distance", 0.0) or 0.0)
            if (
                catchup_distance > 0
                and not observed.in_combat
                and not observed.has_aggro
                and client.horizontal_distance_to(observed) > catchup_distance
            ):
                offset = max(float(getattr(args, "required_target_catchup_offset", 250.0) or 0.0), 0.0)
                angle = (index % max(int(getattr(args, "concurrency", 1) or 1), 1)) * (math.tau / max(int(getattr(args, "concurrency", 1) or 1), 1))
                client.x = int(observed.x + math.cos(angle) * offset)
                client.y = int(observed.y + math.sin(angle) * offset)
                client.z = int(observed.z)
                client.heading = heading_from_delta(observed.x - client.x, observed.y - client.y)
                client.send_position_update(speed=0.0, target_in_view=True)
                actions += add_action(action_counts, "required_target_catchup")
                if party_state is not None:
                    party_state.update_member(party_member_name, client)
                log_encounter_event(
                    "required_target_catchup",
                    now,
                    npc=observed,
                    target_distance=round(client.horizontal_distance_to(observed), 2),
                    catchup_distance=round(catchup_distance, 2),
                    catchup_offset=round(offset, 2),
                )

            if member_may_publish:
                party_state.update_shared_target(observed, engaged=observed.in_combat or observed.has_aggro)
                actions += add_action(action_counts, "required_target_api_update")

            should_retarget_required_object = (
                current_target == 0
                or current_target == old_leader_target_id
                or current_target == observed.object_id
                or (
                    bool(getattr(args, "party_focus_target_backoff", False))
                    and normalize_target_name(observed.target) == normalize_target_name(party_member_name)
                    and not party_member_is_active_tank(party_snapshot, party_member_name)
                )
                or (rescue_target_id <= 0 and active_combat is not None and str(active_combat.get("target_name", "")) == observed.name)
            )
            if should_retarget_required_object:
                if current_target != observed.object_id:
                    current_target = observed.object_id
                    current_target_since = now
                current_target_last_visible_at = now
                client.target_object(observed.object_id)

            log_encounter_event(
                "required_target_api_update",
                now,
                npc=observed,
                observed_health_percent=round(observed.health_percent, 2),
                observed_health=observed.health,
                observed_max_health=observed.max_health,
                observed_in_combat=observed.in_combat,
                observed_has_aggro=observed.has_aggro,
                observed_target=observed.target,
                published=member_may_publish,
                retargeted=should_retarget_required_object,
            )
            return observed

        log_encounter_event("round_start", time.monotonic())

        def send_ping_if_due(now: float) -> None:
            nonlocal actions, next_ping

            if args.ping_interval <= 0 or now < next_ping:
                return

            client.send_ping()
            actions += add_action(action_counts, "ping")
            next_ping = now + args.ping_interval + rng.uniform(0, args.jitter)

        def send_position_heartbeat(now: float) -> None:
            nonlocal actions, next_position_heartbeat

            if args.position_heartbeat_interval <= 0 or now < next_position_heartbeat:
                return

            if not should_send_position_heartbeat_for_client(client):
                return

            client.send_position_update(speed=getattr(client, "last_position_speed", 0.0), target_in_view=current_target != 0)
            actions += add_action(action_counts, "position_heartbeat")
            next_position_heartbeat = (
                now
                + args.position_heartbeat_interval
                + rng.uniform(0.0, min(args.jitter, max(args.position_heartbeat_interval * 0.5, 0.0)))
            )

        def send_face_command_if_due(now: float, reason: str, destination: MovementDestination | None = None) -> None:
            nonlocal actions, next_face_command

            if args.target_face_command_interval <= 0 or now < next_face_command:
                return

            if destination is None:
                actions += add_action(action_counts, "facegloc_command_skipped_no_destination")
                actions += add_action(action_counts, f"facegloc_command_skipped_no_destination_{reason}")
                next_face_command = now + args.target_face_command_interval + rng.uniform(
                    0.0,
                    min(args.jitter, max(args.target_face_command_interval * 0.5, 0.0)),
                )
                return

            face_point_for_attack(client, destination.x, destination.y)
            client.send_command(facegloc_command_for_point(destination.x, destination.y))
            actions += add_action(action_counts, "facegloc_command")
            actions += add_action(action_counts, f"facegloc_command_{reason}")
            next_face_command = now + args.target_face_command_interval + rng.uniform(
                0.0,
                min(args.jitter, max(args.target_face_command_interval * 0.5, 0.0)),
            )

        def send_stick_command_if_due(now: float, reason: str) -> None:
            nonlocal actions, next_stick_command

            if args.target_stick_command_interval <= 0 or now < next_stick_command:
                return

            actions += add_action(action_counts, "stick_command_skipped_unavailable")
            actions += add_action(action_counts, f"stick_command_skipped_unavailable_{reason}")
            next_stick_command = now + args.target_stick_command_interval + rng.uniform(
                0.0,
                min(args.jitter, max(args.target_stick_command_interval * 0.5, 0.0)),
            )

        def speak_state_change(now: float, state: str, text: str) -> None:
            nonlocal actions, last_spoken_state, last_state_speech_at

            if not getattr(args, "speak_state_changes", False):
                return
            if state == last_spoken_state:
                return

            min_interval = max(0.0, float(getattr(args, "state_speech_min_interval", 0.0) or 0.0))
            if last_state_speech_at > 0.0 and now - last_state_speech_at < min_interval:
                return

            client.send_command(format_say_command(text))
            actions += add_action(action_counts, "state_speech")
            last_spoken_state = state
            last_state_speech_at = now

        def start_combat(npc, distance: float, now: float) -> None:
            nonlocal actions, active_combat
            active_combat = {
                "target_id": npc.object_id,
                "target_name": npc.name,
                "target_level": npc.level,
                "started": now,
                "attacks": 0,
                "skills": 0,
                "damage_done": 0,
                "damage_taken": 0,
                "off_target_damage_taken": 0,
                "off_target_attacker_name": "",
                "last_combat_message_at": 0.0,
                "last_damage_done_at": 0.0,
                "server_los_failures": 0,
                "start_distance": distance,
                "end_distance": distance,
                "target_x": int(getattr(npc, "x", 0) or 0),
                "target_y": int(getattr(npc, "y", 0) or 0),
                "target_z": int(getattr(npc, "z", 0) or 0),
            }
            if publish_combat_start_as_leader_target(
                party_state,
                client,
                npc,
                is_party_leader=is_party_leader,
                current_target_intent=current_target_intent,
            ):
                actions += add_action(action_counts, "leader_combat_start_shared")
            log_encounter_event("combat_start", now, npc=npc, start_distance=round(distance, 2))
            speak_state_change(now, f"combat:{npc.object_id}", f"state: attacking {npc.name} L{npc.level}")

        def finish_combat(outcome: str, now: float, end_distance: float = 0.0) -> bool:
            nonlocal active_combat

            if active_combat is None:
                return False

            duration = max(0.0, now - float(active_combat["started"]))
            final_distance = end_distance if end_distance > 0 else float(active_combat["end_distance"])
            log_encounter_event(
                "combat_finish",
                now,
                outcome=outcome,
                duration_seconds=round(duration, 3),
                final_distance=round(final_distance, 2),
            )
            metric = CombatMetric(
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
            combat_metrics.append(metric)
            if outcome in POST_ABANDON_TARGET_REMOVED_OUTCOMES:
                recent_finished_combats[metric.target_id] = (
                    metric,
                    now,
                    int(active_combat.get("damage_done", 0) or 0),
                )
            else:
                recent_finished_combats.pop(metric.target_id, None)
            speak_state_change(
                now,
                f"finish:{outcome}",
                f"state: combat ended {outcome}",
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
            nonlocal actions, current_target, current_target_last_visible_at, current_target_removed_preserve_count, latest_required_target_api_observation, objective_complete_at

            for object_id in client.consume_removed_object_ids():
                if object_id != current_target:
                    recent_finished = recent_finished_combats.get(int(object_id))
                    if recent_finished is None:
                        continue
                    metric, finished_at, damage_done = recent_finished
                    previous_outcome = metric.outcome
                    promoted = promote_recent_finished_combat_to_target_removed(
                        metric,
                        finished_at=finished_at,
                        now=now,
                        damage_done=damage_done,
                    )
                    recent_finished_combats.pop(int(object_id), None)
                    if promoted:
                        actions += add_action(action_counts, "target_removed")
                        actions += add_action(action_counts, "post_abandon_target_removed")
                        rejected_targets.pop(object_id, None)
                        log_encounter_event(
                            "post_abandon_target_removed",
                            now,
                            removed_object_id=int(object_id),
                            previous_outcome=previous_outcome,
                            damage_done=int(damage_done),
                        )
                    continue

                log_encounter_event("target_object_removed", now, removed_object_id=int(object_id))

                stop_after_removed = should_stop_after_required_target_removed(args, active_combat, int(object_id))
                confirmation_observation = None
                if stop_after_removed and getattr(args, "required_target_api", False):
                    confirmation_observation = latest_required_target_api_observation
                    try:
                        confirmation_observation = fetch_required_target_observation(
                            args,
                            int(getattr(client, "zone_id", 0) or 0),
                        )
                        if confirmation_observation is not None:
                            confirmation_observation = replace(confirmation_observation, last_seen=now)
                            latest_required_target_api_observation = confirmation_observation
                    except Exception as exc:
                        actions += add_action(action_counts, "required_target_removed_api_error")
                        log_encounter_event(
                            "required_target_removed_api_error",
                            now,
                            removed_object_id=int(object_id),
                            error=short_text(str(exc), 220),
                        )

                    if not required_target_removed_api_confirms_completion(
                        args,
                        active_combat,
                        confirmation_observation,
                        int(object_id),
                    ):
                        stop_after_removed = False
                        actions += add_action(action_counts, "required_target_removed_api_alive")
                        log_encounter_event(
                            "required_target_removed_api_alive",
                            now,
                            removed_object_id=int(object_id),
                            observed_object_id=(
                                int(confirmation_observation.object_id)
                                if confirmation_observation is not None
                                else 0
                            ),
                            observed_name=(
                                confirmation_observation.name if confirmation_observation is not None else ""
                            ),
                            observed_health_percent=(
                                round(confirmation_observation.health_percent, 2)
                                if confirmation_observation is not None
                                else 0.0
                            ),
                            observed_health=(
                                int(confirmation_observation.health)
                                if confirmation_observation is not None
                                else 0
                            ),
                            observed_max_health=(
                                int(confirmation_observation.max_health)
                                if confirmation_observation is not None
                                else 0
                            ),
                            observed_is_alive=(
                                bool(confirmation_observation.is_alive)
                                if confirmation_observation is not None
                                else False
                            ),
                        )
                if (
                    should_preserve_removed_party_target(
                        args,
                        party_state,
                        current_target,
                        active_combat,
                        stop_after_removed,
                        now,
                        current_target_last_visible_at,
                        current_target_removed_preserve_count,
                    )
                ):
                    current_target_removed_preserve_count += 1
                    preserve_destination = None
                    if confirmation_observation is not None and confirmation_observation.is_alive:
                        preserve_destination = destination_from_actor("required-target-api", confirmation_observation)
                        client.npcs[confirmation_observation.object_id] = confirmation_observation
                        current_target = confirmation_observation.object_id
                        current_target_last_visible_at = now
                    elif party_state is not None:
                        party_snapshot = party_state.snapshot()
                        if int(party_snapshot["leader_target_id"]) == current_target:
                            preserve_destination = destination_from_point(
                                "party-target-last-known",
                                int(party_snapshot["leader_target_x"]),
                                int(party_snapshot["leader_target_y"]),
                                int(party_snapshot["leader_target_z"]),
                            )
                    client.target_object(current_target)
                    client.set_attack_mode(True)
                    send_face_command_if_due(now, "target_removed_preserved", preserve_destination)
                    send_stick_command_if_due(now, "target_removed_preserved")
                    if preserve_destination is not None:
                        outcome = move_towards_destination(
                            client,
                            preserve_destination,
                            step=smooth_movement_step(args) if args.smooth_movement else args.move_step,
                            stop_distance=melee_stop_distance(args),
                            args=args,
                            path_state=path_state,
                            action_counts=action_counts,
                            target_in_view=True,
                        )
                        actions += outcome.actions
                        record_movement_failure(
                            movement_failures,
                            client,
                            preserve_destination,
                            outcome,
                            "target_removed_preserved",
                        )
                        actions += add_action(
                            action_counts,
                            "target_removed_preserved_approach" if outcome.moved else "target_removed_preserved_hold",
                        )
                    actions += add_action(action_counts, "target_removed_preserved")
                    log_encounter_event(
                        "target_removed_preserved",
                        now,
                        removed_object_id=int(object_id),
                        preserve_count=int(current_target_removed_preserve_count),
                        has_destination=preserve_destination is not None,
                    )
                    continue

                if should_preserve_current_party_target(args, party_state, current_target, active_combat):
                    actions += add_action(action_counts, "target_removed_preserve_expired")
                    log_encounter_event(
                        "target_removed_preserve_expired",
                        now,
                        removed_object_id=int(object_id),
                        preserve_count=int(current_target_removed_preserve_count),
                    )

                completed_target_display_name = str(active_combat["target_name"]) if active_combat is not None else ""
                completed_target_name = completed_target_display_name.lower()
                completed_target_level = int(active_combat["target_level"]) if active_combat is not None else 0
                recorded = finish_combat("target_removed", now)
                current_target = 0
                rejected_targets.pop(object_id, None)
                if recorded:
                    actions += add_action(action_counts, "target_removed")
                    if stop_after_removed:
                        objective_complete_at = now
                        if party_state is not None:
                            party_state.mark_objective_complete(object_id, completed_target_display_name)
                        if completed_target_name and completed_target_level:
                            rejected_target_kinds[(completed_target_name, completed_target_level)] = end_time + args.target_failure_name_cooldown
                        client.clear_target()
                        client.set_attack_mode(False)
                        actions += add_action(action_counts, "required_target_complete")
                        log_encounter_event(
                            "required_target_complete",
                            now,
                            completed_target_name=completed_target_name,
                            completed_target_level=completed_target_level,
                            loot_wait_seconds=args.target_removed_loot_wait,
                        )
                    elif party_state is not None and (is_party_leader or args.party_assist_only):
                        party_state.clear_leader_target()
                        party_state.clear_rescue_target(object_id)

        def consume_messages(now: float) -> None:
            nonlocal actions, current_target, current_target_intent, current_target_since, current_target_last_visible_at
            nonlocal current_target_removed_preserve_count, target_observed_at
            nonlocal attack_target_in_view_primed_at, attack_target_in_view_primed_target
            nonlocal next_party_rescue_request, local_rescue_until, boss_hazard_backoff_until
            nonlocal last_damage_taken_at, last_incoming_damage_at, last_incoming_damage_attacker_name
            nonlocal flee_until, next_flee_move, next_flee_pressure_replan, flee_destination, flee_wander_heading_hold_until

            for message in client.consume_messages():
                text = message.text.lower()
                message_categories: list[str] = []
                actions += add_action(action_counts, "server_message")
                loot_metric = parse_loot_message(message.text)
                party_attack_message = None
                if party_state is not None and args.party_rescue_aggro:
                    party_attack_message = parse_party_attack_message(
                        message.text,
                        list(party_state.member_names),
                    )

                if loot_metric is not None:
                    loot_metrics.append(loot_metric)
                    actions += add_action(action_counts, "loot_acquired")
                    actions += add_action(action_counts, f"loot_tier_{loot_metric.tier}")
                    message_categories.append("loot")

                combat_categories = classify_combat_server_message(message.text)
                if "out_of_range" in combat_categories:
                    actions += add_action(action_counts, "combat_out_of_range_msg")
                    message_categories.append("out_of_range")
                if "not_visible" in combat_categories:
                    actions += add_action(action_counts, "combat_not_visible_msg")
                    message_categories.append("not_visible")
                if "damage" in combat_categories:
                    actions += add_action(action_counts, "combat_damage_msg")
                    message_categories.append("damage")

                if is_active_target_combat_contact_message(active_combat, message.text, int(getattr(message, "chat_type", 0) or 0)):
                    active_combat["last_combat_message_at"] = now
                    active_combat["server_los_failures"] = 0
                    current_target_last_visible_at = now
                    actions += add_action(action_counts, "combat_contact_msg")
                    message_categories.append("combat_contact")

                if (
                    current_target
                    and active_combat is not None
                    and getattr(args, "reject_target_on_server_los_failure", False)
                    and ("out_of_range" in combat_categories or "not_visible" in combat_categories)
                    and "damage" not in combat_categories
                ):
                    observed_target = fetch_current_target_observation(
                        args,
                        api_region_for_client(args, client),
                        current_target,
                    )
                    retry_target, retry_target_source = server_los_retry_target(
                        client,
                        args,
                        current_target=current_target,
                        active_combat=active_combat,
                        observed_target=observed_target,
                    )
                    observed_distance = None
                    if retry_target is not None:
                        observed_distance = math.hypot(retry_target.x - client.x, retry_target.y - client.y)
                    else:
                        target_destination = active_combat_last_known_destination(active_combat)
                        if target_destination is not None:
                            observed_distance = horizontal_distance_between_points(
                                int(client.x),
                                int(client.y),
                                target_destination.x,
                                target_destination.y,
                            )
                    count_los_failure = should_count_server_los_failure(
                        combat_categories,
                        target_distance=observed_distance,
                        close_distance=server_los_failure_count_distance(args, action_rotation),
                    )
                    if count_los_failure:
                        active_combat["server_los_failures"] = int(active_combat.get("server_los_failures", 0) or 0) + 1
                    else:
                        actions += add_action(action_counts, "server_range_closing_retry")
                        if "not_visible" in combat_categories:
                            actions += add_action(action_counts, "server_los_far_closing_retry")
                    target_age = now - current_target_since
                    los_failure_grace = max(0.5, float(getattr(args, "server_los_failure_grace", args.target_loss_grace) or 0.0))
                    if (not count_los_failure) or should_retry_server_los_failure(
                        active_combat,
                        now=now,
                        target_age=target_age,
                        los_failure_grace=los_failure_grace,
                        max_retries_after_hit=max(
                            0,
                            int(getattr(args, "server_los_failure_max_retries_after_hit", 8) or 0),
                        ),
                    ):
                        if retry_target is not None:
                            active_combat["target_x"] = int(getattr(retry_target, "x", 0) or 0)
                            active_combat["target_y"] = int(getattr(retry_target, "y", 0) or 0)
                            active_combat["target_z"] = int(getattr(retry_target, "z", 0) or 0)
                            if retry_target_source == "visible_npc":
                                actions += add_action(action_counts, "current_target_visible_refresh")
                            elif retry_target_source == "api":
                                server_target_observations[current_target] = observed_target
                                actions += add_action(action_counts, "current_target_api_refresh")
                            else:
                                actions += add_action(action_counts, "current_target_last_known_refresh")
                            observed_distance = math.hypot(retry_target.x - client.x, retry_target.y - client.y)
                            face_point_for_attack(client, retry_target.x, retry_target.y)
                            client.send_position_update(speed=0.0, target_in_view=True)
                            actions += add_action(action_counts, "current_target_api_face")
                            if observed_distance > max(32.0, float(args.minimum_melee_stop_distance)):
                                chase_speed = combat_chase_movement_speed(args, action_rotation, observed_distance)
                                moved = client.move_towards_position(
                                    retry_target.x,
                                    retry_target.y,
                                    retry_target.z,
                                    step=combat_chase_step(args, action_rotation, observed_distance, smooth_movement_step(args)),
                                    stop_distance=server_los_retry_stop_distance(args, action_rotation),
                                    movement_speed=chase_speed,
                                    min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                                    target_in_view=True,
                                )
                                actions += add_action(
                                    action_counts,
                                    "current_target_api_close_move" if moved else "current_target_api_close_hold",
                                )
                            else:
                                reposition_after_close_server_los_failure(
                                    client,
                                    args,
                                    retry_target,
                                    action_counts,
                                )
                        current_target_last_visible_at = now
                        client.target_object(current_target)
                        send_stick_command_if_due(now, "server_los_failure_retry")
                        client.set_attack_mode(False)
                        actions += add_action(action_counts, "server_los_failure_retry")
                    else:
                        rejected_targets[current_target] = now + max(0.5, float(args.server_los_failure_target_cooldown))
                        kind_cooldown = max(
                            0.0,
                            float(getattr(args, "server_los_failure_kind_cooldown", 0.0) or 0.0),
                        )
                        if kind_cooldown > 0 and not getattr(args, "require_target_name", ""):
                            reject_active_target_kind(now, kind_cooldown)
                        abandoned_target_id = current_target
                        finish_combat("server_los_failure", now)
                        client.clear_target()
                        client.set_attack_mode(False)
                        current_target = 0
                        actions += add_action(action_counts, "server_los_failure_retarget")
                        if last_damage_taken_at > 0.0 and now - last_damage_taken_at <= args.travel_aggro_clear_grace:
                            transition_to(DummyBehaviorState.DropAggroAndRecover, "server_los_failure_drop_aggro", now)
                            clear_shared_leader_target_on_abandon(
                                now,
                                "server_los_failure_drop_aggro",
                                abandoned_target_id,
                            )
                            flee_until = max(
                                flee_until,
                                now + drop_aggro_recovery_duration(args, health_percent=current_health_percent),
                            )
                            next_flee_move = now
                            next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                            flee_wander_heading_hold_until = 0.0
                            flee_destination = flee_escape_destination(args, client)
                            if getattr(args, "flee_use_sprint", True):
                                client.send_command("/sprint")
                                actions += add_action(action_counts, "sprint_escape")
                            actions += add_action(action_counts, "drop_aggro_flee_start")
                            log_encounter_event(
                                "flee_start",
                                now,
                                reason="server_los_failure_drop_aggro",
                                destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                            )

                boss_hazard_duration = boss_hazard_message_duration(args, message.text)
                if boss_hazard_duration > 0:
                    boss_hazard_backoff_until = max(boss_hazard_backoff_until, now + boss_hazard_duration)
                    actions += add_action(action_counts, "boss_hazard_message")
                    message_categories.append("boss_hazard")

                if party_attack_message is not None:
                    party_snapshot = party_state.snapshot()
                    leader_target_id = int(party_snapshot["leader_target_id"])
                    if party_state.update_leader_target_focus_from_attack(
                        party_attack_message.attacker_name,
                        party_attack_message.victim_name,
                    ):
                        actions += add_action(action_counts, "party_boss_focus_message")
                        message_categories.append("boss_focus")
                        party_snapshot = party_state.snapshot()
                    attacker = choose_attack_message_rescue_attacker(
                        client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args)),
                        client,
                        args,
                        leader_target_id,
                        party_attack_message.attacker_name,
                    )
                    objective_add = (
                        is_combat_proven_party_objective_add(args, party_snapshot, attacker)
                        if attacker is not None
                        else False
                    )

                    if attacker is not None and party_state.request_rescue(
                        party_attack_message.victim_name,
                        attacker,
                        leader_target_id=leader_target_id,
                        min_hold=args.party_rescue_min_hold,
                        objective_add=objective_add,
                    ):
                        local_rescue_until = max(local_rescue_until, now + args.party_rescue_max_age)
                        next_party_rescue_request = now + min(args.party_rescue_cooldown, 1.0)
                        actions += add_action(action_counts, "party_rescue_attack_message")
                        message_categories.append("party_attack")
                    elif attacker is not None and party_state.record_rescue_threat(
                        party_attack_message.victim_name,
                        attacker,
                        objective_add=objective_add,
                    ):
                        local_rescue_until = max(local_rescue_until, now + args.party_rescue_max_age)
                        actions += add_action(action_counts, "party_rescue_threat_message")
                        message_categories.append("party_attack")

                combat_text_metric = parse_combat_text_metric(message.text)

                if combat_text_metric is not None:
                    metric_name, amount = combat_text_metric
                    combat_text_totals[metric_name] += amount
                    actions += add_action(action_counts, f"combat_{metric_name}")
                    message_categories.append(metric_name)
                    active_combat_metric_recorded = False
                    if active_combat is not None:
                        active_target_name = normalize_target_name(str(active_combat.get("target_name", "") or ""))
                        normalized_message = normalize_target_name(message.text)
                        if active_target_name and active_target_name in normalized_message:
                            active_combat["last_combat_message_at"] = now
                            current_target_last_visible_at = now
                            if metric_name == "damage_done":
                                active_combat["damage_done"] = int(active_combat.get("damage_done", 0) or 0) + amount
                                active_combat["last_damage_done_at"] = now
                                active_combat["server_los_failures"] = 0
                                active_combat_metric_recorded = True
                            elif metric_name == "damage_taken":
                                active_combat["damage_taken"] = int(active_combat.get("damage_taken", 0) or 0) + amount
                                active_combat_metric_recorded = True

                    if metric_name == "damage_taken" and amount > 0:
                        last_damage_taken_at = now
                        last_incoming_damage_at = now
                        local_rescue_until = max(local_rescue_until, now + args.party_rescue_max_age)
                        attacker_name = parse_incoming_damage_attacker_name(message.text)
                        if attacker_name:
                            last_incoming_damage_attacker_name = attacker_name
                            if active_combat is not None and not active_combat_metric_recorded:
                                active_target_actor = actor_from_active_combat(active_combat)
                                if recent_incoming_damage_matches_actor(
                                    active_target_actor,
                                    attacker_name,
                                    last_damage_at=now,
                                    now=now,
                                    grace_seconds=1.0,
                                ):
                                    active_combat["last_combat_message_at"] = now
                                    current_target_last_visible_at = now
                                    active_combat["damage_taken"] = int(active_combat.get("damage_taken", 0) or 0) + amount
                                else:
                                    active_combat["damage_taken"] = int(active_combat.get("damage_taken", 0) or 0) + amount
                                    active_combat["off_target_damage_taken"] = (
                                        int(active_combat.get("off_target_damage_taken", 0) or 0) + amount
                                    )
                                    active_combat["off_target_attacker_name"] = attacker_name
                        if attacker_name and refresh_exact_rescue_threat_from_attacker_name(
                            party_state,
                            client,
                            args,
                            party_member_name,
                            attacker_name,
                        ):
                            actions += add_action(action_counts, "party_rescue_damage_attacker")
                        if (
                            attacker_name
                            and current_target <= 0
                            and party_state is not None
                            and should_allow_untracked_damage_counterattack(
                                behavior_state,
                                flee_until=flee_until,
                                now=now,
                            )
                        ):
                            damage_party_snapshot = party_state.snapshot()
                            damage_counterattack_actor = choose_incoming_damage_counterattack_target(
                                client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args)),
                                client,
                                args,
                                damage_party_snapshot,
                                member_name=party_member_name,
                                action_rotation=action_rotation,
                                health_percent=current_health_percent,
                                attacker_name=attacker_name,
                                current_target=current_target,
                                behavior_state=behavior_state,
                                rejected_targets=rejected_targets,
                                now=now,
                            )
                            if damage_counterattack_actor is not None:
                                damage_counterattack_intent = target_intent_for_selected_npc(
                                    args,
                                    damage_counterattack_actor,
                                    selected_npc_is_rescue=True,
                                    behavior_state=behavior_state,
                                    recent_incoming_attacker_name=attacker_name,
                                )
                                if (
                                    damage_counterattack_intent == TargetIntent.required_retaliation
                                    and not should_commit_required_retaliation_for_objective(
                                        args,
                                        behavior_state,
                                        required_home_hunt_ready=required_target_home_hunt_ready(client, args),
                                        party_ready_for_objective=party_ready_for_pull(args, party_state)
                                        if party_state is not None
                                        else True,
                                        direct_required_damage_to_active_tank=party_member_is_active_tank(
                                            damage_party_snapshot,
                                            party_member_name,
                                        ),
                                    )
                                ):
                                    actions += add_action(action_counts, "required_target_retaliation_wait_home")
                                    log_encounter_event(
                                        "required_target_retaliation_wait_home",
                                        now,
                                        npc=damage_counterattack_actor,
                                        attacker_name=attacker_name,
                                    )
                                    if should_drop_required_retaliation_before_objective_ready(
                                        args,
                                        behavior_state,
                                        required_home_hunt_ready=required_target_home_hunt_ready(client, args),
                                        party_ready_for_objective=party_ready_for_pull(args, party_state)
                                        if party_state is not None
                                        else True,
                                    ):
                                        start_travel_aggro_drop(
                                            now,
                                            "required_retaliation_wait_home",
                                            npc=damage_counterattack_actor,
                                        )
                                        actions += add_action(action_counts, "required_target_retaliation_drop_aggro")
                                    damage_counterattack_actor = None

                            if damage_counterattack_actor is not None:
                                current_target = int(getattr(damage_counterattack_actor, "object_id", 0) or 0)
                                current_target_intent = damage_counterattack_intent
                                current_target_since = now
                                current_target_last_visible_at = now
                                current_target_removed_preserve_count = 0
                                target_observed_at = now
                                attack_target_in_view_primed_at = 0.0
                                attack_target_in_view_primed_target = 0
                                client.target_object(current_target)
                                face_target_for_attack(client, damage_counterattack_actor)
                                client.send_position_update(speed=0.0, target_in_view=True)
                                client.set_attack_mode(True)
                                if should_publish_damage_counterattack_as_leader_target(
                                    is_party_leader=is_party_leader,
                                    party_state=party_state,
                                    current_target_intent=damage_counterattack_intent,
                                ):
                                    party_state.update_leader(client, damage_counterattack_actor)
                                    party_state.mark_leader_target_engaged(current_target)
                                    actions += add_action(action_counts, "leader_damage_counterattack_shared")
                                if damage_counterattack_intent in {TargetIntent.objective, TargetIntent.required_retaliation}:
                                    transition_to(
                                        DummyBehaviorState.HuntObjective,
                                        "objective_target_selected"
                                        if damage_counterattack_intent == TargetIntent.objective
                                        else "required_target_retaliation",
                                        now,
                                    )
                                if should_start_rescue_counterattack_combat(
                                    active_combat,
                                    current_target,
                                    damage_counterattack_actor,
                                ):
                                    start_combat(
                                        damage_counterattack_actor,
                                        combat_distance_to(client, damage_counterattack_actor),
                                        now,
                                    )
                                local_rescue_until = max(local_rescue_until, now + args.party_rescue_max_age)
                                actions += add_action(action_counts, "incoming_damage_counterattack")
                                actions += add_action(action_counts, "party_rescue_damage_counterattack")
                                log_encounter_event(
                                    "incoming_damage_counterattack",
                                    now,
                                    target_id=current_target,
                                    target_name=str(getattr(damage_counterattack_actor, "name", "") or ""),
                                    current_target_intent=target_intent_value(damage_counterattack_intent),
                                    health_percent=current_health_percent,
                                    recent_incoming_attacker=attacker_name,
                                )
                        request_party_rescue(now, "message")

                log_encounter_event(
                    "server_message",
                    now,
                    chat_type=int(message.chat_type),
                    text=short_text(message.text),
                    categories=message_categories,
                    loot_item=loot_metric.item_name if loot_metric is not None else "",
                    loot_tier=loot_metric.tier if loot_metric is not None else "",
                    combat_metric_name=combat_text_metric[0] if combat_text_metric is not None else "",
                    combat_metric_amount=combat_text_metric[1] if combat_text_metric is not None else 0,
                    party_attack_attacker=party_attack_message.attacker_name if party_attack_message is not None else "",
                    party_attack_victim=party_attack_message.victim_name if party_attack_message is not None else "",
                )

        def request_party_rescue(now: float, reason: str) -> bool:
            nonlocal actions, next_party_rescue_request

            if (
                party_state is None
                or not is_party_follower
                or not args.party_rescue_aggro
                or now < next_party_rescue_request
            ):
                return False

            party_snapshot = party_state.snapshot()
            rescue_is_urgent = reason in {"message", "health_drop"}
            if not should_allow_party_rescue_before_objective_engaged(
                args,
                party_snapshot,
                active_combat,
                now,
                urgent=rescue_is_urgent,
            ):
                actions += add_action(action_counts, "party_rescue_wait_objective_engaged")
                next_party_rescue_request = now + min(args.party_rescue_cooldown, 1.0)
                return False

            leader_target_id = int(party_snapshot["leader_target_id"])
            leader_target = choose_party_assist_target(
                client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args)),
                leader_target_id,
            )

            if leader_target is not None and not is_required_target(args, leader_target):
                rescue_age = party_rescue_target_age(
                    party_snapshot,
                    int(party_snapshot.get("rescue_target_id", 0) or 0),
                    now,
                )

                if rescue_age <= args.party_rescue_min_hold:
                    actions += add_action(action_counts, "party_rescue_leader_busy")
                    next_party_rescue_request = now + min(args.party_rescue_cooldown, 1.0)
                    return False

            attacker = choose_party_rescue_attacker(
                client,
                args,
                leader_target_id,
                party_snapshot=party_snapshot,
                objective_scan_only=reason == "objective_scan",
            )

            if attacker is None:
                if reason == "objective_scan":
                    next_party_rescue_request = now + min(args.party_rescue_cooldown, 1.0)
                return False

            if party_state.request_rescue(
                party_member_name,
                attacker,
                leader_target_id=leader_target_id,
                min_hold=args.party_rescue_min_hold,
                objective_add=is_party_objective_add_rescue_threat(args, party_snapshot, attacker),
            ):
                actions += add_action(action_counts, "party_rescue_request")
                actions += add_action(action_counts, f"party_rescue_{reason}")
                next_party_rescue_request = now + args.party_rescue_cooldown
                return True

            return False

        def start_travel_aggro_drop(now: float, reason: str, *, npc=None) -> None:
            nonlocal actions, current_target, current_target_intent, flee_until, next_flee_move
            nonlocal next_flee_pressure_replan, flee_destination, flee_wander_heading_hold_until
            nonlocal attack_target_in_view_primed_at, attack_target_in_view_primed_target
            nonlocal travel_aggro_danger_x, travel_aggro_danger_y, travel_aggro_danger_z
            nonlocal travel_aggro_danger_until, travel_aggro_repeat_count, travel_aggro_last_at, travel_aggro_last_name

            if (
                npc is not None
                and is_required_target(args, npc)
                and should_commit_required_retaliation_for_objective(
                    args,
                    behavior_state,
                    required_home_hunt_ready=required_target_home_hunt_ready(client, args),
                    party_ready_for_objective=party_ready_for_pull(args, party_state) if party_state is not None else True,
                )
            ):
                current_target_intent = TargetIntent.required_retaliation
                transition_to(DummyBehaviorState.HuntObjective, "required_target_retaliation", now)
                return

            client.set_attack_mode(False)
            if current_target:
                finish_combat("travel_aggro_drop", now)
                client.clear_target()
                current_target = 0
            current_target_intent = TargetIntent.travel_aggro
            attack_target_in_view_primed_at = 0.0
            attack_target_in_view_primed_target = 0
            danger_npc = npc
            if danger_npc is None and last_incoming_damage_attacker_name:
                try:
                    danger_npc = choose_named_rescue_attacker(
                        client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args)),
                        client,
                        args,
                        0,
                        last_incoming_damage_attacker_name,
                    )
                except Exception:
                    danger_npc = None

            danger_name = str(getattr(danger_npc, "name", "") or last_incoming_damage_attacker_name or "")
            if danger_npc is not None:
                danger_x = int(getattr(danger_npc, "x", 0) or getattr(client, "x", 0) or 0)
                danger_y = int(getattr(danger_npc, "y", 0) or getattr(client, "y", 0) or 0)
                danger_z = int(getattr(danger_npc, "z", 0) or getattr(client, "z", 0) or 0)
            else:
                danger_x = int(getattr(client, "x", 0) or 0)
                danger_y = int(getattr(client, "y", 0) or 0)
                danger_z = int(getattr(client, "z", 0) or 0)

            repeat_window = max(1.0, float(getattr(args, "travel_aggro_avoid_seconds", 120.0) or 120.0))
            same_danger = (
                bool(travel_aggro_last_name)
                and normalize_target_name(travel_aggro_last_name) == normalize_target_name(danger_name)
                and travel_aggro_last_at > 0.0
                and now - travel_aggro_last_at <= repeat_window
            )
            travel_aggro_repeat_count = travel_aggro_repeat_count + 1 if same_danger else 1
            travel_aggro_last_at = now
            travel_aggro_last_name = danger_name
            travel_aggro_danger_x = danger_x
            travel_aggro_danger_y = danger_y
            travel_aggro_danger_z = danger_z
            travel_aggro_danger_until = now + repeat_window
            actions += add_action(action_counts, "travel_aggro_avoid_memory")
            log_encounter_event(
                "travel_aggro_avoid_memory",
                now,
                danger_name=danger_name,
                danger_x=danger_x,
                danger_y=danger_y,
                danger_z=danger_z,
                repeat_count=travel_aggro_repeat_count,
                avoid_seconds=round(repeat_window, 3),
            )
            transition_to(DummyBehaviorState.HandleTravelAggro, reason, now)
            transition_to(DummyBehaviorState.DropAggroAndRecover, "drop_aggro_and_recover", now)
            clear_shared_leader_target_on_abandon(now, reason)
            flee_until = max(
                flee_until,
                now + max(args.flee_duration, float(getattr(args, "travel_aggro_clear_grace", 0.0) or 0.0)),
            )
            next_flee_move = now
            next_flee_pressure_replan = now + max(3.0, args.flee_move_interval * 6.0)
            flee_destination = flee_escape_destination(args, client)
            flee_wander_heading_hold_until = 0.0
            if getattr(args, "flee_use_sprint", True):
                client.send_command("/sprint")
                actions += add_action(action_counts, "sprint_escape")
            if flee_destination is not None:
                outcome, flee_actions = move_towards_flee_destination(
                    client,
                    args,
                    path_state,
                    action_counts,
                    flee_destination,
                )
                actions += flee_actions
                actions += add_action(
                    action_counts,
                    "travel_aggro_immediate_flee_move" if outcome.moved else "travel_aggro_immediate_flee_hold",
                )
                record_movement_failure(movement_failures, client, flee_destination, outcome, "travel_aggro_immediate_flee")
                if outcome.moved:
                    next_flee_move = now + args.flee_move_interval + rng.uniform(0, args.jitter)
            actions += add_action(action_counts, "travel_aggro_drop")
            actions += add_action(action_counts, "flee_start")
            log_encounter_event(
                "flee_start",
                now,
                reason=reason,
                destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                target_id=int(getattr(npc, "object_id", 0) or 0) if npc is not None else 0,
                target_name=str(getattr(npc, "name", "") or "") if npc is not None else "",
                current_target_intent=current_target_intent.value,
            )
            speak_state_change(now, "flee", "state: dropping travel aggro")

        initial_state = initial_behavior_state_for_objective(
            client,
            args,
            is_party_leader=is_party_leader,
            current_target=current_target,
        )
        transition_to(initial_state, "startup_complete", time.monotonic())

        while time.monotonic() < end_time:
            now = time.monotonic()
            if party_state is not None:
                if is_party_leader:
                    party_state.update_leader(client)
                else:
                    party_state.update_member(party_member_name, client)
            consume_removed_objects(now)
            consume_messages(now)

            if args.live_control_file and now >= next_live_control_check:
                next_live_control_check = now + max(0.2, float(args.live_control_interval or 0.0))
                live_payload, live_mtime_ns = read_live_control_payload(args.live_control_file)
                if live_payload is not None:
                    revision = live_control_revision(live_payload, live_mtime_ns)
                    if revision != last_live_control_revision:
                        last_live_control_revision = revision
                        updates = apply_live_control_overrides(args, live_payload)
                        commands_to_send = live_payload.get("commands", live_payload.get("command", []))
                        if isinstance(commands_to_send, str):
                            commands_to_send = [commands_to_send]
                        sent_commands = []
                        if isinstance(commands_to_send, list):
                            for live_command in commands_to_send:
                                if not isinstance(live_command, str) or not live_command.strip():
                                    continue
                                client.send_command(live_command.strip())
                                sent_commands.append(live_command.strip())
                                actions += add_action(action_counts, "live_control_command")
                        say_text = live_payload.get("say", "")
                        if isinstance(say_text, str) and say_text.strip():
                            client.send_command(format_say_command(say_text))
                            sent_commands.append("/say")
                            actions += add_action(action_counts, "live_control_say")
                        feedback_reason = str(
                            live_payload.get("behavior_feedback")
                            or live_payload.get("watcher_feedback")
                            or live_payload.get("feedback_reason")
                            or ""
                        ).strip()
                        if feedback_reason:
                            feedback_state = state_after_watcher_feedback(behavior_state, feedback_reason)
                            if behavior_state_value(feedback_state) != behavior_state.value:
                                feedback_npc = current_visible_target_npc()
                                if (
                                    feedback_state == DummyBehaviorState.HandleTravelAggro
                                    and feedback_npc is not None
                                    and should_handle_travel_aggro_target(
                                        args,
                                        behavior_state,
                                        feedback_npc,
                                        current_target_intent,
                                    )
                                ):
                                    start_travel_aggro_drop(now, f"watcher_feedback_{feedback_reason}", npc=feedback_npc)
                                else:
                                    transition_to(DummyBehaviorState(behavior_state_value(feedback_state)), f"watcher_feedback_{feedback_reason}", now)
                                actions += add_action(action_counts, "live_control_behavior_feedback")
                        if updates or sent_commands:
                            log_encounter_event(
                                "live_control_applied",
                                now,
                                revision=revision,
                                updates={key: {"old": old, "new": new} for key, (old, new) in updates.items()},
                                command_count=len(sent_commands),
                            )

            if objective_complete_at <= 0.0 and party_state is not None:
                party_completion_snapshot = party_state.snapshot()
                shared_completed_at = float(party_completion_snapshot.get("objective_completed_at", 0.0) or 0.0)
                if shared_completed_at > 0.0:
                    objective_complete_at = shared_completed_at
                    completed_target_id = int(party_completion_snapshot.get("objective_complete_target_id", 0) or 0)
                    completed_target_name = str(party_completion_snapshot.get("objective_complete_name", "") or "")
                    if current_target:
                        finish_combat("party_objective_complete", now)
                        client.clear_target()
                        current_target = 0
                    client.set_attack_mode(False)
                    actions += add_action(action_counts, "required_target_complete_shared")
                    log_encounter_event(
                        "required_target_complete_shared",
                        now,
                        completed_target_id=completed_target_id,
                        completed_target_name=completed_target_name,
                        loot_wait_seconds=args.target_removed_loot_wait,
                    )

            if objective_complete_at > 0:
                if current_target:
                    client.clear_target()
                    current_target = 0
                client.set_attack_mode(False)
                send_ping_if_due(now)
                send_position_heartbeat(now)
                client.drain(args.tick)
                if now - objective_complete_at >= args.target_removed_loot_wait:
                    consume_messages(time.monotonic())
                    actions += add_action(action_counts, "required_target_complete_exit")
                    break
                continue

            current_health_percent = int(getattr(client, "health_percent", 100) or 0)
            party_snapshot_for_tick = party_state.snapshot() if party_state is not None else {}
            required_target_api_observation = refresh_required_target_from_api(now, party_snapshot_for_tick)
            if required_target_api_observation is not None and party_state is not None:
                party_snapshot_for_tick = party_state.snapshot()
            if should_refresh_party_melee_survival_backoff(args, current_health_percent):
                party_melee_survival_backoff_until = max(
                    party_melee_survival_backoff_until,
                    now + args.party_melee_survival_backoff_duration,
                )
            party_melee_survival_backoff = (
                party_state is not None
                and should_back_off_for_party_melee_survival(
                    args,
                    party_snapshot_for_tick,
                    party_member_name,
                    action_rotation,
                    current_health_percent,
                    now,
                    party_melee_survival_backoff_until,
                )
            )
            boss_hazard_backoff = (
                party_state is not None
                and should_back_off_for_boss_hazard(
                    args,
                    party_snapshot_for_tick,
                    party_member_name,
                    action_rotation,
                    now=now,
                    hazard_until=boss_hazard_backoff_until,
                )
            )
            party_survival_backoff = (
                party_state is not None
                and should_back_off_for_party_encounter_survival(
                    args,
                    party_snapshot_for_tick,
                    party_member_name,
                    action_rotation,
                    now=now,
                )
            )
            local_required_focus_backoff = (
                required_target_api_observation is not None
                and bool(getattr(args, "party_focus_target_backoff", False))
                and normalize_target_name(required_target_api_observation.target) == normalize_target_name(party_member_name)
                and not party_member_is_active_tank(party_snapshot_for_tick, party_member_name)
            )
            party_focus_target_backoff = (
                party_state is not None
                and (
                    should_back_off_for_party_focus_target(
                        args,
                        party_snapshot_for_tick,
                        party_member_name,
                        now=now,
                    )
                    or local_required_focus_backoff
                )
            )
            party_focus_pressure_backoff = (
                party_state is not None
                and should_back_off_for_party_focus_pressure(
                    args,
                    party_snapshot_for_tick,
                    party_member_name,
                    action_rotation,
                    now=now,
                )
            )
            log_encounter_tick_if_due(
                now,
                party_snapshot=party_snapshot_for_tick,
                party_melee_survival_backoff=party_melee_survival_backoff,
                boss_hazard_backoff=boss_hazard_backoff,
                party_survival_backoff=party_survival_backoff,
                party_focus_target_backoff=party_focus_target_backoff,
                party_focus_pressure_backoff=party_focus_pressure_backoff,
            )
            current_target_for_precast = next(
                (
                    npc
                    for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
                    if npc.object_id == current_target
                ),
                None,
            )
            current_target_distance_for_precast = (
                combat_distance_to(client, current_target_for_precast)
                if current_target_for_precast is not None
                else float("inf")
            )
            ranged_safety_backoff_due = (
                current_target_for_precast is not None
                and current_target > 0
                and should_back_off_from_boss_target(
                    args,
                    action_rotation,
                    current_target_distance_for_precast,
                )
            )
            ranged_target_backoff_due = (
                current_target_for_precast is not None
                and current_target > 0
                and should_back_off_for_ranged_combat_target(
                    args,
                    action_rotation,
                    current_target_distance_for_precast,
                )
            )
            hurt_member_for_precast = (
                choose_party_heal_target(party_state, args, exclude_name=party_member_name)
                if is_party_follower and action_rotation == "healer-support" and args.party_heal_leader_interval > 0
                else None
            )
            healer_heal_due = (
                is_party_follower
                and action_rotation == "healer-support"
                and args.party_heal_leader_interval > 0
                and now >= next_party_heal
                and party_heal_target_in_cast_range(client, args, hurt_member_for_precast)
            )
            healer_buff_due = (
                is_party_follower
                and action_rotation == "healer-support"
                and args.party_buff_interval > 0
                and args.party_buff_spell_levels
                and now >= next_party_buff
                and bool(party_state.buff_targets(exclude_name=party_member_name))
            )
            precast_movement_hold = should_hold_precast_movement(
                args,
                action_rotation,
                combat_plan=combat_plan,
                heal_due=healer_heal_due,
                buff_due=healer_buff_due,
                offensive_due=bool(current_target and now >= next_skill),
                current_target_distance=current_target_distance_for_precast,
                tactical_backoff=(
                    party_melee_survival_backoff
                    or boss_hazard_backoff
                    or party_survival_backoff
                    or party_focus_target_backoff
                    or party_focus_pressure_backoff
                    or ranged_safety_backoff_due
                ),
            )
            previous_health_percent = last_health_percent
            travel_aggro_damage_due = False
            if (
                current_health_percent > 0
                and last_health_percent > 0
                and current_health_percent < last_health_percent
            ):
                local_rescue_until = max(local_rescue_until, now + args.party_rescue_max_age)
                visible_for_damage = client.visible_npcs(
                    max_age=args.npc_max_age,
                    include_peace=should_scan_peace_npcs(args),
                )
                travel_aggro_damage_due = should_handle_travel_aggro_damage(
                    args,
                    behavior_state,
                    last_incoming_damage_attacker_name,
                    attacker_level=visible_npc_level_by_name(visible_for_damage, last_incoming_damage_attacker_name),
                    player_level=int(getattr(args, "player_level", 0) or 0),
                    health_percent=current_health_percent,
                    previous_health_percent=last_health_percent,
                )
                if not travel_aggro_damage_due and request_party_rescue(now, "health_drop"):
                    actions += add_action(action_counts, "party_rescue_health_drop_detected")
            elif (
                party_state is not None
                and is_party_follower
                and args.party_rescue_aggro
                and should_preserve_party_target_on_loss(args)
                and action_rotation != "healer-support"
                and now >= next_party_rescue_request
            ):
                request_party_rescue(now, "objective_scan")
            last_health_percent = current_health_percent

            if should_force_drop_aggro_for_critical_health(
                args,
                behavior_state,
                health_percent=current_health_percent,
            ):
                abandoned_target_id = current_target
                client.set_attack_mode(False)
                current_target = 0
                current_target_intent = TargetIntent.none
                client.clear_target()
                finish_combat("critical_health_drop_aggro", now)
                transition_to(DummyBehaviorState.DropAggroAndRecover, "critical_health_drop_aggro", now)
                clear_shared_leader_target_on_abandon(now, "critical_health_drop_aggro", abandoned_target_id)
                attack_target_in_view_primed_at = 0.0
                attack_target_in_view_primed_target = 0
                flee_until = max(flee_until, now + max(args.flee_duration, args.low_health_rest_min, 1.0))
                next_flee_move = now
                next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                flee_destination = flee_escape_destination(args, client)
                flee_wander_heading_hold_until = 0.0
                actions += add_action(action_counts, "critical_health_drop_aggro")
                if getattr(args, "flee_use_sprint", True):
                    client.send_command("/sprint")
                    actions += add_action(action_counts, "sprint_escape")
                actions += add_action(action_counts, "flee_start")
                log_encounter_event(
                    "flee_start",
                    now,
                    reason="critical_health_drop_aggro",
                    health_percent=current_health_percent,
                    previous_health_percent=previous_health_percent,
                    destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                )
                speak_state_change(now, "flee", "state: critical health escape")
                send_ping_if_due(now)
                send_position_heartbeat(now)
                client.drain(args.tick)
                continue

            if travel_aggro_damage_due:
                start_travel_aggro_drop(now, "travel_non_objective_aggro_damage")
                send_ping_if_due(now)
                send_position_heartbeat(now)
                client.drain(args.tick)
                continue

            if stand_after_rest and now >= rest_until:
                if should_extend_recovery_rest(args, health_percent=current_health_percent):
                    rest_until = now + max(args.low_health_rest_min, 1.0)
                    actions += add_action(action_counts, "low_health_rest_extend")
                    log_encounter_event("low_health_rest_extend", now, health_percent=current_health_percent)
                else:
                    stand_after_rest = False
                    client.send_command("/stand")
                    transition_to(
                        next_state_after_rest_recovery_completion(
                            args,
                            client,
                            is_party_leader=is_party_leader,
                            current_target=current_target,
                        ),
                        "rest_complete",
                        now,
                    )
                    actions += add_action(action_counts, "stand")

            if should_complete_timed_rest_recovery(
                behavior_state,
                rest_until=rest_until,
                stand_after_rest=stand_after_rest,
                now=now,
            ):
                rest_until = 0.0
                transition_to(
                    next_state_after_rest_recovery_completion(
                        args,
                        client,
                        is_party_leader=is_party_leader,
                        current_target=current_target,
                    ),
                    "rest_complete",
                    now,
                )
                actions += add_action(action_counts, "rest_complete")
                log_encounter_event("rest_complete", now, health_percent=current_health_percent)

            if now < rest_until:
                if should_abort_rest_for_death(is_dead=client.is_dead, rest_until=rest_until, now=now):
                    rest_until = 0.0
                    stand_after_rest = False
                    actions += add_action(action_counts, "rest_abort_death")
                elif should_flee_rest_pressure(
                    args,
                    current_health_percent=current_health_percent,
                    last_health_percent=previous_health_percent,
                    local_rescue_until=local_rescue_until,
                    now=now,
                ):
                    rest_until = 0.0
                    stand_after_rest = False
                    client.send_command("/stand")
                    client.set_attack_mode(False)
                    abandoned_target_id = current_target
                    current_target = 0
                    client.clear_target()
                    finish_combat("flee", now)
                    flee_until = now + args.flee_duration
                    next_flee_move = now
                    next_flee_pressure_replan = now + max(3.0, args.flee_move_interval * 6.0)
                    flee_destination = flee_escape_destination(args, client)
                    flee_wander_heading_hold_until = 0.0
                    transition_to(state_after_flee_start(behavior_state), "rest_pressure", now)
                    clear_shared_leader_target_on_abandon(now, "rest_pressure", abandoned_target_id)
                    actions += add_action(action_counts, "flee_rest_pressure")
                    if getattr(args, "flee_use_sprint", True):
                        client.send_command("/sprint")
                        actions += add_action(action_counts, "sprint_escape")
                    actions += add_action(action_counts, "flee_start")
                    log_encounter_event(
                        "flee_start",
                        now,
                        reason="rest_pressure",
                        health_percent=current_health_percent,
                        previous_health_percent=previous_health_percent,
                        destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                    )
                    speak_state_change(now, "flee", "state: fleeing to town")
                elif (
                    stand_after_rest
                    and args.low_health_rest_resume_percent > 0
                    and current_health_percent >= args.low_health_rest_resume_percent
                ):
                    rest_until = 0.0
                    stand_after_rest = False
                    client.send_command("/stand")
                    transition_to(
                        next_state_after_rest_recovery_completion(
                            args,
                            client,
                            is_party_leader=is_party_leader,
                            current_target=current_target,
                        ),
                        "low_health_rest_complete",
                        now,
                    )
                    actions += add_action(action_counts, "low_health_rest_complete")
                elif should_healer_prioritize_party_heal_during_rest(
                    args,
                    action_rotation=action_rotation,
                    current_health_percent=current_health_percent,
                    hurt_member=hurt_member_for_precast,
                ):
                    rest_until = 0.0
                    stand_after_rest = False
                    client.send_command("/stand")
                    next_party_heal = min(next_party_heal, now)
                    actions += add_action(action_counts, "party_critical_heal_abort_rest")
                    log_encounter_event(
                        "party_critical_heal_abort_rest",
                        now,
                        health_percent=current_health_percent,
                        heal_target=hurt_member_for_precast.get("name", "") if isinstance(hurt_member_for_precast, dict) else "",
                        heal_target_health=hurt_member_for_precast.get("health_percent", 0) if isinstance(hurt_member_for_precast, dict) else 0,
                    )
                elif should_healer_self_preserve_during_rest(
                    args,
                    action_rotation=action_rotation,
                    current_health_percent=current_health_percent,
                    now=now,
                    next_self_preserve_heal=next_self_preserve_heal,
                ):
                    heal_action = perform_healer_self_preserve_cast(client, rng, args, combat_plan)
                    if heal_action is not None:
                        actions += add_action(action_counts, heal_action)
                        next_self_preserve_heal = now + max(args.party_heal_leader_interval, args.party_friendly_cast_target_hold, 1.8)
                        rest_until = max(rest_until, now + max(args.party_friendly_cast_target_hold, 1.0))
                        stand_after_rest = True
                        log_encounter_event(
                            "self_preserve_heal",
                            now,
                            health_percent=current_health_percent,
                            action=heal_action,
                        )
                    send_ping_if_due(now)
                    send_position_heartbeat(now)
                    client.drain(args.tick)
                    continue
                elif should_healer_abort_rest_for_party_heal(
                    args,
                    action_rotation=action_rotation,
                    current_health_percent=current_health_percent,
                    hurt_member=hurt_member_for_precast,
                ):
                    rest_until = 0.0
                    stand_after_rest = False
                    client.send_command("/stand")
                    next_party_heal = min(next_party_heal, now)
                    actions += add_action(action_counts, "party_heal_abort_rest")
                    log_encounter_event(
                        "party_heal_abort_rest",
                        now,
                        health_percent=current_health_percent,
                        heal_target=hurt_member_for_precast.get("name", "") if isinstance(hurt_member_for_precast, dict) else "",
                        heal_target_health=hurt_member_for_precast.get("health_percent", 0) if isinstance(hurt_member_for_precast, dict) else 0,
                    )
                else:
                    send_ping_if_due(now)
                    send_position_heartbeat(now)
                    client.drain(args.tick)
                    continue

            extend_threat_snapshot = (
                flee_threat_snapshot(args, client, member_name=party_member_name)
                if flee_until > 0 and now >= flee_until and flee_destination is not None
                else None
            )
            if should_extend_flee(
                args,
                health_percent=current_health_percent,
                flee_until=flee_until,
                now=now,
                flee_destination=flee_destination,
                previous_health_percent=previous_health_percent,
                recent_damage_age_seconds=(now - last_damage_taken_at if last_damage_taken_at > 0.0 else None),
                active_threat=flee_threat_snapshot_is_active(extend_threat_snapshot),
            ):
                flee_until = now + max(args.flee_duration, args.low_health_rest_min, 1.0)
                next_flee_move = now
                next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                flee_wander_heading_hold_until = 0.0
                actions += add_action(action_counts, "flee_extend")
                log_encounter_event("flee_extend", now, health_percent=current_health_percent)

            party_snapshot_for_untracked_damage = (
                party_state.snapshot()
                if party_state is not None and party_member_is_active_tank(party_state.snapshot(), party_member_name)
                else None
            )
            if (
                party_snapshot_for_untracked_damage is not None
                and current_target <= 0
                and current_health_percent > 0
                and previous_health_percent > 0
                and current_health_percent < previous_health_percent
            ):
                party_ready_for_objective = party_ready_for_pull(args, party_state)
                force_flee_from_health_drop = should_force_flee_from_non_required_health_drop(
                    args,
                    current_health_percent=current_health_percent,
                    previous_health_percent=previous_health_percent,
                    last_damage_attacker_name=last_incoming_damage_attacker_name,
                )
                if should_commit_required_target_from_recent_damage(
                    args,
                    current_health_percent=current_health_percent,
                    previous_health_percent=previous_health_percent,
                    current_target=current_target,
                    last_damage_attacker_name=last_incoming_damage_attacker_name,
                    party_ready_for_objective=party_ready_for_objective,
                    required_home_hunt_ready=required_target_home_hunt_ready(client, args),
                    behavior_state=behavior_state,
                ):
                    visible_required_actor = choose_required_visible_target(
                        client,
                        client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args)),
                        args,
                    )
                    if visible_required_actor is not None:
                        current_target = int(getattr(visible_required_actor, "object_id", 0) or 0)
                        current_target_intent = TargetIntent.required_retaliation
                        current_target_since = now
                        current_target_last_visible_at = now
                        target_observed_at = now
                        client.target_object(current_target)
                        client.set_attack_mode(True)
                        transition_to(DummyBehaviorState.HuntObjective, "required_target_retaliation", now)
                        required_target_x = int(getattr(visible_required_actor, "x", 0) or 0)
                        required_target_y = int(getattr(visible_required_actor, "y", 0) or 0)
                        if required_target_x or required_target_y:
                            face_point_for_attack(client, required_target_x, required_target_y)
                        if should_start_rescue_counterattack_combat(active_combat, current_target, visible_required_actor):
                            start_combat(
                                visible_required_actor,
                                combat_distance_to(client, visible_required_actor),
                                now,
                            )
                        actions += add_action(action_counts, "required_target_damage_counterattack")
                        log_encounter_event(
                            "required_target_damage_counterattack",
                            now,
                            target_id=current_target,
                            target_name=str(getattr(visible_required_actor, "name", "") or ""),
                            health_percent=current_health_percent,
                            recent_incoming_attacker=last_incoming_damage_attacker_name,
                        )

                objective_counterattack_actor = None if current_target > 0 or force_flee_from_health_drop else party_objective_actor_from_snapshot_for_counterattack(
                    args,
                    party_snapshot_for_untracked_damage,
                    member_name=party_member_name,
                    action_rotation=action_rotation,
                    health_percent=current_health_percent,
                    behavior_state=behavior_state,
                    required_home_hunt_ready=required_target_home_hunt_ready(client, args),
                    party_ready_for_objective=party_ready_for_objective,
                )
                if objective_counterattack_actor is not None:
                    objective_counterattack_intent = target_intent_for_selected_npc(
                        args,
                        objective_counterattack_actor,
                        selected_npc_is_rescue=False,
                        behavior_state=behavior_state,
                        recent_incoming_attacker_name=last_incoming_damage_attacker_name,
                    )
                    if not should_allow_counterattack_for_behavior_state(
                        behavior_state,
                        args,
                        objective_counterattack_actor,
                        objective_counterattack_intent,
                    ):
                        actions += add_action(action_counts, "drop_aggro_counterattack_suppressed")
                        log_encounter_event(
                            "drop_aggro_counterattack_suppressed",
                            now,
                            target_id=int(getattr(objective_counterattack_actor, "object_id", 0) or 0),
                            target_name=str(getattr(objective_counterattack_actor, "name", "") or ""),
                            current_target_intent=target_intent_value(objective_counterattack_intent),
                        )
                        objective_counterattack_actor = None
                if objective_counterattack_actor is not None:
                    current_target = int(getattr(objective_counterattack_actor, "object_id", 0) or 0)
                    current_target_intent = objective_counterattack_intent
                    current_target_since = now
                    current_target_last_visible_at = now
                    target_observed_at = now
                    client.target_object(current_target)
                    client.set_attack_mode(True)
                    objective_target_x = int(getattr(objective_counterattack_actor, "x", 0) or 0)
                    objective_target_y = int(getattr(objective_counterattack_actor, "y", 0) or 0)
                    if objective_target_x or objective_target_y:
                        face_point_for_attack(client, objective_target_x, objective_target_y)
                    if should_start_rescue_counterattack_combat(active_combat, current_target, objective_counterattack_actor):
                        start_combat(
                            objective_counterattack_actor,
                            combat_distance_to(client, objective_counterattack_actor),
                            now,
                        )
                    actions += add_action(action_counts, "party_objective_damage_counterattack")
                    log_encounter_event(
                        "party_objective_damage_counterattack",
                        now,
                        target_id=current_target,
                        target_name=str(getattr(objective_counterattack_actor, "name", "") or ""),
                        health_percent=current_health_percent,
                    )

                rescue_counterattack_actor = None if current_target > 0 or force_flee_from_health_drop else party_rescue_actor_from_snapshot(
                    args,
                    party_snapshot_for_untracked_damage,
                    member_name=party_member_name,
                    action_rotation=action_rotation,
                    health_percent=current_health_percent,
                    now=now,
                )
                if rescue_counterattack_actor is not None:
                    rescue_counterattack_intent = target_intent_for_selected_npc(
                        args,
                        rescue_counterattack_actor,
                        selected_npc_is_rescue=True,
                        behavior_state=behavior_state,
                        recent_incoming_attacker_name=last_incoming_damage_attacker_name,
                    )
                    if not should_allow_counterattack_for_behavior_state(
                        behavior_state,
                        args,
                        rescue_counterattack_actor,
                        rescue_counterattack_intent,
                    ):
                        actions += add_action(action_counts, "drop_aggro_counterattack_suppressed")
                        log_encounter_event(
                            "drop_aggro_counterattack_suppressed",
                            now,
                            target_id=int(getattr(rescue_counterattack_actor, "object_id", 0) or 0),
                            target_name=str(getattr(rescue_counterattack_actor, "name", "") or ""),
                            current_target_intent=target_intent_value(rescue_counterattack_intent),
                        )
                        rescue_counterattack_actor = None
                if rescue_counterattack_actor is not None:
                    current_target = int(getattr(rescue_counterattack_actor, "object_id", 0) or 0)
                    current_target_intent = rescue_counterattack_intent
                    current_target_since = now
                    current_target_last_visible_at = now
                    target_observed_at = now
                    client.target_object(current_target)
                    client.set_attack_mode(True)
                    rescue_target_x = int(getattr(rescue_counterattack_actor, "x", 0) or 0)
                    rescue_target_y = int(getattr(rescue_counterattack_actor, "y", 0) or 0)
                    if rescue_target_x or rescue_target_y:
                        face_point_for_attack(client, rescue_target_x, rescue_target_y)
                    if should_start_rescue_counterattack_combat(active_combat, current_target, rescue_counterattack_actor):
                        start_combat(
                            rescue_counterattack_actor,
                            combat_distance_to(client, rescue_counterattack_actor),
                            now,
                        )
                    local_rescue_until = max(local_rescue_until, now + args.party_rescue_max_age)
                    actions += add_action(action_counts, "party_rescue_damage_counterattack")
                    log_encounter_event(
                        "party_rescue_damage_counterattack",
                        now,
                        target_id=current_target,
                        target_name=str(getattr(rescue_counterattack_actor, "name", "") or ""),
                        health_percent=current_health_percent,
                    )
            elif (
                party_snapshot_for_untracked_damage is not None
                and should_abandon_party_rescue_counterattack_for_flee(
                    args,
                    party_snapshot_for_untracked_damage,
                    current_target=current_target,
                    current_health_percent=current_health_percent,
                    previous_health_percent=previous_health_percent,
                )
            ):
                client.set_attack_mode(False)
                current_target = 0
                client.clear_target()
                actions += add_action(action_counts, "party_rescue_counterattack_failed_flee")
                log_encounter_event(
                    "party_rescue_counterattack_failed_flee",
                    now,
                    health_percent=current_health_percent,
                )

            if should_flee_untracked_damage(
                args,
                current_health_percent=current_health_percent,
                last_health_percent=previous_health_percent,
                current_target=current_target,
                flee_until=flee_until,
                now=now,
                party_rescue_target_id=(
                    int(party_snapshot_for_untracked_damage.get("rescue_target_id", 0) or 0)
                    if party_snapshot_for_untracked_damage is not None
                    else 0
                ),
                last_damage_attacker_name=last_incoming_damage_attacker_name,
                party_ready_for_objective=party_ready_for_pull(args, party_state) if party_state is not None else True,
                force_flee_from_health_drop=should_force_flee_from_non_required_health_drop(
                    args,
                    current_health_percent=current_health_percent,
                    previous_health_percent=previous_health_percent,
                    last_damage_attacker_name=last_incoming_damage_attacker_name,
                ),
            ):
                client.set_attack_mode(False)
                abandoned_target_id = current_target
                current_target = 0
                client.clear_target()
                finish_combat("flee", now)
                flee_until = now + args.flee_duration
                next_flee_move = now
                next_flee_pressure_replan = now + max(3.0, args.flee_move_interval * 6.0)
                flee_destination = flee_escape_destination(args, client)
                flee_wander_heading_hold_until = 0.0
                transition_to(state_after_flee_start(behavior_state), "untracked_damage", now)
                clear_shared_leader_target_on_abandon(now, "untracked_damage", abandoned_target_id)
                actions += add_action(action_counts, "flee_untracked_damage")
                if getattr(args, "flee_use_sprint", True):
                    client.send_command("/sprint")
                    actions += add_action(action_counts, "sprint_escape")
                actions += add_action(action_counts, "flee_start")
                log_encounter_event(
                    "flee_start",
                    now,
                    reason="untracked_damage",
                    health_percent=current_health_percent,
                    previous_health_percent=previous_health_percent,
                    destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                )
                speak_state_change(now, "flee", "state: fleeing to safety")

            if (
                args.low_health_rest_percent > 0
                and not current_target
                and not client.is_dead
                and current_health_percent > 0
                and current_health_percent <= args.low_health_rest_percent
                and now >= flee_until
                and not should_healer_prioritize_party_heal_during_rest(
                    args,
                    action_rotation=action_rotation,
                    current_health_percent=current_health_percent,
                    hurt_member=hurt_member_for_precast,
                )
                and (
                    should_recover_before_required_target_home(args, health_percent=current_health_percent)
                    or not should_return_home_before_low_health_rest(client, args)
                )
            ):
                threat_snapshot = flee_threat_snapshot(args, client, member_name=party_member_name)
                recent_damage_age_seconds = (
                    now - last_damage_taken_at if last_damage_taken_at > 0.0 else None
                )
                if should_flee_instead_of_low_health_rest(
                    args,
                    current_health_percent=current_health_percent,
                    previous_health_percent=previous_health_percent,
                    recent_damage_age_seconds=recent_damage_age_seconds,
                    active_threat=flee_threat_snapshot_is_active(threat_snapshot),
                ):
                    client.set_attack_mode(False)
                    abandoned_target_id = current_target
                    current_target = 0
                    client.clear_target()
                    finish_combat("flee", now)
                    flee_until = now + args.flee_duration
                    next_flee_move = now
                    next_flee_pressure_replan = now + max(3.0, args.flee_move_interval * 6.0)
                    flee_destination = flee_escape_destination(args, client)
                    flee_wander_heading_hold_until = 0.0
                    flee_reason = "nearby_threat" if flee_threat_snapshot_is_active(threat_snapshot) else "recent_damage"
                    transition_to(state_after_flee_start(behavior_state), flee_reason, now)
                    clear_shared_leader_target_on_abandon(now, flee_reason, abandoned_target_id)
                    actions += add_action(action_counts, "flee_threat_pressure")
                    if getattr(args, "flee_use_sprint", True):
                        client.send_command("/sprint")
                        actions += add_action(action_counts, "sprint_escape")
                    actions += add_action(action_counts, "flee_start")
                    log_encounter_event(
                        "flee_start",
                        now,
                        reason="nearby_threat" if flee_threat_snapshot_is_active(threat_snapshot) else "recent_damage",
                        health_percent=current_health_percent,
                        previous_health_percent=previous_health_percent,
                        recent_damage_age_seconds=recent_damage_age_seconds,
                        destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                        **(threat_snapshot or {}),
                    )
                else:
                    client.set_attack_mode(False)
                    client.send_command("/sit")
                    rest_until = now + rng.uniform(args.low_health_rest_min, args.low_health_rest_max)
                    stand_after_rest = True
                    transition_to(DummyBehaviorState.RestRecover, "low_health_rest", now)
                    actions += add_action(action_counts, "low_health_rest")
                    log_encounter_event("low_health_rest", now, health_percent=current_health_percent)
                send_ping_if_due(now)
                send_position_heartbeat(now)
                client.drain(args.tick)
                continue

            if client.is_dead:
                if not death_seen:
                    death_seen = True
                    death_release_after = now + args.death_release_delay
                    next_death_release = death_release_after
                    transition_to(DummyBehaviorState.DeadReleaseRecover, "death_detected", now)
                    if not should_preserve_party_target_on_loss(args):
                        reject_active_target_kind(now, args.target_death_cooldown)
                    finish_combat("player_death", now)
                    current_target = 0
                    if (
                        is_party_leader
                        and party_state is not None
                        and not should_preserve_party_target_on_loss(args)
                    ):
                        party_state.clear_leader_target()
                    client.set_attack_mode(False)
                    if hasattr(client, "send_corpse_position_update"):
                        client.send_corpse_position_update()
                        corpse_position_sent = True
                        actions += add_action(action_counts, "corpse_position")
                    actions += add_action(action_counts, "death_detected")
                    log_encounter_event("death_detected", now)

                if args.auto_release_on_death and now >= next_death_release:
                    client.send_command("/release")
                    actions += add_action(action_counts, "death_release")
                    next_death_release = now + args.death_recovery_cooldown
                    log_encounter_event("death_release", now)
                elif not corpse_position_sent and hasattr(client, "send_corpse_position_update"):
                    client.send_corpse_position_update()
                    corpse_position_sent = True
                    actions += add_action(action_counts, "corpse_position")
                    log_encounter_event("corpse_position", now)

                send_ping_if_due(now)
                send_position_heartbeat(now)
                client.drain(args.tick)
                continue

            if death_seen and not client.is_dead:
                death_seen = False
                corpse_position_sent = False
                actions += add_action(action_counts, "death_recovered")
                log_encounter_event("death_recovered", now)

                if should_escape_after_death_recovery(args):
                    rest_until = 0.0
                    stand_after_rest = False
                    client.set_attack_mode(False)
                    if current_target:
                        client.clear_target()
                    current_target = 0
                    current_target_intent = TargetIntent.none
                    attack_target_in_view_primed_at = 0.0
                    attack_target_in_view_primed_target = 0
                    transition_to(DummyBehaviorState.DropAggroAndRecover, "death_recovered_escape", now)
                    flee_until = max(
                        flee_until,
                        now
                        + max(
                            float(getattr(args, "flee_duration", 0.0) or 0.0),
                            float(getattr(args, "low_health_rest_min", 0.0) or 0.0),
                            float(getattr(args, "post_release_rest", 0.0) or 0.0),
                            1.0,
                        ),
                    )
                    next_flee_move = now
                    next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                    flee_destination = flee_escape_destination(args, client)
                    flee_wander_heading_hold_until = 0.0
                    if getattr(args, "flee_use_sprint", True):
                        client.send_command("/sprint")
                        actions += add_action(action_counts, "sprint_escape")
                    if flee_destination is not None:
                        outcome, flee_actions = move_towards_flee_destination(
                            client,
                            args,
                            path_state,
                            action_counts,
                            flee_destination,
                        )
                        actions += flee_actions
                        actions += add_action(
                            action_counts,
                            "death_recovered_immediate_flee_move" if outcome.moved else "death_recovered_immediate_flee_hold",
                        )
                        record_movement_failure(
                            movement_failures,
                            client,
                            flee_destination,
                            outcome,
                            "death_recovered_immediate_flee",
                        )
                        if outcome.moved:
                            next_flee_move = now + args.flee_move_interval + rng.uniform(0, args.jitter)
                    actions += add_action(action_counts, "death_recovered_escape")
                    actions += add_action(action_counts, "flee_start")
                    log_encounter_event(
                        "flee_start",
                        now,
                        reason="death_recovered_escape",
                        health_percent=current_health_percent,
                        destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                    )
                    speak_state_change(now, "flee", "state: escaping after release")
                else:
                    rest_until = now + args.post_release_rest
                    transition_to(DummyBehaviorState.RestRecover, "death_recovered", now)
                client.drain(args.tick)
                continue

            send_position_heartbeat(now)

            recent_incoming_melee_for_current_target = False
            if current_target:
                incoming_actor = current_visible_target_npc()
                if incoming_actor is None and active_combat is not None:
                    incoming_actor = actor_from_active_combat(active_combat)
                recent_incoming_melee_for_current_target = recent_incoming_damage_matches_actor(
                    incoming_actor,
                    last_incoming_damage_attacker_name,
                    last_damage_at=last_incoming_damage_at,
                    now=now,
                    grace_seconds=float(getattr(args, "incoming_damage_melee_grace", 4.0) or 4.0),
                )
                if (
                    not recent_incoming_melee_for_current_target
                    and active_combat is not None
                    and int(active_combat.get("damage_taken", 0) or 0) > 0
                    and last_damage_taken_at > 0.0
                    and now - last_damage_taken_at <= float(getattr(args, "incoming_damage_melee_grace", 4.0) or 4.0)
                ):
                    recent_incoming_melee_for_current_target = True

            losing_combat_flee_due = (
                current_target
                and should_flee_losing_combat(
                    args,
                    active_combat,
                    health_percent=int(getattr(client, "health_percent", 0) or 0),
                    now=now,
                )
            )
            multi_aggro_flee_due = (
                current_target
                and should_flee_multi_aggro_combat(
                    args,
                    active_combat,
                    health_percent=int(getattr(client, "health_percent", 0) or 0),
                )
            )
            multi_aggro_counterattack_hold = (
                multi_aggro_flee_due
                and should_hold_initial_required_retaliation_multi_aggro(
                    args,
                    active_combat,
                    current_target_intent=current_target_intent,
                    is_active_tank=party_state is not None
                    and party_member_is_active_tank(party_state.snapshot(), party_member_name),
                    health_percent=int(getattr(client, "health_percent", 0) or 0),
                    now=now,
                )
            )
            counterattack_hold = (
                losing_combat_flee_due
                and not multi_aggro_flee_due
                and should_delay_early_flee_for_melee_counterattack(
                    args,
                    active_combat,
                    health_percent=int(getattr(client, "health_percent", 0) or 0),
                    recent_incoming_melee=recent_incoming_melee_for_current_target,
                    target_distance=combat_distance_to(client, incoming_actor) if incoming_actor is not None else 0.0,
                )
            )
            if counterattack_hold or multi_aggro_counterattack_hold:
                log_encounter_event(
                    "early_flee_counterattack_hold",
                    now,
                    recent_incoming_melee=bool(recent_incoming_melee_for_current_target),
                    recent_incoming_attacker=last_incoming_damage_attacker_name,
                    multi_aggro=bool(multi_aggro_counterattack_hold),
                )
            if (
                (losing_combat_flee_due or multi_aggro_flee_due)
                and not counterattack_hold
                and not multi_aggro_counterattack_hold
            ):
                reject_active_target_kind(now, args.target_retreat_cooldown)
                next_flee_destination = (
                    flee_escape_destination_for_combat(args, client, active_combat)
                )
                abandoned_target_id = current_target
                finish_combat("flee", now)
                current_target = 0
                client.clear_target()
                client.set_attack_mode(False)
                flee_until = now + args.flee_duration
                next_flee_move = now
                next_flee_pressure_replan = now + max(3.0, args.flee_move_interval * 6.0)
                flee_destination = next_flee_destination
                flee_wander_heading_hold_until = 0.0
                if next_flee_destination is not None and destination_kind(next_flee_destination) == "flee-safe":
                    flee_damage_replan_suppressed_until = now + 10.0
                    next_flee_pressure_replan = max(next_flee_pressure_replan, flee_damage_replan_suppressed_until)
                flee_reason = "multi_aggro" if multi_aggro_flee_due else "losing_combat"
                transition_to(state_after_flee_start(behavior_state), flee_reason, now)
                clear_shared_leader_target_on_abandon(now, flee_reason, abandoned_target_id)
                if getattr(args, "flee_use_sprint", True):
                    client.send_command("/sprint")
                    actions += add_action(action_counts, "sprint_escape")
                actions += add_action(action_counts, "flee_start")
                log_encounter_event(
                    "flee_start",
                    now,
                    health_percent=int(getattr(client, "health_percent", 0) or 0),
                    reason="multi_aggro" if multi_aggro_flee_due else "losing_combat",
                    destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                    recent_incoming_melee=bool(recent_incoming_melee_for_current_target),
                    recent_incoming_attacker=last_incoming_damage_attacker_name,
                    off_target_attacker=str(active_combat.get("off_target_attacker_name", "") or "") if active_combat else "",
                )
                speak_state_change(now, "flee", "state: fleeing to town")

            if now < flee_until:
                if now >= next_flee_move:
                    if flee_destination is not None:
                        recent_flee_damage_age = (
                            now - last_damage_taken_at if last_damage_taken_at > 0.0 else None
                        )
                        if should_replan_flee_safe_after_recent_damage(
                            args,
                            flee_destination,
                            health_percent=current_health_percent,
                            recent_damage_age_seconds=recent_flee_damage_age,
                            damage_seen_at=last_damage_taken_at,
                            last_replanned_damage_at=last_flee_damage_replan_at,
                        ) and now >= flee_damage_replan_suppressed_until:
                            updated_destination = flee_escape_destination(args, client)
                            if updated_destination is not None:
                                flee_destination = updated_destination
                                last_flee_damage_replan_at = last_damage_taken_at
                                flee_until = max(flee_until, now + max(args.flee_duration, args.low_health_rest_min, 1.0))
                                next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                                flee_wander_heading_hold_until = 0.0
                                actions += add_action(action_counts, "flee_damage_replan")
                                log_encounter_event(
                                    "flee_damage_replan",
                                    now,
                                    health_percent=current_health_percent,
                                    recent_damage_age_seconds=round(recent_flee_damage_age or 0.0, 3),
                                    destination=destination_kind(flee_destination),
                                )
                        pressure_snapshot = flee_threat_snapshot(args, client, member_name=party_member_name)
                        if (
                            now >= next_flee_pressure_replan
                            and now >= flee_damage_replan_suppressed_until
                            and should_replan_flee_safe_under_pressure(
                            args,
                            flee_destination,
                            health_percent=current_health_percent,
                            threat_snapshot=pressure_snapshot,
                            )
                        ):
                            updated_destination = flee_escape_destination(args, client)
                            if updated_destination is not None:
                                flee_destination = updated_destination
                                flee_until = max(flee_until, now + max(args.flee_duration, args.low_health_rest_min, 1.0))
                                next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                                flee_wander_heading_hold_until = 0.0
                                actions += add_action(action_counts, "flee_threat_pressure")
                                log_encounter_event(
                                    "flee_threat_pressure",
                                    now,
                                    health_percent=current_health_percent,
                                    destination=destination_kind(flee_destination),
                                    **(pressure_snapshot or {}),
                                )
                        outcome, flee_actions = move_towards_flee_destination(
                            client,
                            args,
                            path_state,
                            action_counts,
                            flee_destination,
                        )
                        actions += flee_actions
                        if outcome.arrived:
                            health_percent = int(getattr(client, "health_percent", 0) or 0)
                            recent_arrival_damage_age = (
                                now - last_damage_taken_at if last_damage_taken_at > 0.0 else None
                            )
                            if should_replan_flee_home_after_arrival(
                                args,
                                flee_destination,
                                health_percent=health_percent,
                                previous_health_percent=previous_health_percent,
                                recent_damage_age_seconds=recent_arrival_damage_age,
                            ):
                                updated_destination = flee_home_overrun_destination(args, client, flee_destination)
                                if updated_destination is not None:
                                    flee_destination = updated_destination
                                    flee_until = now + max(args.flee_duration, args.low_health_rest_min, 1.0)
                                    next_flee_move = now
                                    next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                                    flee_wander_heading_hold_until = 0.0
                                    actions += add_action(action_counts, "flee_home_overrun")
                                    log_encounter_event(
                                        "flee_home_overrun",
                                        now,
                                        health_percent=health_percent,
                                        recent_damage_age_seconds=round(recent_arrival_damage_age or 0.0, 3),
                                        destination=destination_kind(flee_destination),
                                    )
                            elif should_replan_flee_safe_after_arrival(
                                args,
                                flee_destination,
                                health_percent=health_percent,
                                previous_health_percent=previous_health_percent,
                                recent_damage_age_seconds=recent_arrival_damage_age,
                            ):
                                flee_destination = flee_escape_destination(args, client)
                                flee_until = now + max(args.flee_duration, args.low_health_rest_min, 1.0)
                                next_flee_move = now
                                next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                                flee_wander_heading_hold_until = 0.0
                                actions += add_action(action_counts, "flee_safe_replan")
                                log_encounter_event(
                                    "flee_safe_replan",
                                    now,
                                    health_percent=health_percent,
                                    destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                                )
                            elif should_overrun_flee_home(args, health_percent=health_percent):
                                flee_destination = None
                                next_flee_move = now
                                flee_wander_heading_hold_until = 0.0
                                actions += add_action(action_counts, "flee_home_overrun")
                                log_encounter_event(
                                    "flee_home_overrun",
                                    now,
                                    health_percent=health_percent,
                                )
                            else:
                                threat_snapshot = flee_threat_snapshot(args, client, member_name=party_member_name)
                                if should_continue_flee_for_active_threat(threat_snapshot):
                                    flee_destination = flee_escape_destination(args, client)
                                    flee_until = now + max(args.flee_duration, args.low_health_rest_min, 1.0)
                                    next_flee_move = now
                                    next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                                    flee_wander_heading_hold_until = 0.0
                                    actions += add_action(action_counts, "flee_threat_pressure")
                                    log_encounter_event(
                                        "flee_threat_pressure",
                                        now,
                                        health_percent=health_percent,
                                        destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                                        **threat_snapshot,
                                    )
                                else:
                                    next_recovery_state = next_state_after_drop_aggro_recovery(
                                        args,
                                        health_percent=health_percent,
                                        now=now,
                                        last_damage_taken_at=last_damage_taken_at,
                                        active_threat=False,
                                    )
                                    if (
                                        behavior_state == DummyBehaviorState.DropAggroAndRecover
                                        and next_recovery_state == DummyBehaviorState.DropAggroAndRecover
                                    ):
                                        clear_remaining = drop_aggro_clear_grace_remaining(
                                            args,
                                            now=now,
                                            last_damage_taken_at=last_damage_taken_at,
                                        )
                                        flee_until = max(
                                            flee_until,
                                            now
                                            + drop_aggro_clear_hold_duration(
                                                args,
                                                clear_remaining=clear_remaining,
                                                health_percent=health_percent,
                                            ),
                                        )
                                        next_flee_move = now + args.flee_move_interval + rng.uniform(0, args.jitter)
                                        actions += add_action(action_counts, "flee_clear_grace_hold")
                                        log_encounter_event(
                                            "flee_clear_grace_hold",
                                            now,
                                            health_percent=health_percent,
                                            clear_remaining=round(clear_remaining, 3),
                                            destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                                        )
                                    elif should_rest_after_flee_recovery(args, health_percent=health_percent):
                                        client.send_command("/sit")
                                        stand_after_rest = True
                                        rest_until = max(rest_until, now + max(args.low_health_rest_max, args.low_health_rest_min, 1.0))
                                        transition_to(DummyBehaviorState.RestRecover, "flee_recovered_rest", now)
                                        actions += add_action(action_counts, "low_health_rest")
                                        log_encounter_event("low_health_rest", now, health_percent=health_percent, reason="flee_recovered")
                                    else:
                                        rest_until = max(rest_until, now + max(args.low_health_rest_min, 1.0))
                                        transition_to(next_recovery_state, "flee_recovered", now)
                                    if next_recovery_state != DummyBehaviorState.DropAggroAndRecover:
                                        flee_until = 0.0
                                        actions += add_action(action_counts, "flee_recovered")
                                        log_encounter_event("flee_recovered", now, health_percent=health_percent)
                                        speak_state_change(now, "flee_recovered", "state: reached safety")
                    else:
                        if should_refresh_flee_wander_heading(now=now, hold_until=flee_wander_heading_hold_until):
                            flee_wander_heading = (heading + rng.randrange(768, 1536)) & 0x0FFF
                            flee_wander_heading_hold_until = now + max(args.flee_duration * 0.5, 4.0)
                            actions += add_action(action_counts, "flee_heading_refresh")
                        heading = flee_wander_heading
                        client.wander(
                            heading,
                            step=args.flee_step,
                            movement_speed=getattr(args, "flee_movement_speed", None),
                            min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                        )
                        actions += add_action(action_counts, "flee_move")
                    next_flee_move = now + args.flee_move_interval + rng.uniform(0, args.jitter)

                client.drain(args.tick)
                continue

            if flee_destination is not None:
                current_health_percent = int(getattr(client, "health_percent", 0) or 0)
                threat_snapshot = flee_threat_snapshot(args, client, member_name=party_member_name)
                if should_extend_flee_after_duration(threat_snapshot):
                    if flee_destination is not None and destination_kind(flee_destination) == "flee-home":
                        updated_destination = flee_home_overrun_destination(args, client, flee_destination)
                    else:
                        updated_destination = flee_escape_destination(args, client)
                    if updated_destination is not None:
                        flee_destination = updated_destination
                    flee_until = now + max(args.flee_duration, args.low_health_rest_min, 1.0)
                    next_flee_move = now
                    next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                    flee_wander_heading_hold_until = 0.0
                    actions += add_action(action_counts, "flee_threat_pressure")
                    log_encounter_event(
                        "flee_threat_pressure",
                        now,
                        health_percent=current_health_percent,
                        destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                        **(threat_snapshot or {}),
                    )
                    client.drain(args.tick)
                    continue
                if should_rest_after_flee_recovery(args, health_percent=current_health_percent):
                    client.send_command("/sit")
                    stand_after_rest = True
                    rest_until = max(rest_until, now + max(args.low_health_rest_max, args.low_health_rest_min, 1.0))
                    transition_to(DummyBehaviorState.RestRecover, "flee_finished_recovery", now)
                    actions += add_action(action_counts, "low_health_rest")
                    actions += add_action(action_counts, "flee_recovered")
                    log_encounter_event(
                        "low_health_rest",
                        now,
                        health_percent=current_health_percent,
                        reason="flee_finished_recovery",
                    )
                    log_encounter_event("flee_recovered", now, health_percent=current_health_percent)
                    speak_state_change(now, "flee_recovered", "state: reached safety")
                    flee_destination = None
                    client.drain(args.tick)
                    continue
                next_recovery_state = next_state_after_drop_aggro_recovery(
                    args,
                    health_percent=current_health_percent,
                    now=now,
                    last_damage_taken_at=last_damage_taken_at,
                    active_threat=False,
                )
                if (
                    behavior_state == DummyBehaviorState.DropAggroAndRecover
                    and next_recovery_state == DummyBehaviorState.DropAggroAndRecover
                ):
                    clear_remaining = drop_aggro_clear_grace_remaining(
                        args,
                        now=now,
                        last_damage_taken_at=last_damage_taken_at,
                    )
                    flee_until = now + drop_aggro_clear_hold_duration(
                        args,
                        clear_remaining=clear_remaining,
                        health_percent=current_health_percent,
                    )
                    next_flee_move = now
                    actions += add_action(action_counts, "flee_clear_grace_hold")
                    log_encounter_event(
                        "flee_clear_grace_hold",
                        now,
                        health_percent=current_health_percent,
                        clear_remaining=round(clear_remaining, 3),
                        destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                    )
                    client.drain(args.tick)
                    continue

                transition_to(next_recovery_state, "flee_finished", now)
                actions += add_action(action_counts, "flee_recovered")
                log_encounter_event("flee_recovered", now, health_percent=current_health_percent)
                speak_state_change(now, "flee_recovered", "state: reached safety")
                actions += add_action(action_counts, "flee_finished")
                log_encounter_event("flee_finished", now, health_percent=current_health_percent)
                flee_destination = None

            if friendly_cast_hold_until > 0 and now >= friendly_cast_hold_until:
                if friendly_cast_restore_target:
                    client.target_object(friendly_cast_restore_target)
                    actions += add_action(action_counts, "friendly_cast_retarget_enemy")

                friendly_cast_hold_until = 0.0
                friendly_cast_restore_target = 0

            friendly_cast_tactical_backoff = friendly_cast_hold_breaking_backoff(
                party_melee_survival_backoff=bool(party_melee_survival_backoff),
                boss_hazard_backoff=bool(boss_hazard_backoff),
                party_survival_backoff=bool(party_survival_backoff),
                party_focus_target_backoff=bool(party_focus_target_backoff),
                party_focus_pressure_backoff=bool(party_focus_pressure_backoff),
                ranged_safety_backoff_due=bool(ranged_safety_backoff_due),
            )
            if should_hold_friendly_cast_target(
                friendly_cast_hold_until=friendly_cast_hold_until,
                now=now,
                tactical_backoff=bool(friendly_cast_tactical_backoff),
            ):
                client.set_attack_mode(False)
                actions += add_action(action_counts, "friendly_cast_target_hold")
                send_ping_if_due(now)
                send_position_heartbeat(now)
                client.drain(args.tick)
                continue

            if should_continue_cast_action_hold(cast_action_hold_until, now):
                client.set_attack_mode(False)
                actions += add_action(action_counts, "cast_action_hold")
                send_ping_if_due(now)
                send_position_heartbeat(now)
                client.drain(args.tick)
                continue

            if now >= next_rest_check:
                if (
                    should_allow_scheduled_rest(behavior_state, current_target)
                    and args.rest_chance > 0
                    and rng.random() < args.rest_chance
                ):
                    rest_until = now + rng.uniform(args.rest_min, args.rest_max)
                    client.set_attack_mode(False)
                    transition_to(DummyBehaviorState.RestRecover, "scheduled_rest", now)
                    actions += add_action(action_counts, "rest")

                next_rest_check = now + rng.uniform(3.0, 8.0)

            if args.ai_player and args.long_rest_chance > 0 and now >= next_long_rest and not current_target:
                if rng.random() < args.long_rest_chance:
                    client.send_command("/sit")
                    rest_until = now + rng.uniform(args.long_rest_min, args.long_rest_max)
                    stand_after_rest = True
                    transition_to(DummyBehaviorState.RestRecover, "long_rest", now)
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
                    client.send_command(format_say_command(rng.choice(args.player_greet_lines)))
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
                followed_player_this_tick = False
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
                    followed_player_this_tick = bool(
                        outcome.moved or not getattr(args, "follow_player_hold_allows_waypoint", False)
                    )

                next_player_follow = now + args.player_follow_interval + rng.uniform(0, args.jitter)
            else:
                followed_player_this_tick = False

            if args.waypoints and args.waypoint_interval > 0 and now >= next_waypoint_move and not current_target and not followed_player_this_tick:
                if should_approach_required_target_home(
                    args,
                    is_party_leader=is_party_leader,
                    current_target=current_target,
                ) and should_move_to_required_target_home(
                    client,
                    args,
                    is_party_leader=is_party_leader,
                    current_target=current_target,
                ):
                    actions += add_action(action_counts, "waypoint_wait_required_home")
                elif should_suppress_party_follower_waypoint(
                    args,
                    party_state,
                    is_party_follower=is_party_follower,
                    current_target=current_target,
                ):
                    actions += add_action(action_counts, "party_follower_waypoint_suppressed")
                else:
                    waypoint_index = advance_continuous_waypoint_index(client, args, waypoint_index)
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
                and should_run_smooth_combat_movement(args, action_rotation, current_target, party_state)
                and (args.move or args.hunter)
                and args.smooth_move_interval > 0
                and now >= next_smooth_move
            ):
                target_npc = next(
                    (
                        npc
                        for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
                        if npc.object_id == current_target
                    ),
                    None,
                )
                if target_npc is None and current_target > 0:
                    target_observation = server_target_observations.get(current_target)
                    refresh_interval = max(
                        0.0,
                        float(getattr(args, "current_target_api_refresh_interval", 0.0) or 0.0),
                    )
                    if (
                        getattr(args, "current_target_api_refresh", False)
                        and (
                            target_observation is None
                            or now - target_observation.last_seen >= refresh_interval
                        )
                    ):
                        refreshed_target = fetch_current_target_observation(
                            args,
                            api_region_for_client(args, client),
                            current_target,
                        )
                        if refreshed_target is not None:
                            target_observation = refreshed_target
                            server_target_observations[current_target] = refreshed_target
                            if active_combat is not None:
                                active_combat["target_x"] = refreshed_target.x
                                active_combat["target_y"] = refreshed_target.y
                                active_combat["target_z"] = refreshed_target.z
                            actions += add_action(action_counts, "hunter_target_api_refresh_lost")
                    if fresh_hunter_target_observation(args, target_observation, now):
                        target_npc = actor_from_target_observation(target_observation)
                        actions += add_action(action_counts, "hunter_target_api_chase")
                support_evasion_threat = (
                    choose_party_support_evasion_threat(
                        client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args)),
                        client,
                        args,
                        party_snapshot_for_tick,
                        action_rotation=action_rotation,
                        now=now,
                        local_rescue_until=local_rescue_until,
                        precast_movement_hold=precast_movement_hold,
                    )
                    if party_state is not None
                    else None
                )

                if support_evasion_threat is not None:
                    client.set_attack_mode(False)
                    moved = move_away_from_actor(
                        client,
                        support_evasion_threat,
                        step=smooth_movement_step(args),
                        min_distance=party_focus_target_backoff_distance(args, action_rotation),
                        args=args,
                        target_in_view=False,
                    )
                    actions += add_action(action_counts, "party_support_evasion_backoff" if moved else "party_support_evasion_hold")
                    log_attack_decision(
                        now,
                        False,
                        "support_evasion_threat",
                        npc=support_evasion_threat,
                        party_snapshot=party_snapshot_for_tick,
                        distance=round(combat_distance_to(client, support_evasion_threat), 2),
                    )
                elif precast_movement_hold:
                    client.set_attack_mode(False)
                    if target_npc is not None:
                        face_target_for_attack(client, target_npc)
                    actions += add_action(action_counts, "precast_movement_hold")
                    log_attack_decision(
                        now,
                        False,
                        "precast_movement_hold",
                        npc=target_npc,
                        party_snapshot=party_snapshot_for_tick,
                        distance=round(combat_distance_to(client, target_npc), 2) if target_npc is not None else 0.0,
                    )
                elif (
                    target_npc is not None
                    and target_home_leash_violation(client, args, target_npc)[0]
                    and not current_target_bypasses_target_home_leash(args, party_snapshot_for_tick, current_target)
                ):
                    violated, leash_reason, leash_distance = target_home_leash_violation(client, args, target_npc)
                    if violated:
                        rejected_targets[current_target] = now + min(args.target_failure_cooldown, 5.0)
                        abandoned_target_id = current_target
                        finish_combat("target_home_leash", now, combat_distance_to(client, target_npc))
                        log_encounter_event(
                            "target_home_leash_rejected",
                            now,
                            npc=target_npc,
                            leash_reason=leash_reason,
                            leash_distance=round(leash_distance, 2),
                        )
                        client.clear_target()
                        client.set_attack_mode(False)
                        current_target = 0
                        clear_shared_leader_target_on_abandon(now, "target_home_leash", abandoned_target_id)
                        actions += add_action(action_counts, "target_home_leash")
                elif target_npc is not None:
                    target_observation = server_target_observations.get(current_target)
                    refresh_interval = max(
                        0.0,
                        float(getattr(args, "current_target_api_refresh_interval", 0.0) or 0.0),
                    )
                    if (
                        getattr(args, "current_target_api_refresh", False)
                        and refresh_interval > 0
                        and (
                            target_observation is None
                            or now - target_observation.last_seen >= refresh_interval
                        )
                    ):
                        refreshed_target = fetch_current_target_observation(
                            args,
                            api_region_for_client(args, client),
                            current_target,
                        )
                        if refreshed_target is not None:
                            target_observation = refreshed_target
                            server_target_observations[current_target] = refreshed_target
                            if active_combat is not None:
                                active_combat["target_x"] = refreshed_target.x
                                active_combat["target_y"] = refreshed_target.y
                                active_combat["target_z"] = refreshed_target.z
                            actions += add_action(action_counts, "current_target_api_refresh_visible")
                    if (
                        target_observation is not None
                        and now - target_observation.last_seen <= args.current_target_api_max_age
                    ):
                        target_npc = target_actor_with_server_observation(target_npc, target_observation)
                    target_destination = destination_from_actor("target", target_npc)
                    distance = combat_distance_to(client, target_npc)
                    if should_abort_overextended_combat(args, active_combat, distance, now - current_target_since):
                        rejected_targets[current_target] = now + min(args.target_failure_cooldown, 5.0)
                        finish_combat("combat_chase_overextended", now, distance)
                        log_encounter_event(
                            "combat_chase_overextended",
                            now,
                            npc=target_npc,
                            distance=round(distance, 2),
                            target_age=round(now - current_target_since, 3),
                        )
                        client.clear_target()
                        client.set_attack_mode(False)
                        current_target = 0
                        actions += add_action(action_counts, "combat_chase_overextended")
                        continue
                    party_boss_melee_backoff = should_back_off_for_party_boss_melee_limit(
                        args,
                        party_snapshot_for_tick,
                        party_member_name,
                        action_rotation,
                        current_target,
                    )
                    visible_ranged_target_backoff = ranged_target_backoff_due or should_back_off_for_ranged_combat_target(
                        args,
                        action_rotation,
                        distance,
                    )
                    tactical_backoff_reason, tactical_backoff_distance = party_smooth_tactical_backoff_reason_and_distance(
                        args,
                        action_rotation,
                        party_melee_survival_backoff=bool(party_melee_survival_backoff),
                        boss_hazard_backoff=bool(boss_hazard_backoff),
                        party_focus_target_backoff=bool(party_focus_target_backoff),
                        party_focus_pressure_backoff=bool(party_focus_pressure_backoff),
                        party_boss_melee_backoff=bool(party_boss_melee_backoff),
                        party_survival_backoff=bool(party_survival_backoff),
                        ranged_safety_backoff_due=bool(ranged_safety_backoff_due),
                        ranged_target_backoff_due=bool(visible_ranged_target_backoff),
                    )
                    tactical_backoff = bool(tactical_backoff_reason)
                    attack_enabled = (
                        False
                        if tactical_backoff
                        else should_enable_attack_mode(args, action_rotation, distance)
                    )
                    if tactical_backoff:
                        client.set_attack_mode(False)
                    else:
                        face_target_for_attack(client, target_npc)
                    if (
                        party_state is not None
                        and should_preserve_party_target_on_loss(args)
                        and is_required_target(args, target_npc)
                    ):
                        party_state.update_shared_target(target_npc, engaged=False)
                    if tactical_backoff:
                        moved = move_away_from_actor(
                            client,
                            target_npc,
                            step=smooth_movement_step(args),
                            min_distance=tactical_backoff_distance,
                            args=args,
                            target_in_view=True,
                        )
                        if tactical_backoff_reason == "boss_hazard":
                            actions += add_action(action_counts, "boss_hazard_backoff" if moved else "boss_hazard_hold")
                        elif tactical_backoff_reason == "party_focus_target":
                            actions += add_action(action_counts, "party_focus_target_backoff" if moved else "party_focus_target_hold")
                        elif tactical_backoff_reason == "party_focus_pressure":
                            actions += add_action(action_counts, "party_focus_pressure_backoff" if moved else "party_focus_pressure_hold")
                        elif tactical_backoff_reason == "boss_ranged":
                            actions += add_action(action_counts, "boss_ranged_backoff" if moved else "boss_ranged_hold")
                        elif tactical_backoff_reason == "ranged_target":
                            actions += add_action(action_counts, "ranged_target_backoff" if moved else "ranged_target_hold")
                        elif tactical_backoff_reason == "party_boss_melee":
                            actions += add_action(action_counts, "party_boss_melee_backoff" if moved else "party_boss_melee_hold")
                        elif tactical_backoff_reason == "party_survival":
                            actions += add_action(
                                action_counts,
                                "party_survival_backoff" if moved else "party_survival_hold",
                            )
                        else:
                            actions += add_action(
                                action_counts,
                                "party_melee_survival_backoff" if moved else "party_melee_survival_hold",
                            )
                    else:
                        target_step = smooth_movement_step(args)
                        target_step = combat_chase_step(args, action_rotation, distance, target_step)
                        target_movement_speed = combat_chase_movement_speed(args, action_rotation, distance)
                        target_step = active_tank_reaggro_chase_step(
                            args,
                            party_snapshot_for_tick,
                            party_member_name,
                            action_rotation,
                            target_npc,
                            distance=distance,
                            base_step=target_step,
                            now=now,
                        )
                        if distance <= float(getattr(args, "combat_direct_move_distance", 0.0) or 0.0):
                            moved = client.move_towards_position(
                                target_destination.x,
                                target_destination.y,
                                target_destination.z,
                                step=target_step,
                                stop_distance=combat_stop_distance(args, action_rotation),
                                movement_speed=target_movement_speed,
                                min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                                target_in_view=attack_enabled,
                            )
                            outcome = MovementOutcome(moved=moved, arrived=not moved)
                            actions += add_action(action_counts, "combat_direct_move" if moved else "combat_direct_hold")
                        else:
                            outcome = move_towards_destination(
                                client,
                                target_destination,
                                step=target_step,
                                stop_distance=combat_stop_distance(args, action_rotation),
                                args=args,
                                path_state=path_state,
                                action_counts=action_counts,
                                target_in_view=attack_enabled,
                            )
                        actions += outcome.actions
                        record_movement_failure(movement_failures, client, target_destination, outcome, "smooth_target")
                        actions += add_action(action_counts, "smooth_move" if outcome.moved else "smooth_hold")
                    distance = combat_distance_to(client, target_npc)

                    if active_combat is not None:
                        active_combat["end_distance"] = distance

                    effective_attack_distance = effective_attack_distance_for_recent_incoming_damage(
                        args,
                        action_rotation,
                        target_npc,
                        distance=distance,
                        recent_incoming_attacker_name=last_incoming_damage_attacker_name,
                        last_incoming_damage_at=last_incoming_damage_at,
                        now=now,
                    )
                    recent_incoming_melee = effective_attack_distance < distance
                    action_distance = attack_action_distance(action_rotation, distance, effective_attack_distance)
                    attack_enabled = (
                        False
                        if tactical_backoff
                        else should_enable_attack_mode(args, action_rotation, action_distance)
                    )
                    if attack_enabled:
                        face_target_for_attack(client, target_npc)
                        send_face_command_if_due(now, "attack_visible", target_destination)
                        client.target_object(current_target)
                        actions += add_action(action_counts, "target_refresh_in_view")
                        client.send_position_update(speed=0.0, target_in_view=True)
                        actions += add_action(action_counts, "attack_target_in_view_update")
                        prime_delay = attack_target_in_view_prime_delay(
                            args,
                            recent_incoming_melee=recent_incoming_melee,
                        )
                        newly_primed = attack_target_in_view_primed_target != current_target
                        if newly_primed:
                            attack_target_in_view_primed_target = current_target
                            attack_target_in_view_primed_at = now
                        if should_wait_for_attack_target_prime(
                            primed_target=attack_target_in_view_primed_target,
                            current_target=current_target,
                            primed_at=attack_target_in_view_primed_at,
                            now=now,
                            prime_delay=prime_delay,
                        ):
                            client.set_attack_mode(False)
                            actions += add_action(
                                action_counts,
                                "attack_target_in_view_prime" if newly_primed else "attack_target_in_view_prime_wait",
                            )
                            attack_enabled = False
                        else:
                            client.set_attack_mode(True)
                            actions += add_action(action_counts, "attack_on")
                    else:
                        client.set_attack_mode(False)
                        actions += add_action(action_counts, "attack_off")
                    if active_combat is not None and should_count_attack_attempt(
                        args,
                        action_rotation,
                        attack_enabled=attack_enabled,
                        action_distance=action_distance,
                    ):
                        active_combat["attacks"] = int(active_combat["attacks"]) + 1
                    if (
                        is_party_leader
                        and party_state is not None
                        and should_preserve_party_target_on_loss(args)
                        and is_required_target(args, target_npc)
                        and should_mark_leader_target_engaged(
                            args,
                            action_rotation,
                            attack_enabled=attack_enabled,
                            action_distance=action_distance,
                        )
                    ):
                        party_state.mark_leader_target_engaged(current_target)
                    reaggro_taunt_due = should_active_tank_reaggro_taunt(
                        args,
                        party_snapshot_for_tick,
                        party_member_name,
                        action_rotation,
                        now=now,
                        next_taunt=next_active_tank_reaggro_taunt,
                    )
                    if (
                        not party_melee_survival_backoff
                        and not boss_hazard_backoff
                        and not party_focus_target_backoff
                        and not party_focus_pressure_backoff
                        and not party_boss_melee_backoff
                        and not party_survival_backoff
                    ):
                        prefer_taunt_skill = should_prefer_taunt_skill_for_target(
                            args,
                            party_snapshot_for_tick,
                            member_name=party_member_name,
                            action_rotation=action_rotation,
                            selected_npc_is_rescue=False,
                            selected_npc_is_required=is_required_target(args, target_npc),
                            reaggro_taunt_due=reaggro_taunt_due,
                        )
                        rotation_action, next_skill, next_active_tank_reaggro_taunt = perform_due_rotation_action(
                            client,
                            rng,
                            args,
                            action_rotation,
                            action_distance,
                            combat_plan,
                            active_combat=active_combat,
                            now=now,
                            next_skill=next_skill,
                            reaggro_taunt_due=reaggro_taunt_due,
                            prefer_taunt_skill=prefer_taunt_skill,
                            next_active_tank_reaggro_taunt=next_active_tank_reaggro_taunt,
                        )
                        if rotation_action is not None:
                            actions += add_action(action_counts, rotation_action)
                            cast_hold_seconds = effective_cast_action_hold_seconds(args, rotation_action)
                            if cast_hold_seconds > 0:
                                cast_action_hold_until = now + cast_hold_seconds
                                actions += add_action(action_counts, "cast_action_hold_start")
                        if reaggro_taunt_due:
                            actions += add_action(action_counts, "party_active_tank_reaggro_taunt")
                    log_attack_decision(
                        now,
                        attack_enabled,
                        "smooth_visible_target",
                        npc=target_npc,
                        party_snapshot=party_snapshot_for_tick,
                        distance=round(distance, 2),
                        tactical_backoff=bool(tactical_backoff),
                        party_melee_survival_backoff=bool(party_melee_survival_backoff),
                        boss_hazard_backoff=bool(boss_hazard_backoff),
                        party_focus_target_backoff=bool(party_focus_target_backoff),
                        party_focus_pressure_backoff=bool(party_focus_pressure_backoff),
                        party_boss_melee_backoff=bool(party_boss_melee_backoff),
                        party_survival_backoff=bool(party_survival_backoff),
                        ranged_safety_backoff_due=bool(ranged_safety_backoff_due),
                        tactical_backoff_reason=tactical_backoff_reason,
                        effective_attack_distance=round(effective_attack_distance, 2),
                        recent_incoming_melee=bool(recent_incoming_melee),
                        recent_incoming_attacker=last_incoming_damage_attacker_name,
                    )
                elif args.party_assist_only and party_state is not None:
                    party_snapshot = party_state.snapshot()

                    tactical_backoff = (
                        party_melee_survival_backoff
                        or boss_hazard_backoff
                        or party_focus_target_backoff
                        or party_focus_pressure_backoff
                        or party_survival_backoff
                    )
                    if tactical_backoff:
                        client.set_attack_mode(False)
                        log_attack_decision(
                            now,
                            False,
                            "smooth_last_known_tactical_backoff",
                            party_snapshot=party_snapshot,
                            tactical_backoff=True,
                            party_melee_survival_backoff=bool(party_melee_survival_backoff),
                            boss_hazard_backoff=bool(boss_hazard_backoff),
                            party_focus_target_backoff=bool(party_focus_target_backoff),
                            party_focus_pressure_backoff=bool(party_focus_pressure_backoff),
                            party_survival_backoff=bool(party_survival_backoff),
                        )
                        if boss_hazard_backoff and should_use_shared_target_backoff_point(party_snapshot, current_target):
                            moved = move_away_from_point(
                                client,
                                int(party_snapshot["leader_target_x"]),
                                int(party_snapshot["leader_target_y"]),
                                step=smooth_movement_step(args),
                                min_distance=boss_hazard_backoff_distance(args, action_rotation),
                                args=args,
                                target_in_view=False,
                            )
                            actions += add_action(
                                action_counts,
                                "boss_hazard_last_known_backoff" if moved else "boss_hazard_last_known_hold",
                            )
                        elif party_focus_target_backoff and should_use_shared_target_backoff_point(party_snapshot, current_target):
                            moved = move_away_from_point(
                                client,
                                int(party_snapshot["leader_target_x"]),
                                int(party_snapshot["leader_target_y"]),
                                step=smooth_movement_step(args),
                                min_distance=party_focus_target_backoff_distance(args, action_rotation),
                                args=args,
                                target_in_view=False,
                            )
                            actions += add_action(
                                action_counts,
                                "party_focus_target_last_known_backoff" if moved else "party_focus_target_last_known_hold",
                            )
                        elif party_focus_pressure_backoff and should_use_shared_target_backoff_point(party_snapshot, current_target):
                            moved = move_away_from_point(
                                client,
                                int(party_snapshot["leader_target_x"]),
                                int(party_snapshot["leader_target_y"]),
                                step=smooth_movement_step(args),
                                min_distance=party_focus_target_backoff_distance(args, action_rotation),
                                args=args,
                                target_in_view=False,
                            )
                            actions += add_action(
                                action_counts,
                                "party_focus_pressure_last_known_backoff" if moved else "party_focus_pressure_last_known_hold",
                            )
                        elif party_survival_backoff and should_use_shared_target_backoff_point(party_snapshot, current_target):
                            moved = move_away_from_point(
                                client,
                                int(party_snapshot["leader_target_x"]),
                                int(party_snapshot["leader_target_y"]),
                                step=smooth_movement_step(args),
                                min_distance=party_encounter_survival_distance(args),
                                args=args,
                                target_in_view=False,
                            )
                            actions += add_action(
                                action_counts,
                                "party_survival_last_known_backoff" if moved else "party_survival_last_known_hold",
                            )
                        else:
                            actions += add_action(action_counts, "party_melee_survival_last_known_hold")
                    if should_chase_last_known_shared_target(
                        party_snapshot,
                        current_target=current_target,
                        tactical_backoff=bool(tactical_backoff),
                    ):
                        target_destination = destination_from_point(
                            "party-target-last-known",
                            int(party_snapshot["leader_target_x"]),
                            int(party_snapshot["leader_target_y"]),
                            int(party_snapshot["leader_target_z"]),
                        )
                        client.target_object(current_target)
                        face_point_for_attack(client, target_destination.x, target_destination.y)
                        send_face_command_if_due(now, "smooth_last_known", target_destination)
                        send_stick_command_if_due(now, "smooth_last_known")
                        outcome = move_towards_destination(
                            client,
                            target_destination,
                            step=smooth_movement_step(args),
                            stop_distance=party_last_known_stop_distance(
                                args,
                                action_rotation,
                                party_snapshot,
                                party_member_name,
                            ),
                            args=args,
                            path_state=path_state,
                            action_counts=action_counts,
                            target_in_view=True,
                        )
                        actions += outcome.actions
                        record_movement_failure(movement_failures, client, target_destination, outcome, "smooth_target_last_known")
                        actions += add_action(action_counts, "smooth_target_last_known" if outcome.moved else "smooth_target_last_known_hold")
                        log_attack_decision(
                            now,
                            True,
                            "smooth_last_known_target",
                            party_snapshot=party_snapshot,
                            last_known_x=target_destination.x,
                            last_known_y=target_destination.y,
                            last_known_z=target_destination.z,
                            moved=bool(outcome.moved),
                            movement_reason=outcome.reason,
                        )

                next_smooth_move = now + args.smooth_move_interval + rng.uniform(0.0, min(args.jitter, args.smooth_move_interval))

            send_ping_if_due(now)

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
                    client.send_command(format_say_command(rng.choice(args.social_lines)))
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

            if (
                is_party_leader
                and args.party_invite_interval > 0
                and now >= next_invite
                and not party_ready_for_pull(args, party_state)
            ):
                for member_name in party_state.member_names[1:]:
                    client.send_command(f"/invite {member_name}")
                    actions += add_action(action_counts, "party_invite")

                next_invite = now + args.party_invite_interval + rng.uniform(0, args.jitter)

            if (
                is_party_follower
                and args.party_accept_interval > 0
                and now >= next_accept
                and not party_ready_for_pull(args, party_state)
            ):
                party_snapshot = party_state.snapshot()
                leader_session_id = int(party_snapshot["leader_session_id"])

                if leader_session_id:
                    client.accept_group_invite(leader_session_id)
                    if party_member_ready_for_pull(client, args):
                        party_state.mark_ready(character_name_from_account(account.username))
                        actions += add_action(action_counts, "party_ready")
                    else:
                        actions += add_action(action_counts, "party_accept_wait_home")
                    actions += add_action(action_counts, "party_accept")

                next_accept = now + args.party_accept_interval + rng.uniform(0, args.jitter)

            if (
                should_start_party_form_up_delay(
                    args,
                    party_state,
                    is_party_leader=is_party_leader,
                    current_target=current_target,
                )
                and party_pull_ready_since <= 0.0
            ):
                party_pull_ready_since = now

            required_home_should_move = should_move_to_required_target_home(
                client,
                args,
                is_party_leader=is_party_leader,
                current_target=current_target,
            )
            required_home_low_health_return = (
                current_health_percent > 0
                and current_health_percent <= args.low_health_rest_percent
                and should_approach_required_target_home(
                    args,
                    is_party_leader=is_party_leader,
                    current_target=current_target,
                )
                and should_return_home_before_low_health_rest(client, args)
                and not should_recover_before_required_target_home(
                    args,
                    health_percent=current_health_percent,
                )
            )
            required_home_defer_friendly_cast = should_defer_required_home_move_for_friendly_cast(
                is_party_follower=is_party_follower,
                action_rotation=action_rotation,
                precast_movement_hold=precast_movement_hold,
                friendly_target_pending=hurt_member_for_precast is not None,
            )
            if (
                (required_home_should_move or required_home_low_health_return)
                and (args.move or args.hunter)
                and not required_home_defer_friendly_cast
                and now >= next_follow
            ):
                destination = required_target_home_destination(args)

                if destination is not None:
                    destination_action = "required_target_home_move"
                    destination_hold_action = "required_target_home_hold"
                    if should_clear_travel_aggro_avoid_memory(
                        args,
                        client,
                        now=now,
                        danger_until=travel_aggro_danger_until,
                        danger_x=travel_aggro_danger_x,
                        danger_y=travel_aggro_danger_y,
                        last_damage_taken_at=last_damage_taken_at,
                    ):
                        actions += add_action(action_counts, "travel_aggro_avoid_memory_clear")
                        log_encounter_event(
                            "travel_aggro_avoid_memory_clear",
                            now,
                            danger_x=travel_aggro_danger_x,
                            danger_y=travel_aggro_danger_y,
                            danger_z=travel_aggro_danger_z,
                            repeat_count=travel_aggro_repeat_count,
                        )
                        travel_aggro_danger_until = 0.0
                        travel_aggro_repeat_count = 0
                        travel_aggro_danger_x = 0
                        travel_aggro_danger_y = 0
                        travel_aggro_danger_z = 0
                    if travel_aggro_danger_until > now:
                        detour_destination = travel_aggro_detour_destination(
                            args,
                            client,
                            destination,
                            danger_x=travel_aggro_danger_x,
                            danger_y=travel_aggro_danger_y,
                            danger_z=travel_aggro_danger_z,
                            attempt_count=travel_aggro_repeat_count,
                        )
                        if detour_destination is not None:
                            destination = detour_destination
                            destination_action = "travel_aggro_detour_move"
                            destination_hold_action = "travel_aggro_detour_hold"
                            actions += add_action(action_counts, "travel_aggro_detour")
                            log_encounter_event(
                                "travel_aggro_detour",
                                now,
                                danger_x=travel_aggro_danger_x,
                                danger_y=travel_aggro_danger_y,
                                danger_z=travel_aggro_danger_z,
                                repeat_count=travel_aggro_repeat_count,
                                destination_x=destination.x,
                                destination_y=destination.y,
                                destination_z=destination.z,
                            )
                    transition_to(
                        DummyBehaviorState.ReturnToObjective
                        if behavior_state in {
                            DummyBehaviorState.DropAggroAndRecover,
                            DummyBehaviorState.RestRecover,
                            DummyBehaviorState.ReturnToObjective,
                        }
                        else DummyBehaviorState.TravelToObjective,
                        "required_target_home_move",
                        now,
                    )
                    speak_state_change(now, "return_home", "state: returning to camp")
                    movement_step = smooth_movement_step(args) if args.smooth_movement else args.party_follow_step
                    if destination_kind(destination) == "travel-aggro-detour":
                        moved = client.move_towards_position(
                            destination.x,
                            destination.y,
                            destination.z,
                            step=movement_step,
                            stop_distance=required_target_home_move_stop_distance(
                                args,
                                party_state,
                                is_party_leader=is_party_leader,
                                current_target=current_target,
                            ),
                            movement_speed=getattr(args, "movement_speed", None),
                            min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                        )
                        outcome = MovementOutcome(
                            moved=moved,
                            arrived=not moved,
                            actions=add_action(
                                action_counts,
                                "travel_aggro_detour_direct_move" if moved else "travel_aggro_detour_direct_hold",
                            ),
                        )
                    else:
                        outcome = move_towards_destination(
                            client,
                            destination,
                            step=movement_step,
                            stop_distance=required_target_home_move_stop_distance(
                                args,
                                party_state,
                                is_party_leader=is_party_leader,
                                current_target=current_target,
                            ),
                            args=args,
                            path_state=path_state,
                            action_counts=action_counts,
                        )
                    actions += outcome.actions
                    record_movement_failure(movement_failures, client, destination, outcome, "required_target_home")
                    actions += add_action(action_counts, destination_action if outcome.moved else destination_hold_action)
                    if is_party_follower and party_member_ready_for_pull(client, args):
                        party_state.mark_ready(character_name_from_account(account.username))
                        actions += add_action(action_counts, "party_ready_home")
                    next_follow = now + args.party_follow_interval + rng.uniform(0, args.jitter)
                    send_ping_if_due(now)
                    send_position_heartbeat(now)
                    client.drain(args.tick)
                    continue

            if is_party_follower and args.party_assist_interval > 0 and now >= next_assist:
                party_snapshot = party_state.snapshot()
                leader_target_id = int(party_snapshot["leader_target_id"])
                leader_target_age = now - float(party_snapshot["leader_target_updated_at"])
                leader_engaged = float(party_snapshot["leader_target_engaged_at"]) > 0.0

                if not should_allow_party_assist_for_behavior_state(behavior_state):
                    client.set_attack_mode(False)
                    if current_target:
                        client.clear_target()
                        current_target = 0
                    actions += add_action(action_counts, "drop_aggro_party_assist_suppressed")
                elif should_send_party_assist_command(
                    args,
                    behavior_state,
                    leader_target_id=leader_target_id,
                    leader_engaged=leader_engaged,
                ):
                    client.send_command(f"/assist {party_state.leader_name}")
                    actions += add_action(action_counts, "party_assist_command")

                if not should_allow_party_assist_for_behavior_state(behavior_state):
                    pass
                elif should_hold_party_assist_for_rescue_target(
                    args,
                    party_snapshot,
                    now=now,
                    current_target=current_target,
                    party_member_name=party_member_name,
                    action_rotation=action_rotation,
                    health_percent=current_health_percent,
                ):
                    client.target_object(current_target)
                    client.set_attack_mode(True)
                    actions += add_action(action_counts, "party_assist_rescue_hold")
                elif should_hold_party_assist_for_local_rescue(
                    args,
                    now=now,
                    local_rescue_until=local_rescue_until,
                    current_target=current_target,
                    leader_target_id=leader_target_id,
                ):
                    client.target_object(current_target)
                    client.set_attack_mode(True)
                    actions += add_action(action_counts, "party_assist_local_rescue_hold")
                elif (
                    leader_target_id
                    and leader_target_age >= party_role_assist_attack_delay(args, action_rotation)
                    and (not args.party_require_leader_engaged or leader_engaged)
                ):
                    client.target_object(leader_target_id)
                    current_target = leader_target_id
                    current_target_since = now
                    actions += add_action(action_counts, "party_assist")
                elif leader_target_id and (party_role_assist_attack_delay(args, action_rotation) > 0 or args.party_require_leader_engaged):
                    client.set_attack_mode(False)
                    actions += add_action(action_counts, "party_assist_leader_wait" if args.party_require_leader_engaged and not leader_engaged else "party_assist_delay")
                elif args.party_assist_only and current_target:
                    if should_preserve_unshared_party_target(args, current_target, active_combat):
                        client.target_object(current_target)
                        client.set_attack_mode(True)
                        actions += add_action(action_counts, "party_assist_preserve_unshared")
                    else:
                        client.clear_target()
                        client.set_attack_mode(False)
                        current_target = 0
                        actions += add_action(action_counts, "party_assist_clear")

                next_assist = now + args.party_assist_interval + rng.uniform(0, args.jitter)

            if is_party_follower and args.party_follow_interval > 0 and now >= next_follow:
                party_snapshot = party_state.snapshot()

                if (
                    time.monotonic() - float(party_snapshot["updated_at"]) <= args.party_state_max_age
                    and not party_anchor_position_valid(party_snapshot)
                ):
                    actions += add_action(action_counts, "party_follow_wait_anchor")
                elif time.monotonic() - float(party_snapshot["updated_at"]) <= args.party_state_max_age:
                    party_anchor = party_anchor_from_snapshot(party_snapshot)
                    anchor_x = int(party_anchor["x"])
                    anchor_y = int(party_anchor["y"])
                    anchor_z = int(party_anchor["z"])
                    anchor_destination = destination_from_point("party-anchor", anchor_x, anchor_y, anchor_z)
                    anchor_dx = int(client.x) - anchor_x
                    anchor_dy = int(client.y) - anchor_y
                    anchor_distance = math.sqrt(anchor_dx * anchor_dx + anchor_dy * anchor_dy)
                    target_npc_for_spacing = next(
                        (
                            npc
                            for npc in client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
                            if npc.object_id == current_target
                        ),
                        None,
                    )
                    required_home_destination = required_target_home_destination(args)
                    required_home_distance = (
                        horizontal_distance_between_points(
                            int(client.x),
                            int(client.y),
                            required_home_destination.x,
                            required_home_destination.y,
                        )
                        if required_home_destination is not None
                        else float("inf")
                    )

                    if precast_movement_hold:
                        client.set_attack_mode(False)
                        actions += add_action(action_counts, "party_precast_follow_hold")
                    elif (
                        current_target
                        and target_npc_for_spacing is not None
                        and should_back_off_from_boss_target(
                            args,
                            action_rotation,
                            combat_distance_to(client, target_npc_for_spacing),
                        )
                    ):
                        moved = move_away_from_actor(
                            client,
                            target_npc_for_spacing,
                            step=args.party_follow_step,
                            min_distance=boss_ranged_safe_distance(args, action_rotation),
                            args=args,
                            target_in_view=True,
                        )
                        actions += add_action(action_counts, "boss_ranged_backoff" if moved else "boss_ranged_hold")
                    elif current_target and should_follow_leader_during_required_boss(args, action_rotation, anchor_distance):
                        outcome = move_towards_destination(
                            client,
                            anchor_destination,
                            step=args.party_follow_step,
                            stop_distance=args.boss_non_tank_follow_distance,
                            args=args,
                            path_state=path_state,
                            action_counts=action_counts,
                            target_in_view=True,
                        )
                        actions += outcome.actions
                        record_movement_failure(movement_failures, client, anchor_destination, outcome, "boss_non_tank_regroup")
                        actions += add_action(action_counts, "boss_non_tank_regroup" if outcome.moved else "boss_non_tank_hold")
                    elif current_target and should_back_off_for_ranged_combat_follow(args, action_rotation, anchor_distance):
                        if anchor_dx == 0 and anchor_dy == 0:
                            radians = (int(client.heading) & 0x0FFF) / 4096.0 * math.pi * 2
                            anchor_dx = int(math.cos(radians) * 100)
                            anchor_dy = int(math.sin(radians) * 100)

                        length = max(1.0, math.sqrt(anchor_dx * anchor_dx + anchor_dy * anchor_dy))
                        backoff_x = int(client.x + anchor_dx / length * args.party_follow_step)
                        backoff_y = int(client.y + anchor_dy / length * args.party_follow_step)
                        moved = client.move_towards_position(
                            backoff_x,
                            backoff_y,
                            int(client.z),
                            step=args.party_follow_step,
                            stop_distance=0.0,
                            movement_speed=getattr(args, "movement_speed", None),
                            min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                            target_in_view=True,
                        )
                        actions += add_action(action_counts, "party_ranged_backoff" if moved else "party_ranged_hold")
                    elif current_target:
                        actions += add_action(action_counts, "party_follow_suppressed_combat")
                    elif (
                        required_home_destination is not None
                        and should_back_off_from_required_home_before_engage(
                            args,
                            action_rotation,
                            required_home_distance,
                            current_target=current_target,
                        )
                    ):
                        moved = move_away_from_point(
                            client,
                            required_home_destination.x,
                            required_home_destination.y,
                            step=args.party_follow_step,
                            min_distance=float(getattr(args, "party_preengage_ranged_safe_distance", 0.0) or 0.0),
                            args=args,
                            target_in_view=False,
                        )
                        actions += add_action(action_counts, "party_preengage_ranged_backoff" if moved else "party_preengage_ranged_hold")
                    else:
                        outcome = move_towards_destination(
                            client,
                            anchor_destination,
                            step=args.party_follow_step,
                            stop_distance=args.party_follow_distance,
                            args=args,
                            path_state=path_state,
                            action_counts=action_counts,
                        )
                        actions += outcome.actions
                        record_movement_failure(movement_failures, client, anchor_destination, outcome, "party_follow")
                        actions += add_action(action_counts, "party_follow" if outcome.moved else "party_hold")

                    if should_mark_party_ready_after_follow(
                        client,
                        args,
                        is_party_follower=is_party_follower,
                        current_target=current_target,
                    ):
                        party_state.mark_ready(character_name_from_account(account.username))
                        actions += add_action(action_counts, "party_ready_home")

                next_follow = now + args.party_follow_interval + rng.uniform(0, args.jitter)

            if (
                is_party_follower
                and action_rotation == "healer-support"
                and args.party_buff_interval > 0
                and args.party_buff_spell_levels
                and now >= next_party_buff
            ):
                friendly_spell_cast = False
                buff_targets = party_state.buff_targets(exclude_name=party_member_name)

                if buff_targets:
                    if combat_plan.buff_spells:
                        target = buff_targets[party_buff_index % len(buff_targets)]
                        party_buff_index += 1
                        spell = rng.choice(combat_plan.buff_spells[: min(len(combat_plan.buff_spells), args.combat_plan_spell_pool)])
                        client.target_object(int(target["object_id"]))
                        cast_party_friendly_usable_spell(
                            client,
                            spell,
                            args,
                            target_in_view=True,
                        )
                        actions += add_action(action_counts, "validated_party_buff_member")
                        friendly_spell_cast = True
                    elif getattr(args, "allow_unvalidated_spells", False):
                        target = buff_targets[party_buff_index % len(buff_targets)]
                        party_buff_index += 1
                        client.target_object(int(target["object_id"]))
                        cast_party_friendly_raw_spell(
                            client,
                            rng.choice(args.party_buff_spell_levels),
                            args,
                            spell_line_index=args.party_buff_spell_line_index,
                            target_in_view=True,
                        )
                        actions += add_action(action_counts, "party_buff_member")
                        friendly_spell_cast = True
                    else:
                        actions += add_action(action_counts, "party_buff_skipped_unvalidated")

                    if friendly_spell_cast:
                        friendly_cast_hold_until, friendly_cast_restore_target = plan_friendly_cast_target_hold(args, now, current_target)
                        if friendly_cast_hold_until > now:
                            actions += add_action(action_counts, "party_buff_target_hold")
                        elif current_target:
                            client.target_object(current_target)
                            actions += add_action(action_counts, "retarget_enemy_after_buff")
                    elif current_target:
                        client.target_object(current_target)
                        actions += add_action(action_counts, "retarget_enemy_after_buff")

                next_party_buff = now + args.party_buff_interval + rng.uniform(0, args.jitter)

            if (
                is_party_follower
                and action_rotation == "healer-support"
                and args.party_heal_leader_interval > 0
                and now >= next_party_heal
            ):
                friendly_spell_cast = False
                hurt_member = choose_party_heal_target(
                    party_state,
                    args,
                    exclude_name=party_member_name,
                )

                if hurt_member is not None and party_heal_target_in_cast_range(client, args, hurt_member):
                    if combat_plan.heal_spells:
                        client.target_object(int(hurt_member["object_id"]))
                        spell = rng.choice(combat_plan.heal_spells[: min(len(combat_plan.heal_spells), args.combat_plan_spell_pool)])
                        cast_party_friendly_usable_spell(
                            client,
                            spell,
                            args,
                            target_in_view=True,
                        )
                        action_name = "validated_party_heal_leader" if hurt_member["name"] == party_state.leader_name else "validated_party_heal_member"
                        actions += add_action(action_counts, action_name)
                        friendly_spell_cast = True
                    elif getattr(args, "allow_unvalidated_spells", False):
                        client.target_object(int(hurt_member["object_id"]))
                        cast_party_friendly_raw_spell(
                            client,
                            rng.choice(args.heal_spell_levels),
                            args,
                            spell_line_index=args.heal_spell_line_index,
                            target_in_view=True,
                        )
                        action_name = "party_heal_leader" if hurt_member["name"] == party_state.leader_name else "party_heal_member"
                        actions += add_action(action_counts, action_name)
                        friendly_spell_cast = True
                    else:
                        actions += add_action(action_counts, "party_heal_skipped_unvalidated")

                    if friendly_spell_cast:
                        friendly_cast_hold_until, friendly_cast_restore_target = plan_friendly_cast_target_hold(args, now, current_target)
                        if friendly_cast_hold_until > now:
                            actions += add_action(action_counts, "party_heal_target_hold")
                        elif current_target:
                            client.target_object(current_target)
                            actions += add_action(action_counts, "retarget_enemy_after_heal")
                    elif current_target:
                        client.target_object(current_target)
                        actions += add_action(action_counts, "retarget_enemy_after_heal")
                elif hurt_member is not None:
                    if should_approach_party_heal_target(
                        args,
                        action_rotation=action_rotation,
                        hurt_member=hurt_member,
                        current_target=current_target,
                        behavior_state=behavior_state,
                    ):
                        heal_destination = party_heal_target_destination(hurt_member)
                        outcome = move_towards_party_heal_target(client, args, path_state, action_counts, hurt_member)
                        if outcome is not None and heal_destination is not None:
                            actions += outcome.actions
                            record_movement_failure(movement_failures, client, heal_destination, outcome, "party_heal_target")
                            actions += add_action(
                                action_counts,
                                "party_heal_target_approach" if outcome.moved else "party_heal_target_approach_hold",
                            )
                        else:
                            actions += add_action(action_counts, "party_heal_target_too_far")
                    else:
                        actions += add_action(action_counts, "party_heal_target_too_far")

                next_party_heal = now + args.party_heal_leader_interval + rng.uniform(0, args.jitter)

            if (args.combat or args.hunter) and args.combat_interval > 0 and now >= next_combat:
                if is_party_leader and not current_target and not party_ready_for_pull(args, party_state):
                    if (
                        (args.move or args.hunter)
                        and should_move_to_required_target_home(
                            client,
                            args,
                            is_party_leader=is_party_leader,
                            current_target=current_target,
                        )
                    ):
                        destination = required_target_home_destination(args)
                        if destination is not None:
                            outcome = move_towards_destination(
                                client,
                                destination,
                                step=smooth_movement_step(args) if args.smooth_movement else args.party_follow_step,
                                stop_distance=required_target_home_move_stop_distance(
                                    args,
                                    party_state,
                                    is_party_leader=is_party_leader,
                                    current_target=current_target,
                                ),
                                args=args,
                                path_state=path_state,
                                action_counts=action_counts,
                            )
                            actions += outcome.actions
                            record_movement_failure(movement_failures, client, destination, outcome, "party_forming_required_home")
                            actions += add_action(
                                action_counts,
                                "party_forming_required_home_move" if outcome.moved else "party_forming_required_home_hold",
                            )
                            next_follow = now + args.party_follow_interval + rng.uniform(0, args.jitter)

                    party_pull_ready_since = 0.0
                    client.set_attack_mode(False)
                    actions += add_action(action_counts, "party_forming")
                    next_combat = now + args.combat_interval + rng.uniform(0, args.jitter)
                    next_think = now + rng.uniform(args.think_min, args.think_max)
                    client.drain(args.tick)
                    continue

                if (
                    is_party_leader
                    and not current_target
                    and should_start_party_form_up_delay(
                        args,
                        party_state,
                        is_party_leader=is_party_leader,
                        current_target=current_target,
                    )
                ):
                    if party_pull_ready_since <= 0.0:
                        party_pull_ready_since = now

                    if now - party_pull_ready_since < args.party_form_up_delay:
                        client.set_attack_mode(False)
                        actions += add_action(action_counts, "party_form_up_wait")
                        next_combat = now + args.combat_interval + rng.uniform(0, args.jitter)
                        next_think = now + rng.uniform(args.think_min, args.think_max)
                        client.drain(args.tick)
                        continue
                elif current_target:
                    party_pull_ready_since = 0.0

                    if current_target and now - current_target_since > args.target_timeout:
                        timeout_combat_actor = actor_from_active_combat(active_combat)
                        if (
                            should_preserve_current_party_target(args, party_state, current_target, active_combat)
                            and target_removed_preserve_allowed(
                                args,
                                now,
                                current_target_last_visible_at,
                                current_target_removed_preserve_count,
                            )
                        ):
                            current_target_since = now
                            client.target_object(current_target)
                            client.set_attack_mode(True)
                            timeout_destination = None
                            if party_state is not None:
                                party_snapshot = party_state.snapshot()
                                if int(party_snapshot["leader_target_id"]) == current_target:
                                    timeout_destination = destination_from_point(
                                        "party-target-last-known",
                                        int(party_snapshot["leader_target_x"]),
                                        int(party_snapshot["leader_target_y"]),
                                        int(party_snapshot["leader_target_z"]),
                                    )
                            send_face_command_if_due(now, "target_timeout_preserved", timeout_destination)
                            send_stick_command_if_due(now, "target_timeout_preserved")
                            actions += add_action(action_counts, "target_timeout_preserved")
                            log_encounter_event(
                                "target_timeout_preserved",
                                now,
                                preserve_count=int(current_target_removed_preserve_count),
                            )
                            if timeout_destination is not None:
                                face_point_for_attack(client, timeout_destination.x, timeout_destination.y)
                        elif should_preserve_target_timeout_for_combat_progress(
                            args,
                            active_combat,
                            timeout_combat_actor,
                            recent_incoming_attacker_name=last_incoming_damage_attacker_name,
                            last_incoming_damage_at=last_incoming_damage_at,
                            now=now,
                        ):
                            current_target_since = now
                            current_target_last_visible_at = now
                            client.target_object(current_target)
                            client.set_attack_mode(True)
                            timeout_destination = None
                            if timeout_combat_actor is not None:
                                timeout_destination = destination_from_point(
                                    "combat-target-last-known",
                                    int(getattr(timeout_combat_actor, "x", 0) or 0),
                                    int(getattr(timeout_combat_actor, "y", 0) or 0),
                                    int(getattr(timeout_combat_actor, "z", 0) or 0),
                                )
                            send_face_command_if_due(now, "target_timeout_combat_progress", timeout_destination)
                            send_stick_command_if_due(now, "target_timeout_combat_progress")
                            if current_target_intent in {TargetIntent.objective, TargetIntent.required_retaliation}:
                                transition_to(DummyBehaviorState.HuntObjective, "target_timeout_combat_progress", now)
                            actions += add_action(action_counts, "target_timeout_preserved_combat_progress")
                            log_encounter_event(
                                "target_timeout_preserved_combat_progress",
                                now,
                                target_id=int(current_target),
                                target_name=str(getattr(timeout_combat_actor, "name", "") or ""),
                                last_incoming_damage_age=round(now - last_incoming_damage_at, 3)
                                if last_incoming_damage_at > 0.0
                                else 0.0,
                                last_damage_done_age=round(
                                    now - float(active_combat.get("last_damage_done_at", 0.0) or 0.0),
                                    3,
                                )
                                if active_combat is not None and float(active_combat.get("last_damage_done_at", 0.0) or 0.0) > 0.0
                                else 0.0,
                            )
                            if timeout_destination is not None:
                                face_point_for_attack(client, timeout_destination.x, timeout_destination.y)
                        else:
                            rejected_targets[current_target] = now + args.target_failure_cooldown
                            if not should_preserve_party_target_on_loss(args):
                                reject_active_target_kind(now, args.target_failure_name_cooldown)
                            finish_combat("target_timeout", now)
                            log_encounter_event("target_timeout_rejected", now)
                            client.clear_target()
                            current_target = 0
                            if (
                                is_party_leader
                                and party_state is not None
                                and not should_preserve_party_target_on_loss(args)
                            ):
                                party_state.clear_leader_target()
                            actions += add_action(action_counts, "reject_target")

                npcs = client.visible_npcs(max_age=args.npc_max_age, include_peace=should_scan_peace_npcs(args))
                if current_target:
                    current_visible_npc = choose_current_visible_target(npcs, current_target)
                    if current_visible_npc is not None:
                        observed_intent = (
                            current_target_intent
                            if current_target_intent != TargetIntent.none and not is_required_target(args, current_visible_npc)
                            else target_intent_for_selected_npc(
                                args,
                                current_visible_npc,
                                selected_npc_is_rescue=False,
                                behavior_state=behavior_state,
                                recent_incoming_attacker_name=last_incoming_damage_attacker_name,
                            )
                        )
                        if should_handle_travel_aggro_target(
                            args,
                            behavior_state,
                            current_visible_npc,
                            observed_intent,
                        ):
                            start_travel_aggro_drop(now, "travel_non_objective_aggro", npc=current_visible_npc)
                            send_ping_if_due(now)
                            send_position_heartbeat(now)
                            client.drain(args.tick)
                            continue
                        if current_target_intent == TargetIntent.none or is_required_target(args, current_visible_npc):
                            current_target_intent = observed_intent
                    elif active_combat is not None:
                        active_target_actor = actor_from_active_combat(active_combat)
                        observed_intent = target_intent_for_selected_npc(
                            args,
                            active_target_actor,
                            selected_npc_is_rescue=False,
                            behavior_state=behavior_state,
                            recent_incoming_attacker_name=last_incoming_damage_attacker_name,
                        )
                        if should_handle_travel_aggro_target(
                            args,
                            behavior_state,
                            active_target_actor,
                            observed_intent,
                        ):
                            start_travel_aggro_drop(now, "travel_non_objective_aggro_last_known", npc=active_target_actor)
                            send_ping_if_due(now)
                            send_position_heartbeat(now)
                            client.drain(args.tick)
                            continue

                kept_current_target_without_visible_npc = False

                selected_npc = None
                selected_npc_is_rescue = False
                selected_target_source: TargetSource | str = TargetSource.hunter_selection
                selected_target_decision = None

                if args.hunter:
                    if party_state is not None:
                        party_snapshot = party_state.snapshot()
                        leader_target_id = int(party_snapshot["leader_target_id"])
                        rescue_target_id = int(party_snapshot["rescue_target_id"])
                        rescue_age = party_rescue_target_age(party_snapshot, rescue_target_id, now)
                        rescue_objective_ready = should_allow_party_rescue_before_objective_engaged(
                            args,
                            party_snapshot,
                            active_combat,
                            now,
                        )

                        if rescue_target_id and rescue_age > args.party_rescue_max_age:
                            party_state.clear_rescue_target()
                            party_snapshot = party_state.snapshot()
                            leader_target_id = int(party_snapshot["leader_target_id"])
                            rescue_target_id = int(party_snapshot["rescue_target_id"])
                            rescue_age = party_rescue_target_age(party_snapshot, rescue_target_id, now)

                        if (
                            selected_npc is None
                            and is_party_leader
                            and getattr(args, "party_clear_objective_adds_before_engage", False)
                            and float(party_snapshot.get("leader_target_engaged_at", 0.0) or 0.0) <= 0.0
                        ):
                            objective_npc = choose_required_visible_target(client, npcs, args)
                            selected_npc = choose_pre_objective_add_target(
                                npcs,
                                client,
                                args,
                                objective_npc,
                                rejected_targets=rejected_targets,
                                rejected_target_kinds=rejected_target_kinds,
                                now=now,
                            )
                            if selected_npc is not None:
                                selected_npc_is_rescue = True
                                selected_target_source = TargetSource.party_rescue
                                if args.party_rescue_aggro and party_state.request_rescue(
                                    party_member_name,
                                    selected_npc,
                                    leader_target_id=int(getattr(objective_npc, "object_id", 0) or 0),
                                    min_hold=0.0,
                                    objective_add=True,
                                ):
                                    actions += add_action(action_counts, "party_pre_objective_add_shared")
                                actions += add_action(action_counts, "party_pre_objective_add_target")

                        if selected_npc is None and rescue_objective_ready:
                            selected_npc = choose_party_rescue_threat_target(
                                npcs,
                                client,
                                args,
                                party_snapshot,
                                member_name=party_member_name,
                                action_rotation=action_rotation,
                                health_percent=current_health_percent,
                                now=now,
                                current_target=current_target,
                            )

                            if selected_npc is not None:
                                selected_npc_is_rescue = True
                                selected_target_source = TargetSource.party_rescue
                                actions += add_action(action_counts, "party_rescue_threat_target")

                        if (
                            selected_npc is None
                            and rescue_objective_ready
                            and args.party_rescue_aggro
                            and rescue_target_id
                            and rescue_age <= args.party_rescue_max_age
                            and should_party_member_handle_rescue_target(
                                args,
                                party_snapshot,
                                party_member_name,
                                action_rotation,
                                current_health_percent,
                                rescue_age=rescue_age,
                            )
                        ):
                            selected_npc = choose_party_assist_target(npcs, rescue_target_id)

                            if selected_npc is not None:
                                if should_accept_party_rescue_target(args, selected_npc):
                                    selected_npc_is_rescue = True
                                    selected_target_source = TargetSource.party_rescue
                                    actions += add_action(action_counts, "party_rescue_assist_target")
                                else:
                                    selected_npc = None
                                    party_state.clear_rescue_target()
                                    actions += add_action(action_counts, "party_rescue_target_rejected")

                        if (
                            selected_npc is None
                            and rescue_objective_ready
                            and local_rescue_window_active(now, local_rescue_until)
                            and should_party_member_use_local_rescue_target(args, action_rotation, current_health_percent)
                        ):
                            selected_npc = choose_local_rescue_target(
                                npcs,
                                client,
                                args,
                                leader_target_id,
                                current_target=current_target,
                            )

                            if selected_npc is not None:
                                selected_npc_is_rescue = True
                                selected_target_source = TargetSource.local_rescue
                                actions += add_action(action_counts, "party_local_rescue_target")

                                if args.party_rescue_aggro and party_state.request_rescue(
                                    party_member_name,
                                    selected_npc,
                                    leader_target_id=leader_target_id,
                                    min_hold=args.party_rescue_min_hold,
                                    objective_add=is_party_objective_add_rescue_threat(args, party_snapshot, selected_npc),
                                ):
                                    actions += add_action(action_counts, "party_local_rescue_shared")

                    if current_target and selected_npc is None:
                        selected_npc = selected_npc or choose_current_visible_target(npcs, current_target)
                        if selected_npc is not None:
                            selected_target_source = TargetSource.current_target_preserve
                        if (
                            selected_npc is not None
                            and party_state is not None
                            and current_target_is_party_rescue_target(party_snapshot, current_target)
                            and should_accept_party_rescue_target(args, selected_npc)
                            and should_party_member_handle_rescue_target(
                                args,
                                party_snapshot,
                                party_member_name,
                                action_rotation,
                                current_health_percent,
                                rescue_age=party_rescue_target_age(party_snapshot, current_target, now),
                            )
                        ):
                            selected_npc_is_rescue = True
                            selected_target_source = TargetSource.party_rescue
                            actions += add_action(action_counts, "party_rescue_continue_target")

                        if should_reject_selected_target_for_required_filter(args, selected_npc, selected_npc_is_rescue):
                            selected_npc = None
                            rejected_target_id = current_target
                            current_target = 0
                            if is_party_leader and party_state is not None:
                                party_snapshot = party_state.snapshot()
                                if should_clear_leader_target_after_required_filter(args, party_snapshot, rejected_target_id):
                                    party_state.clear_leader_target()
                            client.clear_target()
                            client.set_attack_mode(False)
                            actions += add_action(action_counts, "required_target_filter_clear")

                    if is_party_follower and selected_npc is None:
                        party_snapshot = party_state.snapshot()
                        leader_target_id = int(party_snapshot["leader_target_id"])
                        leader_target_age = now - float(party_snapshot["leader_target_updated_at"])
                        leader_engaged = float(party_snapshot["leader_target_engaged_at"]) > 0.0
                        if leader_target_age >= party_role_assist_attack_delay(args, action_rotation) and (
                            not args.party_require_leader_engaged or leader_engaged
                        ):
                            selected_npc = choose_party_assist_target(npcs, leader_target_id)

                            if selected_npc is not None and not passes_required_target_filter(args, selected_npc):
                                selected_npc = None
                                current_target = 0
                                client.clear_target()
                                client.set_attack_mode(False)
                                actions += add_action(action_counts, "party_assist_required_target_rejected")
                            elif selected_npc is not None:
                                selected_target_source = TargetSource.party_assist

                    if selected_npc is None:
                        party_snapshot = party_state.snapshot() if party_state is not None else {}
                        if should_reacquire_shared_objective_visible_target(
                            args,
                            party_snapshot,
                            is_party_follower=is_party_follower,
                        ):
                            selected_npc = choose_shared_objective_visible_target(
                                client,
                                npcs,
                                args,
                                int(party_snapshot.get("leader_target_id", 0) or 0),
                            )
                            if selected_npc is not None:
                                selected_target_source = TargetSource.leader_target_reacquire
                                party_state.update_shared_target(selected_npc)
                                actions += add_action(action_counts, "party_assist_required_reacquire")

                    if (
                        selected_npc is None
                        and not (is_party_follower and args.party_assist_only)
                        and not (is_party_leader and args.party_assist_only and current_target)
                    ):
                        if party_state is not None:
                            party_snapshot = party_state.snapshot()
                            selected_npc = party_rescue_actor_from_snapshot(
                                args,
                                party_snapshot,
                                member_name=party_member_name,
                                action_rotation=action_rotation,
                                health_percent=current_health_percent,
                                now=now,
                            )
                            if selected_npc is not None:
                                selected_npc_is_rescue = True
                                selected_target_source = TargetSource.party_rescue
                                actions += add_action(action_counts, "party_rescue_snapshot_target")
                        if (
                            current_target <= 0
                            and selected_npc is None
                            and should_approach_required_target_home(args, is_party_leader=is_party_leader, current_target=current_target)
                            and not required_target_home_reached(client, args)
                            and not required_target_home_hunt_ready(client, args)
                        ):
                            actions += add_action(action_counts, "required_target_home_wait")
                        elif (
                            current_target > 0
                            and choose_current_visible_target(npcs, current_target) is None
                            and not fresh_hunter_target_observation(
                                args,
                                server_target_observations.get(current_target),
                                now,
                            )
                        ):
                            actions += add_action(action_counts, "target_loss_grace_wait")
                        elif (
                            current_target > 0
                            and choose_current_visible_target(npcs, current_target) is None
                            and fresh_hunter_target_observation(
                                args,
                                server_target_observations.get(current_target),
                                now,
                            )
                        ):
                            actions += add_action(action_counts, "hunter_target_api_continue")
                        else:
                            if should_hunter_wind_down_before_segment_end(
                                args,
                                time_left_seconds=end_time - now,
                                target_removed_count=int(action_counts.get("target_removed", 0) or 0),
                                current_target=current_target,
                            ):
                                actions += add_action(action_counts, "hunter_wind_down")
                            elif behavior_state == DummyBehaviorState.DropAggroAndRecover:
                                actions += add_action(action_counts, "drop_aggro_target_selection_suppressed")
                            else:
                                selected_npc = choose_hunter_target(
                                    client,
                                    rng,
                                    args,
                                    rejected_targets,
                                    rejected_target_kinds,
                                    now,
                                )
                                if selected_npc is not None:
                                    selected_target_source = TargetSource.hunter_selection
                                if selected_npc is None:
                                    hunter_api_target = fetch_hunter_target_api_observation(
                                        args,
                                        client,
                                        rng,
                                        rejected_targets,
                                        rejected_target_kinds,
                                        now,
                                    )
                                    if hunter_api_target is not None:
                                        selected_npc = actor_from_target_observation(hunter_api_target)
                                        selected_target_source = TargetSource.current_target_api_refresh
                                        server_target_observations[hunter_api_target.object_id] = hunter_api_target
                                        actions += add_action(action_counts, "hunter_target_api_scout")
                                        log_encounter_event(
                                            "hunter_target_api_scout",
                                            now,
                                            target_id=hunter_api_target.object_id,
                                            target_name=hunter_api_target.name,
                                            target_level=hunter_api_target.level,
                                            target_x=hunter_api_target.x,
                                            target_y=hunter_api_target.y,
                                            target_z=hunter_api_target.z,
                                            target_distance=round(combat_distance_to(client, selected_npc), 2),
                                        )
                            if selected_npc is None and encounter_log_path and now >= next_hunter_scan_log:
                                scan_snapshot = hunter_target_scan_snapshot(
                                    client,
                                    args,
                                    rejected_targets,
                                    rejected_target_kinds,
                                    now,
                                )
                                log_encounter_event(
                                    "hunter_target_scan_empty",
                                    now,
                                    **scan_snapshot,
                                )
                                if int(scan_snapshot.get("hunter_visible_npcs", 0) or 0) > 0:
                                    reject_counts = scan_snapshot.get("hunter_reject_counts", {})
                                    top_reason = ""
                                    if isinstance(reject_counts, dict):
                                        reasons = {
                                            str(key): int(value)
                                            for key, value in reject_counts.items()
                                            if key not in {"visible", "eligible"}
                                            and isinstance(value, int)
                                            and value > 0
                                        }
                                        if reasons:
                                            top_reason = max(reasons.items(), key=lambda item: item[1])[0]
                                    speak_state_change(
                                        now,
                                        f"scan_empty:{top_reason}",
                                        f"state: no eligible target reason={top_reason or 'unknown'}",
                                    )
                                next_hunter_scan_log = now + max(3.0, float(args.encounter_log_interval or 0.0))
                    elif selected_npc is None and args.party_assist_only and current_target:
                        party_snapshot = party_state.snapshot()
                        party_boss_melee_backoff = should_back_off_for_party_boss_melee_limit(
                            args,
                            party_snapshot_for_tick,
                            party_member_name,
                            action_rotation,
                            current_target,
                        )
                        tactical_backoff = (
                            party_melee_survival_backoff
                            or boss_hazard_backoff
                            or party_focus_target_backoff
                            or party_focus_pressure_backoff
                            or party_boss_melee_backoff
                            or party_survival_backoff
                        )

                        if should_chase_last_known_shared_target(
                            party_snapshot,
                            current_target=current_target,
                            tactical_backoff=bool(tactical_backoff),
                        ):
                            client.target_object(current_target)
                            client.set_attack_mode(True)
                            target_destination = destination_from_point(
                                "party-target-last-known",
                                int(party_snapshot["leader_target_x"]),
                                int(party_snapshot["leader_target_y"]),
                                int(party_snapshot["leader_target_z"]),
                            )
                            face_point_for_attack(client, target_destination.x, target_destination.y)
                            send_face_command_if_due(now, "party_target_last_known", target_destination)
                            send_stick_command_if_due(now, "party_target_last_known")
                            outcome = move_towards_destination(
                                client,
                                target_destination,
                                step=smooth_movement_step(args) if args.smooth_movement else args.move_step,
                                stop_distance=party_last_known_stop_distance(
                                    args,
                                    action_rotation,
                                    party_snapshot,
                                    party_member_name,
                                ),
                                args=args,
                                path_state=path_state,
                                action_counts=action_counts,
                                target_in_view=True,
                            )
                            actions += outcome.actions
                            record_movement_failure(movement_failures, client, target_destination, outcome, "party_target_last_known")
                            actions += add_action(action_counts, "party_target_last_known" if outcome.moved else "party_target_last_known_hold")
                            client.send_position_update(speed=getattr(client, "last_position_speed", 0.0), target_in_view=True)
                            kept_current_target_without_visible_npc = True
                        else:
                            if (
                                not tactical_backoff
                                and should_preserve_unshared_party_target(args, current_target, active_combat)
                            ):
                                client.target_object(current_target)
                                client.set_attack_mode(True)
                                unshared_destination = None
                                if party_state is not None:
                                    party_snapshot = party_state.snapshot()
                                    if int(party_snapshot["leader_target_id"]) == current_target:
                                        unshared_destination = destination_from_point(
                                            "party-target-unshared",
                                            int(party_snapshot["leader_target_x"]),
                                            int(party_snapshot["leader_target_y"]),
                                            int(party_snapshot["leader_target_z"]),
                                        )
                                send_face_command_if_due(now, "party_target_unshared", unshared_destination)
                                send_stick_command_if_due(now, "party_target_unshared")
                                kept_current_target_without_visible_npc = True
                                actions += add_action(action_counts, "party_target_unshared_preserved")
                            else:
                                client.clear_target()
                                client.set_attack_mode(False)
                                current_target = 0
                                actions += add_action(action_counts, "party_assist_hold")

                    npcs = [selected_npc] if selected_npc is not None else []
                    if args.hunter and not selected_npc_is_rescue:
                        level_filtered_npcs = [
                            npc
                            for npc in npcs
                            if passes_hunter_target_level_filter(args, npc)
                            or preferred_low_con_fallback_allowed(args, client, npc)
                        ]
                        if npcs and not level_filtered_npcs:
                            rejected_target_id = int(getattr(npcs[0], "object_id", 0) or 0)
                            if rejected_target_id:
                                rejected_targets[rejected_target_id] = now + min(args.target_failure_cooldown, 5.0)
                            if current_target == rejected_target_id:
                                current_target = 0
                                client.clear_target()
                                client.set_attack_mode(False)
                            actions += add_action(action_counts, "hunter_level_filter_clear")
                        npcs = level_filtered_npcs
                        if not npcs:
                            selected_npc = None

                    selected_target_decision = None
                    if selected_npc is not None:
                        selection_party_snapshot = party_state.snapshot() if party_state is not None else {}
                        selection_leader_engaged = (
                            float(selection_party_snapshot.get("leader_target_engaged_at", 0.0) or 0.0) > 0.0
                        )
                        selection_required_home_reached = required_target_home_reached(client, args)
                        selection_required_home_hunt_ready = required_target_home_hunt_ready(client, args)
                        selection_party_ready_for_objective = (
                            party_ready_for_pull(args, party_state) if party_state is not None else True
                        )
                        if should_enter_hunt_for_objective_area_rescue(
                            args,
                            behavior_state,
                            selected_npc_is_rescue=selected_npc_is_rescue,
                            required_home_hunt_ready=selection_required_home_hunt_ready,
                            party_ready_for_objective=selection_party_ready_for_objective,
                        ):
                            transition_to(DummyBehaviorState.HuntObjective, "objective_area_rescue_target_selected", now)

                        selected_target_intent = target_intent_for_selected_npc(
                            args,
                            selected_npc,
                            selected_npc_is_rescue=selected_npc_is_rescue,
                            behavior_state=behavior_state,
                            recent_incoming_attacker_name=last_incoming_damage_attacker_name,
                        )
                        if should_delay_target_selection_until_objective_ready(
                            args,
                            behavior_state,
                            selected_target_intent,
                            current_target=current_target,
                            required_home_hunt_ready=selection_required_home_hunt_ready,
                            party_ready_for_objective=selection_party_ready_for_objective,
                            is_party_follower=is_party_follower,
                            leader_engaged=selection_leader_engaged,
                        ):
                            actions += add_action(action_counts, "objective_selection_wait_ready")
                            log_encounter_event(
                                "objective_selection_wait_ready",
                                now,
                                target_id=int(getattr(selected_npc, "object_id", 0) or 0),
                                target_name=str(getattr(selected_npc, "name", "") or ""),
                                target_intent=target_intent_value(selected_target_intent),
                            )
                            dropped_for_recent_damage = should_drop_objective_wait_for_recent_damage(
                                behavior_state,
                                selected_target_intent,
                                last_damage_taken_at=last_damage_taken_at,
                                now=now,
                            )
                            if dropped_for_recent_damage:
                                actions += add_action(action_counts, "objective_wait_damage_drop")
                                start_travel_aggro_drop(now, "objective_wait_damage", npc=selected_npc)
                            selected_npc = None
                            npcs = []
                            if not dropped_for_recent_damage:
                                current_target_intent = TargetIntent.none
                        elif not should_allow_target_selection_for_behavior_state(
                            behavior_state,
                            args,
                            selected_npc,
                            selected_target_intent,
                        ):
                            if is_objective_travel_state(behavior_state):
                                if should_suppress_passive_travel_target(
                                    args,
                                    behavior_state,
                                    selected_npc,
                                    selected_target_intent,
                                    current_target=current_target,
                                    now=now,
                                    last_damage_taken_at=last_damage_taken_at,
                                ):
                                    rejected_target_id = int(getattr(selected_npc, "object_id", 0) or 0)
                                    if rejected_target_id:
                                        rejected_targets[rejected_target_id] = now + min(
                                            float(getattr(args, "target_failure_cooldown", 5.0) or 5.0),
                                            5.0,
                                        )
                                    actions += add_action(action_counts, "travel_passive_target_suppressed")
                                    log_encounter_event(
                                        "travel_passive_target_suppressed",
                                        now,
                                        target_id=rejected_target_id,
                                        target_name=str(getattr(selected_npc, "name", "") or ""),
                                        target_level=int(getattr(selected_npc, "level", 0) or 0),
                                    )
                                    selected_npc = None
                                    npcs = []
                                    current_target_intent = TargetIntent.none
                                else:
                                    start_travel_aggro_drop(now, "travel_non_objective_aggro", npc=selected_npc)
                                    send_ping_if_due(now)
                                    send_position_heartbeat(now)
                                    client.drain(args.tick)
                                    continue
                            else:
                                selected_npc = None
                                npcs = []
                                actions += add_action(action_counts, "drop_aggro_target_selection_suppressed")
                        else:
                            selected_target_candidate = engagement_candidate_from_actor(
                                selected_npc,
                                source=selected_target_source,
                                intent=selected_target_intent,
                            )
                            selected_target_decision = evaluate_engagement_candidate(
                                selected_target_candidate,
                                EngagementContext(
                                    behavior_state=behavior_state,
                                    current_target=current_target,
                                    current_target_intent=current_target_intent,
                                    is_party_leader=is_party_leader,
                                    is_party_follower=is_party_follower,
                                    party_ready=selection_party_ready_for_objective,
                                    leader_engaged=selection_leader_engaged,
                                    current_health_percent=current_health_percent,
                                    objective_home_reached=selection_required_home_reached,
                                    objective_hunt_ready=selection_required_home_hunt_ready,
                                    drop_aggro_active=behavior_state == DummyBehaviorState.DropAggroAndRecover,
                                    rest_active=rest_until > now,
                                    flee_active=flee_until > now,
                                ),
                                client,
                                args,
                                selection_party_snapshot,
                            )
                            if not selected_target_decision.allowed:
                                commit_target(
                                    selected_target_decision,
                                    client,
                                    party_state,
                                    now=now,
                                    current_target=current_target,
                                    current_target_since=current_target_since,
                                    current_target_last_visible_at=current_target_last_visible_at,
                                    current_target_intent=current_target_intent,
                                    action_counts=action_counts,
                                    log_event=log_encounter_event,
                                )
                                rejected_target_id = int(getattr(selected_npc, "object_id", 0) or 0)
                                if rejected_target_id:
                                    rejected_targets[rejected_target_id] = now + min(
                                        float(getattr(args, "target_failure_cooldown", 5.0) or 5.0),
                                        5.0,
                                    )
                                selected_npc = None
                                npcs = []
                            else:
                                current_target_intent = selected_target_decision.intent
                            if (
                                selected_target_decision is not None
                                and selected_target_decision.allowed
                                and selected_target_intent in {TargetIntent.objective, TargetIntent.required_retaliation}
                            ):
                                transition_to(
                                    DummyBehaviorState.HuntObjective,
                                    "objective_target_selected"
                                    if selected_target_intent == TargetIntent.objective
                                    else "required_target_retaliation",
                                    now,
                                )

                if npcs:
                    npc = rng.choice(npcs[: max(args.target_pool, 1)])
                    distance = combat_distance_to(client, npc)
                    target_commit_result = None

                    if current_target != npc.object_id:
                        finish_combat("target_switched", now, distance)
                        examine = args.target_examine_chance > 0 and rng.random() < args.target_examine_chance
                        if selected_target_decision is None:
                            fallback_candidate = engagement_candidate_from_actor(
                                npc,
                                source=selected_target_source,
                                intent=current_target_intent,
                            )
                            selected_target_decision = evaluate_engagement_candidate(
                                fallback_candidate,
                                EngagementContext(
                                    behavior_state=behavior_state,
                                    current_target=current_target,
                                    current_target_intent=current_target_intent,
                                    is_party_leader=is_party_leader,
                                    is_party_follower=is_party_follower,
                                    party_ready=party_ready_for_pull(args, party_state) if party_state is not None else True,
                                    leader_engaged=float(
                                        (party_state.snapshot() if party_state is not None else {}).get(
                                            "leader_target_engaged_at",
                                            0.0,
                                        )
                                        or 0.0
                                    )
                                    > 0.0,
                                    current_health_percent=current_health_percent,
                                    objective_home_reached=required_target_home_reached(client, args),
                                    objective_hunt_ready=required_target_home_hunt_ready(client, args),
                                    drop_aggro_active=behavior_state == DummyBehaviorState.DropAggroAndRecover,
                                    rest_active=rest_until > now,
                                    flee_active=flee_until > now,
                                ),
                                client,
                                args,
                                party_state.snapshot() if party_state is not None else {},
                            )

                        target_commit_result = commit_target(
                            selected_target_decision,
                            client,
                            party_state,
                            now=now,
                            current_target=current_target,
                            current_target_since=current_target_since,
                            current_target_last_visible_at=current_target_last_visible_at,
                            current_target_intent=current_target_intent,
                            action_counts=action_counts,
                            log_event=log_encounter_event,
                            examine=examine,
                        )
                        current_target = target_commit_result.current_target
                        current_target_since = target_commit_result.current_target_since
                        current_target_last_visible_at = target_commit_result.current_target_last_visible_at
                        current_target_intent = target_commit_result.current_target_intent
                        if not target_commit_result.current_target_updated:
                            rejected_target_id = int(getattr(npc, "object_id", 0) or 0)
                            if rejected_target_id:
                                rejected_targets[rejected_target_id] = now + min(
                                    float(getattr(args, "target_failure_cooldown", 5.0) or 5.0),
                                    5.0,
                                )
                            npcs = []
                            selected_npc = None
                            continue
                        current_target_removed_preserve_count = 0
                        attack_target_in_view_primed_at = 0.0
                        attack_target_in_view_primed_target = 0
                        start_combat(npc, distance, now)
                        actions += add_action(action_counts, "examine_target" if examine else "target")

                        if is_party_leader and party_state is not None and not selected_npc_is_rescue:
                            party_state.clear_rescue_target(npc.object_id)

                    if is_party_leader and should_update_party_objective_target(selected_npc_is_rescue):
                        if not (
                            target_commit_result is not None
                            and target_commit_result.party_leader_target_published
                        ):
                            party_state.update_leader(client, npc)
                    elif is_party_leader:
                        party_state.update_leader(client)
                    elif (
                        party_state is not None
                        and should_share_selected_target(
                            args,
                            selected_npc_is_rescue,
                            is_party_leader=is_party_leader,
                            party_snapshot=party_snapshot_for_tick,
                        )
                    ):
                        party_state.update_shared_target(npc)

                    if current_target == npc.object_id:
                        current_target_last_visible_at = now
                        current_target_removed_preserve_count = 0
                        if active_combat is not None:
                            active_combat["target_x"] = int(getattr(npc, "x", 0) or 0)
                            active_combat["target_y"] = int(getattr(npc, "y", 0) or 0)
                            active_combat["target_z"] = int(getattr(npc, "z", 0) or 0)

                    if should_send_target_start_command_for_npc(args, npc, selected_npc_is_rescue) and should_send_target_start_commands(
                        args,
                        current_target,
                        sent_target_start_command_targets,
                    ):
                        for target_start_command in args.target_start_command:
                            client.send_command(target_start_command)
                            actions += add_action(action_counts, "target_start_command")
                        sent_target_start_command_targets.add(current_target)

                    if (args.move or args.hunter) and not args.smooth_movement:
                        target_destination = destination_from_actor("target", npc)
                        attack_enabled = should_enable_attack_mode(args, action_rotation, distance)
                        outcome = move_towards_destination(
                            client,
                            target_destination,
                            step=args.move_step,
                            stop_distance=combat_stop_distance(args, action_rotation),
                            args=args,
                            path_state=path_state,
                            action_counts=action_counts,
                            target_in_view=attack_enabled,
                        )
                        actions += outcome.actions
                        record_movement_failure(movement_failures, client, target_destination, outcome, "target")
                        actions += add_action(action_counts, "move" if outcome.moved else "hold_position")

                        if outcome.moved:
                            distance = combat_distance_to(client, npc)

                    if args.interact:
                        client.interact_object(npc.object_id)
                        actions += add_action(action_counts, "interact")

                    party_boss_melee_backoff = should_back_off_for_party_boss_melee_limit(
                        args,
                        party_snapshot_for_tick,
                        party_member_name,
                        action_rotation,
                        current_target,
                    )
                    tactical_backoff = (
                        party_melee_survival_backoff
                        or boss_hazard_backoff
                        or party_focus_target_backoff
                        or party_focus_pressure_backoff
                        or party_boss_melee_backoff
                        or party_survival_backoff
                    )
                    effective_attack_distance = effective_attack_distance_for_recent_incoming_damage(
                        args,
                        action_rotation,
                        npc,
                        distance=distance,
                        recent_incoming_attacker_name=last_incoming_damage_attacker_name,
                        last_incoming_damage_at=last_incoming_damage_at,
                        now=now,
                    )
                    recent_incoming_melee = effective_attack_distance < distance
                    action_distance = attack_action_distance(action_rotation, distance, effective_attack_distance)
                    attack_enabled = (
                        False
                        if tactical_backoff
                        else should_enable_attack_mode(args, action_rotation, action_distance)
                    )
                    if attack_enabled:
                        face_target_for_attack(client, npc)
                        client.target_object(current_target)
                        actions += add_action(action_counts, "target_refresh_in_view")
                        client.send_position_update(speed=0.0, target_in_view=True)
                        actions += add_action(action_counts, "attack_target_in_view_update")
                        prime_delay = attack_target_in_view_prime_delay(
                            args,
                            recent_incoming_melee=recent_incoming_melee,
                        )
                        newly_primed = attack_target_in_view_primed_target != current_target
                        if newly_primed:
                            attack_target_in_view_primed_target = current_target
                            attack_target_in_view_primed_at = now
                        if should_wait_for_attack_target_prime(
                            primed_target=attack_target_in_view_primed_target,
                            current_target=current_target,
                            primed_at=attack_target_in_view_primed_at,
                            now=now,
                            prime_delay=prime_delay,
                        ):
                            client.set_attack_mode(False)
                            actions += add_action(
                                action_counts,
                                "attack_target_in_view_prime" if newly_primed else "attack_target_in_view_prime_wait",
                            )
                            attack_enabled = False
                        else:
                            client.set_attack_mode(True)
                            actions += add_action(action_counts, "attack_on")
                    else:
                        client.set_attack_mode(False)
                        actions += add_action(action_counts, "attack_off")
                    log_attack_decision(
                        now,
                        attack_enabled,
                        "combat_tick_visible_target",
                        npc=npc,
                        party_snapshot=party_snapshot_for_tick,
                        distance=round(distance, 2),
                        tactical_backoff=bool(tactical_backoff),
                        party_melee_survival_backoff=bool(party_melee_survival_backoff),
                        boss_hazard_backoff=bool(boss_hazard_backoff),
                        party_focus_target_backoff=bool(party_focus_target_backoff),
                        party_focus_pressure_backoff=bool(party_focus_pressure_backoff),
                        party_boss_melee_backoff=bool(party_boss_melee_backoff),
                        party_survival_backoff=bool(party_survival_backoff),
                        selected_npc_is_rescue=bool(selected_npc_is_rescue),
                        effective_attack_distance=round(effective_attack_distance, 2),
                        recent_incoming_melee=bool(recent_incoming_melee),
                        recent_incoming_attacker=last_incoming_damage_attacker_name,
                    )

                    if (
                        is_party_leader
                        and should_mark_leader_target_engaged(
                            args,
                            action_rotation,
                            attack_enabled=attack_enabled,
                            action_distance=action_distance,
                        )
                    ):
                        party_state.mark_leader_target_engaged(npc.object_id)

                    if active_combat is not None:
                        active_combat["end_distance"] = distance

                        if should_count_attack_attempt(
                            args,
                            action_rotation,
                            attack_enabled=attack_enabled,
                            action_distance=action_distance,
                        ):
                            active_combat["attacks"] = int(active_combat["attacks"]) + 1

                    reaggro_taunt_due = should_active_tank_reaggro_taunt(
                        args,
                        party_snapshot_for_tick,
                        party_member_name,
                        action_rotation,
                        now=now,
                        next_taunt=next_active_tank_reaggro_taunt,
                    )
                    if (
                        not party_melee_survival_backoff
                        and not boss_hazard_backoff
                        and not party_focus_target_backoff
                        and not party_focus_pressure_backoff
                        and not party_boss_melee_backoff
                        and not party_survival_backoff
                    ):
                        prefer_taunt_skill = should_prefer_taunt_skill_for_target(
                            args,
                            party_snapshot_for_tick,
                            member_name=party_member_name,
                            action_rotation=action_rotation,
                            selected_npc_is_rescue=bool(selected_npc_is_rescue),
                            selected_npc_is_required=is_required_target(args, npc),
                            reaggro_taunt_due=reaggro_taunt_due,
                        )
                        rotation_action, next_skill, next_active_tank_reaggro_taunt = perform_due_rotation_action(
                            client,
                            rng,
                            args,
                            action_rotation,
                            action_distance,
                            combat_plan,
                            active_combat=active_combat,
                            now=now,
                            next_skill=next_skill,
                            reaggro_taunt_due=reaggro_taunt_due,
                            prefer_taunt_skill=prefer_taunt_skill,
                            next_active_tank_reaggro_taunt=next_active_tank_reaggro_taunt,
                        )

                        if rotation_action is not None:
                            actions += add_action(action_counts, rotation_action)
                            cast_hold_seconds = effective_cast_action_hold_seconds(args, rotation_action)
                            if cast_hold_seconds > 0:
                                cast_action_hold_until = now + cast_hold_seconds
                                actions += add_action(action_counts, "cast_action_hold_start")

                        if reaggro_taunt_due:
                            actions += add_action(action_counts, "party_active_tank_reaggro_taunt")
                elif kept_current_target_without_visible_npc:
                    actions += add_action(action_counts, "attack_hold_last_known")
                    log_attack_decision(now, True, "combat_tick_last_known", party_snapshot=party_snapshot_for_tick)
                elif (
                    current_target
                    and active_combat is not None
                    and (args.move or args.hunter)
                    and now - current_target_last_visible_at <= float(getattr(args, "target_loss_grace", 0.0) or 0.0)
                ):
                    target_destination = active_combat_last_known_destination(active_combat)
                    if target_destination is not None:
                        client.target_object(current_target)
                        face_point_for_attack(client, target_destination.x, target_destination.y)
                        outcome = move_towards_destination(
                            client,
                            target_destination,
                            step=smooth_movement_step(args) if args.smooth_movement else args.move_step,
                            stop_distance=combat_stop_distance(args, action_rotation),
                            args=args,
                            path_state=path_state,
                            action_counts=action_counts,
                            target_in_view=False,
                        )
                        actions += outcome.actions
                        record_movement_failure(movement_failures, client, target_destination, outcome, "target_last_known")
                        actions += add_action(action_counts, "target_last_known_move" if outcome.moved else "target_last_known_hold")
                        if active_combat is not None:
                            active_combat["end_distance"] = horizontal_distance_between_points(
                                int(client.x),
                                int(client.y),
                                target_destination.x,
                                target_destination.y,
                            )
                        last_known_distance = (
                            float(active_combat["end_distance"]) if active_combat is not None else 0.0
                        )
                        leash_violated, leash_reason, leash_distance = target_home_leash_violation(client, args, None)
                        if leash_violated and not current_target_bypasses_target_home_leash(
                            args,
                            party_snapshot_for_tick,
                            current_target,
                        ):
                            rejected_targets[current_target] = now + min(args.target_failure_cooldown, 5.0)
                            abandoned_target_id = current_target
                            finish_combat("target_home_leash", now, last_known_distance)
                            log_encounter_event(
                                "target_home_leash_rejected",
                                now,
                                last_known_x=target_destination.x,
                                last_known_y=target_destination.y,
                                last_known_z=target_destination.z,
                                leash_reason=leash_reason,
                                leash_distance=round(leash_distance, 2),
                            )
                            client.clear_target()
                            client.set_attack_mode(False)
                            current_target = 0
                            clear_shared_leader_target_on_abandon(now, "target_home_leash", abandoned_target_id)
                            actions += add_action(action_counts, "target_home_leash")
                            attack_enabled = False
                        else:
                            attack_enabled = is_melee_rotation(action_rotation) and last_known_distance <= melee_stop_distance(args)
                        if attack_enabled:
                            client.target_object(current_target)
                            face_point_for_attack(client, target_destination.x, target_destination.y)
                            client.send_position_update(speed=0.0, target_in_view=True)
                            actions += add_action(action_counts, "attack_target_in_view_update")
                            prime_delay = attack_target_in_view_prime_delay(
                                args,
                                recent_incoming_melee=False,
                            )
                            newly_primed = attack_target_in_view_primed_target != current_target
                            if newly_primed:
                                attack_target_in_view_primed_target = current_target
                                attack_target_in_view_primed_at = now
                            if should_wait_for_attack_target_prime(
                                primed_target=attack_target_in_view_primed_target,
                                current_target=current_target,
                                primed_at=attack_target_in_view_primed_at,
                                now=now,
                                prime_delay=prime_delay,
                            ):
                                client.set_attack_mode(False)
                                actions += add_action(
                                    action_counts,
                                    "attack_target_in_view_prime" if newly_primed else "attack_target_in_view_prime_wait",
                                )
                                attack_enabled = False
                            else:
                                client.set_attack_mode(True)
                                if active_combat is not None:
                                    active_combat["attacks"] = int(active_combat["attacks"]) + 1
                                actions += add_action(action_counts, "attack_on")
                        log_attack_decision(
                            now,
                            attack_enabled,
                            "combat_tick_target_last_known",
                            last_known_x=target_destination.x,
                            last_known_y=target_destination.y,
                            last_known_z=target_destination.z,
                            distance=round(last_known_distance, 2),
                            moved=bool(outcome.moved),
                            movement_reason=outcome.reason,
                        )
                elif (
                    current_target
                    and float(getattr(args, "target_loss_grace", 0.0) or 0.0) > 0
                    and now - current_target_last_visible_at > float(getattr(args, "target_loss_grace", 0.0) or 0.0)
                    and not should_preserve_current_party_target(args, party_state, current_target, active_combat)
                    and not fresh_hunter_target_observation(args, server_target_observations.get(current_target), now)
                ):
                    loss_after_server_los = should_treat_target_loss_as_server_los_failure(
                        active_combat,
                        max_retries_after_hit=max(
                            0,
                            int(getattr(args, "server_los_failure_max_retries_after_hit", 8) or 0),
                        ),
                    )
                    rejected_targets[current_target] = now + (
                        max(0.5, float(args.server_los_failure_target_cooldown))
                        if loss_after_server_los
                        else min(args.target_failure_cooldown, 5.0)
                    )
                    abandoned_target_id = current_target
                    finish_combat("server_los_failure" if loss_after_server_los else "target_lost", now)
                    log_encounter_event(
                        "target_lost_rejected",
                        now,
                        last_visible_age=round(now - current_target_last_visible_at, 3),
                        treated_as_server_los_failure=loss_after_server_los,
                    )
                    client.clear_target()
                    client.set_attack_mode(False)
                    current_target = 0
                    actions += add_action(action_counts, "target_lost")
                    if loss_after_server_los:
                        actions += add_action(action_counts, "target_lost_after_server_los_failure")
                        transition_to(DummyBehaviorState.DropAggroAndRecover, "target_loss_after_server_los_drop_aggro", now)
                        clear_shared_leader_target_on_abandon(
                            now,
                            "target_loss_after_server_los_drop_aggro",
                            abandoned_target_id,
                        )
                        flee_until = max(
                            flee_until,
                            now + drop_aggro_recovery_duration(args, health_percent=current_health_percent),
                        )
                        next_flee_move = now
                        next_flee_pressure_replan = now + flee_pressure_replan_cooldown(args)
                        flee_wander_heading_hold_until = 0.0
                        flee_destination = flee_escape_destination(args, client)
                        if getattr(args, "flee_use_sprint", True):
                            client.send_command("/sprint")
                            actions += add_action(action_counts, "sprint_escape")
                        actions += add_action(action_counts, "drop_aggro_flee_start")
                        log_encounter_event(
                            "flee_start",
                            now,
                            reason="target_loss_after_server_los_drop_aggro",
                            destination=destination_kind(flee_destination) if flee_destination is not None else "wander",
                        )
                else:
                    client.set_attack_mode(False)
                    actions += add_action(action_counts, "attack_off")
                    log_attack_decision(now, False, "combat_tick_no_target", party_snapshot=party_snapshot_for_tick)

                    if is_party_follower and args.party_assist_only:
                        actions += add_action(action_counts, "party_assist_wait")
                    elif should_idle_wander(args, is_party_leader=is_party_leader, current_target=current_target):
                        if path_state.graph is not None:
                            actions += add_action(action_counts, "wander_path_guard")
                        else:
                            heading = (heading + rng.randrange(-512, 513)) & 0x0FFF
                            client.wander(
                                heading,
                                step=args.wander_step,
                                movement_speed=getattr(args, "movement_speed", None),
                                min_position_send_interval=getattr(args, "movement_update_interval", 0.0),
                            )
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
            loot_metrics,
            combat_text_totals["damage_done"],
            combat_text_totals["damage_taken"],
            combat_text_totals["healing_done"],
            combat_text_totals["healing_received"],
            account.class_id,
            account.class_name,
            account.specs,
        )

    except Exception as exc:  # noqa: BLE001 - test runner should report and continue.
        if should_treat_disconnect_as_completed(exc, client, death_seen):
            finish_combat("player_death_disconnect", time.monotonic())
            actions += add_action(action_counts, "death_disconnect_complete")
            try:
                actions += add_action(action_counts, f"rotation_{resolve_action_rotation(args, index % max(args.party_size, 1))}")
            except Exception:
                pass
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
                loot_metrics,
                combat_text_totals["damage_done"],
                combat_text_totals["damage_taken"],
                combat_text_totals["healing_done"],
                combat_text_totals["healing_received"],
                account.class_id,
                account.class_name,
                account.specs,
            )

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
            loot_metrics,
            combat_text_totals["damage_done"],
            combat_text_totals["damage_taken"],
            combat_text_totals["healing_done"],
            combat_text_totals["healing_received"],
            account.class_id,
            account.class_name,
            account.specs,
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
                    class_id=int(row["class_id"]) if row.get("class_id") else None,
                    class_name=row.get("class_name", ""),
                    specs=row.get("specs", ""),
                    start_x=int(row["start_x"]) if row.get("start_x") else None,
                    start_y=int(row["start_y"]) if row.get("start_y") else None,
                    start_z=int(row["start_z"]) if row.get("start_z") else None,
                    zone_id=int(row["zone_id"]) if row.get("zone_id") else None,
                )
            )

    if not rows:
        raise ValueError(f"no accounts found in {path}")

    return rows


def auto_train_commands_from_specs(specs: str, level: int, *, full_spec: bool = False) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for part in specs.split(";"):
        if "|" not in part:
            continue
        name, value = part.split("|", 1)
        name = name.strip()
        try:
            target_level = int(value.strip())
        except ValueError:
            target_level = 0
        if name and target_level > 0:
            candidates.append((target_level, name))
    if not candidates:
        return []
    if full_spec:
        return [
            f"/train {name} {max(1, min(int(level), int(target_level)))}"
            for target_level, name in candidates
            if target_level > 1
        ]
    target_level, name = next(((target, spec_name) for target, spec_name in candidates if target > 1), candidates[0])
    train_level = max(1, min(int(level), int(target_level)))
    return [f"/train {name} {train_level}"]


def auto_train_command_from_specs(specs: str, level: int) -> str:
    commands = auto_train_commands_from_specs(specs, level)
    return commands[0] if commands else ""


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
                "class_id",
                "class_name",
                "specs",
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
                "loot_acquired",
                "damage_done",
                "damage_taken",
                "healing_done",
                "healing_received",
                "error",
                *[f"action_{action_name}" for action_name in action_names],
            ]
        )

        for result in results:
            for metric in result.metrics or []:
                combats = metric.combat_metrics or []
                durations = [combat.duration for combat in combats if combat.outcome == "target_removed"]
                combat_player_deaths = sum(1 for combat in combats if combat.outcome == "player_death")
                detected_player_deaths = int((metric.action_counts or {}).get("death_detected", 0) or 0)
                writer.writerow(
                    [
                        metric.username,
                        metric.class_id or "",
                        metric.class_name,
                        metric.specs,
                        metric.round_index,
                        metric.persona,
                        "true" if metric.ok else "false",
                        metric.actions,
                        f"{metric.elapsed:.3f}",
                        len(combats),
                        sum(1 for combat in combats if combat.outcome == "target_removed"),
                        max(combat_player_deaths, detected_player_deaths),
                        sum(1 for combat in combats if combat.outcome == "target_timeout"),
                        f"{(sum(durations) / len(durations)):.3f}" if durations else "0.000",
                        len(metric.movement_failures or []),
                        format_movement_failure_sample(metric.movement_failures or []),
                        len(metric.loot_metrics or []),
                        metric.damage_done,
                        metric.damage_taken,
                        metric.healing_done,
                        metric.healing_received,
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


def iter_loot_metrics(results: list[DummyResult]):
    for result in results:
        for metric in result.metrics or []:
            for loot_metric in metric.loot_metrics or []:
                yield metric, loot_metric


def summarize_loot(results: list[DummyResult]) -> dict[str, object]:
    loot_entries = list(iter_loot_metrics(results))
    by_tier: dict[str, int] = {}

    for _, loot_metric in loot_entries:
        by_tier[loot_metric.tier] = by_tier.get(loot_metric.tier, 0) + 1

    return {
        "total": len(loot_entries),
        "by_tier": dict(sorted(by_tier.items())),
        "samples": loot_entries[:25],
    }


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


def summarize_combat_text_totals(results: list[DummyResult]) -> dict[str, int]:
    totals = {
        "damage_done": 0,
        "damage_taken": 0,
        "healing_done": 0,
        "healing_received": 0,
    }

    for result in results:
        for metric in result.metrics or []:
            totals["damage_done"] += metric.damage_done
            totals["damage_taken"] += metric.damage_taken
            totals["healing_done"] += metric.healing_done
            totals["healing_received"] += metric.healing_received

    return totals


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
    combat_text_totals = summarize_combat_text_totals(results)
    rotation_totals = summarize_rotations(action_totals)
    persona_totals = summarize_personas(results)
    combat_summary = summarize_combat(results)
    loot_summary = summarize_loot(results)
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
        f"- Autoloot: `{getattr(args, 'auto_loot', False)}`",
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
        f"- Text parsed damage done/taken: `{combat_text_totals['damage_done']}` / `{combat_text_totals['damage_taken']}`",
        f"- Text parsed healing done/received: `{combat_text_totals['healing_done']}` / `{combat_text_totals['healing_received']}`",
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

    lines += [
        "",
        "## Loot Summary",
        "",
        f"- Items acquired: `{loot_summary['total']}`",
        "",
        "| Tier | Count |",
        "| --- | ---: |",
    ]

    loot_by_tier = loot_summary["by_tier"]

    if loot_by_tier:
        for tier, count in loot_by_tier.items():
            lines.append(f"| `{tier}` | {count} |")
    else:
        lines.append("| `none` | 0 |")

    lines += [
        "",
        "| Account | Round | Tier | Item |",
        "| --- | ---: | --- | --- |",
    ]

    loot_samples = loot_summary["samples"]

    if loot_samples:
        for metric, loot_metric in loot_samples:
            item_name = loot_metric.item_name.replace("|", "\\|")
            lines.append(f"| `{metric.username}` | {metric.round_index} | `{loot_metric.tier}` | {item_name} |")
    else:
        lines.append("| `none` | 0 | `none` | none |")

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

        party_state = PartyState(
            member_names[0],
            member_names,
            active_tank_handoff_health_percent=getattr(args, "party_active_tank_handoff_health_percent", 0),
        )

        for index in range(party_start, party_end):
            party_states[index] = party_state

    return party_states


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=DEFAULT_DUMMY_HOST)
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
    parser.add_argument(
        "--combat-usable-api",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="load each logged-in dummy's real usable skill/spell snapshot from /api/dummy/combat/usable",
    )
    parser.add_argument("--combat-usable-api-url", default="", help="override combat usable API endpoint; default is http://HOST:API_PORT/api/dummy/combat/usable")
    parser.add_argument("--combat-usable-api-timeout", type=float, default=2.0)
    parser.add_argument("--combat-usable-api-retries", type=int, default=6)
    parser.add_argument("--combat-usable-api-retry-delay", type=float, default=0.5)
    parser.add_argument("--startup-self-buff-count", type=int, default=0, help="cast up to N validated self buff spells after combat usable plan load")
    parser.add_argument("--startup-self-buff-delay", type=float, default=0.8, help="seconds to wait between startup self buffs")
    parser.add_argument(
        "--required-target-api",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="poll /api/dummy/combat/npcs for the configured required target and refresh shared objective coordinates",
    )
    parser.add_argument("--required-target-api-url", default="", help="override required target NPC API endpoint")
    parser.add_argument("--required-target-api-name", default="", help="override required target name used by --required-target-api")
    parser.add_argument("--required-target-api-region", type=int, default=-1, help="region filter for --required-target-api; -1 uses client zone")
    parser.add_argument("--required-target-api-limit", type=int, default=20)
    parser.add_argument("--required-target-api-interval", type=float, default=2.0)
    parser.add_argument("--required-target-api-timeout", type=float, default=1.5)
    parser.add_argument(
        "--current-target-api-refresh",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="on server melee range/visibility failures, refresh the current target coordinates from /api/dummy/combat/npcs by objectId",
    )
    parser.add_argument("--current-target-api-timeout", type=float, default=0.5)
    parser.add_argument("--current-target-api-max-age", type=float, default=4.0)
    parser.add_argument("--current-target-api-refresh-interval", type=float, default=0.75)
    parser.add_argument(
        "--hunter-target-api-scout",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="when local visible NPC scan has no eligible target, ask /api/dummy/combat/npcs for nearby level-appropriate targets",
    )
    parser.add_argument("--hunter-target-api-radius", type=float, default=6500.0)
    parser.add_argument("--hunter-target-api-limit", type=int, default=80)
    parser.add_argument("--hunter-target-api-timeout", type=float, default=0.75)
    parser.add_argument("--hunter-target-api-max-age", type=float, default=20.0)
    parser.add_argument(
        "--hunter-target-api-engage-distance",
        type=float,
        default=0.0,
        help="only turn server-scouted hunter targets within this distance into combat targets; 0 uses --max-target-distance",
    )
    parser.add_argument(
        "--hunter-target-max-ground-z-delta",
        type=float,
        default=0.0,
        help="reject hunter candidates whose NPC Z differs from the sampled ground Z by more than this; 0 disables",
    )
    parser.add_argument(
        "--hunter-min-time-left-for-new-target",
        type=float,
        default=0.0,
        help="after at least one kill, stop pulling fresh hunter targets when the finite run is almost over",
    )
    parser.add_argument(
        "--required-target-catchup-distance",
        type=float,
        default=0.0,
        help="if a required target is not yet in combat and moves farther than this distance, reposition this dummy near it; 0 disables",
    )
    parser.add_argument("--required-target-catchup-offset", type=float, default=250.0)
    parser.add_argument("--combat-plan-skill-pool", type=int, default=4, help="pick validated melee styles from the top N highest-level usable styles")
    parser.add_argument("--combat-plan-spell-pool", type=int, default=3, help="pick validated spells from the top N highest-level usable spells per role")
    parser.add_argument("--char-index", type=int, default=0)
    parser.add_argument("--login-retries", type=int, default=2, help="retry transient login handshakes that connect but do not receive a session id")
    parser.add_argument("--login-retry-delay", type=float, default=1.0, help="seconds to wait before reconnecting after a transient session-id login failure")
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
    # Movement/load runs should stay on the destination heading unless a scenario explicitly opts into
    # cosmetic turns. The older dummy tools and historical smoke runs defaulted this to 0.
    parser.add_argument("--turn-interval", type=float, default=0.0)
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
    parser.add_argument(
        "--auto-loot",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="send /autoloot on immediately after login and count acquired loot messages in reports",
    )
    parser.add_argument("--target-pool", type=int, default=5, help="randomly pick from the nearest N known NPCs")
    parser.add_argument("--npc-max-age", type=float, default=60.0)
    parser.add_argument("--player-level", type=int, default=1)
    parser.add_argument("--ideal-target-level", type=int, default=0, help="preferred NPC level for smart target scoring; 0 uses --player-level")
    parser.add_argument("--min-target-level", type=int, default=1)
    parser.add_argument("--max-target-level", type=int, default=-1, help="absolute maximum NPC level; -1 uses player level plus delta")
    parser.add_argument("--max-target-level-delta", type=int, default=2)
    parser.add_argument("--max-target-distance", type=float, default=0.0, help="ignore targets farther than this distance; 0 disables the cap")
    parser.add_argument("--target-home-max-distance", type=float, default=0.0, help="when --required-target-home is set, ignore hunter targets farther than this from that home; 0 disables")
    parser.add_argument("--combat-home-leash-distance", type=float, default=0.0, help="drop the current combat target when the player or target is dragged this far from --required-target-home; 0 disables")
    parser.add_argument("--combat-chase-max-distance", type=float, default=0.0, help="abort unproven combat if the visible target opens more than this distance; 0 disables")
    parser.add_argument("--combat-chase-max-distance-grace", type=float, default=3.0, help="seconds before --combat-chase-max-distance can abort a newly selected target")
    parser.add_argument("--target-timeout", type=float, default=20.0)
    parser.add_argument(
        "--target-timeout-active-combat-grace",
        type=float,
        default=8.0,
        help="seconds of recent combat progress that prevent target-timeout rejection",
    )
    parser.add_argument("--target-loss-grace", type=float, default=8.0, help="seconds to keep a normal target after it leaves visibility before reacquiring")
    parser.add_argument(
        "--reject-target-on-server-los-failure",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="retarget after the server reports the current target is not visible or too far; useful for growth smoke loops with stale NPC positions",
    )
    parser.add_argument(
        "--server-los-failure-target-cooldown",
        type=float,
        default=4.0,
        help="seconds to avoid the current target after a server visibility/range failure when retargeting is enabled",
    )
    parser.add_argument(
        "--server-los-failure-grace",
        type=float,
        default=8.0,
        help="seconds to retry a no-damage target after server visibility/range failures before retargeting",
    )
    parser.add_argument(
        "--server-los-failure-max-retries-after-hit",
        type=int,
        default=8,
        help="maximum server visibility/range failures to tolerate after the dummy has damaged the target before dropping it",
    )
    parser.add_argument(
        "--server-los-failure-kind-cooldown",
        type=float,
        default=0.0,
        help="seconds to avoid the same target name/level after a server visibility/range failure; 0 only avoids the failed object",
    )
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
    parser.add_argument("--require-target-name", default="", help="comma-separated lowercase/name fragments; if set, hunter only targets matching NPC names")
    parser.add_argument("--objective-add-target-name", default="", help="comma-separated lowercase/name fragments treated as objective camp adds")
    parser.add_argument(
        "--required-target-home",
        type=parse_waypoint,
        default=None,
        help="x,y,z point where a party leader gathers while looking for the required encounter target",
    )
    parser.add_argument(
        "--required-target-home-stop-distance",
        type=float,
        default=2500.0,
        help="stop distance from --required-target-home while scanning for the required encounter target",
    )
    parser.add_argument(
        "--required-target-home-hunt-distance",
        type=float,
        default=0.0,
        help="distance from --required-target-home where hunter target selection may start before reaching the exact home point; 0 reuses --target-home-max-distance",
    )
    parser.add_argument(
        "--required-target-recover-before-home-health-percent",
        type=int,
        default=0,
        help="when hurt below this percent, recover at the current safe point before returning to a named objective home",
    )
    parser.add_argument("--avoid-target-name", default="", help="comma-separated lowercase/name fragments to ignore")
    parser.add_argument(
        "--allow-avoid-target-fallback",
        action="store_true",
        help="treat avoided target names as last-resort candidates when no normal target is available",
    )
    parser.add_argument("--prefer-target-bonus", type=float, default=300.0)
    parser.add_argument("--target-examine-chance", type=float, default=0.0, help="chance to examine a newly selected target like a player checking it")
    parser.add_argument(
        "--target-face-command-interval",
        type=float,
        default=1.2,
        help="minimum seconds between /face commands while preserving a required boss target that is briefly out of view; 0 disables",
    )
    parser.add_argument(
        "--target-stick-command-interval",
        type=float,
        default=1.2,
        help="minimum seconds between /stick commands while preserving a required boss target; 0 disables",
    )
    parser.add_argument(
        "--target-auto-lowest-visible-level",
        action="store_true",
        help="if strict level filters find no target, pick the lowest visible preferred target at or below player level",
    )
    parser.add_argument(
        "--allow-preferred-low-con-fallback",
        action="store_true",
        help="allow preferred route targets below the strict minimum level when no normal target is available",
    )
    parser.add_argument(
        "--preferred-low-con-min-level",
        type=int,
        default=0,
        help="minimum reported level for --allow-preferred-low-con-fallback",
    )
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
    parser.add_argument("--smooth-move-interval", type=float, default=DEFAULT_PLAYER_MOVEMENT_INTERVAL)
    parser.add_argument("--movement-speed", type=float, default=DEFAULT_PLAYER_MOVEMENT_SPEED, help="movement units per second for --smooth-movement")
    parser.add_argument(
        "--movement-update-interval",
        type=float,
        default=DEFAULT_PLAYER_MOVEMENT_INTERVAL,
        help="minimum seconds between moving position packets; smooth movement looks most natural when this matches --smooth-move-interval",
    )
    parser.add_argument(
        "--server-correction-smoothing",
        action="store_true",
        help="absorb small server self-position corrections over several local ticks instead of snapping immediately",
    )
    parser.add_argument("--server-correction-min-distance", type=float, default=20.0)
    parser.add_argument("--server-correction-step", type=float, default=45.0)
    parser.add_argument("--server-correction-max-snap-distance", type=float, default=800.0)
    parser.add_argument("--ground-z-map", default="", help="JSON point cache for sampling ground Z during dummy movement")
    parser.add_argument("--ground-z-offset", type=int, default=0, help="vertical correction applied after ground Z sampling")
    parser.add_argument("--path-graph", default="", help="JSON waypoint graph used for A* dummy movement")
    parser.add_argument("--path-region", type=int, default=0, help="region id inside --path-graph; 0 uses the client's current zone id")
    parser.add_argument("--disable-graph-pathing", action="store_true")
    parser.add_argument("--path-max-node-distance", type=float, default=2500.0)
    parser.add_argument("--path-node-arrival-distance", type=float, default=160.0)
    parser.add_argument("--path-last-mile-distance", type=float, default=450.0)
    parser.add_argument("--path-max-edge-length", type=float, default=1800.0)
    parser.add_argument("--path-max-height-delta", type=int, default=450)
    parser.add_argument("--path-waypoint-ground-z-skip-delta", type=int, default=80)
    parser.add_argument("--path-replan-interval", type=float, default=3.0)
    parser.add_argument("--path-allow-water", action="store_true")
    parser.add_argument("--path-allow-closed-door", action="store_true")
    parser.add_argument("--path-allow-keep-door", action="store_true")
    parser.add_argument("--path-allow-cliff", action="store_true")
    parser.add_argument(
        "--client-grid-nav-map",
        default="",
        help="client MPK heightmap config used as lightweight outdoor A* fallback when navmesh/graph pathing is unavailable",
    )
    parser.add_argument("--client-grid-nav-cell-size", type=int, default=256)
    parser.add_argument("--client-grid-nav-max-step-z", type=int, default=240)
    parser.add_argument("--client-grid-nav-fixture-padding", type=int, default=160)
    parser.add_argument("--client-grid-nav-max-visited", type=int, default=20000)
    parser.add_argument("--client-grid-nav-allow-water", action="store_true")
    parser.add_argument("--nav-api-url", default="", help="server API root used for navmesh path queries, for example http://127.0.0.1:5000")
    parser.add_argument("--nav-api-timeout", type=float, default=1.0)
    parser.add_argument("--nav-api-max-nodes", type=int, default=128)
    parser.add_argument("--nav-api-snap", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--nav-api-avoid-blocking-doors", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--nav-segment-validate", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--attack-range", type=float, default=350.0)
    parser.add_argument(
        "--combat-direct-move-distance",
        type=float,
        default=450.0,
        help="bypass nav pathing and move directly to a visible combat target inside this distance",
    )
    parser.add_argument(
        "--attack-target-in-view-prime-delay",
        type=float,
        default=0.0,
        help="seconds to wait after sending a target-in-view position update before enabling attack mode",
    )
    parser.add_argument("--melee-range-buffer", type=float, default=25.0, help="stand this much inside attack range before attacking")
    parser.add_argument("--minimum-melee-stop-distance", type=float, default=70.0)
    parser.add_argument(
        "--melee-stick-attack",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="for melee rotations, keep attack mode on while sticking to the selected target instead of waiting for exact melee range",
    )
    parser.add_argument(
        "--melee-stick-attack-distance",
        type=float,
        default=1200.0,
        help="maximum distance for --melee-stick-attack; 0 keeps attack mode on whenever a melee target is selected",
    )
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
    parser.add_argument(
        "--waypoint-continuous-turns",
        action="store_true",
        help="advance to the next waypoint before sending a stop packet when close to the current waypoint",
    )
    parser.add_argument(
        "--waypoint-advance-distance",
        type=float,
        default=0.0,
        help="distance used by --waypoint-continuous-turns; 0 reuses --waypoint-stop-distance",
    )
    parser.add_argument("--flee-health-percent", type=int, default=0, help="retreat when health is at or below this percent; 0 disables fleeing")
    parser.add_argument("--flee-pressure-health-percent", type=int, default=0, help="retreat earlier at or below this percent when combat damage pressure is bad or damage is untracked")
    parser.add_argument("--flee-duration", type=float, default=4.0)
    parser.add_argument("--flee-step", type=float, default=360.0)
    parser.add_argument("--flee-move-interval", type=float, default=0.8)
    parser.add_argument("--flee-movement-speed", type=float, default=240.0, help="movement packet speed while fleeing; models sprint without tripping server movement validation")
    parser.add_argument("--flee-use-sprint", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--flee-home", type=parse_waypoint, default=None, help="x,y,z safe point to run toward when fleeing; defaults to --required-target-home")
    parser.add_argument("--flee-home-stop-distance", type=float, default=900.0)
    parser.add_argument("--flee-dynamic-safe-point", action=argparse.BooleanOptionalAction, default=False, help="when fleeing, run away from nearby observed NPC threats before falling back to --flee-home")
    parser.add_argument("--flee-safe-threat-radius", type=float, default=2500.0)
    parser.add_argument("--flee-safe-point-distance", type=float, default=1800.0)
    parser.add_argument("--flee-critical-health-percent", type=int, default=65)
    parser.add_argument("--flee-critical-safe-point-distance", type=float, default=4200.0)
    parser.add_argument("--flee-safe-api-scout", action=argparse.BooleanOptionalAction, default=False, help="query the combat NPC API before picking a dynamic flee-safe point")
    parser.add_argument("--flee-safe-api-timeout", type=float, default=1.0)
    parser.add_argument("--flee-safe-api-limit", type=int, default=80)
    parser.add_argument("--flee-safe-replan-damage-grace", type=float, default=6.0, help="after reaching a flee-safe point, keep fleeing if damage was taken this recently")
    parser.add_argument("--travel-aggro-clear-grace", type=float, default=18.0, help="after a travel add hits, wait this long without damage before returning to the objective")
    parser.add_argument("--travel-aggro-avoid-seconds", type=float, default=120.0, help="remember the last travel add location for temporary return-path detours")
    parser.add_argument("--travel-aggro-avoid-radius", type=float, default=0.0, help="radius around the remembered travel add to route around; 0 derives from flee-safe threat radius")
    parser.add_argument("--travel-aggro-detour-distance", type=float, default=0.0, help="side-step distance for a temporary travel add detour; 0 derives from avoid radius")
    parser.add_argument("--flee-town-health-percent", type=int, default=10, help="at or below this health, prefer the configured flee-home/town path over a short dynamic safe point")
    parser.add_argument("--flee-min-combat-seconds", type=float, default=0.0)
    parser.add_argument("--flee-min-damage-taken", type=int, default=0)
    parser.add_argument("--flee-damage-taken-ratio", type=float, default=0.0)
    parser.add_argument(
        "--flee-melee-counterattack-min-attacks",
        type=int,
        default=0,
        help="while recently hit in melee and above critical health, delay losing-combat flee until this many attack ticks have been attempted",
    )
    parser.add_argument(
        "--flee-melee-counterattack-health-floor",
        type=int,
        default=0,
        help="do not delay losing-combat flee for melee counterattacks at or below this health percent",
    )
    parser.add_argument(
        "--flee-melee-counterattack-max-distance",
        type=float,
        default=0.0,
        help="only delay losing-combat flee before dealing damage when the target is this close; 0 disables the distance guard",
    )
    parser.add_argument(
        "--required-target-tank-commit-health-percent",
        type=int,
        default=0,
        help="for named required objectives, keep the tank committed above this health percent even inside the normal critical flee band",
    )
    parser.add_argument("--rest-chance", type=float, default=0.0)
    parser.add_argument("--rest-min", type=float, default=1.0)
    parser.add_argument("--rest-max", type=float, default=3.0)
    parser.add_argument("--low-health-rest-percent", type=int, default=0)
    parser.add_argument("--low-health-rest-resume-percent", type=int, default=85)
    parser.add_argument("--low-health-rest-min", type=float, default=5.0)
    parser.add_argument("--low-health-rest-max", type=float, default=12.0)
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
    parser.add_argument("--speak-state-changes", action="store_true", help="say short visible status lines when the dummy changes major behavior state")
    parser.add_argument("--state-speech-min-interval", type=float, default=4.0, help="minimum seconds between visible state speech lines")
    parser.add_argument("--follow-nearby-player", action="store_true", help="when idle, move near the closest visible player to look like a social PvE player")
    parser.add_argument("--follow-player-name", default="", help="optional visible player name fragment to prefer for idle follow behavior")
    parser.add_argument("--player-follow-interval", type=float, default=2.0)
    parser.add_argument("--player-follow-step", type=float, default=260.0)
    parser.add_argument("--player-follow-distance", type=float, default=850.0)
    parser.add_argument("--follow-player-max-distance", type=float, default=3500.0)
    parser.add_argument(
        "--follow-player-hold-allows-waypoint",
        action="store_true",
        help="when a followed player is already close enough, allow waypoint movement to continue instead of idling",
    )
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
    parser.add_argument(
        "--allow-unvalidated-skills",
        action="store_true",
        help="send raw UseSkill index/type requests without a live usable-skill snapshot; disabled by default to avoid bad skill requests",
    )
    parser.add_argument("--spell-levels", type=parse_int_list, default=parse_int_list("1,2"), help="comma-separated UseSpell levels for caster/hybrid rotations")
    parser.add_argument("--spell-line-index", type=int, default=0)
    parser.add_argument("--spell-range", type=float, default=1500.0)
    parser.add_argument("--ranged-stop-distance", type=float, default=900.0, help="distance caster/healer roles try to keep from combat targets")
    parser.add_argument("--stationary-cast-actions", action="store_true", help="send a stop-position update before spell-like actions; disabled by default because some boss tests perform worse with it")
    parser.add_argument("--cast-action-hold", type=float, default=0.0, help="seconds to suppress movement after offensive spell-like actions so casts are less likely to be interrupted")
    parser.add_argument("--stationary-cast-min-hold", type=float, default=3.4, help="minimum movement hold for stationary spell actions; keeps 3s casts from being interrupted by tactical movement")
    parser.add_argument("--heal-spell-levels", type=parse_int_list, default=parse_int_list("1"), help="comma-separated UseSpell levels for healer-support self heal attempts")
    parser.add_argument("--heal-spell-line-index", type=int, default=0)
    parser.add_argument("--healer-self-health-percent", type=int, default=65)
    parser.add_argument("--party-buff-interval", type=float, default=0.0, help="seconds between healer-support party member buff attempts; 0 disables")
    parser.add_argument("--party-buff-spell-levels", type=parse_optional_int_list, default=[], help="comma-separated UseSpell levels for party buff attempts")
    parser.add_argument("--party-buff-spell-line-index", type=int, default=0)
    parser.add_argument(
        "--allow-unvalidated-spells",
        action="store_true",
        help="send raw UseSpell line/level requests without a live usable-spell snapshot; disabled by default to avoid server incorrect-spell warnings",
    )
    parser.add_argument("--support-spell-chance", type=float, default=0.35)
    parser.add_argument("--hybrid-melee-chance", type=float, default=0.65)
    parser.add_argument("--recovery", action="store_true", help="occasionally send /release or /pray like a player recovering from death")
    parser.add_argument("--recovery-interval", type=float, default=45.0)
    parser.add_argument("--auto-release-on-death", action="store_true", help="detect PlayerDeath packets and send /release")
    parser.add_argument("--death-release-delay", type=float, default=2.0)
    parser.add_argument("--death-recovery-cooldown", type=float, default=8.0)
    parser.add_argument("--post-release-rest", type=float, default=3.0)
    parser.add_argument("--party-size", type=int, default=1, help="group workers into leader/follower parties of this size")
    parser.add_argument(
        "--party-encounter-mode",
        choices=["standard", "boss", "quest", "siege"],
        default="standard",
        help="shared party objective mode; non-standard modes preserve the shared target without boss-name-specific combat code",
    )
    parser.add_argument("--party-invite-interval", type=float, default=10.0)
    parser.add_argument("--party-accept-interval", type=float, default=4.0)
    parser.add_argument("--party-assist-interval", type=float, default=3.0)
    parser.add_argument(
        "--party-assist-attack-delay",
        type=float,
        default=0.0,
        help="followers wait this many seconds after the leader shares a new target before attacking",
    )
    parser.add_argument(
        "--party-ranged-assist-extra-delay",
        type=float,
        default=0.0,
        help="extra caster/healer delay before assisting the shared target, giving tanks time to establish boss aggro",
    )
    parser.add_argument(
        "--party-require-leader-engaged",
        action="store_true",
        help="followers wait until the party leader reaches attack range before assisting",
    )
    parser.add_argument(
        "--party-mark-pull-engaged",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="for party assist, treat a melee leader's committed pull/chase as engaged before the first in-range swing",
    )
    parser.add_argument(
        "--party-pull-engage-distance",
        type=float,
        default=0.0,
        help="maximum melee pull/chase distance that can mark the leader target engaged when --party-mark-pull-engaged is enabled; 0 uses --melee-stick-attack-distance",
    )
    parser.add_argument(
        "--party-block-solo-required-retaliation",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="when a party is still forming, the active tank drops required-target aggro instead of solo counterattacking before the party is ready",
    )
    parser.add_argument(
        "--party-rescue-aggro",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="followers that take damage ask the party leader/tank to peel nearby non-boss attackers",
    )
    parser.add_argument("--party-rescue-max-distance", type=float, default=1400.0, help="maximum follower-to-attacker distance for rescue aggro; 0 disables the cap")
    parser.add_argument("--party-rescue-engaged-distance", type=float, default=250.0, help="non-boss rescue targets must be within this close-threat distance; 0 allows the full rescue max distance")
    parser.add_argument("--party-rescue-objective-max-distance", type=float, default=0.0, help="in shared objective modes, treat non-objective NPCs within this distance of the objective as add/rescue threats even before they hit a party member; 0 disables")
    parser.add_argument("--party-rescue-cooldown", type=float, default=2.0, help="minimum seconds between rescue requests from one follower")
    parser.add_argument("--party-rescue-min-hold", type=float, default=5.0, help="minimum seconds the leader keeps a non-boss rescue target before accepting another rescue target")
    parser.add_argument("--party-rescue-max-age", type=float, default=8.0, help="seconds the leader keeps prioritizing a rescue target")
    parser.add_argument("--party-rescue-before-objective-engaged", action=argparse.BooleanOptionalAction, default=False, help="allow rescue/add targets before a required shared objective has been engaged")
    parser.add_argument("--party-clear-objective-adds-before-engage", action=argparse.BooleanOptionalAction, default=False, help="before engaging a required shared objective, have the party leader clear visible non-objective NPCs near that objective")
    parser.add_argument("--party-rescue-objective-engaged-grace", type=float, default=8.0, help="seconds after first engaging a required shared objective before rescue/add targets may interrupt the active tank")
    parser.add_argument("--party-rescue-assist-after", type=float, default=0.0, help="seconds after a rescue/add target is requested before non-healer damage roles help the active tank; 0 keeps active-tank-only rescue")
    parser.add_argument("--party-rescue-emergency-assist-after", type=float, default=0.0, help="seconds before non-healer damage roles focus a rescue add that is actively pressuring a healer or caster; 0 disables the experimental focus rule")
    parser.add_argument("--party-rescue-peer-health-percent", type=int, default=45, help="melee peers keep assisting the shared target unless a same-role rescue victim is at or below this health percent; support/caster rescue remains immediate")
    parser.add_argument("--party-assist-rescue-target", action=argparse.BooleanOptionalAction, default=False, help="non-healer party damage roles briefly help the tank burn rescue targets such as adds; default keeps DPS on the shared objective")
    parser.add_argument("--party-caster-assist-rescue-target", action=argparse.BooleanOptionalAction, default=False, help="allow caster damage roles to chase rescue/add targets; disabled by default to avoid interrupting ranged casts")
    parser.add_argument("--party-local-rescue-target", action=argparse.BooleanOptionalAction, default=False, help="non-healer party members prioritize nearby non-boss threats before the shared boss target; default leaves rescue target handling to the active tank")
    parser.add_argument("--party-local-rescue-max-distance", type=float, default=1200.0, help="maximum distance for local self-defense target selection; 0 disables the cap")
    parser.add_argument("--party-healer-local-rescue-health-percent", type=int, default=0, help="allow healer-support roles to self-target nearby threats only at or below this health percent; 0 keeps healers focused on support")
    parser.add_argument("--party-support-evasion", action=argparse.BooleanOptionalAction, default=False, help="allow healer/caster roles that were recently hit to kite away from visible rescue threats; off by default because movement can interrupt support throughput")
    parser.add_argument("--party-follow-interval", type=float, default=1.2)
    parser.add_argument("--party-follow-step", type=float, default=320.0)
    parser.add_argument("--party-follow-distance", type=float, default=550.0)
    parser.add_argument("--party-preengage-ranged-safe-distance", type=float, default=0.0, help="caster/healer distance to keep from the required target home before they acquire a combat target; 0 disables")
    parser.add_argument("--boss-non-tank-follow-distance", type=float, default=450.0, help="during required boss fights, caster/healer followers regroup near the party leader if farther than this")
    parser.add_argument("--boss-ranged-safe-distance", type=float, default=0.0, help="during required boss fights, caster/healer followers back away from the objective itself until at least this distance; 0 reuses ranged stop distance")
    parser.add_argument("--boss-hazard-message-backoff-duration", type=float, default=0.0, help="seconds non-active-tank party members back away after boss broadcast telegraphs such as breath or massive attack; 0 disables")
    parser.add_argument("--boss-hazard-message-backoff-distance", type=float, default=0.0, help="distance non-active-tank members try to keep after boss hazard broadcasts; 0 derives from role distances")
    parser.add_argument("--party-focus-target-backoff", action=argparse.BooleanOptionalAction, default=False, help="when the shared objective is observed attacking a non-active-tank party member, that member kites away from the objective instead of trading hits")
    parser.add_argument("--party-focus-pressure-melee-backoff", action=argparse.BooleanOptionalAction, default=False, help="when the shared objective focuses any non-active-tank member, nearby non-active melee members temporarily reduce melee pressure")
    parser.add_argument("--party-focus-pressure-offtank-reaggro", action=argparse.BooleanOptionalAction, default=False, help="allow melee-basic off-tanks to stay on the shared objective and prefer taunts when it focuses support or caster members")
    parser.add_argument("--party-focus-target-max-age", type=float, default=5.0, help="seconds to trust the shared objective's observed current target for focus backoff; 0 keeps it until a new focus arrives")
    parser.add_argument("--party-focus-target-backoff-distance", type=float, default=0.0, help="distance the focused non-tank member tries to keep from the shared objective; 0 derives from boss/ranged survival spacing")
    parser.add_argument("--party-burn-required-target-health-percent", type=float, default=0.0, help="disable non-active melee focus-pressure backoff when the shared required target is at or below this health percent; 0 disables")
    parser.add_argument("--party-active-tank-last-known-stop-distance", type=float, default=0.0, help="tight stop distance used by the active tank when chasing the shared objective's last-known position; 0 derives from melee spacing")
    parser.add_argument("--party-active-tank-reaggro-taunt-interval", type=float, default=1.2, help="seconds between extra active-tank taunt attempts while the shared objective is focusing a non-active-tank member; 0 disables")
    parser.add_argument("--party-boss-non-tank-melee-backoff", action=argparse.BooleanOptionalAction, default=False, help="during required boss fights, keep non-active melee members away from the shared boss objective so only the active tank holds melee aggro")
    parser.add_argument("--party-boss-non-tank-melee-backoff-distance", type=float, default=0.0, help="distance non-active melee members try to keep from a shared boss objective; 0 derives from role distances")
    parser.add_argument("--party-melee-survival-health-percent", type=int, default=0, help="non-active melee party members back off from shared encounter targets at or below this health percent; 0 disables")
    parser.add_argument("--party-melee-survival-resume-health-percent", type=int, default=75, help="non-active melee party members stay backed off until this health percent while a survival backoff window is active")
    parser.add_argument("--party-melee-survival-backoff-duration", type=float, default=6.0, help="seconds a low-health non-active melee member keeps spacing before checking whether it can re-engage")
    parser.add_argument("--party-melee-survival-distance", type=float, default=0.0, help="distance low-health non-active melee members try to reach from the shared encounter target; 0 derives from melee/ranged settings")
    parser.add_argument("--party-survival-death-count", type=int, default=0, help="in shared encounters, trigger survival spacing after this many party deaths; 0 disables")
    parser.add_argument("--party-survival-death-window", type=float, default=45.0, help="seconds since the latest party death for shared-encounter survival spacing")
    parser.add_argument("--party-survival-active-tank-health-percent", type=int, default=0, help="trigger survival spacing when the active tank is at or below this health percent; 0 disables")
    parser.add_argument("--party-active-tank-handoff-health-percent", type=int, default=0, help="when >0, prefer a healthy off-tank as active tank if the current leader tank is at or below this health percent")
    parser.add_argument("--party-survival-backoff-distance", type=float, default=0.0, help="distance non-active melee members keep during shared-encounter survival mode; 0 derives from boss/melee spacing")
    parser.add_argument(
        "--party-target-loss-grace",
        type=float,
        default=4.0,
        help="seconds a party dummy may keep a required encounter target after it briefly disappears before forcing reacquire",
    )
    parser.add_argument(
        "--party-target-removed-preserve-limit",
        type=int,
        default=4,
        help="maximum repeated remove events to preserve for the current encounter target before clearing it for reacquire",
    )
    parser.add_argument(
        "--stop-after-required-target-removed",
        action="store_true",
        help="after a required shared objective is removed, wait briefly for loot messages and end the round instead of pulling a respawn",
    )
    parser.add_argument(
        "--target-removed-loot-wait",
        type=float,
        default=4.0,
        help="seconds to keep the client alive after required target removal so autoloot/chat loot messages can arrive",
    )
    parser.add_argument("--party-state-max-age", type=float, default=10.0)
    parser.add_argument("--party-heal-leader-interval", type=float, default=1.8)
    parser.add_argument("--party-heal-leader-health-percent", type=int, default=80)
    parser.add_argument("--party-heal-cast-range-buffer", type=float, default=200.0)
    parser.add_argument(
        "--party-friendly-cast-target-hold",
        type=float,
        default=2.6,
        help="seconds to keep a friendly heal/buff target before restoring the enemy target, so queued casts use the intended ally",
    )
    parser.add_argument("--party-use-assist-command", action="store_true")
    parser.add_argument(
        "--party-min-ready",
        type=int,
        default=0,
        help="party leader waits until this many members have accepted invites before pulling; 0 disables the gate",
    )
    parser.add_argument(
        "--party-form-up-delay",
        type=float,
        default=0.0,
        help="extra seconds the party leader waits after --party-min-ready is reached before pulling",
    )
    parser.add_argument(
        "--party-ready-max-leader-distance",
        type=float,
        default=0.0,
        help="when positive, ready party members must remain this close to the leader before the leader can pull",
    )
    parser.add_argument(
        "--party-pre-pull-home-stop-distance",
        type=float,
        default=0.0,
        help="larger required-target-home stop distance while the party is still forming, so the leader waits outside early aggro range",
    )
    parser.add_argument(
        "--party-assist-only",
        action="store_true",
        help="party followers never pick their own hunter target; they only attack the leader's shared target",
    )
    parser.add_argument(
        "--party-role-strategy",
        choices=["same", "mixed"],
        default="mixed",
        help="when action rotation is auto, assign mixed party roles by slot or use the same role for everyone",
    )
    parser.add_argument(
        "--party-slot-rotations",
        type=lambda value: [part.strip() for part in value.split(",") if part.strip()],
        default=[],
        help="comma-separated action rotations by party slot, e.g. melee-basic,melee-basic,melee-burst,healer-support",
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
        "--trace-movement-log",
        default="",
        help="optional per-client movement trace file path; supports {username}, {round}, {index}",
    )
    parser.add_argument(
        "--encounter-log",
        default="",
        help="optional per-client encounter JSONL path; supports {username}, {round}, {index}",
    )
    parser.add_argument(
        "--encounter-log-interval",
        type=float,
        default=2.0,
        help="seconds between periodic encounter snapshots when --encounter-log is enabled",
    )
    parser.add_argument(
        "--live-control-file",
        default="",
        help="optional JSON file polled while running; revision changes can tune hunter/combat distances and send one-shot commands",
    )
    parser.add_argument("--live-control-interval", type=float, default=1.0, help="seconds between live-control JSON polls")
    parser.add_argument(
        "--encounter-log-attack-decisions",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="log every attack decision instead of only attack on/off state changes",
    )
    parser.add_argument(
        "--trace-observed-player-positions",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="include every observed nearby player movement in trace logs; keep disabled for high-concurrency tests because it is very IO-heavy",
    )
    parser.add_argument(
        "--command",
        action="append",
        default=None,
        help="repeatable command. Use --command '' to disable defaults.",
    )
    parser.add_argument(
        "--startup-command",
        action="append",
        default=[],
        help="repeatable command sent once immediately after login, useful for boss start rituals such as Green Knight's defend whisper",
    )
    parser.add_argument("--startup-auto-train", action="store_true", help="send /train <best spec line> <level> from the account specs after login")
    parser.add_argument("--startup-train-full-specs", action="store_true", help="send /train for each configured spec line after login")
    parser.add_argument("--startup-train-level", type=int, default=0, help="target level for --startup-auto-train")
    parser.add_argument("--startup-train-command-delay", type=float, default=1.6, help="delay between startup /train commands")
    parser.add_argument("--startup-delay", type=float, default=0.0, help="seconds to idle after startup commands/services before combat or movement")
    parser.add_argument(
        "--startup-service-npc-name",
        default="",
        help="comma-separated NPC name fragments to target immediately after login for town service actions",
    )
    parser.add_argument("--startup-service-scan-seconds", type=float, default=1.0)
    parser.add_argument("--startup-service-interact", action="store_true")
    parser.add_argument("--startup-service-accept-dialog", action="store_true")
    parser.add_argument("--startup-service-buy-slot", action="append", type=parse_int_list, default=[])
    parser.add_argument("--startup-service-buy-count", type=int, default=1)
    parser.add_argument("--startup-service-sell-slot", action="append", type=parse_int_list, default=[])
    parser.add_argument("--startup-service-equip-slot", action="append", type=parse_int_list, default=[])
    parser.add_argument(
        "--startup-teleporter-npc-name",
        default="master visur,stor gothi annark,channeler glasny,teleporter,porter,텔레포터",
        help="comma-separated NPC name fragments used to find a town teleporter after startup service actions",
    )
    parser.add_argument("--startup-teleport-destination", default="", help="destination whispered to the startup teleporter")
    parser.add_argument("--startup-teleport-scan-seconds", type=float, default=1.0)
    parser.add_argument("--startup-teleport-approach-distance", type=float, default=150.0)
    parser.add_argument("--startup-teleport-approach-timeout", type=float, default=20.0)
    parser.add_argument("--startup-teleporter-home", type=parse_waypoint, default=None, help="x,y,z town teleporter hub to path toward when the teleporter is not initially visible")
    parser.add_argument("--startup-teleporter-home-stop-distance", type=float, default=900.0)
    parser.add_argument("--startup-teleporter-home-timeout", type=float, default=90.0)
    parser.add_argument("--startup-teleport-interact", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--startup-teleport-warmup-whisper",
        action="append",
        default=[],
        help="repeatable whisper sent to the teleporter before the destination, for opening menus if needed",
    )
    parser.add_argument(
        "--startup-teleport-warmup-delay",
        type=float,
        default=1.6,
        help="seconds to wait after each teleporter warmup whisper so NPC whisper throttling does not drop the destination",
    )
    parser.add_argument("--startup-teleport-wait-seconds", type=float, default=2.0)
    parser.add_argument(
        "--target-start-command",
        action="append",
        default=[],
        help="repeatable command sent once after selecting a new target, for encounter start rituals that require an active target",
    )
    return parser


def main() -> int:
    parser = build_parser()
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
