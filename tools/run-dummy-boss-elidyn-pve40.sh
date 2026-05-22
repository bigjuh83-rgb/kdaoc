#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${OPENDAOC_DUMMY_HOST:-192.168.0.42}"
PORT="${OPENDAOC_DUMMY_PORT:-10300}"
API_PORT="${OPENDAOC_DUMMY_API_PORT:-5000}"
BOSS_API_URL="${OPENDAOC_BOSS_API_URL:-http://127.0.0.1:${API_PORT}/api/dummy/combat/npcs}"
STAMP="$(date +%Y%m%d-%H%M%S)"
REPORT_ROOT="${1:-tools/reports/boss-elidyn-pve40-${STAMP}}"
GROUND_Z_MAP="tools/pathing/heightmaps/region001_client_zones.json"
TARGET_NAME="${OPENDAOC_BOSS_TARGET_NAME:-Lord Elidyn}"
TARGET_LEVEL="${OPENDAOC_BOSS_TARGET_LEVEL:-59}"
START_REGION="${OPENDAOC_BOSS_START_REGION:-}"
START_X="${OPENDAOC_BOSS_START_X:-}"
START_Y="${OPENDAOC_BOSS_START_Y:-}"
START_Z="${OPENDAOC_BOSS_START_Z:-}"
REQUIRED_TARGET_HOME="${OPENDAOC_BOSS_TARGET_HOME:-}"
REQUIRED_TARGET_HOME_STOP_DISTANCE="${OPENDAOC_BOSS_TARGET_HOME_STOP_DISTANCE:-900}"
SEARCH_WAYPOINTS="${OPENDAOC_BOSS_SEARCH_WAYPOINTS:-}"
HOLD="${OPENDAOC_BOSS_HOLD:-720}"
TARGET_TIMEOUT="${OPENDAOC_BOSS_TARGET_TIMEOUT:-660}"
MOVEMENT_SPEED="${OPENDAOC_DUMMY_MOVEMENT_SPEED:-165}"
SMOOTH_MOVE_INTERVAL="${OPENDAOC_DUMMY_SMOOTH_MOVE_INTERVAL:-0.25}"
MOVEMENT_UPDATE_INTERVAL="${OPENDAOC_DUMMY_MOVEMENT_UPDATE_INTERVAL:-0.25}"
PARTY_FOLLOW_STEP="${OPENDAOC_DUMMY_PARTY_FOLLOW_STEP:-260}"
RANGED_STOP_DISTANCE="${OPENDAOC_BOSS_RANGED_STOP_DISTANCE:-1000}"
COMBAT_INTERVAL="${OPENDAOC_BOSS_COMBAT_INTERVAL:-0.35}"
PARTY_ASSIST_INTERVAL="${OPENDAOC_BOSS_PARTY_ASSIST_INTERVAL:-0.35}"
ATTACK_RANGE="${OPENDAOC_BOSS_ATTACK_RANGE:-350}"
MELEE_RANGE_BUFFER="${OPENDAOC_BOSS_MELEE_RANGE_BUFFER:-250}"
MINIMUM_MELEE_STOP_DISTANCE="${OPENDAOC_BOSS_MINIMUM_MELEE_STOP_DISTANCE:-85}"
MELEE_STICK_ATTACK="${OPENDAOC_BOSS_MELEE_STICK_ATTACK:-1}"
MELEE_STICK_ATTACK_DISTANCE="${OPENDAOC_BOSS_MELEE_STICK_ATTACK_DISTANCE:-1400}"
SUPPORT_SPELL_CHANCE="${OPENDAOC_BOSS_SUPPORT_SPELL_CHANCE:-0}"
RESCUE_MIN_HOLD="${OPENDAOC_BOSS_RESCUE_MIN_HOLD:-4}"
RESCUE_MAX_AGE="${OPENDAOC_BOSS_RESCUE_MAX_AGE:-14}"
RESCUE_ASSIST_AFTER="${OPENDAOC_BOSS_RESCUE_ASSIST_AFTER:-3}"
RESCUE_ENGAGED_DISTANCE="${OPENDAOC_BOSS_RESCUE_ENGAGED_DISTANCE:-350}"
RESCUE_OBJECTIVE_DISTANCE="${OPENDAOC_BOSS_RESCUE_OBJECTIVE_DISTANCE:-1800}"
RESCUE_AGGRO="${OPENDAOC_BOSS_RESCUE_AGGRO:-1}"
RESCUE_BEFORE_OBJECTIVE_ENGAGED="${OPENDAOC_BOSS_RESCUE_BEFORE_OBJECTIVE_ENGAGED:-1}"
CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE="${OPENDAOC_BOSS_CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE:-0}"
LOCAL_RESCUE="${OPENDAOC_BOSS_LOCAL_RESCUE:-1}"
LOCAL_RESCUE_MAX_DISTANCE="${OPENDAOC_BOSS_LOCAL_RESCUE_MAX_DISTANCE:-900}"
HEALER_LOCAL_RESCUE_HEALTH="${OPENDAOC_BOSS_HEALER_LOCAL_RESCUE_HEALTH:-35}"
BOSS_HAZARD_BACKOFF_DURATION="${OPENDAOC_BOSS_HAZARD_BACKOFF_DURATION:-9}"
BOSS_HAZARD_BACKOFF_DISTANCE="${OPENDAOC_BOSS_HAZARD_BACKOFF_DISTANCE:-2400}"
BOSS_NON_TANK_MELEE_BACKOFF="${OPENDAOC_BOSS_NON_TANK_MELEE_BACKOFF:-0}"
BOSS_NON_TANK_MELEE_BACKOFF_DISTANCE="${OPENDAOC_BOSS_NON_TANK_MELEE_BACKOFF_DISTANCE:-1000}"
PARTY_FOCUS_TARGET_BACKOFF="${OPENDAOC_BOSS_PARTY_FOCUS_TARGET_BACKOFF:-1}"
PARTY_FOCUS_TARGET_MAX_AGE="${OPENDAOC_BOSS_PARTY_FOCUS_TARGET_MAX_AGE:-6}"
PARTY_FOCUS_TARGET_BACKOFF_DISTANCE="${OPENDAOC_BOSS_PARTY_FOCUS_TARGET_BACKOFF_DISTANCE:-1400}"
PARTY_MELEE_SURVIVAL_HEALTH_PERCENT="${OPENDAOC_BOSS_PARTY_MELEE_SURVIVAL_HEALTH_PERCENT:-45}"
PARTY_MELEE_SURVIVAL_RESUME_HEALTH_PERCENT="${OPENDAOC_BOSS_PARTY_MELEE_SURVIVAL_RESUME_HEALTH_PERCENT:-80}"
PARTY_MELEE_SURVIVAL_BACKOFF_DURATION="${OPENDAOC_BOSS_PARTY_MELEE_SURVIVAL_BACKOFF_DURATION:-12}"
PARTY_SURVIVAL_DEATH_COUNT="${OPENDAOC_BOSS_PARTY_SURVIVAL_DEATH_COUNT:-2}"
PARTY_SURVIVAL_DEATH_WINDOW="${OPENDAOC_BOSS_PARTY_SURVIVAL_DEATH_WINDOW:-75}"
PARTY_SURVIVAL_TANK_HEALTH="${OPENDAOC_BOSS_PARTY_SURVIVAL_TANK_HEALTH:-35}"
PARTY_SURVIVAL_BACKOFF_DISTANCE="${OPENDAOC_BOSS_PARTY_SURVIVAL_BACKOFF_DISTANCE:-1000}"
USE_TARGET_FORMATION="${OPENDAOC_BOSS_USE_TARGET_FORMATION:-1}"
TARGET_START_COMMAND="${OPENDAOC_BOSS_TARGET_START_COMMAND:-}"
BOSS_API_MONITOR_INTERVAL="${OPENDAOC_BOSS_API_MONITOR_INTERVAL:-2}"
BOSS_API_MONITOR_FINAL_GRACE="${OPENDAOC_BOSS_API_MONITOR_FINAL_GRACE:-3}"
ENCOUNTER_LOG_INTERVAL="${OPENDAOC_BOSS_ENCOUNTER_LOG_INTERVAL:-2.0}"
ENCOUNTER_LOG_ATTACK_DECISIONS="${OPENDAOC_BOSS_ENCOUNTER_LOG_ATTACK_DECISIONS:-0}"
PARTY_SET="${OPENDAOC_BOSS_PARTY_SET:-all}"
TARGET_START_ARGS=()
if [[ -n "$TARGET_START_COMMAND" ]]; then
  TARGET_START_ARGS+=(--target-start-command "$TARGET_START_COMMAND")
