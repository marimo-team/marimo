# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import partial
from textwrap import dedent

import pytest

from marimo._ast import compiler
from marimo._ast.visitor import Name, VariableData
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime import dataflow

parse_cell = partial(compiler.compile_cell, cell_id="0")

HAS_DUCKDB = DependencyManager.duckdb.has()


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
    assert dataflow.transitive_closure(graph, cell_ids=set(["0"])) == set(
        ["0", "1"]
    )


def test_graph_closure_predicate() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "def foo():\n  return x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)
    graph.set_stale(set(["1"]))

    code = "x"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    # 0 --> 1
    assert graph.cells == {"0": first_cell, "1": second_cell, "2": third_cell}
    assert graph.parents == {"0": set(), "1": set(["0"]), "2": set(["0"])}
    assert graph.children == {"0": set(["1", "2"]), "1": set(), "2": set()}

    assert dataflow.transitive_closure(
        graph, cell_ids=set(["0"]), predicate=lambda cell: not cell.stale
    ) == set(["0", "2"])


def test_graph_closure_inclusive() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "z = y"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    # 0 --> 1 --> 2
    assert graph.cells == {"0": first_cell, "1": second_cell, "2": third_cell}
    assert graph.parents == {"0": set(), "1": set(["0"]), "2": set(["1"])}
    assert graph.children == {"0": set(["1"]), "1": set(["2"]), "2": set()}

    # Test inclusive=True (default)
    assert dataflow.transitive_closure(graph, cell_ids=set(["1"])) == set(
        ["1", "2"]
    )

    # Test inclusive=False
    assert dataflow.transitive_closure(
        graph, cell_ids=set(["1"]), inclusive=False
    ) == set(["2"])

    # Test with multiple starting cells
    assert dataflow.transitive_closure(graph, cell_ids=set(["0", "1"])) == set(
        ["0", "1", "2"]
    )

    # Test ancestors (children=False)
    assert dataflow.transitive_closure(
        graph, cell_ids=set(["2"]), children=False
    ) == set(["0", "1", "2"])

    # Test ancestors with inclusive=False
    assert dataflow.transitive_closure(
        graph, cell_ids=set(["2"]), children=False, inclusive=False
    ) == set(["0", "1"])


def test_graph_closure_predicate_with_inclusive_false() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "z = y"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    result = dataflow.transitive_closure(
        graph, cell_ids=set(["0"]), inclusive=False
    )
    assert result == set(["1", "2"])

    result = dataflow.transitive_closure(
        graph, cell_ids=set(["1"]), inclusive=False
    )
    assert result == set(["2"])

    result = dataflow.transitive_closure(
        graph, cell_ids=set(["0", "1"]), inclusive=False
    )
    assert result == set(["2"])

    result = dataflow.transitive_closure(
        graph, cell_ids=set(["0", "1", "2"]), inclusive=False
    )
    assert result == set()


def test_graph_closure_empty() -> None:
    graph = dataflow.DirectedGraph()

    # Test with empty graph
    assert dataflow.transitive_closure(graph, cell_ids=set()) == set()

    # Add a single cell with no connections
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    # Test with single cell, no connections
    assert dataflow.transitive_closure(graph, cell_ids=set(["0"])) == set(
        ["0"]
    )
    assert (
        dataflow.transitive_closure(
            graph, cell_ids=set(["0"]), inclusive=False
        )
        == set()
    )


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


def test_set_stale() -> None:
    # 0 --> 1 --> 2, 0 --> 2, 3
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

    code = "a = 0"
    fourth_cell = parse_cell(code)
    graph.register_cell("3", fourth_cell)

    # no cells are stale originally
    assert not graph.get_stale()

    # 0 and its children are stale
    graph.set_stale(set(["0"]))
    assert graph.get_stale() == set(["0", "1", "2"])

    graph.cells["0"].set_stale(stale=False)
    graph.cells["1"].set_stale(stale=False)
    graph.cells["2"].set_stale(stale=False)
    assert not graph.get_stale()


def test_ancestors() -> None:
    # 0 --> 1 --> 2, 0 --> 2, 3
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

    code = "a = 0"
    fourth_cell = parse_cell(code)
    graph.register_cell("3", fourth_cell)

    assert not graph.ancestors("0")
    assert graph.ancestors("1") == set(["0"])
    assert graph.ancestors("2") == set(["0", "1"])
    assert not graph.ancestors("3")


def test_descendants() -> None:
    # 0 --> 1 --> 2, 0 --> 2, 3
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

    code = "a = 0"
    fourth_cell = parse_cell(code)
    graph.register_cell("3", fourth_cell)

    assert graph.descendants("0") == set(["1", "2"])
    assert graph.descendants("1") == set(["2"])
    assert not graph.descendants("2")
    assert not graph.ancestors("3")


def test_register_with_stale_ancestor() -> None:
    # 0 [stale]
    # register 0 [stale] --> 1, ensure 1 is stale
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)
    graph.set_stale(set(["0"]))

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)
    assert graph.get_stale() == set(["0", "1"])

    # add a third cell not related to the others
    code = "a = 0"
    third_cell = parse_cell(code)
    graph.register_cell("3", third_cell)
    assert graph.get_stale() == set(["0", "1"])


def test_topological_sort_single_node() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    cell = parse_cell(code)
    graph.register_cell("0", cell)
    sorted_cells = dataflow.topological_sort(graph, ["0"])
    assert sorted_cells == ["0"]


def test_topological_sort_linear_chain() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "z = y"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    sorted_cells = dataflow.topological_sort(graph, ["0", "1", "2"])
    assert sorted_cells == ["0", "1", "2"]


def test_topological_sort_diamond_dependency() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "z = x"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    code = "a = y + z"
    fourth_cell = parse_cell(code)
    graph.register_cell("3", fourth_cell)

    sorted_cells = dataflow.topological_sort(graph, ["0", "1", "2", "3"])
    assert sorted_cells == ["0", "1", "2", "3"]

    sorted_cells = dataflow.topological_sort(graph, ["3", "2", "1", "0"])
    assert sorted_cells == ["0", "1", "2", "3"]

    # Subset of nodes
    sorted_cells = dataflow.topological_sort(graph, ["0"])
    assert sorted_cells == ["0"]


