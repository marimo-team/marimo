# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import functools
import io
from functools import cached_property
from typing import TYPE_CHECKING, Any, Optional

import narwhals.stable.v2 as nw

from marimo import _loggers
from marimo._data.models import ExternalDataType
from marimo._dependencies.dependencies import DependencyManager
from marimo._output.data.data import sanitize_json_bigint
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
    format_value,
)
from marimo._plugins.ui._impl.tables.narwhals_table import NarwhalsTableManager
from marimo._plugins.ui._impl.tables.selection import INDEX_COLUMN_NAME
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    FieldTypes,
    TableManager,
    TableManagerFactory,
)

if TYPE_CHECKING:
    import pandas as pd

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from pandas._typing import DtypeObj


def _trivial_range_index(index: pd.Index) -> bool:
    import pandas as pd

    # A trivial index is an unnamed RangeIndex (0, 1, 2, ...)
    return isinstance(index, pd.RangeIndex) and index.name is None


def _resolve_index_column_conflicts(df: pd.DataFrame) -> pd.DataFrame:
    """Rename index names that conflict with column names by appending '_index'.

    Avoids 'ValueError: cannot insert x, already exists' on reset_index().
    Modifies the DataFrame in-place and returns it.
    """
    import pandas as pd

    index_names = df.index.names
    conflicting_names = set(index_names) & set(df.columns)
    if not conflicting_names:
        return df

    new_names: list[str] = []
    for name in index_names:
        if name in conflicting_names:
            new_names.append(f"{name}_index")
        else:
            new_names.append(str(name))

    if isinstance(df.index, pd.MultiIndex):
        df.index = df.index.set_names(new_names)
    else:
        df.index = df.index.rename(new_names[0])

    return df


def _maybe_convert_geopandas_to_pandas(data: pd.DataFrame) -> pd.DataFrame:
    # Convert to pandas dataframe since geopandas will fail on
    # certain operations (like to_json(orient="records"))
    if DependencyManager.geopandas.imported():
        import geopandas as gpd  # type: ignore
        import pandas as pd

        if isinstance(data, gpd.GeoDataFrame):
            return pd.DataFrame(data)
    return data


