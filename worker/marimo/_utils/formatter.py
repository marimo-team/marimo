# Copyright 2024 Marimo. All rights reserved.
from typing import Dict

from marimo import _loggers
from marimo._ast.cell import CellId_t

LOGGER = _loggers.marimo_logger()

CellCodes = Dict[CellId_t, str]


class Formatter:
    def __init__(self, line_length: int) -> None:
        self.data = None
        self.line_length = line_length

    def format(self, codes: CellCodes) -> CellCodes:
        return codes


class BlackFormatter(Formatter):
    def format(self, codes: CellCodes) -> CellCodes:
        try:
            import black
        except ModuleNotFoundError:
            LOGGER.warn(
                "To enable code formatting, install black (pip install black)"
            )
            return {}

        formatted_codes: CellCodes = {}
        for key, code in codes.items():
            try:
                mode = black.Mode(line_length=self.line_length)  # type: ignore
                formatted = black.format_str(code, mode=mode)
                formatted_codes[key] = formatted.strip()
            except Exception:
                formatted_codes[key] = code

        return formatted_codes
