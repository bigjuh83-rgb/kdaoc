#!/usr/bin/env python3
"""Run preset OpenDAoC dummy-client load tests with reports."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
DEFAULT_REPORT_ROOT = TOOLS / "reports" / "dummy-load"


@dataclass(frozen=True)
class LoadPreset:
    name: str
    count: int
    concurrency: int
    hold: int
    party_size: int
    ramp_up: int
    rounds: int = 1
    fresh_account_per_round: bool = False
    description: str = ""


@dataclass(frozen=True)
class BalanceScenario:
    name: str
    behavior_profile: str
    action_rotation: str
    party_role_strategy: str
    player_level: int
    min_target_level: int
    max_target_level: int
    max_target_level_delta: int
    target_timeout: float
    target_selection: str
    ideal_target_level: int
    max_target_distance: float
    combat_interval: float
    target_pool: int
    attack_range: int
    move_step: int
    skill_interval: float
    rest_chance: float
    think_min: float
    think_max: float
    smooth_movement: bool = False
    smooth_move_interval: float = 0.25
    movement_speed: float = 220.0
    path_graph: str = ""
    path_region: int = 0
    start_x: int | None = None
    start_y: int | None = None
    start_z: int | None = None
    start_region: int | None = None
    position_step: int | None = None
    waypoints: str = ""
    prefer_target_name: str = ""
    avoid_target_name: str = ""
    ai_player: bool = False
    description: str = ""


ALBION_LOW_LEVEL_START = (523520, 490520, 2543)
ALBION_LOW_LEVEL_WAYPOINTS = "523520,490520,2543|523900,490900,2543|524250,490650,2543|523760,490280,2543"
ALBION_LOW_LEVEL_PATH_GRAPH = "tools/pathing/regions/albion-lowlevel.json"


PRESETS: dict[str, LoadPreset] = {
    "smoke": LoadPreset("smoke", count=3, concurrency=3, hold=35, party_size=3, ramp_up=3, description="3명 파티형 짧은 스모크"),
    "party-small": LoadPreset("party-small", count=6, concurrency=6, hold=180, party_size=3, ramp_up=20, description="6명, 3분 파티형 소형 부하"),
    "party-medium": LoadPreset("party-medium", count=20, concurrency=20, hold=300, party_size=4, ramp_up=60, description="20명, 5분 파티형 중형 부하"),
    "party-large": LoadPreset("party-large", count=50, concurrency=50, hold=600, party_size=5, ramp_up=120, description="50명, 10분 파티형 대형 부하"),
    "ai-filler-small": LoadPreset("ai-filler-small", count=10, concurrency=10, hold=1800, party_size=1, ramp_up=120, description="10명, 30분 운영 보충형 AI"),
    "ai-filler-medium": LoadPreset("ai-filler-medium", count=30, concurrency=30, hold=3600, party_size=1, ramp_up=300, description="30명, 1시간 운영 보충형 AI"),
}


SCENARIOS: dict[str, BalanceScenario] = {
    "newbie-solo": BalanceScenario(
        "newbie-solo",
        behavior_profile="cautious-solo",
        action_rotation="hybrid",
        party_role_strategy="same",
        player_level=1,
        min_target_level=0,
        max_target_level=0,
        max_target_level_delta=0,
        target_timeout=45,
        target_selection="smart",
        ideal_target_level=0,
        max_target_distance=3500,
        combat_interval=1.8,
        target_pool=3,
        attack_range=120,
        move_step=260,
        skill_interval=4.0,
        rest_chance=0.10,
        think_min=0.35,
        think_max=1.0,
        smooth_movement=True,
        path_graph=ALBION_LOW_LEVEL_PATH_GRAPH,
        path_region=1,
        start_x=ALBION_LOW_LEVEL_START[0],
        start_y=ALBION_LOW_LEVEL_START[1],
        start_z=ALBION_LOW_LEVEL_START[2],
        start_region=1,
        position_step=650,
        waypoints=ALBION_LOW_LEVEL_WAYPOINTS,
        prefer_target_name="worker ant,boar piglet",
        avoid_target_name="green snake",
        description="초보 솔플러 기준. 초반 몬스터가 과하게 아픈지 확인한다.",
    ),
    "solo-melee": BalanceScenario(
        "solo-melee",
        behavior_profile="solo-melee",
        action_rotation="melee-basic",
        party_role_strategy="same",
        player_level=1,
        min_target_level=0,
        max_target_level=0,
        max_target_level_delta=0,
        target_timeout=55,
        target_selection="smart",
        ideal_target_level=0,
        max_target_distance=4500,
        combat_interval=1.6,
        target_pool=4,
        attack_range=120,
        move_step=260,
        skill_interval=3.0,
        rest_chance=0.05,
        think_min=0.2,
        think_max=0.7,
        smooth_movement=True,
        path_graph=ALBION_LOW_LEVEL_PATH_GRAPH,
        path_region=1,
        start_x=ALBION_LOW_LEVEL_START[0],
        start_y=ALBION_LOW_LEVEL_START[1],
        start_z=ALBION_LOW_LEVEL_START[2],
        start_region=1,
        position_step=650,
        waypoints=ALBION_LOW_LEVEL_WAYPOINTS,
        prefer_target_name="worker ant,boar piglet",
        avoid_target_name="green snake",
        description="일반 근접 솔플러 기준. 기본 사냥 속도와 사망률을 본다.",
    ),
    "ai-pve-casual": BalanceScenario(
        "ai-pve-casual",
        behavior_profile="pve-casual",
        action_rotation="auto",
        party_role_strategy="same",
        player_level=1,
        min_target_level=0,
        max_target_level=0,
        max_target_level_delta=0,
        target_timeout=55,
        target_selection="smart",
        ideal_target_level=0,
        max_target_distance=4500,
        combat_interval=1.9,
        target_pool=4,
        attack_range=120,
        move_step=260,
        skill_interval=3.8,
        rest_chance=0.10,
        think_min=0.35,
        think_max=1.35,
        smooth_movement=True,
        path_graph=ALBION_LOW_LEVEL_PATH_GRAPH,
        path_region=1,
        start_x=ALBION_LOW_LEVEL_START[0],
        start_y=ALBION_LOW_LEVEL_START[1],
        start_z=ALBION_LOW_LEVEL_START[2],
        start_region=1,
        position_step=650,
        waypoints=ALBION_LOW_LEVEL_WAYPOINTS,
        prefer_target_name="worker ant,boar piglet",
        avoid_target_name="green snake",
        ai_player=True,
        description="생활형 PvE AI 플레이어 기준. 사냥, 배회, 휴식, 가벼운 사회 행동을 섞는다.",
    ),
    "ai-party-casual": BalanceScenario(
        "ai-party-casual",
        behavior_profile="party-dps",
        action_rotation="auto",
        party_role_strategy="mixed",
        player_level=1,
        min_target_level=1,
        max_target_level=-1,
        max_target_level_delta=4,
        target_timeout=55,
        target_selection="smart",
        ideal_target_level=3,
        max_target_distance=5200,
        combat_interval=1.5,
        target_pool=5,
        attack_range=120,
        move_step=280,
        skill_interval=2.8,
        rest_chance=0.07,
        think_min=0.20,
        think_max=0.85,
        ai_player=True,
        description="생활형 파티 AI 플레이어 기준. 리더/딜러/지원 역할로 초대, 추종, 어시스트를 섞는다.",
    ),
    "ai-filler-casual": BalanceScenario(
        "ai-filler-casual",
        behavior_profile="pve-casual",
        action_rotation="auto",
        party_role_strategy="same",
        player_level=1,
        min_target_level=0,
        max_target_level=0,
        max_target_level_delta=0,
        target_timeout=60,
        target_selection="smart",
        ideal_target_level=0,
        max_target_distance=4200,
        combat_interval=2.6,
        target_pool=3,
        attack_range=120,
        move_step=260,
        skill_interval=4.8,
        rest_chance=0.14,
        think_min=0.75,
        think_max=2.20,
        smooth_movement=True,
        path_graph=ALBION_LOW_LEVEL_PATH_GRAPH,
        path_region=1,
        start_x=ALBION_LOW_LEVEL_START[0],
        start_y=ALBION_LOW_LEVEL_START[1],
        start_z=ALBION_LOW_LEVEL_START[2],
        start_region=1,
        position_step=650,
        waypoints=ALBION_LOW_LEVEL_WAYPOINTS,
        prefer_target_name="worker ant,boar piglet",
        avoid_target_name="green snake",
        ai_player=True,
        description="운영 보충형 AI. 단독 생활형 사냥/휴식/주변 유저 반응을 낮은 빈도로 섞는다.",
    ),
    "party-assist": BalanceScenario(
        "party-assist",
        behavior_profile="party-dps",
        action_rotation="auto",
        party_role_strategy="mixed",
        player_level=1,
        min_target_level=1,
        max_target_level=-1,
        max_target_level_delta=4,
        target_timeout=55,
        target_selection="smart",
        ideal_target_level=3,
        max_target_distance=5200,
        combat_interval=1.3,
        target_pool=5,
        attack_range=120,
        move_step=280,
        skill_interval=2.4,
        rest_chance=0.04,
        think_min=0.1,
        think_max=0.45,
        description="파티 지원/집중 공격 기준. 파티 사냥 처리량과 서버 부하를 본다.",
    ),
    "mobgrowth-pressure": BalanceScenario(
        "mobgrowth-pressure",
        behavior_profile="solo-melee",
        action_rotation="melee-burst",
        party_role_strategy="same",
        player_level=1,
        min_target_level=1,
        max_target_level=-1,
        max_target_level_delta=2,
        target_timeout=45,
        target_selection="nearest",
        ideal_target_level=2,
        max_target_distance=0,
        combat_interval=1.1,
        target_pool=8,
        attack_range=120,
        move_step=280,
        skill_interval=2.5,
        rest_chance=0.02,
        think_min=0.0,
        think_max=0.25,
        description="몬스터 성장/전투 이벤트 압박용. 많은 타겟 교전과 처치 추정을 만든다.",
    ),
}


def run(command: list[str], log_path: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+ " + shlex.join(command))

    if log_path is None:
        subprocess.run(command, cwd=ROOT, env=env, check=True)
        return

    with log_path.open("a", encoding="utf-8") as log:
        log.write("+ " + shlex.join(command) + "\n")
        log.flush()
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        assert process.stdout is not None

        for line in process.stdout:
            print(line, end="")
            log.write(line)

        exit_code = process.wait()

        if exit_code != 0:
            raise subprocess.CalledProcessError(exit_code, command)


def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def shifted_time(value: str, offset_hours: float) -> str:
    current = datetime.strptime(value, "%H:%M:%S")
    return (current + timedelta(hours=offset_hours)).strftime("%H:%M:%S")


def truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "ok"}


def build_provision_command(args: argparse.Namespace, preset: LoadPreset, scenario: BalanceScenario, accounts_csv: Path) -> list[str]:
    command = [
        sys.executable,
        str(TOOLS / "provision-dummy-accounts.py"),
        "--start",
        str(args.start),
        "--count",
        str(args.count or preset.count),
        "--password",
        args.password,
        "--csv",
        str(accounts_csv),
        "--replace",
    ]

    character_name_mode = args.character_name_mode
    if character_name_mode is None and (scenario.ai_player or args.ai_player):
        character_name_mode = "natural"

    if character_name_mode:
        command += ["--character-name-mode", character_name_mode]

    if args.character_names:
        command += ["--character-names", args.character_names]

    if args.character_name_file:
        command += ["--character-name-file", args.character_name_file]

    if args.mysql_bin:
        command += ["--mysql-bin", args.mysql_bin]

    if args.db_password:
        command += ["--db-password", args.db_password]

    if scenario.start_x is not None:
        command += ["--start-x", str(scenario.start_x)]

    if scenario.start_y is not None:
        command += ["--start-y", str(scenario.start_y)]

    if scenario.start_z is not None:
        command += ["--start-z", str(scenario.start_z)]

    if scenario.start_region is not None:
        command += ["--start-region", str(scenario.start_region)]

    if scenario.position_step is not None:
        command += ["--position-step", str(scenario.position_step)]

    return command


def build_behavior_command(
    args: argparse.Namespace,
    preset: LoadPreset,
    scenario: BalanceScenario,
    accounts_csv: Path,
    metrics_csv: Path,
    combat_csv: Path,
    report_md: Path,
) -> list[str]:
    count = args.count or preset.count
    concurrency = args.concurrency or preset.concurrency
    hold = args.hold or preset.hold
    party_size = args.party_size or preset.party_size
    ramp_up = args.ramp_up if args.ramp_up is not None else preset.ramp_up
    rounds = args.rounds or preset.rounds

    command = [
        sys.executable,
        str(TOOLS / "behavior-dummy-client.py"),
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--accounts",
        str(accounts_csv),
        "--concurrency",
        str(concurrency),
        "--rounds",
        str(rounds),
        "--hold",
        str(hold),
        "--ramp-up",
        str(ramp_up),
        "--party-size",
        str(party_size),
        "--ping-interval",
        "5",
        "--turn-interval",
        "0",
        "--hunter",
        "--behavior-profile",
        args.behavior_profile or scenario.behavior_profile,
        "--action-rotation",
        args.action_rotation or scenario.action_rotation,
        "--party-role-strategy",
        scenario.party_role_strategy,
        "--realm-strategy",
        args.realm_strategy,
        "--api-port",
        str(args.api_port),
        "--player-level",
        str(scenario.player_level),
        "--ideal-target-level",
        str(scenario.ideal_target_level),
        "--min-target-level",
        str(scenario.min_target_level),
        "--max-target-level",
        str(scenario.max_target_level),
        "--max-target-level-delta",
        str(scenario.max_target_level_delta),
        "--max-target-distance",
        str(scenario.max_target_distance),
        "--target-timeout",
        str(scenario.target_timeout),
        "--target-selection",
        scenario.target_selection,
        "--combat-interval",
        str(scenario.combat_interval),
        "--target-pool",
        str(scenario.target_pool),
        "--attack-range",
        str(scenario.attack_range),
        "--move-step",
        str(scenario.move_step),
    ]

    if scenario.smooth_movement:
        command += [
            "--smooth-movement",
            "--smooth-move-interval",
            str(scenario.smooth_move_interval),
            "--movement-speed",
            str(scenario.movement_speed),
        ]

    if scenario.path_graph:
        command += ["--path-graph", scenario.path_graph]

    if scenario.path_region:
        command += ["--path-region", str(scenario.path_region)]

    command += [
        "--use-skills",
        "--skill-interval",
        str(scenario.skill_interval),
        "--skill-indexes",
        "0,1,2",
        "--skill-type",
        "1",
        "--party-invite-interval",
        "6",
        "--party-accept-interval",
        "3",
        "--party-assist-interval",
        "3",
        "--party-follow-interval",
        "1.2",
        "--party-follow-step",
        "320",
        "--party-follow-distance",
        "500",
        "--party-use-assist-command",
        "--auto-release-on-death",
        "--death-release-delay",
        "2",
        "--death-recovery-cooldown",
        "8",
        "--post-release-rest",
        "3",
        "--rest-chance",
        str(scenario.rest_chance),
        "--rest-min",
        "1",
        "--rest-max",
        "2",
        "--think-min",
        str(scenario.think_min),
        "--think-max",
        str(scenario.think_max),
        "--command",
        "",
        "--jitter",
        "0.2",
        "--tick",
        "0.05",
        "--metrics-csv",
        str(metrics_csv),
        "--combat-csv",
        str(combat_csv),
        "--report-md",
        str(report_md),
    ]

    if scenario.waypoints:
        command += ["--waypoints", scenario.waypoints]

    if scenario.prefer_target_name:
        command += ["--prefer-target-name", scenario.prefer_target_name]

    if scenario.avoid_target_name:
        command += ["--avoid-target-name", scenario.avoid_target_name]

    if args.live_api_url:
        command += ["--live-api-url", args.live_api_url]

    if args.nav_api_url:
        command += ["--nav-api-url", args.nav_api_url]

    if scenario.ai_player or args.ai_player:
        command += [
            "--ai-player",
            "--ai-persona",
            args.ai_persona,
            "--target-examine-chance",
            str(args.target_examine_chance),
            "--social-interval",
            str(args.social_interval),
            "--social-chance",
            str(args.social_chance),
            "--player-greet-interval",
            str(args.player_greet_interval),
            "--player-greet-chance",
            str(args.player_greet_chance),
            "--emote-interval",
            str(args.emote_interval),
            "--emote-chance",
            str(args.emote_chance),
            "--look-around-interval",
            str(args.look_around_interval),
            "--long-rest-chance",
            str(args.long_rest_chance),
            "--follow-player-name",
            args.follow_player_name,
            "--player-follow-interval",
            str(args.player_follow_interval),
            "--player-follow-distance",
            str(args.player_follow_distance),
            "--follow-player-max-distance",
            str(args.follow_player_max_distance),
        ]

    if preset.fresh_account_per_round or args.fresh_account_per_round:
        command += ["--fresh-account-per-round"]

    if count < concurrency:
        raise ValueError(f"count={count} must be >= concurrency={concurrency}")

    if party_size > concurrency:
        raise ValueError(f"party-size={party_size} must be <= concurrency={concurrency}")

    return command


def build_server_stats_command(args: argparse.Namespace, output_dir: Path, report_md: Path, since_time: str, until_time: str) -> list[str] | None:
    if not args.server_log:
        return None

    since_time = shifted_time(since_time, args.server_log_time_offset_hours)
    until_time = shifted_time(until_time, args.server_log_time_offset_hours)

    return [
        sys.executable,
        str(TOOLS / "summarize-server-stats.py"),
        args.server_log,
        "--since-time",
        since_time,
        "--until-time",
        until_time,
        "--csv",
        str(output_dir / "server-stats.csv"),
        "--json",
        str(output_dir / "server-stats.json"),
        "--append-report",
        str(report_md),
    ]


def write_run_metadata(
    path: Path,
    args: argparse.Namespace,
    preset: LoadPreset,
    scenario: BalanceScenario,
    commands: dict[str, list[str] | None],
    test_window: dict[str, str] | None = None,
) -> None:
    data = {
        "preset": asdict(preset),
        "scenario": asdict(scenario),
        "args": {
            "host": args.host,
            "port": args.port,
            "start": args.start,
            "count": args.count,
            "concurrency": args.concurrency,
            "hold": args.hold,
            "party_size": args.party_size,
            "ramp_up": args.ramp_up,
            "rounds": args.rounds,
            "server_log": args.server_log,
            "server_log_time_offset_hours": args.server_log_time_offset_hours,
            "accounts_csv": args.accounts_csv,
            "scenario": args.scenario,
            "behavior_profile": args.behavior_profile,
            "action_rotation": args.action_rotation,
            "ai_player": args.ai_player,
            "ai_persona": args.ai_persona,
            "target_examine_chance": args.target_examine_chance,
            "social_interval": args.social_interval,
            "social_chance": args.social_chance,
            "player_greet_interval": args.player_greet_interval,
            "player_greet_chance": args.player_greet_chance,
            "emote_interval": args.emote_interval,
            "emote_chance": args.emote_chance,
            "look_around_interval": args.look_around_interval,
            "long_rest_chance": args.long_rest_chance,
            "follow_player_name": args.follow_player_name,
            "player_follow_interval": args.player_follow_interval,
            "player_follow_distance": args.player_follow_distance,
            "follow_player_max_distance": args.follow_player_max_distance,
            "realm_strategy": args.realm_strategy,
            "live_api_url": args.live_api_url,
            "character_name_mode": args.character_name_mode,
        },
        "test_window": test_window,
        "commands": {name: shlex.join(command) for name, command in commands.items() if command is not None},
    }
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_metrics(metrics_csv: Path) -> dict[str, object]:
    if not metrics_csv.exists():
        return {
            "rows": 0,
            "ok_rows": 0,
            "failed_rows": 0,
            "actions": 0,
            "deaths": 0,
            "death_releases": 0,
            "combat_engagements": 0,
            "target_removed": 0,
            "player_deaths": 0,
            "target_timeouts": 0,
            "errors": ["metrics.csv not found"],
        }

    rows = []
    errors: list[str] = []
    with metrics_csv.open("r", encoding="utf-8", newline="") as input_file:
        reader = csv.DictReader(input_file)
        for row in reader:
            rows.append(row)
            if not truthy(row.get("ok")):
                errors.append(f"{row.get('username', 'unknown')} round {row.get('round', '?')} failed")
            if (row.get("error") or "").strip():
                errors.append(f"{row.get('username', 'unknown')}: {row['error']}")

    return {
        "rows": len(rows),
        "ok_rows": sum(1 for row in rows if truthy(row.get("ok"))),
        "failed_rows": sum(1 for row in rows if not truthy(row.get("ok"))),
        "actions": sum(int(row.get("actions") or 0) for row in rows),
        "deaths": sum(int(row.get("death_detected") or 0) for row in rows),
        "death_releases": sum(int(row.get("death_release") or 0) for row in rows),
        "combat_engagements": sum(int(row.get("combat_engagements") or 0) for row in rows),
        "target_removed": sum(int(row.get("target_removed") or 0) for row in rows),
        "player_deaths": sum(int(row.get("player_deaths") or 0) for row in rows),
        "target_timeouts": sum(int(row.get("target_timeouts") or 0) for row in rows),
        "errors": errors,
    }


def read_json(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def add_issue(issues: list[dict[str, str]], status: str, message: str) -> None:
    issues.append({"status": status, "message": message})


def assess_load_test(args: argparse.Namespace, metrics_csv: Path, server_stats_json: Path) -> dict[str, object]:
    metrics = read_metrics(metrics_csv)
    server_stats = read_json(server_stats_json) if args.server_log else None
    issues: list[dict[str, str]] = []

    if metrics["failed_rows"]:
        add_issue(issues, "FAIL", f"{metrics['failed_rows']} dummy round(s) failed")
    for error in metrics["errors"]:
        add_issue(issues, "FAIL", str(error))

    if int(metrics.get("combat_engagements", 0)) <= 0:
        add_issue(issues, "WARN", "no combat engagements were recorded")
    if args.min_target_removed and int(metrics.get("target_removed", 0)) < args.min_target_removed:
        add_issue(
            issues,
            "FAIL",
            f"target_removed {metrics.get('target_removed', 0)} is below required {args.min_target_removed}",
        )
    if args.max_player_deaths is not None and int(metrics.get("player_deaths", 0)) > args.max_player_deaths:
        add_issue(
            issues,
            "FAIL",
            f"player_deaths {metrics.get('player_deaths', 0)} exceeded limit {args.max_player_deaths}",
        )

    if args.server_log:
        if not server_stats:
            add_issue(issues, "FAIL", "server-stats.json was not created")
        elif int(server_stats.get("samples", 0)) < args.min_server_stat_samples:
            add_issue(
                issues,
                "FAIL",
                f"only {server_stats.get('samples', 0)} server StatPrint sample(s); required {args.min_server_stat_samples}",
            )
        else:
            for key, label, minimum in [
                ("min_tps10", "TPS 10s", args.min_tps10),
                ("min_tps30", "TPS 30s", args.min_tps30),
                ("min_tps60", "TPS 60s", args.min_tps60),
            ]:
                value = float(server_stats.get(key, 100.0))
                if value < minimum:
                    add_issue(issues, "FAIL", f"{label} minimum {value}% is below threshold {minimum}%")

            max_process_cpu = float(server_stats.get("max_process_cpu", 0.0))
            max_system_cpu = float(server_stats.get("max_system_cpu", 0.0))
            max_memory_used_mb = int(server_stats.get("max_memory_used_mb", 0))

            if max_process_cpu > args.warn_process_cpu:
                add_issue(issues, "WARN", f"process CPU max {max_process_cpu}% exceeded warning threshold {args.warn_process_cpu}%")
            if max_system_cpu > args.warn_system_cpu:
                add_issue(issues, "WARN", f"system CPU max {max_system_cpu}% exceeded warning threshold {args.warn_system_cpu}%")
            if args.max_memory_used_mb and max_memory_used_mb > args.max_memory_used_mb:
                add_issue(issues, "FAIL", f"memory used max {max_memory_used_mb} MB exceeded limit {args.max_memory_used_mb} MB")
            elif args.warn_memory_used_mb and max_memory_used_mb > args.warn_memory_used_mb:
                add_issue(issues, "WARN", f"memory used max {max_memory_used_mb} MB exceeded warning threshold {args.warn_memory_used_mb} MB")
    else:
        add_issue(issues, "WARN", "server StatPrint checks skipped because --server-log was not provided")

    if any(issue["status"] == "FAIL" for issue in issues):
        status = "FAIL"
    elif any(issue["status"] == "WARN" for issue in issues):
        status = "WARN"
    else:
        status = "PASS"

    return {
        "status": status,
        "metrics": metrics,
        "server_stats": server_stats,
        "thresholds": {
            "min_tps10": args.min_tps10,
            "min_tps30": args.min_tps30,
            "min_tps60": args.min_tps60,
            "min_server_stat_samples": args.min_server_stat_samples,
            "warn_process_cpu": args.warn_process_cpu,
            "warn_system_cpu": args.warn_system_cpu,
            "warn_memory_used_mb": args.warn_memory_used_mb,
            "max_memory_used_mb": args.max_memory_used_mb,
            "min_target_removed": args.min_target_removed,
            "max_player_deaths": args.max_player_deaths,
        },
        "issues": issues,
    }


def render_assessment(assessment: dict[str, object]) -> str:
    metrics = assessment["metrics"]
    assert isinstance(metrics, dict)
    issues = assessment["issues"]
    assert isinstance(issues, list)
    server_stats = assessment.get("server_stats")
    status = assessment["status"]

    lines = [
        "# Load Test Assessment",
        "",
        f"**Result: `{status}`**",
        "",
        "## Gate Summary",
        "",
        f"- Dummy rounds: `{metrics['ok_rows']}/{metrics['rows']}`",
        f"- Total actions: `{metrics['actions']}`",
        f"- Deaths/release attempts: `{metrics['deaths']}` / `{metrics['death_releases']}`",
        f"- Combat engagements: `{metrics['combat_engagements']}`",
        f"- Target removed/player deaths/timeouts: `{metrics['target_removed']}` / `{metrics['player_deaths']}` / `{metrics['target_timeouts']}`",
    ]

    if isinstance(server_stats, dict) and server_stats.get("samples", 0):
        lines += [
            f"- Server samples: `{server_stats['samples']}` (`{server_stats['time_start']}` - `{server_stats['time_end']}`)",
            f"- TPS 10/30/60 min: `{server_stats['min_tps10']}%` / `{server_stats['min_tps30']}%` / `{server_stats['min_tps60']}%`",
            f"- CPU process/system max: `{server_stats['max_process_cpu']}%` / `{server_stats['max_system_cpu']}%`",
            f"- Memory used max: `{server_stats['max_memory_used_mb']} MB`",
        ]

    lines += ["", "## Gate Issues", ""]

    if issues:
        lines.extend(f"- `{issue['status']}` {issue['message']}" for issue in issues)
    else:
        lines.append("- No issues.")

    return "\n".join(lines) + "\n\n---\n\n"


def prepend_report(report_md: Path, markdown: str) -> None:
    original = report_md.read_text(encoding="utf-8") if report_md.exists() else ""
    report_md.write_text(markdown + original, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("preset_arg", nargs="?", default="smoke", choices=sorted(PRESETS))
    parser.add_argument("--preset", dest="preset_option", choices=sorted(PRESETS), help="preset name; equivalent to positional preset")
    parser.add_argument("--scenario", default="solo-melee", choices=sorted(SCENARIOS))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--start", type=int, default=100)
    parser.add_argument("--count", type=int)
    parser.add_argument("--concurrency", type=int)
    parser.add_argument("--hold", type=int)
    parser.add_argument("--party-size", type=int)
    parser.add_argument("--ramp-up", type=int)
    parser.add_argument("--rounds", type=int)
    parser.add_argument("--fresh-account-per-round", action="store_true")
    parser.add_argument(
        "--behavior-profile",
        choices=["custom", "solo-melee", "cautious-solo", "pve-casual", "party-tank", "party-dps"],
        default=None,
        help="override the behavior profile chosen by --scenario",
    )
    parser.add_argument(
        "--action-rotation",
        choices=["auto", "none", "melee-basic", "melee-burst", "caster-basic", "healer-support", "hybrid"],
        default=None,
        help="override the action rotation chosen by --scenario",
    )
    parser.add_argument("--password", default=os.environ.get("OPENDAOC_DUMMY_PASSWORD", "dummy-pass"))
    parser.add_argument("--accounts-csv", help="use an existing account CSV instead of the generated output accounts.csv")
    parser.add_argument("--character-name-mode", choices=["sequential", "natural"], default=None)
    parser.add_argument("--character-names", default="")
    parser.add_argument("--character-name-file", default="")
    parser.add_argument("--ai-player", action="store_true", help="force AI-player pacing even when the selected scenario does not enable it")
    parser.add_argument(
        "--ai-persona",
        choices=["auto", "none", "cautious-hunter", "helpful-follower", "quiet-grinder", "social-roamer"],
        default="auto",
    )
    parser.add_argument("--realm-strategy", choices=["fixed", "least-populated"], default="fixed")
    parser.add_argument("--live-api-url", default="")
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--nav-api-url", default="", help="server API root for dummy navmesh pathing, for example http://127.0.0.1:5000")
    parser.add_argument("--target-examine-chance", type=float, default=0.20)
    parser.add_argument("--social-interval", type=float, default=75.0)
    parser.add_argument("--social-chance", type=float, default=0.08)
    parser.add_argument("--player-greet-interval", type=float, default=45.0)
    parser.add_argument("--player-greet-chance", type=float, default=0.06)
    parser.add_argument("--emote-interval", type=float, default=55.0)
    parser.add_argument("--emote-chance", type=float, default=0.12)
    parser.add_argument("--look-around-interval", type=float, default=12.0)
    parser.add_argument("--long-rest-chance", type=float, default=0.06)
    parser.add_argument("--follow-player-name", default="")
    parser.add_argument("--player-follow-interval", type=float, default=2.0)
    parser.add_argument("--player-follow-distance", type=float, default=850.0)
    parser.add_argument("--follow-player-max-distance", type=float, default=3500.0)
    parser.add_argument("--db-password", default=os.environ.get("DB_PASSWORD"))
    parser.add_argument("--mysql-bin", default=os.environ.get("MYSQL_BIN"))
    parser.add_argument("--report-root", default=str(DEFAULT_REPORT_ROOT))
    parser.add_argument("--name", help="optional suffix for the report directory")
    parser.add_argument("--server-log", help="server.log path to summarize StatPrint samples into the report")
    parser.add_argument("--server-log-time-offset-hours", type=float, default=0.0, help="shift local test window before matching server log HH:MM:SS")
    parser.add_argument("--min-tps10", type=float, default=95.0)
    parser.add_argument("--min-tps30", type=float, default=95.0)
    parser.add_argument("--min-tps60", type=float, default=95.0)
    parser.add_argument("--min-server-stat-samples", type=int, default=1)
    parser.add_argument("--warn-process-cpu", type=float, default=80.0)
    parser.add_argument("--warn-system-cpu", type=float, default=85.0)
    parser.add_argument("--warn-memory-used-mb", type=int)
    parser.add_argument("--max-memory-used-mb", type=int)
    parser.add_argument("--min-target-removed", type=int, default=0, help="fail if fewer target_removed combat outcomes are recorded")
    parser.add_argument("--max-player-deaths", type=int, help="fail if combat player_deaths exceeds this value")
    parser.add_argument("--no-fail-on-assessment", action="store_true")
    parser.add_argument("--skip-provision", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    args.preset = args.preset_option or args.preset_arg

    preset = PRESETS[args.preset]
    scenario = SCENARIOS[args.scenario]
    run_name = f"{timestamp()}-{preset.name}-{scenario.name}" + (f"-{args.name}" if args.name else "")
    output_dir = Path(args.report_root) / run_name
    output_dir.mkdir(parents=True, exist_ok=True)
    accounts_csv = output_dir / "accounts.csv"
    metrics_csv = output_dir / "metrics.csv"
    combat_csv = output_dir / "combat.csv"
    report_md = output_dir / "report.md"
    output_log = output_dir / "output.log"
    metadata_json = output_dir / "run.json"
    assessment_json = output_dir / "assessment.json"

    provision_command = build_provision_command(args, preset, scenario, accounts_csv)
    behavior_command = build_behavior_command(args, preset, scenario, accounts_csv, metrics_csv, combat_csv, report_md)
    write_run_metadata(metadata_json, args, preset, scenario, {"provision": provision_command, "behavior": behavior_command})

    print(f"preset: {preset.name} - {preset.description}")
    print(f"scenario: {scenario.name} - {scenario.description}")
    print(f"output: {output_dir}")

    if args.dry_run:
        print("dry-run only; commands written to run.json")
        return 0

    if args.accounts_csv:
        shutil.copyfile(args.accounts_csv, accounts_csv)
        args.skip_provision = True

    if not args.skip_provision:
        run(provision_command, output_log)

    test_start_time = datetime.now().strftime("%H:%M:%S")
    run(behavior_command, output_log)
    test_end_time = datetime.now().strftime("%H:%M:%S")

    server_stats_command = build_server_stats_command(args, output_dir, report_md, test_start_time, test_end_time)
    write_run_metadata(
        metadata_json,
        args,
        preset,
        scenario,
        {"provision": provision_command, "behavior": behavior_command, "server_stats": server_stats_command},
        {"start": test_start_time, "end": test_end_time},
    )

    if server_stats_command:
        run(server_stats_command, output_log)
        print(f"server stats: {output_dir / 'server-stats.json'}")

    assessment = assess_load_test(args, metrics_csv, output_dir / "server-stats.json")
    assessment_json.write_text(json.dumps(assessment, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    prepend_report(report_md, render_assessment(assessment))

    print(f"assessment: {assessment_json}")
    print(f"assessment result: {assessment['status']}")
    print(f"report: {report_md}")
    print(f"metrics: {metrics_csv}")
    print(f"combat: {combat_csv}")
    print(f"log: {output_log}")
    if assessment["status"] == "FAIL" and not args.no_fail_on_assessment:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
