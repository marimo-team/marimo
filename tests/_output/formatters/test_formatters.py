from __future__ import annotations

import importlib
import os.path
from unittest.mock import Mock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import (
    Plain,
    as_html,
    formatter,
    get_formatter,
    try_format,
)


def test_path_finder_find_spec() -> None:
    # exercises a bug surfaced in
    # https://github.com/marimo-team/marimo/issues/763, in which find_spec
    # would fail because it was incorrectly patched
    register_formatters()

    spec = importlib.machinery.PathFinder.find_spec(
        "test_formatters", [os.path.dirname(__file__)]
    )
    assert spec is not None


HAS_DEPS = DependencyManager.has_pandas() and DependencyManager.has_polars()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_formatters_with_opinionated_formatter() -> None:
    register_formatters()

    import pandas as pd
    import polars as pl

    pd_df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})
    pl_df = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})

    # Happy path
    obj = ["test"]
    formatter = get_formatter(obj)
    assert formatter
    assert formatter(obj) == ("application/json", '["text/plain:\\"test\\""]')

    # With Plain
    obj = Plain(["test"])
    formatter = get_formatter(obj)
    assert formatter
    assert formatter(obj) == ("application/json", '["text/plain:\\"test\\""]')

    # With pandas DataFrame
    formatter = get_formatter(pd_df)
    assert formatter
    mime, content = formatter(pd_df)
    assert mime == "text/html"
    assert "<marimo-table" in content

    # With plain DataFrame + Plain
    obj = Plain(pd_df)
    formatter = get_formatter(obj)
    assert formatter
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert "<marimo-table" not in content

    # With polars DataFrame
    formatter = get_formatter(pl_df)
    assert formatter
    mime, content = formatter(pl_df)
    assert mime == "text/html"
    assert "<marimo-table" in content

    # With plain DataFrame + Plain
    obj = Plain(pl_df)
    formatter = get_formatter(obj)
    assert formatter
    mime, content = formatter(obj)
    assert mime == "text/html"
    assert "<marimo-table" not in content


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_as_html_opinionated_formatter():
    register_formatters()

    import pandas as pd
    import polars as pl

    pd_df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})
    pl_df = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})

    # With pandas DataFrame
    html = as_html(pd_df)
    assert "<marimo-table" in html.text

    # With polars DataFrame
    html = as_html(pl_df)
    assert "<marimo-table" in html.text

    # With pandas DataFrame + Plain
    html = as_html(Plain(pd_df))
    assert "<marimo-table" not in html.text

    # With polars DataFrame + Plain
    html = as_html(Plain(pl_df))
    assert "<marimo-table" not in html.text


def test_broken_formatter():
    class _ClsForBrokenFormatter:
        ...

    def _format(cls: _ClsForBrokenFormatter) -> tuple[KnownMimeType, str]:
        del cls
        raise BaseException("Broken Formatter")

    formatter(_ClsForBrokenFormatter)(_format)

    obj = _ClsForBrokenFormatter()
    formatted = try_format(obj)
    assert formatted.traceback is not None
    assert "Broken Formatter" in formatted.traceback


@patch(
    "marimo._output.formatters.formatters.THIRD_PARTY_FACTORIES",
    new_callable=dict,
)
@patch("sys.modules", new_callable=dict)
def test_pre_imported_formatter(mock_sys_modules, mock_third_party_factories):
    mock_sys_modules["fake_module"] = Mock()

    mock_factory = Mock()
    mock_third_party_factories["fake_module"] = mock_factory

    register_formatters()
    assert mock_factory.register.call_count == 1
