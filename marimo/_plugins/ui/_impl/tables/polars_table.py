# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Tuple, cast

from marimo._data.models import (
    ColumnSummary,
    ExternalDataType,
    NonNestedLiteral,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    FieldTypes,
    TableManager,
    TableManagerFactory,
)


class PolarsTableManagerFactory(TableManagerFactory):
    @staticmethod
    def package_name() -> str:
        return "polars"

    @staticmethod
    def create() -> type[TableManager[Any]]:
        import polars as pl

        class PolarsTableManager(TableManager[pl.DataFrame]):
            type = "polars"

            def to_csv(self) -> bytes:
                return self.data.write_csv().encode("utf-8")

            def to_json(self) -> bytes:
                return self.data.write_json(row_oriented=True).encode("utf-8")

            def supports_filters(self) -> bool:
                return True

            def select_rows(
                self, indices: list[int]
            ) -> TableManager[pl.DataFrame]:
                return PolarsTableManager(self.data[indices])

            def select_columns(
                self, columns: list[str]
            ) -> TableManager[pl.DataFrame]:
                return PolarsTableManager(self.data.select(columns))

            def get_row_headers(
                self,
            ) -> list[str]:
                return []

            @staticmethod
            def is_type(value: Any) -> bool:
                return isinstance(value, pl.DataFrame)

            def get_field_types(self) -> FieldTypes:
                return {
                    column: PolarsTableManager._get_field_type(
                        self.data[column]
                    )
                    for column in self.data.columns
                }

            def limit(self, num: int) -> PolarsTableManager:
                if num < 0:
                    raise ValueError("Limit must be a positive integer")
                return PolarsTableManager(self.data.head(num))

            def search(self, query: str) -> TableManager[Any]:
                query = query.lower()

                expressions = [
                    pl.col(column).str.contains("(?i)" + query)
                    for column in self.data.columns
                ]
                or_expr = expressions[0]
                for expr in expressions[1:]:
                    or_expr = or_expr | expr

                filtered = self.data.filter(or_expr)
                return PolarsTableManager(filtered)

            def get_summary(self, column: str) -> ColumnSummary:
                # If column is not in the dataframe, return an empty summary
                if column not in self.data.columns:
                    return ColumnSummary()
                col = self.data[column]
                total = len(col)
                if col.dtype == pl.String:
                    return ColumnSummary(
                        total=total,
                        nulls=col.null_count(),
                        unique=col.n_unique(),
                    )
                if col.dtype == pl.Boolean:
                    return ColumnSummary(
                        total=total,
                        nulls=col.null_count(),
                        true=cast(int, col.sum()),
                        false=cast(int, total - col.sum()),
                    )
                if col.dtype.is_temporal():
                    return ColumnSummary(
                        total=total,
                        nulls=col.null_count(),
                        min=cast(NonNestedLiteral, col.min()),
                        max=cast(NonNestedLiteral, col.max()),
                        mean=cast(NonNestedLiteral, col.mean()),
                        median=cast(NonNestedLiteral, col.median()),
                        p5=col.quantile(0.05),
                        p25=col.quantile(0.25),
                        p75=col.quantile(0.75),
                        p95=col.quantile(0.95),
                    )
                return ColumnSummary(
                    total=total,
                    nulls=col.null_count(),
                    unique=col.n_unique() if col.dtype.is_integer() else None,
                    min=cast(NonNestedLiteral, col.min()),
                    max=cast(NonNestedLiteral, col.max()),
                    mean=cast(NonNestedLiteral, col.mean()),
                    median=cast(NonNestedLiteral, col.median()),
                    std=col.std(),
                    p5=col.quantile(0.05),
                    p25=col.quantile(0.25),
                    p75=col.quantile(0.75),
                    p95=col.quantile(0.95),
                )

            def get_num_rows(self, force: bool = True) -> int:
                del force
                return self.data.height

            def get_num_columns(self) -> int:
                return self.data.width

            def get_column_names(self) -> list[str]:
                return self.data.columns

            def get_unique_column_values(
                self, column: str
            ) -> list[str | int | float]:
                return self.data[column].unique().to_list()

            def sort_values(
                self, by: ColumnName, descending: bool
            ) -> PolarsTableManager:
                sorted_data = self.data.sort(by, descending=descending)
                return PolarsTableManager(sorted_data)

            @staticmethod
            def _get_field_type(
                column: pl.Series,
            ) -> Tuple[FieldType, ExternalDataType]:
                dtype_string = column.dtype._string_repr()
                if column.dtype == pl.String:
                    return ("string", dtype_string)
                elif column.dtype == pl.Boolean:
                    return ("boolean", dtype_string)
                elif column.dtype.is_integer():
                    return ("integer", dtype_string)
                elif column.dtype.is_float() or column.dtype.is_numeric():
                    return ("number", dtype_string)
                elif column.dtype.is_temporal():
                    return ("date", dtype_string)
                else:
                    return ("unknown", dtype_string)

        return PolarsTableManager
