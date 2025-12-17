# Copyright 2024 Marimo. All rights reserved.
"""Graph coordinator that orchestrates all dataflow components."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Literal, Optional, cast

from marimo import _loggers
from marimo._ast.compiler import code_key
from marimo._ast.sql_visitor import SQLTypes
from marimo._ast.variables import is_mangled_local
from marimo._runtime.dataflow.dag import MutableDirectedGraph
from marimo._runtime.dataflow.definitions import DefinitionRegistry
from marimo._runtime.dataflow.topology import GraphTopology

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._ast.cell import CellImpl
    from marimo._ast.sql_visitor import SQLRef
    from marimo._ast.visitor import ImportData, Name, VariableData
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


def _resolve_variable_name(
    name: Name,
    other_cell: CellImpl,
    sql_ref: Optional[SQLRef],
    sql_matches: list[tuple[set[CellId_t], Name]],
) -> Name:
    """
    Resolve the variable name to use when checking if it exists in another cell.

    For regular (non-SQL) references, returns the original name unchanged.
    For SQL hierarchical references, finds the variable name from sql_matches that
    is actually defined in the other_cell.

    Example:
        cell_1: CREATE SCHEMA schema_name
        cell_2: CREATE TABLE schema_name.table_name
        cell_3: FROM schema_name.table_name SELECT *

        When cell_3 references "schema_name.table_name":
        - For cell_1: returns "schema_name" (what cell_1 actually defines)
        - For cell_2: returns "table_name" (what cell_2 actually defines)
    """
    if not sql_ref or name in other_cell.variable_data:
        return name

    # For SQL hierarchical references, find the matching variable name
    for _, matching_variable_name in sql_matches:
        if matching_variable_name in other_cell.variable_data:
            return matching_variable_name

    return name


@dataclass(frozen=True)
class _MarimoGraph(GraphTopology):
    """Internal implementation that coordinates all graph operations.

    Responsibilities:
    - Coordinate topology, definitions
    - Execute register_cell/delete_cell operations
    - Maintain thread safety
    - Handle marimo-specific logic (Name/refs, imports, SQL)

    Exposed as DirectedGraph for backwards compat.
    """

    topology: MutableDirectedGraph = field(
        default_factory=MutableDirectedGraph
    )
    definition_registry: DefinitionRegistry = field(
        default_factory=DefinitionRegistry
    )

    # This lock must be acquired during methods that mutate the graph; it's
    # only needed because a graph is shared between the kernel and the code
    # completion service. It should almost always be uncontended.
    lock: threading.Lock = field(default_factory=threading.Lock)

    def is_cell_cached(self, cell_id: CellId_t, code: str) -> bool:
        """Whether a cell with id `cell_id` and code `code` is in the graph."""
        return (
            cell_id in self.topology.cells
            and code_key(code) == self.topology.cells[cell_id].key
        )

    def get_defining_cells(self, name: Name) -> set[CellId_t]:
        """Get all cells that define name.

        This is a singleton for well-formed graphs.
        """
        return self.definition_registry.get_defining_cells(name)

    def get_referring_cells(
        self, name: Name, language: Literal["python", "sql"]
    ) -> set[CellId_t]:
        """Get all cells that have a ref to `name`.

        The variable can be either a Python variable or a SQL variable (table).
        SQL variables don't leak to Python cells, but Python variables do leak
        to SQL.

        Only does a local analysis of refs, without taking into consideration
        whether refs are defined by other cells.
        """
        if language == "sql":
            # For SQL, only return SQL cells that reference the name
            cells: set[CellId_t] = set()
            for cid, cell in self.topology.cells.items():
                if cell.language != "sql":
                    continue

                for ref in cell.refs:
                    # Direct reference match
                    if ref == name:
                        cells.add(cid)
                        break

                    sql_ref = cell.sql_refs.get(ref)
                    kind: SQLTypes = "any"
                    if name in cell.variable_data:
                        variable_data = cell.variable_data[name][-1]
                        kind = cast(SQLTypes, variable_data.kind)

                    # Hierarchical reference match
                    if sql_ref and sql_ref.matches_hierarchical_ref(
                        name, ref, kind
                    ):
                        cells.add(cid)
                        break

            return cells
        else:
            # For Python, return all cells that reference the name
            return {
                cid
                for cid, cell in self.topology.cells.items()
                if name in cell.refs
            }

    def _is_valid_cell_reference(
        self, cell_id: CellId_t, variable_name: Name
    ) -> bool:
        """Check if a cell reference is valid and log errors if not."""
        if cell_id not in self.topology.cells:
            LOGGER.error(
                "Variable %s is defined in cell %s, but is not in the graph",
                variable_name,
                cell_id,
            )
            return False
        return True

    def _compute_edges_for_cell(
        self, cell_id: CellId_t, cell: CellImpl
    ) -> tuple[set[CellId_t], set[CellId_t]]:
        """Compute parent and child edges for a cell being registered."""
        parents: set[CellId_t] = set()
        children: set[CellId_t] = set()

        # Process definitions - cells that refer to our defs become children
        for name, variable_data in cell.variable_data.items():
            variable = variable_data[-1]
            referring_cells = self.get_referring_cells(
                name, language=variable.language
            ) - {cell_id}
            children.update(referring_cells)

        # Process references - cells that define our refs become parents
        for name in cell.refs:
            other_ids_defining_name: set[CellId_t] = (
                self.definition_registry.definitions.get(name, set())
                - {cell_id}
            )

            variable_name: Name = name

            # Handle SQL hierarchical references
            sql_matches: list[tuple[set[CellId_t], Name]] = []
            sql_ref = cell.sql_refs.get(name)
            if sql_ref:
                sql_matches = (
                    self.definition_registry.find_sql_hierarchical_matches(
                        sql_ref
                    )
                )
                for matching_cell_ids, _ in sql_matches:
                    if cell_id not in matching_cell_ids:
                        other_ids_defining_name.update(matching_cell_ids)

            for other_id in other_ids_defining_name:
                if other_id == cell_id:
                    continue
                if not self._is_valid_cell_reference(other_id, variable_name):
                    continue
                other_cell = self.topology.cells[other_id]

                variable_name = _resolve_variable_name(
                    variable_name, other_cell, sql_ref, sql_matches
                )

                if variable_name not in other_cell.variable_data:
                    LOGGER.error(
                        "Variable %s is not defined in cell %s",
                        variable_name,
                        other_id,
                    )
                    continue

                other_variable_data = other_cell.variable_data[variable_name][
                    -1
                ]
                language = other_variable_data.language

                # SQL table def -> Python ref is not an edge
                if language == "sql" and cell.language == "python":
                    continue
                # SQL-to-SQL edges must respect hierarchy
                if language == "sql" and cell.language == "sql":
                    if sql_ref and not sql_ref.matches_hierarchical_ref(
                        variable_name,
                        other_variable_data.qualified_name or name,
                        kind=cast(SQLTypes, other_variable_data.kind),
                    ):
                        continue
                parents.add(other_id)

            # Next, any cell that deletes this referenced variable is made
            # a child of this cell. In particular, if a cell deletes a
            # variable, it becomes a child of all other cells that
            # reference that variable. This means that if two cells delete
            # the same variable, they form a cycle.
            #
            # For example, two cells
            #
            #   cell u: x
            #   cell v: del x
            #
            # v becomes a child of u.
            #
            # Another example:
            #
            #   cell u: del x
            #   cell v: del x
            #
            # u and v form a cycle.
            other_ids_deleting_name: set[CellId_t] = {
                cid
                for cid in self.get_referring_cells(name, language="python")
                if name in self.topology.cells[cid].deleted_refs
            } - {cell_id}
            children.update(other_ids_deleting_name)

        # Finally, if this cell deletes a variable, we make it a child of
        # all other cells that reference this variable.
        for name in cell.deleted_refs:
            referring_cells = self.get_referring_cells(
                name, language="python"
            ) - {cell_id}
            parents.update(referring_cells)

        return parents, children

    def register_cell(self, cell_id: CellId_t, cell: CellImpl) -> None:
        """Add a cell to the graph.

        Mutates the graph, acquiring `self.lock`.

        Requires that `cell_id` is not already in the graph.
        """
        LOGGER.debug("Acquiring graph lock to register cell %s", cell_id)
        with self.lock:
            LOGGER.debug("Acquired graph lock.")
            assert cell_id not in self.topology.cells

            # Add the cell to topology
            self.topology.add_node(cell_id, cell)

            # Process definitions FIRST (needed for edge computation)
            for name, variable_data in cell.variable_data.items():
                self.definition_registry.register_definition(
                    cell_id, name, variable_data
                )
            # Now compute edges
            parents, children = self._compute_edges_for_cell(cell_id, cell)

            # Add edges to topology
            for parent_id in parents:
                self.topology.add_edge(parent_id, cell_id)
                self.topology.detect_cycle_for_edge((parent_id, cell_id))

            for child_id in children:
                self.topology.add_edge(cell_id, child_id)
                self.topology.detect_cycle_for_edge((cell_id, child_id))

        LOGGER.debug("Registered cell %s and released graph lock", cell_id)

        if self.topology.is_any_ancestor_stale(cell_id):
            self.set_stale({cell_id})

        if self.topology.is_any_ancestor_disabled(cell_id):
            cell.set_runtime_state(status="disabled-transitively")

    def is_any_ancestor_stale(self, cell_id: CellId_t) -> bool:
        """Check if any ancestor of a cell is stale."""
        return self.topology.is_any_ancestor_stale(cell_id)

    def is_any_ancestor_disabled(self, cell_id: CellId_t) -> bool:
        """Check if any ancestor of a cell is disabled."""
        return self.topology.is_any_ancestor_disabled(cell_id)

    def disable_cell(self, cell_id: CellId_t) -> None:
        """
        Disables a cell in the graph.

        Does not mutate the graph (but does mutate cell statuses).

        Returns the ids of descendants that are disabled transitively.
        """
        self.topology.disable_cell(cell_id)

    def enable_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """
        Enables a cell in the graph.

        Does not mutate the graph (but does mutate cell statuses).

        Returns:
        - set of cells that were stale and should be re-run
        """
        return self.topology.enable_cell(cell_id)

    def delete_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """Removes a cell from the graph.

        Mutates the graph, acquiring `self.lock`.

        Returns the ids of the children of the removed cell.
        """
        LOGGER.debug("Acquiring graph lock to delete cell %s", cell_id)
        with self.lock:
            LOGGER.debug("Acquired graph lock to delete cell %s", cell_id)

            # Removing this cell from its defs' definer sets
            cell = self.topology.cells[cell_id]
            self.definition_registry.unregister_definitions(cell_id, cell.defs)

            # Purge this cell from the graph topology (also removes cycles)
            children = self.topology.delete_cell(cell_id)

        LOGGER.debug("Deleted cell %s and Released graph lock.", cell_id)
        return children

    def is_disabled(self, cell_id: CellId_t) -> bool:
        """Check if a cell is disabled (directly or transitively)."""
        return self.topology.is_disabled(cell_id)

    def get_imports(
        self, cell_id: Optional[CellId_t] = None
    ) -> dict[Name, ImportData]:
        """Get imports from cell(s)."""
        imports: dict[Name, ImportData] = {}
        cells = (
            self.topology.cells.values()
            if cell_id is None
            else [self.topology.cells[cell_id]]
        )
        for cell in cells:
            for imported in cell.imports:
                imports[imported.definition] = imported
        return imports

    def get_multiply_defined(self) -> list[Name]:
        """Return a list of names that are defined in multiple cells."""
        return self.definition_registry.get_multiply_defined()

    def get_deleted_nonlocal_ref(self) -> list[Name]:
        """Get names that are deleted but defined elsewhere."""
        names: list[Name] = []
        for cell in self.topology.cells.values():
            for ref in cell.deleted_refs:
                if ref in self.definition_registry.definitions:
                    names.append(ref)
        return names

    def set_stale(
        self, cell_ids: set[CellId_t], prune_imports: bool = False
    ) -> None:
        """Mark cells as stale (need re-execution)."""
        from marimo._runtime.dataflow import (
            get_import_block_relatives,
            transitive_closure,
        )

        relatives = (
            None if not prune_imports else get_import_block_relatives(self)
        )

        for cid in transitive_closure(self, cell_ids, relatives=relatives):
            self.topology.cells[cid].set_stale(stale=True)

    def get_stale(self) -> set[CellId_t]:
        """Get all stale cells."""
        return self.topology.get_stale()

    def get_transitive_references(
        self,
        refs: set[Name],
        inclusive: bool = True,
        predicate: Callable[[Name, VariableData], bool] | None = None,
    ) -> set[Name]:
        """Return a set of the passed-in cells' references and their
        references on the block (function / class) level.

        If inclusive, includes the references of the passed-in cells in the
        set.

        If predicate, only references satisfying predicate(ref) are included
        """
        # TODO: Consider caching on the graph level and updating on register /
        # delete
        processed: set[Name] = set()
        queue: set[Name] = refs & self.definition_registry.definitions.keys()
        predicate = predicate or (lambda *_: True)

        while queue:
            # Should ideally be one cell per ref, but for completion, stay
            # agnostic to potenital cycles.
            cells = {
                cell_id
                for ref in queue
                for cell_id in self.definition_registry.definitions.get(
                    ref, set()
                )
            }

            for cell_id in cells:
                data = self.topology.cells[cell_id].variable_data
                newly_processed = set(data.keys()) & queue
                processed.update(newly_processed)
                queue.difference_update(newly_processed)
                for variable in newly_processed:
                    # variables can be defined multiple times in a single
                    # cell ...
                    for datum in data[variable]:
                        if predicate(variable, datum):
                            to_process = datum.required_refs - processed
                            queue.update(
                                to_process
                                & self.definition_registry.definitions.keys()
                            )
                            # Private variables referenced by public functions
                            # have to be included.
                            processed.update(
                                maybe_private
                                for maybe_private in (
                                    to_process
                                    - self.definition_registry.definitions.keys()
                                )
                                if is_mangled_local(maybe_private, cell_id)
                            )

        if inclusive:
            return processed | refs
        return processed - refs

    def copy(self, filename: None | str = None) -> DirectedGraph:
        """Return a deep copy of the graph by recompiling all cells.

        This is mainly useful in the case where recompilation must be done
        due to a dynamically changing notebook, where the line cache must be
        consistent with the cell code, e.g. for debugging.
        """
        from marimo._ast.compiler import compile_cell

        graph = DirectedGraph()
        with self.lock:
            for cid, old_cell in self.topology.cells.items():
                cell = compile_cell(
                    old_cell.code,
                    cell_id=cid,
                    filename=filename,
                )
                # Carry over import data manually
                imported_defs = old_cell.import_workspace.imported_defs
                is_import_block = old_cell.import_workspace.is_import_block
                cell.import_workspace.imported_defs = imported_defs
                cell.import_workspace.is_import_block = is_import_block
                # Reregister
                graph.register_cell(cid, cell)
        return graph

    @property
    def cells(self) -> Mapping[CellId_t, CellImpl]:
        """Get the cells dictionary."""
        return self.topology.cells

    @property
    def parents(self) -> Mapping[CellId_t, set[CellId_t]]:
        """Get the parents dictionary."""
        return self.topology.parents

    @property
    def children(self) -> Mapping[CellId_t, set[CellId_t]]:
        """Get the children dictionary."""
        return self.topology.children

    def get_path(
        self, source: CellId_t, dst: CellId_t
    ) -> list[tuple[CellId_t, CellId_t]]:
        """Get a path from `source` to `dst`, if any."""
        return self.topology.get_path(source, dst)

    def descendants(self, cell_id: CellId_t) -> set[CellId_t]:
        """Get all descendants of a cell."""
        return self.topology.descendants(cell_id)

    def ancestors(self, cell_id: CellId_t) -> set[CellId_t]:
        """Get all ancestors of a cell."""
        return self.topology.ancestors(cell_id)

    @property
    def definitions(self) -> Mapping[Name, set[CellId_t]]:
        """Get the definitions dictionary."""
        return self.definition_registry.definitions

    @property
    def cycles(self) -> set[tuple[tuple[CellId_t, CellId_t], ...]]:
        """Get the cycles set."""
        return self.topology.cycles


# Used over _MarimoGraph for backwards compatibility
class DirectedGraph(_MarimoGraph):
    """marimo's dataflow graph for tracking cell dependencies.

    The DirectedGraph tracks relationships between cells based on their
    variable definitions and references. It provides:

    - Cell registration and deletion
    - Dependency tracking (parents/children)
    - Cycle detection
    - Stale cell tracking
    - Import analysis

    This class is the main interface for interacting with marimo's
    reactive execution model.
    """

    pass
