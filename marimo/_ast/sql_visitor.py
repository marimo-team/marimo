# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import re
from typing import Any, Optional

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

    def remove_comments(sql: str) -> str:
        # Function to replace comments with spaces, preserving newlines
        def replace_with_spaces(match: re.Match[Any]) -> str:
            return " " * len(match.group())

        # Split the SQL into strings and non-strings
        parts = re.split(r'(\'(?:\'\'|[^\'])*\'|"(?:""|[^"])*")', sql)

        for i in range(0, len(parts), 2):
            # Remove single-line comments
            parts[i] = re.sub(
                r"--.*$", replace_with_spaces, parts[i], flags=re.MULTILINE
            )

            # Remove multi-line comments
            parts[i] = re.sub(r"/\*[\s\S]*?\*/", replace_with_spaces, parts[i])

        # Join the parts back together
        return "".join(parts)

    sql_statement = remove_comments(sql_statement)

    tokens = duckdb.tokenize(sql_statement)
    created_tables: list[str] = []
    i = 0

    def token_str(i: int) -> str:
        token = tokens[i]
        start = token[0]
        end = len(sql_statement) - 1
        if i + 1 < len(tokens):
            end = tokens[i + 1][0]
        return sql_statement[start:end].strip()

    def keyword_token_str(i: int) -> str:
        return token_str(i).lower()

    def token_type(i: int) -> str:
        return tokens[i][1]

    while i < len(tokens):
        if (
            keyword_token_str(i) == "create"
            and token_type(i) == duckdb.token_type.keyword
        ):
            i += 1
            if i < len(tokens) and keyword_token_str(i) == "or":
                i += 2  # Skip 'OR REPLACE'
            if i < len(tokens) and keyword_token_str(i) in (
                "temporary",
                "temp",
            ):
                i += 1  # Skip 'TEMPORARY' or 'TEMP'
            if i < len(tokens) and keyword_token_str(i) == "table":
                i += 1
                if i < len(tokens) and keyword_token_str(i) == "if":
                    i += 3  # Skip 'IF NOT EXISTS'
                if i < len(tokens):
                    table_name = token_str(i)
                    # Remove quotes if present
                    if table_name.startswith('"') and table_name.endswith('"'):
                        table_name = table_name[1:-1]

                    created_tables.append(table_name)
        i += 1

    return created_tables
