# Copyright 2026 Marimo. All rights reserved.
"""App behavior on the host-framed session transport."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import msgspec
import pytest
from starlette.websockets import WebSocketDisconnect

from marimo._core import protocol
from marimo._server.codes import WebSocketCodes
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._server.host.events import serialize_event
from marimo._session.model import SessionMode
from marimo._types.ids import SessionId
from tests._server.host.drive import socket_snapshot
from tests._server.host.test_editor_websocket import receive_notification
from tests._server.mocks import get_session_manager

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.testclient import TestClient


@pytest.fixture
def app_host(client: TestClient) -> Iterator[SessionBridge]:
    manager = get_session_manager(client)
    manager.mode = SessionMode.RUN
    manager.include_code = False
    bridge = SessionBridge(manager)
    client.app.state.host_context = HostContext(
        bridge=bridge, token="", port=0
    )
    with client:
        assert client.portal is not None
        client.portal.call(bridge.open)
        try:
            yield bridge
        finally:
            client.portal.call(bridge.close)


def url(session_id: str) -> str:
    return f"/ws?session_id={session_id}&access_token=fake-token"


@pytest.mark.parametrize("include_code", [False, True])
def test_app_executes_with_hidden_source_and_retained_hashes(
    client: TestClient, app_host: SessionBridge, include_code: bool
) -> None:
    get_session_manager(client).include_code = include_code
    with client.websocket_connect(
        url("alice") + "&query_params=color%3Dblue"
    ) as ws:
        snapshot = socket_snapshot(ws)
        ready = receive_notification(ws, "kernel-ready")
        assert ready["auto_instantiated"] is True
        cell = next(
            e["data"]["cell"] for e in snapshot if e["event"] == "cell"
        )
        assert cell["code"] == (
            "import marimo as mo" if include_code else None
        )
        manager = get_session_manager(client)
        session = manager.get_session(SessionId("alice"))
        assert session is not None
        assert session._kernel_manager.app_metadata.query_params == {
            "color": "blue"
        }
        notebook = app_host.notebook_for_session(session)
        assert notebook is not None
        source = next(iter(notebook.document))
        assert source.code == "import marimo as mo"
        assert (cell["code_hash"], cell["etag"]) == (
            source.code_hash,
            source.etag,
        )
        # Delivery never mutates the host event, even when readers differ.
        event = next(
            e
            for e in app_host.host.events(notebook_id=notebook.id)
            if isinstance(e.event, protocol.CellEvent)
        )
        hidden = msgspec.json.decode(
            serialize_event(event, include_code=False)
        )
        visible = msgspec.json.decode(
            serialize_event(event, include_code=True)
        )
        assert hidden["data"]["cell"] == {
            **visible["data"]["cell"],
            "code": None,
        }
        assert event.event.data.cell.code == source.code
        executions = []
        while True:
            event = ws.receive_json()
            if event["event"] == "execution":
                executions.append(event["data"]["execution"])
            if (
                event["event"] == "run"
                and event["data"]["run"]["status"] == "completed"
            ):
                break
        assert executions
        assert executions[-1]["code_hash"] == cell["code_hash"]
        assert executions[-1]["status"] == "completed"


def test_app_visitors_are_isolated_and_reconnect_retains_identity(
    client: TestClient, app_host: SessionBridge
) -> None:
    manager = get_session_manager(client)
    with client.websocket_connect(url("alice")) as alice:
        a = socket_snapshot(alice)
        receive_notification(alice, "kernel-ready")
        alice_id = next(
            e["data"]["notebook"]["id"] for e in a if e["event"] == "notebook"
        )
        original = manager.get_session(SessionId("alice"))
        with client.websocket_connect(url("bob")) as bob:
            b = socket_snapshot(bob)
            receive_notification(bob, "kernel-ready")
            bob_id = next(
                e["data"]["notebook"]["id"]
                for e in b
                if e["event"] == "notebook"
            )
            assert alice_id != bob_id
            assert original is not manager.get_session(SessionId("bob"))
            assert all(
                record.path is None and record.operations == ()
                for record in app_host.host.notebooks.values()
            )
    with client.websocket_connect(url("alice")) as reconnected:
        snapshot = socket_snapshot(reconnected)
        receive_notification(reconnected, "reconnected")
        assert manager.get_session(SessionId("alice")) is original
        assert (
            next(
                e["data"]["notebook"]["id"]
                for e in snapshot
                if e["event"] == "notebook"
            )
            == alice_id
        )


def test_app_host_keeps_authentication(
    client: TestClient, app_host: SessionBridge
) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws?session_id=alice"):
            pass
    assert exc.value.code == WebSocketCodes.UNAUTHORIZED
    assert not app_host.host.notebooks
    assert not get_session_manager(client).sessions


def test_app_host_is_removed_when_session_expires(
    client: TestClient, app_host: SessionBridge
) -> None:
    manager = get_session_manager(client)
    with client.websocket_connect(url("alice")) as ws:
        cursor = socket_snapshot(ws)[-1]["id"]
        receive_notification(ws, "kernel-ready")
        session = manager.get_session(SessionId("alice"))
        assert session is not None
        session.ttl_seconds = 0.01
        notebook = app_host.notebook_for_session(session)
        assert notebook is not None
        removed = asyncio.Event()
        unsubscribe = app_host.host.subscribe(
            lambda _: removed.set(), types={"notebook"}
        )
        ws.close()

        async def expired() -> None:
            await asyncio.wait_for(removed.wait(), timeout=5)
            assert not manager.sessions
            assert not app_host.host.notebooks

        ws.portal.call(expired)
        unsubscribe()
    with client.websocket_connect(url("alice") + f"&cursor={cursor}") as ws:
        snapshot = socket_snapshot(ws)
        assert snapshot[0]["event"] == "reset"
        assert (
            next(
                e["data"]["notebook"]["id"]
                for e in snapshot
                if e["event"] == "notebook"
            )
            != notebook.id
        )


@pytest.mark.parametrize("stale", [False, True])
def test_app_session_replays_host_events_or_resets_stale_cursor(
    client: TestClient, app_host: SessionBridge, stale: bool
) -> None:
    endpoint = url("alice") + "&types=notebook,cell,custom,marimo"
    with client.websocket_connect(endpoint) as ws:
        snapshot = socket_snapshot(ws)
        cursor = snapshot[-1]["id"]
        receive_notification(ws, "kernel-ready")
        session = get_session_manager(client).get_session(SessionId("alice"))
        assert session is not None
        notebook = app_host.notebook_for_session(session)
        assert notebook is not None
    assert client.portal is not None
    client.portal.call(notebook.emit, "test.missed", {"value": 1})
    if stale:
        cursor = "expired-host-cursor"
    with client.websocket_connect(endpoint + f"&cursor={cursor}") as ws:
        opening = socket_snapshot(ws)
        if stale:
            assert opening[0]["event"] == "reset"
            assert any(e["event"] == "notebook" for e in opening)
            cells = [
                e["data"]["cell"] for e in opening if e["event"] == "cell"
            ]
            assert cells
            assert all(c["code"] is None for c in cells)
        else:
            assert [e["event"] for e in opening] == ["custom", "ready"]
            assert opening[0]["data"]["custom"]["data"] == {"value": 1}
        receive_notification(ws, "reconnected")
