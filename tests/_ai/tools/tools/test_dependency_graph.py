# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from unittest.mock import Mock

import pytest

from marimo._ai._tools.base import ToolContext
from marimo._ai._tools.tools.dependency_graph import (
    GetCellDependencyGraph,
    GetCellDependencyGraphArgs,
    VariableInfo,
)
from marimo._ai._tools.utils.exceptions import ToolExecutionError
from marimo._types.ids import CellId_t, SessionId


def _make_cell_impl(
    defs: set[str],
    refs: set[str],
    variable_data: dict[str, list[Mock]] | None = None,
) -> Mock:
    cell = Mock()
    cell.defs = defs
    cell.refs = refs
    if variable_data is None:
        variable_data = {name: [Mock(kind="variable")] for name in defs}
    cell.variable_data = variable_data
    return cell


def _make_cell_data(cell_id: str, name: str = "") -> Mock:
    cd = Mock()
    cd.cell_id = CellId_t(cell_id)
    cd.name = name
    return cd


def _make_tool_with_graph(
    cell_impls: dict[str, Mock],
    parents: dict[str, set[str]],
    children: dict[str, set[str]],
    definitions: dict[str, set[str]],
    cell_data_list: list[Mock],
    cycles: set | None = None,
    ancestors_map: dict[str, set[str]] | None = None,
    descendants_map: dict[str, set[str]] | None = None,
) -> GetCellDependencyGraph:
    graph = Mock()
    graph.cells = {CellId_t(k): v for k, v in cell_impls.items()}
    graph.parents = {
        CellId_t(k): {CellId_t(p) for p in v} for k, v in parents.items()
    }
    graph.children = {
        CellId_t(k): {CellId_t(c) for c in v} for k, v in children.items()
    }
    graph.definitions = {
        k: {CellId_t(c) for c in v} for k, v in definitions.items()
    }
    graph.cycles = cycles or set()
    graph.get_multiply_defined.return_value = [
        name for name, defs in definitions.items() if len(defs) > 1
    ]

    if ancestors_map:
        graph.ancestors = lambda cid: {
            CellId_t(a) for a in ancestors_map.get(cid, set())
        }
    else:
        graph.ancestors = lambda _cid: set()

    if descendants_map:
        graph.descendants = lambda cid: {
            CellId_t(d) for d in descendants_map.get(cid, set())
        }
    else:
        graph.descendants = lambda _cid: set()

    cell_manager = Mock()
    cell_manager.cell_data.return_value = cell_data_list

    mock_app = Mock()
    mock_app.graph = graph
    mock_app.cell_manager = cell_manager

    mock_session = Mock()
    mock_session.app_file_manager.app = mock_app

    context = Mock(spec=ToolContext)
    context.get_session.return_value = mock_session

    tool = GetCellDependencyGraph(ToolContext())
    tool.context = context
    return tool


def test_full_graph_basic():
    """Three cells in a chain: c1 defines x, c2 refs x defines y, c3 refs y defines z."""
    tool = _make_tool_with_graph(
        cell_impls={
            "c1": _make_cell_impl(defs={"x"}, refs=set()),
            "c2": _make_cell_impl(defs={"y"}, refs={"x"}),
            "c3": _make_cell_impl(defs={"z"}, refs={"y"}),
        },
        parents={"c1": set(), "c2": {"c1"}, "c3": {"c2"}},
        children={"c1": {"c2"}, "c2": {"c3"}, "c3": set()},
        definitions={"x": {"c1"}, "y": {"c2"}, "z": {"c3"}},
        cell_data_list=[
            _make_cell_data("c1", "imports"),
            _make_cell_data("c2", "transform"),
            _make_cell_data("c3", "output"),
        ],
    )

    result = tool.handle(
        GetCellDependencyGraphArgs(session_id=SessionId("s1"))
    )

    assert result.status == "success"
    assert len(result.cells) == 3

    # Check cell ordering matches cell_data order
    assert result.cells[0].cell_id == "c1"
    assert result.cells[0].cell_name == "imports"
    assert result.cells[1].cell_id == "c2"
    assert result.cells[2].cell_id == "c3"

    # Check defs/refs
    assert result.cells[0].defs == [VariableInfo(name="x", kind="variable")]
    assert result.cells[0].refs == []
    assert result.cells[1].refs == ["x"]
    assert result.cells[2].refs == ["y"]

    # Check parent/child relationships
    assert result.cells[0].parent_cell_ids == []
    assert result.cells[0].child_cell_ids == ["c2"]
    assert result.cells[1].parent_cell_ids == ["c1"]
    assert result.cells[1].child_cell_ids == ["c3"]
    assert result.cells[2].parent_cell_ids == ["c2"]
    assert result.cells[2].child_cell_ids == []

    # Check variable owners
    assert result.variable_owners == {"x": ["c1"], "y": ["c2"], "z": ["c3"]}

    assert result.multiply_defined == []
    assert result.cycles == []


