#!/usr/bin/env bash
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo '=== EdgeVision: estado ==='
echo 'Direcciones de Ubuntu:'
ip -4 -br addr
echo 'Worker RPC:'
if timeout 3 bash -c 'echo >/dev/tcp/192.168.100.20/50052' 2>/dev/null; then echo 'Puerto 50052 accesible'; else echo 'Worker no responde'; fi
if tmux has-session -t edgevision-web 2>/dev/null; then echo 'Portal: sesión tmux activa'; else echo 'Portal: apagado'; fi
curl -fsS --max-time 3 http://127.0.0.1:8000/api/status || true
printf '\nÚltimos eventos del modelo:\n'
tail -n 12 "$ROOT/evidencias/modelo-vlm.log" 2>/dev/null || true
