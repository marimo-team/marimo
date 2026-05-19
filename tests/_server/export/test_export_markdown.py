from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from marimo._convert.markdown.flavor.base import MarkdownFlavorName
from marimo._server.export import export_as_md
from marimo._utils.marimo_path import MarimoPath

if TYPE_CHECKING:
    from pathlib import Path


def _write_markdown_notebook(path: Path) -> None:
    lines = [
        "---",
        "marimo-version: 0.0.0",
        "---",
        "",
        "```python {.marimo}",
        "x = 1",
        "```",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


@pytest.mark.parametrize(
    ("source_name", "flavor", "download_filename", "expected", "absent"),
    [
        ("source.qmd", None, "source.qmd", "```{marimo .python", None),
        ("source.myst.md", None, "source.myst.md", "```{marimo} python", None),
        ("source.myst.md", "pymdown", "source.md", "```python", "```{marimo}"),
    ],
)
def test_export_as_md_uses_source_markdown_filename(
    tmp_path: Path,
    source_name: str,
    flavor: MarkdownFlavorName | None,
    download_filename: str,
    expected: str,
    absent: str | None,
) -> None:
    notebook = tmp_path / source_name
    _write_markdown_notebook(notebook)

    result = export_as_md(MarimoPath(notebook), flavor=flavor)

    assert result.download_filename == download_filename
    assert expected in result.text
    if absent:
        assert absent not in result.text


@pytest.mark.parametrize(
    ("filename", "flavor", "download_filename", "expected", "absent"),
    [
        ("custom.qmd", None, "custom.qmd", "```{marimo .python", None),
        (
            "custom.qmd",
            "pymdown",
            "custom.md",
            "```python",
            "```{marimo .python",
        ),
        (None, "qmd", "notebook.qmd", "```{marimo .python", None),
        (None, "mystmd", "notebook.myst.md", "```{marimo} python", None),
    ],
)
def test_export_as_md_uses_requested_filename_and_flavor(
    temp_marimo_file: str,
    tmp_path: Path,
    filename: str | None,
    flavor: MarkdownFlavorName | None,
    download_filename: str,
    expected: str,
    absent: str | None,
) -> None:
    output = str(tmp_path / filename) if filename else None

    result = export_as_md(
        MarimoPath(temp_marimo_file),
        flavor=flavor,
        filename=output,
    )

    assert result.download_filename == download_filename
    assert expected in result.text
    if absent:
        assert absent not in result.text
