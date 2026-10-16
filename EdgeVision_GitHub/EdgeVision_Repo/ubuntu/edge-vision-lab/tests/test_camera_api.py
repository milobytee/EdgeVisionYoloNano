"""Tests of the portal -> Orange Pi camera proxy with a simulated remote."""
import io
import httpx
from fastapi.testclient import TestClient
from PIL import Image
from backend import main


class FakeResponse:
    status_code=200
    headers={'content-type':'multipart/x-mixed-replace; boundary=frame'}
    def __init__(self, raw):
        self.content=raw
    def raise_for_status(self):
        pass
    def json(self):
        return {'online': True, 'model': 'YOLO11n', 'fps': 1.2, 'detections': [], 'paused': False}
    async def aiter_raw(self):
        yield b'--frame\r\nContent-Type: image/jpeg\r\n\r\nJPEG\r\n'
    async def aclose(self):
        pass


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        self.response=FakeResponse(build_jpeg())
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass
    async def aclose(self):
        pass
    async def get(self, url):
        return self.response
    async def post(self, url):
        if url.endswith('/pause') or url.endswith('/resume'):
            return FakeResponse(b'')
        raise AssertionError(url)
    def build_request(self, method, url):
        return (method,url)
    async def send(self, request, stream=False):
        return self.response


def build_jpeg():
    output=io.BytesIO()
    Image.new('RGB',(64,64),'blue').save(output,'JPEG')
    return output.getvalue()


def test_camera_status_proxied(monkeypatch):
    monkeypatch.setattr(main.httpx, 'AsyncClient', FakeAsyncClient)
    response = TestClient(main.app).get('/api/camera/status')
    assert response.status_code == 200
    assert response.json()['online'] is True


def test_camera_snapshot_proxied(monkeypatch):
    monkeypatch.setattr(main.httpx, 'AsyncClient', FakeAsyncClient)
    response = TestClient(main.app).get('/api/camera/snapshot')
    assert response.status_code == 200
    assert response.headers['content-type'].startswith('image/jpeg')
    assert response.content[:3] == b'\xff\xd8\xff'


def test_camera_control_only_pause_or_resume(monkeypatch):
    monkeypatch.setattr(main.httpx, 'AsyncClient', FakeAsyncClient)
    client=TestClient(main.app)
    assert client.post('/api/camera/pause').status_code == 200
    assert client.post('/api/camera/resume').status_code == 200
    assert client.post('/api/camera/wipe').status_code == 404


def test_camera_stream_has_mjpeg_boundary(monkeypatch):
    monkeypatch.setattr(main.httpx, 'AsyncClient', FakeAsyncClient)
    with TestClient(main.app).stream('GET', '/api/camera/stream') as response:
        assert response.status_code == 200
        assert 'multipart/x-mixed-replace' in response.headers['content-type']
        assert b'--frame\r\n' in b''.join(response.iter_bytes())
