# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import base64
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import pytest

from marimo._ast.cell import CellConfig
from marimo._code_mode._context import (
    AsyncCodeModeContext,
    NotebookCell,
)
from marimo._code_mode.screenshot import (
    ScreenshotError,
    _ScreenshotSession,
    _to_data_url,
)
from marimo._code_mode.screenshot_meta import (
    SCREENSHOT_AUTH_TOKEN_KEY,
    SCREENSHOT_FILE_KEY,
    SCREENSHOT_SERVER_URL_KEY,
)
from marimo._messaging.cell_output import CellChannel, CellOutput
from marimo._messaging.context import http_request_context
from marimo._messaging.notebook.document import (
    NotebookCell as _DocNotebookCell,
    NotebookDocument,
    notebook_document_context,
)
from marimo._messaging.notebook.outputs import (
    CellOutputs,
    notebook_outputs_context,
)
from marimo._output.formatting import try_format
from marimo._runtime.commands import HTTPRequest
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from typing import Any

    from marimo._runtime.runtime import Kernel


class TestToDataUrl:
    def test_round_trip(self) -> None:
        payload = b"\x89PNG\r\n\x1a\n"
        result = _to_data_url(payload)
        assert result.startswith("data:image/png;base64,")
        decoded = base64.b64decode(result.split(",", 1)[1])
        assert decoded == payload

    def test_empty(self) -> None:
        result = _to_data_url(b"")
        assert result == "data:image/png;base64,"


class TestScreenshotSessionAuthUrl:
    def test_url_without_auth(self) -> None:
        session = _ScreenshotSession("http://localhost:1234")
        assert session._server_url == "http://localhost:1234"
        assert session._screenshot_auth_token is None

    def test_url_with_auth(self) -> None:
        session = _ScreenshotSession(
            "http://localhost:1234", screenshot_auth_token="tok123"
        )
        assert session._screenshot_auth_token == "tok123"

    def test_page_url_includes_screenshot_auth_token(self) -> None:
        """The kiosk page URL must include the access_token query param."""
        session = _ScreenshotSession(
            "http://localhost:9999",
            screenshot_auth_token="secret+&=#?",
            file_key="notebooks/my notebook + #1.py",
        )
        assert parse_qs(urlsplit(session._page_url()).query) == {
            "access_token": ["secret+&=#?"],
            "file": ["notebooks/my notebook + #1.py"],
            "kiosk": ["true"],
        }

    def test_page_url_omits_token_when_none(self) -> None:
        session = _ScreenshotSession("http://localhost:9999")
        page_url = session._page_url()

        assert "access_token" not in page_url
        assert page_url == "http://localhost:9999?kiosk=true"

    def test_page_url_preserves_base_path_query_and_fragment(self) -> None:
        session = _ScreenshotSession(
            "http://localhost:9999/base/?theme=dark&theme=light&kiosk=false"
            "&session_id=editor&file=old.py&access_token=old#output",
            screenshot_auth_token="secret",
            file_key="__new__notebook",
        )
        url = urlsplit(session._page_url())
        assert url.path == "/base/"
        assert url.fragment == "output"
        assert parse_qs(url.query) == {
            "theme": ["dark", "light"],
            "kiosk": ["true"],
            "file": ["__new__notebook"],
            "access_token": ["secret"],
        }


class _FakeCells:
    """Minimal stand-in for `_CellsView` used by the resolver tests.

    Supports the operations `_resolve_screenshot_target` actually
    calls — `__len__`, integer indexing, and `_resolve(str)` — so
    the resolver can run without a live kernel/document.
    """

    def __init__(
        self,
        cell_ids: list[str],
        names: dict[str, str] | None = None,
    ) -> None:
        self._ids = [CellId_t(cid) for cid in cell_ids]
        self._names = names or {}

    def __len__(self) -> int:
        return len(self._ids)

    def __getitem__(self, idx: int) -> Any:
        return SimpleNamespace(id=self._ids[idx])

    def _resolve(self, target: str) -> CellId_t:
        if target in self._ids:
            return CellId_t(target)
        for cid, name in self._names.items():
            if name == target:
                return CellId_t(cid)
        raise KeyError(target)


