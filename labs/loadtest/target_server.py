"""Serveur CIBLE local pour s'entraîner au load-testing (ton propre système).

Lance-le dans ta VM, puis vise-le avec loadtest.py. Il simule une petite API :
chaque requête fait un peu de « travail » (délai paramétrable) et renvoie 200.

    python target_server.py                 # http://127.0.0.1:8090
    python target_server.py --port 8090 --work-ms 5 --max-rps 0

C'est ta cible d'entraînement : tu peux la ralentir, limiter son débit, et
observer comment elle se comporte sous charge.
"""

from __future__ import annotations

import argparse
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_lock = threading.Lock()
_count = 0
_window_start = time.time()
_window_count = 0


class Handler(BaseHTTPRequestHandler):
    work_ms = 0
    max_rps = 0  # 0 = illimité ; sinon renvoie 429 au-delà

    def _throttled(self) -> bool:
        global _window_start, _window_count
        if self.max_rps <= 0:
            return False
        with _lock:
            now = time.time()
            if now - _window_start >= 1.0:
                _window_start, _window_count = now, 0
            _window_count += 1
            return _window_count > self.max_rps

    def do_GET(self):
        global _count
        if self._throttled():
            self.send_response(429)
            self.end_headers()
            self.wfile.write(b"rate limited")
            return
        if self.work_ms:
            time.sleep(self.work_ms / 1000.0)
        with _lock:
            _count += 1
            n = _count
        body = f'{{"ok": true, "served": {n}, "path": "{self.path}"}}'.encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    do_POST = do_GET

    def log_message(self, *a):
        pass  # silencieux


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8090)
    ap.add_argument("--work-ms", type=int, default=0, help="temps de traitement simulé par requête")
    ap.add_argument("--max-rps", type=int, default=0, help="limite de débit (0 = aucune) ; au-delà : 429")
    args = ap.parse_args()
    Handler.work_ms = args.work_ms
    Handler.max_rps = args.max_rps
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Cible d'entraînement sur http://{args.host}:{args.port}  "
          f"(work={args.work_ms}ms, max_rps={args.max_rps or 'illimité'})  —  Ctrl+C pour arrêter")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\narrêt.")


if __name__ == "__main__":
    main()
