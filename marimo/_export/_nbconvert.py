# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from marimo._convert.common.dom_traversal import (
    replace_public_files_with_data_uris,
    replace_virtual_files_with_data_uris,
)
from marimo._convert.ipynb.from_ir import NBCONVERT_REMOVE_INPUT_TAG
from marimo._dependencies.dependencies import DependencyManager
from marimo._export._limits import MAX_VIRTUAL_FILE_INLINE_BYTES

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from traitlets.config import Config

T = TypeVar("T")


def inline_pdf_assets(html: str, filename: str | None) -> str:
    """Resolve notebook assets before Chromium opens HTML in a temp directory."""
    html, _ = replace_virtual_files_with_data_uris(
        html,
        allowed_tags={"img", "audio", "video", "source"},
        allowed_attributes={"src"},
        max_inline_bytes=MAX_VIRTUAL_FILE_INLINE_BYTES,
    )
    if filename is not None:
        html, _ = replace_public_files_with_data_uris(
            html,
            public_dir=Path(filename).resolve().parent / "public",
            max_inline_bytes=MAX_VIRTUAL_FILE_INLINE_BYTES,
        )
    return html


def _nbconvert_tag_remove_config() -> Config:
    """Build a traitlets config that strips inputs from cells tagged with
    `NBCONVERT_REMOVE_INPUT_TAG`. Used to honor `hide_code=True` in nbconvert
    exports."""
    from traitlets.config import Config

    config = Config()
    config.TagRemovePreprocessor.enabled = True
    config.TagRemovePreprocessor.remove_input_tags = (
        NBCONVERT_REMOVE_INPUT_TAG,
    )
    return config


# JupyterLab's stylesheet (shipped with nbconvert) styles the code input area
# with `overflow: hidden` and leaves the `<pre>` at the default `white-space:
# pre`. In JupyterLab that is fine because the editor scrolls; in a PDF there is
# no scrolling, so long lines are clipped and the text is lost entirely.
# Outputs already wrap (`.jp-OutputArea-output pre` sets `word-break`), so this
# only targets the input area.
#
# `!important` is required because this is inlined ahead of the JupyterLab
# rules; the slides PDF path overrides nbconvert styling the same way.
WEBPDF_CODE_WRAP_CSS = """\
/* marimo: wrap long code lines instead of clipping them (#9421) */
.jp-InputArea-editor {
  overflow: visible !important;
}
.jp-InputArea-editor .highlight pre {
  white-space: pre-wrap !important;
  overflow-wrap: anywhere !important;
}
"""


def _inline_code_wrap_css(nb: Any, resources: Any) -> tuple[Any, Any]:
    """Inline `WEBPDF_CODE_WRAP_CSS`, as an nbconvert preprocessor.

    Preprocessors run after nbconvert populates `resources`, so appending here
    is what gets the stylesheet into the rendered HTML.
    """
    inlining = resources.setdefault("inlining", {})
    inlining.setdefault("css", []).append(WEBPDF_CODE_WRAP_CSS)
    return nb, resources


def _render_webpdf_html(
    notebook: Any, include_inputs: bool, filename: str | None
) -> str:
    from nbconvert import HTMLExporter  # type: ignore[import-not-found]

    html_exporter = HTMLExporter(  # type: ignore[no-untyped-call]
        template_name="webpdf",
        config=_nbconvert_tag_remove_config(),
    )
    html_exporter.exclude_input = not include_inputs
    html_exporter.register_preprocessor(  # type: ignore[no-untyped-call]
        _inline_code_wrap_css, enabled=True
    )
    html, _resources = html_exporter.from_notebook_node(notebook)  # type: ignore[no-untyped-call]
    return inline_pdf_assets(html, filename)


async def print_pdf(page: Any, **options: Any) -> bytes:
    """Print a loaded Playwright page to PDF.

    The PDF carries an outline (bookmarks) of the page's headings when
    Playwright is 1.42 or newer, the first release with `tagged` and `outline`.
    """
    defaults: dict[str, Any] = {"print_background": True}
    if DependencyManager.playwright.has_at_version(
        min_version="1.42.0", quiet=True
    ):
        # Chromium builds the outline from the tagged structure tree, so
        # `outline` has no effect without `tagged`.
        defaults |= {"tagged": True, "outline": True}
    pdf: bytes = await page.pdf(**(defaults | options))
    return pdf


async def _print_webpdf_async(url: str) -> bytes:
    from playwright.async_api import (  # type: ignore[import-not-found]
        async_playwright,
    )

    from marimo._export.dependencies import _install_playwright_chromium
    from marimo._utils.async_path import isfile

    async with async_playwright() as playwright:
        if not await isfile(playwright.chromium.executable_path):
            await _install_playwright_chromium()
        browser = await playwright.chromium.launch()
        try:
            page = await browser.new_page()
            await page.emulate_media(media="print")
            await page.goto(url, wait_until="networkidle")
            # Give MathJax time to typeset after load (nbconvert's default
            # `page_render_timeout`).
            await page.wait_for_timeout(100)
            return await print_pdf(page)
        finally:
            await browser.close()


def run_playwright(main: Coroutine[Any, Any, T]) -> T:
    """Run Playwright code on a new event loop in the calling thread.

    Call it from a worker thread: the loop cannot share a thread with a running
    one, and Playwright blocks it while Chromium prints.
    """
    # marimo installs the Selector policy on Windows, whose loops cannot start
    # Playwright's driver subprocess.
    loop_factory = (
        asyncio.ProactorEventLoop  # type: ignore[attr-defined]
        if sys.platform == "win32"
        else None
    )
    with asyncio.Runner(loop_factory=loop_factory) as runner:
        return runner.run(main)


def run_playwright_on_html(
    html: str, main: Callable[[str], Coroutine[Any, Any, T]]
) -> T:
    """Write `html` to a temporary file and run `main(file_url)` on it.

    The file lives as long as this call, so a caller that stops waiting on a
    worker thread cannot remove the page while Chromium still loads it.
    """
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        # Load from a file URL so Chromium can read `file://` resources.
        path = Path(directory) / "page.html"
        path.write_text(html, encoding="utf-8")
        return run_playwright(main(path.as_uri()))


def _print_webpdf(html: str) -> bytes:
    return run_playwright_on_html(html, _print_webpdf_async)


def _render_webpdf(
    notebook: Any, include_inputs: bool, filename: str | None = None
) -> bytes:
    from concurrent.futures import ThreadPoolExecutor

    html = _render_webpdf_html(notebook, include_inputs, filename)
    # Playwright runs its own event loop, which cannot share a thread with the
    # caller's running loop.
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_print_webpdf, html).result()
