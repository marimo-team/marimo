# Copyright 2026 Marimo. All rights reserved.
"""Cell definitions, references, and syntax errors."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._ast.compiler import compile_cell
from marimo._core import protocol
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Mapping

    from marimo._ast.cell import CellImpl

SOURCE = "marimo"


class Analyzer:
    """Incremental analysis for one document."""

    def __init__(self) -> None:
        self._codes: dict[str, str] = {}
        self._compiled: dict[str, CellImpl] = {}
        self._syntax: dict[str, protocol.Error] = {}

    def __call__(
        self, codes: Mapping[str, str]
    ) -> dict[str, protocol.Analysis]:
        self._update(codes)
        definers: dict[str, int] = {}
        for cell in self._compiled.values():
            for name in cell.defs:
                definers[name] = definers.get(name, 0) + 1
        result: dict[str, protocol.Analysis] = {}
        for cell_id in codes:
            compiled = self._compiled.get(cell_id)
            if compiled is None:
                result[cell_id] = protocol.Analysis(
                    defs=(), refs=(), errors=(self._syntax[cell_id],)
                )
                continue
            result[cell_id] = protocol.Analysis(
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
            self._codes[cell_id] = code
            try:
                self._compiled[cell_id] = compile_cell(code, CellId_t(cell_id))
            except (SyntaxError, ValueError) as error:
                self._syntax[cell_id] = _syntax_error(code, error)


def analyze(codes: Mapping[str, str]) -> dict[str, protocol.Analysis]:
    """Analyze a document once."""
    return Analyzer()(codes)


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
