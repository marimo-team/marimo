from __future__ import annotations

import json
import sys
from datetime import datetime
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, call, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.altair_formatters import (
    FETCH_TIMEOUT,
    FORMAT_LOCALE_URL,
    TIME_FORMAT_LOCALE_URL,
    AltairFormatter,
    _apply_format_locales,
    _maybe_warn_external_resources,
)
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import get_formatter
from tests._data.mocks import create_dataframes

HAS_DEPS = DependencyManager.altair.has() and DependencyManager.polars.has()

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


def assert_vegalite_mimetype(mime: str) -> None:
    """Assert that the mime type is a valid vega-lite mime type (v5 or v6)."""
    assert mime in (
        "application/vnd.vegalite.v5+json",
        "application/vnd.vegalite.v6+json",
    ), f"Expected vega-lite mime type (v5 or v6), got {mime}"


def assert_vega_mimetype(mime: str) -> None:
    """Assert that the mime type is a valid vega mime type (v5 or v6)."""
    assert mime in (
        "application/vnd.vega.v5+json",
        "application/vnd.vega.v6+json",
    ), f"Expected vega mime type (v5 or v6), got {mime}"


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
    assert_vegalite_mimetype(mime)
    assert isinstance(content, str)
    # Verify it's valid JSON
    json_content = json.loads(content)
    assert "data" in json_content
    assert "mark" in json_content
    assert "encoding" in json_content


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
def test_altair_formatter_respects_default_width():
    AltairFormatter().register()

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

    formatter = get_formatter(chart)
    assert formatter is not None
    res = formatter(chart)
    assert res is not None
    mime, content = res
    assert_vegalite_mimetype(mime)
    assert isinstance(content, str)
    json_content = json.loads(content)
    assert json_content.get("width") != "container"


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
def test_altair_formatter_vegafusion_dark_mode():
    AltairFormatter().register()

    import altair as alt

    with alt.data_transformers.enable("vegafusion"):
        chart = alt.Chart(get_data()).mark_point()
        formatter = get_formatter(chart)

        assert formatter is not None
        res = formatter(chart)
        assert res is not None
        mime, content = res
        assert_vega_mimetype(mime)
        assert isinstance(content, str)
        json_data = json.loads(content)
        assert "background" in json_data
        assert json_data["background"] == "transparent"


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
            "application/vnd.vegalite.v6+json": json.dumps({"test": "data"}),
        },
    ):
        formatter = get_formatter(mock_chart)
        assert formatter is not None
        mime, content = formatter(mock_chart)

        # Should return a mimebundle with both types
        assert mime == "application/vnd.marimo+mimebundle"
        mimebundle = json.loads(content)
        assert "image/svg+xml" in mimebundle
        assert "application/vnd.vegalite.v6+json" in mimebundle


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
@pytest.mark.parametrize(
    ("raw_svg", "expected"),
    [
        (True, "<svg></svg>"),
        (False, "data:image/svg+xml;base64,PHN2Zz48L3N2Zz4="),
    ],
)
def test_altair_formatter_svg(raw_svg: bool, expected: str):
    AltairFormatter().register()

    import altair as alt

    # Create a mock chart with a _repr_mimebundle_ method that returns SVG
    mock_chart = alt.Chart(get_data()).mark_point()
    with (
        patch.dict(alt.renderers.options, {"raw_svg": raw_svg}),
        patch.object(
            alt.Chart,
            "_repr_mimebundle_",
            return_value={"image/svg+xml": "<svg></svg>"},
        ),
    ):
        formatter = get_formatter(mock_chart)
        assert formatter is not None
        mime, content = formatter(mock_chart)

        assert mime == "image/svg+xml"
        assert content == expected


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
def test_altair_formatter_png():
    AltairFormatter().register()

    import altair as alt

    # Create a mock chart with a _repr_mimebundle_ method that returns PNG
    mock_chart = alt.Chart(get_data()).mark_point()
    with patch.object(
        alt.Chart,
        "_repr_mimebundle_",
        return_value=(
            {"image/png": b"png"},
            {"image/png": {"width": 10.2, "height": 19.8}},
        ),
    ):
        formatter = get_formatter(mock_chart)
        assert formatter is not None
        mime, content = formatter(mock_chart)

        assert mime == "application/vnd.marimo+mimebundle"
        assert content.startswith('{"image/png": "data:image/png;base64,cG5n"')
        assert content.endswith('{"image/png": {"width": 10, "height": 20}}}')


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
    assert_vegalite_mimetype(mime)
    assert isinstance(content, str)

    for non_valid_value in ["NaN", "Infinity", "-Infinity"]:
        assert non_valid_value not in content
    assert content.count('"B": null') == 3


