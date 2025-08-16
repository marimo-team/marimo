# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import TYPE_CHECKING, Optional, Union

import pytest

from marimo._ast import compiler
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime import dataflow
from marimo._types.ids import CellId_t

parse_cell = partial(compiler.compile_cell, cell_id=CellId_t("0"))

HAS_DUCKDB = DependencyManager.duckdb.has()

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass
class GraphTestCase:
    """A test case for dataflow graph operations."""

    # Test description
    name: str

    # If enabled

    # Code to create and register
    code: dict[str, str]

    # Expected graph structure
    expected_parents: Optional[dict[str, Iterable[str]]] = None
    expected_children: Optional[dict[str, Iterable[str]]] = None
    expected_stale: Optional[Iterable[str]] = None

    # Expected refs/defs
    expected_refs: Optional[dict[str, Iterable[str]]] = None
    expected_defs: Optional[dict[str, Iterable[str]]] = None

    enabled: bool = True
    xfail: Union[bool, str] = False

    def __post_init__(self) -> None:
        # Convert all to a []
        if self.expected_parents is not None:
            self.expected_parents = {
                cell_id: set(parents)
                for cell_id, parents in self.expected_parents.items()
            }
        if self.expected_children is not None:
            self.expected_children = {
                cell_id: set(children)
                for cell_id, children in self.expected_children.items()
            }
        if self.expected_stale is not None:
            self.expected_stale = set(self.expected_stale)
        if self.expected_refs is not None:
            self.expected_refs = {
                cell_id: set(refs)
                for cell_id, refs in self.expected_refs.items()
            }
        if self.expected_defs is not None:
            self.expected_defs = {
                cell_id: set(defs)
                for cell_id, defs in self.expected_defs.items()
            }


PYTHON_CASES = [
    # Basic Python Cases
    GraphTestCase(
        name="single node",
        code={"0": "x = 0"},
        expected_parents={"0": []},
        expected_children={"0": []},
        expected_refs={"0": []},
        expected_defs={"0": ["x"]},
    ),
    GraphTestCase(
        name="chain",
        code={"0": "x = 0", "1": "y = x", "2": "z = y\nzz = x"},
        expected_parents={"0": [], "1": ["0"], "2": ["0", "1"]},
        expected_children={"0": ["1", "2"], "1": ["2"], "2": []},
        expected_refs={"0": [], "1": ["x"], "2": ["x", "y"]},
        expected_defs={
            "0": ["x"],
            "1": ["y"],
            "2": ["z", "zz"],
        },
    ),
    GraphTestCase(
        name="cycle",
        code={"0": "x = y", "1": "y = x"},
        expected_parents={"0": ["1"], "1": ["0"]},
        expected_children={"0": ["1"], "1": ["0"]},
        expected_refs={"0": ["y"], "1": ["x"]},
        expected_defs={"0": ["x"], "1": ["y"]},
    ),
    GraphTestCase(
        name="diamond",
        code={
            "0": "x = 0",
            "1": "y = x",
            "2": "z = y\nzz = x",
            "3": "a = z",
        },
        expected_parents={
            "0": [],
            "1": ["0"],
            "2": ["0", "1"],
            "3": ["2"],
        },
        expected_children={
            "0": ["1", "2"],
            "1": ["2"],
            "2": ["3"],
            "3": [],
        },
        expected_refs={
            "0": [],
            "1": ["x"],
            "2": ["x", "y"],
            "3": ["z"],
        },
        expected_defs={
            "0": ["x"],
            "1": ["y"],
            "2": ["z", "zz"],
            "3": ["a"],
        },
    ),
    GraphTestCase(
        name="variable del",
        code={"0": "x = 0", "1": "y = x", "2": "del x"},
        expected_parents={"0": [], "1": ["0"], "2": ["0", "1"]},
        expected_children={"0": ["1", "2"], "1": ["2"], "2": []},
        expected_refs={"0": [], "1": ["x"], "2": ["x"]},
        expected_defs={
            "0": ["x"],
            "1": ["y"],
            "2": [],
        },
    ),
]

