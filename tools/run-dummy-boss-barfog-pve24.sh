#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${OPENDAOC_DUMMY_HOST:-192.168.0.42}"
PORT="${OPENDAOC_DUMMY_PORT:-10300}"
API_PORT="${OPENDAOC_DUMMY_API_PORT:-5000}"
BOSS_API_URL="${OPENDAOC_BOSS_API_URL:-http://127.0.0.1:${API_PORT}/api/dummy/combat/npcs}"
STAMP="$(date +%Y%m%d-%H%M%S)"
REPORT_ROOT="${1:-tools/reports/boss-barfog-pve24-${STAMP}}"
GROUND_Z_MAP="tools/pathing/heightmaps/region001_client_zones.json"
TARGET_NAME="${OPENDAOC_BOSS_TARGET_NAME:-king of the barfog hills}"
EXTRA_PARTIES="${OPENDAOC_BOSS_EXTRA_PARTIES:-0}"
HOLD="${OPENDAOC_BOSS_HOLD:-720}"
TARGET_TIMEOUT="${OPENDAOC_BOSS_TARGET_TIMEOUT:-660}"
MOVEMENT_SPEED="${OPENDAOC_DUMMY_MOVEMENT_SPEED:-165}"
SMOOTH_MOVE_INTERVAL="${OPENDAOC_DUMMY_SMOOTH_MOVE_INTERVAL:-0.25}"
MOVEMENT_UPDATE_INTERVAL="${OPENDAOC_DUMMY_MOVEMENT_UPDATE_INTERVAL:-0.25}"
PARTY_FOLLOW_STEP="${OPENDAOC_DUMMY_PARTY_FOLLOW_STEP:-260}"
ATTACK_RANGE="${OPENDAOC_BOSS_ATTACK_RANGE:-350}"
MELEE_RANGE_BUFFER="${OPENDAOC_BOSS_MELEE_RANGE_BUFFER:-250}"
MINIMUM_MELEE_STOP_DISTANCE="${OPENDAOC_BOSS_MINIMUM_MELEE_STOP_DISTANCE:-85}"
RANGED_STOP_DISTANCE="${OPENDAOC_BOSS_RANGED_STOP_DISTANCE:-1000}"
TARGET_FACE_COMMAND_INTERVAL="${OPENDAOC_BOSS_TARGET_FACE_COMMAND_INTERVAL:-0.8}"
TARGET_STICK_COMMAND_INTERVAL="${OPENDAOC_BOSS_TARGET_STICK_COMMAND_INTERVAL:-1.6}"
MIXED_DELAY="${OPENDAOC_BOSS_MIXED_DELAY:-0}"
SUPPORT_DELAY="${OPENDAOC_BOSS_SUPPORT_DELAY:-0}"
HEALWALL_DELAY="${OPENDAOC_BOSS_HEALWALL_DELAY:-0}"
RANGED_DELAY="${OPENDAOC_BOSS_RANGED_DELAY:-0}"
BOSS_API_MONITOR_INTERVAL="${OPENDAOC_BOSS_API_MONITOR_INTERVAL:-2}"
BOSS_API_MONITOR_FINAL_GRACE="${OPENDAOC_BOSS_API_MONITOR_FINAL_GRACE:-3}"
ENCOUNTER_LOG_INTERVAL="${OPENDAOC_BOSS_ENCOUNTER_LOG_INTERVAL:-2.0}"
ENCOUNTER_LOG_ATTACK_DECISIONS="${OPENDAOC_BOSS_ENCOUNTER_LOG_ATTACK_DECISIONS:-0}"
PARTY_FOCUS_TARGET_BACKOFF_DISTANCE="${OPENDAOC_BOSS_PARTY_FOCUS_TARGET_BACKOFF_DISTANCE:-1400}"
PARTY_FOCUS_TARGET_MAX_AGE="${OPENDAOC_BOSS_PARTY_FOCUS_TARGET_MAX_AGE:-6}"

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

MYSQL=(/home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb -h127.0.0.1 -uroot opendaoc)

