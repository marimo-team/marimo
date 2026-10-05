# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import msgspec
import pytest

from marimo._host import protocol
from marimo._host.host import Host
from marimo._host.model import (
    Attachment,
    HostState,
    Indexed,
    Notebook,
    Project,
)
from marimo._host.stream import Event
from marimo._host.transitions import (
    Action,
    Attach,
    Conflict,
    KernelExited,
    KernelReady,
    NotebookSeen,
    RestartRuntime,
    StartKernel,
    StartRuntime,
    StopKernel,
    StopRuntime,
)
from marimo._types.ids import AttachmentId, NotebookId, ProjectId, RuntimeId

START = datetime(2026, 10, 1, 9, 14, 2, tzinfo=timezone.utc)
PROJECT = ProjectId("p1")
NOTEBOOK = NotebookId("n1")
RUNTIME = RuntimeId("r1")


class FakeRuntime:
    def __init__(self) -> None:
        self.performed: list[Action] = []

    def perform(self, action: Action) -> None:
        self.performed.append(action)


def make_host(history: int = 1000) -> tuple[Host, FakeRuntime, list[Event]]:
    project = Project(PROJECT, "forecasting", Path("/p"), Indexed())
    notebook = Notebook(
        NOTEBOOK, PROJECT, "forecasts", Path("forecasts.py"), START
    )
    state = HostState().with_project(project).with_notebook(notebook)
    runtime = FakeRuntime()
    host = Host(
        state,
        runtime,
        operations=["runtime.start"],
        history=history,
    )
    received: list[Event] = []
    host.subscribe(received.append)
    return host, runtime, received


def start() -> StartRuntime:
    return StartRuntime(NOTEBOOK, RUNTIME, START, sandbox=True)


def runtime_of(event: Event) -> protocol.Runtime:
    assert isinstance(event.data, protocol.RuntimeMessage)
    return event.data.runtime


def test_a_runtime_lifetime_as_a_client_sees_it() -> None:
    host, runtime, received = make_host()

    host.command(start(), request_id="r1")
    host.observe(KernelReady(RUNTIME, 0, "0.25.0"))
    attachment = Attachment(AttachmentId("a1"), "browser", "Chrome", START)
    host.command(Attach(NOTEBOOK, attachment))
    host.command(StopRuntime(NOTEBOOK), request_id="r2")
    host.observe(KernelExited(RUNTIME, 0, "stopped"))

    assert [(e.id, e.name) for e in received] == [
        (1, "runtime"),
        (2, "runtime"),
        (3, "attachment"),
        (4, "runtime"),
        (5, "runtime.removed"),
    ]
    statuses = [runtime_of(e).status for e in received if e.name == "runtime"]
    assert statuses == ["starting", "running", "terminating"]
    assert runtime.performed == [
        StartKernel(NOTEBOOK, RUNTIME, generation=0, sandbox=True),
        StopKernel(RUNTIME, generation=0),
    ]
    # The attachment belongs to the notebook and outlives the runtime.
    notebook = host.state.notebooks[NOTEBOOK]
    assert notebook.runtime is None
    assert list(notebook.attachments) == ["a1"]


def test_request_id_follows_the_runtime_until_it_settles() -> None:
    host, _, received = make_host()

    host.command(start(), request_id="k1")
    host.observe(KernelReady(RUNTIME, 0, "0.25.0"))
    host.command(RestartRuntime(NOTEBOOK))
    host.observe(KernelReady(RUNTIME, 1, "0.25.0"))
    host.command(StopRuntime(NOTEBOOK), request_id="k2")
    host.observe(KernelExited(RUNTIME, 1, "stopped"))

    def request_id(event: Event) -> str | None:
        assert event.data is not None
        value = event.data.request_id
        return None if value is msgspec.UNSET else value

    assert [(e.name, request_id(e)) for e in received] == [
        ("runtime", "k1"),  # starting
        ("runtime", "k1"),  # running: k1 is done after this
        ("runtime", None),  # restart without a request id
        ("runtime", None),
        ("runtime", "k2"),  # terminating
        ("runtime.removed", "k2"),
    ]


def test_a_connection_catches_up_from_its_cursor() -> None:
    host, _, received = make_host()
    host.command(start())
    host.observe(KernelReady(RUNTIME, 0, "0.25.0"))
    assert [e.id for e in received] == [1, 2]
    assert all(e.data.time.tzinfo is timezone.utc for e in received)  # type: ignore[union-attr]

    fresh = host.events()
    assert [e.name for e in fresh] == [
        "host",
        "project",
        "notebook",
        "runtime",
        "ready",
    ]
    assert fresh[-1].id == 2
    assert all(e.id is None for e in fresh[:-1])

    resumed = host.events(cursor=1)
    assert [(e.id, e.name) for e in resumed] == [(2, "runtime"), (2, "ready")]
    assert host.events(cursor=2) == [Event("ready", id=2)]


def test_a_notebook_stream_sees_only_its_notebook() -> None:
    host, _, _ = make_host()
    host.command(start())
    other = Notebook(NotebookId("n2"), PROJECT, "other", Path("o.py"), START)
    host.observe(NotebookSeen(other))

    own = host.events(notebook_id=NOTEBOOK)
    assert [e.name for e in own] == ["notebook", "runtime", "ready"]

    resumed = host.events(cursor=1, notebook_id=NOTEBOOK)
    assert [e.name for e in resumed] == ["ready"]  # n2's arrival is not ours


def test_a_cursor_older_than_the_history_gets_a_reset() -> None:
    host, _, _ = make_host(history=1)
    host.command(start())
    host.observe(KernelReady(RUNTIME, 0, "0.25.0"))

    events = host.events(cursor=0)
    assert [e.name for e in events] == [
        "reset",
        "host",
        "project",
        "notebook",
        "runtime",
        "ready",
    ]


def test_a_refused_command_publishes_nothing_and_leaves_state_alone() -> None:
    host, runtime, received = make_host()
    host.command(start())
    host.command(StopRuntime(NOTEBOOK))
    before = host.state

    with pytest.raises(Conflict):
        host.command(RestartRuntime(NOTEBOOK))

    assert host.state is before
    assert len(received) == 2
    assert len(runtime.performed) == 2


def test_a_failing_listener_interrupts_nothing() -> None:
    host, runtime, received = make_host()
    late: list[Event] = []

    def broken(event: Event) -> None:
        raise RuntimeError(f"cannot handle {event.name}")

    host.subscribe(broken)
    host.subscribe(late.append)

    host.command(start())

    assert host.state.notebooks[NOTEBOOK].runtime is not None
    assert [e.name for e in received] == ["runtime"]
    assert [e.name for e in late] == ["runtime"]
    assert runtime.performed == [
        StartKernel(NOTEBOOK, RUNTIME, generation=0, sandbox=True)
    ]


def test_stale_observations_publish_nothing() -> None:
    host, _, received = make_host()
    host.command(start())
    host.observe(KernelReady(RUNTIME, 0, "0.25.0"))
    host.command(RestartRuntime(NOTEBOOK))
    count = len(received)

    host.observe(KernelExited(RUNTIME, 0, "late"))
    host.observe(KernelReady(RuntimeId("other"), 0, None))

    assert len(received) == count
