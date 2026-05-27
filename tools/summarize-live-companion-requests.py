#!/usr/bin/env python3
"""Print a compact operational summary of live companion requests."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Any


def pick(row: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        if key in row and row[key] not in (None, ""):
            return row[key]
    return default


def request_summary(args: argparse.Namespace) -> dict[str, Any]:
    query: dict[str, str] = {"limit": str(args.limit)}
    if args.api_password:
        query["password"] = args.api_password
    url = f"{args.api_url.rstrip('/')}/api/dummy/companions/summary?{urllib.parse.urlencode(query)}"
    with urllib.request.urlopen(url, timeout=args.api_timeout) as response:
        payload = response.read().decode("utf-8")
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise RuntimeError(f"unexpected summary payload: {data!r}")
    return data


def format_request(prefix: str, row: dict[str, Any]) -> str:
    requester = pick(row, "requesterName", "RequesterName", default="?")
    companion = pick(row, "assignedCompanionName", "AssignedCompanionName", default="unassigned")
    role = pick(row, "requestedRole", "RequestedRole", default="?")
    status = pick(row, "status", "Status", default="?")
    message = pick(row, "message", "Message", default="")
    return f"{prefix} {requester} <- {companion} role={role} status={status} message={message}".rstrip()


def format_summary(payload: dict[str, Any]) -> list[str]:
    total = int(pick(payload, "total", "Total", default=0) or 0)
    open_count = int(pick(payload, "openCount", "OpenCount", default=0) or 0)
    active_count = int(pick(payload, "activeCount", "ActiveCount", default=0) or 0)
    lines = [f"live_companion_requests total={total} open={open_count} active={active_count}"]

    status_counts = pick(payload, "statusCounts", "StatusCounts", default={}) or {}
    if isinstance(status_counts, dict) and status_counts:
        rendered = " ".join(f"{key}={status_counts[key]}" for key in sorted(status_counts))
        lines.append(f"status_counts {rendered}")

    active = pick(payload, "active", "activeRequests", "ActiveRequests", default=[]) or []
    for row in active:
        if isinstance(row, dict):
            lines.append(format_request("active", row))

    open_rows = pick(payload, "open", "openRequests", "OpenRequests", default=[]) or []
    for row in open_rows:
        if isinstance(row, dict):
            lines.append(format_request("open", row))

    recent = pick(payload, "recent", "recentRequests", "RecentRequests", default=[]) or []
    if recent and not active and not open_rows:
        for row in recent:
            if isinstance(row, dict):
                lines.append(format_request("recent", row))

    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://localhost:5000")
    parser.add_argument("--api-timeout", type=float, default=2.0)
    parser.add_argument("--api-password", default=os.environ.get("OPENDAOC_API_PASSWORD", ""))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--json", action="store_true", help="print raw JSON summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = request_summary(args)
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    for line in format_summary(payload):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
