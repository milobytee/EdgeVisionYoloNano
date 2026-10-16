#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HF="$ROOT/.venv/bin/hf"
MODELS_DIR="${MODELS_DIR:-$HOME/edge-vision-models}"
if [[ ! -x "$HF" ]]; then echo "No se encontró $HF. Primero ejecuta install_vm.sh"; exit 1; fi
mkdir -p "$MODELS_DIR"
echo 'Descargando 2 archivos (~1.55 GB) desde Hugging Face; requieren Internet solo durante instalación.'
"$HF" download Qwen/Qwen3-VL-2B-Instruct-GGUF Qwen3VL-2B-Instruct-Q4_K_M.gguf --local-dir "$MODELS_DIR"
"$HF" download Qwen/Qwen3-VL-2B-Instruct-GGUF mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf --local-dir "$MODELS_DIR"
ls -lh "$MODELS_DIR"/*.gguf
python3 - "$MODELS_DIR" <<'PY'
from pathlib import Path
import sys
folder = Path(sys.argv[1])
for filename, minimal in [('Qwen3VL-2B-Instruct-Q4_K_M.gguf', 950_000_000),
                          ('mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf', 350_000_000)]:
    path = folder / filename
    if not path.is_file() or path.stat().st_size < minimal:
        raise SystemExit(f'ERROR: archivo ausente o incompleto: {path}')
print('Ambos archivos tienen un tamaño consistente con la descarga esperada.')
PY
