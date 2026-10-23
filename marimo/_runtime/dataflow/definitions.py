# Copyright 2026 Marimo. All rights reserved.
"""Variable definition tracking for cells."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, NamedTuple

from marimo._ast.sql_visitor import SQLRef

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._ast.cell import CellImpl
    from marimo._ast.visitor import Name, VariableData
    from marimo._types.ids import CellId_t


def effective_variable_definitions(
    data: list[VariableData],
) -> list[VariableData]:
    """SQL objects coexist with each other and the final Python binding."""
    sql_definitions = [
        variable for variable in data if variable.language == "sql"
    ]
    return (
        sql_definitions
        if data[-1].language == "sql"
        else [*sql_definitions, data[-1]]
    )


class _DefinitionConflictKey(NamedTuple):
    namespace: Literal["global", "sql", "sql-schema"]
    parts: tuple[str, ...]


@dataclass
class DefinitionRegistry:
    """Tracks variable definitions across cells.

    Responsibilities:
    - Track which cells define which variables
    - Handle typed definitions (SQL vs Python)
    - Detect multiply-defined names
    - SQL hierarchical reference matching
    """

    # A mapping from defs to the cells that define them
    definitions: dict[Name, set[CellId_t]] = field(default_factory=dict)

    # Typed definitions: (name, type) -> cell_ids
    # e.g. ("my_table", "table") -> {cell_id_1}
    typed_definitions: dict[tuple[Name, str], set[CellId_t]] = field(
        default_factory=dict
    )

    # Track definition conflicts separately from lookup indexes.
    # Qualified SQL definitions with the same leaf name are distinct objects
    # in the database, but still need to be discoverable by their leaf name
    # when computing SQL edges.
    definition_conflicts: dict[_DefinitionConflictKey, set[CellId_t]] = field(
        default_factory=dict
    )
    conflict_names: dict[_DefinitionConflictKey, Name] = field(
        default_factory=dict
    )

    @staticmethod
    def _conflict_key(
        name: Name,
        variable: VariableData,
        catalogs: frozenset[str],
    ) -> _DefinitionConflictKey:
        """
        Return the key used to group definitions that conflict.
        Only qualified SQL definitions return a non-global key.
        """
        sql_ref = variable.sql_ref
        if variable.language == "sql" and sql_ref is not None:
            if variable.kind == "schema":
                catalog, path = sql_ref.split_catalog(catalogs)
                catalog = catalog or "memory"
                if catalog == "memory" and path == (name,):
                    return _DefinitionConflictKey("global", (name,))
                return _DefinitionConflictKey(
                    "sql-schema",
                    (catalog, *path),
                )
            if sql_ref.qualified_name != name:
                return _DefinitionConflictKey(
                    "sql", tuple(part.lower() for part in sql_ref.parts)
                )

        return _DefinitionConflictKey("global", (name,))

    def _register_conflict(
        self, cell_id: CellId_t, name: Name, key: _DefinitionConflictKey
    ) -> set[CellId_t]:
        definers = self.definition_conflicts.setdefault(key, set())
        definers.add(cell_id)
        self.conflict_names.setdefault(key, name)
        return definers

    @property
    def sql_catalogs(self) -> frozenset[str]:
        return frozenset(
            name.lower()
            for name, kind in self.typed_definitions
            if kind == "catalog"
        )

    def rebuild_conflicts(self, cells: Mapping[CellId_t, CellImpl]) -> None:
        self.definition_conflicts.clear()
        self.conflict_names.clear()
        catalogs = self.sql_catalogs
        for cell_id, cell in cells.items():
            for name, data in cell.variable_data.items():
                for variable in effective_variable_definitions(data):
                    key = self._conflict_key(name, variable, catalogs)
                    self._register_conflict(cell_id, name, key)

    def register_definition(
        self,
        cell_id: CellId_t,
        name: Name,
        variable_data: list[VariableData],
    ) -> set[CellId_t]:
        """Register a definition for a cell.

        Args:
            cell_id: The cell that defines the variable
            name: The variable name
            variable_data: List of metadata about the variable (from cell.variable_data[name])

        Returns:
            Set of sibling cell IDs (cells that also define this variable)
        """
        variables = effective_variable_definitions(variable_data)
        catalogs: frozenset[str] | None = None
        siblings: set[CellId_t] = set()
        self.definitions.setdefault(name, set()).add(cell_id)
        for variable in variables:
            if variable.kind == "schema" and catalogs is None:
                catalogs = self.sql_catalogs
            typed_def = (name, variable.kind)
            conflict_key = self._conflict_key(
                name, variable, catalogs or frozenset()
            )
            self.typed_definitions.setdefault(typed_def, set()).add(cell_id)
            if variable.kind == "catalog" and catalogs is not None:
                catalogs = catalogs | {name.lower()}
            definers = self._register_conflict(cell_id, name, conflict_key)
            siblings.update(definers - {cell_id})
        return siblings

    def unregister_definitions(
        self,
        cell_id: CellId_t,
        variable_data: dict[Name, list[VariableData]],
    ) -> None:
        catalogs = (
            self.sql_catalogs
            if any(
                variable.kind == "schema"
                for data in variable_data.values()
                for variable in data
            )
            else frozenset()
        )
        for name, data in variable_data.items():
            if name not in self.definitions:
                continue
            variables = effective_variable_definitions(data)
            for variable in variables:
                typed_def = (name, variable.kind)
                conflict_key = self._conflict_key(name, variable, catalogs)
                if typed_def in self.typed_definitions:
                    self.typed_definitions[typed_def].discard(cell_id)
                    if not self.typed_definitions[typed_def]:
                        del self.typed_definitions[typed_def]
                if conflict_key in self.definition_conflicts:
                    self.definition_conflicts[conflict_key].discard(cell_id)
                    if not self.definition_conflicts[conflict_key]:
                        del self.definition_conflicts[conflict_key]
                        self.conflict_names.pop(conflict_key, None)
            self.definitions[name].discard(cell_id)
            if not self.definitions[name]:
                del self.definitions[name]

    def get_defining_cells(self, name: Name) -> set[CellId_t]:
        """Get all cells that define a variable name.

        This is a singleton for well-formed graphs (no multiply-defined names).

        Args:
            name: The variable name

        Returns:
            Set of cell IDs that define this name
        """
        return self.definitions.get(name, set())

    def find_sql_hierarchical_matches(
        self, sql_ref: SQLRef
    ) -> list[tuple[set[CellId_t], Name]]:
        """Find cells that define components of a hierarchical SQL reference.

        This method searches through all definitions in the graph to find cells
        that define the individual components (table, schema, or catalog) of the
        hierarchical reference.

        For example, given a reference "my_schema.my_table", this method will:
        - Look for cells that define a table/view named "my_table"
        - Look for cells that define a catalog named "my_schema"
          (when the reference has at least 2 parts)

        Args:
            sql_ref: A hierarchical SQL reference (e.g., "schema.table",
                  "catalog.schema.table") to find matching definitions for.

        Returns:
            A list of tuples containing:
            - A set of cell IDs that define components of the hierarchical reference
            - The definition of the name that was found (e.g., "schema.table" -> "table")
        """
        matching_cell_ids_list = []

        for (def_name, kind), cell_ids in self.typed_definitions.items():
            # Match table/view definitions
            if sql_ref.contains_hierarchical_ref(def_name, kind):
                matching_cell_ids_list.append((cell_ids, def_name))

        return matching_cell_ids_list

    def get_multiply_defined(self) -> list[tuple[Name, set[CellId_t]]]:
        """
        Return multiply-defined names with their conflicting cells.

        Results are sorted by display name and conflict key to keep diagnostics
        deterministic.
        """

        def sort_key(
            item: tuple[_DefinitionConflictKey, set[CellId_t]],
        ) -> tuple[Name, tuple[str, str]]:
            conflict_key, _definers = item
            identity = (
                conflict_key.parts[0]
                if conflict_key.namespace == "global"
                else SQLRef.from_parts(list(conflict_key.parts)).qualified_name
            )
            return (
                self.conflict_names[conflict_key],
                (conflict_key.namespace, identity),
            )

        return [
            (self.conflict_names[conflict_key], definers)
            for conflict_key, definers in sorted(
                self.definition_conflicts.items(),
                key=sort_key,
            )
            if len(definers) > 1
        ]
