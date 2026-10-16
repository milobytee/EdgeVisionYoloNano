"""EdgeVision 2.0.5.1: isolated, non-intrusive RPC supervision and serialized cold recovery.

Never connect to the RPC data port for health polling: the pinned ggml RPC
server serves one persistent client at a time. Liveness is observed out of band
through a separate lightweight observer (9101); the existing metrics (9100) stays untouched. No inference is fabricated.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / 'evidencias'
MODEL_DIR = Path(os.getenv('MODELS_DIR', str(Path.home() / 'edge-vision-models')))
BIN = Path(os.getenv('LLAMA_BIN', str(Path.home() / 'llama.cpp/build/bin/llama-server')))
MODEL = MODEL_DIR / 'Qwen3VL-2B-Instruct-Q4_K_M.gguf'
MMPROJ = MODEL_DIR / 'mmproj-Qwen3VL-2B-Instruct-Q8_0.gguf'
SERVER_URL = 'http://127.0.0.1:8081'
RPC_HOST = os.getenv('EDGE_RPC_HOST', '192.168.100.20')
RPC_PORT = int(os.getenv('EDGE_RPC_PORT', '50052'))
MONITOR_URL = os.getenv('EDGE_WORKER_METRICS_URL', f'http://{RPC_HOST}:9100/metrics')
OBSERVER_URL = os.getenv('EDGE_RPC_OBSERVER_URL', f'http://{RPC_HOST}:9101/rpc-health')
BOOT_TIMEOUT = int(os.getenv('EDGE_BOOT_TIMEOUT', '180'))
THREADS = int(os.getenv('VM_THREADS', '3'))
RPC_LAYERS = int(os.getenv('RPC_LAYERS', '8'))
CONTEXT = int(os.getenv('CONTEXT_TOKENS', '4096'))
IMAGE_MAX_TOKENS = int(os.getenv('IMAGE_MAX_TOKENS', '512'))
MONITOR_TTL = 3.0
WATCH_INTERVAL = 5.0
FAILURE_SAMPLES = 3
FAILURE_GRACE = 10.0
logger = logging.getLogger('edgevision.engine')


class ModelEngine:
    def __init__(self):
        self.mode = 'stopped'
        self.process: subprocess.Popen | None = None
        self.log_handle = None
        self.error: str | None = None
        self.last_switch: str | None = None
        self.last_reason: str | None = None
        self.failover_count = 0
        self.lock = asyncio.Lock()
        # Shared by HTTP analyze/mode changes and watchdog: never stop a running
        # inference behind its request handler's back.
        self.activity_lock = asyncio.Lock()
        self.model_log = LOG_DIR / 'modelo-vlm.log'
        self.session_id: str | None = None
        self.session_log_offset = 0
        self.generation = 0
        self.monitor_warning: str | None = None
        self._remote_lock = asyncio.Lock()
        self._remote_cache: dict | None = None
        self._remote_checked = float('-inf')
        self._remote_seq = 0
        self._bad_since: float | None = None
        self._bad_samples = 0
        self._last_bad_sample = -1
        self._last_watch_event: str | None = None
        self._ready_lock = asyncio.Lock()
        self._ready_checked = float('-inf')
        self._ready_generation = -1
        self._ready_cache = False

    def _event(self, event: str, **details) -> None:
        record = {'utc': datetime.now(timezone.utc).isoformat(), 'event': event,
                  'session_id': self.session_id, 'mode': self.mode, **details}
        logger.info('Supervision RPC: %s', json.dumps(record, ensure_ascii=False))
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            with (LOG_DIR / 'supervision-rpc.jsonl').open('a', encoding='utf8') as f:
                f.write(json.dumps(record, ensure_ascii=False) + '\n')
        except OSError:
            logger.warning('No se pudo escribir supervision-rpc.jsonl')

    async def remote_status(self, force: bool = False) -> dict:
        """Read telemetry; no socket is opened on RPC_PORT.

        listening is True/False only for a valid out-of-band observation.
        Missing telemetry is UNKNOWN, not proof that the RPC worker died.
        The cache/lock coalesce requests from multiple browser tabs.
        """
        async with self._remote_lock:
            now = time.monotonic()
            if not force and self._remote_cache is not None and now - self._remote_checked < MONITOR_TTL:
                return dict(self._remote_cache)
            worker = None
            available = None
            reason = None
            try:
                async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                    # Dedicated passive observer; NEVER opens a socket to 50052.
                    response = await client.get(OBSERVER_URL)
                    response.raise_for_status()
                    report = response.json()
                if not isinstance(report, dict):
                    raise ValueError('Respuesta del observador no es JSON de tipo objeto')
                obs = report.get('rpc_observation')
                if (report.get('agent_version') == '2.0.5.1'
                        and isinstance(obs, dict)
                        and obs.get('schema') == 'proc-net-tcp-v1'
                        and obs.get('port') == RPC_PORT
                        and isinstance(obs.get('listening'), bool)):
                    available = obs['listening']
                    reason = 'Listener RPC observado pasivamente desde 9101; sin conexiones a 50052.'
                else:
                    reason = 'Observador con respuesta incompleta; RPC sin confirmar.'
            except (httpx.HTTPError, ValueError, TypeError) as exc:
                reason = f'Observador 9101 no disponible ({type(exc).__name__}); RPC sin confirmar.'
            # Existing CPU/RAM metrics are obtained independently from the original
            # monitor. Its process, port and Python file are NOT modified.
            try:
                async with httpx.AsyncClient(timeout=3.0, trust_env=False) as client:
                    metrics = await client.get(MONITOR_URL)
                    metrics.raise_for_status()
                    data = metrics.json()
                    if isinstance(data, dict):
                        worker = data
            except (httpx.HTTPError, ValueError, TypeError):
                pass
            self._remote_seq += 1
            self._remote_checked = time.monotonic()
            self._remote_cache = {'available': available, 'worker': worker,
                                  'source': 'rpc-observer-9101', 'reason': reason,
                                  'sequence': self._remote_seq}
            return dict(self._remote_cache)

    def _command(self, mode: str) -> list[str]:
        # Same model, projector and inference settings as the working 2.0.3 build.
        cmd = [str(BIN), '-m', str(MODEL), '--mmproj', str(MMPROJ),
               '--no-mmproj-offload', '--host', '127.0.0.1', '--port', '8081',
               '--alias', 'edgevision-vlm', '-ngl', str(RPC_LAYERS if mode == 'rpc' else 0),
               '-t', str(THREADS), '-c', str(CONTEXT), '-b', '512', '-ub', '512',
               '--image-max-tokens', str(IMAGE_MAX_TOKENS), '-np', '1']
        if mode == 'rpc':
            cmd += ['--rpc', f'{RPC_HOST}:{RPC_PORT}']
        if os.getenv('EDGE_VERBOSE', 'true').lower() == 'true':
            cmd += ['-lv', '5']
        return cmd

    async def ready(self) -> bool:
        process = self.process
        generation = self.generation
        if process is None or process.poll() is not None:
            return False
        async with self._ready_lock:
            if (generation == self._ready_generation
                    and time.monotonic() - self._ready_checked < 1.0):
                return self._ready_cache
            ok = False
            try:
                async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                    resp = await client.get(f'{SERVER_URL}/health')
                ok = resp.status_code == 200
            except (httpx.HTTPError, ValueError):
                pass
            ok = ok and process is self.process and generation == self.generation and process.poll() is None
            self._ready_cache = ok
            self._ready_generation = generation
            self._ready_checked = time.monotonic()
            return ok

    def _terminate(self) -> None:
        # Only the process group that this portal launched; never kill RPC/YOLO.
        if self.process is not None:
            if self.process.poll() is None:
                try:
                    os.killpg(self.process.pid, signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    pass
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(self.process.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
                    self.process.wait(timeout=5)
            self.process = None
        if self.log_handle is not None:
            self.log_handle.close()
            self.log_handle = None
        self._ready_checked = float('-inf')

    async def switch(self, mode: str, reason: str = '', *, recovery: bool = False) -> None:
        if mode not in ('rpc', 'local'):
            raise ValueError('Modo desconocido')
        async with self.lock:
            if self.mode == mode and await self.ready():
                return
            if mode == 'rpc':
                observation = await self.remote_status(force=True)
                if observation['available'] is not True:
                    raise RuntimeError('No se confirma el listener RPC por el observador 9101. '
                                       'Se conserva el modo actual; revisa edgevision-rpc-observer/edgevision-rpc.')
            missing = [str(p) for p in (BIN, MODEL, MMPROJ) if not p.is_file()]
            if missing:
                raise RuntimeError('Faltan archivos: ' + ', '.join(missing))
            previous = self.mode
            self.generation += 1
            self.mode = f'starting-{mode}'
            self.error = None
            self.last_reason = reason or 'Cambio manual'
            self.last_switch = datetime.now(timezone.utc).isoformat()
            self.session_id = uuid.uuid4().hex[:16]
            self._bad_samples = 0
            self._bad_since = None
            self._last_bad_sample = -1
            self.monitor_warning = None
            self._event('switch_begin', previous_mode=previous, target_mode=mode, reason=self.last_reason)
            await asyncio.to_thread(self._terminate)
            if recovery and mode == 'local':
                self.failover_count += 1
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            self.session_log_offset = self.model_log.stat().st_size if self.model_log.exists() else 0
            self.log_handle = self.model_log.open('a', encoding='utf-8')
            self.log_handle.write(f'\n=== {self.last_switch} start mode={mode} '
                                  f'session_id={self.session_id} reason={self.last_reason} ===\n')
            self.log_handle.flush()
            env = os.environ.copy()
            env['GGML_RPC_NO_RDMA'] = '1'
            if os.getenv('EDGE_VERBOSE', 'true').lower() == 'true':
                env['GGML_RPC_DEBUG'] = '1'
            try:
                self.process = subprocess.Popen(self._command(mode), stdout=self.log_handle,
                    stderr=subprocess.STDOUT, cwd=str(BIN.parent.parent.parent), env=env, start_new_session=True)
                started = time.monotonic()
                while time.monotonic() - started < BOOT_TIMEOUT:
                    if self.process.poll() is not None:
                        raise RuntimeError(f'llama-server termino al cargar (exit={self.process.returncode}); '
                                           'revisar evidencias/modelo-vlm.log')
                    if await self.ready():
                        self.mode = mode
                        self._event('switch_ready', pid=self.process.pid)
                        return
                    await asyncio.sleep(1.2)
                raise RuntimeError(f'El modelo no estuvo listo antes de {BOOT_TIMEOUT} s; revisar el log.')
            except asyncio.CancelledError:
                await asyncio.to_thread(self._terminate)
                self.mode = 'stopped'
                raise
            except (OSError, ValueError, RuntimeError) as exc:
                self.error = str(exc)
                self.mode = 'error'
                self._event('switch_error', target_mode=mode, reason=self.error)
                await asyncio.to_thread(self._terminate)
                raise RuntimeError(self.error) from exc

    async def ensure_ready(self) -> None:
        if self.mode.startswith('starting-'):
            async with self.lock:
                pass
        if self.mode in ('rpc', 'local') and (self.process is None or self.process.poll() is not None):
            previous = self.mode
            if previous == 'rpc':
                await self.failover('Proceso VLM RPC termino inesperadamente')
            else:
                await self.switch('local', reason='Recuperacion del proceso VLM local')
        elif self.mode in ('stopped', 'error'):
            observation = await self.remote_status()
            target = 'rpc' if observation['available'] is True else 'local'
            try:
                await self.switch(target, reason='Inicio automatico')
            except RuntimeError:
                if target != 'rpc':
                    raise
                await self.failover('No arranco el primario RPC; revisar log de su sesion')
        # A loaded RPC model keeps its persistent socket. Do NOT open a second
        # RPC connection here to decide whether it may accept an image.
        if not await self.ready():
            raise RuntimeError(self.error or 'El modelo no esta disponible')

    async def failover(self, reason: str) -> None:
        await self.switch('local', reason=reason, recovery=True)

    async def _recover_idle(self, generation: int, reason: str) -> None:
        if self.activity_lock.locked():
            self.monitor_warning = 'Fallo observado; se permite que la solicitud termine o alcance su timeout.'
            return
        async with self.activity_lock:
            if self.mode == 'rpc' and self.generation == generation:
                self._event('watchdog_recovery', reason=reason)
                await self.failover(reason)

    async def watch_once(self) -> None:
        """One watchdog iteration, intentionally testable with deterministic clocks."""
        if self.mode != 'rpc':
            self._bad_samples = 0
            self._bad_since = None
            return
        generation = self.generation
        if self.process is None or self.process.poll() is not None:
            await self._recover_idle(generation, 'Proceso VLM RPC termino (watchdog)')
            return
        observation = await self.remote_status()
        if self.mode != 'rpc' or self.generation != generation:
            return
        available = observation['available']
        if available is True:
            self._bad_samples = 0
            self._bad_since = None
            self.monitor_warning = None
            self._last_watch_event = None
            return
        if available is None:
            # A failed metrics agent is not automatically a dead inference
            # worker. Real RPC request/transport errors still trigger failover.
            self._bad_samples = 0
            self._bad_since = None
            self.monitor_warning = observation['reason']
            if self._last_watch_event != 'telemetry_unknown':
                self._event('telemetry_unknown', reason=self.monitor_warning)
                self._last_watch_event = 'telemetry_unknown'
            return
        now = time.monotonic()
        if self._bad_since is None:
            self._bad_since = now
        if observation['sequence'] != self._last_bad_sample:
            self._bad_samples += 1
            self._last_bad_sample = observation['sequence']
            self._event('rpc_listener_missing', samples=self._bad_samples)
        self.monitor_warning = f'Listener RPC ausente: {self._bad_samples} muestras; comprobando antes de recuperar.'
        if self._bad_samples >= FAILURE_SAMPLES and now - self._bad_since >= FAILURE_GRACE:
            await self._recover_idle(generation, 'Listener RPC ausente confirmado por monitor independiente (watchdog)')

    async def background_watch(self) -> None:
        while True:
            try:
                await self.watch_once()
            except (RuntimeError, OSError, ValueError) as exc:
                self.error = str(exc)
                self._event('watchdog_error', reason=self.error)
            await asyncio.sleep(WATCH_INTERVAL)

    def info(self) -> dict:
        return {'mode': self.mode,
                'pid': self.process.pid if self.process and self.process.poll() is None else None,
                'last_error': self.error, 'last_switch_reason': self.last_reason,
                'last_switch_utc': self.last_switch, 'failovers': self.failover_count,
                'cold_failover': True, 'generation': self.generation,
                'session_id': self.session_id, 'session_log_offset': self.session_log_offset,
                'transitioning': self.mode.startswith('starting-'),
                'supervision': 'passive-rpc-observer-9101',
                'monitor_warning': self.monitor_warning, 'watchdog_missing_samples': self._bad_samples}

    def stop(self) -> None:
        self._terminate()
        self.mode = 'stopped'
