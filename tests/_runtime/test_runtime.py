# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from typing import Sequence

from marimo._messaging.errors import (
    CycleError,
    DeleteNonlocalError,
    Error,
    MultipleDefinitionError,
)
from marimo._plugins.ui._core.ids import IDProvider
from marimo._runtime.dataflow import Edge
from marimo._runtime.requests import (
    CreationRequest,
    DeleteRequest,
    ExecutionRequest,
    SetCellConfigRequest,
    SetUIElementValueRequest,
)
from marimo._runtime.runtime import Kernel
from tests.conftest import ExecReqProvider


def _check_edges(error: Error, expected_edges: Sequence[Edge]) -> None:
    assert isinstance(error, CycleError)
    assert len(error.edges) == len(expected_edges)
    for edge in expected_edges:
        assert edge in error.edges or (edge[1], edge[0]) in error.edges


# Test Basic Reactivity
def test_triangle(k: Kernel) -> None:
    # x
    # x --> y
    # x, y --> z
    k.run(
        [
            ExecutionRequest(cell_id="0", code="x = 1"),
            ExecutionRequest(cell_id="1", code="y = x + 1"),
            ExecutionRequest(cell_id="2", code="z = x + y"),
        ]
    )
    assert k.globals["x"] == 1
    assert k.globals["y"] == 2
    assert k.globals["z"] == 3

    k.run([ExecutionRequest(cell_id="0", code="x = 2")])
    assert k.globals["x"] == 2
    assert k.globals["y"] == 3
    assert k.globals["z"] == 5

    k.run([ExecutionRequest(cell_id="1", code="y = 0")])
    assert k.globals["x"] == 2
    assert k.globals["y"] == 0
    assert k.globals["z"] == 2

    k.delete(DeleteRequest(cell_id="1"))
    assert k.globals["x"] == 2
    assert "y" not in k.globals
    assert "z" not in k.globals

    k.delete(DeleteRequest(cell_id="0"))
    assert "x" not in k.globals
    assert "y" not in k.globals
    assert "z" not in k.globals


def test_set_ui_element_value(k: Kernel) -> None:
    k.run([ExecutionRequest(cell_id="0", code="import marimo as mo")])
    k.run(
        [
            ExecutionRequest(
                cell_id="1", code="s = mo.ui.slider(0, 10, value=1); s"
            )
        ]
    )
    k.run([ExecutionRequest(cell_id="2", code="x = s.value + 1")])
    assert k.globals["x"] == 2

    element_id = k.globals["s"]._id
    k.set_ui_element_value(SetUIElementValueRequest([(element_id, 5)]))
    assert k.globals["s"].value == 5
    assert k.globals["x"] == 6


def test_set_ui_element_value_not_found_doesnt_fail(k: Kernel) -> None:
    # smoke test -- this shouldn't raise an exception
    k.set_ui_element_value(
        SetUIElementValueRequest([("does not exist", None)])
    )


