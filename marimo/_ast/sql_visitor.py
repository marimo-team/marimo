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

                    # Assert parts is either 1, 2, or 3
                    if len(parts) not in (1, 2, 3):
                        LOGGER.warning(
                            "Unexpected number of parts in CREATE TABLE: %s",
                            parts,
                            extra={"parts": parts},
                        )

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


@dataclass(frozen=True)
class SQLRef:
    # Tables are synonymous with views,
    # since we can't know the difference in queries
    table: str
    schema: str | None = None
    catalog: str | None = None

    @classmethod
    def from_parts(
        cls,
        parts: list[str],
    ) -> SQLRef:
        catalog = None
        schema = None
        table = ""
        if len(parts) == 3:
            catalog, schema, table = parts
            catalog = catalog.lower()
            schema = schema.lower()
        elif len(parts) == 2:
            schema, table = parts
            schema = schema.lower()
        elif len(parts) == 1:
            table = parts[0]
        return cls(table=table.lower(), schema=schema, catalog=catalog)

    @property
    def qualified_name(self) -> str:
        """Convert a SQLRef to a fully qualified name to be used as a reference in the visitor"""
        parts = []
        if self.catalog is not None:
            parts.append(self.catalog)
        if self.schema is not None:
            parts.append(self.schema)

        # Table is always required
        parts.append(self.table)
        name = ".".join(parts)
        return name.lower()

    def matches_hierarchical_ref(
        self, name: str, ref: str, kind: SQLTypes = "any"
    ) -> bool:
        """
        Determine if a hierarchical reference string matches a SQLRef.

        Args:
            name: The name to match against (could be catalog, schema, or table).
            ref: The fully qualified reference string (e.g., "schema.table", "catalog.schema.table").
            kind: The kind of reference ("table", "view", "schema", "catalog").

        Returns:
            True if the reference matches the SQLRef's structure and values, False otherwise.
        """
        ref = ref.lower()
        name = name.lower()
        parts = ref.split(".")
        num_parts = len(parts)

        if num_parts == 0:
            return False

        if kind == "catalog":
            if self.catalog is not None:
                return name == self.catalog == parts[0]
            # Fallback to schema if catalog is None
            kind = "schema"

        if kind == "schema":
            if num_parts < 3:
                return name == self.schema == parts[0]
            return name == self.schema == parts[1]

        # Otherwise, kind is "table" or "view", and we should check the ordering
        # and return accordingly
        if num_parts == 1:
            # Only table name provided
            return name == self.table == parts[0] and kind in (
                "table",
                "view",
                "any",
            )

        if num_parts == 2:
            # Format: schema.table or catalog.table
            # sqlglot cannot differentiate between schema and catalog
            # so we check if the qualifier matches either
            qualifier, table = parts
            # Try matching as schema or catalog
            if (self.schema, self.catalog) == (None, None):
                return name == self.table == table and kind in (
                    "table",
                    "view",
                    "any",
                )
            if qualifier not in (self.schema, self.catalog):
                return False

            return name in (
                self.catalog,
                self.schema,
                self.table,
            ) and kind in (
                "table",
                "view",
                "catalog",
                "schema",
                "any",
            )

        if num_parts == 3:
            # Format: catalog.schema.table
            catalog, schema, table = parts
            if self.catalog:
                if catalog != self.catalog:
                    return False
                if schema != self.schema:
                    return name == self.catalog and kind in ("catalog", "any")
            elif self.schema:
                if schema != self.schema:
                    return False
                return name == self.schema and kind in ("schema", "any")
            return name in (
                self.catalog,
                self.schema,
                self.table,
            ) and kind in (
                "table",
                "view",
                "catalog",
                "schema",
                "any",
            )

        return False

    def contains_hierarchical_ref(self, ref: str, kind: str) -> bool:
        if kind in ("table", "view"):
            return ref == self.table
        if kind == "catalog":
            return ref == self.catalog or ref == self.schema
        return False


@dataclass(frozen=True)
class _FallbackSQLToken:
    value: str
    quoted: bool = False


def _fallback_sql_tokens(sql_statement: str) -> list[_FallbackSQLToken]:
    """Tokenize the small SQL subset needed for dependency bootstrapping."""
    tokens: list[_FallbackSQLToken] = []
    punctuation = "(),."
    i = 0
    while i < len(sql_statement):
        char = sql_statement[i]
        if char.isspace():
            i += 1
            continue
        if sql_statement.startswith("--", i):
            newline = sql_statement.find("\n", i + 2)
            i = len(sql_statement) if newline == -1 else newline + 1
            continue
        if sql_statement.startswith("/*", i):
            comment_end = sql_statement.find("*/", i + 2)
            i = len(sql_statement) if comment_end == -1 else comment_end + 2
            continue
        if char in ('"', "`", "'"):
            quote = char
            i += 1
            identifier: list[str] = []
            while i < len(sql_statement):
                if sql_statement[i] != quote:
                    identifier.append(sql_statement[i])
                    i += 1
                elif (
                    i + 1 < len(sql_statement)
                    and sql_statement[i + 1] == quote
                ):
                    identifier.append(quote)
                    i += 2
                else:
                    i += 1
                    break
            tokens.append(_FallbackSQLToken("".join(identifier), quoted=True))
            continue
        if char in punctuation:
            tokens.append(_FallbackSQLToken(char))
            i += 1
            continue
        if char == "_" or char.isalpha():
            start = i
            i += 1
            while i < len(sql_statement):
                candidate = sql_statement[start : i + 1]
                if candidate.isidentifier() or sql_statement[i] == "$":
                    i += 1
                else:
                    break
            tokens.append(_FallbackSQLToken(sql_statement[start:i]))
            continue
        # Operators and other punctuation cannot introduce a relation.
        tokens.append(_FallbackSQLToken(char))
        i += 1
    return tokens


