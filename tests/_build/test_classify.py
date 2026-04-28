# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.app import App, InternalApp
from marimo._build.classify import classify_static


def _classify(app: App) -> tuple[frozenset[str], frozenset[str], InternalApp]:
    internal = InternalApp(app)
    classification = classify_static(internal.graph, internal.cell_manager)
    return classification.compilable, classification.non_compilable, internal


def _ids(internal: InternalApp, *names: str) -> set[str]:
    return {
        cid
        for cid in internal.graph.cells
        if internal.cell_manager.cell_name(cid) in names
    }


def test_no_inputs_all_compilable() -> None:
    app = App()

    @app.cell
    def customers() -> tuple[int]:
        customers = 1
        return (customers,)

    @app.cell
    def orders(customers: int) -> tuple[int]:
        orders = customers + 1
        return (orders,)

    compilable, non_compilable, internal = _classify(app)
    assert non_compilable == frozenset()
    assert compilable == frozenset(_ids(internal, "customers", "orders"))


def test_ui_cell_propagates_non_compilable() -> None:
    app = App()

    @app.cell
    def _imports() -> tuple:
        import marimo as mo

        return (mo,)

    @app.cell
    def customers() -> tuple[int]:
        customers = 1
        return (customers,)

    @app.cell
    def category(mo):  # type: ignore[no-untyped-def]
        category = mo.ui.dropdown(["a", "b"])
        return (category,)

    @app.cell
    def filtered(customers, category):  # type: ignore[no-untyped-def]
        filtered = customers + category.value
        return (filtered,)

    compilable, non_compilable, internal = _classify(app)
    # `category` directly uses mo.ui; `filtered` inherits via the
    # transitive closure. `_imports` and `customers` are unaffected.
    assert non_compilable == frozenset(_ids(internal, "category", "filtered"))
    assert compilable == frozenset(_ids(internal, "_imports", "customers"))
