# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import List

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.utils.dataframe import get_row_headers

HAS_DEPS = DependencyManager.has_pandas()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_row_headers() -> None:
    import pandas as pd

    expected: List[tuple[str, List[str]]]

    # Test with pandas DataFrame
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    df.index.name = "Index"
    assert get_row_headers(df) == []

    # Test with non-DataFrame input
    assert get_row_headers([1, 2, 3]) == []

    # Test with MultiIndex
    arrays = [
        ["foo", "bar", "baz"],
        ["one", "two", "three"],
    ]
    df_multi = pd.DataFrame({"A": range(3)}, index=arrays)
    expected = [
        ("", ["foo", "bar", "baz"]),
        ("", ["one", "two", "three"]),
    ]
    assert get_row_headers(df_multi) == expected

    # Test with RangeIndex
    df_range = pd.DataFrame({"A": range(3)})
    assert get_row_headers(df_range) == []

    # Test with categorical Index
    df_cat = pd.DataFrame({"A": range(3)})
    df_cat.index = pd.CategoricalIndex(["a", "b", "c"])
    expected = [("", ["a", "b", "c"])]
    assert get_row_headers(df_cat) == expected

    # Test with named categorical Index
    df_cat = pd.DataFrame({"A": range(3)})
    df_cat.index = pd.CategoricalIndex(["a", "b", "c"], name="Colors")
    expected = [("Colors", ["a", "b", "c"])]
    assert get_row_headers(df_cat) == expected