def test_topological_sort_with_unrelated_nodes() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "a = 0"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    sorted_cells = dataflow.topological_sort(graph, ["0", "1", "2"])
    assert sorted_cells == ["0", "1", "2"]

    sorted_cells = dataflow.topological_sort(graph, ["2", "1", "0"])
    assert sorted_cells == ["0", "1", "2"]


def test_topological_sort_with_cycle() -> None:
    graph = dataflow.DirectedGraph()
    code = "x = y"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    sorted_cells = dataflow.topological_sort(graph, ["0", "1"])
    assert sorted_cells == []


def test_topological_sort_complex() -> None:
    """Test the topological sort."""
    graph = dataflow.DirectedGraph()

    # Create a complex dependency graph
    # 0 -> 1 -> 3
    # 0 -> 2 -> 3
    # 4 (standalone)
    code = "a = 1"
    cell0 = parse_cell(code)
    graph.register_cell("0", cell0)

    code = "b = a + 1"
    cell1 = parse_cell(code)
    graph.register_cell("1", cell1)

    code = "c = a * 2"
    cell2 = parse_cell(code)
    graph.register_cell("2", cell2)

    code = "d = b + c"
    cell3 = parse_cell(code)
    graph.register_cell("3", cell3)

    code = "e = 5"
    cell4 = parse_cell(code)
    graph.register_cell("4", cell4)

    # Check the sort order
    sorted_cells = dataflow.topological_sort(graph, ["0", "1", "2", "3", "4"])

    # The order should respect dependencies
    # 0 must come before 1 and 2
    # 1 and 2 must come before 3
    # 4 can be anywhere

    # Get the indices of each cell in the sorted list
    indices = {cell: i for i, cell in enumerate(sorted_cells)}

    # Check the relative ordering
    assert indices["0"] < indices["1"]
    assert indices["0"] < indices["2"]
    assert indices["1"] < indices["3"]
    assert indices["2"] < indices["3"]

    # Check with a subset of cells
    sorted_cells = dataflow.topological_sort(graph, ["1", "3"])
    assert sorted_cells == ["1", "3"]


