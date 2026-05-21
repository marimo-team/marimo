# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import weakref
from unittest.mock import MagicMock, patch

from marimo import ui
from marimo._plugins.ui._core.registry import UIElementRegistry
from marimo._runtime.context import get_context
from marimo._runtime.runtime import Kernel
from marimo._types.ids import UIElementId
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


def test_register_passes_element_id_not_weakref_id() -> None:
    """register() must call delete() with id(element), not id(weakref.ref).

    Regression test for the bug where register() passed id(self._objects[oid])
    — the weakref wrapper — rather than id(self._objects[oid]()) — the element.
    Because delete() derives registered_python_id from id(element), passing the
    weakref id always fails the guard check and causes delete() to silently
    return without cleaning up function-registry entries for the old element.
    """

    class _FakeElement:
        _lens = None

    elem1 = _FakeElement()
    elem2 = _FakeElement()
    oid = UIElementId("ui-test-weakref-id")

    registry = UIElementRegistry()
    registry._objects[oid] = weakref.ref(elem1)

    delete_calls: list[int] = []

    def _tracking_delete(_object_id: UIElementId, python_id: int) -> None:
        delete_calls.append(python_id)

    registry.delete = _tracking_delete  # type: ignore[method-assign]

    mock_ctx = MagicMock()
    mock_ctx.execution_context = MagicMock()

    with patch(
        "marimo._plugins.ui._core.registry.get_context",
        return_value=mock_ctx,
    ):
        registry.register(oid, elem2)  # type: ignore[arg-type]

    assert len(delete_calls) == 1
    assert delete_calls[0] == id(elem1), (
        f"delete() must receive id(element)={id(elem1)}, "
        f"not id(weakref)={id(registry._objects.get(oid, 'gone'))}"
    )


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
