# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import base64
import mimetypes
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Optional, cast

from marimo import _loggers
from marimo._ast.app import InternalApp
from marimo._ast.names import DEFAULT_CELL_NAME
from marimo._config.config import (
    DEFAULT_CONFIG,
    DisplayConfig,
    MarimoConfig,
)
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._config.utils import deep_copy
from marimo._convert.common.dom_traversal import (
    replace_virtual_files_with_data_uris,
)
from marimo._convert.common.filename import (
    get_download_filename,
    get_filename,
)
from marimo._convert.ipynb.from_ir import convert_from_ir_to_ipynb
from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import KnownMimeType
from marimo._runtime.virtual_file import read_virtual_file
from marimo._schemas.notebook import NotebookV1
from marimo._schemas.session import NotebookSessionV1
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._server.templates.templates import (
    static_notebook_template,
    wasm_notebook_template,
)
from marimo._server.tokens import SkewProtectionToken
from marimo._session.state.serialize import (
    serialize_notebook,
    serialize_session_view,
)
from marimo._session.state.session_view import SessionView
from marimo._types.ids import CellId_t
from marimo._utils import async_path
from marimo._utils.code import hash_code
from marimo._utils.data_uri import build_data_url
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import marimo_package_path
from marimo._version import __version__

if TYPE_CHECKING:
    from collections.abc import Mapping

LOGGER = _loggers.marimo_logger()

# Root directory for static assets
ROOT = (marimo_package_path() / "_static").resolve()

VIRTUAL_FILE_ALLOWED_ATTRIBUTES = {"src"}
# We don't include video/audio as it can potentially be too much data
# and the current use-cases are for images.
VIRTUAL_FILE_ALLOWED_TAGS = {"img"}


