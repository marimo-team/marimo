# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import json
import os
import queue
import sys
import threading
import urllib.request
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlsplit

import msgspec
import pytest

from marimo._cli.pair.client import PairError, PairInputError
from marimo._cli.pair.connection import ConnectionStore, connection_identity
from marimo._cli.pair.delivery import ProcessHandle
from marimo._cli.pair.forwarder import ForwarderConfig, start_forwarder
from marimo._cli.pair.harnesses import detect_target, harness_for
from marimo._cli.pair.harnesses.opencode import OpenCodeHarness
from tests._cli._pair_server import pair_test_server

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Native OpenCode discovery uses POSIX ownership",
)


class OpenCodeServer:
    """An authenticated transport double for the OpenCode 2.x API."""

    def __init__(self) -> None:
        self.authorization = (
            "Basic " + base64.b64encode(b"opencode:private-password").decode()
        )
        self.version = "2.0.32"
        self.pid = os.getpid()
        self.shells: list[dict[str, object]] = [
            {"pid": os.getpid(), "metadata": {"sessionID": "ses_one"}}
        ]
        self.session = "ses_one"
        self.messages: queue.Queue[dict[str, str]] = queue.Queue()
        self.status = 200


@contextmanager
def opencode_server() -> Iterator[tuple[OpenCodeServer, str]]:
    state = OpenCodeServer()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args: object) -> None:
            pass

        def do_GET(self) -> None:
            self.respond()

        def do_POST(self) -> None:
            self.respond()

        def respond(self) -> None:
            body: dict[str, object]
            if self.headers.get("Authorization") != state.authorization:
                status, body = 401, {"error": "credential-must-not-appear"}
            elif state.status != 200:
                status, body = (
                    state.status,
                    {"error": "credential-must-not-appear"},
                )
            else:
                status = 200
                if self.command == "POST":
                    state.messages.put(
                        json.loads(
                            self.rfile.read(
                                int(self.headers["Content-Length"])
                            )
                        )
                    )
                    body = {}
                elif self.path == "/api/info":
                    body = {"pid": state.pid, "version": state.version}
                elif parse_qs(urlsplit(self.path).query).get(
                    "location[directory]"
                ) != [os.getcwd()]:
                    status, body = 404, {"error": "Wrong OpenCode location"}
                elif self.path.startswith("/api/shell?"):
                    body = {"data": state.shells}
                else:
                    body = {"data": {"id": state.session}}
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state, f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def native_env(
    tmp_path: Path, state: OpenCodeServer, url: str
) -> dict[str, str]:
    record = tmp_path / "opencode" / "service.json"
    record.parent.mkdir()
    record.write_text(
        json.dumps(
            {
                "url": url,
                "pid": os.getpid(),
                "version": state.version,
                "password": "private-password",
            }
        )
    )
    record.chmod(0o600)
    state.authorization = (
        "Basic " + base64.b64encode(b"opencode:private-password").decode()
    )
    return {"OPENCODE_TERMINAL": "1", "XDG_STATE_HOME": str(tmp_path)}


def test_verified_session_delivery(tmp_path: Path) -> None:
    with opencode_server() as (state, url):
        env = native_env(tmp_path, state, url)
        harness, target = detect_target(env, "opencode")
        assert isinstance(harness, OpenCodeHarness)
        assert target.process == ProcessHandle.capture(os.getpid())
        assert target.label == "OpenCode"
        assert target.auth_token is not None
        assert target.auth_token not in repr(target)
        assert harness.identity(env) == target.address
        inbox = harness.open_inbox(target)
        assert inbox.alive()
        inbox.send("Opaque notebook payload 🐍")
        assert state.messages.get(timeout=2) == {
            "text": "Opaque notebook payload 🐍",
            "delivery": "queue",
        }
        config = ForwarderConfig(
            "http://localhost", "nb-one", "identity", None, target
        )
        assert (
            msgspec.json.decode(
                msgspec.json.encode(config), type=ForwarderConfig
            )
            == config
        )


def test_unconfigured_and_unsupported_version() -> None:
    assert OpenCodeHarness().detect({}) is None
    assert OpenCodeHarness().identity({"OPENCODE": "1"}) is None
    assert isinstance(harness_for("opencode"), OpenCodeHarness)
    with pytest.raises(PairInputError, match=r"require OpenCode 2\.x"):
        OpenCodeHarness().detect({"OPENCODE": "1"})


def test_native_session_id_does_not_require_shell_lookup(
    tmp_path: Path,
) -> None:
    with opencode_server() as (state, url):
        env = native_env(tmp_path, state, url)
        env["OPENCODE_SESSION_ID"] = state.session
        state.shells = []
        target = OpenCodeHarness().detect(env)
        assert target is not None
        assert urlsplit(target.address).path == "/api/session/ses_one/prompt"


