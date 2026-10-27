# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._sql.sql_quoting import quote_qualified_name, quote_sql_identifier

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from marimo._ast.visitor import Name, VariableData

LOGGER = _loggers.marimo_logger()


@dataclass(frozen=True)
class SQLCleanupState:
    """Execution-time bindings and objects that a cell must leave intact."""

    catalogs: frozenset[str]
    protected_relations: frozenset[tuple[str, ...]]
    protected_catalogs: frozenset[str]

    def delete_definition(self, name: Name, variable: VariableData) -> None:
        """Delete an owned relation or catalog using its original bindings."""
        import duckdb

        if variable.kind in ("table", "view"):
            path = in_memory_relation_path(variable, name, self.catalogs)
            if path is None or path in self.protected_relations:
                return
            qualified = quote_qualified_name(*path)
            try:
                duckdb.execute(
                    f"DROP {variable.kind.upper()} IF EXISTS {qualified}"
                )
            except Exception as e:
                LOGGER.warning(
                    "Failed to drop %s %s: %s", variable.kind, name, e
                )
        elif variable.kind == "catalog":
            if name in self.protected_catalogs:
                return
            try:
                duckdb.execute(
                    f"DETACH DATABASE IF EXISTS {quote_sql_identifier(name)}"
                )
            except Exception as e:
                LOGGER.warning("Failed to detach catalog %s: %s", name, e)


def _get_attached_catalogs() -> frozenset[str]:
    import duckdb

    try:
        return frozenset(
            row[0].lower()
            for row in duckdb.sql(
                "SELECT database_name FROM duckdb_databases()"
            ).fetchall()
        )
    except Exception:
        return frozenset()


def in_memory_relation_path(
    variable: VariableData,
    name: Name,
    attached_catalogs: frozenset[str],
) -> tuple[str, ...] | None:
    """Resolve an in-memory relation using its execution's catalog bindings."""
    sql_ref = variable.sql_ref
    qualifiers = list(sql_ref.qualifiers) if sql_ref else []
    catalog = "memory"
    if qualifiers and (
        qualifiers[0].lower() == "memory"
        or qualifiers[0].lower() in attached_catalogs
        or (
            sql_ref is not None
            and sql_ref.catalog is not None
            and sql_ref.schema is None
        )
    ):
        catalog = qualifiers.pop(0).lower()
    if catalog != "memory":
        return None
    return (catalog, *(qualifiers or ["main"]), name)


def capture_sql_cleanup_state(
    variable_data: Mapping[Name, Sequence[VariableData]],
) -> SQLCleanupState | None:
    """Record pre-existing objects before executing a cell's SQL."""
    variables = [
        (name, variable)
        for name, data in variable_data.items()
        for variable in data
        if variable.kind in ("table", "view", "catalog")
    ]
    if not variables:
        return None
    live_catalogs = _get_attached_catalogs()
    declared_catalogs = frozenset(
        name.lower()
        for name, variable in variables
        if variable.kind == "catalog"
    )
    catalogs = live_catalogs | declared_catalogs
    targets = {
        path
        for name, variable in variables
        if variable.kind in ("table", "view")
        and (path := in_memory_relation_path(variable, name, catalogs))
        is not None
    }
    protected_catalogs = frozenset(
        name
        for name, variable in variables
        if variable.kind == "catalog" and name.lower() in live_catalogs
    )
    protected_relations: set[tuple[str, ...]] = set()
    if targets:
        from marimo._sql.engines.duckdb import DuckDBEngine

        # Existing objects must survive failed CREATE and IF NOT EXISTS.
        try:
            existing: dict[tuple[str, ...], set[str]] = {}
            engine = DuckDBEngine()
            for target in targets:
                schema_path = tuple(part.lower() for part in target[1:-1])
                if schema_path not in existing:
                    existing[schema_path] = {
                        table.name.lower()
                        for table in engine.get_tables_in_schema(
                            database="memory",
                            schema=schema_path[-1],
                            schema_path=list(schema_path),
                            include_table_details=False,
                        )
                    }
                if target[-1].lower() in existing[schema_path]:
                    protected_relations.add(target)
        except Exception:
            protected_relations.update(targets)
            LOGGER.warning(
                "Failed to inspect SQL cleanup targets", exc_info=True
            )
    return SQLCleanupState(
        catalogs, frozenset(protected_relations), protected_catalogs
    )
