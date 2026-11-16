# Copyright 2026 Marimo. All rights reserved.
"""Errors the analyzer and the run translator describe the same way."""

from __future__ import annotations

from typing import TYPE_CHECKING

from marimo._core import protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Sequence

    from marimo._messaging.errors import CycleError
    from marimo._runtime.dataflow import EdgeWithVar

SOURCE = "marimo"


def error(
    kind: str,
    message: str,
    *,
    name: str | None = None,
    traceback: protocol.DisplayData | None = None,
    range_: protocol.Range | None = None,
    related: tuple[protocol.Related, ...] = (),
) -> protocol.Error:
    """An error marimo produced, at error severity."""
    return protocol.Error(
        kind=kind,
        name=name,
        message=message,
        traceback=traceback,
        source=SOURCE,
        severity="error",
        range=range_,
        related=related,
    )


def utf16(code: str, line: int, column: int) -> int:
    """Convert a source column to UTF-16 code units."""
    lines = code.split("\n")
    text = lines[line] if line < len(lines) else ""
    return len(text[:column].encode("utf-16-le")) // 2


def utf16_from_utf8(code: str, line: int, byte_column: int) -> int:
    """Convert an AST column, a UTF-8 byte offset, to UTF-16 code units."""
    lines = code.split("\n")
    text = lines[line] if line < len(lines) else ""
    column = len(text.encode()[:byte_column].decode("utf-8", "ignore"))
    return utf16(code, line, column)


def by_position(order: Sequence[str]) -> Callable[[str], tuple[int, str]]:
    """A sort key for document order, with cells not in it last by id."""
    index = {cell: position for position, cell in enumerate(order)}
    return lambda cell: (index.get(cell, len(index)), cell)


def depends_on(edges: Iterable[EdgeWithVar]) -> tuple[protocol.Related, ...]:
    """One entry per edge, on the cell that depends on the other."""
    return tuple(
        protocol.Related(
            cell_id=protocol.CellId(child),
            range=None,
            message=f"Depends on {parent}"
            + (f" through {', '.join(names)}" if names else ""),
        )
        for parent, names, child in edges
    )


def cycle(found: CycleError) -> protocol.Error:
    """The cycle in dependency order, starting at the same cell for any rotation."""
    edges = found.edges_with_vars
    start = min(range(len(edges)), key=lambda index: edges[index][2])
    return error(
        "cycle-dependencies",
        found.describe(),
        related=depends_on(edges[start:] + edges[:start]),
    )


def multiple_definitions(
    cell_id: protocol.CellId | None,
    name: str,
    definers: Iterable[protocol.CellId],
    where: Callable[[protocol.CellId, str], protocol.Range | None] = (
        lambda _cell, _name: None
    ),
) -> protocol.Error:
    """Every cell defining `name`, in the order given, placed at each definition."""
    return error(
        "multiple-definitions",
        f"Multiple cells define {name}",
        range_=None if cell_id is None else where(cell_id, name),
        related=tuple(
            protocol.Related(
                cell_id=definer,
                range=where(definer, name),
                message=f"Defines {name}",
            )
            for definer in definers
        ),
    )
