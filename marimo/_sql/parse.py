# Copyright 2025 Marimo. All rights reserved.

from typing import Literal, Optional, Union

import msgspec

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager

LOGGER = _loggers.marimo_logger()


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


class SqlCatalogCheckResult(msgspec.Struct):
    """
    Result of running validation against the database.
    """

    success: bool
    error_message: Optional[str]


def parse_sql(
    query: str, dialect: str
) -> tuple[Optional[SqlParseResult], Optional[str]]:
    """Parses an SQL query. Returns syntax errors.
    Does not check for catalog errors (incorrect table names, etc).
    Currently only supports DuckDB.

    Args:
        query (str): The SQL query to parse.
        dialect (str): The dialect of the SQL query.

    Returns:
        tuple[SqlParseResult, str]: SqlParseResult and unexpected errors
    """
    dialect = dialect.strip().lower()

    try:
        if "duckdb" in dialect:
            return _parse_sql_duckdb(query)
        else:
            return None, "Unsupported dialect: " + dialect
    except Exception as e:
        return None, str(e)


class DuckDBParseError(msgspec.Struct):
    error: bool
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_subtype: Optional[str] = None
    position: Optional[Union[int, str]] = None


# skip to reduce the response size
# the response doesn't matter too much, we are interested in the errors
JSON_SERIALIZE_LEGACY_QUERY = "SELECT JSON_SERIALIZE_SQL(CAST(? AS VARCHAR), skip_null := true, skip_empty := true, skip_default := true)"
JSON_SERIALIZE_QUERY = "SELECT JSON_SERIALIZE_SQL(?, skip_null := true, skip_empty := true, skip_default := true)"


def _parse_sql_duckdb(
    query: str,
) -> tuple[Optional[SqlParseResult], Optional[str]]:
    """Parse an SQL query using DuckDB. Returns parse result and unexpected errors.

    Note:
    - Only SELECT statements support json_serialize_sql
    - Invalid function names do not throw errors
    - Some syntax errors do not throw errors since they are not errors in the AST parser
    """
    if not DependencyManager.duckdb.has():
        return None, "DuckDB not installed"

    import duckdb

    json_serialize_query = (
        JSON_SERIALIZE_QUERY
        if duckdb.__version__ >= "1.1.0"
        else JSON_SERIALIZE_LEGACY_QUERY
    )

    relation = duckdb.execute(json_serialize_query, [query])
    fetch_result = relation.fetchone()
    if fetch_result is None:
        return None, "No result from DuckDB parse query"

    parse_response = fetch_result[0]
    parsed_error = msgspec.json.decode(parse_response, type=DuckDBParseError)

    if not parsed_error.error:
        return SqlParseResult(success=True, errors=[]), None

    if parsed_error.error_type == "not implemented":
        # This is a valid query, but not supported by DuckDB
        # Only SELECT statements support json_serialize_sql
        return SqlParseResult(success=True, errors=[]), None

    position = int(parsed_error.position or 0)
    subquery = query[:position]
    line_number = subquery.count("\n") + 1
    column_number = position - subquery.rfind("\n") - 1

    sql_parse_result = SqlParseResult(
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
    return sql_parse_result, None
