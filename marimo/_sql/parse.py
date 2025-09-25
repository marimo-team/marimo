# Copyright 2025 Marimo. All rights reserved.

from typing import Literal, Optional, Union

import msgspec


class SqlParseError(msgspec.Struct):
    """
    Represents a single SQL parse error.

    Attributes:
        message (str): Description of the error.
        line (int): Line number where the error occurred (1-based).
        column (int): Column number where the error occurred (1-based).
        severity (Literal["error", "warning"]): Severity of the error.
    """

    message: str
    line: int
    column: int
    severity: Literal["error", "warning"]


class SqlParseResult(msgspec.Struct):
    """
    Result of parsing an SQL query.

    Attributes:
        success (bool): True if parsing succeeded without errors.
        errors (list[SqlParseError]): List of parse errors (empty if success is True).
    """

    success: bool
    errors: list[SqlParseError]


def parse_sql(query: str, dialect: str) -> SqlParseResult:
    """Parses an SQL query. Returns syntax errors.
    Does not check for catalog errors (incorrect table names, etc).
    Currently only supports DuckDB.

    Args:
        query (str): The SQL query to parse.
        dialect (str): The dialect of the SQL query.

    Returns:
        str: The syntax errors in the SQL query.
    """
    dialect = dialect.strip().lower()

    # Handle DuckDB
    if "duckdb" in dialect:
        return _parse_sql_duckdb(query)

    # If we don't support the dialect, we return a success result
    return SqlParseResult(success=True, errors=[])


# DuckDB


class DuckDBParseError(msgspec.Struct):
    error: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_subtype: Optional[str] = None
    position: Optional[Union[int, str]] = None


# skip to reduce the response size
# the response doesn't matter too much, we are interested in the errors
JSON_SERIALIZE_QUERY = "SELECT JSON_SERIALIZE_SQL(?, skip_null := true, skip_empty := true, skip_default := true)"


def _parse_sql_duckdb(query: str) -> SqlParseResult:
    import duckdb

    relation = duckdb.execute(JSON_SERIALIZE_QUERY, [query])
    result = relation.fetchone()[0]
    parsed_error = msgspec.json.decode(result, type=DuckDBParseError)

    if not parsed_error.error:
        return SqlParseResult(success=True, errors=[])

    position = int(parsed_error.position or 0)
    subquery = query[:position]
    line_number = subquery.count("\n") + 1
    column_number = position - subquery.rfind("\n") - 1

    return SqlParseResult(
        success=False,
        errors=[
            SqlParseError(
                message=parsed_error.error_message or "Syntax error in query",
                line=line_number,
                column=column_number,
                severity="error",
            )
        ],
    )
