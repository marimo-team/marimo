# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from marimo._ast.cell import Cell
from marimo._messaging.mimetypes import KnownMimeType
from marimo._output import formatting
from marimo._output.formatters.formatter_factory import FormatterFactory


class CellFormatter(FormatterFactory):
    @staticmethod
    def package_name() -> None:
        return None

    def register(self) -> None:
        @formatting.formatter(Cell)
        def _format_cell(cell: Cell) -> tuple[KnownMimeType, str]:
            return cell._help()._mime_()
