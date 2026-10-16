#!/usr/bin/env bash
# EdgeVision 2.0.1: recover YOLO download with SHA256 verification.
# Execute on Ubuntu VM; DOES NOT stop/restart the multimodal portal.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PI="${PI_SSH:-orangepi@192.168.100.20}"
MODEL_DIR="$ROOT/camera_worker/models"
MODEL="$MODEL_DIR/yolo11n.onnx"
PART="$MODEL.part"
MODEL_URL='https://huggingface.co/unileon-robotics/YOLO11-ONNX/resolve/main/yolo11n.onnx'
# Both file digests were individually published in the upstream model page.
# Never accept a downloaded model that does not match one of these.
MODEL_SHA_V1='36a10d3faf914feaf0f4e813d5635c26762cc71e54eff14c40cef8dba5b8a70d'
MODEL_SHA_V2='baeb4c1d6f3bb460689823cc2d40daa31e6156f2517fcd48aab0db9490d9f4e5'
verify_model() {
  [[ -f "$1" ]] || return 1
  local got
  got="$(sha256sum "$1" | awk '{print $1}')"
  case "$got" in
    "$MODEL_SHA_V1"|"$MODEL_SHA_V2")
      echo "Modelo verificado: SHA256=$got"; return 0;;
    *) echo "SHA256 NO COINCIDE: $got ($1)"; return 1;;
  esac
}
mkdir -p "$MODEL_DIR"
echo '== EdgeVision 2.0.1: comprobacion segura de modelo YOLO =='
if verify_model "$MODEL"; then
  echo 'Modelo ya verificado; omitiendo descarga.'
elif verify_model "$PART"; then
  echo 'Recuperando descarga anterior valida.'
  mv -f "$PART" "$MODEL"
else
  rm -f "$PART"
  echo 'Descargando modelo YOLO11n desde unileon-robotics/Hugging Face...'
  curl -fL --retry 4 --retry-delay 2 --connect-timeout 25 \
    -o "$PART" "$MODEL_URL"
  if ! verify_model "$PART"; then
    echo 'ERROR: El archivo no coincide con las dos versiones oficiales conocidas.' >&2
    echo "No se instalara el archivo no validado: $PART" >&2
    echo 'Envia este diagnostico: sha256sum del .part y tamaño del archivo.' >&2
    exit 2
  fi
  mv -f "$PART" "$MODEL"
fi
verify_model "$MODEL"
printf '== Enviando modelo y servicio a %s ==\n' "$PI"
ssh -o ConnectTimeout=12 "$PI" 'mkdir -p ~/edgevision-camera'
scp -o ConnectTimeout=12 \
  "$ROOT/camera_worker/camera_service.py" \
  "$ROOT/camera_worker/start.sh" \
  "$ROOT/camera_worker/install.sh" \
  "$ROOT/camera_worker/requirements.txt" \
  "$MODEL" "$PI:~/edgevision-camera/"
ssh -tt -o ConnectTimeout=12 "$PI" 'bash ~/edgevision-camera/install.sh'
echo '== YOLO instalado en Orange Pi; portal Qwen3-VL NO fue reiniciado. =='
