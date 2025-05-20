from __future__ import annotations

import base64
import datetime
import json
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
)
from tests._data.mocks import create_dataframes

HAS_DEPS = DependencyManager.pandas.has() and DependencyManager.altair.has()

if TYPE_CHECKING:
    from narwhals.typing import IntoDataFrame


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    "df",
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", "b", "c"]}, exclude=["duckdb"]
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
        {"A": [1, 2, 3], "B": ["a", "b", "c"]}, exclude=["duckdb"]
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
        {"A": [1, 2, 3], "B": ["a", "b", "c"]}, exclude=["duckdb"]
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
        {"A": [1, 2, 3], "B": ["a", "b", "c"]}, exclude=["duckdb"]
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
    create_dataframes(
        {"A": [1, 2, 3], "B": ["a", "b", "c"]}, exclude=["pyarrow", "duckdb"]
    ),
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
        exclude=["pyarrow", "duckdb"],
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
    assert decoded_data.startswith('"A","B"') or decoded_data.startswith("A,B")
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


SUPPORTS_ARROW_IPC = ["pandas", "polars", "lazy-polars"]


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
