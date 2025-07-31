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
from marimo._plugins.stateless.json_output import json_output
from marimo._plugins.stateless.mermaid import mermaid
from marimo._plugins.stateless.plain_text import plain_text
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


def polars_dot_to_mermaid(dot: str) -> str:
    """Converts polars DOT query plan renderings to mermaid.

    Adapted from https://github.com/pola-rs/polars/pull/20607
    Note: Not comprehensive, only handles components of the dot language used by polars.
    """

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
        import polars as pl

        from marimo._output import formatting

        if not include_opinionated():
            return None

        unpatch_polars_write_json = patch_polars_write_json()

        @formatting.opinionated_formatter(pl.DataFrame)
        def _show_marimo_dataframe(
            df: pl.DataFrame,
        ) -> tuple[KnownMimeType, str]:
            try:
                return table(df, selection=None, pagination=True)._mime_()
            except BaseException as e:
                # Catch-all: some libraries like Polars have bugs and raise
                # BaseExceptions, which shouldn't crash the kernel
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
            except BaseException as e:
                # Catch-all: some libraries like Polars have bugs and raise
                # BaseExceptions, which shouldn't crash the kernel
                LOGGER.warning("Failed to format Series: %s", e)
                return ("text/html", series._repr_html_())

        @formatting.opinionated_formatter(pl.LazyFrame)
        def _show_marimo_lazyframe(
            df: pl.LazyFrame,
        ) -> tuple[KnownMimeType, str]:
            return tabs.tabs(
                {
                    # NB(Trevor): Use `optimized=True` to match other methods' defaults (`show_graph`, `collect`).
                    # The _repr_html_ uses `optimized=False`, but "cost" is probably minimal and this is more
                    # accurate/opinionated default.
                    # See: https://github.com/pola-rs/polars/blob/911352/py-polars/polars/lazyframe/frame.py#L773-L790
                    "Query plan": mermaid(
                        polars_dot_to_mermaid(df._ldf.to_dot(optimized=True))
                    ),
                    "Table": table.lazy(df),
                }
            )._mime_()

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


