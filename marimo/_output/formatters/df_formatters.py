# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from enum import Enum
from typing import Any

import narwhals.stable.v2 as nw

from marimo import _loggers
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output.formatters.formatter_factory import (
    FormatterFactory,
    Unregister,
)
from marimo._output.hypertext import is_no_js
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

    if is_no_js():
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

    When eager execution is enabled, tables, columns and values are executed
    and displayed using an appropriate marimo formatter.
    For lazy expressions, show the query representation and the SQL (if available).
    For unbound expressions, show the query representation and the SQL.
    """

    @staticmethod
    def package_name() -> str:
        return "ibis"

    def register(self) -> None:
        import ibis  # type: ignore[import-not-found]
        import ibis.expr.types as ir  # type: ignore[import-not-found]
        from ibis.backends.sql import (  # type: ignore[import-not-found]
            SQLBackend,
        )

        from marimo._output import formatting

        if not include_opinionated():
            return

        class IbisDisplayMode(Enum):
            """Display mode for Ibis expressions."""

            INTERACTIVE = "interactive"  # Execute and show as table
            UNBOUND = (
                "unbound"  # Show Expression+SQL tabs (contains unbound tables)
            )
            LAZY = "lazy"  # Show Expression+SQL tabs (non-interactive mode)

        def _get_display_mode(expr: ir.Expr) -> IbisDisplayMode:
            """Get display mode for expression.

            Returns:
            - INTERACTIVE: Execute and show as interactive table
            - UNBOUND: Show Expression+SQL tabs (contains unbound tables)
            - LAZY: Show Expression+SQL tabs (non-interactive mode)
            """

            # We are using _find_backends() to detect unbound expressions instead of get_backend(),
            # because the latter throws a general IbisError rather than UnboundExpressionError
            # https://github.com/ibis-project/ibis/blob/main/ibis/expr/types/core.py#L330.
            #
            # If this private method is removed in future versions, fallback to:
            # try: expr.get_backend() except IbisError: has_unbound = True
            _, has_unbound = expr._find_backends()

            if has_unbound:
                return IbisDisplayMode.UNBOUND
            elif not ibis.options.interactive:
                return IbisDisplayMode.LAZY
            else:
                return IbisDisplayMode.INTERACTIVE

        def _render_plain_text_fallback(
            obj: Any,
        ) -> tuple[KnownMimeType, str]:
            """Helper to render object as plain text with fallback."""
            try:
                return plain_text(repr(obj))._mime_()
            except Exception:
                return (
                    "text/plain",
                    f"<{type(obj).__name__} object - could not display>",
                )

        def _get_sql_repr(expr: ir.Expr, mode: IbisDisplayMode) -> str:
            """Get SQL representation or message if backend doesn't support SQL."""
            try:
                if mode == IbisDisplayMode.UNBOUND or isinstance(
                    expr.get_backend(), SQLBackend
                ):
                    return f"```sql\n{ibis.to_sql(expr)}\n```"
                else:
                    return "Backend doesn't support SQL"
            except Exception as e:
                LOGGER.warning("Could not generate SQL for expression: %s", e)
                return f"Could not generate SQL: {e}"

        def _format_lazy_expression(
            expr: ir.Expr, mode: IbisDisplayMode
        ) -> tuple[KnownMimeType, str]:
            """Display the expression as a lazy representation with Expression and SQL."""

            # We need to call _noninteractive_repr() directly instead of just relying on ir.Expr.__repr__() because
            # otherwise when the expression is unbound and interactive mode is enabled it will try to execute it.
            # https://github.com/ibis-project/ibis/blob/8a7534c8ef3c675229edd17f2f4467f314d0c143/ibis/expr/types/core.py#L53C3-L58C1
            #
            # If this private method is removed in future versions, fallback to repr(expr) is acceptable -
            # unbound expressions in interactive mode will crash, but that's a reasonable failure mode
            # since users shouldn't typically have unbound expressions in interactive contexts.
            expr_repr = expr._noninteractive_repr()
            if mode == IbisDisplayMode.UNBOUND:
                expr_content = (
                    f"Contains unbound tables - cannot execute\n\n{expr_repr}"
                )
            else:
                expr_content = expr_repr

            sql_content = _get_sql_repr(expr, mode)

            return tabs.tabs(
                {"Expression": plain_text(expr_content), "SQL": sql_content}
            )._mime_()

        def _format_ibis_expression(
            expr: ir.Expr,
        ) -> tuple[KnownMimeType, str]:
            """Format Ibis expressions.

            Interactive mode: Shows data as marimo table
            Non-interactive or unbound: Shows the expression representation
            """
            try:
                mode = _get_display_mode(expr)

                if mode == IbisDisplayMode.INTERACTIVE:
                    # Even though interactive mode is enabled and the expression may not be unbound,
                    # it could be an extremely large query (e.g. s3 bucket)
                    # Without lazy, this tries to load the entire dataframe into memory
                    #
                    # If a user does want the full dataframe, they can call .execute() manually
                    # or use `mo.ui.table(df)`
                    return table.lazy(
                        expr,
                        # Lazy, but preload the first page of data (since interactive is true)
                        preload=True,
                    )._mime_()
                else:
                    return _format_lazy_expression(expr, mode)

            except BaseException as e:
                LOGGER.warning("Failed to format Ibis expression: %s", e)
                # Simple fallback - just show the expression as text
                return _render_plain_text_fallback(expr)

        @formatting.opinionated_formatter(ir.Table)
        def _show_marimo_ibis_table(
            table_expr: ir.Table,
        ) -> tuple[KnownMimeType, str]:
            """Format Table expressions.

            Interactive, bound expressions show as table widgets.
            All other cases show lazy expression representation.

            Examples:
            --------
            >>> t.mutate(c=t.a + t.b)
            >>> t.filter(t.species == "Adelie")
            >>> ratings.select("userId", "rating")
            """
            return _format_ibis_expression(table_expr)

        @formatting.opinionated_formatter(ir.Column)
        def _show_marimo_ibis_column(
            column_expr: ir.Column,
        ) -> tuple[KnownMimeType, str]:
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

        @formatting.formatter(ir.Scalar)
        def _show_scalar(scalar: ir.Scalar) -> tuple[KnownMimeType, str]:
            """Format Scalar expressions.

            Simple scalars render as text.
            Complex scalars (arrays, maps, structs) render using marimo's json_output.

            Bound, interactive expressions execute to single values.
            All other cases are displayed using the lazy expression representation.

            Examples:
            --------
            >>> t.body_mass_g.max()
            >>> t.bill_depth_mm.quantile(0.99)
            >>> ibis.literal(42)
            >>> t.species.nunique()
            """
            mode = _get_display_mode(scalar)

            if mode != IbisDisplayMode.INTERACTIVE:
                return _format_lazy_expression(scalar, mode)

            # Interactive mode - try to execute
            try:
                val = scalar.to_pyarrow().as_py()
                # Complex scalars as JSON, simple ones as text
                if isinstance(
                    scalar, (ir.ArrayScalar, ir.StructScalar, ir.MapScalar)
                ):
                    return json_output(json_data=val)._mime_()
                else:
                    return _render_plain_text_fallback(val)
            except BaseException as e:
                LOGGER.warning("Failed to format Ibis scalar: %s", e)
                return _render_plain_text_fallback(scalar)
