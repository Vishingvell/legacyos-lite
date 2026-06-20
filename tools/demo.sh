#!/usr/bin/env bash
# Copyright (c) 2026 Vishalan Karunanithi
# All Rights Reserved.
# Unauthorized copying, modification, distribution, or commercial use is prohibited.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${LEGACYOSLITE_DEMO_PORT:-8010}"
DEMO_DB_PATH="${LEGACYOSLITE_DEMO_DB_PATH:-$ROOT_DIR/data/legacyoslite.demo.db}"
DEMO_OPEN_BROWSER="${LEGACYOSLITE_DEMO_OPEN_BROWSER:-1}"
SMOKE_PORT="${LEGACYOSLITE_SMOKE_PORT:-8011}"
UVICORN_BIN="${LEGACYOSLITE_UVICORN_BIN:-$ROOT_DIR/../.venv/bin/uvicorn}"
PYTHON_BIN="${LEGACYOSLITE_PYTHON_BIN:-$ROOT_DIR/../.venv/bin/python}"

RUN_SMOKE=1
KEEP_SERVER=1

usage() {
  cat <<'EOF'
Usage:
  ./tools/demo.sh [--no-smoke] [--no-open-browser] [--no-keep-alive]

Options:
  --no-smoke        Skip the Day 7 smoke verification.
  --no-open-browser Do not auto-open a browser tab.
  --no-keep-alive   Exit after startup checks instead of waiting for Ctrl+C.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-smoke)
      RUN_SMOKE=0
      shift
      ;;
    --no-open-browser)
      DEMO_OPEN_BROWSER=0
      shift
      ;;
    --no-keep-alive)
      KEEP_SERVER=0
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ ! -x "$UVICORN_BIN" ]]; then
  echo "Could not find uvicorn at $UVICORN_BIN"
  echo "Run: .venv/bin/pip install fastapi uvicorn"
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Could not find python interpreter at $PYTHON_BIN"
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/backend"
export LEGACYOSLITE_DB_PATH="$DEMO_DB_PATH"

cleanup() {
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi

  if [[ -f "$ROOT_DIR/.demo-server.log" ]]; then
    rm -f "$ROOT_DIR/.demo-server.log"
  fi
}
trap cleanup EXIT

run_smoke() {
  echo "Running Day 7 smoke verification on port ${SMOKE_PORT}..."
  LEGACYOSLITE_SMOKE_PORT="$SMOKE_PORT" \
  PYTHONPATH="$ROOT_DIR/backend" \
  "$PYTHON_BIN" "$ROOT_DIR/tools/day7_smoke.py"
}

start_demo_server() {
  rm -f "$DEMO_DB_PATH"
  echo "Starting LegacyOS Lite demo server on 127.0.0.1:${PORT} ..."
  "$UVICORN_BIN" legacyos_lite.main:app \
    --host 127.0.0.1 \
    --port "$PORT" \
    >"$ROOT_DIR/.demo-server.log" \
    2>&1 &
  API_PID=$!

  for attempt in $(seq 1 30); do
    if curl -fsS "http://127.0.0.1:$PORT/api/health" >/tmp/legacyoslite-health.json 2>/dev/null; then
      break
    fi
    sleep 0.2
  done

  if ! curl -fsS "http://127.0.0.1:$PORT/api/health" >/tmp/legacyoslite-health.json 2>/dev/null; then
    echo "Demo API failed to start in time. Check $ROOT_DIR/.demo-server.log"
    exit 1
  fi

  echo "Demo endpoint is live: http://127.0.0.1:$PORT"
  echo
  echo "Rehearsal flow:"
  echo "1) Open dashboard and select a role."
  echo "2) Complete the interview prompts (min 80 chars each)."
  echo "3) Run Generate Profile."
  echo "4) Open Timeline and Knowledge Graph pages."
  echo "5) Add one note in Knowledge Repository."
  echo "6) Ask one high-clarity question in Search."
  echo
}

start_demo_server

if [[ "$DEMO_OPEN_BROWSER" == "1" ]]; then
  if command -v open >/dev/null 2>&1; then
    open "http://127.0.0.1:$PORT"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "http://127.0.0.1:$PORT" >/dev/null 2>&1 || true
  else
    echo "No browser opener found; open http://127.0.0.1:$PORT manually."
  fi
fi

if [[ "$RUN_SMOKE" == "1" ]]; then
  run_smoke
fi

if [[ "$KEEP_SERVER" == "1" ]]; then
  echo "Server running. Press Ctrl+C to stop."
  wait "$API_PID"
else
  echo "Skipping keep-alive. Close with script exit."
fi
