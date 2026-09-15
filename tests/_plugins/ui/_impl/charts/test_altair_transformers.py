from __future__ import annotations

import base64
import datetime
import json
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.charts.altair_transformer import (
    _data_to_csv_string,
    _data_to_json_string,
    _to_marimo_arrow,
    _to_marimo_csv,
    _to_marimo_inline_csv,
    _to_marimo_json,
    register_transformers,
    sanitize_nan_infs,
)
from tests._data.mocks import DFType, create_dataframes

HAS_DEPS = DependencyManager.pandas.has() and DependencyManager.altair.has()

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", "b", "c"]},
    ),
)
def test_to_marimo_json(df: IntoDataFrame):
    result = _to_marimo_json(df)

    assert isinstance(result, dict)
    assert "url" in result
    assert "format" in result
    assert result["format"] == {"type": "json"}


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", "b", "c"]},
    ),
)
def test_to_marimo_csv(df: IntoDataFrame):
    result = _to_marimo_csv(df)

    assert isinstance(result, dict)
    assert "url" in result
    assert "format" in result
    assert result["format"] == {"type": "csv"}


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", "b", "c"]},
    ),
)
def test_to_marimo_inline_csv(df: IntoDataFrame):
    result = _to_marimo_inline_csv(df)

    assert isinstance(result, dict)
    assert "url" in result
    assert result["url"].startswith("data:text/csv;base64,")
    assert "format" in result
    assert result["format"] == {"type": "csv"}


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", "b", "c"]},
    ),
)
def test_data_to_json_string(df: IntoDataFrame):
    result = _data_to_json_string(df)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert len(parsed) == 3
    assert all(set(item.keys()) == {"A", "B"} for item in parsed)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    # We skip pyarrow because it's csv is formatted differently
    create_dataframes({"A": [1, 2, 3], "B": ["a", "b", "c"]}),
)
def test_data_to_csv_string(df: IntoDataFrame):
    result = _data_to_csv_string(df)

    assert isinstance(result, str)
    lines = result.strip().split("\n")
    assert len(lines) == 4  # header + 3 data rows
    assert lines[0].startswith('"A","B"') or lines[0].startswith("A,B")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes({}, exclude=["ibis", "duckdb"]),
)
def test_to_marimo_json_empty_dataframe(df: IntoDataFrame):
    result = _to_marimo_json(df)

    assert isinstance(result, dict)
    assert "url" in result
    assert "format" in result
    assert result["format"] == {"type": "json"}
    assert result["url"].startswith("data:application/json;base64,")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 1, 3], "B": ["a", None, "c"], "C": [True, False, None]},
        exclude=["duckdb"],
    ),
)
def test_to_marimo_csv_with_missing_values(df: IntoDataFrame):
    result = _to_marimo_csv(df)

    assert isinstance(result, dict)
    assert "url" in result
    assert "format" in result
    assert result["format"] == {"type": "csv"}
    assert result["url"].startswith("data:text/csv;base64,")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": range(10000), "B": [f"value_{i}" for i in range(10000)]},
    ),
)
def test_to_marimo_inline_csv_large_dataset(df: IntoDataFrame):
    result = _to_marimo_inline_csv(df)

    assert isinstance(result, dict)
    assert "url" in result
    assert result["url"].startswith("data:text/csv;base64,")
    assert "format" in result
    assert result["format"] == {"type": "csv"}

    # Verify the content of the inline CSV
    base64_data = result["url"].split(",")[1]
    decoded_data = base64.b64decode(base64_data).decode("utf-8")
    assert decoded_data.startswith(('"A","B"', "A,B"))
    lines = decoded_data.strip().split("\n")
    assert len(lines) == 10001  # header + 10000 data rows


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    # We skip pyarrow because it's json is missing new lines
    create_dataframes({"A": [1, 2, 3], "B": ['a"b', "c,d", "e\nf"]}),
)
def test_data_to_json_string_with_special_characters(
    df: IntoDataFrame,
):
    result = _data_to_json_string(df)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert len(parsed) == 3
    assert parsed[0]["B"] == 'a"b'
    assert parsed[1]["B"] == "c,d"
    assert parsed[2]["B"] == "e\nf" or parsed[2]["B"] == "ef"


@pytest.mark.skipif(
    not HAS_DEPS or not DependencyManager.pyarrow.has(),
    reason="optional dependencies not installed",
)
@pytest.mark.parametrize("error", [ValueError, NotImplementedError])
def test_to_marimo_arrow_with_duration_export_failure(error: type[Exception]):
    import narwhals.stable.v2 as nw
    import pandas as pd

    df = pd.DataFrame({"a.b": [1.0, 2.0, 3.0], "n": [1, 2, 3]})
    df["d"] = pd.to_timedelta([1, 2, 3], unit="D")

    with (
        patch(
            "marimo._plugins.ui._impl.tables.pandas_table._dataframe_to_arrow_ipc",
            side_effect=error("Arrow export failed"),
        ),
        patch(
            "marimo._plugins.ui._impl.charts.altair_transformer.mo_data.csv"
        ) as export_csv,
    ):
        export_csv.return_value.url = "test.csv"
        result = _to_marimo_arrow(nw.from_native(df))

    assert result == {"url": "test.csv", "format": {"type": "csv"}}
    export_csv.assert_called_once_with(
        b"a.b,n,d\n1.0,1,1 days\n2.0,2,2 days\n3.0,3,3 days\n"
    )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "int": [1, 2, 3],
            "float": [1.1, 2.2, 3.3],
            "bool": [True, False, True],
            "datetime": [
                datetime.datetime(2023, 1, 1, 1),
                datetime.datetime(2023, 1, 2, 1),
                datetime.datetime(2023, 1, 3, 1),
            ],
            "category": ["a", "b", "c"],
        },
        exclude=["ibis"],
    ),
)
def test_data_to_csv_string_with_different_dtypes(df: IntoDataFrame):
    result = _data_to_csv_string(df)
    assert isinstance(result, str)


