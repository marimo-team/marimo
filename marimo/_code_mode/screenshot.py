# Copyright 2026 Marimo. All rights reserved.
"""Headless Chromium screenshot session for cell outputs.

Lazily launches a browser connected to the running notebook server
in kiosk mode and reuses it across captures.
"""

from __future__ import annotations

import base64
from typing import TYPE_CHECKING, Any

from marimo import _loggers
from marimo._server.export._pdf_raster import (
    WAIT_FOR_NEXT_PAINT,
    WAIT_FOR_PAGE_READY,
)

if TYPE_CHECKING:
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()

_READINESS_TIMEOUT_MS = 90_000
_NETWORK_IDLE_TIMEOUT_MS = 10_000
_VIEWPORT_WIDTH = 1440
_VIEWPORT_HEIGHT = 1000
_DEVICE_SCALE_FACTOR = 2.0

# Minimum slice of `timeout_ms` budget to spend looking for the cell
# container in the DOM.  If the container never attaches, we fail fast
# with a clear error (rather than letting the locator consume the full
# user-provided timeout on a branch that will never succeed).
_ATTACH_TIMEOUT_MS = 5_000

# When the container exists but we're probing selector variants for the
# output element, each candidate selector gets a short wait before we
# move on to the next one.
_SELECTOR_PROBE_TIMEOUT_MS = 1_000


class ScreenshotError(RuntimeError):
    """A cell screenshot could not be captured.

    Messages include actionable hints (available cell IDs,
    install commands, likely misconfigurations).
    """


def _to_data_url(image: bytes) -> str:
    """Convert raw PNG bytes to a ``data:image/png;base64,...`` string."""
    encoded = base64.b64encode(image).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _require_playwright() -> Any:
    """Import ``async_playwright``, raising :class:`ScreenshotError` if missing."""
    from marimo._dependencies.dependencies import DependencyManager

    if not DependencyManager.playwright.has():
        raise ScreenshotError(
            "Playwright is not installed.\n"
            "Fix:\n"
            '  1. ctx.install_packages("playwright")  '
            "# or: pip install playwright\n"
            "  2. python -m playwright install chromium  "
            "# download browser binary"
        )

    from playwright.async_api import (  # type: ignore[import-not-found]
        async_playwright,
    )

    return async_playwright


def _raise_browser_missing(err: Exception) -> None:
    """Raise :class:`ScreenshotError` for a missing Chromium binary."""
    raise ScreenshotError(
        "Chromium browser binary is not installed.\n"
        "Fix: python -m playwright install chromium\n"
        f"Underlying error: {err}"
    ) from err