fi

DB_PASS="$(
python3 - <<'PY'
import re
from pathlib import Path

config = Path("CoreServer/config/serverconfig.xml").read_text(encoding="utf-8")
print(re.search(r"Password=([^;]+)", config).group(1))
PY
)"

if [[ -z "$REQUIRED_TARGET_HOME" || -z "$START_REGION" || -z "$START_X" || -z "$START_Y" || -z "$START_Z" ]]; then
  TARGET_HOME_QUERY="$(
    python3 - <<'PY' "$TARGET_NAME"
import sys

target = sys.argv[1].strip().lower().replace("'", "''")
print(
    "SELECT Region,X,Y,Z FROM mob "
    f"WHERE LOWER(Name)=LOWER('{target}') "
    "ORDER BY Level DESC LIMIT 1;"
)
PY
  )"
  TARGET_HOME_ROW="$(
    MYSQL_PWD="$DB_PASS" /home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb -h127.0.0.1 -uroot opendaoc -N -B -e "$TARGET_HOME_QUERY" \
      | awk 'NF >= 4 {print $1","$2","$3","$4; exit}'
  )"
  if [[ -n "$TARGET_HOME_ROW" ]]; then
    IFS=',' read -r TARGET_REGION TARGET_X TARGET_Y TARGET_Z <<< "$TARGET_HOME_ROW"
    [[ -n "$REQUIRED_TARGET_HOME" ]] || REQUIRED_TARGET_HOME="$TARGET_X,$TARGET_Y,$TARGET_Z"
    [[ -n "$START_REGION" ]] || START_REGION="$TARGET_REGION"
    [[ -n "$START_X" ]] || START_X="$((TARGET_X + 1200))"
    [[ -n "$START_Y" ]] || START_Y="$((TARGET_Y + 1200))"
    [[ -n "$START_Z" ]] || START_Z="$TARGET_Z"
  fi
