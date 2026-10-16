# EdgeVision 2.0 — Guía de webcam USB, YOLO11-Nano y Qwen3-VL

## 1. Arquitectura física

```text
Webcam USB UVC
    |
    v
Orange Pi 4 Pro (Debian 12 ARM64, 4 GB RAM)
  |-- /dev/video* -> OpenCV VideoCapture/V4L2
  |-- yolo11n.onnx -> ONNX Runtime CPU, 2 hilos, FPS bajo
  |-- cámara HTTP local 192.168.100.20:9200
  |     |-- GET /status
  |     |-- GET /stream.mjpg   -> JPEG anotado (recuadros + clases)
  |     |-- GET /snapshot.jpg -> JPEG ORIGINAL sin recuadros
  |     |-- POST /pause /resume
  |-- ggml-rpc-server 192.168.100.20:50052 (independiente)
    |
    | switch Gigabit Ethernet + CAT6 (sin nube)
    v
Ubuntu VM x86_64 192.168.100.10
  |-- FastAPI EdgeVision :8000 (proxy de webcam, mismo origen)
  |-- Qwen3-VL Q4 + mmproj -> :8081 (loopback interno)
  |-- Qwen3-VL elige RPC + VM o respaldo Solo VM
    |
    v
Windows 11: navegador web EdgeVision
```

El procesamiento YOLO ocurre **en la Orange Pi**; no necesita `llama.cpp`. El VLM multimodal es el proceso separado coordinado por Ubuntu, que puede utilizar la CPU de la Orange Pi por RPC. La tasa de cámara se limita intencionalmente porque el equipo tiene 4 GB de RAM. El video MJPEG no equivale a video de 30 FPS: el objetivo inicial es aproximadamente 1 FPS, dependiente de rendimiento real.

## 2. Requisitos

- Webcam USB UVC que Linux detecte en `/dev/videoN`.
- Raspberry **no** es requerida: el nodo ARM es la Orange Pi 4 Pro ya configurada.
- Cuenta `orangepi`, SSH `orangepi@192.168.100.20`, con permisos de sudo.
- En Ubuntu, SSH funcional desde Windows (directo o NAT de VirtualBox).
- Internet **solo durante instalación** de pip y descarga del modelo ONNX; posteriormente la inferencia no necesita Internet.
- En Orange Pi: sistema con Python 3.11, kernel compatible con V4L2, acceso `sudo` a paquetes apt.

## 3. Instalar (preferido)

1. Conecta webcam a USB de **Orange Pi** y enciende Orange Pi y la VM.
2. En Windows descomprime ZIP completo y ejecuta `Actualizar-Camara-EdgeVision.bat`.
3. Confirma reinicio breve del portal y proporciona credenciales cuando se soliciten.
4. El script copiará los archivos y modelo ONNX desde Ubuntu a Orange Pi mediante SCP, instalará venv y arrancará `tmux` `edgevision-camera`.
5. Abre tu URL habitual de EdgeVision y selecciona la pestaña Cámara.

**Si falla la automatización SSH anidada**, desde Ubuntu (no Windows ni Orange Pi) ejecuta una sola línea:

```bash
bash ~/edge-vision-lab/scripts/install_camera_worker.sh
```

Ese script solamente instala el componente de cámara; no descarga Qwen ni recompila `llama.cpp`.

## 4. Diagnóstico y selección de dispositivo

Desde Orange Pi:

```bash
ls -l /dev/video*
v4l2-ctl --list-devices
tmux ls
tail -n 70 ~/edgevision-camera/camara.log
```

Si aparece `permission denied`:

```bash
sudo usermod -aG video orangepi
```

Luego **cierra y vuelve a abrir la sesión SSH**. Reinicia la sesión de cámara:

```bash
tmux kill-session -t edgevision-camera
# Si tu webcam es /dev/video2:
CAMERA_DEVICE=/dev/video2 tmux new-session -d -s edgevision-camera "CAMERA_DEVICE=/dev/video2 bash ~/edgevision-camera/start.sh >> ~/edgevision-camera/camara.log 2>&1"
```

Para seleccionar el dispositivo de modo persistente, modifica en la Orange Pi `~/edgevision-camera/start.sh` (valor `CAMERA_DEVICE`), o guarda la variable en un script de arranque local. Con `auto`, el servicio escanea `/dev/video0` a `/dev/video5` y toma la primera interfaz que realmente entregue fotogramas.

Para validar:

