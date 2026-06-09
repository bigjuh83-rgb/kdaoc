#!/usr/bin/env python3
"""Run the live-companion smoke with one dummy acting as the player driver."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SMOKE_SCRIPT = ROOT / "tools" / "run-live-companion-party-smoke.py"
DEFAULT_RUN_DIR = Path("test-output/live-companion-selftest/player-command-combat")


def _has_option(args: list[str], option: str) -> bool:
    return option in args or any(arg.startswith(f"{option}=") for arg in args)


def build_command(args: list[str]) -> list[str]:
    command = [sys.executable, str(SMOKE_SCRIPT)]
    if not _has_option(args, "--smoke-profile"):
        command += ["--smoke-profile", "player-command-combat"]
    if not _has_option(args, "--run-dir"):
        command += ["--run-dir", str(DEFAULT_RUN_DIR)]
    if not _has_option(args, "--replace"):
        command.append("--replace")
    command.extend(args)
    return command


def main(argv: list[str] | None = None) -> int:
    command = build_command(list(sys.argv[1:] if argv is None else argv))
    return subprocess.run(command, cwd=ROOT).returncode


if __name__ == "__main__":
    raise SystemExit(main())
