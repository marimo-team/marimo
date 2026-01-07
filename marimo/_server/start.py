# Copyright 2026 Marimo. All rights reserved.
from __future__ import annotations

import os
import re
import subprocess
import threading
from typing import Optional

import uvicorn

import marimo._server.api.lifespans as lifespans
from marimo._cli.print import echo
from marimo._config.manager import get_default_config_manager
from marimo._config.settings import GLOBAL_SETTINGS
from marimo._mcp.server.main import setup_mcp_server
from marimo._messaging.notification import StartupLogsNotification
from marimo._runtime.commands import SerializedCLIArgs
from marimo._server.config import (
    StarletteServerStateInit,
)
from marimo._server.file_router import AppFileRouter
from marimo._server.lsp import CompositeLspServer, NoopLspServer
from marimo._server.main import create_starlette_app
from marimo._server.registry import LIFESPAN_REGISTRY
from marimo._server.session_manager import SessionManager
from marimo._server.tokens import AuthToken
from marimo._server.utils import (
    initialize_asyncio,
    initialize_fd_limit,
)
from marimo._server.uvicorn_utils import initialize_signals
from marimo._session.model import SessionMode
from marimo._tracer import LOGGER
from marimo._utils.lifespans import Lifespans
from marimo._utils.net import find_free_port

DEFAULT_PORT = 2718
PROXY_REGEX = re.compile(r"^(.*):(\d+)$")


def _execute_startup_command(
    command: str, session_manager: SessionManager
) -> None:
    """Execute a server startup command in a background thread and stream logs."""

    def run_command() -> None:
        buffer = StartupLogsNotification(content="", status="start")

        def write_to_all_sessions(
            content: StartupLogsNotification,
            buffer: StartupLogsNotification,
        ) -> None:
            for session in session_manager.sessions.values():
                # Clear buffer if it has content
                if buffer.content != "":
                    session.notify(buffer, from_consumer_id=None)
                    buffer = StartupLogsNotification(
                        content="", status="start"
                    )
                session.notify(content, from_consumer_id=None)
            else:
                buffer.content += content.content
                buffer.status = content.status

        try:
            # Broadcast start message to all sessions
            write_to_all_sessions(
                StartupLogsNotification(content="", status="start"), buffer
            )

            # Execute the command
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Stream stderr to stdout
                text=True,
                universal_newlines=True,
            )

            # Stream output line by line
            if process.stdout:
                for line in process.stdout:
                    write_to_all_sessions(
                        StartupLogsNotification(content=line, status="append"),
                        buffer,
                    )
                    echo(line, nl=False)

            # Wait for process to complete
            return_code = process.wait()

            # Broadcast completion message
            final_message = (
                f"\nProcess completed with exit code: {return_code}\n"
            )
            write_to_all_sessions(
                StartupLogsNotification(content=final_message, status="done"),
                buffer,
            )
            echo(final_message)

        except Exception as e:
            # Broadcast error message
            error_message = f"\nError executing startup command: {str(e)}\n"
            write_to_all_sessions(
                StartupLogsNotification(content=error_message, status="done"),
                buffer,
            )
            echo(error_message)

    # Run the command in a background thread
    thread = threading.Thread(target=run_command)
    thread.start()


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
    skew_protection: bool,
    remote_url: Optional[str] = None,
    mcp: bool = False,
    server_startup_command: Optional[str] = None,
    asset_url: Optional[str] = None,
    timeout: Optional[float] = None,
) -> None:
    """
    Start the server.
    """
    import packaging.version

    # Defaults when mcp is enabled
    if mcp:
        # Turn on watch mode
        watch = True
        # Turn off skew protection for MCP server
        # since it is more convenient to connect to.
        # Skew protection is not a security thing, but rather
        # prevents connecting to old servers.
        skew_protection = False

    # Find a free port if none is specified
    # if the user specifies a port, we don't try to find a free one
    port = port or find_free_port(DEFAULT_PORT, addr=host)

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

    if watch and config_reader.is_auto_save_enabled:
        LOGGER.warning("Enabling watch mode may interfere with auto-save.")

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

    session_manager = SessionManager(
        file_router=file_router,
        mode=mode,
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

    log_level = "info" if development_mode else "error"

    lifespans_list = [
        lifespans.lsp,
        lifespans.mcp,
        lifespans.etc,
        lifespans.signal_handler,
        lifespans.logging,
        lifespans.open_browser,
        lifespans.tool_manager,
        *LIFESPAN_REGISTRY.get_all(),
    ]

    mcp_enabled = mcp and mode == SessionMode.EDIT

    if mcp_enabled:
        from marimo._mcp.server.lifespan import mcp_server_lifespan

        lifespans_list.append(mcp_server_lifespan)

    (external_port, external_host) = _resolve_proxy(port, host, proxy)
    enable_auth = not AuthToken.is_empty(session_manager.auth_token)
    app = create_starlette_app(
        base_url=base_url,
        host=external_host,
        lifespan=Lifespans(lifespans_list),
        allow_origins=allow_origins,
        enable_auth=enable_auth,
        lsp_servers=list(lsp_composite_server.servers.values())
        if lsp_composite_server is not None
        else None,
        skew_protection=skew_protection,
        timeout=timeout,
    )

    if mcp_enabled:
        setup_mcp_server(app)

    init_state = StarletteServerStateInit(
        port=external_port,
        host=external_host,
        base_url=base_url,
        asset_url=asset_url,
        headless=headless,
        quiet=quiet,
        session_manager=session_manager,
        config_manager=config_reader,
        remote_url=remote_url,
        mcp_server_enabled=mcp,
        skew_protection=skew_protection,
        enable_auth=enable_auth,
    )
    init_state.apply(app.state)

    # Resource initialization
    # Increase the limit on open file descriptors to prevent resource
    # exhaustion when opening multiple notebooks in the same server.
    initialize_fd_limit(limit=4096)
    initialize_signals()

    # Platform-specific initialization of the event loop policy (Windows
    # requires SelectorEventLoop).
    initialize_asyncio()

    if packaging.version.Version(
        uvicorn.__version__
    ) >= packaging.version.Version("0.36.0"):
        # uvicorn 0.36.0 introduced custom event loop policies, and uses a loop
        # factory instead of asyncio's global event loop policy (the latter was
        # deprecated in Python 3.14).
        #
        # We have to use a SelectorEventLoop on Windows in particular (because
        # we use the add_reader API); Selector is already the default on Unix.
        #
        # The syntax is awkward: <module>:function
        edit_loop_policy = "asyncio:SelectorEventLoop"
    else:
        # Older versions of uvicorn use the globally configured event
        # loop policy
        edit_loop_policy = "asyncio"

    # Under uvloop, reading the socket we monitor under add_reader()
    # occasionally throws BlockingIOError (errno 11, or errno 35,
    # ...). RUN mode no longer uses a socket (it has no IPC) but EDIT
    # does, so force asyncio.
    loop_policy = edit_loop_policy if mode == SessionMode.EDIT else "auto"

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            port=port,
            host=host,
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
            # loop can take an arbitrary string but mypy is complaining
            # expecting it to be a Literal
            loop=loop_policy,  # type:ignore[arg-type]
        )
    )
    app.state.server = server

    # Execute server startup command if provided
    if server_startup_command:
        _execute_startup_command(server_startup_command, session_manager)

    server.run()
