from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._data.preview_column import (
    get_column_preview_for_dataframe,
    get_column_preview_for_duckdb,
)
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.charts.altair_transformer import (
    register_transformers,
)
from marimo._runtime.requests import PreviewDatasetColumnRequest
from marimo._utils.platform import is_windows
from tests.mocks import snapshotter

if TYPE_CHECKING:
    from collections.abc import Generator

HAS_DF_DEPS = DependencyManager.pandas.has() and DependencyManager.altair.has()
HAS_SQL_DEPS = (
    DependencyManager.duckdb.has() and DependencyManager.altair.has()
)

snapshot = snapshotter(__file__)


# Run cleanup after all tests are done
@pytest.fixture(scope="module", autouse=True)
def cleanup() -> Generator[None, None, None]:
    import duckdb

    yield
    duckdb.execute("""
        DROP TABLE IF EXISTS tbl;
        DROP TABLE IF EXISTS date_tbl;
        DROP TABLE IF EXISTS datetime_tbl;
        DROP TABLE IF EXISTS time_tbl;
        DROP TABLE IF EXISTS bool_tbl;
        DROP TABLE IF EXISTS large_tbl;
    """)


@pytest.mark.skipif(
    not HAS_DF_DEPS, reason="optional dependencies not installed"
)
@pytest.mark.skipif(is_windows(), reason="Windows encodes base64 differently")
@pytest.mark.parametrize(
    ("column_name", "snapshot_prefix"),
    [
        ("A", "column_preview_int"),
        ("B", "column_preview_str"),
        ("date_col", "column_preview_date"),
        ("float_col", "column_preview_float"),
        ("bool_col", "column_preview_bool"),
        ("category_col", "column_preview_categorical"),
    ],
)
def test_get_column_preview_for_dataframe(
    column_name: str, snapshot_prefix: str
) -> None:
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
            "float_col": [1.1, 2.2, 3.3],
            "bool_col": [True, False, True],
            "category_col": pd.Categorical(["cat1", "cat2", "cat1"]),
        }
    )

    # Patch DependencyManager to simulate vegafusion not being available
    with patch("marimo._data.preview_column.DependencyManager") as mock_dm:
        # Keep altair available but make vegafusion unavailable
        mock_dm.altair.has.return_value = True
        mock_dm.vegafusion.has.return_value = False
        mock_dm.vl_convert_python.has.return_value = True

        result = get_column_preview_for_dataframe(
            df,
            request=PreviewDatasetColumnRequest(
                source="source",
                table_name="table",
                column_name=column_name,
                source_type="local",
            ),
        )
        assert result is not None
        assert result.chart_code is not None
        assert result.chart_spec is not None
        assert result.stats is not None
        assert result.error is None

        snapshot(f"{snapshot_prefix}_chart_code.txt", result.chart_code)
        # Skip date_col because of timezone
        if column_name != "date_col":
            snapshot(f"{snapshot_prefix}_chart_spec.txt", result.chart_spec)

        # Verify vegafusion was checked
        mock_dm.vegafusion.has.assert_called_once()

    result_with_vegafusion = get_column_preview_for_dataframe(
        df,
        request=PreviewDatasetColumnRequest(
            source="source",
            table_name="table",
            column_name=column_name,
            source_type="local",
        ),
    )

    assert result_with_vegafusion is not None
    assert result_with_vegafusion.chart_code is not None
    assert result_with_vegafusion.chart_spec is not None
    assert result_with_vegafusion.stats is not None
    assert result_with_vegafusion.error is None

    # Skip date_col because of timezone
    if column_name != "date_col":
        snapshot(
            f"{snapshot_prefix}_chart_spec_with_vegafusion.txt",
            result_with_vegafusion.chart_spec,
        )
    assert result_with_vegafusion.chart_code == result.chart_code
    assert result_with_vegafusion.chart_spec != result.chart_spec


@pytest.mark.skipif(
    not HAS_SQL_DEPS, reason="optional dependencies not installed"
)
@pytest.mark.skipif(is_windows(), reason="Windows encodes base64 differently")
def test_get_column_preview_for_duckdb() -> None:
    import duckdb

    # Create a table with a deterministic pattern
    duckdb.execute("""
        CREATE OR REPLACE TABLE tbl AS
        SELECT
            range AS id,
            CAST(range % 2 AS INTEGER) AS outcome
        FROM range(100)
    """)

    # Test preview for the 'outcome' column (alternating 0 and 1)
    result = get_column_preview_for_duckdb(
        fully_qualified_table_name="tbl",
        column_name="outcome",
    )
    assert result is not None
    assert result.stats is not None
    assert result.error is None

    # Check if summary contains expected statistics for the alternating pattern
    assert result.stats.total == 100
    assert result.stats.unique == 2
    assert result.stats.mean == 0.5  # Exactly 0.5 due to alternating pattern
    assert result.chart_spec is not None

    # Test preview for the 'id' column (for comparison)
    result_id = get_column_preview_for_duckdb(
        fully_qualified_table_name="tbl",
        column_name="id",
    )
    assert result_id is not None
    assert result_id.stats is not None
    assert result_id.error is None
    assert result_id.chart_spec is not None

    # Not implemented yet
    assert result.chart_code is None


