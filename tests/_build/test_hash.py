# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.app import App, InternalApp
from marimo._build.classify import classify_static
from marimo._build.hash import compilable_hash, short_hash


def _hashes(app: App) -> dict[str, bytes]:
    internal = InternalApp(app)
    classification = classify_static(internal.graph, internal.cell_manager)
    cache: dict = {}
    out: dict[str, bytes] = {}
    for cid in classification.compilable:
        digest = compilable_hash(
            cid,
            graph=internal.graph,
            compilable=classification.compilable,
            cache=cache,
        )
        out[internal.cell_manager.cell_name(cid)] = digest
    return out


def test_hash_is_stable_across_runs() -> None:
    def make() -> App:
        app = App()

        @app.cell
        def customers() -> tuple[int]:
            customers = 1
            return (customers,)

        @app.cell
        def orders(customers):  # type: ignore[no-untyped-def]
            orders = customers + 1
            return (orders,)

        return app

    assert _hashes(make()) == _hashes(make())


def test_hash_changes_when_source_changes() -> None:
    app1 = App()

    @app1.cell
    def customers_1() -> tuple[int]:
        customers = 1
        return (customers,)

    app2 = App()

    @app2.cell
    def customers_1() -> tuple[int]:  # noqa: F811
        customers = 2  # different value
        return (customers,)

    h1 = _hashes(app1)["customers_1"]
    h2 = _hashes(app2)["customers_1"]
    assert h1 != h2


def test_hash_changes_when_ancestor_source_changes() -> None:
    app1 = App()

    @app1.cell
    def root_cell() -> tuple[int]:
        root = 1
        return (root,)

    @app1.cell
    def child_cell(root):  # type: ignore[no-untyped-def]
        child = root + 1
        return (child,)

    app2 = App()

    @app2.cell
    def root_cell() -> tuple[int]:  # noqa: F811
        root = 2
        return (root,)

    @app2.cell
    def child_cell(root):  # type: ignore[no-untyped-def, no-redef]  # noqa: F811
        child = root + 1
        return (child,)

    h1 = _hashes(app1)
    h2 = _hashes(app2)
    assert h1["root_cell"] != h2["root_cell"]
    # The child's hash must change when the parent's source changes,
    # even though the child's own source is unchanged.
    assert h1["child_cell"] != h2["child_cell"]


def test_hash_unaffected_by_unrelated_cell() -> None:
    app1 = App()

    @app1.cell
    def root_cell() -> tuple[int]:
        root = 1
        return (root,)

    app2 = App()

    @app2.cell
    def root_cell() -> tuple[int]:  # noqa: F811
        root = 1
        return (root,)

    @app2.cell
    def unrelated() -> tuple[int]:
        unrelated = 99
        return (unrelated,)

    assert _hashes(app1)["root_cell"] == _hashes(app2)["root_cell"]


def test_short_hash_stable_length() -> None:
    digest = bytes.fromhex("a" * 32)
    assert short_hash(digest) == "a" * 12


def test_diamond_dag_no_exponential_blowup() -> None:
    # Build a wide diamond. Without memoization this would be exponential.
    app = App()

    @app.cell
    def a() -> tuple[int]:
        a = 0
        return (a,)

    @app.cell
    def b(a):  # type: ignore[no-untyped-def]
        b = a + 1
        return (b,)

    @app.cell
    def c(a):  # type: ignore[no-untyped-def]
        c = a + 2
        return (c,)

    @app.cell
    def d(b, c):  # type: ignore[no-untyped-def]
        d = b + c
        return (d,)

    internal = InternalApp(app)
    classification = classify_static(internal.graph, internal.cell_manager)
    cache: dict = {}
    for cid in classification.compilable:
        compilable_hash(
            cid,
            graph=internal.graph,
            compilable=classification.compilable,
            cache=cache,
        )
    # Cache should hold exactly one entry per compilable cell.
    assert len(cache) == len(classification.compilable) == 4
