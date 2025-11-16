# tests/_runtime/app/test_embed_reactivity.py
import pytest


@pytest.mark.asyncio
async def test_reactive_update_with_static_reference(
    # force_notebook_mode,
    build_child_app,
    build_parent_app,
    run_all_cells,
    run_only_cells,
    # list_cell_ids,
):
    child = build_child_app(static_ref=True)
    parent = build_parent_app(child)

    parent_runner, parent_ids = await run_all_cells(parent)

    child_runner = child._get_kernel_runner()
    cgl = child_runner._kernel.globals
    assert cgl["child_seen_x"] == 1
    assert cgl["child_exec_count_A"] == 1
    assert cgl["child_exec_count_B"] == 1

    # Re-run only the parent x/theme cell with updated input.
    x_theme_cell_id = parent_ids[1]
    parent_runner._kernel.globals["x_input"] = 2
    await run_only_cells(parent, [x_theme_cell_id])

    # Only referring child cell re-runs.
    assert cgl["child_seen_x"] == 2
    assert cgl["child_exec_count_A"] == 2
    assert cgl["child_exec_count_B"] == 1


@pytest.mark.asyncio
async def test_no_reactivity_with_dynamic_lookup(
    # force_notebook_mode,
    build_child_app,
    build_parent_app,
    run_all_cells,
    run_only_cells,
    # list_cell_ids,
):
    child = build_child_app(static_ref=False)  # globals().get("parent")
    parent = build_parent_app(child)

    parent_runner, parent_ids = await run_all_cells(parent)

    child_runner = child._get_kernel_runner()
    cgl = child_runner._kernel.globals
    assert cgl["child_seen_x"] == 1
    a0 = cgl["child_exec_count_A"]

    x_theme_cell_id = parent_ids[1]
    parent_runner._kernel.globals["x_input"] = 3
    await run_only_cells(parent, [x_theme_cell_id])

    assert cgl["child_seen_x"] == 1
    assert cgl["child_exec_count_A"] == a0


@pytest.mark.asyncio
async def test_multiple_exposed_names_selective_rerun(
    # force_notebook_mode,
    build_child_app,
    build_parent_app,
    run_all_cells,
    run_only_cells,
    # list_cell_ids,
):
    child = build_child_app(static_ref=True)
    parent = build_parent_app(child)

    parent_runner, parent_ids = await run_all_cells(parent)

    child_runner = child._get_kernel_runner()
    cgl = child_runner._kernel.globals
    assert cgl["child_seen_x"] == 1
    assert cgl["child_seen_theme"] == "light"

    x_theme_cell_id = parent_ids[1]
    parent_runner._kernel.globals["x_input"] = 5
    await run_only_cells(parent, [x_theme_cell_id])

    assert cgl["child_seen_x"] == 5
    assert cgl["child_seen_theme"] == "light"
