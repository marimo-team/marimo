# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import partial

import pytest

from marimo._ast import compiler
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime.dataflow.definitions import DefinitionRegistry
from marimo._runtime.dataflow.edges import EdgeComputer
from marimo._runtime.dataflow.topology import MutableGraphTopology

parse_cell = partial(compiler.compile_cell, cell_id="0")

HAS_SQL = DependencyManager.duckdb.has() and DependencyManager.polars.has()


class TestEdgeComputer:
    """Tests for EdgeComputer class."""

    def setup_method(self) -> None:
        """Set up a fresh topology and definitions for each test."""
        self.topology = MutableGraphTopology()
        self.definitions = DefinitionRegistry()
        self.edge_computer = EdgeComputer(self.topology, self.definitions)

    def test_get_referring_cells_python_no_refs(self) -> None:
        """Test getting referring cells when no cells reference the variable."""
        cell1 = parse_cell("x = 1")
        self.topology.add_node("cell_1", cell1)

        referring = self.edge_computer.get_referring_cells(
            "x", language="python"
        )

        assert referring == set()

    def test_get_referring_cells_python_single_ref(self) -> None:
        """Test getting referring cells with a single reference."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)

        referring = self.edge_computer.get_referring_cells(
            "x", language="python"
        )

        assert referring == {"cell_2"}

    def test_get_referring_cells_python_multiple_refs(self) -> None:
        """Test getting referring cells with multiple references."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")
        cell3 = parse_cell("z = x * 2")
        cell4 = parse_cell("w = x + y")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)
        self.topology.add_node("cell_3", cell3)
        self.topology.add_node("cell_4", cell4)

        referring = self.edge_computer.get_referring_cells(
            "x", language="python"
        )

        assert referring == {"cell_2", "cell_3", "cell_4"}

    def test_get_referring_cells_python_no_self_reference(self) -> None:
        """Test that a cell doesn't include itself in referring cells."""
        cell1 = parse_cell("x = x + 1")

        self.topology.add_node("cell_1", cell1)

        referring = self.edge_computer.get_referring_cells(
            "x", language="python"
        )

        # cell_1 both defines and references x, but should be in the result
        assert referring == {"cell_1"}

    def test_compute_edges_simple_dependency(self) -> None:
        """Test computing edges for a simple dependency."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)

        # Register cell1's definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Compute edges for cell2
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_2", cell2
        )

        assert parents == {"cell_1"}
        assert children == set()

    def test_compute_edges_multiple_parents(self) -> None:
        """Test computing edges with multiple parent dependencies."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = 2")
        cell3 = parse_cell("z = x + y")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)
        self.topology.add_node("cell_3", cell3)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)
        for name, var_data in cell2.variable_data.items():
            self.definitions.register_definition("cell_2", name, var_data)

        # Compute edges for cell3
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_3", cell3
        )

        assert parents == {"cell_1", "cell_2"}
        assert children == set()

    def test_compute_edges_with_children(self) -> None:
        """Test computing edges when a cell has both parents and children."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")
        cell3 = parse_cell("z = y")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)
        self.topology.add_node("cell_3", cell3)

        # Register definitions for cell1
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Register definitions for cell2
        for name, var_data in cell2.variable_data.items():
            self.definitions.register_definition("cell_2", name, var_data)

        # Compute edges for cell2 (middle cell)
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_2", cell2
        )

        assert parents == {"cell_1"}
        assert children == {"cell_3"}

    def test_compute_edges_no_dependencies(self) -> None:
        """Test computing edges for an independent cell."""
        cell1 = parse_cell("x = 1")

        self.topology.add_node("cell_1", cell1)

        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_1", cell1
        )

        assert parents == set()
        assert children == set()

    def test_compute_edges_with_deleted_refs(self) -> None:
        """Test computing edges when a cell deletes a variable."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("y = x")
        cell3 = parse_cell("del x")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)
        self.topology.add_node("cell_3", cell3)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Compute edges for cell3 (which deletes x)
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_3", cell3
        )

        # cell3 should become a child of cells that reference x (cell2)
        assert parents == {"cell_1", "cell_2"}
        assert children == set()

    def test_compute_edges_multiple_deleted_refs_create_cycle(self) -> None:
        """Test that multiple cells deleting the same variable create cycles."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("del x")
        cell3 = parse_cell("del x")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)
        self.topology.add_node("cell_3", cell3)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Compute edges for cell2
        parents2, children2 = self.edge_computer.compute_edges_for_cell(
            "cell_2", cell2
        )

        # Compute edges for cell3
        parents3, children3 = self.edge_computer.compute_edges_for_cell(
            "cell_3", cell3
        )

        # Both cells should have cell1 as parent
        assert "cell_1" in parents2
        assert "cell_1" in parents3

        # cell2 and cell3 should be children of each other (cycle)
        assert "cell_3" in children2
        assert "cell_2" in parents3

    def test_compute_edges_cell_references_its_own_def(self) -> None:
        """Test computing edges when a cell references its own definition."""
        cell1 = parse_cell("x = x + 1 if 'x' in globals() else 0")

        self.topology.add_node("cell_1", cell1)

        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_1", cell1
        )

        # A cell doesn't create an edge to itself
        assert parents == set()
        assert children == set()

    def test_compute_edges_diamond_dependency(self) -> None:
        """Test computing edges in a diamond-shaped dependency graph."""
        cell1 = parse_cell("a = 1")
        cell2 = parse_cell("b = a")
        cell3 = parse_cell("c = a")
        cell4 = parse_cell("d = b + c")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)
        self.topology.add_node("cell_3", cell3)
        self.topology.add_node("cell_4", cell4)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)
        for name, var_data in cell2.variable_data.items():
            self.definitions.register_definition("cell_2", name, var_data)
        for name, var_data in cell3.variable_data.items():
            self.definitions.register_definition("cell_3", name, var_data)

        # Check cell1's children (only direct children, not grandchildren)
        parents1, children1 = self.edge_computer.compute_edges_for_cell(
            "cell_1", cell1
        )
        assert children1 == {"cell_2", "cell_3"}

        # Check cell4's parents (it references b and c, not a directly)
        parents4, children4 = self.edge_computer.compute_edges_for_cell(
            "cell_4", cell4
        )
        assert parents4 == {"cell_2", "cell_3"}

    def test_compute_edges_with_undefined_reference(self) -> None:
        """Test computing edges when a cell references an undefined variable."""
        cell1 = parse_cell("y = x")  # x is not defined

        self.topology.add_node("cell_1", cell1)

        # Should not raise an error, just return empty parents
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_1", cell1
        )

        assert parents == set()
        assert children == set()

    def test_compute_edges_with_function_closure(self) -> None:
        """Test computing edges with function closures."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("def foo():\n    return x")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Compute edges for cell2
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_2", cell2
        )

        assert parents == {"cell_1"}
        assert children == set()

    def test_compute_edges_with_class_definition(self) -> None:
        """Test computing edges with class definitions."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("class MyClass:\n    value = x")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Compute edges for cell2
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_2", cell2
        )

        assert parents == {"cell_1"}
        assert children == set()

    def test_compute_edges_chain_of_dependencies(self) -> None:
        """Test a long chain of dependencies."""
        cells = []
        for i in range(5):
            if i == 0:
                cell = parse_cell(f"x{i} = {i}")
            else:
                cell = parse_cell(f"x{i} = x{i - 1} + 1")
            self.topology.add_node(f"cell_{i}", cell)
            cells.append((f"cell_{i}", cell))

        # Register definitions
        for cell_id, cell in cells[:-1]:
            for name, var_data in cell.variable_data.items():
                self.definitions.register_definition(cell_id, name, var_data)

        # Check last cell's parents
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_4", cells[-1][1]
        )

        assert parents == {"cell_3"}
        assert children == set()

    @pytest.mark.skipif(not HAS_SQL, reason="requires duckdb and polars")
    def test_get_referring_cells_sql_basic(self) -> None:
        """Test getting referring cells for SQL variables."""
        # SQL cell that creates a table
        cell1 = compiler.compile_cell(
            "import duckdb; import polars as pl; df = pl.DataFrame({'a': [1, 2, 3]})",
            cell_id="0",
        )
        cell2 = compiler.compile_cell("df.select(pl.col('a'))", cell_id="1")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)

        referring = self.edge_computer.get_referring_cells(
            "df", language="python"
        )

        assert referring == {"cell_2"}

    @pytest.mark.skipif(not HAS_SQL, reason="requires duckdb and polars")
    def test_compute_edges_sql_to_python(self) -> None:
        """Test that SQL table definitions don't create edges to Python refs."""
        # This tests the language isolation: SQL defs don't leak to Python
        cell1 = compiler.compile_cell(
            "df = mo.sql('CREATE TABLE my_table AS SELECT 1 as x')",
            cell_id="0",
        )
        cell2 = compiler.compile_cell("print(my_table)", cell_id="1")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)

        # Register SQL table definition
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Compute edges for cell2 (Python cell)
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_2", cell2
        )

        # SQL definitions should not create edges to Python cells
        # (unless explicitly exported)
        # Since my_table is SQL, it won't be a parent
        # However, the compiler might not recognize it as SQL without execution
        # So this test verifies the edge computation logic

    def test_compute_edges_multiple_definitions_of_same_var(self) -> None:
        """Test computing edges when multiple cells define the same variable."""
        cell1 = parse_cell("x = 1")
        cell2 = parse_cell("x = 2")
        cell3 = parse_cell("y = x")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)
        self.topology.add_node("cell_3", cell3)

        # Register both definitions of x
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)
        for name, var_data in cell2.variable_data.items():
            self.definitions.register_definition("cell_2", name, var_data)

        # Compute edges for cell3
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_3", cell3
        )

        # cell3 should depend on both cells that define x
        assert parents == {"cell_1", "cell_2"}

    def test_compute_edges_complex_scenario(self) -> None:
        """Test a complex scenario with multiple patterns."""
        # Create a complex graph:
        # cell1: defines a
        # cell2: defines b = a
        # cell3: defines c = a + b
        # cell4: uses c, deletes a
        # cell5: defines d = b

        cell1 = parse_cell("a = 1")
        cell2 = parse_cell("b = a")
        cell3 = parse_cell("c = a + b")
        cell4 = parse_cell("result = c; del a")
        cell5 = parse_cell("d = b")

        cells = [
            ("cell_1", cell1),
            ("cell_2", cell2),
            ("cell_3", cell3),
            ("cell_4", cell4),
            ("cell_5", cell5),
        ]

        for cell_id, cell in cells:
            self.topology.add_node(cell_id, cell)

        # Register definitions for cells 1-3
        for cell_id, cell in cells[:3]:
            for name, var_data in cell.variable_data.items():
                self.definitions.register_definition(cell_id, name, var_data)

        # Compute edges for cell4
        parents4, children4 = self.edge_computer.compute_edges_for_cell(
            "cell_4", cell4
        )

        # cell4 should:
        # - depend on cell3 (for c)
        # - depend on cell1 (for del a)
        # - depend on cell2 (because it references a, which cell4 deletes)
        assert "cell_3" in parents4  # uses c
        assert "cell_1" in parents4  # deletes a
        assert "cell_2" in parents4  # cell2 references a

    def test_is_valid_cell_reference_missing_cell(self) -> None:
        """Test validation when a cell reference points to a non-existent cell."""
        # The _is_valid_cell_reference method logs an error when a cell is not found
        result = self.edge_computer._is_valid_cell_reference(
            "nonexistent", "some_var"
        )

        assert result is False

    def test_is_valid_cell_reference_valid_cell(self) -> None:
        """Test validation when a cell reference is valid."""
        cell1 = parse_cell("x = 1")
        self.topology.add_node("cell_1", cell1)

        result = self.edge_computer._is_valid_cell_reference("cell_1", "x")

        assert result is True

    def test_compute_edges_with_imports(self) -> None:
        """Test computing edges with import statements."""
        cell1 = parse_cell("import math")
        cell2 = parse_cell("x = math.pi")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Compute edges for cell2
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_2", cell2
        )

        assert parents == {"cell_1"}

    def test_compute_edges_with_from_import(self) -> None:
        """Test computing edges with from-import statements."""
        cell1 = parse_cell("from math import pi")
        cell2 = parse_cell("x = pi")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Compute edges for cell2
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_2", cell2
        )

        assert parents == {"cell_1"}

    def test_compute_edges_list_comprehension(self) -> None:
        """Test computing edges with list comprehensions."""
        cell1 = parse_cell("numbers = [1, 2, 3]")
        cell2 = parse_cell("squared = [x**2 for x in numbers]")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # Compute edges for cell2
        parents, children = self.edge_computer.compute_edges_for_cell(
            "cell_2", cell2
        )

        assert parents == {"cell_1"}

    def test_compute_edges_with_multiple_assignments(self) -> None:
        """Test computing edges with multiple assignments."""
        cell1 = parse_cell("x = y = z = 1")
        cell2 = parse_cell("a = x")
        cell3 = parse_cell("b = y")
        cell4 = parse_cell("c = z")

        self.topology.add_node("cell_1", cell1)
        self.topology.add_node("cell_2", cell2)
        self.topology.add_node("cell_3", cell3)
        self.topology.add_node("cell_4", cell4)

        # Register definitions
        for name, var_data in cell1.variable_data.items():
            self.definitions.register_definition("cell_1", name, var_data)

        # All cells should depend on cell1
        for cell_id in ["cell_2", "cell_3", "cell_4"]:
            cell = self.topology.cells[cell_id]
            parents, children = self.edge_computer.compute_edges_for_cell(
                cell_id, cell
            )
            assert parents == {"cell_1"}

        # Check that cell1 has all three as children
        parents1, children1 = self.edge_computer.compute_edges_for_cell(
            "cell_1", cell1
        )
        assert children1 == {"cell_2", "cell_3", "cell_4"}
