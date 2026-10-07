# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from marimo._host.host import Host
from marimo._host.model import HostState, Indexed, Running, Runtime
from marimo._host.transitions import Action, KernelReady, StartRuntime
from marimo._server.host.index import WorkspaceIndex
from marimo._server.workspace import DirectoryWorkspace, SingleFileWorkspace
from marimo._types.ids import RuntimeId
from marimo._utils.marimo_path import MarimoPath
from tests._server.host.drive import notebook_id

if TYPE_CHECKING:
    from marimo._host.stream import Event

NOTEBOOK = """import marimo

app = marimo.App()

if __name__ == "__main__":
    app.run()
"""

NOW = datetime(2026, 10, 1, 9, 14, 2, tzinfo=timezone.utc)


class NoRuntime:
    def perform(self, action: Action) -> None:
        del action


def make_host() -> Host:
    return Host(HostState(), NoRuntime(), operations=[])


def write_notebook(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(NOTEBOOK)
    return path


def test_a_directory_becomes_one_indexed_project(tmp_path: Path) -> None:
    write_notebook(tmp_path / "forecasts.py")
    write_notebook(tmp_path / "models" / "train.py")
    (tmp_path / "helpers.py").write_text("x = 1\n")
    host = make_host()

    index = WorkspaceIndex(
        host, DirectoryWorkspace(str(tmp_path), include_markdown=False)
    )
    index.refresh()

    [project] = host.state.projects.values()
    assert project.root == tmp_path
    assert project.name == tmp_path.name
    assert project.index == Indexed()

    notebooks = host.state.notebooks
    assert {n.path for n in notebooks.values()} == {
        Path("forecasts.py"),
        Path("models") / "train.py",
    }
    train = notebooks[notebook_id(host, Path("models") / "train.py")]
    assert train.title == "train"
    assert train.path == Path("models") / "train.py"
    assert train.updated_at is not None
    assert train.updated_at.tzinfo is timezone.utc


def test_a_rescan_reports_what_changed(tmp_path: Path) -> None:
    forecasts = write_notebook(tmp_path / "forecasts.py")
    host = make_host()
    index = WorkspaceIndex(
        host, DirectoryWorkspace(str(tmp_path), include_markdown=False)
    )
    index.refresh()
    received: list[Event] = []
    host.subscribe(received.append)

    # Nothing changed: nothing is sent.
    index.refresh()
    assert received == []

    write_notebook(tmp_path / "new.py")
    forecasts.unlink()
    index.refresh()
    assert [e.name for e in received] == ["notebook", "notebook.removed"]
    assert {n.path for n in host.state.notebooks.values()} == {Path("new.py")}


def test_a_deleted_file_with_a_runtime_keeps_a_nameless_notebook(
    tmp_path: Path,
) -> None:
    forecasts = write_notebook(tmp_path / "forecasts.py")
    host = make_host()
    index = WorkspaceIndex(
        host, DirectoryWorkspace(str(tmp_path), include_markdown=False)
    )
    index.refresh()
    forecasts_id = notebook_id(host, Path("forecasts.py"))
    host.command(
        StartRuntime(forecasts_id, RuntimeId("rt-1"), NOW, sandbox=False)
    )
    host.observe(KernelReady(RuntimeId("rt-1"), 0, None))

    forecasts.unlink()
    index.refresh()

    notebook = host.state.notebooks[forecasts_id]
    assert notebook.path is None
    assert isinstance(notebook.runtime, Runtime)
    assert isinstance(notebook.runtime.lifecycle, Running)


def test_ensure_admits_files_under_the_root_only(tmp_path: Path) -> None:
    write_notebook(tmp_path / "forecasts.py")
    host = make_host()
    index = WorkspaceIndex(
        host, DirectoryWorkspace(str(tmp_path), include_markdown=False)
    )
    index.refresh()

    later = write_notebook(tmp_path / "later.py")
    later_id = index.ensure(str(later))
    assert later_id == notebook_id(host, Path("later.py"))

    outside = write_notebook(tmp_path.parent / "outside.py")
    assert index.ensure(str(outside)) is None
    assert index.ensure(str(tmp_path / "missing.py")) is None

    # Admitted files survive a rescan that lists them too, under the same id.
    index.refresh()
    assert later_id in host.state.notebooks


def test_a_single_file_workspace_uses_its_directory_as_the_root(
    tmp_path: Path,
) -> None:
    forecasts = write_notebook(tmp_path / "forecasts.py")
    host = make_host()

    index = WorkspaceIndex(
        host, SingleFileWorkspace.from_path(MarimoPath(str(forecasts)))
    )
    index.refresh()

    [project] = host.state.projects.values()
    assert project.root == tmp_path
    assert {n.path for n in host.state.notebooks.values()} == {
        Path("forecasts.py")
    }