fi

START_REGION="${START_REGION:-1}"
START_X="${START_X:-566900}"
START_Y="${START_Y:-404050}"
START_Z="${START_Z:-5032}"
TARGET_HOME_X=""
TARGET_HOME_Y=""
TARGET_HOME_Z=""
if [[ -n "$REQUIRED_TARGET_HOME" ]]; then
  IFS=',' read -r TARGET_HOME_X TARGET_HOME_Y TARGET_HOME_Z <<< "$REQUIRED_TARGET_HOME"
fi

REQUIRED_TARGET_HOME_ARGS=()
if [[ -n "$REQUIRED_TARGET_HOME" ]]; then
  REQUIRED_TARGET_HOME_ARGS+=(--required-target-home "$REQUIRED_TARGET_HOME" --required-target-home-stop-distance "$REQUIRED_TARGET_HOME_STOP_DISTANCE")
fi
SEARCH_WAYPOINT_ARGS=()
if [[ -n "$SEARCH_WAYPOINTS" ]]; then
  SEARCH_WAYPOINT_ARGS+=(--waypoints "$SEARCH_WAYPOINTS" --waypoint-mode loop --waypoint-continuous-turns --waypoint-stop-distance "$REQUIRED_TARGET_HOME_STOP_DISTANCE" --waypoint-advance-distance "$((REQUIRED_TARGET_HOME_STOP_DISTANCE + 500))")
fi
RESCUE_AGGRO_ARGS=()
if [[ "$RESCUE_AGGRO" == "1" || "${RESCUE_AGGRO,,}" == "true" || "${RESCUE_AGGRO,,}" == "yes" ]]; then
  RESCUE_AGGRO_ARGS+=(--party-rescue-aggro)
fi
RESCUE_BEFORE_OBJECTIVE_ARGS=()
if [[ "$RESCUE_BEFORE_OBJECTIVE_ENGAGED" == "1" || "${RESCUE_BEFORE_OBJECTIVE_ENGAGED,,}" == "true" || "${RESCUE_BEFORE_OBJECTIVE_ENGAGED,,}" == "yes" ]]; then
  RESCUE_BEFORE_OBJECTIVE_ARGS+=(--party-rescue-before-objective-engaged)
