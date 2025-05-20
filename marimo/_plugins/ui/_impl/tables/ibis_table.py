# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

import narwhals as nw

from marimo._data.models import (
    ColumnSummary,
    ExternalDataType,
)
from marimo._plugins.ui._impl.tables.narwhals_table import NarwhalsTableManager
from marimo._plugins.ui._impl.tables.table_manager import (
    FieldType,
    TableManager,
    TableManagerFactory,
)


class IbisTableManagerFactory(TableManagerFactory):
    @staticmethod
    def package_name() -> str:
        return "ibis"

    @staticmethod
    def create() -> type[TableManager[Any]]:
        import ibis  # type: ignore

        class IbisTableManager(NarwhalsTableManager[ibis.Table]):
            type = "ibis"

            def __init__(self, data: ibis.Table) -> None:
                self._original_data = data
                super().__init__(nw.from_native(data))

            def collect(self) -> ibis.Table:
                return self._original_data

            @staticmethod
            def is_type(value: Any) -> bool:
                return isinstance(value, ibis.Table)

            def get_row_headers(
                self,
            ) -> list[str]:
                return []

            def get_summary(self, column: str) -> ColumnSummary:
                frame = self.as_lazy_frame()
                col = nw.col(column)
                exprs = {
                    "total": nw.len().alias("total"),
                    "nulls": col.null_count(),
                }
                if frame.schema[column].is_numeric():
                    exprs.update(
                        {
                            "min": col.min(),
                            "max": col.max(),
                            "mean": col.mean(),
                            "median": col.median(),
                            "std": col.std(),
                        }
                    )

                summary = frame.select(**exprs)
                return ColumnSummary(**summary.collect().rows(named=True)[0])

            def get_field_type(
                self, column_name: str
            ) -> tuple[FieldType, ExternalDataType]:
                column = self._original_data[column_name]
                dtype = column.type()
                if dtype.is_string():
                    return ("string", str(dtype))
                elif dtype.is_boolean():
                    return ("boolean", str(dtype))
                elif dtype.is_integer():
                    return ("integer", str(dtype))
                elif dtype.is_floating():
                    return ("number", str(dtype))
                elif dtype.is_timestamp():
                    return ("datetime", str(dtype))
                elif dtype.is_time():
                    return ("time", str(dtype))
                elif dtype.is_date():
                    return ("date", str(dtype))
                else:
                    return ("unknown", str(dtype))

        return IbisTableManager
