from __future__ import annotations

from typing import TYPE_CHECKING, Any

import narwhals.stable.v1 as nw
import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._utils.narwhals_utils import (
    assert_narwhals_dataframe,
    assert_narwhals_series,
    can_narwhalify,
    can_narwhalify_lazyframe,
    dataframe_to_csv,
    empty_df,
    is_narwhals_integer_type,
    is_narwhals_lazyframe,
    is_narwhals_string_type,
    is_narwhals_temporal_type,
    unwrap_narwhals_dataframe,
    unwrap_py_scalar,
    upgrade_narwhals_df,
)
from tests._data.mocks import create_dataframes

HAS_DEPS = DependencyManager.polars.has()

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"a": [1, 2, 3], "b": ["x", "y", "z"]},
    ),
)
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_empty_df(df: IntoDataFrame) -> None:
    empty: Any = empty_df(df)

    # Assert shape is empty
    n_df = upgrade_narwhals_df(nw.from_native(empty))
    if is_narwhals_lazyframe(n_df):
        n_df = n_df.collect()

    assert n_df.shape == (0, 2)


@pytest.mark.parametrize(
    "df",
    create_dataframes({"a": [1, 2, 3]}, exclude=["lazy-polars"]),
)
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_assert_narwhals_dataframe(df: IntoDataFrame) -> None:
    df_wrapped = nw.from_native(df)
    assert_narwhals_dataframe(df_wrapped)  # Should not raise

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


@pytest.mark.parametrize(
    "df", create_dataframes({"a": [1, 2], "b": ["x", "y"]})
)
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_dataframe_to_csv(df: IntoDataFrame) -> None:
    df_wrapped = nw.from_native(df)
    csv = dataframe_to_csv(df_wrapped)
    assert '"a","b"' in csv or "a,b" in csv
    assert '1,"x"' in csv or "1,x" in csv
    assert '2,"y"' in csv or "2,y" in csv


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_narwhals_type_checks():
    assert is_narwhals_integer_type(nw.Int64)
    assert is_narwhals_integer_type(nw.UInt8)
    assert not is_narwhals_integer_type(nw.Float64)

    assert is_narwhals_temporal_type(nw.Datetime)
    assert is_narwhals_temporal_type(nw.Date)
    assert is_narwhals_temporal_type(nw.Duration)
    assert not is_narwhals_temporal_type(nw.Int64)

    assert is_narwhals_string_type(nw.String)
    assert is_narwhals_string_type(nw.Categorical)
    assert not is_narwhals_string_type(nw.Int64)


@pytest.mark.parametrize("df", create_dataframes({"a": [1, 2, 3]}))
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_unwrap_narwhals_dataframe(df: IntoDataFrame) -> None:
    df_wrapped = nw.from_native(df)
    unwrapped = unwrap_narwhals_dataframe(df_wrapped)
    assert type(unwrapped) is type(df)

    # Non-narwhals df should be returned as-is
    assert unwrap_narwhals_dataframe(df) is df


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_unwrap_py_scalar():
    import polars as pl

    # Test basic scalar conversion
    series = nw.from_native(pl.Series("a", [1]), series_only=True)
    assert unwrap_py_scalar(series[0]) == 1

    # Test non-scalar values are returned as-is
    complex_obj = {"a": 1}
    assert unwrap_py_scalar(complex_obj) == complex_obj


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_can_narwhalify_lazyframe():
    import duckdb
    import polars as pl

    # Test with a LazyFrame
    lazy_df = pl.DataFrame({"a": [1, 2, 3]}).lazy()
    assert can_narwhalify_lazyframe(lazy_df) is True

    # Test with a regular DataFrame
    df = pl.DataFrame({"a": [1, 2, 3]})
    assert can_narwhalify_lazyframe(df) is False

    # Test with non-polars objects
    assert can_narwhalify_lazyframe({"a": [1, 2, 3]}) is False
    assert can_narwhalify_lazyframe([1, 2, 3]) is False
    assert can_narwhalify_lazyframe(None) is False

    # Test with duckdb relation
    con = duckdb.connect(":memory:")
    rel = con.sql("SELECT 1")
    assert can_narwhalify_lazyframe(rel) is True