fi
CLEAR_OBJECTIVE_ADDS_ARGS=()
if [[ "$CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE" == "1" || "${CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE,,}" == "true" || "${CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE,,}" == "yes" ]]; then
  CLEAR_OBJECTIVE_ADDS_ARGS+=(--party-clear-objective-adds-before-engage)
fi
LOCAL_RESCUE_ARGS=()
if [[ "$LOCAL_RESCUE" == "1" || "${LOCAL_RESCUE,,}" == "true" || "${LOCAL_RESCUE,,}" == "yes" ]]; then
  LOCAL_RESCUE_ARGS+=(--party-local-rescue-target --party-local-rescue-max-distance "$LOCAL_RESCUE_MAX_DISTANCE" --party-healer-local-rescue-health-percent "$HEALER_LOCAL_RESCUE_HEALTH")
fi
MELEE_STICK_ARGS=()
if [[ "$MELEE_STICK_ATTACK" == "1" || "${MELEE_STICK_ATTACK,,}" == "true" || "${MELEE_STICK_ATTACK,,}" == "yes" ]]; then
  MELEE_STICK_ARGS+=(--melee-stick-attack --melee-stick-attack-distance "$MELEE_STICK_ATTACK_DISTANCE")
fi
BOSS_NON_TANK_MELEE_ARGS=()
if [[ "$BOSS_NON_TANK_MELEE_BACKOFF" == "1" || "${BOSS_NON_TANK_MELEE_BACKOFF,,}" == "true" || "${BOSS_NON_TANK_MELEE_BACKOFF,,}" == "yes" ]]; then
  BOSS_NON_TANK_MELEE_ARGS+=(--party-boss-non-tank-melee-backoff --party-boss-non-tank-melee-backoff-distance "$BOSS_NON_TANK_MELEE_BACKOFF_DISTANCE")
fi
PARTY_FOCUS_TARGET_ARGS=()
if [[ "$PARTY_FOCUS_TARGET_BACKOFF" == "1" || "${PARTY_FOCUS_TARGET_BACKOFF,,}" == "true" || "${PARTY_FOCUS_TARGET_BACKOFF,,}" == "yes" ]]; then
  PARTY_FOCUS_TARGET_ARGS+=(--party-focus-target-backoff --party-focus-target-max-age "$PARTY_FOCUS_TARGET_MAX_AGE" --party-focus-target-backoff-distance "$PARTY_FOCUS_TARGET_BACKOFF_DISTANCE")
fi

python3 - <<'PY' "$START_REGION" "$START_X" "$START_Y" "$START_Z" "$TARGET_HOME_X" "$TARGET_HOME_Y" "$TARGET_HOME_Z" "$GROUND_Z_MAP" "$USE_TARGET_FORMATION" | MYSQL_PWD="$DB_PASS" /home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb -h127.0.0.1 -uroot opendaoc
import sys
from pathlib import Path

sys.path.insert(0, str(Path("tools").resolve()))
try:
    from daoc_zone_heightmap import ClientZoneHeightSampler
except Exception:
    ClientZoneHeightSampler = None
import sys