@pytest.mark.skipif(not HAS_DUCKDB, reason="duckdb is required")
class TestSQL:
    @pytest.mark.parametrize(
        ("code1", "code2"),
        [
            (
                'mo.sql("CREATE TABLE t1 (i INTEGER, j INTEGER)")',
                'mo.sql("SELECT * from t1")',
            ),
            (
                'duckdb.sql("CREATE TABLE t1 (i INTEGER, j INTEGER)")',
                'duckdb.sql("SELECT * from t1")',
            ),
            (
                'duckdb.sql("CREATE TABLE t1 (i INTEGER, j INTEGER)")',
                'mo.sql("SELECT * from t1")',
            ),
            (
                'duckdb.sql("CREATE TABLE t1 (i INTEGER, j INTEGER)")',
                'duckdb.execute("SELECT * from t1")',
            ),
        ],
    )
    def test_sql_chain(self, code1: str, code2: str) -> None:
        graph = dataflow.DirectedGraph()
        first_cell = parse_cell(code1)
        graph.register_cell("0", first_cell)

        assert graph.cells == {"0": first_cell}
        assert graph.parents == {"0": set()}
        assert graph.children == {"0": set()}

        second_cell = parse_cell(code2)
        graph.register_cell("1", second_cell)

        assert graph.cells == {"0": first_cell, "1": second_cell}
        assert graph.parents == {"0": set(), "1": set(["0"])}
        assert graph.children == {"0": set(["1"]), "1": set()}

    def test_sql_tree_with_declared_df(self) -> None:
        graph = dataflow.DirectedGraph()
        code = 'df = mo.sql("CREATE TABLE t1 (i INTEGER, j INTEGER)")'
        first_cell = parse_cell(code)
        graph.register_cell("0", first_cell)

        assert graph.cells == {"0": first_cell}
        assert graph.parents == {"0": set()}
        assert graph.children == {"0": set()}

        code = 'mo.sql("SELECT * from t1")'
        second_cell = parse_cell(code)
        graph.register_cell("1", second_cell)

        assert graph.cells == {"0": first_cell, "1": second_cell}
        assert graph.parents == {"0": set(), "1": set(["0"])}
        assert graph.children == {"0": set(["1"]), "1": set()}

        code = 'mo.sql("SELECT * from df")'
        third_cell = parse_cell(code)
        graph.register_cell("2", third_cell)

        assert graph.cells == {
            "0": first_cell,
            "1": second_cell,
            "2": third_cell,
        }
        assert graph.parents == {"0": set(), "1": set(["0"]), "2": set(["0"])}
        assert graph.children == {"0": set(["1", "2"]), "1": set(), "2": set()}

        code = "df"
        fourth_cell = parse_cell(code)
        graph.register_cell("3", fourth_cell)

        assert graph.cells == {
            "0": first_cell,
            "1": second_cell,
            "2": third_cell,
            "3": fourth_cell,
        }
        assert graph.parents == {
            "0": set(),
            "1": set(["0"]),
            "2": set(["0"]),
            "3": set(["0"]),
        }
        assert graph.children == {
            "0": set(["1", "2", "3"]),
            "1": set(),
            "2": set(),
            "3": set(),
        }

    @pytest.mark.xfail(reason="TODO: A bug in finding multiply defined names")
    def test_redefine_sql_table_diff_schema(self):
        graph = dataflow.DirectedGraph()
        code = "t1 = 123"
        first_cell = parse_cell(code)
        graph.register_cell("0", first_cell)

        code = 'df = mo.sql("CREATE TABLE schema1.t1 (i INTEGER, j INTEGER)")'
        second_cell = parse_cell(code)
        graph.register_cell("1", second_cell)

        assert graph.cells == {
            "0": first_cell,
            "1": second_cell,
        }

        # Because t1 is qualified with schema1, it is not considered multiply defined
        multiply_defined = graph.get_multiply_defined()
        assert multiply_defined == []

    def test_no_sql_table_to_python_ref(self):
        graph = dataflow.DirectedGraph()
        code = 'df = mo.sql("CREATE TABLE t1 (i INTEGER, j INTEGER)")'
        first_cell = parse_cell(code)
        graph.register_cell("0", first_cell)

        # not a child of first_cell because t1 is a sql table not Python
        # variable
        code = "t1"
        second_cell = parse_cell(code)
        graph.register_cell("1", second_cell)

        # is a child of first_cell because df is a Python variable
        code = "df"
        third_cell = parse_cell(code)
        graph.register_cell("2", third_cell)

        assert graph.cells == {
            "0": first_cell,
            "1": second_cell,
            "2": third_cell,
        }
        assert graph.parents == {"0": set(), "1": set([]), "2": set(["0"])}
        assert graph.children == {"0": set(["2"]), "1": set(), "2": set([])}

        assert second_cell.language == "python"
        assert graph.get_referring_cells("t1", language="sql") == set([])
        assert graph.get_referring_cells("df", language="python") == set(["2"])

    def test_python_to_sql_ref(self):
        graph = dataflow.DirectedGraph()
        code = "df = 123"
        first_cell = parse_cell(code)
        graph.register_cell("0", first_cell)

        # not a child of first_cell because t1 is a sql table not Python
        # variable
        code = "mo.sql('SELECT * from df')"
        second_cell = parse_cell(code)
        graph.register_cell("1", second_cell)

        assert graph.cells == {
            "0": first_cell,
            "1": second_cell,
        }
        assert graph.parents == {"0": set(), "1": set(["0"])}
        assert graph.children == {"0": set(["1"]), "1": set([])}

        assert graph.get_referring_cells("df", language="python") == set(["1"])

    def test_get_referring_cells_sql_and_python(self) -> None:
        """Test the get_referring_cells method."""
        graph = dataflow.DirectedGraph()

        # First cell defines x
        code = "x = 0"
        first_cell = parse_cell(code)
        graph.register_cell("0", first_cell)

        # No cells refer to x yet
        assert graph.get_referring_cells("x", language="python") == set()

        # Second cell refers to x in Python
        code = "y = x"
        second_cell = parse_cell(code)
        graph.register_cell("1", second_cell)

        # Second cell should be in the referring cells for x
        assert graph.get_referring_cells("x", language="python") == set(["1"])

        # Third cell refers to x in SQL
        code = "mo.sql('SELECT * FROM x')"
        third_cell = parse_cell(code)
        graph.register_cell("2", third_cell)

        # Both cells should be in the referring cells for x
        assert graph.get_referring_cells("x", language="python") == set(
            ["1", "2"]
        )
        assert graph.get_referring_cells("x", language="sql") == set(["2"])

        # Test language filter (Python vars can leak to SQL, but not vice versa)
        code = "mo.sql('CREATE TABLE t1 (i INTEGER)')"
        fourth_cell = parse_cell(code)
        graph.register_cell("3", fourth_cell)

        code = "mo.sql('SELECT * FROM t1')"
        fifth_cell = parse_cell(code)
        graph.register_cell("4", fifth_cell)

        code = "t1"
        sixth_cell = parse_cell(code)
        graph.register_cell("5", sixth_cell)

        # cell "5"'s t1 cannot possibly be a SQL variable
        assert graph.get_referring_cells("t1", language="sql") == set(["4"])
        # t1 could potentially be a Python variable, so it is included in the
        # reference set; even if t1 were not defined anywhere, it would still
        # return "5"
        assert graph.get_referring_cells("t1", language="python") == set(
            ["4", "5"]
        )

        # Python cell "5" is not a child of SQL cell "3", even though 5
        # refs "t1" and 3 defines SQL variable t1
        assert graph.children["3"] == {"4"}

        # Test nonexistent variable
        assert (
            graph.get_referring_cells("nonexistent", language="python")
            == set()
        )

    def test_referring_cells_sql_and_python(self) -> None:
        graph = dataflow.DirectedGraph()
        code = 'df = mo.sql("select * from my_schema.my_table")'
        first_cell = parse_cell(code)
        assert first_cell.refs == {"mo", "my_schema.my_table"}

        graph.register_cell("0", first_cell)

        # my_table should not be passed in as a reference to sql cell
        code = "df; my_table = ..."
        second_cell = parse_cell(code)
        graph.register_cell("1", second_cell)

        assert (
            graph.get_referring_cells("my_table", language="python") == set()
        )
        assert not graph.cycles

    def test_attached_db(self):
        graph = dataflow.DirectedGraph()
        code = "mo.sql(\"ATTACH 'my_db.db'\")"
        first_cell = parse_cell(code)
        graph.register_cell("0", first_cell)

        code = "mo.sql('SELECT * FROM my_db.my_table')"
        second_cell = parse_cell(code)
        graph.register_cell("1", second_cell)

        code = "my_db"
        third_cell = parse_cell(code)
        graph.register_cell("2", third_cell)

        assert graph.cells == {
            "0": first_cell,
            "1": second_cell,
            "2": third_cell,
        }
        assert graph.parents == {"0": set(), "1": set(["0"]), "2": set([])}
        assert graph.children == {"0": set(["1"]), "1": set([]), "2": set([])}

        # cell 2 shouldn't count as a referring cell because it isn't a SQL
        # cell
        assert graph.get_referring_cells("my_db", language="sql") == set(["1"])

    def test_get_referring_cells_sql_fuzzy_matching(self) -> None:
        """Test SQL fuzzy matching logic in get_referring_cells."""
        graph = dataflow.DirectedGraph()

        # Test SQL cells with schema.table references
        code = "mo.sql('SELECT * FROM my_schema.my_table')"
        first_cell = parse_cell(code)
        graph.register_cell("0", first_cell)

        # Should match both exact and partial matches
        assert graph.get_referring_cells(
            "my_schema.my_table", language="sql"
        ) == set(["0"])
        assert graph.get_referring_cells("my_schema", language="sql") == set(
            ["0"]
        )
        assert graph.get_referring_cells("my_table", language="sql") == set(
            ["0"]
        )

        # Test with multiple dots
        code = "mo.sql('SELECT * FROM catalog.schema.table')"
        second_cell = parse_cell(code)
        graph.register_cell("1", second_cell)

        assert graph.get_referring_cells(
            "catalog.schema.table", language="sql"
        ) == set(["1"])
        assert graph.get_referring_cells(
            "catalog.schema", language="sql"
        ) == set(["1"])
        assert graph.get_referring_cells(
            "schema.table", language="sql"
        ) == set(["1"])
        assert graph.get_referring_cells("catalog", language="sql") == set(
            ["1"]
        )

    def test_register_cell_language_barriers(self) -> None:
        """Test that language barriers are properly enforced in register_cell."""
        graph = dataflow.DirectedGraph()

        # Create a SQL cell that defines a table
        code = "mo.sql('CREATE TABLE sql_table (id INT)')"
        sql_def_cell = parse_cell(code)
        graph.register_cell("0", sql_def_cell)

        # Create a Python cell that references the same name
        code = "sql_table = [1, 2, 3]"
        python_ref_cell = parse_cell(code)
        graph.register_cell("1", python_ref_cell)

        # The Python cell should NOT be a child of the SQL cell
        # because SQL definitions don't create edges to Python references
        assert "1" not in graph.children["0"]
        assert "0" not in graph.parents["1"]

        # But if we create a SQL cell that references the table
        code = "mo.sql('SELECT * FROM sql_table')"
        sql_ref_cell = parse_cell(code)
        graph.register_cell("2", sql_ref_cell)

        # This should create a dependency
        assert "2" in graph.children["0"]
        assert "0" in graph.parents["2"]

        assert not graph.cycles

    def test_register_cell_with_catalog(self) -> None:
        """Test SQL cells with catalog, schema and table."""
        graph = dataflow.DirectedGraph()

        # Create a cell that defines a database
        code = "mo.sql(\"ATTACH 'catalog.db' AS catalog\")"
        catalog_cell = parse_cell(code)
        graph.register_cell("0", catalog_cell)

        # Create a cell that defines a schema
        code = "mo.sql('CREATE SCHEMA catalog.my_schema')"
        schema_cell = parse_cell(code)
        graph.register_cell("1", schema_cell)

        # Create a cell that defines a table
        code = "mo.sql('CREATE TABLE catalog.my_schema.my_table (id INT)')"
        table_cell = parse_cell(code)
        graph.register_cell("2", table_cell)

        # Create a cell that references the table
        code = "mo.sql('SELECT * FROM catalog.my_schema.my_table')"
        ref_cell = parse_cell(code)
        graph.register_cell("3", ref_cell)

        # Test that fuzzy matching creates appropriate dependencies
        # The ref cell should be a child of the table cell
        assert "3" in graph.children["2"]
        assert "2" in graph.parents["3"]

        # Test get_referring_cells with various patterns
        assert graph.get_referring_cells(
            "catalog.my_schema.my_table", language="sql"
        ) == set(["3"])
        assert graph.get_referring_cells(
            "my_schema.my_table", language="sql"
        ) == set(["3"])
        assert graph.get_referring_cells("my_table", language="sql") == set(
            ["3"]
        )

    def test_register_cell_sql_circular_dependencies(self) -> None:
        """Test that SQL circular dependencies are properly detected."""
        graph = dataflow.DirectedGraph()

        # Create a SQL cell that defines a table
        code = "mo.sql('CREATE TABLE t1 AS SELECT * FROM t2')"
        t1_cell = parse_cell(code)
        graph.register_cell("0", t1_cell)

        # Create a SQL cell that references t1
        code = "mo.sql('SELECT * FROM t1')"
        t1_ref_cell = parse_cell(code)
        graph.register_cell("1", t1_ref_cell)

        # Create a SQL cell that defines t2 and references t1
        code = "mo.sql('CREATE TABLE t2 AS SELECT * FROM t1')"
        t2_cell = parse_cell(code)
        graph.register_cell("2", t2_cell)

        # This should create a cycle: t1 -> t2 -> t1
        assert len(graph.cycles) > 0

        # Check that the cycle is properly recorded
        cycle_found = False
        for cycle in graph.cycles:
            cycle_edges = set(cycle)
            if ("0", "2") in cycle_edges and ("2", "0") in cycle_edges:
                cycle_found = True
                break
        assert cycle_found

    def test_sql_multiple_tables_same_schema(self) -> None:
        """Test SQL cells with multiple tables in the same schema."""
        graph = dataflow.DirectedGraph()

        # Create tables in the same schema
        code = "mo.sql('CREATE TABLE my_schema.users (id INT, name TEXT)')"
        users_table = parse_cell(code)
        graph.register_cell("0", users_table)

        code = "mo.sql('CREATE TABLE my_schema.orders (id INT, user_id INT)')"
        orders_table = parse_cell(code)
        graph.register_cell("1", orders_table)

        code = "mo.sql('CREATE TABLE my_schema.products (id INT, name TEXT)')"
        products_table = parse_cell(code)
        graph.register_cell("2", products_table)

        # Create a cell that selects from multiple tables in the same schema
        code = dedent("""
        mo.sql('''
            SELECT u.name, o.id as order_id, p.name as product_name
            FROM my_schema.users u
            JOIN my_schema.orders o ON u.id = o.user_id
            JOIN my_schema.products p ON o.product_id = p.id
        ''')
        """)
        multi_select = parse_cell(code)
        graph.register_cell("3", multi_select)

        # The multi-select cell should be a child of all three table cells
        assert "3" in graph.children["0"]  # users table
        assert "3" in graph.children["1"]  # orders table
        assert "3" in graph.children["2"]  # products table
        assert "0" in graph.parents["3"]
        assert "1" in graph.parents["3"]
        assert "2" in graph.parents["3"]

        # Test get_referring_cells for individual tables
        assert graph.get_referring_cells(
            "my_schema.users", language="sql"
        ) == set(["3"])
        assert graph.get_referring_cells(
            "my_schema.orders", language="sql"
        ) == set(["3"])
        assert graph.get_referring_cells(
            "my_schema.products", language="sql"
        ) == set(["3"])

        # Test get_referring_cells for schema
        schema_refs = graph.get_referring_cells("my_schema", language="sql")
        assert "3" in schema_refs

        # Test a single select
        code = "mo.sql('SELECT * FROM my_schema.users')"
        single_select = parse_cell(code)
        graph.register_cell("4", single_select)
        assert "4" in graph.children["0"]
        assert "0" in graph.parents["4"]

        # Test a single select with a different table
        code = "mo.sql('SELECT * FROM my_schema.products')"
        single_select = parse_cell(code)
        graph.register_cell("5", single_select)
        assert "5" in graph.children["2"]
        assert "2" in graph.parents["5"]

    @pytest.mark.xfail(reason="Catalogs not well supported")
    def test_sql_same_catalog_different_schemas(self) -> None:
        """Test SQL cells with same catalog but different schemas."""
        graph = dataflow.DirectedGraph()

        # Create schemas in the same catalog
        code = "mo.sql('CREATE SCHEMA my_catalog.sales_schema')"
        sales_schema = parse_cell(code)
        graph.register_cell("0", sales_schema)

        code = "mo.sql('CREATE SCHEMA my_catalog.inventory_schema')"
        inventory_schema = parse_cell(code)
        graph.register_cell("1", inventory_schema)

        code = "mo.sql('CREATE SCHEMA my_catalog.user_schema')"
        user_schema = parse_cell(code)
        graph.register_cell("2", user_schema)

        # Create tables in different schemas
        code = "mo.sql('CREATE TABLE my_catalog.sales_schema.transactions (id INT)')"
        sales_table = parse_cell(code)
        graph.register_cell("3", sales_table)

        code = (
            "mo.sql('CREATE TABLE my_catalog.inventory_schema.stock (id INT)')"
        )
        inventory_table = parse_cell(code)
        graph.register_cell("4", inventory_table)

        code = (
            "mo.sql('CREATE TABLE my_catalog.user_schema.profiles (id INT)')"
        )
        user_table = parse_cell(code)
        graph.register_cell("5", user_table)

        # Create a cell that selects from tables in different schemas
        code = dedent("""
        mo.sql('''
            SELECT t.id as transaction_id, s.quantity, p.name
            FROM my_catalog.sales_schema.transactions t
            JOIN my_catalog.inventory_schema.stock s ON t.product_id = s.product_id
            JOIN my_catalog.user_schema.profiles p ON t.user_id = p.id
        ''')
        """)
        cross_schema_select = parse_cell(code)
        graph.register_cell("6", cross_schema_select)

        # The cross-schema select should be a child of all three table cells
        assert "6" in graph.children["3"]  # sales table
        assert "6" in graph.children["4"]  # inventory table
        assert "6" in graph.children["5"]  # user table

        # Test get_referring_cells for individual schemas
        assert graph.get_referring_cells(
            "my_catalog.sales_schema", language="sql"
        ) == set(["6"])
        assert graph.get_referring_cells(
            "my_catalog.inventory_schema", language="sql"
        ) == set(["6"])
        assert graph.get_referring_cells(
            "my_catalog.user_schema", language="sql"
        ) == set(["6"])

        # Test get_referring_cells for catalog
        catalog_refs = graph.get_referring_cells("my_catalog", language="sql")
        assert "6" in catalog_refs

    def test_sql_multiple_selects_same_table(self) -> None:
        """Test multiple SQL cells selecting from the same table."""
        graph = dataflow.DirectedGraph()

        # Create a table
        code = "mo.sql('CREATE TABLE my_schema.my_table (id INT, name TEXT, value FLOAT)')"
        table_cell = parse_cell(code)
        graph.register_cell("0", table_cell)

        # Create multiple cells that select from the same table
        code = "mo.sql('SELECT id, name FROM my_table WHERE value > 100')"
        select1 = parse_cell(code)
        graph.register_cell("1", select1)

        code = "mo.sql('SELECT COUNT(*) as count FROM my_table')"
        select2 = parse_cell(code)
        graph.register_cell("2", select2)

        code = "mo.sql('SELECT AVG(value) as avg_value FROM my_table')"
        select3 = parse_cell(code)
        graph.register_cell("3", select3)

        code = "mo.sql('SELECT * FROM my_table ORDER BY id DESC LIMIT 10')"
        select4 = parse_cell(code)
        graph.register_cell("4", select4)

        # All select cells should be children of the table cell
        for i in range(1, 5):
            assert str(i) in graph.children["0"]
            assert "0" in graph.parents[str(i)]

        # Test get_referring_cells for the table
        table_refs = graph.get_referring_cells("my_table", language="sql")
        assert "1" in table_refs
        assert "2" in table_refs
        assert "3" in table_refs
        assert "4" in table_refs

    def test_sql_complex_nested_queries(self) -> None:
        """Test complex SQL with nested queries and subqueries."""
        graph = dataflow.DirectedGraph()

        # Create base tables
        code = (
            "mo.sql('CREATE TABLE customers (id INT, name TEXT, region TEXT)')"
        )
        customers_table = parse_cell(code)
        graph.register_cell("0", customers_table)

        code = "mo.sql('CREATE TABLE orders (id INT, customer_id INT, amount FLOAT)')"
        orders_table = parse_cell(code)
        graph.register_cell("1", orders_table)

        code = "mo.sql('CREATE TABLE regions (name TEXT, manager TEXT)')"
        regions_table = parse_cell(code)
        graph.register_cell("2", regions_table)

        # Create a complex query with nested subqueries
        code = dedent("""
        mo.sql('''
            SELECT
                c.name,
                c.region,
                r.manager,
                (SELECT COUNT(*) FROM orders o WHERE o.customer_id = c.id) as order_count,
                (SELECT AVG(amount) FROM orders o WHERE o.customer_id = c.id) as avg_order
            FROM customers c
            JOIN regions r ON c.region = r.name
            WHERE c.id IN (
                SELECT DISTINCT customer_id
                FROM orders
                WHERE amount > (SELECT AVG(amount) FROM orders)
            )
        ''')
        """)
        complex_query = parse_cell(code)
        graph.register_cell("3", complex_query)

        # The complex query should be a child of all three table cells
        assert "3" in graph.children["0"]  # customers
        assert "3" in graph.children["1"]  # orders
        assert "3" in graph.children["2"]  # regions

        # Test get_referring_cells for each table
        assert graph.get_referring_cells("customers", language="sql") == set(
            ["3"]
        )
        assert graph.get_referring_cells("orders", language="sql") == set(
            ["3"]
        )
        assert graph.get_referring_cells("regions", language="sql") == set(
            ["3"]
        )

    def test_sql_edge_cases_and_special_syntax(self) -> None:
        """Test SQL edge cases and special syntax patterns."""
        graph = dataflow.DirectedGraph()

        # Create tables with special characters in names
        code = "mo.sql('CREATE TABLE `special-table` (id INT)')"
        special_table = parse_cell(code)
        graph.register_cell("0", special_table)

        # Create queries with special syntax
        code = "mo.sql('SELECT * FROM `special-table`')"
        special_query = parse_cell(code)
        graph.register_cell("1", special_query)

        # Test dependencies
        assert "1" in graph.children["0"]

        # Test get_referring_cells with special characters
        assert graph.get_referring_cells(
            "special-table", language="sql"
        ) == set(["1"])

    @pytest.mark.xfail(reason="Case sensitive matching not supported")
    def test_sql_case_insensitive_matching(self) -> None:
        """Test that SQL matching is case insensitive for table names."""
        graph = dataflow.DirectedGraph()

        # Create table with mixed case
        code = "mo.sql('CREATE TABLE MyTable (id INT)')"
        table_cell = parse_cell(code)
        graph.register_cell("0", table_cell)

        # Create queries with different case variations
        code = "mo.sql('SELECT * FROM MyTable')"
        exact_case = parse_cell(code)
        graph.register_cell("1", exact_case)

        code = "mo.sql('SELECT * FROM mytable')"
        lower_case = parse_cell(code)
        graph.register_cell("2", lower_case)

        code = "mo.sql('SELECT * FROM MYTABLE')"
        upper_case = parse_cell(code)
        graph.register_cell("3", upper_case)

        # All queries should be children of the table cell
        assert "1" in graph.children["0"]
        assert "2" in graph.children["0"]
        assert "3" in graph.children["0"]

        # Test get_referring_cells with different cases
        assert graph.get_referring_cells("MyTable", language="sql") == set(
            ["1", "2", "3"]
        )
        assert graph.get_referring_cells("mytable", language="sql") == set(
            ["1", "2", "3"]
        )
        assert graph.get_referring_cells("MYTABLE", language="sql") == set(
            ["1", "2", "3"]
        )


