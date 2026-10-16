# Copyright 2026 Marimo. All rights reserved.
"""Session discovery and updates in the host catalog."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from starlette.datastructures import State

from marimo._config.manager import MarimoConfigManager
from marimo._core import protocol
from marimo._core.errors import Conflict
from marimo._core.stream import Event
from marimo._messaging.notification import (
    AttachmentsNotification,
    CompletedRunNotification,
    ExecutionNotification,
    StartupProgressNotification,
)
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.api.deps import AppStateBase
from marimo._server.host.bridge import SessionBridge
from marimo._server.models.home import MarimoFile
from marimo._server.workspace import FixedFilesWorkspace
from marimo._session.model import SessionMode
from tests._core.conftest import names
from tests._server.host.conftest import FakeManager, FakeSession

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from marimo._config.manager import UserConfigStore
    from marimo._core.document import CellSource, Policy
    from marimo._session.consumer import SessionConsumer


def prepare(manager: FakeManager, root: Path, *names: str) -> None:
    files = []
    for name in names:
        (root / name).write_text("")
        files.append(MarimoFile(name=name, path=str(root / name)))
    manager.workspace = FixedFilesWorkspace(files, directory=str(root))


NOTEBOOK = """import marimo

__generated_with = "0.0.0"
app = marimo.App()

@app.cell
def _():
    x = 1
    return (x,)
