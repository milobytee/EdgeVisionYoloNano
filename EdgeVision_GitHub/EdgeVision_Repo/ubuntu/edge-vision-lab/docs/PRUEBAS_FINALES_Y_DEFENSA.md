# EdgeVision — Guía final de pruebas, evidencias y defensa

Fecha del laboratorio: **14 de octubre de 2026**. Entrega comunicada en clase: **viernes 16 de octubre, antes de medianoche**; defensa **sábado 17 de octubre**. Consulta Canvas para confirmar el plazo exacto y los formatos de carga.

## 1. Lo que ya está demostrado y lo que falta probar

| Criterio | Evidencia obtenida hasta ahora | Próximo paso |
|---|---|---|
| Orange Pi ARM64 con 4 GB, Debian 12 | `uname -m=aarch64`, 8 núcleos, `free -h` | Captura de `lscpu` |
| VM Ubuntu x86-64 con 3 vCPU | `uname -m=x86_64`, `nproc=3` | Captura con RAM asignada |
| IP privadas y switch Gigabit | Ping en ambos sentidos, SSH y `ethtool` 1000Mb/s | Medir `iperf3` y hacer IP persistentes |
| Backend llama.cpp mismo commit | SHA `df18bee11e96557b07aa7b12db0976f3c7ac9165` | Guardar captura SHA en ambos nodos |
| Motor RPC en Orange Pi | Conexión TCP 50052 accesible | Captura del worker durante generación |
| Inferencia de texto local | ~10.4 tokens/s, Qwen2.5-0.5B | Guardar captura original |
| Inferencia de texto con RPC | ~8.6 tokens/s, RPC0 asignado, compute buffer RPC0 | Captura de CPU de ambos durante ejecución |
| Visión multimodal Qwen3-VL | **NO probada físicamente todavía** | Descarga, analiza 3 fotografías |
| Portal web | Código listo y 9 pruebas simuladas aprobadas | Abrir en Windows y subir imágenes |
| Recuperación ante caída de worker | Controlador de respaldo en frío implementado | **NO probada físicamente todavía** |
| Operación sin Internet | Diseño sin APIs externas de IA | Desactivar Wi-Fi Windows, comprobar WAN caída, analizar imagen |

### 2. Prueba multimodal de la feria

1. En la Orange Pi confirma que siga activo `ggml-rpc-server` y que la IP `192.168.100.20` responda desde Ubuntu. Si no está activo, en Orange Pi:

   ```bash
   tmux new-session -d -s edge-rpc "$HOME/llama.cpp/build/bin/ggml-rpc-server --host 192.168.100.20 --port 50052 --threads 4"
   ```

   Si ya existe `edge-rpc`, no crees una segunda sesión. Puedes revisar `tmux ls`.
2. Desde Windows inicia **Iniciar-EdgeVision.bat** (o desde Ubuntu `bash ~/edge-vision-lab/scripts/start.sh`). Espera que el portal muestre *Motor multimodal disponible* y **Ruta RPC + VM**. La carga inicial puede tardar 1–4 minutos, o más según CPU/almacenamiento.
3. Abre `http://192.168.137.128:8000` o la IP real que tenga Ubuntu. Si falla por la red puente, utiliza reenvío NAT `127.0.0.1:8000 → invitado:8000` en Adaptador 2.
4. Sube **fotografías propias de objetos cotidianos** (ejemplos: zapato, caja, botella, etiqueta; máximo 5 MB cada una). Si hay textos pequeños, usa una imagen con buena iluminación y comprueba el resultado, no presupongas OCR perfecto.
5. Pregunta: `Describe los tres objetos más importantes que aparecen en la imagen y cualquier texto legible. Si algo no se ve, indícalo.`
6. Captura la pantalla con **resultado real, duración, ruta RPC+VM, CPU VM y CPU Orange Pi**.
7. Compara respuesta con lo que **realmente** contiene la foto. Registra errores y limitaciones.

### 3. Prueba del Worker y tolerancia a fallos (cold failover)

1. Con una imagen ya analizada en modo RPC, abre una terminal SSH a Orange Pi, ejecuta `tmux ls` y localiza `edge-rpc`.
2. Simula la caída **solo del Worker**:

   ```bash
   tmux kill-session -t edge-rpc
   ```

3. Espera a que el portal indique que RPC está desconectado y cambia a **Solo VM**. El controlador termina su instancia distribuida y carga una instancia CPU local **en el mismo puerto** para no duplicar RAM. **Puede tardar varios minutos**.
4. Sube **una nueva imagen** y conserva captura donde aparezca `vm-fallback` y una respuesta válida. Esto prueba recuperación del servicio *para nuevas solicitudes*. No prueba continuidad sin pausa ni reanudación exacta de una inferencia interrumpida.
5. Vuelve a iniciar Worker en Orange Pi:

   ```bash
   tmux new-session -d -s edge-rpc "$HOME/llama.cpp/build/bin/ggml-rpc-server --host 192.168.100.20 --port 50052 --threads 4"
   ```

6. Desde el portal, pulsa **Reactivar RPC**, espera la recarga y analiza otra imagen.
7. Guarda `~/edge-vision-lab/evidencias/modelo-vlm.log`, `inferencias.jsonl` y captura del estado de la web. Si un error impide la recuperación, documentarlo y no anunciar tolerancia validada.

### 4. Prueba offline (sin Internet y SIN cambiar la red privada)

