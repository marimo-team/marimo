# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
import json
from copy import deepcopy
from dataclasses import dataclass
from html import unescape
from typing import TYPE_CHECKING, Any, Literal, cast

from marimo import _loggers
from marimo._config.config import DisplayConfig
from marimo._config.manager import get_default_config_manager
from marimo._server.export._html_asset_server import HtmlAssetServer
from marimo._server.export._live_notebook_server import LiveNotebookServer
from marimo._server.export._raster_mime import (
    TEXT_HTML,
    TEXT_MARKDOWN,
    TEXT_PLAIN,
    VEGA_MIME_TYPES,
)
from marimo._server.models.export import ExportAsHTMLRequest
from marimo._types.ids import CellId_t
from marimo._utils.paths import marimo_package_path

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._ast.app import InternalApp
    from marimo._session.state.session_view import SessionView

LOGGER = _loggers.marimo_logger()

MIMEBUNDLE_TYPE = "application/vnd.marimo+mimebundle"
MARIMO_COMPONENT_MARKERS: tuple[str, ...] = (
    "<marimo-",
    "&lt;marimo-",
)
ANYWIDGET_COMPONENT_MARKERS: tuple[str, ...] = (
    "<marimo-anywidget",
    "&lt;marimo-anywidget",
)
EMBEDDED_VEGA_MARKERS: tuple[str, ...] = tuple(VEGA_MIME_TYPES)

_READINESS_TIMEOUT_MS = 90_000
_NETWORK_IDLE_TIMEOUT_MS = 10_000
_NAVIGATION_SETTLE_TIMEOUT_MS = 30_000
_DYNAMIC_OUTPUT_EXTRA_WAIT_MS = 10_000
_VIEWPORT_WIDTH = 1440
_VIEWPORT_HEIGHT = 1000

WAIT_FOR_PAGE_READY = r"""
() => {
  const root = document.getElementById("root");
  if (!root) return false;

  return root.childElementCount > 0;
}
"""

GO_TO_NEXT_SLIDE = r"""
() => {
  const swiper = document.querySelector('.swiper')?.swiper;
  if (swiper) {
    swiper.slideNext();
  }
}
"""

WAIT_FOR_NEXT_PAINT = r"""
() => new Promise((resolve) => {
  requestAnimationFrame(() => requestAnimationFrame(resolve));
})
"""


@dataclass(frozen=True)
class PDFRasterizationOptions:
    enabled: bool = True
    scale: float = 4.0
    server_mode: str = "static"


CaptureExpectation = Literal["anywidget", "vega"]


@dataclass(frozen=True)
class _RasterTarget:
    cell_id: CellId_t
    expects: tuple[CaptureExpectation, ...]


def _format_target_expects(expects: tuple[CaptureExpectation, ...]) -> str:
    if not expects:
        return "generic"
    return ",".join(expects)


def _contains_marker(content: Any, markers: tuple[str, ...]) -> bool:
    """Return whether any string payload contains one of the markers."""

    def _contains(value: str) -> bool:
        return any(marker in value for marker in markers)

    if isinstance(content, list):
        return any(
            isinstance(item, str) and _contains(item) for item in content
        )
    return isinstance(content, str) and _contains(content)


