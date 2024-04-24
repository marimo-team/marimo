# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
from typing import Any, Union, cast

from marimo._plugins.ui._impl.tables.table_manager import (
    FieldType,
    FieldTypes,
    TableManager,
    TableManagerFactory,
)


class PyArrowTableManagerFactory(TableManagerFactory):
    @staticmethod
    def package_name() -> str:
        return "pyarrow"

    @staticmethod
    def create() -> type[TableManager[Any]]:
        import pyarrow as pa  # type: ignore

        class PyArrowTableManager(
            TableManager[Union[pa.Table, pa.RecordBatch]]
        ):
            def to_csv(self) -> bytes:
                import pyarrow.csv as csv  # type: ignore

                buffer = io.BytesIO()
                csv.write_csv(self.data, buffer)
                return buffer.getvalue()

            def to_json(self) -> bytes:
                # Arrow does not have a built-in JSON writer
                return (
                    self.data.to_pandas()
                    .to_json(orient="records")
                    .encode("utf-8")
                )

            def select_rows(self, indices: list[int]) -> PyArrowTableManager:
                if not indices:
                    return PyArrowTableManager(
                        pa.Table.from_pylist([], schema=self.data.schema)
                    )
                return PyArrowTableManager(self.data.take(indices))

            def get_row_headers(
                self,
            ) -> list[tuple[str, list[str | int | float]]]:
                return []

            @staticmethod
            def is_type(value: Any) -> bool:
                import pyarrow as pa  # type: ignore

                return isinstance(value, pa.Table) or isinstance(
                    value, pa.RecordBatch
                )

            def get_field_types(self) -> FieldTypes:
                return {
                    column: PyArrowTableManager._get_field_type(
                        cast(Any, self.data)[idx]
                    )
                    for idx, column in enumerate(self.data.schema.names)
                }

            @staticmethod
            def _get_field_type(column: pa.Array[Any, Any]) -> FieldType:
                if isinstance(column, pa.NullArray):
                    return "unknown"
                elif pa.types.is_string(column.type):
                    return "string"
                elif pa.types.is_boolean(column.type):
                    return "boolean"
                elif pa.types.is_integer(column.type):
                    return "integer"
                elif pa.types.is_floating(column.type) or pa.types.is_decimal(
                    column.type
                ):
                    return "number"
                elif pa.types.is_date(column.type) or pa.types.is_timestamp(
                    column.type
                ):
                    return "date"
                else:
                    return "unknown"

        return PyArrowTableManager