@patch("altair.data_transformers")
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_register_transformers(mock_data_transformers: MagicMock):
    register_transformers()

    assert mock_data_transformers.register.call_count == 5
    mock_data_transformers.register.assert_any_call("marimo", _to_marimo_csv)
    mock_data_transformers.register.assert_any_call(
        "marimo_inline_csv", _to_marimo_inline_csv
    )
    mock_data_transformers.register.assert_any_call(
        "marimo_json", _to_marimo_json
    )
    mock_data_transformers.register.assert_any_call(
        "marimo_csv", _to_marimo_csv
    )
    mock_data_transformers.register.assert_any_call(
        "marimo_arrow", _to_marimo_arrow
    )


SUPPORTS_ARROW_IPC: list[DFType] = ["pandas", "polars", "lazy-polars"]


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", "b", "c"]}, include=SUPPORTS_ARROW_IPC
    ),
)
def test_to_marimo_arrow(df: IntoDataFrame):
    result = _to_marimo_arrow(df)

    assert isinstance(result, dict)
    assert "url" in result
    assert "format" in result
    print(type(df))
    assert result["format"] == {"type": "arrow"}


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", "b", "c"]}, exclude=SUPPORTS_ARROW_IPC
    ),
)
def test_to_marimo_arrow_fallback(df: IntoDataFrame):
    result = _to_marimo_arrow(df)

    # Should fallback to CSV format
    assert isinstance(result, dict)
    assert "url" in result
    assert "format" in result
    assert result["format"] == {"type": "csv"}


@pytest.mark.skipif(
    not HAS_DEPS or not DependencyManager.pyarrow.has(),
    reason="optional dependencies not installed",
)
def test_to_marimo_arrow_with_duration():
    import narwhals.stable.v2 as nw
    import pandas as pd
    import pyarrow as pa

    df = pd.DataFrame({"a.b": [1.0, 2.0, 3.0], "n": [1, 2, 3]})
    df["d"] = pd.to_timedelta([1, 2, 3], unit="D")

    with patch(
        "marimo._plugins.ui._impl.charts.altair_transformer.mo_data.arrow"
    ) as export_arrow:
        result = _to_marimo_arrow(nw.from_native(df))

    assert result["format"] == {"type": "arrow"}
    export_arrow.assert_called_once()
    exported = pa.ipc.open_file(export_arrow.call_args.args[0]).read_all()
    pd.testing.assert_frame_equal(exported.to_pandas(), df)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_marimo_arrow_with_duration_without_pyarrow():
    import narwhals.stable.v2 as nw
    import pandas as pd

    df = pd.DataFrame({"a.b": [1.0, 2.0, 3.0], "n": [1, 2, 3]})
    df["d"] = pd.to_timedelta([1, 2, 3], unit="D")
    wrapped = nw.from_native(df)

    with (
        patch.dict(sys.modules, {"pyarrow": None}),
        patch(
            "marimo._plugins.ui._impl.charts.altair_transformer.mo_data.csv"
        ) as export_csv,
    ):
        export_csv.return_value.url = "test.csv"
        result = _to_marimo_arrow(wrapped)

    assert result == {"url": "test.csv", "format": {"type": "csv"}}
    export_csv.assert_called_once_with(
        b"a.b,n,d\n1.0,1,1 days\n2.0,2,2 days\n3.0,3,3 days\n"
    )


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_marimo_arrow_csv_fallback_preserves_infinities():
    import narwhals.stable.v2 as nw
    import pandas as pd

    df = nw.from_native(
        pd.DataFrame(
            {
                "a.b": [1.0, float("inf"), float("-inf"), None],
                "n": [1, 2, 3, 4],
            }
        )
    )
    with (
        patch.dict(sys.modules, {"pyarrow": None}),
        patch(
            "marimo._plugins.ui._impl.charts.altair_transformer.mo_data.csv"
        ) as export_csv,
    ):
        export_csv.return_value.url = "test.csv"
        result = _to_marimo_arrow(df)

    assert result == {"url": "test.csv", "format": {"type": "csv"}}
    export_csv.assert_called_once_with(b"a.b,n\n1.0,1\ninf,2\n-inf,3\n,4\n")


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "int": [1, 2, 3],
            "float": [1.1, 2.2, 3.3],
            "bool": [True, False, True],
            "datetime": [
                datetime.datetime(2023, 1, 1, 1),
                datetime.datetime(2023, 1, 2, 1),
                datetime.datetime(2023, 1, 3, 1),
            ],
            "category": ["a", "b", "c"],
        },
        include=SUPPORTS_ARROW_IPC,
    ),
)
def test_to_marimo_arrow_different_dtypes(df: IntoDataFrame):
    result = _to_marimo_arrow(df)

    assert isinstance(result, dict)
    assert "url" in result
    assert "format" in result
    assert result["format"] == {"type": "arrow"}


@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {
            "A": [1.0, float("nan"), 3.0],
            "B": [float("inf"), 2.0, float("-inf")],
        },
    ),
)
def test_sanitize_nan_infs_preserves_df_type(df: IntoDataFrame):
    """Test that sanitize_nan_infs preserves eager dataframe type."""
    original_type = type(df)

    result = sanitize_nan_infs(df)

    assert type(result) is original_type
