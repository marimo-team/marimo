# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import pytest

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl import data_explorer
from marimo._runtime.runtime import ExecutionContext
from tests.conftest import MockedKernel

HAS_DEPS = DependencyManager.has_pandas()


@pytest.mark.skipif(not HAS_DEPS, reason="optional dependencies not installed")
def test_data_explorer() -> None:
    import pandas as pd

    # Create kernel and give the execution context an existing cell
    mocked = MockedKernel()
    mocked.k.execution_context = ExecutionContext("test_cell_id", False)

    data = pd.DataFrame({"A": [1, 2, 3], "B": [4, 5, 6]})
    explorer = data_explorer.data_explorer(data)
    assert explorer
