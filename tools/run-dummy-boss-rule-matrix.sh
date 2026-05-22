#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

HOST="${OPENDAOC_DUMMY_HOST:-192.168.0.42}"
PORT="${OPENDAOC_DUMMY_PORT:-10300}"
API_PORT="${OPENDAOC_DUMMY_API_PORT:-5000}"
API_URL="${OPENDAOC_BOSS_API_URL:-http://127.0.0.1:${API_PORT}/api/dummy/combat/npcs}"
STAMP="$(date +%Y%m%d-%H%M%S)"
REPORT_ROOT="${1:-tools/reports/boss-rule-matrix-${STAMP}}"
GROUND_Z_MAP="tools/pathing/heightmaps/region001_client_zones.json"
HOLD="${OPENDAOC_MATRIX_HOLD:-150}"
TARGET_TIMEOUT="${OPENDAOC_MATRIX_TARGET_TIMEOUT:-170}"
ENCOUNTER_LOG_INTERVAL="${OPENDAOC_MATRIX_ENCOUNTER_LOG_INTERVAL:-2.0}"
API_MONITOR_INTERVAL="${OPENDAOC_MATRIX_API_MONITOR_INTERVAL:-1}"
COMBAT_INTERVAL="${OPENDAOC_MATRIX_COMBAT_INTERVAL:-0.35}"
PARTY_ASSIST_INTERVAL="${OPENDAOC_MATRIX_PARTY_ASSIST_INTERVAL:-0.35}"
RANGED_ASSIST_EXTRA_DELAY="${OPENDAOC_MATRIX_RANGED_ASSIST_EXTRA_DELAY:-0}"
PREENGAGE_RANGED_SAFE_DISTANCE="${OPENDAOC_MATRIX_PREENGAGE_RANGED_SAFE_DISTANCE:-0}"
BURN_REQUIRED_TARGET_HEALTH_PERCENT="${OPENDAOC_MATRIX_BURN_REQUIRED_TARGET_HEALTH_PERCENT:-0}"
FORCE_CASTER_RESCUE="${OPENDAOC_MATRIX_FORCE_CASTER_RESCUE:-}"
FORCE_SUPPORT_EVASION="${OPENDAOC_MATRIX_FORCE_SUPPORT_EVASION:-}"
CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE="${OPENDAOC_MATRIX_CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE:-0}"
ACTIVE_TANK_HANDOFF_HEALTH_PERCENT="${OPENDAOC_MATRIX_ACTIVE_TANK_HANDOFF_HEALTH_PERCENT:-0}"
BOSS_NON_TANK_MELEE_BACKOFF="${OPENDAOC_MATRIX_BOSS_NON_TANK_MELEE_BACKOFF:-0}"
SERVER_SNAPSHOT_RADIUS="${OPENDAOC_MATRIX_SERVER_SNAPSHOT_RADIUS:-5000}"
LOGIN_RETRIES="${OPENDAOC_MATRIX_LOGIN_RETRIES:-6}"
LOGIN_RETRY_DELAY="${OPENDAOC_MATRIX_LOGIN_RETRY_DELAY:-5}"
MATRIX_MODE="${OPENDAOC_MATRIX_MODE:-spread8}"
CASE_FILTER="${OPENDAOC_MATRIX_CASE_FILTER:-}"
MOVEMENT_SPEED="${OPENDAOC_DUMMY_MOVEMENT_SPEED:-165}"
SMOOTH_MOVE_INTERVAL="${OPENDAOC_DUMMY_SMOOTH_MOVE_INTERVAL:-0.25}"
MOVEMENT_UPDATE_INTERVAL="${OPENDAOC_DUMMY_MOVEMENT_UPDATE_INTERVAL:-0.25}"
START_OFFSET="${OPENDAOC_MATRIX_START_OFFSET:-1200}"
FORM_UP_DELAY="${OPENDAOC_MATRIX_FORM_UP_DELAY:-8}"
MELEE_STICK_DISTANCE="${OPENDAOC_MATRIX_MELEE_STICK_DISTANCE:-1400}"
CATCHUP_DISTANCE="${OPENDAOC_MATRIX_CATCHUP_DISTANCE:-0}"
CATCHUP_OFFSET="${OPENDAOC_MATRIX_CATCHUP_OFFSET:-250}"
SWEEP_POOL_COUNT="${OPENDAOC_MATRIX_SWEEP_POOL_COUNT:-100}"
SWEEP_PARTY_SIZE="${OPENDAOC_MATRIX_SWEEP_PARTY_SIZE:-8}"
SWEEP_PARTIES_PER_REALM="${OPENDAOC_MATRIX_SWEEP_PARTIES_PER_REALM:-12}"
SWEEP_SPEC_FILTER="${OPENDAOC_MATRIX_SWEEP_SPEC_FILTER:-}"
MAX_PARALLEL_CASES="${OPENDAOC_MATRIX_MAX_PARALLEL_CASES:-12}"
CASE_LAUNCH_STAGGER="${OPENDAOC_MATRIX_CASE_LAUNCH_STAGGER:-3}"
CASE_WAVE_COOLDOWN="${OPENDAOC_MATRIX_CASE_WAVE_COOLDOWN:-8}"
ISOLATE_BOSS_CLONES="${OPENDAOC_MATRIX_ISOLATE_BOSS_CLONES:-1}"
CLONE_GRID_SPACING="${OPENDAOC_MATRIX_CLONE_GRID_SPACING:-6500}"
CLONE_DENSITY_PROFILE="${OPENDAOC_MATRIX_CLONE_DENSITY_PROFILE:-dense}"
CLONE_MIN_SOURCE_DISTANCE="${OPENDAOC_MATRIX_CLONE_MIN_SOURCE_DISTANCE:-2600}"
CLONE_MIN_TEST_DISTANCE="${OPENDAOC_MATRIX_CLONE_MIN_TEST_DISTANCE:-9000}"
CLONE_NEARBY_RADIUS="${OPENDAOC_MATRIX_CLONE_NEARBY_RADIUS:-2600}"
RESCUE_MAX_AGE="${OPENDAOC_MATRIX_RESCUE_MAX_AGE:-14}"
RESCUE_EMERGENCY_ASSIST_AFTER="${OPENDAOC_MATRIX_RESCUE_EMERGENCY_ASSIST_AFTER:-0}"

DB_PASS="$(
python3 - <<'PY'
import re
from pathlib import Path

