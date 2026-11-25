# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import shutil
import subprocess
import sys
import textwrap
from functools import lru_cache

from marimo import _loggers
from marimo._ast.parse import unwrap_cell_body
from marimo._dependencies.dependencies import DependencyManager
from marimo._types.ids import CellId_t
from marimo._utils.async_map import bounded_map

LOGGER = _loggers.marimo_logger()


CellCodes = dict[CellId_t, str]


async def _run_subprocess_safe(
    *args: str, input_data: bytes | None = None
) -> tuple[bytes, bytes, int]:
    """Run subprocess safely on all platforms, including Windows."""
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE if input_data is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await process.communicate(input_data)
        except asyncio.CancelledError:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass
            await process.communicate()
            raise
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


@lru_cache(maxsize=1)
def _ruff_binary() -> str:
    try:
        # Keep project modules out of the server and Ruff's discovery process.
        return subprocess.check_output(
            [
                sys.executable,
                "-I",
                "-c",
                "from ruff.__main__ import find_ruff_bin; print(find_ruff_bin())",
            ],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=30,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        binary = shutil.which("ruff")
        if binary is not None:
            return binary
        raise ModuleNotFoundError(
            "To enable code formatting, please install ruff", name="ruff"
        ) from None


async def ruff(
    codes: CellCodes, *cmd: str, stdin_filename: str | None = None
) -> CellCodes:
    if not codes:
        return {}
    command = [_ruff_binary(), *cmd]
    if stdin_filename:
        command.extend(["--stdin-filename", stdin_filename])
    command.append("-")

    async def format_cell(code: str) -> str | None:
        try:
            stdout, _stderr, returncode = await _run_subprocess_safe(
                *command, input_data=code.encode()
            )
            if returncode != 0:
                raise FormatError("Failed to format code with ruff")
            return stdout.decode().strip()
        except Exception as e:
            LOGGER.error("Failed to format code with ruff")
            LOGGER.debug(e)
            return None

    results = await bounded_map(
        format_cell, list(codes.values()), concurrency=8
    )
    return {
        key: result
        for key, result in zip(codes, results, strict=True)
        if result is not None
    }


class Formatter:
    def __init__(self, line_length: int) -> None:
        self.line_length = line_length

    async def format(
        self, codes: CellCodes, stdin_filename: str | None = None
    ) -> CellCodes:
        del stdin_filename
        return codes


class DefaultFormatter(Formatter):
    """
    Tries ruff, then black, then no formatting.
    """

    async def format(
        self, codes: CellCodes, stdin_filename: str | None = None
    ) -> CellCodes:
        # Ruff may be installed in venv or globally
        if DependencyManager.ruff.has() or DependencyManager.which("ruff"):
            return await RuffFormatter(self.line_length).format(
                codes, stdin_filename=stdin_filename
            )
        # Black must be installed in venv
        elif DependencyManager.black.has():
            return await BlackFormatter(self.line_length).format(codes)
        else:
            raise ModuleNotFoundError(
                "To enable code formatting, please install ruff or black",
                name="ruff",
            )


class RuffFormatter(Formatter):
    async def format(
        self, codes: CellCodes, stdin_filename: str | None = None
    ) -> CellCodes:
        # Wrap each cell in a dummy function so ruff applies function-scope
        # blank-line rules (1 blank line around nested defs) instead of
        # file-scope rules (2 blank lines). Cells with no executable
        # statements (whitespace-only or comment-only) are left unwrapped
        # since an empty or comment-only function body is invalid Python.
        skip_wrap = {
            key
            for key, code in codes.items()
            if all(
                not line.strip() or line.strip().startswith("#")
                for line in code.splitlines()
            )
        }
        wrapped: CellCodes = {}
        for key, code in codes.items():
            if key not in skip_wrap:
                wrapped[key] = "\n".join(
                    ["def _():", textwrap.indent(code, "    ")]
                )
            else:
                wrapped[key] = code

        wrapped_result = await ruff(
            wrapped,
            "format",
            "--line-length",
            str(self.line_length),
            stdin_filename=stdin_filename,
        )

        # Unwrap: use the AST to extract the function body, mirroring the
        # parse mechanism in marimo/_ast/parse.py (Extractor + fixed_dedent).
        result: CellCodes = {}
        for key, code in codes.items():
            if key in skip_wrap:
                result[key] = wrapped_result.get(key, code)
            elif key in wrapped_result:
                result[key] = unwrap_cell_body(wrapped_result[key])

        return result


class BlackFormatter(Formatter):
    async def format(
        self, codes: CellCodes, stdin_filename: str | None = None
    ) -> CellCodes:
        del stdin_filename
        DependencyManager.black.require("to enable code formatting")

        import black  # type: ignore[import-not-found]

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
