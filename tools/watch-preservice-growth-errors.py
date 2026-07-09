#!/usr/bin/env python3
"""Watch a case-supervisor run directory for dummy growth errors.

The monitor is intentionally file based so it can run beside a visible
PowerShell console and still leave machine-readable breadcrumbs for triage.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any


ERROR_EVENTS = {
    "case_quarantined",
    "case_worker_startup_no_output",
    "case_worker_timeout",
    "command_decode_failed",
    "command_rejected",
}

MAX_TAIL_LINE_CHARS = 900


def utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def truncate_text(value: Any, max_chars: int = MAX_TAIL_LINE_CHARS) -> str:
    text = str(value)
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}... [truncated {len(text) - max_chars} chars]"


def safe_print(line: Any = "") -> None:
    try:
        print(truncate_text(line, max_chars=2000), flush=True)
    except Exception:
        # The monitor must keep running even if a console pipe rejects output.
        pass


def read_offset(offset_path: Path, events_path: Path, replay: bool) -> int:
    if replay:
        return 0
    try:
        return int(offset_path.read_text(encoding="utf-8").strip() or "0")
    except (OSError, ValueError):
        try:
            return events_path.stat().st_size
        except OSError:
            return 0


def write_offset(offset_path: Path, offset: int) -> None:
    offset_path.parent.mkdir(parents=True, exist_ok=True)
    offset_path.write_text(f"{offset}\n", encoding="utf-8")


def read_new_events(events_path: Path, offset: int) -> tuple[list[dict[str, Any]], int]:
    if not events_path.exists():
        return [], offset
    size = events_path.stat().st_size
    if offset > size:
        offset = 0
    events: list[dict[str, Any]] = []
    with events_path.open("rb") as handle:
        handle.seek(offset)
        for line in handle:
            line = line.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                payload = {"event": "malformed_event_line", "raw": line}
            events.append(payload)
        return events, handle.tell()


def load_status_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return {row.get("case_id", ""): row for row in csv.DictReader(handle) if row.get("case_id")}
    except (OSError, csv.Error):
        return {}


def tail_text(path_value: str, line_count: int) -> list[str]:
    if not path_value:
        return []
    path = Path(path_value)
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return [truncate_text(line) for line in lines[-line_count:]]


def compact_status(status: dict[str, str]) -> dict[str, Any]:
    fields = [
        "case_id",
        "realm",
        "party_size",
        "status",
        "current_segment",
        "last_completed_segment",
        "attempt",
        "pid",
        "last_heartbeat_utc",
        "last_error",
        "max_level",
        "kills",
        "deaths",
        "xp",
        "money",
        "last_event",
        "stdout_log",
        "stderr_log",
        "reproduction_command",
    ]
    return {field: status.get(field, "") for field in fields}


def build_alert(
    base_run_dir: Path,
    event: dict[str, Any],
    status_rows: dict[str, dict[str, str]],
    tail_lines: int,
) -> dict[str, Any]:
    case_id = str(event.get("case_id") or event.get("case") or "")
    status = status_rows.get(case_id, {})
    stdout_log = status.get("stdout_log", "")
    stderr_log = status.get("stderr_log", "")
    alert = {
        "detected_utc": utc_timestamp(),
        "base_run_dir": str(base_run_dir),
        "event": event.get("event", ""),
        "case_id": case_id,
        "segment": event.get("segment", status.get("current_segment", "")),
        "attempt": event.get("attempt", status.get("attempt", "")),
        "reason": event.get("reason") or event.get("error") or status.get("last_error", ""),
        "status": compact_status(status),
        "event_payload": event,
        "stdout_tail": tail_text(stdout_log, tail_lines),
        "stderr_tail": tail_text(stderr_log, tail_lines),
    }
    if not alert["reason"]:
        alert["reason"] = status.get("last_error", "")
    return alert


def write_alert(control_dir: Path, alert: dict[str, Any]) -> None:
    control_dir.mkdir(parents=True, exist_ok=True)
    latest = control_dir / "latest-error.json"
    alerts = control_dir / "error-alerts.jsonl"
    latest.write_text(json.dumps(alert, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with alerts.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(alert, ensure_ascii=False, sort_keys=True) + "\n")


def clear_resolved_latest_error(control_dir: Path, status_rows: dict[str, dict[str, str]]) -> None:
    latest = control_dir / "latest-error.json"
    try:
        alert = json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    if not isinstance(alert, dict):
        try:
            latest.unlink()
        except FileNotFoundError:
            pass
        return
    case_id = str(alert.get("case_id") or "")
    current_status = status_rows.get(case_id, {}).get("status", "")
    if current_status in {"quarantined", "paused"}:
        return
    try:
        latest.unlink()
    except FileNotFoundError:
        pass
    safe_print(
        f"[{utc_timestamp()}] resolved latest error cleared "
        f"case={case_id or '(unknown-case)'} status={current_status or '(missing)'}"
    )


def print_alert(alert: dict[str, Any]) -> None:
    status = alert.get("status", {})
    if not isinstance(status, dict):
        status = {}
    case_id = alert.get("case_id") or "(unknown-case)"
    segment = alert.get("segment") or status.get("current_segment") or "?"
    attempt = alert.get("attempt") or status.get("attempt") or "?"
    reason = alert.get("reason") or "(no reason recorded)"
    safe_print(
        f"[{alert['detected_utc']}] ERROR {alert.get('event')} "
        f"case={case_id} segment={segment} attempt={attempt} reason={reason}"
    )
    repro = status.get("reproduction_command")
    stdout_log = status.get("stdout_log")
    stderr_log = status.get("stderr_log")
    if repro:
        safe_print(f"  repro={repro}")
    if stdout_log:
        safe_print(f"  stdout={stdout_log}")
    if stderr_log:
        safe_print(f"  stderr={stderr_log}")
    stderr_tail = alert.get("stderr_tail") or []
    stdout_tail = alert.get("stdout_tail") or []
    tail = stderr_tail or stdout_tail
    if tail:
        safe_print("  tail:")
        for line in tail[-5:]:
            safe_print(f"    {line}")


def emit_current_quarantined(
    base_run_dir: Path,
    status_rows: dict[str, dict[str, str]],
    seen_current_path: Path,
    tail_lines: int,
) -> None:
    seen: set[str] = set()
    try:
        seen_payload = json.loads(seen_current_path.read_text(encoding="utf-8"))
        if isinstance(seen_payload, list):
            seen = {str(item) for item in seen_payload}
    except (OSError, json.JSONDecodeError, TypeError):
        pass

    changed = False
    for case_id, status in sorted(status_rows.items()):
        if status.get("status") not in {"quarantined", "paused"}:
            continue
        signature = f"{case_id}:{status.get('status')}:{status.get('attempt')}:{status.get('last_error')}"
        if signature in seen:
            continue
        event = {
            "event": f"current_{status.get('status')}",
            "case_id": case_id,
            "attempt": status.get("attempt", ""),
            "reason": status.get("last_error", ""),
        }
        alert = build_alert(base_run_dir, event, status_rows, tail_lines)
        write_alert(base_run_dir / "control", alert)
        print_alert(alert)
        seen.add(signature)
        changed = True

    if changed:
        seen_current_path.write_text(json.dumps(sorted(seen), ensure_ascii=False) + "\n", encoding="utf-8")


def build_monitor_error_alert(base_run_dir: Path, error: BaseException) -> dict[str, Any]:
    return {
        "detected_utc": utc_timestamp(),
        "base_run_dir": str(base_run_dir),
        "event": "monitor_internal_error",
        "case_id": "",
        "segment": "",
        "attempt": "",
        "reason": f"{type(error).__name__}: {error}",
        "status": {},
        "event_payload": {
            "event": "monitor_internal_error",
            "error_type": type(error).__name__,
            "error": str(error),
            "traceback": traceback.format_exc().splitlines(),
        },
        "stdout_tail": [],
        "stderr_tail": [],
    }


def print_monitor_error(alert: dict[str, Any]) -> None:
    safe_print(
        f"[{alert['detected_utc']}] MONITOR ERROR {alert['reason']} - continuing",
    )
    for line in alert.get("event_payload", {}).get("traceback", [])[-8:]:
        safe_print(f"  {line}")


def configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    # Windows PowerShell wraps native stderr lines as NativeCommandError records.
    # Keep monitor tracebacks in the normal tee/log stream instead.
    sys.stderr = sys.stdout


def run_monitor(args: argparse.Namespace) -> int:
    base_run_dir = Path(args.base_run_dir)
    control_dir = base_run_dir / "control"
    events_path = base_run_dir / "case-events.jsonl"
    status_path = base_run_dir / "case-status.csv"
    offset_path = control_dir / "error-monitor.offset"
    seen_current_path = control_dir / "error-monitor-current.json"

    offset = read_offset(offset_path, events_path, args.replay)
    if args.replay:
        write_offset(offset_path, 0)

    safe_print(f"Watching dummy growth errors: {base_run_dir}")
    while True:
        try:
            status_rows = load_status_rows(status_path)
            clear_resolved_latest_error(control_dir, status_rows)
            emit_current_quarantined(base_run_dir, status_rows, seen_current_path, args.tail_lines)

            events, offset = read_new_events(events_path, offset)
            for event in events:
                if event.get("event") not in ERROR_EVENTS:
                    continue
                alert = build_alert(base_run_dir, event, status_rows, args.tail_lines)
                write_alert(control_dir, alert)
                print_alert(alert)
            write_offset(offset_path, offset)
        except Exception as exc:  # Keep the visible monitor alive during live file churn.
            alert = build_monitor_error_alert(base_run_dir, exc)
            try:
                write_alert(control_dir, alert)
            except Exception:
                pass
            print_monitor_error(alert)

        if args.once:
            return 0
        time.sleep(max(1, args.interval_seconds))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-run-dir", required=True)
    parser.add_argument("--interval-seconds", type=int, default=2)
    parser.add_argument("--tail-lines", type=int, default=40)
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--replay", action="store_true", help="Read case-events.jsonl from the beginning.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    configure_stdio()
    return run_monitor(parse_args(argv))


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except Exception as exc:
        configure_stdio()
        base_run_dir = Path(".")
        if "--base-run-dir" in sys.argv:
            try:
                base_run_dir = Path(sys.argv[sys.argv.index("--base-run-dir") + 1])
            except (IndexError, ValueError):
                base_run_dir = Path(".")
        alert = build_monitor_error_alert(base_run_dir, exc)
        try:
            write_alert(base_run_dir / "control", alert)
        except Exception:
            pass
        print_monitor_error(alert)
        raise SystemExit(1)
