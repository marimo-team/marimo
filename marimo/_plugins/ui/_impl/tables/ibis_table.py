# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import datetime
import functools
from typing import TYPE_CHECKING, Any, Union

import narwhals.stable.v2 as nw

from marimo import _loggers
from marimo._data.models import BinValue, ExternalDataType
from marimo._plugins.ui._impl.tables.narwhals_table import NarwhalsTableManager
from marimo._plugins.ui._impl.tables.table_manager import (
    ColumnName,
    FieldType,
    TableManager,
    TableManagerFactory,
)

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

        class IbisTableManager(NarwhalsTableManager[ibis.Table, ibis.Table]):
            type = "ibis"

            def __init__(self, data: ibis.Table) -> None:
                self._original_data = data
                super().__init__(nw.from_native(data))

            def collect(self) -> ibis.Table:
                return self._original_data

            @staticmethod
            def is_type(value: Any) -> bool:
                return isinstance(value, ibis.Table)

            def _get_numeric_bin_values(
                self, col: ibis.Column, num_bins: int
            ) -> ibis.Table:
                data = self._original_data
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
                data = data.mutate(bin=col.histogram(nbins=num_bins))
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
                data = self._original_data
                if column not in data.columns:
                    LOGGER.error(f"Column {column} not found in Ibis table")
                    return []

                col = data[column]
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
                data = self._original_data

                def _convert_ms_to_time(ms: int) -> datetime.time:
                    hours = ms // 3600000
                    minutes = (ms % 3600000) // 60000
                    seconds = (ms % 60000) // 1000
                    microseconds = (ms % 1000) * 1000
                    return datetime.time(hours, minutes, seconds, microseconds)

                col = data[column]

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

            def get_field_type(
                self, column_name: str
            ) -> tuple[FieldType, ExternalDataType]:
                column = self._original_data[column_name]
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

        return IbisTableManager
