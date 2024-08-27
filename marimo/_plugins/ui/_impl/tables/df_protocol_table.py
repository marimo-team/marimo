# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional, Tuple, Union

from marimo._data.models import ColumnSummary, ExternalDataType
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.dataframe_protocol import (
    Column,
    DtypeKind,
)
from marimo._plugins.ui._impl.tables.format import FormatMapping
from marimo._plugins.ui._impl.tables.pyarrow_table import (
    PyArrowTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    FieldTypes,
    TableManager,
)
from marimo._plugins.ui._impl.tables.types import (
    DataFrameLike,
    is_dataframe_like,
)

if TYPE_CHECKING:
    import pyarrow as pa  # type: ignore


class DataFrameProtocolTableManager(TableManager[DataFrameLike]):
    type = "dataframe-like"

    def __init__(self, data: DataFrameLike):
        self.data = data
        self._df = data.__dataframe__()

        if not hasattr(self._df, "num_columns"):
            raise ValueError(
                "The DataFrameLike object must have a num_columns method"
            )

        self._delegate: Optional[
            TableManager[Union[pa.Table, pa.RecordBatch]]
        ] = None

    def _ensure_delegate(
        self,
    ) -> TableManager[Union[pa.Table, pa.RecordBatch]]:
        DependencyManager.pyarrow.require(
            "for table support using the dataframe protocol"
        )

        if self._delegate is None:
            self._delegate = PyArrowTableManagerFactory.create()(
                arrow_table_from_dataframe_protocol(self.data)
            )
        return self._delegate

    def apply_formatting(  # type: ignore
        self, format_mapping: FormatMapping
    ) -> Union[pa.Table, pa.RecordBatch]:
        return self._ensure_delegate().apply_formatting(format_mapping)

    def supports_filters(self) -> bool:
        # Does't support filters until pyarrow supports it
        return False

    def to_csv(self, format_mapping: Optional[FormatMapping] = None) -> bytes:
        return self._ensure_delegate().to_csv(format_mapping)

    def to_json(self) -> bytes:
        return self._ensure_delegate().to_json()

    @staticmethod
    def is_type(value: Any) -> bool:
        return is_dataframe_like(value)

    def select_rows(
        self, indices: list[int]
    ) -> TableManager[Union[pa.Table, pa.RecordBatch]]:
        return self._ensure_delegate().select_rows(indices)

    def select_columns(
        self, columns: list[str]
    ) -> TableManager[Union[pa.Table, pa.RecordBatch]]:
        return self._ensure_delegate().select_columns(columns)

    def get_row_headers(
        self,
    ) -> list[str]:
        return []

    def get_field_types(self) -> FieldTypes:
        return {
            column: self._get_field_type(self._df.get_column_by_name(column))
            for column in self._df.column_names()
        }

    def take(
        self, count: int, offset: int
    ) -> TableManager[Union[pa.Table, pa.RecordBatch]]:
        return self._ensure_delegate().take(count, offset)

    def search(self, query: str) -> TableManager[Any]:
        return self._ensure_delegate().search(query)

    def get_summary(self, column: str) -> ColumnSummary:
        return self._ensure_delegate().get_summary(column)

    def get_num_rows(self, force: bool = True) -> Optional[int]:
        if force:
            return self._df.num_rows() or int("nan")
        return None

    def get_num_columns(self) -> int:
        return self._df.num_columns() or int("nan")

    def get_column_names(self) -> list[str]:
        return list(self._df.column_names())

    def get_unique_column_values(
        self, column: ColumnName
    ) -> list[str | int | float]:
        return self._ensure_delegate().get_unique_column_values(column)

    def sort_values(
        self, by: ColumnName, descending: bool
    ) -> TableManager[DataFrameLike]:
        return self._ensure_delegate().sort_values(by, descending)

    @staticmethod
    def _get_field_type(column: Column) -> Tuple[FieldType, ExternalDataType]:
        kind = column.dtype[0]
        if kind == DtypeKind.BOOL:
            return ("boolean", "BOOL")
        elif kind == DtypeKind.INT:
            return ("integer", "INT")
        elif kind == DtypeKind.UINT:
            return ("integer", "UINT")
        elif kind == DtypeKind.FLOAT:
            return ("number", "FLOAT")
        elif kind == DtypeKind.STRING:
            return ("string", "STRING")
        elif kind == DtypeKind.DATETIME:
            return ("date", "DATETIME")
        elif kind == DtypeKind.CATEGORICAL:
            return ("string", "CATEGORICAL")
        else:
            return ("unknown", "UNKNOWN")


# Copied from Altair
# https://github.com/vega/altair/blob/18a2c3c237014591d172284560546a2f0ac1a883/altair/utils/data.py#L343
def arrow_table_from_dataframe_protocol(
    dfi_df: DataFrameLike,
) -> "pa.lib.Table":
    """
    Convert a DataFrame Interchange Protocol compatible object
    to an Arrow Table
    """
    import pyarrow as pa
    import pyarrow.interchange as pi

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
