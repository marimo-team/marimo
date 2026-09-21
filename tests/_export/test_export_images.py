# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._export.file import export_html, export_pdf
from marimo._export.requests import (
    HTMLFileExportRequest,
    NotebookExecutionOptions,
    PDFFileExportRequest,
)
from marimo._schemas.export_options import HTMLExportOptions, PDFExportOptions
from marimo._utils.marimo_path import MarimoPath
from tests._server.templates.utils import parse_mount_config

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def image_notebook(tmp_path: Path) -> Path:
    public = tmp_path / "public"
    public.mkdir()
    (public / "image.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
        '<rect width="20" height="20" fill="blue"/></svg>'
    )
    notebook = tmp_path / "images.py"
    notebook.write_text("""import marimo
app = marimo.App()

@app.cell
def _():
    import marimo as mo
    return (mo,)

@app.cell
def _(mo):
    mo.md("![markdown](public/image.svg)")
    return

@app.cell
def _(mo):
    mo.image("./public/image.svg", alt="standalone")
    return

@app.cell
def _(mo):
    mo.vstack([mo.image("public/image.svg", alt="stacked")])
    return

@app.cell
def _(mo):
    _name = "dynamic"
    mo.md(f"![{_name}](public/image.svg)")
    return
""")
    return notebook


async def test_html_export_inlines_rendered_markdown_images(
    image_notebook: Path,
) -> None:
    result = await export_html(
        HTMLFileExportRequest(
            path=MarimoPath(image_notebook),
            options=HTMLExportOptions(files=(), include_code=True),
            execution=NotebookExecutionOptions(cli_args={}, argv=None),
        )
    )
    assert not result.did_error
    cells = parse_mount_config(result.text)["session"]["cells"]
    outputs = [cell["outputs"][0]["data"] for cell in cells[1:]]
    encoded = base64.b64encode(
        (image_notebook.parent / "public" / "image.svg").read_bytes()
    ).decode()
    for output in outputs:
        html = next(iter(output.values()))
        assert f"data:image/svg+xml;base64,{encoded}" in html
        assert "public/image.svg" not in html


@pytest.mark.requires("nbformat", "nbconvert")
@pytest.mark.parametrize("include_outputs", [True, False])
async def test_webpdf_inlines_images_relative_to_notebook(
    image_notebook: Path, include_outputs: bool
) -> None:
    from bs4 import BeautifulSoup
    from nbconvert import WebPDFExporter

    with (
        patch("marimo._export.exporter.require_export_dependencies"),
        patch("marimo._export._nbconvert.sys.platform", "linux"),
        patch.object(
            WebPDFExporter, "run_playwright", return_value=b"pdf"
        ) as print_pdf,
    ):
        result = await export_pdf(
            PDFFileExportRequest(
                path=MarimoPath(image_notebook),
                options=PDFExportOptions(
                    preset="document", include_inputs=False, webpdf=True
                ),
                execution=(
                    NotebookExecutionOptions(cli_args={}, argv=None)
                    if include_outputs
                    else None
                ),
            )
        )

    assert result is not None
    assert not result.did_error
    html = BeautifulSoup(print_pdf.call_args.args[0], "html.parser")
    images = html.find_all("img")
    assert [image["alt"] for image in images] == (
        ["markdown", "standalone", "stacked", "dynamic"]
        if include_outputs
        else ["markdown"]
    )
    expected = (image_notebook.parent / "public" / "image.svg").read_bytes()
    for image in images:
        prefix, encoded = image["src"].split(",", 1)
        assert prefix == "data:image/svg+xml;base64"
        assert base64.b64decode(encoded) == expected


@pytest.mark.requires("nbformat", "nbconvert")
def test_webpdf_resolves_virtual_images_before_spawning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import nbformat

    from marimo._export._nbconvert import _render_webpdf
    from marimo._runtime.virtual_file import (
        InMemoryStorage,
        VirtualFileStorageManager,
    )

    # Import optional dependencies before simulating the Windows branch.
    pytest.importorskip("nbconvert")
    storage = InMemoryStorage()
    storage.store("image.svg", b"<svg/>")
    monkeypatch.setattr(VirtualFileStorageManager(), "storage", storage)
    notebook = nbformat.v4.new_notebook(
        cells=[
            nbformat.v4.new_code_cell(
                outputs=[
                    nbformat.v4.new_output(
                        "display_data",
                        data={"text/html": '<img src="./@file/6-image.svg">'},
                    )
                ]
            )
        ]
    )
    with (
        patch("marimo._export._nbconvert.sys.platform", "win32"),
        patch("concurrent.futures.ProcessPoolExecutor") as pool,
    ):
        worker = pool.return_value.__enter__.return_value
        worker.submit.return_value.result.return_value = b"pdf"
        assert _render_webpdf(notebook, include_inputs=False) == b"pdf"

    html = worker.submit.call_args.args[1]
    assert 'src="data:image/svg+xml;base64,PHN2Zy8+"' in html
    assert "./@file/" not in html
