# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import msgspec

from marimo._convert.markdown.flavor.base import MarkdownFlavorName
from marimo._messaging.mimetypes import MimeBundleTuple
from marimo._runtime.layout.layout import LayoutConfig
from marimo._schemas.export_options import (
    ExportPDFPreset,
    ExportSetupRequirementName,
    HTMLExportOptions,
    IPYNBExportOptions,
    IPYNBSortMode,
    MarkdownExportOptions,
    PDFExportOptions,
    ServerExportFormat,
)
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Callable


class ExportAsHTMLRequest(msgspec.Struct, rename="camel"):
    """Request a static HTML export.

    `layout` carries the current client layout. An omitted field reads the
    saved layout file, `null` selects the vertical layout, and an object uses
    that serialized layout for this export.
    """

    download: bool
    files: list[str]
    include_code: bool
    asset_url: str | None = None
    layout: LayoutConfig | None | msgspec.UnsetType = msgspec.UNSET


def to_html_export_options(
    request: ExportAsHTMLRequest,
) -> HTMLExportOptions:
    return HTMLExportOptions(
        files=tuple(request.files),
        include_code=request.include_code,
        asset_url=request.asset_url,
    )


def to_html_export_layout(
    request: ExportAsHTMLRequest,
    *,
    fallback: Callable[[], LayoutConfig | None],
) -> LayoutConfig | None:
    if request.layout is msgspec.UNSET:
        return fallback()
    return request.layout


class ExportAsScriptRequest(msgspec.Struct, rename="camel"):
    download: bool


class ExportAsIPYNBRequest(msgspec.Struct, rename="camel"):
    download: bool
    sort_mode: IPYNBSortMode = "top-down"
    include_outputs: bool = True


class AutoExportAsIPYNBRequest(msgspec.Struct, rename="camel"):
    download: bool


def to_ipynb_export_options(
    request: ExportAsIPYNBRequest,
) -> IPYNBExportOptions:
    return IPYNBExportOptions(sort_mode=request.sort_mode)


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
    include_outputs: bool = True


def to_pdf_export_options(
    request: ExportAsPDFRequest,
) -> PDFExportOptions:
    return PDFExportOptions(
        webpdf=request.webpdf,
        preset=request.preset,
        include_inputs=request.include_inputs,
    )


class ExportedFile(msgspec.Struct, rename="camel"):
    contents: str
    filename: str
    media_type: str


class ExportSetupRequirement(msgspec.Struct, rename="camel", frozen=True):
    name: ExportSetupRequirementName
    command: str


class ExportFormatAvailability(msgspec.Struct, rename="camel", frozen=True):
    format: ServerExportFormat
    dependencies_available: bool
    missing_packages: list[str]
    missing_setup: list[ExportSetupRequirement]


class ExportAvailabilityResponse(msgspec.Struct, rename="camel", frozen=True):
    source: Literal["server"]
    formats: list[ExportFormatAvailability]


class InstallExportRequirementsRequest(msgspec.Struct, rename="camel"):
    format: ServerExportFormat


class UpdateCellOutputsRequest(msgspec.Struct, rename="camel"):
    cell_ids_to_output: dict[CellId_t, MimeBundleTuple]
