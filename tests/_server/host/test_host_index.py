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
from marimo._core.stream import Event
from marimo._server.host.index import WorkspaceIndex
from marimo._server.models.home import MarimoFile
from marimo._server.workspace import FixedFilesWorkspace
from tests._core.conftest import ScriptedBackend, names, runtime_id_of


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
        lambda _: ScriptedBackend(),
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
        e.data.project
        for e in host.events()
        if isinstance(e.data, ProjectMessage)
    ]
    assert project.root == str(tmp_path)
    assert project.status == "indexed"
    records = sorted(n.path or "" for n in host.notebooks.values())
    assert records == ["a.py", str(Path("sub") / "b.py")]


def test_ids_survive_a_rescan_and_a_move(tmp_path: Path) -> None:
    host = Host(operations=[])
    index = WorkspaceIndex(
        host, workspace(tmp_path, "a.py"), lambda _: ScriptedBackend()
    )
    index.refresh()
    (notebook,) = host.notebooks.values()
    log: list[Event] = []
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


def test_a_deleted_file_leaves_the_catalog(tmp_path: Path) -> None:
    host = Host(operations=[])
    ws = workspace(tmp_path, "a.py", "b.py")
    index = WorkspaceIndex(host, ws, lambda _: ScriptedBackend())
    index.refresh()
    removed = index.notebook_for(str(tmp_path / "b.py"))
    assert removed is not None
    index.rename(removed.id, "Old name")
    (tmp_path / "b.py").unlink()
    ws._files = [f for f in ws._files if f.name == "a.py"]

    index.refresh()

    assert [n.path for n in host.notebooks.values()] == ["a.py"]
    with pytest.raises(NotFound):
        host.notebook(removed.id)

    (tmp_path / "b.py").write_text("import marimo\n")
    recreated = index.ensure(str(tmp_path / "b.py"))
    assert recreated is not None
    assert recreated.id != removed.id
    assert recreated.name == "b"


def test_ensure_admits_a_file_the_listing_missed(tmp_path: Path) -> None:
    host = Host(operations=[])
    index = WorkspaceIndex(
        host, workspace(tmp_path, "a.py"), lambda _: ScriptedBackend()
    )
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


def test_deleted_file_keeps_its_runtime_until_stopped(tmp_path: Path) -> None:
    host = Host(operations=[])
    ws = workspace(tmp_path, "a.py")
    backend = ScriptedBackend()
    index = WorkspaceIndex(host, ws, lambda _: backend)
    index.refresh()
    (record,) = host.notebooks.values()
    notebook = host.notebook(record.id)
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
