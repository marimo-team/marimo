# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import pytest
from pycrdt import (
    YMessageType,
)
from starlette.websockets import WebSocketDisconnect

from marimo._config.manager import UserConfigManager
from marimo._messaging.ops import KernelCapabilities, KernelReady
from marimo._server.api.endpoints.ws import (
    CellIdAndFileKey,
    WebSocketCodes,
    clean_cell,
)
from marimo._server.model import SessionMode
from marimo._server.sessions import SessionManager
from marimo._utils.parse_dataclass import parse_raw
from tests._server.conftest import get_session_manager, get_user_config_manager
from tests._server.mocks import token_header

if TYPE_CHECKING:
    from starlette.testclient import TestClient, WebSocketTestSession


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
    with rtc_enabled(get_user_config_manager(client)):
        with client.websocket_connect("/ws?session_id=123") as websocket:
            data = websocket.receive_json()
            assert_kernel_ready_response(data)
            # Should allow second connection
            with client.websocket_connect(
                "/ws?session_id=456"
            ) as other_websocket:
                data = other_websocket.receive_json()
                assert_kernel_ready_response(
                    data, create_response({"resumed": True})
                )
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


def test_allows_multiple_connections_with_same_file(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    with rtc_enabled(get_user_config_manager(client)):
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


async def test_file_watcher_calls_reload(client: TestClient) -> None:
    session_manager: SessionManager = get_session_manager(client)
    session_manager.watch = True
    with client.websocket_connect("/ws?session_id=123") as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        session_manager.mode = SessionMode.RUN
        filename = session_manager.file_router.get_unique_file_key()
        assert filename
        with open(filename, "a") as f:  # noqa: ASYNC101 ASYNC230
            f.write("\n# test")
            f.close()
        assert session_manager.watcher_manager._watchers
        watcher = list(session_manager.watcher_manager._watchers.values())[0]
        await watcher.callback(Path(filename))
        data = websocket.receive_json()
        assert data == {"op": "reload", "data": {}}
        session_manager.mode = SessionMode.EDIT
        session_manager.watch = False
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


async def test_connects_to_existing_session_with_same_file(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    ws_1 = f"/ws?session_id=123&file={temp_marimo_file}"
    ws_2 = f"/ws?session_id=456&file={temp_marimo_file}"

    with rtc_enabled(get_user_config_manager(client)):
        with client.websocket_connect(ws_1) as websocket1:
            data = websocket1.receive_json()
            assert_parse_ready_response(data)

            # Instantiate the session
            client.post(
                "/api/kernel/instantiate",
                headers=headers("123"),
                json={"object_ids": [], "values": [], "auto_run": True},
            )

            messages1 = flush_messages(websocket1, at_least=14)
            # This can/may change if implementation changes, but this is a snapshot to
            # make sure it doesn't change when we don't expect it to
            assert len(messages1) == 14
            assert messages1[0]["op"] == "variables"

            # Connect second client - should connect to same session
            with client.websocket_connect(ws_2) as websocket2:
                # Check in the same room
                session_manager = get_session_manager(client)
                assert len(session_manager.sessions) == 1
                assert session_manager.sessions["123"].room.size == 2

                data2 = websocket2.receive_json()
                assert_parse_ready_response(data2)
                assert data2["data"]["resumed"] is True

                messages2 = flush_messages(websocket2, at_least=4)
                # This can/may change if implementation changes, but this is a snapshot to
                # make sure it doesn't change when we don't expect it to
                assert len(messages2) == 4
                assert messages2[0]["op"] == "variables"

    client.post("/api/kernel/shutdown", headers=HEADERS)


def flush_messages(
    websocket: WebSocketTestSession, at_least: int = 0
) -> list[dict[str, Any]]:
    # There is no way to properly flush messages from the websocket
    # without using a timeout or non-blocking calls
    # So we just keep calling receive_json until we get at least the number of messages we expect
    messages: list[dict[str, Any]] = []
    while len(messages) < at_least:
        messages.append(websocket.receive_json())
    return messages


@contextmanager
def rtc_enabled(config: UserConfigManager):
    prev_config = config.get_config()
    try:
        config.save_config({"experimental": {"rtc_v2": True}})
        yield
    finally:
        config.save_config(prev_config)


async def test_ycell_sync(client: TestClient) -> None:
    """Test that Y-CRDT sync works between multiple clients"""
    ws_1 = "/ws?session_id=123"
    ws_2 = "/ws?session_id=456"

    cell_id = "Hbol"

    ws_1_cell_1 = f"/ws/{cell_id}?session_id=123"
    ws_2_cell_1 = f"/ws/{cell_id}?session_id=456"

    # First connect main websocket to create session
    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect(ws_1) as websocket,
        client.websocket_connect(ws_2) as websocket2,
    ):
        data = websocket.receive_json()
        assert_parse_ready_response(data)
        data2 = websocket2.receive_json()
        assert_parse_ready_response(data2)

        # Connect first client to cell websocket
        with client.websocket_connect(ws_1_cell_1) as cell_ws1:
            # Should receive initial sync message
            sync_msg1 = cell_ws1.receive_bytes()
            assert sync_msg1[0] == YMessageType.SYNC

            # Connect second client
            with client.websocket_connect(ws_2_cell_1) as cell_ws2:
                # Should receive initial sync
                sync_msg2 = cell_ws2.receive_bytes()
                assert sync_msg2[0] == YMessageType.SYNC

                # Send update from client 1
                update_msg = bytes([YMessageType.AWARENESS]) + b"test update"
                cell_ws1.send_bytes(update_msg)

                # Client 2 should receive the update
                # TODO: This hangs
                # received = cell_ws2.receive_bytes()
                # assert received[0] == YMessageType.AWARENESS
                # assert received[1:] == b"test update"

    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_ycell_cleanup_on_session_close(
    client: TestClient,
) -> None:
    """Test that cell websockets are cleaned up when session closes"""
    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect("/ws?session_id=123") as websocket,
    ):
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        cell_id = "Hbol"
        # Connect to cell websocket
        with client.websocket_connect(
            f"/ws/{cell_id}?session_id=123"
        ) as cell_ws:
            sync_msg = cell_ws.receive_bytes()
            assert sync_msg[0] == YMessageType.SYNC

            # Close main websocket
            websocket.close()

            # Cell websocket should close automatically
            # TODO: This hangs
            # with pytest.raises(WebSocketDisconnect):
            #     while True:
            #         cell_ws.receive_bytes()

    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_ycell_persistence(client: TestClient) -> None:
    """Test that cell content persists between connections"""
    cell_id = "Hbol"
    initial_code = "print('hello')"

    # First connection sets initial code
    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect("/ws?session_id=123") as websocket,
    ):
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        with client.websocket_connect(
            f"/ws/{cell_id}?session_id=123"
        ) as cell_ws1:
            sync_msg = cell_ws1.receive_bytes()
            assert sync_msg[0] == YMessageType.SYNC

            # Send initial code
            update_msg = (
                bytes([YMessageType.AWARENESS]) + initial_code.encode()
            )
            cell_ws1.send_bytes(update_msg)

    # Second connection should receive persisted code
    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect("/ws?session_id=456") as websocket,
    ):
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({"resumed": True}))

        with client.websocket_connect(
            f"/ws/{cell_id}?session_id=456"
        ) as cell_ws2:
            sync_msg = cell_ws2.receive_bytes()
            # Verify initial code is preserved
            assert sync_msg[0] == YMessageType.SYNC
            # Sync message contains binary yjs data, not raw code
            assert len(sync_msg[1:]) > 0

    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_ycell_cleanup_after_close(
    client: TestClient, temp_marimo_file: str
) -> None:
    """Test that cell data is cleaned up after all clients disconnect"""
    from marimo._server.api.endpoints.ws import ycells

    cell_id = "Hbol"

    with client.websocket_connect(
        f"/ws?session_id=123&file={temp_marimo_file}"
    ) as websocket:
        data = websocket.receive_json()
        assert_parse_ready_response(data)

        with client.websocket_connect(
            f"/ws/{cell_id}?session_id=123&file={temp_marimo_file}"
        ) as cell_ws:
            key = CellIdAndFileKey(cell_id, temp_marimo_file)
            sync_msg = cell_ws.receive_bytes()
            assert sync_msg[0] == YMessageType.SYNC
            assert key in ycells

            # Close websocket
            cell_ws.close()

            # Cell should still exist
            assert key in ycells

            # Wait for cleanup
            await clean_cell(key, timeout=0.01)

            # Cell should be removed
            assert key not in ycells

    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_ycell_multiple_clients(
    client: TestClient, temp_marimo_file: str
) -> None:
    """Test multiple clients can connect to same cell"""
    cell_id = "Hbol"

    with client.websocket_connect(
        f"/ws?session_id=123&file={temp_marimo_file}"
    ) as websocket:
        data = websocket.receive_json()
        assert_parse_ready_response(data)

        # Connect first client
        with client.websocket_connect(
            f"/ws/{cell_id}?session_id=123&file={temp_marimo_file}"
        ) as cell_ws1:
            sync_msg1 = cell_ws1.receive_bytes()
            assert sync_msg1[0] == YMessageType.SYNC

            # Connect second client
            with client.websocket_connect(
                f"/ws/{cell_id}?session_id=123&file={temp_marimo_file}"
            ) as cell_ws2:
                sync_msg2 = cell_ws2.receive_bytes()
                assert sync_msg2[0] == YMessageType.SYNC

                # Both should receive updates
                update_msg = bytes([1]) + b"test"
                cell_ws1.send_bytes(update_msg)

                # TODO: This hangs
                # received = cell_ws2.receive_bytes()
                # assert received[0] == YMessageType.AWARENESS
                # assert received[1:] == b"test"

                # Verify client count
                from marimo._server.api.endpoints.ws import ycells

                key = CellIdAndFileKey(cell_id, temp_marimo_file)

                assert ycells[key].clients == 2

                # Close one client
                cell_ws2.close()
                await asyncio.sleep(0.1)
                assert ycells[key].clients == 1

    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_ycell_invalid_session(client: TestClient) -> None:
    """Test connecting to cell with invalid session is rejected"""
    cell_id = "Hbol"

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect(f"/ws/{cell_id}?session_id=invalid"):
            pass

    assert exc_info.value.code == WebSocketCodes.FORBIDDEN
    assert exc_info.value.reason == "MARIMO_NOT_ALLOWED"
