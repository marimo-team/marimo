from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._output.formatters.formatters import register_formatters
from marimo._output.formatting import (
    get_formatter,
)

HAS_DEPS = DependencyManager.pandas.has()


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
