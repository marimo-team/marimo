# Copyright 2024 Marimo. All rights reserved.

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.hypertext import Html
from marimo._plugins.stateless.stat import try_convert_to_html


def test_try_convert_to_html_valid_html():
    result = try_convert_to_html("<div>Hello, World!</div>")
    assert result is not None
    assert result.text == "<span>&lt;div&gt;Hello, World!&lt;/div&gt;</span>"


def test_try_convert_to_html_plain():
    result = try_convert_to_html(123)
    assert isinstance(result, Html)
    assert result.text == "<span>123</span>"


def test_try_convert_to_html_none():
    result = try_convert_to_html(None)
    assert result is None


@pytest.mark.skipif(
    not DependencyManager.altair.has() or not DependencyManager.pandas.has(),
    reason="optional dependencies not installed",
)
def test_try_convert_to_html_altair_chart():
    import altair as alt
    import pandas as pd

    df = pd.DataFrame({"x": [1, 2, 3], "y": [4, 5, 6]})
    chart = alt.Chart(df).mark_point().encode(x="x", y="y")
    result = try_convert_to_html(chart)
    assert isinstance(result, Html)
    assert "<marimo-mime-renderer" in result.text
    assert "application/vnd.vega" in result.text
