"""EdgeVision: local image interpretation with monitored RPC and cold failover."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import io
import json
import logging
import os
import socket
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psutil
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response, StreamingResponse
from PIL import Image, ImageOps, UnidentifiedImageError

load_dotenv(Path(__file__).with_name('.env'))
from backend.engine import ModelEngine, SERVER_URL  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STATIC = Path(__file__).with_name('static')
WORKER_METRICS = os.getenv('EDGE_WORKER_METRICS_URL', 'http://192.168.100.20:9100/metrics')
CAMERA_URL = os.getenv('EDGE_CAMERA_URL', 'http://192.168.100.20:9200').rstrip('/')
UPSTREAM_TIMEOUT = float(os.getenv('EDGE_UPSTREAM_TIMEOUT', '480'))
AUDIT_FILE = ROOT / 'evidencias' / 'inferencias.jsonl'
MAX_UPLOAD = 5 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 16_000_000
logger = logging.getLogger('edgevision')
engine = ModelEngine()
request_lock = engine.activity_lock


@asynccontextmanager
async def lifespan(app: FastAPI):
    async def startup():
        try:
            await engine.ensure_ready()
        except RuntimeError as exc:
            logger.error('No se pudo arrancar el VLM: %s', exc)
    boot = asyncio.create_task(startup()) if os.getenv('EDGE_AUTO_ENGINE', 'false') == 'true' else None
    watch = asyncio.create_task(engine.background_watch()) if boot else None
    yield
    for task in (boot, watch):
        if task:
            task.cancel()
    if boot or watch:
        await asyncio.gather(*(t for t in (boot, watch) if t), return_exceptions=True)
    engine.stop()


app = FastAPI(title='EdgeVision - IA multimodal local', version='2.0.5.1', lifespan=lifespan, docs_url='/api/docs')


@app.get('/')
async def home():
    return FileResponse(STATIC / 'index.html')


async def worker_metrics() -> dict | None:
    return (await engine.remote_status()).get('worker')


async def camera_metrics() -> dict:
    """Camera service state; camera unavailability never breaks the existing VLM."""
    try:
        async with httpx.AsyncClient(timeout=1.2, trust_env=False) as client:
            response = await client.get(f'{CAMERA_URL}/status')
            response.raise_for_status()
            data = response.json()
            if not isinstance(data, dict):
                raise ValueError('Estado de cámara inesperado')
            data['service_reachable'] = True
            return data
    except (httpx.HTTPError, ValueError):
        return {'service_reachable': False, 'online': False,
                'last_error': 'Servicio YOLO de Orange Pi no disponible'}


def host_metrics() -> dict:
    mem = psutil.virtual_memory()
    return {'hostname': socket.gethostname(),
            'cpu_percent': round(psutil.cpu_percent(interval=None), 1),
            'memory_percent': round(mem.percent, 1),
            'memory_used_mb': round(mem.used / 1024**2),
            'memory_total_mb': round(mem.total / 1024**2),
            'cpu_count': psutil.cpu_count(logical=True)}


@app.get('/api/status')
async def status():
    before = engine.info().get('generation')
    observation, ready, camera = await asyncio.gather(
        engine.remote_status(), engine.ready(), camera_metrics())
    details = engine.info()
    # Do not combine a health response from the old process with a new mode.
    ready = bool(ready and details['mode'] in ('rpc', 'local')
                 and before == details.get('generation'))
    return {'vm': host_metrics(), 'worker': observation.get('worker'),
            'worker_rpc': observation['available'], 'rpc_observation': {
                'source': observation['source'], 'reason': observation['reason']},
            'engine': details, 'model_ready': ready, 'camera': camera,
            'analysis_or_switch_in_progress': request_lock.locked(),
            'portal_version': '2.0.5.1',
            'model': 'Qwen3-VL-2B-Instruct Q4_K_M + mmproj Q8',
            'note': 'Supervision pasiva por 9101; CPU/RAM por 9100; sin sondeos al puerto 50052.'}


def prepare_image(data: bytes) -> tuple[str, str]:
    if not data or len(data) > MAX_UPLOAD:
        raise HTTPException(status_code=413, detail='La imagen debe ocupar menos de 5 MB.')
    try:
        with Image.open(io.BytesIO(data)) as original:
            if original.width * original.height > 6_000_000:
                raise HTTPException(status_code=413, detail='Dimensiones muy grandes: máximo 6 megapíxeles.')
            if original.format not in {'JPEG', 'PNG', 'WEBP'}:
                raise HTTPException(status_code=415, detail='Formato permitido: JPG, PNG o WebP.')
            image = ImageOps.exif_transpose(original)
            image.thumbnail((640, 640), Image.Resampling.LANCZOS)
            if image.mode in ('RGBA', 'LA') or 'transparency' in image.info:
                image = image.convert('RGBA')
                white = Image.new('RGBA', image.size, 'white')
                white.alpha_composite(image)
                image = white.convert('RGB')
            else:
                image = image.convert('RGB')
            output = io.BytesIO()
            image.save(output, format='JPEG', quality=78, optimize=True)
        return ('data:image/jpeg;base64,' + base64.b64encode(output.getvalue()).decode('ascii'),
                hashlib.sha256(data).hexdigest()[:16])
    except HTTPException:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, ValueError):
        raise HTTPException(status_code=415, detail='El archivo no es una imagen válida.')


async def query_model(image_uri: str, question: str) -> str:
    payload = {'model': 'edgevision-vlm', 'messages': [{'role':'user', 'content': [
        {'type':'text', 'text': question},
        {'type':'image_url', 'image_url': {'url': image_uri}}]}],
        'max_tokens': 180, 'temperature': 0.1, 'stream': False}
    async with httpx.AsyncClient(timeout=httpx.Timeout(UPSTREAM_TIMEOUT, connect=5), trust_env=False) as client:
        resp = await client.post(f'{SERVER_URL}/v1/chat/completions', json=payload)
        resp.raise_for_status()
        obj = resp.json()
        content = obj['choices'][0]['message']['content']
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            rendered = '\n'.join(el.get('text', '') for el in content if isinstance(el, dict))
            if rendered.strip():
                return rendered.strip()
        raise ValueError('El modelo devolvió una respuesta vacía o inesperada.')


def audit_record(details: dict) -> None:
    try:
        AUDIT_FILE.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_FILE.open('a', encoding='utf-8') as f:
            f.write(json.dumps(details, ensure_ascii=False) + '\n')
    except OSError as exc:
        logger.warning('No se pudo escribir evidencia: %s', exc)


async def ensure_vlm_for_analysis() -> bool:
    """Ensure VLM is available, with a single CPU-local cold recovery attempt.

    The camera worker and RPC daemon are never stopped or reconfigured here.
    Return True if this request had to recover Qwen3-VL in local CPU mode.
    """
    try:
        await engine.ensure_ready()
        return False
    except RuntimeError as first_exc:
        # A transient error during startup may resolve before this check.
        if await engine.ready():
            return False
        logger.warning('Qwen3-VL no disponible al analizar; intentando CPU local: %s', first_exc)
        try:
            # Only llama-server is restarted, not camera, YOLO or RPC.
            await engine.switch('local', reason='Recuperacion VLM al analizar una imagen')
            if not await engine.ready():
                raise RuntimeError('Qwen3-VL continua sin responder a /health')
            return True
        except RuntimeError as local_exc:
            logger.error('Qwen3-VL no pudo recuperarse: %s', local_exc)
            raise HTTPException(
                status_code=503,
                detail=('Qwen3-VL no esta disponible. Reintento por CPU local fallido: '
                        + str(local_exc)[:160] + '. Consulta evidencias/modelo-vlm.log en Ubuntu.'),
            ) from local_exc


@app.post('/api/analyze')
async def analyze(image: UploadFile = File(...), question: str = Form('Describe lo que ves en esta imagen. Responde en español sin inventar detalles.')):
    if not 1 <= len(question.strip()) <= 1000:
        raise HTTPException(status_code=422, detail='Instrucción de 1 a 1000 caracteres.')
    data = await image.read(MAX_UPLOAD + 1)
    image_uri, digest = prepare_image(data)
    started = time.monotonic()
    request_id = uuid.uuid4().hex[:16]
    async with request_lock:
        startup_recovered = await ensure_vlm_for_analysis()
        starting_mode = engine.mode
        starting_session = engine.info().get('session_id')
        recovered = False
        first_error = None
        try:
            response = await query_model(image_uri, question.strip())
        except (httpx.HTTPError, ValueError, KeyError, TypeError, RuntimeError) as exc:
            first_error = f'{type(exc).__name__}: {str(exc)[:120]}'
            if engine.mode != 'rpc' and not engine.mode.startswith('starting-rpc'):
                raise HTTPException(status_code=503, detail=f'Fallo de inferencia local: {first_error}') from exc
            try:
                await engine.failover('Error durante inferencia RPC: ' + first_error)
                response = await query_model(image_uri, question.strip())
                recovered = True
            except (RuntimeError, httpx.HTTPError, ValueError, KeyError, TypeError) as other:
                raise HTTPException(status_code=503, detail=f'Fallaron RPC y respaldo local: {str(other)[:140]}') from other
        elapsed = round(time.monotonic() - started, 2)
        mode = 'rpc-primary' if engine.mode == 'rpc' else 'vm-fallback'
        final_session = engine.info().get('session_id')
        audit_record({'utc': datetime.now(timezone.utc).isoformat(), 'request_id': request_id,
                      'starting_mode': starting_mode, 'starting_session_id': starting_session,
                      'model_session_id': final_session, 'image_sha256_prefix': digest,
                      'mode': mode, 'latency_seconds': elapsed,
                      'recovered_this_request': recovered or startup_recovered,
                      'startup_recovered': startup_recovered, 'first_error': first_error})
        return {'answer': response, 'mode': mode, 'latency_seconds': elapsed,
                'request_id': request_id, 'model_session_id': final_session,
                'image_hash': digest, 'failover_retried': recovered,
                'startup_recovered': startup_recovered,
                'distributed_verified': False,
                'verification_note': 'Revisar evidencias/modelo-vlm.log y actividad CPU para demostrar cálculo RPC.'}


@app.post('/api/use-rpc')
async def use_rpc():
    async with request_lock:
        try:
            # switch() uses the independent monitor; no extra RPC connections.
            await engine.switch('rpc', reason='Retorno manual al RPC desde el portal')
            return {'ok': True, 'mode': engine.mode, 'session_id': engine.info().get('session_id')}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post('/api/use-local')
async def use_local():
    async with request_lock:
        try:
            await engine.switch('local', reason='Cambio manual a respaldo local')
            return {'ok': True, 'mode': engine.mode}
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get('/api/camera/status')
async def camera_status():
    return await camera_metrics()


@app.get('/api/camera/snapshot')
async def camera_snapshot():
    """A fresh raw camera frame for Qwen3-VL, never with YOLO annotations."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(8.0, connect=2.5), trust_env=False) as client:
            response = await client.get(f'{CAMERA_URL}/snapshot.jpg')
            response.raise_for_status()
            body = response.content
            if not (8 < len(body) <= MAX_UPLOAD and body[:3] == b'\xff\xd8\xff'):
                raise HTTPException(status_code=502, detail='La Orange Pi entregó una imagen inválida.')
            return Response(body, media_type='image/jpeg', headers={'Cache-Control': 'no-store'})
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=503, detail='Cámara USB no disponible. Revisa el servicio YOLO en Orange Pi.') from exc


