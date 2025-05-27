# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import functools
import io
from functools import cached_property
from typing import Any, Optional, Union, cast

import narwhals.stable.v1 as nw
from narwhals.stable.v1.typing import IntoFrameT

from marimo import _loggers
from marimo._data.models import ColumnStats, ExternalDataType
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.data.data import sanitize_json_bigint
from marimo._plugins.core.media import io_to_data_url
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
    format_value,
)
from marimo._plugins.ui._impl.tables.selection import INDEX_COLUMN_NAME
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    TableCell,
    TableCoordinate,
    TableManager,
)
from marimo._utils.narwhals_utils import (
    can_narwhalify,
    dataframe_to_csv,
    is_narwhals_integer_type,
    is_narwhals_lazyframe,
    is_narwhals_string_type,
    is_narwhals_temporal_type,
    is_narwhals_time_type,
    unwrap_py_scalar,
    upgrade_narwhals_df,
)

LOGGER = _loggers.marimo_logger()


class NarwhalsTableManager(
    TableManager[Union[nw.DataFrame[IntoFrameT], nw.LazyFrame[IntoFrameT]]]
):
    type = "narwhals"

    @staticmethod
    def from_dataframe(data: IntoFrameT) -> NarwhalsTableManager[IntoFrameT]:
        return NarwhalsTableManager(nw.from_native(data, pass_through=False))

    def as_frame(self) -> nw.DataFrame[Any]:
        if is_narwhals_lazyframe(self.data):
            return self.data.collect()
        return self.data

    def upgrade(self) -> NarwhalsTableManager[Any]:
        return NarwhalsTableManager(upgrade_narwhals_df(self.data))

    def as_lazy_frame(self) -> nw.LazyFrame[Any]:
        if is_narwhals_lazyframe(self.data):
            return self.data
        return self.data.lazy()

    def with_new_data(
        self, data: nw.DataFrame[Any] | nw.LazyFrame[Any]
    ) -> TableManager[Any]:
        if type(self) is NarwhalsTableManager:
            return NarwhalsTableManager(data)
        # If this call comes from a subclass, we need to call the constructor
        # of the subclass with the native data.
        return self.__class__(data.to_native())

    def to_csv_str(
        self,
        format_mapping: Optional[FormatMapping] = None,
    ) -> str:
        _data = self.apply_formatting(format_mapping).as_frame()
        return dataframe_to_csv(_data)

    def to_json_str(
        self, format_mapping: Optional[FormatMapping] = None
    ) -> str:
        frame = self.upgrade().apply_formatting(format_mapping).as_frame()
        return sanitize_json_bigint(frame.rows(named=True))

    def to_parquet(self) -> bytes:
        stream = io.BytesIO()
        self.as_frame().write_parquet(stream)
        return stream.getvalue()

    def apply_formatting(
        self, format_mapping: Optional[FormatMapping]
    ) -> NarwhalsTableManager[Any]:
        if not format_mapping:
            return self

        frame = self.upgrade().as_frame()
        _data = frame.to_dict(as_series=False).copy()
        for col in _data.keys():
            if col in format_mapping:
                _data[col] = [
                    format_value(col, x, format_mapping) for x in _data[col]
                ]
        return NarwhalsTableManager(
            nw.from_dict(_data, backend=nw.get_native_namespace(frame))
        )

    def supports_filters(self) -> bool:
        return True

    def select_rows(self, indices: list[int]) -> TableManager[Any]:
        if not indices:
            return self.with_new_data(self.data.head(0))

        # Prefer the index column for selections
        if INDEX_COLUMN_NAME in self.nw_schema.names():
            # Drop the index column before returning
            return self.with_new_data(
                self.data.filter(nw.col(INDEX_COLUMN_NAME).is_in(indices))
            )

        df = self.as_frame()
        return self.with_new_data(df[indices])

    def select_columns(self, columns: list[str]) -> TableManager[Any]:
        return self.with_new_data(self.data.select(columns))

    def select_cells(self, cells: list[TableCoordinate]) -> list[TableCell]:
        if not cells:
            return []

        df = self.as_frame()
        if INDEX_COLUMN_NAME in df.columns:
            selection: list[TableCell] = []
            for row, col in cells:
                filtered: nw.DataFrame[Any] = df.filter(
                    nw.col(INDEX_COLUMN_NAME) == int(row)
                )
                if filtered.is_empty():
                    continue

                selection.append(
                    TableCell(row, col, filtered.get_column(col)[0])
                )

            return selection
        else:
            return [
                TableCell(row, col, df.item(row=int(row), column=col))
                for row, col in cells
            ]

    def drop_columns(self, columns: list[str]) -> TableManager[Any]:
        return self.with_new_data(self.data.drop(columns, strict=False))

    def get_row_headers(
        self,
    ) -> list[str]:
        return []

    @functools.lru_cache(maxsize=5)  # noqa: B019
    def calculate_top_k_rows(
        self, column: ColumnName, k: int
    ) -> list[tuple[Any, int]]:
        if column not in self.get_column_names():
            raise ValueError(f"Column {column} not found in table.")

        frame = self.as_lazy_frame()
        _unique_name = "__len_count__"

        def _calculate_top_k_rows(
            df: nw.DataFrame[Any] | nw.LazyFrame[Any],
        ) -> nw.DataFrame[Any]:
            result = (
                df.group_by(column)
                .agg(nw.len().alias(_unique_name))
                .sort(
                    [_unique_name, column],
                    descending=[True, False],
                    nulls_last=False,
                )
                .head(k)
            )
            if isinstance(result, nw.LazyFrame):
                return result.collect()
            return result

        # For pandas, dicts and lists are unhashable, and thus cannot be grouped_by
        # so we convert them to strings
        if self.data.implementation.is_pandas():
            import pandas as pd

            df = self.data.to_native()
            if (
                isinstance(df, pd.DataFrame)
                and not df.empty
                and isinstance(df[column].iloc[0], (list, dict))
            ):
                str_data = self.data.select(self.data[column].cast(nw.String))
                result = _calculate_top_k_rows(str_data)
                str_to_val = {str(val): val for val in df[column]}

                # Map back to the original values
                return [
                    (
                        str_to_val.get(unwrap_py_scalar(row[0])),
                        int(unwrap_py_scalar(row[1])),
                    )
                    for row in result.rows()
                ]

        result = _calculate_top_k_rows(frame)
        return [
            (unwrap_py_scalar(row[0]), int(unwrap_py_scalar(row[1])))
            for row in result.rows()
        ]

    @staticmethod
    def is_type(value: Any) -> bool:
        return can_narwhalify(value)

    @cached_property
    def nw_schema(self) -> nw.Schema:
        return cast(nw.Schema, self.data.collect_schema())

    def get_field_type(
        self, column_name: str
    ) -> tuple[FieldType, ExternalDataType]:
        dtype = self.nw_schema[column_name]
        dtype_string = str(dtype)
        if is_narwhals_string_type(dtype):
            return ("string", dtype_string)
        elif dtype == nw.Boolean:
            return ("boolean", dtype_string)
        elif dtype == nw.Duration:
            return ("number", dtype_string)
        elif dtype.is_integer():
            return ("integer", dtype_string)
        elif is_narwhals_time_type(dtype):
            return ("time", dtype_string)
        elif dtype == nw.Date:
            return ("date", dtype_string)
        elif dtype == nw.Datetime:
            return ("datetime", dtype_string)
        elif dtype.is_temporal():
            return ("datetime", dtype_string)
        elif dtype.is_numeric():
            return ("number", dtype_string)
        else:
            return ("unknown", dtype_string)

    def take(self, count: int, offset: int) -> TableManager[Any]:
        if count < 0:
            raise ValueError("Count must be a positive integer")
        if offset < 0:
            raise ValueError("Offset must be a non-negative integer")

        if offset == 0:
            return self.with_new_data(self.data.head(count))
        else:
            return self.with_new_data(self.data[offset : offset + count])

    def search(self, query: str) -> TableManager[Any]:
        query = query.lower()

        expressions: list[Any] = []
        for column, dtype in self.nw_schema.items():
            if column == INDEX_COLUMN_NAME:
                continue
            if dtype == nw.String:
                expressions.append(nw.col(column).str.contains(f"(?i){query}"))
            elif dtype == nw.List(nw.String):
                # TODO: Narwhals doesn't support list.contains
                # expressions.append(
                #     nw.col(column).list.contains(query)
                # )
                pass
            elif (
                dtype.is_numeric()
                or is_narwhals_temporal_type(dtype)
                or dtype == nw.Boolean
            ):
                expressions.append(
                    nw.col(column).cast(nw.String).str.contains(f"(?i){query}")
                )

        if not expressions:
            return NarwhalsTableManager(self.data.filter(nw.lit(False)))

        or_expr = expressions[0]
        for expr in expressions[1:]:
            or_expr = or_expr | expr

        filtered = self.data.filter(or_expr)
        return NarwhalsTableManager(filtered)

    def get_stats(self, column: str) -> ColumnStats:
        stats = self._get_stats_internal(column)
        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore",
                message="Discarding nonzero nanoseconds in conversion",
                category=UserWarning,
            )

            for key, value in stats.__dict__.items():
                if value is not None:
                    stats.__dict__[key] = unwrap_py_scalar(value)
        return stats

    def _get_stats_internal(self, column: str) -> ColumnStats:
        # If column is not in the dataframe, return empty stats
        if column not in self.nw_schema:
            return ColumnStats()

        frame = self.data.lazy()
        col = nw.col(column)
        dtype = self.nw_schema[column]
        units: dict[str, str] = {}

        # Base expressions for all types
        exprs: dict[str, nw.Expr] = {
            "total": nw.len().alias("total"),
            "nulls": col.null_count(),
        }

        if is_narwhals_string_type(dtype):
            exprs["unique"] = col.n_unique()
        elif dtype == nw.Boolean:
            exprs.update(
                {
                    "true": col.sum(),  # type: ignore[dict-item]
                    "false": nw.len() - col.sum(),  # type: ignore[dict-item]
                }
            )
        elif (dtype == nw.Date) or is_narwhals_time_type(dtype):
            exprs.update(
                {
                    "min": col.min(),
                    "max": col.max(),
                }
            )
            # Arrow does not support mean or quantile
            if not frame.implementation.is_pyarrow():
                exprs["mean"] = col.mean()
                # Quantile not supported on date and time types
                # exprs["median"] = col.quantile(0.5, interpolation="nearest")

        elif dtype == nw.Duration and isinstance(dtype, nw.Duration):
            unit_map = {
                "ms": (col.dt.total_milliseconds, "ms"),
                "ns": (col.dt.total_nanoseconds, "ns"),
                "us": (col.dt.total_microseconds, "μs"),
                "s": (col.dt.total_seconds, "s"),
            }
            method, unit = unit_map[dtype.time_unit]
            res = method()
            exprs.update(
                {
                    "min": res.min(),
                    "max": res.max(),
                    "mean": res.mean(),
                }
            )
            units.update(
                {
                    "min": unit,
                    "max": unit,
                    "mean": unit,
                }
            )
        elif is_narwhals_temporal_type(dtype):
            exprs.update(
                {
                    "min": col.min(),
                    "max": col.max(),
                }
            )
            # Arrow does not support mean or quantile
            if not frame.implementation.is_pyarrow():
                exprs.update(
                    {
                        "mean": col.mean(),
                        "median": col.quantile(0.5, interpolation="nearest"),
                        "p5": col.quantile(0.05, interpolation="nearest"),
                        "p25": col.quantile(0.25, interpolation="nearest"),
                        "p75": col.quantile(0.75, interpolation="nearest"),
                        "p95": col.quantile(0.95, interpolation="nearest"),
                    }
                )
        elif is_narwhals_integer_type(dtype):
            exprs.update(
                {
                    "unique": col.n_unique(),
                    "min": col.min(),
                    "max": col.max(),
                    "mean": col.mean(),
                    "median": col.quantile(0.5, interpolation="nearest"),
                    "std": col.std(),
                    "p5": col.quantile(0.05, interpolation="nearest"),
                    "p25": col.quantile(0.25, interpolation="nearest"),
                    "p75": col.quantile(0.75, interpolation="nearest"),
                    "p95": col.quantile(0.95, interpolation="nearest"),
                }
            )
        elif dtype.is_numeric():
            exprs.update(
                {
                    "min": col.min(),
                    "max": col.max(),
                    "mean": col.mean(),
                    "median": col.quantile(0.5, interpolation="nearest"),
                    "std": col.std(),
                    "p5": col.quantile(0.05, interpolation="nearest"),
                    "p25": col.quantile(0.25, interpolation="nearest"),
                    "p75": col.quantile(0.75, interpolation="nearest"),
                    "p95": col.quantile(0.95, interpolation="nearest"),
                }
            )

        stats = frame.select(**exprs)
        stats_dict = stats.collect().rows(named=True)[0]

        # Maybe add units to the stats
        for key, value in stats_dict.items():
            if key in units:
                stats_dict[key] = f"{value} {units[key]}"

        return ColumnStats(**stats_dict)

    def get_num_rows(self, force: bool = True) -> Optional[int]:
        # If force is true, collect the data and get the number of rows
        if force:
            return self.as_frame().shape[0]

        # When lazy, we don't know the number of rows
        if is_narwhals_lazyframe(self.data):
            return None

        # Otherwise, we can get the number of rows from the shape
        try:
            return self.data.shape[0]
        except Exception:
            # narwhals will raise on metadata-only frames
            return None

    def get_num_columns(self) -> int:
        return len(self.get_column_names())

    def get_column_names(self) -> list[str]:
        column_names = self.nw_schema.names()
        if INDEX_COLUMN_NAME in column_names:
            column_names.remove(INDEX_COLUMN_NAME)
        return column_names

    def get_unique_column_values(self, column: str) -> list[str | int | float]:
        frame = self.data.select(nw.col(column))
        if isinstance(frame, nw.LazyFrame):
            frame = frame.collect()
        try:
            return frame[column].unique().to_list()
        except BaseException:
            # Catch-all: some libraries like Polars have bugs and raise
            # BaseExceptions, which shouldn't crash the kernel
            # If an exception occurs, try converting to strings first
            return frame[column].cast(nw.String).unique().to_list()

    def get_sample_values(self, column: str) -> list[str | int | float]:
        # Skip lazy frames
        if is_narwhals_lazyframe(self.data):
            return []

        # Sample 3 values from the column
        SAMPLE_SIZE = 3
        try:
            from enum import Enum

            def to_primitive(value: Any) -> str | int | float:
                if isinstance(value, list):
                    return str([to_primitive(v) for v in value])
                elif isinstance(value, dict):
                    return str({k: to_primitive(v) for k, v in value.items()})
                elif isinstance(value, Enum):
                    return value.name
                elif isinstance(value, (float, int)):
                    return value
                return str(value)

            if self.data[column].dtype == nw.Datetime:
                # Drop timezone info for datetime columns
                # It's ok to drop timezone since these are just sample values
                # and not used for any calculations
                values = (
                    self.data[column]
                    .dt.replace_time_zone(None)
                    .head(SAMPLE_SIZE)
                    .to_list()
                )
            else:
                values = self.data[column].head(SAMPLE_SIZE).to_list()
            # Serialize values to primitives
            return [to_primitive(v) for v in values]
        except BaseException:
            # Catch-all: some libraries like Polars have bugs and raise
            # BaseExceptions, which shouldn't crash the kernel
            # May be metadata-only frame
            return []

    def sort_values(
        self, by: ColumnName, descending: bool
    ) -> TableManager[Any]:
        if is_narwhals_lazyframe(self.data):
            return self.with_new_data(
                self.data.sort(by, descending=descending, nulls_last=True)
            )
        else:
            return self.with_new_data(
                self.data.sort(by, descending=descending, nulls_last=True)
            )

    def __repr__(self) -> str:
        rows = self.get_num_rows(force=False)
        columns = self.get_num_columns()
        df_type = str(nw.get_native_namespace(self.data).__name__)
        if rows is None:
            return f"{df_type}: {columns:,} columns"
        return f"{df_type}: {rows:,} rows x {columns:,} columns"

    def _sanitize_table_value(self, value: Any) -> Any:
        """
        Sanitize a value for display in a table cell.

        Most values are unchanged, but some values are for better
        display such as Images.
        """
        if value is None:
            return None

        # Handle Pillow images
        if DependencyManager.pillow.imported():
            from PIL import Image

            if isinstance(value, Image.Image):
                return io_to_data_url(value, "image/png")
        return value
