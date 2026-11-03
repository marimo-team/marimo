# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import msgspec
import pytest

if TYPE_CHECKING:
    from pathlib import Path

from marimo._ast.app_config import _AppConfig
from marimo._ast.cell import CellConfig
from marimo._config.config import DEFAULT_CONFIG
from marimo._core.calls import EditCall, dispatch
from marimo._messaging.notebook import CreateCell, Transaction
from marimo._messaging.notification import (
    ModelLifecycleNotification,
    ModelOpen,
    NotebookDocumentTransactionNotification,
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
    ModelCommand,
    ModelUpdateMessage,
)
from marimo._runtime.layout.layout import LayoutConfig
from marimo._session.model import SessionMode
from marimo._session.notebook import AppFileManager
from marimo._types.ids import CellId_t, WidgetModelId


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
    assert events[0]["data"]["notebook"]["operations"] == [
        "notebook.edit",
        "notebook.save",
    ]
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
    assert (await send(bridge, save))["status"] == 403


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
    assert "codes" not in kernel_ready
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


async def test_resubscription_preserves_frontend_widget_updates(bridge):
    model_id = WidgetModelId("widget-1")
    await snapshot(bridge)
    bridge.session._on_message(
        serialize_kernel_message(
            ModelLifecycleNotification(
                model_id=model_id,
                message=ModelOpen(
                    state={"value": 1}, buffer_paths=[], buffers=[]
                ),
            )
        )
    )
    bridge.session.put_control_request(
        ModelCommand(
            model_id=model_id,
            message=ModelUpdateMessage(state={"value": 7}, buffer_paths=[]),
            buffers=[],
        )
    )
    bridge.notebook.unsubscribe("reader")
    notifications = []
    await snapshot(bridge, notifications=notifications)

    assert [
        notification
        for notification in notifications
        if notification["op"] == "model-lifecycle"
    ] == [
        {
            "op": "model-lifecycle",
            "model_id": model_id,
            "message": {
                "method": "open",
                "state": {"value": 7},
                "buffer_paths": [],
                "buffers": [],
                "esm_spec": None,
            },
        }
    ]


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
        bridge.session.session_view.add_raw_notification,
        bridge._on_message,
    ]


def save_call(bridge, key="save-1", if_match=None):
    headers = {"idempotency-key": key}
    if if_match is not None:
        headers["if-match"] = if_match
    return {
        "operation": "notebook.save",
        "params": {"notebook_id": bridge.notebook.id},
        "headers": headers,
        "body": {},
    }


async def test_save_keeps_newer_edits_and_kernel_updates(bridge):
    events = await snapshot(bridge)
    instantiate(bridge.session, auto_instantiate=False)
    queue = bridge.session._queue_manager.control_queue
    queue.get_nowait()
    await send(bridge, edit(events))
    queue.get_nowait()
    notebook = await bridge.notebook.host.notebook(bridge.notebook.id)
    saved_revision = notebook.document.etag
    started, release = asyncio.Event(), asyncio.Event()
    writes = []

    async def persist(contents, _filename):
        writes.append(contents)
        started.set()
        await release.wait()

    bridge.notebook.set_persistence(persist)
    request = save_call(bridge)
    saving = asyncio.create_task(send(bridge, request))
    await started.wait()
    # A second subscriber observes the updated cell's current etag.
    await send(
        bridge, edit(await snapshot(bridge, "editor"), "x = 3", "edit-2")
    )
    update = queue.get_nowait()
    assert isinstance(update, EditCellsCommand)
    assert list(update.codes.values()) == ["x = 3"]
    release.set()
    reply = await saving
    assert reply["status"] == 200
    assert reply["body"]["document"]["saved_etag"] == saved_revision
    assert notebook.document.etag != notebook.saved_etag
    assert list(bridge.session.app_manager.app.cell_manager.codes()) == [
        "x = 3"
    ]
    assert len(writes) == 1
    assert "x = 2" in writes[0]
    assert "x = 3" not in writes[0]
    assert queue.empty()
    # A lost reply retries the same save, rather than saving the newer document.
    assert await send(bridge, request) == reply
    assert len(writes) == 1


async def test_failed_save_stays_dirty_and_can_retry(bridge):
    events = await snapshot(bridge)
    await send(bridge, edit(events))
    notebook = await bridge.notebook.host.notebook(bridge.notebook.id)
    saved = notebook.saved_etag
    persist = AsyncMock(side_effect=OSError("storage full"))
    bridge.notebook.set_persistence(persist)
    request = save_call(bridge)
    count = len(events)
    failed = await send(bridge, request)
    assert failed["status"] == 409
    assert "storage full" in failed["body"]["detail"]
    assert notebook.saved_etag == saved != notebook.document.etag
    assert len(events) == count
    persist.side_effect = None
    assert (await send(bridge, request))["status"] == 200
    assert notebook.saved_etag == notebook.document.etag
    assert persist.await_count == 2


