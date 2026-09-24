#!/usr/bin/env bash
# Instala y verifica las dependencias de LiveClip AI en Xubuntu/Debian.
# Uso: ./Prepare-Xubuntu.sh [--with-ollama]
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
WITH_OLLAMA=false
[[ "${1:-}" == "--with-ollama" ]] && WITH_OLLAMA=true
[[ $# -le 1 ]] || { echo "Uso: $0 [--with-ollama]" >&2; exit 2; }

if ! command -v apt-get >/dev/null 2>&1; then
  echo "Este script requiere Xubuntu, Ubuntu o Debian con apt-get." >&2
  exit 1
fi
if [[ $EUID -eq 0 ]]; then SUDO=(); else SUDO=(sudo); fi
if [[ $EUID -ne 0 ]] && ! command -v sudo >/dev/null 2>&1; then
  echo "Necesitas sudo para instalar dependencias del sistema." >&2
  exit 1
fi

need_apt=false
for command in python3 ffmpeg curl; do command -v "$command" >/dev/null 2>&1 || need_apt=true; done
[[ -d "$ROOT/backend/.venv" ]] || need_apt=true
if $need_apt; then
  "${SUDO[@]}" apt-get update
fi

"${SUDO[@]}" apt-get install -y \
  ca-certificates curl ffmpeg fonts-dejavu-core python3 python3-pip python3-venv

python_major="$(python3 -c 'import sys; print(sys.version_info.major)')"
python_minor="$(python3 -c 'import sys; print(sys.version_info.minor)')"
if [[ "$python_major" -ne 3 || "$python_minor" -lt 10 ]]; then
  echo "Se requiere Python 3.10 o superior; se encontró $(python3 --version)." >&2
  exit 1
fi

node_major=0
if command -v node >/dev/null 2>&1; then node_major="$(node -p 'process.versions.node.split(".")[0]')"; fi
if [[ "$node_major" -lt 20 ]]; then
  echo "Instalando Node.js 22 LTS para el frontend…"
  if [[ $EUID -eq 0 ]]; then
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
  else
    curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  fi
  "${SUDO[@]}" apt-get install -y nodejs
fi
node_major="$(node -p 'process.versions.node.split(".")[0]')"
if [[ "$node_major" -lt 20 ]]; then
  echo "Node.js 20 o superior es necesario; se encontró $(node --version)." >&2
  exit 1
fi

filters="$(ffmpeg -hide_banner -filters 2>/dev/null)"
if ! grep -qE '[[:space:]](ass|subtitles)[[:space:]]' <<<"$filters"; then
  echo "El FFmpeg instalado no incluye el filtro libass requerido para quemar subtítulos." >&2
  exit 1
fi
encoders="$(ffmpeg -hide_banner -encoders 2>/dev/null)"
if ! grep -q 'libx264' <<<"$encoders" || ! grep -qE '[[:space:]]aac[[:space:]]' <<<"$encoders"; then
  echo "El FFmpeg instalado necesita los codificadores libx264 y AAC para generar MP4." >&2
  exit 1
fi

echo "Preparando entorno Python…"
if [[ ! -x "$ROOT/backend/.venv/bin/python" ]]; then
  python3 -m venv "$ROOT/backend/.venv"
fi
"$ROOT/backend/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/backend/.venv/bin/python" -m pip install -r "$ROOT/backend/requirements-lock.txt"

echo "Preparando frontend…"
npm --prefix "$ROOT/frontend" ci

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "Se creó .env con valores locales predeterminados."
fi

if $WITH_OLLAMA; then
  if ! command -v ollama >/dev/null 2>&1; then
    echo "Instalando Ollama local…"
    curl -fsSL https://ollama.com/install.sh | "${SUDO[@]}" sh
  fi
  if ! curl --fail --silent --max-time 3 http://127.0.0.1:11434/api/tags >/dev/null; then
    echo "Ollama está instalado, pero no responde en localhost:11434." >&2
    echo "Inícialo con: systemctl --user start ollama  (o ejecuta: ollama serve)" >&2
  fi
else
  echo "Ollama es opcional para probar subtítulos y render 9:16."
  echo "Para instalarlo después: ./Prepare-Xubuntu.sh --with-ollama"
fi

echo
echo "Listo. Verificación rápida de fases 4 y 5:"
echo "  $ROOT/backend/.venv/bin/python -m pytest $ROOT/backend/tests/test_rendering.py -q"
echo "Para iniciar el estudio: ./Start-LiveClip-Xubuntu.sh"
