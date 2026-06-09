#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${OPENDAOC_COMPANION_ENV_FILE:-$ROOT/.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source <(sed "s/\r$//" "$ENV_FILE")
  set +a
fi

PYTHON_BIN="${OPENDAOC_COMPANION_PYTHON:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  COMPANION_AI_VENV="${OPENDAOC_COMPANION_AI_VENV:-$HOME/.opendaoc-companion-ai-venv}"
  if [[ -x "$COMPANION_AI_VENV/bin/python" ]]; then
    PYTHON_BIN="$COMPANION_AI_VENV/bin/python"
  elif [[ -x "$ROOT/.venv-companion-ai/bin/python" ]]; then
    PYTHON_BIN="$ROOT/.venv-companion-ai/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi
API_URL="${OPENDAOC_COMPANION_API_URL:-http://localhost:5000}"
ACCOUNTS_CSV="${OPENDAOC_COMPANION_ACCOUNTS:-tools/dummy-live-companions.csv}"
RUN_DIR="${OPENDAOC_COMPANION_RUN_DIR:-test-output/live-companion-service}"
POLL_INTERVAL="${OPENDAOC_COMPANION_POLL_INTERVAL:-3}"
MAX_RUNTIME="${OPENDAOC_COMPANION_MAX_RUNTIME:-0}"
HOLD="${OPENDAOC_COMPANION_HOLD:-3600}"
ATTACH_TIMEOUT="${OPENDAOC_COMPANION_ATTACH_TIMEOUT:-15}"
LEASE_REFRESH_INTERVAL="${OPENDAOC_COMPANION_LEASE_REFRESH_INTERVAL:-30}"
ACTIVE_REQUEST_STATUS_INTERVAL="${OPENDAOC_COMPANION_ACTIVE_REQUEST_STATUS_INTERVAL:-15}"
COMBAT_HOME_LEASH_DISTANCE="${OPENDAOC_COMPANION_COMBAT_HOME_LEASH_DISTANCE:-4500}"
ATTACH_GROUP="${OPENDAOC_COMPANION_ATTACH_GROUP:-1}"
DIALOGUE_ENABLED="${OPENDAOC_COMPANION_DIALOGUE_ENABLED:-0}"
GUIDE_ENABLED="${OPENDAOC_COMPANION_GUIDE_ENABLED:-$DIALOGUE_ENABLED}"
AI_GATEWAY_CONFIG="${OPENDAOC_COMPANION_AI_GATEWAY_CONFIG:-${OPENDAOC_AI_GATEWAY_CONFIG:-tools/opendaoc-ai-gateway.json}}"
AI_GATEWAY_MODEL_ALIAS="${OPENDAOC_COMPANION_AI_GATEWAY_MODEL_ALIAS:-small-dialogue}"
AI_GUIDE_MODEL_ALIAS="${OPENDAOC_COMPANION_AI_GUIDE_MODEL_ALIAS:-openai-small-guide}"
AI_GATEWAY_TIMEOUT="${OPENDAOC_COMPANION_AI_GATEWAY_TIMEOUT:-5}"
DIALOGUE_MIN_INTERVAL="${OPENDAOC_COMPANION_DIALOGUE_MIN_INTERVAL:-5}"
STOP_EXISTING="${OPENDAOC_COMPANION_STOP_EXISTING:-1}"
ONCE="${OPENDAOC_COMPANION_ONCE:-0}"
DRY_RUN="${OPENDAOC_COMPANION_DRY_RUN:-0}"
WAIT_API="${OPENDAOC_COMPANION_WAIT_API:-1}"
WAIT_API_TIMEOUT="${OPENDAOC_COMPANION_WAIT_API_TIMEOUT:-90}"

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

if [[ "$WAIT_API" == "1" ]]; then
  echo "[OpenDAoC] Waiting for companion API..."
  "$PYTHON_BIN" - "$API_URL" "$WAIT_API_TIMEOUT" <<'PY'
import sys
import time
import urllib.error
import urllib.request

base = sys.argv[1].rstrip("/")
timeout = max(0.0, float(sys.argv[2]))
deadline = time.monotonic() + timeout
url = f"{base}/api/dummy/companions/config"

while True:
    try:
        with urllib.request.urlopen(url, timeout=2.0) as response:
            response.read(1)
        print("[OpenDAoC] Companion API is ready.")
        raise SystemExit(0)
    except Exception as exc:
        if time.monotonic() >= deadline:
            print(f"[OpenDAoC] Companion API not ready after {timeout:.0f}s: {exc}", file=sys.stderr)
            raise SystemExit(1)
        time.sleep(1.0)
PY
fi

command=(
  "$PYTHON_BIN" tools/dummy-companion-service.py
  --api-url "$API_URL"
  --accounts-csv "$ACCOUNTS_CSV"
  --run-dir "$RUN_DIR"
  --poll-interval "$POLL_INTERVAL"
  --max-runtime "$MAX_RUNTIME"
  --hold "$HOLD"
  --attach-timeout "$ATTACH_TIMEOUT"
  --active-lease-refresh-interval "$LEASE_REFRESH_INTERVAL"
  --active-request-status-interval "$ACTIVE_REQUEST_STATUS_INTERVAL"
  --combat-home-leash-distance "$COMBAT_HOME_LEASH_DISTANCE"
  --ai-gateway-model-alias "$AI_GATEWAY_MODEL_ALIAS"
  --ai-guide-model-alias "$AI_GUIDE_MODEL_ALIAS"
  --ai-gateway-timeout "$AI_GATEWAY_TIMEOUT"
  --dialogue-min-interval "$DIALOGUE_MIN_INTERVAL"
)

if [[ -n "$AI_GATEWAY_CONFIG" ]]; then
  command+=(--ai-gateway-config "$AI_GATEWAY_CONFIG")
fi

if [[ "$ATTACH_GROUP" == "0" ]]; then
  command+=(--no-attach-group)
else
  command+=(--attach-group)
fi

if [[ "$DIALOGUE_ENABLED" == "1" ]]; then
  command+=(--dialogue-enabled)
else
  command+=(--no-dialogue-enabled)
fi

if [[ "$GUIDE_ENABLED" == "1" ]]; then
  command+=(--guide-enabled)
else
  command+=(--no-guide-enabled)
fi

if [[ "$ONCE" == "1" ]]; then
  command+=(--once)
fi

if [[ "$DRY_RUN" == "1" ]]; then
  command+=(--dry-run)
fi

exec "${command[@]}"
