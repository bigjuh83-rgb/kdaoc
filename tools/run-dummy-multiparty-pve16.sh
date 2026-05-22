#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${OPENDAOC_DUMMY_HOST:-192.168.0.42}"
PORT="${OPENDAOC_DUMMY_PORT:-10300}"
STAMP="$(date +%Y%m%d-%H%M%S)"
REPORT_ROOT="${1:-tools/reports/multiparty-pve16-${STAMP}}"
GROUND_Z_MAP="tools/pathing/heightmaps/region001_client_zones.json"

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
    WHEN 'dummy400' THEN 562500
    WHEN 'dummy401' THEN 562580
    WHEN 'dummy402' THEN 562660
    WHEN 'dummy403' THEN 562740
    WHEN 'dummy404' THEN 562820
    WHEN 'dummy405' THEN 562900
    WHEN 'dummy406' THEN 562980
    WHEN 'dummy407' THEN 563060
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
    WHEN 'dummy400' THEN 357690
    WHEN 'dummy401' THEN 357700
    WHEN 'dummy402' THEN 357710
    WHEN 'dummy403' THEN 357720
    WHEN 'dummy404' THEN 357730
    WHEN 'dummy405' THEN 357740
    WHEN 'dummy406' THEN 357820
    WHEN 'dummy407' THEN 357830
    ELSE Ypos
  END,
  Zpos = CASE AccountName
    WHEN 'dummy040' THEN 4868
    WHEN 'dummy300' THEN 4867
    WHEN 'dummy041' THEN 4865
    WHEN 'dummy042' THEN 4863
    WHEN 'dummy043' THEN 4862
    WHEN 'dummy302' THEN 4860
    WHEN 'dummy301' THEN 4867
    WHEN 'dummy303' THEN 4866
    WHEN 'dummy400' THEN 4852
    WHEN 'dummy401' THEN 4853
    WHEN 'dummy402' THEN 4854
    WHEN 'dummy403' THEN 4854
    WHEN 'dummy404' THEN 4855
    WHEN 'dummy405' THEN 4855
    WHEN 'dummy406' THEN 4855
    WHEN 'dummy407' THEN 4855
    ELSE Zpos
  END,
  Health = 9999,
  Endurance = 10000,
  Mana = 9999,
  DeathTime = 0,
  DeathCount = 0
WHERE AccountName IN (
  'dummy040','dummy300','dummy041','dummy042','dummy043','dummy302','dummy301','dummy303',
  'dummy400','dummy401','dummy402','dummy403','dummy404','dummy405','dummy406','dummy407'
);
SQL

mkdir -p "$REPORT_ROOT/party-classic/traces" "$REPORT_ROOT/party-mixed/traces"

run_party() {
  local accounts="$1"
  local report_dir="$2"
  local rotations="$3"

  python3 tools/behavior-dummy-client.py \
    --host "$HOST" \
    --port "$PORT" \
    --accounts "$accounts" \
    --concurrency 8 \
    --rounds 1 \
    --hold 180 \
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
    --ground-z-map "$GROUND_Z_MAP" \
    --use-skills \
    --skill-interval 2.5 \
    --action-rotation auto \
    --party-slot-rotations "$rotations" \
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
    --player-level 50 \
    --min-target-level 34 \
    --max-target-level 34 \
    --ideal-target-level 34 \
    --target-selection smart \
    --target-pool 6 \
    --max-target-distance 2400 \
    --target-timeout 90 \
    --target-failure-cooldown 15 \
    --target-failure-name-cooldown 25 \
    --prefer-target-name "giant boar" \
    --avoid-target-name "peallaidh,Grymkin,moorlich,arawnite,shamaness,archer,horse,warder,bone snapper,danaoin" \
    --auto-loot \
    --jitter 0.1 \
    --trace-movement-log "$report_dir/traces/{username}-{round}.jsonl" \
    --metrics-csv "$report_dir/metrics.csv" \
    --combat-csv "$report_dir/combat.csv" \
    --report-md "$report_dir/report.md"
}

pid_classic=0
pid_mixed=0
cleanup() {
  if [[ "$pid_classic" != "0" ]]; then kill "$pid_classic" 2>/dev/null || true; fi
  if [[ "$pid_mixed" != "0" ]]; then kill "$pid_mixed" 2>/dev/null || true; fi
}
trap cleanup EXIT

run_party \
  "tools/dummy-party-albion-pve8.csv" \
  "$REPORT_ROOT/party-classic" \
  "melee-basic,melee-basic,melee-burst,melee-burst,melee-burst,melee-burst,healer-support,healer-support" \
  > "$REPORT_ROOT/party-classic/output.log" 2>&1 &
pid_classic=$!

run_party \
  "tools/dummy-party-albion-mixed-pve8.csv" \
  "$REPORT_ROOT/party-mixed" \
  "melee-basic,melee-burst,melee-basic,caster-basic,caster-basic,caster-basic,caster-basic,healer-support" \
  > "$REPORT_ROOT/party-mixed/output.log" 2>&1 &
pid_mixed=$!

status_classic=0
status_mixed=0
wait "$pid_classic" || status_classic=$?
pid_classic=0
wait "$pid_mixed" || status_mixed=$?
pid_mixed=0

python3 tools/analyze-dummy-movement-traces.py \
  "$REPORT_ROOT/party-classic/traces/*.jsonl" \
  "$REPORT_ROOT/party-mixed/traces/*.jsonl" \
  --json-out "$REPORT_ROOT/movement-analysis.json" \
  --report-md "$REPORT_ROOT/movement-analysis.md" || true

python3 - <<'PY' "$REPORT_ROOT"
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
summary = {
    "reports": {},
    "total_loot": 0,
    "tiers": {},
    "workers_ok": 0,
    "workers_total": 0,
    "deaths": 0,
    "timeouts": 0,
    "movement_failures": 0,
}
for metrics_path in sorted(root.glob("party-*/metrics.csv")):
    rows = list(csv.DictReader(metrics_path.open(encoding="utf-8")))
    report = metrics_path.parent.name
    ok = sum(1 for row in rows if row.get("ok") == "true")
    summary["reports"][report] = {"ok": ok, "total": len(rows)}
    summary["workers_ok"] += ok
    summary["workers_total"] += len(rows)
    for row in rows:
        summary["total_loot"] += int(row.get("loot_acquired") or 0)
        summary["deaths"] += int(row.get("player_deaths") or 0)
        summary["timeouts"] += int(row.get("target_timeouts") or 0)
        summary["movement_failures"] += int(row.get("movement_failures") or 0)
        for key, value in row.items():
            if key.startswith("loot_tier_") and value:
                tier = key.removeprefix("loot_tier_")
                summary["tiers"][tier] = summary["tiers"].get(tier, 0) + int(value)
summary_path = root / "multiparty-summary.json"
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY

echo "classic_status=$status_classic"
echo "mixed_status=$status_mixed"
echo "report_root=$REPORT_ROOT"

if [[ "$status_classic" != "0" || "$status_mixed" != "0" ]]; then
  exit 1
fi
