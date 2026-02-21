# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import pytest
from starlette.websockets import WebSocketDisconnect

from marimo._config.config import ExperimentalConfig
from marimo._config.manager import UserConfigManager
from marimo._messaging.msgspec_encoder import asdict
from marimo._messaging.notification import (
    KernelCapabilitiesNotification,
    KernelReadyNotification,
)
from marimo._server.codes import WebSocketCodes
from marimo._server.session_manager import SessionManager
from marimo._session.model import SessionMode
from marimo._utils.parse_dataclass import parse_raw
from tests._server.conftest import (
    get_kernel_tasks,
    get_session_manager,
    get_user_config_manager,
)
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
        "capabilities": asdict(KernelCapabilitiesNotification()),
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


def _create_ws_url(session_id: str) -> str:
    return f"/ws?session_id={session_id}&access_token=fake-token"


WS_URL = _create_ws_url("123")
OTHER_WS_URL = _create_ws_url("456")


def assert_kernel_ready_response(
    raw_data: dict[str, Any], response: Optional[dict[str, Any]] = None
) -> None:
    if response is None:
        response = create_response({})
    data = parse_raw(raw_data["data"], KernelReadyNotification)
    expected = parse_raw(response, KernelReadyNotification)
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
    data = parse_raw(raw_data["data"], KernelReadyNotification)
    assert data is not None


def test_ws(client: TestClient) -> None:
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)


def test_without_session(client: TestClient) -> None:
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/ws?access_token=fake-token"),
    ):
        raise AssertionError()
    assert exc_info.value.code == 1000
    assert exc_info.value.reason == "MARIMO_NO_SESSION_ID"


def test_disconnect_and_reconnect(client: TestClient) -> None:
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
    # Connect by the same session id
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {"op": "reconnected"}}
        data = websocket.receive_json()
        assert data["op"] == "alert"


def test_disconnect_then_reconnect_then_refresh(client: TestClient) -> None:
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        websocket.close()
    # Connect by the same session id
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {"op": "reconnected"}}
        data = websocket.receive_json()
        assert data["op"] == "alert"
    # New session with new ID (simulates refresh)
    with client.websocket_connect(OTHER_WS_URL) as websocket:
        data = websocket.receive_json()
        assert data == {"op": "reconnected", "data": {"op": "reconnected"}}
        data = websocket.receive_json()
        assert_kernel_ready_response(data, create_response({"resumed": True}))


def test_allows_multiple_connections_with_other_sessions(
    client: TestClient,
) -> None:
    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect(WS_URL) as websocket,
    ):
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        # Should allow second connection
        with client.websocket_connect(OTHER_WS_URL) as other_websocket:
            data = other_websocket.receive_json()
            assert_kernel_ready_response(
                data, create_response({"resumed": True})
            )


def test_fails_on_multiple_connections_with_other_sessions(
    client: TestClient,
) -> None:
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        with (  # noqa: PT012
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(OTHER_WS_URL) as other_websocket,
        ):
            other_websocket.receive_json()
            raise AssertionError()
        assert exc_info.value.code == 1003
        assert exc_info.value.reason == "MARIMO_ALREADY_CONNECTED"


def test_allows_multiple_connections_with_same_file(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    del temp_marimo_file
    ws_1 = WS_URL
    ws_2 = _create_ws_url("456")
    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect(ws_1) as websocket,
    ):
        data = websocket.receive_json()
        assert_parse_ready_response(data)
        # Should allow second connection
        with client.websocket_connect(ws_2) as other_websocket:
            data = other_websocket.receive_json()
            assert_parse_ready_response(data)


