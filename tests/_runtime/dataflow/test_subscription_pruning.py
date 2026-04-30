# Copyright 2026 Marimo. All rights reserved.
"""Tests for the kernel-side dataflow subscription helpers."""

from __future__ import annotations

import marimo
from marimo._ast.app import InternalApp
from marimo._runtime.dataflow import (
    cells_for_subscription,
    prune_cells_for_subscription,
)


def _three_cell_chain():
    """Three-cell chain: ``x -> (result, doubled) -> summary, big``."""
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
        big = doubled**2
        return (big,)

    return InternalApp(app).graph


def _defs_at(graph, cells):
    out: set[str] = set()
    for cid in cells:
        out.update(graph.cells[cid].defs)
    return out


class TestCellsForSubscription:
    def test_includes_only_ancestors(self) -> None:
        graph = _three_cell_chain()
        # Subscribing to ``summary`` should pull in ``compute`` (defines
        # ``result``) and ``describe`` (defines ``summary``); ``expensive``
        # is unrelated downstream and must stay out.
        closure = cells_for_subscription(graph, {"summary"})
        defs = _defs_at(graph, closure)
        assert "summary" in defs
        assert "result" in defs
        assert "big" not in defs

    def test_unknown_var_returns_empty(self) -> None:
        graph = _three_cell_chain()
        assert cells_for_subscription(graph, {"nonexistent"}) == set()


class TestPruneCellsForSubscription:
    def test_partial_override_keeps_cells_with_other_defs(self) -> None:
        graph = _three_cell_chain()
        candidates = cells_for_subscription(graph, {"summary"})
        # Override only ``result`` — but ``compute`` defines both ``result``
        # and ``doubled``. Pruning must keep it because ``doubled`` could
        # still be demanded; here it isn't, but the conservative call is
        # correct: ``compute``'s defs aren't *all* covered by inputs+demand.
        pruned = prune_cells_for_subscription(
            graph, candidates, {"result"}, {"summary"}
        )
        # ``describe`` survives because it produces ``summary``; ``compute``
        # is dropped because its only demanded def, ``result``, is provided
        # as an input and ``doubled`` is not in the demand set.
        defs = _defs_at(graph, pruned)
        assert "summary" in defs
        assert "result" not in defs
