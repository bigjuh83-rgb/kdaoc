#!/usr/bin/env sh
set -eu

pids="$(
  ps -eo pid,args |
    awk '/tools\/(run-dummy-growth-suite|behavior-dummy-client|monitor-dummy-growth-live|summarize-dummy-growth-run)\.py/ && !/awk/ { print $1 }'
)"

if [ -n "$pids" ]; then
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 1
  # shellcheck disable=SC2086
  kill -9 $pids 2>/dev/null || true
fi

ps -eo pid,ppid,etime,args |
  grep -E 'run-dummy-growth-suite|behavior-dummy-client|monitor-dummy-growth-live|summarize-dummy-growth-run' |
  grep -v grep || true
