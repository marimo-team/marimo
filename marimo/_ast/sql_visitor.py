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


class TokenExtractor:
    def __init__(self, sql_statement: str, tokens: list[Any]) -> None:
        self.sql_statement = sql_statement
        self.tokens = tokens

    def token_str(self, i: int) -> str:
        sql_statement, tokens = self.sql_statement, self.tokens
        token = tokens[i]
        start = token[0]

        # If it starts with a quote, find the matching end quote
        if sql_statement[start] == '"':
            end = sql_statement.find('"', start + 1) + 1
        elif sql_statement[start] == "'":
            end = sql_statement.find("'", start + 1) + 1
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

    def is_keyword(self, i: int, match: str) -> bool:
        import duckdb

        if self.tokens[i][1] != duckdb.token_type.keyword:
            return False
        return self.token_str(i).lower() == match

    def strip_quotes(self, token: str) -> str:
        if token.startswith('"') and token.endswith('"'):
            return token.strip('"')
        elif token.startswith("'") and token.endswith("'"):
            return token.strip("'")
        return token


def find_created_tables_and_attached_databases(
    sql_statement: str,
) -> tuple[list[str], list[str]]:
    """
    Find the tables created, databases attached in a SQL statement.

    This function uses the DuckDB tokenizer to find the tables created
    and databases attached in a SQL statement. It returns a list of the table
    names created and databases attached in the statement.

    Args:
        sql_statement: The SQL statement to parse.

    Returns:
        A tuple of a list of table names created and a list of databases
        attached in the statement.
    """
    if not DependencyManager.duckdb.has():
        return [], []

    import duckdb

    tokens = duckdb.tokenize(sql_statement)
    token_extractor = TokenExtractor(
        sql_statement=sql_statement, tokens=tokens
    )
    created_tables: list[str] = []
    created_dbs: list[str] = []
    i = 0

    # See
    #
    #   https://duckdb.org/docs/sql/statements/create_table#syntax
    #
    # for the CREATE TABLE syntax, and
    #
    #   https://duckdb.org/docs/sql/statements/attach#attach-syntax
    #
    # for ATTACH syntax
    while i < len(tokens):
        if token_extractor.is_keyword(i, "create"):
            i += 1
            if i < len(tokens) and token_extractor.is_keyword(i, "or"):
                i += 2  # Skip 'OR REPLACE'
            if i < len(tokens) and (
                token_extractor.is_keyword(i, "temporary")
                or token_extractor.is_keyword(i, "temp")
            ):
                i += 1  # Skip 'TEMPORARY' or 'TEMP'
            if i < len(tokens) and token_extractor.is_keyword(i, "table"):
                i += 1
                if i < len(tokens) and token_extractor.is_keyword(i, "if"):
                    i += 3  # Skip 'IF NOT EXISTS'
                if i < len(tokens):
                    table_name = token_extractor.strip_quotes(
                        token_extractor.token_str(i)
                    )
                    created_tables.append(table_name)
        elif token_extractor.is_keyword(i, "attach"):
            db_name = None
            i += 1
            if i < len(tokens) and token_extractor.is_keyword(i, "database"):
                i += 1  # Skip 'DATABASE'
            if i < len(tokens) and token_extractor.is_keyword(i, "if"):
                i += 3  # Skip "IF NOT EXISTS"
            if i < len(tokens):
                db_name = token_extractor.strip_quotes(
                    token_extractor.token_str(i)
                )
                if "." in db_name:
                    # strip the extension from the name
                    db_name = db_name.split(".")[0]
            if i + 1 < len(tokens) and token_extractor.is_keyword(i + 1, "as"):
                # Skip over database-path 'AS'
                i += 2
                # AS clause gets precedence in creating database
                db_name = token_extractor.strip_quotes(
                    token_extractor.token_str(i)
                )
            if db_name is not None:
                created_dbs.append(db_name)

        i += 1

    return created_tables, created_dbs


def find_from_targets(
    sql_statement: str,
) -> list[str]:
    """
    Find tokens following the FROM keyword, which may be tables or databases.

    Args:
        sql_statement: The SQL statement to parse.

    Returns:
        A list of names following the FROM keyword.
    """
    if not DependencyManager.duckdb.has():
        return []

    import duckdb

    tokens = duckdb.tokenize(sql_statement)
    token_extractor = TokenExtractor(
        sql_statement=sql_statement, tokens=tokens
    )
    refs: list[str] = []
    i = 0

    while i < len(tokens):
        if token_extractor.is_keyword(i, "from"):
            i += 1
            if i < len(tokens):
                # TODO(akshayka): this is maybe a name, but it's totally
                # possible that it's not a name -- could be a function (such as
                # range), or the start of a subquery, ...
                name = token_extractor.strip_quotes(
                    token_extractor.token_str(i)
                )
                if "." in name:
                    # get the database name
                    name = name.split(".")[0]
                refs.append(name)
        i += 1

    return refs