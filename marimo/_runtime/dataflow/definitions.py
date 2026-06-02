# Copyright 2026 Marimo. All rights reserved.
"""Variable definition tracking for cells."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._ast.sql_visitor import SQLRef
    from marimo._ast.visitor import Name, VariableData
    from marimo._types.ids import CellId_t


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
    definition_conflicts: dict[tuple[str, str], set[CellId_t]] = field(
        default_factory=dict
    )
    conflict_names: dict[tuple[str, str], Name] = field(default_factory=dict)

    def _conflict_key(
        self, name: Name, variable: VariableData
    ) -> tuple[str, str]:
        """
        Return the key used to group definitions that conflict.
        Only qualified SQL definitions return a non-global key.
        """
        if (
            variable.language == "sql"
            and variable.qualified_name is not None
            and variable.qualified_name != name
        ):
            return ("sql", variable.qualified_name)
        return ("global", name)

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
        variable = variable_data[-1]  # Only the last definition matters
        typed_def = (name, variable.kind)
        conflict_key = self._conflict_key(name, variable)

        # Check if this is a duplicate definition
        if (
            name in self.definitions
            and typed_def not in self.typed_definitions
        ):
            # Duplicate if the qualified name is no different
            if variable.qualified_name == name or variable.language != "sql":
                self.definitions[name].add(cell_id)
        else:
            self.definitions.setdefault(name, set()).add(cell_id)

        self.typed_definitions.setdefault(typed_def, set()).add(cell_id)
        self.definition_conflicts.setdefault(conflict_key, set()).add(cell_id)
        self.conflict_names.setdefault(conflict_key, name)

        # Return siblings (other cells that define the same semantic object)
        siblings = self.definition_conflicts[conflict_key] - {cell_id}
        return siblings

    def unregister_definitions(
        self,
        cell_id: CellId_t,
        variable_data: dict[Name, list[VariableData]],
    ) -> None:
        """Unregister all definitions for a cell.

        Args:
            cell_id: The cell being removed
            variable_data: Definitions and metadata for the cell
        """
        for name, data in variable_data.items():
            if name not in self.definitions:
                continue

            variable = data[-1]
            typed_def = (name, variable.kind)
            conflict_key = self._conflict_key(name, variable)

            name_defs = self.definitions[name]
            name_defs.discard(cell_id)
            if typed_def in self.typed_definitions:
                self.typed_definitions[typed_def].discard(cell_id)
                if not self.typed_definitions[typed_def]:
                    del self.typed_definitions[typed_def]

            if conflict_key in self.definition_conflicts:
                conflict_defs = self.definition_conflicts[conflict_key]
                conflict_defs.discard(cell_id)
                if not conflict_defs:
                    del self.definition_conflicts[conflict_key]
                    self.conflict_names.pop(conflict_key, None)

            if not name_defs:
                # No more cells define this name, so we remove it
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
            item: tuple[tuple[str, str], set[CellId_t]],
        ) -> tuple[Name, tuple[str, str]]:
            conflict_key, _definers = item
            return (self.conflict_names[conflict_key], conflict_key)

        return [
            (self.conflict_names[conflict_key], definers)
            for conflict_key, definers in sorted(
                self.definition_conflicts.items(),
                key=sort_key,
            )
            if len(definers) > 1
        ]
