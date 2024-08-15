# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import re
from typing import Optional

from marimo._dependencies.dependencies import DependencyManager


class SQLVisitor(ast.NodeVisitor):
    """
    Find any SQL queries in the AST.
    This should be inside a function called `.execute` or `.sql`.
    """

    def __init__(self) -> None:
        super().__init__()
        self._sqls: list[str] = []

    def visit_Call(self, node: ast.Call) -> None:
        # Check if the call is a method call and the method is named
        # either 'execute' or 'sql'
        if isinstance(node.func, ast.Attribute) and node.func.attr in (
            "execute",
            "sql",
        ):
            # Check if there are arguments and the first argument is a
            # string or f-string
            if node.args:
                first_arg = node.args[0]
                sql: Optional[str] = None
                if isinstance(first_arg, ast.Constant):
                    sql = first_arg.s
                elif isinstance(first_arg, ast.JoinedStr):
                    sql = normalize_sql_f_string(first_arg)

                if sql is not None:
                    # Append the SQL query to the list
                    self._sqls.append(sql)
        # Continue walking through the AST
        self.generic_visit(node)

    def get_sqls(self) -> list[str]:
        return self._sqls


def normalize_sql_f_string(node: ast.JoinedStr) -> str:
    """
    Normalize a f-string to a string by joining the parts.

    We add placeholder for {...} expressions in the f-string.
    This is so we can create a valid SQL query to be passed to
    other utilities.
    """

    def print_part(part: ast.expr) -> str:
        if isinstance(part, ast.FormattedValue):
            return print_part(part.value)
        elif isinstance(part, ast.JoinedStr):
            return normalize_sql_f_string(part)
        elif isinstance(part, ast.Constant):
            return str(part.s)
        else:
            # Just add '_' as a placeholder for {...} expressions
            return "'_'"

    result = "".join(print_part(part) for part in node.values)
    # remove any double '' created by the f-string
    return result.replace("''", "'")


def find_created_tables(sql_statement: str) -> list[str]:
    """
    Find the tables created in a SQL statement.

    This function uses the DuckDB tokenizer to find the tables created
    in a SQL statement. It returns a list of the table names created
    in the statement.

    Args:
        sql_statement: The SQL statement to parse.

    Returns:
        A list of the table names created in the statement.
    """
    if not DependencyManager.duckdb.has():
        return []

    import duckdb

    tokens = duckdb.tokenize(sql_statement)
    created_tables: list[str] = []
    i = 0

    def token_str(i: int) -> str:
        token = tokens[i]
        start = token[0]

        if sql_statement[start] == '"':
            # If it starts with a quote, find the matching end quote
            end = sql_statement.find('"', start + 1) + 1
        else:
            # For non-quoted tokens, find until space or comment
            maybe_end = re.search(r"[\s\-/]", sql_statement[start:])
            end = (
                start + maybe_end.start() if maybe_end else len(sql_statement)
            )
            if i + 1 < len(tokens):
                # For tokens squashed together e.g. '(select' or 'x);;'
                # in (select * from x);;
                end = min(end, tokens[i + 1][0])

        return sql_statement[start:end]

    def is_keyword(i: int, match: str) -> bool:
        if tokens[i][1] != duckdb.token_type.keyword:
            return False
        return token_str(i).lower() == match

    # See https://duckdb.org/docs/sql/statements/create_table#syntax
    # for more information on the CREATE TABLE syntax.
    while i < len(tokens):
        if is_keyword(i, "create"):
            i += 1
            if i < len(tokens) and is_keyword(i, "or"):
                i += 2  # Skip 'OR REPLACE'
            if i < len(tokens) and (
                is_keyword(i, "temporary") or is_keyword(i, "temp")
            ):
                i += 1  # Skip 'TEMPORARY' or 'TEMP'
            if i < len(tokens) and is_keyword(i, "table"):
                i += 1
                if i < len(tokens) and is_keyword(i, "if"):
                    i += 3  # Skip 'IF NOT EXISTS'
                if i < len(tokens):
                    table_name = token_str(i)
                    # Remove quotes if present
                    if table_name.startswith('"') and table_name.endswith('"'):
                        table_name = table_name[1:-1]

                    created_tables.append(table_name)
        i += 1

    return created_tables
