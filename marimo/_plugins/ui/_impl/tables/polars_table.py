# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

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
