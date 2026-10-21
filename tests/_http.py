# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class RecordedHTTPRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class HTTPEndpoint:
    url: str = ""
    status: int = 200
    body: bytes = b"response"
    delay: float = 0
    chunk_delay: float = 0
    content_length: int | None = None
    headers: dict[str, str] = field(default_factory=dict)
    requests: list[RecordedHTTPRequest] = field(default_factory=list)


@contextmanager
def http_test_server() -> Iterator[HTTPEndpoint]:
    state = HTTPEndpoint()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            pass

        def do_GET(self) -> None:
            self.respond()

        def do_POST(self) -> None:
            self.respond()

        def respond(self) -> None:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            state.requests.append(
                RecordedHTTPRequest(
                    self.command, self.path, dict(self.headers), body
                )
            )
            time.sleep(state.delay)
            try:
                self.send_response(state.status)
                self.send_header(
                    "Content-Length",
                    str(
                        len(state.body)
                        if state.content_length is None
                        else state.content_length
                    ),
                )
                for name, value in state.headers.items():
                    self.send_header(name, value)
                self.end_headers()
                if state.chunk_delay:
                    for byte in state.body:
                        time.sleep(state.chunk_delay)
                        self.wfile.write(bytes([byte]))
                        self.wfile.flush()
                else:
                    self.wfile.write(state.body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state.url = f"http://127.0.0.1:{server.server_port}"
    worker = threading.Thread(
        target=lambda: server.serve_forever(poll_interval=0.01), daemon=True
    )
    worker.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