MYSQL_PWD="$DB_PASS" "${MYSQL[@]}" <<'SQL'
UPDATE DOLCharacters
SET
  Region = 1,
  Xpos = CASE AccountName
    WHEN 'dummy040' THEN 443820 WHEN 'dummy300' THEN 443900 WHEN 'dummy041' THEN 443980 WHEN 'dummy042' THEN 444060
    WHEN 'dummy043' THEN 444140 WHEN 'dummy302' THEN 444220 WHEN 'dummy301' THEN 443860 WHEN 'dummy303' THEN 443940
    WHEN 'dummy400' THEN 444260 WHEN 'dummy401' THEN 444340 WHEN 'dummy402' THEN 444420 WHEN 'dummy403' THEN 444500
    WHEN 'dummy404' THEN 444580 WHEN 'dummy405' THEN 444660 WHEN 'dummy406' THEN 444740 WHEN 'dummy407' THEN 444820
    WHEN 'dummy408' THEN 444020 WHEN 'dummy409' THEN 444100 WHEN 'dummy410' THEN 444180 WHEN 'dummy411' THEN 444260
    WHEN 'dummy412' THEN 444340 WHEN 'dummy413' THEN 444420 WHEN 'dummy414' THEN 444500 WHEN 'dummy415' THEN 444580
    WHEN 'dummy416' THEN 443700 WHEN 'dummy417' THEN 443780 WHEN 'dummy418' THEN 443860 WHEN 'dummy419' THEN 443940
    WHEN 'dummy420' THEN 444020 WHEN 'dummy421' THEN 444100 WHEN 'dummy422' THEN 444180 WHEN 'dummy423' THEN 444260
    WHEN 'dummy424' THEN 444760 WHEN 'dummy425' THEN 444840 WHEN 'dummy426' THEN 444920 WHEN 'dummy427' THEN 445000
    WHEN 'dummy428' THEN 445080 WHEN 'dummy429' THEN 445160 WHEN 'dummy430' THEN 445240 WHEN 'dummy431' THEN 445320
    ELSE Xpos
  END,
  Ypos = CASE AccountName
    WHEN 'dummy040' THEN 377810 WHEN 'dummy300' THEN 377850 WHEN 'dummy041' THEN 377890 WHEN 'dummy042' THEN 377930
    WHEN 'dummy043' THEN 377970 WHEN 'dummy302' THEN 378010 WHEN 'dummy301' THEN 377900 WHEN 'dummy303' THEN 377940
    WHEN 'dummy400' THEN 378030 WHEN 'dummy401' THEN 378070 WHEN 'dummy402' THEN 378110 WHEN 'dummy403' THEN 378150
    WHEN 'dummy404' THEN 378190 WHEN 'dummy405' THEN 378230 WHEN 'dummy406' THEN 378270 WHEN 'dummy407' THEN 378310
    WHEN 'dummy408' THEN 377780 WHEN 'dummy409' THEN 377820 WHEN 'dummy410' THEN 377860 WHEN 'dummy411' THEN 377900
    WHEN 'dummy412' THEN 377940 WHEN 'dummy413' THEN 377980 WHEN 'dummy414' THEN 378020 WHEN 'dummy415' THEN 378060
    WHEN 'dummy416' THEN 377720 WHEN 'dummy417' THEN 377760 WHEN 'dummy418' THEN 377800 WHEN 'dummy419' THEN 377840
    WHEN 'dummy420' THEN 377880 WHEN 'dummy421' THEN 377920 WHEN 'dummy422' THEN 377960 WHEN 'dummy423' THEN 378000
    WHEN 'dummy424' THEN 378240 WHEN 'dummy425' THEN 378280 WHEN 'dummy426' THEN 378320 WHEN 'dummy427' THEN 378360
    WHEN 'dummy428' THEN 378400 WHEN 'dummy429' THEN 378440 WHEN 'dummy430' THEN 378480 WHEN 'dummy431' THEN 378520
    ELSE Ypos
  END,
  Zpos = CASE AccountName
    WHEN 'dummy040' THEN 6644 WHEN 'dummy300' THEN 6648 WHEN 'dummy041' THEN 6648 WHEN 'dummy042' THEN 6650
    WHEN 'dummy043' THEN 6654 WHEN 'dummy302' THEN 6659 WHEN 'dummy301' THEN 6647 WHEN 'dummy303' THEN 6650
    WHEN 'dummy400' THEN 6668 WHEN 'dummy401' THEN 6682 WHEN 'dummy402' THEN 6698 WHEN 'dummy403' THEN 6719
    WHEN 'dummy404' THEN 6742 WHEN 'dummy405' THEN 6764 WHEN 'dummy406' THEN 6786 WHEN 'dummy407' THEN 6809
    WHEN 'dummy408' THEN 6648 WHEN 'dummy409' THEN 6652 WHEN 'dummy410' THEN 6656 WHEN 'dummy411' THEN 6661
    WHEN 'dummy412' THEN 6668 WHEN 'dummy413' THEN 6678 WHEN 'dummy414' THEN 6690 WHEN 'dummy415' THEN 6706
    WHEN 'dummy416' THEN 6641 WHEN 'dummy417' THEN 6643 WHEN 'dummy418' THEN 6647 WHEN 'dummy419' THEN 6650
    WHEN 'dummy420' THEN 6652 WHEN 'dummy421' THEN 6654 WHEN 'dummy422' THEN 6658 WHEN 'dummy423' THEN 6663
    WHEN 'dummy424' THEN 6792 WHEN 'dummy425' THEN 6815 WHEN 'dummy426' THEN 6840 WHEN 'dummy427' THEN 6864
    WHEN 'dummy428' THEN 6888 WHEN 'dummy429' THEN 6912 WHEN 'dummy430' THEN 6936 WHEN 'dummy431' THEN 6960
    ELSE Zpos
  END,
  Health = 9999,
  Endurance = 10000,
  Mana = 9999,
  DeathTime = 0,
  DeathCount = 0,
  IsLevelSecondStage = 0,
  IsLevelRespecUsed = 0,
  SerializedSpecs = CASE AccountName
    WHEN 'dummy040' THEN 'Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13'
    WHEN 'dummy300' THEN 'Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1'
    WHEN 'dummy041' THEN 'Slash|1;Thrust|1;Crush|50;Dual Wield|50;Parry|28'
    WHEN 'dummy042' THEN 'Slash|1;Thrust|1;Crush|50;Dual Wield|50;Parry|28'
    WHEN 'dummy043' THEN 'Slash|1;Thrust|1;Crush|50;Dual Wield|50;Parry|28'
    WHEN 'dummy302' THEN 'Slash|1;Thrust|1;Crush|50;Dual Wield|50;Parry|28'
    WHEN 'dummy301' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy303' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy400' THEN 'Flexible|50;Shields|42;Soulrending|36;Parry|13'
    WHEN 'dummy401' THEN 'Enhancement|44;Rejuvenation|25;Parry|13;Staff|39'
    WHEN 'dummy402' THEN 'Stealth|35;Slash|35;Longbows|50'
    WHEN 'dummy403' THEN 'Fire Magic|50;Earth Magic|15;Cold Magic|10'
    WHEN 'dummy404' THEN 'Earth Magic|50;Cold Magic|15;Wind Magic|10'
    WHEN 'dummy405' THEN 'Matter Magic|46;Body Magic|28;Spirit Magic|4'
    WHEN 'dummy406' THEN 'Death Servant|50;Painworking|20;Deathsight|1'
    WHEN 'dummy407' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy408' THEN 'Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13'
    WHEN 'dummy409' THEN 'Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1'
    WHEN 'dummy410' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy411' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy412' THEN 'Enhancement|44;Rejuvenation|25;Parry|13;Staff|39'
    WHEN 'dummy413' THEN 'Fire Magic|50;Earth Magic|15;Cold Magic|10'
    WHEN 'dummy414' THEN 'Flexible|50;Shields|42;Soulrending|36;Parry|13'
    WHEN 'dummy415' THEN 'Matter Magic|46;Body Magic|28;Spirit Magic|4'
    WHEN 'dummy416' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy417' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy418' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy419' THEN 'Enhancement|44;Rejuvenation|25;Parry|13;Staff|39'
    WHEN 'dummy420' THEN 'Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13'
    WHEN 'dummy421' THEN 'Flexible|50;Shields|42;Soulrending|36;Parry|13'
    WHEN 'dummy422' THEN 'Fire Magic|50;Earth Magic|15;Cold Magic|10'
    WHEN 'dummy423' THEN 'Matter Magic|46;Body Magic|28;Spirit Magic|4'
    WHEN 'dummy424' THEN 'Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1'
    WHEN 'dummy425' THEN 'Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13'
    WHEN 'dummy426' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy427' THEN 'Smite|1;Rejuvenation|40;Enhancement|36'
    WHEN 'dummy428' THEN 'Enhancement|44;Rejuvenation|25;Parry|13;Staff|39'
    WHEN 'dummy429' THEN 'Fire Magic|50;Earth Magic|15;Cold Magic|10'
    WHEN 'dummy430' THEN 'Matter Magic|46;Body Magic|28;Spirit Magic|4'
    WHEN 'dummy431' THEN 'Death Servant|50;Painworking|20;Deathsight|1'
    ELSE SerializedSpecs
  END
