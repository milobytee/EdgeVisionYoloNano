#!/usr/bin/env bash
# EdgeVision 2.0.4: migracion segura de tmux a systemd en Orange Pi.
# No modifica GGUF, ONNX, YOLO, llama.cpp, portal, IP, ni los servicios Ubuntu.
set -Eeuo pipefail

PI_HOME=/home/orangepi
BASE="$PI_HOME/edgevision-start204"
STAGE="$BASE/pi-services"
SERVICES=(edgevision-rpc edgevision-camera edgevision-metrics)
BACKUP="$BASE/respaldo-units-$(date +%Y%m%d-%H%M%S)"
HAD_RPC_TMUX=0
HAD_CAM_TMUX=0
HAD_METRICS_TMUX=0
TRANSITION_STARTED=0
declare -A PREV_ACTIVE=()
declare -A PREV_ENABLED=()

say() { printf '\n[EdgeVision 2.0.4] %s\n' "$*"; }
port_listening() { ss -H -ltn "( sport = :$1 )" | grep -q .; }
service_active() { systemctl is-active --quiet "${1}.service"; }
session_exists() { tmux has-session -t "$1" 2>/dev/null; }

restore_tmux() {
  if [[ "$HAD_RPC_TMUX" == 1 ]] && ! session_exists edge-rpc; then
    tmux new-session -d -s edge-rpc "GGML_RPC_NO_RDMA=1 $PI_HOME/llama.cpp/build/bin/ggml-rpc-server --host 192.168.100.20 --port 50052 --threads 4 >> $PI_HOME/edgevision-rpc.log 2>&1" || true
  fi
  if [[ "$HAD_CAM_TMUX" == 1 ]] && ! session_exists edgevision-camera; then
    tmux new-session -d -s edgevision-camera "bash $PI_HOME/edgevision-camera/start.sh >> $PI_HOME/edgevision-camera/camara.log 2>&1" || true
  fi
  if [[ "$HAD_METRICS_TMUX" == 1 ]] && ! session_exists edgevision-metrics; then
    tmux new-session -d -s edgevision-metrics "python3 $PI_HOME/edgevision-worker-metrics.py --bind 192.168.100.20 --port 9100" || true
  fi
}

rollback() {
  local code="$?"
  trap - ERR
  echo >&2
  echo "ERROR: instalacion incompleta (codigo $code). Revirtiendo servicios instalados..." >&2
  for name in "${SERVICES[@]}"; do
    sudo systemctl stop "${name}.service" >/dev/null 2>&1 || true
    sudo systemctl disable "${name}.service" >/dev/null 2>&1 || true
  done
  if [[ -d "$BACKUP" ]]; then
    for name in "${SERVICES[@]}"; do
      path="/etc/systemd/system/${name}.service"
      if [[ -f "$BACKUP/${name}.service" ]]; then
        sudo cp -a "$BACKUP/${name}.service" "$path" || true
      else
        sudo rm -f "$path" || true
      fi
    done
    sudo systemctl daemon-reload || true
    for name in "${SERVICES[@]}"; do
      if [[ "${PREV_ENABLED[$name]:-0}" == 1 ]]; then sudo systemctl enable "${name}.service" >/dev/null 2>&1 || true; fi
      if [[ "${PREV_ACTIVE[$name]:-0}" == 1 ]]; then sudo systemctl start "${name}.service" >/dev/null 2>&1 || true; fi
    done
  fi
  if [[ "$TRANSITION_STARTED" == 1 ]]; then
    restore_tmux
  fi
  echo 'El codigo del modelo, la webcam y el portal no se modificaron.' >&2
  echo "Registros: sudo journalctl -u edgevision-camera -u edgevision-rpc -u edgevision-metrics -n 80 --no-pager" >&2
  exit "$code"
}
trap rollback ERR

say 'Prevalidaciones sin alterar servicios'
[[ "$(id -un)" == orangepi ]] || { echo 'Ejecutar como usuario orangepi' >&2; exit 2; }
[[ -x "$PI_HOME/llama.cpp/build/bin/ggml-rpc-server" ]] || { echo 'Falta binario RPC' >&2; exit 2; }
[[ -r "$PI_HOME/edgevision-camera/start.sh" ]] || { echo 'Falta start.sh de camara' >&2; exit 2; }
[[ -x "$PI_HOME/edgevision-camera/.venv/bin/python" ]] || { echo 'Falta venv de YOLO (no reinstalar)' >&2; exit 2; }
[[ -s "$PI_HOME/edgevision-camera/yolo11n.onnx" ]] || { echo 'Falta modelo YOLO' >&2; exit 2; }
[[ -r "$PI_HOME/edgevision-camera/camera_service.py" ]] || { echo 'Falta servicio webcam' >&2; exit 2; }
[[ -r "$BASE/scripts/worker_metrics.py" ]] || { echo 'Falta archivo de metricas' >&2; exit 2; }
for name in "${SERVICES[@]}"; do
  [[ -r "$STAGE/${name}.service" ]] || { echo "Falta $STAGE/${name}.service" >&2; exit 2; }
done
bash "$BASE/scripts/esperar_ip.sh"

# Nunca tomar puertos pertenecientes a otros gestores/procesos no reconocidos.
if port_listening 50052 && ! session_exists edge-rpc && ! service_active edgevision-rpc; then
  echo 'Puerto 50052 ocupado fuera de tmux edge-rpc/systemd. No se detiene el proceso ajeno.' >&2; exit 3
