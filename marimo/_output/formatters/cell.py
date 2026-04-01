# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell import Cell
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output import formatting
from marimo._output.formatters.formatter_factory import FormatterFactory


class CellFormatter(FormatterFactory):
    """Formatter factory for marimo Cell objects."""

    @staticmethod
    def package_name() -> None:
        """Return None because this formatter is always registered."""
        return None

    def register(self) -> None:
        """Register a formatter that renders a Cell as its help output."""
        @formatting.formatter(Cell)
        def _format_cell(cell: Cell) -> tuple[KnownMimeType, str]:
            return cell._help()._mime_()
