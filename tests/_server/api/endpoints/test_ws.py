# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import pytest
from starlette.websockets import WebSocketDisconnect

from marimo._config.config import ExperimentalConfig
from marimo._config.manager import UserConfigManager
from marimo._messaging.msgspec_encoder import asdict
from marimo._messaging.ops import KernelCapabilities, KernelReady
from marimo._server.codes import WebSocketCodes
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


def _create_ws_url(session_id: str) -> str:
    return f"/ws?session_id={session_id}&access_token=fake-token"


WS_URL = _create_ws_url("123")
OTHER_WS_URL = _create_ws_url("456")


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
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
    # shut down after websocket context manager exists, otherwise
    # the test fails on windows (event loop closed twice)
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_without_session(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws?access_token=fake-token"):
            raise AssertionError()
    assert exc_info.value.code == 1000
    assert exc_info.value.reason == "MARIMO_NO_SESSION_ID"
    client.post("/api/kernel/shutdown", headers=HEADERS)


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

    client.post("/api/kernel/shutdown", headers=HEADERS)


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

    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_allows_multiple_connections_with_other_sessions(
    client: TestClient,
) -> None:
    with rtc_enabled(get_user_config_manager(client)):
        with client.websocket_connect(WS_URL) as websocket:
            data = websocket.receive_json()
            assert_kernel_ready_response(data)
            # Should allow second connection
            with client.websocket_connect(OTHER_WS_URL) as other_websocket:
                data = other_websocket.receive_json()
                assert_kernel_ready_response(
                    data, create_response({"resumed": True})
                )
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_fails_on_multiple_connections_with_other_sessions(
    client: TestClient,
) -> None:
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        with pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: PT012
            with client.websocket_connect(OTHER_WS_URL) as other_websocket:
                other_websocket.receive_json()
                raise AssertionError()
        assert exc_info.value.code == 1003
        assert exc_info.value.reason == "MARIMO_ALREADY_CONNECTED"
    client.post("/api/kernel/shutdown", headers=HEADERS)


def test_allows_multiple_connections_with_same_file(
    client: TestClient,
    temp_marimo_file: str,
) -> None:
    del temp_marimo_file
    with rtc_enabled(get_user_config_manager(client)):
        ws_1 = WS_URL
        ws_2 = _create_ws_url("456")
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
    ws_1 = f"{WS_URL}&file={temp_marimo_file}"
    ws_2 = f"{OTHER_WS_URL}&file={temp_marimo_file}"
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


@pytest.mark.flaky(reruns=3)
async def test_file_watcher_calls_reload(client: TestClient) -> None:
    session_manager: SessionManager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN
    session_manager.watch = True
    with client.websocket_connect(WS_URL) as websocket:
        data = websocket.receive_json()
        assert_kernel_ready_response(data)
        filename = session_manager.file_router.get_unique_file_key()
        assert filename
        with open(filename, "a") as f:  # noqa: ASYNC230
            f.write("\n# test")
            f.close()
        assert session_manager.watcher_manager._watchers
        watcher = list(session_manager.watcher_manager._watchers.values())[0]
        await watcher.callback(Path(filename))
        data = websocket.receive_json()
        assert data == {"op": "reload", "data": {"op": "reload"}}
        session_manager.mode = SessionMode.EDIT
        session_manager.watch = False
    client.post("/api/kernel/shutdown", headers=HEADERS)


async def test_query_params(client: TestClient) -> None:
    with client.websocket_connect(
        f"{WS_URL}&foo=1&bar=2&bar=3&baz=4"
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
            "/ws?session_id=123&kiosk=true&access_token=fake-token"
        ) as websocket:
            websocket.receive_json()
            raise AssertionError()
    assert exc_info.value.code == WebSocketCodes.NORMAL_CLOSE
    assert exc_info.value.reason == "MARIMO_NO_SESSION"
    client.post("/api/kernel/shutdown", headers=HEADERS)


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
    client.post("/api/kernel/shutdown", headers=HEADERS)


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
        with pytest.raises(WebSocketDisconnect) as exc_info:  # noqa: PT012
            with client.websocket_connect(
                f"{WS_URL}&kiosk=true"
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
    ws_1 = f"{WS_URL}&file={temp_marimo_file}"
    ws_2 = f"{OTHER_WS_URL}&file={temp_marimo_file}"

    with rtc_enabled(get_user_config_manager(client)):
        with client.websocket_connect(ws_1) as websocket1:
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
        experimental_config = ExperimentalConfig(rtc_v2=True)
        config.save_config({"experimental": experimental_config})
        yield
    finally:
        config.save_config(prev_config)


def test_ws_requires_authentication(client: TestClient) -> None:
    """Test that WebSocket connections require authentication."""
    # Try to connect without any authentication headers
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws"):
            raise AssertionError("Should not be able to connect without auth")

    assert exc_info.value.code == WebSocketCodes.UNAUTHORIZED
    assert exc_info.value.reason == "MARIMO_UNAUTHORIZED"

    # Ensure shutdown
    try:
        client.post("/api/kernel/shutdown", headers=HEADERS)
    except Exception:
        pass


def test_ws_sync_requires_authentication(client: TestClient) -> None:
    """Test that WebSocket sync endpoint requires authentication."""
    # Try to connect without any authentication headers
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/ws_sync?file=test"):
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
    client.post("/api/kernel/shutdown", headers=HEADERS)