WHERE AccountName IN (
  'dummy040','dummy300','dummy041','dummy042','dummy043','dummy302','dummy301','dummy303',
  'dummy400','dummy401','dummy402','dummy403','dummy404','dummy405','dummy406','dummy407',
  'dummy408','dummy409','dummy410','dummy411','dummy412','dummy413','dummy414','dummy415',
  'dummy416','dummy417','dummy418','dummy419','dummy420','dummy421','dummy422','dummy423',
  'dummy424','dummy425','dummy426','dummy427','dummy428','dummy429','dummy430','dummy431'
);
SQL

mkdir -p "$REPORT_ROOT/party-classic/traces" "$REPORT_ROOT/party-classic/encounter" \
  "$REPORT_ROOT/party-mixed/traces" "$REPORT_ROOT/party-mixed/encounter" \
  "$REPORT_ROOT/party-support/traces" "$REPORT_ROOT/party-support/encounter"
if [[ "$EXTRA_PARTIES" == "1" ]]; then
  mkdir -p "$REPORT_ROOT/party-healwall/traces" "$REPORT_ROOT/party-healwall/encounter" \
    "$REPORT_ROOT/party-ranged/traces" "$REPORT_ROOT/party-ranged/encounter"
fi

run_party() {
  local accounts="$1"
  local report_dir="$2"
  local rotations="$3"
  local encounter_args=(--encounter-log "$report_dir/encounter/{username}-{round}.jsonl" --encounter-log-interval "$ENCOUNTER_LOG_INTERVAL")
  if [[ "$ENCOUNTER_LOG_ATTACK_DECISIONS" == "1" || "${ENCOUNTER_LOG_ATTACK_DECISIONS,,}" == "true" || "${ENCOUNTER_LOG_ATTACK_DECISIONS,,}" == "yes" ]]; then
    encounter_args+=(--encounter-log-attack-decisions)
  fi

  PYTHONUNBUFFERED=1 python3 tools/behavior-dummy-client.py \
    --host "$HOST" \
    --port "$PORT" \
    --accounts "$accounts" \
    --concurrency 8 \
    --rounds 1 \
    --hold "$HOLD" \
    --timeout 8 \
    --ramp-up 0.4 \
    --ping-interval 10 \
    --position-heartbeat-interval 2.5 \
    --combat \
    --hunter \
    --combat-interval 0.35 \
    --move \
    --smooth-movement \
    --server-correction-smoothing \
    --movement-speed "$MOVEMENT_SPEED" \
    --smooth-move-interval "$SMOOTH_MOVE_INTERVAL" \
    --movement-update-interval "$MOVEMENT_UPDATE_INTERVAL" \
    --move-step 120 \
    --attack-range "$ATTACK_RANGE" \
    --melee-range-buffer "$MELEE_RANGE_BUFFER" \
    --minimum-melee-stop-distance "$MINIMUM_MELEE_STOP_DISTANCE" \
    --melee-stick-attack \
    --melee-stick-attack-distance 1400 \
    --ranged-stop-distance "$RANGED_STOP_DISTANCE" \
    --ground-z-map "$GROUND_Z_MAP" \
    --use-skills \
    --skill-interval 2.0 \
    --spell-levels 1,10,20,30,40,50 \
    --heal-spell-levels 1,10,20,30,40 \
    --action-rotation auto \
    --party-slot-rotations "$rotations" \
    --party-size 8 \
    --party-encounter-mode boss \
    --party-assist-only \
    --party-min-ready 8 \
    --party-form-up-delay 8 \
    --party-assist-interval 0.35 \
    --party-assist-attack-delay 0.2 \
    --party-rescue-aggro \
    --party-rescue-max-distance 1400 \
    --party-rescue-engaged-distance 250 \
    --party-rescue-cooldown 2 \
    --party-rescue-min-hold 5 \
    --party-rescue-max-age 8 \
    --party-rescue-objective-engaged-grace 20 \
    --party-invite-interval 5 \
    --party-accept-interval 2 \
    --party-follow-interval 0.6 \
    --party-follow-step "$PARTY_FOLLOW_STEP" \
    --party-follow-distance 250 \
    --boss-ranged-safe-distance 1000 \
    --party-focus-target-backoff \
    --party-focus-target-max-age "$PARTY_FOCUS_TARGET_MAX_AGE" \
    --party-focus-target-backoff-distance "$PARTY_FOCUS_TARGET_BACKOFF_DISTANCE" \
    --party-melee-survival-health-percent 0 \
    --party-heal-leader-interval 0.5 \
    --party-heal-leader-health-percent 99 \
    --party-buff-interval 12 \
    --party-buff-spell-levels 1,10,20,30,40 \
    --healer-self-health-percent 80 \
    --support-spell-chance 0 \
    --player-level 50 \
    --min-target-level 65 \
    --max-target-level 65 \
    --ideal-target-level 65 \
    --target-selection smart \
    --target-pool 1 \
    --max-target-distance 5500 \
    --target-timeout "$TARGET_TIMEOUT" \
    --target-failure-cooldown 10 \
    --target-failure-name-cooldown 15 \
    --stop-after-required-target-removed \
    --target-removed-loot-wait 5 \
    --target-face-command-interval "$TARGET_FACE_COMMAND_INTERVAL" \
    --target-stick-command-interval "$TARGET_STICK_COMMAND_INTERVAL" \
    --prefer-target-name "$TARGET_NAME" \
    --require-target-name "$TARGET_NAME" \
    --auto-loot \
    --required-target-api \
    --required-target-api-region 1 \
    --required-target-api-interval "$BOSS_API_MONITOR_INTERVAL" \
    --jitter 0.1 \
    --trace-movement-log "$report_dir/traces/{username}-{round}.jsonl" \
    "${encounter_args[@]}" \
    --metrics-csv "$report_dir/metrics.csv" \
    --combat-csv "$report_dir/combat.csv" \
    --report-md "$report_dir/report.md"
}