1. **Una vez descargados los modelos**, desconecta temporalmente el **Wi-Fi de Windows 11** y cualquier otra conexión a Internet de la laptop, conservando Realtek–switch–Orange Pi.
2. Comprueba que Ubuntu no tenga salida WAN: `ping -c 2 1.1.1.1` (debe fallar), pero `ping -c 2 192.168.100.20` sí funcione.
3. Abre el portal desde Windows usando Ethernet local (`192.168.137.128:8000` si mantiene esa IP) y analiza una imagen. El motor y el proyector ya están descargados; no hacen peticiones de inferencia a la nube.
4. Registra una captura tanto del `ping` WAN fallido como del portal respondiendo. Al terminar, restaura Wi-Fi si lo necesitas para otros trabajos.

**Importante:** desactivar solamente el NAT de VirtualBox no garantiza aislamiento si Windows sigue compartiendo Internet por Ethernet (`192.168.137.1`). Debes cortar la salida WAN de todos los caminos durante la prueba.

### 5. Cómo recoger evidencias por SSH sin repetir largas instrucciones

En Ubuntu (no en Windows):

```bash
bash ~/edge-vision-lab/scripts/recoger_evidencias.sh
bash ~/edge-vision-lab/scripts/status.sh
```

El reporte incluye rutas/IP, versión de Linux, estado del RPC y extractos del log. Si deseas mostrar métricas reales de Orange Pi en el portal, instala su monitor en una sola línea desde Ubuntu:

```bash
bash ~/edge-vision-lab/scripts/install_worker_metrics.sh
```

Toma fotos del montaje físico (laptop, switch de 5 puertos, CAT6, Orange Pi) y capturas del panel durante generación. La evidencia de carga de `RPC0` y `compute buffer` es evidencia de asignación; para ejecución efectiva combina **carga CPU y logs durante inferencia**.

### 6. Matriz académica de cumplimiento

| Elemento del material de clase | Resultado del proyecto |
|---|---|
| Reemplazar dependencia de IAaaS/tokens | Solo modelos GGUF locales y red propia para inferencia |
| Dos equipos heterogéneos conectados con switch | Orange Pi ARM64 y VM Ubuntu x86-64 |
| Comparten procesamiento CPU por red | `llama.cpp` con backend RPC; demostrar con logs y métricas |
| Subir imagen para interpretación por VLM | Qwen3-VL-2B + portal web; requiere demostración real |
| Caída de Worker sin dejar sin capacidad al sistema | Reinicio en modo CPU local para solicitudes nuevas, con demora |
| Redes privadas con IP fija | Direcciones definidas .10/.20; **aún no persistentes al reinicio** |
| Red local redundante | **NO**: un switch representa punto único de fallo físico |
| Caso 1 según PDF | **NO literal**: pide YOLO/MobileNet + cámara, mientras la clase acepta imagen subida al VLM |
| pfSense, VLAN y AIOps de algunos descriptores de rúbrica | No se implementaron; en clase pfSense fue descrito como opcional |

Solicita al profesor confirmación de la divergencia **VLM/cámara** y **VM frente a restricciones de hardware del PDF**. No declares literalmente todos los requisitos cumplidos sin esa validación.

### 7. Entregables exigidos

- **Informe técnico formal PDF** por grupo con portada, objetivos, diagrama, arquitectura física/lógica, elección del modelo, instalación reproducible, pruebas con datos reales, tiempos, capturas y conclusiones. Pasa el diseño al catedrático si aún puedes obtener revisión.
- **Presentación en vivo** (~5 min) y explicación individual de cada integrante (deben entender los nodos, el modelo, cómo viajan datos y cómo se recupera el sistema).
- **Video de demostración grupal** hasta unos 10 minutos para la feria virtual, **videos individuales** de 5–7 min conforme al PDF y **video de reflexión** según la clase. Confirmar publicación y permisos de acceso.
- **Autoevaluación y evaluación por pares**: cargar la hoja Excel original de Canvas; asignación 1–100 por persona, sin inventar notas ni miembros.
- **Entrega de Canvas por todos los integrantes**, según instrucciones del 10/oct.

### 8. Guion sugerido para defensa ~5 minutos

- **0:00–0:40**: problema: depender de APIs/tokens para analizar fotos.
- **0:40–1:30**: presentar Orange Pi ARM64, VM Ubuntu, switch Gigabit y direcciones IP.
- **1:30–2:00**: cuantización Q4, mmproj de visión Q8 y reparto RPC (mostrar capas RPC0).
- **2:00–3:20**: analizar una fotografía propia en web y observar recursos.
- **3:20–4:25**: detener Worker, mostrar recarga local y un resultado nuevo (si demora mucho, grabar evidencia previamente etiquetada).
- **4:25–5:00**: prueba offline, limitaciones reales y conclusión.

### 9. Resultados medidos (llenar después de la prueba multimodal)

| Imagen | Esperado | Respuesta real | Ruta | Segundos | CPU VM | CPU Pi | ¿Correcto? |
|---|---|---|---|---:|---:|---:|---|
| Foto 1 | Pendiente | Pendiente | rpc-primary | — | — | — | — |
| Foto 2 | Pendiente | Pendiente | rpc-primary | — | — | — | — |
| Foto 3 | Pendiente | Pendiente | vm-fallback | — | — | — | — |

No reemplazar valores faltantes con aproximaciones sin medición.
