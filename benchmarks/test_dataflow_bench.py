# Copyright 2026 Marimo. All rights reserved.
"""Benchmarks for the reactive dataflow graph.

Every edit rebuilds part of the graph and recomputes the set of cells that
need to run, so graph construction and traversal are on the interactive path.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from benchmarks.notebooks import generate_cell_codes
from marimo._ast.compiler import compile_cell
from marimo._runtime.dataflow import (
    DirectedGraph,
    topological_sort,
    transitive_closure,
)

if TYPE_CHECKING:
    from pytest_codspeed import BenchmarkFixture

    from marimo._ast.cell import CellImpl
    from marimo._types.ids import CellId_t


def _compiled_cells(n_cells: int) -> list[tuple[CellId_t, CellImpl]]:
    from marimo._types.ids import CellId_t

    return [
        (
            CellId_t(str(index)),
            compile_cell(code, cell_id=CellId_t(str(index))),
        )
        for index, code in enumerate(generate_cell_codes(n_cells))
    ]


def _graph(n_cells: int) -> DirectedGraph:
    graph = DirectedGraph()
    for cell_id, cell in _compiled_cells(n_cells):
        graph.register_cell(cell_id, cell)
    return graph


@pytest.fixture(scope="module")
def graph() -> DirectedGraph:
    return _graph(200)


def test_build_graph(benchmark: BenchmarkFixture) -> None:
    """Register 100 cells, as done when a notebook is instantiated."""
    cells = _compiled_cells(100)

    @benchmark
    def _() -> None:
        graph = DirectedGraph()
        for cell_id, cell in cells:
            graph.register_cell(cell_id, cell)


def test_transitive_closure(
    benchmark: BenchmarkFixture, graph: DirectedGraph
) -> None:
    """Compute the descendants of the root cell of a 200-cell notebook."""
    roots = {next(iter(graph.cells))}
    benchmark(transitive_closure, graph, roots)


def test_topological_sort(
    benchmark: BenchmarkFixture, graph: DirectedGraph
) -> None:
    cell_ids = list(graph.cells)
    benchmark(topological_sort, graph, cell_ids)


def test_get_transitive_references(
    benchmark: BenchmarkFixture, graph: DirectedGraph
) -> None:
    """Resolve the transitive refs of every cell, used for cache keys."""
    refs = {name for cell in graph.cells.values() for name in cell.refs}

    @benchmark
    def _() -> None:
        graph.get_transitive_references(refs)