def test_cell_id_with_depth_1():
    """Centered on c2 with depth=1 should include c1, c2, c3 but not c0."""
    tool = _make_tool_with_graph(
        cell_impls={
            "c0": _make_cell_impl(defs={"w"}, refs=set()),
            "c1": _make_cell_impl(defs={"x"}, refs={"w"}),
            "c2": _make_cell_impl(defs={"y"}, refs={"x"}),
            "c3": _make_cell_impl(defs={"z"}, refs={"y"}),
        },
        parents={"c0": set(), "c1": {"c0"}, "c2": {"c1"}, "c3": {"c2"}},
        children={"c0": {"c1"}, "c1": {"c2"}, "c2": {"c3"}, "c3": set()},
        definitions={"w": {"c0"}, "x": {"c1"}, "y": {"c2"}, "z": {"c3"}},
        cell_data_list=[
            _make_cell_data("c0"),
            _make_cell_data("c1"),
            _make_cell_data("c2"),
            _make_cell_data("c3"),
        ],
    )

    result = tool.handle(
        GetCellDependencyGraphArgs(
            session_id=SessionId("s1"),
            cell_id=CellId_t("c2"),
            depth=1,
        )
    )

    cell_ids = [c.cell_id for c in result.cells]
    assert "c0" not in cell_ids
    assert "c1" in cell_ids
    assert "c2" in cell_ids
    assert "c3" in cell_ids

    # variable_owners is still global
    assert "w" in result.variable_owners


def test_cell_id_with_depth_none():
    """Centered on c2 with depth=None should return full transitive closure."""
    tool = _make_tool_with_graph(
        cell_impls={
            "c0": _make_cell_impl(defs={"w"}, refs=set()),
            "c1": _make_cell_impl(defs={"x"}, refs={"w"}),
            "c2": _make_cell_impl(defs={"y"}, refs={"x"}),
            "c3": _make_cell_impl(defs={"z"}, refs={"y"}),
        },
        parents={"c0": set(), "c1": {"c0"}, "c2": {"c1"}, "c3": {"c2"}},
        children={"c0": {"c1"}, "c1": {"c2"}, "c2": {"c3"}, "c3": set()},
        definitions={"w": {"c0"}, "x": {"c1"}, "y": {"c2"}, "z": {"c3"}},
        cell_data_list=[
            _make_cell_data("c0"),
            _make_cell_data("c1"),
            _make_cell_data("c2"),
            _make_cell_data("c3"),
        ],
        ancestors_map={"c2": {"c0", "c1"}},
        descendants_map={"c2": {"c3"}},
    )

    result = tool.handle(
        GetCellDependencyGraphArgs(
            session_id=SessionId("s1"),
            cell_id=CellId_t("c2"),
            depth=None,
        )
    )

    cell_ids = [c.cell_id for c in result.cells]
    assert set(cell_ids) == {"c0", "c1", "c2", "c3"}


