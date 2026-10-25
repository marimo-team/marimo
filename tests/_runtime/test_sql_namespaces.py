# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from itertools import permutations
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from marimo._ast import compiler
from marimo._dependencies.dependencies import DependencyManager
from marimo._runtime import dataflow
from marimo._runtime.dataflow import edges
from marimo._runtime.dataflow.definitions import DefinitionRegistry
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Sequence

    from marimo._ast.cell import CellImpl

pytestmark = pytest.mark.skipif(
    not DependencyManager.duckdb.has() or not DependencyManager.sqlglot.has(),
    reason="SQL dependencies required",
)


def _compile_sql(cell_id: str, sql: str) -> CellImpl:
    return compiler.compile_cell(f"mo.sql({sql!r})", cell_id=CellId_t(cell_id))


def _sql_graph(
    sources: dict[str, str], order: Sequence[str]
) -> dataflow.DirectedGraph:
    graph = dataflow.DirectedGraph()
    for cell_id in order:
        graph.register_cell(
            CellId_t(cell_id), _compile_sql(cell_id, sources[cell_id])
        )
    return graph


@pytest.mark.parametrize("reverse_order", [False, True])
@pytest.mark.parametrize(
    "statement",
    [
        "CREATE TABLE finance.reports.sales AS SELECT * FROM finance.reports",
        "SELECT * FROM finance.reports; CREATE TABLE finance.reports.sales AS SELECT 1 AS id",
    ],
)
def test_table_and_namespace_references_with_same_spelling(
    reverse_order: bool, statement: str
) -> None:
    sources = {
        "root": "CREATE SCHEMA finance",
        "source": "CREATE TABLE finance.reports (id INT)",
        "namespace": "CREATE SCHEMA finance.reports",
        "target": statement,
    }
    order = list(sources)
    graph = _sql_graph(sources, order[::-1] if reverse_order else order)
    assert graph.parents[CellId_t("target")] == {"root", "source", "namespace"}


@pytest.mark.parametrize("reverse_order", [False, True])
@pytest.mark.parametrize(
    ("external_definition", "statement"),
    [
        (
            "CREATE SCHEMA finance.reports",
            "CREATE TABLE finance.reports (id INT); CREATE TABLE finance.reports.sales AS SELECT * FROM finance.reports",
        ),
        (
            "CREATE TABLE finance.reports (id INT)",
            "CREATE SCHEMA finance.reports; SELECT * FROM finance.reports",
        ),
    ],
)
def test_local_definitions_only_satisfy_their_own_sql_kind(
    reverse_order: bool, external_definition: str, statement: str
) -> None:
    sources = {
        "root": "CREATE SCHEMA finance",
        "source": external_definition,
        "target": statement,
    }
    order = list(sources)
    graph = _sql_graph(sources, order[::-1] if reverse_order else order)
    assert graph.parents[CellId_t("target")] == {"root", "source"}


@pytest.mark.parametrize("reverse_order", [False, True])
def test_all_definitions_in_a_candidate_cell_are_matched(
    reverse_order: bool,
) -> None:
    sources = {
        "root": "CREATE SCHEMA finance",
        "namespace": "CREATE SCHEMA finance.reports",
        "source": (
            "CREATE SCHEMA other; CREATE SCHEMA other.reports; "
            "CREATE TABLE finance.reports.sales (id INT)"
        ),
        "query": "SELECT * FROM finance.reports.sales",
    }
    order = list(sources)
    graph = _sql_graph(sources, order[::-1] if reverse_order else order)
    assert graph.parents[CellId_t("query")] == {"root", "namespace", "source"}
    assert graph.parents[CellId_t("source")] == {"root", "namespace"}


