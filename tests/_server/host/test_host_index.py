# Copyright 2026 Marimo. All rights reserved.
"""Workspace indexing and notebook catalog updates."""

from __future__ import annotations

from pathlib import Path

import pytest
from msgspec.structs import replace

from marimo._core import backend as be
from marimo._core.errors import NotFound
from marimo._core.host import Host
from marimo._core.protocol import ProjectMessage
from marimo._core.stream import RoutedEvent
from marimo._server.host.index import WorkspaceIndex
from marimo._server.models.home import MarimoFile
from marimo._server.workspace import DirectoryWorkspace, FixedFilesWorkspace
from marimo._utils.http import HTTPException
from tests._core.conftest import (
    ScriptedBackend,
    make_notebook,
    names,
    runtime_id_of,
)


def workspace(root: Path, *names: str) -> FixedFilesWorkspace:
    files = []
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text("import marimo\n")
        files.append(MarimoFile(name=name, path=str(path), last_modified=1.0))
    return FixedFilesWorkspace(files, directory=str(root))


def test_refresh_publishes_the_project_and_its_notebooks(
    tmp_path: Path,
) -> None:
    host = Host(operations=[])
    index = WorkspaceIndex(
        host,
        workspace(tmp_path, "a.py", "sub/b.py"),
        make_notebook,
    )
    index.refresh()

    assert names(host.events()) == [
        "host",
        "project",
        "notebook",
        "notebook",
        "ready",
    ]
    [project] = [
        e.event.data.project
        for e in host.events()
        if isinstance(e.event.data, ProjectMessage)
    ]
    assert project.root == str(tmp_path)
    assert project.status == "indexed"
    records = sorted(n.path or "" for n in host.notebooks.values())
    assert records == ["a.py", str(Path("sub") / "b.py")]


def test_ids_survive_a_rescan_and_a_move(tmp_path: Path) -> None:
    host = Host(operations=[])
    index = WorkspaceIndex(host, workspace(tmp_path, "a.py"), make_notebook)
    index.refresh()
    (notebook,) = host.notebooks.values()
    log: list[RoutedEvent] = []
    host.subscribe(log.append)

    index.refresh()
    assert log == []

    (tmp_path / "a.py").rename(tmp_path / "b.py")
    moved = index.moved(notebook.id, str(tmp_path / "b.py"), request_id="req")
    assert moved is not None
    assert moved.id == notebook.id
    assert moved.path == "b.py"
    assert moved.name == "b"
    assert names(log) == ["notebook"]
    assert index.notebook_for(str(tmp_path / "b.py")) == moved
    assert index.notebook_for(str(tmp_path / "a.py")) is None
    assert index.file_of(notebook.id) == tmp_path / "b.py"


async def test_a_deleted_file_leaves_the_catalog(tmp_path: Path) -> None:
    host = Host(operations=[])
    ws = workspace(tmp_path, "a.py", "b.py")
    index = WorkspaceIndex(host, ws, make_notebook)
    index.refresh()
    removed = index.notebook_for(str(tmp_path / "b.py"))
    assert removed is not None
    index.rename(removed.id, "Old name")
    (tmp_path / "b.py").unlink()
    ws._files = [f for f in ws._files if f.name == "a.py"]

    index.refresh()

    assert [n.path for n in host.notebooks.values()] == ["a.py"]
    with pytest.raises(NotFound):
        (await host.notebook(removed.id))

    (tmp_path / "b.py").write_text("import marimo\n")
    recreated = index.ensure(str(tmp_path / "b.py"))
    assert recreated is not None
    assert recreated.id != removed.id
    assert recreated.name == "b"


def test_ensure_admits_a_file_the_listing_missed(tmp_path: Path) -> None:
    host = Host(operations=[])
    index = WorkspaceIndex(host, workspace(tmp_path, "a.py"), make_notebook)
    index.refresh()
    (tmp_path / "c.py").write_text("")

    admitted = index.ensure(str(tmp_path / "c.py"))
    assert admitted is not None
    assert admitted.path == "c.py"
    assert index.ensure(str(tmp_path / "missing.py")) is None
    outside = tmp_path.parent / f"{tmp_path.name}-outside.py"
    outside.write_text("import marimo\n")
    assert index.ensure(str(outside)) is None
    index.refresh()
    assert admitted.id in host.notebooks