def _fake_ctx(cell_ids: list[str], names: dict[str, str] | None = None) -> Any:
    """Build an object usable as `self` for the resolver method."""
    return SimpleNamespace(cells=_FakeCells(cell_ids, names))


def _resolve(ctx: Any, target: Any) -> CellId_t:
    return AsyncCodeModeContext._resolve_screenshot_target(ctx, target)


class TestResolveScreenshotTarget:
    def test_none_with_empty_notebook_raises(self) -> None:
        with pytest.raises(ScreenshotError, match="no cells"):
            _resolve(_fake_ctx([]), None)

    def test_none_returns_last_cell(self) -> None:
        ctx = _fake_ctx(["cell-a", "cell-b", "cell-c"])
        assert _resolve(ctx, None) == CellId_t("cell-c")

    def test_bool_raises_type_error(self) -> None:
        # ``bool`` is a subclass of ``int``; guard before the int branch
        # so ``ctx.screenshot(True)`` surfaces as a caller mistake.
        ctx = _fake_ctx(["cell-a"])
        with pytest.raises(TypeError, match="bool"):
            _resolve(ctx, True)
        with pytest.raises(TypeError, match="bool"):
            _resolve(ctx, False)

    def test_int_positive_index(self) -> None:
        ctx = _fake_ctx(["cell-a", "cell-b", "cell-c"])
        assert _resolve(ctx, 0) == CellId_t("cell-a")
        assert _resolve(ctx, 1) == CellId_t("cell-b")

    def test_int_negative_index(self) -> None:
        ctx = _fake_ctx(["cell-a", "cell-b", "cell-c"])
        assert _resolve(ctx, -1) == CellId_t("cell-c")
        assert _resolve(ctx, -3) == CellId_t("cell-a")

    def test_int_out_of_range_raises(self) -> None:
        ctx = _fake_ctx(["cell-a"])
        with pytest.raises(ScreenshotError, match="out of range"):
            _resolve(ctx, 5)
        with pytest.raises(ScreenshotError, match="out of range"):
            _resolve(ctx, -2)

    def test_str_resolves_cell_id(self) -> None:
        ctx = _fake_ctx(["cell-a", "cell-b"])
        assert _resolve(ctx, "cell-a") == CellId_t("cell-a")

    def test_str_resolves_cell_name(self) -> None:
        ctx = _fake_ctx(["cell-a", "cell-b"], names={"cell-b": "my_cell"})
        assert _resolve(ctx, "my_cell") == CellId_t("cell-b")

    def test_str_unknown_raises(self) -> None:
        ctx = _fake_ctx(["cell-a"])
        with pytest.raises(ScreenshotError, match="Unknown cell ID or name"):
            _resolve(ctx, "does-not-exist")

    def test_notebook_cell_target(self) -> None:
        doc_cell = _DocNotebookCell(
            id=CellId_t("cell-x"),
            code="x = 1",
            name="",
            config=CellConfig(),
        )
        nb_cell = NotebookCell(doc_cell, cell_impl=None)
        ctx = _fake_ctx(["cell-a"])  # cell-x deliberately not in view
        assert _resolve(ctx, nb_cell) == CellId_t("cell-x")

    def test_unsupported_type_raises(self) -> None:
        ctx = _fake_ctx(["cell-a"])
        with pytest.raises(TypeError, match="Unsupported"):
            _resolve(ctx, 3.14)
        with pytest.raises(TypeError, match="Unsupported"):
            _resolve(ctx, object())


@pytest.fixture
def doc_cell() -> _DocNotebookCell:
    return _DocNotebookCell(
        id=CellId_t("cell-a"),
        code="value = 1",
        name="",
        config=CellConfig(),
    )


