#!/usr/bin/env python3
"""Case-level supervisor for pre-service dummy growth tests.

The supervisor keeps every growth case isolated.  A case runs exactly one
segment per worker process, then the supervisor decides whether to queue the
next segment, pause, quarantine, or complete that case.
"""

from __future__ import annotations

import argparse
import atexit
import csv
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable


REALMS = ("alb", "mid", "hib")
REALM_ORDER = {realm: index for index, realm in enumerate(REALMS)}
DEFAULT_VARIANTS = {
    "solo-s150-r2": {
        "party_size": 1,
        "repeats_arg": "solo_repeats",
        "default_repeats": 2,
        "segment_seconds": 150,
        "extra_args": ["--travel-aggro-clear-grace", "18"],
    },
    "duo-s150": {
        "party_size": 2,
        "repeats_arg": "duo_repeats",
        "default_repeats": 1,
        "segment_seconds": 150,
        "extra_args": ["--travel-aggro-clear-grace", "16", "--party-rescue-assist-after", "3"],
    },
    "party4-s180": {
        "party_size": 4,
        "repeats_arg": "party4_repeats",
        "default_repeats": 1,
        "segment_seconds": 180,
        "extra_args": [
            "--travel-aggro-clear-grace",
            "12",
            "--party-rescue-assist-after",
            "2",
            "--party-rescue-emergency-assist-after",
            "1",
        ],
    },
    "party8-s240": {
        "party_size": 8,
        "repeats_arg": "party8_repeats",
        "default_repeats": 1,
        "segment_seconds": 240,
        "extra_args": [
            "--travel-aggro-clear-grace",
            "10",
            "--party-rescue-assist-after",
            "2",
            "--party-rescue-emergency-assist-after",
            "1",
        ],
    },
}

ACTIVE_STATES = {"queued", "running"}
RESUMABLE_STATES = {"paused", "quarantined"}
FINAL_STATES = {"completed", "paused", "quarantined"}
ATOMIC_REPLACE_ATTEMPTS = 20
ATOMIC_REPLACE_RETRY_SECONDS = 0.05
BOTTLENECK_LEDGER_FIELDS = [
    "timestamp_utc",
    "event",
    "case_id",
    "variant",
    "realm",
    "party_size",
    "segment",
    "attempt",
    "status_after",
    "reason",
    "max_level",
    "min_level",
    "recent_segment_span",
    "recent_xp",
    "recent_target_removed",
    "recent_deaths",
    "kills",
    "target_removed",
    "deaths",
    "xp",
    "money",
    "stdout_log",
    "stderr_log",
    "reproduction_command",
]


def process_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError:
            return False
        return str(pid) in str(result.stdout or "")
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def process_command_line(pid: int) -> str:
    if pid <= 0:
        return ""
    if os.name == "nt":
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    f"(Get-CimInstance Win32_Process -Filter 'ProcessId = {int(pid)}').CommandLine",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError:
            return ""
        return str(result.stdout or "").strip()
    try:
        return Path(f"/proc/{int(pid)}/cmdline").read_text(encoding="utf-8", errors="replace").replace("\x00", " ")
    except OSError:
        return ""


def is_case_worker_process(pid: int, case_id: str) -> bool:
    command_line = process_command_line(pid)
    if not command_line:
        return False
    normalized = command_line.replace("\\", "/")
    return "run-dummy-growth-suite.py" in normalized and str(case_id) in normalized


