from __future__ import annotations

import pytest

from marimo._server.export._nbformat_png_fallbacks import (
    inject_png_fallbacks_into_notebook,
)

nbformat = pytest.importorskip("nbformat")


def test_inject_png_fallbacks_replaces_rasterized_mimetypes() -> None:
    notebook = nbformat.v4.new_notebook()
    cell = nbformat.v4.new_code_cell("print('x')", id="cell-1")
    cell.outputs = [
        nbformat.v4.new_output(
            "display_data",
            data={
                "text/html": "<div>hello</div>",
                "text/plain": "hello",
                "application/vnd.vega.v5+json": {"mark": "point"},
            },
            metadata={},
        )
    ]
    notebook.cells = [cell]

    injected = inject_png_fallbacks_into_notebook(
        notebook,
        png_fallbacks={"cell-1": "data:image/png;base64,ZmFrZQ=="},
    )

    assert injected == 1
    data = notebook.cells[0].outputs[0]["data"]
    assert "text/html" not in data
    assert "text/plain" not in data
    assert "application/vnd.vega.v5+json" not in data
    assert data["image/png"] == "ZmFrZQ=="


def test_inject_png_fallbacks_appends_display_output_when_missing() -> None:
    notebook = nbformat.v4.new_notebook()
    cell = nbformat.v4.new_code_cell("print('x')", id="cell-2")
    cell.outputs = []
    notebook.cells = [cell]

    injected = inject_png_fallbacks_into_notebook(
        notebook,
        png_fallbacks={"cell-2": "data:image/png;base64,YWJj"},
    )

    assert injected == 1
    assert len(notebook.cells[0].outputs) == 1
    output = notebook.cells[0].outputs[0]
    assert output["output_type"] == "display_data"
    assert output["data"]["image/png"] == "YWJj"


def test_inject_png_fallbacks_keeps_existing_plain_payload() -> None:
    notebook = nbformat.v4.new_notebook()
    cell = nbformat.v4.new_code_cell("print('x')", id="cell-3")
    cell.outputs = [
        nbformat.v4.new_output("display_data", data={}, metadata={})
    ]
    notebook.cells = [cell]

    injected = inject_png_fallbacks_into_notebook(
        notebook,
        png_fallbacks={"cell-3": "YWJj"},
    )

    assert injected == 1
    assert notebook.cells[0].outputs[0]["data"]["image/png"] == "YWJj"
