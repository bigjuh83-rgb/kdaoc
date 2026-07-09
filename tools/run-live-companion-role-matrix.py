#!/usr/bin/env python3
"""Run the current live-companion smoke baseline as a repeatable role matrix."""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Sequence


ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = ROOT / "tools" / "run-live-companion-party-smoke.py"
DEFAULT_PROFILES = [
    "support-crowd-control",
    "support-speed-song",
    "stealth-passive",
    "mixed-real-join",
    "tank-protection",
    "caster-dps",
    "healer-resurrection",
]
# Matrix-tail healer-resurrection can hit Broken pipe when the previous six profiles
# leave clients/accounts warm. Give accounts longer to drain and add extra settle
# before the real-join resurrection smoke.
MATRIX_ACCOUNT_OFFLINE_TIMEOUT_SECONDS = 60.0
MATRIX_PROFILE_SETTLE_SECONDS = 45.0
MATRIX_HEALER_RESURRECTION_PRE_SETTLE_SECONDS = 60.0
PROFILE_OVERRIDES: dict[str, list[str]] = {
    "healer-resurrection": [
        "--real-player-join",
        "--joiner-account",
        "albtest007",
        "--roles",
        "healer",
    ],
}


def parse_profiles(value: str) -> list[str]:
    profiles: list[str] = []
    for part in str(value or "").replace("|", ",").split(","):
        normalized = part.strip()
        if normalized and normalized not in profiles:
            profiles.append(normalized)
    return profiles


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profiles", type=parse_profiles, default=list(DEFAULT_PROFILES))
    parser.add_argument(
        "--run-root",
        type=Path,
        default=Path("test-output/live-companion-selftest/role-matrix"),
    )
    parser.add_argument("--api-url", default="http://localhost:5000")
    parser.add_argument("--account-offline-timeout", type=float, default=MATRIX_ACCOUNT_OFFLINE_TIMEOUT_SECONDS)
    parser.add_argument("--account-offline-poll-interval", type=float, default=1.0)
    parser.add_argument("--profile-settle-seconds", type=float, default=MATRIX_PROFILE_SETTLE_SECONDS)
    parser.add_argument(
        "--healer-resurrection-pre-settle-seconds",
        type=float,
        default=MATRIX_HEALER_RESURRECTION_PRE_SETTLE_SECONDS,
        help="Extra settle time before the matrix-tail healer-resurrection profile.",
    )
    parser.add_argument("--replace", action="store_true")
    return parser


def build_profile_command(profile: str, args: argparse.Namespace, passthrough: Sequence[str]) -> list[str]:
    run_dir = Path(args.run_root) / profile
    command = [
        sys.executable,
        str(SMOKE_SCRIPT),
        "--smoke-profile",
        profile,
        "--run-dir",
        str(run_dir),
    ]
    if args.replace:
        command.append("--replace")
    command.extend(PROFILE_OVERRIDES.get(profile, []))
    command.extend(passthrough)
    return command


def run_profile(profile: str, args: argparse.Namespace, passthrough: Sequence[str]) -> dict[str, object]:
    command = build_profile_command(profile, args, passthrough)
    print(f"=== profile={profile} run_dir={Path(args.run_root) / profile} ===")
    completed = subprocess.run(command, cwd=ROOT)
    result = {
        "profile": profile,
        "run_dir": str(Path(args.run_root) / profile),
        "return_code": int(completed.returncode),
    }
    print(f"=== profile={profile} return_code={completed.returncode} ===")
    return result


def profile_player_accounts(run_dir: Path) -> list[str]:
    accounts_path = Path(run_dir) / "player-accounts.csv"
    try:
        with accounts_path.open(encoding="utf-8-sig", newline="") as handle:
            rows = csv.DictReader(handle)
            accounts: list[str] = []
            seen: set[str] = set()
            for row in rows:
                account = str(row.get("username") or row.get("account") or "").strip()
                normalized = account.lower()
                if not account or normalized in seen:
                    continue
                seen.add(normalized)
                accounts.append(account)
            return accounts
    except OSError:
        return []


def api_json(api_url: str, path: str, query: dict[str, object] | None = None, *, timeout: float = 2.0) -> object | None:
    clean_query = {
        key: value
        for key, value in (query or {}).items()
        if value not in (None, "")
    }
    query_string = urllib.parse.urlencode(clean_query)
    url = f"{str(api_url).rstrip('/')}{path}" + (f"?{query_string}" if query_string else "")
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail or f"GET {url} failed with HTTP {exc.code}") from exc
    if not payload:
        return None
    return json.loads(payload)


def fetch_player_state(api_url: str, account: str, *, timeout: float = 2.0) -> dict[str, object] | None:
    payload = api_json(
        api_url,
        "/api/dummy/combat/usable",
        {"account": account},
        timeout=timeout,
    )
    if isinstance(payload, dict) and isinstance(payload.get("player"), dict):
        return payload
    return None


def wait_for_accounts_offline(
    api_url: str,
    accounts: Sequence[str],
    *,
    timeout: float = 45.0,
    poll_interval: float = 1.0,
) -> bool:
    pending = [str(account).strip() for account in accounts if str(account).strip()]
    if not pending:
        return True

    deadline = time.monotonic() + max(0.0, float(timeout))
    request_timeout = max(0.5, min(float(poll_interval or 1.0), 5.0))
    sleep_seconds = max(0.1, float(poll_interval or 1.0))

    while True:
        still_online = [
            account
            for account in pending
            if fetch_player_state(api_url, account, timeout=request_timeout) is not None
        ]
        if not still_online:
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(sleep_seconds)
        pending = still_online


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, passthrough = parser.parse_known_args(argv)

    results: list[dict[str, object]] = []
    for index, profile in enumerate(args.profiles):
        pre_settle = float(getattr(args, "healer_resurrection_pre_settle_seconds", 0.0) or 0.0)
        if profile == "healer-resurrection" and pre_settle > 0.0:
            print(f"=== profile={profile} pre_settle={pre_settle}s ===")
            time.sleep(pre_settle)
        result = run_profile(profile, args, passthrough)
        results.append(result)
        if index < len(args.profiles) - 1:
            accounts = profile_player_accounts(Path(result["run_dir"]))
            if accounts and not wait_for_accounts_offline(
                args.api_url,
                accounts,
                timeout=float(args.account_offline_timeout),
                poll_interval=float(args.account_offline_poll_interval),
            ):
                print(
                    json.dumps(
                        {
                            "results": results,
                            "error": {
                                "profile": profile,
                                "type": "accounts_not_offline",
                                "accounts": accounts,
                            },
                        },
                        ensure_ascii=False,
                    )
                )
                return 2
            if float(args.profile_settle_seconds) > 0:
                time.sleep(float(args.profile_settle_seconds))
    print(json.dumps({"results": results}, ensure_ascii=False))
    return 0 if all(int(result["return_code"]) == 0 for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
