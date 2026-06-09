#!/usr/bin/env bash
set -euo pipefail

BASE="${OPENDAOC_LLAMACPP_BASE:-/db/opendaoc-llamacpp}"
PID_FILE="$BASE/llama-gemma4-server.pid"
LOG_FILE="$BASE/logs/llama-gemma4-server.log"

mkdir -p "$BASE/logs"

if [[ -f "$PID_FILE" ]]; then
  pid="$(cat "$PID_FILE" || true)"
  if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
    echo "already running pid=$pid"
    exit 0
  fi
  rm -f "$PID_FILE"
fi

nohup "$BASE/start-gemma4-e4b-server.sh" >"$LOG_FILE" 2>&1 &
pid="$!"
echo "$pid" >"$PID_FILE"
echo "started pid=$pid log=$LOG_FILE"
