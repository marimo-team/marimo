# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import asyncio

from marimo._runtime.commands import ExecuteCellCommand
from tests._runtime._helpers.session import mocked_kernel_session


def _captured_console_messages() -> tuple[list[str], list[str]]:
    with mocked_kernel_session() as session:
        kernel = session.kernel

        async def run_cells() -> None:
            await kernel.run(
                [
                    ExecuteCellCommand(
                        cell_id="defs",
code="""
import asyncio
import sys

async def emit(label):
    await asyncio.sleep(0.01)
    print(f"{label} stdout")
    print(f"{label} stderr", file=sys.stderr)
""",
                    ),
                    ExecuteCellCommand(
                        cell_id="awaited",
                        code='await emit("awaited")',
                    ),
                    ExecuteCellCommand(
                        cell_id="created",
                        code=(
                            "task = asyncio.get_running_loop().create_task("
                            'emit("created-task"))'
                        ),
                    ),
                ]
            )
            await asyncio.sleep(0.05)

        asyncio.run(run_cells())
        return session.stdout.messages, session.stderr.messages


def test_awaited_async_stdout_is_captured_as_cell_console_output() -> None:
    stdout, _stderr = _captured_console_messages()
    assert "awaited stdout\n" in "".join(stdout)


def test_created_task_stdout_is_captured_as_cell_console_output() -> None:
    stdout, _stderr = _captured_console_messages()
    assert "created-task stdout\n" in "".join(stdout)


def test_created_task_stderr_is_captured_as_stderr_output() -> None:
    stdout, stderr = _captured_console_messages()

    assert "created-task stderr\n" not in "".join(stdout)
    assert "created-task stderr\n" in "".join(stderr)
