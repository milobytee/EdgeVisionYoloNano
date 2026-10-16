#!/usr/bin/env bash
set -euo pipefail
# Run separately on VM (x86-64) and Orange Pi (aarch64), always the same Git commit.
sudo apt-get update
sudo apt-get install -y git cmake ninja-build build-essential libcurl4-openssl-dev libssl-dev pkg-config ccache
LLAMA_DIR="${LLAMA_DIR:-$HOME/llama.cpp}"
if [ ! -d "$LLAMA_DIR/.git" ]; then
  git clone https://github.com/ggml-org/llama.cpp.git "$LLAMA_DIR"
fi
if [ -n "${LLAMA_COMMIT:-}" ]; then
  git -C "$LLAMA_DIR" fetch --tags
  git -C "$LLAMA_DIR" checkout "$LLAMA_COMMIT"
fi
cmake -S "$LLAMA_DIR" -B "$LLAMA_DIR/build" -G Ninja \
  -DGGML_RPC=ON -DGGML_NATIVE=ON -DCMAKE_BUILD_TYPE=Release
# ARM SBC: limit simultaneous compiler processes to avoid OOM.
CORES="$(nproc)"
if [ "$(uname -m)" = "aarch64" ]; then
  if [ "$CORES" -gt 2 ]; then CORES=2; fi
elif [ "$CORES" -gt 3 ]; then
  CORES=3
fi
cmake --build "$LLAMA_DIR/build" --config Release --parallel "$CORES" \
  --target llama-server llama-cli ggml-rpc-server
printf '\nCompilado. Revision: '
git -C "$LLAMA_DIR" rev-parse --short HEAD
printf 'Binarios: %s/build/bin\n' "$LLAMA_DIR"
