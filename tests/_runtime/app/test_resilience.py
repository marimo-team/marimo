# tests/_runtime/app/test_resilience.py
import pytest


@pytest.mark.asyncio
async def test_child_cannot_mutate_parent_namespace(
    # force_notebook_mode,
    build_child_app,
    build_parent_app,
    run_all_cells,
):
    # Add a mutating cell to the child that tries to assign `parent.x = ..`
    child = build_child_app(static_ref=True)

    @child.cell
    def __():
        attempted_set_result = None
        try:
            parent.x = 5  # noqa: F821
        except Exception as e:
            attempted_set_result = type(e).__name__
        return (attempted_set_result,)

    parent = build_parent_app(child)
    await run_all_cells(parent)

    cgl = child._get_kernel_runner()._kernel.globals
    assert cgl["attempted_set_result"] in {"AttributeError", "NameError"}


@pytest.mark.asyncio
async def test_hook_error_resilience(
    # force_notebook_mode,
    build_child_app,
    build_parent_app,
    run_all_cells,
    run_only_cells,
    monkeypatch,
):
    from marimo._ast.app import InternalApp

    child = build_child_app(static_ref=True)
    parent = build_parent_app(child)
    parent_runner, parent_ids = await run_all_cells(parent)

    def boom(
        _self,
        # updates
    ):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        InternalApp, "_schedule_exposed_binding_updates", boom, raising=True
    )

    x_theme_cell_id = parent_ids[1]
    parent_runner._kernel.globals["x_input"] = 11
    # Should not raise even if a child propagation fails
    await run_only_cells(parent, [x_theme_cell_id])

    assert True
