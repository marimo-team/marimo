# Copyright 2024 Marimo. All rights reserved.
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

KERNEL_READY_RESPONSE = '{"op": "kernel-ready", "data": {"codes": ["import marimo as mo"], "names": ["my_cell"], "layout": null, "configs": [{"disabled": false, "hide_code": true}]}}'  # noqa: E501


def test_ws(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data == KERNEL_READY_RESPONSE
    # shut down after websocket context manager exists, otherwise
    # the test fails on windows (event loop closed twice)
    client.post("/api/kernel/shutdown")


def test_without_session(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws"):
            raise AssertionError()
    assert exc_info.value.code == 1000
    assert exc_info.value.reason == "MARIMO_NO_SESSION_ID"


def test_refresh(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data == KERNEL_READY_RESPONSE
    # New session with new ID (simulates refresh)
    with client.websocket_connect("/ws?session_id=455") as websocket:
        data = websocket.receive_text()
        assert data == KERNEL_READY_RESPONSE


def test_disconnect_and_reconnect(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data == KERNEL_READY_RESPONSE
        websocket.close()
    # Connect by the same session id
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data == '{"op": "reconnected", "data": null}'  # noqa: E501
    client.post("/api/kernel/shutdown")


def test_disconnect_then_reconnect_then_refresh(client: TestClient) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data == KERNEL_READY_RESPONSE
        websocket.close()
    # Connect by the same session id
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data == '{"op": "reconnected", "data": null}'  # noqa: E501
    # New session with new ID (simulates refresh)
    with client.websocket_connect("/ws?session_id=455") as websocket:
        data = websocket.receive_text()
        assert data == KERNEL_READY_RESPONSE


def test_fails_on_multiple_connections_with_other_sessions(
    client: TestClient,
) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_text()
        assert data == KERNEL_READY_RESPONSE
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(
                "/ws?session_id=456"
            ) as other_websocket:
                other_websocket.receive_text()
                raise AssertionError()
        assert exc_info.value.code == 1003
        assert exc_info.value.reason == "MARIMO_ALREADY_CONNECTED"
    client.post("/api/kernel/shutdown")
