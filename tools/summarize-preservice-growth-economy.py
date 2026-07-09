#!/usr/bin/env python3
"""Summarize pre-service growth loot, economy, and bottleneck data."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


TIER_FIELDS = (
    "loot_tier_common",
    "loot_tier_magic",
    "loot_tier_rare",
    "loot_tier_heroic",
    "loot_tier_legendary",
    "loot_tier_mythic",
)


def to_int(value: object) -> int:
    try:
        return int(float(str(value or "0").strip() or "0"))
    except ValueError:
        return 0


def to_float(value: object) -> float:
    try:
        return float(str(value or "0").strip() or "0")
    except ValueError:
        return 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def ratio(numerator: float, denominator: float) -> str:
    if denominator <= 0:
        return "0.000"
    return f"{numerator / denominator:.3f}"


def count_non_empty(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if str(row.get(field, "") or "").strip())


def sum_fields(rows: list[dict[str, str]], *fields: str) -> int:
    return sum(sum(to_int(row.get(field)) for field in fields) for row in rows)


def top_reasons(rows: list[dict[str, str]], limit: int = 5) -> str:
    counter: Counter[str] = Counter()
    for row in rows:
        for token in str(row.get("bottleneck_reason", "") or "").split(";"):
            reason = token.strip()
            if reason:
                counter[reason] += 1
    return ";".join(f"{reason}:{count}" for reason, count in counter.most_common(limit))


def first_last_timestamp(rows: list[dict[str, str]]) -> tuple[str, str]:
    values = sorted(str(row.get("timestamp_utc", "") or "") for row in rows if row.get("timestamp_utc"))
    if not values:
        return "", ""
    return values[0], values[-1]


def elapsed_minutes(rows: list[dict[str, str]]) -> str:
    start_text, end_text = first_last_timestamp(rows)
    if not start_text or not end_text:
        return "0.0"
    try:
        start = datetime.fromisoformat(start_text.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_text.replace("Z", "+00:00"))
    except ValueError:
        return "0.0"
    return f"{max(0.0, (end - start).total_seconds() / 60.0):.1f}"


def summarize_scope(rows: list[dict[str, str]], prefix: str) -> dict[str, object]:
    target_removed = sum_fields(rows, "target_removed")
    loot_acquired = sum_fields(rows, "loot_acquired")
    random_loot = sum_fields(rows, *TIER_FIELDS)
    return {
        f"{prefix}_rows": len(rows),
        f"{prefix}_max_level": max((to_int(row.get("level_after")) for row in rows), default=0),
        f"{prefix}_level_delta": sum_fields(rows, "level_delta"),
        f"{prefix}_wall_minutes": f"{sum(to_float(row.get('elapsed_seconds')) for row in rows) / 60.0:.1f}",
        f"{prefix}_xp_effective": sum_fields(rows, "xp_effective_delta"),
        f"{prefix}_money_copper": sum_fields(rows, "money_delta_copper"),
        f"{prefix}_target_removed": target_removed,
        f"{prefix}_loot_acquired": loot_acquired,
        f"{prefix}_loot_per_target": ratio(loot_acquired, target_removed),
        f"{prefix}_random_loot_total": random_loot,
        f"{prefix}_random_loot_per_target": ratio(random_loot, target_removed),
        f"{prefix}_loot_tier_common": sum_fields(rows, "loot_tier_common"),
        f"{prefix}_loot_tier_magic": sum_fields(rows, "loot_tier_magic"),
        f"{prefix}_loot_tier_rare": sum_fields(rows, "loot_tier_rare"),
        f"{prefix}_loot_tier_heroic": sum_fields(rows, "loot_tier_heroic"),
        f"{prefix}_loot_tier_legendary": sum_fields(rows, "loot_tier_legendary"),
        f"{prefix}_loot_tier_mythic": sum_fields(rows, "loot_tier_mythic"),
        f"{prefix}_weapon_delta": sum_fields(rows, "weapon_items_delta"),
        f"{prefix}_armor_delta": sum_fields(rows, "armor_items_delta"),
        f"{prefix}_equipment_other_delta": sum_fields(rows, "equipment_other_items_delta"),
        f"{prefix}_junk_delta": sum_fields(rows, "junk_items_delta"),
        f"{prefix}_sellable_junk_delta": sum_fields(rows, "sellable_junk_items_delta"),
        f"{prefix}_sellable_junk_value_delta": sum_fields(rows, "sellable_junk_value_copper_delta"),
        f"{prefix}_equip_candidate_rows": count_non_empty(rows, "equip_candidate_slots"),
        f"{prefix}_sell_candidate_rows": count_non_empty(rows, "sell_candidate_slots"),
        f"{prefix}_party_share_candidate_rows": count_non_empty(rows, "party_share_candidate_slots"),
        f"{prefix}_party_share_received_rows": count_non_empty(rows, "party_share_received_slots"),
        f"{prefix}_merchant_sell_actions": sum_fields(rows, "startup_merchant_sell"),
        f"{prefix}_merchant_buy_actions": sum_fields(rows, "startup_merchant_buy"),
        f"{prefix}_merchant_equip_actions": sum_fields(rows, "startup_merchant_equip"),
        f"{prefix}_buy_shortage_copper": sum_fields(rows, "buy_shortage_copper"),
        f"{prefix}_deaths": sum_fields(rows, "death_delta"),
        f"{prefix}_top_bottlenecks": top_reasons(rows),
    }


def latest_by_case(rows: list[dict[str, str]], field: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for row in rows:
        case_id = str(row.get("case_id", "") or row.get("supervisor_case_id", "") or "").strip()
        if case_id:
            values[case_id] = str(row.get(field, "") or "")
    return values


def build_summary(run_dir: Path) -> list[dict[str, object]]:
    timeline = read_csv(run_dir / "aggregate-timeline.csv")
    status_rows = read_csv(run_dir / "case-status.csv")
    bottleneck_rows = read_csv(run_dir / "bottleneck-ledger.csv")

    timeline_by_case: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in timeline:
        case_id = str(row.get("supervisor_case_id", "") or row.get("case", "") or "").strip()
        if case_id:
            timeline_by_case[case_id].append(row)

    status_by_case = {str(row.get("case_id", "") or "").strip(): row for row in status_rows}
    latest_bottleneck_reason = latest_by_case(bottleneck_rows, "reason")

    rows: list[dict[str, object]] = []
    for case_id in sorted(set(timeline_by_case) | set(status_by_case)):
        case_rows = timeline_by_case.get(case_id, [])
        status = status_by_case.get(case_id, {})
        tracked_rows = [
            row
            for row in case_rows
            if str(row.get("growth_role", "") or "").strip().lower() in {"", "tracked"}
        ]
        first_seen, last_seen = first_last_timestamp(case_rows)
        output: dict[str, object] = {
            "case_id": case_id,
            "variant": status.get("variant") or (case_rows[-1].get("variant") if case_rows else ""),
            "realm": status.get("realm") or (case_rows[-1].get("realm") if case_rows else ""),
            "party_size": status.get("party_size") or (case_rows[-1].get("party_size") if case_rows else ""),
            "status": status.get("status", ""),
            "next_segment": status.get("next_segment", ""),
            "last_passed_segment": status.get("last_passed_segment", ""),
            "attempt": status.get("attempt", ""),
            "first_seen_utc": first_seen,
            "last_seen_utc": last_seen,
            "case_elapsed_minutes": elapsed_minutes(case_rows),
            "latest_bottleneck_reason": latest_bottleneck_reason.get(case_id, ""),
            "last_error": status.get("last_error", ""),
        }
        output.update(summarize_scope(tracked_rows, "tracked"))
        output.update(summarize_scope(case_rows, "party_total"))
        rows.append(output)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, rows: list[dict[str, object]]) -> None:
    problem_rows = [
        row
        for row in rows
        if str(row.get("status", "")) == "quarantined"
        or to_int(row.get("tracked_buy_shortage_copper")) > 0
        or to_int(row.get("tracked_deaths")) > 0
    ]
    total_targets = sum(to_int(row.get("party_total_target_removed")) for row in rows)
    total_loot = sum(to_int(row.get("party_total_loot_acquired")) for row in rows)
    total_random = sum(to_int(row.get("party_total_random_loot_total")) for row in rows)
    total_equip_candidates = sum(to_int(row.get("party_total_equip_candidate_rows")) for row in rows)
    total_sell_candidates = sum(to_int(row.get("party_total_sell_candidate_rows")) for row in rows)
    total_share_candidates = sum(to_int(row.get("party_total_party_share_candidate_rows")) for row in rows)
    total_share_received = sum(to_int(row.get("party_total_party_share_received_rows")) for row in rows)
    total_merchant_sells = sum(to_int(row.get("party_total_merchant_sell_actions")) for row in rows)
    total_merchant_buys = sum(to_int(row.get("party_total_merchant_buy_actions")) for row in rows)
    total_merchant_equips = sum(to_int(row.get("party_total_merchant_equip_actions")) for row in rows)
    lines = [
        "# Pre-service growth loot/economy snapshot",
        "",
        f"- cases: {len(rows)}",
        f"- quarantined: {sum(1 for row in rows if row.get('status') == 'quarantined')}",
        f"- target removed: {total_targets}",
        f"- loot acquired: {total_loot} ({ratio(total_loot, total_targets)} per target)",
        f"- corrected random loot total: {total_random} ({ratio(total_random, total_targets)} per target)",
        f"- equip candidate rows: {total_equip_candidates}",
        f"- sell candidate rows: {total_sell_candidates}",
        f"- party share candidates/received rows: {total_share_candidates}/{total_share_received}",
        f"- merchant sell/buy/equip actions: {total_merchant_sells}/{total_merchant_buys}/{total_merchant_equips}",
        f"- loot tiers common/magic/rare/heroic/legendary/mythic: "
        f"{sum(to_int(row.get('party_total_loot_tier_common')) for row in rows)}/"
        f"{sum(to_int(row.get('party_total_loot_tier_magic')) for row in rows)}/"
        f"{sum(to_int(row.get('party_total_loot_tier_rare')) for row in rows)}/"
        f"{sum(to_int(row.get('party_total_loot_tier_heroic')) for row in rows)}/"
        f"{sum(to_int(row.get('party_total_loot_tier_legendary')) for row in rows)}/"
        f"{sum(to_int(row.get('party_total_loot_tier_mythic')) for row in rows)}",
        "",
        "## Problem cases",
        "",
        "| case | status | tracked level | targets | loot | random | equip | sell | share | merchant s/b/e | money | shortage | deaths | bottleneck |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in sorted(problem_rows, key=lambda item: (str(item.get("status", "")), str(item.get("case_id", "")))):
        bottleneck = str(row.get("latest_bottleneck_reason") or row.get("tracked_top_bottlenecks") or "")[:120]
        merchant_summary = (
            f"{to_int(row.get('party_total_merchant_sell_actions'))}/"
            f"{to_int(row.get('party_total_merchant_buy_actions'))}/"
            f"{to_int(row.get('party_total_merchant_equip_actions'))}"
        )
        lines.append(
            "| {case_id} | {status} | {tracked_max_level} | {tracked_target_removed} | "
            "{tracked_loot_acquired} | {tracked_random_loot_total} | {party_total_equip_candidate_rows} | "
            "{party_total_sell_candidate_rows} | {party_total_party_share_received_rows} | {merchant_summary} | "
            "{tracked_money_copper} | {tracked_buy_shortage_copper} | {tracked_deaths} | {bottleneck} |".format(
                bottleneck=bottleneck.replace("|", "/"),
                merchant_summary=merchant_summary,
                **row,
            )
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--output-csv", type=Path, default=None)
    parser.add_argument("--output-md", type=Path, default=None)
    args = parser.parse_args()

    run_dir = args.run_dir
    rows = build_summary(run_dir)
    csv_path = args.output_csv or run_dir / "loot-economy-bottleneck-summary.csv"
    md_path = args.output_md or run_dir / "loot-economy-bottleneck-summary.md"
    write_csv(csv_path, rows)
    write_markdown(md_path, rows)
    print(f"wrote {csv_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
