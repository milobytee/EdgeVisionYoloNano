#!/usr/bin/env bash
# Runs from Ubuntu VM; copies the already-tested patch to Orange Pi.
set -euo pipefail
SRC="$HOME/edge-vision-lab/camera_worker"
PI="${EDGE_PI_SSH:-orangepi@192.168.100.20}"
[[ -f "$SRC/camera_service_fixed.py" && -f "$SRC/apply_patch_202.sh" ]] || {
  echo 'No se copiaron los archivos del parche a Ubuntu.' >&2
  exit 1
}
echo 'Transfiriendo solo 2 archivos del parche a Orange Pi (sin descargar modelo)...'
scp -o ConnectTimeout=12 \
 "$SRC/camera_service_fixed.py" "$SRC/apply_patch_202.sh" \
 "$PI:/home/orangepi/edgevision-camera/"
echo 'Validando ONNX, aplicando parche y arrancando servicio de camara...'
ssh -tt -o ConnectTimeout=12 "$PI" 'bash /home/orangepi/edgevision-camera/apply_patch_202.sh'
echo 'Reparacion 2.0.2 finalizada. Verifica el portal EdgeVision.'