accounts = [
    "dummy040","dummy300","dummy041","dummy042","dummy043","dummy302","dummy301","dummy303",
    "dummy400","dummy401","dummy402","dummy403","dummy404","dummy405","dummy406","dummy407",
    "dummy408","dummy409","dummy410","dummy411","dummy412","dummy413","dummy414","dummy415",
    "dummy420","dummy416","dummy417","dummy418","dummy419","dummy421","dummy422","dummy423",
    "dummy425","dummy424","dummy426","dummy427","dummy428","dummy429","dummy430","dummy431",
]
specs = {
    "dummy040": "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13",
    "dummy300": "Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1",
    "dummy041": "Slash|1;Thrust|1;Crush|50;Dual Wield|50;Parry|28",
    "dummy042": "Slash|1;Thrust|1;Crush|50;Dual Wield|50;Parry|28",
    "dummy043": "Slash|1;Thrust|1;Crush|50;Dual Wield|50;Parry|28",
    "dummy302": "Slash|1;Thrust|1;Crush|50;Dual Wield|50;Parry|28",
    "dummy301": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy303": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy400": "Flexible|50;Shields|42;Soulrending|36;Parry|13",
    "dummy401": "Enhancement|44;Rejuvenation|25;Parry|13;Staff|39",
    "dummy402": "Stealth|35;Slash|35;Longbows|50",
    "dummy403": "Fire Magic|50;Earth Magic|15;Cold Magic|10",
    "dummy404": "Earth Magic|50;Cold Magic|15;Wind Magic|10",
    "dummy405": "Matter Magic|46;Body Magic|28;Spirit Magic|4",
    "dummy406": "Death Servant|50;Painworking|20;Deathsight|1",
    "dummy407": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy408": "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13",
    "dummy409": "Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1",
    "dummy410": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy411": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy412": "Enhancement|44;Rejuvenation|25;Parry|13;Staff|39",
    "dummy413": "Fire Magic|50;Earth Magic|15;Cold Magic|10",
    "dummy414": "Flexible|50;Shields|42;Soulrending|36;Parry|13",
    "dummy415": "Matter Magic|46;Body Magic|28;Spirit Magic|4",
    "dummy416": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy417": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy418": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy419": "Enhancement|44;Rejuvenation|25;Parry|13;Staff|39",
    "dummy420": "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13",
    "dummy421": "Flexible|50;Shields|42;Soulrending|36;Parry|13",
    "dummy422": "Fire Magic|50;Earth Magic|15;Cold Magic|10",
    "dummy423": "Matter Magic|46;Body Magic|28;Spirit Magic|4",
    "dummy424": "Slash|1;Thrust|1;Crush|50;Polearm|1;Shields|42;Two Handed|1;Parry|39;Crossbows|1",
    "dummy425": "Slash|39;Thrust|1;Crush|1;Two Handed|1;Chants|48;Shields|42;Parry|13",
    "dummy426": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy427": "Smite|1;Rejuvenation|40;Enhancement|36",
    "dummy428": "Enhancement|44;Rejuvenation|25;Parry|13;Staff|39",
    "dummy429": "Fire Magic|50;Earth Magic|15;Cold Magic|10",
    "dummy430": "Matter Magic|46;Body Magic|28;Spirit Magic|4",
    "dummy431": "Death Servant|50;Painworking|20;Deathsight|1",
}
region = int(sys.argv[1])
base_x = int(sys.argv[2])
base_y = int(sys.argv[3])
base_z = int(sys.argv[4])
target_x = int(sys.argv[5]) if sys.argv[5] else None
target_y = int(sys.argv[6]) if sys.argv[6] else None
target_z = int(sys.argv[7]) if sys.argv[7] else None
heightmap_path = Path(sys.argv[8]) if sys.argv[8] else None
use_target_formation = sys.argv[9].lower() in {"1", "true", "yes"}
sampler = None
if ClientZoneHeightSampler is not None and heightmap_path is not None and heightmap_path.exists():
    try:
        sampler = ClientZoneHeightSampler.from_config(heightmap_path)
    except Exception:
        sampler = None
target_offsets = [
    (-1249, -709), (-1169, -669), (-1089, -629), (-1009, -589), (-929, -549), (-849, -509), (-1209, -619), (-1129, -579),
    (-809, -489), (-729, -449), (-649, -409), (-569, -369), (-489, -329), (-409, -289), (-329, -249), (-249, -209),
    (-1049, -739), (-969, -699), (-889, -659), (-809, -619), (-729, -579), (-649, -539), (-569, -499), (-489, -459),
    (-1369, -799), (-1289, -759), (-1209, -719), (-1129, -679), (-1049, -639), (-969, -599), (-889, -559), (-809, -519),
    (-309, -279), (-229, -239), (-149, -199), (-69, -159), (11, -119), (91, -79), (171, -39), (251, 1),
]
rows = []
for index, account in enumerate(accounts):
    if use_target_formation and target_x is not None and target_y is not None:
        dx, dy = target_offsets[index % len(target_offsets)]
        x = target_x + dx
        y = target_y + dy
        z = target_z if target_z is not None else base_z
    else:
        col = index % 8
        row = index // 8
        x = base_x + col * 115
        y = base_y + row * 130
        z = base_z
    if sampler is not None:
        sampled_z = sampler.sample(x, y, region)
        if sampled_z is not None:
            z = sampled_z
    rows.append((account, x, y, z, specs[account]))

def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

