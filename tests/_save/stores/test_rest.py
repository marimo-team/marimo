# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._save.stores import rest

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def rest_server() -> Iterator[tuple[str, list[tuple[str, str, bytes | None]]]]:
    requests: list[tuple[str, str, bytes | None]] = []

    class Handler(BaseHTTPRequestHandler):
        def handle_request(self) -> None:
            body = (
                self.rfile.read(int(self.headers["Content-Length"]))
                if self.command == "PUT"
                else None
            )
            requests.append((self.command, self.path, body))
            self.send_response(200)
            self.end_headers()
            if self.command == "GET":
                self.wfile.write(b"cached-value")

        do_GET = handle_request
        do_HEAD = handle_request
        do_PUT = handle_request

        def log_message(self, format_: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(
        target=lambda: server.serve_forever(poll_interval=0.01), daemon=True
    )
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/cache-api", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("operation", ["get", "read", "hit", "put"])
@pytest.mark.parametrize(
    ("key", "encoded_key"),
    [
        ("plain/entry.json", "plain/entry.json"),
        ("my cache/entry.json", "my%20cache/entry.json"),
        ("my%20cache/entry.json", "my%2520cache/entry.json"),
        ("my%2Fcache/entry.json", "my%252Fcache/entry.json"),
    ],
)
def test_requests_encode_logical_keys(
    rest_server: tuple[str, list[tuple[str, str, bytes | None]]],
    operation: str,
    key: str,
    encoded_key: str,
) -> None:
    base_url, requests = rest_server
    store = rest.RestStore(
        base_url=base_url, api_key="test-key", project_id="project"
    )

    if operation == "put":
        assert store.put(key, b"new-value") is True
        expected_method, expected_body = "PUT", b"new-value"
    elif operation == "hit":
        assert store.hit(key) is True
        expected_method, expected_body = "HEAD", None
    else:
        assert getattr(store, operation)(key) == b"cached-value"
        expected_method, expected_body = "GET", None

    assert requests == [
        (expected_method, f"/cache-api/project/{encoded_key}", expected_body)
    ]


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
