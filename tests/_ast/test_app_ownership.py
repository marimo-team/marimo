# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc
import weakref

from marimo import App

# Cell outputs are expression statements.
# ruff: noqa: B018


def test_container_preserves_function_globals() -> None:
    app = App()

    @app.cell
    def _():
        number = 41

        def plus_one():
            return number + 1

        bundle = [plus_one]
        return bundle, number, plus_one

    _, defs = app.run()
    bundle = defs["bundle"]
    function_ref = weakref.ref(bundle[0])
    del defs
    gc.collect()
    assert bundle[0]() == 42

    del bundle
    gc.collect()
    assert function_ref() is None


def test_transitive_dependency_survives_namespace() -> None:
    app = App()

    @app.cell
    def _():
        class _Payload:
            pass

        payload = _Payload()

        def helper():
            return payload

        def exported():
            return helper()

        return exported, helper, payload

    _, defs = app.run()
    payload_ref = weakref.ref(defs["payload"])
    exported = defs["exported"]
    del defs
    gc.collect()
    assert payload_ref() is not None
    assert exported() is payload_ref()

    del exported
    gc.collect()
    assert payload_ref() is None


def test_alias_does_not_keep_value_alive() -> None:
    app = App()

    @app.cell
    def _():
        class _Payload:
            pass

        value = _Payload()
        alias = value
        return alias, value

    _, defs = app.run()
    value_ref = weakref.ref(defs["value"])
    del defs
    gc.collect()
    assert value_ref() is None


def test_recursive_function_survives_namespace() -> None:
    app = App()

    @app.cell
    def _():
        def f(n):
            return 0 if n == 0 else 1 + f(n - 1)

        return (f,)

    _, defs = app.run()
    f = defs["f"]
    function_ref = weakref.ref(f)
    del defs
    gc.collect()
    assert f(2) == 2

    del f
    gc.collect()
    assert function_ref() is None


def test_function_returned_by_export_survives_export() -> None:
    app = App()

    @app.cell
    def _():
        number = 42

        def inner():
            return number

        def outer():
            return inner

        return inner, number, outer

    _, defs = app.run()
    outer = defs["outer"]
    del defs
    inner = outer()
    function_ref = weakref.ref(inner)
    del outer
    gc.collect()
    assert inner() == 42

    del inner
    gc.collect()
    assert function_ref() is None


def test_output_function_survives_namespace() -> None:
    app = App()

    @app.cell
    def _():
        number = 42

        def result():
            return number

        result
        return number, result

    outputs, defs = app.run()
    result = outputs[0]
    function_ref = weakref.ref(result)
    del outputs, defs
    gc.collect()
    assert result() == 42

    del result
    gc.collect()
    assert function_ref() is None


def test_slotted_instance_preserves_method_globals() -> None:
    app = App()

    @app.cell
    def _():
        number = 42

        class _Box:
            __slots__ = ()

            def value(self):
                return number

        box = _Box()
        return box, number

    _, defs = app.run()
    box = defs["box"]
    del defs
    gc.collect()
    assert box.value() == 42
