#!/usr/bin/env bash
set -euo pipefail

BASE="${OPENDAOC_LLAMACPP_BASE:-/db/opendaoc-llamacpp}"
PID_FILE="$BASE/llama-gemma4-server.pid"
MATCH_PATH="$BASE/llama.cpp/build/bin/llama-server"
PIDS=()

add_tree() {
  local root="$1"
  [[ "$root" =~ ^[0-9]+$ ]] || return 0
  kill -0 "$root" 2>/dev/null || return 0
  local child
  while IFS= read -r child; do
    add_tree "$child"
  done < <(pgrep -P "$root" 2>/dev/null || true)
  PIDS+=("$root")
}

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  add_tree "$pid"
fi

while IFS= read -r pid; do
  add_tree "$pid"
done < <(pgrep -f "$MATCH_PATH" 2>/dev/null || true)

if ((${#PIDS[@]} == 0)); then
  rm -f "$PID_FILE"
  echo "not running"
  exit 0
fi

mapfile -t UNIQUE_PIDS < <(printf '%s\n' "${PIDS[@]}" | awk 'NF && !seen[$1]++')

for pid in "${UNIQUE_PIDS[@]}"; do
  kill "$pid" 2>/dev/null || true
done

for _ in {1..30}; do
  ALIVE=()
  for pid in "${UNIQUE_PIDS[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      ALIVE+=("$pid")
    fi
  done
  ((${#ALIVE[@]} == 0)) && break
  sleep 0.2
done

for pid in "${ALIVE[@]:-}"; do
  kill -KILL "$pid" 2>/dev/null || true
done

rm -f "$PID_FILE"
echo "stopped pids=${UNIQUE_PIDS[*]}"