async def test_save_serializes_writes_and_checks_revision_after_waiting(
    bridge,
):
    events = await snapshot(bridge)
    notebook = await bridge.notebook.host.notebook(bridge.notebook.id)
    original = notebook.document.etag
    started, release = asyncio.Event(), asyncio.Event()
    writes = []

    async def persist(contents, _filename):
        writes.append(contents)
        started.set()
        await release.wait()

    bridge.notebook.set_persistence(persist)
    first = asyncio.create_task(send(bridge, save_call(bridge)))
    await started.wait()
    stale = asyncio.create_task(
        send(bridge, save_call(bridge, "stale", original))
    )
    await send(bridge, edit(events))
    second = asyncio.create_task(send(bridge, save_call(bridge, "save-2")))
    await asyncio.sleep(0)
    assert len(writes) == 1
    release.set()
    assert (await first)["status"] == 200
    assert (await stale)["status"] == 409
    assert (await second)["status"] == 200
    assert len(writes) == 2
    assert "x = 2" in writes[1]
    assert notebook.saved_etag == notebook.document.etag


async def test_host_edits_config_layout_and_reload(bridge):
    events = await snapshot(bridge)
    cell = next(e["data"]["cell"] for e in events if e["event"] == "cell")
    edited = await send(
        bridge,
        {
            "operation": "notebook.edit",
            "params": {"notebook_id": bridge.notebook.id},
            "headers": {"idempotency-key": "edit-1"},
            "body": {
                "changes": [
                    {
                        "kind": "put_cell",
                        "base_etag": cell["etag"],
                        "cell": {
                            "id": cell["id"],
                            "code": "x = 9",
                            "name": "example",
                            "config": cell["config"],
                        },
                    },
                    {
                        "kind": "put_cell",
                        "base_etag": None,
                        "before": cell["id"],
                        "cell": {"id": "new", "code": "y = 2"},
                    },
                ]
            },
        },
    )
    assert edited["status"] == 200, edited
    await bridge.save_app_config(json.dumps({"config": {"width": "full"}}))
    layout = {"type": "slides", "data": {"slides": [[cell["id"]]]}}
    await bridge.notebook.set_layout(json.dumps(layout))
    path = bridge.session.app_manager.filename

    async def persist(contents, filename):
        from pathlib import Path

        await asyncio.to_thread(Path(filename).write_text, contents)

    bridge.notebook.set_persistence(persist)
    assert (await send(bridge, save_call(bridge)))["status"] == 200
    restored = AppFileManager(path)
    assert list(restored.app.cell_manager.codes()) == ["y = 2", "x = 9"]
    assert list(restored.app.cell_manager.names()) == ["_", "example"]
    assert restored.app.config.width == "full"
    assert restored.read_layout_config() == LayoutConfig(**layout)
    deleted = await send(
        bridge,
        {
            "operation": "notebook.edit",
            "params": {"notebook_id": bridge.notebook.id},
            "headers": {"idempotency-key": "edit-2"},
            "body": {
                "changes": [
                    {
                        "kind": "delete_cell",
                        "id": "new",
                        "base_etag": edited["body"]["cells"]["new"]["etag"],
                    }
                ]
            },
        },
    )
    assert deleted["status"] == 200, deleted
    assert list(bridge.session.app_manager.app.cell_manager.codes()) == [
        "x = 9"
    ]


async def test_save_includes_kernel_document_edits(bridge):
    await snapshot(bridge)
    persist = AsyncMock()
    bridge.notebook.set_persistence(persist)
    bridge.session._on_message(
        serialize_kernel_message(
            NotebookDocumentTransactionNotification(
                transaction=Transaction(
                    changes=(
                        CreateCell(
                            cell_id=CellId_t("kernel-cell"),
                            code="y = 8",
                            name="_",
                            config=CellConfig(),
                        ),
                    ),
                    source="kernel",
                )
            )
        )
    )
    assert (await send(bridge, save_call(bridge)))["status"] == 200
    contents, _filename = persist.call_args.args
    assert "y = 8" in contents
    assert list(bridge.session.app_manager.app.cell_manager.codes()) == [
        "x = 1",
        "y = 8",
    ]
    assert bridge.session._queue_manager.control_queue.empty()
