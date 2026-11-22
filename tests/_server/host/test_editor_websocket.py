# Copyright 2026 Marimo. All rights reserved.
"""The editor's session lifecycle on the host event stream."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any

import msgspec
import pytest
from dirty_equals import IsStr
from inline_snapshot import snapshot
from starlette.websockets import WebSocketDisconnect

from marimo._config.config import DEFAULT_CONFIG
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
from marimo._session.notebook import AppFileManager
from marimo._session.state.serialize import (
    get_session_cache_file,
    serialize_session_view,
)
from marimo._types.ids import CellId_t, ConsumerId, SessionId
from marimo._utils.code import hash_code
from marimo._version import __version__
from tests._server.api.endpoints.ws_helpers import headers
from tests._server.host.drive import socket_snapshot
from tests._server.mocks import get_session_manager, run_cells

if TYPE_CHECKING:
    from collections.abc import Iterator

    from starlette.testclient import TestClient, WebSocketTestSession

    from marimo._config.manager import UserConfigStore


def first_cell_id(client: TestClient, session_id: str) -> CellId_t:
    """The first cell of the session's document, as the host stream has it."""
    session = get_session_manager(client).get_session(SessionId(session_id))
    assert session is not None
    return session.document.cell_ids[0]


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


def assert_reconnect_alert(websocket: WebSocketTestSession) -> None:
    assert websocket.receive_json() == snapshot(
        {
            "event": "marimo",
            "data": {
                "marimo": {
                    "op": "alert",
                    "title": "Reconnected",
                    "description": "You have reconnected to an existing session.",
                    "variant": None,
                }
            },
        }
    )


def completed(event: dict[str, Any], run_id: str) -> bool:
    """Whether `event` is the kernel's completed-run for the host run."""
    return (
        event["event"] == "marimo"
        and event["data"]["marimo"]["op"] == "completed-run"
        and event["data"]["marimo"]["run_id"] == run_id
    )


def receive_completed_run(
    websocket: WebSocketTestSession, run_id: str
) -> None:
    """Read until the host run's cycle has ended; an edit's cycle may come first."""
    while not completed(websocket.receive_json(), run_id):
        pass


def test_editor_opens_with_the_results_an_earlier_session_stored(
    client: TestClient, editor_host: SessionBridge
) -> None:
    # With autorun off the session keeps its own cache of this file, and
    # starts writing it as soon as it exists.
    manager = get_session_manager(client)
    manager._config_manager = manager._config_manager.with_overrides(
        {
            "runtime": {
                **DEFAULT_CONFIG.runtime.to_dict(),
                "auto_instantiate": False,
            }
        }
    )
    (notebook_id,) = editor_host.host.notebooks
    file = editor_host.index.file_of(notebook_id)
    assert file is not None
    (code,) = AppFileManager(str(file)).app.cell_manager.codes()
    cache = get_session_cache_file(file)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(
        json.dumps(
            {
                "version": "1",
                "metadata": {
                    "marimo_version": __version__,
                    "script_metadata_hash": None,
                },
                "cells": [
                    {
                        "id": "earlier",
                        "code_hash": hash_code(code),
                        "outputs": [
                            {"type": "data", "data": {"text/plain": "stored"}}
                        ],
                        "console": [],
                    }
                ],
            }
        )
    )

    with client.websocket_connect(socket_url(editor_host)) as websocket:
        opening = socket_snapshot(websocket)

    assert [
        event["data"]["output"]["media"]
        for event in opening
        if event["event"] == "output"
    ] == [{"mimetype": "text/plain", "data": "stored"}]


