# Copyright 2026 Marimo. All rights reserved.
"""Host fixtures with a backend that records commands."""

from __future__ import annotations

import asyncio

import pytest

from marimo._core import backend as be, protocol
from marimo._core.document import Document, DocumentSnapshot, code_hash
from marimo._core.executions import CellExecution, Executions
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.run_log import RetentionPolicy
from marimo._core.stream import Event, Sink

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

    def interrupt(self, run_id: str) -> None:
        self.calls.append(("interrupt", run_id))

    def forget(self, run_id: str) -> None:
        self.calls.append(("forget", run_id))


class ScriptedAnalyzer:
    """Expose snapshots and let tests complete analysis explicitly."""

    def __init__(self) -> None:
        self.requests: list[DocumentSnapshot] = []
        self.pending: asyncio.Queue[
            tuple[
                DocumentSnapshot,
                asyncio.Future[dict[protocol.CellId, protocol.CellAnalysis]],
            ]
        ] = asyncio.Queue()

    async def analyze(
        self, snapshot: DocumentSnapshot
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
        DocumentSnapshot,
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
    return Notebook(
        document or Document(record.id, [], {}),
        Executions(),
        backend or ScriptedBackend(),
        sink,
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
def log(host: Host) -> list[Event]:
    """Collect events published during the test."""
    events: list[Event] = []
    host.subscribe(events.append, notebook_id="n1")
    return events


def names(events: list[Event]) -> list[str]:
    return [e.name for e in events]


def request_ids(events: list[Event]) -> list[object]:
    return [getattr(e.data, "request_id", None) for e in events]


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
    notebook.observe(be.Status(execution, "running"))
    return execution


def finish(notebook: Notebook, execution: protocol.ExecutionId) -> None:
    notebook.observe(
        be.Concluded(
            execution,
            protocol.ValueOutcome(
                protocol.DisplayData(mimetype="text/plain", data="value")
            ),
        )
    )
    notebook.observe(be.Status(execution, "completed"))


def fold(events: list[Event], initial: dict | None = None) -> dict:
    state = dict(initial or {})
    for event in events:
        if event.name == "reset":
            state.clear()
        elif event.kind in {"run", "execution", "console", "display"}:
            if event.name.endswith(".removed"):
                state.pop((event.kind, event.data.id), None)
            else:
                body = getattr(event.data, event.kind)
                state[event.kind, body.id] = body
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
            bindings=(),
            status="completed",
            outcome=protocol.ValueOutcome(
                protocol.DisplayData(mimetype="text/plain", data="42")
            ),
            stale=False if cell_id is not None else None,
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
