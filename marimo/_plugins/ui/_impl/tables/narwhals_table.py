# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import functools
import io
import math
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, Optional, Union, cast

import msgspec
import narwhals.stable.v2 as nw
from narwhals.typing import IntoDataFrameT, IntoLazyFrameT

from marimo import _loggers
from marimo._data.models import BinValue, ColumnStats, ExternalDataType
from marimo._output.data.data import sanitize_json_bigint
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
    format_value,
)
from marimo._plugins.ui._impl.tables.selection import INDEX_COLUMN_NAME
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    FieldTypes,
    TableCell,
    TableCoordinate,
    TableManager,
)
from marimo._utils.narwhals_utils import (
    can_narwhalify,
    dataframe_to_csv,
    downgrade_narwhals_df_to_v1,
    is_narwhals_integer_type,
    is_narwhals_lazyframe,
    is_narwhals_string_type,
    is_narwhals_temporal_type,
    is_narwhals_time_type,
    unwrap_py_scalar,
)

if TYPE_CHECKING:
    from marimo._plugins.ui._impl.table import SortArgs

LOGGER = _loggers.marimo_logger()
UNSTABLE_API_WARNING = "`Series.hist` is being called from the stable API although considered an unstable feature."

# Standardize this across libraries
# It should match the table value as closely as possible
NAN_VALUE = "NaN"
POSITIVE_INF = str(float("inf"))
NEGATIVE_INF = str(float("-inf"))