@pytest.mark.parametrize("output", [None, CellOutput.empty()])
@pytest.mark.parametrize("new_context", [False, True])
async def test_screenshot_after_run_ignores_stale_empty_snapshot(
    k: Kernel,
    doc_cell: _DocNotebookCell,
    screenshot_request: HTTPRequest,
    output: CellOutput | None,
    new_context: bool,
) -> None:
    doc_cell.code = "value = 42\nvalue"
    outputs = CellOutputs(
        output={} if output is None else {doc_cell.id: output},
        console_outputs={},
    )
    with (
        notebook_document_context(NotebookDocument([doc_cell])),
        notebook_outputs_context(outputs),
        http_request_context(screenshot_request),
        patch(
            "marimo._code_mode.screenshot._ScreenshotSession", autospec=True
        ) as session,
    ):
        session.return_value.capture.return_value = b"png"
        ctx = AsyncCodeModeContext(k, skip_staleness_check=True)
        async with ctx:
            ctx.run_cell(doc_cell.id)
        assert k.globals["value"] == 42
        if new_context:
            ctx = AsyncCodeModeContext(k, skip_staleness_check=True)
        assert ctx.cells[doc_cell.id].output is output
        assert await ctx.screenshot(doc_cell.id) == b"png"
        session.return_value.capture.assert_awaited_once_with(
            doc_cell.id, timeout_ms=30_000
        )
        await ctx.close_screenshot_session()


@pytest.fixture
def screenshot_request() -> HTTPRequest:
    return HTTPRequest(
        url={"path": "/api/kernel/execute"},
        base_url={},
        headers={},
        query_params={},
        path_params={},
        cookies={},
        meta={
            SCREENSHOT_SERVER_URL_KEY: "http://localhost:1234/base",
            SCREENSHOT_AUTH_TOKEN_KEY: "secret",
            SCREENSHOT_FILE_KEY: "notebooks/my notebook.py",
        },
        user={},
    )


@pytest.mark.parametrize("has_snapshot", [True, False])
async def test_screenshot_passes_credentials_and_reuses_browser(
    k: Kernel,
    doc_cell: _DocNotebookCell,
    screenshot_request: HTTPRequest,
    has_snapshot: bool,
) -> None:
    outputs = CellOutputs(
        output={
            doc_cell.id: CellOutput(
                channel=CellChannel.OUTPUT, mimetype="text/plain", data="1"
            )
        },
        console_outputs={},
    )
    with (
        notebook_document_context(NotebookDocument([doc_cell])),
        notebook_outputs_context(outputs if has_snapshot else None),
        http_request_context(screenshot_request),
        patch(
            "marimo._code_mode.screenshot._ScreenshotSession", autospec=True
        ) as session,
    ):
        session.return_value.capture.return_value = b"png"
        ctx = AsyncCodeModeContext(k)
        image = await ctx.screenshot(doc_cell.id)
        data_url = await ctx.screenshot(doc_cell.id, as_data_url=True)
        assert isinstance(image, bytes)
        assert image == b"png"
        assert isinstance(data_url, str)
        assert data_url == _to_data_url(b"png")
        for value in (image, data_url):
            formatted = try_format(value)
            assert (formatted.mimetype, formatted.data) == (
                "image/png",
                _to_data_url(b"png"),
            )
        session.assert_called_once_with(
            "http://localhost:1234/base",
            screenshot_auth_token="secret",
            file_key="notebooks/my notebook.py",
        )
        session.return_value.capture.assert_awaited_with(
            doc_cell.id, timeout_ms=30_000
        )
        await ctx.close_screenshot_session()
        session.return_value.close.assert_awaited_once()


@pytest.mark.parametrize("reused_page", [False, True])
async def test_empty_browser_output_refreshes_only_a_reused_page(
    reused_page: bool,
) -> None:
    session = _ScreenshotSession("http://localhost:1234")
    if reused_page:
        session._page = MagicMock()

    async def ready() -> None:
        session._page = MagicMock()

    with (
        patch.object(session, "_ensure_ready", side_effect=ready),
        patch.object(
            session, "_wait_for_output", return_value="empty"
        ) as wait,
        patch.object(session, "_navigate", new_callable=AsyncMock) as navigate,
        patch.object(
            session, "_resolve_output_locator", new_callable=AsyncMock
        ) as resolve,
    ):
        with pytest.raises(ScreenshotError, match="has no rendered output"):
            await session.capture(CellId_t("cell-a"))
        assert wait.await_count == (2 if reused_page else 1)
        if reused_page:
            navigate.assert_awaited_once_with(initial=False)
        else:
            navigate.assert_not_awaited()
        resolve.assert_not_awaited()


