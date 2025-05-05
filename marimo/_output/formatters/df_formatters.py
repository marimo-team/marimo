# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os

import narwhals.stable.v1 as nw

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._output.md import md
from marimo._plugins.ui._impl import tabs
from marimo._plugins.ui._impl.table import get_default_table_page_size, table

LOGGER = _loggers.marimo_logger()


def include_opinionated() -> bool:
    from marimo._runtime.context import (
        get_context,
        runtime_context_installed,
    )

    if os.getenv("MARIMO_NO_JS", "false").lower() == "true":
        return False

    if runtime_context_installed():
        ctx = get_context()
        return ctx.marimo_config["display"]["dataframes"] == "rich"
    return True


class PolarsFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "polars"

    def register(self) -> None:
        import polars as pl

        from marimo._output import formatting

        if not include_opinionated():
            return

        @formatting.opinionated_formatter(pl.DataFrame)
        def _show_marimo_dataframe(
            df: pl.DataFrame,
        ) -> tuple[KnownMimeType, str]:
            try:
                return table(df, selection=None, pagination=True)._mime_()
            except Exception as e:
                LOGGER.warning("Failed to format DataFrame: %s", e)
                return ("text/html", df._repr_html_())

        @formatting.opinionated_formatter(pl.Series)
        def _show_marimo_series(
            series: pl.Series,
        ) -> tuple[KnownMimeType, str]:
            try:
                # Table need a column name for operations
                if series.name is None or series.name == "":
                    df = pl.DataFrame({"value": series})
                else:
                    df = series.to_frame()
                return table(df, selection=None, pagination=True)._mime_()
            except Exception as e:
                LOGGER.warning("Failed to format Series: %s", e)
                return ("text/html", series._repr_html_())

        @formatting.opinionated_formatter(pl.LazyFrame)
        def _show_marimo_lazyframe(
            df: pl.LazyFrame,
        ) -> tuple[KnownMimeType, str]:
            return tabs.tabs(
                {
                    "Table": table.lazy(df),
                    "Query plan": md(df._repr_html_()),
                }
            )._mime_()


class PyArrowFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "pyarrow"

    def register(self) -> None:
        import pyarrow as pa  # type: ignore[import-not-found]

        from marimo._output import formatting

        if not include_opinionated():
            return

        @formatting.opinionated_formatter(pa.Table)
        def _show_marimo_dataframe(
            df: pa.Table,
        ) -> tuple[KnownMimeType, str]:
            return table(df, selection=None, pagination=True)._mime_()


class PySparkFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "pyspark"

    def register(self) -> None:
        try:
            from pyspark.sql.connect.dataframe import (  # type: ignore[import-not-found]
                DataFrame as pyspark_connect_DataFrame,
            )
        except (ImportError, ModuleNotFoundError):
            pyspark_connect_DataFrame = None

        try:
            from pyspark.sql.dataframe import (  # type: ignore[import-not-found]
                DataFrame as pyspark_DataFrame,
            )
        except (ImportError, ModuleNotFoundError):
            pyspark_DataFrame = None

        from marimo._output import formatting

        if not include_opinionated():
            return

        if pyspark_connect_DataFrame is not None:

            @formatting.opinionated_formatter(pyspark_connect_DataFrame)
            def _show_connect_df(
                df: pyspark_connect_DataFrame,
            ) -> tuple[KnownMimeType, str]:
                # narwhals (1.37.0) supports pyspark.sql.connect.dataframe.DataFrame
                if hasattr(nw.dependencies, "is_pyspark_connect_dataframe"):
                    return table.lazy(df)._mime_()

                # Otherwise, we convert to Arrow and load the first page of data
                # NOTE: this is no longer lazy, but will only load the first page of data
                return table(
                    df.limit(get_default_table_page_size()).toArrow(),
                    selection=None,
                    pagination=False,
                    _internal_lazy=True,
                    _internal_preload=True,
                )._mime_()

        if pyspark_DataFrame is not None:

            @formatting.opinionated_formatter(pyspark_DataFrame)
            def _show_df(df: pyspark_DataFrame) -> tuple[KnownMimeType, str]:
                return table.lazy(df)._mime_()
