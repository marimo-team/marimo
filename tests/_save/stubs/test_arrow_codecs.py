# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import warnings

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._save.stubs.lazy_stub import BLOB_DESERIALIZERS, BLOB_SERIALIZERS

HAS_PANDAS_ARROW = (
    DependencyManager.pandas.has() and DependencyManager.pyarrow.has()
)


def _has_feather_deprecation_warning(
    caught: list[warnings.WarningMessage],
) -> bool:
    return any(
        issubclass(w.category, FutureWarning)
        and "write_feather" in str(w.message)
        for w in caught
    )


@pytest.mark.skipif(not HAS_PANDAS_ARROW, reason="pandas and pyarrow required")
def test_pandas_dataframe_arrow_round_trip_without_feather_warning() -> None:
    import pandas as pd

    df = pd.DataFrame({"x": [1, 2], "y": [3.0, 4.0]})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data = BLOB_SERIALIZERS["arrow"](df)
    assert not _has_feather_deprecation_warning(caught)

    restored = BLOB_DESERIALIZERS[".arrow"](data, "pandas.DataFrame")
    pd.testing.assert_frame_equal(restored, df)


@pytest.mark.skipif(not HAS_PANDAS_ARROW, reason="pandas and pyarrow required")
def test_pandas_series_arrow_round_trip_without_feather_warning() -> None:
    import pandas as pd

    series = pd.Series([10, 20, 30], name="vals")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data = BLOB_SERIALIZERS["arrow"](series)
    assert not _has_feather_deprecation_warning(caught)

    restored = BLOB_DESERIALIZERS[".arrow"](data, "pandas.Series")
    assert isinstance(restored, pd.Series)
    pd.testing.assert_series_equal(restored, series)