@pytest.mark.parametrize(
    "kinds",
    [None, "marimo", "marimo,run", "marimo,run,execution,output,console"],
)
def test_editor_starts_and_runs_through_the_host_socket(
    client: TestClient, editor_host: SessionBridge, kinds: str | None
) -> None:
    url = socket_url(editor_host)
    if kinds is not None:
        url += f"&kinds={kinds}"
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
        if kinds is None:
            names = [event["event"] for event in messages[:boundary]]
            assert names[0] == "notebook"
            assert names.index("cell") < names.index("document")
        cell_id = first_cell_id(client, "s1")
        (notebook_id,) = editor_host.host.notebooks
        response = run_cells(
            client,
            notebook_id,
            {cell_id: "print('host socket')\n1234567"},
            headers=headers("s1"),
        )
        assert response.status_code == 202, response.text
        while True:
            event = websocket.receive_json()
            messages.append(event)
            if completed(event, response.json()["id"]):
                break
        received_types = {event["event"] for event in messages}
        if kinds is None:
            assert "run" in received_types
            host_url = f"{HOST_API_PATH}/notebooks/{notebook_id}/events/ws?access_token=fake-token"
            with client.websocket_connect(host_url) as observer:
                retained = socket_snapshot(observer)
            assert any(
                event["event"] == "console"
                and "host socket"
                in event["data"]["console"]["content"]["text"]
                for event in retained
            )
            assert not any(
                event["event"] == "marimo"
                and event["data"]["marimo"]["op"] == "cell-op"
                for event in retained
            )
        else:
            assert received_types == {*kinds.split(","), "ready"}
        if kinds and "output" in kinds:
            assert any(
                event["event"] == "output"
                and "1234567" in str(event["data"]["output"]["media"])
                for event in messages
            )
            assert not any(
                event["event"] == "marimo"
                and event["data"]["marimo"]["op"] == "cell-op"
                and event["data"]["marimo"]["output"] is not None
                for event in messages
            )
        assert not any(
            event["event"] == "marimo"
            and event["data"]["marimo"]["op"]
            in {"cell-op", "pdb-output", "callback-output"}
            for event in messages
        )
        assert sum(
            event["event"] == "console"
            and "host socket" in event["data"]["console"]["content"]["text"]
            for event in messages
        ) == (kinds is None or "console" in kinds)


