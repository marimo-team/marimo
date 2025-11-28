# tests/_runtime/app/test_script_mode.py
import pytest


@pytest.mark.asyncio
async def test_script_mode_is_snapshot(
    # force_script_mode,
    build_child_app,
    build_parent_app,
    run_all_cells,
    run_only_cells,
):
    child = build_child_app(static_ref=True)
    parent = build_parent_app(child)

    parent_runner, parent_ids = await run_all_cells(parent)
    pgl = parent_runner._kernel.globals

    # The embed cell copied child's defs["child_seen_x"] into parent global (once).
    assert pgl["child_seen_from_parent"] == 1

    x_theme_cell_id = parent_ids[1]
    parent_runner._kernel.globals["x_input"] = 4
    await run_only_cells(parent, [x_theme_cell_id])

    # No reactivity in script mode; captured snapshot unchanged
    assert pgl["child_seen_from_parent"] == 1
