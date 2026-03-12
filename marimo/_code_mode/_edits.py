# Copyright 2026 Marimo. All rights reserved.
"""Notebook edit descriptors.

Build edits with ``NotebookEdit`` static methods, then apply them
with ``await ctx.apply(edits)``.

Tip: check this module's imports for where types live.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Union
from uuid import uuid4

from marimo._ast.cell import CellConfig
from marimo._types.ids import CellId_t

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class NotebookCellData:
    """Immutable cell descriptor (code and/or config).

    Use ``.replace()`` to derive a modified copy, or ``.edit()`` to
    produce a replace-edit for ``ctx.apply_edit()``.
    """

    code: str | None = None
    config: CellConfig | None = None
    draft: bool = False
    cell_id: CellId_t = field(default_factory=lambda: CellId_t(str(uuid4())))
    _index: int | None = field(default=None, repr=False, compare=False)

    def replace(self, **kwargs: Any) -> NotebookCellData:  # noqa: ANN401
        """Return a copy with the given fields replaced."""
        return dataclasses.replace(self, **kwargs)

    def edit(
        self,
        code: str | None = None,
        config: CellConfig | None = None,
        draft: bool = False,
    ) -> _ReplaceCells:
        """Return a replace-edit targeting this cell's position.

        Only works on cells returned by ``ctx.cells[i]`` (which have
        a known index).

        Args:
            code: New cell code. ``None`` keeps existing code.
            config: New cell config. ``None`` keeps existing config.
            draft: If ``True``, send as a draft for user review
                without executing.

        Example::

            cell = ctx.cells[6]
            await ctx.apply_edit(cell.edit(code="x = 30"))
        """
        if self._index is None:
            raise ValueError(
                "edit() requires a cell with a known index. "
                "Use cells returned by ctx.cells[i], not manually "
                "constructed NotebookCellData."
            )
        return _ReplaceCells(
            index=self._index,
            cells=[
                NotebookCellData(
                    code=code,
                    config=config,
                    draft=draft,
                    cell_id=self.cell_id,
                )
            ],
        )


@dataclass(frozen=True)
class _InsertCells:
    index: int
    cells: Sequence[NotebookCellData]


@dataclass(frozen=True)
class _DeleteCells:
    start: int
    end: int


@dataclass(frozen=True)
class _ReplaceCells:
    index: int
    cells: Sequence[NotebookCellData]


Edit = Union[_InsertCells, _DeleteCells, _ReplaceCells]


class NotebookEdit:
    """Static factories for notebook edits.

    Each method returns an edit descriptor. Pass one or a list
    to ``ctx.apply_edit()``.
    """

    @staticmethod
    def insert_cells(
        index: int, cells: Sequence[NotebookCellData]
    ) -> _InsertCells:
        """Insert cells at the given index.

        Index 0 prepends, len(cells) appends.
        """
        return _InsertCells(index=index, cells=cells)

    @staticmethod
    def delete_cells(start: int, end: int) -> _DeleteCells:
        """Delete cells in the range [start, end)."""
        return _DeleteCells(start=start, end=end)

    @staticmethod
    def replace_cells(
        index: int, cells: Sequence[NotebookCellData]
    ) -> _ReplaceCells:
        """Replace cells starting at index.

        Each cell replaces the cell at the corresponding position.
        ``code=None`` keeps existing code. ``config=None`` keeps
        existing config.
        """
        return _ReplaceCells(index=index, cells=cells)