print("USE opendaoc;")
print(f"UPDATE DOLCharacters SET Region={region},")
for column, offset in (("Xpos", 1), ("Ypos", 2), ("Zpos", 3)):
    print(f"{column}=CASE AccountName")
    for row in rows:
        print(f"WHEN {q(row[0])} THEN {row[offset]}")
    print(f"ELSE {column} END,")
print("Health=9999, Endurance=10000, Mana=9999, DeathTime=0, DeathCount=0,")
print("SerializedSpecs=CASE AccountName")
for account, _, _, _, spec in rows:
    print(f"WHEN {q(account)} THEN {q(spec)}")
print("ELSE SerializedSpecs END")
print("WHERE AccountName IN (" + ",".join(q(row[0]) for row in rows) + ");")
PY

should_run_party() {
  local party="$1"
  [[ "$PARTY_SET" == "all" || ",$PARTY_SET," == *",$party,"* ]]
}

run_party() {
  local accounts="$1"
  local report_dir="$2"
  local rotations="$3"
  local concurrency="${4:-8}"
  local party_size="${5:-8}"
  local party_min_ready="${6:-8}"
  local encounter_args=(--encounter-log "$report_dir/encounter/{username}-{round}.jsonl" --encounter-log-interval "$ENCOUNTER_LOG_INTERVAL")
  if [[ "$ENCOUNTER_LOG_ATTACK_DECISIONS" == "1" || "${ENCOUNTER_LOG_ATTACK_DECISIONS,,}" == "true" || "${ENCOUNTER_LOG_ATTACK_DECISIONS,,}" == "yes" ]]; then
    encounter_args+=(--encounter-log-attack-decisions)
  fi

  PYTHONUNBUFFERED=1 python3 tools/behavior-dummy-client.py \
    --host "$HOST" --port "$PORT" --accounts "$accounts" --concurrency "$concurrency" --rounds 1 --hold "$HOLD" --timeout 8 --ramp-up 0.35 \
    --ping-interval 10 --position-heartbeat-interval 2.5 --combat --hunter --combat-interval "$COMBAT_INTERVAL" \
    --move --smooth-movement --server-correction-smoothing --movement-speed "$MOVEMENT_SPEED" --smooth-move-interval "$SMOOTH_MOVE_INTERVAL" --movement-update-interval "$MOVEMENT_UPDATE_INTERVAL" \
    --move-step 120 --attack-range "$ATTACK_RANGE" --melee-range-buffer "$MELEE_RANGE_BUFFER" --minimum-melee-stop-distance "$MINIMUM_MELEE_STOP_DISTANCE" "${MELEE_STICK_ARGS[@]}" --ranged-stop-distance "$RANGED_STOP_DISTANCE" \
    --ground-z-map "$GROUND_Z_MAP" --use-skills --skill-interval 2.0 --spell-levels 1,10,20,30,40,50 --heal-spell-levels 1,10,20,30,40 --stationary-cast-actions --cast-action-hold 2.2 \
    --action-rotation auto --party-slot-rotations "$rotations" --party-size "$party_size" --party-encounter-mode boss --party-assist-only --party-min-ready "$party_min_ready" --party-form-up-delay 8 \
    --party-assist-interval "$PARTY_ASSIST_INTERVAL" --party-assist-attack-delay 0.2 "${RESCUE_AGGRO_ARGS[@]}" "${RESCUE_BEFORE_OBJECTIVE_ARGS[@]}" "${CLEAR_OBJECTIVE_ADDS_ARGS[@]}" "${LOCAL_RESCUE_ARGS[@]}" --party-rescue-max-distance 1400 --party-rescue-engaged-distance "$RESCUE_ENGAGED_DISTANCE" --party-rescue-objective-max-distance "$RESCUE_OBJECTIVE_DISTANCE" --party-rescue-cooldown 2 --party-rescue-min-hold "$RESCUE_MIN_HOLD" --party-rescue-max-age "$RESCUE_MAX_AGE" --party-rescue-objective-engaged-grace 20 --party-rescue-assist-after "$RESCUE_ASSIST_AFTER" --party-invite-interval 5 --party-accept-interval 2 \
    --party-follow-interval 0.6 --party-follow-step "$PARTY_FOLLOW_STEP" --party-follow-distance 250 --boss-ranged-safe-distance 1000 --boss-hazard-message-backoff-duration "$BOSS_HAZARD_BACKOFF_DURATION" --boss-hazard-message-backoff-distance "$BOSS_HAZARD_BACKOFF_DISTANCE" "${PARTY_FOCUS_TARGET_ARGS[@]}" "${BOSS_NON_TANK_MELEE_ARGS[@]}" --party-melee-survival-health-percent "$PARTY_MELEE_SURVIVAL_HEALTH_PERCENT" --party-melee-survival-resume-health-percent "$PARTY_MELEE_SURVIVAL_RESUME_HEALTH_PERCENT" --party-melee-survival-backoff-duration "$PARTY_MELEE_SURVIVAL_BACKOFF_DURATION" --party-survival-death-count "$PARTY_SURVIVAL_DEATH_COUNT" --party-survival-death-window "$PARTY_SURVIVAL_DEATH_WINDOW" --party-survival-active-tank-health-percent "$PARTY_SURVIVAL_TANK_HEALTH" --party-survival-backoff-distance "$PARTY_SURVIVAL_BACKOFF_DISTANCE" --party-heal-leader-interval 0.5 --party-heal-leader-health-percent 99 \
    --party-buff-interval 12 --party-buff-spell-levels 1,10,20,30,40 --healer-self-health-percent 80 --support-spell-chance "$SUPPORT_SPELL_CHANCE" --player-level 50 --min-target-level "$TARGET_LEVEL" --max-target-level "$TARGET_LEVEL" --ideal-target-level "$TARGET_LEVEL" \
    --target-selection smart --target-pool 1 --max-target-distance 5000 --target-timeout "$TARGET_TIMEOUT" --target-failure-cooldown 10 --target-failure-name-cooldown 15 --stop-after-required-target-removed --target-removed-loot-wait 5 \
    --prefer-target-name "$TARGET_NAME" --require-target-name "$TARGET_NAME" --auto-loot --jitter 0.1 \
    --required-target-api --required-target-api-region "$START_REGION" --required-target-api-interval "$BOSS_API_MONITOR_INTERVAL" \
    "${TARGET_START_ARGS[@]}" \
    "${REQUIRED_TARGET_HOME_ARGS[@]}" \
    "${SEARCH_WAYPOINT_ARGS[@]}" \
    --trace-movement-log "$report_dir/traces/{username}-{round}.jsonl" \
    "${encounter_args[@]}" \
    --metrics-csv "$report_dir/metrics.csv" --combat-csv "$report_dir/combat.csv" --report-md "$report_dir/report.md"
}

