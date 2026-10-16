#!/usr/bin/env bash
set -uo pipefail
HOST=192.168.100.20
printf '\n== Servicios systemd ==\n'
for service in edgevision-rpc edgevision-camera edgevision-metrics; do
  systemctl is-active "${service}.service" || true
done
printf '\n== Puertos ==\n'
ss -ltn | grep -E ':50052|:9200|:9100' || true
printf '\n== RPC 50052 ==\n'
if timeout 3 bash -c "echo >/dev/tcp/$HOST/50052" >/dev/null 2>&1; then echo 'RPC accesible'; else echo 'RPC no responde'; fi
printf '\n== Camara 9200 ==\n'
curl --noproxy '*' -fsS --max-time 5 "http://$HOST:9200/status" || true
printf '\n\n== Monitor 9100 ==\n'
curl --noproxy '*' -fsS --max-time 5 "http://$HOST:9100/metrics" || true
printf '\n'
