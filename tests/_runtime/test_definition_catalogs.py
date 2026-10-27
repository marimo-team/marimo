# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import PropertyMock, patch

import pytest

from marimo._ast.compiler import compile_cell
from marimo._ast.sql_visitor import SQLRef
from marimo._ast.visitor import VariableData
from marimo._runtime.dataflow.definitions import DefinitionRegistry
from marimo._runtime.dataflow.graph import DirectedGraph
from marimo._types.ids import CellId_t


@pytest.mark.parametrize(
    "variable",
    [
        VariableData("variable"),
        VariableData("function"),
        VariableData("table", sql_ref=SQLRef.from_parts(["finance", "sales"])),
        VariableData("view", sql_ref=SQLRef.from_parts(["finance", "sales"])),
        VariableData("catalog"),
    ],
)
def test_non_schema_definitions_do_not_scan_catalogs(
    variable: VariableData,
) -> None:
    registry = DefinitionRegistry()
    cell_id = CellId_t("source")
    with patch.object(
        DefinitionRegistry,
        "sql_catalogs",
        new_callable=PropertyMock,
        side_effect=AssertionError("catalog lookup is unnecessary"),
    ):
        registry.register_definition(cell_id, "sales", [variable])
        assert registry.get_defining_cells("sales") == {cell_id}
        assert registry.typed_definitions == {
            ("sales", variable.kind): {cell_id}
        }
        assert list(registry.definition_conflicts.values()) == [{cell_id}]
        registry.unregister_definitions(cell_id, {"sales": [variable]})

    assert (
        registry.definitions,
        registry.typed_definitions,
        registry.definition_conflicts,
        registry.conflict_names,
    ) == ({}, {}, {}, {})


def test_python_reference_lookup_does_not_scan_catalogs() -> None:
    graph = DirectedGraph()
    cell_id = CellId_t("reader")
    graph.register_cell(cell_id, compile_cell("value + 1", cell_id=cell_id))
    with patch.object(
        DefinitionRegistry,
        "sql_catalogs",
        new_callable=PropertyMock,
        side_effect=AssertionError("catalog lookup is unnecessary"),
    ):
        assert graph.get_referring_cells("value", language="python") == {
            cell_id
        }
