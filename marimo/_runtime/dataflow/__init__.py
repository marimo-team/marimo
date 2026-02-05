# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING, Any, Callable, Optional

from marimo import _loggers
from marimo._ast.cell import CellImpl
from marimo._runtime.dataflow.graph import DirectedGraph
from marimo._runtime.dataflow.runner import Runner
from marimo._runtime.dataflow.topology import GraphTopology
from marimo._runtime.dataflow.types import Edge, EdgeWithVar
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Collection


LOGGER = _loggers.marimo_logger()


def transitive_closure(
    graph: GraphTopology,
    cell_ids: set[CellId_t],
    *,
    children: bool = True,
    inclusive: bool = True,
    relatives: Callable[[CellId_t, bool], set[CellId_t]] | None = None,
    predicate: Callable[[CellImpl], bool] | None = None,
) -> set[CellId_t]:
    """Return a set of the passed-in cells and their descendants or ancestors

    If children is True, returns descendants; otherwise, returns ancestors

    If inclusive, includes passed-in cells in the set.

    If relatives is not None, it computes the parents/children of a
        cell

    If predicate, only cells satisfying predicate(cell) are included; applied
        after the relatives are computed
    """

    result: set[CellId_t] = cell_ids.copy() if inclusive else set()
    seen: set[CellId_t] = cell_ids.copy()
    queue: deque[CellId_t] = deque(cell_ids)
    predicate = predicate or (lambda _: True)

    def _relatives(cid: CellId_t) -> set[CellId_t]:
        if relatives is None:
            return graph.children[cid] if children else graph.parents[cid]
        return relatives(cid, children)

    while queue:
        cid = queue.popleft()  # O(1) operation

        relatives_set = _relatives(cid)
        new_relatives = relatives_set - seen

        if new_relatives:
            # Add new relatives to queue and result if they pass predicate
            for relative in new_relatives:
                if predicate(graph.cells[relative]):
                    result.add(relative)
                seen.add(relative)
                queue.append(relative)

    return result


def induced_subgraph(
    graph: GraphTopology, cell_ids: Collection[CellId_t]
) -> tuple[dict[CellId_t, set[CellId_t]], dict[CellId_t, set[CellId_t]]]:
    """Return parents and children for each node in `cell_ids`

    Represents the subgraph induced by `cell_ids`.
    """
    parents: dict[CellId_t, set[CellId_t]] = {}
    children: dict[CellId_t, set[CellId_t]] = {}
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
    graph: GraphTopology, cell_ids: Collection[CellId_t]
) -> list[CellId_t]:
    """Sort `cell_ids` in a topological order using a heap queue.

    When multiple cells have the same parents (including no parents), the tie is broken by
    registration order - cells registered earlier are processed first.
    """
    from heapq import heapify, heappop, heappush

    # Use a list for O(1) lookup of registration order
    registration_order = list(graph.cells.keys())
    top_down_keys = {key: idx for idx, key in enumerate(registration_order)}

    # Build adjacency lists and in-degree counts
    parents, children = induced_subgraph(graph, cell_ids)
    in_degree = {cid: len(parents[cid]) for cid in cell_ids}

    # Initialize heap with roots
    heap = [
        (top_down_keys[cid], cid) for cid in cell_ids if in_degree[cid] == 0
    ]
    heapify(heap)

    sorted_cell_ids: list[CellId_t] = []
    while heap:
        _, cid = heappop(heap)
        sorted_cell_ids.append(cid)

        # Process children
        for child in children[cid]:
            in_degree[child] -= 1
            if in_degree[child] == 0:
                heappush(heap, (top_down_keys[child], child))

    return sorted_cell_ids


def prune_cells_for_overrides(
    graph: DirectedGraph,
    execution_order: Collection[CellId_t],
    overrides: dict[str, Any],
    excluded: Optional[CellId_t] = None,
) -> list[CellId_t]:
    """Prune cells from execution when their definitions are overridden.

    When variable definitions are provided externally (overrides), this function
    identifies cells that would normally define those variables and removes them
    from the execution order. It also validates that all definitions from pruned
    cells are provided in the overrides.

    Args:
        graph: The dataflow graph containing cell dependencies
        execution_order: Ordered collection of cells to execute
        overrides: Dictionary mapping variable names to their override values
        excluded: CellId to ignore for closure determination.

    Returns:
        Filtered execution order excluding cells whose definitions are overridden

    Raises:
        IncompleteRefsError: If overrides don't provide all definitions from
            pruned cells (e.g., a cell defines both x and y, but only x is
            provided in overrides)

    Example:
        If cell A defines variables x and y, and overrides = {"x": 1, "y": 2},
        then cell A will be pruned from execution_order. However, if overrides
        only contains {"x": 1}, an IncompleteRefsError is raised because y is
        missing.
    """
    if not overrides:
        return list(execution_order)

    cells_to_prune: set[CellId_t] = set()
    refs = set(overrides.keys())

    # Find cells that define the overridden variables
    for ref_name in refs:
        if ref_name in graph.definitions:
            defining_cells = graph.get_defining_cells(ref_name)
            cells_to_prune.update(defining_cells)

    # Validate that all definitions from pruned cells are provided
    missing_defs: set[str] = set()
    for cell_id in cells_to_prune:
        if cell_id == excluded:
            continue
        cell = graph.cells[cell_id]
        # Check all definitions this cell would have provided
        for missing in cell.defs - refs:
            missing_defs.add(missing)

    if missing_defs:
        from marimo._ast.errors import IncompleteRefsError

        raise IncompleteRefsError(
            f"When providing refs that override cell definitions, you must "
            f"provide all definitions from those cells. Missing: {sorted(missing_defs)}. "
            f"Provided refs: {sorted(refs)}."
        )

    # Return filtered execution order
    return [cid for cid in execution_order if cid not in cells_to_prune]


def get_import_block_relatives(
    graph: DirectedGraph,
) -> Callable[[CellId_t, bool], set[CellId_t]]:
    def import_block_relatives(cid: CellId_t, children: bool) -> set[CellId_t]:
        if not children:
            return graph.parents[cid]

        cell = graph.cells[cid]
        if not cell.import_workspace.is_import_block:
            return graph.children[cid]

        # This cell is an import block, which should be special cased:
        #
        # We prune definitions that have already been imported from the set of
        # definitions used to find the descendants of this cell.
        unimported_defs = cell.defs - cell.import_workspace.imported_defs

        children_ids = {
            child_id
            for name in unimported_defs
            for child_id in graph.get_referring_cells(name, language="python")
        }

        # If children haven't been executed, then still use imported defs;
        # handle an edge case when an import cell is interrupted by an
        # exception or user interrupt, so that a module is imported but the
        # cell's children haven't run.
        if cell.import_workspace.imported_defs:
            interrupted_states = {
                "interrupted",
                "cancelled",
                "marimo-error",
                None,
            }
            children_ids.update(
                child_id
                for name in cell.import_workspace.imported_defs
                for child_id in graph.get_referring_cells(
                    name, language="python"
                )
                if graph.cells[child_id].run_result_status
                in interrupted_states
            )

        return children_ids

    return import_block_relatives


__all__ = [
    "Edge",
    "EdgeWithVar",
    "DirectedGraph",
    "Runner",
    "get_cycles",
    "get_import_block_relatives",
    "induced_subgraph",
    "prune_cells_for_overrides",
    "topological_sort",
    "transitive_closure",
]
