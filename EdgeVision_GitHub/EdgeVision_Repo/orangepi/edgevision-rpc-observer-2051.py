#!/usr/bin/env python3
"""Passive RPC socket observation on a SEPARATE port (never touch 9100 or 50052).

Listener presence is not evidence of tensor computation. Designed for the private
EdgeVision Ethernet subnet only; do not expose this status service to the internet.
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

RPC_PORT = 50052
VERSION = '2.0.5.1'


def get_observation(tcp_path='/proc/net/tcp', port=RPC_PORT):
    result = {'schema': 'proc-net-tcp-v1', 'port': port, 'listening': None,
              'established_connections': 0, 'source': 'kernel-proc-net-tcp'}
    try:
        lines = Path(tcp_path).read_text(encoding='ascii').splitlines()[1:]
        listener = False
        established = 0
        for line in lines:
            fields = line.split()
            if len(fields) < 4:
                continue
            try:
                local_port = int(fields[1].rsplit(':', 1)[-1], 16)
            except ValueError:
                continue
            if local_port == port:
                if fields[3] == '0A':
                    listener = True
                if fields[3] == '01':
                    established += 1
        result.update(listening=listener, established_connections=established)
    except (OSError, UnicodeError, ValueError, IndexError) as exc:
        result['error'] = type(exc).__name__
    return result


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != '/rpc-health':
            self.send_error(404)
            return
        result = {'agent_version': VERSION, 'rpc_observation': get_observation()}
        body = json.dumps(result).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        return


class Service(ThreadingHTTPServer):
    daemon_threads = True


def wait_for_bindable_ip(ip: str, limit: int = 90):
    for _ in range(limit):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind((ip, 0))
            return True
        except OSError:
            time.sleep(1)
    return False


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--bind', default='192.168.100.20')
    p.add_argument('--port', type=int, default=9101)
    p.add_argument('--self-test', action='store_true')
    p.add_argument('--wait-ip', action='store_true')
    args = p.parse_args()
    if args.self_test:
        report = {'agent_version': VERSION, 'rpc_observation': get_observation()}
        print(json.dumps(report))
        return 0 if isinstance(report['rpc_observation']['listening'], bool) else 2
    if args.wait_ip:
        return 0 if wait_for_bindable_ip(args.bind) else 2
    print(f'Passive RPC observer: http://{args.bind}:{args.port}/rpc-health', flush=True)
    with Service((args.bind, args.port), HealthHandler) as server:
        server.serve_forever(poll_interval=0.5)
    return 0


if __name__ == '__main__':
    sys.exit(main())
