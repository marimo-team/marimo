# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import threading
from collections.abc import Collection
from dataclasses import dataclass, field
from typing import Tuple

from marimo import _loggers
from marimo._ast.cell import Cell, CellId_t, code_key

Edge = Tuple[CellId_t, CellId_t]

LOGGER = _loggers.marimo_logger()


# TODO(akshayka): Add method disable_cell, enable_cell which handle
# state transitions on cells
@dataclass(frozen=True)
class DirectedGraph:
    # Nodes in the graph
    cells: dict[CellId_t, Cell] = field(default_factory=dict)

    # Edge (u, v) means v is a child of u, i.e., v has a reference
    # to something defined in u
    children: dict[CellId_t, set[CellId_t]] = field(default_factory=dict)

    # Reversed edges (parent pointers) for convenience
    parents: dict[CellId_t, set[CellId_t]] = field(default_factory=dict)

    # Cells that define the same name
    #
    # siblings[cell_id] is a set of cell ids, one for each cell that shares a
    # definition with cell_id.
    #
    # If this dict is non-empty, then the marimo program contains multiply
    # defined names (and is therefore in an error state)
    siblings: dict[CellId_t, set[CellId_t]] = field(default_factory=dict)

    # A mapping from defs to the cells that define them
    definitions: dict[str, set[CellId_t]] = field(default_factory=dict)

    # The set of cycles in the graph
    cycles: set[tuple[Edge, ...]] = field(default_factory=set)

    # This lock must be acquired during methods that mutate the graph; it's
    # only needed because a graph is shared between the kernel and the code
    # completion service. It should almost always be uncontended.
    lock: threading.Lock = field(default_factory=threading.Lock)

    def is_cell_cached(self, cell_id: CellId_t, code: str) -> bool:
        """Whether a cell with id `cell_id` and code `code` is in the graph."""
        return (
            cell_id in self.cells and code_key(code) == self.cells[cell_id].key
        )

    def get_referring_cells(self, name: str) -> set[CellId_t]:
        """Get all cells that have a ref to `name`."""
        return set([cid for cid in self.cells if name in self.cells[cid].refs])

    def get_path(self, source: CellId_t, dst: CellId_t) -> list[Edge]:
        """Get a path from `source` to `dst`, if any."""
        if source == dst:
            return []

        queue: list[tuple[CellId_t, list[Edge]]] = [(source, [])]
        found = set()
        while queue:
            node, path = queue.pop(0)
            found.add(node)
            for cid in self.children[node]:
                if cid not in found:
                    next_path = path + [(node, cid)]
                    if cid == dst:
                        return next_path
                    queue.append((cid, next_path))
        return []

    def register_cell(self, cell_id: CellId_t, cell: Cell) -> None:
        """Add a cell to the graph.

        Mutates the graph, acquiring `self.lock`.

        Requires that `cell_id` is not already in the graph.
        """
        with self.lock:
            assert cell_id not in self.cells
            self.cells[cell_id] = cell
            # Children are the set of cells that refer to a name defined in
            # `cell`
            children: set[CellId_t] = set()
            # Cells that define the same name as this one
            siblings: set[CellId_t] = set()
            # Parents are the set of cells that define a name referred to by
            # `cell`
            parents: set[CellId_t] = set()

            # Populate children, siblings, and parents
            self.children[cell_id] = children
            self.siblings[cell_id] = siblings
            self.parents[cell_id] = parents
            for name in cell.defs:
                self.definitions.setdefault(name, set()).add(cell_id)
                for sibling in self.definitions[name]:
                    if sibling != cell_id:
                        siblings.add(sibling)
                        self.siblings[sibling].add(cell_id)

                # a cell can refer to its own defs, but that doesn't add an
                # edge to the dependency graph
                referring_cells = self.get_referring_cells(name) - set(
                    (cell_id,)
                )
                # we will add an edge (cell_id, v) for each v in
                # referring_cells; if there is a path from v to cell_id, then
                # the new edge will form a cycle
                for v in referring_cells:
                    path = self.get_path(v, cell_id)
                    if path:
                        self.cycles.add(tuple([(cell_id, v)] + path))

                children.update(referring_cells)
                for child in referring_cells:
                    self.parents[child].add(cell_id)

            for name in cell.refs:
                other_ids = (
                    self.definitions[name]
                    if name in self.definitions
                    else set()
                ) - set((cell_id,))
                # if other is empty, this means that the user is going to
                # get a NameError once the cell is run, unless the symbol
                # is say a builtin
                for other_id in other_ids:
                    parents.add(other_id)
                    # we are adding an edge (other_id, cell_id). If there
                    # is a path from cell_id to other_id, then the new
                    # edge forms a cycle
                    path = self.get_path(cell_id, other_id)
                    if path:
                        self.cycles.add(tuple([(other_id, cell_id)] + path))
                    self.children[other_id].add(cell_id)

    def disable_cell(self, cell_id: CellId_t) -> None:
        """
        Disables a cell in the graph.

        Does not mutate the graph (but does mutate cell statuses).

        Returns the ids of descendants that are disabled transitively.
        """
        if cell_id not in self.cells:
            raise ValueError(f"Cell {cell_id} not found")

        for cid in transitive_closure(self, set([cell_id])) - set([cell_id]):
            cell = self.cells[cid]
            if not cell.stale:
                cell.set_status(status="disabled-transitively")

    def enable_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """
        Enables a cell in the graph.

        Does not mutate the graph (but does mutate cell statuses).

        Returns:
        - set of cells that were stale and should be re-run
        """
        if cell_id not in self.cells:
            raise ValueError(f"Cell {cell_id} not found")

        cells_to_run: set[CellId_t] = set()
        for cid in transitive_closure(self, set([cell_id])):
            if not self.is_disabled(cid):
                child = self.cells[cid]
                if child.stale:
                    # cell was previously disabled, is no longer
                    # disabled, and is stale: needs to run.
                    cells_to_run.add(cid)
                elif child.disabled_transitively:
                    # cell is no longer disabled: status -> idle
                    child.set_status("idle")
        return cells_to_run

    def delete_cell(self, cell_id: CellId_t) -> set[CellId_t]:
        """Removes a cell from the graph.

        Mutates the graph, acquiring `self.lock`.

        Returns the ids of the children of the removed cell.
        """
        with self.lock:
            if cell_id not in self.cells:
                raise ValueError(f"Cell {cell_id} not found")

            # Removing this cell from its defs' definer sets
            for name in self.cells[cell_id].defs:
                name_defs = self.definitions[name]
                name_defs.remove(cell_id)
                if not name_defs:
                    # No more cells define this name, so we remove it from the
                    # graph
                    del self.definitions[name]

            # Remove cycles that are broken from removing this cell.
            edges = [(cell_id, child) for child in self.children[cell_id]] + [
                (parent, cell_id) for parent in self.parents[cell_id]
            ]
            for e in edges:
                broken_cycles = [c for c in self.cycles if e in c]
                for c in broken_cycles:
                    self.cycles.remove(c)

            # Grab a reference to children before we remove it from our map.
            children = self.children[cell_id]

            # Purge this cell from the graph.
            del self.cells[cell_id]
            del self.children[cell_id]
            del self.parents[cell_id]
            del self.siblings[cell_id]

            for elems in self.parents.values():
                if cell_id in elems:
                    elems.remove(cell_id)
            for elems in self.children.values():
                if cell_id in elems:
                    elems.remove(cell_id)
            for elems in self.siblings.values():
                if cell_id in elems:
                    elems.remove(cell_id)

            return children

    def is_disabled(self, cell_id: CellId_t) -> bool:
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


