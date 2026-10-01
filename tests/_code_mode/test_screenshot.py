# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import pytest

from marimo._ast.cell import CellConfig
from marimo._code_mode._context import (
    AsyncCodeModeContext,
    NotebookCell,
)
from marimo._code_mode.screenshot import (
    ScreenshotError,
    _ScreenshotOutput,
    _ScreenshotSession,
    _to_data_url,
)
from marimo._messaging.cell_output import CellOutput
from marimo._messaging.notebook.document import (
    NotebookCell as _DocNotebookCell,
)
from marimo._messaging.notebook.outputs import CellOutputs
from marimo._output.formatting import try_format
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from typing import Any


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


class TestScreenshotOutput:
    def test_formats_png_without_html_wrapper(self) -> None:
        png = b"\x89PNG\r\n\x1a\n" + b"payload"

        output = try_format(_ScreenshotOutput(png))

        assert output.mimetype == "image/png"
        assert output.data == _to_data_url(png)
        assert "<pre" not in output.data


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
            screenshot_auth_token="secret",
            file_key="notebooks/my notebook.py",
        )
        page_url = session._page_url()
        query = parse_qs(urlparse(page_url).query)

        assert query == {
            "access_token": ["secret"],
            "file": ["notebooks/my notebook.py"],
            "kiosk": ["true"],
        }

    def test_page_url_omits_token_when_none(self) -> None:
        session = _ScreenshotSession("http://localhost:9999")
        page_url = session._page_url()

        assert "access_token" not in page_url
        assert page_url == "http://localhost:9999?kiosk=true"


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
    return SimpleNamespace(
        cells=_FakeCells(cell_ids, names),
        graph=SimpleNamespace(cells={}),
        _document=SimpleNamespace(cells=[]),
    )


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

    def test_str_resolves_uniquely_defined_variable(self) -> None:
        ctx = _fake_ctx(["cell-a", "cell-b"])
        ctx._document.cells = [
            _DocNotebookCell(
                id=CellId_t("cell-a"),
                code="source = [1, 2, 3]",
                name="",
                config=CellConfig(),
            ),
            _DocNotebookCell(
                id=CellId_t("cell-b"),
                code="chart = source",
                name="",
                config=CellConfig(),
            ),
        ]

        assert _resolve(ctx, "chart") == CellId_t("cell-b")

    def test_str_does_not_resolve_ambiguous_variable(self) -> None:
        ctx = _fake_ctx(["cell-a", "cell-b"])
        ctx.graph.cells = {
            CellId_t("cell-a"): SimpleNamespace(defs={"chart"}),
            CellId_t("cell-b"): SimpleNamespace(defs={"chart"}),
        }

        with pytest.raises(ScreenshotError, match="uniquely defined variable"):
            _resolve(ctx, "chart")

    def test_str_unknown_raises(self) -> None:
        ctx = _fake_ctx(["cell-a"])
        with pytest.raises(
            ScreenshotError, match="Unknown cell ID, name, or uniquely"
        ):
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


def test_notebook_cell_distinguishes_empty_rendered_output() -> None:
    cell_id = CellId_t("cell-a")
    doc_cell = _DocNotebookCell(
        id=cell_id,
        code="value = 1",
        name="",
        config=CellConfig(),
    )
    empty_cell = NotebookCell(
        doc_cell,
        cell_impl=None,
        outputs=CellOutputs(
            output={cell_id: CellOutput.empty()},
            console_outputs={},
        ),
    )
    visible_cell = NotebookCell(
        doc_cell,
        cell_impl=None,
        outputs=CellOutputs(
            output={
                cell_id: CellOutput(
                    channel=CellOutput.empty().channel,
                    mimetype="text/plain",
                    data="1",
                )
            },
            console_outputs={},
        ),
    )

    assert empty_cell.has_output is False
    assert visible_cell.has_output is True


@pytest.mark.asyncio
async def test_screenshot_rejects_missing_output_before_browser() -> None:
    ctx = SimpleNamespace(
        _resolve_screenshot_target=lambda _target: CellId_t("cell-a"),
        _outputs=CellOutputs(output={}, console_outputs={}),
        cells={"cell-a": SimpleNamespace(has_output=False)},
    )

    with pytest.raises(
        ScreenshotError,
        match="exists but has no recorded rendered output",
    ):
        await AsyncCodeModeContext.screenshot(ctx, "cell-a")


@pytest.mark.asyncio
async def test_screenshot_rejects_empty_output_before_browser() -> None:
    ctx = SimpleNamespace(
        _resolve_screenshot_target=lambda _target: CellId_t("cell-a"),
        _outputs=CellOutputs(
            output={CellId_t("cell-a"): CellOutput.empty()},
            console_outputs={},
        ),
        cells={"cell-a": SimpleNamespace(has_output=False)},
    )

    with pytest.raises(
        ScreenshotError,
        match="exists but has no recorded rendered output",
    ):
        await AsyncCodeModeContext.screenshot(ctx, "cell-a")
