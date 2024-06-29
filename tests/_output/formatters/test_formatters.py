from __future__ import annotations

import importlib
import os.path

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import Plain, get_formatter


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

    register_formatters()

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

    register_formatters()

    pd_df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})
    pl_df = pl.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})

    from marimo._output.formatting import as_html

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
