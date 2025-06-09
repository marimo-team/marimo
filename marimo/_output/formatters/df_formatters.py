# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import re

import narwhals.stable.v1 as nw

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import (
    FormatterFactory,
    Unregister,
)
from marimo._output.md import md
from marimo._plugins.ui._impl import tabs
from marimo._plugins.ui._impl.table import get_default_table_page_size, table
from marimo._runtime.patches import patch_polars_write_json

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


# adapted from https://github.com/pola-rs/polars/pull/20607
def dot_to_mermaid(dot: str) -> str:
    """Not comprehensive, only handles components of the dot language used by polars."""

    edge_regex = r"(?P<node1>\w+) -- (?P<node2>\w+)"
    node_regex = r"(?P<node>\w+)(\s+)?\[label=\"(?P<label>.*)\"]"

    nodes = re.finditer(node_regex, dot)
    edges = re.finditer(edge_regex, dot)

    mermaid_str = "\n".join(
        [
            "graph TD",
            *[f'\t{n["node"]}["{n["label"]}"]' for n in nodes],
            *[f"\t{e['node1']} --- {e['node2']}" for e in edges],
        ]
    )

    # replace [https://...] with <a> tags to avoid Mermaid interpreting it as markdown
    mermaid_str = re.sub(
        r"\[(https?://[^\]]+)\]",
        lambda m: f"[<a href='{m.group(1)}'>{m.group(1)}</a>]",
        mermaid_str,
    )

    # replace escaped newlines
    mermaid_str = mermaid_str.replace(r"\n", "\n")

    # replace escaped quotes
    mermaid_str = mermaid_str.replace(r"\"", "#quot;")

    return mermaid_str


class PolarsFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> str:
        return "polars"

    def register(self) -> Unregister | None:
        from unittest.mock import patch

        import polars as pl

        from marimo._output import formatting
        from marimo._output.hypertext import Html

        if not include_opinionated():
            return None

        unpatch_polars_write_json = patch_polars_write_json()

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

        # Patch for https://github.com/pola-rs/polars/blob/66ca5b/py-polars/polars/_utils/various.py#L655-L656
        # Which has the comment: "Don't rename or move. This is used by polars cloud", so monkey patching inline should be safe
        def display_dot_graph(
            *,
            dot: str,
            show: bool = True,  # noqa: ARG001
            output_path: str | None = None,  # noqa: ARG001
            raw_output: bool = False,  # noqa: ARG001
            figsize: tuple[float, float] = (16.0, 12.0),  # noqa: ARG001
        ) -> Html:
            import marimo as mo

            return mo.mermaid(dot_to_mermaid(dot))

        @pl.api.register_lazyframe_namespace("mo")
        class DTypeOperations:
            def __init__(self, ldf: pl.LazyFrame) -> None:
                self._ldf = ldf

            def show_graph(self, *args, **kwargs) -> Html:  # noqa: ANN002, ANN003
                with patch(
                    "polars.lazyframe.frame.display_dot_graph"
                ) as mock_display:
                    self._ldf.show_graph(*args, **kwargs)
                    return display_dot_graph(
                        *mock_display.call_args.args,
                        **mock_display.call_args.kwargs,
                    )

        return unpatch_polars_write_json


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
