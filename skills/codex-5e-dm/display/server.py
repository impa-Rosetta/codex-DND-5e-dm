"""Read-only loopback campaign panel. Never exposes raw logs or world.md."""

from __future__ import annotations

import argparse
import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
from state import StateError, load, public_snapshot

WEB = Path(__file__).resolve().parent / "web"
ASSETS = {"/": ("index.html", "text/html; charset=utf-8"),
          "/style.css": ("style.css", "text/css; charset=utf-8"),
          "/app.js": ("app.js", "text/javascript; charset=utf-8")}


def handler_for(campaign: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, body: bytes, mime: str):
            self.send_response(status)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; connect-src 'self'; style-src 'self'; script-src 'self'")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = self.path.split("?", 1)[0]
            if route in ASSETS:
                name, mime = ASSETS[route]
                self._send(200, (WEB / name).read_bytes(), mime)
                return
            if route == "/api/snapshot":
                try:
                    manifest, state, _ = load(campaign)
                    value = public_snapshot(state, manifest)
                    body = json.dumps(value, ensure_ascii=False).encode("utf-8")
                    self._send(200, body, "application/json; charset=utf-8")
                except StateError as exc:
                    self._send(503, json.dumps({"error": str(exc)}).encode(), "application/json")
                return
            if route == "/api/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                last_revision = -1
                try:
                    for _ in range(120):
                        manifest, state, _ = load(campaign)
                        if state["revision"] != last_revision:
                            data = json.dumps({"revision": state["revision"]})
                            self.wfile.write(f"event: revision\ndata: {data}\n\n".encode())
                            self.wfile.flush()
                            last_revision = state["revision"]
                        time.sleep(1)
                except (BrokenPipeError, ConnectionResetError, StateError):
                    pass
                return
            self._send(404, b"Not found", "text/plain; charset=utf-8")

        def do_POST(self):
            self._send(405, b"Read only", "text/plain; charset=utf-8")

        do_PUT = do_POST
        do_DELETE = do_POST

    return Handler


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("directory")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    campaign = Path(args.directory).resolve()
    load(campaign)
    if not 0 <= args.port <= 65535:
        parser.error("Invalid port")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(campaign))
    print(f"http://127.0.0.1:{server.server_port}/", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
