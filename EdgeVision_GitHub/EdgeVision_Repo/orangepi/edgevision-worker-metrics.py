#!/usr/bin/env python3
"""Tiny read-only Linux metrics endpoint; no dependencies on Orange Pi."""
from __future__ import annotations
import argparse
import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

lock = threading.Lock()
previous = None


def cpu_counters() -> tuple[int, int]:
    with open('/proc/stat', encoding='utf8') as f:
        first = f.readline().split()
    fields = [int(n) for n in first[1:]]
    idle = fields[3] + (fields[4] if len(fields) > 4 else 0)
    return (sum(fields), idle)


def get_cpu_percent() -> float:
    global previous
    current = cpu_counters()
    with lock:
        if previous is None:
            previous = current
            return 0.0
        total = current[0] - previous[0]
        idle = current[1] - previous[1]
        previous = current
    return round(100 * max(0.0, (total - idle) / total), 1) if total > 0 else 0.0


def mem_stats() -> tuple[float, int, int]:
    with open('/proc/meminfo', encoding='utf8') as file:
        vals = {}
        for line in file:
            key, val = line.split(':', 1)
            vals[key] = int(val.strip().split()[0])  # kB
    total = vals['MemTotal']
    avail = vals['MemAvailable']
    used = total - avail
    return (round(100 * used / total, 1), round(used / 1024), round(total / 1024))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ('/metrics', '/health'):
            self.send_error(404)
            return
        memory_pct, used_mb, total_mb = mem_stats()
        response = {
            'hostname': socket.gethostname(), 'cpu_percent': get_cpu_percent(),
            'memory_percent': memory_pct, 'memory_used_mb': used_mb,
            'memory_total_mb': total_mb, 'cpu_count': os.cpu_count(),
            'load1': round(os.getloadavg()[0], 2),
        }
        body = json.dumps(response).encode('utf8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--bind', default='192.168.100.20')
    parser.add_argument('--port', type=int, default=9100)
    args = parser.parse_args()
    print(f'Local worker metrics: http://{args.bind}:{args.port}/metrics', flush=True)
    ThreadingHTTPServer((args.bind, args.port), Handler).serve_forever()
