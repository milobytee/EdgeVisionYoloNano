#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -x "$DIR/.venv/bin/python" ]]; then echo 'Falta entorno Python, ejecutar install.sh' >&2; exit 1; fi
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2
# Bindeo de red privada únicamente; no publicar puerto 9200 en router.
exec "$DIR/.venv/bin/python" "$DIR/camera_service.py" \
  --bind "${CAMERA_BIND:-192.168.100.20}" --port "${CAMERA_PORT:-9200}" \
  --device "${CAMERA_DEVICE:-auto}" --target-fps "${CAMERA_TARGET_FPS:-1}" \
  --onnx-threads "${CAMERA_ONNX_THREADS:-2}" --conf "${CAMERA_CONFIDENCE:-0.40}"
