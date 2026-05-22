#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${OPENDAOC_DUMMY_HOST:-192.168.0.42}"
PORT="${OPENDAOC_DUMMY_PORT:-10300}"
REPORT_DIR="${1:-tools/reports/highlevel-party-albion-pve8-giant-boar-l34}"

DB_PASS="$(
python3 - <<'PY'
import re
from pathlib import Path

config = Path("CoreServer/config/serverconfig.xml").read_text(encoding="utf-8")
match = re.search(r"Password=([^;]+)", config)
if not match:
    raise SystemExit("Could not find DB password in serverconfig.xml")
print(match.group(1))
PY
)"

MYSQL_PWD="$DB_PASS" /home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb -h127.0.0.1 -uroot opendaoc <<'SQL'
UPDATE DOLCharacters
SET
  Region = 1,
  Xpos = CASE AccountName
    WHEN 'dummy040' THEN 561900
    WHEN 'dummy300' THEN 561980
    WHEN 'dummy041' THEN 562060
    WHEN 'dummy042' THEN 562140
    WHEN 'dummy043' THEN 562220
    WHEN 'dummy302' THEN 562300
    WHEN 'dummy301' THEN 561940
    WHEN 'dummy303' THEN 562020
    ELSE Xpos
  END,
  Ypos = CASE AccountName
    WHEN 'dummy040' THEN 357450
    WHEN 'dummy300' THEN 357460
    WHEN 'dummy041' THEN 357470
    WHEN 'dummy042' THEN 357480
    WHEN 'dummy043' THEN 357490
    WHEN 'dummy302' THEN 357500
    WHEN 'dummy301' THEN 357550
    WHEN 'dummy303' THEN 357560
    ELSE Ypos
  END,
  Zpos = 4826,
  Health = 9999,
  Endurance = 10000,
  Mana = 9999,
  DeathTime = 0,
  DeathCount = 0
WHERE AccountName IN ('dummy040','dummy300','dummy041','dummy042','dummy043','dummy302','dummy301','dummy303');
SQL

mkdir -p "$REPORT_DIR"

python3 tools/behavior-dummy-client.py \
  --host "$HOST" \
  --port "$PORT" \
  --accounts tools/dummy-party-albion-pve8.csv \
  --concurrency 8 \
  --rounds 1 \
  --hold 150 \
  --timeout 8 \
  --ramp-up 0.4 \
  --ping-interval 10 \
  --position-heartbeat-interval 2.5 \
  --combat \
  --hunter \
  --combat-interval 1.0 \
  --move \
  --smooth-movement \
  --server-correction-smoothing \
  --movement-speed 185 \
  --smooth-move-interval 0.20 \
  --movement-update-interval 0.20 \
  --move-step 120 \
  --attack-range 145 \
  --melee-range-buffer 25 \
  --minimum-melee-stop-distance 65 \
  --use-skills \
  --skill-interval 2.5 \
  --action-rotation auto \
  --party-slot-rotations "melee-basic,melee-basic,melee-burst,melee-burst,melee-burst,melee-burst,healer-support,healer-support" \
  --party-size 8 \
  --party-assist-only \
  --party-min-ready 8 \
  --party-form-up-delay 8 \
  --party-assist-interval 0.8 \
  --party-assist-attack-delay 0.2 \
  --party-require-leader-engaged \
  --party-invite-interval 5 \
  --party-accept-interval 2 \
  --party-follow-interval 0.6 \
  --party-follow-step 320 \
  --party-follow-distance 250 \
  --party-heal-leader-interval 1.0 \
  --party-heal-leader-health-percent 95 \
  --party-buff-interval 12 \
  --party-buff-spell-levels 1,10,20,30,40 \
  --player-level 50 \
  --min-target-level 34 \
  --max-target-level 34 \
  --ideal-target-level 34 \
  --target-selection smart \
  --target-pool 4 \
  --max-target-distance 2200 \
  --target-timeout 90 \
  --target-failure-cooldown 15 \
  --target-failure-name-cooldown 25 \
  --prefer-target-name "giant boar" \
  --avoid-target-name "peallaidh,Grymkin,moorlich,archer,horse,warder,bone snapper,danaoin" \
  --auto-loot \
  --jitter 0.1 \
  --metrics-csv "$REPORT_DIR/metrics.csv" \
  --combat-csv "$REPORT_DIR/combat.csv" \
  --report-md "$REPORT_DIR/report.md"
