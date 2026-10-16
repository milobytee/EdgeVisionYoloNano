#!/usr/bin/env bash
set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE="$ROOT/evidencias"
mkdir -p "$EVIDENCE"
REPORT="$EVIDENCE/diagnostico_$(date +%Y%m%d_%H%M%S).txt"
{
  echo '=== EDGEVISION: DIAGNOSTICO DE LABORATORIO ==='
  date -Is
  echo '\n=== VM Ubuntu ==='
  uname -a
  cat /etc/os-release | grep -E 'PRETTY_NAME|VERSION_ID'
  echo "lscpu: $(nproc) CPU virtual(es)"
  free -h
  echo '\n=== Rutas e IP ==='
  ip -4 -br addr
  ip route
  echo '\n=== Conectividad Orange Pi ==='
  ping -c 3 -W 2 192.168.100.20 || true
  timeout 2 bash -c 'echo >/dev/tcp/192.168.100.20/50052' && echo 'RPC: accesible' || echo 'RPC: no disponible'
  echo '\n=== Revision llama.cpp ==='
  git -C "$HOME/llama.cpp" rev-parse HEAD 2>/dev/null || true
  echo '\n=== Portal /api/status ==='
  curl -sS --max-time 4 http://127.0.0.1:8000/api/status || true
  echo '\n=== Ultimas lineas modelo Qwen3-VL ==='
  tail -n 50 "$EVIDENCE/modelo-vlm.log" 2>/dev/null || true
  echo '\n=== Eventos de asignacion RPC ==='
  grep -Ei 'assigned to device RPC|RPC0|offload|compute buffer|using device' "$EVIDENCE/modelo-vlm.log" 2>/dev/null | tail -n 50 || true
} > "$REPORT" 2>&1
printf 'Reporte creado: %s\n' "$REPORT"
# Cámara YOLO: diagnóstico adicional para el informe (sin capturar imagen).
CAMERA_REPORT="$EVIDENCE/estado_yolo_$(date +%Y%m%d_%H%M%S).json"
curl --noproxy '*' -fsS --max-time 5 'http://192.168.100.20:9200/status' > "$CAMERA_REPORT" \
  && echo "Estado de cámara YOLO guardado: $CAMERA_REPORT" \
  || { rm -f "$CAMERA_REPORT"; echo 'Cámara YOLO no disponible para diagnóstico.'; }
