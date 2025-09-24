# Copyright 2025 Marimo. All rights reserved.
import ast
import re
from typing import TYPE_CHECKING, Callable, Optional, TypedDict

from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    from marimo._messaging.errors import MarimoSQLError

from marimo import _loggers

LOGGER = _loggers.marimo_logger()


class MarimoSQLException(Exception):
    """Exception raised for SQL-related errors in marimo."""

    def __init__(
        self,
        message: str,
        sql_statement: str = "",
        sql_line: Optional[int] = None,
        sql_col: Optional[int] = None,
        hint: Optional[str] = None,
    ):
        super().__init__(message)
        self.sql_statement = sql_statement
        self.sql_line = sql_line
        self.sql_col = sql_col
        self.hint = hint


class SQLErrorMetadata(TypedDict):
    """Structured metadata for SQL parsing errors."""

    lint_rule: str
    error_type: str
    clean_message: str
    hint: Optional[str]
    node_lineno: int
    node_col_offset: int
    sql_statement: str
    sql_line: Optional[int]
    sql_col: Optional[int]
    context: str


def is_sql_parse_error(exception: BaseException) -> bool:
    """Check if the exception is a SQL parsing error."""
    # Check for DuckDB exceptions first (most common)
    if DependencyManager.duckdb.has():
        try:
            import duckdb

            # Errors are general enough to capture all meaningful SQL issues.
            # NB. Errors like Binder/CatalogException are under ProgrammingError.
            # The definitions can be found here:
            # https://github.com/duckdb/duckdb-python/blob/0ee500cfa35fc07bf81ed02e8ab6984ea1f665fd/duckdb/__init__.pyi#L82
            if isinstance(
                exception,
                (
                    duckdb.ParserException,
                    duckdb.ProgrammingError,
                    duckdb.IOException,
                    duckdb.OperationalError,
                    duckdb.IntegrityError,
                    duckdb.DataError,
                ),
            ):
                return True
        except ImportError:
            pass

    # Check for SQLGlot exceptions
    if DependencyManager.sqlglot.has():
        try:
            from sqlglot.errors import ParseError

            # Definitions can be found here:
            # https://sqlglot.com/sqlglot/errors.html
            if isinstance(exception, ParseError):
                return True
        except ImportError:
            pass

    return isinstance(exception, MarimoSQLException)


def extract_sql_position(
    exception_msg: str,
) -> tuple[Optional[int], Optional[int]]:
    """Extract line and column position from SQL exception message."""
    # SqlGlot format: "Line 1, Col: 15"
    line_col_match = re.search(r"Line (\d+), Col: (\d+)", exception_msg)
    if line_col_match:
        return (
            int(line_col_match.group(1)) - 1,  # Convert to 0-based
            int(line_col_match.group(2)) - 1,
        )

    # DuckDB format: "LINE 4:" (line only)
    line_only_match = re.search(r"LINE (\d+):", exception_msg)
    if line_only_match:
        return (
            int(line_only_match.group(1)) - 1,  # Convert to 0-based
            None,  # No column information
        )

    # SQLGlot format variations
    sqlglot_match = re.search(
        r"line (\d+), col (\d+)", exception_msg, re.IGNORECASE
    )
    if sqlglot_match:
        return (
            int(sqlglot_match.group(1)) - 1,
            int(sqlglot_match.group(2)) - 1,
        )

    return None, None


