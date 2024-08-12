# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, List

from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.default_table import DefaultTableManager
from marimo._plugins.ui._impl.tables.df_protocol_table import (
    DataFrameProtocolTableManager,
)
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
from marimo._plugins.ui._impl.tables.types import (
    is_dataframe_like,
)

MANAGERS: List[TableManagerFactory] = [
    PandasTableManagerFactory(),
    PolarsTableManagerFactory(),
    PyArrowTableManagerFactory(),
]


def get_table_manager(data: Any) -> TableManager[Any]:
    return get_table_manager_or_none(data) or DefaultTableManager(data)


def get_table_manager_or_none(data: Any) -> TableManager[Any] | None:
    if data is None:
        return None

    # Try to find a manager specifically for the data type
    for manager_factory in MANAGERS:
        if DependencyManager.has(manager_factory.package_name()):
            manager = manager_factory.create()
            if manager.is_type(data):
                return manager(data)

    # Unpack narwhal dataframe wrapper
    if DependencyManager.narwhals.has():
        import narwhals  # type: ignore[import-not-found,import-untyped,unused-ignore] # noqa: E501

        if isinstance(data, narwhals.DataFrame):
            return get_table_manager_or_none(narwhals.to_native(data))

    # If we have a DataFrameLike object, use the DataFrameProtocolTableManager
    if is_dataframe_like(data):
        try:
            return DataFrameProtocolTableManager(data)
        except Exception:
            return None

    return None
