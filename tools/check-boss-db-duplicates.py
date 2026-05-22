#!/usr/bin/env python3
"""Check Mob table duplicate boss rows without printing DB credentials."""

from __future__ import annotations

import csv
import argparse
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


BOSS_NAMES = [
    "Golestandt",
    "Gjalpinulva",
    "Cuuldurach the Glimmer King",
    "Moran the Mighty",
    "Cailleach Uragaig",
    "Fester",
    "Wrath of Mordred",
    "Legendary Afanc",
    "Green Knight",
    "Lord Elidyn",
]


def parse_connection(root: Path) -> dict[str, str]:
    config = root / "CoreServer" / "config" / "serverconfig.xml"
    tree = ET.parse(config)
    server = tree.getroot().find("Server")
    conn = server.findtext("DBConnectionString") if server is not None else ""
    parts: dict[str, str] = {}
    for item in (conn or "").split(";"):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key.strip().lower()] = value.strip()
    return parts


def mysql_bin() -> str:
    candidates = [
        shutil.which("mariadb"),
        shutil.which("mysql"),
        "/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb",
        "/home/bigjuh/.local/opendaoc-mariadb/current/bin/mysql",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return str(candidate)
    raise SystemExit("mariadb/mysql client not found")


def run_mysql(root: Path, sql: str) -> list[dict[str, str]]:
    conn = parse_connection(root)
    env = os.environ.copy()
    env["MYSQL_PWD"] = conn.get("password", "")
    args = [
        mysql_bin(),
        "--protocol=tcp",
        "-h",
        conn.get("server", "127.0.0.1"),
        "-P",
        conn.get("port", "3306"),
        "-u",
        conn.get("userid", "root"),
        "--batch",
        "--raw",
        conn.get("database", "opendaoc"),
    ]
    proc = subprocess.run(args, input=sql, text=True, capture_output=True, env=env, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f"mysql exited with {proc.returncode}")
    if not proc.stdout.strip():
        return []
    reader = csv.DictReader(proc.stdout.splitlines(), delimiter="\t")
    return list(reader)


def exec_mysql(root: Path, sql: str) -> str:
    conn = parse_connection(root)
    env = os.environ.copy()
    env["MYSQL_PWD"] = conn.get("password", "")
    args = [
        mysql_bin(),
        "--protocol=tcp",
        "-h",
        conn.get("server", "127.0.0.1"),
        "-P",
        conn.get("port", "3306"),
        "-u",
        conn.get("userid", "root"),
        conn.get("database", "opendaoc"),
    ]
    proc = subprocess.run(args, input=sql, text=True, capture_output=True, env=env, check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or f"mysql exited with {proc.returncode}")
    return proc.stdout


def quote_sql(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fix-golestandt-empty-package",
        action="store_true",
        help="delete the duplicate Golestandt row whose PackageID is an empty string, keeping the NULL PackageID row",
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]

    columns = run_mysql(root, "SHOW COLUMNS FROM Mob;\n")
    column_names = [row["Field"] for row in columns]
    key_col = next((row["Field"] for row in columns if row.get("Key") == "PRI"), column_names[0])
    wanted = [name for name in BOSS_NAMES]
    wanted_sql = ",".join(quote_sql(name) for name in wanted)
    select_cols = [
        key_col,
        "Name",
        "Region",
        "X",
        "Y",
        "Z",
        "Level",
        "ClassType",
        "PackageID",
        "Brain",
        "RespawnInterval",
    ]
    existing_cols = [col for col in select_cols if col in column_names]
    col_sql = ", ".join(f"`{col}`" for col in existing_cols)

    rows = run_mysql(
        root,
        f"""
SELECT {col_sql}
FROM Mob
WHERE Name IN ({wanted_sql})
   OR Name LIKE 'KDAOC\\_TEST\\_%' ESCAPE '\\\\'
ORDER BY Name, Region, X, Y, Z, `{key_col}`;
""",
    )

    duplicate_names = run_mysql(
        root,
        f"""
SELECT Name, COUNT(*) AS Count
FROM Mob
WHERE Name IN ({wanted_sql})
GROUP BY Name
HAVING COUNT(*) > 1
ORDER BY Count DESC, Name;
""",
    )

    duplicate_spawns = run_mysql(
        root,
        f"""
SELECT Name, Region, X, Y, Z, COUNT(*) AS Count
FROM Mob
WHERE Name IN ({wanted_sql})
GROUP BY Name, Region, X, Y, Z
HAVING COUNT(*) > 1
ORDER BY Count DESC, Name, Region, X, Y, Z;
""",
    )

    clone_rows = [row for row in rows if row.get("Name", "").startswith("KDAOC_TEST_")]
    exact_rows = [row for row in rows if not row.get("Name", "").startswith("KDAOC_TEST_")]

    if args.fix_golestandt_empty_package:
        if key_col not in column_names:
            raise SystemExit(f"primary key column not found: {key_col}")
        matching = [
            row
            for row in exact_rows
            if row.get("Name") == "Golestandt"
            and row.get("Region") == "1"
            and row.get("X") == "391326"
            and row.get("Y") == "755351"
            and row.get("Z") == "388"
            and row.get("Level") == "80"
            and row.get("ClassType") == "DOL.GS.AlbGolestandt"
        ]
        empty_package = [row for row in matching if row.get("PackageID", "") == ""]
        null_package = [row for row in matching if row.get("PackageID", "") == "NULL"]
        if len(matching) != 2 or len(empty_package) != 1 or len(null_package) != 1:
            raise SystemExit(
                "refusing to delete: expected exactly one empty-PackageID Golestandt row and one NULL-PackageID row"
            )
        delete_id = empty_package[0][key_col]
        exec_mysql(
            root,
            f"""
START TRANSACTION;
DELETE FROM Mob
WHERE `{key_col}` = {quote_sql(delete_id)}
  AND Name = 'Golestandt'
  AND Region = 1
  AND X = 391326
  AND Y = 755351
  AND Z = 388
  AND Level = 80
  AND ClassType = 'DOL.GS.AlbGolestandt'
  AND COALESCE(PackageID, '') = '';
COMMIT;
""",
        )
        print(f"deleted duplicate Golestandt row: {key_col}={delete_id}")
        return main_without_fix(root, column_names, key_col, wanted)

    return main_without_fix(root, column_names, key_col, wanted)


def main_without_fix(root: Path, column_names: list[str], key_col: str, wanted: list[str]) -> int:
    wanted_sql = ",".join(quote_sql(name) for name in wanted)
    select_cols = [
        key_col,
        "Name",
        "Region",
        "X",
        "Y",
        "Z",
        "Level",
        "ClassType",
        "PackageID",
        "Brain",
        "RespawnInterval",
    ]
    existing_cols = [col for col in select_cols if col in column_names]
    col_sql = ", ".join(f"`{col}`" for col in existing_cols)

    rows = run_mysql(
        root,
        f"""
SELECT {col_sql}
FROM Mob
WHERE Name IN ({wanted_sql})
   OR Name LIKE 'KDAOC\\_TEST\\_%' ESCAPE '\\\\'
ORDER BY Name, Region, X, Y, Z, `{key_col}`;
""",
    )

    duplicate_names = run_mysql(
        root,
        f"""
SELECT Name, COUNT(*) AS Count
FROM Mob
WHERE Name IN ({wanted_sql})
GROUP BY Name
HAVING COUNT(*) > 1
ORDER BY Count DESC, Name;
""",
    )

    duplicate_spawns = run_mysql(
        root,
        f"""
SELECT Name, Region, X, Y, Z, COUNT(*) AS Count
FROM Mob
WHERE Name IN ({wanted_sql})
GROUP BY Name, Region, X, Y, Z
HAVING COUNT(*) > 1
ORDER BY Count DESC, Name, Region, X, Y, Z;
""",
    )

    clone_rows = [row for row in rows if row.get("Name", "").startswith("KDAOC_TEST_")]
    exact_rows = [row for row in rows if not row.get("Name", "").startswith("KDAOC_TEST_")]

    print("== duplicate exact boss names ==")
    if duplicate_names:
        writer = csv.DictWriter(sys.stdout, fieldnames=list(duplicate_names[0].keys()), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(duplicate_names)
    else:
        print("(none)")

    print("\n== duplicate exact boss spawn coordinates ==")
    if duplicate_spawns:
        writer = csv.DictWriter(sys.stdout, fieldnames=list(duplicate_spawns[0].keys()), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(duplicate_spawns)
    else:
        print("(none)")

    print("\n== exact boss rows ==")
    if exact_rows:
        writer = csv.DictWriter(sys.stdout, fieldnames=existing_cols, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(exact_rows)
    else:
        print("(none)")

    print("\n== KDAOC_TEST clone rows ==")
    if clone_rows:
        writer = csv.DictWriter(sys.stdout, fieldnames=existing_cols, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(clone_rows)
    else:
        print("(none)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
