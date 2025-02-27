# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import subprocess
import sys

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


CellCodes = dict[CellId_t, str]


def ruff(codes: CellCodes, *cmd: str) -> CellCodes:
    ruff_cmd = [sys.executable, "-m", "ruff"]
    process = subprocess.run([*ruff_cmd, "--help"], capture_output=True)
    if process.returncode != 0:
        LOGGER.warning(
            "To enable code formatting, install ruff (pip install ruff)"
        )
        return {}

    formatted_codes: CellCodes = {}
    for key, code in codes.items():
        try:
            process = subprocess.run(
                [
                    *ruff_cmd,
                    *cmd,
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


class Formatter:
    def __init__(self, line_length: int) -> None:
        self.line_length = line_length

    def format(self, codes: CellCodes) -> CellCodes:
        return codes


class DefaultFormatter(Formatter):
    """
    Tries ruff, then black, then no formatting.
    """

    def format(self, codes: CellCodes) -> CellCodes:
        if DependencyManager.ruff.has():
            return RuffFormatter(self.line_length).format(codes)
        elif DependencyManager.black.has():
            return BlackFormatter(self.line_length).format(codes)
        else:
            LOGGER.warning(
                "To enable code formatting, install ruff (pip install ruff) "
                "or black (pip install black)"
            )
            return {}


class RuffFormatter(Formatter):
    def format(self, codes: CellCodes) -> CellCodes:
        return ruff(codes, "format", "--line-length", str(self.line_length))


class BlackFormatter(Formatter):
    def format(self, codes: CellCodes) -> CellCodes:
        try:
            import black
        except ModuleNotFoundError:
            LOGGER.warning(
                "To enable code formatting, install ruff (pip install ruff) "
                "or black (pip install black)"
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
