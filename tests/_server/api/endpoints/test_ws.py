# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import pytest
from starlette.websockets import WebSocketDisconnect

from marimo._messaging.ops import KernelReady
from marimo._server.model import SessionMode
from marimo._server.sessions import SessionManager
from marimo._utils.parse_dataclass import parse_raw
from tests._server.conftest import get_session_manager

if TYPE_CHECKING:
    from starlette.testclient import TestClient


def create_response(
    partial_response: dict[str, Any],
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "cell_ids": ["Hbol"],
        "codes": ["import marimo as mo"],
        "names": ["__"],
        "layout": None,
        "resumed": False,
        "ui_values": {},
        "last_executed_code": {},
        "configs": [{"disabled": False, "hide_code": False}],
        "app_config": {"width": "full"},
    }
    response.update(partial_response)
    return response


HEADERS = {
    "Marimo-Server-Token": "fake-token",
}


def assert_kernel_ready_response(
    raw_data: dict[str, Any], response: Optional[dict[str, Any]] = None
) -> None:
    if response is None:
        response = create_response({})
    data = parse_raw(raw_data["data"], KernelReady)
    expected = parse_raw(response, KernelReady)
    assert data.cell_ids == expected.cell_ids
    assert data.codes == expected.codes
    assert data.names == expected.names
    assert data.layout == expected.layout
    assert data.resumed == expected.resumed
    assert data.ui_values == expected.ui_values
    assert data.configs == expected.configs
    assert data.app_config == expected.app_config


def assert_parse_ready_response(raw_data: dict[str, Any]) -> None:
    data = parse_raw(raw_data["data"], KernelReady)
    assert data is not None


def test_ws(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
    # shut down after websocket context manager exists, otherwise
    # the test fails on windows (event loop closed twice)
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_without_session(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws"):
            raise AssertionError()
    assert exc_info.value.code == 1000
    assert exc_info.value.reason == "MARIMO_NO_SESSION_ID"
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_disconnect_and_reconnect(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
    # Connect by the same session id
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {}}
        data = websocket.receive_json()
        assert data["op"] == "alert"

    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_disconnect_then_reconnect_then_refresh(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        websocket.close()
    # Connect by the same session id
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {}}
        data = websocket.receive_json()
        assert data["op"] == "alert"
    # New session with new ID (simulates refresh)
    with client.websocket_connect("/ws?session_id=456") as websocket:
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {}}
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({"resumed": True}))

    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_fails_on_multiple_connections_with_other_sessions(
    client: TestClient,
) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        with pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: PT012
            with client.websocket_connect(
                "/ws?session_id=456"
            ) as other_websocket:
                other_websocket.receive_json()
                raise AssertionError()
        assert exc_info.value.code == 1003
        assert exc_info.value.reason == "MARIMO_ALREADY_CONNECTED"
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_fails_on_multiple_connections_with_same_file(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    ws_1 = f"/ws?session_id=123&file={temp_marimo_file}"
    ws_2 = f"/ws?session_id=456&file={temp_marimo_file}"
    with client.websocket_connect(ws_1) as websocket:
        data = websocket.receive_json()
        assert_parse_ready_response(data)
        with pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: PT012
            with client.websocket_connect(ws_2) as other_websocket:
                other_websocket.receive_json()
                raise AssertionError()
        assert exc_info.value.code == 1003
        assert exc_info.value.reason == "MARIMO_ALREADY_CONNECTED"
    client.post("/api/kernel/shutdown", headers=HEADERS)


@pytest.mark.asyncio
async def test_file_watcher_calls_reload(client: TestClient) -> None:
    session_manager: SessionManager = get_session_manager(client)
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        session_manager.mode = SessionMode.RUN
        unsubscribe = session_manager.start_file_watcher()
        filename = session_manager.file_router.get_unique_file_key()
        assert filename
        with open(filename, "a") as f:  # noqa: ASYNC101
            f.write("\n# test")
            f.close()
        assert session_manager.watcher
        await session_manager.watcher.callback(Path(filename))
        unsubscribe()
        data = websocket.receive_json()
        assert data == {"op": "reload", "data": {}}
        session_manager.mode = SessionMode.EDIT
    client.post("/api/kernel/shutdown", headers=HEADERS)


@pytest.mark.asyncio
async def test_query_params(client: TestClient) -> None:
    with client.websocket_connect(
        "/ws?session_id=123&foo=1&bar=2&bar=3&baz=4"
    ) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        session = get_session_manager(client).get_session("123")
        assert session
        assert session.kernel_manager.app_metadata.query_params == {
            "foo": "1",
            "bar": ["2", "3"],
            "baz": "4",
        }
    client.post("/api/kernel/shutdown", headers=HEADERS)
