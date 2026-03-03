# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Literal, Optional

import msgspec

from marimo._messaging.mimetypes import MimeBundleTuple
from marimo._types.ids import CellId_t


class ExportAsHTMLRequest(msgspec.Struct, rename="camel"):
    download: bool
    files: list[str]
    include_code: bool
    asset_url: Optional[str] = None


class ExportAsScriptRequest(msgspec.Struct, rename="camel"):
    download: bool


class ExportAsIPYNBRequest(msgspec.Struct, rename="camel"):
    download: bool


class ExportAsMarkdownRequest(msgspec.Struct, rename="camel"):
    download: bool


ExportPDFPreset = Literal["document", "slides"]


class ExportAsPDFRequest(msgspec.Struct, rename="camel"):
    webpdf: bool
    preset: ExportPDFPreset = "document"
    include_inputs: bool = False
    rasterize_outputs: bool = True
    raster_scale: float = 4.0
    raster_server: Literal["static", "live"] = "static"


class UpdateCellOutputsRequest(msgspec.Struct, rename="camel"):
    cell_ids_to_output: dict[CellId_t, MimeBundleTuple]
