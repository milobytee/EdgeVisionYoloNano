"""Offline tests: no webcam, no ONNX Runtime, no physical hardware required."""
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path
from sys import path as syspath

import cv2
import numpy as np

syspath.insert(0, str(Path(__file__).resolve().parents[1]))
from camera_worker.camera_service import (COCO_ES, CameraHTTPServer, CameraLoop, annotate,
                            decode_yolo11, preprocess)


def test_coco_labels_are_80():
    assert len(COCO_ES) == 80
    assert COCO_ES[15] == 'gato'


def test_preprocess_shape_padding():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    tensor, scale, left, top = preprocess(frame, 640)
    assert tensor.shape == (1, 3, 640, 640)
    assert tensor.dtype == np.float32
    assert (scale, left, top) == (1, 0, 80)
    assert np.allclose(tensor[:, :, :80], 114 / 255.0)


def test_decode_boxes_and_nms():
    output = np.zeros((1, 84, 8400), dtype=np.float32)
    output[0, :4, 0] = [320, 320, 200, 200]
    output[0, :4, 1] = [321, 320, 201, 200]
    output[0, 4 + 15, 0] = 0.90
    output[0, 4 + 15, 1] = 0.83
    result = decode_yolo11(output, 640, 480, 1.0, 0, 80)
    assert len(result) == 1
    assert result[0]['label'] == 'gato'
    assert result[0]['box'] == [220, 140, 420, 340]
    assert result[0]['confidence'] == .90
    picture = np.zeros((480, 640, 3), dtype=np.uint8)
    overlay = annotate(picture, result, .9)
    assert overlay.shape == picture.shape
    assert not np.array_equal(overlay, picture)


def test_reject_non_yolo_output():
    import pytest
    with pytest.raises(ValueError):
        decode_yolo11(np.zeros((1, 90, 500)), 640, 480, 1., 0, 0)


def test_camera_pause_flag_and_http_status():
    class Detector:
        pass
    loop = CameraLoop(Detector(), '/dev/video9')
    server = CameraHTTPServer(('127.0.0.1', 0), loop)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f'http://127.0.0.1:{server.server_port}'
        with urllib.request.urlopen(endpoint + '/status', timeout=3) as r:
            before = json.load(r)
        assert before['online'] is False
        request = urllib.request.Request(endpoint + '/pause', data=b'', method='POST')
        with urllib.request.urlopen(request, timeout=3) as r:
            assert json.load(r)['paused'] is True
        request = urllib.request.Request(endpoint + '/resume', data=b'', method='POST')
        with urllib.request.urlopen(request, timeout=3) as r:
            assert json.load(r)['paused'] is False
        try:
            urllib.request.urlopen(endpoint + '/snapshot.jpg', timeout=3)
        except urllib.error.HTTPError as e:
            assert e.code == 503
        else:
            raise AssertionError('Snapshot sin webcam debería fallar')
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