SQL_CASES = [
    GraphTestCase(
        name="python -> sql",
        code={
            "0": "df = pd.read_csv('data.csv')",
            "1": "result = mo.sql(f'FROM df WHERE name = {name}')",
        },
        expected_parents={"0": [], "1": ["0"]},
        expected_children={"0": ["1"], "1": []},
        expected_refs={"0": ["pd"], "1": ["df", "mo", "name"]},
        expected_defs={"0": ["df"], "1": ["result"]},
    ),
    GraphTestCase(
        name="sql -> python via output",
        code={
            "0": "result = mo.sql(f'FROM my_table WHERE name = {name}')",
            "1": "df = result.head()",
        },
        expected_parents={"0": [], "1": ["0"]},
        expected_children={"0": ["1"], "1": []},
        expected_refs={"0": ["mo", "name", "my_table"], "1": ["result"]},
        expected_defs={"0": ["result"], "1": ["df"]},
    ),
    GraphTestCase(
        name="sql -/> python when creating a table",
        code={
            "0": "_ = mo.sql(f'CREATE TABLE my_table (name STRING)')",
            "1": "my_table = df.head()",
        },
        expected_parents={"0": [], "1": []},
        expected_children={"0": [], "1": []},
        expected_refs={"0": ["mo"], "1": ["df"]},
        expected_defs={"0": ["my_table"], "1": ["my_table"]},
    ),
    GraphTestCase(
        name="sql redefinition",
        code={
            "0": "df = pd.read_csv('data.csv')",
            "1": "df = mo.sql(f'FROM df')",
        },
        expected_parents={"0": [], "1": ["0"]},
        expected_children={"0": ["1"], "1": []},
        expected_refs={"0": ["pd"], "1": ["df", "mo"]},
        expected_defs={"0": ["df"], "1": ["df"]},
    ),
    GraphTestCase(
        name="python and sql not related because has schema",
        enabled=HAS_DUCKDB,
        code={
            "0": "df = pd.read_csv('data.csv')",
            "1": "result = mo.sql(f'FROM my_schema.df')",
        },
        expected_parents={"0": [], "1": []},
        expected_children={"0": [], "1": []},
        expected_refs={"0": ["pd"], "1": ["mo", "my_schema.df"]},
        # This is correct
        # expected_refs={"0": ["pd"], "1": ["df.my_schema", "mo"]},
        expected_defs={"0": ["df"], "1": ["result"]},
    ),
    GraphTestCase(
        name="sql should not reference python variables when schema",
        enabled=HAS_DUCKDB,
        code={
            "0": "my_schema = 100",
            "1": "_ = mo.sql(f'FROM my_schema.df')",
        },
        expected_parents={"0": [], "1": []},
        expected_children={"0": [], "1": []},
        expected_refs={"0": [], "1": ["mo", "my_schema.df"]},
        # This is correct
        # expected_refs={"0": ["pd"], "1": ["my_schema.df", "mo"]},
        expected_defs={"0": ["my_schema"], "1": []},
    ),
    GraphTestCase(
        name="sql should not reference python variables when catalog",
        enabled=HAS_DUCKDB,
        code={
            "0": "my_catalog = 100",
            "1": "_ = mo.sql(f'FROM my_catalog.my_schema.df')",
        },
        expected_parents={"0": [], "1": []},
        expected_children={"0": [], "1": []},
        expected_refs={"0": [], "1": ["mo", "my_catalog.my_schema.df"]},
        # This is correct
        # expected_refs={"0": ["pd"], "1": ["my_catalog.my_schema.df", "mo"]},
        expected_defs={"0": ["my_catalog"], "1": []},
    ),
    GraphTestCase(
        name="sql table reference resolves to table name even if created with schema",
        enabled=HAS_DUCKDB,
        code={
            "0": "_df = mo.sql(f'CREATE TABLE my_schema.my_table (name STRING)')",
            "1": "_df = mo.sql(f'FROM my_table SELECT *')",
        },
        expected_parents={"0": [], "1": ["0"]},
        expected_children={"0": ["1"], "1": []},
        expected_refs={"0": ["mo"], "1": ["my_table", "mo"]},
        expected_defs={"0": ["my_table"], "1": []},
    ),
    GraphTestCase(
        name="sql table reference resolves to table name even if created with catalog and schema",
        enabled=HAS_DUCKDB,
        code={
            "0": "_df = mo.sql(f'CREATE TABLE my_catalog.my_schema.my_table (name STRING)')",
            "1": "_df = mo.sql(f'FROM my_table SELECT *')",
        },
        expected_parents={"0": [], "1": ["0"]},
        expected_children={"0": ["1"], "1": []},
        expected_refs={"0": ["mo"], "1": ["my_table", "mo"]},
        expected_defs={"0": ["my_table"], "1": []},
    ),
    GraphTestCase(
        name="sql table created from another table reference",
        enabled=HAS_DUCKDB,
        code={
            "0": "_df = mo.sql(f'CREATE TABLE schema_one.my_table (name STRING)')",
            "1": "_df = mo.sql(f'CREATE TABLE schema_two.my_table_two AS SELECT * FROM schema_one.my_table')",
        },
        expected_parents={"0": [], "1": ["0"]},
        expected_children={"0": ["1"], "1": []},
        expected_refs={"0": ["mo"], "1": ["mo", "schema_one.my_table"]},
        expected_defs={"0": ["my_table"], "1": ["my_table_two"]},
    ),
    GraphTestCase(
        name="sql table reference with catalog and schema",
        enabled=HAS_DUCKDB,
        code={
            "0": "_ = mo.sql(f'CREATE TABLE my_catalog.my_schema.my_table (name STRING)')",
            "1": "_ = mo.sql(f'FROM my_catalog.my_schema.my_table SELECT *')",
        },
        expected_parents={"0": [], "1": ["0"]},
        expected_children={"0": ["1"], "1": []},
        expected_refs={
            "0": ["mo"],
            "1": ["my_catalog.my_schema.my_table", "mo"],
        },
        expected_defs={"0": ["my_table"], "1": []},
    ),
    GraphTestCase(
        name="different schemas with same table name",
        enabled=HAS_DUCKDB,
        code={
            "0": "_df = mo.sql(f'CREATE TABLE schema_one.my_table (name STRING)')",
            "1": "_df = mo.sql(f'CREATE TABLE schema_two.my_table (name STRING)')",
            "2": "_df = mo.sql(f'FROM schema_one.my_table SELECT *')",
        },
        expected_parents={"0": [], "1": [], "2": ["0"]},
        expected_children={"0": ["2"], "1": [], "2": []},
        expected_refs={
            "0": ["mo"],
            "1": ["mo"],
            "2": ["mo", "schema_one.my_table"],
        },
        # What should the defs be?
        expected_defs={
            "0": ["schema_one.my_table"],
            "1": ["schema_two.my_table"],
            "2": [],
        },
        xfail=True,
    ),
]

