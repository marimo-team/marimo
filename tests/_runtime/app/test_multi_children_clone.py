# tests/_runtime/app/test_multi_children_clone.py
import pytest

import marimo as mo


@pytest.mark.asyncio
async def test_multiple_children_disjoint_subscriptions(
    # force_notebook_mode,
    run_all_cells,
    run_only_cells,
):
    # child1 reads parent.x; child2 reads parent.theme
    def build_child(static_ref=True):
        from tests._runtime.conftest import build_child_app as _builder

        return _builder()(static_ref=static_ref)

    child1 = build_child(static_ref=True)
    child2 = build_child(static_ref=True)

    parent = mo.App()

    @parent.cell
    def __():
        import marimo as mo  # noqa: F401

        x_input = 1
        theme_input = "light"
        return mo, x_input, theme_input

    @parent.cell
    def __(x_input, theme_input):
        x = x_input
        theme = theme_input
        return x, theme

    @parent.cell
    async def __(
        child1,
        x,
        # theme
    ):
        await child1.embed(expose={"x": x}, namespace="parent", readonly=True)
        return

    @parent.cell
    async def __(
        child2,
        # x,
        theme,
    ):
        await child2.embed(
            expose={"theme": theme}, namespace="parent", readonly=True
        )
        return

    parent_runner, parent_ids = await run_all_cells(parent)

    c1 = child1._get_kernel_runner()._kernel.globals
    c2 = child2._get_kernel_runner()._kernel.globals

    assert c1["child_seen_x"] == 1
    assert c2["child_seen_theme"] == "light"

    x_theme_cell_id = parent_ids[1]
    parent_runner._kernel.globals["x_input"] = 7
    await run_only_cells(parent, [x_theme_cell_id])

    assert c1["child_seen_x"] == 7
    assert c2["child_seen_theme"] == "light"

    parent_runner._kernel.globals["theme_input"] = "dark"
    await run_only_cells(parent, [x_theme_cell_id])

    assert c1["child_seen_x"] == 7
    assert c2["child_seen_theme"] == "dark"


@pytest.mark.asyncio
async def test_clone_isolation(
    # force_notebook_mode,
    build_child_app,
    build_parent_app,
    run_all_cells,
    run_only_cells,
):
    base_child = build_child_app(static_ref=True)
    childA = base_child.clone()
    childB = base_child.clone()
    parent = build_parent_app(childA)

    @parent.cell
    async def __(
        childB=childB,
        # x=None,
        # theme=None
    ):
        z = 100
        await childB.embed(expose={"z": z}, namespace="parent", readonly=True)
        return (z,)

    parent_runner, parent_ids = await run_all_cells(parent)

    cA = childA._get_kernel_runner()._kernel.globals
    cB = childB._get_kernel_runner()._kernel.globals
    assert cA["child_seen_x"] == 1
    assert cB["child_seen_x"] is None  # childB never reads x

    x_theme_cell_id = parent_ids[1]
    parent_runner._kernel.globals["x_input"] = 9
    await run_only_cells(parent, [x_theme_cell_id])

    assert cA["child_seen_x"] == 9
    assert cB["child_seen_x"] is None