def test_disable_enable_cell() -> None:
    """Test disabling and enabling cells."""
    graph = dataflow.DirectedGraph()

    # Create a chain of cells: 0 -> 1 -> 2
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "z = y"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    # Initially all cells should be enabled (not disabled)
    assert not graph.cells["0"].config.disabled
    assert not graph.cells["1"].config.disabled
    assert not graph.cells["2"].config.disabled

    # Disable the first cell
    graph.cells["0"].config.disabled = True
    graph.disable_cell("0")

    # The first cell should be disabled, and all descendants should be transitively disabled
    assert graph.cells["0"].config.disabled
    assert graph.cells["1"].disabled_transitively
    assert graph.cells["2"].disabled_transitively

    # Make one of them stale
    graph.cells["1"].set_stale(stale=True)

    # Re-enable the first cell
    graph.cells["0"].config.disabled = False
    cells_to_run = graph.enable_cell("0")

    # All cells should be enabled now
    assert not graph.cells["0"].config.disabled
    assert not graph.cells["1"].disabled_transitively
    assert not graph.cells["2"].disabled_transitively

    # Cells to run should include all previously disabled cells and the stale one
    assert cells_to_run == set(["1"])

    # Test disabling a middle cell
    graph.cells["1"].config.disabled = True
    graph.disable_cell("1")

    # First cell should remain enabled, second disabled, third transitively disabled
    assert not graph.cells["0"].config.disabled
    assert graph.cells["1"].config.disabled
    assert graph.cells["2"].disabled_transitively

    # Enable the middle cell
    graph.cells["1"].config.disabled = False
    # Make one of them stale
    graph.cells["2"].set_stale(stale=True)

    cells_to_run = graph.enable_cell("1")

    # All cells should be enabled again
    assert not graph.cells["0"].config.disabled
    assert not graph.cells["1"].config.disabled
    assert not graph.cells["2"].disabled_transitively

    # Only cells 1 and 2 need to be run
    assert cells_to_run == set(["1", "2"])


