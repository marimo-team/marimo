# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from marimo._server.export._raster_mime import MIME_TYPES_REPLACED_BY_PNG
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Mapping

    from nbformat.notebooknode import NotebookNode  # type: ignore


_DISPLAY_OUTPUT_TYPES = {"display_data", "execute_result"}
_PNG_DATA_URL_PREFIX = "data:image/png;base64,"


def _to_png_payload(data_url_or_payload: str) -> str | None:
    if data_url_or_payload.startswith(_PNG_DATA_URL_PREFIX):
        return data_url_or_payload.removeprefix(_PNG_DATA_URL_PREFIX)
    if data_url_or_payload.startswith("data:"):
        return None
    return data_url_or_payload


def inject_png_fallbacks_into_notebook(
    notebook: NotebookNode,
    png_fallbacks: Mapping[CellId_t, str],
) -> int:
    """Inject image/png fallbacks into a notebook node by code-cell id."""
    injected_count = 0

    cells = notebook.get("cells", [])
    if not isinstance(cells, list):
        return 0

    for cell in cells:
        if not isinstance(cell, dict):
            continue
        if cell.get("cell_type") != "code":
            continue

        raw_cell_id = cell.get("id")
        if not isinstance(raw_cell_id, str):
            continue
        cell_id = cast(CellId_t, raw_cell_id)

        data_url = png_fallbacks.get(cell_id)
        if not data_url:
            continue

        png_payload = _to_png_payload(data_url)
        if png_payload is None:
            continue

        outputs = cell.get("outputs")
        if not isinstance(outputs, list):
            continue

        display_output: dict[str, Any] | None = None
        for output in outputs:
            if not isinstance(output, dict):
                continue
            output_type = output.get("output_type")
            if output_type in _DISPLAY_OUTPUT_TYPES:
                display_output = output
                break

        if display_output is None:
            display_output = {
                "output_type": "display_data",
                "data": {},
                "metadata": {},
            }
            outputs.append(display_output)

        data = display_output.get("data")
        if not isinstance(data, dict):
            display_output["data"] = {}
            data = cast(dict[str, Any], display_output["data"])

        for mime_type in MIME_TYPES_REPLACED_BY_PNG:
            data.pop(mime_type, None)
        data["image/png"] = png_payload
        injected_count += 1

    return injected_count