def test_widget_callback_console_is_routed_to_its_defining_cell(
    client: TestClient, editor_host: SessionBridge
) -> None:
    get_session_manager(client).redirect_console_to_browser = True
    url = socket_url(editor_host)
    with client.websocket_connect(url) as socket:
        receive_notification(socket, "kernel-ready")
        cell_id = first_cell_id(client, "s1")
        (notebook_id,) = editor_host.host.notebooks
        response = run_cells(
            client,
            notebook_id,
            {
                cell_id: dedent("""
                    import marimo as mo
                    from threading import Event, Thread

                    _after_widget = Event()
                    def _late_write():
                        if _after_widget.wait(10):
                            print("from original execution")
                    mo.Thread(target=_late_write, daemon=True).start()

                    def on_change(value):
                        if value == 0:
                            mo.output.clear_console()
                            return
                        try:
                            input("Another value? ")
                        except EOFError:
                            before = Thread(target=lambda: print("before"))
                            before.start()
                            before.join()
                            worker = mo.Thread(target=lambda: print(f"changed {value}"))
                            worker.start()
                            worker.join()
                            print("after", flush=True)
                            _after_widget.set()

                    slider = mo.ui.slider(0, 10, on_change=on_change)
                    _writer = Thread(target=lambda: print(slider._id))
                    _writer.start()
                    _writer.join()
                """)
            },
            headers=headers("s1"),
        )
        assert response.status_code == 202, response.text
        stdout = []
        last_seq = -1
        while True:
            frame = socket.receive_json()
            if completed(frame, response.json()["id"]):
                break
            if frame["event"] == "console":
                stdout.append(frame["data"]["console"]["content"]["text"])
                last_seq = frame["data"]["console"]["seq"]
        widget_id = "".join(stdout).strip()
        assert widget_id
        update = client.post(
            "/api/kernel/set_ui_element_value",
            headers=headers("s1"),
            json={"objectIds": [widget_id], "values": [7]},
        )
        assert update.status_code == 200, update.text
        live = []
        while not live or "after" not in "".join(live):
            callback = receive_notification(socket, "callback-output")
            assert callback["cell_id"] == cell_id
            assert callback["after_seq"] == [last_seq] * len(
                callback["entries"]
            )
            live.extend(entry["data"] for entry in callback["entries"])
        assert "".join(live).splitlines() == ["before", "changed 7", "after"]
        while (frame := socket.receive_json())["event"] != "console":
            pass
        assert (
            frame["data"]["console"]["content"]["text"]
            == "from original execution\n"
        )
        assert frame["data"]["console"]["seq"] > last_seq
        session = get_session_manager(client).get_session(SessionId("s1"))
        assert session is not None
        export = serialize_session_view(
            session.session_view,
            [CellId_t(cell_id)],
            for_display=True,
            drop_virtual_file_outputs=False,
        )
        text = "".join(
            row["text"]
            for row in export["cells"][0]["console"]
            if row["type"] == "stream"
        )
        assert text.splitlines() == [
            widget_id,
            "before",
            "changed 7",
            "after",
            "from original execution",
        ]
    with client.websocket_connect(url) as socket:
        frames = socket_snapshot(socket)
        console = [
            frame["data"]["console"]
            for frame in frames
            if frame["event"] == "console"
        ]
        assert [item["content"]["text"] for item in console] == [
            *stdout,
            "from original execution\n",
        ]
        assert not any(
            frame["event"] == "console"
            and "changed 7" in frame["data"]["console"]["content"]["text"]
            for frame in frames
        )
        replay = receive_notification(socket, "callback-output")
        assert replay["replace"]
        assert replay["after_seq"] == [last_seq] * len(replay["entries"])
        assert "".join(
            entry["data"] for entry in replay["entries"]
        ).splitlines() == ["before", "changed 7", "after"]

        clear = client.post(
            "/api/kernel/set_ui_element_value",
            headers=headers("s1"),
            json={"objectIds": [widget_id], "values": [0]},
        )
        assert clear.status_code == 200, clear.text
        removed = set()
        cleared_callbacks = False
        while len(removed) < len(console) or not cleared_callbacks:
            frame = socket.receive_json()
            if frame["event"] == "console.removed":
                removed.add(frame["data"]["id"])
            elif frame["event"] == "marimo":
                message = frame["data"]["marimo"]
                if message["op"] == "callback-output":
                    assert message["entries"] == []
                    cleared_callbacks = True
        assert removed == {item["id"] for item in console}
        assert (
            session.session_view.cell_console(
                CellId_t(cell_id), include_callbacks=True
            )
            == []
        )
    with client.websocket_connect(url) as socket:
        assert not any(
            frame["event"] == "console" for frame in socket_snapshot(socket)
        )
        assert receive_notification(socket, "callback-output")["entries"] == []


def test_editor_with_autorun_reports_the_startup_run_on_the_host_socket(
    client: TestClient,
    editor_host: SessionBridge,
    user_config_manager: UserConfigStore,
) -> None:
    Path(user_config_manager.get_config_path()).write_text(
        "[runtime]\nauto_instantiate = true\n"
    )
    with client.websocket_connect(socket_url(editor_host)) as websocket:
        while True:
            event = websocket.receive_json()
            if (
                event["event"] == "execution"
                and event["data"]["execution"]["state"]["status"]
                == "completed"
            ):
                execution = event["data"]["execution"]
                break
        assert execution["cell_id"] == first_cell_id(client, "s1")
        assert execution["state"]["outcome"]["kind"] == "succeeded"


