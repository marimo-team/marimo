# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from marimo._config.manager import get_default_config_manager
from marimo._host import protocol
from marimo._host.host import Host
from marimo._host.model import (
    Failed,
    HostState,
    Indexed,
    Notebook,
    Project,
    Running,
    Runtime,
    Terminating,
)
from marimo._server.host.runtime import SessionManagerRuntime
from marimo._server.lsp import LspServer
from marimo._server.session_manager import SessionManager
from marimo._server.workspace import EmptyWorkspace
from marimo._session.consumer import SessionConsumer
from marimo._session.model import ConnectionState, SessionMode
from marimo._types.ids import (
    ConsumerId,
    NotebookId,
    ProjectId,
    RuntimeId,
    SessionId,
)
from tests._server.host.drive import wait_for

if TYPE_CHECKING:
    from marimo._host.stream import Event
    from marimo._host.transitions import StartRuntime
    from marimo._messaging.types import KernelMessage
    from marimo._session.events import SessionEventBus
    from marimo._session.types import Session as ManagerSession

NOW = datetime(2026, 10, 1, 9, 14, 2, tzinfo=timezone.utc)
PROJECT = ProjectId("p1")
NOTEBOOK = NotebookId("n1")
RUNTIME = RuntimeId("rt-1")

NOTEBOOK_SOURCE = """import marimo

app = marimo.App()


@app.cell
def _():
    x = 1
    return (x,)


if __name__ == "__main__":
    app.run()
"""


class Tab(SessionConsumer):
    def __init__(self, consumer_id: str) -> None:
        self._id = ConsumerId(consumer_id)

    @property
    def consumer_id(self) -> ConsumerId:
        return self._id

    def notify(self, notification: KernelMessage) -> None:
        del notification

    def connection_state(self) -> ConnectionState:
        return ConnectionState.OPEN

    def on_attach(
        self, session: ManagerSession, event_bus: SessionEventBus
    ) -> None:
        del session, event_bus

    def on_detach(self) -> None:
        pass


@pytest.fixture
def notebook_path(tmp_path: Path) -> Path:
    path = tmp_path / "forecasts.py"
    path.write_text(NOTEBOOK_SOURCE)
    return path


@pytest.fixture
def manager() -> SessionManager:
    return SessionManager(
        workspace=EmptyWorkspace(),
        mode=SessionMode.EDIT,
        quiet=True,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )


def make_host(
    manager: SessionManager, notebook_path: Path
) -> tuple[Host, list[Event]]:
    project = Project(PROJECT, "project", notebook_path.parent, Indexed())
    notebook = Notebook(
        NOTEBOOK, PROJECT, "forecasts", Path(notebook_path.name), None
    )
    state = HostState().with_project(project).with_notebook(notebook)
    runtime = SessionManagerRuntime(manager)
    host = Host(state, runtime, operations=["runtime.start"])
    runtime.bind(host)
    received: list[Event] = []
    host.subscribe(received.append)
    return host, received


def start() -> StartRuntime:
    from marimo._host.transitions import StartRuntime

    return StartRuntime(NOTEBOOK, RUNTIME, NOW, sandbox=False)


def runtime_of(host: Host) -> Runtime | None:
    return host.state.notebooks[NOTEBOOK].runtime


def statuses(received: list[Event]) -> list[str]:
    return [
        e.data.runtime.status
        for e in received
        if isinstance(e.data, protocol.RuntimeMessage)
    ]


async def test_a_host_started_runtime_runs_attaches_and_stops(
    manager: SessionManager, notebook_path: Path
) -> None:
    host, received = make_host(manager, notebook_path)
    try:
        host.command(start(), request_id="r1")
        await wait_for(lambda: isinstance(runtime_of(host).lifecycle, Running))  # type: ignore[union-attr]

        managed = manager.get_session_by_file_key(str(notebook_path))
        assert managed is not None
        assert managed.room.main_consumer is None

        tab = Tab("tab")
        managed.connect_consumer(tab, main=True)
        [attachment] = host.state.notebooks[NOTEBOOK].attachments.values()
        assert attachment.kind == "browser"

        managed.disconnect_consumer(tab)
        assert host.state.notebooks[NOTEBOOK].attachments == {}

        from marimo._host.transitions import StopRuntime

        host.command(StopRuntime(NOTEBOOK), request_id="r2")
        assert runtime_of(host) is None
        assert manager.sessions == {}
        assert statuses(received) == ["starting", "running", "terminating"]
        assert received[-1].name == "runtime.removed"
    finally:
        manager.close_all_sessions()


