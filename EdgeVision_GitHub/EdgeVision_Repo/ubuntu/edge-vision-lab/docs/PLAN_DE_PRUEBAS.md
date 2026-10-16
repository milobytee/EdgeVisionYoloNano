> **ACTUALIZACIÓN 14/10/2026:** usa `docs/PRUEBAS_FINALES_Y_DEFENSA.md` para el procedimiento de respaldo en frío con una instancia única y las pruebas multimodales. Esta matriz corresponde al kit inicial y el esquema de dos servidores residentes ya no se utiliza.

> **Perfil de recursos (16 GB/4 GB):** las pruebas HA-01/HA-02 todavia no estan validadas; el fallback requiere un segundo servidor residente y podria exceder 7 GB de la VM. Para considerar la prueba aprobada, primero verificar la RAM con ambos servicios o implementar failover automatico bajo demanda y repetir la prueba fisica.

# Plan experimental — datos observados, no inventados

## Evidencia mínima de hardware y direccionamiento

| ID | Máquina | Comando | Debe mostrar |
|---|---|---|---|
| HW-01 | Pi | `uname -m; lscpu; free -h; cat /etc/os-release` | aarch64, RAM real, Linux 64-bit |
| HW-02 | VM | `uname -m; lscpu; free -h` | x86_64, asignación de vCPU/RAM |
| NW-01 | Ambos | `ip -4 a; ip route` | .10 y .20 /24; sin gateway privado |
| NW-02 | Ambos | `ping -c 5 IP_OTRO` | Sin pérdida local en condiciones normales |
| NW-03 | Pi | `ethtool NIC` | Negociación 1000Mb/s/full si compatible |
| NW-04 | VM→Pi | `iperf3 -c 192.168.100.20 -t 10` | Throughput real medido |

## Evidencia mínima de IA y cómputo

| ID | Experimento | Procedimiento | Aprobación |
|---|---|---|---|
| AI-01 | Multimodal local | Subir foto conocida y prompt de objetos | Respuesta pertinente, sin llamada a nube |
| AI-02 | Control local | Solo modelo VM (-ngl 0, sin RPC) | Medir latencia / CPU VM |
| AI-03 | RPC real | Worker + `-ngl` parcial; mismas fotos/prompts | Logs de offload RPC y trabajo del worker durante inferencia |
| AI-04 | 3–5 ejemplos distintos | Fotos de objetos y etiquetas | Registrar respuesta esperada y real; errores anotados |
| HA-01 | Worker apagado | Cerrar `ggml-rpc-server`; mantener respaldo completo | Nueva solicitud da `vm-fallback` + respuesta válida |
| HA-02 | Recuperación | Reactivar worker y reiniciar primario cuando haga falta | Nueva solicitud usa de nuevo ruta RPC |
| ISO-01 | Sin Internet | Deshabilitar NAT VM / Wi-Fi Pi; red privada viva | Inferencia funciona sin ruta WAN |
| SEC-01 | RPC aislado | Verificar firewall/bind privados | Port 50052 no accesible desde WAN |

## Formato de tabla para informe

| Foto | Esperado | Resultado observado | Ruta | Segundos | VM pico CPU % | Pi pico CPU % | Exitoso (criterio) |
|---|---|---|---|---:|---:|---:|---|
| objeto_a.jpg | ... | ... | rpc-primary | **medir** | **medir** | **medir** | Sí / Parcial / No |
| objeto_a.jpg | ... | ... | vm-fallback | **medir** | **medir** | **medir** | Sí / Parcial / No |

En caso de error, adjuntar la salida exacta y no rellenar con valores esperados. Una sola ejecución exitosa no valida disponibilidad, rendimiento ni precisión generalizable. Bajo CPU, generación puede tardar significativamente.

### Guion breve de demostración en clase (~5 minutos)

- 0:00–0:40: problema empresarial (tokens recurrentes / dependencia de nube), caso de uso subiendo imágenes.
- 0:40–1:25: piezas físicas en cámara, cableado por switch, 2 arquitecturas de CPU e IPs.
- 1:25–2:00: modelo Qwen3-VL cuantizado + componentes GGUF y RPC (con traza de offload).
- 2:00–3:10: cargar imagen real, ver respuesta y actividad simultánea de las CPU.
- 3:10–4:10: detener worker y mostrar nueva solicitud vía respaldo VM; documentar diferencia entre recuperación y reanudar sesión.
- 4:10–5:00: captura de aislamiento sin Internet, limitaciones y conclusión; todos los compañeros listos para preguntas.

### Capturas propuestas (nombrar y almacenar en carpeta evidencias)

- `01_fisico_switch_pi_laptop.jpg` (fotografía propia del cableado).
- `02_cpu_arquitectura_pi.png`, `03_cpu_arquitectura_vm.png`.
- `04_ip_privada_pi.png`, `05_ip_privada_vm.png`, `06_iperf.png`.
- `07_rpc_worker_start.png`, `08_llama_primary_capas_rpc.png`.
- `09_dos_cpu_en_uso.png` (dos sesiones/monitores visibles con carga correlacionada).
- `10_web_descripcion.png`, `11_respaldo_activo.png`, `12_sin_internet.png`.
- `benchmark_distribuido.json`, `benchmark_respaldo.json` y los logs de consola.
