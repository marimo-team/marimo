# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
from typing import Optional

import uvicorn

import marimo._server.api.lifespans as lifespans
from marimo._config.manager import UserConfigManager
from marimo._runtime.requests import SerializedCLIArgs
from marimo._server.file_router import AppFileRouter
from marimo._server.main import create_starlette_app
from marimo._server.model import SessionMode
from marimo._server.sessions import LspServer, SessionManager
from marimo._server.utils import find_free_port, initialize_asyncio
from marimo._server.uvicorn_utils import initialize_signals
from marimo._utils.paths import import_files

DEFAULT_PORT = 2718


def start(
    *,
    file_router: AppFileRouter,
    mode: SessionMode,
    development_mode: bool,
    quiet: bool,
    include_code: bool,
    headless: bool,
    port: Optional[int],
    host: str,
    watch: bool,
    cli_args: SerializedCLIArgs,
    base_url: str = "",
) -> None:
    """
    Start the server.
    """

    # Find a free port if none is specified
    # if the user specifies a port, we don't try to find a free one
    port = port or find_free_port(DEFAULT_PORT)
    user_config_mgr = UserConfigManager()

    session_manager = SessionManager(
        file_router=file_router,
        mode=mode,
        development_mode=development_mode,
        quiet=quiet,
        include_code=include_code,
        lsp_server=LspServer(port * 10),
        user_config_manager=user_config_mgr,
        cli_args=cli_args,
    )

    log_level = "info" if development_mode else "error"

    app = create_starlette_app(
        base_url=base_url,
        lifespan=lifespans.Lifespans(
            [
                lifespans.lsp,
                lifespans.watcher,
                lifespans.etc,
                lifespans.signal_handler,
                lifespans.logging,
                lifespans.open_browser,
            ]
        ),
    )

    app.state.headless = headless
    app.state.port = port
    app.state.host = host or "localhost"
    app.state.watch = watch
    app.state.session_manager = session_manager
    app.state.base_url = base_url
    app.state.config_manager = user_config_mgr

    initialize_signals()
    server = uvicorn.Server(
        uvicorn.Config(
            app,
            port=port,
            host=host,
            # TODO: cannot use reload unless the app is an import string
            # although cannot use import string because it breaks the
            # session manager
            # reload=development_mode,
            reload_dirs=(
                [
                    os.path.realpath(
                        str(import_files("marimo").joinpath("_static"))
                    )
                ]
                if development_mode
                else None
            ),
            log_level=log_level,
            # uvicorn times out HTTP connections (i.e. TCP sockets) every 5
            # seconds by default; for some reason breaks the server in
            # mysterious ways (it stops processing requests) in edit mode.
            timeout_keep_alive=300 if mode == SessionMode.RUN else int(1e9),
            # ping the websocket once a second to prevent intermittent
            # disconnections
            ws_ping_interval=1,
            # close the websocket if we don't receive a pong after 60 seconds
            ws_ping_timeout=60,
            timeout_graceful_shutdown=1,
        )
    )
    app.state.server = server

    initialize_asyncio()
    server.run()
