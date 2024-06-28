from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import Mock

import pytest

from marimo._data.series import (
    get_category_series_info,
    get_date_series_info,
    get_number_series_info,
)
from marimo._dependencies.dependencies import DependencyManager

HAS_DEPS = (
    DependencyManager.has_pandas()
    and DependencyManager.has_numpy()
    and DependencyManager.has_polars()
)

if HAS_DEPS:
    import pandas as pd
    import polars as pl
else:
    pd = Mock()
    pl = Mock()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    [
        pd.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]}),
        pl.DataFrame({"A": [1, 2, 3], "B": ["a", "a", "a"]}),
    ],
)
def test_number_series(
    df: Any,
) -> None:
    response = get_number_series_info(df["A"])

    assert response.min == 1
    assert response.max == 3
    assert response.label == "A"

    with pytest.raises(ValueError):
        response = get_number_series_info(df["B"])


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_get_with_no_name() -> None:
    series = pd.Series([1, 2, 3])
    series.name = None
    assert get_number_series_info(series).label == ""


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    [
        pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "b"]}),
        pl.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "b"]}),
    ],
)
def test_categorical_series(df: Any) -> None:
    response = get_category_series_info(df["B"])

    assert response.categories == ["a", "b"]
    assert response.label == "B"

    response = get_category_series_info(df["A"])
    assert response.categories == [1, 2, 3]
    assert response.label == "A"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    [
        pd.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "b"],
                "C": [
                    datetime(2024, 1, 1),
                    datetime(2024, 1, 2),
                    datetime(2024, 1, 3),
                ],
            }
        ),
        pl.DataFrame(
            {
                "A": [1, 2, 3],
                "B": ["a", "b", "b"],
                "C": [
                    datetime(2024, 1, 1),
                    datetime(2024, 1, 2),
                    datetime(2024, 1, 3),
                ],
            }
        ),
    ],
)
def test_date_series(df: Any) -> None:
    response = get_date_series_info(df["C"])

    assert response.min == "2024-01-01"
    assert response.max == "2024-01-03"
    assert response.label == "C"

    with pytest.raises(ValueError):
        response = get_date_series_info(df["B"])
    with pytest.raises(ValueError):
        response = get_date_series_info(df["A"])
