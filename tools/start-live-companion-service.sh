#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

API_URL="${OPENDAOC_COMPANION_API_URL:-http://127.0.0.1:5000}"
ACCOUNTS_CSV="${OPENDAOC_COMPANION_ACCOUNTS:-tools/dummy-live-companions.csv}"
RUN_DIR="${OPENDAOC_COMPANION_RUN_DIR:-test-output/live-companion-service}"
POLL_INTERVAL="${OPENDAOC_COMPANION_POLL_INTERVAL:-3}"
MAX_RUNTIME="${OPENDAOC_COMPANION_MAX_RUNTIME:-0}"
HOLD="${OPENDAOC_COMPANION_HOLD:-3600}"
ATTACH_TIMEOUT="${OPENDAOC_COMPANION_ATTACH_TIMEOUT:-15}"
LEASE_REFRESH_INTERVAL="${OPENDAOC_COMPANION_LEASE_REFRESH_INTERVAL:-30}"
COMBAT_HOME_LEASH_DISTANCE="${OPENDAOC_COMPANION_COMBAT_HOME_LEASH_DISTANCE:-4500}"
ATTACH_GROUP="${OPENDAOC_COMPANION_ATTACH_GROUP:-1}"
DIALOGUE_ENABLED="${OPENDAOC_COMPANION_DIALOGUE_ENABLED:-0}"
AI_GATEWAY_CONFIG="${OPENDAOC_COMPANION_AI_GATEWAY_CONFIG:-${OPENDAOC_AI_GATEWAY_CONFIG:-}}"
AI_GATEWAY_MODEL_ALIAS="${OPENDAOC_COMPANION_AI_GATEWAY_MODEL_ALIAS:-small-dialogue}"
AI_GATEWAY_TIMEOUT="${OPENDAOC_COMPANION_AI_GATEWAY_TIMEOUT:-5}"
DIALOGUE_MIN_INTERVAL="${OPENDAOC_COMPANION_DIALOGUE_MIN_INTERVAL:-5}"
STOP_EXISTING="${OPENDAOC_COMPANION_STOP_EXISTING:-1}"
ONCE="${OPENDAOC_COMPANION_ONCE:-0}"
DRY_RUN="${OPENDAOC_COMPANION_DRY_RUN:-0}"

if [[ ! -f "$ACCOUNTS_CSV" ]]; then
  echo "[OpenDAoC] Missing companion account pool: $ACCOUNTS_CSV" >&2
  exit 1
fi

stop_existing_service() {
  local pids
  pids="$(pgrep -f '[t]ools/dummy-companion-service.py' || true)"
  if [[ -z "$pids" ]]; then
    return
  fi

  echo "[OpenDAoC] Existing companion service detected; stopping it first..."
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true

  for _ in {1..10}; do
    if [[ -z "$(pgrep -f '[t]ools/dummy-companion-service.py' || true)" ]]; then
      echo "[OpenDAoC] Previous companion service stopped."
      return
    fi
    sleep 1
  done

  pids="$(pgrep -f '[t]ools/dummy-companion-service.py' || true)"
  if [[ -n "$pids" ]]; then
    echo "[OpenDAoC] Previous companion service did not exit in time; forcing stop..."
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

if [[ "$STOP_EXISTING" == "1" ]]; then
  stop_existing_service
fi

mkdir -p "$RUN_DIR"

echo "[OpenDAoC] Starting live companion service."
echo "[OpenDAoC] API: $API_URL"
echo "[OpenDAoC] Accounts: $ACCOUNTS_CSV"
echo "[OpenDAoC] Run dir: $RUN_DIR"

command=(
  python3 tools/dummy-companion-service.py
  --api-url "$API_URL"
  --accounts-csv "$ACCOUNTS_CSV"
  --run-dir "$RUN_DIR"
  --poll-interval "$POLL_INTERVAL"
  --max-runtime "$MAX_RUNTIME"
  --hold "$HOLD"
  --attach-timeout "$ATTACH_TIMEOUT"
  --active-lease-refresh-interval "$LEASE_REFRESH_INTERVAL"
  --combat-home-leash-distance "$COMBAT_HOME_LEASH_DISTANCE"
)

if [[ "$ATTACH_GROUP" == "0" ]]; then
  command+=(--no-attach-group)
else
  command+=(--attach-group)
fi

if [[ "$DIALOGUE_ENABLED" == "1" ]]; then
  command+=(
    --dialogue-enabled
    --ai-gateway-model-alias "$AI_GATEWAY_MODEL_ALIAS"
    --ai-gateway-timeout "$AI_GATEWAY_TIMEOUT"
    --dialogue-min-interval "$DIALOGUE_MIN_INTERVAL"
  )
  if [[ -n "$AI_GATEWAY_CONFIG" ]]; then
    command+=(--ai-gateway-config "$AI_GATEWAY_CONFIG")
  fi
else
  command+=(--no-dialogue-enabled)
fi

if [[ "$ONCE" == "1" ]]; then
  command+=(--once)
fi

if [[ "$DRY_RUN" == "1" ]]; then
  command+=(--dry-run)
fi

exec "${command[@]}"
