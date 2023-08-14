# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from typing import Any, Generator, Sequence

import pytest

from marimo._messaging.errors import (
    CycleError,
    DeleteNonlocalError,
    Error,
    MultipleDefinitionError,
)
from marimo._plugins.ui._core.ids import IDProvider
from marimo._plugins.ui._core.registry import UIElementRegistry
from marimo._runtime.context import get_context
from marimo._runtime.dataflow import Edge
from marimo._runtime.requests import (
    CreationRequest,
    DeleteRequest,
    ExecutionRequest,
    SetUIElementValueRequest,
)
from marimo._runtime.runtime import Kernel


class _MockStream:
    def write(self, op: str, data: dict[Any, Any]) -> None:
        del op
        del data
        pass


# fixture that provides a kernel (and tears it down)
@pytest.fixture
def k() -> Generator[Kernel, None, None]:
    k = Kernel()
    get_context().initialize(
        kernel=k,
        ui_element_registry=UIElementRegistry(),
        stream=_MockStream(),  # type: ignore
        stdout=None,
        stderr=None,
    )
    yield k
    get_context()._kernel = None
    get_context()._ui_element_registry = None
    get_context()._stream = None
    get_context()._initialized = False


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
            ExecutionRequest("0", "x = 1"),
            ExecutionRequest("1", "y = x + 1"),
            ExecutionRequest("2", "z = x + y"),
        ]
    )
    assert k.globals["x"] == 1
    assert k.globals["y"] == 2
    assert k.globals["z"] == 3

    k.run([ExecutionRequest("0", "x = 2")])
    assert k.globals["x"] == 2
    assert k.globals["y"] == 3
    assert k.globals["z"] == 5

    k.run([ExecutionRequest("1", "y = 0")])
    assert k.globals["x"] == 2
    assert k.globals["y"] == 0
    assert k.globals["z"] == 2

    k.delete(DeleteRequest("1"))
    assert k.globals["x"] == 2
    assert "y" not in k.globals
    assert "z" not in k.globals

    k.delete(DeleteRequest("0"))
    assert "x" not in k.globals
    assert "y" not in k.globals
    assert "z" not in k.globals


def test_set_ui_element_value(k: Kernel) -> None:
    k.run([ExecutionRequest("0", "import marimo as mo")])
    k.run([ExecutionRequest("1", "s = mo.ui.slider(0, 10, value=1); s")])
    k.run([ExecutionRequest("2", "x = s.value + 1")])
    assert k.globals["x"] == 2

    element_id = k.globals["s"]._id
    k.set_ui_element_value(SetUIElementValueRequest([(element_id, 5)]))
    assert k.globals["s"].value == 5
    assert k.globals["x"] == 6


def test_creation_with_ui_element_value(k: Kernel) -> None:
    id_provider = IDProvider(prefix="1")
    k.instantiate(
        CreationRequest(
            execution_requests=(
                ExecutionRequest("0", "import marimo as mo"),
                ExecutionRequest("1", "s = mo.ui.slider(0, 10, value=1)"),
            ),
            set_ui_element_value_request=SetUIElementValueRequest(
                [(id_provider.take_id(), 2)]
            ),
        )
    )
    assert k.globals["s"].value == 2


# Test errors in marimo semantics
def test_kernel_simultaneous_multiple_definition_error(k: Kernel) -> None:
    k.run([ExecutionRequest("0", "x=0"), ExecutionRequest("1", "x=1")])

    assert "x" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert k.errors["0"] == (MultipleDefinitionError("x", ("1",)),)
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)


def test_kernel_new_multiple_definition_does_not_invalidate(k: Kernel) -> None:
    k.run([ExecutionRequest("0", "x=0")])
    assert k.globals["x"] == 0
    assert not k.errors

    # cell 0 should not be invalidated by the introduction of cell 1
    k.run([ExecutionRequest("1", "x=0")])
    assert k.globals["x"] == 0
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)

    # re-running cell 0 should invalidate it
    k.run([ExecutionRequest("0", "x=0")])
    assert "x" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert k.errors["0"] == (MultipleDefinitionError("x", ("1",)),)
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)