pids=()
monitor_pid=0
cleanup() {
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
  if [[ "$monitor_pid" != "0" ]]; then
    kill "$monitor_pid" 2>/dev/null || true
  fi
}
trap cleanup EXIT

mkdir -p "$REPORT_ROOT"
python3 tools/monitor-boss-combat-api.py \
  --api-url "$BOSS_API_URL" \
  --name "$TARGET_NAME" \
  --region "$START_REGION" \
  --interval "$BOSS_API_MONITOR_INTERVAL" \
  --out "$REPORT_ROOT/boss-api.jsonl" \
  > "$REPORT_ROOT/boss-api-monitor.log" 2>&1 &
monitor_pid=$!

if should_run_party classic; then
  mkdir -p "$REPORT_ROOT/party-classic/traces" "$REPORT_ROOT/party-classic/encounter"
  run_party tools/dummy-party-albion-pve8.csv "$REPORT_ROOT/party-classic" "melee-basic,melee-basic,melee-burst,melee-burst,melee-burst,melee-burst,healer-support,healer-support" > "$REPORT_ROOT/party-classic/output.log" 2>&1 & pids+=($!)
fi
if should_run_party mixed; then
  mkdir -p "$REPORT_ROOT/party-mixed/traces" "$REPORT_ROOT/party-mixed/encounter"
  run_party tools/dummy-party-albion-mixed-pve8.csv "$REPORT_ROOT/party-mixed" "melee-basic,melee-burst,melee-basic,caster-basic,caster-basic,caster-basic,caster-basic,healer-support" > "$REPORT_ROOT/party-mixed/output.log" 2>&1 & pids+=($!)
fi
if should_run_party support; then
  mkdir -p "$REPORT_ROOT/party-support/traces" "$REPORT_ROOT/party-support/encounter"
  run_party tools/dummy-party-albion-boss-support-pve8.csv "$REPORT_ROOT/party-support" "melee-basic,melee-basic,healer-support,healer-support,healer-support,caster-basic,melee-burst,caster-basic" > "$REPORT_ROOT/party-support/output.log" 2>&1 & pids+=($!)
