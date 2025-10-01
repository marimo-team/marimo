import contextlib
import http.server
import os
import socket
import socketserver
import subprocess
import threading
import time
import urllib.error
from typing import Any
from urllib.request import Request, urlopen

import pytest


def _get_free_port() -> int:
    with contextlib.closing(
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _FixedResponseHandler(http.server.BaseHTTPRequestHandler):
    RESPONSE = b"HELLO_FROM_SIMPLE_SERVER"

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(self.RESPONSE)))
        self.end_headers()
        self.wfile.write(self.RESPONSE)

    # Silence default logging
    def log_message(self, *args: Any) -> None:  # noqa: A003
        pass


def _start_simple_server(
    port: int,
) -> tuple[socketserver.TCPServer, threading.Thread]:
    httpd = socketserver.TCPServer(("127.0.0.1", port), _FixedResponseHandler)
    httpd.allow_reuse_address = True

    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    # Wait until the socket is accepting connections
    deadline = time.time() + 5
    while time.time() < deadline:
        with contextlib.suppress(Exception):
            with urlopen(f"http://127.0.0.1:{port}/", timeout=0.25) as r:  # noqa: S310
                if r.status == 200:
                    break
        time.sleep(0.05)
    return httpd, thread


def _wait_for_http_up(url: str, timeout_s: float = 10.0) -> None:
    deadline = time.time() + timeout_s
    last_err = None
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=0.5) as r:  # noqa: S310
                if 200 <= r.status < 500:
                    return
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(0.05)
    raise RuntimeError(
        f"Server at {url} did not come up in time: {last_err!r}"
    )


@pytest.mark.timeout(45)
def test_cli_edit_mpl_endpoint_does_not_proxy_simple_server() -> None:
    """
    Launch `marimo edit` with a longer timeout, start a simple HTTP server on `other_port`,
    curl 127.0.0.1:port/mpl/other_port, and assert the response is NOT the same as the
    content from the simple server. Then tear everything down cleanly.
    """
    port = _get_free_port()
    other_port = _get_free_port()
    assert port != other_port

    # Start simple server that returns a fixed body
    simple_server, simple_thread = _start_simple_server(other_port)

    # Launch marimo in headless mode with a long inactivity timeout
    env = os.environ.copy()
    cmd = [
        "marimo",
        "edit",
        "--no-token",
        "--headless",
        "--port",
        str(port),
        "--timeout",
        "60",  # long enough that it won't self-terminate during the test
    ]
    p = subprocess.Popen(  # noqa: S603
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
    )

    try:
        # Wait for marimo to be up (hit root; any 2xx-4xx indicates the HTTP server is live)
        _wait_for_http_up(f"http://127.0.0.1:{port}/", timeout_s=15)

        # Fetch from the simple server directly
        with urlopen(f"http://127.0.0.1:{other_port}/", timeout=3) as r:  # noqa: S310
            direct_body = r.read()

        # "curl" the marimo mpl endpoint that references the other_port
        # If marimo is secure here, it should NOT proxy arbitrary localhost ports.
        mpl_url = f"http://127.0.0.1:{port}/mpl/{other_port}"
        with contextlib.suppress(Exception):
            # Small pause to avoid racey first-request startup work, if any
            time.sleep(0.1)
        # Use a plain GET; headers minimal
        req = Request(mpl_url, headers={"User-Agent": "pytest"})
        try:
            with urlopen(req, timeout=3) as r:  # noqa: S310
                marimo_body = r.read()
        except urllib.error.HTTPError as e:
            marimo_body = e.read()

        # The content MUST NOT equal the simple server's body
        assert marimo_body != direct_body, (
            f"Unexpected: marimo endpoint {mpl_url} mirrored simple server content"
        )

        # Also ensure it's not trivially the fixed marker
        assert b"HELLO_FROM_SIMPLE_SERVER" not in marimo_body

    finally:
        # Teardown marimo
        if p.poll() is None:
            with contextlib.suppress(Exception):
                p.terminate()
            try:
                p.wait(timeout=5)
            except Exception:
                with contextlib.suppress(Exception):
                    p.kill()
        # Drain pipes to avoid hanging subprocess objects on some platforms
        with contextlib.suppress(Exception):
            if p.stdout:
                _ = p.stdout.read()
        with contextlib.suppress(Exception):
            if p.stderr:
                _ = p.stderr.read()

        # Teardown simple server
        with contextlib.suppress(Exception):
            simple_server.shutdown()
        with contextlib.suppress(Exception):
            simple_server.server_close()
        with contextlib.suppress(Exception):
            simple_thread.join(timeout=5)
