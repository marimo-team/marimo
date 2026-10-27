# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from textwrap import dedent
from typing import Any, Literal

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager

LOGGER = _loggers.marimo_logger()

COMMON_FILE_EXTENSIONS = (
    ".csv",
    ".parquet",
    ".json",
    ".txt",
    ".db",
    ".tsv",
    ".xlsx",
)

SQLKind = Literal["table", "view", "schema", "catalog"]

SQLTypes = SQLKind | Literal["any"]


class SQLVisitor(ast.NodeVisitor):
    """
    Find any SQL queries in the AST.
    This should be inside a function called `.execute` or `.sql`.
    """

    def __init__(self, raw: bool = False) -> None:
        super().__init__()
        self._sqls: list[str] = []
        self._raw = raw

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
                sql: str | None = None
                if isinstance(first_arg, ast.Constant):
                    sql = first_arg.value
                elif isinstance(first_arg, ast.JoinedStr):
                    if self._raw:
                        f_sql = ast.unparse(first_arg)
                        sql = dedent(
                            f_sql[1:]
                            .strip(f_sql[1])
                            .encode()
                            .decode("unicode_escape")
                        )
                    else:
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

    The placeholder "1" is used instead of "null" because it's valid in more
    SQL contexts. For example, interval expressions like `interval '{days} days'`
    become `interval '1 days'` which parses correctly, whereas `interval 'null days'`
    would cause a parsing error (issue #7717).
    """

    def print_part(part: ast.expr) -> str:
        if isinstance(part, ast.FormattedValue):
            return print_part(part.value)
        elif isinstance(part, ast.JoinedStr):
            return normalize_sql_f_string(part)
        elif isinstance(part, ast.Constant):
            return str(part.value)
        else:
            # Use "1" as placeholder - it's valid in more SQL contexts than "null"
            # (e.g., interval expressions like `interval '1 days'`)
            return "1"

    result = "".join(print_part(part) for part in node.values)
    return result


class _TokenExtractor:
    def __init__(self, sql_statement: str, tokens: list[Any]) -> None:
        # DuckDB token positions are UTF-8 byte offsets.
        self.sql_statement = sql_statement.encode("utf-8")
        self.tokens = tokens

    def token_str(self, i: int) -> str:
        sql_statement, tokens = self.sql_statement, self.tokens
        token = tokens[i]
        start = token[0]

        # If it starts with a quote, find the matching end quote
        if sql_statement.startswith(b'"', start):
            end = sql_statement.find(b'"', start + 1) + 1
        elif sql_statement.startswith(b"'", start):
            end = sql_statement.find(b"'", start + 1) + 1
        elif sql_statement.startswith(b"e'", start):
            start += 1
            end = sql_statement.find(b"'", start + 1) + 1
        else:
            # For non-quoted tokens, find until space or comment
            maybe_end = re.search(rb"[\s\-/]", sql_statement[start:])
            end = (
                start + maybe_end.start() if maybe_end else len(sql_statement)
            )
            if i + 1 < len(tokens):
                # For tokens squashed together e.g. '(select' or 'x);;'
                # in (select * from x);;
                end = min(end, tokens[i + 1][0])

        return sql_statement[start:end].decode("utf-8")

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
    tables: list[SQLRef] = field(default_factory=list)
    views: list[SQLRef] = field(default_factory=list)
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
    # DuckDB 2 emits comments as tokens; definition matching needs only syntax.
    comment_type = getattr(duckdb.token_type, "comment", None)
    if comment_type is not None:
        tokens = [token for token in tokens if token[1] != comment_type]
    token_extractor = _TokenExtractor(
        sql_statement=sql_statement, tokens=tokens
    )
    created_tables: list[SQLRef] = []
    created_views: list[SQLRef] = []
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

                    parts: list[str] = []
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

                    if is_table:
                        # only add the table name
                        created_tables.append(SQLRef.from_parts(parts))
                        # add the catalog and schema if exist
                        if len(parts) == 3:
                            reffed_catalogs.append(parts[0])
                            reffed_schemas.append(parts[1])
                        if len(parts) == 2:
                            reffed_catalogs.append(parts[0])
                    elif is_view:
                        # only add the table name
                        created_views.append(SQLRef.from_parts(parts))
                        # add the catalog and schema if exist
                        if len(parts) == 3:
                            reffed_catalogs.append(parts[0])
                            reffed_schemas.append(parts[1])
                        if len(parts) == 2:
                            reffed_catalogs.append(parts[0])
                    elif is_schema:
                        # only add the schema name
                        created_schemas.append(
                            SQLRef.from_parts(parts).qualified_name
                        )
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


@dataclass(frozen=True, init=False)
class SQLRef:
    table: str
    qualifiers: tuple[str, ...]
    kind: Literal["table", "schema"]
    _catalog_only: bool = field(repr=False)

    def __init__(
        self,
        table: str,
        schema: str | None = None,
        catalog: str | None = None,
        *,
        qualifiers: tuple[str, ...] | None = None,
        kind: Literal["table", "schema"] = "table",
    ) -> None:
        object.__setattr__(self, "table", table)
        object.__setattr__(self, "kind", kind)
        object.__setattr__(
            self,
            "_catalog_only",
            qualifiers is None and catalog is not None and schema is None,
        )
        object.__setattr__(
            self,
            "qualifiers",
            qualifiers
            if qualifiers is not None
            else tuple(part for part in (catalog, schema) if part is not None),
        )

    @property
    def schema(self) -> str | None:
        return (
            self.qualifiers[-1]
            if self.qualifiers and not self._catalog_only
            else None
        )

    @property
    def catalog(self) -> str | None:
        return (
            self.qualifiers[0]
            if len(self.qualifiers) > 1 or self._catalog_only
            else None
        )

    @property
    def parts(self) -> tuple[str, ...]:
        return (*self.qualifiers, self.table)

    @classmethod
    def from_parts(cls, parts: list[str]) -> SQLRef:
        return cls(
            table=parts[-1].lower(),
            qualifiers=tuple(part.lower() for part in parts[:-1]),
        )

    @classmethod
    def from_qualified_name(cls, name: str) -> SQLRef:
        parts = re.findall(r'"(?:[^"]|"")*"|[^.]+', name)
        return cls.from_parts(
            [
                part[1:-1].replace('""', '"') if part.startswith('"') else part
                for part in parts
            ]
        )

    @property
    def qualified_name(self) -> str:
        def quote_part(part: str) -> str:
            if "." in part or '"' in part:
                return '"' + part.replace('"', '""') + '"'
            return part

        return ".".join(quote_part(part.lower()) for part in self.parts)

    def split_catalog(
        self, catalogs: frozenset[str]
    ) -> tuple[str | None, tuple[str, ...]]:
        parts = tuple(part.lower() for part in self.parts)
        has_namespace = len(parts) > 1 or self.kind == "schema"
        if has_namespace and (
            self._catalog_only or parts[0] in catalogs | {"memory", "temp"}
        ):
            return parts[0], parts[1:]
        return None, parts

    def matches_hierarchical_ref(
        self,
        name: str,
        definition: SQLRef,
        kind: SQLTypes = "any",
        *,
        catalogs: frozenset[str] = frozenset(),
    ) -> bool:
        own_parts = tuple(part.lower() for part in self.parts)
        name = name.lower()
        if kind == "catalog":
            namespace = own_parts if self.kind == "schema" else own_parts[:-1]
            return (
                bool(namespace)
                and name == namespace[0] == definition.parts[0].lower()
            )

        own_catalog, own_path = self.split_catalog(catalogs)
        ref_catalog, parts = (
            definition.split_catalog(catalogs)
            if definition.qualifiers
            else (None, (definition.table.lower(),))
        )
        if (
            self.kind == "schema"
            or kind == "schema"
            or (self.qualifiers and definition.qualifiers)
        ) and (own_catalog or "memory") != (ref_catalog or "memory"):
            return False
        if kind == "schema":
            namespace = own_path if self.kind == "schema" else own_path[:-1]
            return namespace[: len(parts)] == parts
        if self.kind == "schema":
            return False
        if kind == "any" and name != own_parts[-1]:
            return name in own_parts[:-1]

        if own_catalog is not None and len(own_path) == 1:
            own_path = ("main", *own_path)
        if ref_catalog is not None and len(parts) == 1:
            parts = ("main", *parts)
        if self.qualifiers and definition.qualifiers:
            return name == own_parts[-1] and own_path == parts
        return name == own_parts[-1]

    def contains_hierarchical_ref(self, ref: str, kind: str) -> bool:
        if kind in ("table", "view"):
            if self.kind == "schema":
                return False
            return ref.lower() == self.table.lower()
        if kind in ("catalog", "schema"):
            namespace = (
                self.parts if self.kind == "schema" else self.qualifiers
            )
            return ref.lower() in (part.lower() for part in namespace)
        return False


def find_sql_refs(sql_statement: str) -> set[SQLRef]:
    """
    Find table and schema references in a SQL statement.

    Args:
        sql_statement: The SQL statement to parse.

    Returns:
        A set of unique SQLRefs, one for each table reference in the statement.
        Eg. SELECT * FROM schema1.test_table INNER JOIN schema2.test_table2
        would return two SQLRefs, one for the first table and one for the second.

    Note:
        When providing only a single qualification,
        DuckDB will interpret as either a catalog or a schema, as long as there are no conflicts.

        Eg. SELECT * FROM my_db.my_table, my_db can be a catalog or schema. If a catalog exists,
        then it would resolve to my_db.main.my_table.

        At the moment, we don't know this, so my_db is treated as a schema.
    """

    # Use sqlglot to parse ast (https://github.com/tobymao/sqlglot/blob/main/posts/ast_primer.md)

    DependencyManager.sqlglot.require(why="SQL parsing")

    from sqlglot import exp, parse
    from sqlglot.errors import OptimizeError
    from sqlglot.optimizer.scope import build_scope

    def get_ref_from_table(table: exp.Table) -> SQLRef | None:
        # The variables might be empty strings, if they are, we set them to None
        try:
            table_name = table.name or None
        except AttributeError:
            # sqlglot may return Table nodes with this=None (e.g. DROP SCHEMA)
            return None
        if table_name is None:
            return None
        if "://" in table_name or table_name.endswith(COMMON_FILE_EXTENSIONS):
            return None
        parts = [part.name for part in table.parts]
        return SQLRef(table=parts[-1], qualifiers=tuple(parts[:-1]))

    from sqlglot.errors import ParseError

    try:
        with _loggers.suppress_warnings_logs("sqlglot"):
            expression_list = parse(sql_statement, dialect="duckdb")
    except ParseError:
        return set()

    refs: set[SQLRef] = set()

    def is_cte_reference(table: exp.Table) -> bool:
        if table.db or table.catalog:
            return False

        target = (
            table.parent if isinstance(table.parent, exp.Schema) else table
        )
        if (
            isinstance(target.parent, (exp.Insert, exp.Update, exp.Delete))
            and target.parent.this is target
        ):
            return False

        table_name = table.name.lower()
        node: exp.Expr = table
        while parent := node.parent:
            with_clause = (
                parent
                if isinstance(parent, exp.With)
                else parent.args.get("with_")
            )
            if isinstance(with_clause, exp.With) and node is not with_clause:
                for cte in with_clause.expressions:
                    if cte is node and not with_clause.args.get("recursive"):
                        break
                    if cte.alias.lower() == table_name:
                        return True
                    if cte is node:
                        break
            node = parent
        return False

    def _collect_table_refs_excluding_ctes(expression: exp.Expression) -> None:
        for table in expression.find_all(exp.Table):
            if not is_cte_reference(table):
                if ref := get_ref_from_table(table):
                    refs.add(ref)

    for expression in expression_list:
        if expression is None:
            continue

        requires_table_scan = bool(
            expression.find(
                exp.Update,
                exp.Insert,
                exp.Delete,
                exp.Describe,
                exp.Summarize,
                exp.Pivot,
                exp.Analyze,
                exp.Drop,
                exp.TruncateTable,
                exp.Copy,
            )
        )
        if requires_table_scan:
            _collect_table_refs_excluding_ctes(expression)  # type: ignore[arg-type]

        # build_scope only works for select statements.
        # It may raise OptimizeError for valid SQL with duplicate aliases
        # (e.g., "SELECT * FROM (SELECT 1 as x), (SELECT 2 as x)")
        # In that case, fall back to extracting table references directly.
        try:
            if root := build_scope(expression):
                for scope in root.traverse():  # type: ignore
                    for _node, source in scope.selected_sources.values():
                        # SQLGlot can expose DML CTE references as plain tables.
                        if isinstance(source, exp.Table):
                            if requires_table_scan and is_cte_reference(
                                source
                            ):
                                continue
                            if ref := get_ref_from_table(source):
                                refs.add(ref)
        except OptimizeError:
            _collect_table_refs_excluding_ctes(expression)  # type: ignore[arg-type]

    return refs
