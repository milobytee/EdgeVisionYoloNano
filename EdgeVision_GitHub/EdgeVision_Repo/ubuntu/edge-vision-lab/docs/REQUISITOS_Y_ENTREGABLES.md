> **ACTUALIZACIÓN AL 14/10/2026:** este documento es una matriz histórica del kit inicial, cuando aún faltaba instalar los equipos. Actualmente ya se han confirmado: Debian ARM64 en Orange Pi, Ubuntu VM x86-64, Ping/SSH, compilación de llama.cpp con RPC en ambas CPU, y asignación RPC0 con Qwen2.5-0.5B de texto. **Quedan pendientes las pruebas físicas con Qwen3-VL, continuidad al apagar Worker, operación offline, IP persistentes e informe y videos.** Para el plan actualizado utiliza `docs/PRUEBAS_FINALES_Y_DEFENSA.md`.

> **Configuracion confirmada 2026-10-10:** Windows 11 16 GB RAM/6 nucleos, Orange Pi 4 Pro 4 GB sin OS; VM estimada 7168 MB RAM/3 vCPU. Ver `docs/PERFIL_16GB_4GB_Y_ETAPA1.md`. El cumplimiento de inferencia distribuida y HA requiere pruebas en ambos equipos; no esta validado aun.

# Matriz de cumplimiento y defensa académica

Esta matriz diferencia explícitamente **lo estipulado en el PDF**, **lo explicado oralmente** y el estado del kit. No confundir prototipo preparado con implementación validada.

| Criterio | Fuente | Acción requerida | Estado del kit |
|---|---|---|---|
| Hardware embebido permitido | PDF p.1 | Orange Pi 4 Pro real | Por instalar |
| Segundo nodo de CPU, preferiblemente diferente arquitectura | Clase (10-oct) | VM x86-64 del portátil | Configurable, autorización de hardware por confirmar |
| IP estática privada en clase C | PDF p.2 | .10 VM / .20 Orange Pi | Guía incluida |
| Red local con switch Gigabit | PDF p.2 y clase | 2 enlaces Cat6, medir con `iperf3` | Guía incluida |
| Arquitectura de red "redundante" | PDF p.2 | Con un switch no existe camino redundante físico | NO CUMPLE literalmente sin hardware adicional/clarificación |
| Worker caído sin perder capacidad de inferencia | PDF p.2 | Segundo modelo local completo y reintento | Código incluido; falta prueba física y RAM |
| Distribución/redistribución mediante middleware | PDF p.2 | llama.cpp RPC + conmutación de aplicación | Código y scripts; validar offload real |
| Caso de visión | PDF p.2 | YOLO/MobileNet con cámara directa | NO implementado; caso VLM distinto |
| VLM que recibe una imagen | Clase | Subida web y descripción local | Código incluido, probar físicamente |
| Modelo local cuantizado | Clase y PDF Caso 3 | Qwen3-VL-2B GGUF Q4_K_M + mmproj Q8 | Descarga automatizada, NO instalada |
| Aislamiento sin nube de inferencia | PDF/Clase | Desactivar NAT/Wi-Fi tras aprovisionar | Plan documentado |
| Medidas de CPU/RAM/tráfico | Clase | panel + capturas `htop`, `mpstat`, `iperf3` | Panel incluido, mediciones pendientes |
| Evidencia de análisis técnico | Rúbrica/clase | arquitectura, decisión de LLM, procedimientos, resultados y límites | Estructura sugerida abajo |
| pfSense | Descriptores rúbrica PDF p.4 | La clase afirma que no es obligatorio | Consulta recomendada ante inconsistencia |
| Autoevaluación Anexo A | Clase | Excel original de Canvas, nota individual 1–100 | Adjuntar plantilla oficial no aportada |
| Pares Anexo B | Clase | Cada miembro evalúa a otro (1–100) | Adjuntar plantilla oficial no aportada |
| Informe PDF formal | PDF p.1 / Clase | Un informe grupal técnico extenso y revisado | Por redactar desde resultados reales |
| Defensa individual video 5–7 minutos | PDF p.1 | Uno por estudiante | Por grabar |
| Video grupal ~10 minutos y reflexión | Clase | Publicar feria virtual | Por grabar |
| Publicación en feria virtual | Clase | Responsable del acceso: equipo web coordinador | Por cargar |
| Entrega 16-oct todos miembros | Clase | Cada integrante debe confirmar Canvas y permisos | Por entregar |
| Defensa del 17-oct | Clase | Explicación demostración aproximada 5 min; todos dominan el proyecto | Por preparar |

