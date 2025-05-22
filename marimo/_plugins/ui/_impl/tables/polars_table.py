# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
from functools import cached_property
from typing import Any, Optional, Union

import narwhals.stable.v1 as nw

from marimo import _loggers
from marimo._data.models import (
    ExternalDataType,
)
from marimo._output.data.data import sanitize_json_bigint
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

LOGGER = _loggers.marimo_logger()


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
                if isinstance(self._original_data, pl.LazyFrame):
                    # Less expensive operation
                    return self._original_data.collect_schema()
                return self._original_data.schema

            def to_arrow_ipc(self) -> bytes:
                out = io.BytesIO()
                self.collect().write_ipc(out)
                return out.getvalue()

            # We override narwhals's to_csv to handle polars
            # nested data types.
            def to_csv_str(
                self,
                format_mapping: Optional[FormatMapping] = None,
            ) -> str:
                _data = self.apply_formatting(format_mapping).collect()
                try:
                    return _data.write_csv()
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
                            result = self._cast_object_to_string(
                                result, column
                            )
                        elif isinstance(dtype, pl.Duration):
                            result = self._convert_time_to_string(
                                result, column
                            )
                    return result.write_csv()

            def to_json_str(
                self, format_mapping: Optional[FormatMapping] = None
            ) -> str:
                result = self.apply_formatting(format_mapping).collect()
                try:
                    for column in result.get_columns():
                        dtype = column.dtype
                        if isinstance(dtype, pl.Duration):
                            result = self._convert_time_to_string(
                                result, column
                            )
                    return sanitize_json_bigint(result.write_json())
                except (
                    BaseException
                ):  # Sometimes, polars throws a generic exception
                    LOGGER.info(
                        "Failed to write json. Trying to convert columns to strings."
                    )
                    for column in result.get_columns():
                        dtype = column.dtype
                        if isinstance(dtype, pl.Object):
                            result = self._cast_object_to_string(
                                result, column
                            )
                        elif str(dtype) == "Int128":
                            # Use string comparison because pl.Int128 doesn't exist on older versions
                            # As of writing this, Int128 is not supported by polars
                            LOGGER.warning(
                                "Column %s is of type Int128, which is not supported. Converting to string.",
                                column.name,
                            )
                            result = result.with_columns(
                                column.cast(pl.String)
                            )
                        elif isinstance(dtype, pl.Duration):
                            result = self._convert_time_to_string(
                                result, column
                            )

                    return sanitize_json_bigint(result.write_json())

            def _convert_time_to_string(
                self, result: pl.DataFrame, column: pl.Series
            ) -> pl.DataFrame:
                # Converts to human readable format
                return result.with_columns(
                    column.dt.to_string(format="polars")
                )

            def _cast_object_to_string(
                self, df: pl.DataFrame, column: pl.Series
            ) -> pl.DataFrame:
                import warnings

                with warnings.catch_warnings(record=True):
                    return df.with_columns(
                        # As of writing this, cast(pl.String) doesn't work
                        # for pl.Object types, so we use map_elements
                        column.map_elements(
                            lambda v: str(self._sanitize_table_value(v)),
                            return_dtype=pl.String,
                        )
                    )

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
                return isinstance(value, (pl.DataFrame, pl.LazyFrame))

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
            ) -> tuple[FieldType, ExternalDataType]:
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
