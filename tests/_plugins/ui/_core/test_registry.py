# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo import ui
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


async def test_cached_element_still_registered(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get("import functools"),
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                @functools.lru_cache
                def slider():
                    return mo.ui.slider(1, 10)
                """
            ),
            (construct_slider := exec_req.get("s = slider()")),
        ]
    )
    # Make sure that the slider is registered
    s = k.globals["s"]
    assert get_context().ui_element_registry.get_object(s._id) == s

    # Re-run the cell but fetch the same slider, since we're using
    # functools.cache. Make sure it's still registered!
    await k.run([construct_slider])
    assert get_context().ui_element_registry.get_object(s._id) == s


def test_resolve_simple_noop(executing_kernel: Kernel) -> None:
    del executing_kernel
    t = ui.text()
    registry = get_context().ui_element_registry
    assert registry.resolve_lens(t._id, "hello world") == (
        t._id,
        "hello world",
    )


def test_resolve_array_noop(executing_kernel: Kernel) -> None:
    del executing_kernel
    array = ui.array([ui.text(), ui.slider(1, 10)])
    registry = get_context().ui_element_registry
    assert registry.resolve_lens(array._id, {"0": "hello world"}) == (
        array._id,
        {"0": "hello world"},
    )


def test_resolve_lens_array(executing_kernel: Kernel) -> None:
    del executing_kernel
    array = ui.array([ui.text(), ui.slider(1, 10)])
    registry = get_context().ui_element_registry
    assert registry.resolve_lens(array[0]._id, "hello world") == (
        array._id,
        {"0": "hello world"},
    )
    assert registry.resolve_lens(array[1]._id, 5) == (
        array._id,
        {"1": 5},
    )


def test_resolve_lens_nested(executing_kernel: Kernel) -> None:
    del executing_kernel

    # an array containing an array containing a dict
    dict_inner = ui.dictionary({"0": ui.text(), "1": ui.slider(1, 10)})
    array_inner = ui.array([ui.text(), ui.slider(1, 10), dict_inner])
    array = ui.array([ui.text(), ui.slider(1, 10), array_inner])

    registry = get_context().ui_element_registry

    # array resolves to itself
    assert registry.resolve_lens(array._id, {"0": "hello world"}) == (
        array._id,
        {"0": "hello world"},
    )

    # setting the simple elements of the array
    assert registry.resolve_lens(array[0]._id, "hello world") == (
        array._id,
        {"0": "hello world"},
    )
    assert registry.resolve_lens(array[1]._id, 5) == (
        array._id,
        {"1": 5},
    )

    # setting some elements of the inner array
    assert registry.resolve_lens(
        array[2]._id,
        {"0": "hello world", "1": 5},
    ) == (
        array._id,
        {"2": {"0": "hello world", "1": 5}},
    )
    assert registry.resolve_lens(
        array[2][0]._id,
        "hello world",
    ) == (
        array._id,
        {"2": {"0": "hello world"}},
    )
    assert registry.resolve_lens(
        array[2][1]._id,
        5,
    ) == (
        array._id,
        {"2": {"1": 5}},
    )

    # setting some elements of the inner dict
    assert registry.resolve_lens(
        array[2][2]._id,
        {"0": "hello world", "1": 5},
    ) == (
        array._id,
        {"2": {"2": {"0": "hello world", "1": 5}}},
    )
    assert registry.resolve_lens(
        array[2][2]["1"]._id,
        5,
    ) == (
        array._id,
        {"2": {"2": {"1": 5}}},
    )


async def test_lens_not_bound(k: Kernel, exec_req: ExecReqProvider) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                array = mo.ui.array([mo.ui.text(), mo.ui.slider(1, 10)])
                """
            )
        ]
    )
    array = k.globals["array"]
    registry = get_context().ui_element_registry
    assert not registry.bound_names(array[0]._id)
    assert registry.bound_names(array._id) == set(["array"])


async def test_parent_bound_to_view(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get(
                """
                import marimo as mo
                array = mo.ui.array([mo.ui.text(), mo.ui.slider(1, 10)])
                child = array[0]
                """
            )
        ]
    )
    array = k.globals["array"]
    registry = get_context().ui_element_registry
    assert registry.bound_names(array._id) == set(["array", "child"])
