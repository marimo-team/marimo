# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import re
from typing import Any, Callable, Literal, Optional, Union

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

    idx_to_offset_dict: dict[int, int] = {}
    try:
        query, idx_to_offset_dict = replace_brackets_with_quotes(query)
    except Exception as e:
        LOGGER.debug(f"Error sanitizing SQL query: {e}")

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

    last_newline_idx = subquery.rfind("\n")
    column_number = position - last_newline_idx - 1

    # Adjust column_number to account for any added quotes from bracket replacements
    # SELECT {id} FRO users
    #             ^ error position should be here
    # SELECT {id} FRO users
    #               ^ user sees this
    # So in this case, we subtract the offset from the column position.
    # If the error is before the brackets, we don't need to add the offset because it just increases the string length
    # Column position will be the same as the user sees.
    error_line_start = last_newline_idx + 1
    cumulative_offset = 0
    for idx, offset in idx_to_offset_dict.items():
        # Only count replacements that are on the same line as the error
        # and come before the error position
        if error_line_start <= idx < position:
            cumulative_offset += offset
    column_number -= cumulative_offset

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


def replace_brackets_with_quotes(sql: str) -> tuple[str, dict[int, int]]:
    """
    Replaces unquoted curly bracket expressions (e.g., {id}) with quoted strings (e.g., '{id}'),
    ignoring brackets already inside single or double quotes.

    Returns the modified SQL and a record mapping the index of each replaced bracket to the
    number of characters added (for offset tracking).

    Args:
        sql (str): The SQL string to process.

    Returns:
        tuple[str, dict[int, int]]: A tuple containing:
            - The modified SQL string
            - A dictionary mapping original bracket positions to the number of characters added (0-based)

    Example:
        replace_brackets_with_quotes("SELECT {id}, '{name}' FROM users")
        # => ("SELECT '{id}', '{name}' FROM users", {7: 2})
    """
    QUOTE_LENGTH = 2  # Length of the added quotes around brackets

    offset_record: dict[int, int] = {}

    # Pattern to match quoted strings or unquoted brackets
    # Groups: 1=double quoted, 2=single quoted, 3=bracket
    pattern = r'("(?:[^"\\]|\\.)*")|(\'(?:[^\'\\]|\\.)*\')|(\{[^}]*\})'

    def replacement_func(match: re.Match[str]) -> str:
        double_quoted = match.group(1)
        single_quoted = match.group(2)
        bracket = match.group(3)

        # If it's a quoted string, return it as-is
        if double_quoted or single_quoted:
            return match.group(0)

        # If it's a bracket, quote it and record the offset
        if bracket:
            offset_record[match.start()] = QUOTE_LENGTH
            return f"'{bracket}'"

        return match.group(0)

    replaced_sql = re.sub(pattern, replacement_func, sql)

    return replaced_sql, offset_record


def format_query_with_globals(
    query: str,
    globals_dict: dict[str, Any],
    missing_key_handler: Callable[[str], str] = lambda key: f"'{key}'",
) -> str:
    """
    Format a query by substituting brace expressions with values from globals_dict.
    Braces inside single-quoted strings (SQL literals) are left untouched.
    Braces inside double-quoted strings (SQL identifiers) are substituted.

    Args:
        query: The SQL query with brace expressions like {var}
        globals_dict: Dictionary mapping variable names to their values
        missing_key_handler: Function to handle missing keys. Defaults to quoting the key.

    Returns:
        The formatted query with substitutions applied

    Example:
        format_query_with_globals("SELECT {col} FROM '{table}'", {"col": "id"})
        # => "SELECT id FROM '{table}'"

        format_query_with_globals("SELECT * FROM '{table}'", {}, lambda key: key.upper())
        # => "SELECT id FROM TABLE"
    """
    # Quick check - if no braces, return as-is
    if "{" not in query or "}" not in query:
        return query

    # Pattern to match single-quoted strings or brace expressions
    # Groups: 1=single quoted string, 2=full brace, 3=brace content (without braces)
    pattern = r"(\'(?:[^\'\\]|\\.)*\')|(\{([^}]*)\})"

    def replacement_func(match: re.Match[str]) -> str:
        raw_query = match.group(0)
        single_quoted = match.group(1)
        has_braces = match.group(2) is not None

        # If it's a single-quoted string, return it as-is
        if single_quoted:
            return raw_query

        if has_braces:
            key = match.group(3)  # The content inside the braces
            if key in globals_dict:
                return str(globals_dict[key])
            return missing_key_handler(key)

        return raw_query

    return re.sub(pattern, replacement_func, query)