def test_editor_receives_native_attachment_snapshots_and_changes(
    client: TestClient, editor_host: SessionBridge
) -> None:
    assert client.portal is not None
    (notebook_id,) = editor_host.host.notebooks
    notebook = client.portal.call(editor_host.host.notebook, notebook_id)
    agent = client.portal.call(
        lambda: notebook.attach(kind="agent", name="Test Agent")
    )
    url = f"{socket_url(editor_host)}&kinds=attachment"
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
    url = f"{socket_url(editor_host)}&kinds=marimo,console,execution"
    with client.websocket_connect(url) as websocket:
        receive_notification(websocket, "kernel-ready")
        cell_id = first_cell_id(client, "s1")
        (notebook_id,) = editor_host.host.notebooks
        response = run_cells(
            client,
            notebook_id,
            {cell_id: "print('retained output')"},
            headers=headers("s1"),
        )
        assert response.status_code == 202, response.text
        receive_completed_run(websocket, response.json()["id"])
    with client.websocket_connect(url) as websocket:
        retained = socket_snapshot(websocket)
        [console] = [
            f["data"]["console"]
            for f in retained
            if f["event"] == "console"
            and "retained output" in f["data"]["console"]["content"]["text"]
        ]
        assert any(
            f["event"] == "execution"
            and f["data"]["execution"]["id"] == console["execution_id"]
            and f["data"]["execution"]["cell_id"] == cell_id
            for f in retained
        )
        assert_reconnect_alert(websocket)
    with client.websocket_connect(
        f"{socket_url(editor_host, 's2')}&kinds=marimo,console,execution"
    ) as websocket:
        retained = socket_snapshot(websocket)
        [console] = [
            f["data"]["console"]
            for f in retained
            if f["event"] == "console"
            and "retained output" in f["data"]["console"]["content"]["text"]
        ]
        assert any(
            f["event"] == "execution"
            and f["data"]["execution"]["id"] == console["execution_id"]
            and f["data"]["execution"]["cell_id"] == cell_id
            for f in retained
        )
        event = websocket.receive_json()
        assert event["event"] == "marimo"
        ready = event["data"]["marimo"]
        assert ready["op"] == "kernel-ready"
        assert ready["resumed"] is True
        assert ready["kiosk"] is False


@pytest.mark.parametrize("replay", ["snapshot", "cursor", "reset"])
def test_reconnect_recovers_offline_notifications(
    client: TestClient, editor_host: SessionBridge, replay: str
) -> None:
    url = f"{socket_url(editor_host)}&kinds=marimo"
    with client.websocket_connect(url) as socket:
        cursor = socket_snapshot(socket)[-1]["id"]
        receive_notification(socket, "kernel-ready")
    session = get_session_manager(client).get_session(SessionId("s1"))
    assert session is not None
    assert client.portal is not None
    update = CellNotification(
        cell_id=session.document.cell_ids[0],
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
        assert_reconnect_alert(socket)
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
        assert all(n["op"] != "cell-op" for n in notifications)
        assert all(
            n["op"] not in {"pdb-output", "callback-output"}
            for n in notifications
        )
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
            f"{socket_url(editor_host)}&kinds=unknown"
        ):
            pytest.fail("Invalid event kinds were accepted")
    assert (exc.value.code, exc.value.reason) == (1008, "Invalid event kinds")
    assert not get_session_manager(client).sessions


@pytest.mark.parametrize("session_route", [False, True])
def test_editor_resumes_host_events_without_replaying_private_notifications(
    client: TestClient, editor_host: SessionBridge, session_route: bool
) -> None:
    endpoint = (
        "/ws?session_id=s1&access_token=fake-token"
        if session_route
        else socket_url(editor_host)
    )
    url = f"{endpoint}&kinds=marimo,custom"
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
        assert_reconnect_alert(socket)


def test_an_empty_cursor_is_rejected_before_starting_a_session(
    client: TestClient, editor_host: SessionBridge
) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"{socket_url(editor_host)}&cursor="):
            pytest.fail("Invalid cursor was accepted")
    assert (exc.value.code, exc.value.reason) == (1008, "Invalid event cursor")
    assert not get_session_manager(client).sessions


