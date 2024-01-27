# Copyright 2024 Marimo. All rights reserved.
import json

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

KERNEL_READY_RESPONSE = {
    "codes": ["import marimo as mo"],
    "names": ["__"],
    "layout": None,
    "configs": [{"disabled": False, "hide_code": False}],
}

HEADERS = {
    "Marimo-Server-Token": "fake-token",
}


def assert_kernel_ready_response(data_str: str) -> None:
    as_json = json.loads(data_str)
    data = as_json["data"]
    assert data["cell_ids"]
    assert len(data["cell_ids"]) == 1
    del data["cell_ids"]
    assert data == KERNEL_READY_RESPONSE


def test_ws(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
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


def test_refresh(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert_kernel_ready_response(data)
    # New session with new ID (simulates refresh)
    with client.websocket_connect("/ws?session_id=455") as websocket:
        data = websocket.receive_text()
        assert_kernel_ready_response(data)


def test_disconnect_and_reconnect(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert_kernel_ready_response(data)
        websocket.close()
    # Connect by the same session id
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data == '{"op": "reconnected", "data": null}'  # noqa: E501
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_disconnect_then_reconnect_then_refresh(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert_kernel_ready_response(data)
        websocket.close()
    # Connect by the same session id
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data == '{"op": "reconnected", "data": null}'  # noqa: E501
    # New session with new ID (simulates refresh)
    with client.websocket_connect("/ws?session_id=455") as websocket:
        data = websocket.receive_text()
        assert_kernel_ready_response(data)


def test_fails_on_multiple_connections_with_other_sessions(
    client: TestClient,
) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
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
