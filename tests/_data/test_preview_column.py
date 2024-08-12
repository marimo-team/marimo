from __future__ import annotations

import sys

import pytest

from marimo._data.preview_column import get_column_preview
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.charts.altair_transformer import (
    register_transformers,
)
from marimo._runtime.requests import PreviewDatasetColumnRequest
from tests.mocks import snapshotter

HAS_DEPS = DependencyManager.pandas.has() and DependencyManager.altair.has()

snapshot = snapshotter(__file__)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Windows encodes base64 differently",
)
def test_get_column_preview() -> None:
    import pandas as pd

    register_transformers()

    df = pd.DataFrame(
        {
            "A": [1, 2, 3],
            "B": ["a", "a", "a"],
            "date_col": [
                pd.Timestamp("2021-01-01"),
                pd.Timestamp("2021-01-02"),
                pd.Timestamp("2021-01-03"),
            ],
        }
    )
    result = get_column_preview(
        df,
        request=PreviewDatasetColumnRequest(
            source="source",
            table_name="table",
            column_name="A",
            source_type="local",
        ),
    )

    assert result is not None
    assert result.chart_code is not None
    assert result.chart_spec is not None
    assert result.summary is not None
    assert result.error is None

    snapshot("column_preview_chart_code.txt", result.chart_code)
    snapshot("column_preview_chart_spec.txt", result.chart_spec)

    result = get_column_preview(
        df,
        request=PreviewDatasetColumnRequest(
            source="source",
            table_name="table",
            column_name="date_col",
            source_type="local",
        ),
    )

    assert result is not None
    assert result.chart_code is not None
    assert result.chart_spec is not None
    assert result.summary is not None
    assert result.error is None

    snapshot("column_preview_date_chart_code.txt", result.chart_code)
    snapshot("column_preview_date_chart_spec.txt", result.chart_spec)
