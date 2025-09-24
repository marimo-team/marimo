# Copyright 2025 Marimo. All rights reserved.
from typing import Callable, Optional, TypedDict

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager

LOGGER = _loggers.marimo_logger()

DEFAULT_DIALECT = "duckdb"


class MarimoSQLException(Exception):
    """Exception raised for SQL-related errors in marimo."""

    def __init__(
        self,
        message: str,
        error_type: str,
        codeblock: Optional[str],
    ):
        super().__init__(message)
        self.error_type = error_type
        self.codeblock = codeblock


class SQLErrorMetadata(TypedDict):
    """Structured metadata for SQL parsing errors."""

    lint_rule: str
    error_type: str
    message: str
    codeblock: Optional[str]
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


def split_error_message(exception_msg: str) -> tuple[Optional[str], str]:
    """Split an exception message into (error_type, error_message). If no splits, return error message entirely."""
    split_parts = exception_msg.split(":")
    if len(split_parts) == 1:
        return None, exception_msg.strip()

    error_type = split_parts[0].strip()
    error_message = ":".join(split_parts[1:]).strip()
    return error_type, error_message


def exception_message_to_metadata(
    exception_msg: str, dialect: str
) -> tuple[str, Optional[str], Optional[str]]:
    """Convert an exception message to a tuple of (message, error_type, codeblock)."""
    if dialect == "duckdb":
        error_type, error_message = split_error_message(exception_msg)

        # Extract codeblock for DuckDB errors
        codeblock = None
        line_block = error_message.find("LINE ")
        if line_block != -1:
            # Extract the LINE section as codeblock
            codeblock = error_message[line_block:].strip()
            # Remove the codeblock from the main error message
            error_message = error_message[:line_block].strip()

        return error_message, error_type, codeblock
    else:
        # Generic parsing - no codeblock extraction
        error_type, error_message = split_error_message(exception_msg)
        return error_message, error_type, None


def create_sql_error_metadata(
    exception_message: str,
    *,
    dialect: str,
    rule_code: str,
    context: str = "",
) -> SQLErrorMetadata:
    """Create structured SQL error metadata from an exception.

    This is the single source of truth for parsing SQL exceptions into metadata.
    """
    message, error_type, codeblock = exception_message_to_metadata(
        exception_message, dialect
    )
    return SQLErrorMetadata(
        lint_rule=rule_code,
        error_type=error_type or "Parse Error",
        message=message,
        codeblock=codeblock,
        context=context,
    )


def log_sql_error(
    logger_func: Callable[..., None],
    *,
    message: str,
    exception: BaseException,
    rule_code: str,
    context: str = "",
) -> None:
    """Log SQL-related errors with structured metadata."""
    # Use centralized metadata creation
    metadata = create_sql_error_metadata(
        str(exception),
        dialect=DEFAULT_DIALECT,
        rule_code=rule_code,
        context=context,
    )

    # Log SQL error without traces
    log_msg = message if message else metadata["message"]
    logger_func(log_msg, extra=metadata)


def create_sql_error_from_exception(
    exception: BaseException,
) -> SQLErrorMetadata:
    """Create a MarimoSQLError from a SQL parsing exception."""
    # Check if this is a MarimoSQLException with structured hint data
    if isinstance(exception, MarimoSQLException):
        return SQLErrorMetadata(
            lint_rule="runtime",
            error_type=exception.error_type,
            message=str(exception),
            codeblock=exception.codeblock,
            context="cell_execution",
        )

    metadata = create_sql_error_metadata(
        str(exception),
        dialect=DEFAULT_DIALECT,
        rule_code="runtime",
        context="cell_execution",
    )

    return metadata