class IbisFormatter(FormatterFactory):
    """Custom formatting for Ibis expressions.

    Provides custom formatters for tables, columns, and scalar values.

    When eager execution is enabled, tables and values are executed/generated.
    For unbound expressions, shows textual representation and generated SQL if backend supports SQL.
    For lazy expressions, shows expression representation and SQL instead of executing.
    """

    @staticmethod
    def package_name() -> str:
        return "ibis"

    def register(self) -> None:

        import ibis  # type: ignore[import-not-found]
        import ibis.expr.types as ir  # type: ignore[import-not-found]
        from ibis.backends.sql import (
            SQLBackend,  # type: ignore[import-not-found]
        )

        from marimo._output import formatting

        if not include_opinionated():
            return

        def _is_lazy_display(expr) -> tuple[bool, bool]:
            """Check if expression should be displayed lazily (without execution).

            Returns (is_lazy, has_unbound):
            - is_lazy: True if we should show Expression+SQL tabs
            - has_unbound: True if expression contains unbound tables
            """

            # Use _find_backends() to detect unbound expressions instead of get_backend(),
            # which throws IbisError rather than UnboundExpressionError
            # https://github.com/ibis-project/ibis/blob/main/ibis/expr/types/core.py#L330
            _, has_unbound = expr._find_backends()

            # Show lazy format if non-interactive OR unbound
            is_lazy = not ibis.options.interactive or has_unbound

            return is_lazy, has_unbound

        def _format_expr_and_sql(expr, has_unbound: bool, expr_type: str = "Expression") -> tuple[KnownMimeType, str]:
            """Format expression as tabs with Expression and SQL (if backend supports SQL)."""
            if has_unbound:
                expr_content = f"Contains unbound tables - cannot execute\n\n{expr._noninteractive_repr()}"
                # For unbound expressions, always try SQL generation
                sql = ibis.to_sql(expr)
                return tabs.tabs(
                    {
                        expr_type: plain_text(expr_content),
                        "SQL": f"```sql\n{sql!s}\n```"
                    }
                )._mime_()
            else:
                # For bound expressions, check if backend supports SQL.
                # Note: We are forced to use this private method instead of __repr__.
                # Because ibis.options.interactive is set AND the it's unbound the __repr__ will call `to_pyarrow` and crash.
                # https://github.com/ibis-project/ibis/blob/6b9f80c78e70c9013633ef89e5073a2081c49990/ibis/expr/types/core.py#L53
                expr_content = expr._noninteractive_repr()
                backend = expr.get_backend()
                supports_sql = isinstance(backend, SQLBackend)

                if supports_sql:
                    sql = ibis.to_sql(expr)
                    return tabs.tabs(
                        {
                            expr_type: plain_text(expr_content),
                            "SQL": f"```sql\n{sql!s}\n```"
                        }
                    )._mime_()
                else:
                    # Non-SQL backend, just show expression
                    return ("text/plain", expr_content)

        def _format_ibis_expression(expr) -> tuple[KnownMimeType, str]:
            """Format Ibis expressions.

            Interactive mode: Shows data as interactive table
            Non-interactive or unbound: Shows expression + SQL if it's a SQLBackend
            """
            try:
                is_lazy, has_unbound = _is_lazy_display(expr)

                if is_lazy:
                    return _format_expr_and_sql(expr, has_unbound)
                else:
                    return table(expr, selection=None, pagination=True)._mime_()

            except BaseException as e:
                LOGGER.error("Failed to format Ibis expression: %s", e)
                # Simple fallback - just show the expression as text
                try:
                    return ("text/plain", str(expr))
                except Exception:
                    return ("text/plain", f"<{type(expr).__name__} object - could not display>")

        @formatting.opinionated_formatter(ir.Table)
        def _show_marimo_ibis_table(
            table_expr: ir.Table,
        ) -> tuple[KnownMimeType, str]:
            """Format Table expressions.

            Interactive, bound expressions show as table widgets.
            All other cases show Expression+SQL tabs.

            Examples:
            --------
            >>> t.mutate(c=t.a + t.b)
            >>> t.filter(t.species == "Adelie")
            >>> ratings.select("userId", "rating")
            """
            return _format_ibis_expression(table_expr)

        try:
            from ibis.expr.types.groupby import GroupedTable

            @formatting.opinionated_formatter(GroupedTable)
            def _show_marimo_ibis_grouped_table(
                grouped_expr: GroupedTable,
            ) -> tuple[KnownMimeType, str]:
                """Format GroupedTable expressions as plain text.

                GroupedTable can be safely converted to a string.

                Examples:
                --------
                >>> t.group_by("species")
                """
                return ("text/plain", str(grouped_expr))
        except ImportError:
            pass

        @formatting.opinionated_formatter(ir.Join)
        def _show_marimo_ibis_join(
            join_expr: ir.Join,
        ) -> tuple[KnownMimeType, str]:
            """Format Join expressions.

            Uses same logic as tables: Interactive+bound expressions show
            as table widgets, all other cases show Expression+SQL tabs.

            Examples:
            --------
            >>> t1.left_join(t2, t1.key == t2.key)
            >>> ratings.inner_join(movies, "movieId")
            >>> customers.outer_join(orders, "customer_id")
            """
            return _format_ibis_expression(join_expr)

        try:
            from ibis.expr.types.relations import CachedTable

            @formatting.opinionated_formatter(CachedTable)
            def _show_marimo_ibis_cached_table(
                cached_expr: CachedTable,
            ) -> tuple[KnownMimeType, str]:
                """Format CachedTable expressions.

                Uses same logic as regular tables: Interactive+bound expressions
                show as table widgets, all other cases show Expression+SQL tabs.

                Examples:
                --------
                >>> t.cache()
                >>> cached_table = backend.cache(t)
                """
                return _format_ibis_expression(cached_expr)
        except ImportError:
            pass

        def register_column_formatters() -> None:
            """Register formatters for Column types.

            Handles numeric, text, temporal, geospatial, and complex column types.
            Converts columns to tables using .as_table().
            """
            column_types = [
                ir.Column, ir.UnknownColumn, ir.NullColumn,
                ir.NumericColumn, ir.IntegerColumn, ir.FloatingColumn,
                ir.DecimalColumn, ir.BooleanColumn, ir.StringColumn,
                ir.TimeColumn, ir.DateColumn, ir.TimestampColumn, ir.IntervalColumn,
                ir.GeoSpatialColumn, ir.PointColumn, ir.LineStringColumn, ir.PolygonColumn,
                ir.MultiLineStringColumn, ir.MultiPointColumn, ir.MultiPolygonColumn,
                ir.ArrayColumn, ir.SetColumn, ir.MapColumn, ir.StructColumn, ir.JSONColumn,
                ir.BinaryColumn, ir.MACADDRColumn, ir.INETColumn, ir.UUIDColumn,
            ]

            for column_type in column_types:
                @formatting.opinionated_formatter(column_type)
                def _show_marimo_ibis_column(column_expr) -> tuple[KnownMimeType, str]:
                    """Format Column expressions.

                    Columns are converted to single-column tables via .as_table()
                    then formatted using standard table logic.

                    Examples:
                    --------
                    >>> t.column
                    >>> t["species"]
                    >>> t.bill_length_mm
                    >>> t.body_mass_g.cast("float32")
                    """
                    return _format_ibis_expression(column_expr.as_table())

        register_column_formatters()

        def register_scalar_formatters() -> None:
            """Register formatters for Scalar types.

            Simple scalars render as text.
            Complex scalars (arrays, maps, structs) render using marimo json_output.
            """
            # Simple scalars - render as text
            simple_scalar_types = [
                ir.Scalar, ir.UnknownScalar, ir.NullScalar, ir.NumericScalar,
                ir.IntegerScalar, ir.FloatingScalar, ir.DecimalScalar,
                ir.BooleanScalar, ir.StringScalar, ir.BinaryScalar, ir.TimeScalar,
                ir.DateScalar, ir.TimestampScalar, ir.IntervalScalar, ir.JSONScalar,
                ir.SetScalar, ir.MACADDRScalar, ir.INETScalar, ir.UUIDScalar,
                ir.GeoSpatialScalar, ir.PointScalar, ir.LineStringScalar, ir.PolygonScalar,
                ir.MultiLineStringScalar, ir.MultiPointScalar, ir.MultiPolygonScalar,
            ]

            # Complex scalars - render as JSON
            json_scalar_types = [
                ir.ArrayScalar, ir.StructScalar, ir.MapScalar,
            ]

            for scalar_type in simple_scalar_types:
                @formatting.opinionated_formatter(scalar_type)
                def _show_marimo_ibis_scalar(scalar_expr) -> tuple[KnownMimeType, str]:
                    """Format simple Scalar expressions.

                    Interactive+bound expressions execute to single values.
                    All other cases show Expression+SQL tabs (even scalars become
                    "column-like" when unbound since they can't execute).

                    Examples:
                    --------
                    >>> t.body_mass_g.max()
                    >>> t.bill_depth_mm.quantile(0.99)
                    >>> ibis.literal(42)
                    >>> t.species.nunique()
                    """
                    is_lazy, has_unbound = _is_lazy_display(scalar_expr)

                    if is_lazy:
                        return _format_expr_and_sql(scalar_expr, has_unbound, "Scalar")
                    else:
                        try:
                            val = scalar_expr.to_pyarrow().as_py()
                            return ("text/plain", str(val))
                        except BaseException as e:
                            LOGGER.error("Failed to format Ibis scalar: %s", e)
                            try:
                                return ("text/plain", str(scalar_expr))
                            except Exception:
                                return ("text/plain", f"<{type(scalar_expr).__name__} object - could not display>")

            for scalar_type in json_scalar_types:
                @formatting.opinionated_formatter(scalar_type)
                def _show_marimo_ibis_json_scalar(scalar_expr) -> tuple[KnownMimeType, str]:
                    """Format complex JSON Scalar expressions.

                    Interactive+bound expressions execute to JSON widgets.
                    All other cases show Expression+SQL tabs.

                    Examples:
                    --------
                    >>> ibis.array([1, 2, 3])           # Literal ArrayScalar
                    >>> t.some_array.first()            # Column-derived ArrayScalar
                    >>> ibis.map({"a": 1, "b": 2})      # Literal MapScalar
                    """
                    is_lazy, has_unbound = _is_lazy_display(scalar_expr)

                    if is_lazy:
                        # Show scalar as expression + SQL tabs
                        return _format_expr_and_sql(scalar_expr, has_unbound, "JSON Scalar")
                    else:
                        # Interactive mode with bound expression - try to execute
                        try:
                            val = scalar_expr.to_pyarrow().as_py()
                            return json_output(json_data=val)._mime_()
                        except BaseException as e:
                            LOGGER.error("Failed to format Ibis scalar: %s", e)
                            # Simple fallback - just show the scalar as text
                            try:
                                return ("text/plain", str(scalar_expr))
                            except Exception:
                                return ("text/plain", f"<{type(scalar_expr).__name__} object - could not display>")

        register_scalar_formatters()
