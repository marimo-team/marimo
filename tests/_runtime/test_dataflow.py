# Copyright 2023 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell import parse_cell
from marimo._runtime import dataflow


def test_graph_single_node() -> None:
    code = "x = 0"
    graph = dataflow.DirectedGraph()
    cell = parse_cell(code)
    graph.register_cell("0", cell)
    assert graph.cells == {"0": cell}
    assert graph.parents == {"0": set()}
    assert graph.children == {"0": set()}


def test_graph_two_chains() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "z = y\nzz = x"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    # 0 --> 1 --> 2, 0 --> 2
    assert graph.cells == {"0": first_cell, "1": second_cell, "2": third_cell}
    assert graph.parents == {"0": set(), "1": set(["0"]), "2": set(["0", "1"])}
    assert graph.children == {
        "0": set(["1", "2"]),
        "1": set(["2"]),
        "2": set(),
    }


def test_graph_unconnected() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = 0"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    # 0, 1
    assert graph.cells == {"0": first_cell, "1": second_cell}
    assert graph.parents == {"0": set(), "1": set()}
    assert graph.children == {"0": set(), "1": set()}


def test_graph_closure() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "def foo():\n  return x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    # 0 --> 1
    assert graph.cells == {"0": first_cell, "1": second_cell}
    assert graph.parents == {"0": set(), "1": set(["0"])}
    assert graph.children == {"0": set(["1"]), "1": set()}


def test_graph_redefine() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "def foo():\n  x = 0\n  return x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    # 0, 1
    assert graph.cells == {"0": first_cell, "1": second_cell}
    assert graph.parents == {"0": set(), "1": set()}
    assert graph.children == {"0": set(), "1": set()}