async def test_reused_empty_browser_refreshes_before_rejecting_new_output() -> (
    None
):
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    target = AsyncMock()
    target.screenshot.return_value = b"png"
    with (
        patch.object(session, "_ensure_ready", new_callable=AsyncMock),
        patch.object(session, "_navigate", new_callable=AsyncMock) as navigate,
        patch.object(
            session, "_wait_for_output", side_effect=["empty", "ready"]
        ),
        patch.object(session, "_resolve_output_locator", return_value=target),
    ):
        assert await session.capture(CellId_t("cell-a")) == b"png"
        navigate.assert_awaited_once_with(initial=False)


@pytest.mark.parametrize("refreshed_state", ["ready", "empty"])
async def test_reused_ready_output_is_refreshed_before_capture(
    refreshed_state: str,
) -> None:
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    target = AsyncMock()
    target.screenshot.return_value = b"fresh png"
    with (
        patch.object(session, "_ensure_ready", new_callable=AsyncMock),
        patch.object(session, "_navigate", new_callable=AsyncMock) as navigate,
        patch.object(
            session, "_wait_for_output", side_effect=["ready", refreshed_state]
        ),
        patch.object(session, "_resolve_output_locator", return_value=target),
    ):
        if refreshed_state == "ready":
            assert await session.capture(CellId_t("cell-a")) == b"fresh png"
        else:
            with pytest.raises(
                ScreenshotError, match="has no rendered output"
            ):
                await session.capture(CellId_t("cell-a"))
            target.screenshot.assert_not_awaited()
        navigate.assert_awaited_once_with(initial=False)


async def test_missing_container_and_empty_output_share_one_refresh() -> None:
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    with (
        patch.object(session, "_ensure_ready", new_callable=AsyncMock),
        patch.object(session, "_navigate", new_callable=AsyncMock) as navigate,
        patch.object(
            session, "_wait_for_output", side_effect=[TimeoutError, "empty"]
        ),
    ):
        with pytest.raises(ScreenshotError, match="has no rendered output"):
            await session.capture(CellId_t("cell-a"))
        navigate.assert_awaited_once_with(initial=False)


async def test_rendering_wait_and_screenshot_share_timeout_budget() -> None:
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    with (
        patch.object(session, "_ensure_ready", new_callable=AsyncMock),
        patch.object(session, "_wait_for_output", return_value="ready"),
        patch.object(
            session, "_resolve_output_locator", new_callable=AsyncMock
        ) as resolve,
        patch(
            "marimo._code_mode.screenshot.time.monotonic",
            side_effect=[0, 0.001, 0.050],
        ),
    ):
        with pytest.raises(ScreenshotError, match="Screenshot timed out"):
            await session.capture(CellId_t("cell-a"), timeout_ms=20)
        resolve.assert_not_awaited()


@pytest.mark.parametrize("kind", ["deadline", "playwright", "reload"])
async def test_refresh_failure_is_actionable(kind: str) -> None:
    error: Exception
    if kind == "deadline":
        error = TimeoutError()
    elif kind == "playwright":
        playwright = pytest.importorskip("playwright.async_api")
        error = playwright.TimeoutError("navigation timed out")
    else:
        error = RuntimeError("reload failed")
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    with (
        patch.object(session, "_ensure_ready", new_callable=AsyncMock),
        patch.object(session, "_wait_for_output", return_value="empty"),
        patch.object(session, "_navigate", side_effect=error),
    ):
        with pytest.raises(ScreenshotError, match="refreshing") as raised:
            await session.capture(CellId_t("cell-a"))
        assert "Fix:" in str(raised.value)
        assert raised.value.__cause__ is error


async def test_pending_probe_preserves_exhausted_budget_error() -> None:
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    with (
        patch.object(session, "_ensure_ready", new_callable=AsyncMock),
        patch.object(
            session, "_wait_for_output", return_value="pending"
        ) as wait,
        patch.object(session, "_navigate", new_callable=AsyncMock) as navigate,
        patch(
            "marimo._code_mode.screenshot.time.monotonic",
            side_effect=[0, 0.001, 0.050],
        ),
    ):
        with pytest.raises(ScreenshotError, match="Screenshot timed out"):
            await session.capture(CellId_t("cell-a"), timeout_ms=20)
        assert wait.await_count == 1
        navigate.assert_not_awaited()