"""


@pytest.mark.parametrize(
    ("server_policy", "script_policy", "expected"),
    [
        ("autorun", None, "autorun"),
        ("lazy", None, "lazy"),
        ("autorun", "lazy", "lazy"),
        ("lazy", "autorun", "autorun"),
    ],
)
async def test_initial_policy_inherits_server_config_with_script_overrides(
    manager: FakeManager,
    tmp_path: Path,
    user_config_manager: UserConfigStore,
    server_policy: Policy,
    script_policy: Policy | None,
    expected: Policy,
) -> None:
    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    header = (
        "# /// script\n"
        "# [tool.marimo.runtime]\n"
        f'# on_cell_change = "{script_policy}"\n'
        "# ///\n"
        if script_policy is not None
        else ""
    )
    path.write_text(header + NOTEBOOK)
    config = MarimoConfigManager(user_config_manager).with_overrides(
        {"runtime": {"on_cell_change": server_policy}}
    )
    bridge = SessionBridge(manager, config)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None

    notebook = await bridge.host.notebook(record.id)

    assert notebook.document._record.policy == expected
    assert notebook.runtime is None
    assert manager.starts == []
    bridge.close()


async def test_initial_policy_uses_the_adopted_sessions_effective_config(
    manager: FakeManager,
    tmp_path: Path,
    user_config_manager: UserConfigStore,
) -> None:
    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    config = MarimoConfigManager(user_config_manager).with_overrides(
        {"runtime": {"on_cell_change": "autorun"}}
    )
    session = FakeSession(str(path))
    session.config_manager = config.with_overrides(
        {"runtime": {"on_cell_change": "lazy"}}
    )
    manager.sessions["browser"] = session
    bridge = SessionBridge(manager, config)  # type: ignore[arg-type]

    await bridge.open()

    record = bridge.index.notebook_for(str(path))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    assert notebook.document._record.policy == "lazy"
    assert notebook.runtime is not None
    bridge.close()


async def test_an_adopted_document_is_saved_as_far_as_the_file_goes(
    manager: FakeManager, tmp_path: Path
) -> None:
    from marimo._messaging.notebook import SetCode, Transaction
    from marimo._session.notebook import AppFileManager

    prepare(manager, tmp_path, "saved.py", "edited.py")
    sessions = {}
    for name in ("saved.py", "edited.py"):
        path = tmp_path / name
        path.write_text(NOTEBOOK)
        session = FakeSession(str(path))
        session.document = AppFileManager(str(path)).app.cell_manager.document
        session.app_file_manager.app.config.asdict_difference.return_value = {}
        sessions[name] = manager.sessions[name] = session
    edited = sessions["edited.py"].document
    edited.apply(
        Transaction(
            changes=(SetCode(edited.cell_ids[0], "x = 2"),), source="frontend"
        )
    )
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()

    documents = {}
    for name in ("saved.py", "edited.py"):
        record = bridge.index.notebook_for(str(tmp_path / name))
        assert record is not None
        document = (await bridge.host.notebook(record.id)).document
        assert document is not None
        documents[name] = document._record

    # A session showing the file as it is on disk is saved.
    assert documents["saved.py"].saved_etag == documents["saved.py"].etag
    # One with an edit the file lacks is not, and names the file's revision.
    assert documents["edited.py"].saved_etag != documents["edited.py"].etag
    assert documents["edited.py"].saved_etag == documents["saved.py"].etag
    bridge.close()


async def test_sessions_present_and_created_are_adopted(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py", "b.py")
    existing = FakeSession(str(tmp_path / "a.py"))
    manager.sessions["browser-1"] = existing
    bridge = SessionBridge(manager)  # type: ignore[arg-type]

    await bridge.open()

    a = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert a is not None
    runtime = (await bridge.host.notebook(a.id)).runtime
    assert runtime is not None
    assert runtime.status == "running"
    assert existing.consumers[0][1] is False

    created = FakeSession(str(tmp_path / "b.py"))
    await manager.event_bus.emit_session_created(created)  # type: ignore[arg-type]
    b = bridge.index.notebook_for(str(tmp_path / "b.py"))
    assert b is not None
    assert (await bridge.host.notebook(b.id)).runtime is not None

    unknown = FakeSession(str(tmp_path.parent / "elsewhere.py"))
    await manager.event_bus.emit_session_created(unknown)  # type: ignore[arg-type]
    assert unknown.consumers == []
    bridge.close()


async def test_delete_during_adoption_preserves_the_file_and_session(
    manager: FakeManager,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    session = FakeSession(str(path))
    started, release, deleting = (
        asyncio.Event(),
        asyncio.Event(),
        asyncio.Event(),
    )
    load = bridge._load

    async def paused_load(
        file: Path,
    ) -> tuple[list[CellSource], dict[str, Any]] | None:
        started.set()
        await release.wait()
        return await load(file)

    async def delete() -> None:
        deleting.set()
        await bridge.delete(record.id, request_id="delete")

    monkeypatch.setattr(bridge, "_load", paused_load)
    adoption = asyncio.create_task(
        manager.event_bus.emit_session_created(session)  # type: ignore[arg-type]
    )
    await asyncio.wait_for(started.wait(), 5)
    deletion = asyncio.create_task(delete())
    try:
        # Queue deletion on the file lock before initialization finishes.
        await asyncio.wait_for(deleting.wait(), 5)
        release.set()
        with pytest.raises(Conflict, match="runtime"):
            await asyncio.wait_for(deletion, 5)
        await asyncio.wait_for(adoption, 5)

        notebook = await bridge.host.notebook(record.id)
        assert notebook.runtime is not None
        assert notebook.runtime.status == "running"
        assert path.read_text() == NOTEBOOK
        assert bridge._backends[record.id].session is session
        assert not session.closed
    finally:
        release.set()
        await asyncio.gather(adoption, deletion, return_exceptions=True)
        bridge.close()


async def test_a_subscriber_can_stop_an_adopted_session(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py")
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
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
    await bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
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
    await bridge.open()
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
    await bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
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
    await bridge.open()
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
    await bridge.open()
    notebook = bridge.index.notebook_for(str(source))
    assert notebook is not None
    runtime = (await bridge.host.notebook(notebook.id)).runtime

    async def rename(_session_id: str, _path: str) -> tuple[bool, str | None]:
        return False, "The notebook is busy"

    monkeypatch.setattr(manager, "rename_session", rename, raising=False)
    with pytest.raises(Conflict, match="busy"):
        await bridge.update(notebook.id, target=target, request_id="move")
    assert source.exists()
    assert not target.exists()
    assert bridge.host.notebooks[notebook.id].path == "a.py"
    assert (await bridge.host.notebook(notebook.id)).runtime is runtime
    bridge.close()


async def test_session_notebook_lookup_boundaries(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py", "unopened.py")
    saved = FakeSession(str(tmp_path / "a.py"))
    unsaved = FakeSession(None)
    outside = FakeSession(str(tmp_path.parent / "outside.py"))
    manager.sessions.update(saved=saved, unsaved=unsaved, outside=outside)
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    notebook = bridge.notebook_for_session(saved)  # type: ignore[arg-type]
    assert notebook is not None
    assert bridge.session_for_notebook(notebook.id) is saved
    assert bridge.notebook_for_session(unsaved) is None  # type: ignore[arg-type]
    assert bridge.notebook_for_session(outside) is None  # type: ignore[arg-type]
    assert (
        bridge.notebook_for_session(FakeSession(str(tmp_path / "a.py")))
        is None
    )  # type: ignore[arg-type]
    unopened = bridge.index.notebook_for(str(tmp_path / "unopened.py"))
    assert unopened is not None
    assert bridge.session_for_notebook(unopened.id) is None
    assert bridge.session_for_notebook("missing") is None
    saved.close()
    assert bridge.session_for_notebook(notebook.id) is None
    assert bridge.notebook_for_session(saved) is None  # type: ignore[arg-type]
    bridge.close()


async def test_attachment_feed_uses_full_current_state_and_unsubscribes(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py", "b.py")
    first = FakeSession(str(tmp_path / "a.py"))
    second = FakeSession(str(tmp_path / "b.py"))
    first.notify = Mock()  # type: ignore[attr-defined]
    second.notify = Mock()  # type: ignore[attr-defined]
    manager.sessions.update(first=first, second=second)
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    notebook = bridge.notebook_for_session(first)  # type: ignore[arg-type]
    assert notebook is not None
    assert notebook.attachments == []
    agent = notebook.attach(identity="codex", kind="agent", name="Codex")
    client = notebook.attach(kind="client")
    notebook.detach(agent.id)
    notebook.detach("missing")
    assert first.notify.call_args_list == [  # type: ignore[attr-defined]
        (
            (AttachmentsNotification(attachments=[agent]),),
            {"from_consumer_id": None},
        ),
        (
            (AttachmentsNotification(attachments=[agent, client]),),
            {"from_consumer_id": None},
        ),
        (
            (AttachmentsNotification(attachments=[client]),),
            {"from_consumer_id": None},
        ),
    ]
    second.notify.assert_not_called()  # type: ignore[attr-defined]
    bridge.close()
    notebook.detach(client.id)
    assert first.notify.call_count == 3  # type: ignore[attr-defined]


@pytest.mark.parametrize("mode", ["edit", "run"])
def test_app_state_without_host_has_no_notebook_or_session(mode: str) -> None:
    state = AppStateBase(
        State({"session_manager": SimpleNamespace(mode=SessionMode(mode))})
    )
    assert state.notebook_for_session(FakeSession(None)) is None  # type: ignore[arg-type]
    assert state.session_for_notebook("missing") is None


async def test_bridge_supplies_metadata_for_the_current_session(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py")
    session = FakeSession(str(tmp_path / "a.py"))
    manager.sessions["browser"] = session
    bridge = SessionBridge(
        manager,  # type: ignore[arg-type]
        request_metadata=lambda current: {
            "file": current.app_file_manager.path,
            "extra": 7,
        },
    )
    await bridge.open()
    notebook = bridge.notebook_for_session(session)  # type: ignore[arg-type]
    assert notebook is not None
    run = notebook.run("print(1)", request_id="metadata-test")
    await session.submitted.wait()
    assert session.commands[-1].request.meta == {
        "file": str(tmp_path / "a.py"),
        "extra": 7,
    }
    session.broadcast(CompletedRunNotification(run_id=run.id))
    backend = bridge._backends[notebook.id]
    assert backend._run is not None
    assert backend._run.task is not None
    await backend._run.task
    bridge.close()
