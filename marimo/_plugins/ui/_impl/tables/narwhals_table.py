# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Optional, Union, cast

import narwhals.stable.v1 as nw

from marimo._data.models import ColumnSummary
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
    format_value,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldTypes,
    TableManager,
)
from marimo._utils.narwhals_utils import (
    can_narwhalify,
    is_narwhals_integer_type,
    is_narwhals_string_type,
    is_narwhals_temporal_type,
)

Frame = Union[nw.DataFrame[Any], nw.LazyFrame[Any]]

if TYPE_CHECKING:
    from narwhals.typing import IntoFrame


class NarwhalsTableManager(TableManager[Frame]):
    type = "narwhals"

    @staticmethod
    def from_dataframe(data: IntoFrame) -> NarwhalsTableManager:
        return NarwhalsTableManager(nw.from_native(data, strict=True))

    def as_frame(self) -> nw.DataFrame[Any]:
        if isinstance(self.data, nw.LazyFrame):
            return self.data.collect()
        return self.data

    def to_csv(
        self,
        format_mapping: Optional[FormatMapping] = None,
    ) -> bytes:
        _data = (
            self.apply_formatting(format_mapping)
            if format_mapping
            else self.as_frame()
        )
        csv_str = _data.write_csv()
        if isinstance(csv_str, str):
            return csv_str.encode("utf-8")
        return cast(bytes, csv_str)

    def to_json(self) -> bytes:
        csv_str = self.as_frame().write_csv()
        import csv

        csv_reader = csv.DictReader(csv_str.splitlines())
        return json.dumps([row for row in csv_reader]).encode("utf-8")

    def apply_formatting(
        self, format_mapping: FormatMapping
    ) -> nw.DataFrame[Any]:
        _data = self.as_frame().to_dict(as_series=False).copy()
        for col in _data.keys():
            if col in format_mapping:
                _data[col] = [
                    format_value(col, x, format_mapping) for x in _data[col]
                ]
        return nw.from_dict(
            _data, native_namespace=nw.get_native_namespace(self.data)
        )

    def supports_filters(self) -> bool:
        return True

    def select_rows(self, indices: list[int]) -> TableManager[Frame]:
        df = self.as_frame()
        return NarwhalsTableManager(df[indices])

    def select_columns(self, columns: list[str]) -> TableManager[Frame]:
        return NarwhalsTableManager(self.data.select(columns))

    def get_row_headers(
        self,
    ) -> list[str]:
        return []

    @staticmethod
    def is_type(value: Any) -> bool:
        return can_narwhalify(value)

    def get_field_types(self) -> FieldTypes:
        field_types: FieldTypes = {}
        for column, dtype in self.data.schema.items():
            dtype_string = str(dtype)
            if is_narwhals_string_type(dtype):
                field_types[column] = ("string", dtype_string)
            elif dtype == nw.Boolean:
                field_types[column] = ("boolean", dtype_string)
            elif is_narwhals_integer_type(dtype):
                field_types[column] = ("integer", dtype_string)
            elif is_narwhals_temporal_type(dtype):
                field_types[column] = ("date", dtype_string)
            elif dtype.is_numeric():
                field_types[column] = ("number", dtype_string)
            else:
                field_types[column] = ("unknown", dtype_string)

        return field_types

    def take(self, count: int, offset: int) -> NarwhalsTableManager:
        if count < 0:
            raise ValueError("Count must be a positive integer")
        if offset < 0:
            raise ValueError("Offset must be a non-negative integer")
        return NarwhalsTableManager(self.data[offset:count])

    def search(self, query: str) -> TableManager[Any]:
        query = query.lower()

        expressions: list[Any] = []
        for column in self.data.columns:
            dtype = self.data[column].dtype
            if dtype == nw.String:
                expressions.append(nw.col(column).str.contains(query))
            # TODO: Unsupported by narwhals
            # elif dtype == nw.List(nw.String):
            #     expressions.append(
            #         nw.col(column).cast(nw.String).str.contains(query)
            #     )
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

    def get_summary(self, column: str) -> ColumnSummary:
        summary = self._get_summary_internal(column)
        for key, value in summary.__dict__.items():
            if value is not None:
                summary.__dict__[key] = _maybe_convert_as_py(value)
        return summary

    def _get_summary_internal(self, column: str) -> ColumnSummary:
        # If column is not in the dataframe, return an empty summary
        if column not in self.data.columns:
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
                # TODO: Implement median not in narwhals
                # median=col.median(),
            )
        if is_narwhals_temporal_type(col.dtype):
            return ColumnSummary(
                total=total,
                nulls=col.null_count(),
                min=col.min(),
                max=col.max(),
                mean=col.mean(),
                # TODO: Implement median not in narwhals
                # median=col.median(),
                p5=col.quantile(0.05, interpolation="nearest"),
                p25=col.quantile(0.25, interpolation="nearest"),
                p75=col.quantile(0.75, interpolation="nearest"),
                p95=col.quantile(0.95, interpolation="nearest"),
            )
        if col.dtype == nw.List:
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
            unique=col.n_unique()
            if is_narwhals_integer_type(col.dtype)
            else None,
            min=col.min(),
            max=col.max(),
            mean=col.mean(),
            # TODO: Implement median not in narwhals
            # median=col.median(),
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
        return self.data.shape[0]

    def get_num_columns(self) -> int:
        return len(self.data.columns)

    def get_column_names(self) -> list[str]:
        return self.data.columns

    def get_unique_column_values(self, column: str) -> list[str | int | float]:
        return self.data[column].unique().to_list()

    def sort_values(
        self, by: ColumnName, descending: bool
    ) -> NarwhalsTableManager:
        sorted_data = self.data.sort(by, descending=descending)
        return NarwhalsTableManager(sorted_data)

    def __repr__(self) -> str:
        rows = self.get_num_rows(force=False)
        columns = self.get_num_columns()
        df_type = str(nw.get_native_namespace(self.data).__name__)
        if rows is None:
            return f"{df_type}: {columns:,} columns"
        return f"{df_type}: {rows:,} rows x {columns:,} columns"


# pyarrow use wrapper types for primitives
# so we need to convert to the primitive type
def _maybe_convert_as_py(value: Any) -> Any:
    if hasattr(value, "to_pylist"):
        return value.to_pylist()
    if hasattr(value, "as_py"):
        return value.as_py()
    return value
