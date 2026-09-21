# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from marimo._convert.common.dom_traversal import (
    replace_public_files_with_data_uris,
    replace_virtual_files_with_data_uris,
)
from marimo._convert.ipynb.from_ir import NBCONVERT_REMOVE_INPUT_TAG

if TYPE_CHECKING:
    from traitlets.config import Config


def inline_pdf_assets(html: str, filename: str | None) -> str:
    """Resolve notebook assets before Chromium opens HTML in a temp directory."""
    html, _ = replace_virtual_files_with_data_uris(
        html,
        allowed_tags={"img", "audio", "video", "source"},
        allowed_attributes={"src"},
    )
    if filename is not None:
        html, _ = replace_public_files_with_data_uris(
            html, public_dir=Path(filename).resolve().parent / "public"
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


def _print_webpdf(html: str) -> Any:
    if sys.platform == "win32":
        # marimo installs the Selector policy during import. The spawned render
        # process restores Proactor before Playwright creates its subprocess loop.
        asyncio.set_event_loop_policy(None)

    from nbconvert import WebPDFExporter  # type: ignore[import-not-found]

    exporter = WebPDFExporter(allow_chromium_download=True)  # type: ignore[no-untyped-call]
    return exporter.run_playwright(html)  # type: ignore[no-untyped-call]


def _render_webpdf(
    notebook: Any, include_inputs: bool, filename: str | None = None
) -> Any:
    # Resolve process-local virtual files before crossing the spawn boundary.
    html = _render_webpdf_html(notebook, include_inputs, filename)
    if sys.platform != "win32":
        return _print_webpdf(html)

    from concurrent.futures import ProcessPoolExecutor
    from multiprocessing import get_context

    with ProcessPoolExecutor(
        max_workers=1,
        mp_context=get_context("spawn"),
    ) as pool:
        return pool.submit(_print_webpdf, html).result()
