# Copyright 2026 Marimo. All rights reserved.
"""Graph coordinator that orchestrates all dataflow components."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Literal, Optional

from marimo import _loggers
from marimo._ast.compiler import code_key
from marimo._ast.variables import is_mangled_local
from marimo._runtime.dataflow import edges
from marimo._runtime.dataflow.cycles import CycleTracker
from marimo._runtime.dataflow.definitions import DefinitionRegistry
from marimo._runtime.dataflow.topology import (
    GraphTopology,
    MutableGraphTopology,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._ast.cell import CellImpl
    from marimo._ast.visitor import ImportData, Name, VariableData
    from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


@dataclass(frozen=True)
class DirectedGraph(GraphTopology):
    """Main entry point that coordinates all graph operations.

    Responsibilities:
    - Coordinate topology, definitions, cycles
    - Execute register_cell/delete_cell operations
    - Maintain thread safety
    - Delegate to specialists
    """

    topology: MutableGraphTopology = field(
        default_factory=MutableGraphTopology
    )
    definition_registry: DefinitionRegistry = field(
        default_factory=DefinitionRegistry
    )
    cycle_tracker: CycleTracker = field(default_factory=CycleTracker)

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
        return edges.get_referring_cells(name, language, self.topology)

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

            # Process definitions and build sibling relationships FIRST
            # This must happen before computing edges because edge computation
            # needs to look up definitions
            for name, variable_data in cell.variable_data.items():
                self.definition_registry.register_definition(
                    cell_id, name, variable_data
                )
            # Now compute edges (which can now find the definitions)
            parents, children = edges.compute_edges_for_cell(
                cell_id, cell, self.topology, self.definition_registry
            )

            # Add edges to topology
            for parent_id in parents:
                self.topology.add_edge(parent_id, cell_id)
                # Detect cycle for this edge
                self.cycle_tracker.detect_cycle_for_edge(
                    (parent_id, cell_id), self.topology
                )

            for child_id in children:
                self.topology.add_edge(cell_id, child_id)
                # Detect cycle for this edge
                self.cycle_tracker.detect_cycle_for_edge(
                    (cell_id, child_id), self.topology
                )

        LOGGER.debug("Registered cell %s and released graph lock", cell_id)
        if self.is_any_ancestor_stale(cell_id):
            self.set_stale({cell_id})

        if self.is_any_ancestor_disabled(cell_id):
            cell.set_runtime_state(status="disabled-transitively")

    def is_any_ancestor_stale(self, cell_id: CellId_t) -> bool:
        """Check if any ancestor of a cell is stale."""
        return any(
            self.topology.cells[cid].stale for cid in self.ancestors(cell_id)
        )

    def is_any_ancestor_disabled(self, cell_id: CellId_t) -> bool:
        """Check if any ancestor of a cell is disabled."""
        return any(
            self.topology.cells[cid].config.disabled
            for cid in self.ancestors(cell_id)
        )

    def disable_cell(self, cell_id: CellId_t) -> None:
        """Disables a cell in the graph.

        Does not mutate the graph (but does mutate cell statuses).

        Returns the ids of descendants that are disabled transitively.
        """
        if cell_id not in self.topology.cells:
            raise ValueError(f"Cell {cell_id} not found")

        from marimo._runtime.dataflow import transitive_closure

        for cid in transitive_closure(self, {cell_id}) - {cell_id}:
            cell = self.topology.cells[cid]
            cell.set_runtime_state(status="disabled-transitively")

    def enable_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """Enables a cell in the graph.

        Does not mutate the graph (but does mutate cell statuses).

        Returns:
        - set of cells that were stale and should be re-run
        """
        if cell_id not in self.topology.cells:
            raise ValueError(f"Cell {cell_id} not found")

        from marimo._runtime.dataflow import transitive_closure

        cells_to_run: set[CellId_t] = set()
        for cid in transitive_closure(self, {cell_id}):
            if not self.is_disabled(cid):
                child = self.topology.cells[cid]
                if child.stale:
                    # cell was previously disabled, is no longer
                    # disabled, and is stale: needs to run.
                    cells_to_run.add(cid)
                if child.disabled_transitively:
                    # cell is no longer disabled: status -> idle
                    child.set_runtime_state("idle")
        return cells_to_run

    def delete_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """Removes a cell from the graph.

        Mutates the graph, acquiring `self.lock`.

        Returns the ids of the children of the removed cell.
        """
        LOGGER.debug("Acquiring graph lock to delete cell %s", cell_id)
        with self.lock:
            LOGGER.debug("Acquired graph lock to delete cell %s", cell_id)
            if cell_id not in self.topology.cells:
                raise ValueError(f"Cell {cell_id} not found")

            # Grab a reference to children before we remove it
            children = self.topology.children[cell_id].copy()

            # Removing this cell from its defs' definer sets
            cell = self.topology.cells[cell_id]
            self.definition_registry.unregister_definitions(cell_id, cell.defs)

            # Remove cycles that are broken from removing this cell
            edges = [
                (cell_id, child) for child in self.topology.children[cell_id]
            ] + [
                (parent, cell_id) for parent in self.topology.parents[cell_id]
            ]
            for e in edges:
                self.cycle_tracker.remove_cycles_with_edge(e)

            # Purge this cell from the graph topology
            self.topology.remove_node(cell_id)

        LOGGER.debug("Deleted cell %s and Released graph lock.", cell_id)
        return children

    def is_disabled(self, cell_id: CellId_t) -> bool:
        """Check if a cell is disabled (directly or transitively)."""
        if cell_id not in self.topology.cells:
            raise ValueError(f"Cell {cell_id} not in graph.")
        cell = self.topology.cells[cell_id]
        if cell.config.disabled:
            return True
        seen: set[CellId_t] = set()
        queue = [cell_id]
        while queue:
            cid = queue.pop()
            seen.add(cid)
            for parent_id in self.topology.parents[cid]:
                if parent_id in seen:
                    continue
                elif self.topology.cells[parent_id].config.disabled:
                    return True
                else:
                    queue.append(parent_id)
        return False

    def get_imports(
        self, cell_id: Optional[CellId_t] = None
    ) -> dict[Name, ImportData]:
        """Get imports from cell(s)."""
        imports = {}
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
        return {cid for cid, cell in self.topology.cells.items() if cell.stale}

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
        return self.cycle_tracker.cycles