@pytest.mark.parametrize("reverse_order", [False, True])
@pytest.mark.parametrize("namespace", ["finance", "main", "memory", "temp"])
def test_namespace_prerequisites_do_not_bind_python_variables(
    reverse_order: bool,
    namespace: str,
) -> None:
    cells = {
        "python": compiler.compile_cell(
            f"{namespace} = 100", cell_id=CellId_t("python")
        ),
        "table": _compile_sql(
            "table", f"CREATE TABLE {namespace}.sales (id INT)"
        ),
    }
    graph = dataflow.DirectedGraph()
    for cell_id in reversed(cells) if reverse_order else cells:
        graph.register_cell(CellId_t(cell_id), cells[cell_id])
    assert graph.parents[CellId_t("table")] == set()


@pytest.mark.parametrize(
    "order", list(permutations(("attach", "source", "query")))
)
def test_catalog_shorthand_refreshes_after_catalog_mutations(
    order: tuple[str, ...],
) -> None:
    sources = {
        "attach": "ATTACH ':memory:' AS attached",
        "source": "CREATE TABLE attached.sales (id INT)",
        "query": "SELECT * FROM attached.main.sales",
    }
    graph = _sql_graph(sources, order)
    assert graph.parents[CellId_t("query")] == {"attach", "source"}

    affected = graph.delete_cell(CellId_t("attach"))
    assert affected == dataflow.GraphMutationResult(
        frozenset({"source", "query"})
    )
    assert graph.parents[CellId_t("query")] == set()

    affected = graph.register_cell(
        CellId_t("attach"), _compile_sql("attach", sources["attach"])
    )
    assert CellId_t("query") in affected.affected_cells
    assert graph.parents[CellId_t("query")] == {"attach", "source"}


@pytest.mark.parametrize("reverse_order", [False, True])
@pytest.mark.parametrize(
    ("sources", "expected_parents"),
    [
        (
            {
                "attach": "ATTACH ':memory:' AS attached",
                "main": "CREATE TABLE attached.main.sales (id INT)",
                "other": "CREATE TABLE attached.finance.sales (id INT)",
                "local": "CREATE TABLE finance.sales (id INT)",
                "query": "SELECT * FROM attached.main.sales",
            },
            {"attach", "main"},
        ),
        (
            {
                "attach": "ATTACH ':memory:' AS attached",
                "local": "CREATE TABLE memory.attached.sales (id INT)",
                "remote": "CREATE TABLE attached.main.sales (id INT)",
                "query": "SELECT * FROM attached.main.sales",
            },
            {"attach", "remote"},
        ),
        (
            {
                "main": "CREATE TABLE memory.main.sales (id INT)",
                "other": "CREATE TABLE memory.finance.sales (id INT)",
                "query": "SELECT * FROM memory.main.sales",
            },
            {"main"},
        ),
        (
            {
                "root": "CREATE TABLE reports.sales (id INT)",
                "unrelated_schema": "CREATE SCHEMA reports",
                "nested": "CREATE TABLE finance.reports.sales (id INT)",
                "query": "SELECT * FROM finance.reports.sales",
            },
            {"nested"},
        ),
        (
            {
                "attach": "ATTACH ':memory:' AS attached",
                "other_attach": "ATTACH ':memory:' AS other",
                "table": "CREATE TABLE attached.finance.sales (id INT)",
                "other_table": "CREATE TABLE other.finance.sales (id INT)",
                "query": "SELECT * FROM attached.finance.sales",
            },
            {"attach", "table"},
        ),
    ],
)
def test_qualified_names_preserve_catalog_and_namespace_boundaries(
    reverse_order: bool,
    sources: dict[str, str],
    expected_parents: set[str],
) -> None:
    order = list(sources)
    graph = _sql_graph(sources, order[::-1] if reverse_order else order)
    assert graph.parents[CellId_t("query")] == expected_parents


