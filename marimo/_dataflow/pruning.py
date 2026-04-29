# Copyright 2026 Marimo. All rights reserved.
"""Dataflow graph pruning for variable-level subscriptions.

Given a set of subscribed output variables and a set of input overrides,
computes the minimal set of cells that must run to produce those outputs.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._runtime.dataflow import topological_sort, transitive_closure

if TYPE_CHECKING:
    from marimo._runtime.dataflow.graph import DirectedGraph
    from marimo._types.ids import CellId_t


def compute_cells_to_run(
    graph: DirectedGraph,
    inputs: dict[str, Any],
    subscribed: set[str],
    changed_inputs: set[str] | None = None,
) -> list[CellId_t]:
    """Compute the minimal set of cells needed to produce subscribed variables.

    Algorithm:
    1. Find cells that DEFINE the subscribed variables (sink cells).
    2. Compute the transitive ancestors of sinks (needed cells).
    3. If changed_inputs is provided, intersect with the descendants of
       cells that reference those changed inputs (affected cells).
    4. Prune cells whose defs are fully covered by the provided inputs.
    5. Return in topological order.

    Args:
        graph: The directed dataflow graph.
        inputs: Dict of variable name -> value provided by the client.
        subscribed: Set of variable names the client wants updates for.
        changed_inputs: If provided, only re-run cells affected by these
            changed inputs (incremental mode). If None, run all needed cells
            (full mode — used for the first request in a session).

    Returns:
        List of cell IDs in topological order.
    """
    if not subscribed:
        return []

    # 1. Cells that define the subscribed variables
    sink_cells: set[CellId_t] = set()
    for var_name in subscribed:
        sink_cells.update(graph.get_defining_cells(var_name))

    if not sink_cells:
        return []

    # 2. Transitive ancestors of sinks (everything needed to produce them)
    needed = transitive_closure(graph, sink_cells, children=False)

    # 3. If incremental, intersect with the affected subgraph
    if changed_inputs is not None:
        source_cells: set[CellId_t] = set()
        for var_name in changed_inputs:
            source_cells.update(
                graph.get_referring_cells(var_name, language="python")
            )
        if source_cells:
            affected = transitive_closure(graph, source_cells, children=True)
            needed = needed & affected
        else:
            # No cells reference the changed inputs — nothing to run
            return []

    # 4. Prune cells whose defs are all provided as inputs
    candidates = _prune_for_subscription(graph, needed, inputs, subscribed)

    # 5. Also skip disabled cells
    candidates = {
        cid for cid in candidates if not graph.is_disabled(cid)
    }

    return topological_sort(graph, candidates)


def _prune_for_subscription(
    graph: DirectedGraph,
    needed_cells: set[CellId_t],
    inputs: dict[str, Any],
    subscribed: set[str],
) -> set[CellId_t]:
    """Prune cells whose definitions are fully covered by inputs.

    A cell is prunable if ALL of its defs satisfy at least one of:
      - The def is in `inputs` (overridden by the client).
      - The def is not in `subscribed` AND no other needed cell references it.

    In other words: a cell must run if it defines at least one variable that
    is either directly subscribed or referenced by another needed cell, AND
    that variable is not already provided in the inputs.

    Args:
        graph: The directed dataflow graph.
        needed_cells: Set of cell IDs we plan to run.
        inputs: Provided input values.
        subscribed: The variables the client wants.

    Returns:
        Filtered set of cell IDs with prunable cells removed.
    """
    if not inputs:
        return needed_cells

    input_names = set(inputs.keys())

    # Pre-compute the set of refs across all needed cells (what cells need)
    needed_refs: set[str] = set()
    for cid in needed_cells:
        cell = graph.cells.get(cid)
        if cell is not None:
            needed_refs.update(cell.refs)

    # The "demand set" = everything that's either subscribed or referenced
    demand = subscribed | needed_refs

    cells_to_prune: set[CellId_t] = set()
    for cid in needed_cells:
        cell = graph.cells.get(cid)
        if cell is None:
            continue

        if not cell.defs:
            continue

        # A cell is prunable if none of its defs are both demanded AND un-provided
        has_needed_def = False
        for d in cell.defs:
            if d in input_names:
                # This def is provided by inputs — doesn't require running
                continue
            if d in demand:
                # This def is needed and NOT in inputs — cell must run
                has_needed_def = True
                break

        if not has_needed_def:
            cells_to_prune.add(cid)

    return needed_cells - cells_to_prune