def _fallback_parentheses(
    tokens: list[_FallbackSQLToken],
) -> dict[int, int]:
    pairs: dict[int, int] = {}
    stack: list[int] = []
    for index, token in enumerate(tokens):
        if token.value == "(":
            stack.append(index)
        elif token.value == ")" and stack:
            pairs[stack.pop()] = index
    return pairs


def _fallback_cte_scopes(
    tokens: list[_FallbackSQLToken], pairs: dict[int, int]
) -> list[tuple[str, int, int]]:
    """Return CTE names and the token ranges in which they are visible."""
    scopes: list[tuple[str, int, int]] = []
    enclosing: list[int] = []
    for index, token in enumerate(tokens):
        if token.value == "(":
            enclosing.append(pairs.get(index, len(tokens)))
            continue
        if token.value == ")":
            if enclosing:
                enclosing.pop()
            continue
        if token.quoted or token.value.casefold() != "with":
            continue

        scope_end = enclosing[-1] if enclosing else len(tokens)
        cursor = index + 1
        recursive = (
            cursor < len(tokens)
            and not tokens[cursor].quoted
            and tokens[cursor].value.casefold() == "recursive"
        )
        if recursive:
            cursor += 1
        while cursor < scope_end:
            name = tokens[cursor]
            if not name.value.isidentifier():
                break
            cursor += 1
            # Optional CTE column list.
            if cursor < scope_end and tokens[cursor].value == "(":
                cursor = pairs.get(cursor, scope_end) + 1
            if (
                cursor >= scope_end
                or tokens[cursor].quoted
                or tokens[cursor].value.casefold() != "as"
            ):
                break
            cursor += 1
            if (
                cursor < scope_end
                and not tokens[cursor].quoted
                and tokens[cursor].value.casefold() == "not"
            ):
                cursor += 1
            if (
                cursor < scope_end
                and not tokens[cursor].quoted
                and tokens[cursor].value.casefold() == "materialized"
            ):
                cursor += 1
            if cursor >= scope_end or tokens[cursor].value != "(":
                break
            body_end = pairs.get(cursor, scope_end)
            # A non-recursive CTE does not shadow a same-named base relation
            # inside its own definition. Earlier CTEs are visible to later
            # definitions because their visibility starts after their body.
            visibility_start = index if recursive else body_end + 1
            scopes.append((name.value, visibility_start, scope_end))
            cursor = body_end + 1
            if cursor >= scope_end or tokens[cursor].value != ",":
                break
            cursor += 1
    return scopes


