#!/usr/bin/env python3
"""Collect observed end-to-end latency for a REAL supplied image, not mock data."""
from __future__ import annotations
import argparse
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx

p = argparse.ArgumentParser()
p.add_argument('image', help='Ruta de la imagen de prueba (JPG, PNG o WebP)')
p.add_argument('--url', default='http://192.168.100.10:8000')
p.add_argument('--repetitions', type=int, default=3)
p.add_argument('--question', default='Describe los objetos principales en la imagen.')
p.add_argument('--output', default='evidencias/benchmark.json')
a = p.parse_args()
image = Path(a.image)
if not image.is_file():
    p.error('Imagen no encontrada')
measurements = []
for n in range(a.repetitions):
    tic = time.monotonic()
    with image.open('rb') as f, httpx.Client(timeout=400.0) as client:
        response = client.post(f'{a.url}/api/analyze', data={'question': a.question}, files={'image':(image.name, f)})
    elapsed = round(time.monotonic() - tic, 3)
    response.raise_for_status()
    payload = response.json()
    measurements.append({'run':n+1, 'wall_seconds':elapsed, 'server_seconds':payload['latency_seconds'], 'mode':payload['mode'], 'result':payload['answer'][:180]})
    print(f'Iteracion {n+1}: {elapsed}s, ruta={payload["mode"]}')
report = {
    'created_utc': datetime.now(timezone.utc).isoformat(),
    'image': image.name, 'repetitions': len(measurements),
    'median_wall_seconds': statistics.median(x['wall_seconds'] for x in measurements),
    'measurements': measurements,
    'note': 'Comparar modo primario y respaldo con la MISMA imagen y pregunta; no asumir aceleracion.'
}
output = Path(a.output)
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'Evidencia: {output.resolve()}')