```bash
curl --noproxy '*' -sS http://192.168.100.20:9200/status
curl --noproxy '*' -f -o /tmp/camara.jpg http://192.168.100.20:9200/snapshot.jpg
```

- `service_reachable` en el portal indica disponibilidad del puerto, no fotogramas.
- `"online": true` indica que recibió fotogramas recientes. Si no hay webcam, muestra un error.
- `"paused": true` aparece durante la inferencia Qwen3-VL porque se liberan los hilos de detección.

## 5. Qué pruebo para entregar

**A. YOLO físico**: graba en video la webcam conectada por USB a Orange Pi. Muestra `v4l2-ctl --list-devices`, la pantalla del navegador con el streaming anotado y la pantalla de CPU Orange Pi (opcional). Captura al menos 3 objetos con clases y confianza; anota FPS medido. No inventes detecciones ni precisión.

**B. Multimodal desde webcam**: pulsa «Capturar y analizar con Qwen3-VL», muestra la imagen original, consulta el texto generado y guarda evidencia con modo `RPC + VM` o `Solo VM` correctamente etiquetado. Si el VLM está solo en VM, **no atribuyas sus cálculos a RPC**.

**C. Red y autonomía**: después de instalar todo, deshabilita temporalmente Internet pero conserva Ethernet del switch y las IP privadas. Usa las dos modalidades; muestra que la inferencia no llama APIs de nube. Documenta cómo se restituyó Internet.

**D. Fallo del Worker RPC**: detener solamente `ggml-rpc-server` en Orange Pi; esperar a que el portal cambie el VLM a `Solo VM`; ejecutar un análisis y guardar la respuesta. La webcam ONNX es un servicio diferente y puede continuar trabajando: **no equivale a HA de la webcam**.

**E. Formalidades**: informe de arquitectura, resultados y métricas, video principal, participación de equipo, autoevaluaciones y valoración por pares según la clase. Se menciona en documentos una discrepancia entre el PDF (YOLO con cámara) y la clase (VLM con imagen cargada): **esta actualización permite demostrar ambos**.

## 6. Configuración y rendimiento

Valores iniciales en `camera_worker/start.sh`:

| Parámetro | Valor predeterminado |
|---|---|
| `CAMERA_DEVICE` | auto |
| `CAMERA_BIND` | 192.168.100.20 |
| `CAMERA_PORT` | 9200 |
| `CAMERA_TARGET_FPS` | 1 (máximo configurable 4) |
| `CAMERA_ONNX_THREADS` | 2 |
| `CAMERA_CONFIDENCE` | 0.40 |
| Modelo | YOLO11n ONNX FP32 estático 640×640 |

La cámara captura inicialmente a 640×480; el detector aplica letterbox 640×640, decodifica las cajas de salida de YOLO `[1,84,8400]`, realiza NMS por clase, dibuja recuadros y publica MJPEG. No instala PyTorch sobre ARM64.

Con CPU limitada, el FPS real puede ser mucho menor de 1; se mide en `/status`. El coste real de inferencia de la webcam compite con el procesamiento RPC del VLM si ocurren simultáneamente. Por ello, el portal pausa YOLO cuando se solicita el análisis multimodal y lo reanuda al concluir. La recuperación del VLM continúa siendo en frío.

## 7. Fuente y licencia del modelo

- Modelo: `yolo11n.onnx` (YOLO11-Nano, Ultralytics, 80 clases COCO).
- Repositorio y archivo preexportado: https://huggingface.co/unileon-robotics/YOLO11-ONNX/blob/main/yolo11n.onnx
- Descarga automatizada: https://huggingface.co/unileon-robotics/YOLO11-ONNX/resolve/main/yolo11n.onnx
- SHA-256 **esperado**: `36a10d3faf914feaf0f4e813d5635c26762cc71e54eff14c40cef8dba5b8a70d`
- Licencia del modelo: **AGPL-3.0** (consulta documentación del repositorio y https://www.ultralytics.com/license). Revisa requisitos antes de usar en aplicaciones empresariales no abiertas.
- ONNX Runtime: https://onnxruntime.ai/; OpenCV: https://opencv.org/.

**No se incluye el archivo ONNX dentro del ZIP**; la instalación valida el SHA del descargado. El servidor de cámara y el portal no disponen de autenticación: limitar uso a red privada y no hacer port-forward externo. La webcam no se graba permanentemente en disco; se almacenan fotogramas JPEG en memoria y una captura solo en el navegador al solicitarla.
