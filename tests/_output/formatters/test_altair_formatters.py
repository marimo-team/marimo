from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.altair_formatters import AltairFormatter
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import get_formatter
from marimo._plugins.ui._impl.altair_chart import maybe_make_full_width

HAS_DEPS = DependencyManager.altair.has() and DependencyManager.polars.has()


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
    mock_chart = MagicMock(spec=alt.Chart)
    mock_chart._repr_mimebundle_.return_value = {
        "image/svg+xml": "<svg></svg>",
        "application/vnd.vegalite.v5+json": json.dumps({"test": "data"}),
    }

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
    mock_chart = MagicMock(spec=alt.Chart)
    mock_chart._repr_mimebundle_.return_value = {
        "image/svg+xml": "<svg></svg>"
    }

    formatter = get_formatter(mock_chart)
    assert formatter is not None
    mime, content = formatter(mock_chart)

    assert mime == "image/svg+xml"
    assert content == "<svg></svg>"
