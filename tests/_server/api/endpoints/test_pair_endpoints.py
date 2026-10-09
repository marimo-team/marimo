# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING, cast
from unittest.mock import Mock, patch
from uuid import UUID

import httpx
import pytest
from starlette.applications import Starlette

from marimo._ast.app import App, InternalApp
from marimo._config.manager import get_default_config_manager
from marimo._messaging.attachments import Attachment
from marimo._messaging.notification import AttachmentsNotification
from marimo._messaging.serde import deserialize_kernel_message
from marimo._server.api.deps import (
    ATTACHMENT_ID_HEADER,
    ATTACHMENT_KIND_HEADER,
    ATTACHMENT_NAME_HEADER,
)
from marimo._server.api.endpoints import pair
from marimo._server.sse import HEARTBEAT_EVENT
from marimo._session.consumer import SessionConsumer
from marimo._session.extensions.extensions import SessionViewExtension
from marimo._session.handoff_stream import MAX_PENDING_EVENTS, sse_event
from marimo._session.managers import KernelManagerImpl
from marimo._session.model import ConnectionState
from marimo._session.notebook import AppFileManager
from marimo._session.session import SessionImpl
from marimo._session.state.session_view import SessionView
from marimo._types.ids import ConsumerId, SessionId
from marimo._utils.env import PAIR_PREVIEW_ENV
from tests._server.mocks import get_session_manager, token_header

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterator

    from starlette.testclient import TestClient
    from starlette.types import Message, Scope
    from typing_extensions import Self


@pytest.fixture(autouse=True)
def preview(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(PAIR_PREVIEW_ENV, "1")


@pytest.fixture
def session(client: TestClient) -> Iterator[SessionImpl]:
    consumer = Mock(spec=SessionConsumer)
    consumer.consumer_id = ConsumerId("browser")
    consumer.connection_state.return_value = ConnectionState.OPEN
    kernel = Mock(spec=KernelManagerImpl)
    kernel.kernel_task = None
    session = SessionImpl(
        session_view=SessionView(),
        initialization_id="notebook.py",
        session_consumer=consumer,
        kernel_manager=kernel,
        app_file_manager=AppFileManager.from_app(InternalApp(App())),
        config_manager=get_default_config_manager(current_path=None),
        ttl_seconds=None,
        extensions=[SessionViewExtension()],
    )
    get_session_manager(client)._repository.add_sync(
        SessionId("browser"), session
    )
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
async def http(client: TestClient) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=client.app),
        base_url="http://testserver",
        headers=token_header("fake-token"),
    ) as http:
        yield http


def _path(session: SessionImpl, operation: str) -> str:
    return f"/api/pair/notebooks/{session.stable_id}/{operation}"


class PairStream:
    """Read response chunks directly because TestClient buffers SSE bodies."""

    def __init__(
        self,
        client: TestClient,
        session: SessionImpl,
        attachment_id: str | None = "a1",
        *,
        kind: str = "agent",
        name: str = "Claude Code",
        spec_version: str = "2.3",
    ) -> None:
        self.app = cast(Starlette, client.app)
        headers = token_header("fake-token")
        if attachment_id is not None:
            headers[ATTACHMENT_ID_HEADER] = attachment_id
        headers[ATTACHMENT_KIND_HEADER] = kind
        headers[ATTACHMENT_NAME_HEADER] = name
        path = _path(session, "events")
        self.scope: Scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": spec_version},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "root_path": "",
            "headers": [
                (key.lower().encode(), value.encode())
                for key, value in headers.items()
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
        }
        self.incoming: asyncio.Queue[Message] = asyncio.Queue()
        self.chunks: asyncio.Queue[bytes | None] = asyncio.Queue()
        self.started = asyncio.Event()
        self.task: asyncio.Task[None] | None = None
        self.status: int | None = None
        self.headers: dict[str, str] = {}

    async def __aenter__(self) -> Self:
        self.task = asyncio.create_task(
            self.app(self.scope, self.incoming.get, self.send)
        )
        await asyncio.wait_for(self.started.wait(), timeout=2)
        return self

    async def __aexit__(self, *_args: object) -> None:
        self.incoming.put_nowait({"type": "http.disconnect"})
        assert self.task is not None
        await asyncio.wait_for(self.task, timeout=2)

    async def send(self, message: Message) -> None:
        if message["type"] == "http.response.start":
            self.status = message["status"]
            self.headers = {
                key.decode(): value.decode()
                for key, value in message["headers"]
            }
            self.started.set()
        elif message["type"] == "http.response.body":
            if message.get("body"):
                self.chunks.put_nowait(message["body"])
            if not message.get("more_body", False):
                self.chunks.put_nowait(None)

    async def next_chunk(self) -> bytes | None:
        return await asyncio.wait_for(self.chunks.get(), timeout=2)

    async def ready(self) -> None:
        chunk = await self.next_chunk()
        assert chunk is not None
        assert chunk.startswith(b"event: attached\n")


