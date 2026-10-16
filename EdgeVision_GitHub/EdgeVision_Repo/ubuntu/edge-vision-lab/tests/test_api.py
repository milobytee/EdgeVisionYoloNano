import io

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from backend import main


def picture():
    image = Image.new('RGB', (100, 80), 'teal')
    buff = io.BytesIO()
    image.save(buff, format='PNG')
    return buff.getvalue()


class FakeEngine:
    def __init__(self, mode='rpc'):
        self.mode = mode
        self.failover_called = False
        self.last_switch = 'test'
        self.error = None
        self.failover_count = 0

    async def ensure_ready(self):
        pass

    async def failover(self, reason):
        self.failover_called = True
        self.mode = 'local'
        self.failover_count += 1

    async def ready(self):
        return True

    async def switch(self, mode, reason=''):
        self.mode = mode

    def info(self):
        return {'mode': self.mode, 'failovers': self.failover_count}

    def stop(self):
        pass


def post_image(client, content=None):
    return client.post('/api/analyze', data={'question': 'Describe la fotografía'},
                       files={'image': ('foto.png', content if content is not None else picture(), 'image/png')})


def test_home_and_invalid_image():
    client = TestClient(main.app)
    assert client.get('/').status_code == 200
    assert post_image(client, b'bad').status_code == 415


def test_image_downsample_and_hash():
    data, digest = main.prepare_image(picture())
    assert data.startswith('data:image/jpeg;base64,')
    assert len(digest) == 16


def test_single_rpc_request(monkeypatch):
    fake = FakeEngine('rpc')
    monkeypatch.setattr(main, 'engine', fake)
    async def answer(image, prompt):
        assert image.startswith('data:image/jpeg;base64,')
        return 'Una fotografía de prueba.'
    monkeypatch.setattr(main, 'query_model', answer)
    monkeypatch.setattr(main, 'audit_record', lambda x: None)
    r = post_image(TestClient(main.app))
    assert r.status_code == 200
    assert r.json()['mode'] == 'rpc-primary'
    assert r.json()['distributed_verified'] is False


def test_worker_already_down_local_mode(monkeypatch):
    fake = FakeEngine('local')
    monkeypatch.setattr(main, 'engine', fake)
    async def answer(image, prompt): return 'Respuesta por VM.'
    monkeypatch.setattr(main, 'query_model', answer)
    monkeypatch.setattr(main, 'audit_record', lambda x: None)
    r = post_image(TestClient(main.app))
    assert r.status_code == 200
    assert r.json()['mode'] == 'vm-fallback'


def test_failover_retries_from_beginning(monkeypatch):
    fake = FakeEngine('rpc')
    monkeypatch.setattr(main, 'engine', fake)
    counter = {'calls': 0}
    async def answer(image, prompt):
        counter['calls'] += 1
        if counter['calls'] == 1:
            raise httpx.ReadError('RPC connection dropped')
        return 'El modelo local recuperó la inferencia.'
    monkeypatch.setattr(main, 'query_model', answer)
    monkeypatch.setattr(main, 'audit_record', lambda x: None)
    r = post_image(TestClient(main.app))
    assert r.status_code == 200
    assert fake.failover_called
    assert counter['calls'] == 2
    assert r.json()['failover_retried'] is True
    assert r.json()['mode'] == 'vm-fallback'


def test_error_in_local_mode_does_not_forge_success(monkeypatch):
    fake = FakeEngine('local')
    monkeypatch.setattr(main, 'engine', fake)
    async def answer(image, prompt): raise httpx.ReadError('Local failed')
    monkeypatch.setattr(main, 'query_model', answer)
    r = post_image(TestClient(main.app))
    assert r.status_code == 503


def test_large_upload_rejected():
    response = post_image(TestClient(main.app), b'Z' * (5 * 1024 * 1024 + 1))
    assert response.status_code == 413


def test_status_response(monkeypatch):
    fake = FakeEngine('rpc')
    monkeypatch.setattr(main, 'engine', fake)
    async def no_pi(): return None
    async def _ready(): return True
    monkeypatch.setattr(main, 'worker_metrics', no_pi)
    monkeypatch.setattr(main, 'rpc_tcp_open', lambda: True)
    r = TestClient(main.app).get('/api/status')
    assert r.status_code == 200
    assert r.json()['engine']['mode'] == 'rpc'
    assert r.json()['model_ready'] is True


def test_manual_switch_local(monkeypatch):
    fake = FakeEngine('rpc')
    monkeypatch.setattr(main, 'engine', fake)
    r = TestClient(main.app).post('/api/use-local')
    assert r.status_code == 200
    assert fake.mode == 'local'