@pytest.mark.skipif(
    not HAS_SQL_DEPS, reason="optional dependencies not installed"
)
@pytest.mark.skipif(is_windows(), reason="Windows encodes base64 differently")
def test_get_column_preview_for_duckdb_categorical() -> None:
    import duckdb

    # Test preview for a categorical column
    duckdb.execute("""
        CREATE OR REPLACE TABLE tbl AS
        SELECT
            CASE
                WHEN range % 4 = 0 THEN 'A'
                WHEN range % 4 = 1 THEN 'B'
                WHEN range % 4 = 2 THEN 'C'
                ELSE 'D'
            END AS category
        FROM range(100)
    """)

    result_categorical = get_column_preview_for_duckdb(
        fully_qualified_table_name="tbl",
        column_name="category",
    )
    assert result_categorical is not None
    assert result_categorical.stats is not None
    assert result_categorical.error is None

    # Check if summary contains expected statistics for the categorical pattern
    assert result_categorical.stats.total == 100
    assert result_categorical.stats.unique == 4
    assert result_categorical.stats.nulls == 0
    assert result_categorical.chart_spec is not None

    snapshot(
        "column_preview_duckdb_categorical_chart_spec.txt",
        result_categorical.chart_spec,
    )

    # Not implemented yet
    assert result_categorical.chart_code is None

    # Test works when fully qualified
    assert (
        get_column_preview_for_duckdb(
            fully_qualified_table_name="tbl",
            column_name="category",
        ).stats
        == get_column_preview_for_duckdb(
            fully_qualified_table_name="memory.main.tbl",
            column_name="category",
        ).stats
    )


@pytest.mark.skipif(
    not HAS_SQL_DEPS, reason="optional dependencies not installed"
)
@pytest.mark.skipif(is_windows(), reason="Windows encodes base64 differently")
def test_get_column_preview_for_duckdb_date() -> None:
    import datetime

    import duckdb

    # Test preview for a date column
    duckdb.execute("""
        CREATE OR REPLACE TABLE date_tbl AS
        SELECT DATE '2023-01-01' + INTERVAL (range % 365) DAY AS date_col
        FROM range(100)
    """)

    result_date = get_column_preview_for_duckdb(
        fully_qualified_table_name="date_tbl",
        column_name="date_col",
    )
    assert result_date is not None
    assert result_date.stats is not None
    assert result_date.error is None

    # Check if summary contains expected statistics for the date pattern
    assert result_date.stats.total == 100
    assert result_date.stats.unique == 100
    assert result_date.stats.nulls == 0
    assert result_date.stats.min == datetime.datetime(2023, 1, 1, 0, 0)
    assert result_date.stats.max == datetime.datetime(2023, 4, 10, 0, 0)
    assert result_date.chart_spec is not None

    # No chart_spec snapshot because of date timezone

    # Not implemented yet
    assert result_date.chart_code is None

    # Test works when fully qualified
    assert (
        get_column_preview_for_duckdb(
            fully_qualified_table_name="date_tbl",
            column_name="date_col",
        ).stats
        == get_column_preview_for_duckdb(
            fully_qualified_table_name="memory.main.date_tbl",
            column_name="date_col",
        ).stats
    )


