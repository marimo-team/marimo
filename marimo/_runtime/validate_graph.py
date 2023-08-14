# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

import itertools
from collections import defaultdict

from marimo._ast.cell import CellId_t
from marimo._messaging.errors import (
    CycleError,
    DeleteNonlocalError,
    Error,
    MultipleDefinitionError,
)
from marimo._runtime.dataflow import DirectedGraph


def check_for_multiple_definitions(
    graph: DirectedGraph,
) -> dict[CellId_t, list[MultipleDefinitionError]]:
    """Check whether multiple cells define the same global name."""
    errors = defaultdict(list)
    defs = sorted(
        list(set().union(*(cell.defs for _, cell in graph.cells.items())))
    )
    for name in defs:
        defining_cells = graph.definitions[name]
        if len(defining_cells) > 1:
            for cid in defining_cells:
                errors[cid].append(
                    MultipleDefinitionError(
                        name=name,
                        cells=tuple(sorted(defining_cells - set([cid]))),
                    )
                )
    return errors


def check_for_delete_nonlocal(
    graph: DirectedGraph,
) -> dict[CellId_t, list[DeleteNonlocalError]]:
    """Check whether cells delete their refs."""
    errors = defaultdict(list)
    for cid in graph.cells.keys():
        for name in graph.cells[cid].deleted_refs:
            if name in graph.definitions:
                errors[cid].append(
                    DeleteNonlocalError(
                        name=name,
                        cells=tuple(graph.definitions[name]),
                    )
                )
    return errors


def check_for_cycles(graph: DirectedGraph) -> dict[CellId_t, list[CycleError]]:
    """Return cycle errors, if any."""
    errors = defaultdict(list)
    for cycle in graph.cycles:
        nodes_in_cycle: set[CellId_t] = set(sum(cycle, ()))
        for cid in nodes_in_cycle:
            errors[cid].append(CycleError(edges=cycle))
    return errors


def check_for_errors(
    graph: DirectedGraph,
) -> dict[CellId_t, tuple[Error, ...]]:
    """
    Check graph for violations of marimo semantics.

    Return a dict of errors in the graph, with an entry for each cell
    that is involved in an error.
    """
    multiple_definition_errors = check_for_multiple_definitions(graph)
    delete_nonlocal_errors = check_for_delete_nonlocal(graph)
    cycle_errors = check_for_cycles(graph)

    errors: dict[CellId_t, tuple[Error, ...]] = {}
    for cid in set(
        itertools.chain(
            multiple_definition_errors.keys(),
            delete_nonlocal_errors.keys(),
            cycle_errors.keys(),
        )
    ):
        errors[cid] = tuple(
            itertools.chain(
                multiple_definition_errors[cid],
                cycle_errors[cid],
                delete_nonlocal_errors[cid],
            )
        )
    return errors
