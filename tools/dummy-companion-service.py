#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_server_companion_config: dict[str, Any] = {}
_server_config_fetched_at: float = 0.0
_last_live_control_revision: int = 0


def next_live_control_revision() -> int:
    global _last_live_control_revision
    revision = time.time_ns()
    if revision <= _last_live_control_revision:
        revision = _last_live_control_revision + 1
    _last_live_control_revision = revision
    return revision


def fetch_server_companion_config(args: argparse.Namespace) -> dict[str, Any]:
    global _server_companion_config, _server_config_fetched_at
    now = time.monotonic()
    if now - _server_config_fetched_at < 30.0 and _server_config_fetched_at > 0:
        return _server_companion_config
    try:
        config = api_request(args, "GET", "/api/dummy/companions/config")
    except Exception:
        return _server_companion_config
    if isinstance(config, dict):
        _server_companion_config = config
        _server_config_fetched_at = now
    return _server_companion_config


def dialogue_enabled_from_server_or_cli(args: argparse.Namespace) -> bool:
    if arg_bool(args, "dialogue_enabled", False):
        return True
    config = fetch_server_companion_config(args)
    return bool(config.get("dialogue_enabled"))


VALID_ROLES = {"fill", "healer", "tank", "dps", "support"}
CONTRACT_TIERS = {"common", "skilled", "elite", "legendary"}
CONTRACT_TIER_ALIASES = {
    "normal": "common",
    "basic": "common",
    "일반": "common",
    "숙련": "skilled",
    "정예": "elite",
    "전설": "legendary",
}
CONTRACT_TIER_DEFAULTS = {
    "common": {"duration": 30 * 60, "offline_grace": 3 * 60},
    "skilled": {"duration": 45 * 60, "offline_grace": 5 * 60},
    "elite": {"duration": 60 * 60, "offline_grace": 7 * 60},
    "legendary": {"duration": 90 * 60, "offline_grace": 10 * 60},
}
ROLE_ROTATIONS = {
    "fill": "auto",
    "healer": "healer-support",
    "support": "healer-support",
    "tank": "melee-basic",
    "dps": "melee-burst",
}
REALM_GROUND_Z_MAP = {
    1: "tools/pathing/heightmaps/region001_client_zones.json",
    100: "tools/pathing/heightmaps/region100_client_zones.json",
    200: "tools/pathing/heightmaps/region200_client_zones.json",
}
RELEASE_PRIORITY = {
    "dps": 0,
    "fill": 1,
    "support": 2,
    "tank": 3,
    "healer": 4,
}
CLASS_ROLE_HINTS = {
    "armsman": {"tank", "dps"},
    "animist": {"support", "dps"},
    "bainshee": {"support", "dps"},
    "berserker": {"dps"},
    "blademaster": {"dps"},
    "bonedancer": {"support", "dps"},
    "cabalist": {"support", "dps"},
    "champion": {"dps", "tank"},
    "cleric": {"healer", "support"},
    "druid": {"healer", "support"},
    "eldritch": {"support", "dps"},
    "enchanter": {"support", "dps"},
    "friar": {"healer", "support", "dps"},
    "healer": {"healer", "support"},
    "heretic": {"healer", "support", "dps"},
    "hero": {"tank", "dps"},
    "paladin": {"tank", "support"},
    "hunter": {"dps"},
    "infiltrator": {"dps"},
    "mauleralb": {"tank", "dps"},
    "maulerhib": {"tank", "dps"},
    "maulermid": {"tank", "dps"},
    "mentalist": {"support", "dps"},
    "mercenary": {"dps"},
    "minstrel": {"support", "dps"},
    "necromancer": {"support", "dps"},
    "nightshade": {"dps"},
    "ranger": {"dps"},
    "reaver": {"tank", "dps"},
    "runemaster": {"support", "dps"},
    "savage": {"dps"},
    "scout": {"dps"},
    "shadowblade": {"dps"},
    "shaman": {"healer", "support"},
    "bard": {"healer", "support"},
    "skald": {"support", "dps"},
    "sorcerer": {"support", "dps"},
    "spiritmaster": {"support", "dps"},
    "thane": {"tank", "dps"},
    "theurgist": {"support", "dps"},
    "valewalker": {"dps"},
    "valkyrie": {"tank", "support", "dps"},
    "vampiir": {"dps"},
    "warden": {"healer", "support", "tank", "dps"},
    "warlock": {"support", "dps"},
    "warrior": {"tank", "dps"},
    "wizard": {"dps"},
}
CLASS_ROTATION_HINTS = {
    "animist": "caster-basic",
    "bainshee": "caster-basic",
    "bard": "healer-support",
    "bonedancer": "caster-basic",
    "cabalist": "caster-basic",
    "cleric": "healer-support",
    "druid": "healer-support",
    "eldritch": "caster-basic",
    "enchanter": "caster-basic",
    "friar": "healer-support",
    "healer": "healer-support",
    "heretic": "healer-support",
    "mentalist": "caster-basic",
    "minstrel": "hybrid",
    "necromancer": "caster-basic",
    "runemaster": "caster-basic",
    "shaman": "healer-support",
    "skald": "hybrid",
    "sorcerer": "caster-basic",
    "spiritmaster": "caster-basic",
    "thane": "hybrid",
    "theurgist": "caster-basic",
    "valewalker": "hybrid",
    "valkyrie": "hybrid",
    "vampiir": "hybrid",
    "warden": "healer-support",
    "warlock": "caster-basic",
    "wizard": "caster-basic",
}
CLASS_CAPABILITY_HINTS = {
    "animist": {"caster_dps", "offensive_support"},
    "armsman": {"defensive_tank"},
    "bainshee": {"caster_dps", "dedicated_dps"},
    "bard": {"speed_song", "group_support"},
    "berserker": {"dedicated_dps", "melee_dps"},
    "blademaster": {"dedicated_dps", "melee_dps"},
    "bonedancer": {"caster_dps", "offensive_support"},
    "cabalist": {"caster_dps", "offensive_support"},
    "eldritch": {"caster_dps", "dedicated_dps"},
    "enchanter": {"caster_dps", "dedicated_dps"},
    "friar": {"self_sustain"},
    "hero": {"defensive_tank"},
    "hunter": {"dedicated_dps", "ranged_dps", "stealth"},
    "infiltrator": {"dedicated_dps", "melee_dps", "stealth"},
    "mauleralb": {"melee_dps", "self_sustain"},
    "maulerhib": {"melee_dps", "self_sustain"},
    "maulermid": {"melee_dps", "self_sustain"},
    "mentalist": {"caster_dps", "offensive_support"},
    "mercenary": {"dedicated_dps", "melee_dps"},
    "minstrel": {"crowd_control", "speed_song", "stealth"},
    "necromancer": {"caster_dps", "offensive_support"},
    "nightshade": {"dedicated_dps", "melee_dps", "stealth"},
    "paladin": {"defensive_tank", "group_support", "self_sustain"},
    "ranger": {"dedicated_dps", "ranged_dps", "stealth"},
    "reaver": {"defensive_tank"},
    "runemaster": {"caster_dps", "dedicated_dps"},
    "savage": {"dedicated_dps", "melee_dps"},
    "scout": {"dedicated_dps", "ranged_dps", "stealth"},
    "shadowblade": {"dedicated_dps", "melee_dps", "stealth"},
    "skald": {"speed_song", "melee_dps"},
    "sorcerer": {"caster_dps", "crowd_control", "offensive_support"},
    "spiritmaster": {"caster_dps", "offensive_support"},
    "theurgist": {"caster_dps", "crowd_control", "offensive_support"},
    "valewalker": {"melee_dps"},
    "valkyrie": {"defensive_tank", "self_sustain"},
    "vampiir": {"dedicated_dps", "melee_dps", "self_sustain"},
    "warden": {"defensive_tank", "group_support", "self_sustain"},
    "warrior": {"defensive_tank"},
    "warlock": {"caster_dps", "offensive_support"},
    "wizard": {"caster_dps", "dedicated_dps"},
}
DEFAULT_TANK_CAPABILITY_WEIGHTS = {
    "defensive_tank": 30,
    "self_sustain": 20,
    "group_support": 10,
}
DEFAULT_DPS_CAPABILITY_WEIGHTS = {
    "dedicated_dps": 30,
    "melee_dps": 20,
    "caster_dps": 20,
    "ranged_dps": 15,
    "self_sustain": 5,
    "offensive_support": 5,
}
BOSS_DPS_CAPABILITY_WEIGHTS = {
    "caster_dps": 30,
    "ranged_dps": 25,
    "offensive_support": 10,
    "crowd_control": 10,
    "melee_dps": -15,
}
CAPABILITY_ALIASES = {
    "groupspeed": "group_speed",
    "scout": "stealth",
    "speedsong": "speed_song",
}
LIVE_COMPANION_FLEE_FLAGS = [
    "--flee-dynamic-safe-point",
    "--flee-safe-api-scout",
    "--flee-pressure-health-percent",
    "90",
    "--flee-safe-threat-radius",
    "9000",
    "--flee-safe-point-distance",
    "10500",
    "--flee-duration",
    "28",
    "--flee-step",
    "1200",
    "--flee-move-interval",
    "0.30",
    "--flee-movement-speed",
    "300",
]
LIVE_COMPANION_PARTY_COORDINATION_FLAGS = [
    "--party-rescue-aggro",
    "--party-rescue-before-objective-engaged",
    "--party-block-solo-required-retaliation",
    "--party-support-evasion",
    "--party-rescue-max-distance",
    "6500",
    "--party-rescue-objective-max-distance",
    "6500",
    "--party-rescue-max-age",
    "16",
    "--party-active-tank-handoff-health-percent",
    "100",
    "--party-focus-target-backoff",
    "--party-focus-pressure-offtank-reaggro",
    "--party-active-tank-reaggro-taunt-interval",
    "0.8",
    "--party-protection-interval",
    "4",
    "--party-focus-target-max-age",
    "6",
    "--party-target-loss-grace",
    "12",
    "--party-target-removed-preserve-limit",
    "12",
    "--flee-melee-counterattack-health-floor",
    "45",
    "--required-target-tank-commit-health-percent",
    "25",
    "--current-target-api-refresh",
    "--reject-target-on-server-los-failure",
    "--server-los-failure-grace",
    "12",
    "--server-los-failure-max-retries-after-hit",
    "16",
]
ROOT = Path(__file__).resolve().parents[1]


class ActiveCompanion:
    def __init__(
        self,
        request: dict[str, Any],
        process: subprocess.Popen,
        account: str = "",
        control_path: Path | None = None,
    ) -> None:
        self.request = request
        self.process = process
        self.account = account
        self.control_path = control_path
        self.last_lease_refresh = time.monotonic()
        self.last_request_status_check = 0.0
        self.requester_offline_since = 0.0


def normalize_role(role: Any) -> str:
    normalized = str(role or "").strip().lower()
    return normalized if normalized in VALID_ROLES else "fill"


def normalize_contract_tier(tier: Any) -> str:
    normalized = str(tier or "").strip().lower()
    normalized = CONTRACT_TIER_ALIASES.get(normalized, normalized)
    return normalized if normalized in CONTRACT_TIERS else "common"


def request_contract_tier(request: dict[str, Any]) -> str:
    explicit = request_value(request, "contractTier", "ContractTier", "tier", "Tier", default="")
    if explicit:
        return normalize_contract_tier(explicit)
    capabilities = str(request_value(request, "requestedCapabilities", "RequestedCapabilities", default="") or "")
    for part in capabilities.replace("|", ",").replace(";", ",").split(","):
        token = part.strip()
        lowered = token.lower()
        if lowered.startswith("tier:"):
            return normalize_contract_tier(token.split(":", 1)[1])
        if lowered.startswith("contract_tier:"):
            return normalize_contract_tier(token.split(":", 1)[1])
    return "common"


def request_contract_duration_seconds(request: dict[str, Any]) -> int:
    configured = parse_int(request_value(request, "contractDurationSeconds", "ContractDurationSeconds", default=0))
    if configured > 0:
        return configured
    return int(CONTRACT_TIER_DEFAULTS[request_contract_tier(request)]["duration"])


def request_offline_grace_seconds(request: dict[str, Any]) -> int:
    configured = parse_int(request_value(request, "offlineGraceSeconds", "OfflineGraceSeconds", default=0))
    if configured > 0:
        return configured
    return int(CONTRACT_TIER_DEFAULTS[request_contract_tier(request)]["offline_grace"])


def role_to_rotation(role: Any) -> str:
    return ROLE_ROTATIONS[normalize_role(role)]


def live_companion_uses_hostile_assist(
    role: Any,
    action_rotation: str,
    request: dict[str, Any] | None = None,
) -> bool:
    if normalize_role(role) in {"healer", "support"} and action_rotation == "healer-support":
        return not bool(request_objective_target_name(request or {}))
    return True


def live_companion_party_assist_interval(
    role: Any,
    action_rotation: str,
    request: dict[str, Any] | None = None,
) -> str:
    return "0.6" if live_companion_uses_hostile_assist(role, action_rotation, request) else "0"


def live_companion_party_assist_attack_delay(
    role: Any,
    action_rotation: str,
    request: dict[str, Any] | None = None,
) -> str:
    if not live_companion_uses_hostile_assist(role, action_rotation, request):
        return "0"
    if normalize_role(role) in {"healer", "support"} and action_rotation == "healer-support":
        return "0"
    if live_companion_claims_objective_target(role, action_rotation):
        return "0.3"
    if action_rotation.startswith("caster"):
        return "1.0"
    return "8.0"