async def test_a_browser_started_session_is_published_as_a_runtime(
    manager: SessionManager, notebook_path: Path
) -> None:
    host, _ = make_host(manager, notebook_path)
    browser_id = SessionId("browser")
    try:
        managed = await manager.create_session(
            browser_id,
            Tab("tab"),
            query_params={},
            file_key=str(notebook_path),
            auto_instantiate=False,
        )
        await wait_for(
            lambda: (
                isinstance(runtime_of(host).lifecycle, Running)  # type: ignore[union-attr]
                and len(host.state.notebooks[NOTEBOOK].attachments) == 1
            )
        )
        assert runtime_of(host).generation == 0  # type: ignore[union-attr]
        assert manager.get_session(browser_id) is managed

        # The user closes it from the browser side: the kernel is gone,
        # the browser's attachment with it, and the runtime has failed.
        manager.close_session(browser_id)
        await wait_for(lambda: isinstance(runtime_of(host).lifecycle, Failed))  # type: ignore[union-attr]
        assert host.state.notebooks[NOTEBOOK].attachments == {}
    finally:
        manager.close_all_sessions()


async def test_stop_during_startup_closes_the_kernel_on_arrival(
    manager: SessionManager, notebook_path: Path
) -> None:
    host, _ = make_host(manager, notebook_path)
    try:
        from marimo._host.transitions import StopRuntime

        host.command(start())
        host.command(StopRuntime(NOTEBOOK))
        assert isinstance(runtime_of(host).lifecycle, Terminating)  # type: ignore[union-attr]

        await wait_for(lambda: runtime_of(host) is None)
        await wait_for(lambda: manager.sessions == {})
    finally:
        manager.close_all_sessions()


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL is POSIX")
async def test_a_dead_kernel_fails_the_runtime_and_a_new_start_recovers(
    manager: SessionManager, notebook_path: Path
) -> None:
    host, _ = make_host(manager, notebook_path)
    try:
        host.command(start())
        await wait_for(lambda: isinstance(runtime_of(host).lifecycle, Running))  # type: ignore[union-attr]
        managed = manager.get_session_by_file_key(str(notebook_path))
        assert managed is not None
        pid = managed.kernel_pid()
        assert pid is not None

        os.kill(pid, signal.SIGKILL)
        await wait_for(lambda: isinstance(runtime_of(host).lifecycle, Failed))  # type: ignore[union-attr]
        failed = runtime_of(host)
        assert failed is not None
        assert isinstance(failed.lifecycle, Failed)
        assert failed.lifecycle.reason

        # A failed runtime is stopped, then a fresh one started.
        from marimo._host.transitions import StartRuntime, StopRuntime

        host.command(StopRuntime(NOTEBOOK))
        assert runtime_of(host) is None
        host.command(
            StartRuntime(NOTEBOOK, RuntimeId("rt-2"), NOW, sandbox=False)
        )
        await wait_for(
            lambda: (
                isinstance(runtime_of(host).lifecycle, Running)  # type: ignore[union-attr]
                and runtime_of(host).id == RuntimeId("rt-2")  # type: ignore[union-attr]
            )  # type: ignore[union-attr]
        )
        # Running means a new kernel, not the dead session found again.
        replacement = manager.get_session_by_file_key(str(notebook_path))
        assert replacement is not None
        assert replacement is not managed
        assert replacement.kernel_pid() not in (None, pid)
    finally:
        manager.close_all_sessions()


