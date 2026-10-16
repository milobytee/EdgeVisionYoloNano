#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then echo 'Falta .venv; ejecuta scripts/install_vm.sh primero.' >&2; exit 1; fi
export EDGE_AUTO_ENGINE=true
# ModelEngine escucha exclusivamente en 127.0.0.1:8081. Portal visible por LAN privada de la VM.
exec .venv/bin/python -m uvicorn backend.main:app --host "${WEB_BIND:-0.0.0.0}" --port "${WEB_PORT:-8000}" --workers 1
