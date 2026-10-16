#!/usr/bin/env bash
# Esperar solamente la IP privada; no se exige Internet ni puerta de enlace.
set -euo pipefail
for _ in $(seq 1 60); do
  if ip -4 -o addr show dev end0 | grep -Fq '192.168.100.20/24'; then
    exit 0
  fi
  sleep 2
done
echo 'No se encontro 192.168.100.20/24 en end0. Comprobar nmcli.' >&2
exit 1