def live_companion_ranged_assist_extra_delay(role: Any, action_rotation: str) -> str:
    if normalize_role(role) in {"healer", "support"} and action_rotation == "healer-support":
        return "0"
    if action_rotation.startswith("caster"):
        return "0"
    return "0"


def live_companion_follow_distance(role: Any, action_rotation: str) -> str:
    # Live companions should stay tight while travelling so the player does not
    # feel the party stretching out. Combat spacing is handled by the separate
    # boss/preengage/ranged safe-distance flags.
    return "120"


def live_companion_follow_hold_allows_waypoint(role: Any, action_rotation: str) -> bool:
    return not (normalize_role(role) == "healer" and action_rotation == "healer-support")


def live_companion_requires_follow_anchor_before_objective(role: Any, action_rotation: str) -> bool:
    normalized_role = normalize_role(role)
    return normalized_role in {"healer", "support"} or action_rotation.startswith("caster")


def live_companion_waypoint_stop_distance(role: Any, action_rotation: str) -> str:
    normalized_role = normalize_role(role)
    if normalized_role == "support":
        return "900"
    if normalized_role == "healer" and action_rotation == "healer-support":
        return "1500"
    if action_rotation.startswith("caster"):
        return "1500"
    return "650"


def live_companion_required_home_stop_distance(role: Any, action_rotation: str) -> str:
    normalized_role = normalize_role(role)
    if normalized_role == "support":
        return "1100"
    if normalized_role == "healer" and action_rotation == "healer-support":
        return "1800"
    if action_rotation.startswith("caster"):
        return "1400"
    return "900"


def live_companion_required_home_hunt_distance(role: Any, action_rotation: str) -> str:
    normalized_role = normalize_role(role)
    if normalized_role == "support":
        return "2800"
    if normalized_role == "healer" and action_rotation == "healer-support":
        return "3200"
    if action_rotation.startswith("caster"):
        return "3200"
    return "2800"


def live_companion_claims_objective_target(role: Any, action_rotation: str) -> bool:
    normalized_role = normalize_role(role)
    if normalized_role == "tank":
        return True
    return normalized_role == "fill" and action_rotation in {"melee-basic", "hybrid"}


def live_companion_boss_role_flags(role: Any, action_rotation: str, args: argparse.Namespace | None = None) -> list[str]:
    normalized_role = normalize_role(role)
    healer_boss_ranged_safe_distance = "1800"
    healer_party_preengage_ranged_safe_distance = "2000"
    healer_boss_non_tank_follow_distance = "1800"
    if normalized_role == "healer" and action_rotation == "healer-support" and args is not None:
        def configured_override(name: str) -> float:
            try:
                return float(getattr(args, name, 0.0) or 0.0)
            except (TypeError, ValueError):
                return 0.0

        configured_boss_ranged_safe_distance = configured_override("healer_boss_ranged_safe_distance")
        configured_party_preengage_ranged_safe_distance = configured_override(
            "healer_party_preengage_ranged_safe_distance"
        )
        configured_boss_non_tank_follow_distance = configured_override("healer_boss_non_tank_follow_distance")
        if configured_boss_ranged_safe_distance > 0.0:
            healer_boss_ranged_safe_distance = str(int(configured_boss_ranged_safe_distance))
        if configured_party_preengage_ranged_safe_distance > 0.0:
            healer_party_preengage_ranged_safe_distance = str(int(configured_party_preengage_ranged_safe_distance))
        if configured_boss_non_tank_follow_distance > 0.0:
            healer_boss_non_tank_follow_distance = str(int(configured_boss_non_tank_follow_distance))

    flags = [
        "--party-require-leader-engaged",
        "--party-mark-pull-engaged",
        "--party-pull-engage-distance",
        "1800",
        "--boss-hazard-message-backoff-duration",
        "9",
        "--boss-hazard-message-backoff-distance",
        "2400",
        "--party-focus-target-backoff-distance",
        "1400",
        "--party-melee-survival-health-percent",
        "45",
        "--party-melee-survival-resume-health-percent",
        "80",
        "--party-melee-survival-backoff-duration",
        "12",
        "--party-survival-death-count",
        "1",
        "--party-survival-death-window",
        "75",
        "--party-survival-active-tank-health-percent",
        "25",
        "--party-survival-backoff-distance",
        "1200",
    ]
    if live_companion_claims_objective_target(role, action_rotation):
        flags.extend(
            [
                "--party-rescue-assist-after",
                "3",
                "--party-rescue-emergency-assist-after",
                "2",
                "--party-active-tank-last-known-stop-distance",
                "25",
            ]
        )
    elif action_rotation.startswith("melee") or action_rotation == "hybrid":
        flags.extend(
            [
                "--party-rescue-assist-after",
                "0",
                "--party-rescue-emergency-assist-after",
                "0",
                "--party-boss-non-tank-melee-backoff",
                "--party-boss-non-tank-melee-backoff-distance",
                "1400",
                "--party-focus-pressure-melee-backoff",
                "--party-burn-required-target-health-percent",
                "20",
            ]
        )
    if action_rotation == "caster-basic":
        flags.extend(
            [
                "--party-rescue-assist-after",
                "0",
                "--party-rescue-emergency-assist-after",
                "0",
                "--boss-ranged-safe-distance",
                "1400",
                "--party-preengage-ranged-safe-distance",
                "1500",
                "--boss-non-tank-follow-distance",
                "1200",
                "--stationary-cast-actions",
                "--stationary-cast-min-hold",
                "3.4",
            ]
        )
    elif action_rotation == "healer-support" or normalized_role == "support":
        flags.extend(
            [
                "--party-rescue-assist-after",
                "0",
                "--party-rescue-emergency-assist-after",
                "0",
                "--boss-ranged-safe-distance",
                "1400" if normalized_role == "support" else healer_boss_ranged_safe_distance,
                "--party-preengage-ranged-safe-distance",
                "1500" if normalized_role == "support" else healer_party_preengage_ranged_safe_distance,
                "--boss-non-tank-follow-distance",
                "1400" if normalized_role == "support" else healer_boss_non_tank_follow_distance,
            ]
        )
    return flags


def live_companion_field_role_flags(role: Any, action_rotation: str) -> list[str]:
    normalized_role = normalize_role(role)
    if action_rotation == "caster-basic" or (
        normalized_role in {"healer", "support"} and action_rotation == "healer-support"
    ):
        return [
            "--ranged-stop-distance",
            "650",
            "--attack-target-in-view-prime-delay",
            "0.75",
        ]
    if action_rotation.startswith("melee") or action_rotation == "hybrid":
        return [
            "--target-face-command-interval",
            "0",
            "--melee-stick-attack-distance",
            "330",
        ]
    return []


def live_companion_role_flags(role: Any, action_rotation: str, args: argparse.Namespace | None = None) -> list[str]:
    flags: list[str] = []
    if normalize_role(role) in {"healer", "support"} and action_rotation == "healer-support":
        flags.extend(
            [
                "--healer-self-health-percent",
                "92",
                "--party-heal-leader-health-percent",
                "92",
                "--party-heal-leader-interval",
                "1.0",
                "--self-preserve-heal-min-interval",
                "8.0",
            ]
        )
        if args is not None:
            flee_pressure = arg_float(args, "healer_flee_pressure_health_percent", 0.0)
            flee_health = arg_float(args, "healer_flee_health_percent", 0.0)
            if flee_pressure > 0.0:
                flags.extend(
                    [
                        "--flee-pressure-health-percent",
                        str(int(flee_pressure)),
                    ]
                )
            if flee_health > 0.0:
                flags.extend(
                    [
                        "--flee-health-percent",
                        str(int(flee_health)),
                    ]
                )
            heal_exclude_names = str(getattr(args, "healer_heal_exclude_names", "") or "").strip()
            if heal_exclude_names:
                flags.extend(["--party-heal-exclude-names", heal_exclude_names])
    return flags


def live_companion_contract_tier_flags(request: dict[str, Any]) -> list[str]:
    tier = request_contract_tier(request)
    if tier == "common":
        return []
    profiles = {
        "skilled": {
            "combat": "0.52",
            "skill": "0.85",
            "api_retry": "0.32",
            "follow_interval": "0.22",
            "move_interval": "0.16",
            "flee_speed": "315",
            "buff_count": "3",
        },
        "elite": {
            "combat": "0.45",
            "skill": "0.72",
            "api_retry": "0.25",
            "follow_interval": "0.18",
            "move_interval": "0.14",
            "flee_speed": "335",
            "buff_count": "4",
        },
        "legendary": {
            "combat": "0.38",
            "skill": "0.60",
            "api_retry": "0.18",
            "follow_interval": "0.14",
            "move_interval": "0.12",
            "flee_speed": "360",
            "buff_count": "5",
        },
    }
    profile = profiles[tier]
    return [
        "--combat-interval",
        profile["combat"],
        "--skill-interval",
        profile["skill"],
        "--combat-usable-api-retry-delay",
        profile["api_retry"],
        "--party-follow-interval",
        profile["follow_interval"],
        "--smooth-move-interval",
        profile["move_interval"],
        "--movement-update-interval",
        profile["move_interval"],
        "--flee-movement-speed",
        profile["flee_speed"],
        "--startup-self-buff-count",
        profile["buff_count"],
    ]


def live_companion_service_flee_flags(args: argparse.Namespace | None) -> list[str]:
    if args is None:
        return []

    flags: list[str] = []
    flee_pressure = arg_float(args, "companion_flee_pressure_health_percent", 0.0)
    flee_health = arg_float(args, "companion_flee_health_percent", 0.0)
    if flee_pressure > 0.0:
        flags.extend(
            [
                "--flee-pressure-health-percent",
                str(int(flee_pressure)),
            ]
        )
    if flee_health > 0.0:
        flags.extend(
            [
                "--flee-health-percent",
                str(int(flee_health)),
            ]
        )
    return flags


def party_vacancy(max_members: Any, group_size: Any) -> int:
    try:
        max_count = int(max_members)
        current_count = int(group_size)
    except (TypeError, ValueError):
        return 0
    return max(0, max_count - max(0, current_count))


