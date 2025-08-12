# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import sys

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


CellCodes = dict[CellId_t, str]


async def ruff(codes: CellCodes, *cmd: str) -> CellCodes:
    # Try with sys.executable first
    ruff_cmd = [sys.executable, "-m", "ruff"]
    process = await asyncio.create_subprocess_exec(
        *ruff_cmd,
        "--help",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await process.wait()

    # If that fails, try global ruff
    if process.returncode != 0:
        ruff_cmd = ["ruff"]
        process = await asyncio.create_subprocess_exec(
            *ruff_cmd,
            "--help",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.wait()
        if process.returncode != 0:
            raise ModuleNotFoundError(
                "To enable code formatting, please install ruff", name="ruff"
            )

    formatted_codes: CellCodes = {}
    for key, code in codes.items():
        try:
            process = await asyncio.create_subprocess_exec(
                *ruff_cmd,
                *cmd,
                "-",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await process.communicate(code.encode())

            if process.returncode != 0:
                raise FormatError("Failed to format code with ruff")

            formatted = stdout.decode()
            formatted_codes[key] = formatted.strip()
        except Exception as e:
            LOGGER.error("Failed to format code with ruff")
            LOGGER.debug(e)
            continue

    return formatted_codes


class Formatter:
    def __init__(self, line_length: int) -> None:
        self.line_length = line_length

    async def format(self, codes: CellCodes) -> CellCodes:
        return codes


class DefaultFormatter(Formatter):
    """
    Tries ruff, then black, then no formatting.
    """

    async def format(self, codes: CellCodes) -> CellCodes:
        # Ruff may be installed in venv or globally
        if DependencyManager.ruff.has() or DependencyManager.which("ruff"):
            return await RuffFormatter(self.line_length).format(codes)
        # Black must be installed in venv
        elif DependencyManager.black.has():
            return await BlackFormatter(self.line_length).format(codes)
        else:
            raise ModuleNotFoundError(
                "To enable code formatting, please install ruff or black",
                name="ruff",
            )


class RuffFormatter(Formatter):
    async def format(self, codes: CellCodes) -> CellCodes:
        return await ruff(
            codes, "format", "--line-length", str(self.line_length)
        )


class BlackFormatter(Formatter):
    async def format(self, codes: CellCodes) -> CellCodes:
        DependencyManager.black.require("to enable code formatting")

        import black

        formatted_codes: CellCodes = {}
        for key, code in codes.items():
            try:
                # Run black formatting in a thread pool to avoid blocking
                mode = black.Mode(line_length=self.line_length)  # type: ignore
                formatted = await asyncio.to_thread(
                    black.format_str, code, mode=mode
                )
                formatted_codes[key] = formatted.strip()
            except Exception:
                formatted_codes[key] = code

        return formatted_codes


class FormatError(Exception):
    pass
