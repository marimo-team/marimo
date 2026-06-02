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

    # Typed definitions for SQL support: (name, type) -> cell_ids
    # e.g. ("my_table", "table") -> {cell_id_1}
    typed_definitions: dict[tuple[Name, str], set[CellId_t]] = field(
        default_factory=dict
    )

    # Track all types for a given definition name
    # e.g. "my_table" -> {"table", "view"}
    definition_types: dict[Name, set[str]] = field(default_factory=dict)

    # SQL table/view definitions that include a schema or catalog should only
    # collide with the exact same qualified name.
    qualified_definitions: dict[tuple[Name, str, str], set[CellId_t]] = field(
        default_factory=dict
    )

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
        qualified_name = variable.qualified_name
        is_qualified_sql_def = (
            variable.language == "sql"
            and qualified_name is not None
            and qualified_name != name
        )

        if is_qualified_sql_def:
            qualified_def = (name, variable.kind, qualified_name)
            existing_defs = self.qualified_definitions.setdefault(
                qualified_def, set()
            )
            if existing_defs:
                self.definitions.setdefault(name, set()).update(existing_defs)
                self.definitions[name].add(cell_id)
            existing_defs.add(cell_id)
        else:
            self.definitions.setdefault(name, set()).add(cell_id)

        self.typed_definitions.setdefault(typed_def, set()).add(cell_id)
        self.definition_types.setdefault(name, set()).add(variable.kind)

        # Return siblings (other cells that define this name)
        siblings = self.definitions.get(name, set()) - {cell_id}
        return siblings

    def unregister_definitions(
        self,
        cell_id: CellId_t,
        defs: set[Name],
    ) -> None:
        """Unregister all definitions for a cell.

        Args:
            cell_id: The cell being removed
            defs: The set of variable names defined by the cell
        """
        for name in defs:
            if name in self.definitions:
                name_defs = self.definitions[name]
                name_defs.discard(cell_id)

                if not name_defs:
                    # No more cells define this name, so we remove it
                    del self.definitions[name]

            for typed_def, cell_ids in list(self.typed_definitions.items()):
                if typed_def[0] != name:
                    continue
                cell_ids.discard(cell_id)
                if not cell_ids:
                    del self.typed_definitions[typed_def]

            for qualified_def, cell_ids in list(
                self.qualified_definitions.items()
            ):
                if qualified_def[0] != name:
                    continue
                cell_ids.discard(cell_id)
                if not cell_ids:
                    del self.qualified_definitions[qualified_def]

            if name in self.definitions:
                for (
                    qualified_def,
                    cell_ids,
                ) in self.qualified_definitions.items():
                    if qualified_def[0] == name and len(cell_ids) < 2:
                        self.definitions[name].difference_update(cell_ids)
                if not self.definitions[name]:
                    del self.definitions[name]

            remaining_types = {
                kind
                for def_name, kind in self.typed_definitions
                if def_name == name
            }
            if remaining_types:
                self.definition_types[name] = remaining_types
            else:
                self.definition_types.pop(name, None)

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

    def get_multiply_defined(self) -> list[Name]:
        """Return a list of names that are defined in multiple cells."""
        names: list[Name] = []
        for name, definers in self.definitions.items():
            if len(definers) > 1:
                names.append(name)
        return names
