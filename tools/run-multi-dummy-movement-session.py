#!/usr/bin/env python3
"""Provision and run multiple dummy characters for movement/hunt observation."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
OUTPUT = TOOLS / "test-output" / "multi-dummy-movement"
MARIADB = Path("/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb")

# Albion low-level hunt area (Cotswold vicinity)
HUNT_START = (523520, 490520, 2543)
HUNT_WAYPOINTS = "523520,490520,2543|523900,490900,2543|524250,490650,2543|523760,490280,2543"
HUNT_PATH_GRAPH = "tools/pathing/regions/albion-lowlevel.json"
HUNT_GROUND_Z = "tools/pathing/heightmaps/region001_client_zones.json"

# Albion giant boar boss hunt (Pve8 vicinity)
BOSS_HUNT_START = (561900, 357450, 4868)

# Salisbury slope loop (movement rewind probe area)
MOVE_WAYPOINTS = (
    "581632,581632,2192|582432,581632,2008|582432,582432,1968|581066,581066,2412|"
    "580800,582800,2154|582800,580800,2159|581632,581632,2192"
)
MOVE_START = (581632, 581632, 2192)

# Non-stealth Albion classes only (no Scout/Minstrel/Infiltrator/Nightshade).
STEALTH_CLASS_IDS = {3, 4, 9, 12}
NON_STEALTH_CLASS_CYCLE = "2|11|6|7"  # Armsman, Mercenary, Cleric, Wizard
NON_STEALTH_SPEC_CYCLE = (
    "Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1||"
    "Slash|50;Thrust|1;Crush|1;Dual Wield|50;Parry|28||"
    "Smite|1;Rejuvenation|40;Enhancement|36||"
    "Fire Magic|50;Earth Magic|15;Cold Magic|10"
)
DEFAULT_CHARACTER_NAMES = "가온|라온|이든|하람|서윤|도윤|유찬|시온"


def hunt_start_xyz(args: argparse.Namespace) -> tuple[int, int, int]:
    if getattr(args, "hunt_profile", "low") == "boss":
        return BOSS_HUNT_START
    if args.mode in {"hunt", "both"}:
        return HUNT_START
    return MOVE_START


def hunt_behavior_extras(args: argparse.Namespace) -> list[str]:
    if getattr(args, "hunt_profile", "low") == "boss":
        return [
            "--player-level",
            "50",
            "--ideal-target-level",
            "34",
            "--min-target-level",
            "30",
            "--max-target-level",
            "50",
            "--max-target-level-delta",
            "16",
            "--max-target-distance",
            "4500",
            "--target-timeout",
            "120",
            "--target-loss-grace",
            "3.0",
            "--target-loss-rescan",
            "--target-loss-scan-interval",
            "0.35",
            "--combat-interval",
            "1.0",
            "--attack-range",
            "145",
            "--move-step",
            "120",
            "--skill-interval",
            "2.5",
            "--prefer-target-name",
            "giant boar",
            "--avoid-target-name",
            "peallaidh,Grymkin,moorlich,archer,horse,warder,bone snapper,danaoin",
        ]
    return [
        "--player-level",
        "1",
        "--ideal-target-level",
        "0" if args.party <= 1 else "3",
        "--min-target-level",
        "0",
        "--max-target-level",
        "0" if args.party <= 1 else "-1",
        "--max-target-level-delta",
        "0" if args.party <= 1 else "4",
        "--max-target-distance",
        "4500",
        "--target-timeout",
        "55",
        "--target-loss-grace",
        "1.5",
        "--target-loss-rescan",
        "--target-loss-scan-interval",
        "0.35",
        "--combat-interval",
        "1.6" if args.party <= 1 else "1.3",
        "--attack-range",
        "120",
        "--move-step",
        "260",
        "--skill-interval",
        "3.0",
        "--prefer-target-name",
        "worker ant,boar piglet",
        "--avoid-target-name",
        "green snake",
    ]


def read_db_password() -> str:
    root = ET.parse(ROOT / "CoreServer/config/serverconfig.xml").getroot()
    server = root.find("Server")
    conn = server.findtext("DBConnectionString") if server is not None else ""
    for part in (conn or "").split(";"):
        if part.lower().startswith("password="):
            return part.split("=", 1)[1]
    raise RuntimeError("database password not found in serverconfig.xml")


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
        raise RuntimeError(proc.stderr.strip() or "mysql command failed")
    return proc.stdout.strip()


def character_name_from_account(username: str) -> str:
    if username.lower().startswith("dummy"):
        return "Dummy" + username[5:]
    return username[:1].upper() + username[1:]


def provision_accounts(args: argparse.Namespace, accounts_csv: Path, start_xyz: tuple[int, int, int]) -> list[dict[str, str]]:
    accounts_csv.parent.mkdir(parents=True, exist_ok=True)
    sx, sy, sz = start_xyz
    command = [
        sys.executable,
        str(TOOLS / "provision-dummy-accounts.py"),
        "--prefix",
        args.prefix,
        "--start",
        str(args.start),
        "--count",
        str(args.count),
        "--password",
        args.password,
        "--template-account",
        args.template_account,
        "--template-character",
        args.template_character,
        "--realm",
        str(args.realm),
        "--priv-level",
        str(args.priv_level),
        "--class-cycle",
        args.class_cycle,
        "--csv-class-cycle",
        args.class_cycle,
        "--spec-cycle",
        args.spec_cycle,
        "--character-name-mode",
        args.character_name_mode,
        "--character-names",
        args.character_names,
        "--start-x",
        str(sx),
        "--start-y",
        str(sy),
        "--start-z",
        str(sz),
        "--start-region",
        "1",
        "--position-step",
        str(args.position_step),
        "--csv",
        str(accounts_csv),
        "--replace",
    ]
    if args.boss_hunt:
        command += ["--level", "50|50|50|50|50|50|50|50|50|50|50|50|50|50|50|50"]
    print("provisioning accounts...")
    print(" ".join(command))
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode != 0:
        raise SystemExit(f"provision-dummy-accounts failed with rc={proc.returncode}")

    db_password = read_db_password()
    rows: list[dict[str, str]] = []
    with accounts_csv.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        for extra in ("character_name", "start_x", "start_y", "start_z"):
            if extra not in fieldnames:
                fieldnames.append(extra)
        for index, row in enumerate(reader):
            offset = index * args.position_step
            username = row["username"]
            char_name = mysql(
                db_password,
                f"SELECT Name FROM dolcharacters WHERE AccountName = '{username}' ORDER BY AccountSlot LIMIT 1",
            )
            row["character_name"] = char_name
            row["start_x"] = str(sx + offset)
            row["start_y"] = str(sy + offset)
            row["start_z"] = str(sz)
            rows.append(row)

    with accounts_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})

    return rows


def write_accounts_csv(
    path: Path,
    usernames: list[str],
    password: str,
    realm: int,
    *,
    start_xyz: tuple[int, int, int],
    position_step: int,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["username", "password", "realm", "char_index", "start_x", "start_y", "start_z"],
        )
        writer.writeheader()
        sx, sy, sz = start_xyz
        for index, username in enumerate(usernames):
            offset = index * position_step
            writer.writerow(
                {
                    "username": username,
                    "password": password,
                    "realm": realm,
                    "char_index": 0,
                    "start_x": sx + offset,
                    "start_y": sy + offset,
                    "start_z": sz,
                }
            )


def apply_movement_session_defaults(args: argparse.Namespace) -> None:
    if args.visible_movement and args.move_update_interval == 0.0:
        args.move_update_interval = 0.20
        if args.move_interval == 0.25:
            args.move_interval = 0.20


def build_behavior_command(args: argparse.Namespace, accounts_csv: Path) -> list[str]:
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
        str(args.count),
        "--hold",
        str(args.hold),
        "--ramp-up",
        str(args.ramp_up),
        "--party-size",
        str(args.party if args.party > 1 else 1),
        "--realm",
        str(args.realm),
        "--smooth-movement",
        "--movement-speed",
        str(args.movement_speed),
        "--smooth-move-interval",
        str(args.move_interval),
        "--movement-update-interval",
        str(args.move_update_interval),
        "--combat-direct-move-distance",
        str(args.combat_direct_move_distance),
        "--path-last-mile-distance",
        str(args.path_last_mile_distance),
        "--path-max-edge-length",
        str(args.path_max_edge_length),
        "--verbose",
    ]

    if args.visible_movement:
        command += [
            "--tick",
            str(args.tick),
            "--target-face-command-interval",
            "0",
        ]

    command += ["--ground-z-map", HUNT_GROUND_Z]

    if args.visible_movement and args.mode in {"hunt", "both"}:
        command += ["--server-correction-smoothing"]

    if args.mode in {"hunt", "both"}:
        profile = "party-dps" if args.party > 1 else "solo-melee"
        rotation = "auto" if args.party > 1 else "melee-basic"
        command += [
            "--hunter",
            "--behavior-profile",
            profile,
            "--action-rotation",
            rotation,
            "--target-selection",
            "smart",
            "--target-pool",
            "4",
            *hunt_behavior_extras(args),
        ]
        if args.party > 1:
            command += [
                "--party-role-strategy",
                "mixed",
                "--party-assist-only",
                "--melee-stick-attack",
                "--melee-stick-attack-distance",
                "300",
            ]
        if not args.visible_movement:
            command += [
                "--path-graph",
                HUNT_PATH_GRAPH,
                "--client-grid-nav-map",
                HUNT_GROUND_Z,
                "--path-region",
                "1",
            ]

    if args.mode in {"move", "both"}:
        command += [
            "--move",
            "--waypoints",
            args.waypoints or (MOVE_WAYPOINTS if args.mode == "move" else HUNT_WAYPOINTS),
            "--waypoint-mode",
            "loop",
            "--waypoint-stop-distance",
            "120",
            "--waypoint-step",
            "280",
        ]

    if args.audit:
        command += [
            "--startup-command",
            "/movementaudit on {character} full",
            "--startup-delay",
            "2",
        ]

    report_path = accounts_csv.with_suffix("").with_suffix(".report.md")
    command += ["--report-md", str(report_path)]

    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Run multiple dummy characters for movement/hunt observation")
    parser.add_argument("--count", type=int, default=4, help="number of dummy accounts (default: 4)")
    parser.add_argument("--start", type=int, default=1, help="account number suffix start (default: 1)")
    parser.add_argument("--prefix", default="parthunt", help="account prefix (default: parthunt -> parthunt001)")
    parser.add_argument("--password", default="dummy-pass")
    parser.add_argument("--template-account", default="albtest002")
    parser.add_argument("--template-character", default="Albtest002")
    parser.add_argument("--class-cycle", default=NON_STEALTH_CLASS_CYCLE, help="pipe-separated class IDs (default: Armsman|Mercenary|Cleric|Wizard)")
    parser.add_argument("--spec-cycle", default=NON_STEALTH_SPEC_CYCLE, help="||-separated specs aligned to class-cycle")
    parser.add_argument("--character-name-mode", choices=["sequential", "natural"], default="natural")
    parser.add_argument("--character-names", default=DEFAULT_CHARACTER_NAMES, help="pipe-separated visible character names")
    parser.add_argument("--realm", type=int, default=1)
    parser.add_argument("--priv-level", type=int, default=1, help="dummy account privilege level; keep 1 for visual movement tests so server does not GM-stealth the characters")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=10300)
    parser.add_argument("--hold", type=float, default=180.0, help="seconds each dummy stays online")
    parser.add_argument("--ramp-up", type=float, default=8.0, help="seconds between logins")
    parser.add_argument("--position-step", type=int, default=180, help="spawn offset between dummies")
    parser.add_argument("--movement-speed", type=float, default=191.0)
    parser.add_argument("--move-interval", type=float, default=0.25, help="smooth move step interval (seconds)")
    parser.add_argument(
        "--move-update-interval",
        type=float,
        default=0.0,
        help="seconds between C2S position packets; 0 sends every move step (visible running)",
    )
    parser.add_argument(
        "--visible-movement",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="disable nav path snapping and send position every move step",
    )
    parser.add_argument("--tick", type=float, default=0.05)
    parser.add_argument("--combat-direct-move-distance", type=float, default=180.0)
    parser.add_argument("--path-last-mile-distance", type=float, default=180.0)
    parser.add_argument("--path-max-edge-length", type=float, default=220.0)
    parser.add_argument(
        "--mode",
        choices=["hunt", "move", "both"],
        default="hunt",
        help="hunt=low-level mobs, move=Salisbury loop, both=hunt+patrol",
    )
    parser.add_argument("--waypoints", default="", help="override waypoints for move/both mode")
    parser.add_argument(
        "--hunt-profile",
        choices=["low", "boss"],
        default="low",
        help="low=Cotswold mobs, boss=giant boar L34 party hunt",
    )
    parser.add_argument("--audit", action="store_true", help="enable /movementaudit on each dummy (may require GM priv; does not auto-raise --priv-level)")
    parser.add_argument("--party", type=int, default=4, help="party size (>1 groups dummies; 1=solo each)")
    parser.add_argument(
        "--party-hunt",
        action="store_true",
        help="shorthand for --mode hunt --party <count> with non-stealth party classes",
    )
    parser.add_argument(
        "--solo-hunt",
        action="store_true",
        help="shorthand for --mode hunt --party 1 (each dummy hunts solo)",
    )
    parser.add_argument(
        "--boss-hunt",
        action="store_true",
        help="shorthand for --hunt-profile boss --party <count> giant boar hunt",
    )
    parser.add_argument("--provision-only", action="store_true", help="only create accounts/CSV, do not launch dummies")
    args = parser.parse_args()

    if args.party_hunt:
        args.mode = "hunt"
        args.hunt_profile = "low"
        if args.party <= 1:
            args.party = args.count

    if args.solo_hunt:
        args.mode = "hunt"
        args.hunt_profile = "low"
        args.party = 1

    if args.boss_hunt:
        args.mode = "hunt"
        args.hunt_profile = "boss"
        args.party = args.count

    apply_movement_session_defaults(args)

    if args.priv_level != 1:
        print(
            "WARNING: PrivLevel != 1 enables GM auto-stealth on login; "
            "visual movement speed observations will be inaccurate.",
            file=sys.stderr,
        )

    if args.audit and args.priv_level < 2:
        print(
            "WARNING: --audit uses /movementaudit startup command which typically requires GM priv; "
            f"keeping --priv-level {args.priv_level} per policy (not auto-bumping to 2).",
            file=sys.stderr,
        )

    stealth_ids = {int(part.strip()) for part in args.class_cycle.split("|") if part.strip()}
    blocked = sorted(stealth_ids & STEALTH_CLASS_IDS)
    if blocked:
        raise SystemExit(f"stealth classes are not allowed: {blocked}")

    if args.party > 1 and args.party > args.count:
        raise SystemExit("--party cannot be greater than --count")
    if args.count < 1:
        raise SystemExit("--count must be >= 1")
    if not MARIADB.exists():
        raise SystemExit(f"mariadb client not found: {MARIADB}")

    OUTPUT.mkdir(parents=True, exist_ok=True)

    start_xyz = hunt_start_xyz(args)
    accounts_csv = OUTPUT / f"{args.prefix}-accounts.csv"
    rows = provision_accounts(args, accounts_csv, start_xyz)

    print("provisioned dummy accounts:")
    for row in rows:
        print(
            f"  - account={row['username']} character={row.get('character_name', '?')} "
            f"class={row.get('class_name', '?')} (id={row.get('class_id', '?')})"
        )

    if args.provision_only:
        print(f"accounts_csv={accounts_csv}")
        return 0

    behavior_command = build_behavior_command(args, accounts_csv)
    print("launching dummies...")
    print(" ".join(behavior_command))

    proc = subprocess.run(behavior_command, cwd=ROOT, check=False)
    print(f"behavior-dummy-client exit={proc.returncode}")

    if args.audit:
        print("audit logs (if movement occurred):")
        for row in rows:
            char_name = row.get("character_name") or character_name_from_account(row["username"])
            log_path = ROOT / "Debug" / "logs" / f"movement-audit-{char_name}.jsonl"
            print(f"  - {log_path} ({'exists' if log_path.exists() else 'missing'})")

    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
