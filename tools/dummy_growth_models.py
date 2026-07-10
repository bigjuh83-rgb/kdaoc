"""Data models shared by the dummy growth runner and its helpers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RoutePoint:
    level: int
    x: int
    y: int
    z: int
    prefer: str = ""
    avoid: str = ""
    teleport_destination: str = ""
    objective_adds: str = ""
    source: str = ""
    mob_level: int = 0
    mob_count: int = 0
    live_anchor_z: bool = False
    startup_anchor: bool = False


@dataclass(frozen=True)
class RealmProfile:
    key: str
    realm_id: int
    region: int
    prefix: str
    character_prefix: str
    class_cycle: str
    race_cycle: str
    spec_cycle: str
    start: tuple[int, int, int]
    points: tuple[RoutePoint, ...]
    ground_z_map: str = ""
    startup_service_npc_name: str = ""
    growth_class_cycle: str = ""
    growth_race_cycle: str = ""
    growth_spec_cycle: str = ""


@dataclass(frozen=True)
class CharacterSnapshot:
    account: str
    name: str
    character_id: str
    level: int
    experience: int
    realm: int
    class_id: int
    specs: str
    region: int
    x: int
    y: int
    z: int
    deaths: int
    money_copper: int
    inventory_rows: int
    inventory_items: int
    serialized_abilities: str = ""


@dataclass(frozen=True)
class InventoryItem:
    account: str
    slot: int
    template_id: str
    name: str
    level: int
    dps_af: int
    spd_abs: int
    object_type: int
    item_type: int
    quality: int
    bonus: int
    allowed_classes: str
    count: int
    sell_price: int
    realm: int = 0
    type_damage: int = 0


@dataclass(frozen=True)
class GrowthPartyShareTransfer:
    source_account: str
    source_slot: int
    target_account: str
    target_slot: int
    target_equip_slot: int
    item_name: str
    candidate_score: int
    equipped_score: int


@dataclass(frozen=True)
class SegmentDbRestoreState:
    character_rows: list[dict[str, str]]
    inventory_columns: list[str]
    inventory_rows: list[dict[str, str]]


@dataclass(frozen=True)
class GrowthItemPlan:
    equip_slots: list[int]
    sell_slots: list[int]
    party_share_slots: list[int] = field(default_factory=list)
    party_share_transfers: list[GrowthPartyShareTransfer] = field(default_factory=list)
    party_share_executed_slots: list[int] = field(default_factory=list)
    party_share_received_slots: list[int] = field(default_factory=list)
    party_share_failed_slots: list[int] = field(default_factory=list)
    equip_reason: str = ""
    sell_reason: str = ""
    party_share_reason: str = ""
    party_share_execution_reason: str = ""
    merchant_npc_name: str = ""
    buy_slots: list[int] = field(default_factory=list)
    buy_inventory_slots: list[int] = field(default_factory=list)
    buy_reason: str = ""
    buy_shortage_copper: int = 0
    buy_price_copper: int = 0


@dataclass(frozen=True)
class MerchantItemCandidate:
    merchant_name: str
    item_list_id: str
    buy_slot: int
    template_id: str
    name: str
    level: int
    dps_af: int
    spd_abs: int
    object_type: int
    item_type: int
    quality: int
    bonus: int
    allowed_classes: str
    price: int
    distance: int
    realm: int = 0
    type_damage: int = 0
