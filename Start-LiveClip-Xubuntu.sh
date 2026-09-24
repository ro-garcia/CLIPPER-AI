#!/usr/bin/env bash
# Inicia LiveClip AI en loopback. Uso: ./Start-LiveClip-Xubuntu.sh [--open]
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
RUNTIME="$ROOT/backend/storage/runtime"
LOGS="$ROOT/backend/storage/logs"
OPEN=false
[[ "${1:-}" == "--open" ]] && OPEN=true
[[ $# -le 1 ]] || { echo "Uso: $0 [--open]" >&2; exit 2; }
mkdir -p "$RUNTIME" "$LOGS"

[[ -x "$ROOT/backend/.venv/bin/python" ]] || { echo "Falta backend/.venv. Ejecuta ./Prepare-Xubuntu.sh primero." >&2; exit 1; }
[[ -d "$ROOT/frontend/node_modules" ]] || { echo "Falta frontend/node_modules. Ejecuta ./Prepare-Xubuntu.sh primero." >&2; exit 1; }

healthy() { curl --fail --silent --max-time 2 "$1" >/dev/null; }
start_backend() {
  if healthy http://127.0.0.1:8000/health; then
    echo "Backend ya está activo en http://127.0.0.1:8000"
    return
  fi
  echo "Iniciando backend…"
  setsid "$ROOT/backend/.venv/bin/python" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 \
    --app-dir "$ROOT/backend" >"$LOGS/backend-xubuntu.log" 2>&1 &
  echo $! > "$RUNTIME/backend.pid"
}
start_frontend() {
  if healthy http://127.0.0.1:5173; then
    echo "Frontend ya está activo en http://127.0.0.1:5173"
    return
  fi
  echo "Iniciando frontend…"
  (
    cd "$ROOT/frontend"
    exec setsid npm run dev -- --host 127.0.0.1 --port 5173
  ) >"$LOGS/frontend-xubuntu.log" 2>&1 &
  echo $! > "$RUNTIME/frontend.pid"
}
wait_for() {
  local url="$1" label="$2"
  for _ in $(seq 1 25); do
    healthy "$url" && return
    sleep 1
  done
  echo "$label no respondió. Revisa $LOGS" >&2
  exit 1
}

start_backend
start_frontend
wait_for http://127.0.0.1:8000/health "El backend"
wait_for http://127.0.0.1:5173 "El frontend"
echo "LiveClip AI listo: http://127.0.0.1:5173"

if $OPEN && command -v xdg-open >/dev/null 2>&1; then
  xdg-open http://127.0.0.1:5173 >/dev/null 2>&1 &
fi