def _dedupe_strings(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _load_mimebundle(data: Any) -> dict[str, Any] | None:
    if isinstance(data, dict):
        return data

    if isinstance(data, str):
        try:
            loaded = json.loads(data)
        except json.JSONDecodeError:
            return None
        if isinstance(loaded, dict):
            return loaded

    return None


def _should_rasterize_output(mimetype: str, data: Any) -> bool:
    """Return whether this output is eligible for PNG fallback capture."""

    if mimetype in VEGA_MIME_TYPES:
        return True

    if mimetype in {TEXT_HTML, TEXT_PLAIN, TEXT_MARKDOWN}:
        return _contains_marker(data, MARIMO_COMPONENT_MARKERS)

    return False


def _build_target_from_mimebundle(
    cell_id: CellId_t,
    mimebundle: dict[str, Any],
) -> _RasterTarget | None:
    """Build capture metadata for a cell emitting a MIME bundle output."""

    should_capture = False
    expects: list[CaptureExpectation] = []

    for mimetype, content in mimebundle.items():
        if _should_rasterize_output(mimetype, content):
            should_capture = True
        if _contains_marker(content, ANYWIDGET_COMPONENT_MARKERS):
            expects.append("anywidget")
        if mimetype in VEGA_MIME_TYPES or _contains_marker(
            content, EMBEDDED_VEGA_MARKERS
        ):
            expects.append("vega")

    if not should_capture:
        return None

    return _RasterTarget(
        cell_id=cell_id,
        expects=cast(tuple[CaptureExpectation, ...], _dedupe_strings(expects)),
    )


def _build_target_from_output(
    cell_id: CellId_t,
    *,
    mimetype: str,
    data: Any,
) -> _RasterTarget | None:
    """Build capture metadata for a non-mimebundle output."""

    if not _should_rasterize_output(mimetype, data):
        return None

    expects: list[CaptureExpectation] = []
    if _contains_marker(data, ANYWIDGET_COMPONENT_MARKERS):
        expects.append("anywidget")
    if mimetype in VEGA_MIME_TYPES or _contains_marker(
        data, EMBEDDED_VEGA_MARKERS
    ):
        expects.append("vega")

    return _RasterTarget(
        cell_id=cell_id,
        expects=cast(tuple[CaptureExpectation, ...], _dedupe_strings(expects)),
    )


def _collect_raster_targets(session_view: SessionView) -> list[_RasterTarget]:
    """Collect capture targets from the current executed session outputs."""

    targets: list[_RasterTarget] = []

    for cell_id, cell_notification in session_view.cell_notifications.items():
        output = cell_notification.output
        if output is None or output.data is None:
            continue

        if output.mimetype == MIMEBUNDLE_TYPE:
            mimebundle = _load_mimebundle(output.data)
            if mimebundle is None:
                continue
            target = _build_target_from_mimebundle(cell_id, mimebundle)
            if target is not None:
                targets.append(target)
            continue

        target = _build_target_from_output(
            cell_id,
            mimetype=output.mimetype,
            data=output.data,
        )
        if target is not None:
            targets.append(target)

    return targets


def _sort_targets_by_notebook_order(
    session_view: SessionView,
    targets: list[_RasterTarget],
) -> list[_RasterTarget]:
    """Sort targets in notebook order so capture sequencing is deterministic."""

    if session_view.cell_ids is None:
        return targets

    order = {
        cell_id: index
        for index, cell_id in enumerate(session_view.cell_ids.cell_ids)
    }
    fallback_index = len(order)
    return sorted(
        targets,
        key=lambda target: order.get(target.cell_id, fallback_index),
    )


def _promote_text_output_for_capture(output: Any) -> None:
    if not _contains_marker(output.data, MARIMO_COMPONENT_MARKERS):
        return
    output.mimetype = TEXT_HTML
    output.data = _unescape_component_markup(output.data)


def _promote_mimebundle_output_for_capture(output: Any) -> None:
    """Ensure mimebundle component markup is available as unescaped text/html."""

    mimebundle = _load_mimebundle(output.data)
    if mimebundle is None:
        return

    html_data = mimebundle.get(TEXT_HTML)
    if html_data is not None and _contains_marker(
        html_data, MARIMO_COMPONENT_MARKERS
    ):
        mimebundle[TEXT_HTML] = _unescape_component_markup(html_data)
        output.data = mimebundle
        return

    plain_data = mimebundle.get(TEXT_PLAIN)
    if plain_data is None or not _contains_marker(
        plain_data, MARIMO_COMPONENT_MARKERS
    ):
        markdown_data = mimebundle.get(TEXT_MARKDOWN)
        if markdown_data is None or not _contains_marker(
            markdown_data, MARIMO_COMPONENT_MARKERS
        ):
            return
        mimebundle[TEXT_HTML] = _unescape_component_markup(markdown_data)
        output.data = mimebundle
        return

    mimebundle[TEXT_HTML] = _unescape_component_markup(plain_data)
    output.data = mimebundle


def _promote_component_markup_for_capture(
    session_view: SessionView,
    targets: list[_RasterTarget],
) -> SessionView:
    """Return a copied session view with target component outputs normalized."""

    capture_view = deepcopy(session_view)

    for target in targets:
        cell_notification = capture_view.cell_notifications.get(target.cell_id)
        if cell_notification is None or cell_notification.output is None:
            continue

        output = cell_notification.output
        if output.mimetype in {TEXT_HTML, TEXT_PLAIN, TEXT_MARKDOWN}:
            _promote_text_output_for_capture(output)
            continue

        if output.mimetype != MIMEBUNDLE_TYPE:
            continue

        _promote_mimebundle_output_for_capture(output)

    return capture_view


def _unescape_component_markup(data: Any) -> Any:
    if isinstance(data, str):
        return unescape(data)
    if isinstance(data, list):
        return [
            unescape(item) if isinstance(item, str) else item for item in data
        ]
    return data


def _to_display_config(filepath: str | None) -> DisplayConfig:
    """Resolve display config for exporter rendering settings."""

    config = get_default_config_manager(current_path=filepath).get_config()
    return cast(DisplayConfig, config["display"])


def _to_data_url(image: bytes) -> str:
    encoded = base64.b64encode(image).decode("ascii")
    return f"data:image/png;base64,{encoded}"


async def _collect_static_captures(
    *,
    app: InternalApp,
    session_view: SessionView,
    filename: str | None,
    filepath: str | None,
    options: PDFRasterizationOptions,
    static_targets: list[_RasterTarget],
) -> dict[CellId_t, str]:
    """Capture PNG fallbacks from exported static HTML for non-live targets."""

    from marimo._server.export.exporter import Exporter

    LOGGER.debug(
        "Raster capture static phase: %s target(s), scale=%s",
        len(static_targets),
        options.scale,
    )

    static_dir = marimo_package_path() / "_static"
    with HtmlAssetServer(
        directory=static_dir,
        route="/__marimo_pdf_raster__.html",
    ) as server:
        capture_view = _promote_component_markup_for_capture(
            session_view,
            static_targets,
        )
        html, _download_filename = Exporter().export_as_html(
            filename=filename,
            app=app,
            session_view=capture_view,
            display_config=_to_display_config(filepath),
            request=ExportAsHTMLRequest(
                download=False,
                files=[],
                include_code=True,
                asset_url=server.base_url,
            ),
        )
        server.set_html(html)
        captures = await _capture_pngs_from_page(
            page_url=server.page_url,
            targets=static_targets,
            scale=options.scale,
        )
        LOGGER.debug(
            "Raster capture static phase complete: %s/%s captured",
            len(captures),
            len(static_targets),
        )
        return captures


async def _collect_live_captures(
    *,
    filepath: str | None,
    argv: list[str] | None,
    options: PDFRasterizationOptions,
    live_targets: list[_RasterTarget],
) -> dict[CellId_t, str]:
    """Capture PNG fallbacks from a live notebook runtime when required."""

    if not filepath:
        LOGGER.debug(
            "Raster capture live phase skipped: no filepath provided."
        )
        return {}

    LOGGER.debug(
        "Raster capture live phase: %s target(s), scale=%s",
        len(live_targets),
        options.scale,
    )
    captures = await _capture_pngs_from_live_page(
        filepath=filepath,
        targets=live_targets,
        scale=options.scale,
        argv=argv,
    )
    LOGGER.debug(
        "Raster capture live phase complete: %s/%s captured",
        len(captures),
        len(live_targets),
    )
    return captures


async def collect_pdf_png_fallbacks(
    *,
    app: InternalApp,
    session_view: SessionView,
    filename: str | None,
    filepath: str | None,
    argv: list[str] | None = None,
    options: PDFRasterizationOptions,
) -> dict[CellId_t, str]:
    """Collect per-cell PNG fallbacks to inject before nbconvert PDF export."""

    if not options.enabled:
        LOGGER.debug("Raster capture disabled by options.")
        return {}

    targets = _collect_raster_targets(session_view)
    if not targets:
        LOGGER.debug("Raster capture skipped: no eligible outputs found.")
        return {}

    targets = _sort_targets_by_notebook_order(session_view, targets)
    server_mode = options.server_mode.lower()
    if server_mode not in {"static", "live"}:
        LOGGER.warning(
            "Unknown raster server mode '%s'; defaulting to static.",
            options.server_mode,
        )
        server_mode = "static"

    LOGGER.debug(
        "Raster capture planning: total=%s server_mode=%s",
        len(targets),
        server_mode,
    )
    LOGGER.info(
        "Rasterizing %s component(s) for PDF [mode=%s, scale=%s].",
        len(targets),
        server_mode,
        options.scale,
    )

    if server_mode == "live":
        LOGGER.debug("Raster capture strategy: live-only.")
        captures = await _collect_live_captures(
            filepath=filepath,
            argv=argv,
            options=options,
            live_targets=targets,
        )
    else:
        LOGGER.debug("Raster capture strategy: static-only.")
        captures = await _collect_static_captures(
            app=app,
            session_view=session_view,
            filename=filename,
            filepath=filepath,
            options=options,
            static_targets=targets,
        )

    LOGGER.debug(
        "Raster capture complete: %s/%s outputs captured.",
        len(captures),
        len(targets),
    )
    return captures


async def _wait_for_network_idle(
    page: Any,
    *,
    timeout_ms: int,
    timeout_error: type[Exception],
) -> None:
    """Best-effort network-idle wait that never fails capture flow."""

    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except timeout_error:
        return


async def _wait_for_navigation_settled(
    *,
    page: Any,
    timeout_error: type[Exception],
) -> None:
    """Settle the page by waiting for load states and a fixed quiet period."""

    for state in ("domcontentloaded", "load", "networkidle"):
        try:
            await page.wait_for_load_state(
                state,
                timeout=_NAVIGATION_SETTLE_TIMEOUT_MS,
            )
        except timeout_error:
            continue
    await page.wait_for_timeout(_DYNAMIC_OUTPUT_EXTRA_WAIT_MS)


async def _wait_for_target_ready(
    *,
    page: Any,
    target: _RasterTarget,
    locator: Any,
    timeout_error: type[Exception],
) -> bool:
    """Wait for a target output to become visible and then stabilize."""

    try:
        await locator.wait_for(
            state="visible",
            timeout=_READINESS_TIMEOUT_MS,
        )
        await locator.scroll_into_view_if_needed(
            timeout=_READINESS_TIMEOUT_MS,
        )
        await page.evaluate(WAIT_FOR_NEXT_PAINT)
        await _wait_for_network_idle(
            page,
            timeout_ms=_NETWORK_IDLE_TIMEOUT_MS,
            timeout_error=timeout_error,
        )
        if target.expects:
            await _wait_for_navigation_settled(
                page=page,
                timeout_error=timeout_error,
            )

        await _wait_for_network_idle(
            page,
            timeout_ms=_NETWORK_IDLE_TIMEOUT_MS,
            timeout_error=timeout_error,
        )
        await page.evaluate(WAIT_FOR_NEXT_PAINT)
    except timeout_error:
        LOGGER.debug(
            "Raster target %s timed out while waiting for visibility/readiness.",
            target.cell_id,
        )
        return False
    else:
        return True


async def _capture_pngs_from_page(
    *,
    page_url: str,
    targets: list[_RasterTarget],
    scale: float,
) -> dict[CellId_t, str]:
    """Capture PNG screenshots for target outputs from a single page URL."""

    from playwright.async_api import (  # type: ignore[import-not-found]
        TimeoutError as PlaywrightTimeoutError,
        async_playwright,
    )

    captures: dict[CellId_t, str] = {}
    device_scale_factor = max(1.0, scale)

    LOGGER.debug(
        "Raster page capture start: url=%s targets=%s scale=%s",
        page_url,
        len(targets),
        scale,
    )

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        context = await browser.new_context(
            viewport={
                "width": _VIEWPORT_WIDTH,
                "height": _VIEWPORT_HEIGHT,
            },
            device_scale_factor=device_scale_factor,
        )
        page = await context.new_page()
        await page.goto(
            page_url,
            wait_until="domcontentloaded",
            timeout=_READINESS_TIMEOUT_MS,
        )
        LOGGER.debug("Page loaded, waiting for readiness...")

        await _wait_for_network_idle(
            page,
            timeout_ms=_NETWORK_IDLE_TIMEOUT_MS,
            timeout_error=PlaywrightTimeoutError,
        )
        LOGGER.debug(
            "Initial network idle achieved, waiting for page ready..."
        )

        await page.wait_for_function(
            WAIT_FOR_PAGE_READY,
            timeout=_READINESS_TIMEOUT_MS,
        )
        LOGGER.debug("Page ready, waiting for final network idle...")

        await _wait_for_network_idle(
            page,
            timeout_ms=_NETWORK_IDLE_TIMEOUT_MS,
            timeout_error=PlaywrightTimeoutError,
        )
        LOGGER.debug("Page network idle, starting target captures...")

        for index, target in enumerate(targets, start=1):
            LOGGER.info(
                "Rasterizing [%s/%s] cell=%s (%s)",
                index,
                len(targets),
                target.cell_id,
                _format_target_expects(target.expects),
            )
            LOGGER.debug(
                "Processing raster target: cell_id=%s expects=%s",
                target.cell_id,
                target.expects,
            )

            # In live notebook mode, output wrappers often use `display: contents`,
            # which cannot be directly screenshotted, so we target a concrete child node.
            locator = page.locator(f"#output-{target.cell_id} > .output").first
            if not await _wait_for_target_ready(
                page=page,
                target=target,
                locator=locator,
                timeout_error=PlaywrightTimeoutError,
            ):
                LOGGER.debug(
                    "Raster target skipped: cell_id=%s",
                    target.cell_id,
                )
                continue

            try:
                await page.evaluate(GO_TO_NEXT_SLIDE)
                await page.evaluate(WAIT_FOR_NEXT_PAINT)
                image = await locator.screenshot(
                    type="png",
                    animations="disabled",
                    timeout=_READINESS_TIMEOUT_MS,
                )
            except PlaywrightTimeoutError:
                LOGGER.debug(
                    "Raster screenshot timed out: cell_id=%s",
                    target.cell_id,
                )
                continue

            captures[target.cell_id] = _to_data_url(image)
            LOGGER.debug(
                "Raster target captured: cell_id=%s",
                target.cell_id,
            )

        await context.close()
        await browser.close()

    LOGGER.debug(
        "Raster page capture complete: %s/%s captured",
        len(captures),
        len(targets),
    )
    LOGGER.info(
        "Rasterization complete: captured %s/%s component(s).",
        len(captures),
        len(targets),
    )
    return captures


async def _capture_pngs_from_live_page(
    *,
    filepath: str,
    targets: list[_RasterTarget],
    scale: float,
    argv: list[str] | None,
) -> dict[CellId_t, str]:
    """Capture outputs by running notebook in a live marimo server process."""

    with LiveNotebookServer(filepath=filepath, argv=argv) as server:
        return await _capture_pngs_from_page(
            page_url=server.page_url,
            targets=targets,
            scale=scale,
        )
