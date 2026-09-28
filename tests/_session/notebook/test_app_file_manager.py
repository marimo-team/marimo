# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import threading
from concurrent.futures import ThreadPoolExecutor, wait
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._session.notebook import (
    AppFileManager,
    load_notebook,
    new_notebook,
    read_css_file,
)

if TYPE_CHECKING:
    from pathlib import Path

_NOTEBOOK_SOURCE = """
import marimo

app = marimo.App()


@app.cell
def __():
    x = 1
    return (x,)
"""


def _write_notebook(path: Path) -> Path:
    path.write_text(_NOTEBOOK_SOURCE)
    return path


def test_load_notebook_from_string_path(tmp_path: Path) -> None:
    nb = _write_notebook(tmp_path / "nb.py")
    fm = load_notebook(str(nb))
    assert isinstance(fm, AppFileManager)
    assert fm.path == str(nb.absolute())


def test_load_notebook_from_path_object(tmp_path: Path) -> None:
    nb = _write_notebook(tmp_path / "nb.py")
    fm = load_notebook(nb)
    assert fm.path == str(nb.absolute())


def test_load_notebook_resolves_relative_path(tmp_path: Path) -> None:
    nb = _write_notebook(tmp_path / "nb.py")
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        fm = load_notebook("nb.py")
    finally:
        os.chdir(original_cwd)
    assert fm.path == str(nb.absolute())


def test_load_notebook_rejects_non_notebook_extension(tmp_path: Path) -> None:
    bogus = tmp_path / "not_a_notebook.txt"
    bogus.write_text("hello")
    with pytest.raises(ValueError):
        load_notebook(bogus)


def test_load_notebook_loads_cells(tmp_path: Path) -> None:
    nb = _write_notebook(tmp_path / "nb.py")
    fm = load_notebook(nb)
    cells = list(fm.app.cell_manager.cell_data())
    assert len(cells) == 1
    assert "x = 1" in cells[0].code


def test_load_notebook_advances_document_version(tmp_path: Path) -> None:
    nb = _write_notebook(tmp_path / "nb.py")
    fm = load_notebook(nb)
    assert fm.app.cell_manager.document.version > 0


def test_new_notebook_returns_unbacked_manager() -> None:
    fm = new_notebook()
    assert isinstance(fm, AppFileManager)
    assert fm.path is None
    assert fm.filename is None


def test_new_notebook_advances_document_version() -> None:
    fm = new_notebook()
    assert fm.app.cell_manager.document.version > 0


def test_read_css_file_expands_home_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    css = "body { color: red; }"
    (tmp_path / "theme.css").write_text(css, encoding="utf-8")

    assert read_css_file("~/theme.css", filename=None) == css


def test_read_css_file_skips_unresolvable_home_directory() -> None:
    with patch(
        "pathlib.Path.expanduser",
        side_effect=RuntimeError("Could not determine home directory."),
    ):
        assert read_css_file("~/theme.css", filename=None) is None


@pytest.mark.parametrize("suffix", [".py", ".md"])
@pytest.mark.parametrize("first_writer", ["manifest", "cells"])
def test_manifest_and_cell_saves_preserve_each_other(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    first_writer: str,
) -> None:
    from marimo._environments import script_metadata
    from marimo._server.models.models import SaveNotebookRequest
    from marimo._session.notebook.serializer import get_notebook_serializer

    path = tmp_path / f"notebook{suffix}"
    serializer = get_notebook_serializer(path)
    notebook = get_notebook_serializer(tmp_path / "notebook.py").deserialize(
        script_metadata.dumps({"dependencies": []}) + "\n" + _NOTEBOOK_SOURCE
    )
    path.write_text(serializer.serialize(notebook))
    manager = load_notebook(path)
    previous = script_metadata.read_manifest(str(path))
    read = threading.Event()
    release = threading.Event()
    second_started = threading.Event()

    def pause_after_read(value):
        read.set()
        assert release.wait(timeout=5)
        return value

    if first_writer == "manifest":
        wrap_block = script_metadata.wrap_block
        monkeypatch.setattr(
            script_metadata,
            "wrap_block",
            lambda contents: pause_after_read(wrap_block(contents)),
        )
    else:
        serializer_type = type(serializer)
        extract_header = serializer_type.extract_header
        monkeypatch.setattr(
            serializer_type,
            "extract_header",
            lambda self, path: pause_after_read(extract_header(self, path)),
        )

    def save_manifest():
        return script_metadata.write_manifest(
            str(path), 'dependencies = ["requests"]\n', previous=previous
        )

    def save_cells():
        return manager.save(
            SaveNotebookRequest(
                cell_ids=list(manager.app.cell_manager.cell_ids()),
                codes=["x = 2"],
                names=["__"],
                configs=[{}],
                filename=str(path),
                layout=None,
                persist=True,
            )
        )

    first, second = (
        (save_manifest, save_cells)
        if first_writer == "manifest"
        else (save_cells, save_manifest)
    )

    def second_save():
        second_started.set()
        return second()

    # An in-flight environment operation can retain its carrier while saves
    # proceed; it must not own the notebook's read-modify-write lock.
    with (
        script_metadata.materialized_for_environment(str(path)),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        first_task = executor.submit(first)
        try:
            assert read.wait(timeout=5)
            second_task = executor.submit(second_save)
            assert second_started.wait(timeout=5)
            # Give the second writer a chance to finish if saves don't
            # serialize; the final contents must preserve both edits either way.
            wait([second_task], timeout=0.1)
        finally:
            release.set()
        first_task.result(timeout=5)
        second_task.result(timeout=5)

    assert (
        script_metadata.read_manifest(str(path))
        == 'dependencies = ["requests"]\n'
    )
    saved = load_notebook(path)
    assert [cell.code for cell in saved.app.cell_manager.cell_data()] == [
        "x = 2"
    ]
