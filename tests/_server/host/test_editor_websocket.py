# Copyright 2026 Marimo. All rights reserved.
"""The editor's session lifecycle on the host event stream."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import msgspec
import pytest
from dirty_equals import IsStr
from starlette.websockets import WebSocketDisconnect

from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.notification import (
    AlertNotification,
    CellNotification,
    StartupProgressNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._server.host import HOST_API_PATH
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.context import HostContext
from marimo._session.managers.ipc import KernelStartupError
from marimo._types.ids import ConsumerId, SessionId
from tests._server.api.endpoints.ws_helpers import headers
from tests._server.host.drive import socket_snapshot
from tests._server.mocks import get_session_manager

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from starlette.testclient import TestClient, WebSocketTestSession


@pytest.fixture
def editor_host(client: TestClient) -> Iterator[SessionBridge]:
    bridge = SessionBridge(get_session_manager(client))
    client.app.state.host_context = HostContext(  # type: ignore[union-attr]
        bridge=bridge, token="host-token", port=1234
    )
    with client:
        assert client.portal is not None
        client.portal.call(bridge.open)
        try:
            yield bridge
        finally:
            client.portal.call(bridge.close)


def socket_url(bridge: SessionBridge, session_id: str = "s1") -> str:
    (notebook_id,) = bridge.host.notebooks
    return f"{HOST_API_PATH}/notebooks/{notebook_id}/events/ws?session_id={session_id}&access_token=fake-token"


def receive_notification(
    websocket: WebSocketTestSession, op: str
) -> dict[str, Any]:
    while True:
        event = websocket.receive_json()
        assert "op" not in event
        if event["event"] == "marimo" and event["data"]["marimo"]["op"] == op:
            return event["data"]["marimo"]


@pytest.mark.parametrize("types", [None, "marimo", "marimo,run"])
def test_editor_starts_and_runs_through_the_host_socket(
    client: TestClient, editor_host: SessionBridge, types: str | None
) -> None:
    url = socket_url(editor_host)
    if types is not None:
        url += f"&types={types}"
    with client.websocket_connect(url) as websocket:
        messages = []
        while True:
            event = websocket.receive_json()
            messages.append(event)
            if (
                event["event"] == "marimo"
                and event["data"]["marimo"]["op"] == "kernel-ready"
            ):
                ready = event["data"]["marimo"]
                break
        assert ready["resumed"] is False
        assert ready["consumer_capabilities"]["edit"] is True
        boundary = next(
            i for i, event in enumerate(messages) if event["event"] == "ready"
        )
        assert all("id" not in event for event in messages[:boundary])
        assert messages[boundary]["data"] == {}
        if types is None:
            names = [event["event"] for event in messages[:boundary]]
            assert names[0] == "notebook"
            assert names.index("cell") < names.index("document")
        cell_id = ready["cell_ids"][0]
        response = client.post(
            "/api/kernel/run",
            headers=headers("s1"),
            json={"cellIds": [cell_id], "codes": ["print('host socket')"]},
        )
        assert response.status_code == 200, response.text
        while True:
            event = websocket.receive_json()
            messages.append(event)
            if (
                event["event"] == "marimo"
                and event["data"]["marimo"]["op"] == "completed-run"
            ):
                break
        received_types = {event["event"] for event in messages}
        if types is None:
            assert "run" in received_types
        else:
            assert received_types == {*types.split(","), "ready"}
        consoles = [
            event["data"]["marimo"]["console"]
            for event in messages
            if event["event"] == "marimo"
            and event["data"]["marimo"]["op"] == "cell-op"
            and event["data"]["marimo"]["console"]
        ]
        assert sum("host socket" in str(output) for output in consoles) == 1


def test_editor_receives_native_attachment_snapshots_and_changes(
    client: TestClient, editor_host: SessionBridge
) -> None:
    assert client.portal is not None
    (notebook_id,) = editor_host.host.notebooks
    notebook = client.portal.call(editor_host.host.notebook, notebook_id)
    agent = client.portal.call(
        lambda: notebook.attach(kind="agent", name="Test Agent")
    )
    url = f"{socket_url(editor_host)}&types=attachment"
    with client.websocket_connect(url) as socket:
        snapshot = socket_snapshot(socket)
        assert [event["event"] for event in snapshot] == [
            "attachment",
            "attachment",
            "ready",
        ]
        assert snapshot[0]["data"]["attachment"] == msgspec.to_builtins(agent)
        client.portal.call(notebook.detach, agent.id)
        removed = socket.receive_json()
        assert removed == {
            "event": "attachment.removed",
            "id": IsStr,
            "data": {"id": agent.id, "time": IsStr},
        }
        replacement = client.portal.call(
            lambda: notebook.attach(kind="agent", name="Replacement")
        )
        attached = socket.receive_json()
        assert attached["event"] == "attachment"
        assert attached["data"]["attachment"] == msgspec.to_builtins(
            replacement
        )
    client.portal.call(notebook.detach, replacement.id)
    with client.websocket_connect(url) as socket:
        snapshot = socket_snapshot(socket)
        assert [event["event"] for event in snapshot] == [
            "attachment",
            "ready",
        ]
        assert snapshot[0]["data"]["attachment"]["kind"] == "client"


def test_reconnect_keeps_state_and_refresh_replays_it(
    client: TestClient, editor_host: SessionBridge
) -> None:
    url = f"{socket_url(editor_host)}&types=marimo"
    with client.websocket_connect(url) as websocket:
        ready = receive_notification(websocket, "kernel-ready")
        cell_id = ready["cell_ids"][0]
        response = client.post(
            "/api/kernel/run",
            headers=headers("s1"),
            json={"cellIds": [cell_id], "codes": ["print('retained output')"]},
        )
        assert response.status_code == 200, response.text
        receive_notification(websocket, "completed-run")
    with client.websocket_connect(url) as websocket:
        socket_snapshot(websocket)
        while True:
            event = websocket.receive_json()
            assert event["event"] == "marimo"
            notification = event["data"]["marimo"]
            assert notification["op"] not in ("kernel-ready", "cell-op")
            if notification["op"] == "reconnected":
                break
        assert (
            receive_notification(websocket, "alert")["title"] == "Reconnected"
        )
        cell = receive_notification(websocket, "cell-op")
        assert cell["cell_id"] == cell_id
        assert "retained output" in str(cell["console"])
    with client.websocket_connect(
        f"{socket_url(editor_host, 's2')}&types=marimo"
    ) as websocket:
        ready = receive_notification(websocket, "kernel-ready")
        assert ready["resumed"] is True
        assert ready["kiosk"] is False
        cell = receive_notification(websocket, "cell-op")
        assert cell["cell_id"] == cell_id
        assert "retained output" in str(cell["console"])


@pytest.mark.parametrize("replay", ["snapshot", "cursor", "reset"])
def test_reconnect_recovers_offline_notifications(
    client: TestClient, editor_host: SessionBridge, replay: str
) -> None:
    url = f"{socket_url(editor_host)}&types=marimo"
    with client.websocket_connect(url) as socket:
        cursor = socket_snapshot(socket)[-1]["id"]
        ready = receive_notification(socket, "kernel-ready")
    session = get_session_manager(client).get_session(SessionId("s1"))
    assert session is not None
    assert client.portal is not None
    update = CellNotification(
        cell_id=ready["cell_ids"][0],
        status="idle",
        output=CellOutput(
            channel=CellChannel.OUTPUT,
            mimetype="text/plain",
            data="offline output",
            timestamp=1.0,
        ),
        console=[
            CellOutput(
                channel=CellChannel.STDOUT,
                mimetype="text/plain",
                data="offline console",
                timestamp=1.0,
            )
        ],
        timestamp=1.0,
    )
    client.portal.call(session.notify, update, None)
    client.portal.call(
        session.notify,
        AlertNotification(title="excluded", description=""),
        ConsumerId("s1"),
    )
    if replay == "cursor":
        url += f"&cursor={cursor}"
    elif replay == "reset":
        # A bare integer is a cursor from a host before this one.
        url += "&cursor=999999999"
    with client.websocket_connect(url) as socket:
        opening = socket_snapshot(socket)
        assert [event["event"] for event in opening] == (
            ["reset", "ready"] if replay == "reset" else ["ready"]
        )
        receive_notification(socket, "reconnected")
        client.portal.call(
            session.notify,
            AlertNotification(title="marker", description=""),
            None,
        )
        notifications = []
        while True:
            event = socket.receive_json()
            notification = event["data"]["marimo"]
            if (
                notification["op"] == "alert"
                and notification["title"] == "marker"
            ):
                break
            notifications.append(notification)
        assert [n for n in notifications if n["op"] == "cell-op"] == [
            msgspec.json.decode(serialize_kernel_message(update))
        ]
        assert not any(n["op"] == "kernel-ready" for n in notifications)
        assert not any(
            n["op"] == "alert" and n["title"] == "excluded"
            for n in notifications
        )


@pytest.mark.parametrize("run_id", ["", "wanted"])
def test_run_filter_is_rejected_before_starting_an_editor_session(
    client: TestClient, editor_host: SessionBridge, run_id: str
) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"{socket_url(editor_host)}&run_id={run_id}"
        ):
            pytest.fail("Editor run filter was accepted")
    assert (exc.value.code, exc.value.reason) == (
        1008,
        "Editor sessions do not support run_id filtering",
    )
    assert not get_session_manager(client).sessions


def test_second_tab_gets_private_startup_and_excluded_messages_do_not_echo(
    client: TestClient, editor_host: SessionBridge
) -> None:
    with client.websocket_connect(socket_url(editor_host)) as first:
        receive_notification(first, "kernel-ready")
        with client.websocket_connect(socket_url(editor_host, "s2")) as second:
            ready = receive_notification(second, "kernel-ready")
            assert ready["kiosk"] is True
            assert ready["consumer_capabilities"]["edit"] is False
            session = get_session_manager(client).get_session(SessionId("s1"))
            assert session is not None
            first.portal.call(
                session.notify,
                AlertNotification(title="other client", description=""),
                ConsumerId("s1"),
            )
            first.portal.call(
                session.notify,
                AlertNotification(title="marker", description=""),
                None,
            )
            while True:
                event = first.receive_json()
                if event["event"] != "marimo":
                    continue
                notification = event["data"]["marimo"]
                assert notification["op"] != "kernel-ready"
                if notification["op"] == "alert":
                    assert notification["title"] == "marker"
                    break
            assert (
                receive_notification(second, "alert")["title"]
                == "other client"
            )
            assert receive_notification(second, "alert")["title"] == "marker"


def test_session_cannot_bind_to_another_notebook(
    client: TestClient, editor_host: SessionBridge, tmp_path: Path
) -> None:
    other = tmp_path / "other.py"
    other.write_text("import marimo\napp = marimo.App()\n")
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"{socket_url(editor_host)}&file={other}"
        ):
            pytest.fail("Mismatched notebook was accepted")
    assert exc.value.code == 1008
    assert not get_session_manager(client).sessions


def test_startup_failure_is_sent_before_the_close(
    client: TestClient,
    editor_host: SessionBridge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fail(**kwargs: Any) -> None:
        del kwargs
        raise KernelStartupError("kernel could not start")

    monkeypatch.setattr(get_session_manager(client), "create_session", fail)
    with client.websocket_connect(socket_url(editor_host)) as websocket:
        assert (
            receive_notification(websocket, "kernel-startup-error")["error"]
            == "kernel could not start"
        )
        with pytest.raises(WebSocketDisconnect) as exc:
            websocket.receive_json()
        assert (exc.value.code, exc.value.reason) == (
            1011,
            "MARIMO_KERNEL_STARTUP_ERROR",
        )


def test_disconnect_during_startup_cancels_the_connection(
    client: TestClient,
    editor_host: SessionBridge,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cancelled = asyncio.Event()

    async def wait_for_startup(**kwargs: Any) -> None:
        kwargs["session_consumer"].notify(
            serialize_kernel_message(
                StartupProgressNotification(
                    phase="starting-kernel",
                    logs="Starting",
                    log_mode="replace",
                )
            )
        )
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(
        get_session_manager(client), "create_session", wait_for_startup
    )
    with client.websocket_connect(socket_url(editor_host)) as websocket:
        assert (
            receive_notification(websocket, "startup-progress")["logs"]
            == "Starting"
        )
    assert client.portal is not None
    client.portal.call(asyncio.wait_for, cancelled.wait(), 5)
    assert not get_session_manager(client).sessions


def test_invalid_event_types_are_rejected_before_starting_a_session(
    client: TestClient, editor_host: SessionBridge
) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(
            f"{socket_url(editor_host)}&types=unknown"
        ):
            pytest.fail("Invalid event types were accepted")
    assert (exc.value.code, exc.value.reason) == (1008, "Invalid event types")
    assert not get_session_manager(client).sessions


def test_editor_resumes_host_events_without_replaying_private_notifications(
    client: TestClient, editor_host: SessionBridge
) -> None:
    url = f"{socket_url(editor_host)}&types=marimo,custom"
    with client.websocket_connect(url) as socket:
        cursor = socket_snapshot(socket)[-1]["id"]
        receive_notification(socket, "kernel-ready")
        session = get_session_manager(client).get_session(SessionId("s1"))
        assert session is not None
        socket.portal.call(
            session.notify,
            AlertNotification(title="excluded", description=""),
            ConsumerId("s1"),
        )
        socket.portal.call(
            session.notify,
            AlertNotification(title="marker", description=""),
            None,
        )
        assert receive_notification(socket, "alert")["title"] == "marker"
    assert client.portal is not None
    (notebook_id,) = editor_host.host.notebooks
    notebook = client.portal.call(editor_host.host.notebook, notebook_id)
    client.portal.call(notebook.emit, "test.missed", {"text": "replayed"})
    with client.websocket_connect(f"{url}&cursor={cursor}") as socket:
        opening = socket_snapshot(socket)
        assert [event["event"] for event in opening] == ["custom", "ready"]
        assert opening[0]["data"]["custom"] == {
            "type": "test.missed",
            "data": {"text": "replayed"},
        }
        receive_notification(socket, "reconnected")
        assert receive_notification(socket, "alert")["title"] == "Reconnected"


def test_an_empty_cursor_is_rejected_before_starting_a_session(
    client: TestClient, editor_host: SessionBridge
) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"{socket_url(editor_host)}&cursor="):
            pytest.fail("Invalid cursor was accepted")
    assert (exc.value.code, exc.value.reason) == (1008, "Invalid event cursor")
    assert not get_session_manager(client).sessions