class PandasTableManagerFactory(TableManagerFactory):
    @staticmethod
    def package_name() -> str:
        return "pandas"

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def create() -> type[TableManager[Any]]:
        import pandas as pd

        class PandasTableManager(NarwhalsTableManager[pd.DataFrame, Any]):
            type = "pandas"

            def __init__(self, data: pd.DataFrame) -> None:
                data = _maybe_convert_geopandas_to_pandas(data)
                data = self._handle_multi_col_indexes(data)
                data = self._handle_non_string_column_names(data)
                self._original_data = data
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
                return self.apply_formatting(
                    format_mapping
                )._original_data.to_csv(index=has_headers)

            def to_json_str(
                self,
                format_mapping: Optional[FormatMapping] = None,
                strict_json: bool = False,
                ensure_ascii: bool = True,
            ) -> str:
                def to_json(
                    result: pd.DataFrame,
                ) -> list[dict[str, Any]] | str:
                    """
                    to_dict preserves nans, infs and is more accurate than to_json.
                    By default, we use to_dict unless strict_json is True
                    """
                    if strict_json:
                        try:
                            json_str = result.to_json(
                                orient="records",
                                date_format="iso",
                                default_handler=str,
                            )
                            assert json_str is not None
                            return json_str
                        except Exception as e:
                            LOGGER.warning(
                                "Error serializing to JSON. Falling back to to_dict. Error: %s",
                                e,
                            )
                    return result.to_dict(orient="records")  # type: ignore

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
                            # Check if column contains date objects (not datetime), and convert them to string
                            # Typically, this will change to YYYY-MM-DD format
                            inferred_dtype = self._infer_dtype(col)
                            if inferred_dtype == "date":
                                result[col] = result[col].apply(str)

                            # Cast bytes to string to avoid overflow error
                            if self._infer_dtype(col) == "bytes":
                                result[col] = result[col].apply(str)

                except Exception as e:
                    LOGGER.error(
                        "Error handling complex or timedelta64 dtype",
                        exc_info=e,
                    )
                    return sanitize_json_bigint(
                        to_json(result), ensure_ascii=ensure_ascii
                    )

                # Flatten row multi-index
                # Reset index if it's a MultiIndex or a named Index
                # (including named RangeIndex, which pandas 3.0 uses for sequential integers)
                # Only skip reset for unnamed default RangeIndex (0, 1, 2, ...)
                if isinstance(result.index, pd.MultiIndex) or (
                    isinstance(result.index, pd.Index)
                    and not _trivial_range_index(result.index)
                ):
                    unnamed_indexes = any(
                        idx is None for idx in result.index.names
                    )

                    index_levels = result.index.nlevels

                    _resolve_index_column_conflicts(result)
                    index_names = result.index.names

                    result = result.reset_index()

                    if unnamed_indexes:
                        # After reset_index, the index is converted to a column
                        # We need to rename the new columns to empty strings
                        # And it must be unique for each column
                        # TODO: On the frontend this still displays the original index, not the renamed one
                        empty_name = ""
                        for i, idx_name in enumerate(index_names):
                            if idx_name is None:
                                result.columns.values[i] = empty_name
                                empty_name += " "

                        if index_levels > 1:
                            LOGGER.warning(
                                "Indexes with more than one level are not well supported, call reset_index() or use mo.plain(df)"
                            )

                return sanitize_json_bigint(
                    to_json(result), ensure_ascii=ensure_ascii
                )

            def _infer_dtype(self, column: ColumnName) -> str:
                # Typically, pandas dtypes returns a generic dtype
                # This provides more specific dtypes like bytes, floating, categorical, etc.
                return pd.api.types.infer_dtype(self._original_data[column])

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

            @classmethod
            def _handle_multi_col_indexes(
                cls, data: pd.DataFrame
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

            @classmethod
            def _handle_non_string_column_names(
                cls, data: pd.DataFrame
            ) -> pd.DataFrame:
                if not isinstance(data.columns, pd.Index):
                    return data

                if len(data.columns) > 0 and not isinstance(
                    data.columns[0], str
                ):
                    data_copy = data.copy()
                    data_copy.columns = pd.Index(
                        [str(name) for name in data_copy.columns]
                    )
                    return data_copy
                return data

            # We override the default implementation to use pandas
            # headers
            def get_row_headers(self) -> FieldTypes:
                return self._get_row_headers_for_index(
                    self._original_data.index
                )

            def _has_non_trivial_index(self) -> bool:
                """Check if the DataFrame has a non-trivial index that should be searched."""
                index = self._original_data.index
                return not _trivial_range_index(index)

            def search(self, query: str) -> PandasTableManager:
                # If there's a non-trivial index, include it in the search
                # by resetting the index first
                if self._has_non_trivial_index():
                    index = self._original_data.index
                    num_levels = index.nlevels
                    original_names = list(index.names)

                    working = self._original_data.copy()
                    _resolve_index_column_conflicts(working)
                    df_with_index = working.reset_index()
                    manager = PandasTableManager(df_with_index)

                    # Get index column names AFTER manager init, since
                    # _handle_non_string_column_names may have converted
                    # non-string column names to strings
                    index_columns = list(
                        manager._original_data.columns[:num_levels]
                    )

                    result = super(PandasTableManager, manager).search(query)
                    native_df: pd.DataFrame = nw.to_native(result.data)

                    # Restore the original index structure
                    native_df = native_df.set_index(index_columns)
                    native_df.index.names = original_names
                    return PandasTableManager(native_df)
                result = super().search(query)
                native_df = nw.to_native(result.data)
                return PandasTableManager(native_df)

            @staticmethod
            def is_type(value: Any) -> bool:
                return isinstance(value, pd.DataFrame)

            def _get_row_headers_for_index(
                self, index: pd.Index[Any]
            ) -> FieldTypes:
                # Ignore if it's the default index with no name
                if _trivial_range_index(index):
                    return []

                if isinstance(index, pd.MultiIndex):
                    # recurse
                    headers: FieldTypes = []
                    for i in range(index.nlevels):
                        headers.extend(
                            self._get_row_headers_for_index(
                                index.get_level_values(i)
                            )
                        )
                    return headers

                dtype = index.dtype
                field_type = self._map_dtype_to_field_type(dtype)
                return [(str(index.name or ""), field_type)]

            # We override the default implementation to use pandas's
            # internal fields since they get displayed in the UI.
            def get_field_type(
                self, column_name: str
            ) -> tuple[FieldType, ExternalDataType]:
                dtype = self.schema[column_name]
                return self._map_dtype_to_field_type(dtype)

            def _map_dtype_to_field_type(
                self, dtype: str | pd.DataFrame | DtypeObj
            ) -> tuple[FieldType, ExternalDataType]:
                # If a df has duplicate columns, it won't be a series, but
                # a dataframe. In this case, we take the dtype of the columns
                if isinstance(dtype, pd.DataFrame):
                    dtype = str(dtype.columns.dtype)
                else:
                    dtype = str(dtype)

                lower_dtype = dtype.lower()

                if lower_dtype.startswith("interval"):
                    return ("string", dtype)
                if lower_dtype.startswith(("int", "uint")):
                    return ("integer", dtype)
                if lower_dtype.startswith("float"):
                    return ("number", dtype)
                if lower_dtype == "object":
                    return ("string", dtype)
                if lower_dtype == "bool":
                    return ("boolean", dtype)
                if lower_dtype.startswith("datetime"):
                    return ("datetime", dtype)
                if lower_dtype == "date":
                    return ("date", dtype)
                if lower_dtype == "time":
                    return ("time", dtype)
                if lower_dtype == "timedelta64[ns]":
                    return ("string", dtype)
                if lower_dtype == "category":
                    return ("string", dtype)
                if lower_dtype in {"string", "str"}:
                    return ("string", dtype)
                if lower_dtype.startswith("complex"):
                    return ("unknown", dtype)
                return ("unknown", dtype)

            # We override the default since narwhals returns a Series
            def get_unique_column_values(
                self, column: str
            ) -> list[str | int | float]:
                return self._original_data[column].unique().tolist()  # type: ignore[return-value,no-any-return]

        return PandasTableManager
