# Copyright 2026 Marimo. All rights reserved.
"""Static-only schema tests.

Live ``mo.api.input`` schema generation runs on the kernel and is exercised
end-to-end via the dataflow API integration tests; this module covers the
graph-only fallback used by tooling.
"""

from __future__ import annotations

import marimo
from marimo._ast.app import InternalApp
from marimo._dataflow.schema import (
    compute_dataflow_schema,
    compute_dataflow_schema_from_globals,
)


class TestStaticSchema:
    def test_detects_free_vars_as_inputs(self) -> None:
        app = marimo.App()

        @app.cell
        def _(x, y):
            result = x + y
            return (result,)

        schema = compute_dataflow_schema(InternalApp(app))
        assert {i.name for i in schema.inputs} == {"x", "y"}
        assert {o.name for o in schema.outputs} == {"result"}

    def test_excludes_builtins(self) -> None:
        app = marimo.App()

        @app.cell
        def _(x):
            n = len(x)
            return (n,)

        schema = compute_dataflow_schema(InternalApp(app))
        assert "len" not in {i.name for i in schema.inputs}

    def test_schema_id_changes_with_structure(self) -> None:
        a, b = marimo.App(), marimo.App()

        @a.cell
        def _(x, y):
            r = x + y
            return (r,)

        @b.cell
        def _(z):
            r = z + 1
            return (r,)

        s1 = compute_dataflow_schema(InternalApp(a))
        s2 = compute_dataflow_schema(InternalApp(b))
        assert s1.schema_id != s2.schema_id

    def test_explicit_schema_id_is_passthrough(self) -> None:
        app = marimo.App()

        @app.cell
        def _(x):
            r = x + 1
            return (r,)

        schema = compute_dataflow_schema_from_globals(
            graph=InternalApp(app).graph,
            globals_={},
            schema_id="static-test",
        )
        assert schema.schema_id == "static-test"
