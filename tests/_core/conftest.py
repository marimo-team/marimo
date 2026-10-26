# Copyright 2026 Marimo. All rights reserved.
"""Host fixtures with a backend that records commands."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest

from marimo._core import backend as be, protocol, protocol_events
from marimo._core.document import Document, code_hash
from marimo._core.executions import CellExecution, Executions
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.run_log import RetentionPolicy
from marimo._core.stream import RoutedEvent, Sink, event_name

if TYPE_CHECKING:
    from collections.abc import Sequence

OPERATIONS = ["notebook.create", "runtime.start", "runtime.run"]


class ScriptedBackend:
    """Records backend commands without executing them."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def start(self, runtime_id: str) -> None:
        self.calls.append(("start", runtime_id))

    def stop(self, runtime_id: str) -> None:
        self.calls.append(("stop", runtime_id))

    def run(self, run_id: str, code: str) -> None:
        self.calls.append(("run", run_id, code))

    def run_cells(
        self, run_id: str, document: Document, cell_ids: Sequence[str]
    ) -> None:
        self.calls.append(
            ("run_cells", run_id, document.etag, tuple(cell_ids))
        )

    def interrupt(self, run_id: str) -> None:
        self.calls.append(("interrupt", run_id))

    def forget(self, run_id: str) -> None:
        self.calls.append(("forget", run_id))


class ScriptedAnalyzer:
    """Expose snapshots and let tests complete analysis explicitly."""

    def __init__(self) -> None:
        self.requests: list[Document] = []
        self.pending: asyncio.Queue[
            tuple[
                Document,
                asyncio.Future[dict[protocol.CellId, protocol.CellAnalysis]],
            ]
        ] = asyncio.Queue()

    async def analyze(
        self, snapshot: Document
    ) -> dict[protocol.CellId, protocol.CellAnalysis]:
        result: asyncio.Future[
            dict[protocol.CellId, protocol.CellAnalysis]
        ] = asyncio.get_running_loop().create_future()
        self.requests.append(snapshot)
        self.pending.put_nowait((snapshot, result))
        return await result

    async def next_request(
        self,
    ) -> tuple[
        Document,
        asyncio.Future[dict[protocol.CellId, protocol.CellAnalysis]],
    ]:
        return await asyncio.wait_for(self.pending.get(), timeout=5)


def runtime_id_of(notebook: Notebook) -> protocol.RuntimeId:
    """The current runtime's ID, for reports about it."""
    assert notebook.runtime is not None
    return notebook.runtime.id


def project(project_id: str = "p1") -> protocol.Project:
    return protocol.Project(
        id=protocol.ProjectId(project_id),
        name="forecasting",
        root="/Users/me/forecasting",
        status="indexed",
        message=None,
        operations=("notebook.create",),
    )


def record(
    notebook_id: str = "n1", path: str = "forecasts.py"
) -> protocol.Notebook:
    return protocol.Notebook(
        id=protocol.NotebookId(notebook_id),
        project_id=protocol.ProjectId("p1"),
        path=path,
        name=path.removesuffix(".py"),
        operations=("runtime.start", "runtime.run"),
        updated_at=None,
    )


def make_notebook(
    record: protocol.Notebook,
    sink: Sink,
    backend: ScriptedBackend | None = None,
    *,
    document: Document | None = None,
    analyzer: ScriptedAnalyzer | None = None,
) -> Notebook:
    document = document if document is not None else Document([], {})
    return Notebook(
        record.id,
        document,
        Executions(),
        backend or ScriptedBackend(),
        sink,
        saved_etag=document.etag,
        analyzer=analyzer,
    )


async def add_notebook(
    host: Host,
    record: protocol.Notebook,
    backend: ScriptedBackend,
    *,
    document: Document | None = None,
    analyzer: ScriptedAnalyzer | None = None,
) -> Notebook:
    host.add_notebook(
        record,
        lambda current, sink: make_notebook(
            current, sink, backend, document=document, analyzer=analyzer
        ),
    )
    return await host.notebook(record.id)


