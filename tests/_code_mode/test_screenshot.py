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


async def test_screenshot_rejects_currently_empty_browser_output() -> None:
    session = _ScreenshotSession("http://localhost:1234")
    session._page = MagicMock()
    with (
        patch.object(session, "_ensure_ready", new_callable=AsyncMock),
        patch.object(session, "_wait_for_container", new_callable=AsyncMock),
        patch.object(
            session,
            "_container_has_content",
            new_callable=AsyncMock,
            return_value=False,
        ) as has_content,
        patch.object(
            session, "_resolve_output_locator", new_callable=AsyncMock
        ) as resolve_output,
    ):
        with pytest.raises(ScreenshotError, match="has no rendered content"):
            await session.capture(CellId_t("cell-a"))
        has_content.assert_awaited_once_with("#output-cell-a")
        resolve_output.assert_not_awaited()


@pytest.fixture
def playwright_mock() -> MagicMock:
    playwright = MagicMock()
    playwright.stop = AsyncMock()
    browser = AsyncMock()
    page = AsyncMock()
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
