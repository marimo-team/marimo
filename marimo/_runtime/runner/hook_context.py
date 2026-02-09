# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, TypeAlias, Union

from marimo._config.config import OnCellChangeType
from marimo._messaging.errors import Error
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from contextlib import AbstractContextManager

    from marimo._runtime.context.types import ExecutionContext
    from marimo._runtime.dataflow.graph import DirectedGraph

ExceptionOrError = Union[BaseException, Error]

ExecutionContextManager: TypeAlias = Callable[
    [CellId_t], "AbstractContextManager[ExecutionContext]"
]


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
    cells_cancelled: Mapping[CellId_t, set[CellId_t]]
    # Whether data (variables, datasets, etc.) should be broadcast
    # to the frontend. Computed once per run to avoid repeated checks.
    should_broadcast_data: bool = False

    def cancelled(self, cell_id: CellId_t) -> bool:
        """Check if a cell was cancelled."""
        return any(
            cell_id in cancelled for cancelled in self.cells_cancelled.values()
        )


@dataclass(frozen=True)
class OnFinishHookContext:
    graph: DirectedGraph
    cells_to_run: Sequence[CellId_t]
    interrupted: bool
    cells_cancelled: Mapping[CellId_t, set[CellId_t]]
    exceptions: Mapping[CellId_t, ExceptionOrError]