def test_schema_conflict_identity_refreshes_with_catalog_bindings() -> None:
    sources = {
        "unqualified_catalog": "CREATE SCHEMA attached.finance",
        "default_catalog": "CREATE SCHEMA memory.attached.finance",
        "attach": "ATTACH ':memory:' AS attached",
    }
    graph = _sql_graph(sources, ["unqualified_catalog", "default_catalog"])
    assert graph.get_multiply_defined() == ["finance"]

    graph.register_cell(
        CellId_t("attach"), _compile_sql("attach", sources["attach"])
    )
    assert not graph.get_multiply_defined()
    graph.delete_cell(CellId_t("attach"))
    assert graph.get_multiply_defined() == ["finance"]

    graph = _sql_graph(
        sources, ["attach", "default_catalog", "unqualified_catalog"]
    )
    assert not graph.get_multiply_defined()


@pytest.mark.parametrize("schema", ["attached.nested", "attached.attached"])
def test_unregister_definitions_retains_catalog_binding(schema: str) -> None:
    cell_id = CellId_t("source")
    cell = _compile_sql(
        cell_id, f"ATTACH ':memory:' AS attached; CREATE SCHEMA {schema}"
    )
    registry = DefinitionRegistry()
    for name, variables in cell.variable_data.items():
        registry.register_definition(cell_id, name, variables)
    registry.rebuild_conflicts({cell_id: cell})

    registry.unregister_definitions(cell_id, cell.variable_data)

    assert (
        registry.definitions,
        registry.typed_definitions,
        registry.definition_conflicts,
        registry.conflict_names,
    ) == ({}, {}, {}, {})


def test_catalog_rebinding_adds_and_removes_cycles() -> None:
    graph = dataflow.DirectedGraph()
    graph.register_cell(
        CellId_t("source"),
        _compile_sql(
            "source", "CREATE TABLE attached.sales AS SELECT * FROM feedback"
        ),
    )
    graph.register_cell(
        CellId_t("query"),
        compiler.compile_cell(
            "feedback = mo.sql('SELECT * FROM attached.main.sales')",
            cell_id=CellId_t("query"),
        ),
    )
    assert not graph.cycles
    attach = _compile_sql("attach", "ATTACH ':memory:' AS attached")

    graph.register_cell(CellId_t("attach"), attach)
    assert len(graph.cycles) == 1
    assert set(next(iter(graph.cycles))) == {
        ("source", "query"),
        ("query", "source"),
    }
    graph.delete_cell(CellId_t("attach"))
    assert not graph.cycles
    assert graph.parents[CellId_t("source")] == {"query"}
    assert graph.parents[CellId_t("query")] == set()

    graph.register_cell(CellId_t("attach"), attach)
    assert len(graph.cycles) == 1


def test_catalog_rebinding_respects_disabled_dependencies() -> None:
    sources = {
        "source": "CREATE TABLE attached.sales (id INT)",
        "query": "SELECT * FROM attached.main.sales",
    }
    graph = _sql_graph(sources, ["source", "query"])
    graph.cells[CellId_t("source")].config.disabled = True
    assert not graph.is_disabled(CellId_t("query"))

    affected = graph.register_cell(
        CellId_t("attach"),
        _compile_sql("attach", "ATTACH ':memory:' AS attached"),
    )
    assert CellId_t("query") in affected.affected_cells
    assert graph.is_disabled(CellId_t("query"))
    graph.disable_cell(CellId_t("source"))
    assert graph.cells[CellId_t("query")].disabled_transitively

    graph.cells[CellId_t("source")].config.disabled = False
    graph.enable_cell(CellId_t("source"))
    assert not graph.is_disabled(CellId_t("query"))
    assert not graph.cells[CellId_t("query")].disabled_transitively


def test_unrelated_catalog_does_not_recompute_existing_sql_cells() -> None:
    sources = {
        "source": "CREATE TABLE sales (id INT)",
        "query": "SELECT * FROM sales",
    }
    graph = _sql_graph(sources, list(sources))
    with patch.object(
        edges, "compute_edges_for_cell", wraps=edges.compute_edges_for_cell
    ) as compute:
        graph.register_cell(
            CellId_t("attach"),
            _compile_sql("attach", "ATTACH ':memory:' AS unrelated"),
        )
        assert [call.args[0] for call in compute.call_args_list] == ["attach"]
        compute.reset_mock()
        graph.delete_cell(CellId_t("attach"))
        compute.assert_not_called()
    assert graph.parents[CellId_t("query")] == {"source"}