@pytest.fixture
def host() -> Host:
    return Host(operations=OPERATIONS)


@pytest.fixture
def backend() -> ScriptedBackend:
    return ScriptedBackend()


@pytest.fixture
async def notebook(host: Host, backend: ScriptedBackend) -> Notebook:
    host.update_project(project())
    return await add_notebook(host, record(), backend)


@pytest.fixture
def log(host: Host) -> list[RoutedEvent]:
    """Collect events published during the test."""
    events: list[RoutedEvent] = []
    host.subscribe(events.append, notebook_id="n1")
    return events


def names(events: list[RoutedEvent]) -> list[str]:
    return [event_name(e.event) for e in events]


def request_ids(events: list[RoutedEvent]) -> list[object]:
    return [getattr(e.event.data, "request_id", None) for e in events]


class Clock:
    now = 0.0

    def __call__(self) -> float:
        return self.now


async def host_at(clock: Clock, history: int = 1000) -> tuple[Host, Notebook]:
    host = Host(
        operations=[],
        history=history,
        clock=clock,
        retention=RetentionPolicy(ephemeral_seconds=10),
    )
    host.update_project(project())
    notebook = await add_notebook(host, record(), ScriptedBackend())
    notebook.adopt(lambda _: None)
    notebook.observe(be.Running(runtime_id_of(notebook)))
    return host, notebook


def plan(
    notebook: Notebook, run: protocol.Run, eid: str, cell: str | None = None
) -> protocol.ExecutionId:
    execution = protocol.ExecutionId(eid)
    notebook.observe(
        be.Planned(
            run.id,
            (
                be.PlannedExecution(
                    execution, cell, "hash", "code" if cell is None else None
                ),
            ),
        )
    )
    notebook.observe(be.Started(execution))
    return execution


def finish(notebook: Notebook, execution: protocol.ExecutionId) -> None:
    notebook.observe(
        be.Completed(
            execution,
            protocol.ValueOutcome(
                protocol.DisplayData(mimetype="text/plain", data="value")
            ),
        )
    )


def fold(events: list[RoutedEvent], initial: dict | None = None) -> dict:
    state = dict(initial or {})
    for routed in events:
        event = routed.event
        if isinstance(event, protocol.ResetEvent):
            state.clear()
        elif isinstance(
            event,
            (
                protocol.RunEvent,
                protocol.ExecutionEvent,
                protocol.ConsoleEvent,
                protocol.DisplayEvent,
            ),
        ):
            body = protocol_events.body(event)
            state[event_name(event), body.id] = body
        elif isinstance(
            event,
            (
                protocol.RunRemovedEvent,
                protocol.ExecutionRemovedEvent,
                protocol.ConsoleRemovedEvent,
                protocol.DisplayRemovedEvent,
            ),
        ):
            state.pop(
                (event_name(event).removesuffix(".removed"), event.data.id),
                None,
            )
    return state


def retained_execution(
    cell_id: str | None = "c1", run_id: str | None = None
) -> CellExecution:
    """A completed execution with one console item, as a store retains it."""
    execution_id = protocol.ExecutionId("restored")
    return CellExecution(
        protocol.Execution(
            id=execution_id,
            run_id=None if run_id is None else protocol.RunId(run_id),
            runtime_id=None,
            caused_by=None,
            cell_id=None if cell_id is None else protocol.CellId(cell_id),
            code="42" if cell_id is None else None,
            code_hash=code_hash("42"),
            depends_on={},
            status="completed",
            outcome=protocol.ValueOutcome(
                protocol.DisplayData(mimetype="text/plain", data="42")
            ),
            started_at=None,
            completed_at=None,
        ),
        (
            protocol.Console(
                execution_id,
                protocol.ItemId("restored-output"),
                "stdout",
                0,
                "hello",
            ),
        ),
    )
