# Copyright 2026 Marimo. All rights reserved.
"""Resolve sqlglot DuckDB table nodes to remote file sources.

The SQL patch should only rewrite queries it can execute with fetched
DataFrames. This module recognizes direct URL table syntax and supported
``read_*`` table functions, extracts literal URL/options from sqlglot's AST,
and returns ``None`` for dynamic expressions so they continue through DuckDB
unchanged.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from marimo._runtime._wasm._duckdb.io import (
    RemoteFileSource,
    reader_for_url,
    remote_file_from_url,
    remote_file_source_from_reader_args,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlglot import exp

# SQL options can parse to falsy values such as false, 0, or ""; this marks
# unsupported expressions without conflating them with valid literal values.
_MISSING = object()


def remote_file_source_from_table(
    table: exp.Table,
    *,
    query: str | None = None,
) -> RemoteFileSource | None:
    """Return a remote source for supported direct URLs or reader calls."""
    table_name = table.name
    if table_name and _is_single_quoted_table_identifier(table, query):
        reader = reader_for_url(table_name)
        remote_file = remote_file_from_url(table_name)
        if reader is not None and remote_file is not None:
            return RemoteFileSource((remote_file,), reader.name)

    table_expr = table.this
    if table_expr is None:
        return None

    table_function = _table_function_call(table_expr)
    if table_function is None:
        return None

    function_name, args = table_function
    source = _read_function_source(args)
    if source is None:
        return None

    raw_options = _read_function_options(args[1:])
    if raw_options is None:
        return None
    return remote_file_source_from_reader_args(
        function_name, source, raw_options
    )


def _is_single_quoted_table_identifier(
    table: exp.Table, query: str | None
) -> bool:
    """Distinguish DuckDB file scans from ordinary quoted identifiers."""
    if query is None:
        return False
    meta = getattr(table.this, "meta", {})
    start = meta.get("start")
    end = meta.get("end")
    if not isinstance(start, int) or not isinstance(end, int):
        return _query_has_single_quoted_table_reference(query, table.name)
    return (
        0 <= start
        and end < len(query)
        and query[start] == "'"
        and query[end] == "'"
    )


def _query_has_single_quoted_table_reference(
    query: str, table_name: str
) -> bool:
    if not table_name:
        return False

    quoted_table = re.escape(f"'{table_name}'")
    return any(
        re.search(pattern, query, flags=re.IGNORECASE) is not None
        for pattern in (
            rf"(?:^|[()\s])FROM\s+{quoted_table}",
            rf"\bJOIN\s+{quoted_table}",
        )
    )


def _table_function_call(
    table_expr: exp.Expression,
) -> tuple[str, list[exp.Expression]] | None:
    """Return a normalized DuckDB reader name and its arguments."""
    import sqlglot.expressions as exp

    # sqlglot versions model first-party DuckDB readers either as explicit
    # Read* nodes or as generic anonymous table functions.
    for node_name, function_name in (
        ("ReadCSV", "read_csv"),
        ("ReadParquet", "read_parquet"),
    ):
        read_node = getattr(exp, node_name, None)
        if read_node is not None and isinstance(table_expr, read_node):
            first = [table_expr.this] if table_expr.this is not None else []
            return function_name, [*first, *table_expr.expressions]

    if isinstance(table_expr, exp.Anonymous):
        return str(table_expr.this).lower(), list(table_expr.expressions)
    return None


def _read_function_source(
    args: Sequence[exp.Expression],
) -> str | tuple[str, ...] | None:
    """Accept only literal URL sources that can be fetched before execution."""
    import sqlglot.expressions as exp

    if not args:
        return None
    source_expr = args[0]
    if isinstance(source_expr, exp.Literal) and source_expr.is_string:
        return str(source_expr.this)

    if isinstance(source_expr, exp.Array) and source_expr.expressions:
        urls: list[str] = []
        for item_expr in source_expr.expressions:
            if not (
                isinstance(item_expr, exp.Literal) and item_expr.is_string
            ):
                return None
            urls.append(str(item_expr.this))
        return tuple(urls)

    return None


def _read_function_options(
    option_exprs: Sequence[exp.Expression],
) -> dict[str, Any] | None:
    """Decode literal keyword options from a DuckDB table-function call."""
    options: dict[str, Any] = {}
    for option_expr in option_exprs:
        option = _read_function_option(option_expr)
        if option is None:
            return None
        key, value = option
        options[key] = value
    return options


def _read_function_option(
    option_expr: exp.Expression,
) -> tuple[str, Any] | None:
    """Return one static option or ``None`` for unsupported expressions."""
    import sqlglot.expressions as exp

    property_eq = getattr(exp, "PropertyEQ", None)
    option_classes = (
        (exp.EQ,) if property_eq is None else (exp.EQ, property_eq)
    )
    if not isinstance(option_expr, option_classes):
        return None

    value_expr = option_expr.args.get("expression")
    if value_expr is None:
        return None

    value = _literal_value(value_expr)
    if value is _MISSING:
        return None

    key = getattr(option_expr.this, "name", None)
    if key is None:
        return None
    return key.lower(), value


def _literal_value(value_expr: exp.Expression) -> Any:
    """Convert sqlglot literals while preserving falsy values via _MISSING."""
    import sqlglot.expressions as exp

    if isinstance(value_expr, exp.Boolean):
        return value_expr.this
    if isinstance(value_expr, exp.Literal):
        if value_expr.is_string:
            return value_expr.this
        return value_expr.to_py()
    return _MISSING
