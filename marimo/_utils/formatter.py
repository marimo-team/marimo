# Copyright 2024 Marimo. All rights reserved.
import subprocess
from typing import Dict

from marimo import _loggers
from marimo._ast.cell import CellId_t
from marimo._dependencies.dependencies import DependencyManager

LOGGER = _loggers.marimo_logger()

CellCodes = Dict[CellId_t, str]


class Formatter:
    def __init__(self, line_length: int) -> None:
        self.data = None
        self.line_length = line_length

    def format(self, codes: CellCodes) -> CellCodes:
        return codes


class DefaultFormatter(Formatter):
    """
    Tries black, then ruff, then no formatting.
    """

    def format(self, codes: CellCodes) -> CellCodes:
        if DependencyManager.has("black"):
            return BlackFormatter(self.line_length).format(codes)
        elif DependencyManager.has("ruff"):
            return RuffFormatter(self.line_length).format(codes)
        else:
            LOGGER.warning(
                "To enable code formatting, install black (pip install black) "
                "or ruff (pip install ruff)"
            )
            return {}


class RuffFormatter(Formatter):
    def format(self, codes: CellCodes) -> CellCodes:
        formatted_codes: CellCodes = {}
        for key, code in codes.items():
            try:
                process = subprocess.run(
                    [
                        "ruff",
                        "format",
                        "--line-length",
                        str(self.line_length),
                        "-",
                    ],
                    input=code.encode(),
                    capture_output=True,
                    check=True,
                )
                if process.returncode != 0:
                    raise FormatError("Failed to format code with ruff")

                formatted = process.stdout.decode()
                formatted_codes[key] = formatted.strip()
            except Exception as e:
                LOGGER.error("Failed to format code with ruff")
                LOGGER.debug(e)
                continue

        return formatted_codes


class BlackFormatter(Formatter):
    def format(self, codes: CellCodes) -> CellCodes:
        try:
            import black
        except ModuleNotFoundError:
            LOGGER.warning(
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


class FormatError(Exception):
    pass
