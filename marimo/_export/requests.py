# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import AbstractContextManager
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path  # noqa: TC003
from typing import Protocol

from marimo._ast.app import InternalApp
from marimo._ast.app_config import _AppConfig
from marimo._config.config import DisplayConfig, SharingConfig
from marimo._export._status import PDFExportStatusCallback
from marimo._runtime.commands import SerializedCLIArgs
from marimo._schemas.export_options import (
    HTMLExportOptions,
    IPYNBExportOptions,
    MarkdownExportOptions,
    NotebookExportSnapshot,
    PDFExportOptions,
    PDFRasterizationOptions,
    WASMExportOptions,
)
from marimo._schemas.notebook import NotebookV1
from marimo._schemas.serialization import NotebookSerialization
from marimo._schemas.session import NotebookSessionV1
from marimo._session.notebook import AppFileManager
from marimo._session.state.session_view import SessionView
from marimo._types.ids import CellId_t
from marimo._utils.marimo_path import MarimoPath

LivePageURLProvider = Callable[[], AbstractContextManager[str]]


class TextWriter(Protocol):
    def write(self, value: str, /) -> object: ...


@dataclass(kw_only=True)
class ExportResult:
    contents: bytes | str
    download_filename: str
    did_error: bool

    @cached_property
    def bytez(self) -> bytes:
        """Return UTF-8 encoded bytes (cached)."""
        if isinstance(self.contents, bytes):
            return self.contents
        return self.contents.encode("utf-8")

    @cached_property
    def text(self) -> str:
        """Return UTF-8 decoded text (cached)."""
        if isinstance(self.contents, str):
            return self.contents
        return self.contents.decode("utf-8")


@dataclass(frozen=True, kw_only=True)
class ScriptExportRequest:
    notebook: NotebookSerialization


@dataclass(frozen=True, kw_only=True)
class MarkdownExportRequest:
    notebook: NotebookSerialization
    options: MarkdownExportOptions


@dataclass(frozen=True, kw_only=True)
class HTMLExportRequest:
    filename: str | None
    app_code: str
    app_config: _AppConfig
    snapshot: NotebookExportSnapshot
    display_config: DisplayConfig
    options: HTMLExportOptions
    sharing_config: SharingConfig | None = None


@dataclass(frozen=True, kw_only=True)
class IPYNBExportRequest:
    app: InternalApp
    options: IPYNBExportOptions
    session_view: SessionView | None = None


@dataclass(frozen=True, kw_only=True)
class WASMExportRequest:
    filename: str | None
    app_config: _AppConfig
    display_config: DisplayConfig
    code: str
    options: WASMExportOptions
    session_snapshot: NotebookSessionV1 | None = None
    notebook_snapshot: NotebookV1 | None = None
    sharing_config: SharingConfig | None = None


@dataclass(frozen=True, kw_only=True)
class PDFExportRequest:
    app: InternalApp
    session_view: SessionView | None
    options: PDFExportOptions
    png_fallbacks: Mapping[CellId_t, str] | None = None
    status_callback: PDFExportStatusCallback | None = None


@dataclass(frozen=True, kw_only=True)
class NotebookExecutionOptions:
    cli_args: SerializedCLIArgs
    argv: list[str] | None
    quiet: bool = False
    persist_session: bool = True
    cache_export: bool = False
    stderr: TextWriter | None = None


@dataclass(frozen=True, kw_only=True)
class RunNotebookRequest:
    file_manager: AppFileManager
    options: NotebookExecutionOptions


@dataclass(frozen=True, kw_only=True)
class ScriptFileExportRequest:
    path: MarimoPath


@dataclass(frozen=True, kw_only=True)
class MarkdownFileExportRequest:
    path: MarimoPath
    options: MarkdownExportOptions


@dataclass(frozen=True, kw_only=True)
class IPYNBFileExportRequest:
    path: MarimoPath
    options: IPYNBExportOptions
    execution: NotebookExecutionOptions | None = None
    stderr: TextWriter | None = None


@dataclass(frozen=True, kw_only=True)
class HTMLFileExportRequest:
    path: MarimoPath
    options: HTMLExportOptions
    execution: NotebookExecutionOptions | None = None


@dataclass(frozen=True, kw_only=True)
class WASMFileExportRequest:
    path: MarimoPath
    options: WASMExportOptions
    execution: NotebookExecutionOptions | None = None
    cache_export_dir: Path | None = None
    code_transform: Callable[[str], str] | None = None
    stdout: TextWriter | None = None


@dataclass(frozen=True, kw_only=True)
class PDFFileExportRequest:
    path: MarimoPath
    options: PDFExportOptions
    rasterization: PDFRasterizationOptions | None = None
    execution: NotebookExecutionOptions | None = None
    live_page_url: LivePageURLProvider | None = None
    status_callback: PDFExportStatusCallback | None = None


@dataclass(frozen=True, kw_only=True)
class PDFRasterizationRequest:
    app: InternalApp
    session_view: SessionView
    filename: str | None
    filepath: str | None
    options: PDFRasterizationOptions
    live_page_url: LivePageURLProvider | None = None
    status_callback: PDFExportStatusCallback | None = None


@dataclass(frozen=True, kw_only=True)
class ReactiveHTMLFileExportRequest:
    path: MarimoPath
    include_code: bool


@dataclass(frozen=True, kw_only=True)
class CacheBundleRequest:
    notebook_path: MarimoPath
    output_directory: Path
    stdout: TextWriter | None = None
