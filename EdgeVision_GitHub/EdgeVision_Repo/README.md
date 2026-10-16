# EdgeVision - proyecto academico (fuentes)

Clúster Edge Computing local: VM Ubuntu x86-64 (portal + llama.cpp/Qwen3-VL)
y Orange Pi 4 Pro ARM64 (YOLO-Nano + servidor RPC + observador).

## Estructura
- `ubuntu/edge-vision-lab/`: backend, HTML/JS, scripts, pruebas y documentacion.
- `orangepi/edgevision-camera/`: codigo de webcam/YOLO sin pesos ONNX.
- `orangepi/edgevision*.py`: agentes de telemetria y supervisor RPC.
- `orangepi/systemd/`: unidades systemd para revisar/adaptar.
- `docs/index.html`: pagina publica de presentacion estatica (no ejecuta IA).

## Ejecucion
La inferencia requiere los pesos Qwen3-VL GGUF, mmproj, modelo YOLO ONNX,
una instalacion local de llama.cpp compilada para x86-64 y ARM64 y la LAN privada.
Esos pesos, ejecutables y entornos virtuales NO se incluyen en el repositorio.
Documentar versiones, enlaces oficiales, licencias y hashes para reproducirlos.

## Resultados comprobados
- YOLO-Nano procesa video de webcam conectada a la Orange Pi.
- Qwen3-VL genera descripciones locales sin API de IA externa.
- El backend RPC distribuyo capas de Qwen2.5 y se observaron logs RPC0.
- Para afirmar Qwen3-VL distribuido en una solicitud: demostrar `rpc-primary`
  en inferencias.jsonl con la misma session_id en logs de asignacion RPC0.

## SEGURIDAD - revisar antes de publicar
No divulgar contrasenas, claves, tokens, fotos de personas, rutas privadas de
backups, certificados ni logs con peticiones reales. Este exportador EXCLUYE
rutas comunes, pero NO puede detectar todas las credenciales incrustadas
manualmente en scripts. Revisar TODO el contenido antes de hacer publico.

La aplicacion original no tiene autenticacion. Mantener RPC (50052), camera
(9200), observador (9101) y portal (8000) dentro de la LAN; publicar el portal
real solo tras incorporar autenticacion y controles de abuso.

Los fuentes de llama.cpp son de terceros: no se copian al repo, se documenta
la revision en `VERSION_LLAMA_CPP.txt` y se obtiene del repositorio original.
