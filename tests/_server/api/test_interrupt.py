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
    set_signal.assert_called_once_with(
        signal.SIGINT, handler._interrupt_during_shutdown
    )
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


@pytest.mark.parametrize("windows", [False, True])
async def test_shutdown_filters_duplicates_but_allows_force_quit(
    windows: bool,
) -> None:
    handler = InterruptHandler(quiet=True, shutdown=Mock())
    with (
        patch.object(
            handler.loop,
            "remove_signal_handler",
            side_effect=NotImplementedError if windows else None,
        ),
        patch("signal.signal"),
        patch("marimo._server.api.interrupt.time") as clock,
    ):
        clock.monotonic.return_value = 10.0
        handler.stop()
        clock.monotonic.return_value = 10.2
        handler._interrupt_during_shutdown(signal.SIGINT, None)
        handler.stop()
        clock.monotonic.return_value = 11.1
        with pytest.raises(KeyboardInterrupt):
            handler._interrupt_during_shutdown(signal.SIGINT, None)


@pytest.mark.skipif(sys.platform == "win32", reason="Uses POSIX signals")
@pytest.mark.parametrize(
    "mode", ["sigint", "sigterm", "programmatic", "embedded", "force"]
)
def test_uvicorn_shutdown(mode: str) -> None:
    script = textwrap.dedent(
        """
        import asyncio
        from contextlib import asynccontextmanager
        import signal
        import sys
        from unittest.mock import AsyncMock, MagicMock, patch

        from starlette.applications import Starlette
        import uvicorn

        from marimo._server.api import lifespans
        from marimo._server.uvicorn_utils import close_uvicorn, initialize_signals
        from marimo._utils.lifespans import Lifespans

        mode = sys.argv[1]
        original_handler = signal.getsignal(signal.SIGINT)
        state = MagicMock()
        state.quiet = True
        state.session_manager.shutdown = AsyncMock()

        async def embedded():
            before = signal.getsignal(signal.SIGINT)
            async with lifespans.signal_handler(MagicMock()):
                pass
            assert signal.getsignal(signal.SIGINT) == before

        async def interrupt():
            while not server.started:
                await asyncio.sleep(0.001)
            if mode == "programmatic":
                close_uvicorn(server)
            elif mode == "sigterm":
                signal.raise_signal(signal.SIGTERM)
            else:
                signal.raise_signal(signal.SIGINT)
                await asyncio.sleep(0.01)
                signal.raise_signal(signal.SIGINT)
                await asyncio.sleep(0.2)
                signal.raise_signal(signal.SIGINT)

        @asynccontextmanager
        async def slow_cleanup(app):
            task = asyncio.create_task(interrupt())
            try:
                yield
            finally:
                await task
                if mode == "force":
                    asyncio.get_running_loop().call_later(
                        1.1, signal.raise_signal, signal.SIGINT
                    )
                    await asyncio.Event().wait()
                else:
                    await asyncio.sleep(0.2)
                    print("cleanup finished", flush=True)

        with patch.object(lifespans.AppState, "from_app", return_value=state):
            if mode == "embedded":
                asyncio.run(embedded())
                assert signal.getsignal(signal.SIGINT) == original_handler
            else:
                initialize_signals()
                app = Starlette(lifespan=Lifespans([
                    lifespans.signal_handler, slow_cleanup
                ]))
                server = uvicorn.Server(uvicorn.Config(app, log_level="error"))
                state.server = server
                try:
                    server.run(sockets=[])
                except KeyboardInterrupt:
                    assert mode == "force"
                    print("forced exit", flush=True)
                else:
                    assert mode != "force"
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", script, mode],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == (
        -signal.SIGTERM if mode == "sigterm" else 0
    ), result.stderr
    if mode == "force":
        assert "forced exit" in result.stdout
    elif mode != "embedded":
        assert "cleanup finished" in result.stdout
        assert "Traceback" not in result.stderr
