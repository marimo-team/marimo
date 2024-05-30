# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, cast

from marimo._data.models import ColumnSummary, NonNestedLiteral
from marimo._plugins.ui._impl.tables.table_manager import (
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

            def select_rows(
                self, indices: list[int]
            ) -> TableManager[pl.DataFrame]:
                return PolarsTableManager(self.data[indices])

            def get_row_headers(
                self,
            ) -> list[tuple[str, list[str | int | float]]]:
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

            def get_summary(self, column: str) -> ColumnSummary:
                # If column is not in the dataframe, return an empty summary
                if column not in self.data.columns:
                    return ColumnSummary()
                col = self.data[column]
                total = len(col)
                if col.is_utf8():
                    return ColumnSummary(
                        total=total,
                        nulls=col.null_count(),
                        unique=col.n_unique(),
                    )
                if col.is_boolean():
                    return ColumnSummary(
                        total=total,
                        nulls=col.null_count(),
                        true=col.sum(),
                        false=total - col.sum(),
                    )
                if col.is_temporal():
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
                    unique=col.n_unique() if col.is_integer() else None,
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

            def get_num_rows(self) -> int:
                return self.data.height

            def get_num_columns(self) -> int:
                return self.data.width

            @staticmethod
            def _get_field_type(column: pl.Series) -> FieldType:
                if column.is_utf8():
                    return "string"
                elif column.is_boolean():
                    return "boolean"
                elif column.is_integer():
                    return "integer"
                elif column.is_float() or column.is_numeric():
                    return "number"
                elif column.is_temporal():
                    return "date"
                else:
                    return "unknown"

        return PolarsTableManager