def test_fails_on_multiple_connections_with_same_file(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    ws_1 = f"{WS_URL}&file={temp_marimo_file}"
    ws_2 = f"{OTHER_WS_URL}&file={temp_marimo_file}"
    with client.websocket_connect(ws_1) as websocket:
        data = websocket.receive_json()
        assert_parse_ready_response(data)
        with (  # noqa: PT012
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(ws_2) as other_websocket,
        ):
            other_websocket.receive_json()
            raise AssertionError()
        assert exc_info.value.code == 1003
        assert exc_info.value.reason == "MARIMO_ALREADY_CONNECTED"


async def test_file_watcher_calls_reload(client: TestClient) -> None:
    session_manager: SessionManager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN
    # Recreate the file change coordinator with the new mode's strategy
    session_manager._file_change_coordinator = (
        session_manager._create_file_change_coordinator()
    )
    session_manager.watch = True
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        filename = session_manager.file_router.get_unique_file_key()
        assert filename
        with open(filename, "a") as f:  # noqa: ASYNC230
            f.write("\n# test")
            f.close()
        assert session_manager._watcher_manager._watchers
        watcher = next(
            iter(session_manager._watcher_manager._watchers.values())
        )
        await watcher.callback(Path(filename))
        # Drain messages until we get the reload message
        # (other messages like 'variables' may arrive first)
        expected = {"op": "reload", "data": {"op": "reload"}}
        for _ in range(10):
            data = websocket.receive_json()
            if data == expected:
                break
        else:
            raise AssertionError(f"Expected {expected}, but never received it")
        session_manager.watch = False


async def test_query_params(client: TestClient) -> None:
    with client.websocket_connect(
        f"{WS_URL}&foo=1&bar=2&bar=3&baz=4"
    ) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        session = get_session_manager(client).get_session("123")
        assert session
        assert session._kernel_manager.app_metadata.query_params == {
            "foo": "1",
            "bar": ["2", "3"],
            "baz": "4",
        }


async def test_connect_kiosk_without_session(client: TestClient) -> None:
    with (  # noqa: PT012
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect(
            "/ws?session_id=123&kiosk=true&access_token=fake-token"
        ) as websocket,
    ):
        websocket.receive_json()
        raise AssertionError()
    assert exc_info.value.code == WebSocketCodes.NORMAL_CLOSE
    assert exc_info.value.reason == "MARIMO_NO_SESSION"


async def test_connect_kiosk_with_session(client: TestClient) -> None:
    # Create the first session
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        # Connect by the same session id in kiosk mode
        with client.websocket_connect(
            f"{WS_URL}&kiosk=true"
        ) as other_websocket:
            data = other_websocket.receive_json()
            assert_kernel_ready_response(
                data, create_response({"kiosk": True, "resumed": True})
            )


async def test_cannot_connect_kiosk_with_run_session(
    client: TestClient,
) -> None:
    # Create the first session
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        # Connect by the same session id in kiosk mode
        with (  # noqa: PT012
            pytest.raises(WebSocketDisconnect) as exc_info,
            client.websocket_connect(
                f"{WS_URL}&kiosk=true"
            ) as other_websocket,
        ):
            data = other_websocket.receive_json()
            raise AssertionError()
        assert exc_info.value.code == WebSocketCodes.FORBIDDEN
        assert exc_info.value.reason == "MARIMO_KIOSK_NOT_ALLOWED"


async def test_connects_to_existing_session_with_same_file(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    ws_1 = f"{WS_URL}&file={temp_marimo_file}"
    ws_2 = f"{OTHER_WS_URL}&file={temp_marimo_file}"

    with (
        rtc_enabled(get_user_config_manager(client)),
        client.websocket_connect(ws_1) as websocket1,
    ):
        data = websocket1.receive_json()
        assert_parse_ready_response(data)

        # Instantiate the session
        client.post(
            "/api/kernel/instantiate",
            headers=headers("123"),
            json={"objectIds": [], "values": [], "auto_run": True},
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
            assert len(session_manager.sessions["123"].consumers) == 2

            data2 = websocket2.receive_json()
            assert_parse_ready_response(data2)
            assert data2["data"]["resumed"] is True

            messages2 = flush_messages(websocket2, at_least=4)
            # This can/may change if implementation changes, but this is a snapshot to
            # make sure it doesn't change when we don't expect it to
            assert len(messages2) == 4
            assert messages2[0]["op"] == "variables"


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
        experimental_config = ExperimentalConfig(rtc_v2=True)
        config.save_config({"experimental": experimental_config})
        yield
    finally:
        config.save_config(prev_config)


def test_ws_requires_authentication(client: TestClient) -> None:
    """Test that WebSocket connections require authentication."""
    # Try to connect without any authentication headers
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/ws"),
    ):
        raise AssertionError("Should not be able to connect without auth")

    assert exc_info.value.code == WebSocketCodes.UNAUTHORIZED
    assert exc_info.value.reason == "MARIMO_UNAUTHORIZED"


def test_ws_sync_requires_authentication(client: TestClient) -> None:
    """Test that WebSocket sync endpoint requires authentication."""
    # Try to connect without any authentication headers
    with (
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/ws_sync?file=test"),
    ):
        raise AssertionError("Should not be able to connect without auth")

    assert exc_info.value.code == WebSocketCodes.UNAUTHORIZED
    assert exc_info.value.reason == "MARIMO_UNAUTHORIZED"


def test_ws_with_valid_authentication(client: TestClient) -> None:
    """Test that WebSocket connections work with valid authentication."""
    # Connect with proper authentication headers
    with client.websocket_connect(WS_URL, headers=HEADERS) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

    # Clean up


# ==============================================================================
# Edge Cases - Session Resumption
# ==============================================================================


async def test_session_resumption(client: TestClient) -> None:
    """Test that session resumption restores state and replays operations."""
    # Create a session and instantiate it
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        # Instantiate to generate some operations
        client.post(
            "/api/kernel/instantiate",
            headers=headers("123"),
            json={"objectIds": [], "values": [], "auto_run": True},
        )

        # Flush initial messages
        flush_messages(websocket, at_least=1)

    await asyncio.sleep(0.2)

    # Resume with new session ID (simulates browser refresh)
    with client.websocket_connect(OTHER_WS_URL) as websocket:
        # Should receive reconnected + resumed state
        reconnect_msg = websocket.receive_json()
        assert reconnect_msg["op"] == "reconnected"

        kernel_ready_msg = websocket.receive_json()
        assert kernel_ready_msg["op"] == "kernel-ready"

        # Verify resumed flag is True
        data = parse_raw(kernel_ready_msg["data"], KernelReadyNotification)
        assert data.resumed is True

        # Should replay operations - collect some messages
        replayed = flush_messages(websocket, at_least=1)
        assert len(replayed) >= 1


# ==============================================================================
# Edge Cases - Disconnection/Reconnection
# ==============================================================================


async def test_reconnection_cancels_close_handle(client: TestClient) -> None:
    """Test that reconnection properly cancels pending close handle."""
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN

    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        # Close the websocket
        websocket.close()

        # Wait briefly for disconnect handling
        await asyncio.sleep(0.1)

        # Reconnect immediately (before TTL expires)
        with client.websocket_connect(WS_URL) as new_websocket:
            data = new_websocket.receive_json()
            # Should get reconnected message
            assert data["op"] == "reconnected"

            # Session should still exist (TTL was canceled)
            session = session_manager.get_session("123")
            assert session is not None


@pytest.mark.parametrize(
    ("mode", "manager_ttl"),
    [
        (
            SessionMode.RUN,
            120,
        ),  # RUN mode always uses TTL which has to be integer: default 120.
        (SessionMode.EDIT, 120),  # EDIT mode with --session-ttl
    ],
)
async def test_session_ttl_expiration(
    client: TestClient, mode: SessionMode, manager_ttl: int | None
) -> None:
    """Test that sessions expire after TTL in RUN mode or when TTL cleanup applies in EDIT mode."""
    session_manager = get_session_manager(client)
    session_manager.mode = mode
    session_manager.ttl_seconds = manager_ttl

    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        session = session_manager.get_session("123")
        assert session is not None

        # Override TTL to be very short for testing
        kernel_tasks = get_kernel_tasks(session_manager)
        session.ttl_seconds = 0.01

        websocket.close()

        # Wait for TTL to expire, which should close the session
        await asyncio.sleep(0.3)
        session = session_manager.get_session("123")
        assert session is None

        # We join on kernel threads to make sure that the main module
        # is restored correctly.
        for task in kernel_tasks:
            task.join()


async def test_edit_mode_without_session_ttl_no_delayed_cleanup(
    client: TestClient,
) -> None:
    """Test that EDIT mode without --session-ttl doesn't use TTL-based cleanup.

    This is the default behavior for `marimo edit` (without --session-ttl flag).
    Sessions persist for reconnection - no delayed TTL cleanup is scheduled.
    """
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.EDIT
    # Default: no --session-ttl flag passed
    assert session_manager.ttl_seconds is None

    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        session = session_manager.get_session("123")
        assert session is not None

    # Wait for disconnect handling
    await asyncio.sleep(0.1)

    # Session should still exist
    session = session_manager.get_session("123")
    assert session is not None


# ==============================================================================
# Edge Cases - Connection Validation
# ==============================================================================


def test_missing_file_key_closes_connection(client: TestClient) -> None:
    """Test that missing file key causes connection to close.

    This can happen when file_router.get_unique_file_key() returns None.
    """
    from unittest.mock import patch

    session_manager = get_session_manager(client)

    # Mock get_unique_file_key to return None
    with (
        patch.object(
            session_manager.file_router,
            "get_unique_file_key",
            return_value=None,
        ),
        pytest.raises(WebSocketDisconnect) as exc_info,
        client.websocket_connect("/ws?session_id=123&access_token=fake-token"),
    ):
        pass

    assert exc_info.value.code == WebSocketCodes.NORMAL_CLOSE
    assert exc_info.value.reason == "MARIMO_NO_FILE_KEY"


async def test_rtc_config_with_loro_unavailable(client: TestClient) -> None:
    """Regression test: connection works when RTC enabled but Loro unavailable."""
    from unittest.mock import patch

    # Enable RTC in config but mock Loro as unavailable
    with (
        (
            rtc_enabled(get_user_config_manager(client)),
            patch(
                "marimo._server.api.endpoints.ws.ws_kernel_ready.is_rtc_available",
                return_value=False,
            ),
        ),
        client.websocket_connect(WS_URL) as websocket,
    ):
        # Connection should succeed without errors
        data = websocket.receive_json()
        assert_kernel_ready_response(data)


# ============================================================================
# Advanced WebSocket State Machine Tests
# ============================================================================


async def test_rapid_reconnection_cancels_ttl_cleanup(
    client: TestClient,
) -> None:
    """Test that rapid reconnection cancels the TTL cleanup timer."""
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

    # Disconnect and immediately reconnect (before TTL expires)
    await asyncio.sleep(0.1)

    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert data["op"] == "reconnected"
        data = websocket.receive_json()
        assert data["op"] == "alert"


async def test_multiple_rapid_reconnections(client: TestClient) -> None:
    """Test multiple rapid connect/disconnect cycles don't break session."""
    for i in range(5):
        with client.websocket_connect(WS_URL) as websocket:
            data = websocket.receive_json()
            if i == 0:
                assert_kernel_ready_response(data)
            else:
                assert data["op"] == "reconnected"


async def test_websocket_message_queue_delivery(client: TestClient) -> None:
    """Test that kernel messages are queued and delivered."""
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)

        client.post(
            "/api/kernel/instantiate",
            headers=headers("123"),
            json={"objectIds": [], "values": [], "autoRun": True},
        )

        messages = flush_messages(websocket, at_least=1)
        assert len(messages) >= 1
