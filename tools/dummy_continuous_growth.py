"""Continuous-session supervisor for natural dummy level progression."""

from __future__ import annotations

import csv
import json
import math
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

try:
    from tools.dummy_progression_audit import (
        EconomyLedger,
        ProgressionAnomaly,
        ProgressionItem,
        ProgressionSnapshot,
        audit_progression_checkpoint,
        parse_progression_snapshot,
        specialization_gains,
        write_compact_anomaly_summary,
    )
except ModuleNotFoundError:
    from dummy_progression_audit import (
        EconomyLedger,
        ProgressionAnomaly,
        ProgressionItem,
        ProgressionSnapshot,
        audit_progression_checkpoint,
        parse_progression_snapshot,
        specialization_gains,
        write_compact_anomaly_summary,
    )


@dataclass(frozen=True)
class ContinuousSupervisorOptions:
    api_base_url: str
    api_password: str = ""
    poll_interval: float = 0.5
    online_timeout: float = 120.0
    level_timeout: float = 3600.0
    service_timeout: float = 180.0
    request_timeout: float = 3.0
    max_level: int = 50
    fail_on_checkpoint_error: bool = True
    dynamic_quests: bool = True
    dynamic_quest_poll_interval: float = 2.0
    dynamic_quest_timeout: float = 240.0
    dynamic_quest_max_target_count: int = 8
    dynamic_quest_max_level_delta: int = 2
    dynamic_quest_max_distance: float = 60000.0


@dataclass(frozen=True)
class ContinuousSupervisorResult:
    ok: bool
    completed_level: int
    checkpoints: int
    anomalies: tuple[ProgressionAnomaly, ...]
    error: str = ""
    mode: str = ""
    realm: str = ""
    party_size: int = 0


@dataclass(frozen=True)
class DynamicQuestObservation:
    quest_id: str
    title: str
    node_id: str
    node_type: str
    target_name: str
    target_count: int
    current_count: int
    min_level: int
    max_level: int
    region: int
    x: int
    y: int
    z: int
    radius: int
    npc_name: str
    npc_internal_id: str
    stalled_reason: str
    failed: bool
    elapsed_seconds: int

    @property
    def signature(self) -> tuple[object, ...]:
        return (
            self.quest_id,
            self.node_id,
            self.node_type,
            self.target_name,
            self.current_count,
            self.target_count,
            self.region,
            self.x,
            self.y,
        )


@dataclass(frozen=True)
class DynamicQuestStartScope:
    region: int
    x: int
    y: int
    z: int
    radius: int
    location_name: str = ""


@dataclass(frozen=True)
class DynamicQuestOfferObservation:
    quest_id: str
    title: str
    target_name: str
    min_level: int
    max_level: int
    trigger: str
    trigger_matches: bool
    player_level_matches: bool
    has_completed: bool
    has_completed_story_family: bool
    has_progress: bool
    has_active_story_family: bool
    inside_start_scope: bool
    blocked_reasons: tuple[str, ...]
    start_scopes: tuple[DynamicQuestStartScope, ...]
    tags: tuple[str, ...]


@dataclass
class DynamicQuestTrack:
    quest_id: str
    title: str
    started_at: float
    last_progress_at: float
    last_signature: tuple[object, ...]
    start_experience: int
    start_money_copper: int
    skipped: bool = False


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def command_option_value(command: list[str], option: str, default: str = "") -> str:
    try:
        index = command.index(option)
    except ValueError:
        return default
    return command[index + 1] if index + 1 < len(command) else default


def command_has_flag(command: list[str], option: str) -> bool:
    return option in command


def replace_command_option(command: list[str], option: str, value: object) -> list[str]:
    updated = list(command)
    try:
        index = updated.index(option)
    except ValueError:
        updated.extend([option, str(value)])
        return updated
    if index + 1 >= len(updated):
        updated.append(str(value))
    else:
        updated[index + 1] = str(value)
    return updated


def remove_command_option(command: list[str], option: str, *, takes_value: bool = True) -> list[str]:
    updated = list(command)
    while option in updated:
        index = updated.index(option)
        del updated[index]
        if takes_value and index < len(updated):
            del updated[index]
    return updated


def atomic_write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def safe_status_component(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip())
    return normalized.strip("-.") or "unknown"


def status_path(status_directory: Path, request_id: str, account: str) -> Path:
    return status_directory / (
        f"{safe_status_component(request_id)}--{safe_status_component(account)}.json"
    )


def usable_api_url(api_base_url: str, account: str, character: str = "") -> str:
    query = urllib.parse.urlencode({"account": account, "name": character})
    return f"{api_base_url.rstrip('/')}/api/dummy/combat/usable?{query}"


def dynamic_quest_progress_url(api_base_url: str, account: str, character: str = "") -> str:
    query = urllib.parse.urlencode({"account": account, "player": character})
    return f"{api_base_url.rstrip('/')}/api/world/dynamic-quests/progress?{query}"


def dynamic_quest_timeline_url(api_base_url: str, account: str, character: str = "") -> str:
    query = urllib.parse.urlencode({"account": account, "player": character, "limit": 100})
    return f"{api_base_url.rstrip('/')}/api/world/dynamic-quests/timeline?{query}"


def dynamic_quest_autoaccept_diagnostics_url(
    api_base_url: str,
    account: str,
    character: str = "",
) -> str:
    query = urllib.parse.urlencode({"account": account, "player": character})
    return f"{api_base_url.rstrip('/')}/api/world/dynamic-quests/autoaccept-diagnostics?{query}"


