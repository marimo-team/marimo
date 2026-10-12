# Copyright 2026 Marimo. All rights reserved.
"""Execution attempts reported by the kernel.

An attempt has one identity from planning through completion, even when
compilation fails or the cell is skipped. Output keeps that identity after
completion, so a background thread cannot write into a later attempt.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from marimo._messaging.context import (
    EXECUTION_CTX,
    RUN_ID_CTX,
    execution_id_context,
)
from marimo._messaging.notification import ExecutionNotification
from marimo._messaging.notification_utils import broadcast_notification
from marimo._runtime.context.utils import get_mode
from marimo._types.ids import CellId_t


@dataclass
class ExecutionAttempt:
    """One planned evaluation of a cell, including its output identity."""

    cell_id: CellId_t
    id: str = field(default_factory=lambda: str(uuid4()))
    run_id: str | None = field(default_factory=lambda: RUN_ID_CTX.get(None))
    completed: bool = False

    @classmethod
    def plan(cls, cell_id: CellId_t, code: str) -> ExecutionAttempt:
        attempt = cls(cell_id)
        parent = EXECUTION_CTX.get()
        broadcast_notification(
            ExecutionNotification(
                execution_id=attempt.id,
                cell_id=cell_id,
                run_id=attempt.run_id,
                phase="planned",
                code=code if get_mode() != "run" else None,
                caused_by=(
                    parent.id
                    if parent is not None and parent.run_id == attempt.run_id
                    else None
                ),
            )
        )
        return attempt

    def activate(self) -> execution_id_context:
        """Attribute output in this context to the attempt."""
        return execution_id_context(self.cell_id, self.id)

    def start(self) -> None:
        self._notify("running")

    def finish(self) -> None:
        """Complete the attempt after its output and errors are reported."""
        if not self.completed:
            self.completed = True
            self._notify("completed")

    def _notify(self, phase: Literal["running", "completed"]) -> None:
        broadcast_notification(
            ExecutionNotification(
                execution_id=self.id,
                cell_id=self.cell_id,
                run_id=self.run_id,
                phase=phase,
            )
        )
