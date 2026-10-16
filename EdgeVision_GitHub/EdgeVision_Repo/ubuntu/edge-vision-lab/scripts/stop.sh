#!/usr/bin/env bash
# Apagado de portal para actualizar archivos, preserva modelos y evidencias.
set -euo pipefail
if ! tmux has-session -t edgevision-web 2>/dev/null; then
  echo 'Portal ya estaba detenido.'
  exit 0
fi
echo 'Solicitando cierre ordenado de FastAPI y del proceso Qwen3-VL...'
# Uvicorn recibe Ctrl-C, ejecuta lifespan/shutdown y termina llama-server.
tmux send-keys -t edgevision-web C-c || true
for i in $(seq 1 12); do
  if ! tmux has-session -t edgevision-web 2>/dev/null; then
    echo 'Portal detenido correctamente.'
    exit 0
  fi
  sleep 1
done
# Si el cierre tarda, se cierra tmux; podría requerirse validar proceso huérfano.
echo 'El cierre excedió 12 segundos. Terminando sesión tmux...'
tmux kill-session -t edgevision-web || true
echo 'Si se observa error puerto 8081 ocupado tras iniciar, comprobar: pgrep -af llama-server'
