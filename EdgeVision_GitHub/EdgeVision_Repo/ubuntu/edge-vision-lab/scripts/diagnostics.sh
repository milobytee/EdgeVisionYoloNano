#!/usr/bin/env bash
set -uo pipefail
printf '=== HOST ===\n'
uname -a
printf '\n=== ARQUITECTURA Y CPU ===\n'
uname -m
lscpu | sed -n '1,18p'
printf '\n=== RAM ===\n'
free -h
printf '\n=== IPS ===\n'
ip -br -4 addr
printf '\n=== RUTAS ===\n'
ip route
printf '\n=== ENLACE ETHERNET ===\n'
ip -br link
printf '\n=== DISCO ===\n'
df -h /
printf '\n=== RED ===\n'
ping -c 2 -W 2 "${PEER_IP:-192.168.100.20}" || true
printf '\n=== RPC TCP ===\n'
python3 - <<'PY'
import socket
try:
    socket.create_connection(('192.168.100.20',50052),timeout=2).close()
    print('OK: worker RPC acepta TCP')
except OSError as exc:
    print('SIN RPC:',exc)
PY
printf '\n=== SERVICIOS ===\n'
for p in 8000 8081 8082 9100; do
  curl --connect-timeout 1 --max-time 2 -s -o /dev/null -w "127.0.0.1:$p HTTP %{http_code}\n" "http://127.0.0.1:$p/health" || true
done