fi
if port_listening 9200 && ! session_exists edgevision-camera && ! service_active edgevision-camera; then
  echo 'Puerto 9200 ocupado fuera de tmux edgevision-camera/systemd. No se detiene el proceso ajeno.' >&2; exit 3
fi
if port_listening 9100 && ! session_exists edgevision-metrics && ! service_active edgevision-metrics; then
  echo 'Puerto 9100 ocupado fuera de tmux edgevision-metrics/systemd. No se detiene el proceso ajeno.' >&2; exit 3
fi

for name in "${SERVICES[@]}"; do
  target="/etc/systemd/system/${name}.service"
  if [[ -f "$target" ]] && ! grep -q 'Managed by EdgeVision 2.0.4' "$target"; then
    echo "Ya existe un servicio ajeno $target. No se sobrescribe." >&2; exit 4
  fi
done
say 'Validar sintaxis systemd y solicitar permisos sudo'
sudo -v
sudo systemd-analyze verify "${STAGE}/edgevision-rpc.service" "${STAGE}/edgevision-camera.service" "${STAGE}/edgevision-metrics.service"

if session_exists edge-rpc; then HAD_RPC_TMUX=1; fi
if session_exists edgevision-camera; then HAD_CAM_TMUX=1; fi
if session_exists edgevision-metrics; then HAD_METRICS_TMUX=1; fi

for name in "${SERVICES[@]}"; do
  if service_active "$name"; then PREV_ACTIVE[$name]=1; fi
  if systemctl is-enabled --quiet "${name}.service" 2>/dev/null; then PREV_ENABLED[$name]=1; fi
done
mkdir -p "$BACKUP"
for name in "${SERVICES[@]}"; do
  target="/etc/systemd/system/${name}.service"
  if [[ -f "$target" ]]; then sudo cp -a "$target" "$BACKUP/"; fi
done
# Guarda detalle del respaldo para auditoria (sin credenciales).
printf 'fecha=%s\ntmux_rpc=%s\ntmux_camera=%s\ntmux_metrics=%s\n' "$(date -Iseconds)" "$HAD_RPC_TMUX" "$HAD_CAM_TMUX" "$HAD_METRICS_TMUX" > "$BACKUP/contexto.txt"
cp "$BASE/scripts/worker_metrics.py" "$PI_HOME/edgevision-worker-metrics.py"
chmod 644 "$PI_HOME/edgevision-worker-metrics.py"

say 'Instalar unidades. Los procesos tmux aun no han sido detenidos.'
for name in "${SERVICES[@]}"; do
  sudo install -m 0644 "$STAGE/${name}.service" "/etc/systemd/system/${name}.service"
done
sudo systemctl daemon-reload
sudo systemctl enable edgevision-rpc.service edgevision-camera.service edgevision-metrics.service

say 'Transferir control desde tmux a systemd (se interrumpen los servicios unos segundos)'
TRANSITION_STARTED=1
for name in edge-rpc edgevision-camera edgevision-metrics; do
  if session_exists "$name"; then tmux kill-session -t "$name"; fi
done
sleep 2
for name in "${SERVICES[@]}"; do sudo systemctl restart "${name}.service"; done

say 'Esperando respuesta de puertos RPC 50052, webcam 9200 y monitor 9100'
all_healthy=0
for attempt in $(seq 1 55); do
  rpc_ok=0; camera_ok=0; metrics_ok=0
  if timeout 2 bash -c 'echo >/dev/tcp/192.168.100.20/50052' >/dev/null 2>&1; then rpc_ok=1; fi
  if curl --noproxy '*' -fsS --max-time 3 http://192.168.100.20:9200/status 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin);sys.exit(0 if d.get("online") else 1)' 2>/dev/null; then camera_ok=1; fi
  if curl --noproxy '*' -fsS --max-time 3 http://192.168.100.20:9100/metrics 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin);sys.exit(0 if "cpu_percent" in d and "memory_percent" in d else 1)' 2>/dev/null; then metrics_ok=1; fi
  if [[ "$rpc_ok" == 1 && "$camera_ok" == 1 && "$metrics_ok" == 1 ]]; then all_healthy=1; break; fi
  if [[ "$attempt" -eq 1 || $((attempt % 10)) -eq 0 ]]; then
    printf 'Comprobacion %s: RPC=%s YOLO=%s METRICAS=%s\n' "$attempt" "$rpc_ok" "$camera_ok" "$metrics_ok"
  fi
  sleep 2
done
if [[ "$all_healthy" != 1 ]]; then
  sudo journalctl -u edgevision-camera -u edgevision-rpc -u edgevision-metrics -n 35 --no-pager || true
  echo 'No estuvieron saludables los tres servicios dentro del tiempo de espera.' >&2
  false # Dispara el rollback por ERR, no deja el servicio a medias.
fi

say 'Exito: servicios activos y persistentes'
for name in "${SERVICES[@]}"; do
  echo "${name}.service: $(systemctl is-active "${name}.service") / $(systemctl is-enabled "${name}.service")"
done
bash "$BASE/scripts/verificar_pi.sh"
printf '\nRespaldo guardado en: %s\n' "$BACKUP"
echo 'Qwen3-VL y el portal en Ubuntu se mantuvieron intactos.'
echo 'Si el portal muestra Solo VM, pulsa Reactivar RPC cuando no este analizando imagenes.'
