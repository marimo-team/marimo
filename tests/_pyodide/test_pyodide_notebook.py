# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import msgspec
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from marimo._ast.app_config import _AppConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._core.calls import EditCall, dispatch
from marimo._messaging.notification import (
    VariableDeclarationNotification,
    VariablesNotification,
)
from marimo._messaging.serde import serialize_kernel_message
from marimo._pyodide.bootstrap import instantiate
from marimo._pyodide.pyodide_session import PyodideBridge, PyodideSession
from marimo._runtime.commands import (
    AppMetadata,
    CreateNotebookCommand,
    EditCellsCommand,
)
from marimo._session.model import SessionMode
from marimo._session.notebook import AppFileManager


@pytest.fixture
def bridge(tmp_path: Path):
    filename = tmp_path / "notebook.py"
    filename.write_text("""import marimo
app = marimo.App()
@app.cell
def _():
    x = 1
    return (x,)
""")
    session = PyodideSession(
        AppFileManager(str(filename)),
        SessionMode.EDIT,
        AppMetadata(
            query_params={},
            cli_args={},
            app_config=_AppConfig(),
            filename=str(filename),
        ),
        DEFAULT_CONFIG,
    )
    bridge = PyodideBridge(session)
    yield bridge
    bridge.close()


async def snapshot(
    bridge, subscription="reader", cursor=None, notifications=None
):
    """Follow host events, and marimo notifications into `notifications`."""
    events = []

    def receive(raw):
        event = json.loads(raw)
        if event["event"] != "marimo":
            events.append(event)
        elif notifications is not None:
            notifications.append(event["data"]["marimo"])

    await bridge.notebook.subscribe(subscription, cursor, receive)
    return events


def ops(notifications):
    return [notification["op"] for notification in notifications]


async def send(bridge, call):
    return json.loads(await bridge.notebook.call(json.dumps(call)))


def edit(events, code="x = 2", request_id="edit-1"):
    cell = next(
        event["data"]["cell"] for event in events if event["event"] == "cell"
    )
    return {
        "operation": "notebook.edit",
        "params": {"notebook_id": cell["notebook_id"]},
        "headers": {"idempotency-key": request_id},
        "body": {
            "changes": [
                {
                    "kind": "put_cell",
                    "base_etag": cell["etag"],
                    "cell": {
                        "id": cell["id"],
                        "code": code,
                        "name": cell["name"],
                        "config": cell["config"],
                    },
                }
            ]
        },
    }


async def test_snapshot_edit_and_retry(bridge):
    events = await snapshot(bridge)
    assert [event["event"] for event in events] == [
        "notebook",
        "cell",
        "document",
        "ready",
    ]
    assert events[0]["data"]["notebook"]["operations"] == ["notebook.edit"]
    request = edit(events)
    response = await send(bridge, request)
    assert response["status"] == 200
    assert response["body"]["document"] == events[-1]["data"]["document"]
    assert [event["event"] for event in events[-2:]] == ["cell", "document"]
    assert all(
        event["data"]["request_id"] == "edit-1" for event in events[-2:]
    )
    assert list(bridge.session.app_manager.app.cell_manager.codes()) == [
        "x = 2"
    ]
    count = len(events)
    assert await send(bridge, request) == response
    assert len(events) == count
    # A call dispatched directly shares the worker's retry receipts.
    direct = await dispatch(
        bridge.notebook.mutations,
        bridge.notebook,
        msgspec.json.decode(json.dumps(request), type=EditCall),
    )
    assert msgspec.json.decode(msgspec.json.encode(direct)) == [
        response["status"],
        response["body"],
    ]
    assert len(events) == count
    conflict = await send(bridge, edit(events, "x = 3"))
    assert conflict["body"]["type"].endswith("/conflict")
    assert list(bridge.session.app_manager.app.cell_manager.codes()) == [
        "x = 2"
    ]


async def test_atomic_conflict_and_kernel_update(bridge):
    events = await snapshot(bridge)
    instantiate(bridge.session, auto_instantiate=False)
    queue = bridge.session._queue_manager.control_queue
    assert isinstance(queue.get_nowait(), CreateNotebookCommand)
    await send(bridge, edit(events))
    update = queue.get_nowait()
    assert isinstance(update, EditCellsCommand)
    cell_id = events[1]["data"]["cell"]["id"]
    assert update.codes == {cell_id: "x = 2"}
    request = edit(events, "x = 3", request_id="conflict")
    request["body"]["changes"].insert(
        0,
        {
            "kind": "put_cell",
            "base_etag": None,
            "after": cell_id,
            "cell": {"id": "new", "code": "y = 1"},
        },
    )
    result = await send(bridge, request)
    assert result["status"] == 409
    assert result["body"]["edit"]["change"] == 1
    assert result["body"]["edit"]["cell"]["code"] == "x = 2"
    assert list(bridge.session.app_manager.app.cell_manager.codes()) == [
        "x = 2"
    ]
    assert queue.empty()


