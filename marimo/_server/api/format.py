# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

from marimo import _loggers
from marimo._ast import cell
from marimo._server import server_utils as sessions
from marimo._server.api.validated_handler import ValidatedHandler
from marimo._utils.parse_dataclass import parse_raw

LOGGER = _loggers.marimo_logger()


@dataclass
class Format:
    # map from cell id to code
    codes: Dict[cell.CellId_t, str]
    line_length: int


class FormatHandler(ValidatedHandler):
    """Format code."""

    @sessions.requires_edit
    def post(self) -> None:
        try:
            import black
        except ModuleNotFoundError:
            LOGGER.debug(
                "To enable code formatting, install black (pip install black)"
            )
            return

        args = parse_raw(self.request.body, Format)
        codes = args.codes
        formatted_codes: dict[cell.CellId_t, str] = {}
        for key, code in codes.items():
            try:
                mode = black.Mode(line_length=args.line_length)  # type: ignore
                formatted = black.format_str(code, mode=mode)
                formatted_codes[key] = formatted.strip()
            except Exception:
                formatted_codes[key] = code
        self.write({"codes": formatted_codes})
