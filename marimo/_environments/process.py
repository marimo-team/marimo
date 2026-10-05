# Copyright 2026 Marimo. All rights reserved.
"""Awaitable sandbox commands with ownership of their subprocesses."""

from __future__ import annotations

import asyncio
import subprocess
from typing import TYPE_CHECKING

from marimo import _loggers
from marimo._utils.subprocess import stop_subprocess

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

LOGGER = _loggers.marimo_logger()


async def run_command(
    argv: Sequence[str],
    *,
    env: Mapping[str, str] | None = None,
    cwd: str | None = None,
    timeout: float | None = None,
    on_stderr: Callable[[str], None] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Capture output and stream stderr without blocking the event loop.

    The callback runs on the caller's event loop. Cancellation and timeout
    stop the command's owned process group and finish reading its pipes before
    returning. Nonzero exits are returned for the backend to interpret.
    """
    loop = asyncio.get_running_loop()

    def report(line: str) -> None:
        if on_stderr is not None:
            try:
                on_stderr(line)
            except Exception:
                LOGGER.exception("Failed to report sandbox output")

    # Windows sessions use a selector loop, which has no asyncio subprocess
    # support. Own Popen here; only pipe reads and waiting run on threads.
    with subprocess.Popen(  # noqa: ASYNC220
        list(argv),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=cwd,
        start_new_session=True,
    ) as process:
        assert process.stdout is not None
        assert process.stderr is not None
        stderr_pipe = process.stderr

        def read_stderr() -> str:
            lines: list[str] = []
            for line in stderr_pipe:
                lines.append(line)
                if on_stderr is not None:
                    loop.call_soon_threadsafe(report, line)
            process.wait()
            return "".join(lines)

        output = asyncio.gather(
            loop.run_in_executor(None, process.stdout.read),
            loop.run_in_executor(None, read_stderr),
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                asyncio.shield(output), timeout=timeout
            )
        except BaseException:
            await stop_subprocess(
                process, start_new_session=True, drain=output
            )
            raise
    return subprocess.CompletedProcess(
        list(argv), process.returncode, stdout, stderr
    )
