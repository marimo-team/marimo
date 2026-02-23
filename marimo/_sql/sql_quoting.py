# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re


def quote_sql_identifier(identifier: str, dialect: str = "duckdb") -> str:
    """
    Quote a SQL identifier for the given dialect, escaping special characters.

    Args:
        identifier: The raw identifier string (database, schema, or table name).
        dialect: The SQL dialect. Supported: "duckdb", "redshift", "clickhouse".

    Returns:
        The properly quoted identifier string.
    """
    if dialect in ("duckdb", "redshift", "postgresql", "postgres"):
        # Double-quote style: escape embedded " as ""
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'
    elif dialect in ("clickhouse", "mysql"):
        # Backtick style: escape embedded ` as ``
        escaped = identifier.replace("`", "``")
        return f"`{escaped}`"
    else:
        # Default to double-quote (ANSI SQL standard)
        escaped = identifier.replace('"', '""')
        return f'"{escaped}"'


def quote_qualified_name(*parts: str, dialect: str = "duckdb") -> str:
    """
    Build a fully qualified name from parts, quoting each one.

    Example:
        quote_qualified_name("my db", "public", "my.table", dialect="duckdb")
        # => '"my db"."public"."my.table"'
    """
    return ".".join(quote_sql_identifier(p, dialect) for p in parts)


def parse_fully_qualified_table_name(
    fully_qualified_table_name: str,
) -> tuple[str, str, str]:
    """
    Parse a fully qualified table name into (database, schema, table).

    Handles both quoted and unquoted identifiers:
      - "my.db"."schema"."table" => ("my.db", "schema", "table")
      - db.schema.table => ("db", "schema", "table")
    """
    # Match either a quoted identifier ("...") or an unquoted segment (no dots)
    pattern = r'"([^"]*(?:""[^"]*)*)"|([^.]+)'
    parts = [
        m.group(1).replace('""', '"') if m.group(1) is not None else m.group(2)
        for m in re.finditer(pattern, fully_qualified_table_name)
    ]
    if len(parts) != 3:
        raise ValueError(
            f"Invalid fully qualified table name: {fully_qualified_table_name}"
        )
    return parts[0], parts[1], parts[2]
