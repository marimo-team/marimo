# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Optional, Tuple

from marimo._data.models import ColumnSummary, ExternalDataType
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
    format_value,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    FieldTypes,
    TableManager,
    TableManagerFactory,
)


class PandasTableManagerFactory(TableManagerFactory):
    @staticmethod
    def package_name() -> str:
        return "pandas"

    @staticmethod
    def create() -> type[TableManager[Any]]:
        import pandas as pd

        class PandasTableManager(TableManager[pd.DataFrame]):
            type = "pandas"

            def to_csv(
                self, format_mapping: Optional[FormatMapping] = None
            ) -> bytes:
                has_headers = len(self.get_row_headers()) > 0
                if format_mapping:
                    _data = self.apply_formatting(format_mapping)
                    return _data.to_csv(
                        index=has_headers,
                    ).encode("utf-8")
                return self.data.to_csv(index=has_headers).encode("utf-8")

            def to_json(self) -> bytes:
                return self.data.to_json(orient="records").encode("utf-8")

            def apply_formatting(
                self, format_mapping: FormatMapping
            ) -> pd.DataFrame:
                _data = self.data.copy()
                for col in _data.columns:
                    if col in format_mapping:
                        _data[col] = _data[col].apply(
                            lambda x, col=col: format_value(  # type: ignore
                                col, x, format_mapping
                            )
                        )
                return _data

            def supports_filters(self) -> bool:
                return True

            def select_rows(
                self, indices: list[int]
            ) -> TableManager[pd.DataFrame]:
                return PandasTableManager(self.data.iloc[indices])

            def select_columns(
                self, columns: list[str]
            ) -> TableManager[pd.DataFrame]:
                return PandasTableManager(self.data[columns])

            def get_row_headers(
                self,
            ) -> list[str]:
                return PandasTableManager._get_row_headers_for_index(
                    self.data.index
                )

            @staticmethod
            def is_type(value: Any) -> bool:
                return isinstance(value, pd.DataFrame)

            @staticmethod
            def _get_row_headers_for_index(
                index: pd.Index[Any],
            ) -> list[str]:
                # Ignore if it's the default index with no name
                if index.name is None and isinstance(index, pd.RangeIndex):
                    return []

                if isinstance(index, pd.MultiIndex):
                    # recurse
                    headers: list[Any] = []
                    for i in range(index.nlevels):
                        headers.extend(
                            PandasTableManager._get_row_headers_for_index(
                                index.get_level_values(i)
                            )
                        )
                    return headers

                return [str(index.name or "")]

            def get_field_types(self) -> FieldTypes:
                return {
                    column: PandasTableManager._get_field_type(
                        self.data[column]
                    )
                    for column in self.data.columns
                }

            def limit(self, num: int) -> PandasTableManager:
                if num < 0:
                    raise ValueError("Limit must be a positive integer")
                return PandasTableManager(self.data.head(num))

            def search(self, query: str) -> TableManager[Any]:
                query = query.lower()

                def contains_query(series: pd.Series[Any]) -> pd.Series[bool]:
                    def search(s: Any) -> bool:
                        return query in str(s).lower()

                    return series.map(search)

                mask = self.data.apply(contains_query)
                return PandasTableManager(self.data.loc[mask.any(axis=1)])

            @staticmethod
            def _get_field_type(
                series: pd.Series[Any] | pd.DataFrame,
            ) -> Tuple[FieldType, ExternalDataType]:
                # If a df has duplicate columns, it won't be a series, but
                # a dataframe. In this case, we take the dtype of the columns
                if isinstance(series, pd.DataFrame):
                    dtype = str(series.columns.dtype)
                else:
                    dtype = str(series.dtype)

                if dtype.startswith("interval"):
                    return ("string", dtype)
                if dtype.startswith("int") or dtype.startswith("uint"):
                    return ("integer", dtype)
                if dtype.startswith("float"):
                    return ("number", dtype)
                if dtype == "object":
                    return ("string", dtype)
                if dtype == "bool":
                    return ("boolean", dtype)
                if dtype == "datetime64[ns]":
                    return ("date", dtype)
                if dtype == "timedelta64[ns]":
                    return ("string", dtype)
                if dtype == "category":
                    return ("string", dtype)
                if dtype.startswith("complex"):
                    return ("unknown", dtype)
                return ("unknown", dtype)

            def get_summary(self, column: str) -> ColumnSummary:
                # If column is not in the dataframe, return an empty summary
                if column not in self.data.columns:
                    return ColumnSummary()
                col = self.data[column]

                if col.dtype == "object":
                    try:
                        return ColumnSummary(
                            total=col.count(),
                            nulls=col.isnull().sum(),
                            unique=col.nunique(),
                        )
                    except TypeError:
                        # If the column is not hashable,
                        # we can't get the unique values
                        return ColumnSummary(
                            total=col.count(),
                            nulls=col.isnull().sum(),
                        )

                if col.dtype == "bool":
                    return ColumnSummary(
                        total=col.count(),
                        nulls=col.isnull().sum(),
                        true=col.sum(),
                        false=col.count() - col.sum(),
                    )

                if col.dtype == "datetime64[ns]":
                    return ColumnSummary(
                        total=col.count(),
                        nulls=col.isnull().sum(),
                        min=col.min(),
                        max=col.max(),
                        mean=col.mean(),
                        median=col.median(),
                        p5=col.quantile(0.05),
                        p25=col.quantile(0.25),
                        p75=col.quantile(0.75),
                        p95=col.quantile(0.95),
                    )

                return ColumnSummary(
                    total=col.count(),
                    nulls=col.isnull().sum(),
                    min=col.min(),
                    max=col.max(),
                    mean=col.mean(),
                    median=col.median(),
                    std=col.std(),
                    p5=col.quantile(0.05),
                    p25=col.quantile(0.25),
                    p75=col.quantile(0.75),
                    p95=col.quantile(0.95),
                )

            def get_num_rows(self, force: bool = True) -> int:
                del force
                return self.data.shape[0]

            def get_num_columns(self) -> int:
                return self.data.shape[1]

            def get_column_names(self) -> list[str]:
                return self.data.columns.tolist()

            def get_unique_column_values(
                self, column: str
            ) -> list[str | int | float]:
                return self.data[column].unique().tolist()  # type: ignore[no-any-return]

            def sort_values(
                self, by: ColumnName, descending: bool
            ) -> PandasTableManager:
                sorted_data = self.data.sort_values(
                    by, ascending=not descending
                )
                return PandasTableManager(sorted_data)

        return PandasTableManager
