# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import partial

import pytest

from marimo._ast import compiler
from marimo._runtime.dataflow.topology import MutableGraphTopology
from marimo._types.ids import CellId_t

parse_cell = partial(compiler.compile_cell, cell_id=CellId_t("0"))


class TestMutableGraphTopology:
    """Tests for MutableGraphTopology class."""

    def test_empty_graph(self) -> None:
        """Test that an empty graph has no cells, parents, or children."""
        graph = MutableGraphTopology()
        assert len(graph.cells) == 0
        assert len(graph.children) == 0
        assert len(graph.parents) == 0

    def test_add_single_node(self) -> None:
        """Test adding a single node to the graph."""
        graph = MutableGraphTopology()
        cell = parse_cell("x = 1")

        graph.add_node("cell_1", cell)

        assert "cell_1" in graph.cells
        assert graph.cells["cell_1"] == cell
        assert graph.children["cell_1"] == set()
        assert graph.parents["cell_1"] == set()

    def test_add_duplicate_node_raises_error(self) -> None:
        """Test that adding a duplicate node raises an assertion error."""
        graph = MutableGraphTopology()
        cell = parse_cell("x = 1")

        graph.add_node("cell_1", cell)

        with pytest.raises(
            AssertionError, match="Cell cell_1 already in graph"
        ):
            graph.add_node("cell_1", cell)

    def test_add_multiple_nodes(self) -> None:
        """Test adding multiple nodes to the graph."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = 2")
        cell3 = parse_cell("z = 3")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_node("cell_3", cell3)

        assert len(graph.cells) == 3
        assert "cell_1" in graph.cells
        assert "cell_2" in graph.cells
        assert "cell_3" in graph.cells

    def test_remove_node(self) -> None:
        """Test removing a node from the graph."""
        graph = MutableGraphTopology()
        cell = parse_cell("x = 1")

        graph.add_node("cell_1", cell)
        graph.remove_node("cell_1")

        assert "cell_1" not in graph.cells
        assert "cell_1" not in graph.children
        assert "cell_1" not in graph.parents

    def test_remove_nonexistent_node_raises_error(self) -> None:
        """Test that removing a non-existent node raises ValueError."""
        graph = MutableGraphTopology()

        with pytest.raises(ValueError, match="Cell cell_1 not found"):
            graph.remove_node("cell_1")

    def test_remove_node_with_edges(self) -> None:
        """Test that removing a node also removes its edges."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")
        cell3 = parse_cell("z = y")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_node("cell_3", cell3)
        graph.add_edge("cell_1", "cell_2")
        graph.add_edge("cell_2", "cell_3")

        # Remove middle node
        graph.remove_node("cell_2")

        # Check that cell_2 is removed from children and parents
        assert "cell_2" not in graph.cells
        assert "cell_2" not in graph.children["cell_1"]
        assert "cell_2" not in graph.parents["cell_3"]

    def test_add_edge(self) -> None:
        """Test adding an edge between two nodes."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_edge("cell_1", "cell_2")

        assert "cell_2" in graph.children["cell_1"]
        assert "cell_1" in graph.parents["cell_2"]

    def test_add_multiple_edges(self) -> None:
        """Test adding multiple edges in the graph."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")
        cell3 = parse_cell("z = x + y")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_node("cell_3", cell3)
        graph.add_edge("cell_1", "cell_2")
        graph.add_edge("cell_1", "cell_3")
        graph.add_edge("cell_2", "cell_3")

        # cell_1 has two children
        assert graph.children["cell_1"] == {"cell_2", "cell_3"}
        # cell_2 has one child
        assert graph.children["cell_2"] == {"cell_3"}
        # cell_3 has two parents
        assert graph.parents["cell_3"] == {"cell_1", "cell_2"}

    def test_remove_edge(self) -> None:
        """Test removing an edge between two nodes."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_edge("cell_1", "cell_2")
        graph.remove_edge("cell_1", "cell_2")

        assert "cell_2" not in graph.children["cell_1"]
        assert "cell_1" not in graph.parents["cell_2"]

    def test_remove_nonexistent_edge(self) -> None:
        """Test that removing a non-existent edge doesn't raise error."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = 2")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)

        # Should not raise an error (using discard)
        graph.remove_edge("cell_1", "cell_2")

        assert "cell_2" not in graph.children["cell_1"]
        assert "cell_1" not in graph.parents["cell_2"]

    def test_get_path_direct_edge(self) -> None:
        """Test getting a path between two directly connected nodes."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_edge("cell_1", "cell_2")

        path = graph.get_path("cell_1", "cell_2")

        assert path == [("cell_1", "cell_2")]

    def test_get_path_indirect(self) -> None:
        """Test getting a path through intermediate nodes."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")
        cell3 = parse_cell("z = y")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_node("cell_3", cell3)
        graph.add_edge("cell_1", "cell_2")
        graph.add_edge("cell_2", "cell_3")

        path = graph.get_path("cell_1", "cell_3")

        assert path == [("cell_1", "cell_2"), ("cell_2", "cell_3")]

    def test_get_path_no_path(self) -> None:
        """Test getting a path when no path exists."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = 2")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)

        path = graph.get_path("cell_1", "cell_2")

        assert path == []

    def test_get_path_same_node(self) -> None:
        """Test getting a path from a node to itself."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")

        graph.add_node("cell_1", cell1)

        path = graph.get_path("cell_1", "cell_1")

        assert path == []

    def test_get_path_complex_graph(self) -> None:
        """Test getting a path in a more complex graph with multiple paths."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("a = 1")
        cell2 = parse_cell("b = a")
        cell3 = parse_cell("c = a")
        cell4 = parse_cell("d = b + c")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_node("cell_3", cell3)
        graph.add_node("cell_4", cell4)
        graph.add_edge("cell_1", "cell_2")
        graph.add_edge("cell_1", "cell_3")
        graph.add_edge("cell_2", "cell_4")
        graph.add_edge("cell_3", "cell_4")

        # BFS should find one of the shortest paths
        path = graph.get_path("cell_1", "cell_4")

        # Should be length 2 (one of: cell_1->cell_2->cell_4 or cell_1->cell_3->cell_4)
        assert len(path) == 2
        assert path[0][0] == "cell_1"
        assert path[1][1] == "cell_4"

    def test_ancestors_empty(self) -> None:
        """Test ancestors of a node with no parents."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")

        graph.add_node("cell_1", cell1)

        ancestors = graph.ancestors("cell_1")

        assert ancestors == set()

    def test_ancestors_single_parent(self) -> None:
        """Test ancestors with a single parent."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_edge("cell_1", "cell_2")

        ancestors = graph.ancestors("cell_2")

        assert ancestors == {"cell_1"}

    def test_ancestors_multiple_generations(self) -> None:
        """Test ancestors across multiple generations."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")
        cell3 = parse_cell("z = y")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_node("cell_3", cell3)
        graph.add_edge("cell_1", "cell_2")
        graph.add_edge("cell_2", "cell_3")

        ancestors = graph.ancestors("cell_3")

        assert ancestors == {"cell_1", "cell_2"}

    def test_ancestors_diamond_shape(self) -> None:
        """Test ancestors in a diamond-shaped graph."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("a = 1")
        cell2 = parse_cell("b = a")
        cell3 = parse_cell("c = a")
        cell4 = parse_cell("d = b + c")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_node("cell_3", cell3)
        graph.add_node("cell_4", cell4)
        graph.add_edge("cell_1", "cell_2")
        graph.add_edge("cell_1", "cell_3")
        graph.add_edge("cell_2", "cell_4")
        graph.add_edge("cell_3", "cell_4")

        ancestors = graph.ancestors("cell_4")

        assert ancestors == {"cell_1", "cell_2", "cell_3"}

    def test_descendants_empty(self) -> None:
        """Test descendants of a node with no children."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")

        graph.add_node("cell_1", cell1)

        descendants = graph.descendants("cell_1")

        assert descendants == set()

    def test_descendants_single_child(self) -> None:
        """Test descendants with a single child."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_edge("cell_1", "cell_2")

        descendants = graph.descendants("cell_1")

        assert descendants == {"cell_2"}

    def test_descendants_multiple_generations(self) -> None:
        """Test descendants across multiple generations."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")
        cell3 = parse_cell("z = y")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_node("cell_3", cell3)
        graph.add_edge("cell_1", "cell_2")
        graph.add_edge("cell_2", "cell_3")

        descendants = graph.descendants("cell_1")

        assert descendants == {"cell_2", "cell_3"}

    def test_descendants_diamond_shape(self) -> None:
        """Test descendants in a diamond-shaped graph."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("a = 1")
        cell2 = parse_cell("b = a")
        cell3 = parse_cell("c = a")
        cell4 = parse_cell("d = b + c")

        graph.add_node("cell_1", cell1)
        graph.add_node("cell_2", cell2)
        graph.add_node("cell_3", cell3)
        graph.add_node("cell_4", cell4)
        graph.add_edge("cell_1", "cell_2")
        graph.add_edge("cell_1", "cell_3")
        graph.add_edge("cell_2", "cell_4")
        graph.add_edge("cell_3", "cell_4")

        descendants = graph.descendants("cell_1")

        assert descendants == {"cell_2", "cell_3", "cell_4"}

    def test_properties_are_readonly(self) -> None:
        """Test that the properties return Mapping (read-only) types."""
        graph = MutableGraphTopology()
        cell1 = parse_cell("x = 1")

        graph.add_node("cell_1", cell1)

        # The properties should return Mapping types
        from collections.abc import Mapping

        assert isinstance(graph.cells, Mapping)
        assert isinstance(graph.children, Mapping)
        assert isinstance(graph.parents, Mapping)

    def test_complex_graph_operations(self) -> None:
        """Test a complex sequence of operations on the graph."""
        graph = MutableGraphTopology()

        # Build a graph: 1 -> 2 -> 3 -> 4
        #                     \-> 5 -> 6
        cells = {f"cell_{i}": parse_cell(f"x{i} = {i}") for i in range(1, 7)}

        for cell_id, cell in cells.items():
            graph.add_node(cell_id, cell)

        graph.add_edge("cell_1", "cell_2")
        graph.add_edge("cell_2", "cell_3")
        graph.add_edge("cell_3", "cell_4")
        graph.add_edge("cell_2", "cell_5")
        graph.add_edge("cell_5", "cell_6")

        # Test various operations
        assert graph.descendants("cell_1") == {
            "cell_2",
            "cell_3",
            "cell_4",
            "cell_5",
            "cell_6",
        }
        assert graph.descendants("cell_2") == {
            "cell_3",
            "cell_4",
            "cell_5",
            "cell_6",
        }
        assert graph.ancestors("cell_4") == {"cell_1", "cell_2", "cell_3"}
        assert graph.ancestors("cell_6") == {"cell_1", "cell_2", "cell_5"}

        # Remove an edge and test again
        graph.remove_edge("cell_2", "cell_5")
        assert graph.descendants("cell_2") == {"cell_3", "cell_4"}

        # Remove a node and test
        graph.remove_node("cell_3")
        assert graph.descendants("cell_1") == {"cell_2"}
        assert "cell_3" not in graph.cells
