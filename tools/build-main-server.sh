#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

DB_PASSWORD="${OPENDAOC_DB_PASSWORD:-$(read_config_password)}" \
DOTNET_BIN="${DOTNET_BIN:-/home/bigjuh/.dotnet/dotnet}" \
  tools/run-local-server.sh --no-run