@pytest.mark.skipif(not HAS_DEPS, reason="altair not installed")
def test_altair_formatter_embed_options():
    AltairFormatter().register()
    import altair as alt

    format_locale = {"decimal": ".", "thousands": ","}
    time_format_locale = {"date": "%m/%d/%Y", "time": "%H:%M:%S"}

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

    try:
        alt.renderers.set_embed_options(formatLocale=format_locale)
        content = get_formatted_content(get_chart())
        assert content["usermeta"]["embedOptions"] == {
            "formatLocale": format_locale
        }

        alt.renderers.set_embed_options(timeFormatLocale=time_format_locale)
        content = get_formatted_content(get_chart())
        assert content["usermeta"]["embedOptions"] == {
            "timeFormatLocale": time_format_locale
        }

        alt.renderers.set_embed_options()
        content = get_formatted_content(get_chart())
        assert content["usermeta"]["embedOptions"] == {}
    finally:
        alt.renderers.set_embed_options()


def test_apply_format_locales_with_vl_convert() -> None:
    format_locale = {"decimal": "."}
    time_format_locale = {"date": "%m/%d/%Y"}
    vl_convert = MagicMock()
    vl_convert.get_format_locale.return_value = format_locale
    vl_convert.get_time_format_locale.return_value = time_format_locale

    with (
        patch.object(
            DependencyManager.vl_convert_python, "has", return_value=True
        ),
        patch.dict(sys.modules, {"vl_convert": vl_convert}),
    ):
        result = _apply_format_locales(
            {"formatLocale": "en-US", "timeFormatLocale": "en-US"}
        )

    assert result == {
        "formatLocale": format_locale,
        "timeFormatLocale": time_format_locale,
    }
    vl_convert.get_format_locale.assert_called_once_with("en-US")
    vl_convert.get_time_format_locale.assert_called_once_with("en-US")


def test_apply_format_locales_with_http_fallback() -> None:
    format_locale = {"decimal": "."}
    time_format_locale = {"date": "%m/%d/%Y"}
    time_response = MagicMock()
    time_response.__enter__.return_value.read.return_value = json.dumps(
        time_format_locale
    ).encode()
    format_response = MagicMock()
    format_response.__enter__.return_value.read.return_value = json.dumps(
        format_locale
    ).encode()

    with (
        patch.object(
            DependencyManager.vl_convert_python, "has", return_value=False
        ),
        patch(
            "marimo._output.formatters.altair_formatters.urlopen",
            side_effect=[time_response, format_response],
        ) as mock_urlopen,
    ):
        result = _apply_format_locales(
            {"formatLocale": "en-US", "timeFormatLocale": "en-US"}
        )

    assert result == {
        "formatLocale": format_locale,
        "timeFormatLocale": time_format_locale,
    }
    assert mock_urlopen.call_args_list == [
        call(
            TIME_FORMAT_LOCALE_URL.format(locale="en-US"),
            timeout=FETCH_TIMEOUT,
        ),
        call(
            FORMAT_LOCALE_URL.format(locale="en-US"),
            timeout=FETCH_TIMEOUT,
        ),
    ]


def test_apply_format_locales_handles_http_timeout() -> None:
    with (
        patch.object(
            DependencyManager.vl_convert_python, "has", return_value=False
        ),
        patch(
            "marimo._output.formatters.altair_formatters.urlopen",
            side_effect=TimeoutError("read timed out"),
        ),
        patch(
            "marimo._output.formatters.altair_formatters.LOGGER.warning"
        ) as mock_warning,
    ):
        result = _apply_format_locales({"formatLocale": "en-US"})

    assert result == {"formatLocale": {}}
    mock_warning.assert_called_once_with(
        "Error getting format locale: read timed out"
    )


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        ('<image xlink:href="https://ffox.png"/>', True),
        ('<image href="#id"/>', False),
        ('<image href="data:image/png;base64,xxx"/>', False),
        ('<image href=" https://ffox.png"/>', True),
        ('<image href=" #id"/>', False),
    ],
)
def test_maybe_warn_external_resource(content: str, expected: bool) -> None:
    with patch(
        "marimo._output.formatters.altair_formatters.LOGGER.warning"
    ) as mock_warning:
        _maybe_warn_external_resources(content)
        if expected:
            mock_warning.assert_called_once()
            assert "raw_svg=True" in mock_warning.call_args[0][0]
        else:
            mock_warning.assert_not_called()
