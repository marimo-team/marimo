# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import gc
import weakref
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from marimo import ui
from marimo._plugins.ui._core.registry import UIElementRegistry
from marimo._plugins.ui._core.ui_element import UIElement
from marimo._runtime.context import get_context
from marimo._runtime.functions import EmptyArgs, Function
from marimo._runtime.runtime import Kernel
from marimo._types.ids import UIElementId
from tests.conftest import ExecReqProvider


@dataclass
class _CyclicDummy:
    cycle: _CyclicDummy = field(init=False)

    def __post_init__(self) -> None:
        self.cycle = self


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
    assert registry.bound_names(array._id) == {"array"}


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
    assert registry.bound_names(array._id) == {"array", "child"}


async def test_dont_delete_element_with_wrong_python_id(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    await k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get(
                """
                s = mo.ui.slider(1, 10)
                """
            ),
        ]
    )
    # Make sure that the slider is registered
    s = k.globals["s"]
    assert get_context().ui_element_registry.get_object(s._id) == s

    # If the Python id doesn't match, don't delete the object.
    get_context().ui_element_registry.delete(s._id, -1)
    assert get_context().ui_element_registry.get_object(s._id) == s


def test_finalizer_does_not_delete_functions_from_non_owner_context(
    executing_kernel: Kernel,
) -> None:
    del executing_kernel
    ctx = get_context()
    owner_registry = UIElementRegistry()
    object_id = UIElementId("shared-object-id")
    function = Function(
        name="function",
        arg_cls=EmptyArgs,
        function=lambda _args: None,
    )
    ctx.function_registry.register(namespace=object_id, function=function)

    dummy = _CyclicDummy()
    owner_registry.register(
        object_id,
        cast("UIElement[Any, Any]", dummy),
    )
    finalizer = weakref.finalize(
        dummy,
        owner_registry.delete,
        object_id,
        id(dummy),
    )
    del dummy

    gc.collect()

    assert not finalizer.alive
    assert (
        ctx.function_registry.get_function(object_id, "function") is function
    )
    with pytest.raises(KeyError):
        owner_registry.get_object(object_id)


def test_owner_registry_delete_removes_function_namespace(
    executing_kernel: Kernel,
) -> None:
    del executing_kernel
    ctx = get_context()
    object_id = UIElementId("owned-object-id")
    function = Function(
        name="function",
        arg_cls=EmptyArgs,
        function=lambda _args: None,
    )
    ctx.function_registry.register(namespace=object_id, function=function)
    dummy = _CyclicDummy()
    ctx.ui_element_registry.register(
        object_id,
        cast("UIElement[Any, Any]", dummy),
    )

    ctx.ui_element_registry.delete(object_id, id(dummy))

    assert ctx.function_registry.get_function(object_id, "function") is None
    with pytest.raises(KeyError):
        ctx.ui_element_registry.get_object(object_id)
