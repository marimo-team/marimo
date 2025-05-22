# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any
from unittest.mock import Mock

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl import data_explorer
from marimo._utils.data_uri import from_data_uri
from marimo._utils.platform import is_windows
from tests._data.mocks import create_dataframes

HAS_DEPS = DependencyManager.pandas.has()


if HAS_DEPS:
    import pandas as pd
else:
    pd = Mock()


@pytest.mark.parametrize(
    "df",
    create_dataframes({"A": [1, 2, 3], "B": [4, 5, 6]}, exclude=["duckdb"]),
)
def test_data_explorer(df: Any) -> None:
    explorer = data_explorer.data_explorer(df)
    assert explorer


@pytest.mark.skipif(
    not HAS_DEPS or is_windows(),
    reason="optional dependencies not installed or windows",
)
def test_data_explorer_index() -> None:
    # With index
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}, index=["a", "b", "c"])
    explorer = data_explorer.data_explorer(df)
    data = explorer._component_args["data"]
    assert from_data_uri(data)[1] == b"A,B\n1,4\n2,5\n3,6\n"

    # Reset index beforehand
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]}, index=["a", "b", "c"])
    explorer = data_explorer.data_explorer(df.reset_index(drop=False))
    data = explorer._component_args["data"]
    assert from_data_uri(data)[1] == b"index,A,B\na,1,4\nb,2,5\nc,3,6\n"

    # No index
    df = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    explorer = data_explorer.data_explorer(df)
    data = explorer._component_args["data"]
    assert from_data_uri(data)[1] == b"A,B\n1,4\n2,5\n3,6\n"


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
@pytest.mark.parametrize(
    ("df_input", "initial_spec_kwargs", "expected_value"),
    [
        (
            pd.DataFrame({"A": [1, 2], "B": [3, 4], "C": [5, 6]}),
            {"x": "A", "y": "B", "color": "C"},
            {"x": "A", "y": "B", "color": "C"},
        ),
        (
            pd.DataFrame({"X": [10, 20], "Y": [30, 40]}),
            {"x": "X", "size": "Y"},
            {"x": "X", "size": "Y"},
        ),
        (
            pd.DataFrame(
                {"C1": [100, 200], "C2": [300, 400], "C3": [500, 600]}
            ),
            {"row": "C1", "column": "C2", "shape": "C3"},
            {"row": "C1", "column": "C2", "shape": "C3"},
        ),
        (pd.DataFrame({"E": [1, 2], "F": [3, 4]}), {}, {}),
    ],
)
def test_data_explorer_initial_spec(
    df_input: Any,
    initial_spec_kwargs: dict[str, str],
    expected_value: dict[str, str],
) -> None:
    """Test data_explorer with various initial spec keyword arguments."""
    valid_keys = ("x", "y", "row", "column", "color", "size", "shape")
    expected_value = {**dict.fromkeys(valid_keys, None), **expected_value}
    explorer = data_explorer.data_explorer(df_input, **initial_spec_kwargs)
    assert explorer.value == expected_value
