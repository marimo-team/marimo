# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, List

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.default_table import DefaultTableManager
from marimo._plugins.ui._impl.tables.pandas_table import (
    PandasTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.polars_table import (
    PolarsTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.pyarrow_table import (
    PyArrowTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    TableManager,
    TableManagerFactory,
)

MANAGERS: List[TableManagerFactory] = [
    PandasTableManagerFactory(),
    PolarsTableManagerFactory(),
    PyArrowTableManagerFactory(),
]


def get_table_manager(data: Any) -> TableManager[Any]:
    for manager_factory in MANAGERS:
        if DependencyManager.has(manager_factory.package_name()):
            manager = manager_factory.create()
            if manager.is_type(data):
                return manager(data)

    return DefaultTableManager(data)
