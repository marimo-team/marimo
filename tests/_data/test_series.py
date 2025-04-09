from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from marimo._data.series import (
    get_category_series_info,
    get_date_series_info,
    get_datetime_series_info,
    get_number_series_info,
)
from marimo._dependencies.dependencies import DependencyManager
from tests._data.mocks import NON_EAGER_LIBS, create_dataframes, create_series

HAS_DEPS = (
    DependencyManager.pandas.has()
    and DependencyManager.numpy.has()
    and DependencyManager.polars.has()
)

# We exclude ibis because it neither eager_or_interchange_only


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, None, 3], "B": ["a", "a", "a"]},
        exclude=NON_EAGER_LIBS,
    ),
)
def test_number_series(
    df: Any,
) -> None:
    response = get_number_series_info(df["A"])

    # None/null values should be filtered out
    assert response.min == 1
    assert response.max == 3
    assert response.label == "A" or is_pyarrow_type(df)

    with pytest.raises(ValueError):
        response = get_number_series_info(df["B"])


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "series",
    create_series([1, 2, 3]),
)
def test_get_with_no_name(series: Any) -> None:
    assert get_number_series_info(series).label == ""


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", None, "b"]},
        exclude=NON_EAGER_LIBS,
    ),
)
def test_categorical_series(df: Any) -> None:
    response = get_category_series_info(df["B"])

    # None/null values should be filtered out
    assert response.categories == ["a", "b"]
    assert response.label == "B" or is_pyarrow_type(df)

    response = get_category_series_info(df["A"])
    assert response.categories == [1, 2, 3]
    assert response.label == "A" or is_pyarrow_type(df)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3],
            "B": ["a", "b", "b"],
            "C": [
                datetime(2024, 1, 1),
                None,
                datetime(2024, 1, 3),
            ],
        },
        exclude=NON_EAGER_LIBS,
    ),
)
def test_date_series(df: Any) -> None:
    response = get_date_series_info(df["C"])

    # None/null values should be filtered out
    assert response.min == "2024-01-01"
    assert response.max == "2024-01-03"
    assert response.label == "C" or is_pyarrow_type(df)

    with pytest.raises(ValueError):
        response = get_date_series_info(df["B"])
    with pytest.raises(ValueError):
        response = get_date_series_info(df["A"])


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3],
            "B": ["a", "b", "b"],
            "C": [
                datetime(2024, 1, 1, 12, 0),
                datetime(2024, 1, 2, 13, 30),
                None,
            ],
        },
        exclude=NON_EAGER_LIBS,
    ),
)
def test_datetime_series(df: Any) -> None:
    response = get_datetime_series_info(df["C"])

    # None/null values should be filtered out
    assert response.min == "2024-01-01T12:00:00"
    assert response.max == "2024-01-02T13:30:00"
    assert response.label == "C" or is_pyarrow_type(df)

    with pytest.raises(ValueError):
        response = get_datetime_series_info(df["B"])
    with pytest.raises(ValueError):
        response = get_datetime_series_info(df["A"])


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1, 2, 3],
            "B": ["a", "b", "b"],
            "C": [
                datetime(2024, 1, 1, 12, 0),
                datetime(2024, 1, 2, 13, 30),
                datetime(2024, 1, 3, 15, 45),
            ],
        },
        include=NON_EAGER_LIBS,
    ),
)
def test_ibis_fails(df: Any) -> None:
    with pytest.raises((TypeError, ValueError)):
        get_number_series_info(df["A"])
    with pytest.raises((TypeError, ValueError)):
        get_category_series_info(df["B"])
    with pytest.raises((TypeError, ValueError)):
        get_date_series_info(df["C"])
    with pytest.raises((TypeError, ValueError)):
        get_datetime_series_info(df["C"])


# Pyarrow columns don't have a name
def is_pyarrow_type(response: Any) -> bool:
    try:
        import pyarrow as pa

        return isinstance(response, pa.Table)
    except ImportError:
        return False
