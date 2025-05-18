# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import itertools
from collections import defaultdict

from marimo._ast.names import SETUP_CELL_NAME
from marimo._messaging.errors import (
    CycleError,
    DeleteNonlocalError,
    Error,
    MultipleDefinitionError,
    SetupRootError,
)
from marimo._runtime.dataflow import DirectedGraph
from marimo._types.ids import CellId_t


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
                        name=str(name),
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
                        name=str(name),
                        cells=tuple(graph.definitions[name]),
                    )
                )
    return errors


def check_for_invalid_root(
    graph: DirectedGraph,
) -> dict[CellId_t, list[SetupRootError]]:
    """Setup cell cannot have parents."""
    errors: dict[CellId_t, list[SetupRootError]] = defaultdict(list)
    setup_id = CellId_t(SETUP_CELL_NAME)
    if setup_id not in graph.cells:
        return errors
    if ancestors := graph.ancestors(setup_id):
        invalid_refs = tuple(
            (
                ancestor,
                deps,
                setup_id,
            )
            for ancestor in ancestors
            if (
                deps := sorted(
                    graph.cells[ancestor].defs & graph.cells[setup_id].refs
                )
            )
        )
        errors[setup_id].append(
            SetupRootError(
                edges_with_vars=invalid_refs,
            )
        )
    return errors


def check_for_cycles(graph: DirectedGraph) -> dict[CellId_t, list[CycleError]]:
    """Return cycle errors, if any."""
    errors = defaultdict(list)
    for cycle in graph.cycles:
        nodes_in_cycle: set[CellId_t] = set(sum(cycle, ()))
        # before reporting the cells in the cycle to the user,
        # we first annotate the cycle with the variable names
        # that link its cells
        cycle_with_vars = tuple(
            (
                edge[0],
                sorted(graph.cells[edge[0]].defs & graph.cells[edge[1]].refs),
                edge[1],
            )
            for edge in cycle
        )
        for cid in nodes_in_cycle:
            errors[cid].append(CycleError(edges_with_vars=cycle_with_vars))
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
    invalid_root_errors = check_for_invalid_root(graph)

    errors: dict[CellId_t, tuple[Error, ...]] = {}
    for cid in set(
        itertools.chain(
            multiple_definition_errors.keys(),
            delete_nonlocal_errors.keys(),
            cycle_errors.keys(),
            invalid_root_errors.keys(),
        )
    ):
        errors[cid] = tuple(
            itertools.chain(
                multiple_definition_errors[cid],
                cycle_errors[cid],
                delete_nonlocal_errors[cid],
                invalid_root_errors[cid],
            )
        )
    return errors
