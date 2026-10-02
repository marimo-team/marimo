from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import (
    get_formatter,
)
from marimo._plugins.ui._impl.table import (
    DownloadAsArgs,
    SearchTableArgs,
    SortArgs,
    table,
)
from marimo._utils.data_uri import from_data_uri

HAS_DEPS = DependencyManager.pandas.has()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize("as_series", [False, True])
@pytest.mark.parametrize("dtype", ["float64", "Float64"])
def test_pandas_float_format(as_series: bool, dtype: str) -> None:
    register_formatters()

    import pandas as pd

    values = pd.Series([10.125, 2.125, None], dtype=dtype)
    data = (
        values
        if as_series
        else pd.DataFrame(
            {"value": values, "count": [1, 2, 3], "label": ["a", "b", "c"]}
        )
    )
    original = data.copy(deep=True)
    formatter = get_formatter(data, include_opinionated=True)
    assert formatter is not None

    # Capture the real table so its RPCs can be exercised after rendering.
    with patch.object(table, "_mime_", autospec=True) as mime:
        mime.return_value = ("text/html", "")
        with pd.option_context("display.float_format", "{:.2f}".format):
            formatter(data)
        rendered = mime.call_args.args[0]

    response = rendered._search(
        SearchTableArgs(
            page_size=2,
            page_number=0,
            sort=[SortArgs(by="value", descending=False)],
        )
    )
    assert [row["value"] for row in json.loads(response.data)] == [
        "2.12",
        "10.12",
    ]
    assert response.raw_data is not None
    assert [row["value"] for row in json.loads(response.raw_data)] == [
        2.125,
        10.125,
    ]
    if not as_series:
        assert [row["count"] for row in json.loads(response.data)] == [2, 1]
        assert [row["label"] for row in json.loads(response.data)] == [
            "b",
            "a",
        ]

    response = rendered._search(SearchTableArgs(page_size=3, page_number=0))
    assert pd.isna(json.loads(response.data)[2]["value"])
    download = rendered._download_as(DownloadAsArgs(format="json"))
    assert [
        row["value"] for row in json.loads(from_data_uri(download.url)[1])
    ] == [10.125, 2.125, None]
    if as_series:
        pd.testing.assert_series_equal(data, original)
    else:
        pd.testing.assert_frame_equal(data, original)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    ("column", "display_column"),
    [("value", "value"), (0, "0"), (("group", "value"), "group,value")],
)
def test_pandas_float_format_default_and_explicit_table(
    column: Any, display_column: str
) -> None:
    register_formatters()

    import pandas as pd

    df = pd.DataFrame({column: [0.8331949753793817]})
    formatter = get_formatter(df, include_opinionated=True)
    assert formatter is not None
    with pd.option_context("display.float_format", None):
        with patch.object(table, "_mime_", autospec=True) as mime:
            mime.return_value = ("text/html", "")
            formatter(df)
            rendered = mime.call_args.args[0]
        response = rendered._search(
            SearchTableArgs(page_size=1, page_number=0)
        )
        assert (
            json.loads(response.data)[0][display_column] == 0.8331949753793817
        )
        assert response.raw_data is None

    with pd.option_context("display.float_format", "{:.2g}".format):
        with patch.object(table, "_mime_", autospec=True) as mime:
            mime.return_value = ("text/html", "")
            formatter(df)
            rendered = mime.call_args.args[0]
        response = rendered._search(
            SearchTableArgs(page_size=1, page_number=0)
        )
        assert json.loads(response.data)[0][display_column] == "0.83"

        explicit = table(df, format_mapping={display_column: "{:.4f}"})
        response = explicit._search(
            SearchTableArgs(page_size=1, page_number=0)
        )
        assert json.loads(response.data)[0][display_column] == "0.8332"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_pandas_formatters_with_no_max_rows() -> None:
    register_formatters()

    import pandas as pd

    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_columns", None)
    pd.set_option("display.show_dimensions", "truncate")

    df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})

    # dataframe
    formatter = get_formatter(df, include_opinionated=False)
    assert formatter
    mime, content = formatter(df)
    assert mime == "text/html"
    assert content.startswith("<table")

    # series
    formatter = get_formatter(df.dtypes, include_opinionated=False)
    assert formatter
    mime, content = formatter(df.dtypes)
    assert mime == "text/html"
    assert content.startswith("<table")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_pandas_formatters_with_max_rows() -> None:
    register_formatters()

    import pandas as pd

    pd.set_option("display.max_rows", 2)
    pd.set_option("display.max_columns", 2)
    pd.set_option("display.show_dimensions", "truncate")

    df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})

    # dataframe
    formatter = get_formatter(df, include_opinionated=False)
    assert formatter
    mime, content = formatter(df)
    assert mime == "text/html"
    assert content.startswith("<table")

    # series
    formatter = get_formatter(df.dtypes, include_opinionated=False)
    assert formatter
    mime, content = formatter(df.dtypes)
    assert mime == "text/html"
    assert content.startswith("<table")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_pandas_formatters_with_truncate() -> None:
    register_formatters()

    import pandas as pd

    df = pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]})

    for setting in (True, False, "truncate"):
        pd.set_option("display.show_dimensions", setting)
        # dataframe
        formatter = get_formatter(df, include_opinionated=False)
        assert formatter
        mime, content = formatter(df)
        assert mime == "text/html"
        assert content.startswith("<table")

        # series
        formatter = get_formatter(df.dtypes, include_opinionated=False)
        assert formatter
        mime, content = formatter(df.dtypes)
        assert mime == "text/html"
        assert content.startswith("<table")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_pandas_series_name_conflict_opinionated() -> None:
    """Test that Series with same name as index works with opinionated formatter."""
    register_formatters()

    import pandas as pd

    # Create a Series with the same name as its index (GitHub issue #6385)
    series = pd.Series(
        data=[1, 2, 3], name="x", index=pd.Index([1, 2, 3], name="x")
    )

    # This should not raise "ValueError: cannot insert x, already exists"
    formatter = get_formatter(series, include_opinionated=True)
    assert formatter
    mime, content = formatter(series)
    # The key test is that it doesn't raise an exception
    # The mime type might be either application/json or text/html depending on the formatter
    assert mime in ("application/json", "text/html")
    # Should successfully format without errors
    assert content is not None
    assert len(content) > 0