@app.get('/api/camera/stream')
async def camera_stream():
    """Same-origin MJPEG relay. The webcam stays physically on Orange Pi."""
    client = httpx.AsyncClient(timeout=httpx.Timeout(connect=3.0, read=None, write=5.0, pool=5.0),
                               trust_env=False)
    try:
        request = client.build_request('GET', f'{CAMERA_URL}/stream.mjpg')
        upstream = await client.send(request, stream=True)
        upstream.raise_for_status()
        if 'multipart/x-mixed-replace' not in upstream.headers.get('content-type', '').lower():
            await upstream.aclose()
            raise HTTPException(status_code=502, detail='La fuente de cámara no ofrece flujo MJPEG.')
    except httpx.HTTPError as exc:
        await client.aclose()
        raise HTTPException(status_code=503, detail='Transmisión de webcam no disponible.') from exc
    except HTTPException:
        await client.aclose()
        raise

    async def stream_chunks():
        try:
            async for chunk in upstream.aiter_raw():
                if chunk:
                    yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(stream_chunks(), media_type='multipart/x-mixed-replace; boundary=frame',
                             headers={'Cache-Control': 'no-store, no-cache',
                                      'X-Accel-Buffering': 'no',
                                      'X-Content-Type-Options': 'nosniff'})


@app.post('/api/camera/{action}')
async def camera_control(action: str):
    if action not in ('pause', 'resume'):
        raise HTTPException(status_code=404, detail='Acción de cámara desconocida.')
    try:
        async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
            response = await client.post(f'{CAMERA_URL}/{action}')
            response.raise_for_status()
            return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail='No se pudo controlar la webcam de Orange Pi.') from exc
