# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import random

import pytest

from marimo._ast import compiler
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime import dataflow
from marimo._runtime.dataflow import edges
from marimo._types.ids import CellId_t

pytestmark = pytest.mark.skipif(
    not DependencyManager.duckdb.has() or not DependencyManager.sqlglot.has(),
    reason="SQL dependencies required",
)


@pytest.mark.parametrize("seed", range(8))
def test_incremental_catalog_edges_match_full_reconciliation(
    seed: int,
) -> None:
    sources = {
        "catalog": "mo.sql(\"ATTACH ':memory:' AS attached\")",
        "duplicate": "mo.sql(\"ATTACH ':memory:' AS Attached\")",
        "schema": "mo.sql('CREATE SCHEMA attached.reports')",
        "memory_schema": "mo.sql('CREATE SCHEMA memory.attached.reports')",
        "table": "mo.sql('CREATE TABLE attached.reports.sales (amount INT)')",
        "memory_table": "mo.sql('CREATE TABLE memory.attached.reports.sales (amount INT)')",
        "query": "mo.sql('SELECT * FROM attached.reports.sales')",
        "memory_query": "mo.sql('SELECT * FROM memory.attached.reports.sales')",
        "python": "sales = 1",
        "mixed": "mo.sql('SELECT * FROM attached.reports.sales')\nsales",
        "delete": "mo.sql('SELECT 1')\ndel sales",
        "feedback": "feedback = mo.sql('SELECT * FROM attached.main.sales')",
        "cyclic": "mo.sql('CREATE TABLE attached.sales AS SELECT * FROM feedback')",
    }
    cells = {
        CellId_t(cid): compiler.compile_cell(code, cell_id=CellId_t(cid))
        for cid, code in sources.items()
    }
    graph = dataflow.DirectedGraph()
    randomizer = random.Random(seed)
    operations = list(cells) * 4
    randomizer.shuffle(operations)
    for cid in operations:
        if cid in graph.cells:
            graph.delete_cell(cid)
        else:
            graph.register_cell(cid, cells[cid])

        # Recompute every cell without the changed-catalog selection filter.
        expected_edges = set()
        for cell_id, cell in graph.cells.items():
            parents, children = edges.compute_edges_for_cell(
                cell_id, cell, graph.topology, graph.definition_registry
            )
            expected_edges.update((parent, cell_id) for parent in parents)
            expected_edges.update((cell_id, child) for child in children)
        actual_edges = {
            (parent, child)
            for parent, children in graph.children.items()
            for child in children
        }
        assert actual_edges == expected_edges, (seed, cid)

        # Kahn's algorithm checks the cycle tracker without sharing its logic.
        remaining = set(graph.cells)
        while remaining:
            roots = {
                cell_id
                for cell_id in remaining
                if not graph.parents[cell_id] & remaining
            }
            if not roots:
                break
            remaining -= roots
        assert bool(graph.cycles) == bool(remaining), (seed, cid)
        for cycle in graph.cycles:
            assert cycle
            assert set(cycle) <= actual_edges, (seed, cid, cycle)
            assert all(
                edge[1] == cycle[(index + 1) % len(cycle)][0]
                for index, edge in enumerate(cycle)
            ), (seed, cid, cycle)
