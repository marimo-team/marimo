# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
import threading
from functools import partial
from typing import TYPE_CHECKING, Any
from unittest.mock import MagicMock, patch

import pytest

from marimo._messaging.notification import AlertNotification
from marimo._messaging.serde import serialize_kernel_message
from marimo._server.api.endpoints.ws.sse_handler import SSESessionHandler
from marimo._server.api.endpoints.ws.ws_connection_validator import (
    ConnectionParams,
)
from marimo._server.api.endpoints.ws.ws_session_connector import (
    ConnectionType,
)
from marimo._server.sse import format_close_event, format_sse_event
from marimo._session.managers.ipc import KernelStartupError
from marimo._session.model import ConnectionState, SessionMode
from marimo._types.ids import SessionId
from tests._server.api.endpoints.ws_helpers import (
    assert_kernel_ready_response,
    create_response,
)
from tests._server.mocks import get_session_manager

if TYPE_CHECKING:
    from starlette.applications import Starlette
    from starlette.testclient import TestClient
    from typing_extensions import Self

SSE_QUERY = "session_id=123&access_token=fake-token"
OTHER_SSE_QUERY = "session_id=456&access_token=fake-token"


class SSETestConnection:
    """Drives a `GET /sse` request against the raw ASGI app.

    The TestClient buffers entire response bodies, which never works for an
    unbounded SSE stream; this speaks ASGI directly so tests can read
    events incrementally and disconnect at any time.
    """

    def __init__(
        self,
        app: Starlette,
        query: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._app = app
        self._scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/sse",
            "raw_path": b"/sse",
            "query_string": query.encode(),
            "root_path": "",
            # ASGI header names must be lowercase bytes
            "headers": [
                (b"host", b"testserver"),
                *(
                    (k.lower().encode(), v.encode())
                    for k, v in (headers or {}).items()
                ),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
        self._receive_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._events: asyncio.Queue[dict[str, str]] = asyncio.Queue()
        self._buffer = ""
        self._task: asyncio.Task[None] | None = None
        self.status: int | None = None
        self.headers: dict[str, str] = {}

    async def __aenter__(self) -> Self:
        self._task = asyncio.create_task(
            self._app(self._scope, self._receive, self._send)
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.disconnect()
        assert self._task is not None
        await asyncio.wait_for(self._task, timeout=10)

    def disconnect(self) -> None:
        self._receive_queue.put_nowait({"type": "http.disconnect"})

    async def next_event(self, timeout: float = 10) -> dict[str, str]:
        """The next SSE record: {"event": ..., "data": ...} or a comment."""
        return await asyncio.wait_for(self._events.get(), timeout)

    def has_pending_events(self) -> bool:
        return not self._events.empty()

    def stream_ended(self) -> bool:
        assert self._task is not None
        return self._task.done()

    async def _receive(self) -> dict[str, Any]:
        return await self._receive_queue.get()

    async def _send(self, message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            self.status = message["status"]
            self.headers = {
                k.decode(): v.decode() for k, v in message.get("headers", [])
            }
        elif message["type"] == "http.response.body":
            self._buffer += message.get("body", b"").decode()
            while "\n\n" in self._buffer:
                record, self._buffer = self._buffer.split("\n\n", 1)
                self._events.put_nowait(_parse_record(record))


def _parse_record(record: str) -> dict[str, str]:
    event = "message"
    data_lines: list[str] = []
    comments: list[str] = []
    for line in record.split("\n"):
        if line.startswith(":"):
            comments.append(line[1:].strip())
        elif line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            data_lines.append(line[len("data:") :].removeprefix(" "))
    if comments and not data_lines:
        return {"event": "comment", "data": "\n".join(comments)}
    return {"event": event, "data": "\n".join(data_lines)}


def _connect(
    client: TestClient,
    query: str = SSE_QUERY,
    headers: dict[str, str] | None = None,
) -> SSETestConnection:
    return SSETestConnection(client.app, query, headers)


async def _expect_close(
    connection: SSETestConnection, code: int, reason: str
) -> None:
    event = await connection.next_event()
    assert event["event"] == "close"
    assert json.loads(event["data"]) == {"code": code, "reason": reason}


async def test_sse_kernel_ready(client: TestClient) -> None:
    async with _connect(client) as connection:
        event = await connection.next_event()
        assert connection.status == 200
        assert connection.headers["content-type"].startswith(
            "text/event-stream"
        )
        assert event["event"] == "message"
        message = json.loads(event["data"])
        assert message["op"] == "kernel-ready"
        assert_kernel_ready_response(message)


async def test_sse_requires_session_id(client: TestClient) -> None:
    async with _connect(client, "access_token=fake-token") as connection:
        await _expect_close(connection, 1000, "MARIMO_NO_SESSION_ID")


async def test_sse_requires_authentication(client: TestClient) -> None:
    async with _connect(client, "session_id=123") as connection:
        await _expect_close(connection, 3000, "MARIMO_UNAUTHORIZED")


async def test_sse_authenticates_with_bearer_header(
    client: TestClient,
) -> None:
    # The frontend SSE transport sends auth in headers, not the URL
    async with _connect(
        client,
        "session_id=123",
        headers={"Authorization": "Bearer fake-token"},
    ) as connection:
        event = await connection.next_event()
        assert json.loads(event["data"])["op"] == "kernel-ready"


async def test_sse_rejects_invalid_query_token(client: TestClient) -> None:
    async with _connect(
        client, "session_id=123&access_token=wrong-token"
    ) as connection:
        await _expect_close(connection, 3000, "MARIMO_UNAUTHORIZED")


async def test_sse_rejects_invalid_bearer_token(client: TestClient) -> None:
    async with _connect(
        client,
        "session_id=123",
        headers={"Authorization": "Bearer wrong-token"},
    ) as connection:
        await _expect_close(connection, 3000, "MARIMO_UNAUTHORIZED")


@pytest.mark.parametrize(
    "authorization",
    [
        "Bearer",  # no credentials
        "Unknown fake-token",  # unsupported scheme
        "Basic !!!not-base64!!!",
        "Basic dXNlcm5hbWUtb25seQ==",  # no password ("username-only")
    ],
)
async def test_sse_rejects_malformed_authorization_header(
    client: TestClient, authorization: str
) -> None:
    async with _connect(
        client,
        "session_id=123",
        headers={"Authorization": authorization},
    ) as connection:
        await _expect_close(connection, 3000, "MARIMO_UNAUTHORIZED")


async def test_sse_unauthorized_has_no_side_effects(
    client: TestClient,
) -> None:
    """A rejected request must not create a session or leak anything."""
    session_manager = get_session_manager(client)
    async with _connect(client, "session_id=123") as connection:
        await _expect_close(connection, 3000, "MARIMO_UNAUTHORIZED")

    assert session_manager.sessions == {}
    # The stream ends after the close event; nothing else is sent
    assert connection.stream_ended()
    assert not connection.has_pending_events()
    # Failed auth must not issue an authenticated session cookie
    assert "set-cookie" not in connection.headers


async def test_sse_allows_unauthenticated_when_auth_disabled(
    client: TestClient,
) -> None:
    # Trusted environments (e.g. --no-token) disable marimo's own auth
    client.app.state.enable_auth = False
    async with _connect(client, "session_id=123") as connection:
        event = await connection.next_event()
        assert json.loads(event["data"])["op"] == "kernel-ready"


async def test_sse_kiosk_not_allowed_in_run_mode(client: TestClient) -> None:
    get_session_manager(client).mode = SessionMode.RUN
    async with _connect(client, f"{SSE_QUERY}&kiosk=true") as connection:
        await _expect_close(connection, 1008, "MARIMO_KIOSK_NOT_ALLOWED")
    assert get_session_manager(client).sessions == {}


async def test_sse_hides_code_when_include_code_false(
    client: TestClient,
) -> None:
    session_manager = get_session_manager(client)
    session_manager.mode = SessionMode.RUN
    session_manager.include_code = False
    async with _connect(client) as connection:
        event = await connection.next_event()
        message = json.loads(event["data"])
        assert message["op"] == "kernel-ready"
        assert message["data"]["codes"] == [""]  # hidden
        assert message["data"]["last_executed_code"] == {}  # hidden
        assert message["data"]["cell_ids"] == ["Hbol"]  # preserved


async def test_sse_kernel_startup_error(client: TestClient) -> None:
    with patch.object(
        SSESessionHandler,
        "_connect_session",
        side_effect=KernelStartupError("boom"),
    ):
        async with _connect(client) as connection:
            event = await connection.next_event()
            message = json.loads(event["data"])
            assert message["op"] == "kernel-startup-error"
            assert message["data"]["error"] == "boom"
            await _expect_close(
                connection, 1011, "MARIMO_KERNEL_STARTUP_ERROR"
            )


async def test_sse_kiosk_without_session(client: TestClient) -> None:
    async with _connect(client, f"{SSE_QUERY}&kiosk=true") as connection:
        await _expect_close(connection, 1000, "MARIMO_NO_SESSION")


async def test_sse_disconnect_and_reconnect(client: TestClient) -> None:
    async with _connect(client) as connection:
        event = await connection.next_event()
        assert json.loads(event["data"])["op"] == "kernel-ready"
    # Reconnect with the same session id
    async with _connect(client) as connection:
        event = await connection.next_event()
        assert json.loads(event["data"])["op"] == "reconnected"
        event = await connection.next_event()
        assert json.loads(event["data"])["op"] == "alert"


async def test_sse_second_connection_joins_as_viewer(
    client: TestClient,
) -> None:
    async with _connect(client) as connection:
        event = await connection.next_event()
        assert json.loads(event["data"])["op"] == "kernel-ready"
        async with _connect(client, OTHER_SSE_QUERY) as viewer:
            event = await viewer.next_event()
            message = json.loads(event["data"])
            assert message["op"] == "kernel-ready"
            assert_kernel_ready_response(
                message, create_response({"kiosk": True, "resumed": True})
            )


async def test_sse_heartbeat(client: TestClient) -> None:
    with_heartbeat = partial(SSESessionHandler, heartbeat_seconds=0.01)
    with patch(
        "marimo._server.api.endpoints.ws_endpoint.SSESessionHandler",
        with_heartbeat,
    ):
        async with _connect(client) as connection:
            event = await connection.next_event()
            assert json.loads(event["data"])["op"] == "kernel-ready"
            # Drain until the first heartbeat comment arrives
            for _ in range(20):
                event = await connection.next_event()
                if event["event"] == "comment":
                    break
            assert event == {"event": "comment", "data": "keep-alive"}


# Unit tests for the stream generator


def _make_handler(
    request: MagicMock, *, mode: SessionMode = SessionMode.RUN
) -> SSESessionHandler:
    params = ConnectionParams(
        session_id=SessionId("s1"),
        file_key="test.py",
        kiosk=False,
        auto_instantiate=False,
        rtc_enabled=False,
    )
    handler = SSESessionHandler(
        request=request,
        manager=MagicMock(),
        params=params,
        mode=mode,
        doc_manager=MagicMock(),
        heartbeat_seconds=60,
    )
    handler.status = ConnectionState.OPEN
    # Bypass SessionConnector; unit tests drive the handler directly
    session = MagicMock()
    session.room.main_consumer = handler
    handler._connect_session = MagicMock(  # type: ignore[method-assign]
        return_value=(session, ConnectionType.NEW)
    )
    return handler


def _never_receive() -> Any:
    async def receive() -> dict[str, Any]:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    return receive


async def test_stream_sends_messages_and_close_event() -> None:
    request = MagicMock()
    request._receive = _never_receive()
    handler = _make_handler(request)

    stream = handler.stream()
    handler.notify(
        serialize_kernel_message(
            AlertNotification(title="hello", description="world")
        )
    )
    first = await asyncio.wait_for(stream.__anext__(), timeout=10)
    assert first.startswith("data: ")
    assert json.loads(first[len("data: ") :].strip())["op"] == "alert"

    # Detaching from the session requests a SHUTDOWN close
    handler.on_detach()
    second = await asyncio.wait_for(stream.__anext__(), timeout=10)
    assert second == format_close_event(1000, "MARIMO_SHUTDOWN")
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(stream.__anext__(), timeout=10)
    assert not handler._is_transport_connected()


async def test_stream_does_not_connect_until_iterated() -> None:
    """A response body that is never consumed must not attach a consumer."""
    request = MagicMock()
    request._receive = _never_receive()
    handler = _make_handler(request)

    stream = handler.stream()
    await asyncio.sleep(0)
    handler._connect_session.assert_not_called()

    await stream.aclose()
    handler._connect_session.assert_not_called()


async def test_stream_flushes_pending_messages_before_close() -> None:
    """Messages enqueued before a server close are sent, then the close."""
    request = MagicMock()
    request._receive = _never_receive()
    handler = _make_handler(request)

    handler.notify(
        serialize_kernel_message(
            AlertNotification(title="one", description="")
        )
    )
    handler.notify(
        serialize_kernel_message(
            AlertNotification(title="two", description="")
        )
    )
    handler.on_detach()

    events = [event async for event in handler.stream()]
    assert len(events) == 3
    assert json.loads(events[0][len("data: ") :])["data"]["title"] == "one"
    assert json.loads(events[1][len("data: ") :])["data"]["title"] == "two"
    assert events[2] == format_close_event(1000, "MARIMO_SHUTDOWN")


async def test_stream_ends_on_client_disconnect() -> None:
    request = MagicMock()

    async def receive() -> dict[str, Any]:
        return {"type": "http.disconnect"}

    request._receive = receive
    handler = _make_handler(request, mode=SessionMode.EDIT)
    handler.manager.get_session.return_value = None
    handler.manager.ttl_seconds = None

    events = [event async for event in handler.stream()]
    assert events == []
    assert handler.connection_state() == ConnectionState.CLOSED


async def test_check_status_update_runs_off_the_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The synchronous update check must not block kernel messages."""
    from marimo._config.settings import GLOBAL_SETTINGS
    from marimo._server.api.endpoints.ws import session_handler

    monkeypatch.setattr(GLOBAL_SETTINGS, "CHECK_STATUS_UPDATE", True)
    monkeypatch.setattr(session_handler, "has_toasted", False)

    started = threading.Event()
    release = threading.Event()

    def slow_check(on_update: Any) -> None:
        started.set()
        assert release.wait(timeout=10)
        on_update("0.0.1", MagicMock(latest_version="9.9.9", notices=[]))

    monkeypatch.setattr(session_handler, "check_for_updates", slow_check)

    handler = _make_handler(MagicMock(), mode=SessionMode.EDIT)
    # Returns immediately, while the check is still running on a thread
    handler._check_status_update()
    assert await asyncio.wait_for(asyncio.to_thread(started.wait, 10), 20)
    assert handler.message_queue.empty()

    # Once the check completes, the alert is delivered onto the queue
    release.set()
    message = await asyncio.wait_for(handler.message_queue.get(), timeout=10)
    assert b"Update available" in bytes(message)


async def test_stream_heartbeat_without_messages() -> None:
    request = MagicMock()
    request._receive = _never_receive()
    handler = _make_handler(request)
    handler.heartbeat_seconds = 0.01

    stream = handler.stream()
    first = await asyncio.wait_for(stream.__anext__(), timeout=10)
    assert first == ": keep-alive\n\n"
    handler._request_close(1000, "MARIMO_SHUTDOWN")
    async for _ in stream:
        pass


# Unit tests for SSE framing


def test_format_sse_event() -> None:
    assert format_sse_event('{"op": "alert"}') == 'data: {"op": "alert"}\n\n'
    assert (
        format_sse_event('{"code": 1}', event="close")
        == 'event: close\ndata: {"code": 1}\n\n'
    )
    # Multi-line payloads become one data line each
    assert format_sse_event("a\nb") == "data: a\ndata: b\n\n"


def test_format_close_event() -> None:
    assert format_close_event(1000, "MARIMO_SHUTDOWN") == (
        'event: close\ndata: {"code": 1000, "reason": "MARIMO_SHUTDOWN"}\n\n'
    )
