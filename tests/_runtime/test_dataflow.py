# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from functools import partial

import pytest

from marimo._ast import compiler
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
