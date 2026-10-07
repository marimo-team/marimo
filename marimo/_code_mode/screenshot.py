# Copyright 2026 Marimo. All rights reserved.
"""Headless Chromium screenshot session for cell outputs.

Lazily launches a browser connected to the running notebook server
in kiosk mode and reuses it across captures.
"""

from __future__ import annotations

import asyncio
import base64
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal, TypeAlias
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from marimo import _loggers
from marimo._export._pdf_raster import (
    WAIT_FOR_NEXT_PAINT,
    WAIT_FOR_PAGE_READY,
)

if TYPE_CHECKING:
    from marimo._messaging.mimetypes import KnownMimeType
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()

_OutputState: TypeAlias = Literal["empty", "ready", "pending"]

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


def _suppress() -> Any:
    """contextlib.suppress(Exception) without the import."""
    import contextlib

    return contextlib.suppress(Exception)


class ScreenshotError(RuntimeError):
    """A cell screenshot could not be captured.

    Messages include actionable hints (available cell IDs,
    install commands, likely misconfigurations).
    """


def _to_data_url(image: bytes) -> str:
    """Convert raw PNG bytes to a `data:image/png;base64,...` string."""
    encoded = base64.b64encode(image).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@dataclass(frozen=True)
class _ScreenshotOutput:
    """Preserve PNG MIME information when formatting screenshot values."""

    data_url: str

    def _mime_(self) -> tuple[KnownMimeType, str]:
        return ("image/png", self.data_url)


# The display protocol takes precedence over registered bytes/str formatters.
class _ScreenshotBytes(bytes):
    def _display_(self) -> _ScreenshotOutput:
        return _ScreenshotOutput(_to_data_url(self))


class _ScreenshotDataUrl(str):
    def _display_(self) -> _ScreenshotOutput:
        return _ScreenshotOutput(self)


