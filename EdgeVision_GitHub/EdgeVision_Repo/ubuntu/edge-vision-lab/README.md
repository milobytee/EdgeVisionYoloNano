# EdgeVision 1.0 — Demo de IA multimodal local con Orange Pi 4 Pro

**Proyecto listo para instalar en Ubuntu Server (VM), pero todavía necesita validación física con el modelo multimodal y la Orange Pi.** El backend fue probado con servicios simulados, no sobre el hardware del usuario.

## Hardware y progreso real (14/oct/2026)

- Laptop Windows 11, RAM 16 GB, 6 núcleos. VirtualBox con VM Ubuntu Server x86-64, 3 vCPU, RAM observada 8 GiB.
- Orange Pi 4 Pro, Linux Debian Bookworm ARM64, 8 núcleos, 4 GB RAM, conectada por switch Gigabit CAT6.
- VM `192.168.100.10`, Orange Pi `192.168.100.20`, comunicación Ping/SSH confirmada (direcciones aún **no persistentes**).
- Compilación `llama.cpp` con RPC en ambas arquitecturas completada con revisión Git `df18bee11e96557b07aa7b12db0976f3c7ac9165`.
- Inferencia **texto** Qwen2.5-0.5B exitosa: 10.4 tok/s local y 8.6 tok/s con RPC; trazas previas de `RPC0`, buffer de cómputo remoto y asignación de capas. Visión todavía no validada.

## Arranque inmediato sin comandos largos

1. Extrae el ZIP de esta entrega **en Windows**. Lee primero `LEEME_PRIMERO.md` en la raíz del ZIP.
2. Ejecuta `Instalar-EdgeVision.bat` desde Windows. Detecta SSH (directo o NAT) y copia `edge-vision-lab/` a Ubuntu. En Ubuntu instala venv y descarga `Qwen3VL-2B-Instruct-Q4_K_M.gguf` (~1.11 GB) y `mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf` (~445 MB).
3. La opción de monitoreo configura un mini-servicio Python en la Orange Pi mediante su SSH; también se puede ejecutar después.
4. El instalador inicia la aplicación con `tmux` y deja un único `llama-server` bajo control de FastAPI. Abre `http://192.168.137.128:8000` desde Windows, si ésa sigue siendo la IP de Ubuntu. Si no, revisa `ip -4 -br addr` y usa su IP actual. Alternativa: reenvío NAT puerto 8000 a `127.0.0.1:8000` de Windows.
5. Para encender luego de reiniciar, ejecuta `Iniciar-EdgeVision.bat` sin reinstalar. El motor local solo se carga una vez.

## Aplicación y tolerancia a fallos

El usuario selecciona una imagen y envía un prompt; la web la valida, reduce a 640px, la entrega como Base64 JPEG a la API local de `llama-server` en 127.0.0.1:8081, y presenta la respuesta del VLM. No se llama a servicios externos de IA.

`backend/engine.py` administra **un solo proceso de modelo** (para ahorrar RAM). Prefiere distribuir capas del VLM por RPC a la Orange Pi (`--rpc 192.168.100.20:50052 -ngl 8`) y procesa otras capas en la VM. El componente visual `mmproj` se ejecuta en CPU local. Si la Orange Pi deja de responder, detiene el modelo primario, **carga un modelo completo en CPU VM** y vuelve a procesar la solicitud. El cambio puede durar minutos (respaldo en frío, no alta disponibilidad sin interrupción). El retorno al modo RPC es manual desde la interfaz para no interrumpir respuestas.

La capacidad de distribuir Qwen3-VL (no solo Qwen2.5 de texto) **debe probarse físicamente**: el funcionamiento de RPC con un VLM depende de la versión de `llama.cpp` y recursos CPU/RAM. Si RPC del VLM falla, el controlador intentará responder en CPU local y registrará el error; no inventará éxito.

## Parámetros de recursos

- Modelo Qwen3-VL 2B Q4 + mmproj Q8: ambos archivos se descargan a `~/edge-vision-models`.
- Contexto inicial: `4096` tokens, imagen máximo `512` tokens dinámicos, imagen de entrada reducida a máximo `640×640`. Esto previene errores de contexto frecuentes con visión.
- VM: 3 hilos CPU, 8 capas remotas (`RPC_LAYERS=8`), un solo slot, lotes de 512. Si el rendimiento falla, disminuir `RPC_LAYERS` y registrar el nuevo valor.
- Registro de asignación: `evidencias/modelo-vlm.log`; resumen de solicitudes: `evidencias/inferencias.jsonl` (no se conserva imagen original).
- El Worker RPC utiliza TCP puerto 50052 **solo en la red privada**. El servidor web escucha en el puerto 8000 en la VM, sin autenticación: no exponerlo a Internet.