class StalledPairStream(PairStream):
    def __init__(
        self, client: TestClient, session: SessionImpl, *, spec_version: str
    ) -> None:
        super().__init__(client, session, spec_version=spec_version)
        self.blocked = asyncio.Event()
        self.resume = asyncio.Event()

    async def send(self, message: Message) -> None:
        if message["type"] == "http.response.body" and message.get(
            "body", b""
        ).startswith(b"event: handoff\n"):
            self.blocked.set()
            await self.resume.wait()
        await super().send(message)

    async def __aexit__(self, *_args: object) -> None:
        self.resume.set()
        if self.task is not None and self.task.cancelled():
            return
        await super().__aexit__(*_args)


@pytest.mark.parametrize("spec_version", ["2.3", "2.4"])
async def test_stream_attaches_first_and_notifies_browser(
    client: TestClient,
    session: SessionImpl,
    spec_version: str,
) -> None:
    with patch("marimo._server.api.deps.time.time", return_value=1.0):
        async with PairStream(
            client, session, spec_version=spec_version
        ) as stream:
            attachment = Attachment(
                id="a1", kind="agent", name="Claude Code", since=1.0
            )
            assert await stream.next_chunk() == sse_event(
                "attached", attachment
            )
            assert stream.chunks.empty()
            assert stream.status == 200
            assert stream.headers["content-type"].startswith(
                "text/event-stream"
            )
            assert stream.headers["cache-control"] == "no-cache, no-transform"
            assert session.handoffs.attachments() == [attachment]
            consumer = session.room.get_consumer(ConsumerId("browser"))
            assert isinstance(consumer, Mock)
            assert deserialize_kernel_message(
                consumer.notify.call_args.args[0]
            ) == AttachmentsNotification(attachments=[attachment])

    assert session.handoffs.attachments() == []
    consumer = session.room.get_consumer(ConsumerId("browser"))
    assert isinstance(consumer, Mock)
    assert deserialize_kernel_message(consumer.notify.call_args.args[0]) == (
        AttachmentsNotification(attachments=[])
    )


async def test_missing_id_mints_a_client_even_with_agent_metadata(
    client: TestClient,
    session: SessionImpl,
) -> None:
    with patch("marimo._server.api.deps.time.time", return_value=42.0):
        async with PairStream(client, session, attachment_id=None) as stream:
            chunk = await stream.next_chunk()
            assert chunk is not None
            attachment = json.loads(chunk.decode().split("data: ", 1)[1])
            attachment_uuid = UUID(attachment["id"].removeprefix("att_"))
            assert attachment_uuid.version == 4
            assert attachment == {
                "id": f"att_{attachment_uuid}",
                "kind": "client",
                "name": None,
                "since": 42.0,
            }
            assert session.handoffs.attachments() == [Attachment(**attachment)]


