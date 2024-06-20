# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._data.models import ColumnSummary
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

            def to_csv(self) -> bytes:
                return self.data.to_csv(
                    index=False,
                ).encode("utf-8")

            def to_json(self) -> bytes:
                return self.data.to_json(orient="records").encode("utf-8")

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
            ) -> list[tuple[str, list[str | int | float]]]:
                return PandasTableManager._get_row_headers_for_index(
                    self.data.index
                )

            @staticmethod
            def is_type(value: Any) -> bool:
                return isinstance(value, pd.DataFrame)

            @staticmethod
            def _get_row_headers_for_index(
                index: pd.Index[Any],
            ) -> list[tuple[str, list[str | int | float]]]:
                if isinstance(index, pd.RangeIndex):
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

                # we only care about the index if it has a name
                # or if it is type 'object'
                # otherwise, it may look like meaningless number
                if isinstance(index, pd.Index):
                    dtype = str(index.dtype)
                    if (
                        index.name
                        or dtype == "object"
                        or dtype == "string"
                        or dtype == "category"
                    ):
                        name = str(index.name) if index.name else ""
                        return [(name, index.tolist())]  # type: ignore[list-item]

                if isinstance(index, pd.DatetimeIndex):
                    # Format to Y-m-d if the time is 00:00:00
                    formatted: list[str] = index.strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ).tolist()
                    if all(time.endswith(" 00:00:00") for time in formatted):
                        return [
                            (
                                index.name or "",
                                index.strftime("%Y-%m-%d").tolist(),
                            )
                        ]
                    return [
                        (
                            index.name or "",
                            index.strftime("%Y-%m-%d %H:%M:%S").tolist(),
                        )
                    ]

                if isinstance(index, pd.TimedeltaIndex):
                    return [
                        (
                            index.name or "",
                            index.astype(str).tolist(),
                        )
                    ]

                return []

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
            ) -> FieldType:
                # If a df has duplicate columns, it won't be a series, but
                # a dataframe. In this case, we take the dtype of the columns
                if isinstance(series, pd.DataFrame):
                    dtype = str(series.columns.dtype)
                else:
                    dtype = str(series.dtype)

                if dtype.startswith("interval"):
                    return "string"
                if dtype.startswith("int") or dtype.startswith("uint"):
                    return "integer"
                if dtype.startswith("float"):
                    return "number"
                if dtype == "object":
                    return "string"
                if dtype == "bool":
                    return "boolean"
                if dtype == "datetime64[ns]":
                    return "date"
                if dtype == "timedelta64[ns]":
                    return "string"
                if dtype == "category":
                    return "string"
                if dtype.startswith("complex"):
                    return "unknown"
                return "unknown"

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