def choose_release_candidate(members: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidates = [member for member in members if bool(member.get("is_dummy") or member.get("isCompanion"))]
    if not candidates:
        return None
    return sorted(
        candidates,
        key=lambda member: (
            RELEASE_PRIORITY.get(normalize_role(member.get("role")), RELEASE_PRIORITY["fill"]),
            str(member.get("name") or ""),
        ),
    )[0]


def request_value(request: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in request and request[key] not in (None, ""):
            return request[key]
    return default


def is_mock_value(value: Any) -> bool:
    return value.__class__.__module__ == "unittest.mock"


def arg_string(args: argparse.Namespace, name: str, default: str = "") -> str:
    value = getattr(args, name, default)
    if is_mock_value(value):
        return default
    return str(value)


def arg_float(args: argparse.Namespace, name: str, default: float) -> float:
    value = getattr(args, name, default)
    if is_mock_value(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def arg_bool(args: argparse.Namespace, name: str, default: bool = False) -> bool:
    value = getattr(args, name, default)
    if is_mock_value(value):
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def request_requester_key(request: dict[str, Any]) -> str:
    account = str(request_value(request, "requesterAccount", "RequesterAccount", default="")).strip().lower()
    if account:
        return f"account:{account}"
    name = str(request_value(request, "requesterName", "RequesterName", default="")).strip().lower()
    return f"name:{name}" if name else ""


def request_matches_requester(request: dict[str, Any], key: str) -> bool:
    return bool(key) and request_requester_key(request) == key


def member_identity_keys(member: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    account = str(member.get("account") or member.get("Account") or "").strip().lower()
    name = str(member.get("name") or member.get("Name") or "").strip().lower()
    if account:
        keys.add(f"account:{account}")
    if name:
        keys.add(f"name:{name}")
    return keys


def active_companion_member_rows(active: dict[str, ActiveCompanion], requester_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for request_id, companion in active.items():
        request = companion.request
        if not request_matches_requester(request, requester_key):
            continue
        rows.append(
            {
                "request_id": request_id,
                "name": request_value(request, "assignedCompanionName", "AssignedCompanionName", default=companion.account),
                "account": companion.account,
                "role": request_value(request, "requestedRole", "RequestedRole", default="fill"),
                "isCompanion": True,
            }
        )
    return rows


def active_companion_identity_keys(active: dict[str, ActiveCompanion], requester_key: str) -> set[str]:
    keys: set[str] = set()
    for row in active_companion_member_rows(active, requester_key):
        keys.update(member_identity_keys(row))
    return keys


def real_group_member_count(
    requester_state: dict[str, Any] | None,
    requester_key: str,
    active: dict[str, ActiveCompanion],
) -> int:
    if not isinstance(requester_state, dict):
        return 0

    companion_keys = active_companion_identity_keys(active, requester_key)
    count = 0
    for member in requester_state.get("groupMembers", []) or []:
        if not isinstance(member, dict):
            continue
        member_keys = member_identity_keys(member)
        if requester_key and requester_key in member_keys:
            continue
        if member_keys & companion_keys:
            continue
        if bool(member.get("isCompanion") or member.get("is_dummy")):
            continue
        count += 1
    return count


def group_member_count(requester_state: dict[str, Any] | None) -> int:
    return len(group_member_rows(requester_state))


def group_has_vacant_slots(requester_state: dict[str, Any] | None, max_group_size: int = 8) -> bool:
    return group_member_count(requester_state) < max(1, int(max_group_size))


def pending_companion_count_for_requester(
    active: dict[str, ActiveCompanion],
    requester_key: str,
    requester_state: dict[str, Any] | None,
) -> int:
    if not requester_key:
        return 0

    group_keys: set[str] = set()
    for member in group_member_rows(requester_state):
        group_keys.update(member_identity_keys(member))

    pending = 0
    for row in active_companion_member_rows(active, requester_key):
        if member_identity_keys(row) & group_keys:
            continue
        pending += 1
    return pending


def companion_slot_block_reason(
    active: dict[str, ActiveCompanion],
    request: dict[str, Any],
    requester_state: dict[str, Any] | None,
    max_group_size: int = 8,
) -> str:
    if not has_group_member_snapshot(requester_state):
        return ""

    max_count = max(1, int(max_group_size))
    member_count = group_member_count(requester_state)
    if member_count >= max_count:
        return f"group is full ({member_count}/{max_count})"

    requester_key = request_requester_key(request)
    vacancy = party_vacancy(max_count, member_count)
    pending = pending_companion_count_for_requester(active, requester_key, requester_state)
    if pending >= vacancy:
        return "pending companion already reserves remaining group slot"
    return ""


def choose_release_request_for_real_player_join(
    active: dict[str, ActiveCompanion],
    requester_key: str,
    requester_state: dict[str, Any] | None,
    release_counts: dict[str, int],
) -> str:
    # Real players joining the group should not implicitly dismiss a companion.
    # The party leader must explicitly free a slot through a leave/kick flow.
    return ""


def choose_release_request_for_missing_group_companion(
    active: dict[str, ActiveCompanion],
    requester_key: str,
    requester_state: dict[str, Any] | None,
) -> str:
    if not isinstance(requester_state, dict):
        return ""
    if not has_group_member_snapshot(requester_state):
        return ""
    members = group_member_rows(requester_state)
    if not snapshot_contains_requester(members, requester_key):
        return ""
    if not members:
        candidate = choose_release_candidate(active_companion_member_rows(active, requester_key))
        return str(candidate.get("request_id") or "") if candidate else ""

    group_keys: set[str] = set()
    for member in members:
        group_keys.update(member_identity_keys(member))
    for row in active_companion_member_rows(active, requester_key):
        if member_identity_keys(row) & group_keys:
            continue
        return str(row.get("request_id") or "")
    return ""


def is_leave_request(request: dict[str, Any]) -> bool:
    role = str(request_value(request, "requestedRole", "RequestedRole", default="")).strip().lower()
    status = str(request_value(request, "status", "Status", default="")).strip().lower()
    return role == "leave" or status == "leaving"


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def split_words(value: Any) -> set[str]:
    return {
        part.strip().lower()
        for part in str(value or "").replace("|", ",").replace(";", ",").split(",")
        if part.strip()
    }


def normalize_capability_key(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_")
    compact = "".join(ch for ch in raw if ch.isalnum())
    return CAPABILITY_ALIASES.get(compact, raw)


def split_capabilities(value: Any) -> set[str]:
    return {normalized for part in split_words(value) if (normalized := normalize_capability_key(part))}


def request_capabilities(request: dict[str, Any]) -> set[str]:
    capabilities: set[str] = set()
    for key in (
        "requestedCapability",
        "RequestedCapability",
        "requestedCapabilities",
        "RequestedCapabilities",
        "capability",
        "Capability",
        "capabilities",
        "Capabilities",
        "capabilityTags",
        "CapabilityTags",
    ):
        capabilities.update(split_capabilities(request.get(key)))
    return capabilities


def normalize_class_key(value: Any) -> str:
    return "".join(ch for ch in str(value or "").strip().lower() if ch.isalnum())


def companion_row_class_key(row: dict[str, Any]) -> str:
    return normalize_class_key(row.get("class_name") or row.get("class") or row.get("ClassName"))


def request_mercenary_class_key(request: dict[str, Any]) -> str:
    return normalize_class_key(
        request_value(
            request,
            "mercenaryClassName",
            "MercenaryClassName",
            "requestedClassName",
            "RequestedClassName",
            default="",
        )
    )


def request_mercenary_personality(request: dict[str, Any]) -> str:
    return str(
        request_value(
            request,
            "mercenaryPersonality",
            "MercenaryPersonality",
            "requestedPersonality",
            "RequestedPersonality",
            default="",
        )
        or ""
    ).strip()


TACTIC_ALIASES = {
    "safe": "safe",
    "safety": "safe",
    "careful": "safe",
    "cautious": "safe",
    "안전": "safe",
    "안전하게": "safe",
    "aggressive": "aggressive",
    "attack": "aggressive",
    "offense": "aggressive",
    "공격": "aggressive",
    "공격적으로": "aggressive",
    "heal": "heal_priority",
    "healing": "heal_priority",
    "heal_priority": "heal_priority",
    "힐": "heal_priority",
    "힐우선": "heal_priority",
    "치유": "heal_priority",
    "치유우선": "heal_priority",
    "mez": "mez_priority",
    "mezz": "mez_priority",
    "cc": "mez_priority",
    "crowd_control": "mez_priority",
    "메즈": "mez_priority",
    "메즈우선": "mez_priority",
    "protect": "leader_protect",
    "leader": "leader_protect",
    "leader_protect": "leader_protect",
    "보호": "leader_protect",
    "리더보호": "leader_protect",
    "balanced": "balanced",
    "balance": "balanced",
    "default": "balanced",
    "기본": "balanced",
}
TACTICS = {"balanced", "safe", "aggressive", "heal_priority", "mez_priority", "leader_protect"}


def normalize_tactic_preset(value: Any) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    compact = "".join(ch for ch in raw if ch.isalnum() or "\uac00" <= ch <= "\ud7a3")
    normalized = TACTIC_ALIASES.get(raw) or TACTIC_ALIASES.get(compact) or raw
    return normalized if normalized in TACTICS else "balanced"


def request_mercenary_tactic(request: dict[str, Any]) -> str:
    return normalize_tactic_preset(
        request_value(
            request,
            "mercenaryTacticPreset",
            "MercenaryTacticPreset",
            "mercenaryTactic",
            "MercenaryTactic",
            "tacticPreset",
            "TacticPreset",
            default="balanced",
        )
    )


def request_mercenary_traits(request: dict[str, Any]) -> list[str]:
    value = request_value(request, "mercenaryTraits", "MercenaryTraits", "traits", "Traits", default="")
    return [part.strip() for part in str(value or "").replace(";", "|").replace(",", "|").split("|") if part.strip()]


def request_mercenary_int(request: dict[str, Any], *keys: str, default: int = 0) -> int:
    return max(0, min(100, parse_int(request_value(request, *keys, default=default), default=default)))


def request_mercenary_counter(request: dict[str, Any], *keys: str, default: int = 0) -> int:
    return max(0, parse_int(request_value(request, *keys, default=default), default=default))


def request_mercenary_trust(request: dict[str, Any]) -> int:
    return request_mercenary_int(request, "mercenaryTrust", "MercenaryTrust", "trust", "Trust", default=50)


def request_mercenary_fatigue(request: dict[str, Any]) -> int:
    return request_mercenary_int(request, "mercenaryFatigue", "MercenaryFatigue", "fatigue", "Fatigue", default=0)


def request_mercenary_memory(request: dict[str, Any]) -> str:
    return str(
        request_value(
            request,
            "mercenaryAdventureMemory",
            "MercenaryAdventureMemory",
            "adventureMemory",
            "AdventureMemory",
            "mercenaryBackground",
            "MercenaryBackground",
            default="",
        )
        or ""
    ).strip()


def request_mercenary_record(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_contracts": request_mercenary_counter(request, "mercenaryTotalContracts", "MercenaryTotalContracts", default=0),
        "total_contract_minutes": request_mercenary_counter(
            request,
            "mercenaryTotalContractMinutes",
            "MercenaryTotalContractMinutes",
            default=0,
        ),
        "kills_together": request_mercenary_counter(request, "mercenaryKillsTogether", "MercenaryKillsTogether", default=0),
        "deaths_together": request_mercenary_counter(request, "mercenaryDeathsTogether", "MercenaryDeathsTogether", default=0),
        "rescues": request_mercenary_counter(request, "mercenaryRescues", "MercenaryRescues", default=0),
        "quests_completed": request_mercenary_counter(
            request,
            "mercenaryQuestsCompleted",
            "MercenaryQuestsCompleted",
            default=0,
        ),
        "earned_titles": str(request_value(request, "mercenaryEarnedTitles", "MercenaryEarnedTitles", default="") or ""),
        "personal_quest_state": str(
            request_value(request, "mercenaryPersonalQuestState", "MercenaryPersonalQuestState", default="") or ""
        ),
        "relationship_event_state": str(
            request_value(request, "mercenaryRelationshipEventState", "MercenaryRelationshipEventState", default="") or ""
        ),
    }


def mercenary_operational_state(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "tactic": request_mercenary_tactic(request),
        "trust": request_mercenary_trust(request),
        "fatigue": request_mercenary_fatigue(request),
        "traits": request_mercenary_traits(request),
        "memory": request_mercenary_memory(request),
        "record": request_mercenary_record(request),
    }


def live_companion_tactic_flags(tactic: str, role: Any, action_rotation: str) -> list[str]:
    tactic = normalize_tactic_preset(tactic)
    if tactic == "safe":
        return [
            "--party-assist-attack-delay",
            "0.9",
            "--flee-health-percent",
            "52",
            "--flee-pressure-health-percent",
            "88",
            "--party-preengage-ranged-safe-distance",
            "2200",
        ]
    if tactic == "aggressive":
        return [
            "--party-assist-attack-delay",
            "0.05",
            "--flee-health-percent",
            "30",
            "--combat-interval",
            "0.45",
            "--skill-interval",
            "0.72",
        ]
    if tactic == "heal_priority":
        return [
            "--party-heal-leader-health-percent",
            "95",
            "--healer-self-health-percent",
            "94",
            "--party-heal-leader-interval",
            "0.8",
        ]
    if tactic == "mez_priority":
        return [
            "--party-rescue-assist-after",
            "4",
            "--party-rescue-emergency-assist-after",
            "3",
            "--party-support-evasion",
        ]
    if tactic == "leader_protect":
        return [
            "--party-survival-active-tank-health-percent",
            "50",
            "--party-rescue-max-distance",
            "7000",
            "--party-assist-attack-delay",
            "0.25",
        ]
    return []


def live_companion_trait_flags(traits: list[str]) -> list[str]:
    normalized = " ".join(traits).lower()
    flags: list[str] = []
    if any(token in normalized for token in ("응급", "치료", "heal", "medic")):
        flags += [
            "--party-heal-leader-health-percent",
            "95",
            "--self-preserve-heal-min-interval",
            "6.0",
        ]
    if any(token in normalized for token in ("도망", "탈출", "후퇴", "escape", "flee")):
        flags += [
            "--flee-movement-speed",
            "360",
            "--flee-safe-point-distance",
            "2400",
        ]
    if any(token in normalized for token in ("추적", "정찰", "몹", "track", "scout")):
        flags += [
            "--combat-usable-api-retries",
            "6",
            "--target-loss-grace",
            "12",
        ]
    if any(token in normalized for token in ("겁 없음", "겁없", "용맹", "brave", "fearless")):
        flags += [
            "--flee-health-percent",
            "25",
            "--required-target-tank-commit-health-percent",
            "55",
        ]
    if any(token in normalized for token in ("야영", "휴식", "camp", "rest")):
        flags += [
            "--low-health-rest-min",
            "8",
        ]
    return flags


def live_companion_trust_fatigue_flags(trust: int, fatigue: int) -> list[str]:
    flags: list[str] = []
    if trust >= 80 and fatigue < 60:
        flags += [
            "--combat-interval",
            "0.5",
            "--skill-interval",
            "0.78",
            "--startup-self-buff-count",
            "3",
        ]
    elif trust < 35:
        flags += [
            "--party-assist-attack-delay",
            "1.4",
            "--flee-health-percent",
            "58",
        ]

    if fatigue >= 70:
        flags += [
            "--combat-interval",
            "0.9",
            "--skill-interval",
            "1.25",
            "--flee-health-percent",
            "62",
        ]
    elif fatigue <= 20 and trust >= 60:
        flags += [
            "--combat-interval",
            "0.5",
        ]
    return flags


def mercenary_trust_stage(trust: int) -> str:
    trust = max(0, min(100, int(trust)))
    if trust >= 90:
        return "충성"
    if trust >= 75:
        return "두터운 신뢰"
    if trust >= 55:
        return "익숙함"
    if trust >= 35:
        return "조심스러움"
    return "낯섦"


def mercenary_trust_dialogue_note(trust: int) -> str:
    stage = mercenary_trust_stage(trust)
    notes = {
        "충성": "친밀도 말투: 충성, 먼저 안심시키고 믿고 맡기라는 어조",
        "두터운 신뢰": "친밀도 말투: 두터운 신뢰, 편하게 보고하고 책임감 있게 답함",
        "익숙함": "친밀도 말투: 익숙함, 자연스럽고 실무적으로 답함",
        "조심스러움": "친밀도 말투: 조심스러움, 예의 있지만 거리를 둠",
        "낯섦": "친밀도 말투: 낯섦, 사무적이고 과한 친근함을 피함",
    }
    return notes[stage]


def mercenary_primary_title_label(value: Any) -> str:
    titles = [part.strip() for part in str(value or "").replace(";", "|").replace(",", "|").split("|") if part.strip()]
    return titles[0] if titles else ""


def mercenary_personal_quest_label(value: Any) -> str:
    state = str(value or "").strip().lower()
    labels = {
        "available:first_bond": "신뢰의 첫 증표 진행 중",
        "completed:first_bond": "신뢰의 첫 증표 완료",
        "available:field_oath": "전장의 맹세 진행 중",
        "completed:field_oath": "전장의 맹세 완료",
    }
    return labels.get(state, "")


def mercenary_relationship_event_labels(value: Any) -> list[str]:
    labels = {
        "bond_acknowledged": "처음으로 리더를 믿겠다고 인정한 관계 이벤트가 있음",
        "field_oath": "전장에서 끝까지 함께하겠다고 맹세한 관계 이벤트가 있음",
    }
    tokens = [part.strip().lower() for part in str(value or "").replace(";", "|").replace(",", "|").split("|") if part.strip()]
    return [labels[token] for token in tokens if token in labels]


def live_companion_mercenary_state_flags(request: dict[str, Any], role: Any, action_rotation: str) -> list[str]:
    state = mercenary_operational_state(request)
    flags: list[str] = []
    flags += live_companion_tactic_flags(str(state["tactic"]), role, action_rotation)
    flags += live_companion_trait_flags(list(state["traits"]))
    flags += live_companion_trust_fatigue_flags(int(state["trust"]), int(state["fatigue"]))
    return flags


def first_account_row(account_csv: str | Path) -> dict[str, Any]:
    try:
        with Path(account_csv).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                return row
    except OSError:
        return {}
    return {}


def companion_row_roles(row: dict[str, Any]) -> set[str]:
    explicit = split_words(row.get("role") or row.get("roles"))
    if explicit:
        return {normalize_role(role) for role in explicit}

    return set(CLASS_ROLE_HINTS.get(companion_row_class_key(row), set()))


def companion_row_capabilities(row: dict[str, Any]) -> set[str]:
    explicit = split_capabilities(row.get("capabilities") or row.get("capability_tags"))
    class_capabilities = set(CLASS_CAPABILITY_HINTS.get(companion_row_class_key(row), set()))
    return explicit | class_capabilities


def default_role_capability_score(
    requested_role: str,
    row: dict[str, Any],
    request: dict[str, Any] | None = None,
) -> int:
    role = normalize_role(requested_role)
    weights = {
        "tank": DEFAULT_TANK_CAPABILITY_WEIGHTS,
        "dps": DEFAULT_DPS_CAPABILITY_WEIGHTS,
    }.get(role)
    if not weights:
        return 0

    capabilities = companion_row_capabilities(row)
    row_roles = companion_row_roles(row)
    score = sum(weight for capability, weight in weights.items() if capability in capabilities)
    if role == "dps" and request is not None and request_is_boss_or_objective_content(request):
        score += sum(
            weight
            for capability, weight in BOSS_DPS_CAPABILITY_WEIGHTS.items()
            if capability in capabilities
        )
    if (
        role == "tank"
        and request is not None
        and request_is_boss_or_objective_content(request)
        and "defensive_tank" in capabilities
        and row_roles & {"support", "healer"}
    ):
        score -= 40
    return score


def role_to_rotation_for_row(
    role: Any,
    row: dict[str, Any] | None = None,
    request: dict[str, Any] | None = None,
) -> str:
    normalized_role = normalize_role(role)
    class_key = companion_row_class_key(row or {})
    class_rotation = CLASS_ROTATION_HINTS.get(class_key, "")
    class_roles = CLASS_ROLE_HINTS.get(class_key, set())

    if normalized_role == "fill" and class_rotation:
        return class_rotation
    if normalized_role == "support" and class_rotation and "healer" not in class_roles:
        return class_rotation
    if normalized_role == "dps" and class_rotation in {"caster-basic", "hybrid"}:
        return class_rotation

    return role_to_rotation(normalized_role)


def row_matches_request_realm(row: dict[str, Any], request: dict[str, Any]) -> bool:
    request_realm = parse_int(request_value(request, "realm", "Realm", default=0))
    row_realm = parse_int(row.get("realm") or row.get("Realm"), default=0)
    return request_realm <= 0 or row_realm <= 0 or row_realm == request_realm


def row_matches_requested_role(row: dict[str, Any], requested_role: str) -> bool:
    role = normalize_role(requested_role)
    if role == "fill":
        return True

    row_roles = companion_row_roles(row)
    return not row_roles or role in row_roles


def row_home_position(row: dict[str, Any]) -> tuple[int, int, int] | None:
    x = row.get("home_x", row.get("x"))
    y = row.get("home_y", row.get("y"))
    z = row.get("home_z", row.get("z"))
    if x in (None, "") or y in (None, ""):
        return None
    return (parse_int(x), parse_int(y), parse_int(z))


def request_position(request: dict[str, Any]) -> tuple[int, int, int] | None:
    x = parse_int(request_value(request, "x", "X", default=0))
    y = parse_int(request_value(request, "y", "Y", default=0))
    z = parse_int(request_value(request, "z", "Z", default=0))
    if x == 0 and y == 0 and z == 0:
        return None
    return (x, y, z)


def request_region(request: dict[str, Any]) -> int:
    return parse_int(request_value(request, "region", "Region", default=0))


def ground_z_map_for_companion(request: dict[str, Any], companion_row: dict[str, Any]) -> str:
    realm = parse_int(request_value(request, "realm", "Realm", default=0))
    if realm <= 0:
        realm = parse_int(companion_row.get("realm") or companion_row.get("Realm"), default=1)
    return REALM_GROUND_Z_MAP.get(realm, REALM_GROUND_Z_MAP[1])


def request_objective_target_name(request: dict[str, Any]) -> str:
    explicit = str(
        request_value(
            request,
            "targetName",
            "TargetName",
            "objectiveName",
            "ObjectiveName",
            "objectiveTarget",
            "ObjectiveTarget",
            default="",
        )
        or ""
    ).strip()
    if explicit:
        return explicit

    content_type = str(request_value(request, "contentType", "ContentType", default="") or "").strip()
    if ":" not in content_type:
        return ""
    prefix, suffix = content_type.split(":", 1)
    if prefix.strip().lower() not in {"pve", "boss", "objective"}:
        return ""
    return suffix.strip()


def request_is_boss_or_objective_content(request: dict[str, Any]) -> bool:
    content_type = str(request_value(request, "contentType", "ContentType", default="") or "").strip()
    if request_objective_target_name(request):
        return True
    if not content_type:
        return False
    prefix = content_type.split(":", 1)[0].strip().lower()
    return prefix in {"boss", "objective"}


def live_companion_party_encounter_mode(request: dict[str, Any]) -> str:
    return "boss" if request_is_boss_or_objective_content(request) else "standard"


def should_enable_startup_stealth(
    request: dict[str, Any],
    role: Any,
    row: dict[str, Any] | None,
    *,
    action_rotation: str,
    hostile_assist: bool,
) -> bool:
    capabilities = companion_row_capabilities(row or {})
    if "stealth" not in capabilities:
        return False

    if "stealth" in request_capabilities(request):
        return True

    if (
        normalize_role(role) in {"support", "healer"}
        and request_is_boss_or_objective_content(request)
    ):
        return False

    return True


def first_account_home_waypoint(account_csv: str | Path) -> str:
    try:
        with Path(account_csv).open(encoding="utf-8-sig", newline="") as handle:
            row = next(csv.DictReader(handle), None)
    except (OSError, StopIteration):
        return ""
    if not row:
        return ""

    x = parse_int(row.get("home_x") or row.get("HomeX"))
    y = parse_int(row.get("home_y") or row.get("HomeY"))
    z = parse_int(row.get("home_z") or row.get("HomeZ"))
    if x <= 0 or y <= 0:
        return ""
    return f"{x},{y},{z}"


def requester_player_level(request: dict[str, Any], requester_state: dict[str, Any] | None = None) -> int:
    player = requester_state.get("player") if isinstance(requester_state, dict) else None
    if isinstance(player, dict):
        level = parse_int(player.get("level") or player.get("Level"))
        if level > 0:
            return level

    return parse_int(
        request_value(
            request,
            "playerLevel",
            "PlayerLevel",
            "requesterLevel",
            "RequesterLevel",
            "level",
            "Level",
            default=0,
        )
    )


def distance_squared(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def rank_companion_rows(request: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    realm_rows = [row for row in rows if row_matches_request_realm(row, request)]
    if realm_rows:
        rows = realm_rows

    requested_class = request_mercenary_class_key(request)
    if requested_class:
        class_rows = [row for row in rows if companion_row_class_key(row) == requested_class]
        if class_rows:
            rows = class_rows

    requested_role = normalize_role(request_value(request, "requestedRole", "RequestedRole", default="fill"))
    role_rows = [row for row in rows if row_matches_requested_role(row, requested_role)]
    if role_rows:
        rows = role_rows

    desired_capabilities = request_capabilities(request)
    if desired_capabilities:
        capability_rows = [
            row
            for row in rows
            if desired_capabilities.issubset(companion_row_capabilities(row))
        ]
        if capability_rows:
            rows = capability_rows

    if requested_role in {"tank", "dps"} and not desired_capabilities:
        indexed_rows = list(enumerate(rows))
        rows = [
            row
            for _, row in sorted(
                indexed_rows,
                key=lambda item: (-default_role_capability_score(requested_role, item[1], request), item[0]),
            )
        ]

    target_position = request_position(request)
    if target_position is None:
        return rows

    indexed_rows = list(enumerate(rows))

    def sort_key(item: tuple[int, dict[str, Any]]) -> tuple[int, int, int]:
        index, row = item
        home = row_home_position(row)
        if home is None:
            return (1, 0, index)
        return (0, distance_squared(target_position, home), index)

    return [row for _, row in sorted(indexed_rows, key=sort_key)]


def select_companion_accounts_csv(
    request: dict[str, Any],
    account_csv: str | Path,
    run_dir: str | Path,
    excluded_accounts: set[str] | None = None,
) -> Path:
    source_path = Path(account_csv)
    requester_account = str(request_value(request, "requesterAccount", "RequesterAccount", default="")).strip().lower()
    requester_name = str(request_value(request, "requesterName", "RequesterName", default="")).strip().lower()
    excluded = {account.strip().lower() for account in (excluded_accounts or set()) if account.strip()}

    with source_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows = [row for row in reader]

    if not fieldnames:
        raise ValueError(f"account csv has no header: {source_path}")

    request_start = request_position(request)
    if request_start is not None:
        for field in ("start_x", "start_y", "start_z", "zone_id"):
            if field not in fieldnames:
                fieldnames.append(field)

    candidates = []
    for row in rows:
        username = str(row.get("username") or "").strip().lower()
        character = str(row.get("character") or row.get("name") or "").strip().lower()
        if requester_account and username == requester_account:
            continue
        if username in excluded:
            continue
        if requester_name and character == requester_name:
            continue
        candidates.append(row)

    candidates = rank_companion_rows(request, candidates)
    if request_start is not None:
        region = request_region(request)
        for row in candidates:
            row["start_x"] = str(request_start[0])
            row["start_y"] = str(request_start[1])
            row["start_z"] = str(request_start[2])
            if region > 0:
                row["zone_id"] = str(region)

    if not candidates:
        raise ValueError(f"no companion accounts left after excluding requester from {source_path}")

    target_path = Path(run_dir) / "companion-accounts.csv"
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with target_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(candidates)
    return target_path


def first_account_username(account_csv: str | Path) -> str:
    with Path(account_csv).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            return str(row.get("username") or "").strip()
    return ""


def account_usernames_from_csv(account_csv: str | Path) -> list[str]:
    usernames: list[str] = []
    try:
        with Path(account_csv).open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                username = str(row.get("username") or "").strip()
                if username:
                    usernames.append(username)
    except OSError:
        return []
    return usernames


def build_behavior_command(
    args: argparse.Namespace,
    request: dict[str, Any],
    account_csv: str | Path,
    run_dir: str | Path,
    requester_state: dict[str, Any] | None = None,
) -> list[str]:
    run_path = Path(run_dir)
    run_path.mkdir(parents=True, exist_ok=True)

    request_id = str(request_value(request, "id", "Id", default="live-companion"))
    leader_name = str(request_value(request, "requesterName", "RequesterName", default="")).strip()
    role = normalize_role(request_value(request, "requestedRole", "RequestedRole", default="fill"))
    hold = str(request_contract_duration_seconds(request) or getattr(args, "hold", 3600))
    combat_home = str(getattr(args, "combat_home_leash_distance", 4500))
    leader_waypoint = request_waypoint(request)
    objective_target_name = request_objective_target_name(request)
    companion_home_waypoint = first_account_home_waypoint(account_csv)
    companion_row = first_account_row(account_csv)
    action_rotation = role_to_rotation_for_row(role, companion_row, request)
    forced_personality_raw = getattr(args, "force_companion_personality", "")
    forced_personality = forced_personality_raw.strip() if isinstance(forced_personality_raw, str) else ""
    requested_personality = request_mercenary_personality(request)
    personality = forced_personality or requested_personality or companion_personality_for_role(role)
    mercenary_state = mercenary_operational_state(request)
    mercenary_record = dict(mercenary_state.get("record") or {})
    hostile_assist = live_companion_uses_hostile_assist(role, action_rotation, request)
    player_level = requester_player_level(request, requester_state)
    encounter_mode = live_companion_party_encounter_mode(request)

    command = [
        sys.executable,
        "tools/behavior-dummy-client.py",
        "--host",
        str(getattr(args, "host", "127.0.0.1")),
        "--port",
        str(getattr(args, "port", 10300)),
        "--api-port",
        str(getattr(args, "api_port", 5000)),
        "--accounts",
        str(account_csv),
        "--concurrency",
        "1",
        "--rounds",
        "1",
        "--hold",
        hold,
        "--party-size",
        str(args.party_size),
        "--party-external-member-names",
        leader_name,
        "--party-auto-external-members",
        "--party-assist-only",
        "--party-local-rescue-target",
        "--party-encounter-mode",
        encounter_mode,
        "--party-assist-interval",
        live_companion_party_assist_interval(role, action_rotation, request),
        "--party-assist-attack-delay",
        live_companion_party_assist_attack_delay(role, action_rotation, request),
        "--party-ranged-assist-extra-delay",
        live_companion_ranged_assist_extra_delay(role, action_rotation),
        "--party-follow-interval",
        "0.25",
        "--party-follow-step",
        "360",
        "--party-follow-distance",
        live_companion_follow_distance(role, action_rotation),
        "--party-follow-catchup-distance",
        "800",
        "--party-follow-catchup-speed-multiplier",
        "1.6",
        "--party-follow-hard-catchup-distance",
        "1600",
        "--party-follow-hard-catchup-speed-multiplier",
        "2.3",
        "--party-follow-teleport-distance",
        "2500",
        "--party-follow-teleport-stop-distance",
        "90",
        "--follow-nearby-player",
        "--follow-player-name",
        leader_name,
        "--follow-player-max-distance",
        "12000",
        "--combat",
        "--hunter",
        "--move",
        "--smooth-movement",
        "--server-correction-smoothing",
        "--smooth-move-interval",
        "0.18",
        "--movement-speed",
        "191",
        "--movement-update-interval",
        "0.18",
        "--ground-z-map",
        ground_z_map_for_companion(request, companion_row),
        "--move-step",
        "320",
        "--use-skills",
        "--combat-usable-api",
        "--combat-usable-api-retries",
        "4",
        "--combat-usable-api-retry-delay",
        "0.4",
        "--startup-summon-pet",
        "--startup-self-buff-count",
        "2",
        "--startup-self-buff-delay",
        "0.8",
        "--action-rotation",
        action_rotation,
        *(
            [
                "--player-level",
                str(player_level),
                "--ideal-target-level",
                str(player_level),
                "--min-target-level",
                str(max(1, player_level - 8)),
            ]
            if player_level > 0
            else []
        ),
        *(
            [
                "--startup-train-full-specs",
                "--startup-train-level",
                str(player_level),
            ]
            if player_level > 0 and str(companion_row.get("specs", "") or "").strip()
            else []
        ),
        "--auto-release-on-death",
        "--companion-chat-reply",
        "--companion-chat-reply-channel",
        "party",
        "--companion-chat-reply-cooldown",
        "2",
        "--companion-personality",
        personality,
        "--mercenary-trust",
        str(int(mercenary_state["trust"])),
        "--mercenary-fatigue",
        str(int(mercenary_state["fatigue"])),
        "--mercenary-tactic-preset",
        str(mercenary_state["tactic"]),
        "--mercenary-total-contracts",
        str(int(mercenary_record.get("total_contracts", 0) or 0)),
        "--mercenary-total-contract-minutes",
        str(int(mercenary_record.get("total_contract_minutes", 0) or 0)),
        "--mercenary-kills-together",
        str(int(mercenary_record.get("kills_together", 0) or 0)),
        "--mercenary-deaths-together",
        str(int(mercenary_record.get("deaths_together", 0) or 0)),
        "--mercenary-rescues",
        str(int(mercenary_record.get("rescues", 0) or 0)),
        "--mercenary-quests-completed",
        str(int(mercenary_record.get("quests_completed", 0) or 0)),
        "--no-auto-loot",
        "--combat-home-leash-distance",
        combat_home,
        "--attack-range",
        "350",
        "--combat-interval",
        "0.6",
        "--skill-interval",
        "1.0",
        "--combat-direct-move-distance",
        "2200",
        "--melee-stick-attack",
        "--melee-stick-attack-distance",
        "1800",
        "--target-face-command-interval",
        "0.8",
        "--melee-range-buffer",
        "300",
        "--minimum-melee-stop-distance",
        "60",
        "--target-loss-grace",
        "8",
        "--target-timeout",
        "65",
        "--live-control-file",
        str(run_path / "live-control.json"),
        "--live-control-interval",
        "0.5",
        *LIVE_COMPANION_PARTY_COORDINATION_FLAGS,
        *(
            live_companion_boss_role_flags(role, action_rotation, args)
            if encounter_mode == "boss"
            else live_companion_field_role_flags(role, action_rotation)
        ),
        *LIVE_COMPANION_FLEE_FLAGS,
        *live_companion_service_flee_flags(args),
        *companion_personality_behavior_flags(personality, role, action_rotation),
        "--metrics-csv",
        str(run_path / f"{request_id}-metrics.csv"),
        "--report-md",
        str(run_path / f"{request_id}-report.md"),
        "--encounter-log",
        str(run_path / f"{request_id}-{{username}}-{{round}}-encounters.jsonl"),
        "--trace-movement-log",
        str(run_path / f"{request_id}-{{username}}-{{round}}-movement.jsonl"),
    ]
    if live_companion_requires_follow_anchor_before_objective(role, action_rotation):
        command.append("--follow-player-required-for-objective-move")
    if live_companion_follow_hold_allows_waypoint(role, action_rotation):
        command.append("--follow-player-hold-allows-waypoint")
    if hostile_assist:
        command.append("--party-use-assist-command")
    for option, key in (
        ("--mercenary-earned-titles", "earned_titles"),
        ("--mercenary-personal-quest-state", "personal_quest_state"),
        ("--mercenary-relationship-event-state", "relationship_event_state"),
    ):
        value = str(mercenary_record.get(key, "") or "").strip()
        if value:
            command += [option, value]
    memory = str(mercenary_state.get("memory", "") or "").strip()
    if memory:
        command += ["--mercenary-adventure-memory", memory]
    command.extend(live_companion_role_flags(role, action_rotation, args))
    command.extend(live_companion_contract_tier_flags(request))
    command.extend(live_companion_mercenary_state_flags(request, role, action_rotation))
    if objective_target_name and hostile_assist and (
        live_companion_claims_objective_target(role, action_rotation) or action_rotation.startswith("caster")
    ):
        command += [
            "--require-target-name",
            objective_target_name,
            "--prefer-target-name",
            objective_target_name,
            "--allow-avoid-target-fallback",
        ]
        region = request_region(request)
        if region > 0:
            command += ["--path-region", str(region)]
    if should_enable_startup_stealth(
        request,
        role,
        companion_row,
        action_rotation=action_rotation,
        hostile_assist=hostile_assist,
    ):
        command.append("--startup-stealth")
    if "speed_song" in companion_row_capabilities(companion_row):
        command.append("--startup-speed-song")
    if dialogue_enabled_from_server_or_cli(args) or arg_bool(args, "guide_enabled", False):
        command += [
            "--companion-free-chat",
            "--ai-gateway-model-alias",
            arg_string(args, "ai_gateway_model_alias", "small-dialogue") or "small-dialogue",
            "--companion-guide-rag",
            "--companion-guide-model-alias",
            arg_string(args, "ai_guide_model_alias", "openai-small-guide") or "openai-small-guide",
            "--companion-guide-timeout",
            str(max(1.0, arg_float(args, "ai_gateway_timeout", 8.0))),
        ]
        gateway_config = arg_string(args, "ai_gateway_config", "")
        if gateway_config:
            command += ["--ai-gateway-config", gateway_config, "--companion-guide-ai-gateway-config", gateway_config]
    if leader_waypoint and objective_target_name:
        command += [
            "--waypoints",
            leader_waypoint,
            "--waypoint-interval",
            "0.6",
            "--waypoint-step",
            "520",
            "--waypoint-stop-distance",
            live_companion_waypoint_stop_distance(role, action_rotation),
            "--required-target-home",
            leader_waypoint,
            "--required-target-home-stop-distance",
            live_companion_required_home_stop_distance(role, action_rotation),
            "--required-target-home-hunt-distance",
            live_companion_required_home_hunt_distance(role, action_rotation),
            "--target-home-max-distance",
            str(max(arg_float(args, "combat_home_leash_distance", 4500.0), 4500.0)),
        ]
    if companion_home_waypoint:
        command += [
            "--flee-home",
            companion_home_waypoint,
        ]

    return [part for part in command if part != ""]


def request_waypoint(request: dict[str, Any]) -> str:
    try:
        x = int(request_value(request, "x", "X", default=0))
        y = int(request_value(request, "y", "Y", default=0))
        z = int(request_value(request, "z", "Z", default=0))
    except (TypeError, ValueError):
        return ""
    if x == 0 and y == 0 and z == 0:
        return ""
    return f"{x},{y},{z}"


def encode_query(query: dict[str, Any]) -> str:
    clean = {key: value for key, value in query.items() if value not in (None, "")}
    return urllib.parse.urlencode(clean)


def api_request(args: argparse.Namespace, method: str, path: str, query: dict[str, Any] | None = None) -> Any:
    base = str(args.api_url).rstrip("/")
    suffix = path if path.startswith("/") else f"/{path}"
    request_query = dict(query or {})
    api_password = arg_string(args, "api_password", "")
    if api_password and "password" not in request_query:
        request_query["password"] = api_password
    query_string = encode_query(request_query)
    url = f"{base}{suffix}" + (f"?{query_string}" if query_string else "")
    request = urllib.request.Request(url, method=method)
    try:
        with urllib.request.urlopen(request, timeout=args.api_timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
        print(f"[OpenDAoC] Companion API unavailable: {exc}", file=sys.stderr)
        return None
    if not payload:
        return None
    return json.loads(payload)


def wait_for_server_api_ready(args: argparse.Namespace) -> bool:
    timeout = max(0.0, float(getattr(args, "api_startup_wait", 0.0) or 0.0))
    if timeout <= 0.0:
        return True
    interval = max(0.05, float(getattr(args, "api_startup_retry_interval", 0.5) or 0.5))
    deadline = time.monotonic() + timeout

    while True:
        if api_request(args, "GET", "/api/dummy/companions/config") is not None:
            return True
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            print(
                f"[OpenDAoC] Companion API was not ready after {timeout:.1f}s; service startup aborted.",
                file=sys.stderr,
            )
            return False
        time.sleep(min(interval, remaining))


def claim_next_request(args: argparse.Namespace) -> dict[str, Any] | None:
    return api_request(args, "POST", "/api/dummy/companions/requests/claim")


def snapshot_requests(args: argparse.Namespace, status: str = "", limit: int = 100) -> list[dict[str, Any]]:
    params: dict[str, str] = {"limit": str(max(1, int(limit or 1)))}
    if status:
        params["status"] = status
    payload = api_request(args, "GET", "/api/dummy/companions/requests", params)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def live_behavior_process_lines() -> list[str]:
    try:
        completed = subprocess.run(
            ["pgrep", "-af", "[t]ools/behavior-dummy-client.py"],
            text=True,
            capture_output=True,
            timeout=2.0,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if completed.returncode not in (0, 1):
        return []
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def recover_orphaned_active_requests(args: argparse.Namespace) -> int:
    if not arg_bool(args, "recover_orphaned_active_requests", True):
        return 0
    try:
        requests = snapshot_requests(args, "active", 100)
    except Exception:
        return 0
    if not requests:
        return 0

    process_lines = live_behavior_process_lines()
    recovered = 0
    for request in requests:
        request_id = str(request_value(request, "id", "Id", default="")).strip()
        if not request_id:
            continue
        if any(request_id in line for line in process_lines):
            continue
        update_request_status(
            args,
            request_id,
            "queued",
            "companion service recovered orphaned active request",
            str(request_value(request, "assignedCompanionName", "AssignedCompanionName", default="")),
        )
        recovered += 1
    return recovered


def update_request_status(
    args: argparse.Namespace,
    request_id: str,
    status: str,
    message: str = "",
    companion: str = "",
    close_reason: str = "",
) -> None:
    params = {"status": status, "message": message, "companion": companion}
    if close_reason:
        params["closeReason"] = close_reason
    api_request(
        args,
        "POST",
        f"/api/dummy/companions/requests/{urllib.parse.quote(request_id)}/status",
        params,
    )


def service_stop_file(args: argparse.Namespace) -> Path:
    configured = arg_string(args, "stop_file", "")
    if configured:
        return Path(configured)
    return Path(arg_string(args, "run_dir", "test-output/live-companions")) / "companion-service.stop"


def service_stop_requested(args: argparse.Namespace) -> bool:
    return service_stop_file(args).exists()


def metric_int(row: dict[str, Any], key: str) -> int:
    try:
        return int(float(row.get(key) or 0))
    except (TypeError, ValueError):
        return 0


def live_companion_completion_metrics(run_dir: str | Path) -> dict[str, int]:
    counts = {
        "target_removed": 0,
        "player_deaths": 0,
        "damage_done": 0,
        "healing_done": 0,
        "resurrect": 0,
        "cure": 0,
        "crowd_control": 0,
        "party_protection": 0,
    }
    run_path = Path(run_dir)
    if not run_path.exists():
        return counts

    for path in run_path.rglob("*metrics.csv"):
        try:
            with path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    counts["target_removed"] += metric_int(row, "target_removed")
                    counts["player_deaths"] += metric_int(row, "player_deaths")
                    counts["damage_done"] += metric_int(row, "damage_done")
                    counts["healing_done"] += metric_int(row, "healing_done")
                    for key, value in row.items():
                        if not str(key or "").startswith("action_"):
                            continue
                        amount = metric_int({key: value}, key)
                        if amount <= 0:
                            continue
                        if key.startswith("action_validated_party_resurrect_") or key.startswith("action_validated_revive_"):
                            counts["resurrect"] += amount
                        elif "validated_party_cure_" in key:
                            counts["cure"] += amount
                        elif "validated_crowd_control_spell" in key:
                            counts["crowd_control"] += amount
                        elif key.startswith("action_validated_party_") and key.endswith("_member") and any(
                            token in key for token in ("guard", "protect", "intercept", "bodyguard", "protection")
                        ):
                            counts["party_protection"] += amount
        except OSError:
            continue
    return counts


def live_companion_success_close_reason(request: dict[str, Any], run_dir: str | Path) -> str:
    metrics = live_companion_completion_metrics(run_dir)
    if metrics["resurrect"] > 0:
        return "resurrection_save"
    if metrics["target_removed"] > 0 and request_objective_target_name(request):
        return "boss_defeated" if live_companion_party_encounter_mode(request) == "boss" else "objective_completed"
    if metrics["party_protection"] > 0 or (
        metrics["healing_done"] > 0 and metrics["player_deaths"] <= 0
    ):
        return "protected_leader"
    if (
        metrics["damage_done"] > 0
        or metrics["healing_done"] > 0
        or metrics["cure"] > 0
        or metrics["crowd_control"] > 0
    ):
        return "honorable_release"
    return "normal_behavior_client_exit"


def health_band_from_percent(value: Any) -> str:
    try:
        percent = float(value)
    except (TypeError, ValueError):
        return "unknown"
    if percent <= 0:
        return "dead"
    if percent < 30:
        return "critical"
    if percent < 55:
        return "low"
    if percent < 85:
        return "normal"
    return "high"


def player_row(state: dict[str, Any] | None) -> dict[str, Any]:
    player = state.get("player") if isinstance(state, dict) else None
    return player if isinstance(player, dict) else {}


def numeric_percent(row: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = row.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def group_member_rows(state: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(state, dict):
        return []
    raw_members = state.get("groupMembers") or state.get("group_members") or state.get("partyMembers") or []
    return [member for member in raw_members if isinstance(member, dict)]


def has_group_member_snapshot(state: dict[str, Any] | None) -> bool:
    return isinstance(state, dict) and any(key in state for key in ("groupMembers", "group_members", "partyMembers"))


def snapshot_contains_requester(members: list[dict[str, Any]], requester_key: str) -> bool:
    if not members or not requester_key:
        return True
    return any(requester_key in member_identity_keys(member) for member in members)


def party_dead_count(state: dict[str, Any] | None) -> int:
    return sum(1 for member in group_member_rows(state) if bool(member.get("isDead")) or bool(member.get("dead")))


def member_is_crowd_controlled(member: dict[str, Any]) -> bool:
    return any(
        bool(member.get(key))
        for key in ("isCrowdControlled", "isMezzed", "isStunned", "isDiseased", "isPoisoned", "isSilenced", "isNearsighted")
    )


def party_crowd_controlled_count(state: dict[str, Any] | None) -> int:
    return sum(1 for member in group_member_rows(state) if member_is_crowd_controlled(member))


def party_lowest_health_percent(state: dict[str, Any] | None) -> float | None:
    values = [
        percent
        for member in group_member_rows(state)
        if (percent := numeric_percent(member, "healthPercent", "health_percent")) is not None
    ]
    return min(values) if values else None


def estimate_add_count(state: dict[str, Any] | None) -> int:
    if not isinstance(state, dict):
        return 0
    for key in ("adds", "addCount", "add_count", "nearbyAddCount", "nearby_add_count"):
        try:
            return max(0, int(float(state.get(key))))
        except (TypeError, ValueError):
            continue

    target_ids: set[int] = set()
    for member in group_member_rows(state):
        try:
            target_id = int(member.get("targetObjectId") or member.get("target_object_id") or 0)
        except (TypeError, ValueError):
            target_id = 0
        if target_id <= 0:
            continue
        target_type = str(member.get("targetType") or member.get("target_type") or "").lower()
        if "gameplayer" in target_type:
            continue
        target_ids.add(target_id)
    return max(0, len(target_ids) - 1)


def dialogue_command_intent(event_type: str) -> str:
    event_type = str(event_type or "").strip().lower()
    if event_type in {"player_requested_heal", "leader_critical", "party_member_low_health"}:
        return "heal_priority"
    if event_type == "party_member_dead":
        return "resurrect_priority"
    if event_type == "add_pressure":
        return "cc_add"
    if event_type in {"party_member_crowd_controlled", "player_crowd_controlled"}:
        return "cure_priority"
    if event_type == "companion_joined":
        return "follow"
    if event_type in {"player_requested_wait", "companion_low_mana"}:
        return "wait"
    if event_type in {"leader_fleeing", "companion_fleeing"}:
        return "flee"
    return "none"


def companion_personality_for_role(role: Any) -> str:
    role = normalize_role(role)
    return {
        "tank": "steady_protector",
        "healer": "calm_support",
        "support": "loyal_guardian",
        "dps": "sharp_striker",
        "fill": "cautious_scout",
    }.get(role, "cautious_scout")


def companion_personality_behavior_flags(personality: str, role: Any, action_rotation: str) -> list[str]:
    personality = str(personality or "").strip()
    normalized_role = normalize_role(role)
    flags_by_personality = {
        "steady_protector": [
            "--flee-health-percent",
            "40",
            "--flee-pressure-health-percent",
            "75",
            "--required-target-tank-commit-health-percent",
            "35",
            "--party-survival-active-tank-health-percent",
            "35",
        ],
        "calm_support": [
            "--flee-health-percent",
            "45",
            "--flee-pressure-health-percent",
            "80",
            "--skill-interval",
            "0.85",
        ],
        "bold_vanguard": [
            "--party-assist-attack-delay",
            "0.1",
            "--flee-health-percent",
            "30",
            "--required-target-tank-commit-health-percent",
            "45",
        ],
        "sharp_striker": [
            "--party-assist-attack-delay",
            "0.1",
            "--combat-interval",
            "0.5",
            "--skill-interval",
            "0.75",
        ],
        "cautious_scout": [
            "--party-assist-attack-delay",
            "0.8",
            "--flee-health-percent",
            "47",
            "--flee-pressure-health-percent",
            "85",
            "--party-preengage-ranged-safe-distance",
            "2200",
        ],
        "wary_survivor": [
            "--party-assist-attack-delay",
            "1.2",
            "--flee-health-percent",
            "55",
            "--flee-pressure-health-percent",
            "90",
        ],
        "loyal_guardian": [
            "--party-assist-attack-delay",
            "0.2",
            "--party-survival-active-tank-health-percent",
            "45",
            "--flee-health-percent",
            "40",
        ],
        "eager_rookie": [
            "--party-assist-attack-delay",
            "0.1",
            "--party-follow-step",
            "410",
        ],
        "sly_opportunist": [
            "--party-assist-attack-delay",
            "0.15",
            "--flee-health-percent",
            "45",
            "--boss-ranged-safe-distance",
            "2000",
        ],
        "shifty_traitor": [
            "--party-assist-attack-delay",
            "1.6",
            "--flee-health-percent",
            "60",
            "--flee-pressure-health-percent",
            "92",
        ],
        "reckless_berserker": [
            "--party-assist-attack-delay",
            "0",
            "--flee-health-percent",
            "15",
            "--flee-pressure-health-percent",
            "35",
            "--required-target-tank-commit-health-percent",
            "55",
        ],
        "lazy_veteran": [
            "--party-assist-attack-delay",
            "1.0",
            "--combat-interval",
            "0.8",
            "--skill-interval",
            "1.2",
        ],
    }
    flags = list(flags_by_personality.get(personality, []))
    if normalized_role in {"healer", "support"} and action_rotation == "healer-support" and personality in {
        "bold_vanguard",
        "reckless_berserker",
    }:
        flags += ["--flee-health-percent", "43"]
    return flags


def build_companion_dialogue_payload(
    companion: ActiveCompanion,
    requester_state: dict[str, Any] | None,
    event_type: str,
    companion_state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    player = player_row(requester_state)
    companion_player = player_row(companion_state)
    role = request_value(companion.request, "requestedRole", "RequestedRole", default="fill")
    event_type = str(event_type or "status")
    mercenary_state = mercenary_operational_state(companion.request)
    mercenary_record = dict(mercenary_state.get("record") or {})
    personality = request_mercenary_personality(companion.request) or companion_personality_for_role(role)
    memory_parts = []
    if mercenary_state["traits"]:
        memory_parts.append("특성: " + ", ".join(str(trait) for trait in mercenary_state["traits"]))
    memory_parts.append(mercenary_trust_dialogue_note(int(mercenary_state["trust"])))
    if mercenary_state["memory"]:
        memory_parts.append(str(mercenary_state["memory"]))
    primary_title = mercenary_primary_title_label(mercenary_record.get("earned_titles", ""))
    if primary_title:
        memory_parts.append(f"현재 칭호: {primary_title}")
    if any(int(mercenary_record.get(key, 0) or 0) > 0 for key in ("total_contracts", "kills_together", "rescues", "quests_completed")):
        memory_parts.append(
            "누적 기록: "
            f"계약 {int(mercenary_record.get('total_contracts', 0) or 0)}회, "
            f"처치 기여 {int(mercenary_record.get('kills_together', 0) or 0)}회, "
            f"구출 {int(mercenary_record.get('rescues', 0) or 0)}회, "
            f"개인 의뢰 {int(mercenary_record.get('quests_completed', 0) or 0)}회"
        )
    personal_quest = mercenary_personal_quest_label(mercenary_record.get("personal_quest_state", ""))
    if personal_quest:
        memory_parts.append(f"개인 의뢰: {personal_quest}")
    relationship_events = mercenary_relationship_event_labels(mercenary_record.get("relationship_event_state", ""))
    if relationship_events:
        memory_parts.append("관계 이벤트: " + ", ".join(relationship_events))
    return {
        "feature": "companion_dialogue",
        "event_type": event_type,
        "realm": str(request_value(companion.request, "realm", "Realm", default="unknown")),
        "role": normalize_role(role),
        "personality": personality,
        "state": {
            "combat": bool(player.get("inCombat")),
            "leader_health_band": health_band_from_percent(player.get("healthPercent")),
            "party_lowest_health_band": health_band_from_percent(party_lowest_health_percent(requester_state)),
            "companion_health_band": health_band_from_percent(companion_player.get("healthPercent")),
            "companion_mana_band": health_band_from_percent(
                numeric_percent(companion_player, "manaPercent", "powerPercent", "mana_percent", "power_percent")
            ),
            "adds": estimate_add_count(requester_state),
            "party_dead": max(0, party_dead_count(requester_state)),
            "party_crowd_controlled": max(0, party_crowd_controlled_count(requester_state)),
            "player_called": event_type.startswith("player_requested_"),
            "command_intent": dialogue_command_intent(event_type),
            "mercenary": {
                "tactic": str(mercenary_state["tactic"]),
                "trust": int(mercenary_state["trust"]),
                "trust_stage": mercenary_trust_stage(int(mercenary_state["trust"])),
                "fatigue": int(mercenary_state["fatigue"]),
                "traits": list(mercenary_state["traits"]),
                "record": dict(mercenary_record),
            },
        },
        "memory": " | ".join(memory_parts),
    }


SERVICE_ALLOWED_CHANNELS = {"party", "say", "none"}
SERVICE_ALLOWED_HINTS = {
    "none",
    "heal_priority",
    "resurrect_priority",
    "follow",
    "wait",
    "assist",
    "flee",
    "cc_add",
    "cure_priority",
}
SERVICE_ALLOWED_URGENCY = {"low", "normal", "high"}
MAX_COMPANION_SAY_TEXT_LENGTH = 120


def normalize_dialogue_intent_hint(value: Any) -> str:
    hint = str(value or "none").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "heal": "heal_priority",
        "healing": "heal_priority",
        "res": "resurrect_priority",
        "rez": "resurrect_priority",
        "resurrect": "resurrect_priority",
        "cc": "cc_add",
        "crowd_control": "cc_add",
        "mez": "cc_add",
        "stun": "cc_add",
        "cure": "cure_priority",
        "cleanse": "cure_priority",
        "purge": "cure_priority",
        "attack": "assist",
        "attack_assist": "assist",
        "escape": "flee",
    }
    hint = aliases.get(hint, hint)
    return hint if hint in SERVICE_ALLOWED_HINTS else "none"


def sanitize_companion_dialogue_response(response: dict[str, Any]) -> dict[str, str] | None:
    channel = str(response.get("say_channel") or "none").strip().lower()
    if channel not in SERVICE_ALLOWED_CHANNELS:
        return None
    urgency = str(response.get("urgency") or "normal").strip().lower()
    if urgency not in SERVICE_ALLOWED_URGENCY:
        return None
    text = " ".join(str(response.get("say_text") or "").split())
    if len(text) > MAX_COMPANION_SAY_TEXT_LENGTH:
        return None
    if text.startswith("/") or "\n/" in text or " /" in text:
        return None
    lowered = text.lower()
    forbidden = ("gold", "realm point", "drop rate", "ban", "gm", "보상", "골드", "추방")
    if any(word in lowered for word in forbidden):
        return None
    return {
        "say_channel": channel,
        "say_text": text,
        "intent_hint": normalize_dialogue_intent_hint(response.get("intent_hint")),
        "urgency": urgency,
    }


def sanitize_companion_guide_response(response: dict[str, Any]) -> dict[str, Any] | None:
    channel = str(response.get("say_channel") or "party").strip().lower()
    if channel not in SERVICE_ALLOWED_CHANNELS:
        return None
    raw_lines = response.get("guide_lines")
    if not isinstance(raw_lines, list):
        return None
    lines = [" ".join(str(line or "").split()) for line in raw_lines]
    lines = [line for line in lines if line]
    if len(lines) < 3 or len(lines) > 5:
        return None
    for line in lines:
        if len(line) > MAX_COMPANION_SAY_TEXT_LENGTH:
            return None
        if line.startswith("/") or "\n/" in line or " /" in line:
            return None
    source_ids = response.get("source_ids", [])
    if not isinstance(source_ids, list):
        source_ids = []
    return {
        "say_channel": channel,
        "guide_lines": lines,
        "source_ids": [str(source_id or "").strip() for source_id in source_ids if str(source_id or "").strip()][:8],
        "intent_hint": "none",
        "urgency": str(response.get("urgency") or "normal"),
    }


def write_companion_live_control(path: Path, response: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "revision": next_live_control_revision(),
        "say_channel": str(response.get("say_channel") or "none"),
        "say_text": str(response.get("say_text") or ""),
        "guide_lines": list(response.get("guide_lines") or []),
        "source_ids": list(response.get("source_ids") or []),
        "intent_hint": str(response.get("intent_hint") or "none"),
        "urgency": str(response.get("urgency") or "normal"),
    }
    path.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def companion_control_path(args: argparse.Namespace, request_id: str) -> Path:
    return Path(arg_string(args, "run_dir", "test-output/live-companions")) / request_id / "live-control.json"


def call_ai_gateway(
    args: argparse.Namespace,
    payload: dict[str, Any],
    *,
    feature: str = "companion_dialogue",
    model_alias: str = "",
) -> dict[str, Any]:
    command = [sys.executable, "tools/opendaoc-ai-gateway.py"]
    config = arg_string(args, "ai_gateway_config", "")
    if config:
        command += ["--config", config]
    if not model_alias:
        model_alias = (
            arg_string(args, "ai_guide_model_alias", "openai-small-guide")
            if feature == "companion_guide"
            else arg_string(args, "ai_gateway_model_alias", "small-dialogue")
        )
    command += [
        "generate",
        "--feature",
        feature,
        "--model-alias",
        model_alias or "small-dialogue",
        "--payload-json",
        json.dumps(payload, ensure_ascii=False),
    ]
    try:
        env = dict(os.environ)
        env.setdefault("PYTHONIOENCODING", "utf-8")
        completed = subprocess.run(
            command,
            cwd=arg_string(args, "repo_root", str(ROOT)),
            text=True,
            encoding="utf-8",
            capture_output=True,
            timeout=arg_float(args, "ai_gateway_timeout", 5.0),
            env=env,
        )
    except subprocess.TimeoutExpired:
        return {"allowed": False, "blocked_reason": "gateway_timeout"}
    except OSError:
        return {"allowed": False, "blocked_reason": "gateway_process_failed"}
    if completed.returncode != 0:
        return {"allowed": False, "blocked_reason": "gateway_process_failed"}
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError:
        return {"allowed": False, "blocked_reason": "gateway_invalid_stdout"}


def request_companion_dialogue(args: argparse.Namespace, payload: dict[str, Any], control_path: Path) -> bool:
    if not dialogue_enabled_from_server_or_cli(args):
        return False
    result = call_ai_gateway(args, payload)
    if not result.get("allowed"):
        return False
    response = result.get("response")
    if not isinstance(response, dict):
        return False
    sanitized = sanitize_companion_dialogue_response(response)
    if sanitized is None:
        return False
    write_companion_live_control(control_path, sanitized)
    return True


def request_companion_guide(args: argparse.Namespace, payload: dict[str, Any], control_path: Path) -> bool:
    if not dialogue_enabled_from_server_or_cli(args):
        return False
    result = call_ai_gateway(args, payload, feature="companion_guide")
    if not result.get("allowed"):
        return False
    response = result.get("response")
    if not isinstance(response, dict):
        return False
    sanitized = sanitize_companion_guide_response(response)
    if sanitized is None:
        return False
    write_companion_live_control(control_path, sanitized)
    return True


def emit_companion_dialogue(
    args: argparse.Namespace,
    companion: ActiveCompanion,
    requester_state: dict[str, Any] | None,
    event_type: str,
) -> bool:
    request_id = str(request_value(companion.request, "id", "Id", default=""))
    if not request_id:
        return False
    companion_state: dict[str, Any] | None = None
    if companion.account:
        try:
            companion_state = fetch_player_state_by_account(args, companion.account)
        except Exception:
            companion_state = None
    payload = build_companion_dialogue_payload(companion, requester_state, event_type, companion_state)
    return request_companion_dialogue(args, payload, companion_control_path(args, request_id))


def should_emit_dialogue(dialogue_state: dict[str, float], key: str, now: float, interval: float) -> bool:
    previous = float(dialogue_state.get(key, 0.0) or 0.0)
    if now - previous < max(0.0, interval):
        return False
    return True


def dialogue_event_for_requester_state(requester_state: dict[str, Any] | None) -> str:
    player = player_row(requester_state)
    try:
        health_percent = float(player.get("healthPercent") or 100)
    except (TypeError, ValueError):
        health_percent = 100
    if party_dead_count(requester_state) > 0:
        return "party_member_dead"
    if party_crowd_controlled_count(requester_state) > 0:
        return "party_member_crowd_controlled"
    if estimate_add_count(requester_state) > 0 and bool(player.get("inCombat")):
        return "add_pressure"
    if bool(player.get("inCombat")) and health_percent < 30:
        return "leader_critical"
    if bool(player.get("inCombat")) and health_percent < 55:
        return "player_requested_heal"
    lowest = party_lowest_health_percent(requester_state)
    if bool(player.get("inCombat")) and lowest is not None and lowest < 55:
        return "party_member_low_health"
    return ""


def fetch_requester_state(args: argparse.Namespace, request: dict[str, Any]) -> dict[str, Any] | None:
    requester_account = str(request_value(request, "requesterAccount", "RequesterAccount", default="")).strip()
    requester_name = str(request_value(request, "requesterName", "RequesterName", default="")).strip()
    query: dict[str, Any] = {}
    if requester_account:
        query["account"] = requester_account
    elif requester_name:
        query["name"] = requester_name
    else:
        return None

    state = api_request(args, "GET", "/api/dummy/combat/usable", query)
    if not isinstance(state, dict) or state.get("error"):
        return None
    player = state.get("player")
    return state if isinstance(player, dict) else None


def requester_spawn_ready(state: dict[str, Any] | None) -> tuple[bool, str]:
    if state is None:
        return False, "requester offline"
    player = state.get("player") if isinstance(state, dict) else None
    if not isinstance(player, dict):
        return False, "requester unavailable"
    if bool(player.get("isDead")) or bool(player.get("isAlive")) is False:
        return False, "requester dead"
    return True, ""


def fetch_player_state_by_account(args: argparse.Namespace, account: str) -> dict[str, Any] | None:
    if not account:
        return None
    state = api_request(args, "GET", "/api/dummy/combat/usable", {"account": account})
    if not isinstance(state, dict) or state.get("error"):
        return None
    player = state.get("player")
    return state if isinstance(player, dict) else None


def online_accounts_from_pool(args: argparse.Namespace, account_csv: str | Path) -> set[str]:
    online: set[str] = set()
    for account in account_usernames_from_csv(account_csv):
        try:
            if fetch_player_state_by_account(args, account) is not None:
                online.add(account.strip().lower())
        except Exception:
            continue
    return online


def prune_account_cooldowns(account_cooldowns: dict[str, float], now: float) -> None:
    for account, expires_at in list(account_cooldowns.items()):
        if expires_at <= now:
            account_cooldowns.pop(account, None)


def mark_account_cooldown(args: argparse.Namespace, account_cooldowns: dict[str, float] | None, account: str) -> None:
    if account_cooldowns is None or not account:
        return
    cooldown = max(0.0, float(getattr(args, "account_reuse_cooldown", 0.0) or 0.0))
    if cooldown <= 0.0:
        return
    account_cooldowns[account.strip().lower()] = time.monotonic() + cooldown


def wait_for_companion_online(args: argparse.Namespace, account_csv: str | Path) -> str:
    account = first_account_username(account_csv)
    if not account:
        return ""
    deadline = time.monotonic() + max(0.0, float(getattr(args, "attach_timeout", 0.0)))
    while time.monotonic() <= deadline:
        if fetch_player_state_by_account(args, account) is not None:
            return account
        time.sleep(0.5)
    return ""


def attach_companion_to_request(args: argparse.Namespace, request_id: str, account: str) -> tuple[bool, str]:
    try:
        payload = api_request(
            args,
            "POST",
            f"/api/dummy/companions/requests/{urllib.parse.quote(request_id)}/attach",
            {"account": account},
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return False, detail or f"attach failed with HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)
    if payload is None:
        return False, "attach failed: request or companion not found"
    return True, ""


def current_request_status(args: argparse.Namespace, request_id: str) -> str:
    try:
        payload = api_request(args, "GET", f"/api/dummy/companions/requests/{urllib.parse.quote(request_id)}")
    except Exception:
        return ""
    if not isinstance(payload, dict):
        return ""
    return str(request_value(payload, "status", "Status", default="")).strip().lower()


def request_status_is_externally_closed(status: str) -> bool:
    return str(status or "").strip().lower() in {"canceled", "cancelled", "failed", "completed"}


def should_check_active_request_status(args: argparse.Namespace, companion: ActiveCompanion, now: float) -> bool:
    interval = max(0.0, arg_float(args, "active_request_status_interval", 15.0))
    if interval <= 0.0:
        return True
    return companion.last_request_status_check <= 0.0 or now - companion.last_request_status_check >= interval


def active_request_is_externally_closed(args: argparse.Namespace, request_id: str, companion: ActiveCompanion, now: float) -> bool:
    if not should_check_active_request_status(args, companion, now):
        return False
    companion.last_request_status_check = now
    return request_status_is_externally_closed(current_request_status(args, request_id))


def detach_companion_from_request(args: argparse.Namespace, request_id: str, account: str) -> tuple[bool, str]:
    try:
        payload = api_request(
            args,
            "POST",
            f"/api/dummy/companions/requests/{urllib.parse.quote(request_id)}/detach",
            {"account": account},
        )
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        return False, detail or f"detach failed with HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)
    if payload is None:
        return False, "detach failed: request or companion not found"
    return True, ""


def companion_leave_farewell_line(reason: str = "leave_request") -> str:
    if str(reason or "").strip().lower() in {"leave_request", "party_kick", "kick", "dismiss"}:
        return "알겠습니다. 계약을 정리하고 파티에서 빠지겠습니다. 빈자리는 제가 비워두겠습니다."
    return ""


def request_companion_quit(control_path: Path | None, *, farewell_line: str = "") -> None:
    if control_path is None:
        return
    control_path.parent.mkdir(parents=True, exist_ok=True)
    commands = []
    if farewell_line:
        commands.append(f"/g {farewell_line[:120]}")
    commands.append("/quit")
    control_path.write_text(
        json.dumps(
            {
                "revision": next_live_control_revision(),
                "commands": commands,
                "intent_hint": "leave",
                "quit_after_sit_seconds": 4.0,
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        encoding="utf-8",
    )


def stop_companion(
    process: subprocess.Popen,
    timeout: float = 10.0,
    control_path: Path | None = None,
    farewell_line: str = "",
) -> None:
    if process.poll() is not None:
        return
    request_companion_quit(control_path, farewell_line=farewell_line)
    try:
        process.wait(timeout=max(1.0, timeout))
        return
    except subprocess.TimeoutExpired:
        pass
    process.terminate()
    try:
        process.wait(timeout=max(1.0, min(timeout, 5.0)))
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=max(1.0, min(timeout, 5.0)))


def stop_all_active_companions(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    reason: str,
) -> None:
    for request_id, companion in list(active.items()):
        stop_companion(companion.process, control_path=companion.control_path)
        try:
            update_request_status(args, request_id, "completed", reason, companion.account)
        finally:
            active.pop(request_id, None)


def release_active_companions_for_leave_request(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    leave_request: dict[str, Any],
) -> int:
    requester_key = request_requester_key(leave_request)
    if not requester_key:
        return 0

    released = 0
    for request_id, companion in list(active.items()):
        if not request_matches_requester(companion.request, requester_key):
            continue

        detached, message = detach_companion_from_request(args, request_id, companion.account)
        stop_companion(
            companion.process,
            control_path=companion.control_path,
            farewell_line=companion_leave_farewell_line("leave_request"),
        )
        status_message = "leave request; companion released"
        if not detached and message:
            status_message = f"{status_message}; detach warning: {message}"
        update_request_status(
            args,
            request_id,
            "completed",
            status_message,
            companion.account,
            close_reason="leader_dismissed",
        )
        active.pop(request_id, None)
        released += 1
    return released


def handle_request(
    args: argparse.Namespace,
    request: dict[str, Any],
    active: dict[str, ActiveCompanion],
    account_cooldowns: dict[str, float] | None = None,
) -> None:
    request_id = str(request_value(request, "id", "Id", default=""))
    if is_leave_request(request):
        released = release_active_companions_for_leave_request(args, active, request)
        message = (
            f"leave request acknowledged; released {released} companion(s)"
            if released
            else "leave request acknowledged; no active companion"
        )
        update_request_status(args, request_id, "completed", message)
        return

    requester_state = fetch_requester_state(args, request)
    ready, reason = requester_spawn_ready(requester_state)
    if not ready:
        update_request_status(
            args,
            request_id,
            "failed",
            f"cannot spawn companion: {reason}",
            close_reason="system_spawn_blocked",
        )
        return

    slot_block_reason = companion_slot_block_reason(active, request, requester_state)
    if slot_block_reason:
        update_request_status(
            args,
            request_id,
            "failed",
            f"cannot spawn companion: {slot_block_reason}",
            close_reason="party_full",
        )
        return

    run_dir = Path(args.run_dir) / request_id
    active_accounts = {companion.account.lower() for companion in active.values() if companion.account}
    active_accounts.update(online_accounts_from_pool(args, args.accounts_csv))
    if account_cooldowns is not None:
        prune_account_cooldowns(account_cooldowns, time.monotonic())
        active_accounts.update(account_cooldowns)
    try:
        companion_accounts_csv = select_companion_accounts_csv(request, args.accounts_csv, run_dir, active_accounts)
        companion_account = first_account_username(companion_accounts_csv)
        if not companion_account:
            raise ValueError("selected companion account csv has no usable account")
        command = build_behavior_command(args, request, companion_accounts_csv, run_dir, requester_state=requester_state)
    except (OSError, ValueError) as exc:
        update_request_status(
            args,
            request_id,
            "failed",
            f"cannot spawn companion: {exc}",
            close_reason="system_spawn_failed",
        )
        return

    if args.dry_run:
        print(json.dumps({"request": request, "command": command}, ensure_ascii=False))
        return

    update_request_status(args, request_id, "spawning", "starting live companion behavior client")
    process = subprocess.Popen(command, cwd=args.repo_root)
    control_path = companion_control_path(args, request_id)
    active[request_id] = ActiveCompanion(
        request=request,
        process=process,
        account=companion_account,
        control_path=control_path,
    )
    update_request_status(args, request_id, "grouping", "live companion behavior client started; waiting for grouping", companion_account)
    companion = active[request_id]

    if getattr(args, "attach_group", True):
        account = wait_for_companion_online(args, companion_accounts_csv)
        if not account:
            stop_companion(process, control_path=control_path)
            mark_account_cooldown(args, account_cooldowns, companion_account)
            active.pop(request_id, None)
            update_request_status(
                args,
                request_id,
                "failed",
                "companion did not appear online before grouping timeout",
                close_reason="system_grouping_timeout",
            )
            return

        attached, message = attach_companion_to_request(args, request_id, account)
        if not attached:
            stop_companion(process, control_path=control_path)
            mark_account_cooldown(args, account_cooldowns, account)
            active.pop(request_id, None)
            update_request_status(
                args,
                request_id,
                "failed",
                f"group attach failed: {message}",
                account,
                close_reason="system_attach_failed",
            )
            return
        update_request_status(args, request_id, "active", "live companion grouped and active", account)
        emit_companion_dialogue(args, companion, requester_state, "companion_joined")
    else:
        update_request_status(args, request_id, "active", "live companion behavior client started")
        emit_companion_dialogue(args, companion, requester_state, "companion_joined")


def release_companion_for_real_player(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    request_id: str,
    release_counts: dict[str, int],
    requester_key: str,
) -> None:
    companion = active.get(request_id)
    if companion is None:
        return

    detached, message = detach_companion_from_request(args, request_id, companion.account)
    stop_companion(companion.process, control_path=companion.control_path)
    status_message = "real player joined; companion released"
    if not detached and message:
        status_message = f"{status_message}; detach warning: {message}"
    update_request_status(
        args,
        request_id,
        "completed",
        status_message,
        companion.account,
        close_reason="real_player_joined",
    )
    active.pop(request_id, None)
    release_counts[requester_key] = int(release_counts.get(requester_key, 0) or 0) + 1


def release_companion_for_party_loss(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    request_id: str,
) -> None:
    companion = active.get(request_id)
    if companion is None:
        return

    detached, message = detach_companion_from_request(args, request_id, companion.account)
    stop_companion(companion.process, control_path=companion.control_path)
    status_message = "party disbanded or companion removed; companion released"
    if not detached and message:
        status_message = f"{status_message}; detach warning: {message}"
    update_request_status(
        args,
        request_id,
        "completed",
        status_message,
        companion.account,
        close_reason="party_lost",
    )
    active.pop(request_id, None)


def refresh_active_companion_lease(
    args: argparse.Namespace,
    request_id: str,
    companion: ActiveCompanion,
    now: float,
) -> None:
    interval = arg_float(args, "active_lease_refresh_interval", 30.0)
    if companion.last_lease_refresh and now - companion.last_lease_refresh < max(1.0, interval):
        return
    update_request_status(args, request_id, "active", "live companion heartbeat", companion.account)
    companion.last_lease_refresh = now


def poll_active(
    args: argparse.Namespace,
    active: dict[str, ActiveCompanion],
    release_counts: dict[str, int] | None = None,
    dialogue_state: dict[str, float] | None = None,
    account_cooldowns: dict[str, float] | None = None,
) -> None:
    release_counts = release_counts if release_counts is not None else {}
    dialogue_state = dialogue_state if dialogue_state is not None else {}
    finished: list[str] = []
    requester_states: dict[str, dict[str, Any] | None] = {}
    for request_id, companion in list(active.items()):
        process = companion.process
        return_code = process.poll()
        if return_code is None:
            now = time.monotonic()
            if active_request_is_externally_closed(args, request_id, companion, now):
                detach_companion_from_request(args, request_id, companion.account)
                stop_companion(process, control_path=companion.control_path)
                finished.append(request_id)
                continue

            requester_key = request_requester_key(companion.request)
            requester_state = requester_states.setdefault(requester_key, fetch_requester_state(args, companion.request))
            if requester_state is None:
                grace = max(0, request_offline_grace_seconds(companion.request))
                if grace > 0:
                    if companion.requester_offline_since <= 0.0:
                        companion.requester_offline_since = now
                        update_request_status(
                            args,
                            request_id,
                            "active",
                            f"requester offline; waiting {grace} seconds for reconnect",
                            companion.account,
                        )
                    if now - companion.requester_offline_since <= grace:
                        refresh_active_companion_lease(args, request_id, companion, now)
                        continue

                detach_companion_from_request(args, request_id, companion.account)
                stop_companion(process, control_path=companion.control_path)
                update_request_status(
                    args,
                    request_id,
                    "completed",
                    "requester offline grace expired; companion stopped",
                    close_reason="offline_grace_expired",
                )
                finished.append(request_id)
            else:
                if companion.requester_offline_since > 0.0:
                    update_request_status(args, request_id, "active", "requester reconnected; companion resumed", companion.account)
                    companion.requester_offline_since = 0.0
                refresh_active_companion_lease(args, request_id, companion, now)
                event_type = dialogue_event_for_requester_state(requester_state)
                if event_type:
                    dialogue_key = f"{request_id}:{event_type}"
                    if should_emit_dialogue(
                        dialogue_state,
                        dialogue_key,
                        time.monotonic(),
                        arg_float(args, "dialogue_min_interval", 5.0),
                    ):
                        if emit_companion_dialogue(args, companion, requester_state, event_type):
                            dialogue_state[dialogue_key] = time.monotonic()
            continue
        status = "completed" if return_code == 0 else "failed"
        mark_account_cooldown(args, account_cooldowns, companion.account)
        run_dir = Path(arg_string(args, "run_dir", "test-output/live-companions")) / request_id
        update_request_status(
            args,
            request_id,
            status,
            f"behavior client exited with {return_code}",
            close_reason=(
                live_companion_success_close_reason(companion.request, run_dir)
                if status == "completed"
                else "system_behavior_client_exit"
            ),
        )
        finished.append(request_id)
    for request_id in finished:
        active.pop(request_id, None)

    for requester_key, requester_state in requester_states.items():
        request_id = choose_release_request_for_missing_group_companion(active, requester_key, requester_state)
        if request_id:
            release_companion_for_party_loss(args, active, request_id)
            continue

        request_id = choose_release_request_for_real_player_join(active, requester_key, requester_state, release_counts)
        if request_id:
            release_companion_for_real_player(args, active, request_id, release_counts, requester_key)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run live companion behavior clients from server companion requests.")
    parser.add_argument("--api-url", default="http://localhost:5000")
    parser.add_argument("--api-timeout", type=float, default=2.0)
    parser.add_argument("--api-startup-wait", type=float, default=60.0)
    parser.add_argument("--api-startup-retry-interval", type=float, default=0.5)
    parser.add_argument("--api-password", default=os.environ.get("OPENDAOC_API_PASSWORD", ""))
    parser.add_argument("--accounts-csv", default=str(Path(__file__).resolve().with_name("dummy-live-companions.csv")))
    parser.add_argument("--run-dir", default="test-output/live-companions")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--hold", type=float, default=3600.0)
    parser.add_argument("--combat-home-leash-distance", type=float, default=4500.0)
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--attach-timeout", type=float, default=15.0)
    parser.add_argument("--attach-group", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--active-lease-refresh-interval", type=float, default=30.0)
    parser.add_argument("--active-request-status-interval", type=float, default=15.0)
    parser.add_argument("--recover-orphaned-active-requests", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dialogue-enabled", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--guide-enabled", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--ai-gateway-config", default="")
    parser.add_argument("--ai-gateway-model-alias", default="small-dialogue")
    parser.add_argument("--ai-guide-model-alias", default="openai-small-guide")
    parser.add_argument("--ai-gateway-timeout", type=float, default=5.0)
    parser.add_argument("--dialogue-min-interval", type=float, default=5.0)
    parser.add_argument("--healer-boss-ranged-safe-distance", type=float, default=0.0)
    parser.add_argument("--healer-party-preengage-ranged-safe-distance", type=float, default=0.0)
    parser.add_argument("--healer-boss-non-tank-follow-distance", type=float, default=0.0)
    parser.add_argument("--healer-flee-pressure-health-percent", type=float, default=0.0)
    parser.add_argument("--healer-flee-health-percent", type=float, default=0.0)
    parser.add_argument(
        "--healer-heal-exclude-names",
        default="",
        help="pipe- or comma-separated party member names the healer companion must NOT heal (still resurrectable); forwarded as --party-heal-exclude-names",
    )
    parser.add_argument("--companion-flee-pressure-health-percent", type=float, default=0.0)
    parser.add_argument("--companion-flee-health-percent", type=float, default=0.0)
    parser.add_argument("--force-companion-personality", default="")
    parser.add_argument("--max-runtime", type=float, default=0.0, help="stop the service after this many seconds; 0 runs until interrupted")
    parser.add_argument("--party-size", type=int, default=1, help="effective party size to pass to companions")
    parser.add_argument("--account-reuse-cooldown", type=float, default=75.0)
    parser.add_argument("--stop-file", default="", help="exit gracefully when this file exists")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    stop_file = service_stop_file(args)
    if stop_file.exists():
        stop_file.unlink()
    if not wait_for_server_api_ready(args):
        return 2
    recovered = recover_orphaned_active_requests(args)
    if recovered:
        print(f"[OpenDAoC] Requeued {recovered} orphaned active companion request(s).")
    active: dict[str, ActiveCompanion] = {}
    release_counts: dict[str, int] = {}
    dialogue_state: dict[str, float] = {}
    account_cooldowns: dict[str, float] = {}
    deadline = time.monotonic() + max(0.0, float(args.max_runtime)) if args.max_runtime else None

    try:
        while True:
            poll_active(args, active, release_counts, dialogue_state, account_cooldowns)
            if service_stop_requested(args):
                return 0
            request = claim_next_request(args)
            if request is not None:
                handle_request(args, request, active, account_cooldowns)
            elif args.once:
                return 0

            if deadline is not None and time.monotonic() >= deadline:
                return 0

            if args.once:
                poll_active(args, active, release_counts, dialogue_state, account_cooldowns)
                return 0
            time.sleep(max(0.25, args.poll_interval))
    finally:
        if active:
            stop_all_active_companions(args, active, "companion service stopped; companion stopped")


if __name__ == "__main__":
    raise SystemExit(main())
