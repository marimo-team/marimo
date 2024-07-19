# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui._impl.table import table

LOGGER = _loggers.marimo_logger()


class PolarsFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "polars"

    def register(self) -> None:
        import polars as pl

        from marimo._output import formatting

        @formatting.opinionated_formatter(pl.DataFrame)
        def _show_marimo_dataframe(
            df: pl.DataFrame,
        ) -> tuple[KnownMimeType, str]:
            try:
                return table(df, selection=None, pagination=True)._mime_()
            except Exception as e:
                LOGGER.warning("Failed to format DataFrame: %s", e)
                return ("text/html", df._repr_html_())


class PyArrowFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "pyarrow"

    def register(self) -> None:
        import pyarrow as pa

        from marimo._output import formatting

        @formatting.opinionated_formatter(pa.Table)
        def _show_marimo_dataframe(
            df: pa.Table,
        ) -> tuple[KnownMimeType, str]:
            return table(df, selection=None, pagination=True)._mime_()
