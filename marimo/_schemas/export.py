# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import msgspec

from marimo._messaging.mimetypes import MimeBundleTuple
from marimo._schemas.export_options import (
    ExportPDFPreset,
    HTMLExportOptions,
    PDFRasterServer,
)
from marimo._types.ids import CellId_t


class ExportAsHTMLRequest(msgspec.Struct, rename="camel"):
    download: bool
    files: list[str]
    include_code: bool
    asset_url: str | None = None


def to_html_export_options(
    request: ExportAsHTMLRequest,
) -> HTMLExportOptions:
    return HTMLExportOptions(
        files=tuple(request.files),
        include_code=request.include_code,
        asset_url=request.asset_url,
    )


class ExportAsScriptRequest(msgspec.Struct, rename="camel"):
    download: bool


class ExportAsIPYNBRequest(msgspec.Struct, rename="camel"):
    download: bool


class ExportAsMarkdownRequest(msgspec.Struct, rename="camel"):
    download: bool


class ExportAsPDFRequest(msgspec.Struct, rename="camel"):
    webpdf: bool
    preset: ExportPDFPreset = "document"
    include_inputs: bool = False
    rasterize_outputs: bool = True
    raster_scale: float = 4.0
    raster_server: PDFRasterServer = "static"


class UpdateCellOutputsRequest(msgspec.Struct, rename="camel"):
    cell_ids_to_output: dict[CellId_t, MimeBundleTuple]