def transitive_closure(
    graph: DirectedGraph, cell_ids: set[CellId_t]
) -> set[CellId_t]:
    """Return a set of the passed-in cells and their descendants."""
    cells = set()
    queue = list(cell_ids)
    while queue:
        cid = queue.pop(0)
        cells.add(cid)
        for child_id in graph.children[cid]:
            if child_id not in cells:
                queue.append(child_id)
    return cells


def induced_subgraph(
    graph: DirectedGraph, cell_ids: Collection[CellId_t]
) -> tuple[dict[CellId_t, set[CellId_t]], dict[CellId_t, set[CellId_t]]]:
    """Return parents and children for each node in `cell_ids`

    Represents the subgraph induced by `cell_ids`.
    """
    parents = {}
    children = {}
    for cid in cell_ids:
        parents[cid] = set(p for p in graph.parents[cid] if p in cell_ids)
        children[cid] = set(c for c in graph.children[cid] if c in cell_ids)
    return parents, children


def get_cycles(
    graph: DirectedGraph, cell_ids: Collection[CellId_t]
) -> list[tuple[Edge, ...]]:
    """Get all cycles among `cell_ids`."""
    _, induced_children = induced_subgraph(graph, cell_ids)
    induced_edges = set(
        [(u, v) for u in induced_children for v in induced_children[u]]
    )
    return [c for c in graph.cycles if all(e in induced_edges for e in c)]


def topological_sort(
    graph: DirectedGraph, cell_ids: Collection[CellId_t]
) -> list[CellId_t]:
    """Sort `cell_ids` in a topological order."""
    parents, children = induced_subgraph(graph, cell_ids)
    roots = [cid for cid in cell_ids if not parents[cid]]
    sorted_cell_ids = []
    while roots:
        cid = roots.pop(0)
        sorted_cell_ids.append(cid)
        for child in children[cid]:
            parents[child].remove(cid)
            if not parents[child]:
                roots.append(child)
    # TODO make sure parents for each id is empty, otherwise cycle
    return sorted_cell_ids
