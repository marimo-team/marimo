# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec
import pytest
from msgspec.structs import replace

from marimo._core import backend as be, protocol
from marimo._core.errors import Conflict, NotFound
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import RoutedEvent
from tests._core.conftest import ScriptedBackend, finish, plan


def prompt(notebook: Notebook) -> tuple[protocol.Run, protocol.Input]:
    runtime, _ = notebook.start()
    notebook.observe(be.Running(runtime.id))
    run = notebook.run("input()", request_id="run", request=None)
    execution_id = plan(notebook, run, "execution")
    item = protocol.Input(
        execution_id=execution_id,
        id=protocol.ItemId("prompt"),
        password=True,
        prompt="Password: ",
        seq=0,
        status="pending",
    )
    notebook.observe(be.Produced(item))
    return run, item


def test_answer_is_final_and_never_retained(
    notebook: Notebook,
    backend: ScriptedBackend,
    host: Host,
    log: list[RoutedEvent],
) -> None:
    run, item = prompt(notebook)
    answered = notebook.reply_input(item.id, "secret", request_id="answer")
    assert answered == replace(item, status="answered")
    assert backend.calls[-1] == ("reply_input", item.id, "secret")
    with pytest.raises(Conflict, match="answered"):
        notebook.reply_input(item.id, "second", request_id="again")

    finish(notebook, item.execution_id)
    notebook.observe(be.Done(run.id, "succeeded"))
    assert host.input("n1", item.id) == answered
    input_events = [
        event.event.data
        for event in log
        if isinstance(event.event, protocol.InputEvent)
    ]
    assert [
        (event.input.status, event.request_id) for event in input_events
    ] == [("pending", "run"), ("answered", "answer")]
    snapshot = host._snapshot(protocol.NotebookId("n1"))
    assert answered in [
        event.event.data.input
        for event in snapshot
        if isinstance(event.event, protocol.InputEvent)
    ]
    assert b"secret" not in msgspec.json.encode(
        [event.event for event in [*log, *snapshot]]
    )


@pytest.mark.parametrize(
    "ending", ["complete", "interrupt", "stop", "restart", "exit"]
)
def test_pending_inputs_cancel_before_execution_ends(
    notebook: Notebook, log: list[RoutedEvent], ending: str
) -> None:
    run, item = prompt(notebook)
    if ending == "interrupt":
        notebook.interrupt(run.id, request_id="cancel")
    elif ending == "stop":
        notebook.stop(request_id="cancel")
    elif ending == "restart":
        notebook.restart(request_id="cancel")
    elif ending == "exit":
        assert notebook.runtime is not None
        notebook.observe(be.Exited(notebook.runtime.id, "kernel died"))
    finish(notebook, item.execution_id)

    cancelled = [
        (index, event.event.data)
        for index, event in enumerate(log)
        if isinstance(event.event, protocol.InputEvent)
        and event.event.data.input.status == "cancelled"
    ]
    [(index, message)] = cancelled
    assert message.input == replace(item, status="cancelled")
    assert message.request_id == (
        "cancel" if ending in {"interrupt", "stop", "restart"} else "run"
    )
    assert any(
        isinstance(event.event, protocol.ExecutionEvent)
        and event.event.data.execution.status == "completed"
        for event in log[index + 1 :]
    )
    with pytest.raises((Conflict, NotFound)):
        notebook.reply_input(item.id, "late", request_id="late")
    notebook.observe(be.Produced(replace(item, id=protocol.ItemId("late"))))
    with pytest.raises(NotFound):
        notebook.reply_input(
            protocol.ItemId("late"), "late", request_id="late"
        )
