# Copyright 2025 Marimo. All rights reserved.

import ast
import re
from typing import Callable, Literal, Optional, TypedDict, Union

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager

LOGGER = _loggers.marimo_logger()

# DCL: Data Control Language, usually associated with auth (GRANT and REVOKE)
# DML: Data Manipulation Language, usually associated with changing data (INSERT, UPDATE, and DELETE)
# DQL: Data Query Language, usually associated with reading data (SELECT)
# DDL: Data Definition Language, usually associated with creating/altering/dropping tables (CREATE, ALTER, and DROP)
SQL_TYPE = Literal["DDL", "DML", "DQL", "DCL"]
SQLGLOT_DIALECTS = Literal[
    "duckdb", "clickhouse", "mysql", "postgres", "sqlite"
]


class SQLErrorMetadata(TypedDict):
    """Structured metadata for SQL parsing errors."""

    lint_rule: str
    error_type: str
    clean_message: str  # Just the meaningful error without SQL trace
    node_lineno: int
    node_col_offset: int
    sql_statement: str  # Truncated if needed
    sql_line: Optional[int]  # 0-based line within SQL
    sql_col: Optional[int]  # 0-based column within SQL
    context: str


def classify_sql_statement(
    sql_statement: str, dialect: Optional[SQLGLOT_DIALECTS] = None
) -> Union[SQL_TYPE, Literal["unknown"]]:
    """
    Identifies whether a SQL statement is a DDL, DML, or DQL statement.
    """
    DependencyManager.sqlglot.require(why="SQL parsing")

    from sqlglot import exp, parse
    from sqlglot.errors import ParseError

    sql_statement = sql_statement.strip().lower()
    try:
        with _loggers.suppress_warnings_logs("sqlglot"):
            expression_list = parse(sql_statement, dialect=dialect)
    except ParseError as e:
        log_sql_error(
            LOGGER.debug,
            message="Failed to parse SQL statement for classification.",
            exception=e,
            rule_code="MF005",
            node=None,
            sql_content=sql_statement,
        )
        return "unknown"

    for expression in expression_list:
        if expression is None:
            continue

        if bool(
            expression.find(
                exp.Create, exp.Drop, exp.Alter, exp.Attach, exp.Detach
            )
        ):
            return "DDL"
        elif bool(expression.find(exp.Insert, exp.Update, exp.Delete)):
            return "DML"
        else:
            return "DQL"

    return "unknown"


def log_sql_error(
    logger: Callable[..., None],
    *,
    message: str,
    exception: BaseException,
    rule_code: str,
    node: Optional[ast.expr] = None,
    sql_content: str = "",
    context: str = "",
) -> None:
    """Utility to log SQL-related errors with consistent metadata."""
    # Parse SQL position from exception message if available
    sql_line = None
    sql_col = None

    exception_msg = str(exception)
    line_col_match = re.search(r"Line (\d+), Col: (\d+)", exception_msg)
    if line_col_match:
        sql_line = int(line_col_match.group(1)) - 1  # Convert to 0-based
        sql_col = int(line_col_match.group(2)) - 1  # Convert to 0-based

    # Truncate long SQL content
    truncated_sql = sql_content
    if sql_content and len(sql_content) > 200:
        truncated_sql = sql_content[:200] + "..."

    # Create metadata using TypedDict
    metadata: SQLErrorMetadata = {
        "lint_rule": rule_code,
        "error_type": type(exception).__name__,
        "clean_message": exception_msg.split("\n", 1)[0],
        "node_lineno": node.lineno if node else 0,
        "node_col_offset": node.col_offset if node else 0,
        "sql_statement": truncated_sql,
        "sql_line": sql_line,
        "sql_col": sql_col,
        "context": context,
    }

    logger(message, exception, extra=metadata)