def test_clear_multiple_definition_error(k: Kernel) -> None:
    k.run([ExecutionRequest("0", "x=0"), ExecutionRequest("1", "x=1")])
    assert "x" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert k.errors["0"] == (MultipleDefinitionError("x", ("1",)),)
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)

    # Rename second occurrence of x to y; should eliminate error and run both
    # cells
    k.run([ExecutionRequest("1", "y=1")])
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert not k.errors


def test_clear_multiple_definition_error_with_delete(k: Kernel) -> None:
    k.run([ExecutionRequest("0", "x=0"), ExecutionRequest("1", "x=1")])
    assert "x" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert k.errors["0"] == (MultipleDefinitionError("x", ("1",)),)
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)

    # issue delete request for cell 1 to clear error and run cell 0
    k.delete(DeleteRequest("1"))
    assert k.globals["x"] == 0
    assert not k.errors


def test_new_errors_update_old_ones(k: Kernel) -> None:
    k.run([ExecutionRequest("0", "x=0")])
    k.run([ExecutionRequest("1", "x, y =1, 2")])
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (MultipleDefinitionError("x", ("0",)),)

    # errors propagated back to cell 1, even though we are not running it
    k.run([ExecutionRequest("2", "x, y = 3, 4")])
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
            ExecutionRequest("0", "x=y"),
            ExecutionRequest("1", "y=x"),
            ExecutionRequest("2", "z = x + 1"),
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
    k.run([ExecutionRequest("1", "y=1")])
    assert k.globals["x"] == 1
    assert k.globals["y"] == 1
    assert k.globals["z"] == 2
    assert not k.errors


def test_break_cycle_error_with_delete(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest("0", "x=y"),
            ExecutionRequest("1", "y=x"),
        ]
    )
    assert "x" not in k.globals
    assert "y" not in k.globals
    assert set(k.errors.keys()) == {"0", "1"}
    assert len(k.errors["0"]) == 1
    assert len(k.errors["1"]) == 1
    _check_edges(k.errors["0"][0], [("0", "1"), ("1", "0")])

    # break cycle by deleting cell
    k.delete(DeleteRequest("1"))
    assert not k.errors


def test_delete_nonlocal_error(k: Kernel) -> None:
    k.run(
        [
            ExecutionRequest("0", "x=0"),
            ExecutionRequest("1", "del x; y = 1"),
            ExecutionRequest("2", "z = y + 1"),
        ]
    )
    assert "y" not in k.globals
    assert "z" not in k.globals
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (DeleteNonlocalError("x", ("0",)),)

    # fix cell 1, should run cell 1 and 2
    k.run([ExecutionRequest("1", "y=1")])
    assert k.globals["y"] == 1
    assert k.globals["z"] == 2
    assert not k.errors


def test_defs_with_no_definers_are_removed_from_cell(k: Kernel) -> None:
    k.run([ExecutionRequest("0", "x=0"), ExecutionRequest("1", "del x")])
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (DeleteNonlocalError("x", ("0",)),)

    # Delete the cell that defines x. There shouldn't be any more errors
    # because x no longer exists.
    k.delete(DeleteRequest("0"))
    assert not k.errors

    # Add x back in.
    k.run([ExecutionRequest("2", "x=0")])
    assert set(k.errors.keys()) == {"1"}
    assert k.errors["1"] == (DeleteNonlocalError("x", ("2",)),)

    # Repair graph
    k.run([ExecutionRequest("1", "y = x + 1")])
    assert not k.errors
    assert k.globals["y"] == 1

    # Make sure graph is tracking x again and update propagates
    k.run([ExecutionRequest("2", "x = 1")])
    assert not k.errors
    assert k.globals["y"] == 2


def test_syntax_error(k: Kernel) -> None:
    k.run([ExecutionRequest("0", "x=0"), ExecutionRequest("1", "x; y = 1")])
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert not k.errors

    k.run([ExecutionRequest("0", "x=")])
    assert "x" not in k.globals
    assert "y" not in k.globals
    assert "0" not in k.graph.cells
    assert "1" in k.graph.cells

    # fix syntax error
    k.run([ExecutionRequest("0", "x=0")])
    assert k.globals["x"] == 0
    assert k.globals["y"] == 1
    assert "0" in k.graph.cells
    assert "1" in k.graph.cells
    assert not k.errors