class _ScreenshotSession:
    """Reusable Playwright browser session for cell screenshots.

    Lazily launches on first :meth:`capture`, reuses across calls.
    Call :meth:`close` to release resources.
    """

    def __init__(
        self, server_url: str, screenshot_auth_token: str | None = None
    ) -> None:
        self._server_url = server_url
        self._screenshot_auth_token = screenshot_auth_token
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None

    async def _ensure_ready(self) -> None:
        """Launch browser and navigate to the notebook if not already done."""
        if self._page is not None:
            return

        async_playwright = _require_playwright()

        LOGGER.debug("Screenshot session: launching browser")
        self._playwright = await async_playwright().start()
        try:
            self._browser = await self._playwright.chromium.launch()
        except Exception as err:
            # Most likely the browser binary was never downloaded.
            # Playwright raises plain `Error` here, so match on the
            # message rather than the class.
            msg = str(err).lower()
            if (
                "executable doesn't exist" in msg
                or "looks like playwright" in msg
            ):
                _raise_browser_missing(err)
            raise

        context = await self._browser.new_context(
            viewport={"width": _VIEWPORT_WIDTH, "height": _VIEWPORT_HEIGHT},
            device_scale_factor=_DEVICE_SCALE_FACTOR,
        )
        page = await context.new_page()
        await page.emulate_media(reduced_motion="reduce")

        self._page = page
        await self._navigate(initial=True)
        LOGGER.debug("Screenshot session: ready")

    async def _navigate(self, *, initial: bool) -> None:
        """Navigate (initial=True) or reload (initial=False) the kiosk page."""
        assert self._page is not None

        params = "kiosk=true"
        if self._screenshot_auth_token:
            params += f"&access_token={self._screenshot_auth_token}"
        page_url = f"{self._server_url}?{params}"
        if initial:
            LOGGER.debug(
                "Screenshot session: navigating to %s", self._server_url
            )
            await self._page.goto(page_url, wait_until="domcontentloaded")
        else:
            LOGGER.debug("Screenshot session: reloading page")
            await self._page.reload(wait_until="domcontentloaded")

        try:
            await self._page.wait_for_function(
                WAIT_FOR_PAGE_READY, timeout=_READINESS_TIMEOUT_MS
            )
        except Exception:
            LOGGER.warning(
                "Screenshot session: page readiness check timed out"
            )

        try:
            await self._page.wait_for_load_state(
                "networkidle", timeout=_NETWORK_IDLE_TIMEOUT_MS
            )
        except Exception:
            pass

    async def capture(
        self,
        cell_id: CellId_t,
        *,
        timeout_ms: int = 30_000,
    ) -> bytes:
        """Screenshot a cell's output and return PNG bytes.

        Raises :class:`ScreenshotError` if the cell container is
        missing, has no content, or no output element becomes visible.
        """
        await self._ensure_ready()
        assert self._page is not None

        LOGGER.debug("Screenshot: capturing cell %s", cell_id)

        # Step 1: find the cell container in the DOM.  The page is
        # cached, so if a cell was added after launch we reload once.
        container_selector = f"#output-{cell_id}"
        attach_timeout = min(_ATTACH_TIMEOUT_MS, timeout_ms)
        try:
            await self._wait_for_container(
                container_selector, timeout=attach_timeout
            )
        except Exception:
            LOGGER.debug(
                "Screenshot: container %s missing, reloading page once",
                container_selector,
            )
            try:
                await self._navigate(initial=False)
            except Exception:
                # If reload itself blows up, fall through to the
                # original error path — we still want to surface the
                # missing-container hints to the caller.
                LOGGER.warning("Screenshot: page reload failed")
            try:
                await self._wait_for_container(
                    container_selector, timeout=attach_timeout
                )
            except Exception as err:
                available = await self._list_cell_ids()
                raise ScreenshotError(
                    self._format_missing_container_error(cell_id, available)
                ) from err

        # Step 2: container exists but may be empty (cell not run, or
        # returned None).
        if not await self._container_has_content(container_selector):
            raise ScreenshotError(
                f"Cell {cell_id!r} has no rendered content.\n"
                "Fix: run the cell first (`ctx.run_cell(...)`) and "
                "ensure its last expression is not None."
            )

        # Step 3: resolve the screenshottable element via prioritised
        # selector list (.output, .vega-embed, .plotly, etc.).
        target = await self._resolve_output_locator(
            container_selector, timeout_ms=timeout_ms
        )

        await target.scroll_into_view_if_needed(timeout=timeout_ms)
        await self._page.evaluate(WAIT_FOR_NEXT_PAINT)
        image: bytes = await target.screenshot(
            type="png",
            animations="disabled",
            timeout=timeout_ms,
        )
        LOGGER.debug(
            "Screenshot: captured cell %s (%d bytes)", cell_id, len(image)
        )
        return image

    async def _resolve_output_locator(
        self,
        container_selector: str,
        *,
        timeout_ms: int,
    ) -> Any:
        """Return the first visible locator from a prioritised selector list."""
        assert self._page is not None

        # Most-specific → most-general, then the container itself.
        candidates: list[str] = [
            f"{container_selector} > .output",
            f"{container_selector} > .vega-embed",
            f"{container_selector} > .plotly",
            f"{container_selector} > .anywidget",
            f"{container_selector} > div",
            container_selector,
        ]

        # Each probe gets a short wait; the container fallback is
        # guaranteed to exist (step 1) so it resolves immediately.
        probe_budget = min(_SELECTOR_PROBE_TIMEOUT_MS, timeout_ms)

        last_error: Exception | None = None
        for selector in candidates:
            locator = self._page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=probe_budget)
                LOGGER.debug(
                    "Screenshot: resolved output via selector %s", selector
                )
                return locator
            except Exception as err:
                last_error = err
                continue

        # Every candidate failed.
        dom_snapshot = await self._describe_container(container_selector)
        raise ScreenshotError(
            f"No visible output element under {container_selector!r}.\n"
            f"Tried: {candidates}\n"
            f"Container: {dom_snapshot}\n"
            "Fix: increase `timeout_ms`, or ensure the output is "
            "not hidden (display:none)."
        ) from last_error

    async def _wait_for_container(
        self, container_selector: str, *, timeout: int
    ) -> None:
        """Wait for a cell output container to attach to the DOM."""
        assert self._page is not None
        await self._page.locator(container_selector).first.wait_for(
            state="attached", timeout=timeout
        )

    async def _list_cell_ids(self) -> list[str]:
        """Return the cell IDs currently rendered on the page."""
        assert self._page is not None
        try:
            ids: list[str] = await self._page.eval_on_selector_all(
                "[id^='output-']",
                "els => els.map(e => e.id.replace(/^output-/, ''))",
            )
            return ids
        except Exception:
            return []

    async def _container_has_content(self, container_selector: str) -> bool:
        """Whether the cell container has any rendered children."""
        assert self._page is not None
        try:
            return bool(
                await self._page.eval_on_selector(
                    container_selector,
                    "el => el.children.length > 0 "
                    "|| el.textContent.trim().length > 0",
                )
            )
        except Exception:
            return False

    async def _describe_container(self, container_selector: str) -> str:
        """Human-readable snapshot of the container for error messages."""
        assert self._page is not None
        try:
            info = await self._page.eval_on_selector(
                container_selector,
                """el => ({
                    childCount: el.children.length,
                    firstChildTag: el.children[0]?.tagName ?? null,
                    firstChildClass: el.children[0]?.className ?? null,
                    innerLen: el.innerHTML.length,
                    visible: el.offsetParent !== null,
                })""",
            )
            return str(info)
        except Exception as err:
            return f"<failed to inspect container: {err}>"

    @staticmethod
    def _format_missing_container_error(
        cell_id: CellId_t, available: list[str]
    ) -> str:
        """Compose the error raised when the cell container is absent."""
        if available:
            # Keep the list digestible when there are many cells.
            shown = available[:20]
            truncated = (
                f" (+{len(available) - len(shown)} more)"
                if len(available) > len(shown)
                else ""
            )
            available_line = f"Cells currently on the page: {shown}{truncated}"
        else:
            available_line = (
                "No cell output containers are on the page at all."
            )
        return (
            f"Cell {cell_id!r} not found on the page.\n"
            f"{available_line}\n"
            "Fix: verify the cell ID/name/index, and ensure the "
            "context manager has exited (which flushes new cells "
            "to the frontend)."
        )

    async def close(self) -> None:
        """Release browser resources."""
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
        self._page = None
        LOGGER.debug("Screenshot session: closed")
