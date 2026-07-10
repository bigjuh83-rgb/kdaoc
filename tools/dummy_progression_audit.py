"""Deterministic snapshots and anomaly checks for continuous dummy growth."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class ProgressionSpecialization:
    name: str = ""
    key_name: str = ""
    level: int = 0
    trainable: bool = False


@dataclass(frozen=True)
class ProgressionItem:
    slot: int = 0
    template_id: str = ""
    unique_template_id: str = ""
    name: str = ""
    level: int = 0
    count: int = 0
    sell_price: int = 0
    price: int = 0
    dps_af: int = 0
    spd_abs: int = 0
    object_type: int = 0
    item_type: int = 0
    quality: int = 0
    bonus: int = 0
    type_damage: int = 0
    realm: int = 0
    allowed_classes: str = ""
    equipped: bool = False
    backpack: bool = False

    @property
    def stack_sell_value(self) -> int:
        return max(0, self.sell_price) * max(0, self.count)


@dataclass(frozen=True)
class ProgressionSnapshot:
    name: str = ""
    account: str = ""
    level: int = 0
    class_name: str = ""
    class_id: int = 0
    realm: str = ""
    region: int = 0
    x: int = 0
    y: int = 0
    z: int = 0
    experience: int = 0
    experience_for_current_level: int = 0
    experience_for_next_level: int = 0
    experience_into_level: int = 0
    experience_needed_for_level: int = 0
    money_copper: int = 0
    specialty_points: int = 0
    specializations: tuple[ProgressionSpecialization, ...] = ()
    inventory: tuple[ProgressionItem, ...] = ()
    usable_skills: tuple[str, ...] = ()
    usable_spells: tuple[str, ...] = ()
    is_companion: bool = False
    companion_role: str = ""

    @property
    def inventory_item_count(self) -> int:
        return sum(max(0, item.count) for item in self.inventory)

    @property
    def backpack_sell_value(self) -> int:
        return sum(item.stack_sell_value for item in self.inventory if item.backpack)

    @property
    def specialization_levels(self) -> dict[str, int]:
        return {spec.key_name or spec.name: spec.level for spec in self.specializations}


@dataclass(frozen=True)
class EconomyLedger:
    hunt_start_copper: int
    service_start_copper: int
    service_end_copper: int
    expected_sale_copper: int = 0
    expected_purchase_copper: int = 0

    @property
    def mob_coin_copper(self) -> int:
        return self.service_start_copper - self.hunt_start_copper

    @property
    def service_net_copper(self) -> int:
        return self.service_end_copper - self.service_start_copper

    @property
    def expected_service_net_copper(self) -> int:
        return self.expected_sale_copper - self.expected_purchase_copper

    @property
    def unexplained_service_copper(self) -> int:
        return self.service_net_copper - self.expected_service_net_copper


@dataclass(frozen=True)
class ProgressionAnomaly:
    code: str
    severity: str
    message: str
    details: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ProgressionLocation:
    region: int = 0
    x: int = 0
    y: int = 0
    z: int = 0

    @property
    def configured(self) -> bool:
        return self.region > 0 and (self.x != 0 or self.y != 0)


@dataclass(frozen=True)
class ProgressionServiceRequest:
    request_id: str
    level: int
    service_location: ProgressionLocation
    hunt_location: ProgressionLocation
    merchant_location: ProgressionLocation = ProgressionLocation()
    status_directory: str = ""
    service_npc_name: str = ""
    merchant_npc_name: str = ""
    specs: str = ""
    train: bool = True
    sell_slots: tuple[int, ...] = ()
    buy_slots: tuple[int, ...] = ()
    equip_slots: tuple[int, ...] = ()
    merchant_equip_slots: tuple[int, ...] = ()
    expected_sale_copper: int = 0
    expected_purchase_copper: int = 0
    prefer_target_name: str = ""
    require_target_name: str = ""
    avoid_target_name: str = ""
    require_target_name_exact: bool = False
    min_target_level: int = 0
    max_target_level: int = 0
    target_home_max_distance: float = 0.0
    combat_home_leash_distance: float = 0.0
    required_target_home_hunt_distance: float = 0.0


@dataclass(frozen=True)
class ProgressionHuntRequest:
    request_id: str
    level: int
    hunt_location: ProgressionLocation
    prefer_target_name: str = ""
    require_target_name: str = ""
    avoid_target_name: str = ""
    require_target_name_exact: bool = False
    min_target_level: int = 0
    max_target_level: int = 0
    target_home_max_distance: float = 0.0
    combat_home_leash_distance: float = 0.0
    required_target_home_hunt_distance: float = 0.0


def _as_int(value: object, default: int = 0) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return default


def _as_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _as_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return default


def _player_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {}
    player = payload.get("player", payload)
    return player if isinstance(player, dict) else {}


def _first(mapping: dict[str, object], *names: str, default: object = None) -> object:
    for name in names:
        if name in mapping:
            return mapping[name]
    return default


def _int_tuple(value: object) -> tuple[int, ...]:
    if isinstance(value, str):
        values: Iterable[object] = value.split(",")
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        values = ()
    parsed = []
    for item in values:
        number = _as_int(item, -1)
        if number >= 0 and number not in parsed:
            parsed.append(number)
    return tuple(parsed)


def _parse_location(value: object) -> ProgressionLocation:
    if not isinstance(value, dict):
        return ProgressionLocation()
    return ProgressionLocation(
        region=_as_int(_first(value, "region", "regionId", "region_id")),
        x=_as_int(value.get("x")),
        y=_as_int(value.get("y")),
        z=_as_int(value.get("z")),
    )


def parse_progression_service_request(
    payload: object,
    *,
    account: str,
) -> ProgressionServiceRequest | None:
    if not isinstance(payload, dict):
        return None
    raw = _first(payload, "progressionService", "progression_service")
    if not isinstance(raw, dict):
        return None

    merged: dict[str, object] = dict(raw)
    members = _first(raw, "members", "memberPlans", "member_plans", default={})
    if isinstance(members, dict) and members:
        member = next(
            (
                value
                for name, value in members.items()
                if str(name).strip().lower() == str(account).strip().lower()
            ),
            None,
        )
        if not isinstance(member, dict):
            return None
        merged.update(member)

    request_id = str(_first(raw, "requestId", "request_id", default="") or "").strip()
    level = _as_int(_first(merged, "level", "trainLevel", "train_level"))
    service_location = _parse_location(
        _first(merged, "serviceLocation", "service_location", default={})
    )
    hunt_location = _parse_location(
        _first(merged, "huntLocation", "hunt_location", default={})
    )
    merchant_location = _parse_location(
        _first(merged, "merchantLocation", "merchant_location", default={})
    )
    if not request_id or not 1 <= level <= 50 or not service_location.configured or not hunt_location.configured:
        return None

    return ProgressionServiceRequest(
        request_id=request_id,
        level=level,
        service_location=service_location,
        hunt_location=hunt_location,
        merchant_location=merchant_location,
        status_directory=str(
            _first(raw, "statusDirectory", "status_directory", default="") or ""
        ).strip(),
        service_npc_name=str(
            _first(merged, "serviceNpcName", "service_npc_name", default="") or ""
        ).strip(),
        merchant_npc_name=str(
            _first(merged, "merchantNpcName", "merchant_npc_name", default="") or ""
        ).strip(),
        specs=str(merged.get("specs", "") or "").strip(),
        train=_as_bool(merged.get("train", True)),
        sell_slots=_int_tuple(_first(merged, "sellSlots", "sell_slots", default=[])),
        buy_slots=_int_tuple(_first(merged, "buySlots", "buy_slots", default=[])),
        equip_slots=_int_tuple(_first(merged, "equipSlots", "equip_slots", default=[])),
        merchant_equip_slots=_int_tuple(
            _first(merged, "merchantEquipSlots", "merchant_equip_slots", default=[])
        ),
        expected_sale_copper=_as_int(
            _first(merged, "expectedSaleCopper", "expected_sale_copper")
        ),
        expected_purchase_copper=_as_int(
            _first(merged, "expectedPurchaseCopper", "expected_purchase_copper")
        ),
        prefer_target_name=str(
            _first(merged, "preferTargetName", "prefer_target_name", default="") or ""
        ).strip(),
        require_target_name=str(
            _first(merged, "requireTargetName", "require_target_name", default="") or ""
        ).strip(),
        avoid_target_name=str(
            _first(merged, "avoidTargetName", "avoid_target_name", default="") or ""
        ).strip(),
        require_target_name_exact=_as_bool(
            _first(merged, "requireTargetNameExact", "require_target_name_exact", default=False)
        ),
        min_target_level=_as_int(_first(merged, "minTargetLevel", "min_target_level")),
        max_target_level=_as_int(_first(merged, "maxTargetLevel", "max_target_level")),
        target_home_max_distance=_as_float(
            _first(merged, "targetHomeMaxDistance", "target_home_max_distance", default=0.0)
        ),
        combat_home_leash_distance=_as_float(
            _first(merged, "combatHomeLeashDistance", "combat_home_leash_distance", default=0.0)
        ),
        required_target_home_hunt_distance=_as_float(
            _first(
                merged,
                "requiredTargetHomeHuntDistance",
                "required_target_home_hunt_distance",
                default=0.0,
            )
        ),
    )


def parse_progression_hunt_request(
    payload: object,
    *,
    account: str,
) -> ProgressionHuntRequest | None:
    if not isinstance(payload, dict):
        return None
    raw = _first(payload, "progressionHunt", "progression_hunt")
    if not isinstance(raw, dict):
        return None

    merged: dict[str, object] = dict(raw)
    members = _first(raw, "members", "memberPlans", "member_plans", default={})
    if isinstance(members, dict) and members:
        member = next(
            (
                value
                for name, value in members.items()
                if str(name).strip().lower() == str(account).strip().lower()
            ),
            None,
        )
        if not isinstance(member, dict):
            return None
        merged.update(member)

    request_id = str(_first(raw, "requestId", "request_id", default="") or "").strip()
    level = _as_int(_first(merged, "level", "playerLevel", "player_level"))
    hunt_location = _parse_location(
        _first(merged, "huntLocation", "hunt_location", default={})
    )
    if not request_id or not 1 <= level <= 50 or not hunt_location.configured:
        return None

    return ProgressionHuntRequest(
        request_id=request_id,
        level=level,
        hunt_location=hunt_location,
        prefer_target_name=str(
            _first(merged, "preferTargetName", "prefer_target_name", default="") or ""
        ).strip(),
        require_target_name=str(
            _first(merged, "requireTargetName", "require_target_name", default="") or ""
        ).strip(),
        avoid_target_name=str(
            _first(merged, "avoidTargetName", "avoid_target_name", default="") or ""
        ).strip(),
        require_target_name_exact=_as_bool(
            _first(merged, "requireTargetNameExact", "require_target_name_exact", default=False)
        ),
        min_target_level=_as_int(_first(merged, "minTargetLevel", "min_target_level")),
        max_target_level=_as_int(_first(merged, "maxTargetLevel", "max_target_level")),
        target_home_max_distance=_as_float(
            _first(merged, "targetHomeMaxDistance", "target_home_max_distance", default=0.0)
        ),
        combat_home_leash_distance=_as_float(
            _first(merged, "combatHomeLeashDistance", "combat_home_leash_distance", default=0.0)
        ),
        required_target_home_hunt_distance=_as_float(
            _first(
                merged,
                "requiredTargetHomeHuntDistance",
                "required_target_home_hunt_distance",
                default=0.0,
            )
        ),
    )


def _parse_specializations(player: dict[str, object]) -> tuple[ProgressionSpecialization, ...]:
    rows = player.get("specializations", [])
    if not isinstance(rows, list):
        return ()
    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parsed.append(
            ProgressionSpecialization(
                name=str(row.get("name", "") or ""),
                key_name=str(row.get("keyName", row.get("key_name", "")) or ""),
                level=_as_int(row.get("level")),
                trainable=_as_bool(row.get("trainable")),
            )
        )
    return tuple(sorted(parsed, key=lambda item: (item.key_name or item.name).lower()))


def _parse_inventory(player: dict[str, object]) -> tuple[ProgressionItem, ...]:
    rows = player.get("inventory", [])
    if not isinstance(rows, list):
        return ()
    parsed = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        parsed.append(
            ProgressionItem(
                slot=_as_int(row.get("slot", row.get("slotPosition"))),
                template_id=str(row.get("iTemplate_Id", row.get("templateId", "")) or ""),
                unique_template_id=str(row.get("uTemplate_Id", row.get("uniqueTemplateId", "")) or ""),
                name=str(row.get("name", "") or ""),
                level=_as_int(row.get("level")),
                count=_as_int(row.get("count")),
                sell_price=_as_int(row.get("sellPrice", row.get("sell_price"))),
                price=_as_int(row.get("price")),
                dps_af=_as_int(row.get("dpS_AF", row.get("dpsAf", row.get("dps_af")))),
                spd_abs=_as_int(row.get("spD_ABS", row.get("spdAbs", row.get("spd_abs")))),
                object_type=_as_int(row.get("object_Type", row.get("objectType", row.get("object_type")))),
                item_type=_as_int(row.get("item_Type", row.get("itemType", row.get("item_type")))),
                quality=_as_int(row.get("quality")),
                bonus=_as_int(row.get("bonus")),
                type_damage=_as_int(row.get("type_Damage", row.get("typeDamage", row.get("type_damage")))),
                realm=_as_int(row.get("realm")),
                allowed_classes=str(
                    row.get("allowedClasses", row.get("allowed_classes", "")) or ""
                ),
                equipped=_as_bool(row.get("equipped")),
                backpack=_as_bool(row.get("backpack")),
            )
        )
    return tuple(sorted(parsed, key=lambda item: item.slot))


def _usable_signatures(payload: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(payload, dict):
        return (), ()
    skill_keys = set()
    for row in payload.get("skills", []):
        if not isinstance(row, dict):
            continue
        name = str(row.get("name", "") or "").strip()
        if name:
            skill_keys.add(f"{name}|{_as_int(row.get('level'))}")
    spell_keys = set()
    for line in payload.get("spellLines", []):
        if not isinstance(line, dict):
            continue
        for row in line.get("entries", []):
            if not isinstance(row, dict):
                continue
            name = str(row.get("name", "") or "").strip()
            if name:
                spell_keys.add(f"{name}|{_as_int(row.get('level', row.get('spellLevel')))}")
    return tuple(sorted(skill_keys)), tuple(sorted(spell_keys))


def parse_progression_snapshot(payload: object) -> ProgressionSnapshot:
    player = _player_payload(payload)
    usable_skills, usable_spells = _usable_signatures(payload)
    return ProgressionSnapshot(
        name=str(player.get("name", "") or ""),
        account=str(player.get("account", "") or ""),
        level=_as_int(player.get("level")),
        class_name=str(player.get("class", player.get("className", "")) or ""),
        class_id=_as_int(player.get("classId", player.get("class_id"))),
        realm=str(player.get("realm", "") or ""),
        region=_as_int(player.get("region")),
        x=_as_int(player.get("x")),
        y=_as_int(player.get("y")),
        z=_as_int(player.get("z")),
        experience=_as_int(player.get("experience")),
        experience_for_current_level=_as_int(player.get("experienceForCurrentLevel")),
        experience_for_next_level=_as_int(player.get("experienceForNextLevel")),
        experience_into_level=_as_int(player.get("experienceIntoLevel")),
        experience_needed_for_level=_as_int(player.get("experienceNeededForLevel")),
        money_copper=_as_int(player.get("moneyCopper", player.get("money_copper"))),
        specialty_points=_as_int(player.get("specialtyPoints", player.get("specialty_points"))),
        specializations=_parse_specializations(player),
        inventory=_parse_inventory(player),
        usable_skills=usable_skills,
        usable_spells=usable_spells,
        is_companion=_as_bool(player.get("isCompanion", player.get("is_companion"))),
        companion_role=str(player.get("companionRole", player.get("companion_role", "")) or ""),
    )


def specialization_gains(
    before: ProgressionSnapshot,
    after: ProgressionSnapshot,
) -> dict[str, int]:
    before_levels = before.specialization_levels
    return {
        name: level - before_levels.get(name, 0)
        for name, level in after.specialization_levels.items()
        if level > before_levels.get(name, 0)
    }


def usable_catalog_identity(value: str) -> str:
    name, separator, level = str(value or "").rpartition("|")
    if separator and level.isdigit():
        return name.strip().casefold()
    return str(value or "").strip().casefold()


def audit_progression_checkpoint(
    before: ProgressionSnapshot,
    after: ProgressionSnapshot,
    *,
    expected_level: int | None = None,
    training_requested: bool = False,
    economy: EconomyLedger | None = None,
    expected_equipped_template_ids: Iterable[str] = (),
) -> list[ProgressionAnomaly]:
    anomalies: list[ProgressionAnomaly] = []
    target_level = after.level if expected_level is None else int(expected_level)
    if after.level < before.level:
        anomalies.append(ProgressionAnomaly("level_regression", "error", "Character level regressed."))
    if after.level != target_level:
        anomalies.append(
            ProgressionAnomaly(
                "unexpected_level",
                "error",
                "Checkpoint level does not match the requested level.",
                {"expected": target_level, "actual": after.level},
            )
        )
    if after.level == before.level and after.experience < before.experience:
        anomalies.append(
            ProgressionAnomaly(
                "experience_regression",
                "warning",
                "Experience decreased without a level transition.",
                {"before": before.experience, "after": after.experience},
            )
        )

    spec_gains = specialization_gains(before, after)
    if training_requested and 2 <= after.level < 50 and not spec_gains:
        anomalies.append(
            ProgressionAnomaly(
                "training_no_spec_gain",
                "error",
                "Training was requested but no specialization increased.",
                {"specialtyPointsBefore": before.specialty_points, "specialtyPointsAfter": after.specialty_points},
            )
        )
    over_level_specs = {
        spec.key_name or spec.name: spec.level
        for spec in after.specializations
        if spec.trainable and spec.level > after.level
    }
    if over_level_specs:
        anomalies.append(
            ProgressionAnomaly(
                "specialization_above_level",
                "error",
                "A trainable specialization exceeds character level.",
                {"specializations": over_level_specs, "level": after.level},
            )
        )
    if training_requested:
        after_identities = {
            usable_catalog_identity(value)
            for value in after.usable_skills + after.usable_spells
        }
        disappeared = sorted(
            value
            for value in set(before.usable_skills + before.usable_spells)
            if usable_catalog_identity(value) not in after_identities
        )
        if disappeared:
            anomalies.append(
                ProgressionAnomaly(
                    "usable_catalog_regression",
                    "warning",
                    "Usable skills or spells disappeared after training.",
                    {"entries": disappeared[:20], "total": len(disappeared)},
                )
            )

    if economy is not None and economy.unexplained_service_copper != 0:
        anomalies.append(
            ProgressionAnomaly(
                "service_economy_mismatch",
                "warning",
                "Observed service money delta differs from planned sales and purchases.",
                {
                    "observedNet": economy.service_net_copper,
                    "expectedNet": economy.expected_service_net_copper,
                    "unexplained": economy.unexplained_service_copper,
                },
            )
        )

    expected_templates = {value for value in expected_equipped_template_ids if value}
    if expected_templates:
        equipped_templates = {
            item.unique_template_id or item.template_id
            for item in after.inventory
            if item.equipped
        }
        missing = sorted(expected_templates - equipped_templates)
        if missing:
            anomalies.append(
                ProgressionAnomaly(
                    "planned_equipment_not_equipped",
                    "error",
                    "Planned equipment was not equipped.",
                    {"templateIds": missing},
                )
            )
    return anomalies


def compact_anomaly_payload(
    anomalies: Iterable[ProgressionAnomaly],
    *,
    run_id: str,
    checkpoints: int,
) -> dict[str, object]:
    rows = list(anomalies)
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for row in rows:
        key = (row.code, row.severity)
        group = grouped.setdefault(
            key,
            {
                "code": row.code,
                "severity": row.severity,
                "count": 0,
                "message": row.message,
                "sampleDetails": [],
            },
        )
        group["count"] = int(group["count"]) + 1
        samples = group["sampleDetails"]
        if isinstance(samples, list) and row.details and row.details not in samples and len(samples) < 2:
            samples.append(row.details)
    unknown_rows = [
        row
        for row in rows
        if row.code.startswith("unknown_") or row.code.startswith("unclassified_")
    ]
    sample_limit = 20
    return {
        "schemaVersion": 1,
        "runId": run_id,
        "checkpointCount": int(checkpoints),
        "anomalyCount": len(rows),
        "anomalyGroups": list(grouped.values()),
        "anomalies": [asdict(row) for row in rows[:sample_limit]],
        "anomaliesTruncated": max(0, len(rows) - sample_limit),
        "modelRouting": {
            "default": "none",
            "decision": "small" if unknown_rows else "none",
            "unknownAnomalyCount": len(unknown_rows),
            "smallModelInput": [asdict(row) for row in unknown_rows[:10]],
            "smallModelWhen": "unknown anomalies remain after deterministic classification",
            "strongModelWhen": "unknown anomaly repeats or requires server-rule/code change",
        },
    }


def write_compact_anomaly_summary(
    path: Path,
    anomalies: Iterable[ProgressionAnomaly],
    *,
    run_id: str,
    checkpoints: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = compact_anomaly_payload(anomalies, run_id=run_id, checkpoints=checkpoints)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
