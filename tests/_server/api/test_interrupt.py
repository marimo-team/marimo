# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import signal
import subprocess
import sys
import textwrap
from unittest.mock import Mock, patch

import pytest

from marimo._server.api.interrupt import InterruptHandler


@pytest.mark.parametrize("quiet", [False, True])
@pytest.mark.parametrize("interactive", [False, True])
async def test_shutdown_is_requested_once(
    quiet: bool, interactive: bool
) -> None:
    shutdown = Mock()
    handler = InterruptHandler(quiet=quiet, shutdown=shutdown)
    with (
        patch.object(handler.loop, "remove_signal_handler"),
        patch("signal.signal") as set_signal,
        patch("sys.stdin.isatty", return_value=interactive),
        patch("builtins.input", return_value="y") as prompt,
    ):
        handler._interrupt_handler()
        handler._interrupt_handler()

    shutdown.assert_called_once_with()
    set_signal.assert_called_once_with(signal.SIGINT, signal.SIG_IGN)
    assert prompt.call_count == int(interactive and not quiet)


async def test_declining_shutdown_keeps_interrupt_handler() -> None:
    shutdown = Mock()
    handler = InterruptHandler(quiet=False, shutdown=shutdown)
    with (
        patch.object(handler.loop, "remove_signal_handler"),
        patch.object(handler, "_add_interrupt_handler") as register,
        patch("sys.stdin.isatty", return_value=True),
        patch("builtins.input", return_value="n"),
    ):
        handler._interrupt_handler()

    shutdown.assert_not_called()
    register.assert_called_once_with()


@pytest.mark.skipif(sys.platform == "win32", reason="Uses POSIX signals")
def test_repeated_sigint_does_not_cancel_cleanup() -> None:
    script = textwrap.dedent(
        """
        import asyncio
        import signal
        from unittest.mock import Mock

        from marimo._server.api.interrupt import InterruptHandler
        from marimo._server.uvicorn_utils import close_uvicorn

        async def main():
            finished = asyncio.Event()
            tasks = []

            async def cleanup():
                signal.raise_signal(signal.SIGINT)
                await asyncio.sleep(0.01)
                close_uvicorn(Mock())
                signal.raise_signal(signal.SIGINT)
                await asyncio.sleep(0.01)
                finished.set()

            def shutdown():
                tasks.append(asyncio.create_task(cleanup()))

            handler = InterruptHandler(quiet=True, shutdown=shutdown)
            handler.register()
            signal.raise_signal(signal.SIGINT)
            await asyncio.wait_for(finished.wait(), timeout=2)
            await asyncio.gather(*tasks)
            assert len(tasks) == 1

        asyncio.run(main())
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