@pytest.mark.parametrize("alias", ["attached", "Attached"])
def test_duplicate_catalog_keeps_existing_bindings(alias: str) -> None:
    sources = {
        "attach": "ATTACH ':memory:' AS attached",
        "source": "CREATE TABLE attached.sales (id INT)",
        "query": "SELECT * FROM attached.main.sales",
    }
    graph = _sql_graph(sources, list(sources))
    with patch.object(
        edges, "compute_edges_for_cell", wraps=edges.compute_edges_for_cell
    ) as compute:
        graph.register_cell(
            CellId_t("duplicate"),
            _compile_sql("duplicate", f"ATTACH ':memory:' AS {alias}"),
        )
        assert [call.args[0] for call in compute.call_args_list] == [
            "duplicate"
        ]
        assert graph.parents[CellId_t("query")] == {
            "attach",
            "duplicate",
            "source",
        }
        compute.reset_mock()
        graph.delete_cell(CellId_t("duplicate"))
        compute.assert_not_called()
    assert graph.parents[CellId_t("query")] == {"attach", "source"}


def test_catalog_rebinding_updates_explicit_memory_readers() -> None:
    sources = {
        "source": "CREATE TABLE attached.sales (id INT)",
        "query": "SELECT * FROM memory.attached.sales",
    }
    graph = _sql_graph(sources, list(sources))
    assert graph.parents[CellId_t("query")] == {"source"}
    graph.register_cell(
        CellId_t("attach"),
        _compile_sql("attach", "ATTACH ':memory:' AS attached"),
    )
    assert graph.parents[CellId_t("query")] == set()
    graph.delete_cell(CellId_t("attach"))
    assert graph.parents[CellId_t("query")] == {"source"}


@pytest.mark.parametrize("alias", ["attached", "Attached"])
def test_same_cell_attach_satisfies_its_namespace(alias: str) -> None:
    cell = _compile_sql(
        "owner",
        f"ATTACH ':memory:' AS {alias}; CREATE TABLE {alias}.sales (id INT)",
    )
    assert not cell.sql_namespace_refs


@pytest.mark.parametrize("initially_attached", [False, True])
def test_catalog_rebinding_refreshes_disabled_state_of_descendants(
    initially_attached: bool,
) -> None:
    graph = dataflow.DirectedGraph()
    attach_id = CellId_t("attach")
    attach = _compile_sql(attach_id, "ATTACH ':memory:' AS attached")
    if initially_attached:
        graph.register_cell(attach_id, attach)
    source = _compile_sql("source", "CREATE TABLE attached.sales (id INT)")
    source.config.disabled = True
    graph.register_cell(CellId_t("source"), source)
    graph.register_cell(
        CellId_t("reader"),
        compiler.compile_cell(
            "rows = mo.sql('SELECT * FROM attached.main.sales')",
            cell_id=CellId_t("reader"),
        ),
    )
    graph.register_cell(
        CellId_t("descendant"),
        compiler.compile_cell("rows", cell_id=CellId_t("descendant")),
    )
    for cid in (CellId_t("reader"), CellId_t("descendant")):
        assert graph.cells[cid].disabled_transitively == initially_attached

    mutation = (
        graph.delete_cell(attach_id)
        if initially_attached
        else graph.register_cell(attach_id, attach)
    )

    assert CellId_t("reader") in mutation.affected_cells
    for cid in (CellId_t("reader"), CellId_t("descendant")):
        assert graph.is_disabled(cid) == (not initially_attached)
        assert graph.cells[cid].disabled_transitively == (
            not initially_attached
        )