@pytest.mark.parametrize(
    "payload",
    [
        "Hello\nagent",
        {"custom": {"answer": 42}},
        [1, "two", None],
        7,
        2.5,
        True,
        None,
        {
            "notebook": "nb.py",
            "cell_id": "c1",
            "error": {"message": "failure"},
        },
        {
            "type": "cell-output",
            "cell_id": "c1",
            "code": "raise ValueError('failed')",
            "output": {
                "type": "error",
                "message": "failed",
                "traceback": "Traceback\nValueError: failed",
            },
        },
        {
            "lens": {
                "selection": [1, 2],
                "chart": {"mark": "point", "fields": ["x", "y"]},
            },
        },
    ],
)
async def test_any_json_reaches_every_agent_and_no_client(
    client: TestClient,
    session: SessionImpl,
    http: httpx.AsyncClient,
    payload: object,
) -> None:
    async with (
        PairStream(client, session, "a1") as first,
        PairStream(client, session, "a2", name="Codex") as second,
        PairStream(client, session, "c1", kind="client") as observer,
    ):
        for stream in (first, second, observer):
            await stream.ready()
        response = await http.post(
            _path(session, "handoffs"),
            content=json.dumps(payload),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 202
        assert response.content == b""
        assert await first.next_chunk() == sse_event("handoff", payload)
        assert await second.next_chunk() == sse_event("handoff", payload)
        assert observer.chunks.empty()


@pytest.mark.parametrize("with_client", [False, True])
async def test_handoff_requires_an_agent(
    session: SessionImpl,
    http: httpx.AsyncClient,
    *,
    with_client: bool,
) -> None:
    if with_client:
        session.handoffs.attach(
            Attachment(id="c1", kind="client", name=None, since=0)
        )
    response = await http.post(
        _path(session, "handoffs"), json={"custom": True}
    )
    assert response.status_code == 409
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "No agent attached"}


@pytest.mark.parametrize("body", [b"", b"{", b"NaN", b"\xff"])
async def test_invalid_json_returns_400(
    session: SessionImpl,
    http: httpx.AsyncClient,
    body: bytes,
) -> None:
    response = await http.post(_path(session, "handoffs"), content=body)
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid JSON handoff payload."}


@pytest.mark.parametrize("enabled", [None, "0", "false"])
@pytest.mark.parametrize("operation", ["events", "handoffs"])
async def test_preview_off_returns_404(
    session: SessionImpl,
    http: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    enabled: str | None,
    operation: str,
) -> None:
    if enabled is None:
        monkeypatch.delenv(PAIR_PREVIEW_ENV)
    else:
        monkeypatch.setenv(PAIR_PREVIEW_ENV, enabled)
    response = await http.request(
        "GET" if operation == "events" else "POST", _path(session, operation)
    )
    assert response.status_code == 404
    assert session.handoffs.attachments() == []


@pytest.mark.parametrize("identity", ["unknown", "browser"])
@pytest.mark.parametrize("operation", ["events", "handoffs"])
async def test_routes_require_a_stable_session_id(
    session: SessionImpl,
    http: httpx.AsyncClient,
    identity: str,
    operation: str,
) -> None:
    response = await http.request(
        "GET" if operation == "events" else "POST",
        f"/api/pair/notebooks/{identity}/{operation}",
    )
    assert response.status_code == 404
    assert session.handoffs.attachments() == []


@pytest.mark.parametrize("operation", ["events", "handoffs"])
async def test_routes_require_authentication(
    session: SessionImpl,
    http: httpx.AsyncClient,
    operation: str,
) -> None:
    http.headers.clear()
    response = await http.request(
        "GET" if operation == "events" else "POST", _path(session, operation)
    )
    assert response.status_code == 401
    assert session.handoffs.attachments() == []


@pytest.mark.parametrize(
    "headers",
    [
        {ATTACHMENT_ID_HEADER: ""},
        {ATTACHMENT_ID_HEADER: "a1", ATTACHMENT_KIND_HEADER: "invalid"},
    ],
)
async def test_stream_rejects_invalid_attachment_headers(
    session: SessionImpl,
    http: httpx.AsyncClient,
    headers: dict[str, str],
) -> None:
    response = await http.get(_path(session, "events"), headers=headers)
    assert response.status_code == 400
    assert session.handoffs.attachments() == []