@pytest.mark.skipif(sys.platform == "win32", reason="SIGKILL is POSIX")
async def test_a_browser_reconnecting_to_a_failed_runtime_replaces_it(
    manager: SessionManager, notebook_path: Path
) -> None:
    host, received = make_host(manager, notebook_path)
    try:
        host.command(start())
        await wait_for(lambda: isinstance(runtime_of(host).lifecycle, Running))  # type: ignore[union-attr]
        managed = manager.get_session_by_file_key(str(notebook_path))
        assert managed is not None
        pid = managed.kernel_pid()
        assert pid is not None
        os.kill(pid, signal.SIGKILL)
        await wait_for(lambda: isinstance(runtime_of(host).lifecycle, Failed))  # type: ignore[union-attr]

        # The user reloads the tab. The connector finds nothing to resume,
        # which sweeps the dead session, and opens a new one.
        browser_id = SessionId("browser")
        assert (
            manager.maybe_resume_session(browser_id, str(notebook_path))
            is None
        )
        fresh = await manager.create_session(
            browser_id,
            Tab("tab"),
            query_params={},
            file_key=str(notebook_path),
            auto_instantiate=False,
        )
        await wait_for(
            lambda: (
                isinstance(runtime_of(host).lifecycle, Running)  # type: ignore[union-attr]
                and len(host.state.notebooks[NOTEBOOK].attachments) == 1
            )
        )
        assert runtime_of(host).id == RuntimeId(fresh.stable_id)  # type: ignore[union-attr]
        assert statuses(received)[-3:] == ["failed", "starting", "running"]
    finally:
        manager.close_all_sessions()


async def test_a_rename_from_the_browser_moves_the_notebook(
    tmp_path: Path,
) -> None:
    from marimo._server.host.index import WorkspaceIndex
    from marimo._server.workspace import DirectoryWorkspace
    from tests._server.host.drive import notebook_id

    forecasts = tmp_path / "forecasts.py"
    forecasts.write_text(NOTEBOOK_SOURCE)
    manager = SessionManager(
        workspace=DirectoryWorkspace(str(tmp_path), include_markdown=False),
        mode=SessionMode.EDIT,
        quiet=True,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )
    runtime = SessionManagerRuntime(manager)
    host = Host(HostState(), runtime, operations=["runtime.start"])
    index = WorkspaceIndex(host, manager.workspace)
    index.refresh()
    runtime.bind(host, index=index)
    before = notebook_id(host, Path("forecasts.py"))
    browser_id = SessionId("browser")
    try:
        await manager.create_session(
            browser_id,
            Tab("tab"),
            query_params={},
            file_key=str(forecasts),
            auto_instantiate=False,
        )
        await wait_for(
            lambda: isinstance(
                host.state.notebooks[before].runtime.lifecycle,  # type: ignore[union-attr]
                Running,
            )
        )

        ok, error = await manager.rename_session(
            browser_id, str(tmp_path / "models" / "forecasts_v2.py")
        )
        assert ok, error
        await wait_for(
            lambda: (
                host.state.notebooks[before].path
                == Path("models") / "forecasts_v2.py"
            )
        )
        assert host.state.notebooks[before].title == "forecasts_v2"
        assert host.state.notebooks[before].runtime is not None
    finally:
        manager.close_all_sessions()


async def test_a_browser_session_on_an_unlisted_file_is_admitted(
    tmp_path: Path,
) -> None:
    from marimo._server.host.index import WorkspaceIndex
    from marimo._server.workspace import DirectoryWorkspace

    manager = SessionManager(
        workspace=DirectoryWorkspace(str(tmp_path), include_markdown=False),
        mode=SessionMode.EDIT,
        quiet=True,
        include_code=True,
        lsp_server=MagicMock(spec=LspServer),
        config_manager=get_default_config_manager(current_path=None),
        cli_args={},
        argv=None,
        auth_token=None,
        redirect_console_to_browser=False,
        ttl_seconds=None,
    )
    runtime = SessionManagerRuntime(manager)
    host = Host(HostState(), runtime, operations=["runtime.start"])
    index = WorkspaceIndex(host, manager.workspace)
    index.refresh()
    runtime.bind(host, index=index)
    assert host.state.notebooks == {}

    later = tmp_path / "later.py"
    later.write_text(NOTEBOOK_SOURCE)
    try:
        await manager.create_session(
            SessionId("browser"),
            Tab("tab"),
            query_params={},
            file_key=str(later),
            auto_instantiate=False,
        )
        await wait_for(
            lambda: any(
                nb.runtime is not None
                and isinstance(nb.runtime.lifecycle, Running)
                for nb in host.state.notebooks.values()
            )
        )
        [notebook] = host.state.notebooks.values()
        assert notebook.path == Path("later.py")
    finally:
        manager.close_all_sessions()