## Archivos clave

```text
edge-vision-lab/
├── backend/
│   ├── engine.py                # proceso único + failover en frío
│   ├── main.py                  # API FastAPI para subir imagen, estado y cambios de modo
│   ├── static/index.html        # interfaz web sin dependencias externas
│   ├── requirements.txt
│   └── .env.example             # configuración de recursos
├── scripts/
│   ├── install_vm.sh            # Python venv, descarga GGUF, unit tests
│   ├── download_model.sh        # pesos y mmproj del repositorio de Qwen
│   ├── run_web.sh               # iniciar API + motor
│   ├── start.sh                 # arranque simplificado con tmux
│   ├── status.sh                # diagnóstico
│   ├── stop.sh                  # apagar portal
│   ├── install_worker_metrics.sh# instalar monitor en Orange Pi
│   ├── worker_metrics.py        # CPU/memoria en Orange Pi
│   ├── recoger_evidencias.sh    # capturas de estado, consola y logs
│   └── benchmark.py             # latencia de 3 fotos reales
├── tests/test_api.py            # 9 pruebas automatizadas sin hardware
├── docs/PRUEBAS_FINALES_Y_DEFENSA.md
├── docs/REQUISITOS_Y_ENTREGABLES.md
└── evidencias/                   # resultados reales en el equipo del usuario
```

## Pruebas automatizadas

Ejecutadas al preparar el paquete: 9/9 aprobadas. Incluyen validación de imágenes, HTTP, clasificación de ruta, caída simulada del primario y recuperación de la respuesta desde un backend falso. **No sustituyen la prueba real de Qwen3-VL y RPC**.

## Vacíos frente a la rúbrica y la clase

- El **PDF, página 2**, exige en el caso de visión YOLO/MobileNet, cámara directa y clasificación/detección en tiempo real. La **clase** autorizó la interpretación de imágenes subidas al VLM. Se recomienda confirmar al profesor que sustituir el caso escrito por el VLM elegido es válido.
- El PDF restringe el tipo de hardware y plantea redundancia de red, mientras que la clase permite una VM sobre laptop y se dispone de un solo switch. La **red no es físicamente redundante**.
- Las IP se agregaron con `ip addr add` y **aún no son persistentes**. Es importante corregirlas usando NetworkManager/Netplan antes de la entrega. No ejecutamos un cambio remoto automático por el riesgo de desconectar SSH sin conocer los perfiles actuales.
- Aún se requieren resultados de precisión y tiempos **medidos**, prueba de caída del Worker, prueba sin Internet, informe formal PDF, video(s), evaluación de pares y autoevaluación.

Más información en `docs/PRUEBAS_FINALES_Y_DEFENSA.md`. No modificar ni borrar el proyecto original `~/llama.cpp` que el usuario ya compiló.

## ACTUALIZACIÓN 2.0 (14/oct/2026): webcam USB + YOLO11-Nano

Esta versión **conserva toda la funcionalidad de Qwen3-VL y RPC** y añade en la Orange Pi un proceso independiente de detección por webcam USB con YOLO11n ONNX CPU. El portal incorpora la segunda pestaña «Cámara en vivo · YOLO-Nano», recuadros con clasificación/confianza, FPS medido y botones «Capturar fotograma» y «Capturar y analizar con Qwen3-VL».

**Para actualizar una instalación existente desde Windows, utiliza exclusivamente `Actualizar-Camara-EdgeVision.bat`.** No hace falta reinstalar Qwen3-VL ni recompilar `llama.cpp`. Este instalador copiará el backend actualizado, reiniciará la web, descargará/validará el modelo pequeño ONNX y configurará el servicio de cámara en Orange Pi. Ver `LEEME_PRIMERO.md` en la raíz del ZIP y `docs/GUIA_CAMARA_YOLO.md`.

Estado del código: pruebas automatizadas del backend y lógica YOLO ejecutadas con servicios/cámara simulados; **funcionamiento físico de la webcam USB y su tasa FPS reales pendientes de validación en el hardware del usuario**. No sustituye las evidencias de entrega.
