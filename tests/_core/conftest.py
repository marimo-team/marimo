# Copyright 2026 Marimo. All rights reserved.
"""Host fixtures with a backend that records commands."""

from __future__ import annotations

import pytest

from marimo._core import protocol
from marimo._core.host import Host
from marimo._core.notebook import Notebook
from marimo._core.stream import Event

OPERATIONS = ["notebook.create", "runtime.start", "runtime.run"]


class ScriptedBackend:
    """Records backend commands without executing them."""

    def __init__(self) -> None:
        self.calls: list[tuple[object, ...]] = []

    def start(self, runtime_id: str) -> None:
        self.calls.append(("start", runtime_id))

    def stop(self) -> None:
        self.calls.append(("stop",))

    def run(self, run_id: str, code: str) -> None:
        self.calls.append(("run", run_id, code))

    def interrupt(self, run_id: str) -> None:
        self.calls.append(("interrupt", run_id))


def project(project_id: str = "p1") -> protocol.Project:
    return protocol.Project(
        id=protocol.ProjectId(project_id),
        name="forecasting",
        root="/Users/me/forecasting",
        status="indexed",
        message=None,
        operations=["notebook.create"],
    )


def record(
    notebook_id: str = "n1", path: str = "forecasts.py"
) -> protocol.Notebook:
    return protocol.Notebook(
        id=protocol.NotebookId(notebook_id),
        project_id=protocol.ProjectId("p1"),
        path=path,
        name=path.removesuffix(".py"),
        operations=["runtime.start", "runtime.run"],
        updated_at=None,
    )


@pytest.fixture
def host() -> Host:
    return Host(operations=OPERATIONS)


@pytest.fixture
def backend() -> ScriptedBackend:
    return ScriptedBackend()


@pytest.fixture
def notebook(host: Host, backend: ScriptedBackend) -> Notebook:
    host.update_project(project())
    return host.add_notebook(record(), backend)


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