def test_is_disabled() -> None:
    """Test the is_disabled method."""
    graph = dataflow.DirectedGraph()

    # Create a diamond dependency: 0 -> 1 -> 3, 0 -> 2 -> 3
    code = "x = 0"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "z = x"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    code = "w = y + z"
    fourth_cell = parse_cell(code)
    graph.register_cell("3", fourth_cell)

    # No cells are disabled initially
    assert not graph.is_disabled("0")
    assert not graph.is_disabled("1")
    assert not graph.is_disabled("2")
    assert not graph.is_disabled("3")

    # Disable the first cell
    graph.cells["0"].config.disabled = True

    # All cells should be considered disabled
    assert graph.is_disabled("0")
    assert graph.is_disabled("1")
    assert graph.is_disabled("2")
    assert graph.is_disabled("3")

    # Enable the first cell, disable a middle cell
    graph.cells["0"].config.disabled = False
    graph.cells["1"].config.disabled = True

    # Cell 0 and 2 should not be disabled, but 1 and 3 should be
    assert not graph.is_disabled("0")
    assert graph.is_disabled("1")
    assert not graph.is_disabled("2")
    assert graph.is_disabled(
        "3"
    )  # Disabled because one of its dependencies (1) is disabled

    # Disable both middle cells
    graph.cells["2"].config.disabled = True

    # Now all cells except the first should be disabled
    assert not graph.is_disabled("0")
    assert graph.is_disabled("1")
    assert graph.is_disabled("2")
    assert graph.is_disabled("3")

    # Test with a cycle
    graph = dataflow.DirectedGraph()
    code = "x = y"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    # Disable one cell in the cycle
    graph.cells["0"].config.disabled = True

    # Both cells should be considered disabled
    assert graph.is_disabled("0")
    assert graph.is_disabled("1")

    # Test with a disconnected cell
    code = "z = 0"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    # The disconnected cell should not be affected by other disabled cells
    assert not graph.is_disabled("2")


