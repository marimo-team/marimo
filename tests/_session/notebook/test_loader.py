# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from marimo._session.notebook import (
    AppFileManager,
    load_notebook,
    new_notebook,
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


def test_new_notebook_returns_unbacked_manager() -> None:
    fm = new_notebook()
    assert isinstance(fm, AppFileManager)
    assert fm.path is None
    assert fm.filename is None
