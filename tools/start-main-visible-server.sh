#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_ROOT="${OPENDAOC_MARIADB_ROOT:-/home/bigjuh/.local/opendaoc-mariadb}"
MYSQLD_SAFE="$DB_ROOT/current/bin/mariadbd-safe"
MYSQLADMIN="$DB_ROOT/current/bin/mariadb-admin"
MY_CNF="$DB_ROOT/etc/my.cnf"
API_PORT="${OPENDAOC_API_PORT:-5000}"

require_file() {
  local path="$1"
  local description="$2"

  if [[ ! -e "$path" ]]; then
    echo "[OpenDAoC] Missing $description: $path" >&2
    exit 1
  fi
}

stop_existing_game_server() {
  local pids
  pids="$(pgrep -f '[C]oreServer.dll --start' || true)"

  if [[ -z "$pids" ]]; then
    return
  fi

  echo "[OpenDAoC] Existing game server detected; stopping it first..."
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true

  for _ in {1..15}; do
    if [[ -z "$(pgrep -f '[C]oreServer.dll --start' || true)" ]] && ! server_ports_in_use; then
      echo "[OpenDAoC] Previous game server stopped."
      return
    fi
    sleep 1
  done

  pids="$(pgrep -f '[C]oreServer.dll --start' || true)"
  if [[ -n "$pids" ]]; then
    echo "[OpenDAoC] Previous game server did not exit in time; forcing stop..."
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi

  for _ in {1..15}; do
    if [[ -z "$(pgrep -f '[C]oreServer.dll --start' || true)" ]] && ! server_ports_in_use; then
      echo "[OpenDAoC] Previous game server force-stopped."
      return
    fi
    sleep 1
  done

  echo "[OpenDAoC] Previous game server is still alive after forced stop." >&2
  pgrep -af '[C]oreServer.dll --start' >&2 || true
}

server_ports_in_use() {
  ss -ltn | grep -Eq ":(10300|10400|${API_PORT}) "
}

read_config_password() {
  python3 - <<'PY'
from pathlib import Path
from xml.etree import ElementTree as ET

path = Path("CoreServer/config/serverconfig.xml")
root = ET.parse(path).getroot()
server = root.find("Server")
conn = server.findtext("DBConnectionString") if server is not None else ""

for part in (conn or "").split(";"):
    if part.lower().startswith("password="):
        print(part.split("=", 1)[1])
        break
PY
}

cd "$ROOT"

require_file "$MYSQLD_SAFE" "MariaDB startup script"
require_file "$MYSQLADMIN" "MariaDB admin client"
require_file "$MY_CNF" "MariaDB config"

stop_existing_game_server

if server_ports_in_use; then
  echo "[OpenDAoC] Game server ports are still in use after cleanup."
  ss -ltunp | grep -E ":10300 |:10400 |:${API_PORT} " || true
  exit 1
fi

DB_PASSWORD="${OPENDAOC_DB_PASSWORD:-$(read_config_password)}"

if ! ss -ltn | grep -q ':3306 '; then
  echo "[OpenDAoC] Starting local MariaDB..."
  mkdir -p "$DB_ROOT/logs" "$DB_ROOT/run"
  rm -f "$DB_ROOT/run/mariadb.pid" "$DB_ROOT/run/mariadb.sock"
  setsid -f "$MYSQLD_SAFE" --defaults-file="$MY_CNF" >> "$DB_ROOT/logs/mariadb.safe.log" 2>&1 < /dev/null

  for _ in {1..45}; do
    if MYSQL_PWD="$DB_PASSWORD" "$MYSQLADMIN" --protocol=tcp -h 127.0.0.1 -P 3306 -uroot ping >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

MYSQL_PWD="$DB_PASSWORD" "$MYSQLADMIN" --protocol=tcp -h 127.0.0.1 -P 3306 -uroot ping >/dev/null

LAN_IP="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^192\.168\.' | head -n 1 || true)"
if [[ -n "$LAN_IP" ]]; then
  echo "[OpenDAoC] Starting visible main server on 0.0.0.0:10300 (LAN $LAN_IP)..."
else
  echo "[OpenDAoC] Starting visible main server on 0.0.0.0:10300..."
fi

DB_PASSWORD="$DB_PASSWORD" DOTNET_BIN="/home/bigjuh/.dotnet/dotnet" exec tools/run-local-server.sh --skip-build
