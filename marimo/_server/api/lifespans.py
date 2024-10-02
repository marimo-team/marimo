# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import asyncio
import contextlib
import socket
import sys
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import AbstractAsyncContextManager

from starlette.applications import Starlette

from marimo._server.api.deps import AppState, AppStateBase
from marimo._server.file_router import AppFileRouter
from marimo._server.sessions import SessionManager
from marimo._server.tokens import AuthToken

if sys.version_info < (3, 10):
    from typing_extensions import TypeAlias
else:
    from typing import TypeAlias

from marimo import _loggers
from marimo._server.api.interrupt import InterruptHandler
from marimo._server.api.utils import open_url_in_browser
from marimo._server.model import SessionMode
from marimo._server.print import print_shutdown, print_startup
from marimo._server.utils import initialize_mimetypes
from marimo._server.uvicorn_utils import close_uvicorn

LifespanList: TypeAlias = Sequence[
    Callable[[Starlette], AbstractAsyncContextManager[None]]
]

LOGGER = _loggers.marimo_logger()


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
async def lsp(app: Starlette) -> AsyncIterator[None]:
    state = AppState.from_app(app)
    user_config = state.config_manager.get_config()
    session_mgr = state.session_manager
    run = session_mgr.mode == SessionMode.RUN
    if not run and user_config["completion"]["copilot"]:
        LOGGER.debug("GitHub Copilot is enabled")
        await session_mgr.start_lsp_server()
    yield


@contextlib.asynccontextmanager
async def watcher(app: Starlette) -> AsyncIterator[None]:
    state = AppState.from_app(app)
    if state.watch:
        session_mgr = state.session_manager
        session_mgr.start_file_watcher()
    yield


@contextlib.asynccontextmanager
async def open_browser(app: Starlette) -> AsyncIterator[None]:
    state = AppState.from_app(app)
    if not state.headless:
        url = _startup_url(state)
        user_config = state.config_manager.get_config()
        browser = user_config["server"]["browser"]
        # Wait 20ms for the server to start and then open the browser, but this
        # function must complete
        asyncio.get_running_loop().call_later(
            0.02, open_url_in_browser, browser, url
        )
    yield


@contextlib.asynccontextmanager
async def logging(app: Starlette) -> AsyncIterator[None]:
    state = AppState.from_app(app)
    manager: SessionManager = state.session_manager
    file_router = manager.file_router

    # Startup message
    if not manager.quiet:
        file = file_router.maybe_get_single_file()
        print_startup(
            file.name if file else None,
            _startup_url(state),
            manager.mode == SessionMode.RUN,
            new=file_router.get_unique_file_key() == AppFileRouter.NEW_FILE,
        )

    yield

    # Shutdown message
    if not manager.quiet:
        print_shutdown()


@contextlib.asynccontextmanager
async def signal_handler(app: Starlette) -> AsyncIterator[None]:
    state = AppState.from_app(app)
    manager = state.session_manager

    # Interrupt handler
    def shutdown() -> None:
        manager.shutdown()
        if state.server:
            close_uvicorn(state.server)

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


def _startup_url(state: AppStateBase) -> str:
    host = state.host
    port = state.port
    try:
        # pretty printing:
        # if the address maps to localhost, print "localhost" to stdout
        if (
            socket.getnameinfo((host, port), socket.NI_NOFQDN)[0]
            == "localhost"
        ):
            host = "localhost"
    except Exception:
        # aggressive try/except in case of platform-specific quirks;
        # nothing to handle, since the `try` logic is just for pretty
        # printing the host name
        ...

    url = f"http://{host}:{port}{state.base_url}"
    if port == 80:
        url = f"http://{host}{state.base_url}"
    elif port == 443:
        url = f"https://{host}{state.base_url}"

    if AuthToken.is_empty(state.session_manager.auth_token):
        return url
    return f"{url}?access_token={str(state.session_manager.auth_token)}"
