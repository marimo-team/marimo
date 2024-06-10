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
from marimo._plugins.ui._impl.tables.types import DataFrameLike

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

    # If we have a DataFrameLike object, use the DataFrameProtocolTableManager
    if isinstance(data, DataFrameLike):
        return DataFrameProtocolTableManager(data)

    return None

# Copied from Altair
# https://github.com/vega/altair/blob/18a2c3c237014591d172284560546a2f0ac1a883/altair/utils/data.py#L343
def arrow_table_from_dataframe_protocol(
    dfi_df: DataFrameLike,
) -> "pyarrow.lib.Table":
    """
    Convert a DataFrame Interchange Protocol compatible object
    to an Arrow Table
    """
    import pyarrow as pa
    import pyarrow.interchange as pi  # type: ignore

    # First check if the dataframe object has a method to convert to arrow.
    # Give this preference over the pyarrow from_dataframe function
    # since the object
    # has more control over the conversion, and may have broader compatibility.
    # This is the case for Polars, which supports Date32 columns in
    # direct conversion
    # while pyarrow does not yet support this type in from_dataframe
    for convert_method_name in ("arrow", "to_arrow", "to_arrow_table"):
        convert_method = getattr(dfi_df, convert_method_name, None)
        if callable(convert_method):
            result = convert_method()
            if isinstance(result, pa.Table):
                return result

    return pi.from_dataframe(dfi_df)  # type: ignore[no-any-return]
