#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI="${PI_SSH:-orangepi@192.168.100.20}"
echo "Copiando monitor a $PI (puede pedir contraseña)..."
scp "$ROOT/scripts/worker_metrics.py" "$PI:edgevision-worker-metrics.py"
ssh "$PI" 'tmux has-session -t edgevision-metrics 2>/dev/null || tmux new-session -d -s edgevision-metrics "python3 ~/edgevision-worker-metrics.py --bind 192.168.100.20 --port 9100"'
echo 'Monitor Orange Pi preparado: http://192.168.100.20:9100/metrics'
curl --max-time 3 --fail http://192.168.100.20:9100/metrics || true
