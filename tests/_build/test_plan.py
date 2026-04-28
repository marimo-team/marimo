# Copyright 2026 Marimo. All rights reserved.
"""Tests for :mod:`marimo._build.plan`.

The plan is fed mocked ``captured_defs`` so we can exercise the
inductive rule independently of execution.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from marimo._ast.app import App, InternalApp
from marimo._build.classify import classify_static
from marimo._build.plan import CellKind, compute_plan

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._types.ids import CellId_t


def _kinds_by_name(
    app: App, captured_defs: Mapping[str, Mapping[str, Any]]
) -> dict[str, CellKind]:
    """Run :func:`compute_plan` against ``app`` and return ``{name: kind}``.

    ``captured_defs`` is keyed by cell name, not id, for readable
    fixtures; we translate to ids internally.
    """
    internal = InternalApp(app)
    classification = classify_static(internal.graph, internal.cell_manager)
    name_to_id = {
        internal.cell_manager.cell_name(cid): cid
        for cid in internal.graph.cells
    }
    captured_by_id: dict[CellId_t, dict[str, Any]] = {
        name_to_id[name]: dict(defs) for name, defs in captured_defs.items()
    }
    plan = compute_plan(
        graph=internal.graph,
        cell_manager=internal.cell_manager,
        classification=classification,
        captured_defs=captured_by_id,
    )
    return {
        internal.cell_manager.cell_name(cid): cell_plan.kind
        for cid, cell_plan in plan.cells.items()
    }


def test_named_persistable_becomes_loader() -> None:
    app = App()

    @app.cell
    def customers() -> tuple[int]:
        customers = 1
        return (customers,)

    assert _kinds_by_name(app, {"customers": {"customers": 1}}) == {
        "customers": CellKind.LOADER,
    }


def test_anonymous_with_no_consumer_is_elided() -> None:
    """No retained cell needs the def -> elided."""
    app = App()

    @app.cell
    def _intermediate() -> tuple[int]:
        x = 1
        return (x,)

    @app.cell
    def named(x):  # type: ignore[no-untyped-def]
        named = x + 1
        return (named,)

    kinds = _kinds_by_name(
        app,
        {"_intermediate": {"x": 1}, "named": {"named": 2}},
    )
    # `named` is a LOADER, so its precomputed value already encodes x:
    # nothing in the output cares about x.
    assert kinds == {
        "_intermediate": CellKind.ELIDED,
        "named": CellKind.LOADER,
    }


def test_anonymous_with_verbatim_consumer_becomes_loader() -> None:
    """A VERBATIM consumer of the def keeps the cell alive as a loader."""
    app = App()

    @app.cell
    def _imports() -> tuple:
        import marimo as mo

        return (mo,)

    @app.cell
    def _shared() -> tuple[int]:
        shared = 5
        return (shared,)

    @app.cell
    def picker(mo):  # type: ignore[no-untyped-def]
        picker = mo.ui.dropdown(["a", "b"])
        return (picker,)

    @app.cell
    def consume(shared, picker):  # type: ignore[no-untyped-def]
        consume = shared + len(picker.value)
        return (consume,)

    kinds = _kinds_by_name(
        app,
        {
            "_imports": {"mo": object()},  # not persistable -> VERBATIM
            "_shared": {"shared": 5},
        },
    )
    # `consume` is non-compilable (descendant of UI). It refs `shared`,
    # so `_shared` is retained as a LOADER instead of being elided.
    assert kinds["_shared"] == CellKind.LOADER
    assert kinds["consume"] == CellKind.VERBATIM
    assert kinds["picker"] == CellKind.VERBATIM
    assert kinds["_imports"] == CellKind.VERBATIM


def test_non_persistable_cell_does_not_cascade() -> None:
    """A non-persistable parent makes itself VERBATIM, but not its children.

    The user's inductive rule is per-cell on persistability: a cell
    that depends on a non-persistable parent can still be compiled if
    its *own* defs are persistable.
    """
    app = App()

    @app.cell
    def _make_lambda() -> tuple:
        f = lambda x: x + 1  # noqa: E731 — not persistable
        return (f,)

    @app.cell
    def downstream(f):  # type: ignore[no-untyped-def]
        downstream = f(5)  # value is 6, persistable
        return (downstream,)

    kinds = _kinds_by_name(
        app,
        {
            "_make_lambda": {"f": (lambda x: x)},
            "downstream": {"downstream": 6},
        },
    )
    assert kinds == {
        "_make_lambda": CellKind.VERBATIM,
        "downstream": CellKind.LOADER,
    }


def test_no_def_cell_is_verbatim() -> None:
    """Side-effect-only cells (no defs) are emitted verbatim, never elided."""
    app = App()

    @app.cell
    def _imports() -> tuple:
        import marimo as mo

        return (mo,)

    @app.cell
    def _print(mo) -> tuple:  # type: ignore[no-untyped-def]
        print("debug:", mo)  # no defs
        return ()

    kinds = _kinds_by_name(
        app,
        {
            "_imports": {"mo": object()},
            "_print": {},
        },
    )
    # _imports is non-persistable -> VERBATIM.
    # _print has no defs -> VERBATIM (would otherwise be wrongly elided).
    assert kinds == {
        "_imports": CellKind.VERBATIM,
        "_print": CellKind.VERBATIM,
    }


def test_named_with_no_consumer_still_a_loader() -> None:
    """Explicit names are honored even without a downstream consumer."""
    app = App()

    @app.cell
    def settings() -> tuple[dict[str, int]]:
        settings = {"version": 1}
        return (settings,)

    assert _kinds_by_name(app, {"settings": {"settings": {"version": 1}}}) == {
        "settings": CellKind.LOADER,
    }


def test_chain_of_anonymous_cells_collapses() -> None:
    """A chain of anonymous compilable cells should fully elide."""
    app = App()

    @app.cell
    def _a() -> tuple[int]:
        x = 1
        return (x,)

    @app.cell
    def _b(x):  # type: ignore[no-untyped-def]
        y = x + 1
        return (y,)

    @app.cell
    def named(y):  # type: ignore[no-untyped-def]
        named = y * 2
        return (named,)

    kinds = _kinds_by_name(
        app,
        {
            "_a": {"x": 1},
            "_b": {"y": 2},
            "named": {"named": 4},
        },
    )
    assert kinds == {
        "_a": CellKind.ELIDED,
        "_b": CellKind.ELIDED,
        "named": CellKind.LOADER,
    }