def acquire_run_lock(base_run_dir: Path) -> Path:
    base_run_dir.mkdir(parents=True, exist_ok=True)
    lock_path = base_run_dir / "supervisor.lock"
    payload = {"pid": os.getpid(), "timestamp_utc": utc_now()}
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            existing = json.loads(lock_path.read_text(encoding="utf-8"))
        except Exception:
            existing = {}
        existing_pid = as_int(existing.get("pid"))
        if process_exists(existing_pid):
            raise SystemExit(f"case supervisor already running for {base_run_dir} (pid {existing_pid})")
        lock_path.unlink(missing_ok=True)
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    atexit.register(lambda: lock_path.unlink(missing_ok=True))
    return lock_path


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def timestamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def parse_csv_list(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_int_csv(value: str) -> set[int]:
    result: set[int] = set()
    for part in parse_csv_list(value):
        result.add(int(part))
    return result


def as_int(value: Any, default: int = 0) -> int:
    try:
        if value in ("", None):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def windows_path_to_wsl(path: Path) -> str:
    resolved = path.resolve()
    drive = resolved.drive.rstrip(":").lower()
    if not drive:
        return str(resolved).replace("\\", "/")
    rest = str(resolved)[3:].replace("\\", "/")
    return f"/mnt/{drive}/{rest}"


def detect_wsl_default_gateway(wsl_exe: str) -> str:
    if os.name != "nt":
        return ""
    try:
        result = subprocess.run(
            [
                str(wsl_exe or r"C:\Windows\System32\wsl.exe"),
                "--exec",
                "bash",
                "-lc",
                "ip route | awk '/default/ {print $3; exit}'",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    if result.returncode != 0:
        return ""
    return str(result.stdout or "").strip()


def maybe_resolve_worker_wsl_host(args: argparse.Namespace) -> None:
    default_host = "192.168.0.42"
    default_nav = "http://192.168.0.42:5000"
    host_address = str(getattr(args, "host_address", "") or "").strip()
    nav_api_url = str(getattr(args, "nav_api_url", "") or "").strip()
    if host_address != default_host and nav_api_url != default_nav:
        return

    gateway = detect_wsl_default_gateway(str(getattr(args, "wsl_exe", "") or ""))
    if not gateway:
        return

    if host_address == default_host:
        args.host_address = gateway
    if nav_api_url == default_nav:
        args.nav_api_url = f"http://{gateway}:{int(getattr(args, 'api_port', 5000) or 5000)}"


def local_base_run_dir(value: str) -> Path:
    if value:
        path = Path(value)
    else:
        path = Path("test-output") / f"preservice-growth-50x-case-supervisor-{timestamp()}"
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def wsl_run_dir_arg(local_path: Path, args: argparse.Namespace) -> str:
    if args.fake_worker:
        return str(local_path)
    try:
        base = args.base_run_dir_path
        relative = local_path.resolve().relative_to(base.resolve())
        base_arg = args.base_run_dir_wsl
        return f"{base_arg.rstrip('/')}/{relative.as_posix()}"
    except ValueError:
        return windows_path_to_wsl(local_path)


def kill_wsl_case_processes(args: argparse.Namespace, case: "CaseRecord", *, force: bool) -> list[int]:
    if getattr(args, "fake_worker", False):
        return []
    markers = sorted(
        {
            str(case.case_id),
            str(case.run_dir_arg),
            str(case.case_data_dir).replace("\\", "/"),
            f"/cases/{case.case_id}/",
            f"/{case.case_id}/",
        }
    )
    script = r"""
import json
import os
import signal
import sys
import time

markers = [marker for marker in json.loads(sys.argv[1]) if marker]
force = sys.argv[2] == "1"
targets = ("run-dummy-growth-suite.py", "behavior-dummy-client.py", "monitor-dummy-growth-live.py")
self_pid = os.getpid()

def matching_pids():
    result = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        pid = int(name)
        if pid == self_pid:
            continue
        try:
            raw = open(f"/proc/{pid}/cmdline", "rb").read()
        except OSError:
            continue
        cmd = raw.replace(b"\0", b" ").decode("utf-8", "replace")
        if any(target in cmd for target in targets) and any(marker in cmd for marker in markers):
            result.append(pid)
    return result

killed = []
for pid in matching_pids():
    try:
        os.kill(pid, signal.SIGTERM)
        killed.append(pid)
    except ProcessLookupError:
        pass
    except PermissionError:
        pass

if force:
    time.sleep(0.5)
    for pid in matching_pids():
        try:
            os.kill(pid, signal.SIGKILL)
            if pid not in killed:
                killed.append(pid)
        except ProcessLookupError:
            pass
        except PermissionError:
            pass

print(json.dumps(sorted(set(killed))))
"""
    command = [
        str(args.wsl_exe),
        "--cd",
        str(args.wsl_work_dir),
        "--exec",
        str(args.python_exe),
        "-c",
        script,
        json.dumps(markers),
        "1" if force else "0",
    ]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except OSError:
        return []
    try:
        payload = completed.stdout.strip().splitlines()[-1]
        return [int(pid) for pid in json.loads(payload)]
    except Exception:
        return []


@dataclass
class CaseRecord:
    case_id: str
    variant: str
    realm: str
    party_size: int
    repeat_index: int
    case_index: int
    start: int
    segment_seconds: int
    max_segments: int
    max_level: int
    reset_level: int
    extra_args: list[str]
    run_dir: str
    run_dir_arg: str
    case_data_dir: str
    status: str = "queued"
    next_segment: int = 1
    last_passed_segment: int = 0
    attempt: int = 0
    pid: int = 0
    exit_code: int | None = None
    started_at_utc: str = ""
    updated_at_utc: str = field(default_factory=utc_now)
    last_heartbeat_utc: str = ""
    last_error: str = ""
    max_observed_level: int = 0
    kills: int = 0
    target_removed: int = 0
    last_segment: int = 0
    last_segment_xp: int = 0
    last_segment_target_removed: int = 0
    last_segment_deaths: int = 0
    recent_segment_span: str = ""
    recent_xp: int = 0
    recent_target_removed: int = 0
    recent_deaths: int = 0
    min_observed_level: int = 0
    zero_xp_members: int = 0
    lowest_members: str = ""
    deaths: int = 0
    xp: int = 0
    money: int = 0
    last_event: str = ""
    stdout_log: str = ""
    stderr_log: str = ""


def is_completed_before_target_level(case: CaseRecord) -> bool:
    return case.status == "completed" and case.max_observed_level < case.max_level


class AttachedProcess:
    def __init__(self, pid: int) -> None:
        self.pid = pid
        self.returncode: int | None = None

    def poll(self) -> int | None:
        if self.returncode is not None:
            return self.returncode
        if process_exists(self.pid):
            return None
        self.returncode = 0
        return self.returncode

    def terminate(self) -> None:
        self.returncode = -15

    def kill(self) -> None:
        self.returncode = -9


def case_id_for(variant: str, realm: str, repeat_index: int) -> str:
    return f"{variant}-{realm}-r{repeat_index + 1:03d}"


def route_case_index_for_attempt(case: CaseRecord) -> int:
    retry_shift = max(0, int(case.attempt or 0) - int(case.next_segment or 0))
    return int(case.case_index or 0) + retry_shift


def variant_repeat_count(args: argparse.Namespace, variant: str) -> int:
    if args.case_repeats:
        return args.case_repeats
    spec = DEFAULT_VARIANTS[variant]
    return int(getattr(args, str(spec["repeats_arg"]), spec["default_repeats"]))


def parse_case_specs(value: str) -> list[tuple[str, str, int]]:
    specs: list[tuple[str, str, int]] = []
    for token in parse_csv_list(value):
        parts = [part.strip() for part in token.split(":")]
        if len(parts) not in (2, 3) or not parts[0] or not parts[1]:
            raise SystemExit("--case-specs entries must use variant:realm[:repeats]")
        variant, realm = parts[0], parts[1]
        repeats = int(parts[2]) if len(parts) == 3 and parts[2] else 1
        if repeats < 1:
            raise SystemExit("--case-specs repeats must be positive")
        specs.append((variant, realm, repeats))
    return specs


def build_case_manifest(args: argparse.Namespace) -> list[CaseRecord]:
    case_specs = parse_case_specs(args.case_specs) if args.case_specs else []
    variants = sorted({variant for variant, _realm, _repeats in case_specs}) if case_specs else parse_csv_list(args.variants)
    realms = sorted({realm for _variant, realm, _repeats in case_specs}) if case_specs else parse_csv_list(args.realms)
    unknown_variants = [variant for variant in variants if variant not in DEFAULT_VARIANTS]
    if unknown_variants:
        raise SystemExit(f"unknown variant(s): {', '.join(unknown_variants)}")
    unknown_realms = [realm for realm in realms if realm not in REALMS]
    if unknown_realms:
        raise SystemExit(f"unknown realm(s): {', '.join(unknown_realms)}")

    cases: list[CaseRecord] = []
    case_index = 0
    cases_root = args.base_run_dir_path / "cases"
    expanded_specs: list[tuple[str, str, int]]
    if case_specs:
        expanded_specs = case_specs
    else:
        expanded_specs = [
            (variant, realm, variant_repeat_count(args, variant))
            for variant in variants
            for realm in realms
        ]
    for variant, realm, repeats in expanded_specs:
        spec = DEFAULT_VARIANTS[variant]
        if repeats < 1:
            raise SystemExit("repeat counts must be positive")
        for repeat_index in range(repeats):
            case_id = case_id_for(variant, realm, repeat_index)
            run_dir = cases_root / case_id
            case_data_dir = run_dir / case_id
            cases.append(
                CaseRecord(
                    case_id=case_id,
                    variant=variant,
                    realm=realm,
                    party_size=int(spec["party_size"]),
                    repeat_index=repeat_index,
                    case_index=case_index,
                    start=args.start_base + case_index * args.case_start_stride,
                    segment_seconds=int(spec["segment_seconds"]),
                    max_segments=args.max_segments,
                    max_level=args.max_level,
                    reset_level=args.reset_level,
                    extra_args=list(spec["extra_args"]),
                    run_dir=str(run_dir),
                    run_dir_arg=wsl_run_dir_arg(run_dir, args),
                    case_data_dir=str(case_data_dir),
                )
            )
            case_index += 1
    return cases


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError:
        return []


def case_account_roles(case: CaseRecord) -> dict[str, str]:
    roles: dict[str, str] = {}
    accounts_path = Path(case.case_data_dir) / "primary-accounts.csv"
    for row in read_csv_rows(accounts_path):
        account = str(row.get("username") or row.get("account") or "").strip()
        role = str(row.get("growth_role") or "tracked").strip().lower()
        if account:
            roles[account] = role or "tracked"
    return roles


def write_csv_rows(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    replace_path_with_retry(tmp, path)


def replace_path_with_retry(tmp: Path, path: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(ATOMIC_REPLACE_ATTEMPTS):
        try:
            tmp.replace(path)
            return
        except PermissionError as exc:
            last_error = exc
        except OSError as exc:
            if os.name != "nt" or getattr(exc, "winerror", None) != 5:
                raise
            last_error = exc
        time.sleep(ATOMIC_REPLACE_RETRY_SECONDS * (attempt + 1))

    print(f"warning: could not replace {path}: {last_error}", file=sys.stderr, flush=True)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def append_csv_row(path: Path, row: dict[str, Any], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def latest_failure_repro(case: CaseRecord) -> str:
    direct = Path(case.case_data_dir) / "failure-reproduction-command.txt"
    if direct.exists():
        return str(direct)
    attempts_root = Path(case.run_dir).parent.parent / "failed-attempts" / case.case_id
    if attempts_root.exists():
        matches = sorted(attempts_root.rglob("failure-reproduction-command.txt"))
        if matches:
            return str(matches[-1])
    return ""


def refresh_case_progress(case: CaseRecord) -> None:
    timeline_rows = read_csv_rows(Path(case.run_dir) / "timeline.csv")
    account_roles = case_account_roles(case)
    max_level = 0
    min_level = 0
    max_segment = case.last_passed_segment
    target_removed = 0
    deaths = 0
    xp = 0
    money = 0
    last_event = ""
    timeline_max_segment = case.last_passed_segment
    latest_by_account: dict[str, dict[str, Any]] = {}
    segment_totals: dict[int, dict[str, int]] = {}
    for row in timeline_rows:
        segment = as_int(row.get("segment"), max_segment)
        account = str(row.get("account") or row.get("character") or "")
        growth_role = str(row.get("growth_role") or "").strip().lower()
        if not growth_role:
            growth_role = account_roles.get(account, "tracked")
        is_carry = growth_role == "carry"
        level_after = as_int(row.get("level_after"))
        if not is_carry:
            max_level = max(max_level, level_after)
        max_segment = max(max_segment, segment)
        timeline_max_segment = max(timeline_max_segment, segment)
        row_target_removed = as_int(row.get("target_removed"))
        row_deaths = max(0, as_int(row.get("death_delta")))
        row_xp = as_int(row.get("xp_effective_delta"), as_int(row.get("text_xp_delta"), as_int(row.get("xp_delta"))))
        row_money = as_int(row.get("money_delta_copper"))
        row_loot = as_int(row.get("loot_acquired"))
        target_removed += row_target_removed
        deaths += row_deaths
        if not is_carry:
            xp += row_xp
            money += row_money
        if segment > 0:
            totals = segment_totals.setdefault(
                segment,
                {"xp": 0, "target_removed": 0, "deaths": 0, "row_rewarded_removed": 0, "tracked_reward": 0},
            )
            if not is_carry:
                totals["xp"] += max(0, row_xp)
                tracked_reward = max(0, row_xp) + max(0, row_money) + max(0, row_loot)
                totals["tracked_reward"] += tracked_reward
                if row_target_removed > 0 and tracked_reward > 0:
                    totals["row_rewarded_removed"] += row_target_removed
            totals["target_removed"] += max(0, row_target_removed)
            totals["deaths"] += row_deaths
        role_suffix = "/carry" if is_carry else ""
        last_event = f"s{row.get('segment', '')}/{row.get('account', '')}{role_suffix}/L{row.get('level_after', '')}"
        if account and not is_carry:
            latest_by_account[account] = row

    data_dir = Path(case.case_data_dir)
    for metrics_path in data_dir.rglob("segment-*-metrics.csv") if data_dir.exists() else []:
        match = re.search(r"segment-(\d+)-metrics\.csv$", metrics_path.name)
        metric_segment = 0
        if match:
            metric_segment = int(match.group(1))
            max_segment = max(max_segment, metric_segment)
        if metric_segment and metric_segment <= timeline_max_segment:
            continue
        for row in read_csv_rows(metrics_path):
            row_target_removed = as_int(row.get("target_removed"))
            row_deaths = max(0, as_int(row.get("player_deaths")))
            target_removed += row_target_removed
            deaths += row_deaths
            if metric_segment > 0:
                totals = segment_totals.setdefault(
                    metric_segment,
                    {"xp": 0, "target_removed": 0, "deaths": 0, "row_rewarded_removed": 0, "tracked_reward": 0},
                )
                totals["target_removed"] += max(0, row_target_removed)
                totals["deaths"] += row_deaths
    zero_xp_members = 0
    lowest: list[tuple[int, int, str, str]] = []
    for account, row in latest_by_account.items():
        level_after = as_int(row.get("level_after"))
        xp_after = as_int(row.get("xp_after"))
        if level_after <= 1 and xp_after <= 0:
            zero_xp_members += 1
        if level_after > 0:
            lowest.append((level_after, xp_after, account, f"{account}:L{level_after}/XP{xp_after}"))
    min_level = min((item[0] for item in lowest), default=0)
    case.max_observed_level = max(case.max_observed_level, max_level)
    case.min_observed_level = min_level
    case.target_removed = target_removed
    rewarded_target_removed = 0
    for totals in segment_totals.values():
        row_rewarded_removed = max(0, int(totals.get("row_rewarded_removed", 0) or 0))
        if row_rewarded_removed > 0:
            rewarded_target_removed += row_rewarded_removed
        elif int(case.party_size or 0) > 1 and max(0, int(totals.get("tracked_reward", 0) or 0)) > 0:
            rewarded_target_removed += max(0, int(totals.get("target_removed", 0) or 0))
    case.kills = rewarded_target_removed
    recent_segments = sorted(segment_totals)[-2:]
    if recent_segments:
        latest_segment = recent_segments[-1]
        latest_totals = segment_totals[latest_segment]
        case.last_segment = latest_segment
        case.last_segment_xp = latest_totals["xp"]
        case.last_segment_target_removed = latest_totals["target_removed"]
        case.last_segment_deaths = latest_totals["deaths"]
        case.recent_segment_span = (
            str(recent_segments[0]) if len(recent_segments) == 1 else f"{recent_segments[0]}-{recent_segments[-1]}"
        )
        case.recent_xp = sum(segment_totals[segment]["xp"] for segment in recent_segments)
        case.recent_target_removed = sum(segment_totals[segment]["target_removed"] for segment in recent_segments)
        case.recent_deaths = sum(segment_totals[segment]["deaths"] for segment in recent_segments)
    else:
        case.last_segment = 0
        case.last_segment_xp = 0
        case.last_segment_target_removed = 0
        case.last_segment_deaths = 0
        case.recent_segment_span = ""
        case.recent_xp = 0
        case.recent_target_removed = 0
        case.recent_deaths = 0
    case.zero_xp_members = zero_xp_members
    case.lowest_members = ",".join(item[3] for item in sorted(lowest)[:4])
    case.deaths = deaths
    case.xp = xp
    case.money = money
    case.last_event = last_event or case.last_event


def effective_worker_hold_seconds(case: CaseRecord) -> float:
    base = float(case.segment_seconds or 0)
    level = int(case.max_observed_level or case.reset_level or 1)
    party_size = int(case.party_size or 0)
    if party_size >= 4 and level <= 4:
        return max(base, 360.0)
    if party_size >= 2 and level <= 4:
        return max(base, 300.0)
    if case.realm == "hib" and party_size <= 1 and level == 4:
        return max(base, 300.0)
    return base


def worker_timeout_seconds(args: argparse.Namespace, case: CaseRecord) -> float:
    grace = max(0.0, float(getattr(args, "worker_timeout_grace_seconds", 0.0) or 0.0))
    if grace <= 0.0:
        return 0.0
    return max(1.0, effective_worker_hold_seconds(case) + grace)


def case_segment_has_startup_activity(case: CaseRecord) -> bool:
    for log_path in (case.stdout_log, case.stderr_log):
        if not log_path:
            continue
        try:
            if Path(log_path).stat().st_size > 0:
                return True
        except OSError:
            continue

    data_dir = Path(case.case_data_dir)
    pattern = f"segment-{case.next_segment:03d}-*.jsonl"
    for folder in ("encounters", "movement"):
        activity_dir = data_dir / folder
        if not activity_dir.exists():
            continue
        try:
            if any(path.stat().st_size > 0 for path in activity_dir.glob(pattern)):
                return True
        except OSError:
            continue
    return False


def worker_startup_no_output_fatal_reason(
    args: argparse.Namespace,
    case: CaseRecord,
    elapsed_seconds: float,
) -> str:
    threshold = float(getattr(args, "worker_startup_no_output_fatal_seconds", 0.0) or 0.0)
    if threshold <= 0.0 or elapsed_seconds < threshold:
        return ""
    if case_segment_has_startup_activity(case):
        return ""
    return (
        "worker startup produced no output/artifacts "
        f"after {elapsed_seconds:.1f}s threshold={threshold:.1f}s"
    )


def live_fatal_numeric(row: dict[str, Any], key: str) -> float:
    try:
        return float(row.get(key, 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def live_fatal_bool(row: dict[str, Any], key: str) -> bool:
    value = row.get(key)
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes"}


def case_planned_buy_shortage_copper(case: CaseRecord) -> int:
    summary_path = Path(case.run_dir) / "summary.md"
    if not summary_path.exists():
        return 0
    try:
        for line in summary_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "Planned merchant buy shortage copper" not in line:
                continue
            match = re.search(r"`?(-?\d+)`?", line)
            if match:
                return max(0, int(match.group(1)))
    except OSError:
        return 0
    return 0


def iter_case_segment_encounter_rows(case: CaseRecord) -> Iterable[dict[str, Any]]:
    data_dir = Path(case.case_data_dir)
    if not data_dir.exists():
        return
    encounter_dir = data_dir / "encounters"
    if not encounter_dir.exists():
        return
    pattern = f"segment-{case.next_segment:03d}-*.jsonl"
    for path in sorted(encounter_dir.glob(pattern)):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue


def iter_case_segment_movement_rows(case: CaseRecord) -> Iterable[dict[str, Any]]:
    data_dir = Path(case.case_data_dir)
    if not data_dir.exists():
        return
    movement_dir = data_dir / "movement"
    if not movement_dir.exists():
        return
    pattern = f"segment-{case.next_segment:03d}-*.jsonl"
    for path in sorted(movement_dir.glob(pattern)):
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue


LIVE_FATAL_RUNTIME_FAILURE_MEMORY_FIELDS = [
    "timestamp_utc",
    "case",
    "realm",
    "party_size",
    "segment",
    "level",
    "reason",
    "action",
    "target_name",
    "target_level",
    "source",
    "expires_segment",
]
LIVE_FATAL_RUNTIME_FAILURE_MEMORY_TTL_SEGMENTS = 3

LIVE_FATAL_DEATH_KILLER_PATTERNS = [
    re.compile(r"^(?P<victim>.+?)(?:\uC774|\uAC00|\uC774\(\uAC00\))\s+(?P<killer>.+?)\uC5D0\uAC8C\s+\uC0AC\uB9DD\uD588\uC2B5\uB2C8\uB2E4[.!]?$", re.IGNORECASE),
    re.compile(r"^(?P<victim>.+?) was (?:just )?killed by (?P<killer>.+?)(?: in .+)?[.!]?$", re.IGNORECASE),
]

LIVE_FATAL_ACTOR_FIELDS = [
    "recent_incoming_attacker",
    "off_target_attacker",
    "off_target_attacker_name",
    "party_attack_attacker",
    "attacker_name",
    "active_target_name",
    "current_target_name",
    "target_name",
    "rescue_target_name",
    "leader_target_focus_name",
    "leader_target_name",
]

LIVE_FATAL_OFFTARGET_ACTOR_FIELDS = [
    "rescue_target_name",
    "off_target_attacker",
    "off_target_attacker_name",
    "recent_incoming_attacker",
    "party_attack_attacker",
    "attacker_name",
    "blocked_target_name",
]


def clean_live_fatal_actor_name(value: str) -> str:
    name = " ".join(str(value or "").strip().split())
    name = re.sub(r"^(?:a|an|the)\s+", "", name, flags=re.IGNORECASE).strip()
    name = re.sub(r"^[\uFFFD?]+(?:\s+|$)", "", name).strip()
    name = re.sub(r"^(?:[^\x00-\x7F]+\s+)+(?=[A-Za-z0-9])", "", name).strip()
    return name


def normalize_live_fatal_actor_key(value: str) -> str:
    return " ".join(clean_live_fatal_actor_name(value).replace("\u2019", "'").lower().split())


def parse_live_fatal_death_victim_killer_names(text: str) -> tuple[str, str]:
    normalized = str(text or "").strip()
    if not normalized:
        return "", ""
    for pattern in LIVE_FATAL_DEATH_KILLER_PATTERNS:
        match = pattern.match(normalized)
        if match is not None:
            return (
                clean_live_fatal_actor_name(match.group("victim")),
                clean_live_fatal_actor_name(match.group("killer")),
            )
    return "", ""


def parse_live_fatal_death_killer_name(text: str) -> str:
    _victim_name, killer_name = parse_live_fatal_death_victim_killer_names(text)
    return killer_name


def add_live_fatal_actor_stat(
    stats: dict[str, dict[str, int | str]],
    name: str,
    *,
    level: int = 0,
    source: str,
) -> None:
    actor_name = clean_live_fatal_actor_name(name)
    key = normalize_live_fatal_actor_key(actor_name)
    if not key:
        return
    actor_stats = stats.setdefault(
        key,
        {
            "name": actor_name,
            "level": int(level or 0),
            "count": 0,
            "source": source,
        },
    )
    actor_stats["count"] = int(actor_stats.get("count", 0) or 0) + 1
    if not int(actor_stats.get("level", 0) or 0) and int(level or 0) > 0:
        actor_stats["level"] = int(level or 0)


def live_fatal_actor_names_from_row(row: dict[str, Any], source: str) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    def add_from_fields(fields: Iterable[str]) -> None:
        for field in fields:
            actor_name = clean_live_fatal_actor_name(str(row.get(field, "") or ""))
            key = normalize_live_fatal_actor_key(actor_name)
            if not key or key in seen:
                continue
            seen.add(key)
            names.append(actor_name)

    if source == "live_fatal_offtarget_damage":
        add_from_fields(LIVE_FATAL_OFFTARGET_ACTOR_FIELDS)
        if names:
            return names
    add_from_fields(LIVE_FATAL_ACTOR_FIELDS)
    return names


def live_fatal_row_level(row: dict[str, Any]) -> int:
    for field in (
        "attacker_level",
        "target_level",
        "active_target_level",
        "rescue_target_level",
        "leader_target_level",
    ):
        level = as_int(row.get(field))
        if level > 0:
            return level
    return 0


def live_fatal_actor_stats(case: CaseRecord) -> dict[str, dict[str, int | str]]:
    stats: dict[str, dict[str, int | str]] = {}
    case_actor_keys = {
        normalize_live_fatal_actor_key(account)
        for account in case_account_roles(case).keys()
        if str(account or "").strip()
    }
    for row in iter_case_segment_encounter_rows(case):
        event = str(row.get("event", "") or "")
        if event == "server_message":
            victim_name, killer_name = parse_live_fatal_death_victim_killer_names(str(row.get("text", "") or ""))
            victim_key = normalize_live_fatal_actor_key(victim_name)
            if case_actor_keys and victim_key not in case_actor_keys:
                continue
            if killer_name:
                add_live_fatal_actor_stat(
                    stats,
                    killer_name,
                    level=live_fatal_row_level(row),
                    source="live_fatal_death_message",
                )
            continue
        source = ""
        if event == "death_detected":
            source = "live_fatal_death_detected"
        elif event in {"flee_start", "unengaged_pull_offtarget_damage"}:
            reason = str(row.get("reason", "") or "")
            if reason == "unengaged_pull_offtarget_damage" or event == "unengaged_pull_offtarget_damage":
                source = "live_fatal_offtarget_damage"
        elif event == "combat_finish" and str(row.get("outcome", "") or "") == "critical_health_drop_aggro":
            source = "live_fatal_critical_health"
        if not source:
            continue
        level = live_fatal_row_level(row)
        for actor_name in live_fatal_actor_names_from_row(row, source):
            add_live_fatal_actor_stat(stats, actor_name, level=level, source=source)
    return stats


def live_fatal_memory_reason(fatal_reason: str) -> str:
    reason = str(fatal_reason or "").lower()
    if "death" in reason or "killed" in reason:
        return "death_pressure"
    if "gear/economy" in reason or "critical_health" in reason:
        return "combat_pressure_no_kill"
    if "scan empty" in reason:
        return "scan_empty"
    if "idle no engagement" in reason:
        return "no_engagement"
    return "live_fatal"


def live_fatal_should_downgrade_target_plan(fatal_reason: str) -> bool:
    reason = str(fatal_reason or "").lower()
    return any(
        token in reason
        for token in (
            "scan empty",
            "idle no engagement",
            "required target home oscillation",
            "route_home_fast_travel failed",
        )
    )


def record_live_fatal_runtime_failure_memory(case: CaseRecord, fatal_reason: str) -> int:
    stats = live_fatal_actor_stats(case)
    path = Path(case.case_data_dir) / "runtime-failure-memory.csv"
    case_actor_keys = {
        normalize_live_fatal_actor_key(account)
        for account in case_account_roles(case).keys()
        if str(account or "").strip()
    }
    existing: set[tuple[str, int, str]] = set()
    existing_downgrades: set[tuple[int, str]] = set()
    if path.exists():
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    target_key = normalize_live_fatal_actor_key(str(row.get("target_name", "") or ""))
                    segment = as_int(row.get("segment"))
                    reason = str(row.get("reason", "") or "")
                    action = str(row.get("action", "") or "")
                    if target_key:
                        existing.add((target_key, segment, reason))
                    if action == "downgrade_target_plan":
                        existing_downgrades.add((segment, reason))
        except (OSError, csv.Error):
            existing = set()
            existing_downgrades = set()

    memory_reason = live_fatal_memory_reason(fatal_reason)
    rows: list[dict[str, object]] = []
    expires_segment = int(case.next_segment or 0) + LIVE_FATAL_RUNTIME_FAILURE_MEMORY_TTL_SEGMENTS
    if live_fatal_should_downgrade_target_plan(fatal_reason):
        downgrade_key = (int(case.next_segment or 0), memory_reason)
        if downgrade_key not in existing_downgrades:
            rows.append(
                {
                    "timestamp_utc": utc_now(),
                    "case": case.case_id,
                    "realm": case.realm,
                    "party_size": int(case.party_size or 0),
                    "segment": int(case.next_segment or 0),
                    "level": 0,
                    "reason": memory_reason,
                    "action": "downgrade_target_plan",
                    "source": "live_fatal_encounter",
                    "expires_segment": expires_segment,
                }
            )
            existing_downgrades.add(downgrade_key)
    for actor_stats in stats.values():
        target_name = str(actor_stats.get("name", "") or "").strip()
        target_key = normalize_live_fatal_actor_key(target_name)
        if not target_key:
            continue
        if target_key in case_actor_keys:
            continue
        existing_key = (target_key, int(case.next_segment or 0), memory_reason)
        if existing_key in existing:
            continue
        rows.append(
            {
                "timestamp_utc": utc_now(),
                "case": case.case_id,
                "realm": case.realm,
                "party_size": int(case.party_size or 0),
                "segment": int(case.next_segment or 0),
                "level": 0,
                "reason": memory_reason,
                "action": "avoid_target",
                "target_name": target_name,
                "target_level": actor_stats.get("level", ""),
                "source": actor_stats.get("source", "live_fatal_encounter"),
                "expires_segment": expires_segment,
            }
        )
        existing.add(existing_key)
    if not rows:
        return 0

    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LIVE_FATAL_RUNTIME_FAILURE_MEMORY_FIELDS)
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in LIVE_FATAL_RUNTIME_FAILURE_MEMORY_FIELDS})
    return len(rows)


def live_idle_no_engagement_fatal_seconds(args: argparse.Namespace, case: CaseRecord) -> float:
    base = float(getattr(args, "live_idle_no_engagement_fatal_seconds", 30.0) or 30.0)
    party_size = int(getattr(case, "party_size", 0) or 0)
    if party_size >= 8:
        return max(base, 120.0)
    if party_size >= 4:
        return max(base, 90.0)
    if party_size >= 2:
        return max(base, 75.0)
    return max(base, 60.0)


def live_death_loop_fatal_count(args: argparse.Namespace, case: CaseRecord) -> int:
    base = int(getattr(args, "live_death_loop_fatal_count", 3) or 3)
    party_size = int(getattr(case, "party_size", 0) or 0)
    if party_size >= 8:
        return max(base, 12)
    if party_size >= 4:
        return max(base, 8)
    if party_size >= 2:
        return max(base, 5)
    return max(base, 3)


RECOVERY_IDLE_EXEMPT_STATES = {
    "DeadReleaseRecover",
    "DropAggroAndRecover",
    "RestRecover",
    "ReturnToObjective",
}


def case_live_fatal_reason(args: argparse.Namespace, case: CaseRecord) -> str:
    scan_empty_eligible_zero = 0
    scan_empty_visible_zero = 0
    nav_path_failed = 0
    required_home_move = 0
    objective_ready = 0
    idle_ready_ticks = 0
    combat_events = 0
    api_scout_events = 0
    death_events = 0
    target_object_removed_events = 0
    recovery_or_travel_events = 0
    recovery_events = 0
    max_damage_done = 0
    critical_health_drop_aggro = 0
    max_failed_target_remaining_percent = 0.0
    first_event_at = 0.0
    last_event_at = 0.0
    last_tick_position: tuple[int, int] | None = None
    reject_reasons: dict[str, int] = {}

    for row in iter_case_segment_encounter_rows(case):
        event = str(row.get("event", "") or "")
        timestamp = live_fatal_numeric(row, "t")
        if timestamp > 0:
            if first_event_at <= 0.0:
                first_event_at = timestamp
            last_event_at = timestamp
        max_damage_done = max(max_damage_done, int(live_fatal_numeric(row, "damage_done")))
        behavior_state = str(row.get("behavior_state", "") or "")
        if behavior_state in RECOVERY_IDLE_EXEMPT_STATES:
            recovery_events += 1
            recovery_or_travel_events += 1
        elif behavior_state == "TravelToObjective":
            recovery_or_travel_events += 1
        if event == "hunter_target_scan_empty":
            if behavior_state in RECOVERY_IDLE_EXEMPT_STATES or behavior_state == "TravelToObjective":
                continue
            visible = int(live_fatal_numeric(row, "hunter_visible_npcs"))
            eligible = int(live_fatal_numeric(row, "hunter_eligible_npcs"))
            if visible > 0 and eligible <= 0:
                scan_empty_eligible_zero += 1
                counts = row.get("hunter_reject_counts", {})
                if isinstance(counts, dict):
                    for reason, value in counts.items():
                        if reason in {"visible", "eligible"}:
                            continue
                        reject_reasons[str(reason)] = reject_reasons.get(str(reason), 0) + as_int(value)
            elif visible <= 0:
                scan_empty_visible_zero += 1
        elif event in {"combat_start", "combat_finish"}:
            combat_events += 1
            if event == "combat_finish":
                outcome = str(row.get("outcome", "") or "")
                if outcome == "critical_health_drop_aggro":
                    critical_health_drop_aggro += 1
                    max_failed_target_remaining_percent = max(
                        max_failed_target_remaining_percent,
                        live_fatal_numeric(row, "active_target_remaining_health_percent"),
                    )
        elif event == "hunter_target_api_scout":
            api_scout_events += 1
        elif event == "death_detected":
            death_events += 1
        elif event == "target_object_removed":
            target_object_removed_events += 1
        elif event == "nav_path_failed":
            nav_path_failed += 1
        elif event == "behavior_state_change":
            reason = str(row.get("reason", "") or row.get("behavior_state_reason", "") or "")
            if reason == "required_target_home_move":
                required_home_move += 1
            elif reason == "objective_area_ready":
                objective_ready += 1
        elif event == "encounter_tick":
            if behavior_state in RECOVERY_IDLE_EXEMPT_STATES:
                continue
            if behavior_state == "TravelToObjective":
                last_tick_position = (
                    int(live_fatal_numeric(row, "x")),
                    int(live_fatal_numeric(row, "y")),
                )
                continue
            x = int(live_fatal_numeric(row, "x"))
            y = int(live_fatal_numeric(row, "y"))
            position = (x, y)
            if behavior_state == "TravelToObjective" and last_tick_position is not None:
                dx = x - last_tick_position[0]
                dy = y - last_tick_position[1]
                if (dx * dx + dy * dy) >= 10000:
                    last_tick_position = position
                    continue
            last_tick_position = position
            if int(case.party_size or 0) > 1 and "is_leader" in row and not live_fatal_bool(row, "is_leader"):
                continue
            if (
                int(live_fatal_numeric(row, "current_target")) <= 0
                and live_fatal_numeric(row, "health_percent") >= 80.0
                and not live_fatal_bool(row, "is_dead")
            ):
                idle_ready_ticks += 1

    top_reason = ""
    if reject_reasons:
        top_reason = max(reject_reasons.items(), key=lambda item: item[1])[0]
    elapsed = max(0.0, last_event_at - first_event_at) if first_event_at > 0.0 else 0.0

    if (
        recovery_events <= 0
        and combat_events <= 0
        and api_scout_events <= 0
        and scan_empty_eligible_zero >= int(
        getattr(args, "live_scan_empty_fatal_count", 3) or 3
        )
    ):
        return f"live fatal: repeated target scan empty eligible=0 count={scan_empty_eligible_zero} reason={top_reason or 'unknown'}"
    if (
        recovery_events <= 0
        and combat_events <= 0
        and scan_empty_visible_zero >= int(getattr(args, "live_scan_empty_no_visible_fatal_count", 5) or 5)
    ):
        return f"live fatal: repeated target scan empty visible=0 count={scan_empty_visible_zero}"
    if nav_path_failed >= int(getattr(args, "live_nav_path_failed_fatal_count", 3) or 3):
        return f"live fatal: repeated nav_path_failed count={nav_path_failed}"
    route_home_failed = 0
    route_home_reason_counts: dict[str, int] = {}
    for row in iter_case_segment_movement_rows(case):
        if str(row.get("event", "") or "") != "route_home_fast_travel_reposition":
            continue
        if live_fatal_bool(row, "moved"):
            continue
        route_home_failed += 1
        reason = str(row.get("reason", "") or "unknown").strip() or "unknown"
        route_home_reason_counts[reason] = route_home_reason_counts.get(reason, 0) + 1
    route_home_threshold = int(getattr(args, "live_route_home_failed_fatal_count", 5) or 0)
    if route_home_threshold > 0 and route_home_failed >= route_home_threshold:
        top_route_home_reason = "unknown"
        if route_home_reason_counts:
            top_route_home_reason = max(route_home_reason_counts.items(), key=lambda item: item[1])[0]
        return f"live fatal: repeated route_home_fast_travel failed count={route_home_failed} reason={top_route_home_reason}"
    if death_events >= live_death_loop_fatal_count(args, case):
        return f"live fatal: repeated deaths count={death_events}"
    gear_bottleneck_count = int(getattr(args, "live_solo_gear_bottleneck_fatal_count", 1) or 0)
    gear_bottleneck_seconds = float(getattr(args, "live_solo_gear_bottleneck_fatal_seconds", 30.0) or 0.0)
    gear_shortage_copper = case_planned_buy_shortage_copper(case)
    if (
        int(case.party_size or 0) <= 1
        and gear_bottleneck_count > 0
        and gear_bottleneck_seconds > 0.0
        and gear_shortage_copper > 0
        and critical_health_drop_aggro >= gear_bottleneck_count
        and recovery_events <= 0
        and target_object_removed_events <= 0
        and elapsed >= gear_bottleneck_seconds
    ):
        return (
            "live fatal: solo gear/economy bottleneck "
            f"buy_shortage_copper={gear_shortage_copper} "
            f"critical_health_drop_aggro={critical_health_drop_aggro} "
            f"target_remaining={max_failed_target_remaining_percent:.1f}% "
            f"damage_done={max_damage_done} elapsed={elapsed:.1f}s"
        )
    solo_death_no_progress_count = int(getattr(args, "live_solo_death_no_progress_fatal_count", 1) or 0)
    solo_death_no_progress_seconds = float(
        getattr(args, "live_solo_death_no_progress_fatal_seconds", 55.0) or 0.0
    )
    if (
        int(case.party_size or 0) <= 1
        and solo_death_no_progress_count > 0
        and solo_death_no_progress_seconds > 0.0
        and death_events >= solo_death_no_progress_count
        and target_object_removed_events <= 0
        and elapsed >= solo_death_no_progress_seconds
    ):
        return (
            "live fatal: solo death without progress "
            f"deaths={death_events} target_removed={target_object_removed_events} "
            f"damage_done={max_damage_done} elapsed={elapsed:.1f}s"
        )
    if (
        int(case.party_size or 0) <= 1
        and combat_events <= 0
        and target_object_removed_events >= int(getattr(args, "live_target_removed_no_combat_fatal_count", 12) or 12)
    ):
        return f"live fatal: repeated target_object_removed without combat count={target_object_removed_events}"
    if (
        combat_events <= 0
        and recovery_events <= 0
        and idle_ready_ticks >= int(getattr(args, "live_idle_no_engagement_fatal_ticks", 10) or 10)
        and elapsed >= live_idle_no_engagement_fatal_seconds(args, case)
    ):
        return f"live fatal: idle no engagement ticks={idle_ready_ticks} elapsed={elapsed:.1f}s"
    if (
        combat_events <= 0
        and required_home_move >= int(getattr(args, "live_required_home_oscillation_fatal_count", 10) or 10)
        and objective_ready >= int(getattr(args, "live_required_home_oscillation_fatal_count", 10) or 10)
    ):
        return f"live fatal: required target home oscillation move={required_home_move} ready={objective_ready}"
    return ""


COMPLETED_STALL_RECOVERY_EXEMPT_STATES = {
    "DeadReleaseRecover",
    "DropAggroAndRecover",
    "RestRecover",
}


def completed_segment_ended_in_recovery(case: CaseRecord) -> bool:
    last_state = ""
    for row in iter_case_segment_encounter_rows(case):
        state = str(row.get("behavior_state", "") or "")
        if state:
            last_state = state
    return last_state in COMPLETED_STALL_RECOVERY_EXEMPT_STATES


def completed_segment_stall_reason(args: argparse.Namespace, case: CaseRecord) -> str:
    threshold = int(getattr(args, "completed_stall_fatal_segments", 0) or 0)
    if threshold <= 0:
        return ""

    role_by_account = {
        normalize_live_fatal_actor_key(account): role
        for account, role in case_account_roles(case).items()
        if str(account or "").strip()
    }
    segment_totals: dict[int, dict[str, int]] = {}
    for row in read_csv_rows(Path(case.run_dir) / "timeline.csv"):
        segment = as_int(row.get("segment"))
        if segment <= 0 or segment > case.next_segment:
            continue
        totals = segment_totals.setdefault(
            segment,
            {
                "rows": 0,
                "xp": 0,
                "tracked_xp": 0,
                "level_delta": 0,
                "tracked_level_delta": 0,
                "target_removed": 0,
                "target_removed_no_reward": 0,
                "target_removed_no_xp": 0,
                "deaths": 0,
                "loot": 0,
                "money": 0,
                "transaction": 0,
                "merchant_action": 0,
            },
        )
        account_key = normalize_live_fatal_actor_key(str(row.get("account") or row.get("character") or ""))
        growth_role = str(row.get("growth_role") or role_by_account.get(account_key, "tracked") or "tracked").strip().lower()
        tracked_row = growth_role != "carry"
        xp_delta = max(
            0,
            as_int(
                row.get("xp_effective_delta"),
                as_int(row.get("text_xp_delta"), as_int(row.get("xp_delta"))),
            ),
        )
        level_delta = max(0, as_int(row.get("level_delta")))
        totals["rows"] += 1
        totals["xp"] += xp_delta
        totals["level_delta"] += level_delta
        if tracked_row:
            totals["tracked_xp"] += xp_delta
            totals["tracked_level_delta"] += level_delta
        totals["target_removed"] += max(0, as_int(row.get("target_removed")))
        totals["target_removed_no_reward"] += max(0, as_int(row.get("target_removed_no_reward")))
        if "target_removed_no_xp" in str(row.get("bottleneck_reason") or ""):
            totals["target_removed_no_xp"] += 1
        totals["deaths"] += max(0, as_int(row.get("death_delta"), as_int(row.get("player_deaths"))))
        totals["loot"] += max(0, as_int(row.get("loot_acquired")))
        totals["money"] += max(0, as_int(row.get("money_delta_copper")))
        totals["transaction"] += abs(as_int(row.get("money_delta_copper")))
        totals["transaction"] += abs(as_int(row.get("inventory_rows_delta")))
        totals["transaction"] += abs(as_int(row.get("inventory_items_delta")))
        totals["transaction"] += abs(as_int(row.get("weapon_items_delta")))
        totals["transaction"] += abs(as_int(row.get("armor_items_delta")))
        totals["transaction"] += abs(as_int(row.get("equipment_other_items_delta")))
        totals["transaction"] += abs(as_int(row.get("junk_items_delta")))
        totals["merchant_action"] += max(0, as_int(row.get("startup_merchant_sell")))
        totals["merchant_action"] += max(0, as_int(row.get("startup_merchant_buy")))
        totals["merchant_action"] += max(0, as_int(row.get("startup_merchant_equip")))

    recent_segments = sorted(segment_totals)[-threshold:]
    if len(recent_segments) < threshold:
        return ""
    recent = [segment_totals[segment] for segment in recent_segments]
    if any(totals["tracked_xp"] > 0 or totals["tracked_level_delta"] > 0 for totals in recent):
        return ""

    target_removed = sum(totals["target_removed"] for totals in recent)
    target_removed_no_reward = sum(totals["target_removed_no_reward"] for totals in recent)
    target_removed_no_xp = sum(totals["target_removed_no_xp"] for totals in recent)
    deaths = sum(totals["deaths"] for totals in recent)
    loot = sum(totals["loot"] for totals in recent)
    money = sum(totals["money"] for totals in recent)
    transaction = sum(totals["transaction"] for totals in recent)
    merchant_action = sum(totals["merchant_action"] for totals in recent)
    span = f"{recent_segments[0]}-{recent_segments[-1]}"
    if deaths <= 0 and target_removed_no_reward <= 0 and target_removed_no_xp <= 0 and merchant_action > 0:
        return ""
    if target_removed > 0:
        return (
            f"completed stall: no tracked xp/level across {threshold} segments {span} "
            f"despite target_removed={target_removed} target_removed_no_reward={target_removed_no_reward} "
            f"target_removed_no_xp={target_removed_no_xp} deaths={deaths} loot={loot} money={money} "
            f"transaction={transaction}"
        )
    return (
        f"completed stall: no tracked xp/level/target_removed across {threshold} segments {span} "
        f"deaths={deaths} loot={loot} money={money} transaction={transaction}"
    )


def completed_party_member_stuck_reason(args: argparse.Namespace, case: CaseRecord) -> str:
    threshold = int(getattr(args, "party_member_stuck_fatal_segments", 0) or 0)
    if threshold <= 0 or int(case.party_size or 0) < 4:
        return ""
    if int(case.zero_xp_members or 0) <= 0:
        return ""
    if int(case.max_observed_level or 0) < max(3, int(case.reset_level or 1) + 2):
        return ""
    rows = read_csv_rows(Path(case.run_dir) / "timeline.csv")
    latest_by_account: dict[str, dict[str, str]] = {}
    segment_rows: dict[int, list[dict[str, str]]] = {}
    for row in rows:
        segment = as_int(row.get("segment"))
        if segment <= 0 or segment > int(case.next_segment or 0):
            continue
        account = str(row.get("account") or row.get("character") or "")
        if account:
            latest_by_account[account] = row
        segment_rows.setdefault(segment, []).append(row)

    stuck_accounts = {
        account
        for account, row in latest_by_account.items()
        if as_int(row.get("level_after")) <= 1 and as_int(row.get("xp_after")) <= 0
    }
    if not stuck_accounts:
        return ""

    recent_segments = sorted(segment_rows)[-threshold:]
    if len(recent_segments) < threshold:
        return ""
    for segment in recent_segments:
        for row in segment_rows.get(segment, []):
            account = str(row.get("account") or row.get("character") or "")
            if account not in stuck_accounts:
                continue
            xp_delta = max(
                0,
                as_int(
                    row.get("xp_effective_delta"),
                    as_int(row.get("text_xp_delta"), as_int(row.get("xp_delta"))),
                ),
            )
            if xp_delta > 0 or max(0, as_int(row.get("level_delta"))) > 0:
                return ""
    return (
        f"party member stuck: zero_xp_members={case.zero_xp_members} "
        f"Lmin={case.min_observed_level} Lmax={case.max_observed_level} "
        f"lowest={case.lowest_members or '-'}"
    )


class CaseSupervisor:
    def __init__(
        self,
        args: argparse.Namespace,
        cases: list[CaseRecord],
        *,
        process_factory: Callable[..., Any] | None = None,
        stale_process_cleaner: Callable[..., list[int]] | None = None,
    ) -> None:
        self.args = args
        self.cases = {case.case_id: case for case in cases}
        self.case_order = [case.case_id for case in cases]
        self.process_factory = process_factory or subprocess.Popen
        self.stale_process_cleaner = stale_process_cleaner or kill_wsl_case_processes
        self.processes: dict[str, Any] = {}
        self.process_started_monotonic: dict[str, float] = {}
        self.command_offset = 0
        self.max_concurrent_cases = args.max_concurrent_cases
        self.last_progress_print = 0.0
        self.shutdown_requested = False

        self.base_run_dir = args.base_run_dir_path
        self.control_dir = self.base_run_dir / "control"
        self.commands_path = self.control_dir / "commands.jsonl"
        self.command_offset_path = self.control_dir / "commands.offset"
        self.events_path = self.base_run_dir / "case-events.jsonl"
        self.manifest_path = self.base_run_dir / "case-manifest.csv"
        self.status_path = self.base_run_dir / "case-status.csv"
        self.state_path = self.base_run_dir / "case-state.json"
        self.aggregate_timeline_path = self.base_run_dir / "aggregate-timeline.csv"
        self.bottleneck_ledger_path = self.base_run_dir / "bottleneck-ledger.csv"
        self.interventions_path = self.base_run_dir / "interventions.jsonl"
        self.logs_dir = self.base_run_dir / "logs"
        self.failed_attempts_dir = self.base_run_dir / "failed-attempts"

    def prepare(self) -> None:
        self.base_run_dir.mkdir(parents=True, exist_ok=True)
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.failed_attempts_dir.mkdir(parents=True, exist_ok=True)
        self.commands_path.touch(exist_ok=True)
        if self.command_offset_path.exists():
            self.command_offset = as_int(self.command_offset_path.read_text(encoding="utf-8").strip())
        else:
            self.command_offset = 0
        for case in self.cases.values():
            Path(case.run_dir).mkdir(parents=True, exist_ok=True)
        self.reattach_running_workers()
        self.write_manifest()
        self.write_status_files()
        self.record_event("supervisor_started", max_concurrent_cases=self.max_concurrent_cases)

    def reattach_running_workers(self) -> None:
        for case in self.cases.values():
            if case.status != "running" or case.pid <= 0:
                continue
            if not process_exists(case.pid) or not is_case_worker_process(case.pid, case.case_id):
                case.status = "queued"
                case.pid = 0
                case.last_error = "supervisor restarted; previous worker process is gone or pid was reused"
                continue
            self.processes[case.case_id] = AttachedProcess(case.pid)
            self.process_started_monotonic[case.case_id] = time.monotonic()
            case.last_heartbeat_utc = utc_now()
            self.record_event("case_worker_reattached", case_id=case.case_id, pid=case.pid, segment=case.next_segment)

    def record_event(self, event: str, **fields: Any) -> None:
        append_jsonl(self.events_path, {"timestamp_utc": utc_now(), "event": event, **fields})

    def record_bottleneck(self, event: str, case: CaseRecord, reason: str) -> None:
        refresh_case_progress(case)
        append_csv_row(
            self.bottleneck_ledger_path,
            {
                "timestamp_utc": utc_now(),
                "event": event,
                "case_id": case.case_id,
                "variant": case.variant,
                "realm": case.realm,
                "party_size": case.party_size,
                "segment": case.next_segment,
                "attempt": case.attempt,
                "status_after": case.status,
                "reason": reason,
                "max_level": case.max_observed_level,
                "min_level": case.min_observed_level,
                "recent_segment_span": case.recent_segment_span,
                "recent_xp": case.recent_xp,
                "recent_target_removed": case.recent_target_removed,
                "recent_deaths": case.recent_deaths,
                "kills": case.kills,
                "target_removed": case.target_removed,
                "deaths": case.deaths,
                "xp": case.xp,
                "money": case.money,
                "stdout_log": case.stdout_log,
                "stderr_log": case.stderr_log,
                "reproduction_command": latest_failure_repro(case),
            },
            BOTTLENECK_LEDGER_FIELDS,
        )

    def current_segment_attempt_count(self, case: CaseRecord) -> int:
        count = 0
        if self.events_path.exists():
            try:
                with self.events_path.open("r", encoding="utf-8") as handle:
                    for line in handle:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            event = json.loads(stripped)
                        except json.JSONDecodeError:
                            continue
                        if (
                            event.get("event") == "case_started"
                            and event.get("case_id") == case.case_id
                            and as_int(event.get("segment")) == int(case.next_segment or 0)
                        ):
                            count += 1
            except OSError:
                count = 0
        if count <= 0 and int(case.attempt or 0) > 0:
            return 1
        return count

    def queue_bottleneck_retry(self, event: str, case: CaseRecord, reason: str) -> bool:
        if not bool(getattr(self.args, "continue_after_bottleneck", False)):
            return False
        max_attempts = int(getattr(self.args, "bottleneck_auto_resume_attempts", 0) or 0)
        segment_attempts = self.current_segment_attempt_count(case)
        if max_attempts <= 0 or segment_attempts >= max_attempts:
            return False
        case.status = "queued"
        case.last_error = reason
        case.last_event = f"{event} recorded; retrying segment {case.next_segment}"
        append_jsonl(
            self.interventions_path,
            {
                "timestamp_utc": utc_now(),
                "event": "bottleneck_retry_queued",
                "source_event": event,
                "case_id": case.case_id,
                "segment": case.next_segment,
                "completed_attempt": case.attempt,
                "next_attempt": case.attempt + 1,
                "completed_segment_attempt": segment_attempts,
                "next_segment_attempt": segment_attempts + 1,
                "max_attempts": max_attempts,
                "action": "retry_same_segment_with_next_route_case_index",
                "reason": reason,
                "reproduction_command": latest_failure_repro(case),
            },
        )
        self.record_event(
            "case_bottleneck_retry_queued",
            case_id=case.case_id,
            source_event=event,
            segment=case.next_segment,
            completed_attempt=case.attempt,
            next_attempt=case.attempt + 1,
            completed_segment_attempt=segment_attempts,
            next_segment_attempt=segment_attempts + 1,
            max_attempts=max_attempts,
            reason=reason,
        )
        return True

    def cleanup_case_processes(self, case: CaseRecord, *, force: bool, reason: str) -> None:
        killed = self.stale_process_cleaner(self.args, case, force=force)
        if killed:
            self.record_event(
                "case_stale_wsl_processes_killed",
                case_id=case.case_id,
                reason=reason,
                force=force,
                pids=killed,
            )

    def write_manifest(self) -> None:
        rows = []
        for case_id in self.case_order:
            case = self.cases[case_id]
            rows.append(
                {
                    "case_id": case.case_id,
                    "variant": case.variant,
                    "realm": case.realm,
                    "party_size": case.party_size,
                    "repeat_index": case.repeat_index,
                    "case_index": case.case_index,
                    "start": case.start,
                    "segment_seconds": case.segment_seconds,
                    "max_segments": case.max_segments,
                    "max_level": case.max_level,
                    "run_dir": case.run_dir,
                    "case_data_dir": case.case_data_dir,
                    "extra_args": " ".join(case.extra_args),
                }
            )
        write_csv_rows(
            self.manifest_path,
            rows,
            [
                "case_id",
                "variant",
                "realm",
                "party_size",
                "repeat_index",
                "case_index",
                "start",
                "segment_seconds",
                "max_segments",
                "max_level",
                "run_dir",
                "case_data_dir",
                "extra_args",
            ],
        )

    def write_status_files(self) -> None:
        status_rows: list[dict[str, Any]] = []
        for case_id in self.case_order:
            case = self.cases[case_id]
            refresh_case_progress(case)
            status_rows.append(
                {
                    "case_id": case.case_id,
                    "variant": case.variant,
                    "realm": case.realm,
                    "party_size": case.party_size,
                    "status": case.status,
                    "pid": case.pid,
                    "next_segment": case.next_segment,
                    "last_passed_segment": case.last_passed_segment,
                    "attempt": case.attempt,
                    "max_level": case.max_observed_level,
                    "min_level": case.min_observed_level,
                    "kills": case.kills,
                    "target_removed": case.target_removed,
                    "last_segment": case.last_segment,
                    "last_segment_xp": case.last_segment_xp,
                    "last_segment_target_removed": case.last_segment_target_removed,
                    "last_segment_deaths": case.last_segment_deaths,
                    "recent_segment_span": case.recent_segment_span,
                    "recent_xp": case.recent_xp,
                    "recent_target_removed": case.recent_target_removed,
                    "recent_deaths": case.recent_deaths,
                    "zero_xp_members": case.zero_xp_members,
                    "lowest_members": case.lowest_members,
                    "deaths": case.deaths,
                    "xp": case.xp,
                    "money": case.money,
                    "last_event": case.last_event,
                    "last_error": case.last_error,
                    "last_heartbeat_utc": case.last_heartbeat_utc,
                    "stdout_log": case.stdout_log,
                    "stderr_log": case.stderr_log,
                    "reproduction_command": latest_failure_repro(case),
                }
            )
        write_csv_rows(
            self.status_path,
            status_rows,
            [
                "case_id",
                "variant",
                "realm",
                "party_size",
                "status",
                "pid",
                "next_segment",
                "last_passed_segment",
                "attempt",
                "max_level",
                "min_level",
                "kills",
                "target_removed",
                "last_segment",
                "last_segment_xp",
                "last_segment_target_removed",
                "last_segment_deaths",
                "recent_segment_span",
                "recent_xp",
                "recent_target_removed",
                "recent_deaths",
                "zero_xp_members",
                "lowest_members",
                "deaths",
                "xp",
                "money",
                "last_event",
                "last_error",
                "last_heartbeat_utc",
                "stdout_log",
                "stderr_log",
                "reproduction_command",
            ],
        )
        state = {
            "timestamp_utc": utc_now(),
            "max_concurrent_cases": self.max_concurrent_cases,
            "max_concurrent_per_realm": self.args.max_concurrent_per_realm,
            "command_offset": self.command_offset,
            "cases": [asdict(self.cases[case_id]) for case_id in self.case_order],
        }
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        replace_path_with_retry(tmp, self.state_path)
        self.write_aggregate_timeline()

    def write_aggregate_timeline(self) -> None:
        rows: list[dict[str, Any]] = []
        fields: list[str] = ["supervisor_case_id", "variant"]
        known = set(fields)
        for case_id in self.case_order:
            case = self.cases[case_id]
            for row in read_csv_rows(Path(case.run_dir) / "timeline.csv"):
                aggregate_row: dict[str, Any] = {"supervisor_case_id": case.case_id, "variant": case.variant, **row}
                rows.append(aggregate_row)
                for key in aggregate_row:
                    if key not in known:
                        known.add(key)
                        fields.append(key)
        write_csv_rows(self.aggregate_timeline_path, rows, fields)

    def read_new_commands(self) -> list[dict[str, Any]]:
        if not self.commands_path.exists():
            return []
        commands: list[dict[str, Any]] = []
        with self.commands_path.open("r", encoding="utf-8") as handle:
            handle.seek(self.command_offset)
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    commands.append(json.loads(stripped))
                except json.JSONDecodeError as exc:
                    self.record_event("command_decode_failed", error=str(exc), line=stripped[:200])
            self.command_offset = handle.tell()
        self.command_offset_path.write_text(str(self.command_offset), encoding="utf-8")
        return commands

    def process_commands(self) -> None:
        handled = False
        for command in self.read_new_commands():
            self.handle_command(command)
            handled = True
        if handled:
            self.write_status_files()

    def handle_command(self, command: dict[str, Any]) -> None:
        name = str(command.get("command") or command.get("type") or "")
        case_id = str(command.get("case_id") or "")
        reason = str(command.get("reason") or "manual command")
        if name == "set_concurrency":
            value = as_int(command.get("max_concurrent_cases") or command.get("value"))
            if value < 0:
                self.record_event("command_rejected", command=name, reason="max_concurrent_cases cannot be negative")
                return
            self.max_concurrent_cases = value
            self.record_event("concurrency_changed", max_concurrent_cases=value)
            return
        if name == "set_worker_timeout_grace":
            value = float(command.get("worker_timeout_grace_seconds") or command.get("seconds") or command.get("value") or 0)
            if value < 0:
                self.record_event("command_rejected", command=name, reason="worker_timeout_grace_seconds must be non-negative")
                return
            self.args.worker_timeout_grace_seconds = value
            self.record_event("worker_timeout_grace_changed", worker_timeout_grace_seconds=value)
            return
        if name == "set_completed_stall_fatal_segments":
            value = as_int(command.get("completed_stall_fatal_segments") or command.get("segments") or command.get("value"))
            if value <= 0:
                self.record_event("command_rejected", command=name, reason="completed_stall_fatal_segments must be at least 1")
                return
            self.args.completed_stall_fatal_segments = value
            self.record_event("completed_stall_fatal_segments_changed", completed_stall_fatal_segments=value)
            return
        if name == "set_bottleneck_auto_resume_attempts":
            value = as_int(command.get("bottleneck_auto_resume_attempts") or command.get("attempts") or command.get("value"))
            if value < 0:
                self.record_event("command_rejected", command=name, reason="bottleneck_auto_resume_attempts cannot be negative")
                return
            self.args.bottleneck_auto_resume_attempts = value
            self.record_event("bottleneck_auto_resume_attempts_changed", bottleneck_auto_resume_attempts=value)
            return
        if name == "resume_all_quarantined":
            resumed = 0
            for case in self.cases.values():
                if case.status == "quarantined":
                    case.status = "queued"
                    case.last_error = ""
                    case.updated_at_utc = utc_now()
                    resumed += 1
            self.record_event("all_quarantined_resumed", count=resumed)
            return
        if case_id not in self.cases:
            self.record_event("command_rejected", command=name, case_id=case_id, reason="unknown case")
            return
        case = self.cases[case_id]
        if name == "stop_case":
            self.stop_case(case, force=False, status="paused", reason=reason)
        elif name == "kill_case":
            self.stop_case(case, force=True, status="paused", reason=reason)
        elif name == "quarantine_case":
            self.stop_case(case, force=False, status="quarantined", reason=reason)
        elif name == "resume_case":
            if case.status in RESUMABLE_STATES or is_completed_before_target_level(case):
                if is_completed_before_target_level(case):
                    case.next_segment = max(case.next_segment, case.last_passed_segment + 1)
                case.status = "queued"
                case.last_error = ""
                case.exit_code = None
                case.updated_at_utc = utc_now()
                self.record_event("case_resumed", case_id=case.case_id)
            else:
                self.record_event("command_ignored", command=name, case_id=case.case_id, status=case.status)
        else:
            self.record_event("command_rejected", command=name, case_id=case_id, reason="unknown command")

    def stop_case(self, case: CaseRecord, *, force: bool, status: str, reason: str) -> None:
        process = self.processes.pop(case.case_id, None)
        self.process_started_monotonic.pop(case.case_id, None)
        if process is not None:
            terminate_process(process, force=force)
        self.cleanup_case_processes(case, force=force, reason="stop_case")
        case.status = status
        case.pid = 0
        case.last_error = reason
        case.last_heartbeat_utc = utc_now()
        case.updated_at_utc = utc_now()
        self.record_event("case_stopped", case_id=case.case_id, status=status, force=force, reason=reason)

    def running_count_for_realm(self, realm: str) -> int:
        return sum(1 for case in self.cases.values() if case.status == "running" and case.realm == realm)

    def can_start_case(self, case: CaseRecord) -> bool:
        if case.status != "queued":
            return False
        if len(self.processes) >= self.max_concurrent_cases:
            return False
        per_realm = self.args.max_concurrent_per_realm
        if per_realm > 0 and self.running_count_for_realm(case.realm) >= per_realm:
            return False
        return True

    def queued_cases_by_start_priority(self) -> list[CaseRecord]:
        queued = (self.cases[case_id] for case_id in self.case_order)
        return sorted(
            (case for case in queued if case.status == "queued"),
            key=lambda case: (
                case.next_segment,
                case.last_passed_segment,
                case.repeat_index,
                case.party_size,
                REALM_ORDER.get(case.realm, len(REALM_ORDER)),
                case.case_index,
            ),
        )

    def start_ready_cases(self) -> None:
        for case in self.queued_cases_by_start_priority():
            if not self.can_start_case(case):
                continue
            self.launch_case(case)

    def worker_command(self, case: CaseRecord) -> list[str]:
        if self.args.fake_worker:
            exit_code = self.fake_exit_code(case)
            return [
                sys.executable,
                str(Path(__file__).resolve()),
                "--_fake-worker",
                "--case-id",
                case.case_id,
                "--realm",
                case.realm,
                "--party-size",
                str(case.party_size),
                "--run-dir",
                case.run_dir,
                "--segment",
                str(case.next_segment),
                "--exit-code",
                str(exit_code),
                "--sleep",
                str(self.args.fake_worker_sleep),
            ]
        command = [
            self.args.wsl_exe,
            "--cd",
            self.args.wsl_work_dir,
            "--exec",
            self.args.python_exe,
            "tools/run-dummy-growth-suite.py",
            "--mysql-bin",
            self.args.mysql_bin,
            "--growth-stage",
            "custom",
            "--growth-speed-profile",
            "fast-balance",
            "--segment-seconds",
            str(case.segment_seconds),
            "--max-segments",
            "1",
            "--max-level",
            str(case.max_level),
            "--reset-level",
            str(case.reset_level),
            "--realms",
            case.realm,
            "--party-sizes",
            str(case.party_size),
            "--case-repeats",
            "1",
            "--parallel-cases",
            "1",
            "--start",
            str(case.start),
            "--start-stride",
            str(self.args.case_start_stride),
            "--host",
            self.args.host_address,
            "--nav-api-url",
            self.args.nav_api_url,
            "--api-port",
            str(self.args.api_port),
            "--run-dir",
            case.run_dir_arg,
            "--case-name",
            case.case_id,
            "--first-segment",
            str(case.next_segment),
            "--growth-route-case-index",
            str(route_case_index_for_attempt(case)),
        ]
        if self.args.growth_fast_travel == "route-home":
            command.extend(["--no-fail-on-regression", "--no-require-segment-kill", "--no-require-segment-xp"])
        else:
            command.extend(["--fail-on-regression", "--require-segment-kill", "--require-segment-xp"])
        if self.args.growth_hunting_index:
            command.extend(["--growth-hunting-index", self.args.growth_hunting_index])
        if self.args.growth_fast_travel != "off":
            command.extend(["--growth-fast-travel", self.args.growth_fast_travel])
        if self.args.growth_fast_travel == "route-home" and self.args.growth_hunting_index:
            command.extend(["--growth-route-preflight", "--growth-route-preflight-anchor"])
        command.extend(
            [
                "--growth-allow-lower-xp-gear-farm",
                "--no-growth-equip-party-carry-gear",
                "--no-level50-party-gear",
                "--growth-party-carry-level-offset",
                str(getattr(self.args, "growth_party_carry_level_offset", 12)),
                "--growth-party-carry-count",
                str(getattr(self.args, "growth_party_carry_count", -1)),
            ]
        )
        accounts_csv = Path(case.case_data_dir) / "accounts.csv"
        if self.args.skip_provision or case.next_segment > 1 or accounts_csv.exists():
            command.append("--skip-provision")
        if not self.args.reset_progress or case.next_segment > 1 or accounts_csv.exists():
            command.append("--no-reset-progress")
        if self.args.dry_run:
            command.append("--dry-run")
        command.extend(case.extra_args)
        command.extend(self.args.worker_extra_args)
        return command

    def fake_exit_code(self, case: CaseRecord) -> int:
        fail_cases = set(parse_csv_list(self.args.fake_fail_cases))
        fail_segments = parse_int_csv(self.args.fake_fail_segments)
        if case.case_id in fail_cases and case.next_segment in fail_segments:
            return self.args.fake_fail_exit_code
        return 0

    def archive_failed_segment_artifacts(self, case: CaseRecord) -> None:
        if case.attempt <= 0:
            return
        segment = case.next_segment
        data_dir = Path(case.case_data_dir)
        candidates = []
        if data_dir.exists():
            candidates = [
                path
                for path in data_dir.rglob("*")
                if path.is_file() and path.name.startswith(f"segment-{segment:03d}")
            ]
            repro = data_dir / "failure-reproduction-command.txt"
            if repro.exists():
                candidates.append(repro)
        failed_timeline_rows: list[dict[str, str]] = []
        kept_timeline_rows: list[dict[str, str]] = []
        timeline_fields: list[str] = []
        timeline_path = Path(case.run_dir) / "timeline.csv"
        if timeline_path.exists() and timeline_path.stat().st_size > 0:
            with timeline_path.open("r", encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                timeline_fields = list(reader.fieldnames or [])
                for row in reader:
                    if row.get("case") == case.case_id and as_int(row.get("segment")) == segment:
                        failed_timeline_rows.append(row)
                    else:
                        kept_timeline_rows.append(row)
        if not candidates and not failed_timeline_rows:
            return
        target_root = self.failed_attempts_dir / case.case_id / f"segment-{segment:03d}-attempt-{case.attempt:03d}"
        for path in candidates:
            try:
                relative = path.relative_to(data_dir)
            except ValueError:
                relative = Path(path.name)
            target = target_root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
        if failed_timeline_rows:
            write_csv_rows(target_root / "timeline.csv", failed_timeline_rows, timeline_fields)
            write_csv_rows(timeline_path, kept_timeline_rows, timeline_fields)
        self.record_event("failed_artifacts_archived", case_id=case.case_id, segment=segment, attempt=case.attempt, path=str(target_root))

    def launch_case(self, case: CaseRecord) -> None:
        self.cleanup_case_processes(case, force=True, reason="before_launch")
        self.archive_failed_segment_artifacts(case)
        case.attempt += 1
        command = self.worker_command(case)
        stdout_log = self.logs_dir / f"{case.case_id}-segment-{case.next_segment:03d}-attempt-{case.attempt:03d}.stdout.log"
        stderr_log = self.logs_dir / f"{case.case_id}-segment-{case.next_segment:03d}-attempt-{case.attempt:03d}.stderr.log"
        stdout_log.parent.mkdir(parents=True, exist_ok=True)
        stderr_log.parent.mkdir(parents=True, exist_ok=True)
        stdout = stdout_log.open("w", encoding="utf-8", errors="replace")
        stderr = stderr_log.open("w", encoding="utf-8", errors="replace")
        try:
            process = self.process_factory(command, stdout=stdout, stderr=stderr, cwd=str(Path.cwd()))
        finally:
            stdout.close()
            stderr.close()
        self.processes[case.case_id] = process
        self.process_started_monotonic[case.case_id] = time.monotonic()
        case.status = "running"
        case.pid = int(getattr(process, "pid", 0) or 0)
        case.exit_code = None
        case.last_error = ""
        case.started_at_utc = utc_now()
        case.updated_at_utc = case.started_at_utc
        case.last_heartbeat_utc = case.started_at_utc
        case.stdout_log = str(stdout_log)
        case.stderr_log = str(stderr_log)
        case.last_event = f"segment {case.next_segment} attempt {case.attempt} started"
        self.record_event(
            "case_started",
            case_id=case.case_id,
            segment=case.next_segment,
            attempt=case.attempt,
            pid=case.pid,
            command=command,
        )

    def reap_finished(self) -> None:
        now = utc_now()
        for case_id, process in list(self.processes.items()):
            case = self.cases[case_id]
            rc = process.poll()
            if rc is None:
                started_monotonic = self.process_started_monotonic.get(case_id)
                elapsed_seconds = 0.0
                if started_monotonic is not None:
                    elapsed_seconds = max(0.0, time.monotonic() - started_monotonic)
                startup_fatal_reason = worker_startup_no_output_fatal_reason(self.args, case, elapsed_seconds)
                if startup_fatal_reason:
                    terminate_process(process, force=True)
                    self.cleanup_case_processes(case, force=True, reason="startup_no_output")
                    self.processes.pop(case_id, None)
                    self.process_started_monotonic.pop(case_id, None)
                    case.pid = 0
                    case.exit_code = -9
                    case.status = "quarantined"
                    case.last_error = startup_fatal_reason
                    case.last_event = f"startup-no-output quarantined at segment {case.next_segment}"
                    case.updated_at_utc = now
                    case.last_heartbeat_utc = now
                    refresh_case_progress(case)
                    retry_queued = self.queue_bottleneck_retry("case_worker_startup_no_output", case, startup_fatal_reason)
                    self.record_bottleneck("case_worker_startup_no_output", case, startup_fatal_reason)
                    self.record_event(
                        "case_worker_startup_no_output",
                        case_id=case.case_id,
                        segment=case.next_segment,
                        attempt=case.attempt,
                        elapsed_seconds=round(elapsed_seconds, 3),
                        retry_queued=retry_queued,
                        stderr_log=case.stderr_log,
                        reproduction_command=latest_failure_repro(case),
                    )
                    continue
                live_fatal_reason = case_live_fatal_reason(self.args, case)
                if live_fatal_reason:
                    runtime_failure_memory_rows = record_live_fatal_runtime_failure_memory(case, live_fatal_reason)
                    terminate_process(process, force=True)
                    self.cleanup_case_processes(case, force=True, reason="live_fatal")
                    self.processes.pop(case_id, None)
                    self.process_started_monotonic.pop(case_id, None)
                    case.pid = 0
                    case.exit_code = -9
                    case.status = "quarantined"
                    case.last_error = live_fatal_reason
                    case.last_event = f"live-fatal quarantined at segment {case.next_segment}"
                    case.updated_at_utc = now
                    case.last_heartbeat_utc = now
                    refresh_case_progress(case)
                    retry_queued = self.queue_bottleneck_retry("case_live_fatal", case, live_fatal_reason)
                    self.record_bottleneck("case_live_fatal", case, live_fatal_reason)
                    self.record_event(
                        "case_live_fatal",
                        case_id=case.case_id,
                        segment=case.next_segment,
                        attempt=case.attempt,
                        reason=live_fatal_reason,
                        retry_queued=retry_queued,
                        runtime_failure_memory_rows=runtime_failure_memory_rows,
                        stderr_log=case.stderr_log,
                        reproduction_command=latest_failure_repro(case),
                    )
                    continue
                timeout_seconds = worker_timeout_seconds(self.args, case)
                if (
                    timeout_seconds > 0.0
                    and started_monotonic is not None
                    and elapsed_seconds > timeout_seconds
                ):
                    terminate_process(process, force=True)
                    self.cleanup_case_processes(case, force=True, reason="worker_timeout")
                    self.processes.pop(case_id, None)
                    self.process_started_monotonic.pop(case_id, None)
                    case.pid = 0
                    case.exit_code = -9
                    case.status = "quarantined"
                    case.last_error = f"worker timeout after {timeout_seconds:.0f}s"
                    case.last_event = f"quarantined at segment {case.next_segment}"
                    case.updated_at_utc = now
                    case.last_heartbeat_utc = now
                    refresh_case_progress(case)
                    timeout_reason = f"worker timeout after {timeout_seconds:.0f}s"
                    retry_queued = self.queue_bottleneck_retry("case_worker_timeout", case, timeout_reason)
                    self.record_bottleneck("case_worker_timeout", case, timeout_reason)
                    self.record_event(
                        "case_worker_timeout",
                        case_id=case.case_id,
                        segment=case.next_segment,
                        attempt=case.attempt,
                        timeout_seconds=round(timeout_seconds, 3),
                        retry_queued=retry_queued,
                        stderr_log=case.stderr_log,
                        reproduction_command=latest_failure_repro(case),
                    )
                    continue
                case.last_heartbeat_utc = now
                continue
            self.processes.pop(case_id, None)
            self.process_started_monotonic.pop(case_id, None)
            self.cleanup_case_processes(case, force=True, reason="worker_reaped")
            case.pid = 0
            case.exit_code = int(rc)
            case.updated_at_utc = now
            case.last_heartbeat_utc = now
            refresh_case_progress(case)
            if rc == 0:
                member_stuck_reason = completed_party_member_stuck_reason(self.args, case)
                if member_stuck_reason:
                    case.status = "quarantined"
                    case.last_error = member_stuck_reason
                    case.last_event = f"member-stuck quarantined at segment {case.next_segment}"
                    retry_queued = self.queue_bottleneck_retry("case_party_member_stuck", case, member_stuck_reason)
                    self.record_bottleneck("case_party_member_stuck", case, member_stuck_reason)
                    self.record_event(
                        "case_party_member_stuck",
                        case_id=case.case_id,
                        segment=case.next_segment,
                        attempt=case.attempt,
                        reason=member_stuck_reason,
                        retry_queued=retry_queued,
                        stderr_log=case.stderr_log,
                        reproduction_command=latest_failure_repro(case),
                    )
                    continue
                stall_reason = completed_segment_stall_reason(self.args, case)
                if stall_reason:
                    case.status = "quarantined"
                    case.last_error = stall_reason
                    case.last_event = f"completed-stall quarantined at segment {case.next_segment}"
                    retry_queued = self.queue_bottleneck_retry("case_completed_stall", case, stall_reason)
                    self.record_bottleneck("case_completed_stall", case, stall_reason)
                    self.record_event(
                        "case_completed_stall",
                        case_id=case.case_id,
                        segment=case.next_segment,
                        attempt=case.attempt,
                        reason=stall_reason,
                        retry_queued=retry_queued,
                        stderr_log=case.stderr_log,
                        reproduction_command=latest_failure_repro(case),
                    )
                    continue
                case.last_passed_segment = case.next_segment
                if case.max_observed_level >= case.max_level:
                    case.status = "completed"
                    case.last_event = f"completed at segment {case.last_passed_segment}"
                    self.record_event("case_completed", case_id=case.case_id, segment=case.last_passed_segment)
                else:
                    if case.last_passed_segment >= case.max_segments:
                        old_max_segments = case.max_segments
                        case.max_segments = case.last_passed_segment + 1
                        self.record_event(
                            "case_segment_budget_extended",
                            case_id=case.case_id,
                            previous_max_segments=old_max_segments,
                            next_max_segments=case.max_segments,
                            max_observed_level=case.max_observed_level,
                            target_level=case.max_level,
                        )
                    case.next_segment = case.last_passed_segment + 1
                    case.status = "queued"
                    case.last_event = f"segment {case.last_passed_segment} passed"
                    self.record_event("case_segment_passed", case_id=case.case_id, segment=case.last_passed_segment)
            else:
                case.status = "quarantined"
                case.last_error = f"worker exit code {rc}"
                case.last_event = f"quarantined at segment {case.next_segment}"
                retry_queued = self.queue_bottleneck_retry("case_quarantined", case, case.last_error)
                self.record_bottleneck("case_quarantined", case, case.last_error)
                self.record_event(
                    "case_quarantined",
                    case_id=case.case_id,
                    segment=case.next_segment,
                    attempt=case.attempt,
                    exit_code=rc,
                    retry_queued=retry_queued,
                    stderr_log=case.stderr_log,
                    reproduction_command=latest_failure_repro(case),
                )

    def counts(self) -> dict[str, int]:
        result = {"total": len(self.cases), "running": 0, "queued": 0, "paused": 0, "quarantined": 0, "completed": 0}
        for case in self.cases.values():
            result[case.status] = result.get(case.status, 0) + 1
        return result

    def has_active_work(self) -> bool:
        if self.processes:
            return True
        return any(case.status == "queued" for case in self.cases.values())

    def selected_progress_cases(self) -> list[CaseRecord]:
        cases = [self.cases[case_id] for case_id in self.case_order]
        if self.args.show_all_cases:
            return cases
        priority = {"quarantined": 0, "paused": 1, "running": 2, "queued": 3, "completed": 4}
        return sorted(cases, key=lambda case: (priority.get(case.status, 9), case.case_index))[: min(25, len(cases))]

    def print_progress(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_progress_print < self.args.progress_interval_seconds:
            return
        self.last_progress_print = now
        self.write_status_files()
        counts = self.counts()
        print(
            f"[{utc_now()}] total={counts['total']} running={counts['running']} queued={counts['queued']} "
            f"paused={counts['paused']} quarantined={counts['quarantined']} completed={counts['completed']} "
            f"max_concurrent={self.max_concurrent_cases}",
            flush=True,
        )
        for case in self.selected_progress_cases():
            print(
                f"  {case.case_id} {case.status} realm={case.realm} p{case.party_size} "
                f"seg={case.last_passed_segment}->{case.next_segment} "
                f"Lmin={case.min_observed_level} Lmax={case.max_observed_level} "
                f"last_seg={case.last_segment} removed={case.last_segment_target_removed} xp={case.last_segment_xp} "
                f"recent[{case.recent_segment_span or '-'}] removed={case.recent_target_removed} xp={case.recent_xp} "
                f"total_removed={case.target_removed} rewarded={case.kills} zero_xp={case.zero_xp_members} "
                f"deaths={case.deaths} money={case.money} "
                f"last={case.last_event or '-'}",
                flush=True,
            )
            if case.status == "quarantined":
                repro = latest_failure_repro(case)
                print(f"    error={case.last_error or '-'} repro={repro or '-'}", flush=True)

    def run(self) -> int:
        self.prepare()
        try:
            while True:
                self.process_commands()
                self.reap_finished()
                self.start_ready_cases()
                self.print_progress()
                if self.shutdown_requested:
                    return 1
                if not self.has_active_work():
                    self.write_status_files()
                    self.print_progress(force=True)
                    if self.args.keep_alive:
                        time.sleep(self.args.scheduler_interval_seconds)
                        continue
                    break
                time.sleep(self.args.scheduler_interval_seconds)
        except Exception as exc:
            self.record_event("supervisor_crashed", error=repr(exc))
            raise
        finally:
            self.write_status_files()
        if any(case.status == "quarantined" for case in self.cases.values()):
            return 1
        return 0


def terminate_process(process: Any, *, force: bool) -> None:
    pid = int(getattr(process, "pid", 0) or 0)
    if os.name == "nt" and pid:
        command = ["taskkill", "/PID", str(pid), "/T"]
        if force:
            command.append("/F")
        subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        return
    try:
        if force:
            process.kill()
        else:
            process.terminate()
    except Exception:
        pass


def load_cases_from_state(args: argparse.Namespace) -> list[CaseRecord]:
    state_path = args.base_run_dir_path / "case-state.json"
    if not args.resume_supervisor or not state_path.exists():
        return build_case_manifest(args)
    data = json.loads(state_path.read_text(encoding="utf-8"))
    cases: list[CaseRecord] = []
    for row in data.get("cases", []):
        row = dict(row)
        if row.get("status") == "running":
            pid = as_int(row.get("pid"))
            if pid > 0 and process_exists(pid):
                row["pid"] = pid
                row["last_error"] = "supervisor restarted; worker process reattached"
            else:
                row["status"] = "queued"
                row["pid"] = 0
                row["last_error"] = "supervisor restarted; previous worker process is gone"
        cases.append(CaseRecord(**row))
    return cases


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-run-dir", default="")
    parser.add_argument("--case-specs", default="", help="comma-separated exact cases as variant:realm[:repeats]")
    parser.add_argument("--realms", default="alb,mid,hib")
    parser.add_argument("--variants", default="solo-s150-r2,duo-s150,party4-s180,party8-s240")
    parser.add_argument("--solo-repeats", type=int, default=2)
    parser.add_argument("--duo-repeats", type=int, default=1)
    parser.add_argument("--party4-repeats", type=int, default=1)
    parser.add_argument("--party8-repeats", type=int, default=1)
    parser.add_argument("--case-repeats", type=int, default=0, help="override repeat count for every selected variant")
    parser.add_argument("--max-concurrent-cases", type=int, default=6)
    parser.add_argument("--max-concurrent-per-realm", type=int, default=0, help="0 disables realm-level concurrency limiting")
    parser.add_argument("--max-segments", type=int, default=5)
    parser.add_argument("--max-level", type=int, default=50)
    parser.add_argument("--reset-level", type=int, default=1)
    parser.add_argument(
        "--growth-party-carry-level-offset",
        type=int,
        default=12,
        help="party carry character level offset passed to each growth worker",
    )
    parser.add_argument(
        "--growth-party-carry-count",
        type=int,
        default=-1,
        help="party carry characters per worker case; -1 keeps N-1 carry mode, 0 makes every party member a tracked growth target",
    )
    parser.add_argument("--start-base", type=int, default=42001)
    parser.add_argument("--case-start-stride", type=int, default=40)
    parser.add_argument("--host", dest="host_address", default="192.168.0.42")
    parser.add_argument("--nav-api-url", default="http://192.168.0.42:5000")
    parser.add_argument("--api-port", type=int, default=5000)
    parser.add_argument("--mysql-bin", default="/mnt/c/Program Files/MariaDB 12.3/bin/mariadb.exe")
    parser.add_argument("--growth-hunting-index", default="")
    parser.add_argument("--growth-fast-travel", choices=["off", "route-home", "teleport"], default="off")
    parser.add_argument("--wsl-exe", default=r"C:\Windows\System32\wsl.exe")
    parser.add_argument("--wsl-work-dir", default="")
    parser.add_argument("--python-exe", default="python3")
    parser.add_argument("--progress-interval-seconds", type=float, default=30.0)
    parser.add_argument("--scheduler-interval-seconds", type=float, default=2.0)
    parser.add_argument(
        "--worker-timeout-grace-seconds",
        type=float,
        default=300.0,
        help="quarantine a segment worker after segment_seconds plus this grace; 0 disables",
    )
    parser.add_argument(
        "--worker-startup-no-output-fatal-seconds",
        type=float,
        default=120.0,
        help="quarantine a worker that creates no stdout/stderr or segment artifacts after this many seconds; 0 disables",
    )
    parser.add_argument("--live-scan-empty-fatal-count", type=int, default=3)
    parser.add_argument("--live-scan-empty-no-visible-fatal-count", type=int, default=5)
    parser.add_argument("--live-nav-path-failed-fatal-count", type=int, default=3)
    parser.add_argument(
        "--live-route-home-failed-fatal-count",
        type=int,
        default=5,
        help="quarantine a running case after repeated failed route-home player-move attempts; 0 disables",
    )
    parser.add_argument("--live-target-removed-no-combat-fatal-count", type=int, default=12)
    parser.add_argument("--live-idle-no-engagement-fatal-ticks", type=int, default=10)
    parser.add_argument("--live-idle-no-engagement-fatal-seconds", type=float, default=30.0)
    parser.add_argument("--live-required-home-oscillation-fatal-count", type=int, default=10)
    parser.add_argument("--live-death-loop-fatal-count", type=int, default=3)
    parser.add_argument("--live-solo-death-no-progress-fatal-count", type=int, default=3)
    parser.add_argument("--live-solo-death-no-progress-fatal-seconds", type=float, default=55.0)
    parser.add_argument(
        "--completed-stall-fatal-segments",
        type=int,
        default=2,
        help="quarantine a case after this many completed segments with no aggregate xp or level gain; 0 disables",
    )
    parser.add_argument(
        "--continue-after-bottleneck",
        action="store_true",
        help="record a bottleneck and retry the same segment with the next route-case-index instead of stopping immediately",
    )
    parser.add_argument(
        "--bottleneck-auto-resume-attempts",
        type=int,
        default=0,
        help="maximum attempts per segment when --continue-after-bottleneck is enabled; 0 disables automatic bottleneck retries",
    )
    parser.add_argument(
        "--party-member-stuck-fatal-segments",
        type=int,
        default=10,
        help="quarantine party cases when a member remains level 1 with zero XP after this many completed segments; 0 disables",
    )
    parser.add_argument("--show-all-cases", action="store_true")
    parser.add_argument("--keep-alive", action="store_true")
    parser.add_argument("--resume-supervisor", action="store_true")
    parser.add_argument("--skip-provision", action="store_true")
    parser.add_argument("--no-reset-progress", dest="reset_progress", action="store_false", default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--worker-extra-args", nargs=argparse.REMAINDER, default=[])
    parser.add_argument("--fake-worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--fake-worker-sleep", type=float, default=0.05, help=argparse.SUPPRESS)
    parser.add_argument("--fake-fail-cases", default="", help=argparse.SUPPRESS)
    parser.add_argument("--fake-fail-segments", default="1", help=argparse.SUPPRESS)
    parser.add_argument("--fake-fail-exit-code", type=int, default=7, help=argparse.SUPPRESS)
    parser.add_argument("--_fake-worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.growth_fast_travel == "teleport":
        args.growth_fast_travel = "route-home"
    if args.max_concurrent_cases < 0:
        raise SystemExit("--max-concurrent-cases cannot be negative")
    if args.max_concurrent_per_realm < 0:
        raise SystemExit("--max-concurrent-per-realm cannot be negative")
    if args.max_segments < 1:
        raise SystemExit("--max-segments must be positive")
    if args.max_level < 1:
        raise SystemExit("--max-level must be positive")
    if args.reset_level < 1:
        raise SystemExit("--reset-level must be positive")
    if args.growth_party_carry_level_offset < 0:
        raise SystemExit("--growth-party-carry-level-offset cannot be negative")
    if args.growth_party_carry_count < -1:
        raise SystemExit("--growth-party-carry-count cannot be less than -1")
    if args.case_start_stride < 1:
        raise SystemExit("--case-start-stride must be positive")
    if args.completed_stall_fatal_segments < 0:
        raise SystemExit("--completed-stall-fatal-segments cannot be negative")
    if args.bottleneck_auto_resume_attempts < 0:
        raise SystemExit("--bottleneck-auto-resume-attempts cannot be negative")
    if args.live_route_home_failed_fatal_count < 0:
        raise SystemExit("--live-route-home-failed-fatal-count cannot be negative")
    if args.party_member_stuck_fatal_segments < 0:
        raise SystemExit("--party-member-stuck-fatal-segments cannot be negative")
    args.base_run_dir_path = local_base_run_dir(args.base_run_dir)
    args.base_run_dir_wsl = windows_path_to_wsl(args.base_run_dir_path)
    if not args.wsl_work_dir:
        args.wsl_work_dir = windows_path_to_wsl(Path.cwd())
    maybe_resolve_worker_wsl_host(args)
    args.worker_extra_args = list(args.worker_extra_args or [])
    return args


def fake_worker_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--_fake-worker", action="store_true")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--realm", required=True)
    parser.add_argument("--party-size", type=int, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--segment", type=int, required=True)
    parser.add_argument("--exit-code", type=int, required=True)
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args(argv)
    time.sleep(args.sleep)
    run_dir = args.run_dir
    case_dir = run_dir / args.case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    if args.exit_code == 0:
        metrics_path = case_dir / f"segment-{args.segment:03d}-metrics.csv"
        write_csv_rows(
            metrics_path,
            [{"target_removed": "1", "player_deaths": "0", "elapsed_seconds": "1"}],
            ["target_removed", "player_deaths", "elapsed_seconds"],
        )
        timeline_path = run_dir / "timeline.csv"
        rows = read_csv_rows(timeline_path)
        rows.append(
            {
                "timestamp_utc": utc_now(),
                "case": args.case_id,
                "realm": args.realm,
                "party_size": args.party_size,
                "segment": args.segment,
                "account": f"fake-{args.case_id}",
                "level_after": min(50, args.segment + 1),
                "xp_delta": "10",
                "xp_effective_delta": "10",
                "money_delta_copper": "3",
                "death_delta": "0",
                "target_removed": "1",
            }
        )
        write_csv_rows(
            timeline_path,
            rows,
            [
                "timestamp_utc",
                "case",
                "realm",
                "party_size",
                "segment",
                "account",
                "level_after",
                "xp_delta",
                "xp_effective_delta",
                "money_delta_copper",
                "death_delta",
                "target_removed",
            ],
        )
    else:
        (case_dir / "failure-reproduction-command.txt").write_text(
            f"fake-worker --case-id {args.case_id} --segment {args.segment}\n",
            encoding="utf-8",
        )
    return args.exit_code


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(argv) if argv is not None else sys.argv[1:]
    if "--_fake-worker" in raw_argv:
        return fake_worker_main(raw_argv)
    args = parse_args(raw_argv)
    acquire_run_lock(args.base_run_dir_path)
    cases = load_cases_from_state(args)
    supervisor = CaseSupervisor(args, cases)
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())
