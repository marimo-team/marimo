# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import json
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


def test_rename_changes_format_py_to_ipynb_and_back(tmp_path: Path) -> None:
    """Renaming a .py file to .ipynb converts to ipynb format,
    and renaming back to .py converts back to Python format."""
    # Create a .py notebook file
    py_path = tmp_path / "test_notebook.py"
    py_path.write_text(_NOTEBOOK_SOURCE)

    # Load the notebook
    fm = load_notebook(py_path)
    assert fm.filename == str(py_path.absolute())

    # Rename .py → .ipynb
    ipynb_path = tmp_path / "test_notebook.ipynb"
    result = fm.rename(str(ipynb_path))
    assert result == ipynb_path.name

    # The old .py file should be gone (rename moves the file)
    assert not py_path.exists()
    # The new .ipynb file should exist
    assert ipynb_path.exists()

    # Verify the .ipynb content is valid JSON with marimo metadata
    with open(ipynb_path, encoding="utf-8") as f:
        ipynb_data = json.load(f)
    assert "cells" in ipynb_data
    assert "metadata" in ipynb_data
    assert "marimo" in ipynb_data["metadata"]
    assert "marimo_version" in ipynb_data["metadata"]["marimo"]
    # Verify cell content is preserved
    assert any("x = 1" in cell["source"] for cell in ipynb_data["cells"])

    # Rename .ipynb → .py
    new_py_path = tmp_path / "test_notebook.py"
    result = fm.rename(str(new_py_path))
    assert result == new_py_path.name

    # The .ipynb file should be gone
    assert not ipynb_path.exists()
    # The .py file should exist again
    assert new_py_path.exists()

    # Verify the .py content is valid marimo format
    py_content = new_py_path.read_text(encoding="utf-8")
    assert "import marimo" in py_content
    assert "x = 1" in py_content

    # Verify the AppFileManager still points to the right file
    assert fm.filename == str(new_py_path.absolute())
