# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import marimo
from marimo._ast.app import InternalApp
from marimo._dataflow.runtime import DataflowRuntime
from marimo._dataflow.schema import compute_dataflow_schema


def _schema_for(app):
    runtime = DataflowRuntime(InternalApp(app))
    try:
        return runtime.submit_to_worker(compute_dataflow_schema, runtime)
    finally:
        runtime.close()


class TestComputeDataflowSchema:
    def test_detects_free_vars_as_inputs(self) -> None:
        app = marimo.App()

        @app.cell
        def _(x, y):
            result = x + y
            doubled = result * 2
            return result, doubled

        @app.cell
        def _(result):
            summary = f"got {result}"
            return (summary,)

        schema = _schema_for(app)
        assert {i.name for i in schema.inputs} == {"x", "y"}
        assert {o.name for o in schema.outputs} == {
            "result",
            "doubled",
            "summary",
        }

    def test_detects_mo_api_inputs_as_ui_elements(self) -> None:
        app = marimo.App()

        @app.cell
        def _():
            import marimo as mo

            threshold = mo.api.input(min=0, max=100, default=50)
            category = mo.api.input(
                options=["all", "A", "B"], default="all"
            )
            return threshold, category, mo

        @app.cell
        def _(threshold, category):
            label = f"{category}@{threshold.value}"
            return (label,)

        schema = _schema_for(app)
        input_names = {i.name for i in schema.inputs}
        assert input_names == {"threshold", "category"}
        threshold = next(i for i in schema.inputs if i.name == "threshold")
        assert threshold.default == 50
        assert threshold.constraints is not None
        assert threshold.constraints.get("min") == 0
        assert threshold.constraints.get("max") == 100
        assert "label" in {o.name for o in schema.outputs}

    def test_excludes_builtins(self) -> None:
        app = marimo.App()

        @app.cell
        def _(x):
            n = len(x)
            return (n,)

        schema = _schema_for(app)
        names = {i.name for i in schema.inputs}
        assert "len" not in names
        assert "x" in names

    def test_schema_id_changes_with_structure(self) -> None:
        app1 = marimo.App()

        @app1.cell
        def _(x, y):
            r = x + y
            return (r,)

        app2 = marimo.App()

        @app2.cell
        def _(a):
            r = a + 1
            return (r,)

        assert _schema_for(app1).schema_id != _schema_for(app2).schema_id
