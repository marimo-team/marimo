# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import subprocess
import sys

from marimo import _loggers
from marimo._dependencies.dependencies import DependencyManager
from marimo._types.ids import CellId_t

LOGGER = _loggers.marimo_logger()


CellCodes = dict[CellId_t, str]


async def _run_subprocess_safe(
    *args: str, input_data: bytes | None = None
) -> tuple[bytes, bytes, int]:
    """Run subprocess safely on all platforms, including Windows."""
    try:
        # Try asyncio first (works on most platforms)
        if input_data is not None:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate(input_data)
        else:
            process = await asyncio.create_subprocess_exec(
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

        return stdout, stderr, process.returncode or 0
    except NotImplementedError:
        # Windows may throw NotImplementedError if using _WindowsSelectorEventLoop
        def run_sync() -> tuple[bytes, bytes, int]:
            if input_data is not None:
                result = subprocess.run(
                    args,
                    input=input_data,
                    capture_output=True,
                    timeout=30,  # Add reasonable timeout
                )
            else:
                result = subprocess.run(
                    args,
                    capture_output=True,
                    timeout=30,
                )
            return result.stdout, result.stderr, result.returncode

        return await asyncio.to_thread(run_sync)


async def ruff(codes: CellCodes, *cmd: str) -> CellCodes:
    # Try with sys.executable first
    ruff_cmd = [sys.executable, "-m", "ruff"]
    stdout, _stderr, returncode = await _run_subprocess_safe(
        *ruff_cmd, "--help"
    )

    # If that fails, try global ruff
    if returncode != 0:
        ruff_cmd = ["ruff"]
        stdout, _stderr, returncode = await _run_subprocess_safe(
            *ruff_cmd, "--help"
        )
        if returncode != 0:
            raise ModuleNotFoundError(
                "To enable code formatting, please install ruff", name="ruff"
            )

    formatted_codes: CellCodes = {}
    for key, code in codes.items():
        try:
            stdout, _stderr, returncode = await _run_subprocess_safe(
                *ruff_cmd, *cmd, "-", input_data=code.encode()
            )

            if returncode != 0:
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
