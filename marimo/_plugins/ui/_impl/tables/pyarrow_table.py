# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
from typing import Any, Union, cast

from marimo._data.models import ColumnSummary
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
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
        import pyarrow.compute as pc  # type: ignore

        class PyArrowTableManager(
            TableManager[Union[pa.Table, pa.RecordBatch]]
        ):
            type = "pyarrow"

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

            def supports_filters(self) -> bool:
                # Does't support filters until we
                # have a PyArrowTransformHandler
                return False

            def select_columns(
                self, columns: list[str]
            ) -> PyArrowTableManager:
                if isinstance(self.data, pa.RecordBatch):
                    return PyArrowTableManager(
                        pa.RecordBatch.from_arrays(
                            [
                                self.data.column(
                                    self.data.schema.get_field_index(col)
                                )
                                for col in columns
                            ],
                            names=columns,
                        )
                    )
                return PyArrowTableManager(self.data.select(columns))

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

            def limit(self, num: int) -> PyArrowTableManager:
                if num < 0:
                    raise ValueError("Limit must be a positive integer")
                if num >= self.data.num_rows:
                    return PyArrowTableManager(self.data)
                return PyArrowTableManager(self.data.take(list(range(num))))

            def search(self, query: str) -> TableManager[Any]:
                query = query.lower()
                import pyarrow.compute as pc

                masks: list[Any] = []
                for column in self.data.columns:  # type: ignore
                    # Cast to string to handle non-string columns
                    column = pc.cast(column, pa.string())  # type: ignore
                    mask: pa.BooleanArray = pc.match_substring(  # type: ignore
                        column, query, ignore_case=True
                    )
                    masks.append(mask)

                # Combine the masks using logical OR
                combined_mask: pa.BooleanArray = masks[0]
                for mask in masks[1:]:
                    combined_mask = pc.or_(combined_mask, mask)  # type: ignore
                return PyArrowTableManager(self.data.filter(combined_mask))

            def get_summary(self, column: str) -> ColumnSummary:
                # If column is not in the dataframe, return an empty summary
                if column not in self.data.schema.names:
                    return ColumnSummary()
                idx = self.data.schema.get_field_index(column)
                col: Any = self.data.column(idx)

                field_type = self._get_field_type(col)
                if field_type == "unknown":
                    return ColumnSummary()
                if field_type == "string":
                    return ColumnSummary(
                        total=self.data.num_rows,
                        nulls=col.null_count,
                        unique=pc.count_distinct(col).as_py(),  # type: ignore[attr-defined]
                    )
                if field_type == "boolean":
                    return ColumnSummary(
                        total=self.data.num_rows,
                        nulls=col.null_count,
                        true=pc.sum(col).as_py(),  # type: ignore[attr-defined]
                        false=self.data.num_rows
                        - pc.sum(col).as_py()  # type: ignore[attr-defined]
                        - col.null_count,
                    )
                if field_type == "integer":
                    return ColumnSummary(
                        total=self.data.num_rows,
                        nulls=col.null_count,
                        unique=pc.count_distinct(col).as_py(),  # type: ignore[attr-defined]
                        min=pc.min(col).as_py(),  # type: ignore[attr-defined]
                        max=pc.max(col).as_py(),  # type: ignore[attr-defined]
                        mean=pc.mean(col).as_py(),  # type: ignore[attr-defined]
                    )
                if field_type == "number":
                    return ColumnSummary(
                        total=self.data.num_rows,
                        nulls=col.null_count,
                        min=pc.min(col).as_py(),  # type: ignore[attr-defined]
                        max=pc.max(col).as_py(),  # type: ignore[attr-defined]
                        mean=pc.mean(col).as_py(),  # type: ignore[attr-defined]
                    )
                if field_type == "date":
                    return ColumnSummary(
                        total=self.data.num_rows,
                        nulls=col.null_count,
                        min=pc.min(col).as_py(),  # type: ignore[attr-defined]
                        max=pc.max(col).as_py(),  # type: ignore[attr-defined]
                    )
                return ColumnSummary()

            def get_num_rows(self, force: bool = True) -> int:
                del force
                return self.data.num_rows

            def get_num_columns(self) -> int:
                return self.data.num_columns

            def get_column_names(self) -> list[str]:
                return self.data.schema.names

            def get_unique_column_values(
                self, column: str
            ) -> list[str | int | float]:
                idx = self.data.schema.get_field_index(column)
                col: Any = self.data.column(idx)
                return pc.unique(col).to_pylist()  # type: ignore[attr-defined, no-any-return]

            def sort_values(
                self, by: ColumnName, descending: bool
            ) -> PyArrowTableManager:
                sorted_data = self.data.sort_by(  # type: ignore
                    [(by, "ascending" if not descending else "descending")]
                )
                return PyArrowTableManager(sorted_data)

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
