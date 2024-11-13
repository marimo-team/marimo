# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any, List, Optional

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager

LOGGER = _loggers.marimo_logger()


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
            # Just add null as a placeholder for {...} expressions
            return "null"

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
        elif sql_statement[start:].startswith("e'"):
            start += 1
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


@dataclass
class SQLDefs:
    tables: list[str] = field(default_factory=list)
    views: list[str] = field(default_factory=list)
    schemas: list[str] = field(default_factory=list)
    catalogs: list[str] = field(default_factory=list)

    # The schemas referenced in the CREATE SQL statement
    reffed_schemas: list[str] = field(default_factory=list)
    # The catalogs referenced in the CREATE SQL statement
    reffed_catalogs: list[str] = field(default_factory=list)


def find_sql_defs(sql_statement: str) -> SQLDefs:
    """
    Find the tables, views, schemas, and catalogs created/attached in a SQL statement.

    This function uses the DuckDB tokenizer to find the tables created
    and schemas attached in a SQL statement. It returns a list of the table
    names created, views created, schemas created, and catalogs attached in the
    statement.

    Args:
        sql_statement: The SQL statement to parse.

    Returns:
        SQLDefs
    """
    if not DependencyManager.duckdb.has():
        return SQLDefs()

    import duckdb

    tokens = duckdb.tokenize(sql_statement)
    token_extractor = TokenExtractor(
        sql_statement=sql_statement, tokens=tokens
    )
    created_tables: list[str] = []
    created_views: list[str] = []
    created_schemas: list[str] = []
    created_catalogs: list[str] = []

    reffed_schemas: list[str] = []
    reffed_catalogs: list[str] = []
    i = 0

    # See
    #
    #   https://duckdb.org/docs/sql/statements/create_table#syntax
    #   https://duckdb.org/docs/sql/statements/create_view#syntax
    #
    # for the CREATE syntax, and
    #
    #   https://duckdb.org/docs/sql/statements/attach#attach-syntax
    #
    # for ATTACH syntax
    while i < len(tokens):
        if token_extractor.is_keyword(i, "create"):
            # CREATE TABLE, CREATE VIEW, CREATE SCHEMA have the same syntax
            i += 1
            if i < len(tokens) and token_extractor.is_keyword(i, "or"):
                i += 2  # Skip 'OR REPLACE'
            if i < len(tokens) and (
                token_extractor.is_keyword(i, "temporary")
                or token_extractor.is_keyword(i, "temp")
            ):
                i += 1  # Skip 'TEMPORARY' or 'TEMP'

            is_table = False
            is_view = False
            is_schema = False

            if i < len(tokens) and (
                (is_table := token_extractor.is_keyword(i, "table"))
                or (is_view := token_extractor.is_keyword(i, "view"))
                or (is_schema := token_extractor.is_keyword(i, "schema"))
            ):
                i += 1
                if i < len(tokens) and token_extractor.is_keyword(i, "if"):
                    i += 3  # Skip 'IF NOT EXISTS'
                if i < len(tokens):
                    # Get table name parts, this could be:
                    # - catalog.schema.table
                    # - catalog.table (this is shorthand for catalog.main.table)
                    # - table

                    parts: List[str] = []
                    while i < len(tokens):
                        part = token_extractor.strip_quotes(
                            token_extractor.token_str(i)
                        )
                        parts.append(part)
                        # next token is a dot, so we continue getting parts
                        if (
                            i + 1 < len(tokens)
                            and token_extractor.token_str(i + 1) == "."
                        ):
                            i += 2
                            continue
                        break

                    # Assert parts is either 1, 2, or 3
                    if len(parts) not in (1, 2, 3):
                        LOGGER.warning(
                            "Unexpected number of parts in CREATE TABLE: %s",
                            parts,
                        )

                    if is_table:
                        # only add the table name
                        created_tables.append(parts[-1])
                        # add the catalog and schema if exist
                        if len(parts) == 3:
                            reffed_catalogs.append(parts[0])
                            reffed_schemas.append(parts[1])
                        if len(parts) == 2:
                            reffed_catalogs.append(parts[0])
                    elif is_view:
                        # only add the table name
                        created_views.append(parts[-1])
                        # add the catalog and schema if exist
                        if len(parts) == 3:
                            reffed_catalogs.append(parts[0])
                            reffed_schemas.append(parts[1])
                        if len(parts) == 2:
                            reffed_catalogs.append(parts[0])
                    elif is_schema:
                        # only add the schema name
                        created_schemas.append(parts[-1])
                        # add the catalog if exist
                        if len(parts) == 2:
                            reffed_catalogs.append(parts[0])
        elif token_extractor.is_keyword(i, "attach"):
            catalog_name = None
            i += 1
            if i < len(tokens) and token_extractor.is_keyword(i, "database"):
                i += 1  # Skip 'DATABASE'
            if i < len(tokens) and token_extractor.is_keyword(i, "if"):
                i += 3  # Skip "IF NOT EXISTS"
            if i < len(tokens):
                catalog_name = token_extractor.strip_quotes(
                    token_extractor.token_str(i)
                )
                if "." in catalog_name:
                    # e.g. "db.sqlite"
                    # strip the extension from the name
                    catalog_name = catalog_name.split(".")[0]
                if ":" in catalog_name:
                    # e.g. "md:my_db"
                    # split on ":" and take the second part
                    catalog_name = catalog_name.split(":")[1]
            if i + 1 < len(tokens) and token_extractor.is_keyword(i + 1, "as"):
                # Skip over database-path 'AS'
                i += 2
                # AS clause gets precedence in creating database
                if i < len(tokens):
                    catalog_name = token_extractor.strip_quotes(
                        token_extractor.token_str(i)
                    )
            if catalog_name is not None:
                created_catalogs.append(catalog_name)

        i += 1

    # Remove 'memory' from catalogs, as this is the default and doesn't have a def
    if "memory" in reffed_catalogs:
        reffed_catalogs.remove("memory")
    # Remove 'main' from schemas, as this is the default and doesn't have a def
    if "main" in reffed_schemas:
        reffed_schemas.remove("main")

    return SQLDefs(
        tables=created_tables,
        views=created_views,
        schemas=created_schemas,
        catalogs=created_catalogs,
        reffed_schemas=reffed_schemas,
        reffed_catalogs=reffed_catalogs,
    )


