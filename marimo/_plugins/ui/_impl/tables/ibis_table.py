# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import functools
from typing import TYPE_CHECKING, Any, Optional, Union

from marimo import _loggers
from marimo._data.models import BinValue, ColumnStats, ExternalDataType
from marimo._dependencies.dependencies import DependencyManager
from marimo._plugins.ui._impl.tables.format import (
    FormatMapping,
)
from marimo._plugins.ui._impl.tables.pandas_table import (
    PandasTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.polars_table import (
    PolarsTableManagerFactory,
)
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    FieldTypes,
    TableCell,
    TableCoordinate,
    TableManager,
    TableManagerFactory,
)
from marimo._utils.memoize import memoize_last_value

LOGGER = _loggers.marimo_logger()

if TYPE_CHECKING:
    from ibis import DataType  # type: ignore


class IbisTableManagerFactory(TableManagerFactory):
    @staticmethod
    def package_name() -> str:
        return "ibis"

    @staticmethod
    @functools.lru_cache(maxsize=1)
    def create() -> type[TableManager[Any]]:
        import ibis  # type: ignore

        class IbisTableManager(TableManager[ibis.Table]):
            type = "ibis"

            def to_csv_str(
                self, format_mapping: Optional[FormatMapping] = None
            ) -> str:
                return self._as_table_manager().to_csv_str(format_mapping)

            def to_json_str(
                self, format_mapping: Optional[FormatMapping] = None
            ) -> str:
                return self._as_table_manager().to_json_str(format_mapping)

            def to_parquet(self) -> bytes:
                return self._as_table_manager().to_parquet()

            def supports_download(self) -> bool:
                return False

            def apply_formatting(
                self, format_mapping: Optional[FormatMapping]
            ) -> IbisTableManager:
                raise NotImplementedError("Column formatting not supported")

            def supports_filters(self) -> bool:
                return True

            def select_rows(
                self, indices: list[int]
            ) -> TableManager[ibis.Table]:
                if not indices:
                    return self.take(0, 0)  # Return empty table
                # Select rows using Ibis API
                return IbisTableManager(
                    self.data.filter(ibis.row_number().over().isin(indices))
                )

            def select_columns(
                self, columns: list[str]
            ) -> TableManager[ibis.Table]:
                return IbisTableManager(self.data.select(columns))

            def select_cells(
                self, cells: list[TableCoordinate]
            ) -> list[TableCell]:
                del cells
                raise NotImplementedError("Cell selection not supported")

            def drop_columns(
                self, columns: list[str]
            ) -> TableManager[ibis.Table]:
                return IbisTableManager(self.data.drop(columns))

            def get_row_headers(self) -> FieldTypes:
                return []

            @staticmethod
            def is_type(value: Any) -> bool:
                return isinstance(value, ibis.Table)

            def take(self, count: int, offset: int) -> IbisTableManager:
                if count < 0:
                    raise ValueError("Count must be a positive integer")
                if offset < 0:
                    raise ValueError("Offset must be a non-negative integer")
                return IbisTableManager(self.data.limit(count, offset=offset))

            def search(self, query: str) -> TableManager[Any]:
                query = query.lower()
                predicates = []
                for column in self.data.columns:
                    col = self.data[column]
                    if col.type().is_string():
                        predicates.append(col.lower().rlike(query))
                    elif col.type().is_numeric():
                        predicates.append(
                            col.cast("string").lower().contains(query)
                        )
                    elif col.type().is_boolean():
                        predicates.append(
                            col.cast("string").lower().contains(query)
                        )
                    elif col.type().is_timestamp():
                        predicates.append(
                            col.cast("string").lower().contains(query)
                        )
                    elif col.type().is_date():
                        predicates.append(
                            col.cast("string").lower().contains(query)
                        )
                    elif col.type().is_time():
                        predicates.append(
                            col.cast("string").lower().contains(query)
                        )

                if predicates:
                    filtered = self.data.filter(ibis.or_(*predicates))
                else:
                    filtered = self.data.filter(ibis.literal(False))

                return IbisTableManager(filtered)

            def get_stats(self, column: str) -> ColumnStats:
                col = self.data[column]
                total = self.data.count().execute()
                nulls = col.isnull().sum().execute()

                stats = ColumnStats(total=total, nulls=nulls)

                if col.type().is_numeric():
                    stats.min = col.min().execute()
                    stats.max = col.max().execute()
                    stats.mean = col.mean().execute()
                    stats.median = col.median().execute()
                    stats.std = col.std().execute()

                return stats

            def _get_numeric_bin_values(
                self, col: ibis.Column, num_bins: int
            ) -> ibis.Table:
                min_val = col.min().execute()
                max_val = col.max().execute()

                # Handle case where all values are the same
                if min_val == max_val:
                    # Create a single bin with all the data
                    total_count = col.count().execute()
                    return ibis.memtable(
                        {
                            "bin": [0],
                            "count": [total_count],
                            "bin_start": [min_val],
                            "bin_end": [max_val],
                        }
                    ).execute()

                bin_width = (max_val - min_val) / num_bins

                # Assign bins and count occurrences
                data = self.data.mutate(bin=col.histogram(nbins=num_bins))
                value_counts = data["bin"].value_counts(name="count")

                # Fill in missing bins
                all_bins = ibis.range(num_bins).unnest().name("bin").as_table()
                joined = all_bins.left_join(value_counts, "bin").mutate(
                    count=ibis.coalesce(value_counts["count"], 0)
                )

                # Compute bin_start and bin_end for each bin
                # If the last bin, we use the last value for bin_end, else calculate the bin_end
                result = joined.mutate(
                    bin_start=min_val + joined["bin"] * bin_width,
                    bin_end=ibis.cases(
                        (joined["bin"] == (num_bins - 1), max_val),
                        else_=min_val + (joined["bin"] + 1) * bin_width,
                    ),
                ).order_by("bin")

                return result.execute()

            def get_bin_values(
                self, column: ColumnName, num_bins: int
            ) -> list[BinValue]:
                """Get bin values for a column. Currently supports numeric and temporal columns.

                Args:
                    column (str): The column to get bin values for.
                    num_bins (int): The number of bins to create.

                Returns:
                    list[BinValue]: The bin values.
                """
                if column not in self.data.columns:
                    LOGGER.error(f"Column {column} not found in Ibis table")
                    return []

                col = self.data[column]
                dtype = col.type()

                if dtype.is_temporal():
                    return self._get_bin_values_temporal(
                        column, dtype, num_bins
                    )

                if not dtype.is_numeric():
                    return []

                bin_values = self._get_numeric_bin_values(col, num_bins)

                return [
                    BinValue(
                        bin_start=row.bin_start,
                        bin_end=row.bin_end,
                        count=row.count,
                    )
                    for row in bin_values.itertuples(index=False)
                ]

            def _get_bin_values_temporal(
                self, column: ColumnName, dtype: DataType, num_bins: int
            ) -> list[BinValue]:
                def _convert_ms_to_time(ms: int) -> datetime.time:
                    hours = ms // 3600000
                    minutes = (ms % 3600000) // 60000
                    seconds = (ms % 60000) // 1000
                    microseconds = (ms % 1000) * 1000
                    return datetime.time(hours, minutes, seconds, microseconds)

                col = self.data[column]

                if dtype.is_time():
                    col_agg = (
                        col.hour() * 3600000
                        + col.minute() * 60000
                        + col.second() * 1000
                        + col.microsecond() // 1000
                    )
                else:
                    col_agg = col.epoch_seconds()

                numeric_bin_values = self._get_numeric_bin_values(
                    col_agg, num_bins
                )

                bin_values = []
                bin_start: Union[
                    datetime.datetime, datetime.date, datetime.time
                ]
                bin_end: Union[datetime.datetime, datetime.date, datetime.time]

                for row in numeric_bin_values.itertuples(index=False):
                    if dtype.is_date():
                        bin_start = datetime.date.fromtimestamp(row.bin_start)
                        bin_end = datetime.date.fromtimestamp(row.bin_end)
                    elif dtype.is_time():
                        ms = int(row.bin_start)
                        bin_start = _convert_ms_to_time(ms)

                        ms = int(row.bin_end)
                        bin_end = _convert_ms_to_time(ms)
                    else:
                        bin_start = datetime.datetime.fromtimestamp(
                            row.bin_start
                        )
                        bin_end = datetime.datetime.fromtimestamp(row.bin_end)

                    bin_values.append(
                        BinValue(
                            bin_start=bin_start,
                            bin_end=bin_end,
                            count=row.count,
                        )
                    )

                return bin_values

            @memoize_last_value
            def get_num_rows(self, force: bool = True) -> Optional[int]:
                if force:
                    return self.data.count().execute()  # type: ignore
                return None

            def get_num_columns(self) -> int:
                return len(self.data.columns)

            def get_column_names(self) -> list[str]:
                return self.data.columns  # type: ignore

            def get_unique_column_values(
                self, column: str
            ) -> list[str | int | float]:
                result = (
                    self.data.distinct(on=column)
                    .select(column)
                    .execute()[column]
                    .tolist()
                )
                return result  # type: ignore

            def get_sample_values(self, column: str) -> list[Any]:
                # Don't sample values for Ibis tables
                # since it can be expensive
                del column
                return []

            def sort_values(
                self, by: ColumnName, descending: bool
            ) -> IbisTableManager:
                sorted_data = self.data.order_by(
                    ibis.desc(by) if descending else ibis.asc(by)
                )
                return IbisTableManager(sorted_data)

            @functools.lru_cache(maxsize=5)  # noqa: B019
            def calculate_top_k_rows(
                self, column: ColumnName, k: int
            ) -> list[tuple[Any, int]]:
                count_col_name = f"{column}_count"
                result = (
                    self.data[[column]]
                    .value_counts(name=count_col_name)
                    .order_by(ibis.desc(count_col_name))
                    .limit(k)
                    .execute()
                )

                return [
                    (row[0], int(row[1]))
                    for row in result.itertuples(index=False)
                ]

            def get_field_type(
                self, column_name: str
            ) -> tuple[FieldType, ExternalDataType]:
                column = self.data[column_name]
                dtype = column.type()
                if dtype.is_string():
                    return ("string", str(dtype))
                elif dtype.is_boolean():
                    return ("boolean", str(dtype))
                elif dtype.is_integer():
                    return ("integer", str(dtype))
                elif dtype.is_floating():
                    return ("number", str(dtype))
                elif dtype.is_timestamp():
                    return ("datetime", str(dtype))
                elif dtype.is_time():
                    return ("time", str(dtype))
                elif dtype.is_date():
                    return ("date", str(dtype))
                else:
                    return ("unknown", str(dtype))

            def _as_table_manager(self) -> TableManager[Any]:
                if DependencyManager.pandas.has():
                    return PandasTableManagerFactory.create()(
                        self.data.to_pandas()
                    )
                if DependencyManager.polars.has():
                    return PolarsTableManagerFactory.create()(
                        self.data.to_polars()
                    )

                raise ValueError(
                    "Requires at least one of pandas, polars, or pyarrow"
                )

        return IbisTableManager
