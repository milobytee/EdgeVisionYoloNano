#!/usr/bin/env bash
set -euo pipefail
BIN="${LLAMA_DIR:-$HOME/llama.cpp}/build/bin/ggml-rpc-server"
if [[ ! -x "$BIN" ]]; then echo "No se encuentra $BIN" >&2; exit 1; fi
export GGML_RPC_NO_RDMA=1
exec "$BIN" --host "${WORKER_IP:-192.168.100.20}" --port "${RPC_PORT:-50052}" --threads "${WORKER_THREADS:-4}"
