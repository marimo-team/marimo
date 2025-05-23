from __future__ import annotations

import ast
from datetime import datetime
from typing import Any

import pytest

from marimo._data.charts import (
    ChartBuilder,
    DateChartBuilder,
    get_chart_builder,
)
from marimo._data.models import DataType
from marimo._dependencies.dependencies import DependencyManager
from tests._data.mocks import NON_EAGER_LIBS, create_dataframes
from tests.mocks import snapshotter

TYPES: list[tuple[DataType, bool]] = [
    ("boolean", False),
    ("date", False),
    ("datetime", False),
    ("time", False),
    ("integer", False),
    ("number", False),
    ("string", False),
    ("string", True),
    ("unknown", False),
]

snapshot = snapshotter(__file__)

HAS_DEPS = DependencyManager.pandas.has() and DependencyManager.altair.has()


def test_get_chart_builder():
    for t, should_limit_to_10_items in TYPES:
        assert isinstance(
            get_chart_builder(t, should_limit_to_10_items), ChartBuilder
        )


def test_charts_altair_code():
    outputs: list[str] = []

    for t, should_limit_to_10_items in TYPES:
        builder = get_chart_builder(t, should_limit_to_10_items)
        code = builder.altair_code("df", "some_column")
        # Validate it is valid Python code
        try:
            ast.parse(code)
        except SyntaxError as e:
            raise SyntaxError(f"Invalid Python code for {t}") from e
        title = f"{t} (limit to 10 items)" if should_limit_to_10_items else t
        outputs.append(f"# {title}\n{code}")

    snapshot("charts.txt", "\n\n".join(outputs))


def test_charts_bad_characters():
    outputs: list[str] = []
    builder = get_chart_builder("string", False)
    chars = {
        "<": "angles",
        "[0]": "brackets",
        ":": "colon",
        ".": "period",
        "\\": "backslash",
    }

    for char, name in chars.items():
        col = f"col{char}{name}"
        code = builder.altair_code("df", col)
        outputs.append(f"# {col}\n{code}")

    snapshot("charts_bad_characters.txt", "\n\n".join(outputs))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_charts_altair_json():
    outputs: list[str] = []
    import altair as alt
    import pandas as pd

    data = pd.DataFrame({"some_column": [1, 2, 3]})

    for t, should_limit_to_10_items in TYPES:
        builder = get_chart_builder(t, should_limit_to_10_items)
        code = builder.altair_json(data, "some_column")
        # Validate it is valid JSON
        alt.Chart.from_json(code)
        title = f"{t} (limit to 10 items)" if should_limit_to_10_items else t
        outputs.append(f"# {title}\n{code}")

    snapshot("charts_json.txt", "\n\n".join(outputs))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_charts_altair_json_bad_data():
    import altair as alt
    import pandas as pd

    data = pd.DataFrame({"some[0]really.bad:column": [1, 2, 3]})

    build = get_chart_builder("string", False)
    code = build.altair_json(data, "some[0]really.bad:column")
    # Validate it is valid JSON
    alt.Chart.from_json(code)
    snapshot("charts_json_bad_data.txt", code)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    ("data", "expected_format"),
    [
        # More than 10 years
        (
            ({"dates": [datetime(2000, 1, 1), datetime(2020, 1, 1)]}),
            ("%Y", "year"),
        ),
        # More than a year
        (
            ({"dates": [datetime(2020, 1, 1), datetime(2021, 6, 1)]}),
            ("%Y-%m", "yearmonth"),
        ),
        # More than a month
        (
            ({"dates": [datetime(2020, 1, 1), datetime(2020, 2, 15)]}),
            ("%Y-%m-%d", "yearmonthdate"),
        ),
        # More than a day
        (
            (
                {
                    "dates": [
                        datetime(2020, 1, 1, 0, 0),
                        datetime(2020, 1, 2, 12, 0),
                    ]
                }
            ),
            ("%Y-%m-%d %H:%M", "yearmonthdatehoursminutes"),
        ),
        # Less than a day
        (
            (
                {
                    "dates": [
                        datetime(2020, 1, 1, 0, 0, 0),
                        datetime(2020, 1, 1, 12, 30, 45),
                    ]
                }
            ),
            ("%Y-%m-%d %H:%M", "yearmonthdatehoursminutes"),
        ),
    ],
)
def test_date_chart_builder_guess_date_format_with_dataframes(
    data: dict[str, list[Any]], expected_format: str
):
    eager_dfs = create_dataframes(data, exclude=NON_EAGER_LIBS)
    assert len(eager_dfs) > 0

    builder = DateChartBuilder()
    for df in eager_dfs:
        date_format, time_unit = builder._guess_date_format(df, "dates")
        assert (
            date_format,
            time_unit,
        ) == expected_format, f"Expected {expected_format} for {type(df)}"

    non_eager_dfs = create_dataframes(data, include=NON_EAGER_LIBS)
    for df in non_eager_dfs:
        date_format, time_unit = builder._guess_date_format(df, "dates")
        assert (
            date_format,
            time_unit,
        ) == (
            DateChartBuilder.DEFAULT_DATE_FORMAT,
            DateChartBuilder.DEFAULT_TIME_UNIT,
        ), f"Expected {DateChartBuilder.DEFAULT_DATE_FORMAT} for {type(df)}"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_date_chart_builder_guess_date_format_with_non_narwhalifiable_data():
    builder = DateChartBuilder()

    # Test with non-narwhalifiable data
    class NonNarwhalifiableData:
        pass

    date_format, time_unit = builder._guess_date_format(
        NonNarwhalifiableData(), "dates"
    )
    assert date_format == DateChartBuilder.DEFAULT_DATE_FORMAT
    assert time_unit == DateChartBuilder.DEFAULT_TIME_UNIT


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_date_chart_builder_get_date_format():
    from datetime import datetime

    import pandas as pd

    builder = DateChartBuilder()

    # Test with non-cached format (should guess)
    data = pd.DataFrame(
        {"dates": [datetime(2020, 1, 1), datetime(2020, 2, 1)]}
    )

    # First call should guess the format
    date_format, time_unit = builder._get_date_format(data, "dates")
    assert date_format == "%Y-%m-%d %H"
    assert time_unit == "yearmonthdatehours"

    # Second call should use cached format
    date_format2, time_unit2 = builder._get_date_format(data, "dates")
    assert date_format2 == date_format
    assert time_unit2 == time_unit

    # Test with manually set format
    builder2 = DateChartBuilder()
    builder2.date_format = "%Y"
    builder2.time_unit = "year"

    date_format3, time_unit3 = builder2._get_date_format(data, "dates")
    assert date_format3 == "%Y"
    assert time_unit3 == "year"
