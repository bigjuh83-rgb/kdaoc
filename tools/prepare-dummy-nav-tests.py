#!/usr/bin/env python3
"""Print ready-to-run dummy navigation comparison commands."""

from __future__ import annotations

import argparse
import shlex
from dataclasses import dataclass


REGION001_CLIENT_MAP = "tools/pathing/heightmaps/region001_client_zones.json"


@dataclass(frozen=True)
class NavTestProfile:
    name: str
    description: str
    path_region: int
    waypoints: str


PROFILES: dict[str, NavTestProfile] = {
    "camelot-flat": NavTestProfile(
        "camelot-flat",
        "Camelot Hills observed flat-ish visual check near /loc 552563,513585,2896",
        0,
        "552563,513585,2896|553163,513585,2896|553163,514185,2896|552563,514185,2896",
    ),
    "salisbury-slope": NavTestProfile(
        "salisbury-slope",
        "Salisbury Plains height/Z regression route with visible slope changes",
        1,
        "581632,581632,2192|582432,581632,2008|582432,582432,1968|581066,581066,2412",
    ),
    "salisbury-grid": NavTestProfile(
        "salisbury-grid",
        "Salisbury Plains client-grid A* route sanity check",
        1,
        "581632,581632,2192|582400,581632,1968|582400,582400,2050|581632,582400,2150",
    ),
}


def build_behavior_command(args: argparse.Namespace, profile: NavTestProfile, *, grid: bool) -> list[str]:
    command = [
        "python3",
        "tools/behavior-dummy-client.py",
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--accounts",
        args.accounts,
        "--concurrency",
        str(args.concurrency),
        "--hold",
        str(args.hold),
        "--char-index",
        str(args.char_index),
        "--move",
        "--smooth-movement",
        "--movement-speed",
        str(args.movement_speed),
        "--smooth-move-interval",
        str(args.interval),
        "--movement-update-interval",
        str(args.interval),
        "--server-correction-smoothing",
        "--ground-z-map",
        REGION001_CLIENT_MAP,
        "--path-region",
        str(profile.path_region),
        "--waypoints",
        profile.waypoints,
        "--waypoint-mode",
        "loop",
        "--waypoint-continuous-turns",
        "--waypoint-advance-distance",
        "35",
        "--waypoint-stop-distance",
        "12",
        "--trace-movement-log",
        f"tools/reports/movement-{profile.name}-{'grid-on' if grid else 'grid-off'}-{{username}}.jsonl",
    ]

    if grid:
        command += [
            "--client-grid-nav-map",
            REGION001_CLIENT_MAP,
            "--client-grid-nav-cell-size",
            str(args.cell_size),
            "--client-grid-nav-max-step-z",
            str(args.max_step_z),
            "--client-grid-nav-fixture-padding",
            str(args.fixture_padding),
        ]

    return command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=[*sorted(PROFILES), "all"], default="all")
    parser.add_argument("--mode", choices=["compare", "grid-on", "grid-off"], default="compare")
    parser.add_argument("--host", default="192.168.0.42")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--accounts", default="tools/dummy-accounts.csv")
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--hold", type=int, default=300)
    parser.add_argument("--char-index", type=int, default=0)
    parser.add_argument("--movement-speed", type=float, default=191.0)
    parser.add_argument("--interval", type=float, default=0.20)
    parser.add_argument("--cell-size", type=int, default=256)
    parser.add_argument("--max-step-z", type=int, default=240)
    parser.add_argument("--fixture-padding", type=int, default=160)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    names = sorted(PROFILES) if args.profile == "all" else [args.profile]

    for name in names:
        profile = PROFILES[name]
        print(f"# {profile.name}: {profile.description}")

        if args.mode in {"compare", "grid-off"}:
            print(shlex.join(build_behavior_command(args, profile, grid=False)))

        if args.mode in {"compare", "grid-on"}:
            print(shlex.join(build_behavior_command(args, profile, grid=True)))

        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
