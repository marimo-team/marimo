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
from marimo._server.host import diagnostics
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from marimo._core.document import Document


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
    code: str
    result: CellImpl | protocol.Error


class CellAnalyzer:
    """Reuse compilation by cell identity and exact source across revisions."""

    def __init__(self) -> None:
        self._cache: dict[protocol.CellId, _CachedCell] = {}

    def __call__(
        self, document: Document
    ) -> dict[protocol.CellId, protocol.CellAnalysis]:
        cache: dict[protocol.CellId, _CachedCell] = {}
        graph = DirectedGraph()
        for cell in document:
            cached = self._cache.get(cell.id)
            if cached is None or cached.code != cell.code:
                try:
                    result: CellImpl | protocol.Error = compile_cell(
                        cell.code, CellId_t(cell.id)
                    )
                except (SyntaxError, ValueError) as error:
                    result = _syntax_error(cell.code, error)
                cached = _CachedCell(cell.code, result)
            cache[cell.id] = cached
            if isinstance(cached.result, CellImpl):
                graph.register_cell(CellId_t(cell.id), cached.result)
        self._cache = cache

        conflicts = check_for_multiple_definitions(graph)
        cycles = check_for_cycles(graph)
        position = diagnostics.by_position([cell.id for cell in document])
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
                        diagnostics.multiple_definitions(
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
                                key=position,
                            ),
                            self._definition,
                        )
                        for error in conflicts.get(CellId_t(cell.id), ())
                    )
                    + tuple(
                        diagnostics.cycle(error)
                        for error in sorted(
                            cycles.get(CellId_t(cell.id), ()),
                            key=lambda error: error.edges_with_vars,
                        )
                    ),
                )
        return analyses

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
                character=diagnostics.utf16(
                    compiled.code, line, location.column
                ),
            ),
            end=protocol.Position(
                line=line,
                character=diagnostics.utf16(
                    compiled.code, line, location.end_column
                ),
            ),
        )


def _syntax_error(code: str, e: Exception) -> protocol.Error:
    where = None
    if isinstance(e, SyntaxError) and e.lineno is not None:
        line = e.lineno - 1
        character = diagnostics.utf16(code, line, (e.offset or 1) - 1)
        where = protocol.Range(
            start=protocol.Position(line=line, character=character),
            end=protocol.Position(line=line, character=character),
        )
    message = e.msg if isinstance(e, SyntaxError) else str(e)
    return diagnostics.error("invalid-syntax", message, range_=where)