async def test_edit_before_instantiation(bridge):
    events = await snapshot(bridge)
    await send(bridge, edit(events))
    queue = bridge.session._queue_manager.control_queue
    assert queue.empty()
    instantiate(bridge.session, auto_instantiate=False)
    command = queue.get_nowait()
    assert isinstance(command, CreateNotebookCommand)
    assert [request.code for request in command.execution_requests] == [
        "x = 2"
    ]
    assert queue.empty()


async def test_resume_and_independent_unsubscribe(bridge):
    first = await snapshot(bridge, "first")
    cursor = first[-1]["id"]
    await send(bridge, edit(first))
    second = await snapshot(bridge, "second", cursor)
    assert [event["event"] for event in second] == [
        "cell",
        "document",
        "ready",
    ]
    bridge.notebook.unsubscribe("first")
    count = len(first)
    await send(bridge, edit(second, "x = 3", request_id="edit-2"))
    assert len(first) == count
    assert second[-2]["data"]["cell"]["code"] == "x = 3"
    reset = await snapshot(bridge, "third", "another-host")
    assert [event["event"] for event in reset] == [
        "reset",
        "notebook",
        "cell",
        "document",
        "ready",
    ]
    bridge.close()
    with pytest.raises(RuntimeError, match="closed"):
        await snapshot(bridge)
    assert bridge.notebook._subscriptions == {}


async def test_permissions_and_unsupported_operations(bridge):
    bridge.session.mode = SessionMode.RUN
    events = await snapshot(bridge)
    assert events[0]["data"]["notebook"]["operations"] == []
    request = edit(events)
    assert (await send(bridge, request))["status"] == 403
    save = {**request, "operation": "notebook.save", "body": {}}
    assert (await send(bridge, save))["status"] == 501


async def test_invalid_calls(bridge):
    request = edit(await snapshot(bridge))
    for invalid in (
        {**request, "body": "not a request"},
        {**request, "operation": "notebook.missing"},
        {**request, "params": {}},
    ):
        reply = await send(bridge, invalid)
        assert reply["status"] == 400
        assert reply["body"]["type"].endswith("/invalid-request")
    assert json.loads(await bridge.notebook.call("{"))["status"] == 400
    other = {**request, "params": {"notebook_id": "elsewhere"}}
    assert (await send(bridge, other))["status"] == 404


async def test_kernel_ready_follows_the_snapshot(bridge):
    frames = []
    await bridge.notebook.subscribe(
        "reader", None, lambda raw: frames.append(json.loads(raw))
    )
    kinds = [frame["event"] for frame in frames]
    assert kinds[:4] == ["notebook", "cell", "document", "ready"]
    assert set(kinds[4:]) == {"marimo"}
    kernel_ready = frames[4]["data"]["marimo"]
    assert kernel_ready["op"] == "kernel-ready"
    assert kernel_ready["codes"] == ["x = 1"]
    assert kernel_ready["resumed"] is False


async def test_a_later_subscription_resumes_with_retained_notifications(
    bridge,
):
    session = bridge.session
    session.instantiated = True
    variables = VariablesNotification(
        variables=[
            VariableDeclarationNotification(
                name="x", declared_by=[], used_by=[]
            )
        ]
    )
    session._on_message(serialize_kernel_message(variables))
    notifications = []
    await snapshot(bridge, notifications=notifications)
    assert ops(notifications)[0] == "kernel-ready"
    assert notifications[0]["resumed"] is True
    assert "variables" in ops(notifications)


async def test_live_notifications_reach_each_subscription_until_it_closes(
    bridge,
):
    first, second = [], []
    await snapshot(bridge, "first", notifications=first)
    await snapshot(bridge, "second", notifications=second)
    variables = VariablesNotification(variables=[])
    bridge.session._on_message(serialize_kernel_message(variables))
    assert ops(first)[-1] == ops(second)[-1] == "variables"
    bridge.notebook.unsubscribe("first")
    count = len(first)
    bridge.session._on_message(serialize_kernel_message(variables))
    assert len(first) == count
    assert ops(second)[-2:] == ["variables", "variables"]
    bridge.notebook.unsubscribe("second")
    assert bridge.session.consumers == [
        bridge.session.session_view.add_raw_notification
    ]
