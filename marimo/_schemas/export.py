# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal

import msgspec

from marimo._convert.markdown.flavor.base import MarkdownFlavorName
from marimo._messaging.mimetypes import MimeBundleTuple
from marimo._schemas.export_options import (
    ExportPDFPreset,
    HTMLExportOptions,
    MarkdownExportOptions,
    PDFRasterServer,
    ServerExportFormat,
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
    flavor: MarkdownFlavorName | None = None


class AutoExportAsMarkdownRequest(msgspec.Struct, rename="camel"):
    download: bool


def to_markdown_export_options(
    request: ExportAsMarkdownRequest,
    *,
    filename: str | None = None,
    source_filename: str | None = None,
) -> MarkdownExportOptions:
    return MarkdownExportOptions(
        flavor=request.flavor,
        filename=filename,
        source_filename=source_filename,
    )


class ExportAsPDFRequest(msgspec.Struct, rename="camel"):
    webpdf: bool
    preset: ExportPDFPreset = "document"
    include_inputs: bool = False
    rasterize_outputs: bool = True
    raster_scale: float = 4.0
    raster_server: PDFRasterServer = "static"


class ExportedFile(msgspec.Struct, rename="camel"):
    contents: str
    filename: str
    media_type: str


class ExportFormatAvailability(msgspec.Struct, rename="camel", frozen=True):
    format: ServerExportFormat
    dependencies_available: bool
    missing_packages: list[str]


class ExportAvailabilityResponse(msgspec.Struct, rename="camel", frozen=True):
    source: Literal["server"]
    formats: list[ExportFormatAvailability]


class UpdateCellOutputsRequest(msgspec.Struct, rename="camel"):
    cell_ids_to_output: dict[CellId_t, MimeBundleTuple]