def test_untitled_editor_bootstraps_and_reconnects_with_host_events(
    client: TestClient,
) -> None:
    from marimo._server.workspace import EmptyWorkspace

    manager = get_session_manager(client)
    manager.workspace = EmptyWorkspace()
    bridge = SessionBridge(manager)
    client.app.state.host_context = HostContext(
        bridge=bridge, token="host-token", port=1234
    )
    url = "/ws?session_id=new&access_token=fake-token"
    with client:
        assert client.portal is not None
        client.portal.call(bridge.open)
        try:
            with client.websocket_connect(url) as ws:
                snapshot = socket_snapshot(ws)
                receive_notification(ws, "kernel-ready")
                notebook_id = next(
                    e["data"]["notebook"]["id"]
                    for e in snapshot
                    if e["event"] == "notebook"
                )
                response = run_cells(
                    client,
                    notebook_id,
                    {first_cell_id(client, "new"): "x = 42"},
                    headers=headers("new"),
                )
                assert response.status_code == 202, response.text
                receive_completed_run(ws, response.json()["id"])
            with client.websocket_connect(url) as ws:
                snapshot = socket_snapshot(ws)
                assert_reconnect_alert(ws)
                assert (
                    next(
                        e["data"]["notebook"]["id"]
                        for e in snapshot
                        if e["event"] == "notebook"
                    )
                    == notebook_id
                )
        finally:
            client.portal.call(bridge.close)


def test_untitled_editor_restarts_its_runtime_through_the_host(
    client: TestClient,
) -> None:
    from marimo._server.workspace import EmptyWorkspace

    manager = get_session_manager(client)
    manager.workspace = EmptyWorkspace()
    bridge = SessionBridge(manager)
    client.app.state.host_context = HostContext(
        bridge=bridge, token="host-token", port=1234
    )
    url = "/ws?session_id=new&access_token=fake-token"
    with client:
        assert client.portal is not None
        client.portal.call(bridge.open)
        try:
            with client.websocket_connect(url) as ws:
                snapshot = socket_snapshot(ws)
                receive_notification(ws, "kernel-ready")
                notebook_id = next(
                    e["data"]["notebook"]["id"]
                    for e in snapshot
                    if e["event"] == "notebook"
                )
                cell_id = first_cell_id(client, "new")
                response = run_cells(
                    client,
                    notebook_id,
                    {cell_id: "x = 42"},
                    headers=headers("new"),
                )
                assert response.status_code == 202, response.text
                receive_completed_run(ws, response.json()["id"])

                restarted = client.post(
                    f"{HOST_API_PATH}/notebooks/{notebook_id}/runtime/restart",
                    headers={**headers("new"), "Idempotency-Key": "restart"},
                )
                assert restarted.status_code == 202, restarted.text
                replacement = restarted.json()["id"]
                while True:
                    try:
                        ws.receive_json()
                    except WebSocketDisconnect as exc:
                        disconnect = (exc.code, exc.reason)
                        break
                assert disconnect == (1000, "MARIMO_SHUTDOWN")
            with client.websocket_connect(url) as ws:
                snapshot = socket_snapshot(ws)
                assert (
                    next(
                        e["data"]["notebook"]["id"]
                        for e in snapshot
                        if e["event"] == "notebook"
                    )
                    == notebook_id
                )
                runtime = next(
                    e["data"]["runtime"]
                    for e in reversed(snapshot)
                    if e["event"] == "runtime"
                )
                assert (runtime["id"], runtime["state"]["status"]) == (
                    replacement,
                    "ready",
                )
                response = run_cells(
                    client,
                    notebook_id,
                    {cell_id: "x = 43"},
                    headers=headers("new"),
                )
                assert response.status_code == 202, response.text
                receive_completed_run(ws, response.json()["id"])
        finally:
            client.portal.call(bridge.close)
