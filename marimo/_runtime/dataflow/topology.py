# Copyright 2026 Marimo. All rights reserved.
"""Graph topology for cell dependencies.

This module provides the core graph structure for tracking cell relationships.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

from marimo._runtime.dataflow.types import Edge

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._ast.cell import CellImpl
    from marimo._types.ids import CellId_t


class GraphTopology(Protocol):
    """Graph topology protocol.

    This protocol is used to ensure that the graph topology is immutable. All mutations
    should go through the MutableGraphTopology class.
    """

    @property
    def cells(self) -> Mapping[CellId_t, CellImpl]: ...

    @property
    def children(self) -> Mapping[CellId_t, set[CellId_t]]: ...

    @property
    def parents(self) -> Mapping[CellId_t, set[CellId_t]]: ...

    def get_path(self, source: CellId_t, dst: CellId_t) -> list[Edge]: ...

    def ancestors(self, cell_id: CellId_t) -> set[CellId_t]: ...

    def descendants(self, cell_id: CellId_t) -> set[CellId_t]: ...


@dataclass
class MutableGraphTopology(GraphTopology):
    """Pure graph structure: nodes and edges only.

    Responsibilities:
    - Store cells, parents, children mappings
    - Provide fast lookups and traversals
    - No business logic, just data structure
    """

    # Nodes in the graph
    _cells: dict[CellId_t, CellImpl] = field(default_factory=dict)

    # Edge (u, v) means v is a child of u, i.e., v has a reference
    # to something defined in u
    _children: dict[CellId_t, set[CellId_t]] = field(default_factory=dict)

    # Reversed edges (parent pointers) for convenience
    _parents: dict[CellId_t, set[CellId_t]] = field(default_factory=dict)

    @property
    def cells(self) -> Mapping[CellId_t, CellImpl]:
        return self._cells

    @property
    def children(self) -> Mapping[CellId_t, set[CellId_t]]:
        return self._children

    @property
    def parents(self) -> Mapping[CellId_t, set[CellId_t]]:
        return self._parents

    def ancestors(self, cell_id: CellId_t) -> set[CellId_t]:
        """Get all ancestors of a cell."""
        from marimo._runtime.dataflow import transitive_closure

        return transitive_closure(
            self, {cell_id}, children=False, inclusive=False
        )

    def descendants(self, cell_id: CellId_t) -> set[CellId_t]:
        """Get all descendants of a cell."""
        from marimo._runtime.dataflow import transitive_closure

        return transitive_closure(self, {cell_id}, inclusive=False)

    def add_node(self, cell_id: CellId_t, cell: CellImpl) -> None:
        """Add a cell to the graph topology."""
        assert cell_id not in self.cells, f"Cell {cell_id} already in graph"
        self._cells[cell_id] = cell
        self._children[cell_id] = set()
        self._parents[cell_id] = set()

    def remove_node(self, cell_id: CellId_t) -> None:
        """Remove a cell from the graph topology.

        Also removes all edges connected to this cell.
        """
        if cell_id not in self.cells:
            raise ValueError(f"Cell {cell_id} not found")

        # Remove from cells
        del self._cells[cell_id]
        del self._children[cell_id]
        del self._parents[cell_id]

        # Remove from other nodes' parent/child lists
        for elems in self.parents.values():
            if cell_id in elems:
                elems.remove(cell_id)
        for elems in self.children.values():
            if cell_id in elems:
                elems.remove(cell_id)

    def add_edge(self, parent: CellId_t, child: CellId_t) -> None:
        """Add an edge from parent to child."""
        self.children[parent].add(child)
        self.parents[child].add(parent)

    def remove_edge(self, parent: CellId_t, child: CellId_t) -> None:
        """Remove an edge from parent to child."""
        self.children[parent].discard(child)
        self.parents[child].discard(parent)

    def get_path(self, source: CellId_t, dst: CellId_t) -> list[Edge]:
        """Get a path from `source` to `dst`, if any.

        Returns an empty list if source == dst or if no path exists.
        """
        if source == dst:
            return []

        # BFS to find path
        # deque has O(1) append/pop operation
        queue: deque[tuple[CellId_t, list[Edge]]] = deque([(source, [])])
        found = {source}  # set has O(1) lookups

        while queue:
            node, path = queue.popleft()  # O(1) operation
            for cid in self.children[node]:
                if cid not in found:
                    next_path = path + [(node, cid)]
                    if cid == dst:
                        return next_path
                    found.add(cid)
                    queue.append((cid, next_path))
        return []