def test_runner_sync() -> None:
    """Test the Runner class for synchronous execution."""
    graph = dataflow.DirectedGraph()

    # Create a chain of cells: 0 -> 1 -> 2
    code = "x = 10"
    first_cell = compiler.compile_cell(code, cell_id="0")
    graph.register_cell("0", first_cell)

    code = "y = x * 2"
    second_cell = compiler.compile_cell(code, cell_id="1")
    graph.register_cell("1", second_cell)

    code = "z = y + 5; z"
    third_cell = compiler.compile_cell(code, cell_id="2")
    graph.register_cell("2", third_cell)

    # Create a runner
    runner = dataflow.Runner(graph)

    # Run the last cell
    output, defs = runner.run_cell_sync("2", {})

    # Check output and definitions
    assert output == 25  # 10 * 2 + 5
    assert defs == {"z": 25}

    # Run the last cell with substituted values
    output, defs = runner.run_cell_sync("2", {"y": 50})

    # Check output and definitions with substituted value
    assert output == 55  # 50 + 5
    assert defs == {"z": 55}

    # Try to run with an invalid argument
    try:
        runner.run_cell_sync("2", {"invalid": 100})
        raise AssertionError("Should have raised an exception")
    except ValueError:
        pass  # Expected


def test_runner_ancestors() -> None:
    """Test that the Runner correctly identifies ancestors based on refs."""
    graph = dataflow.DirectedGraph()

    # Create cells with different refs/defs patterns
    code = "x = 10"
    first_cell = compiler.compile_cell(code, cell_id="0")
    graph.register_cell("0", first_cell)

    code = "y = 20"
    second_cell = compiler.compile_cell(code, cell_id="1")
    graph.register_cell("1", second_cell)

    code = "z = x + y"
    third_cell = compiler.compile_cell(code, cell_id="2")
    graph.register_cell("2", third_cell)

    # Create a runner
    runner = dataflow.Runner(graph)

    # Get ancestors of the third cell
    ancestors = runner._get_ancestors(graph.cells["2"], {})
    assert ancestors == set(["0", "1"])

    # When substituting y, only cell 0 should be an ancestor
    ancestors = runner._get_ancestors(graph.cells["2"], {"y": 30})
    assert ancestors == set(["0"])

    # When substituting both x and y, there should be no ancestors
    ancestors = runner._get_ancestors(graph.cells["2"], {"x": 40, "y": 30})
    assert ancestors == set()


