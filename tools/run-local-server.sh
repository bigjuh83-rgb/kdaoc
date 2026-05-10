#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG="$ROOT/CoreServer/config/serverconfig.xml"
EXAMPLE_CONFIG="$ROOT/CoreServer/config/serverconfig.example.xml"
DB_SQL_DIR="${DB_SQL_DIR:-$ROOT/../OpenDAoC-Database/opendaoc-db-core}"

DOTNET_BIN="${DOTNET_BIN:-dotnet}"
MYSQL_BIN="${MYSQL_BIN:-}"

CONFIGURATION="${CONFIGURATION:-Debug}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-opendaoc}"
DB_USER="${DB_USER:-root}"
DB_PASSWORD="${DB_PASSWORD:-my-secret-pw}"
DB_TREAT_TINY_AS_BOOLEAN="${DB_TREAT_TINY_AS_BOOLEAN:-false}"
SERVER_PORT="${SERVER_PORT:-10300}"
REGION_PORT="${REGION_PORT:-10400}"
UDP_PORT="${UDP_PORT:-10400}"
SERVER_NAME="${SERVER_NAME:-OpenDAoC Local}"
SERVER_NAME_SHORT="${SERVER_NAME_SHORT:-OPENDAOCL}"

INIT_DB=0
SKIP_BUILD=0
RUN_SERVER=1

usage() {
  cat <<'USAGE'
Usage: tools/run-local-server.sh [options]

Starts OpenDAoC locally with the CoreServer config pointed at a local MariaDB.

Options:
  --init-db       Create the database and import ../OpenDAoC-Database/opendaoc-db-core/*.sql.
  --skip-build    Do not run dotnet build before starting.
  --no-run        Prepare config/build only; do not start the server.
  -h, --help      Show this help.

Environment:
  DOTNET_BIN      dotnet executable. Default: dotnet, with /home/bigjuh/.dotnet/dotnet fallback.
  MYSQL_BIN       mariadb/mysql client executable. Auto-detected when --init-db is used.
  DB_HOST         MariaDB host. Default: 127.0.0.1
  DB_PORT         MariaDB port. Default: 3306
  DB_NAME         Database name. Default: opendaoc
  DB_USER         Database user. Default: root
  DB_PASSWORD     Database password. Default: my-secret-pw. Use DB_PASSWORD='' for no password.
  DB_SQL_DIR      SQL directory. Default: ../OpenDAoC-Database/opendaoc-db-core
  CONFIGURATION   Build configuration. Default: Debug
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --init-db)
      INIT_DB=1
      ;;
    --skip-build)
      SKIP_BUILD=1
      ;;
    --no-run)
      RUN_SERVER=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

if [[ ! -f "$CONFIG" ]]; then
  cp "$EXAMPLE_CONFIG" "$CONFIG"
fi

if ! command -v "$DOTNET_BIN" >/dev/null 2>&1; then
  if [[ -x "/home/bigjuh/.dotnet/dotnet" ]]; then
    DOTNET_BIN="/home/bigjuh/.dotnet/dotnet"
  else
    echo "dotnet not found. Install .NET 10 SDK or set DOTNET_BIN." >&2
    exit 1
  fi
fi

CONNECTION_STRING="Server=$DB_HOST;Port=$DB_PORT;Database=$DB_NAME;UserId=$DB_USER;Password=$DB_PASSWORD;TreatTinyAsBoolean=$DB_TREAT_TINY_AS_BOOLEAN;Pooling=true;MinimumPoolSize=30;MaximumPoolSize=120;ConnectionReset=false;CharSet=utf8mb4"

python3 - "$CONFIG" "$CONNECTION_STRING" "$SERVER_PORT" "$REGION_PORT" "$UDP_PORT" "$SERVER_NAME" "$SERVER_NAME_SHORT" <<'PY'
import shutil
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree as ET

config, conn, server_port, region_port, udp_port, server_name, server_name_short = sys.argv[1:]
path = Path(config)
tree = ET.parse(path)
root = tree.getroot()
server = root.find("Server")

if server is None:
    raise SystemExit(f"Missing <Server> in {path}")

def set_text(name, value):
    node = server.find(name)
    if node is None:
        raise SystemExit(f"Missing <{name}> in {path}")
    node.text = value

before = path.read_bytes()
set_text("Port", server_port)
set_text("RegionPort", region_port)
set_text("UdpPort", udp_port)
set_text("EnableUPnP", "False")
set_text("ServerName", server_name)
set_text("ServerNameShort", server_name_short)
set_text("DBType", "MYSQL")
set_text("DBConnectionString", conn)
set_text("DBAutosave", "True")
set_text("DBAutosaveInterval", "10")

ET.indent(tree, space="    ")
new_text = ET.tostring(root, encoding="utf-8", xml_declaration=True)

if before != new_text:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy2(path, path.with_suffix(path.suffix + f".backup-{stamp}"))
    path.write_bytes(new_text)
PY

if [[ "$INIT_DB" -eq 1 ]]; then
  if [[ -z "$MYSQL_BIN" ]]; then
    if command -v mariadb >/dev/null 2>&1; then
      MYSQL_BIN="mariadb"
    elif command -v mysql >/dev/null 2>&1; then
      MYSQL_BIN="mysql"
    else
      echo "mariadb/mysql client not found. Install MariaDB client or set MYSQL_BIN." >&2
      exit 1
    fi
  fi

  if [[ ! -d "$DB_SQL_DIR" ]]; then
    echo "DB_SQL_DIR not found: $DB_SQL_DIR" >&2
    exit 1
  fi

  MYSQL_ARGS=(--default-character-set=utf8mb4 --protocol=tcp -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER")
  if [[ -n "$DB_PASSWORD" ]]; then
    MYSQL_ARGS+=("-p$DB_PASSWORD")
  fi

  echo "Creating database '$DB_NAME' on $DB_HOST:$DB_PORT..."
  "$MYSQL_BIN" "${MYSQL_ARGS[@]}" \
    -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

  echo "Importing SQL files from $DB_SQL_DIR..."
  while IFS= read -r sql_file; do
    echo "  $(basename "$sql_file")"
    "$MYSQL_BIN" "${MYSQL_ARGS[@]}" "$DB_NAME" < "$sql_file"
  done < <(find "$DB_SQL_DIR" -maxdepth 1 -type f -name '*.sql' | sort)
fi

if [[ "$SKIP_BUILD" -eq 0 ]]; then
  "$DOTNET_BIN" build "$ROOT/CoreServer/CoreServer.csproj" -c "$CONFIGURATION"
fi

if [[ "$RUN_SERVER" -eq 1 ]]; then
  cd "$ROOT/$CONFIGURATION"
  exec "$DOTNET_BIN" CoreServer.dll --start
fi
