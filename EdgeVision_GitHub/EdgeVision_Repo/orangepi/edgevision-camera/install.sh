#!/usr/bin/env bash
# EdgeVision 2.0.1: strict acceptance of two known upstream YOLO11n model digests.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"
MODEL="$DIR/yolo11n.onnx"
SHA_V1='36a10d3faf914feaf0f4e813d5635c26762cc71e54eff14c40cef8dba5b8a70d'
SHA_V2='baeb4c1d6f3bb460689823cc2d40daa31e6156f2517fcd48aab0db9490d9f4e5'
[[ -f "$MODEL" ]] || { echo "Falta $MODEL" >&2; exit 1; }
ACTUAL="$(sha256sum "$MODEL" | awk '{print $1}')"
case "$ACTUAL" in
  "$SHA_V1"|"$SHA_V2") echo "Modelo YOLO verificado en Orange Pi ($ACTUAL)";;
  *) echo "ERROR: SHA256 inesperado en Orange Pi: $ACTUAL" >&2; exit 2;;
esac
echo '== Instalando dependencias Python y herramientas webcam (sin alterar RPC/VLM) =='
sudo apt-get update
sudo apt-get install -y python3-venv python3-pip v4l-utils libgomp1 tmux curl
if [[ ! -x "$DIR/.venv/bin/python" ]]; then python3 -m venv "$DIR/.venv"; fi
"$DIR/.venv/bin/python" -m pip install --upgrade pip
"$DIR/.venv/bin/python" -m pip install --only-binary=:all: -r "$DIR/requirements.txt"
echo 'Verificando que ONNX Runtime pueda cargar la red neuronal...'
"$DIR/.venv/bin/python" - "$DIR" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from camera_service import OnnxDetector
model = OnnxDetector(Path(sys.argv[1]) / 'yolo11n.onnx', threads=2)
print(f'Modelo ONNX cargado. Entrada: {model.size}x{model.size}')
PY
echo 'Detectando webcam(s):'
v4l2-ctl --list-devices || true
if ! id -nG | tr ' ' '\n' | grep -qx video; then
  echo 'AVISO: usuario no pertenece al grupo video. Si la webcam marca Permission denied, agrega al usuario al grupo video y vuelve a abrir SSH.'
fi
if tmux has-session -t edgevision-camera 2>/dev/null; then tmux kill-session -t edgevision-camera; fi
tmux new-session -d -s edgevision-camera "bash '$DIR/start.sh' >> '$DIR/camara.log' 2>&1"
sleep 5
echo 'Estado del worker webcam:'
if ! curl --noproxy '*' -fsS --max-time 5 'http://192.168.100.20:9200/status'; then
  echo
  echo 'Worker no listo. Ultimo log:'
  tail -n 70 "$DIR/camara.log" || true
  exit 1
fi
echo
echo '== Instalacion de camara finalizada =='
