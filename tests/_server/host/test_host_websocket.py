# Copyright 2026 Marimo. All rights reserved.
"""Retained session state on the host WebSocket."""

from __future__ import annotations

from typing import TYPE_CHECKING

import msgspec
import pytest
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.testclient import TestClient

from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.notification import (
    CellNotification,
    CompletedRunNotification,
)
from marimo._server.host import HOST_API_PATH
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._server.host.middleware import HostApiMiddleware
from marimo._server.models.home import MarimoFile
from marimo._server.workspace import FixedFilesWorkspace
from marimo._session.notebook import AppFileManager
from marimo._session.state.session_view import SessionView
from tests._server.host.conftest import FakeManager, FakeSession
from tests._server.host.drive import (
    AUTHORITY,
    PORT,
    socket_snapshot,
    with_client_address,
)

if TYPE_CHECKING:
    from pathlib import Path

    from starlette.types import Message, Receive, Scope, Send

AUTH = {"Authorization": "Bearer snapshot-test"}


@pytest.fixture
def session_host(
    manager: FakeManager, tmp_path: Path
) -> tuple[Starlette, SessionBridge, FakeSession]:
    path = tmp_path / "notebook.py"
    path.write_text(
        "import marimo\napp = marimo.App()\n"
        "@app.cell\ndef _():\n    x = 1\n    return (x,)\n"
    )
    manager.workspace = FixedFilesWorkspace(
        [MarimoFile(name=path.name, path=str(path))], directory=str(tmp_path)
    )
    session = FakeSession(str(path))
    session.document = AppFileManager(str(path)).app.cell_manager.document
    session.session_view = SessionView()
    session.session_view.add_notification(
        CellNotification(
            cell_id=session.document.cell_ids[0],
            output=CellOutput(
                channel=CellChannel.OUTPUT,
                mimetype="text/plain",
                data="retained output",
                timestamp=1.0,
            ),
            status="idle",
            run_id="r1",
            timestamp=1.0,
        )
    )
    manager.sessions["existing"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    app = Starlette(middleware=[Middleware(HostApiMiddleware)])
    app.state.host_context = HostContext(
        bridge=bridge, token="snapshot-test", port=PORT
    )
    return app, bridge, session


def test_snapshot_is_private_and_precedes_updates_during_accept(
    session_host: tuple[Starlette, SessionBridge, FakeSession],
) -> None:
    app, bridge, session = session_host
    connections = 0

    async def app_with_update(
        scope: Scope, receive: Receive, send: Send
    ) -> None:
        async def send_with_update(message: Message) -> None:
            nonlocal connections
            if message["type"] == "websocket.accept":
                connections += 1
                if connections == 2:
                    session.notify(CompletedRunNotification(run_id="live"))
            await send(message)

        await app(scope, receive, send_with_update)

    with TestClient(with_client_address(app_with_update)) as client:
        assert client.portal is not None
        client.portal.call(bridge.open)
        try:
            (notebook_id,) = bridge.host.notebooks
            url = f"ws://{AUTHORITY}{HOST_API_PATH}/notebooks/{notebook_id}/events/ws?types=marimo"
            with client.websocket_connect(url, headers=dict(AUTH)) as first:
                opening = socket_snapshot(first)
                initial = opening[:-1]
                assert initial == [
                    {
                        "event": "marimo",
                        "data": {
                            "marimo": {
                                "op": "environment-state",
                                "source": source,
                                "state": {
                                    "restart_required": False,
                                    "operations": [],
                                },
                            }
                        },
                    }
                    for source in ("kernel", "server")
                ] + [
                    {
                        "event": "marimo",
                        "data": {
                            "marimo": {
                                "op": "cell-op",
                                "cell_id": session.document.cell_ids[0],
                                "output": {
                                    "channel": "output",
                                    "mimetype": "text/plain",
                                    "data": "retained output",
                                    "timestamp": 1.0,
                                },
                                "console": None,
                                "status": "idle",
                                "stale_inputs": None,
                                "run_id": "r1",
                                "execution_id": None,
                                "timestamp": 1.0,
                            }
                        },
                    }
                ]
                with client.websocket_connect(
                    url, headers=dict(AUTH)
                ) as second:
                    assert socket_snapshot(second)[:-1] == initial
                    live = second.receive_json()
                    attachment_update = first.receive_json()
                    assert (
                        attachment_update["data"]["marimo"]["op"]
                        == "attachments"
                    )
                    assert (
                        len(attachment_update["data"]["marimo"]["attachments"])
                        == 2
                    )
                    assert first.receive_json() == live
                    assert live == {
                        "id": live["id"],
                        "event": "marimo",
                        "data": {
                            "marimo": {
                                "op": "completed-run",
                                "run_id": "live",
                                "outcome": "succeeded",
                                "error": None,
                            }
                        },
                    }
        finally:
            client.portal.call(bridge.close)


@pytest.mark.parametrize(
    ("query", "has_snapshot"),
    [
        ("types=marimo&run_id=r1", True),
        ("types=marimo&run_id=other", False),
        ("types=custom", False),
    ],
)
def test_snapshot_obeys_type_and_run_filters(
    session_host: tuple[Starlette, SessionBridge, FakeSession],
    query: str,
    has_snapshot: bool,
) -> None:
    app, bridge, session = session_host
    with TestClient(with_client_address(app)) as client:
        assert client.portal is not None
        client.portal.call(bridge.open)
        try:
            (notebook_id,) = bridge.host.notebooks
            notebook = client.portal.call(bridge.host.notebook, notebook_id)
            url = f"ws://{AUTHORITY}{HOST_API_PATH}/notebooks/{notebook_id}/events/ws?{query}"
            with client.websocket_connect(
                url, headers=dict(AUTH)
            ) as websocket:
                opening = socket_snapshot(websocket)
                assert len(opening) == (2 if has_snapshot else 1)
                if has_snapshot:
                    snapshot = opening[0]
                    assert "id" not in snapshot
                    assert snapshot["event"] == "marimo"
                    assert snapshot["data"]["marimo"]["run_id"] == "r1"
                    assert (
                        snapshot["data"]["marimo"]["output"]["data"]
                        == "retained output"
                    )
                if query == "types=custom":
                    client.portal.call(notebook.emit, "test.marker", {})
                    assert websocket.receive_json()["event"] == "custom"
                else:
                    run_id = "r1" if has_snapshot else "other"
                    client.portal.call(
                        session.notify, CompletedRunNotification(run_id=run_id)
                    )
                    assert websocket.receive_json()["data"]["marimo"] == {
                        "op": "completed-run",
                        "run_id": run_id,
                        "outcome": "succeeded",
                        "error": None,
                    }
        finally:
            client.portal.call(bridge.close)


def test_opening_delivers_protocol_and_session_state_before_ready(
    session_host: tuple[Starlette, SessionBridge, FakeSession],
) -> None:
    app, bridge, session = session_host
    with TestClient(with_client_address(app)) as client:
        assert client.portal is not None
        client.portal.call(bridge.open)
        try:
            (notebook_id,) = bridge.host.notebooks
            url = f"ws://{AUTHORITY}{HOST_API_PATH}/notebooks/{notebook_id}/events/ws"
            with client.websocket_connect(url, headers=dict(AUTH)) as socket:
                opening = socket_snapshot(socket)
                names = [event["event"] for event in opening]
                assert names[0] == "notebook"
                assert names.index("cell") < names.index("document")
                assert names.index("document") < names.index("marimo")
                assert "attachment" in names
                assert all("id" not in event for event in opening[:-1])
                cell = next(
                    e["data"]["cell"] for e in opening if e["event"] == "cell"
                )
                document = next(
                    e["data"]["document"]
                    for e in opening
                    if e["event"] == "document"
                )
                assert cell["id"] == session.document.cell_ids[0]
                assert document["order"] == [cell["id"]]
        finally:
            client.portal.call(bridge.close)


@pytest.mark.parametrize("use_header", [False, True])
def test_reconnect_replays_original_events_then_continues_live(
    session_host: tuple[Starlette, SessionBridge, FakeSession],
    use_header: bool,
) -> None:
    app, bridge, session = session_host
    with TestClient(with_client_address(app)) as client:
        assert client.portal is not None
        client.portal.call(bridge.open)
        try:
            (notebook_id,) = bridge.host.notebooks
            url = f"ws://{AUTHORITY}{HOST_API_PATH}/notebooks/{notebook_id}/events/ws?types=marimo"
            with client.websocket_connect(url, headers=dict(AUTH)) as socket:
                cursor = socket_snapshot(socket)[-1]["id"]
                client.portal.call(
                    session.notify, CompletedRunNotification(run_id="missed")
                )
                missed = socket.receive_json()
            headers = dict(AUTH)
            if use_header:
                headers["Last-Event-ID"] = cursor
            else:
                url += f"&cursor={cursor}"
            with client.websocket_connect(url, headers=headers) as socket:
                replay = socket_snapshot(socket)
                assert replay[0] == missed
                assert [
                    event["data"]["marimo"]["op"] for event in replay[1:-1]
                ] == ["attachments", "attachments"]
                assert replay[1]["data"]["marimo"]["attachments"] == []
                assert len(replay[2]["data"]["marimo"]["attachments"]) == 1
                client.portal.call(
                    session.notify, CompletedRunNotification(run_id="live")
                )
                live = socket.receive_json()
                assert live["data"]["marimo"]["run_id"] == "live"
                assert int(live["id"]) > int(replay[-1]["id"])
        finally:
            client.portal.call(bridge.close)


def test_expired_cursor_resets_to_current_state(
    session_host: tuple[Starlette, SessionBridge, FakeSession],
) -> None:
    app, bridge, _ = session_host
    with TestClient(with_client_address(app)) as client:
        assert client.portal is not None
        client.portal.call(bridge.open)
        try:
            (notebook_id,) = bridge.host.notebooks
            notebook = client.portal.call(bridge.host.notebook, notebook_id)
            url = f"ws://{AUTHORITY}{HOST_API_PATH}/notebooks/{notebook_id}/events/ws?types=cell,document,marimo,custom"
            with client.websocket_connect(url, headers=dict(AUTH)) as socket:
                initial = socket_snapshot(socket)
                cursor = initial[-1]["id"]
            # Expire the default 1000-event replay history.
            for index in range(1001):
                client.portal.call(
                    notebook.emit, "test.expire", {"index": index}
                )
            with client.websocket_connect(
                f"{url}&cursor={cursor}", headers=dict(AUTH)
            ) as socket:
                reset = socket_snapshot(socket)
                assert reset[0] == {"event": "reset", "data": {}}
                assert reset[1:-1] == initial[:-1]
                assert int(reset[-1]["id"]) > int(cursor)
                event = client.portal.call(notebook.emit, "test.live", {})
                live = socket.receive_json()
                assert live["event"] == "custom"
                assert live["data"]["custom"] == msgspec.to_builtins(event)
                assert int(live["id"]) > int(reset[-1]["id"])
        finally:
            client.portal.call(bridge.close)
