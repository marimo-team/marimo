# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import io
from functools import cached_property
from typing import Any, Optional

import narwhals.stable.v1 as nw

from marimo import _loggers
from marimo._data.models import ExternalDataType
from marimo._output.data.data import sanitize_json_bigint
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
    format_value,
)
from marimo._plugins.ui._impl.tables.narwhals_table import NarwhalsTableManager
from marimo._plugins.ui._impl.tables.selection import INDEX_COLUMN_NAME
from marimo._plugins.ui._impl.tables.table_manager import (
    FieldType,
    TableManager,
    TableManagerFactory,
)

LOGGER = _loggers.marimo_logger()


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
                self._original_data = self._handle_multi_col_indexes(data)
                super().__init__(nw.from_native(self._original_data))

            @cached_property
            def schema(self) -> pd.Series[Any]:
                return self._original_data.dtypes  # type: ignore

            # We override narwhals's to_csv_str to handle pandas
            # headers
            def to_csv_str(
                self, format_mapping: Optional[FormatMapping] = None
            ) -> str:
                has_headers = len(self.get_row_headers()) > 0
                # Pandas omits H:M:S for datetimes when H:M:S is identically
                # 0; this doesn't play well with our frontend table component,
                # so we use an explicit date format.
                return self.apply_formatting(
                    format_mapping
                )._original_data.to_csv(
                    # By adding %H:%M:%S and %z, we ensure that the
                    # datetime is displayed in the frontend with the
                    # correct timezone.
                    index=has_headers,
                    date_format="%Y-%m-%d %H:%M:%S%z",
                )

            def to_json_str(
                self, format_mapping: Optional[FormatMapping] = None
            ) -> str:
                from pandas.api.types import (
                    is_complex_dtype,
                    is_object_dtype,
                    is_timedelta64_dtype,
                    is_timedelta64_ns_dtype,
                )

                _data = self.apply_formatting(format_mapping)._original_data
                result = _data.copy()  # to avoid SettingWithCopyWarning
                try:
                    for col in result.columns:
                        dtype = result[col].dtype
                        # Complex dtypes are converted to {'imag': num, 'real': num} by default
                        # We want to preserve the original display
                        if is_complex_dtype(dtype):
                            result[col] = result[col].apply(str)
                        if is_timedelta64_dtype(
                            dtype
                        ) or is_timedelta64_ns_dtype(dtype):
                            result[col] = result[col].apply(str)
                        if is_object_dtype(dtype):
                            result[col] = result[col].apply(
                                self._sanitize_table_value
                            )

                except Exception as e:
                    LOGGER.error(
                        "Error handling complex or timedelta64 dtype",
                        exc_info=e,
                    )
                    return sanitize_json_bigint(
                        result.to_json(
                            orient="records",
                            date_format="iso",
                            default_handler=str,
                        )
                    )

                # Flatten row multi-index
                if isinstance(result.index, pd.MultiIndex) or (
                    isinstance(result.index, pd.Index)
                    and not isinstance(result.index, pd.RangeIndex)
                ):
                    unnamed_indexes = result.index.names[0] is None
                    index_levels = result.index.nlevels
                    result = result.reset_index()

                    if unnamed_indexes:
                        # We could rename, but it doesn't work cleanly for multi-col indexes
                        result.columns = pd.Index(
                            [""] + list(result.columns[1:])
                        )

                        if index_levels > 1:
                            LOGGER.warning(
                                "Indexes with more than one level are not supported properly, call reset_index() to flatten"
                            )

                return sanitize_json_bigint(
                    result.to_json(
                        orient="records",
                        date_format="iso",
                        default_handler=str,
                    )
                )

            def to_arrow_ipc(self) -> bytes:
                out = io.BytesIO()
                self._original_data.to_feather(out, compression="uncompressed")
                return out.getvalue()

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

            def _handle_multi_col_indexes(
                self, data: pd.DataFrame
            ) -> pd.DataFrame:
                is_multi_col_index = isinstance(data.columns, pd.MultiIndex)
                # When in a table with selection, narwhals will convert the columns to a tuple
                is_multi_col_table = (
                    INDEX_COLUMN_NAME in data.columns
                    and len(data.columns) > 1
                    and any(isinstance(col, tuple) for col in data.columns)
                )

                # Convert multi-index or tuple columns to comma-separated strings
                if is_multi_col_index or is_multi_col_table:
                    data_copy = data.copy()
                    LOGGER.info(
                        "Multi-column indexes are not supported, converting to single index"
                    )
                    _cols = data_copy.columns
                    if INDEX_COLUMN_NAME in data_copy.columns:
                        data_copy.columns = pd.Index(
                            [INDEX_COLUMN_NAME]
                            + [
                                ",".join([str(lev) for lev in c])
                                for c in _cols[1:]
                            ]
                        )
                    else:
                        data_copy.columns = pd.Index(
                            [",".join([str(lev) for lev in c]) for c in _cols]
                        )
                    return data_copy

                return data

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
            ) -> tuple[FieldType, ExternalDataType]:
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
