#!/usr/bin/env bash
# Detiene únicamente procesos iniciados por Start-LiveClip-Xubuntu.sh.
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="$ROOT/backend/storage/runtime"

if curl --fail --silent --max-time 3 -X POST http://127.0.0.1:8000/streams/stop >/dev/null 2>&1; then
  echo "La transmisión activa fue detenida."
fi

stop_service() {
  local name="$1" pid_file="$2" expected="$3"
  [[ -f "$pid_file" ]] || return 0
  local pid command
  pid="$(<"$pid_file")"
  if [[ ! "$pid" =~ ^[0-9]+$ ]] || [[ ! -d "/proc/$pid" ]]; then
    rm -f "$pid_file"
    return 0
  fi
  command="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  if [[ "$command" != *"$expected"* ]]; then
    echo "No se detuvo $name: el PID $pid no corresponde al lanzador de LiveClip." >&2
    return 1
  fi
  echo "Deteniendo $name…"
  kill -- "-$pid" 2>/dev/null || kill "$pid" 2>/dev/null || true
  for _ in $(seq 1 10); do
    [[ ! -d "/proc/$pid" ]] && break
    sleep 1
  done
  [[ ! -d "/proc/$pid" ]] || kill -KILL -- "-$pid" 2>/dev/null || true
  rm -f "$pid_file"
}

stop_service "frontend" "$RUNTIME/frontend.pid" "npm run dev"
stop_service "backend" "$RUNTIME/backend.pid" "uvicorn app.main:app"
echo "LiveClip AI apagado."
