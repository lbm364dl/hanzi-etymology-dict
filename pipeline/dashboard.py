"""Local, live observability for editorial queues, model stages and source repairs.

Run ``python3 -m pipeline.dashboard --port 8765`` and open http://127.0.0.1:8765.
The service only reads pipeline artifacts; it does not start jobs or issue approvals.
"""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
import time
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(__file__).with_name('dashboard')
STATIC = {'/favicon.ico': ('favicon.svg', 'image/svg+xml'), '/': ('index.html', 'text/html; charset=utf-8'),
          '/index.html': ('index.html', 'text/html; charset=utf-8'),
          '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
          '/style.css': ('style.css', 'text/css; charset=utf-8')}


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def artifact_path(root, requested):
    """Resolve only JSON receipts inside known artifact directories, including symlinks."""
    root = Path(root).resolve()
    if not requested or Path(requested).is_absolute():
        raise ValueError('An artifact requires a relative path')
    path = (root / requested).resolve()
    relative = path.relative_to(root)
    if path.suffix != '.json' or relative.parts[0] not in ('runs', 'research', 'content'):
        raise ValueError('Only repository JSON artifacts can be opened')
    if not path.is_file():
        raise FileNotFoundError(requested)
    if path.stat().st_size > 8 * 1024 * 1024:
        raise ValueError('Artifact exceeds the 8 MiB viewer limit')
    return path


class Feed:
    def __init__(self, collector, interval=2, github=None, workspace=None):
        self.collector = collector
        self.github = github
        self.workspace = workspace
        self.interval = interval
        self.condition = threading.Condition()
        self.stopped = threading.Event()
        self.snapshot = {'generated_at': utc_now(), 'jobs': [], 'queues': [], 'processes': [],
                         'repairs': [], 'machine': {}, 'coverage': {}, 'warnings': ['Collecting initial state…'],
                         'collector_status': 'starting'}
        self.revision = 0
        self.payload = json.dumps(self.snapshot, ensure_ascii=False).encode()
        self.thread = threading.Thread(target=self._collect, daemon=True, name='dashboard-observer')

    def start(self):
        self.thread.start()

    def _collect(self):
        while not self.stopped.is_set():
            started = time.monotonic()
            try:
                snapshot = self.collector.snapshot()
                if self.github is not None:
                    snapshot['github'] = self.github.snapshot()
                if self.workspace is not None:
                    snapshot.update(self.workspace.snapshot())
                snapshot['collector_status'] = 'ready'
                snapshot['collector_duration_ms'] = round((time.monotonic() - started) * 1000)
                snapshot['refresh_interval_seconds'] = self.interval
            except Exception as exc:
                # Keep the last known work visible; never silently turn a collector failure
                # into zero running agents or a completed queue.
                snapshot = {**self.snapshot, 'collector_status': 'error',
                            'collector_error': f'{type(exc).__name__}: {exc}',
                            'collector_attempted_at': utc_now()}
            payload = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':')).encode()
            with self.condition:
                self.snapshot, self.payload = snapshot, payload
                self.revision += 1
                self.condition.notify_all()
            self.stopped.wait(max(0.1, self.interval - (time.monotonic() - started)))

    def current(self):
        with self.condition:
            return self.revision, self.payload

    def close(self):
        self.stopped.set()
        with self.condition:
            self.condition.notify_all()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, root, feed):
        self.root, self.feed = Path(root).resolve(), feed
        super().__init__(address, Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):
        # Polls are intentionally quiet; server startup and failures remain visible.
        if '200' not in args and '304' not in args:
            super().log_message(format, *args)

    def _headers(self, code, content_type, length=None, **extra):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        if length is not None:
            self.send_header('Content-Length', str(length))
        for key, value in extra.items():
            self.send_header(key.replace('_', '-'), value)
        self.end_headers()

    def _send(self, code, value, content_type='application/json; charset=utf-8', **extra):
        payload = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode()
        self._headers(code, content_type, len(payload), **extra)
        self.wfile.write(payload)

    def do_GET(self):
        parsed = urlsplit(self.path)
        try:
            if parsed.path in STATIC:
                name, mime = STATIC[parsed.path]
                return self._send(200, (ASSETS / name).read_bytes(), mime)
            if parsed.path == '/api/state':
                revision, payload = self.server.feed.current()
                etag = f'"{revision}-{hashlib.sha256(payload).hexdigest()[:12]}"'
                if self.headers.get('If-None-Match') == etag:
                    self._headers(304, 'application/json', 0, ETag=etag)
                    return
                return self._send(200, payload, ETag=etag)
            if parsed.path == '/api/events':
                return self._events()
            if parsed.path == '/api/artifact':
                requested = parse_qs(parsed.query).get('path', [''])[0]
                path = artifact_path(self.server.root, requested)
                # Serve a parsed JSON representation, never script or arbitrary bytes.
                return self._send(200, json.loads(path.read_text(encoding='utf-8')))
            if parsed.path == '/health':
                snapshot = self.server.feed.snapshot
                return self._send(200 if snapshot.get('collector_status') != 'error' else 503,
                                  {'status': snapshot.get('collector_status'),
                                   'generated_at': snapshot.get('generated_at')})
            return self._send(404, {'error': 'Unknown endpoint'})
        except (BrokenPipeError, ConnectionResetError):
            return
        except (ValueError, FileNotFoundError, OSError) as exc:
            return self._send(400, {'error': str(exc)})

    def _events(self):
        self._headers(200, 'text/event-stream; charset=utf-8', Connection='keep-alive',
                      X_Accel_Buffering='no')
        revision = -1
        try:
            while not self.server.feed.stopped.is_set():
                with self.server.feed.condition:
                    if revision == self.server.feed.revision:
                        self.server.feed.condition.wait(timeout=15)
                    current, payload = self.server.feed.revision, self.server.feed.payload
                if current != revision:
                    self.wfile.write(f'id: {current}\nevent: state\ndata: '.encode() + payload + b'\n\n')
                    revision = current
                else:
                    self.wfile.write(b': heartbeat\n\n')
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--interval', type=float, default=2)
    args = parser.parse_args()
    if args.interval < 0.5:
        parser.error('--interval must be at least 0.5 seconds')
    from pipeline.dashboard_data import Collector
    from pipeline.dashboard_github import GitHubFeed, repositories
    github = GitHubFeed(repositories(args.root))
    github.start()
    from pipeline.dashboard_workspace import Workspace
    feed = Feed(Collector(args.root), args.interval, github, Workspace(args.root))
    server = Server((args.host, args.port), args.root, feed)
    feed.start()
    print(f'Live pipeline dashboard: http://{args.host}:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        feed.close()
        github.close()
        server.server_close()


if __name__ == '__main__':
    main()
