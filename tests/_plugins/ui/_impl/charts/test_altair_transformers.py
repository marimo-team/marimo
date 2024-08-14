from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.charts.altair_transformer import (
    _data_to_csv_string,
    _data_to_json_string,
    _to_marimo_csv,
    _to_marimo_inline_csv,
    _to_marimo_json,
    register_transformers,
)

if TYPE_CHECKING:
    import pandas as pd

HAS_DEPS = (
    DependencyManager.pandas.has()
    and DependencyManager.altair.has()
    # altair produces different output on windows
    and sys.platform == "win32"
)


def get_data() -> pd.DataFrame:
    import pandas as pd

    return pd.DataFrame({"A": [1, 2, 3], "B": ["a", "b", "c"]})


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_marimo_json():
    sample_data = get_data()
    result = _to_marimo_json(sample_data)

    assert isinstance(result, dict)
    assert "url" in result
    assert "format" in result
    assert result["format"] == {"type": "json"}


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_marimo_csv():
    sample_data = get_data()
    result = _to_marimo_csv(sample_data)

    assert isinstance(result, dict)
    assert "url" in result
    assert "format" in result
    assert result["format"] == {"type": "csv"}


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_to_marimo_inline_csv():
    sample_data = get_data()
    result = _to_marimo_inline_csv(sample_data)

    assert isinstance(result, dict)
    assert "url" in result
    assert result["url"].startswith("data:text/csv;base64,")
    assert "format" in result
    assert result["format"] == {"type": "csv"}


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_data_to_json_string():
    sample_data = get_data()
    result = _data_to_json_string(sample_data)

    assert isinstance(result, str)
    parsed = json.loads(result)
    assert len(parsed) == 3
    assert all(set(item.keys()) == {"A", "B"} for item in parsed)


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_data_to_csv_string():
    sample_data = get_data()
    result = _data_to_csv_string(sample_data)

    assert isinstance(result, str)
    lines = result.strip().split("\n")
    assert len(lines) == 4  # header + 3 data rows
    assert lines[0] == "A,B"


@patch("altair.data_transformers")
@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_register_transformers(mock_data_transformers: MagicMock):
    register_transformers()

    assert mock_data_transformers.register.call_count == 4
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