async def test_deleted_file_keeps_its_runtime_until_stopped(
    tmp_path: Path,
) -> None:
    host = Host(operations=[])
    ws = workspace(tmp_path, "a.py")
    backend = ScriptedBackend()
    index = WorkspaceIndex(
        host, ws, lambda record, sink: make_notebook(record, sink, backend)
    )
    index.refresh()
    (record,) = host.notebooks.values()
    notebook = await host.notebook(record.id)
    notebook.start()
    notebook.observe(be.Running(runtime_id_of(notebook)))
    runtime = notebook.runtime
    backend.calls.clear()
    (tmp_path / "a.py").unlink()
    ws._files = []

    index.refresh()
    index.refresh()

    assert host.notebooks[record.id] == replace(
        record, path=None, updated_at=None
    )
    assert notebook.runtime == runtime
    assert backend.calls == []

    notebook.stop()
    notebook.observe(be.Exited(runtime_id_of(notebook)))
    index.refresh()

    assert dict(host.notebooks) == {}
    assert runtime is not None
    assert backend.calls == [("stop", runtime.id)]


def test_open_notebooks_survive_rescans_and_move_into_workspace(
    tmp_path: Path,
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    tutorials = tmp_path / "tutorials"
    tutorials.mkdir()
    file = tutorials / "intro.py"
    file.write_text("import marimo\n")
    ws = DirectoryWorkspace(str(root), include_markdown=False)
    host = Host(operations=[])
    index = WorkspaceIndex(host, ws, make_notebook)
    index.refresh()
    assert [
        e.event.data.project.name
        for e in host.events()
        if isinstance(e.event.data, ProjectMessage)
    ] == ["workspace"]

    with pytest.raises(HTTPException):
        index.register_open_notebook(str(file))
    ws.register_temp_dir(str(tutorials))
    assert index.ensure(str(file)) is None
    record = index.register_open_notebook(str(file))
    [project] = [
        e.event.data.project
        for e in host.events()
        if isinstance(e.event.data, ProjectMessage)
        and e.event.data.project.id == record.project_id
    ]
    assert (project.name, project.root, project.operations) == (
        "Open notebooks",
        None,
        (),
    )
    assert (record.name, record.path) == ("intro", None)
    assert "notebook.edit" in record.operations
    assert "notebook.save" in record.operations
    assert "notebook.delete" not in record.operations

    index.refresh()
    assert index.register_open_notebook(str(file)) == record
    assert index.file_of(record.id) == file
    another = tutorials / "other.py"
    another.write_text("import marimo\n")
    assert index.register_open_notebook(str(another)).project_id == project.id

    renamed = tutorials / "renamed.py"
    file.rename(renamed)
    moved = index.moved(record.id, str(renamed))
    assert moved == replace(record, name="renamed")
    assert index.notebook_for(str(file)) is None
    assert index.notebook_for(str(renamed)) == moved

    saved = root / "saved.py"
    renamed.rename(saved)
    moved = index.moved(record.id, str(saved))
    assert moved is not None
    assert (moved.id, moved.project_id, moved.path) == (
        record.id,
        index.project_id,
        "saved.py",
    )
    index.refresh()
    assert index.notebook_for(str(saved)) == moved
    assert index.notebook_for(str(renamed)) is None
    assert index.file_of(record.id) == saved


def test_register_open_notebook_keeps_workspace_files_in_the_workspace(
    tmp_path: Path,
) -> None:
    host = Host(operations=[])
    index = WorkspaceIndex(host, workspace(tmp_path, "a.py"), make_notebook)
    index.refresh()
    record = index.register_open_notebook(str(tmp_path / "a.py"))
    assert (record.project_id, record.path) == (index.project_id, "a.py")
    assert [
        e.event.data.project.id
        for e in host.events()
        if isinstance(e.event.data, ProjectMessage)
    ] == [index.project_id]


@pytest.mark.parametrize("untitled", [False, True])
def test_saving_outside_the_workspace_preserves_identity(
    tmp_path: Path, untitled: bool
) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    original = root / "a.py"
    original.write_text("import marimo\napp = marimo.App()\n")
    host = Host(operations=[])
    index = WorkspaceIndex(
        host,
        DirectoryWorkspace(str(root), include_markdown=False),
        make_notebook,
    )
    index.refresh()
    record = (
        index.untitled() if untitled else index.notebook_for(str(original))
    )
    assert record is not None
    saved = tmp_path / "saved.py"
    if untitled:
        saved.write_text("import marimo\n")
    else:
        original.rename(saved)
    moved = index.moved(record.id, str(saved))
    index.refresh()
    assert (moved.id, moved.name, moved.path) == (record.id, "saved", None)
    assert [
        e.event.data.project.name
        for e in host.events()
        if isinstance(e.event.data, ProjectMessage)
        and e.event.data.project.id == moved.project_id
    ] == ["Open notebooks"]
    assert index.notebook_for(str(saved)) == moved
    assert index.file_of(record.id) == saved
    if not untitled:
        assert index.notebook_for(str(original)) is None
