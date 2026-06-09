#!/usr/bin/env python3
"""Launch solo + party + boss observation dummy sessions (non-stealth only)."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OUTPUT = TOOLS / "test-output" / "observation-dummies"
SESSION = TOOLS / "run-multi-dummy-movement-session.py"
CLEANUP = TOOLS / "cleanup-movement-dummies.py"

SCENARIOS = (
    {
        "key": "solo",
        "prefix": "solohunt",
        "names": "솔온|솔론",
        "args": ["--solo-hunt", "--count", "2"],
        "note": "Cotswold solo hunt x2 (Armsman/Mercenary)",
    },
    {
        "key": "party",
        "prefix": "parthunt",
        "names": "가온|라온|이든|하람",
        "args": ["--party-hunt", "--count", "4"],
        "note": "Cotswold 4-person party hunt",
    },
    {
        "key": "boss",
        "prefix": "bosshunt",
        "names": "보운|보헴|보온|보윤|보검|보랑|보혜|보라",
        "args": ["--boss-hunt", "--count", "8"],
        "note": "Giant boar L34 boss party x8 (L50)",
    },
)


def build_command(scenario: dict[str, str], hold: float, ramp_up: float, audit: bool) -> list[str]:
    command = [
        sys.executable,
        str(SESSION),
        *scenario["args"],
        "--prefix",
        scenario["prefix"],
        "--character-names",
        scenario["names"],
        "--hold",
        str(hold),
        "--ramp-up",
        str(ramp_up),
        "--position-step",
        "80" if scenario["key"] == "boss" else "180",
    ]
    if audit:
        command.append("--audit")
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Run observation dummy sessions (solo/party/boss)")
    parser.add_argument("--hold", type=float, default=600.0, help="seconds each session stays online")
    parser.add_argument("--ramp-up", type=float, default=6.0)
    parser.add_argument("--audit", action="store_true", help="enable movement audit on all dummies")
    parser.add_argument(
        "--scenarios",
        default="solo,party,boss",
        help="comma-separated subset: solo,party,boss",
    )
    parser.add_argument("--cleanup-first", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--foreground", action="store_true", help="run sequentially in foreground (debug)")
    args = parser.parse_args()

    selected = {part.strip() for part in args.scenarios.split(",") if part.strip()}
    unknown = selected - {item["key"] for item in SCENARIOS}
    if unknown:
        raise SystemExit(f"unknown scenarios: {sorted(unknown)}")

    if args.cleanup_first:
        subprocess.run([sys.executable, str(CLEANUP)], cwd=ROOT, check=False)

    OUTPUT.mkdir(parents=True, exist_ok=True)
    launched: list[tuple[str, subprocess.Popen | subprocess.CompletedProcess]] = []

    for scenario in SCENARIOS:
        if scenario["key"] not in selected:
            continue
        command = build_command(scenario, args.hold, args.ramp_up, args.audit)
        log_path = OUTPUT / f"{scenario['prefix']}-session.log"
        print(f"launch {scenario['key']}: {scenario['note']}")
        print(" ", " ".join(command))
        print(f"  log={log_path}")

        if args.foreground:
            with log_path.open("w", encoding="utf-8") as log_handle:
                proc = subprocess.run(command, cwd=ROOT, stdout=log_handle, stderr=subprocess.STDOUT, check=False)
            launched.append((scenario["key"], proc))
            if proc.returncode != 0:
                print(f"  exit={proc.returncode}")
                return proc.returncode
            continue

        log_handle = log_path.open("w", encoding="utf-8")
        env = {**os.environ, "PYTHONUNBUFFERED": "1"}
        proc = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            start_new_session=True,
        )
        log_handle.close()
        launched.append((scenario["key"], proc))
        time.sleep(2.0)

    if args.foreground:
        return 0

    print("\nobservation dummies running in background:")
    for key, proc in launched:
        if isinstance(proc, subprocess.Popen):
            print(f"  - {key}: pid={proc.pid}")
    print(f"logs: {OUTPUT}")
    print("stop all: python3 tools/cleanup-movement-dummies.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
