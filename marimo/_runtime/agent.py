# Copyright 2026 Marimo. All rights reserved.
"""Per-kernel agent state."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from marimo._messaging.notebook.document import NotebookDocument
    from marimo._types.ids import CellId_t


@dataclass(frozen=True)
class CellRevision:
    """Source replaced or deleted by an agent mutation."""

    sequence: int
    code: str
    name: str


class AgentRevisionStore:
    """Bounded source history for agent-authored mutations."""

    _MAX_REVISIONS_PER_CELL = 10
    _MAX_TOTAL_REVISIONS = 100
    _MAX_TOTAL_SOURCE_CHARS = 200_000

    def __init__(self) -> None:
        self._next_sequence = 1
        self._source_chars = 0
        self._truncated = False
        self._revisions: dict[CellId_t, list[CellRevision]] = {}

    def record(self, cell_id: CellId_t, *, code: str, name: str) -> None:
        revisions = self._revisions.setdefault(cell_id, [])
        if revisions and revisions[-1].code == code:
            return
        if len(code) > self._MAX_TOTAL_SOURCE_CHARS:
            self._truncated = True
            if not revisions:
                del self._revisions[cell_id]
            return
        revisions.append(
            CellRevision(
                sequence=self._next_sequence,
                code=code,
                name=name,
            )
        )
        self._next_sequence += 1
        self._source_chars += len(code)
        while len(revisions) > self._MAX_REVISIONS_PER_CELL:
            self._discard(revisions.pop(0))
        while (
            self._revision_count() > self._MAX_TOTAL_REVISIONS
            or self._source_chars > self._MAX_TOTAL_SOURCE_CHARS
        ):
            oldest_cell_id, oldest_revisions = min(
                self._revisions.items(),
                key=lambda item: item[1][0].sequence,
            )
            self._discard(oldest_revisions.pop(0))
            if not oldest_revisions:
                del self._revisions[oldest_cell_id]

    def _revision_count(self) -> int:
        return sum(len(revisions) for revisions in self._revisions.values())

    def _discard(self, revision: CellRevision) -> None:
        self._source_chars -= len(revision.code)
        self._truncated = True

    def all(self) -> dict[CellId_t, tuple[CellRevision, ...]]:
        return {
            cell_id: tuple(revisions)
            for cell_id, revisions in self._revisions.items()
        }

    @property
    def truncated(self) -> bool:
        return self._truncated


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
    revisions: AgentRevisionStore = field(default_factory=AgentRevisionStore)