def _require_playwright() -> Any:
    """Import `async_playwright`, raising :class:`ScreenshotError` if missing."""
    from marimo._dependencies.dependencies import DependencyManager

    if not DependencyManager.playwright.has():
        raise ScreenshotError(
            "Playwright is not installed.\n"
            "Fix:\n"
            "  1. pip install playwright\n"
            "  2. python -m playwright install chromium"
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
        self,
        server_url: str,
        screenshot_auth_token: str | None = None,
        *,
        file_key: str | None = None,
    ) -> None:
        self._server_url = server_url
        self._screenshot_auth_token = screenshot_auth_token
        self._file_key = file_key
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._init_lock = asyncio.Lock()

    async def _ensure_ready(self) -> None:
        """Launch browser and navigate to the notebook if not already done."""
        async with self._init_lock:
            if self._page is not None:
                return
            await self._init_browser()

    async def _init_browser(self) -> None:
        """Start Playwright + Chromium and navigate to the kiosk page.

        On failure, any partially-created resources are cleaned up
        before re-raising.
        """
        async_playwright = _require_playwright()

        LOGGER.debug("Screenshot session: launching browser")
        pw = await async_playwright().start()
        browser: Any = None
        page: Any = None
        try:
            try:
                browser = await pw.chromium.launch()
            except Exception as err:
                msg = str(err).lower()
                if (
                    "executable doesn't exist" in msg
                    or "looks like playwright" in msg
                ):
                    _raise_browser_missing(err)
                raise

            context = await browser.new_context(
                viewport={
                    "width": _VIEWPORT_WIDTH,
                    "height": _VIEWPORT_HEIGHT,
                },
                device_scale_factor=_DEVICE_SCALE_FACTOR,
            )
            page = await context.new_page()
            await page.emulate_media(reduced_motion="reduce")

            self._page = page
            await self._navigate(initial=True)
            self._playwright = pw
            self._browser = browser
            LOGGER.debug("Screenshot session: ready")
        except BaseException:
            self._page = None
            # Clean up partially-created resources.
            if browser is not None:
                with _suppress():
                    await browser.close()
            with _suppress():
                await pw.stop()
            raise

    async def _navigate(self, *, initial: bool) -> None:
        """Navigate (initial=True) or reload (initial=False) the kiosk page."""
        assert self._page is not None

        if initial:
            LOGGER.debug(
                "Screenshot session: navigating to %s", self._server_url
            )
            await self._page.goto(
                self._page_url(), wait_until="domcontentloaded"
            )
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

    def _page_url(self) -> str:
        """Build an authenticated kiosk URL for the active notebook."""
        url = urlsplit(self._server_url)
        params = {"kiosk": "true"}
        # Session IDs also identify consumers. The kiosk must create its
        # own consumer and join the live session by file key.
        if self._file_key is not None:
            params["file"] = self._file_key
        if self._screenshot_auth_token:
            params["access_token"] = self._screenshot_auth_token
        query = [
            (key, value)
            for key, value in parse_qsl(url.query, keep_blank_values=True)
            if key not in params and key != "session_id"
        ]
        query.extend(params.items())
        return urlunsplit(url._replace(query=urlencode(query)))

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
        reused_page = self._page is not None
        await self._ensure_ready()
        assert self._page is not None
        deadline = time.monotonic() + timeout_ms / 1000.0
        refreshed = False
        container_selector = f"#output-{cell_id}"

        while True:
            remaining = self._remaining_ms(deadline)
            wait_timeout = (
                remaining if refreshed else min(_ATTACH_TIMEOUT_MS, remaining)
            )
            try:
                state = await self._wait_for_output(
                    cell_id,
                    timeout=wait_timeout,
                    probe=True,
                )
                if state == "pending":
                    remaining = self._remaining_ms(deadline)
                    try:
                        state = await self._wait_for_output(
                            cell_id, timeout=remaining
                        )
                    except Exception as err:
                        raise ScreenshotError(
                            f"Cell {cell_id!r} has no visible rendered output after waiting.\n"
                            "Fix: inspect the cell's code and errors, run it if needed, "
                            "or increase `timeout_ms` if rendering is slow."
                        ) from err
            except ScreenshotError:
                raise
            except Exception as err:
                if refreshed:
                    available = await self._list_cell_ids()
                    raise ScreenshotError(
                        self._format_missing_container_error(
                            cell_id, available
                        )
                    ) from err
            else:
                if state == "ready" and (not reused_page or refreshed):
                    break
                if state == "empty" and (not reused_page or refreshed):
                    raise ScreenshotError(
                        f"Cell {cell_id!r} has no rendered output.\n"
                        "Fix: inspect `ctx.cells[cell_id].code` and `.errors`, "
                        "then run the cell (`ctx.run_cell(...)`) with a "
                        "displayable last expression or `mo.output.append(...)`. "
                        "Printed text is console output and cannot be captured here."
                    )

            # A reused kiosk may lag execution in the current invocation.
            # Refresh even ready output: its marker and DOM may both be stale.
            refreshed = True
            remaining = self._remaining_ms(deadline)
            try:
                await asyncio.wait_for(
                    self._navigate(initial=False), remaining / 1000.0
                )
            except TimeoutError as err:
                raise ScreenshotError(
                    "Screenshot timed out while refreshing. Fix: increase `timeout_ms`."
                ) from err
            except Exception as err:
                raise ScreenshotError(
                    "Screenshot failed while refreshing the notebook. "
                    "Fix: check the notebook connection and retry; "
                    "increase `timeout_ms` if navigation is slow."
                ) from err

        target = await self._resolve_output_locator(
            container_selector, timeout_ms=self._remaining_ms(deadline)
        )
        await target.scroll_into_view_if_needed(
            timeout=self._remaining_ms(deadline)
        )
        await self._page.evaluate(WAIT_FOR_NEXT_PAINT)
        image: bytes = await target.screenshot(
            type="png",
            animations="disabled",
            timeout=self._remaining_ms(deadline),
        )
        return image

    @staticmethod
    def _remaining_ms(deadline: float) -> int:
        remaining = int((deadline - time.monotonic()) * 1000)
        if remaining <= 0:
            raise ScreenshotError(
                "Screenshot timed out. Fix: increase `timeout_ms` if rendering is slow."
            )
        return remaining

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

        # Track a hard deadline so total probing never exceeds timeout_ms.
        deadline = time.monotonic() + timeout_ms / 1000.0

        last_error: Exception | None = None
        for selector in candidates:
            remaining_ms = max(0, int((deadline - time.monotonic()) * 1000))
            if remaining_ms == 0:
                break
            probe = min(_SELECTOR_PROBE_TIMEOUT_MS, remaining_ms)
            locator = self._page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=probe)
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

    async def _wait_for_output(
        self, cell_id: CellId_t, *, timeout: int, probe: bool = False
    ) -> _OutputState:
        assert self._page is not None
        handle = await self._page.wait_for_function(
            """({cellId, probe}) => {
                const capture = window.__marimoCapture;
                if (capture) {
                    const state = capture.getCellState(cellId);
                    if (state === "empty") return "empty";
                    if (state === "missing") return false;
                    if (state !== "available") return probe ? "pending" : false;
                }
                // Rendering readiness remains a DOM check, independent of availability.
                const el = document.getElementById(`output-${cellId}`);
                if (el && el.getClientRects().length > 0 &&
                    (el.children.length > 0 || el.textContent.trim().length > 0)) {
                    return "ready";
                }
                if (probe && (capture || el)) return "pending";
                return false;
            }""",
            arg={"cellId": cell_id, "probe": probe},
            timeout=timeout,
        )
        try:
            state = await handle.json_value()
        finally:
            await handle.dispose()
        if state == "empty":
            return "empty"
        if state == "ready":
            return "ready"
        if state == "pending":
            return "pending"
        raise ScreenshotError(f"Unexpected browser output state: {state!r}")

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
            "to the frontend). Inspect the cell's code and errors: "
            "a cell that has not run or produces no display output "
            "has no output container. Printed text is console output."
        )

    async def close(self) -> None:
        """Release browser resources."""
        async with self._init_lock:
            browser = self._browser
            playwright = self._playwright
            self._browser = None
            self._playwright = None
            self._page = None
            try:
                if browser is not None:
                    await browser.close()
            finally:
                if playwright is not None:
                    await playwright.stop()
        LOGGER.debug("Screenshot session: closed")
