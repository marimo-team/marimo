# Copyright 2026 Marimo. All rights reserved.
"""Per-kernel agent state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._messaging.notebook.document import NotebookDocument
    from marimo._types.ids import CellId_t


class AgentReadTracker:
    """Highest cell version the agent has observed, per cell."""

    def __init__(self) -> None:
        self._read_versions: dict[CellId_t, int] = {}

    def record_read(self, cell_id: CellId_t, version: int) -> None:
        prev = self._read_versions.get(cell_id, -1)
        if version > prev:
            self._read_versions[cell_id] = version

    def has_read(self, cell_id: CellId_t, current_version: int) -> bool:
        last = self._read_versions.get(cell_id)
        return last is not None and last >= current_version

    def get_stale_cells(self, doc: NotebookDocument) -> frozenset[CellId_t]:
        # Empty (or whitespace-only) cells have nothing to clobber, so they
        # never count as stale even when the agent hasn't read them.
        stale: set[CellId_t] = set()
        for cell in doc.cells:
            if not cell.code.strip():
                continue
            last = self._read_versions.get(cell.id)
            if last is None or cell.version > last:
                stale.add(cell.id)
        return frozenset(stale)


@dataclass
class Agent:
    """One per `Kernel` — long-lived across scratchpad executions."""

    read_tracker: AgentReadTracker = field(default_factory=AgentReadTracker)
