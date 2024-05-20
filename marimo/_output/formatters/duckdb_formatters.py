# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._dependencies.dependencies import DependencyManager
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import FormatterFactory
from marimo._plugins.ui import table


class DuckDBFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "duckdb"

    def register(self) -> None:
        import duckdb

        from marimo._output import formatting

        @formatting.formatter(duckdb.DuckDBPyConnection)
        @formatting.formatter(duckdb.DuckDBPyRelation)
        def _show_plot(
            con: duckdb.DuckDBPyConnection,
        ) -> tuple[KnownMimeType, str]:
            if DependencyManager.has_polars():
                return table(con.pl(), selection=None)._mime_()
            if DependencyManager.has_pandas():
                return table(con.df(), selection=None)._mime_()

            return (
                "text/html",
                str(con),
            )
