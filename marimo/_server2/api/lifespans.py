# Copyright 2024 Marimo. All rights reserved.
import asyncio
import contextlib
import sys
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager

from fastapi import FastAPI
from typing_extensions import TypeAlias

from marimo import _loggers
from marimo._config.config import get_configuration
from marimo._config.utils import load_config
from marimo._server.model import SessionMode
from marimo._server.print import print_shutdown, print_startup
from marimo._server.sessions import get_manager
from marimo._server.utils import initialize_mimetypes
from marimo._server2.api.interupt import InterruptHandler
from marimo._server2.api.utils import open_url_in_browser

LifespanList: TypeAlias = Sequence[
    Callable[[FastAPI], AbstractAsyncContextManager[None]]
]

LOGGER = _loggers.marimo_logger()


def _shutdown(with_error: bool = False) -> None:
    """Shutdown the server."""
    mgr = get_manager()

    if with_error:
        LOGGER.fatal("marimo shut down with an error.")
    elif not mgr.quiet:
        print_shutdown()
    mgr.shutdown()
    if with_error:
        sys.exit(1)
    else:
        sys.exit(0)


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
        app: FastAPI,
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

    def __call__(self, app: FastAPI) -> AbstractAsyncContextManager[None]:
        return self._manager(app, lifespans=self.lifespans)


@contextlib.asynccontextmanager
async def user_configuration(app: FastAPI) -> AsyncIterator[None]:
    try:
        load_config()
    except Exception as e:
        LOGGER.fatal("Error parsing the marimo configuration file: ")
        LOGGER.fatal(type(e).__name__ + ": " + str(e))
        _shutdown(with_error=True)

    yield


@contextlib.asynccontextmanager
async def lsp(app: FastAPI) -> AsyncIterator[None]:
    user_config = get_configuration()
    session_mgr = get_manager()
    run = session_mgr.mode == SessionMode.RUN
    if not run and user_config["completion"]["copilot"]:
        LOGGER.debug("GitHub Copilot is enabled")
        session_mgr.start_lsp_server()
    yield


@contextlib.asynccontextmanager
async def open_browser(app: FastAPI) -> AsyncIterator[None]:
    session_mgr = get_manager()
    url = f"http://localhost:{session_mgr.port}"
    user_config = get_configuration()
    headless = app.state.headless
    if not headless:
        browser = user_config["server"]["browser"]
        open_url_in_browser(browser, url)
    yield


@contextlib.asynccontextmanager
async def logging(app: FastAPI) -> AsyncIterator[None]:
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
async def signal_handler(app: FastAPI) -> AsyncIterator[None]:
    manager = get_manager()

    # Interrupt handler
    def shutdown() -> None:
        manager.shutdown()
        print_shutdown()
        sys.exit(0)

    InterruptHandler(
        quiet=manager.quiet,
        shutdown=shutdown,
    ).register()
    yield


@contextlib.asynccontextmanager
async def etc(app: FastAPI) -> AsyncIterator[None]:
    # Mimetypes
    initialize_mimetypes()
    yield


LIFESPANS = Lifespans(
    [user_configuration, lsp, open_browser, etc, signal_handler, logging]
)
