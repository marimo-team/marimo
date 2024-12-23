# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from functools import cached_property
from typing import Any, Optional, Tuple, Union, cast

import narwhals.stable.v1 as nw
from narwhals.stable.v1.typing import IntoFrameT

from marimo._data.models import ColumnSummary, ExternalDataType
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
    format_value,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    TableManager,
)
from marimo._utils.narwhals_utils import (
    can_narwhalify,
    dataframe_to_csv,
    is_narwhals_integer_type,
    is_narwhals_string_type,
    is_narwhals_temporal_type,
    unwrap_py_scalar,
)


class NarwhalsTableManager(
    TableManager[Union[nw.DataFrame[IntoFrameT], nw.LazyFrame[IntoFrameT]]]
):
    type = "narwhals"

    @staticmethod
    def from_dataframe(data: IntoFrameT) -> NarwhalsTableManager[IntoFrameT]:
        return NarwhalsTableManager(nw.from_native(data, strict=True))

    def as_frame(self) -> nw.DataFrame[Any]:
        if isinstance(self.data, nw.LazyFrame):
            return self.data.collect()
        return self.data

    def with_new_data(
        self, data: nw.DataFrame[Any] | nw.LazyFrame[Any]
    ) -> TableManager[Any]:
        if type(self) is NarwhalsTableManager:
            return NarwhalsTableManager(data)
        # If this call comes from a subclass, we need to call the constructor
        # of the subclass with the native data.
        return self.__class__(data.to_native())

    def to_csv(
        self,
        format_mapping: Optional[FormatMapping] = None,
    ) -> bytes:
        _data = self.apply_formatting(format_mapping).as_frame()
        return dataframe_to_csv(_data).encode("utf-8")

    def to_json(self) -> bytes:
        csv_str = self.to_csv().decode("utf-8")
        import csv

        csv_reader = csv.DictReader(csv_str.splitlines())
        return json.dumps([row for row in csv_reader]).encode("utf-8")

    def apply_formatting(
        self, format_mapping: Optional[FormatMapping]
    ) -> NarwhalsTableManager[Any]:
        if not format_mapping:
            return self

        _data = self.as_frame().to_dict(as_series=False).copy()
        for col in _data.keys():
            if col in format_mapping:
                _data[col] = [
                    format_value(col, x, format_mapping) for x in _data[col]
                ]
        return NarwhalsTableManager(
            nw.from_dict(
                _data, native_namespace=nw.get_native_namespace(self.data)
            )
        )

    def supports_filters(self) -> bool:
        return True

    def select_rows(self, indices: list[int]) -> TableManager[Any]:
        df = self.as_frame()
        return self.with_new_data(df[indices])

    def select_columns(self, columns: list[str]) -> TableManager[Any]:
        return self.with_new_data(self.data.select(columns))

    def get_row_headers(
        self,
    ) -> list[str]:
        return []

    @staticmethod
    def is_type(value: Any) -> bool:
        return can_narwhalify(value)

    @cached_property
    def nw_schema(self) -> nw.Schema:
        return cast(nw.Schema, self.data.schema)

    def get_field_type(
        self, column_name: str
    ) -> Tuple[FieldType, ExternalDataType]:
        dtype = self.nw_schema[column_name]
        dtype_string = str(dtype)
        if is_narwhals_string_type(dtype):
            return ("string", dtype_string)
        elif dtype == nw.Boolean:
            return ("boolean", dtype_string)
        elif is_narwhals_integer_type(dtype):
            return ("integer", dtype_string)
        elif is_narwhals_temporal_type(dtype):
            return ("date", dtype_string)
        elif dtype == nw.Duration:
            return ("number", dtype_string)
        elif dtype.is_numeric():
            return ("number", dtype_string)
        else:
            return ("unknown", dtype_string)

    def take(self, count: int, offset: int) -> TableManager[Any]:
        if count < 0:
            raise ValueError("Count must be a positive integer")
        if offset < 0:
            raise ValueError("Offset must be a non-negative integer")
        return self.with_new_data(self.data[offset : offset + count])

    def search(self, query: str) -> TableManager[Any]:
        query = query.lower()

        expressions: list[Any] = []
        for column, dtype in self.nw_schema.items():
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
                or dtype == nw.Duration
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

    def get_summary(self, column: str) -> ColumnSummary:
        summary = self._get_summary_internal(column)
        for key, value in summary.__dict__.items():
            if value is not None:
                summary.__dict__[key] = unwrap_py_scalar(value)
        return summary

    def _get_summary_internal(self, column: str) -> ColumnSummary:
        # If column is not in the dataframe, return an empty summary
        if column not in self.nw_schema:
            return ColumnSummary()
        col = self.data[column]
        total = len(col)
        if is_narwhals_string_type(col.dtype):
            return ColumnSummary(
                total=total,
                nulls=col.null_count(),
                unique=col.n_unique(),
            )
        if col.dtype == nw.Boolean:
            return ColumnSummary(
                total=total,
                nulls=col.null_count(),
                true=cast(int, col.sum()),
                false=cast(int, total - col.sum()),
            )
        if col.dtype == nw.Date:
            return ColumnSummary(
                total=total,
                nulls=col.null_count(),
                min=col.min(),
                max=col.max(),
                mean=col.mean(),
                # Quantile not supported on date type
                # median=col.quantile(0.5, interpolation="nearest"),
            )
        if is_narwhals_temporal_type(col.dtype):
            return ColumnSummary(
                total=total,
                nulls=col.null_count(),
                min=col.min(),
                max=col.max(),
                mean=col.mean(),
                median=col.quantile(0.5, interpolation="nearest"),
                p5=col.quantile(0.05, interpolation="nearest"),
                p25=col.quantile(0.25, interpolation="nearest"),
                p75=col.quantile(0.75, interpolation="nearest"),
                p95=col.quantile(0.95, interpolation="nearest"),
            )
        if col.dtype == nw.Duration and isinstance(col.dtype, nw.Duration):
            unit_map = {
                "ms": (col.dt.total_milliseconds, "ms"),
                "ns": (col.dt.total_nanoseconds, "ns"),
                "us": (col.dt.total_microseconds, "μs"),
                "s": (col.dt.total_seconds, "s"),
            }
            method, unit = unit_map[col.dtype.time_unit]
            res = method()
            return ColumnSummary(
                total=total,
                nulls=col.null_count(),
                min=str(res.min()) + unit,
                max=str(res.max()) + unit,
                mean=str(res.mean()) + unit,
            )
        if (
            col.dtype == nw.List
            or col.dtype == nw.Struct
            or col.dtype == nw.Object
            or col.dtype == nw.Array
        ):
            return ColumnSummary(
                total=total,
                nulls=col.null_count(),
            )
        if col.dtype == nw.Unknown:
            return ColumnSummary(
                total=total,
                nulls=col.null_count(),
            )
        return ColumnSummary(
            total=total,
            nulls=col.null_count(),
            unique=(
                col.n_unique() if is_narwhals_integer_type(col.dtype) else None
            ),
            min=col.min(),
            max=col.max(),
            mean=col.mean(),
            median=col.quantile(0.5, interpolation="nearest"),
            std=col.std(),
            p5=col.quantile(0.05, interpolation="nearest"),
            p25=col.quantile(0.25, interpolation="nearest"),
            p75=col.quantile(0.75, interpolation="nearest"),
            p95=col.quantile(0.95, interpolation="nearest"),
        )

    def get_num_rows(self, force: bool = True) -> Optional[int]:
        # If force is true, collect the data and get the number of rows
        if force:
            return self.as_frame().shape[0]

        # When lazy, we don't know the number of rows
        if isinstance(self.data, nw.LazyFrame):
            return None

        # Otherwise, we can get the number of rows from the shape
        try:
            return self.data.shape[0]
        except Exception:
            # narwhals will raise on metadata-only frames
            return None

    def get_num_columns(self) -> int:
        return len(self.nw_schema.names())

    def get_column_names(self) -> list[str]:
        return self.nw_schema.names()

    def get_unique_column_values(self, column: str) -> list[str | int | float]:
        return self.data[column].unique().to_list()

    def get_sample_values(self, column: str) -> list[Any]:
        # Sample 3 values from the column
        SAMPLE_SIZE = 3
        try:
            return self.data[column].head(SAMPLE_SIZE).to_list()
        except Exception:
            # May be metadata-only frame
            return []

    def sort_values(
        self, by: ColumnName, descending: bool
    ) -> TableManager[Any]:
        if isinstance(self.data, nw.LazyFrame):
            return self.with_new_data(
                self.data.sort(by, descending=descending)
            )
        else:
            return self.with_new_data(
                self.data.sort(by, descending=descending)
            )

    def __repr__(self) -> str:
        rows = self.get_num_rows(force=False)
        columns = self.get_num_columns()
        df_type = str(nw.get_native_namespace(self.data).__name__)
        if rows is None:
            return f"{df_type}: {columns:,} columns"
        return f"{df_type}: {rows:,} rows x {columns:,} columns"