def test_cycles() -> None:
    """Test cycle detection and handling."""
    graph = dataflow.DirectedGraph()

    # Create a cycle: 0 -> 1 -> 2 -> 0
    code = "x = z"
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = "y = x"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "z = y"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    # Check that cycles are detected
    assert len(graph.cycles) > 0

    # Find a cycle that includes all three cells
    full_cycle = None
    for cycle in graph.cycles:
        edges = set(cycle)
        if len(edges) == 3:
            full_cycle = cycle
            break

    assert full_cycle is not None

    # Check that get_cycles finds this cycle
    cycles = dataflow.get_cycles(graph, ["0", "1", "2"])
    assert len(cycles) > 0

    # Test breaking a cycle
    graph.delete_cell("0")

    # Cycles should be cleared
    assert not graph.cycles


def test_del_del_cycle():
    """Two variables that delete the same variable form a cycle."""
    graph = dataflow.DirectedGraph()

    graph.register_cell("0", parse_cell("del x"))
    graph.register_cell("1", parse_cell("del x"))
    assert len(graph.cycles) == 1
    assert set(list(graph.cycles)[0]) == set((("0", "1"), ("1", "0")))


def test_del_ref_cycle():
    """One cell deletes a variable and defines another, the other refs both."""
    graph = dataflow.DirectedGraph()

    graph.register_cell("0", parse_cell("x = 1"))
    graph.register_cell("1", parse_cell("del x; y = 1"))
    graph.register_cell("2", parse_cell("z = x + y"))
    assert len(graph.cycles) == 1
    assert set(list(graph.cycles)[0]) == set([("1", "2"), ("2", "1")])


def test_del_child_of_ref():
    """Cells that delete a variable become a child of cells that reference it."""
    graph = dataflow.DirectedGraph()

    graph.register_cell("0", parse_cell("del x"))
    graph.register_cell("1", parse_cell("x"))
    graph.register_cell("2", parse_cell("x = 1"))
    assert graph.parents["0"] == set(["1", "2"])
    assert graph.children["0"] == set()

    assert graph.parents["1"] == set(["2"])
    assert graph.children["1"] == set(["0"])

    assert graph.parents["2"] == set([])
    assert graph.children["2"] == set(["0", "1"])


