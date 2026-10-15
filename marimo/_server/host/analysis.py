# Copyright 2026 Marimo. All rights reserved.
"""Cell definitions, references, and syntax errors.

The kernel reports errors involving multiple cells, such as cycles
and multiple definitions.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from marimo._ast.compiler import compile_cell
from marimo._core import protocol
from marimo._core.analysis import Analyzed
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from marimo._ast.cell import CellImpl

LOGGER = logging.getLogger(__name__)
SOURCE = "marimo"


class HostAnalyzer:
    """Analyzes each requested revision in a thread and reports the result.

    Compiling cells can take long enough to stall the event loop, so the
    work runs in a worker. The notebook requests one revision at a time,
    which keeps the incremental state consistent.
    """

    def __init__(self, observe: Callable[[Analyzed], None]) -> None:
        self._cells = CellAnalyzer()
        self._observe = observe
        self._tasks: set[asyncio.Task[None]] = set()

    def analyze(
        self, document_etag: protocol.Etag, codes: Mapping[str, str]
    ) -> None:
        task = asyncio.create_task(self._run(document_etag, dict(codes)))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run(
        self, document_etag: protocol.Etag, codes: dict[str, str]
    ) -> None:
        cells: dict[str, protocol.CellAnalysis] | None
        try:
            cells = await asyncio.to_thread(self._cells, codes)
        except Exception:
            LOGGER.exception("Could not analyze document %s", document_etag)
            cells = None
        self._observe(Analyzed(document_etag, cells))


class CellAnalyzer:
    """Incremental analysis for one document."""

    def __init__(self) -> None:
        self._codes: dict[str, str] = {}
        self._compiled: dict[str, CellImpl] = {}
        self._syntax: dict[str, protocol.Error] = {}

    def __call__(
        self, codes: Mapping[str, str]
    ) -> dict[str, protocol.CellAnalysis]:
        self._update(codes)
        definers: dict[str, int] = {}
        for cell in self._compiled.values():
            for name in cell.defs:
                definers[name] = definers.get(name, 0) + 1
        result: dict[str, protocol.CellAnalysis] = {}
        for cell_id in codes:
            compiled = self._compiled.get(cell_id)
            if compiled is None:
                result[cell_id] = protocol.CellAnalysis(
                    defs=(), refs=(), errors=(self._syntax[cell_id],)
                )
                continue
            result[cell_id] = protocol.CellAnalysis(
                defs=tuple(sorted(compiled.defs)),
                refs=tuple(
                    sorted(
                        name
                        for name in compiled.refs
                        if definers.get(name, 0) > (name in compiled.defs)
                    )
                ),
                errors=(),
            )
        return result

    def _update(self, codes: Mapping[str, str]) -> None:
        """Forget cells that are gone or changed, then compile what is new."""
        for cell_id in list(self._codes):
            if codes.get(cell_id) == self._codes[cell_id]:
                continue
            del self._codes[cell_id]
            self._syntax.pop(cell_id, None)
            self._compiled.pop(cell_id, None)
        for cell_id, code in codes.items():
            if cell_id in self._codes:
                continue
            try:
                self._compiled[cell_id] = compile_cell(code, CellId_t(cell_id))
            except (SyntaxError, ValueError) as error:
                self._syntax[cell_id] = _syntax_error(code, error)
            self._codes[cell_id] = code


def analyze(codes: Mapping[str, str]) -> dict[str, protocol.CellAnalysis]:
    """Analyze a document once."""
    return CellAnalyzer()(codes)


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