@pytest.mark.skipif(
    not HAS_SQL_DEPS, reason="optional dependencies not installed"
)
@pytest.mark.skipif(is_windows(), reason="Windows encodes base64 differently")
def test_get_column_preview_for_duckdb_datetime() -> None:
    import datetime

    import duckdb

    # Test preview for a datetime column
    duckdb.execute("""
        CREATE OR REPLACE TABLE datetime_tbl AS
        SELECT TIMESTAMP '2023-01-01 00:00:00' +
               INTERVAL (range % 365) DAY +
               INTERVAL (range % 24) HOUR +
               INTERVAL (range % 60) MINUTE AS datetime_col
        FROM range(100)
    """)

    result_datetime = get_column_preview_for_duckdb(
        fully_qualified_table_name="datetime_tbl",
        column_name="datetime_col",
    )
    assert result_datetime is not None
    assert result_datetime.stats is not None
    assert result_datetime.error is None

    # Check if summary contains expected statistics for the datetime pattern
    assert result_datetime.stats.total == 100
    assert result_datetime.stats.unique == 100
    assert result_datetime.stats.nulls == 0
    assert result_datetime.stats.min == datetime.datetime(2023, 1, 1, 0, 0)
    assert result_datetime.stats.max == datetime.datetime(2023, 4, 10, 3, 39)
    assert result_datetime.chart_spec is not None

    # Not implemented yet
    assert result_datetime.chart_code is None

    # No chart_spec snapshot because of date timezone

    # Test works when fully qualified
    assert (
        get_column_preview_for_duckdb(
            fully_qualified_table_name="datetime_tbl",
            column_name="datetime_col",
        ).stats
        == get_column_preview_for_duckdb(
            fully_qualified_table_name="memory.main.datetime_tbl",
            column_name="datetime_col",
        ).stats
    )


@pytest.mark.skipif(
    not HAS_SQL_DEPS, reason="optional dependencies not installed"
)
@pytest.mark.skipif(is_windows(), reason="Windows encodes base64 differently")
def test_get_column_preview_for_duckdb_time() -> None:
    import datetime

    import duckdb

    # Test preview for a time column
    duckdb.execute("""
        CREATE OR REPLACE TABLE time_tbl AS
        SELECT TIME '00:00:00' +
               INTERVAL (range % 24) HOUR +
               INTERVAL (range % 60) MINUTE AS time_col
        FROM range(100)
    """)

    result_time = get_column_preview_for_duckdb(
        fully_qualified_table_name="time_tbl",
        column_name="time_col",
    )
    assert result_time is not None
    assert result_time.stats is not None
    assert result_time.error is None

    # Check if summary contains expected statistics for the time pattern
    assert result_time.stats.total == 100
    assert result_time.stats.unique == 100
    assert result_time.stats.nulls == 0
    assert result_time.stats.min == datetime.time(0, 0)
    assert result_time.stats.max == datetime.time(23, 47)

    # Time is not handled yet
    assert result_time.chart_spec is None

    # Not implemented yet
    assert result_time.chart_code is None


@pytest.mark.skipif(
    not HAS_SQL_DEPS, reason="optional dependencies not installed"
)
@pytest.mark.skipif(is_windows(), reason="Windows encodes base64 differently")
def test_get_column_preview_for_duckdb_bool() -> None:
    import duckdb

    # Test preview for a boolean column
    duckdb.execute("""
        CREATE OR REPLACE TABLE bool_tbl AS
        SELECT range % 2 = 0 AS bool_col
        FROM range(100)
    """)

    result_bool = get_column_preview_for_duckdb(
        fully_qualified_table_name="bool_tbl",
        column_name="bool_col",
    )
    assert result_bool is not None
    assert result_bool.stats is not None
    assert result_bool.error is None

    # Check if summary contains expected statistics for the boolean pattern
    assert result_bool.stats.total == 100
    assert result_bool.stats.unique == 2
    assert result_bool.stats.nulls == 0
    assert result_bool.stats.true == 50
    assert result_bool.stats.false == 50
    assert result_bool.chart_spec is not None

    snapshot(
        "column_preview_duckdb_bool_chart_spec.txt", result_bool.chart_spec
    )

    # Not implemented yet
    assert result_bool.chart_code is None


@pytest.mark.skipif(
    not HAS_SQL_DEPS, reason="optional dependencies not installed"
)
@pytest.mark.skipif(is_windows(), reason="Windows encodes base64 differently")
def test_get_column_preview_for_duckdb_over_limit() -> None:
    import duckdb

    from marimo._data.preview_column import CHART_MAX_ROWS

    # Create a table with more rows than the chart limit
    duckdb.execute(f"""
        CREATE OR REPLACE TABLE large_tbl AS
        SELECT
            range AS id,
            range % 5 AS category
        FROM range({CHART_MAX_ROWS + 100})
    """)

    # Test preview for a column in a table that exceeds the row limit
    result = get_column_preview_for_duckdb(
        fully_qualified_table_name="large_tbl",
        column_name="category",
    )

    assert result is not None
    assert result.stats is not None
    assert result.error is None
    assert result.chart_max_rows_errors is True
    assert result.chart_spec is None

    # Not implemented yet
    assert result.chart_code is None
