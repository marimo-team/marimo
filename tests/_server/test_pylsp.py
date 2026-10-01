# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosedError, InvalidStatus

from marimo._server._pylsp import create_server, pylsp_connection
from marimo._server.lsp import PyLspServer
from marimo._utils.net import find_free_port
from tests._server.conftest import serve_in_thread

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    ("headers", "origin"),
    [
        ({}, None),
        ({"Marimo-LSP-Token": ""}, None),
        ({"Marimo-LSP-Token": "wrong"}, None),
        ({"Marimo-LSP-Token": "x" * len("test-token")}, None),
        ({"Marimo-LSP-Token": "test-token-extra"}, None),
        ({"Marimo-LSP-Token": "tést-token"}, None),
        ({"Marimo-LSP-Token": "test-token, test-token"}, None),
        ({}, "https://attacker.test"),
        ({"Marimo-LSP-Token": "test-token"}, "https://attacker.test"),
        ({"Marimo-LSP-Token": "test-token"}, "http://evil.example.com"),
        ({"Marimo-LSP-Token": "test-token"}, "null"),
        ({"Marimo-LSP-Token": "test-token"}, "http://127.0.0.1"),
        ({"Marimo-LSP-Token": "test-token"}, ""),
        (
            [
                ("Marimo-LSP-Token", "test-token"),
                ("Marimo-LSP-Token", "test-token"),
            ],
            None,
        ),
        (
            [
                ("Marimo-LSP-Token", "wrong"),
                ("Marimo-LSP-Token", "test-token"),
            ],
            None,
        ),
        (
            [
                ("Marimo-LSP-Token", "test-token"),
                ("Marimo-LSP-Token", "wrong"),
            ],
            None,
        ),
    ],
)
async def test_rejects_direct_connections(monkeypatch, headers, origin):
    handler = Mock(side_effect=lambda ws: ws.send(ws.recv()))
    monkeypatch.setattr("marimo._server._pylsp.pylsp_connection", handler)
    with create_server(0, "test-token") as server, serve_in_thread(server):
        host, port = server.socket.getsockname()
        assert host == "127.0.0.1"
        with pytest.raises(InvalidStatus) as exc:
            async with connect(
                f"ws://{host}:{port}",
                additional_headers=headers,
                origin=origin,
            ):
                pytest.fail("Unauthorized connection accepted")
        assert exc.value.response.status_code == 403
        handler.assert_not_called()
        # A rejected handshake must not poison subsequent valid connections.
        async with connect(
            f"ws://{host}:{port}",
            additional_headers={"marimo-lsp-token": "test-token"},
        ) as websocket:
            await websocket.send("still available")
            assert (
                await asyncio.wait_for(websocket.recv(), 5)
                == "still available"
            )
        handler.assert_called_once()


def test_requires_token():
    with pytest.raises(ValueError, match="MARIMO_LSP_TOKEN"):
        create_server(0, "")


@pytest.mark.parametrize("token", [None, ""])
def test_launcher_fails_closed_without_token(tmp_path: Path, token):
    server = PyLspServer(0)
    server.log_file = tmp_path / "pylsp.log"
    env = dict(os.environ)
    env.pop("MARIMO_LSP_TOKEN", None)
    if token is not None:
        env["MARIMO_LSP_TOKEN"] = token
    result = subprocess.run(
        server.get_command(),
        env=env,
        capture_output=True,
        text=True,
        timeout=5,
    )
    assert result.returncode != 0
    assert "MARIMO_LSP_TOKEN must be set" in result.stderr


@pytest.mark.parametrize(
    "failure", ["receive", "decode", "consume", "send", "shutdown"]
)
def test_handler_releases_resources_on_failure(monkeypatch, failure):
    pylsp = pytest.importorskip("pylsp.python_lsp")
    handler = Mock(config=Mock(), _shutdown=False)
    factory = Mock(return_value=handler)
    monkeypatch.setattr(pylsp, "PythonLSPServer", factory)
    websocket = MagicMock()
    websocket.__iter__.return_value = iter(
        ['{"jsonrpc":"2.0","method":"example"}']
    )
    error = RuntimeError(f"{failure} failed")
    expected_error = RuntimeError
    if failure == "receive":
        websocket.__iter__.side_effect = error
    elif failure == "decode":
        websocket.__iter__.return_value = iter(["invalid JSON"])
        expected_error = json.JSONDecodeError
    elif failure == "consume":
        handler.consume.side_effect = error
    elif failure == "send":
        websocket.send.side_effect = error
        handler.consume.side_effect = lambda _: factory.call_args.kwargs[
            "consumer"
        ]({})
    else:
        handler.m_shutdown.side_effect = error

    with pytest.raises(expected_error):
        pylsp_connection(websocket)
    handler.m_shutdown.assert_called_once()
    handler.m_exit.assert_called_once()