config = Path("CoreServer/config/serverconfig.xml").read_text(encoding="utf-8")
print(re.search(r"Password=([^;]+)", config).group(1))
PY
)"

query_target_home() {
  local target_name="$1"
  python3 - <<'PY' "$target_name" | MYSQL_PWD="$DB_PASS" /home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb -h127.0.0.1 -uroot opendaoc -N -B
import sys

target = sys.argv[1].replace("'", "''")
print(
    "SELECT Region,X,Y,Z,Level FROM mob "
    f"WHERE LOWER(Name)=LOWER('{target}') "
    "ORDER BY Level DESC LIMIT 1;"
)
PY
}

query_target_live() {
  local target_name="$1"
  local region="$2"
  local fallback_level="$3"
  python3 - <<'PY' "$API_URL" "$target_name" "$region" "$fallback_level"
import json
import sys
import urllib.parse
import urllib.request

api_url, target_name, region_s, fallback_level = sys.argv[1:5]
query = {"limit": "20", "name": target_name, "region": region_s}
separator = "&" if "?" in api_url else "?"
url = api_url + separator + urllib.parse.urlencode(query)

try:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=2.0) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception:
    raise SystemExit(0)

if isinstance(payload, list):
    items = [item for item in payload if isinstance(item, dict)]
elif isinstance(payload, dict):
    items = []
    for key in ("items", "npcs", "results"):
        if isinstance(payload.get(key), list):
            items = [item for item in payload[key] if isinstance(item, dict)]
            break
    if not items:
        items = [payload]
else:
    items = []

lowered = target_name.lower()
matches = [item for item in items if str(item.get("name", "")).lower() == lowered]
if not matches:
    matches = [item for item in items if lowered in str(item.get("name", "")).lower()]
if not matches and items:
    matches = [items[0]]
if not matches:
    raise SystemExit(0)

item = matches[0]
try:
    if not bool(item.get("isAlive", True)):
        raise ValueError
    region = int(item.get("region", region_s))
    x = int(item["x"])
    y = int(item["y"])
    z = int(item["z"])
    level = int(item.get("level", fallback_level))
except Exception:
    raise SystemExit(0)

print(f"{region}\t{x}\t{y}\t{z}\t{level}")
PY
}

delete_test_boss_clones() {
  python3 - <<'PY' "$API_PORT"
import sys
import urllib.error
import urllib.request

api_port = sys.argv[1]
url = f"http://127.0.0.1:{api_port}/api/dummy/combat/test-clones?prefix=KDAOC_TEST_"
request = urllib.request.Request(url, method="DELETE")
try:
    with urllib.request.urlopen(request, timeout=3.0) as response:
        response.read()
except urllib.error.HTTPError as exc:
    raise SystemExit(f"failed to delete test boss clones: HTTP {exc.code}")
except Exception as exc:
    raise SystemExit(f"failed to delete test boss clones: {exc}")
PY
}

clone_target_for_case() {
  local case_name="$1"
  local source_name="$2"
  local source_row="$3"

  python3 - <<'PY' "$API_PORT" "$case_name" "$source_name" "$source_row" "$GROUND_Z_MAP" "$CLONE_GRID_SPACING" "$CLONE_DENSITY_PROFILE" "$CLONE_MIN_SOURCE_DISTANCE" "$CLONE_MIN_TEST_DISTANCE" "$CLONE_NEARBY_RADIUS"
import json
import sys
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path("tools").resolve()))
try:
    from daoc_zone_heightmap import ClientZoneHeightSampler
except Exception:
    ClientZoneHeightSampler = None

api_port, case_name, source_name, source_row, heightmap_s, spacing_s, density_profile, min_source_distance_s, min_test_distance_s, nearby_radius_s = sys.argv[1:11]
region_s, x_s, y_s, z_s, level_s = source_row.split("\t")
region = int(region_s)
source_x = int(x_s)
source_y = int(y_s)
source_z = int(z_s)
level = int(level_s)
spacing = int(spacing_s)
min_source_distance = int(min_source_distance_s)
min_test_distance = int(min_test_distance_s)
nearby_radius = max(0, int(nearby_radius_s))

heightmap_path = Path(heightmap_s)
sampler = None
if ClientZoneHeightSampler is not None and heightmap_path.exists():
    try:
        sampler = ClientZoneHeightSampler.from_config(heightmap_path)
    except Exception:
        sampler = None

clone_name = "KDAOC_TEST_" + "".join(ch if ch.isalnum() else "_" for ch in case_name)[:48]