CASES = PYTHON_CASES + SQL_CASES


@pytest.mark.parametrize("case", CASES)
def test_cases(case: GraphTestCase) -> None:
    print(f"Running {case.name}")
    graph = dataflow.DirectedGraph()

    if not case.enabled:
        pytest.skip(f"Skipping {case.name} because it's not enabled")

    for cell_id, code in case.code.items():
        cell = parse_cell(code)
        graph.register_cell(CellId_t(cell_id), cell)

    def make_assertions():
        if case.expected_refs:
            for cell_id, refs in case.expected_refs.items():
                assert graph.cells[CellId_t(cell_id)].refs == refs, (
                    f"Cell {cell_id} has refs {graph.cells[CellId_t(cell_id)].refs}, expected {refs}"
                )
        if case.expected_defs:
            for cell_id, defs in case.expected_defs.items():
                assert graph.cells[CellId_t(cell_id)].defs == defs, (
                    f"Cell {cell_id} has defs {graph.cells[CellId_t(cell_id)].defs}, expected {defs}"
                )
        assert graph.parents == case.expected_parents, (
            f"Graph parents {graph.parents} do not match expected {case.expected_parents}"
        )
        assert graph.children == case.expected_children, (
            f"Graph children {graph.children} do not match expected {case.expected_children}"
        )

    if case.xfail:
        if isinstance(case.xfail, str):
            print(case.xfail)
        with pytest.raises(AssertionError):
            make_assertions()
    else:
        make_assertions()
