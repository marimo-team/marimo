# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import sys

if sys.version_info < (3, 9):
    from typing import AsyncContextManager as AbstractAsyncContextManager
    from typing import AsyncIterator, Callable, Sequence
else:
    from collections.abc import AsyncIterator, Callable, Sequence
    from contextlib import AbstractAsyncContextManager

from starlette.applications import Starlette
from typing_extensions import TypeAlias

from marimo import _loggers
from marimo._config.config import get_configuration
from marimo._config.utils import load_config
from marimo._server.api.interrupt import InterruptHandler
from marimo._server.api.utils import open_url_in_browser
from marimo._server.model import SessionMode
from marimo._server.print import print_shutdown, print_startup
from marimo._server.sessions import get_manager
from marimo._server.utils import initialize_mimetypes
from marimo._server.uvicorn_utils import close_uvicorn

LifespanList: TypeAlias = Sequence[
    Callable[[Starlette], AbstractAsyncContextManager[None]]
]

LOGGER = _loggers.marimo_logger()


async def _shutdown(app: Starlette, with_error: bool = False) -> None:
    """Shutdown the server."""
    mgr = get_manager()

    if with_error:
        LOGGER.fatal("marimo shut down with an error.")
    mgr.shutdown()
    if with_error:
        await close_uvicorn(app.state.server)


# Compound lifespans
class Lifespans:
    def __init__(
        self,
        lifespans: LifespanList,
    ) -> None:
        self.lifespans = lifespans

    @contextlib.asynccontextmanager
    async def _manager(
        self,
        app: Starlette,
        lifespans: LifespanList,
    ) -> AsyncIterator[None]:
        exit_stack = contextlib.AsyncExitStack()
        try:
            async with exit_stack:
                for lifespan in lifespans:
                    LOGGER.debug(f"Setup: {lifespan.__name__}")
                    await exit_stack.enter_async_context(lifespan(app))
                yield
        except asyncio.CancelledError:
            pass

    def __call__(self, app: Starlette) -> AbstractAsyncContextManager[None]:
        return self._manager(app, lifespans=self.lifespans)


@contextlib.asynccontextmanager
async def user_configuration(app: Starlette) -> AsyncIterator[None]:
    try:
        load_config()
    except Exception as e:
        LOGGER.fatal("Error parsing the marimo configuration file: ")
        LOGGER.fatal(type(e).__name__ + ": " + str(e))
        await _shutdown(app, with_error=True)

    yield


@contextlib.asynccontextmanager
async def lsp(app: Starlette) -> AsyncIterator[None]:
    del app
    user_config = get_configuration()
    session_mgr = get_manager()
    run = session_mgr.mode == SessionMode.RUN
    if not run and user_config["completion"]["copilot"]:
        LOGGER.debug("GitHub Copilot is enabled")
        session_mgr.start_lsp_server()
    yield


@contextlib.asynccontextmanager
async def open_browser(app: Starlette) -> AsyncIterator[None]:
    session_mgr = get_manager()
    url = f"http://localhost:{session_mgr.port}"
    user_config = get_configuration()
    headless = app.state.headless
    if not headless:
        browser = user_config["server"]["browser"]
        # Wait 20ms for the server to start and then open the browser, but this
        # function must complete
        asyncio.get_running_loop().call_later(
            0.02, open_url_in_browser, browser, url
        )
    yield


@contextlib.asynccontextmanager
async def logging(app: Starlette) -> AsyncIterator[None]:
    del app
    manager = get_manager()

    # Startup message
    if not manager.quiet:
        print_startup(
            manager.filename,
            f"http://localhost:{manager.port}",
            manager.mode == SessionMode.RUN,
        )

    yield

    # Shutdown message
    if not manager.quiet:
        print_shutdown()


@contextlib.asynccontextmanager
async def signal_handler(app: Starlette) -> AsyncIterator[None]:
    manager = get_manager()

    # Interrupt handler
    def shutdown() -> None:
        manager.shutdown()
        asyncio.create_task(close_uvicorn(app.state.server))

    InterruptHandler(
        quiet=manager.quiet,
        shutdown=shutdown,
    ).register()
    yield


@contextlib.asynccontextmanager
async def etc(app: Starlette) -> AsyncIterator[None]:
    del app
    # Mimetypes
    initialize_mimetypes()
    yield


LIFESPANS = Lifespans(
    [user_configuration, lsp, etc, signal_handler, logging, open_browser]
)
