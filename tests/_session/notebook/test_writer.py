# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._ast.cell import CellConfig
from marimo._messaging.notebook.document import NotebookCell
from marimo._session.notebook.storage import FilesystemStorage
from marimo._session.notebook.writer import NotebookWriter, cells_to_ir
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from pathlib import Path

HEADER = """# /// script
# dependencies = ["requests"]
# ///
"""

NOTEBOOK = (
    HEADER
    + """
import marimo

app = marimo.App()


@app.cell
def _():
    x = 1
    return (x,)
"""
)


class CountingStorage(FilesystemStorage):
    def __init__(self) -> None:
        super().__init__()
        self.writes = 0
        self.fail = False

    def write(self, path: Path, content: str) -> None:
        if self.fail:
            raise OSError("disk full")
        self.writes += 1
        super().write(path, content)


def cells(code: str, name: str = "_") -> list[NotebookCell]:
    return [NotebookCell(CellId_t("c"), code, name, CellConfig())]


def test_cells_to_ir_names_unnamed_cells() -> None:
    ir = cells_to_ir(cells("x = 1", name=""), {"width": "full"})

    assert [cell.name for cell in ir.cells] == ["_"]
    assert ir.app.options == {"width": "full"}
    assert ir.header is None


def test_write_keeps_the_header(tmp_path: Path) -> None:
    path = tmp_path / "nb.py"
    path.write_text(NOTEBOOK)
    writer = NotebookWriter()

    text = writer.write_ir(
        path, notebook=cells_to_ir(cells("x = 2"), {}), persist=True
    )

    assert text.startswith(HEADER)
    assert path.read_text() == text
    assert "x = 2" in text


def test_write_reads_the_header_from_the_previous_path(tmp_path: Path) -> None:
    old = tmp_path / "old.py"
    old.write_text(NOTEBOOK)
    new = tmp_path / "new.py"
    writer = NotebookWriter()

    text = writer.write_ir(
        new,
        notebook=cells_to_ir(cells("x = 1"), {}),
        persist=True,
        previous_path=old,
    )

    assert text.startswith(HEADER)


def test_unchanged_content_is_not_written_again(tmp_path: Path) -> None:
    path = tmp_path / "nb.py"
    path.write_text(NOTEBOOK)
    storage = CountingStorage()
    writer = NotebookWriter(storage)
    notebook = cells_to_ir(cells("x = 2"), {})

    first = writer.write_ir(path, notebook=notebook, persist=True)
    second = writer.write_ir(path, notebook=notebook, persist=True)

    assert storage.writes == 1
    assert first.strip() == second.strip()


def test_serializing_without_persisting_leaves_the_file_alone(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nb.py"
    path.write_text(NOTEBOOK)
    writer = NotebookWriter()

    text = writer.write_ir(
        path, notebook=cells_to_ir(cells("x = 2"), {}), persist=False
    )

    assert "x = 2" in text
    assert path.read_text() == NOTEBOOK
    assert writer.last_content is None


def test_failed_write_keeps_the_baseline(tmp_path: Path) -> None:
    path = tmp_path / "nb.py"
    path.write_text(NOTEBOOK)
    storage = CountingStorage()
    writer = NotebookWriter(storage)
    written = writer.write_ir(
        path, notebook=cells_to_ir(cells("x = 2"), {}), persist=True
    )

    storage.fail = True
    with pytest.raises(OSError):
        writer.write_ir(
            path, notebook=cells_to_ir(cells("x = 3"), {}), persist=True
        )

    assert writer.content_matches_last_save(written)
    assert path.read_text() == written


def test_content_matches_ignores_the_generated_with_version(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nb.py"
    path.write_text(NOTEBOOK)
    writer = NotebookWriter()
    written = writer.write_ir(
        path, notebook=cells_to_ir(cells("x = 2"), {}), persist=True
    )
    (line,) = [
        line
        for line in written.splitlines()
        if line.startswith("__generated_with")
    ]

    assert writer.content_matches_last_save(
        written.replace(line, '__generated_with = "0.0.0"')
    )
    assert not writer.content_matches_last_save(
        written.replace("x = 2", "x = 3")
    )