async def test_known_cell_gets_full_rendering_wait_without_refresh() -> None:
    session = _ScreenshotSession("http://localhost:1234")

    async def ready() -> None:
        session._page = AsyncMock()

    target = AsyncMock()
    target.screenshot.return_value = b"png"
    with (
        patch.object(session, "_ensure_ready", side_effect=ready),
        patch.object(
            session, "_wait_for_output", side_effect=["pending", "ready"]
        ) as wait,
        patch.object(session, "_navigate", new_callable=AsyncMock) as navigate,
        patch.object(session, "_resolve_output_locator", return_value=target),
    ):
        assert await session.capture(CellId_t("cell-a")) == b"png"
        assert wait.await_args_list[1].kwargs["timeout"] > 5000
        navigate.assert_not_awaited()


async def test_known_cell_render_timeout_is_actionable_without_refresh() -> (
    None
):
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    with (
        patch.object(session, "_ensure_ready", new_callable=AsyncMock),
        patch.object(
            session, "_wait_for_output", side_effect=["pending", TimeoutError]
        ),
        patch.object(session, "_navigate", new_callable=AsyncMock) as navigate,
    ):
        with pytest.raises(
            ScreenshotError, match="no visible rendered output after waiting"
        ):
            await session.capture(CellId_t("cell-a"))
        navigate.assert_not_awaited()


@pytest.mark.parametrize("state", ["empty", "ready", "pending"])
async def test_browser_state_handle_is_disposed(state: str) -> None:
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    handle = session._page.wait_for_function.return_value
    handle.json_value.return_value = state
    assert (
        await session._wait_for_output(CellId_t("cell-a"), timeout=1000)
        == state
    )
    handle.dispose.assert_awaited_once()


async def test_unexpected_browser_state_is_rejected_and_disposed() -> None:
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    handle = session._page.wait_for_function.return_value
    handle.json_value.return_value = "unknown"
    with pytest.raises(
        ScreenshotError, match="Unexpected browser output state"
    ):
        await session._wait_for_output(CellId_t("cell-a"), timeout=1000)
    handle.dispose.assert_awaited_once()


@pytest.fixture
def playwright_mock() -> MagicMock:
    playwright = MagicMock()
    playwright.stop = AsyncMock()
    browser = AsyncMock()
    page = AsyncMock()
    page.on = MagicMock()
    browser.new_context.return_value.new_page.return_value = page
    playwright.chromium.launch = AsyncMock(return_value=browser)
    return playwright


@pytest.mark.parametrize(
    ("stage", "error"),
    [
        ("launch", RuntimeError("launch failed")),
        ("navigation", RuntimeError("navigation failed")),
        ("navigation", asyncio.CancelledError()),
    ],
)
async def test_browser_initialization_failure_releases_resources_and_retries(
    playwright_mock: MagicMock, stage: str, error: BaseException
) -> None:
    browser = playwright_mock.chromium.launch.return_value
    page = browser.new_context.return_value.new_page.return_value
    if stage == "launch":
        playwright_mock.chromium.launch.side_effect = [error, browser]
    else:
        page.goto.side_effect = [error, None]
    manager = MagicMock(start=AsyncMock(return_value=playwright_mock))
    session = _ScreenshotSession("http://localhost:1234", file_key="app.py")
    with patch(
        "marimo._code_mode.screenshot._require_playwright",
        return_value=lambda: manager,
    ):
        with pytest.raises(type(error)):
            await session._ensure_ready()
        assert session._page is None
        assert session._browser is None
        assert session._playwright is None
        if stage == "launch":
            browser.close.assert_not_awaited()
        else:
            browser.close.assert_awaited_once()
        playwright_mock.stop.assert_awaited_once()

        await session._ensure_ready()
        page.goto.assert_awaited_with(
            session._page_url(), wait_until="domcontentloaded"
        )
        assert playwright_mock.chromium.launch.await_count == 2
        await session.close()


