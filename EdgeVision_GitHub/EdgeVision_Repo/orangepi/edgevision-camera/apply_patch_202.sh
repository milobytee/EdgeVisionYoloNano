#!/usr/bin/env bash
# EdgeVision 2.0.2 -- Only fixes the YOLO rectangular ONNX input on Orange Pi.
# No downloads, pip installs, RPC changes, or VLM restarts.
set -euo pipefail
DIR="$HOME/edgevision-camera"
cd "$DIR"
MODEL="$DIR/yolo11n.onnx"
PATCH="$DIR/camera_service_fixed.py"
SHA_V1='36a10d3faf914feaf0f4e813d5635c26762cc71e54eff14c40cef8dba5b8a70d'
SHA_V2='baeb4c1d6f3bb460689823cc2d40daa31e6156f2517fcd48aab0db9490d9f4e5'
[[ -f "$MODEL" && -f "$PATCH" && -x "$DIR/.venv/bin/python" ]] || {
  echo 'ERROR: faltan ONNX, parche Python o entorno virtual. Se necesita la instalacion 2.0.1 previa.' >&2
  exit 1
}
ACTUAL="$(sha256sum "$MODEL" | awk '{print $1}')"
case "$ACTUAL" in
  "$SHA_V1"|"$SHA_V2") echo "OK SHA256 YOLO: $ACTUAL" ;;
  *) echo "ERROR: SHA256 del ONNX inesperado: $ACTUAL" >&2; exit 2;;
esac

"$DIR/.venv/bin/python" -m py_compile "$PATCH"
echo 'Prueba real ONNX 480x640 / 640x640 (sin webcam):'
# Import the patch in isolation, before changing the running service.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=2 "$DIR/.venv/bin/python" - "$PATCH" "$MODEL" <<'PY'
from pathlib import Path
import importlib.util
import numpy as np
import sys, time
patch, model = map(Path, sys.argv[1:3])
spec = importlib.util.spec_from_file_location('edgevision_camera_202', patch)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
begin = time.monotonic()
detector = m.OnnxDetector(model, threads=2)
print('Modelo aceptado. Dimensiones ALTO x ANCHO:', detector.height, 'x', detector.width, flush=True)
assert detector.height > 0 and detector.width > 0
frame = np.zeros((480, 640, 3), dtype=np.uint8)
tensor, scale, left, top = m.preprocess(frame, (detector.height, detector.width))
assert tensor.shape == (1,3,detector.height,detector.width), tensor.shape
assert tensor.dtype == np.float32
found = detector.predict(frame)
assert isinstance(found, list)
print(f'Inferencia ONNX de prueba correcta. {len(found)} detecciones, {time.monotonic()-begin:.1f} s.', flush=True)
PY

STAMP="$(date +%Y%m%d_%H%M%S)"
cp -p "$DIR/camera_service.py" "$DIR/camera_service.py.bak_$STAMP"
cp "$PATCH" "$DIR/camera_service.py"
chmod 644 "$DIR/camera_service.py"
echo "Codigo actualizado; respaldo: camera_service.py.bak_$STAMP"

if tmux has-session -t edgevision-camera 2>/dev/null; then
  tmux kill-session -t edgevision-camera
fi
# Only restart the camera tmux session. Other services are unaffected.
tmux new-session -d -s edgevision-camera "bash '$DIR/start.sh' >> '$DIR/camara.log' 2>&1"
echo 'Esperando al servicio de camara en 192.168.100.20:9200...'
RESPONSE=''
for _ in $(seq 1 20); do
  RESPONSE="$(curl --noproxy '*' -fsS --max-time 2 'http://192.168.100.20:9200/status' 2>/dev/null || true)"
  if [[ -n "$RESPONSE" ]]; then break; fi
  sleep 1
done
if [[ -z "$RESPONSE" ]]; then
  echo 'ERROR: el servicio de camara no abrio su puerto.' >&2
  echo 'Ultimas lineas de camara.log:'
  tail -n 70 "$DIR/camara.log" || true
  exit 1
fi
printf 'ESTADO YOLO: %s\n' "$RESPONSE"
if [[ "$RESPONSE" == *'"online": true'* || "$RESPONSE" == *'"online":true'* ]]; then
  echo 'EXITO: servicio YOLO activo y webcam entregando fotogramas.'
else
  echo 'AVISO: el servidor YOLO responde, pero aun no hay fotogramas recientes de la webcam.'
  echo 'Comprueba webcam USB, permisos /dev/video*, o consulta el campo last_error en status.'
fi
echo 'RPC (50052) y Qwen3-VL NO se modificaron.'