def test_set_ui_element_value_lensed(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test setting the value of a lensed element.

    Make sure reactivity flows through its parent, and that its on_change
    handler is called exactly once.
    """
    k.run([exec_req.get(code="import marimo as mo")])

    # Create an array and output it ...
    cell_one_code = """
    data = []
    def on_change(v):
        data.append(v)

    array = mo.ui.array([mo.ui.slider(0, 10, value=1, on_change=on_change)]);
    array
    """
    k.run([exec_req.get(code=cell_one_code)])

    # Reference the array's value
    k.run([exec_req.get(code="x = array.value[0] + 1")])
    assert k.globals["x"] == 2

    # Set a child of the array to 5 ...
    child_id = k.globals["array"][0]._id
    k.set_ui_element_value(SetUIElementValueRequest([(child_id, 5)]))

    # Make sure the array and its child are updated
    assert k.globals["array"].value == [5]
    assert k.globals["array"][0].value == 5

    # Make sure the on_change handler got called exactly once
    assert k.globals["data"] == [5]

    # Make sure setting array's child triggered execution of the second cell,
    # which references `array`
    assert k.globals["x"] == 6


def test_set_ui_element_value_lensed_bound_child(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test setting the value of a lensed element.

    Make sure reactivity flows through its parent and also to names bound
    to children.
    """
    k.run([exec_req.get(code="import marimo as mo")])

    cell_one_code = """
    array = mo.ui.array([mo.ui.slider(0, 10, value=1)])
    child = array[0]
    """
    k.run([exec_req.get(code=cell_one_code)])
    k.run([exec_req.get(code="x = child.value + 1")])

    array_id = k.globals["array"]._id
    k.set_ui_element_value(SetUIElementValueRequest([(array_id, {"0": 5})]))
    assert k.globals["array"].value == [5]
    assert k.globals["x"] == 6


def test_set_ui_element_value_lensed_with_state(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    """Test setting the value of a lensed element with on_change set_state"""
    k.run([exec_req.get(code="import marimo as mo")])

    # Create an array and output it ...
    cell_one_code = """
    get_state, set_state = mo.state(None)

    array = mo.ui.array(
        [mo.ui.slider(0, 10, value=1, on_change=set_state),
        mo.ui.slider(0, 10, value=1, on_change=set_state)
    ]);
    """
    k.run([exec_req.get(code=cell_one_code)])
    k.run([exec_req.get(code="state = get_state()")])

    # Set a child of the array and make sure its on_change handler is called
    child_id = k.globals["array"][0]._id
    k.set_ui_element_value(SetUIElementValueRequest([(child_id, 5)]))

    # Make sure the array and its child are updated
    assert k.globals["state"] == 5


def test_set_local_var_ui_element_value(k: Kernel) -> None:
    k.run([ExecutionRequest("0", "import marimo as mo")])
    k.run([ExecutionRequest("1", "_s = mo.ui.slider(0, 10, value=1); _s")])
    # _s's name is mangled to _cell_1_s because it is local
    assert k.globals["_cell_1_s"].value == 1

    element_id = k.globals["_cell_1_s"]._id
    # This shouldn't crash the kernel, and s's value should still be updated
    k.set_ui_element_value(SetUIElementValueRequest([(element_id, 5)]))
    assert k.globals["_cell_1_s"].value == 5


def test_creation_with_ui_element_value(k: Kernel) -> None:
    id_provider = IDProvider(prefix="1")
    k.instantiate(
        CreationRequest(
            execution_requests=(
                ExecutionRequest(cell_id="0", code="import marimo as mo"),
                ExecutionRequest(
                    cell_id="1", code="s = mo.ui.slider(0, 10, value=1)"
                ),
            ),
            set_ui_element_value_request=SetUIElementValueRequest(
                [(id_provider.take_id(), 2)]
            ),
        )
    )
    assert k.globals["s"].value == 2


# Test errors in marimo semantics
def test_kernel_simultaneous_multiple_definition_error(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest(cell_id="0", code="x=0"),
            ExecutionRequest(cell_id="1", code="x=1"),
        ]
    )

    assert "x" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert k.errors["0"] == (MultipleDefinitionError("x", ("1",)),)
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)


def test_kernel_new_multiple_definition_does_not_invalidate(k: Kernel) -> None:
    k.run([ExecutionRequest(cell_id="0", code="x=0")])
    assert k.globals["x"] == 0
    assert not k.errors

    # cell 0 should not be invalidated by the introduction of cell 1
    k.run([ExecutionRequest(cell_id="1", code="x=0")])
    assert k.globals["x"] == 0
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)

    # re-running cell 0 should invalidate it
    k.run([ExecutionRequest(cell_id="0", code="x=0")])
    assert "x" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert k.errors["0"] == (MultipleDefinitionError("x", ("1",)),)
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)


def test_clear_multiple_definition_error(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest(cell_id="0", code="x=0"),
            ExecutionRequest(cell_id="1", code="x=1"),
        ]
    )
    assert "x" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert k.errors["0"] == (MultipleDefinitionError("x", ("1",)),)
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)

    # Rename second occurrence of x to y; should eliminate error and run both
    # cells
    k.run([ExecutionRequest(cell_id="1", code="y=1")])
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert not k.errors


def test_clear_multiple_definition_error_with_delete(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest(cell_id="0", code="x=0"),
            ExecutionRequest(cell_id="1", code="x=1"),
        ]
    )
    assert "x" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert k.errors["0"] == (MultipleDefinitionError("x", ("1",)),)
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)

    # issue delete request for cell 1 to clear error and run cell 0
    k.delete(DeleteRequest(cell_id="1"))
    assert k.globals["x"] == 0
    assert not k.errors


