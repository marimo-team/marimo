# Copyright 2026 Marimo. All rights reserved.
"""Cycle detection and tracking for cell dependencies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo._runtime.dataflow.types import Edge

if TYPE_CHECKING:
    from collections.abc import Collection

    from marimo._runtime.dataflow.topology import GraphTopology
    from marimo._types.ids import CellId_t


@dataclass
class CycleTracker:
    """Detects and tracks cycles in the graph.

    Responsibilities:
    - Detect cycles when edges are added
    - Maintain cycle set
    - Remove broken cycles
    """

    # The set of cycles in the graph
    # Each cycle is represented as a tuple of edges
    cycles: set[tuple[Edge, ...]] = field(default_factory=set)

    def detect_cycle_for_edge(
        self,
        edge: Edge,
        topology: GraphTopology,
    ) -> tuple[Edge, ...] | None:
        """Detect if adding an edge creates a cycle.

        Args:
            edge: The edge (parent, child) being added
            topology: The graph topology to search for paths

        Returns:
            The cycle as a tuple of edges if one exists, None otherwise.
            The cycle includes the new edge plus the path from child back to parent.
        """
        parent, child = edge
        # Check if there's a path from child back to parent
        # If so, adding this edge creates a cycle
        path = topology.get_path(child, parent)
        if path:
            # The cycle is: edge + path
            cycle = tuple([edge] + path)
            self.cycles.add(cycle)
            return cycle
        return None

    def remove_cycles_with_edge(self, edge: Edge) -> None:
        """Remove all cycles that contain the given edge.

        This should be called when an edge is removed from the graph.
        """
        broken_cycles = [c for c in self.cycles if edge in c]
        for c in broken_cycles:
            self.cycles.remove(c)

    def get_cycles(
        self,
        cell_ids: Collection[CellId_t],
        topology: GraphTopology,
    ) -> list[tuple[Edge, ...]]:
        """Get all cycles among the given cell_ids.

        Args:
            cell_ids: The cells to consider
            topology: The graph topology

        Returns:
            List of cycles, where each cycle is a tuple of edges.
            Only returns cycles where all edges are between cells in cell_ids.
        """
        # Build induced subgraph edges
        induced_edges = set()
        for u in cell_ids:
            if u in topology.children:
                for v in topology.children[u]:
                    if v in cell_ids:
                        induced_edges.add((u, v))

        # Filter cycles to those in the induced subgraph
        return [c for c in self.cycles if all(e in induced_edges for e in c)]