class Exporter:
    # Virtual file URL format constants
    _VIRTUAL_FILE_PATTERN = "./@file/"
    _VIRTUAL_FILE_PREFIX_WITH_SLASH = "/@file/"

    def export_as_html(
        self,
        *,
        filename: Optional[str],
        app: InternalApp,
        session_view: SessionView,
        display_config: DisplayConfig,
        request: ExportAsHTMLRequest,
    ) -> tuple[str, str]:
        index_html = get_html_contents()
        filename = get_filename(filename)

        # Configure notebook with display settings
        config = self._prepare_display_config(display_config)

        # Serialize notebook state
        session_snapshot = serialize_session_view(
            session_view, cell_ids=app.cell_manager.cell_ids()
        )
        notebook_snapshot = serialize_notebook(session_view, app.cell_manager)

        # Replace virtual files in HTML outputs with data URIs
        session_snapshot, replaced_files = self._inline_virtual_files(
            session_snapshot
        )

        app_code = app.to_py()

        # Prepare code for export
        code = self._prepare_code(
            request.include_code, app_code, notebook_snapshot, session_snapshot
        )

        # Build fallback virtual_files dict for files not in HTML outputs
        virtual_files = self._build_virtual_files_dict(
            request.files, replaced_files
        )

        # Generate final HTML
        code_hash = hash_code(app_code)
        html = static_notebook_template(
            html=index_html,
            user_config=config,
            config_overrides={},
            server_token=SkewProtectionToken("static"),
            app_config=app.config,
            filepath=filename,
            code=code,
            code_hash=code_hash,
            session_snapshot=session_snapshot,
            notebook_snapshot=notebook_snapshot,
            files=virtual_files,
            model_notifications=session_view.get_model_notifications(),
            asset_url=request.asset_url,
        )

        download_filename = get_download_filename(filename, "html")
        return html, download_filename

    def _prepare_display_config(
        self, display_config: DisplayConfig
    ) -> MarimoConfig:
        """Prepare config with display settings for static notebook."""
        # We only want pass the display config in the static notebook,
        # since we use:
        # - display.theme
        # - display.cell_output
        config = deep_copy(DEFAULT_CONFIG)
        config["display"] = display_config
        return cast(MarimoConfig, config)

    def _inline_virtual_files(
        self, session_snapshot: NotebookSessionV1
    ) -> tuple[NotebookSessionV1, set[str]]:
        """Replace virtual file URLs with data URIs in session outputs.

        Returns:
            Tuple of (modified_snapshot, set_of_replaced_files)
        """
        replaced_files: set[str] = set()

        for cell in session_snapshot["cells"]:
            for output in cell["outputs"]:
                if output["type"] != "data":
                    continue

                for mime_type, data in output["data"].items():
                    if not isinstance(data, str):
                        continue
                    if self._VIRTUAL_FILE_PATTERN not in data:
                        continue

                    processed, files = replace_virtual_files_with_data_uris(
                        data,
                        allowed_tags=VIRTUAL_FILE_ALLOWED_TAGS,
                        allowed_attributes=VIRTUAL_FILE_ALLOWED_ATTRIBUTES,
                    )
                    replaced_files.update(files)
                    output["data"][mime_type] = processed

        return session_snapshot, replaced_files

    def _prepare_code(
        self,
        include_code: bool,
        app_code: str,
        notebook_snapshot: NotebookV1,
        session_snapshot: NotebookSessionV1,
    ) -> str:
        """Prepare code for export, optionally clearing it."""
        if not include_code:
            # Clear code and console outputs
            for nb_cell in notebook_snapshot["cells"]:
                nb_cell["code"] = ""
                nb_cell["name"] = DEFAULT_CELL_NAME
            for snapshot_cell in session_snapshot["cells"]:
                snapshot_cell["console"] = []
            return ""

        return app_code

    def _normalize_virtual_file_url(self, url: str) -> str:
        """Normalize virtual file URL format from /@file/ to ./@file/."""
        if url.startswith(self._VIRTUAL_FILE_PATTERN):
            return url
        return url.replace(
            self._VIRTUAL_FILE_PREFIX_WITH_SLASH,
            self._VIRTUAL_FILE_PATTERN,
            1,
        )

    def _build_virtual_files_dict(
        self, file_urls: list[str], replaced_files: set[str]
    ) -> dict[str, str]:
        """Build dict of virtual files not already inlined in HTML.

        Args:
            file_urls: List of virtual file URLs from request
            replaced_files: Set of URLs already replaced in HTML outputs

        Returns:
            Dict mapping file URLs to data URIs
        """
        virtual_files: dict[str, str] = {}

        for file_url in file_urls:
            # Skip files already replaced in HTML outputs
            normalized_url = self._normalize_virtual_file_url(file_url)
            if normalized_url in replaced_files:
                LOGGER.debug(
                    "Skipping virtual file %s (already inlined in HTML)",
                    file_url,
                )
                continue

            # Process virtual file URLs
            if self._VIRTUAL_FILE_PREFIX_WITH_SLASH not in file_url:
                continue

            data_uri = self._read_virtual_file_as_data_uri(file_url)
            if data_uri:
                virtual_files[file_url] = data_uri

        return virtual_files

    def _read_virtual_file_as_data_uri(self, file_url: str) -> Optional[str]:
        """Read a virtual file and convert it to a data URI.

        Args:
            file_url: Virtual file URL in format /@file/{byte_length}-{filename}

        Returns:
            Data URI string, or None if file cannot be read
        """
        # Extract byte_length and filename from URL
        # Format: /@file/{byte_length}-{filename}
        prefix_len = len(self._VIRTUAL_FILE_PREFIX_WITH_SLASH)
        virtual_file = file_url[prefix_len:]

        try:
            byte_length_str, basename = virtual_file.split("-", 1)
            buffer_contents = read_virtual_file(basename, int(byte_length_str))
        except Exception as e:
            LOGGER.warning(
                "File not found in export: %s. Error: %s", file_url, e
            )
            return None

        mime_type = mimetypes.guess_type(basename)[0] or "text/plain"
        return build_data_url(
            cast(KnownMimeType, mime_type),
            base64.b64encode(buffer_contents),
        )

    def export_as_ipynb(
        self,
        app: InternalApp,
        *,
        sort_mode: Literal["top-down", "topological"],
        session_view: Optional[SessionView] = None,
    ) -> str:
        """Export notebook as .ipynb, optionally including outputs if session_view provided."""
        return convert_from_ir_to_ipynb(
            app, sort_mode=sort_mode, session_view=session_view
        )

    def export_as_wasm(
        self,
        *,
        app: InternalApp,
        filename: Optional[str],
        display_config: DisplayConfig,
        code: str,
        mode: Literal["edit", "run"],
        show_code: bool,
        asset_url: Optional[str] = None,
    ) -> tuple[str, str]:
        """Export notebook as a WASM-powered standalone HTML file."""
        index_html = get_html_contents()
        filename = get_filename(filename)

        # We only want to pass the display config in the static notebook
        config: MarimoConfig = deep_copy(DEFAULT_CONFIG)
        config["display"] = display_config
        # Remove autosave
        config["save"]["autosave"] = "off"

        html = wasm_notebook_template(
            html=index_html,
            version=__version__,
            filename=filename,
            mode=mode,
            user_config=config,
            config_overrides={},
            app_config=app.config,
            code=code,
            asset_url=asset_url,
            show_code=show_code,
        )

        download_filename = get_download_filename(filename, "wasm.html")

        return html, download_filename

    def export_as_pdf(
        self,
        *,
        app: InternalApp,
        session_view: SessionView | None,
        png_fallbacks: Mapping[CellId_t, str] | None = None,
        webpdf: bool,
        include_inputs: bool = True,
    ) -> bytes | None:
        """Export notebook as a PDF.

        Args:
            app: The app to export
            session_view: The session view to export. If None, outputs are not included.
            png_fallbacks: Optional cell-id keyed image/png fallbacks to
                inject into notebook outputs before nbconvert.
            include_inputs: Whether to include code cell inputs in the export.
            webpdf: If False, tries standard PDF export (pandoc + TeX) first,
                falling back to webpdf on failure. If True, uses webpdf
                directly.

        Returns:
            PDF data
        """
        # We check for all dependencies upfront since standard export failing
        # falls back to webpdf (which requires playwright).
        # We don't want users to reinstall again after the first failure.
        # Webpdf is generally more resilient to errors than standard export.
        DependencyManager.require_many(
            "for PDF export",
            DependencyManager.nbformat,
            DependencyManager.nbconvert,
            DependencyManager.playwright,
        )

        ipynb_json_str = self.export_as_ipynb(
            app=app, sort_mode="top-down", session_view=session_view
        )

        import nbformat

        notebook = nbformat.reads(ipynb_json_str, as_version=4)  # type: ignore[no-untyped-call]
        if png_fallbacks:
            from marimo._server.export._nbformat_png_fallbacks import (
                inject_png_fallbacks_into_notebook,
            )

            inject_png_fallbacks_into_notebook(
                notebook,
                png_fallbacks=png_fallbacks,
            )

        # Try standard PDF export first (requires pandoc + TeX)
        # and fall back to webpdf if it fails
        if not webpdf:
            try:
                from nbconvert import (  # type: ignore[import-not-found]
                    PDFExporter,
                )

                exporter = PDFExporter()
                exporter.exclude_input = not include_inputs
                pdf_data, _resources = exporter.from_notebook_node(notebook)
                if isinstance(pdf_data, bytes):
                    return pdf_data
                LOGGER.error("PDF data is not bytes: %s", pdf_data)
                return None
            except OSError as e:
                LOGGER.warning(
                    "Standard PDF export failed, falling back to webpdf. Error: %s",
                    e,
                )

        from nbconvert import WebPDFExporter  # type: ignore[import-not-found]

        web_exporter = WebPDFExporter()
        web_exporter.exclude_input = not include_inputs
        web_exporter.allow_chromium_download = True
        pdf_data, _resources = web_exporter.from_notebook_node(notebook)

        if not isinstance(pdf_data, bytes):
            LOGGER.error("PDF data is not bytes: %s", pdf_data)
            return None
        return pdf_data

    async def export_as_slides_pdf(
        self,
        *,
        app: InternalApp,
        session_view: SessionView | None,
        png_fallbacks: Mapping[CellId_t, str] | None = None,
        include_inputs: bool = True,
    ) -> bytes | None:
        """Export a slides notebook as PDF using reveal.js + Playwright.

        Converts to iPynb with Jupyter slideshow metadata, renders to
        reveal.js HTML via nbconvert's SlidesExporter, then uses
        Playwright (async API) to print to PDF via ?print-pdf mode.

        Must be called from an async context since Playwright's async API
        is required when running inside an asyncio event loop.

        Args:
            app: The app to export
            session_view: The session view to export. If None, outputs
                are not included.
            png_fallbacks: Optional cell-id keyed image/png fallbacks to
                inject into notebook outputs before conversion.
            include_inputs: Whether to include code cell inputs.

        Returns:
            PDF data
        """
        DependencyManager.require_many(
            "for PDF export",
            DependencyManager.nbformat,
            DependencyManager.nbconvert,
            DependencyManager.playwright,
        )

        ipynb_json_str = self.export_as_ipynb(
            app=app, sort_mode="top-down", session_view=session_view
        )

        import nbformat

        notebook = nbformat.reads(ipynb_json_str, as_version=4)  # type: ignore[no-untyped-call]
        if png_fallbacks:
            from marimo._server.export._nbformat_png_fallbacks import (
                inject_png_fallbacks_into_notebook,
            )

            inject_png_fallbacks_into_notebook(
                notebook,
                png_fallbacks=png_fallbacks,
            )
        return await self._export_slides_as_pdf(notebook, include_inputs)

    @staticmethod
    def _to_file_uri(path: str) -> str:
        import os
        from urllib.request import pathname2url

        return f"file://{pathname2url(os.path.abspath(path))}"

    @staticmethod
    def _slide_type_for_cell(cell: Any, include_inputs: bool) -> str:
        if include_inputs:
            return "slide"
        cell_type = str(cell.get("cell_type", ""))
        if cell_type != "code":
            return "slide"
        outputs = cell.get("outputs", [])
        if isinstance(outputs, list) and outputs:
            return "slide"
        return "skip"

    @staticmethod
    async def _export_slides_as_pdf(
        notebook: Any,
        include_inputs: bool,
    ) -> bytes | None:
        """Render slides notebook to PDF using Playwright async API."""
        import os
        import tempfile

        from nbconvert import SlidesExporter  # type: ignore[import-not-found]

        # Add slideshow metadata so each cell becomes a slide.
        for cell in notebook.cells:
            if "slideshow" not in cell.metadata:
                cell.metadata["slideshow"] = {}
            cell.metadata["slideshow"]["slide_type"] = (
                Exporter._slide_type_for_cell(cell, include_inputs)
            )

        # Convert to reveal.js HTML
        slides_exporter = SlidesExporter()
        slides_exporter.exclude_input = not include_inputs
        html_data, _resources = slides_exporter.from_notebook_node(notebook)

        # Write HTML to a temp file for Playwright to load
        with tempfile.NamedTemporaryFile(
            suffix=".html", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(html_data)
            temp_path = f.name

        try:
            from playwright.async_api import (  # type: ignore[import-not-found]
                async_playwright,
            )

            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch()
                try:
                    page = await browser.new_page()
                    # ?print-pdf tells reveal.js to use a linear print layout
                    temp_uri = Exporter._to_file_uri(temp_path)
                    await page.goto(
                        f"{temp_uri}?print-pdf",
                        wait_until="networkidle",
                    )
                    await page.evaluate(
                        """
                        () => {
                          const reveal = window.Reveal;
                          if (
                            reveal &&
                            typeof reveal.layout === "function"
                          ) {
                            reveal.layout();
                          }
                        }
                        """
                    )
                    await page.wait_for_timeout(300)
                    await page.add_style_tag(
                        content=(
                            ".pdf-page:last-of-type {"
                            " page-break-after: auto !important;"
                            " break-after: auto !important;"
                            "}"
                        )
                    )
                    pdf_data = await page.pdf(
                        print_background=True,
                        prefer_css_page_size=True,
                    )
                finally:
                    await browser.close()
        finally:
            try:
                os.unlink(temp_path)
            except OSError:
                LOGGER.debug("Failed to remove temp slide HTML: %s", temp_path)

        if not isinstance(pdf_data, bytes):
            LOGGER.error("Slides PDF data is not bytes: %s", pdf_data)
            return None
        return pdf_data

    def export_assets(
        self, directory: Path, ignore_index_html: bool = False
    ) -> None:
        # Copy assets to the same directory as the notebook
        dirpath = Path(directory)
        LOGGER.debug(f"Copying assets to {dirpath}")
        if not dirpath.exists():
            dirpath.mkdir(parents=True, exist_ok=True)

        import shutil

        shutil.copytree(
            ROOT,
            dirpath,
            dirs_exist_ok=True,
            ignore=(
                shutil.ignore_patterns("index.html")
                if ignore_index_html
                else None
            ),
        )

    def export_public_folder(
        self, directory: Path, marimo_file: MarimoPath
    ) -> bool:
        FOLDER_NAME = "public"
        public_dir = marimo_file.path.parent / FOLDER_NAME

        if public_dir.exists():
            import shutil

            # Copy public folder to the same directory as the notebook
            dirpath = Path(directory)
            if not dirpath.exists():
                dirpath.mkdir(parents=True, exist_ok=True)

            target_dir = dirpath / FOLDER_NAME
            if target_dir == public_dir:
                # Skip if source and target are the same
                return True

            LOGGER.debug(f"Copying public folder to {dirpath}")
            shutil.copytree(
                public_dir,
                target_dir,
                dirs_exist_ok=True,
            )
            return True

        return False


class AutoExporter:
    EXPORT_DIR = "__marimo__"

    def __init__(self) -> None:
        # Cache directories we've already created to avoid redundant checks
        self._created_dirs: set[Path] = set()
        # Thread pool for blocking I/O operations
        self._executor = ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="export"
        )

    async def _save_file(
        self, filename: Optional[str], content: str, extension: str
    ) -> None:
        directory = Path(get_filename(filename)).parent
        filename = get_download_filename(filename, extension)

        await self._ensure_export_dir_async(directory)
        filepath = directory / self.EXPORT_DIR / filename

        # Run blocking file I/O in thread pool
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            self._executor, self._write_file_sync, filepath, content
        )

    async def save_html(self, filename: Optional[str], html: str) -> None:
        await self._save_file(filename, html, "html")

    async def save_md(self, filename: Optional[str], markdown: str) -> None:
        await self._save_file(filename, markdown, "md")

    async def save_ipynb(self, filename: Optional[str], ipynb: str) -> None:
        await self._save_file(filename, ipynb, "ipynb")

    def _write_file_sync(self, filepath: Path, content: str) -> None:
        """Synchronous file write (runs in thread pool)"""
        if content == "":
            return
        filepath.write_text(content, encoding="utf-8")

    async def _ensure_export_dir_async(self, directory: Path) -> None:
        """Async directory creation with caching to avoid redundant checks"""
        export_dir = directory / self.EXPORT_DIR

        # Fast path: already created this directory
        if export_dir in self._created_dirs:
            return

        if not await async_path.exists(directory):
            raise FileNotFoundError(f"Directory {directory} does not exist")

        await async_path.mkdir(export_dir, parents=True, exist_ok=True)

        # Cache that we've created this directory
        self._created_dirs.add(export_dir)

    def cleanup(self) -> None:
        """Cleanup resources"""
        self._executor.shutdown(wait=False)


def get_html_contents() -> str:
    if GLOBAL_SETTINGS.DEVELOPMENT_MODE:
        import marimo._utils.requests as requests

        # Fetch from a CDN
        LOGGER.info(
            "Fetching index.html from jsdelivr because in development mode"
        )
        url = f"https://cdn.jsdelivr.net/npm/@marimo-team/frontend@{__version__}/dist/index.html"
        return requests.get(url).text()

    index_html = Path(ROOT) / "index.html"
    return index_html.read_text(encoding="utf-8")