def test_get_path() -> None:
    """Test the get_path method."""
    graph = dataflow.DirectedGraph()

    # Create a complex path: 0 -> 1 -> 2 -> 3
    #                         \         /
    #                          -> 4 -> 5
    code = "a = 1"
    cell0 = parse_cell(code)
    graph.register_cell("0", cell0)

    code = "b = a"
    cell1 = parse_cell(code)
    graph.register_cell("1", cell1)

    code = "c = b"
    cell2 = parse_cell(code)
    graph.register_cell("2", cell2)

    code = "d = c + f"
    cell3 = parse_cell(code)
    graph.register_cell("3", cell3)

    code = "e = a"
    cell4 = parse_cell(code)
    graph.register_cell("4", cell4)

    code = "f = e"
    cell5 = parse_cell(code)
    graph.register_cell("5", cell5)

    # Get path from 0 to 3
    path_0_to_3 = graph.get_path("0", "3")

    # Should be a valid path
    assert path_0_to_3

    # Verify it's a valid path by checking edges
    for i in range(len(path_0_to_3) - 1):
        src, dst = path_0_to_3[i][0], path_0_to_3[i][1]
        assert dst in graph.children[src]

    # Check that the path starts at 0 and ends with a node connected to 3
    assert path_0_to_3[0][0] == "0"
    assert path_0_to_3[-1][1] == "3"

    # No path should exist between unconnected nodes
    code = "g = 100"
    cell6 = parse_cell(code)
    graph.register_cell("6", cell6)

    # No path from 6 to any other node
    assert not graph.get_path("6", "0")
    assert not graph.get_path("6", "1")
    assert not graph.get_path("6", "2")
    assert not graph.get_path("6", "3")
    assert not graph.get_path("6", "4")
    assert not graph.get_path("6", "5")

    # No path from any node to 6
    assert not graph.get_path("0", "6")
    assert not graph.get_path("1", "6")
    assert not graph.get_path("2", "6")
    assert not graph.get_path("3", "6")
    assert not graph.get_path("4", "6")
    assert not graph.get_path("5", "6")

    # Path to self should be empty
    assert graph.get_path("0", "0") == []


def test_import_block_relatives() -> None:
    """Test the import_block_relatives function."""
    graph = dataflow.DirectedGraph()

    # Create an import block
    code = "import pandas as pd\nimport numpy as np"
    first_cell = parse_cell(code)
    first_cell.import_workspace.is_import_block = True
    first_cell.import_workspace.imported_defs = set(["pd", "np"])
    graph.register_cell("0", first_cell)

    # Create cells that use the imports
    code = "df = pd.DataFrame()"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    code = "arr = np.array([1, 2, 3])"
    third_cell = parse_cell(code)
    graph.register_cell("2", third_cell)

    # Create a cell that doesn't use the imports
    code = "x = 10"
    fourth_cell = parse_cell(code)
    graph.register_cell("3", fourth_cell)

    # Test the function
    children = dataflow.import_block_relatives(graph, "0", True)

    # Should include cells that use pd and np
    assert "1" in children
    assert "2" in children
    assert "3" not in children

    # Test with a non-import block
    children = dataflow.import_block_relatives(graph, "3", True)

    # Should just return normal children
    assert children == graph.children["3"]


def test_get_transitive_references() -> None:
    """Test the get_transitive_references method."""
    graph = dataflow.DirectedGraph()

    # Create a chain of cells with interdependent functions
    code = """
def func1():
    return 1

def func2():
    return func1() + 2
"""
    first_cell = compiler.compile_cell(code, cell_id="0")
    graph.register_cell("0", first_cell)

    code = """
def func3():
    return func2() + 3

result = func3()
"""
    second_cell = compiler.compile_cell(code, cell_id="1")
    graph.register_cell("1", second_cell)

    # Get transitive references from result
    refs = graph.get_transitive_references(set(["result"]))

    # Should include all functions in the chain
    assert "result" in refs
    assert "func3" in refs
    assert "func2" in refs
    assert "func1" in refs

    # Test with non-inclusive mode
    refs = graph.get_transitive_references(set(["result"]), inclusive=False)

    # Should include all except result
    assert "result" not in refs
    assert "func3" in refs
    assert "func2" in refs
    assert "func1" in refs

    # Test with predicate
    # Custom predicate that only includes functions
    def is_function(name: Name, data: VariableData) -> bool:
        del name
        return data.kind == "function"

    refs = graph.get_transitive_references(
        set(["result", "func3"]), predicate=is_function, inclusive=False
    )

    # Should include only functions
    assert refs == set(["func2", "func1"])

    # result is not a function, so it should be excluded even with inclusive=True
    assert "result" not in refs


def test_class_method_references() -> None:
    """Test transitive references with class methods."""
    graph = dataflow.DirectedGraph()

    code = """
class MyClass:
    def __init__(self):
        self.value = 1

    def method1(self):
        return self.value + helper()

def helper():
    return 42
"""
    first_cell = parse_cell(code)
    graph.register_cell("0", first_cell)

    code = """
obj = MyClass()
result = obj.method1()
"""
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    # Get transitive references from result
    refs = graph.get_transitive_references(set(["result"]))

    # Should include all related symbols
    assert "result" in refs
    assert "obj" in refs
    assert "MyClass" in refs
    assert "helper" in refs


def test_private_variables() -> None:
    """Test handling of private variables in get_transitive_references."""
    graph = dataflow.DirectedGraph()

    # Create a cell with private variables
    code = """
def public_func():
    # This creates a mangled name for _private_var
    _private_var = 10
    return _private_var + 5
"""
    cell = parse_cell(code)
    graph.register_cell("0", cell)

    code = "result = public_func()"
    second_cell = parse_cell(code)
    graph.register_cell("1", second_cell)

    # Get transitive references
    refs = graph.get_transitive_references(set(["result"]))

    # Should include public_func
    assert "public_func" in refs

    # Private variable shouldn't appear directly
    assert "_private_var" not in refs