def test_new_errors_update_old_ones(k: Kernel) -> None:
    k.run([ExecutionRequest(cell_id="0", code="x=0")])
    k.run([ExecutionRequest(cell_id="1", code="x, y =1, 2")])
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)

    # errors propagated back to cell 1, even though we are not running it
    k.run([ExecutionRequest(cell_id="2", code="x, y = 3, 4")])
    assert set(k.errors.keys()) == {"1", "2"}
    assert k.errors["1"] == (
        MultipleDefinitionError("x", ("0", "2")),
        MultipleDefinitionError("y", ("2",)),
    )
    assert k.errors["2"] == (
        MultipleDefinitionError("x", ("0", "1")),
        MultipleDefinitionError("y", ("1",)),
    )

    assert k.globals["x"] == 0


def test_cycle_error(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest(cell_id="0", code="x=y"),
            ExecutionRequest(cell_id="1", code="y=x"),
            ExecutionRequest(cell_id="2", code="z = x + 1"),
        ]
    )
    assert "x" not in k.globals
    assert "y" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert len(k.errors["0"]) == 1
    assert len(k.errors["1"]) == 1
    _check_edges(k.errors["0"][0], [("0", "1"), ("1", "0")])
    _check_edges(k.errors["1"][0], [("0", "1"), ("1", "0")])

    # break cycle by modifying cell
    k.run([ExecutionRequest(cell_id="1", code="y=1")])
    assert k.globals["x"] == 1
    assert k.globals["y"] == 1
    assert k.globals["z"] == 2
    assert not k.errors


def test_break_cycle_error_with_delete(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest(cell_id="0", code="x=y"),
            ExecutionRequest(cell_id="1", code="y=x"),
        ]
    )
    assert "x" not in k.globals
    assert "y" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert len(k.errors["0"]) == 1
    assert len(k.errors["1"]) == 1
    _check_edges(k.errors["0"][0], [("0", "1"), ("1", "0")])

    # break cycle by deleting cell
    k.delete(DeleteRequest(cell_id="1"))
    assert not k.errors


def test_delete_nonlocal_error(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest(cell_id="0", code="x=0"),
            ExecutionRequest(cell_id="1", code="del x; y = 1"),
            ExecutionRequest(cell_id="2", code="z = y + 1"),
        ]
    )
    assert "y" not in k.globals
    assert "z" not in k.globals
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (DeleteNonlocalError("x", ("0",)),)

    # fix cell 1, should run cell 1 and 2
    k.run([ExecutionRequest(cell_id="1", code="y=1")])
    assert k.globals["y"] == 1
    assert k.globals["z"] == 2
    assert not k.errors


def test_defs_with_no_definers_are_removed_from_cell(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest(cell_id="0", code="x=0"),
            ExecutionRequest(cell_id="1", code="del x"),
        ]
    )
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (DeleteNonlocalError("x", ("0",)),)

    # Delete the cell that defines x. There shouldn't be any more errors
    # because x no longer exists.
    k.delete(DeleteRequest(cell_id="0"))
    assert not k.errors

    # Add x back in.
    k.run([ExecutionRequest(cell_id="2", code="x=0")])
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (DeleteNonlocalError("x", ("2",)),)

    # Repair graph
    k.run([ExecutionRequest(cell_id="1", code="y = x + 1")])
    assert not k.errors
    assert k.globals["y"] == 1

    # Make sure graph is tracking x again and update propagates
    k.run([ExecutionRequest(cell_id="2", code="x = 1")])
    assert not k.errors
    assert k.globals["y"] == 2


def test_syntax_error(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest(cell_id="0", code="x=0"),
            ExecutionRequest(cell_id="1", code="x; y = 1"),
        ]
    )
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert not k.errors

    k.run([ExecutionRequest(cell_id="0", code="x=")])
    assert "x" not in k.globals
    assert "y" not in k.globals
    assert "0" not in k.graph.cells
    assert "1" in k.graph.cells

    # fix syntax error
    k.run([ExecutionRequest(cell_id="0", code="x=0")])
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert "0" in k.graph.cells
    assert "1" in k.graph.cells
    assert not k.errors


