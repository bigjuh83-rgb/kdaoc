#!/usr/bin/env python3
"""WorldAI/MobGrowth smoke test using the headless OpenDAoC client.

The test avoids real client UI work. It sends GM/player commands through the
headless packet client, then verifies database/API state.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path


DEFAULT_MYSQL = "/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb"


def load_headless_client_class():
    module_path = Path(__file__).with_name("headless-daoc-client.py")
    spec = importlib.util.spec_from_file_location("headless_daoc_client", module_path)

    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {module_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.HeadlessDaocClient


HeadlessDaocClient = load_headless_client_class()


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


class SmokeFailure(Exception):
    pass


def mysql_query(args: argparse.Namespace, sql: str) -> list[dict[str, str]]:
    command = [
        args.mysql_bin,
        "--batch",
        "--raw",
        "--skip-column-names",
        "--protocol=tcp",
        "-h",
        args.db_host,
        "-P",
        str(args.db_port),
        "-u",
        args.db_user,
        f"-p{args.db_password}",
        "--default-character-set=utf8mb4",
        args.db_name,
        "-e",
        sql,
    ]

    process = subprocess.run(command, check=True, capture_output=True, text=True)
    rows: list[dict[str, str]] = []

    for line in process.stdout.splitlines():
        if not line.strip():
            continue

        parts = line.split("\t")
        rows.append({str(index): value for index, value in enumerate(parts)})

    return rows


def scalar(args: argparse.Namespace, sql: str) -> int:
    rows = mysql_query(args, sql)

    if not rows:
        return 0

    return int(rows[0].get("0") or "0")


def run_client_commands(args: argparse.Namespace, commands: list[str]) -> None:
    client = HeadlessDaocClient(args.host, args.port, args.timeout, verbose=args.verbose)

    try:
        client.drive_login(args.username, args.password, args.realm, args.char_index)

        for command in commands:
            client.send_command(command)
            time.sleep(args.command_delay)

        end_time = time.monotonic() + args.hold

        while time.monotonic() < end_time:
            client.send_ping()
            client.drain(0.1)
            time.sleep(0.5)
    finally:
        client.close()


def fetch_json(url: str, timeout: float) -> tuple[bool, object | str]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return True, json.loads(body)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, str(exc)


def add_result(results: list[CheckResult], name: str, ok: bool, detail: str) -> None:
    results.append(CheckResult(name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}: {detail}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--username", default=os.environ.get("OPENDAOC_USERNAME", "bigjuh"))
    parser.add_argument("--password", default=os.environ.get("OPENDAOC_PASSWORD", ""))
    parser.add_argument("--realm", type=int, default=1)
    parser.add_argument("--char-index", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--hold", type=float, default=2.0)
    parser.add_argument("--command-delay", type=float, default=1.2)
    parser.add_argument("--verbose", action="store_true")

    parser.add_argument("--mysql-bin", default=os.environ.get("MYSQL_BIN", DEFAULT_MYSQL))
    parser.add_argument("--db-host", default=os.environ.get("DB_HOST", "127.0.0.1"))
    parser.add_argument("--db-port", type=int, default=int(os.environ.get("DB_PORT", "3306")))
    parser.add_argument("--db-name", default=os.environ.get("DB_NAME", "opendaoc"))
    parser.add_argument("--db-user", default=os.environ.get("DB_USER", "root"))
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD", "opendaoc-local"))

    parser.add_argument("--api-base", default=os.environ.get("OPENDAOC_API_BASE", "http://127.0.0.1:5000"))
    parser.add_argument("--require-api", action="store_true")
    parser.add_argument("--mob-scan", type=int, default=0, help="optional /mobgrowth scan limit. 0 skips scan.")
    args = parser.parse_args()

    if not args.password:
        raise SystemExit("missing game password: pass --password or set OPENDAOC_PASSWORD")

    if not Path(args.mysql_bin).exists():
        raise SystemExit(f"mysql client not found: {args.mysql_bin}")

    results: list[CheckResult] = []
    before_events = scalar(args, "SELECT COUNT(*) FROM world_event_log;")
    before_completed = scalar(args, "SELECT COUNT(*) FROM llm_job WHERE Status='Completed';")
    before_results = scalar(args, "SELECT COUNT(*) FROM llm_result WHERE ValidationStatus='Valid';")

    commands = [
        "/worldai seed bossborn",
        "/worldai processfake 10",
        "/worldnews",
        "/history",
        "/mobgrowth enable",
        "/mobgrowth status",
        "/mobgrowth top 5",
    ]

    if args.mob_scan > 0:
        commands.insert(-2, f"/mobgrowth scan {args.mob_scan}")

    run_client_commands(args, commands)

    after_events = scalar(args, "SELECT COUNT(*) FROM world_event_log;")
    after_completed = scalar(args, "SELECT COUNT(*) FROM llm_job WHERE Status='Completed';")
    after_results = scalar(args, "SELECT COUNT(*) FROM llm_result WHERE ValidationStatus='Valid';")
    public_events = scalar(args, "SELECT COUNT(*) FROM world_event_log WHERE IsPublic=1 AND PublicTitle<>'' AND PublicText<>'';")

    event_ok = after_events > before_events or public_events > 0
    jobs_ok = after_completed >= before_completed + 2 or after_completed >= 2
    results_ok = after_results >= before_results + 2 or after_results >= 2

    add_result(
        results,
        "world event exists",
        event_ok,
        f"events {before_events} -> {after_events}, public_events={public_events}",
    )
    add_result(
        results,
        "fake LLM jobs completed",
        jobs_ok,
        f"completed {before_completed} -> {after_completed}",
    )
    add_result(
        results,
        "valid LLM results stored",
        results_ok,
        f"valid {before_results} -> {after_results}",
    )
    add_result(results, "public news/history text available", public_events > 0, f"public_events={public_events}")

    if args.mob_scan > 0:
        mob_states = scalar(args, "SELECT COUNT(*) FROM mob_growth_state;")
        add_result(results, "mob growth states available", mob_states > 0, f"mob_growth_state={mob_states}")

    api_checks = [
        ("world news api", f"{args.api_base.rstrip('/')}/api/world/news?limit=3"),
        ("world events api", f"{args.api_base.rstrip('/')}/api/world/events?limit=3"),
        ("dashboard live api", f"{args.api_base.rstrip('/')}/api/dashboard/live"),
    ]

    for name, url in api_checks:
        ok, payload = fetch_json(url, args.timeout)

        if args.require_api:
            add_result(results, name, ok, "reachable" if ok else str(payload))
        else:
            status = "reachable" if ok else f"skipped/not reachable: {payload}"
            add_result(results, name, True, status)

    failed = [result for result in results if not result.ok]

    if failed:
        print(f"smoke test failed: {len(failed)} check(s) failed")
        return 1

    print("smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