def fetch_dynamic_quest_progress(
    options: ContinuousSupervisorOptions,
    account: str,
    character: str = "",
) -> dict[str, object]:
    request = urllib.request.Request(
        dynamic_quest_progress_url(options.api_base_url, account, character),
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=max(0.1, options.request_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def fetch_dynamic_quest_timeline(
    options: ContinuousSupervisorOptions,
    account: str,
    character: str = "",
) -> dict[str, object]:
    request = urllib.request.Request(
        dynamic_quest_timeline_url(options.api_base_url, account, character),
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=max(0.1, options.request_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def fetch_dynamic_quest_autoaccept_diagnostics(
    options: ContinuousSupervisorOptions,
    account: str,
    character: str = "",
) -> dict[str, object]:
    request = urllib.request.Request(
        dynamic_quest_autoaccept_diagnostics_url(options.api_base_url, account, character),
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=max(0.1, options.request_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def dynamic_quest_reward_amount(payload: object, quest_id: str) -> tuple[int, int]:
    if not isinstance(payload, dict):
        return 0, 0
    events = payload.get("events", payload.get("Events", []))
    if not isinstance(events, list):
        return 0, 0
    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        if _dict_text(event, "questId", "quest_id", "QuestId") != quest_id:
            continue
        event_type = _dict_text(event, "eventType", "event_type", "EventType").lower()
        if event_type != "quest_reward_amount":
            continue
        detail = _dict_text(event, "detail", "Detail")
        values = {}
        for part in detail.split(";"):
            key, separator, value = part.partition("=")
            if separator:
                values[key.strip().lower()] = value.strip()
        try:
            xp = max(0, int(values.get("xp", "0")))
        except ValueError:
            xp = 0
        try:
            money = max(0, int(values.get("money_copper", "0")))
        except ValueError:
            money = 0
        return xp, money
    return 0, 0


def cancel_dynamic_quest_progress(
    options: ContinuousSupervisorOptions,
    account: str,
    character: str,
    reason: str,
) -> dict[str, object]:
    query_values = {"account": account, "player": character, "reason": reason}
    if options.api_password:
        query_values["password"] = options.api_password
    query = urllib.parse.urlencode(query_values)
    url = f"{options.api_base_url.rstrip('/')}/api/world/dynamic-quests/progress/cancel?{query}"
    request = urllib.request.Request(
        url,
        data=b"",
        headers={"Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=max(0.1, options.request_timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def api_json_request(
    options: ContinuousSupervisorOptions,
    method: str,
    path: str,
    query: dict[str, object] | None = None,
) -> dict[str, object]:
    values = {key: value for key, value in (query or {}).items() if value not in (None, "")}
    if options.api_password and "password" not in values:
        values["password"] = options.api_password
    encoded = urllib.parse.urlencode(values)
    suffix = path if path.startswith("/") else f"/{path}"
    url = f"{options.api_base_url.rstrip('/')}{suffix}" + (f"?{encoded}" if encoded else "")
    request = urllib.request.Request(
        url,
        data=b"" if method.upper() != "GET" else None,
        headers={"Accept": "application/json"},
        method=method.upper(),
    )
    with urllib.request.urlopen(request, timeout=max(0.1, options.request_timeout)) as response:
        raw = response.read().decode("utf-8")
    if not raw:
        return {}
    payload = json.loads(raw)
    return payload if isinstance(payload, dict) else {}


def normalize_dynamic_quest_node_type(value: object) -> str:
    text = str(value or "").strip().lower().replace("_", "")
    aliases = {
        "0": "talk",
        "1": "kill",
        "2": "returntonpc",
        "3": "choice",
        "4": "complete",
        "5": "fail",
        "6": "explore",
        "return": "returntonpc",
    }
    return aliases.get(text, text)


def _dict_int(mapping: dict[str, object], *keys: str) -> int:
    for key in keys:
        if key not in mapping:
            continue
        try:
            return int(mapping[key] or 0)
        except (TypeError, ValueError):
            continue
    return 0


def _dict_text(mapping: dict[str, object], *keys: str) -> str:
    for key in keys:
        if key in mapping:
            return str(mapping[key] or "").strip()
    return ""


def _dict_bool(mapping: dict[str, object], *keys: str) -> bool:
    for key in keys:
        if key not in mapping:
            continue
        value = mapping[key]
        if isinstance(value, bool):
            return value
        return str(value or "").strip().lower() in {"1", "true", "yes", "on"}
    return False


def parse_dynamic_quest_offer_observations(payload: object) -> list[DynamicQuestOfferObservation]:
    if not isinstance(payload, dict):
        return []
    triggers = payload.get("triggers", payload.get("Triggers", []))
    if not isinstance(triggers, list):
        return []
    observations: list[DynamicQuestOfferObservation] = []
    for trigger_item in triggers:
        if not isinstance(trigger_item, dict):
            continue
        trigger = _dict_text(trigger_item, "trigger", "Trigger")
        candidates = trigger_item.get("candidates", trigger_item.get("Candidates", []))
        if not isinstance(candidates, list):
            continue
        for candidate in candidates:
            if not isinstance(candidate, dict):
                continue
            raw_scopes = candidate.get("startScopes", candidate.get("start_scopes", []))
            scopes: list[DynamicQuestStartScope] = []
            if isinstance(raw_scopes, list):
                for raw_scope in raw_scopes:
                    if not isinstance(raw_scope, dict):
                        continue
                    scopes.append(
                        DynamicQuestStartScope(
                            region=_dict_int(raw_scope, "regionId", "region_id", "RegionId"),
                            x=_dict_int(raw_scope, "x", "X"),
                            y=_dict_int(raw_scope, "y", "Y"),
                            z=_dict_int(raw_scope, "z", "Z"),
                            radius=_dict_int(raw_scope, "radius", "Radius"),
                            location_name=_dict_text(
                                raw_scope,
                                "locationName",
                                "location_name",
                                "LocationName",
                            ),
                        )
                    )
            blocked = candidate.get(
                "offerBlockedReasons",
                candidate.get("offer_blocked_reasons", []),
            )
            tags = candidate.get("tags", candidate.get("Tags", []))
            observations.append(
                DynamicQuestOfferObservation(
                    quest_id=_dict_text(candidate, "questId", "quest_id", "QuestId"),
                    title=_dict_text(candidate, "title", "Title"),
                    target_name=_dict_text(candidate, "targetName", "target_name", "TargetName"),
                    min_level=_dict_int(candidate, "minLevel", "min_level", "MinLevel"),
                    max_level=_dict_int(candidate, "maxLevel", "max_level", "MaxLevel"),
                    trigger=trigger,
                    trigger_matches=_dict_bool(
                        candidate,
                        "triggerMatches",
                        "trigger_matches",
                        "TriggerMatches",
                    ),
                    player_level_matches=_dict_bool(
                        candidate,
                        "playerLevelMatches",
                        "player_level_matches",
                        "PlayerLevelMatches",
                    ),
                    has_completed=_dict_bool(candidate, "hasCompleted", "has_completed"),
                    has_completed_story_family=_dict_bool(
                        candidate,
                        "hasCompletedStoryFamily",
                        "has_completed_story_family",
                    ),
                    has_progress=_dict_bool(candidate, "hasProgress", "has_progress"),
                    has_active_story_family=_dict_bool(
                        candidate,
                        "hasActiveStoryFamily",
                        "has_active_story_family",
                    ),
                    inside_start_scope=_dict_bool(
                        candidate,
                        "insideStartScope",
                        "inside_start_scope",
                    ),
                    blocked_reasons=tuple(
                        str(value or "").strip()
                        for value in (blocked if isinstance(blocked, list) else [])
                        if str(value or "").strip()
                    ),
                    start_scopes=tuple(scopes),
                    tags=tuple(
                        str(value or "").strip()
                        for value in (tags if isinstance(tags, list) else [])
                        if str(value or "").strip()
                    ),
                )
            )
    return [item for item in observations if item.quest_id]


def parse_dynamic_quest_observations(payload: object) -> list[DynamicQuestObservation]:
    if not isinstance(payload, dict):
        return []
    active = payload.get("active", payload.get("Active", []))
    if not isinstance(active, list):
        return []
    observations = []
    for item in active:
        if not isinstance(item, dict):
            continue
        objective = item.get("currentObjective", item.get("current_objective", {}))
        if not isinstance(objective, dict):
            objective = {}
        observations.append(
            DynamicQuestObservation(
                quest_id=_dict_text(item, "questId", "quest_id", "QuestId"),
                title=_dict_text(item, "title", "Title"),
                node_id=_dict_text(item, "currentNodeId", "current_node_id", "CurrentNodeId"),
                node_type=normalize_dynamic_quest_node_type(
                    item.get("currentNodeType", item.get("current_node_type", ""))
                ),
                target_name=_dict_text(
                    objective,
                    "targetName",
                    "target_name",
                    "TargetName",
                )
                or _dict_text(item, "targetName", "target_name", "TargetName"),
                target_count=_dict_int(
                    objective,
                    "targetCount",
                    "target_count",
                    "TargetCount",
                )
                or _dict_int(item, "targetCount", "target_count", "TargetCount"),
                current_count=_dict_int(item, "count", "currentCount", "current_count", "Count"),
                min_level=_dict_int(objective, "minLevel", "min_level", "MinLevel"),
                max_level=_dict_int(objective, "maxLevel", "max_level", "MaxLevel"),
                region=_dict_int(objective, "regionId", "region_id", "RegionId"),
                x=_dict_int(objective, "x", "X"),
                y=_dict_int(objective, "y", "Y"),
                z=_dict_int(objective, "z", "Z"),
                radius=_dict_int(objective, "radius", "Radius"),
                npc_name=_dict_text(objective, "npcName", "npc_name", "NpcName"),
                npc_internal_id=_dict_text(
                    objective,
                    "npcInternalId",
                    "npc_internal_id",
                    "NpcInternalId",
                ),
                stalled_reason=_dict_text(item, "stalledReason", "stalled_reason", "StalledReason"),
                failed=bool(item.get("failed", item.get("Failed", False))),
                elapsed_seconds=_dict_int(
                    item,
                    "currentNodeElapsedSeconds",
                    "current_node_elapsed_seconds",
                    "CurrentNodeElapsedSeconds",
                ),
            )
        )
    return [item for item in observations if item.quest_id]


def completed_dynamic_quest_ids(payload: object) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    values = payload.get("completedQuestIds", payload.get("completed_quest_ids", []))
    if not isinstance(values, list):
        return set()
    return {str(value or "").strip() for value in values if str(value or "").strip()}


def dynamic_quest_progress_timeout(
    observation: DynamicQuestObservation,
    options: ContinuousSupervisorOptions,
) -> float:
    configured = max(15.0, float(options.dynamic_quest_timeout))
    if observation.node_type == "explore":
        return min(configured, 60.0)
    if observation.node_type == "kill":
        target_count = max(1, observation.target_count - observation.current_count)
        return min(configured, 60.0 + target_count * 30.0)
    return configured


def dynamic_quest_difficulty_reasons(
    observation: DynamicQuestObservation,
    snapshot: ProgressionSnapshot,
    options: ContinuousSupervisorOptions,
) -> list[str]:
    reasons: list[str] = []
    if observation.failed or observation.node_type == "fail":
        reasons.append("quest_failed_node")
    expected_wait_states = {
        "complete",
        "target_reached_waiting_for_transition",
        "waiting_for_kill_credit",
        "waiting_for_location",
        "waiting_for_story_transition",
    }
    if observation.stalled_reason and observation.stalled_reason.lower() not in expected_wait_states:
        reasons.append(f"stalled:{observation.stalled_reason}")
    if observation.elapsed_seconds > dynamic_quest_progress_timeout(observation, options):
        reasons.append("node_timeout")
    if observation.node_type == "kill":
        if not observation.target_name:
            reasons.append("missing_target_name")
        if observation.target_count > options.dynamic_quest_max_target_count:
            reasons.append(
                f"target_count:{observation.target_count}>{options.dynamic_quest_max_target_count}"
            )
        if observation.min_level > snapshot.level + options.dynamic_quest_max_level_delta:
            reasons.append(
                f"target_min_level:{observation.min_level}>{snapshot.level}+{options.dynamic_quest_max_level_delta}"
            )
        if observation.region <= 0 or (observation.x == 0 and observation.y == 0):
            reasons.append("missing_target_location")
        elif snapshot.region > 0 and observation.region != snapshot.region:
            reasons.append(f"cross_region:{snapshot.region}->{observation.region}")
        else:
            distance = math.hypot(observation.x - snapshot.x, observation.y - snapshot.y)
            if distance > options.dynamic_quest_max_distance:
                reasons.append(
                    f"target_distance:{distance:.0f}>{options.dynamic_quest_max_distance:.0f}"
                )
    return reasons


DYNAMIC_QUEST_TIMELINE_FIELDS = [
    "timestamp_utc",
    "case",
    "account",
    "character",
    "level",
    "quest_id",
    "title",
    "node_id",
    "node_type",
    "target_name",
    "target_count",
    "current_count",
    "outcome",
    "reason",
    "elapsed_seconds",
    "reward_xp",
    "reward_money_copper",
    "experience_during_quest",
    "money_during_quest_copper",
]


def write_dynamic_quest_timeline_row(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DYNAMIC_QUEST_TIMELINE_FIELDS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def fetch_progression_payload(
    api_base_url: str,
    account: str,
    *,
    character: str = "",
    timeout: float = 3.0,
) -> dict[str, object]:
    request = urllib.request.Request(
        usable_api_url(api_base_url, account, character),
        headers={"Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=max(0.1, timeout)) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("combat usable API returned a non-object payload")
    return payload


def fetch_all_progression_payloads(
    options: ContinuousSupervisorOptions,
    accounts: dict[str, str],
) -> dict[str, dict[str, object]]:
    return {
        account: fetch_progression_payload(
            options.api_base_url,
            account,
            character=character,
            timeout=options.request_timeout,
        )
        for account, character in accounts.items()
    }


def wait_for_online_payloads(
    process: subprocess.Popen[object],
    options: ContinuousSupervisorOptions,
    accounts: dict[str, str],
) -> dict[str, dict[str, object]]:
    deadline = time.monotonic() + max(1.0, options.online_timeout)
    last_error = ""
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"behavior process exited before API online: rc={process.returncode}")
        try:
            payloads = fetch_all_progression_payloads(options, accounts)
            if len(payloads) == len(accounts):
                return payloads
        except Exception as exc:
            last_error = str(exc)
        time.sleep(max(0.1, options.poll_interval))
    raise TimeoutError(f"dummy accounts did not become API-visible: {last_error}")


def read_statuses(
    status_directory: Path,
    request_id: str,
    accounts: Iterable[str],
) -> dict[str, dict[str, object]] | None:
    rows: dict[str, dict[str, object]] = {}
    for account in accounts:
        path = status_path(status_directory, request_id, account)
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or payload.get("requestId") != request_id:
            return None
        rows[account] = payload
    return rows


def wait_for_statuses(
    process: subprocess.Popen[object],
    status_directory: Path,
    request_id: str,
    accounts: Iterable[str],
    *,
    timeout: float,
    poll_interval: float,
) -> dict[str, dict[str, object]]:
    account_list = list(accounts)
    deadline = time.monotonic() + max(1.0, timeout)
    while time.monotonic() < deadline:
        statuses = read_statuses(status_directory, request_id, account_list)
        if statuses is not None:
            return statuses
        if process.poll() is not None:
            raise RuntimeError(f"behavior process exited while servicing {request_id}: rc={process.returncode}")
        time.sleep(max(0.1, poll_interval))
    missing = [
        account
        for account in account_list
        if not status_path(status_directory, request_id, account).exists()
    ]
    raise TimeoutError(f"progression service timeout request={request_id} missing={','.join(missing)}")


def item_identity(item: ProgressionItem) -> tuple[str, str, int]:
    return item.unique_template_id or item.template_id, item.name, item.slot


def acquired_inventory_items(
    before: ProgressionSnapshot,
    after: ProgressionSnapshot,
) -> list[dict[str, object]]:
    before_counts: dict[tuple[str, str, int], int] = {}
    for item in before.inventory:
        before_counts[item_identity(item)] = before_counts.get(item_identity(item), 0) + item.count
    rows = []
    for item in after.inventory:
        gained = item.count - before_counts.get(item_identity(item), 0)
        if gained <= 0:
            continue
        rows.append(
            {
                "slot": item.slot,
                "templateId": item.unique_template_id or item.template_id,
                "name": item.name,
                "count": gained,
                "level": item.level,
                "objectType": item.object_type,
                "itemType": item.item_type,
                "quality": item.quality,
            }
        )
    return rows


CONTINUOUS_TIMELINE_FIELDS = [
    "timestamp_utc",
    "request_id",
    "case",
    "mode",
    "realm",
    "party_size",
    "account",
    "character",
    "level_hunt_start",
    "level_service_start",
    "level_service_end",
    "level_jump",
    "xp_hunt_delta",
    "experience_into_level_after",
    "mob_coin_copper",
    "sale_proceeds_expected_copper",
    "purchase_cost_expected_copper",
    "service_money_delta_copper",
    "service_unexplained_copper",
    "money_end_copper",
    "inventory_hunt_delta",
    "acquired_items",
    "specialty_points_before",
    "specialty_points_after",
    "spec_gains",
    "usable_skills_before",
    "usable_skills_after",
    "usable_spells_before",
    "usable_spells_after",
    "training_commands",
    "service_ok",
    "service_errors",
    "used_player_reset",
    "is_companion",
    "companion_role",
    "data_integrity_flags",
    "anomaly_codes",
]


def write_timeline_row(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONTINUOUS_TIMELINE_FIELDS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def request_quit(live_control_path: Path, revision: str) -> None:
    atomic_write_json(
        live_control_path,
        {
            "revision": revision,
            "commands": ["/quit"],
            "quit_after_sit_seconds": 1.0,
        },
    )


def checkpoint_service_to_hunt_payload(
    payload: dict[str, object],
    *,
    request_id: str,
) -> dict[str, object]:
    service = payload.get("progressionService", {})
    if not isinstance(service, dict):
        raise ValueError("progressionService is missing from checkpoint payload")
    hunt = {
        key: value
        for key, value in service.items()
        if key
        in {
            "level",
            "huntLocation",
            "preferTargetName",
            "requireTargetName",
            "avoidTargetName",
            "requireTargetNameExact",
            "minTargetLevel",
            "maxTargetLevel",
            "targetHomeMaxDistance",
            "combatHomeLeashDistance",
            "requiredTargetHomeHuntDistance",
            "members",
        }
    }
    hunt["requestId"] = request_id
    return {"revision": request_id, "progressionHunt": hunt}


def build_dynamic_quest_hunt_payload(
    observation: DynamicQuestObservation,
    snapshots: dict[str, ProgressionSnapshot],
    *,
    request_id: str,
) -> dict[str, object]:
    player_level = min(snapshot.level for snapshot in snapshots.values())
    min_target_level = max(1, observation.min_level or max(1, player_level - 2))
    max_target_level = observation.max_level or player_level + 2
    max_target_level = max(min_target_level, min(max_target_level, player_level + 2))
    home_distance = max(2500.0, float(max(0, observation.radius)) * 3.0)
    members = {
        account: {"level": snapshot.level}
        for account, snapshot in snapshots.items()
    }
    return {
        "revision": request_id,
        "progressionHunt": {
            "requestId": request_id,
            "level": player_level,
            "huntLocation": {
                "region": observation.region,
                "x": observation.x,
                "y": observation.y,
                "z": observation.z,
            },
            "preferTargetName": observation.target_name,
            "requireTargetName": observation.target_name,
            "requireTargetNameExact": False,
            "minTargetLevel": min_target_level,
            "maxTargetLevel": max_target_level,
            "targetHomeMaxDistance": home_distance,
            "combatHomeLeashDistance": max(home_distance, 3200.0),
            "requiredTargetHomeHuntDistance": max(500.0, float(max(0, observation.radius))),
            "members": members,
        },
    }


def dynamic_quest_offer_matches_region(
    offer: DynamicQuestOfferObservation,
    region: int,
) -> bool:
    if any(scope.region in {0, region} for scope in offer.start_scopes):
        return True
    return f"region:{region}" in {tag.lower() for tag in offer.tags}


def select_dynamic_quest_start_scope(
    offer: DynamicQuestOfferObservation,
    snapshot: ProgressionSnapshot,
) -> DynamicQuestStartScope | None:
    candidates = [
        scope
        for scope in offer.start_scopes
        if scope.region in {0, snapshot.region} and (scope.x != 0 or scope.y != 0)
    ]
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda scope: math.hypot(scope.x - snapshot.x, scope.y - snapshot.y),
    )


def snapshot_inside_dynamic_quest_start_scope(
    snapshot: ProgressionSnapshot,
    scope: DynamicQuestStartScope,
) -> bool:
    if scope.radius <= 0 or scope.region not in {0, snapshot.region}:
        return False
    return math.hypot(scope.x - snapshot.x, scope.y - snapshot.y) <= scope.radius


def build_dynamic_quest_probe_payload(
    quest_id: str,
    region: int,
    x: int,
    y: int,
    z: int,
    radius: int,
    snapshots: dict[str, ProgressionSnapshot],
    *,
    request_id: str,
    probe_kind: str,
) -> dict[str, object]:
    player_level = min(snapshot.level for snapshot in snapshots.values())
    probe_name = f"__dynamic_quest_{probe_kind}_probe__:{quest_id}"
    return {
        "revision": request_id,
        "progressionHunt": {
            "requestId": request_id,
            "level": player_level,
            "huntLocation": {
                "region": region,
                "x": x,
                "y": y,
                "z": z,
            },
            "preferTargetName": probe_name,
            "requireTargetName": probe_name,
            "requireTargetNameExact": True,
            "minTargetLevel": 0,
            "maxTargetLevel": 0,
            "targetHomeMaxDistance": max(500.0, float(radius)),
            "combatHomeLeashDistance": max(1200.0, float(radius) * 2.0),
            "requiredTargetHomeHuntDistance": max(100.0, float(radius)),
        },
    }


def build_dynamic_quest_start_scope_payload(
    offer: DynamicQuestOfferObservation,
    scope: DynamicQuestStartScope,
    snapshots: dict[str, ProgressionSnapshot],
    *,
    request_id: str,
) -> dict[str, object]:
    return build_dynamic_quest_probe_payload(
        offer.quest_id,
        scope.region,
        scope.x,
        scope.y,
        scope.z,
        scope.radius,
        snapshots,
        request_id=request_id,
        probe_kind="scope",
    )


def build_dynamic_quest_explore_payload(
    observation: DynamicQuestObservation,
    snapshots: dict[str, ProgressionSnapshot],
    *,
    request_id: str,
) -> dict[str, object]:
    return build_dynamic_quest_probe_payload(
        observation.quest_id,
        observation.region,
        observation.x,
        observation.y,
        observation.z,
        observation.radius,
        snapshots,
        request_id=request_id,
        probe_kind="explore",
    )


class DynamicQuestCoordinator:
    def __init__(
        self,
        *,
        options: ContinuousSupervisorOptions,
        accounts: dict[str, str],
        case_name: str,
        party_size: int,
        live_control_path: Path,
        timeline_path: Path,
    ) -> None:
        self.options = options
        self.accounts = accounts
        self.case_name = case_name
        self.party_size = party_size
        self.live_control_path = live_control_path
        self.timeline_path = timeline_path
        self.tracks: dict[str, DynamicQuestTrack] = {}
        self.skipped_quest_ids: dict[str, set[str]] = {account: set() for account in accounts}
        self.regular_hunt_payload: dict[str, object] | None = None
        self.routed_signature: tuple[object, ...] | None = None
        self.last_regular_hunt_reason = ""
        self.reported_anomalies: set[tuple[str, str, str]] = set()
        self.reported_offer_outcomes: set[tuple[str, int, str, str]] = set()
        self.offer_probe_started_at: dict[tuple[str, str], float] = {}
        self.offer_route_started_at: dict[tuple[str, str], float] = {}
        self.revision = 0
        self.next_poll_at = 0.0

    def set_regular_hunt_payload(self, payload: dict[str, object]) -> None:
        self.regular_hunt_payload = payload
        self.routed_signature = None
        self.last_regular_hunt_reason = ""

    def next_request_id(self, suffix: str) -> str:
        self.revision += 1
        return f"{self.case_name}-quest-{self.revision:04d}-{safe_status_component(suffix)}"

    def write_event(
        self,
        account: str,
        snapshot: ProgressionSnapshot,
        observation: DynamicQuestObservation,
        *,
        outcome: str,
        reason: str = "",
        track: DynamicQuestTrack | None = None,
        reward_xp: int = 0,
        reward_money_copper: int = 0,
    ) -> None:
        write_dynamic_quest_timeline_row(
            self.timeline_path,
            {
                "timestamp_utc": utc_now(),
                "case": self.case_name,
                "account": account,
                "character": snapshot.name,
                "level": snapshot.level,
                "quest_id": observation.quest_id,
                "title": observation.title,
                "node_id": observation.node_id,
                "node_type": observation.node_type,
                "target_name": observation.target_name,
                "target_count": observation.target_count,
                "current_count": observation.current_count,
                "outcome": outcome,
                "reason": reason,
                "elapsed_seconds": 0 if track is None else round(time.monotonic() - track.started_at, 3),
                "reward_xp": reward_xp,
                "reward_money_copper": reward_money_copper,
                "experience_during_quest": 0
                if track is None
                else snapshot.experience - track.start_experience,
                "money_during_quest_copper": 0
                if track is None
                else snapshot.money_copper - track.start_money_copper,
            },
        )

    def write_offer_outcome(
        self,
        offer: DynamicQuestOfferObservation | None,
        snapshots: dict[str, ProgressionSnapshot],
        *,
        outcome: str,
        reason: str,
        scope: DynamicQuestStartScope | None = None,
    ) -> None:
        for account, snapshot in snapshots.items():
            quest_id = offer.quest_id if offer is not None else ""
            key = (account, snapshot.level, quest_id, outcome)
            if key in self.reported_offer_outcomes:
                continue
            self.reported_offer_outcomes.add(key)
            selected_scope = scope or DynamicQuestStartScope(
                region=snapshot.region,
                x=snapshot.x,
                y=snapshot.y,
                z=snapshot.z,
                radius=0,
            )
            observation = DynamicQuestObservation(
                quest_id=quest_id,
                title=offer.title if offer is not None else "",
                node_id="offer",
                node_type="offer",
                target_name=offer.target_name if offer is not None else "",
                target_count=0,
                current_count=0,
                min_level=offer.min_level if offer is not None else 0,
                max_level=offer.max_level if offer is not None else 0,
                region=selected_scope.region,
                x=selected_scope.x,
                y=selected_scope.y,
                z=selected_scope.z,
                radius=selected_scope.radius,
                npc_name="",
                npc_internal_id="",
                stalled_reason="",
                failed=False,
                elapsed_seconds=0,
            )
            self.write_event(
                account,
                snapshot,
                observation,
                outcome=outcome,
                reason=reason,
            )

    def handle_no_active_offer(
        self,
        diagnostics: dict[str, object],
        snapshots: dict[str, ProgressionSnapshot],
        now: float,
    ) -> list[ProgressionAnomaly]:
        leader_account = next(iter(self.accounts))
        leader_snapshot = snapshots[leader_account]
        offers = parse_dynamic_quest_offer_observations(diagnostics)
        realm_offers = [
            offer
            for offer in offers
            if dynamic_quest_offer_matches_region(offer, leader_snapshot.region)
        ]
        eligible: list[DynamicQuestOfferObservation] = []
        seen_eligible: set[str] = set()
        for offer in realm_offers:
            if offer.quest_id in seen_eligible:
                continue
            blockers = set(offer.blocked_reasons)
            if (
                offer.trigger_matches
                and offer.player_level_matches
                and not offer.has_completed
                and not offer.has_completed_story_family
                and not offer.has_progress
                and not offer.has_active_story_family
                and blockers.issubset({"outside_start_scope"})
            ):
                eligible.append(offer)
                seen_eligible.add(offer.quest_id)

        if eligible:
            offer = eligible[0]
            scope = select_dynamic_quest_start_scope(offer, leader_snapshot)
            if scope is None:
                anomaly = self.anomaly_once(
                    "dynamic_quest_start_scope_missing",
                    "error",
                    "An eligible auto-accept quest did not expose a usable start scope.",
                    {"account": leader_account, "questId": offer.quest_id},
                )
                return [anomaly] if anomaly is not None else []

            probe_key = (leader_account, offer.quest_id)
            route_signature = (
                "offer",
                offer.quest_id,
                scope.region,
                scope.x,
                scope.y,
            )
            if route_signature != self.routed_signature:
                request_id = self.next_request_id(f"offer-{offer.quest_id}")
                atomic_write_json(
                    self.live_control_path,
                    build_dynamic_quest_start_scope_payload(
                        offer,
                        scope,
                        snapshots,
                        request_id=request_id,
                    ),
                )
                self.routed_signature = route_signature
                self.last_regular_hunt_reason = ""
                self.offer_probe_started_at.clear()
                self.offer_route_started_at.clear()
                self.offer_route_started_at[probe_key] = now
                self.write_offer_outcome(
                    offer,
                    snapshots,
                    outcome="offer_routed",
                    reason="inside_start_scope" if offer.inside_start_scope else "outside_start_scope",
                    scope=scope,
                )

            all_inside_scope = all(
                snapshot_inside_dynamic_quest_start_scope(snapshot, scope)
                for snapshot in snapshots.values()
            )
            if not all_inside_scope:
                route_started_at = self.offer_route_started_at.setdefault(probe_key, now)
                route_timeout = max(
                    60.0,
                    self.options.dynamic_quest_poll_interval * 10.0,
                )
                if now - route_started_at > route_timeout:
                    anomaly = self.anomaly_once(
                        "dynamic_quest_offer_route_timeout",
                        "error",
                        "The party did not reach an eligible auto-accept quest scope.",
                        {
                            "account": leader_account,
                            "questId": offer.quest_id,
                            "seconds": round(now - route_started_at, 3),
                        },
                    )
                    return [anomaly] if anomaly is not None else []
                return []

            started_at = self.offer_probe_started_at.setdefault(probe_key, now)
            activation_timeout = min(
                60.0,
                max(15.0, self.options.dynamic_quest_poll_interval * 5.0),
            )
            if now - started_at > activation_timeout:
                anomaly = self.anomaly_once(
                    "dynamic_quest_offer_activation_timeout",
                    "error",
                    "The party reached an eligible auto-accept quest scope but no quest became active.",
                    {
                        "account": leader_account,
                        "questId": offer.quest_id,
                        "seconds": round(now - started_at, 3),
                    },
                )
                return [anomaly] if anomaly is not None else []
            return []

        unique_realm_offers: dict[str, DynamicQuestOfferObservation] = {}
        for offer in realm_offers:
            unique_realm_offers.setdefault(offer.quest_id, offer)
        candidates = list(unique_realm_offers.values())
        level_mismatches = [offer for offer in candidates if not offer.player_level_matches]
        if level_mismatches:
            offer = min(
                level_mismatches,
                key=lambda row: min(
                    abs(leader_snapshot.level - row.min_level),
                    abs(leader_snapshot.level - row.max_level),
                ),
            )
            ranges = sorted({f"{row.min_level}-{row.max_level}" for row in level_mismatches})
            outcome = "not_eligible"
            reason = (
                f"player_level_mismatch:level={leader_snapshot.level};"
                f"available_ranges={','.join(ranges)}"
            )
        elif candidates:
            offer = candidates[0]
            outcome = "not_available"
            reasons = sorted({reason for row in candidates for reason in row.blocked_reasons})
            reason = ";".join(reasons) or "completed_or_active_story_family"
        else:
            offer = None
            outcome = "not_available"
            reason = f"no_autoaccept_candidate_for_region:{leader_snapshot.region}"

        self.offer_probe_started_at.clear()
        self.offer_route_started_at.clear()
        self.write_offer_outcome(
            offer,
            snapshots,
            outcome=outcome,
            reason=reason,
        )
        if self.routed_signature and self.routed_signature[0] == "offer":
            self.send_regular_hunt(f"{outcome}-level-{leader_snapshot.level}")
        return []

    def send_regular_hunt(self, reason: str) -> None:
        if self.regular_hunt_payload is None:
            return
        if reason == self.last_regular_hunt_reason:
            return
        request_id = self.next_request_id(f"regular-{reason}")
        payload = json.loads(json.dumps(self.regular_hunt_payload))
        payload["revision"] = request_id
        hunt = payload.get("progressionHunt", {})
        if isinstance(hunt, dict):
            hunt["requestId"] = request_id
        atomic_write_json(self.live_control_path, payload)
        self.routed_signature = None
        self.last_regular_hunt_reason = reason

    def anomaly_once(
        self,
        code: str,
        severity: str,
        message: str,
        details: dict[str, object],
    ) -> ProgressionAnomaly | None:
        account = str(details.get("account", "") or "")
        quest_id = str(details.get("questId", "") or "")
        key = (code, account, quest_id)
        if key in self.reported_anomalies:
            return None
        self.reported_anomalies.add(key)
        return ProgressionAnomaly(code, severity, message, details)

    def cancel_for_difficulty(
        self,
        account: str,
        snapshot: ProgressionSnapshot,
        observation: DynamicQuestObservation,
        reasons: list[str],
    ) -> None:
        reason = "continuous_growth_difficulty_skip:" + ",".join(reasons)
        cancel_result = cancel_dynamic_quest_progress(
            self.options,
            account,
            self.accounts.get(account, ""),
            reason,
        )
        if _dict_int(cancel_result, "cancelled", "Cancelled") < 1:
            raise RuntimeError(
                f"dynamic quest cancel returned no cancelled progress for {observation.quest_id}"
            )
        self.skipped_quest_ids.setdefault(account, set()).add(observation.quest_id)
        track = self.tracks.get(account)
        if track is not None:
            track.skipped = True
        self.write_event(
            account,
            snapshot,
            observation,
            outcome="difficulty_skip",
            reason=";".join(reasons),
            track=track,
        )

    def poll(self, snapshots: dict[str, ProgressionSnapshot]) -> list[ProgressionAnomaly]:
        if not self.options.dynamic_quests:
            return []
        anomalies: list[ProgressionAnomaly] = []
        progress_payloads: dict[str, dict[str, object]] = {}
        observations: dict[str, DynamicQuestObservation] = {}
        now = time.monotonic()
        if now < self.next_poll_at:
            return []
        self.next_poll_at = now + max(0.5, self.options.dynamic_quest_poll_interval)
        for account, character in self.accounts.items():
            try:
                progress = fetch_dynamic_quest_progress(self.options, account, character)
            except Exception as exc:
                anomaly = self.anomaly_once(
                        "dynamic_quest_progress_api_error",
                        "error",
                        "Dynamic quest progress could not be read.",
                        {"account": account, "error": str(exc)},
                )
                if anomaly is not None:
                    anomalies.append(anomaly)
                continue
            if progress.get("enabled", progress.get("Enabled", True)) is False:
                anomaly = self.anomaly_once(
                    "dynamic_quests_disabled",
                    "error",
                    "Dynamic quests are disabled while the progression audit requires them.",
                    {"account": account},
                )
                if anomaly is not None:
                    anomalies.append(anomaly)
                continue
            progress_payloads[account] = progress
            active = parse_dynamic_quest_observations(progress)
            if len(active) > 1:
                anomaly = self.anomaly_once(
                        "multiple_active_dynamic_quests",
                        "warning",
                        "Only the oldest active dynamic quest is routed by continuous growth.",
                        {"account": account, "count": len(active)},
                )
                if anomaly is not None:
                    anomalies.append(anomaly)
            if active:
                observations[account] = active[0]

        if observations:
            self.offer_probe_started_at.clear()
            self.offer_route_started_at.clear()
        elif not self.tracks and len(progress_payloads) == len(self.accounts):
            leader_account = next(iter(self.accounts))
            try:
                diagnostics = fetch_dynamic_quest_autoaccept_diagnostics(
                    self.options,
                    leader_account,
                    self.accounts.get(leader_account, ""),
                )
            except Exception as exc:
                anomaly = self.anomaly_once(
                    "dynamic_quest_diagnostics_api_error",
                    "error",
                    "Dynamic quest auto-accept diagnostics could not be read.",
                    {"account": leader_account, "error": str(exc)},
                )
                if anomaly is not None:
                    anomalies.append(anomaly)
            else:
                if diagnostics.get("enabled", diagnostics.get("Enabled", True)) is False:
                    anomaly = self.anomaly_once(
                        "dynamic_quests_disabled",
                        "error",
                        "Dynamic quests are disabled while the progression audit requires them.",
                        {"account": leader_account},
                    )
                    if anomaly is not None:
                        anomalies.append(anomaly)
                else:
                    anomalies.extend(
                        self.handle_no_active_offer(
                            diagnostics,
                            snapshots,
                            now,
                        )
                    )

        completed_any = False
        for account, track in list(self.tracks.items()):
            observation = observations.get(account)
            if observation is not None and observation.quest_id == track.quest_id:
                if observation.signature != track.last_signature:
                    track.last_signature = observation.signature
                    track.last_progress_at = now
                    self.write_event(
                        account,
                        snapshots[account],
                        observation,
                        outcome="progress",
                        track=track,
                    )
                continue
            completed = track.quest_id in completed_dynamic_quest_ids(progress_payloads.get(account, {}))
            terminal = DynamicQuestObservation(
                quest_id=track.quest_id,
                title=track.title,
                node_id="complete" if completed else "ended",
                node_type="complete" if completed else "ended",
                target_name="",
                target_count=0,
                current_count=0,
                min_level=0,
                max_level=0,
                region=0,
                x=0,
                y=0,
                z=0,
                radius=0,
                npc_name="",
                npc_internal_id="",
                stalled_reason="",
                failed=False,
                elapsed_seconds=0,
            )
            if not track.skipped:
                reward_xp = 0
                reward_money = 0
                if completed:
                    try:
                        reward_xp, reward_money = dynamic_quest_reward_amount(
                            fetch_dynamic_quest_timeline(
                                self.options,
                                account,
                                self.accounts.get(account, ""),
                            ),
                            track.quest_id,
                        )
                    except Exception:
                        reward_xp, reward_money = 0, 0
                self.write_event(
                    account,
                    snapshots[account],
                    terminal,
                    outcome="completed" if completed else "ended_without_reward",
                    track=track,
                    reward_xp=reward_xp,
                    reward_money_copper=reward_money,
                )
            completed_any = completed_any or completed
            del self.tracks[account]
        if completed_any:
            self.send_regular_hunt("quest-complete")

        for account, observation in observations.items():
            if observation.quest_id in self.skipped_quest_ids.get(account, set()):
                continue
            snapshot = snapshots[account]
            track = self.tracks.get(account)
            if track is None or track.quest_id != observation.quest_id:
                track = DynamicQuestTrack(
                    quest_id=observation.quest_id,
                    title=observation.title,
                    started_at=now,
                    last_progress_at=now,
                    last_signature=observation.signature,
                    start_experience=snapshot.experience,
                    start_money_copper=snapshot.money_copper,
                )
                self.tracks[account] = track
                self.write_event(account, snapshot, observation, outcome="accepted", track=track)
            reasons = dynamic_quest_difficulty_reasons(observation, snapshot, self.options)
            if now - track.last_progress_at > dynamic_quest_progress_timeout(
                observation,
                self.options,
            ):
                reasons.append("progress_timeout")
            if reasons:
                try:
                    self.cancel_for_difficulty(account, snapshot, observation, reasons)
                except Exception as exc:
                    anomaly = self.anomaly_once(
                            "dynamic_quest_cancel_failed",
                            "error",
                            "A difficult dynamic quest could not be cancelled.",
                            {"account": account, "questId": observation.quest_id, "error": str(exc)},
                    )
                    if anomaly is not None:
                        anomalies.append(anomaly)

        feasible_kills = {
            account: observation
            for account, observation in observations.items()
            if observation.node_type == "kill"
            and observation.quest_id not in self.skipped_quest_ids.get(account, set())
            and not dynamic_quest_difficulty_reasons(observation, snapshots[account], self.options)
        }
        feasible_explores = {
            account: observation
            for account, observation in observations.items()
            if observation.node_type == "explore"
            and observation.quest_id not in self.skipped_quest_ids.get(account, set())
            and not dynamic_quest_difficulty_reasons(observation, snapshots[account], self.options)
        }
        if feasible_kills:
            objective_keys = {
                (
                    observation.target_name.lower(),
                    observation.region,
                    observation.x,
                    observation.y,
                )
                for observation in feasible_kills.values()
            }
            if self.party_size > 1 and len(objective_keys) > 1:
                for account, observation in feasible_kills.items():
                    try:
                        self.cancel_for_difficulty(
                            account,
                            snapshots[account],
                            observation,
                            ["party_quest_objective_mismatch"],
                        )
                    except Exception as exc:
                        anomaly = self.anomaly_once(
                                "dynamic_quest_cancel_failed",
                                "error",
                                "Mismatched party quests could not be cancelled.",
                                {"account": account, "questId": observation.quest_id, "error": str(exc)},
                        )
                        if anomaly is not None:
                            anomalies.append(anomaly)
                self.send_regular_hunt("party-quest-mismatch")
            else:
                leader_account = next(account for account in self.accounts if account in feasible_kills)
                observation = feasible_kills[leader_account]
                route_signature = (
                    observation.quest_id,
                    observation.node_id,
                    observation.target_name,
                    observation.region,
                    observation.x,
                    observation.y,
                )
                if route_signature != self.routed_signature:
                    request_id = self.next_request_id(f"route-{observation.quest_id}")
                    atomic_write_json(
                        self.live_control_path,
                        build_dynamic_quest_hunt_payload(
                            observation,
                            snapshots,
                            request_id=request_id,
                        ),
                    )
                    self.routed_signature = route_signature
                    self.last_regular_hunt_reason = ""
                    for account, account_observation in feasible_kills.items():
                        self.write_event(
                            account,
                            snapshots[account],
                            account_observation,
                            outcome="routed",
                            track=self.tracks.get(account),
                        )
        elif feasible_explores:
            objective_keys = {
                (
                    observation.region,
                    observation.x,
                    observation.y,
                    observation.radius,
                )
                for observation in feasible_explores.values()
            }
            if self.party_size > 1 and len(objective_keys) > 1:
                for account, observation in feasible_explores.items():
                    try:
                        self.cancel_for_difficulty(
                            account,
                            snapshots[account],
                            observation,
                            ["party_quest_objective_mismatch"],
                        )
                    except Exception as exc:
                        anomaly = self.anomaly_once(
                            "dynamic_quest_cancel_failed",
                            "error",
                            "Mismatched party explore quests could not be cancelled.",
                            {"account": account, "questId": observation.quest_id, "error": str(exc)},
                        )
                        if anomaly is not None:
                            anomalies.append(anomaly)
                self.send_regular_hunt("party-explore-mismatch")
            else:
                leader_account = next(account for account in self.accounts if account in feasible_explores)
                observation = feasible_explores[leader_account]
                route_signature = (
                    "explore",
                    observation.quest_id,
                    observation.node_id,
                    observation.region,
                    observation.x,
                    observation.y,
                )
                if route_signature != self.routed_signature:
                    request_id = self.next_request_id(f"explore-{observation.quest_id}")
                    atomic_write_json(
                        self.live_control_path,
                        build_dynamic_quest_explore_payload(
                            observation,
                            snapshots,
                            request_id=request_id,
                        ),
                    )
                    self.routed_signature = route_signature
                    self.last_regular_hunt_reason = ""
                    for account, account_observation in feasible_explores.items():
                        self.write_event(
                            account,
                            snapshots[account],
                            account_observation,
                            outcome="routed",
                            track=self.tracks.get(account),
                        )
        elif any(
            observation.quest_id in self.skipped_quest_ids.get(account, set())
            for account, observation in observations.items()
        ):
            skipped_ids = sorted(
                observation.quest_id
                for account, observation in observations.items()
                if observation.quest_id in self.skipped_quest_ids.get(account, set())
            )
            self.send_regular_hunt("difficulty-skip-" + "-".join(skipped_ids))
        return anomalies


MERCENARY_TIMELINE_FIELDS = [
    "timestamp_utc",
    "case",
    "request_id",
    "status",
    "outcome",
    "reason",
    "leader_account",
    "leader_character",
    "leader_level",
    "companion_account",
    "companion_character",
    "companion_level",
    "companion_experience",
    "companion_experience_into_level",
    "companion_money_copper",
    "companion_class",
    "companion_role",
    "level_delta",
    "group_valid",
    "distance_to_leader",
    "proximity_valid",
    "service_money_delta_copper",
    "specializations",
    "usable_skills",
    "usable_spells",
]


def write_mercenary_timeline_row(path: Path, row: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MERCENARY_TIMELINE_FIELDS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def companion_request_object(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    request = payload.get("request", payload.get("Request", payload))
    return request if isinstance(request, dict) else {}


class MercenaryCoordinator:
    TERMINAL_STATUSES = {"canceled", "cancelled", "completed", "failed"}

    def __init__(
        self,
        *,
        options: ContinuousSupervisorOptions,
        case_name: str,
        leader_account: str,
        leader_character: str,
        role: str,
        contract_tier: str,
        companion_account: str,
        companion_specs: str,
        service_process: subprocess.Popen[object],
        service_run_directory: Path,
        status_directory: Path,
        timeline_path: Path,
        initial_hunt_payload: dict[str, object] | None = None,
        poll_interval: float = 2.0,
        attach_timeout: float = 60.0,
        attach_max_distance: float = 4000.0,
    ) -> None:
        self.options = options
        self.case_name = case_name
        self.leader_account = leader_account
        self.leader_character = leader_character
        self.role = role
        self.contract_tier = contract_tier
        self.companion_account = companion_account
        self.companion_specs = companion_specs
        self.service_process = service_process
        self.service_run_directory = service_run_directory
        self.status_directory = status_directory
        self.timeline_path = timeline_path
        self.initial_hunt_payload = initial_hunt_payload
        self.poll_interval = max(0.5, poll_interval)
        self.attach_timeout = max(5.0, attach_timeout)
        self.attach_max_distance = max(1.0, attach_max_distance)
        self.request_id = ""
        self.status = ""
        self.assigned_name = ""
        self.request_started_at = 0.0
        self.active_since = 0.0
        self.next_poll_at = 0.0
        self.next_request_at = 0.0
        self.last_signature: tuple[object, ...] | None = None
        self.last_companion_snapshot: ProgressionSnapshot | None = None
        self.group_valid = False
        self.proximity_valid = False
        self.initial_hunt_routed = False
        self.reported_anomalies: set[tuple[str, str, str]] = set()

    @property
    def ready(self) -> bool:
        return (
            self.status == "active"
            and self.group_valid
            and self.proximity_valid
            and self.last_companion_snapshot is not None
        )

    @staticmethod
    def distance_to_leader(
        leader: ProgressionSnapshot,
        companion: ProgressionSnapshot,
    ) -> float:
        if leader.region != companion.region:
            return math.inf
        return math.hypot(companion.x - leader.x, companion.y - leader.y)

    def route_initial_hunt(self, companion: ProgressionSnapshot) -> None:
        if self.initial_hunt_payload is None:
            raise RuntimeError("mercenary initial hunt payload is missing")
        payload = json.loads(json.dumps(self.initial_hunt_payload))
        hunt = payload.get("progressionHunt", {})
        if not isinstance(hunt, dict):
            raise ValueError("mercenary initial progressionHunt must be an object")
        request_id = f"{self.request_id}-initial-hunt"
        hunt["requestId"] = request_id
        hunt["members"] = {self.companion_account: {"level": companion.level}}
        payload["revision"] = request_id
        atomic_write_json(
            self.service_run_directory / self.request_id / "live-control.json",
            payload,
        )
        self.initial_hunt_routed = True

    def anomaly_once(
        self,
        code: str,
        severity: str,
        message: str,
        details: dict[str, object],
        *,
        marker: str = "",
    ) -> ProgressionAnomaly | None:
        key = (code, self.request_id, marker)
        if key in self.reported_anomalies:
            return None
        self.reported_anomalies.add(key)
        return ProgressionAnomaly(code, severity, message, details)

    def write_event(
        self,
        leader: ProgressionSnapshot,
        companion: ProgressionSnapshot | None,
        *,
        outcome: str,
        reason: str = "",
        group_valid: bool = False,
        proximity_valid: bool = False,
        service_money_delta_copper: int | None = None,
    ) -> None:
        distance = (
            self.distance_to_leader(leader, companion)
            if companion is not None
            else math.inf
        )
        write_mercenary_timeline_row(
            self.timeline_path,
            {
                "timestamp_utc": utc_now(),
                "case": self.case_name,
                "request_id": self.request_id,
                "status": self.status,
                "outcome": outcome,
                "reason": reason,
                "leader_account": self.leader_account,
                "leader_character": leader.name or self.leader_character,
                "leader_level": leader.level,
                "companion_account": self.companion_account,
                "companion_character": self.assigned_name if companion is None else companion.name,
                "companion_level": 0 if companion is None else companion.level,
                "companion_experience": "" if companion is None else companion.experience,
                "companion_experience_into_level": ""
                if companion is None
                else companion.experience_into_level,
                "companion_money_copper": "" if companion is None else companion.money_copper,
                "companion_class": "" if companion is None else companion.class_name,
                "companion_role": self.role if companion is None else companion.companion_role,
                "level_delta": 0 if companion is None else companion.level - leader.level,
                "group_valid": 1 if group_valid else 0,
                "distance_to_leader": "" if not math.isfinite(distance) else round(distance, 1),
                "proximity_valid": 1 if proximity_valid else 0,
                "service_money_delta_copper": ""
                if service_money_delta_copper is None
                else service_money_delta_copper,
                "specializations": ""
                if companion is None
                else json.dumps(companion.specialization_levels, ensure_ascii=False, separators=(",", ":")),
                "usable_skills": 0 if companion is None else len(companion.usable_skills),
                "usable_spells": 0 if companion is None else len(companion.usable_spells),
            },
        )

    def create_request(self, leader: ProgressionSnapshot) -> None:
        if not leader.name:
            raise RuntimeError("mercenary request needs the online leader character name")
        payload = api_json_request(
            self.options,
            "POST",
            "/api/dummy/companions/requests",
            {
                "player": leader.name,
                "role": self.role,
                "source": f"continuous_growth_{self.case_name}",
                "contentType": "pve",
                "createdBy": "dummy-continuous-growth",
                "contractTier": self.contract_tier,
                "region": leader.region,
                "x": leader.x,
                "y": leader.y,
                "z": leader.z,
            },
        )
        request = companion_request_object(payload)
        request_id = _dict_text(request, "id", "Id")
        if not request_id:
            raise RuntimeError(f"mercenary request did not return an id: {payload}")
        self.request_id = request_id
        self.status = _dict_text(request, "status", "Status") or "queued"
        self.assigned_name = _dict_text(
            request,
            "assignedCompanionName",
            "AssignedCompanionName",
        )
        self.request_started_at = time.monotonic()
        self.active_since = 0.0
        self.last_signature = None
        self.last_companion_snapshot = None
        self.group_valid = False
        self.proximity_valid = False
        self.initial_hunt_routed = False
        self.write_event(leader, None, outcome="requested")

    def request_snapshot(self) -> dict[str, object]:
        if not self.request_id:
            return {}
        return companion_request_object(
            api_json_request(
                self.options,
                "GET",
                f"/api/dummy/companions/requests/{urllib.parse.quote(self.request_id)}",
            )
        )

    def fetch_companion_snapshot(self) -> ProgressionSnapshot:
        payload = fetch_progression_payload(
            self.options.api_base_url,
            self.companion_account,
            character=self.assigned_name,
            timeout=self.options.request_timeout,
        )
        return parse_progression_snapshot(payload)

    def grouped_companion(self, leader_payload: dict[str, object]) -> dict[str, object] | None:
        members = leader_payload.get("groupMembers", leader_payload.get("group_members", []))
        if not isinstance(members, list):
            return None
        for member in members:
            if not isinstance(member, dict):
                continue
            name = _dict_text(member, "name", "Name")
            account = _dict_text(member, "account", "Account")
            is_companion = bool(member.get("isCompanion", member.get("is_companion", False)))
            if not is_companion:
                continue
            if self.assigned_name and name.lower() == self.assigned_name.lower():
                return member
            if self.companion_account and account.lower() == self.companion_account.lower():
                return member
        return None

    def companion_snapshot_anomalies(
        self,
        leader: ProgressionSnapshot,
        companion: ProgressionSnapshot,
    ) -> list[ProgressionAnomaly]:
        anomalies: list[ProgressionAnomaly] = []
        level_delta = companion.level - leader.level
        if abs(level_delta) > 1:
            anomaly = self.anomaly_once(
                "mercenary_level_desync",
                "error",
                "Mercenary level differs from the owner by more than one level.",
                {
                    "leaderLevel": leader.level,
                    "mercenaryLevel": companion.level,
                    "account": self.companion_account,
                },
                marker=f"{leader.level}:{companion.level}",
            )
            if anomaly is not None:
                anomalies.append(anomaly)
        previous = self.last_companion_snapshot
        if previous is not None:
            if companion.level < previous.level:
                anomaly = self.anomaly_once(
                    "mercenary_level_regression",
                    "error",
                    "Mercenary level regressed during the continuous run.",
                    {"before": previous.level, "after": companion.level},
                    marker=f"{previous.level}:{companion.level}",
                )
                if anomaly is not None:
                    anomalies.append(anomaly)
            disappeared = sorted(
                set(previous.usable_skills + previous.usable_spells)
                - set(companion.usable_skills + companion.usable_spells)
            )
            if disappeared:
                anomaly = self.anomaly_once(
                    "mercenary_usable_catalog_regression",
                    "warning",
                    "Mercenary usable skills or spells disappeared.",
                    {"entries": disappeared[:20], "total": len(disappeared)},
                    marker=f"{leader.level}:{companion.level}",
                )
                if anomaly is not None:
                    anomalies.append(anomaly)
        over_level = {
            spec.key_name or spec.name: spec.level
            for spec in companion.specializations
            if spec.trainable and spec.level > companion.level
        }
        if over_level:
            anomaly = self.anomaly_once(
                "mercenary_specialization_above_level",
                "error",
                "A mercenary specialization exceeds the mercenary level.",
                {"level": companion.level, "specializations": over_level},
                marker=str(companion.level),
            )
            if anomaly is not None:
                anomalies.append(anomaly)
        return anomalies

    def poll(
        self,
        leader_payload: dict[str, object],
        leader: ProgressionSnapshot,
    ) -> list[ProgressionAnomaly]:
        if self.service_process.poll() is not None:
            raise RuntimeError(
                f"mercenary service exited during growth: rc={self.service_process.returncode}"
            )
        now = time.monotonic()
        if now < self.next_poll_at:
            return []
        self.next_poll_at = now + self.poll_interval
        if not self.request_id:
            if now >= self.next_request_at:
                self.create_request(leader)
            return []

        request = self.request_snapshot()
        if not request:
            raise RuntimeError(f"mercenary request disappeared: {self.request_id}")
        previous_status = self.status
        self.status = _dict_text(request, "status", "Status").lower()
        self.assigned_name = _dict_text(
            request,
            "assignedCompanionName",
            "AssignedCompanionName",
        ) or self.assigned_name
        if self.status != previous_status:
            self.write_event(
                leader,
                None,
                outcome="request_status",
                reason=_dict_text(request, "message", "Message"),
            )
        if self.status in self.TERMINAL_STATUSES:
            reason = _dict_text(request, "closeReason", "CloseReason", "message", "Message")
            self.write_event(leader, self.last_companion_snapshot, outcome="contract_ended", reason=reason)
            if self.status == "failed":
                raise RuntimeError(f"mercenary request failed: {reason or self.request_id}")
            self.request_id = ""
            self.status = ""
            self.assigned_name = ""
            self.group_valid = False
            self.proximity_valid = False
            self.next_request_at = now + 80.0
            return []
        if self.status != "active":
            if now - self.request_started_at > self.attach_timeout:
                raise TimeoutError(
                    f"mercenary attach timeout request={self.request_id} status={self.status}"
                )
            return []

        if self.active_since <= 0.0:
            self.active_since = now
        group_member = self.grouped_companion(leader_payload)
        if group_member is None:
            self.group_valid = False
            self.proximity_valid = False
            if now - self.active_since > self.attach_timeout:
                raise RuntimeError(
                    f"active mercenary is missing from leader group request={self.request_id}"
                )
            return []

        try:
            companion = self.fetch_companion_snapshot()
        except Exception as exc:
            anomaly = self.anomaly_once(
                "mercenary_telemetry_api_error",
                "warning",
                "Mercenary progression telemetry could not be read.",
                {"account": self.companion_account, "error": str(exc)},
            )
            return [] if anomaly is None else [anomaly]

        anomalies = self.companion_snapshot_anomalies(leader, companion)
        self.group_valid = True
        distance = self.distance_to_leader(leader, companion)
        self.proximity_valid = distance <= self.attach_max_distance
        if not self.proximity_valid:
            if not self.initial_hunt_routed:
                self.route_initial_hunt(companion)
                self.write_event(
                    leader,
                    companion,
                    outcome="hunt_routed",
                    reason=f"distance={distance:.1f}",
                    group_valid=True,
                    proximity_valid=False,
                )
            self.last_companion_snapshot = companion
            if now - self.active_since > self.attach_timeout:
                raise RuntimeError(
                    "active mercenary did not reach the leader "
                    f"request={self.request_id} distance={distance:.1f}"
                )
            return anomalies
        signature = (
            self.request_id,
            self.status,
            leader.level,
            companion.level,
            companion.experience,
            len(companion.usable_skills),
            len(companion.usable_spells),
            self.proximity_valid,
        )
        if signature != self.last_signature:
            self.write_event(
                leader,
                companion,
                outcome="active",
                group_valid=True,
                proximity_valid=True,
            )
            self.last_signature = signature
        self.last_companion_snapshot = companion
        return anomalies

    def prepare_checkpoint(
        self,
        payload: dict[str, object],
        request_id: str,
    ) -> ProgressionSnapshot:
        if not self.request_id or self.status != "active":
            raise RuntimeError("mercenary is not active at the level service checkpoint")
        before = self.fetch_companion_snapshot()
        companion_payload = json.loads(json.dumps(payload))
        progression = companion_payload.get("progressionService", {})
        if not isinstance(progression, dict):
            raise ValueError("mercenary checkpoint progressionService must be an object")
        progression["requestId"] = request_id
        progression["statusDirectory"] = str(self.status_directory)
        progression["members"] = {
            self.companion_account: {
                "level": before.level,
                "specs": self.companion_specs,
                "train": before.level >= 2,
                "sellSlots": [],
                "buySlots": [],
                "equipSlots": [],
                "merchantEquipSlots": [],
                "expectedSaleCopper": 0,
                "expectedPurchaseCopper": 0,
            }
        }
        companion_payload["revision"] = request_id
        atomic_write_json(
            self.service_run_directory / self.request_id / "live-control.json",
            companion_payload,
        )
        return before

    def finish_checkpoint(
        self,
        request_id: str,
        before: ProgressionSnapshot,
        leader: ProgressionSnapshot,
    ) -> list[ProgressionAnomaly]:
        statuses = wait_for_statuses(
            self.service_process,
            self.status_directory,
            request_id,
            [self.companion_account],
            timeout=self.options.service_timeout,
            poll_interval=self.options.poll_interval,
        )
        status = statuses.get(self.companion_account, {})
        after = self.fetch_companion_snapshot()
        economy = EconomyLedger(
            hunt_start_copper=before.money_copper,
            service_start_copper=before.money_copper,
            service_end_copper=after.money_copper,
        )
        anomalies = [
            ProgressionAnomaly(
                f"mercenary_{row.code}",
                row.severity,
                row.message,
                {"account": self.companion_account, **row.details},
            )
            for row in audit_progression_checkpoint(
                before,
                after,
                expected_level=before.level,
                training_requested=before.level >= 2,
                economy=economy,
            )
        ]
        if not bool(status.get("ok")):
            anomalies.append(
                ProgressionAnomaly(
                    "mercenary_service_checkpoint_failed",
                    "error",
                    "Mercenary behavior client reported a failed training checkpoint.",
                    {"account": self.companion_account, "errors": status.get("errors", [])},
                )
            )
        self.write_event(
            leader,
            after,
            outcome="level_checkpoint",
            reason=";".join(str(value) for value in status.get("errors", [])),
            group_valid=True,
            proximity_valid=self.distance_to_leader(leader, after) <= self.attach_max_distance,
            service_money_delta_copper=economy.service_net_copper,
        )
        self.last_companion_snapshot = after
        return anomalies

    def close(self) -> None:
        if not self.request_id or self.status in self.TERMINAL_STATUSES:
            return
        try:
            api_json_request(
                self.options,
                "POST",
                f"/api/dummy/companions/requests/{urllib.parse.quote(self.request_id)}/cancel",
                {"reason": "continuous_growth_complete"},
            )
        except Exception:
            pass


def wait_for_process_exit(process: subprocess.Popen[object], timeout: float = 30.0) -> None:
    try:
        process.wait(timeout=max(1.0, timeout))
    except subprocess.TimeoutExpired:
        process.terminate()
        try:
            process.wait(timeout=10.0)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10.0)


def supervise_continuous_progression(
    *,
    process: subprocess.Popen[object],
    options: ContinuousSupervisorOptions,
    accounts: dict[str, str],
    case_name: str,
    mode: str,
    realm: str,
    party_size: int,
    live_control_path: Path,
    status_directory: Path,
    output_directory: Path,
    build_checkpoint_payload: Callable[
        [int, dict[str, dict[str, object]], dict[str, ProgressionSnapshot]],
        dict[str, object],
    ],
    data_integrity_flags: Iterable[str] = (),
    mercenary_service_process: subprocess.Popen[object] | None = None,
    mercenary_service_run_directory: Path | None = None,
    mercenary_account: str = "",
    mercenary_specs: str = "",
    mercenary_role: str = "fill",
    mercenary_contract_tier: str = "legendary",
    mercenary_poll_interval: float = 2.0,
    mercenary_attach_timeout: float = 60.0,
) -> ContinuousSupervisorResult:
    anomalies: list[ProgressionAnomaly] = []
    checkpoints = 0
    completed_level = 0
    error = ""
    output_directory.mkdir(parents=True, exist_ok=True)
    timeline_path = output_directory / "continuous-timeline.csv"
    checkpoint_directory = output_directory / "checkpoints"
    anomaly_path = output_directory / "anomaly-summary.json"
    mercenary_coordinator: MercenaryCoordinator | None = None

    try:
        hunt_start_payloads = wait_for_online_payloads(process, options, accounts)
        hunt_start = {
            account: parse_progression_snapshot(payload)
            for account, payload in hunt_start_payloads.items()
        }
        completed_level = min(snapshot.level for snapshot in hunt_start.values())
        serviced_level = completed_level
        last_progress_at = time.monotonic()
        initial_template = build_checkpoint_payload(
            serviced_level,
            hunt_start_payloads,
            hunt_start,
        )
        initial_hunt_payload = checkpoint_service_to_hunt_payload(
            initial_template,
            request_id=f"{case_name}-initial-regular-hunt",
        )
        if mercenary_service_process is not None:
            if len(accounts) != 1:
                raise ValueError("continuous mercenary mode requires exactly one owner account")
            if mercenary_service_run_directory is None or not mercenary_account:
                raise ValueError("continuous mercenary mode needs its service directory and account")
            leader_account = next(iter(accounts))
            mercenary_coordinator = MercenaryCoordinator(
                options=options,
                case_name=case_name,
                leader_account=leader_account,
                leader_character=accounts[leader_account],
                role=mercenary_role,
                contract_tier=mercenary_contract_tier,
                companion_account=mercenary_account,
                companion_specs=mercenary_specs,
                service_process=mercenary_service_process,
                service_run_directory=mercenary_service_run_directory,
                status_directory=status_directory,
                timeline_path=output_directory / "mercenary-timeline.csv",
                initial_hunt_payload=initial_hunt_payload,
                poll_interval=mercenary_poll_interval,
                attach_timeout=mercenary_attach_timeout,
            )
        dynamic_quest_coordinator = DynamicQuestCoordinator(
            options=options,
            accounts=accounts,
            case_name=case_name,
            party_size=party_size,
            live_control_path=live_control_path,
            timeline_path=output_directory / "dynamic-quest-timeline.csv",
        )
        dynamic_quest_coordinator.set_regular_hunt_payload(initial_hunt_payload)

        while serviced_level < options.max_level:
            if process.poll() is not None:
                raise RuntimeError(f"behavior process exited during growth: rc={process.returncode}")
            try:
                service_start_payloads = fetch_all_progression_payloads(options, accounts)
            except Exception:
                time.sleep(max(0.1, options.poll_interval))
                continue
            service_start = {
                account: parse_progression_snapshot(payload)
                for account, payload in service_start_payloads.items()
            }
            if mercenary_coordinator is not None:
                leader_account = mercenary_coordinator.leader_account
                mercenary_anomalies = mercenary_coordinator.poll(
                    service_start_payloads[leader_account],
                    service_start[leader_account],
                )
                anomalies.extend(mercenary_anomalies)
                if options.fail_on_checkpoint_error and any(
                    row.severity == "error" for row in mercenary_anomalies
                ):
                    raise RuntimeError(
                        "mercenary progression validation failed: "
                        + ",".join(row.code for row in mercenary_anomalies)
                    )
                if not mercenary_coordinator.ready:
                    time.sleep(max(0.1, options.poll_interval))
                    continue
            dynamic_quest_anomalies = dynamic_quest_coordinator.poll(service_start)
            anomalies.extend(dynamic_quest_anomalies)
            if options.fail_on_checkpoint_error and any(
                row.severity == "error" for row in dynamic_quest_anomalies
            ):
                raise RuntimeError(
                    "dynamic quest validation failed: "
                    + ",".join(row.code for row in dynamic_quest_anomalies)
                )
            current_level = min(snapshot.level for snapshot in service_start.values())
            if (
                current_level > serviced_level
                and mercenary_coordinator is not None
                and mercenary_coordinator.last_companion_snapshot is not None
                and mercenary_coordinator.last_companion_snapshot.level < current_level
            ):
                if time.monotonic() - last_progress_at > options.level_timeout:
                    raise TimeoutError(
                        "mercenary catch-up timeout "
                        f"leader={current_level} "
                        f"mercenary={mercenary_coordinator.last_companion_snapshot.level} "
                        f"seconds={options.level_timeout:.0f}"
                    )
                time.sleep(max(0.1, options.poll_interval))
                continue
            if current_level <= serviced_level:
                if time.monotonic() - last_progress_at > options.level_timeout:
                    raise TimeoutError(
                        f"continuous level timeout level={serviced_level} seconds={options.level_timeout:.0f}"
                    )
                time.sleep(max(0.1, options.poll_interval))
                continue

            request_id = f"{case_name}-level-{current_level:02d}-{checkpoints + 1:03d}"
            payload = build_checkpoint_payload(current_level, service_start_payloads, service_start)
            progression = payload.setdefault("progressionService", {})
            if not isinstance(progression, dict):
                raise ValueError("checkpoint payload progressionService must be an object")
            progression["requestId"] = request_id
            progression["statusDirectory"] = str(status_directory)
            payload["revision"] = request_id
            dynamic_quest_coordinator.set_regular_hunt_payload(
                checkpoint_service_to_hunt_payload(
                    payload,
                    request_id=f"{request_id}-regular-hunt",
                )
            )
            mercenary_before = (
                mercenary_coordinator.prepare_checkpoint(payload, request_id)
                if mercenary_coordinator is not None
                else None
            )
            atomic_write_json(live_control_path, payload)
            member_plans = progression.get("members", {})
            if not isinstance(member_plans, dict) or not member_plans:
                raise ValueError("checkpoint payload must contain progressionService.members")
            serviced_accounts = [account for account in accounts if account in member_plans]
            statuses = wait_for_statuses(
                process,
                status_directory,
                request_id,
                serviced_accounts,
                timeout=options.service_timeout,
                poll_interval=options.poll_interval,
            )
            service_end_payloads = fetch_all_progression_payloads(options, accounts)
            service_end = {
                account: parse_progression_snapshot(payload)
                for account, payload in service_end_payloads.items()
            }
            mercenary_checkpoint_anomalies: list[ProgressionAnomaly] = []
            if mercenary_coordinator is not None and mercenary_before is not None:
                leader_account = mercenary_coordinator.leader_account
                mercenary_checkpoint_anomalies = mercenary_coordinator.finish_checkpoint(
                    request_id,
                    mercenary_before,
                    service_end[leader_account],
                )
                anomalies.extend(mercenary_checkpoint_anomalies)

            checkpoint_payload = {
                "schemaVersion": 1,
                "request": payload,
                "statuses": statuses,
                "serviceStart": service_start_payloads,
                "serviceEnd": service_end_payloads,
            }
            atomic_write_json(checkpoint_directory / f"level-{current_level:02d}.json", checkpoint_payload)

            checkpoint_failed = any(
                row.severity == "error" for row in mercenary_checkpoint_anomalies
            )
            for account in serviced_accounts:
                start = hunt_start[account]
                before = service_start[account]
                after = service_end[account]
                member_plan = member_plans.get(account, {})
                if not isinstance(member_plan, dict):
                    member_plan = {}
                status = statuses.get(account, {})
                expected_sale = int(member_plan.get("expectedSaleCopper", 0) or 0)
                expected_purchase = int(member_plan.get("expectedPurchaseCopper", 0) or 0)
                economy = EconomyLedger(
                    hunt_start_copper=start.money_copper,
                    service_start_copper=before.money_copper,
                    service_end_copper=after.money_copper,
                    expected_sale_copper=expected_sale,
                    expected_purchase_copper=expected_purchase,
                )
                account_anomalies = audit_progression_checkpoint(
                    before,
                    after,
                    expected_level=int(member_plan.get("level", current_level) or current_level),
                    training_requested=bool(member_plan.get("train", True)),
                    economy=economy,
                )
                level_jump = max(0, before.level - start.level)
                if level_jump > 1:
                    account_anomalies.append(
                        ProgressionAnomaly(
                            "level_jump_missed_checkpoint",
                            "error",
                            "More than one level was gained between supervisor polls.",
                            {"account": account, "from": start.level, "to": before.level},
                        )
                    )
                if not bool(status.get("ok")):
                    checkpoint_failed = True
                    account_anomalies.append(
                        ProgressionAnomaly(
                            "service_checkpoint_failed",
                            "error",
                            "Behavior client reported a failed training or merchant checkpoint.",
                            {"account": account, "errors": status.get("errors", [])},
                        )
                    )
                if any(row.severity == "error" for row in account_anomalies):
                    checkpoint_failed = True
                anomalies.extend(account_anomalies)
                acquired = acquired_inventory_items(start, before)
                write_timeline_row(
                    timeline_path,
                    {
                        "timestamp_utc": utc_now(),
                        "request_id": request_id,
                        "case": case_name,
                        "mode": mode,
                        "realm": realm,
                        "party_size": party_size,
                        "account": account,
                        "character": after.name,
                        "level_hunt_start": start.level,
                        "level_service_start": before.level,
                        "level_service_end": after.level,
                        "level_jump": level_jump,
                        "xp_hunt_delta": before.experience - start.experience,
                        "experience_into_level_after": after.experience_into_level,
                        "mob_coin_copper": economy.mob_coin_copper,
                        "sale_proceeds_expected_copper": expected_sale,
                        "purchase_cost_expected_copper": expected_purchase,
                        "service_money_delta_copper": economy.service_net_copper,
                        "service_unexplained_copper": economy.unexplained_service_copper,
                        "money_end_copper": after.money_copper,
                        "inventory_hunt_delta": before.inventory_item_count - start.inventory_item_count,
                        "acquired_items": json.dumps(acquired, ensure_ascii=False, separators=(",", ":")),
                        "specialty_points_before": before.specialty_points,
                        "specialty_points_after": after.specialty_points,
                        "spec_gains": json.dumps(
                            specialization_gains(before, after),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        "usable_skills_before": len(before.usable_skills),
                        "usable_skills_after": len(after.usable_skills),
                        "usable_spells_before": len(before.usable_spells),
                        "usable_spells_after": len(after.usable_spells),
                        "training_commands": json.dumps(
                            status.get("trainingCommands", []),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                        "service_ok": 1 if status.get("ok") else 0,
                        "service_errors": ";".join(str(value) for value in status.get("errors", [])),
                        "used_player_reset": 1 if status.get("usedPlayerReset") else 0,
                        "is_companion": 1 if after.is_companion else 0,
                        "companion_role": after.companion_role,
                        "data_integrity_flags": ";".join(data_integrity_flags),
                        "anomaly_codes": ";".join(row.code for row in account_anomalies),
                    },
                )

            checkpoints += 1
            serviced_level = current_level
            completed_level = current_level
            hunt_start_payloads = service_end_payloads
            hunt_start = service_end
            last_progress_at = time.monotonic()
            if checkpoint_failed and options.fail_on_checkpoint_error:
                raise RuntimeError(f"checkpoint failed at level {current_level}")

        if mercenary_coordinator is not None:
            mercenary_coordinator.close()
        request_quit(live_control_path, f"{case_name}-complete-level-{completed_level}")
        wait_for_process_exit(process)
    except Exception as exc:
        error = str(exc)
        anomalies.append(
            ProgressionAnomaly(
                "continuous_supervisor_failed",
                "error",
                error,
                {"completedLevel": completed_level, "checkpointCount": checkpoints},
            )
        )
        if mercenary_coordinator is not None:
            mercenary_coordinator.close()
        if process.poll() is None:
            request_quit(live_control_path, f"{case_name}-abort")
            wait_for_process_exit(process)

    write_compact_anomaly_summary(
        anomaly_path,
        anomalies,
        run_id=case_name,
        checkpoints=checkpoints,
    )
    result = ContinuousSupervisorResult(
        ok=not error and not any(row.severity == "error" for row in anomalies),
        completed_level=completed_level,
        checkpoints=checkpoints,
        anomalies=tuple(anomalies),
        error=error,
        mode=mode,
        realm=realm,
        party_size=party_size,
    )
    atomic_write_json(output_directory / "continuous-result.json", asdict(result))
    return result
