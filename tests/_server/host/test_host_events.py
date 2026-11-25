# Copyright 2026 Marimo. All rights reserved.
"""Typed envelopes preserve transport framing and event routing."""

from __future__ import annotations

import json
from typing import Any

import pytest

from marimo._core import protocol
from marimo._core.stream import RoutedEvent, Stream, snapshot_event
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.notebook.changes import Transaction
from marimo._messaging.notification import (
    CallbackOutputNotification,
    CellNotification,
    CompletedRunNotification,
    ExecutionNotification,
    InterruptedNotification,
    NotebookDocumentTransactionNotification,
    NotificationMessage,
    PdbOutputNotification,
    VariablesNotification,
    VariableValuesNotification,
)
from marimo._server.host.api import _frame
from marimo._server.host.events import (
    EditorNotifications,
    MarimoEvent,
    MarimoMessage,
    notification_event,
    serialize_event,
)
from marimo._session.state.session_view import SessionView
from marimo._types.ids import CellId_t


def test_execution_clear_removes_only_command_transcripts_the_editor_received() -> (
    None
):
    cell = CellId_t("cell")
    view = SessionView()
    editor, viewer = EditorNotifications(), EditorNotifications()
    view.add_notification(
        ExecutionNotification("execution", cell, "run", "planned")
    )
    callback = CallbackOutputNotification(
        cell, [CellOutput.stdout("callback")]
    )
    debugger = PdbOutputNotification(cell, [CellOutput.stdout("debugger")])
    for notification in (callback, debugger):
        view.add_notification(notification)
        list(editor.events(None, notification, view))
    list(viewer.events(None, callback, view))

    clear = CellNotification(cell, execution_id="execution", console=[])
    view.add_notification(clear)
    assert {
        event.event.data.marimo.name
        for event in editor.events(None, clear, view)
        if isinstance(event.event, MarimoEvent)
    } == {"callback-output", "pdb-output"}
    assert [
        event.event.data.marimo
        for event in viewer.events(None, clear, view)
        if isinstance(event.event, MarimoEvent)
    ] == [CallbackOutputNotification(cell, [], replace=True)]
    assert not list(editor.events(None, clear, view))
    assert view.get_cell_console_outputs([cell]) == {}
    assert view.debugger_notifications() == [
        PdbOutputNotification(cell, [], replace=True)
    ]


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        (
            snapshot_event(protocol.Host(operations=("runtime.start",))),
            {
                "event": "host",
                "data": {"host": {"operations": ["runtime.start"]}},
            },
        ),
        (
            RoutedEvent(protocol.ReadyEvent(data={}, id="42")),
            {"event": "ready", "data": {}, "id": "42"},
        ),
        (
            RoutedEvent(protocol.ResetEvent(data={})),
            {"event": "reset", "data": {}},
        ),
        (
            notification_event(
                protocol.NotebookId("n1"),
                CompletedRunNotification(run_id="r1"),
            ),
            {
                "event": "marimo",
                "data": {
                    "marimo": {
                        "op": "completed-run",
                        "run_id": "r1",
                        "outcome": "succeeded",
                        "error": None,
                    }
                },
            },
        ),
    ],
)
def test_transports_encode_the_same_envelope(
    event: RoutedEvent, expected: dict[str, Any]
) -> None:
    assert json.loads(serialize_event(event)) == expected
    frame = _frame(event).decode()
    assert frame.endswith("\n\n")
    fields = dict(line.split(": ", 1) for line in frame.strip().splitlines())
    assert {**fields, "data": json.loads(fields["data"])} == expected


def test_extension_routing_and_control_filters() -> None:
    notebook_id = protocol.NotebookId("n1")
    event = notification_event(
        notebook_id, CompletedRunNotification(run_id="r1")
    )
    assert event is not None
    assert [event.visible_in(scope) for scope in (None, "n1", "n2")] == [
        False,
        True,
        False,
    ]
    assert event.wanted({"marimo"}, "r1")
    assert not event.wanted({"cell"}, "r1")
    assert not event.wanted({"marimo"}, "r2")

    stream = Stream()
    recorded = stream.append(event)
    assert recorded.event == MarimoEvent(
        data=MarimoMessage(CompletedRunNotification(run_id="r1")),
        id=stream.cursor_at(1),
    )
    assert stream.since(0) == [recorded]

    for wire in (
        protocol.ReadyEvent(data={}, id="1"),
        protocol.ResetEvent(data={}),
    ):
        control = RoutedEvent(wire, notebook_id=notebook_id)
        assert control.wanted({"cell"}, "other-run")
        assert not control.visible_in(notebook_id)


@pytest.mark.parametrize(
    "notification",
    [
        NotebookDocumentTransactionNotification(
            transaction=Transaction(changes=(), source="code-mode")
        ),
        InterruptedNotification(run_id="run"),
        VariablesNotification(variables=[]),
        VariableValuesNotification(variables=[]),
    ],
)
def test_kernel_notifications_stay_internal(
    notification: NotificationMessage,
) -> None:
    assert notification_event(None, notification) is None
    assert not list(EditorNotifications().events(None, notification))


def test_editor_does_not_forward_cell_status_changes() -> None:
    editor = EditorNotifications()
    cell = CellId_t("cell")
    assert (
        list(
            editor.events(
                None, CellNotification(cell, status="disabled-transitively")
            )
        )
        == []
    )
