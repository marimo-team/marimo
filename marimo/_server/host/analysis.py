# Copyright 2026 Marimo. All rights reserved.
"""Cell definitions, references, and syntax errors for the host protocol.

The kernel reports errors involving multiple cells.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo._ast.cell import CellImpl
from marimo._ast.compiler import compile_cell
from marimo._core import protocol
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.dataflow.edges import resolve_cell_references
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._core.document import DocumentSnapshot

SOURCE = "marimo"


class HostAnalyzer:
    """Analyze serialized document snapshots in a worker thread."""

    def __init__(self) -> None:
        self._cells = CellAnalyzer()

    async def analyze(
        self, snapshot: DocumentSnapshot
    ) -> dict[protocol.CellId, protocol.CellAnalysis]:
        return await asyncio.to_thread(self._cells, snapshot)


@dataclass(frozen=True)
class _CachedCell:
    code_hash: protocol.Etag
    result: CellImpl | protocol.Error


class CellAnalyzer:
    """Reuse compilation by cell identity and code hash across snapshots."""

    def __init__(self) -> None:
        self._cache: dict[protocol.CellId, _CachedCell] = {}

    def __call__(
        self, snapshot: DocumentSnapshot
    ) -> dict[protocol.CellId, protocol.CellAnalysis]:
        cache: dict[protocol.CellId, _CachedCell] = {}
        graph = DirectedGraph()
        for cell in snapshot.cells:
            cached = self._cache.get(cell.id)
            if cached is None or cached.code_hash != cell.code_hash:
                try:
                    result: CellImpl | protocol.Error = compile_cell(
                        cell.code, CellId_t(cell.id)
                    )
                except (SyntaxError, ValueError) as error:
                    result = _syntax_error(cell.code, error)
                cached = _CachedCell(cell.code_hash, result)
            cache[cell.id] = cached
            if isinstance(cached.result, CellImpl):
                graph.register_cell(CellId_t(cell.id), cached.result)
        self._cache = cache

        analyses: dict[protocol.CellId, protocol.CellAnalysis] = {}
        for cell in snapshot.cells:
            compiled = cache[cell.id].result
            if isinstance(compiled, protocol.Error):
                analyses[cell.id] = protocol.CellAnalysis(
                    defs=(), refs=(), errors=(compiled,)
                )
            else:
                refs = resolve_cell_references(
                    CellId_t(cell.id),
                    compiled,
                    graph,
                    graph.definition_registry,
                )
                analyses[cell.id] = protocol.CellAnalysis(
                    defs=tuple(sorted(compiled.defs)),
                    refs=tuple(sorted(refs)),
                    errors=(),
                )
        return analyses


def _syntax_error(code: str, e: Exception) -> protocol.Error:
    where = None
    if isinstance(e, SyntaxError) and e.lineno is not None:
        line = e.lineno - 1
        character = _utf16(code, line, (e.offset or 1) - 1)
        where = protocol.Range(
            start=protocol.Position(line=line, character=character),
            end=protocol.Position(line=line, character=character),
        )
    message = e.msg if isinstance(e, SyntaxError) else str(e)
    return protocol.Error(
        kind="invalid-syntax",
        message=message,
        source=SOURCE,
        severity="error",
        range=where,
        name=None,
        traceback=None,
        related=(),
    )


def _utf16(code: str, line: int, column: int) -> int:
    """Convert a source column to UTF-16 code units."""
    lines = code.split("\n")
    text = lines[line] if line < len(lines) else ""
    return len(text[:column].encode("utf-16-le")) // 2