# TODO(akshayka): there are other kinds of refs to find; this should be
# find_sql_refs
def find_sql_refs(
    sql_statement: str,
) -> list[str]:
    """
    Find table and schema references in a SQL statement.

    Args:
        sql_statement: The SQL statement to parse.

    Returns:
        A list of table and schema names referenced in the statement.
    """
    if not DependencyManager.duckdb.has():
        return []

    import duckdb

    tokens = duckdb.tokenize(sql_statement)
    token_extractor = TokenExtractor(
        sql_statement=sql_statement, tokens=tokens
    )
    refs: list[str] = []
    cte_names: set[str] = set()
    i = 0

    # First pass - collect CTE names
    while i < len(tokens):
        if token_extractor.is_keyword(i, "with"):
            i += 1
            # Handle optional parenthesis after WITH
            if token_extractor.token_str(i) == "(":
                i += 1
            while i < len(tokens):
                if token_extractor.is_keyword(i, "select"):
                    break
                if (
                    token_extractor.token_str(i) == ","
                    or token_extractor.token_str(i) == "("
                ):
                    i += 1
                    continue
                cte_name = token_extractor.strip_quotes(
                    token_extractor.token_str(i)
                )
                if not token_extractor.is_keyword(i, "as"):
                    cte_names.add(cte_name)
                i += 1
                if token_extractor.is_keyword(i, "as"):
                    break
        i += 1

    # Second pass - collect references excluding CTEs
    i = 0
    while i < len(tokens):
        if token_extractor.is_keyword(i, "from") or token_extractor.is_keyword(
            i, "join"
        ):
            i += 1
            if i < len(tokens):
                # Skip over opening parenthesis for subqueries
                if token_extractor.token_str(i) == "(":
                    continue

                # Get table name parts, this could be:
                # - catalog.schema.table
                # - catalog.table (this is shorthand for catalog.main.table)
                # - table

                parts: List[str] = []
                while i < len(tokens):
                    part = token_extractor.strip_quotes(
                        token_extractor.token_str(i)
                    )
                    parts.append(part)
                    # next token is a dot, so we continue getting parts
                    if (
                        i + 1 < len(tokens)
                        and token_extractor.token_str(i + 1) == "."
                    ):
                        i += 2
                        continue
                    break

                if len(parts) == 3:
                    # If its the default in-memory catalog,
                    # only add the table name
                    if parts[0] == "memory":
                        refs.append(parts[2])
                    else:
                        # Just add the catalog and table, skip schema
                        refs.extend([parts[0], parts[2]])
                elif len(parts) == 2:
                    # If its the default in-memory catalog, only add the table
                    if parts[0] == "memory":
                        refs.append(parts[1])
                    else:
                        # It's a catalog and table, add both
                        refs.extend(parts)
                elif len(parts) == 1:
                    # It's a table, make sure it's not a CTE
                    if parts[0] not in cte_names:
                        refs.append(parts[0])
                else:
                    LOGGER.warning(
                        "Unexpected number of parts in SQL reference: %s",
                        parts,
                    )

                i -= 1  # Compensate for outer loop increment
        i += 1

    # Re-use find_sql_defs to find referenced schemas and catalogs during creation.
    defs = find_sql_defs(sql_statement)
    refs.extend(defs.reffed_schemas)
    refs.extend(defs.reffed_catalogs)

    # Remove duplicates while preserving order
    return list(dict.fromkeys(refs))
