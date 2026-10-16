#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p evidencias
if tmux has-session -t edgevision-web 2>/dev/null; then
  echo 'EdgeVision ya tiene una sesión activa (tmux edgevision-web).'
else
  tmux new-session -d -s edgevision-web "bash '$ROOT/scripts/run_web.sh' >> '$ROOT/evidencias/portal.log' 2>&1"
  echo 'Portal arrancando en segundo plano (puede tardar al cargar Qwen3-VL).'
fi
sleep 2
if ! tmux has-session -t edgevision-web 2>/dev/null; then
  echo 'La sesión se cerró por un error. Revisa las últimas líneas:'
  tail -n 40 evidencias/portal.log || true
  exit 1
fi
HOST_IP=$(ip -4 -o addr show enp0s3 2>/dev/null | awk '{print $4}' | head -n 1 | cut -d/ -f1 || true)
echo 'Portal local: http://127.0.0.1:8000'
echo "Portal desde Windows (si el puente está conectado): http://${HOST_IP:-IP_DE_LA_VM}:8000"
echo 'Diagnóstico: bash ~/edge-vision-lab/scripts/status.sh'
