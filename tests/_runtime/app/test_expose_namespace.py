# tests/_runtime/app/test_expose_namespace.py
import pytest


@pytest.mark.asyncio
async def test_readonly_namespace_behavior(
    # force_notebook_mode,
    build_child_app,
):
    child = build_child_app(static_ref=True)
    runner = child._get_kernel_runner()

    runner.register_exposed_bindings(
        expose={"x": 1}, namespace="parent", readonly=True
    )

    ns = runner._kernel.globals["parent"]
    assert ns.x == 1

    with pytest.raises(AttributeError):
        ns.x = 2

    changed = runner.apply_exposed_binding_updates({"x": 3})
    assert changed == {"x"}
    assert ns.x == 3


@pytest.mark.asyncio
async def test_update_diffing_no_change(
    # force_notebook_mode,
    build_child_app,
):
    child = build_child_app(static_ref=True)
    runner = child._get_kernel_runner()
    runner.register_exposed_bindings(
        expose={"x": 42}, namespace="parent", readonly=True
    )

    changed = runner.apply_exposed_binding_updates({"x": 42})
    assert changed == set()


@pytest.mark.asyncio
async def test_flat_injection_namespace_none(
    # force_notebook_mode,
    build_child_app,
):
    child = build_child_app(static_ref=True)
    runner = child._get_kernel_runner()
    runner.register_exposed_bindings(
        expose={"x": 10}, namespace=None, readonly=True
    )

    assert runner._kernel.globals["x"] == 10
    changed = runner.apply_exposed_binding_updates({"x": 20})
    assert changed == {"x"}
    assert runner._kernel.globals["x"] == 20
