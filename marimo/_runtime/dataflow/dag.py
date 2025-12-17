# Copyright 2024 Marimo. All rights reserved.
"""Directed graph with cycle tracking and cell state operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo._runtime.dataflow.topology import MutableGraphTopology
from marimo._runtime.dataflow.types import Edge

if TYPE_CHECKING:
    from marimo._types.ids import CellId_t


@dataclass
class MutableDirectedGraph(MutableGraphTopology):
    """MutableGraphTopology with cycle detection and cell state operations.

    Extends the base topology with:
    - Cycle tracking (detect/remove cycles)
    - Cell state operations (disabled, stale) that don't touch Name/refs
    """

    # Could be abstracted further with CellId_t -> Node
    # and "disabled", "stale" -> colourings
    # with distinctions between DG/ coloured DG.
    # However, this is sufficent for our purposes

    _cycles: set[tuple[Edge, ...]] = field(default_factory=set)

    @property
    def cycles(self) -> set[tuple[Edge, ...]]:
        return self._cycles

    def remove_node(self, cell_id: CellId_t) -> None:
        """Remove a cell and any cycles containing its edges."""
        if cell_id not in self.cells:
            raise ValueError(f"Cell {cell_id} not found")

        # Remove cycles containing edges to/from this cell
        edges_to_remove = [
            (cell_id, child) for child in self._children[cell_id]
        ] + [(parent, cell_id) for parent in self._parents[cell_id]]
        for edge in edges_to_remove:
            self.remove_cycles_with_edge(edge)

        super().remove_node(cell_id)

    def detect_cycle_for_edge(self, edge: Edge) -> tuple[Edge, ...] | None:
        """Detect if adding an edge creates a cycle.

        Returns the cycle as a tuple of edges if one exists, None otherwise.
        """
        parent, child = edge
        path = self.get_path(child, parent)
        if path:
            cycle = tuple([edge] + path)
            self._cycles.add(cycle)
            return cycle
        return None

    def remove_cycles_with_edge(self, edge: Edge) -> None:
        """Remove all cycles that contain the given edge."""
        broken_cycles = [c for c in self._cycles if edge in c]
        for c in broken_cycles:
            self._cycles.remove(c)

    def is_disabled(self, cell_id: CellId_t) -> bool:
        """Check if a cell is disabled (directly or transitively)."""
        if cell_id not in self.cells:
            raise ValueError(f"Cell {cell_id} not in graph.")
        cell = self.cells[cell_id]
        if cell.config.disabled:
            return True
        seen: set[CellId_t] = set()
        queue = [cell_id]
        while queue:
            cid = queue.pop()
            seen.add(cid)
            for parent_id in self.parents[cid]:
                if parent_id in seen:
                    continue
                elif self.cells[parent_id].config.disabled:
                    return True
                else:
                    queue.append(parent_id)
        return False

    def is_any_ancestor_stale(self, cell_id: CellId_t) -> bool:
        """Check if any ancestor of a cell is stale."""
        return any(self.cells[cid].stale for cid in self.ancestors(cell_id))

    def is_any_ancestor_disabled(self, cell_id: CellId_t) -> bool:
        """Check if any ancestor of a cell is disabled."""
        return any(
            self.cells[cid].config.disabled for cid in self.ancestors(cell_id)
        )

    def get_stale(self) -> set[CellId_t]:
        """Get all stale cells."""
        return {cid for cid, cell in self.cells.items() if cell.stale}

    def disable_cell(self, cell_id: CellId_t) -> None:
        """Disables a cell and its descendants in the graph.

        Does not mutate the graph structure, only cell statuses.
        """
        if cell_id not in self.cells:
            raise ValueError(f"Cell {cell_id} not found")

        from marimo._runtime.dataflow import transitive_closure

        for cid in transitive_closure(self, {cell_id}) - {cell_id}:
            cell = self.cells[cid]
            cell.set_runtime_state(status="disabled-transitively")

    def enable_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """Enables a cell in the graph.

        Returns set of cells that were stale and should be re-run.
        """
        if cell_id not in self.cells:
            raise ValueError(f"Cell {cell_id} not found")

        from marimo._runtime.dataflow import transitive_closure

        cells_to_run: set[CellId_t] = set()
        for cid in transitive_closure(self, {cell_id}):
            if not self.is_disabled(cid):
                child = self.cells[cid]
                if child.stale:
                    cells_to_run.add(cid)
                if child.disabled_transitively:
                    child.set_runtime_state("idle")
        return cells_to_run

    def delete_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """Removes a cell from the graph topology.

        Returns the ids of the children of the removed cell.
        """
        if cell_id not in self.cells:
            raise ValueError(f"Cell {cell_id} not found")

        # Grab a reference to children before we remove it from our map.
        children = self._children[cell_id].copy()

        # Purge this cell from the graph (also removes cycles)
        self.remove_node(cell_id)

        return children
