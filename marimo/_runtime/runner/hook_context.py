# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, TypeAlias, Union

from marimo._config.config import OnCellChangeType
from marimo._messaging.errors import Error
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Iterator, Mapping, Sequence
    from contextlib import AbstractContextManager

    from marimo._runtime.context.types import ExecutionContext
    from marimo._runtime.dataflow.graph import DirectedGraph

ExceptionOrError = Union[BaseException, Error]

ExecutionContextManager: TypeAlias = Callable[
    [CellId_t], "AbstractContextManager[ExecutionContext]"
]


class CancelledCells:
    """Tracks cancelled cells with both structured and flat views.

    Maintains a mapping from raising cell -> cancelled descendants,
    and a flat set for O(1) membership checks.
    """

    def __init__(self) -> None:
        self._by_raising_cell: dict[CellId_t, set[CellId_t]] = {}
        self._all: set[CellId_t] = set()

    def add(self, raising_cell: CellId_t, descendants: set[CellId_t]) -> None:
        """Record that raising_cell caused descendants to be cancelled."""
        self._by_raising_cell[raising_cell] = descendants
        self._all.update(descendants)

    def __contains__(self, cell_id: object) -> bool:
        """O(1) check if a cell has been cancelled."""
        return cell_id in self._all

    def __iter__(self) -> Iterator[CellId_t]:
        """Iterate over raising cells."""
        return iter(self._by_raising_cell)

    def __getitem__(self, raising_cell: CellId_t) -> set[CellId_t]:
        """Get descendants cancelled by a specific raising cell."""
        return self._by_raising_cell[raising_cell]

    def __bool__(self) -> bool:
        return bool(self._by_raising_cell)


@dataclass(frozen=True)
class PreparationHookContext:
    graph: DirectedGraph
    execution_mode: OnCellChangeType
    cells_to_run: Sequence[CellId_t]


@dataclass(frozen=True)
class PreExecutionHookContext:
    graph: DirectedGraph
    execution_mode: OnCellChangeType


@dataclass(frozen=True)
class PostExecutionHookContext:
    graph: DirectedGraph
    glbls: dict[str, Any]
    execution_context: ExecutionContextManager | None
    # Dict, because errors get mutated (formatted) by hooks.
    exceptions: dict[CellId_t, ExceptionOrError]
    cancelled_cells: CancelledCells
    # Pre-computed union of all cell temporaries
    all_temporaries: frozenset[str]
    # Whether data (variables, datasets, etc.) should be broadcast
    # to the frontend. Computed once per run to avoid repeated checks.
    should_broadcast_data: bool = False
    # User configuration, for hooks that need access to runtime settings
    user_config: dict[str, Any] | None = None


@dataclass(frozen=True)
class OnFinishHookContext:
    graph: DirectedGraph
    cells_to_run: Sequence[CellId_t]
    interrupted: bool
    cancelled_cells: CancelledCells
    exceptions: Mapping[CellId_t, ExceptionOrError]
