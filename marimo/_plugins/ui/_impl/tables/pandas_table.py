# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import cached_property
from typing import Any, Optional, Tuple

import narwhals.stable.v1 as nw

from marimo._data.models import ExternalDataType
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


class PandasTableManagerFactory(TableManagerFactory):
    @staticmethod
    def package_name() -> str:
        return "pandas"

    @staticmethod
    def create() -> type[TableManager[Any]]:
        import pandas as pd

        class PandasTableManager(NarwhalsTableManager[pd.DataFrame]):
            type = "pandas"

            def __init__(self, data: pd.DataFrame) -> None:
                self._original_data = data
                super().__init__(nw.from_native(data))

            @cached_property
            def schema(self) -> pd.Series[Any]:
                return self._original_data.dtypes  # type: ignore

            # We override narwhals's to_csv to handle pandas
            # headers
            def to_csv(
                self, format_mapping: Optional[FormatMapping] = None
            ) -> bytes:
                has_headers = len(self.get_row_headers()) > 0
                # Pandas omits H:M:S for datetimes when H:M:S is identically
                # 0; this doesn't play well with our frontend table component,
                # so we use an explicit date format.
                return (
                    self.apply_formatting(format_mapping)
                    ._original_data.to_csv(
                        # By adding %H:%M:%S and %z, we ensure that the
                        # datetime is displayed in the frontend with the
                        # correct timezone.
                        index=has_headers,
                        date_format="%Y-%m-%d %H:%M:%S%z",
                    )
                    .encode("utf-8")
                )

            def to_json(self) -> bytes:
                return self._original_data.to_json(orient="records").encode(
                    "utf-8"
                )

            def apply_formatting(
                self, format_mapping: Optional[FormatMapping]
            ) -> PandasTableManager:
                if not format_mapping:
                    return self

                _data = self._original_data.copy()
                for col in _data.columns:
                    if col in format_mapping:
                        _data[col] = _data[col].apply(
                            lambda x, col=col: format_value(  # type: ignore
                                col, x, format_mapping
                            )
                        )
                return PandasTableManager(_data)

            # We override the default implementation to use pandas
            # headers
            def get_row_headers(
                self,
            ) -> list[str]:
                return PandasTableManager._get_row_headers_for_index(
                    self._original_data.index
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

            # We override the default implementation to use pandas's
            # internal fields since they get displayed in the UI.
            def get_field_type(
                self, column_name: str
            ) -> Tuple[FieldType, ExternalDataType]:
                dtype = self.schema[column_name]
                # If a df has duplicate columns, it won't be a series, but
                # a dataframe. In this case, we take the dtype of the columns
                if isinstance(dtype, pd.DataFrame):
                    dtype = str(dtype.columns.dtype)
                else:
                    dtype = str(dtype)

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
                    return ("datetime", dtype)
                if dtype == "date":
                    return ("date", dtype)
                if dtype == "time":
                    return ("time", dtype)
                if dtype == "timedelta64[ns]":
                    return ("string", dtype)
                if dtype == "category":
                    return ("string", dtype)
                if dtype.startswith("complex"):
                    return ("unknown", dtype)
                return ("unknown", dtype)

            # We override the default since narwhals returns a Series
            def get_unique_column_values(
                self, column: str
            ) -> list[str | int | float]:
                return self._original_data[column].unique().tolist()  # type: ignore[return-value,no-any-return]

        return PandasTableManager
