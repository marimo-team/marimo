# Copyright 2026 Marimo. All rights reserved.
"""Session discovery and updates in the host catalog."""

from __future__ import annotations

import asyncio
import threading
from typing import TYPE_CHECKING

import pytest

from marimo._core import protocol
from marimo._core.errors import Conflict, DecisionRequired, EditConflict
from marimo._core.stream import RoutedEvent
from marimo._messaging.notification import (
    CompletedRunNotification,
    ExecutionNotification,
    StartupProgressNotification,
    VariablesNotification,
)
from marimo._runtime.scratch import SCRATCH_CELL_ID
from marimo._server.host.bridge import SessionBridge
from marimo._server.host.events import MarimoEvent, MarimoMessage
from marimo._server.models.home import MarimoFile
from marimo._server.workspace import FixedFilesWorkspace
from tests._core.conftest import names
from tests._server.host.conftest import FakeManager, FakeSession

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any

    from marimo._core.document import DocumentCell
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
        notebook = await bridge.host.notebook(record.id)
        documents[name] = (notebook.saved_etag, notebook.document.etag)

    # A session showing the file as it is on disk is saved.
    saved, current = documents["saved.py"]
    assert saved == current
    # One with an edit the file lacks is not, and names the file's revision.
    saved, current = documents["edited.py"]
    assert saved != current
    assert saved == documents["saved.py"][1]
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
    ) -> tuple[list[DocumentCell], dict[str, Any]] | None:
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

    def stop_on_starting(event: RoutedEvent) -> None:
        if (
            isinstance(event.event, protocol.RuntimeEvent)
            and event.event.data.runtime.status == "starting"
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


async def test_editor_transactions_reach_the_host_document(
    manager: FakeManager, tmp_path: Path
) -> None:
    from marimo._ast.cell import CellConfig
    from marimo._messaging.notebook import (
        NotebookCell,
        NotebookDocument,
        SetCode,
        Transaction,
    )
    from marimo._messaging.notification import (
        NotebookDocumentTransactionNotification,
    )
    from marimo._types.ids import CellId_t

    prepare(manager, tmp_path, "a.py")
    session = FakeSession(str(tmp_path / "a.py"))
    session.document = NotebookDocument(
        [NotebookCell(CellId_t("Hbol"), "x = 1", "_", CellConfig())]
    )
    manager.sessions["browser-1"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    events: list[RoutedEvent] = []
    bridge.host.subscribe(events.append, notebook_id=record.id)

    # The document comes from the session, ids included.
    notebook = await bridge.host.notebook(record.id)
    document = notebook.document
    assert [c.id for c in document] == ["Hbol"]

    # A frontend edit reaches the host document, and the app config as
    # the session reports it comes along.
    applied = session.document.apply(
        Transaction(
            changes=(SetCode(CellId_t("Hbol"), "x = 2"),), source="frontend"
        )
    )
    session.app_file_manager.app.config.asdict_difference.return_value = {
        "width": "full"
    }
    session.broadcast(
        NotebookDocumentTransactionNotification(transaction=applied)
    )

    cell = notebook.document.cell("Hbol")
    assert cell is not None
    assert cell.code == "x = 2"
    assert notebook.document.app_config == {"width": "full"}
    assert names(events)[-2:] == ["cell", "document"]
    bridge.close()


async def test_host_edits_reach_the_session_as_one_transaction(
    manager: FakeManager, tmp_path: Path
) -> None:
    from marimo._ast.cell import CellConfig
    from marimo._messaging.notebook import NotebookCell, NotebookDocument
    from marimo._messaging.notification import (
        NotebookDocumentTransactionNotification,
    )
    from marimo._types.ids import CellId_t

    prepare(manager, tmp_path, "a.py")
    session = FakeSession(str(tmp_path / "a.py"))
    session.document = NotebookDocument(
        [NotebookCell(CellId_t("Hbol"), "x = 1", "_", CellConfig())]
    )
    manager.sessions["browser-1"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    events: list[RoutedEvent] = []
    bridge.host.subscribe(events.append, notebook_id=record.id)

    response = await bridge.edit(
        record.id,
        [
            protocol.PutCell(
                base_etag=None,
                cell=protocol.CellInput(
                    id=protocol.CellId("new"), code="y = x"
                ),
            )
        ],
        request_id="edit-1",
    )

    assert set(response.cells) == {"new"}
    assert session.document.cell_ids == ["Hbol", "new"]
    (notification,) = session.notifications
    assert isinstance(notification, NotebookDocumentTransactionNotification)
    assert notification.transaction.source == "host"
    # The session echoes the edit without publishing the document twice.
    assert names(
        [e for e in events if not isinstance(e.event, MarimoEvent)]
    ) == [
        "cell",
        "document",
    ]
    assert [
        e.event.data for e in events if isinstance(e.event, MarimoEvent)
    ] == [MarimoMessage(notification)]
    assert notebook.document.etag == response.document.etag
    assert "y = x" not in (tmp_path / "a.py").read_text()
    bridge.close()


async def test_edit_response_includes_app_config_mirrored_from_the_session(
    manager: FakeManager, tmp_path: Path
) -> None:
    from marimo._session.notebook import AppFileManager

    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    session = FakeSession(str(path))
    session.document = AppFileManager(str(path)).app.cell_manager.document
    manager.sessions["browser-1"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    try:
        record = bridge.index.notebook_for(str(path))
        assert record is not None
        notebook = await bridge.host.notebook(record.id)
        session.app_file_manager.app.config.asdict_difference.return_value = {
            "width": "full"
        }

        response = await bridge.edit(
            record.id,
            [
                protocol.PutCell(
                    base_etag=None,
                    cell=protocol.CellInput(
                        id=protocol.CellId("new"), code="y = 2"
                    ),
                )
            ],
            request_id="edit-1",
        )

        assert response.document.app_config == {"width": "full"}
        assert response.document.etag == notebook.document.etag
    finally:
        bridge.close()


async def test_a_new_session_replaces_a_read_without_host_edits(
    manager: FakeManager, tmp_path: Path
) -> None:
    from marimo._session.notebook import AppFileManager

    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    document = notebook.document
    events: list[RoutedEvent] = []
    bridge.host.subscribe(events.append, notebook_id=record.id)

    # The file changes after the host read it, then a session opens it.
    path.write_text(NOTEBOOK.replace("x = 1", "x = 2"))
    session = FakeSession(str(path))
    session.document = AppFileManager(str(path)).app.cell_manager.document
    await manager.event_bus.emit_session_created(session)  # type: ignore[arg-type]

    assert [cell.code for cell in notebook.document] == ["x = 2"]
    assert notebook.saved_etag == notebook.document.etag
    assert names(events)[-3:] == ["cell", "document", "runtime"]
    assert session.notifications == []
    bridge.close()


async def test_a_new_session_adopts_unsaved_host_edits(
    manager: FakeManager, tmp_path: Path
) -> None:
    from marimo._ast.cell import CellConfig
    from marimo._messaging.notebook import NotebookCell, NotebookDocument
    from marimo._types.ids import CellId_t

    def editor_cell(cell: protocol.Cell) -> NotebookCell:
        return NotebookCell(
            CellId_t(cell.id), cell.code, cell.name, CellConfig()
        )

    prepare(manager, tmp_path, "a.py")
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(tmp_path / "a.py"))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    document = notebook.document
    session = FakeSession(str(tmp_path / "a.py"))
    session.document = NotebookDocument(editor_cell(c) for c in document)
    await bridge.edit(
        record.id,
        [
            protocol.PutCell(
                base_etag=None,
                cell=protocol.CellInput(
                    id=protocol.CellId("new"), code="unsaved = 42"
                ),
            )
        ],
        request_id="edit-before-session",
    )

    await manager.event_bus.emit_session_created(session)  # type: ignore[arg-type]

    assert [(c.id, c.code) for c in session.document.cells] == [
        (c.id, c.code) for c in notebook.document
    ]
    assert notebook.saved_etag != notebook.document.etag
    assert "unsaved" not in (tmp_path / "a.py").read_text()
    bridge.close()


async def test_an_edit_reaches_the_kernel_as_one_command(
    manager: FakeManager, tmp_path: Path
) -> None:
    from marimo._runtime.commands import EditCellsCommand
    from marimo._session.notebook import AppFileManager

    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(
        NOTEBOOK + "@app.cell\ndef _(x):\n    y = x\n    return (y,)\n"
    )
    session = FakeSession(str(path))
    session.document = AppFileManager(str(path)).app.cell_manager.document
    manager.sessions["browser-1"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    first, second = (await bridge.host.notebook(record.id)).document

    await bridge.edit(
        record.id,
        [
            protocol.PutCell(
                base_etag=first.etag,
                cell=protocol.CellInput(
                    id=first.id,
                    code=first.code,
                    config=protocol.CellConfigInput(disabled=True),
                ),
            ),
            protocol.DeleteCell(id=second.id, base_etag=second.etag),
            protocol.PutCell(
                base_etag=None,
                cell=protocol.CellInput(
                    id=protocol.CellId("new"),
                    code="z = 1",
                    config=protocol.CellConfigInput(hide_code=True),
                ),
            ),
        ],
        request_id="edit-1",
    )

    default = {
        "column": None,
        "disabled": False,
        "hide_code": False,
        "expand_output": False,
    }
    assert session.commands == [
        EditCellsCommand(
            codes={"new": "z = 1"},
            configs={
                first.id: {**default, "disabled": True},
                "new": {**default, "hide_code": True},
            },
            delete_ids=[second.id],
        )
    ]

    # Changed code reaches the kernel without a run.
    await bridge.edit(
        record.id,
        [
            protocol.PutCell(
                base_etag="*",
                cell=protocol.CellInput(
                    id=protocol.CellId("new"),
                    code="z = 2",
                    config=protocol.CellConfigInput(hide_code=True),
                ),
            )
        ],
        request_id="edit-2",
    )
    assert session.commands[1:] == [
        EditCellsCommand(codes={"new": "z = 2"}, configs={}, delete_ids=[])
    ]
    bridge.close()


def replace_code(cell: protocol.Cell, code: str) -> protocol.PutCell:
    return protocol.PutCell(
        base_etag=cell.etag, cell=protocol.CellInput(id=cell.id, code=code)
    )


async def test_save_writes_the_cells_and_keeps_the_app_config(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(
        NOTEBOOK.replace("marimo.App()", 'marimo.App(width="full")')
    )
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    document = notebook.document
    (cell,) = document
    events: list[RoutedEvent] = []
    bridge.host.subscribe(events.append, notebook_id=record.id)

    edited = await bridge.edit(
        record.id, [replace_code(cell, "x = 2")], request_id="edit-1"
    )
    assert edited.document.saved_etag != edited.document.etag

    with pytest.raises(EditConflict) as stale:
        await bridge.save(record.id, if_match=["stale"], request_id="save-0")
    assert stale.value.change == 0
    assert "x = 2" not in path.read_text()

    saved = await bridge.save(
        record.id, if_match=[edited.document.etag], request_id="save-1"
    )

    assert (
        saved.document.saved_etag
        == saved.document.etag
        == edited.document.etag
    )
    assert saved.cells == {}
    text = path.read_text()
    assert "x = 2" in text
    assert 'width="full"' in text
    assert names(events)[-1] == "document"
    assert events[-1].event.data.request_id == "save-1"  # type: ignore[union-attr]
    bridge.close()


async def test_saving_keeps_an_edit_made_while_the_file_is_written(
    manager: FakeManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from marimo._session.notebook import AppFileManager

    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    document = notebook.document
    (cell,) = document
    written = notebook.document.etag

    started = asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    original = AppFileManager.save_from_cells

    def save(self: AppFileManager, cells: Any, **kwargs: Any) -> str:
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        return original(self, cells, **kwargs)

    monkeypatch.setattr(AppFileManager, "save_from_cells", save)
    saving = asyncio.ensure_future(
        bridge.save(record.id, if_match=None, request_id="save-1")
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        edited = await bridge.edit(
            record.id, [replace_code(cell, "x = 2")], request_id="edit-1"
        )
    finally:
        release.set()
    saved = await asyncio.wait_for(saving, 5)

    # The file has the snapshot; the host keeps the edit, unsaved.
    assert saved.document.etag == edited.document.etag
    assert saved.document.saved_etag == written
    assert notebook.saved_etag != notebook.document.etag
    assert "x = 1" in path.read_text()
    assert "x = 2" not in path.read_text()
    bridge.close()


async def test_save_with_a_session_writes_through_the_editors_file_manager(
    manager: FakeManager, tmp_path: Path
) -> None:
    from marimo._session.notebook import AppFileManager

    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    session = FakeSession(str(path))
    session.app_file_manager = AppFileManager(str(path))
    session.document = session.app_file_manager.app.cell_manager.document
    manager.sessions["browser-1"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    document = notebook.document
    (cell,) = document
    # The editor wrote once, so its manager remembers what is on disk.
    session.app_file_manager.save_from_cells(list(session.document.cells))
    events: list[RoutedEvent] = []
    bridge.host.subscribe(events.append, notebook_id=record.id)

    edited = await bridge.edit(
        record.id, [replace_code(cell, "x = 2")], request_id="edit-1"
    )
    saved = await bridge.save(record.id, if_match=None, request_id="save-1")

    assert saved.document.saved_etag == edited.document.etag
    text = path.read_text()
    assert "x = 2" in text
    # The editor's record of the last write is the host's write, so its
    # watcher ignores it and its next write of other content proceeds.
    assert session.app_file_manager.content_matches_last_save(text)
    # The write is published once, under the request that asked for it,
    # not again when the editor's manager reports it.
    published = [
        e
        for e in events
        if isinstance(e.event, protocol.DocumentEvent)
        and e.event.data.document.saved_etag == saved.document.etag  # type: ignore[union-attr]
    ]
    assert [e.event.data.request_id for e in published] == ["save-1"]  # type: ignore[union-attr]
    bridge.close()


async def test_the_editor_saving_marks_the_host_document_saved(
    manager: FakeManager, tmp_path: Path
) -> None:
    from marimo._ast.cell import CellConfig
    from marimo._core.document import Document
    from marimo._messaging.notebook import NotebookCell
    from marimo._server.host.document import from_file_manager
    from marimo._session.notebook import AppFileManager
    from marimo._types.ids import CellId_t

    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    document = notebook.document
    session = FakeSession(str(path))
    session.app_file_manager = AppFileManager(str(path))
    session.document = session.app_file_manager.app.cell_manager.document
    manager.sessions["browser-1"] = session
    await manager.event_bus.emit_session_created(session)  # type: ignore[arg-type]
    (cell,) = session.document.cells
    before = notebook.document.etag

    # The editor writes new content the host has not mirrored yet.
    session.app_file_manager.save_from_cells(
        [NotebookCell(CellId_t(cell.id), "x = 2", cell.name, CellConfig())]
    )

    written = Document(*from_file_manager(session.app_file_manager)).etag
    assert notebook.saved_etag == written
    assert notebook.document.etag == before != written

    # Once the session goes away, its writes are no longer the host's,
    # and the file as the editor left it is what the host compares to.
    manager.close_session("browser-1")
    assert session.app_file_manager.on_persisted is None
    saved = await bridge.save(record.id, if_match=None, request_id="save-1")
    assert saved.document.saved_etag == saved.document.etag
    assert "x = 1" in path.read_text()
    path.write_text(path.read_text().replace("x = 1", "x = 3"))
    with pytest.raises(DecisionRequired):
        await bridge.save(record.id, if_match=None, request_id="save-2")
    bridge.close()


@pytest.mark.parametrize("error", [OSError, UnicodeError])
async def test_save_refuses_to_overwrite_when_the_file_cannot_be_read(
    manager: FakeManager,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    error: type[Exception],
) -> None:
    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    before = notebook.document
    external = NOTEBOOK.replace("x = 1", "x = 2")
    path.write_text(external)

    def unreadable(_file: Path) -> str:
        raise error("The change check failed, but the file is writable")

    monkeypatch.setattr("marimo._server.host.bridge._read_text", unreadable)
    try:
        with pytest.raises(Conflict, match="could not be read"):
            await bridge.save(record.id, if_match=None, request_id="save-1")
        assert path.read_text() == external
        assert notebook.document == before
    finally:
        bridge.close()


async def test_save_without_a_file_baseline_requires_a_decision(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    await bridge.host.notebook(record.id)
    bridge._file_texts.pop(record.id)
    external = NOTEBOOK.replace("x = 1", "x = 2")
    path.write_text(external)
    try:
        with pytest.raises(DecisionRequired):
            await bridge.save(record.id, if_match=None, request_id="save-1")
        assert path.read_text() == external

        reloaded = await bridge.save(
            record.id,
            if_match=None,
            decisions={"file": "reload"},
            request_id="save-2",
        )
        assert reloaded.document.saved_etag == reloaded.document.etag
        assert path.read_text() == external
        assert bridge._file_texts[record.id] == external
    finally:
        bridge.close()


async def test_reloading_refuses_to_drop_an_edit_made_while_reading(
    manager: FakeManager, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prepare(manager, tmp_path, "a.py")
    path = tmp_path / "a.py"
    path.write_text(NOTEBOOK)
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    record = bridge.index.notebook_for(str(path))
    assert record is not None
    notebook = await bridge.host.notebook(record.id)
    document = notebook.document
    (cell,) = document
    path.write_text(NOTEBOOK.replace("x = 1", "x = 2"))

    started = asyncio.Event()
    release = threading.Event()
    loop = asyncio.get_running_loop()
    original = SessionBridge._read

    def read(self: SessionBridge, file: Path) -> Any:
        loop.call_soon_threadsafe(started.set)
        assert release.wait(5)
        return original(self, file)

    monkeypatch.setattr(SessionBridge, "_read", read)
    reloading = asyncio.ensure_future(
        bridge.save(
            record.id,
            if_match=None,
            decisions={"file": "reload"},
            request_id="save-1",
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 5)
        edited = await bridge.edit(
            record.id, [replace_code(cell, "x = 3")], request_id="edit-1"
        )
    finally:
        release.set()

    with pytest.raises(EditConflict) as conflict:
        await asyncio.wait_for(reloading, 5)
    assert conflict.value.document == edited.document
    assert notebook.document.cell(cell.id).code == "x = 3"  # type: ignore[union-attr]
    bridge.close()


async def test_session_notifications_join_the_notebook_stream_once(
    manager: FakeManager, tmp_path: Path
) -> None:
    prepare(manager, tmp_path, "a.py", "b.py")
    session = FakeSession(str(tmp_path / "a.py"))
    manager.sessions["browser"] = session
    bridge = SessionBridge(manager)  # type: ignore[arg-type]
    await bridge.open()
    a = bridge.index.notebook_for(str(tmp_path / "a.py"))
    b = bridge.index.notebook_for(str(tmp_path / "b.py"))
    assert a is not None
    assert b is not None

    first: list[RoutedEvent] = []
    second: list[RoutedEvent] = []
    catalog: list[RoutedEvent] = []
    other: list[RoutedEvent] = []
    filtered: list[RoutedEvent] = []
    bridge.host.subscribe(first.append, notebook_id=a.id)
    bridge.host.subscribe(second.append, notebook_id=a.id)
    bridge.host.subscribe(catalog.append)
    bridge.host.subscribe(other.append, notebook_id=b.id)
    bridge.host.subscribe(filtered.append, notebook_id=a.id, types={"marimo"})

    variables = VariablesNotification(variables=[])
    planned = ExecutionNotification(
        run_id="run-1",
        execution_id="execution-1",
        cell_id="cell-1",
        phase="planned",
        code="x = 1",
    )
    session.broadcast(variables)
    session.broadcast(planned)

    assert first == second
    assert catalog == other == []
    assert filtered == [e for e in first if isinstance(e.event, MarimoEvent)]
    assert [(e.run_id, e.event.data) for e in filtered] == [
        (None, MarimoMessage(variables)),
        (protocol.RunId("run-1"), MarimoMessage(planned)),
    ]
    bridge.close()
