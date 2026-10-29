# Copyright 2026 Marimo. All rights reserved.
"""Cell definitions, references, syntax errors, and graph diagnostics."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from marimo._ast.cell import CellImpl
from marimo._ast.compiler import compile_cell
from marimo._core import protocol
from marimo._lint.validate_graph import (
    check_for_cycles,
    check_for_multiple_definitions,
)
from marimo._lint.visitors import VariableLineVisitor
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.dataflow.edges import resolve_cell_references
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._core.document import Document
    from marimo._messaging.errors import CycleError

SOURCE = "marimo"


class HostAnalyzer:
    """Analyze document revisions in a worker thread."""

    def __init__(self) -> None:
        self._cells = CellAnalyzer()

    async def analyze(
        self, document: Document
    ) -> dict[protocol.CellId, protocol.CellAnalysis]:
        return await asyncio.to_thread(self._cells, document)


@dataclass(frozen=True)
class _CachedCell:
    code_hash: protocol.Etag
    result: CellImpl | protocol.Error


class CellAnalyzer:
    """Reuse compilation by cell identity and code hash across revisions."""

    def __init__(self) -> None:
        self._cache: dict[protocol.CellId, _CachedCell] = {}

    def __call__(
        self, document: Document
    ) -> dict[protocol.CellId, protocol.CellAnalysis]:
        cache: dict[protocol.CellId, _CachedCell] = {}
        graph = DirectedGraph()
        for cell in document:
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

        conflicts = check_for_multiple_definitions(graph)
        cycles = check_for_cycles(graph)
        order = {cell.id: index for index, cell in enumerate(document)}
        analyses: dict[protocol.CellId, protocol.CellAnalysis] = {}
        for cell in document:
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
                    errors=tuple(
                        self._multiple_definitions(
                            cell.id,
                            error.name,
                            sorted(
                                [
                                    cell.id,
                                    *(
                                        protocol.CellId(cid)
                                        for cid in error.cells
                                    ),
                                ],
                                key=order.__getitem__,
                            ),
                        )
                        for error in conflicts.get(CellId_t(cell.id), ())
                    )
                    + tuple(
                        _cycle(error)
                        for error in sorted(
                            cycles.get(CellId_t(cell.id), ()),
                            key=lambda error: error.edges_with_vars,
                        )
                    ),
                )
        return analyses

    def _multiple_definitions(
        self,
        cell_id: protocol.CellId,
        name: str,
        definers: list[protocol.CellId],
    ) -> protocol.Error:
        return protocol.Error(
            kind="multiple-definitions",
            message=f"Multiple cells define {name}",
            source=SOURCE,
            severity="error",
            range=self._definition(cell_id, name),
            name=None,
            traceback=None,
            related=tuple(
                protocol.Related(
                    cell_id=definer,
                    range=self._definition(definer, name),
                    message=f"Defines {name}",
                )
                for definer in definers
            ),
        )

    def _definition(
        self, cell_id: protocol.CellId, name: str
    ) -> protocol.Range | None:
        compiled = self._cache[cell_id].result
        if not isinstance(compiled, CellImpl):
            raise RuntimeError("Expected a compiled cell for analysis")
        visitor = VariableLineVisitor(name, compiled.code)
        visitor.visit(compiled.mod)
        location = visitor.definition_range
        if location is None:
            return None
        line = location.line
        return protocol.Range(
            start=protocol.Position(
                line=line,
                character=_utf16(compiled.code, line, location.column),
            ),
            end=protocol.Position(
                line=line,
                character=_utf16(compiled.code, line, location.end_column),
            ),
        )


def _cycle(error: CycleError) -> protocol.Error:
    edges = error.edges_with_vars
    # Preserve dependency order, starting at the same cell for any rotation.
    start = min(range(len(edges)), key=lambda index: edges[index][2])
    edges = edges[start:] + edges[:start]
    return protocol.Error(
        kind="cycle-dependencies",
        message=error.describe(),
        source=SOURCE,
        severity="error",
        range=None,
        name=None,
        traceback=None,
        related=tuple(
            protocol.Related(
                cell_id=protocol.CellId(child),
                range=None,
                message=f"Depends on {parent}"
                + (f" through {', '.join(names)}" if names else ""),
            )
            for parent, names, child in edges
        ),
    )


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