def create_sql_error_metadata(
    exception: BaseException,
    *,
    rule_code: str,
    node: Optional[ast.expr] = None,
    sql_content: str = "",
    context: str = "",
) -> SQLErrorMetadata:
    """Create structured SQL error metadata from an exception.

    This is the single source of truth for parsing SQL exceptions into metadata.
    """
    exception_msg = str(exception)
    sql_line, sql_col = extract_sql_position(exception_msg)

    # Truncate long SQL content
    truncated_sql = sql_content
    if sql_content and len(sql_content) > 200:
        truncated_sql = sql_content[:200] + "..."

    # Create clean error message (first line only)
    clean_message = exception_msg.split("\n", 1)[0]

    # Extract helpful DuckDB hints separately (including multiline hints)
    hint = None
    lines = exception_msg.split("\n")
    hint_lines = []

    for line in lines[1:]:
        hint_lines.append(line.strip())

    if hint_lines:
        hint = "\n".join(hint_lines)

    return SQLErrorMetadata(
        lint_rule=rule_code,
        error_type=type(exception).__name__,
        clean_message=clean_message,
        hint=hint,
        node_lineno=node.lineno if node else 0,
        node_col_offset=node.col_offset if node else 0,
        sql_statement=truncated_sql,
        sql_line=sql_line,
        sql_col=sql_col,
        context=context,
    )


def metadata_to_sql_error(metadata: SQLErrorMetadata) -> "MarimoSQLError":
    """Convert SQLErrorMetadata to MarimoSQLError for frontend messaging."""
    from marimo._messaging.errors import MarimoSQLError

    return MarimoSQLError(
        msg=metadata["clean_message"],
        sql_statement=metadata["sql_statement"],
        hint=metadata["hint"],
        sql_line=metadata["sql_line"],
        sql_col=metadata["sql_col"],
        node_lineno=metadata["node_lineno"],
        node_col_offset=metadata["node_col_offset"],
    )


def log_sql_error(
    logger_func: Callable[..., None],
    *,
    message: str,
    exception: BaseException,
    rule_code: str,
    node: Optional[ast.expr] = None,
    sql_content: str = "",
    context: str = "",
) -> None:
    """Log SQL-related errors with structured metadata."""
    # Use centralized metadata creation
    metadata = create_sql_error_metadata(
        exception,
        rule_code=rule_code,
        node=node,
        sql_content=sql_content,
        context=context,
    )

    # Log clean SQL error without traces
    log_msg = message if message else metadata["clean_message"]
    if metadata["sql_line"] is not None and metadata["sql_col"] is not None:
        log_msg += f" (Line {metadata['sql_line'] + 1}, Col {metadata['sql_col'] + 1})"
    if metadata["sql_statement"]:
        log_msg += f"\nSQL: {metadata['sql_statement']}"

    logger_func(log_msg, extra=metadata)


def create_sql_error_from_exception(
    exception: BaseException,
    cell: object,
) -> "MarimoSQLError":
    """Create a MarimoSQLError from a SQL parsing exception."""
    # Get SQL statement from cell
    sql_statement = ""
    if hasattr(cell, "sqls") and cell.sqls:
        sql_statement = str(cell.sqls[0])

    # Check if this is a MarimoSQLException with structured hint data
    if isinstance(exception, MarimoSQLException) and exception.hint:
        # Use the structured hint data from the exception
        from marimo._messaging.errors import MarimoSQLError

        return MarimoSQLError(
            msg=str(exception),
            sql_statement=exception.sql_statement,
            hint=exception.hint,
            sql_line=exception.sql_line,
            sql_col=exception.sql_col,
        )

    # Create metadata using centralized function
    metadata = create_sql_error_metadata(
        exception,
        rule_code="runtime",
        node=None,
        sql_content=sql_statement,
        context="cell_execution",
    )

    # Enhance error messages based on exception type
    exception_type = metadata["error_type"]
    clean_message = metadata["clean_message"]
    if exception_type == "ParserException":
        clean_message = f"SQL syntax error: {clean_message}"
    elif "ParseError" in exception_type:
        clean_message = f"SQL parse error: {clean_message}"
    elif "ProgrammingError" in exception_type:
        clean_message = f"SQL programming error: {clean_message}"

    # Update metadata with enhanced message
    enhanced_metadata = metadata.copy()
    enhanced_metadata["clean_message"] = clean_message

    # Convert to MarimoSQLError using converter
    return metadata_to_sql_error(enhanced_metadata)
