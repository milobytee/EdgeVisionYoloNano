#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
echo '== EdgeVision: instalando en Ubuntu Server =='
for app in python3 curl; do command -v "$app" >/dev/null || { echo "Falta $app"; exit 1; }; done
if ! python3 -m venv /tmp/edgevision-venv-check-$$ 2>/dev/null; then
  echo 'Instalando python3-venv (requiere permiso sudo)...'
  sudo apt-get update
  sudo apt-get install -y python3-venv python3-pip tmux curl
else
  rm -rf /tmp/edgevision-venv-check-$$
fi
if ! command -v tmux >/dev/null; then sudo apt-get update && sudo apt-get install -y tmux; fi
if [[ ! -x "$HOME/llama.cpp/build/bin/llama-server" ]]; then
  echo 'Falta llama-server compilado en ~/llama.cpp/build/bin. Se conserva tu instalación existente; no se recompila automáticamente.' >&2
  exit 1
fi
if [[ ! -f backend/.env ]]; then cp backend/.env.example backend/.env; fi
mkdir -p evidencias
if [[ ! -x .venv/bin/python ]]; then python3 -m venv .venv; fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt 'huggingface_hub>=0.35,<2' 'pytest>=8,<10'
echo '== Descargando Qwen3-VL multimodal =='
bash scripts/download_model.sh
echo '== Pruebas unitarias =='
.venv/bin/python -m pytest -q tests
printf '\nInstalación terminada. Inicia el portal ejecutando: bash ~/edge-vision-lab/scripts/start.sh\n'