pid_classic=0
pid_mixed=0
pid_support=0
pid_healwall=0
pid_ranged=0
monitor_pid=0
cleanup() {
  if [[ "$pid_classic" != "0" ]]; then kill "$pid_classic" 2>/dev/null || true; fi
  if [[ "$pid_mixed" != "0" ]]; then kill "$pid_mixed" 2>/dev/null || true; fi
  if [[ "$pid_support" != "0" ]]; then kill "$pid_support" 2>/dev/null || true; fi
  if [[ "$pid_healwall" != "0" ]]; then kill "$pid_healwall" 2>/dev/null || true; fi
  if [[ "$pid_ranged" != "0" ]]; then kill "$pid_ranged" 2>/dev/null || true; fi
  if [[ "$monitor_pid" != "0" ]]; then kill "$monitor_pid" 2>/dev/null || true; fi
}
trap cleanup EXIT

python3 tools/monitor-boss-combat-api.py \
  --api-url "$BOSS_API_URL" \
  --name "$TARGET_NAME" \
  --region 1 \
  --interval "$BOSS_API_MONITOR_INTERVAL" \
  --out "$REPORT_ROOT/boss-api.jsonl" \
  > "$REPORT_ROOT/boss-api-monitor.log" 2>&1 &
monitor_pid=$!

