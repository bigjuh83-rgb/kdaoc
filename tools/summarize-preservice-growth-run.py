#!/usr/bin/env python3
"""Summarize a pre-service growth supervisor run for operations review."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size <= 0:
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_int(value: Any) -> int:
    try:
        return int(float(str(value or "0").strip() or "0"))
    except ValueError:
        return 0


def as_float(value: Any) -> float:
    try:
        return float(str(value or "0").strip() or "0")
    except ValueError:
        return 0.0


def unique_count(rows: Iterable[dict[str, str]], field: str) -> int:
    return len({row.get(field, "") for row in rows if row.get(field, "")})


def csv_join(values: Iterable[Any]) -> str:
    return ",".join(str(value) for value in values)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def group_summary(rows: list[dict[str, str]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(field, "") for field in fields)].append(row)

    summaries: list[dict[str, Any]] = []
    for key, group_rows in sorted(grouped.items()):
        summary = {field: value for field, value in zip(fields, key)}
        summary.update(
            {
                "rows": len(group_rows),
                "cases": unique_count(group_rows, "supervisor_case_id"),
                "accounts": unique_count(group_rows, "account"),
                "segments": unique_count(group_rows, "segment"),
                "max_level": max((as_int(row.get("level_after")) for row in group_rows), default=0),
                "level_delta": sum(as_int(row.get("level_delta")) for row in group_rows),
                "xp_effective_delta": sum(as_int(row.get("xp_effective_delta")) for row in group_rows),
                "money_delta_copper": sum(as_int(row.get("money_delta_copper")) for row in group_rows),
                "inventory_items_delta": sum(as_int(row.get("inventory_items_delta")) for row in group_rows),
                "weapon_items_delta": sum(as_int(row.get("weapon_items_delta")) for row in group_rows),
                "armor_items_delta": sum(as_int(row.get("armor_items_delta")) for row in group_rows),
                "equipment_other_items_delta": sum(as_int(row.get("equipment_other_items_delta")) for row in group_rows),
                "junk_items_delta": sum(as_int(row.get("junk_items_delta")) for row in group_rows),
                "total_sell_value_copper_delta": sum(as_int(row.get("total_sell_value_copper_delta")) for row in group_rows),
                "loot_acquired": sum(as_int(row.get("loot_acquired")) for row in group_rows),
                "train_command_sent": sum(as_int(row.get("train_command_sent")) for row in group_rows),
                "train_verified": sum(as_int(row.get("train_verified")) for row in group_rows),
                "buy_shortage_copper": sum(as_int(row.get("buy_shortage_copper")) for row in group_rows),
                "buy_shortage_rows": sum(1 for row in group_rows if as_int(row.get("buy_shortage_copper")) > 0),
                "deaths": sum(as_int(row.get("death_delta") or row.get("player_deaths")) for row in group_rows),
                "target_removed": sum(as_int(row.get("target_removed")) for row in group_rows),
                "target_timeouts": sum(as_int(row.get("target_timeouts")) for row in group_rows),
                "combat_failures": sum(as_int(row.get("combat_failures")) for row in group_rows),
                "server_los_failures": sum(as_int(row.get("server_los_failures")) for row in group_rows),
                "movement_failures": sum(as_int(row.get("movement_failures")) for row in group_rows),
                "elapsed_seconds": round(sum(as_float(row.get("elapsed_seconds")) for row in group_rows), 3),
                "xp_per_hour": round(
                    sum(as_float(row.get("xp_effective_delta")) for row in group_rows)
                    * 3600
                    / max(1.0, sum(as_float(row.get("elapsed_seconds")) for row in group_rows)),
                    3,
                ),
                "money_per_hour": round(
                    sum(as_float(row.get("money_delta_copper")) for row in group_rows)
                    * 3600
                    / max(1.0, sum(as_float(row.get("elapsed_seconds")) for row in group_rows)),
                    3,
                ),
            }
        )
        summaries.append(summary)
    return summaries


def top_counter(rows: Iterable[dict[str, str]], field: str, *, limit: int = 10) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for row in rows:
        value = " ".join(str(row.get(field, "") or "").split())
        if value:
            counter[value] += 1
    return counter.most_common(limit)


def collect_bottlenecks(rows: list[dict[str, str]], *, limit: int = 100) -> list[dict[str, Any]]:
    bottlenecks: list[dict[str, Any]] = []
    for row in rows:
        checks = [
            ("buy_shortage", as_int(row.get("buy_shortage_copper")) > 0, row.get("buy_candidate_reason", "")),
            ("death", as_int(row.get("death_delta") or row.get("player_deaths")) > 0, "death during segment"),
            ("movement_failure", as_int(row.get("movement_failures")) > 0, "movement failure"),
            ("target_timeout", as_int(row.get("target_timeouts")) > 0, "target timeout"),
            ("combat_failure", as_int(row.get("combat_failures")) > 0, "combat failure"),
            ("xp_persist_lag", row.get("xp_persist_status") not in {"", "synced"}, row.get("xp_persist_status", "")),
        ]
        for kind, active, reason in checks:
            if active:
                bottlenecks.append(
                    {
                        "kind": kind,
                        "case": row.get("supervisor_case_id") or row.get("case"),
                        "variant": row.get("variant", ""),
                        "realm": row.get("realm", ""),
                        "party_size": row.get("party_size", ""),
                        "segment": row.get("segment", ""),
                        "account": row.get("account", ""),
                        "level_after": row.get("level_after", ""),
                        "reason": reason,
                        "buy_shortage_copper": row.get("buy_shortage_copper", ""),
                        "movement_failures": row.get("movement_failures", ""),
                        "target_timeouts": row.get("target_timeouts", ""),
                        "combat_failures": row.get("combat_failures", ""),
                    }
                )
    return bottlenecks[:limit]


def parse_loot_report_line(line: str) -> tuple[str, str, str, str] | None:
    stripped = line.strip()
    if not stripped.startswith("| `") or stripped.startswith("| `none`"):
        return None
    parts = [part.strip() for part in stripped.strip("|").split("|")]
    if len(parts) < 4:
        return None
    account = parts[0].strip("` ")
    round_index = parts[1].strip()
    tier = parts[2].strip("` ")
    item = "|".join(parts[3:]).strip()
    if not account or account == "Account":
        return None
    return account, round_index, tier, item


def collect_loot_samples(run_dir: Path, *, limit: int = 30) -> list[dict[str, str]]:
    samples: list[dict[str, str]] = []
    for report in sorted((run_dir / "cases").glob("*/*/segment-*-report.md")):
        in_loot_table = False
        try:
            lines = report.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            if line.startswith("| Account | Round | Tier | Item |"):
                in_loot_table = True
                continue
            if in_loot_table and not line.startswith("|"):
                in_loot_table = False
            if not in_loot_table:
                continue
            parsed = parse_loot_report_line(line)
            if not parsed:
                continue
            account, round_index, tier, item = parsed
            samples.append(
                {
                    "case": report.parent.parent.name,
                    "segment_report": str(report),
                    "account": account,
                    "round": round_index,
                    "tier": tier,
                    "item": item,
                }
            )
            if len(samples) >= limit:
                return samples
    return samples


def markdown_table(rows: list[dict[str, Any]], fields: list[str], *, limit: int = 20) -> list[str]:
    lines = [
        "| " + " | ".join(fields) + " |",
        "| " + " | ".join("---" for _field in fields) + " |",
    ]
    for row in rows[:limit]:
        lines.append("| " + " | ".join(str(row.get(field, "")) for field in fields) + " |")
    if not rows:
        lines.append("| " + " | ".join("none" if index == 0 else "0" for index, _field in enumerate(fields)) + " |")
    return lines


def write_markdown(
    path: Path,
    *,
    run_dir: Path,
    timeline_rows: list[dict[str, str]],
    status_rows: list[dict[str, str]],
    by_variant: list[dict[str, Any]],
    by_realm_variant: list[dict[str, Any]],
    bottlenecks: list[dict[str, Any]],
    loot_samples: list[dict[str, str]],
) -> None:
    status_counts = Counter(row.get("status", "") for row in status_rows)
    levels = [as_int(row.get("level_after")) for row in timeline_rows]
    lines = [
        "# Pre-Service Growth Operational Summary",
        "",
        f"- Generated UTC: `{utc_now()}`",
        f"- Run dir: `{run_dir}`",
        f"- Timeline rows: `{len(timeline_rows)}`",
        f"- Cases with data: `{unique_count(timeline_rows, 'supervisor_case_id')}`",
        f"- Accounts with data: `{unique_count(timeline_rows, 'account')}`",
        f"- Highest observed level: `{max(levels) if levels else 0}`",
        f"- Status counts: `{dict(sorted(status_counts.items()))}`",
        f"- XP effective delta: `{sum(as_int(row.get('xp_effective_delta')) for row in timeline_rows)}`",
        f"- Money delta copper: `{sum(as_int(row.get('money_delta_copper')) for row in timeline_rows)}`",
        f"- Weapon item delta: `{sum(as_int(row.get('weapon_items_delta')) for row in timeline_rows)}`",
        f"- Armor item delta: `{sum(as_int(row.get('armor_items_delta')) for row in timeline_rows)}`",
        f"- Equipment-other item delta: `{sum(as_int(row.get('equipment_other_items_delta')) for row in timeline_rows)}`",
        f"- Junk item delta: `{sum(as_int(row.get('junk_items_delta')) for row in timeline_rows)}`",
        f"- Total sell value delta copper: `{sum(as_int(row.get('total_sell_value_copper_delta')) for row in timeline_rows)}`",
        f"- Loot acquired: `{sum(as_int(row.get('loot_acquired')) for row in timeline_rows)}`",
        f"- Buy shortage copper: `{sum(as_int(row.get('buy_shortage_copper')) for row in timeline_rows)}`",
        f"- Deaths: `{sum(as_int(row.get('death_delta') or row.get('player_deaths')) for row in timeline_rows)}`",
        "",
        "## By Variant",
        "",
        *markdown_table(
            by_variant,
            [
                "variant",
                "rows",
                "cases",
                "accounts",
                "max_level",
                "xp_effective_delta",
                "money_delta_copper",
                "weapon_items_delta",
                "armor_items_delta",
                "junk_items_delta",
                "total_sell_value_copper_delta",
                "loot_acquired",
                "buy_shortage_copper",
                "deaths",
                "movement_failures",
            ],
        ),
        "",
        "## By Realm And Variant",
        "",
        *markdown_table(
            by_realm_variant,
            [
                "realm",
                "variant",
                "cases",
                "accounts",
                "max_level",
                "xp_effective_delta",
                "money_delta_copper",
                "weapon_items_delta",
                "armor_items_delta",
                "junk_items_delta",
                "total_sell_value_copper_delta",
                "loot_acquired",
                "target_removed",
                "deaths",
            ],
            limit=30,
        ),
        "",
        "## Bottleneck Samples",
        "",
        *markdown_table(
            bottlenecks,
            [
                "kind",
                "case",
                "variant",
                "realm",
                "segment",
                "account",
                "level_after",
                "reason",
                "buy_shortage_copper",
            ],
            limit=25,
        ),
        "",
        "## Top Reasons",
        "",
        "- Buy reasons: "
        + csv_join(f"{reason}={count}" for reason, count in top_counter(timeline_rows, "buy_candidate_reason")),
        "- Sell reasons: "
        + csv_join(f"{reason}={count}" for reason, count in top_counter(timeline_rows, "sell_candidate_reason")),
        "- Equip reasons: "
        + csv_join(f"{reason}={count}" for reason, count in top_counter(timeline_rows, "equip_candidate_reason")),
        "",
        "## Loot Samples",
        "",
        *markdown_table(loot_samples, ["case", "account", "round", "tier", "item"], limit=30),
        "",
        "## Output Files",
        "",
        f"- By variant CSV: `{path.with_name('operational-summary-by-variant.csv')}`",
        f"- By realm/variant CSV: `{path.with_name('operational-summary-by-realm-variant.csv')}`",
        f"- Bottlenecks CSV: `{path.with_name('operational-bottlenecks.csv')}`",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--output", default="")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir)
    output = Path(args.output) if args.output else run_dir / "operational-summary.md"
    timeline_rows = read_csv_rows(run_dir / "aggregate-timeline.csv")
    status_rows = read_csv_rows(run_dir / "case-status.csv")
    by_variant = group_summary(timeline_rows, ("variant",))
    by_realm_variant = group_summary(timeline_rows, ("realm", "variant"))
    bottlenecks = collect_bottlenecks(timeline_rows)
    loot_samples = collect_loot_samples(run_dir)

    write_csv(output.with_name("operational-summary-by-variant.csv"), by_variant, list(by_variant[0].keys()) if by_variant else ["variant"])
    write_csv(
        output.with_name("operational-summary-by-realm-variant.csv"),
        by_realm_variant,
        list(by_realm_variant[0].keys()) if by_realm_variant else ["realm", "variant"],
    )
    write_csv(
        output.with_name("operational-bottlenecks.csv"),
        bottlenecks,
        list(bottlenecks[0].keys())
        if bottlenecks
        else [
            "kind",
            "case",
            "variant",
            "realm",
            "party_size",
            "segment",
            "account",
            "level_after",
            "reason",
            "buy_shortage_copper",
            "movement_failures",
            "target_timeouts",
            "combat_failures",
        ],
    )
    write_markdown(
        output,
        run_dir=run_dir,
        timeline_rows=timeline_rows,
        status_rows=status_rows,
        by_variant=by_variant,
        by_realm_variant=by_realm_variant,
        bottlenecks=bottlenecks,
        loot_samples=loot_samples,
    )
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