def test_disable_and_reenable_not_stale(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    k.run(
        [
            (
                er_1 := exec_req.get(
                    """
                class namespace:
                    ...
                ns = namespace()
                ns.count = 0
                """
                )
            ),
            (er_2 := exec_req.get("ns.count += 1")),
        ]
    )
    assert k.globals["ns"].count == 1
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale

    # disable and re-enable cell 2: cell 2 should not re-run because it
    # shouldn't have passed through stale status
    # disable cell 2
    k.set_cell_config(
        SetCellConfigRequest(configs={er_2.cell_id: {"disabled": True}})
    )
    assert k.globals["ns"].count == 1
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale

    # re-enable cell 2
    k.set_cell_config(
        SetCellConfigRequest(configs={er_2.cell_id: {"disabled": False}})
    )
    # cell 2 should **not** have re-run
    assert k.globals["ns"].count == 1
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale


def test_disable_and_reenable_stale(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    k.run(
        [
            (
                er_1 := exec_req.get(
                    """
                class namespace:
                    ...
                ns = namespace()
                ns.count = 0
                """
                )
            ),
            (er_2 := exec_req.get("ns.count += 1")),
        ]
    )
    assert k.globals["ns"].count == 1
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale

    # disable and re-enable cell 2, making it stale in between;
    # cell 2 should re-run on enable
    k.set_cell_config(
        SetCellConfigRequest(configs={er_2.cell_id: {"disabled": True}})
    )
    k.run(
        [
            exec_req.get_with_id(
                er_1.cell_id,
                """
                class namespace:
                    ...
                ns = namespace()
                ns.count = 10
                """,
            )
        ]
    )

    assert k.globals["ns"].count == 10
    assert not k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale

    # re-enable cell 2
    k.set_cell_config(
        SetCellConfigRequest(configs={er_2.cell_id: {"disabled": False}})
    )
    # cell 2 should have re-run
    assert k.globals["ns"].count == 11
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale


def test_disable_and_reenable_tree(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    # x
    # x --> y
    # x, y --> z
    k.run(
        [
            (er_1 := exec_req.get("x = 1")),
            (er_2 := exec_req.get("y = x + 1")),
            (er_3 := exec_req.get("z = x + y")),
            (er_4 := exec_req.get("zz = z + 1")),
            (er_5 := exec_req.get("zzz = x + 1")),
        ]
    )
    assert k.globals["x"] == 1
    assert k.globals["y"] == 2
    assert k.globals["z"] == 3
    assert k.globals["zz"] == 4
    assert k.globals["zzz"] == 2

    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert not k.graph.cells[er_4.cell_id].stale
    assert not k.graph.cells[er_5.cell_id].stale

    # disable cell 2
    k.set_cell_config(
        SetCellConfigRequest(configs={er_2.cell_id: {"disabled": True}})
    )

    k.run([ExecutionRequest(cell_id=er_1.cell_id, code="x = 2")])
    assert k.globals["x"] == 2
    assert k.globals["zzz"] == 3

    # stale cells' state is gone
    assert "y" not in k.globals
    assert "z" not in k.globals
    assert "zz" not in k.globals

    # cell 1 is not disabled
    assert not k.graph.cells[er_1.cell_id].stale
    # cell 2 stale because disabled and cannot run
    assert k.graph.cells[er_2.cell_id].stale
    # cell 3 stale because its parent (cell 2) is disabled
    assert k.graph.cells[er_3.cell_id].stale
    # cell 4 stale because cell 2 (an ancestor) is disabled
    assert k.graph.cells[er_4.cell_id].stale
    # cell 5 is not disabled
    assert not k.graph.cells[er_5.cell_id].stale

    # enable cell 2: should run stale cells as a side-effect
    k.set_cell_config(
        SetCellConfigRequest(configs={er_2.cell_id: {"disabled": False}})
    )
    assert k.globals["x"] == 2
    assert k.globals["zzz"] == 3

    # stale cells **should have** updated
    assert k.globals["y"] == 3
    assert k.globals["z"] == 5
    assert k.globals["zz"] == 6

    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale
    assert not k.graph.cells[er_3.cell_id].stale
    assert not k.graph.cells[er_4.cell_id].stale
    assert not k.graph.cells[er_5.cell_id].stale


def test_disable_consecutive(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            (er_1 := exec_req.get("x = 1")),
            (er_2 := exec_req.get("y = x + 1")),
        ]
    )
    assert k.globals["x"] == 1
    assert k.globals["y"] == 2
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale

    # disable both cells
    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": True}})
    )
    k.set_cell_config(
        SetCellConfigRequest(configs={er_2.cell_id: {"disabled": True}})
    )
    # update the code of cell 1 -- both cells stale
    k.run([exec_req.get_with_id(er_1.cell_id, "x = 2")])
    assert "x" not in k.globals
    assert "y" not in k.globals
    assert k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale

    # enable cell 1, but 2 still disabled
    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": False}})
    )
    assert k.globals["x"] == 2
    assert "y" not in k.globals
    assert not k.graph.cells[er_1.cell_id].stale
    assert k.graph.cells[er_2.cell_id].stale

    # enable cell 2
    k.set_cell_config(
        SetCellConfigRequest(configs={er_2.cell_id: {"disabled": False}})
    )
    assert k.globals["x"] == 2
    assert k.globals["y"] == 3
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_2.cell_id].stale