run_party \
  "tools/dummy-party-albion-pve8.csv" \
  "$REPORT_ROOT/party-classic" \
  "melee-basic,melee-basic,melee-burst,melee-burst,melee-burst,melee-burst,healer-support,healer-support" \
  > "$REPORT_ROOT/party-classic/output.log" 2>&1 &
pid_classic=$!

sleep "$MIXED_DELAY"
run_party \
  "tools/dummy-party-albion-mixed-pve8.csv" \
  "$REPORT_ROOT/party-mixed" \
  "melee-basic,melee-burst,melee-basic,melee-burst,melee-burst,melee-burst,healer-support,healer-support" \
  > "$REPORT_ROOT/party-mixed/output.log" 2>&1 &
pid_mixed=$!

sleep "$SUPPORT_DELAY"
run_party \
  "tools/dummy-party-albion-boss-support-pve8.csv" \
  "$REPORT_ROOT/party-support" \
  "melee-basic,melee-basic,melee-burst,melee-burst,melee-burst,healer-support,healer-support,healer-support" \
  > "$REPORT_ROOT/party-support/output.log" 2>&1 &
pid_support=$!

if [[ "$EXTRA_PARTIES" == "1" ]]; then
  sleep "$HEALWALL_DELAY"
  run_party \
    "tools/dummy-party-albion-boss-healwall-pve8.csv" \
    "$REPORT_ROOT/party-healwall" \
    "melee-basic,healer-support,healer-support,healer-support,healer-support,melee-burst,caster-basic,caster-basic" \
    > "$REPORT_ROOT/party-healwall/output.log" 2>&1 &
  pid_healwall=$!

  sleep "$RANGED_DELAY"
  run_party \
    "tools/dummy-party-albion-boss-ranged-pve8.csv" \
    "$REPORT_ROOT/party-ranged" \
    "melee-basic,melee-basic,healer-support,healer-support,healer-support,caster-basic,caster-basic,caster-basic" \
    > "$REPORT_ROOT/party-ranged/output.log" 2>&1 &
  pid_ranged=$!
