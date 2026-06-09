#!/usr/bin/env python3
"""Stop movement-test dummy clients and remove movhunt/movdummy accounts."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MARIADB = Path("/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb")
PREFIXES = ("movhunt", "movdummy", "parthunt", "solohunt", "bosshunt")
PROCESS_PATTERNS = ("behavior-dummy-client.py", "run-multi-dummy-movement-session.py")
GRACEFUL_SHUTDOWN_TIMEOUT = 35.0
PROCESS_POLL_INTERVAL = 0.5


def read_db_password() -> str:
    root = ET.parse(ROOT / "CoreServer/config/serverconfig.xml").getroot()
    server = root.find("Server")
    conn = server.findtext("DBConnectionString") if server is not None else ""
    for part in (conn or "").split(";"):
        if part.lower().startswith("password="):
            return part.split("=", 1)[1]
    return "opendaoc-local"


def mysql(password: str, sql: str) -> str:
    proc = subprocess.run(
        [
            str(MARIADB),
            "-h",
            "127.0.0.1",
            "-P",
            "3306",
            "-uroot",
            f"-p{password}",
            "opendaoc",
            "-N",
            "-B",
            "-e",
            sql,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "mysql failed")
    return proc.stdout.strip()


def matching_processes() -> list[str]:
    found: list[str] = []
    for pattern in PROCESS_PATTERNS:
        proc = subprocess.run(["pgrep", "-af", pattern], capture_output=True, text=True, check=False)
        if proc.returncode != 0:
            continue
        for line in proc.stdout.splitlines():
            text = line.strip()
            if text:
                found.append(text)
    return found


def stop_processes() -> None:
    if not matching_processes():
        return

    print("requesting graceful dummy shutdown (/quit via SIGTERM)...")
    for pattern in PROCESS_PATTERNS:
        subprocess.run(["pkill", "-TERM", "-f", pattern], check=False)

    deadline = time.monotonic() + GRACEFUL_SHUTDOWN_TIMEOUT
    while time.monotonic() < deadline:
        if not matching_processes():
            print("dummy processes exited cleanly")
            return
        time.sleep(PROCESS_POLL_INTERVAL)

    remaining = matching_processes()
    if remaining:
        print(f"forcing shutdown after {GRACEFUL_SHUTDOWN_TIMEOUT:.0f}s timeout:")
        for line in remaining:
            print(f"  - {line}")
        for pattern in PROCESS_PATTERNS:
            subprocess.run(["pkill", "-KILL", "-f", pattern], check=False)


def delete_accounts(password: str) -> None:
    for prefix in PREFIXES:
        mysql(
            password,
            f"DELETE FROM dolcharacters WHERE AccountName LIKE '{prefix}%'; "
            f"DELETE FROM account WHERE Name LIKE '{prefix}%';",
        )
        print(f"deleted: {prefix}*")


def main() -> int:
    if not MARIADB.exists():
        raise SystemExit(f"mariadb not found: {MARIADB}")

    stop_processes()
    password = read_db_password()
    delete_accounts(password)

    remaining = mysql(
        password,
        "SELECT Name FROM account WHERE Name LIKE 'movhunt%' OR Name LIKE 'movdummy%' OR Name LIKE 'parthunt%' OR Name LIKE 'solohunt%' OR Name LIKE 'bosshunt%' ORDER BY Name",
    )
    print("remaining:", remaining or "(none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
