#!/usr/bin/env python3
"""Camera/YOLO11n ONNX worker for Orange Pi ARM64.

Uses ONLY OpenCV, NumPy and ONNX Runtime (no PyTorch). Local-network-only,
never sends camera images to a cloud. One inference loop shared by MJPEG clients.
This server intentionally does not implement authentication; bind to the
private EdgeVision interface and never forward port 9200 to the Internet.
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import cv2
import numpy as np

LOG = logging.getLogger('edgevision.camera')
# Standard COCO-80 indices; translated for the live-demo overlay.
COCO_ES = [
    'persona', 'bicicleta', 'automovil', 'motocicleta', 'avion', 'autobus', 'tren',
    'camion', 'barco', 'semaforo', 'hidrante', 'senal alto', 'parquimetro', 'banco',
    'pajaro', 'gato', 'perro', 'caballo', 'oveja', 'vaca', 'elefante', 'oso',
    'cebra', 'jirafa', 'mochila', 'paraguas', 'bolso', 'corbata', 'maleta',
    'frisbee', 'esquis', 'snowboard', 'pelota', 'cometa', 'bate', 'guante beisbol',
    'patineta', 'surf', 'raqueta', 'botella', 'copa', 'taza', 'tenedor', 'cuchillo',
    'cuchara', 'tazon', 'banano', 'manzana', 'sandwich', 'naranja', 'brocoli',
    'zanahoria', 'hot dog', 'pizza', 'dona', 'pastel', 'silla', 'sofa',
    'planta', 'cama', 'mesa', 'inodoro', 'televisor', 'portatil', 'raton',
    'control', 'teclado', 'celular', 'microondas', 'horno', 'tostadora',
    'lavamanos', 'refrigerador', 'libro', 'reloj', 'florero', 'tijeras',
    'oso peluche', 'secador', 'cepillo dental',
]
assert len(COCO_ES) == 80


def preprocess(frame: np.ndarray, size: int) -> tuple[np.ndarray, float, int, int]:
    """Letterbox BGR camera frame into a square RGB float32 ONNX tensor."""
    h, w = frame.shape[:2]
    if w < 1 or h < 1:
        raise ValueError('Fotograma sin dimensiones')
    scale = min(size / w, size / h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(frame, (nw, nh), interpolation=cv2.INTER_LINEAR)
    left = (size - nw) // 2
    top = (size - nh) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[top:top+nh, left:left+nw] = resized
    tensor = np.ascontiguousarray(canvas[:, :, ::-1].transpose(2, 0, 1), dtype=np.float32)[None] / 255.0
    return tensor, scale, left, top


def decode_yolo11(output: np.ndarray, width: int, height: int,
                  scale: float, pad_left: int, pad_top: int,
                  confidence: float = 0.40, nms_iou: float = 0.45,
                  limit: int = 20) -> list[dict]:
    """Decode standard Ultralytics YOLO11n ONNX [1,84,N] detections (no NMS)."""
    array = np.asarray(output)
    if array.ndim == 3 and array.shape[0] == 1:
        array = array[0]
    if array.ndim != 2:
        raise ValueError(f'Forma de salida ONNX no compatible: {array.shape}')
    if array.shape[0] == 84:
        array = array.T  # [anchors, xywh+80 scores]
    if array.shape[1] != 84:
        raise ValueError(f'Se esperaba tensor YOLO11n [N,84], recibido: {array.shape}')
    class_scores = array[:, 4:]
    cls_ids = np.argmax(class_scores, axis=1)
    scores = class_scores[np.arange(len(class_scores)), cls_ids]
    selected = np.flatnonzero(np.isfinite(scores) & (scores >= confidence))
    if selected.size == 0:
        return []
    # Bound NMS work and JSON/overlay density on a small ARM board.
    if selected.size > 300:
        top_k = np.argpartition(scores[selected], -300)[-300:]
        selected = selected[top_k]
    boxes: list[list[int]] = []
    valid_scores: list[float] = []
    valid_classes: list[int] = []
    for idx in selected:
        cx, cy, bw, bh = array[idx, :4].tolist()
        x1 = max(0, min(width-1, round((cx - bw / 2 - pad_left) / scale)))
        y1 = max(0, min(height-1, round((cy - bh / 2 - pad_top) / scale)))
        x2 = max(0, min(width-1, round((cx + bw / 2 - pad_left) / scale)))
        y2 = max(0, min(height-1, round((cy + bh / 2 - pad_top) / scale)))
        if x2 <= x1 or y2 <= y1:
            continue
        boxes.append([int(x1), int(y1), int(x2-x1), int(y2-y1)])
        valid_scores.append(float(scores[idx]))
        valid_classes.append(int(cls_ids[idx]))
    if not boxes:
        return []
    # Class-aware NMS: avoid suppressing different categories overlapping.
    kept: list[int] = []
    for class_id in set(valid_classes):
        group = [i for i, cls in enumerate(valid_classes) if cls == class_id]
        k = cv2.dnn.NMSBoxes([boxes[i] for i in group], [valid_scores[i] for i in group],
                             score_threshold=confidence, nms_threshold=nms_iou)
        for j in np.asarray(k).reshape(-1):
            kept.append(group[int(j)])
    kept.sort(key=lambda i: valid_scores[i], reverse=True)
    return [dict(class_id=valid_classes[i], label=COCO_ES[valid_classes[i]],
                 confidence=round(valid_scores[i], 3),
                 box=[boxes[i][0], boxes[i][1], boxes[i][0]+boxes[i][2], boxes[i][1]+boxes[i][3]])
            for i in kept[:limit]]


def annotate(frame: np.ndarray, detections: list[dict], fps: float) -> np.ndarray:
    annotated = frame.copy()
    for det in detections:
        x1, y1, x2, y2 = det['box']
        label = f"{det['label']} {det['confidence']:.2f}"
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (54, 207, 155), 2)
        (tw, th), baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.56, 1)
        top = max(0, y1 - th - baseline - 7)
        cv2.rectangle(annotated, (x1, top), (min(frame.shape[1] - 1, x1+tw+9), y1), (54, 207, 155), -1)
        cv2.putText(annotated, label, (x1 + 4, max(th + 1, y1-baseline-4)),
                    cv2.FONT_HERSHEY_SIMPLEX, .56, (8, 37, 32), 1, cv2.LINE_AA)
    cv2.rectangle(annotated, (0, 0), (225, 26), (13, 30, 42), -1)
    cv2.putText(annotated, f'EdgeVision / YOLO11-Nano / {fps:.2f} FPS',
                (8, 18), cv2.FONT_HERSHEY_SIMPLEX, .46, (238, 240, 242), 1, cv2.LINE_AA)
    return annotated


class OnnxDetector:
    def __init__(self, model: Path, threads: int = 2, conf: float = 0.4):
        import onnxruntime as ort
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = max(1, min(threads, 4))
        opts.inter_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = ort.InferenceSession(str(model), sess_options=opts, providers=['CPUExecutionProvider'])
        self.input = self.session.get_inputs()[0]
        shape = self.input.shape
        if len(shape) != 4 or shape[0] != 1 or shape[1] != 3 or not isinstance(shape[2], int) or shape[2] != shape[3]:
            raise ValueError(f'El modelo debe aceptar entrada estatica [1,3,S,S], recibido {shape}')
        self.size = shape[2]
        self.conf = conf

    def predict(self, frame: np.ndarray) -> list[dict]:
        tensor, scale, left, top = preprocess(frame, self.size)
        output = self.session.run(None, {self.input.name: tensor})[0]
        return decode_yolo11(output, frame.shape[1], frame.shape[0], scale, left, top,
                             confidence=self.conf)


class CameraLoop:
    def __init__(self, detector: OnnxDetector, device: str, target_fps: float = 1.0):
        self.detector = detector
        self.device = device
        self.target_fps = max(0.2, min(4.0, target_fps))
        self.lock = threading.Lock()
        self.raw_jpeg: bytes | None = None
        self.annotated_jpeg: bytes | None = None
        self.last_frame_monotonic = 0.0
        self.last_error = 'Esperando cámara USB...'
        self.total_frames = 0
        self.detections: list[dict] = []
        self.fps = 0.0
        self.inference_ms = 0.0
        self.started = time.monotonic()
        self.paused = threading.Event()
        self.thread = threading.Thread(target=self._loop, daemon=True, name='yolo-camera')

    def start(self):
        self.thread.start()

    def status(self) -> dict:
        with self.lock:
            age = round(time.monotonic() - self.last_frame_monotonic, 1) if self.last_frame_monotonic else None
            return {'online': age is not None and (age < 15.0 or self.paused.is_set()),
                    'model': 'YOLO11n ONNX CPU', 'camera_device': self.device,
                    'frames_total': self.total_frames, 'fps': round(self.fps, 2),
                    'paused': self.paused.is_set(),
                    'inference_ms': round(self.inference_ms, 1),
                    'detections': list(self.detections), 'last_error': self.last_error,
                    'last_frame_age_s': age, 'uptime_s': round(time.monotonic()-self.started)}

    def snapshot(self, annotated: bool = False) -> bytes | None:
        with self.lock:
            if (self.last_frame_monotonic == 0 or
                (time.monotonic() - self.last_frame_monotonic > 15 and not self.paused.is_set())):
                return None  # no stale frames presented as live
            return self.annotated_jpeg if annotated else self.raw_jpeg

    def _open_capture(self) -> cv2.VideoCapture | None:
        devices = ([self.device] if self.device != 'auto'
                   else [f'/dev/video{i}' for i in (0, 1, 2, 3, 4, 5)])
        for dev in devices:
            cap = cv2.VideoCapture(dev, cv2.CAP_V4L2)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ok, frame = cap.read()
            if ok and frame is not None:
                LOG.info('Webcam detectada: %s (%s)', dev, frame.shape)
                self.device = dev
                return cap
            cap.release()
        return None

    def _loop(self):
        cap = None
        while True:
            if self.paused.is_set():
                time.sleep(.2)
                continue
            if cap is None:
                cap = self._open_capture()
                if cap is None:
                    with self.lock:
                        self.last_error = 'No se pudo abrir webcam USB. Revisar /dev/video*, grupo video o CAMERA_DEVICE.'
                    time.sleep(3)
                    continue
            tick = time.monotonic()
            try:
                ok, frame = cap.read()
                if not ok or frame is None:
                    raise RuntimeError('La cámara dejó de entregar fotogramas')
                # Preserve unannotated original for the multimodal VLM.
                raw_ok, raw = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
                if not raw_ok:
                    raise RuntimeError('No se pudo codificar el fotograma')
                infer_start = time.monotonic()
                detections = self.detector.predict(frame)
                inference_ms = (time.monotonic() - infer_start) * 1000
                previous = self.last_frame_monotonic
                actual_fps = (1.0 / max(.001, tick - previous)) if previous else 0
                overlay = annotate(frame, detections, actual_fps)
                drawn_ok, drawn = cv2.imencode('.jpg', overlay, [cv2.IMWRITE_JPEG_QUALITY, 75])
                if not drawn_ok:
                    raise RuntimeError('No se pudo codificar la detección')
                with self.lock:
                    self.raw_jpeg = bytes(raw)
                    self.annotated_jpeg = bytes(drawn)
                    self.detections = detections
                    self.total_frames += 1
                    self.fps = actual_fps
                    self.inference_ms = inference_ms
                    self.last_frame_monotonic = time.monotonic()
                    self.last_error = None
                time.sleep(max(0, 1/self.target_fps-(time.monotonic()-tick)))
            except Exception as exc:
                LOG.warning('Fallo webcam/inferencia: %s', exc)
                with self.lock:
                    self.last_error = f'{type(exc).__name__}: {exc}'[:220]
                cap.release()
                cap = None
                time.sleep(3)


class RequestHandler(BaseHTTPRequestHandler):
    server: 'CameraHTTPServer'

    def do_POST(self):
        path = urlsplit(self.path).path
        if path == '/pause':
            self.server.camera.paused.set()
        elif path == '/resume':
            self.server.camera.paused.clear()
        else:
            return self.send_bytes(b'{"detail":"Ruta no encontrada"}', 'application/json', 404)
        self.send_bytes(json.dumps({'ok': True, 'paused': self.server.camera.paused.is_set()}).encode(), 'application/json')

    def log_message(self, fmt, *args):
        LOG.info('%s %s', self.address_string(), fmt % args)

    def send_bytes(self, body: bytes, content_type: str, status: int = 200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlsplit(self.path).path
        loop = self.server.camera
        if path == '/status':
            return self.send_bytes(json.dumps(loop.status(), ensure_ascii=False).encode('utf-8'), 'application/json')
        if path in ('/snapshot.jpg', '/annotated.jpg'):
            frame = loop.snapshot(annotated=path == '/annotated.jpg')
            if frame is None:
                return self.send_bytes(b'{"detail":"La camara aun no produce imagenes."}', 'application/json', 503)
            return self.send_bytes(frame, 'image/jpeg')
        if path == '/stream.mjpg':
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-store, no-cache')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            previous = None
            try:
                while True:
                    current = loop.snapshot(annotated=True)
                    if current is not None and current is not previous:
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' +
                                         str(len(current)).encode('ascii') + b'\r\n\r\n')
                        self.wfile.write(current + b'\r\n')
                        self.wfile.flush()
                        previous = current
                    time.sleep(.25)
            except (BrokenPipeError, ConnectionResetError, OSError):
                return
        return self.send_bytes(b'{"detail":"Ruta no encontrada"}', 'application/json', 404)


class CameraHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, loop):
        self.camera = loop
        super().__init__(address, RequestHandler)


def main():
    parser = argparse.ArgumentParser(description='EdgeVision YOLO11 Nano webcam worker')
    parser.add_argument('--bind', default='192.168.100.20')
    parser.add_argument('--port', type=int, default=9200)
    parser.add_argument('--device', default='auto', help='auto o /dev/videoN')
    parser.add_argument('--model', default=str(Path(__file__).with_name('yolo11n.onnx')))
    parser.add_argument('--conf', type=float, default=0.40)
    parser.add_argument('--target-fps', type=float, default=1.0)
    parser.add_argument('--onnx-threads', type=int, default=2)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    cv2.setNumThreads(1)  # evita paralelismo excesivo en ARM64 de 4 GB
    model = Path(args.model)
    if not model.is_file() or model.stat().st_size < 1_000_000:
        parser.error(f'Modelo ONNX ausente o incompleto: {model}')
    detector = OnnxDetector(model, args.onnx_threads, args.conf)
    loop = CameraLoop(detector, args.device, args.target_fps)
    server = CameraHTTPServer((args.bind, args.port), loop)
    loop.start()
    LOG.info('Servicio local: http://%s:%s/status', args.bind, args.port)
    try:
        server.serve_forever(poll_interval=.5)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
