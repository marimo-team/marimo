# Copyright 2023 Marimo. All rights reserved.
from typing import Any, Generator

import pytest

from marimo._plugins.ui._impl.table import TableData, _normalize_data
from marimo._runtime.conftest import MockedKernel
from marimo._runtime.context import get_context
from marimo._runtime.runtime import ExecutionContext, Kernel


# fixture that wraps a kernel and other mocked objects
@pytest.fixture
def k() -> Generator[MockedKernel, None, None]:
    mocked = MockedKernel()
    # Give the execution context an existing cell
    mocked.k.execution_context = ExecutionContext("test_cell_id", False)
    yield mocked
    # have to teardown the runtime context because it's a global
    get_context()._kernel = None
    get_context()._ui_element_registry = None
    get_context()._stream = None
    get_context()._initialized = False


def test_normalize_data(k: Kernel) -> None:
    data: TableData

    # Test with list of integers
    data = [1, 2, 3]
    result = _normalize_data(data)
    assert result == [
        {"value": 1},
        {"value": 2},
        {"value": 3},
    ]

    # Test with list of strings
    data = ["a", "b", "c"]
    result = _normalize_data(data)
    assert result == [
        {"value": "a"},
        {"value": "b"},
        {"value": "c"},
    ]

    # Test with list of dictionaries
    data = [
        {"key1": "value1"},
        {"key2": "value2"},
        {"key3": "value3"},
    ]  # type: ignore
    result = _normalize_data(data)
    assert result == [
        {"key1": "value1"},
        {"key2": "value2"},
        {"key3": "value3"},
    ]

    # Test with pandas DataFrame
    try:
        import pandas as pd

        data = pd.DataFrame({"column1": [1, 2, 3], "column2": ["a", "b", "c"]})
        result = _normalize_data(data)
        assert type(result) == str
        assert result.endswith(".csv")
    except ImportError:
        pass

    # Test with invalid data type
    data2: Any = "invalid data type"
    try:
        _normalize_data(data2)
    except ValueError as e:
        assert str(e) == "data must be a list or tuple."

    # Test with invalid data structure
    data3: Any = [set([1, 2, 3])]
    try:
        _normalize_data(data3)
    except ValueError as e:
        assert (
            str(e)
            == "data must be a sequence of JSON-serializable types, or a "
            + "sequence of dicts."
        )