@pytest.mark.parametrize(
    ("initialized", "shutdown"), [(False, False), (True, False), (True, True)]
)
def test_handler_disconnect_cleanup(monkeypatch, initialized, shutdown):
    pylsp = pytest.importorskip("pylsp.python_lsp")
    handler = Mock(config=Mock() if initialized else None, _shutdown=shutdown)
    monkeypatch.setattr(pylsp, "PythonLSPServer", Mock(return_value=handler))
    websocket = MagicMock()
    websocket.__iter__.return_value = iter([])

    pylsp_connection(websocket)

    assert handler.m_shutdown.call_count == int(initialized and not shutdown)
    handler.m_exit.assert_called_once()


@pytest.mark.parametrize(
    "failure", ["invalid-json", "invalid-utf8", "disconnect"]
)
async def test_bad_client_does_not_stop_server(failure):
    pytest.importorskip("pylsp")
    with create_server(0, "test-token") as server, serve_in_thread(server):
        host, port = server.socket.getsockname()
        url = f"ws://{host}:{port}"
        headers = {"Marimo-LSP-Token": "test-token"}
        async with connect(url, additional_headers=headers) as websocket:
            if failure == "disconnect":
                websocket.transport.abort()
            else:
                await websocket.send(
                    "invalid JSON" if failure == "invalid-json" else b"\xff"
                )
                with pytest.raises(ConnectionClosedError) as exc:
                    await asyncio.wait_for(websocket.recv(), 5)
                assert exc.value.rcvd.code == 1011

        async with connect(url, additional_headers=headers) as websocket:
            await websocket.send('{"jsonrpc":"2.0","id":1,"method":"unknown"}')
            response = json.loads(await asyncio.wait_for(websocket.recv(), 5))
            assert response["error"]["code"] == -32601


async def test_pylsp_launcher(tmp_path: Path):
    pytest.importorskip("pylsp")
    server = PyLspServer(find_free_port(23100))
    server.log_file = tmp_path / "pylsp.log"
    try:
        assert await server.start() is None
        assert server.is_running()
        with pytest.raises(InvalidStatus):
            async with connect(f"ws://127.0.0.1:{server.port}"):
                pytest.fail("Unauthorized connection accepted")
        async with connect(
            f"ws://127.0.0.1:{server.port}",
            additional_headers={"Marimo-LSP-Token": server.auth_token},
        ) as websocket:
            await websocket.send(
                json.dumps({"jsonrpc": "2.0", "id": 1, "method": "unknown"})
            )
            response = json.loads(await asyncio.wait_for(websocket.recv(), 10))
            assert response["error"]["code"] == -32601
    finally:
        server.stop()
    assert server.auth_token not in server.log_file.read_text()


async def test_authenticated_pylsp(tmp_path: Path):
    pytest.importorskip("pylsp")
    target = tmp_path / "fixture.py"
    target.write_text("def example():\n    return 42\n")
    with create_server(0, "test-token") as server, serve_in_thread(server):
        host, port = server.socket.getsockname()
        # Reconnection must still work after the first handler is disposed.
        for _ in range(2):
            async with connect(
                f"ws://{host}:{port}/lsp/pylsp",
                additional_headers={"Marimo-LSP-Token": "test-token"},
            ) as websocket:
                await websocket.send(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 1,
                            "method": "initialize",
                            "params": {
                                "processId": None,
                                "rootUri": tmp_path.as_uri(),
                                "capabilities": {},
                            },
                        }
                    )
                )
                response = json.loads(
                    await asyncio.wait_for(websocket.recv(), 10)
                )
                assert "capabilities" in response["result"]
                await websocket.send(
                    json.dumps(
                        {
                            "jsonrpc": "2.0",
                            "id": 2,
                            "method": "textDocument/documentSymbol",
                            "params": {
                                "textDocument": {"uri": target.as_uri()}
                            },
                        }
                    )
                )
                response = json.loads(
                    await asyncio.wait_for(websocket.recv(), 10)
                )
                assert response["result"][0]["name"] == "example"
