#!/usr/bin/env python3
"""Poll the DummyCombat NPC API during boss dummy runs.

This is intentionally read-only.  It records boss health/combat state beside
dummy encounter logs so failed runs can be diagnosed without guessing.
"""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def fetch_json(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "npcs", "results"):
            items = payload.get(key)
            if isinstance(items, list):
                return [item for item in items if isinstance(item, dict)]
        return [payload]
    return []


def build_url(base_url: str, name: str, region: int | None, limit: int) -> str:
    query: dict[str, str] = {"limit": str(limit)}
    if name:
        query["name"] = name
    if region is not None:
        query["region"] = str(region)
    separator = "&" if "?" in base_url else "?"
    return base_url + separator + urllib.parse.urlencode(query)


def build_snapshot_url(
    npc_api_url: str,
    snapshot_api_url: str,
    name: str,
    region: int | None,
    radius: int,
    limit: int,
) -> str:
    base_url = snapshot_api_url.strip()
    if not base_url:
        base_url = npc_api_url.rsplit("/", 1)[0] + "/encounter-snapshot"

    query: dict[str, str] = {"radius": str(radius), "limit": str(limit)}
    if name:
        query["name"] = name
    if region is not None:
        query["region"] = str(region)

    separator = "&" if "?" in base_url else "?"
    return base_url + separator + urllib.parse.urlencode(query)


def pick_primary(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    if not items:
        return None
    if not name:
        return items[0]
    lowered = name.lower()
    exact = [item for item in items if str(item.get("name", "")).lower() == lowered]
    if exact:
        return exact[0]
    contains = [item for item in items if lowered in str(item.get("name", "")).lower()]
    if contains:
        return contains[0]
    return items[0]


def write_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-url", default="http://127.0.0.1:5000/api/dummy/combat/npcs")
    parser.add_argument("--name", default="")
    parser.add_argument("--region", type=int, default=None)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--interval", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--duration", type=float, default=0.0, help="0 means run until terminated")
    parser.add_argument("--snapshot-api-url", default="")
    parser.add_argument("--snapshot-radius", type=int, default=0, help="when >0, also record server-side encounter snapshots around the boss")
    parser.add_argument("--snapshot-limit", type=int, default=80)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    output = Path(args.out)
    started = time.monotonic()
    url = build_url(args.api_url, args.name, args.region, args.limit)
    snapshot_url = (
        build_snapshot_url(args.api_url, args.snapshot_api_url, args.name, args.region, args.snapshot_radius, args.snapshot_limit)
        if args.snapshot_radius > 0
        else ""
    )

    while True:
        now = time.monotonic()
        payload: dict[str, Any] = {
            "event": "boss_api_sample",
            "t": round(now, 6),
            "elapsed": round(now - started, 3),
            "url": url,
            "query_name": args.name,
            "query_region": args.region if args.region is not None else "",
        }
        try:
            items = as_list(fetch_json(url, args.timeout))
            primary = pick_primary(items, args.name)
            payload.update({"ok": True, "found": primary is not None, "count": len(items)})
            if primary is not None:
                payload.update(primary)
                if "name" in primary:
                    payload.setdefault("target_name", primary.get("name"))
            if snapshot_url:
                payload["snapshot"] = fetch_json(snapshot_url, args.timeout)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            payload.update({"ok": False, "found": False, "error": str(exc)})

        write_jsonl(output, payload)

        if args.duration > 0 and time.monotonic() - started >= args.duration:
            return 0
        time.sleep(max(args.interval, 0.2))


if __name__ == "__main__":
    raise SystemExit(main())
