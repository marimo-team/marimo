# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, get_args

from marimo._convert.markdown.flavor.base import MarkdownFlavorName
from marimo._messaging.notification import ModelLifecycleNotification
from marimo._schemas.notebook import NotebookV1
from marimo._schemas.session import NotebookSessionV1

ExportPDFPreset = Literal["document", "slides"]
IPYNBSortMode = Literal["top-down", "topological"]
PDFRasterServer = Literal["static", "live"]
ServerExportFormat = Literal["html", "markdown", "ipynb", "pdf", "script"]
ExportSetupRequirementName = Literal["playwright-chromium"]
SERVER_EXPORT_FORMATS: tuple[ServerExportFormat, ...] = get_args(
    ServerExportFormat
)
WASMMode = Literal["edit", "run"]


@dataclass(frozen=True, kw_only=True)
class NotebookExportSnapshot:
    notebook: NotebookV1
    session: NotebookSessionV1
    model_notifications: tuple[ModelLifecycleNotification, ...] = ()


@dataclass(frozen=True, kw_only=True)
class HTMLExportOptions:
    files: tuple[str, ...]
    include_code: bool
    asset_url: str | None = None


@dataclass(frozen=True, kw_only=True)
class MarkdownExportOptions:
    flavor: MarkdownFlavorName | None = None
    filename: str | None = None
    source_filename: str | None = None


@dataclass(frozen=True, kw_only=True)
class WASMExportOptions:
    mode: WASMMode
    show_code: bool
    asset_url: str | None = None


@dataclass(frozen=True, kw_only=True)
class IPYNBExportOptions:
    sort_mode: IPYNBSortMode


@dataclass(frozen=True, kw_only=True)
class PDFRasterizationOptions:
    enabled: bool = True
    scale: float = 4.0
    server_mode: PDFRasterServer = "static"


@dataclass(frozen=True, kw_only=True)
class PDFExportOptions:
    webpdf: bool
    preset: ExportPDFPreset
    include_inputs: bool