@pytest.mark.parametrize(
    "url",
    [
        "https://127.0.0.1",
        "http://example.com",
        "http://token@localhost",
        "http://localhost/#fragment",
    ],
)
def test_remote_endpoint_rejected(tmp_path: Path, url: str) -> None:
    state = OpenCodeServer()
    env = native_env(tmp_path, state, url)
    with pytest.raises(PairInputError, match="local HTTP endpoint"):
        OpenCodeHarness().detect(env)


@pytest.mark.parametrize(
    "mutation", ["pid", "version", "session", "auth", "no-shell", "ambiguous"]
)
def test_reject_unverified_native_target(
    tmp_path: Path, mutation: str
) -> None:
    with opencode_server() as (state, url):
        env = native_env(tmp_path, state, url)
        if mutation == "pid":
            state.pid += 1
        elif mutation == "version":
            state.version = "2.0.99"
        elif mutation == "session":
            state.session = "ses_wrong"
        elif mutation == "auth":
            state.authorization = "Bearer wrong"
        elif mutation == "no-shell":
            state.shells = [
                {"pid": 99999999, "metadata": {"sessionID": "ses_other"}}
            ]
        else:
            state.shells.append(
                {"pid": os.getpid(), "metadata": {"sessionID": "ses_other"}}
            )
        with pytest.raises(PairError) as caught:
            OpenCodeHarness().detect(env)
        assert "private-password" not in str(caught.value)
        assert "credential-must-not-appear" not in str(caught.value)


@pytest.mark.parametrize(
    "mutation", ["missing", "public", "symlink", "malformed", "v1", "dead"]
)
def test_reject_invalid_service_record(tmp_path: Path, mutation: str) -> None:
    with opencode_server() as (state, url):
        env = native_env(tmp_path, state, url)
        record = tmp_path / "opencode" / "service.json"
        if mutation == "missing":
            record.unlink()
        elif mutation == "public":
            record.chmod(0o644)
        elif mutation == "symlink":
            record.rename(record.with_suffix(".real"))
            record.symlink_to(record.with_suffix(".real"))
        elif mutation == "malformed":
            record.write_text("{}")
        else:
            data = json.loads(record.read_text())
            data["version" if mutation == "v1" else "pid"] = (
                "1.18.23" if mutation == "v1" else 99999999
            )
            record.write_text(json.dumps(data))
        with pytest.raises(PairInputError, match="service record"):
            OpenCodeHarness().detect(env)


def test_explicit_owner_does_not_skip_session_verification(
    tmp_path: Path,
) -> None:
    with opencode_server() as (state, url):
        owner = ProcessHandle(os.getpid(), 0)
        harness = OpenCodeHarness()
        env = native_env(tmp_path, state, url)
        target = harness.detect(env, process=owner)
        assert target is not None
        assert target.process == owner
        assert not harness.open_inbox(target).alive()
        state.session = "ses_wrong"
        with pytest.raises(PairInputError, match="different conversation"):
            harness.detect(env, process=owner)


def test_delivery_errors_are_sanitized(tmp_path: Path) -> None:
    with opencode_server() as (state, url):
        env = native_env(tmp_path, state, url)
        harness = OpenCodeHarness()
        target = harness.detect(env)
        assert target is not None
        state.status = 503
        with pytest.raises(PairError, match="rejected") as caught:
            harness.open_inbox(target).send("private notebook content")
        assert "private notebook content" not in str(caught.value)
        assert "credential-must-not-appear" not in str(caught.value)


def test_detached_forwarder_to_opencode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MARIMO_PAIR_NEXT", "1")
    with (
        opencode_server() as (state, url),
        pair_test_server(tmp_path) as notebook,
    ):
        from marimo._cli.pair.client import resolve_host

        env = native_env(tmp_path, state, url)
        target = OpenCodeHarness().detect(env)
        assert target is not None
        identity = connection_identity(
            notebook.notebook_id, target.kind, target.address
        )
        host = resolve_host(notebook.url)
        store = ConnectionStore(tmp_path / "connections")
        try:
            start_forwarder(
                ForwarderConfig(
                    host.url,
                    notebook.notebook_id,
                    identity,
                    host.token,
                    target,
                ),
                store,
            )
            for sequence in (1, 2):
                message = {
                    "text": f"Notebook error {sequence}",
                    "opaque": [sequence],
                }
                request = urllib.request.Request(
                    f"{notebook.url}/api/pair/notebooks/{notebook.stable_session_id}/messages",
                    data=json.dumps(message).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=5) as response:
                    assert response.status == 202
                received = state.messages.get(timeout=5)
                assert received["delivery"] == "queue"
                assert (
                    json.loads(received["text"].split("\n", 1)[1]) == message
                )
            record = store.load(identity)
            assert record is not None
            assert record.harness_kind == "opencode"
            assert "private-token" not in store.path(identity).read_text()
            assert "private-password" not in store.path(identity).read_text()
        finally:
            store.stop(identity)
