#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== processes ==="
ps aux | grep -E 'behavior-dummy|run-multi-dummy|run-observation' | grep -v grep || echo "(none)"

echo
echo "=== accounts ==="
python3 - <<'PY'
from pathlib import Path
from xml.etree import ElementTree as ET
import subprocess

root = ET.parse("CoreServer/config/serverconfig.xml").getroot()
conn = root.find("Server").findtext("DBConnectionString") or ""
password = next((p.split("=", 1)[1] for p in conn.split(";") if p.lower().startswith("password=")), "")
mariadb = Path("/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb")
sql = "SELECT Name FROM account WHERE Name LIKE 'solohunt%' OR Name LIKE 'parthunt%' OR Name LIKE 'bosshunt%' ORDER BY Name"
out = subprocess.check_output(
    [str(mariadb), "-h", "127.0.0.1", "-P", "3306", "-u", "root", f"-p{password}", "opendaoc", "-e", sql],
    text=True,
)
print(out.strip() or "(none)")
PY

echo
echo "=== logs ==="
LOGDIR="$ROOT/tools/test-output/observation-dummies"
for f in solohunt parthunt bosshunt; do
  p="$LOGDIR/${f}-session.log"
  if [[ -f "$p" ]]; then
    sz=$(wc -c < "$p")
    echo "$f: ${sz} bytes"
    tail -n 5 "$p" 2>/dev/null || true
  else
    echo "$f: missing"
  fi
  echo "---"
done
