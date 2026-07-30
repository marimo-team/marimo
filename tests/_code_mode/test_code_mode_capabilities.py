from __future__ import annotations

import contextlib
import io
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, cast
from unittest.mock import MagicMock, patch

import pytest

import marimo._code_mode as cm
from marimo._code_mode._capabilities import (
    _LOADED_CAPABILITIES,
    CellView,
)

if TYPE_CHECKING:
    from collections.abc import Iterator, MutableMapping


class _Cells:
    def __init__(self) -> None:
        self._cells = (
            _Cell(
                id="cell-id",
                code="answer = source + 1",
                definitions=frozenset({"answer"}),
                references=frozenset({"source"}),
            ),
        )

    def __getitem__(self, key: int | str) -> CellView:
        if key in (0, "cell-id"):
            return self._cells[0]
        raise KeyError(key)

    def __iter__(self) -> Iterator[CellView]:
        return iter(self._cells)


class _Context:
    def __init__(self) -> None:
        self.globals: dict[str, object] = {"source": 41}
        self.cells = _Cells()


@dataclass(frozen=True)
class _Cell:
    id: str
    code: str
    definitions: frozenset[str]
    references: frozenset[str]


class _Capability:
    description = "Test capability"
    instructions = "Use the test capability."

    def bind(self, context: _Context) -> _Context:
        return context


def _capability() -> _Capability:
    return _Capability()


@pytest.fixture(autouse=True)
def clear_loaded_capabilities() -> Iterator[None]:
    _LOADED_CAPABILITIES.clear()
    yield
    _LOADED_CAPABILITIES.clear()


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_capabilities_lists_names_without_loading(
    get_entry_points: MagicMock,
) -> None:
    first = MagicMock(name="first")
    first.name = "zeta"
    second = MagicMock(name="second")
    second.name = "alpha"
    duplicate = MagicMock(name="duplicate")
    duplicate.name = "alpha"
    get_entry_points.return_value = [first, second, duplicate]

    assert cm.capabilities() == ("alpha", "zeta")
    get_entry_points.assert_called_once_with("marimo.agent.capability")
    first.load.assert_not_called()
    second.load.assert_not_called()
    duplicate.load.assert_not_called()


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_help_lists_installed_capabilities_without_loading(
    get_entry_points: MagicMock,
) -> None:
    entry_point = MagicMock()
    entry_point.name = "test"
    get_entry_points.return_value = [entry_point]

    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        help(cm)

    assert "Installed capabilities: test" in output.getvalue()
    assert "cm.capabilities()" in output.getvalue()
    entry_point.load.assert_not_called()


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_load_capability_loads_and_caches_one_capability(
    get_entry_points: MagicMock,
) -> None:
    entry_point = MagicMock()
    entry_point.name = "test"
    entry_point.load.return_value = _capability()
    get_entry_points.return_value = [entry_point]

    loaded = cm.load_capability("test")

    assert loaded.description == "Test capability"
    assert loaded.instructions == "Use the test capability."
    context = _Context()
    bound_context = loaded.bind(context)

    assert bound_context is not context
    assert isinstance(bound_context.globals, MappingProxyType)
    assert bound_context.globals == {"source": 41}
    mutable_globals = cast(
        "MutableMapping[str, object]", bound_context.globals
    )
    with pytest.raises(TypeError):
        mutable_globals["injected"] = True
    assert "injected" not in context.globals
    assert not hasattr(bound_context, "create_cell")
    assert not hasattr(bound_context, "edit_cell")
    context.globals["source"] = 42
    assert bound_context.globals == {"source": 41}

    cell = bound_context.cells["cell-id"]
    assert cell.code == "answer = source + 1"
    assert cell.definitions == frozenset({"answer"})
    assert cell.references == frozenset({"source"})
    assert bound_context.cells[0] is cell

    assert cm.load_capability("test") is loaded
    entry_point.load.assert_called_once_with()


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_load_capability_rejects_duplicate_names(
    get_entry_points: MagicMock,
) -> None:
    first = MagicMock()
    first.name = "test"
    second = MagicMock()
    second.name = "test"
    get_entry_points.return_value = [first, second]

    with pytest.raises(RuntimeError, match="Multiple capabilities"):
        cm.load_capability("test")

    first.load.assert_not_called()
    second.load.assert_not_called()


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_load_capability_rejects_invalid_provider(
    get_entry_points: MagicMock,
) -> None:
    entry_point = MagicMock()
    entry_point.name = "test"
    entry_point.load.return_value = object()
    get_entry_points.return_value = [entry_point]

    with pytest.raises(TypeError, match="must provide string 'description'"):
        cm.load_capability("test")


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_load_capability_wraps_import_error(
    get_entry_points: MagicMock,
) -> None:
    entry_point = MagicMock()
    entry_point.name = "test"
    entry_point.load.side_effect = ImportError("broken")
    get_entry_points.return_value = [entry_point]

    with pytest.raises(RuntimeError, match="Failed to import") as exc_info:
        cm.load_capability("test")

    assert isinstance(exc_info.value.__cause__, ImportError)


@patch("marimo._code_mode._capabilities.get_entry_points")
def test_load_capability_rejects_unknown_name(
    get_entry_points: MagicMock,
) -> None:
    get_entry_points.return_value = []

    with pytest.raises(KeyError, match="not installed"):
        cm.load_capability("missing")
