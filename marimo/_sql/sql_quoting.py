# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re


def quote_sql_identifier(identifier: str, *, dialect: str = "duckdb") -> str:
    """
    Quote a SQL identifier for the given dialect, escaping special characters.

    Args:
        identifier: The raw identifier string (database, schema, or table name).
        dialect: The SQL dialect.
            Double-quote style: "duckdb", "redshift", "postgresql"/"postgres".
            Backtick style: "clickhouse", "mysql", "bigquery".
            Unknown dialects return the identifier unquoted.

    Returns:
        The properly quoted identifier string.
    """
    if dialect in ("duckdb", "redshift", "postgresql", "postgres"):
        # Double-quote style: escape embedded " as ""
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'
    elif dialect in ("clickhouse", "mysql", "bigquery"):
        # Backtick style: escape embedded ` as ``
        escaped = identifier.replace("`", "``")
        return f"`{escaped}`"
    else:
        # Unknown dialect: return unquoted to avoid breaking databases
        # that treat quoted identifiers differently
        return identifier


def quote_qualified_name(*parts: str, dialect: str = "duckdb") -> str:
    """
    Build a fully qualified name from parts, quoting each one.

    Example:
        quote_qualified_name("my db", "public", "my.table", dialect="duckdb")
        # => '"my db"."public"."my.table"'
    """
    return ".".join(quote_sql_identifier(p, dialect=dialect) for p in parts)


def parse_fully_qualified_table_name(
    fully_qualified_table_name: str,
) -> tuple[str, str, str]:
    """
    Parse a fully qualified table name into (database, schema, table).

    Handles both quoted and unquoted identifiers:
      - "my.db"."schema"."table" => ("my.db", "schema", "table")
      - db.schema.table => ("db", "schema", "table")

    Raises ValueError for malformed input (unterminated quotes, stray quotes,
    wrong number of parts).
    """
    # Fast path for simple unquoted identifiers (no quotes)
    if '"' not in fully_qualified_table_name:
        parts = fully_qualified_table_name.split(".")
        if len(parts) != 3:
            raise ValueError(
                f"Invalid fully qualified table name: {fully_qualified_table_name}"
            )
        return parts[0], parts[1], parts[2]

    # Each identifier is either:
    #   - a quoted identifier: "..." with escaped "" inside
    #   - an unquoted identifier: no dots or quotes
    _ident = r'(?:"([^"]*(?:""[^"]*)*)"|([^."]+))'
    pattern = re.compile(rf"^{_ident}\.{_ident}\.{_ident}$")
    match = pattern.fullmatch(fully_qualified_table_name)
    if not match:
        raise ValueError(
            f"Invalid fully qualified table name: {fully_qualified_table_name}"
        )

    def _segment(quoted_group: int, unquoted_group: int) -> str:
        value = match.group(quoted_group)
        if value is not None:
            return value.replace('""', '"')
        return match.group(unquoted_group)

    return (
        _segment(1, 2),
        _segment(3, 4),
        _segment(5, 6),
    )
