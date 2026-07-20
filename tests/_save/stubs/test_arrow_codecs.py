# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import warnings

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._save.stubs.lazy_stub import BLOB_DESERIALIZERS, BLOB_SERIALIZERS

HAS_PANDAS_ARROW = (
    DependencyManager.pandas.has() and DependencyManager.pyarrow.has()
)


@pytest.mark.skipif(not HAS_PANDAS_ARROW, reason="pandas and pyarrow required")
def test_pandas_dataframe_arrow_round_trip_without_feather_warning() -> None:
    import pandas as pd

    df = pd.DataFrame({"x": [1, 2], "y": [3.0, 4.0]})
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data = BLOB_SERIALIZERS["arrow"](df)
    assert not any(issubclass(w.category, FutureWarning) for w in caught)

    restored = BLOB_DESERIALIZERS[".arrow"](data, "pandas.DataFrame")
    pd.testing.assert_frame_equal(restored, df)


@pytest.mark.skipif(not HAS_PANDAS_ARROW, reason="pandas and pyarrow required")
def test_pandas_series_arrow_round_trip_without_feather_warning() -> None:
    import pandas as pd

    series = pd.Series([10, 20, 30], name="vals")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        data = BLOB_SERIALIZERS["arrow"](series)
    assert not any(issubclass(w.category, FutureWarning) for w in caught)

    restored = BLOB_DESERIALIZERS[".arrow"](data, "pandas.Series")
    assert isinstance(restored, pd.Series)
    pd.testing.assert_series_equal(restored, series)
