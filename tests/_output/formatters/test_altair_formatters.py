from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from urllib.request import urlopen

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.altair_formatters import (
    FORMAT_LOCALE_URL,
    TIME_FORMAT_LOCALE_URL,
    AltairFormatter,
)
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import get_formatter
from marimo._plugins.ui._impl.altair_chart import maybe_make_full_width
from tests._data.mocks import create_dataframes

HAS_DEPS = DependencyManager.altair.has() and DependencyManager.polars.has()

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


def get_data():
    import polars as pl

    return pl.DataFrame(
        {
            "Horsepower": [100, 150, 200],
            "Miles_per_Gallon": [20, 25, 30],
            "Origin": ["USA", "Europe", "Asia"],
        }
    )


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
def test_altair_formatter_registration():
    register_formatters()

    import altair as alt

    cars = get_data()
    chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
            color="Origin",
        )
    )

    formatter = get_formatter(chart)
    assert formatter is not None
    mime, content = formatter(chart)
    assert mime == "application/vnd.vegalite.v5+json"
    assert isinstance(content, str)
    # Verify it's valid JSON
    json_content = json.loads(content)
    assert "data" in json_content
    assert "mark" in json_content
    assert "encoding" in json_content


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
@patch("marimo._output.formatters.altair_formatters.maybe_make_full_width")
def test_altair_formatter_full_width(mock_make_full_width: MagicMock):
    AltairFormatter().register()

    mock_make_full_width.side_effect = maybe_make_full_width

    import altair as alt

    cars = get_data()
    chart = (
        alt.Chart(cars)
        .mark_point()
        .encode(
            x="Horsepower",
            y="Miles_per_Gallon",
        )
    )

    mock_make_full_width.return_value = chart

    formatter = get_formatter(chart)
    assert formatter is not None
    res = formatter(chart)
    assert res is not None
    mime, content = res
    assert mime == "application/vnd.vegalite.v5+json"
    assert isinstance(content, str)
    assert "container" in content

    # Verify maybe_make_full_width was called
    mock_make_full_width.assert_called_once()


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
def test_altair_formatter_mimebundle():
    AltairFormatter().register()

    import altair as alt

    # Create a mock chart with a _repr_mimebundle_ method that returns multiple mime types
    mock_chart = alt.Chart(get_data()).mark_point()
    with patch.object(
        alt.Chart,
        "_repr_mimebundle_",
        return_value={
            "image/svg+xml": "<svg></svg>",
            "application/vnd.vegalite.v5+json": json.dumps({"test": "data"}),
        },
    ):
        formatter = get_formatter(mock_chart)
        assert formatter is not None
        mime, content = formatter(mock_chart)

        # Should return a mimebundle with both types
        assert mime == "application/vnd.marimo+mimebundle"
        mimebundle = json.loads(content)
        assert "image/svg+xml" in mimebundle
        assert "application/vnd.vegalite.v5+json" in mimebundle


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
def test_altair_formatter_svg():
    AltairFormatter().register()

    import altair as alt

    # Create a mock chart with a _repr_mimebundle_ method that returns SVG
    mock_chart = alt.Chart(get_data()).mark_point()
    with patch.object(
        alt.Chart,
        "_repr_mimebundle_",
        return_value={"image/svg+xml": "<svg></svg>"},
    ):
        formatter = get_formatter(mock_chart)
        assert formatter is not None
        mime, content = formatter(mock_chart)

        assert mime == "image/svg+xml"
        assert content == "<svg></svg>"


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3],
            "B": [-float("inf"), float("nan"), float("inf")],
            "C": ["a", "b", "c"],
            "D": [1.0, 2.0, float("nan")],
            "E": [
                datetime(2020, 1, 1),
                datetime(2020, 1, 2),
                datetime(2020, 1, 3),
            ],
            "F": [None, None, None],
        },
        include=["polars", "pandas"],
    ),
)
def test_altair_formatter_sanitize_nan_infs(df: IntoDataFrame):
    AltairFormatter().register()

    import altair as alt

    chart = alt.Chart(df).mark_point().encode(x="A", y="B")
    formatter = get_formatter(chart)
    assert formatter is not None
    mime, content = formatter(chart)
    assert mime == "application/vnd.vegalite.v5+json"
    assert isinstance(content, str)

    for non_valid_value in ["NaN", "Infinity", "-Infinity"]:
        assert non_valid_value not in content
    assert content.count('"B": null') == 3


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
def test_altair_formatter_embed_options():
    AltairFormatter().register()
    import altair as alt

    def get_chart():
        return (
            alt.Chart(get_data())
            .mark_point()
            .encode(x="Horsepower", y="Miles_per_Gallon")
        )

    def get_formatted_content(chart):
        formatter = get_formatter(chart)
        assert formatter is not None
        _, content = formatter(chart)
        return json.loads(content)

    # Test format locale
    alt.renderers.set_embed_options(formatLocale="en-US")
    content = get_formatted_content(get_chart())
    assert "formatLocale" in content["usermeta"]["embedOptions"]
    assert "timeFormatLocale" not in content["usermeta"]["embedOptions"]
    with urlopen(
        FORMAT_LOCALE_URL.format(locale="en-US"), timeout=3
    ) as response:
        assert content["usermeta"]["embedOptions"][
            "formatLocale"
        ] == json.loads(response.read())

    # Test adding a time format locale
    alt.renderers.set_embed_options(timeFormatLocale="en-US")
    content = get_formatted_content(get_chart())
    assert "timeFormatLocale" in content["usermeta"]["embedOptions"]
    with urlopen(
        TIME_FORMAT_LOCALE_URL.format(locale="en-US"), timeout=3
    ) as response:
        assert content["usermeta"]["embedOptions"][
            "timeFormatLocale"
        ] == json.loads(response.read())

    # Old embed option is no longer present
    assert "formatLocale" not in content["usermeta"]["embedOptions"]

    # Test reset embed options
    alt.renderers.set_embed_options()
    content = get_formatted_content(get_chart())
    assert content["usermeta"]["embedOptions"] == {}