fi

status_classic=0
status_mixed=0
status_support=0
status_healwall=0
status_ranged=0
wait "$pid_classic" || status_classic=$?
pid_classic=0
wait "$pid_mixed" || status_mixed=$?
pid_mixed=0
wait "$pid_support" || status_support=$?
pid_support=0
if [[ "$EXTRA_PARTIES" == "1" ]]; then
  wait "$pid_healwall" || status_healwall=$?
  pid_healwall=0
  wait "$pid_ranged" || status_ranged=$?
  pid_ranged=0
fi
if [[ "$monitor_pid" != "0" ]]; then
  sleep "$BOSS_API_MONITOR_FINAL_GRACE"
  kill "$monitor_pid" 2>/dev/null || true
  wait "$monitor_pid" 2>/dev/null || true
  monitor_pid=0
fi

python3 tools/analyze-dummy-movement-traces.py \
  "$REPORT_ROOT/party-classic/traces/*.jsonl" \
  "$REPORT_ROOT/party-mixed/traces/*.jsonl" \
  "$REPORT_ROOT/party-support/traces/*.jsonl" \
  "$REPORT_ROOT/party-healwall/traces/*.jsonl" \
  "$REPORT_ROOT/party-ranged/traces/*.jsonl" \
  --json-out "$REPORT_ROOT/movement-analysis.json" \
  --report-md "$REPORT_ROOT/movement-analysis.md" || true

if compgen -G "$REPORT_ROOT/party-*/encounter/*.jsonl" > /dev/null || [[ -f "$REPORT_ROOT/boss-api.jsonl" ]]; then
  python3 tools/analyze-dummy-encounter-logs.py \
    "$REPORT_ROOT/party-*/encounter/*.jsonl" \
    "$REPORT_ROOT/boss-api.jsonl" \
    --json-out "$REPORT_ROOT/encounter-analysis.json" \
    --report-md "$REPORT_ROOT/encounter-analysis.md" || true
fi

python3 - <<'PY' "$REPORT_ROOT"
import csv
import json
import sys
from pathlib import Path

root = Path(sys.argv[1])
summary = {
    "reports": {},
    "workers_ok": 0,
    "workers_total": 0,
    "deaths": 0,
    "timeouts": 0,
    "target_removed": 0,
    "loot": 0,
    "tiers": {},
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
        summary["deaths"] += int(row.get("player_deaths") or 0)
        summary["timeouts"] += int(row.get("target_timeouts") or 0)
        summary["target_removed"] += int(row.get("target_removed") or 0)
        summary["loot"] += int(row.get("loot_acquired") or 0)
        summary["movement_failures"] += int(row.get("movement_failures") or 0)
        for key, value in row.items():
            if key.startswith("loot_tier_") and value:
                tier = key.removeprefix("loot_tier_")
                summary["tiers"][tier] = summary["tiers"].get(tier, 0) + int(value)

root.joinpath("boss-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(summary, ensure_ascii=False, indent=2))
PY

echo "classic_status=$status_classic"
echo "mixed_status=$status_mixed"
echo "support_status=$status_support"
echo "healwall_status=$status_healwall"
echo "ranged_status=$status_ranged"
echo "report_root=$REPORT_ROOT"

if [[ "$status_classic" != "0" || "$status_mixed" != "0" || "$status_support" != "0" || "$status_healwall" != "0" || "$status_ranged" != "0" ]]; then
  exit 1
fi
