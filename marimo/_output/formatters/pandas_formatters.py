# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any

from marimo._loggers import marimo_logger
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.df_formatters import include_opinionated
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.utils import flatten_string
from marimo._plugins.ui._impl.table import table
from marimo._plugins.ui._impl.tables.format import FormatMapping

LOGGER = marimo_logger()


class PandasFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "pandas"

    def register(self) -> None:
        import pandas as pd

        pd.set_option("display.max_rows", 10)
        pd.set_option("display.max_columns", 20)
        pd.set_option("display.show_dimensions", "truncate")

        from marimo._output import formatting

        if include_opinionated():

            @formatting.opinionated_formatter(pd.DataFrame)
            def _show_marimo_dataframe(
                df: pd.DataFrame,
            ) -> tuple[KnownMimeType, str]:
                float_format = pd.get_option("display.float_format")
                format_mapping: FormatMapping | None = (
                    {
                        (
                            ",".join(map(str, col))
                            if isinstance(df.columns, pd.MultiIndex)
                            and isinstance(col, tuple)
                            else str(col)
                        ): lambda value: (
                            value if pd.isna(value) else float_format(value)
                        )
                        for col, dtype in df.dtypes.items()
                        if pd.api.types.is_float_dtype(dtype)
                    }
                    if float_format is not None
                    else None
                )
                return table(
                    df,
                    selection=None,
                    pagination=None,
                    format_mapping=format_mapping,
                )._mime_()

            @formatting.opinionated_formatter(pd.Series)
            def _show_marimo_series(
                series: pd.Series[Any],
            ) -> tuple[KnownMimeType, str]:
                try:
                    # Table need a column name for operations
                    if series.name is None:
                        series = series.rename("value")
                    return _show_marimo_dataframe(series.to_frame())
                except Exception as e:
                    LOGGER.warning("Failed to format Series: %s", e)
                    return ("text/html", series._repr_html_())

        @formatting.formatter(pd.DataFrame)
        def _show_dataframe(df: pd.DataFrame) -> tuple[KnownMimeType, str]:
            max_rows = pd.get_option("display.max_rows")
            max_columns = pd.get_option("display.max_columns")
            show_dimensions_option = pd.get_option("display.show_dimensions")

            if show_dimensions_option == "truncate":
                # Handle None for max_rows
                if max_rows is None:
                    max_rows = len(df.index)

                # Handle None for max_columns
                if max_columns is None:
                    max_columns = len(df.columns)

                show_dimensions = (
                    len(df.index) > max_rows or len(df.columns) > max_columns
                )
            elif show_dimensions_option:
                show_dimensions = True
            else:
                show_dimensions = False

            # Flatten the HTML to avoid indentation issues when
            # interpolating into other HTML/Markdown with an f-string
            return (
                "text/html",
                flatten_string(
                    df.to_html(
                        max_rows=max_rows,
                        max_cols=max_columns,
                        show_dimensions=show_dimensions,
                    )
                ),
            )

        @formatting.formatter(pd.Series)
        def _show_series(series: pd.Series[Any]) -> tuple[KnownMimeType, str]:
            max_rows = pd.get_option("display.max_rows")
            show_dimensions_option = pd.get_option("display.show_dimensions")

            if show_dimensions_option == "truncate":
                # Handle None for max_rows
                if max_rows is None:
                    max_rows = len(series.index)

                show_dimensions = len(series.index) > max_rows
            elif show_dimensions_option:
                show_dimensions = True
            else:
                show_dimensions = False

            return (
                "text/html",
                flatten_string(
                    series.to_frame().to_html(
                        max_rows=max_rows, show_dimensions=show_dimensions
                    )
                ),
            )