fi
if should_run_party healwall; then
  mkdir -p "$REPORT_ROOT/party-healwall/traces" "$REPORT_ROOT/party-healwall/encounter"
  run_party tools/dummy-party-albion-boss-healwall-pve8.csv "$REPORT_ROOT/party-healwall" "melee-basic,healer-support,healer-support,healer-support,healer-support,melee-burst,caster-basic,caster-basic" > "$REPORT_ROOT/party-healwall/output.log" 2>&1 & pids+=($!)
fi
if should_run_party ranged; then
  mkdir -p "$REPORT_ROOT/party-ranged/traces" "$REPORT_ROOT/party-ranged/encounter"
  run_party tools/dummy-party-albion-boss-ranged-pve8.csv "$REPORT_ROOT/party-ranged" "melee-basic,melee-basic,healer-support,healer-support,healer-support,caster-basic,caster-basic,caster-basic" > "$REPORT_ROOT/party-ranged/output.log" 2>&1 & pids+=($!)
fi
if should_run_party raid; then
  mkdir -p "$REPORT_ROOT/party-raid/traces" "$REPORT_ROOT/party-raid/encounter"
  RAID_ACCOUNTS="$REPORT_ROOT/raid-accounts.csv"
  awk 'FNR == 1 && NR != 1 { next } { print }' \
    tools/dummy-party-albion-pve8.csv \
    tools/dummy-party-albion-mixed-pve8.csv \
    tools/dummy-party-albion-boss-support-pve8.csv \
    tools/dummy-party-albion-boss-healwall-pve8.csv \
    tools/dummy-party-albion-boss-ranged-pve8.csv \
    > "$RAID_ACCOUNTS"
  RAID_ROTATIONS="melee-basic,melee-basic,melee-burst,melee-burst,melee-burst,melee-burst,healer-support,healer-support,melee-basic,melee-burst,melee-basic,caster-basic,caster-basic,caster-basic,caster-basic,healer-support,melee-basic,melee-basic,healer-support,healer-support,healer-support,caster-basic,melee-burst,caster-basic,melee-basic,healer-support,healer-support,healer-support,healer-support,melee-burst,caster-basic,caster-basic,melee-basic,melee-basic,healer-support,healer-support,healer-support,caster-basic,caster-basic,caster-basic"
  run_party "$RAID_ACCOUNTS" "$REPORT_ROOT/party-raid" "$RAID_ROTATIONS" 40 40 40 > "$REPORT_ROOT/party-raid/output.log" 2>&1 & pids+=($!)
fi

if [[ "${#pids[@]}" -eq 0 ]]; then
  echo "No parties selected by OPENDAOC_BOSS_PARTY_SET='$PARTY_SET'." >&2
  exit 2
fi

status=0
for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done
pids=()
if [[ "$monitor_pid" != "0" ]]; then
  sleep "$BOSS_API_MONITOR_FINAL_GRACE"
  kill "$monitor_pid" 2>/dev/null || true
  wait "$monitor_pid" 2>/dev/null || true
  monitor_pid=0
fi

trace_files=("$REPORT_ROOT"/party-*/traces/*.jsonl)
if [[ -e "${trace_files[0]}" ]]; then
  python3 tools/analyze-dummy-movement-traces.py "${trace_files[@]}" --json-out "$REPORT_ROOT/movement-analysis.json" --report-md "$REPORT_ROOT/movement-analysis.md" || true
fi

if compgen -G "$REPORT_ROOT/party-*/encounter/*.jsonl" > /dev/null || [[ -f "$REPORT_ROOT/boss-api.jsonl" ]]; then
  python3 tools/analyze-dummy-encounter-logs.py \
    "$REPORT_ROOT/party-*/encounter/*.jsonl" \
    "$REPORT_ROOT/boss-api.jsonl" \
    --json-out "$REPORT_ROOT/encounter-analysis.json" \
    --report-md "$REPORT_ROOT/encounter-analysis.md" || true
fi

python3 tools/summarize-dummy-boss-report.py "$REPORT_ROOT"

echo "status=$status"
echo "report_root=$REPORT_ROOT"
exit "$status"
