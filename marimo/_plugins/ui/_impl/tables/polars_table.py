# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import cached_property
from typing import Any, Optional, Tuple, Union

import narwhals.stable.v1 as nw

from marimo._data.models import (
    ExternalDataType,
)
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
    format_value,
)
from marimo._plugins.ui._impl.tables.narwhals_table import NarwhalsTableManager
from marimo._plugins.ui._impl.tables.table_manager import (
    FieldType,
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

        class PolarsTableManager(
            NarwhalsTableManager[Union[pl.DataFrame, pl.LazyFrame]]
        ):
            type = "polars"

            def __init__(
                self, data: Union[pl.DataFrame, pl.LazyFrame]
            ) -> None:
                self._original_data = data
                super().__init__(nw.from_native(data))

            def collect(self) -> pl.DataFrame:
                native: Any = self._original_data
                if isinstance(native, pl.LazyFrame):
                    return native.collect()
                if isinstance(native, pl.DataFrame):
                    return native
                raise ValueError(f"Unsupported native type: {type(native)}")

            @cached_property
            def schema(self) -> dict[str, pl.DataType]:
                return self._original_data.schema

            # We override narwhals's to_csv to handle polars
            # nested data types.
            def to_csv(
                self,
                format_mapping: Optional[FormatMapping] = None,
            ) -> bytes:
                _data = self.apply_formatting(format_mapping).collect()
                try:
                    return _data.write_csv().encode("utf-8")
                except pl.exceptions.ComputeError:
                    # Likely CSV format does not support nested data or objects
                    # Try to convert columns to json or strings
                    result = _data
                    for column in result.get_columns():
                        dtype = column.dtype
                        if isinstance(dtype, pl.Struct):
                            result = result.with_columns(
                                column.struct.json_encode()
                            )
                        elif isinstance(dtype, pl.List):
                            result = result.with_columns(
                                column.cast(pl.List(pl.Utf8)).list.join(",")
                            )
                        elif isinstance(dtype, pl.Array):
                            result = result.with_columns(
                                column.cast(
                                    pl.Array(pl.Utf8, shape=dtype.shape)
                                ).arr.join(",")
                            )
                        elif isinstance(dtype, pl.Object):
                            import warnings

                            with warnings.catch_warnings(record=True):
                                result = result.with_columns(
                                    # As of writing this, cast(pl.String) doesn't work
                                    # for pl.Object types, so we use map_elements
                                    column.map_elements(
                                        str, return_dtype=pl.String
                                    )
                                )
                        elif isinstance(dtype, pl.Duration):
                            unit_map = {
                                "ms": column.dt.total_milliseconds,
                                "ns": column.dt.total_nanoseconds,
                                "us": column.dt.total_microseconds,
                                "s": column.dt.total_seconds,
                            }
                            if dtype.time_unit in unit_map:
                                method = unit_map[dtype.time_unit]
                                result = result.with_columns(method())
                    return result.write_csv().encode("utf-8")

            def to_json(self) -> bytes:
                return self.collect().write_json().encode("utf-8")

            def apply_formatting(
                self, format_mapping: Optional[FormatMapping]
            ) -> PolarsTableManager:
                if not format_mapping:
                    return self

                _data = self.collect()
                for col in _data.columns:
                    if col in format_mapping:
                        _data = _data.with_columns(
                            pl.Series(
                                col,
                                [
                                    format_value(col, x, format_mapping)
                                    for x in _data[col]
                                ],
                            )
                        )
                return PolarsTableManager(_data)

            @staticmethod
            def is_type(value: Any) -> bool:
                return isinstance(value, pl.DataFrame)

            def search(self, query: str) -> PolarsTableManager:
                query = query.lower()

                expressions: list[pl.Expr] = []
                for column, dtype in self.schema.items():
                    if dtype == pl.String:
                        expressions.append(
                            pl.col(column).str.contains(f"(?i){query}")
                        )
                    elif dtype == pl.List(pl.Utf8):
                        expressions.append(pl.col(column).list.contains(query))
                    elif (
                        dtype.is_numeric()
                        or dtype.is_temporal()
                        or dtype == pl.Boolean
                    ):
                        expressions.append(
                            pl.col(column)
                            .cast(pl.String)
                            .str.contains(f"(?i){query}")
                        )

                if not expressions:
                    return self

                or_expr = expressions[0]
                for expr in expressions[1:]:
                    or_expr = or_expr | expr

                filtered = self._original_data.filter(or_expr)
                return PolarsTableManager(filtered)

            # We override the default implementation to use polars's
            # internal fields since they get displayed in the UI.
            def get_field_type(
                self, column_name: str
            ) -> Tuple[FieldType, ExternalDataType]:
                dtype = self.schema[column_name]
                try:
                    dtype_string = dtype._string_repr()
                except (TypeError, AttributeError):
                    dtype_string = str(dtype)
                if (
                    dtype == pl.String
                    or dtype == pl.Categorical
                    or dtype == pl.Enum
                ):
                    return ("string", dtype_string)
                elif dtype == pl.Boolean:
                    return ("boolean", dtype_string)
                elif dtype.is_integer():
                    return ("integer", dtype_string)
                elif (
                    dtype.is_float()
                    or dtype.is_numeric()
                    or dtype.is_decimal()
                ):
                    return ("number", dtype_string)
                elif dtype == pl.Date:
                    return ("date", dtype_string)
                elif dtype == pl.Time:
                    return ("time", dtype_string)
                elif dtype == pl.Duration:
                    return ("number", dtype_string)
                elif dtype == pl.Datetime:
                    return ("datetime", dtype_string)
                elif dtype.is_temporal():
                    return ("datetime", dtype_string)
                else:
                    return ("unknown", dtype_string)

        return PolarsTableManager