def test_cell_id_not_found():
    """Invalid cell_id should raise ToolExecutionError."""
    tool = _make_tool_with_graph(
        cell_impls={},
        parents={},
        children={},
        definitions={},
        cell_data_list=[],
    )

    with pytest.raises(ToolExecutionError) as exc_info:
        tool.handle(
            GetCellDependencyGraphArgs(
                session_id=SessionId("s1"),
                cell_id=CellId_t("invalid"),
            )
        )
    assert exc_info.value.code == "CELL_NOT_FOUND"


def test_multiply_defined_variables():
    """Two cells defining the same variable should be reported."""
    tool = _make_tool_with_graph(
        cell_impls={
            "c1": _make_cell_impl(defs={"x"}, refs=set()),
            "c2": _make_cell_impl(defs={"x"}, refs=set()),
        },
        parents={"c1": set(), "c2": set()},
        children={"c1": set(), "c2": set()},
        definitions={"x": {"c1", "c2"}},
        cell_data_list=[
            _make_cell_data("c1"),
            _make_cell_data("c2"),
        ],
    )

    result = tool.handle(
        GetCellDependencyGraphArgs(session_id=SessionId("s1"))
    )

    assert result.multiply_defined == ["x"]
    assert sorted(result.variable_owners["x"]) == ["c1", "c2"]


def test_variable_kind_info():
    """Variable kind should be extracted from variable_data."""
    tool = _make_tool_with_graph(
        cell_impls={
            "c1": _make_cell_impl(
                defs={"bar", "foo"},
                refs=set(),
                variable_data={
                    "foo": [Mock(kind="function")],
                    "bar": [Mock(kind="variable")],
                },
            ),
        },
        parents={"c1": set()},
        children={"c1": set()},
        definitions={"foo": {"c1"}, "bar": {"c1"}},
        cell_data_list=[_make_cell_data("c1")],
    )

    result = tool.handle(
        GetCellDependencyGraphArgs(session_id=SessionId("s1"))
    )

    defs = result.cells[0].defs
    # Sorted by name
    assert defs[0] == VariableInfo(name="bar", kind="variable")
    assert defs[1] == VariableInfo(name="foo", kind="function")


def test_variable_owners_always_global():
    """variable_owners should include all variables even when depth-filtered."""
    tool = _make_tool_with_graph(
        cell_impls={
            "c1": _make_cell_impl(defs={"x"}, refs=set()),
            "c2": _make_cell_impl(defs={"y"}, refs={"x"}),
            "c3": _make_cell_impl(defs={"z"}, refs=set()),
        },
        parents={"c1": set(), "c2": {"c1"}, "c3": set()},
        children={"c1": {"c2"}, "c2": set(), "c3": set()},
        definitions={"x": {"c1"}, "y": {"c2"}, "z": {"c3"}},
        cell_data_list=[
            _make_cell_data("c1"),
            _make_cell_data("c2"),
            _make_cell_data("c3"),
        ],
    )

    result = tool.handle(
        GetCellDependencyGraphArgs(
            session_id=SessionId("s1"),
            cell_id=CellId_t("c1"),
            depth=1,
        )
    )

    # Only c1 and c2 are within depth 1 of c1
    cell_ids = [c.cell_id for c in result.cells]
    assert "c3" not in cell_ids

    # But z is still in variable_owners
    assert "z" in result.variable_owners
    assert result.variable_owners["z"] == ["c3"]


def test_empty_graph():
    """Empty graph should return empty results."""
    tool = _make_tool_with_graph(
        cell_impls={},
        parents={},
        children={},
        definitions={},
        cell_data_list=[],
    )

    result = tool.handle(
        GetCellDependencyGraphArgs(session_id=SessionId("s1"))
    )

    assert result.cells == []
    assert result.variable_owners == {}
    assert result.multiply_defined == []
    assert result.cycles == []
