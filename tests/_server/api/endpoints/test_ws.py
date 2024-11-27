# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import pytest
from starlette.websockets import WebSocketDisconnect

from marimo._messaging.ops import KernelCapabilities, KernelReady
from marimo._server.api.endpoints.ws import WebSocketCodes
from marimo._server.model import SessionMode
from marimo._server.sessions import SessionManager
from marimo._utils.parse_dataclass import parse_raw
from tests._server.conftest import get_session_manager
from tests._server.mocks import token_header

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
        "last_execution_time": {},
        "kiosk": False,
        "configs": [{"disabled": False, "hide_code": False}],
        "app_config": {"width": "full"},
        "capabilities": asdict(KernelCapabilities()),
    }
    response.update(partial_response)
    return response


HEADERS = {
    **token_header("fake-token"),
}


def headers(session_id: str) -> dict[str, str]:
    return {
        "Marimo-Session-Id": session_id,
        **token_header("fake-token"),
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
    assert data.kiosk == expected.kiosk
    assert data.capabilities == expected.capabilities


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


def test_allows_multiple_connections_with_other_sessions(
    client: TestClient,
) -> None:
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        # Should allow second connection
        with client.websocket_connect("/ws?session_id=456") as other_websocket:
            data = other_websocket.receive_json()
            assert_kernel_ready_response(data)
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_allows_multiple_connections_with_same_file(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    ws_1 = f"/ws?session_id=123&file={temp_marimo_file}"
    ws_2 = f"/ws?session_id=456&file={temp_marimo_file}"
    with client.websocket_connect(ws_1) as websocket:
        data = websocket.receive_json()
        assert_parse_ready_response(data)
        # Should allow second connection
        with client.websocket_connect(ws_2) as other_websocket:
            data = other_websocket.receive_json()
            assert_parse_ready_response(data)
    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_file_watcher_calls_reload(client: TestClient) -> None:
    session_manager: SessionManager = get_session_manager(client)
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        session_manager.mode = SessionMode.RUN
        unsubscribe = session_manager.start_file_watcher()
        filename = session_manager.file_router.get_unique_file_key()
        assert filename
        with open(filename, "a") as f:  # noqa: ASYNC101 ASYNC230
            f.write("\n# test")
            f.close()
        assert session_manager.watcher
        await session_manager.watcher.callback(Path(filename))
        unsubscribe()
        data = websocket.receive_json()
        assert data == {"op": "reload", "data": {}}
        session_manager.mode = SessionMode.EDIT
    client.post("/api/kernel/shutdown", headers=HEADERS)


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


async def test_connect_kiosk_without_session(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: PT012
        with client.websocket_connect(
            "/ws?session_id=123&kiosk=true"
        ) as websocket:
            websocket.receive_json()
            raise AssertionError()
    assert exc_info.value.code == WebSocketCodes.NORMAL_CLOSE
    assert exc_info.value.reason == "MARIMO_NO_SESSION"
    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_connect_kiosk_with_session(client: TestClient) -> None:
    # Create the first session
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        # Connect by the same session id in kiosk mode
        with client.websocket_connect(
            "/ws?session_id=123&kiosk=true"
        ) as other_websocket:
            data = other_websocket.receive_json()
            assert_kernel_ready_response(
                data, create_response({"kiosk": True, "resumed": True})
            )
    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_cannot_connect_kiosk_with_run_session(
    client: TestClient,
) -> None:
    # Create the first session
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        # Connect by the same session id in kiosk mode
        with pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: PT012
            with client.websocket_connect(
                "/ws?session_id=123&kiosk=true"
            ) as other_websocket:
                data = other_websocket.receive_json()
                raise AssertionError()
        assert exc_info.value.code == WebSocketCodes.FORBIDDEN
        assert exc_info.value.reason == "MARIMO_KIOSK_NOT_ALLOWED"

    client.post("/api/kernel/shutdown", headers=HEADERS)
    session_manager.mode = SessionMode.EDIT


def test_connects_to_existing_session_with_same_file(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    ws_1 = f"/ws?session_id=123&file={temp_marimo_file}"
    ws_2 = f"/ws?session_id=456&file={temp_marimo_file}"

    with client.websocket_connect(ws_1) as websocket1:
        data = websocket1.receive_json()
        assert_parse_ready_response(data)

        # Connect second client - should connect to same session
        with client.websocket_connect(ws_2) as websocket2:
            data = websocket2.receive_json()
            assert_parse_ready_response(data)

            # Send a message from first client
            client.post(
                "/api/kernel/set_ui_element_value",
                headers=headers("123"),
                json={
                    "object_ids": ["test"],
                    "values": ["value1"],
                },
            )

            # Both clients should receive the update
            data1 = websocket1.receive_json()
            data2 = websocket2.receive_json()
            assert data1 == data2

    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_replays_messages_when_connecting_to_existing_session(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    ws_1 = f"/ws?session_id=123&file={temp_marimo_file}"
    ws_2 = f"/ws?session_id=456&file={temp_marimo_file}"

    with client.websocket_connect(ws_1) as websocket1:
        data = websocket1.receive_json()
        assert_parse_ready_response(data)

        # Send a message before second client connects
        client.post(
            "/api/kernel/set_ui_element_value",
            headers=token_header("fake-token"),
            json={
                "object_ids": ["test1"],
                "values": ["value1"],
            },
        )
        # First client receives update
        data1 = websocket1.receive_json()

        # Connect second client - should connect to same session
        with client.websocket_connect(ws_2) as websocket2:
            # Should get kernel ready with current state
            data = websocket2.receive_json()
            assert_kernel_ready_response(
                data,
                create_response(
                    {
                        "resumed": True,
                        "ui_values": {"test1": "value1"},
                    }
                ),
            )

            # Should get replayed operation
            data2 = websocket2.receive_json()
            assert data1 == data2

            # New operations should go to both clients
            client.post(
                "/api/kernel/set_ui_element_value",
                headers=token_header("fake-token"),
                json={
                    "object_ids": ["test2"],
                    "values": ["value2"],
                },
            )

            # Both clients receive new update
            data1 = websocket1.receive_json()
            data2 = websocket2.receive_json()
            assert data1 == data2

    client.post("/api/kernel/shutdown", headers=HEADERS)
