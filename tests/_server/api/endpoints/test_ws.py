# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from marimo._messaging.ops import KernelReady
from marimo._utils.parse_dataclass import parse_raw


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
        "configs": [{"disabled": False, "hide_code": False}],
    }
    response.update(partial_response)
    return response


KERNEL_READY_RESPONSE = create_response({})

RESUMED_KERNEL_READY_RESPONSE = create_response(
    {
        "resumed": True,
    }
)

HEADERS = {
    "Marimo-Server-Token": "fake-token",
}


def assert_kernel_ready_response(
    raw_data: dict[str, Any], response: dict[str, Any] = KERNEL_READY_RESPONSE
):
    data = parse_raw(raw_data["data"], KernelReady)
    expected = parse_raw(response, KernelReady)
    assert data.cell_ids == expected.cell_ids
    assert data.codes == expected.codes
    assert data.names == expected.names
    assert data.layout == expected.layout
    assert data.resumed == expected.resumed
    assert data.ui_values == expected.ui_values
    assert data.configs == expected.configs


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


def test_disconnect_and_reconnect(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        websocket.close()
    # Connect by the same session id
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": None}
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({"resumed": True}))
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_disconnect_then_reconnect_then_refresh(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        websocket.close()
    # Connect by the same session id
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": None}
    # New session with new ID (simulates refresh)
    with client.websocket_connect("/ws?session_id=455") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)


def test_fails_on_multiple_connections_with_other_sessions(
    client: TestClient,
) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/ws?session_id=456"
            ) as other_websocket:
                other_websocket.receive_text()
                raise AssertionError()
        assert exc_info.value.code == 1003
        assert exc_info.value.reason == "MARIMO_ALREADY_CONNECTED"
    client.post("/api/kernel/shutdown", headers=HEADERS)