async def test_concurrent_initialization_waits_for_navigation(
    playwright_mock: MagicMock,
) -> None:
    browser = playwright_mock.chromium.launch.return_value
    page = browser.new_context.return_value.new_page.return_value
    navigating = asyncio.Event()
    finish_navigation = asyncio.Event()

    async def navigate(*_args: object, **_kwargs: object) -> None:
        navigating.set()
        await finish_navigation.wait()

    page.goto.side_effect = navigate
    manager = MagicMock(start=AsyncMock(return_value=playwright_mock))
    session = _ScreenshotSession("http://localhost:1234")
    with patch(
        "marimo._code_mode.screenshot._require_playwright",
        return_value=lambda: manager,
    ):
        first = asyncio.create_task(session._ensure_ready())
        await navigating.wait()
        second = asyncio.create_task(session._ensure_ready())
        await asyncio.sleep(0)
        assert not second.done()
        finish_navigation.set()
        await asyncio.gather(first, second)
        playwright_mock.chromium.launch.assert_awaited_once()
        await session.close()


async def test_close_stops_playwright_even_if_browser_close_fails(
    playwright_mock: MagicMock,
) -> None:
    browser = playwright_mock.chromium.launch.return_value
    browser.close.side_effect = RuntimeError("close failed")
    manager = MagicMock(start=AsyncMock(return_value=playwright_mock))
    session = _ScreenshotSession("http://localhost:1234")
    with patch(
        "marimo._code_mode.screenshot._require_playwright",
        return_value=lambda: manager,
    ):
        await session._ensure_ready()
        with pytest.raises(RuntimeError, match="close failed"):
            await session.close()
        playwright_mock.stop.assert_awaited_once()
        assert session._page is None
        assert session._browser is None
        assert session._playwright is None
        await session.close()
        playwright_mock.stop.assert_awaited_once()


@pytest.mark.parametrize("first_fails", [False, True])
async def test_concurrent_captures_serialize_navigation_and_screenshot(
    first_fails: bool,
) -> None:
    session = _ScreenshotSession("http://localhost:1234")
    session._page = AsyncMock()
    target = AsyncMock()
    screenshot_started = asyncio.Event()
    finish_screenshot = asyncio.Event()
    calls = 0

    async def screenshot(**_kwargs: object) -> bytes:
        nonlocal calls
        calls += 1
        if calls == 1:
            screenshot_started.set()
            await finish_screenshot.wait()
            if first_fails:
                raise RuntimeError("capture failed")
        return b"png"

    target.screenshot.side_effect = screenshot
    with (
        patch.object(session, "_ensure_ready", new_callable=AsyncMock),
        patch.object(session, "_navigate", new_callable=AsyncMock) as navigate,
        patch.object(session, "_wait_for_output", return_value="ready"),
        patch.object(session, "_resolve_output_locator", return_value=target),
    ):
        first = asyncio.create_task(session.capture(CellId_t("cell-a")))
        await asyncio.wait_for(screenshot_started.wait(), timeout=1)
        second = asyncio.create_task(session.capture(CellId_t("cell-b")))
        try:
            await asyncio.sleep(0)
            navigate.assert_awaited_once_with(initial=False)
            target.screenshot.assert_awaited_once()
            assert not second.done()
        finally:
            finish_screenshot.set()
            results = await asyncio.gather(
                first, second, return_exceptions=True
            )
        if first_fails:
            assert isinstance(results[0], RuntimeError)
        else:
            assert results[0] == b"png"
        assert results[1] == b"png"
        assert navigate.await_count == 2


async def test_close_waits_for_active_capture() -> None:
    session = _ScreenshotSession("http://localhost:1234")
    browser = AsyncMock()
    session._browser = browser
    capture_started = asyncio.Event()
    finish_capture = asyncio.Event()

    async def capture(*_args: object, **_kwargs: object) -> bytes:
        capture_started.set()
        await finish_capture.wait()
        assert session._browser is browser
        return b"png"

    with patch.object(session, "_capture", side_effect=capture):
        capturing = asyncio.create_task(session.capture(CellId_t("cell-a")))
        await asyncio.wait_for(capture_started.wait(), timeout=1)
        closing = asyncio.create_task(session.close())
        try:
            await asyncio.sleep(0)
            browser.close.assert_not_awaited()
        finally:
            finish_capture.set()
            assert await capturing == b"png"
            await closing
        browser.close.assert_awaited_once()
