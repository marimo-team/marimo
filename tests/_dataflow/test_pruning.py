# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import marimo

from marimo._ast.app import InternalApp
from marimo._dataflow.pruning import compute_cells_to_run


def _make_chain_app():
    """Three-cell chain: x -> result -> summary, with side-product doubled."""
    app = marimo.App()

    @app.cell
    def compute(x):
        result = x * 10
        doubled = x * 20
        return result, doubled

    @app.cell
    def describe(result):
        summary = f"val={result}"
        return (summary,)

    @app.cell
    def expensive(doubled):
        big = doubled ** 2
        return (big,)

    return app


class TestComputeCellsToRun:
    def test_subscribe_leaf_runs_ancestors(self) -> None:
        app = _make_chain_app()
        graph = InternalApp(app).graph
        cells = compute_cells_to_run(graph, inputs={"x": 1}, subscribed={"summary"})
        defs = [graph.cells[c].defs for c in cells]
        assert any("result" in d for d in defs)
        assert any("summary" in d for d in defs)

    def test_subscribe_intermediate_prunes_descendants(self) -> None:
        app = _make_chain_app()
        graph = InternalApp(app).graph
        cells = compute_cells_to_run(graph, inputs={"x": 1}, subscribed={"result"})
        all_defs = set()
        for c in cells:
            all_defs.update(graph.cells[c].defs)
        assert "result" in all_defs
        # summary and big should not be in cells that run
        assert "summary" not in all_defs
        assert "big" not in all_defs

    def test_subscribe_multiple_vars(self) -> None:
        app = _make_chain_app()
        graph = InternalApp(app).graph
        cells = compute_cells_to_run(
            graph, inputs={"x": 1}, subscribed={"summary", "big"}
        )
        all_defs = set()
        for c in cells:
            all_defs.update(graph.cells[c].defs)
        assert "summary" in all_defs
        assert "big" in all_defs

    def test_empty_subscription_returns_nothing(self) -> None:
        app = _make_chain_app()
        graph = InternalApp(app).graph
        cells = compute_cells_to_run(graph, inputs={"x": 1}, subscribed=set())
        assert cells == []

    def test_prune_cell_when_all_defs_provided(self) -> None:
        """If a cell's outputs are all in inputs, skip it."""
        app = marimo.App()

        @app.cell
        def _(a):
            b = a + 1
            return (b,)

        @app.cell
        def _(b):
            c = b + 1
            return (c,)

        graph = InternalApp(app).graph
        # Provide b as input — first cell should be pruned
        cells = compute_cells_to_run(
            graph, inputs={"a": 1, "b": 99}, subscribed={"c"}
        )
        all_defs = set()
        for c in cells:
            all_defs.update(graph.cells[c].defs)
        assert "c" in all_defs
        assert "b" not in all_defs  # cell defining b was pruned
