# Copyright 2026 Marimo. All rights reserved.
"""Static classification of a notebook's cells.

A cell is **compilable** iff it has no transitive dependency on a
runtime input — concretely, no ancestor's AST references ``<mo>.ui.*``
or ``<mo>.cli_args*``. This is the only static decision the build
pipeline makes; everything else (persistability, named-vs-anonymous
emission, elidability) happens after execution and lives in
:mod:`marimo._build.plan`.

The setup cell sits outside the bucket system — it's always emitted
as a setup block, runs before everything else, and isn't a graph
parent for hashing.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo._runtime import dataflow

if TYPE_CHECKING:
    from marimo._ast.cell import CellImpl
    from marimo._ast.cell_manager import CellManager
    from marimo._runtime.dataflow import DirectedGraph
    from marimo._types.ids import CellId_t


# Marimo attributes that signal a cell depends on runtime input. Extend
# this set when adding new sources of input non-determinism.
INPUT_ATTRS: frozenset[str] = frozenset({"ui", "cli_args"})


@dataclass(frozen=True)
class Classification:
    """Result of classifying a notebook's cells.

    Every non-setup cell is in exactly one of the two sets.
    """

    compilable: frozenset[CellId_t]
    non_compilable: frozenset[CellId_t]


def classify_static(
    graph: DirectedGraph, cell_manager: CellManager
) -> Classification:
    """Walk the dataflow graph and partition cells into two buckets.

    A cell is non-compilable iff its AST references a known input
    source, OR any of its ancestors do. The setup cell is excluded
    from both buckets.
    """
    setup_id = cell_manager.setup_cell_id
    marimo_names = _collect_marimo_names(graph)

    seeds: set[CellId_t] = {
        cell_id
        for cell_id, cell in graph.cells.items()
        if cell_id != setup_id and _has_input_source(cell, marimo_names)
    }
    non_compilable = dataflow.transitive_closure(
        graph, seeds, children=True, inclusive=True
    )
    compilable = {
        cell_id
        for cell_id in graph.cells
        if cell_id != setup_id and cell_id not in non_compilable
    }
    return Classification(
        compilable=frozenset(compilable),
        non_compilable=frozenset(non_compilable),
    )


def _collect_marimo_names(graph: DirectedGraph) -> set[str]:
    """Names bound to the marimo module itself across the notebook.

    ``import marimo`` and ``import marimo as mo`` are considered;
    ``from marimo import ui`` is not, because it binds the ``ui``
    submodule rather than the package object.
    """
    names: set[str] = set()
    for cell in graph.cells.values():
        for import_data in cell.imports:
            if (
                import_data.module == "marimo"
                and import_data.imported_symbol is None
            ):
                names.add(import_data.definition)
    return names


def _has_input_source(cell: CellImpl, marimo_names: set[str]) -> bool:
    """True iff the cell directly references ``<mo>.ui`` or ``<mo>.cli_args``.

    Catches ``mo.ui.dropdown(...)``, ``mo.cli_args.get(...)`` and bare
    ``mo.cli_args``. This is conservative: a cell that gets a UI value
    indirectly (e.g., through a function argument) won't be flagged
    here, and will instead surface at runtime as a missing-ref error
    that aborts the build.
    """
    return any(
        isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in marimo_names
        and node.attr in INPUT_ATTRS
        for node in ast.walk(cell.mod)
    )
