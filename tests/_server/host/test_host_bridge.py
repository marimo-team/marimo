# Copyright 2026 Marimo. All rights reserved.
"""Session discovery and updates in the host catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._core import protocol
from marimo._core.errors import Conflict
from marimo._core.stream import Event
from marimo._messaging.notification import (
    CompletedRunNotification,
    ExecutionNotification,
    StartupProgressNotification,
)
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.host.bridge import SessionBridge
from marimo._server.models.home import MarimoFile
from marimo._server.workspace import FixedFilesWorkspace
from tests._core.conftest import names
from tests._server.host.conftest import FakeManager, FakeSession

if TYPE_CHECKING:
    from pathlib import Path

    from marimo._session.consumer import SessionConsumer


def prepare(manager: FakeManager, root: Path, *names: str) -> None:
    files = []
    for name in names:
        (root / name).write_text("")
        files.append(MarimoFile(name=name, path=str(root / name)))
    manager.workspace = FixedFilesWorkspace(files, directory=str(root))


async def test_sessions_present_and_created_are_adopted(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py", "b.py")
    existing = FakeSession(str(tmp_path / "a.py"))
    manager.sessions["browser-1"] = existing
    bridge = SessionBridge(manager)  # type: ignore[arg-type]

    bridge.open()

    a = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert a is not None
    runtime = bridge.host.notebook(a.id).runtime
    assert runtime is not None
    assert runtime.status == "running"
    assert existing.consumers[0][1] is False

    created = FakeSession(str(tmp_path / "b.py"))
    await manager.event_bus.emit_session_created(created)  # type: ignore[arg-type]
    b = bridge.index.notebook_for(str(tmp_path / "b.py"))
    assert b is not None
    assert bridge.host.notebook(b.id).runtime is not None

    unknown = FakeSession(str(tmp_path.parent / "elsewhere.py"))
    await manager.event_bus.emit_session_created(unknown)  # type: ignore[arg-type]
    assert unknown.consumers == []
    bridge.close()


async def test_a_subscriber_can_stop_an_adopted_session(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py")
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    notebook = bridge.host.notebook(record.id)
    session = FakeSession(str(tmp_path / "a.py"))
    manager.sessions["browser"] = session

    def stop_on_starting(event: Event) -> None:
        if (
            isinstance(event.data, protocol.RuntimeMessage)
            and event.data.runtime.status == "starting"
        ):
            notebook.stop()

    bridge.host.subscribe(stop_on_starting, types={"runtime"})

    await manager.event_bus.emit_session_created(session)  # type: ignore[arg-type]

    assert (session.closed, notebook.runtime, manager.sessions) == (
        True,
        None,
        {},
    )
    bridge.close()


@pytest.mark.parametrize("attached", [False, True])
async def test_failed_adoption_detaches_without_closing_the_session(
    manager: FakeManager,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attached: bool,
) -> None:
    prepare(manager, tmp_path, "a.py")
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    notebook = bridge.host.notebook(record.id)
    session = FakeSession(str(tmp_path / "a.py"))
    connect = session.connect_consumer

    def fail(consumer: SessionConsumer, *, main: bool) -> None:
        if attached:
            connect(consumer, main=main)
        raise RuntimeError("cannot attach")

    monkeypatch.setattr(session, "connect_consumer", fail)

    await manager.event_bus.emit_session_created(session)  # type: ignore[arg-type]

    failed = notebook.runtime
    assert failed is not None
    backend = bridge._backends[record.id]
    assert (
        failed.status,
        failed.message,
        backend.session,
        session.consumers,
        session.closed,
    ) == ("failed", "cannot attach", None, [], False)

    replacement = FakeSession(str(tmp_path / "a.py"))
    await manager.event_bus.emit_session_created(replacement)  # type: ignore[arg-type]
    session.close()

    runtime = notebook.runtime
    assert runtime is not None
    assert runtime.id != failed.id
    assert (runtime.status, backend.session) == ("running", replacement)
    bridge.close()


async def test_a_rename_keeps_the_notebook_id(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py")
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    bridge.open()
    notebook = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert notebook is not None
    (tmp_path / "a.py").rename(tmp_path / "renamed.py")
    session = FakeSession(str(tmp_path / "renamed.py"))

    await manager.event_bus.emit_session_notebook_renamed(
        session,  # type: ignore[arg-type]
        str(tmp_path / "a.py"),
    )

    assert bridge.host.notebooks[notebook.id].path == "renamed.py"
    renamed = bridge.index.notebook_for(str(tmp_path / "renamed.py"))
    assert renamed is not None
    assert renamed.id == notebook.id


async def test_session_updates_after_catalog_removal_are_ignored(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py")
    session = FakeSession(str(tmp_path / "a.py"))
    manager.sessions["browser"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    notebook = bridge.host.notebook(record.id)
    bridge.index.forget(record.id)
    cursor = bridge.host.events()[-1].id
    assert cursor is not None

    session.broadcast(
        StartupProgressNotification(
            phase="starting-kernel", logs="", log_mode="append"
        )
    )
    session.close()

    assert names(bridge.host.events(cursor)) == ["ready"]
    assert notebook.runtime is None
    bridge.close()


@pytest.mark.parametrize("cell_id", [SCRATCH_CELL_ID, "a"])
async def test_removed_runs_release_backend_translation_state(
    manager: FakeManager, tmp_path: Path, cell_id: str
) -> None:
    prepare(manager, tmp_path, "a.py")
    session = FakeSession(str(tmp_path / "a.py"))
    manager.sessions["browser"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    now = 0.0
    bridge.host.clock = lambda: now
    bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    backend = bridge._backends[record.id]
    for phase in ("planned", "completed"):
        session.broadcast(
            ExecutionNotification(
                run_id="run",
                execution_id="execution",
                cell_id=cell_id,
                phase=phase,
                code="42",
            )
        )
    session.broadcast(
        CompletedRunNotification(run_id="run", outcome="succeeded")
    )
    retained = {"run"} if cell_id != SCRATCH_CELL_ID else set()
    assert set(backend._translators) == retained
    now = 60
    bridge.host.expire()
    # Cell results are retained, so their translation state stays too.
    retained = {"run"} if cell_id != SCRATCH_CELL_ID else set()
    assert set(backend._translators) == retained
    bridge.index.forget(record.id)
    assert backend._translators == {}
    assert bridge._backends == {}
    bridge.close()


async def test_failed_session_move_preserves_the_notebook(
    manager: FakeManager,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare(manager, tmp_path, "a.py")
    source, target = tmp_path / "a.py", tmp_path / "renamed.py"
    session = FakeSession(str(source))
    manager.sessions["browser"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    bridge.open()
    notebook = bridge.index.notebook_for(str(source))
    assert notebook is not None
    runtime = bridge.host.notebook(notebook.id).runtime

    async def rename(_session_id: str, _path: str) -> tuple[bool, str | None]:
        return False, "The notebook is busy"

    monkeypatch.setattr(manager, "rename_session", rename, raising=False)
    with pytest.raises(Conflict, match="busy"):
        await bridge.update(notebook.id, target=target, request_id="move")
    assert source.exists()
    assert not target.exists()
    assert bridge.host.notebooks[notebook.id].path == "a.py"
    assert bridge.host.notebook(notebook.id).runtime is runtime
    bridge.close()