slot = sum((index + 1) * ord(ch) for index, ch in enumerate(case_name))
base_candidates = [
    (-1, -1), (1, 1), (-1, 1), (1, -1),
    (-1, 0), (1, 0), (0, -1), (0, 1),
    (-2, 0), (2, 0), (0, -2), (0, 2),
    (-2, -1), (2, 1), (-2, 1), (2, -1),
    (0, 0),
]
base_candidates = base_candidates[slot % len(base_candidates):] + base_candidates[:slot % len(base_candidates)]
if density_profile == "clean":
    spacing_candidates = [spacing, max(3200, spacing // 2), 3200, 2200]
elif density_profile == "mixed":
    spacing_candidates = [spacing, max(3200, spacing // 2), 2200, 1400, 800, 0]
else:
    spacing_candidates = [1400, 800, 2200, 0, max(3200, spacing // 2), spacing]
errors = []
payload = None

def sample_z(x: int, y: int, fallback: int) -> int:
    if sampler is None:
        return fallback

    try:
        zone_id = find_zone_id(x, y)
        sampled_z = sampler.sample(x, y, zone_id) if zone_id is not None else None
        if sampled_z is not None:
            return int(sampled_z)
    except Exception:
        pass

    return fallback


def find_zone_id(x: int, y: int) -> int | None:
    if sampler is None:
        return None

    for zone_id, zone in sampler.zones.items():
        if (
            zone.world_x <= x < zone.world_x + zone.world_width
            and zone.world_y <= y < zone.world_y + zone.world_height
        ):
            return int(zone_id)

    return None


def formation_offsets(total: int, offset: int) -> list[tuple[int, int]]:
    result = []
    columns = 4 if total <= 8 else 5
    spacing_x = 170 if total <= 8 else 220
    spacing_y = 240 if total <= 8 else 260

    for index in range(total):
        row = index // columns
        col = index % columns
        centered_col = col - (columns - 1) / 2.0
        stagger = 80 if row % 2 else 0
        result.append((-offset + int(centered_col * spacing_x) + stagger, -offset + row * spacing_y))

    return result


def terrain_is_suitable(x: int, y: int, z: int) -> tuple[bool, int, str]:
    if sampler is None:
        return True, z, "no-sampler"

    if find_zone_id(x, y) is None:
        return True, z, "no-known-zone"

    probe_points = [(x, y)]
    probe_points.extend((x + dx, y + dy) for dx, dy in formation_offsets(16, 1200))
    samples = []
    for px, py in probe_points:
        zone_id = find_zone_id(px, py)
        if zone_id is None:
            continue

        sampled = sampler.sample(px, py, zone_id)
        if sampled is None:
            return False, z, f"missing-z:{px}:{py}:zone{zone_id}"

        samples.append(int(sampled))

    if not samples:
        return True, z, "no-known-zone-samples"

    low = min(samples)
    high = max(samples)
    median = sorted(samples)[len(samples) // 2]

    if high - low > 900 or abs(z - median) > 650:
        return False, median, f"uneven:{low}:{high}:{median}"

    return True, z, f"ok:{low}:{high}:{median}"


def active_test_clone_positions() -> list[tuple[str, int, int]]:
    query = urllib.parse.urlencode({"name": "KDAOC_TEST_", "region": str(region), "limit": "500"})
    url = f"http://127.0.0.1:{api_port}/api/dummy/combat/npcs?{query}"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=2.0) as response:
            loaded = json.loads(response.read().decode("utf-8"))
    except Exception:
        return []

    if isinstance(loaded, list):
        items = loaded
    elif isinstance(loaded, dict):
        items = next((loaded[key] for key in ("items", "npcs", "results") if isinstance(loaded.get(key), list)), [])
    else:
        items = []

    positions = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "") or "")
        if not name.startswith("KDAOC_TEST_") or not bool(item.get("isAlive", True)):
            continue
        try:
            positions.append((name, int(item["x"]), int(item["y"])))
        except Exception:
            continue
    return positions


test_clone_positions = active_test_clone_positions()

for candidate_spacing in spacing_candidates:
    for grid_x, grid_y in base_candidates:
        x = source_x + grid_x * candidate_spacing
        y = source_y + grid_y * candidate_spacing
        source_distance = ((x - source_x) ** 2 + (y - source_y) ** 2) ** 0.5
        if source_distance < min_source_distance:
            errors.append(f"source-distance:{x},{y}:{source_distance:.0f}<min{min_source_distance}")
            continue
        if min_test_distance > 0:
            too_close_clone = next(
                (
                    (name, clone_distance)
                    for name, clone_x, clone_y in test_clone_positions
                    for clone_distance in [((x - clone_x) ** 2 + (y - clone_y) ** 2) ** 0.5]
                    if clone_distance < min_test_distance
                ),
                None,
            )
            if too_close_clone is not None:
                errors.append(
                    f"test-clone-distance:{x},{y}:{too_close_clone[0]}:{too_close_clone[1]:.0f}<min{min_test_distance}"
                )
                continue
        z = sample_z(x, y, source_z)
        terrain_ok, adjusted_z, terrain_reason = terrain_is_suitable(x, y, z)
        if not terrain_ok:
            errors.append(f"terrain:{x},{y},{z}:{terrain_reason}")
            continue
        z = adjusted_z

        query = urllib.parse.urlencode({
            "source": source_name,
            "name": clone_name,
            "region": str(region),
            "x": str(x),
            "y": str(y),
            "z": str(z),
            "level": str(level),
            "nearbyRadius": str(nearby_radius),
        })
        url = f"http://127.0.0.1:{api_port}/api/dummy/combat/clone-npc?{query}"
        request = urllib.request.Request(url, method="POST", headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=5.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            errors.append(f"{exc.code}:{x},{y},{z}:{body[:160]}")
        except Exception as exc:
            errors.append(f"{type(exc).__name__}:{x},{y},{z}:{exc}")
    if payload is not None:
        break

if payload is None:
    raise SystemExit("clone failed: " + " | ".join(errors[-8:]))

print(
    f"{int(payload.get('region', region))}\t"
    f"{int(payload.get('x', x))}\t"
    f"{int(payload.get('y', y))}\t"
    f"{int(payload.get('z', z))}\t"
    f"{int(payload.get('level', level))}\t"
    f"{payload.get('name', clone_name)}"
)
PY
}

prepare_party_at_target() {
  local accounts_csv="$1"
  local target_name="$2"
  local target_row="$3"
  local start_offset="${4:-1200}"
  local positioned_csv="${5:-}"

  python3 - <<'PY' "$accounts_csv" "$target_name" "$target_row" "$start_offset" "$GROUND_Z_MAP" "$positioned_csv" \
    | MYSQL_PWD="$DB_PASS" /home/bigjuh/.local/opendaoc-mariadb/current/bin/mariadb -h127.0.0.1 -uroot opendaoc
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path("tools").resolve()))
try:
    from daoc_zone_heightmap import ClientZoneHeightSampler
except Exception:
    ClientZoneHeightSampler = None

accounts_csv = Path(sys.argv[1])
target_name = sys.argv[2]
region_s, x_s, y_s, z_s, _level_s = sys.argv[3].split("\t")
offset = int(sys.argv[4])
heightmap_path = Path(sys.argv[5])
positioned_csv = Path(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[6] else None
region = int(region_s)
target_x = int(x_s)
target_y = int(y_s)
target_z = int(z_s)
sampler = None
if ClientZoneHeightSampler is not None and heightmap_path.exists():
    try:
        sampler = ClientZoneHeightSampler.from_config(heightmap_path)
    except Exception:
        sampler = None

with accounts_csv.open(newline="", encoding="utf-8") as handle:
    account_rows = list(csv.DictReader(handle))
    accounts = [row["username"] for row in account_rows]

def formation_offset(index: int, total: int, offset: int) -> tuple[int, int]:
    if total <= 8:
        columns = 4
        spacing_x = 170
        spacing_y = 240
    else:
        columns = 5
        spacing_x = 220
        spacing_y = 260

    row = index // columns
    col = index % columns
    centered_col = col - (columns - 1) / 2.0
    stagger = 80 if row % 2 else 0
    dx = -offset + int(centered_col * spacing_x) + stagger
    dy = -offset + row * spacing_y
    return dx, dy

def find_zone_id(x: int, y: int) -> int | None:
    if sampler is None:
        return None

    for zone_id, zone in sampler.zones.items():
        if (
            zone.world_x <= x < zone.world_x + zone.world_width
            and zone.world_y <= y < zone.world_y + zone.world_height
        ):
            return int(zone_id)

    return None

rows = []
for index, account in enumerate(accounts):
    dx, dy = formation_offset(index, len(accounts), offset)
    x = target_x + dx
    y = target_y + dy
    z = target_z
    if sampler is not None:
        zone_id_for_sample = find_zone_id(x, y)
        sampled_z = sampler.sample(x, y, zone_id_for_sample) if zone_id_for_sample is not None else None
        if sampled_z is not None:
            z = sampled_z
    zone_id = 0
    zone_x = x // 8192
    zone_y = y // 8192
    # Region-local zone IDs follow the database zone offset grid.
    # Use a deterministic lookup query in the generated SQL result set.
    rows.append((account, x, y, z, zone_x, zone_y, zone_id))

def q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

if positioned_csv is not None:
    positioned_csv.parent.mkdir(parents=True, exist_ok=True)
    zone_ids = {}
    with positioned_csv.open("w", newline="", encoding="utf-8") as out:
        fieldnames = list(account_rows[0].keys()) if account_rows else ["username", "password", "realm", "char_index"]
        for field in ["start_x", "start_y", "start_z", "zone_id"]:
            if field not in fieldnames:
                fieldnames.append(field)
        writer = csv.DictWriter(out, fieldnames=fieldnames)
        writer.writeheader()
        for source, row in zip(account_rows, rows):
            output_row = dict(source)
            output_row.update({
                "start_x": row[1],
                "start_y": row[2],
                "start_z": row[3],
                "zone_id": "",
            })
            writer.writerow(output_row)

print("USE opendaoc;")
print("DROP TEMPORARY TABLE IF EXISTS tmp_dummy_zone_lookup;")
print("CREATE TEMPORARY TABLE tmp_dummy_zone_lookup (AccountName varchar(255), ZoneID int);")
for row in rows:
    print(
        "INSERT INTO tmp_dummy_zone_lookup "
        f"SELECT {q(row[0])}, COALESCE((SELECT ZoneID FROM zones WHERE RegionID={region} "
        f"AND OffsetX <= {row[4]} AND {row[4]} < OffsetX + Width "
        f"AND OffsetY <= {row[5]} AND {row[5]} < OffsetY + Height "
        "ORDER BY ZoneID LIMIT 1), 0);"
    )
print(f"UPDATE DOLCharacters SET Region={region},")
for column, value_index in (("Xpos", 1), ("Ypos", 2), ("Zpos", 3)):
    print(f"{column}=CASE AccountName")
    for row in rows:
        print(f"WHEN {q(row[0])} THEN {row[value_index]}")
    print(f"ELSE {column} END,")
print("Health=9999, Endurance=10000, Mana=9999, DeathTime=0, DeathCount=0")
print("WHERE AccountName IN (" + ",".join(q(row[0]) for row in rows) + ");")
if positioned_csv is not None:
    print("SELECT AccountName,ZoneID FROM tmp_dummy_zone_lookup;")
PY
}

slice_accounts_csv() {
  local source_csv="$1"
  local start_index="$2"
  local count="$3"
  local output_csv="$4"

  python3 - <<'PY' "$source_csv" "$start_index" "$count" "$output_csv"
import csv
import sys
from pathlib import Path

source = Path(sys.argv[1])
start = int(sys.argv[2])
count = int(sys.argv[3])
output = Path(sys.argv[4])

if not source.exists():
    raise SystemExit(f"missing account pool: {source}")

with source.open(newline="", encoding="utf-8") as handle:
    rows = list(csv.DictReader(handle))
    fieldnames = handle.readline()

selected = rows[start:start + count]
if len(selected) < count:
    raise SystemExit(f"account pool {source} has only {len(rows)} rows; need slice {start}:{start + count}")

output.parent.mkdir(parents=True, exist_ok=True)
with output.open("w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(selected[0].keys()))
    writer.writeheader()
    writer.writerows(selected)
PY
}

run_case() {
  local case_name="$1"
  local target_name="$2"
  local target_level="$3"
  local accounts_csv="$4"
  local rotations="$5"
  local rescue_objective_distance="$6"
  local rescue_assist_after="$7"
  local local_rescue="$8"
  local caster_rescue="$9"
  local support_evasion="${10}"
  local party_size="${11:-8}"
  local concurrency="${12:-$party_size}"
  if [[ -n "$FORCE_CASTER_RESCUE" ]]; then
    caster_rescue="$FORCE_CASTER_RESCUE"
  fi
  if [[ -n "$FORCE_SUPPORT_EVASION" ]]; then
    support_evasion="$FORCE_SUPPORT_EVASION"
  fi

  local db_target_row
  db_target_row="$(query_target_home "$target_name" | awk 'NF >= 5 {print $1"\t"$2"\t"$3"\t"$4"\t"$5; exit}')"
  if [[ -z "$db_target_row" ]]; then
    echo "missing target: $target_name" >&2
    return 2
  fi

  local region target_x target_y target_z actual_level
  IFS=$'\t' read -r region target_x target_y target_z actual_level <<< "$db_target_row"
  local live_target_row
  live_target_row="$(query_target_live "$target_name" "$region" "$actual_level" | awk 'NF >= 5 {print $1"\t"$2"\t"$3"\t"$4"\t"$5; exit}')"
  local target_row="$db_target_row"
  local target_source="db"
  if [[ -n "$live_target_row" ]]; then
    target_row="$live_target_row"
    target_source="api"
    IFS=$'\t' read -r region target_x target_y target_z actual_level <<< "$target_row"
  fi
  local source_target_name="$target_name"
  if [[ "$ISOLATE_BOSS_CLONES" == "1" ]]; then
    local cloned_target_row
    cloned_target_row="$(clone_target_for_case "$case_name" "$source_target_name" "$target_row" | awk 'NF >= 6 {print $1"\t"$2"\t"$3"\t"$4"\t"$5"\t"$6; exit}')"
    if [[ -z "$cloned_target_row" ]]; then
      echo "failed to clone target: $source_target_name for $case_name" >&2
      return 3
    fi
    local cloned_target_name
    IFS=$'\t' read -r region target_x target_y target_z actual_level cloned_target_name <<< "$cloned_target_row"
    target_name="$cloned_target_name"
    target_row="${region}"$'\t'"${target_x}"$'\t'"${target_y}"$'\t'"${target_z}"$'\t'"${actual_level}"
    target_source="clone:$source_target_name"
  fi
  local report_dir="$REPORT_ROOT/$case_name"
  mkdir -p "$report_dir/traces" "$report_dir/encounter"
  local positioned_accounts_csv="$report_dir/accounts-positioned.csv"
  local zone_ids_tsv="$report_dir/zone-ids.tsv"
  prepare_party_at_target "$accounts_csv" "$target_name" "$target_row" "$START_OFFSET" "$positioned_accounts_csv" > "$zone_ids_tsv"
  python3 - <<'PY' "$positioned_accounts_csv" "$zone_ids_tsv"
import csv
import sys

csv_path = sys.argv[1]
zone_path = sys.argv[2]
zone_by_account = {}
with open(zone_path, encoding="utf-8") as handle:
    for line in handle:
        parts = line.rstrip("\n").split("\t")
        if len(parts) == 2 and parts[0] != "AccountName":
            zone_by_account[parts[0]] = parts[1]

if not zone_by_account:
    raise SystemExit(0)

with open(csv_path, newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    rows = list(reader)
    fieldnames = list(reader.fieldnames or [])

for row in rows:
    row["zone_id"] = zone_by_account.get(row["username"], row.get("zone_id", ""))

with open(csv_path, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
PY

  {
    printf 'case\t%s\n' "$case_name"
    printf 'target\t%s\n' "$target_name"
    printf 'source_target\t%s\n' "$source_target_name"
    printf 'target_level\t%s\n' "$target_level"
    printf 'actual_level\t%s\n' "$actual_level"
    printf 'target_source\t%s\n' "$target_source"
    printf 'target_home\t%s,%s,%s,%s\n' "$region" "$target_x" "$target_y" "$target_z"
    printf 'start_offset\t%s\n' "$START_OFFSET"
    printf 'form_up_delay\t%s\n' "$FORM_UP_DELAY"
    printf 'movement_speed\t%s\n' "$MOVEMENT_SPEED"
    printf 'melee_stick_distance\t%s\n' "$MELEE_STICK_DISTANCE"
    printf 'catchup_distance\t%s\n' "$CATCHUP_DISTANCE"
    printf 'catchup_offset\t%s\n' "$CATCHUP_OFFSET"
    printf 'accounts\t%s\n' "$accounts_csv"
    printf 'positioned_accounts\t%s\n' "$positioned_accounts_csv"
    printf 'rotations\t%s\n' "$rotations"
    printf 'rescue_objective_distance\t%s\n' "$rescue_objective_distance"
    printf 'rescue_assist_after\t%s\n' "$rescue_assist_after"
    printf 'local_rescue\t%s\n' "$local_rescue"
    printf 'caster_rescue\t%s\n' "$caster_rescue"
    printf 'support_evasion\t%s\n' "$support_evasion"
    printf 'clone_density_profile\t%s\n' "$CLONE_DENSITY_PROFILE"
    printf 'clone_min_source_distance\t%s\n' "$CLONE_MIN_SOURCE_DISTANCE"
    printf 'clone_nearby_radius\t%s\n' "$CLONE_NEARBY_RADIUS"
  } > "$report_dir/matrix.tsv"

  local local_rescue_args=()
  if [[ "$local_rescue" == "1" ]]; then
    local_rescue_args+=(--party-local-rescue-target --party-local-rescue-max-distance 900 --party-healer-local-rescue-health-percent 35)
  fi
  local caster_rescue_args=()
  if [[ "$caster_rescue" == "1" ]]; then
    caster_rescue_args+=(--party-caster-assist-rescue-target)
  fi
  local support_evasion_args=()
  if [[ "$support_evasion" == "1" ]]; then
    support_evasion_args+=(--party-support-evasion)
  fi
  local boss_non_tank_melee_backoff_args=()
  if [[ "$BOSS_NON_TANK_MELEE_BACKOFF" == "1" ]]; then
    boss_non_tank_melee_backoff_args+=(--party-boss-non-tank-melee-backoff)
  fi
  local clear_objective_adds_args=()
  if [[ "$CLEAR_OBJECTIVE_ADDS_BEFORE_ENGAGE" == "1" ]]; then
    clear_objective_adds_args+=(--party-clear-objective-adds-before-engage)
  fi

  python3 tools/monitor-boss-combat-api.py \
    --api-url "$API_URL" \
    --name "$target_name" \
    --region "$region" \
    --interval "$API_MONITOR_INTERVAL" \
    --snapshot-radius "$SERVER_SNAPSHOT_RADIUS" \
    --out "$report_dir/boss-api.jsonl" \
    > "$report_dir/boss-api-monitor.log" 2>&1 &
  local monitor_pid=$!

  PYTHONUNBUFFERED=1 python3 tools/behavior-dummy-client.py \
    --host "$HOST" --port "$PORT" --accounts "$positioned_accounts_csv" --concurrency "$concurrency" --rounds 1 --hold "$HOLD" --timeout 8 --ramp-up 0.35 \
    --login-retries "$LOGIN_RETRIES" --login-retry-delay "$LOGIN_RETRY_DELAY" \
    --ping-interval 10 --position-heartbeat-interval 2.5 --combat --hunter --combat-interval "$COMBAT_INTERVAL" \
    --move --smooth-movement --server-correction-smoothing --movement-speed "$MOVEMENT_SPEED" --smooth-move-interval "$SMOOTH_MOVE_INTERVAL" --movement-update-interval "$MOVEMENT_UPDATE_INTERVAL" \
    --move-step 120 --attack-range 350 --melee-range-buffer 250 --minimum-melee-stop-distance 85 --melee-stick-attack --melee-stick-attack-distance "$MELEE_STICK_DISTANCE" --ranged-stop-distance 1000 \
    --ground-z-map "$GROUND_Z_MAP" --use-skills --skill-interval 2.0 --spell-levels 1,10,20,30,40,50 --heal-spell-levels 1,10,20,30,40 --stationary-cast-actions --cast-action-hold 2.2 \
    --action-rotation auto --party-slot-rotations "$rotations" --party-size "$party_size" --party-encounter-mode boss --party-assist-only --party-min-ready "$party_size" --party-form-up-delay "$FORM_UP_DELAY" \
    --party-assist-interval "$PARTY_ASSIST_INTERVAL" --party-assist-attack-delay 0.2 --party-ranged-assist-extra-delay "$RANGED_ASSIST_EXTRA_DELAY" --party-rescue-aggro --party-rescue-before-objective-engaged \
    "${local_rescue_args[@]}" "${caster_rescue_args[@]}" "${support_evasion_args[@]}" "${boss_non_tank_melee_backoff_args[@]}" "${clear_objective_adds_args[@]}" \
    --party-rescue-max-distance 1400 --party-rescue-engaged-distance 350 --party-rescue-objective-max-distance "$rescue_objective_distance" --party-rescue-cooldown 2 --party-rescue-min-hold 4 --party-rescue-max-age "$RESCUE_MAX_AGE" --party-rescue-objective-engaged-grace 20 --party-rescue-assist-after "$rescue_assist_after" --party-rescue-emergency-assist-after "$RESCUE_EMERGENCY_ASSIST_AFTER" \
    --party-invite-interval 5 --party-accept-interval 2 --party-follow-interval 0.6 --party-follow-step 260 --party-follow-distance 250 --party-preengage-ranged-safe-distance "$PREENGAGE_RANGED_SAFE_DISTANCE" \
    --boss-ranged-safe-distance 1600 --boss-hazard-message-backoff-duration 9 --boss-hazard-message-backoff-distance 2600 --party-focus-target-backoff --party-focus-pressure-melee-backoff --party-focus-pressure-offtank-reaggro --party-burn-required-target-health-percent "$BURN_REQUIRED_TARGET_HEALTH_PERCENT" --party-active-tank-reaggro-taunt-interval 0.8 --party-active-tank-handoff-health-percent "$ACTIVE_TANK_HANDOFF_HEALTH_PERCENT" --party-focus-target-max-age 6 --party-focus-target-backoff-distance 1900 \
    --party-melee-survival-health-percent 45 --party-melee-survival-resume-health-percent 80 --party-melee-survival-backoff-duration 12 --party-survival-death-count 2 --party-survival-death-window 75 --party-survival-active-tank-health-percent 35 --party-survival-backoff-distance 1000 \
    --party-heal-leader-interval 0.5 --party-heal-leader-health-percent 99 --party-buff-interval 12 --party-buff-spell-levels 1,10,20,30,40 --healer-self-health-percent 80 --support-spell-chance 0 \
    --player-level 50 --min-target-level "$target_level" --max-target-level "$target_level" --ideal-target-level "$target_level" \
    --target-selection smart --target-pool 1 --max-target-distance 5000 --target-timeout "$TARGET_TIMEOUT" --target-failure-cooldown 10 --target-failure-name-cooldown 15 --stop-after-required-target-removed --target-removed-loot-wait 5 --party-target-loss-grace 12 --party-target-removed-preserve-limit 100 \
    --prefer-target-name "$target_name" --require-target-name "$target_name" --auto-loot --jitter 0.1 \
    --required-target-api --required-target-api-region "$region" --required-target-api-interval "$API_MONITOR_INTERVAL" \
    --required-target-catchup-distance "$CATCHUP_DISTANCE" --required-target-catchup-offset "$CATCHUP_OFFSET" \
    --required-target-home "$target_x,$target_y,$target_z" --required-target-home-stop-distance 900 \
    --trace-movement-log "$report_dir/traces/{username}-{round}.jsonl" \
    --encounter-log "$report_dir/encounter/{username}-{round}.jsonl" --encounter-log-interval "$ENCOUNTER_LOG_INTERVAL" \
    --metrics-csv "$report_dir/metrics.csv" --combat-csv "$report_dir/combat.csv" --report-md "$report_dir/report.md" \
    > "$report_dir/output.log" 2>&1
  local status=$?

  sleep 2
  kill "$monitor_pid" 2>/dev/null || true
  wait "$monitor_pid" 2>/dev/null || true

  if compgen -G "$report_dir/encounter/*.jsonl" > /dev/null || [[ -f "$report_dir/boss-api.jsonl" ]]; then
    python3 tools/analyze-dummy-encounter-logs.py \
      "$report_dir/encounter/*.jsonl" \
      "$report_dir/boss-api.jsonl" \
      --json-out "$report_dir/encounter-analysis.json" \
      --report-md "$report_dir/encounter-analysis.md" || true
  fi

  return "$status"
}

status=0
cases_launched=0

case_enabled() {
  local case_name="$1"
  [[ -z "$CASE_FILTER" || "$case_name" =~ $CASE_FILTER ]]
}

launch_case() {
  local case_name="$1"
  shift

  if ! case_enabled "$case_name"; then
    return 0
  fi

  run_case "$case_name" "$@" &
  pids+=($!)
  cases_launched=$((cases_launched + 1))
  if (( CASE_LAUNCH_STAGGER > 0 )); then
    sleep "$CASE_LAUNCH_STAGGER"
  fi
  if (( MAX_PARALLEL_CASES > 0 && ${#pids[@]} >= MAX_PARALLEL_CASES )); then
    wait_case_wave
  fi
}

wait_case_wave() {
  local pid
  local wave_status=0

  for pid in "${pids[@]}"; do
    wait "$pid" || wave_status=1
  done

  pids=()

  if [[ "$wave_status" != "0" ]]; then
    status=1
  fi

  if (( CASE_WAVE_COOLDOWN > 0 )); then
    sleep "$CASE_WAVE_COOLDOWN"
  fi
}

mkdir -p "$REPORT_ROOT"
if [[ "$ISOLATE_BOSS_CLONES" == "1" ]]; then
  delete_test_boss_clones
fi
REALM_ROTATIONS_40="melee-basic,melee-basic,melee-burst,melee-burst,healer-support,healer-support,caster-basic,caster-basic,melee-basic,melee-basic,melee-burst,melee-burst,healer-support,healer-support,caster-basic,caster-basic,melee-basic,melee-basic,melee-burst,melee-burst,healer-support,healer-support,caster-basic,caster-basic,melee-basic,melee-basic,melee-burst,melee-burst,healer-support,healer-support,caster-basic,caster-basic,melee-basic,melee-basic,melee-burst,melee-burst,healer-support,healer-support,caster-basic,caster-basic"
PARTY8_BALANCED="melee-basic,melee-basic,melee-burst,melee-burst,healer-support,healer-support,caster-basic,caster-basic"
PARTY16_BALANCED="${PARTY8_BALANCED},${PARTY8_BALANCED}"

if [[ "$MATRIX_MODE" == "sweep300" ]]; then
  ALB_POOL="tools/dummy-accounts-albion-${SWEEP_POOL_COUNT}.csv"
  MID_POOL="tools/dummy-accounts-midgard-${SWEEP_POOL_COUNT}.csv"
  HIB_POOL="tools/dummy-accounts-hibernia-${SWEEP_POOL_COUNT}.csv"
  for pool in "$ALB_POOL" "$MID_POOL" "$HIB_POOL"; do
    if [[ ! -f "$pool" ]]; then
      echo "missing $pool; run OPENDAOC_REALM_POOL_COUNT=${SWEEP_POOL_COUNT} tools/provision-dummy-realm-pools.sh first" >&2
      exit 2
    fi
  done

  cat > "$REPORT_ROOT/matrix.tsv" <<'EOF'
case	target	level	accounts	rescue_objective_distance	rescue_assist_after	local_rescue	caster_rescue	support_evasion	party_size
EOF

  pids=()
  launch_sweep_realm() {
    local realm_key="$1"
    local target_name="$2"
    local target_level="$3"
    local pool_csv="$4"
    local offset=0

    local specs=(
      "base8|2200|3|1|0|0|8|$PARTY8_BALANCED"
      "assist1|2200|1|1|0|0|8|$PARTY8_BALANCED"
      "assist5|2200|5|1|0|0|8|$PARTY8_BALANCED"
      "radius1400|1400|3|1|0|0|8|$PARTY8_BALANCED"
      "radius2600|2600|3|1|0|0|8|$PARTY8_BALANCED"
      "nolocal|2200|3|0|0|0|8|$PARTY8_BALANCED"
      "caster_rescue|2200|3|1|1|0|8|$PARTY8_BALANCED"
      "support_evasion|2200|3|1|0|1|8|$PARTY8_BALANCED"
      "wide_caster|2600|2|1|1|0|8|$PARTY8_BALANCED"
      "party16|2200|3|1|0|0|16|$PARTY16_BALANCED"
      "party16_radius2600|2600|3|1|0|0|16|$PARTY16_BALANCED"
      "party16_caster_rescue|2600|2|1|1|0|16|$PARTY16_BALANCED"
    )

    local filter=",${SWEEP_SPEC_FILTER},"
    local launched=0
    for spec in "${specs[@]}"; do
      if (( launched >= SWEEP_PARTIES_PER_REALM )); then
        break
      fi
      IFS='|' read -r label rescue_distance assist_after local_rescue caster_rescue support_evasion party_size rotations <<< "$spec"
      if [[ -n "$SWEEP_SPEC_FILTER" && "$filter" != *",$label,"* ]]; then
        continue
      fi
      local accounts_slice="$REPORT_ROOT/accounts-${realm_key}-${label}.csv"
      slice_accounts_csv "$pool_csv" "$offset" "$party_size" "$accounts_slice"
      offset=$((offset + party_size))
      local case_name="${realm_key}_${label}_${party_size}"
      printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
        "$case_name" "$target_name" "$target_level" "$accounts_slice" "$rescue_distance" "$assist_after" \
        "$local_rescue" "$caster_rescue" "$support_evasion" "$party_size" >> "$REPORT_ROOT/matrix.tsv"
      run_case "$case_name" "$target_name" "$target_level" "$accounts_slice" "$rotations" \
        "$rescue_distance" "$assist_after" "$local_rescue" "$caster_rescue" "$support_evasion" "$party_size" "$party_size" &
      pids+=($!)
      if (( CASE_LAUNCH_STAGGER > 0 )); then
        sleep "$CASE_LAUNCH_STAGGER"
      fi
      if (( ${#pids[@]} >= MAX_PARALLEL_CASES )); then
        wait_case_wave
      fi
      launched=$((launched + 1))
    done
  }

  launch_sweep_realm alb "Golestandt" 80 "$ALB_POOL"
  launch_sweep_realm mid "Gjalpinulva" 80 "$MID_POOL"
  launch_sweep_realm hib "Cuuldurach the Glimmer King" 80 "$HIB_POOL"

elif [[ "$MATRIX_MODE" == "realms120" ]]; then
  cat > "$REPORT_ROOT/matrix.tsv" <<'EOF'
case	target	level	accounts	rescue_objective_distance	rescue_assist_after	local_rescue	caster_rescue	support_evasion	party_size
alb_golestandt40	Golestandt	80	tools/dummy-accounts-albion-40.csv	2200	3	1	0	1	40
mid_gjalpinulva40	Gjalpinulva	80	tools/dummy-accounts-midgard-40.csv	2200	3	1	0	1	40
hib_cuuldurach40	Cuuldurach the Glimmer King	80	tools/dummy-accounts-hibernia-40.csv	2200	3	1	0	1	40
EOF

  pids=()
  launch_case alb_golestandt40 "Golestandt" 80 tools/dummy-accounts-albion-40.csv "$REALM_ROTATIONS_40" 2200 3 1 0 1 40 40
  launch_case mid_gjalpinulva40 "Gjalpinulva" 80 tools/dummy-accounts-midgard-40.csv "$REALM_ROTATIONS_40" 2200 3 1 0 1 40 40
  launch_case hib_cuuldurach40 "Cuuldurach the Glimmer King" 80 tools/dummy-accounts-hibernia-40.csv "$REALM_ROTATIONS_40" 2200 3 1 0 1 40 40
elif [[ "$MATRIX_MODE" == "raidmix" ]]; then
  CLASSIC_MIXED="$REPORT_ROOT/accounts-classic-mixed.csv"
  SUPPORT_HEALWALL="$REPORT_ROOT/accounts-support-healwall.csv"
  awk 'FNR == 1 && NR != 1 { next } { print }' \
    tools/dummy-party-albion-pve8.csv \
    tools/dummy-party-albion-mixed-pve8.csv \
    > "$CLASSIC_MIXED"
  awk 'FNR == 1 && NR != 1 { next } { print }' \
    tools/dummy-party-albion-boss-support-pve8.csv \
    tools/dummy-party-albion-boss-healwall-pve8.csv \
    > "$SUPPORT_HEALWALL"

  cat > "$REPORT_ROOT/matrix.tsv" <<EOF
case	target	level	accounts	rescue_objective_distance	rescue_assist_after	local_rescue	caster_rescue	support_evasion	party_size
moran_balanced16	Moran the Mighty	73	$CLASSIC_MIXED	1800	3	1	0	0	16
cailleach_heal16	Cailleach Uragaig	70	$SUPPORT_HEALWALL	1800	4	1	0	0	16
fester_ranged8	Fester	64	tools/dummy-party-albion-boss-ranged-pve8.csv	1800	2	1	0	0	8
EOF

  pids=()
  launch_case moran_balanced16 "Moran the Mighty" 73 "$CLASSIC_MIXED" "melee-basic,melee-basic,melee-burst,melee-burst,melee-burst,melee-burst,healer-support,healer-support,melee-basic,melee-burst,melee-basic,caster-basic,caster-basic,caster-basic,caster-basic,healer-support" 1800 3 1 0 0 16 16
  launch_case cailleach_heal16 "Cailleach Uragaig" 70 "$SUPPORT_HEALWALL" "melee-basic,melee-basic,healer-support,healer-support,healer-support,caster-basic,melee-burst,caster-basic,melee-basic,healer-support,healer-support,healer-support,healer-support,melee-burst,caster-basic,caster-basic" 1800 4 1 0 0 16 16
  launch_case fester_ranged8 "Fester" 64 tools/dummy-party-albion-boss-ranged-pve8.csv "melee-basic,melee-basic,healer-support,healer-support,healer-support,caster-basic,caster-basic,caster-basic" 1800 2 1 0 0 8 8
elif [[ "$MATRIX_MODE" == "raidmix40" ]]; then
  RAIDMIX40="$REPORT_ROOT/accounts-raidmix40.csv"
  if [[ -f tools/dummy-accounts-albion-40.csv ]]; then
    python3 - <<'PY' tools/dummy-accounts-albion-40.csv "$RAIDMIX40"
import csv
import sys

source_path, out_path = sys.argv[1], sys.argv[2]
with open(source_path, newline="", encoding="utf-8") as handle:
    reader = csv.DictReader(handle)
    rows = list(reader)[:40]
    fieldnames = list(reader.fieldnames or [])

with open(out_path, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
PY
  else
    awk 'FNR == 1 && NR != 1 { next } { print }' \
      tools/dummy-party-albion-pve8.csv \
      tools/dummy-party-albion-mixed-pve8.csv \
      tools/dummy-party-albion-boss-support-pve8.csv \
      tools/dummy-party-albion-boss-healwall-pve8.csv \
      tools/dummy-party-albion-boss-ranged-pve8.csv \
      > "$RAIDMIX40"
  fi

  cat > "$REPORT_ROOT/matrix.tsv" <<EOF
case	target	level	accounts	rescue_objective_distance	rescue_assist_after	local_rescue	caster_rescue	support_evasion	party_size
moran_raid40	Moran the Mighty	73	$RAIDMIX40	1800	3	1	0	0	40
cailleach_raid40	Cailleach Uragaig	70	$RAIDMIX40	1800	4	1	0	0	40
fester_raid40	Fester	64	$RAIDMIX40	1800	2	1	0	0	40
EOF

  pids=()
  launch_case moran_raid40 "Moran the Mighty" 73 "$RAIDMIX40" "$REALM_ROTATIONS_40" 1800 3 1 0 0 40 40
  launch_case cailleach_raid40 "Cailleach Uragaig" 70 "$RAIDMIX40" "$REALM_ROTATIONS_40" 1800 4 1 0 0 40 40
  launch_case fester_raid40 "Fester" 64 "$RAIDMIX40" "$REALM_ROTATIONS_40" 1800 2 1 0 0 40 40
else
  cat > "$REPORT_ROOT/matrix.tsv" <<'EOF'
case	target	level	accounts	rescue_objective_distance	rescue_assist_after	local_rescue	caster_rescue	support_evasion
moran_wide	Moran the Mighty	73	tools/dummy-party-albion-pve8.csv	1800	3	1	0	0
wrath_standard	Wrath of Mordred	73	tools/dummy-party-albion-mixed-pve8.csv	1400	3	1	0	0
cailleach_slow	Cailleach Uragaig	70	tools/dummy-party-albion-boss-support-pve8.csv	1800	4	1	0	0
afanc_tight	Legendary Afanc	70	tools/dummy-party-albion-boss-healwall-pve8.csv	1200	3	1	0	0
fester_fast	Fester	64	tools/dummy-party-albion-boss-ranged-pve8.csv	1800	2	1	0	0
EOF

  pids=()
  run_case moran_wide "Moran the Mighty" 73 tools/dummy-party-albion-pve8.csv "melee-basic,melee-basic,melee-burst,melee-burst,melee-burst,melee-burst,healer-support,healer-support" 1800 3 1 0 0 8 8 & pids+=($!)
  run_case wrath_standard "Wrath of Mordred" 73 tools/dummy-party-albion-mixed-pve8.csv "melee-basic,melee-burst,melee-basic,caster-basic,caster-basic,caster-basic,caster-basic,healer-support" 1400 3 1 0 0 8 8 & pids+=($!)
  run_case cailleach_slow "Cailleach Uragaig" 70 tools/dummy-party-albion-boss-support-pve8.csv "melee-basic,melee-basic,healer-support,healer-support,healer-support,caster-basic,melee-burst,caster-basic" 1800 4 1 0 0 8 8 & pids+=($!)
  run_case afanc_tight "Legendary Afanc" 70 tools/dummy-party-albion-boss-healwall-pve8.csv "melee-basic,healer-support,healer-support,healer-support,healer-support,melee-burst,caster-basic,caster-basic" 1200 3 1 0 0 8 8 & pids+=($!)
  run_case fester_fast "Fester" 64 tools/dummy-party-albion-boss-ranged-pve8.csv "melee-basic,melee-basic,healer-support,healer-support,healer-support,caster-basic,caster-basic,caster-basic" 1800 2 1 0 0 8 8 & pids+=($!)
fi

for pid in "${pids[@]}"; do
  wait "$pid" || status=1
done

if [[ "$MATRIX_MODE" == "realms120" && -n "$CASE_FILTER" && "$cases_launched" -eq 0 ]]; then
  echo "no cases matched OPENDAOC_MATRIX_CASE_FILTER=$CASE_FILTER" >&2
  status=2
fi

python3 tools/summarize-dummy-boss-report.py "$REPORT_ROOT" || true
echo "status=$status"
echo "report_root=$REPORT_ROOT"
exit "$status"
