# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl import data_explorer
from marimo._utils.data_uri import from_data_uri
from marimo._utils.platform import is_windows
from tests._data.mocks import create_dataframes

HAS_DEPS = DependencyManager.pandas.has()


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
    import pandas as pd

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