async def test_stream_pings_when_idle(
    client: TestClient,
    session: SessionImpl,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert pair.PING_INTERVAL == 15
    monkeypatch.setattr(pair, "PING_INTERVAL", 0.01)
    async with PairStream(client, session) as stream:
        await stream.ready()
        assert await stream.next_chunk() == HEARTBEAT_EVENT.encode("utf-8")


async def test_session_close_ends_streams(
    client: TestClient,
    session: SessionImpl,
) -> None:
    async with PairStream(client, session) as stream:
        await stream.ready()
        session.close()
        assert await stream.next_chunk() is None
    assert session.handoffs.attachments() == []


async def test_replacing_a_stream_keeps_its_attachment_alive(
    client: TestClient,
    session: SessionImpl,
) -> None:
    with patch("marimo._server.api.deps.time.time", return_value=1.0):
        async with PairStream(client, session) as old:
            await old.ready()
            assert session.handoffs.attachments()[0].since == 1.0
            with patch("marimo._server.api.deps.time.time", return_value=99.0):
                async with PairStream(
                    client, session, name="Reconnected"
                ) as replacement:
                    await replacement.ready()
                    assert await old.next_chunk() is None
                    assert session.handoffs.attachments() == [
                        Attachment(
                            id="a1",
                            kind="agent",
                            name="Reconnected",
                            since=1.0,
                        )
                    ]


@pytest.mark.parametrize("spec_version", ["2.3", "2.4"])
async def test_overflow_ends_a_stalled_stream_and_keeps_healthy_delivery(
    client: TestClient,
    session: SessionImpl,
    http: httpx.AsyncClient,
    spec_version: str,
) -> None:
    async with (
        StalledPairStream(client, session, spec_version=spec_version) as slow,
        PairStream(client, session, "a2", name="Codex") as healthy,
    ):
        await slow.ready()
        await healthy.ready()
        session.handoffs.publish("in flight")
        await asyncio.wait_for(slow.blocked.wait(), timeout=2)
        assert await healthy.next_chunk() == sse_event("handoff", "in flight")
        for index in range(MAX_PENDING_EVENTS):
            session.handoffs.publish(index)
            assert await healthy.next_chunk() == sse_event("handoff", index)

        response = await http.post(_path(session, "handoffs"), json="overflow")

        assert response.status_code == 202
        assert [a.id for a in session.handoffs.attachments()] == ["a2"]
        assert await healthy.next_chunk() == sse_event("handoff", "overflow")
        consumer = session.room.get_consumer(ConsumerId("browser"))
        assert isinstance(consumer, Mock)
        assert deserialize_kernel_message(
            consumer.notify.call_args.args[0]
        ) == (
            AttachmentsNotification(attachments=session.handoffs.attachments())
        )
        slow.resume.set()
        assert await slow.next_chunk() == sse_event("handoff", "in flight")
        assert await slow.next_chunk() is None

        response = await http.post(_path(session, "handoffs"), json="later")
        assert response.status_code == 202
        assert await healthy.next_chunk() == sse_event("handoff", "later")
        assert [a.id for a in session.handoffs.attachments()] == ["a2"]


@pytest.mark.parametrize("spec_version", ["2.3", "2.4"])
@pytest.mark.parametrize("action", ["close", "disconnect", "cancel"])
async def test_full_stream_queue_closes_on_shutdown_or_disconnect(
    client: TestClient,
    session: SessionImpl,
    spec_version: str,
    action: str,
) -> None:
    async with StalledPairStream(
        client, session, spec_version=spec_version
    ) as stream:
        await stream.ready()
        session.handoffs.publish("in flight")
        await asyncio.wait_for(stream.blocked.wait(), timeout=2)
        for index in range(MAX_PENDING_EVENTS):
            session.handoffs.publish(index)
        assert len(session.handoffs.attachments()) == 1

        detached = asyncio.Event()
        consumer = session.room.get_consumer(ConsumerId("browser"))
        assert isinstance(consumer, Mock)
        consumer.notify.side_effect = lambda _message: detached.set()
        if action == "close":
            session.close()
        elif action == "cancel":
            assert stream.task is not None
            stream.task.cancel()
        else:
            stream.incoming.put_nowait({"type": "http.disconnect"})

        await asyncio.wait_for(detached.wait(), timeout=2)
        assert session.handoffs.attachments() == []
        assert deserialize_kernel_message(
            consumer.notify.call_args.args[0]
        ) == (AttachmentsNotification(attachments=[]))
        stream.resume.set()
        assert stream.task is not None
        if action == "cancel":
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(stream.task, timeout=2)
        else:
            await asyncio.wait_for(stream.task, timeout=2)
