# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._save.cache import Cache
from marimo._save.hash import HashKey
from marimo._save.loaders.json import JsonLoader
from marimo._save.stores import rest

if TYPE_CHECKING:
    from collections.abc import Iterator


def test_get_logs_unexpected_response_status() -> None:
    store = rest.RestStore(
        base_url="https://cache.example.com", api_key="test-key"
    )
    response = MagicMock()
    response.status = 500
    response.__enter__.return_value = response

    with (
        patch.object(rest.urllib.request, "urlopen", return_value=response),
        patch.object(rest.LOGGER, "warning") as warning,
    ):
        result = store.get("cache-key")

    assert result is None
    warning.assert_called_once_with(
        "GET %s - Unexpected status: %s",
        "https://cache.example.com/cache-key",
        500,
    )


class _RecordingHandler(BaseHTTPRequestHandler):
    """Serve PUT bodies back on GET and HEAD, keyed by the raw request path."""

    blobs: dict[str, bytes]
    requests: list[tuple[str, str]]

    def do_PUT(self) -> None:
        self.requests.append(("PUT", self.path))
        length = int(self.headers["Content-Length"])
        self.blobs[self.path] = self.rfile.read(length)
        self.send_response(200)
        self.end_headers()

    def do_GET(self) -> None:
        self.requests.append(("GET", self.path))
        blob = self.blobs.get(self.path)
        if blob is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(blob)

    def do_HEAD(self) -> None:
        self.requests.append(("HEAD", self.path))
        self.send_response(200 if self.path in self.blobs else 404)
        self.end_headers()

    def log_message(self, *args: object) -> None:
        del args


@pytest.fixture
def server() -> Iterator[tuple[str, type[_RecordingHandler]]]:
    handler = type(
        "Handler", (_RecordingHandler,), {"blobs": {}, "requests": []}
    )
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{httpd.server_port}", handler
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join()


@pytest.mark.parametrize(
    ("key", "path"),
    [
        ("my_cache/P_repro.json", "/my_cache/P_repro.json"),
        ("my cache/P_repro.json", "/my%20cache/P_repro.json"),
        # An already-escaped key is a logical name, so it is escaped again.
        ("my%20cache/P_repro.json", "/my%2520cache/P_repro.json"),
    ],
)
def test_round_trip_encodes_key_path(
    server: tuple[str, type[_RecordingHandler]], key: str, path: str
) -> None:
    base_url, handler = server
    store = rest.RestStore(base_url=base_url, api_key="test-key")

    assert store.put(key, b"payload")
    assert store.hit(key)
    assert store.get(key) == b"payload"
    assert store.read(key) == b"payload"
    assert handler.requests == [
        ("PUT", path),
        ("HEAD", path),
        ("GET", path),
        ("GET", path),
    ]


def test_project_id_prefix_is_not_encoded(
    server: tuple[str, type[_RecordingHandler]],
) -> None:
    base_url, handler = server
    store = rest.RestStore(
        base_url=base_url, api_key="test-key", project_id="team%2Fproj"
    )

    assert store.put("my cache/P_repro.json", b"payload")
    assert handler.requests == [
        ("PUT", "/team%2Fproj/my%20cache/P_repro.json")
    ]


def test_json_loader_restores_cache_name_with_space(
    server: tuple[str, type[_RecordingHandler]],
) -> None:
    base_url, _ = server
    store = rest.RestStore(base_url=base_url, api_key="test-key")
    loader = JsonLoader("my cache", store=store)
    key = HashKey(hash="repro", cache_type="Pure")
    cache = Cache(
        defs={"answer": 42},
        hash="repro",
        cache_type="Pure",
        stateful_refs=set(),
        hit=False,
        meta={},
    )

    assert loader.save_cache(cache)
    restored = loader.load_cache(key)

    assert restored is not None
    assert restored.defs == {"answer": 42}
