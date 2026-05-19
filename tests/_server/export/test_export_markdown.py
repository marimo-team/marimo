from __future__ import annotations

from typing import TYPE_CHECKING

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


def test_export_as_md_infers_qmd_extension_from_source_path(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "source.qmd"
    _write_markdown_notebook(notebook)

    result = export_as_md(MarimoPath(notebook))

    assert result.download_filename == "source.qmd"
    assert "```{marimo .python" in result.text


def test_export_as_md_infers_mystmd_extension_from_source_path(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "source.myst.md"
    _write_markdown_notebook(notebook)

    result = export_as_md(MarimoPath(notebook))

    assert result.download_filename == "source.myst.md"
    assert "```{marimo} python" in result.text


def test_export_as_md_explicit_pymdown_strips_mystmd_suffix(
    tmp_path: Path,
) -> None:
    notebook = tmp_path / "source.myst.md"
    _write_markdown_notebook(notebook)

    result = export_as_md(MarimoPath(notebook), flavor="pymdown")

    assert result.download_filename == "source.md"
    assert "```{marimo} python" not in result.text


def test_export_as_md_uses_qmd_extension_for_qmd_flavor(
    temp_marimo_file: str,
) -> None:
    result = export_as_md(MarimoPath(temp_marimo_file), flavor="qmd")

    assert result.download_filename == "notebook.qmd"
    assert "```{marimo .python" in result.text


def test_export_as_md_uses_mystmd_extension_for_mystmd_flavor(
    temp_marimo_file: str,
) -> None:
    result = export_as_md(MarimoPath(temp_marimo_file), flavor="mystmd")

    assert result.download_filename == "notebook.myst.md"
    assert "```{marimo} python" in result.text


def test_export_as_md_infers_qmd_extension_from_filename(
    temp_marimo_file: str, tmp_path: Path
) -> None:
    output = tmp_path / "custom.qmd"

    result = export_as_md(MarimoPath(temp_marimo_file), filename=str(output))

    assert result.download_filename == "custom.qmd"
    assert "```{marimo .python" in result.text


def test_export_as_md_explicit_flavor_controls_extension(
    temp_marimo_file: str, tmp_path: Path
) -> None:
    output = tmp_path / "custom.qmd"

    result = export_as_md(
        MarimoPath(temp_marimo_file),
        flavor="pymdown",
        filename=str(output),
    )

    assert result.download_filename == "custom.md"
    assert "```{marimo .python" not in result.text