class NarwhalsTableManager(
    TableManager[
        Union[nw.DataFrame[IntoDataFrameT], nw.LazyFrame[IntoLazyFrameT]]
    ]
):
    type = "narwhals"

    @staticmethod
    def from_dataframe(
        data: Union[IntoDataFrameT, IntoLazyFrameT],
    ) -> NarwhalsTableManager[IntoDataFrameT, IntoLazyFrameT]:
        return NarwhalsTableManager(nw.from_native(data, pass_through=False))

    def as_frame(self) -> nw.DataFrame[Any]:
        if is_narwhals_lazyframe(self.data):
            return self.data.collect()
        return self.data

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
        self,
        format_mapping: Optional[FormatMapping] = None,
        strict_json: bool = False,
        ensure_ascii: bool = True,
    ) -> str:
        del strict_json
        frame = self.apply_formatting(format_mapping).as_frame()
        return sanitize_json_bigint(
            frame.rows(named=True), ensure_ascii=ensure_ascii
        )

    def to_parquet(self) -> bytes:
        stream = io.BytesIO()
        self.as_frame().write_parquet(stream)
        return stream.getvalue()

    def apply_formatting(
        self, format_mapping: Optional[FormatMapping]
    ) -> NarwhalsTableManager[IntoDataFrameT, IntoLazyFrameT]:
        if not format_mapping:
            return self

        frame = self.as_frame()
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

    def select_rows(
        self, indices: list[int]
    ) -> TableManager[Union[IntoDataFrameT, IntoLazyFrameT]]:
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

    def get_row_headers(self) -> FieldTypes:
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
            if is_narwhals_lazyframe(result):
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
        value_counts: list[tuple[Any, int]] = []

        # NaNs and Infs serialize to null, which isn't distingushable from normal nulls
        # so instead we set to string values
        for row in result.rows():
            value = unwrap_py_scalar(row[0])
            count = int(unwrap_py_scalar(row[1]))
            if isinstance(value, float) and math.isnan(value):
                value = NAN_VALUE
            elif isinstance(value, float) and math.isinf(value) and value > 0:
                value = POSITIVE_INF
            elif isinstance(value, float) and math.isinf(value) and value < 0:
                value = NEGATIVE_INF
            value_counts.append((value, count))

        return value_counts

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
            if is_narwhals_lazyframe(self.data):
                # Lazyframes do not support slicing, https://github.com/narwhals-dev/narwhals/issues/2389
                # So we collect the first n rows
                data = self.data.head(offset + count).collect()
                return self.with_new_data(data[offset : offset + count])
            else:
                return self.with_new_data(self.data[offset : offset + count])

    def search(self, query: str) -> TableManager[Any]:
        query = query.lower()

        expressions: list[Any] = []
        for column, dtype in self.nw_schema.items():
            if column == INDEX_COLUMN_NAME:
                continue
            if is_narwhals_string_type(dtype):
                # Cast to string as pandas may fail for certain values
                expressions.append(
                    nw.col(column).cast(nw.String).str.contains(f"(?i){query}")
                )
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

            # Normalize values to Python builtins
            for field in msgspec.structs.fields(stats):
                value = getattr(stats, field.name)
                if value is not None:
                    setattr(stats, field.name, unwrap_py_scalar(value))

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

        # As of Oct 2025, pyarrow and ibis do not support quantiles
        # through narwhals
        supports_numeric_quantiles = (
            not frame.implementation.is_pyarrow()
            and not frame.implementation.is_ibis()
        )
        supports_temporal_quantiles = (
            not frame.implementation.is_pyarrow()
            and not frame.implementation.is_ibis()
        )

        quantile_interpolation: Literal["nearest", "linear"] = "nearest"
        if frame.implementation.is_duckdb():
            # As of Oct 2025, DuckDB does not support "nearest" interpolation
            quantile_interpolation = "linear"

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
            if supports_temporal_quantiles:
                exprs.update(
                    {
                        "mean": col.mean(),
                        "median": col.quantile(
                            0.5, interpolation=quantile_interpolation
                        ),
                        "p5": col.quantile(
                            0.05, interpolation=quantile_interpolation
                        ),
                        "p25": col.quantile(
                            0.25, interpolation=quantile_interpolation
                        ),
                        "p75": col.quantile(
                            0.75, interpolation=quantile_interpolation
                        ),
                        "p95": col.quantile(
                            0.95, interpolation=quantile_interpolation
                        ),
                    }
                )
        elif is_narwhals_integer_type(dtype):
            exprs.update(
                {
                    "unique": col.n_unique(),
                    "min": col.min(),
                    "max": col.max(),
                    "mean": col.mean(),
                    "std": col.std(),
                    "median": col.median(),
                }
            )
            if supports_numeric_quantiles:
                exprs.update(
                    {
                        "p5": col.quantile(
                            0.05, interpolation=quantile_interpolation
                        ),
                        "p25": col.quantile(
                            0.25, interpolation=quantile_interpolation
                        ),
                        "p75": col.quantile(
                            0.75, interpolation=quantile_interpolation
                        ),
                        "p95": col.quantile(
                            0.95, interpolation=quantile_interpolation
                        ),
                    }
                )
        elif dtype.is_numeric():
            exprs.update(
                {
                    "unique": col.n_unique(),
                    "min": col.min(),
                    "max": col.max(),
                    "mean": col.mean(),
                    "std": col.std(),
                    "median": col.median(),
                }
            )
            if supports_numeric_quantiles:
                exprs.update(
                    {
                        "p5": col.quantile(
                            0.05, interpolation=quantile_interpolation
                        ),
                        "p25": col.quantile(
                            0.25, interpolation=quantile_interpolation
                        ),
                        "p75": col.quantile(
                            0.75, interpolation=quantile_interpolation
                        ),
                        "p95": col.quantile(
                            0.95, interpolation=quantile_interpolation
                        ),
                    }
                )

        stats = frame.select(**exprs)
        stats_dict = stats.collect().rows(named=True)[0]

        # Maybe add units to the stats
        for key, value in stats_dict.items():
            if key in units:
                stats_dict[key] = f"{value} {units[key]}"

        # Maybe coerce null count to int
        if stats_dict["nulls"] is not None:
            stats_dict["nulls"] = int(stats_dict["nulls"])

        return ColumnStats(**stats_dict)

    def get_bin_values(self, column: str, num_bins: int) -> list[BinValue]:
        if column not in self.nw_schema:
            LOGGER.error(f"Column {column} not found in schema")
            return []

        dtype = self.nw_schema[column]

        if dtype.is_temporal():
            return self._get_bin_values_temporal(column, dtype, num_bins)

        if not dtype.is_numeric():
            return []

        # Downgrade to v1 since v2 does not support the hist() method yet
        downgraded_df = downgrade_narwhals_df_to_v1(self.as_frame())
        col = downgraded_df.get_column(column)

        # If the column is decimal, we need to convert it to float
        if dtype.is_decimal():
            import narwhals.stable.v1 as nw1

            col = col.cast(nw1.Float64)

        bin_start = col.min()
        bin_values: list[BinValue] = []

        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message=UNSTABLE_API_WARNING, category=UserWarning
            )
            hist = col.hist(bin_count=num_bins)

        for bin_end, count in hist.iter_rows(named=False):
            bin_values.append(
                BinValue(bin_start=bin_start, bin_end=bin_end, count=count)
            )
            bin_start = bin_end
        return bin_values

    def _get_bin_values_temporal(
        self, column: str, dtype: Any, num_bins: int
    ) -> list[BinValue]:
        """
        Get bin values for a temporal column.

        nw.hist does not support temporal columns, so we convert to numeric
        and then convert back to temporal values.
        """
        # Downgrade to v1 since v2 does not support the hist() method yet
        downgraded_df = downgrade_narwhals_df_to_v1(self.as_frame())
        col = downgraded_df.get_column(column)

        if dtype == nw.Time:
            # Convert to timestamp in ms
            col_in_ms = (
                col.dt.hour().cast(nw.Int64) * 3600000
                + col.dt.minute().cast(nw.Int64) * 60000
                + col.dt.second().cast(nw.Int64) * 1000
                + col.dt.microsecond().cast(nw.Int64) // 1000
            )
        else:
            col_in_ms = col.dt.timestamp(time_unit="ms")

        import warnings

        with warnings.catch_warnings():
            warnings.filterwarnings(
                "ignore", message=UNSTABLE_API_WARNING, category=UserWarning
            )
            hist = col_in_ms.hist(bin_count=num_bins)

        bin_values = []
        ms_time = 1000

        bin_start = col.min()

        for bin_end, count in hist.iter_rows(named=False):
            if dtype == nw.Time:
                hours = bin_end // 3600000
                minutes = (bin_end % 3600000) // 60000
                seconds = (bin_end % 60000) // 1000
                microseconds = (bin_end % 1000) * 1000
                bin_end = datetime.time(
                    int(hours), int(minutes), int(seconds), int(microseconds)
                )
            elif dtype == nw.Date:
                # Use timedelta to handle dates before Unix epoch (1970)
                # which cause OSError on Windows with fromtimestamp
                try:
                    bin_end = datetime.date.fromtimestamp(bin_end / ms_time)
                except (OSError, OverflowError, ValueError):
                    # Fall back to timedelta calculation for old dates
                    epoch = datetime.datetime(
                        1970, 1, 1, tzinfo=datetime.timezone.utc
                    )
                    bin_end_dt = epoch + datetime.timedelta(
                        seconds=bin_end / ms_time
                    )
                    bin_end = bin_end_dt.date()
            else:
                # Use timedelta to handle datetimes before Unix epoch (1970)
                # which cause OSError on Windows with fromtimestamp
                try:
                    bin_end = datetime.datetime.fromtimestamp(
                        bin_end / ms_time
                    )
                except (OSError, OverflowError, ValueError):
                    # Fall back to timedelta calculation for old dates
                    epoch = datetime.datetime(
                        1970, 1, 1, tzinfo=datetime.timezone.utc
                    )
                    bin_end = epoch + datetime.timedelta(
                        seconds=bin_end / ms_time
                    )
                    # Remove timezone to match fromtimestamp behavior
                    bin_end = bin_end.replace(tzinfo=None)

            # Only append if the count is greater than 0
            if count > 0:
                bin_values.append(
                    BinValue(bin_start=bin_start, bin_end=bin_end, count=count)
                )
            bin_start = bin_end
        return bin_values

    def _sample_indexes(self, size: int, total: int) -> list[int]:
        """Sample evenly from a list of length `total`"""
        if total <= size:
            return list(range(total))
        return [round(i * (total - 1) / (size - 1)) for i in range(size)]

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
        if is_narwhals_lazyframe(frame):
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

    def sort_values(self, by: list[SortArgs]) -> TableManager[Any]:
        if not by:
            return self

        # Extract columns and descending flags for Narwhals/Polars
        columns = [sort_arg.by for sort_arg in by]
        descending = [sort_arg.descending for sort_arg in by]

        return self.with_new_data(
            self.data.sort(columns, descending=descending, nulls_last=True)
        )

    def __repr__(self) -> str:
        rows = self.get_num_rows(force=False)
        columns = self.get_num_columns()
        df_type = str(nw.get_native_namespace(self.data).__name__)
        if rows is None:
            return f"{df_type}: {columns:,} columns"
        return f"{df_type}: {rows:,} rows x {columns:,} columns"
