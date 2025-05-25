# Copyright 2024 Marimo. All rights reserved.
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Optional

import uvicorn

import marimo._server.api.lifespans as lifespans
from marimo._config.manager import get_default_config_manager
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._runtime.requests import SerializedCLIArgs
from marimo._server.file_router import AppFileRouter, flatten_files
from marimo._server.lsp import CompositeLspServer, NoopLspServer
from marimo._server.main import create_starlette_app
from marimo._server.model import SessionMode
from marimo._server.registry import LIFESPAN_REGISTRY
from marimo._server.sessions import SessionManager
from marimo._server.tokens import AuthToken
from marimo._server.utils import (
    find_free_port,
    initialize_asyncio,
    initialize_fd_limit,
)
from marimo._server.uvicorn_utils import initialize_signals
from marimo._tracer import LOGGER
from marimo._utils.lifespans import Lifespans
from marimo._utils.marimo_path import MarimoPath
from marimo._utils.paths import marimo_package_path

DEFAULT_PORT = 2718
PROXY_REGEX = re.compile(r"^(.*):(\d+)$")

if TYPE_CHECKING:
    from starlette.applications import Starlette


def _resolve_proxy(
    port: int, host: str, proxy: Optional[str]
) -> tuple[int, str]:
    """Provided that there is a proxy, utilize the host and port of the proxy.

    -----------------         Communication has to be consistent
    |   User        | ----    so Starlette only needs to know the
    -----------------     |   external facing endpoint, while uvi-
                          |   corn handles the actual running of
                          v   the app.
                  -----------------
      e.g. nginx  |   Proxy       |
                  -----------------
                          |
                          v
                  -----------------
        the app   |   marimo      |
       (uvicorn)  -----------------


    If the proxy is provided, it will default to port 80. Otherwise if the
    proxy has a port specified, it will use that port.
    e.g. `example.com:8080`
    """
    if not proxy:
        return port, host

    match = PROXY_REGEX.match(proxy)
    # Our proxy has an explicit port defined, so return that.
    if match:
        external_host, external_port = match.groups()
        return int(external_port), external_host

    # A default to 80 is reasonable if a proxy is provided.
    return 80, proxy


def start(
    *,
    file_router: AppFileRouter,
    mode: SessionMode,
    development_mode: bool,
    quiet: bool,
    include_code: bool,
    ttl_seconds: Optional[int],
    headless: bool,
    port: Optional[int],
    host: str,
    proxy: Optional[str],
    watch: bool,
    cli_args: SerializedCLIArgs,
    argv: list[str],
    base_url: str = "",
    allow_origins: Optional[tuple[str, ...]] = None,
    auth_token: Optional[AuthToken],
    redirect_console_to_browser: bool,
) -> None:
    """
    Start the server.
    """

    # Find a free port if none is specified
    # if the user specifies a port, we don't try to find a free one
    port = port or find_free_port(DEFAULT_PORT)

    # This is the path that will be used to read the project configuration
    start_path: Optional[str] = None
    if (single_file := file_router.maybe_get_single_file()) is not None:
        start_path = single_file.path
    elif (directory := file_router.directory) is not None:
        start_path = directory
    else:
        start_path = os.getcwd()

    config_reader = get_default_config_manager(current_path=start_path)

    lsp_composite_server: Optional[CompositeLspServer] = None
    if mode == SessionMode.EDIT:
        lsp_composite_server = CompositeLspServer(
            config_reader=config_reader,
            min_port=DEFAULT_PORT + 400,
        )

    # If watch is true, disable auto-save and format-on-save,
    # watch is enabled when they are editing in another editor
    if watch:
        config_reader = config_reader.with_overrides(
            {
                "save": {
                    "autosave": "off",
                    "format_on_save": False,
                    "autosave_delay": 1000,
                }
            }
        )
        LOGGER.info("Watch mode enabled, auto-save is disabled")

    if GLOBAL_SETTINGS.MANAGE_SCRIPT_METADATA:
        config_reader = config_reader.with_overrides(
            {
                # Currently, only uv is supported for managing script metadata
                # If this changes, instead we should only update the config
                # if the user's package manager does not support sandboxes.
                "package_management": {
                    "manager": "uv",
                }
            }
        )

    (external_port, external_host) = _resolve_proxy(port, host, proxy)
    lifespan = Lifespans(
        [
            lifespans.lsp,
            lifespans.etc,
            lifespans.signal_handler,
            lifespans.logging,
            lifespans.open_browser,
            *LIFESPAN_REGISTRY.get_all(),
        ]
    )

    def create_app(file_router: AppFileRouter, subpath: str = "") -> Starlette:
        session_manager = SessionManager(
            file_router=file_router,
            mode=mode,
            development_mode=development_mode,
            quiet=quiet,
            include_code=include_code,
            ttl_seconds=ttl_seconds,
            lsp_server=lsp_composite_server or NoopLspServer(),
            config_manager=config_reader,
            cli_args=cli_args,
            argv=argv,
            auth_token=auth_token,
            redirect_console_to_browser=redirect_console_to_browser,
            watch=watch,
        )

        app = create_starlette_app(
            base_url=base_url + subpath,
            host=external_host,
            lifespan=lifespan,
            allow_origins=allow_origins,
            enable_auth=not AuthToken.is_empty(session_manager.auth_token),
            lsp_servers=list(lsp_composite_server.servers.values())
            if lsp_composite_server is not None
            else None,
        )

        app.state.port = external_port
        app.state.host = external_host

        app.state.headless = headless
        app.state.watch = watch
        app.state.session_manager = session_manager
        app.state.base_url = base_url
        app.state.config_manager = config_reader
        return app

    # If we were requested a dictionary and in run mode, we create a new app
    # for each file.
    if file_router.directory and mode == SessionMode.RUN:
        app = create_app(file_router)
        marimo_files = [
            file
            for file in flatten_files(file_router.files)
            if file.is_marimo_file
        ]
        for file in marimo_files:
            pathname = (
                Path(file.path)
                .relative_to(file_router.directory)
                .with_suffix("")
                .as_posix()
            )
            app.mount(
                f"/{pathname}/",
                create_app(AppFileRouter.from_filename(MarimoPath(file.path))),
            )
    else:
        app = create_app(file_router)

    # Resource initialization
    # Increase the limit on open file descriptors to prevent resource
    # exhaustion when opening multiple notebooks in the same server.
    initialize_fd_limit(limit=4096)
    initialize_signals()

    log_level = "info" if development_mode else "error"
    server = uvicorn.Server(
        uvicorn.Config(
            app=app,
            port=port,
            host=host,
            # TODO: cannot use reload unless the app is an import string
            # although cannot use import string because it breaks the
            # session manager
            # reload=development_mode,
            reload_dirs=(
                [
                    str((marimo_package_path() / "_static").resolve()),
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
            # Under uvloop, reading the socket we monitor under add_reader()
            # occasionally throws BlockingIOError (errno 11, or errno 35,
            # ...). RUN mode no longer uses a socket (it has no IPC) but EDIT
            # does, so force asyncio.
            loop="asyncio" if mode == SessionMode.EDIT else "auto",
        )
    )
    app.state.server = server

    initialize_asyncio()
    server.run()
