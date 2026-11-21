# Copyright 2026 Marimo. All rights reserved.
"""Cell definitions, references, syntax errors, and graph diagnostics."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marimo._ast.cell import CellImpl
from marimo._ast.compiler import compile_cell
from marimo._ast.definition_range import find_definition_range
from marimo._ast.names import SETUP_CELL_NAME
from marimo._ast.toplevel import TopLevelExtraction, TopLevelStatus
from marimo._core import protocol
from marimo._lint.validate_graph import (
    check_for_cycles,
    check_for_multiple_definitions,
)
from marimo._runtime.dataflow import DirectedGraph
from marimo._runtime.dataflow.edges import resolve_cell_references
from marimo._server.host import diagnostics
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Container

    from marimo._core.document import Document

_REUSABLE_MESSAGE = (
    "This definition is importable when the notebook is saved as Python."
)


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
    """What a cell's source alone determines, kept until the source changes."""

    code: str
    result: CellImpl | protocol.CellDiagnostic
    _ranges: dict[str, protocol.Range | None] = field(
        default_factory=dict, init=False, repr=False, compare=False
    )

    def definition_range(self, name: str) -> protocol.Range | None:
        """Where the cell binds `name`."""
        if name not in self._ranges:
            assert isinstance(self.result, CellImpl)
            self._ranges[name] = _locate_definition(self.result, name)
        return self._ranges[name]


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
                    result: CellImpl | protocol.CellDiagnostic = compile_cell(
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
        hints = self._reusable_definitions(document, graph, conflicts)
        position = diagnostics.by_position([cell.id for cell in document])
        analyses: dict[protocol.CellId, protocol.CellAnalysis] = {}
        for cell in document:
            compiled = cache[cell.id].result
            if isinstance(compiled, protocol.CellDiagnostic):
                analyses[cell.id] = protocol.CellAnalysis(
                    defs=(), refs=(), parents=(), diagnostics=(compiled,)
                )
                continue

            findings = []
            for conflict in conflicts.get(compiled.cell_id, ()):
                definers = sorted([cell.id, *conflict.cells], key=position)
                findings.append(
                    diagnostics.multiple_definitions(
                        cell.id,
                        conflict.name,
                        (protocol.CellId(cid) for cid in definers),
                        self._definition,
                    )
                )
            findings.extend(
                diagnostics.cycle(error)
                for error in sorted(
                    cycles.get(compiled.cell_id, ()),
                    key=lambda error: error.edges_with_vars,
                )
            )
            if cell.id in hints:
                findings.append(hints[cell.id])

            refs = resolve_cell_references(
                compiled.cell_id, compiled, graph, graph.definition_registry
            )
            analyses[cell.id] = protocol.CellAnalysis(
                defs=tuple(sorted(compiled.defs)),
                refs=tuple(sorted(refs)),
                parents=tuple(
                    protocol.CellId(parent)
                    for parent in sorted(graph.parents[compiled.cell_id])
                ),
                diagnostics=tuple(findings),
            )
        return analyses

    def _reusable_definitions(
        self,
        document: Document,
        graph: DirectedGraph,
        conflicting: Container[CellId_t],
    ) -> dict[protocol.CellId, protocol.CellDiagnostic]:
        # The file writer resolves definition-time references in document order.
        setup = next(
            (cell for cell in document if cell.name == SETUP_CELL_NAME), None
        )
        compiled_setup = graph.cells.get(CellId_t(setup.id)) if setup else None
        allowed = compiled_setup.defs if compiled_setup else set()
        statuses = [
            TopLevelStatus.from_cell(compiled, allowed, name=cell.name)
            for cell in document
            if cell is not setup
            and (compiled := graph.cells.get(CellId_t(cell.id))) is not None
        ]
        hints = {}
        for status in TopLevelExtraction(statuses, allowed):
            compiled = graph.cells[status.cell_id]
            if compiled.toplevel_variable is None or status.hint is None:
                continue
            # An import of a name that several cells define gets the last one.
            if status.is_toplevel and status.cell_id in conflicting:
                continue
            cell_id = protocol.CellId(status.cell_id)
            # A definition local to its cell binds no name to point at.
            where = next(
                (self._definition(cell_id, name) for name in compiled.defs),
                None,
            )
            reusable = status.is_toplevel
            hints[cell_id] = protocol.CellDiagnostic(
                source=diagnostics.SOURCE,
                kind="reusable-definition"
                if reusable
                else "non-reusable-definition",
                severity="information" if reusable else "hint",
                message=_REUSABLE_MESSAGE if reusable else status.hint,
                range=where,
                related=(),
            )
        return hints

    def _definition(
        self, cell_id: protocol.CellId, name: str
    ) -> protocol.Range | None:
        return self._cache[cell_id].definition_range(name)


def _locate_definition(compiled: CellImpl, name: str) -> protocol.Range | None:
    location = find_definition_range(compiled.mod, name, compiled.code)
    if location is None:
        return None
    return protocol.Range(
        start=protocol.Position(
            line=location.line,
            character=diagnostics.utf16(
                compiled.code, location.line, location.column
            ),
        ),
        end=protocol.Position(
            line=location.line,
            character=diagnostics.utf16(
                compiled.code, location.line, location.end_column
            ),
        ),
    )


def _syntax_error(code: str, e: Exception) -> protocol.CellDiagnostic:
    where = None
    if isinstance(e, SyntaxError) and e.lineno is not None:
        line = e.lineno - 1
        character = diagnostics.utf16(code, line, (e.offset or 1) - 1)
        point = protocol.Position(line=line, character=character)
        where = protocol.Range(start=point, end=point)
    message = e.msg if isinstance(e, SyntaxError) else str(e)
    return diagnostics.analysis_error("invalid-syntax", message, range_=where)
