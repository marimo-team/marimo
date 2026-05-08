# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from functools import partial
from typing import cast

from marimo._ast import compiler
from marimo._ast.names import SETUP_CELL_NAME
from marimo._lint.validate_graph import check_for_errors
from marimo._messaging.errors import (
    CycleError,
    SetupRootError,
)
from marimo._runtime import dataflow

parse_cell = partial(compiler.compile_cell, cell_id="0")


def test_chain_shadowing_valid() -> None:
    graph = dataflow.DirectedGraph()
    graph.register_cell("0", parse_cell("x = 0"))
    graph.register_cell("1", parse_cell("x = 1"))
    errors = check_for_errors(graph)
    # Chain shadowing is now valid (implicit edge 0->1)
    assert not errors

    graph.register_cell("2", parse_cell("x = 1"))
    errors = check_for_errors(graph)
    # Three-cell chain is also valid (implicit edges 0->1->2)
    assert not errors


def test_multiple_definition_error_fork() -> None:
    graph = dataflow.DirectedGraph()
    graph.register_cell("0", parse_cell("x = 0"))
    graph.register_cell("1", parse_cell("y = x"))
    graph.register_cell("2", parse_cell("x = 1"))
    # Cell 2 has implicit edge from 0 (most recent definer of x)
    # But cell 1 is between them, creating a valid chain
    errors = check_for_errors(graph)
    assert not errors


def test_overlapping_chain_shadowing() -> None:
    graph = dataflow.DirectedGraph()
    graph.register_cell("0", parse_cell("x = 0"))
    graph.register_cell("1", parse_cell("x, y = 1, 2"))
    graph.register_cell("2", parse_cell("y, z = 3, 4"))
    errors = check_for_errors(graph)
    # Chain shadowing makes all valid:
    # x: 0 -> 1 (implicit edge)
    # y: 1 -> 2 (implicit edge)
    assert not errors


def test_underscore_variables_are_private() -> None:
    graph = dataflow.DirectedGraph()
    graph.register_cell("0", parse_cell("_x = 0"))
    graph.register_cell("1", parse_cell("_x = 1"))
    errors = check_for_errors(graph)
    assert not errors

    graph = dataflow.DirectedGraph()
    graph.register_cell("0", parse_cell("_x = 0"))
    graph.register_cell("1", parse_cell("del _x"))
    errors = check_for_errors(graph)
    assert not errors


def test_two_node_cycle() -> None:
    graph = dataflow.DirectedGraph()
    graph.register_cell("0", parse_cell("x = y"))
    graph.register_cell("1", parse_cell("y = x"))
    errors = check_for_errors(graph)
    assert set(errors.keys()) == {"0", "1"}
    # Edge ordering in returned error is not deterministic, so we list both
    # possible cycles
    expected_cycle = [
        CycleError(edges_with_vars=(("0", ("x",), "1"), ("1", ("y",), "0"))),
        CycleError(edges_with_vars=(("1", ("y",), "0"), ("0", ("x",), "1"))),
    ]
    assert len(errors["0"]) == 1
    assert len(errors["1"]) == 1
    assert errors["0"][0] in expected_cycle
    assert errors["1"][0] in expected_cycle


def test_three_node_cycle() -> None:
    graph = dataflow.DirectedGraph()
    graph.register_cell("0", parse_cell("x = y"))
    graph.register_cell("1", parse_cell("y = z"))
    graph.register_cell("2", parse_cell("z = x"))
    errors = check_for_errors(graph)
    assert set(errors.keys()) == {"0", "1", "2"}
    for t in errors.values():
        assert len(t) == 1
        assert isinstance(t[0], CycleError)
        edges_with_vars = t[0].edges_with_vars
        assert len(edges_with_vars) == 3
        assert ("0", ("x",), "2") in edges_with_vars
        assert ("1", ("y",), "0") in edges_with_vars
        assert ("2", ("z",), "1") in edges_with_vars


def test_cycle_and_chain_shadowing() -> None:
    graph = dataflow.DirectedGraph()
    graph.register_cell("0", parse_cell("x, z = y, 0"))
    graph.register_cell("1", parse_cell("y, z = x, 0"))
    errors = check_for_errors(graph)
    # z forms a valid chain (0 -> 1 via implicit edge)
    # Only the cycle remains
    assert set(errors.keys()) == {"0", "1"}
    for t in errors.values():
        assert len(t) == 1
        assert isinstance(t[0], CycleError)
        cycle_error = cast(CycleError, t[0])
        edges_with_vars = cycle_error.edges_with_vars
        assert len(edges_with_vars) == 2
        assert ("0", ("x",), "1") in edges_with_vars
        assert ("1", ("y",), "0") in edges_with_vars


def test_del_ref_cycle() -> None:
    graph = dataflow.DirectedGraph()

    graph.register_cell("0", parse_cell("x = 1"))
    graph.register_cell("1", parse_cell("del x; y = 1"))
    graph.register_cell("2", parse_cell("z = x + y"))
    errors = check_for_errors(graph)
    # Edge ordering in returned error is not deterministic, so we list both
    # possible cycles
    expected_cycle = [
        CycleError(edges_with_vars=(("2", ("x",), "1"), ("1", ("y",), "2"))),
        CycleError(edges_with_vars=(("1", ("y",), "2"), ("2", ("x",), "1"))),
    ]

    assert len(errors["1"]) == 1
    assert len(errors["2"]) == 1
    assert errors["1"][0] in expected_cycle
    assert errors["2"][0] in expected_cycle


def test_setup_has_refs() -> None:
    graph = dataflow.DirectedGraph()
    graph.register_cell(SETUP_CELL_NAME, parse_cell("z = y"))
    graph.register_cell("0", parse_cell("y = 1"))
    errors = check_for_errors(graph)
    assert set(errors.keys()) == {SETUP_CELL_NAME}
    for t in errors.values():
        assert len(t) == 1
        assert isinstance(t[0], SetupRootError)
        setup_error = cast(SetupRootError, t[0])
        edges_with_vars = setup_error.edges_with_vars
        assert len(edges_with_vars) == 1
        assert ("0", ("y",), SETUP_CELL_NAME) in edges_with_vars
