# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from marimo._ast.sql_visitor import SQLKind, SQLRef
from marimo._dependencies.dependencies import DependencyManager

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._ast.cell import CellImpl


@dataclass(frozen=True)
class SQLBinding:
    """A SQL definition, named as declared in the notebook."""

    name: str
    kind: SQLKind
    ref: SQLRef | None = None

    def matches(self, ref: SQLRef) -> bool:
        return ref.matches_hierarchical_ref(
            self.ref.table if self.ref is not None else self.name,
            self.name,
            self.kind,
        )


def get_sql_bindings(cell: CellImpl) -> list[SQLBinding]:
    """Resolve declared SQL objects against the live default DuckDB catalog.

    Static definitions alone cannot distinguish a successful CREATE from one
    skipped by a conditional or an exception earlier in the cell.
    """
    candidates = []
    for name, definitions in cell.variable_data.items():
        variable = definitions[-1]
        if variable.kind not in ("table", "view", "schema", "catalog"):
            continue
        candidates.append(
            SQLBinding(
                variable.sql_ref.qualified_name if variable.sql_ref else name,
                cast(SQLKind, variable.kind),
                variable.sql_ref,
            )
        )
    return existing_sql_bindings(candidates)


def existing_sql_bindings(
    candidates: Sequence[SQLBinding],
) -> list[SQLBinding]:
    """Return the SQL bindings whose objects still exist in this runtime."""
    if not candidates or not DependencyManager.duckdb.has():
        return []

    import duckdb

    try:
        database, schema = duckdb.sql(
            "SELECT current_database(), current_schema()"
        ).fetchone() or ("memory", "main")
        database, schema = database.lower(), schema.lower()
        catalogs = {
            row[0].lower()
            for row in duckdb.sql(
                "SELECT database_name FROM duckdb_databases()"
            ).fetchall()
        }
        schemas = {
            tuple(part.lower() for part in row)
            for row in duckdb.sql(
                "SELECT database_name, schema_name FROM duckdb_schemas()"
            ).fetchall()
        }
        relations = {
            tuple(part.lower() for part in row)
            for row in duckdb.sql(
                "SELECT database_name, schema_name, table_name, 'table' "
                "FROM duckdb_tables() UNION ALL "
                "SELECT database_name, schema_name, view_name, 'view' "
                "FROM duckdb_views()"
            ).fetchall()
        }
    except duckdb.Error:
        # An aborted transaction can make catalog inspection unavailable.
        return []

    bound = []
    for candidate in candidates:
        if candidate.kind == "catalog":
            exists = candidate.name.lower() in catalogs
        elif candidate.kind == "schema":
            parts = candidate.name.lower().split(".")
            qualified = (
                tuple(parts) if len(parts) == 2 else (database, parts[0])
            )
            exists = qualified in schemas
        else:
            ref = candidate.ref
            assert ref is not None
            catalog = ref.catalog or database
            namespace = ref.schema or schema
            if ref.catalog is None and ref.schema in catalogs:
                catalog, namespace = ref.schema, "main"
            exists = (
                catalog,
                namespace,
                ref.table,
                candidate.kind,
            ) in relations
            if ref.catalog is None and ref.schema in (None, "main"):
                # Unqualified and main-qualified names also resolve temp tables.
                exists |= (
                    "temp",
                    "main",
                    ref.table,
                    candidate.kind,
                ) in relations
        if exists:
            bound.append(candidate)
    return bound
