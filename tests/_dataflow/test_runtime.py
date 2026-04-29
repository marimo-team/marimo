# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio

import marimo
from marimo._ast.app import InternalApp
from marimo._dataflow.protocol import Kind, RunEvent, VarEvent
from marimo._dataflow.runtime import DataflowRuntime


def _make_free_var_app():
    app = marimo.App()

    @app.cell
    def _(x, y):
        result = x + y
        return (result,)

    @app.cell
    def _(result):
        label = f"sum={result}"
        return (label,)

    return app


def _make_ui_input_app():
    app = marimo.App()

    @app.cell
    def _():
        import marimo as mo

        x = mo.api.input(min=0, max=100, default=10)
        y = mo.api.input(min=0, max=100, default=20)
        return mo, x, y

    @app.cell
    def _(x, y):
        result = x.value + y.value
        return (result,)

    @app.cell
    def _(result):
        label = f"sum={result}"
        return (label,)

    return app


def _run(runtime, inputs, subscribed):
    return asyncio.run(runtime.apply_inputs_and_run(inputs, subscribed))


import pytest


@pytest.fixture(autouse=True)
def _close_runtimes():
    runtimes: list = []
    orig_init = DataflowRuntime.__init__

    def tracking_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        runtimes.append(self)

    DataflowRuntime.__init__ = tracking_init
    try:
        yield
    finally:
        DataflowRuntime.__init__ = orig_init
        for r in runtimes:
            r.close()


class TestDataflowRuntimeFreeVars:
    def test_produces_var_events_with_correct_values(self) -> None:
        runtime = DataflowRuntime(InternalApp(_make_free_var_app()))
        events = _run(runtime, {"x": 3, "y": 4}, {"result", "label"})

        var_events = {e.name: e for e in events if isinstance(e, VarEvent)}
        assert var_events["result"].value == 7
        assert var_events["result"].kind == Kind.INTEGER
        assert var_events["label"].value == "sum=7"

    def test_run_event_brackets_execution(self) -> None:
        runtime = DataflowRuntime(InternalApp(_make_free_var_app()))
        events = _run(runtime, {"x": 1, "y": 2}, {"result"})

        run_events = [e for e in events if isinstance(e, RunEvent)]
        assert run_events[0].status == "started"
        assert run_events[-1].status == "done"
        assert (run_events[-1].elapsed_ms or 0) >= 0

    def test_subscription_filters_emitted_vars(self) -> None:
        runtime = DataflowRuntime(InternalApp(_make_free_var_app()))
        events = _run(runtime, {"x": 1, "y": 2}, {"label"})

        var_names = {e.name for e in events if isinstance(e, VarEvent)}
        assert var_names == {"label"}


class TestDataflowRuntimeUIInputs:
    def test_default_values_used_when_no_overrides(self) -> None:
        runtime = DataflowRuntime(InternalApp(_make_ui_input_app()))
        events = _run(runtime, {}, {"result"})

        var_events = {e.name: e for e in events if isinstance(e, VarEvent)}
        assert var_events["result"].value == 30

    def test_overrides_route_through_ui_elements(self) -> None:
        runtime = DataflowRuntime(InternalApp(_make_ui_input_app()))
        events = _run(runtime, {"x": 5, "y": 7}, {"result"})

        var_events = {e.name: e for e in events if isinstance(e, VarEvent)}
        assert var_events["result"].value == 12

    def test_persistent_state_across_runs(self) -> None:
        runtime = DataflowRuntime(InternalApp(_make_ui_input_app()))
        _run(runtime, {"x": 5, "y": 7}, {"result"})
        events2 = _run(runtime, {"x": 100}, {"result"})

        var_events = {e.name: e for e in events2 if isinstance(e, VarEvent)}
        assert var_events["result"].value == 107
