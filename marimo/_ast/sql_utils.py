# Copyright 2025 Marimo. All rights reserved.

from typing import Literal, Optional, Union

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
        LOGGER.debug(
            f"Unable to parse SQL. Error: {e}", extra={"lint_rule": "MF005"}
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