### Contradicción de rúbrica

Aunque el PDF se titula *Diseño, Montaje e Implementación de un Clúster de Edge Computing para Inferencia de IA Local Autónoma*, la rúbrica adjunta incluye descriptores de WAN dual stack, pfSense/inspección HTTPS, portal cautivo, SNMP y telecomunicaciones. Esos textos no describen necesariamente el sistema multimodal expuesto oralmente. Antes de asignar esfuerzos a pfSense, solicita **una aclaración al catedrático y conserva la respuesta por escrito**.

### Estructura propuesta del informe (adaptar y enviar layout a profesor)

1. Portada, datos del curso, autores y responsabilidades.
2. Resumen ejecutivo y problema de negocio: dependencia de IA como servicio, privacidad, continuidad y costos de tokens.
3. Objetivos general y específicos medibles.
4. Alcance del caso VLM y diferencia con detección YOLO en tiempo real.
5. Inventario: CPU, RAM, almacenamiento, placas, SO y potencia, capturas `lscpu` y `free -h`.
6. Diagrama físico y lógico: subred/ARP, IPs estáticas, switch y conectores, dependencias, puertos.
7. Selección de Qwen3-VL 2B, Q4_K_M, mmproj, licencia, archivos, compatibilidad y límites de CPU.
8. Arquitectura RPC, distribución de operaciones, HA de worker, SPOF, seguridad y amenaza RPC.
9. Instalación reproducible por comandos + SHA exacto de `llama.cpp` + pantallazos anotados.
10. Software propio: diagramas secuencia subir-imagen→API→LLM→respuesta; validación y fallos.
11. Pruebas y resultados: latencia, tokens/s si servidor expone, CPU de AMBOS, RAM, éxito de 3–5 imágenes, con/sin worker, con/sin Internet.
12. Riesgos: OOM, rendimiento por red vs CPU local, falta redundancia de switch, alucinaciones VLM, inferencia CPU lenta.
13. Seguridad, ética de los datos y análisis breve de marco regulatorio aplicable, sin alegar normas no verificadas.
14. Comparativa experimental local vs distribuido y análisis de coste operacional (no inventar USD/kWh ni ahorro).
15. Recomendaciones, trabajos futuros, conclusiones y referencias.
16. Anexos: tabla de IPs, scripts, bitácora, capturas, links de videos, Excel autoevaluación/pares.

### Propuesta de asignación de roles (si son 4 estudiantes)

- Integrante A: Orange Pi, Linux, compilación ARM64, pruebas de enlace, evidencias.
- Integrante B: hipervisor/VM/red, firewall, fallover, almacenamiento, evidencias.
- Integrante C: modelo VLM, experimentos con capas RPC, selección y benchmarks.
- Integrante D: aplicación web, integración, UX, informe, guion y subida a feria.

**Todos** deben comprender la ruta física, el modelo, la inferencia y la recuperación; no basta con especialización aislada. Las coevaluaciones deben reflejar participación real.

### Preguntas concretas para el catedrático

1. ¿La demostración de imágenes **subidas** a un VLM multimodal sustituye el requisito de **cámara en vivo con YOLO/MobileNet**, o se solicita complementar ambas?
2. ¿Está permitido el CPU de la **VM Ubuntu de una laptop convencional** como segundo nodo, junto a Orange Pi 4 Pro, para satisfacer la restricción del PDF?
3. En la red, ¿es suficiente demostrar caída del *worker* con continuidad por VM, o se exige físicamente redundancia de switch/enlaces?
4. ¿Cuál rúbrica se aplicará, la del PDF que menciona pfSense y portal cautivo, o la explicación oral del 10 de octubre?
5. ¿Se entregan **ambos** formatos: video grupal hasta 10 minutos y videos individuales de 5–7 minutos?
