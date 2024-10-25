from __future__ import annotations

from typing import TYPE_CHECKING, Any

import narwhals.stable.v1 as nw
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.narwhals_utils import (
    assert_narwhals_dataframe,
    assert_narwhals_series,
    can_narwhalify,
    empty_df,
)
from tests._data.mocks import create_dataframes

HAS_DEPS = DependencyManager.polars.has()

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"a": [1, 2, 3], "b": ["x", "y", "z"]}, exclude=["ibis", "duckdb"]
    ),
)
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_empty_df(df: IntoDataFrame) -> None:
    empty: Any = empty_df(df)
    assert len(empty) == 0
    assert len(empty.columns) == 2


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_assert_narwhals_dataframe():
    import polars as pl

    df = nw.from_native(pl.DataFrame({"a": [1, 2, 3]}))
    assert_narwhals_dataframe(df)  # Should not raise

    with pytest.raises(ValueError, match="Unsupported dataframe type"):
        assert_narwhals_dataframe([])


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_assert_narwhals_series():
    import polars as pl

    series = nw.from_native(pl.Series("a", [1, 2, 3]), series_only=True)
    assert_narwhals_series(series)  # Should not raise

    with pytest.raises(ValueError, match="Unsupported series type"):
        assert_narwhals_series(pl.Series("a", [1, 2, 3]))


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_can_narwhalify():
    import polars as pl

    assert can_narwhalify([1, 2, 3]) is False
    assert can_narwhalify({"a": 1, "b": 2}) is False
    assert can_narwhalify(pl.DataFrame({"a": [1, 2, 3]})) is True