def test_disable_syntax_error(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            (er_1 := exec_req.get("x = 1")),
        ]
    )
    assert k.globals["x"] == 1

    # disable cell
    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": True}})
    )

    # add a syntax error
    k.run([exec_req.get_with_id(er_1.cell_id, "x 2")])
    assert "x" not in k.globals

    # repair syntax, cell should still be disabled
    k.run([exec_req.get_with_id(er_1.cell_id, "x = 2")])
    assert "x" not in k.globals
    assert k.graph.cells[er_1.cell_id].stale

    # enable: should run
    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": False}})
    )
    assert k.globals["x"] == 2
    assert not k.graph.cells[er_1.cell_id].stale


def test_disable_cycle(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            (er_1 := exec_req.get("a = b")),
            (er_2 := exec_req.get("b = a")),
        ]
    )
    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": True}})
    )
    assert k.graph.cells[er_1.cell_id].config.disabled
    assert k.graph.cells[er_2.cell_id].disabled_transitively

    k.set_cell_config(
        SetCellConfigRequest(configs={er_2.cell_id: {"disabled": True}})
    )
    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": False}})
    )
    assert k.graph.cells[er_1.cell_id].disabled_transitively
    assert k.graph.cells[er_2.cell_id].config.disabled

    # adding a new cell shouldn't toggle disabled states of either
    k.run([exec_req.get("c = 0")])
    assert k.graph.cells[er_1.cell_id].disabled_transitively
    assert k.graph.cells[er_2.cell_id].config.disabled

    # breaking the cycle should re-enable
    k.run([ExecutionRequest(cell_id=er_1.cell_id, code="a = 0")])
    assert not k.graph.cells[er_1.cell_id].disabled_transitively
    assert not k.graph.cells[er_1.cell_id].stale
    assert not k.graph.cells[er_1.cell_id].config.disabled
    assert k.graph.cells[er_2.cell_id].config.disabled


def test_disable_cycle_incremental(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    k.run([er_1 := exec_req.get("a = b")])
    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": True}})
    )
    assert k.graph.cells[er_1.cell_id].config.disabled

    k.run([er_2 := exec_req.get("b = a")])
    assert k.graph.cells[er_2.cell_id].disabled_transitively


def test_enable_cycle_incremental(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    k.run(
        [
            (er_1 := exec_req.get("a = b")),
            (er_2 := exec_req.get("b = a")),
        ]
    )
    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": True}})
    )
    assert k.graph.cells[er_1.cell_id].config.disabled
    assert k.graph.cells[er_2.cell_id].disabled_transitively

    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": False}})
    )
    assert not k.graph.cells[er_1.cell_id].config.disabled
    assert k.graph.cells[er_2.cell_id].status == "idle"


def test_set_config_before_registering_cell(
    k: Kernel, exec_req: ExecReqProvider
) -> None:
    er_1 = exec_req.get("x = 0")
    k.set_cell_config(
        SetCellConfigRequest(configs={er_1.cell_id: {"disabled": True}})
    )
    k.run([er_1])
    assert k.graph.cells[er_1.cell_id].config.disabled
    assert "x" not in k.globals


def test_interrupt(k: Kernel, exec_req: ExecReqProvider) -> None:
    er = exec_req.get(
        """
        from marimo._runtime.control_flow import MarimoInterrupt

        tries = 0
        while tries < 5:
            try:
                raise MarimoInterrupt
            except Exception:
                ...
            tries += 1
        """
    )
    k.run([er])

    # make sure the interrupt wasn't caught by the try/except
    assert k.globals["tries"] == 0


def test_file_path(k: Kernel, exec_req: ExecReqProvider) -> None:
    k.run(
        [
            exec_req.get("import marimo as mo"),
            exec_req.get("x = __file__"),
        ]
    )

    assert k.globals["x"] == "/app/test.py"