def find_unqualified_sql_refs_fallback(sql_statement: str) -> set[SQLRef]:
    """Best-effort local-frame refs before SQLGlot can be installed.

    Polars and SQLGlot are optional dependencies. SQL cells are compiled before
    missing packages can be installed, so this lightweight tokenizer wires the
    reactive graph on first compilation. SQLGlot remains authoritative once it
    is available.
    """
    tokens = _fallback_sql_tokens(sql_statement)
    pairs = _fallback_parentheses(tokens)
    cte_scopes = _fallback_cte_scopes(tokens, pairs)
    refs: set[SQLRef] = set()
    from_active: dict[int, bool] = {}
    expect_relation: dict[int, bool] = {}
    query_depths = {0}
    depth = 0
    index = 0
    clause_terminators = {
        "except",
        "group",
        "having",
        "intersect",
        "limit",
        "order",
        "qualify",
        "returning",
        "union",
        "where",
        "window",
    }

    while index < len(tokens):
        token = tokens[index]
        keyword = None if token.quoted else token.value.casefold()
        if token.value == "(":
            entering_relation_group = bool(expect_relation.get(depth))
            if entering_relation_group:
                expect_relation[depth] = False
            depth += 1
            next_token = tokens[index + 1] if index + 1 < len(tokens) else None
            starts_query = (
                next_token is not None
                and not next_token.quoted
                and next_token.value.casefold()
                in (
                    "select",
                    "values",
                    "with",
                )
            )
            if starts_query:
                query_depths.add(depth)
            elif entering_relation_group:
                # Polars supports parenthesized join groups without a nested
                # SELECT, e.g. `FROM (a JOIN b ON ...) AS nested`.
                query_depths.add(depth)
                from_active[depth] = True
                expect_relation[depth] = True
            index += 1
            continue
        if token.value == ")":
            from_active.pop(depth, None)
            expect_relation.pop(depth, None)
            query_depths.discard(depth)
            depth = max(0, depth - 1)
            index += 1
            continue
        if depth not in query_depths:
            index += 1
            continue
        if keyword in ("from", "join"):
            from_active[depth] = True
            expect_relation[depth] = True
            index += 1
            continue
        if keyword in clause_terminators:
            from_active[depth] = False
            expect_relation[depth] = False
            index += 1
            continue
        if token.value == "," and from_active.get(depth):
            expect_relation[depth] = True
            index += 1
            continue
        if not expect_relation.get(depth):
            index += 1
            continue
        if keyword in ("lateral", "only"):
            index += 1
            continue

        expect_relation[depth] = False
        if not token.value.isidentifier():
            index += 1
            continue
        parts = [token.value]
        cursor = index + 1
        while (
            cursor + 1 < len(tokens)
            and tokens[cursor].value == "."
            and tokens[cursor + 1].value.isidentifier()
        ):
            parts.append(tokens[cursor + 1].value)
            cursor += 2
        # Qualified names and table functions are not notebook frames.
        if len(parts) == 1 and (
            cursor >= len(tokens) or tokens[cursor].value != "("
        ):
            table = parts[0]
            is_cte = any(
                name == table and start <= index < end
                for name, start, end in cte_scopes
            )
            if not is_cte:
                refs.add(SQLRef(table=table))
        index = cursor
    return refs


def find_polars_sql_refs(sql_statement: str) -> set[SQLRef]:
    """Find local Polars frame references across supported SQL quoting."""
    refs = find_unqualified_sql_refs_fallback(sql_statement)
    if DependencyManager.sqlglot.has():
        # SQLGlot understands richer query structure, while the fallback also
        # covers Polars syntax that its DuckDB dialect rejects (for example,
        # backticks and SEMI/ANTI joins). The fallback is query-scope aware, so
        # merging avoids dropping relations from either supported syntax.
        refs.update(find_sql_refs(sql_statement))
    return refs


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
        schema_name = table.db or None
        catalog_name = table.catalog or None

        if table_name is None:
            return None

        # Check if the table name looks like a URL or has a file extension.
        # These are often not actual table references, so we skip them.
        # Note that they can be valid table names, but we skip them to avoid circular deps
        if "://" in table_name or table_name.endswith(COMMON_FILE_EXTENSIONS):
            return None

        return SQLRef(
            table=table_name, schema=schema_name, catalog=catalog_name
        )

    from sqlglot.errors import ParseError

    try:
        with _loggers.suppress_warnings_logs("sqlglot"):
            expression_list = parse(sql_statement, dialect="duckdb")
    except ParseError:
        return set()

    refs: set[SQLRef] = set()

    def _collect_table_refs_excluding_ctes(expression: exp.Expression) -> None:
        """Walk all Table nodes, filtering out unqualified CTE references.

        find_all(exp.Table) doesn't understand CTE scope, so bare
        references to CTE names would be misidentified as real tables.

        We only collect CTEs from the statement-level WITH clause
        rather than nested subqueries, because a subquery's CTE is
        scoped to that subquery and must not mask a real table with the
        same name in the outer query. We identify statement-level CTEs
        by checking that the CTE's grandparent (With -> Expression) is
        the top-level expression. Schema-qualified refs (e.g. schema.foo)
        are always real tables even if a CTE shares the same base name.
        """
        cte_names: set[str] = set()
        for cte in expression.find_all(exp.CTE):
            with_node = cte.parent
            if with_node and with_node.parent is expression:
                alias = cte.alias
                if alias:
                    cte_names.add(alias.lower())
        for table in expression.find_all(exp.Table):
            if ref := get_ref_from_table(table):
                is_unqualified_cte = (
                    ref.table.lower() in cte_names
                    and ref.schema is None
                    and ref.catalog is None
                )
                if not is_unqualified_cte:
                    refs.add(ref)

    for expression in expression_list:
        if expression is None:
            continue

        if bool(
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
        ):
            _collect_table_refs_excluding_ctes(expression)  # type: ignore[arg-type]

        # build_scope only works for select statements.
        # It may raise OptimizeError for valid SQL with duplicate aliases
        # (e.g., "SELECT * FROM (SELECT 1 as x), (SELECT 2 as x)")
        # In that case, fall back to extracting table references directly.
        try:
            if root := build_scope(expression):
                for scope in root.traverse():  # type: ignore
                    for _node, source in scope.selected_sources.values():
                        if isinstance(source, exp.Table):
                            if ref := get_ref_from_table(source):
                                refs.add(ref)
        except OptimizeError:
            _collect_table_refs_excluding_ctes(expression)  # type: ignore[arg-type]

    return refs
