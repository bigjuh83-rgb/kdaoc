#!/usr/bin/env bash
set -euo pipefail

check_tcp() {
  local port="$1"
  ss -H -ltn "sport = :$port" | grep -q .
}

check_udp() {
  local port="$1"
  ss -H -lun "sport = :$port" | grep -q .
}

check_api() {
  local port="${OPENDAOC_API_PORT:-5000}"
  curl -fsS --max-time 2 "http://127.0.0.1:${port}/api/world/dynamic-quests/story-config" >/dev/null
}

ok=1

if check_tcp 10300; then
  echo "OK tcp 10300"
else
  echo "DOWN tcp 10300"
  ok=0
fi

if check_udp 10400; then
  echo "OK udp 10400"
else
  echo "DOWN udp 10400"
  ok=0
fi

if check_tcp 3306; then
  echo "OK db 3306"
else
  echo "DOWN db 3306"
  ok=0
fi

if check_api; then
  echo "OK api ${OPENDAOC_API_PORT:-5000}"
else
  echo "DOWN api ${OPENDAOC_API_PORT:-5000}"
  ok=0
fi

exit $(( ok ? 0 : 1 ))
